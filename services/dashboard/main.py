#!/usr/bin/env python3
"""
main.py – dashboarden: kontrollrummet för hela SVADA PoC (komponent 14).

    docker compose -f compose.portaler.yml --profile dashboard up -d
    http://localhost:8800

Sex vyer, alla över samma JSON-API så att verifieringen kan pröva exakt det
en människa ser:

  1. KEDJAN        steg 1–10 med live-hälsa per komponent och "kör steget"
  2. AUDITLOGG     kronologisk händelsekedja aggregerad ur alla led
  3. SUVERÄNITET   KoV-godkännande (providerns API) + ODRL-blockeringsdemon
  4. AVVIKELSE     mätt (orion-dhi) vs modellerat (orion-stad/Mintaka)
  5. FELINJEKTION  reglagen mot fcf-sim + resultatet i ingest
  6. JOBB          loggen för det som kördes

API
  GET  /                          – kontrollrummet (HTML)
  GET  /health                    – dashboardens egen hälsa
  GET  /api/status                – komponenthälsa + stegens status
  GET  /api/steg                  – stegens detaljsiffror (live)
  GET  /api/steg/{nr}             – ett steg
  GET  /api/steg/{nr}/exempel     – exempelobjektet som passerar steget
  GET  /api/folj                  – följ ett värde genom kedjan (tråd)
  POST /api/atgard/{atgard}       – "kör steget" (bakgrundsjobb)
  GET  /api/jobb  /api/jobb/{id}  – jobbens loggar
  GET  /api/audit                 – auditloggen (inkl. hash-kedjans status)
  GET  /api/audit/kedja           – hash-kedjans fullstandiga integritetskontroll
  GET  /api/analys                – steg 6: inspektionsprioritering (läge B/A)
  GET  /api/analys/brunn          – steg 6: samma brunn i B och A sida vid sida
  GET  /api/kov                   – providerns KoV-kö
  POST /api/kov/{id}/{beslut}     – godkänn/avslå (hård regel 7)
  GET  /api/felinjektion          POST /api/felinjektion  /reset

HÄLSOPOLLNINGEN går i en bakgrundstråd (DASH_HALSA_INTERVALL_S) så att
sidan alltid har ett färskt svar att visa utan att varje besökare utlöser
tretton nya anrop. Detaljsiffrorna hämtas däremot on demand – de är dyrare
och behöver bara vara färska när någon tittar.
"""

import concurrent.futures
import contextvars
import html
import json
import datetime as dt
import os
import re
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import audit
import analys
import i18n
import meddelanden
import jobb as jobbmodul
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
import kallor
import kedjan
import skydd
import sessioner
import nyheter
import statistiksida
import steg as stegmodul
import vy
from gemensam import aterstall, rensa
from gemensam import statistik as statmodul
from kallor import KallFel

VERSION = "1.0.0"
DEMO_VERSION = os.environ.get("SVADA_VERSION", "okänd")      # demons version (.env); visas i sidfoten och i /api/status
# Variant: "extern" = publik demo (inga portnummer, inga interna hänvisningar),
# "intern" = standard. Sätts till extern på servern (publik-demo).
DEMO_VARIANT = os.environ.get("DEMO_VARIANT", "intern")
if DEMO_VARIANT not in ("intern", "extern"):
    raise SystemExit("DEMO_VARIANT måste vara intern eller extern")
stegmodul.UTAN_PORTAR = DEMO_VARIANT == "extern"
HALSA_INTERVALL_S = float(os.environ.get("DASH_HALSA_INTERVALL_S", "10"))
STARTAD = dt.datetime.now(dt.timezone.utc)

# id -> {"status": "upp"/"ned", "detalj": ..., "tid": ...}
HALSA = {}
HALSA_LAS = threading.Lock()

# Externa varianten: ingen interaktiv API-dokumentation (/docs, /openapi.json).
# Den innehåller kodens interna docstrings och laddar Swagger UI från ett CDN.
_EXTERN = DEMO_VARIANT == "extern"
# Samordnarens utestängning (återkallelse av medlemsintyg) fungerar, men stänger ute ALLA besökare samtidigt i en delad demo. I den
# externa varianten är den därför avstängd för anrop via Caddy (den publika vägen); anrop direkt mot dashboardens port (testerna,
# värdens skript) berörs inte, som för övriga skydd. Slås på igen med DASH_UTESTANGNING=ja.
UTESTANGNING_TILLATEN = (os.environ.get("DASH_UTESTANGNING") or ("nej" if _EXTERN else "ja")) == "ja"      # tom = ej satt
# Egen vy per besökare (sessioner.py): bara i den externa varianten, bara via Caddy och bara när DASH_SESSIONER=ja.
sessioner.PA = _EXTERN and (os.environ.get("DASH_SESSIONER") or "nej") == "ja"
app = FastAPI(title="SVADA PoC – kontrollrum (dashboard)", version=VERSION,
              docs_url=None if _EXTERN else "/docs",
              redoc_url=None if _EXTERN else "/redoc",
              openapi_url=None if _EXTERN else "/openapi.json")

# Kontrollrummets egna statiska filer (Leaflet för den valfria kartbakgrunden). Allt serveras härifrån:
# sidan laddar inget från ett CDN.
_STATISKT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statiskt")
if os.path.isdir(_STATISKT):
    app.mount("/statiskt", StaticFiles(directory=_STATISKT), name="statiskt")


def _fel_svar(fel, status, **extra):
    """Ett felsvar med den svenska texten (`fel`) och det lagrade meddelandet (`kod`, `p`) för andra språk."""
    m = fel.meddelande() if hasattr(fel, "meddelande") else meddelanden.fri(str(fel))
    return JSONResponse(status_code=status, content=dict({"fel": str(fel), "kod": m["kod"], "p": m["p"]}, **extra))


MAX_KROPP_BYTES = 64 * 1024          # kontrollrummets knappar skickar några tiotal byte; allt större är fel


class Kroppsfel(Exception):
    """En POST-kropp som inte går att använda. Bär felkod och HTTP-status; INGEN sidoeffekt får ske efter den."""

    def __init__(self, kod, status):
        super().__init__(kod)
        self.kod, self.status = kod, status


