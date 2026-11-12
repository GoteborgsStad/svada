"""Enhetsprov av avtalsscenariot "betrodd organisation" (services/dashboard/jobb.py, _egen_betrodd; märkningen i audit.py och avtalssidan). API:t /api/scenario prövas över HTTP i verify_kedjevy.sh (K41b). Ingen stack, inget nätverk.

Bevisar (granskningsfynd 2026-11-04 inkluderade): en förhandling som redan finns och ännu inte prövats av gaten omfattas aldrig av någon annans utpekning
(jobbet väntar in prövningen); en kvarlämnad utpekning städas före nästa A-förhandling; ett fel vid utpekningen lämnar ingen utpekning kvar och
visar inga interna adresser; ett automatiskt beslut märks i auditloggen, i avtalssidan och i KoV-tabellens data, aldrig som ett KoV-godkännande;
utan val rörs providern aldrig; med val pekas staden ut hos providern INNAN förhandlingen och utpekningen tas bort direkt efteråt,
även när förhandlingen fallerar; ett fel vid borttagningen göms inte (det loggas, och utpekningen går ut av sig själv hos providern); valet
gäller bara besökarens egen session; ett avtal som skrevs direkt tar besökaren förbi KoV-steget i "Nästa"; utpekningen begärs med stadens
deltagar-id och en tid inom providerns tak.

Körs i dashboard-imagen med arbetskopian monterad (tests/verify_kedjevy.sh, K41), eller lokalt:  python3 -I tests/betrodd_enhet.py
"""
import os
import sys

rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sok in ("/srv/dashboard", "/srv", os.path.join(rot, "services", "dashboard"), os.path.join(rot, "services")):
    if os.path.isdir(sok):
        sys.path.insert(0, sok)

import jobb as jobbmodul  # noqa: E402
import kallor  # noqa: E402
import sessioner  # noqa: E402
import kedjan  # noqa: E402
import audit  # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print(f"  [{'OK' if ok else 'FEL'}] {text}")
    fel += 0 if ok else 1


class Jobb:
    """Det _egen_betrodd behöver av ett jobb: en session och en logg."""
    def __init__(self, session):
        self.session = session
        self.rader = []
        self.status = "klar"
        self.utfall = None
        self.atgard = "forhandla-a"
        self.resultat = None

    def logg(self, kod, **p):
        self.rader.append(kod)


anrop = []


def stubba():
    """Ersätter anropen mot providern med stubbar som skriver upp vad som anropades (görs om efter att kallor laddats om längre ned)."""
    kallor.kov_betrodd_satt = lambda did, sek: anrop.append(("satt", did, sek))
    kallor.kov_betrodd_bort = lambda did: anrop.append(("bort", did))
    kallor.STAD_DID = "did:web:stad.test"
    kallor.kov_betrodda = lambda: []


stubba()

print("== _egen_betrodd ==")
s_av, _ = sessioner.hamta_eller_skapa(None)
with jobbmodul._egen_betrodd(Jobb(s_av)) as b:
    kolla(b is False and anrop == [], "utan val: providern rörs aldrig")

s_pa, _ = sessioner.hamta_eller_skapa(None)
s_pa.betrodd = True
j = Jobb(s_pa)
with jobbmodul._egen_betrodd(j) as b:
    kolla(b is True and anrop == [("satt", "did:web:stad.test", jobbmodul.BETRODD_SEK)], "med val: staden pekas ut INNAN förhandlingen, med stadens deltagar-id")
kolla(anrop[-1] == ("bort", "did:web:stad.test") and j.rader == ["jobb.betrodd_pa", "jobb.betrodd_av"], "direkt efteråt tas utpekningen bort och båda stegen loggas")
kolla(0 < jobbmodul.BETRODD_SEK <= 600, "tiden ryms inom providerns tak (600 s)")

anrop.clear()
j = Jobb(s_pa)
try:
    with jobbmodul._egen_betrodd(j):
        raise RuntimeError("förhandlingen föll")
except RuntimeError:
    pass
kolla(anrop[-1] == ("bort", "did:web:stad.test"), "faller förhandlingen tas utpekningen ändå bort")


def _fel(did):
    raise kallor.KallFel("providern svarar inte")


anrop.clear()
kallor.kov_betrodd_bort = _fel
j = Jobb(s_pa)
with jobbmodul._egen_betrodd(j):
    pass
kolla("jobb.betrodd_kvar" in j.rader and "jobb.betrodd_av" not in j.rader, "ett fel vid borttagningen göms inte: det loggas (utpekningen går ut av sig själv hos providern)")
kallor.kov_betrodd_bort = lambda did: anrop.append(("bort", did))

