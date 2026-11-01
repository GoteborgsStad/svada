"""
modell.py – utkastet till datamodell, uppslagbart på brunnsvyns adress.

UTKAST. Modellen är inte beslutad, inte överenskommen med dataägaren (Kretslopp och Vatten), leverantören (DHI) eller den tekniska
förvaltaren (Intraservice) och inte inskickad till Smart Data Models. Varje sida och varje fil som serveras här säger det. Se
docs/modell/README.md.

Filerna ligger i datamodell/utkast/ (monteras skrivskyddat på /modell) och genereras av tools/bygg-datamodell.py. I förrådet har termernas
adresser en platshållare under .invalid som inte går att öppna; här byts den mot den här tjänstens egen publika adress, så att en term går att
slå upp (sida, eller JSON för en maskin). Tjänsten läser bara filer ur en fast lista och en termlista; inget ur begäran blir en filsökväg.
Standardbibliotek och vy.py, inga andra beroenden.
"""

import json
import os

import vy
from vy import e, _s

KATALOG = os.environ.get("MODELL_KATALOG", "/modell")
STATUS = "DRAFT v0.1, a temporary PoC model: not decided, not agreed, not submitted to Smart Data Models, not proposed as a general model"

# Filerna som serveras: namn -> (sökväg under katalogen, mediatyp). En fast lista, aldrig en sökväg ur begäran.
FILER = {
    "context.jsonld": ("context.jsonld", "application/ld+json"),
    "schema.json": ("schema.json", "application/schema+json"),
    "schema-profil-B.json": ("schema-profil-B.json", "application/schema+json"),
    "SPEC.md": ("SPEC.md", "text/plain"),
    "mappings.sssom.tsv": ("mappings.sssom.tsv", "text/plain"),
    "termer.json": ("termer.json", "application/json"),
    "examples/example-A.json": ("examples/example-A.json", "application/json"),
    "examples/example-B.json": ("examples/example-B.json", "application/json"),
    "examples/example-normalized-B.jsonld": ("examples/example-normalized-B.jsonld", "application/ld+json"),
}
BESKRIVNING_FIL = {
    "context.jsonld": ("JSON-LD-kontext: varje term till sin adress.", "JSON-LD context: each term to its address."),
    "schema.json": ("JSON Schema, profil A (hela modellen).", "JSON Schema, profile A (the whole model)."),
    "schema-profil-B.json": ("JSON Schema, profil B (utan position).", "JSON Schema, profile B (without position)."),
    "SPEC.md": ("Specifikationen i text.", "The specification as text."),
    "mappings.sssom.tsv": ("Länkar till termer hos andra (SSSOM).", "Links to terms elsewhere (SSSOM)."),
    "termer.json": ("Källan: alla termer med definition, enhet, ursprung och länkar.", "The source: every term with definition, unit, origin and links."),
    "examples/example-A.json": ("Exempel, profil A (utkast, ingen beslutad modell). Positionen är påhittad.", "Example, profile A (draft, not a decided model). The position is invented."),
    "examples/example-B.json": ("Exempel, profil B (utkast, ingen beslutad modell).", "Example, profile B (draft, not a decided model)."),
    "examples/example-normalized-B.jsonld": ("Exempel, profil B, i NGSI-LD-form (utkast, ingen beslutad modell).", "Example, profile B, in NGSI-LD form (draft, not a decided model)."),
}
URSPRUNG = {
    "egen": ("egen", "own", "Vår egen term med egen definition: ingen annan har den, såvitt vi hittat.",
             "Our own term with our own definition: nobody else has it, as far as we found."),
    "knyt": ("kopplad", "linked", "Vår egen term med egen definition, med en länk till den närmaste termen hos någon annan. Länken säger \"liknande\", inte \"samma\".",
             "Our own term with our own definition, with a link to the nearest term somewhere else. The link says \"similar\", not \"the same\"."),
    "lånad": ("lånad", "borrowed", "Någon annans term som vi använder som den är, med deras adress och definition.",
              "Somebody else's term that we use as it is, with their address and definition."),
}
LANKTYP = {
    "skos:exactMatch": ("samma sak", "the same thing"),
    "skos:closeMatch": ("nästan samma", "nearly the same"),
    "rdfs:seeAlso": ("besläktad, inte samma", "related, not the same"),
}
ENTITET = {"type": ("entitetstyp", "entity type"), "result": ("resultatet (SewerOverflowModelResult)", "the result (SewerOverflowModelResult)"),
           "weir": ("brunnen (SewerOverflowWeir)", "the chamber (SewerOverflowWeir)"),
           "provenance": ("proveniensen (medlem i provenance)", "provenance (a member of provenance)")}

