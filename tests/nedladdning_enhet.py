#!/usr/bin/env python3
"""K39 (utan stack): nedladdningarna. Registret täcker varje steg, A kräver ett gällande avtal, filer med interna adresser vägras,
CSV/zip/kontrollsummor är riktiga, främmande avtals-id syns inte i stadens poster, rutan finns på båda språken."""
import re
import hashlib
import io
import json
import os
import sys
import zipfile

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROT, "services", "dashboard"))
sys.path.insert(0, os.path.join(ROT, "services"))
os.environ.setdefault("SVADA_VERSION", "2026.10.29-14")
import analys  # noqa: E402
import kallor  # noqa: E402
import nedladdning  # noqa: E402
import sessioner  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    if not villkor:
        fel += 1


print("== Registret ==")
ids = [p["id"] for p in nedladdning.POSTER]
kolla(len(ids) == len(set(ids)), "id:na är unika")
kolla(all(any(p["steg"] == n for p in nedladdning.POSTER) for n in range(1, 7)), "varje steg 1-6 har minst en fil")
kolla(any(p["steg"] == 0 for p in nedladdning.POSTER), "ordlistan och MIM-bedömningen kan laddas ned (steg 0)")
kolla(all(re.fullmatch(r"svada-[a-z-]+(-DISTRIBUTION-A-ej-for-spridning)?-[0-9.]+-[0-9]+-[0-9]{8}T[0-9]{6}Z\.json", nedladdning.filnamn(p, "json", "sv")) for p in nedladdning.POSTER), "filnamnet bär versionen och ett tidsmärke (UTC), så att två hämtningar går att skilja åt")
kolla(all("DISTRIBUTION-A" in nedladdning.filnamn(p, "json", "sv") for p in nedladdning.POSTER if p.get("krav_a")), "filer med distribution A märks i filnamnet")
kolla(all("DISTRIBUTION-A" not in nedladdning.filnamn(p, "json", "sv") for p in nedladdning.POSTER if not p.get("krav_a")), "filer utan A har inte A-märket")
kolla(all(p["sv"][0] and p["en"][0] and p["info"][0] and p["info"][1] for p in nedladdning.POSTER), "varje fil har titel och information på båda språken")

print("== CSV ==")
c = nedladdning._csv([{"id": "a", "v": 1.5, "location": {"type": "Point", "coordinates": [11.9, 57.7]}}, {"id": "b", "v": None}]).decode()
kolla(c.splitlines()[0] == "id,v,location.lon,location.lat", "positionen blir lon och lat: %r" % c.splitlines()[0])
kolla(c.splitlines()[1] == "a,1.5,11.9,57.7" and c.splitlines()[2] == "b,,,", "värden och tomma fält: %r" % c.splitlines()[1:])

print("== Åtkomst: distribution A kräver ett gällande avtal ==")
analys.senaste_gallande_a_avtal = lambda: (None, None)
for p in nedladdning.POSTER:
    if p.get("krav_a"):
        try:
            nedladdning.skapa(p["id"], "sv", extern=True)
            kolla(False, "%s utan avtal borde nekas" % p["id"])
        except nedladdning.Ej as ej:
            kolla(ej.status == 403 and ej.kod == "kraver-avtal", "%s utan gällande avtal: 403 med förklaring" % p["id"])
analys.senaste_gallande_a_avtal = lambda: (None, {"id": "x", "status": "HAVT"})
try:
    nedladdning._kraver_a()
except nedladdning.Ej as ej:
    kolla("hävt" in ej.sv and "revoked" in ej.en, "ett hävt avtal sägs i förklaringen på båda språken")

print("== Referensfiler rensas inte, och A följer besökarens egna gällande avtal ==")
b_, _m, _e, _a, _s_, _k = nedladdning.skapa("ordlista", "sv", extern=True)
kolla(b"EPSG:4326" in b_, "ordlistan har kvar ':4326' i EPSG:4326 (rensningen rör inte referensfiler)")
_reg = {"avtal": [{"id": "A1", "distribution": "A", "status": "HAVT"}, {"id": "A2", "distribution": "A", "status": "GALLANDE"},
                  {"id": "AX", "distribution": "A", "status": "GALLANDE"}]}
