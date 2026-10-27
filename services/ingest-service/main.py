#!/usr/bin/env python3
"""ingest-service – stadens mottagning av EDC-transfern (komponent 8).

Plats i kedjan:

    fcf-sim (DHI)  --GET-->  edc-provider dataplan  --HTTP-PUSH-->  INGEST
                                                                      |
                                              NGSI-LD upsert + proveniens
                                                                      v
                                                    orion-stad (CIP) + Mintaka

Tjänsten gör tre saker och vägrar allt annat:

  1. Utfärdar ENGÅNGSAUKTORISATION mot ett kontraktsavtal som staden
     faktiskt har (auktorisation.py) – utan avtal, ingen token.
  2. Tar emot providerns push, VALIDERAR den (validering.py) och avvisar
     med tydlig orsak om schemat avviker eller om Distribution B bär
     brunns-GIS (avtalsbrott).
  3. Transformerar till NGSI-LD (en entitetstyp per distribution) med proveniens
     (avtals-ID, dataprodukt, distribution, batch, tidpunkt) och skriver
     till orion-stad (ngsild.py).

API:

  GET  /health                     – status + räknare
  POST /auktorisation              – {"contractAgreementId": "..."} -> token
  POST /ingest                     – providerns push (Authorization: Bearer)
  GET  /leveranser                 – kvitto-/avvisningslogg (dashboard, tester)
  GET  /auktorisationer            – utfärdade tokens (utan själva token)

Allt konfigureras via env – portar och id:n kommer ur .env (hård regel 4/5).
"""

import asyncio
import datetime as dt
import os
import threading

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

import ngsild
import validering
from auktorisation import Auktorisationer, Auktorisationsfel
from avtalsregister import Avtalsregister

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Konfiguration (env)
# ---------------------------------------------------------------------------
ORION_URL = os.environ.get("ORION_URL", "http://orion-stad:1026").rstrip("/")
# Stadens EGEN connector – ingest slår upp avtalet där (aldrig hos DHI:s).
EDC_MGMT_URL = os.environ.get(
    "EDC_MGMT_URL", "http://edc-consumer:29193/management")
ASSET_A_ID = os.environ.get("EDC_ASSET_A_ID", "modellerad-bradddata-a")
ASSET_B_ID = os.environ.get("EDC_ASSET_B_ID", "modellerad-bradddata-b")
# Nyckelskyddat management-API: delad nyckel mot edc-consumers management-API.
MGMT_KEY = os.environ.get("EDC_CONSUMER_MGMT_KEY", "")
TOKEN_TTL_S = int(os.environ.get("INGEST_TOKEN_TTL_S", "600"))
LOGG_RETENTION = int(os.environ.get("INGEST_LOG_RETENTION", "50"))

# Providerns smala, skrivskyddade avtalsstatus (inte management-API:t). Se avtalsregister.py.
PROVIDER_STATUS_URL = os.environ.get(
    "EDC_PROVIDER_STATUS_URL", "http://edc-provider:19195/status")
PROVIDER_STATUS_KEY = os.environ.get("EDC_PROVIDER_STATUS_KEY", "")
AVTAL_BAS_URL = os.environ.get("AVTAL_BAS_URL", "")

ASSET_DIST = {ASSET_A_ID: "a", ASSET_B_ID: "b"}
REGISTER = Avtalsregister(EDC_MGMT_URL, MGMT_KEY, PROVIDER_STATUS_URL,
                          PROVIDER_STATUS_KEY, ASSET_DIST,
                          offentlig_bas=AVTAL_BAS_URL)
AUKT = Auktorisationer(EDC_MGMT_URL, ASSET_DIST,
                       mgmt_key=MGMT_KEY, ttl_s=TOKEN_TTL_S,
                       register=REGISTER)

# ---------------------------------------------------------------------------
# Tillstånd: leveransloggen (kvitton OCH avvisningar – båda är bevis)
# ---------------------------------------------------------------------------
LEVERANSER = []
LEVERANS_LAS = threading.Lock()
RAKNARE = {"mottagna": 0, "accepterade": 0, "avvisade": 0, "entiteter": 0}
STARTAD = dt.datetime.now(dt.timezone.utc)

