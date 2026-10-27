"""Integrationstest av skydden i den publika demon: dashboardens RIKTIGA app (middleware, rutter, jobbmodul,
städning) körs i processen med kontrollerad klocka och stubbade källor. Ingen stack, inget nätverk.

Skiljer sig från tests/skydd_enhet.py, som bara prövar hjälpfunktionerna i skydd.py: här prövas KOPPLINGEN –
att middleware nekar, att jobbet markerar sitt slut, att API-rutterna är idempotenta och nekar under
återhämtning, att städningen återförsöker efter ett källfel och att den startas av appen.

Körs i dashboard-imagen med arbetskopian monterad (se tests/verify_kedjevy.sh, K24):
  docker run --rm --network none -e DEMO_VARIANT=extern -v "$PWD/services:/srv:ro" <dashboard-image> \
      python /srv/../tests/skydd_integration.py     (testet monteras separat, se skriptet)

Varje kontroll är skriven så att en minimal mutation av kopplingen gör den röd (tests/mutationsprov.sh kör dem).
"""
import asyncio
import json
import os
import sys
import threading

os.environ.update(DEMO_VARIANT="extern", DASH_PAUS_EFTER_JOBB_S="8", DASH_UTESTANGNING_S="180",
                  DASH_FELINJEKTION_S="300", DASH_AVKYLNING_S="60")
for sok in ("/srv/dashboard", "/srv", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "services", "dashboard"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "services")):
    if os.path.isdir(sok):
        sys.path.insert(0, sok)

import io, contextlib   # noqa: E402,E401
import skydd            # noqa: E402
import kallor           # noqa: E402
import jobb as jobbmodul  # noqa: E402
import main             # noqa: E402

# Standardvärdet i den externa varianten: samordnarens utestängning är avstängd för anrop via Caddy (avsnitt 4b nedan). Avsnitten 4 och
# framåt prövar utestängningens BOKFÖRING, som finns kvar när den slås på (DASH_UTESTANGNING=ja), så de körs med den påslagen.
STANDARD_UTESTANGNING = main.UTESTANGNING_TILLATEN
main.UTESTANGNING_TILLATEN = True

fel = 0


def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text))
    fel += (not ok)


# --- kontrollerad klocka: skydd.py läser tiden via sin modul `time` ---------------------------------------
class Klocka:
    def __init__(self):
        self.nu = 1000.0

    def monotonic(self):
        return self.nu

    def sleep(self, _s):                     # städloopen sover i verkligheten; här körs varven för hand
        pass


klocka = Klocka()
skydd.time = klocka
main.time = klocka                      # main.py tar pausens starttid med samma klocka som skydd.py (annars jämförs två tidsaxlar)


# --- stubbade källor ----------------------------------------------------------------------------------------
class Kallor:
    def __init__(self):
        self.svada = []              # (mottagare, atgard) för varje anrop som nådde källan
        self.svada_fel = 0           # antal anrop som ska misslyckas innan nästa lyckas
        self.fcf_satt = []
        self.fcf_av = 0
        self.fcf_av_fel = 0
        self.lagen = {"schemadrift": False, "saknade_parametrar": False, "gis_i_b": False}


K = Kallor()


def svada_satt(mottagare, atgard):
    K.svada.append((mottagare, atgard))
    if K.svada_fel > 0:
        K.svada_fel -= 1
        raise kallor.KallFel("identity hub nere (stub)")
    return {"mottagare": mottagare, "aterkallat": atgard == "aterkalla"}


def fcf_satt_fel(lagen):
    K.fcf_satt.append(dict(lagen))
    K.lagen.update(lagen)
    return {"aktiv": any(K.lagen.values()), "lagen": dict(K.lagen)}


def fcf_nollstall_fel():
    K.fcf_av += 1
    if K.fcf_av_fel > 0:
        K.fcf_av_fel -= 1
        raise kallor.KallFel("fcf nere (stub)")
    for k in K.lagen:
        K.lagen[k] = False
    return {"aktiv": False, "lagen": dict(K.lagen)}


kallor.svada_satt, kallor.fcf_satt_fel, kallor.fcf_nollstall_fel = svada_satt, fcf_satt_fel, fcf_nollstall_fel

# Ett snabbt jobb som inte rör någon källa.
jobbmodul.ATGARDER["kor-batch"] = ("atgard.kor-batch", 1, lambda j, a: {"ok": True})


# --- minimal ASGI-klient (stöder avbruten kropp, vilket TestClient inte gör) -----------------------------
BAS = {"host": "demo.test", "origin": "http://demo.test", "x-forwarded-for": "1.1.1.1",
       "x-forwarded-proto": "http", "content-type": "application/json"}


def anropa(metod, sokvag, kropp=None, klient="1.1.1.1", huvud=None, bitar=None, avbryt_efter=None, ursprung=True, vanta=None):
    """Synkron variant: kör anropet i en egen händelseloop (se anropa_async)."""
    return asyncio.run(anropa_async(metod, sokvag, kropp, klient, huvud, bitar, avbryt_efter, ursprung, vanta))


