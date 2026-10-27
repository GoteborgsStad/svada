"""Användningsstatistik för demon (enkel räkning av dagssummor, inga personuppgifter).

Tre delar, alla utan personuppgifter, cookies eller tredje part:

  1. Loggräkningen: läser Caddys JSON-åtkomstlogg (kapade IP-adresser, inga hemligheter), den aktuella filen och de roterade
     (access-<tid>-size.log.gz), och räknar per dag (svensk tid) och värdnamn. Definitioner:
       sidvisning  GET med status 200 och svar av typen text/html på kontrollrummet eller brunnar (kontrollrummet pollar
                   /api/*; de räknas aldrig som besök)
       unik        kapad IP-adress + webbläsare samma dag. Ett minimum: många datorer med samma webbläsare bakom en gemensam adress (NAT) räknas som en (olika webbläsare ger olika besökare).
       robot       User-Agent med robotmönster (bot, crawl, curl, headless ...); ingår aldrig i besök eller avvisade
       avvisad     en besökare (kapad adress + webbläsare, ingen robot) som fick 401 men aldrig en sida under dygnet: öppnade
                   länken men kom inte förbi lösenordet. Första 401:an hos den som sedan loggar in räknas inte.
       API-träff   lyckad GET mot tidsserie, och varje anrop mot cip
       fel         5xx per värdnamn
       begränsad   429 (för många anrop) per värdnamn; spärrarnas nekanden är inga fel och redovisas skilt (409 räknas inte alls)
       kampanj     värdet på ?k=... på en sidvisning (högst KAMPANJ_MAX olika per dag och värd, resten blir "(övriga)")
  2. Historiken: rålogg roteras bort efter några dygn, så de dagliga SUMMORNA sparas för sig (data/dagligt.json) och
     bara siffror ligger kvar. En dag som loggen bara täcker delvis (den äldsta) skriver aldrig över en fullständigare rad.
     En fil som inte går att tolka flyttas åt sidan i stället för att skrivas över.
  3. Händelseräknaren: sidan rapporterar vitlistade händelser (steg öppnat, flik, åtgärd ...) och här räknas ett
     tal per dag och händelse upp (data/handelser.json). Ingen identifierare, ingen IP, ingen fritext.

Egna adresser kan uteslutas med miljövariabeln STATISTIK_UTESLUT (kapade adresser, CIDR, komma- eller blankseparerade).
Katalogen (STATISTIK_KATALOG, standard /statistik) har logg/ (läses) och data/ (skrivs).
"""
import datetime as dt
import glob
import gzip
import ipaddress
import json
import os
import re
import tempfile
import threading
import time
import zlib
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
ROBOT = re.compile(r"bot|crawl|spider|slurp|curl|wget|python|httpie|headless|uptime|monitor|check_http|go-http|libwww|scrapy|preview",
                   re.I)
FALT = ("sidvisningar", "unika", "avvisade", "api_traffar", "robotar", "fel", "begransade")
KAMPANJ_MAX = 20            # olika kampanjvärden per dag och värd; ett ?k= i en länk får aldrig fylla lagret
VARDAR = ("kontrollrum", "brunnar", "tidsserie", "cip")
FLIKAR = ("kedjan", "folj", "audit", "suveranitet", "felinjektion", "jobb", "om", "ordlista")


def vardroll(host):
    """kontrollrum | brunnar | tidsserie | cip | annat, ur värdnamnet utan port."""
    h = (host or "").split(":")[0].lower()
    for namn in ("brunnar", "tidsserie", "cip"):
        if h.startswith(namn + "."):
            return namn
    return "kontrollrum" if h else "annat"


def ar_robot(ua):
    return bool(ROBOT.search(ua or "")) or not ua


def _forsta(rubriker, namn):
    for k, v in (rubriker or {}).items():
        if k.lower() == namn.lower() and v:
            return v[0]
    return ""


def _oppna(fil):
    return gzip.open(fil, "rt", encoding="utf-8", errors="replace") if fil.endswith(".gz") else open(fil, encoding="utf-8", errors="replace")