_orig_reg = kallor.avtalsregister
kallor.avtalsregister = lambda: _reg
_s1 = sessioner.Session("1" * 32); _s1.avtal.update({"A1", "A2"})
_tok = sessioner.satt(_s1)
kolla([a["id"] for a in nedladdning._egna_avtal("A")] == ["A1", "A2"], "besökaren ser bara sina egna avtal (inte AX)")
_hamtade = []
_orig_hamta = nedladdning._hamta_ingest_innehall
nedladdning._hamta_ingest_innehall = lambda i: (_hamtade.append(i), (b'{"x":1}', {"X-Received-At": i, "X-Content-SHA256": "s"}))[1]
analys.senaste_gallande_a_avtal = lambda: (_reg["avtal"][1], _reg["avtal"][0])
_farsk = {"A2": "GALLANDE"}
_orig_farsk = kallor.ingest_avtalsstatus
kallor.ingest_avtalsstatus = lambda i: {"id": i, "status": _farsk.get(i, "OKAND")}
nedladdning.PER_ID["leverans-a"]["skapa"]("sv", True)
kolla(_hamtade == ["A2"], "Leverera A hämtar bara från GÄLLANDE avtal (inte hävda A1, inte andras AX): %s" % _hamtade)
# Registret säger GÄLLANDE men den färska statusen är hävd (listan synkas inte vid läsning): ingen leverans A lämnas ut.
_hamtade.clear(); _farsk["A2"] = "HAVT"
try:
    nedladdning.PER_ID["leverans-a"]["skapa"]("sv", True)
    kolla(False, "leverans A under ett avtal som just hävts borde nekas")
except nedladdning.Ej as ej:
    kolla(ej.status == 403 and not _hamtade, "leverans A nekas (403) och inget hämtas när färsk status är hävd, trots att registret säger gällande")
def _kasta(i):
    raise OSError("ingest nåddes inte")
kallor.ingest_avtalsstatus = _kasta
try:
    nedladdning.PER_ID["leverans-a"]["skapa"]("sv", True)
    kolla(False, "leverans A utan läsbar status borde nekas")
except nedladdning.Ej as ej:
    kolla(ej.status == 403 and not _hamtade, "kan statusen inte läsas nekas leverans A (stängt som standard)")
kallor.ingest_avtalsstatus = _orig_farsk
nedladdning._hamta_ingest_innehall = _orig_hamta
kallor.avtalsregister = _orig_reg
sessioner.aterstall(_tok)

print("== Inget internt ==")
nedladdning.PER_ID["katalog"]["skapa"] = lambda s, x: (b'{"adress": "http://edc-provider:19194/protocol", "p": "did:web:identity-hub-stad%3A29197"}', "application/json", "json", "faktisk")
ut = nedladdning.skapa("katalog", "sv", extern=True)[0].decode()
kolla("edc-provider" not in ut and "19194" not in ut and "29197" not in ut and "did:web:stad.example" in ut,
      "containernamn, portar och DID-namn byts mot neutrala (samma rensning som sidorna): %s" % ut.strip())
kolla("edc-provider" in nedladdning.skapa("katalog", "sv", extern=False)[0].decode(), "den interna varianten rensar inget")
nedladdning.PER_ID["katalog"]["skapa"] = lambda s, x: (b'{"db": "timescale-stad", "k": "FCF-simulator"}', "application/json", "json", "faktisk")
try:
    nedladdning.skapa("katalog", "sv", extern=True)
    kolla(False, "en fil med ett internt namn som inte rensas borde vägras")
except nedladdning.Ej as ej:
    kolla(ej.status == 500 and ej.kod == "internt-innehall", "en fil som ändå har ett internt namn vägras (stängt som standard)")
nedladdning.PER_ID["katalog"]["skapa"] = lambda s, x: (b'{"k": "FCF-simulator"}', "application/json", "json", "faktisk")
kolla(nedladdning.skapa("katalog", "sv", extern=True)[2].endswith(".json"), "visningsnamnet FCF-simulator är inget internt namn")
nedladdning.PER_ID["leverans-b"]["skapa"] = lambda s, x: (b'{"x": "edc-provider"}', "application/json", "json", "faktisk", "ab" * 32)
try:
    nedladdning.skapa("leverans-b", "sv", extern=True)
    kolla(False, "leveransen skrivs inte om, så ett internt namn i den ska vägras")
except nedladdning.Ej as ej:
    kolla(ej.kod == "internt-innehall", "leveransen (byte för byte) skrivs inte om men vägras om den skulle innehålla något internt")