async def las_json_kropp(begaran, tillat_tom=False):
    """Läser en POST-kropp som ett JSON-OBJEKT eller kastar Kroppsfel (rättning efter Codex del d, fynd D2).

    Tidigare fångades alla undantag och ersattes med {} – då startade ett jobb trots att Caddy redan svarat 413,
    och en avbruten eller tom kropp förnyade felinjektionens frist. Nu gäller: för stor kropp -> 413, avbruten
    eller oläsbar -> 400, ogiltig JSON eller något annat än ett objekt -> 400, tom kropp -> {} bara om
    `tillat_tom`. Anroparen ska låta felet avsluta anropet innan någon åtgärd startas."""
    deklarerad = begaran.headers.get("content-length", "")
    if deklarerad.isdigit() and int(deklarerad) > MAX_KROPP_BYTES:
        raise Kroppsfel("fel.kropp_stor", 413)
    rad = bytearray()
    try:
        async for bit in begaran.stream():
            rad.extend(bit)
            if len(rad) > MAX_KROPP_BYTES:
                raise Kroppsfel("fel.kropp_stor", 413)
    except Kroppsfel:
        raise
    except Exception:                                    # noqa: BLE001 – klienten kopplade ned eller Caddy avbröt
        raise Kroppsfel("fel.kropp_avbruten", 400)
    if not rad.strip():
        if tillat_tom:
            return {}
        raise Kroppsfel("fel.kropp_ogiltig", 400)
    try:
        kropp = json.loads(bytes(rad))
    except (ValueError, RecursionError):
        raise Kroppsfel("fel.kropp_ogiltig", 400)
    if not isinstance(kropp, dict):
        raise Kroppsfel("fel.kropp_ogiltig", 400)
    return kropp


def _kroppsfel_svar(fel):
    return _fel_svar(jobbmodul.Jobbfel(fel.kod), fel.status)


@app.middleware("http")
async def skydda_skrivande_anrop(request, anrop_vidare):
    """Publik demo (anrop via Caddy): POST måste komma från sidans egen origin, och den som just körde ett jobb
    får vänta lite så att andra hinner före (skydd.py). Direkta anrop mot dashboardens port berörs inte."""
    if not (_EXTERN and request.method == "POST" and skydd.via_proxy(request)):
        return await anrop_vidare(request)
    if not skydd.samma_ursprung(request):
        return _fel_svar(jobbmodul.Jobbfel("fel.annat_ursprung"), 403)
    startar_jobb = request.url.path.startswith(("/api/atgard/", "/api/kov/"))
    if startar_jobb:
        sek = skydd.vanta_efter_jobb(request, jobbmodul.aktivt() is not None)
        if sek:
            return _fel_svar(jobbmodul.Jobbfel("fel.vanta", sek=sek), 429, vantaSek=sek)
    # Starten noteras vid antagningen (_starta_jobb), med jobbets id – inte här i efterhand (del a2, A2-04).
    return await anrop_vidare(request)


@app.middleware("http")
async def rensa_api_externt(request, anrop_vidare):
    """Externa varianten: ingen port eller internt värdnamn når besökaren i
    något API-svar eller i /health (felmeddelanden, jobblogg, auditlogg, FAIR,
    policyer).
    Ett enda ställe i stället för en rensning per slutpunkt. Rensas bara på
    vägen ut, så auditkedjans hashar och de lagrade jobbraderna är oförändrade."""
    svar = await anrop_vidare(request)
    sokvag = request.url.path
    if (DEMO_VARIANT != "extern"
            or not (sokvag.startswith("/api/") or sokvag == "/health")
            or "json" not in svar.headers.get("content-type", "")):
        return svar
    kropp = b"".join([d async for d in svar.body_iterator])
    text = rensa.neutrala_did(stegmodul.utan_intern_adress(kropp.decode("utf-8", "replace")))
    rubriker = {k: v for k, v in svar.headers.items()
                if k.lower() not in ("content-length", "content-type")}
    return Response(content=text, status_code=svar.status_code,
                    headers=rubriker, media_type="application/json")


# Varje åtgärd i jobb.py ska ha en knapptext i steg.py (och tvärtom).
_TACKNING = stegmodul.kontrollera_mot_jobb(jobbmodul.ATGARDER)
if _TACKNING:
    raise SystemExit("knapptäckning: " + "; ".join(_TACKNING))


# ---------------------------------------------------------------------------
# Hälsopollningen
# ---------------------------------------------------------------------------
def _sondera(komponent):
    try:
        svar = komponent["sond"]()
        detalj = "svarar"
        if isinstance(svar, dict):
            detalj = (svar.get("status") or svar.get("isSystemHealthy")
                      or svar.get("version") or "svarar")
        return {"status": "upp", "detalj": str(detalj), "tid": audit.nu()}
    except KallFel as fel:
        return {"status": "ned", "detalj": str(fel), "tid": audit.nu()}
    except Exception as fel:                             # noqa: BLE001
        return {"status": "ned", "detalj": "%s: %s" % (type(fel).__name__, fel),
                "tid": audit.nu()}


def _poll_halsa():
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        resultat = dict(zip([k["id"] for k in stegmodul.KOMPONENTER],
                            pool.map(_sondera, stegmodul.KOMPONENTER)))
    with HALSA_LAS:
        HALSA.update(resultat)


def _halsoloop():
    while True:
        try:
            _poll_halsa()
        except Exception as fel:                         # noqa: BLE001
            print("[halsa] pollningen misslyckades: %s" % fel, flush=True)
        time.sleep(HALSA_INTERVALL_S)


@app.on_event("startup")
def starta():
    print("[dashboard] startar – når komponenterna på %s (portkartan i .env)"
          % kallor.VARD, flush=True)
    threading.Thread(target=_halsoloop, name="halsa", daemon=True).start()
    if _EXTERN:
        if sessioner.PA:
            skydd.fel_lacka(True)       # en omstart av kontrollrummet kan ha lämnat ett eget felinjektionsläge kvar i FCF: städa första varvet
        threading.Thread(target=_stada_loop, name="stada", daemon=True).start()


STADA_INTERVALL_S = 10


def _stada_loop():
    """Publik demo: släpper in utestängda parter och slår av felinjektion när tiden gått (skydd.py)."""
    while True:
        time.sleep(STADA_INTERVALL_S)
        _stada_ett_varv()


