#!/usr/bin/env python3
"""KONCEPT: docs/koncept/04-informationsklassning.md

Dataprodukten "Modellerad bräddata" i två distributioner.

  A – K1R1T1, full: brunnens GIS-position ingår. Får ej spridas/publiceras
      och kräver KoV-godkännande (verkställs på PROVIDER-sidan, DSP:s
      arbetsdelning: providern äger policyverkställningen). accessRights = non-public.
  B – K0R1T1, GIS-reducerad: brunnens position och dess ursprungs-SRS är
      BORTTAGNA. Utsläppspunkt (med koordinat) och recipient ligger kvar –
      det är den upplösning som får bli öppna data. accessRights = public.

Distribution B härleds ALLTID ur A genom att plocka bort de känsliga
nycklarna (en enda kodväg – ingen risk att ett nytt fält smyger in i B av
misstag). Fälten som får försvinna listas i KANSLIGA_FALT.

Felinjektionsläget är avsiktligt "tyst": nyttolasten
innehåller INGEN flagga om att den är manipulerad. Ingest-/policylagret ska upptäcka felen själv, inte bli tillsagt.
"""

import copy
import datetime as dt

from modell import (MODELLVERSION, PUNKTER_PER_DYGN, aggregera,
                    serie_for_brunn)

# Nycklar i en post som utgör BRUNNENS GIS – enbart dessa skiljer A från B.
KANSLIGA_FALT = ("location", "sourceSrs")

DATASET = "Modellerad bräddata"

DIST_META = {
    "a": {
        "distributionId": "modellerad-bradddata-a",
        "titel": "Modellerad bräddata – A (fullständig, med brunns-GIS)",
        "accessRights": "non-public",
        "informationsklass": "K1R1T1",
        # Formell text (avtalsvillkor) är engelsk i båda vyerna; beskrivande text är svensk.
        "licens": "Agreement DHI–City of Gothenburg (M2); requires KoV approval",
        "villkor": ["use", "prohibition: distribute", "prohibition: publish",
                    "obligation: approval from KoV (Data Rights Holder)"],
    },
    "b": {
        "distributionId": "modellerad-bradddata-b",
        "titel": "Modellerad bräddata – B (brunns-GIS borttagen)",
        "accessRights": "public",
        "informationsklass": "K0R1T1",
        "licens": "CC BY 4.0",
        "villkor": ["use", "distribute", "publish",
                    "duty: attribution (DHI / Göteborgs Stad)"],
    },
}

# Enheterna som posternas mätetal uttrycks i (UN/CEFACT där det finns kod).
ENHETER = {
    "inflowMeanM3S": "MQS", "inflowPeakM3S": "MQS", "inflowVolumeM3": "MTQ",
    "overflowVolumeM3": "MTQ", "overflowPeakM3S": "MQS",
    "overflowDurationMin": "MIN", "waterLevelMaxM": "MTR",
}