def logg_filer(kat):
    """Roterade filer (äldst först) och sist den aktuella. Caddy döper en roterad fil access-<tid>-size.log.gz (gzippad som standard).
    Finns både X.log och X.log.gz (mitt under komprimeringen) räknas bara den komprimerade, annars blir allt dubbelräknat."""
    alla = sorted(f for f in glob.glob(os.path.join(kat, "logg", "access-*.log*")) if not os.path.isdir(f))
    roterade = [f for f in alla if not (not f.endswith(".gz") and f + ".gz" in alla)]
    aktuell = os.path.join(kat, "logg", "access.log")
    return roterade + ([aktuell] if os.path.exists(aktuell) else [])


def lasa_poster(sokvagar):
    """Ger en dict per giltig logg-rad ur filerna (globmönster eller sökvägar; .gz läses). Trasiga rader och filer som inte går
    att läsa hoppas över (en delvis skriven sista rad är normal)."""
    for sokvag in sokvagar:
        for fil in sorted(glob.glob(sokvag)):
            if os.path.isdir(fil) or fil.endswith(".gitkeep"):
                continue
            try:
                with _oppna(fil) as f:
                    for rad in f:
                        try:
                            post = json.loads(rad)
                        except ValueError:
                            continue
                        if isinstance(post, dict) and "request" in post and "status" in post:
                            yield post
            except (OSError, EOFError, zlib.error):
                continue


class Rakning:
    """Räkning av en eller flera filer; kan slås ihop (de roterade filerna är oföränderliga och cachas var för sig)."""

    def __init__(self):
        self.rakn = defaultdict(Counter)
        self.unika = defaultdict(set)
        self.kampanj = defaultdict(Counter)
        self.avvisade = defaultdict(set)      # dag -> besökare som fick 401
        self.inne = defaultdict(set)          # dag -> besökare som fick en sida (alla värdnamn delar kakan)
        self.aldsta = None

    def lagg_till(self, annan):
        for k, c in annan.rakn.items():
            self.rakn[k].update(c)
        for k, v in annan.unika.items():
            self.unika[k] |= v
        for k, c in annan.kampanj.items():
            self.kampanj[k].update(c)
        for k, v in annan.avvisade.items():
            self.avvisade[k] |= v
        for k, v in annan.inne.items():
            self.inne[k] |= v
        if annan.aldsta and (self.aldsta is None or annan.aldsta < self.aldsta):
            self.aldsta = annan.aldsta


def raknaa_poster(poster, uteslutna=()):
    r = Rakning()
    for p in poster:
        req = p["request"]
        # Testläge: besök med kakan svada-test (loggfältet "test") och själva ?test=1-anropet som sätter den räknas inte alls.
        if p.get("test") == "1" or re.search(r"[?&]test=1(?:&|$)", req.get("uri", "")):
            continue
        try:
            ip = ipaddress.ip_address(req.get("client_ip") or req.get("remote_ip") or "")
        except ValueError:
            ip = None
        if ip is not None and any(ip in n for n in uteslutna):
            continue
        dag = dt.datetime.fromtimestamp(float(p.get("ts", 0)), TZ).date().isoformat()
        r.aldsta = dag if r.aldsta is None or dag < r.aldsta else r.aldsta
        roll = vardroll(req.get("host"))
        ua = _forsta(req.get("headers"), "User-Agent")
        status = int(p["status"])
        metod = req.get("method", "")
        typ = _forsta(p.get("resp_headers"), "Content-Type").lower()
        k = (dag, roll)
        c = r.rakn[k]
        c["anrop"] += 1
        robot = ar_robot(ua)
        besokare = (str(ip), ua)
        if status >= 500:
            c["fel"] += 1
        elif status == 429:
            c["begransade"] += 1
        if roll in ("kontrollrum", "brunnar"):
            if robot:
                c["robot"] += 1
            elif status == 401:
                r.avvisade[dag].add(besokare)
            elif metod == "GET" and status == 200 and typ.startswith("text/html"):
                c["sidvisningar"] += 1
                r.unika[k].add(besokare)
                r.inne[dag].add(besokare)
                m = re.search(r"[?&]k=([A-Za-z0-9_-]{1,40})(?:&|$)", req.get("uri", ""))
                if m:
                    namn = m.group(1)
                    r.kampanj[k][namn if namn in r.kampanj[k] or len(r.kampanj[k]) < KAMPANJ_MAX else "(övriga)"] += 1
        elif roll == "tidsserie":
            if metod == "GET" and status == 200:
                c["api_traffar"] += 1
        elif roll == "cip":
            c["api_traffar"] += 1
    return r


