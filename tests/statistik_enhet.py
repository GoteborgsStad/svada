"""Enhetsprov av services/gemensam/statistik.py. Ingen stack behövs.

Bevisar: bara HTML-sidvisningar räknas som besök (inte polling), robotar och uteslutna adresser hålls utanför, unika räknas per
kapad adress + webbläsare, 401 räknas som avvisade, 429 och 5xx som fel men inte 409, kampanjen ?k= räknas, API-träffar räknas per
värd, dygnet följer svensk tid; historiken behåller dagar vars rålogg roterats bort och en tunnare äldsta dag skriver inte över en
fullständigare; händelsevitlistan avvisar allt utom kända namn; räknaren sparar bara tal per dag och överlever en omstart; tools/
statistik-rapport.py körs mot samma kod.
"""
import datetime as dt
import importlib.util
import ipaddress
import json
import os
import subprocess
import sys
import tempfile

rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(rot, "services"))
from gemensam import statistik as S  # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print(f"  [{'OK' if ok else 'FEL'}] {text}")
    fel += 0 if ok else 1


def ts(tid):  # lokal svensk tid -> epok
    return dt.datetime.fromisoformat(tid).replace(tzinfo=S.TZ).timestamp()


def post(tid, host, uri="/", status=200, ip="10.1.2.0", ua="Mozilla/5.0 Safari", typ="text/html; charset=utf-8", metod="GET"):
    return {"ts": ts(tid), "status": status,
            "request": {"remote_ip": ip, "client_ip": ip, "method": metod, "host": host, "uri": uri, "headers": {"User-Agent": [ua]}},
            "resp_headers": {"Content-Type": [typ]}}


H = "svada-demo.example"
poster = [
    post("2026-10-20T10:00:00", H),
    post("2026-10-20T10:00:05", H, "/api/status", typ="application/json"),
    post("2026-10-20T10:01:00", H, "/?lang=en&k=webinar"),
    post("2026-10-20T11:00:00", H, ip="10.9.9.0"),
    post("2026-10-20T11:00:00", H, ua="Googlebot/2.1"),
    post("2026-10-20T11:00:00", H, ua="curl/8.7.1"),
    post("2026-10-20T11:00:00", H, status=401, typ="text/plain"),                      # samma besökare som fick sidor: inte avvisad
    post("2026-10-20T11:00:00", H, status=401, typ="text/plain", ip="10.7.7.0"),       # kom aldrig förbi lösenordet: avvisad
    post("2026-10-20T11:00:00", H, status=401, typ="text/plain", ip="10.8.8.0", ua="curl/8.7.1"),   # robot: räknas inte som avvisad
    post("2026-10-20T11:00:00", H, status=401, typ="text/plain", ip="10.9.1.0"),       # första 401:an hos den som sedan loggar in ...
    post("2026-10-20T11:00:05", H, ip="10.9.1.0"),                                     # ... och sedan får en sida: inte avvisad
    post("2026-10-20T11:00:00", H, status=429, typ="text/plain", metod="POST"),
    post("2026-10-20T11:00:00", H, status=409, typ="application/json", metod="POST"),
    post("2026-10-20T11:00:00", H, status=502, typ="text/plain"),
    post("2026-10-20T12:00:00", "brunnar." + H + ":38080", "/brunnar"),
    post("2026-10-20T12:00:00", "tidsserie." + H, "/temporal/entities", typ="application/json"),
    post("2026-10-20T12:00:00", "tidsserie." + H, "/temporal/entities", status=403, typ="text/plain"),
    post("2026-10-20T12:00:00", "cip." + H, "/ngsi-ld/v1/entities", status=401, typ="application/json"),
    post("2026-10-20T12:00:00", H, ip="192.168.7.0"),
    post("2026-10-19T23:30:00", H, ip="10.5.5.0"),
    post("2026-10-20T00:30:00", H, ip="10.6.6.0"),
]
uteslutna = [ipaddress.ip_network("192.168.7.0/24")]
rakn, unika, kamp, aldsta = S.raknaa(poster, uteslutna)
d20, d19 = "2026-10-20", "2026-10-19"
kr = rakn[(d20, "kontrollrum")]
kolla(kr["sidvisningar"] == 5, f"sidvisningar på kontrollrummet 20/10: {kr['sidvisningar']} (väntade 5)")
kolla(len(unika[(d20, "kontrollrum")]) == 4, f"unika 20/10: {len(unika[(d20, 'kontrollrum')])} (väntade 4)")
kolla(kr["robot"] == 3, f"robotar: {kr['robot']} (väntade 3, hålls utanför besöken)")
kolla(kr["avvisade"] == 1, f"avvisade: {kr['avvisade']} (väntade 1: bara den som aldrig fick en sida; inte robotar och inte den som loggade in)")
kolla(kr["fel"] == 1 and kr["begransade"] == 1, f"fel: {kr['fel']} och begränsade: {kr['begransade']} (väntade 1 och 1: 502 är ett fel, 429 en spärr som redovisas skilt, 409 räknas inte)")
kolla(kamp[(d20, "kontrollrum")] == {"webinar": 1}, f"kampanjen ?k=webinar räknas: {dict(kamp[(d20, 'kontrollrum')])}")
kolla(rakn[(d20, "brunnar")]["sidvisningar"] == 1, "värdnamnet med port känns igen som brunnar")
kolla(rakn[(d20, "tidsserie")]["api_traffar"] == 1, "tidsserie: bara lyckade GET räknas som API-träff (403 räknas inte)")
kolla(rakn[(d20, "cip")]["api_traffar"] == 1, "cip: varje anrop räknas")
kolla(rakn[(d19, "kontrollrum")]["sidvisningar"] == 1, "23:30 räknas som 19/10 och 00:30 som 20/10 (svensk tid)")
kolla(aldsta == d19, f"äldsta dag i loggen: {aldsta}")
kolla("192.168.7.0" not in str(sorted(unika[(d20, 'kontrollrum')])), "den uteslutna adressen ingår inte")

