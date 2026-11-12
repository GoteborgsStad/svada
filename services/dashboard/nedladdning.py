"""KONCEPT: docs/koncept/C7-nedladdning.md

nedladdning.py – ladda ned det som faktiskt passerar varje steg, så att en besökare kan se datat och kontrollera att det är riktigt.

Principer:
  * FAKTISKT, inte inspelat. En fil är det steget just nu har i kedjan (batchen, katalogen, avtalet, leveransen, stadens plattform,
    analysen). Det som bara är ett exempel märks som exempel ("art").
  * Samma åtkomst som sidan. Distribution B är öppen. Distribution A (och allt som innehåller brunns-GIS) kräver ett gällande avtal
    för besökaren, precis som analysen: den här modulen har ingen egen åtkomstlogik utan återanvänder analysens (analys.py).
    Distribution A är inte hemlig i demon (koordinaterna är påhittade) men ska hanteras som icke-publik: filnamnet och rubriken säger det.
  * Kontrollsumma. Varje svar bär SHA-256 av exakt de byte som skickas (X-Content-SHA256). För steg 4 är summan den som ingest-service
    räknade när leveransen togs emot (finns också i auditloggen), så att filen går att jämföra byte för byte med det som gick genom kedjan.
  * Inget internt. Containernamn, portar och liknande tas bort ur filerna i den externa varianten, och en fil som ändå innehåller något
    sådant vägras (stängt som standard).

Filen finns bara i dashboard-tjänsten. Brunnsvyn (services/publik-vy) har sina egna nedladdningar av modellen och de öppna data.
"""

import csv
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

import analys
import audit
import kallor
import sessioner
from gemensam import rensa
from kallor import KallFel

VERSION = os.environ.get("SVADA_VERSION", "okänd")

# Adresser och namn som aldrig ska stå i en fil till en besökare i den externa varianten.
INTERNT = re.compile(
    r"(?:edc-provider|edc-consumer|orion-stad|orion-dhi|stad-gateway|ingest-service|identity-hub|fcf-sim(?!ulator)|mintaka(?=:\d)|timescale-|mongo-|"
    r"host\.docker\.internal|127\.0\.0\.1|(?<![\w.])localhost|\b172\.\d+\.\d+\.\d+|\b192\.168\.\d+\.\d+|\b10\.\d+\.\d+\.\d+)"
    r"(?::\d+)?", re.I)
PORT_I_ADRESS = re.compile(r"%3A\d{4,5}")


class Ej(Exception):
    """Filen kan inte skapas just nu av ett normalt skäl (ingen leverans än, kräver avtal …). Visas för besökaren, är inget fel."""

    def __init__(self, sv, en, status=409, kod="ej-tillganglig"):
        super().__init__(sv)
        self.sv, self.en, self.status, self.kod = sv, en, status, kod

    def text(self, sprak):
        return self.en if sprak == "en" else self.sv


def _json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _platta(rad, prefix=""):
    """En post blir en platt rad: underobjekt får kolumner som a.b, positionen blir lon/lat, listor blir JSON."""
    ut = {}
    for k, v in rad.items():
        namn = prefix + k
        if isinstance(v, dict):
            if v.get("type") == "Point" and isinstance(v.get("coordinates"), list) and len(v["coordinates"]) >= 2:
                ut[namn + ".lon"], ut[namn + ".lat"] = v["coordinates"][0], v["coordinates"][1]
            else:
                ut.update(_platta(v, namn + "."))
        elif isinstance(v, list):
            ut[namn] = json.dumps(v, ensure_ascii=False)
        else:
            ut[namn] = v
    return ut


def _csv(rader):
    plana = [_platta(r) for r in rader]
    kolumner = []
    for r in plana:
        for k in r:
            if k not in kolumner:
                kolumner.append(k)
    ut = io.StringIO()
    skriv = csv.DictWriter(ut, fieldnames=kolumner, lineterminator="\n")
    skriv.writeheader()
    for r in plana:
        skriv.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in kolumner})
    return ut.getvalue().encode("utf-8")