_CACHE = {}          # (sökväg, storlek, ändrad, uteslutna) -> Rakning; bara roterade (oföränderliga) filer


def raknaa(poster, uteslutna=()):
    """Bakåtkompatibel: ({(dag, värd): Counter}, {…: set(unika)}, {…: Counter(kampanj)}, äldsta dag) ur en ström av poster."""
    r = raknaa_poster(poster, uteslutna)
    _lagg_avvisade(r)
    return r.rakn, r.unika, r.kampanj, r.aldsta


def _lagg_avvisade(r):
    """Avvisade = besökare som fick 401 men aldrig en sida samma dygn (läggs på kontrollrummets rad)."""
    for dag, besokare in r.avvisade.items():
        n = len(besokare - r.inne.get(dag, set()))
        if n:
            r.rakn[(dag, "kontrollrum")]["avvisade"] = n


def raknaa_katalog(kat, uteslutna=()):
    """Räknar hela loggkatalogen: roterade filer cachas, den aktuella läses om varje gång."""
    nyckel_utesl = ",".join(sorted(str(n) for n in uteslutna))
    tot = Rakning()
    for fil in logg_filer(kat):
        rotad = os.path.basename(fil) != "access.log"
        try:
            st = os.stat(fil)
        except OSError:
            continue
        ck = (fil, st.st_size, st.st_mtime_ns, nyckel_utesl)
        if rotad and ck in _CACHE:
            tot.lagg_till(_CACHE[ck])
            continue
        r = raknaa_poster(lasa_poster([fil]), uteslutna)
        if rotad:
            for gammal in [k for k in _CACHE if k[0] == fil]:
                del _CACHE[gammal]
            _CACHE[ck] = r
        tot.lagg_till(r)
    for k, c in tot.kampanj.items():       # tak även efter sammanslagning av flera filer
        if len(c) > KAMPANJ_MAX:
            storst = dict(c.most_common(KAMPANJ_MAX))
            rest = sum(n for kamp, n in c.items() if kamp not in storst)
            tot.kampanj[k] = Counter(storst)
            tot.kampanj[k]["(övriga)"] += rest
    _lagg_avvisade(tot)
    return tot


def dagsrader(rakn, unika, kampanj):
    """{dag: {värd: {sidvisningar, unika, avvisade, api_traffar, robotar, fel, begransade, kampanjer{}}}} ur en räkning."""
    ut = defaultdict(dict)
    for (dag, roll) in rakn:
        c = rakn[(dag, roll)]
        ut[dag][roll] = {"sidvisningar": c["sidvisningar"], "unika": len(unika.get((dag, roll), ())),
                         "avvisade": c["avvisade"], "api_traffar": c["api_traffar"], "robotar": c["robot"],
                         "fel": c["fel"], "begransade": c["begransade"], "kampanjer": dict(kampanj.get((dag, roll), {}))}
    return dict(ut)


def sla_ihop(historik, nya, aldsta_dag):
    """Lägger loggens dagar i historiken. Fullständiga dagar skriver över; den äldsta dagen (loggen kan ha rotats mitt på
    dagen) tar per fält det största av gammalt och nytt, så att en fullständigare rad aldrig ersätts av en tunnare."""
    ut = {d: {v: dict(r) for v, r in vard.items()} for d, vard in historik.items()}
    for dag, vard in nya.items():
        for roll, rad in vard.items():
            gammal = ut.get(dag, {}).get(roll)
            if gammal is None or dag != aldsta_dag:
                ut.setdefault(dag, {})[roll] = rad
                continue
            ny = dict(rad)
            for f in FALT:
                ny[f] = max(int(gammal.get(f, 0)), int(rad.get(f, 0)))
            kamp = {k: max(int((gammal.get("kampanjer") or {}).get(k, 0)), int((rad.get("kampanjer") or {}).get(k, 0)))
                    for k in set(gammal.get("kampanjer") or {}) | set(rad.get("kampanjer") or {})}
            if len(kamp) > KAMPANJ_MAX + 1:      # ett tak även här: en gammal fil kan ha fler nycklar än nu tillåts
                storst = dict(Counter(kamp).most_common(KAMPANJ_MAX))
                storst["(övriga)"] = storst.get("(övriga)", 0) + sum(n for k, n in kamp.items() if k not in storst)
                kamp = storst
            ny["kampanjer"] = kamp
            ut[dag][roll] = ny
    return ut