def _stada_ett_varv():
    """Ett varv i städningen. Egen funktion så att den kan provköras med kontrollerad klocka (tests/skydd_integration.py).
    Varje åtgärd görs under störningens lås, och fristen prövas igen under låset: en gammal ögonblicksbild från
    forfallna() får inte släppa in en part som nyss stängts ute på nytt (A2-02). Varvet tar den tid källorna tar; en
    störning slås därför av först efter fristen + upp till STADA_INTERVALL_S + källornas svarstid (A2-08)."""
    try:
        inslapp, av = skydd.forfallna()
        # Varje åtgärd för sig, och bokföringen släpps först när åtgärden hos källan lyckats: ett fel
        # (identity hub nere) ska ge nytt försök nästa varv, inte en uteslutning som glöms bort.
        for m in inslapp:
            with skydd.STORNINGSLAS["ute:" + m]:
                if not skydd.utestangning_forfallen(m):
                    continue
                try:
                    kallor.svada_satt(m, "aterinsatt")
                except Exception as fel:                 # noqa: BLE001
                    print("[dashboard] städningen: kunde inte släppa in %s (nytt försök): %s" % (m, fel), flush=True)
                    continue
                skydd.insatt(m)
                audit.notera(3, "intyg", "INSATT", "audit.svada_automatisk", {"mottagare": m},
                             {"mottagare": m, "atgard": "aterinsatt", "automatiskt": True})
        if av:
            with skydd.STORNINGSLAS["fel"]:
                if skydd.felinjektion_forfallen():
                    try:
                        svar = kallor.fcf_nollstall_fel()
                    except Exception as fel:                 # noqa: BLE001
                        print("[dashboard] städningen: kunde inte slå av felinjektionen (nytt försök): %s" % fel, flush=True)
                    else:
                        skydd.felinjektion_pa(False)
                        audit.notera(4, "felinjektion", "AV", "audit.felinj_automatisk", {}, svar.get("lagen"))
        if skydd.fel_lacka_forfallen():              # en besökares eget felinjektionsläge kan ha lämnats kvar i FCF (jobb.py)
            with skydd.STORNINGSLAS["fel"]:
                try:
                    kallor.fcf_nollstall_fel()
                except Exception as fel:             # noqa: BLE001
                    print("[dashboard] städningen: kunde inte slå av ett kvarlämnat felinjektionsläge (nytt försök): %s" % fel, flush=True)
                else:
                    skydd.fel_lacka(False)
                    audit.notera(4, "felinjektion", "AV", "audit.felinj_automatisk", {}, None)
    except Exception as fel:                         # noqa: BLE001
        print("[dashboard] städningen misslyckades: %s" % fel, flush=True)


# ---------------------------------------------------------------------------
# Statussammanställning
# ---------------------------------------------------------------------------
def _komponentlista(sprak="sv"):
    with HALSA_LAS:
        lage = dict(HALSA)
    ut = []
    for k in stegmodul.KOMPONENTER:
        h = lage.get(k["id"]) or {"status": "okänd", "detalj": "inte pollad ännu",
                                  "tid": None}
        h = dict(h, detalj=stegmodul.utan_portar(h["detalj"]))
        ut.append({"id": k["id"],
                   "namn": k.get("namn_en") or k["namn"] if sprak == "en"
                   else k["namn"], "org": k["org"],
                   "steg": k["steg"],
                   "adress": "" if DEMO_VARIANT == "extern"
                   else kallor.url(k["port"]), **h})
    return ut


def _stegstatus(komponenter):
    per_steg = {}
    for k in komponenter:
        per_steg.setdefault(k["steg"], []).append(k["status"])
    ut = []
    for s in stegmodul.STEG:
        # Steg 6 har inga egna komponenter: dess status är plattformens (steg 5).
        statusar = per_steg.get(stegmodul._STATUS_FRAN.get(s["nr"], s["nr"]), [])
        if statusar and all(x == "upp" for x in statusar):
            status = "upp"
        elif statusar and any(x == "upp" for x in statusar):
            status = "delvis"
        else:
            status = "ned"
        ut.append({"nr": s["nr"], "titel": s["titel"], "org": s["org"],
                   "protokoll": s["protokoll"],
                   "beskrivning": s["beskrivning"], "status": status,
                   "komponenter": [k["id"] for k in komponenter
                                   if k["steg"] == stegmodul._STATUS_FRAN.get(s["nr"], s["nr"])],
                   "atgarder": s["atgarder"]})
    return ut


# ---------------------------------------------------------------------------
# Vyn
# ---------------------------------------------------------------------------
# Publik demo: de adresser en extern besökare når (via Caddy), med en nyckel
# som vy.py översätter till radnamn (pub_<nyckel>). Satta i
# .env på grenen publik-demo, tomma i originalet.
PUBLIKA_INGANGAR = [
    (namn, os.environ.get(var, "").rstrip("/"))
    for namn, var in (
        ("kontrollrum", "PUBLIK_URL_KONTROLLRUM"),
        ("brunnar", "PUBLIK_URL_BRUNNAR"),
        ("tidsserie", "PUBLIK_URL_TIDSSERIE"),
        ("cip", "PUBLIK_URL_CIP"),
    )
    if os.environ.get(var)
]


def _valt_sprak(begaran):
    """(språk, uttryckligt): ?lang=sv|en vinner över kakan svada-sprak."""
    fraga = begaran.query_params.get("lang")
    if fraga in vy.SPRAK:
        return fraga, True
    # Sidans egna anrop bär sidans språk (huvudet X-Svada-Lang). Annars följde svaren kakan, som en annan flik kan ha ändrat: en svensk
    # sida fick då engelska jobb och loggrader (externa webbläsartestet 2026-10-23, F7).
    huvud = begaran.headers.get("x-svada-lang")
    if huvud in vy.SPRAK:
        return huvud, False
    kaka = begaran.cookies.get("svada-sprak")
    return (kaka if kaka in vy.SPRAK else "sv"), False


@app.middleware("http")
async def oversatt_api(begaran: Request, call_next):
    """Engelskt språk: meddelanden från komponenterna (jobblogg, audit, fel) översätts vid gränsen.

    Se i18n.py. Sidans och stegens egna texter är redan tvåspråkiga, och exempelobjekten är data
    som visas som de är, så /api/steg* lämnas orörda.
    """
    svar = await call_next(begaran)
    sokvag = begaran.url.path
    if (not sokvag.startswith("/api/") or sokvag.startswith("/api/steg")
            or "application/json" not in svar.headers.get("content-type", "")):
        return svar
    if _valt_sprak(begaran)[0] != "en":
        return svar
    kropp = b"".join([bit async for bit in svar.body_iterator])
    try:
        data = json.loads(kropp)
    except ValueError:
        return Response(content=kropp, status_code=svar.status_code, media_type="application/json")
    return JSONResponse(status_code=svar.status_code,
                        content=i18n.oversatt_struktur(meddelanden.till_sprak(data, "en")))


@app.middleware("http")
async def sessionskaka(begaran: Request, anrop_vidare):
    """Egen vy per besökare (sessioner.py). Definieras SIST bland middlewarena, så att den är yttersta lagret och sessionen finns för alla
    inre lager och rutter. Bara via Caddy (X-Forwarded-For) och när sessioner är påslagna; annars lämnas anropet orört."""
    sokvag = begaran.url.path
    if not (sessioner.PA and skydd.via_proxy(begaran)) or sokvag.startswith("/statiskt/") or sokvag == "/health":
        return await anrop_vidare(begaran)
    sess, ny = sessioner.hamta_eller_skapa(begaran.cookies.get(sessioner.KAKNAMN))
    token = sessioner.satt(sess)
    try:
        svar = await anrop_vidare(begaran)
    finally:
        sessioner.aterstall(token)
    if ny:
        svar.set_cookie(sessioner.KAKNAMN, sess.id, max_age=sessioner.KAKA_MAXALDER_S, httponly=True, samesite="lax", path="/",
                        secure=begaran.headers.get("x-forwarded-proto") == "https")
    return svar