def _rensa_intern(obj, extern):
    """Tar bort portar ur adresser i den externa varianten (samma regel som sidorna använder)."""
    if not extern:
        return obj
    return json.loads(PORT_I_ADRESS.sub("", json.dumps(obj)))


def _egna_avtal(dist=None):
    """Besökarens egna avtal i stadens register (ur stadens avtalsregister). Utan session: alla."""
    reg = kallor.avtalsregister().get("avtal", [])
    s = sessioner.aktuell()
    return [a for a in reg if (dist is None or a.get("distribution") == dist) and (s is None or a.get("id") in s.avtal)]


def _nekad_a(havt):
    return Ej("Distribution A kräver ett gällande avtal. Förhandla A och låt KoV godkänna först" +
              (" (ditt avtal är hävt)." if havt else "."),
              "Distribution A needs a current agreement. Negotiate A and let KoV approve first" +
              (" (your agreement has been revoked)." if havt else "."), status=403, kod="kraver-avtal")


def _kraver_a():
    gallande, havt = analys.senaste_gallande_a_avtal()
    if not gallande:
        raise _nekad_a(havt)
    return gallande


# ---------------------------------------------------------------------------
# Skapare: en per fil. Varje returnerar (bytes, mimetyp, filändelse, art).
# ---------------------------------------------------------------------------
def _matvarden(form):
    """Underlaget modellen räknar på: mätfönstret ur FCF (en riktig mätserie, som dataägaren godkänt att visa). Själva batchen, dataproduktens
    nyttolast, hämtar kontrollrummet aldrig från FCF: den når staden bara genom avtalet och kan laddas ned i steg 4 (Mottagen leverans)."""
    def skapa(sprak, extern):
        svar = kallor.anrop(kallor.url("fcf", "/measurements"), timeout=30)
        punkter = svar.get("window") or []
        if form == "csv":
            if not punkter:
                raise Ej("Inga mätvärden än.", "No measurements yet.")
            return _csv(punkter), "text/csv", "csv", "faktisk"
        return _json(svar), "application/json", "json", "faktisk"
    return skapa


def _katalog(sprak, extern):
    return _json(_rensa_intern(kallor.dsp_katalog(), extern)), "application/ld+json", "jsonld", "faktisk"


def _deltagare(sprak, extern):
    return _json(_rensa_intern(kallor.deltagarregister(), extern)), "application/json", "json", "faktisk"


def _avtal(sprak, extern):
    egna = _egna_avtal()
    if not egna:
        raise Ej("Du har inget avtal än. Förhandla B (eller A) i steg 3 först.", "You have no agreement yet. Negotiate B (or A) in step 3 first.")
    return _json(_rensa_intern({"avtal": egna}, extern)), "application/json", "json", "faktisk"


def _odrl(dist):
    def skapa(sprak, extern):
        import steg as stegmodul               # sent, så att modulerna inte beror på varandra vid import
        villkor = stegmodul.odrl_villkor(sprak, extern=extern)
        return _json(villkor[dist]["json"]), "application/json", "json", "faktisk"
    return skapa


def _hamta_ingest_innehall(avtals_id):
    """Rå hämtning: leveransen under avtalet exakt som den kom (inte omtolkad), med huvudena."""
    adress = kallor.url("ingest", "/leveranser/%s/innehall" % avtals_id)
    try:
        with urllib.request.urlopen(adress, timeout=20) as svar:
            return svar.read(), dict(svar.headers)
    except urllib.error.HTTPError as fel:
        if fel.code == 404:
            return None, {}
        raise KallFel("ingest-service svarade %s" % fel.code) from fel
    except (urllib.error.URLError, OSError) as fel:
        raise KallFel("ingest-service nåddes inte") from fel


def _farskt_gallande(avtals_id):
    """Leverans A lämnas ut bara under ett avtal som är gällande JUST NU enligt färsk status, inte enligt registrets senast sparade
    (granskningen 2026-11-01: listan synkas inte vid läsning). Stängt som standard: kan statusen inte läsas är avtalet inte gällande."""
    try:
        return (kallor.ingest_avtalsstatus(avtals_id) or {}).get("status") == "GALLANDE"
    except Exception:
        return False


