#!/usr/bin/env python3
"""publik-vy – Göteborgs Stads publika representation av Distribution B.

Plats i kedjan:

    ingest-service --> orion-stad (CIP) --TRoE--> mintaka
                                                    |
                                        attributallowlist + tidsfönster
                                                    v
                                     PUBLIK-VY  (HTML för människa,
                                                 JSON för maskin)
                                                    ^
                                     dcat:accessURL |  portal/skördare
                                                       dereferenserar aldrig,
                                                       men en MÄNNISKA klickar

VARFÖR TJÄNSTEN FINNS (gapanalys G9)
------------------------------------
`dcat:accessURL` för Distribution B pekade tidigare rakt på Mintakas
NGSI-LD Temporal API. Den adressen fungerar för en maskin men svarar
**HTTP 400** på en webbläsares `Accept: text/html,...` – Mintaka accepterar
bara `application/json` och `application/ld+json`. En åtkomstadress som inte
går att följa gör den öppna distributionen otillgänglig i praktiken, och
DCAT-AP:s modell är EN distribution per representation. Den här tjänsten är
`text/html`-representationen; Mintaka är fortsatt `application/json`-
representationen och har en egen distribution i katalogen.

TVÅ HÅRDA REGLER STYR IMPLEMENTATIONEN
--------------------------------------
1. **Hård regel 8 / invariant 3.** Vyn är en STADENS endpoint. Den läser
   stadens eget Mintaka och lagrar ingenting. Ingen kopia, ingen volym.
2. **Invariant 2 (integritet i klassningen).** `OPPNA_ATTRIBUT` är en
   ALLOWLIST, inte en denylist. Endast dessa attribut efterfrågas hos
   Mintaka, vilket gör det omöjligt för vyn att råka publicera brunnens
   `location` – även om entiteten i CIP bär den efter en A-leverans.
   Testfall 5.7 i tests/verify_ap5.sh kontrollerar det.

API:

  GET  /                      – landningssida (HTML)
  GET  /health                – status (JSON)
  GET  /brunnar               – senaste dygnet per brunn (HTML eller JSON)
  GET  /brunnar/{id}          – tidsserie för en brunn (HTML eller JSON)

Innehållsförhandling: `Accept: application/json` (eller `?format=json`) ger
JSON, allt annat ger HTML. `Accept: */*` – det curl och de flesta bibliotek
skickar – ger HTML med status 200, så att nåbarhetskontroller passerar.
"""

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import vy

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Konfiguration (env – portar och adresser kommer ur .env, hård regel 4/5)
# ---------------------------------------------------------------------------
MINTAKA_URL = os.environ.get("MINTAKA_URL", "http://mintaka:8080").rstrip("/")
# Adressen som visas för användaren (värdens port, inte containernamnet).
MINTAKA_PUBLIK = os.environ.get(
    "MINTAKA_PUBLIK_URL", "http://localhost:8083").rstrip("/")
EGEN_PUBLIK = os.environ.get(
    "PUBLIK_VY_PUBLIK_URL", "http://localhost:8085").rstrip("/")
KATALOG_URL = ""      # Svada-mini: ingen katalog (portalerna ingår inte)
# Tidsfönstrets start. Mintaka KRÄVER timerel+timeAt – utan dem svarar den
# "Invalid time relation." (samma defekt som G9:s andra halva).
FONSTER_FRAN = os.environ.get("PUBLIK_VY_TIMEAT", "2020-01-01T00:00:00Z")
TIMEOUT_S = int(os.environ.get("PUBLIK_VY_TIMEOUT_S", "20"))
MAX_BRUNNAR = int(os.environ.get("PUBLIK_VY_MAX_BRUNNAR", "200"))
# Antal tidpunkter per brunn i detaljvyn. GOTCHA (verifierat 2026-07-24):
# UTAN `lastN` sidindelar Mintaka svaret och kapar instanslistan – ett
# kollektivt anrop över 91 brunnar gav då 2026-07-05 som "senaste" trots att
# historiken går till 2026-09-15. Med `lastN` blir svaret deterministiskt.
MAX_PUNKTER = int(os.environ.get("PUBLIK_VY_MAX_PUNKTER", "100"))