@app.get("/", response_class=HTMLResponse)
def index(begaran: Request):
    sprak, uttryckligt = _valt_sprak(begaran)
    svar = HTMLResponse(vy.sida(
        stegmodul.STEG, _komponentlista(sprak), kallor.PORTAR, kallor.VARD,
        0.5, PUBLIKA_INGANGAR, sprak=sprak,
        variant=DEMO_VARIANT, utestangning=UTESTANGNING_TILLATEN))
    if uttryckligt:
        svar.set_cookie("svada-sprak", sprak, max_age=31536000, samesite="lax")
    return svar


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Statistik: öppen sida med dagssummor, och en räknare för vitlistade händelser. Inga personuppgifter.
# ---------------------------------------------------------------------------
_HANDELSER = statmodul.Handelser()
_STAT_CACHE = {"t": 0.0, "data": None}
_STAT_LAS = threading.Lock()


def _statistikdata(ny=False):
    """Räknar om loggen och slår ihop med sparade dagar högst en gång i minuten (på begäran, `ny`, högst var femte sekund)."""
    with _STAT_LAS:
        nu = time.monotonic()
        if _STAT_CACHE["data"] is None or nu - _STAT_CACHE["t"] > (5 if ny else 60):
            _STAT_CACHE["data"] = statmodul.sammanstall(statmodul.uppdatera_historik(), _HANDELSER.alla())
            _STAT_CACHE["t"] = nu
        return _STAT_CACHE["data"]


@app.on_event("shutdown")
def _spola_handelser():
    _HANDELSER.spola()


@app.get("/nyheter", response_class=HTMLResponse)
def nyheter_sida(begaran: Request):
    sprak, _ = _valt_sprak(begaran)
    return HTMLResponse(nyheter.sida(sprak))


@app.get("/statistik", response_class=HTMLResponse)
def statistik_sida(begaran: Request):
    sprak, _ = _valt_sprak(begaran)
    return HTMLResponse(statistiksida.sida(_statistikdata(), sprak))


@app.get("/api/statistik")
def api_statistik(ny: int = 0):
    return _statistikdata(bool(ny))


@app.post("/api/handelse")
async def api_handelse(begaran: Request):
    """Sidan rapporterar en vitlistad händelse (steg öppnat, flik, åtgärd ...). Ingen identifierare, ingen IP och ingen fritext
    lagras: ett tal per dag och händelse. Robotar (curl, headless) räknas inte."""
    try:
        kropp = await las_json_kropp(begaran)
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    namn = kropp.get("h")
    if not statmodul.giltig_handelse(namn, jobbmodul.ATGARDER):
        return _fel_svar(jobbmodul.Jobbfel("fel.okand_handelse"), 400)
    # Testläge (kakan svada-test, satt via ?test=1): händelsen räknas inte, så att vår egen provning inte syns i statistiken.
    if not statmodul.ar_robot(begaran.headers.get("user-agent", "")) and begaran.cookies.get("svada-test") != "1":
        _HANDELSER.rakna(namn)
    return Response(status_code=204)


@app.get("/api/aterstallning")
def api_aterstallning():
    """Nästa nattliga återställning (UTC) och serverns nuvarande tid, för nedräkningen. Tomt svar lokalt (ingen nattlig återställning)."""
    svar = aterstall.som_svar(os.environ.get("DEMO_ATERSTALL_KL", ""), os.environ.get("TZ", "UTC"))
    return svar or {"nastaUtc": None}


@app.get("/health")
def health():
    komponenter = _komponentlista()
    uppe = sum(1 for k in komponenter if k["status"] == "upp")
    svar = {"status": "ok", "version": VERSION, "demoVersion": DEMO_VERSION,
            "startedAt": STARTAD.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vard": kallor.VARD,
            "komponenter": {"totalt": len(komponenter), "uppe": uppe,
                            "nere": len(komponenter) - uppe}}
    if DEMO_VARIANT == "extern":
        svar.pop("vard")                  # internt värdnamn hör inte hemma publikt
    return svar


_AVTAL_A = {}      # sessions-id (eller "" utan session) -> {"t", "v", "pagar"}: värdet räknas fram per besökare
_AVTAL_A_LAS = threading.Lock()


def _avtal_a_gallande():
    """Gäller något avtal om A just nu? Läses ur stadens avtalsregister högst var 2:a sekund (statusrundan pollas av varje öppen flik).
    None = okänt (registret svarar inte). Låset hålls aldrig under anropet: en tråd uppdaterar, övriga får det senaste värdet, så en
    hängande ingest inte kan binda alla trådar."""
    sess = sessioner.aktuell()
    nyckel = sess.id if sess else ""
    with _AVTAL_A_LAS:
        if len(_AVTAL_A) > 2 * sessioner.MAX_SESSIONER:
            _AVTAL_A.clear()
        post = _AVTAL_A.setdefault(nyckel, {"t": 0.0, "v": None, "pagar": False})
        uppdatera = time.monotonic() - post["t"] > 2 and not post["pagar"]
        if uppdatera:
            post["pagar"] = True
    if uppdatera:
        try:
            v = analys.senaste_gallande_a_avtal()[0] is not None
        except KallFel:
            v = None
        with _AVTAL_A_LAS:
            post.update(v=v, t=time.monotonic(), pagar=False)
    return post["v"]


@app.get("/api/status")
def api_status(lang: str = "sv"):
    komponenter = _komponentlista(lang)
    uppe = sum(1 for k in komponenter if k["status"] == "upp")
    return {"tid": audit.nu(), "komponenter": komponenter,
            "steg": _stegstatus(komponenter),
            "sammanfattning": {"totalt": len(komponenter), "uppe": uppe,
                               "nere": len(komponenter) - uppe},
            "demoVersion": DEMO_VERSION,
            "jobbAktivt": jobbmodul.aktivt(),
            "nasta": jobbmodul.nasta_atgard(),      # åtgärden som är rimlig att köra härnäst (markeras på knappen)
            # F1: sidan läser om steg 6 när avtalet om A inte längre gäller (annars låg positionerna kvar tills besökaren uppdaterade)
            "avtalA": {"gallande": _avtal_a_gallande()}}


@app.get("/api/steg")
def api_steg(lang: str = "sv"):
    """Alla stegens detaljsiffror. Hämtas parallellt – annars tar det evigheter."""
    nummer = [s["nr"] for s in stegmodul.STEG]
    ctx = contextvars.copy_context()                    # tas HÄR (anropets tråd): besökarens session följer med in i trådarna
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        detaljer = dict(zip(nummer, pool.map(
            lambda n: ctx.copy().run(stegmodul.detaljer, n, lang), nummer)))
    return {"steg": [{"nr": n, "detaljer": detaljer[n]} for n in nummer]}