def _las_json(sokvag, standard):
    """Innehållet, eller `standard` om filen saknas, inte går att tolka eller inte går att läsa."""
    return _las_json_status(sokvag, standard)[0]


def _las_json_status(sokvag, standard):
    """(innehåll, status): ok | saknas | trasig (finns men går inte att tolka) | oläsbar (rättigheter eller annat fel, filen är
    kanske hel). En oläsbar fil får aldrig flyttas åt sidan eller skrivas över."""
    try:
        with open(sokvag, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return standard, "saknas"
    except OSError:
        return standard, "oläsbar"
    except ValueError:
        return standard, "trasig"
    return (data, "ok") if isinstance(data, type(standard)) else (standard, "trasig")


def _skriv_json(sokvag, data):
    """Atomisk skrivning: en avbruten skrivning lämnar aldrig en halv fil."""
    os.makedirs(os.path.dirname(sokvag), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(sokvag), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
        os.chmod(tmp, 0o644)        # bara siffror: läsbar för den som kör rapporten som vanlig användare
        os.replace(tmp, sokvag)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def katalog():
    return os.environ.get("STATISTIK_KATALOG", "/statistik")


def uteslutna_fran_miljon():
    """Kapade adresser (CIDR) ur STATISTIK_UTESLUT, komma- eller blankseparerade. Ogiltiga poster hoppas över."""
    ut = []
    for post in re.split(r"[,\s]+", os.environ.get("STATISTIK_UTESLUT", "")):
        if post:
            try:
                ut.append(ipaddress.ip_network(post, strict=False))
            except ValueError:
                pass
    return ut


def uppdatera_historik(kat=None, uteslutna=None):
    """Räknar om loggen (aktuell och roterade filer), slår ihop med sparade dagar, skriver data/dagligt.json och returnerar
    historiken. Egna adresser ur STATISTIK_UTESLUT (och `uteslutna`) räknas aldrig, så sidan och rapporten ger samma tal."""
    kat = kat or katalog()
    utesl = list(uteslutna or []) + uteslutna_fran_miljon()
    r = raknaa_katalog(kat, utesl)
    sokvag = os.path.join(kat, "data", "dagligt.json")
    sparad, status = _las_json_status(sokvag, {})
    if status == "trasig" and os.path.getsize(sokvag) > 2:
        try:                         # en fil som inte gick att tolka skrivs aldrig över: spara den åt sidan först
            os.replace(sokvag, sokvag + ".trasig-" + dt.datetime.now(TZ).strftime("%Y%m%d%H%M%S"))
        except OSError:
            pass
    ny = sla_ihop(sparad, dagsrader(r.rakn, r.unika, r.kampanj), r.aldsta)
    if ny != sparad and status != "oläsbar":      # en oläsbar historik skrivs aldrig över: visa det vi har utan att spara
        try:
            _skriv_json(sokvag, ny)
        except OSError:
            pass                    # skrivskyddad katalog: visa det vi har, men misslyckas inte sidan
    return ny


# ------------------------------------------------------------------ händelseräknaren
_STATISK_HANDELSER = re.compile(
    r"^(steg_[1-6]|flik_(%s)|sprak_(sv|en)|karta_osm|analys_(a|b)|js_fel|atgard_nekad)$" % "|".join(FLIKAR))
_ATGARD = re.compile(r"^atgard_([a-z][a-z0-9-]{0,30})$")
MAX_HANDELSER_PER_DAG = 200000          # skydd mot ett skript som fyller lagret; långt över verklig användning


def giltig_handelse(namn, atgarder=()):
    """Vitlistan. Allt som inte stämmer avvisas: ingen fritext och inget id når lagret."""
    if not isinstance(namn, str) or len(namn) > 60:
        return False
    if _STATISK_HANDELSER.match(namn):
        return True
    m = _ATGARD.match(namn)
    return bool(m and m.group(1) in set(atgarder))


class Handelser:
    """Ett tal per dag och händelse, sparat i data/handelser.json. Skrivs högst var SKRIV_VAR_S sekund (och vid läsning)."""
    SKRIV_VAR_S = 5.0

    def __init__(self, kat=None):
        self.sokvag = os.path.join(kat or katalog(), "data", "handelser.json")
        self.las = threading.Lock()
        self.data, status = _las_json_status(self.sokvag, {})
        self.skrivskyddad = status == "oläsbar"        # en oläsbar fil skrivs aldrig över
        if status == "trasig" and os.path.getsize(self.sokvag) > 2:
            try:                # en fil som inte gick att tolka skrivs aldrig över
                os.replace(self.sokvag, self.sokvag + ".trasig-" + dt.datetime.now(TZ).strftime("%Y%m%d%H%M%S"))
            except OSError:
                pass
        self.smutsig = False
        self.senast = 0.0

    def rakna(self, namn, nu=None):
        dag = dt.datetime.fromtimestamp(nu if nu is not None else time.time(), TZ).date().isoformat()
        with self.las:
            d = self.data.setdefault(dag, {})
            if sum(d.values()) >= MAX_HANDELSER_PER_DAG:
                return False
            d[namn] = int(d.get(namn, 0)) + 1
            self.smutsig = True
            self._skriv_om_dags(False)
        return True

    def _skriv_om_dags(self, tvinga):
        if self.skrivskyddad or not self.smutsig or (not tvinga and time.monotonic() - self.senast < self.SKRIV_VAR_S):
            return
        try:
            _skriv_json(self.sokvag, self.data)
            self.smutsig = False
        except OSError:
            pass
        self.senast = time.monotonic()

    def spola(self):
        with self.las:
            self._skriv_om_dags(True)

    def alla(self):
        """{dag: {händelse: antal}} (kopia)."""
        with self.las:
            self._skriv_om_dags(True)
            return {d: dict(v) for d, v in self.data.items()}


def sammanstall(historik, handelser, idag=None, dagar=30):
    """Det sidan visar: de senaste dagarna, summor och händelser. Bara siffror."""
    idag = idag or dt.datetime.now(TZ).date()
    alla_dagar = sorted(set(historik) | set(handelser))
    fran = (idag - dt.timedelta(days=dagar - 1)).isoformat()
    rad = []
    d = idag - dt.timedelta(days=dagar - 1)
    while d <= idag:
        iso = d.isoformat()
        k = (historik.get(iso) or {}).get("kontrollrum", {})
        b = (historik.get(iso) or {}).get("brunnar", {})
        rad.append({"dag": iso, "unika": int(k.get("unika", 0)), "sidvisningar": int(k.get("sidvisningar", 0)),
                    "brunnar_sidvisningar": int(b.get("sidvisningar", 0)), "avvisade": int(k.get("avvisade", 0)) + int(b.get("avvisade", 0)),
                    # serverfel och 429 per dag (alla värdar): visar WHEN det strulade, inte bara hur mycket sedan start
                    "fel": sum(int((historik.get(iso) or {}).get(v, {}).get("fel", 0)) for v in VARDAR),
                    "begransade": sum(int((historik.get(iso) or {}).get(v, {}).get("begransade", 0)) for v in VARDAR)})
        d += dt.timedelta(days=1)
    summa = {v: Counter() for v in VARDAR}
    kampanj = Counter()
    for dag, vard in historik.items():
        for v in VARDAR:
            for f in FALT:
                summa[v][f] += int((vard.get(v) or {}).get(f, 0))
        for v in ("kontrollrum", "brunnar"):
            for kamp, n in ((vard.get(v) or {}).get("kampanjer") or {}).items():
                kampanj[kamp] += int(n)
    ev = Counter()
    for dag, h in handelser.items():
        for namn, n in h.items():
            ev[namn] += int(n)
    return {"dagar": rad, "fran": fran, "forsta_dag": alla_dagar[0] if alla_dagar else None,
            "summa": {v: dict(c) for v, c in summa.items()}, "kampanjer": dict(kampanj.most_common(10)),
            "handelser": dict(ev), "uppdaterad": dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")}