# Historiken: rotation tar bort rålogg, men sparade dagar finns kvar; den äldsta dagen är ofullständig
rader = S.dagsrader(rakn, unika, kamp)
hist = {"2026-10-10": {"kontrollrum": {"sidvisningar": 50, "unika": 9, "avvisade": 0, "api_traffar": 0, "robotar": 0, "fel": 0, "kampanjer": {}}},
        d19: {"kontrollrum": {"sidvisningar": 10, "unika": 5, "avvisade": 0, "api_traffar": 0, "robotar": 0, "fel": 0, "kampanjer": {}}}}
ihop = S.sla_ihop(hist, rader, aldsta)
kolla("2026-10-10" in ihop and ihop["2026-10-10"]["kontrollrum"]["sidvisningar"] == 50, "en dag vars rålogg är borta finns kvar i historiken")
kolla(ihop[d19]["kontrollrum"]["sidvisningar"] == 10 and ihop[d19]["kontrollrum"]["unika"] == 5, "den äldsta (ofullständiga) dagen skriver inte över en fullständigare rad")
kolla(ihop[d20]["kontrollrum"]["sidvisningar"] == 5, "en fullständig dag skriver över")
tunn = S.sla_ihop({d20: {"kontrollrum": {"sidvisningar": 99, "unika": 1, "avvisade": 0, "api_traffar": 0, "robotar": 0, "fel": 0, "kampanjer": {}}}}, rader, d20)
kolla(tunn[d20]["kontrollrum"]["sidvisningar"] == 99 and tunn[d20]["kontrollrum"]["unika"] == 4, "är dagen den äldsta tas per fält det största av gammalt och nytt")