def _leverans(dist):
    def skapa(sprak, extern):
        if dist == "A":
            _kraver_a()
        senaste = None
        avtal = _egna_avtal(dist)
        if dist == "A":
            # Bara GÄLLANDE avtal: data som kom under ett hävt avtal lämnas inte ut (regel 8).
            avtal = [a for a in avtal if a.get("status") == "GALLANDE" and _farskt_gallande(a["id"])]
            if not avtal:
                raise _nekad_a(True)
        for a in avtal:
            innehall, huvud = _hamta_ingest_innehall(a["id"])
            if innehall is not None and (senaste is None or huvud.get("X-Received-At", "") > senaste[1].get("X-Received-At", "")):
                senaste = (innehall, huvud)
        if senaste is None:
            raise Ej("Ingen leverans av %s har tagits emot under ett av dina avtal än. Leverera i steg 4 först." % dist,
                     "No delivery of %s has been received under one of your agreements yet. Deliver in step 4 first." % dist)
        # Byte för byte som den kom; summan är den som räknades vid mottagandet.
        return senaste[0], "application/json", "json", "faktisk", senaste[1].get("X-Content-SHA256")
    return skapa


def _schemakontroll(sprak, extern):
    poster = []
    for lev in (kallor.ingest_leveranser().get("deliveries") or []):
        if lev.get("resultat") == "LEVERERAD" and lev.get("schemakontroll") and lev.get("contractAgreementId") in {a["id"] for a in _egna_avtal()}:
            poster.append({"mottagen": lev.get("at"), "distribution": lev.get("distribution"), "batchId": lev.get("batchId"),
                           "kontrollsumma_leverans_sha256": lev.get("sha256"), "bytes": lev.get("bytes"),
                           "schemakontroll": lev["schemakontroll"]})
    if not poster:
        raise Ej("Ingen av dina leveranser har schemakontrollerats än. Leverera i steg 4 först.",
                 "None of your deliveries has been schema-checked yet. Deliver in step 4 first.")
    return _json({"leveranser": poster}), "application/json", "json", "faktisk"


def _skydda_proveniens(poster):
    """Ett avtals-id som inte är besökarens egna ska inte synas (samma regel som analysen)."""
    s = sessioner.aktuell()
    if s is None:
        return poster
    for e in poster:
        prov = e.get("provenance")
        if isinstance(prov, dict) and prov.get("contractAgreementId") not in s.avtal:
            for k in ("contractAgreementId", "contractAgreementUrl", "transferProcessId"):
                prov.pop(k, None)
    return poster


def _cip(dist):
    def skapa(sprak, extern):
        if dist == "A":
            gallande = _kraver_a()
            huvud = analys._nyckel_for_avtal(gallande["id"])
        else:
            huvud = kallor.STAD_GATEWAY_HUVUD
        poster = analys._hamta_typ(huvud, analys.MODELLTYP[dist])
        if not poster:
            raise Ej("Stadens plattform har inga poster för %s än. Leverera i steg 4 först." % dist,
                     "The city's platform has no records for %s yet. Deliver in step 4 first." % dist)
        return _json(_skydda_proveniens(poster)), "application/json", "json", "faktisk"
    return skapa


def _analys(lage, form):
    def skapa(sprak, extern):
        ut = analys.prioritering(lage)
        if ut.get("blockerad"):
            if lage == "a":
                _kraver_a()
            raise Ej("Det finns inget att analysera än. Leverera i steg 4 först.", "There is nothing to analyse yet. Deliver in step 4 first.")
        rader = ut["rader"]
        if form == "json":
            if ut.get("avtal"):
                ut["avtal"] = {k: ut["avtal"].get(k) for k in ("id", "status")}
            return _json(ut), "application/json", "json", "faktisk"
        if form == "csv":
            return _csv([{k: v for k, v in r.items() if k != "avtal"} for r in rader]), "text/csv", "csv", "faktisk"
        sattning = []
        for r in rader:
            pos = r.get("position")
            if not pos:
                continue
            egenskaper = {k: v for k, v in r.items() if k not in ("position", "avtal")}
            sattning.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": pos}, "properties": egenskaper})
        if not sattning:
            raise Ej("Inga positioner att visa.", "There are no positions to show.")
        return (_json({"type": "FeatureCollection", "features": sattning}), "application/geo+json", "geojson", "faktisk")
    return skapa


