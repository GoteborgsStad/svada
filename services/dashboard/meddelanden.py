#!/usr/bin/env python3
"""Meddelandekatalogen: händelser lagras som KOD + PARAMETRAR, texten skapas vid visning.

KONCEPT: docs/koncept/C6-drift-och-uthallighet.md (språk i kontrollrummet)

Varför
------
En loggrad som lagras som svensk text är språkberoende: den kan inte visas på engelska utan att
gissa sig tillbaka till meningen, och den ändras om man ändrar formuleringen. Här lagras i stället
`{"kod": "kov.godkand", "p": {"dist": "A"}}`. Katalogen nedan har en svensk och en engelsk mall per
kod, och `visa()` fyller i parametrarna på det språk läsaren valt. Konsekvenser:

* **Hashkedjan** i auditloggen räknas över kod och parametrar, inte över text. Samma händelse ger
  samma hash oavsett vilket språk någon tittar på.
* **Tjänsterna** (ingest, gateway, fcf-sim, providerns KoV-API) skickar `kod` och `parametrar` i sina
  felsvar och loggposter. De behåller sin svenska `detalj` för den som anropar dem direkt, men
  kontrollrummet visar katalogens text.
* Texten som inte har någon kod (`fri`) visas som den är på svenska och går via den äldre
  översättaren (`i18n.py`) på engelska. Ett test (`tests/engelska_enhet.py`) larmar när något
  fortfarande går den vägen.

Tre slags innehåll (beslut 2026-10-11)
--------------------------------------
* **Formell text** (avtalsklausuler, obligationer, roller, villkorstexter i katalogen) är engelsk i
  båda vyerna och översätts inte.
* **Löptext och beskrivningar** (loggrader, felmeddelanden, förklaringar) skapas här, på vyns språk.
* **Data** (brunns- och vattendragsnamn, id:n, titlar i datat) visas som de är.

Mallsyntax: `{namn}` fylls i; `{namn|kod}` visar en statuskod med engelskt visningsnamn,
`{namn|orsak}` ett orsaksnamn, `{namn|lista}` en lista som kommaseparerad text. Ett värde kan vara
ett inbäddat meddelande `{"kod": …, "p": …}` (renderas på samma språk) eller `{"fri": text}`.
"""

import re

import i18n

