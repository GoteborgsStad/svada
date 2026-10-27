#!/usr/bin/env python3
"""fcf-sim – "Future City Flow" (komponent 5).

Läser råmätvärden ur orion-dhi, modellerar brädd för alla 91 brunnar, och
producerar dataprodukten "Modellerad bräddata" som DAGLIG BATCH ("kl 05")
i två distributioner (A med brunns-GIS, B utan). Batchintervallet är
komprimerbart via env så att en demo hinner se flera dygn.

Dataplans-API:t (det EDC-providern pekar sin asset på):

  GET  /health
  GET  /distributions                      – de två distributionernas metadata
  GET  /distributions/{a|b}/latest         – senaste batchen
  GET  /distributions/{a|b}/batches        – batchlistan
  GET  /distributions/{a|b}/batches/{id}   – en specifik batch
  POST /batches/run                        – trigga en batch direkt (demo/test)
  GET  /weirs                              – brunnsregistret (internt)
  GET  /measurements                       – mätfönstret ur orion-dhi (internt)
  GET  /felinjektion       POST /felinjektion       POST /felinjektion/reset

Allt konfigureras via env – inget hårdkodat (portar/taggar ligger i .env).
"""

import contextlib
import datetime as dt
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

import brunnar as brunnsregister
import distributioner as dist_modul
import modell
from matvarden import CsvFonster, MatvardesFonster

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Konfiguration (env)
# ---------------------------------------------------------------------------
GPKG = os.environ.get("GPKG", "/data/dbsvadaexample.gpkg")
ORION_URL = os.environ.get("ORION_URL", "http://orion-dhi:1026")
# GOTCHA: utan NGSILD-Tenant svarar orion-dhi med tom lista.
ORION_TENANT = os.environ.get("ORION_TENANT", "dhi")
MATT_ENTITET = os.environ.get(
    "FCF_ENTITY_ID", "urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526")
MATT_WEIR_ID = os.environ.get("FCF_WEIR_ID", "SSO1_01-4526")

POLL_INTERVALL_S = float(os.environ.get("FCF_POLL_INTERVAL_S", "5"))
BATCH_INTERVALL_S = float(os.environ.get("FCF_BATCH_INTERVAL_S", "600"))
BATCH_TIMME = int(os.environ.get("FCF_BATCH_HOUR", "5"))
BATCH_RETENTION = int(os.environ.get("FCF_BATCH_RETENTION", "10"))
WARMUP_S = float(os.environ.get("FCF_WARMUP_S", "45"))
# Färre mätpunkter än så ger ett för magert basmönster – då används reserven.
MIN_MATPUNKTER = int(os.environ.get("FCF_MIN_SAMPLES", "12"))
START_DAG = os.environ.get("FCF_START_DAY", "").strip()


def _flagga(namn):
    return os.environ.get(namn, "false").strip().lower() in ("1", "true", "ja")


# Felinjektionen är AV som default (verifieringens testfall 3.8).
FEL = {
    "schemadrift": _flagga("FCF_FAULT_SCHEMA_DRIFT"),
    "saknade_parametrar": _flagga("FCF_FAULT_MISSING_FIELDS"),
    "gis_i_b": _flagga("FCF_FAULT_GIS_IN_B"),
}

# ---------------------------------------------------------------------------
# Tillstånd
# ---------------------------------------------------------------------------
BRUNNAR = brunnsregister.las_brunnar(GPKG)
GIS_KARTA = {b["weirId"]: {"location": b["location"],
                           "sourceSrs": b["sourceSrs"]} for b in BRUNNAR}

# Svada-mini: mätvärdena läses direkt ur brunn 4526:s CSV-filer (CSV_TOTAL, CSV_SPILL).
# Utan dem faller FCF tillbaka på orion-dhi (den gamla vägen via sensorledet).
CSV_TOTAL = os.environ.get("CSV_TOTAL", "")
CSV_SPILL = os.environ.get("CSV_SPILL", "")
if CSV_TOTAL and CSV_SPILL:
    FONSTER = CsvFonster(CSV_TOTAL, CSV_SPILL, MATT_WEIR_ID)
else:
    FONSTER = MatvardesFonster(ORION_URL, MATT_ENTITET, ORION_TENANT,
                               intervall_s=POLL_INTERVALL_S)

