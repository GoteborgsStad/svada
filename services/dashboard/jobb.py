#!/usr/bin/env python3
"""
jobb.py – "kör steget"-knapparna.

Åtgärderna körs som BAKGRUNDSJOBB med en löpande logg. Skälet är krasst
praktiskt: en kontraktsförhandling tar tiotals sekunder och en transfer kan
behöva ett omtag (se kedjan.py). Ett synkront HTTP-anrop hade
antingen timeat ut i webbläsaren eller tvingat fram en tystnad på en minut
mitt i en demo. Nu skrivs varje delsteg ut medan det händer.

ETT JOBB I TAGET. Kedjan är en kedja: två samtidiga transferar skulle
konkurrera om samma dataplan och göra utfallet obegripligt för den som tittar.
Startas ett jobb medan ett annat kör svarar API:t 409.

MED SESSIONER (sessioner.py, den delade externa demon) är jobben fortfarande ett i taget, men en annan besökares jobb ger en KÖ i stället för
ett fel: jobbet får status "kö" och startas när det föregående är klart. Varje besökare ser bara sina egna jobb och har högst ett
pågående (eller köat) i taget. Utan session (direktanrop, intern variant) gäller det gamla: 409.

Varje jobb skriver också en post i auditloggen (audit.notera) – knapptrycken
är händelser i kedjan och ska finnas kvar när jobbet är borta ur listan.
"""

import contextlib
import os
import re
import threading
import time
from collections import deque

import audit
import kallor
import kedjan
import meddelanden
import sessioner
import skydd
from kallor import KallFel
from meddelanden import msg

JOBB = []
_LAS = threading.Lock()
_KOR = threading.Event()          # satt = ett jobb kör just nu
RETENTION = 40
KO = deque()                      # köade jobb (bara med sessioner), äldst först; ändras bara under _LAS
MAX_KO = int(os.environ.get("DASH_JOBB_KO_MAX", "20"))


class Jobbfel(Exception):
    """Ett fel som stoppar ett jobb. Bär ett lagrat meddelande (kod + parametrar), se meddelanden.py."""

    def __init__(self, kod, **p):
        super().__init__(meddelanden.visa(kod, p, "sv"))
        self.kod = kod
        self.p = p

    def meddelande(self):
        return msg(self.kod, **self.p)


class Upptaget(Jobbfel):
    pass


class Jobb:
    def __init__(self, jid, atgard, steg, etikett_kod):
        self.id = jid
        self.atgard = atgard
        self.steg = steg
        self.etikett_kod = etikett_kod
        self.etikett = meddelanden.visa(etikett_kod, {}, "sv")
        self.startad = audit.nu()
        self.klar = None
        self.status = "kör"
        self.rader = []
        self.resultat = None
        self.utfall = None          # "avvisad" | "inget-avtal": jobbet gjorde sitt, men åtgärden gav inget (visas i statusmärket)
        self.session = None         # besökarens session (sessioner.py), eller None utan sessioner
        self.argument = None

    def logg(self, kod, **p):
        """En loggrad som kod + parametrar; texten skapas vid visning (se meddelanden.py)."""
        rad = {"tid": audit.nu(), "kod": kod, "p": p}
        self.rader.append(rad)
        print("[jobb %d] %s" % (self.id, meddelanden.visa(kod, p, "sv")), flush=True)

    def till_json(self):
        rader = [dict(r, text=meddelanden.visa(r["kod"], r["p"], "sv")) for r in self.rader]
        return {"id": self.id, "atgard": self.atgard, "steg": self.steg,
                "etikett": self.etikett, "etikettKod": self.etikett_kod, "status": self.status,
                "startad": self.startad, "klar": self.klar, "utfall": self.utfall,
                "kopos": _ko_plats(self) if self.status == "kö" else None,
                "rader": rader, "resultat": self.resultat}


def _ko_plats(jobb):
    """Plats i kön (1 = näst på tur), eller None. Läses utan lås: ett ögonblicksfel är ofarligt och ger None."""
    try:
        return list(KO).index(jobb) + 1
    except (ValueError, RuntimeError):
        return None


