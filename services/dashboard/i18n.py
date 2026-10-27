#!/usr/bin/env python3
"""Svenska meddelanden -> engelska, för det kontrollrummet visar när språket är engelska.

KONCEPT: docs/koncept/C6-drift-och-uthallighet.md (språk i kontrollrummet)

Varför det finns
----------------
Sidans egna texter är tvåspråkiga (`S(sv, en)` i vy.py, `_t(sv, en)` i steg.py). Men kontrollrummet
visar också text som INTE skrivs av vyn: jobbloggens rader, auditloggens händelser, avvisningsorsaker
från stadens mottagning, nekanden från gatewayen och felmeddelanden från komponenterna. De skrivs på
svenska vid källan, i flera tjänster. Att göra alla tjänsters API tvåspråkiga vore en större ändring;
här översätts de vid kontrollrummets gräns: ett svar till en webbläsare som valt engelska passerar
`oversatt()`, som byter kända meningar mot engelska (regelverket nedan) och lämnar allt annat orört.

Gränser (medvetna)
------------------
* Det som är DATA översätts inte: brunnars och recipienters namn, id:n, värden och exempelobjekten
  (`/api/steg/N/exempel`), som visar objektet precis som det är. Exempelobjektens svenska värden
  (datamängdens titel, licenstext, kvalitetsdeklaration) står kvar och förklaras i dokumentationen.
* En okänd mening förblir på svenska. `tests/engelska_enhet.py` kör en lista verkliga meddelanden
  genom reglerna och larmar om svenska ord blir kvar, så att en ny svensk text i en tjänst upptäcks.
* Statuskoder (AUKTORISERAD, GODKAND, HAVT …) är identifierare. De översätts bara för visning
  (`KODER`), aldrig i API-fälten som används som nycklar eller CSS-klasser.
"""

import functools
import re

# Visningsnamn för koder som är svenska identifierare (aldrig nycklar).
KODER = {
    "AUKTORISERAD": "AUTHORISED",
    "AUKTORISATION-NEKAD": "AUTHORISATION-REFUSED",
    "AVVISAD": "REJECTED",
    "AVVISAT": "REJECTED",
    "AVSLAGEN": "REJECTED",
    "AVSLAGET": "REJECTED",
    "GODKAND": "APPROVED",
    "PABORJAD": "STARTED",
    "VANTANDE": "WAITING",
    "HAVT": "REVOKED",
    "UTGANGET": "EXPIRED",
    "GALLANDE": "VALID",
    "OKAND": "UNKNOWN",
    "LEVERERAD": "DELIVERED",
    "KLAR": "DONE",
    "FEL": "ERROR",
    "UTESTANGD": "EXCLUDED",
    "INSATT": "REINSTATED",
    "PÅ": "ON",
    "AV": "OFF",
}

