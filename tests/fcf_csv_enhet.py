#!/usr/bin/env python3
"""Enhetstest (Svada-mini): FCF bygger sin bas på brunn 4526:s CSV-filer direkt.

Ingen stack behövs. Prövar att CsvFonster ger samma sorts punkter som sensorledet gjorde
och att modellen tar dem som full täckning.
"""
import os
import sys

rot = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(rot, "services", "fcf-sim"))
import matvarden  # noqa: E402
import modell     # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text))
    if not ok:
        fel += 1


f = matvarden.CsvFonster(os.path.join(rot, "data", "Weir_4526-Discharge_0_5_000.csv"),
                         os.path.join(rot, "data", "Weir_4526-Spill, Transport_0_5_000.csv"),
                         "SSO1_01-4526")
f.starta()
p = f.punkter()
kolla(f.lage()["senasteFel"] is None, "CSV-filerna går att läsa")
kolla(len(p) == 576, "fönstret har 576 punkter à 5 min (två dygn) – %d" % len(p))
kolla(p == sorted(p, key=lambda x: x["observedAt"]), "punkterna är sorterade på mätvärdets egen tid")
kolla(p[0]["observedAt"].endswith(".000Z") and "T" in p[0]["observedAt"], "tidsformatet är detsamma som observedAt i NGSI-LD")
kolla(max(x["spillFlow"] for x in p) > 0 and max(x["totalFlow"] for x in p) > 0, "spill- och totalflöde har riktiga värden")
bas, tackning = modell.bas_fran_matvarden(p)
kolla(bas is not None and tackning >= modell.PUNKTER_PER_DYGN, "modellen får full täckning (%s av %d)" % (tackning, modell.PUNKTER_PER_DYGN))
kolla(f.vanta_pa_data(1, minst=10), "vanta_pa_data svarar direkt")
sys.exit(min(fel, 99))
