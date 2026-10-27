"""Skydd för den publika demon när lösenordet är borta.

Kontrollrummets knappar är vanliga API-anrop, och demon är delad: alla besökare ser samma kedja. Vad som gäller
var (preciserat efter del a2, 2026-10-18):

  * Bara för anrop via Caddy (som sätter X-Forwarded-For) och i den externa varianten: ursprungskontrollen (1),
    rättvisepausen (2) och återhämtningsperioden. Anrop direkt mot dashboardens port (testerna, värdens skript) berörs inte.
  * Alltid i den externa varianten, oavsett väg: uteslutningar och felinjektioner BOKFÖRS, och städningen (main.py)
    släpper in och slår av dem när fristen gått, även om de satts direkt mot porten.

  1. Samma ursprung: ett POST-anrop måste komma från kontrollrummets egen sida (Origin = värdnamnet).
     Det stoppar andra webbplatsers formulär och enkla skript. Ett skript kan förfalska huvudet, så
     detta är ett nät, inte en mur; hastighetsgränsen i Caddy och nattens nollställning är resten.
  2. Rättvis kö: den som just körde ett jobb får vänta PAUS_EFTER_JOBB_S innan nästa, så att en
     ensam besökare inte kan hålla jobblåset för alla andra. Prövas när jobbet ANTAS (efter att kroppen lästs).
     Gäller INTE besökare med en egen vy (sessioner.py, DASH_SESSIONER=ja): där ger jobbkön rättvisan (ett nytt jobb hamnar
     sist i kön), och en paus hindrade bara besökaren från att gå vidare till nästa steg (besökartestet 2026-10-22).
  3. Uteslutningar släpps in igen av sig själva efter UTESTANGNING_S (en besökare ska inte kunna
     förstöra demon för alla andra fram till nattens nollställning).
  4. Felinjektion slås av av sig själv efter FELINJEKTION_S.

Tiderna i 3 och 4 är ABSOLUTA (rättning efter Codex del d, fynd D1): fristen räknas från den första
aktiveringen och förnyas aldrig av ett upprepat anrop (aktivering är idempotent). När en störning har
upphört – av sig själv eller för att någon återinsatte/slog av – gäller dessutom en återhämtningsperiod
(AVKYLNING_S) då samma störning inte får slås på igen. Perioden är gemensam för alla besökare, inte per IP.

Hur länge en störning kan pågå (del a2, A2-08): fristen + upp till ett städintervall (main.STADA_INTERVALL_S, 10 s) +
den tid städvarvet tar, dvs. källornas svarstid för varje åtgärd i varvet (högst kallor.TIMEOUT, 8 s, per åtgärd). Svarar
källan inte alls försöker städningen igen varje varv, så då finns ingen övre gräns förrän källan svarar. Det är ingen hård
realtidsgaranti. En ny störning får börja först efter AVKYLNING_S. Varje störning har ett eget lås (STORNINGSLAS) så att
kontroll, källanrop och bokföring inte kan korsa varandra (A2-02). Kopplingen till appen prövas i tests/skydd_integration.py (K24).
"""
import math
import os
import threading
import time
from urllib.parse import urlsplit

import sessioner

PAUS_EFTER_JOBB_S = float(os.environ.get("DASH_PAUS_EFTER_JOBB_S", "8"))
UTESTANGNING_S = float(os.environ.get("DASH_UTESTANGNING_S", "180"))
FELINJEKTION_S = float(os.environ.get("DASH_FELINJEKTION_S", "300"))
AVKYLNING_S = float(os.environ.get("DASH_AVKYLNING_S", "60"))

_LAS = threading.Lock()
_SENASTE = {"klient": None, "jid": 0}              # vem som startade det senast noterade jobbet, och dess id
_SLUT = {}                                         # jobb-id -> monotonic-tid då jobbet tog slut
UTESTANGDA = {}                                    # mottagare -> monotonic-tid då den stängdes ute
FELINJEKTION_SEDAN = None                          # monotonic-tid då felinjektion slogs på
# Ett lås PER störning ("ute:dhi", "ute:stad", "fel"), hållet över hela förloppet kontroll → källanrop → bokföring
# (del a2, A2-02). Annars kunde en återinsättning och en ny uteslutning korsa varandra så att källan stod utestängd
# medan bokföringen var tom, och då släpptes ingen in automatiskt. Låsen gäller bara samma störning; källanropens timeout
# (kallor.TIMEOUT, 8 s) begränsar hur länge någon kan vänta. Det globala _LAS tas aldrig medan ett källanrop pågår.
STORNINGSLAS = {"ute:dhi": threading.Lock(), "ute:stad": threading.Lock(), "fel": threading.Lock()}
_AVKYLNING_TILL = {}                               # störningsnyckel ("ute:dhi", "fel") -> monotonic-tid då den får slås på igen