kolla(not nedladdning.PORT_I_ADRESS.sub("", "x%3A19194/y").count("19194"), "portar ur adresser tas bort (%3A19194)")

print("== Kontrollsumma ==")
nedladdning.PER_ID["deltagare"]["skapa"] = lambda s, x: (b'{"a": 1}\n', "application/json", "json", "faktisk")
innehall, mime, namn, art, summa, klass = nedladdning.skapa("deltagare", "sv", extern=True)
kolla(summa == hashlib.sha256(innehall).hexdigest(), "SHA-256 är summan av exakt de byte som skickas")
kolla(klass == "K0R1T1" and art == "faktisk", "klass och art följer med")
nedladdning.PER_ID["leverans-b"]["skapa"] = lambda s, x: (b'{"z":1}', "application/json", "json", "faktisk", "ab" * 32)
kolla(nedladdning.skapa("leverans-b", "sv", True)[4] == "ab" * 32, "för leveransen används summan som räknades vid mottagandet")

print("== Främmande avtal syns inte ==")
s = sessioner.Session("0" * 32)
s.avtal = {"mitt"}
sessioner.satt(s)
poster = nedladdning._skydda_proveniens([{"provenance": {"contractAgreementId": "annans", "contractAgreementUrl": "u", "transferProcessId": "t", "batchId": "b"}},
                                          {"provenance": {"contractAgreementId": "mitt", "contractAgreementUrl": "u", "batchId": "b"}}])
kolla("contractAgreementId" not in poster[0]["provenance"] and "transferProcessId" not in poster[0]["provenance"] and poster[0]["provenance"]["batchId"] == "b",
      "en annans avtals-id, länk och överföringsid tas bort, resten kvar")
kolla(poster[1]["provenance"]["contractAgreementId"] == "mitt", "besökarens eget avtal står kvar")
sessioner.satt(None)

print("== Rutan ==")
for sprak in ("sv", "en"):
    for n in range(0, 7):
        h = nedladdning.ruta(n, sprak)
        kolla(bool(h) and all(('data-fil="%s"' % p["id"]) in h for p in nedladdning.POSTER if p["steg"] == n), "steg %d (%s): rutan har en knapp per fil" % (n, sprak))
    kolla("aria-label" in nedladdning.ruta(4, sprak) and "SHA-256" in nedladdning.ruta(4, sprak), "(%s): knapparna har namn och rutan nämner kontrollsumman" % sprak)
kolla(nedladdning.ruta(7, "sv") == "", "ett steg utan filer får ingen ruta")
kolla("icke-publik" in nedladdning.ruta(4, "sv") and "non-public" in nedladdning.ruta(4, "en") and "icke-publik" not in nedladdning.ruta(1, "sv"), "rutor med A-filer säger att A är icke-publik")

print("== Brunnsvyns filer ==")
sys.path.insert(0, os.path.join(ROT, "services", "publik-vy"))
import filer  # noqa: E402
z1 = filer.zip_bytes({"a.json": b"1", "b.json": b"2"}, "DRAFT x", "0.1")
z2 = filer.zip_bytes({"b.json": b"2", "a.json": b"1"}, "DRAFT x", "0.1")
kolla(z1 == z2, "zip-filen är deterministisk (samma innehåll ger samma byte och samma summa)")
zf = zipfile.ZipFile(io.BytesIO(z1))
man = json.loads(zf.read("MANIFEST.json"))
kolla(man["sha256"]["a.json"] == hashlib.sha256(b"1").hexdigest() and "READ-ME.txt" in zf.namelist(), "manifestet har rätt SHA-256 per fil och zip-filen har LÄS-MIG")
kolla("DRAFT" in zf.read("READ-ME.txt").decode(), "LÄS-MIG säger att det är ett utkast")
h = filer.huvud(b"abc", "x.csv")
kolla(h["X-Content-SHA256"] == hashlib.sha256(b"abc").hexdigest() and h["X-Svada-Klass"] == "K0R1T1", "svarshuvudet bär summan och klassen")
kolla(re.fullmatch(r"svada-brunnar-.+-[0-9]{8}T[0-9]{6}Z\.csv", filer.filnamn("brunnar", "csv")) is not None, "brunnsvyns filnamn bär också ett tidsmärke (UTC)")

print("OK: alla prov gröna" if fel == 0 else "FEL: %d" % fel)
sys.exit(1 if fel else 0)
