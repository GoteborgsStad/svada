"""Enhetsprov av en egen vy per besökare (services/dashboard/sessioner.py och sessionsdelarna i jobb.py). Ingen stack och inget nätverk.

Bevisar: en kaka som inte är en giltig, känd id ger en NY session; en känd id ger samma; en oanvänd session glöms efter tidsgränsen; antalet
sessioner har tak; ett jobb har en ägare och en besökare ser bara sina egna jobb; en annan besökares jobb KÖAS (status "kö", plats i kön) i
stället för att ge ett fel, och startas när det föregående är klart, i ordning; en besökare har högst ett pågående eller köat jobb; utan session
gäller det gamla (409 och alla jobb syns); ett köat eller körande jobb rensas aldrig ur listan; en förhandling och ett avtal tillhör bara den
som startade dem.

Körs i dashboard-imagen med arbetskopian monterad (tests/verify_kedjevy.sh, K28), eller lokalt:  python3 -I tests/sessioner_enhet.py
"""
import os
import sys
import threading
import time

rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sok in ("/srv/dashboard", "/srv", os.path.join(rot, "services", "dashboard"), os.path.join(rot, "services")):
    if os.path.isdir(sok):
        sys.path.insert(0, sok)

import sessioner  # noqa: E402
import jobb as jobbmodul  # noqa: E402
import kallor  # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print(f"  [{'OK' if ok else 'FEL'}] {text}")
    fel += 0 if ok else 1


# --- sessionerna -------------------------------------------------------------------------------------------------
print("== sessioner.py ==")
s1, ny1 = sessioner.hamta_eller_skapa(None)
kolla(ny1 and len(s1.id) == 32, "ingen kaka ger en ny session med en slumpad id på 128 bitar")
s1b, ny1b = sessioner.hamta_eller_skapa(s1.id)
kolla(s1b is s1 and not ny1b, "en känd id ger samma session, inte en ny")
for dalig in ("", "x", "GEMENER" * 5, "0" * 31, "0" * 33, "g" * 32, "../../etc/passwd", None, 5, "0" * 32):
    s, ny = sessioner.hamta_eller_skapa(dalig)
    if not ny or s is s1:
        kolla(False, f"en ogiltig eller okänd kaka ({dalig!r}) ska ge en NY session")
        break
else:
    kolla(True, "ogiltiga eller okända kakor (tomma, fel längd, fel tecken, sökvägstrick, okänd id) ger alltid en ny session")
s1.forhandlingar.add("forh-1"); s1.avtal.add("avtal-1")
s2, _ = sessioner.hamta_eller_skapa(None)
kolla(not s2.forhandlingar and not s2.avtal and s2.id != s1.id, "en ny session ärver ingenting av en annan")

# tidsgräns och tak (styrd klocka: sessioner.py läser tiden via sin modul `time`)
class Klocka:
    nu = 5000.0
    def monotonic(self): return self.nu
    def __getattr__(self, n): return getattr(time, n)
klocka = Klocka()
verklig_time = sessioner.time
sessioner.time = klocka
sessioner.nollstall()
a, _ = sessioner.hamta_eller_skapa(None)
klocka.nu += sessioner.TTL_S - 1
kolla(sessioner.hamta_eller_skapa(a.id)[0] is a, "strax före tidsgränsen finns sessionen kvar (och förnyas av användningen)")
klocka.nu += sessioner.TTL_S + 1
b, nyb = sessioner.hamta_eller_skapa(a.id)
kolla(nyb and b is not a, "efter tidsgränsen är sessionen glömd: samma id ger en ny, tom session")
sessioner.nollstall()
sessioner.MAX_SESSIONER, gammalt_tak = 5, sessioner.MAX_SESSIONER
forsta, _ = sessioner.hamta_eller_skapa(None)
for _ in range(8):
    klocka.nu += 1
    sessioner.hamta_eller_skapa(None)
