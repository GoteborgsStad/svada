"""Sidan /mim: hur demon följer MIM:arna i detalj, med avsteg och bedömningar.

Innehållet är en kort version av docs/mims/ och ska stämma med den och med rutorna i mim.py (statusen hämtas därifrån).
Filen finns i två kopior (kontrollrummet och brunnsvyn); provet tests/mim_enhet.py kontrollerar att de är lika.
Statusen är vår EGEN bedömning, inte en certifiering.
"""
import html
import os

import mim

_e = html.escape


def _s(sprak, sv, en):
    return sv if sprak == "sv" else en


# nyckel -> (vad vi gör sv, vad vi gör en, avsteg sv, avsteg en)
DETALJ = {
    "MIM0": (
        "Data går att hämta på tre ställen: den öppna vyn (Distribution B som webbsida och JSON, med OpenAPI-beskrivning), tidsserien för B (NGSI-LD-frågor på tid och attribut) och stadens gateway för Distribution A, som kräver ett godkänt avtal. Svaren är maskinläsbara och går att fråga på tid och attribut. Mellan leverantören och staden går data över Dataspace Protocol (DSP) och räknas inte som åtkomst i MIM0:s mening.",
        "Data can be reached in three places: the open view (Distribution B as a web page and JSON, with an OpenAPI description), the time series interface for B (NGSI-LD queries on time and attributes) and the City's gateway for Distribution A, which needs an approved agreement. The answers are machine-readable and can be queried on time and attributes. Between the provider and the City, data travels over the Dataspace Protocol (DSP) and does not count as access in MIM0's sense.",
        "Prenumeration på ändringar (R3.1) gäller inte vårt användningsfall. Positionsfrågor erbjuds inte för B, eftersom B saknar brunnarnas positioner med flit. Den öppna demon återställs varje natt, så en tidsserie är kort.",
        "Subscription to changes (R3.1) does not apply to our use case. Position queries are not offered for B, because B has no chamber positions on purpose. The open demo is reset every night, so a time series is short."),
    "MIM1": (
        "Varje brunn och varje leverans är en entitet med ett unikt id av typ och brunns-id (till exempel urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4402). Samma brunns-id följer brunnen genom hela kedjan. Attributens namn går att följa till en definition på brunnsvyns adress (/modell).",
        "Every chamber and every delivery is an entity with a unique id made of type and chamber id (for example urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4402). The same chamber id follows the chamber through the whole chain. The attributes' names can be followed to a definition at the chamber view's address (/modell).",
        "Id:na är påhittade för PoC:en och kommer att ändras; ingen förvaltar dem över tid (R1.5, PoC-begränsning). Modellen som ger typerna och attributen deras betydelse är ett utkast som inte är överenskommet med dataägaren, leverantören eller förvaltaren. Att följa en relation genom stadens gateway har vi inte prövat (R3.1, ej bedömd).",
        "The ids are made up for the PoC and will change; nobody governs them over time (R1.5, PoC limitation). The model that gives the types and attributes their meaning is a draft that is not agreed with the data owner, the provider or the custodian. We have not tested following a relation through the City's gateway (R3.1, not assessed)."),
    "MIM2": (
        "Data har en tydlig struktur (NGSI-LD) med uttryckliga enheter och tider. Modellen är byggd på erkända modeller (NGSI-LD, Smart Data Models, INSPIRE, Dublin Core, PROV-O, UN/CEFACT) och länkad till dem; grunden står på /modell. Varje leverans kontrolleras mot modellens schema innan staden lagrar den, och resultatet syns i steg 4. Katalogens conformsTo och den öppna vyn pekar på modellen.",
        "The data has a clear structure (NGSI-LD) with explicit units and times. The model is built on recognised models (NGSI-LD, Smart Data Models, INSPIRE, Dublin Core, PROV-O, UN/CEFACT) and linked to them; the basis is on /modell. Every delivery is checked against the model's schema before the City stores it, and the result is shown in step 4. The catalogue's conformsTo and the open view point to the model.",
        "Modellen är en tillfällig modell framtagen för PoC:en, inte en beslutad modell. Den bygger på erkända modeller i ett tillfälligt val av projektet. Vi föreslår den inte som allmän modell och skickar inte in den till Smart Data Models (R1.2b, PoC-begränsning). Det finns bara en källmodell, så det finns inget att förena (R2.1, PoC-begränsning). Ingen erkänd modell har en bräddhändelse, så de termerna är våra egna.",
        "The model is a temporary model made for the PoC, not a decided model. It is built on recognised models in a temporary choice by the project. We do not propose it as a general model and do not submit it to Smart Data Models (R1.2b, PoC limitation). There is only one source model, so there is nothing to unify (R2.1, PoC limitation). No recognised model has an overflow event, so those terms are our own."),
    "MIM3": (
        "Staden hittar leverantören i deltagarregistret och frågar katalogen vad som delas. Villkoren följer med erbjudandet i ODRL, parterna enas, och ett avtal gäller tills det hävs. Rättighetsinnehavaren (Kretslopp och Vatten) beslutar om Distribution A hos leverantören. Parterna identifieras med verifierbara intyg.",
        "The City finds the provider in the participant directory and asks the catalogue what is shared. The terms travel with the offer in ODRL, the parties agree, and a contract holds until it is ended. The rights holder (Kretslopp och Vatten) decides on Distribution A at the provider. The parties are identified with verifiable credentials.",
        "Styrning och regelverk (en samordnare som beslutar ett regelverk, kraven RC1.1–RC1.3, RC2.4, RC3.1) är PoC-begränsningar: vi har bara en roll som vi själva spelar. Förfrågningar om ny data (RC7.1, RC7.2) ligger utanför PoC:en. Att leverantören granskar hur datan används (RC3.2) är en avtalsskrivning utan granskningsrutin och utan juridisk text. Deltagarregistret ligger i minnet och har förenklingar. Hävningsregeln (ett avslag häver tidigare avtal) är en medveten förenkling och är avstängd i den delade demon, så att besökare inte stör varandra; ett avtal häver man där med knappen ”KoV häver avtalet”.",
        "Governance and a rulebook (a coordinator who decides a rulebook, requirements RC1.1–RC1.3, RC2.4, RC3.1) are PoC limitations: we have only a role that we play ourselves. Requests for new data (RC7.1, RC7.2) are outside the PoC. That the provider audits how the data is used (RC3.2) is a contract term without an audit routine and without legal text. The participant directory is held in memory and has simplifications. The termination rule (a refusal ends earlier contracts) is a deliberate simplification and is switched off in the shared demo so that visitors do not disturb each other; an agreement is revoked there with the ”KoV revokes the agreement” button."),
    "MIM6": (
        "Åtkomst styrs: katalogen läses bara av den som bevisar vem den är med ett verifierbart intyg, och Distribution A kräver ett godkänt avtal och en nyckel som staden kontrollerar vid varje användning. Parterna identifieras med intyg som utfärdas av rätt utfärdare (medlemskap och deltagande av samordnaren, roller av organisationen själv).",
        "Access is controlled: the catalogue can only be read by a party that proves who it is with a verifiable credential, and Distribution A needs an approved agreement and a key that the City checks at every use. The parties are identified with credentials issued by the right issuer (membership and participation by the coordinator, roles by the organisation itself).",
        "Utfärdaren är en medveten förenkling: den är inte förankrad i eIDAS. Skyddet av lagrade data (skydd mot att någon ändrar dem i smyg, och en granskningslogg som överlever omstart) saknas; kontrollrummets logg är kedjad med kontrollsummor men ligger i minnet. Delade nycklar skyddar vissa tjänsters interna gränssnitt, vilket är en förenkling i en PoC.",
        "The issuer is a deliberate simplification: it is not anchored in eIDAS. Protection of stored data (against silent changes, and an audit log that survives restarts) is missing; the control room's log is chained with checksums but kept in memory. Shared keys protect some services' internal interfaces, which is a simplification in a PoC."),
    "MIM7": (
        "Positionerna för Distribution A är GeoJSON-punkter i NGSI-LD och visas som punkter på en karta i steg 6. Distribution B har inga brunnspositioner med flit.",
        "The positions for Distribution A are GeoJSON points in NGSI-LD and are shown as points on a map in step 6. Distribution B has no chamber positions on purpose.",
        "MIM7 har inga numrerade krav i v9.0, så den går inte att bedöma mot krav. Den rekommenderar OGC-tjänster (WFS, OGC API); vi erbjuder inga. Vi visar bara data på en karta och redovisar därför vad vi gör i stället för en status.",
        "MIM7 has no numbered requirements in v9.0, so it cannot be assessed against requirements. It recommends OGC services (WFS, OGC API); we offer none. We only show data on a map, so we state what we do instead of a status."),
}

