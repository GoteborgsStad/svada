#!/usr/bin/env python3
"""KONCEPT: docs/koncept/08-proveniens.md

Transformation till NGSI-LD + skrivning till stadens broker (orion-stad).

En post ur dataprodukten "Modellerad bräddata" blir en egen entitet per distribution:
`urn:ngsi-ld:SewerOverflowModelB:<weirId>` (öppna data) eller `urn:ngsi-ld:SewerOverflowModelA:<weirId>` (skyddade).
Brunnsregistret (`SewerOverflowWeir`, 91 stycken: namn, mottagare, geometri) rörs inte av leveranserna;
modellentiteten pekar på sin brunn med relationen `refWeir`. Distributionerna delar alltså inga attribut: en hävning
av A berör bara A:s entiteter, B:s värden och tidsserie består, och den publika tidsserien kan begränsas till B.

Två saker gör skrivningen spårbar:

  * varje mätetal bär `unitCode` (UN/CEFACT, ur kuvertets unitCodes) och
    `observedAt` = det modellerade dygnets slut. observedAt är det som gör
    att Orion-LD:s TRoE-lager (och därmed Mintaka) bygger en TIDSSERIE i
    stället för att bara skriva över nuläget – testfall 4c.6.
  * attributet `provenance` bär avtals-ID, dataprodukt, distribution,
    batch och tidpunkt – testfall 4c.2. Proveniensen är hela poängen: i
    CIP:en ska det alltid gå att svara på VILKET kontrakt en uppgift kom in
    under, inte bara vad den innehåller.

Skrivningen görs med NGSI-LD:s batch-upsert i läget `options=update`, som skapar entiteten om den saknas och annars
UPPDATERAR de attribut vi skickar.
"""

import datetime as dt
import http.client
import json
import urllib.error
import urllib.request

REGISTER_PREFIX = "urn:ngsi-ld:SewerOverflowWeir:"          # brunnsregistret (orört av leveranserna)
ENTITETSTYP_PER_DIST = {"A": "SewerOverflowModelA", "B": "SewerOverflowModelB"}


def entitetstyp(dist):
    return ENTITETSTYP_PER_DIST[str(dist).upper()]


def entitets_id(dist, weir_id):
    return "urn:ngsi-ld:%s:%s" % (entitetstyp(dist), weir_id)

# Mätetal som skrivs som Property med unitCode + observedAt.
MATETAL = ("inflowMeanM3S", "inflowPeakM3S", "inflowVolumeM3",
           "overflowVolumeM3", "overflowPeakM3S", "overflowDurationMin",
           "waterLevelMaxM")

# Beskrivande fält som följer med som vanliga Property:er.
BESKRIVANDE = ("modelledDay", "periodStart", "periodEnd", "dataSource",
               "modelVersion", "overflowStart", "overflowEnd",
               "measuredCoverage")


def _prop(varde, observed_at=None, unit_code=None):
    attr = {"type": "Property", "value": varde}
    if unit_code:
        attr["unitCode"] = unit_code
    if observed_at:
        attr["observedAt"] = observed_at
    return attr


def till_entiteter(kuvert, poster, proveniens, dist):
    """Bygger NGSI-LD-entiteter (upsert-form) ur en leverans, en entitetstyp per distribution."""
    enheter = {}
    entiteter = []
    for post in poster:
        enheter = post.get("unitCodes", enheter)
        # Dygnets slut = tidpunkten modellresultatet gäller för.
        observed_at = post.get("periodEnd")

        entitet = {
            "id": entitets_id(dist, post["weirId"]),
            "type": entitetstyp(dist),
            "refWeir": {"type": "Relationship", "object": REGISTER_PREFIX + post["weirId"]},
            "provenance": _prop(dict(proveniens), observed_at),
        }
        for falt in MATETAL:
            if falt in post:
                entitet[falt] = _prop(post[falt], observed_at,
                                      enheter.get(falt))
        for falt in BESKRIVANDE:
            if post.get(falt) is not None:
                entitet[falt] = _prop(post[falt], observed_at)
        entiteter.append(entitet)
    return entiteter


def bygg_proveniens(kuvert, avtals_id, dist, transfer_id=None, avtal_url=None):
    """Proveniensen som varje berikad entitet bär (testfall 4c.2)."""
    proveniens = {
        # Avtals-ID:t – kopplingen tillbaka till kontraktsförhandlingen i
        # EDC. För Distribution A finns det bara efter KoV-beslut.
        "contractAgreementId": avtals_id,
        # Löstbar adress till avtalet i stadens avtalsregister (dashboarden).
        "contractAgreementUrl": avtal_url,
        "dataset": kuvert.get("dataset"),
        "distribution": dist.upper(),
        "distributionId": kuvert.get("distributionId"),
        "batchId": kuvert.get("batchId"),
        "producedAt": kuvert.get("producedAt"),
        "ingestedAt": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "accessRights": kuvert.get("accessRights"),
        "informationClass": kuvert.get("informationClass"),
        "license": kuvert.get("license"),
        "publisher": kuvert.get("publisher"),
        "receivedVia": "Eclipse EDC transfer (Dataspace Protocol)",
    }
    if transfer_id:
        proveniens["transferProcessId"] = transfer_id
    return {n: v for n, v in proveniens.items() if v is not None}


class OrionFel(Exception):
    pass


def skriv(orion_url, entiteter, batchstorlek=50, tenant=None):
    """Batch-upsert mot orion-stad. Returnerar antal skrivna entiteter."""
    skrivna = 0
    for i in range(0, len(entiteter), batchstorlek):
        del_ = entiteter[i:i + batchstorlek]
        # GOTCHA: ensure_ascii=False – Orion-LD 1.6.0 avkodar inte
        # \uXXXX-escaper utan lagrar dem tecken för tecken.
        data = json.dumps(del_, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            orion_url + "/ngsi-ld/v1/entityOperations/upsert?options=update",
            data=data, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.add_header("Accept", "application/json")
        if tenant:
            req.add_header("NGSILD-Tenant", tenant)
        try:
            with urllib.request.urlopen(req, timeout=60) as svar:
                if svar.status == 207:      # blandat svar: godtas bara om inga poster felade
                    try:
                        svarskropp = json.loads(svar.read().decode("utf-8", "replace") or "{}")
                    except (ValueError, http.client.HTTPException) as fel:
                        raise OrionFel("HTTP 207 med oläsbar kropp: %s" % fel)
                    if not isinstance(svarskropp, dict):
                        raise OrionFel("HTTP 207 med oväntad kropp: %s" % str(svarskropp)[:200])
                    if svarskropp.get("errors"):
                        raise OrionFel("HTTP 207: %s" % str(svarskropp["errors"])[:400])
                elif svar.status not in (200, 201, 204):
                    raise OrionFel("HTTP %d" % svar.status)
        except urllib.error.HTTPError as fel:
            raise OrionFel("HTTP %d: %s" % (
                fel.code, fel.read().decode("utf-8", "replace")[:400]))
        except (urllib.error.URLError, OSError, TimeoutError) as fel:
            raise OrionFel(str(fel))
        skrivna += len(del_)
    return skrivna