def _synlig(j, s):
    """Med en session ser besökaren bara sina egna jobb; utan session (direktanrop, intern variant) alla."""
    return s is None or j.session is s


def lista():
    s = sessioner.aktuell()
    with _LAS:
        return [j.till_json() for j in JOBB if _synlig(j, s)]


_B_SEKVENS = ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b")


class _GlobaltTillstand:
    """Det som sessionen håller för en besökare, för anrop utan session (direktanrop, intern variant): ett tillstånd för alla."""
    def __init__(self):
        self.gjort = set()
        self.a_laget = None
        self.a_forut = None


_GLOBALT = _GlobaltTillstand()


def _tillstand(session):
    return session if session is not None else _GLOBALT


def _notera(jobb):
    """Bokför ett avslutat jobb i besökarens tillstånd (inte ur jobblistan, som rensas efter 40 jobb och delas av alla besökare).
    A-kedjan är en liten tillståndsmaskin: begärd -> godkänd -> levererad; ett avslag, en hävning eller en nekad eller felad
    leverans av A tar besökaren tillbaka till början av A-kedjan (ny förhandling); ett misslyckat beslut ändrar inget."""
    t = _tillstand(jobb.session)
    ok = jobb.status == "klar" and not jobb.utfall
    a = jobb.atgard
    if a in _B_SEKVENS:
        if ok:
            t.gjort.add(a)
    elif a == "forhandla-a":
        if ok:
            # En ny begäran medan ett avtal gäller: läget före sparas, så att ett avslag som inte häver något tar besökaren tillbaka dit.
            t.a_forut = t.a_laget if t.a_laget in ("godkant", "levererat") else None
            t.a_laget = "begart"
    elif a == "kov-godkann":
        if ok:
            t.a_laget = "godkant"
            t.a_forut = None
    elif a == "transfer-a":
        t.a_laget = "levererat" if ok else None
    elif a == "kov-avsla":
        if jobb.status == "klar":          # ett misslyckat beslut (401, tjänsten nere) ändrar inget
            havda = (jobb.resultat or {}).get("havdaAvtal") if isinstance(getattr(jobb, "resultat", None), dict) else None
            # Hävde avslaget tidigare avtal: börja om. Annars gäller det gamla avtalet fortfarande: tillbaka till läget före begäran.
            t.a_laget = None if (havda or jobb.utfall == "inget-avtal") else t.a_forut
            t.a_forut = None
    elif a == "kov-hav":
        if jobb.status == "klar":
            t.a_laget = None
            t.a_forut = None


def nasta_atgard():
    """Nästa åtgärd i den rekommenderade ordningen som besökaren inte redan gjort (eller har pågående), eller None. Används för att
    markera rätt knapp i kontrollrummet. Med en session räknas bara besökarens egna jobb."""
    s = sessioner.aktuell()
    t = _tillstand(s)
    with _LAS:
        pag = {j.atgard for j in JOBB if _synlig(j, s) and j.status in ("kör", "kö")}
    for a in _B_SEKVENS:
        if a not in t.gjort and a not in pag:
            return a
    if t.a_laget is None:
        return None if "forhandla-a" in pag else "forhandla-a"
    if t.a_laget == "begart":
        return None if "kov-godkann" in pag else "kov-godkann"
    if t.a_laget == "godkant":
        return None if "transfer-a" in pag else "transfer-a"
    return "analysera"          # A är levererat: sista steget är att se analysen (steg 6, utan knapp); sidan avslutar raden när steget öppnats


def hamta(jid):
    s = sessioner.aktuell()
    with _LAS:
        for j in JOBB:
            if j.id == jid and _synlig(j, s):
                return j.till_json()
    return None


def aktivt():
    """Pågående jobb. Med en session: besökarens eget jobb, körande eller köat. Utan: det jobb som kör just nu."""
    s = sessioner.aktuell()
    with _LAS:
        for j in JOBB:
            if s is None:
                if j.status == "kör":
                    return j.till_json()
            elif j.session is s and j.status in ("kör", "kö"):
                return j.till_json()
    return None


