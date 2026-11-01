#!/usr/bin/env python3
"""Datamodellens utkast på brunnsvyns adress (K35, utan stack): modell.py serverar bara filer ur den fasta listan, byter platshållaradressen mot den
egna publika, ger varje term en uppslagbar sida och en JSON-beskrivning, och varje sida och svar säger att det är ett UTKAST. Körs från repots rot:
python3 -I tests/modell_publik_enhet.py"""
import json
import os
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.environ["MODELL_KATALOG"] = os.path.join(ROT, "datamodell", "utkast")
os.environ["SVADA_VERSION"] = "2026.10.28-1"
sys.path.insert(0, os.path.join(ROT, "services", "publik-vy"))
import modell  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


PUBLIK = "https://brunnar.exempel.test"
BAS = PUBLIK + "/modell/utkast/0.1/"
TIDSSERIE = "https://tidsserie.exempel.test/temporal/entities?type=X"
d = json.load(open(os.path.join(ROT, "datamodell", "utkast", "termer.json"), encoding="utf-8"))
terms = d["terms"]

kolla(modell.tillganglig(), "modellen går att läsa ur katalogen")
# Enhetskoderna i den öppna vyns JSON kommer ur termlistan (en källa)
import re as _re
_main = open(os.path.join(ROT, "services", "publik-vy", "main.py"), encoding="utf-8").read()
_namn = _re.findall(r'"(\w+)"', _re.search(r"OPPNA_ATTRIBUT = \((.*?)\)", _main, _re.S).group(1))
_enh = modell.enheter(_namn)
kolla(len(_namn) == 7 and set(_enh) == set(_namn) and _enh["overflowVolumeM3"] == "MTQ" and _enh["overflowDurationMin"] == "MIN" and _enh["waterLevelMaxM"] == "MTR",
      "alla %d öppna attribut har en UN/CEFACT-enhetskod ur termlistan (%s)" % (len(_namn), _enh))
kolla('"enheter": modell.enheter(OPPNA_ATTRIBUT)' in _main and '"enheter": modell.enheter(LISTKOLUMNER)' in _main and "ENHETER_SCHEMA" in _main,
      "den öppna vyns JSON och OpenAPI-beskrivningen bär enheterna")
# Filer
for namn in modell.FILER:
    f = modell.fil(namn, PUBLIK)
    kolla(f is not None, "filen %s serveras" % namn)
    if f:
        text = f[0].decode("utf-8")
        kolla("modell.svada.invalid" not in text, "%s innehåller ingen platshållaradress efter bytet" % namn)
        if namn.endswith((".json", ".jsonld")):
            try:
                json.loads(text)
                giltig = True
            except ValueError:
                giltig = False
            kolla(giltig, "%s är giltig JSON" % namn)
ctx = json.loads(modell.fil("context.jsonld", PUBLIK)[0])["@context"]
kolla(ctx["overflowVolumeM3"] == "svada:overflowVolumeM3" and ctx["svada"] == BAS, "kontexten pekar på den egna adressen (%s)" % ctx["svada"])
kolla(ctx["location"] == "https://uri.etsi.org/ngsi-ld/location", "den lånade termen location behåller sin egen adress")
# Det går inte att be om något utanför listan
for ond in ("../termer.json", "..%2ftermer.json", "/etc/passwd", "termer.json/../../x", "", "examples", "examples/", "examples/../termer.json", "nonsens", "CONTEXT.JSONLD",
            "context.jsonld\n", "context.jsonld\x00"):
    kolla(modell.fil(ond, PUBLIK) is None and modell.term(ond) is None, "%r ger varken fil eller term" % ond)
# Varje term har en sida och en JSON-beskrivning
for sprak in ("sv", "en"):
    sida = modell.modell_sida(PUBLIK, TIDSSERIE, "", sprak)
    kolla(("UTKAST" if sprak == "sv" else "DRAFT") in sida and "Smart Data Models" in sida, "översiktssidan (%s) säger att det är ett utkast som inte är inskickat" % sprak)
    kolla(all(("%s%s?lang=%s" % (BAS, t["name"], sprak)) in sida for t in terms), "översiktssidan (%s) länkar till alla %d termer" % (sprak, len(terms)))
    kolla(all(("%s%s" % (BAS, n)) in sida for n in modell.FILER), "översiktssidan (%s) länkar till alla filer" % sprak)
    kolla('id="demoversion">2026.10.28-1<' in sida, "översiktssidan (%s) har versionen i sidfoten" % sprak)
    kolla(all(x not in sida for x in ("mintaka:8080", "host.docker.internal", "/Users/", "None")), "översiktssidan (%s) visar inget internt" % sprak)
    saknar = []
    for t in terms:
        s = modell.term_sida(t, PUBLIK, TIDSSERIE, "", sprak)
        fraga = t["definition_sv"] if sprak == "sv" else t["definition"]
        import html
        if not (("UTKAST" if sprak == "sv" else "DRAFT") in s and html.escape(fraga) in s and "Smart Data Models" in s and "None" not in s):
            saknar.append(t["name"])
    kolla(not saknar, "varje termsida (%s) har utkastmärkning och rätt definition (fel: %s)" % (sprak, saknar or "inga"))
lan = modell.term_sida(modell.term("location"), PUBLIK, TIDSSERIE, "", "en")
kolla("https://uri.etsi.org/ngsi-ld/location" in lan and "borrowed" in lan, "den lånade termen visar den andras adress och ordet borrowed")
for t in terms:
    j = modell.term_json(t, PUBLIK)
    if t["name"] in ("overflowVolumeM3", "name", "provenance.license"):
        kolla(j["status"].startswith("DRAFT") and j["definition"]["en"] and j["definition"]["sv"], "JSON för %s bär status och definition på båda språken" % t["name"])
kolla(modell.term_json(modell.term("overflowVolumeM3"), PUBLIK)["id"] == BAS + "overflowVolumeM3", "termens id i JSON är dess adress")
kolla(modell.term_json(modell.term("dataSource"), PUBLIK)["allowedValues"] == ["measured", "measured-partial", "modelled-synthetic"], "tillåtna värden redovisas")
o = modell.oversikt_json(PUBLIK)
kolla(o["status"].startswith("DRAFT") and len(o["terms"]) == len(terms) and o["base"] == BAS, "översikten i JSON bär status, termerna och basadressen")
# Saknad katalog: tjänsten startar och modellen är bara inte tillgänglig
modell._cache.clear()
modell.KATALOG = "/finns/inte"
kolla(not modell.tillganglig() and modell.fil("context.jsonld", PUBLIK) is None and modell.term("overflowVolumeM3") is None, "utan katalog är modellen inte tillgänglig (och ingenting kraschar)")
print("\nFEL: %d" % fel if fel else "\nDatamodellen på brunnsvyn: GRÖNT")
sys.exit(1 if fel else 0)
