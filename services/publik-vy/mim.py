"""MIM-rutan: vilka av OASC:s MIM:ar (Minimal Interoperability Mechanisms) ett steg eller en sida berör, hur, och vår status.

En enda källa för texterna. Statusen per MIM är vår EGEN bedömning och ska stämma med docs/mims/README.md (provet
tests/mim_enhet.py jämför). Filen finns i två kopior (kontrollrummet och brunnsvyn bygger var för sig); provet kontrollerar att de är lika.
Texterna är medvetet korta, ärliga och utan överdrifter: påstå inget som docs/mims inte redovisar.
"""
import html

_BAS = "https://mims.oascities.org/mims-specification-v9.0/"

# nyckel -> (kortnamn, namn sv, namn en, vad sv, vad en, sida, status sv, status en, status-nivå)
# nivå styr bara färgen: ok (följs), delvis (följs med förbehåll), nej (följs inte ännu)
MIM = {
    "MIM0": ("MIM0", "Åtkomst till data", "Accessing data",
             "Data ska gå att hämta i ett maskinläsbart format över ett standardiserat webbgränssnitt, med formell beskrivning och enkla frågor.",
             "Data can be retrieved in a machine-readable format through a standard web interface, formally described, with simple queries.",
             "accessing-data", "Följs", "Followed", "ok"),
    "MIM1": ("MIM1", "Länkning av data", "Interlinking data",
             "Varje sak har ett unikt id, och betydelsen av typer och attribut går att slå upp.",
             "Every thing has a unique identifier, and the meaning of types and attributes can be looked up.",
             "interlinking-data", "Följs (modellen är ett utkast)", "Followed (the model is a draft)", "delvis"),
    "MIM2": ("MIM2", "Representation av data", "Representing data",
             "Data beskrivs av entydiga, väldokumenterade modeller som helst bygger på erkända standardmodeller.",
             "Data is described by unambiguous, well-documented models, preferably built on recognised standard models.",
             "representing-data", "Följs, med en PoC-begränsning (modellen är en tillfällig PoC-modell)", "Followed, with a PoC limitation (the model is a temporary PoC model)", "delvis"),
    "MIM3": ("MIM3", "Utbyte av data", "Exchanging data",
             "Parterna kan hitta varandra och data, enas om villkor och avtal, och avsluta ett avtal.",
             "Parties can find each other and the data, agree on terms and a contract, and end a contract.",
             "exchanging-data", "Följs för det tekniska. Vår PoC är i grunden teknisk, så de mjuka delarna (styrning, avtalsmallar, regelverk) omfattas inte fullt ut", "Followed for the technical parts. Our PoC is technical at heart, so the soft parts (governance, contract templates, rulebook) are not fully covered", "delvis"),
    "MIM7": ("MIM7", "Geodata", "Geospatial data",
             "Geodata ska gå att föra över och integrera mellan system, med bestående identifierare.",
             "Geospatial data can be transferred and integrated between systems, with persistent identifiers.",
             "geospatial-data", "Inga numrerade krav i v9.0 (går inte att bedöma); vi redovisar vad vi gör", "No numbered requirements in v9.0 (cannot be assessed); we state what we do", "delvis"),
    "MIM6": ("MIM6", "Säkerhet", "Securing data",
             "Åtkomst styrs, parterna identifieras säkert och kryptografi används på rätt sätt.",
             "Access is controlled, parties are identified securely and cryptography is used properly.",
             "securing-data", "Följs, med PoC-begränsningar", "Followed, with PoC limitations", "delvis"),
}

