#!/usr/bin/env python3
"""Versionsnumret (K31, utan stack): SVADA_VERSION i .env är den enda källan, översta posten i nyheter.py har samma värde, formatet är
ÅÅÅÅ.MM.DD-N, posterna är nyast överst, och /nyheter, sidfoten och /api/status bär versionen. Körs från repots rot: python3 -I tests/version_enhet.py"""
import os
import re
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


env = {}
for rad in open(os.path.join(ROT, ".env"), encoding="utf-8"):
    m = re.match(r"^([A-Z_][A-Z0-9_]*)=([^\s#]*)", rad)
    if m:
        env[m.group(1)] = m.group(2)
ver = env.get("SVADA_VERSION", "")
os.environ["SVADA_VERSION"] = ver
sys.path.insert(0, os.path.join(ROT, "services", "dashboard"))
sys.path.insert(0, os.path.join(ROT, "services"))
import nyheter  # noqa: E402
import vy  # noqa: E402

kolla(bool(nyheter.MONSTER.match(ver)), "SVADA_VERSION i .env har formen ÅÅÅÅ.MM.DD-N (%s)" % ver)
kolla(nyheter.NYHETER[0][0] == ver, "översta posten i nyheter.py (%s) är samma version som .env (%s)" % (nyheter.NYHETER[0][0], ver))
versioner = [p[0] for p in nyheter.NYHETER]
kolla(len(set(versioner)) == len(versioner) and all(nyheter.MONSTER.match(v) for v in versioner), "alla versioner är unika och rätt formade")


def nyckel(v):
    d, n = v.split("-")
    return (d, int(n))


kolla(versioner == sorted(versioner, key=nyckel, reverse=True), "posterna ligger med nyaste versionen överst")
kolla(all(p[2] and all(len(x) == 2 and x[0] and x[1] for x in p[2]) for p in nyheter.NYHETER), "varje post har minst en rad, på både svenska och engelska")
for sprak in ("sv", "en"):
    kolla(ver in nyheter.sida(sprak) and "<h1>" in nyheter.sida(sprak), "/nyheter (%s) visar versionen" % sprak)
kolla(not any(k in nyheter.sida("sv") for k in ("localhost", "http://", "AP8", "etapp")), "/nyheter har inga interna hänvisningar eller adresser")
kolla('/nyheter?lang={sprak}' in open(os.path.join(ROT, "services/dashboard/vy.py"), encoding="utf-8").read() and vy.DEMO_VERSION == ver,
      "kontrollrummets sidfot länkar till /nyheter och bär versionen")
pv = open(os.path.join(ROT, "services/publik-vy/vy.py"), encoding="utf-8").read()
kolla("DEMO_VERSION" in pv and 'id="demoversion"' in pv, "brunnsvyns sidfot bär versionen")
kolla("SVADA_VERSION" in open(os.path.join(ROT, "compose.kontrollrum.yml"), encoding="utf-8").read()
      and "SVADA_VERSION" in open(os.path.join(ROT, "compose.stad.yml"), encoding="utf-8").read(), "compose skickar SVADA_VERSION till kontrollrummet och brunnsvyn")
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(min(fel, 99))