ORDNING = ["MIM0", "MIM1", "MIM2", "MIM3", "MIM6", "MIM7"]

_TEXT = {
    "sv": {
        "titel": "Hur den här demon följer MIM:arna",
        "ingress": "MIM:ar (Minimal Interoperability Mechanisms) är minimikrav för interoperabilitet som organisationen OASC har samlat. Den här sidan säger vad vi gör för varje MIM, vilka avsteg vi har och hur vi bedömt oss själva.",
        "ärlig_h": "Så ska du läsa statusen",
        "ärlig": [
            "Statusen är vår egen bedömning. Ingen utomstående har granskat den, och det är ingen certifiering.",
            "Vår PoC är i grunden teknisk. De mjuka delarna (styrning, avtalsmallar, regelverk, juridik) omfattas inte fullt ut, och det syns som PoC-begränsningar.",
            "Vi skriver \"Följs\" först när inget krav har statusen \"Följs inte\". PoC-begränsning betyder att kravet hålls tillbaka just för att det här är en PoC, inte att vi valt bort det i en riktig tjänst.",
            "MIM4 (personuppgifter) och MIM8 (lokala digitala tvillingar) har vi inte bedömt. Datamodellen och id:na är påhittade för PoC:en och är inga förslag på allmänna modeller eller identifierare.",
        ],
        "vad": "Vad MIM:en är", "gor": "Vad vi gör", "avsteg": "Avsteg och begränsningar", "status": "Vår status",
        "las": "Läs MIM:en hos OASC", "tillbaka": "Tillbaka",
    },
    "en": {
        "titel": "How this demo follows the MIMs",
        "ingress": "MIMs (Minimal Interoperability Mechanisms) are minimal requirements for interoperability collected by the organisation OASC. This page says what we do for each MIM, which departures we have and how we assessed ourselves.",
        "ärlig_h": "How to read the status",
        "ärlig": [
            "The status is our own assessment. Nobody outside has reviewed it, and it is not a certification.",
            "Our PoC is technical at heart. The soft parts (governance, contract templates, rulebook, legal matters) are not fully covered, and that shows as PoC limitations.",
            "We write \"Followed\" only when no requirement has the status \"Not followed\". PoC limitation means the requirement is held back precisely because this is a PoC, not that we have chosen to leave it out of a real service.",
            "We have not assessed MIM4 (personal data) or MIM8 (local digital twins). The data model and the ids are made up for the PoC and are not proposals for general models or identifiers.",
        ],
        "vad": "What the MIM is", "gor": "What we do", "avsteg": "Departures and limitations", "status": "Our status",
        "las": "Read the MIM at OASC", "tillbaka": "Back",
    },
}


