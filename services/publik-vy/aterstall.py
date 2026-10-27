"""Nästa nattliga återställning av den publika demon, för nedräkningen på sidan.

Klockslaget kommer ur DEMO_ATERSTALL_KL (till exempel "04:00", i serverns tidszon TZ). Är det tomt (lokalt på en Mac finns ingen
nattlig återställning) visas ingen nedräkning. Servern anger både nästa tidpunkt och sin egen nuvarande tid, så att räknaren går
rätt även om besökarens klocka är fel. Funktionen är ren (tar tiden som parameter) och testas i tests/aterstall_enhet.py.
Samma beräkning finns som en kopia i services/publik-vy/main.py (den tjänsten bygger i en egen Docker-kontext).
"""
import datetime as dt
import re

try:                                    # zoneinfo finns från Python 3.9
    from zoneinfo import ZoneInfo
except ImportError:                     # pragma: no cover
    ZoneInfo = None

# Hur lång en återställning brukar ta (starta-demo.sh plus kontrollerna), för "pågår"-läget i sidan.
VARAKTIGHET_MIN = 10


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


def som_svar(kl, tz="UTC", nu=None):
    """JSON-svaret för /api/aterstallning, eller None när ingen nedräkning ska visas."""
    nu = nu or dt.datetime.now(dt.timezone.utc)
    nasta = nasta_aterstallning(kl, tz, nu)
    if nasta is None:
        return None
    return {"nastaUtc": nasta.strftime("%Y-%m-%dT%H:%M:%SZ"), "nuUtc": nu.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "klockslag": re.sub(r"\s", "", str(kl)).rjust(5, "0"), "tz": tz, "varaktighetMin": VARAKTIGHET_MIN}