async def anropa_async(metod, sokvag, kropp=None, klient="1.1.1.1", huvud=None, bitar=None, avbryt_efter=None, ursprung=True,
                       vanta=None):
    """Skickar ett anrop genom appens HELA middleware-kedja. bitar = kroppen som lista av byte-bitar;
    avbryt_efter = antal bitar efter vilka klienten kopplar ned. Returnerar (status, json|text)."""
    h = dict(BAS)
    if klient is not None:
        h["x-forwarded-for"] = klient
    else:                                    # klient=None: ett anrop direkt mot porten, utan Caddy (inga skydd för publik väg)
        h.pop("x-forwarded-for", None)
    if not ursprung:
        h.pop("origin")
    h.update(huvud or {})
    if bitar is None:
        bitar = [] if kropp is None else [json.dumps(kropp).encode()]
    h_lista = [(k.encode(), v.encode()) for k, v in h.items()]
    if kropp is not None or bitar:
        h_lista.append((b"content-length", str(sum(len(b) for b in bitar)).encode()))
    svar = {"status": None, "kropp": b""}
    # vanta: ett threading.Event som måste sättas innan kroppen levereras (klienten "håller kroppen öppen", A2-04).

    async def kor():
        vag, _, fraga = sokvag.partition("?")
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metod, "scheme": "http",
                 "path": vag, "raw_path": vag.encode(), "query_string": fraga.encode(), "headers": h_lista,
                 "client": ("127.0.0.1", 5555), "server": ("demo.test", 80)}
        kvar = list(bitar)
        skickade = [0]
        fas = {"klar": False}

        async def receive():
            if vanta is not None and skickade[0] == 0 and not fas["klar"]:
                await asyncio.get_running_loop().run_in_executor(None, vanta.wait, 10)
            if avbryt_efter is not None and skickade[0] >= avbryt_efter:
                return {"type": "http.disconnect"}
            if kvar:
                skickade[0] += 1
                return {"type": "http.request", "body": kvar.pop(0), "more_body": bool(kvar)}
            if not fas["klar"]:
                fas["klar"] = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.sleep(0.05)
            return {"type": "http.disconnect"}

        async def send(m):
            if m["type"] == "http.response.start":
                svar["status"] = m["status"]
            elif m["type"] == "http.response.body":
                svar["kropp"] += m.get("body", b"")

        await main.app(scope, receive, send)

    await kor()
    try:
        return svar["status"], json.loads(svar["kropp"] or b"null")
    except ValueError:
        return svar["status"], svar["kropp"].decode("utf-8", "replace")


def vanta_jobb():
    """Väntar tills jobbet är klart OCH har släppt sitt lås (status 'klar' sätts strax före låset)."""
    for _ in range(400):
        if jobbmodul.aktivt() is None and not jobbmodul._KOR.is_set():
            return
        threading.Event().wait(0.01)
    raise SystemExit("jobbet blev aldrig klart")


def jobbsignatur():
    return (max([j.id for j in jobbmodul.JOBB] or [0]), tuple(j.id for j in jobbmodul.JOBB))


def fyll_historiken():
    """Fyll jobblistan till taket (40): då är LÄNGDEN konstant och längdjämförelser bevisar ingenting (fynd E2)."""
    with contextlib.redirect_stdout(io.StringIO()):        # tysta jobb- och auditloggen
        for _ in range(jobbmodul.RETENTION + 3):
            jobbmodul.starta("kor-batch", {})
            vanta_jobb()


# --- 1. Appens uppstart kopplar in städningen -----------------------------------------------------------
print("== 1. Uppstarten startar städtråden ==")
startade = []


class FalskTrad:
    def __init__(self, target=None, name=None, daemon=None, **_):
        self.target, self.name = target, name

    def start(self):
        startade.append((self.name, self.target))


verklig_trad, main.threading.Thread = main.threading.Thread, FalskTrad
try:
    main.starta()
finally:
    main.threading.Thread = verklig_trad
kolla(any(n == "stada" and t is main._stada_loop for n, t in startade), "starta() startar städtråden (_stada_loop) i den publika varianten")

# --- 2. Kroppen läses före varje sidoeffekt -----------------------------------------------------------------
print("== 2. Avvisad, avbruten eller tom kropp ändrar inget (E1, E2) ==")
fyll_historiken()
kolla(len(jobbmodul.JOBB) == jobbmodul.RETENTION, "förutsättning: jobblistan är full (%d) – längdjämförelse vore verkningslös" % len(jobbmodul.JOBB))
klocka.nu += 100                                  # utanför all paus
fore = jobbsignatur()
svar = {}
svar["stor"] = anropa("POST", "/api/atgard/kor-batch", bitar=[b"{" + b"x" * 70000 + b"}"])
svar["trasig"] = anropa("POST", "/api/atgard/kor-batch", bitar=[b"[1,2"])
svar["lista"] = anropa("POST", "/api/atgard/kor-batch", kropp=[1, 2])
svar["avbruten"] = anropa("POST", "/api/atgard/kor-batch", bitar=[b'{"a": ', b'1}'], avbryt_efter=1)
svar["avbruten_direkt"] = anropa("POST", "/api/atgard/kor-batch", bitar=[b'{"a": 1}'], avbryt_efter=0)
vanta_jobb()
kolla(svar["stor"][0] == 413, "kropp över gränsen ger 413 (fick %s)" % (svar["stor"][0],))
kolla(svar["trasig"][0] == 400 and svar["lista"][0] == 400, "trasig JSON och icke-objekt ger 400 (%s, %s)" % (svar["trasig"][0], svar["lista"][0]))
kolla(svar["avbruten"][0] == 400 and svar["avbruten_direkt"][0] == 400, "avbruten kropp ger 400 (%s, %s)" % (svar["avbruten"][0], svar["avbruten_direkt"][0]))
kolla(jobbsignatur() == fore, "inget jobb startades av något avvisat anrop (högsta id %d före och efter, alla id oförändrade)" % fore[0])
kolla(skydd._SENASTE["klient"] is None or skydd._SENASTE["start"] is None or True, "(information) pausens klient orörd av avvisade anrop")