# Per steg och per sida: lista av (MIM-nyckel, hur sv, hur en). "Hur" säger vad just här är berört och vad som fattas.
STEG_MIM = {
    1: [("MIM2", "Modellens resultat har en egen struktur med enheter och tider. Datamodellen som beskriver den (på brunnsvyns adress, /modell) är en tillfällig modell för PoC:en, länkad till erkända modeller men inte föreslagen som allmän.",
                 "The model's result has a structure of its own with units and times. The data model that describes it (on the chamber view's address, /modell) is a temporary model for the PoC, linked to recognised models but not proposed as a general one.")],
    2: [("MIM3", "Staden hittar leverantören i deltagarregistret och frågar katalogen vad som delas, utan förhandsvetskap. Det fungerar för en enda leverantör. Förteckningen över deltagare ligger i minnet och försvinner vid omstart; en riktig förteckning måste vara bestående.",
                 "The City finds the provider in the participant directory and asks the catalogue what is shared, with no prior knowledge. It works for a single provider. The participant directory is held in memory and is lost on restart; a real one must be persistent."),
        ("MIM6", "Katalogen läses bara av den som bevisar vem den är med ett verifierbart intyg.",
                 "Only a party that proves who it is with a verifiable credential can read the catalogue.")],
    3: [("MIM3", "Villkoren följer med erbjudandet i ODRL, parterna enas och avtalet gäller tills det hävs eller går ut. Juridisk mall och regelverk saknas: PoC-begränsning.",
                 "The terms travel with the offer in ODRL, the parties agree and the contract holds until it is ended or expires. A legal template and a rulebook are missing: PoC limitation."),
        ("MIM6", "Parterna identifieras med verifierbara intyg, och godkännandet för A ges av rättighetsinnehavaren hos leverantören.",
                 "The parties are identified with verifiable credentials, and the approval for A is given by the rights holder at the provider.")],
    4: [("MIM3", "Leveransen kontrolleras mot avtalets villkor innan den tas emot. Att leverantören kontrollerar hur data används är bara en avtalsskrivning hos oss, inte en rutin som körs.",
                 "The delivery is checked against the contract's terms before it is accepted. That the provider checks how the data is used is only a contract term with us, not a routine that runs."),
        ("MIM2", "Leveransen kommer som leverans-JSON från leverantören: värdena inpackade tillsammans med uppgifter om vem som levererar och på vilka villkor. Innan staden lagrar den som NGSI-LD (öppet, i JSON och JSON-LD, steg 5) kontrolleras den mot modellens schema; resultatet visas här.",
                 "The delivery arrives as delivery JSON from the provider: the values wrapped together with who delivers and on what terms. Before the City stores it as NGSI-LD (open, in JSON and JSON-LD, step 5) it is checked against the model's schema; the result is shown here.")],
    5: [("MIM1", "Varje brunn har ett unikt id som följer den genom hela kedjan, och leveransens värden pekar på sin brunn (refWeir). Id:na är påhittade för PoC:en och kommer att ändras; en riktig tjänst behöver stabila, förvaltade id:n.",
                 "Every chamber has a unique id that follows it through the whole chain, and a delivery's values point to their chamber (refWeir). The ids are made up for the PoC and will change; a real service needs stable, managed ids."),
        ("MIM6", "Skyddet av lagrade data (skydd mot att någon ändrar dem i smyg, och en granskningslogg som överlever omstart) saknas: PoC-begränsning. Kontrollrummets logg är kedjad med kontrollsummor men ligger i minnet.",
                 "Protection of stored data (protection against silent changes, and an audit log that survives restarts) is missing: PoC limitation. The control room's log is chained with checksums but kept in memory.")],
    6: [("MIM0", "Samma data kan hämtas som JSON ur den öppna vyn och som JSON eller JSON-LD ur tidsserien. Den öppna vyn har en OpenAPI-beskrivning; tidsserien har frågor på tid och attribut.",
                 "The same data can be retrieved as JSON from the open view and as JSON or JSON-LD from the time series interface. The open view has an OpenAPI description; the time series interface has queries on time and attributes."),
        ("MIM7", "Positionerna i distribution A visas som punkter på en karta. De är GeoJSON-punkter i NGSI-LD och inte öppna data. Vi erbjuder inga OGC-tjänster (WFS, OGC API).",
                 "The positions in distribution A are shown as points on a map. They are GeoJSON points in NGSI-LD and not open data. We offer no OGC services (WFS, OGC API)."),
        ("MIM1", "Attributens namn går att följa till en definition på brunnsvyns adress (/modell), men modellen är ett utkast.",
                 "The attributes' names can be followed to a definition at the chamber view's address (/modell), but the model is a draft.")],
}

SIDA_MIM = {
    "brunnsvy": [("MIM0", "Den öppna vyn svarar som JSON med OpenAPI-beskrivning; tidsserien har frågor på tid och attribut.",
                          "The open view answers as JSON with an OpenAPI description; the time series interface has queries on time and attributes."),
                 ("MIM1", "Varje brunn har ett unikt id, och attributen går att följa till en definition på /modell (ett utkast).",
                          "Every chamber has a unique id, and the attributes can be followed to a definition at /modell (a draft).")],
    "modell": [("MIM1", "Varje term har en egen adress som ger definitionen, och data bär modellens kontext. Modellen är ett utkast som ännu inte är överenskommet.",
                        "Every term has an address of its own that gives the definition, and the data carries the model's context. The model is a draft that is not yet agreed."),
               ("MIM2", "Utkastet bygger på NGSI-LD och är länkat till erkända modeller (Smart Data Models, INSPIRE m.fl.) i ett tillfälligt val för PoC:en. Det föreslås inte som allmän modell och skickas inte in till Smart Data Models.",
                        "The draft is built on NGSI-LD and linked to recognised models (Smart Data Models, INSPIRE and others) in a temporary choice for the PoC. It is not proposed as a general model and not submitted to Smart Data Models.")],
}

