#!/usr/bin/env python3
"""K37 (utan stack): MIM-rutorna. En källa (services/dashboard/mim.py, en kopia i publik-vy), statusen stämmer med docs/mims/README.md,
varje steg 1-6 och sidorna brunnsvy och modell har en ruta med rätt länk, båda språken, och inget internt läcker."""
import html
import os
import re
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROT, "services", "dashboard"))
import mim  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    if not villkor:
        fel += 1


print("== MIM-rutorna ==")
a = open(os.path.join(ROT, "services", "dashboard", "mim.py"), encoding="utf-8").read()
b = open(os.path.join(ROT, "services", "publik-vy", "mim.py"), encoding="utf-8").read()
kolla(a == b, "kopian i publik-vy är identisk med källan i dashboard")
vy_dash = open(os.path.join(ROT, "services", "dashboard", "vy.py"), encoding="utf-8").read()
kolla(mim.CSS_LJUS.strip("\n") in vy_dash, "kontrollrummets stilar innehåller modulens ljusa CSS ordagrant (ingen avvikande kopia)")
kolla("prefers-color-scheme: dark" not in mim.CSS_LJUS and 'data-theme="dark"' not in mim.CSS_LJUS, "den ljusa delen har inget mörkt tema (kontrollrummet är ljust)")

# Statusen mot översikten i docs/mims/README.md (egen bedömning; ska aldrig gå längre än dokumenten)
readme = open(os.path.join(ROT, "docs", "mims", "README.md"), encoding="utf-8").read()
rader = {m.group(1): m.group(2) for m in re.finditer(r"^\| (MIM\d) \| [^|]+\| ([^|]+)\|", readme, re.M)}
kolla(set(mim.MIM) <= set(rader), "alla MIM:ar i rutorna finns i översikten (%s)" % sorted(rader))
for nyckel, v in mim.MIM.items():
    doc = rader.get(nyckel, "")
    inte_annu = "Not yet followed" in doc
    kan_inte = "Cannot be assessed" in doc
    kolla(kan_inte == v[6].startswith("Inga numrerade krav") and (kan_inte or (v[6].startswith("Följs inte ännu") == inte_annu and (inte_annu or v[6].startswith("Följs")))),
          "%s: rutans status (%s) stämmer med översikten (%s)" % (nyckel, v[6], re.sub(r"[*]", "", doc).strip()[:48]))
    kolla(v[7].startswith("Not yet followed") == inte_annu and v[7].startswith("No numbered requirements") == kan_inte, "%s: engelska statusen följer samma linje" % nyckel)
    kolla(("delvis" if ("modell" in v[6] or "PoC" in v[6] or kan_inte) else ("nej" if inte_annu else "ok")) == v[8], "%s: färgnivån stämmer med texten" % nyckel)

# Rutor på stegen och sidorna, båda språken, rätt länk, inget internt
ALLT = {**mim.STEG_MIM, **mim.SIDA_MIM}
kolla(set(mim.STEG_MIM) == {1, 2, 3, 4, 5, 6}, "varje steg 1-6 har en ruta")
kolla({"brunnsvy", "modell"} <= set(mim.SIDA_MIM), "brunnsvyn och modellsidan har en ruta")
internt = re.compile(r"edc-|identity-hub|orion|mintaka|publik-vy|127\.0|:\d{4,5}|did:web|\.py\b|docs/|svadamini|AP\d|etapp", re.I)
for nyckel in ALLT:
    for sprak in ("sv", "en"):
        h = mim.ruta(nyckel, sprak)
        slug = [mim.MIM[m][5] for m, _, _ in ALLT[nyckel]]
        kolla('class="mimruta"' in h and all("https://mims.oascities.org/mims-specification-v9.0/%s" % s in h for s in slug) and 'rel="noopener"' in h,
              "%s/%s: rutan finns med länk till varje MIM och rel=noopener" % (nyckel, sprak))
        kolla(not internt.search(re.sub(r"<[^>]+>", " ", h)), "%s/%s: inga interna uppgifter i texten" % (nyckel, sprak))
kolla(mim.ruta("finns-inte", "sv") == "", "en sida utan MIM:ar får ingen ruta")
# varje MIM i en ruta har en rad om vad den är
kolla(all(len(v[3]) > 30 and len(v[4]) > 30 for v in mim.MIM.values()), "varje MIM har en rad om vad den är, på båda språken")