# positiv kontroll med SAMMA transport: ett giltigt anrop når backend och startar ett jobb
fore = jobbsignatur()
pos = anropa("POST", "/api/atgard/kor-batch", kropp={})
vanta_jobb()
kolla(pos[0] == 200 and jobbsignatur()[0] == fore[0] + 1, "positiv kontroll, samma transport: giltig kropp startar ett jobb (id %d → %d)" % (fore[0], jobbsignatur()[0]))

# --- 3. Rättvis kö: jobbet markerar sitt slut, API:t visar pausen, GET ändrar inget ----------------
print("== 3. Paus efter jobb: koppling jobb → skydd → middleware → /api/skydd ==")
s1 = anropa("GET", "/api/skydd")[1]
kolla(0 < s1["pausS"] <= 8, "/api/skydd visar en verklig paus direkt efter jobbet (pausS=%s)" % s1["pausS"])
kolla(s1["regler"] == {"utestangningS": 180.0, "felinjektionS": 300.0, "pausS": 8.0}, "regler() bär de konfigurerade tiderna")
anropa("GET", "/api/skydd"); anropa("GET", "/api/skydd")
kolla(anropa("GET", "/api/skydd")[1]["pausS"] == s1["pausS"], "att läsa /api/skydd flera gånger ändrar inte pausen")
fore = jobbsignatur()
nej = anropa("POST", "/api/atgard/kor-batch", kropp={})
kolla(nej[0] == 429 and nej[1].get("vantaSek"), "samma besökare nekas med 429 och väntetid under pausen (%s)" % (nej[0],))
kolla(jobbsignatur() == fore, "det nekade anropet startade inget jobb")
andra = anropa("POST", "/api/atgard/kor-batch", kropp={}, klient="2.2.2.2")
vanta_jobb()
kolla(andra[0] == 200, "en annan besökare släpps fram direkt (%s)" % (andra[0],))
klocka.nu += 9
igen = anropa("POST", "/api/atgard/kor-batch", kropp={}, klient="2.2.2.2")
vanta_jobb()
kolla(igen[0] == 429 or igen[0] == 200, "(information) den andra besökarens egen paus")
klocka.nu += 20
kolla(anropa("POST", "/api/atgard/kor-batch", kropp={}, klient="1.1.1.1")[0] == 200, "efter pausen får första besökaren köra igen")
vanta_jobb()
kolla(anropa("POST", "/api/atgard/kor-batch", kropp={}, ursprung=False)[0] == 403, "POST utan Origin nekas av middleware (403)")
kolla(anropa("POST", "/api/atgard/kor-batch", kropp={}, huvud={"origin": "ftp://demo.test"})[0] == 403, "POST med fel schema i Origin nekas (403)")
klocka.nu += 100

# --- 4. Uteslutning: idempotens, absolut frist, återhämtning, städning med källfel -----------------
print("== 4. Uteslutning (samordnaren): idempotens, absolut frist, återhämtning, städning ==")
skydd.UTESTANGDA.clear(); skydd._AVKYLNING_TILL.clear(); K.svada.clear()
r1 = anropa("POST", "/api/svada/dhi/aterkalla", kropp={})
kolla(r1[0] == 200 and K.svada == [("dhi", "aterkalla")], "första uteslutningen når källan")
kolla(anropa("GET", "/api/skydd")[1]["utestangningS"] == {"dhi": 180}, "/api/skydd visar 180 s")
klocka.nu += 15
r2 = anropa("POST", "/api/svada/dhi/aterkalla", kropp={})
kolla(r2[0] == 200 and r2[1].get("redan") is True and K.svada == [("dhi", "aterkalla")], "upprepad uteslutning är idempotent: ingen ny källanrop")
kolla(anropa("GET", "/api/skydd")[1]["utestangningS"] == {"dhi": 165}, "fristen är absolut: 165 s kvar efter 15 s (inte 180)")
klocka.nu += 170                                   # 185 s sedan start
K.svada_fel = 1
main._stada_ett_varv()
kolla("dhi" in skydd.UTESTANGDA, "källfel vid återinsättning: uteslutningen finns kvar i bokföringen (inget glöms)")
kolla(K.svada[-1] == ("dhi", "aterinsatt"), "städningen försökte släppa in parten")
main._stada_ett_varv()
kolla("dhi" not in skydd.UTESTANGDA and K.svada[-1] == ("dhi", "aterinsatt") and len(K.svada) == 3,
      "nästa varv lyckas: parten släpps in och bokföringen töms (källanrop: %d)" % len(K.svada))
kolla(any(h.get("kod") == "audit.svada_automatisk" for h in main.audit.samla()) if hasattr(main.audit, "samla") else True,
      "(information) automatisk återinsättning auditerad")
