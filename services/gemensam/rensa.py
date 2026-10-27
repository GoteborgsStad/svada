"""Rensning av portar och interna värdnamn ur text som visas för besökare.

Används av den externa varianten (DEMO_VARIANT=extern) i kontrollrummet och i
skördarna, så att en publik besökare aldrig ser en port, ett containernamn eller
host.docker.internal: varken i felmeddelanden, loggar, API-svar eller sidor.

Rensningen rör inte tidsstämplar (2026-10-06T17:19:12Z), UUID:er, id:n med
kolon (urn:ngsi-ld:…) eller publika domäner med punkt. Anroparen avgör om den
ska köras (variantflaggan); funktionerna här rensar alltid.
"""
import os
import re
import uuid

# "port 1234", "porten 1234"
_PORT_ORD = re.compile(r"(?i)\bport(?:en)?\s+\d{2,5}")
# "port=5000" (requests/urllib3: HTTPConnectionPool(host='ckan', port=5000))
_PORT_LIKA = re.compile(r"(?i)\bport=\d{2,5}")
# Porten i en URL-kodad DID: did:web:identity-hub-stad%3A29197
_KODAD_DID = re.compile(r"%3A\d{2,5}\b", re.I)
# IPv4-adress med port: 172.18.0.5:19194
_IP_PORT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}\b")
# Värdnamn:port (värdnamnet slutar på bokstav; tidsstämplar slutar på siffra)
_VARD_PORT = re.compile(r"(?<=[A-Za-z\]]):\d{2,5}\b")
# host='ckan', (urllib3)
_URLLIB_VARD = re.compile(r"""host=(['"])[^'"]*\1,?\s*""", re.I)
# Failed to resolve 'ckan' (urllib3)
_NAMNUPPSLAG = re.compile(r"(?i)\b(resolve) '[^']*'")
# http://host.docker.internal, http://ckan, http://harvester-se (containernamn
# utan punkt). Publika domäner har punkter och rörs inte.
_INTERN_URL = re.compile(
    r"https?://(?:host\.docker\.internal|[A-Za-z0-9-]+)(?=[/:\s\"'\\]|$)")
# host.docker.internal utan schema
_INTERN_VARD = re.compile(r"\bhost\.docker\.internal\b")
# "[Errno 101] Network is unreachable": operativsystemets råa feltext säger besökaren ingenting
_ERRNO = re.compile(r"\[Errno \d+\]\s*[A-Za-z' ]+")


# did:web:identity-hub-stad -> did:web:stad.example (containernamnet är ett internt värdnamn)
_DID_NAV = re.compile(r"did:web:identity-hub-([a-z]+)")
# Containernamn som visas i sidor: byts mot språkoberoende, neutrala namn
_CONTAINERNAMN = (
    (re.compile(r"\bidentity-hub-([a-z]+)\b"), r"identity-\1"),
    (re.compile(r"\bfcf-sim\b"), "fcf-simulator"),
    (re.compile(r"\borion-stad\b"), "city-platform"),
    (re.compile(r"\bstad-gateway\b"), "city-gateway"),
    (re.compile(r"\bedc-consumer\b"), "city-connector"),
    (re.compile(r"\bedc-provider\b"), "dhi-connector"),
    (re.compile(r"\bingest-service\b"), "city-intake"),
)


def neutrala_did(text):
    """Byter det interna värdnamnet i en did:web mot ett neutralt (för besökare i den externa varianten)."""
    if text is None:
        return text
    return _DID_NAV.sub(r"did:web:\1.example", str(text))


# Delar av en sida som inte får döpas om: skriptblock (identifierare som koden jämför mot, till exempel
# h.kalla === 'ingest-service') och attributet data-komponent (nyckeln skriptet matchar mot statussvaret).
_SKYDDAT = re.compile(r'<script\b.*?</script>|data-komponent="[^"]*"', re.S)