KATALOG = {
    # ---- åtgärdernas rubriker (jobb) ---------------------------------------------------------
    "atgard.kor-batch": {"sv": "Kör en FCF-batch", "en": "Run an FCF batch"},
    "atgard.hamta-katalog": {"sv": "Hämta DSP-katalogen", "en": "Fetch the DSP catalogue"},
    "atgard.forhandla-b": {"sv": "Förhandla Distribution B", "en": "Negotiate Distribution B"},
    "atgard.forhandla-a": {"sv": "Förhandla Distribution A", "en": "Negotiate Distribution A"},
    "atgard.transfer-b": {"sv": "Leverera B (kör transfer)", "en": "Deliver B (run transfer)"},
    "atgard.transfer-a": {"sv": "Leverera A (kör transfer)", "en": "Deliver A (run transfer)"},
    "atgard.kov-godkann": {"sv": "KoV GODKÄNNER Distribution A", "en": "KoV APPROVES Distribution A"},
    "atgard.kov-avsla": {"sv": "KoV AVSLÅR Distribution A", "en": "KoV REJECTS Distribution A"},
    "atgard.kov-hav": {"sv": "KoV HÄVER avtalet om Distribution A",
                       "en": "KoV REVOKES the agreement for Distribution A"},

    # ---- jobbloggen --------------------------------------------------------------------------
    "jobb.start": {"sv": "startar: {etikett}", "en": "starting: {etikett}"},
    "jobb.batch": {"sv": "FCF producerade batch {batch} för modellerat dygn {dygn} ({antal} poster)",
                   "en": "FCF produced batch {batch} for modelled day {dygn} ({antal} records)"},
    "jobb.underlag": {"sv": "underlag: {kalla}", "en": "basis: {kalla}"},
    "jobb.katalograd": {"sv": "{asset} – {namn} ({klass}, {atkomst}): {villkor}",
                        "en": "{asset} – {namn} ({klass}, {atkomst}): {villkor}"},
    "jobb.forh_startad": {"sv": "förhandling {id} startad om Distribution {dist}",
                          "en": "negotiation {id} started for Distribution {dist}"},
    "jobb.vantar_avtal": {"sv": "väntar (högst {sek} s) på att DHI slutför avtalet; är DHI utestängd av samordnaren slutförs det inte",
                          "en": "waiting (at most {sek} s) for DHI to complete the agreement; if DHI is excluded by the coordinator it will not complete"},
    "jobb.a_kraver_kov": {
        "sv": "Distribution A kräver KoV-godkännande – förhandlingen väntar hos PROVIDERN (DHI:s connector), "
              "eftersom spärren sitter hos den som lämnar ut data. Väntar (högst {sek} s) på att förhandlingen "
              "dyker upp i kön.",
        "en": "Distribution A requires KoV approval – the negotiation waits at the PROVIDER (DHI's connector), "
              "because the barrier sits with whoever releases the data. Waiting (at most {sek} s) for the "
              "negotiation to appear in the queue."},
    "jobb.kon": {"sv": "providerns kö: id={id} förhandlingstillstånd={tillstand}, KoV-beslut: {beslut|kod}",
                 "en": "provider queue: id={id} negotiation state={tillstand}, KoV decision: {beslut|kod}"},
    "jobb.kov_panel": {"sv": "Använd KoV-panelen för att godkänna eller avslå.",
                       "en": "Use the KoV panel to approve or reject."},
    "jobb.avtal": {"sv": "avtal {avtal} (tillstånd {tillstand})", "en": "agreement {avtal} (state {tillstand})"},
    "jobb.inget_avtal": {"sv": "inget avtal ännu (tillstånd {tillstand})",
                         "en": "no agreement yet (state {tillstand})"},
    "jobb.inget_avtal_utestangd": {
        "sv": "Orsak: {delar|deltagare} är utestängd av samordnaren (medlemsintyget återkallat), så förhandlingen kan inte "
              "slutföras. Släpp in parten igen i rutan högst upp i steg 3.",
        "en": "Cause: {delar|deltagare} is excluded by the coordinator (membership credential revoked), so the negotiation "
              "cannot complete. Let the party back in using the box at the top of step 3."},
    "jobb.anvander_avtal": {"sv": "använder avtal {avtal} (förhandling {forh})",
                            "en": "using agreement {avtal} (negotiation {forh})"},
    "jobb.kov_beslut": {
        "sv": "KoV-beslut ({beslut|kod}) registrerat hos PROVIDERN: förhandlingstillstånd={tillstand}",
        "en": "KoV decision ({beslut|kod}) registered at the PROVIDER: negotiation state={tillstand}"},
    "jobb.avslag_havde": {
        "sv": "Så fungerar PoC:en: ett avslag av en ny begäran om A häver tidigare avtal för samma tillgång "
              "och part. Hävt hos DHI (DHI:s eget id för avtalet, ett annat än stadens): {havda|lista}",
        "en": "How the PoC works: a rejection of a new request for A revokes earlier agreements for the same "
              "asset and party. Revoked at DHI: {havda|lista}"},
    "jobb.avslag_havde_inget": {
        "sv": "Avslaget häver inget avtal (regeln är avstängd i den delade demon, eller så fanns inget gällande avtal).",
        "en": "The rejection revokes no agreement (the rule is off in the shared demo, or there was no current agreement)."},
    "jobb.id_skiljer": {
        "sv": "stadens förhandling {stad_forh} fick avtal {avtal} ({tillstand}). DHI:s förhandling är {dhi_forh} "
              "och DHI:s eget avtals-id {dhi_avtal} – ids skiljer sig mellan connectorerna.",
        "en": "the city's negotiation {stad_forh} got agreement {avtal} ({tillstand}). DHI's negotiation is "
              "{dhi_forh} and DHI's own agreement id is {dhi_avtal} – the ids differ between the connectors."},
    "jobb.consumer_forh": {"sv": "consumerns förhandling {id} är {tillstand}",
                           "en": "the consumer's negotiation {id} is {tillstand}"},
    "jobb.kov_havt": {
        "sv": "KoV har hävt avtal {avtal} hos DHI. Avtalet gällde tills det hävdes; nya överföringar och nya "
              "åtkomstnycklar nekas.",
        "en": "KoV has revoked agreement {avtal} at DHI. The agreement was valid until it was revoked; new "
              "transfers and new access keys are refused."},
    "jobb.register_havt": {
        "sv": "stadens avtalsregister ser avtalet {avtal} som HÄVT (synkas från DHI ungefär varje sekund)",
        "en": "the city's agreement register sees agreement {avtal} as REVOKED (synced from DHI about every "
              "second)"},
    "jobb.register_ej_synkat": {"sv": "stadens avtalsregister har ännu inte hunnit synka hävningen",
                                "en": "the city's agreement register has not yet synced the revocation"},
    "jobb.avslag_orsak": {
        "sv": "Förhandlingen är avslutad utan avtal. DHI:s orsak: \"{orsak}\" Staden har inget avtal om A, så "
              "Leverera A nekas tills KoV godkänner en ny begäran.",
        "en": "The negotiation has ended without an agreement. DHI's reason: \"{orsak}\" The city has no "
              "agreement for A, so Deliver A is refused until KoV approves a new request."},
    "jobb.avslag_orsak_avtal_galler": {
        "sv": "Förhandlingen är avslutad utan nytt avtal. DHI:s orsak: \"{orsak}\" Ditt tidigare avtal om A gäller fortfarande "
              "(avslaget häver inget i den delade demon), så Leverera A fungerar som förut.",
        "en": "The negotiation has ended without a new agreement. DHI's reason: \"{orsak}\" Your earlier agreement for A is "
              "still valid (a rejection revokes nothing in the shared demo), so Deliver A works as before."},
    "jobb.felinjektion_pa": {"sv": "Ditt felinjektionsläge slås på bara under den här leveransen: {lagen}.",
                             "en": "Your fault-injection mode is switched on only during this delivery: {lagen}."},
    "jobb.felinjektion_av": {"sv": "Felinjektionen är avslagen igen. Ingen annan besökare påverkades.",
                             "en": "The fault injection is off again. No other visitor was affected."},
    "jobb.felinjektion_kvar": {"sv": "Varning: felinjektionen kunde inte slås av direkt ({fel}); städningen slår av den.",
                               "en": "Warning: the fault injection could not be switched off right away ({fel}); the cleanup switches it off."},
    "jobb.misslyckades": {"sv": "MISSLYCKADES: {orsak}", "en": "FAILED: {orsak}"},
    "jobb.nekad": {"sv": "NEKAD av spärren: {orsak}", "en": "REFUSED by the safeguard: {orsak}"},
    "jobb.nekad_inget_avtal": {"sv": "NEKAD, inget gällande avtal: {orsak}",
                               "en": "REFUSED, no valid agreement: {orsak}"},
    "jobb.ovantat": {"sv": "OVÄNTAT FEL: {typ}: {text}", "en": "UNEXPECTED ERROR: {typ}: {text}"},

    # ---- fel som stoppar ett jobb ---------------------------------------------------------------
    "fel.inget_avtal": {"sv": "det finns inget kontraktsavtal för Distribution {dist} – kör steg {steg} först",
                        "en": "there is no contract agreement for Distribution {dist} – run step {steg} first"},
    "fel.inget_avtal_kov": {
        "sv": "det finns inget kontraktsavtal för Distribution {dist} – kör steg {steg} först (och låt KoV godkänna)",
        "en": "there is no contract agreement for Distribution {dist} – run step {steg} first (and let KoV approve)"},
    "fel.avtal_utgangit": {
        "sv": "avtalet {avtal} har gått ut (giltighetstiden är slut). Förhandla A på nytt och låt KoV godkänna "
              "för att få ett nytt avtal",
        "en": "agreement {avtal} has expired (the validity period is over). Negotiate A again and let KoV "
              "approve to get a new agreement"},
    "fel.avtal_havt": {
        "sv": "avtalet {avtal} är hävt av KoV – ett avtal gäller tills det hävs. Förhandla A på nytt och låt KoV "
              "godkänna för att få ett nytt avtal",
        "en": "agreement {avtal} has been revoked by KoV – an agreement is valid until it is revoked. Negotiate "
              "A again and let KoV approve to get a new agreement"},
    "fel.okand_atgard": {"sv": "okänd åtgärd: {atgard}", "en": "unknown action: {atgard}"},
    "fel.annat_ursprung": {"sv": "anropet måste komma från kontrollrummets egen sida",
                           "en": "the request must come from the control room's own page"},
    "fel.vanta": {"sv": "vänta {sek} s – du körde just ett jobb, så att andra besökare också hinner före",
                  "en": "wait {sek} s – you just ran a job, so other visitors get their turn"},
    "fel.kropp_stor": {"sv": "anropets kropp är för stor – inget har gjorts",
                       "en": "the request body is too large – nothing was done"},
    "fel.kropp_avbruten": {"sv": "anropets kropp kunde inte läsas (avbruten) – inget har gjorts",
                           "en": "the request body could not be read (interrupted) – nothing was done"},
    "fel.kropp_ogiltig": {"sv": "anropets kropp måste vara ett JSON-objekt – inget har gjorts",
                          "en": "the request body must be a JSON object – nothing was done"},
    "fel.felinj_argument": {"sv": "felinjektionen tar ett JSON-objekt med läge:sant/falskt (schemadrift, saknade_parametrar, gis_i_b)",
                            "en": "fault injection takes a JSON object with mode:true/false (schemadrift, saknade_parametrar, gis_i_b)"},
    "fel.avkylning": {"sv": "Felinjektionen har just slagits av. Vänta {sek} s innan den slås på igen, så att demon hinner återhämta sig.",
                      "en": "Fault injection has just been switched off. Wait {sek} s before switching it on again so the demo can recover."},
    "fel.avkylning_ute": {"sv": "Medlemsintyget för {part|deltagare} har just satts in igen. Vänta {sek} s innan {part|deltagare} stängs ute på nytt, så att demon hinner återhämta sig.",
                          "en": "The membership credential for {part|deltagare} has just been restored. Wait {sek} s before excluding {part|deltagare} again so the demo can recover."},
    "fel.stad_nekad_dhi": {"sv": "Staden nekas av DHI (401): DHI godtar inte stadens medlemsintyg. Staden måste släppas in igen av samordnaren innan det går att förhandla.",
                           "en": "The city is refused by DHI (401): DHI does not accept the city's membership credential. The city must be let back in by the coordinator before it can negotiate."},
    "fel.jobb_argument": {"sv": "åtgärden {atgard} kräver ett giltigt id", "en": "the action {atgard} requires a valid id"},
    "fel.upptaget": {"sv": "ett jobb kör redan – kedjan körs ett steg i taget",
                     "en": "a job is already running – the chain runs one step at a time"},
    "fel.okant_jobb": {"sv": "okänt jobb", "en": "unknown job"},
    "fel.okand_handelse": {"sv": "okänd händelse", "en": "unknown event"},
    "fel.inte_din_forhandling": {"sv": "Den här förhandlingen är inte din: du kan bara fatta beslut om förhandlingar du själv har startat.",
                                 "en": "This negotiation is not yours: you can only decide on negotiations you started yourself."},
    "fel.inte_ditt_avtal": {"sv": "Det här avtalet är inte ditt: du kan bara häva avtal som kom ur dina egna förhandlingar.",
                            "en": "This agreement is not yours: you can only revoke agreements that came from your own negotiations."},
    "fel.kon_full": {"sv": "Demon är full just nu: för många väntar på sin tur. Försök igen om en stund.",
                     "en": "The demo is full right now: too many are waiting for their turn. Try again in a moment."},
    "fel.utestangning_avstangd": {"sv": "Utestängningen är avstängd i den publika demon: den skulle stänga ute alla besökare samtidigt. Den fungerar, och visas som ett inspelat exempel i steg 3.",
                                  "en": "Exclusion is switched off in the public demo: it would exclude all visitors at the same time. It works, and is shown as a recorded example in step 3."},
    "fel.beslut": {"sv": "beslut måste vara godkann eller avsla", "en": "decision must be godkann or avsla"},
    "fel.svada_argument": {
        "sv": "mottagare måste vara dhi eller stad och åtgärd aterkalla eller aterinsatt",
        "en": "recipient must be dhi or stad and action aterkalla or aterinsatt"},

    # ---- kedjan (kedjan.py) ----------------------------------------------------------------
    "kedja.auktorisation": {"sv": "engångsauktorisation utfärdad mot avtal {avtal}",
                            "en": "one-time authorisation issued against agreement {avtal}"},
    "kedja.transfer_startad": {"sv": "transferprocess {tp} startad ({typ})",
                               "en": "transfer process {tp} started ({typ})"},
    "kedja.transfer_tillstand": {"sv": "transferprocessen är {tillstand}",
                                 "en": "the transfer process is {tillstand}"},
    "kedja.forsok": {
        "sv": "försök {n}: pushen nådde aldrig ingest (EDC-dataplanets 'IOException: closed') – gör om om {sek} s",
        "en": "attempt {n}: the push never reached ingest (the EDC data plane's 'IOException: closed') – "
              "retrying in {sek} s"},
    "kedja.kvitterad": {"sv": "ingest KVITTERADE: {detalj}", "en": "ingest ACKNOWLEDGED: {detalj}"},
    "kedja.avvisad": {"sv": "ingest AVVISADE leveransen: {orsak|orsak} – {detalj}",
                      "en": "ingest REJECTED the delivery: {orsak|orsak} – {detalj}"},
    "kedja.exempel": {"sv": "exempel ur avvisningen: {exempel}", "en": "example from the rejection: {exempel}"},
    "kedja.motivering_forbud": {
        "sv": "ODRL-offerten för {asset} förbjuder {forbud|lista}. Det är avtalsvillkor som mottagaren "
              "förbinder sig till.",
        "en": "The ODRL offer for {asset} prohibits {forbud|lista}. These are contract terms the recipient "
              "commits to."},
    "kedja.motivering_skyldighet": {
        "sv": "Offerten bär dessutom skyldigheten {skyldigheter|lista} – Data Rights Holder (Kretslopp och "
              "Vatten) måste godkänna varje utlämning, och ett sådant godkännande avser stadens EGET bruk, aldrig "
              "vidare publicering.",
        "en": "The offer also carries the obligation {skyldigheter|lista} – the Data Rights Holder (Kretslopp "
              "och Vatten) must approve each release, and such an approval covers the city's OWN use, never "
              "onward publication."},
    "kedja.motivering_klass": {
        "sv": "Distribution A är informationsklassad {klass} med accessRights={access}.",
        "en": "Distribution A is classified {klass} with accessRights={access}."},

    # ---- fel från anrop (KallFel) -----------------------------------------------------------
    "kallfel.http": {"sv": "HTTP {http} från {url}: {svar}", "en": "HTTP {http} from {url}: {svar}"},
    "kallfel.startar_om": {"sv": "Connectorn är inte färdigstartad (HTTP {http}). Försök igen om en stund.",
                           "en": "The connector has not finished starting (HTTP {http}). Try again in a moment."},
    "kallfel.nar_inte": {"sv": "når inte {url}: {orsak}", "en": "cannot reach {url}: {orsak}"},
    "kallfel.sts_http": {"sv": "STS gav HTTP {http} vid tokenhämtning: {svar}",
                         "en": "STS returned HTTP {http} fetching a token: {svar}"},
    "kallfel.sts_nar": {"sv": "når inte Stadens STS ({url}): {orsak}",
                        "en": "cannot reach the city's STS ({url}): {orsak}"},
    "kallfel.okant_beslut": {"sv": "okänt beslut: {beslut}", "en": "unknown decision: {beslut}"},
    "kallfel.asset_saknas": {"sv": "assetet {asset} finns inte i DSP-katalogen (kör registrera-edc?)",
                             "en": "the asset {asset} is not in the DSP catalogue (run registrera-edc?)"},
    "kallfel.offert_saknas": {"sv": "assetet {asset} saknar ODRL-offert",
                              "en": "the asset {asset} has no ODRL offer"},
    "kallfel.ingen_forhandling": {"sv": "ingen förhandling skapades: {svar}",
                                  "en": "no negotiation was created: {svar}"},
    "kallfel.ingen_transfer": {"sv": "ingen transferprocess skapades: {svar}",
                               "en": "no transfer process was created: {svar}"},
    "kallfel.ingest_vagrade": {"sv": "ingest vägrade utfärda auktorisation för {avtal}",
                               "en": "ingest refused to issue an authorisation for {avtal}"},
    "kallfel.inget_kvitto": {"sv": "transfern gav inget ingest-kvitto efter tre försök",
                             "en": "the transfer gave no ingest receipt after three attempts"},
    "kallfel.analys_svar": {"sv": "oväntat svar från stadens plattform: {svar}",
                            "en": "unexpected response from the city's platform: {svar}"},
    "kallfel.analys_nyckel": {"sv": "gatewayen gav ingen nyckel: {svar}", "en": "the gateway gave no key: {svar}"},
    "kallfel.inga_brunnar": {"sv": "inga brunnar i stadens plattform ännu – kör steg {steg} först",
                             "en": "no chambers in the city's platform yet – run step {steg} first"},
    "kallfel.inte_dist_b": {"sv": "senaste leveransen är inte distribution B",
                            "en": "the latest delivery is not distribution B"},
    "kallfel.avtal_inte_b": {"sv": "avtalet gäller inte distribution B",
                             "en": "the agreement does not cover distribution B"},
    "kallfel.avtal_a_havt": {"sv": "SLÄPPTES IGENOM – gaten är inte verksam",
                             "en": "LET THROUGH – the gate is not effective"},

    # ---- auditloggen -----------------------------------------------------------------------
    "audit.forhandling": {"sv": "Förhandling om Distribution {dist} ({asset}) påbörjad",
                          "en": "Negotiation for Distribution {dist} ({asset}) started"},
    "audit.kov_vantar": {
        "sv": "VÄNTAR på Data Rights Holder-beslut (Kretslopp och Vatten) för Distribution A",
        "en": "WAITING for a Data Rights Holder decision (Kretslopp och Vatten) on Distribution A"},
    "audit.kov_godkand": {"sv": "KoV GODKÄNDE utlämning av Distribution A",
                          "en": "KoV APPROVED the release of Distribution A"},
    "audit.kov_godkand_roll": {"sv": "KoV GODKÄNDE utlämning av Distribution A (verifierad roll: {roll})",
                               "en": "KoV APPROVED the release of Distribution A (verified role: {roll|roll})"},
    "audit.kov_avslagen": {"sv": "KoV AVSLOG begäran om Distribution A",
                           "en": "KoV REJECTED the request for Distribution A"},
    "audit.kov_avslagen_roll": {"sv": "KoV AVSLOG begäran om Distribution A (verifierad roll: {roll})",
                                "en": "KoV REJECTED the request for Distribution A (verified role: {roll|roll})"},
    "audit.kov_annat": {"sv": "KoV-gate: {beslut}", "en": "KoV gate: {beslut|kod}"},
    "audit.orsak_avslag": {"sv": "ett avslag av en ny begäran (PoC-regel)",
                           "en": "a rejection of a new request (PoC rule)"},
    "audit.orsak_explicit": {"sv": "KoV häver direkt", "en": "KoV revoked directly"},
    "audit.avtal_havt": {"sv": "KoV HÄVDE avtalet om Distribution {dist}: {orsak}",
                         "en": "KoV REVOKED the agreement for Distribution {dist}: {orsak}"},
    "audit.avtal_havt_roll": {
        "sv": "KoV HÄVDE avtalet om Distribution {dist}: {orsak} (verifierad roll: {roll})",
        "en": "KoV REVOKED the agreement for Distribution {dist}: {orsak} (verified role: {roll|roll})"},
    "audit.transfer": {"sv": "Transfer av Distribution {dist} ({typ}) är {tillstand}",
                       "en": "Transfer of Distribution {dist} ({typ}) is {tillstand}"},
    "audit.atgard_klar": {"sv": "{etikett}", "en": "{etikett}"},
    "audit.atgard_fel": {"sv": "{etikett}: {orsak}", "en": "{etikett}: {orsak}"},
    "audit.felinj_pa": {"sv": "Felinjektion i simulatorn: {lagen|lista}", "en": "Fault injection in the simulator: {lagen|lista}"},
    "audit.felinj_av": {"sv": "Felinjektion i simulatorn: avstängd", "en": "Fault injection in the simulator: off"},
    "audit.svada_aterkallat": {"sv": "Samordnaren återkallade medlemsintyget för {mottagare}: parten är utestängd",
                               "en": "The coordinator revoked the membership credential of {mottagare}: the party is excluded"},
    "audit.svada_aterinsatt": {"sv": "Samordnaren återinsatte medlemsintyget för {mottagare}: parten är med igen",
                               "en": "The coordinator reinstated the membership credential of {mottagare}: the party is back"},
    "audit.svada_automatisk": {"sv": "Medlemsintyget för {mottagare} släpptes in igen automatiskt (den publika demon låter inte en uteslutning stå kvar)",
                               "en": "The membership credential of {mottagare} was reinstated automatically (the public demo does not leave an exclusion in place)"},
    "audit.felinj_automatisk": {"sv": "Felinjektionen slogs av automatiskt (den publika demon låter den inte stå kvar)",
                                "en": "Fault injection was switched off automatically (the public demo does not leave it on)"},
    "audit.felinj_nollstalld": {"sv": "Felinjektionen nollställd", "en": "Fault injection reset"},
    "audit.ingest_avvisad": {"sv": "AVVISAD ({orsak|orsak}): {detalj}", "en": "REJECTED ({orsak|orsak}): {detalj}"},
    "audit.kallfel_forhandlingar": {"sv": "consumerns förhandlings-API: {fel}",
                                    "en": "the consumer's negotiation API: {fel}"},
    "audit.kallfel_kov": {"sv": "providerns KoV-API: {fel}", "en": "the provider's KoV API: {fel}"},
    "audit.kallfel_avtal": {"sv": "providerns avtalslista: {fel}", "en": "the provider's agreement list: {fel}"},
    "audit.kallfel_transfer": {"sv": "consumerns transfer-API: {fel}", "en": "the consumer's transfer API: {fel}"},
    "audit.kallfel_ingest": {"sv": "stadens mottagning: {fel}", "en": "the city intake: {fel}"},
    "audit.kedja_seq": {"sv": "ingen lank med seq={seq} (kedjan har just nu {antal} lankar)",
                        "en": "no link with seq={seq} (the chain currently has {antal} links)"},
    "audit.kedja_foregaende": {
        "sv": "lank {seq}:s lagrade foregaende-hash matchar inte den faktiskt foregaende lankens hash "
              "(kedjan har manipulerats eller skadats)",
        "en": "link {seq}: the stored previous hash does not match the actual previous link's hash (the chain "
              "has been tampered with or damaged)"},
    "audit.kedja_hash": {
        "sv": "lank {seq}:s lagrade hash matchar inte omrakningen fran dess kanoniska innehall "
              "(hashen har mixtrats med i efterhand)",
        "en": "link {seq}: the stored hash does not match the recomputation from its canonical content (the "
              "hash has been tampered with afterwards)"},

    # ---- stadens mottagning (ingest-service) --------------------------------------------------
    "ingest.auktoriserad": {"sv": "engångsnyckel utfärdad för Distribution {dist}",
                            "en": "one-time key issued for Distribution {dist}"},
    "ingest.levererad": {"sv": "Distribution {dist}, batch {batch} -> {entiteter} entiteter i stadens dataplattform",
                         "en": "Distribution {dist}, batch {batch} -> {entiteter} entities in the city data platform"},
    "ingest.edc_otillganglig": {"sv": "kunde inte nå stadens EDC ({url}): {fel}",
                                "en": "could not reach the city's EDC ({url}): {fel}"},
    "ingest.edc_http": {"sv": "stadens EDC svarade HTTP {http} vid avtalsuppslag",
                        "en": "the city's EDC answered HTTP {http} on agreement lookup"},
    "ingest.avtals_id_saknas": {"sv": "contractAgreementId måste anges", "en": "contractAgreementId must be given"},
    "ingest.inget_avtal": {
        "sv": "inget kontraktsavtal {avtal} finns hos stadens EDC-connector – ingen auktorisation utfärdas",
        "en": "no contract agreement {avtal} exists at the city's EDC connector – no authorisation is issued"},
    "ingest.okant_asset": {
        "sv": "avtalet gäller assetet '{asset}', som inte är någon känd distribution av dataprodukten",
        "en": "the agreement covers the asset '{asset}', which is not a known distribution of the data product"},
    "ingest.avtal_status_nyckel": {
        "sv": "avtalet {avtal} har status {status|kod} hos stadens avtalsregister – ingen nyckel utfärdas",
        "en": "agreement {avtal} has status {status|kod} in the city's agreement register – no key is issued"},
    "ingest.avtal_status_ingest": {
        "sv": "avtalet {avtal} har status {status|kod} – ingen ingest",
        "en": "agreement {avtal} has status {status|kod} – no ingest"},
    "ingest.auktorisation_saknas": {
        "sv": "leveransen saknar Authorization-header – ingen engångsauktorisation, ingen ingest",
        "en": "the delivery has no Authorization header – no one-time authorisation, no ingest"},
    "ingest.okand_token": {"sv": "okänd eller redan förbrukad engångsauktorisation",
                           "en": "unknown or already used one-time authorisation"},
    "ingest.token_forbrukad": {"sv": "engångsauktorisationen är redan förbrukad",
                               "en": "the one-time authorisation has already been used"},
    "ingest.token_utgangen": {"sv": "engångsauktorisationen har gått ut",
                              "en": "the one-time authorisation has expired"},
    "ingest.ogiltig_json": {"sv": "nyttolasten gick inte att tolka som JSON",
                            "en": "the payload could not be parsed as JSON"},
    "ingest.ogiltig_json_objekt": {"sv": "nyttolasten är inte ett JSON-objekt",
                                   "en": "the payload is not a JSON object"},
    "ingest.kuvert_ofullstandigt": {"sv": "kuvertet saknar fält: {falt|lista}",
                                    "en": "the envelope is missing fields: {falt|lista}"},
    "ingest.fel_dataprodukt": {"sv": "förväntade dataprodukten '{forvantad}', fick '{fick}'",
                               "en": "expected the data product '{forvantad}', got '{fick}'"},
    "ingest.okand_distribution": {"sv": "okänd distribution '{dist}'", "en": "unknown distribution '{dist}'"},
    "ingest.tom_leverans": {"sv": "leveransen innehåller inga poster", "en": "the delivery contains no records"},
    "ingest.distribution_matchar_inte": {
        "sv": "avtalet gäller Distribution {avtalad} men leveransen bär Distribution {levererad}",
        "en": "the agreement covers Distribution {avtalad} but the delivery carries Distribution {levererad}"},
    "ingest.ogiltig_post": {"sv": "en post är inte ett objekt", "en": "a record is not an object"},
    "ingest.gis_i_b": {
        "sv": "AVTALSBROTT: Distribution B innehåller brunns-GIS ({falt|lista}) i {antal} av {totalt} poster – "
              "leveransen avvisas i sin helhet",
        "en": "BREACH OF CONTRACT: Distribution B contains well GIS ({falt|lista}) in {antal} of {totalt} "
              "records – the delivery is rejected as a whole"},
    "ingest.schema_avviker": {
        "sv": "schemat avviker från dataproduktavtalet i {antal} av {totalt} poster (omdöpta eller uteblivna fält)",
        "en": "the schema deviates from the data product agreement in {antal} of {totalt} records (renamed or "
              "missing fields)"},
    "ingest.orion_skrivfel": {"sv": "kunde inte skriva till stadens dataplattform: {fel}",
                              "en": "could not write to the city data platform: {fel}"},
    "ingest.exempel_gis": {"sv": "{id} bär {falt|lista}", "en": "{id} carries {falt|lista}"},
    "ingest.exempel_saknar": {"sv": "{id} saknar {falt|lista}", "en": "{id} is missing {falt|lista}"},

    # ---- stadens gateway ---------------------------------------------------------------------------
    "gateway.edc_otillganglig": {"sv": "kunde inte nå stadens EDC ({url}): {fel}",
                                 "en": "could not reach the city's EDC ({url}): {fel}"},
    "gateway.edc_http": {"sv": "stadens EDC svarade HTTP {http} vid avtalsuppslag",
                         "en": "the city's EDC answered HTTP {http} on agreement lookup"},
    "gateway.avtals_id_saknas": {"sv": "contractAgreementId måste anges", "en": "contractAgreementId must be given"},
    "gateway.inget_avtal": {
        "sv": "inget kontraktsavtal {avtal} finns hos stadens EDC-connector – utan avtal ingen åtkomst till "
              "Distribution A",
        "en": "no contract agreement {avtal} exists at the city's EDC connector – without an agreement there is "
              "no access to Distribution A"},
    "gateway.fel_distribution": {
        "sv": "avtalet gäller assetet '{asset}'. Åtkomst till stadens CIP kräver ett avtal för Distribution A "
              "({asset_a}). Distribution B läses öppet via Mintaka och den publika vyn – ingen token behövs.",
        "en": "the agreement covers the asset '{asset}'. Access to the city's CIP requires an agreement for "
              "Distribution A ({asset_a}). Distribution B is read openly via Mintaka and the public view – no "
              "token is needed."},
    "gateway.avtal_havt": {
        "sv": "avtalet {avtal} har hävts av Kretslopp och Vatten – nyckeln kan inte längre användas för att "
              "hämta data",
        "en": "agreement {avtal} has been revoked by Kretslopp och Vatten – the key can no longer be used to "
              "fetch data"},
    "gateway.avtal_utgatt": {
        "sv": "avtalets giltighetstid har gått ut (avtal {avtal}) – nyckeln kan inte längre användas för att "
              "hämta data",
        "en": "the agreement's validity period has ended (agreement {avtal}) – the key can no longer be used "
              "to fetch data"},
    "gateway.avtal_status_okand": {"sv": "avtalets status kunde inte bekräftas – åtkomst nekas",
                                   "en": "the agreement's status could not be confirmed – access is refused"},
    "gateway.kraver_godkannande": {
        "sv": "Distribution A är non-public (informationsklass K1R1T1) och bär bräddbrunnarnas fulla GIS. "
              "Läsning kräver ett godkännande från Kretslopp och Vatten (Data Rights Holder). Växla ditt "
              "contractAgreementId mot en token på POST /auktorisation. Distribution B är öppna data och kräver "
              "ingenting – se den öppna distributionen B i katalogen.",
        "en": "Distribution A is non-public (information class K1R1T1) and carries the chambers' full GIS. "
              "Reading requires approval from Kretslopp och Vatten (Data Rights Holder). Exchange your "
              "contractAgreementId for a token at POST /auktorisation. Distribution B is open data and requires "
              "nothing – see the open distribution B in the catalogue."},
    "gateway.okand_token": {"sv": "okänd åtkomsttoken", "en": "unknown access token"},
    "gateway.token_utgangen": {"sv": "åtkomsttoken har gått ut", "en": "the access token has expired"},
    "gateway.ogiltig_json": {"sv": "kroppen är inte giltig JSON", "en": "the body is not valid JSON"},
    "gateway.cip_otillganglig": {"sv": "kunde inte nå stadens dataplattform", "en": "could not reach the city data platform"},

    # ---- fcf-sim ------------------------------------------------------------------------------
    "fcf.schemadrift": {"sv": "döper om {byten}", "en": "renames {byten}"},
    "fcf.saknade_parametrar": {"sv": "tar bort {falt|lista}", "en": "removes {falt|lista}"},
    "fcf.gis_i_b": {
        "sv": "AVTALSBROTT: lägger tillbaka brunns-GIS (location, sourceSrs) i Distribution B",
        "en": "BREACH OF CONTRACT: puts the chambers' GIS (location, sourceSrs) back into Distribution B"},

    # ---- providerns KoV-API (Java) ----------------------------------------------------------
    "kov.authorization_saknas": {
        "sv": "Authorization-header saknas – ett godkänn-/avslå-anrop måste bära ett self-issued DCP-token som "
              "bevisar avsändarens {rolltyp}.",
        "en": "Authorization header missing – an approve/reject call must carry a self-issued DCP token proving "
              "the sender's {rolltyp}."},
    "kov.dcp_misslyckades": {"sv": "DCP-verifiering av avsändarens token misslyckades: {orsak}",
                             "en": "DCP verification of the sender's token failed: {orsak}"},
    "kov.inga_attest": {"sv": "Verifieringen lyckades men gav inga attest alls – inget {rolltyp} kunde hittas.",
                        "en": "Verification succeeded but returned no credentials at all – no {rolltyp} could "
                              "be found."},
    "kov.inget_rollintyg": {
        "sv": "Avsändaren presenterade inget verifierat {rolltyp} – ett giltigt self-issued token räcker inte, "
              "KoV-beslut kräver ett attest för Data Rights Holder-rollen.",
        "en": "The sender presented no verified {rolltyp} – a valid self-issued token is not enough, a KoV "
              "decision requires a credential for the Data Rights Holder role."},
    "kov.fel_roll": {"sv": "Avsändarens verifierade roll är '{funnen}', men KoV-gaten kräver '{kravd}'.",
                     "en": "The sender's verified role is '{funnen}', but the KoV gate requires '{kravd}'."},
    "kov.ingen_forhandling": {"sv": "Ingen förhandling med id {id}", "en": "No negotiation with id {id}"},
    "kov.fel_typ": {
        "sv": "Förhandling {id} är av typen {typ} – KoV-beslut ges bara på provider-sidan (hård regel 7).",
        "en": "Negotiation {id} is of type {typ} – KoV decisions are only given on the provider side (hard "
              "rule 7)."},
    "kov.ingen_obligation": {
        "sv": "Förhandling {id} om {asset} bär ingen svada:kovGodkannande-obligation – den kräver inget Data "
              "Rights Holder-beslut.",
        "en": "Negotiation {id} for {asset} carries no svada:kovGodkannande obligation – it requires no Data "
              "Rights Holder decision."},
    "kov.redan_avgjord": {
        "sv": "Förhandling {id} är redan avgjord ({beslut}) – ett KoV-beslut kan inte ändras eller upprepas.",
        "en": "Negotiation {id} has already been decided ({beslut}) – a KoV decision cannot be changed or "
              "repeated."},
    "kov.statsmaskin": {
        "sv": "Förhandlingen bearbetas just nu av statsmaskinen, försök igen: {orsak}",
        "en": "The negotiation is being processed by the state machine right now, try again: {orsak}"},
    "kov.inget_avtal": {"sv": "Inget avtal med id {id}", "en": "No agreement with id {id}"},
    "kov.avtal_ingen_obligation": {
        "sv": "Avtal {id} om {asset} bär ingen svada:kovGodkannande-obligation – det är inte KoV:s att häva.",
        "en": "Agreement {id} for {asset} carries no svada:kovGodkannande obligation – it is not for KoV to "
              "revoke."},

    # ---- övrigt --------------------------------------------------------------------------------------
    "fri": {"sv": "{text}", "en": "{text}"},
}