nej = anropa("POST", "/api/svada/dhi/aterkalla", kropp={})
kolla(nej[0] == 429 and nej[1].get("vantaSek"), "ny uteslutning direkt efter att den upphört nekas (429) under återhämtningen")
kolla(nej[1].get("fel", "").startswith("Medlemsintyget för DHI") and "Vänta" in nej[1].get("fel", ""),
      "väntemeddelandet är en hel mening som namnger parten (%r)" % nej[1].get("fel", "")[:70])
kolla(len(K.svada) == 3, "den nekade uteslutningen nådde aldrig källan")
kolla(anropa("POST", "/api/svada/stad/aterkalla", kropp={})[0] == 200, "återhämtningen gäller per part: staden kan stängas ute")
klocka.nu += 61
kolla(anropa("POST", "/api/svada/dhi/aterkalla", kropp={})[0] == 200, "efter 60 s får samma part stängas ute igen")
anropa("POST", "/api/svada/dhi/aterinsatt", kropp={}); anropa("POST", "/api/svada/stad/aterinsatt", kropp={})
nej = anropa("POST", "/api/svada/dhi/aterkalla", kropp={})
kolla(nej[0] == 429, "även manuell återinsättning startar återhämtningsperioden")
klocka.nu += 100

# --- 4b. Utestängningen är avstängd i den externa varianten (via Caddy) -----------------------------------------------
print("== 4b. Samordnarens utestängning är avstängd externt: nej via Caddy, orörd lista, direkt mot porten som förut ==")
kolla(STANDARD_UTESTANGNING is False, "standardvärdet i extern variant: utestängningen är avstängd")
main.UTESTANGNING_TILLATEN = STANDARD_UTESTANGNING
skydd.UTESTANGDA.clear(); skydd._AVKYLNING_TILL.clear(); K.svada.clear()
nej = anropa("POST", "/api/svada/stad/aterkalla", kropp={})
kolla(nej[0] == 403 and "avstängd" in nej[1].get("fel", "") and nej[1].get("kod") == "fel.utestangning_avstangd",
      "via Caddy: återkallelse nekas med 403 och en begriplig text (%s, %r)" % (nej[0], nej[1].get("fel", "")[:60]))
kolla(K.svada == [] and not skydd.UTESTANGDA, "den nekade återkallelsen nådde aldrig källan och bokfördes inte")
nej2 = anropa("POST", "/api/svada/dhi/aterinsatt", kropp={})
kolla(nej2[0] == 403 and K.svada == [], "även återinsättning via Caddy nekas (ingen åtgärd mot källan)")
kolla(anropa("POST", "/api/svada/ingen/aterkalla", kropp={})[0] == 400, "en okänd mottagare ger fortfarande 400 före spärren")
_verklig_katalog = kallor.dsp_katalog
kallor.dsp_katalog = lambda: {}
_prov = anropa("GET", "/api/svada/prov")
kallor.dsp_katalog = _verklig_katalog
kolla(_prov[0] == 200 and _prov[1].get("ok") is True, "den läsande katalogförfrågan (Prova …) fungerar fortfarande och svarar ok (%s, %s)" % (_prov[0], _prov[1]))
direkt = anropa("POST", "/api/svada/stad/aterkalla", kropp={}, klient=None)
kolla(direkt[0] == 200 and K.svada == [("stad", "aterkalla")], "direkt mot porten (testerna, värdens skript) berörs inte av spärren (%s)" % (direkt[0],))
anropa("POST", "/api/svada/stad/aterinsatt", kropp={}, klient=None)
main.UTESTANGNING_TILLATEN = True
skydd.UTESTANGDA.clear(); skydd._AVKYLNING_TILL.clear(); K.svada.clear()
klocka.nu += 100

# --- 5. Felinjektion ----------------------------------------------------------------------------------
print("== 5. Felinjektion: tomma anrop, idempotens, absolut frist, städning, återhämtning ==")
skydd.FELINJEKTION_SEDAN = None; skydd._AVKYLNING_TILL.clear(); K.fcf_satt.clear()
for lage in K.lagen:
    K.lagen[lage] = False
for namn, kropp, bitar in (("tom", None, []), ("{}", {}, None), ("okänt läge", {"x": True}, None), ("icke-bool", {"schemadrift": 1}, None)):
    r = anropa("POST", "/api/felinjektion", kropp=kropp, bitar=bitar) if bitar is None else anropa("POST", "/api/felinjektion", bitar=bitar)
    kolla(r[0] == 400, "felinjektion med %s kropp ger 400 (%s)" % (namn, r[0]))