kolla(sessioner.antal() <= 5, f"antalet sessioner har tak ({sessioner.antal()} av högst 5 efter 9 skapade)")
kolla(sessioner.hamta_eller_skapa(forsta.id)[1], "när taket nås glöms den äldsta oanvända först")
sessioner.MAX_SESSIONER = gammalt_tak
sessioner.time = verklig_time
sessioner.nollstall()

# --- jobben ----------------------------------------------------------------------------------------------------------
print("== jobb.py med sessioner ==")
frigor = {n: threading.Event() for n in ("a", "b", "c")}
kord = []


besokare = {n: sessioner.Session(("%x" % i) * 32) for i, n in enumerate("abc", 1)}
# stubben väntar på besökarens egen händelse (nyckel: de första 8 tecknen i id:t)
frigor_efter_id = {besokare[n].kort(): frigor[n] for n in "abc"}
frigor_efter_id["ingen"] = threading.Event()
jobbmodul.ATGARDER["kor-batch"] = (jobbmodul.ATGARDER["kor-batch"][0], 1,
                                   lambda j, a: (kord.append(j.session.kort() if j.session else "ingen"),
                                                 frigor_efter_id[j.session.kort() if j.session else "ingen"].wait(10), {"ok": True})[2])


def som(n, fn, *a, **kw):
    tok = sessioner.satt(besokare[n] if n else None)
    try:
        return fn(*a, **kw)
    finally:
        sessioner.aterstall(tok)


def vanta(villkor, s=5):
    t0 = time.time()
    while time.time() - t0 < s:
        if villkor():
            return True
        time.sleep(0.05)
    return villkor()


ja = som("a", jobbmodul.starta, "kor-batch")
kolla(ja["status"] == "kör", "första besökaren får sitt jobb att köra direkt")
jb = som("b", jobbmodul.starta, "kor-batch")
kolla(jb["status"] == "kö" and jb["kopos"] == 1, f"en annan besökares jobb KÖAS i stället för att ge ett fel (status {jb['status']}, plats {jb['kopos']})")
jc = som("c", jobbmodul.starta, "kor-batch")
kolla(jc["status"] == "kö" and jc["kopos"] == 2, f"nästa besökare hamnar bakom i kön (plats {jc['kopos']})")
try:
    som("a", jobbmodul.starta, "kor-batch")
    kolla(False, "en besökare med ett pågående jobb ska inte få starta ett till")
except jobbmodul.Upptaget:
    kolla(True, "en besökare har högst ett pågående eller köat jobb (Upptaget)")
try:
    som("b", jobbmodul.starta, "kor-batch")
    kolla(False, "en besökare med ett köat jobb ska inte få starta ett till")
except jobbmodul.Upptaget:
    kolla(True, "även ett köat jobb räknas som pågående")
try:
    som(None, jobbmodul.starta, "kor-batch")
    kolla(False, "utan session ska ett jobb under körning ge 409 som förut")
except jobbmodul.Upptaget:
    kolla(True, "utan session gäller det gamla: ett jobb åt gången, annars Upptaget (409)")
kolla([j["id"] for j in som("a", jobbmodul.lista)] == [ja["id"]] and [j["id"] for j in som("b", jobbmodul.lista)] == [jb["id"]],
      "varje besökare ser bara sina egna jobb i listan")
kolla(som("b", jobbmodul.hamta, ja["id"]) is None and som("b", jobbmodul.hamta, jb["id"]) is not None,
      "ett annat jobb går inte att hämta på id (som om det inte fanns)")
kolla(len(som(None, jobbmodul.lista)) == 3, "utan session syns alla jobb (direktanrop, intern variant)")
kolla(som("a", jobbmodul.aktivt)["id"] == ja["id"] and som("b", jobbmodul.aktivt)["status"] == "kö" and som("c", jobbmodul.aktivt)["kopos"] == 2,
      "aktivt() ger besökarens eget jobb, körande eller köat")
