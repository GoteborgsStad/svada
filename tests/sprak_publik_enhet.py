#!/usr/bin/env python3
"""K33b (utan stack, utan beroenden): språkvalet efter webbläsaren är samma regel i kontrollrummet, brunnsvyn och stadens gateway.
Funktionen onskat_sprak ska ha identisk text i de tre tjänsterna (de byggs i egna Docker-kontexter), och brunnsvyns och gatewayens
språkordning (?lang= först, sedan kakan svada-sprak, sist webbläsaren) provas genom att läsa ut funktionerna ur källan."""
import ast
import os
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILER = {"kontrollrummet": "services/dashboard/main.py", "brunnsvyn": "services/publik-vy/main.py", "gatewayen": "services/stad-gateway/main.py"}
fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    if not villkor:
        fel += 1


def funktion(fil, namn, namnrymd=None):
    kalla = open(os.path.join(ROT, fil), encoding="utf-8").read()
    for nod in ast.parse(kalla).body:
        if isinstance(nod, ast.FunctionDef) and nod.name == namn:
            text = ast.get_source_segment(kalla, nod)
            ns = namnrymd if namnrymd is not None else {}
            exec(compile(text, fil, "exec"), ns)
            return text, ns[namn]
    return None, None


print("== Samma regel i de tre tjänsterna ==")
texter = {}
for vem, fil in FILER.items():
    texter[vem], f = funktion(fil, "onskat_sprak")
    kolla(f is not None, "%s har onskat_sprak" % vem)
kolla(len(set(texter.values())) == 1, "onskat_sprak har identisk text i de tre tjänsterna")
_, onskat = funktion(FILER["gatewayen"], "onskat_sprak")
for huvud, vantat in (("sv-SE,sv;q=0.9,en;q=0.8", "sv"), ("en-US,en;q=0.9,sv;q=0.8", "en"), ("de-DE", "en"), ("en;q=0.5,sv;q=0.9", "sv"),
                      ("sv;q=0, en", "en"), ("*", "sv"), ("", "sv"), (None, "sv"), ("q=abc,en", "en"), ("en;q=nan, sv", "sv"), ("x" * 20000, "en")):
    kolla(onskat(huvud) == vantat, "%r -> %s" % ((huvud or "")[:30], vantat))


class Beg:
    def __init__(self, q=None, h=None, c=None):
        self.query_params, self.headers, self.cookies = q or {}, h or {}, c or {}


print("== Ordningen: ?lang= först, sedan kakan, sist webbläsaren ==")
ns = {"onskat_sprak": onskat}
_, sprak = funktion(FILER["brunnsvyn"], "_sprak", ns)
_, avslag = funktion(FILER["gatewayen"], "_avslagssprak", ns)
for namn, f in (("brunnsvyn", sprak), ("gatewayen", avslag)):
    kolla(f(Beg(h={"accept-language": "en-US"})) == "en", "%s: engelsk webbläsare utan val ger engelska" % namn)
    kolla(f(Beg(h={"accept-language": "sv-SE"})) == "sv", "%s: svensk webbläsare ger svenska" % namn)
    kolla(f(Beg()) == "sv", "%s: utan huvud ger svenska" % namn)
    kolla(f(Beg(h={"accept-language": "en-US"}, c={"svada-sprak": "sv"})) == "sv", "%s: kakan går före webbläsaren" % namn)
    kolla(f(Beg(q={"lang": "sv"}, h={"accept-language": "en-US"}, c={"svada-sprak": "en"})) == "sv", "%s: ?lang= går före kakan och webbläsaren" % namn)
    kolla(f(Beg(q={"lang": "xx"}, h={"accept-language": "en-US"})) == "en", "%s: okänt ?lang= ignoreras" % namn)
    kolla(f(Beg(c={"svada-sprak": "xx"}, h={"accept-language": "en-US"})) == "en", "%s: okänd kaka ignoreras" % namn)

print("RESULTAT:", "OK: alla prov gröna" if fel == 0 else "%d fel" % fel)
sys.exit(min(fel, 99))
