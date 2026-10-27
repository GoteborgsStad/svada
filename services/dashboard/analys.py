#!/usr/bin/env python3
"""Steg 6 – staden använder data: inspektionsprioritering.

Frågan vyn svarar på: "Vilka bräddbrunnar bör staden inspektera först?"

Regeln är medvetet enkel och går att förklara med en mening: rangordna brunnarna efter
modellerad bräddvolym (m³); markera de TOPP N som "inspektera". N kan ändras. Bräddtiden är
inte ett kriterium: i modellen är den lika för alla brunnar, och vyn säger det.

Två lägen visar varför avtalet och klassningen spelar roll:
  * B (öppen, utan brunns-GIS): rangordning per brunn utan position, och per utsläppspunkt och
    mottagande vattendrag (recipient). Kräver inget avtal.
  * A (skyddad, med brunns-GIS): rangordning per brunn MED position, så att brunnarna kan läggas
    på en karta. Läsningen går med en nyckel som staden får genom att visa ett GÄLLANDE avtals
    id. Hävs avtalet nekar gatewayen, och vyn säger det i klartext. Hård regel 7 gäller:
    kontrollrummet stoppar inget själv, det är stadens gateway som nekar.

Allt här är LÄSNINGAR mot stadens egen plattform (orion-stad via stad-gateway) och stadens
avtalsregister. Ingenting flyttar data förbi kontraktet.
"""

import json

import kallor
import sessioner
from kallor import KallFel, kallfel

# Brunnsregistret (namn, mottagare, utsläppspunkt, geometri) och en modellentitet per distribution (värdena).
REGISTERTYP = "SewerOverflowWeir"
MODELLTYP = {"A": "SewerOverflowModelA", "B": "SewerOverflowModelB"}
STANDARD_TOPP = 10
MAX_BRUNNAR = 200


def _hamta_typ(huvud, typ):
    svar = kallor.anrop(
        kallor.url("orion_stad", "/ngsi-ld/v1/entities?type=%s&limit=%d&options=keyValues"
                   % (typ, MAX_BRUNNAR)),
        headers=huvud, timeout=30)
    if not isinstance(svar, list):
        raise kallfel("kallfel.analys_svar", svar=str(svar)[:120])
    return svar


def _brunns_id(entitet):
    return str(entitet.get("id", "")).rsplit(":", 1)[-1]


def _hamta_entiteter(huvud, dist):
    """Modellentiteterna för en distribution, var och en ihopfogad med sin brunn i registret.

    A och B ligger på varsin entitetstyp: en hävning av A rör inte B, och läget B läser aldrig A:s entiteter.
    Brunnens egen position finns bara i registret och läses bara i läge A (se _fran_entitet).
    """
    modell = _hamta_typ(huvud, MODELLTYP[dist])
    if not modell:
        return []
    register = {_brunns_id(e): e for e in _hamta_typ(huvud, REGISTERTYP)}
    return [(m, register.get(_brunns_id(m)) or {}) for m in modell]


def senaste_gallande_a_avtal():
    """Det senaste GÄLLANDE avtalet om A i stadens avtalsregister (eller None) och det senaste hävda. Med en session (sessioner.py)
    bara besökarens egna avtal: någon annans avtal gäller inte för den här besökarens analys."""
    reg = kallor.avtalsregister().get("avtal", [])
    s = sessioner.aktuell()
    a = [x for x in reg if x.get("distribution") == "A" and (s is None or x.get("id") in s.avtal)]
    gallande = [x for x in a if x.get("status") == "GALLANDE"]
    havda = [x for x in a if x.get("status") in ("HAVT", "UTGANGET")]
    return (gallande[0] if gallande else None), (havda[0] if havda else None)


def _nyckel_for_avtal(avtals_id):
    """Växlar avtalets id mot en åtkomstnyckel hos stadens gateway (nekas om avtalet inte gäller)."""
    svar = kallor.anrop(kallor.url("orion_stad", "/auktorisation"), "POST",
                        {"contractAgreementId": avtals_id}, timeout=20)
    nyckel = svar.get("token")
    if not nyckel:
        raise kallfel("kallfel.analys_nyckel", svar=str(svar)[:120])
    return {"Authorization": "Bearer %s" % nyckel}


def _fran_entitet(par, med_position):
    e, brunn = par
    prov = e.get("provenance") or {}
    rad = {
        "id": _brunns_id(e),
        "namn": _rent_namn(brunn.get("name")),
        "volymM3": float(e.get("overflowVolumeM3") or 0.0),
        "toppM3S": float(e.get("overflowPeakM3S") or 0.0),
        "nivaM": float(e.get("waterLevelMaxM") or 0.0),
        "tidMin": float(e.get("overflowDurationMin") or 0.0),
        "recipient": brunn.get("recipient"),
        # Stadens plattform lagrar utsläppspunktens NAMN (inte dess koordinat).
        "utslapp": (brunn.get("outlet") if isinstance(brunn.get("outlet"), str)
                    else (brunn.get("outlet") or {}).get("name")),
        "batch": prov.get("batchId"),
        "avtal": prov.get("contractAgreementId"),
        "distribution": prov.get("distribution"),
        "klass": prov.get("informationClass"),
    }
    if med_position:
        rad["position"] = (brunn.get("location") or {}).get("coordinates")
    return rad


def _rent_namn(namn):
    """Brunnsnamnet ur registret kan bära radbrytningar (källdatat); en rad i tabellen får bara en rad."""
    return " ".join(str(namn).split()) if namn else namn