kolla(som(None, jobbmodul.aktivt)["id"] == ja["id"], "utan session ger aktivt() det jobb som kör just nu")
# rensningen tar aldrig ett körande eller köat jobb
jobbmodul.RETENTION = 1
jobbmodul.JOBB.append(jobbmodul.Jobb(9001, "kor-batch", 1, "atgard.kor-batch"))
jobbmodul.JOBB[-1].status = "klar"
jobbmodul.JOBB.append(jobbmodul.Jobb(9002, "kor-batch", 1, "atgard.kor-batch"))
jobbmodul.JOBB[-1].status = "klar"
frigor["a"].set()
vanta(lambda: som("b", jobbmodul.aktivt) and som("b", jobbmodul.aktivt)["status"] == "kör")
kolla(som("b", jobbmodul.aktivt)["status"] == "kör" and som("c", jobbmodul.aktivt)["kopos"] == 1,
      "när det första är klart startar nästa i kön (b) och c flyttar upp till plats 1")
kolla(kord[:2] == [besokare["a"].kort(), besokare["b"].kort()], "jobben körs i ordning: a, sedan b")
# a får starta ett nytt jobb nu när hens förra är klart
frigor_efter_id[besokare["a"].kort()].set()
ja2 = som("a", jobbmodul.starta, "kor-batch")
kolla(ja2["status"] == "kö", "den som är klar får starta ett nytt jobb, som köas bakom de som väntar")
jobbmodul.RETENTION = 40
frigor["b"].set()
kolla(vanta(lambda: som("c", jobbmodul.aktivt) is not None and som("c", jobbmodul.aktivt)["status"] == "kör"), "c startar när b är klar")
frigor["c"].set()
vanta(lambda: som("a", jobbmodul.aktivt) is None and som("b", jobbmodul.aktivt) is None and som("c", jobbmodul.aktivt) is None, 8)
kolla(som("a", jobbmodul.aktivt) is None and som("b", jobbmodul.aktivt) is None and som("c", jobbmodul.aktivt) is None
      and not jobbmodul.KO and not jobbmodul._KOR.is_set(), "när allt är klart är kön tom och ordet fritt")
kolla(all(j["status"] == "klar" for j in som(None, jobbmodul.lista) if j["id"] < 9000), "alla jobb blev klara")

# nästa rimliga åtgärd följer besökarens egna jobb (markeras på knappen i kontrollrummet)
nyb = sessioner.Session("%032x" % 31)
besokare[nyb.id] = nyb
kolla(som(nyb.id, jobbmodul.nasta_atgard) == "kor-batch", "en ny besökare har inte gjort något: nästa är 'kor-batch'")
kolla(som("a", jobbmodul.nasta_atgard) == "hamta-katalog", "besökaren som körde en batch får 'hamta-katalog' härnäst (andras jobb räknas inte)")

# nästa åtgärd som tillståndsmaskin (granskningen 2026-10-23): oberoende av jobblistans gallring, och rätt efter avslag, hävning och nekad leverans
def klart(sess, atgard, status="klar", utfall=None, resultat=None):
    j = jobbmodul.Jobb(8000 + len(atgard), atgard, 1, "atgard." + atgard); j.session = sess; j.status = status; j.utfall = utfall
    j.resultat = resultat
    jobbmodul._notera(j)


def nasta_for(sess):
    return som(sess.id, jobbmodul.nasta_atgard)


for ny_id in (41, 42, 43, 44, 45):
    besokare[("%x" % ny_id) * 32] = sessioner.Session(("%x" % ny_id) * 32)
sa, sb, sc_, sd, se = (besokare[("%x" % i) * 32] for i in (41, 42, 43, 44, 45))
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b"):
    klart(sa, at)
kolla(nasta_for(sa) == "forhandla-a", "efter B-kedjan är nästa 'forhandla-a'")
klart(sa, "forhandla-a"); kolla(nasta_for(sa) == "kov-godkann", "efter Förhandla A är nästa KoV:s godkännande")
klart(sa, "kov-godkann"); kolla(nasta_for(sa) == "transfer-a", "efter godkännandet är nästa 'transfer-a'")
klart(sa, "transfer-a"); kolla(nasta_for(sa) == "analysera", "efter Leverera A är nästa 'analysera' (steg 6, utan knapp); sidan avslutar raden när steg 6 öppnats")
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a"):
    klart(sb, at)