# ---------------------------------------------------------------------------
# Åtgärderna
# ---------------------------------------------------------------------------
def _senaste_avtal(asset, session=None):
    """Nyaste förhandlingen med avtal för ett asset (nyast först i svaret). Med en session bara besökarens egna förhandlingar."""
    for f in kallor.forhandlingar(limit=50):
        if f.get("assetId") == asset and f.get("contractAgreementId"):
            if session is not None and f.get("@id") not in session.forhandlingar:
                continue
            return f["contractAgreementId"], f.get("@id")
    return None, None


def _kor_batch(jobb):
    svar = kallor.fcf_kor_batch()
    jobb.logg("jobb.batch", batch=svar.get("batchId"), dygn=svar.get("modelledDay"),
              antal=svar.get("recordCount", 0))
    # "csv/SSO1_01-4526 – …": filsökvägen visas inte, bara mätserien och dess omfattning.
    jobb.logg("jobb.underlag", kalla=re.sub(r"^csv/", "", str(svar.get("measurementSource") or "")))
    return svar


# EDC:s strukturerade fel när DHI nekar staden: consumerns management-API svarar 502 och bär providerns
# CatalogError med kod "401" (JSON i JSON, ofta kapad, därför ett mönster på strukturen och inte en JSON-tolkning).
_DSP_NEKAD = re.compile(r'CatalogError\\*"\s*,\s*\\*"code\\*"\s*:\s*\\*"401\\*"')


def dsp_nekad(fel):
    """True bara när felet är DHI:s nekande över DSP (502 + CatalogError med kod 401), inte när texten råkar innehålla
    401 (ett request-id, en timeout) eller när consumerns egen management-autentisering fallerar (del a2, A2-06)."""
    return getattr(fel, "status", None) == 502 and bool(_DSP_NEKAD.search(str(getattr(fel, "kropp", "") or "")))


def _katalog_eller_nekad():
    """Katalogen från DHI. Nekar DHI staden (t.ex. när stadens medlemsintyg är återkallat) blir det ett begripligt
    besked i stället för den råa 502-strängen från EDC (gränssnittstestet 2026-10-17, fynd M1)."""
    try:
        return kedjan.hamta_katalog()
    except KallFel as fel:
        if dsp_nekad(fel):
            raise Jobbfel("fel.stad_nekad_dhi")
        raise


def _hamta_katalog(jobb):
    katalog = _katalog_eller_nekad()
    for asset in (kallor.ASSET_B, kallor.ASSET_A):
        d = kedjan.dataset_for(katalog, asset)
        jobb.logg("jobb.katalograd", asset=asset, namn=d.get("edc:name"), klass=d.get("edc:informationClass"),
                  atkomst=d.get("edc:accessRights"), villkor=d.get("odrl:terms"))
    return katalog


def _forhandla(jobb, asset):
    dist = "A" if asset == kallor.ASSET_A else "B"
    katalog = _katalog_eller_nekad()
    fid = kedjan.forhandla(asset, katalog)
    if jobb.session is not None:
        jobb.session.forhandlingar.add(fid)          # besökarens egen förhandling: bara den visas i KoV-rutan och ger avtal i analysen
    jobb.logg("jobb.forh_startad", id=fid, dist=dist)
    if dist == "A":
        jobb.logg("jobb.a_kraver_kov", sek=25)
        post = None
        for _ in range(25):
            post = kedjan.kov_post_for(fid)
            if post:
                break
            time.sleep(1)
        if post:
            jobb.logg("jobb.kon", id=post.get("id"), tillstand=post.get("state"),
                      pending=post.get("pending"), beslut=post.get("kovBeslut"))
            if post.get("kovBeslut") == "VANTANDE":
                jobb.logg("jobb.kov_panel")
                return {"forhandlingId": fid, "kov": post, "avtal": None}
        avtal, tillstand = kedjan.vanta_avtal(fid, 30)
    else:
        # Besked direkt, inte först efter väntan: är DHI utestängd slutförs förhandlingen aldrig (L19).
        jobb.logg("jobb.vantar_avtal", sek=30)
        avtal, tillstand = kedjan.vanta_avtal(fid, 30)
    if avtal and jobb.session is not None:
        jobb.session.avtal.add(avtal)
    if avtal:
        jobb.logg("jobb.avtal", avtal=avtal, tillstand=tillstand)
    else:
        jobb.utfall = "inget-avtal"
        jobb.logg("jobb.inget_avtal", tillstand=tillstand)
        try:
            ute = [p.get("mottagare") for p in (kallor.svada_status() or [])
                   if p.get("aterkallat") and "Membership" in str(p.get("typ"))]
        except KallFel:
            ute = []
        if ute:
            jobb.logg("jobb.inget_avtal_utestangd", delar=sorted(set(ute)))
    return {"forhandlingId": fid, "avtal": avtal, "tillstand": tillstand}


