#!/usr/bin/env python3
"""Flyttar värdportarna i en .env så att två installationer kan köra bredvid varandra på samma värd.

Kontrollrummet och Caddy når komponenterna över VÄRDENS publicerade portar (host.docker.internal), så två stackar med samma portnummer
pratar med varandra av misstag. Det här verktyget lägger ett tal på varje värdport och ger stacken ett eget prefix; de interna portarna
(de som containrarna lyssnar på) rörs aldrig.

Vilka variabler som är värdportar avgörs ur compose-filerna, inte ur en lista som kan bli gammal: en variabel är en värdport om den
står på värdsidan i en `ports:`-rad ("<adress>:${VARIABEL}:<containerport>"). Övriga portvariabler måste vara klassade som interna
(INTERNA nedan) eller kopplade (DEMO_URL_PORT följer CADDY_HTTP_PORT); provet tests/portforskjutning_enhet.py (K32) fäller en ny
portvariabel som ingen har klassat.

  python3 tools/portforskjutning.py --forskjutning 1000 --prefix svadamini3                 # läser .env, skriver .env.forskjuten
  python3 tools/portforskjutning.py --forskjutning 1000 --in .env --ut /sokvag/.env --kontrollera-lediga
"""
import argparse
import glob
import os
import re
import socket
import sys

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Portvariabler som INTE är värdportar: containrarna lyssnar på dem eller använder dem i adresser mellan containrar. De flyttas aldrig.
INTERNA = {
    "EDC_PROVIDER_STATUS_PORT",     # http://edc-provider:<port>/status (container till container)
    "EDC_PROVIDER_PUBLIC_PORT", "EDC_CONSUMER_PUBLIC_PORT",       # dataplanets publika portar inne i connectorerna
    "IDENTITY_HUB_DHI_STS_PORT", "IDENTITY_HUB_SVADA_STS_PORT",   # inbyggda STS-tjänster som inte publiceras på värden
}      # (IDENTITY_HUB_STAD_STS_PORT publiceras och flyttas därför: provet K32 fäller en intern variabel som står på värdsidan i en ports:-rad)
KOPPLADE = {"DEMO_URL_PORT"}        # skrivs ":<CADDY_HTTP_PORT>" och följer den

PUBLICERING = re.compile(r'\$\{([A-Z][A-Z0-9_]*)(?::-[^}]*)?\}:(\d+)"')


def varden_porter_ur_compose(rot=ROT):
    """{variabel: containerport} för varje variabel som står på värdsidan i en publicering i compose.*.yml."""
    ut = {}
    for fil in sorted(glob.glob(os.path.join(rot, "compose.*.yml"))):
        for rad in open(fil, encoding="utf-8"):
            r = rad.strip()
            if not r.startswith('- "'):
                continue
            for m in PUBLICERING.finditer(r):
                ut[m.group(1)] = int(m.group(2))
    return ut


def las_env(sokvag):
    rader = open(sokvag, encoding="utf-8").read().split("\n")
    return rader


def forskjut(rader, forskjutning, prefix=None, rot=ROT):
    """Returnerar (nya rader, lista med (variabel, gammalt, nytt), fel). Rör bara värdportar, DEMO_URL_PORT och SVADA_PREFIX."""
    vardportar = set(varden_porter_ur_compose(rot))
    nya, andringar, fel = [], [], []
    gammal_caddy = None
    for r in rader:
        m = re.match(r"^CADDY_HTTP_PORT=(\d+)", r)
        if m:
            gammal_caddy = int(m.group(1))
    ny_caddy = None
    for r in rader:
        m = re.match(r"^([A-Z][A-Z0-9_]*)=(\d+)(\s*(#.*)?)$", r)
        if m and m.group(1) in vardportar:
            gammalt = int(m.group(2)); nytt = gammalt + forskjutning
            if not 1 <= nytt <= 65535:
                fel.append("%s: %d + %d ligger utanför 1–65535" % (m.group(1), gammalt, forskjutning))
            andringar.append((m.group(1), gammalt, nytt))
            if m.group(1) == "CADDY_HTTP_PORT":
                ny_caddy = nytt
            r = "%s=%d%s" % (m.group(1), nytt, m.group(3))
        elif prefix and re.match(r"^SVADA_PREFIX=", r):
            r = re.sub(r"^SVADA_PREFIX=[^\s#]*", "SVADA_PREFIX=" + prefix, r)
        nya.append(r)
    # DEMO_URL_PORT följer CADDY_HTTP_PORT: ":<port>" när den gamla var ":<gamla Caddyporten>"; lämnas annars (t.ex. tom för 80/443)
    for i, r in enumerate(nya):
        m = re.match(r"^DEMO_URL_PORT=(:(\d+))?(\s*(#.*)?)$", r)
        if m and m.group(2) and gammal_caddy is not None and int(m.group(2)) == gammal_caddy and ny_caddy is not None:
            nya[i] = "DEMO_URL_PORT=:%d%s" % (ny_caddy, m.group(3))
            andringar.append(("DEMO_URL_PORT", ":%d" % gammal_caddy, ":%d" % ny_caddy))
    varden = [a[2] for a in andringar if isinstance(a[2], int)]
    dubbletter = sorted({v for v in varden if varden.count(v) > 1})
    if dubbletter:
        fel.append("flera värdportar får samma nummer efter förskjutningen: %s" % dubbletter)
    return nya, andringar, fel


def ledig(adress, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((adress, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Flyttar värdportarna i en .env (se modulens beskrivning).")
    p.add_argument("--forskjutning", type=int, required=True, help="talet som läggs på varje värdport (t.ex. 1000)")
    p.add_argument("--prefix", help="nytt SVADA_PREFIX (containernamn, images, nät och volymer får det)")
    p.add_argument("--in", dest="inn", default=os.path.join(ROT, ".env"))
    p.add_argument("--ut", default=None, help="standard: <in>.forskjuten")
    p.add_argument("--kontrollera-lediga", action="store_true", help="kontrollera att de nya portarna är lediga på VARD_BIND_IP (den här datorn)")
    a = p.parse_args(argv)
    ut = a.ut or a.inn + ".forskjuten"
    rader = las_env(a.inn)
    nya, andringar, fel = forskjut(rader, a.forskjutning, a.prefix)
    if a.kontrollera_lediga:
        bind = "127.0.0.1"
        for r in rader:
            m = re.match(r"^VARD_BIND_IP=([0-9.]+)", r)
            if m:
                bind = m.group(1)
        for namn, _g, nytt in andringar:
            if isinstance(nytt, int) and not ledig(bind, nytt):
                fel.append("%s: porten %d är upptagen på %s" % (namn, nytt, bind))
    if fel:
        for f in fel:
            print("FEL: " + f, file=sys.stderr)
        return 2
    open(ut, "w", encoding="utf-8").write("\n".join(nya))
    print("Skrev %s: %d värdportar flyttade %+d." % (ut, len([x for x in andringar if x[0] != "DEMO_URL_PORT"]), a.forskjutning))
    for namn, g, n in andringar:
        print("  %-36s %s -> %s" % (namn, g, n))
    kvar = sorted(v for v in INTERNA if any(re.match(r"^%s=" % v, r) for r in rader))
    print("Interna portar som INTE flyttas: " + (", ".join(kvar) or "–"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