# Händelsevitlistan
ATG = ("forhandla-b", "kor-batch", "kov-hav")
giltiga = ["steg_1", "steg_6", "flik_jobb", "flik_ordlista", "sprak_en", "karta_osm", "analys_a", "js_fel", "atgard_nekad", "atgard_forhandla-b", "atgard_kov-hav"]
ogiltiga = ["steg_0", "steg_7", "flik_x", "atgard_rm-rf", "atgard_", "1.2.3.4", "steg_1 ", "STEG_1", "", None, 5, ["steg_1"], "steg_1" * 20]
kolla(all(S.giltig_handelse(n, ATG) for n in giltiga), "alla vitlistade händelser godtas")
kolla(not any(S.giltig_handelse(n, ATG) for n in ogiltiga), "okända namn, fritext, fel typ och för långa namn avvisas")

# Räknaren sparar bara tal per dag och överlever en omstart
with tempfile.TemporaryDirectory() as kat:
    h = S.Handelser(kat)
    nu = ts("2026-10-20T12:00:00")
    for _ in range(3):
        h.rakna("steg_3", nu)
    h.rakna("flik_jobb", nu)
    h.spola()
    lagrat = json.load(open(os.path.join(kat, "data", "handelser.json")))
    kolla(lagrat == {d20: {"steg_3": 3, "flik_jobb": 1}}, f"lagrat: {lagrat} (bara dag, namn och antal)")
    kolla(S.Handelser(kat).alla() == {d20: {"steg_3": 3, "flik_jobb": 1}}, "räknaren överlever en omstart")
    # historik + rapport mot en egen katalog
    os.makedirs(os.path.join(kat, "logg"))
    with open(os.path.join(kat, "logg", "access.log"), "w") as f:
        f.write("\n".join(json.dumps(p) for p in poster) + "\n{trasig\n")
    hist2 = S.uppdatera_historik(kat, uteslutna)
    kolla(hist2[d20]["kontrollrum"]["sidvisningar"] == 5 and os.path.exists(os.path.join(kat, "data", "dagligt.json")), "uppdatera_historik räknar loggen (trasig rad hoppas över) och sparar dagssummorna")
    os.remove(os.path.join(kat, "logg", "access.log"))
    kolla(S.uppdatera_historik(kat)[d20]["kontrollrum"]["sidvisningar"] == 5, "efter att rålogg tagits bort finns dagssummorna kvar")
    ut = subprocess.run([sys.executable, "-I", os.path.join(rot, "tools", "statistik-rapport.py"), "--katalog", kat], capture_output=True, text=True)
    kolla(ut.returncode == 0 and "kontrollrum" in ut.stdout and d20 in ut.stdout, "tools/statistik-rapport.py visar historiken")
    sam = S.sammanstall(hist2, S.Handelser(kat).alla(), idag=dt.date(2026, 10, 21), dagar=3)
    kolla([d["dag"] for d in sam["dagar"]] == ["2026-10-19", d20, "2026-10-21"] and sam["handelser"]["steg_3"] == 3, "sammanställningen ger de senaste dagarna och händelsesummorna")