@app.get("/api/steg/{nr}")
def api_ett_steg(nr: int, lang: str = "sv"):
    return {"nr": nr, "detaljer": stegmodul.detaljer(nr, lang)}


@app.get("/api/steg/5/ursprung")
def api_steg5_ursprung(lang: str = "sv"):
    """Värdet i CIP:en (distribution B) och avtalet dess id pekar på."""
    try:
        return stegmodul.ursprung_b(extern=DEMO_VARIANT == "extern", sprak="en" if lang == "en" else "sv")
    except KallFel as fel:
        # Ett normalt läge (senaste leveransen är inte B): 200 utan värde, så att sidan behåller sina
        # statiska exempel utan att webbläsarens konsol får ett fel.
        return {"tillgangligt": False}


@app.get("/api/steg/{nr}/exempel")
def api_steg_exempel(nr: int, lang: str = "sv"):
    """Exempelobjektet som passerar steget (Nivå 1). Bara det kontrollrummet
    redan lagligt hämtar – aldrig dataproduktens nyttolast (steg.py)."""
    return {"nr": nr, **stegmodul.exempel(nr, lang)}


@app.get("/api/folj")
def api_folj(lang: str = "sv"):
    """Följ ett värde genom kedjan (Nivå 2): samma brunn led för led, med
    avtals-id:t som tråd genom kontrakt, ingest-kvitto och proveniens."""
    return stegmodul.folj_vardet(lang)


def _starta_jobb(begaran, atgard, argument):
    """Antagning av ett jobb. Rättvisepausen prövas HÄR, efter att kroppen lästs, och inte bara i middleware innan
    kroppen kommit fram (del a2, A2-04: annars kunde ett anrop vänta ut föregående jobb med kroppen öppen och starta inom
    pausen). Starten noteras med jobbets id, så att ett sent svar inte skriver över en nyare start."""
    proxy = _EXTERN and skydd.via_proxy(begaran)
    if proxy:
        sek = skydd.vanta_efter_jobb(begaran, jobbmodul.aktivt() is not None)
        if sek:
            return _fel_svar(jobbmodul.Jobbfel("fel.vanta", sek=sek), 429, vantaSek=sek)
    try:
        jobb = jobbmodul.starta(atgard, argument)
    except jobbmodul.Upptaget as fel:
        return _fel_svar(fel, 409, aktivt=jobbmodul.aktivt())
    except jobbmodul.Jobbfel as fel:
        return _fel_svar(fel, 400)
    if proxy:
        skydd.noterat_jobbstart(begaran, jobb["id"])
    return jobb


@app.post("/api/atgard/{atgard}")
async def api_atgard(atgard: str, begaran: Request):
    try:
        argument = await las_json_kropp(begaran, tillat_tom=True)
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    return _starta_jobb(begaran, atgard, argument)


@app.get("/api/jobb")
def api_jobb():
    return {"aktivt": jobbmodul.aktivt(), "jobb": jobbmodul.lista()}


@app.get("/api/jobb/{jid}")
def api_ett_jobb(jid: int):
    post = jobbmodul.hamta(jid)
    if post is None:
        return _fel_svar(jobbmodul.Jobbfel("fel.okant_jobb"), 404)
    return post


@app.get("/api/audit")
def api_audit():
    return audit.logg()


@app.get("/api/audit/kedja")
def api_audit_kedja():
    """Full kontroll av hash-kedjan (G10, "enkla varianten") - samma
    resultat som faltet "kedja" i /api/audit, utan att behova hamta hela
    auditloggen for att se det."""
    return audit.hash_kedja_kontrollera()


# ENDAST for tests/verify_hash_kedja.sh: en avsiktligt destruktiv
# endpoint som bevisar att hash_kedja_kontrollera() slar larm vid
# manipulation. Existerar bara om DASH_AUDIT_KEDJA_TESTLAGE=1 ar satt i
# miljon - i alla andra fall (all riktig drift) ar detta
# 404, precis som om koden
# inte fanns. Se audit.py:s kedja_mixtra_for_test() for sjalva
# mixtrandet.
if os.environ.get("DASH_AUDIT_KEDJA_TESTLAGE") == "1":
    @app.post("/api/audit/kedja/test-mixtra/{seq}")
    def api_audit_kedja_test_mixtra(seq: int):
        try:
            return audit.kedja_mixtra_for_test(seq)
        except KallFel as f:
            return JSONResponse(status_code=400, content={"fel": str(f)})


@app.get("/api/analys")
def api_analys(lage: str = "b", topp: int = 10):
    """Steg 6: inspektionsprioritering. Läge B är öppet; läge A kräver ett gällande avtal."""
    try:
        return analys.prioritering(lage, topp)
    except KallFel as fel:
        return _fel_svar(fel, 502)


@app.get("/api/analys/brunn")
def api_analys_brunn():
    """Steg 6: demobrunnen i B och A sida vid sida (A bara med ett gällande avtal)."""
    try:
        return analys.samma_brunn()
    except KallFel as fel:
        return _fel_svar(fel, 502)


@app.get("/api/kov")
def api_kov():
    """Providerns kö av A-förhandlingar. Hård regel 7: gaten sitter HÄR."""
    try:
        kon = kedjan.kov_kon()
    except KallFel as fel:
        return _fel_svar(fel, 502)
    sess = sessioner.aktuell()
    if sess is not None:           # besökaren ser bara sina egna förhandlingar i KoV-rutan (correlationId = stadens förhandlings-id)
        kon = [f for f in kon if f.get("correlationId") in sess.forhandlingar]
    return {"count": len(kon),
            "vantande": [f for f in kon if f.get("kovBeslut") == "VANTANDE"],
            "forhandlingar": kon,
            # Externt är det bara sökvägen hos providern (inget värdnamn eller port); sidan visar den inte i den externa varianten.
            "api": "/management/kov/forhandlingar" if DEMO_VARIANT == "extern"
            else kallor.url("edc_provider_mgmt",
                            "/management/kov/forhandlingar")}


@app.post("/api/kov/{forhandlings_id}/{beslut}")
async def api_kov_beslut(forhandlings_id: str, beslut: str, begaran: Request):
    # Kroppen läses och godkänns före åtgärden även här (del a2, A2-01); knapparna skickar ingen eller en tom kropp.
    try:
        await las_json_kropp(begaran, tillat_tom=True)
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    atgard = {"godkann": "kov-godkann", "avsla": "kov-avsla"}.get(beslut)
    if not atgard:
        return _fel_svar(jobbmodul.Jobbfel("fel.beslut"), 400)
    try:         # servern vägrar beslut på någon annans förhandling, oavsett vad sidan visar (kallar providern: i trådpoolen)
        if not await run_in_threadpool(jobbmodul.agd_forhandling, sessioner.aktuell(), forhandlings_id):
            return _fel_svar(jobbmodul.Jobbfel("fel.inte_din_forhandling"), 403)
    except KallFel as fel:
        return _fel_svar(fel, 502)
    return _starta_jobb(begaran, atgard, {"id": forhandlings_id})