app = FastAPI(title="ingest-service – stadens EDC-mottagning (SVADA PoC)",
              version=VERSION)


@app.on_event("startup")
def _starta_register():
    REGISTER.kor()


def _nu():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _logga(post):
    """Skriver en rad i leveransloggen och på stdout (docker logs)."""
    post["at"] = _nu()
    with LEVERANS_LAS:
        LEVERANSER.append(post)
        del LEVERANSER[:-LOGG_RETENTION]
    print("[ingest] %s %s" % (post["resultat"],
                              post.get("detalj") or post.get("batchId", "")),
          flush=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return {"service": "ingest-service", "version": VERSION,
            "endpoints": ["/health", "/auktorisation", "/ingest",
                          "/leveranser", "/auktorisationer"]}


@app.get("/health")
def health():
    with LEVERANS_LAS:
        senaste = LEVERANSER[-1] if LEVERANSER else None
    return {"status": "ok", "version": VERSION,
            "startedAt": STARTAD.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "orion": ORION_URL, "edcManagement": EDC_MGMT_URL,
            "counters": dict(RAKNARE), "latestDelivery": senaste}


@app.post("/auktorisation")
async def auktorisera(begaran: Request):
    """Växlar ett kontraktsavtal mot en engångstoken (se auktorisation.py)."""
    try:
        kropp = await begaran.json()
    except Exception:                                    # noqa: BLE001
        kropp = {}
    avtals_id = (kropp or {}).get("contractAgreementId")
    try:
        post = await asyncio.to_thread(AUKT.utfarda, avtals_id)
    except Auktorisationsfel as fel:
        _logga({"resultat": "AUKTORISATION-NEKAD", "orsak": fel.orsak,
                "detalj": fel.detalj, "kod": fel.kod, "parametrar": fel.parametrar,
                "contractAgreementId": avtals_id})
        return JSONResponse(status_code=fel.status,
                            content={"fel": fel.orsak, "detalj": fel.detalj,
                                     "kod": fel.kod, "parametrar": fel.parametrar})
    _logga({"resultat": "AUKTORISERAD", "contractAgreementId": avtals_id,
            "distribution": post["distribution"].upper(),
            "detalj": "engångstoken utfärdad för Distribution %s"
                      % post["distribution"].upper(),
            "kod": "ingest.auktoriserad", "parametrar": {"dist": post["distribution"].upper()}})
    return {"token": post["token"], "contractAgreementId": avtals_id,
            "assetId": post["assetId"],
            "distribution": post["distribution"].upper(),
            "expiresInSeconds": TOKEN_TTL_S}


@app.post("/ingest")
async def ingest(begaran: Request,
                 authorization: str = Header(default=""),
                 x_transfer_process_id: str = Header(default="")):
    """Tar emot providerns HTTP-push. Allt utom en giltig leverans avvisas."""
    RAKNARE["mottagna"] += 1
    token = authorization.split("Bearer ", 1)[-1].strip() if authorization \
        else ""

    def avvisa(status, orsak, detalj, exempel=None, extra=None, kod=None, parametrar=None, exempel_p=None):
        RAKNARE["avvisade"] += 1
        post = {"resultat": "AVVISAD", "orsak": orsak, "detalj": detalj,
                "kod": kod, "parametrar": parametrar or {}}
        post.update(extra or {})
        if exempel:
            post["exempel"] = exempel
            post["exempelParametrar"] = exempel_p or []
        _logga(post)
        svar = {"fel": orsak, "detalj": detalj, "kod": kod, "parametrar": parametrar or {}}
        if exempel:
            svar["exempel"] = exempel
        return JSONResponse(status_code=status, content=svar)

    # 1. Engångsauktorisationen (= har staden ett avtal för detta?)
    try:
        aukt = AUKT.konsumera(token)
    except Auktorisationsfel as fel:
        return avvisa(fel.status, fel.orsak, fel.detalj, kod=fel.kod, parametrar=fel.parametrar)

    # 1b. Avtalet måste fortfarande gälla (avtal gäller tills de hävs).
    # Statusen kan kräva en synk mot providern: hålls utanför händelseslingan.
    st = await asyncio.to_thread(REGISTER.status, aukt["contractAgreementId"])
    if st["status"] != "GALLANDE":
        return avvisa(403, {"HAVT": "avtal-havt", "UTGANGET": "avtal-utgatt"}.get(
                          st["status"], "avtal-status-okand"),
                      "avtalet %s har status %s – ingen ingest"
                      % (aukt["contractAgreementId"], st["status"]),
                      extra={"contractAgreementId":
                             aukt["contractAgreementId"]},
                      kod="ingest.avtal_status_ingest",
                      parametrar={"avtal": aukt["contractAgreementId"], "status": st["status"]})

    # 2. Nyttolasten
    try:
        kropp = await begaran.json()
    except Exception:                                    # noqa: BLE001
        return avvisa(400, "ogiltig-json",
                      "nyttolasten gick inte att tolka som JSON",
                      extra={"contractAgreementId":
                             aukt["contractAgreementId"]},
                      kod="ingest.ogiltig_json")

    gemensamt = {"contractAgreementId": aukt["contractAgreementId"],
                 "avtaladDistribution": aukt["distribution"].upper()}
    try:
        dist = validering.granska_kuvert(kropp)
        validering.granska_mot_avtal(dist, aukt["distribution"])
        validering.granska_poster(dist, kropp["records"])
    except validering.Avvisad as fel:
        gemensamt["batchId"] = kropp.get("batchId") if isinstance(kropp, dict) \
            else None
        return avvisa(fel.status, fel.orsak, fel.detalj, fel.exempel,
                      gemensamt, kod=fel.kod, parametrar=fel.parametrar, exempel_p=fel.exempel_p)

    # 3. Transformation + skrivning till CIP:en
    proveniens = ngsild.bygg_proveniens(
        kropp, aukt["contractAgreementId"], dist,
        x_transfer_process_id or None,
        avtal_url=REGISTER.hamta_url(aukt["contractAgreementId"]))
    entiteter = ngsild.till_entiteter(kropp, kropp["records"], proveniens, dist)
    try:
        skrivna = ngsild.skriv(ORION_URL, entiteter)
    except ngsild.OrionFel as fel:
        return avvisa(502, "orion-skrivfel",
                      "kunde inte skriva till stadens dataplattform: %s" % fel,
                      extra=gemensamt, kod="ingest.orion_skrivfel", parametrar={"fel": str(fel)})

    RAKNARE["accepterade"] += 1
    RAKNARE["entiteter"] += skrivna
    kvitto = {
        "resultat": "LEVERERAD",
        "distribution": dist.upper(),
        "batchId": kropp.get("batchId"),
        "modelledDay": kropp.get("modelledDay"),
        "records": len(kropp["records"]),
        "entiteter": skrivna,
        "contractAgreementId": aukt["contractAgreementId"],
        "transferProcessId": x_transfer_process_id or None,
        "detalj": "Distribution %s, batch %s -> %d entiteter i stadens dataplattform"
                  % (dist.upper(), kropp.get("batchId"), skrivna),
        "kod": "ingest.levererad",
        "parametrar": {"dist": dist.upper(), "batch": kropp.get("batchId"), "entiteter": skrivna},
    }
    _logga(kvitto)
    return kvitto


@app.get("/avtal")
def avtal_lista():
    """Stadens avtalsregister: alla avtal staden har, med status."""
    return {"avtal": REGISTER.lista(), "synkfel": REGISTER.fel()}


@app.get("/avtal/{avtals_id}/status")
def avtal_status(avtals_id: str):
    """Färsk status (gatewayen frågar här vid varje åtkomst; stängt som standard)."""
    return REGISTER.status(avtals_id)


@app.get("/avtal/{avtals_id}")
def avtal_detalj(avtals_id: str):
    post = REGISTER.hamta(avtals_id)
    if post is None:
        return JSONResponse(status_code=404,
                            content={"fel": "okant-avtal", "id": avtals_id})
    return post


@app.get("/leveranser")
def leveranser():
    with LEVERANS_LAS:
        lista = list(LEVERANSER)
    return {"count": len(lista), "counters": dict(RAKNARE),
            "deliveries": lista}


@app.get("/auktorisationer")
def auktorisationer():
    return {"authorizations": AUKT.lage()}