# Sidan /mim: en källa i två kopior, alla MIM:ar med avsteg, länk i varje ruta och i menyn, båda språken, inget internt
import mimsida
sa = open(os.path.join(ROT, "services", "dashboard", "mimsida.py"), encoding="utf-8").read()
sb = open(os.path.join(ROT, "services", "publik-vy", "mimsida.py"), encoding="utf-8").read()
kolla(sa == sb, "mimsida.py: kopian i publik-vy är identisk med källan i dashboard")
kolla(set(mimsida.ORDNING) == set(mim.MIM) and set(mimsida.DETALJ) == set(mim.MIM), "sidan redovisar varje MIM som rutorna nämner")
for sprak in ("sv", "en"):
    h = mimsida.sida(sprak)
    kolla(all('id="%s"' % n.lower() in h for n in mim.MIM), "/mim (%s): ett avsnitt per MIM" % sprak)
    kolla(all(mim.MIM[n][6 if sprak == "sv" else 7] in html.unescape(h) for n in mim.MIM), "/mim (%s): statusen är densamma som i rutorna" % sprak)
    kolla('href="/mim?lang=%s"' % sprak in mim.ruta(1, sprak) and 'href="/mim?lang=%s"' % sprak in mim.menylank(sprak), "(%s): rutan och menyn länkar till /mim" % sprak)
    kolla(not internt.search(re.sub(r"<[^>]+>", " ", h)), "/mim (%s): inga interna uppgifter i texten" % sprak)
    kolla("aria-label" in h and ("ny flik" in h or "new tab" in h), "/mim (%s): länkarna ut säger att de öppnas i ny flik" % sprak)
kolla("kuvert" not in mim.ruta(4, "sv") and "leverans-JSON" in mim.ruta(4, "sv"), "steg 4 säger leverans-JSON, inte kuvert")

# Ordlistan: en källa i två kopior, unika id:n, kompilerbara regex, motorn på sidorna utan egen motor
import ordlista
oa = open(os.path.join(ROT, "services", "dashboard", "ordlista.py"), encoding="utf-8").read()
ob = open(os.path.join(ROT, "services", "publik-vy", "ordlista.py"), encoding="utf-8").read()
kolla(oa == ob, "ordlista.py: kopian i publik-vy är identisk med källan i dashboard")
ids = [o["id"] for o in ordlista.ORDLISTA]
kolla(len(ids) == len(set(ids)), "ordlistan: id:na är unika")
kolla(all(o[sp]["term"] and len(o[sp]["def"]) > 20 and o[sp]["re"] for o in ordlista.ORDLISTA for sp in ("sv", "en")), "ordlistan: varje begrepp har term, regex och förklaring på båda språken")
for o in ordlista.ORDLISTA:
    for sp in ("sv", "en"):
        try:
            re.compile(o[sp]["re"].replace("\\p{L}", "\\w").replace("\\p{N}", "\\d"))
        except re.error as x:
            kolla(False, "ordlistan: regex för %s (%s) går att tolka: %s" % (o["id"], sp, x))
for sprak in ("sv", "en"):
    sida = ordlista.med_ordlista("<html><body><p>x</p></body></html>", sprak, "/ordlista?lang=%s#ordlista-{id}" % sprak)
    kolla("id=\"tips\"" in sida or "tips.id = 'tips'" in sida, "ordlistemotorn läggs in före </body> (%s)" % sprak)
    kolla("\\u003c" not in ordlista.js_ord(sprak).__repr__() and "</script>" not in ordlista.tillagg(sprak, "/x#{id}").replace("</script>", "", 1), "ordlistemotorn: inget </script> inne i skriptet (%s)" % sprak)
    kolla(len(ordlista.sida(sprak)) > 5000 and "Version" in ordlista.sida(sprak), "/ordlista (%s): sidan har alla begrepp och en versionsrad" % sprak)
kolla("li > span" in mim.CSS and ".mimruta span {" not in mim.CSS, "MIM-rutan: blockregeln gäller bara rutans egna rader, inte understrukna ord")

print("OK: alla prov gröna" if fel == 0 else "FEL: %d" % fel)
sys.exit(1 if fel else 0)
