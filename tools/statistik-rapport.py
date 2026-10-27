#!/usr/bin/env python3
"""Daglig rapport ur Caddys JSON-logg och den sparade historiken (statistik etapp 0).

Räkningen och definitionerna ligger i services/gemensam/statistik.py (samma kod som kontrollrummets sida /statistik).
Skriptet läser Caddys loggfiler i statistik/logg (aktuell och roterade, även .gz), slår ihop med statistik/data/dagligt.json (så att dagar vars rålogg roterats bort
finns kvar), skriver historiken tillbaka och skriver en tabell.

Användning:  python3 tools/statistik-rapport.py [--katalog statistik] [--utesluta 1.2.3.0/24 ...] [--ut statistik/rapport]
"""
import argparse
import csv
import ipaddress
import os
import sys

rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(rot, "services"))
from gemensam import statistik  # noqa: E402


def _uteslut_ur_env():
    """STATISTIK_UTESLUT ur repots .env när variabeln inte redan är satt, så att rapporten räknar som kontrollrummets sida."""
    if "STATISTIK_UTESLUT" in os.environ:
        return
    try:
        for rad in open(os.path.join(rot, ".env"), encoding="utf-8"):
            if rad.startswith("STATISTIK_UTESLUT="):
                os.environ["STATISTIK_UTESLUT"] = rad.split("=", 1)[1].strip()
    except OSError:
        pass

HUVUD = ["dag", "värd", "sidvisningar", "unika", "avvisade", "API-träffar", "robotar", "fel", "begränsade", "kampanjer"]


def rader(historik):
    ut = []
    for dag in sorted(historik):
        for vard in statistik.VARDAR:
            r = historik[dag].get(vard)
            if r:
                ut.append([dag, vard, r["sidvisningar"], r["unika"], r["avvisade"], r["api_traffar"], r["robotar"], r["fel"], r.get("begransade", 0),
                           ", ".join(f"{n}={v}" for n, v in sorted((r.get("kampanjer") or {}).items()))])
    return ut


def markdown(tabell):
    ut = ["| " + " | ".join(HUVUD) + " |", "|" + "---|" * len(HUVUD)]
    ut += ["| " + " | ".join(str(x) for x in r) + " |" for r in tabell]
    return "\n".join(ut) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--katalog", default=os.path.join(rot, "statistik"))
    ap.add_argument("--utesluta", nargs="*", default=[], help="adresser att utesluta (CIDR, de kapade adresserna)")
    ap.add_argument("--ut", help="katalog för dagligt.csv och senaste.md")
    a = ap.parse_args(argv)
    _uteslut_ur_env()
    historik = statistik.uppdatera_historik(a.katalog, [ipaddress.ip_network(n, strict=False) for n in a.utesluta])
    tabell = rader(historik)
    md = markdown(tabell)
    sys.stdout.write(md if tabell else "(ingen logg ännu)\n")
    if a.ut:
        os.makedirs(a.ut, exist_ok=True)
        with open(os.path.join(a.ut, "dagligt.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HUVUD)
            w.writerows(tabell)
        with open(os.path.join(a.ut, "senaste.md"), "w", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
