#!/usr/bin/env python3
"""Datamodellens utkast över HTTP mot den körande brunnsvyn (K35): sidan och filerna finns, varje term i kontexten går att slå upp på sin egen adress,
varje svar bär utkastets status, och ingenting utanför den fasta listan går att nå. Användning: python3 -I tests/modell_http.py <brunnsvyns adress>"""
import json
import os
import sys
import urllib.error
import urllib.request

BAS = sys.argv[1].rstrip("/")
fel = 0


def tilltradeskaka():
    """Lösenordsgrinden (om den är på): tests/lib.sh demo_inloggning sparar kakan i $CURL_HOME/demo-kakor. Värdet skrivs aldrig ut."""
    sokvag = os.path.join(os.environ.get("CURL_HOME", ""), "demo-kakor")
    if not os.environ.get("CURL_HOME") or not os.path.exists(sokvag):
        return ""
    for rad in open(sokvag, encoding="utf-8"):
        delar = rad.rstrip("\n").split("\t")
        if len(delar) >= 7 and delar[5] == "svada_tilltrade":
            return "svada_tilltrade=" + delar[6]
    return ""


KAKA = tilltradeskaka()


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


def hamta(sokvag, accept="*/*"):
    huvud = {"Accept": accept}
    # testkakan: vår egen provning ska inte räknas i användningsstatistiken
    huvud["Cookie"] = (KAKA + "; " if KAKA else "") + "svada-test=1"
    req = urllib.request.Request(BAS + sokvag, headers=huvud)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, dict(ex.headers), ex.read()


def hd(h, namn):
    for k, v in h.items():
        if k.lower() == namn.lower():
            return v
    return ""


st, h, kropp = hamta("/modell?lang=sv", "text/html")
t = kropp.decode("utf-8")
kolla(st == 200 and "UTKAST" in t and "Smart Data Models" in t, "/modell (sv): 200 och märkt som utkast")
st, h, kropp = hamta("/modell?lang=en", "text/html")
kolla(st == 200 and "DRAFT" in kropp.decode("utf-8"), "/modell (en): 200 och märkt som utkast")
kolla(hd(h, "X-Data-Model-Status").startswith("DRAFT"), "sidan bär rubriken X-Data-Model-Status: DRAFT")
st, h, kropp = hamta("/modell", "application/json")
o = json.loads(kropp)
kolla(st == 200 and o["status"].startswith("DRAFT") and len(o["terms"]) >= 40, "/modell som JSON: status och %d termer" % len(o["terms"]))
kolla(all(f.startswith(BAS + "/modell/utkast/0.1/") for f in o["files"]) and o["base"] == BAS + "/modell/utkast/0.1/", "adresserna i översikten är brunnsvyns egna (%s)" % o["base"])
for f in o["files"]:
    s, hh, k = hamta(f[len(BAS):])
    kolla(s == 200 and b"modell.svada.invalid" not in k, "filen %s: 200, ingen platshållaradress" % f.rsplit("/", 1)[-1])
st, h, kropp = hamta("/modell/utkast/0.1/context.jsonld")
ctx = json.loads(kropp)["@context"]
kolla(hd(h, "Content-Type").startswith("application/ld+json"), "kontexten har mediatypen application/ld+json")
kolla(hd(h, "Access-Control-Allow-Origin") == "*", "kontexten kan läsas från en annan webbplats (CORS)")
kolla(ctx["svada"] == BAS + "/modell/utkast/0.1/", "kontextens bas är brunnsvyns adress")
# Varje egen term i kontexten går att slå upp på sin adress
egna = [k for k, v in ctx.items() if isinstance(v, str) and v.startswith("svada:")] + [n for n in o["terms"] if n.startswith("provenance.")]   # medlemmarna ligger i egenskapens värde och står inte i kontexten
saknas = []
for namn in egna:
    s, hh, k = hamta("/modell/utkast/0.1/" + namn, "application/json")
    if s != 200 or json.loads(k)["name"] != namn or not json.loads(k)["status"].startswith("DRAFT"):
        saknas.append(namn)
kolla(len(egna) >= 40 and not saknas, "alla %d egna termer i kontexten går att slå upp som JSON med status (fel: %s)" % (len(egna), saknas or "inga"))
s, hh, k = hamta("/modell/utkast/0.1/overflowVolumeM3?lang=en", "text/html")
kolla(s == 200 and b"DRAFT" in k and b"cubic metre" in k, "en termsida (en) är märkt som utkast och visar enheten")
s, hh, k = hamta("/modell/utkast/0.1/overflowVolumeM3", "application/ld+json")
kolla(s == 200 and json.loads(k)["unit"]["code"] == "MTQ", "en JSON-LD-läsare får JSON för en term")
# Enheterna i den öppna vyns JSON (MIM2 R3.3)
s, hh, k = hamta("/brunnar?format=json", "application/json")
try:
    lj = json.loads(k)
except ValueError:
    lj = {}
kolla(s == 200 and lj.get("enheter", {}).get("overflowVolumeM3") == "MTQ" and lj.get("datamodell", "").endswith("/modell"),
      "listan i JSON bär enhetskoder (UN/CEFACT) och en länk till datamodellen")
# Sidfoten länkar hit
st, h, kropp = hamta("/brunnar?lang=sv", "text/html")
kolla(b'href="/modell?lang=sv"' in kropp, "brunnsvyns sidfot länkar till datamodellen")
# Utanför listan
for ond in ("/modell/utkast/0.1/../../health", "/modell/utkast/0.1/%2e%2e/%2e%2e/etc/passwd", "/modell/utkast/0.1/nonsens", "/modell/utkast/0.1/examples/",
            "/modell/utkast/0.1/examples/../termer.json/x", "/modell/utkast/1.0/context.jsonld"):
    s, hh, k = hamta(ond)
    kolla(s == 404 or (ond.endswith("/health") and s == 200 and b"oppnaAttribut" in k), "%s ger 404 (eller normaliseras av klienten till en vanlig sida)" % ond)
print("\nFEL: %d" % fel if fel else "\nDatamodellen över HTTP: GRÖNT")
sys.exit(1 if fel else 0)
