#!/usr/bin/env python3
"""Bygger datamodellens utkast ur datamodell/utkast/termer.json (den enda källan).

UTKAST. Modellen är inte beslutad, inte överenskommen med dataägaren (KoV), leverantören (DHI) eller den tekniska
förvaltaren (Intraservice) och inte inskickad till Smart Data Models. Se docs/modell/README.md.

Skriver (alla genereras, redigera aldrig för hand):
  datamodell/utkast/context.jsonld            JSON-LD-kontext: varje term till en adress
  datamodell/utkast/schema.json               JSON Schema (nyckel-värde), profil A (hela modellen)
  datamodell/utkast/schema-profil-B.json      JSON Schema, profil B (utan position)
  datamodell/utkast/SPEC.md                   läsbar specifikation
  datamodell/utkast/mappings.sssom.tsv        kopplingar till andra termer (SSSOM)
  datamodell/utkast/examples/*                exempel
  docs/modell/termlista.md                    termlistan (låna, egen, knyt)

Användning, från repots rot:  python3 tools/bygg-datamodell.py            (skriver filerna)
                              python3 tools/bygg-datamodell.py --kontrollera   (felkod 1 om filerna är gamla)
"""
import json
import os
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
KALLA = os.path.join(ROT, "datamodell", "utkast", "termer.json")

BANNER_EN = ("**DRAFT v0.1. This is not a decided model.** It is a working draft that this demo uses and shows to visitors to learn what a "
             "model would need. It is a temporary model made for the PoC, not proposed as a general model. It is not agreed with the data owner, the provider or the City's technical custodian, and it is not submitted to "
             "Smart Data Models. Terms, names and addresses may change without notice. In the source files the addresses are placeholders; on the "
             "demo they point to the demo's own address. Both are provisional.")
BANNER_SV = ("**UTKAST v0.1. Detta är ingen beslutad modell.** Det är ett arbetsutkast som den här demon använder och visar för besökare för att lära sig "
             "vad en modell behöver. Det är en tillfällig modell framtagen för PoC:en, inte en föreslagen allmän modell. Det är inte överenskommet med dataägaren, leverantören eller stadens tekniska förvaltare och inte inskickat till "
             "Smart Data Models. Termer, namn och adresser kan ändras utan förvarning. I källfilerna är adresserna platshållare; i demon pekar de på "
             "demons egen adress. Båda är provisoriska.")

SCHEMATYP = {
    "number": {"type": "number"},
    "integer": {"type": "integer"},
    "string": {"type": "string"},
    "date": {"type": "string", "format": "date"},
    "date-time": {"type": "string", "format": "date-time"},
    "uri": {"type": "string", "format": "uri"},
    "object": {"type": "object"},
    "geometry": {"type": "object", "required": ["type", "coordinates"],
                 "properties": {"type": {"const": "Point"},
                                "coordinates": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3}}},
}


def las():
    return json.load(open(KALLA, encoding="utf-8"))


def iri(modell, term):
    """Termens adress: lånade termer behåller sin egen, övriga får utkastets platshållaradress."""
    for l in term["links"]:
        if term["origin"] == "lånad" and l["predicate"] == "skos:exactMatch":
            return l["target"]
    return modell["base"] + term["name"]


def kontext(d):
    m = d["model"]
    # JSON-LD 1.0 med enkla termer (ingen @version 1.1 och ingen nästlad kontext): Mintaka 0.7 kan inte läsa 1.1 och svarar 500.
    # Proveniensens medlemmar ligger i värdet på egenskapen provenance (vanlig JSON, inte egna attribut) och behöver ingen term i
    # kontexten; de är dokumenterade och slås upp på sina egna adresser.
    c = {"id": "@id", "type": "@type", "svada": m["base"]}
    for typ in m["entities"].values():
        if typ != "provenance":
            c[typ] = "svada:" + typ
    for t in d["terms"]:
        if t["entity"] == "provenance":
            continue
        elif t["origin"] == "lånad":
            c[t["name"]] = iri(m, t)
        else:
            c[t["name"]] = "svada:" + t["name"]
    c["provenance"] = "svada:provenance"
    # Statusen ligger utanför @context (JSON-LD ignorerar andra nycklar på toppnivån), så att ingen läser filen som en beslutad modell.
    return {"_status": "%s (version %s)" % (m["status"], m["version"].split("-")[0]), "@context": c}