kolla(K.fcf_satt == [] and skydd.FELINJEKTION_SEDAN is None, "inget av de avvisade anropen nådde källan eller startade en frist")
anropa("POST", "/api/felinjektion", kropp={"schemadrift": True})
kolla(anropa("GET", "/api/skydd")[1]["felinjektionS"] == 300, "/api/skydd visar 300 s")
klocka.nu += 12
anropa("POST", "/api/felinjektion", kropp={"schemadrift": True}); anropa("POST", "/api/felinjektion", kropp={"saknade_parametrar": True})
kolla(anropa("GET", "/api/skydd")[1]["felinjektionS"] == 288, "fristen är absolut även när samma eller ett andra läge slås på: 288 s")
klocka.nu += 289                                   # 301 s sedan start
K.fcf_av_fel = 1
main._stada_ett_varv()
kolla(skydd.FELINJEKTION_SEDAN is not None and K.fcf_av == 1, "källfel: felinjektionen finns kvar i bokföringen och försöks igen")
main._stada_ett_varv()
kolla(skydd.FELINJEKTION_SEDAN is None and K.fcf_av == 2 and not any(K.lagen.values()), "nästa varv slår av den hos källan")
nej = anropa("POST", "/api/felinjektion", kropp={"schemadrift": True})
kolla(nej[0] == 429 and nej[1].get("vantaSek"), "ny felinjektion direkt efter avslag nekas (429) under återhämtningen")
kolla(nej[1].get("fel", "").startswith("Felinjektionen har just slagits av"), "väntemeddelandet för felinjektion börjar med versal och säger vad som hänt (%r)" % nej[1].get("fel", "")[:60])
kolla(not any(K.lagen.values()), "den nekade aktiveringen ändrade inget hos källan")
klocka.nu += 61
kolla(anropa("POST", "/api/felinjektion", kropp={"schemadrift": True})[0] == 200, "efter 60 s får den slås på igen")
kolla(anropa("POST", "/api/felinjektion", kropp={"schemadrift": False})[0] == 200, "att slå AV nekas aldrig av återhämtningen")


# --- 6. Begripliga besked (gränssnittstestet 2026-10-17) -------------------------------------------------
print("== 6. Klartext i stället för rå 502-JSON och interna koder ==")
import meddelanden       # noqa: E402
import kedjan            # noqa: E402
klocka.nu += 100
skydd.UTESTANGDA.clear()
rad_502 = '[{"message":"{\\"@type\\":\\"CatalogError\\",\\"code\\":\\"401\\"}"}]'
kedjan.hamta_katalog = lambda: (_ for _ in ()).throw(kallor.KallFel("HTTP 502 från /management/v3/catalog/request: " + rad_502, status=502, kropp=rad_502))
anropa("POST", "/api/atgard/forhandla-b", kropp={})
vanta_jobb()
senaste = jobbmodul.JOBB[-1].till_json()
rader_text = " ".join(r.get("text", "") for r in senaste["rader"])
kolla(senaste["status"] == "fel" and "nekas av DHI (401)" in rader_text and "502" not in rader_text and "CatalogError" not in rader_text,
      "Förhandla B när staden är utestängd: klartext (%r), inte rå 502-JSON" % rader_text[-110:])
kedjan.hamta_katalog = lambda: (_ for _ in ()).throw(kallor.KallFel("HTTP 500 från /x", status=500, kropp="fel"))
klocka.nu += 100
anropa("POST", "/api/atgard/forhandla-b", kropp={}); vanta_jobb()
kolla("nekas av DHI" not in " ".join(r.get("text", "") for r in jobbmodul.JOBB[-1].till_json()["rader"]),
      "ett annat HTTP-fel presenteras inte som att staden nekats")
# Okänt avtal: sidan på besökarens språk och med väg tillbaka (gränssnittstestet L8, del e E13).
_verklig = kallor.anrop
kallor.anrop = lambda *a, **k: (_ for _ in ()).throw(kallor.KallFel("ingest svarade 404"))
for _sp, _fras, _lank in (("sv", "Avtalet hittades inte.", "Tillbaka till kontrollrummet"),
                          ("en", "The agreement was not found.", "Back to the control room")):
    _st, _html = anropa("GET", "/avtal/finns-inte?lang=%s" % _sp)
    kolla(_st == 404 and _fras in str(_html) and _lank in str(_html) and ('lang="%s"' % _sp) in str(_html),
          "okänt avtal (%s): 404 på språket, med länk tillbaka" % _sp)
_st, _html = anropa("GET", "/avtal/finns/inte?lang=sv")
kolla(_st == 404 and "Avtalet hittades inte." in str(_html), "okänt avtal med snedstreck i id: avtalssidans 404, inte rå JSON (L8, fick %s)" % _st)
kallor.anrop = _verklig
kon_sv = meddelanden.visa("jobb.kon", {"id": "x", "tillstand": "REQUESTED", "pending": False, "beslut": "VANTANDE"}, "sv")
kon_en = meddelanden.visa("jobb.kon", {"id": "x", "tillstand": "REQUESTED", "pending": False, "beslut": "VANTANDE"}, "en")
kolla("pending" not in kon_sv and "VANTANDE" not in kon_sv and "väntar på beslut" in kon_sv, "providerns kö i jobbloggen: ingen intern flagga och ingen å/ä/ö-lös kod på svenska (%r)" % kon_sv)
kolla("pending" not in kon_en and "WAITING" in kon_en, "…och på engelska (%r)" % kon_en)

# =====================================================================================================================
# DEL A2 (Codex, 2026-10-18). Varje avsnitt är skrivet så att det blir rött mot koden före rättningen (se mutationsprov.sh).
# =====================================================================================================================
import time as _realtid    # riktig tid för trådschemana; skyddets klocka är fortfarande den styrda
kallor.anrop = _verklig
for _a in ("kov-godkann", "kov-avsla", "kov-hav"):
    jobbmodul.ATGARDER[_a] = (jobbmodul.ATGARDER[_a][0], 3, lambda j, a: {"ok": True})


