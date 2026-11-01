"""filer.py – nedladdningar från brunnsvyn: de öppna data (distribution B) som tabell och JSON, och datamodellen som en samlad fil.

Allt här är öppet (K0R1T1, CC BY 4.0). Varje svar bär SHA-256 av exakt de byte som skickas (X-Content-SHA256), så att en besökare kan
jämföra mot en summa hen räknar själv. Brunnsvyn kopierar inget: filerna byggs av samma svar som sidan visar.
"""

import csv
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone

VERSION = os.environ.get("SVADA_VERSION", "okänd")
LICENS = "CC BY 4.0"


def csv_bytes(rader, kolumner=None):
    """En lista av platta poster som CSV (UTF-8, radslut \\n). Kolumnordningen är första förekomst, om inget anges."""
    if kolumner is None:
        kolumner = []
        for r in rader:
            for k in r:
                if k not in kolumner:
                    kolumner.append(k)
    ut = io.StringIO()
    skriv = csv.DictWriter(ut, fieldnames=list(kolumner), lineterminator="\n", extrasaction="ignore")
    skriv.writeheader()
    for r in rader:
        skriv.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in kolumner})
    return ut.getvalue().encode("utf-8")


def summa(innehall):
    return hashlib.sha256(innehall).hexdigest()


def huvud(innehall, filnamn, extra=None):
    h = {"Content-Disposition": 'attachment; filename="%s"' % filnamn, "X-Content-SHA256": summa(innehall),
         "X-Svada-Klass": "K0R1T1", "X-Svada-Licens": LICENS, "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    h.update(extra or {})
    return h


def filnamn(bas, andelse):
    """Version och UTC-tidsmärke i namnet, som i kontrollrummets nedladdningar: två hämtningar går att skilja åt och webbläsaren ersätter ingen tidigare fil."""
    return "svada-%s-%s-%s.%s" % (bas, VERSION, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), andelse)


def termlista_rader(termer):
    """Termlistan platt: en rad per term (för CSV)."""
    rader = []
    for t in termer["terms"]:
        rader.append({
            "term": t["name"], "hor_till": termer["model"]["entities"].get(t["entity"], t["entity"]), "slag": t.get("nature"),
            "typ": t.get("type"), "enhetskod": (t.get("unit") or {}).get("code") if t.get("unit") else None,
            "definition_en": t.get("definition"), "definition_sv": t.get("definition_sv"),
            "ursprung": {"egen": "own", "knyt": "linked", "lånad": "borrowed"}.get(t["origin"], t["origin"]),
            "profiler": " ".join(t.get("profiles") or []), "obligatorisk": t.get("required"),
            "lagras_i_brokern": t.get("stored") == "broker",
            "lankar": "; ".join("%s <%s>" % (l["predicate"], l["target"]) for l in (t.get("links") or [])),
        })
    return rader


def zip_bytes(filer, status, version):
    """Hela datamodellens utkast som en zip: filerna, en LASMIG med statusen och ett manifest med SHA-256 per fil.
    Tidsstämplarna i zip-filen är fasta, så att samma innehåll ger samma byte (och samma summa)."""
    manifest = {}
    ut = io.BytesIO()
    with zipfile.ZipFile(ut, "w", zipfile.ZIP_DEFLATED) as z:
        def lagg(namn, data):
            info = zipfile.ZipInfo(namn, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
            manifest[namn] = hashlib.sha256(data).hexdigest()
        lasmig = ("DRAFT. %s\n\nVersion %s. Files in this archive are generated from the draft data model of this demo. "
                  "MANIFEST.json lists the SHA-256 of every file.\n\nUTKAST. Det här är en tillfällig modell framtagen för PoC:en, "
                  "inte en beslutad eller föreslagen allmän modell.\n" % (status, version))
        lagg("READ-ME.txt", lasmig.encode("utf-8"))
        for namn in sorted(filer):
            lagg(namn, filer[namn])
        z.writestr(zipfile.ZipInfo("MANIFEST.json", date_time=(2026, 1, 1, 0, 0, 0)),
                   json.dumps({"status": status, "version": version, "sha256": manifest}, indent=2, ensure_ascii=False) + "\n")
    return ut.getvalue()