# (mönster, ersättning). Tillämpas i ordning, delmening för delmening (re.sub), så att
# sammansatta meddelanden ("… (verifierad roll: …)") översätts del för del.
# Längre och mer specifika regler först.
_REGLER = [
    # ---- auditloggen -------------------------------------------------------------------
    (r"VÄNTAR på Data Rights Holder-beslut \(Kretslopp och Vatten\) för Distribution (\w+)",
     r"WAITING for a Data Rights Holder decision (Kretslopp och Vatten) on Distribution \1"),
    (r"KoV GODKÄNDE utlämning av Distribution (\w+)", r"KoV APPROVED the release of Distribution \1"),
    (r"KoV AVSLOG begäran om Distribution (\w+)", r"KoV REJECTED the request for Distribution \1"),
    (r"KoV HÄVDE avtalet om Distribution (\w+)", r"KoV REVOKED the agreement for Distribution \1"),
    (r"ett avslag av en ny begäran \(PoC-regel\)", "a rejection of a new request (PoC rule)"),
    (r"KoV häver direkt", "KoV revoked directly"),
    (r"\(verifierad roll: ", "(verified role: "),
    (r"rättighetsinnehavare \(dataägare\)", "rights holder (data owner)"),
    (r"Förhandling om Distribution (\w+) \((.*?)\) är (\w+)", r"Negotiation for Distribution \1 (\2) is \3"),
    (r"Transfer av Distribution (\w+) \((.*?)\) är (\w+)", r"Transfer of Distribution \1 (\2) is \3"),
    (r"consumerns förhandlings-API: ", "the consumer's negotiation API: "),
    (r"consumerns transfer-API: ", "the consumer's transfer API: "),
    (r"providerns avtalslista: ", "the provider's agreement list: "),
    (r"Felinjektion i fcf-sim: ", "Fault injection in fcf-sim: "),
    (r"Felinjektionen nollställd", "Fault injection reset"),
    (r"KoV \(Kretslopp och Vatten\) avslog begäran om Distribution A", "KoV (Kretslopp och Vatten) rejected the request for Distribution A"),
    (r"ingen lank med seq=(\S+) \(kedjan har just nu (\d+) lankar\)", r"no link with seq=\1 (the chain currently has \2 links)"),
    (r"lank (\d+):s lagrade foregaende-hash matchar inte den faktiskt foregaende lankens hash \(kedjan har manipulerats eller skadats\)",
     r"link \1: the stored previous hash does not match the actual previous link's hash (the chain has been tampered with or damaged)"),
    (r"lank (\d+):s lagrade hash matchar inte omrakningen fran dess kanoniska innehall \(hashen har mixtrats med i efterhand\)",
     r"link \1: the stored hash does not match the recomputation from its canonical content (the hash has been tampered with afterwards)"),
    (r"stadens EDC svarade HTTP (\d+) vid avtalsuppslag", r"the city's EDC answered HTTP \1 on agreement lookup"),
    # ---- jobbloggen: rubriker -----------------------------------------------------------
    (r"startar: ", "starting: "),
    (r"Kör en FCF-batch", "Run an FCF batch"),
    (r"Hämta DSP-katalogen", "Fetch the DSP catalogue"),
    (r"Förhandla Distribution (\w+)", r"Negotiate Distribution \1"),
    (r"Kör transfer \((\w+)\)( och se utfallet)?", r"Run transfer (\1)"),
    (r"KoV GODKÄNNER Distribution A", "KoV APPROVES Distribution A"),
    (r"KoV AVSLÅR Distribution A", "KoV REJECTS Distribution A"),
    (r"KoV HÄVER avtalet om Distribution A", "KoV REVOKES the agreement for Distribution A"),
    # ---- jobbloggen: rader --------------------------------------------------------------
    (r"FCF producerade batch (\S+) för modellerat dygn (\S+) \((\d+) poster\)",
     r"FCF produced batch \1 for modelled day \2 (\3 records)"),
    (r"förhandling (\S+) startad om Distribution (\w+)", r"negotiation \1 started for Distribution \2"),
    (r"Distribution A kräver KoV-godkännande – förhandlingen väntar hos PROVIDERN \(DHI:s connector\), eftersom "
     r"spärren sitter hos den som lämnar ut data\. Väntar \(högst (\d+) s\) på att förhandlingen dyker upp i kön\.",
     r"Distribution A requires KoV approval – the negotiation waits at the PROVIDER (DHI's connector), because "
     r"the barrier sits with whoever releases the data. Waiting (at most \1 s) for the negotiation to appear in the queue."),
    (r"providerns kö: id=(\S+) tillstånd=(\S+) pending=(\S+) beslut=(\S+)",
     r"provider queue: id=\1 state=\2 pending=\3 decision=\4"),
    (r"Använd KoV-panelen för att godkänna eller avslå\.", "Use the KoV panel to approve or reject."),
    (r"inget avtal ännu \(tillstånd (\w+)\)", r"no agreement yet (state \1)"),
    (r"avtal (\S+) \(tillstånd (\w+)\)", r"agreement \1 (state \2)"),
    (r"det finns inget kontraktsavtal för Distribution (\w+) – kör steg (\d) först( \(och låt KoV godkänna\))?",
     lambda m: "there is no contract agreement for Distribution %s – run step %s first%s"
     % (m.group(1), m.group(2), " (and let KoV approve)" if m.group(3) else "")),
    (r"använder avtal (\S+) \(förhandling (\S+)\)", r"using agreement \1 (negotiation \2)"),
    (r"avtalet (\S+) har gått ut \(giltighetstiden är slut\)\. Förhandla A på nytt och låt KoV godkänna för att få ett nytt avtal",
     r"agreement \1 has expired (the validity period is over). Negotiate A again and let KoV approve to get a new agreement"),
    (r"avtalet (\S+) är hävt av KoV – ett avtal gäller tills det hävs\. Förhandla A på nytt och låt KoV godkänna för att få ett nytt avtal",
     r"agreement \1 has been revoked by KoV – an agreement is valid until it is revoked. Negotiate A again and let KoV approve to get a new agreement"),
    (r"KoV-beslut (\S+) registrerat hos PROVIDERN: tillstånd=(\S+) pending=(\S+)",
     r"KoV decision \1 registered at the PROVIDER: state=\2 pending=\3"),
    (r"Så fungerar PoC:en: ett avslag av en ny begäran om A häver tidigare avtal för samma tillgång och part\. Hävda hos DHI: (.*)",
     r"How the PoC works: a rejection of a new request for A revokes earlier agreements for the same asset and party. Revoked at DHI: \1"),
    (r"Avslaget häver inget avtal \(regeln är avstängd i den delade demon, eller så fanns inget gällande avtal\)\.",
     "The rejection revokes no agreement (the rule is off in the shared demo, or there was no current agreement)."),
    (r"stadens förhandling (\S+) fick avtal (\S+) \((\w+)\)\. DHI:s förhandling är (\S+) och DHI:s eget avtals-id (\S+) – ids skiljer sig mellan connectorerna\.",
     r"the city's negotiation \1 got agreement \2 (\3). DHI's negotiation is \4 and DHI's own agreement id is \5 – the ids differ between the connectors."),
    (r"consumerns förhandling (\S+) är (\w+)", r"the consumer's negotiation \1 is \2"),
    (r"KoV har hävt avtal (\S+) hos DHI\. Avtalet gällde tills det hävdes; nya överföringar och nya åtkomstnycklar nekas\.",
     r"KoV has revoked agreement \1 at DHI. The agreement was valid until it was revoked; new transfers and new access keys are refused."),
    (r"stadens avtalsregister ser avtalet (\S+) som HÄVT \(synkas från DHI ungefär varje sekund\)",
     r"the city's agreement register sees agreement \1 as REVOKED (synced from DHI about every second)"),
    (r"stadens avtalsregister har ännu inte hunnit synka hävningen", "the city's agreement register has not yet synced the revocation"),
    (r"okänd åtgärd: ", "unknown action: "),
    (r"ett jobb kör redan – kedjan körs ett steg i taget", "a job is already running – the chain runs one step at a time"),
    (r"OVÄNTAT FEL: ", "UNEXPECTED ERROR: "),
    (r"MISSLYCKADES: ", "FAILED: "),
    (r"\b(distribute|publish) och (distribute|publish)\b", r"\1 and \2"),
    (r"okänt jobb", "unknown job"),
    # ---- kedjan (kedjan.py) ---------------------------------------------------------------
    (r"assetet (\S+) finns inte i DSP-katalogen \(kör registrera-edc\?\)", r"the asset \1 is not in the DSP catalogue (run registrera-edc?)"),
    (r"ingen förhandling skapades: ", "no negotiation was created: "),
    (r"ingen transferprocess skapades: ", "no transfer process was created: "),
    (r"ingest vägrade utfärda auktorisation för (\S+)", r"ingest refused to issue an authorisation for \1"),
    (r"engångsauktorisation utfärdad mot avtal (\S+)", r"one-time authorisation issued against agreement \1"),
    (r"transferprocess (\S+) startad \((\S+)\)", r"transfer process \1 started (\2)"),
    (r"transferprocessen är (\w+)", r"the transfer process is \1"),
    (r"försök (\d+): pushen nådde aldrig ingest \(EDC-dataplanets 'IOException: closed'\) – gör om om (\d+) s",
     r"attempt \1: the push never reached ingest (the EDC data plane's 'IOException: closed') – retrying in \2 s"),
    (r"transfern gav inget ingest-kvitto efter tre försök", "the transfer gave no ingest receipt after three attempts"),
    (r"ingest KVITTERADE: ", "ingest ACKNOWLEDGED: "),
    (r"ingest AVVISADE leveransen: ", "ingest REJECTED the delivery: "),
    (r"exempel ur avvisningen: ", "example from the rejection: "),
    (r"ODRL-offerten för (\S+) förbjuder (.*?)\. Det är avtalsvillkor som mottagaren förbinder sig till\.",
     r"The ODRL offer for \1 prohibits \2. These are contract terms the recipient commits to."),
    (r"Offerten bär dessutom skyldigheten (.*?) – Data Rights Holder \(Kretslopp och Vatten\) måste godkänna varje utlämning, "
     r"och ett sådant godkännande avser stadens EGET bruk, aldrig vidare publicering\.",
     r"The offer also carries the obligation \1 – the Data Rights Holder (Kretslopp och Vatten) must approve each release, "
     r"and such an approval covers the city's OWN use, never onward publication."),
    (r"Distribution A är informationsklassad (\S+) med accessRights=(\S+)\.", r"Distribution A is classified \1 with accessRights=\2."),
    # ---- stadens mottagning (ingest) och gateway ------------------------------------------
    (r"engång(?:stoken|snyckel) utfärdad för Distribution (\w+)", r"one-time key issued for Distribution \1"),
    (r"avtalet (\S+) har status (\w+) hos stadens avtalsregister – ingen nyckel utfärdas",
     r"agreement \1 has status \2 in the city's agreement register – no key is issued"),
    (r"avtalet (\S+) har status (\w+) – ingen ingest", r"agreement \1 has status \2 – no ingest"),
    (r"inget kontraktsavtal (\S+) finns hos stadens EDC-connector – ingen auktorisation utfärdas",
     r"no contract agreement \1 exists at the city's EDC connector – no authorisation is issued"),
    (r"inget kontraktsavtal (\S+) finns hos stadens EDC-connector – utan avtal ingen åtkomst till Distribution A",
     r"no contract agreement \1 exists at the city's EDC connector – without an agreement there is no access to Distribution A"),
    (r"leveransen saknar Authorization-header – ingen engångsauktorisation, ingen ingest",
     "the delivery has no Authorization header – no one-time authorisation, no ingest"),
    (r"okänd eller redan förbrukad engångsauktorisation", "unknown or already used one-time authorisation"),
    (r"engångsauktorisationen är redan förbrukad", "the one-time authorisation has already been used"),
    (r"engångsauktorisationen har gått ut", "the one-time authorisation has expired"),
    (r"nyttolasten gick inte att tolka som JSON", "the payload could not be parsed as JSON"),
    (r"nyttolasten är inte ett JSON-objekt", "the payload is not a JSON object"),
    (r"kuvertet saknar fält: ", "the envelope is missing fields: "),
    (r"förväntade dataprodukten '(.*?)', fick '(.*?)'", r"expected the data product '\1', got '\2'"),
    (r"okänd distribution '(.*?)'", r"unknown distribution '\1'"),
    (r"leveransen innehåller inga poster", "the delivery contains no records"),
    (r"avtalet gäller Distribution (\w+) men leveransen bär Distribution (\w+)", r"the agreement covers Distribution \1 but the delivery carries Distribution \2"),
    (r"en post är inte ett objekt", "a record is not an object"),
    (r"AVTALSBROTT: Distribution B innehåller brunns-GIS \((.*?)\) i (\d+) av (\d+) poster – leveransen avvisas i sin helhet",
     r"BREACH OF CONTRACT: Distribution B contains well GIS (\1) in \2 of \3 records – the delivery is rejected as a whole"),
    (r"schemat avviker från dataproduktavtalet i (\d+) av (\d+) poster \(omdöpta eller uteblivna fält\)",
     r"the schema deviates from the data product agreement in \1 of \2 records (renamed or missing fields)"),
    (r"(\S+) bär ((?:location|sourceSrs)(?:, \w+)*)", r"\1 carries \2"),
    (r"kunde inte skriva till orion-stad: ", "could not write to orion-stad: "),
    (r"kunde inte nå stadens EDC \((.*?)\): ", r"could not reach the city's EDC (\1): "),
    (r"contractAgreementId måste anges", "contractAgreementId must be given"),
    (r"avtalet gäller assetet '(.*?)', som inte är någon känd distribution av dataprodukten",
     r"the agreement covers the asset '\1', which is not a known distribution of the data product"),
    (r"avtalet (\S+) har hävts av Kretslopp och Vatten – nyckeln kan inte längre användas för att hämta data",
     r"agreement \1 has been revoked by Kretslopp och Vatten – the key can no longer be used to fetch data"),
    (r"avtalets giltighetstid har gått ut \(avtal (\S+)\) – nyckeln kan inte längre användas för att hämta data",
     r"the agreement's validity period has ended (agreement \1) – the key can no longer be used to fetch data"),
    (r"avtalets status kunde inte bekräftas – åtkomst nekas", "the agreement's status could not be confirmed – access is refused"),
    (r"okänd åtkomsttoken", "unknown access token"),
    (r"åtkomsttoken har gått ut", "the access token has expired"),
    (r"kroppen är inte giltig JSON", "the body is not valid JSON"),
    (r"kunde inte nå orion-stad", "could not reach orion-stad"),
    # ---- providerns KoV-API (Java: KovController, KovIdentitetsverifiering) --------------------
    (r"Authorization-header saknas – ett godkänn-/avslå-anrop måste bära ett self-issued DCP-token som bevisar avsändarens (\w+)\.",
     r"Authorization header missing – an approve/reject call must carry a self-issued DCP token proving the sender's \1."),
    (r"DCP-verifiering av avsändarens token misslyckades: ", "DCP verification of the sender's token failed: "),
    (r"Verifieringen lyckades men gav inga attest alls – inget (\w+) kunde hittas\.",
     r"Verification succeeded but returned no credentials at all – no \1 could be found."),
    (r"Avsändaren presenterade inget verifierat (\w+) – ett giltigt self-issued token räcker inte, KoV-beslut kräver ett attest för Data Rights Holder-rollen\.",
     r"The sender presented no verified \1 – a valid self-issued token is not enough, a KoV decision requires a credential for the Data Rights Holder role."),
    (r"Avsändarens verifierade roll är '(.*?)', men KoV-gaten kräver '(.*?)'\.", r"The sender's verified role is '\1', but the KoV gate requires '\2'."),
    (r"Ingen förhandling med id (\S+)", r"No negotiation with id \1"),
    (r"Förhandling (\S+) är av typen (\w+) – KoV-beslut ges bara på provider-sidan \(hård regel 7\)\.",
     r"Negotiation \1 is of type \2 – KoV decisions are only given on the provider side (hard rule 7)."),
    (r"Förhandling (\S+) om (\S+) bär ingen svada:kovGodkannande-obligation – den kräver inget Data Rights Holder-beslut\.",
     r"Negotiation \1 for \2 carries no svada:kovGodkannande obligation – it requires no Data Rights Holder decision."),
    (r"Förhandling (\S+) är redan avgjord \((.*?)\) – ett KoV-beslut kan inte ändras eller upprepas\.",
     r"Negotiation \1 has already been decided (\2) – a KoV decision cannot be changed or repeated."),
    (r"Förhandlingen bearbetas just nu av statsmaskinen, försök igen: ", "The negotiation is being processed by the state machine right now, try again: "),
    (r"Inget avtal med id (\S+)", r"No agreement with id \1"),
    (r"Avtal (\S+) om (\S+) bär ingen svada:kovGodkannande-obligation – det är inte KoV:s att häva\.",
     r"Agreement \1 for \2 carries no svada:kovGodkannande obligation – it is not for KoV to revoke."),
    # ---- fcf-sim ----------------------------------------------------------------------
    (r"AVTALSBROTT: lägger tillbaka brunns-GIS \(location, sourceSrs\) i Distribution B",
     "BREACH OF CONTRACT: puts the chambers' GIS (location, sourceSrs) back into Distribution B"),
    (r"döper om ", "renames "),
    (r"tar bort ", "removes "),
    (r"okänd distribution: (.*?) \(a eller b\)", r"unknown distribution: \1 (a or b)"),
    (r"okänd batch: ", "unknown batch: "),
    (r"ingen batch producerad ännu – försök igen om en stund", "no batch produced yet – try again in a moment"),
    (r"okända lägen: ", "unknown modes: "),
    # ---- kontrollrummets egna fel ----------------------------------------------------------
    (r"beslut måste vara godkann eller avsla", "decision must be godkann or avsla"),
    (r"mottagare måste vara dhi eller stad och åtgärd aterkalla eller aterinsatt",
     "recipient must be dhi or stad and action aterkalla or aterinsatt"),
    (r"inte pollad ännu", "not polled yet"),
    (r"oväntat svar från stadens plattform: ", "unexpected response from the city's platform: "),
    (r"gatewayen gav ingen nyckel: ", "the gateway gave no key: "),
    (r"inga brunnar i stadens plattform ännu – kör steg (\d) först", r"no chambers in the city's platform yet – run step \1 first"),
    (r"STS gav HTTP (\d+) vid tokenhämtning: ", r"STS returned HTTP \1 fetching a token: "),
    (r"når inte (.*?): ", r"cannot reach \1: "),
    (r"HTTP (\d+) från (\S+): ", r"HTTP \1 from \2: "),
    (r"okänt beslut: ", "unknown decision: "),
    (r"SLÄPPTES IGENOM – gaten är inte verksam", "LET THROUGH – the gate is not effective"),
    # ---- steg 6 ------------------------------------------------------------------------
    (r"^Brunnar i stadens plattform$", "Chambers in the city's platform"),
    (r"^Brunnar som bräddar$", "Chambers overflowing"),
    (r"^Total bräddvolym \(m³\)$", "Total overflow volume (m³)"),
    (r"^Högsta bräddvolym \(m³\)$", "Highest overflow volume (m³)"),
    (r"^Gällande avtal om A$", "Current agreement for A"),
    (r"^inget$", "none"),
    (r"underlag: ", "basis: "),
    (r"(\d+) av (\d+) tidpunkter mätta, resten reservmönster", r"\1 of \2 time points measured, the rest a fallback pattern"),
    (r"alla (\d+) tidpunkter i dygnet mätta", r"all \1 time points of the day measured"),
    (r"(\d+) av (\d+) dygnspositioner mätta, resten reservmönster", r"\1 of \2 daily positions measured, the rest a fallback pattern"),
    (r"internt basmönster \(endast (\d+) mätpunkter i fönstret\)", r"internal base pattern (only \1 measurement points in the window)"),
    (r"(\d+) entiteter i (\S+)", r"\1 entities in \2"),
    (r"\buse \(endast Göteborgs Stad\)", "use (only the City of Gothenburg)"),
    (r"\bGöteborgs Stad\b", "City of Gothenburg"),
    (r"obligation: godkännande av Kretslopp och Vatten", "obligation: approval by Kretslopp och Vatten"),
    (r"Modellerad bräddata", "Modelled overflow data"),
    (r"\bGODKAND\b", "APPROVED"),
    (r"\bAVSLAGEN\b", "REJECTED"),
    (r"\bVANTANDE\b", "WAITING"),
    # ---- koder och orsaksnamn som står inne i en mening (visning; nycklarna är oförändrade) ----
    (r"\bAUKTORISATION-NEKAD\b", "AUTHORISATION-REFUSED"),
    (r"\bAUKTORISERAD\b", "AUTHORISED"),
    (r"\bAVVISAD\b(?= \()", "REJECTED"),
    (r"\bUTGANGET\b", "EXPIRED"),
    (r"\bHAVT\b", "REVOKED"),
    (r"\bGALLANDE\b", "VALID"),
    (r"\bOKAND\b", "UNKNOWN"),
    (r"\bbrunns-gis-i-distribution-b\b(?! \()", "brunns-gis-i-distribution-b (well-gis-in-distribution-b)"),
    (r"\bschema-avviker\b(?! \()", "schema-avviker (schema-mismatch)"),
    (r"\btoken-forbrukad\b(?! \()", "token-forbrukad (token-used)"),
    (r"\bkuvert-ofullstandigt\b(?! \()", "kuvert-ofullstandigt (envelope-incomplete)"),
    (r"\bokand-token\b(?! \()", "okand-token (unknown-token)"),
    (r"\bauktorisation-saknas\b(?! \()", "auktorisation-saknas (authorisation-missing)"),
    (r"\bdistribution-matchar-inte-avtalet\b(?! \()", "distribution-matchar-inte-avtalet (distribution-mismatch)"),
    (r"\bnyttolast-ogiltig\b(?! \()", "nyttolast-ogiltig (payload-invalid)"),
]
_KOMPILERADE = [(re.compile(m), e) for m, e in _REGLER]