def schema(d, profil):
    m = d["model"]
    egenskaper = {"id": {"type": "string", "pattern": "^urn:ngsi-ld:", "description": "Entity identifier (NGSI-LD URN)."},
                  "type": {"const": m["id"]}}
    krav = ["id", "type"]
    prov_e, prov_k = {}, []
    for t in d["terms"]:
        if t["entity"] == "provenance":
            namn = t["name"].split(".", 1)[1]
            prov_e[namn] = dict(SCHEMATYP[t["type"]], description=t["definition"])
            if t["required"]:
                prov_k.append(namn)
    for t in d["terms"]:
        if t["entity"] != "result" or t["name"] == "provenance":
            continue
        if profil not in t["profiles"]:
            egenskaper[t["name"]] = False
            continue
        s = dict(SCHEMATYP[t["type"]])
        s["description"] = t["definition"] + (" Unit: %s (%s)." % (t["unit"]["label"], t["unit"]["code"]) if t["unit"] else "")
        if "enum" in t:
            s["enum"] = t["enum"]
        egenskaper[t["name"]] = s
        if t["required"]:
            krav.append(t["name"])
    egenskaper["provenance"] = {"type": "object", "properties": prov_e, "required": prov_k, "additionalProperties": False,
                                "description": "Where the delivery came from and under which agreement."}
    krav.append("provenance")
    weir_e, weir_k = {"id": {"type": "string", "pattern": "^urn:ngsi-ld:SewerOverflowWeir:"}, "type": {"const": "SewerOverflowWeir"}}, ["id", "type"]
    for t in d["terms"]:
        if t["entity"] == "weir":
            weir_e[t["name"]] = dict(SCHEMATYP[t["type"]], description=t["definition"])
            if t["required"]:
                weir_k.append(t["name"])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": m["base"] + ("schema.json" if profil == "A" else "schema-profil-B.json"),
        "title": "%s, profile %s (DRAFT %s, not decided)" % (m["id"], profil, m["version"].split("-")[0]),
        "description": m["status"] + " " + m["definition"] + " Key-value form (the simplified NGSI-LD form).",
        "$ref": "#/$defs/" + m["id"],
        "$defs": {
            m["id"]: {"type": "object", "properties": egenskaper, "required": krav},
            "SewerOverflowWeir": {"type": "object", "properties": weir_e, "required": weir_k,
                                  "description": d["model"]["weirDefinition"]},
        },
    }


def tabell(rader):
    return "\n".join(rader) + "\n"


def termrad(t):
    enhet = "%s (%s)" % (t["unit"]["label"], t["unit"]["code"]) if t["unit"] else ""
    prof = "A, B" if len(t["profiles"]) == 2 else "only " + t["profiles"][0]
    return "| `%s` | %s | %s | %s | %s | %s |" % (t["name"], t["nature"], t["type"], enhet, prof, t["definition"])


