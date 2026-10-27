#!/usr/bin/env python3
"""stad-gateway – åtkomstkontroll framför stadens CIP (åtgärd av G22).

Vad tjänsten är
---------------
Den enda vägen in till `orion-stad` utifrån värden. Före den här åtgärden
publicerade `orion-stad` port 2026 rakt ut: Distribution A:s `accessURL` i
katalogen gick att klicka på och gav 91 bräddbrunnars fulla GIS till vem som
helst, trots `access-right/NON_PUBLIC`. Märkningen var en etikett utan
verkställighet. Nu lyssnar gatewayen på 2026 och `orion-stad` publicerar
ingen port alls – den nås bara från `stad-internal`.

Tjänsten gör tre saker och vägrar allt annat:

  1. SLÄPPER IGENOM liveness (`/ngsi-ld/ex/v1/version`) utan token, så att
     healthchecks och dashboardens statusvy kan se att CIP:en lever utan att
     därmed få läsa den.
  2. UTFÄRDAR åtkomsttoken mot ett kontraktsavtal som staden faktiskt har
     för Distribution A (atkomst.py) – utan avtal, ingen token.
  3. PROXAR allt annat vidare till orion-stad, oförändrat, men bara med
     giltig token. Utan token: 403 med orsaken utskriven – som HTML för en
     webbläsare och som NGSI-LD-format för en maskin.

API:

  GET  /health                     – status + räknare
  POST /auktorisation              – {"contractAgreementId": "..."} -> token
  GET  /auktorisationer            – utfärdade tokens (utan själva token)
  *    /ngsi-ld/...                – proxas till orion-stad

Allt konfigureras via env – portar och id:n kommer ur .env (hård regel 4/5).
"""

import datetime as dt
import json
import os
import types
import urllib.error
import urllib.parse
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import vy
from atkomst import Atkomstfel, Atkomstregister

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Konfiguration (env)
# ---------------------------------------------------------------------------
ORION_URL = os.environ.get("ORION_URL", "http://orion-stad:1026").rstrip("/")
# Stadens EGEN connector – gatewayen slår upp avtalet där (aldrig hos DHI:s).
EDC_MGMT_URL = os.environ.get(
    "EDC_MGMT_URL", "http://edc-consumer:29193/management")
ASSET_A_ID = os.environ.get("EDC_ASSET_A_ID", "modellerad-bradddata-a")
DRIFT_TOKEN = os.environ.get("STAD_GATEWAY_DRIFT_TOKEN", "")
# Nyckelskyddat management-API: delad nyckel mot edc-consumers management-API.
MGMT_KEY = os.environ.get("EDC_CONSUMER_MGMT_KEY", "")
TOKEN_TTL_S = int(os.environ.get("STAD_GATEWAY_TOKEN_TTL_S", "3600"))
TIMEOUT_S = float(os.environ.get("STAD_GATEWAY_TIMEOUT_S", "30"))

# Adresser som VISAS för användaren – värdens portar, inte containernamnen.
EGEN_PUBLIK = os.environ.get("STAD_GATEWAY_PUBLIK_URL",
                             "http://localhost:2026").rstrip("/")
PUBLIK_VY_PUBLIK = os.environ.get("PUBLIK_VY_PUBLIK_URL",
                                  "http://localhost:8085").rstrip("/")
MINTAKA_PUBLIK = os.environ.get("MINTAKA_PUBLIK_URL",
                                "http://localhost:8083").rstrip("/")

# Stadens avtalsregister (ingest-service) avgör om avtalet fortfarande gäller.
AVTALSSTATUS_URL = os.environ.get("INGEST_URL", "http://ingest-service:8060")
REGISTER = Atkomstregister(EDC_MGMT_URL, ASSET_A_ID, DRIFT_TOKEN,
                           mgmt_key=MGMT_KEY, ttl_s=TOKEN_TTL_S,
                           avtalsstatus_url=AVTALSSTATUS_URL)
STARTAD = dt.datetime.now(dt.timezone.utc)

# Headers som ska följa med i BÅDA riktningarna. Authorization skickas
# medvetet INTE vidare: den är gatewayens, inte orion-stads (orion-stad har
# ingen egen autentisering och skulle bara ignorera den).
VIDARE_IN = ("accept", "content-type", "link", "ngsild-tenant",
             "ngsild-path", "accept-language")
VIDARE_UT = ("content-type", "link", "ngsild-results-count",
             "location", "content-range")

# Externa varianten (publik demo): ingen intern adress i svaren och ingen
# API-dokumentation (Swagger laddas dessutom från ett CDN).
EXTERN = os.environ.get("DEMO_VARIANT", "intern") == "extern"

app = FastAPI(title="stad-gateway – åtkomstkontroll framför stadens CIP "
                    "(SVADA PoC)",
              version=VERSION,
              docs_url=None if EXTERN else "/docs",
              redoc_url=None if EXTERN else "/redoc",
              openapi_url=None if EXTERN else "/openapi.json")