ENTITETSTYP = "SewerOverflowModelB"      # bara den öppna distributionen; A ligger på en egen entitetstyp

# ALLOWLIST (invariant 2). Brunnens `location`/`sourceSrs` finns MEDVETET
# inte här och kan därför aldrig hämtas av den här tjänsten.
OPPNA_ATTRIBUT = (
    "overflowVolumeM3",
    "overflowDurationMin",
    "overflowPeakM3S",
    "inflowMeanM3S",
    "inflowPeakM3S",
    "inflowVolumeM3",
    "waterLevelMaxM",
)
# Attribut vyn visar i listan (i den ordningen).
LISTKOLUMNER = ("overflowVolumeM3", "overflowDurationMin")

# Ingen interaktiv API-dokumentation (/docs, /redoc, /openapi.json): vyn är publik, och dokumentationen
# beskriver bara interna detaljer (rättning efter Codex del d, fynd D5).
app = FastAPI(title="publik-vy – stadens öppna vy av Distribution B "
                    "(SVADA PoC)",
              version=VERSION, docs_url=None, redoc_url=None, openapi_url=None)


PREFIX = "urn:ngsi-ld:%s:" % ENTITETSTYP
ID_MONSTER = re.compile(r"[A-Za-z0-9_.-]{1,80}")      # används med fullmatch: ett avslutande radslut ska inte godkännas


class BrunnSaknas(Exception):
    """Brunnen finns inte (okänt eller ogiltigt id, eller Mintaka svarade 404/400): ett normalt svar, inget serverfel."""


class MintakaFel(Exception):
    """Mintaka svarade inte som väntat. Bär en kod och parametrar (språkoberoende); texten skapas på besökarens språk
    och innehåller aldrig Mintakas svarskropp eller undantagstext (de kan bära interna adresser)."""

    TEXTER = {
        "http": {"sv": "Mintaka svarade med felkod {status}.", "en": "Mintaka responded with error code {status}."},
        "nar_inte": {"sv": "Mintaka gick inte att nå.", "en": "Mintaka could not be reached."},
    }

    def __init__(self, kod, **p):
        super().__init__("%s %s" % (kod, p))      # str(fel) går till loggen, aldrig till besökaren
        self.kod = kod
        self.p = p

    def text(self, sprak):
        return self.TEXTER[self.kod][sprak if sprak == "en" else "sv"].format(**self.p)