@app.get("/api/skydd")
def api_skydd(begaran: Request):
    """Tickande tider i den publika demon (automatisk återinsättning, felinjektionens slut, kön). Tomt lokalt."""
    if not _EXTERN:
        return {"utestangningS": {}, "felinjektionS": None, "pausS": 0,
                "regler": {"utestangningS": 0, "felinjektionS": 0, "pausS": 0}}
    svar = skydd.kvar_sekunder(begaran, jobbmodul.aktivt() is not None)
    if not UTESTANGNING_TILLATEN:         # ingen utestängning kan ske: ingen nedräkning och ingen regel om den (förklaringsdialogen nämner den inte)
        svar = dict(svar, utestangningS={}, regler=dict(svar.get("regler") or {}, utestangningS=0))
    return svar


@app.get("/api/svada/status")
def api_svada_status():
    """Statuslistan hos Svadas utfärdare (samordningsrollen): vilka intyg som är återkallade."""
    try:
        # Bara det vyn behöver: mottagare, typ och om intyget är återkallat. Inte intygets subjekt (en DID med internt värdnamn).
        return {"poster": [{k: v for k, v in p.items() if k != "subjekt"} for p in kallor.svada_status()]}
    except KallFel as fel:
        return _fel_svar(fel, 502)


@app.post("/api/svada/{mottagare}/{atgard}")
async def api_svada_satt(mottagare: str, atgard: str, begaran: Request):
    """Samordnaren stänger ute (aterkalla) eller släpper in (aterinsatt) en deltagare."""
    try:
        await las_json_kropp(begaran, tillat_tom=True)      # A2-01: ingen åtgärd på en trasig eller avbruten kropp
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    if mottagare not in ("dhi", "stad") or atgard not in ("aterkalla", "aterinsatt"):
        return _fel_svar(jobbmodul.Jobbfel("fel.svada_argument"), 400)
    if not UTESTANGNING_TILLATEN and skydd.via_proxy(begaran):
        return _fel_svar(jobbmodul.Jobbfel("fel.utestangning_avstangd"), 403)
    # Källanropet blockerar (urllib): i trådpoolen, inte i händelseloopen (A2-05).
    return await run_in_threadpool(_svada_satt_synk, mottagare, atgard, _EXTERN and skydd.via_proxy(begaran))


def _svada_satt_synk(mottagare, atgard, proxy):
    """Kontroll, källanrop och bokföring under störningens lås (A2-02): en återinsättning och en ny uteslutning av
    samma part kan inte korsa varandra, och två samtidiga uteslutningar når inte källan två gånger."""
    with skydd.STORNINGSLAS["ute:" + mottagare]:
        if proxy and atgard == "aterkalla":
            # Absolut frist och återhämtningsperiod (skydd.py): en uteslutning som pågår förnyas inte av ett nytt
            # anrop (idempotent, ingen ny auditpost), och en nyss avslutad får inte slås på igen på en gång.
            if mottagare in skydd.UTESTANGDA:
                return {"redan": True, "mottagare": mottagare, "atgard": atgard}
            kvar = skydd.avkylning_kvar("ute:" + mottagare)
            if kvar:
                return _fel_svar(jobbmodul.Jobbfel("fel.avkylning_ute", sek=kvar, part=[mottagare]), 429, vantaSek=kvar)
        try:
            svar = kallor.svada_satt(mottagare, atgard)
        except KallFel as fel:
            if fel.status is None and atgard == "aterkalla":
                # Tvetydigt (timeout eller avbrott efter att begäran skickats): utestängningen KAN ha gått igenom.
                # Bokför den, så att den automatiska återinsättningen finns kvar; en återinsättning av en redan insläppt
                # part är ofarlig. Vid en misslyckad återinsättning står bokföringen kvar och städningen försöker igen.
                skydd.utestangd(mottagare)
            return _fel_svar(fel, 502)
        # Åtgärden är en händelse i kedjan och ska finnas kvar i auditloggen (och dess hashkedja).
        (skydd.utestangd if atgard == "aterkalla" else skydd.insatt)(mottagare)
        audit.notera(3, "intyg", "UTESTANGD" if atgard == "aterkalla" else "INSATT",
                     "audit.svada_aterkallat" if atgard == "aterkalla" else "audit.svada_aterinsatt",
                     {"mottagare": mottagare}, {"mottagare": mottagare, "atgard": atgard})
        return svar


@app.get("/api/svada/prov")
def api_svada_prov():
    """Prövar om staden når DHI över DSP just nu: en katalogförfrågan. 401 = utesluten."""
    try:
        kallor.dsp_katalog()
        return {"ok": True}
    except KallFel as fel:
        m = fel.meddelande()
        # nekad = DHI nekade staden över DSP (strukturerat, A2-06); sidan ska inte gissa ur feltexten.
        return {"ok": False, "nekad": jobbmodul.dsp_nekad(fel), "fel": str(fel)[:300], "kod": m["kod"], "p": m["p"]}


@app.get("/api/avtal")
def api_avtal():
    """Stadens avtalsregister: avtal, status (GALLANDE/HAVT/OKAND), ODRL-sammanfattning."""
    try:
        reg = kallor.avtalsregister()
        sess = sessioner.aktuell()
        if sess is not None:       # bara besökarens egna avtal
            reg = dict(reg, avtal=[a for a in reg.get("avtal", []) if a.get("id") in sess.avtal])
        return reg
    except KallFel as fel:
        return _fel_svar(fel, 502)