klart(sb, "kov-avsla", utfall="inget-avtal")
kolla(nasta_for(sb) == "forhandla-a", "efter ett AVSLAG är nästa 'forhandla-a' (en ny begäran ska förhandlas; 'transfer-a' bygger på ett avtal som kanske inte längre gäller)")
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a", "kov-godkann"):
    klart(sc_, at)
klart(sc_, "kov-hav")
kolla(nasta_for(sc_) == "forhandla-a", "efter en HÄVNING är nästa 'forhandla-a'")
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a", "kov-godkann"):
    klart(sd, at)
klart(sd, "transfer-a", status="fel", utfall="nekad")
kolla(nasta_for(sd) == "forhandla-a", "efter en nekad leverans av A är nästa 'forhandla-a'")
# Ett avslag av en NY begäran medan ett avtal gäller (delad demon: avslaget häver inget) tar besökaren tillbaka dit hen var; häver avslaget avtal börjar hen om.
for nr_, (havda, forvantat) in enumerate((([], "analysera"), (["x"], "forhandla-a"))):
    sh = sessioner.Session(("%x" % (50 + nr_)) * 32)
    besokare[sh.id] = sh
    for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a", "kov-godkann", "transfer-a"):
        klart(sh, at)
    klart(sh, "forhandla-a")
    kolla(nasta_for(sh) == "kov-godkann", "en ny begäran medan ett avtal gäller: nästa är KoV:s beslut")
    klart(sh, "kov-avsla", utfall=None, resultat={"havdaAvtal": havda})
    kolla(nasta_for(sh) == forvantat, "avslag %s: nästa är '%s'" % ("som häver avtal" if havda else "som inte häver något", forvantat))
sg = sessioner.Session("e" * 32); besokare[sg.id] = sg
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a", "kov-godkann"):
    klart(sg, at)

# Eget felinjektionsläge (C): slås på i FCF bara medan besökarens egen leverans körs, och slås av direkt efteråt, även vid fel
_anrop = []
_orig = (jobbmodul.kallor.fcf_satt_fel, jobbmodul.kallor.fcf_nollstall_fel, jobbmodul.kedjan.kor_transfer, jobbmodul._senaste_avtal)
jobbmodul.kallor.fcf_satt_fel = lambda lagen: _anrop.append(("satt", dict(lagen)))
jobbmodul.kallor.fcf_nollstall_fel = lambda: _anrop.append(("av",))
jobbmodul.kedjan.kor_transfer = lambda avtal, logg: {"kvitto": {"resultat": "LEVERERAD"}}
jobbmodul._senaste_avtal = lambda asset, sess: ("AVTAL1", "FORH1")


def _lev(sess):
    j = jobbmodul.Jobb(8800, "transfer-b", 4, "atgard.transfer-b"); j.session = sess
    jobbmodul._transfer(j, jobbmodul.kallor.ASSET_B)
    return j


_sf = sessioner.Session("d" * 32); besokare[_sf.id] = _sf
_lev(_sf); kolla(_anrop == [], "utan eget läge rörs inte FCF")
_sf.fel_lagen.update({"gis_i_b": True}); _anrop.clear(); _j = _lev(_sf)
kolla(_anrop == [("satt", {"schemadrift": False, "saknade_parametrar": False, "gis_i_b": True}), ("av",)],
      "med eget läge slås felet på före och av efter leveransen (%s)" % _anrop)
kolla(any(r["kod"] == "jobb.felinjektion_pa" for r in _j.rader) and any(r["kod"] == "jobb.felinjektion_av" for r in _j.rader),
      "jobbloggen säger att läget slogs på och av")
_anrop.clear()
jobbmodul.kedjan.kor_transfer = lambda avtal, logg: (_ for _ in ()).throw(RuntimeError("leveransen föll"))
try:
    _lev(_sf)
except RuntimeError:
    pass
