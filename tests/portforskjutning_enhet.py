#!/usr/bin/env python3
"""K32 (utan stack): portförskjutningen (tools/portforskjutning.py) flyttar exakt värdportarna och inget annat.

Kontrollerar att klassningen av portvariablerna stämmer mot compose-filerna (en ny portvariabel som ingen har klassat fäller provet), att
interna portar aldrig står på värdsidan i en publicering, att en förskjutning ger en .env där alla värdportar är flyttade lika mycket och
DEMO_URL_PORT följer Caddyporten, att förskjutning 0 inte ändrar något, och att fel upptäcks. Körs från repots rot: python3 -I tests/portforskjutning_enhet.py"""
import glob
import os
import re
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROT, "tools"))
import portforskjutning as pf  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


publicerade = set(pf.varden_porter_ur_compose(ROT))
# Utan .env (en nyklonad kopia före tools/forsta-start.sh) provas mallen .env.exempel, som har samma portvariabler.
ENV_FIL = os.path.join(ROT, ".env") if os.path.exists(os.path.join(ROT, ".env")) else os.path.join(ROT, ".env.exempel")
rader = pf.las_env(ENV_FIL)
portvar = sorted({m.group(1) for r in rader for m in [re.match(r"^([A-Z][A-Z0-9_]*PORT[A-Z0-9_]*)=", r)] if m})

kolla(len(publicerade) >= 28 and {"DASHBOARD_PORT", "IDENTITY_HUB_STAD_STS_PORT", "CADDY_HTTP_PORT", "EDC_CONSUMER_MGMT_PORT"} <= publicerade,
      "värdportarna läses ur compose-filerna (%d st), inklusive kontrollrummet, Caddy, EDC och stadens STS" % len(publicerade))
kolla(not (pf.INTERNA & publicerade), "ingen port som klassats som intern står på värdsidan i en publicering (%s)" % sorted(pf.INTERNA & publicerade))

oklassade = [v for v in portvar if v not in publicerade and v not in pf.INTERNA and v not in pf.KOPPLADE]
kolla(not oklassade, "varje portvariabel i .env är klassad som värdport, intern eller kopplad (oklassade: %s)" % oklassade)

# En variabel som används i en adress mellan containrar (http://tjänst:${PORT}) är en intern port och får inte vara en värdport.
mellan_container = set()
for fil in glob.glob(os.path.join(ROT, "compose.*.yml")):
    for m in re.finditer(r"://(?!localhost)[a-z][a-z0-9-]*:\$\{([A-Z][A-Z0-9_]*)\}", open(fil, encoding="utf-8").read()):
        mellan_container.add(m.group(1))
kolla(not (mellan_container & publicerade), "ingen värdport används i en adress mellan containrar (%s)" % sorted(mellan_container & publicerade))

nya, andringar, f = pf.forskjut(rader, 1000, "svadatest")
kolla(not f, "förskjutning 1000 ger inga fel (%s)" % f)


def portar(rs):
    return {m.group(1): int(m.group(2)) for r in rs for m in [re.match(r"^([A-Z][A-Z0-9_]*PORT[A-Z0-9_]*)=(\d+)", r)] if m}


gamla, nyar = portar(rader), portar(nya)
kolla(all(nyar[v] == gamla[v] + 1000 for v in publicerade if v in gamla), "alla värdportar är flyttade exakt +1000")
kolla(all(nyar[v] == gamla[v] for v in gamla if v not in publicerade), "alla övriga portvariabler är oförändrade")
kolla(not ({nyar[v] for v in publicerade if v in nyar} & set(gamla.values())), "de nya värdportarna krockar inte med någon av de gamla (en körande stack med de gamla störs inte)")
kolla(len({nyar[v] for v in publicerade if v in nyar}) == len([v for v in publicerade if v in nyar]), "inga två värdportar fick samma nummer")
caddy = nyar.get("CADDY_HTTP_PORT")
kolla(any(r == "DEMO_URL_PORT=:%d" % caddy or r.startswith("DEMO_URL_PORT=:%d " % caddy) or r.startswith("DEMO_URL_PORT=:%d#" % caddy) for r in nya),
      "DEMO_URL_PORT följer den nya Caddyporten (:%s)" % caddy)
kolla("SVADA_PREFIX=svadatest" in "\n".join(nya), "prefixet byts")
kolla(len(rader) == len(nya), "radantalet är oförändrat")

noll, _a, f0 = pf.forskjut(rader, 0)
kolla(noll == rader and not f0, "förskjutning 0 ändrar ingenting")
_n, _a, f2 = pf.forskjut(rader, 40000)
kolla(bool(f2), "en förskjutning som ger portar över 65535 ger fel")
kolla("portforskjutning" in open(os.path.join(ROT, "docs/02-kom-igang.md"), encoding="utf-8").read(), "docs/02-kom-igang.md beskriver portförskjutningen")
fs = open(os.path.join(ROT, "tools", "forsta-start.sh") if os.path.exists(os.path.join(ROT, "tools", "forsta-start.sh")) else os.path.join(ROT, "tools", "export-mall", "tools", "forsta-start.sh"), encoding="utf-8").read()
kolla('uname -s' in fs and 'docker network inspect bridge' in fs and 'VARD_BIND_IP' in fs, "forsta-start.sh sätter VARD_BIND_IP till Docker-bryggans adress på Linux")
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(min(fel, 99))