def _ordlista(sprak, extern):
    import ordlista
    return _json({"version": VERSION, "sprak": sprak, "begrepp": ordlista.js_ord(sprak)}), "application/json", "json", "referens"


def _mim(sprak, extern):
    import mim
    ut = {}
    for nyckel, v in mim.MIM.items():
        sv = sprak != "en"
        ut[nyckel] = {"namn": v[1] if sv else v[2], "vadDenAr": v[3] if sv else v[4], "status": v[6] if sv else v[7], "niva": v[8]}
    return _json({"version": VERSION, "sprak": sprak, "mim": ut,
                  "anmarkning": "Vår egen bedömning, ingen certifiering." if sprak != "en" else "Our own assessment, not a certification."}), \
        "application/json", "json", "referens"


# ---------------------------------------------------------------------------
# Registret: id, steg, rubriker och skapare. krav_a = filen innehåller Distribution A (eller brunns-GIS).
# ---------------------------------------------------------------------------
POSTER = [
    {"id": "matvarden", "steg": 1, "skapa": _matvarden("json"), "sv": ("Mätvärdena modellen räknar på", "JSON"), "en": ("The measurements the model computes on", "JSON"),
     "info": ("Mätfönstret: de senaste mätpunkterna ur den riktiga mätserien och hur fullständigt fönstret är. Batchen själv når staden först genom avtalet (se steg 4).",
              "The measurement window: the latest points from the real measurement series and how complete the window is. The batch itself reaches the city only through the agreement (see step 4).")},
    {"id": "matvarden-csv", "steg": 1, "skapa": _matvarden("csv"), "sv": ("De senaste mätpunkterna", "CSV"), "en": ("The latest measurement points", "CSV"),
     "info": ("Samma mätpunkter som tabell som går att öppna i kalkylprogram.", "The same measurement points as a table that opens in a spreadsheet.")},
    {"id": "katalog", "steg": 2, "skapa": _katalog, "sv": ("Leverantörens katalog", "JSON-LD"), "en": ("The provider's catalogue", "JSON-LD"),
     "info": ("Svaret på katalogförfrågan: produkterna, villkoren och modellen de följer. Leverantören ger svaret nya id:n varje gång, så kontrollsumman blir en annan vid varje hämtning; den gäller just filen du hämtade.",
              "The answer to the catalogue request: the products, the terms and the model they follow. The provider gives the answer new ids every time, so the checksum differs with each download; it applies to the very file you downloaded.")},
    {"id": "deltagare", "steg": 2, "skapa": _deltagare, "sv": ("Deltagarregistret", "JSON"), "en": ("The participant register", "JSON"),
     "info": ("Vilka som är med i datautrymmet och vilka intyg de har. Registret stämplar svaret med tidpunkten, så kontrollsumman blir en annan vid varje hämtning.",
              "Who takes part in the data space and which credentials they hold. The register stamps the answer with the time, so the checksum differs with each download.")},
    {"id": "avtal", "steg": 3, "skapa": _avtal, "sv": ("Dina avtal", "JSON"), "en": ("Your agreements", "JSON"),
     "info": ("Avtalen du själv har ingått, med status och villkor.", "The agreements you have made yourself, with status and terms.")},
    {"id": "odrl-b", "steg": 3, "skapa": _odrl("B"), "sv": ("Villkoren för distribution B (ODRL)", "JSON"), "en": ("The terms of distribution B (ODRL)", "JSON"),
     "info": ("Policyn som gäller för den öppna distributionen.", "The policy that applies to the open distribution.")},
    {"id": "odrl-a", "steg": 3, "skapa": _odrl("A"), "sv": ("Villkoren för distribution A (ODRL)", "JSON"), "en": ("The terms of distribution A (ODRL)", "JSON"),
     "info": ("Policyn med förbud mot att sprida och med KoV-godkännande.", "The policy with the ban on spreading and with KoV approval.")},
    {"id": "leverans-b", "steg": 4, "skapa": _leverans("B"), "sv": ("Mottagen leverans, distribution B", "JSON"), "en": ("Received delivery, distribution B", "JSON"),
     "info": ("Exakt det som kom in, byte för byte. Summan är den som räknades vid mottagandet och finns i auditloggen.",
              "Exactly what arrived, byte for byte. The checksum is the one computed on receipt and is in the audit log.")},
    {"id": "leverans-a", "steg": 4, "skapa": _leverans("A"), "krav_a": True, "sv": ("Mottagen leverans, distribution A", "JSON"), "en": ("Received delivery, distribution A", "JSON"),
     "info": ("Med brunnarnas positioner. Kräver ett gällande avtal om A.", "With the chambers' positions. Needs a current agreement for A.")},
    {"id": "schemakontroll", "steg": 4, "skapa": _schemakontroll, "sv": ("Schemakontrollens resultat", "JSON"), "en": ("The schema check result", "JSON"),
     "info": ("Vad som kontrollerades mot modellens schema och hur många poster som godkändes.", "What was checked against the model's schema and how many records passed.")},
    {"id": "cip-b", "steg": 5, "skapa": _cip("B"), "sv": ("Stadens plattform: distribution B", "JSON"), "en": ("The city's platform: distribution B", "JSON"),
     "info": ("Posterna som ligger lagrade hos staden, med ursprungsmärkning (proveniens).", "The records stored by the city, with their origin marking (provenance).")},
    {"id": "cip-a", "steg": 5, "skapa": _cip("A"), "krav_a": True, "sv": ("Stadens plattform: distribution A", "JSON"), "en": ("The city's platform: distribution A", "JSON"),
     "info": ("Posterna som ligger lagrade hos staden (mätetal och proveniens, utan positioner). Kräver ett gällande avtal om A.", "The records stored by the city (measures and provenance, without positions). Needs a current agreement for A.")},
    {"id": "analys-b-csv", "steg": 6, "skapa": _analys("b", "csv"), "sv": ("Analysen, distribution B", "CSV"), "en": ("The analysis, distribution B", "CSV"),
     "info": ("Rangordningen av brunnarna efter bräddvolym, utan positioner.", "The ranking of the chambers by overflow volume, without positions.")},
    {"id": "analys-b-json", "steg": 6, "skapa": _analys("b", "json"), "sv": ("Analysen, distribution B", "JSON"), "en": ("The analysis, distribution B", "JSON"),
     "info": ("Samma, med sammanfattning och per mottagande vattendrag.", "The same, with a summary and per receiving watercourse.")},
    {"id": "analys-a-csv", "steg": 6, "skapa": _analys("a", "csv"), "krav_a": True, "sv": ("Analysen, distribution A", "CSV"), "en": ("The analysis, distribution A", "CSV"),
     "info": ("Med positioner. Kräver ett gällande avtal om A.", "With positions. Needs a current agreement for A.")},
    {"id": "analys-a-geojson", "steg": 6, "skapa": _analys("a", "geojson"), "krav_a": True, "sv": ("Brunnarna med position", "GeoJSON"), "en": ("The chambers with positions", "GeoJSON"),
     "info": ("Går att öppna i ett kartprogram. Kräver ett gällande avtal om A.", "Can be opened in a map program. Needs a current agreement for A.")},
    {"id": "ordlista", "steg": 0, "skapa": _ordlista, "sv": ("Ordlistan", "JSON"), "en": ("The glossary", "JSON"),
     "info": ("Alla begrepp med förklaringar.", "All terms with explanations.")},
    {"id": "mim", "steg": 0, "skapa": _mim, "sv": ("MIM-bedömningen", "JSON"), "en": ("The MIM assessment", "JSON"),
     "info": ("Vår egen bedömning av hur vi följer MIM:arna.", "Our own assessment of how we follow the MIMs.")},
]
PER_ID = {p["id"]: p for p in POSTER}
# Filer som aldrig skrivs om, eftersom poängen är att de är exakt de byte som kom (summan räknades vid mottagandet).
# De får ändå inte innehålla något internt: kontrollen i skapa() vägrar dem i så fall.
BYTE_FOR_BYTE = {"leverans-a", "leverans-b"}