# ---------------------------------------------------------------------------
# Mintaka-klienten
# ---------------------------------------------------------------------------
def _hamta(sokvag, parametrar):
    url = MINTAKA_URL + sokvag + "?" + urllib.parse.urlencode(parametrar)
    begaran = urllib.request.Request(
        url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(begaran, timeout=TIMEOUT_S) as svar:
            # 206 Partial Content är Mintakas normalsvar vid paginering.
            return json.loads(svar.read().decode("utf-8"))
    except urllib.error.HTTPError as fel:
        print("[publik-vy] Mintaka svarade %s: %s" % (fel.code, fel.read()[:200].decode("utf-8", "replace")), flush=True)
        if fel.code == 404 and "/temporal/entities/" in sokvag:
            raise BrunnSaknas()
        raise MintakaFel("http", status=fel.code)
    except Exception as fel:                       # noqa: BLE001 – nätfel
        print("[publik-vy] Mintaka gick inte att nå: %s" % fel, flush=True)
        raise MintakaFel("nar_inte")


def _instanser(attribut):
    """Normaliserar ett temporalt attribut till en LISTA av instanser.

    Med `lastN=1` returnerar Mintaka attributet som ETT objekt i stället för
    en lista – NGSI-LD tillåter båda formerna. Vyn ska inte behöva bry sig.
    """
    if attribut is None:
        return []
    return attribut if isinstance(attribut, list) else [attribut]


def _senaste(instanser):
    """Nyaste instansen i en NGSI-LD temporal attributlista."""
    instanser = _instanser(instanser)
    if not instanser:
        return None, None
    nyast = max(instanser, key=lambda i: i.get("observedAt") or "")
    return nyast.get("value"), nyast.get("observedAt")


def lista_brunnar():
    """Senaste modellerade dygnet per bräddbrunn."""
    poster = _hamta("/temporal/entities", {
        "type": ENTITETSTYP,
        "attrs": ",".join(LISTKOLUMNER),
        "timerel": "after",
        "timeAt": FONSTER_FRAN,
        "lastN": 1,
        "limit": MAX_BRUNNAR,
    })
    brunnar = []
    for post in poster:
        rad = {"id": post.get("id", "").replace(
            "urn:ngsi-ld:%s:" % ENTITETSTYP, "")}
        observerat = None
        for falt in LISTKOLUMNER:
            varde, observerat_ = _senaste(post.get(falt) or [])
            rad[falt] = varde
            observerat = observerat or observerat_
        rad["observedAt"] = observerat
        rad["id_fullt"] = post.get("id")
        if any(rad[f] is not None for f in LISTKOLUMNER):
            brunnar.append(rad)
    brunnar.sort(key=lambda r: r["id"])
    return brunnar


def tidsserie(brunns_id):
    """Hela den öppna tidsserien för EN brunn, en rad per observedAt."""
    # Alltid en entitet av den öppna typen: ett urn: från besökaren får inte peka på någon annan entitetstyp (t.ex. A).
    kort = brunns_id[len(PREFIX):] if brunns_id.startswith(PREFIX) else brunns_id
    if not ID_MONSTER.fullmatch(kort):
        raise BrunnSaknas()
    fullt_id = PREFIX + kort
    post = _hamta("/temporal/entities/" + urllib.parse.quote(fullt_id), {
        "attrs": ",".join(OPPNA_ATTRIBUT),
        "timerel": "after",
        "timeAt": FONSTER_FRAN,
        "lastN": MAX_PUNKTER,
    })
    # Vänd den attributvisa strukturen till en rad per tidpunkt. Samma dygn
    # kan ha flera instanser (ominläsning av en batch) – då vinner den sist
    # skrivna, vilket är det värde CIP:en visar i nuläget.
    per_tid = {}
    for falt in OPPNA_ATTRIBUT:
        for instans in _instanser(post.get(falt)):
            tid = instans.get("observedAt")
            per_tid.setdefault(tid, {"observedAt": tid})[falt] = \
                instans.get("value")
    return [per_tid[t] for t in sorted(per_tid, reverse=True)]


# ---------------------------------------------------------------------------
# Innehållsförhandling
# ---------------------------------------------------------------------------
def vill_ha_json(begaran):
    if begaran.query_params.get("format") == "json":
        return True
    accept = (begaran.headers.get("accept") or "").lower()
    # Bara ett EXPLICIT json-önskemål ger JSON. `*/*` och webbläsarens
    # text/html ger HTML, så att både klick och nåbarhetskontroll ger 200.
    return "application/json" in accept and "text/html" not in accept


def _sprak(begaran):
    """?lang=en ger engelska; allt annat svenska."""
    return "en" if begaran.query_params.get("lang") == "en" else "sv"


def _fel(begaran, meddelande):
    if vill_ha_json(begaran):
        return JSONResponse({"fel": meddelande}, status_code=502)
    return HTMLResponse(
        _med_testlage(begaran, vy._sida("Tjänstefel" if _sprak(begaran) == "sv" else "Service error",
                 ("<h1>Kunde inte hämta data</h1>" if _sprak(begaran) == "sv"
                  else "<h1>Could not fetch the data</h1>") + f"<p>{vy.e(meddelande)}</p>",
                 _sprak(begaran))),
        status_code=502)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_fel(begaran: Request, fel: StarletteHTTPException):
    """En okänd adress ger en vanlig 404-sida för en webbläsare (med väg tillbaka) och JSON för maskinella klienter."""
    if fel.status_code == 404 and "text/html" in begaran.headers.get("accept", "") and not vill_ha_json(begaran):
        sp = _sprak(begaran)
        en = sp == "en"
        return HTMLResponse(_med_testlage(begaran, vy._sida("Page not found" if en else "Sidan finns inte",
                                     "<h1>%s</h1><p>%s</p><p><a href=\"/brunnar?lang=%s\">%s</a></p>"
                                     % ("Page not found" if en else "Sidan finns inte",
                                        "There is nothing at this address." if en else "Det finns inget på den här adressen.", sp,
                                        "Back to the list of chambers" if en else "Tillbaka till brunnslistan"), sp)), status_code=404)
    return JSONResponse({"detail": fel.detail}, status_code=fel.status_code)


@app.get("/api/aterstallning")
def api_aterstallning():
    """Nästa nattliga återställning (UTC) och serverns tid, för nedräkningen. Tomt svar lokalt."""
    import aterstall
    return aterstall.som_svar(os.environ.get("DEMO_ATERSTALL_KL", ""), os.environ.get("TZ", "UTC")) or {"nastaUtc": None}


@app.get("/health")
def health():
    # Inget internt värdnamn eller port (MINTAKA_URL) i svaret: /health är publik (fynd D5).
    return {"status": "ok", "version": VERSION,
            "fonsterFran": FONSTER_FRAN,
            "oppnaAttribut": list(OPPNA_ATTRIBUT)}


def _med_testlage(begaran, sida):
    """Testläget (kakan svada-test, satt med ?test=1): sidfoten säger att besöket inte räknas i statistiken."""
    # Caddy sätter kakan på SAMMA svar som ?test=1/?test=0 kommer med, så begäran bär ännu inte det nya läget: frågeparametern gäller före kakan
    # (annars ligger sidfoten ett sidbyte efter; provrunda 2026-10-26).
    lage = begaran.query_params.get("test")
    if lage not in ("0", "1"):
        lage = begaran.cookies.get("svada-test")
    if lage != "1":
        return sida
    text = ("Test mode: this visit is not counted in the statistics (end with ?test=0)." if _sprak(begaran) == "en"
            else "Testläge: besöket räknas inte i statistiken (avsluta med ?test=0).")
    rad = '<p id="testlage">%s</p>' % text
    if "</footer>" in sida:
        return sida.replace("</footer>", rad + "</footer>", 1)
    return sida.replace("</body>", rad + "</body>", 1)      # felsidorna har ingen sidfot


@app.get("/")
@app.get("/brunnar")
def brunnar(begaran: Request):
    try:
        rader = lista_brunnar()
    except MintakaFel as fel:
        return _fel(begaran, fel.text(_sprak(begaran)))
    if vill_ha_json(begaran):
        return JSONResponse({
            "dataset": "Modellerad bräddata",
            "distribution": "B",
            "informationClass": "K0R1T1",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "fonsterFran": FONSTER_FRAN,
            "hamtad": dt.datetime.now(dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "antal": len(rader),
            "brunnar": rader,
        })
    return HTMLResponse(_med_testlage(begaran, vy.landning(
        rader, _mintaka_exempel(), KATALOG_URL, FONSTER_FRAN,
        EGEN_PUBLIK + "/brunnar", _sprak(begaran))))


@app.get("/brunnar/{brunns_id}")
def en_brunn(brunns_id: str, begaran: Request):
    try:
        serie = tidsserie(brunns_id)
    except BrunnSaknas:
        if vill_ha_json(begaran):
            return JSONResponse({"fel": "brunnen finns inte" if _sprak(begaran) == "sv" else "the chamber does not exist"}, status_code=404)
        return HTMLResponse(_med_testlage(begaran, vy.brunn(brunns_id[:80], [], _mintaka_exempel(), KATALOG_URL, _sprak(begaran))), status_code=404)
    except MintakaFel as fel:
        return _fel(begaran, fel.text(_sprak(begaran)))
    if vill_ha_json(begaran):
        return JSONResponse({
            "id": brunns_id, "informationClass": "K0R1T1",
            "antal": len(serie), "serie": serie})
    return HTMLResponse(_med_testlage(begaran, vy.brunn(brunns_id, serie, _mintaka_exempel(),
                                                       KATALOG_URL, _sprak(begaran))))


def _mintaka_exempel():
    """Det maskinella gränssnittets adress – samma som Distribution B:s API."""
    return ("%s/temporal/entities?type=%s&attrs=%s&timerel=after&timeAt=%s"
            % (MINTAKA_PUBLIK, ENTITETSTYP, ",".join(LISTKOLUMNER),
               FONSTER_FRAN))
