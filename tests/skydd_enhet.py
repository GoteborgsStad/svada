"""Enhetstest av skydd.py (publik demo utan lösenord): ursprung, kö, automatisk återinsättning. Kör utan stack."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "dashboard"))
os.environ.update(DASH_PAUS_EFTER_JOBB_S="8", DASH_UTESTANGNING_S="180", DASH_FELINJEKTION_S="300", DASH_AVKYLNING_S="60")
import skydd

fel = 0
def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text)); fel += (not ok)

class R:
    def __init__(self, **h): self.headers = {k.replace("_", "-"): v for k, v in h.items()}; self.client = None

kolla(skydd.via_proxy(R(x_forwarded_for="1.2.3.4")) and not skydd.via_proxy(R()), "bara anrop via Caddy (X-Forwarded-For) berörs")
kolla(skydd.klient(R(x_forwarded_for="1.2.3.4, 10.0.0.1")) == "1.2.3.4", "klienten är första adressen i X-Forwarded-For")
kolla(skydd.samma_ursprung(R(origin="https://demo.x.se", host="demo.x.se")), "samma origin godkänns")
kolla(not skydd.samma_ursprung(R(origin="https://ond.example", host="demo.x.se")), "annan origin nekas")
kolla(not skydd.samma_ursprung(R(host="demo.x.se")), "saknad origin nekas")
kolla(not skydd.samma_ursprung(R(origin="https://demo.x.se", host="demo.x.se", sec_fetch_site="cross-site")), "cross-site nekas även med rätt origin")

a, b = R(x_forwarded_for="1.1.1.1"), R(x_forwarded_for="2.2.2.2")
skydd.noterat_jobbstart(a, 1)
kolla(skydd.vanta_efter_jobb(a, True, 100) == 0, "medan jobbet kör gäller 'upptaget', inte kön")
kolla(skydd.vanta_efter_jobb(a, False, 150) == 0, "att läsa pausen före jobbslut sätter ingen starttid (GET är utan sidoeffekt)")
skydd.jobb_slut(1, 101)
kolla(skydd.vanta_efter_jobb(a, False, 101) == 8, "pausen räknas från jobbets sluttid")
kolla(skydd.vanta_efter_jobb(a, False, 101) == 8, "att läsa flera gånger ändrar inte svaret")
kolla(skydd.vanta_efter_jobb(b, False, 101) == 0, "en annan besökare släpps fram direkt")
kolla(skydd.vanta_efter_jobb(a, False, 106) == 3, "väntan räknas ned")
kolla(skydd.vanta_efter_jobb(a, False, 110) == 0, "efter pausen får samma besökare köra igen")
# ett kort jobb hinner ta slut INNAN starten noterats: pausen ska ändå gälla den som startade det (sluttiden ligger per id)
skydd.jobb_slut(2, 200)
skydd.noterat_jobbstart(b, 2)
kolla(skydd.vanta_efter_jobb(b, False, 201) == 7, "ett jobb som tog slut före noteringen räknas ändå som besökarens")
kolla(skydd.vanta_efter_jobb(a, False, 201) == 0, "och den förra besökaren är fri")
# A2-04: en sen notering för ett ÄLDRE jobb skriver inte över en nyare start (omkastade svar)
skydd.noterat_jobbstart(a, 4); skydd.jobb_slut(4, 300)
skydd.noterat_jobbstart(b, 3)
kolla(skydd.vanta_efter_jobb(a, False, 301) == 7 and skydd.vanta_efter_jobb(b, False, 301) == 0,
      "en sen notering för jobb 3 (b) flyttar inte pausen från jobb 4 (a)")

# schema och port ingår i ursprungskontrollen
kolla(skydd.samma_ursprung(R(origin="https://demo.x.se", host="demo.x.se", x_forwarded_proto="https")), "origin med rätt schema godkänns")
kolla(not skydd.samma_ursprung(R(origin="http://demo.x.se", host="demo.x.se", x_forwarded_proto="https")), "fel schema mot X-Forwarded-Proto nekas")
kolla(not skydd.samma_ursprung(R(origin="ftp://demo.x.se", host="demo.x.se")), "annat schema än http/https nekas")
kolla(not skydd.samma_ursprung(R(origin="https://demo.x.se:8443", host="demo.x.se")), "annan port nekas")

# --- uteslutning och felinjektion: absolut frist, idempotent aktivering, återhämtningsperiod -------------
skydd.UTESTANGDA.clear(); skydd._AVKYLNING_TILL.clear()
kolla(skydd.utestangd("stad", 1000) is True, "ny uteslutning noteras")
kolla(skydd.utestangd("stad", 1100) is False, "upprepad uteslutning är idempotent")
skydd.felinjektion_pa(True, 1000); skydd.felinjektion_pa(True, 1100); skydd.felinjektion_pa(True, 1250)
kolla(skydd.forfallna(1100) == ([], False), "före tiden släpps ingen in och felinjektionen står kvar")
kolla(skydd.forfallna(1180) == (["stad"], False), "180 s efter FÖRSTA uteslutningen släpps parten in (anropet vid 1100 förnyade inte)")
kolla(skydd.forfallna(1300) == (["stad"], True), "300 s efter FÖRSTA aktiveringen slås felinjektionen av (anropen vid 1100/1250 förnyade inte)")
kolla(skydd.forfallna(1301) == (["stad"], True), "forfallna() tar inget ur bokföringen: misslyckas åtgärden försöker städningen igen")
skydd.insatt("stad", 1302); skydd.felinjektion_pa(False, 1302)
kolla(skydd.forfallna(1303) == ([], False), "bokföringen är tom först när åtgärden bekräftats")
kolla(skydd.avkylning_kvar("ute:stad", 1303) == 59 and skydd.avkylning_kvar("fel", 1303) == 59, "återhämtningsperiod startar när störningen upphört")
kolla(skydd.avkylning_kvar("ute:dhi", 1303) == 0, "perioden gäller per störning, inte alla")
kolla(skydd.avkylning_kvar("fel", 1362.5) == 0, "perioden går ut efter 60 s")
skydd.utestangd("dhi", 2000); skydd.insatt("dhi", 2001)
kolla(skydd.forfallna(time.monotonic() + 9999) == ([], False), "manuell återinsättning tar bort posten")
kolla(skydd.avkylning_kvar("ute:dhi", 2002) == 59, "även manuell återinsättning startar återhämtningsperioden")
skydd.insatt("aldrig-utesluten", 3000)
kolla(skydd.avkylning_kvar("ute:aldrig-utesluten", 3001) == 0, "återinsättning av någon som inte var utesluten startar ingen period")
sys.exit(1 if fel else 0)
