#!/usr/bin/env python3
"""Enhetstest: beräkningen av nästa nattliga återställning (services/gemensam/aterstall.py). Ingen stack behövs."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
from gemensam import aterstall  # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text))
    fel += 0 if ok else 1


U = dt.timezone.utc
STHLM = "Europe/Stockholm"


def nasta(kl, tz, nu):
    return aterstall.nasta_aterstallning(kl, tz, nu)


# Sommartid i Sverige (CEST, UTC+2) till och med 2026-10-25; därefter vintertid (CET, UTC+1).
kolla(nasta("04:00", STHLM, dt.datetime(2026, 10, 15, 0, 30, tzinfo=U)) == dt.datetime(2026, 10, 15, 2, 0, tzinfo=U),
      "02:30 lokal tid (sommartid): nästa 04:00 är samma dygn (02:00 UTC)")
kolla(nasta("04:00", STHLM, dt.datetime(2026, 10, 15, 2, 30, tzinfo=U)) == dt.datetime(2026, 10, 16, 2, 0, tzinfo=U),
      "04:30 lokal tid: nästa 04:00 är nästa dygn")
kolla(nasta("04:00", STHLM, dt.datetime(2026, 10, 15, 2, 0, tzinfo=U)) == dt.datetime(2026, 10, 16, 2, 0, tzinfo=U),
      "exakt 04:00: nästa är nästa dygn, inte 'nu'")
kolla(nasta("04:00", STHLM, dt.datetime(2026, 11, 10, 0, 0, tzinfo=U)) == dt.datetime(2026, 11, 10, 3, 0, tzinfo=U),
      "vintertid: 04:00 lokal är 03:00 UTC")
kolla(nasta("04:00", STHLM, dt.datetime(2026, 10, 24, 12, 0, tzinfo=U)) == dt.datetime(2026, 10, 25, 3, 0, tzinfo=U),
      "natten då klockan ställs tillbaka (2026-10-25): 04:00 lokal är 03:00 UTC (vintertid)")
kolla(nasta("04:00", STHLM, dt.datetime(2026, 3, 28, 12, 0, tzinfo=U)) == dt.datetime(2026, 3, 29, 2, 0, tzinfo=U),
      "natten då klockan ställs fram (2026-03-29): 04:00 lokal är 02:00 UTC (sommartid)")
kolla(nasta("4:00", "UTC", dt.datetime(2026, 10, 15, 1, 0, tzinfo=U)) == dt.datetime(2026, 10, 15, 4, 0, tzinfo=U), "klockslaget '4:00' accepteras")
kolla(nasta("", STHLM, dt.datetime(2026, 10, 15, tzinfo=U)) is None, "tomt klockslag ger ingen nedräkning (lokalt på en Mac)")
kolla(nasta(None, STHLM, dt.datetime(2026, 10, 15, tzinfo=U)) is None, "saknat klockslag ger ingen nedräkning")
kolla(nasta("25:00", STHLM, dt.datetime(2026, 10, 15, tzinfo=U)) is None, "ogiltigt klockslag (25:00) ger ingen nedräkning")
kolla(nasta("04:61", STHLM, dt.datetime(2026, 10, 15, tzinfo=U)) is None, "ogiltiga minuter (04:61) ger ingen nedräkning")
kolla(nasta("04:00", "Finns/Inte", dt.datetime(2026, 10, 15, 1, 0, tzinfo=U)) == dt.datetime(2026, 10, 15, 4, 0, tzinfo=U),
      "okänd tidszon räknar i UTC i stället för att tappa nedräkningen")
s = aterstall.som_svar("04:00", STHLM, dt.datetime(2026, 10, 15, 0, 30, tzinfo=U))
kolla(s == {"nastaUtc": "2026-10-15T02:00:00Z", "nuUtc": "2026-10-15T00:30:00Z", "klockslag": "04:00", "tz": STHLM, "varaktighetMin": aterstall.VARAKTIGHET_MIN},
      "svaret bär nästa tidpunkt och serverns tid (UTC, ISO)")
kolla(aterstall.som_svar("", STHLM) is None, "tomt klockslag ger inget svar")
kolla(aterstall.som_svar("4:00", "UTC", dt.datetime(2026, 10, 15, 1, 0, tzinfo=U))["klockslag"] == "04:00", "klockslaget normaliseras till HH:MM")
# publik-vy bygger i en egen Docker-kontext och har därför en kopia: den får inte glida isär från den gemensamma.
sokvag = os.path.join(os.path.dirname(__file__), "..", "services")
kolla(open(os.path.join(sokvag, "gemensam", "aterstall.py"), encoding="utf-8").read()
      == open(os.path.join(sokvag, "publik-vy", "aterstall.py"), encoding="utf-8").read(),
      "services/publik-vy/aterstall.py är identisk med services/gemensam/aterstall.py")
sys.exit(1 if fel else 0)