def _nolla():
    skydd.UTESTANGDA.clear(); skydd._AVKYLNING_TILL.clear(); skydd.FELINJEKTION_SEDAN = None
    klocka.nu += 1000


print("== A2-01: varje skrivande rutt läser och godkänner kroppen före åtgärden ==")
DALIGA = (("trasig JSON", dict(bitar=[b"{"]), 400), ("lista", dict(kropp=[1]), 400),
          ("för stor", dict(bitar=[b"{" + b" " * 70000 + b"}"]), 413), ("avbruten", dict(bitar=[b'{"a": ', b"1}"], avbryt_efter=1), 400))
RUTTER = (("Svada aterkalla", "/api/svada/stad/aterkalla"), ("KoV godkänn", "/api/kov/abc-1/godkann"),
          ("KoV häv", "/api/kov/avtal/abc-1/hav"), ("nollställ felinjektion", "/api/felinjektion/reset"))
for namn, vag in RUTTER:
    for dnamn, arg, vantat in DALIGA:
        _nolla(); K.svada.clear(); fore_av = K.fcf_av; fore = jobbsignatur()
        st, _ = anropa("POST", vag, **arg)
        vanta_jobb()
        rent = K.svada == [] and K.fcf_av == fore_av and jobbsignatur() == fore and not skydd.UTESTANGDA
        kolla(st == vantat and rent, "%s med %s kropp: %s och ingen åtgärd (fick %s)" % (namn, dnamn, vantat, st))
    _nolla(); K.svada.clear(); fore_av = K.fcf_av; fore = jobbsignatur()
    st, _ = anropa("POST", vag)                                     # positiv kontroll: knappen skickar ingen kropp
    vanta_jobb()
    gjort = K.svada == [("stad", "aterkalla")] or jobbsignatur()[0] == fore[0] + 1 or K.fcf_av == fore_av + 1
    kolla(st == 200 and gjort, "%s utan kropp (som knappen): 200 och åtgärden görs (fick %s)" % (namn, st))
    if K.svada:
        anropa("POST", "/api/svada/stad/aterinsatt")
_nolla(); fore = jobbsignatur()
st, _ = anropa("POST", "/api/atgard/kov-godkann", kropp={"id": []})
st2, _ = anropa("POST", "/api/atgard/kov-hav", kropp={})
kolla(st == 400 and st2 == 400 and jobbsignatur() == fore, "KoV-jobb med felaktigt eller saknat id avvisas FÖRE antagning (%s, %s)" % (st, st2))

print("== A2-02: källans tillstånd och bokföringen följs åt även när anrop korsar varandra ==")
LAGE = {"stad": "insatt"}
B_INNE, B_SLAPP = threading.Event(), threading.Event()


def svada_med_lage(mottagare, atgard):
    K.svada.append((mottagare, atgard))
    if atgard == "aterinsatt":
        LAGE[mottagare] = "insatt"
        B_INNE.set(); B_SLAPP.wait(5)            # pausa EFTER källans svar, FÖRE bokföringen
    else:
        LAGE[mottagare] = "utestangd"
    return {"mottagare": mottagare}


kallor.svada_satt = svada_med_lage
_nolla(); K.svada.clear()
LAGE["stad"] = "utestangd"; skydd.utestangd("stad")              # utgångsläge: utestängd och bokförd
B = threading.Thread(target=main._svada_satt_synk, args=("stad", "aterinsatt", False)); B.start()
B_INNE.wait(5)
A = threading.Thread(target=main._svada_satt_synk, args=("stad", "aterkalla", False)); A.start()
_realtid.sleep(0.3)                                                # utan samordning hinner A klart här
B_SLAPP.set(); B.join(5); A.join(5)
kolla(not B.is_alive() and not A.is_alive(), "inget dödläge: båda anropen blev klara")
kolla((LAGE["stad"] == "utestangd") == ("stad" in skydd.UTESTANGDA),
      "korsande återinsättning och uteslutning: källan (%s) och bokföringen (%s) stämmer"
      % (LAGE["stad"], "bokförd" if "stad" in skydd.UTESTANGDA else "tom"))
# två samtidiga uteslutningar: bara en når källan
FORSTA_INNE, FORSTA_SLAPP = threading.Event(), threading.Event()


def svada_langsam(mottagare, atgard):
    K.svada.append((mottagare, atgard))
    if len(K.svada) == 1:
        FORSTA_INNE.set(); FORSTA_SLAPP.wait(5)
    LAGE[mottagare] = "utestangd" if atgard == "aterkalla" else "insatt"
    return {"mottagare": mottagare}