# Orsaksnamn (maskinläsbara) med engelskt visningsnamn. Nycklarna ändras aldrig.
ORSAKER = {
    "brunns-gis-i-distribution-b": "well-gis-in-distribution-b",
    "schema-avviker": "schema-mismatch",
    "token-forbrukad": "token-used",
    "kuvert-ofullstandigt": "envelope-incomplete",
    "okand-token": "unknown-token",
    "token-utgangen": "token-expired",
    "auktorisation-saknas": "authorisation-missing",
    "distribution-matchar-inte-avtalet": "distribution-mismatch",
    "ogiltig-json": "invalid-json",
    "ogiltig-post": "invalid-record",
    "tom-leverans": "empty-delivery",
    "fel-dataprodukt": "wrong-data-product",
    "okand-distribution": "unknown-distribution",
    "orion-skrivfel": "orion-write-error",
    "avtal-havt": "agreement-revoked",
    "avtal-utgatt": "agreement-expired",
    "avtal-status-okand": "agreement-status-unknown",
    "inget-avtal": "no-agreement",
}

# Verifierade roller som visas i texten.
ROLLER = {"Kretslopp och Vatten – rättighetsinnehavare (dataägare)":
          "Kretslopp och Vatten – rights holder (data owner)"}

_MALL = re.compile(r"\{(\w+)(?:\|(\w+))?\}")