# Roterade och gzippade filer (granskningsfynd 2026-10-19): Caddy döper en roterad fil access-<tid>-size.log.gz
import gzip
import stat
with tempfile.TemporaryDirectory() as kat:
    os.makedirs(os.path.join(kat, "logg"))
    halv = len(poster) // 2
    with gzip.open(os.path.join(kat, "logg", "access-2026-10-20T14-00-00.000-size.log.gz"), "wt") as f:
        f.write("\n".join(json.dumps(p) for p in poster[:halv]) + "\n")
    with open(os.path.join(kat, "logg", "access.log"), "w") as f:
        f.write("\n".join(json.dumps(p) for p in poster[halv:]) + "\n")
    ihop_filer = S.uppdatera_historik(kat, uteslutna)
    kolla(ihop_filer[d20]["kontrollrum"]["sidvisningar"] == 5 and ihop_filer[d20]["kontrollrum"]["unika"] == 4 and ihop_filer[d20]["kontrollrum"]["avvisade"] == 1,
          "en gzippad roterad fil och den aktuella räknas ihop (inte bara den aktuella): " + str({k: ihop_filer[d20]["kontrollrum"][k] for k in ("sidvisningar", "unika", "avvisade")}))
    kolla(len(S._CACHE) == 1, "den roterade filen cachas (oföränderlig), den aktuella läses om")
    kolla(stat.S_IMODE(os.stat(os.path.join(kat, "data", "dagligt.json")).st_mode) == 0o644, "dagligt.json är läsbar för en vanlig användare (0644)")
    # en trasig dagligt.json skrivs inte över
    with open(os.path.join(kat, "data", "dagligt.json"), "w") as f:
        f.write("{trasig json som inte går att tolka")
    S.uppdatera_historik(kat, uteslutna)
    kolla(any(n.startswith("dagligt.json.trasig-") for n in os.listdir(os.path.join(kat, "data"))), "en trasig dagligt.json flyttas åt sidan i stället för att skrivas över")
    # uteslutning via miljön: samma tal på sidan och i rapporten
    os.environ["STATISTIK_UTESLUT"] = "10.1.2.0/24, 10.9.9.0/24"
    ute = S.uppdatera_historik(kat)  # historiken har redan dagen; uteslutningen gäller de nya räkningarna
    kolla(S.uteslutna_fran_miljon() == [ipaddress.ip_network("10.1.2.0/24"), ipaddress.ip_network("10.9.9.0/24")], "STATISTIK_UTESLUT läses som kapade adresser (CIDR)")
    r_utan = S.raknaa_katalog(kat, S.uteslutna_fran_miljon())
    r_med = S.raknaa_katalog(kat, [])
    kolla(len(r_utan.unika[(d20, "kontrollrum")]) < len(r_med.unika[(d20, "kontrollrum")]), "uteslutna adresser räknas inte (och cachen blandar inte ihop med och utan uteslutning)")
    del os.environ["STATISTIK_UTESLUT"]
    # en fil som inte går att läsa hoppas över
    if os.getuid() != 0:
        os.chmod(os.path.join(kat, "logg", "access-2026-10-20T14-00-00.000-size.log.gz"), 0)
        S._CACHE.clear()
        try:
            S.raknaa_katalog(kat, [])
            kolla(True, "en oläsbar logg-fil hoppas över i stället för att fälla räkningen")
        except Exception as e:  # noqa: BLE001
            kolla(False, "en oläsbar logg-fil fällde räkningen: %r" % e)

# Åtgärdsnamn på sidan: knapptexten på vyns språk, inte åtgärdens id (granskningsfynd)
sys.path.insert(0, os.path.join(rot, "services", "dashboard"))
import statistiksida as _sida  # noqa: E402
_sam = S.sammanstall({}, {"2026-10-20": {"atgard_forhandla-a": 3, "atgard_kor-batch": 2, "atgard_kov-hav": 1}}, idag=dt.date(2026, 10, 21), dagar=3)
_sv, _en = _sida.sida(_sam, "sv"), _sida.sida(_sam, "en")
kolla("Förhandla Distribution A" in _sv and "forhandla-a" not in _sv and "kor-batch" not in _sv, "sidan visar knapptexten på svenska i stället för åtgärdens id")
kolla("Negotiate Distribution A" in _en and "forhandla-a" not in _en and "kontrollrum" not in _en and "brunnar" not in _en.replace("chambers", ""), "den engelska sidan har engelska knapptexter och inga svenska värdnamn")