def via_proxy(request):
    """Anropet kommer via Caddy (som sätter X-Forwarded-For)."""
    return bool(request.headers.get("x-forwarded-for"))


def klient(request):
    """Besökarens adress: första posten i X-Forwarded-For (Caddy skriver över ett förfalskat huvud)."""
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() or (request.client.host if request.client else "okänd")


def samma_ursprung(request):
    """True om POST-anropet kommer från sidans egen origin: schema, värdnamn och port ska alla stämma.

    Schemat jämförs mot X-Forwarded-Proto (Caddy sätter det) när det finns, annars godtas bara http/https.
    Det är ett skydd mot andra WEBBPLATSER (en webbläsare låter inte främmande skript sätta Origin), inte mot
    curl: ett skript kan skriva vilket Origin-huvud som helst."""
    if request.headers.get("sec-fetch-site", "") == "cross-site":
        return False
    ursprung = request.headers.get("origin", "")
    if not ursprung:
        return False
    delar = urlsplit(ursprung)
    forvantat_schema = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if delar.scheme not in ("http", "https") or (forvantat_schema and delar.scheme != forvantat_schema):
        return False
    return delar.netloc == request.headers.get("host", "")


def vanta_efter_jobb(request, jobb_kor, nu=None):
    """Sekunder (avrundat uppåt) besökaren måste vänta för att starta ett nytt jobb, annars 0.

    Rent läsande (GET /api/skydd får inte sätta något). Pausen räknas från sluttiden för det jobb besökaren senast
    startade, identifierat med jobbets id (del a2, A2-04): en sen eller omkastad notering kan inte flytta pausen till ett
    annat jobb. jobb_kor = True om ett jobb kör just nu (då är det "upptaget"-felet som gäller, inte kön).
    Prövas både tidigt (middleware) och vid själva antagningen, efter att kroppen lästs."""
    if sessioner.aktuell() is not None:
        return 0
    nu = time.monotonic() if nu is None else nu
    k = klient(request)
    with _LAS:
        if jobb_kor or _SENASTE["klient"] != k:
            return 0
        slut = _SLUT.get(_SENASTE["jid"])
        if slut is None:
            return 0
        kvar = slut + PAUS_EFTER_JOBB_S - nu
        return math.ceil(kvar) if kvar > 0 else 0


def noterat_jobbstart(request, jid):
    """Noterar vem som startade jobb `jid`. En notering för ett ÄLDRE jobb än det senast noterade ignoreras, så att ett
    sent svar inte skriver över en nyare start (A2-04). Kan göras efter att jobbet redan tagit slut: sluttiden ligger per id."""
    with _LAS:
        if jid >= _SENASTE["jid"]:
            _SENASTE["klient"] = klient(request)
            _SENASTE["jid"] = jid


def jobb_slut(jid, nu=None):
    """Anropas av jobbmodulen när jobb `jid` avslutats: pausen räknas från själva sluttiden."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        _SLUT[jid] = nu
        for gammal in sorted(_SLUT)[:-50]:        # håll bokföringen liten
            del _SLUT[gammal]


def _avkyl(nyckel, nu):
    if AVKYLNING_S > 0:
        _AVKYLNING_TILL[nyckel] = nu + AVKYLNING_S


def avkylning_kvar(nyckel, nu=None):
    """Sekunder (uppåt) kvar av återhämtningsperioden för en störning, annars 0."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        kvar = _AVKYLNING_TILL.get(nyckel, 0) - nu
    return math.ceil(kvar) if kvar > 0 else 0


def utestangd(mottagare, nu=None):
    """Noterar en uteslutning. Idempotent: pågår den redan behålls den ursprungliga starttiden (ingen förnyelse).
    Returnerar True om uteslutningen är ny."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        if mottagare in UTESTANGDA:
            return False
        UTESTANGDA[mottagare] = nu
        return True


def insatt(mottagare, nu=None):
    """Noterar att en part släppts in (för hand eller av städningen) och startar återhämtningsperioden."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        if UTESTANGDA.pop(mottagare, None) is not None:
            _avkyl("ute:" + mottagare, nu)