anrop.clear()
def _satt_fel(did, sek):
    raise kallor.KallFel("providern svarar inte")
kallor.kov_betrodd_satt = _satt_fel
try:
    with jobbmodul._egen_betrodd(Jobb(s_pa)):
        kolla(False, "kunde inte peka ut: förhandlingen får inte fortsätta som om staden vore betrodd")
except jobbmodul.Jobbfel:
    kolla(True, "kunde utpekningen inte göras avbryts jobbet i stället för att tyst köra utan betrodd status")
kallor.kov_betrodd_satt = lambda did, sek: anrop.append(("satt", did, sek))

print("== valet är besökarens eget ==")
kolla(s_av.betrodd is False and s_pa.betrodd is True, "valet sparas i besökarens egen session")
s_ny, _ = sessioner.hamta_eller_skapa(None)
kolla(s_ny.betrodd is False, "en ny besökare börjar alltid med valet av")
kolla(jobbmodul._GLOBALT.betrodd is False, "utan session (direktanrop) finns ett gemensamt val, av som standard")

print("== Nästa-steget ==")
t = sessioner.hamta_eller_skapa(None)[0]
j = Jobb(t); j.resultat = {"forhandlingId": "f", "avtal": "a1", "tillstand": "FINALIZED", "betrodd": True}
jobbmodul._notera(j)
kolla(t.a_laget == "godkant", "ett avtal som skrevs direkt tar besökaren förbi KoV-steget: nästa är att leverera A")
t2 = sessioner.hamta_eller_skapa(None)[0]
j = Jobb(t2); j.resultat = {"forhandlingId": "f", "avtal": None, "betrodd": True}
jobbmodul._notera(j)
kolla(t2.a_laget == "begart", "blev inget avtal (betrodd men utan avtal) väntar besökaren som vanligt")
t3 = sessioner.hamta_eller_skapa(None)[0]
j = Jobb(t3); j.resultat = {"forhandlingId": "f", "avtal": None, "kov": {"kovBeslut": "VANTANDE"}, "betrodd": False}
jobbmodul._notera(j)
kolla(t3.a_laget == "begart", "utan val är flödet som förut: begärd, sedan KoV-beslut")

print("== kallor: anropens form ==")
import urllib.parse  # noqa: E402
import importlib  # noqa: E402
importlib.reload(kallor)
sett = []
kallor.hamta_kov_token = lambda: "TOKEN"
kallor.anrop = lambda adress, metod="GET", kropp=None, headers=None, timeout=None, ratext=False: sett.append((adress, metod, headers))
kallor.kov_betrodd_satt("did:web:identity-hub-stad%3A29197", 120)
kolla("/management/kov/betrodda?did=did%3Aweb%3Aidentity-hub-stad%253A29197&sek=120" in sett[-1][0] and sett[-1][1] == "POST", "utpekningen är en POST med DID:et URL-kodat och en tid i sekunder")
kolla(sett[-1][2].get("Authorization") == "Bearer TOKEN", "utpekningen bär KoV-rollintyget (som ett godkännande)")
kallor.kov_betrodd_bort("did:web:x")
kolla(sett[-1][1] == "DELETE" and sett[-1][2].get("Authorization") == "Bearer TOKEN", "borttagningen är en DELETE med KoV-rollintyget")

stubba()      # kallor laddades om i avsnittet ovan
print("== skydd mot att någon annans förhandling omfattas ==")
import time  # noqa: E402
jobbmodul.time.sleep = lambda s: None
omgangar = []
svar = [[{"id": "p1", "kovBeslut": "VANTANDE", "pending": False}], [{"id": "p1", "kovBeslut": "VANTANDE", "pending": False}],
        [{"id": "p1", "kovBeslut": "VANTANDE", "pending": True}]]
def _kon():
    omgangar.append(1)
    return svar[min(len(omgangar) - 1, len(svar) - 1)]
kedjan.kov_kon = _kon
jobbmodul._vanta_obeprovade_a(Jobb(s_pa))
kolla(len(omgangar) == 3, "jobbet väntar in att en väntande förhandling prövats av gaten (pending) innan det pekar ut staden (%d läsningar)" % len(omgangar))

anrop.clear()
kedjan.kov_kon = lambda: [{"id": "p1", "kovBeslut": "VANTANDE", "pending": False}]
j = Jobb(s_pa)
with jobbmodul._egen_betrodd(j):
    pass
