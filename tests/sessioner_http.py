"""HTTP-prov av en egen vy per besökare mot en körande stack (kontrollrummet direkt på porten, med X-Forwarded-For satt = "via Caddy").

Två besökare (olika kakburkar) och en tredje utan proxyhuvud. Bevisar: kakan sätts; besökare 2 ser inte besökare 1:s jobb, KoV-förfrågan
eller avtal; besökare 2 nekas (403) att besluta eller häva besökare 1:s saker; besökare 1 kan själv; anrop utan proxyhuvud berörs inte.
Skriver aldrig ut kakvärden. Förutsätter DEMO_VARIANT=extern och DASH_SESSIONER=ja. Körs:  python3 -I tests/sessioner_http.py [bas-url]
"""
import json
import sys
import time
import urllib.error
import urllib.request

BAS = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:38800"
fel = 0


def kolla(ok, text):
    global fel
    print(f"  [{'OK' if ok else 'FEL'}] {text}")
    fel += 0 if ok else 1


class Besokare:
    def __init__(self, ip):
        self.ip, self.kaka = ip, None

    def anrop(self, metod, vag, proxy=True, kropp=None):
        h = {"Accept": "application/json"}
        if proxy:
            h["X-Forwarded-For"] = self.ip
            h["X-Forwarded-Proto"] = "https"
            if metod == "POST":
                h["Origin"] = "https://" + BAS.split("//", 1)[1]
        if self.kaka:
            h["Cookie"] = "svada-sess=" + self.kaka
        if kropp is not None:
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(BAS + vag, method=metod, headers=h, data=(json.dumps(kropp).encode() if kropp is not None else b"") if metod == "POST" else None)
        try:
            with urllib.request.urlopen(r, timeout=60) as s:
                sc = s.headers.get_all("Set-Cookie") or []
                for c in sc:
                    if c.startswith("svada-sess="):
                        self.kaka = c.split(";")[0].split("=", 1)[1]
                return s.status, json.loads(s.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, None


def jobb(b, atgard):
    for _ in range(120):
        sc, j = b.anrop("POST", "/api/atgard/" + atgard)
        if sc != 429:
            break
        time.sleep(2)
    if sc not in (200, 202) or not j:
        return sc, None
    jid = j.get("id") or (j.get("jobb") or {}).get("id")
    for _ in range(240):
        sc2, st = b.anrop("GET", "/api/jobb/%s" % jid)
        if sc2 == 200 and st and st.get("status") in ("klar", "fel"):
            return sc, st
        time.sleep(1)
    return sc, None


v1, v2 = Besokare("203.0.113.11"), Besokare("203.0.113.22")
print("== kaka ==")
sc, _ = v1.anrop("GET", "/api/jobb")
kolla(sc == 200 and v1.kaka and len(v1.kaka) == 32, "första anropet via proxy ger en kaka med 128 bitars id")
v2.anrop("GET", "/api/jobb")
kolla(v2.kaka and v2.kaka != v1.kaka, "en annan besökare får en annan kaka")
fore = v1.kaka
v1.anrop("GET", "/api/jobb")
kolla(v1.kaka == fore, "kakan är stabil (samma besökare behåller sin session)")
direkt = Besokare("0.0.0.0")
sc, lst = direkt.anrop("GET", "/api/jobb", proxy=False)
kolla(sc == 200 and direkt.kaka is None, "anrop utan proxyhuvud (direkt mot porten) får ingen kaka och berörs inte")

print("== besökare 1 kör kedjan, besökare 2 ser inget ==")
sc, st = jobb(v1, "kor-batch")
kolla(st and st["status"] == "klar", "besökare 1: batch klar")
sc, st = jobb(v1, "hamta-katalog")
kolla(st and st["status"] == "klar", "besökare 1: katalog klar")
sc, st = jobb(v1, "forhandla-b")
kolla(st and st["status"] == "klar", "besökare 1: förhandling B klar")
sc, st = jobb(v1, "transfer-b")
kolla(st and st["status"] == "klar", "besökare 1: överföring B klar")
sc, l1 = v1.anrop("GET", "/api/jobb")
sc, l2 = v2.anrop("GET", "/api/jobb")
n1 = len(l1.get("jobb", l1) if isinstance(l1, dict) else l1)
n2 = len(l2.get("jobb", l2) if isinstance(l2, dict) else l2)
kolla(n1 >= 4 and n2 == 0, f"besökare 1 ser sina jobb ({n1}), besökare 2 inga ({n2})")
sc, a1 = v1.anrop("GET", "/api/avtal")
sc, a2 = v2.anrop("GET", "/api/avtal")
lista = lambda x: x.get("avtal", x) if isinstance(x, dict) else x
kolla(len(lista(a1)) >= 1 and len(lista(a2)) == 0, f"avtal: besökare 1 ser {len(lista(a1))}, besökare 2 {len(lista(a2))}")

# ingen rättvisepaus för besökare med en egen vy: när ett jobb är klart kan nästa köras direkt (besökartestet 2026-10-22)
sc_a, ja = v2.anrop("POST", "/api/atgard/kor-batch")
jid = (ja or {}).get("id")
for _ in range(120):
    sc_s, st = v2.anrop("GET", "/api/jobb/%s" % jid)
    if sc_s == 200 and st and st.get("status") in ("klar", "fel"):
        break
    time.sleep(0.5)
sc_b, _ = v2.anrop("POST", "/api/atgard/hamta-katalog")
kolla(sc_a in (200, 202) and sc_b in (200, 202), f"ingen rättvisepaus med en egen vy: batch klar ({sc_a}) och direkt därefter katalog ({sc_b}, inte 429)")
sc, sk = v2.anrop("GET", "/api/skydd")
kolla(sc == 200 and sk.get("pausS") == 0 and sk.get("regler", {}).get("pausS") == 0, "/api/skydd: pausen är 0 för besökare med en egen vy")
print("== analys, status och stegdetaljer följer besökaren ==")
sc, d2 = v2.anrop("GET", "/api/steg")
sc, d1 = v1.anrop("GET", "/api/steg")
avt = [x["id"] for x in lista(a1)]
t1, t2 = json.dumps(d1), json.dumps(d2)
kolla(bool(avt) and all(i in t1 for i in avt[:1]) and not any(i in t2 for i in avt),
      "/api/steg: besökare 1 ser sitt avtals-id i stegdetaljerna, besökare 2 inget av besökare 1:s avtal")
sc, e2 = v2.anrop("GET", "/api/steg/5/exempel")
kolla(sc == 200 and not any(i in json.dumps(e2) for i in avt), "/api/steg/5/exempel visar inget av besökare 1:s avtal för besökare 2")
sc, f2 = v2.anrop("GET", "/api/folj")
kolla(sc == 200 and not any(i in json.dumps(f2) for i in avt), "/api/folj visar inget av besökare 1:s avtal för besökare 2")
sc, s2 = v2.anrop("GET", "/api/status")
kolla(sc == 200 and s2["avtalA"]["gallande"] is False, "/api/status: besökare 2 (utan A-avtal) får avtalA.gallande=false")

print("== A-förhandling, KoV och ägarkontroll ==")
sc, st = jobb(v1, "forhandla-a")   # startar förhandlingen; KoV-beslutet väntar hos providern
sc, k1 = v1.anrop("GET", "/api/kov")
sc, k2 = v2.anrop("GET", "/api/kov")
v1v = [f for f in k1["vantande"]]
kolla(len(v1v) == 1 and k1["count"] >= 1 and k2["count"] == 0 and not k2["vantande"],
      f"KoV-rutan: besökare 1 ser sin väntande förfrågan ({len(v1v)}), besökare 2 ser ingen ({k2['count']})")
fid = v1v[0]["id"] if v1v else "saknas"
sc, _ = v2.anrop("POST", "/api/kov/%s/godkann" % fid)
kolla(sc == 403, f"besökare 2 nekas (403) att godkänna besökare 1:s förfrågan (fick {sc})")
sc, k1b = v1.anrop("GET", "/api/kov")
kolla(len(k1b["vantande"]) == 1, "förfrågan är orörd efter nekandet")
sc, _ = v2.anrop("POST", "/api/kov/finns-inte-alls/godkann")
kolla(sc == 403, f"ett okänt förhandlings-id ger också 403 (fick {sc})")
for _ in range(120):                    # kön: nästa jobb kan få vänta tills ett tidigare jobb är klart (ingen rättvisepaus med egen vy)
    sc, j = v1.anrop("POST", "/api/kov/%s/godkann" % fid)
    if sc != 429:
        break
    time.sleep(2)
kolla(sc in (200, 202), f"besökare 1 kan godkänna sin egen förfrågan (fick {sc})")
for _ in range(240):
    sc, k1c = v1.anrop("GET", "/api/kov")
    if not k1c["vantande"]:
        break
    time.sleep(1)
kolla(not k1c["vantande"], "godkännandet gick igenom hos providern")
for _ in range(30):                     # stadens avtal blir klart en stund efter godkännandet; statuscachen är 2 s per besökare
    time.sleep(2)
    sc, s1 = v1.anrop("GET", "/api/status")
    if s1["avtalA"]["gallande"] is True:
        break
sc, s2 = v2.anrop("GET", "/api/status")
kolla(s1["avtalA"]["gallande"] is True and s2["avtalA"]["gallande"] is False,
      "/api/status: besökare 1 har ett gällande A-avtal, besökare 2 inte (värdet delas inte mellan besökare)")
sc, an2 = v2.anrop("GET", "/api/analys?lage=a")
sc1, an1 = v1.anrop("GET", "/api/analys?lage=a")
print("  (analys läge A: besökare 1 fick %s, besökare 2 fick %s)" % (sc1, sc))
# avtalshävning: besökare 2 får inte häva besökare 1:s avtal
dh = []
for _ in range(240):
    sc, a1 = v1.anrop("GET", "/api/avtal")
    dh = [x["dhiAvtalId"] for x in lista(a1) if x.get("dhiAvtalId")]
    if dh:
        break
    time.sleep(2)
kolla(bool(dh), "besökare 1 ser ett avtal med DHI-id efter godkännandet")
if dh:
    sc, _ = v2.anrop("POST", "/api/kov/avtal/%s/hav" % dh[0])
    kolla(sc == 403, f"besökare 2 nekas (403) att häva besökare 1:s avtal (fick {sc})")
    sc, _ = v2.anrop("POST", "/api/kov/avtal/finns-inte/hav")
    kolla(sc == 403, f"ett okänt avtals-id ger också 403 (fick {sc})")

# Eget felinjektionsläge: besökare 1 slår på ett läge; besökare 2 ser det inte, och inget delat läge eller timer finns
sc, f1 = v1.anrop("POST", "/api/felinjektion", kropp={"gis_i_b": True})
kolla(sc == 200 and f1 and f1["lagen"]["gis_i_b"] is True and f1.get("egen") is True, f"besökare 1 slår på sitt eget felinjektionsläge (HTTP {sc})")
sc, f2 = v2.anrop("GET", "/api/felinjektion")
kolla(sc == 200 and f2 and f2["lagen"]["gis_i_b"] is False and f2["aktiv"] is False, "besökare 2 ser inget påslaget läge: felinjektionen är besökarens egen")
sc, sk = v2.anrop("GET", "/api/skydd")
kolla(sc == 200 and sk and sk.get("felinjektionS") is None, "det finns ingen gemensam felinjektionstimer för besökare 2")
sc, f1b = v1.anrop("GET", "/api/felinjektion")
kolla(f1b and f1b["lagen"]["gis_i_b"] is True, "besökare 1 behåller sitt läge (till sin nästa leverans)")
sc, f1c = v1.anrop("POST", "/api/felinjektion/reset", kropp={})
kolla(sc == 200 and f1c and f1c["aktiv"] is False, "besökare 1 nollställer sitt läge")
# Felinjektionen är besökarens eget läge: samtidiga leveranser från två besökare (F6 från externa testet får inte komma tillbaka).
# Besökare 1 har läget på. Besökare 2 och en ny tredje besökare ska aldrig få det, och leveranserna körs direkt efter varandra i kön:
# modellens läge måste vara avslaget innan besökare 2:s jobb startar. Tre rundor med klick inom samma ögonblick.
print("== felinjektion: samtidiga leveranser, två besökare ==")
import threading
sc, st = jobb(v2, "hamta-katalog")
sc, st = jobb(v2, "forhandla-b")
kolla(st and st["status"] == "klar", "besökare 2: förhandling B klar (behövs för att kunna leverera B)")
v3 = Besokare("203.0.113.33")
v1.anrop("POST", "/api/felinjektion", kropp={"gis_i_b": True})
sc, f3 = v3.anrop("GET", "/api/felinjektion")
kolla(sc == 200 and f3 and f3["aktiv"] is False and not any(f3["lagen"].values()), "en ny tredje besökare ser ingen felinjektion medan besökare 1 har läget på")
for runda in (1, 2, 3):
    ut = {}
    start = threading.Barrier(2)

    def lev(namn, b):
        start.wait()
        ut[namn] = jobb(b, "transfer-b")[1]
    tr = [threading.Thread(target=lev, args=("v1", v1)), threading.Thread(target=lev, args=("v2", v2))]
    [t.start() for t in tr]; [t.join() for t in tr]
    j1, j2 = ut.get("v1") or {}, ut.get("v2") or {}
    kolla(j1.get("utfall") == "avvisad", f"runda {runda}: besökare 1 (läget på) får sin leverans avvisad (jobb {j1.get('id')}, utfall {j1.get('utfall')})")
    kolla(j2.get("status") == "klar" and not j2.get("utfall"), f"runda {runda}: besökare 2 får sin leverans levererad, aldrig avvisad (jobb {j2.get('id')}, utfall {j2.get('utfall')})")
sc, f1d = v1.anrop("GET", "/api/felinjektion")
kolla(f1d and f1d["lagen"]["gis_i_b"] is True, "besökare 1 har kvar sitt läge efter leveranserna (det är hennes tills hon nollställer)")
v1.anrop("POST", "/api/felinjektion/reset", kropp={})
sc, j = jobb(v1, "transfer-b")
kolla(j and j["status"] == "klar" and not j.get("utfall"), "efter nollställning levereras besökare 1:s B")
print("FEL: %d" % fel if fel else "OK: alla prov gröna")
sys.exit(1 if fel else 0)