kolla(_anrop[-1:] == [("av",)], "felet slås av även när leveransen faller")
_anrop.clear(); jobbmodul.kedjan.kor_transfer = lambda avtal, logg: {"kvitto": {"resultat": "LEVERERAD"}}
_ingen = jobbmodul.Jobb(8801, "transfer-b", 4, "atgard.transfer-b"); _ingen.session = None; jobbmodul._transfer(_ingen, jobbmodul.kallor.ASSET_B)
kolla(_anrop == [], "utan session finns inget eget läge (det gemensamma gäller som förut)")
_sg = sessioner.Session("c" * 32); besokare[_sg.id] = _sg
_sg.fel_lagen.update({"gis_i_b": False}); _lev(_sg); kolla(_anrop == [], "ett läge som är avslaget slår inte på något")
# Säkerhetsnät: ett tvetydigt fel vid påslagningen, ett misslyckat avslag, och att nästa leverans städar före sig
_sh = sessioner.Session("b" * 32); besokare[_sh.id] = _sh; _sh.fel_lagen.update({"gis_i_b": True})
def _satt_fel_timeout(lagen):
    raise jobbmodul.KallFel("timeout efter att FCF tagit emot anropet", status=None)
jobbmodul.kallor.fcf_satt_fel = _satt_fel_timeout
_anrop.clear()
try:
    _lev(_sh)
except jobbmodul.KallFel:
    pass
kolla(("av",) in _anrop and not jobbmodul.skydd.fel_lacka_kvar(), "ett tvetydigt fel vid påslagningen städas direkt (nollställning anropas, inget läckskydd kvar)")
jobbmodul.kallor.fcf_satt_fel = lambda lagen: _anrop.append(("satt", dict(lagen)))
def _av_fel():
    raise OSError("FCF svarar inte")
jobbmodul.kallor.fcf_nollstall_fel = _av_fel
_anrop.clear(); _lev(_sh)
kolla(jobbmodul.skydd.fel_lacka_kvar(), "misslyckas avslaget (även ett annat undantag än KallFel) står läckskyddet kvar")
jobbmodul.kallor.fcf_nollstall_fel = lambda: _anrop.append(("av",))
_anrop.clear(); _ingen2 = sessioner.Session("a" * 32); besokare[_ingen2.id] = _ingen2; _lev(_ingen2)
kolla(_anrop == [("av",)] and not jobbmodul.skydd.fel_lacka_kvar(), "en annan besökares leverans städar det kvarlämnade felet före sig (utan eget läge)")
kolla(not jobbmodul.skydd.fel_lacka_forfallen() and (jobbmodul.skydd.fel_lacka(True) or True) and not jobbmodul.skydd.fel_lacka_forfallen()
      and jobbmodul.skydd.fel_lacka_forfallen(nu=__import__("time").monotonic() + 3600), "städloopen ser ett kvarlämnat fel först efter gränsen")
jobbmodul.skydd.fel_lacka(False)
jobbmodul.kallor.fcf_satt_fel, jobbmodul.kallor.fcf_nollstall_fel, jobbmodul.kedjan.kor_transfer, jobbmodul._senaste_avtal = _orig

klart(sg, "forhandla-a"); klart(sg, "kov-avsla", resultat={"havdaAvtal": []})
kolla(nasta_for(sg) == "transfer-a", "avslag av en ny begäran när det äldre avtalet är godkänt men inte levererat: nästa är 'transfer-a'")
besokare["f" * 32] = sessioner.Session("f" * 32)
sf = besokare["f" * 32]
for at in ("kor-batch", "hamta-katalog", "forhandla-b", "transfer-b", "forhandla-a", "kov-godkann"):
    klart(sf, at)
klart(sf, "kov-hav", status="fel")
kolla(nasta_for(sf) == "transfer-a", "en MISSLYCKAD hävning ändrar inget: avtalet gäller, nästa är fortfarande 'transfer-a'")
klart(sf, "kov-hav")
kolla(nasta_for(sf) == "forhandla-a", "den lyckade hävningen efteråt tar besökaren till 'forhandla-a'")
klart(se, "kor-batch"); jobbmodul.JOBB.clear()           # jobblistan gallras (högst 40 jobb, alla besökares): framstegen ska finnas kvar
kolla(nasta_for(se) == "hamta-katalog", "besökarens framsteg försvinner inte när jobblistan gallras")

