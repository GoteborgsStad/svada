"""En egen vy per besökare i den delade, externa demon: besökaren ska uppleva att den är ensam och bara se sina egna saker.

Det här är INGEN full separation: data i stadens plattform (B och A i Orion-LD och Mintaka) är gemensam, och komponenterna (staden, DHI)
är en och samma för alla. Det som skiljs åt är VISNINGEN: jobb, förhandlingar i KoV-rutan, avtal och vilket avtal analysen (steg 5 och 6)
bygger på. Jobben körs fortfarande ett i taget; en annan besökares jobb ger en kö i stället för ett fel (jobb.py).

En besökare identifieras av en slumpad id i en kaka (svada-sess, HttpOnly, SameSite=Lax). Id:t är 128 bitar slump och kopplas inte till
en person, en IP-adress eller något annat; sessionerna ligger bara i minnet (försvinner vid omstart och nollställning), har en tidsgräns
och ett tak. Sessioner gäller bara anrop via Caddy (X-Forwarded-For satt) i den externa varianten och bara när DASH_SESSIONER=ja; anrop
direkt mot dashboardens port (testerna, värdens skript) och den interna varianten berörs inte (`aktuell()` är då None).
"""
import contextvars
import os
import re
import secrets
import threading
import time
from collections import OrderedDict

KAKNAMN = "svada-sess"
KAKA_MAXALDER_S = 86400
TTL_S = float(os.environ.get("DASH_SESSION_TTL_S", "7200"))       # oanvänd session glöms efter två timmar
MAX_SESSIONER = int(os.environ.get("DASH_SESSION_MAX", "300"))    # tak: den äldsta oanvända glöms först
PA = False                                                         # sätts av main.py: DASH_SESSIONER=ja i den externa varianten
_ID = re.compile(r"^[0-9a-f]{32}$")

_AKTUELL = contextvars.ContextVar("svada_session", default=None)
_LAS = threading.Lock()
_SESSIONER = OrderedDict()          # id -> Session, äldst först (senast använd längst bak)


class Session:
    def __init__(self, sid):
        self.id = sid
        self.senast = time.monotonic()
        self.forhandlingar = set()   # stadens förhandlings-id (= DHI:s correlationId) som besökaren själv startat
        self.avtal = set()           # stadens avtals-id som kommit ur besökarens egna förhandlingar
        self.gjort = set()           # åtgärder (batch, katalog, B-förhandling, B-leverans) som besökaren fått klara, för "nästa" (jobb.py)
        self.a_laget = None          # A-kedjan: None, "begart", "godkant" eller "levererat" (jobb.py, nasta_atgard)
        self.fel_lagen = {}          # besökarens eget felinjektionsläge (schemadrift, saknade_parametrar, gis_i_b): slås på i FCF bara medan HENNES leverans körs
        self.a_forut = None          # läget före en ny begäran (godkant/levererat): återställs om begäran avslås utan att något avtal hävs

    def kort(self):
        return self.id[:8]


def aktuell():
    """Sessionen för det här anropet, eller None (sessioner av, direktanrop, eller utanför ett anrop)."""
    return _AKTUELL.get()


def satt(session):
    return _AKTUELL.set(session)


def aterstall(token):
    _AKTUELL.reset(token)


def _rensa_gamla(nu):
    for sid in [s for s, x in _SESSIONER.items() if nu - x.senast > TTL_S]:
        del _SESSIONER[sid]
    while len(_SESSIONER) >= MAX_SESSIONER:
        _SESSIONER.popitem(last=False)


def hamta_eller_skapa(kakvarde):
    """(session, ny). En kaka som inte är en giltig, känd id ger en ny session; den gamla sessionens saker följer inte med."""
    nu = time.monotonic()
    with _LAS:
        if isinstance(kakvarde, str) and _ID.match(kakvarde) and kakvarde in _SESSIONER:
            s = _SESSIONER[kakvarde]
            if nu - s.senast <= TTL_S:
                s.senast = nu
                _SESSIONER.move_to_end(kakvarde)
                return s, False
            del _SESSIONER[kakvarde]
        _rensa_gamla(nu)
        s = Session(secrets.token_hex(16))
        _SESSIONER[s.id] = s
        return s, True


def antal():
    with _LAS:
        return len(_SESSIONER)


def nollstall():
    with _LAS:
        _SESSIONER.clear()