def filnamn(post, andelse, sprak):
    bas = "svada-%s" % post["id"]
    if post.get("krav_a"):
        bas += "-DISTRIBUTION-A-ej-for-spridning"
    # Tidsmärket (UTC) gör två hämtningar åtskiljbara även när innehållet skiljer (katalogen får nya id:n varje gång) och hindrar att
    # webbläsaren ersätter en tidigare fil med samma namn.
    return "%s-%s-%s.%s" % (bas, VERSION, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), andelse)


def skapa(post_id, sprak="sv", extern=True):
    """Skapar filen. Returnerar (bytes, mimetyp, filnamn, art, sha256, klass). Kastar Ej för normala skäl."""
    post = PER_ID.get(post_id)
    if post is None:
        raise Ej("Okänd fil.", "Unknown file.", status=404, kod="okand")
    resultat = post["skapa"](sprak, extern)
    innehall, mime, andelse, art = resultat[:4]
    if extern and post["id"] not in BYTE_FOR_BYTE and art != "referens":
        # (Referensfilerna, ordlistan och MIM-bedömningen, är statisk text och rensas inte: rensningen skulle ta bort ":4326" ur "EPSG:4326".
        # Spärren INTERNT nedan gäller dem ändå.)
        # Samma rensning som sidorna: DID:ernas och containrarnas namn byts mot neutrala, portar och interna adresser tas bort.
        text = innehall.decode("utf-8", "replace")
        text = rensa.utan_intern_adress(rensa.utan_portar(rensa.utan_containernamn(text)))
        innehall = text.encode("utf-8")
    summa = resultat[4] if len(resultat) > 4 and resultat[4] else hashlib.sha256(innehall).hexdigest()
    if extern and INTERNT.search(innehall.decode("utf-8", "replace")):
        # Stängt som standard: hellre ingen fil än en fil med interna adresser.
        raise Ej("Filen kan inte lämnas ut just nu.", "The file cannot be released right now.", status=500, kod="internt-innehall")
    klass = "K1R1T1" if post.get("krav_a") else "K0R1T1"
    return innehall, mime, filnamn(post, andelse, sprak), art, summa, klass