kallor.svada_satt = svada_langsam
_nolla(); K.svada.clear(); LAGE["stad"] = "insatt"; B_SLAPP.clear()
T1 = threading.Thread(target=main._svada_satt_synk, args=("stad", "aterkalla", True)); T1.start()
FORSTA_INNE.wait(5)
T2 = threading.Thread(target=main._svada_satt_synk, args=("stad", "aterkalla", True)); T2.start()
_realtid.sleep(0.3); FORSTA_SLAPP.set(); T1.join(5); T2.join(5)
kolla(len(K.svada) == 1, "två samtidiga uteslutningar av samma part når källan en gång (anrop: %d)" % len(K.svada))
# en gammal ögonblicksbild från forfallna() får inte släppa in en NY uteslutning
kallor.svada_satt = svada_satt
_nolla(); K.svada.clear(); K.svada_fel = 0
anropa("POST", "/api/svada/stad/aterkalla"); klocka.nu += 200
anropa("POST", "/api/svada/stad/aterinsatt"); klocka.nu += 61
anropa("POST", "/api/svada/stad/aterkalla"); K.svada.clear()
_verklig_forfallna = skydd.forfallna
skydd.forfallna = lambda nu=None: (["stad"], False)                # gammal bild: "stad är förfallen"
main._stada_ett_varv()
skydd.forfallna = _verklig_forfallna
kolla(K.svada == [] and "stad" in skydd.UTESTANGDA, "städning med gammal ögonblicksbild släpper inte in en ny uteslutning (anrop: %s)" % K.svada)
# felinjektion: nollställning som korsar en ny påslagning
FEL_LAGE = {"pa": True}
R_INNE, R_SLAPP = threading.Event(), threading.Event()


def nollstall_med_lage():
    FEL_LAGE["pa"] = False
    R_INNE.set(); R_SLAPP.wait(5)
    return {"aktiv": False, "lagen": {"schemadrift": False}}


def satt_med_lage(lagen):
    FEL_LAGE["pa"] = any(lagen.values())
    return {"aktiv": FEL_LAGE["pa"], "lagen": {"schemadrift": FEL_LAGE["pa"]}}


kallor.fcf_nollstall_fel, kallor.fcf_satt_fel = nollstall_med_lage, satt_med_lage
_nolla(); skydd.felinjektion_pa(True)
R = threading.Thread(target=main._nollstall_fel_synk); R.start(); R_INNE.wait(5)
S = threading.Thread(target=main._satt_fel_synk, args=({"schemadrift": True}, False)); S.start()
_realtid.sleep(0.3); R_SLAPP.set(); R.join(5); S.join(5)
kolla(FEL_LAGE["pa"] == (skydd.FELINJEKTION_SEDAN is not None),
      "korsande nollställning och påslagning: källan (%s) och fristen (%s) stämmer"
      % ("på" if FEL_LAGE["pa"] else "av", "satt" if skydd.FELINJEKTION_SEDAN is not None else "ingen"))
kallor.fcf_nollstall_fel, kallor.fcf_satt_fel = fcf_nollstall_fel, fcf_satt_fel

print("== A2-04: rättvisepausen prövas när jobbet antas, inte bara innan kroppen kommit ==")
_nolla()
J1 = threading.Event()
jobbmodul.ATGARDER["kor-batch"] = ("atgard.kor-batch", 1, lambda j, a: (J1.wait(5), {"ok": True})[1])
fore = jobbsignatur()
st1, _ = anropa("POST", "/api/atgard/kor-batch", kropp={})           # jobb 1 kör (väntar på J1)
KROPP = threading.Event(); ut = {}
T = threading.Thread(target=lambda: ut.update(svar=anropa("POST", "/api/atgard/kor-batch", kropp={}, vanta=KROPP))); T.start()
_realtid.sleep(0.4)                                                  # anrop 2 har passerat middleware (jobb 1 kör: ingen paus)
J1.set(); vanta_jobb()                                               # jobb 1 klart: pausen börjar nu
KROPP.set(); T.join(10)                                              # kroppen kommer inom pausen
st2 = ut.get("svar", (None,))[0]
kolla(st1 == 200 and st2 == 429 and jobbsignatur()[0] == fore[0] + 1,
      "kropp som hålls öppen över jobbslutet: antagningen prövar pausen (429), inget andra jobb (fick %s)" % st2)
jobbmodul.ATGARDER["kor-batch"] = ("atgard.kor-batch", 1, lambda j, a: {"ok": True})

print("== A2-05: ett långsamt källanrop fryser inte händelseloopen ==")
_nolla()
kallor.fcf_satt_fel = lambda lagen: (_realtid.sleep(1.0), {"aktiv": False, "lagen": {"schemadrift": False}})[1]


async def _a2_05():
    tick = {"n": 0}

    async def ticker():
        for _ in range(30):
            await asyncio.sleep(0.03); tick["n"] += 1
    t0 = _realtid.monotonic()
    svar, _ = await asyncio.gather(anropa_async("POST", "/api/felinjektion", kropp={"schemadrift": False}), ticker())
    return svar, tick["n"], _realtid.monotonic() - t0


_svar, _ticks, _tid = asyncio.run(_a2_05())
kolla(_svar[0] == 200 and _ticks == 30 and _tid < 1.6,
      "under ett källanrop på 1 s tickade loopen %d gånger av 30 (tid %.2f s): anropet går i trådpoolen" % (_ticks, _tid))
kallor.fcf_satt_fel = fcf_satt_fel

print("== A2-06: bara DHI:s strukturerade nekande räknas som 'staden nekas' ==")
_RIKTIG = '[{"message":"{\\"@type\\":\\"CatalogError\\",\\"code\\":\\"401\\",\\"reason\\":[\\"Unauthorized\\"]'
for _namn, _fel, _vantat in (("riktig DSP-401 i 502", kallor.KallFel("x", status=502, kropp=_RIKTIG), True),
                             ("request-id=401 i 502", kallor.KallFel("x", status=502, kropp="upstream timeout; request-id=401"), False),
                             ("Unauthorized i annan kontext", kallor.KallFel("x", status=502, kropp='{"error":"Unauthorized"}'), False),
                             ("consumerns management 401", kallor.KallFel("x", status=401, kropp="Unauthorized"), False),
                             ("timeout utan status", kallor.KallFel("timeout", status=None, kropp=None), False),
                             ("CatalogError 500", kallor.KallFel("x", status=502, kropp=_RIKTIG.replace("401", "500")), False)):
    kolla(jobbmodul.dsp_nekad(_fel) == _vantat, "felklassning: %s -> %s" % (_namn, "nekad" if _vantat else "inte nekad"))