def prioritering(lage="b", topp=STANDARD_TOPP):
    """Bygger analysen. Kastar aldrig för ett avtal som inte gäller (det är ett giltigt utfall)."""
    lage = "a" if str(lage).lower() == "a" else "b"
    try:
        topp = max(1, min(int(topp), MAX_BRUNNAR))
    except (TypeError, ValueError):
        topp = STANDARD_TOPP
    ut = {"lage": lage.upper(), "topp": topp, "blockerad": None, "rader": [], "perRecipient": [],
          "avtal": None}

    if lage == "a":
        gallande, havt = senaste_gallande_a_avtal()
        if not gallande:
            ut["blockerad"] = {
                "orsak": ("inget-gallande-avtal" if not havt else
                          "avtal-utgatt" if havt.get("status") == "UTGANGET" else "avtal-havt"),
                "giltigTill": (havt or {}).get("giltigTill"),
                "avtal": (havt or {}).get("id"),
                "havning": (havt or {}).get("havning"),
            }
            return ut
        ut["avtal"] = {"id": gallande.get("id"), "status": gallande.get("status"),
                       "url": gallande.get("url")}
        try:
            huvud = _nyckel_for_avtal(gallande["id"])
            entiteter = _hamta_entiteter(huvud, "A")
        except KallFel as fel:
            # Gatewayen nekade (t.ex. hävt mellan registerläsningen och anropet).
            ut["blockerad"] = {"orsak": "nekad-av-gatewayen", "avtal": gallande.get("id"),
                               "detalj": str(fel)[:300]}
            return ut
    else:
        entiteter = _hamta_entiteter(kallor.STAD_GATEWAY_HUVUD, "B")

    if not entiteter:
        # Ingen leverans av den här distributionen har kommit in: nollor vore inga mätningar.
        ut["blockerad"] = {"orsak": "no-delivery", "distribution": lage.upper()}
        return ut
    rader = [_fran_entitet(e, med_position=(lage == "a")) for e in entiteter]
    s = sessioner.aktuell()
    if s is not None:                    # datat är gemensamt, men en annan besökares avtal ska inte synas (id eller länk)
        for r in rader:
            if r.get("avtal") not in s.avtal:
                r["avtal"] = None
    rader.sort(key=lambda r: (-r["volymM3"], r["id"]))
    for i, r in enumerate(rader, 1):
        r["rang"] = i
        r["inspektera"] = i <= topp and r["volymM3"] > 0
    ut["rader"] = rader

    per = {}
    for r in rader:
        k = r["recipient"] or "–"
        p = per.setdefault(k, {"recipient": k, "volymM3": 0.0, "brunnar": 0, "utslapp": set()})
        p["volymM3"] += r["volymM3"]
        p["brunnar"] += 1
        if r["utslapp"]:
            p["utslapp"].add(r["utslapp"])
    ut["perRecipient"] = sorted(
        ({"recipient": p["recipient"], "volymM3": round(p["volymM3"], 1), "brunnar": p["brunnar"],
          "utslapp": sorted(p["utslapp"])} for p in per.values()),
        key=lambda p: -p["volymM3"])

    # Ursprunget: vanligaste avtal/batch/distribution bland raderna.
    def vanligast(falt):
        antal = {}
        for r in rader:
            v = r.get(falt)
            if v:
                antal[v] = antal.get(v, 0) + 1
        return max(antal, key=antal.get) if antal else None
    ut["ursprung"] = {"avtal": vanligast("avtal"), "batch": vanligast("batch"),
                      "distribution": vanligast("distribution"), "klass": vanligast("klass")}
    ut["sammanfattning"] = {
        "brunnar": len(rader),
        "braddar": sum(1 for r in rader if r["volymM3"] > 0),
        "totalVolymM3": round(sum(r["volymM3"] for r in rader), 1),
        "hogstaVolymM3": rader[0]["volymM3"] if rader else 0.0,
        "samtligaTidLika": len({r["tidMin"] for r in rader if r["volymM3"] > 0}) <= 1,
    }
    return ut


def samma_brunn(brunn=None):
    """Steg 6, webinariet 2026-10 (punkt 3): samma brunn i B och A sida vid sida. Varje sida läses som i
    prioritering(): B öppet utan position, A bara med ett gällande avtal (annars samma blockerad-post som analysen).
    Ingen egen åtkomstlogik här, så att jämförelsen aldrig visar mer än analysen själv."""
    brunn = brunn or _brunns_id({"id": kallor.BRUNN_ID})
    ut = {"brunn": brunn}
    for lage in ("b", "a"):
        svar = prioritering(lage, MAX_BRUNNAR)
        rad = next((r for r in svar["rader"] if r["id"] == brunn), None)
        ut[lage.upper()] = {"rad": rad, "blockerad": svar["blockerad"], "avtal": svar.get("avtal")}
    return ut


def sammanfatta_for_steg():
    """Detaljrader för steg 6 (får inte kasta – ett dött led ska visa sitt fel)."""
    b = prioritering("b")
    s = b.get("sammanfattning") or {}
    gallande, havt = senaste_gallande_a_avtal()
    return [
        ("Brunnar i stadens plattform", s.get("brunnar")),
        ("Brunnar som bräddar", s.get("braddar")),
        ("Total bräddvolym (m³)", s.get("totalVolymM3")),
        ("Högsta bräddvolym (m³)", s.get("hogstaVolymM3")),
        ("Gällande avtal om A", (gallande or {}).get("id") or "inget"),
    ]


def exempelrad():
    """En rad ur prioriteringen, med ursprung – för stegets exempelruta."""
    b = prioritering("b", 1)
    if not b["rader"]:
        raise kallfel("kallfel.inga_brunnar", steg=4)
    return json.dumps(b["rader"][0], indent=2, ensure_ascii=False)