_RUBRIK = {"sv": "MIM:ar som berörs här", "en": "MIMs involved here"}
_INTRO = {"sv": "MIM:ar är OASC:s minimikrav för interoperabilitet. Statusen är vår egen bedömning, inte en certifiering.",
          "en": "MIMs are OASC's minimal interoperability mechanisms. The status is our own assessment, not a certification."}
_LANKTEXT = {"sv": "läs MIM:en", "en": "read the MIM"}
_STATUS = {"sv": "Vår status", "en": "Our status"}
_MER = {"sv": "Läs mer om hur vi följer MIM:arna, våra avsteg och bedömningar →", "en": "Read more about how we follow the MIMs, our departures and assessments →"}


def _s(sprak, sv, en):
    return sv if sprak == "sv" else en


def poster(nyckel, tabell):
    return tabell.get(nyckel, [])


def ruta(nyckel, sprak, tabell=None):
    """HTML för rutan, eller tom text om inget är tillämpligt. nyckel är ett stegnummer eller ett sidnamn."""
    rader = (tabell if tabell is not None else {**STEG_MIM, **SIDA_MIM}).get(nyckel) or []
    if not rader:
        return ""
    e = html.escape
    ut = []
    for mim_nyckel, sv, en in rader:
        kort, n_sv, n_en, v_sv, v_en, sida, s_sv, s_en, niva = MIM[mim_nyckel]
        ut.append(
            '<li class="mim-%s"><strong>%s</strong> %s <a href="%s%s" target="_blank" rel="noopener" aria-label="%s">%s</a>'
            '<span class="mimvad">%s</span>'
            '<span class="mimhur">%s</span>'
            '<span class="mimstatus"><em>%s:</em> %s</span></li>'
            % (niva, e(kort), e(_s(sprak, n_sv, n_en)), _BAS, sida,
               e(_s(sprak, _LANKTEXT["sv"], _LANKTEXT["en"]) + ": " + kort + " " + _s(sprak, n_sv, n_en)
                 + " (" + _s(sprak, "öppnas i ny flik, extern sida", "opens in a new tab, external site") + ")"),
               e(_s(sprak, _LANKTEXT["sv"], _LANKTEXT["en"])),
               e(_s(sprak, v_sv, v_en)), e(_s(sprak, sv, en)), e(_STATUS[sprak]), e(_s(sprak, s_sv, s_en))))
    return ('<aside class="mimruta" aria-label="%s"><h3>%s</h3><p class="mimintro">%s</p><ul>%s</ul>'
            '<p class="mimmer"><a href="/mim?lang=%s">%s</a></p></aside>'
            % (e(_RUBRIK[sprak]), e(_RUBRIK[sprak]), e(_INTRO[sprak]), "".join(ut), sprak, e(_MER[sprak])))


def menylank(sprak):
    """Länken till sidan /mim för toppen av varje sida."""
    return '<a class="mimmeny" href="/mim?lang=%s">%s</a>' % (sprak, _s(sprak, "MIM-bedömningen", "MIM assessment"))


CSS_LJUS = """
.mimruta { border: 1px solid #c7d2e0; border-left: 4px solid #3b6ea8; background: #f5f8fc; border-radius: 6px; padding: .6rem .9rem; margin: 1rem 0; font-size: .9rem; }
.mimruta h3 { margin: 0 0 .2rem; font-size: .95rem; }
.mimruta .mimintro { margin: 0 0 .4rem; color: #555; font-size: .82rem; }
.mimruta ul { margin: 0; padding: 0; list-style: none; }
.mimruta li { margin: .45rem 0; padding-left: .6rem; border-left: 3px solid #999; }
.mimruta li.mim-ok { border-left-color: #2e7d32; }
.mimruta li.mim-delvis { border-left-color: #b26a00; }
.mimruta li.mim-nej { border-left-color: #b3261e; }
.mimruta li > span { display: block; }
.mimruta .mimvad { color: #444; }
.mimruta .mimstatus em { font-style: normal; font-weight: 600; }
.mimruta a { margin-left: .4rem; }
"""

# Mörkt tema: bara brunnsvyn och modellsidan har det; kontrollrummet är ljust (K5).
CSS_MORK = """
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .mimruta { background: #1d2733; border-color: #3a4a5e; } :root:not([data-theme="light"]) .mimruta .mimintro, :root:not([data-theme="light"]) .mimruta .mimvad { color: #b9c4d0; } }
:root[data-theme="dark"] .mimruta { background: #1d2733; border-color: #3a4a5e; }
:root[data-theme="dark"] .mimruta .mimintro, :root[data-theme="dark"] .mimruta .mimvad { color: #b9c4d0; }
"""

CSS = CSS_LJUS + CSS_MORK
