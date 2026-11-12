#!/usr/bin/env python3
"""Datamodellens utkast (K34, utan stack): termlistan i datamodell/utkast/termer.json stämmer med vad koden faktiskt levererar, filerna är
genererade ur den, exemplen följer modellen och UTKAST-märkningen finns överallt. Utkastet är inte en beslutad modell; provet skyddar mot
att modellen och koden glider isär och mot att någon tar utkastet för färdigt. Körs från repots rot: python3 -I tests/datamodell_enhet.py"""
import datetime as dt
import json
import os
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


sys.path.insert(0, os.path.join(ROT, "tools"))
sys.path.insert(0, os.path.join(ROT, "services", "fcf-sim"))
sys.path.insert(0, os.path.join(ROT, "services", "ingest-service"))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("bygg_datamodell", os.path.join(ROT, "tools", "bygg-datamodell.py"))
bygg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bygg)
import distributioner  # noqa: E402
import ngsild  # noqa: E402

d = bygg.las()
terms = d["terms"]
namn = [t["name"] for t in terms]
kolla(len(namn) == len(set(namn)), "varje term finns en gång (%d termer)" % len(namn))
resultat = {t["name"]: t for t in terms if t["entity"] == "result"}
brunn_t = {t["name"]: t for t in terms if t["entity"] == "weir"}
prov_t = {t["name"].split(".", 1)[1]: t for t in terms if t["entity"] == "provenance"}

# Mot koden: det som skrivs på resultatentiteten
for falt in ngsild.MATETAL + ngsild.BESKRIVANDE + ("refWeir", "provenance"):
    kolla(falt in resultat, "koden skriver %s och modellen har termen" % falt)
# Mot koden: posten i leveransen
brunn = {"weirId": "X1", "weirName": "n", "regionId": "r", "category": "c", "weirType": "t", "seriesRef": "s",
         "location": {"type": "Point", "coordinates": [1, 2]}, "sourceSrs": "EPSG:4619", "outlet": "o", "recipient": "r"}
bas = [(0.1, 0.0)] * 6 + [(0.5, 0.2)] * 4
nycklar = set()
for matt in ("X1", None):
    nycklar |= set(distributioner.bygg_poster([brunn], bas, 0, dt.date(2026, 6, 24), matt, 5)[0].keys())
kand = set(resultat) | set(brunn_t) | {"weirName", "unitCodes"}   # weirName = name i modellen; unitCodes är leveransens enhetslista
okanda = sorted(nycklar - kand)
kolla(not okanda, "varje fält i leveransposten finns i modellen (saknas: %s)" % (okanda or "inget"))
# Vad som lagras i brokern: resultatentitetens termer som markerats "broker" är exakt de koden skriver
skrivs = set(ngsild.MATETAL + ngsild.BESKRIVANDE + ("refWeir", "provenance"))
kolla({f for f, t in resultat.items() if t["stored"] == "broker"} == skrivs,
      "de termer som sägs lagras i brokern är exakt de koden skriver på resultatentiteten (skillnad: %s)" % (sorted({f for f, t in resultat.items() if t["stored"] == "broker"} ^ skrivs) or "ingen"))
# Enheter
for falt, kod in distributioner.ENHETER.items():
    kolla(resultat[falt]["unit"] and resultat[falt]["unit"]["code"] == kod, "enheten för %s är %s i både koden och modellen" % (falt, kod))
kolla({f for f, t in resultat.items() if t["unit"]} == set(distributioner.ENHETER), "exakt de mätetal koden ger enhet har enhet i modellen")
# Profilerna: det som skiljer A från B i koden är det som bara finns i A i modellen
kolla({f for f, t in resultat.items() if t["profiles"] == ["A"]} == set(distributioner.KANSLIGA_FALT),
      "profil B saknar exakt de fält koden tar bort för B (%s)" % ", ".join(distributioner.KANSLIGA_FALT))
# Proveniens
p = ngsild.bygg_proveniens({"dataset": "d", "distribution": "B", "distributionId": "i", "batchId": "b", "producedAt": "t", "accessRights": "public",
                            "informationClass": "K0R1T1", "license": "l", "publisher": "p"}, "a", "B", "tp", "u")
