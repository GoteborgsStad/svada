#!/usr/bin/env python3
"""KONCEPT: docs/koncept/03-fcf-modellen.md

Bräddmodellen – "Future City Flow" i miniatyr.

MEDVETEN FÖRENKLING: riktiga FCF är en hydrodynamisk modell (MIKE+/MOUSE)
över hela ledningsnätet. Här körs en enkel glidande beräkning per brunn:

  tillrinning  = uppmätt/syntetiskt totalflöde (m³/s) genom brunnen
  bräddflöde   = uppmätt/syntetiskt spillflöde (m³/s) över krönet
  bräddvolym   = Σ bräddflöde · Δt            (Δt = 300 s, seriens upplösning)
  bräddtid     = antal punkter med bräddflöde > 0 · Δt
  vattennivå   = överfallshöjd över krönet ur rektangulär överfallsformel
                 Q = C · b · h^(3/2)  =>  h = (Q / (C · b))^(2/3)
                 (C = 1,7 SI för skarpkantat rektangulärt överfall)

Endast SSO1_01-4526 (Krokängsparken) har en riktig mätserie. De övriga 90
brunnarna får SYNTETISKA serier: samma mönster som Krokängsparken, roterat i
tiden och skalat med en brunnspecifik faktor som härleds DETERMINISTISKT ur
brunns-id:t (samma brunn ger samma faktor vid varje omstart – ingen slump,
så verifieringen blir reproducerbar). En dryg fjärdedel av brunnarna får
bräddfaktor 0, dvs. de bräddar inte alls under dygnet – annars vore
"91 bräddande brunnar varje dygn" en orimlig bild av nätet.
"""

import hashlib
import math

DT_S = 300                 # rådataseriens upplösning: 5 minuter
PUNKTER_PER_DYGN = 288     # 24 h / 5 min
C_OVERFALL = 1.7           # avbördningskoefficient, skarpkantat överfall (SI)
KRON_BREDD_M = 1.0         # antagen krönbredd, samma för alla brunnar i PoC:en

MODELLVERSION = "fcf-sim 1.0.0 / enkel-overfallsmodell"


