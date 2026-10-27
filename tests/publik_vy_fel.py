#!/usr/bin/env python3
"""Körs INUTI publik-vy-containern (docker exec -i ... python - < tests/publik_vy_fel.py).

Simulerar HTTP-fel och anslutningsfel från Mintaka och kontrollerar hela feltexten för båda rutterna på båda språken:
rätt språk, ingen svarskropp eller undantagstext (de kan bära interna adresser), ingen port."""
import sys
import urllib.error

sys.path.insert(0, "/app")
import main  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


class Begaran:
    def __init__(self, sprak):
        self.query_params = {"lang": sprak} if sprak == "en" else {}
        self.headers = {"accept": "text/html"}
        self.cookies = {}


def http_fel(*a, **k):
    raise urllib.error.HTTPError("http://mintaka:8080/x", 500, "Server Error", {}, None)


def nat_fel(*a, **k):
    raise urllib.error.URLError("[Errno 111] Connection refused http://mintaka:8080")


SVENSKA = ("Kunde inte hämta", "svarade", "gick inte att nå")
ENGELSKA = ("Could not fetch", "responded with", "could not be reached")
for namn, simulering, delstrang in (("HTTP-fel", http_fel, "500"), ("anslutningsfel", nat_fel, None)):
    main.urllib.request.urlopen = simulering
    for rutt, anrop in (("/brunnar", lambda b: main.brunnar(b)), ("/brunnar/{id}", lambda b: main.en_brunn("SSO1_01-4526", b))):
        for sprak in ("sv", "en"):
            html = anrop(Begaran(sprak)).body.decode("utf-8")
            ratt, fel_spr = (SVENSKA, ENGELSKA) if sprak == "sv" else (ENGELSKA, SVENSKA)
            kolla(any(t in html for t in ratt) and not any(t in html for t in fel_spr),
                  "%s %s (%s): rubrik och feltext på rätt språk" % (namn, rutt, sprak))
            kolla("mintaka:8080" not in html and "Connection refused" not in html and "Errno" not in html,
                  "%s %s (%s): ingen intern adress eller undantagstext" % (namn, rutt, sprak))
            if delstrang:
                kolla(delstrang in html, "%s %s (%s): felkoden redovisas" % (namn, rutt, sprak))

# Okänd brunn: 404 med "ingen data" (inget Tjänstefel, ingen intern komponent), ogiltigt id når aldrig Mintaka, och ett urn: av annan typ pekar aldrig utanför den öppna typen.
anropade = []


def mintaka_404(begaran, *a, **k):
    anropade.append(begaran.full_url if hasattr(begaran, "full_url") else begaran)
    raise urllib.error.HTTPError("http://mintaka:8080/x", 404, "Not Found", {}, None)


main.urllib.request.urlopen = mintaka_404
for sprak in ("sv", "en"):
    svar = main.en_brunn("SSO1_99-0000", Begaran(sprak))
    html = svar.body.decode("utf-8")
    kolla(svar.status_code == 404 and "Mintaka" not in html and "Tjänstefel" not in html and "Service error" not in html
          and "/brunnar?lang=%s" % sprak in html, "okänd brunn (%s): 404, ingen Mintaka i texten, länk tillbaka" % sprak)
anropade.clear()
for ogiltigt in ("SSO1_01-4526\n", "x y", "a/b", "x" * 200, "urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526:evil?x=1"):
    svar = main.en_brunn(ogiltigt, Begaran("sv"))
    kolla(svar.status_code == 404, "ogiltigt id %r ger 404" % ogiltigt[:20])
kolla(not anropade, "ogiltiga id når aldrig Mintaka")
main.en_brunn("urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526", Begaran("sv"))
kolla(all("SewerOverflowModelA" not in str(u) for u in anropade) or not anropade,
      "ett urn: av en annan entitetstyp (A) frågas aldrig hos Mintaka")