def _ingest_meddelande(post):
    """Ingests post som meddelande: dess egen kod + parametrar, annars den svenska texten."""
    if post.get("kod"):
        return msg(post["kod"], **(post.get("parametrar") or {}))
    return meddelanden.fri(post.get("detalj") or "")


def _ingest_exempel(post):
    """Första exemplet ur en avvisning, som meddelande om ingest skickat det strukturerat."""
    ex = (post.get("exempelParametrar") or [None])[0]
    if ex and ex.get("kod"):
        return msg(ex["kod"], **(ex.get("parametrar") or {}))
    return meddelanden.fri(post["exempel"][0])


@contextlib.contextmanager
def _egen_felinjektion(jobb):
    """Besökarens eget felinjektionsläge gäller bara medan hennes egen leverans körs. Jobben körs ett i taget för hela demon, så ingen annan
    besökares leverans kan hämta data medan felet är påslaget i FCF; direkt efteråt (även vid fel) slås det av. Utan session (direktanrop,
    intern variant) finns inget eget läge: där gäller det gemensamma läget som förut.
    Säkerhetsnät: läckskyddet (skydd.fel_lacka) sätts INNAN FCF rörs, så även ett tvetydigt fel vid påslagningen (timeout efter att FCF tagit
    emot anropet) eller ett misslyckat avslag städas: av nästa leverans före dess start, och av städloopen efter FEL_LACKA_GRANS_S."""
    if skydd.fel_lacka_kvar():          # ett tidigare jobb kan ha lämnat felet kvar: städa före den här leveransen
        try:
            kallor.fcf_nollstall_fel()
            skydd.fel_lacka(False)
        except Exception:               # noqa: BLE001 – tjänsten kan vara nere; flaggan står kvar och städloopen försöker igen
            pass
    lagen = dict(getattr(jobb.session, "fel_lagen", None) or {}) if jobb.session is not None else {}
    aktiva = sorted(k for k, v in lagen.items() if v)
    if not aktiva:
        yield
        return
    skydd.fel_lacka(True)
    try:
        jobb.logg("jobb.felinjektion_pa", lagen=", ".join(aktiva))
        kallor.fcf_satt_fel({k: bool(lagen.get(k)) for k in ("schemadrift", "saknade_parametrar", "gis_i_b")})
        yield
    finally:
        try:
            kallor.fcf_nollstall_fel()
            skydd.fel_lacka(False)
            jobb.logg("jobb.felinjektion_av")
        except Exception as fel:        # noqa: BLE001 – flaggan står kvar: nästa leverans och städloopen slår av felet
            jobb.logg("jobb.felinjektion_kvar", fel=str(fel))


