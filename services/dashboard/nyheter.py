"""Sidan /nyheter: vad som är nytt i vilken version av demon.

Versionen har formen ÅÅÅÅ.MM.DD-N (datum och löpnummer samma dag) och sätts på ETT ställe: SVADA_VERSION i .env. Översta posten här ska
ha samma version (provet tests/version_enhet.py kontrollerar det). En ändring av beteende eller text som en besökare kan märka ger en ny
version och en ny post överst. Testrapporter anger vilken version de provat (den står i sidfoten och i /api/status).
"""
import html
import os
import re

VERSION = os.environ.get("SVADA_VERSION", "okänd")
MONSTER = re.compile(r"^\d{4}\.\d{2}\.\d{2}-\d+$")

# Nyast överst. (version, datum, [(svenska, engelska), ...])
NYHETER = [
    ("2026.11.04-1", "2026-11-04", [
        ("Fliken Felinjektion heter nu Scenarier och har ett nytt avtalsscenario: betrodd organisation. Du kan simulera att KoV i förväg har pekat ut staden som betrodd, så att DHI:s connector skriver avtalet om A direkt utan att vänta på KoV. Avgörandet ligger kvar hos providern, och avtalet märks \"betrodd organisation, ingen KoV-prövning\" i auditloggen och på avtalssidan. Valet är ditt eget och gäller bara dina egna körningar.",
         "The Fault injection tab is now called Scenarios and has a new agreement scenario: trusted organisation. You can simulate that KoV has designated the city as trusted in advance, so that DHI's connector writes the agreement for A directly without waiting for KoV. The decision still lies with the provider, and the agreement is marked \"trusted organisation, no KoV review\" in the audit log and on the agreement page. The choice is your own and applies only to your own runs."),
        ("Källkoden är lätt att hitta: Om-fliken har en ruta med en GitHub-knapp (licensen är Apache-2.0), och varje sida har en länk till källkoden i sidfoten. Upphovet står nu med roller: Niklas Fjellman (originaluppsättning av PoC:en) och Björn Hagström (utveckling och paketering för kommunikation och begriplighet).",
         "The source code is easy to find: the About tab has a box with a GitHub button (the licence is Apache-2.0), and every page has a link to the source code in the footer. The credits now state roles: Niklas Fjellman (original setup of the PoC) and Björn Hagström (development and packaging for communication and comprehensibility)."),
        ("Avtalssidan har en språkväxlare, följer språket på sidan du kom från, och Tillbaka går till stället du kom från (till exempel steg 5) i stället för till Suveränitet.",
         "The agreement page has a language switch, follows the language of the page you came from, and Back goes to where you came from (for example step 5) instead of Sovereignty."),
        ("Den guidade banan har fått steg 5, Ursprung, före Analysera, så att du ser hur villkor, klass och avtal följer med data. Knappen Nästa landar nu på själva steget, där något händer.",
         "The guided path now includes step 5, Provenance, before Analyse, so that you see how terms, class and agreement follow the data. The Next button now lands on the step itself, where something happens."),
        ("Går det inte att hämta kartbakgrunden i steg 6 (till exempel på ett långsamt mobilnät) säger sidan det i stället för att tyst visa den schematiska kartan.",
         "If the map background in step 6 cannot be fetched (for example on a slow mobile network), the page says so instead of silently showing the schematic map."),
    ]),
    ("2026.10.29-16", "2026-11-03", [
        ("Du varnas nu innan en planerad uppdatering av demon. Markeringen uppe till höger och en remsa överst visar nedräkningen från 15 minuter före, med klockslag i din tid, och förklarar att pågående körningar avbryts men att plattformens data finns kvar. De sista två minuterna startas inga nya körningar. Brunnsvyn visar samma varsel.",
         "You are now warned before a planned update of the demo. The marker at the top right and a strip at the top show the countdown from 15 minutes before, with the time in your time zone, and explain that runs in progress are cancelled but the platform's data stays. In the last two minutes no new runs are started. The well view shows the same notice."),
    ]),
    ("2026.10.29-15", "2026-11-02", [
        ("Första gången du kommer in visas en kort ruta som förklarar att det här är en teknisk demo där kedjan körs på riktigt, att du kan låta demon guida dig med knappen Nästa, och att vi utgår från DSSC Blueprint v3.0 och bedömer oss mot OASC:s MIM:ar. Märkena visar vår egen bedömning: grön bock där vi följer och orange bock där vi följer med förbehåll. Språket går att byta direkt i rutan. Rutan öppnas igen med knappen Om demon.",
         "The first time you arrive, a short box explains that this is a technical demo where the chain runs for real, that you can let the demo guide you with the Next button, and that we take DSSC Blueprint v3.0 as our starting point and assess ourselves against OASC's MIMs. The badges show our own assessment: a green tick where we follow and an orange tick where we follow with reservations. The language can be switched right in the box. The box opens again with the About the demo button."),
        ("Ett kort nätavbrott avslutar inte längre uppföljningen av ett jobb: sidan försöker igen i stället för att tappa jobbet ur sikte.",
         "A short network interruption no longer ends the follow-up of a job: the page tries again instead of losing sight of the job."),
        ("Knappen Nästa överst på startsidan tar dig nu till stegets ruta i flödesbilden (till exempel \"Modellen (simulerad) skapar dataprodukten\") med stegets panel strax under, i stället för att landa en bit för långt ned. \"Starta den guidade banan\" i välkomstrutan visar remsan \"Prova i den här ordningen\" och lägger fokus på Nästa.",
         "The Next button at the top of the start page now takes you to the step's box in the flow picture (for example \"The model (simulated) creates the data product\") with the step's panel just below, instead of landing a bit too far down. \"Start the guided path\" in the welcome box shows the \"Try in this order\" strip and puts the focus on Next."),
        ("Startsidan har fått två egna rubriker, \"Guidad bana\" över remsan med Nästa och \"Flödet\" över bilden. Introduktionen \"Följ data från modellen till stadens beslut\" är hopfälld vid senare besök och tar då en rad; knappen \"Visa introduktionen\" öppnar den igen. MIM7 (geodata) har grön bock, eftersom MIM 9.0 inte har några numrerade krav att bedöma mot; statusraden säger det öppet.",
         "The start page now has two headings of its own, \"Guided path\" over the strip with Next and \"The flow\" over the picture. The introduction \"Follow data from the model to the city's decision\" is folded on later visits and then takes one line; the \"Show the introduction\" button opens it again. MIM7 (geospatial data) has a green tick, because MIM 9.0 has no numbered requirements to assess against; the status line says so openly."),
    ]),
    ("2026.10.29-14", "2026-11-01", [
        ("Filer som byggs vid hämtningen (kontrollrummets och brunnsvyns tabeller, JSON, zip och termlista) har nu ett tidsmärke (UTC) i namnet, så att två hämtningar går att skilja åt och webbläsaren inte ersätter en tidigare fil. Under knapparna för katalogen och deltagarregistret står varför kontrollsumman blir en annan vid varje hämtning (nya id:n och en tidpunkt i svaret).",
         "Files built at download time (the control room's and the well view's tables, JSON, zip and term list) now carry a time stamp (UTC) in the name, so two downloads can be told apart and the browser does not replace an earlier file. Under the buttons for the catalogue and the participant register it now says why the checksum differs with each download (new ids and a time in the answer)."),
        ("Termnamnen i tabellerna på datamodellsidan bryts nu inte mitt i ordet vid smal skärm (tabellen rullar i sidled i stället), och enheterna MQS (kubikmeter per sekund) och MTR (meter) förklaras.",
         "The term names in the tables on the data model page are no longer broken in the middle of words on a narrow screen (the table scrolls sideways instead), and the units MQS (cubic metres per second) and MTR (metres) are explained."),
    ]),
    ("2026.10.29-13", "2026-10-30", [
        ("Rättningar efter testet: etiketten vid en nekad körning säger nu \"nekad av spärren – skyddet fungerade\", och efter ett driftfel vid Leverera A föreslår Nästa att leverera igen (avtalet gäller ju fortfarande) i stället för att börja om.",
         "Fixes after the test: the label for a refused run now says \"refused by the safeguard – the protection worked\", and after an operational failure at Deliver A, Next suggests delivering again (the contract still holds) instead of starting over."),
        ("MIM-rutorna i stegen använder inte längre kravkoderna (RC och R) i löptexten; koderna finns kvar på MIM-sidan. Märket Nästa ryms i knappen, tabellerna på datamodellsidan bryter inte mitt i ord, exempelfilerna beskrivs som utkast, felsidorna har versionsraden och brunnsvyn minns valt språk.",
         "The MIM boxes in the steps no longer use the requirement codes (RC and R) in running text; the codes remain on the MIM page. The Next badge fits inside the button, the tables on the data model page no longer break in the middle of words, the example files are described as drafts, the error pages have the version line and the open view remembers the chosen language."),
    ]),
    ("2026.10.29-12", "2026-10-30", [
        ("Du kan nu ladda ned det som passerar varje steg: mätvärdena, katalogen, avtalen, leveransen, posterna i stadens plattform och analysen. Filerna är det kedjan faktiskt har, inte inspelade exempel, och varje fil har en kontrollsumma (SHA-256) som går att räkna ut själv.",
         "You can now download what passes through each step: the measurements, the catalogue, the agreements, the delivery, the records in the city's platform and the analysis. The files are what the chain actually has, not recorded examples, and each file has a checksum (SHA-256) you can compute yourself."),
        ("Leveransens kontrollsumma räknas när den tas emot och står också i auditloggen, så att filen går att jämföra byte för byte med det som gick genom kedjan.",
         "The delivery's checksum is computed when it is received and is also in the audit log, so the file can be compared byte for byte with what went through the chain."),
        ("Brunnsvyn kan laddas ned som CSV eller JSON, och datamodellen finns som en zip med en kontrollsumma per fil och som termlista i CSV. Ordlistan och MIM-bedömningen kan också laddas ned. Distribution A kräver fortfarande ett gällande avtal och märks som icke-publik.",
         "The open view can be downloaded as CSV or JSON, and the data model is available as a zip with a checksum per file and as a term list in CSV. The glossary and the MIM assessment can also be downloaded. Distribution A still needs a current agreement and is marked as non-public."),
    ]),
    ("2026.10.29-11", "2026-10-30", [
        ("Ordlistan finns nu på alla sidor: brunnsvyn, datamodellen, MIM-sidan och nyheterna understryker begreppen och förklarar dem när du pekar på dem, och brunnsvyn har en egen ordlistesida.",
         "The glossary is now on every page: the open view, the data model, the MIM page and the news underline the terms and explain them when you point at them, and the open view has its own glossary page."),
        ("Raderna i MIM-rutorna bryts inte längre kring understrukna ord, länkarna ut till OASC säger att de öppnas i en ny flik, och länkarna i ordlistan har egna namn.",
         "The lines in the MIM boxes no longer break around underlined words, the links out to OASC say they open in a new tab, and the glossary links have names of their own."),
        ("Sidan om MIM-bedömningen heter inte längre Svada-mini, förklarar att hävningsregeln är avstängd i den delade demon, och har en versionsrad. Steg 6 säger nu att läge B visar brunnarnas namn men inga positioner.",
         "The MIM page no longer says Svada-mini, explains that the termination rule is switched off in the shared demo, and has a version line. Step 6 now says that mode B shows the chambers' names but no positions."),
        ("Fler små rättningar efter testet: KoV-knapparna behåller sina namn när de är avstängda, ordförklaringen stängs när fokus går vidare, kontextfilen bär utkastets status, Om-sidan berättar att Krokängsparkens dygn bygger på samma mätvärden, och brunnsvyns adress till tidsserien säger att den inte fungerar direkt i en webbläsare.",
         "More small fixes after the test: the KoV buttons keep their names when disabled, the term explanation closes when focus moves on, the context file carries the draft's status, the About page says that Krokängsparken's days are built on the same measured values, and the open view's time series address says it does not work directly in a browser."),
    ]),
    ("2026.10.29-10", "2026-10-29", [
        ("Ny sida om hur vi följer MIM:arna: för varje MIM vad den är, vad vi gör, våra avsteg och vår bedömning, och hur statusen ska läsas. Den nås från varje MIM-ruta och från länken \"MIM-bedömningen\" högst upp, både i kontrollrummet och i brunnsvyn. Texterna i rutorna är omskrivna och säger tydligt att vår PoC är teknisk och att de mjuka delarna inte omfattas fullt ut.",
         "A new page about how we follow the MIMs: for each MIM what it is, what we do, our departures and our assessment, and how to read the status. It is reached from every MIM box and from the link \"MIM assessment\" at the top, in the control room and in the chamber view. The texts in the boxes are rewritten and say clearly that our PoC is technical and that the soft parts are not fully covered."),
        ("Ordlistan har 20 nya begrepp (bland annat MIM, JSON-LD, OpenAPI, gateway, tidsserie och kravkoderna) och \"JSON-kuvert\" heter nu \"leverans-JSON\".",
         "The glossary has 20 new terms (among them MIM, JSON-LD, OpenAPI, gateway, time series and the requirement codes) and the \"JSON envelope\" is now called \"delivery JSON\"."),
    ]),
    ("2026.10.29-9", "2026-10-29", [
        ("Demon läker sig själv om DHI:s connector startar om: katalogen byggs upp igen inom ungefär femton sekunder i stället för att vara tom tills någon registrerar om den för hand. Avtal som redan slutits går inte att återskapa, så en besökare kan behöva förhandla om.",
         "The demo now heals itself if DHI's connector restarts: the catalogue is rebuilt within about fifteen seconds instead of staying empty until someone registers it again by hand. Agreements already made cannot be recreated, so a visitor may have to negotiate again."),
    ]),
    ("2026.10.29-8", "2026-10-29", [
        ("Rättningar efter webbläsartestet: datamodellsidan visar nu rätt profil för leveranstypen B (stod \"bara A\"), SSSOM-filen och specifikationen öppnas som text i webbläsaren i stället för att laddas ner, MIM-länkarna har tydligare namn för skärmläsare, och några interna beteckningar är borta ur de publika texterna.",
         "Fixes after the browser test: the data model page now shows the right profile for delivery type B (it said \"only A\"), the SSSOM file and the specification open as text in the browser instead of downloading, the MIM links have clearer names for screen readers, and a few internal labels are gone from the public texts."),
    ]),
    ("2026.10.29-7", "2026-10-29", [
        ("Texterna om datamodellen är rättade så att de inte säger mer än de ska: modellen bygger på NGSI-LD och är länkad (inte återanvänd) till erkända modeller, och banderollerna i alla genererade filer säger att den är en tillfällig PoC-modell. "
         "Avvisningsexempel från schemakontrollen står nu på både svenska och engelska.",
         "The texts about the data model are corrected so that they do not say more than they should: the model is built on NGSI-LD and linked (not reused) to recognised models, and the banners in all generated files say that it is a temporary PoC model. "
         "Rejection examples from the schema check are now in both Swedish and English."),
    ]),
    ("2026.10.29-6", "2026-10-29", [
        ("Vi har tittat på MIM7 (geodata). Den har inga numrerade krav i v9.0, så den går inte att bedöma; vi redovisar vad vi gör i stället. Vi visar bara brunnarnas positioner som punkter på en karta, och bara i den icke-offentliga distribution A. MIM-rutan i steg 6 säger det.",
         "We have looked at MIM7 (geospatial data). It has no numbered requirements in v9.0, so it cannot be assessed; we state what we do instead. We only show the positions of the chambers as points on a map, and only in the non-public distribution A. The MIM box in step 6 says so."),
    ]),
    ("2026.10.29-5", "2026-10-29", [
        ("Datamodellen är tydligt märkt som en tillfällig modell framtagen för PoC:en, inte föreslagen som allmän modell, och vad den bygger på står på /modell. "
         "Varje leverans kontrolleras nu mot modellens schema innan staden lagrar den, och resultatet visas i steg 4. Den öppna vyns JSON har enhetskoder och en länk till modellen, "
         "och katalogens conformsTo pekar på modellen. Fem termer som saknades (leveranstyperna A och B samt tre egenskaper på brunnen) är nu definierade.",
         "The data model is clearly marked as a temporary model made for the PoC, not proposed as a general model, and what it is built on is on /modell. "
         "Every delivery is now checked against the model's schema before the City stores it, and the result is shown in step 4. The open view's JSON has unit codes and a link to the model, "
         "and the catalogue's conformsTo points to the model. Five terms that were missing (the delivery types A and B and three properties of the chamber) are now defined."),
    ]),
    ("2026.10.29-4", "2026-10-29", [
        ("Nytt: en ruta i varje steg (1–6), på brunnsvyn och på datamodellsidan som säger vilka MIM:ar (OASC:s minimikrav för interoperabilitet) som berörs, hur, och vår status. "
         "Rutan har en rad om vad varje MIM är och en länk till deras webbsida. Statusen är vår egen bedömning och inte en certifiering; vi påstår inget som vår öppna MIM-redovisning inte beskriver.",
         "New: a box in every step (1–6), on the open chamber view and on the data model page that says which MIMs (OASC's minimal interoperability mechanisms) are involved, how, and our status. "
         "The box has a line on what each MIM is and a link to their web page. The status is our own assessment and not a certification; we claim nothing that our open MIM assessment does not describe."),
    ]),
    ("2026.10.29-3", "2026-10-29", [
        ("Modellversionen i de modellerade värdena heter nu \"FCF-simulator 1.0.0 / enkel överfallsmodell\" i stället för ett internt komponentnamn. "
         "JSON-LD-svaren från tidsserien och från gatewayen nämner nu kontextens publika adress (tidigare ett internt värdnamn).",
         "The model version in the modelled values is now \"FCF-simulator 1.0.0 / enkel överfallsmodell\" instead of an internal component name. "
         "The JSON-LD answers from the time series interface and from the gateway now name the public address of the context (before, an internal host name)."),
    ]),
    ("2026.10.29-2", "2026-10-29", [
        ("Data bär nu datamodellutkastets kontext: attributen i stadens plattform lagras under modellens egna adresser, så att attributen som är termer i modellen går att följa till sin definition på /modell. "
         "Svaren ser likadana ut som förut (samma korta attributnamn). Modellen är fortfarande ett utkast. En besökares egen kontext (Link-huvud) ersätts av vår.",
         "The data now carries the draft data model's context: the attributes in the City's platform are stored under the model's own addresses, so the attributes that are terms of the model can be followed to their definition at /modell. "
         "The answers look the same as before (the same short attribute names). The model is still a draft. A visitor's own context (Link header) is replaced by ours."),
    ]),
    ("2026.10.29-1", "2026-10-29", [
        ("Steg 2 förklarar deltagarregistret enklare: staden har inte leverantörens adress sparad, utan slår upp den i en lista som samordnaren håller. "
         "Registret går inte att nå direkt för besökare; kontrollrummet visar vad det innehåller. I datamodellutkastet är två termer (sourceSrs och provenance.dataset) nu märkta som kopplade, eftersom de länkar till en annan term, och exempelfilen visar avtalet utan intern beteckning.",
         "Step 2 explains the participant directory more simply: the City does not have the provider's address saved, but looks it up in a list kept by the orchestrator. "
         "Visitors cannot reach the directory directly; the control room shows what it contains. In the draft data model two terms (sourceSrs and provenance.dataset) are now marked as linked, because they link to another term, and the example file shows the agreement without an internal label."),
    ]),
    ("2026.10.28-3", "2026-10-29", [
        ("Vi säger nu öppet att demon är byggd med AI-assistenter: en rad på Om-sidan, i projektets beskrivning och i översikten över MIM-bedömningarna, och en mening i rutan överst på datamodellutkastet. "
         "Koden, testerna och dokumentationen är utvecklade tillsammans med AI-assistenter (bland annat Claude, Codex och Gemini). Niklas Fjellman och Björn Hagström har styrt arbetet och tar ansvar för innehållet, men allt är inte oberoende granskat av människor.",
         "We now say openly that the demo is built with AI assistants: a line on the About page, in the project description and in the overview of the MIM assessments, and a sentence in the box at the top of the draft data model. "
         "The code, the tests and the documentation were developed together with AI assistants (among them Claude, Codex and Gemini). Niklas Fjellman and Björn Hagström have directed the work and are responsible for the content, but not everything has been independently reviewed by humans."),
        ("Demon är öppen utan lösenord även när man kör den lokalt: det är nu standard.",
         "The demo is now open without a password when run locally too: that is the default."),
    ]),
    ("2026.10.28-2", "2026-10-28", [
        ("Steg 2: staden hittar nu leverantören i samordnarens deltagarregister i stället för att ha adressen inlagd. Registret är samordnarens lista över deltagarna med medlemsstatus (en återkallelse syns direkt) och connectorns adress, men utan roller; det ligger på samordnarens interna adress, och steget visar namn och status. Steget visar vilka deltagare som finns och hur leverantören hittades.",
         "Step 2: the City now finds the provider in the orchestrator's participant directory instead of having the address built in. The directory is the orchestrator's list of the participants with membership status (a revocation shows at once) and connector address, but no roles; it sits on the orchestrator's internal address, and the step shows names and status. The step shows which participants exist and how the provider was found."),
    ]),
    ("2026.10.28-1", "2026-10-28", [
        ("Nytt: ett UTKAST till datamodell för de modellerade bräddresultaten finns på /modell på brunnsvyns adress (länk i sidfoten). Det är ett arbetsutkast som vi använder för att lära oss: "
         "det är inte beslutat, inte överenskommet med dataägaren, leverantören eller förvaltaren och inte inskickat till Smart Data Models. Varje term har en definition, en enhet och en egen adress som går att slå upp.",
         "New: a DRAFT data model for the modelled overflow results is at /modell on the chamber view's address (link in the footer). It is a working draft we use to learn: "
         "it is not decided, not agreed with the data owner, the provider or the custodian, and not submitted to Smart Data Models. Each term has a definition, a unit and an address of its own that can be looked up."),
    ]),
    ("2026.10.23-13", "2026-10-28", [
        ("Den öppna brunnsvyns maskingränssnitt har nu en formell beskrivning (OpenAPI) på /openapi.json på brunnsvyns adress.",
         "The machine interface of the open chamber view now has a formal description (OpenAPI) at /openapi.json on the chamber view's address."),
    ]),
    ("2026.10.23-12", "2026-10-28", [
        ("Ett kort nätavbrott (wifi, VPN, dator som vilar) räknas inte längre som ett fel i webbläsaren i statistiken: sidan hoppar bara över rundan och fortsätter när nätet är tillbaka.",
         "A short network outage (wifi, VPN, a computer that sleeps) is no longer counted as a browser error in the statistics: the page just skips that round and carries on when the network is back."),
    ]),
    ("2026.10.23-11", "2026-10-26", [
        ("Raden \"Nästa\" tar slut med en tydlig text (\"Klart: du har gått igenom hela kedjan.\") när du sett analysen, i stället för att försvinna.",
         "The \"Next\" row now ends with a clear message (\"Done: you have been through the whole chain.\") once you have seen the analysis, instead of just disappearing."),
        ("Tangentbordet: Tab från länken i en ordförklaring fortsätter efter ordet i stället för att lämna sidan (Skift+Tab går tillbaka till ordet).",
         "Keyboard: Tab from the link in a term explanation continues after the term instead of leaving the page (Shift+Tab goes back to the term)."),
        ("Statistiksidan nämner inget lösenord när demon är öppen. Sidfotens \"Testläge\" i brunnsvyn slås på och av direkt med ?test=1 och ?test=0 (och finns även på felsidorna). Tiden för en hävning visas i din tid.",
         "The statistics page no longer mentions a password when the demo is open. The \"Test mode\" footer in the chambers view switches on and off immediately with ?test=1 and ?test=0 (and is also on the error pages). The time of a revocation is shown in your own time."),
    ]),
    ("2026.10.23-10", "2026-10-26", [
        ("Statistiken förklarar att antalet besökare är ett minimum: många datorer (inte bara många människor) med samma webbläsare på samma adress, till exempel i ett mötesrum, räknas som en besökare.",
         "The statistics page explains that the visitor count is a minimum: many computers (not just many people) with the same browser on one address, for example in a meeting room, count as one visitor."),
    ]),
    ("2026.10.23-9", "2026-10-24", [
        ("Avvisningskoder (till exempel brunns-gis-i-distribution-b) står kvar oförändrade på engelska, med det engelska namnet bredvid, så att de går att söka på i båda språken.",
         "Rejection codes (for example brunns-gis-i-distribution-b) stay unchanged in English, with the English name next to them, so they can be searched for in both languages."),
    ]),
    ("2026.10.23-8", "2026-10-23", [
        ("Felinjektionens säkerhetsnät är starkare: ett kvarlämnat läge städas före nästa besökares leverans och av städningen inom 15 sekunder, även efter en omstart.",
         "The fault injection safety net is stronger: a mode left behind is cleaned up before the next visitor's delivery and by the cleanup within 15 seconds, even after a restart."),
        ("Texten i fliken Felinjektion säger rätt sak oavsett variant. Länken till stadens åtkomstsida (cip.) följer språkvalet. Nollställningstiden anges i din egen tid.",
         "The text in the Fault injection tab is right in every variant. The link to the city's access page (cip.) follows the language choice. The reset time is given in your own time."),
    ]),
    ("2026.10.23-7", "2026-10-23", [
        ("Felinjektionen är nu ditt eget läge: den slås på i modellen bara medan din egen leverans körs och slås av direkt efteråt, så den påverkar ingen annan besökare.",
         "The fault injection is now your own mode: it is switched on in the model only while your own delivery runs and is switched off right after, so it does not affect any other visitor."),
        ("Stavningen är \"bräddata\" (med två d) överallt.",
         "The Swedish spelling is now \"bräddata\" (two d) everywhere."),
    ]),
    ("2026.10.23-6", "2026-10-23", [
        ("Efter Leverera A pekar \"Nästa\" på Analysera (steg 6) och raden tar slut när du öppnat det. \"Nästa: Förhandla A\" flyttar fokus till rätt knapp.",
         "After Deliver A, \"Next\" points to Analyse (step 6) and the row ends once you have opened it. \"Next: Negotiate A\" moves focus to the right button."),
        ("Ett avslag av en ny begäran medan ditt avtal gäller säger det i loggen, och \"Nästa\" går tillbaka dit du var.",
         "Rejecting a new request while your agreement is valid says so in the log, and \"Next\" goes back to where you were."),
        ("Felsidor: en okänd adress ger en riktig sida och ett konstigt avtals-id ger 404 i stället för fel. Stadens åtkomstsida (cip.) finns på engelska.",
         "Error pages: an unknown address gives a proper page and an odd agreement id gives 404 instead of an error. The city's access page (cip.) is available in English."),
        ("Språket följer sidan även när en annan flik har bytt språk. KoV-rutan ryms vid smalare fönster. Interna namn och sökvägar visas inte längre i loggar och exempel.",
         "The language follows the page even when another tab has switched language. The KoV box fits in narrower windows. Internal names and paths are no longer shown in logs and examples."),
        ("Fliken Felinjektion säger att den gäller alla besökare. Brunnsvyn visar Testläge i sidfoten.",
         "The Fault injection tab says it applies to all visitors. The chambers view shows Test mode in the footer."),
    ]),
    ("2026.10.23-5", "2026-10-23", [
        ("Steg 1 och ordlistan förklarar att datumet i batch-id:t (till exempel 2026-06-29) är det modellerade dygnet, inte när batchen kördes. Nytt begrepp: Modellerat dygn.",
         "Step 1 and the glossary explain that the date in the batch id (for example 2026-06-29) is the modelled day, not when the batch was run. New term: Modelled day."),
        ("Testläge för oss som provar: öppna sidan med ?test=1 så räknas inte besöket i statistiken (?test=0 avslutar).",
         "Test mode for those of us testing: open the page with ?test=1 and the visit is not counted in the statistics (?test=0 ends it)."),
    ]),
    ("2026.10.23-4", "2026-10-23", [
        ("Steg 6 startar med distribution A, och växlingen mellan A och B är en tydlig tvåvalsknapp med förklaring.",
         "Step 6 starts with distribution A, and switching between A and B is a clear two-way toggle with an explanation."),
        ("Kartan förbereds så fort steg 6 öppnas (biblioteket laddas och anslutningen till kartplattorna förbereds), så den visas snabbare.",
         "The map is prepared as soon as step 6 opens (the library loads and the connection to the map tiles is prepared), so it appears faster."),
        ("Utan ett gällande avtal visar A en vänlig förklaring i stället för ett larm.",
         "Without a current agreement, A shows a friendly explanation instead of an alert."),
    ]),
    ("2026.10.23-3", "2026-10-23", [
        ("Om-sidan redovisar att arbetet sker inom Vattendatalabbet, nämner finansiärerna, krediterar upphovspersonerna och länkar till projektet.",
         "The About page states that the work is done within the Swedish Water Data Lab, names the funders, credits the authors and links to the project."),
        ("Ordlistan: DCAT och DCP är egna begrepp, och fler begrepp länkar till sina standarder eller projekt.",
         "The glossary: DCAT and DCP are terms of their own, and more terms link to their standards or projects."),
        ("Om-sidan anger att demon följer DSSC Blueprint 3.0, med länk.",
         "The About page states that the demo follows the DSSC Blueprint 3.0, with a link."),
    ]),
    ("2026.10.23-2", "2026-10-23", [
        ("Fliken Jobb visar en snurra och \"Jobb N pågår\" medan ett jobb körs, och en snurra i jobblistan.",
         "The Jobs tab shows a spinner and \"Job N is running\" while a job runs, and a spinner in the job list."),
        ("När en connector just har startats om visas \"Connectorn är inte färdigstartad, försök igen om en stund\" i stället för ett rått HTTP 405.",
         "When a connector has just restarted, \"The connector has not finished starting, try again in a moment\" is shown instead of a raw HTTP 405."),
    ]),
    ("2026.10.23-1", "2026-10-23", [
        ("Versionsnummer i sidfoten och i /api/status, och den här sidan.",
         "Version number in the footer and in /api/status, and this page."),
        ("Ett avslag häver inget avtal i den delade demon, och texterna säger det. KoV häver med knappen \"KoV häver avtalet\".",
         "A rejection revokes no agreement in the shared demo, and the texts say so. KoV revokes with the \"KoV revokes the agreement\" button."),
        ("Brunnsvyn: en okänd brunn ger \"ingen data\" (404) i stället för ett tjänstefel.",
         "Chambers view: an unknown chamber gives \"no data\" (404) instead of a service error."),
        ("Avtalssidan visar attribueringsplikten (duty) som skyldighet.",
         "The agreement page shows the attribution duty as an obligation."),
        ("Statistiken visar serverfel och 429 per dag.",
         "Statistics show server errors and 429 responses per day."),
        ("Rättat: Esc stänger bara den lilla förklaringsrutan; \"Nästa\" ändras inte av ett misslyckat beslut; förklaringsrutan hamnar alltid inom fönstret.",
         "Fixed: Esc closes only the small explanation box; \"Next\" is not changed by a failed decision; the explanation box always stays inside the window."),
        ("Uppgraderade komponenter: Orion-LD 1.12, MongoDB 7, Mintaka 0.7, TimescaleDB (Apache-varianten), Caddy, Python.",
         "Upgraded components: Orion-LD 1.12, MongoDB 7, Mintaka 0.7, TimescaleDB (Apache variant), Caddy, Python."),
    ]),
]

