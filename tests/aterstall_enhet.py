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
kolla(s == {"nastaUtc": "2026-10-15T02:00:00Z", "nuUtc": "2026-10-15T00:30:00Z", "klockslag": "04:00", "tz": STHLM, "varaktighetMin": aterstall.VARAKTIGHET_MIN, "typ": "nollstallning"},
      "svaret bär nästa tidpunkt och serverns tid (UTC, ISO)")
kolla(aterstall.som_svar("", STHLM) is None, "tomt klockslag ger inget svar")
kolla(aterstall.som_svar("4:00", "UTC", dt.datetime(2026, 10, 15, 1, 0, tzinfo=U))["klockslag"] == "04:00", "klockslaget normaliseras till HH:MM")

# ---- Planerad händelse (varselfilen): driftskriptet varsla.sh skriver tid och typ; texterna är fasta i sidan ----
import json
import tempfile
VF = os.path.join(tempfile.mkdtemp(), "varsel.json")


def skriv(innehall):
    with open(VF, "w", encoding="utf-8") as f:
        f.write(innehall if isinstance(innehall, str) else json.dumps(innehall))
    aterstall._CACHE["t"] = None         # förbi femsekunderscachen


def svar(nu):
    return aterstall.som_svar("04:00", STHLM, nu, VF)


nu = dt.datetime(2026, 11, 3, 18, 50, tzinfo=U)          # 19:50 svensk tid
kolla(aterstall.som_svar("04:00", STHLM, nu, VF)["typ"] == "nollstallning", "utan varselfil styr nattens nollställning, som förut")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "uppdatering"})
s = svar(nu)
kolla(s and s["typ"] == "uppdatering" and s["nastaUtc"] == "2026-11-03T19:05:00Z" and s["klockslag"] == "20:05" and s["varaktighetMin"] == 3,
      "en planerad uppdatering före natten styr nedräkningen (typ, tid, klockslag i serverns zon, varaktighet)")
skriv({"tid": "2026-11-04T05:00:00+01:00", "typ": "uppdatering"})
kolla(svar(nu)["typ"] == "nollstallning", "en planerad händelse efter natten ger plats åt nattens nollställning (den tidigaste styr)")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "nollstallning"})
kolla(svar(nu)["typ"] == "nollstallning" and svar(nu)["varaktighetMin"] == aterstall.VARAKTIGHET_MIN, "en planerad nollställning har nollställningens varaktighet")
skriv("{inte json")
kolla(svar(nu)["typ"] == "nollstallning" and not aterstall.sparr_nya_jobb(VF, nu), "en trasig fil ger inget varsel")
skriv({"tid": "2026-11-03T20:05:00", "typ": "uppdatering"})
kolla(svar(nu)["typ"] == "nollstallning", "en tid utan zon är tvetydig och ger inget varsel")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "vad-som-helst"})
kolla(svar(nu)["typ"] == "nollstallning", "en okänd typ ger inget varsel (inga fria texter)")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "uppdatering", "text_sv": "<script>x</script>"})
kolla("text_sv" not in json.dumps(svar(nu)), "fria texter i filen når aldrig besökaren")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "uppdatering"})
efter = dt.datetime(2026, 11, 3, 19, 5, tzinfo=U) + dt.timedelta(minutes=aterstall.VARAKTIGHET_TYP["uppdatering"], seconds=1)
kolla(svar(efter)["typ"] == "nollstallning", "ett varsel vars avbrott är över visas aldrig (ett glömt varsel försvinner av sig självt)")
kolla(svar(dt.datetime(2026, 11, 3, 19, 6, tzinfo=U))["typ"] == "uppdatering", "medan avbrottet pågår styr uppdateringen fortfarande (läget pågår)")
skriv({"tid": "2026-11-03T20:05:00+01:00", "typ": "uppdatering"})
okand = aterstall.som_svar("04:00", "Finns/Inte", nu, VF)
kolla(okand is not None and okand["typ"] == "uppdatering", "en okänd tidszon tappar inte varslet (räknas i UTC i stället för att ge fel)")
T0 = dt.datetime(2026, 11, 3, 19, 5, tzinfo=U)
kolla(not aterstall.sparr_nya_jobb(VF, T0 - dt.timedelta(minutes=3)), "tre minuter före: nya jobb tillåts")
kolla(aterstall.sparr_nya_jobb(VF, T0 - dt.timedelta(minutes=2)), "de sista två minuterna: nya jobb spärras")
kolla(aterstall.sparr_nya_jobb(VF, T0 + dt.timedelta(minutes=1)), "medan uppdateringen pågår: nya jobb spärras")
kolla(not aterstall.sparr_nya_jobb(VF, T0 + dt.timedelta(minutes=4)), "efter avbrottet: nya jobb tillåts igen")
kolla(not aterstall.sparr_nya_jobb("", T0) and not aterstall.sparr_nya_jobb(os.path.join(os.path.dirname(VF), "finns-inte.json"), T0),
      "utan varselfil (tom sökväg eller saknad fil) spärras inget")
# publik-vy bygger i en egen Docker-kontext och har därför en kopia: den får inte glida isär från den gemensamma.
sokvag = os.path.join(os.path.dirname(__file__), "..", "services")
kolla(open(os.path.join(sokvag, "gemensam", "aterstall.py"), encoding="utf-8").read()
      == open(os.path.join(sokvag, "publik-vy", "aterstall.py"), encoding="utf-8").read(),
      "services/publik-vy/aterstall.py är identisk med services/gemensam/aterstall.py")
sys.exit(1 if fel else 0)