kolla([a[0] for a in anrop][:1] == ["satt"], "hinner gaten inte pröva inom väntetiden pekas staden ut ändå (providern godkänner bara förhandlingar skapade efter utpekningen)")
kedjan.kov_kon = lambda: []

anrop.clear()
kallor.kov_betrodda = lambda: [{"did": "did:web:stad.test", "till": "x"}]
with jobbmodul._egen_betrodd(Jobb(s_av)) as b:
    kolla(b is False and anrop == [("bort", "did:web:stad.test")], "utan val städas en kvarlämnad utpekning före förhandlingen (ingen annans förhandling godkänns av den)")
kallor.kov_betrodda = lambda: []

print("== fel vid utpekningen ==")
anrop.clear()
INTERN = "http://host.docker.internal:39193/management/kov/betrodda?did=did%3Aweb%3Aidentity-hub-stad%253A29197"
def _satt_kastar(did, sek):
    raise kallor.KallFel("nar_inte %s" % INTERN)
kallor.kov_betrodd_satt = _satt_kastar
try:
    with jobbmodul._egen_betrodd(Jobb(s_pa)):
        pass
    kolla(False, "ett misslyckat anrop ska stoppa jobbet")
except jobbmodul.Jobbfel as f:
    text = f.meddelande().get("sv", "") if isinstance(f.meddelande(), dict) else str(f.meddelande())
    kolla(f.kod == "fel.betrodd_utpekning" and "host.docker" not in str(f) and "identity-hub" not in str(f) and "39193" not in str(f),
          "ett fel vid utpekningen blir ett eget meddelande utan intern adress, värdnamn eller DID")
kolla(("bort", "did:web:stad.test") in anrop, "kan utpekningen ha registrerats trots felet görs en borttagning")
kallor.kov_betrodd_satt = lambda did, sek: anrop.append(("satt", did, sek))

print("== märkning: aldrig förväxlad med ett KoV-godkännande ==")
hand = []
kallor.kov_forhandlingar = lambda: [{"id": "p1", "correlationId": "c1", "kovBeslut": "GODKAND", "betroddAutomatiskt": True,
                                     "beslutsfattare": "betrodd organisation (automatiskt, ingen KoV-prövning)", "state": "FINALIZED", "pending": False},
                                    {"id": "p2", "correlationId": "c2", "kovBeslut": "GODKAND", "betroddAutomatiskt": False,
                                     "beslutsfattare": "Kretslopp och Vatten – rättighetsinnehavare (dataägare)", "state": "FINALIZED", "pending": False}]
audit._kov(hand, {}, [])
koder = {h["detaljer"]["providerForhandling"]: h["kod"] for h in hand}
kolla(koder.get("p1") == "audit.kov_automatiskt" and koder.get("p2") == "audit.kov_godkand_roll", "auditloggen skiljer ett automatiskt beslut (egen kod) från ett KoV-godkännande")
import meddelanden  # noqa: E402
for sp in ("sv", "en"):
    t = meddelanden.visa("audit.kov_automatiskt", {"roll": "betrodd organisation (automatiskt, ingen KoV-prövning)"}, sp)
    kolla(("ingen KoV-prövning" if sp == "sv" else "without a KoV review") in t and ("GODKÄNDE" not in t and "APPROVED" not in t), "auditmeddelandet (%s) säger att ingen KoV-prövning gjordes" % sp)
import main  # noqa: E402
for sp in (False, True):
    h = main._avtalssida({"id": "a1", "status": "GALLANDE", "distribution": "A", "tillkomst": "betrodd-organisation", "regler": {}}, sp, "steg-5")
    kolla(("without a KoV review" if sp else "utan KoV-prövning") in h and ("trusted organisation (no KoV review)" if sp else "betrodd organisation (ingen KoV-prövning)") in h,
          "avtalssidan (%s) säger att avtalet skrevs utan KoV-prövning, både i rutan och i tabellen" % ("en" if sp else "sv"))
h = main._avtalssida({"id": "a2", "status": "GALLANDE", "distribution": "B", "regler": {}}, False, "steg-5")
kolla("Tillkom genom" not in h, "ett B-avtal (utan KoV) får ingen rad om hur det tillkom")
h = main._avtalssida({"id": "a3", "status": "GALLANDE", "distribution": "A", "tillkomst": "kov-beslut", "regler": {}}, False, "steg-5")
kolla("KoV-beslut" in h and "betrodd organisation" not in h, "ett avtal som KoV godkänt säger KoV-beslut, inte betrodd organisation")

sys.exit(min(fel, 99))