def _vill_ha_html(request):
    """Sant när anroparen är en webbläsare (jfr publik-vy, G9-åtgärden)."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


def _offentlig_text(fel):
    """(detalj, kod, parametrar) så som en besökare får se dem: den externa varianten visar inga interna adresser."""
    if EXTERN and fel.orsak == "edc-svarar-inte":
        return "stadens EDC svarar inte", None, {}
    return fel.detalj, fel.kod, fel.parametrar


def _avslagssvar(request, fel, sokvag):
    """Ett NEJ som går att läsa – för människa respektive maskin."""
    if _vill_ha_html(request):
        # Den externa varianten visar ingen intern adress i HTML-svaret heller (samma text som i JSON-svaret).
        offentligt = types.SimpleNamespace(orsak=fel.orsak, detalj=_offentlig_text(fel)[0])
        return HTMLResponse(
            vy.avslag(offentligt, sokvag, EGEN_PUBLIK, "",
                      PUBLIK_VY_PUBLIK, MINTAKA_PUBLIK,
                      "en" if (request.query_params.get("lang") == "en"
                               or (request.query_params.get("lang") != "sv" and request.cookies.get("svada-sprak") == "en")) else "sv"),
            status_code=fel.status)
    return JSONResponse(
        status_code=fel.status,
        content={
            "type": "https://svada.goteborg.se/ngsi-ld/errors/AccessDenied",
            "title": "Åtkomst nekad",
            "status": fel.status,
            "orsak": fel.orsak,
            "detail": _offentlig_text(fel)[0],
            "kod": _offentlig_text(fel)[1], "parametrar": _offentlig_text(fel)[2],
            "accessRights": "http://publications.europa.eu/resource/"
                            "authority/access-right/NON_PUBLIC",
            "informationClass": "K1R1T1",
            "dataRightsHolder": "Kretslopp och Vatten, Göteborgs Stad",
            "oppetAlternativ": {
                "distribution": "B (K0R1T1, öppna data, utan brunns-GIS)",
                "webbvy": PUBLIK_VY_PUBLIK + "/brunnar",
                "api": MINTAKA_PUBLIK + "/temporal/entities",
            },
        })


# ---------------------------------------------------------------------------
# Gatewayens egna endpoints (deklareras FÖRE catch-all-rutten)
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "orion": None if EXTERN else ORION_URL,
        "startad": STARTAD.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "drifttokenKonfigurerad": bool(DRIFT_TOKEN),
        "raknare": dict(REGISTER.raknare),
    }


@app.post("/auktorisation")
async def auktorisation(request: Request):
    """Växlar ett kontraktsavtal för Distribution A mot en åtkomsttoken."""
    try:
        kropp = json.loads(await request.body() or b"{}")
    except ValueError:
        return JSONResponse(status_code=400,
                            content={"orsak": "ogiltig-json",
                                     "detail": "kroppen är inte giltig JSON",
                                     "kod": "gateway.ogiltig_json", "parametrar": {}})
    try:
        post = REGISTER.utfarda(kropp.get("contractAgreementId"))
    except Atkomstfel as fel:
        detalj, kod, parametrar = _offentlig_text(fel)
        return JSONResponse(status_code=fel.status,
                            content={"orsak": fel.orsak, "detail": detalj,
                                     "kod": kod, "parametrar": parametrar})
    return {
        "token": post["token"],
        "contractAgreementId": post["contractAgreementId"],
        "assetId": post["assetId"],
        "gallerISekunder": TOKEN_TTL_S,
        "anvandning": "Authorization: Bearer <token> mot %s/ngsi-ld/v1/..."
                      % EGEN_PUBLIK,
    }


@app.get("/auktorisationer")
def auktorisationer():
    return {"utfardade": REGISTER.lage(), "raknare": dict(REGISTER.raknare)}


# ---------------------------------------------------------------------------
# Catch-all: allt under /ngsi-ld proxas till orion-stad – med åtkomstbeslut
# ---------------------------------------------------------------------------
@app.api_route("/{sokvag:path}",
               methods=["GET", "POST", "PATCH", "PUT", "DELETE", "HEAD",
                        "OPTIONS"])
async def proxy(sokvag: str, request: Request):
    full_sokvag = "/" + sokvag
    try:
        REGISTER.avgor(full_sokvag, request.headers.get("authorization"))
    except Atkomstfel as fel:
        return _avslagssvar(request, fel, full_sokvag)

    mal = ORION_URL + full_sokvag
    if request.url.query:
        mal += "?" + request.url.query

    kropp = await request.body()
    req = urllib.request.Request(mal, data=kropp or None,
                                 method=request.method)
    for namn in VIDARE_IN:
        varde = request.headers.get(namn)
        if varde:
            req.add_header(namn, varde)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as svar:
            return _vidarebefordra(svar.status, svar.headers, svar.read())
    except urllib.error.HTTPError as fel:
        # Orion-LD:s egna felsvar ska nå anroparen OFÖRÄNDRADE – annars blir
        # gatewayen svår att felsöka bakom (t.ex. NGSI-LD:s 400 på fel
        # Accept-huvud, som är ett äkta protokollsvar och inte vårt fel).
        return _vidarebefordra(fel.code, fel.headers, fel.read())
    except (urllib.error.URLError, OSError, TimeoutError) as fel:
        return JSONResponse(
            status_code=502,
            content={"orsak": "cip-svarar-inte",
                     "detail": "kunde inte nå orion-stad"
                               if EXTERN else
                               "kunde inte nå orion-stad (%s): %s"
                               % (ORION_URL, fel),
                     "kod": "gateway.cip_otillganglig", "parametrar": {}})


def _vidarebefordra(status, headers, kropp):
    ut = {}
    for namn in VIDARE_UT:
        varde = headers.get(namn)
        if varde:
            ut[namn] = varde
    media = ut.pop("content-type", None)
    return Response(content=kropp, status_code=status, headers=ut,
                    media_type=media)