def _hash_tal(text, salt):
    """Deterministiskt tal i [0,1) ur en sträng (ingen slump – se modulens
    docstring). random.seed() undveks eftersom Pythons slumpström inte är
    garanterad stabil mellan versioner."""
    h = hashlib.sha256(("%s|%s" % (salt, text)).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def brunnsprofil(weir_id):
    """Brunnspecifika modellparametrar (deterministiska)."""
    storlek = 0.25 + 2.25 * _hash_tal(weir_id, "storlek")     # 0,25–2,50
    braddbenagenhet = _hash_tal(weir_id, "bradd")
    fas = int(_hash_tal(weir_id, "fas") * PUNKTER_PER_DYGN)   # tidsförskjutning
    return {
        "flodeSkala": round(storlek, 4),
        # ~28 % av brunnarna bräddar inte alls detta dygn.
        "braddSkala": 0.0 if braddbenagenhet < 0.28 else round(
            storlek * (0.4 + 1.2 * braddbenagenhet), 4),
        "fas": fas,
    }


def basmonster():
    """Reservmönster när orion-dhi ännu inte levererat några mätvärden.

    Ett dygnsmönster med morgon-/kvällstopp och en nederbördsutlöst
    bräddhändelse på eftermiddagen. Används bara som fallback – normalt
    kommer basmönstret från den riktiga mätserien.
    """
    serie = []
    for i in range(PUNKTER_PER_DYGN):
        timme = i * DT_S / 3600.0
        spillvatten = 0.02 + 0.012 * math.sin((timme - 6) / 24 * 2 * math.pi)
        regn = 0.0
        if 13.0 <= timme <= 17.0:
            regn = 0.06 * math.sin((timme - 13.0) / 4.0 * math.pi) ** 2
        total = spillvatten + regn
        # Brädd först när flödet överstiger ledningens kapacitet.
        spill = max(0.0, total - 0.045)
        serie.append((round(total, 6), round(spill, 6)))
    return serie


def bas_fran_matvarden(punkter):
    """Bygger dygnsmönstret ur mätfönstret. Returnerar (serie, täckning).

    Basmönstret är ALLTID 288 punkter = ett helt dygn, och varje mätpunkt
    läggs in på sin EGNA klockposition (observedAt → index). Positioner som
    ännu saknar mätvärde får reservmönstrets värde.

    Varför inte bara upprepa fönstret: mätfönstret fylls på i uppspelningstakt
    och är i början bara några minuter långt. Upprepas ett sådant fragment
    över dygnet blir resultatet antingen "brädd dygnet runt" eller "noll
    brädd" beroende på var i serien uppspelningen råkar stå – båda felaktiga.
    Täckningsgraden redovisas i dataprodukten (measuredCoverage).
    """
    if not punkter:
        return None, 0
    serie = basmonster()
    index = set()
    for p in punkter[-PUNKTER_PER_DYGN:]:
        klockslag = p["observedAt"][11:19]          # "HH:MM:SS"
        try:
            h, m, _s = (int(x) for x in klockslag.split(":"))
        except ValueError:
            continue
        i = (h * 3600 + m * 60) // DT_S
        if 0 <= i < PUNKTER_PER_DYGN:
            serie[i] = (max(p["totalFlow"], 0.0), max(p["spillFlow"], 0.0))
            index.add(i)
    return serie, len(index)


def serie_for_brunn(brunn, bas, batch_index, matt_weir_id=None):
    """Brunnens serie för dygnet: mätt för 4526, annars skalat basmönster.

    Sensorbrunnen får basmönstret RÅTT – varken roterat eller skalat. Den är
    ju mätningen, och det är just den serien dashboarden jämför "mätt vs
    modellerat" mot.
    """
    if matt_weir_id and brunn["weirId"] == matt_weir_id:
        return list(bas), {"flodeSkala": 1.0, "braddSkala": 1.0, "fas": 0}

    profil = brunnsprofil(brunn["weirId"])
    # Varje ny batch roterar mönstret 3 h och skalas med en dagsfaktor. Rotationen ensam räcker inte: dygnets
    # summor och toppvärden ändras inte av att mönstret flyttas, så alla dygn fick samma volymer.
    skift = (profil["fas"] + batch_index * 36) % len(bas)
    roterad = bas[skift:] + bas[:skift]
    dag = 0.75 + 0.05 * ((batch_index * 7) % 11)   # 0,75 … 1,25, bestämd av batchens löpnummer
    return [(round(t * profil["flodeSkala"] * dag, 6),
             round(s * profil["braddSkala"] * dag, 6)) for t, s in roterad], profil


def _nivå(flode):
    """Överfallshöjd h (m) ur Q = C · b · h^(3/2)."""
    if flode <= 0:
        return 0.0
    return round((flode / (C_OVERFALL * KRON_BREDD_M)) ** (2.0 / 3.0), 4)


def aggregera(serie, dygn_start):
    """Dygnsaggregat ur en serie av (totalflöde, bräddflöde).

    dygn_start är en datetime (UTC) för seriens första punkt – bräddens
    start-/sluttid räknas ut ur punktindexen.
    """
    import datetime as dt

    antal = len(serie)
    total = [t for t, _ in serie]
    spill = [s for _, s in serie]
    braddpunkter = [i for i, s in enumerate(spill) if s > 0]

    def tid(i):
        return (dygn_start + dt.timedelta(seconds=i * DT_S)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    return {
        "inflowMeanM3S": round(sum(total) / antal, 6) if antal else 0.0,
        "inflowPeakM3S": round(max(total), 6) if antal else 0.0,
        "inflowVolumeM3": round(sum(total) * DT_S, 2),
        "overflowVolumeM3": round(sum(spill) * DT_S, 2),
        "overflowPeakM3S": round(max(spill), 6) if antal else 0.0,
        "overflowDurationMin": round(len(braddpunkter) * DT_S / 60.0, 1),
        "waterLevelMaxM": _nivå(max(spill) if antal else 0.0),
        "overflowStart": tid(braddpunkter[0]) if braddpunkter else None,
        "overflowEnd": tid(braddpunkter[-1] + 1) if braddpunkter else None,
        "sampleCount": antal,
    }