def msg(kod, **p):
    """Ett meddelande som lagras: kod + parametrar (språkoberoende)."""
    return {"kod": kod, "p": p}


def fri(text):
    """Ett meddelande utan kod: texten som den är (svenska), via översättaren på engelska."""
    return msg("fri", text=str(text))


def _varde(v, sprak):
    if isinstance(v, dict) and "kod" in v:
        return visa(v["kod"], v.get("p") or {}, sprak)
    if isinstance(v, dict) and "fri" in v:
        return i18n.oversatt(v["fri"]) if sprak == "en" else v["fri"]
    return v


DELTAGARE = {"dhi": ("DHI", "DHI"), "stad": ("staden", "the city")}


def _filter(namn, varde, sprak, v_ra):
    if namn == "deltagare":
        delar = v_ra if isinstance(v_ra, (list, tuple)) else [v_ra]
        i = 1 if sprak == "en" else 0
        return (" and " if sprak == "en" else " och ").join(DELTAGARE.get(str(x), (str(x), str(x)))[i] for x in delar)
    if namn == "lista":
        if isinstance(v_ra, (list, tuple)):
            return ", ".join(str(_varde(x, sprak)) for x in v_ra)
        return str(varde)
    if namn == "kod" and sprak != "en":
        return SV_KODER.get(str(varde), str(varde))     # VANTANDE -> "väntar på beslut" (utan å/ä/ö-lösa koder i svensk text)
    if sprak != "en":
        return str(varde)
    if namn == "kod":
        return i18n.kod(str(varde))
    if namn == "orsak":
        # Orsakskoden är stabil och sökbar: den svenska koden visas även på engelska, med det engelska namnet bredvid.
        return "%s (%s)" % (varde, ORSAKER[str(varde)]) if str(varde) in ORSAKER else str(varde)
    if namn == "roll":
        return ROLLER.get(str(varde), str(varde))
    return str(varde)