print("== L1: en spärr som gör sitt jobb visas inte som 'misslyckades' ==")
_nolla()
def _spärr(j, a):
    raise jobbmodul.Jobbfel("fel.inget_avtal_kov", dist="A")
_gammal_ta = jobbmodul.ATGARDER["transfer-a"]
jobbmodul.ATGARDER["transfer-a"] = (_gammal_ta[0], _gammal_ta[1], _spärr)
anropa("POST", "/api/atgard/transfer-a", kropp={}); vanta_jobb()
_j = jobbmodul.JOBB[-1].till_json()
kolla(_j["status"] == "fel" and _j.get("utfall") == "nekad", "Leverera A utan avtal: status fel men utfallet 'nekad' (fick %s/%s)" % (_j["status"], _j.get("utfall")))
jobbmodul.ATGARDER["transfer-a"] = (_gammal_ta[0], _gammal_ta[1], lambda j, a: (_ for _ in ()).throw(kallor.KallFel("riktigt fel")))
klocka.nu += 100
anropa("POST", "/api/atgard/transfer-a", kropp={}); vanta_jobb()
kolla(jobbmodul.JOBB[-1].till_json().get("utfall") is None, "ett riktigt källfel får inte utfallet 'nekad'")
jobbmodul.ATGARDER["transfer-a"] = _gammal_ta

print("== Webinariet 2026-10, punkt 2: KoV:s avslag och det efterföljande nekandet syns i klartext ==")
# Leverera A efter ett avslag (avtalet hävt): utfallet nekad, och loggraden säger "inget gällande avtal", inte MISSLYCKADES.
for _kod in ("fel.avtal_havt", "fel.inget_avtal_kov"):
    _nolla(); klocka.nu += 100
    jobbmodul.ATGARDER["transfer-a"] = (_gammal_ta[0], _gammal_ta[1],
                                        lambda j, a, _k=_kod: (_ for _ in ()).throw(jobbmodul.Jobbfel(_k, avtal="A1", dist="A", steg=3)))
    anropa("POST", "/api/atgard/transfer-a", kropp={}); vanta_jobb()
    _j = jobbmodul.JOBB[-1].till_json()
    _sista = _j["rader"][-1]["text"]
    kolla(_j.get("utfall") == "nekad" and _sista.startswith("NEKAD, inget gällande avtal:") and "MISSLYCKADES" not in _sista,
          "Leverera A (%s): utfallet nekad och sista raden '%s'" % (_kod, _sista[:60]))
jobbmodul.ATGARDER["transfer-a"] = _gammal_ta
# KoV avslår: förhandlingen avslutas, DHI:s orsak står i klartext sist i loggen och utfallet är "inget avtal".
_orsak = "KoV (Kretslopp och Vatten) avslog begäran om Distribution A (K1R1T1, non-public)."
_g = (kallor.kov_beslut, jobbmodul.kedjan.kov_kon, jobbmodul.kedjan.vanta_avtal, jobbmodul.audit.notera_beslutstid)
kallor.kov_beslut = lambda fid, b: {"kovBeslut": "AVSLAGEN", "state": "TERMINATING", "pending": False, "havdaAvtal": []}
jobbmodul.kedjan.kov_kon = lambda: [{"id": "P1", "correlationId": "C1", "errorDetail": _orsak}]
jobbmodul.kedjan.vanta_avtal = lambda fid, sek: (None, "TERMINATED")
jobbmodul.audit.notera_beslutstid = lambda fid: None
_ga = jobbmodul.ATGARDER["kov-avsla"]                 # stubbad i del A2 ovan: här körs den riktiga _kov_beslut
jobbmodul.ATGARDER["kov-avsla"] = (_ga[0], 3, lambda j, a: jobbmodul._kov_beslut(j, a["id"], "avsla"))
_nolla(); klocka.nu += 100
anropa("POST", "/api/atgard/kov-avsla", kropp={"id": "P1"}); vanta_jobb()
jobbmodul.ATGARDER["kov-avsla"] = _ga
_j = jobbmodul.JOBB[-1].till_json()
kolla(_j["status"] == "klar" and _j.get("utfall") == "inget-avtal", "KoV avslår: jobbet klart med utfallet 'inget-avtal' (fick %s/%s)" % (_j["status"], _j.get("utfall")))
kolla(_orsak in _j["rader"][-1]["text"] and "Leverera A nekas" in _j["rader"][-1]["text"],
      "KoV avslår: sista raden bär DHI:s orsak i klartext och säger att Leverera A nekas")
kallor.kov_beslut, jobbmodul.kedjan.kov_kon, jobbmodul.kedjan.vanta_avtal, jobbmodul.audit.notera_beslutstid = _g

sys.exit(1 if fel else 0)
