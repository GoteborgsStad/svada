"""Nästa nattliga återställning av den publika demon, för nedräkningen på sidan.

Klockslaget kommer ur DEMO_ATERSTALL_KL (till exempel "04:00", i serverns tidszon TZ). Är det tomt (lokalt på en Mac finns ingen
nattlig återställning) visas ingen nedräkning. Servern anger både nästa tidpunkt och sin egen nuvarande tid, så att räknaren går
rätt även om besökarens klocka är fel. Funktionen är ren (tar tiden som parameter) och testas i tests/aterstall_enhet.py.
Samma beräkning finns som en kopia i services/publik-vy/aterstall.py (den tjänsten bygger i en egen Docker-kontext).

Planerade händelser (en uppdatering mitt på dagen): en liten JSON-fil, VARSEL_FIL, skriven av driftskriptet varsla.sh, innehåller bara
tid och typ ("uppdatering" eller "nollstallning"); texterna är fasta i sidan, så ingen kan visa fri text för besökarna. Filen läses vid
varje anrop (cache i fem sekunder). Den tidigaste händelsen av nattens och den planerade styr nedräkningen. En ogiltig fil ger inget
varsel, och en fil vars händelse och avbrott är över ignoreras, så ett glömt varsel försvinner av sig självt.
"""
import datetime as dt
import json
import re
import time

try:                                    # zoneinfo finns från Python 3.9
    from zoneinfo import ZoneInfo
except ImportError:                     # pragma: no cover
    ZoneInfo = None

# Hur lång en återställning brukar ta (starta-demo.sh plus kontrollerna), för "pågår"-läget i sidan.
VARAKTIGHET_MIN = 10
# Planerad händelse: hur länge sidan kan vara otillgänglig, per typ (minuter). Efter det ignoreras filen (sidan hämtar annars om svaret hela tiden).
VARAKTIGHET_TYP = {"nollstallning": VARAKTIGHET_MIN, "uppdatering": 3}
SPARR_NYA_JOBB_S = 120              # de sista två minuterna före en planerad händelse startas inga nya jobb
_CACHE = {"fil": None, "t": None, "varde": None}      # t = tidpunkt för senaste läsning (monotonic), None = ej läst


def nasta_aterstallning(kl, tz="UTC", nu=None):
    """Nästa tidpunkt (UTC) då klockslaget `kl` ("HH:MM", lokal tid i `tz`) inträffar, eller None om kl är tomt eller ogiltigt."""
    if not kl:
        return None
    m = re.fullmatch(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*", str(kl))
    if not m or ZoneInfo is None:
        return None
    try:
        zon = ZoneInfo(tz or "UTC")
    except Exception:                   # okänd tidszon: räkna i UTC hellre än att tappa nedräkningen
        zon = dt.timezone.utc
    nu = nu or dt.datetime.now(dt.timezone.utc)
    lokal = nu.astimezone(zon)
    mal = lokal.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if mal <= lokal:
        mal = (lokal + dt.timedelta(days=1)).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    return mal.astimezone(dt.timezone.utc)


def _lasa_varsel(fil):
    """(tid i UTC, typ) ur varselfilen, eller None om den saknas eller är ogiltig. Ingen tidsprövning här."""
    try:
        with open(fil, encoding="utf-8") as f:
            d = json.load(f)
        typ = d.get("typ")
        tid = dt.datetime.fromisoformat(str(d.get("tid")))
        if typ not in VARAKTIGHET_TYP or tid.tzinfo is None:        # en tid utan zon är tvetydig: hellre inget varsel
            return None
        return tid.astimezone(dt.timezone.utc), typ
    except Exception:
        return None


def planerad_handelse(fil, nu=None):
    """Den planerade händelsen som fortfarande gäller (tid i UTC, typ), eller None. Läser filen högst var femte sekund."""
    if not fil:
        return None
    nu = nu or dt.datetime.now(dt.timezone.utc)
    if _CACHE["fil"] != fil or _CACHE["t"] is None or time.monotonic() - _CACHE["t"] > 5:
        _CACHE.update(fil=fil, t=time.monotonic(), varde=_lasa_varsel(fil))
    v = _CACHE["varde"]
    if v is None:
        return None
    tid, typ = v
    if nu > tid + dt.timedelta(minutes=VARAKTIGHET_TYP[typ]):
        return None
    return tid, typ


def sparr_nya_jobb(fil, nu=None):
    """Sant de sista två minuterna före en planerad händelse och medan den pågår: då ska inga nya jobb startas."""
    try:
        nu = nu or dt.datetime.now(dt.timezone.utc)
        h = planerad_handelse(fil, nu)
        if h is None:
            return False
        tid, typ = h
        return tid - dt.timedelta(seconds=SPARR_NYA_JOBB_S) <= nu <= tid + dt.timedelta(minutes=VARAKTIGHET_TYP[typ])
    except Exception:
        return False


def som_svar(kl, tz="UTC", nu=None, varselfil=None):
    """JSON-svaret för /api/aterstallning, eller None när ingen nedräkning ska visas. Den tidigaste av nattens och den planerade händelsen styr."""
    nu = nu or dt.datetime.now(dt.timezone.utc)
    nasta = nasta_aterstallning(kl, tz, nu)
    planerad = planerad_handelse(varselfil, nu)
    if nasta is None and planerad is None:
        return None
    svar = None
    if nasta is not None:
        svar = {"nastaUtc": nasta.strftime("%Y-%m-%dT%H:%M:%SZ"), "nuUtc": nu.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "klockslag": re.sub(r"\s", "", str(kl)).rjust(5, "0"), "tz": tz, "varaktighetMin": VARAKTIGHET_MIN, "typ": "nollstallning"}
    if planerad is not None and (nasta is None or planerad[0] <= nasta):
        tid, typ = planerad
        try:
            zon = ZoneInfo(tz or "UTC") if ZoneInfo is not None else dt.timezone.utc
        except Exception:                   # okänd tidszon: räkna i UTC (som nasta_aterstallning) hellre än att tappa varslet
            zon = dt.timezone.utc
        svar = {"nastaUtc": tid.strftime("%Y-%m-%dT%H:%M:%SZ"), "nuUtc": nu.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "klockslag": tid.astimezone(zon).strftime("%H:%M"), "tz": tz, "varaktighetMin": VARAKTIGHET_TYP[typ], "typ": typ}
    return svar