# Under komprimeringen finns både X.log och X.log.gz: bara en räknas; en oläsbar historik skrivs inte över; en korrupt .gz fäller inte räkningen
with tempfile.TemporaryDirectory() as kat:
    os.makedirs(os.path.join(kat, "logg"))
    rad = "\n".join(json.dumps(p) for p in poster) + "\n"
    open(os.path.join(kat, "logg", "access-2026-10-20T14-00-00.000-size.log"), "w").write(rad)
    with gzip.open(os.path.join(kat, "logg", "access-2026-10-20T14-00-00.000-size.log.gz"), "wt") as f:
        f.write(rad)
    kolla(len(S.logg_filer(kat)) == 1 and S.logg_filer(kat)[0].endswith(".gz"), "finns både X.log och X.log.gz räknas bara den komprimerade (ingen dubbelräkning)")
    kolla(S.uppdatera_historik(kat, uteslutna)[d20]["kontrollrum"]["sidvisningar"] == 5, "…och talet blir det rätta, inte det dubbla")
    with open(os.path.join(kat, "logg", "access-2026-10-20T15-00-00.000-size.log.gz"), "wb") as f:
        f.write(b"\x1f\x8b\x08\x00trasig gzip som inte gar att packa upp")
    try:
        S.uppdatera_historik(kat, uteslutna)
        kolla(True, "en korrupt .gz-fil hoppas över i stället för att fälla räkningen")
    except Exception as e:  # noqa: BLE001
        kolla(False, "en korrupt .gz-fil fällde räkningen: %r" % e)
    if os.getuid() != 0:
        sokvag = os.path.join(kat, "data", "dagligt.json")
        os.chmod(sokvag, 0)
        före = sorted(os.listdir(os.path.join(kat, "data")))
        S.uppdatera_historik(kat, uteslutna)
        kolla(sorted(os.listdir(os.path.join(kat, "data"))) == före, "en oläsbar (inte trasig) dagligt.json flyttas inte åt sidan och skrivs inte över")
        os.chmod(sokvag, 0o644)