def felinjektion_pa(pa, nu=None):
    """Noterar att felinjektionen slagits på/av. På när den redan är på ändrar inte starttiden (ingen förnyelse)."""
    global FELINJEKTION_SEDAN
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        if pa:
            if FELINJEKTION_SEDAN is None:
                FELINJEKTION_SEDAN = nu
        elif FELINJEKTION_SEDAN is not None:
            FELINJEKTION_SEDAN = None
            _avkyl("fel", nu)


def utestangning_forfallen(mottagare, nu=None):
    """True om uteslutningen fortfarande är bokförd och fristen gått ut. Prövas igen UNDER störningens lås i städningen,
    så att en gammal ögonblicksbild från forfallna() inte kan agera på en senare uteslutning (A2-02)."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        t = UTESTANGDA.get(mottagare)
        return t is not None and UTESTANGNING_S > 0 and nu - t >= UTESTANGNING_S


FEL_LACKA_SEDAN = None      # monotonic-tid då en besökares egna felinjektion kan ha lämnats kvar i FCF (nollställningen misslyckades eller är osäker)
FEL_LACKA_GRANS_S = 15      # städloopen slår av ett kvarlämnat fel efter så här lång tid; nästa leverans städar dessutom före sig


def fel_lacka(pa, nu=None):
    """Noterar att ett eget felinjektionsläge kan ligga kvar i FCF (pa=True) eller att det är avslaget (pa=False). Driver inte bannern."""
    global FEL_LACKA_SEDAN
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        if pa:
            if FEL_LACKA_SEDAN is None:
                FEL_LACKA_SEDAN = nu
        else:
            FEL_LACKA_SEDAN = None


def fel_lacka_kvar():
    with _LAS:
        return FEL_LACKA_SEDAN is not None


def fel_lacka_forfallen(nu=None):
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        return FEL_LACKA_SEDAN is not None and nu - FEL_LACKA_SEDAN >= FEL_LACKA_GRANS_S


def felinjektion_forfallen(nu=None):
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        return FELINJEKTION_SEDAN is not None and FELINJEKTION_S > 0 and nu - FELINJEKTION_SEDAN >= FELINJEKTION_S


def forfallna(nu=None):
    """(mottagare som ska släppas in, om felinjektionen ska slås av). Tar INTE bort något ur bokföringen:
    städloopen anropar insatt()/felinjektion_pa(False) först när åtgärden hos källan lyckats, så att ett
    tillfälligt fel (identity hub nere) inte gör att en uteslutning glöms bort och blir bestående."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        inslapp = [m for m, t in UTESTANGDA.items() if UTESTANGNING_S > 0 and nu - t >= UTESTANGNING_S]
        av = FELINJEKTION_SEDAN is not None and FELINJEKTION_S > 0 and nu - FELINJEKTION_SEDAN >= FELINJEKTION_S
    return inslapp, av


def kvar_sekunder(request, jobb_kor, nu=None):
    """Det besökaren ska se tickande: sekunder kvar till automatisk återinsättning per part, till att
    felinjektionen slås av, och till att besökaren får köra igen. Servern räknar; webbläsaren tickar ner."""
    nu = time.monotonic() if nu is None else nu
    with _LAS:
        ute = {m: max(0, math.ceil(UTESTANGNING_S - (nu - t))) for m, t in UTESTANGDA.items()} if UTESTANGNING_S > 0 else {}
        fel = (max(0, math.ceil(FELINJEKTION_S - (nu - FELINJEKTION_SEDAN)))
               if FELINJEKTION_SEDAN is not None and FELINJEKTION_S > 0 else None)
    paus = vanta_efter_jobb(request, jobb_kor, nu) if via_proxy(request) else 0
    return {"utestangningS": ute, "felinjektionS": fel, "pausS": paus, "regler": regler()}


def regler():
    """De fasta tiderna (sekunder), så att förklaringen på sidan alltid stämmer med inställningarna."""
    return {"utestangningS": UTESTANGNING_S, "felinjektionS": FELINJEKTION_S,
            "pausS": 0 if sessioner.PA else PAUS_EFTER_JOBB_S}      # med egna vyer ger jobbkön rättvisan: ingen paus