def spec(d):
    m = d["model"]
    u = []
    u.append("# %s: DRAFT %s\n\n%s\n\n%s\n" % (m["id"], m["version"].split("-")[0], BANNER_EN, BANNER_SV))
    u.append("*This file is generated from the term list (`termer.json`). Do not edit it by hand.*\n")
    u.append("## What it describes\n\n%s\n\nSwedish: %s\n" % (m["definition"], m["definition_sv"]))
    u.append("## Profiles\n\nThere is one model. The profiles say which terms a distribution uses.\n\n" +
             tabell(["| Profile | Terms |", "|---|---|"] + ["| %s | %s |" % (k, v) for k, v in m["profiles"].items()]) +
             "\nProfile B leaves out the position (`location`, `sourceSrs`). That is a decision about who may see the position, not a different "
             "model.\n")
    u.append("## Identifiers\n\nAn entity has an NGSI-LD identifier `urn:ngsi-ld:<type>:<weirId>`. The identifier of a result is built from the entity type and "
             "the data owner's key for the chamber (`weirId`). The identifiers are ours and are not covered by the addresses of the terms.\n")
    u.append("## Entity types\n")
    u.append(tabell(["| Type | Definition |", "|---|---|"] + ["| `%s` | %s |" % (t["name"], t["definition"]) for t in d["terms"] if t["entity"] == "type"]))
    for nyckel, rubrik in (("result", "Terms of " + m["id"]), ("weir", "Terms of SewerOverflowWeir (the chamber)")):
        u.append("## %s\n" % rubrik)
        u.append(tabell(["| Term | Kind | Type | Unit | Profile | Definition |", "|---|---|---|---|---|---|"] +
                        [termrad(t) for t in d["terms"] if t["entity"] == nyckel]))
        if nyckel == "weir":
            u.append(m["weirDefinition"] + "\n")
    noter = [t for t in d["terms"] if t.get("note")]
    if noter:
        u.append("## Notes on terms\n")
        u.append("\n".join("* `%s`: %s" % (t["name"], t["note"]) for t in noter) + "\n")
    u.append("## Units\n\nEach measure has a UN/CEFACT unit code (in the table above). In the delivery the codes are listed once in `unitCodes`; in NGSI-LD every "
             "value carries its own `unitCode`. Times are ISO 8601 in UTC.\n")
    u.append("## Members of `provenance`\n")
    u.append(tabell(["| Member | Type | Definition |", "|---|---|---|"] +
                    ["| `%s` | %s | %s |" % (t["name"].split(".", 1)[1], t["type"], t["definition"]) for t in d["terms"] if t["entity"] == "provenance"]))
    u.append("## Links to other terms\n\nA link says that a term of ours is related to a term somewhere else. `skos:exactMatch` means the same thing; "
             "`skos:closeMatch` means nearly; `rdfs:seeAlso` means related but not equal. The links are in `mappings.sssom.tsv` and are drafts like the rest.\n")
    rader = ["| Our term | Link | Other term | Comment |", "|---|---|---|---|"]
    for t in d["terms"]:
        for l in t["links"]:
            rader.append("| `%s` | %s | <%s> | %s |" % (t["name"], l["predicate"], l["target"], l["comment"]))
    u.append(tabell(rader))
    u.append("## Files\n\n`context.jsonld` (term to address), `schema.json` and `schema-profil-B.json` (JSON Schema, key-value form), `mappings.sssom.tsv`, "
             "`examples/`. Not Smart Data Models' own artefact set yet: that would also need a description file in their layout and a review by the data owner.\n")
    u.append("## Swedish summary\n\nDetta är ett utkast till datamodell för modellerade bräddresultat per brunn och dygn. Det finns en modell och två profiler: A med "
             "position, B utan. Varje term har en definition, en typ och en enhet, och en del är kopplade till termer hos andra. Utkastet är inte beslutat eller "
             "överenskommet med någon, och det är inte inskickat till Smart Data Models.\n")
    return "\n".join(u)


def sssom(d):
    m = d["model"]
    r = ["#curie_map:", "#  svada: " + m["base"], "#  skos: http://www.w3.org/2004/02/skos/core#", "#  rdfs: http://www.w3.org/2000/01/rdf-schema#",
         "#  semapv: https://w3id.org/semapv/vocab/",
         "#mapping_set_id: " + m["base"] + "mappings.sssom.tsv",
         "#comment: DRAFT, not decided. " + m["status"],
         "\t".join(["subject_id", "predicate_id", "object_id", "mapping_justification", "comment"])]
    for t in d["terms"]:
        for l in t["links"]:
            r.append("\t".join(["svada:" + t["name"], l["predicate"], l["target"], "semapv:ManualMappingCuration", l["comment"]]))
    return "\n".join(r) + "\n"


def termlista(d):
    u = ["# Term list for the model draft (stage 1)\n", BANNER_EN + "\n", BANNER_SV + "\n",
         "*Generated by `tools/bygg-datamodell.py` from `datamodell/utkast/termer.json`. Do not edit by hand.*\n",
         "Each term is **borrowed** (`lånad`: we reuse an existing term as it is), **own** (`egen`: nobody else has it that we found) or **linked** (`knyt`: ours, "
         "with a link to the nearest term somewhere else). Links say \"related\" or \"nearly the same\", never more than the definitions support.\n"]
    from collections import Counter
    c = Counter(t["origin"] for t in d["terms"])
    u.append("%d terms: %d own, %d linked, %d borrowed.\n" % (len(d["terms"]), c["egen"], c["knyt"], c["lånad"]))
    u.append(tabell(["| Term | Belongs to | Origin | Profile | Link | Stored in the broker |", "|---|---|---|---|---|---|"] + [
        "| `%s` | %s | %s | %s | %s | %s |" % (
            t["name"], t["entity"], t["origin"], "A, B" if len(t["profiles"]) == 2 else "only " + t["profiles"][0],
            "; ".join("%s <%s>" % (l["predicate"], l["target"]) for l in t["links"]) or "–",
            "yes" if t["stored"] == "broker" else "no (in the delivery only)") for t in d["terms"]]))
    u.append("The data owner's gap G7 says `SewerOverflowWeir` is not a published Smart Data Model. Every own term above is a term nobody has agreed on.\n")
    u.append("## Swedish summary\n\nTermlistan visar för varje term om den är lånad, egen eller kopplad. De flesta är egna, eftersom vi inte hittade någon "
             "modell för en bräddhändelse. Inget här är beslutat.\n")
    return "\n".join(u)