# Kampanjnycklar har tak (en länk med ?k=<valfritt> får inte fylla lagret)
mangd = [post("2026-10-20T10:00:%02d" % (i % 60), H, "/?k=kamp%d" % i, ip="10.%d.%d.0" % (i // 250, i % 250)) for i in range(300)]
rk, uk, kk, _ = S.raknaa(mangd)
kolla(len(kk[(d20, "kontrollrum")]) <= S.KAMPANJ_MAX + 1 and kk[(d20, "kontrollrum")]["(övriga)"] > 0, f"kampanjnycklarna har tak: {len(kk[(d20, 'kontrollrum')])} nycklar av 300 olika")

# En trasig handelser.json skrivs inte över
with tempfile.TemporaryDirectory() as kat:
    os.makedirs(os.path.join(kat, "data"))
    with open(os.path.join(kat, "data", "handelser.json"), "w") as f:
        f.write("{trasig")
    S.Handelser(kat)
    kolla(any(n.startswith("handelser.json.trasig-") for n in os.listdir(os.path.join(kat, "data"))), "en trasig handelser.json flyttas åt sidan")

# Sidan: rendering utan stack
sys.path.insert(0, os.path.join(rot, "services", "dashboard"))
import statistiksida  # noqa: E402
sida = statistiksida.sida(sam, "sv") + statistiksida.sida(sam, "en")
kolla("<script" not in sida and "http://" not in sida and "https://" not in sida, "sidan har inget skript och inga externa adresser (sv och en)")
kolla(statistiksida.sida(S.sammanstall({}, {}, idag=dt.date(2026, 10, 21), dagar=3), "sv").count("Ingen statistik ännu") >= 1, "sidan klarar att det inte finns någon data ännu")
# Testläge: anrop med loggfältet test=1 och själva ?test=1-anropet räknas inte; övriga räknas som förut
def _post(ts, uri, test=None, ua="Mozilla/5.0 (X11) Chrome/120"):
    p = {"ts": ts, "status": 200, "request": {"host": "demo.example.org", "method": "GET", "uri": uri, "client_ip": "203.0.113.0",
         "headers": {"User-Agent": [ua]}}, "resp_headers": {"Content-Type": ["text/html; charset=utf-8"]}}
    if test is not None:
        p["test"] = test
    return p


_ts = dt.datetime(2026, 10, 23, 12, 0, tzinfo=S.TZ).timestamp()
_r = S.raknaa_poster([_post(_ts, "/"), _post(_ts, "/?test=1"), _post(_ts, "/", test="1"), _post(_ts, "/?k=x&test=1&y=2"), _post(_ts, "/", test="")])
_rad = _r.rakn[("2026-10-23", "kontrollrum")]
kolla(_rad["sidvisningar"] == 2, "testläge: bara de två vanliga sidvisningarna räknas (test=1 i loggen och ?test=1 hoppas över; test=\"\" är ett vanligt besök) – fick %d" % _rad["sidvisningar"])
kolla(S.raknaa_poster([_post(_ts, "/", test="1")]).rakn == {}, "testläge: en rad med test=1 lämnar inga spår alls (inte ens som anrop)")
# Serverfel och 429 per dag: visar när det strulade
_sf = S.sammanstall({"2026-10-20": {"kontrollrum": {"fel": 3, "begransade": 5}, "tidsserie": {"fel": 2}}, "2026-10-21": {"kontrollrum": {"fel": 0}}}, {},
                    idag=dt.date(2026, 10, 21), dagar=2)
_d = {x["dag"]: x for x in _sf["dagar"]}
kolla(_d["2026-10-20"]["fel"] == 5 and _d["2026-10-20"]["begransade"] == 5 and _d["2026-10-21"]["fel"] == 0, "dagstabellen bär serverfel och 429 per dag (alla värdar)")
kolla("<th>Serverfel (5xx)</th>" in statistiksida.sida(_sf, "sv") and "<th>Server errors (5xx)</th>" in statistiksida.sida(_sf, "en"), "dagstabellen har kolumnerna för serverfel och 429 på båda språken")
# Besökare = kapad adress + webbläsare: datorer med samma webbläsare bakom en adress blir EN besökare, olika webbläsare blir flera (texten på /statistik säger det).
_u = S.raknaa_poster([_post(_ts, "/", ua="Mozilla/5.0 (Macintosh) Safari/605"), _post(_ts, "/", ua="Mozilla/5.0 (Macintosh) Safari/605"),
                      _post(_ts, "/", ua="Mozilla/5.0 (Windows NT 10.0) Edg/120")])
kolla(len(_u.unika[("2026-10-23", "kontrollrum")]) == 2, "samma adress: två datorer med samma webbläsare räknas som en, en annan webbläsare som en till (2 besökare)")
# Öppen demo (ingen lösenordsgrind): inga avvisade, så sidan talar inte om lösenord; finns avvisade visas kolumnen och förklaringen.
_tom = statistiksida.sida(S.sammanstall({}, {}, idag=dt.date(2026, 10, 21), dagar=3), "sv")
kolla("lösenord" not in _tom.lower() and "Avvisade" not in _tom, "öppen demo: statistiken nämner inget lösenord och har ingen kolumn för avvisade")
_av = S.sammanstall({"2026-10-21": {"kontrollrum": {"sidvisningar": 3, "unika": 2, "avvisade": 2}}}, {}, idag=dt.date(2026, 10, 21), dagar=1)
_avsv, _aven = statistiksida.sida(_av, "sv"), statistiksida.sida(_av, "en")
kolla("<th>Avvisade vid lösenordet" in _avsv and "Avvisade:" in _avsv, "finns avvisade (grind på): kolumnen och förklaringen om lösenordet visas på svenska")
kolla("<th>Turned away at the password" in _aven and "Turned away:" in _aven, "finns avvisade (grind på): kolumnen och förklaringen visas på engelska")
_tomen = statistiksida.sida(S.sammanstall({}, {}, idag=dt.date(2026, 10, 21), dagar=3), "en")
kolla("Turned away" not in _tomen and "password" not in _tomen.lower(), "öppen demo: den engelska sidan nämner inget lösenord och har ingen kolumn för avvisade")
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(1 if fel else 0)