# Nycklar vars värden är data eller identifierare och aldrig ska översättas.
_HOPPA_NYCKLAR = {"orsak", "p", "parametrar", "resultat", "detaljer", "raPolicy", "policy", "json", "katalog", "id", "tid", "namn", "weirName", "recipient", "innehall", "kalla", "resultat", "status",
                  "state", "tillstand", "kovBeslut", "atgard", "typ", "api"}


# En sträng utan svenska tecken eller ord behöver inte gå igenom reglerna.
_SVENSKT = re.compile(r"[åäöÅÄÖ]|\b(?:och|att|som|inte|för|med|ett|på|till|kan|från|eller|har|ska|när|efter|"
                      r"stadens?|avtal\w*|ingen|inget|finns|väntar|förhandl\w*|överföring|nekas|hävt|"
                      r"[A-ZÅÄÖ]{3,})\b")


@functools.lru_cache(maxsize=8192)
def _oversatt_cachad(text):
    ut = text
    for monster, ersattning in _KOMPILERADE:
        ut = monster.sub(ersattning, ut)
    return ut


def oversatt(text):
    """Översätter kända svenska meningar i en sträng till engelska; allt annat lämnas orört."""
    if not isinstance(text, str) or not text.strip() or not _SVENSKT.search(text):
        return text
    return _oversatt_cachad(text)


def kod(visa):
    """Visningsnamn för en svensk statuskod på engelska (okända koder oförändrade)."""
    return KODER.get(visa, visa)


def oversatt_struktur(nod, nyckel=None):
    """Går igenom ett JSON-träd och översätter textvärden, utom data (se _HOPPA_NYCKLAR)."""
    if isinstance(nod, dict):
        # Delträd under en nyckel i _HOPPA_NYCKLAR är data (jobbets resultat, katalogen, policyn): lämnas orörda.
        return {k: (v if k in _HOPPA_NYCKLAR else oversatt_struktur(v, k)) for k, v in nod.items()}
    if isinstance(nod, list):
        return [oversatt_struktur(v, nyckel) for v in nod]
    if isinstance(nod, str) and nyckel not in _HOPPA_NYCKLAR:
        return oversatt(nod)
    return nod