def anteckna(post, filnamn_, innehall, summa):
    """Auditloggen får en rad för varje nedladdning (vem som helst kan se att och vad som laddades ned, men inte vem)."""
    try:
        audit.notera(post["steg"] or 0, "nedladdning", "OK", "audit.nedladdning",
                     {"fil": post["id"], "filnamn": filnamn_, "bytes": len(innehall), "sha": summa})
    except Exception:                               # noqa: BLE001 – loggen får aldrig hindra nedladdningen
        pass


# ---------------------------------------------------------------------------
# Rutan i varje steg (server-renderad; knapparna förbättras av en liten JS-bit i vy.py)
# ---------------------------------------------------------------------------
import html as _html

_RUBRIK = {"sv": "Ladda ned det som passerar det här steget", "en": "Download what passes through this step"}
_INTRO = {
    "sv": "Filerna är det som kedjan just nu faktiskt har i det här steget, inte inspelade exempel. Varje fil har en kontrollsumma (SHA-256) "
          "så att du kan kontrollera att den är oförändrad.",
    "en": "The files are what the chain actually has at this step right now, not recorded examples. Each file has a checksum (SHA-256) "
          "so that you can check that it is unchanged.",
}
_A_NOT = {"sv": "Distribution A är icke-publik: filen märks så och får inte spridas vidare.",
          "en": "Distribution A is non-public: the file is marked as such and must not be passed on."}
_HUR = {"sv": "Kontrollera själv: <code>sha256sum fil</code> (eller <code>shasum -a 256 fil</code>) ska ge samma summa som visas här.",
        "en": "Check it yourself: <code>sha256sum file</code> (or <code>shasum -a 256 file</code>) should give the same checksum as shown here."}
_KNAPP = {"sv": "Ladda ned", "en": "Download"}


