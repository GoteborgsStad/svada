#!/usr/bin/env python3
"""Kontroller av den renderade kedjevyn (körs av tests/verify_kedjevy.sh).

Renderar sidan i processen, utan nätverk, i båda språken och båda varianterna
och prövar det som inte går att se från ett API:
  K10  inga interna projekthänvisningar i den externa varianten
  K14  inga portnummer i den externa varianten
  K2   båda språken renderas och <html lang> stämmer
  K5   bara ljust tema
  7    id/data-attribut som status, detaljer och verifieringen förutsätter
  8.9  ingen extern resurs
Skriver [OK]/[FEL] per kontroll och avslutar med antalet fel som exitkod.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services",
                                "dashboard"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
import kallor      # noqa: E402
import steg        # noqa: E402
import vy          # noqa: E402
from gemensam import rensa  # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text))
    if not ok:
        fel += 1


KOMP = [{"id": k["id"], "namn": k["namn"], "org": k["org"], "steg": k["steg"],
         "status": "upp", "adress": "", "detalj": "svarar"}
        for k in steg.KOMPONENTER]
# Publika adresser så som de ser ut på servern: domäner, inga portar.
PUBLIKA = [("kontrollrum", "https://demo.example.org"),
           ("brunnar", "https://brunnar.demo.example.org")]


def rendera(sprak, variant):
    return vy.sida(steg.STEG, KOMP, kallor.PORTAR, "localhost", 0.5,
                   PUBLIKA, sprak=sprak, variant=variant)


# Allt som visas för en besökare, utom <script> och <style>: texterna i
# sidan. (JavaScript-koden har egna identifierare men inga interna begrepp.)
FORBJUDET = [
    (r"\bAP[0-9]", "arbetspaketsbeteckning"),
    (r"\bG[0-9]{1,2}\b", "gap-id (G1, G22 …)"),
    (r"(?i)workshop", "workshop"),
    (r"(?i)hård regel", "hård regel"),
    (r"(?i)etapp", "etapp"),
    (r"§", "paragrafhänvisning"),
    (r"(?i)målarkitektur", "målarkitekturen"),
    (r"docs/|docs-archive|\.md\b", "dokumenthänvisning"),
    (r"(?i)komponent 14", "komponentnummer"),
]
PORTAR = [(r"(?:localhost|host\.docker\.internal|[a-z0-9-]+(?:\.[a-z0-9-]+)+|"
           r"(?:edc|orion|iot|fcf|ingest|identity|mintaka|ckan|mosquitto|sensor|"
           r"harvester|stad|dhi)[a-z-]*):[0-9]{2,5}\b", "värd:port"),
          (r"(?i)\bport(?:en)?\s+[0-9]{2,5}\b", "port NNNN")]

print("== Kedjevyn: rendering ==")
for sprak in vy.SPRAK:
    for variant in ("extern", "intern"):
        h = rendera(sprak, variant)
        kolla('<html lang="%s"' % sprak in h, "%s/%s: html lang=%s" % (sprak, variant, sprak))
        kolla("color-scheme: light;" in h and "prefers-color-scheme: dark" not in h,
              "%s/%s: bara ljust tema (K5)" % (sprak, variant))
        kolla(all('id="steg-%d"' % n in h and 'id="nod-%d"' % n in h
                  and 'data-stegstatus="%d"' % n in h
                  and 'data-detaljer="%d"' % n in h for n in range(1, 7)),
              "%s/%s: alla sex steg har panel, nod, status och detaljer" % (sprak, variant))
        kolla("data-komponent=" in h and 'ontoggle="oppnaExempel' in h and "data-atgard=" in h,
              "%s/%s: data-komponent, data-atgard och oppnaExempel finns" % (sprak, variant))
        kolla(not re.search(r"<(?:script|link|img|iframe)[^>]+(?:src|href)=[\"']https?://", h),
              "%s/%s: ingen extern resurs (skript, stilmall, bild, ram)" % (sprak, variant))
        kolla("@import" not in h and not re.search(r"url\(\s*[\"']?https?:", h),
              "%s/%s: inga externa typsnitt eller importer" % (sprak, variant))
    h = rendera(sprak, "extern")
    sida_text = re.sub(r"<style>.*?</style>", "", h, flags=re.S)
    # K10 ska gälla texten besökaren ser. Skriptets tryckta texter ingår
    # (de skrivs i sidan), men inte identifierare; de har inga träffar.
    for monster, namn in FORBJUDET:
        traffar = re.findall(monster, sida_text)
        kolla(not traffar, "%s/extern: inget om %s (K10)%s" % (
            sprak, namn, "" if not traffar else " – träffar: %r" % traffar[:3]))
    for monster, namn in PORTAR:
        traffar = re.findall(monster, sida_text)
        kolla(not traffar, "%s/extern: inga portnummer (%s, K14)%s" % (
            sprak, namn, "" if not traffar else " – träffar: %r" % traffar[:3]))

print("== Kedjevyn: stegtexter (K10, K12, K18–K21) ==")
alla = []
for s in steg.STEG:
    p = s["pedagogik"]
    for nyckel in ("vad", "varfor", "dataspace", "akta", "forenklat"):
        for sp in vy.SPRAK:
            alla.append(("steg %d %s %s" % (s["nr"], nyckel, sp), steg.text(p[nyckel], sp)))
    for aid, k in (p.get("knappar") or {}).items():
        for nyckel in ("gor", "titta", "kraver"):
            for sp in vy.SPRAK:
                alla.append(("%s %s %s" % (aid, nyckel, sp), steg.text(k[nyckel], sp)))
for namn, t in alla:
    t = t or ""
    if re.search(r"[A-Za-zåäöÅÄÖ]*datat\b", t):
        kolla(False, "%s: 'datat' ska vara 'data' (K19)" % namn)
    if re.search(r"(?i)\b(troligen|förmodligen|kanske|probably|presumably|maybe)\b", t):
        kolla(False, "%s: reservation (K12)" % namn)
    if re.search(r"(?i)\bstängd[a]? (version|distribution|data)", t):
        kolla(False, "%s: 'stängd' om A (K20)" % namn)
for sp in vy.SPRAK:
    for nyckel, t in vy.TEXTER[sp].items():
        if isinstance(t, str) and re.search(r"[A-Za-zåäöÅÄÖ]*datat\b", t):
            kolla(False, "gränssnittstext %s/%s: 'datat' ska vara 'data' (K19)" % (sp, nyckel))
kolla(True, "stegtexterna är genomsökta (%d texter)" % len(alla))
for nr, sv_start, en_start in ((2, "Så gör vi i PoC:en", "What we do in the PoC"),
                               (3, "Så gör vi i PoC:en", "What we do in the PoC"),
                               (4, "Så gör vi i PoC:en", "What we do in the PoC")):
    p = steg.STEG[nr - 1]["pedagogik"]
    kolla(steg.text(p["vad"], "sv").startswith("**" + sv_start)
          and steg.text(p["vad"], "en").startswith("**" + en_start),
          "steg %d: 'Vad händer?' börjar med '%s' (K21)" % (nr, sv_start))
    kolla(steg.text(p["dataspace"], "sv").startswith("**Gäller dataspace generellt")
          and steg.text(p["dataspace"], "en").startswith("**True of data spaces in general"),
          "steg %d: dataspace-rutan börjar med 'Gäller dataspace generellt' (K21)" % nr)
# Samordnarens utestängning (steg 3): intern variant har knapparna, extern har ett inspelat exempel, och flaggan `utestangning` tvingar det ena
# eller andra oavsett variant (granskningsfynd 2026-10-20: ingen kontroll visade att den interna varianten behåller knapparna).
_med = lambda **kw: vy.sida(steg.STEG, KOMP, kallor.PORTAR, "localhost", 0.5, PUBLIKA, sprak="sv", **kw)
_intern, _extern = _med(variant="intern"), _med(variant="extern")
kolla('id="svadatabell"' in _intern and 'id="svadatabell"' not in _extern and 'id="svadaprov"' in _extern,
      "samordnarrutan: intern variant har knapparna, extern har inga (utestängningen är avstängd externt)")
kolla('class="utdrag"' in _extern and 'class="utdrag"' not in _intern and "CatalogError" in _extern and "SvadaMembershipCredential" in _extern,
      "samordnarrutan: extern variant visar det inspelade exemplet (statuslista, 401, jobblogg), intern inte")
kolla('id="svadatabell"' in _med(variant="extern", utestangning=True) and 'id="svadatabell"' not in _med(variant="intern", utestangning=False),
      "samordnarrutan: flaggan utestangning tvingar knapparna på eller av oavsett variant")
kolla("avstängd i den publika demon" in _extern and "inte implementerad" not in _extern.lower(),
      "samordnarrutan (extern): säger att utestängningen är avstängd, inte att den saknas")

kolla(not steg.kontrollera_knapptackning(), "varje åtgärd har knapptext och roll på båda språken (K3)")
kolla("verkliga brunnar" not in str(steg.STEG[0]["pedagogik"]), "steg 1 påstår inte att brunnarna är verkliga")
for sp in vy.SPRAK:
    monster = r"påhittade" if sp == "sv" else r"made[- ]up"
    kolla(re.search(monster, steg.text(steg.STEG[0]["pedagogik"]["vad"], sp)),
          "%s: koordinaterna anges som påhittade i steg 1" % sp)

print("== Kedjevyn: portrensning rör inte tidsstämplar ==")
steg.UTAN_PORTAR = True
tid = "2026-10-06T17:19:12.951486Z 2026-07-17T00:00:00.000Z 2026-10-06T19:12Z"
kolla(steg.utan_portar(tid) == tid, "tidsstämplar förblir oförändrade av portrensningen")
kolla(steg.utan_portar("edc-provider:19193 http://host.docker.internal:39393/x")
      == "edc-provider http://host.docker.internal/x", "värd:port rensas")
kolla(steg.utan_portar('"did:web:identity-hub-stad%3A29197"') == '"did:web:identity-hub-stad"'
      and "19197" not in steg.utan_portar("did:web:identity-hub-dhi%3A19197"),
      "porten i en URL-kodad DID (%3A29197) rensas")
kolla(steg.utan_intern_adress(
    "når inte http://host.docker.internal:39193/management/kov/forhandlingar: refused")
    == "når inte /management/kov/forhandlingar: refused",
    "felmeddelande: värd och port bort, sökvägen kvar")
kolla(steg.utan_intern_adress("läser http://ckan:5000/catalog.ttl")
      == "läser /catalog.ttl", "containernamn (utan punkt) bort ur adressen")
kolla(steg.utan_intern_adress("https://katalog.demo.example.org/x")
      == "https://katalog.demo.example.org/x", "publika domäner rörs inte")
kolla(steg.utan_intern_adress(tid) == tid, "tidsstämplar rörs inte av adressrensningen")
steg.UTAN_PORTAR = False
kolla(steg.utan_intern_adress("http://host.docker.internal:39193/x")
      == "http://host.docker.internal:39193/x", "intern variant rensar ingenting")

# De publika ingångarnas port hör till adressen (gränssnittstestet 2026-10-17: texten i tabellen "Publika ingångar" och
# avtalsadresserna saknade :38080 och gick inte att öppna lokalt). Interna portar ska fortfarande bort.
steg.UTAN_PORTAR = True
os.environ["PUBLIK_URL_KONTROLLRUM"] = "http://svada-demo.localhost:38080"
kolla(steg.utan_portar("http://svada-demo.localhost:38080/avtal/x edc-provider:19193")
      == "http://svada-demo.localhost:38080/avtal/x edc-provider",
      "publika ingångens port bevaras, internt värd:port rensas")
kolla(steg.utan_intern_adress("se http://svada-demo.localhost:38080/avtal/x via http://edc-provider:19193/y")
      == "se http://svada-demo.localhost:38080/avtal/x via /y", "samma i adressrensningen")
_rad = vy._ingangar({}, "h", [("kontrollrum", "http://svada-demo.localhost:38080")],
                    {"pub_kontrollrum": "K", "ingangarRub": "R", "ingangarText": "T", "kolKomponent": "C", "kolAdress": "A"},
                    "sv", "extern")
kolla("<code>http://svada-demo.localhost:38080</code>" in _rad and 'href="http://svada-demo.localhost:38080"' in _rad,
      "tabellen Publika ingångar visar adressen med port, som länken")
# A2-07 (del a2): platshållaren går inte att förfalska, en bas skyddas bara vid URL-gräns, och interna portar efter
# userinfo rensas. Idempotent, och tider/UUID/URN rörs inte.
os.environ["PUBLIK_URL_BRUNNAR"] = "http://brunnar.svada-demo.localhost:38080"
kolla(rensa.utan_portar("\x00P0\x00 {abc_0}") == "\x00P0\x00 {abc_0}", "rensning: indata som liknar en platshållare blir ingen publik adress")
# Granskningsfynd 2026-10-19: platshållaren med kolon åts av portrensningen från den elfte adressen (37 % av anropen).
_tolv = " ".join("http://svada-demo.localhost:38080/avtal/%d" % i for i in range(12))
kolla(all(rensa.utan_portar(_tolv) == _tolv for _ in range(60)), "rensning: tolv publika adresser i samma text bevaras vid varje anrop (60 försök, platshållaren slumpas)")
kolla(rensa.utan_portar("http://svada-demo.localhost:380801/x") == "http://svada-demo.localhost:380801/x",
      "rensning: en bas med extra siffror (:380801) är inte den publika adressen")
kolla(not re.search(r":\d{2,5}\b", rensa.utan_portar("http://svada-demo.localhost:38080@edc-provider:19193/x")),
      "rensning: userinfo-trick (publik:38080@intern:19193) skyddas inte; båda portarna rensas")
kolla(rensa.utan_portar("http://brunnar.svada-demo.localhost:38080?lang=en och http://svada-demo.localhost:38080/avtal/1")
      == "http://brunnar.svada-demo.localhost:38080?lang=en och http://svada-demo.localhost:38080/avtal/1",
      "rensning: två publika baser och fråga/sökväg bevaras")
_r1 = rensa.utan_portar("se http://svada-demo.localhost:38080/x via edc-provider:19193 2026-10-17T13:21:22Z urn:ngsi-ld:X:1")
kolla(rensa.utan_portar(_r1) == _r1 and "2026-10-17T13:21:22Z" in _r1 and "urn:ngsi-ld:X:1" in _r1 and "19193" not in _r1,
      "rensning: idempotent, och tider och URN bevaras")
del os.environ["PUBLIK_URL_BRUNNAR"]
del os.environ["PUBLIK_URL_KONTROLLRUM"]
steg.UTAN_PORTAR = False


print("== Följ ett värde: felled på rätt språk (framtvingat fel, del e E5) ==")
# En connector som just startats om svarar 405 eller 5xx på sin management-endpoint: besökaren ser en förklaring, inte rå HTTP-text och intern sökväg.
print("== Källfel: connector som startar om ==")
import io
import urllib.error
_urlopen = kallor.urllib.request.urlopen


def _svara(status):
    def f(*a, **k):
        raise urllib.error.HTTPError("http://edc:1/management/v3/contractnegotiations/request", status, "x", {}, io.BytesIO(b'{"message":"HTTP method POST is not supported by this URL"}'))
    return f


for _st in (405, 503):
    kallor.urllib.request.urlopen = _svara(_st)
    try:
        kallor.anrop("http://edc:1/management/v3/contractnegotiations/request", "POST", {})
        _fel = None
    except kallor.KallFel as _e:
        _fel = _e
    kolla(_fel is not None and "inte färdigstartad" in str(_fel) and "/management/" not in str(_fel) and "not supported" not in str(_fel),
          "HTTP %d från en management-endpoint ger en förklarande text utan intern sökväg eller rå svarstext" % _st)
kallor.urllib.request.urlopen = _svara(404)
try:
    kallor.anrop("http://edc:1/management/v3/x", "POST", {})
except kallor.KallFel as _e:
    kolla("inte färdigstartad" not in str(_e), "ett vanligt 404 från en management-endpoint förklaras inte som en omstart")
kallor.urllib.request.urlopen = _svara(503)
try:
    kallor.anrop("http://orion:1/ngsi-ld/v1/entities", "GET")
except kallor.KallFel as _e:
    kolla("inte färdigstartad" not in str(_e), "bara management-endpoints får omstartstexten")
kallor.urllib.request.urlopen = _urlopen

_verklig_anrop = kallor.anrop
def _alltid_fel(*a, **k):
    raise kallor.KallFel("kunde inte nå källan (provfel utan kod)")
kallor.anrop = _alltid_fel
try:
    for _sp in ("en", "sv"):
        _f = steg.folj_vardet(_sp)
        _fel = [h for h in _f["hopp"] if h.get("fel")]
        _text = " ".join(h["innehall"] for h in _fel)
        if _sp == "en":
            kolla(len(_fel) >= 3 and not re.search(r"[åäöÅÄÖ]|kunde inte", _text),
                  "Följ ett värde (en): %d framtvingade felled, inget på svenska (%r)" % (len(_fel), _text[:80]))
        else:
            kolla(len(_fel) >= 3 and "kunde inte hämtas" in _text, "Följ ett värde (sv): felleden är på svenska")
finally:
    kallor.anrop = _verklig_anrop

print("== Gränssnittstestet 2026-10-18: Följ ett värde steg 4 (M7) och auditens förhandlingsstart (M6) ==")
import audit  # noqa: E402
_lev = kallor.ingest_leveranser
kallor.ingest_leveranser = lambda: {"counters": {}, "deliveries": [{"contractAgreementId": "B-avtal", "distribution": "B"},
                                                                   {"contractAgreementId": "A-avtal", "distribution": "A"}]}
kolla(steg._e4("sv", "B-avtal")["innehall"].count("B-avtal") == 1 and "A-avtal" not in steg._e4("sv", "B-avtal")["innehall"],
      "Följ ett värde steg 4: kvittot för trådens avtal (B), inte den senaste leveransen (A)")
kallor.ingest_leveranser = _lev
_forh = kallor.forhandlingar
def _poster(tillstand):
    return lambda limit=40: [{"@id": "f1", "createdAt": 1792300000000, "state": tillstand, "assetId": "modellerad-bradddata-a"}]
_h1, _h2 = [], []
kallor.forhandlingar = _poster("REQUESTED"); audit._forhandlingar(_h1, [])
kallor.forhandlingar = _poster("TERMINATED"); audit._forhandlingar(_h2, [])
kallor.forhandlingar = _forh
kolla(audit._kanonisk(_h1[0]) == audit._kanonisk(_h2[0]) and "tillstand" not in _h1[0]["p"] and _h1[0]["resultat"] == "PABORJAD",
      "auditens förhandlingsstart bär inte ett senare tillstånd och ändrar inte innehåll (hash) när tillståndet ändras")

_verklig2 = kallor.anrop
kallor.anrop = lambda *a, **k: {}                                   # tomma svar: inget har körts
try:
    _tomma = [h for h in steg.folj_vardet("sv")["hopp"] if h["steg"] in (2, 3, 4, 5)]
finally:
    kallor.anrop = _verklig2
kolla(_tomma and all(h["innehall"].startswith("Inget ännu") for h in _tomma),
      "Följ ett värde: tomma led säger 'Inget ännu' i stället för ett objekt med bara null (L15)")

print("== Kedjevyn: gemensam rensning (kontrollrum och skördare) ==")
URLLIB = ("kunde inte hämta http://ckan:5000/catalog.ttl: HTTPConnectionPool("
          "host='ckan', port=5000): Max retries exceeded with url: /catalog.ttl "
          "(Caused by NameResolutionError(\"Failed to resolve 'ckan' "
          "([Errno -2] Name or service not known)\"))")
ren = rensa.utan_intern_adress(URLLIB)
kolla(not re.search(r"ckan|5000", ren), "urllib3-texten (host='ckan', port=5000) rensas: %r" % ren[:70])
kolla("Max retries exceeded" in ren and "/catalog.ttl" in ren,
      "felets innehåll i övrigt finns kvar (sökväg och orsak)")
kolla(rensa.utan_intern_adress("Failed to connect to edc-provider/172.18.0.5:19194")
      == "Failed to connect to edc-provider/", "IPv4:port rensas helt (adress och port)")
kolla(rensa.utan_intern_adress('{"vard":"host.docker.internal"}') == '{"vard":""}',
      "host.docker.internal utan schema rensas")
kolla(rensa.utan_intern_adress("urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526 2026-10-06T17:19:12Z "
                               "ef83a1b2-0c3d-4e5f-8a9b-1c2d3e4f5a6b https://katalog.demo.example.org/x")
      == "urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526 2026-10-06T17:19:12Z "
         "ef83a1b2-0c3d-4e5f-8a9b-1c2d3e4f5a6b https://katalog.demo.example.org/x",
      "id:n, UUID:er, tidsstämplar och publika domäner rörs inte")
kolla(rensa.utan_portar("port=5000 a:5000") == " a",
      "utan_portar tar port=N och värd:N")


print("== Kedjevyn: tillgänglighet och texträttningar (granskningen 2026-10-06) ==")


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexfarg):
    h = hexfarg.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _kontrast(a, b):
    hi, lo = max(_lum(a), _lum(b)), min(_lum(a), _lum(b))
    return (hi + 0.05) / (lo + 0.05)


# Textfärgerna ska nå 7:1 mot varje bakgrund de ligger på (WCAG-formeln, handräknad
# i koden här). Ytorna är sidans vita bakgrund och de tonade fälten.
rot = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", vy.STIL))
ytor = {"vit": "#ffffff", "kod": rot["kod"], "ds-ton": rot["ds-ton"], "kedja-ton": rot["kedja-ton"],
        "bak": rot["bak"], "gul": "#fff4d6", "gron": "#e3f3e7"}
# Varje textfärg mot de bakgrunder den faktiskt ligger på i vyn.
BRUK = {"dov": ("vit", "kod", "ds-ton", "kedja-ton", "bak"), "kedja": ("vit", "kedja-ton"),
        "a": ("vit", "kod", "bak"), "ned": ("vit", "kod", "bak"), "b": ("vit", "kod", "bak", "gron"),
        "upp": ("vit", "kod", "bak"), "fokus": ("vit", "kod", "bak", "ds-ton"), "lank": ("vit", "kod", "bak"),
        "ds": ("vit", "ds-ton", "kod"), "vanta": ("vit", "bak", "gul")}
for namn, bakgrunder in BRUK.items():
    if namn not in rot:
        continue
    svagast = min((_kontrast(rot[namn], ytor[y]), y) for y in bakgrunder)
    kolla(svagast[0] >= 7.0, "kontrast: --%s %s når 7:1 mot sina bakgrunder (lägst %.2f mot %s)" % (
        namn, rot[namn], svagast[0], svagast[1]))
kolla(_kontrast(rot["gran"], "#ffffff") >= 7.0, "kontrast: --gran når 7:1 mot vitt (%.2f)" % _kontrast(rot["gran"], "#ffffff"))
for fg, bg in (("#6b4b00", "#fff4d6"), ("#165a27", "#e3f3e7"), ("#47514c", "#eef0ee")):
    kolla(_kontrast(fg, bg) >= 7.0, "kontrast: %s på %s når 7:1 (%.2f)" % (fg, bg, _kontrast(fg, bg)))

h_en = rendera("en", "extern")
h_sv = rendera("sv", "extern")
for fras in ("Staden frågar efter katalogen", "Skickas som en signerad JWT", "(stadens connector)", "(till DHI:s connector)", "(till DHI&#x27;s connector)", "(till "):
    kolla(fras not in h_en, "engelska sidan: ingen svensk förklaring i exemplen ('%s')" % fras)
kolla("Staden frågar efter katalogen" in h_sv, "svenska sidan: exemplen är kvar på svenska")
kolla('<nav id="flikar" aria-label="Flikar"' in h_sv and '<nav id="flikar" aria-label="Tabs"' in h_en,
      "flikradens namn är 'Flikar'/'Tabs', inte första flikens namn")
kolla("Vem kan tvinga fram vad?" in h_sv and "Who can force what?" in h_en,
      "steg 2: rutan om vem som kan tvinga fram vad finns på båda språken")
kolla("statusNamn" in h_sv and 'aria-label="1. ' in h_sv, "status har textnamn och stegradens knappar heter något")
kolla('"@type": "Set"' in vy._ODRL_A and '"rightOperand": "did:web:identity-hub-stad' in vy._ODRL_A
      and "odrl:eq" in vy._ODRL_A, "ODRL-exemplet för A följer policyfilen (Set, odrl:eq, stadens DID)")
kolla(h_sv.count('<li class="las">') == 7 and h_en.count('<li class="las">') == 7,
      "steg 2: sju lås listas på båda språken, med vem och steg")
kolla("Hävning av avtalet" in h_sv and "Revocation of the agreement" in h_en
      and "Filter i skördarna" not in h_sv and "harvesters" not in h_en,
      "låslistan har hävningen och saknar skördarfiltret (portalerna ingår inte)")
kolla("DSSC" in h_sv and "DSSC" in h_en and "DCAT" in h_sv and "DCAT" in h_en,
      "katalogtexten nämner DCAT (Dataspace Protocol bygger på det) och DSSC")
# Engelska sidan: inga svenska ord kvar i stegtexterna (efter att namn som "Kretslopp och Vatten"
# tagits bort), och inga föråldrade påståenden från tidigare versioner.
_SV_ORD = re.compile(r"\b(och|att|inte|som|är|för|med|ett|det|den|på|av|vi|kan|ska|till|från|eller|alla|när|hos|vid|bara|men|även|finns|varje|samt|också)\b", re.I)
_svenska = []
for _s in steg.STEG:
    _p = _s["pedagogik"]
    _en = [steg.text(_p.get(k), "en") for k in ("titel", "org", "vad", "varfor", "dataspace", "byggblock", "akta", "forenklat", "inga_knappar")]
    for _kn in (_p.get("knappar") or {}).values():
        _en += [steg.text(_kn.get(k), "en") for k in ("etikett", "gor", "titta", "kraver")]
    _en += [steg.text(_x.get("gor"), "en") for _x in _s["teknik"]]
    for _t in _en:
        if isinstance(_t, str):
            _t = _t.replace("Kretslopp och Vatten", "").replace("Kretslopp och vatten", "")
            _svenska += [(_s["nr"], m.group(0)) for m in _SV_ORD.finditer(_t)]
kolla(not _svenska, "engelska stegtexter: inga svenska ord kvar%s" % ("" if not _svenska else " – träffar: %r" % _svenska[:5]))
_en7 = str(steg.STEG[3]["pedagogik"].get("vad")) + str(steg.STEG[3]["pedagogik"].get("dataspace"))
kolla("so B carries none" not in _en7 and "The delivery carries the agreement's id" not in _en7,
      "steg 4 på engelska har inte de föråldrade påståendena (B bär inga positioner, leveransen bär avtalets id)")
for _sp, _ord in (("sv", ("verifierbara intyg", "VC", "DCP", "grundteknik")), ("en", ("verifiable credentials", "VC", "DCP", "basic technique"))):
    _t7 = steg.text(steg.STEG[3]["pedagogik"]["vad"], _sp) + steg.text(steg.STEG[3]["pedagogik"]["dataspace"], _sp)
    kolla(all(o.lower() in _t7.lower() for o in _ord), "steg 4 (%s): verifierbara intyg (VC), DCP och att det är en grundteknik står med" % _sp)
kolla("Identity & Attestation" in steg.text(steg.STEG[3]["pedagogik"]["byggblock"], "sv")
      and "Identity & Attestation" in steg.text(steg.STEG[3]["pedagogik"]["byggblock"], "en"),
      "steg 4: byggblocket Identity & Attestation är med")
kolla("tests" not in vy.TEXTER["sv"]["sehur"]["not"].lower() and "testerna" not in vy.TEXTER["en"]["sehur"]["not"].lower(),
      "anteckningen i 'Se hur det ser ut' hänvisar inte till testerna")

print("== Kedjevyn: engelska komponentnamn ==")
h = rendera("en", "extern")
kolla(all(t in h for t in ("stands in for DHI", "open data (K0R1T1)", "KoV gate (EDC extension at DHI)",
                           "connector (city)")), "teknikrutans beskrivande ord är på engelska")
kolla("står i för" not in h and "öppna data (K0R1T1)" not in h, "inga svenska delar kvar i teknikrutans namn (en)")

print("== Kedjevyn: ODRL i klartext ==")
pol = {"permission": [{"action": "odrl:use"}, {"action": "odrl:distribute"},
                      {"action": "odrl:publish"}],
       "prohibition": [], "obligation": []}
r = steg.odrl_klartext(pol, "sv")
kolla(len(r) == 3 and r[0][1].startswith("får användas"), "ODRL-klartext för B (sv)")
pol_a = {"permission": [{"action": "odrl:use", "constraint": [{
    "leftOperand": "https://x/ns/deltagare", "operator": "odrl:eq",
    "rightOperand": "did:web:identity-hub-stad%3A29197"}]}],
    "prohibition": [{"action": "odrl:distribute"}, {"action": "odrl:publish"}],
    "obligation": [{"action": "https://x/ns/kovGodkannande"}]}
ra = steg.odrl_klartext(pol_a, "en", extern=True)
kolla(len(ra) == 5 and "29197" not in str(ra) and "KoV must approve" in ra[-1][1],
      "ODRL-klartext för A (en), port bortrensad i extern variant")

# Intervallet i A: två villkor på samma operand visas med operatorsymbol (≥ / ≤), inte som två lika rader.
_pol_int = {"permission": [{"action": "odrl:use", "constraint": [
    {"leftOperand": "inForceDate", "operator": "odrl:gteq", "rightOperand": "contractAgreement+0s"},
    {"leftOperand": "inForceDate", "operator": "odrl:lteq", "rightOperand": "contractAgreement+30d"}]}],
    "prohibition": [], "obligation": []}
for _sp in ("sv", "en"):
    _t = str(steg.odrl_klartext(_pol_int, _sp))
    kolla("inForceDate ≥ " in _t and "inForceDate ≤ " in _t, "ODRL-intervallet visas med ≥ och ≤ (%s)" % _sp)

print("== Batch-datumet förklaras (backlog 32) ==")
kolla(steg._dygn_ur_batchid("batch-015-2026-06-29") == "2026-06-29" and steg._dygn_ur_batchid(None) == "–" and steg._dygn_ur_batchid("batch-x") == "–",
      "datumet ur batch-id:t läses som det modellerade dygnet (och ger – när det saknas)")
for _sp in ("sv", "en"):
    _t = steg.text(steg.STEG[0]["pedagogik"]["knappar"]["kor-batch"]["titta"], _sp)
    kolla(("modellerade dygnet" if _sp == "sv" else "modelled day") in _t and ("inte när den kördes" if _sp == "sv" else "not when it was run") in _t,
          "steg 1 (%s): texten säger att datumet i batch-id:t är det modellerade dygnet, inte när batchen kördes" % _sp)
_by0 = {x["id"]: x for x in vy.ORDLISTA}
kolla("batch-015-2026-06-29" in _by0["batch"]["sv"]["def"] and "batch-015-2026-06-29" in _by0["batch"]["en"]["def"] and "modellerat-dygn" in _by0,
      "ordlistan: Batch förklarar datumet och Modellerat dygn är ett eget begrepp")
kolla("Modellerat dygn (datumet i batch-id:t)" in steg._ENG if hasattr(steg, "_ENG") else True, "raden för det modellerade dygnet har en engelsk etikett")
print("== Stadens gateway (cip.): avslagssidan på två språk ==")
import importlib.util
_sp = importlib.util.spec_from_file_location("gateway_vy", os.path.join(os.path.dirname(__file__), "..", "services", "stad-gateway", "vy.py"))
_gv = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_gv)


class _Fel:
    orsak = "atkomst-kraver-godkannande"
    detalj = "Avtal saknas"


_s = _gv.avslag(_Fel(), "/ngsi-ld/v1/entities", "https://x", "", "https://y", "https://z", "sv")
_e = _gv.avslag(_Fel(), "/ngsi-ld/v1/entities", "https://x", "", "https://y", "https://z", "en")
kolla("Åtkomst nekad" in _s and "Så får du åtkomst" in _s and 'lang="sv"' in _s and "Access denied" not in _s, "cip.-sidan på svenska är svensk")
kolla("Access denied" in _e and "How to get access" in _e and 'lang="en"' in _e and "Åtkomst nekad" not in _e and "Så får du" not in _e and "Göteborgs Stad" not in _e,
      "cip.-sidan på engelska är engelsk (inga svenska rubriker, 'City of Gothenburg')")
kolla("?lang=en" in _s and "?lang=sv" in _e, "cip.-sidan har en språkväxlare åt båda hållen")
print("== Testläge ==")
_h = rendera("sv", "extern")
kolla('id="testlage"' in _h and "svada-test=1" in _h and "räknas inte i statistiken" in _h, "sidfoten har en markering för testläget som visas när kakan svada-test=1 finns")

print("== Ordlistan: länkar och begrepp ==")
_ids = [o["id"] for o in vy.ORDLISTA]
kolla(len(set(_ids)) == len(_ids), "ordlistan: alla begrepp har unika id")
kolla(all(o["lank"].startswith("https://") for o in vy.ORDLISTA if o.get("lank")), "ordlistan: alla länkar är https")
kolla({"dcat", "dcatbegrepp", "dcp", "intyg"} <= set(_ids) and "vc" not in _ids, "ordlistan: DCAT, DCAT-AP-SE, DCP och Verifierbart intyg är egna begrepp (VC är en förkortning under Verifierbart intyg)")
for _id in ("dcatbegrepp", "dcp", "intyg", "dcat", "fcf", "dhi"):
    _o = _ordl[_id] if "_ordl" in globals() else {x["id"]: x for x in vy.ORDLISTA}[_id]
    kolla(_o.get("lank") and all(_o[_s]["def"] and _o[_s]["term"] for _s in ("sv", "en")), "ordlistan: %s har länk och definition på båda språken" % _id)
_rx = lambda o, sp: re.compile(o[sp]["re"].replace(chr(92) + "p{L}", "A-Za-zåäöÅÄÖ").replace(chr(92) + "p{N}", "0-9"))      # bara för mönster där \p{..} står i en teckenklass
_by = {x["id"]: x for x in vy.ORDLISTA}
kolla(_rx(_by["dcatbegrepp"], "sv").search("beskrivs i DCAT i katalogen") and not _rx(_by["dcatbegrepp"], "sv").search("DCAT-AP-SE")
      and _rx(_by["dcat"], "sv").search("DCAT-AP-SE"), "ordlistan: DCAT matchar bara fristående DCAT, DCAT-AP-SE har sitt eget begrepp")

print("== Om demon: projektet, upphovspersoner och Blueprint ==")
for _sp, _ord in (("sv", ("Arbetet sker inom Vattendatalabbet", "https://vattendatalabbet.se/", "Energimyndigheten, Formas, Vinnova och Water Wise Societies", "Blueprint 3.0")),
                  ("en", ("The work is done within the Swedish Water Data Lab", "https://vattendatalabbet.se/", "Swedish Energy Agency", "Blueprint 3.0"))):
    for _var in ("intern", "extern"):
        _h = rendera(_sp, _var)
        _om = _h[_h.find('<section id="om"'):_h.find('<section id="ordlista"')]
        kolla(all(o in _om for o in _ord) and "Björn Hagström" in _om and "Niklas Fjellman" in _om
              and 'href="https://dssc.eu/"' in _om and "vinnova.se/en/p/the-swedish-water-data-lab-svada" in _om,
              "Om-sidan (%s, %s): projektet SVADA, finansiärer, upphovspersoner, Blueprint 3.0 och länkarna" % (_sp, _var))
        kolla(all(('rel="noopener"' in x) for x in re.findall(r'<a [^>]*target="_blank"[^>]*>', _om)), "Om-sidan (%s, %s): externa länkar har rel=noopener" % (_sp, _var))

print("== Avtal gäller tills de hävs (avtal-havning) ==")
for _sp, _ord in (("sv", ("KoV häver avtalet", "gäller tills det hävs", "Så fungerar PoC:en", "olika")),
                  ("en", ("KoV revokes the agreement", "valid until it is revoked", "How the PoC works", "differs"))):
    _h = rendera(_sp, "intern")
    kolla("data-kovbeslut=\"hav\"" in _h, "KoV-rutan har en Häv-knapp (%s)" % _sp)
    kolla(all(o in _h for o in _ord), "hävningstexterna står med på %s: %s" % (_sp, ", ".join(_ord)))
    kolla("id=\"avtallista\"" in _h, "avtalslistan finns på fliken Suveränitet (%s)" % _sp)
_p3 = str(steg.STEG[2]["pedagogik"])
kolla("round trip" not in _p3 and "hemresa" not in _p3, "steg 3: formuleringen om hemresa/round trip är borta")
kolla("stays valid" not in _p3 and "fortsätter att gälla" not in _p3,
      "steg 3: inget påstående att ett tidigare avtal består efter ett avslag")
# Webinariet 2026-10: villkoren sätts av ägaren och binder mottagaren; för A tar Intraservice emot på KoV:s uppdrag.
for _sp in ("sv", "en"):
    _v3 = str(steg.STEG[2]["pedagogik"]["varfor"][_sp])
    kolla(("binder mottagaren" if _sp == "sv" else "bind the recipient") in _v3
          and ("på KoV:s uppdrag" if _sp == "sv" else "on KoV's behalf") in _v3
          and ("samma part" not in _v3 and "same party" not in _v3),
          "steg 3 (%s): villkoren binder mottagaren, Intraservice tar emot på KoV:s uppdrag (inte 'samma part')" % _sp)
    _a3 = steg.text(steg.STEG[2]["pedagogik"]["akta"], _sp)
    kolla(("Hävningen är också riktig" if _sp == "sv" else "Revocation is real too") in _a3,
          "steg 3 (%s): Äkta säger att hävningen av avtal är riktig (webinariet p7)" % _sp)
    _f3 = steg.text(steg.STEG[2]["pedagogik"]["forenklat"], _sp)
    kolla(all(o in _f3 for o in (("I PoC:en ligger avtal och KoV-beslut bara i minnet", "avtalsregister", "diarieförs")
                                 if _sp == "sv" else ("In the PoC, agreements and KoV decisions are kept only in memory",
                                                      "agreement register", "filed in the city's records"))),
          "steg 3 (%s): Förenklat säger var avtal och KoV-beslut ligger i PoC:en och att avtal i drift diarieförs (webinariet p9)" % _sp)
_ordl = {o["id"]: o for o in vy.ORDLISTA}
kolla("binder" in _ordl["kov"]["sv"]["def"] and "på KoV:s uppdrag" in _ordl["intraservice"]["sv"]["def"]
      and "bind" in _ordl["kov"]["en"]["def"] and "on KoV's behalf" in _ordl["intraservice"]["en"]["def"],
      "ordlistan: KoV sätter villkoren som binder mottagaren, Intraservice tar emot på KoV:s uppdrag")
kolla(all(a in steg.STEG[2]["pedagogik"]["knappar"] for a in ("kov-godkann", "kov-avsla", "kov-hav")),
      "steg 3 har tre KoV-knappar: godkänn, avslå, häv")
kolla("var jobbAktivtNu" not in _h and "function kovKnappar()" in _h,
      "KoV-knapparnas tillstånd sätts av en enda funktion (kovKnappar)")

print("== Svada-mini: sex steg, inga portaler eller sensorled ==")
kolla([x["nr"] for x in steg.STEG] == [1, 2, 3, 4, 5, 6], "kedjan har sex steg")
for _sp in ("sv", "en"):
    _hh = rendera(_sp, "intern")
    _sida = re.sub(r"<script.*?</script>|<style.*?</style>", "", _hh, flags=re.S)
    _sida = re.sub(r'href="[^"]*"', "", _sida)      # länkar till standarddokumentation räknas inte
    _borta = re.findall(r"(?i)\b(ckan|harvester\w*|skördar\w*|mosquitto|iot agent|orion-dhi|mqa|data\.europa\.eu|dataportal\w*)\b", _sida)
    kolla(not _borta, "%s: inget om portaler, CKAN, sensorled eller MQTT i sidan%s" % (_sp, "" if not _borta else " – träffar: %r" % sorted(set(_borta))[:6]))
    kolla('id="analysruta"' in _hh and "function laddaAnalys(" in _hh and 'name="analyslage"' in _hh,
          "%s: steg 6 har inspektionsprioriteringen (analysruta, laddaAnalys, val av distribution)" % _sp)
    # Webinariet p12 (K18, K20): B före A där båda nämns, och "känslig" är inget namn på en distribution.
    _ab = re.findall(r"(?i)\b(?:distributions?|distributionerna|i)?\s?A (?:och|and) B\b|[Dd]istribution A känslig|B-distribution",
                     _sida)
    kolla(not _ab, "%s: B nämns före A och 'känslig' är inget namn på A (webinariet p12)%s" % (_sp, " – träffar: %r" % _ab[:5] if _ab else ""))
    _jb = _hh.find('id="brunnjamfor"')
    kolla(_jb > _hh.find('id="analysruta"') > 0 and "laddaBrunnJamforelse();" in _hh
          and "sida('B'" in _hh and _hh.find("sida('B'") < _hh.find("sida('A'"),
          "%s: steg 6 visar samma brunn i B och A sida vid sida, B först (webinariet p3, K20)" % _sp)
    kolla('data-flik="avvikelse"' not in _hh and 'id="avvikelse"' not in _hh and 'id="fair"' not in _hh,
          "%s: flikarna Avvikelse och FAIR finns inte kvar" % _sp)
_p6 = steg.STEG[5]["pedagogik"]
kolla("lämnar" not in steg.text(_p6["forenklat"], "sv") and "bräddtiden är lika" in steg.text(_p6["forenklat"], "sv"),
      "steg 6 säger öppet att bräddtiden är lika för alla brunnar och inte används")
kolla(steg.komponenter_for(6) == steg.komponenter_for(5) and steg.komponenter_for(6),
      "steg 6 har stadens plattforms status (inga egna komponenter)")


# ---- Varje API-sökväg som sidans skript anropar finns som rutt i main.py ----------------------------------
# (En omnumrerad rutt, /api/steg/8/ursprung -> /api/steg/5/ursprung, lämnade vyn med ett anrop mot 404 utan att
#  något test märkte det.)
import re as _re
_main = open(os.path.join(os.path.dirname(__file__), "..", "services", "dashboard", "main.py"), encoding="utf-8").read()
_rutter = [_re.sub(r"\(\?:[^)]*\)", "[^/]+", r) for r in _re.findall(r'@app\.(?:get|post)\("(/[^"]*)"', _main)]
_saknas = []
for _sokvag in _re.findall(r"api\(\s*[`'\"](/api/[^`'\"$?]*)", vy.SKRIPT):
    _stam = _sokvag.rstrip("/")
    if not any(_re.fullmatch(r, _sokvag) or _re.fullmatch(r, _stam) or r.startswith(_stam + "/") for r in _rutter):
        _saknas.append(_sokvag)
kolla(not _saknas, "varje api('/api/…') i sidans skript har en rutt i main.py" + (" – saknas: %s" % _saknas if _saknas else ""))


# ---- Webinariet 2026-10, punkt 4: värdet i CIP bredvid avtalet (id, distribution, status, villkor i klartext) ----
import json as _json
_pol_b = _json.load(open(os.path.join(os.path.dirname(__file__), "..", "edc", "bootstrap", "policy-distribution-b.json"),
                         encoding="utf-8"))
_pol_b = _pol_b.get("policy", _pol_b)
_g = (kallor.orion_stad_brunn, kallor.avtal, kallor.avtalsregister)
kallor.orion_stad_brunn = lambda: {"id": kallor.BRUNN_ID, "type": "SewerOverflowModelB", "overflowVolumeM3": 1.5,
                                   "provenance": {"value": {"contractAgreementId": "AV1", "distribution": "B"}}}
# Avtalets policy i den form stadens connector faktiskt svarar med (odrl:-prefix, actions som {"@id": ...}); en stubbe
# i katalogens form dolde att klartexten blev tom mot den riktiga stacken.
_pol_avtal = {"permission": [{"odrl:action": {"@id": "odrl:use"}, "odrl:duty": {"odrl:action": {"@id": "odrl:attribute"}}},
                             {"odrl:action": {"@id": "odrl:distribute"}}, {"odrl:action": {"@id": "odrl:publish"}}]}
kolla(steg.odrl_klartext(steg._kompakt_odrl(_pol_avtal)) == steg.odrl_klartext(_pol_b),
      "avtalets policy (management-API:ts form) ger samma klartext som katalogens policy för B")
kallor.avtal = lambda aid: {"@id": aid, "assetId": kallor.ASSET_B, "providerId": "p", "consumerId": "c",
                            "contractSigningDate": 1, "policy": _pol_avtal}
kallor.avtalsregister = lambda: {"avtal": [{"id": "AV1", "status": "GALLANDE", "url": "http://x/avtal/AV1"}]}
for _sp, _ord in (("sv", "får användas …"), ("en", "may be used …")):
    _u = steg.ursprung_b(extern=True, sprak=_sp)
    _v, _a = _json.loads(_u["varde"]), _json.loads(_u["avtal"].split("\n", 1)[1])
    kolla(_v["provenance"]["contractAgreementId"] == _a["@id"] == "AV1" and _a["distribution"] == "B"
          and _a["status"] == "GALLANDE" and len(_a["villkorIKlartext"]) == 4
          and any(_ord in r for r in _a["villkorIKlartext"]) and "policy" in _a,
          "%s: steg 5 visar värdets contractAgreementId bredvid avtalet med id, distribution, status och villkor i klartext" % _sp)
kallor.orion_stad_brunn, kallor.avtal, kallor.avtalsregister = _g
kolla("ursprung?lang=" in vy.SKRIPT, "sidan ber om avtalets klartext på sitt eget språk")

sys.exit(min(fel, 99))