# Svenska visningsnamn för statuskoder (koderna själva är ASCII och används i logiken; här gäller bara texten).
SV_KODER = {
    "VANTANDE": "väntar på beslut", "GODKAND": "godkänd", "AVSLAGEN": "avslagen", "AVSLAGET": "avslaget",
    "HAVT": "hävt", "UTGANGET": "utgånget", "GALLANDE": "gällande", "OKAND": "okänd", "AVVISAD": "avvisad",
    "AVVISAT": "avvisat", "LEVERERAD": "levererad", "UTESTANGD": "utestängd", "INSATT": "insläppt", "PABORJAD": "påbörjad",
}


def visa(kod, p=None, sprak="sv"):
    """Texten för ett lagrat meddelande på önskat språk. Okänd kod -> koden i klartext."""
    p = p or {}
    if kod == "fri":
        text = str(p.get("text", ""))
        return i18n.oversatt(text) if sprak == "en" else text
    post = KATALOG.get(kod)
    if post is None:
        return "[%s] %s" % (kod, p) if p else "[%s]" % kod
    mall = post.get(sprak) or post["sv"]

    def fyll(m):
        namn, filtret = m.group(1), m.group(2)
        if namn not in p:
            return m.group(0)
        v_ra = p[namn]
        v = _varde(v_ra, sprak)
        if isinstance(v_ra, (list, tuple)) and not filtret:
            v = ", ".join(str(_varde(x, sprak)) for x in v_ra)
        return _filter(filtret, v, sprak, v_ra) if filtret else str(v)

    return _MALL.sub(fyll, mall)