BATCHAR = []                     # nyast sist (kapad av FCF_BATCH_RETENTION)
# Monotont löpnummer för batchar. FÅR INTE härledas ur len(BATCHAR):
# listan kapas av retentionen, så efter FCF_BATCH_RETENTION batchar hade
# löpnumret (och därmed batchId och modellerat dygn) frusit.
# Felet upptäcktes av verify_ap3.sh 3.5 först
# efter att fcf-sim varit igång tio batchintervall.
BATCH_RAKNARE = 0
BATCH_LAS = threading.Lock()
# Ankaret för dygnssekvensen. Fryses vid första batchen – se _startdygn().
START_DYGN = None
STARTAD = dt.datetime.now(dt.timezone.utc)


@contextlib.asynccontextmanager
async def livscykel(_app):
    """Startar mätvärdespollningen och batchloopen (bakgrundstrådar)."""
    FONSTER.starta()
    threading.Thread(target=_batchloop, name="batch", daemon=True).start()
    yield
    FONSTER.stoppa()


app = FastAPI(title="fcf-sim – Future City Flow (SVADA PoC)",
              version=VERSION, lifespan=livscykel)


# ---------------------------------------------------------------------------
# Batchproduktion
# ---------------------------------------------------------------------------
def _startdygn():
    """Första modellerade dygnet: env, annars mätseriens egen dag.

    Härleds EN gång och FRYSES sedan. Ankaret får INTE räknas om per batch:
    sensor-simulatorn spelar upp CSV:n i loop, så `senaste observedAt`
    vandrar genom serien och hoppar tillbaka vid varje varv. Med ett rörligt
    ankare blir `dygn = ankare + index` icke-monotont och två batchar kan
    landa på samma modelledDay – exakt det verify_ap3.sh 3.5 fångar.

    Samma buggklass som den frusna BATCH_RAKNARE ovan (se kommentaren vid
    BATCH_RAKNARE ovan): syns först när tjänsten hunnit producera mer än en batch.

    Anropas alltid inifrån BATCH_LAS (kor_batch), så memoiseringen behöver
    inget eget lås.
    """
    global START_DYGN
    if START_DYGN is not None:
        return START_DYGN
    if START_DAG:
        START_DYGN = dt.date.fromisoformat(START_DAG)
    else:
        senaste = FONSTER.senaste()
        if senaste:
            # observedAt = mätningens egen tid (2026-06-13/14), inte
            # uppspelningens.
            START_DYGN = dt.date.fromisoformat(senaste["observedAt"][:10])
        else:
            # Kallstart utan mätvärden: ankra på idag. Ankaret fryses ändå,
            # så dygnssekvensen förblir monoton även i detta fall.
            START_DYGN = dt.datetime.now(dt.timezone.utc).date()
    return START_DYGN