_cache = {}


def _termer():
    """Läser termer.json en gång. Saknas katalogen (till exempel ingen montering) är modellen helt enkelt inte tillgänglig."""
    if "d" not in _cache:
        try:
            with open(os.path.join(KATALOG, "termer.json"), encoding="utf-8") as f:
                _cache["d"] = json.load(f)
        except (OSError, ValueError):
            _cache["d"] = None
    return _cache["d"]


def enheter(namn):
    """UN/CEFACT-enhetskoder för de angivna termerna, ur termlistan (en källa). Tomt om modellen inte är monterad."""
    d = _termer()
    if d is None:
        return {}
    return {t["name"]: t["unit"]["code"] for t in d["terms"] if t["name"] in namn and t.get("unit")}


def tillganglig():
    return _termer() is not None


def bas(egen_publik):
    return egen_publik.rstrip("/") + "/modell/utkast/0.1/"


def _byt_bas(text, egen_publik):
    d = _termer()
    return text.replace(d["model"]["base"], bas(egen_publik))


def fil(namn, egen_publik):
    """(innehåll som bytes, mediatyp) för en fil ur den fasta listan, annars None."""
    if not tillganglig() or namn not in FILER:
        return None
    sokvag, medietyp = FILER[namn]
    try:
        with open(os.path.join(KATALOG, sokvag), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    return _byt_bas(text, egen_publik).encode("utf-8"), medietyp


GENERERADE = {
    "utkast.zip": ("application/zip", "datamodell-utkast", "zip"),
    "termlista.csv": ("text/csv", "termlista", "csv"),
}


def genererad(namn, egen_publik):
    """Filer som byggs av de övriga: hela utkastet som zip (med manifest och SHA-256 per fil) och termlistan som CSV.
    Returnerar (innehåll, mediatyp, filnamn) eller None."""
    import filer
    d = _termer()
    if d is None or namn not in GENERERADE:
        return None
    mime, bas_namn, andelse = GENERERADE[namn]
    if namn == "termlista.csv":
        return filer.csv_bytes(filer.termlista_rader(d)), mime, filer.filnamn(bas_namn, andelse)
    samlade = {}
    for n in FILER:
        f = fil(n, egen_publik)
        if f is not None:
            samlade[n] = f[0]
    return filer.zip_bytes(samlade, STATUS, d["model"]["version"].split("-")[0]), mime, filer.filnamn(bas_namn, andelse)


def term(namn):
    d = _termer()
    if not d:
        return None
    for t in d["terms"]:
        if t["name"] == namn:
            return t
    return None


def term_json(t, egen_publik):
    """En terms beskrivning för en maskin: alltid med utkastets status."""
    d = _termer()
    u = {"id": bas(egen_publik) + t["name"], "name": t["name"], "status": STATUS,
         "belongsTo": d["model"]["entities"].get(t["entity"], t["entity"]),
         "kind": t["nature"], "type": t["type"], "unit": t["unit"], "definition": {"en": t["definition"], "sv": t["definition_sv"]},
         "origin": {"egen": "own", "knyt": "linked", "lånad": "borrowed"}[t["origin"]], "profiles": t["profiles"], "required": t["required"],
         "storedInBroker": t["stored"] == "broker", "links": t["links"]}
    if "enum" in t:
        u["allowedValues"] = t["enum"]
    if t.get("note"):
        u["note"] = t["note"]
    return u


def oversikt_json(egen_publik):
    d = _termer()
    return {"status": STATUS, "model": d["model"]["id"], "version": d["model"]["version"], "base": bas(egen_publik),
            "profiles": d["model"]["profiles"],
            "terms": [t["name"] for t in d["terms"]], "files": ["%s%s" % (bas(egen_publik), n) for n in FILER],
            "downloads": ["%s%s" % (bas(egen_publik), n) for n in GENERERADE]}


def utkast_ruta(sprak):
    """Rutan som sitter överst på varje sida: det här är ett utkast."""
    return ('<div class="utkast" role="note"><strong>' + _s(sprak, "UTKAST. Detta är ingen beslutad modell.", "DRAFT. This is not a decided model.") + "</strong> "
            + _s(sprak,
                 "Det är en tillfällig modell framtagen för PoC:en för att lära oss vad en modell behöver, inte en föreslagen allmän modell. Det är inte överenskommet med dataägaren "
                 "(Kretslopp och Vatten), leverantören (DHI) eller stadens tekniska förvaltare (Intraservice), och inte inskickat till Smart Data Models. "
                 "Termer och definitioner är framtagna tillsammans med AI-assistenter och inte granskade av sakkunniga. Termer, namn och adresser kan ändras utan förvarning.",
                 "It is a temporary model made for the PoC to learn what a model needs, not a proposed general model. It is not agreed with the data owner (Kretslopp och Vatten), "
                 "the provider (DHI) or the City's technical custodian (Intraservice), and it is not submitted to Smart Data Models. "
                 "The terms and definitions were prepared together with AI assistants and have not been reviewed by subject experts. Terms, names and "
                 "addresses may change without notice.")
            + "</div>")


def _namn_ursprung(t, sprak):
    sv, en, _, _ = URSPRUNG[t["origin"]]
    return _s(sprak, sv, en)


def _profil(t, sprak):
    if len(t["profiles"]) == 2:
        return "A, B"
    return _s(sprak, "bara " + t["profiles"][0], "only " + t["profiles"][0])


def _def(t, sprak):
    return t["definition_sv"] if sprak == "sv" else t["definition"]


def _enhet(t):
    return "%s (%s)" % (t["unit"]["label"], t["unit"]["code"]) if t["unit"] else ""


def modell_sida(egen_publik, mintaka_publik, katalog_url, sprak):
    d = _termer()
    m = d["model"]
    b = bas(egen_publik)
    rubriker = {"type": _s(sprak, "Entitetstyper", "Entity types"),
                "result": _s(sprak, "Termer i resultatet", "Terms of the result"),
                "weir": _s(sprak, "Termer för brunnen", "Terms of the chamber"),
                "provenance": _s(sprak, "Medlemmar i provenance (varifrån leveransen kom)", "Members of provenance (where the delivery came from)")}
    delar = []
    for nyckel in ("type", "result", "weir", "provenance"):
        rader = []
        for t in d["terms"]:
            if t["entity"] != nyckel:
                continue
            rader.append("<tr><td><a href=\"%s%s?lang=%s\"><code>%s</code></a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                e(b), e(t["name"]), sprak, e(t["name"]), e(_enhet(t)), e(_profil(t, sprak)), e(_namn_ursprung(t, sprak)), e(_def(t, sprak))))
        delar.append("<h2>%s</h2><table><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>" % (
            rubriker[nyckel], _s(sprak, "Term", "Term"), _s(sprak, "Enhet", "Unit"), _s(sprak, "Profil", "Profile"), _s(sprak, "Ursprung", "Origin"),
            _s(sprak, "Definition", "Definition"), "".join(rader)))
    filer = "".join("<li><a href=\"%s%s\"><code>%s</code></a>: %s</li>" % (e(b), e(n), e(n), e(_s(sprak, *BESKRIVNING_FIL[n]))) for n in FILER)
    ursprung = "".join("<li><b>%s</b>: %s</li>" % (e(_s(sprak, v[0], v[1])), e(_s(sprak, v[2], v[3]))) for v in URSPRUNG.values())
    kropp = (
        utkast_ruta(sprak)
        + "<h1>" + _s(sprak, "Datamodell (utkast)", "Data model (draft)") + "</h1>"
        + vy._sprakval(sprak, "/modell")
        + "<p>" + _s(sprak,
            "Den öppna distributionen är modellerade bräddresultat per brunn och dygn. Här är utkastet till den modell som beskriver dem: vilka fält det finns, "
            "vad varje term betyder, dess enhet, och hur den hänger ihop med termer hos andra. Beräkningsmodellen som tog fram värdena ingår inte; "
            "det här gäller datan som delas.",
            "The open distribution is modelled overflow results per chamber and day. This is the draft of the model that describes them: which fields there are, "
            "what each term means, its unit, and how it relates to terms elsewhere. The calculation model that produced the values is not part of it; "
            "this is about the data that is shared.") + "</p>"
        + "<h2>" + _s(sprak, "En modell, två profiler", "One model, two profiles") + "</h2>"
        + "<p>" + _s(sprak,
            "Modellen heter <code>%s</code>. Distribution A och B har samma modell. <b>B är en profil som utelämnar brunnens position</b> (<code>location</code> och "
            "<code>sourceSrs</code>); det är ett beslut om vem som får se positionen, inte en annan modell.",
            "The model is called <code>%s</code>. Distributions A and B have the same model. <b>B is a profile that leaves out the position of the chamber</b> "
            "(<code>location</code> and <code>sourceSrs</code>); that is a decision about who may see the position, not a different model.") % e(m["id"]) + "</p>"
        + "<h2>" + _s(sprak, "Slå upp en term", "Look up a term") + "</h2>"
        + "<p>" + _s(sprak,
            "Varje term har en egen adress under <code>%s</code>. Öppna den i webbläsaren för en sida, eller be om JSON:",
            "Each term has its own address under <code>%s</code>. Open it in a browser for a page, or ask for JSON:") % e(b) + "</p>"
        + "<pre>curl -H 'Accept: application/json' %soverflowVolumeM3</pre>" % e(b)
        + "<h2>" + _s(sprak, "Vad utkastet bygger på (ett tillfälligt val)", "What the draft is built on (a temporary choice)") + "</h2><p>" + _s(sprak,
            "Valet är gjort av projektet för PoC:en, utan dataägaren, leverantören och förvaltaren, och skulle göras om med dem i en riktig tjänst. "
            "Ingen modell vi hittade har en bräddhändelse, så de termerna är våra egna.",
            "The choice was made by the project for the PoC, without the data owner, the provider or the custodian, and would be redone with them in a real service. "
            "No model we found has an overflow event, so those terms are our own.") + "</p><ul>"
        + "<li>" + _s(sprak, "<b>NGSI-LD</b> (ETSI): strukturen, <code>location</code> och <code>name</code>, tagna som de är.", "<b>NGSI-LD</b> (ETSI): the structure, <code>location</code> and <code>name</code>, taken as they are.") + "</li>"
        + "<li>" + _s(sprak, "<b>Smart Data Models</b> (Environment, OpenChannelManagement): flöde, nivå, tillrinning och datum, länkade term för term.", "<b>Smart Data Models</b> (Environment, OpenChannelManagement): flow, level, inflow and dates, linked term by term.") + "</li>"
        + "<li>" + _s(sprak, "<b>INSPIRE</b> (Sewer Network): vilken sorts anläggning brunnen är, länkad.", "<b>INSPIRE</b> (Sewer Network): the kind of structure the chamber is, linked.") + "</li>"
        + "<li>" + _s(sprak, "<b>Dublin Core och PROV-O</b>: proveniens och beskrivningar, länkade. <b>UN/CEFACT</b>: enheterna.", "<b>Dublin Core and PROV-O</b>: provenance and descriptions, linked. <b>UN/CEFACT</b>: the units.") + "</li></ul>"
        + "<h2>" + _s(sprak, "Egen, kopplad eller lånad", "Own, linked or borrowed") + "</h2><ul>" + ursprung + "</ul>"
        + "".join(delar)
        + vy.nedladdningsruta(sprak, [(b + "utkast.zip", "Hela utkastet med alla filer och en kontrollsumma per fil", "The whole draft with all files and a checksum per file", "ZIP"),
                                      (b + "termlista.csv", "Termlistan (alla %d termer)" % len(d["terms"]), "The term list (all %d terms)" % len(d["terms"]), "CSV"),
                                      (b + "termer.json", "Termlistan med all information", "The term list with all information", "JSON")])
        + "<h2>" + _s(sprak, "Filer", "Files") + "</h2><ul>" + filer + "</ul>"
        + vy.mim.ruta("modell", sprak)
        + "<h2>" + _s(sprak, "Vad utkastet inte är", "What the draft is not") + "</h2><ul><li>"
        + _s(sprak, "Inte en beslutad modell, och inte en standard.", "Not a decided model, and not a standard.") + "</li><li>"
        + _s(sprak, "Inte godkänd av någon som äger datan eller förvaltar den.", "Not approved by anyone who owns or looks after the data.") + "</li><li>"
        + _s(sprak, "Inte inskickad till Smart Data Models; adresserna här är demons egna och provisoriska.",
             "Not submitted to Smart Data Models; the addresses here belong to the demo and are provisional.") + "</li><li>"
        + _s(sprak, "Entitetsidentifierarna (<code>urn:ngsi-ld:…</code>) är våra egna och inte en del av termernas adresser.",
             "The entity identifiers (<code>urn:ngsi-ld:…</code>) are ours and not part of the term addresses.") + "</li></ul>"
        + vy._sidfot(mintaka_publik, katalog_url, sprak))
    return vy._sida(_s(sprak, "Datamodell (utkast)", "Data model (draft)"), kropp, sprak)


def term_sida(t, egen_publik, mintaka_publik, katalog_url, sprak):
    d = _termer()
    b = bas(egen_publik)
    sv, en, forkl_sv, forkl_en = URSPRUNG[t["origin"]]
    lankar = "".join("<li><code>%s</code> (%s) <a href=\"%s\">%s</a><br>%s</li>" % (
        e(l["predicate"]), e(_s(sprak, *LANKTYP[l["predicate"]])), e(l["target"]), e(l["target"]), e(l["comment"])) for l in t["links"]) or "–"
    ent = ENTITET[t["entity"]]
    rader = [
        (_s(sprak, "Hör till", "Belongs to"), e(_s(sprak, *ent))),
        (_s(sprak, "Slag", "Kind"), e(t["nature"])),
        (_s(sprak, "Typ", "Type"), e(t["type"])),
        (_s(sprak, "Enhet", "Unit"), e(_enhet(t)) or "–"),
        (_s(sprak, "Profil", "Profile"), e(_profil(t, sprak))),
        (_s(sprak, "Obligatorisk", "Required"), _s(sprak, "ja", "yes") if t["required"] else _s(sprak, "nej", "no")),
        (_s(sprak, "Ursprung", "Origin"), "<b>%s</b>: %s" % (e(_s(sprak, sv, en)), e(_s(sprak, forkl_sv, forkl_en)))),
        (_s(sprak, "Lagras i brokern", "Stored in the broker"), _s(sprak, "ja", "yes") if t["stored"] == "broker" else _s(sprak, "nej, bara i leveransen", "no, only in the delivery")),
        (_s(sprak, "Adress", "Address"), "<code>%s</code>" % e(b + t["name"]) if t["origin"] != "lånad" else
         "<code>%s</code>" % e(next(l["target"] for l in t["links"] if l["predicate"] == "skos:exactMatch"))),
    ]
    if "enum" in t:
        rader.append((_s(sprak, "Tillåtna värden", "Allowed values"), ", ".join("<code>%s</code>" % e(v) for v in t["enum"])))
    if t.get("note"):
        rader.append((_s(sprak, "Anmärkning", "Note"), e(t["note"])))
    kropp = (
        utkast_ruta(sprak)
        + "<p><a href=\"/modell?lang=%s\">← %s</a></p>" % (sprak, _s(sprak, "Datamodell (utkast)", "Data model (draft)"))
        + "<h1><code>%s</code></h1>" % e(t["name"])
        + vy._sprakval(sprak, "/modell/utkast/0.1/" + e(t["name"]))
        + "<p><b>%s</b> %s</p>" % (_s(sprak, "Definition:", "Definition:"), e(_def(t, sprak)))
        + "<table><tbody>" + "".join("<tr><th>%s</th><td>%s</td></tr>" % r for r in rader) + "</tbody></table>"
        + "<h2>" + _s(sprak, "Länkar till termer hos andra", "Links to terms elsewhere") + "</h2><ul>" + lankar + "</ul>"
        + "<p><a href=\"%s%s?format=json\">%s</a></p>" % (e(b), e(t["name"]), _s(sprak, "Samma term som JSON", "The same term as JSON"))
        + vy._sidfot(mintaka_publik, katalog_url, sprak))
    return vy._sida(t["name"] + " – " + _s(sprak, "datamodell (utkast)", "data model (draft)"), kropp, sprak)