def kallor_koder():
    """Alla koder i katalogen (för testerna)."""
    return sorted(KATALOG)


def parametrar_i_mall(kod, sprak):
    """Namnen på de parametrar en mall använder (för testet av att sv och en är lika)."""
    return set(m.group(1) for m in _MALL.finditer(KATALOG[kod][sprak]))


def till_sprak(nod, sprak):
    """Går igenom ett JSON-träd och byter text mot katalogens text på `sprak` där ett meddelande (kod + p) finns.

    * en dict med `kod` och `p` får sin `text` (eller `fel`) omräknad,
    * en dict med `etikettKod` får sin `etikett` omräknad.
    Allt annat lämnas orört; fri text hanteras av i18n.oversatt_struktur.
    """
    if isinstance(nod, list):
        return [till_sprak(x, sprak) for x in nod]
    if not isinstance(nod, dict):
        return nod
    ut = {k: till_sprak(v, sprak) for k, v in nod.items()}
    if isinstance(nod.get("kod"), str) and isinstance(nod.get("p"), dict):
        text = visa(nod["kod"], nod["p"], sprak)
        for nyckel in ("text", "fel"):
            if nyckel in ut:
                ut[nyckel] = text
    if isinstance(nod.get("etikettKod"), str) and "etikett" in ut:
        ut["etikett"] = visa(nod["etikettKod"], {}, sprak)
    return ut