def exempel(d):
    m = d["model"]
    b = {
        "id": "urn:ngsi-ld:SewerOverflowModelResult:SSO1_01-4402", "type": m["id"],
        "refWeir": "urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4402",
        "modelledDay": "2026-06-24", "periodStart": "2026-06-24T00:00:00Z", "periodEnd": "2026-06-25T00:00:00Z",
        "dataSource": "modelled-synthetic", "modelVersion": "FCF-simulator 1.0.0 / enkel överfallsmodell",
        "inflowMeanM3S": 0.10273, "inflowPeakM3S": 1.750154, "inflowVolumeM3": 8875.89,
        "overflowVolumeM3": 716.06, "overflowPeakM3S": 0.270568, "overflowDurationMin": 290.0,
        "overflowStart": "2026-06-24T11:55:00Z", "overflowEnd": "2026-06-24T16:45:00Z", "waterLevelMaxM": 0.2937,
        "provenance": {"dataset": "Modellerad bräddata", "distribution": "B", "distributionId": "modellerad-bradddata-b",
                       "batchId": "batch-010-2026-06-24", "producedAt": "2026-10-28T17:03:21Z", "ingestedAt": "2026-10-28T17:03:36Z",
                       "accessRights": "public", "informationClass": "K0R1T1", "license": "CC BY 4.0",
                       "publisher": "DHI – Future City Flow (SVADA PoC)", "receivedVia": "Eclipse EDC transfer (Dataspace Protocol)"},
    }
    a = dict(b)
    a["location"] = {"type": "Point", "coordinates": [11.99, 57.7]}
    a["sourceSrs"] = "EPSG:4619"
    a["provenance"] = dict(b["provenance"], distribution="A", distributionId="modellerad-bradddata-a", accessRights="non-public",
                           informationClass="K1R1T1", license="Agreement DHI–City of Gothenburg; requires KoV approval")
    # Normaliserad NGSI-LD-form för B
    n = {"@context": [m["base"] + "context.jsonld", "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"], "id": b["id"], "type": m["id"],
         "refWeir": {"type": "Relationship", "object": b["refWeir"]}}
    enh = {t["name"]: t["unit"]["code"] for t in d["terms"] if t["unit"]}
    for t in d["terms"]:
        if t["entity"] != "result" or t["name"] in ("refWeir", "provenance", "location", "sourceSrs") or t["name"] not in b:
            continue
        p = {"type": "Property", "value": b[t["name"]]}
        if t["name"] in enh:
            p["unitCode"] = enh[t["name"]]
            p["observedAt"] = b["periodEnd"]
        n[t["name"]] = p
    n["provenance"] = {"type": "Property", "value": b["provenance"], "observedAt": b["periodEnd"]}
    return {"example-A.json": a, "example-B.json": b, "example-normalized-B.jsonld": n}


def allt(d):
    ut = {}
    bas = os.path.join("datamodell", "utkast")
    ut[os.path.join(bas, "context.jsonld")] = json.dumps(kontext(d), ensure_ascii=False, indent=2) + "\n"
    ut[os.path.join(bas, "schema.json")] = json.dumps(schema(d, "A"), ensure_ascii=False, indent=2) + "\n"
    ut[os.path.join(bas, "schema-profil-B.json")] = json.dumps(schema(d, "B"), ensure_ascii=False, indent=2) + "\n"
    ut[os.path.join(bas, "SPEC.md")] = spec(d)
    ut[os.path.join(bas, "mappings.sssom.tsv")] = sssom(d)
    for namn, innehall in exempel(d).items():
        ut[os.path.join(bas, "examples", namn)] = json.dumps(innehall, ensure_ascii=False, indent=2) + "\n"
    ut[os.path.join("docs", "modell", "termlista.md")] = termlista(d)
    return ut


def main():
    d = las()
    ut = allt(d)
    gamla = []
    for sokvag, innehall in ut.items():
        full = os.path.join(ROT, sokvag)
        if "--kontrollera" in sys.argv:
            if not os.path.exists(full) or open(full, encoding="utf-8").read() != innehall:
                gamla.append(sokvag)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            open(full, "w", encoding="utf-8").write(innehall)
    if "--kontrollera" in sys.argv:
        if gamla:
            print("Gamla eller saknade filer (kör python3 tools/bygg-datamodell.py):\n  " + "\n  ".join(gamla))
            sys.exit(1)
        print("Datamodellens filer är aktuella (%d filer)." % len(ut))
    else:
        print("Skrev %d filer." % len(ut))


if __name__ == "__main__":
    main()