def _transfer(jobb, asset):
    dist = "A" if asset == kallor.ASSET_A else "B"
    avtal, fid = _senaste_avtal(asset, jobb.session)
    if not avtal:
        raise Jobbfel("fel.inget_avtal_kov" if dist == "A" else "fel.inget_avtal", dist=dist, steg=3)
    jobb.logg("jobb.anvander_avtal", avtal=avtal, forh=fid)
    if dist == "A":
        try:
            st = kallor.avtalsstatus(avtal).get("status")
        except KallFel:
            st = None
        if st == "UTGANGET":
            raise Jobbfel("fel.avtal_utgangit", avtal=avtal)
        if st == "HAVT":
            raise Jobbfel("fel.avtal_havt", avtal=avtal)
    with _egen_felinjektion(jobb):
        svar = kedjan.kor_transfer(avtal, jobb.logg)
    kvitto = svar.get("kvitto") or {}
    if kvitto.get("resultat") == "LEVERERAD":
        jobb.logg("kedja.kvitterad", detalj=_ingest_meddelande(kvitto))
    else:
        jobb.utfall = "avvisad"
        jobb.logg("kedja.avvisad", orsak=kvitto.get("orsak"), detalj=_ingest_meddelande(kvitto))
        if kvitto.get("exempel"):
            jobb.logg("kedja.exempel", exempel=_ingest_exempel(kvitto))
    return svar


def agd_forhandling(session, provider_id):
    """Tillhör DHI:s förhandling `provider_id` besökaren? DHI:s correlationId är stadens förhandlings-id, som besökarens egna jobb
    har skrivit upp. Utan session (direktanrop, intern variant) är allt tillåtet, som förut."""
    if session is None:
        return True
    for post in kedjan.kov_kon():
        if post.get("id") == provider_id:
            return post.get("correlationId") in session.forhandlingar
    return False


def agd_dhi_avtal(session, dhi_avtals_id):
    """Är DHI:s avtal `dhi_avtals_id` ett av besökarens egna avtal (stadens register kopplar stadens id till DHI:s)?"""
    if session is None:
        return True
    return any(a.get("dhiAvtalId") == dhi_avtals_id and a.get("id") in session.avtal
               for a in kallor.avtalsregister().get("avtal", []))


def _har_gallande_a_avtal(session):
    """Finns det ett gällande avtal om A (besökarens eget; utan session något)? Läses ur stadens avtalsregister."""
    try:
        for a in kallor.avtalsregister().get("avtal", []):
            if a.get("distribution") == "A" and a.get("status") == "GALLANDE" and (session is None or a.get("id") in session.avtal):
                return True
    except KallFel:
        pass
    return False


def _kov_beslut(jobb, forhandlings_id, beslut):
    if not agd_forhandling(jobb.session, forhandlings_id):
        raise Jobbfel("fel.inte_din_forhandling")          # servern vägrar beslut på andras förhandlingar, oavsett vad sidan visar
    svar = kallor.kov_beslut(forhandlings_id, beslut)
    audit.notera_beslutstid(forhandlings_id)
    jobb.logg("jobb.kov_beslut", beslut=svar.get("kovBeslut"), tillstand=svar.get("state"),
              pending=svar.get("pending"))
    if beslut == "avsla":
        havda = svar.get("havdaAvtal") or []
        if havda:
            jobb.logg("jobb.avslag_havde", havda=list(havda))
        else:
            jobb.logg("jobb.avslag_havde_inget")
    korrelation, orsak = None, None
    for post in kedjan.kov_kon():
        if post.get("id") == forhandlings_id:
            korrelation = post.get("correlationId")
            orsak = post.get("errorDetail")
    if korrelation:
        avtal, tillstand = kedjan.vanta_avtal(korrelation, 60)
        if avtal and jobb.session is not None:
            jobb.session.avtal.add(avtal)
        if avtal:
            dhi_post = kedjan.kov_post_for(korrelation) or {}
            jobb.logg("jobb.id_skiljer", stad_forh=korrelation, avtal=avtal, tillstand=tillstand,
                      dhi_forh=forhandlings_id, dhi_avtal=dhi_post.get("contractAgreementId"))
        else:
            jobb.logg("jobb.consumer_forh", id=korrelation, tillstand=tillstand)
            if beslut == "avsla" and tillstand == "TERMINATED":
                # Webinariet 2026-10: avslaget ska synas med orsak i klartext, sist i loggen (kedjevyns ruta visar
                # de två sista raderna). Orsaken är DHI:s egen (providerns förhandling); stadens förhandling bär den inte.
                if _har_gallande_a_avtal(jobb.session):
                    # Avslaget hävde inget (delad demo) och ett äldre avtal gäller: inget "inget avtal"-utfall och en text som stämmer.
                    jobb.logg("jobb.avslag_orsak_avtal_galler", orsak=orsak or "–")
                else:
                    jobb.utfall = "inget-avtal"
                    jobb.logg("jobb.avslag_orsak", orsak=orsak or "–")
    return svar