# kön har tak
jobbmodul.MAX_KO = 1
frigor_efter_id["ingen"].set()
fyra = [sessioner.Session(("%x" % i) * 32) for i in (11, 12, 13)]
for x in fyra:
    frigor_efter_id[x.kort()] = threading.Event()
    besokare[x.id] = x
sv = []
for x in fyra:
    try:
        sv.append(som(x.id, jobbmodul.starta, "kor-batch")["status"])
    except jobbmodul.Upptaget as e:
        sv.append("nekad:" + e.kod)
kolla(sv == ["kör", "kö", "nekad:fel.kon_full"], f"kön har tak: {sv}")
for x in fyra:
    frigor_efter_id[x.kort()].set()
vanta(lambda: not jobbmodul._KOR.is_set(), 8)
jobbmodul.MAX_KO = 20

# --- ägande av förhandlingar och avtal --------------------------------------------------------------------------------
print("== ägande ==")
kallor_kon, kallor_reg = jobbmodul.kedjan.kov_kon, jobbmodul.kallor.avtalsregister
jobbmodul.kedjan.kov_kon = lambda: [{"id": "dhi-1", "correlationId": "stad-A"}, {"id": "dhi-2", "correlationId": "stad-B"}]
jobbmodul.kallor.avtalsregister = lambda: {"avtal": [{"id": "avtal-A", "dhiAvtalId": "dhi-avtal-A"}, {"id": "avtal-B", "dhiAvtalId": "dhi-avtal-B"}]}
ag, bg = sessioner.Session("%032x" % 21), sessioner.Session("%032x" % 22)
ag.forhandlingar.add("stad-A"); ag.avtal.add("avtal-A"); bg.forhandlingar.add("stad-B"); bg.avtal.add("avtal-B")
kolla(jobbmodul.agd_forhandling(ag, "dhi-1") and not jobbmodul.agd_forhandling(ag, "dhi-2") and jobbmodul.agd_forhandling(bg, "dhi-2"),
      "en förhandling hos DHI tillhör den besökare som startade den (via correlationId)")
kolla(not jobbmodul.agd_forhandling(ag, "finns-inte"), "en okänd förhandling tillhör ingen")
kolla(jobbmodul.agd_forhandling(None, "dhi-2") and jobbmodul.agd_dhi_avtal(None, "vad-som-helst"), "utan session är allt tillåtet som förut")
kolla(jobbmodul.agd_dhi_avtal(ag, "dhi-avtal-A") and not jobbmodul.agd_dhi_avtal(ag, "dhi-avtal-B"), "ett avtal tillhör den vars förhandling gav det")
jobbmodul.kedjan.kov_kon, jobbmodul.kallor.avtalsregister = kallor_kon, kallor_reg
# senaste avtal väljs bland besökarens egna förhandlingar
verklig = jobbmodul.kallor.forhandlingar
jobbmodul.kallor.forhandlingar = lambda limit=50: [
    {"@id": "stad-B", "assetId": "tillgang", "contractAgreementId": "avtal-B"},
    {"@id": "stad-A", "assetId": "tillgang", "contractAgreementId": "avtal-A"}]
kolla(jobbmodul._senaste_avtal("tillgang", ag) == ("avtal-A", "stad-A") and jobbmodul._senaste_avtal("tillgang", bg) == ("avtal-B", "stad-B")
      and jobbmodul._senaste_avtal("tillgang", None) == ("avtal-B", "stad-B") and jobbmodul._senaste_avtal("tillgang", sessioner.Session("%032x" % 23)) == (None, None),
      "'senaste avtalet' är besökarens eget; utan session det senaste överhuvudtaget; en besökare utan avtal får inget")
jobbmodul.kallor.forhandlingar = verklig

print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(1 if fel else 0)