# Språkriktiga tal och rubriker (gränssnittstestet 2026-10-17: decimalpunkt i svensk vy, råa attributnamn som kolumnrubriker).
import vy  # noqa: E402
kolla(vy._tal("653.8", "sv") == "653,8" and vy._tal("653.8", "en") == "653.8" and vy._tal("12", "sv") == "12"
      and vy._tal("2026-10-17T13:21:22Z", "sv") == "2026-10-17T13:21:22Z", "tal: decimalkomma på svenska, punkt på engelska, tider orörda")
_serie = [{"observedAt": "2026-10-17T00:00:00Z", "overflowVolumeM3": 591.53, "inflowMeanM3S": 0.25}]
for _sp, _fras in (("sv", "Bräddad volym (m³) <code>overflowVolumeM3</code>"), ("en", "Overflow volume (m³) <code>overflowVolumeM3</code>")):
    _html = vy.brunn("SSO1_01-4526", _serie, "http://x/y", "http://k", _sp)
    kolla(_fras in _html, "brunn (%s): kolumnrubriken är på språket och attributnamnet finns kvar i <code>" % _sp)
kolla("591,53" in vy.brunn("SSO1_01-4526", _serie, "http://x/y", "http://k", "sv"), "brunn (sv): värdet visas med decimalkomma")
# Testläge: sidfoten i brunnsvyn säger det när kakan svada-test=1 finns, och inte annars
class _KakBegaran(Begaran):
    def __init__(self, sprak, kakor):
        super().__init__(sprak)
        self.cookies = kakor


_ren = "<html><footer><p>x</p></footer></html>"
kolla("Testläge" in main._med_testlage(_KakBegaran("sv", {"svada-test": "1"}), _ren) and "id=\"testlage\"" in main._med_testlage(_KakBegaran("sv", {"svada-test": "1"}), _ren),
      "brunnsvyn: sidfoten säger Testläge när kakan svada-test=1 finns")
kolla("Test mode" in main._med_testlage(_KakBegaran("en", {"svada-test": "1"}), _ren), "brunnsvyn: testläget på engelska")
kolla(main._med_testlage(_KakBegaran("sv", {}), _ren) == _ren and main._med_testlage(_KakBegaran("sv", {"svada-test": "0"}), _ren) == _ren, "brunnsvyn: ingen markering utan kakan")
# Caddy sätter kakan på samma svar som ?test=1/?test=0 kommer med: frågeparametern gäller före kakan (annars låg sidfoten ett sidbyte efter).
_pa = _KakBegaran("sv", {}); _pa.query_params = {"test": "1"}
_av = _KakBegaran("sv", {"svada-test": "1"}); _av.query_params = {"test": "0"}
kolla("id=\"testlage\"" in main._med_testlage(_pa, _ren), "brunnsvyn: ?test=1 visar Testläge direkt, även utan kaka")
kolla(main._med_testlage(_av, _ren) == _ren, "brunnsvyn: ?test=0 tar bort Testläge direkt, även om kakan ännu finns")
# Felsidorna har ingen sidfot: Testläge hamnar före </body> (provrunda 2026-10-26, granskningen).
_kb = _KakBegaran("sv", {"svada-test": "1"})
kolla('id="testlage"' in main._fel(_kb, "x").body.decode(), "brunnsvyn: Testläge syns även på tjänstefelsidan (502)")
_kb404 = _KakBegaran("sv", {"svada-test": "1"}); _kb404.headers = {"accept": "text/html"}
_svar404 = __import__("asyncio").run(main.http_fel(_kb404, main.StarletteHTTPException(404, "Not Found")))
kolla('id="testlage"' in _svar404.body.decode(), "brunnsvyn: Testläge syns även på 404-sidan")
kolla('id="testlage"' not in main._fel(_KakBegaran("sv", {}), "x").body.decode(), "brunnsvyn: ingen markering på felsidan utan testläge")
sys.exit(min(fel, 99))