def _kov_hav(jobb, dhi_avtals_id):
    if not agd_dhi_avtal(jobb.session, dhi_avtals_id):
        raise Jobbfel("fel.inte_ditt_avtal")                # bara besökarens egna avtal går att häva
    svar = kallor.kov_hav(dhi_avtals_id)
    jobb.logg("jobb.kov_havt", avtal=dhi_avtals_id)
    for _ in range(10):
        reg = [a for a in kallor.avtalsregister().get("avtal", [])
               if a.get("dhiAvtalId") == dhi_avtals_id]
        if reg and reg[0].get("status") == "HAVT":
            jobb.logg("jobb.register_havt", avtal=reg[0].get("id"))
            break
        time.sleep(1)
    else:
        jobb.logg("jobb.register_ej_synkat")
    return svar


ATGARDER = {
    "kor-batch": ("atgard.kor-batch", 1, lambda j, a: _kor_batch(j)),
    "hamta-katalog": ("atgard.hamta-katalog", 2, lambda j, a: _hamta_katalog(j)),
    "forhandla-b": ("atgard.forhandla-b", 3,
                    lambda j, a: _forhandla(j, kallor.ASSET_B)),
    "forhandla-a": ("atgard.forhandla-a", 3,
                    lambda j, a: _forhandla(j, kallor.ASSET_A)),
    "transfer-b": ("atgard.transfer-b", 4,
                   lambda j, a: _transfer(j, kallor.ASSET_B)),
    "transfer-a": ("atgard.transfer-a", 4,
                   lambda j, a: _transfer(j, kallor.ASSET_A)),
    "kov-godkann": ("atgard.kov-godkann", 3,
                    lambda j, a: _kov_beslut(j, a["id"], "godkann")),
    "kov-avsla": ("atgard.kov-avsla", 3,
                  lambda j, a: _kov_beslut(j, a["id"], "avsla")),
    "kov-hav": ("atgard.kov-hav", 3,
                lambda j, a: _kov_hav(j, a["id"])),
}


# Fel som betyder att en spärr fungerade som den ska (inget avtal, KoV har inte godkänt, staden är utestängd). Jobbet får
# status "fel" (testerna bygger på det) men utfallet "nekad", så att sidan säger "nekad av spärren" i stället för "misslyckades"
# (gränssnittstesterna 2026-10-17/18, L1).
SPARR_KODER = ("fel.inget_avtal", "fel.inget_avtal_kov", "fel.avtal_havt", "fel.avtal_utgangit", "fel.stad_nekad_dhi")
# Av dem: de som betyder att det inte finns något gällande avtal (loggraden säger "inget gällande avtal").
_INGET_AVTAL_KODER = ("fel.inget_avtal", "fel.inget_avtal_kov", "fel.avtal_havt", "fel.avtal_utgangit")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_KRAVER_ID = ("kov-godkann", "kov-avsla", "kov-hav")


