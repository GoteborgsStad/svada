#!/usr/bin/env python3
"""K38 (utan stack): schemakontrollen vid inläsning (MIM2 R3.4). Exempelfilerna godkänns, avvikelser hittas (profil B får inte bära position),
resultatet är öppet (EJ_KONTROLLERAD när schemat saknas) och kontrollen ger samma svar som biblioteket jsonschema när det finns."""
import json
import os
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["MODELL_KATALOG"] = os.path.join(ROT, "datamodell", "utkast")
sys.path.insert(0, os.path.join(ROT, "services", "ingest-service"))
import schemakontroll as sk  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    if not villkor:
        fel += 1


print("== Schemakontroll vid inläsning ==")
ex = os.path.join(ROT, "datamodell", "utkast", "examples")
a = json.load(open(os.path.join(ex, "example-A.json"), encoding="utf-8"))
b = json.load(open(os.path.join(ex, "example-B.json"), encoding="utf-8"))
r = sk.kontrollera([b], "b")
kolla(r["resultat"] == "OK" and r["godkanda"] == 1 and r["schema"] == "schema-profil-B.json", "exempel B godkänns mot profil B (%s)" % r["schema"])
r = sk.kontrollera([a], "a")
kolla(r["resultat"] == "OK" and r["schema"] == "schema.json", "exempel A godkänns mot hela schemat")
r = sk.kontrollera([a], "b")
kolla(r["resultat"] == "AVVIKELSE" and "/location" in " ".join(r["exempel"]), "profil B tillåter ingen position: A:s exempel avvisas mot B (%s)" % r["exempel"][:1])
fel_post = dict(b, overflowVolumeM3="många")
r = sk.kontrollera([b, fel_post], "b")
kolla(r["resultat"] == "AVVIKELSE" and r["godkanda"] == 1 and r["poster"] == 2 and "overflowVolumeM3" in r["exempel"][0], "en post med fel typ hittas, och antalen stämmer (%s)" % r["exempel"][:1])
saknas = {k: v for k, v in b.items() if k != "periodEnd"}
r = sk.kontrollera([saknas], "b")
kolla(r["resultat"] == "AVVIKELSE" and "periodEnd" in r["exempel"][0], "en saknad obligatorisk term hittas")
extra = dict(b, hittepa=1)
kolla(sk.kontrollera([extra], "b")["resultat"] == "OK", "en extra term på toppnivån är tillåten (modellen är öppen för fler termer, som NGSI-LD)")
prov_extra = dict(b, provenance=dict(b["provenance"], hittepa=1))
kolla(sk.kontrollera([prov_extra], "b")["resultat"] == "AVVIKELSE", "en okänd medlem i provenance hittas (den är sluten)")
# Riktig utdata från ingest: ngsild.till_entiteter + bygg_proveniens på en leverans, genom schemakontrollen (inte bara ett handbyggt exempel)
import ngsild  # noqa: E402
post = {k: v for k, v in b.items() if k not in ("id", "type", "refWeir", "provenance")}
post["weirId"] = b["id"].rsplit(":", 1)[-1]
post["unitCodes"] = {"overflowVolumeM3": "MTQ", "overflowDurationMin": "MIN"}
kuvert = {"dataset": "Modellerad bräddata", "distributionId": "modellerad-bradddata-b", "batchId": "batch-prov", "producedAt": b["periodEnd"],
          "accessRights": b["provenance"]["accessRights"], "informationClass": b["provenance"]["informationClass"],
          "license": b["provenance"]["license"], "publisher": b["provenance"]["publisher"]}
for dist, ex_dist in (("b", None), ("a", a)):
    p2 = dict(post)
    if ex_dist:
        p2.update({k: ex_dist[k] for k in ("location", "sourceSrs") if k in ex_dist})
    prov = ngsild.bygg_proveniens(kuvert, "avtal-prov", dist, "tp-prov", avtal_url="https://exempel.test/avtal/avtal-prov")
    ent = ngsild.till_entiteter(kuvert, [p2], prov, dist)
    r = sk.kontrollera(ent, dist)
    kolla(r["resultat"] == "OK", "riktig utdata ur ngsild.till_entiteter godkänns mot %s (%s)" % (r["schema"], r["exempel"][:1] or "inga avvikelser"))
# NGSI-LD i normaliserad form omvandlas till nyckel-värde innan kontrollen, och typen A/B byts mot modellens namn
norm = {"id": b["id"], "type": "SewerOverflowModelB", "refWeir": {"type": "Relationship", "object": b["refWeir"]},
        "provenance": {"type": "Property", "value": b["provenance"], "observedAt": b["periodEnd"]}}
for k, v in b.items():
    if k not in ("id", "type", "refWeir", "provenance"):
        norm[k] = {"type": "Property", "value": v, "observedAt": b["periodEnd"]}
kv = sk.nyckel_varde(norm)
kolla(kv["type"] == "SewerOverflowModelResult" and kv["refWeir"] == b["refWeir"] and kv["overflowVolumeM3"] == b["overflowVolumeM3"], "normaliserad form blir nyckel-värde")
kolla(sk.kontrollera([norm], "b")["resultat"] == "OK", "den normaliserade entiteten godkänns")
# Schemat saknas: öppet redovisat, inte tyst
sk.KATALOG = "/finns/inte"; sk._cache.clear()
r = sk.kontrollera([b], "b")
kolla(r["resultat"] == "EJ_KONTROLLERAD" and r["godkanda"] == 0, "saknas schemat står det som EJ_KONTROLLERAD, inte som godkänt")
sk.KATALOG = os.environ["MODELL_KATALOG"]; sk._cache.clear()
# Mot biblioteket, när det finns
try:
    import jsonschema
    schema_b = json.load(open(os.path.join(ROT, "datamodell", "utkast", "schema-profil-B.json"), encoding="utf-8"))
    for namn, post in (("giltig", b), ("fel typ", fel_post), ("saknad", saknas), ("extra", extra), ("okänd provenance", prov_extra), ("position i B", a)):
        mitt = not sk.validera(post, schema_b, schema_b)
        deras = jsonschema.Draft202012Validator(schema_b).is_valid(post)
        kolla(mitt == deras, "samma utslag som jsonschema för %s (%s)" % (namn, "godkänd" if mitt else "avvisad"))
except ImportError:
    print("  [--] biblioteket jsonschema finns inte här: jämförelsen hoppas över")
print("OK: alla prov gröna" if fel == 0 else "FEL: %d" % fel)
sys.exit(1 if fel else 0)
