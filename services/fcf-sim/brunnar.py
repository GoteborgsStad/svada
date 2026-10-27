#!/usr/bin/env python3
"""Brunnsregistret: läser de 91 bräddbrunnarna (+ utsläppspunkter och
recipienter) ur dbsvadaexample.gpkg.

Samma WKB-parsning som services/ladda_brunnar/ladda_brunnar.py –
gpkg är en SQLite-databas och geometrierna är MultiPoint (WKB-typ 4) med
exakt en punkt. Ingen GDAL/fiona behövs, bara standardbiblioteket.

Skillnad mot ladda_brunnar.py: här läses även utsläppspunktens GEOMETRI, eftersom
Distribution B behåller utsläppspunkt + recipient men tappar brunnens egen
position. Recipienternas location är NULL i hela testdatat, så recipienten bärs som namn.
"""

import sqlite3
import struct

# GeoPackage-headern (OGC 12-128r15): "GP" + version + flaggor + srs_id,
# därefter en valfri envelope vars storlek ges av flaggornas indikatorbitar.
ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def parse_gpkg_point(blob):
    """Plockar ut (lon, lat, srs_id) ur en GeoPackage-blob med MultiPoint.

    Den inre punkten börjar på offset 9 från WKB-starten (1 byte byteordning
    + 4 byte geometrityp + 4 byte antal punkter) och har i sin tur egen
    byteordning + typ (5 byte) före koordinaterna – alltså offset 14.
    """
    if blob[0:2] != b"GP":
        raise ValueError("inte en GeoPackage-blob")
    flags = blob[3]
    endian = "<" if flags & 0x01 else ">"
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


def punkt(lon, lat):
    """GeoJSON-punkt (samma form som NGSI-LD:s GeoProperty-värde)."""
    return {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]}


def las_brunnar(sokvag):
    """Returnerar listan av brunnar sorterade på weirId.

    Varje brunn är en dict med både det som får finnas i Distribution B och
    det som ENDAST får finnas i A (nyckeln "location" + "sourceSrs").
    """
    con = sqlite3.connect(sokvag)
    try:
        recipienter = {r[0]: r[1] for r in con.execute(
            "SELECT id, name FROM Recipient")}
        utslappspunkter = {}
        for oid, namn, blob in con.execute(
                "SELECT id, name, location FROM Outlet"):
            plats = None
            if blob:
                lon, lat, _srs = parse_gpkg_point(blob)
                plats = punkt(lon, lat)
            utslappspunkter[oid] = {"name": namn, "location": plats}

        brunnar = []
        cur = con.execute(
            'SELECT weirid, name, description, location, "group", type, s1_ts, '
            "regionid, recipientid, outletid FROM Weirs ORDER BY weirid"
        )
        for (weirid, namn, beskrivning, blob, grupp, typ, serie,
             regionid, recipientid, outletid) in cur:
            lon, lat, srs_id = parse_gpkg_point(blob)
            if lon == 0 and lat == 0:
                raise ValueError("brunn %s hamnade på nollön [0,0]" % weirid)
            brunnar.append({
                "weirId": weirid,
                "weirName": namn,
                "description": beskrivning,
                "category": grupp,
                "weirType": typ,
                "seriesRef": serie,
                "regionId": regionid,
                # --- ENDAST Distribution A ---------------------------------
                "location": punkt(lon, lat),
                "sourceSrs": "EPSG:%d" % srs_id,
                # --- Får finnas i BÅDA distributionerna ---------------------
                "outlet": utslappspunkter.get(outletid, {"name": None,
                                                         "location": None}),
                "recipient": recipienter.get(recipientid),
            })
        return brunnar
    finally:
        con.close()