def _avtalssida(a, en):
    """Avtalets löstbara sida: vad avtalet innebär och vilken status det har."""
    def t(sv, eng):
        return eng if en else sv
    e = html.escape
    status = {"GALLANDE": t("GÄLLER", "VALID"), "HAVT": t("HÄVT", "REVOKED"),
              "UTGANGET": t("UTGÅNGET", "EXPIRED"),
              "OKAND": t("OKÄND", "UNKNOWN")}.get(a.get("status"), "?")
    regler = a.get("regler") or {}

    def lista(namn, poster):
        poster = "".join("<li>%s</li>" % e(p) for p in poster) or \
            "<li>%s</li>" % t("inga", "none")
        return "<h3>%s</h3><ul>%s</ul>" % (e(namn), poster)
    def klartext(regler, en):
        """Löptext i vyns språk om vad villkoren betyder (de formella villkoren ovan är engelska)."""
        rader = []
        for typ, nyckel in (("prohibition", "forbjudet"), ("obligation", "plikter")):
            for post in regler.get(nyckel, []):
                # en duty på en permission (t.ex. "attribute (duty on use)") förklaras med duty-texten
                dtyp = "duty" if "(duty on " in post else typ
                text = (stegmodul._ODRL_TEXT.get((dtyp, post.split(" ")[0])) or {}).get("en" if en else "sv")
                if text:
                    rader.append("<li><code>%s</code>: %s</li>" % (e(post.split(" ")[0]), e(text)))
        if not rader:
            return ""
        return "<h3>%s</h3><ul>%s</ul>" % (e(t("I klartext", "In plain language")), "".join(rader))
    hav = a.get("havning")
    havtext = ""
    if hav:
        orsaker = {"EXPLICIT": t("KoV hävde direkt", "KoV revoked it directly"),
                   "AVSLAG": t("ett avslag på en ny begäran", "a rejection of a new request")}
        delar = [str(hav.get("tid") or "")[:19].replace("T", " ") + " UTC",
                 t("orsak", "reason") + ": " + orsaker.get(str(hav.get("orsak")), str(hav.get("orsak")))]
        if hav.get("av"):
            delar.append(t("av", "by") + ": " + str(hav.get("av")))
        havtext = "<p><b>%s</b> %s</p>" % (t("Hävt", "Revoked"), e(" · ".join(delar)))

    def tid(epok):
        """Epoksekunder -> läsbar UTC-tid (annars värdet som det är)."""
        try:
            return dt.datetime.fromtimestamp(float(epok), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (TypeError, ValueError, OverflowError, OSError):
            return epok
    rader = "".join("<tr><th scope=\"row\">%s</th><td><code>%s</code></td></tr>"
                    % (e(k), e(str(v if v is not None else "–")))
                    for k, v in (
        (t("Stadens avtals-id", "The city's agreement id"), a.get("id")),
        (t("DHI:s avtals-id", "DHI's agreement id"), a.get("dhiAvtalId")),
        (t("Stadens förhandlings-id", "The city's negotiation id"),
         a.get("forhandlingId")),
        (t("Tillgång", "Asset"), a.get("assetId")),
        (t("Distribution", "Distribution"), a.get("distribution")),
        (t("Part (mottagare)", "Party (recipient)"), a.get("konsument")),
        (t("Provider", "Provider"), a.get("provider")),
        (t("Avtalets adress", "The agreement's address"), "/avtal/%s" % a.get("id") if a.get("id") else None),
        (t("Signerat", "Signed"), tid(a.get("signerat"))),
        (t("Giltigt till", "Valid until"), tid(a.get("giltigTill")))))
    sida = """<!doctype html><html lang="%s"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title><style>
:root{color-scheme:light}
body{background:#fff;color:#1d1d1d;font: 16px/1.5 system-ui,sans-serif;max-width: 46rem;margin: 0 auto;padding: 1rem 16px 3rem}
th{text-align:left;padding-right: 1rem;vertical-align:top;font-weight: 600}
code,pre{overflow-wrap:anywhere;white-space:pre-wrap}
.status{display:inline-block;border: 2px solid currentColor;border-radius: 6px;padding:.1rem .6rem;font-weight: 700}
</style></head><body>
<p><a href="/#suveranitet">&larr; %s</a></p>
<h1>%s <span class="status">%s</span></h1>
<p>%s</p>%s
<table>%s</table>
%s%s%s
<h3>%s</h3><pre>%s</pre>
</body></html>""" % (
        "en" if en else "sv", t("Avtal", "Agreement"),
        t("Kontrollrummet", "Control room"),
        t("Avtal", "Agreement"), status,
        e(t("Ett avtal gäller tills det hävs eller löper ut, inte bara för en datahämtning. "
            "Statusen synkas från DHI:s connector ungefär varje sekund "
            "(PoC-förenkling).",
            "An agreement is valid until it is revoked or expires, not just for one data "
            "fetch. The status is synced from DHI's connector about every "
            "second (PoC simplification).")), havtext, rader,
        # Avtalsvillkoren (raderna) är formell text: engelska i båda vyerna. Rubrikerna och förklaringen under är på vyns språk (F9).
        lista(t("Tillåtet (permitted)", "Permitted"), regler.get("tillatet", [])),
        lista(t("Förbjudet (prohibited)", "Prohibited"), regler.get("forbjudet", [])),
        lista(t("Skyldigheter (obligations)", "Obligations"), regler.get("plikter", [])) + klartext(regler, en),
        t("ODRL-ögonblicksbild (hela policyn)", "ODRL snapshot (full policy)"),
        e(json.dumps(a.get("policy"), ensure_ascii=False, indent=2)))
    return sida


@app.exception_handler(StarletteHTTPException)
async def http_fel(begaran: Request, fel: StarletteHTTPException):
    """En okänd adress ger en vanlig 404-sida för en webbläsare (på besökarens språk, med väg tillbaka) och JSON för API-anrop."""
    if fel.status_code == 404 and "text/html" in begaran.headers.get("accept", "") and not begaran.url.path.startswith("/api/"):
        sprak, _ = _valt_sprak(begaran)
        en = sprak == "en"
        return HTMLResponse('<!doctype html><html lang="%s"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                            '<title>%s</title><body style="font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:12vh auto;padding:0 16px">'
                            '<h1>%s</h1><p>%s</p><p><a href="/?lang=%s">%s</a></p></body></html>'
                            % (sprak, "Page not found" if en else "Sidan finns inte", "Page not found" if en else "Sidan finns inte",
                               "There is nothing at this address." if en else "Det finns inget på den här adressen.", sprak,
                               "Back to the control room" if en else "Tillbaka till kontrollrummet"), status_code=404)
    return JSONResponse({"detail": fel.detail}, status_code=fel.status_code, headers=getattr(fel, "headers", None))


# Ett avtals-id är ett UUID. Allt annat (specialtecken, tomt, mycket långt) är en okänd adress och ska aldrig nå mottagningen.
_AVTALS_ID = re.compile(r"^[0-9A-Za-z-]{1,64}$")


@app.get("/avtal/{avtals_id:path}")      # även id med snedstreck ger avtalssidans 404, inte rå JSON (L8)
def avtalssida(avtals_id: str, lang: str = "sv"):
    try:
        if not _AVTALS_ID.match(avtals_id):
            raise KallFel("ogiltigt avtals-id")
        a = kallor.anrop(kallor.url("ingest", "/avtal/%s" % avtals_id))
    except KallFel:
        # På besökarens språk och med väg tillbaka (gränssnittstestet L8 och del e E13: tidigare bara svenska, ingen länk).
        en = lang == "en"
        return HTMLResponse('<!doctype html><html lang="%s"><meta charset="utf-8"><title>%s</title><p>%s</p><p><a href="/%s">%s</a></p>'
                            % ("en" if en else "sv", "Agreement" if en else "Avtal",
                               "The agreement was not found." if en else "Avtalet hittades inte.",
                               "?lang=en" if en else "", "Back to the control room" if en else "Tillbaka till kontrollrummet"),
                            status_code=404)
    if DEMO_VARIANT == "extern":
        # Rensa bara DATAT (id, parter, policy), inte sidmallen: den bär
        # CSS som regeln för portnummer annars skulle skada.
        a = json.loads(rensa.neutrala_did(stegmodul.utan_intern_adress(
            json.dumps(a, ensure_ascii=False))))
    return HTMLResponse(_avtalssida(a, lang == "en"))


@app.post("/api/kov/avtal/{dhi_avtals_id}/hav")
async def api_kov_hav(dhi_avtals_id: str, begaran: Request):
    """KoV häver ett avtal (PoC-mekanism, MEDVETEN FÖRENKLING)."""
    try:
        await las_json_kropp(begaran, tillat_tom=True)      # A2-01
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    try:
        if not await run_in_threadpool(jobbmodul.agd_dhi_avtal, sessioner.aktuell(), dhi_avtals_id):
            return _fel_svar(jobbmodul.Jobbfel("fel.inte_ditt_avtal"), 403)
    except KallFel as fel:
        return _fel_svar(fel, 502)
    return _starta_jobb(begaran, "kov-hav", {"id": dhi_avtals_id})


@app.get("/api/odrl-villkor")
def api_odrl_villkor(lang: str = "sv"):
    """Villkoren för B och A live ur DSP-katalogen, med klartext (steg 5)."""
    try:
        return stegmodul.odrl_villkor(lang, extern=DEMO_VARIANT == "extern")
    except KallFel as fel:
        return _fel_svar(fel, 502)


@app.get("/api/odrl/a")
def api_odrl_a():
    """Policyn som gäller för Distribution A – READ ONLY."""
    try:
        return kedjan.villkor_a()
    except KallFel as fel:
        return _fel_svar(fel, 502)


def _egen_fel_svar(sprak):
    """Besökarens eget felinjektionsläge (sessioner.py): inget delat läge och inga timers. FCF läses bara för lägesbeskrivningarna."""
    s = sessioner.aktuell()
    lagen = {k: bool((s.fel_lagen or {}).get(k)) for k in _FELLAGEN}
    svar = {"aktiv": any(lagen.values()), "lagen": lagen, "egen": True}
    try:
        beskr = kallor.fcf_felinjektion()
        for lage, mm in (beskr.get("beskrivningKod") or {}).items():
            svar.setdefault("beskrivning", {})[lage] = meddelanden.visa(mm["kod"], mm.get("parametrar") or {}, sprak)
    except KallFel:
        pass
    return svar


@app.get("/api/felinjektion")
def api_felinjektion(begaran: Request):
    if sessioner.aktuell() is not None:
        return _egen_fel_svar(_valt_sprak(begaran)[0])
    try:
        svar = kallor.fcf_felinjektion()
        # Lägesbeskrivningarna kommer från fcf-sim som kod + parametrar; texten skapas på läsarens språk.
        sprak = _valt_sprak(begaran)[0]
        for lage, m in (svar.get("beskrivningKod") or {}).items():
            svar.setdefault("beskrivning", {})[lage] = meddelanden.visa(m["kod"], m.get("parametrar") or {}, sprak)
        return svar
    except KallFel as fel:
        return _fel_svar(fel, 502)


_FELLAGEN = ("schemadrift", "saknade_parametrar", "gis_i_b")


@app.post("/api/felinjektion")
async def api_satt_felinjektion(begaran: Request):
    try:
        kropp = await las_json_kropp(begaran)
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    if not kropp or any(k not in _FELLAGEN or not isinstance(v, bool) for k, v in kropp.items()):
        return _fel_svar(jobbmodul.Jobbfel("fel.felinj_argument"), 400)
    s = sessioner.aktuell()
    if s is not None:
        # Eget läge: sparas i besökarens session och slås på i FCF bara medan hennes leverans körs (jobb.py, _egen_felinjektion).
        s.fel_lagen.update(kropp)
        return await run_in_threadpool(_egen_fel_svar, _valt_sprak(begaran)[0])
    # Källanropet blockerar: i trådpoolen, inte i händelseloopen (A2-05: en långsam FCF frös hela kontrollrummet).
    return await run_in_threadpool(_satt_fel_synk, kropp, _EXTERN and skydd.via_proxy(begaran))


def _satt_fel_synk(kropp, proxy):
    with skydd.STORNINGSLAS["fel"]:                          # A2-02: samma lås som nollställning och städning
        # Återhämtningsperiod: en ny felinjektion får inte slås på direkt efter att den upphört (skydd.py).
        if proxy and any(kropp.values()):
            kvar = skydd.avkylning_kvar("fel")
            if kvar:
                return _fel_svar(jobbmodul.Jobbfel("fel.avkylning", sek=kvar), 429, vantaSek=kvar)
        try:
            svar = kallor.fcf_satt_fel(kropp)
        except KallFel as fel:
            if fel.status is None and any(kropp.values()):
                skydd.felinjektion_pa(True)                 # tvetydigt: kan ha slagits på; städningen slår då av den
            return _fel_svar(fel, 502)
        aktiva = [k for k, v in (svar.get("lagen") or {}).items() if v]
        skydd.felinjektion_pa(bool(aktiva))
        audit.notera(4, "felinjektion", "PÅ" if aktiva else "AV",
                     "audit.felinj_pa" if aktiva else "audit.felinj_av", {"lagen": aktiva},
                     svar.get("lagen"))
        return svar


@app.post("/api/felinjektion/reset")
async def api_nollstall_felinjektion(begaran: Request):
    try:
        await las_json_kropp(begaran, tillat_tom=True)      # A2-01
    except Kroppsfel as fel:
        return _kroppsfel_svar(fel)
    s = sessioner.aktuell()
    if s is not None:
        s.fel_lagen.clear()
        return await run_in_threadpool(_egen_fel_svar, _valt_sprak(begaran)[0])
    return await run_in_threadpool(_nollstall_fel_synk)


def _nollstall_fel_synk():
    with skydd.STORNINGSLAS["fel"]:
        try:
            svar = kallor.fcf_nollstall_fel()
        except KallFel as fel:
            return _fel_svar(fel, 502)                        # bokföringen står kvar: städningen slår av den
        skydd.felinjektion_pa(False)
        audit.notera(4, "felinjektion", "AV", "audit.felinj_nollstalld", {}, svar.get("lagen"))
        return svar