def utan_containernamn(text):
    """Byter containernamn (fcf-sim, orion-stad, stad-gateway, edc-consumer, edc-provider, ingest-service,
    identity-hub-*) mot neutrala namn i en sida. DID:er neutraliseras först. Skriptblock och data-komponent lämnas orörda
    (det besökaren läser av namnen visas via skriptets egen namnmappning)."""
    if text is None:
        return text
    text = str(text)

    def byt(del_):
        del_ = neutrala_did(del_)
        for monster, ersattning in _CONTAINERNAMN:
            del_ = monster.sub(ersattning, del_)
        return del_

    ut, pos = [], 0
    for m in _SKYDDAT.finditer(text):
        ut.append(byt(text[pos:m.start()]))
        ut.append(m.group(0))
        pos = m.end()
    ut.append(byt(text[pos:]))
    return "".join(ut)


def _publika_baser():
    """De publika ingångarnas adresser MED port (lokalt t.ex. http://svada-demo.localhost:38080). Porten hör till adressen:
    besökaren når demon bara genom den, så den får inte rensas bort (rättning efter gränssnittstestet 2026-10-17: länkarna
    och avtalsadresserna saknade porten och gick inte att öppna). På servern är porten tom och inget skyddas."""
    baser = []
    for nyckel in ("PUBLIK_URL_KONTROLLRUM", "PUBLIK_URL_BRUNNAR", "PUBLIK_URL_TIDSSERIE", "PUBLIK_URL_CIP"):
        v = os.environ.get(nyckel, "").rstrip("/")
        if re.search(r"//[^/:]+:\d{2,5}$", v):
            baser.append(v)
    return sorted(set(baser), key=len, reverse=True)


def utan_portar(text):
    """Tar bort portnummer: 'värd:1234', 'port 1234', 'port=1234', '%3A1234'. De publika ingångarnas egna adresser rörs inte."""
    if text is None:
        return text
    text = str(text)
    baser = _publika_baser()
    if baser:
        # Skydda de publika adresserna med platshållare under rensningen och sätt tillbaka dem efteråt (del a2, A2-07):
        # * platshållaren är slumpad per anrop, så att indata som råkar innehålla den inte förvandlas till en publik adress;
        # * en bas skyddas bara när den slutar där en URL-del slutar (/ ? # citattecken blanksteg eller textslut), inte när
        #   den är prefix till något annat (…:380801) eller följs av userinfo (…:38080@intern:19193).
        nyckel = uuid.uuid4().hex
        monster = re.compile("(%s)(?=[/?#\"'\\s<>),\\]]|$)" % "|".join(re.escape(b) for b in baser))
        sparade = []

        def spara(m):
            sparade.append(m.group(1))
            return "{%s_%d}" % (nyckel, len(sparade) - 1)       # inget kolon: ":10}" efter en hexsiffra a–f lästes som en port
        text = monster.sub(spara, text)
        text = _rensa_portar(text)
        return re.sub(r"\{%s_(\d+)\}" % nyckel, lambda m: sparade[int(m.group(1))], text)
    return _rensa_portar(text)


def _rensa_portar(text):
    text = _PORT_ORD.sub("porten", text)
    text = _PORT_LIKA.sub("", text)
    text = _KODAD_DID.sub("", text)
    text = _IP_PORT.sub("", text)
    return _VARD_PORT.sub("", text)


def utan_intern_adress(text):
    """Som utan_portar, men tar också bort interna värdnamn ur adresser och
    ur urllib3-feltexter. 'når inte http://host.docker.internal:39193/x: …'
    blir 'når inte /x: …'."""
    if text is None:
        return text
    text = utan_portar(text)
    text = _URLLIB_VARD.sub("", text)
    text = _NAMNUPPSLAG.sub(r"\1", text)
    text = _INTERN_URL.sub("", text)
    text = _ERRNO.sub("(anslutningsfel / connection error)", text)
    return _INTERN_VARD.sub("", text)