def innehall(sprak):
    """Sidans huvuddel som HTML (utan sidskal)."""
    t = _TEXT[sprak]
    ut = ['<h1>%s</h1><p class="ingress">%s</p>' % (_e(t["titel"]), _e(t["ingress"])),
          '<section class="mimhur"><h2>%s</h2><ul>%s</ul></section>'
          % (_e(t["ärlig_h"]), "".join("<li>%s</li>" % _e(x) for x in t["ärlig"]))]
    for nyckel in ORDNING:
        kort, n_sv, n_en, v_sv, v_en, sida, s_sv, s_en, _niva = mim.MIM[nyckel]
        gor_sv, gor_en, av_sv, av_en = DETALJ[nyckel]
        ut.append(
            '<section id="%s" class="mimsek"><h2>%s %s</h2>'
            '<p><strong>%s.</strong> %s</p>'
            '<p><strong>%s.</strong> %s</p>'
            '<p><strong>%s.</strong> %s</p>'
            '<p><strong>%s:</strong> %s</p>'
            '<p><a href="%s%s" target="_blank" rel="noopener" aria-label="%s (%s)">%s</a></p></section>'
            % (nyckel.lower(), _e(kort), _e(_s(sprak, n_sv, n_en)),
               _e(t["vad"]), _e(_s(sprak, v_sv, v_en)),
               _e(t["gor"]), _e(_s(sprak, gor_sv, gor_en)),
               _e(t["avsteg"]), _e(_s(sprak, av_sv, av_en)),
               _e(t["status"]), _e(_s(sprak, s_sv, s_en)),
               mim._BAS, sida,
               _e(t["las"] + ": " + kort + " " + _s(sprak, n_sv, n_en)),
               _e(_s(sprak, "öppnas i ny flik, extern sida", "opens in a new tab, external site")),
               _e(t["las"])))
    return "".join(ut)


CSS = """
.mimsek { border-top: 1px solid #c7d2e0; margin-top: 1.2rem; padding-top: .4rem; }
.mimsek h2, .mimhur h2 { font-size: 1.1rem; margin: .6rem 0 .3rem; }
.mimsek p { margin: .4rem 0; }
.ingress { color: #444; }
"""


def sida(sprak, path="/mim"):
    """Fristående sida (används av kontrollrummet och brunnsvyn). Delar CSS och språkbyte."""
    sprak = sprak if sprak in _TEXT else "sv"
    t = _TEXT[sprak]
    andra = ("en", "English") if sprak == "sv" else ("sv", "Svenska")
    return f"""<!doctype html><html lang="{sprak}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(t["titel"])}</title><style>
:root{{color-scheme:light;--fg:#1d1d1d}}
body{{background:#fff;color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:1rem 16px 3rem}}
a{{color:#0848a6}} h1{{margin:.6rem 0 .2rem}}
.topp{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
{CSS}
</style></head><body>
<div class="topp"><a href="/?lang={sprak}">&larr; {_e(t["tillbaka"])}</a><a href="{path}?lang={andra[0]}" hreflang="{andra[0]}">{andra[1]}</a></div>
{innehall(sprak)}
<p style="color:#47504c;font-size:.85rem;margin-top:2rem">{_s(sprak, "Version", "Version")} {_e(os.environ.get("SVADA_VERSION", "okänd"))}</p>
</body></html>"""