def kor_batch():
    """Modellerar ett dygn för alla 91 brunnar och lagrar batchen."""
    punkter = FONSTER.punkter()
    bas, tackning = modell.bas_fran_matvarden(punkter)
    if bas and tackning >= MIN_MATPUNKTER:
        kalla = ("%s/%s – %s" % ("csv" if CSV_TOTAL else "orion-dhi", MATT_WEIR_ID,
                                 ("alla %d tidpunkter i dygnet mätta" % modell.PUNKTER_PER_DYGN)
                                 if tackning >= modell.PUNKTER_PER_DYGN else
                                 "%d av %d tidpunkter mätta, resten reservmönster" % (tackning, modell.PUNKTER_PER_DYGN)))
        matt_id = MATT_WEIR_ID
    else:
        # Ärligt redovisad fallback – API:t ska svara även direkt efter
        # kallstart, innan mätvärdena hunnit strömma in.
        bas = modell.basmonster()
        tackning = 0
        kalla = ("internt basmönster (endast %d mätpunkter i fönstret)"
                 % len(punkter))
        matt_id = None

    global BATCH_RAKNARE
    with BATCH_LAS:
        index = BATCH_RAKNARE
        BATCH_RAKNARE += 1
        dygn = _startdygn() + dt.timedelta(days=index)
        poster = dist_modul.bygg_poster(BRUNNAR, bas, index, dygn, matt_id,
                                        tackning)
        # "kl 05"-batchen: dygnet stängs och modelleras klockan 05 dygnet efter.
        klocka = dt.datetime.combine(
            dygn + dt.timedelta(days=1), dt.time(BATCH_TIMME, 0),
            tzinfo=dt.timezone.utc)
        batch = {
            "batchId": "batch-%03d-%s" % (index + 1, dygn.isoformat()),
            "batchClock": klocka.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "producedAt": dt.datetime.now(dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"),
            "modelledDay": dygn.isoformat(),
            "measurementSource": kalla,
            "poster": poster,
        }
        BATCHAR.append(batch)
        del BATCHAR[:-BATCH_RETENTION]
    return batch


def _batchloop():
    # Vänta in mätvärden så att dygn 1 modelleras på riktiga data (annars
    # faller kor_batch tillbaka på det interna basmönstret – redovisat i
    # fältet measurementSource). Väntan bryts så snart MIN_MATPUNKTER finns;
    # WARMUP_S är bara ett tak för det trasiga fallet. Det är också här
    # startdygnet ankras (_startdygn), så en för kort väntan gav BÅDE
    # syntetisk sensorbrunn och ett ankare taget ur luften.
    if not FONSTER.vanta_pa_data(WARMUP_S, minst=MIN_MATPUNKTER):
        print("VARNING: inga mätvärden inom %.0f s – batch 1 modelleras på "
              "reservmönstret (se measurementSource)" % WARMUP_S, flush=True)
    while True:
        try:
            batch = kor_batch()
            print("batch klar: %s (%s)" % (batch["batchId"],
                                           batch["measurementSource"]),
                  flush=True)
        except Exception as fel:            # noqa: BLE001
            # Loopen får ALDRIG dö tyst – då slutar dataprodukten produceras
            # utan att health säger något (drabbade oss under utvecklingen).
            print("FEL i batchproduktionen: %s: %s" % (type(fel).__name__, fel),
                  flush=True)
        time.sleep(BATCH_INTERVALL_S)


# ---------------------------------------------------------------------------
# Hjälpare för utlämning
# ---------------------------------------------------------------------------
def _dist(dist):
    d = dist.lower()
    if d not in dist_modul.DIST_META:
        raise HTTPException(status_code=404,
                            detail="okänd distribution: %s (a eller b)" % dist)
    return d


def _svar(dist, batch):
    poster = batch["poster"]
    if dist == "b":
        poster = dist_modul.till_b(poster)
    svar = dist_modul.kuvert(dist, batch, poster)
    return dist_modul.tillampa_felinjektion(svar, dist, FEL, GIS_KARTA)


def _hitta(batch_id):
    with BATCH_LAS:
        for b in BATCHAR:
            if b["batchId"] == batch_id:
                return b
    raise HTTPException(status_code=404, detail="okänd batch: %s" % batch_id)


def _senaste():
    with BATCH_LAS:
        if not BATCHAR:
            raise HTTPException(
                status_code=503,
                detail="ingen batch producerad ännu – försök igen om en stund")
        return BATCHAR[-1]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return {
        "service": "fcf-sim",
        "version": VERSION,
        "dataset": dist_modul.DATASET,
        "endpoints": ["/health", "/distributions",
                      "/distributions/{a|b}/latest",
                      "/distributions/{a|b}/batches",
                      "/distributions/{a|b}/batches/{batchId}",
                      "/batches/run", "/weirs", "/measurements",
                      "/felinjektion"],
    }


@app.get("/health")
def health():
    with BATCH_LAS:
        antal = len(BATCHAR)
        totalt = BATCH_RAKNARE
        senaste = BATCHAR[-1]["batchId"] if BATCHAR else None
    return {
        "status": "ok",
        "version": VERSION,
        "startedAt": STARTAD.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weirs": len(BRUNNAR),
        "batches": antal,                  # sparade batchar (högst FCF_BATCH_RETENTION)
        "batchesTotal": totalt,            # producerade sedan start (löpnumret) – ökar med varje batch
        "latestBatchId": senaste,
        # Det frusna ankaret för dygnssekvensen (None före batch 1). Görs
        # synligt just för att ett vandrande ankare var osynligt i det tysta.
        "firstModelledDay": START_DYGN.isoformat() if START_DYGN else None,
        "measurementWindow": FONSTER.lage()["punkterIFonstret"],
        "faultInjectionActive": any(FEL.values()),
    }


@app.get("/distributions")
def distributioner():
    with BATCH_LAS:
        senaste = BATCHAR[-1]["batchId"] if BATCHAR else None
    ut = []
    for nyckel, meta in dist_modul.DIST_META.items():
        ut.append({
            "distribution": nyckel.upper(),
            "distributionId": meta["distributionId"],
            "title": meta["titel"],
            "accessRights": meta["accessRights"],
            "informationClass": meta["informationsklass"],
            "license": meta["licens"],
            "odrlTerms": meta["villkor"],
            "containsWeirGis": nyckel == "a",
            "accessURL": "/distributions/%s/latest" % nyckel,
            "latestBatchId": senaste,
        })
    return {"dataset": dist_modul.DATASET, "distributions": ut}


@app.get("/distributions/{dist}/latest")
def senaste_batch(dist: str):
    d = _dist(dist)
    return JSONResponse(_svar(d, _senaste()))


@app.get("/distributions/{dist}/batches")
def batchlista(dist: str):
    d = _dist(dist)
    with BATCH_LAS:
        lista = [{
            "batchId": b["batchId"],
            "batchClock": b["batchClock"],
            "producedAt": b["producedAt"],
            "modelledDay": b["modelledDay"],
            "recordCount": len(b["poster"]),
            "href": "/distributions/%s/batches/%s" % (d, b["batchId"]),
        } for b in BATCHAR]
    return {"distribution": d.upper(), "count": len(lista), "batches": lista}


@app.get("/distributions/{dist}/batches/{batch_id}")
def en_batch(dist: str, batch_id: str):
    d = _dist(dist)
    return JSONResponse(_svar(d, _hitta(batch_id)))


@app.post("/batches/run")
def trigga_batch():
    batch = kor_batch()
    return {"batchId": batch["batchId"], "producedAt": batch["producedAt"],
            "modelledDay": batch["modelledDay"],
            "measurementSource": batch["measurementSource"],
            "recordCount": len(batch["poster"])}


@app.get("/weirs")
def brunnslista():
    return {"count": len(BRUNNAR), "weirs": BRUNNAR}


@app.get("/measurements")
def matvarden():
    """Mätfönstret – underlaget för "mätt vs modellerat"."""
    lage = FONSTER.lage()
    lage["window"] = FONSTER.punkter()[-24:]
    return lage


@app.get("/felinjektion")
def las_fel():
    return {
        "aktiv": any(FEL.values()),
        "lagen": dict(FEL),
        "beskrivning": {
            "schemadrift": "döper om %s" % ", ".join(
                "%s -> %s" % kv for kv in
                dist_modul.SCHEMADRIFT_NYA_NAMN.items()),
            "saknade_parametrar": "tar bort %s" % ", ".join(
                dist_modul.SAKNADE_FALT),
            "gis_i_b": "AVTALSBROTT: lägger tillbaka brunns-GIS "
                       "(location, sourceSrs) i Distribution B",
        },
        # Samma beskrivningar som språkoberoende meddelanden (kontrollrummets meddelandekatalog):
        "beskrivningKod": {
            "schemadrift": {"kod": "fcf.schemadrift",
                            "parametrar": {"byten": ", ".join(
                                "%s -> %s" % kv for kv in dist_modul.SCHEMADRIFT_NYA_NAMN.items())}},
            "saknade_parametrar": {"kod": "fcf.saknade_parametrar",
                                   "parametrar": {"falt": list(dist_modul.SAKNADE_FALT)}},
            "gis_i_b": {"kod": "fcf.gis_i_b", "parametrar": {}},
        },
    }


@app.post("/felinjektion")
def satt_fel(kropp: dict):
    okanda = [k for k in kropp if k not in FEL]
    if okanda:
        raise HTTPException(status_code=400,
                            detail="okända lägen: %s" % ", ".join(okanda))
    for nyckel, varde in kropp.items():
        FEL[nyckel] = bool(varde)
    return las_fel()


@app.post("/felinjektion/reset")
def nollstall_fel():
    for nyckel in FEL:
        FEL[nyckel] = False
    return las_fel()