def starta(atgard, argument=None):
    """Startar ett jobb. Kastar Upptaget om ett annat jobb redan kör (utan session) eller om besökaren redan har ett pågående eller köat
    jobb, eller om kön är full (med session), och Jobbfel om åtgärden eller dess argument är ogiltiga – det prövas INNAN jobbet antas,
    så att ett felaktigt argument inte skapar ett jobb som sedan fallerar (A2-01). Med en session köas jobbet bakom det som kör."""
    if atgard not in ATGARDER:
        raise Jobbfel("fel.okand_atgard", atgard=atgard)
    if atgard in _KRAVER_ID and not (isinstance(argument, dict) and isinstance(argument.get("id"), str) and _ID.match(argument["id"])):
        raise Jobbfel("fel.jobb_argument", atgard=atgard)
    etikett_kod, steg, funktion = ATGARDER[atgard]
    s = sessioner.aktuell()
    with _LAS:
        if s is not None:
            if any(j.session is s and j.status in ("kör", "kö") for j in JOBB):
                raise Upptaget("fel.upptaget")                  # besökaren har redan ett pågående eller köat jobb
            if _KOR.is_set() and len(KO) >= MAX_KO:
                raise Upptaget("fel.kon_full")
        elif _KOR.is_set():
            raise Upptaget("fel.upptaget")
        jid = (JOBB[-1].id + 1) if JOBB else 1
        jobb = Jobb(jid, atgard, steg, etikett_kod)
        jobb.session, jobb.argument = s, argument or {}
        JOBB.append(jobb)
        # Gamla, avslutade jobb rensas; ett körande eller köat jobb får aldrig försvinna ur listan.
        while len(JOBB) > RETENTION:
            gammal = next((j for j in JOBB if j.status not in ("kör", "kö")), None)
            if gammal is None:
                break
            JOBB.remove(gammal)
        if _KOR.is_set():
            jobb.status = "kö"
            KO.append(jobb)
            starta_nu = False
        else:
            _KOR.set()
            starta_nu = True
    if starta_nu:
        _starta_trad(jobb)
    return jobb.till_json()


def _starta_trad(jobb):
    """Kör jobbet i en egen tråd. När det är klart startas nästa köade jobb (om något), annars släpps ordet."""
    etikett_kod, steg, funktion = ATGARDER[jobb.atgard]
    jid, atgard = jobb.id, jobb.atgard

    def kor():
        jobb.logg("jobb.start", etikett=msg(etikett_kod))
        try:
            jobb.resultat = funktion(jobb, jobb.argument or {})
            jobb.status = "klar"
            audit.notera(steg, "atgard", "KLAR", "audit.atgard_klar", {"etikett": msg(etikett_kod)},
                         {"jobbId": jid, "atgard": atgard})
        except (KallFel, Jobbfel) as fel:
            jobb.status = "fel"
            if isinstance(fel, Jobbfel) and fel.kod in SPARR_KODER:
                jobb.utfall = "nekad"            # spärren gjorde sitt jobb: visas inte som "misslyckades" (L1)
                jobb.logg("jobb.nekad_inget_avtal" if fel.kod in _INGET_AVTAL_KODER else "jobb.nekad",
                          orsak=fel.meddelande())
            else:
                jobb.logg("jobb.misslyckades", orsak=fel.meddelande())
            audit.notera(steg, "atgard", "FEL", "audit.atgard_fel",
                         {"etikett": msg(etikett_kod), "orsak": fel.meddelande()},
                         {"jobbId": jid, "atgard": atgard})
        except Exception as fel:                         # noqa: BLE001
            jobb.status = "fel"
            jobb.logg("jobb.ovantat", typ=type(fel).__name__, text=str(fel))
            audit.notera(steg, "atgard", "FEL", "audit.atgard_fel",
                         {"etikett": msg(etikett_kod), "orsak": meddelanden.fri(str(fel))},
                         {"jobbId": jid, "atgard": atgard})
        finally:
            jobb.klar = audit.nu()
            _notera(jobb)
            skydd.jobb_slut(jid)                 # pausen för rättvis kö räknas från sluttiden, inte från när någon tittar
            nasta = None
            with _LAS:                            # släppandet och valet av nästa jobb görs i ett svep: inget nytt jobb kan smita förbi kön
                if KO:
                    nasta = KO.popleft()
                    nasta.status = "kör"          # _KOR förblir satt: ordet går direkt vidare
                else:
                    _KOR.clear()
            if nasta is not None:
                _starta_trad(nasta)

    threading.Thread(target=kor, name="jobb-%d" % jid, daemon=True).start()
