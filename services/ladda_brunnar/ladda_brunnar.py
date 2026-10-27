#!/usr/bin/env python3
"""KONCEPT: docs/koncept/02-ngsi-ld.md

Engångsjobb: läser bräddbrunnarna ur dbsvadaexample.gpkg och skapar dem
som NGSI-LD-entiteter av typ SewerOverflowWeir i stadens broker (orion-stad).

Kör antingen i container (compose-profilen "laddning") eller direkt på
värden:  ORION_URL=http://localhost:2026 python3 ladda_brunnar.py

Jobbet är IDEMPOTENT: det använder NGSI-LD:s batch-upsert, så en omkörning
ger samma 91 entiteter (inga dubbletter).

Beroenden: endast Pythons standardbibliotek (sqlite3, struct, urllib) – gpkg
är en SQLite-databas och WKB-parsningen görs för hand. Därmed behövs varken
GDAL/fiona eller nätverksåtkomst vid bygget.
"""

import json
import os
import sqlite3
import struct
import sys
import time
import urllib.error
import urllib.request

ORION_URL = os.environ.get("ORION_URL", "http://localhost:2026").rstrip("/")
GPKG = os.environ.get("GPKG", "data/dbsvadaexample.gpkg")
BATCH = int(os.environ.get("BATCH", "50"))

# NGSI-LD-entiteternas id-prefix (Smart Data Models-mönster).
ID_PREFIX = "urn:ngsi-ld:SewerOverflowWeir:"

# GeoPackage-headern (OGC 12-128r15): "GP" + version + flaggor + srs_id,
# därefter en valfri envelope vars storlek ges av flaggornas indikatorbitar.
ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def parse_gpkg_point(blob):
    """Plockar ut (lon, lat) ur en GeoPackage-blob med MultiPoint-geometri.

    Gotcha från PoC 1: geometrierna är MULTIPOINT (WKB-typ 4) med exakt en
    punkt, och den inre punkten börjar på offset 9 räknat från WKB-starten
    (1 byte byteordning + 4 byte geometrityp + 4 byte antal punkter). Den
    inre punkten har i sin tur egen byteordning + typ (5 byte) före
    koordinaterna, som alltså ligger på offset 14.
    """
    if blob[0:2] != b"GP":
        raise ValueError("inte en GeoPackage-blob")
    flags = blob[3]
    little = flags & 0x01
    endian = "<" if little else ">"
    envelope = ENVELOPE_BYTES[(flags >> 1) & 0x07]
    srs_id = struct.unpack_from(endian + "i", blob, 4)[0]

    wkb = 8 + envelope
    _bo, geom_type, n_points = struct.unpack_from(endian + "BII", blob, wkb)
    if geom_type != 4:
        raise ValueError("förväntade MultiPoint (WKB-typ 4), fick %d" % geom_type)
    if n_points != 1:
        raise ValueError("förväntade exakt en punkt, fick %d" % n_points)

    _sub_bo, sub_type = struct.unpack_from(endian + "BI", blob, wkb + 9)
    if sub_type != 1:
        raise ValueError("inre geometri är inte Point, fick %d" % sub_type)
    lon, lat = struct.unpack_from(endian + "dd", blob, wkb + 14)
    return lon, lat, srs_id


def prop(value):
    return {"type": "Property", "value": value}