T = {
    "sv": {"titel": "Nyheter", "rub": "Vad som är nytt", "nu": "Den här demon kör version", "tillbaka": "Kontrollrummet", "andra": ("English", "en"),
           "intro": "Varje ändring som en besökare kan märka får en ny version. Testrapporter anger vilken version de provat."},
    "en": {"titel": "What's new", "rub": "What's new", "nu": "This demo runs version", "tillbaka": "Control room", "andra": ("Svenska", "sv"),
           "intro": "Every change a visitor can notice gets a new version. Test reports state which version they tested."},
}


def sida(sprak="sv"):
    sprak = sprak if sprak in T else "sv"
    t = T[sprak]
    i = 0 if sprak == "sv" else 1
    e = html.escape
    poster = "".join(
        f'<h2>{e(v)} <span class="datum">{e(d)}</span></h2><ul>' + "".join(f"<li>{e(x[i])}</li>" for x in rader) + "</ul>"
        for v, d, rader in NYHETER)
    return f"""<!doctype html><html lang="{sprak}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t["titel"])}</title><style>
:root{{color-scheme:light;--fg:#1d1d1d;--dov:#47504c}}
body{{background:#fff;color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:1rem 16px 3rem}}
h1{{margin:.6rem 0 .2rem}} h2{{margin:1.4rem 0 .3rem;font-size:1.1rem}} .datum{{color:var(--dov);font-weight:400;font-size:.9rem}}
.topp{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}} a{{color:#0848a6}} li{{margin:.25rem 0}}
</style></head><body>
<div class="topp"><a href="/?lang={sprak}">&larr; {e(t["tillbaka"])}</a><a href="/nyheter?lang={t["andra"][1]}" hreflang="{t["andra"][1]}">{e(t["andra"][0])}</a></div>
<h1>{e(t["rub"])}</h1>
<p>{e(t["nu"])} <b>{e(VERSION)}</b>. {e(t["intro"])}</p>
{poster}
<p style="color:var(--dov);font-size:.85rem;margin-top:2rem"><a href="https://github.com/GoteborgsStad/svada" target="_blank" rel="noopener">{"Källkod på GitHub" if sprak == "sv" else "Source code on GitHub"} ↗</a></p>
</body></html>"""
