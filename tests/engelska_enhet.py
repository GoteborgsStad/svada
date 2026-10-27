#!/usr/bin/env python3
"""Enhetstest: meddelandekatalogen är komplett och inget svenskt läcker till den engelska vyn.

Ingen stack behövs. Fyra kontroller:

 1. Katalogen (services/dashboard/meddelanden.py): varje kod har både svensk och engelsk mall, med samma
    parametrar, och den engelska renderingen innehåller inga svenska ord.
 2. Varje meddelandekod som tjänsterna (Python och Java) hänvisar till finns i katalogen.
 3. Fri svensk text i kontrollrummets egna moduler: alla svenska strängkonstanter där som ännu inte går
    via en kod körs genom reservöversättaren (i18n.py) och får inte lämna svenska ord kvar.
 4. Hashkedjan räknas över kod och parametrar: samma händelse ger samma kanoniska text oavsett språk.
"""
import ast
import os
import re
import sys

RAD = os.path.join(os.path.dirname(__file__), "..", "services")
sys.path.insert(0, os.path.join(RAD, "dashboard"))
import i18n  # noqa: E402
import meddelanden  # noqa: E402

SVENSKA = re.compile(r"[åäöÅÄÖ]|\b(och|att|som|inte|för|med|ett|på|till|kan|från|eller|har|ska|när|efter|"
                     r"staden|stadens|avtalet|avtalets|brunnar|nyckel|ingen|inget|finns|saknas|kör|väntar|"
                     r"förhandling|leveransen|överföring|skapades|vägrade|nådde|nekas|hävt|hävts)\b")
NAMN = re.compile(r"Kretslopp och [Vv]atten|Göteborg\w*|Krokängsparken|Modellerad bräddata")

fel = 0


def ok(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    if not villkor:
        fel += 1


def exempel_varde(namn):
    return {"dist": "A", "asset": "modellerad-bradddata-a", "tillstand": "FINALIZED", "antal": 7, "totalt": 91,
            "falt": ["location", "sourceSrs"], "forbud": ["distribute", "publish"], "lagen": ["gis_i_b"],
            "skyldigheter": ["kovGodkannande"], "havda": ["x1"], "beslut": "GODKAND", "status": "HAVT",
            "orsak": "brunns-gis-i-distribution-b", "roll": "Kretslopp och Vatten – rättighetsinnehavare (dataägare)"
            }.get(namn, "X1")


# ---- 1. katalogen --------------------------------------------------------------------------------
dalig = []
for kod in meddelanden.kallor_koder():
    mall = meddelanden.KATALOG[kod]
    if not mall.get("sv") or not mall.get("en"):
        dalig.append("%s: saknar svensk eller engelsk mall" % kod)
        continue
    if meddelanden.parametrar_i_mall(kod, "sv") != meddelanden.parametrar_i_mall(kod, "en"):
        dalig.append("%s: svenska och engelska mallen har olika parametrar" % kod)
        continue
    p = {n: exempel_varde(n) for n in meddelanden.parametrar_i_mall(kod, "sv")}
    en = meddelanden.visa(kod, p, "en")
    sv = meddelanden.visa(kod, p, "sv")
    if "{" in en or "{" in sv:
        dalig.append("%s: oifylld parameter (%r)" % (kod, en))
    kvar = SVENSKA.findall(NAMN.sub(" ", en))
    if kvar and kod != "fri":
        dalig.append("%s: engelska mallen innehåller svenska ord %s: %r" % (kod, sorted(set(map(str, kvar)))[:3], en[:80]))
for d in dalig:
    print("  [FEL] katalog: " + d)
ok(not dalig, "katalogen: %d koder, alla med sv och en, samma parametrar, engelskan utan svenska ord"
   % len(meddelanden.KATALOG))

# ---- 2. koder som tjänsterna hänvisar till finns ------------------------------------------------------
KODMONSTER = re.compile(r'["\']((?:atgard|jobb|fel|kedja|kallfel|audit|ingest|gateway|fcf|kov)\.[a-z0-9_-]+)["\']')
KALLFILER = []
for rot, _, filer in os.walk(RAD):
    if "node_modules" in rot:
        continue
    for f in filer:
        if f.endswith(".py"):
            KALLFILER.append(os.path.join(rot, f))
for rot, _, filer in os.walk(os.path.join(RAD, "..", "edc", "src")):
    for f in filer:
        if f.endswith(".java"):
            KALLFILER.append(os.path.join(rot, f))
saknas = set()
for f in KALLFILER:
    if f.endswith("meddelanden.py"):
        continue
    for m in KODMONSTER.finditer(open(f, encoding="utf-8").read()):
        kod = m.group(1)
        # kod som byggs ihop (suffix läggs till i koden) kontrolleras via sina färdiga former nedan
        if kod not in meddelanden.KATALOG and not kod.endswith("_"):
            saknas.add("%s (%s)" % (kod, os.path.relpath(f, RAD)))
for s in sorted(saknas):
    print("  [FEL] kod som saknas i katalogen: " + s)
ok(not saknas, "alla koder som tjänsterna (Python och Java) hänvisar till finns i katalogen")
for kod in ("audit.kov_godkand_roll", "audit.kov_avslagen_roll", "audit.avtal_havt_roll", "fel.inget_avtal_kov"):
    ok(kod in meddelanden.KATALOG, "kod som byggs i koden finns: " + kod)

# ---- 3. fri svensk text i kontrollrummets egna moduler ---------------------------------------------------
DASH = ["jobb.py", "kedjan.py", "audit.py", "analys.py", "kallor.py", "main.py", "steg.py"]
UNDANTAG = (r"^/", r"^https?:", r"^\[", r"^[A-Z_]+ måste", r"^DEMO_VARIANT", r"^Externa varianten",
            r"^knapptäckning", r"^<!doctype", r"^avstängd$", r"^\[dashboard\]", r"^Modellerad bräddata$",
            r"^brunnar$", r"^inte pollad ännu$", r"^Avtalet hittades inte", r"^SLÄPPTES IGENOM",
            r"^kontraktsförhandling$", r"^Felinjektion$", r"%s/avtal", r"^avtal-|^inget-gallande",
            # avtalssidan och exempelobjekten är tvåspråkiga på annat sätt (S(sv, en), _s(sv, en))
            r"^Stadens |^Tillgång|^Giltigt|^ODRL-ögonblicksbild|^Ett avtal gäller tills|^UTGÅNGET",
            r"^Avtal$", r"^I klartext",
            # etiketter i steg 6:s detaljrader översätts av steg.oversatt_detalj (_DETALJ_EN)
            r"^Brunnar |^Total bräddvolym|^Högsta bräddvolym|^Gällande avtal om A")
fri_kvar = []
for fil in DASH:
    traed = ast.parse(open(os.path.join(RAD, "dashboard", fil), encoding="utf-8").read())
    doc = set()
    for n in ast.walk(traed):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) \
                and ast.get_docstring(n, clean=False) is not None and isinstance(n.body[0], ast.Expr):
            doc.add(id(n.body[0].value))
    for n in ast.walk(traed):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc and len(n.value) > 12 \
                and SVENSKA.search(n.value) and not any(re.search(u, n.value) for u in UNDANTAG):
            # tvåspråkiga par _t("sv", "en") / S(...) / _s(...) och kommentarer är inte fri text
            fri_kvar.append((fil, n.lineno, n.value))
