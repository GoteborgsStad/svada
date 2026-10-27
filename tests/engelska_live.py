#!/usr/bin/env python3
"""Livetest: kontrollrummets engelska API-svar innehåller inga svenska meddelanden.

Kräver den körande dashboarden (DASH, standard http://localhost:$DASHBOARDPORT). Hämtar auditloggen och
alla jobb på engelska och kontrollerar textfälten (händelsetext, jobbrader, jobbetiketter). Namn och id:n
(brunnar, recipienter) kontrolleras inte: de är data. Se services/dashboard/i18n.py.
"""
import json
import os
import re
import sys
import urllib.request

DASH = os.environ.get("DASH", "http://localhost:%s" % os.environ.get("DASHBOARD_PORT", "38800"))
SVENSKA = re.compile(r"[åäöÅÄÖ]|\b(och|att|som|inte|för|med|ett|på|till|kan|från|eller|har|ska|när|efter|"
                     r"staden|stadens|avtalet|avtalets|ingen|inget|väntar|förhandling|leveransen|överföring|"
                     r"nekas|hävt|hävts|kör|steg)\b")
UNDANTAG = re.compile(r"Kretslopp och [Vv]atten|Göteborg\w*|Krokängsparken|dygnspositioner|bräddata|modellerad-bradddata")


def hamta(sokvag):
    with urllib.request.urlopen(DASH + sokvag + ("&" if "?" in sokvag else "?") + "lang=en", timeout=20) as r:
        return json.load(r)


fel = 0
texter = []
for h in hamta("/api/audit").get("handelser", []):
    texter.append(("audit", h.get("text", "")))
jobb = hamta("/api/jobb")
for j in (jobb if isinstance(jobb, list) else jobb.get("jobb", [])):
    full = hamta("/api/jobb/%s" % j["id"])
    texter.append(("jobb-etikett", full.get("etikett", "")))
    for r in full.get("rader", []):
        texter.append(("jobb-rad", r.get("text", "")))
# Lagringen är språkoberoende: raderna är kod + parametrar. (Att hashkedjan är densamma oavsett språk bevisas av
# engelska_enhet.py: texten ingår inte i det som kedjas. En jämförelse av två API-anrop vore inget bevis, eftersom
# kedjan räknas före översättningen.)
av = hamta("/api/audit")
saknar_kod = [h for h in av["handelser"] if not h.get("kod")]
if saknar_kod:
    fel += 1
    print("  [FEL] %d auditposter saknar kod (lagras som text)" % len(saknar_kod))
else:
    print("  [OK] alla auditposter är lagrade som kod + parametrar")
for vad, t in texter:
    kvar = SVENSKA.findall(re.sub(r"\S+-\S+", " ", UNDANTAG.sub(" ", t)))   # ord med bindestreck är id:n/koder
    if kvar:
        fel += 1
        print("  [FEL] %s: %s" % (vad, t[:160]))
print("  [%s] %d engelska texter ur auditlogg och jobb kontrollerade, %d på svenska"
      % ("OK" if not fel else "FEL", len(texter), fel))
if not texter:
    print("  [FEL] inga texter att kontrollera (kör några steg först)")
    fel += 1
sys.exit(1 if fel else 0)