def las_brunnar(sokvag):
    """Returnerar (entiteter, srs_ids) ur gpkg:n."""
    con = sqlite3.connect(sokvag)
    try:
        recipienter = {r[0]: r[1] for r in con.execute("SELECT id, name FROM Recipient")}
        utslappspunkter = {r[0]: r[1] for r in con.execute("SELECT id, name FROM Outlet")}

        cur = con.execute(
            'SELECT weirid, name, description, location, "group", type, s1_ts, '
            "regionid, recipientid, outletid FROM Weirs ORDER BY weirid"
        )
        entiteter, srs_ids = [], set()
        for (weirid, namn, beskrivning, blob, grupp, typ, serie,
             regionid, recipientid, outletid) in cur:
            lon, lat, srs_id = parse_gpkg_point(blob)
            srs_ids.add(srs_id)
            if lon == 0 and lat == 0:
                raise ValueError("brunn %s hamnade på nollön [0,0]" % weirid)

            entitet = {
                "id": ID_PREFIX + weirid,
                "type": "SewerOverflowWeir",
                # location är WGS84/CRS84 enligt NGSI-LD. Källan är EPSG:4619
                # (SWEREF99 geografisk, lon/lat i grader) som för Göteborg
                # skiljer sig från WGS84 med långt under en meter – medveten
                # förenkling, ursprungs-SRS bevaras i sourceSrs nedan.
                "location": {
                    "type": "GeoProperty",
                    "value": {"type": "Point", "coordinates": [lon, lat]},
                },
                "name": prop(namn),
                "weirId": prop(weirid),
                "category": prop(grupp),
                "weirType": prop(typ),
                # seriesRef kopplar brunnen till FCF:s tidsserie – används av
                # senare steg för att matcha mätvärden mot rätt brunn.
                "seriesRef": prop(serie),
                "regionId": prop(regionid),
                "sourceSrs": prop("EPSG:%d" % srs_id),
                "source": prop("dbsvadaexample.gpkg"),
                "dataProvider": prop("DHI – Future City Flow (SVADA PoC)"),
            }
            if beskrivning:
                entitet["description"] = prop(beskrivning)
            if recipienter.get(recipientid):
                entitet["recipient"] = prop(recipienter[recipientid])
            if utslappspunkter.get(outletid):
                entitet["outlet"] = prop(utslappspunkter[outletid])
            entiteter.append(entitet)
        return entiteter, srs_ids
    finally:
        con.close()


def http(metod, sokvag, kropp=None):
    # GOTCHA: ensure_ascii=False är nödvändigt. Med Pythons default (True)
    # skickas "Krokängsparken" som "Krokängsparken", och Orion-LD 1.6.0
    # avkodar INTE \uXXXX-escaper utan lagrar dem tecken för tecken – brunnen
    # hette då bokstavligen "Krokängsparken" i CIP:en.
    data = (json.dumps(kropp, ensure_ascii=False).encode("utf-8")
            if kropp is not None else None)
    req = urllib.request.Request(ORION_URL + sokvag, data=data, method=metod)
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as svar:
            return svar.status, svar.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as fel:
        return fel.code, fel.read().decode("utf-8", "replace")


def vanta_pa_orion(sekunder=120):
    for _ in range(sekunder):
        try:
            status, _ = http("GET", "/ngsi-ld/ex/v1/version")
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    print("ladda_brunnar: gpkg=%s orion=%s" % (GPKG, ORION_URL))
    entiteter, srs_ids = las_brunnar(GPKG)
    print("Läste %d brunnar ur gpkg:n (SRS: %s)"
          % (len(entiteter), ", ".join("EPSG:%d" % s for s in sorted(srs_ids))))

    if not vanta_pa_orion():
        print("FEL: orion-stad svarar inte på %s" % ORION_URL, file=sys.stderr)
        return 1

    # Batch-upsert (options=replace) => idempotent omkörning utan dubbletter.
    skrivna = 0
    for i in range(0, len(entiteter), BATCH):
        del_ = entiteter[i:i + BATCH]
        status, kropp = http(
            "POST", "/ngsi-ld/v1/entityOperations/upsert?options=replace", del_)
        if status not in (200, 201, 204):
            print("FEL: upsert gav HTTP %d: %s" % (status, kropp[:500]), file=sys.stderr)
            return 1
        skrivna += len(del_)
        print("  upsert %d/%d -> HTTP %d" % (skrivna, len(entiteter), status))

    status, kropp = http(
        "GET", "/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000&count=true")
    antal = len(json.loads(kropp)) if status == 200 else -1
    print("orion-stad innehåller nu %d SewerOverflowWeir-entiteter" % antal)

    krok = [e for e in entiteter if e["id"].endswith("4526")]
    if krok:
        print("Krokängsparken (%s): %s"
              % (krok[0]["id"], krok[0]["location"]["value"]["coordinates"]))

    return 0 if antal == len(entiteter) else 1


if __name__ == "__main__":
    sys.exit(main())