# I steg.py och main.py finns tvåspråkiga texter (_t, _s, S, t) som inte är meddelanden: de kontrolleras av
# kedjevy_rendering.py (K-testerna). Här räknas bara moduler som skapar meddelanden.
fri_kvar = [x for x in fri_kvar if x[0] in ("jobb.py", "kedjan.py", "audit.py", "analys.py", "kallor.py")]
for fil, rad, text in fri_kvar:
    print("  [FEL] fri svensk text i %s:%d: %r" % (fil, rad, text[:90]))
ok(not fri_kvar, "inga svenska meddelanden kvar som fri text i jobb, kedja, audit, analys och källor")

# ---- 4. hashkedjan är språkoberoende -----------------------------------------------------------------------------
os.environ.setdefault("DASH_AUDIT_RETENTION", "50")
import audit  # noqa: E402
h = {"tid": "2026-10-11T10:00:00Z", "led": 3, "kalla": "x", "typ": "t", "resultat": "GODKAND",
     "kod": "audit.kov_godkand", "p": {}, "detaljer": {}}
sv_text = dict(h, text=meddelanden.visa("audit.kov_godkand", {}, "sv"))
en_text = dict(h, text=meddelanden.visa("audit.kov_godkand", {}, "en"))
ok(sv_text["text"] != en_text["text"] and audit._kanonisk(sv_text) == audit._kanonisk(en_text),
   "den kanoniska texten i hashkedjan är identisk oavsett språk (texten ingår inte)")

# ---- 5. renderingen i övrigt ---------------------------------------------------------------------------------------------
ok(meddelanden.visa("kov.fel_roll", {"funnen": "a", "kravd": "b"}, "en").startswith("The sender's verified role"),
   "parametrar fylls i på engelska")
_kon_en = meddelanden.visa("jobb.kon", {"id": "1", "tillstand": "REQUESTED", "pending": True, "beslut": "VANTANDE"}, "en")
_kon_sv = meddelanden.visa("jobb.kon", {"id": "1", "tillstand": "REQUESTED", "pending": True, "beslut": "VANTANDE"}, "sv")
ok(_kon_en.endswith("decision: WAITING") and "VANTANDE" not in _kon_en,
   "statuskoder i parametrar visas på engelska ({x|kod})")
ok(_kon_sv.endswith("KoV-beslut: väntar på beslut") and "VANTANDE" not in _kon_sv,
   "statuskoder i parametrar visas med svenska ord på svenska, inte som ASCII-kod ({x|kod})")
ok(meddelanden.visa("jobb.misslyckades", {"orsak": meddelanden.msg("fel.avtal_havt", avtal="A1")}, "en").startswith("FAILED: agreement A1 has been revoked"),
   "inbäddade meddelanden renderas på samma språk")
ok(meddelanden.visa("fri", {"text": "okänd åtgärd: x"}, "en") == "unknown action: x",
   "fri text går via reservöversättaren på engelska")
struktur = i18n.oversatt_struktur(meddelanden.till_sprak(
    {"text": "KoV GODKÄNDE utlämning av Distribution A", "kod": "audit.kov_godkand", "p": {}, "resultat": "GODKAND",
     "weirName": "Hovsmedsgatan"}, "en"))
par = i18n.oversatt_struktur({"p": {"forvantad": "Modellerad bräddata", "beslut": "VANTANDE"},
                              "parametrar": {"dataset": "Modellerad bräddata"}})
ok(par["p"]["forvantad"] == "Modellerad bräddata" and par["p"]["beslut"] == "VANTANDE"
   and par["parametrar"]["dataset"] == "Modellerad bräddata",
   "meddelandeparametrar (p, parametrar) översätts aldrig: de är språkoberoende data")
ok(struktur["text"] == "KoV APPROVED the release of Distribution A" and struktur["resultat"] == "GODKAND"
   and struktur["weirName"] == "Hovsmedsgatan",
   "API-träd: text omräknas, kod och data oförändrade")

sys.exit(1 if fel else 0)