def bygg_poster(brunnar, bas, batch_index, dygn, matt_weir_id, tackning=0):
    """Bygger en post per brunn i A-form (dvs. inklusive brunns-GIS).

    matt_weir_id = brunnen vars serie kommer från riktiga mätvärden (None om
    batchen körs på reservmönstret); tackning = antal mätta dygnspositioner.
    """
    dygn_start = dt.datetime.combine(dygn, dt.time(0, 0),
                                     tzinfo=dt.timezone.utc)
    poster = []
    for brunn in brunnar:
        serie, profil = serie_for_brunn(brunn, bas, batch_index, matt_weir_id)
        agg = aggregera(serie, dygn_start)
        matt = brunn["weirId"] == matt_weir_id
        post = {
            "weirId": brunn["weirId"],
            "weirName": brunn["weirName"],
            "regionId": brunn["regionId"],
            "category": brunn["category"],
            "weirType": brunn["weirType"],
            "seriesRef": brunn["seriesRef"],
            # --- brunnens GIS: ENDAST Distribution A ---------------------
            "location": brunn["location"],
            "sourceSrs": brunn["sourceSrs"],
            # --- grövre geografi: finns i BÅDA distributionerna -----------
            "outlet": brunn["outlet"],
            "recipient": brunn["recipient"],
            # --- modellresultatet ----------------------------------------
            "modelledDay": dygn.isoformat(),
            "periodStart": dygn_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "periodEnd": (dygn_start + dt.timedelta(days=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "dataSource": ("measured" if matt and tackning >= PUNKTER_PER_DYGN
                           else "measured-partial" if matt
                           else "modelled-synthetic"),
            "modelVersion": MODELLVERSION,
            "unitCodes": ENHETER,
        }
        post.update(agg)
        if matt:
            # Hur stor del av dygnet som faktiskt vilar på mätvärden.
            post["measuredCoverage"] = round(tackning / PUNKTER_PER_DYGN, 3)
        else:
            # Skalfaktorerna redovisas öppet: det är syntetiskt underlag och
            # ska inte kunna förväxlas med mätdata.
            post["syntheticScale"] = profil["flodeSkala"]
            post["syntheticOverflowScale"] = profil["braddSkala"]
        poster.append(post)
    return poster


def till_b(poster):
    """Distribution B: samma poster utan brunnens GIS."""
    reducerade = []
    for post in poster:
        kopia = {k: v for k, v in post.items() if k not in KANSLIGA_FALT}
        reducerade.append(kopia)
    return reducerade


def kuvert(dist, batch, poster):
    """Bygger svarskuvertet för en distribution."""
    meta = DIST_META[dist]
    return {
        "dataset": DATASET,
        "distribution": dist.upper(),
        "distributionId": meta["distributionId"],
        "title": meta["titel"],
        "accessRights": meta["accessRights"],
        "informationClass": meta["informationsklass"],
        "license": meta["licens"],
        "odrlTerms": meta["villkor"],
        "publisher": "DHI – Future City Flow (SVADA PoC)",
        "batchId": batch["batchId"],
        "batchClock": batch["batchClock"],
        "producedAt": batch["producedAt"],
        "modelledDay": batch["modelledDay"],
        "modelVersion": MODELLVERSION,
        "measurementSource": batch["measurementSource"],
        "recordCount": len(poster),
        "records": poster,
    }


# ---------------------------------------------------------------------------
# Felinjektion. Appliceras vid UTLÄMNING, aldrig i lagret –
# batcherna i minnet förblir korrekta, så felen kan slås av igen utan omkörning.
# ---------------------------------------------------------------------------

# Schemadriften döper om två fält – precis det som händer när en
# modellversion byter namnkonvention utan att avtalet uppdateras.
SCHEMADRIFT_NYA_NAMN = {
    "overflowVolumeM3": "bradd_volym_m3",
    "inflowMeanM3S": "tillrinning_medel_m3s",
}
# "Saknade parametrar": fält som avtalet/schemat kräver men som uteblir.
SAKNADE_FALT = ("overflowDurationMin", "unitCodes")


def tillampa_felinjektion(svar, dist, fel, gis_karta):
    """Returnerar en manipulerad kopia av kuvertet enligt aktiva felflaggor.

    gis_karta = {weirId: {"location": ..., "sourceSrs": ...}} ur brunnsregistret
    och används bara av avtalsbrottsläget (gis_i_b).
    """
    if not any(fel.values()):
        return svar
    svar = copy.deepcopy(svar)
    poster = svar["records"]

    if fel.get("schemadrift"):
        for i, post in enumerate(poster):
            for gammalt, nytt in SCHEMADRIFT_NYA_NAMN.items():
                if gammalt in post:
                    post[nytt] = post.pop(gammalt)
            poster[i] = post

    if fel.get("saknade_parametrar"):
        for post in poster:
            for falt in SAKNADE_FALT:
                post.pop(falt, None)

    # AVTALSBROTT: brunns-GIS läggs tillbaka i B. Ska fångas av ingest (validering av mottagen leverans).
    if fel.get("gis_i_b") and dist == "b":
        for post in poster:
            kalla = gis_karta.get(post["weirId"])
            if kalla:
                post["location"] = kalla["location"]
                post["sourceSrs"] = kalla["sourceSrs"]

    svar["recordCount"] = len(poster)
    return svar