def ruta(steg_nr, sprak="sv"):
    sprak = "en" if sprak == "en" else "sv"
    poster = [p for p in POSTER if p["steg"] == steg_nr]
    if not poster:
        return ""
    e = _html.escape
    i = 1 if sprak == "en" else 0
    rader = []
    for p in poster:
        titel, format_ = p["sv" if sprak == "sv" else "en"]
        rader.append(
            '<li data-fil="%s"><button type="button" class="ladda" data-fil="%s" aria-label="%s: %s, %s">%s</button> '
            '<span class="lnamn">%s <small>(%s)</small></span><span class="linfo">%s</span>'
            '<span class="lsvar" role="status" aria-live="polite"></span></li>'
            % (e(p["id"]), e(p["id"]), e(_KNAPP[sprak]), e(titel), e(format_), e(_KNAPP[sprak]), e(titel), e(format_), e(p["info"][i])))
    a_not = ('<p class="lanm">%s</p>' % e(_A_NOT[sprak])) if any(p.get("krav_a") for p in poster) else ""
    return ('<aside class="nedladdning" aria-label="%s"><h3>%s</h3><p class="lintro">%s</p><ul>%s</ul>%s<p class="lhur">%s</p></aside>'
            % (e(_RUBRIK[sprak]), e(_RUBRIK[sprak]), e(_INTRO[sprak]), "".join(rader), a_not, _HUR[sprak]))


CSS = """
.nedladdning { border: 1px solid #c8d4c8; border-left: 4px solid #2e7d32; background: #f5faf5; border-radius: 6px; padding: .6rem .9rem; margin: 1rem 0; font-size: .9rem; }
.nedladdning h3 { margin: 0 0 .2rem; font-size: .95rem; }
.nedladdning .lintro, .nedladdning .lanm, .nedladdning .lhur { margin: .2rem 0 .4rem; color: #444; font-size: .82rem; }
.nedladdning ul { margin: 0; padding: 0; list-style: none; display: grid; gap: .5rem; }
.nedladdning li { display: grid; grid-template-columns: auto 1fr; gap: .1rem .6rem; align-items: baseline; }
.nedladdning li .linfo, .nedladdning li .lsvar { grid-column: 2; font-size: .8rem; color: #444; }
.nedladdning li .lsvar { overflow-wrap: anywhere; }
.nedladdning li .lsvar.fel { color: #8a1c16; }
.nedladdning li .lsvar code { font-size: .75rem; }
.nedladdning button.ladda { cursor: pointer; }
"""

# Klickhanterare: hämtar filen, sparar den och visar summan; ett normalt skäl att filen inte finns visas som text vid knappen.
SKRIPT = r"""
document.addEventListener('click', async e => {
  const k = e.target.closest && e.target.closest('button.ladda');
  if (!k) return;
  const li = k.closest('li'), svar = li.querySelector('.lsvar');
  const sprak = document.documentElement.lang === 'en' ? 'en' : 'sv';
  k.disabled = true; svar.className = 'lsvar'; svar.textContent = sprak === 'en' ? 'Fetching …' : 'Hämtar …';
  try {
    const r = await fetch('/api/ladda-ned/' + encodeURIComponent(k.dataset.fil) + '?lang=' + sprak, {cache: 'no-store'});
    if (!r.ok) {
      let t = ''; try { t = (await r.json()).detalj || ''; } catch (x) {}
      svar.className = 'lsvar fel'; svar.textContent = t || (sprak === 'en' ? 'The file could not be created.' : 'Filen kunde inte skapas.');
      return;
    }
    const summa = r.headers.get('X-Content-SHA256') || '';
    const namn = ((r.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/) || [])[1] || k.dataset.fil;
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = namn; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    svar.textContent = '';
    svar.append(namn + ' · ' + blob.size + (sprak === 'en' ? ' bytes · SHA-256: ' : ' byte · SHA-256: '));
    const c = document.createElement('code'); c.textContent = summa; svar.append(c);
  } catch (x) {
    svar.className = 'lsvar fel'; svar.textContent = sprak === 'en' ? 'The file could not be fetched.' : 'Filen kunde inte hämtas.';
  } finally { k.disabled = false; }
});
"""