kolla(set(p) <= set(prov_t), "alla proveniensfält koden skriver finns i modellen (saknas: %s)" % (sorted(set(p) - set(prov_t)) or "inget"))
# Termernas kvalitet
saknar = [t["name"] for t in terms if not (t["definition"].strip() and t["definition_sv"].strip())]
kolla(not saknar, "varje term har definition på engelska och svenska (saknas: %s)" % (saknar or "inget"))
kolla(all(t["origin"] in ("lånad", "egen", "knyt") for t in terms), "varje term är lånad, egen eller knyt")
kolla(all(any(l["predicate"] == "skos:exactMatch" for l in t["links"]) for t in terms if t["origin"] == "lånad"), "varje lånad term har en exactMatch-länk")
kolla(all(t["links"] for t in terms if t["origin"] == "knyt"), "varje knyten term har minst en länk")
kolla(not any(t["links"] for t in terms if t["origin"] == "egen"), "ingen egen term har en länk (den är då knyten)")
kolla(all(l["target"].startswith(("http://", "https://")) and l["comment"] for t in terms for l in t["links"]), "varje länk är en adress och har en kommentar")
kolla(all(l["predicate"] in ("skos:exactMatch", "skos:closeMatch", "rdfs:seeAlso") for t in terms for l in t["links"]), "länkarna använder bara exactMatch, closeMatch och seeAlso")
kolla(all(t["origin"] == "lånad" or not any(l["predicate"] == "skos:exactMatch" for l in t["links"]) for t in terms), "bara lånade termer har exactMatch (egna termer påstår aldrig 'samma')")
# Filerna är genererade ur källan
gamla = []
for sokvag, innehall in bygg.allt(d).items():
    full = os.path.join(ROT, sokvag)
    if not os.path.exists(full) or open(full, encoding="utf-8").read() != innehall:
        gamla.append(sokvag)
kolla(not gamla, "de genererade filerna är aktuella (kör python3 tools/bygg-datamodell.py; gamla: %s)" % (gamla or "inga"))
# Kontexten
ctx = json.load(open(os.path.join(ROT, "datamodell", "utkast", "context.jsonld"), encoding="utf-8"))["@context"]
kolla(all(t["name"] in ctx for t in terms if t["entity"] != "provenance"), "kontexten har alla termer")
kolla("@version" not in ctx and not any(isinstance(v, dict) for v in ctx.values()), "kontexten är JSON-LD 1.0 med enkla termer (Mintaka 0.7 klarar inte 1.1 eller nästlade kontexter)")
kolla("provenance" in ctx, "kontexten har provenance (medlemmarna ligger i värdet och slås upp på sina egna adresser)")
bas_iri = d["model"]["base"]
kolla(".invalid/" in bas_iri, "utkastets adresser ligger under .invalid och går med flit inte att öppna (%s)" % bas_iri)
kolla(all(v.startswith("svada:") or v.startswith("https://uri.etsi.org/") for k, v in ctx.items() if isinstance(v, str) and k not in ("id", "type", "svada")),
      "kontexten pekar bara på utkastets adresser eller NGSI-LD:s egna")
# Exempel
for fil, profil in (("example-A.json", "A"), ("example-B.json", "B")):
    ex = json.load(open(os.path.join(ROT, "datamodell", "utkast", "examples", fil), encoding="utf-8"))
    tillatna = {n for n, t in resultat.items() if profil in t["profiles"]} | {"id", "type"}
    kolla(set(ex) <= tillatna, "%s använder bara termer ur profil %s (ej tillåtna: %s)" % (fil, profil, sorted(set(ex) - tillatna) or "inga"))
    kolla(all(n in ex for n, t in resultat.items() if t["required"] and profil in t["profiles"]), "%s har alla obligatoriska termer" % fil)
    kolla(ex["dataSource"] in resultat["dataSource"]["enum"], "%s: dataSource är ett tillåtet värde" % fil)
    kolla(("location" in ex) == (profil == "A"), "%s: position finns i A och inte i B" % fil)
# Utkastmärkningen
for sokvag in ("datamodell/utkast/SPEC.md", "docs/modell/termlista.md", "docs/modell/README.md"):
    text = open(os.path.join(ROT, sokvag), encoding="utf-8").read()
    kolla("DRAFT" in text and "UTKAST" in text, "%s är märkt som utkast (DRAFT och UTKAST)" % sokvag)
    kolla("Smart Data Models" in text, "%s säger att utkastet inte är inskickat till Smart Data Models" % sokvag)
kolla("DRAFT" in d["model"]["status"] and "Not decided" in d["model"]["status"], "modellens status säger DRAFT och Not decided")
print("\nFEL: %d" % fel if fel else "\nDatamodellens utkast: GRÖNT")
sys.exit(1 if fel else 0)
