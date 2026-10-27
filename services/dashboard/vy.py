"""
vy.py – kontrollrummets webbgränssnitt.

Server-renderad HTML med all CSS och JavaScript INLINE. Inga CDN:er, inga
typsnitt utifrån, inget byggsteg – samma princip som skördarnas vy: PoC:en
ska fungera i en helt avskuren miljö, och en demo får inte falla för att ett
bibliotek någonstans på internet inte svarar.

Arbetsfördelningen mellan server och webbläsare:

  * SERVERN renderar det som är STRUKTUR och FÖRKLARING: kedjebilden, de tio
    panelerna, ordlistan och flikarna, på det språk besökaren valt (svenska
    eller engelska). Stegtexterna kommer ur steg.py (nyckeln pedagogik), så de
    är samma sanning som API:t och verifieringen; vy.py har inga egna
    stegtexter, bara gränssnittets egna (TEXTER).
  * WEBBLÄSAREN fyller i det som är FÄRSKVARA: hälsa, siffror, auditlogg,
    jobbloggar, avvikelsekurvan, KoV-kön och ODRL-villkoren. Allt via /api/* –
    exakt de endpoints tests/verify_ap6b.sh prövar. Det som syns i vyn går
    därför alltid att verifiera från ett skal.

Språk: ?lang=sv|en eller kakan svada-sprak. Data översätts inte (loggar,
komponentnamn, värden, API-svar).

Variant: "extern" (publik demo) visar varken portnummer eller interna
projekthänvisningar; "intern" (standard) visar dem. Styrs av DEMO_VARIANT.
"""

import html
import i18n
import json
import os
import re

import steg as stegmodul
from gemensam import rensa

SPRAK = ("sv", "en")
DEMO_VERSION = os.environ.get("SVADA_VERSION", "okänd")      # visas i sidfoten (länk till /nyheter)


TEXTER = {
    "sv": {
        "h1": "SVADA PoC – kontrollrum",
        "vadArRub": "Vad är en avvikelse?",
        "varforTestaRub": "Varför testa det?",
        "simKort": "simulerad",
        "legSim": (
                "<span class=\"tag sim\">simulerad</span> steget innehåller en "
                "simulerad del: modellberäkningen (steg 1) och Svadas "
                "utfärdare (steg 2)"),
        "odrl": {
                "rub": "Villkoren för distribution B och A, i klartext och i ODRL",
                "intro": (
                    "Så här ser erbjudandena ut i DHI:s katalog. Villkoren "
                    "sätts av den som äger data (KoV) och binder den som tar "
                    "emot data. De följer med erbjudandet, men de verkställs olika. "
                    "Connectorn avgör vem som får ingå avtal (bara staden "
                    "för distribution A) och kräver KoV:s godkännande. "
                    "Förbuden mot att sprida och publicera och plikten att "
                    "ange källan kan ingen connector tvinga fram efter en "
                    "leverans: de är en del av avtalet och mottagarens eget "
                    "ansvar. Skillnaden "
                    "syns i regeltyperna: distribution B har bara tillstånd "
                    "(permission). Distribution A har dessutom förbud "
                    "(prohibition) och skyldigheter (obligation). Namn som "
                    "deltagare, kovGodkannande och medgerGranskning är "
                    "identifierare i Svadas eget ODRL-ordförråd och står "
                    "därför likadant i båda språken."),
                "visaJson": "Visa ODRL (JSON)",
                "verkstall": {
                    "rub": "Vem kan tvinga fram vad?",
                    "rader": [
                        ["Före leverans, hos den som lämnar ut data",
                         "Det som ska hindras måste hindras hos datadelaren. "
                         "DHI:s connector släpper bara in den som visar rätt "
                         "intyg, bara staden får ingå avtal om distribution A, "
                         "och inget skickas utan avtal och KoV:s godkännande. "
                         "Mottagaren behöver inte tacka nej: den kommer aldrig "
                         "åt data den inte får."],
                        ["Efter leverans, hos mottagaren",
                         "Förbuden mot att sprida och publicera och plikten "
                         "att ange källan gäller vad mottagaren gör med data "
                         "efteråt. Ingen avsändare kan tekniskt tvinga fram det "
                         "hos någon annan. De är en del av avtalet och "
                         "mottagarens eget ansvar, och därför litar vi inte "
                         "bara på mottagarens ord. För distribution A är "
                         "mottagaren Intraservice, som tar emot data på KoV:s "
                         "uppdrag och är bunden av villkoren som vilken "
                         "mottagare som helst."],
                        ["Därför flera lås",
                         "Skyddet bygger på flera lås, så att inget enskilt "
                         "lås behöver räcka. Listan nedan går igenom dem i den "
                         "ordning data rör sig."],
                    ],
                    "lasRub": "Lås för distribution A, i den ordning data rör sig",
                    "las": [
                        ["Intyg för att alls få se katalogen", "DHI · steg 2",
                         "DHI:s connector svarar bara den som visar giltiga "
                         "intyg från rätt utfärdare (medlemskap och deltagare "
                         "från Svada, rollen från parten själv). Utan intyg: "
                         "Felkoden 401 (Unauthorized, ”obehörig”)."],
                        ["Villkoret i erbjudandet", "DHI · steg 2–3",
                         "Erbjudandet för A säger att bara staden får "
                         "använda datan. Ingen annan part kan ingå avtalet."],
                        ["KoV:s godkännande", "DHI · steg 3",
                         "Avtalet om A blir inte klart förrän KoV har beslutat, "
                         "med ett intyg som bevisar rollen. Spärren sitter hos "
                         "DHI och aldrig hos mottagaren."],
                        ["Kontroll före leverans", "DHI · steg 4",
                         "DHI:s connector skickar bara data om avtalet finns "
                         "och gäller och det är rätt part som beställer."],
                        ["Kontroll vid mottagning", "Staden · steg 4",
                         "Stadens mottagning slår upp avtalet, kontrollerar "
                         "att det gäller rätt dataprodukt och granskar "
                         "innehållet innan något sparas. En öppen leverans som "
                         "innehåller brunnspositioner stoppas."],
                        ["Åtkomstkontroll där data lagras", "Staden · steg 5",
                         "Den skyddade distributionen går bara att läsa med en "
                         "nyckel som man får genom att visa ett avtals id "
                         "(annars felkoden 403, ”förbjudet”). Den öppna läses via ett API som "
                         "bara släpper igenom en fast lista fält, aldrig "
                         "positioner."],
                        ["Hävning av avtalet", "DHI och staden · steg 3–5",
                         "Ett avtal gäller tills det hävs eller löper ut (30 dagar). Hävs det nekar "
                         "DHI:s connector nya överföringar och stadens gateway "
                         "slutar släppa in nycklar som hör till avtalet. "
                         "Statusen kontrolleras vid varje användning."],
                    ],
                },
                "A": {
                    "rub": "Skyddade data",
                    "regler": [
                        ["permission: use", "får användas …"],
                        ["constraint: deltagare = stad", "… men bara av Göteborgs Stad"],
                        ["constraint: inForceDate ≥ contractAgreement+0s", "… från det att avtalet ingåtts"],
                        ["constraint: inForceDate ≤ contractAgreement+30d", "… och i högst 30 dagar"],
                        ["prohibition: distribute", "får inte spridas vidare"],
                        ["prohibition: publish", "får inte publiceras"],
                        [
                            "obligation: kovGodkannande",
                            "KoV måste godkänna innan avtal blir klart",
                        ],
                        [
                            "obligation: medgerGranskning",
                            "mottagaren medger granskning av hur data används (deklaration, verkställs inte tekniskt)",
                        ],
                    ],
                },
                "B": {
                    "rub": "Öppna data (CC BY 4.0)",
                    "regler": [
                        ["permission: use", "får användas …"],
                        ["duty: attribute", "… om källan anges"],
                        ["permission: distribute", "får spridas vidare"],
                        ["permission: publish", "får publiceras"],
                    ],
                },
                "bnot": (
                    "ODRL-reglerna för distribution B är en egen, förenklad "
                    "översättning av licensens huvudvillkor. De pekar inte på "
                    "licenstexten, och licensens övriga villkor (t.ex. att ange"
                    " ändringar) finns bara i licensen."),
                "not": (
                    "I kontrollrummet hämtas villkoren live från DHI:s katalog,"
                    " med knappen Hämta DSP-katalogen eller under Mer detaljer "
                    "› Visa exempelobjekt."),
            },
        "prov": {
                "rub": "Så följer villkoren med data",
                "intro": (
                    "Till vänster ett värde i stadens dataplattform, förkortat."
                    " Fältet provenance bär avtalets id (contractAgreementId). "
                    "Till höger samma id uppslaget i stadens connector: där "
                    "finns avtalet med distribution, status och villkoren, "
                    "först i klartext och sedan i ODRL. ODRL-texten kopieras "
                    "alltså inte in i varje värde. Värdet pekar på avtalet, och"
                    " avtalet bär villkoren."),
                "v1": "1. Värdet i CIP:en med ursprungsmärkning",
                "v2": "2. Avtalet som id:t pekar på: stadens connectors avtal (id, parter, villkor) med status och adress ur stadens avtalsregister",
                "not": (
                    "Förkortade exempel. Fältnamnen är de riktiga från "
                    "mottagningstjänsten."),
            },
        "sehur": {
                "rub": "Se hur det ser ut",
                "tips": "Tre exempel. Klicka på en flik, eller bläddra med knapparna under, för att byta.",
                "foreg": "Föregående", "nasta": "Nästa", "av": "av",
                "katFlik": "Katalogen DHI visar",
                "vcFlik": "Stadens intyg (VC)",
                "nejFlik": "Utan intyg: felkod 401",
                "katA": "Skyddade data",
                "katB": "Öppna data",
                "katText": (
                    "Så här beskriver DHI:s connector vad den delar. Katalogen "
                    "följer DCAT, W3C:s standard för datakataloger. DCAT är "
                    "vad Dataspace Protocol bygger katalogen på, och en av "
                    "standarderna i EU:s blueprint för dataspaces (DSSC). "
                    "Varje datamängd bär sitt erbjudande i ODRL. Här står "
                    "distribution B och A bredvid varandra, förkortade: lägg "
                    "märke till skillnaderna i klass, åtkomst, licens och "
                    "villkor. Distribution B har bara tillstånd (permission), "
                    "med plikten att ange källan. Distribution A har ett "
                    "snävare tillstånd (permission: användning, bara för "
                    "staden) och dessutom förbud (prohibition) och en "
                    "skyldigheter (obligation). Distribution A syns i DHI:s katalog "
                    "och går bara att få avtal om på dess villkor."),
                "vcText": (
                    "Ett av stadens tre intyg: medlemskap i dataspacet SVADA. "
                    "De andra två intygar deltagar-id och roll. Medlemskapet "
                    "är signerat av Svadas utfärdare, rollen intygar staden "
                    "själv; vem som helst kan kontrollera signaturen, men "
                    "ingen kan ändra innehållet."),
                "nejText": (
                    "Behörigheten sitter på att få läsa katalogen. Utan giltigt"
                    " intyg svarar DHI med felkoden 401 (Unauthorized, "
                    "”obehörig”): webbens standardsvar när avsändaren inte kan "
                    "styrka vem den är. Med intyg kommer katalogen."),
                "not": (
                    "Förkortade exempel som är skrivna för att visa formen. "
                    "Villkoren för distribution B och A hämtas live ur DHI:s "
                    "katalog i rutan ovan och under Visa exempelobjekt längre "
                    "ned."),
            },
        "stegradRub": "Steg:",
        "tillBilden": "↑ Till bilden",
        "seHandaRub": "Se det hända",
        "skickade": "Skickade mätvärden (exempel):",
        "flikar": ["Kedjan 1–6", "Följ ett värde", "Auditlogg", "Suveränitet: KoV & ODRL", "Felinjektion", "Jobb"],
        "introH": "Följ data från modellen till stadens beslut",
        "intro1": (
                "Ett dataspace är ett sätt för organisationer att dela data "
                "utan en gemensam databas. Data ligger kvar hos den som äger "
                "det, och lämnas ut först när ett maskinellt avtal säger ja. "
                "Villkoren följer med data via avtalets id och kontrolleras "
                "automatiskt."),
        "intro2": (
                "Två organisationer är med. <b>DHI</b> mäter och räknar fram "
                "data åt staden. <b>Göteborgs Stad</b> äger data. Inom staden "
                "är <b>Kretslopp och Vatten (KoV)</b> den förvaltning som "
                "bestämmer villkoren, och <b>Intraservice</b> driver stadens "
                "connector och dataplattform."),
        "ingress": (
                "Sex steg från DHI:s modell av bräddbrunnarna, genom ett"
                " riktigt dataspace mellan DHI och Göteborgs Stad, till att "
                "staden använder data för analys och beslut. Klicka på ett "
                "steg för att se vad som händer, varför, och vad knapparna gör."),
        "fakta1": (
                "<b>Dataspace</b>: data delas på avtal och villkor, utan "
                "gemensam databas."),
        "fakta3": "<b>Alla koordinater är påhittade.</b>",
        "omLank": "Om dataspaces, EU och demon",
        "omH": "Om dataspaces och demon",
        "omVadH": "Vad är ett dataspace?",
        "tillbakaKedjan": "← Tillbaka till kedjan",
        "omFlik": "Om demon",
        "euH": "Del av EU:s satsning på dataspaces",
        "omProjH": "Arbetet sker inom Vattendatalabbet",
        "omProj": ('Demon är framtagen inom <b>Vattendatalabbet</b> (projektet SVADA), ett projekt i Göteborgs Stad i samarbete med RISE. '
                   'Projektet finansieras av Energimyndigheten, Formas, Vinnova och Water Wise Societies. '
                   '<a href="https://vattendatalabbet.se/" target="_blank" rel="noopener">Vattendatalabbet ↗</a> · '
                   '<a href="https://www.vinnova.se/en/p/the-swedish-water-data-lab-svada--transition-for-smart-water-management" target="_blank" rel="noopener">Projektet hos Vinnova ↗</a>'),
        "omKredH": "Skapad av",
        "omKred": "Björn Hagström, expert på informationshantering och data spaces, och Niklas Fjellman.",
        "omBpH": "Följer DSSC Blueprint 3.0",
        "omBp": ('Demon följer <b>Blueprint 3.0</b> från Data Spaces Support Centre (DSSC), EU:s referensram för data spaces: roller (dataleverantör, datakonsument, operatör), '
                 'dataprodukter, avtal och policyer i ODRL, datautbyte med Dataspace Protocol och verifierbara intyg. Styrning, juridik och affärsmodell ingår inte i demon. '
                 '<a href="https://dssc.eu/" target="_blank" rel="noopener">DSSC Blueprint ↗</a>'),
        "eu1": (
                "EU:s datastrategi från 2020 bygger upp gemensamma europeiska "
                "dataspaces (Common European Data Spaces) inom bland annat "
                "hälsa, energi, mobilitet, jordbruk och miljö (Green Deal). "
                "Målet är en inre marknad för data, där organisationer delar "
                "data på villkor de själva bestämmer. Dataförvaltningsakten och"
                " dataakten sätter de rättsliga ramarna, och EU:s stödcentrum "
                "DSSC beskriver hur ett dataspace byggs."),
        "eu2": (
                "PoC:en använder samma byggstenar som EU rekommenderar: "
                "connector, Dataspace Protocol, villkor i ODRL och verifierbara"
                " intyg. Ett svenskt dataspace för VA-data byggt så här går att"
                " koppla ihop med de europeiska."),
        "introAkta": (
                "<b>Det mesta här körs på riktigt.</b> Varje steg utförs av "
                "riktiga program som pratar riktiga standardprotokoll med "
                "varandra, samma programvara som kan användas i drift. Varje "
                "steg visar vilka system som kör och vad som är förenklat. Om "
                "mätdata och de påhittade koordinaterna, se <a "
                "href=\"#omdata\">Om data i demon</a> längre ned."),
        "legH": "Så läser du bilden",
        "legDs": (
                "<b>Dataspace</b>: finns för att dela data med avtal och "
                "villkor"),
        "legPrincip": "<b>Dataspace-princip</b> syns i steget",
        "legStatus": "<b>Grön punkt</b>: stegets tjänster svarar nu",
        "legDist": (
                "<span class=\"tag b\">B</span> öppna data, utan brunnarnas "
                "position &nbsp;·&nbsp; <span class=\"tag a\">A</span> skyddade "
                "data, originalet med position"),
        "omdataH": "Om data i demon",
        "omMatH": "Mätdata",
        "omMat": (
                "Mätserien för Krokängsparken (brunnen SSO1_01-4526) är riktig uppmätt data från ett "
                "utdrag ur stadens system, liksom brunnsnamnen. Av 91 brunnar "
                "är det bara den här som har en riktig mätserie; de övriga 90 "
                "har påhittade serier som räknas fram ur brunnens id. En av de 91, "
                "SSO1_01-Pump_490, är en bräddpunkt vid en pumpstation."),
        "omKoordH": "Koordinater",
        "omKoord": (
                "<b>Alla koordinater i demon är påhittade.</b> Brunnarnas "
                "riktiga positioner är känsliga, så brunnarna är utplacerade "
                "slumpvis på Liseberg. Krokängsparkens brunn ligger på "
                "Lisebergsbanans spår. Det finns inget samband kvar att räkna "
                "tillbaka till de riktiga positionerna."),
        "omModellH": "Modellen",
        "omModell": (
                "DHI:s riktiga Future City Flow är en hydrodynamisk modell av "
                "hela ledningsnätet. Den körs inte i demon. I stället räknar en"
                " enkel, simulerad modell ut bräddvolym, bräddtid, medelflöde "
                "och vattennivå per brunn ur mätvärdena. Resultaten ser rimliga"
                " ut men är inga riktiga modellresultat."),
        "omFartH": "Hastighet",
        "omFart": (
                "Modellen bygger på hela mätserien för brunnen, som läses direkt "
                "ur filerna. Mätserien är densamma varje gång, så samma dygn ger samma resultat; "
                "de påhittade brunnarna och dygnen varierar mellan batcherna."),
        "omLiveH": "Varför inte live?",
        "omLive": (
                "Riktiga mätningar och positioner från VA-nätet är känslig "
                "information. Därför använder demon en datadump i stället för "
                "en live-koppling till givarna, och en enkel beräkning i "
                "stället för DHI:s modell. Allt från katalogen och framåt är "
                "riktiga tjänster."),
        "ordningEtikett": "Prova i den här ordningen (klicka för att öppna steget; åtgärden körs där):", "nasta": "Nästa", "nastaKnapp": "Nästa: ", "nastaSlut": "Klart: du har gått igenom hela kedjan.",
        "ordning": ["Kör batch", "Hämta katalog", "Förhandla B", "Leverera B", "Förhandla A + KoV", "Leverera A", "Analysera"],
        "zon1": "Hos producenten",
        "zon1s": "DHI tar fram dataprodukten",
        "zon2": "Dataspace",
        "zon2s": "avtal, villkor och leverans",
        "zon3": "Användning",
        "zon3s": "staden lagrar och använder data",
        "banaDhi": "tar fram data åt staden",
        "grans": "Organisationsgräns DHI | Göteborgs Stad",
        "stad": "Göteborgs Stad",
        "banaIs": "driver connector och plattform",
        "banaKov": "äger data och villkoren",
        "kat": {"ds": "◆ Dataspace", "princip": "◇ Dataspace-princip syns här", "kedja": "□ Helhetskedjan"},
        "borja": "Börja här ↓",
        "statusTitel": "Komponenterna svarar (exempel)",
        "kovTitel": "KoV:s beslut om A",
        "kovOrg": "Kretslopp och Vatten, Göteborgs Stad · del av steg 3",
        "steg": "Steg",
        "stang": "Stäng ✕",
        "stangAria": "Stäng panelen",
        "vad": "Vad händer?",
        "varfor": "Varför?",
        "styrning": "Styrning (governance):",
        "dsH": {"kedja": "Är det här dataspace?", "ds": "Därför är det dataspace", "princip": "Dataspace-idén i steget"},
        "prova": "Prova själv",
        "dtGor": "Det här händer",
        "dtTitta": "Titta efter",
        "dtKraver": "Förutsätter",
        "akta": "Äkta",
        "forenklat": "Förenklat i PoC:en",
        "prot": "Protokoll:",
        "teknikNot": (
                "Här ligger också fördjupningen om komponenterna och knappen "
                "Visa exempelobjekt."),
        "siffrorRub": "Siffror just nu (exempel)",
        "klar": "jobbet klart",
        "vantar": "jobbet klart · avtalet väntar på KoV",
        "avvisad": "jobbet klart · leveransen avvisades",
        "ingetavtal": "jobbet klart · inget avtal ingicks",
        "fel": "misslyckades",
        "nekad": "nekad av spärren (så ska det vara)",
        "helaLogg": "Öppna hela loggen i fliken Jobb →",
        "roll": {
                "demo": "demonstratör (simulerar en händelse)",
                "dhi": "DHI",
                "stad": "staden (Intraservice)",
                "kov": "KoV (Kretslopp och Vatten)",
            },
        "agerarSom": "Du agerar som",
        "kovRub": "Agera som KoV",
        "kovIntro": (
                "Här fattar du beslutet som Kretslopp och Vatten. I "
                "verkligheten görs det av en handläggare på KoV. I demon gör du"
                " det själv, och kontrollrummet bevisar KoV-rollen åt dig med "
                "ett intyg."),
        "kovTillA": "Fatta beslutet som KoV i KoV-rutan.",
        "distNyckel": "<b>B</b> = öppna data (klass K0R1T1, CC BY 4.0, utan brunnarnas positioner): avtalet tecknas automatiskt. <b>A</b> = skyddade data (klass K1R1T1, med brunnarnas positioner): kräver KoV:s godkännande och får inte spridas eller publiceras.",
        "kovSidlank": "Öppna hela KoV-sidan (fliken Suveränitet) →",
    },
    "en": {
        "h1": "SVADA PoC – control room",
        "vadArRub": "What is a deviation?",
        "varforTestaRub": "Why test it?",
        "simKort": "simulated",
        "legSim": (
                "<span class=\"tag sim\">simulated</span> the step contains a "
                "simulated part: the model calculation (step 1) and "
                "Svada's issuer (step 2)"),
        "odrl": {
                "rub": (
                    "The terms for distributions B and A, in plain words and in"
                    " ODRL"),
                "intro": (
                    "This is how the offers look in DHI's catalogue. The "
                    "terms are set by whoever owns the data (KoV) and bind "
                    "whoever receives it. They travel with the offer, but they are enforced "
                    "differently. The connector decides who may enter an "
                    "agreement (only the city for distribution A) and "
                    "requires KoV's approval. The prohibitions on sharing and "
                    "publishing and the duty to credit the source cannot be "
                    "forced by any connector after a delivery: they are part "
                    "of the agreement and the recipient's own responsibility. "
                    "The difference "
                    "shows in the rule types: distribution B has only "
                    "permissions. Distribution A also has prohibitions and "
                    "obligations. Names such as deltagare, kovGodkannande "
                    "and medgerGranskning are identifiers in Svada's own "
                    "ODRL vocabulary and are therefore the same in both "
                    "languages."),
                "visaJson": "Show ODRL (JSON)",
                "verkstall": {
                    "rub": "Who can force what?",
                    "rader": [
                        ["Before delivery, at whoever releases the data",
                         "What must be prevented has to be prevented at the "
                         "data sharer. DHI's connector only lets in whoever "
                         "shows the right credential, only the city may enter "
                         "an agreement about distribution A, and nothing is "
                         "sent without an agreement and KoV's approval. The "
                         "recipient does not have to decline: it never gets "
                         "data it may not have."],
                        ["After delivery, at the recipient",
                         "The prohibitions on sharing and publishing and the "
                         "duty to credit the source concern what the recipient "
                         "does with the data afterwards. No sender can "
                         "technically force that on someone else. They are part "
                         "of the agreement and the recipient's own "
                         "responsibility, which is why we do not rely only on "
                         "the recipient's word. For distribution A the "
                         "recipient is Intraservice, which receives the data on "
                         "KoV's behalf and is bound by the terms like any "
                         "other recipient."],
                        ["Hence several locks",
                         "The protection rests on several locks, so that no "
                         "single lock has to be enough. The list below goes "
                         "through them in the order the data moves."],
                    ],
                    "lasRub": "Locks for distribution A, in the order the data moves",
                    "las": [
                        ["Credentials to see the catalogue at all", "DHI · step 2",
                         "DHI's connector only answers whoever shows valid "
                         "credentials from the right issuer (membership and "
                         "participant from Svada, the role from the party "
                         "itself). Without credentials: error code 401 (Unauthorized)."],
                        ["The term in the offer", "DHI · steps 2–3",
                         "The offer for A says only the city may use the data. "
                         "No other party can enter the agreement."],
                        ["KoV's approval", "DHI · step 3",
                         "The agreement for A is not concluded until KoV has "
                         "decided, with a credential proving the role. The "
                         "gate sits at DHI and never at the recipient."],
                        ["Check before delivery", "DHI · step 4",
                         "DHI's connector only sends data if the agreement "
                         "exists and is valid and the right party is ordering."],
                        ["Check on receipt", "The city · step 4",
                         "The city's intake looks up the agreement, checks that "
                         "it covers the right data product and inspects the "
                         "content before anything is stored. An open delivery "
                         "that contains chamber positions is stopped."],
                        ["Access control where data is stored", "The city · step 5",
                         "The protected distribution can only be read with a "
                         "key you get by showing an agreement id (otherwise "
                         "error code 403, forbidden). The open one is read through an API that "
                         "only lets a fixed list of fields through, never "
                         "positions."],
                        ["Revocation of the agreement", "DHI and the city · steps 3–5",
                         "An agreement is valid until it is revoked or expires (30 days). Once "
                         "revoked, DHI's connector refuses new transfers and "
                         "the city's gateway stops accepting keys that belong "
                         "to the agreement. The status is checked on every "
                         "use."],
                    ],
                },
                "A": {
                    "rub": "Protected data",
                    "regler": [
                        ["permission: use", "may be used …"],
                        ["constraint: deltagare = stad", "… but only by the City of Gothenburg"],
                        ["constraint: inForceDate ≥ contractAgreement+0s", "… from the moment the agreement is made"],
                        ["constraint: inForceDate ≤ contractAgreement+30d", "… and for 30 days at most"],
                        ["prohibition: distribute", "may not be passed on"],
                        ["prohibition: publish", "may not be published"],
                        [
                            "obligation: kovGodkannande",
                            "KoV must approve before an agreement is made",
                        ],
                        [
                            "obligation: medgerGranskning",
                            "the recipient allows audit of how the data is used (a declaration, not technically enforced)",
                        ],
                    ],
                },
                "B": {
                    "rub": "Open data (CC BY 4.0)",
                    "regler": [
                        ["permission: use", "may be used …"],
                        ["duty: attribute", "… if the source is credited"],
                        ["permission: distribute", "may be passed on"],
                        ["permission: publish", "may be published"],
                    ],
                },
                "bnot": (
                    "The ODRL rules for distribution B are our own simplified "
                    "translation of the licence's main terms. They do not point"
                    " to the licence text, and the licence's other terms (such "
                    "as indicating changes) exist only in the licence."),
                "not": (
                    "In the control room the terms are fetched live from DHI's "
                    "catalogue, with the Fetch the DSP catalogue button or "
                    "under More detail › Show example object."),
            },
        "prov": {
                "rub": "How the terms follow the data",
                "intro": (
                    "On the left a value in the city's data platform, "
                    "shortened. The provenance field carries the agreement's id"
                    " (contractAgreementId). On the right the same id looked up"
                    " in the city's connector: that is where the agreement with"
                    " its distribution, status and terms lives, first in plain"
                    " words and then in ODRL. So the ODRL text is not copied "
                    "into every value. The value points to the agreement, and "
                    "the agreement carries the terms."),
                "v1": "1. The value in the CIP with its provenance label",
                "v2": "2. The agreement the id points to: the city connector's agreement (id, parties, terms) with status and address from the city's agreement register",
                "not": (
                    "Shortened examples. The field names are the real ones from"
                    " the intake service."),
            },
        "sehur": {
                "rub": "See what it looks like",
                "tips": "Three examples. Click a tab, or page through with the buttons below, to switch.",
                "foreg": "Previous", "nasta": "Next", "av": "of",
                "katFlik": "DHI's catalogue",
                "vcFlik": "The city's credential (VC)",
                "nejFlik": "No credential: error code 401",
                "katA": "Protected data",
                "katB": "Open data",
                "katText": (
                    "This is how DHI's connector describes what it shares. The "
                    "catalogue follows DCAT, the W3C standard for data "
                    "catalogues. DCAT is what the Dataspace Protocol builds "
                    "its catalogue on, and one of the standards in the EU "
                    "blueprint for data spaces (DSSC). Each dataset "
                    "carries its offer in ODRL. Here "
                    "distributions B and A are shown side by side, shortened: "
                    "note the differences in class, access, licence and terms. "
                    "Distribution B has only permissions, with the duty to "
                    "credit the source. Distribution A has a narrower "
                    "permission (use, by the city only) and also prohibitions "
                    "and obligations. Distribution A is visible in DHI's "
                    "catalogue and can only be agreed on its terms."),
                "vcText": (
                    "One of the city's three credentials: membership of the "
                    "SVADA data space. The other two state participant id and "
                    "role. The membership is signed by Svada's issuer, the "
                    "role is attested by the city itself; anyone can check "
                    "the signature, but no one can change the content."),
                "nejText": (
                    "Access control sits on reading the catalogue. Without a "
                    "valid credential DHI answers with the error code 401 "
                    "(Unauthorized): the web's standard reply when the sender "
                    "cannot prove who it is. With one, the catalogue comes "
                    "back."),
                "not": (
                    "Shortened examples written to show the shape. The terms "
                    "for distributions B and A are fetched live from DHI's "
                    "catalogue in the box above and under Show example object "
                    "further down."),
            },
        "stegradRub": "Steps:",
        "tillBilden": "↑ To the diagram",
        "seHandaRub": "See it happen",
        "skickade": "Readings sent (example):",
        "flikar": ["Chain 1–6", "Follow a value", "Audit log", "Sovereignty: KoV & ODRL", "Fault injection", "Jobs"],
        "introH": "Follow data from the model to the city's decision",
        "intro1": (
                "A data space is a way for organisations to share data without "
                "a shared database. The data stays with whoever holds it and is"
                " released only when a machine-readable agreement says yes. The"
                " terms travel with the data through the agreement's id and are"
                " checked automatically."),
        "intro2": (
                "Two organisations take part. <b>DHI</b> measures and models "
                "the data for the city. <b>The City of Gothenburg</b> owns the "
                "data. Within the city, <b>Kretslopp och Vatten (KoV)</b>, the "
                "water and sewage administration, sets the terms, and "
                "<b>Intraservice</b> runs the city's connector and data platform."),
        "ingress": (
                "Six steps from DHI's model of the overflow chambers, through a "
                "real data space between DHI and the City of Gothenburg, to the "
                "city using the data for analysis and decisions. Click a step "
                "to see what happens, why, and what the buttons do."),
        "fakta1": (
                "<b>Data space</b>: data is shared under agreements and terms, "
                "with no shared database."),
        "fakta3": "<b>All coordinates are made up.</b>",
        "omLank": "About data spaces, the EU and the demo",
        "omH": "About data spaces and the demo",
        "omVadH": "What is a data space?",
        "tillbakaKedjan": "← Back to the chain",
        "omFlik": "About the demo",
        "euH": "Part of the EU's investment in data spaces",
        "omProjH": "The work is done within the Swedish Water Data Lab",
        "omProj": ('The demo was produced within the <b>Swedish Water Data Lab</b> (the SVADA project), a project of the City of Gothenburg in cooperation with RISE. '
                   'The project is funded by the Swedish Energy Agency (Energimyndigheten), Formas, Vinnova and Water Wise Societies. '
                   '<a href="https://vattendatalabbet.se/" target="_blank" rel="noopener">Swedish Water Data Lab (in Swedish) ↗</a> · '
                   '<a href="https://www.vinnova.se/en/p/the-swedish-water-data-lab-svada--transition-for-smart-water-management" target="_blank" rel="noopener">The project at Vinnova ↗</a>'),
        "omKredH": "Created by",
        "omKred": "Björn Hagström, expert on information management and data spaces, and Niklas Fjellman.",
        "omBpH": "Follows the DSSC Blueprint 3.0",
        "omBp": ('The demo follows <b>Blueprint 3.0</b> from the Data Spaces Support Centre (DSSC), the EU reference framework for data spaces: roles (data provider, data consumer, operator), '
                 'data products, agreements and policies in ODRL, data exchange with the Dataspace Protocol and verifiable credentials. Governance, legal and business model are not part of the demo. '
                 '<a href="https://dssc.eu/" target="_blank" rel="noopener">DSSC Blueprint ↗</a>'),
        "eu1": (
                "The EU data strategy from 2020 is building common European "
                "data spaces in areas such as health, energy, mobility, "
                "agriculture and the environment (Green Deal). The aim is a "
                "single market for data, where organisations share data on "
                "terms they set themselves. The Data Governance Act and the "
                "Data Act set the legal framework, and the EU support centre "
                "DSSC describes how a data space is built."),
        "eu2": (
                "The PoC uses the same building blocks the EU recommends: "
                "connector, Dataspace Protocol, terms in ODRL and verifiable "
                "credentials. A Swedish data space for water and sewage data "
                "built this way can be connected to the European ones."),
        "introAkta": (
                "<b>Most of what you see runs for real.</b> Every step is "
                "carried out by real programs talking real standard protocols "
                "to each other, the same software that can be used in "
                "production. Each step shows which systems run and what is "
                "simplified. For the measurement data and the made-up "
                "coordinates, see <a href=\"#omdata\">About the data in the "
                "demo</a> further down."),
        "legH": "How to read the diagram",
        "legDs": (
                "<b>Data space</b>: exists to share data under agreements and "
                "terms"),
        "legPrincip": "<b>Data space principle</b> visible in the step",
        "legStatus": "<b>Green dot</b>: the step's services respond now",
        "legDist": (
                "<span class=\"tag b\">B</span> open data, without chamber "
                "positions &nbsp;·&nbsp; <span class=\"tag a\">A</span> protected"
                " data, the original with positions"),
        "omdataH": "About the data in the demo",
        "omMatH": "Measurements",
        "omMat": (
                "The Krokängsparken series (chamber SSO1_01-4526) is real measured data from an "
                "extract of the city's system, as are the chamber names. Of 91 "
                "chambers only this one has a real series; the other 90 have "
                "made-up series computed from the chamber's id. One of the 91, "
                "SSO1_01-Pump_490, is an overflow point at a pumping station."),
        "omKoordH": "Coordinates",
        "omKoord": (
                "<b>All coordinates in the demo are made up.</b> The chambers' "
                "real positions are sensitive, so the chambers are placed at "
                "random within Liseberg. The Krokängsparken chamber sits on the"
                " Lisebergsbanan roller coaster track. There is no link left to"
                " trace back to the real positions."),
        "omModellH": "The model",
        "omModell": (
                "DHI's real Future City Flow is a hydrodynamic model of the "
                "whole sewer network. It does not run in the demo. Instead a "
                "simple simulated model computes overflow volume, overflow "
                "time, mean flow and water level per chamber from the readings."
                " The results look plausible but are not real model results."),
        "omFartH": "Speed",
        "omFart": (
                "The model is built on the chamber's whole measurement series, "
                "read directly from the files. The series is the same every time, so the same day gives "
                "the same result; the made-up chambers and days vary between batches."),
        "omLiveH": "Why not live?",
        "omLive": (
                "Real measurements and positions from the sewer network are "
                "sensitive information. The demo therefore uses a data dump "
                "instead of a live connection to the sensors, and a simple "
                "calculation instead of DHI's model. Everything from the "
                "catalogue onwards is real services."),
        "ordningEtikett": "Try in this order (click to open the step; the action runs there):", "nasta": "Next", "nastaKnapp": "Next: ", "nastaSlut": "Done: you have been through the whole chain.",
        "ordning": ["Run batch", "Fetch catalogue", "Negotiate B", "Deliver B", "Negotiate A + KoV", "Deliver A", "Analyse"],
        "zon1": "At the producer",
        "zon1s": "DHI builds the data product",
        "zon2": "Data space",
        "zon2s": "agreements, terms and delivery",
        "zon3": "Use",
        "zon3s": "the city stores and uses the data",
        "banaDhi": "produces the data for the city",
        "grans": "Organisational boundary DHI | City of Gothenburg",
        "stad": "City of Gothenburg",
        "banaIs": "runs connector and platform",
        "banaKov": "owns the data and the terms",
        "kat": {"ds": "◆ Data space", "princip": "◇ Data space principle visible here", "kedja": "□ End-to-end chain"},
        "borja": "Start here ↓",
        "statusTitel": "Components responding (example)",
        "kovTitel": "KoV's decision on A",
        "kovOrg": "Kretslopp och Vatten, City of Gothenburg · part of step 3",
        "steg": "Step",
        "stang": "Close ✕",
        "stangAria": "Close the panel",
        "vad": "What happens?",
        "varfor": "Why?",
        "styrning": "Governance:",
        "dsH": {"kedja": "Is this data space?", "ds": "Why this is data space", "princip": "The data space idea in this step"},
        "prova": "Try it yourself",
        "dtGor": "What happens",
        "dtTitta": "Look for",
        "dtKraver": "Requires",
        "akta": "Genuine",
        "forenklat": "Simplified in the PoC",
        "prot": "Protocol:",
        "teknikNot": (
                "This is also where the in-depth notes on the components go, "
                "along with the Show example object button."),
        "siffrorRub": "Current figures (example)",
        "klar": "job done",
        "vantar": "job done · agreement waiting for KoV",
        "avvisad": "job done · delivery rejected",
        "ingetavtal": "job done · no agreement made",
        "fel": "failed",
        "nekad": "refused by the safeguard (as it should be)",
        "helaLogg": "Open the full log in the Jobs tab →",
        "roll": {
                "demo": "demonstrator (simulates an event)",
                "dhi": "DHI",
                "stad": "the city (Intraservice)",
                "kov": "KoV (Kretslopp och Vatten)",
            },
        "agerarSom": "You act as",
        "kovRub": "Act as KoV",
        "kovIntro": (
                "Here you make the decision as Kretslopp och Vatten. In reality"
                " a case officer at KoV does this. In the demo you do it "
                "yourself, and the control room proves the KoV role for you "
                "with a credential."),
        "kovTillA": "Make the decision as KoV in the KoV box.",
        "distNyckel": "<b>B</b> = open data (class K0R1T1, CC BY 4.0, without the chambers' positions): the agreement is made automatically. <b>A</b> = protected data (class K1R1T1, with the chambers' positions): needs KoV's approval and must not be passed on or published.",
        "kovSidlank": "Open the full KoV page (Sovereignty tab) →",
    },
}

TEKNIKTEXT = {
    "sv": {
        "rub": "Det här körs i steget",
        "akta": "Riktig tjänst",
        "forenklad": "Riktig tjänst, förenklad",
        "simulerad": "Simulerad",
        "akta_egen": "Riktig kod",
        "egen": "Egen kod i PoC:en",
        "kompEtikett": "Tjänstenamn i PoC:en (container):",
        "mer": "Mer detaljer: siffror och komponenter",
    },
    "en": {
        "rub": "What runs in this step",
        "akta": "Real service",
        "forenklad": "Real service, simplified",
        "simulerad": "Simulated",
        "akta_egen": "Real code",
        "egen": "Own code in the PoC",
        "kompEtikett": "Service names in the PoC (containers):",
        "mer": "More detail: figures and components",
    },
}

ORDTEXT = {
    "sv": {
        "flik": "Ordlista",
        "rub": "Ordlista",
        "intro": (
                "De viktigaste begreppen på sidan, i bokstavsordning. "
                "Understrukna ord i texten visar sin förklaring när du håller "
                "muspekaren över dem eller trycker på dem."),
        "tillbaka": "← Tillbaka till kedjan",
        "helaListan": "Hela ordlistan →",
    },
    "en": {
        "flik": "Glossary",
        "rub": "Glossary",
        "intro": (
                "The main terms on the page, in alphabetical order. "
                "Underlined words in the text show their explanation when you "
                "hover over or tap them."),
        "tillbaka": "← Back to the chain",
        "helaListan": "Full glossary →",
    },
}

# Ordlistan: id, regex (JavaScript-syntax) och förklaring per språk. cs=True
# betyder skiftlägeskänslig matchning. Driver både tipsrutorna och fliken Ordlista.
ORDLISTA = [
    {"id": "poc",
     "sv": {"term": "PoC (proof of concept)", "re": "PoC(?::e?n)?(?!\\p{L})", "cs": True,
            "def": "Ett bevis på att något fungerar i praktiken: här en körbar demo i liten skala av hela kedjan, med riktiga komponenter men utan att vara en driftsatt tjänst."},
     "en": {"term": "PoC (proof of concept)", "re": "PoC", "cs": True,
            "def": "A proof that something works in practice: here a small-scale, runnable demo of the whole chain, with real components but not a deployed service."}},
    {"id": "braddbrunn",
     "sv": {"term": "Bräddbrunn",
            "re": "bräddbrunn\\p{L}*",
            "def": (
                    "En brunn i avloppsnätet där vattnet kan rinna över till "
                    "ett utsläpp när ledningen är full. Här sitter givaren som "
                    "mäter.")},
     "en": {"term": "Overflow chamber",
            "re": "overflow chambers?",
            "def": (
                    "A chamber in the sewer network where water can spill over "
                    "to an outlet when the pipe is full. This is where the "
                    "measuring sensor sits.")},
    },
    {"id": "bradd",
     "sv": {"term": "Bräddning, brädda",
            "re": "brädd(?:ning\\p{L}*|ar|ade|a(?!\\p{L})|händelse\\p{L}*|flöde\\p{L}*|data)",
            "def": (
                    "När avloppsledningen är full, till exempel vid kraftigt "
                    "regn, rinner en del av avloppsvattnet över och ut i ett "
                    "vattendrag i stället för till reningsverket. Det kallas "
                    "att det bräddar. Bräddning ska hållas så liten som "
                    "möjligt.")},
     "en": {"term": "Overflow",
            "re": "overflows?(?! chamber)(?! data)|overflowing",
            "def": (
                    "When the sewer pipe is full, for example in heavy rain, "
                    "some of the sewage spills over into a watercourse instead "
                    "of going to the treatment plant. Overflow should be kept "
                    "as small as possible.")},
    },
    {"id": "spillflode",
     "sv": {"term": "Spillflöde",
            "re": "spillflöde\\p{L}*",
            "def": (
                    "Den del av flödet som bräddar ut, mätt i kubikmeter per "
                    "sekund (m³/s).")},
     "en": {"term": "Spill flow",
            "re": "spill flow",
            "def": (
                    "The part of the flow that overflows, measured in cubic "
                    "metres per second (m³/s).")},
    },
    {"id": "totalflode",
     "sv": {"term": "Totalflöde",
            "re": "totalflöde\\p{L}*",
            "def": "Allt vatten som rinner genom brunnen, mätt i m³/s."},
     "en": {"term": "Total flow",
            "re": "total flow",
            "def": "All water flowing through the chamber, measured in m³/s."},
    },
    {"id": "eudataspace",
     "lank": "https://digital-strategy.ec.europa.eu/en/policies/data-spaces",
     "sv": {"term": "Gemensamma europeiska dataspaces",
            "re": "europeiska dataspace\\p{L}*|Common European Data Spaces",
            "def": (
                    "EU:s satsning, enligt datastrategin från 2020, på "
                    "dataspaces inom bland annat hälsa, energi, mobilitet, "
                    "jordbruk och miljö. Bygger på gemensamma regler och "
                    "byggstenar så att dataspaces kan kopplas ihop.")},
     "en": {"term": "Common European data spaces",
            "re": "common European data spaces|European ones",
            "def": (
                    "The EU initiative, under the 2020 data strategy, for data "
                    "spaces in areas such as health, energy, mobility, "
                    "agriculture and the environment. Built on shared rules and"
                    " building blocks so data spaces can be connected.")},
    },
    {"id": "dsp",
     "lank": "https://eclipse-dataspace-protocol-base.github.io/DataspaceProtocol/",   # specifikationen (L21)
     "sv": {"term": "Dataspace Protocol (DSP)",
            "re": "Dataspace Protocol|DSP(?!\\p{L})",
            "cs": True,
            "def": (
                    "Standardprotokollet som connectorer använder för att visa "
                    "katalog, förhandla avtal och styra överföringar.")},
     "en": {"term": "Dataspace Protocol (DSP)",
            "re": "Dataspace Protocol|DSP(?!\\p{L})",
            "cs": True,
            "def": (
                    "The standard protocol connectors use to show catalogues, "
                    "negotiate agreements and control transfers.")},
    },
    {"id": "dataspace",
     "lank": "https://dssc.eu/",
     "sv": {"term": "Dataspace",
            "re": "dataspace\\p{L}*",
            "def": (
                    "Ett sätt för organisationer att dela data utan gemensam "
                    "databas. Data ligger kvar hos den som har det och lämnas "
                    "ut först när ett maskinellt avtal säger ja. Villkoren "
                    "följer med och kontrolleras automatiskt.")},
     "en": {"term": "Data space",
            "re": "data spaces?",
            "def": (
                    "A way for organisations to share data without a shared "
                    "database. Data stays with whoever holds it and is released"
                    " only when a machine-readable agreement says yes. The "
                    "terms travel with it and are checked automatically.")},
    },
    {"id": "connector",
     "sv": {"term": "Connector",
            "re": "connector\\p{L}*",
            "def": (
                    "Programvaran varje part kör för att delta i dataspacet. "
                    "Den visar katalog, förhandlar avtal och styr överföringar."
                    " Här används Eclipse EDC.")},
     "en": {"term": "Connector",
            "re": "connectors?",
            "def": (
                    "The software each party runs to take part in the data "
                    "space. It shows the catalogue, negotiates agreements and "
                    "controls transfers. Eclipse EDC is used here.")},
    },
    {"id": "edc",
     "lank": "https://projects.eclipse.org/projects/technology.edc",
     "sv": {"term": "Eclipse EDC",
            "re": "Eclipse EDC|EDC(?!\\p{L})",
            "cs": True,
            "def": (
                    "Connector med öppen källkod från Eclipse Foundation, en "
                    "vanlig grund för dataspaces i EU.")},
     "en": {"term": "Eclipse EDC",
            "re": "Eclipse EDC|EDC(?!\\p{L})",
            "cs": True,
            "def": (
                    "Open-source connector from the Eclipse Foundation, a "
                    "common basis for data spaces in the EU.")},
    },
    {"id": "odrl",
     "lank": "https://www.w3.org/TR/odrl-model/",
     "sv": {"term": "ODRL",
            "re": "ODRL",
            "cs": True,
            "def": (
                    "W3C-standard för maskinläsbara användningsvillkor: vad som"
                    " är tillåtet, vad som är förbjudet och vilka skyldigheter "
                    "som gäller.")},
     "en": {"term": "ODRL",
            "re": "ODRL",
            "cs": True,
            "def": (
                    "W3C standard for machine-readable usage terms: what is "
                    "permitted, what is prohibited and which duties apply.")},
    },
    {"id": "intyg",
     "lank": "https://www.w3.org/TR/vc-data-model-2.0/",
     "sv": {"term": "Verifierbart intyg",
            "re": "verifierbar\\p{L}* intyg\\p{L}*|intyg\\p{L}*|rollintyg\\p{L}*|VC(?![\\p{L}\\p{N}])",
            "def": (
                    "Digitalt intyg med kryptografisk signatur (W3C Verifiable "
                    "Credential, VC) som bevisar vem en part är eller vilken "
                    "roll den har. En grundteknik i dataspaces: intygen visas "
                    "och kontrolleras i varje led, enligt protokollet DCP.")},
     "en": {"term": "Verifiable credential",
            "re": "verifiable credentials?|credentials?|VCs?(?![\\p{L}\\p{N}])",
            "def": (
                    "A digital certificate with a cryptographic signature (W3C "
                    "Verifiable Credential, VC) that proves who a party is or "
                    "which role it holds. A basic technique in data spaces: the "
                    "credentials are shown and checked at every step, under the "
                    "protocol DCP.")},
    },
    {"id": "dssc",
     "lank": "https://dssc.eu/",
     "sv": {"term": "DSSC",
            "re": "DSSC",
            "cs": True,
            "def": (
                    "Data Spaces Support Centre, EU:s stödcentrum för "
                    "dataspaces. Förvaltar referensramen (Blueprint) med "
                    "byggblock som PoC:en jämförs mot.")},
     "en": {"term": "DSSC",
            "re": "DSSC",
            "cs": True,
            "def": (
                    "Data Spaces Support Centre, the EU support centre for data"
                    " spaces. It maintains the reference framework (Blueprint) "
                    "whose building blocks the PoC is compared against.")},
    },
    {"id": "ngsild",
     "lank": "https://en.wikipedia.org/wiki/NGSI-LD",
     "sv": {"term": "NGSI-LD",
            "re": "NGSI-LD",
            "cs": True,
            "def": (
                    "Standard för att beskriva saker och deras tillstånd över "
                    "tid, till exempel en brunn och dess flöde.")},
     "en": {"term": "NGSI-LD",
            "re": "NGSI-LD",
            "cs": True,
            "def": (
                    "A standard for describing things and their state over "
                    "time, such as a chamber and its flow.")},
    },
    {"id": "kontextbroker",
     "lank": "https://github.com/FIWARE/context.Orion-LD",
     "sv": {"term": "Kontextbroker",
            "re": "kontextbroker\\p{L}*",
            "def": (
                    "Databas som håller det senaste tillståndet för saker, här "
                    "brunnar, och svarar på NGSI-LD. Här används Orion-LD.")},
     "en": {"term": "Context broker",
            "re": "context brokers?",
            "def": (
                    "A database holding the latest state of things, here "
                    "chambers, answering in NGSI-LD. Orion-LD is used here.")},
    },
    {"id": "fiware",
     "lank": "https://www.fiware.org/",
     "sv": {"term": "FIWARE",
            "re": "FIWARE",
            "cs": True,
            "def": (
                    "Öppen plattform med komponenter för smarta städer, bland "
                    "annat Orion-LD och Mintaka.")},
     "en": {"term": "FIWARE",
            "re": "FIWARE",
            "cs": True,
            "def": (
                    "Open platform with components for smart cities, including "
                    "Orion-LD and Mintaka.")},
    },
    {"id": "dataprodukt",
     "sv": {"term": "Dataprodukt",
            "re": "dataprodukt\\p{L}*",
            "def": (
                    "Data som paketerats tillsammans med beskrivning, klassning"
                    " och användningsvillkor, så att det kan delas som en "
                    "enhet.")},
     "en": {"term": "Data product",
            "re": "data products?",
            "def": (
                    "Data packaged together with a description, classification "
                    "and usage terms, so it can be shared as one unit.")},
    },
    {"id": "klass",
     "sv": {"term": "Informationsklass (K1R1T1, K0R1T1)",
            "re": "K[01]R1T1|informationsklass\\p{L}*|klassning\\p{L}*",
            "def": (
                    "Stadens klassning av information efter konfidentialitet "
                    "(K), riktighet (R) och tillgänglighet (T). K1 betyder "
                    "känslig, K0 betyder öppen.")},
     "en": {"term": "Information class (K1R1T1, K0R1T1)",
            "re": "K[01]R1T1|information class\\p{L}*|classification",
            "def": (
                    "The city's classification of information by "
                    "confidentiality (K), integrity (R) and availability (T). "
                    "K1 means sensitive, K0 means open.")},
    },
    {"id": "kov",
     "sv": {"term": "KoV",
            "re": "KoV(?!-gate)",
            "cs": True,
            "def": (
                    "Kretslopp och Vatten, Göteborgs Stads förvaltning för "
                    "vatten och avlopp. Äger data och sätter villkoren, som "
                    "binder den som tar emot data.")},
     "en": {"term": "KoV",
            "re": "KoV(?! gate)",
            "cs": True,
            "def": (
                    "Kretslopp och Vatten, the City of Gothenburg's water and "
                    "sewage administration. Owns the data and sets the terms, "
                    "which bind whoever receives the data.")},
    },
    {"id": "intraservice",
     "sv": {"term": "Intraservice",
            "re": "Intraservice",
            "cs": True,
            "def": (
                    "Göteborgs Stads förvaltning för digitala tjänster. Driver "
                    "stadens connector och dataplattform och tar emot data på "
                    "KoV:s uppdrag, bunden av KoV:s villkor.")},
     "en": {"term": "Intraservice",
            "re": "Intraservice",
            "cs": True,
            "def": (
                    "The City of Gothenburg's digital services administration. "
                    "Runs the city's connector and data platform and receives "
                    "data on KoV's behalf, bound by KoV's terms.")},
    },
    {"id": "dhi",
     "lank": "https://www.dhigroup.com/",
     "sv": {"term": "DHI",
            "re": "DHI(?!:)",
            "cs": True,
            "def": (
                    "Konsultföretag inom vatten som tar fram data åt staden med"
                    " modellen Future City Flow.")},
     "en": {"term": "DHI",
            "re": "DHI(?!')",
            "cs": True,
            "def": (
                    "Water engineering consultancy that produces the data for "
                    "the city with the Future City Flow model.")},
    },
    {"id": "fcf",
     "lank": "https://www.dhigroup.com/se/teknologier/future-city-flow",
     "sv": {"term": "Future City Flow",
            "re": "Future City Flow",
            "cs": True,
            "def": (
                    "DHI:s modell för flöden och bräddning i avloppsnätet. I "
                    "PoC:en ersatt av en simulerad, enkel beräkning.")},
     "en": {"term": "Future City Flow",
            "re": "Future City Flow",
            "cs": True,
            "def": (
                    "DHI's model for flows and overflow in the sewer network. "
                    "Replaced in the PoC by a simple simulated calculation.")},
    },
    {"id": "batch",
     "sv": {"term": "Batch",
            "re": "batch\\p{L}*",
            "def": (
                    "En omgång beräknade data, här ett modellerat dygn för alla"
                    " brunnar. Datumet sist i batch-id:t (till exempel"
                    " batch-015-2026-06-29) är det modellerade dygnet, inte"
                    " när batchen kördes.")},
     "en": {"term": "Batch",
            "re": "batch(?:es)?",
            "def": (
                    "One round of computed data, here a modelled day for all "
                    "chambers. The date at the end of the batch id (for example "
                    "batch-015-2026-06-29) is the modelled day, not when the "
                    "batch was run.")},
    },
    {"id": "modellerat-dygn",
     "sv": {"term": "Modellerat dygn",
            "re": "modellerade? dygn\\p{L}*",
            "def": (
                    "Det dygn en batch avser. Demon visar inte mätningar i"
                    " realtid: modellen räknar fram ett nytt dygn för varje"
                    " batch (här en var tionde minut), och datumet står i"
                    " batch-id:t. Det är alltså inte dagens datum och inte"
                    " tiden då batchen kördes.")},
     "en": {"term": "Modelled day",
            "re": "modelled days?",
            "def": (
                    "The day a batch covers. The demo does not show"
                    " measurements in real time: the model computes a new day"
                    " for each batch (here one every ten minutes), and the date"
                    " is in the batch id. It is neither today's date nor the"
                    " time the batch was run.")},
    },
    {"id": "dsga",
     "sv": {"term": "DSGA",
            "re": "DSGA(?: 0\\.1)?",
            "cs": True,
            "def": "Data Space Governance Authority: den part som styr ett dataspace, med regler, medlemmar och intyg. I demon spelas den av Svadas utfärdare (version 0.1)."},
     "en": {"term": "DSGA",
            "re": "DSGA(?: 0\\.1)?",
            "cs": True,
            "def": "Data Space Governance Authority: the party that governs a data space, with rules, members and credentials. In the demo it is played by the Svada issuer (version 0.1)."}},
    {"id": "cip",
     "sv": {"term": "CIP",
            "re": "CIP(?!-)",
            "cs": True,
            "def": (
                    "Stadens dataplattform (City Information Platform) där data"
                    " lagras och delas vidare.")},
     "en": {"term": "CIP",
            "re": "CIP(?!-)",
            "cs": True,
            "def": (
                    "The city's data platform (City Information Platform), "
                    "where data is stored and shared onwards.")},
    },
    {"id": "proveniens",
     "lank": "https://www.w3.org/TR/prov-overview/",
     "sv": {"term": "Ursprungsmärkning (proveniens)",
            "re": "ursprungsmärkning\\p{L}*|proveniens\\p{L}*",
            "def": (
                    "Uppgifter som följer med varje värde om varifrån det "
                    "kommer: avtal, batch, distribution och klass.")},
     "en": {"term": "Provenance",
            "re": "provenance",
            "def": (
                    "Information attached to every value about where it came "
                    "from: agreement, batch, distribution and class.")},
    },
    {"id": "dcat",
     "lank": "https://docs.dataportal.se/dcat/sv/",
     "sv": {"term": "DCAT-AP-SE",
            "re": "DCAT-AP(?:-SE)?",
            "cs": True,
            "def": (
                    "Den svenska nationella profilen av DCAT-AP, EU:s "
                    "gemensamma standard för att beskriva datamängder i "
                    "kataloger, till exempel för Sveriges och EU:s portaler. "
                    "Används inte i demon: DHI:s katalog bygger på DCAT i "
                    "den form Dataspace Protocol beskriver.")},
     "en": {"term": "DCAT-AP-SE",
            "re": "DCAT-AP(?:-SE)?",
            "cs": True,
            "def": (
                    "The Swedish national profile of DCAT-AP, the EU's common "
                    "standard for describing datasets in catalogues, for example "
                    "for Swedish and EU portals. Not used in the demo: "
                    "DHI's catalogue is built on DCAT in the form the "
                    "Dataspace Protocol describes.")},
    },
    {"id": "dcatbegrepp",
     "lank": "https://www.w3.org/TR/vocab-dcat-3/",
     "sv": {"term": "DCAT",
            "re": "DCAT(?![-\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Data Catalog Vocabulary, W3C:s standard för att beskriva "
                    "datamängder och kataloger så att de kan läsas av maskiner. "
                    "I demon beskrivs dataprodukten i DCAT i den form "
                    "Dataspace Protocol använder i DHI:s katalog. Profilerna "
                    "DCAT-AP och DCAT-AP-SE bygger på DCAT.")},
     "en": {"term": "DCAT",
            "re": "DCAT(?![-\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Data Catalog Vocabulary, the W3C standard for describing "
                    "datasets and catalogues so that machines can read them. "
                    "In the demo the data product is described in DCAT in the "
                    "form the Dataspace Protocol uses in DHI's catalogue. The "
                    "profiles DCAT-AP and DCAT-AP-SE build on DCAT.")},
    },
    {"id": "dcp",
     "lank": "https://eclipse-dataspace-dcp.github.io/decentralized-claims-protocol/",
     "sv": {"term": "Decentralized Claims Protocol (DCP)",
            "re": "DCP(?![\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Protokollet för hur en part visar upp verifierbara intyg "
                    "för en annan part i ett dataspace, utan en central "
                    "tjänst. Demon använder det för att kontrollera medlemskap, "
                    "deltagare och roller.")},
     "en": {"term": "Decentralized Claims Protocol (DCP)",
            "re": "DCP(?![\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "The protocol for how one party presents verifiable "
                    "credentials to another in a data space, without a central "
                    "service. The demo uses it to check membership, participants "
                    "and roles.")},
    },
]


# Gränssnittstexter som inte kommer ur mockupen, eller som rättats mot koden
# (mockupens exempelsiffror och "mockup"-anmärkningar är ersatta av levande
# värden). Läggs ovanpå TEXTER ovan.
_EXTRA = {
    "sv": {
        "under": "Från DHI:s modell av bräddbrunnarna till stadens beslut.",
        "hamtar": "hämtar status …",
        "sammanfattning": "{uppe} av {totalt} övervakade tjänster svarar · uppdaterad {tid}",
        "faktaAkta": ("<b>{a} riktiga delar</b> kör kedjan. Simulerat: "
                      "modellberäkningen och Svadas utfärdare."),
        "stapel": ("<b>{a} riktiga delar</b> och {f} riktiga men "
                   "förenklade. {r} delar är simulerade: modellberäkningen, "
                   "som står i för DHI:s riktiga Future City Flow och bygger "
                   "på en brunns mätserie ur en datadump, och Svadas utfärdare, som "
                   "simulerar dataspacets tillitstjänst (DSGA 0.1). "
                   "Delarna är programvarorna och "
                   "den egna koden som listas under Det här körs i steget. "
                   "De är fler än de komponenter som statusraden överst "
                   "följer, eftersom en komponent kan innehålla flera delar "
                   "och en del, som uppdelningen i B och A, är kod och ingen "
                   "egen tjänst."),
        "statusTitel": "Stegets komponenter: grön svarar, gul svarar delvis, "
                       "röd svarar inte",
        "statusNamn": {"upp": "Alla komponenter i steget svarar",
                       "delvis": "Bara en del av stegets komponenter svarar",
                       "ned": "Ingen av stegets komponenter svarar",
                       "okänd": "Status är inte läst ännu"},
        "flikarRub": "Flikar",
        "legStatus": ("<b>Statuspunkt</b>: grön när stegets tjänster svarar, "
                      "gul när bara en del svarar, röd när ingen svarar"),
        "skickade": "Skickade mätvärden:",
        "siffrorRub": "Siffror just nu",
        "teknikNot": ("Under Visa exempelobjekt syns objektet som passerar "
                      "steget, hämtat live."),
        "stegAv": "Steg {n} av 6",
        "loggRub": "Jobb {id}",
        "tidigare1": "… 1 tidigare rad",
        "tidigareN": "… {n} tidigare rader",
        "helaSidan": "Hela sidan: {f} →",
        "jobbKor": "kör …",
        "jobbPagar": "Jobb {id} pågår: {etikett} …",
        "jobbKo": "i kö",
        "jobbRadKo": "<b>I kö:</b> {etikett} (jobb {id}) väntar på sin tur, plats {plats} …",
        "jobbStartar": "startar …",
        "jobbFelStart": "Kunde inte starta: {fel}",
        "jobbSvararInte": "Jobbet svarar inte: {fel}",
        "kovVantar": "Väntar på beslut: en förhandling om distribution A ({id}).",
        "kovVantarN": ("Väntar på beslut: {n} förhandlingar om distribution "
                       "A. Beslutet gäller den senaste ({id})."),
        "kovInget": "Inget väntar på beslut.",
        "kovFel": "Kunde inte läsa KoV-kön: {fel}",
        "kovAvtal": ("Gällande avtal om A: {id} · Ett avtal gäller tills det "
                     "hävs eller löper ut (30 dagar)."),
        "kovAvtalN": ("Gällande avtal om A: {n} st, det senaste är {id}. "
                      "Ett avtal gäller tills det hävs eller löper ut."),
        "kovIngetAvtal": "Inget gällande avtal om A.",
        "kovIngetStart": " Kör Förhandla A för att skapa en begäran att besluta om.",
        "avtalFel": "Kunde inte läsa avtalsregistret: {fel}",
        "odrlLive": "Hämtat live från DHI:s katalog.",
        "odrlStatisk": ("Katalogen svarar inte just nu. Reglerna nedan är "
                        "de som registrerats hos DHI, men de är inte "
                        "hämtade live."),
        "provLive": ("Värdet och avtalet är hämtade live: värdet ur stadens "
                     "dataplattform (distribution B) och avtalet ur stadens "
                     "connector."),
        "svarar": "svarar",
        "tidUtc": "tider i UTC",
        "ladda": "hämtar …",
        "kunde": "kunde inte hämtas",
        "jobbRad": "<b>Kör:</b> {etikett} (jobb {id}) …",
        "visaExempel": "Visa exempelobjekt",
        "ingangarRub": "Publika ingångar",
        "ingangarText": ("Det här är adresserna du som besökare når. Resten "
                         "av kedjan är inte nåbar utifrån: kontrollrummet "
                         "anropar den åt dig på servern, och bara genom "
                         "kontrakten."),
        "nasRub": "Så här når kontrollrummet komponenterna",
        "nasText": ("Alla anrop går över värdens publicerade portar, samma "
                    "endpoints som en människa skulle anropa. Kontrollrummet "
                    "ligger därför inte på DHI:s eller stadens interna nät "
                    "och kan inte se något som inte redan är exponerat. Det "
                    "är också därför det aldrig kan läsa distribution A "
                    "förbi kontraktet."),
        "sidfot1": "SVADA PoC.",
        "sidfot2": ("Kontrollrummet läser och utlöser, men flyttar aldrig data "
                    "förbi avtalet. Den skyddade distributionen A lämnar DHI "
                    "bara efter KoV:s godkännande, och går inte att läsa ur stadens plattform utan ett gällande avtal."),
        "pub_kontrollrum": "Kontrollrummet",
        "pub_brunnar": "Öppna data (B) – läsbar webbsida",
        "pub_tidsserie": "Öppna data (B) – tidsserier (NGSI-LD-API)",
        "pub_cip": ("Stadens dataplattform – skyddade data (A) kräver "
                    "behörighet"),
        "kolKomponent": "Komponent",
        "kolAdress": "Adress",
    },
    "en": {
        "under": "From DHI's model of the overflow chambers to the city's "
                 "decisions.",
        "hamtar": "fetching status …",
        "sammanfattning": "{uppe} of {totalt} monitored services responding · "
                          "updated {tid}",
        "faktaAkta": ("<b>{a} real parts</b> run the chain. Simulated: "
                      "the model calculation and Svada's issuer."),
        "stapel": ("<b>{a} real parts</b> and {f} real but simplified. "
                   "{r} parts are simulated: the model calculation, standing "
                   "in for DHI's real Future City Flow and built on one "
                   "chamber's measurement series from a data dump, and "
                   "Svada's issuer, which simulates the data "
                   "space's trust service (DSGA 0.1). "
                   "The parts are the software and own code listed "
                   "under What runs in this step. They outnumber the "
                   "components the status line at the top follows, because "
                   "one component can contain several parts and some parts, "
                   "like the split into B and A, are code rather than a "
                   "service of their own."),
        "statusTitel": "The step's components: green responding, yellow "
                       "partly responding, red not responding",
        "statusNamn": {"upp": "All components in the step respond",
                       "delvis": "Only some of the step's components respond",
                       "ned": "None of the step's components respond",
                       "okänd": "Status not read yet"},
        "flikarRub": "Tabs",
        "legStatus": ("<b>Status dot</b>: green when the step's services "
                      "respond, yellow when only some do, red when none do"),
        "skickade": "Readings sent:",
        "siffrorRub": "Current figures",
        "teknikNot": ("Under Show example object you see the object that "
                      "passes through the step, fetched live."),
        "stegAv": "Step {n} of 6",
        "loggRub": "Job {id}",
        "tidigare1": "… 1 earlier line",
        "tidigareN": "… {n} earlier lines",
        "helaSidan": "Full page: {f} →",
        "jobbKor": "running …",
        "jobbPagar": "Job {id} is running: {etikett} …",
        "jobbKo": "queued",
        "jobbRadKo": "<b>Queued:</b> {etikett} (job {id}) is waiting for its turn, place {plats} …",
        "jobbStartar": "starting …",
        "jobbFelStart": "Could not start: {fel}",
        "jobbSvararInte": "The job does not respond: {fel}",
        "kovVantar": "Waiting for a decision: one negotiation for distribution A ({id}).",
        "kovVantarN": ("Waiting for a decision: {n} negotiations for "
                       "distribution A. The decision applies to the latest "
                       "({id})."),
        "kovInget": "Nothing is waiting for a decision.",
        "kovFel": "Could not read the KoV queue: {fel}",
        "kovAvtal": ("Current agreement for A: {id} · An agreement is valid "
                     "until it is revoked or expires (30 days)."),
        "kovAvtalN": ("Current agreements for A: {n}, the latest is {id}. An "
                      "agreement is valid until it is revoked or expires."),
        "kovIngetAvtal": "No current agreement for A.",
        "kovIngetStart": " Run Negotiate A to create a request to decide on.",
        "avtalFel": "Could not read the agreement register: {fel}",
        "odrlLive": "Fetched live from DHI's catalogue.",
        "odrlStatisk": ("The catalogue is not responding right now. The rules "
                        "below are the ones registered at DHI, but they are "
                        "not fetched live."),
        "provLive": ("The value and the agreement are fetched live: the value "
                     "from the city's data platform (distribution B) and the "
                     "agreement from the city's connector."),
        "svarar": "responding",
        "tidUtc": "times in UTC",
        "ladda": "fetching …",
        "kunde": "could not be fetched",
        "jobbRad": "<b>Running:</b> {etikett} (job {id}) …",
        "visaExempel": "Show example object",
        "ingangarRub": "Public entry points",
        "ingangarText": ("These are the addresses you reach as a visitor. "
                         "The rest of the chain cannot be reached from "
                         "outside: the control room calls it for you on the "
                         "server, and only through the contracts."),
        "nasRub": "How the control room reaches the components",
        "nasText": ("All calls go through the host's published ports, the "
                    "same endpoints a person would call. The control room "
                    "therefore sits on neither DHI's nor the city's internal "
                    "network and cannot see anything that is not already "
                    "exposed. That is also why it can never read "
                    "distribution A past the contract."),
        "sidfot1": "SVADA PoC.",
        "sidfot2": ("The control room reads and triggers, but never moves "
                    "data past the agreement. The protected distribution A "
                    "leaves DHI only after KoV's approval, and cannot be read from the city's platform without a current agreement."),
        "pub_kontrollrum": "The control room",
        "pub_brunnar": "Open data (B) – readable web page",
        "pub_tidsserie": "Open data (B) – time series (NGSI-LD API)",
        "pub_cip": ("The city's data platform – protected data (A) requires "
                    "authorisation"),
        "kolKomponent": "Component",
        "kolAdress": "Address",
    },
}
for _sp in SPRAK:
    TEXTER[_sp].update(_EXTRA[_sp])
TEXTER["sv"]["odrl"]["not"] = (
    "Villkoren hämtas live från DHI:s katalog, med samma anrop som knappen "
    "Hämta DSP-katalogen. Stadens identitet står i klartext som ”Göteborgs "
    "Stad”.")
TEXTER["en"]["odrl"]["not"] = (
    "The terms are fetched live from DHI's catalogue, with the same call as "
    "the Fetch the DSP catalogue button. The city's identity is shown in "
    "plain words as “the City of Gothenburg”.")
# Förkortade exempel som visas i panelen (steg 2 och 8). Siffror och id:n är
# exempel; kontrollrummet visar de riktiga svaren under Visa exempelobjekt.
_EX_KAT_A = """{
  "@id": "modellerad-bradddata-a",
  "@type": "dcat:Dataset",
  "name": "Modellerad bräddata (A)",
  "informationClass": "K1R1T1",
  "accessRights": "non-public",
  "license": "Not an open licence – bilateral agreement",
  "odrl:hasPolicy": {
    "@type": "odrl:Offer",
    "permission": [{ "action": "odrl:use",
      "constraint": [{ "leftOperand": "svada:deltagare",
        "operator": "odrl:eq",
        "rightOperand": "did:web:identity-hub-stad…" },
        { "leftOperand": "edc:inForceDate", "operator": "odrl:gteq",
        "rightOperand": "contractAgreement+0s" },
        { "leftOperand": "edc:inForceDate", "operator": "odrl:lteq",
        "rightOperand": "contractAgreement+30d" }] }],
    "prohibition": [
      { "action": "odrl:distribute" },
      { "action": "odrl:publish" } ],
    "obligation": [{ "action": "svada:kovGodkannande" },
                   { "action": "svada:medgerGranskning" }]
  },
  "dcat:distribution": [{
    "dct:format": "HttpData-PUSH",
    "dcat:accessService": "DHI:s connector"
  }]
}"""

_EX_KAT_B = """{
  "@id": "modellerad-bradddata-b",
  "@type": "dcat:Dataset",
  "name": "Modellerad bräddata (B)",
  "informationClass": "K0R1T1",
  "accessRights": "public",
  "license": "CC BY 4.0",
  "odrl:hasPolicy": {
    "@type": "odrl:Offer",
    "permission": [
      { "action": "odrl:use",
        "duty": [{ "action": "odrl:attribute" }] },
      { "action": "odrl:distribute" },
      { "action": "odrl:publish" }
    ]
  },
  "dcat:distribution": [{
    "dct:format": "HttpData-PUSH",
    "dcat:accessService": "DHI:s connector"
  }]
}"""

_EX_VC = """{
  "type": [ "VerifiableCredential", "SvadaMembershipCredential" ],
  "issuer": "did:web:identity-hub-svada…",
  "issuanceDate": "2026-10-06T08:00:00Z",
  "expirationDate": "2027-10-06T08:00:00Z",
  "credentialSubject": {
    "id": "did:web:identity-hub-stad…",
    "dataspaceId": "svada"
  }
}
// Skickas som en signerad JWT. Mottagaren kontrollerar
// signaturen mot utfärdarens publika nyckel i dess DID-dokument."""

_EX_401 = """# 1. Staden frågar efter katalogen UTAN intyg
POST /protocol/2025-1/catalog/request   (till DHI:s connector)
→ 401 Unauthorized

# 2. Samma fråga MED en presentation av stadens intyg
POST /protocol/2025-1/catalog/request
Authorization: <token som pekar på stadens intyg>
→ 200 OK  + katalogen ovan"""

_ODRL_A = """{
  "@type": "Set",
  "permission": [{
    "action": "odrl:use",
    "constraint": [{
      "leftOperand": "svada:deltagare",
      "operator": "odrl:eq",
      "rightOperand": "did:web:identity-hub-stad…"
    }, {
      "leftOperand": "edc:inForceDate", "operator": "odrl:gteq",
      "rightOperand": "contractAgreement+0s"
    }, {
      "leftOperand": "edc:inForceDate", "operator": "odrl:lteq",
      "rightOperand": "contractAgreement+30d"
    }]
  }],
  "prohibition": [
    { "action": "odrl:distribute" },
    { "action": "odrl:publish" }
  ],
  "obligation": [
    { "action": "svada:kovGodkannande" },
    { "action": "svada:medgerGranskning" }
  ]
}"""

_ODRL_B = """{
  "@type": "Set",
  "permission": [
    { "action": "odrl:use",
      "duty": [{ "action": "odrl:attribute" }] },
    { "action": "odrl:distribute" },
    { "action": "odrl:publish" }
  ],
  "prohibition": [],
  "obligation": []
}"""

_EX_PROV = """{
  "id": "urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526",
  "type": "SewerOverflowModelB",
  "overflowVolumeM3": { "type": "Property", "value": 412.7 },
  "overflowDurationMin": { "type": "Property", "value": 95 },
  "provenance": { "type": "Property", "value": {
    "contractAgreementId": "ef83…",
    "dataset": "Modellerad bräddata",
    "distribution": "B",
    "batchId": "batch-006-2026-06-18",
    "accessRights": "public",
    "informationClass": "K0R1T1",
    "license": "CC BY 4.0",
    "receivedVia": "Eclipse EDC transfer (Dataspace Protocol)"
  } }
}"""

_EX_AVTAL = """GET …/contractagreements/ef83…   (stadens connector)
{
  "@id": "ef83…",
  "distribution": "B",
  "status": "GALLANDE",
  "villkorIKlartext": [
    "permission: use: får användas …",
    "duty: attribute: … om källan anges",
    "permission: distribute: får spridas vidare",
    "permission: publish: får publiceras"
  ],
  "assetId": "modellerad-bradddata-b",
  "providerId": "DHI",
  "consumerId": "Göteborgs Stad",
  "contractSigningDate": 1791230400,
  "policy": {
    "permission": [ use (duty: attribute), distribute, publish ]
  }
}"""

# Exemplen ovan är skrivna på svenska. På den engelska sidan byts förklaringarna i
# dem (kommentarer och namn på parter), medan data (id:n, fältnamn, värden) ligger
# kvar oförändrat.
_EXEMPEL_EN = [
    ("(till DHI:s connector)", "(to DHI's connector)"),
    ("DHI:s connector", "DHI's connector"),
    ("(stadens connector)", "(the city's connector)"),
    ("Göteborgs Stad", "City of Gothenburg"),
    ("får användas …", "may be used …"),
    ("… om källan anges", "… if the source is credited"),
    ("får spridas vidare", "may be passed on"),
    ("får publiceras", "may be published"),
    ("# 1. Staden frågar efter katalogen UTAN intyg", "# 1. The city asks for the catalogue WITHOUT a credential"),
    ("# 2. Samma fråga MED en presentation av stadens intyg", "# 2. The same request WITH a presentation of the city's credential"),
    ("<token som pekar på stadens intyg>", "<token pointing to the city's credential>"),
    ("+ katalogen ovan", "+ the catalogue above"),
    ("// Skickas som en signerad JWT. Mottagaren kontrollerar", "// Sent as a signed JWT. The recipient checks the"),
    ("// signaturen mot utfärdarens publika nyckel i dess DID-dokument.", "// signature against the issuer's public key in its DID document."),
]


def _ex_sprak(text, sprak):
    """Översätter förklaringarna i ett exempel till engelska; data rörs inte."""
    if sprak != "en":
        return text
    for sv, en in _EXEMPEL_EN:
        text = text.replace(sv, en)
    return text


STIL = """
/* Endast ljust tema, vit bakgrund (color-scheme: light, inget mörkt läge).
   Layout: kontrollrummets sidhuvud överst, sedan en kedjebild i simbanor
   (organisationer som rader, steg 1–10 som kolumner, dataspace-zonen som
   tonat fält) och en panel under bilden för valt steg. Under 900px blir
   bilden en lodrät lista och panelen öppnas direkt under det klickade steget. */
:root {
  --bg: #ffffff;          /* vit bakgrund överallt (2026-10-06) */
  color-scheme: light;
  --yta: #ffffff;
  --fg: #1d2421;
  --dov: #47504c;
  --ram: #d3d9d5;
  --ds: #4c3ca7;          /* dataspace / kontrollplan, samma lila som processöverblicken */
  --ds-ton: #eeebfa;
  --ds-ram: #b9b0e6;
  --kedja: #255845;       /* helhetskedjan */
  --kedja-ton: #e7f1ec;
  --a: #99201a;           /* Distribution A, känslig */
  --b: #175b24;           /* Distribution B, öppen */
  --gran: #564aa8;
  --upp: #175b24;
  --fokus: #0848a6;
  --kod: #eef0ee;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 15px; line-height: 1.5; }
h1, h2, h3 { text-wrap: balance; line-height: 1.25; }
button { font: inherit; color: inherit; }
:focus-visible { outline: 3px solid var(--fokus); outline-offset: 2px; }

/* sidhuvud, som i kontrollrummet */
header { padding-block: 1rem .6rem; border-bottom: 1px solid var(--ram); margin-bottom: 1.5rem; }
header h1 { margin: 0; font-size: 1.35rem; }
header .under { margin: .15rem 0 .7rem; color: var(--dov); font-size: .9rem; }
nav { display: flex; flex-wrap: wrap; gap: .4rem; }

/* intro */
.intro { display: block; margin-bottom: 1.2rem; }
.intro .ingress { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: .2rem 2rem; align-items: start; }
.intro .ingress h2 { grid-column: 1 / -1; }
.intro .ingress .omlank { grid-column: 1; justify-self: start; }
.intro .fakta { grid-column: 2; grid-row: 2 / 4; }
@media (max-width: 900px) { .intro .ingress { grid-template-columns: 1fr; } .intro .fakta { grid-column: 1; grid-row: auto; } }
.intro h2 { font-size: 1.6rem; margin: 0 0 .5rem; }
.intro p { margin: 0 0 .6rem; max-width: 62ch; }
.legend { background: var(--yta); border: 1px solid var(--ram); border-radius: 10px; padding: .9rem 1rem; display: grid; gap: .55rem; font-size: .9rem; }
.legend h3 { margin: 0; font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); font-weight: 600; }
.lrad { display: grid; grid-template-columns: 2.2rem minmax(0,1fr); gap: .6rem; align-items: start; }
.lrad .prov { height: 1.4rem; border-radius: 6px; display: grid; place-items: center; font-size: .8rem; font-weight: 700; }
.prov.ds { background: var(--ds-ton); border: 2px solid var(--ds); color: var(--ds); }
.prov.kedja { background: var(--yta); border: 1.5px solid var(--kedja); color: var(--kedja); }
.prov.princip { background: var(--yta); border: 1.5px dashed var(--ds); color: var(--ds); }
.prov.statusprov { border: 1px solid var(--ram); background: var(--yta); }
.prov.statusbar { border: none; background: none; }   /* statuspunkten har ingen inramning i bilden, så ingen i teckenförklaringen heller */
.statusprick { width: .55rem; height: .55rem; border-radius: 50%; background: var(--upp); display: block; }
.nod .kedjeikon { color: var(--kedja); }
.prov.dist { border: none; gap: 2px; grid-auto-flow: column; }

/* ordningsremsan */
.ordning { margin: 0 0 1rem; display: flex; flex-wrap: wrap; align-items: center; gap: .35rem; font-size: .85rem; }
.ordning .etikett { color: var(--dov); margin-right: .3rem; }
.ordning button { border: 1px solid var(--ram); background: var(--yta); border-radius: 999px; padding: .15rem .6rem; cursor: pointer; }
.ordning button:hover { border-color: var(--fg); }
.ordning button .snr { font-variant-numeric: tabular-nums; color: var(--dov); margin-right: .25rem; }
.ordning .pil { color: var(--dov); }

/* ------- kedjebilden (bred skärm) ------- */
.bildram { overflow-x: auto; }
.bild { position: relative; display: grid; min-width: 860px;
  grid-template-columns: 7.5rem repeat(6, minmax(0, 1fr));
  grid-template-rows: auto minmax(6.5rem, auto) 1.6rem minmax(6.5rem, auto) minmax(4.8rem, auto) auto;
  column-gap: .7rem; background: var(--yta); border: 1px solid var(--ram); border-radius: 12px; padding: .8rem .9rem 1rem; }
.zon { grid-row: 1; font-size: .75rem; letter-spacing: .07em; text-transform: uppercase; font-weight: 650; padding: .2rem 0 .5rem; color: var(--dov); border-bottom: 2px solid var(--ram); margin-bottom: .4rem; }
.zon.ds { color: var(--ds); border-color: var(--ds); }
.zon small { display: block; font-weight: 400; letter-spacing: 0; text-transform: none; font-size: .78rem; }
.dsfalt { grid-column: 3 / 6; grid-row: 2 / 6; background: var(--ds-ton); border-radius: 10px; margin: 0 -.35rem; }
.bana { grid-column: 1; font-size: .8rem; line-height: 1.3; padding-right: .4rem; align-self: center; }
.bana b { display: block; font-size: .85rem; }
.bana span { color: var(--dov); }
.bana i { display: block; font-style: normal; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--dov); }
.stadram { grid-column: 1 / 2; grid-row: 4 / 6; border-left: 3px solid var(--ram); margin-left: -.5rem; }
.banlinje.inre { border-top-style: dotted; }
.banlinje { grid-column: 1 / -1; border-top: 1px solid var(--ram); align-self: start; }
.grans { grid-column: 1 / -1; grid-row: 3; align-self: center; border-top: 2px dashed var(--gran); position: relative; z-index: 1; }
.grans span { position: absolute; left: 7.9rem; top: -.75rem; background: var(--yta); padding: 0 .4rem; font-size: .75rem; color: var(--gran); white-space: nowrap; }

.nod { position: relative; z-index: 2; align-self: center; text-align: left; cursor: pointer; border-radius: 9px; padding: .45rem .5rem .5rem; min-height: 5.2rem;
  display: flex; flex-direction: column; gap: .2rem; background: var(--yta); border: 1.5px solid var(--kedja); transition: transform .12s ease, box-shadow .12s ease; }
.nod:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgb(0 0 0 / .08); }
.nod.ds { background: var(--yta); border: 2.5px solid var(--ds); }
.nod.princip { border-style: dashed; border-color: var(--ds); }
.nod .topp { display: flex; align-items: center; gap: .35rem; }
.nod .nr { width: 1.35rem; height: 1.35rem; border-radius: 50%; display: grid; place-items: center; font-size: .75rem; font-weight: 700; background: var(--kedja-ton); color: var(--kedja); font-variant-numeric: tabular-nums; flex: none; }
.nod.ds .nr, .nod.princip .nr { background: var(--ds-ton); color: var(--ds); }
.nod .ikon { font-size: .8rem; color: var(--ds); }
.nod .status { margin-left: auto; width: 1.05rem; height: 1.05rem; border-radius: 50%; background: var(--upp); flex: none;
  display: inline-flex; align-items: center; justify-content: center; color: #fff; font-size: .75rem; line-height: 1; font-weight: 700; }
.nod .status::after { content: "✓"; }
.nod .status[data-s="delvis"]::after { content: "!"; }
.nod .status[data-s="ned"]::after { content: "✕"; }
.nod .status[data-s="okänd"]::after, .nod .status:not([data-s])::after { content: "?"; }
.nod .titel { font-size: .8rem; font-weight: 600; line-height: 1.25; hyphens: manual; overflow-wrap: break-word; }
.nod .taggar { display: flex; flex-wrap: wrap; gap: 3px; margin-top: auto; }
.tag { font-size: .75rem; font-weight: 700; border-radius: 4px; padding: 0 .3rem; border: 1px solid; line-height: 1.4; white-space: nowrap; }
.tag.a { color: var(--a); border-color: var(--a); }
.tag.b { color: var(--b); border-color: var(--b); }
.tag.x { color: var(--a); border-color: var(--a); font-weight: 600; }
.tag.sim { color: #47514c; border: 1px dashed #9aa6a0; background: #eef0ee; font-weight: 600; }
.nod[aria-expanded="true"] { box-shadow: 0 0 0 3px var(--fg); }
.nod.kov { min-height: 4rem; border: 2px solid var(--ds); background: var(--ds-ton); }
.nod.kov .titel { color: var(--ds); }
.borjahar { position: absolute; top: -1.35rem; left: 0; font-size: .75rem; color: var(--kedja); font-weight: 650; white-space: nowrap; }

svg.pilar { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; overflow: visible; }
svg.pilar path { fill: none; stroke: var(--dov); stroke-width: 1.4; }
svg.pilar path.dsp { stroke: var(--ds); stroke-width: 2; }
svg.pilar path.kovpil { stroke: var(--ds); stroke-dasharray: 4 3; }
svg.pilar text { fill: var(--dov); font-size: 10px; font-family: var(--font); }
svg.pilar marker path { fill: var(--dov); stroke: none; }
svg.pilar marker#pilds path { fill: var(--ds); }

/* ------- panelen ------- */
.panel { margin-top: 1rem; background: var(--yta); border: 1px solid var(--ram); border-radius: 12px; padding: 1.2rem 1.3rem 1rem; scroll-margin-top: 3.2rem; }
.panel[hidden] { display: none; }
.phuvud { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem .8rem; }
.phuvud .stegnr { font-size: .8rem; color: var(--dov); font-variant-numeric: tabular-nums; }
.kat { font-size: .78rem; font-weight: 650; padding: .15rem .55rem; border-radius: 999px; }
.kat.ds { background: var(--ds); color: var(--yta); }
.kat.kedja { background: var(--kedja-ton); color: var(--kedja); border: 1px solid var(--kedja); }
.kat.princip { background: var(--yta); color: var(--ds); border: 1.5px dashed var(--ds); }
.org { font-size: .78rem; color: var(--dov); border: 1px solid var(--ram); border-radius: 999px; padding: .1rem .5rem; }
.panel h2 { margin: .45rem 0 .9rem; font-size: 1.35rem; }
.stang { margin-left: auto; border: 1px solid var(--ram); background: transparent; border-radius: 6px; padding: .1rem .55rem; cursor: pointer; }
.pgrid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 1.4rem;  align-items: start; }
.hogerkol { display: grid; gap: .8rem; align-content: start; }
.pgrid > * { min-width: 0; }
.panel h3 { font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); margin: 0 0 .25rem; font-weight: 650; }
.panel p { margin: 0 0 .9rem; max-width: 65ch; }
.dsruta { border-radius: 10px; padding: .8rem .9rem; }
.dsruta.ds { background: var(--ds-ton); border: 1px solid var(--ds-ram); }
.dsruta.kedja { background: var(--kedja-ton); border: 1px solid var(--ram); }
.dsruta.princip { background: var(--yta); border: 1.5px dashed var(--ds); }
.dsruta h3 { color: inherit; }
.dsruta p { margin: 0; }
.dsruta .styrning { margin-top: .55rem; font-size: .85rem; padding: .45rem .6rem; border-left: 3px solid var(--ram); background: rgba(127,127,127,.08); }
.dsruta .byggblock { margin-top: .55rem; font-size: .82rem; color: var(--dov); }

.prova { margin-top: .4rem; margin-bottom: 1.6rem; border-top: 1px solid var(--ram); padding-top: 1rem; }
.panel .knappar { display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: .8rem; margin-top: .4rem; }
.knappkort { border: 1px solid var(--ram); border-radius: 10px; padding: .75rem .85rem; display: flex; flex-direction: column; gap: .45rem; min-width: 0; }
.knappkort button.kor { align-self: flex-start; border: 1.5px solid var(--fg); background: var(--fg); color: var(--bg); border-radius: 7px; padding: .3rem .75rem; cursor: pointer; font-weight: 600; font-size: .9rem; }
.knappkort button.kor.fara { background: transparent; color: var(--a); border-color: var(--a); }
.knappkort button.kor.ja { background: var(--b); border-color: var(--b); color: var(--yta); }
.knappkort dl { margin: 0; display: grid; gap: .3rem; font-size: .88rem; }
.knappkort dt { font-weight: 650; font-size: .75rem; color: var(--dov); text-transform: uppercase; letter-spacing: .06em; }
.knappkort dd { margin: 0; }
.knappkort .var { font-size: .78rem; color: var(--dov); }
.logg { background: var(--kod); border-radius: 8px; padding: .55rem .7rem; font-family: var(--mono); font-size: .76rem; line-height: 1.45; white-space: pre-wrap; overflow-x: auto; margin: 0; }
.logg .rub { font-family: var(--font); font-weight: 650; display: block; margin-bottom: .2rem; font-size: .78rem; }
.ingaknappar { color: var(--dov); font-size: .92rem; }

.akta { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; border-top: 1px solid var(--ram); padding-top: 1rem; }
.akta > div { min-width: 0; }
.akta p { font-size: .92rem; }
details.teknik { border-top: 1px solid var(--ram); padding-top: .7rem; margin-top: .3rem; }
details.teknik summary { cursor: pointer; font-weight: 600; font-size: .92rem; }
.tgrid { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 1rem; margin-top: .7rem; font-size: .88rem; }
.tgrid > * { min-width: 0; }
table.siffror { border-collapse: collapse; width: 100%; font-size: .85rem; font-variant-numeric: tabular-nums; }
table.siffror td { border-bottom: 1px solid var(--ram); padding: .25rem .3rem; vertical-align: top; overflow-wrap: anywhere; }
table.siffror td:first-child { color: var(--dov); width: 55%; }
code { font-family: var(--mono); font-size: .85em; background: var(--kod); padding: 0 .25rem; border-radius: 4px; }
.pnav { display: flex; justify-content: space-between; gap: .8rem; margin-top: 1rem; border-top: 1px solid var(--ram); padding-top: .8rem; }
.pnav button { border: 1px solid var(--ram); background: transparent; border-radius: 7px; padding: .35rem .8rem; cursor: pointer; }
.pnav button:disabled { opacity: .35; cursor: default; }
.anteckning { font-size: .82rem; color: var(--dov); border-left: 3px solid var(--ds-ram); padding-left: .6rem; margin-top: .6rem; }

/* ------- smal skärm: lodrät lista ------- */
@media (max-width: 900px) {
  .intro { grid-template-columns: 1fr; gap: 1rem; }
  .pgrid, .akta, .tgrid { grid-template-columns: 1fr; }
}
@media (max-width: 1100px) {
  .bild { display: flex; flex-direction: column; min-width: 0; gap: .55rem; padding: .8rem; }
  .bildram { overflow: visible; }
  .zon, .dsfalt, .bana, .banlinje, .grans, svg.pilar, .borjahar { display: none; }
  .zonrubrik { display: block !important; }
  .nod { min-height: 0; flex-direction: row; flex-wrap: wrap; align-items: center; gap: .45rem; padding: .55rem .65rem; }
  .nod .topp { order: 0; }
  .nod .titel { font-size: .92rem; flex: 1 1 10rem; }
  .nod .taggar { margin-top: 0; }
  .nod .orgmini { display: inline !important; font-size: .75rem; color: var(--dov); width: 100%; padding-left: 1.8rem; }
  .nod:not(:last-child)::after { content: ""; position: absolute; left: 1.2rem; bottom: -.6rem; height: .55rem; border-left: 2px solid var(--ram); }
  .nod.kov { margin-left: 1.5rem; }
  .panel { margin-top: .2rem; padding: 1rem; }
}
.zonrubrik { display: none; font-size: .75rem; letter-spacing: .07em; text-transform: uppercase; font-weight: 650; color: var(--dov); margin-top: .4rem; }
.zonrubrik.ds { color: var(--ds); }
.orgmini { display: none; }
@media (prefers-reduced-motion: reduce) { .nod { transition: none; } .nod:hover { transform: none; } }

/* logga */
.krvanster { display: flex; align-items: center; gap: 1rem; min-width: 0; }
img.logga { flex: none; height: 4.2rem; width: auto; display: block; }
.krvanster h1 { margin: 0; }

/* språkväljare */
button.kor.bekrafta { outline: 2px solid var(--a); outline-offset: 2px; }
.utdrag h5 { margin: .8rem 0 .2rem; font-size: .9rem; }
.utdrag pre { background: #f3f6f4; border: 1px solid var(--ram); border-radius: 6px; padding: .5rem .7rem; margin: 0 0 .3rem; overflow-x: auto; font-size: .82rem; white-space: pre-wrap; overflow-wrap: anywhere; }
.distnyckel { margin: .7rem 0 0; padding: .55rem .8rem; background: var(--kod); border-radius: 6px; font-size: .88rem; }
.tillbakarad { margin: 0 0 .6rem; }
.last-hint { color: var(--vanta); font-size: .85rem; margin: 0; }
/* Texten tar sin plats även när den är dold: sidan hoppar inte när den dyker upp (besökartestet 2026-10-22). Den står till höger om knappen. */
.last-hint[hidden] { display: block; visibility: hidden; }
.knapprad { display: flex; align-items: center; flex-wrap: wrap; gap: .4rem .9rem; min-height: 48px; }
.knapprad .last-hint { flex: 1 1 12rem; }
.kovval .kovtext { min-width: 0; display: grid; gap: .25rem; }
.bekrafta-info { display: block; grid-column: 1 / -1; font-size: .85rem; color: var(--dov); margin: .3rem 0; max-width: 40rem; }
.lanknot { position: sticky; top: 0; z-index: 30; margin: 0; padding: .5rem 1.5rem; background: #fff4d6; border-bottom: 2px solid #c98a00; color: #4a3800; font-size: .92rem; }
.brytbar td { overflow-wrap: anywhere; }
.krtopp { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: .6rem; }
.krhoger { display: flex; flex-direction: column; align-items: flex-end; gap: .3rem; flex: none; }
.aterstall { margin: 0; font-size: .78rem; color: var(--dov); text-align: right; }
.aterstall.snart { color: #6b4b00; background: #fff4d6; border: 1px solid #c98a00; border-radius: 4px; padding: .05rem .5rem; font-weight: 650; font-size: .95rem; }
.aterstall.nu { color: #fff; background: #b3261e; border: 2px solid #8a1c16; border-radius: 6px; padding: .1rem .65rem; font-weight: 750; font-size: 1.2rem; font-variant-numeric: tabular-nums; max-width: 100%; }
.aterstall small { font-weight: 500; opacity: .85; }
@keyframes aterpuls { 0%, 100% { box-shadow: 0 0 0 0 rgba(179,38,30,.55); } 50% { box-shadow: 0 0 0 6px rgba(179,38,30,0); } }
@media (prefers-reduced-motion: no-preference) { .aterstall.sista { animation: aterpuls 1.2s ease-in-out infinite; } }
.aterstallremsa { margin: 0 0 .6rem; padding: .45rem .8rem; border-radius: 8px; font-size: .9rem; font-weight: 650; background: #fbeeec; color: #8a1c16; border: 2px solid #8a1c16; }
.aterstallremsa[hidden], .aterstall[hidden] { display: none; }
.aterstallrad { display: flex; justify-content: flex-end; align-items: center; gap: .4rem; }
.aterstallinfo { width: 1.5rem; height: 1.5rem; padding: 0; border-radius: 50%; border: 1.5px solid var(--dov); background: transparent; color: var(--dov); font: 700 .85rem/1 system-ui, sans-serif; cursor: pointer; }
.aterstallinfo:hover, .aterstallinfo:focus-visible { background: var(--dov); color: var(--yta); }
.aterstallinfo[hidden] { display: none; }
.aterstallremsa .lank { border: 0; background: none; padding: 0; margin-left: .4rem; font: inherit; font-weight: 600; text-decoration: underline; color: inherit; cursor: pointer; }
dialog.jobb .jkropp ul { margin: 0; padding-left: 1.2rem; font-size: .85rem; display: grid; gap: .35rem; }
@media (max-width: 700px) { dialog.jobb { margin: auto 0 0; width: 100vw; max-width: 100vw; border-radius: 12px 12px 0 0; } }
.pausremsa { margin: 0 0 .6rem; padding: .4rem .8rem; border-radius: 8px; font-size: .9rem; background: #fff4d6; color: #6b4b00; border: 1px solid #c98a00; }
.pausremsa[hidden] { display: none; }
.skyddtid { font-variant-numeric: tabular-nums; font-weight: 650; color: var(--dov); margin-left: .35rem; }
.srdold { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; margin: 0; }
@media (max-width: 700px) { .aterstall .lang { display: none; } }
.sprak { display: inline-flex; border: 1px solid var(--ram); border-radius: 999px; overflow: hidden; flex: none; }
.sprak button { border: 0; background: transparent; padding: .25rem .7rem; font-size: .8rem; font-weight: 650; cursor: pointer; color: var(--dov); }
.sprak button[aria-pressed="true"] { background: var(--fg); color: var(--bg); }
.sprak button:focus-visible { outline: 3px solid var(--fokus); outline-offset: -3px; }

/* loggförhandsvisning */
.loggruta { border: 1px solid var(--ram); border-radius: 8px; overflow: hidden; }
.loggruta .lhuvud { display: flex; align-items: center; gap: .5rem; padding: .35rem .6rem; font-size: .78rem; background: var(--yta); border-bottom: 1px solid var(--ram); }
.loggruta .lhuvud b { font-weight: 650; }
.loggruta .tidnot { margin-left: auto; color: var(--dov); font-size: .75rem; }
.lstatus { font-size: .75rem; font-weight: 700; border-radius: 4px; padding: 0 .35rem; border: 1px solid; }
.lstatus.kor { color: var(--ds); border-color: var(--ds); background: var(--ds-ton); }   /* en statusetikett, inte en knapp: bara button.kor är knappar */
.lstatus.klar { color: var(--b); border-color: var(--b); }
.lstatus.fel { color: var(--a); border-color: var(--a); }
.lstatus.ko { color: #6b4b00; border-color: #c98a00; background: #fff4d6; }
.lstatus.vantar { color: #6b4b00; border-color: #c98a00; background: #fff4d6; }
.lstatus.avvisad, .lstatus.ingetavtal { color: #8a1c16; border-color: #8a1c16; background: #fbeeec; }
.loggruta .logg { border-radius: 0; }
.loggruta .fler { color: var(--dov); font-family: var(--font); font-size: .75rem; display: block; margin-bottom: .15rem; }
.helalogg { display: inline-block; margin: .4rem .6rem .5rem; font-size: .82rem; color: var(--fokus); font-weight: 600; }
.anm { font-size: .75rem; color: var(--dov); margin: 0 .6rem .5rem; }

/* jobbfönster (simulerar fliken Jobb) */
dialog.jobb { border: 1px solid var(--ram); border-radius: 12px; padding: 0; width: min(46rem, calc(100vw - 32px)); background: var(--yta); color: var(--fg); }
dialog.jobb::backdrop { background: rgb(0 0 0 / .35); }
dialog.jobb .jhuvud { display: flex; align-items: center; gap: .6rem; padding: .8rem 1rem; border-bottom: 1px solid var(--ram); }
dialog.jobb h2 { margin: 0; font-size: 1.05rem; }
dialog.jobb .jhuvud button { margin-left: auto; border: 1px solid var(--ram); background: transparent; border-radius: 6px; padding: .15rem .6rem; cursor: pointer; }
dialog.jobb .jkropp { padding: .8rem 1rem 1rem; display: grid; gap: .6rem; }
dialog.jobb .jkropp p { margin: 0; font-size: .85rem; color: var(--dov); }
dialog.jobb .logg { max-height: 50vh; overflow: auto; }

.analys { border: 1px solid var(--ram); border-radius: 10px; padding: .8rem 1rem; margin-top: 1rem; background: var(--yta); }
.analys h3, .analys h4 { margin: .6rem 0 .3rem; }
.analyskontroll { display: flex; flex-wrap: wrap; gap: .6rem 1.4rem; align-items: end; margin: .6rem 0; }
.analyskontroll fieldset { border: 1px solid var(--ram); border-radius: 8px; padding: .3rem .7rem; }
.analyskontroll fieldset.lagevaljare { border: 0; padding: 0; margin: 0; }
.lagevaljare legend { font-size: .8rem; color: var(--dov); padding: 0 0 .2rem; }
.segment { display: inline-flex; border: 2px solid var(--ds); border-radius: 10px; overflow: hidden; background: #fff; }
.analyskontroll label.seg { position: relative; display: block; margin: 0; cursor: pointer; font-size: .9rem; }
.seg input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
.seg span { display: flex; flex-direction: column; min-height: 44px; justify-content: center; padding: .25rem .9rem; color: var(--ds); background: #fff; }
.seg span small { font-size: .78rem; color: var(--dov); }
.seg + .seg span { border-left: 2px solid var(--ds); }
.seg input:checked + span { background: var(--ds); color: #fff; }
.seg input:checked + span small { color: #fff; }
.seg input:focus-visible + span { outline: 3px solid var(--ds); outline-offset: 2px; }
.seg:hover input:not(:checked) + span { background: var(--ds-ton); }
.analyskontroll label { display: block; font-size: .9rem; }
.analyskontroll input[type=number] { width: 4.2rem; font: inherit; }
.analystabell { width: 100%; border-collapse: collapse; font-size: .88rem; }
.analystabell th, .analystabell td { text-align: left; padding: .25rem .5rem; border-bottom: 1px solid var(--ram); }
.analystabell tr.inspektera td { background: #fbeeec; }
.tabellrum { overflow-x: auto; }
/* Smal skärm: breda tabeller rullar i sidled i sin egen ruta i stället för att göra hela sidan bredare. */
@media (max-width: 700px) { section.flik table { display: block; max-width: 100%; overflow-x: auto; } }
.kartrum { margin: .6rem 0; overflow-x: auto; }
.osmkarta { width: 100%; max-width: 40rem; height: 22rem; border: 1px solid #c9d2cd; }
.kartval { margin: .3rem 0; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.leaflet-control-attribution { background: rgba(255,255,255,.92) !important; }
.leaflet-control-attribution a { color: #00456b !important; }
/* Den schematiska kartans text ska vara läsbar på telefon: på smal skärm ritas kartan i en egen, smal viewBox (se analysKarta),
   så att textens storlek följer bildens skala. Bildförhållandet kommer ur width/height-attributen. */
.svadaruta .res-HAVT, .svadaruta .felrad, #svadautfall .res-HAVT { color: #8a1c16; }
svg.karta { display: block; width: 100%; max-width: 40rem; height: auto; }
.analys .larm { border: 2px solid var(--a); background: #fbeeec; border-radius: 10px; padding: .6rem .9rem; }
/* roller och KoV-ruta */
.rollchip { align-self: flex-start; font-size: .75rem; color: var(--dov); border: 1px solid var(--ram); border-radius: 999px; padding: .05rem .5rem; }
.rollchip b { color: var(--fg); font-weight: 650; }
.rollchip.kov { border-color: var(--ds); color: var(--ds); background: var(--ds-ton); }
.rollchip.kov b { color: var(--ds); }
.sidlank { font-size: .84rem; font-weight: 600; color: var(--fokus); }
.tillkov { margin: 0; font-size: .86rem; font-weight: 600; color: var(--ds); }
.tillkov .lank, .hopplank .lank { background: none; border: 0; padding: 0; font: inherit; color: inherit; text-decoration: underline; cursor: pointer; text-align: left; }
.hopplank { display: none; margin: 0 0 .5rem; font-size: .86rem; font-weight: 600; color: var(--ds); }
.panel .knappar.medkov { grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
.kovruta, .svadaruta { border: 2px solid var(--ds); background: var(--ds-ton); border-radius: 10px; padding: .75rem .85rem; display: flex; flex-direction: column; gap: .5rem; min-width: 0; grid-column: span 2; }
.kovruta.fokus { box-shadow: 0 0 0 3px var(--ds-ram); }
.kovruta h4, .svadaruta h4 { margin: 0; font-size: 1rem; color: var(--ds); }
.kovruta .kovintro, .svadaruta .kovintro { margin: 0; font-size: .86rem; }
.kovruta .kovko, .svadaruta .kovko { margin: 0; font-size: .84rem; display: flex; align-items: center; gap: .4rem; font-weight: 600; }
.kovruta .vantar { width: .55rem; height: .55rem; border-radius: 50%; background: #c98a00; flex: none; }
.kovruta .vantar.ingen { background: #8b948f; }
.kovval { display: grid; grid-template-columns: auto minmax(0,1fr); gap: .3rem .8rem; align-items: start; background: var(--yta); border: 1px solid var(--ds-ram); border-radius: 8px; padding: .55rem .65rem; }
.kovval button.kor { align-self: start; border: 1.5px solid var(--fg); background: var(--fg); color: var(--bg); border-radius: 7px; padding: .3rem .75rem; cursor: pointer; font-weight: 600; font-size: .9rem; white-space: nowrap; }
.kovval button.kor.ja { background: var(--b); border-color: var(--b); color: var(--yta); }
.kovval button.kor.fara { background: transparent; color: var(--a); border-color: var(--a); }
.kovval dl { margin: 0; display: grid; gap: .25rem; font-size: .85rem; }
.kovval dt { font-weight: 650; font-size: .75rem; color: var(--dov); text-transform: uppercase; letter-spacing: .06em; }
.kovval dd { margin: 0; }
.kovval .loggplats { grid-column: 1 / -1; }
@media (max-width: 1100px) { .kovruta, .svadaruta { grid-column: auto; } }
@media (max-width: 520px) { .kovval { grid-template-columns: 1fr; } }
/* Smalare KoV-kolumn (vyer under cirka 1250 px): knappen och förklaringen ställs under varandra i stället för i två kolumner, och långa ord får brytas
   (externa webbläsartestet 2026-10-23: förklaringen hamnade i en 82 px smal kolumn och stack ut ur rutan vid 1040 px). */
@media (max-width: 1250px) { .kovval { grid-template-columns: 1fr; } }
.kovval dl, .kovval dd, .kovval dt { overflow-wrap: anywhere; min-width: 0; }

/* begrepp, tipsruta och ordlista */
.term { text-decoration: underline dotted var(--ds); text-decoration-thickness: 1.5px; text-underline-offset: 3px; cursor: help; border-radius: 2px; }
.term:hover, .term:focus-visible { background: var(--ds-ton); }
#tips { position: absolute; z-index: 50; background: var(--fg); color: var(--bg); border-radius: 8px; padding: .55rem .7rem; font-size: .85rem; line-height: 1.45; box-shadow: 0 6px 18px rgb(0 0 0 / .18); display: grid; gap: .25rem; }
#tips[hidden] { display: none; }
#tips a { color: #b8d4ff; font-weight: 600; font-size: .8rem; }
nav button { font: inherit; padding: .3rem .8rem; border: 1px solid var(--ram); border-radius: 999px; font-size: .85rem; color: var(--fg); background: var(--yta); cursor: pointer; }
nav button.aktiv { background: var(--fg); color: var(--bg); border-color: var(--fg); }
[data-dold] { display: none !important; }
.ordsida { max-width: 52rem; }
.ordsida .tillbaka { border: 1px solid var(--ram); background: var(--yta); border-radius: 7px; padding: .3rem .8rem; cursor: pointer; }
.ordsida h2 { font-size: 1.6rem; margin: 1rem 0 .3rem; }
.ordintro { color: var(--dov); max-width: 62ch; }
.ordlista { margin: 1rem 0 0; display: grid; gap: 0; }
.ordlista > div { display: grid; grid-template-columns: 14rem minmax(0,1fr); gap: 1rem; padding: .6rem .4rem; border-bottom: 1px solid var(--ram); scroll-margin-top: 6rem; }
.ordlista dt { font-weight: 650; }
.ordlista dd { margin: 0; }
.ordlista > div.markerad { background: var(--ds-ton); border-radius: 6px; }
@media (max-width: 640px) { .ordlista > div { grid-template-columns: 1fr; gap: .2rem; } }
/* tunn stegrad som syns när bilden har scrollats bort */
.stegrad { flex-wrap: nowrap; position: fixed; top: 0; left: 0; right: 0; z-index: 40; background: var(--yta); border-bottom: 1px solid var(--ram); box-shadow: 0 2px 8px rgb(0 0 0 / .06); padding: calc(env(safe-area-inset-top, 0px) + .3rem) 16px .3rem; display: flex; align-items: center; gap: .3rem; overflow-x: auto; scrollbar-width: none; }
.stegrad[hidden] { display: none; }
.stegrad .srub { font-size: .75rem; color: var(--dov); margin-right: .3rem; white-space: nowrap; }
.stegrad button { flex: none; border: 1px solid var(--ram); background: var(--yta); border-radius: 999px; padding: .1rem .55rem; font-size: .78rem; cursor: pointer; white-space: nowrap; display: inline-flex; align-items: center; gap: .3rem; }
.stegrad button .si { font-size: .75rem; }
.stegrad button.s-ds .si, .stegrad button.s-princip .si { color: var(--ds); }
.stegrad button.s-kedja .si { color: var(--kedja); }
.stegrad button[aria-current="step"] { background: var(--fg); color: var(--bg); border-color: var(--fg); }
.stegrad button[aria-current="step"] .si { color: inherit; }
.stegrad .upp { margin-left: auto; color: var(--fokus); border-color: transparent; }
/* se hur det ser ut */
.sehur { margin-top: 1rem; border-top: 1px solid var(--ram); padding-top: 1rem; }
/* Riktiga flikar (besökartestet 2026-10-22): flikraden med en baslinje, den valda fliken öppen mot innehållet, och bläddring under. */
.sflikar { display: flex; flex-wrap: wrap; gap: .25rem; margin: .5rem 0 0; border-bottom: 2px solid var(--ds); }
.sflikar button { border: 1px solid var(--ram); border-bottom: none; background: var(--kod); color: var(--dov); border-radius: 8px 8px 0 0; padding: .45rem 1rem; font-size: .9rem; cursor: pointer; margin-bottom: -2px; }
.sflikar button:hover { background: var(--ds-ton); color: var(--fg); }
.sflikar button[aria-selected="true"] { background: #fff; color: var(--ds); font-weight: 700; border: 2px solid var(--ds); border-bottom: 2px solid #fff; padding-top: .5rem; }
.sflikar button:focus-visible { outline: 3px solid var(--fokus); outline-offset: 2px; }
.sehur .stips { margin: .2rem 0 0; font-size: .88rem; color: var(--dov); }
.sehur .sinnehall { border: 2px solid var(--ds); border-top: none; border-radius: 0 0 8px 8px; padding: .8rem 1rem; }
.sehur .sstep { display: flex; align-items: center; gap: .8rem; margin: .6rem 0 .2rem; }
.sehur .sstep .sraknare { font-size: .88rem; color: var(--dov); min-width: 5rem; text-align: center; font-variant-numeric: tabular-nums; }
.sinnehall p { font-size: .9rem; margin: 0 0 .5rem; }
.katpar { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: .8rem; }
.katpar > div { min-width: 0; }
.katpar h4 { margin: 0 0 .35rem; font-size: .9rem; }
.katpar .logg { max-height: 34rem; }
.brunnjamfor { margin-top: 1rem; }
.brunnjamfor .sida { border: 2px solid var(--ram); border-radius: 10px; padding: .5rem .75rem; }
.brunnjamfor .sida.b { border-color: var(--b); }
.brunnjamfor .sida.a { border-color: var(--a); }
.brunnjamfor table { width: 100%; border-collapse: collapse; font-size: .86rem; }
.brunnjamfor th { text-align: left; font-weight: 600; padding: .2rem .5rem .2rem 0; vertical-align: top; width: 40%; }
.brunnjamfor td { padding: .2rem 0; overflow-wrap: anywhere; }
.sinnehall .logg { max-height: 22rem; overflow: auto; }
/* ODRL-ruta */
.odrlruta { margin-top: 1rem; border-top: 1px solid var(--ram); padding-top: 1rem; }
.odrlintro { font-size: .9rem; }
.verkstall { margin: 1rem 0 .6rem; padding: .7rem .9rem; border: 1px solid var(--ram); border-left: 4px solid var(--ds); border-radius: 8px; background: var(--yta); }
.verkstall h4 { margin: 0 0 .4rem; font-size: 1rem; }
.verkstall dl { margin: 0; }
.verkstall dt { font-weight: 600; margin-top: .55rem; }
.verkstall dd { margin: .15rem 0 0; }
.verkstall h5 { margin: .9rem 0 .3rem; font-size: .95rem; }
.laslista { margin: 0; padding-left: 1.3rem; }
.laslista li { margin: .4rem 0; }
.laslista .vem { color: var(--dov); font-size: .85rem; white-space: nowrap; }

.odrlgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: .9rem; }
.odrlkol { border: 1px solid var(--ram); border-radius: 10px; padding: .7rem .85rem; min-width: 0; }
.odrlkol.a { border-left: 4px solid var(--a); } .odrlkol.b { border-left: 4px solid var(--b); }
.odrlkol h4 { margin: 0 0 .5rem; font-size: .92rem; }
.odrlkol ul { list-style: none; margin: 0 0 .5rem; padding: 0; display: grid; gap: .35rem; font-size: .86rem; }
.odrlkol li { display: grid; grid-template-columns: minmax(0, 13rem) minmax(0, 1fr); gap: .6rem; }
.odrlkol li code { white-space: normal; overflow-wrap: anywhere; }
.odrlkol .bnot { font-size: .8rem; color: var(--dov); margin: 0 0 .5rem; }
.odrlkol details summary { cursor: pointer; font-size: .82rem; color: var(--fokus); font-weight: 600; }
@media (max-width: 640px) { .odrlkol li { grid-template-columns: 1fr; gap: .1rem; } }
/* dataproduktens versioner */
.versioner { margin-top: 1rem; border-top: 1px solid var(--ram); padding-top: 1rem; }
.vtab { overflow-x: auto; }
.versioner table { border-collapse: collapse; width: 100%; font-size: .86rem; min-width: 46rem; }
.versioner th, .versioner td { text-align: left; vertical-align: top; padding: .5rem .55rem; border-bottom: 1px solid var(--ram); }
.versioner thead th { font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--dov); font-weight: 650; }
.versioner tbody th { white-space: nowrap; font-weight: 650; }
.versioner tr.a th { color: var(--a); } .versioner tr.b th { color: var(--b); }
.versioner .vnot { font-size: .82rem; color: var(--dov); margin: .5rem 0 0; }
/* teckenförklaring inne i bilden */
.bildleg { grid-column: 2 / 8; grid-row: 6; align-self: center; position: relative; z-index: 2; background: var(--yta); border: 1px solid var(--ram); border-radius: 10px; padding: .55rem .7rem; display: grid; grid-template-columns: 1fr 1fr; gap: .3rem .9rem; font-size: .76rem; line-height: 1.35; margin: .4rem 0; }
.bildleg h3 { grid-column: 1 / -1; margin: 0 0 .1rem; font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); }
.bildleg .lrad { grid-template-columns: 1.9rem minmax(0,1fr); gap: .4rem; align-items: center; }
.bildleg .lfull { grid-column: 1 / -1; }
.bildleg .prov { height: 1.15rem; font-size: .75rem; }
@media (max-width: 1100px) { .bildleg { order: -1; display: grid !important; grid-template-columns: 1fr; margin: 0 0 .4rem; } }
/* kort ingress och om-sida */
.ingress p { margin: 0 0 .7rem; max-width: 62ch; }
.fakta { list-style: none; margin: 0 0 .8rem; padding: 0; display: grid; gap: .35rem; font-size: .9rem; }
.fakta li { display: grid; grid-template-columns: 1.4rem minmax(0,1fr); gap: .4rem; align-items: baseline; }
.fikon { font-weight: 700; text-align: center; }
.fikon.f-ds { color: var(--ds); } .fikon.f-akta { color: var(--upp); } .fikon.f-gps { color: var(--dov); }
.omlank { border: 1px solid var(--ds); color: var(--ds); background: var(--yta); border-radius: 999px; padding: .3rem .85rem; font-weight: 600; cursor: pointer; font-size: .88rem; }
.omlank:hover { background: var(--ds-ton); }
.omsida .tillbaka { border: 1px solid var(--ram); background: var(--yta); border-radius: 7px; padding: .3rem .8rem; cursor: pointer; }
.omsida > h2 { font-size: 1.6rem; margin: 1rem 0 .8rem; }
.omkol { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(0,1fr); gap: 1.6rem; align-items: start; }
.omkol h3 { font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); margin: 0 0 .3rem; }
.omkol p { max-width: 62ch; }
@media (max-width: 900px) { .omkol { grid-template-columns: 1fr; } }
/* EU-ruta */
.omprojekt { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 1rem; margin: 1.2rem 0; padding-top: 1rem; border-top: 1px solid var(--ds-ram); }
.omprojekt h3 { margin: 0 0 .3rem; font-size: .95rem; }
.omprojekt p { margin: 0; font-size: .92rem; }
.euruta { border: 1px solid var(--ds-ram); background: var(--ds-ton); border-radius: 10px; padding: .7rem .9rem; margin: 0; }
.euruta h3 { margin: 0 0 .3rem; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ds); }
.euruta p { margin: 0 0 .45rem; font-size: .92rem; }
.euruta p:last-child { margin: 0; }
/* om data */
.omdata { margin-top: 2rem; border-top: 1px solid var(--ram); padding-top: 1.2rem; }
.omdata h2 { font-size: 1.25rem; margin: 0 0 .8rem; }
.omgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1rem 1.4rem; }
.omgrid > div { min-width: 0; }
.omgrid h3 { font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); margin: 0 0 .25rem; }
.omgrid p { margin: 0; font-size: .92rem; }
/* förklaring före knappen */
.forklaring { background: #f3f6f4; border-radius: 8px; padding: .65rem .8rem; font-size: .9rem; margin: .4rem 0 .8rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: .4rem 1.4rem; }
.forklaring p { min-width: 0; }
.forklaring p { margin: 0; }
.forklaring p:last-child { margin: 0; }
/* se det hända */
.sehanda { border: 1px solid var(--ram); border-radius: 10px; padding: .7rem .85rem; }
.sehanda p { margin: 0 0 .45rem; }
.sehanda .raknare { display: flex; align-items: center; gap: .45rem; font-variant-numeric: tabular-nums; }
.sehanda .raknare b { font-size: 1.15rem; }
.puls { width: .6rem; height: .6rem; border-radius: 50%; background: var(--upp); animation: puls 2s ease-in-out infinite; }
@keyframes puls { 0%,100% { opacity: 1; } 50% { opacity: .25; } }
@media (prefers-reduced-motion: reduce) { .puls { animation: none; } }
/* teknikruta: vad som körs på riktigt */
.aktaintro { border-left: 4px solid var(--upp); padding-left: .7rem; }
.stapelrad { font-size: .88rem; color: var(--dov); }
.teknikruta { margin-top: 1rem; border: 1px solid var(--ram); border-radius: 10px; padding: .85rem 1rem .4rem; }
.teknikruta h3 { margin-bottom: .5rem; }
.tlista { list-style: none; margin: 0 0 .8rem; padding: 0; display: grid; gap: .45rem; }
.tlista li { display: grid; grid-template-columns: 10.5rem 15rem minmax(0,1fr); gap: .3rem .8rem; align-items: start; font-size: .9rem; border-bottom: 1px solid var(--ram); padding-bottom: .45rem; }
.tlista li:last-child { border-bottom: 0; }
.tnamn { font-weight: 650; font-family: var(--mono); font-size: .82rem; overflow-wrap: anywhere; display: grid; gap: .15rem; }
.tlankar, .tegen { font-family: var(--font); font-weight: 500; font-size: .76rem; }
.tlankar a { color: var(--fokus); margin-right: .5rem; }
.tegen { color: var(--dov); }
.tstatus { justify-self: start; align-self: start; line-height: 1.5; font-size: .75rem; font-weight: 700; border-radius: 999px; padding: .05rem .55rem; white-space: nowrap; }
.tstatus.s-akta { background: #e3f3e7; color: #165a27; border: 1px solid #9fd2ab; }
.tstatus.s-forenklad { background: #fff4d6; color: #6b4b00; border: 1px solid #e8c86a; }
.tstatus.s-simulerad { background: #eef0ee; color: #47514c; border: 1px dashed #9aa6a0; }
.teknikruta .akta { margin-top: 0; padding-top: .7rem; }
.teknikruta h4 { margin: 0 0 .2rem; font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--dov); }
@media (max-width: 900px) { .tlista li { grid-template-columns: 1fr; } }
/* ---- kontrollrummets övriga flikar (Följ, Audit, Suveränitet …) ---- */
:root { --ned: #99201a; --vanta: #644f00; --bak: #f3f6f4; --lank: #0848a6; }
main { padding: 1rem 1.5rem 3rem; max-width: 78rem; margin: 0 auto; }
header { padding: 1rem 1.5rem 0.6rem; border-bottom: 1px solid var(--ram); margin-bottom: 0; }
header h1 { margin: 0; font-size: 1.35rem; }
header .underrubrik { color: var(--dov); margin: .15rem 0 .5rem; font-size: .9rem; }
section.flik { display: none; }
section.flik.aktiv { display: block; }
.ruta { border: 1px solid var(--ram); border-radius: 8px; padding: 0.8rem 1rem; margin: 0.8rem 0; }
.meta { color: var(--dov); font-size: 0.85rem; margin: 0.1rem 0 0.4rem; }
/* Raden "Kör just nu: …" tar sin plats även när den är tom: annars växte sidhuvudet vid varje klick och sidan hoppade (besökartestet 2026-10-22). */
#jobbrad { min-height: 1.35rem; }
.text { margin: 0 0 0.6rem; }
.prick { display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 50%;
         margin-right: 0.35rem; vertical-align: -1px; background: var(--dov); }
.upp .prick, .prick.upp { background: var(--upp); }
.ned .prick, .prick.ned { background: var(--ned); }
.delvis .prick, .prick.delvis { background: var(--vanta); }
.chip { display: inline-block; border: 1px solid var(--ram); border-radius: 999px;
        padding: 0.05rem 0.6rem; font-size: 0.8rem; margin: 0 0.3rem 0.3rem 0; }
.knappar { margin: 0.5rem 0 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }
button.kor { font: inherit; padding: 0.35rem 0.8rem; border-radius: 6px;
             border: 1px solid currentColor; background: transparent;
             color: inherit; cursor: pointer; }
button.kor:hover { background: rgba(127,127,127,0.15); }
.knappkort button.kor:hover, .kovval button.kor:hover { background: #333; color: var(--bg); }
button.kor:disabled { opacity: 0.45; cursor: not-allowed; }
button.fara { color: var(--ned); }
button.godkann { color: var(--upp); }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
th, td { text-align: left; vertical-align: top; padding: 0.25rem 0.5rem;
         border-bottom: 1px solid var(--ram); }
th { color: var(--dov); font-weight: 600; }
.detaljer td:first-child { color: var(--dov); width: 42%; }
pre { font-family: var(--mono); font-size: 0.82rem; white-space: pre-wrap;
      word-break: break-word; background: var(--bak); padding: 0.6rem;
      border-radius: 6px; max-height: 26rem; overflow: auto; }
.larm { border-color: var(--ned); border-width: 2px; }
.larm h2 { color: var(--ned); }
.normal { border-color: var(--upp); }
.normal h2 { color: var(--upp); }
.nyckeltal { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem,1fr));
             gap: 0.6rem 1rem; }
.nyckeltal div span { display: block; font-size: 0.78rem; color: var(--dov); }
.nyckeltal div b { font-size: 1.15rem; font-weight: 600; }
.res-LEVERERAD, .res-COMPLETED, .res-FINALIZED, .res-GODKAND, .res-KLAR,
.res-SKÖRDAD, .res-PUBLICERAD, .res-AUKTORISERAD, .res-klar { color: var(--upp); }
.res-AVVISAD, .res-TERMINATED, .res-FEL, .res-AVSLAGEN, .res-AVVISAT,
.res-AVSLAGET, .res--AUKTORISATION-NEKAD, .res-fel { color: var(--ned); }
.res-GALLANDE { color: var(--upp); }
.res-HAVT, .res-UTGANGET, .res-OKAND, .res-UTESTANGD { color: var(--ned); }
.res-INSATT { color: var(--upp); }
.res-VANTANDE, .res-REQUESTED, .res-PÅ, .res-kör { color: var(--vanta); }
footer { color: var(--dov); font-size: 0.82rem; margin-top: 2rem;
         border-top: 1px solid var(--ram); padding-top: 0.8rem; }
.rad { display: flex; flex-wrap: wrap; gap: 1rem; align-items: baseline; }
label.reglage { display: block; margin: 0.25rem 0; }
/* Safari räknar inte ut höjden på en inline-SVG med bara viewBox och height:auto (diagrammet blev
   helt vitt). Därför riktiga width/height-attribut på elementet, en fast proportion och ett golv. */
svg.kurva { display: block; width: 100%; min-width: 30rem; height: auto; aspect-ratio: 640 / 270; min-height: 12rem; max-height: 22rem; }
.kurvarum { overflow-x: auto; }
.matare { background: var(--bak); border: 1px solid var(--ram); border-radius: 999px;
          height: 0.55rem; overflow: hidden; min-width: 6rem; margin: 0.3rem 0; }
.matare i { display: block; height: 100%; background: var(--upp); }
mark { background: rgba(224,180,0,0.35); color: inherit; padding: 0 0.15rem; border-radius: 3px; }
details.exempeldetalj { margin-top: 0.5rem; }
details.exempeldetalj > summary { cursor: pointer; color: var(--fokus); font-size: 0.88rem; font-weight: 600; }
.roll-banner { background: var(--bak); border: 1px solid var(--vanta);
       border-left-width: 4px; border-radius: 8px; padding: 0.6rem 0.9rem; margin: 0.6rem 0; }
.roll-banner b { color: var(--vanta); }
.framtid { border-left: 3px solid var(--dov); padding-left: 0.8rem; margin: 0.8rem 0; color: var(--dov); }
.framtid p { margin: 0 0 0.4rem; }
.framtid p:last-child { margin-bottom: 0; }
.mark-trad { color: var(--vanta); font-weight: 600; }
.mark-lucka { color: var(--dov); }
.mark-invariant { color: var(--upp); font-weight: 600; }
.hoppnr { font-size: 0.85rem; color: var(--dov); }
.nod .status[data-s="delvis"] { background: var(--vanta); }
.nod .status[data-s="ned"] { background: var(--ned); }
.nod .status[data-s="okänd"], .nod .status:not([data-s]) { background: var(--dov); }
.felrad { color: var(--ned); font-size: .85rem; margin: .3rem 0 0; }
.knappkort button.kor:disabled, .kovval button.kor:disabled { opacity: .45; cursor: not-allowed; }

/* Rullningslister som alltid syns (besökartestet 2026-10-22): macOS döljer dem annars tills man rullar, så man ser inte att en ruta rullar. */
::-webkit-scrollbar { width: 14px; height: 14px; background: #eceeed; }
::-webkit-scrollbar-thumb { background: #8a8f8c; border-radius: 8px; border: 3px solid #eceeed; }
::-webkit-scrollbar-thumb:hover { background: #5f6663; }
::-webkit-scrollbar-corner { background: #eceeed; }

/* Knappar som GÖR något (besökartestet 2026-10-22: de liknade statusrutor och pillerformer). Egen färg (dataspace-lila) som
   ingen flik eller etikett har, tydligt större, upphöjda, med en symbol och en stark markering vid hovring och tangentbord. */
:root { --akt: var(--ds); --akt-hover: #3a2d85; }
button.kor, .knappkort button.kor, .kovval button.kor {
  display: inline-flex; align-items: center; gap: .5rem; min-height: 44px; padding: .6rem 1.3rem;
  font: inherit; font-size: 1rem; font-weight: 650; line-height: 1.2; border-radius: 8px;
  border: 2px solid var(--akt); background: var(--akt); color: #fff; cursor: pointer; white-space: normal; text-align: left;
  box-shadow: 0 2px 0 rgba(0, 0, 0, .28), 0 4px 10px rgba(76, 60, 167, .25);
  transition: background .12s, box-shadow .12s;
}
/* Pilen (▶) har en fast plats. En avstängd knapp har samma plats tom, och snurran tar den under ett jobb: texten börjar alltid på samma ställe. */
button.kor::before, .knappkort button.kor::before, .kovval button.kor::before { content: "▶"; content: "▶" / ""; font-size: .75em; flex: none; width: 1.2rem; text-align: center; }
button.kor:hover, .knappkort button.kor:hover, .kovval button.kor:hover { background: var(--akt-hover); border-color: var(--akt-hover); color: #fff; }
button.kor:active, .knappkort button.kor:active, .kovval button.kor:active { box-shadow: none; }
button.kor:focus-visible, .knappkort button.kor:focus-visible, .kovval button.kor:focus-visible { outline: 3px solid var(--fokus); outline-offset: 3px; }
button.kor:disabled, .knappkort button.kor:disabled, .kovval button.kor:disabled {
  background: #e6e8e7; border-color: #c9cecb; color: #434b47; box-shadow: none; opacity: 1; cursor: not-allowed; transform: none; }
button.kor:disabled::before, .knappkort button.kor:disabled::before, .kovval button.kor:disabled::before { content: ""; }
button.kor:disabled, .knappkort button.kor:disabled, .kovval button.kor:disabled { border-style: dashed; }
/* Knappar som ser avstängda ut men går att klicka på (aria-disabled): samma utseende som avstängda, klicket visar en förklaring. */
button.kor[aria-disabled="true"], .knappkort button.kor[aria-disabled="true"], .kovval button.kor[aria-disabled="true"] {
  background: #e6e8e7; border-color: #c9cecb; border-style: dashed; color: #434b47; box-shadow: none; cursor: help; }
/* Dubbelt attributvillkor = högre specificitet: den gröna Godkänn-knappen (.ja) och hovringen får inte slå igenom på en knapp som ser avstängd ut. */
button.kor[aria-disabled="true"][aria-disabled="true"], button.kor[aria-disabled="true"][aria-disabled="true"]:hover,
.kovval button.kor[aria-disabled="true"][aria-disabled="true"], .kovval button.kor[aria-disabled="true"][aria-disabled="true"]:hover,
.knappkort button.kor[aria-disabled="true"][aria-disabled="true"], .knappkort button.kor[aria-disabled="true"][aria-disabled="true"]:hover {
  background: #e6e8e7; border-color: #c9cecb; border-style: dashed; color: #434b47; box-shadow: none; cursor: help; }
button.kor[aria-disabled="true"]::before, .kovval button.kor[aria-disabled="true"]::before { content: ""; }
button.kor.fara[aria-disabled="true"], .kovval button.kor.fara[aria-disabled="true"] { background: #e6e8e7; border-color: #c9cecb; color: #434b47; box-shadow: none; }
.knapptips { position: fixed; z-index: 60; max-width: 22rem; padding: .6rem .8rem; background: #fff; color: var(--fg); border: 2px solid var(--ds); border-radius: 8px; box-shadow: 0 6px 18px rgba(0, 0, 0, .2); font-size: .9rem; }
.knapptips a { display: block; margin-top: .35rem; font-weight: 600; color: var(--ds); }
/* Körs just nu: knappen behåller sina färger, pilen ersätts av en snurra. */
button.kor.pagar:disabled, .knappkort button.kor.pagar:disabled, .kovval button.kor.pagar:disabled { background: var(--akt); border-color: var(--akt); border-style: solid; color: #fff; cursor: progress; }
button.kor.pagar.fara:disabled, .knappkort button.kor.pagar.fara:disabled, .kovval button.kor.pagar.fara:disabled { background: #fff; color: var(--a); border-color: var(--a); }
button.kor.pagar.ja:disabled, .knappkort button.kor.pagar.ja:disabled, .kovval button.kor.pagar.ja:disabled { background: var(--b); border-color: var(--b); border-style: solid; color: #fff; }
button.kor.pagar::before, .knappkort button.kor.pagar::before, .kovval button.kor.pagar::before, button.kor.pagar:disabled::before {
  content: ""; box-sizing: border-box; width: 1rem; height: 1rem; margin: 0 .1rem; font-size: 1em; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: snurra .8s linear infinite; }
@media (prefers-reduced-motion: reduce) { button.kor.pagar::before, button.kor.pagar:disabled::before { animation: none; border-right-color: currentColor; border-style: dotted; } }
@keyframes snurra { to { transform: rotate(360deg); } }
.snurr { display: inline-block; box-sizing: border-box; width: 1rem; height: 1rem; vertical-align: -.15rem; margin-right: .35rem; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: snurra .8s linear infinite; }
.jobbpagar { min-height: 1.5rem; margin: 0 0 .4rem; color: var(--ds); font-weight: 600; }   /* fast höjd: raden får inte få sidan att hoppa när den fylls */
@media (prefers-reduced-motion: reduce) { .snurr { animation: none; border-right-color: currentColor; border-style: dotted; } }
button.kor.fara, .knappkort button.kor.fara, .kovval button.kor.fara { background: #fff; color: var(--a); border-color: var(--a); box-shadow: 0 2px 0 rgba(153, 32, 26, .35); }
button.kor.fara:hover, .knappkort button.kor.fara:hover, .kovval button.kor.fara:hover { background: #fbeeec; color: var(--a); border-color: var(--a); }
button.kor.fara:disabled, .knappkort button.kor.fara:disabled, .kovval button.kor.fara:disabled { background: #e6e8e7; border-color: #c9cecb; color: #434b47; box-shadow: none; }
button.kor.ja, button.kor.godkann, .knappkort button.kor.ja, .kovval button.kor.ja { background: var(--b); border-color: var(--b); color: #fff; box-shadow: 0 2px 0 rgba(0, 0, 0, .28), 0 4px 10px rgba(23, 91, 36, .25); }
button.kor.ja:hover, button.kor.godkann:hover, .knappkort button.kor.ja:hover, .kovval button.kor.ja:hover { background: #0f4a1a; border-color: #0f4a1a; color: #fff; }
button.kor.ja:disabled, button.kor.godkann:disabled, .knappkort button.kor.ja:disabled, .kovval button.kor.ja:disabled { background: #e6e8e7; border-color: #c9cecb; color: #434b47; box-shadow: none; }
/* Sekundära knappar (uppdatera, gå till en annan flik): konturknapp i samma färg, utan åtgärdssymbol. */
button.kor.sek { background: #fff; color: var(--akt); border-color: var(--akt); box-shadow: none; font-weight: 600; min-height: 40px; padding: .45rem 1rem; }
button.kor.sek::before { content: none; }
button.kor.sek:disabled, button.kor.sek:disabled:hover { background: #e6e8e7; border-color: #c9cecb; border-style: dashed; color: #434b47; }
button.kor.sek:hover { background: var(--ds-ton); color: var(--akt-hover); border-color: var(--akt-hover); }
/* Knapparna i stegens kort håller sig på en rad ("Förhandla Distribution B" bröts i två vid 1280 px); på smala skärmar får de bryta. */
.knappkort button.kor { white-space: nowrap; padding-left: 1rem; padding-right: 1rem; max-width: 100%; }
@media (max-width: 700px) { .knappkort button.kor { white-space: normal; } }
/* Statusmärken och roller är inte klickbara: platta, fyrkantiga och grå, aldrig rundade med fyllning. */
.rollchip, .chip { border-radius: 4px; border-color: transparent; background: var(--kod); }
/* Nästa rimliga åtgärd: märket "Nästa" på knappen (sätts av markeraNasta). */
button.kor.nasta::after { content: attr(data-nasta); font-size: .7rem; font-weight: 700; background: #fff; color: var(--akt); border-radius: 4px; padding: 0 .4rem; margin-left: .3rem; }
/* Ordningsraden: numrerade fyrkantiga steg, och en riktig knapp för nästa steg. */
.ordning button[data-hopp] { border-radius: 6px; background: var(--kod); border: 1px solid var(--ram); padding: .25rem .6rem; }
.ordning button[data-hopp] .snr { display: inline-block; min-width: 1.4em; text-align: center; background: var(--fg); color: #fff; border-radius: 4px; margin-right: .4rem; }
/* Etikett och nästa-knapp på en rad, själva stegen på en egen rad under (besökartestet 2026-10-22: allt på en rad bröts i två). */
.ordning { display: block; }
.ordningtopp { display: flex; align-items: center; justify-content: space-between; gap: .8rem; flex-wrap: wrap; margin-bottom: .45rem; }
.ordningsteg { display: flex; flex-wrap: nowrap; align-items: flex-end; gap: .2rem; }
.ordningsteg button { white-space: nowrap; padding: .25rem .5rem; font-size: .84rem; }
.ordningsteg .pil { flex: none; }
@media (max-width: 1250px) { .ordningsteg { flex-wrap: wrap; row-gap: .35rem; } }
@media (max-width: 700px) { .ordning button.nastaknapp, .ordningsteg button { min-height: 32px; } }
.ordning button.nastaknapp { border: 1px solid var(--akt); background: var(--akt); color: #fff; font-weight: 650; font-size: .84rem; padding: .25rem .8rem; min-height: 0; line-height: normal; border-radius: 6px; margin-left: .7rem; white-space: nowrap; box-shadow: none; }
.ordning button.nastaknapp:hover { background: var(--akt-hover); border-color: var(--akt-hover); }
.ordning button.nastaknapp:focus-visible { outline: 3px solid var(--fokus); outline-offset: 3px; }
.ordning button.nastaknapp[hidden] { display: none; }
.ordning .nastaslut { font-weight: 650; font-size: .84rem; color: var(--akt); }
.ordning .nastaslut[hidden] { display: none; }
.panel .stegrubrik { margin: 0; }

header .krtopp { margin-bottom: .6rem; }

/* ---- smal skärm, läsbarhet och träffytor (webbläsartestet 2026-10-12) ---- */
.panel, .nod, #bild { scroll-margin-top: 52px; }
code, pre, td code { font-variant-numeric: slashed-zero; font-feature-settings: "zero" 1; }
code, kbd, samp { font-size: max(12px, .88em); }
.livetal { margin: .35rem 0 0; font-size: .8rem; color: var(--dov); }
@media (max-width: 700px) {
  section.flik table[data-rull]::before { content: var(--rullhint); display: block; position: sticky; left: 0; padding: .1rem .3rem; font-size: .75rem; font-weight: 600; color: var(--dov); }
  .hopplank { display: block; }
  /* Breda tabeller rullar i sidled i sin egen ruta; skuggorna visar att det finns mer åt sidan. */
  section.flik table {
    background:
      linear-gradient(to right, var(--yta) 30%, rgba(255,255,255,0)) left center / 28px 100% no-repeat local,
      linear-gradient(to left, var(--yta) 30%, rgba(255,255,255,0)) right center / 28px 100% no-repeat local,
      radial-gradient(farthest-side at 0 50%, rgba(0,0,0,.28), rgba(0,0,0,0)) left center / 12px 100% no-repeat scroll,
      radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.28), rgba(0,0,0,0)) right center / 12px 100% no-repeat scroll;
  }
  /* Träffytor minst 32 px (WCAG 2.5.8 kräver 24 px). */
  button, summary, .kor { min-height: 32px; }
  input[type="radio"], input[type="checkbox"] { width: 22px; height: 22px; }
  .reglage, label:has(> input[type="radio"]) { min-height: 32px; display: flex; align-items: center; gap: .4rem; }
  .term { padding: .15em 0; }
  footer a { display: inline-block; padding: .3rem 0; }
  .stegrad { overflow-x: auto; }
  .stegrad .srub { display: none; }
  /* Mindre inramning inåt: tabellen får mer av bredden. */
  .panel, .ruta, .sinnehall, .knappkort, .kovruta, .svadaruta, .odrlruta, .teknikruta { padding-left: .55rem; padding-right: .55rem; }
  .panel { border-left-width: 0; border-right-width: 0; border-radius: 0; }
}
"""

SKRIPT = r"""
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
/* Avfrågningarna ritar om tabeller och knappar varje sekund. Byts ett element ut mellan musknapp ned och upp tappas
   klicket, och sidan hoppar. För element som är märkta data-stabil hoppas en tilldelning av exakt samma html som sist
   därför över (tom html utförs alltid). Märkningen är medveten: ett element vars barn ändras på annat sätt (egenskaper som
   disabled, Leaflet, SVG som göms) får aldrig sin återställning överhoppad. */
(() => {
  const d = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  Object.defineProperty(Element.prototype, 'innerHTML', {
    get: d.get,
    set(v) {
      const s = String(v);
      if (s && this.hasAttribute && this.hasAttribute('data-stabil') && this._sistaHtml === s && this.isConnected) return;
      this._sistaHtml = s;
      d.set.call(this, v);
    }
  });
  /* En textContent-tilldelning ändrar innehållet bakom cachens rygg: glöm den. */
  const t = Object.getOwnPropertyDescriptor(Node.prototype, 'textContent');
  Object.defineProperty(Node.prototype, 'textContent', {
    get: t.get,
    set(v) { this._sistaHtml = null; t.set.call(this, v); }
  });
})();
const esc = t => String(t === null || t === undefined ? '' : t)
  .replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
/* Servern skickar med gränssnittets texter och ordlistan på det valda språket. */
const TX = __TX__;
const ORD = __ORD__;
const SPRAK = '__SPRAK__';
const VARIANT = '__VARIANT__';
const fmt = (s, v) => String(s).replace(/\{(\w+)\}/g,
  (m, k) => (v && v[k] !== undefined) ? v[k] : m);
const lugnt = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const sov = ms => new Promise(klar => setTimeout(klar, ms));
const talFormat = n => Number(n).toLocaleString(SPRAK === 'en' ? 'en-GB' : 'sv-SE');

async function api(sokvag, metod, kropp) {
  const svar = await fetch(sokvag, {
    method: metod || 'GET',
    headers: kropp ? {'content-type': 'application/json', 'x-svada-lang': SPRAK} : {'x-svada-lang': SPRAK},
    body: kropp ? JSON.stringify(kropp) : undefined});
  const data = await svar.json().catch(() => ({}));
  return {ok: svar.ok, status: svar.status, data};
}

/* Statistik: rapporterar en vitlistad händelse (steg öppnat, flik, knapp ...). Servern räknar upp ett tal per dag och
   händelse; kroppen är bara {h: namn}: ingen identifierare och ingen fritext. (Webbläsaren skickar samma kakor som för varje annat
   anrop, bland annat lösenordsgrindens; servern läser och sparar dem inte, och utan dem skulle grinden stoppa anropet.) Ett
   misslyckande ska aldrig märkas, och sidan skickar högst 150 per laddning (samma händelse inte oftare än var 1,5:e sekund) så att
   ett fel i en loop inte översvämmar. Steg, flikar och analyser räknas bara efter att besökaren rört något (harRort), så att en
   sidladdning eller ett språkbyte inte räknas som att steg 3 öppnats. */
let harRort = false;
['pointerdown', 'keydown', 'touchstart'].forEach(h => window.addEventListener(h, () => { harRort = true; }, {capture: true, passive: true}));
let senastFoljd = null;            // {jid, plats, slut}: det jobb vars ruta följdes senast (för språkbytet)
let analysVisarA = false;          // F1: visar steg 6 just nu positioner ur distribution A?
let jamforVisarA = false;          // F1: visar rutan "samma brunn i B och A" just nu A:s position (även när analysläget är B)?
let lasTill = 0;                   // F2: knapparna hålls låsta till dess (ms), så ett äldre statussvar inte låser upp dem mellan två klick
let handelserSkickade = 0, senasteHandelse = '', senasteHandelseTid = 0;
function handelse(namn) {
  try {
    const nu = Date.now();
    if (handelserSkickade >= 150 || (namn === senasteHandelse && nu - senasteHandelseTid < 1500)) return;
    handelserSkickade++; senasteHandelse = namn; senasteHandelseTid = nu;
    fetch('/api/handelse', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({h: namn}), keepalive: true}).catch(() => {});
  } catch (e) {}
}
window.addEventListener('error', () => handelse('js_fel'));
window.addEventListener('unhandledrejection', () => handelse('js_fel'));

/* Kort notis överst när något inte gick som länken sa (ett steg eller jobb som inte finns): försvinner av sig själv. */
function lanknotis(text) {
  const el = $('#lanknot');
  if (!el) return;
  el.textContent = text; el.hidden = false;
  clearTimeout(el._t); el._t = setTimeout(() => { el.hidden = true; }, 9000);
}
let notisJobb = null;

/* ---------------------------------------------------------------- flikar */
/* Scroll-minne per flik: en flik är display:none när den inte är aktiv,
   så webbläsarens EGEN scrollposition är delad mellan alla flikar och
   nollställs synligt varje gång man byter. Vi sparar och återställer den
   själva per sektion i stället. */
const scrollMinnen = {};
let foregaendeFlik = 'kedjan';
const FLIKAR = ['kedjan', 'folj', 'audit', 'suveranitet',
                'felinjektion', 'jobb', 'om', 'ordlista'];

/* visa() tar ett flik-id eller en djuplänk: steg-N öppnar kedjevyn med steg
   N, jobb-ID öppnar fliken Jobb med jobbet valt, ordlista-ID öppnar
   ordlistan vid ett begrepp. */
function visa(namn, historik) {
  /* historik: 'push' (ett flikbyte, så att webbläsarens Bakåt går tillbaka till föregående flik, M3), 'replace' (samma flik
     eller när adressen redan ändrats av Bakåt/Framåt). Utan värde: push vid byte av flik, annars replace. */
  let steg = null, ordfokus = null, m;
  if ((m = /^steg-(\d+)$/.exec(namn))) {
    steg = +m[1]; namn = 'kedjan';
    if (!(steg >= 1 && steg <= 6)) {        // F13: en länk till ett steg som inte finns får inte skrivas om utan ett ord
      lanknotis(L(`Steg ${steg} finns inte, det finns sex steg. Visar steg ${valt || 1}.`, `Step ${steg} does not exist; there are six steps. Showing step ${valt || 1}.`));
      steg = valt || 1;
    }
  }
  else if ((m = /^jobb-(\d+)$/.exec(namn))) { valtJobb = +m[1]; namn = 'jobb'; }
  else if ((m = /^ordlista-(.+)$/.exec(namn))) { ordfokus = m[1]; namn = 'ordlista'; }
  else if (namn === 'omdata') { namn = 'om'; ordfokus = 'omdata'; }
  if (FLIKAR.indexOf(namn) < 0) namn = 'kedjan';
  const aktivForut = $('section.flik.aktiv');
  if (aktivForut && aktivForut.id !== namn) {
    if (harRort) handelse('flik_' + namn);
    scrollMinnen[aktivForut.id] = window.scrollY;
    foregaendeFlik = aktivForut.id;
  }
  $$('section.flik').forEach(s => s.classList.toggle('aktiv', s.id === namn));
  $$('nav#flikar button').forEach(b => b.classList.toggle('aktiv', b.dataset.flik === namn));
  let nyoppnad = false;
  if (namn === 'kedjan' && steg !== null) { oppna(steg, false); nyoppnad = true; }
  /* replaceState och INTE location.hash: en hash-tilldelning får webbläsaren
     att scrolla fram sektionen, vilket knuffar upp sidhuvudet ur bild. */
  /* Adressen bär det som valdes (steg, jobb, begrepp), så att ett nytt anrop med samma adress ger samma vy: en
     fragmentnavigering utlöser både hashchange och popstate, och begreppet får inte tappas på vägen (#ordlista-dsp). */
  const hash = namn === 'kedjan' ? (valt ? 'steg-' + valt : 'kedjan')
             : namn === 'jobb' && valtJobb ? 'jobb-' + valtJobb
             : namn === 'ordlista' && ordfokus ? 'ordlista-' + ordfokus : namn;
  const byte = aktivForut && aktivForut.id !== namn;
  if ((historik || (byte ? 'push' : 'replace')) === 'push' && location.hash !== '#' + hash) history.pushState(null, '', '#' + hash);
  else history.replaceState(null, '', '#' + hash);
  window.scrollTo(0, scrollMinnen[namn] || 0);
  /* oppna() laddar redan panelen; ladda den bara en gång (annars två anrop mot providern). */
  if (namn === 'kedjan') { ritaPilar(); if (valt && !nyoppnad) laddaPanel(valt); }
  if (namn === 'folj') laddaFolj();
  if (namn === 'audit') laddaAudit();
  if (namn === 'suveranitet') laddaKov();
  if (namn === 'felinjektion') laddaFel();
  if (namn === 'jobb') laddaJobb();
  if (namn === 'ordlista') markeraOrd(ordfokus);
  if (ordfokus === 'omdata') $('#omdata').scrollIntoView({block: 'start'});
  uppdateraStegrad();
}

function tillbakaFranJobb() {
  visa(foregaendeFlik === 'jobb' ? 'kedjan' : foregaendeFlik);
}
/* Alla flikar utom kedjan har en väg tillbaka (besökartestet 2026-10-22: Felinjektion saknade den). */
function tillbakaFranFlik(id) { visa(foregaendeFlik && foregaendeFlik !== id ? foregaendeFlik : 'kedjan'); }
function laggTillbakaKnappar() {
  $$('section.flik').forEach(sec => {
    if (sec.id === 'kedjan' || sec.querySelector('[onclick*="tillbakaFran"]')) return;
    sec.insertAdjacentHTML('afterbegin', `<p class="tillbakarad"><button type="button" class="kor sek" onclick="tillbakaFranFlik('${sec.id}')">${L('← Tillbaka', '← Back')}</button></p>`);
  });
}
setTimeout(laggTillbakaKnappar, 0);        // efter att hela skriptet körts (L och visa är då definierade)

/* Ordlistan: markera och rulla fram begreppet. */
function markeraOrd(id) {
  $$('.ordlista > div').forEach(d => d.classList.remove('markerad'));
  const mal = id ? document.getElementById('ordlista-' + id) : null;
  if (mal) { mal.classList.add('markerad'); mal.scrollIntoView({block: 'center'}); }
}

/* ------------------------------------------------ exempelobjekt (Nivå 1) */
/* Svenska eller engelska ur samma anrop: L('svenska', 'english'). */
const L = (sv, en) => SPRAK === 'en' ? en : sv;
/* Testläge (?test=1 satte kakan svada-test): sidfoten säger att besöket inte räknas i statistiken. */
try { if (/(?:^|; )svada-test=1(?:;|$)/.test(document.cookie)) { const tl = document.getElementById('testlage'); if (tl) { tl.hidden = false; tl.textContent = L(' · Testläge: besöket räknas inte i statistiken (avsluta med ?test=0)', ' · Test mode: this visit is not counted in the statistics (end with ?test=0)'); } } } catch (e) {}
/* Svenska statuskoder är identifierare (CSS-klass, nyckel); bara visningen översätts. Se i18n.py (KODER). */
const KODER_EN = __KODER__;
const KODER_SV = {VANTANDE: 'VÄNTANDE', GODKAND: 'GODKÄND', HAVT: 'HÄVT', UTGANGET: 'UTGÅNGET', GALLANDE: 'GÄLLER', OKAND: 'OKÄND', UTESTANGD: 'UTESTÄNGD', PABORJAD: 'PÅBÖRJAD'};
const resKod = c => SPRAK === 'en' ? (KODER_EN[c] || c) : (KODER_SV[c] || c);

function renderaExempel(d) {
  return `<p class="meta">${esc(d.rubrik)}</p>`
    + `<pre>${esc(d.innehall)}</pre>`
    + (d.not ? `<p class="meta">ⓘ ${esc(d.not)}</p>` : '');
}

async function oppnaExempel(el, nr) {
  if (!el.open || el.dataset.laddat) return;
  const box = $('.exempelinnehall', el);
  const {ok, data} = await api('/api/steg/' + nr + '/exempel?lang=' + SPRAK);
  if (!ok) { box.innerHTML = `<p class="meta">${esc(TX.kunde)}</p>`; return; }
  el.dataset.laddat = '1';
  box.innerHTML = renderaExempel(data) + (SPRAK === 'en'
    ? `<p class="meta">Text in the data itself (names, titles, quality declaration) is shown in the original Swedish; interface text and messages are translated. Contract terms are in English in both languages.</p>` : '');
}

/* --------------------------------------------- följ ett värde */
/* Avtalets adress i en grå ruta blir en länk (besökartestet 2026-10-22). Tar redan HTML-escapad text. */
function lankaAvtal(escHtml) {
  return escHtml.replace(/(https?:\/\/[^\s"<>&]+\/avtal\/[0-9A-Za-z-]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}
async function laddaFolj() {
  const {ok, data} = await api('/api/folj?lang=' + SPRAK);
  if (!ok) { $('#foljhopp').innerHTML = `<p>${esc(TX.kunde)}</p>`; return; }
  const trad = data.tradId;
  $('#tradid').textContent = trad || L('inget avtal ännu – kör steg 3 och 4 först',
                                       'no agreement yet – run steps 3 and 4 first');
  $('#foljinvarianter').innerHTML =
    '<ul>' + data.invarianter.map(i => `<li>${esc(i)}</li>`).join('') + '</ul>';
  $('#foljhopp').innerHTML = data.hopp.map(h => {
    let pre = esc(h.innehall);
    /* markera tråden (avtals-id:t) i nyttoklartexten */
    pre = lankaAvtal(pre);
    /* tråden markeras bara utanför länkarna (ett <mark> i en href skulle bryta länken) */
    if (trad) pre = pre.split(/(<a [^>]*>.*?<\/a>)/).map((d, i) => i % 2 ? d : d.split(esc(trad)).join('<mark>' + esc(trad) + '</mark>')).join('');
    const mk = h.markering
      ? `<p class="meta mark-${esc(h.markering.typ)}">▸ ${esc(h.markering.text)}</p>`
      : '';
    return `<div class="ruta">
      <h3><span class="hoppnr">${L('Steg', 'Step')} ${esc(h.steg)} ·</span> ${esc(h.titel)}</h3>
      <p class="meta">${esc(h.rubrik)}</p>${mk}
      <pre>${pre}</pre>
      ${h.not ? `<p class="meta">ⓘ ${esc(h.not)}</p>` : ''}</div>`;
  }).join('');
}

/* ---------------------------------------------------------------- kedjan */
async function laddaStatus() {
  const {ok, data} = await api('/api/status?lang=' + SPRAK);
  if (!ok) return;
  $('#sammanfattning').textContent = fmt(TX.sammanfattning,
    {uppe: data.sammanfattning.uppe, totalt: data.sammanfattning.totalt,
     tid: data.tid.slice(11, 16) + ' UTC'});
  data.komponenter.forEach(k => {
    $$(`[data-komponent="${k.id}"]`).forEach(el => {
      el.className = 'chip ' + k.status;
      el.title = (k.adress ? k.adress + ' – ' : '') + (k.detalj === 'svarar' ? TX.svarar : k.detalj);
      el.innerHTML = `<span class="prick"></span>${esc(k.namn)}`;
    });
  });
  data.steg.forEach(s => {
    $$(`[data-stegstatus="${s.nr}"]`).forEach(el => {
      /* Status som text och form, inte bara färg: namn för skärmläsare och
         tooltip, och en symbol i pricken (CSS, [data-s]). */
      const namn = TX.statusNamn[s.status] || TX.statusNamn['okänd'];
      el.dataset.s = s.status; el.title = namn;
      el.setAttribute('role', 'img'); el.setAttribute('aria-label', namn);
    });
  });
  /* F1: gäller avtalet om A inte längre medan steg 6 visar positioner ur A läses vyn om, så att den visar nekandet (och kartan
     försvinner) inom en statusrunda i stället för att ligga kvar tills besökaren byter distribution eller antal. */
  if (data.avtalA && data.avtalA.gallande === false && (analysVisarA || jamforVisarA)) laddaAnalys(true);
  /* F2: under de första sekunderna efter ett klick gäller låsningen även om ett statussvar som skickades före klicket kommer
     tillbaka utan ett aktivt jobb (servern hann inte registrera det än). */
  const aktivt = data.jobbAktivt || (Date.now() < lasTill ? {last: true} : null);
  $$('button.kor[data-atgard]:not([data-svada])').forEach(b => { b.disabled = !!aktivt || skyddPausNu; });
  jobbAktivtNu = !!aktivt || skyddPausNu;
  if (!aktivt) sattPagar(null); else if (aktivt.atgard) sattPagar(aktivt.atgard);
  nastaId = data.nasta || null; markeraNasta();
  if (!aktivt) $$('.upptagetfel').forEach(el => el.remove());
  kovKnappar();
  const faktisktJobb = data.jobbAktivt;          // inte platshållaren från låsfönstret (den saknar etikett och id)
  $('#jobbrad').innerHTML = faktisktJobb
    ? (faktisktJobb.status === 'kö' ? fmt(TX.jobbRadKo, {etikett: esc(faktisktJobb.etikett), id: faktisktJobb.id, plats: faktisktJobb.kopos || '…'})
                                    : fmt(TX.jobbRad, {etikett: esc(faktisktJobb.etikett), id: faktisktJobb.id}))
    : '';
  if (aktivt) laddaJobb();
}

/* EN funktion avgör KoV-knapparnas tillstånd (förr ställde laddaStatus och
   laddaKovRuta om dem var för sig, så de blinkade). Godkänn/Avslå kräver en
   väntande förhandling, Häv kräver ett gällande avtal; inget går under ett jobb. */
let jobbAktivtNu = false;
/* Snurran: knappen som startade jobbet visar en snurra på den plats där pilen (▶) stod, tills knapparna låses upp igen. */
const KOV_KNAPP = {'kov-godkann': 'godkann', 'kov-avsla': 'avsla', 'kov-hav': 'hav'};
function knapparFor(atgard) {
  return KOV_KNAPP[atgard] ? $$(`button.kor[data-kovbeslut="${KOV_KNAPP[atgard]}"]`) : $$(`button.kor[data-atgard="${atgard}"]:not([data-svada])`);
}
function sattPagar(atgard) {
  $$('button.kor.pagar').forEach(b => { b.classList.remove('pagar'); b.removeAttribute('aria-busy'); });
  if (atgard) knapparFor(atgard).forEach(b => { b.classList.add('pagar'); b.setAttribute('aria-busy', 'true'); });
}
let aktuellaVantande = null;      // id:n som väntar på KoV-beslut enligt senaste läsningen av providerns kö (null = okänt)
/* F4: en avstängd knapp ska säga varför. Under ett jobb visar knappen som startades en snurra (ingen text); rättvisepausen och orsaken vid KoV-knapparna står som en rad till höger om knappen. */
function visaLasHint() {
  const paus = (typeof skyddInfo !== 'undefined' && skyddInfo.pausS) ? skyddRest(skyddInfo.pausS) : 0;
  /* Texten ändras bara när läget byts (inte varje sekund): rutorna är statusregioner, och en nedräkning skulle läsas upp varje sekund. */
  /* Under ett jobb visas ingen text: knappen som startades visar en snurra (sattPagar). Kvar är rättvisepausen och, vid KoV-knapparna,
     orsaken till att de är avstängda (el.dataset.orsak, satt av kovKnappar). */
  const text = paus ? L('Vänta några sekunder innan nästa körning.', 'Wait a few seconds before the next run.') : '';
  $$('.last-hint').forEach(el => { const t = text || el.dataset.orsak || ''; el.hidden = !t; if (t && el.textContent !== t) el.textContent = t; });
}
function kovKnappar() {
  const ruta = $('#kovruta');
  if (!ruta) return;
  $$('button.kor[data-kovbeslut]', ruta).forEach(b => {
    const behov = b.dataset.kovbeslut === 'hav' ? ruta.dataset.avtal : ruta.dataset.id;
    /* Under ett pågående jobb är knappen avstängd som förut. Saknas det knappen behöver är den bara "avstängd" till utseendet
       (aria-disabled): ett klick på den visar en kort ruta som förklarar varför, och orsaken står också som mouseover och
       som rad till höger om knappen. */
    const brist = !jobbAktivtNu && !behov;
    b.disabled = jobbAktivtNu;
    const orsakKort = brist ? (b.dataset.kovbeslut === 'hav' ? L('Inget gällande avtal om A att häva.', 'There is no current agreement for A to revoke.')
                                       : L('Ingen förfrågan väntar på beslut.', 'No request is waiting for a decision.')) : '';
    if (brist) { b.setAttribute('aria-disabled', 'true'); b.title = orsakKort; b.dataset.tips = b.dataset.kovbeslut === 'hav'
        ? L('Det finns inget gällande avtal om A att häva. Förhandla A och godkänn först.', 'There is no current agreement for A to revoke. Negotiate A and approve first.')
        : L('Ingen förfrågan väntar på beslut ännu. Förhandla Distribution A först, så dyker en förfrågan upp här.', 'No request is waiting for a decision yet. Negotiate Distribution A first, and a request will appear here.'); }
    else { b.removeAttribute('aria-disabled'); b.removeAttribute('title'); delete b.dataset.tips; }
    const hint = b.closest('.kovval') && $('.last-hint', b.closest('.kovval'));
    if (hint) hint.dataset.orsak = orsakKort;
  });
  visaLasHint();
  markeraNasta();
}

async function laddaDetaljer() {
  const {ok, data} = await api('/api/steg?lang=' + SPRAK);
  if (!ok) return;
  data.steg.forEach(s => {
    const el = $(`[data-detaljer="${s.nr}"]`);
    if (!el) return;
    el.innerHTML = s.detaljer.map(d =>
      `<tr><td>${esc(d.etikett)}</td><td>${esc(d.varde)}</td></tr>`).join('');
    /* "Titta efter"-siffrorna ska synas intill knappen, inte bara i den hopfällda rutan. */
    const live = L('Just nu: ', 'Right now: ') + s.detaljer.slice(0, 3).map(d => d.etikett + ' ' + d.varde).join(' · ');
    $$('#steg-' + s.nr + ' .knappkort .livetal').forEach(pp => { pp.textContent = live; });
  });
}

/* Köra en åtgärd. Utan inline-läge (flikarna Felinjektion, Avvikelse och
   Suveränitet) flyttas besökaren till fliken Jobb. Med {inline: element}
   (kedjevyn) visas jobbloggen i en ruta på stället, och besökaren byter
   inte flik. */
async function kor(atgard, argument, val) {
  handelse('atgard_' + atgard);
  const plats = val && val.inline;
  /* F2: knapparna låses direkt (som i KoV-rutan), så ett dubbelklick inte hinner skicka två anrop. */
  $$('button.kor[data-atgard]:not([data-svada])').forEach(b => { b.disabled = true; });
  jobbAktivtNu = true; lasTill = Date.now() + 3000; sattPagar(atgard); kovKnappar(); visaLasHint();
  const {ok, status, data} = await api('/api/atgard/' + atgard, 'POST', argument || {});
  if (!ok) {
    lasTill = 0; sattPagar(null);
    const fel = data.fel || ('HTTP ' + status);
    if (status === 429) hamtaSkydd();
    laddaStatus();                    // låser upp igen om inget jobb kör (annars står knapparna kvar tills jobbet är klart)
    /* 409 (ett jobb kör redan) försvinner av sig själv när jobbet är klart, även i en annan flik (L3). */
    if (plats) plats.innerHTML = `<p class="felrad${status === 409 ? ' upptagetfel' : ''}">${esc(fmt(TX.jobbFelStart, {fel}))}</p>`;
    else lanknotis(fmt(TX.jobbFelStart, {fel}));      // F2: en rad i sidan, aldrig en dialog som låser fliken
    return;
  }
  laddaStatus();
  rensaLoggplatser(plats);            // gamla jobbrutor i stegen ska inte stå kvar och se aktuella ut
  valtJobb = data.id;   // före visa(): adressen (#jobb-N) byggs ur valtJobb. Sätts även för jobb i ett stegkort, så att fliken Jobb öppnas på det senaste jobbet.
  if (plats) { foljJobb(data.id, plats); return; }
  visa('jobb');
  laddaJobb();
  tillJobblogg();
}
function rensaLoggplatser(utom) {
  $$('.loggplats').forEach(x => { if (x !== utom && x.innerHTML) { x.innerHTML = ''; x._sistaHtml = null; x._html = null; delete x.dataset.jid; } });
}
/* "…och se utfallet": fliken Jobb är lång på smal skärm, så scrolla till loggen. */
function tillJobblogg() {
  setTimeout(() => { const l = document.getElementById('jobblogg'); if (l) l.scrollIntoView({behavior: lugnt() ? 'auto' : 'smooth', block: 'start'}); }, 450);
}

/* Jobbstatus och avtalsstatus hålls isär: ett jobb kan vara klart medan
   avtalet väntar. Statusmärket beskriver jobbet. */
function loggStatus(j) {
  if (j.status === 'kör') return 'kor';
  if (j.status === 'kö') return 'ko';           // i kö bakom en annan besökares jobb (sessioner)
  if (j.utfall === 'nekad') return 'nekad';         // spärren fungerade (L1)
  if (j.status === 'fel') return 'fel';
  if (j.utfall === 'avvisad') return 'avvisad';
  if (j.utfall === 'inget-avtal') return 'ingetavtal';
  const kov = j.resultat && j.resultat.kov;
  /* "Väntar på KoV" gäller bara så länge förhandlingen fortfarande ligger väntande i providerns kö (bedömt vid senaste läsning). */
  if (kov && kov.kovBeslut === 'VANTANDE' && (aktuellaVantande === null || aktuellaVantande.has(kov.id))) return 'vantar';
  return 'klar';
}
const LSTATUS = {kor: 'jobbKor', ko: 'jobbKo', fel: 'fel', vantar: 'vantar', klar: 'klar', avvisad: 'avvisad', ingetavtal: 'ingetavtal', nekad: 'nekad'};

function skrivLoggruta(plats, j) {
  const rader = j.rader.map(r => `${(r.tid || '').slice(11, 19)}  ${r.text}`);
  const sista = rader.slice(-2), dolda = rader.length - sista.length;
  const st = loggStatus(j);
  const html = `<div class="loggruta">
      <div class="lhuvud"><b>${esc(fmt(TX.loggRub, {id: j.id}))}</b> · ${esc(j.etikett)}
        <span class="lstatus ${st}">${esc(TX[LSTATUS[st]] + (st === 'ko' && j.kopos ? ' (' + L('plats', 'place') + ' ' + j.kopos + ')' : ''))}</span>
        <span class="tidnot">(${esc(TX.tidUtc)})</span></div>
      <pre class="logg">${dolda > 0 ? `<span class="fler">${esc(
        dolda === 1 ? TX.tidigare1 : fmt(TX.tidigareN, {n: dolda}))}</span>` : ''}${esc(sista.join('\n'))}</pre>
      <a class="helalogg" href="#jobb-${j.id}">${esc(TX.helaLogg)}</a>
    </div>`;
  /* Rutan är en aria-live-region: skriv bara när något ändrats, annars läser
     en skärmläsare upp hela rutan var 1,5:e sekund. */
  if (plats._html !== html) { plats._html = html; plats.innerHTML = html; }
}

async function uppdateraVantande() {
  const k = await api('/api/kov');
  if (k.ok) aktuellaVantande = new Set(k.data.forhandlingar.filter(f => f.kovBeslut === 'VANTANDE').map(f => f.id));
  markeraNasta();
}
/* Nästa rimliga åtgärd: servern säger vilken (data.nasta, besökarens egna jobb); en väntande KoV-förfrågan går före.
   Knappen får märket "Nästa", och ordningsraden en riktig knapp till rätt steg. */
let nastaId = null;
const NASTA_IDX = {'kor-batch': 0, 'hamta-katalog': 1, 'forhandla-b': 2, 'transfer-b': 3, 'forhandla-a': 4, 'transfer-a': 5, 'kov-godkann': 4, 'analysera': 6};
/* Efter Leverera A är sista steget att se analysen (steg 6). Raden pekar dit tills besökaren öppnat steg 6; därefter tar den slut. */
const analysSedd = () => { try { return sessionStorage.getItem('svada-analys-sedd') === '1'; } catch (e) { return false; } };
/* En kort ruta intill en knapp som ser avstängd ut: försvinner av sig själv (4 s, längre medan musen eller tangentbordsfokus är i den), vid nästa klick, tangent (Esc stänger bara rutan) eller rullning. */
let knappTipsTimer = null;
function knappTipsBort() { clearTimeout(knappTipsTimer); $$('.knapptips').forEach(t => t.remove()); }
function visaKnappTips(knapp) {
  knappTipsBort();
  const t = document.createElement('div'); t.className = 'knapptips'; t.setAttribute('role', 'status');
  t.innerHTML = esc(knapp.dataset.tips || knapp.title || '') + ` <a href="#steg-3" data-gaforhandla="1">${L('→ Gå till Förhandla Distribution A', '→ Go to Negotiate Distribution A')}</a>`;
  /* Rutan läggs direkt efter knappen i dokumentet (så att länken nås med Tab) men placeras med fast position intill den. */
  knapp.insertAdjacentElement('afterend', t);
  const r = knapp.getBoundingClientRect();
  /* Ryms inte rutan under knappen (knappen nära fönstrets underkant) läggs den ovanför. */
  t.style.top = Math.round(r.bottom + 8 + t.offsetHeight > window.innerHeight - 8 ? Math.max(8, r.top - 8 - t.offsetHeight) : r.bottom + 8) + 'px';
  t.style.left = Math.max(8, Math.round(Math.min(r.left, window.innerWidth - t.offsetWidth - 12))) + 'px';
  const vanta = () => clearTimeout(knappTipsTimer), borja = () => { vanta(); knappTipsTimer = setTimeout(knappTipsBort, 1500); };
  t.addEventListener('mouseenter', vanta); t.addEventListener('mouseleave', borja);
  t.addEventListener('focusin', vanta); t.addEventListener('focusout', borja);
  knappTipsTimer = setTimeout(knappTipsBort, 4000);
}
const ejAktiv = b => b.disabled || b.getAttribute('aria-disabled') === 'true';
document.addEventListener('keydown', e => {
  if (!$('.knapptips')) return;
  /* Esc stänger bara rutan (stopImmediatePropagation: sidans egen Esc-lyssnare får inte också stänga panelen), även när fokus står i rutan. */
  if (e.key === 'Escape') { knappTipsBort(); e.stopImmediatePropagation(); e.preventDefault(); } else if (e.target.closest('.knapptips')) return; else if (!['Shift', 'Control', 'Alt', 'Meta', 'Tab'].includes(e.key)) knappTipsBort();
}, true);
window.addEventListener('scroll', () => { if ($('.knapptips')) knappTipsBort(); }, {passive: true});
function markeraNasta() {
  /* Idempotent: en knapp som redan är markerad rörs inte (annars sattes märket om vid varje statusrunda), och en avstängd knapp markeras aldrig (besökartestet 2026-10-22: KoV-knappen blinkade medan den var grå). */
  const id = (aktuellaVantande && aktuellaVantande.size) ? 'kov-godkann' : nastaId;
  const nk = $('#nastaknapp');
  if (id && id !== 'analysera') { try { sessionStorage.removeItem('svada-analys-sedd'); } catch (e) {} }      // en ny runda ska peka på analysen igen
  /* "analysera" är ett steg utan knapp (steg 6): bara ordningsraden pekar dit, och bara tills steg 6 öppnats. */
  const sel = (id && id in NASTA_IDX && id !== 'analysera') ? (id === 'kov-godkann' ? 'button.kor[data-kovbeslut="godkann"]' : `button.kor[data-atgard="${id}"]`) : null;
  $$('button.kor.nasta').forEach(b => { if (!sel || !b.matches(sel) || ejAktiv(b)) { b.classList.remove('nasta'); b.removeAttribute('data-nasta'); } });
  const visaAnalys = id === 'analysera' && !analysSedd();
  /* Slutet på raden: efter Leverera A och när steg 6 setts säger raden uttryckligen att kedjan är genomgången (provrunda 2026-10-26). */
  const slut = $('#nastaslut');
  if (slut) { const klar = id === 'analysera' && analysSedd(); slut.hidden = !klar; slut.textContent = klar ? TX.nastaSlut : ''; }
  if (!sel && !visaAnalys) { if (nk) { nk.hidden = true; nk.textContent = ''; } return; }
  if (sel) $$(sel).forEach(b => { if (!ejAktiv(b) && !b.classList.contains('nasta')) { b.classList.add('nasta'); b.dataset.nasta = TX.nasta; } });
  const chip = $$('#ordning .ordningsteg button[data-hopp]:not(.nastaknapp)')[NASTA_IDX[id]];
  if (nk && chip) {
    nk.hidden = false;
    nk.textContent = TX.nastaKnapp + chip.textContent.replace(/^\s*\d+\s*/, '');
    nk.dataset.hopp = chip.dataset.hopp;
    /* Bara en väntande förfrågan skickar till KoV-rutan; annars hamnar besökaren på knappen som ska tryckas (F3). */
    if (id === 'kov-godkann' && chip.dataset.kov) nk.dataset.kov = chip.dataset.kov; else delete nk.dataset.kov;
    if (sel) nk.dataset.fokus = sel; else delete nk.dataset.fokus;
  } else if (nk) nk.hidden = true;
}


/* Pollar jobbet var 1,5 s tills det är klart. Ett nytt jobb i samma ruta
   avbryter det gamla (plats.dataset.jid). */
async function foljJobb(jid, plats) {
  /* Rutan är min så länge dess jid är mitt. Kontrollen görs EFTER varje await: ett sent svar får aldrig återfylla en ruta
     som rensats (rensaLoggplatser) eller tagits över av ett nyare jobb. */
  const minRuta = () => plats.dataset.jid === String(jid);
  plats.dataset.jid = String(jid);
  senastFoljd = {jid, plats, slut: null};
  plats.innerHTML = `<p class="meta">${esc(TX.jobbStartar)}</p>`;
  for (let forsok = 0; forsok < 400; forsok++) {
    if (!minRuta()) return;
    const {ok, data} = await api('/api/jobb/' + jid);
    if (!minRuta()) return;
    if (!ok) {
      plats.innerHTML = `<p class="felrad">${esc(fmt(TX.jobbSvararInte, {fel: data.fel || ''}))}</p>`;
      return;
    }
    skrivLoggruta(plats, data);
    if (data.status !== 'kör' && data.status !== 'kö') {
      if (senastFoljd && senastFoljd.jid === jid) senastFoljd.slut = Date.now();
      if (data.utfall === 'nekad') handelse('atgard_nekad');
      await uppdateraVantande();
      if (!minRuta()) return;
      skrivLoggruta(plats, data);
      break;
    }
    await sov(1500);
  }
  if (!minRuta()) return;
  /* Kön och avtalen läses FÖRST, så att knapparna aldrig hinner vara aktiva mot
     en förhandling som just avgjorts (ett nytt klick skulle då kunna häva avtal). */
  if (valt === 3) await laddaKovRuta();
  laddaStatus(); laddaDetaljer();
}

/* ------------------------------------------------------------------ jobb */
let valtJobb = null;
async function laddaJobb() {
  const {ok, data} = await api('/api/jobb');
  if (!ok) return;
  /* Kön hos providern kan ta flera sekunder att läsa: rita jobblistan och loggen FÖRST (annars stod det förra jobbets
     logg kvar i cirka 10 s efter ett hopp hit, M3), läs kön och rita sedan om listan så att märket "väntar på KoV" stämmer. */
  ritaJobb(data);
  await uppdateraVantande();
  ritaJobb(data);
}
function ritaJobb(data) {
  const jobb = data.jobb.slice().reverse();
  if (valtJobb === null && jobb.length) valtJobb = jobb[0].id;
  $('#jobblista').innerHTML = jobb.map(j =>
    `<tr><td><a href="#jobb-${j.id}">${j.id}</a></td><td>${esc(j.etikett)}</td>
     <td class="res-${esc((j.utfall === 'nekad' ? 'klar' : j.utfall ? 'AVVISAD' : j.status).toUpperCase())}">${['kor', 'ko'].includes(loggStatus(j)) ? '<span class="snurr" aria-hidden="true"></span>' : ''}${esc(TX[LSTATUS[loggStatus(j)]])}</td>
     <td>${esc(j.startad)}</td></tr>`).join('')
    || `<tr><td colspan="4">${L('Inget jobb har körts ännu.', 'No job has run yet.')}</td></tr>`;
  const j = data.jobb.find(x => x.id === valtJobb);
  if (!j && valtJobb !== null && notisJobb !== valtJobb) {      // F13: en länk till ett jobb som inte finns
    notisJobb = valtJobb;
    lanknotis(L(`Jobb ${valtJobb} finns inte (längre). Välj ett jobb i listan.`, `Job ${valtJobb} does not exist (any more). Pick a job in the list.`));
  }
  const pagar = $('#jobbpagar'), arIgang = !!j && ['kor', 'ko'].includes(loggStatus(j));
  pagar.innerHTML = arIgang ? `<span class="snurr" aria-hidden="true"></span>${esc(fmt(TX.jobbPagar, {id: j.id, etikett: j.etikett}))}` : '';
  $('#jobblogg').textContent = j
    ? j.rader.map(r => `${r.tid}  ${r.text}`).join('\n')
      + (j.resultat && j.resultat.rapport ? '\n\n' + j.resultat.rapport : '')
    : (jobb.length ? L('Välj ett jobb i listan.', 'Pick a job in the list.') : '');   // L15: inget dubbelt "tomt"-besked
}

/* -------------------------------------------------------------- auditlogg */
async function laddaAudit() {
  const {ok, data} = await api('/api/audit');
  if (!ok) return;
  const filter = $('#auditfilter').value;
  const rader = data.handelser.filter(h => !filter || String(h.led) === filter);
  $('#auditsammanfattning').textContent =
    L(`${data.count} händelser`, `${data.count} events`) +
    (Object.keys(data.perLed || {}).length ? L(' · per steg: ', ' · per step: ') + Object.entries(data.perLed).map(([k, v]) => `${k}:${v}`).join(' ') : '') +
    (data.kallfel.length ? L(` · källfel: `, ` · source errors: `) + data.kallfel.map(k => k.text).join('; ') : '');
  const kedja = data.kedja || {};
  $('#auditkedja').textContent = kedja.antalLankar
    ? L('Hashkedja för hela demon, alla besökares händelser (visar mekanismen, bevaras inte vid omstart): ',
        'Hash chain for the whole demo, all visitors\' events (shows the mechanism, not kept across restarts): ')
      + kedja.antalLankar + L(' länkade händelser, ', ' linked events, ')
      + (kedja.intakt ? L('INTAKT', 'INTACT')
                      : L(`TRASIG vid länk ${kedja.trasigLank}: ${kedja.fel}`,
                          `BROKEN at link ${kedja.trasigLank}: ${kedja.fel}`))
    : L('Hashkedja: inga länkade händelser än.', 'Hash chain: no linked events yet.');
  $('#auditkedja').textContent += L(' Varje händelse bär en kontrollsumma av den förra, så en ändrad eller borttagen händelse syns.',
    ' Each event carries a checksum of the previous one, so a changed or removed event shows.');
  $('#auditlogg').innerHTML = rader.slice().reverse().map(h =>
    `<tr><td>${esc(h.tid)}</td><td>${esc(h.led)}</td><td>${esc(kallaVisning(h.kalla))}</td>
     <td class="res-${esc(h.resultat)}">${esc(resKod(h.resultat))}</td>
     <td>${esc(h.text)}<br><code>${esc(JSON.stringify(h.detaljer))}</code></td></tr>`
  ).join('') || `<tr><td colspan="5">${L('Inga händelser.', 'No events.')}</td></tr>`;
}

/* Källan i auditloggen: i den externa varianten ett läsbart namn i stället för containernamnet. */
function kallaVisning(k) {
  if (VARIANT !== 'extern') return k;
  const namn = {
    'dashboard': L('kontrollrummet', 'the control room'),
    'edc-consumer': L('stadens connector', 'the city connector'),
    'edc-provider (KoV-gate)': L('DHI:s connector (KoV-grind)', 'DHI connector (KoV gate)'),
    'edc-provider': L('DHI:s connector', 'DHI connector'),
    'ingest-service': L('stadens mottagning', 'the city intake'),
    'stad-gateway': L('stadens gateway', 'the city gateway'),
    'fcf-sim': L('FCF-simulatorn', 'the FCF simulator'),
    'identity-hub-svada': L('Svadas utfärdare', 'the Svada issuer')
  };
  return namn[k] || k;
}

/* ------------------------------------------------------------ suveränitet */
async function laddaKov() {
  laddaOdrl();
  laddaAvtalLista();
  const [{ok, data}, reg] = await Promise.all([api('/api/kov'), api('/api/avtal')]);
  /* DHI:s avtals-id -> status i stadens register, så att hävda avtal inte visas som bara FINALIZED. */
  const hav = {};
  (reg.ok ? reg.data.avtal : []).forEach(a => { if (a.dhiAvtalId && a.status !== 'GALLANDE') hav[a.dhiAvtalId] = a.status === 'UTGANGET' ? L('utgånget', 'expired') : L('hävt', 'revoked'); });
  if (!ok) { $('#kovlista').innerHTML =
    `<tr><td colspan="5">${L('Providern svarar inte: ', 'The provider does not respond: ')}${esc(data.fel)}</td></tr>`; return; }
  $('#kovapi').textContent = data.api || '';
  $('#kovapirad').hidden = !data.api || VARIANT === 'extern';      // externt visas ingen adress, inte ens sökvägen
  /* Väntande först, sedan de senaste besluten. */
  const vantande = data.forhandlingar.filter(f => f.kovBeslut === 'VANTANDE');
  aktuellaVantande = new Set(vantande.map(f => f.id));
  const ovriga = data.forhandlingar.filter(f => f.kovBeslut !== 'VANTANDE').slice(-8);
  $('#kovantal').textContent = L(
    `Providerns lista över förhandlingar om A: ${data.count} hittills, ${vantande.length ? vantande.length + ' väntar på beslut' : 'ingen väntar på beslut (alla är avgjorda)'}`
      + (ovriga.length < data.count - vantande.length ? ` (visar de ${ovriga.length} senaste avgjorda)` : ''),
    `The provider’s list of negotiations for A: ${data.count} so far, ${vantande.length ? vantande.length + ' waiting for a decision' : 'none waiting for a decision (all are decided)'}`
      + (ovriga.length < data.count - vantande.length ? ` (showing the ${ovriga.length} latest decided)` : ''));
  $('#kovlista').innerHTML = vantande.concat(ovriga).map(f => `
    <tr><td><code>${esc(f.id)}</code></td>
        <td>${esc(f.assetId)}</td>
        <td>${esc(f.state)}${f.pending ? ' (pending)' : ''}</td>
        <td class="res-${esc(f.kovBeslut)}">${esc(resKod(f.kovBeslut))}</td>
        <td>${f.kovBeslut === 'VANTANDE' ? `
          <button class="kor godkann" data-kov-id="${esc(f.id)}" data-kov-val="godkann">${L('Godkänn', 'Approve')}</button>
          <button class="kor fara" data-kov-id="${esc(f.id)}" data-kov-val="avsla">${L('Avslå', 'Reject')}</button>`
        : esc(f.contractAgreementId || f.errorDetail || '–') + (hav[f.contractAgreementId] ? ` <b class="res-HAVT">(${esc(hav[f.contractAgreementId])})</b>` : '')}</td></tr>`).join('')
    || `<tr><td colspan="5">${L('Kön är tom – ingen förhandling om A har begärts.',
                                 'The queue is empty – no negotiation for A has been requested.')}</td></tr>`;
}

async function laddaAvtalLista() {
  const {ok, data} = await api('/api/avtal');
  const kropp = $('#avtallista');
  if (!kropp) return;
  if (!ok) { kropp.innerHTML = `<tr><td colspan="5">${esc(data.fel || '')}</td></tr>`; return; }
  const namn = {GALLANDE: L('GÄLLER', 'VALID'), HAVT: L('HÄVT', 'REVOKED'), UTGANGET: L('UTGÅNGET', 'EXPIRED'), OKAND: L('OKÄND', 'UNKNOWN')};
  $('#avtalantal').textContent = L(`${data.avtal.length} avtal i stadens register`, `${data.avtal.length} agreements in the city's register`);
  kropp.innerHTML = data.avtal.map(a => {
    const r = a.regler || {};
    const villkor = [].concat(r.tillatet || [], (r.forbjudet || []).map(x => L('förbjudet: ', 'prohibited: ') + x),
                              (r.plikter || []).map(x => L('plikt: ', 'duty: ') + x)).join('; ');
    const orsakNamn = {AVSLAG: L('avslag på ny begäran', 'rejection of a new request'), EXPLICIT: L('KoV häver direkt', 'KoV revoked directly')};
    const havning = a.havning ? ` (${esc(orsakNamn[a.havning.orsak] || a.havning.orsak)}, ${esc(String(a.havning.tid || '').slice(0, 19).replace('T', ' '))} UTC)` : '';
    return `<tr><td><a href="/avtal/${esc(a.id)}?lang=${SPRAK}"><code>${esc(String(a.id).slice(0, 8))}…</code></a></td>
      <td>${esc(a.distribution)}</td>
      <td class="res-${esc(a.status)}">${esc(namn[a.status] || a.status)}${havning}</td>
      <td>${esc(villkor)}</td>
      <td>${a.distribution === 'A' && a.status === 'GALLANDE' && a.dhiAvtalId
        ? `<button class="kor fara" data-hav-id="${esc(a.dhiAvtalId)}">${L('KoV häver avtalet', 'KoV revokes the agreement')}</button>` : '–'}</td></tr>`;
  }).join('') || `<tr><td colspan="5">${L('Inga avtal ännu.', 'No agreements yet.')}</td></tr>`;
}

async function kovHav(dhiId) {
  handelse('atgard_kov-hav');
  const {ok, status, data} = await api(`/api/kov/avtal/${encodeURIComponent(dhiId)}/hav`, 'POST');
  if (!ok) { lanknotis(fmt(TX.jobbFelStart, {fel: data.fel || ('HTTP ' + status)})); return; }
  valtJobb = data.id; visa('jobb'); laddaJobb(); tillJobblogg();
}

async function kovBeslut(id, beslut) {
  handelse('atgard_kov-' + beslut);
  const {ok, status, data} = await api(`/api/kov/${encodeURIComponent(id)}/${encodeURIComponent(beslut)}`, 'POST');
  if (!ok) { lanknotis(fmt(TX.jobbFelStart, {fel: data.fel || ('HTTP ' + status)})); return; }
  valtJobb = data.id; visa('jobb'); laddaJobb(); tillJobblogg();
}

/* Villkoren visas READ-ONLY när fliken öppnas (GET), försöket görs först när
   någon trycker på knappen (POST). Att se villkoren är inte samma sak som
   att pröva dem, och bara försöket hamnar i auditloggen. */
async function laddaOdrl() {
  /* Bara första gången: varje anrop är en katalogförfrågan mot providern. */
  if ($('#odrlsvar').innerHTML.trim()) return;
  const {ok, data} = await api('/api/odrl/a');
  if (ok) renderaOdrl(data, L('Gällande villkor för distribution A', 'Current terms for distribution A'), 'normal');
}

function renderaOdrl(data, rubrik, klass) {
  $('#odrlsvar').innerHTML = `
    <div class="ruta ${klass}">
      <h2>${esc(rubrik)}</h2>
      <p><b>${L('Dataägare:', 'Data owner:')}</b> ${esc(data.dataRightsHolder)}<br>
         <b>${L('ODRL-villkor i erbjudandet:', 'ODRL terms in the offer:')}</b> ${esc(data.odrlTerms)}</p>
      <ul>${data.motivering.map(m => `<li>${esc(m.text)}</li>`).join('')}</ul>
      <table><tr><th>permission</th><th>prohibition</th><th>obligation</th></tr>
      <tr><td>${esc(data.policy.permission.join(', '))}</td>
          <td><b>${esc(data.policy.prohibition.join(', '))}</b></td>
          <td>${esc(data.policy.obligation.join(', '))}</td></tr></table>
      <details><summary>${L('Hela erbjudandet (rå JSON-LD ur DSP-katalogen)', 'The whole offer (raw JSON-LD from the DSP catalogue)')}</summary>
        <pre>${esc(JSON.stringify(data.raPolicy, null, 2))}</pre></details>
    </div>`;
}

/* ------------------------------------------------------------ felinjektion */
/* Felinjektionens lägen: ett läsbart namn på vyns språk, med identifieraren (som den heter i simulatorn) bredvid. */
function lageNamn(k) {
  const n = {
    schemadrift: L('Schemadrift', 'Schema drift'),
    saknade_parametrar: L('Saknade parametrar', 'Missing parameters'),
    gis_i_b: L('Brunns-GIS i B (avtalsbrott)', 'Chamber GIS in B (breach of contract)')
  };
  return n[k] || k;
}
async function laddaFel() {
  const {ok, data} = await api('/api/felinjektion');
  if (!ok) return;
  $('#felomfattning').innerHTML = data.egen
    ? `<b>${L('Läget är ditt eget:', 'The mode is your own:')}</b> ${L('det slås på i modellen bara medan din egen leverans av B (eller A) körs, och slås av direkt efteråt. Det påverkar ingen annan besökare.', 'it is switched on in the model only while your own delivery of B (or A) runs, and is switched off right after. It does not affect any other visitor.')}`
    : `<b>${L('Gäller alla besökare:', 'Applies to all visitors:')}</b> ${L('i den här varianten är felinjektionen gemensam: ett påslaget läge gäller nästa leverans för alla och slås av av sig själv.', 'in this variant the fault injection is shared: a mode that is switched on applies to everyone\'s next delivery and switches itself off.')}`;
  const beskr = data.beskrivning || {};
  $('#felreglage').innerHTML = Object.entries(data.lagen).map(([k, v]) =>
    `<label class="reglage"><input type="checkbox" aria-label="${esc(lageNamn(k))}" ${v ? 'checked' : ''}
      data-fellage="${esc(k)}"> <b>${esc(lageNamn(k))}</b> (<code>${esc(k)}</code>) –
      ${esc(beskr[k] || '')}</label>`).join('');
  $('#felstatus').innerHTML = data.aktiv
    ? `<b class="res-AVVISAD">${L('Felinjektion AKTIV', 'Fault injection ACTIVE')}</b> – ${data.egen ? L('din nästa leverans ska avvisas av mottagningen (läget slås på bara medan den körs).', 'your next delivery should be rejected by the intake (the mode is switched on only while it runs).') : L('nästa leverans ska avvisas av mottagningen.', 'the next delivery should be rejected by the intake.')}`
    : `<b class="res-LEVERERAD">${L('Felinjektion av', 'Fault injection off')}</b> – ${L('dataprodukten levereras oförändrad.', 'the data product is delivered unchanged.')}`;
  $('#felstatus').insertAdjacentHTML('beforeend', ' <span class="skyddtid" id="felrest"></span>');
  hamtaSkydd();
  laddaLeveranser();
}

async function sattFel(namn, varde) {
  const kropp = {}; kropp[namn] = varde;
  const {ok, data} = await api('/api/felinjektion', 'POST', kropp);
  const svarTid = Date.now();       // väntetiden räknas från svaret, inte från när omläsningen är klar (A2-08)
  /* Kryssrutorna är data-stabil: ritas samma html som sist hoppas tilldelningen över, och då skulle en ruta som besökaren
     just kryssat (men servern nekade) stå kvar ikryssad. Tvinga omritning från servern. */
  const reglage = $('#felreglage'); if (reglage) reglage._sistaHtml = null;
  await laddaFel();
  /* Avvisad (t.ex. återhämtningsperioden efter en nyss avslutad felinjektion): säg varför, med tickande tid vid kryssrutorna. */
  if (!ok && data.fel) {
    felAvslagTill = data.vantaSek ? svarTid + data.vantaSek * 1000 : 0;
    felAvslagText = data.fel;
    visaFelAvslag();
  }
}

let felAvslagTill = 0, felAvslagText = '';
function visaFelAvslag() {
  /* Orsaken står vid kryssrutorna och räknar ned; texten försvinner när tiden gått. */
  const rot = $('#felreglage'); if (!rot) return;
  let el = $('#felavslag');
  if (!felAvslagText || (felAvslagTill && Date.now() >= felAvslagTill)) { if (el) el.remove(); felAvslagText = ''; return; }
  if (!el) { el = document.createElement('p'); el.id = 'felavslag'; el.className = 'felrad'; el.setAttribute('role', 'status'); rot.after(el); }
  const kvar = felAvslagTill ? Math.max(0, Math.ceil((felAvslagTill - Date.now()) / 1000)) : 0;
  el.textContent = felAvslagTill ? felAvslagText.replace(/\d+ s/, kvar + ' s') : felAvslagText;
}
setInterval(visaFelAvslag, 1000);
async function nollstallFel() {
  await api('/api/felinjektion/reset', 'POST');
  laddaFel();
}

async function laddaLeveranser() {
  const {ok, data} = await api('/api/audit');
  if (!ok) return;
  const rader = data.handelser.filter(h => h.kalla === 'ingest-service').slice(-8);
  $('#felresultat').innerHTML = rader.reverse().map(h =>
    `<tr><td>${esc(h.tid)}</td><td class="res-${esc(h.resultat)}">${esc(resKod(h.resultat))}</td>
     <td>${esc(h.text)}</td></tr>`).join('')
    || `<tr><td colspan="3">${L('Inga leveranser ännu.', 'No deliveries yet.')}</td></tr>`;
}

/* ----------------------------------------------------------- kedjevyn */
const smal = window.matchMedia('(max-width: 1100px)');
const mobil = window.matchMedia('(max-width: 700px)');   // telefon: kartan och tabellernas sidledsledtråd
let valt = null;

function laddaPanel(nr) {
  if (nr === 2) laddaOdrlVillkor();
  if (nr === 3) { laddaKovRuta(); laddaSvada(); }
  if (nr === 5) laddaProv();
  if (nr === 6) { forvarmaKarta(); laddaAnalys(); try { sessionStorage.setItem('svada-analys-sedd', '1'); } catch (e) {} setTimeout(markeraNasta, 0); }
}
/* Steg 6: så snart steget öppnas förbereds kartan: kartbiblioteket laddas (lokalt) och anslutningen till kartplattorna förberedds,
   så att kartan inte behöver vänta på dem när analysen av A är klar. Ingen kartplatta begärs förrän avtalet kontrollerats. */
let kartForvarmd = false;
function forvarmaKarta() {
  if (kartForvarmd) return;
  kartForvarmd = true;
  laddaLeaflet();
  const l = document.createElement('link');
  l.rel = 'preconnect'; l.href = 'https://tile.openstreetmap.org'; l.crossOrigin = 'anonymous';
  document.head.appendChild(l);
}

function oppna(nr, flytta, kovFokus) {
  if (!(nr >= 1 && nr <= 6)) return;
  if (nr !== valt && harRort) handelse('steg_' + nr);
  valt = nr;
  $$('.panel').forEach(p => { p.hidden = p.id !== 'steg-' + nr; });
  $$('.nod').forEach(n => n.setAttribute('aria-expanded',
    String(n.id === 'nod-' + nr || (n.id === 'nod-kov' && nr === 3 && !!kovFokus))));
  placera();
  try { history.replaceState(null, '', '#steg-' + nr); } catch (e) {}
  try { localStorage.setItem('svada-steg', String(nr)); } catch (e) {}
  uppdateraStegrad();
  laddaPanel(nr);
  const panel = document.getElementById('steg-' + nr);
  $$('.kovruta').forEach(r => r.classList.toggle('fokus', !!kovFokus));
  if (kovFokus) { const r = $('#kovruta'); if (r) setTimeout(() => r.scrollIntoView({block: 'nearest'}), 50); }
  else if (flytta) panel.scrollIntoView({behavior: lugnt() ? 'auto' : 'smooth', block: 'start'});
}

/* Bred skärm: panelen ligger under bilden. Smal skärm: direkt under det
   klickade steget (steg 6 efter KoV-noden). */
function placera() {
  if (valt === null) return;
  const p = document.getElementById('steg-' + valt);
  if (!p) return;
  if (smal.matches) {
    const mal = document.getElementById('nod-' + (valt === 3 ? 'kov' : valt));
    if (mal && mal.nextElementSibling !== p) mal.after(p);
  } else {
    const rot = $('#paneler');
    if (p.parentNode !== rot) rot.appendChild(p);
  }
}

function stang() {
  const nr = valt; valt = null;
  $$('.panel').forEach(p => { p.hidden = true; });
  $$('.nod').forEach(n => n.setAttribute('aria-expanded', 'false'));
  try { history.replaceState(null, '', '#kedjan'); } catch (e) {}
  try { localStorage.setItem('svada-steg', 'stangd'); } catch (e) {}
  uppdateraStegrad();
  const nod = nr && document.getElementById('nod-' + nr);
  if (nod) nod.focus();
}

/* ---- pilar (bara bred skärm) ---- */
function ritaPilar() {
  const svg = $('#pilar'), bild = $('#bild');
  if (!svg || !bild) return;
  if (smal.matches || !bild.offsetWidth) { svg.innerHTML = ''; return; }
  const r0 = bild.getBoundingClientRect();
  const box = id => {
    const r = document.getElementById(id).getBoundingClientRect();
    return {x: r.left - r0.left, y: r.top - r0.top, w: r.width, h: r.height};
  };
  let ut = `<defs>
    <marker id="pil" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker>
    <marker id="pilds" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>`;
  for (let i = 1; i < 6; i++) {
    const a = box('nod-' + i), b = box('nod-' + (i + 1));
    const ds = i >= 1 && i <= 4;
    const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x - 2, y2 = b.y + b.h / 2;
    let d;
    if (Math.abs(y1 - y2) < 4) d = `M${x1},${y1} L${x2},${y2}`;
    else { const mx = (x1 + x2) / 2; d = `M${x1},${y1} L${mx},${y1} L${mx},${y2} L${x2},${y2}`; }
    ut += `<path class="${ds ? 'dsp' : ''}" d="${d}" marker-end="url(#${ds ? 'pilds' : 'pil'})"/>`;
  }
  const k = box('nod-kov'), s6 = box('nod-3');
  ut += `<path class="kovpil" d="M${k.x + k.w / 2},${k.y} L${s6.x + s6.w / 2},${s6.y + s6.h + 2}" marker-end="url(#pilds)"/>`;
  svg.innerHTML = ut;
}

/* ---- tunn stegrad: syns när bilden har scrollats ur bild ---- */
let bildSynlig = true;
function uppdateraStegrad() {
  const r = $('#stegrad');
  if (!r) return;
  const iKedjan = !!$('section#kedjan.aktiv');
  /* På smal skärm ligger panelerna inne i bilden, så bildens synlighet säger inget: stegraden visas när man scrollat bort från toppen. */
  r.hidden = !iKedjan || window.scrollY < 120 || (!smal.matches && bildSynlig);
  $$('[data-steg]', r).forEach(b => {
    if (+b.dataset.steg === valt) b.setAttribute('aria-current', 'step');
    else b.removeAttribute('aria-current');
  });
}

/* Tabeller som är bredare än skärmen får en ledtråd ("dra i sidled") via attributet data-rull. */
function markeraRullning() {
  if (!mobil.matches) { $$('section.flik table[data-rull]').forEach(t => t.removeAttribute('data-rull')); return; }
  $$('section.flik table').forEach(t => {
    if (!t.offsetParent) return;
    const rullar = t.scrollWidth > t.clientWidth + 4;
    if (rullar !== t.hasAttribute('data-rull')) t.toggleAttribute('data-rull', rullar);
  });
}
setInterval(markeraRullning, 1500);
window.addEventListener('resize', markeraRullning);

let stegradVantar = false;
window.addEventListener('scroll', () => {
  if (stegradVantar) return;
  stegradVantar = true;
  requestAnimationFrame(() => { stegradVantar = false; uppdateraStegrad(); });
}, {passive: true});

/* ---- nedräkning till den nattliga återställningen (publika demon) ----
   Servern anger nästa tidpunkt och sin egen tid; klockskillnaden räknas bort, så att räknaren går rätt även om besökarens klocka är fel.
   Visas bara när servern har ett schema (DEMO_ATERSTALL_KL). Skärps till orange vid 15 minuter och röd med en remsa vid 5. */
/* Tickande tider i den publika demon (skydd.py): servern anger sekunder kvar, webbläsaren räknar ner själv.
   Tre tider: utestängd part släpps in igen, felinjektionen slås av, och väntan innan nästa körning. */
let skyddInfo = {utestangningS: {}, felinjektionS: null, pausS: 0}, skyddHamtad = Date.now(), skyddPausNu = false;
const mmss = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const skyddRest = s => Math.max(0, Math.ceil(s - (Date.now() - skyddHamtad) / 1000));
async function hamtaSkydd() {
  const {ok, data} = await api('/api/skydd');
  if (!ok || !data) return;
  skyddInfo = data; skyddHamtad = Date.now();
  tickaSkydd();
}
function tickaSkydd() {
  $$('[data-utestang]').forEach(el => {
    const s = skyddInfo.utestangningS[el.dataset.utestang];
    el.textContent = s == null ? '' : L(`Släpps in igen automatiskt om ${mmss(skyddRest(s))}`, `Let back in automatically in ${mmss(skyddRest(s))}`);
  });
  const fel = $('#felrest');
  if (fel) fel.textContent = skyddInfo.felinjektionS == null ? ''
    : L(`Slås av automatiskt om ${mmss(skyddRest(skyddInfo.felinjektionS))}`, `Switched off automatically in ${mmss(skyddRest(skyddInfo.felinjektionS))}`);
  visaLasHint();
  const paus = skyddInfo.pausS ? skyddRest(skyddInfo.pausS) : 0, remsa = $('#pausremsa'), sr = $('#skyddsr');
  remsa.hidden = !paus;
  if (paus) remsa.textContent = L(`Vänta ${paus} s innan nästa körning – du körde just ett jobb, så att andra besökare också hinner före.`,
                                  `Wait ${paus} s before the next run – you just ran a job, so other visitors get their turn.`);
  if (!!paus !== skyddPausNu) {                     // läget byts: knapparna och skärmläsaren följer med, inte varje sekund
    skyddPausNu = !!paus;
    $$('button.kor[data-atgard]:not([data-svada])').forEach(b => { b.disabled = !!paus || !!jobbAktivtNu; });   // direkt, utan att vänta på statusrundan
    sr.textContent = paus ? L('Vänta några sekunder innan nästa körning.', 'Wait a few seconds before the next run.')
                          : L('Du kan köra igen.', 'You can run again.');
    laddaStatus();
  }
}
let aterstallInfo = null, aterstallForskjutning = 0, aterstallTillstand = '';
async function hamtaAterstall() {
  /* ?aterstall=<minuter> simulerar läget i den egna vyn: 190 = lugnt, 12 = snart, 4 = röd, 0.5 = sista halvminuten, -2 = pågår. */
  const sim = new URLSearchParams(location.search).get('aterstall');
  if (sim !== null && sim.trim() !== '' && !isNaN(Number(sim))) {
    const nu = Date.now();
    aterstallInfo = {nastaUtc: new Date(nu + Number(sim) * 60000).toISOString(), nuUtc: new Date(nu).toISOString(),
                     klockslag: '04:00', varaktighetMin: 10, simulerad: true};
    aterstallForskjutning = 0;
    uppdateraAterstall();
    return;
  }
  const {ok, data} = await api('/api/aterstallning');
  if (!ok || !data || !data.nastaUtc) { aterstallInfo = null; uppdateraAterstall(); return; }
  aterstallInfo = data;
  aterstallForskjutning = Date.parse(data.nuUtc) - Date.now();
  uppdateraAterstall();
}
/* Klockslaget i BESÖKARENS tidszon (och serverns, för förklaringen): nästa nollställning är ett ögonblick, inte en klocktid. */
function aterstallTid(d, tz) {
  try { return new Intl.DateTimeFormat(SPRAK === 'en' ? 'en-GB' : 'sv-SE', {hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: tz || undefined}).format(d); }
  catch (e) { return aterstallInfo.klockslag; }
}
function aterstallZon(d, tz) {
  try { return (new Intl.DateTimeFormat('en-GB', {timeZoneName: 'short', hour: '2-digit', timeZone: tz || undefined}).formatToParts(d).find(x => x.type === 'timeZoneName') || {}).value || ''; }
  catch (e) { return ''; }
}
function oppnaAterstallInfo() {
  if (!aterstallInfo) return;
  const d = new Date(aterstallInfo.nastaUtc), tz = aterstallInfo.tz || 'Europe/Stockholm';
  const lokal = aterstallTid(d), server = aterstallTid(d, tz);
  const likadan = lokal === server && aterstallZon(d) === aterstallZon(d, tz);
  const nar = likadan
    ? L(`klockan ${server} (${aterstallZon(d, tz)})`, `at ${server} (${aterstallZon(d, tz)})`)
    : L(`klockan ${lokal} i din tidszon (${aterstallZon(d)}), det vill säga ${server} svensk tid`, `at ${lokal} in your time zone (${aterstallZon(d)}), which is ${server} Swedish time`);
  const r = (skyddInfo && skyddInfo.regler) || {};
  const min = s => Math.round(s / 60);
  const delar = [];     // bara reglerna som gäller: utan utestängning (avstängd i den externa demon) nämns den inte
  if (r.utestangningS) delar.push([`en utesluten part släpps in igen efter ${min(r.utestangningS)} min`, `an excluded party is let back in after ${min(r.utestangningS)} min`]);
  if (r.felinjektionS) delar.push([`felinjektionen slås av efter ${min(r.felinjektionS)} min`, `fault injection is switched off after ${min(r.felinjektionS)} min`]);
  if (r.pausS) delar.push([`efter ett jobb väntar du ${r.pausS} s så att andra besökare också hinner före`, `after a job you wait ${r.pausS} s so other visitors get their turn`]);
  const regler = delar.length ? `<li>${esc(L('Några saker städar sig själva under dagen: ' + delar.map(d => d[0]).join(', ') + '.',
    'A few things clean up by themselves during the day: ' + delar.map(d => d[1]).join(', ') + '.'))}</li>` : '';
  $('#aterstalldialogrubrik').textContent = L('Varför nollställs demon?', 'Why is the demo reset?');
  $('#aterstalldialogtext').innerHTML = `<p>${esc(L(`Nästa nollställning är ${nar}, och sedan varje natt.`, `The next reset is ${nar}, and then every night.`))}</p><ul>
    <li>${esc(L('Demon är delad: alla besökare ser samma kedja. Därför återställs den varje natt, så att nästa besökare börjar rent.', 'The demo is shared: all visitors see the same chain. It is therefore reset every night so the next visitor starts clean.'))}</li>
    <li>${esc(L('Det som händer: pågående körningar avbryts, all data raderas (avtal, förhandlingar, auditlogg, felinjektion) och du börjar om från steg 1. Det tar cirka 10 minuter, och sidan visar en väntesida under tiden.', 'What happens: runs in progress are cancelled, all data is deleted (agreements, negotiations, audit log, fault injection) and you start over from step 1. It takes about 10 minutes, and the page shows a waiting page meanwhile.'))}</li>
    ${regler}
    <li>${esc(L('Inget du gör här påverkar riktig data. Allt är en demo med modellerade värden.', 'Nothing you do here affects real data. Everything is a demo with modelled values.'))}</li></ul>`;
  $('#aterstalldialog').showModal();
}
document.addEventListener('click', e => {
  if (e.target.closest('#aterstallinfo, [data-aterstallinfo]')) oppnaAterstallInfo();
  else if (e.target.closest('#aterstallstang') || e.target === $('#aterstalldialog')) $('#aterstalldialog').close();
});
function aterstallMmss(kvar) {            // sista minuterna: m:ss
  const t = Math.max(0, Math.ceil(kvar / 1000));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
}
function aterstallRest(min) {
  if (min < 1) return L('mindre än 1 min', 'less than 1 min');
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h} h ${m} min` : `${m} min`;
}
function uppdateraAterstall() {
  const el = $('#aterstall'), remsa = $('#aterstallremsa'), sr = $('#aterstallsr');
  if (!el) return;
  const info = $('#aterstallinfo');
  if (!aterstallInfo) { el.hidden = true; info.hidden = true; remsa.hidden = true; aterstallTillstand = ''; return; }
  info.hidden = false;
  const kvar = Date.parse(aterstallInfo.nastaUtc) - (Date.now() + aterstallForskjutning);   // ms
  const min = Math.ceil(kvar / 60000);   // avrundat uppåt, som en vanlig nedräkning
  const pagar = kvar <= 0 && kvar > -aterstallInfo.varaktighetMin * 60000;
  let tillstand = 'lugn';
  if (pagar) tillstand = 'pagar'; else if (kvar <= 5 * 60000) tillstand = 'nu'; else if (kvar <= 15 * 60000) tillstand = 'snart';
  el.hidden = false;
  el.className = 'aterstall' + (tillstand === 'snart' ? ' snart' : (tillstand === 'nu' || tillstand === 'pagar') ? ' nu' : '') + (tillstand === 'nu' && kvar <= 60000 ? ' sista' : '');
  const kl = aterstallTid(new Date(aterstallInfo.nastaUtc));    // besökarens egen klocka
  if (pagar) {
    el.textContent = L('Nollställning pågår', 'Reset in progress');
    remsa.hidden = false;
    $('#aterstallremsatext').textContent = L('Demon nollställs just nu. Sidan kan vara otillgänglig i upp till tio minuter; ladda om den sedan.',
      'The demo is being reset right now. The page may be unavailable for up to ten minutes; reload it afterwards.');
  } else {
    const sim = aterstallInfo.simulerad ? ` <small>(${esc(L('simulering', 'simulation'))})</small>` : '';
    el.innerHTML = tillstand === 'nu'
      ? `${esc(L('Nollställs om', 'Resets in'))} ${esc(aterstallMmss(kvar))}${sim}`      // röd och stor: minuter och sekunder
      : `<span class="lang">${esc(L('Nollställs', 'Resets'))} ${esc(kl)} · </span>${esc(L('om', 'in'))} ${esc(aterstallRest(min))}${sim}`;
    el.setAttribute('title', L(`Demon nollställs varje natt klockan ${kl} (din tid). Allt data raderas och du börjar om från steg 1.`,
      `The demo is reset every night at ${kl} (your time). All data is deleted and you start over from step 1.`));
    remsa.hidden = tillstand !== 'nu';
    const resten = kvar < 60000 ? L('mindre än en minut', 'less than a minute') : aterstallRest(min);   // 0:28 i raden ska inte stå som "1 min" i bannern
    if (tillstand === 'nu') $('#aterstallremsatext').textContent = L(`Demon nollställs om ${resten}. Pågående körningar avbryts och allt data raderas; efteråt börjar du om från steg 1.`,
      `The demo is reset in ${resten}. Runs in progress are cancelled and all data is deleted; afterwards you start over from step 1.`);
  }
  /* En skärmläsare får besked bara när tillståndet ändras, inte varje minut. */
  if (tillstand !== aterstallTillstand) {
    if (tillstand === 'snart' || tillstand === 'nu' || tillstand === 'pagar') sr.textContent = remsa.hidden ? el.textContent : $('#aterstallremsatext').textContent;
    else sr.textContent = '';
    aterstallTillstand = tillstand;
  }
  if (kvar <= -aterstallInfo.varaktighetMin * 60000 && !aterstallInfo.simulerad) hamtaAterstall();    // återställningen är klar: hämta nästa tidpunkt
}
hamtaAterstall();
setInterval(uppdateraAterstall, 1000);
setInterval(tickaSkydd, 1000);
setInterval(hamtaSkydd, 3000);
hamtaSkydd();
setInterval(hamtaAterstall, 600000);

/* ---- KoV-beslutet i steg 3 (K4) ---- */
async function laddaKovRuta() {
  const ruta = $('#kovruta');
  if (!ruta) return;
  const status = $('#kovstatus', ruta), avtalRad = $('#kovavtalrad', ruta);
  const [kon, reg] = await Promise.all([api('/api/kov'), api('/api/avtal')]);
  if (!kon.ok) {
    status.textContent = fmt(TX.kovFel, {fel: kon.data.fel || ''});
    ruta.dataset.id = '';
  } else {
    const vantande = kon.data.forhandlingar.filter(f => f.kovBeslut === 'VANTANDE');
    aktuellaVantande = new Set(vantande.map(f => f.id));
    $('#kovprick', ruta).classList.toggle('ingen', !vantande.length);
    if (!vantande.length) {
      status.textContent = TX.kovInget;
      ruta.dataset.id = '';
    } else {
      const senaste = vantande[vantande.length - 1];
      ruta.dataset.id = senaste.id;
      status.textContent = fmt(vantande.length === 1 ? TX.kovVantar : TX.kovVantarN,
        {n: vantande.length, id: String(senaste.id).slice(0, 8) + '…'});
    }
  }
  /* Gällande avtal om A, hämtade ur stadens avtalsregister (status synkas från DHI). */
  const gallande = reg.ok
    ? reg.data.avtal.filter(a => a.distribution === 'A' && a.status === 'GALLANDE' && a.dhiAvtalId) : [];
  if (!gallande.length) {
    avtalRad.textContent = reg.ok ? TX.kovIngetAvtal + (ruta.dataset.id ? '' : TX.kovIngetStart)
      : fmt(TX.avtalFel, {fel: reg.data.fel || ''});
    ruta.dataset.avtal = '';
  } else {
    const senaste = gallande[0];
    ruta.dataset.avtal = senaste.dhiAvtalId;
    avtalRad.textContent = fmt(gallande.length === 1 ? TX.kovAvtal : TX.kovAvtalN,
      {n: gallande.length, id: String(senaste.id).slice(0, 8) + '…'});
  }
  kovKnappar();
}

/* Beslutet går till providern (POST /api/kov/{id}/{beslut}) och loggas inline. */
async function kovBeslutInline(beslut, plats) {
  const ruta = $('#kovruta');
  const hav = beslut === 'hav';
  const id = ruta && (hav ? ruta.dataset.avtal : ruta.dataset.id);
  if (!id) return;
  handelse('atgard_kov-' + beslut);
  /* Knapparna låses direkt, inte först när nästa statusrunda hinner ikapp. */
  jobbAktivtNu = true; lasTill = Date.now() + 3000; sattPagar('kov-' + beslut); kovKnappar();    /* lasTill: en statusrunda före serverns jobb får inte låsa upp knapparna */
  const {ok, status, data} = await api(
    hav ? `/api/kov/avtal/${encodeURIComponent(id)}/hav` : `/api/kov/${encodeURIComponent(id)}/${encodeURIComponent(beslut)}`, 'POST');
  if (!ok) {
    if (status === 429) hamtaSkydd();
    plats.innerHTML = `<p class="felrad">${esc(fmt(TX.jobbFelStart, {fel: data.fel || ('HTTP ' + status)}))}</p>`;
    jobbAktivtNu = false; lasTill = 0; sattPagar(null); kovKnappar();
    return;
  }
  laddaStatus();
  rensaLoggplatser(plats);            // F3: den gamla Förhandla A-rutan ska inte stå kvar med "väntar på KoV" efter beslutet
  valtJobb = data.id;                 // fliken Jobb öppnas på det senaste jobbet, även för ett KoV-beslut i kedjevyn
  foljJobb(data.id, plats);
}

/* ---- steg 6: inspektionsprioritering (B öppet, A kräver ett gällande avtal) ---- */
let analysAnrop = 0;
const tal = v => (v === null || v === undefined) ? '–' : Number(v).toLocaleString(SPRAK === 'en' ? 'en-GB' : 'sv-SE', {maximumFractionDigits: 3});
function analysKarta(rader) {
  const med = rader.filter(r => r.position && r.position.length === 2);
  if (!med.length) return '';
  const nar = mobil.matches;
  const B = nar ? 272 : 560, H = nar ? 300 : 340, M = nar ? 46 : 50;     // smal skärm: egen storlek, så att texten inte krymper med bilden
  const fa = nar ? 12 : 11, fl = nar ? 13 : 12;                           // typstorlek: axeltal och etiketter
  const lon = med.map(r => r.position[0]), lat = med.map(r => r.position[1]);
  let x0 = Math.min(...lon), x1 = Math.max(...lon), y0 = Math.min(...lat), y1 = Math.max(...lat);
  /* Samma skala på båda axlarna (meter), så att avstånd ser rätt ut: lägg på luft kring punkterna. */
  const mLat = 111320, mLon = 111320 * Math.cos(((y0 + y1) / 2) * Math.PI / 180);
  const bredd = Math.max((x1 - x0) * mLon, 50), hojd = Math.max((y1 - y0) * mLat, 50);
  const skala = Math.min((B - 2 * M) / bredd, (H - 2 * M) / hojd);          // pixlar per meter
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const X = v => B / 2 + (v - cx) * mLon * skala;
  const Y = v => H / 2 - (v - cy) * mLat * skala;
  /* Rutnät med koordinater och en skalstock: en schematisk kartbakgrund utan externa kartor. */
  const rutor = nar ? 2 : 4;          // färre axeltal på smal skärm, så att de inte flyter ihop
  let nat = '';
  for (let i = 0; i <= rutor; i++) {
    const gx = M + i * (B - 2 * M) / rutor, gy = M + i * (H - 2 * M) / rutor;
    const lo = cx + (gx - B / 2) / (mLon * skala), la = cy - (gy - H / 2) / (mLat * skala);
    nat += `<line x1="${gx.toFixed(1)}" y1="${M}" x2="${gx.toFixed(1)}" y2="${H - M}" stroke="#d3dbd6" stroke-width="1"/>`
         + `<line x1="${M}" y1="${gy.toFixed(1)}" x2="${B - M}" y2="${gy.toFixed(1)}" stroke="#d3dbd6" stroke-width="1"/>`
         + `<text x="${gx.toFixed(1)}" y="${H - M + 19}" font-size="${fa}" text-anchor="middle" fill="#3b4440">${lo.toFixed(3)}</text>`
         + `<text x="${M - 4}" y="${(gy + 3).toFixed(1)}" font-size="${fa}" text-anchor="end" fill="#3b4440">${la.toFixed(3)}</text>`;
  }
  const bra = [10, 20, 50, 100, 200, 500, 1000];
  const stock = bra.find(m => m * skala >= 50) || 1000;
  const sx = B - M - stock * skala, sy = H - 8;
  nat += `<line x1="${sx.toFixed(1)}" y1="${sy}" x2="${(sx + stock * skala).toFixed(1)}" y2="${sy}" stroke="#1d1d1d" stroke-width="3"/>`
       + `<text x="${(sx + stock * skala / 2).toFixed(1)}" y="${sy - 5}" font-size="${fa}" text-anchor="middle" fill="#1d1d1d">${stock} m</text>`
       + `<text x="${B - 12}" y="${M - 12}" font-size="${fa}" text-anchor="end" fill="#1d1d1d">N ↑</text>`;
  let prickar = '', etiketter = '';
  const lagda = [];     // redan placerade etiketter: en ny etikett som krockar flyttas upp eller ned, men aldrig utanför ytan
  const yMin = fl + 2, yMax = H - M - 4;
  med.slice().reverse().forEach(r => {
    const x = X(r.position[0]).toFixed(1), y = Y(r.position[1]).toFixed(1);
    if (r.inspektera) {
      prickar += `<circle cx="${x}" cy="${y}" r="6" fill="#99201a" stroke="#fff" stroke-width="1.5"><title>${esc(r.id)}: ${tal(r.volymM3)} m³</title></circle>`;
      if (r.rang <= 5) {
        const bredd = String(r.id).length * fl * 0.66;
        let ex = +x + 9;
        if (ex + bredd > B - 2) ex = +x - 9 - bredd;       // ryms inte till höger: lägg etiketten till vänster om pricken
        ex = Math.max(2, ex);
        const krockar = yy => lagda.some(l => Math.abs(l.y - yy) < 16 && ex < l.x + l.b && l.x < ex + bredd);
        let ey = null;
        for (let k = 0; k < 14 && ey === null; k++) {      // närmast pricken först: 0, +1, -1, +2, -2 … steg om 16
          for (const d of (k === 0 ? [0] : [k, -k])) {
            const c = +y + 4 + 16 * d;
            if (c >= yMin && c <= yMax && !krockar(c)) { ey = c; break; }
          }
        }
        if (ey !== null) {                                   // finns ingen plats inom kartan utelämnas etiketten (pricken finns kvar)
          lagda.push({x: ex, y: ey, b: bredd});
          etiketter += `<text x="${ex.toFixed(1)}" y="${ey.toFixed(1)}" font-size="${fl}" fill="#1d1d1d" paint-order="stroke" stroke="#f3f6f4" stroke-width="3">${esc(r.id)}</text>`;
        }
      }
    } else {
      prickar += `<circle cx="${x}" cy="${y}" r="3" fill="#47504c"><title>${esc(r.id)}: ${tal(r.volymM3)} m³</title></circle>`;
    }
  });
  const beskr = L(`Schematisk karta över ${med.length} brunnar. Röda prickar är de som bör inspekteras; de största har namn.`, `Schematic map of ${med.length} chambers. Red dots are the ones to inspect; the largest are named.`);
  return `<div class="kartrum"><svg class="karta" viewBox="0 0 ${B} ${H}" width="${B}" height="${H}" role="img" aria-label="${esc(beskr)}">
      <title>${esc(beskr)}</title><rect x="0" y="0" width="${B}" height="${H}" fill="#f3f6f4" stroke="#c9d2cd"/>${nat}${prickar}${etiketter}</svg>
      <div id="osmkarta" class="osmkarta" hidden></div>
      <p class="meta" id="kartnot">${L('Schematisk kartvy med rutnät, koordinater och skalstock (kartbakgrunden från OpenStreetMap hämtas av din webbläsare och visas när den är klar). Positionerna ur den skyddade distributionen A är påhittade (de ligger på Liseberg). Röd prick: pekas ut för inspektion; namn visas för de fem första.', 'Schematic map view with a grid, coordinates and a scale bar (the OpenStreetMap background is fetched by your browser and shown when it is ready). The positions from the protected distribution A are made up (they lie on Liseberg). Red dot: pointed out for inspection; names are shown for the first five.')}</p></div>`;
}

/* Kartbakgrund: Leaflet serveras av kontrollrummet självt (/statiskt/leaflet). Kartplattorna hämtas alltid från OpenStreetMap
   när brunnarna ur A visas (OpenStreetMap ser då besökarens IP-adress och ungefär vilket område som visas, inget annat);
   den schematiska SVG-kartan visas medan plattorna laddas och om de inte kan hämtas. */
let leafletLaddar = null, osmInstans = null, senasteKartrader = [];
function stadaKarta() {
  if (osmInstans) { try { osmInstans.remove(); } catch (e) { /* redan borta */ } osmInstans = null; }
}
function laddaLeaflet() {
  if (window.L && window.L.map) return Promise.resolve(true);
  if (leafletLaddar) return leafletLaddar;
  leafletLaddar = new Promise(klar => {
    try {
      const c = document.createElement('link');
      c.rel = 'stylesheet'; c.href = '/statiskt/leaflet/leaflet.css';
      document.head.appendChild(c);
      const j = document.createElement('script');
      j.src = '/statiskt/leaflet/leaflet.js';
      j.onload = () => klar(!!(window.L && window.L.map)); j.onerror = () => klar(false);
      document.head.appendChild(j);
      setTimeout(() => klar(false), 8000);
    } catch (e) { klar(false); }
  });
  return leafletLaddar;
}
let kartAnrop = 0;                 /* bara det senaste anropet till visaKartbakgrund får rita eller skriva i kartnoten */
async function visaKartbakgrund() {
  handelse('karta_osm');
  const rot = $('#osmkarta'), svg = $('svg.karta'), min = ++kartAnrop;
  if (!rot || !svg || !senasteKartrader.length) return;
  /* F1: kartan ritas aldrig utan att avtalet kontrollerats mot servern (stadens gateway nekar när det hävts), och positionerna
     tas ur det färska svaret, inte ur det som hämtades när sidan visades. Samma antal (topp) som analysen visar. */
  const [kontroll, lyckades] = await Promise.all([api(`/api/analys?lage=a&topp=${analysTopp()}`), laddaLeaflet()]);      // biblioteket laddas medan avtalet kontrolleras
  if (min !== kartAnrop || !document.body.contains(rot)) return;      // ett nyare anrop eller en ny rendering har tagit över
  if (!kontroll.ok || kontroll.data.blockerad) { laddaAnalys(true); return; }
  senasteKartrader = kontroll.data.rader || senasteKartrader;
  const med = senasteKartrader.filter(r => r.position && r.position.length === 2);
  if (!med.length) return;
  if (!lyckades) {
    const n = $('#kartnot'); if (n) n.textContent += ' ' + L('Kartbiblioteket kunde inte laddas.', 'The map library could not be loaded.');
    return;
  }
  stadaKarta();
  try {
    rot.hidden = false;
    rot.setAttribute('role', 'group');
    rot.setAttribute('aria-label', L(`Karta över ${med.length} brunnar (OpenStreetMap)`, `Map of ${med.length} chambers (OpenStreetMap)`));
    const karta = window.L.map(rot, {scrollWheelZoom: false, zoomAnimation: !lugnt(), fadeAnimation: !lugnt()});
    osmInstans = karta;
    let plattorOk = false;
    const lager = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});
    lager.on('tileload', () => {
      if (plattorOk) return;
      plattorOk = true; svg.style.display = 'none';
      const n = $('#kartnot'); if (n) n.textContent = L('Kartbakgrund: © OpenStreetMap-bidragsgivare. Positionerna ur den skyddade distributionen A är påhittade (de ligger på Liseberg). Röd prick: pekas ut för inspektion.', 'Map background: © OpenStreetMap contributors. The positions from the protected distribution A are made up (they lie on Liseberg). Red dot: pointed out for inspection.');
    });
    lager.addTo(karta);
    const punkter = [], etiketter = [];
    med.slice().reverse().forEach(r => {
      const ll = [r.position[1], r.position[0]]; punkter.push(ll);
      const m = window.L.circleMarker(ll, r.inspektera ? {radius: 8, color: '#fff', weight: 1.5, fillColor: '#99201a', fillOpacity: 1} : {radius: 4, color: '#47504c', weight: 1, fillColor: '#47504c', fillOpacity: .9}).addTo(karta);
            const text = esc(`${r.id}: ${tal(r.volymM3)} m³`), permanent = r.inspektera && r.rang <= 5;
      m.bindTooltip(text, permanent ? {permanent: true, direction: 'right', offset: [9, 0]} : {});
      if (permanent) etiketter.push({m, text, rang: r.rang});
    });
    karta.fitBounds(punkter, {padding: [30, 30], maxZoom: 17});
    /* F11: etiketterna för de fem främsta placeras så att de inte skriver över varandra: varje etikett prövar lägen runt sin
       punkt, i rangordning, tills den inte överlappar en redan placerad. Görs om efter varje zoom (avstånden ändras). */
    const KAND = [['right', [9, 0]], ['left', [-9, 0]], ['top', [0, -9]], ['bottom', [0, 9]], ['right', [9, 18]], ['right', [9, -18]],
                  ['left', [-9, 18]], ['left', [-9, -18]], ['right', [9, 36]], ['left', [-9, 36]], ['right', [9, -36]], ['left', [-9, -36]]];
    const sprid = () => {
      if (osmInstans !== karta) return;
      const taget = [];
      etiketter.slice().sort((x, y) => x.rang - y.rang).forEach(mk => {
        for (const [dir, off] of KAND) {
          mk.m.unbindTooltip(); mk.m.bindTooltip(mk.text, {permanent: true, direction: dir, offset: off}); mk.m.openTooltip();
          const el = mk.m.getTooltip() && mk.m.getTooltip().getElement();
          if (!el) return;
          const b = el.getBoundingClientRect();
          if (!taget.some(t => b.left < t.right && t.left < b.right && b.top < t.bottom && t.top < b.bottom)) { taget.push(b); return; }
        }
        mk.m.unbindTooltip(); mk.m.bindTooltip(mk.text);      // ingen ledig plats: etiketten visas i stället vid hovring
      });
    };
    setTimeout(sprid, 150);
    karta.on('zoomend', () => setTimeout(sprid, 50));
    /* Når inga plattor inom några sekunder: ta bort kartan och behåll den schematiska reserven. */
    setTimeout(() => { if (!plattorOk && osmInstans === karta) { stadaKarta(); rot.hidden = true; } }, 8000);
  } catch (e) { rot.hidden = true; }
}

/* ---- steg 3: samordnaren Svada stänger ute / släpper in en deltagare (återkallelse av medlemsintyg) ---- */
let svadaAnrop = 0;
async function laddaSvada() {
  const tab = $('#svadatabell');
  if (!tab) return;
  const mitt = ++svadaAnrop;
  const {ok, data} = await api('/api/svada/status');
  if (mitt !== svadaAnrop) return;          // ett nyare anrop har tagit över
  if (!ok) { tab.innerHTML = `<tr><td class="felrad">${esc(data.fel || '')}</td></tr>`; return; }
  const namn = {dhi: 'DHI', stad: L('Staden', 'The city')};
  const rader = (data.poster || []).filter(p => /Membership/.test(p.typ));
  tab.innerHTML = rader.map(p => `<tr><td>${esc(namn[p.mottagare] || p.mottagare)}</td>
      <td>${p.aterkallat ? '<b class="res-HAVT">' + L('UTESTÄNGD (intyget återkallat)', 'EXCLUDED (credential revoked)') + '</b><span class="skyddtid" data-utestang="' + esc(p.mottagare) + '"></span>' : L('medlem', 'member')}</td>
      <td><button type="button" class="kor" data-svada="${esc(p.mottagare)}" data-atgard="${p.aterkallat ? 'aterinsatt' : 'aterkalla'}" aria-label="${esc((p.aterkallat ? L('Släpp in igen', 'Let back in') : L('Stäng ute', 'Exclude')) + ': ' + (namn[p.mottagare] || p.mottagare))}">${p.aterkallat ? L('Släpp in igen', 'Let back in') : L('Stäng ute', 'Exclude')}</button></td></tr>`).join('');
  hamtaSkydd();
}
async function svadaAtgard(knapp) {
  /* Spärr under anropet: ett dubbelklick får inte landa på den nyritade knappen och ångra direkt. */
  $$('#svadatabell button').forEach(b => { b.disabled = true; });
  const {ok, data} = await api(`/api/svada/${knapp.dataset.svada}/${knapp.dataset.atgard}`, 'POST', {});
  const tabell = $('#svadatabell');
  if (tabell) tabell._sistaHtml = null;      // knapparna spärrades via egenskapen disabled: tabellen ska alltid ritas om
  const ut = $('#svadautfall');
  if (ut) ut.textContent = ok ? L('Klart. Prova katalogförfrågan om några sekunder (statuslistan läses om var tredje sekund).', 'Done. Try the catalogue request in a few seconds (the status list is re-read every third second).') : (data.fel || '');
  await laddaSvada();
}
async function svadaProv() {
  const ut = $('#svadautfall');
  if (ut) ut.textContent = L('provar …', 'trying …');
  const {ok, data} = await api('/api/svada/prov');
  if (!ut) return;
  if (ok && data.ok) {
    const dhiUte = !!$('#svadatabell button[data-svada="dhi"][data-atgard="aterinsatt"]');
    ut.innerHTML = '<b>' + L('Staden når DHI: katalogen hämtades.', 'The city reaches DHI: the catalogue was fetched.') + '</b>'
      + (dhiUte ? ' ' + L('DHI är utestängd, men det stoppar DHI:s egna meddelanden till staden, som att slutföra ett avtal, inte stadens katalogfråga. Prova Förhandla Distribution B nedan: den slutförs inte.',
                          'DHI is excluded, but that blocks DHI’s own messages to the city, such as completing an agreement, not the city’s catalogue request. Try Negotiate Distribution B below: it does not complete.') : '');
  } else if (ok && data.nekad) {             // serverns strukturerade besked (A2-06), inte en gissning ur feltexten
    ut.innerHTML = '<b class="res-HAVT">' + L('Staden nekas av DHI (401): ', 'The city is refused by DHI (401): ') + '</b>'
      + L('DHI godtar inte stadens medlemsintyg.', 'DHI does not accept the city’s membership credential.');
  } else {
    ut.innerHTML = '<b>' + L('Provet kunde inte göras: ', 'The check could not be made: ') + '</b>'
      + L('DHI svarade inte som väntat. Se Jobb och Auditlogg.', 'DHI did not answer as expected. See Jobs and Audit log.');
  }
}

/* Antalet brunnar som pekas ut: Number, inte parseInt (1e9 är ett stort tal; parseInt läste bara '1'). 0 och negativa blir 1,
   tomt eller ogiltigt blir 10, och högst 91. */
function analysTopp() {
  const rattVarde = ($('#analystopp') || {value: ''}).value.trim();
  const angivet = rattVarde === '' ? NaN : Math.floor(Number(rattVarde));
  return Math.max(1, Math.min(isNaN(angivet) ? 10 : angivet, 91));
}
async function laddaAnalys(automatisk) {
  const rot = $('#analysruta');
  if (!rot) return;
  const lage = ($('input[name="analyslage"]:checked', rot) || {}).value || 'b';
  const topp = analysTopp();
  $('#analystopp').value = topp;               // fältet visar det som faktiskt användes (0, -5 och 999 blev tidigare kvar i fältet)
  const mitt = ++analysAnrop;
  if (harRort && !automatisk) handelse('analys_' + lage);      // en automatisk omläsning är ingen handling från besökaren
  analysVisarA = false;
  laddaBrunnJamforelse();
  $('#analysstatus').textContent = L('hämtar …', 'fetching …');
  const {ok, data} = await api(`/api/analys?lage=${lage}&topp=${topp}`);
  if (mitt !== analysAnrop) return;          // ett nyare anrop har tagit över
  const ut = $('#analysresultat'), st = $('#analysstatus');
  stadaKarta();
  if (!ok) { st.innerHTML = `<span class="felrad">${esc(data.fel || '')}</span>`; ut.innerHTML = ''; return; }
  if (data.blockerad) {
    const b = data.blockerad;
    const orsak = {
      'inget-gallande-avtal': L('Det finns inget gällande avtal om A. Förhandla A och låt KoV godkänna (steg 3).', 'There is no current agreement for A. Negotiate A and let KoV approve (step 3).'),
      'avtal-utgatt': L('Avtalets giltighetstid har gått ut. Ett avtal gäller i en bestämd tid eller tills det hävs: stadens gateway ger ingen nyckel och DHI lämnar inte ut mer. Förhandla A på nytt.', 'The agreement\'s validity period has ended. An agreement is valid for a set time or until it is revoked: the city\'s gateway issues no key and DHI releases no more. Negotiate A again.'),
      'avtal-havt': L('Avtalet om A har hävts av KoV. Ett avtal gäller tills det hävs, och det gäller inte längre: stadens gateway ger ingen nyckel och DHI lämnar inte ut mer.', 'The agreement for A has been revoked by KoV. An agreement is valid until it is revoked, and this one no longer is: the city\'s gateway issues no key and DHI releases no more.'),
      'nekad-av-gatewayen': L('Stadens gateway nekade åtkomsten till A: avtalet gäller inte längre.', 'The city\'s gateway refused access to A: the agreement is no longer valid.')
    }[b.orsak] || b.orsak;
    const orsakText = {AVSLAG: L('avslag på en ny begäran', 'rejection of a new request'), EXPLICIT: L('KoV hävde direkt', 'KoV revoked directly')};
    const hav = b.havning ? ` (${esc(orsakText[b.havning.orsak] || b.havning.orsak)}, ${esc(b.havning.tid ? new Date(String(b.havning.tid).slice(0, 19) + 'Z').toLocaleString(SPRAK === 'en' ? 'en-GB' : 'sv-SE', {year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'}) : '')})` : '';
    st.textContent = '';
    if (b.orsak === 'no-delivery') {
      const dA = b.distribution === 'A';
      ut.innerHTML = `<div class="ruta" role="status"><h4>${dA ? L('Distribution A har inte levererats ännu', 'Distribution A has not been delivered yet') : L('Ingen öppen data har levererats ännu', 'No open data has been delivered yet')}</h4>
        <p>${dA ? L('Avtalet gäller, men inga värden har kommit in under det. Leverera distribution A (<a href="#steg-4" data-hopp="4">steg 4</a>), så rangordnas brunnarna här, med position.', 'The agreement is valid, but no values have arrived under it. Deliver distribution A (<a href="#steg-4" data-hopp="4">step 4</a>), and the chambers are ranked here, with position.')
                : L('Staden känner brunnarna men har inte fått några modellresultat. Kör en batch (<a href="#steg-1" data-hopp="1">steg 1</a>) och leverera distribution B (<a href="#steg-4" data-hopp="4">steg 4</a>), så rangordnas brunnarna här.', 'The city knows the chambers but has received no model results yet. Run a batch (<a href="#steg-1" data-hopp="1">step 1</a>) and deliver distribution B (<a href="#steg-4" data-hopp="4">step 4</a>), and the chambers are ranked here.')}</p></div>`;
      return;
    }
    if (b.orsak === 'inget-gallande-avtal') {
      ut.innerHTML = `<div class="ruta" role="status"><h4>${L('Distribution A kräver ett gällande avtal', 'Distribution A requires a current agreement')}</h4>
        <p>${esc(orsak)}</p>
        <p>${L('Vill du se analysen nu? Distribution B är öppen: välj <b>B</b> ovan.', 'Want to see the analysis now? Distribution B is open: choose <b>B</b> above.')}</p></div>`;
      return;
    }
    ut.innerHTML = `<div class="ruta larm" role="alert"><h4>${L('Distribution A kan inte läsas just nu', 'Distribution A cannot be read right now')}</h4>
      <p>${esc(orsak)}${hav}</p>
      ${b.avtal ? `<p><a href="/avtal/${esc(b.avtal)}?lang=${SPRAK}">${L('Visa avtalet', 'Show the agreement')}</a></p>` : ''}
      <p>${L('Distribution B är öppen och fungerar fortfarande: välj B ovan.', 'Distribution B is open and still works: choose B above.')}</p></div>`;
    return;
  }
  const u = data.ursprung || {}, s = data.sammanfattning || {};
  const avtalId = (data.avtal && data.avtal.id) || u.avtal;
  st.innerHTML = `${L('Bygger på', 'Based on')}: ${L('distribution', 'distribution')} <b>${esc(u.distribution || data.lage)}</b> (${esc(u.klass || '–')}), batch <code>${esc(u.batch || '–')}</code>, ${L('avtal', 'agreement')} ${avtalId ? `<a href="/avtal/${esc(avtalId)}?lang=${SPRAK}"><code>${esc(String(avtalId).slice(0, 8))}…</code></a>` : '–'} · ${L('demon räknar fram en ny batch var tionde minut, så siffrorna ändras', 'the demo computes a new batch every ten minutes, so the figures change')}`;
  const antalTopp = Math.max(1, data.topp || 10);
  const visa = data.rader.slice(0, antalTopp);
  const rad = r => `<tr class="${r.inspektera ? 'inspektera' : ''}"><td>${r.rang}</td><td><code>${esc(r.id)}</code>${r.namn ? ' ' + esc(r.namn) : ''}</td>
      <td>${tal(r.volymM3)}</td><td>${tal(r.toppM3S)}</td><td>${esc(r.recipient || '–')}</td>
      ${data.lage === 'A' ? `<td>${r.position ? r.position.slice().reverse().map(v => (+v).toFixed(4)).join(', ') : '–'}</td>` : ''}
      <td>${r.inspektera ? '<b>' + L('Inspektera', 'Inspect') + '</b>' : ''}</td></tr>`;
  const huvud = `<tr><th>${L('Rang', 'Rank')}</th><th>${L('Brunn', 'Chamber')}</th><th>${L('Bräddvolym (m³)', 'Overflow volume (m³)')}</th><th>${L('Toppflöde (m³/s)', 'Peak flow (m³/s)')}</th><th>${L('Mottagare', 'Recipient')}</th>${data.lage === 'A' ? `<th>${L('Position (bredd, längd)', 'Position (lat, lon)')}</th>` : ''}<th></th></tr>`;
  ut.innerHTML = `
    <div class="nyckeltal">
      <div><span>${L('Brunnar', 'Chambers')}</span><b>${s.brunnar}</b></div>
      <div><span>${L('Brunnar som bräddar', 'Chambers overflowing')}</span><b>${s.braddar}</b></div>
      <div><span>${L('Total bräddvolym (m³)', 'Total overflow (m³)')}</span><b>${tal(s.totalVolymM3)}</b></div>
      <div><span>${L('Högsta (m³)', 'Highest (m³)')}</span><b>${tal(s.hogstaVolymM3)}</b></div>
    </div>
    ${s.samtligaTidLika ? `<p class="meta">${L('Bräddtiden är lika för alla brunnar som bräddar i modellen, så den används inte för att rangordna.', 'The overflow time is the same for all chambers that overflow in the model, so it is not used for ranking.')}</p>` : ''}
    ${data.lage === 'A' ? analysKarta(data.rader) : ''}
    <h4>${L(`De ${data.topp} brunnarna att inspektera först`, `The ${data.topp} chambers to inspect first`)}</h4>
    <div class="tabellrum"><table class="analystabell">${huvud}${visa.map(rad).join('')}</table></div>
    ${data.rader.length > antalTopp ? `<details><summary>${L('Visa alla', 'Show all')} ${data.rader.length}</summary><div class="tabellrum"><table class="analystabell">${huvud}${data.rader.slice(antalTopp).map(rad).join('')}</table></div></details>` : ''}
    <h4>${L('Mottagande vattendrag', 'Receiving watercourses')}</h4>
    <div class="tabellrum"><table class="analystabell"><tr><th>${L('Mottagare', 'Recipient')}</th><th>${L('Brunnar', 'Chambers')}</th><th>${L('Total bräddvolym (m³)', 'Total overflow (m³)')}</th></tr>
      ${data.perRecipient.map(p => `<tr><td>${esc(p.recipient)}</td><td>${p.brunnar}</td><td>${tal(p.volymM3)}</td></tr>`).join('')}</table></div>
    <p class="meta">${data.lage === 'B'
      ? L('Med öppna data (B) går det att rangordna brunnarna och se vilka vattendrag som tar emot mest, men inte att lägga brunnarna på en karta: positionerna ingår inte i B.', 'With open data (B) the chambers can be ranked and the watercourses that receive most can be seen, but the chambers cannot be put on a map: positions are not part of B.')
      : L('Med skyddade data (A) kan brunnarna läggas på en karta. Det kräver ett gällande avtal: hävs det slutar den här delen att fungera.', 'With protected data (A) the chambers can be put on a map. That requires a current agreement: if it is revoked this part stops working.')}</p>`;
  stadaKarta();
  senasteKartrader = data.lage === 'A' ? data.rader : [];
  analysVisarA = data.lage === 'A';
  /* Kartbakgrunden från OpenStreetMap visas alltid när brunnarna ur A visas (förr en knapp). Avtalet
     kontrolleras mot servern först (visaKartbakgrund), så en hävning ger ingen karta. */
  if (analysVisarA && senasteKartrader.length) setTimeout(() => visaKartbakgrund(), 0);
}

/* Samma brunn i B och A sida vid sida (webinariet 2026-10, punkt 3). B först (K20). A visas bara med ett gällande
   avtal; annars samma orsak som analysen ger. Servern avgör åtkomsten (/api/analys/brunn), inte sidan. */
let jamforAnrop = 0;
async function laddaBrunnJamforelse() {
  const rot = $('#brunnjamforkol');
  if (!rot) return;
  const mitt = ++jamforAnrop;
  const {ok, data} = await api('/api/analys/brunn');
  if (mitt !== jamforAnrop) return;
  if (!ok) { jamforVisarA = false; rot.innerHTML = `<p class="felrad">${esc(data.fel || '')}</p>`; return; }
  jamforVisarA = !!(data.A && data.A.rad && data.A.rad.position);
  const orsaker = {
    'inget-gallande-avtal': L('Nekad: det finns inget gällande avtal om A.', 'Refused: there is no current agreement for A.'),
    'avtal-havt': L('Nekad: avtalet om A har hävts av KoV.', 'Refused: the agreement for A has been revoked by KoV.'),
    'avtal-utgatt': L('Nekad: avtalet om A har gått ut.', 'Refused: the agreement for A has expired.'),
    'nekad-av-gatewayen': L('Nekad av stadens gateway: avtalet gäller inte längre.', 'Refused by the city’s gateway: the agreement is no longer valid.'),
    'no-delivery': L('Inget levererat ännu i den här distributionen.', 'Nothing delivered yet in this distribution.')
  };
  const sida = (k, rubrik) => {
    const s = data[k] || {}, r = s.rad;
    let inne;
    if (!r) {
      const b = s.blockerad;
      inne = `<p role="status">${esc(b ? (orsaker[b.orsak] || b.orsak) : L('Brunnen finns inte i den här distributionen.', 'The chamber is not in this distribution.'))}</p>`;
    } else {
      const pos = k === 'A'
        ? (r.position ? r.position.slice().reverse().map(v => (+v).toFixed(4)).join(', ') : '–')
        : L('ingår inte i B', 'not part of B');
      const rader = [
        [L('Brunn', 'Chamber'), `<code>${esc(r.id)}</code>${r.namn ? ' ' + esc(r.namn) : ''}`],
        [L('Bräddvolym (m³)', 'Overflow volume (m³)'), tal(r.volymM3)],
        [L('Toppflöde (m³/s)', 'Peak flow (m³/s)'), tal(r.toppM3S)],
        [L('Mottagare', 'Recipient'), esc(r.recipient || '–')],
        [L('Position (bredd, längd)', 'Position (lat, lon)'), k === 'A' ? `<b>${pos}</b>` : `<i>${pos}</i>`],
        [L('Distribution och klass', 'Distribution and class'), `${esc(r.distribution || k)} (${esc(r.klass || '–')})`],
        [L('Avtal', 'Agreement'), r.avtal ? `<a href="/avtal/${esc(r.avtal)}?lang=${SPRAK}"><code>${esc(String(r.avtal).slice(0, 8))}…</code></a>` : '–'],
        ['Batch', `<code>${esc(r.batch || '–')}</code>`]];
      inne = `<table>${rader.map(([a, b]) => `<tr><th scope="row">${a}</th><td>${b}</td></tr>`).join('')}</table>`;
    }
    return `<div class="sida ${k.toLowerCase()}" data-jamfor="${k}"><h4>${rubrik}</h4>${inne}</div>`;
  };
  rot.innerHTML = sida('B', L('B – den öppna distributionen', 'B – the open distribution'))
                + sida('A', L('A – den skyddade distributionen', 'A – the protected distribution'));
}

/* ---- ODRL-villkoren i steg 2 (K17), live ur DSP-katalogen ---- */
let odrlHamtad = 0;
async function laddaOdrlVillkor() {
  const rot = $('#odrlkolumner');
  if (!rot || Date.now() - odrlHamtad < 60000) return;
  const {ok, data} = await api('/api/odrl-villkor?lang=' + SPRAK);
  const not = $('#odrlstatus');
  if (!ok || !data.B || !data.A) { if (not) not.textContent = TX.odrlStatisk; return; }
  odrlHamtad = Date.now();
  ['B', 'A'].forEach(k => {
    const kol = $(`[data-odrl="${k}"]`, rot);
    if (!kol) return;
    $('ul', kol).innerHTML = data[k].regler.map(r =>
      `<li title="${esc(r[0])}: ${esc(r[1])}"><code>${esc(r[0])}</code><span>${esc(r[1])}</span></li>`).join('');
    $('pre', kol).textContent = JSON.stringify(data[k].json, null, 2);
  });
  if (not) not.textContent = TX.odrlLive;
}

/* ---- ursprungsmärkningen i steg 5 (K22): ett riktigt värde ur CIP:en ---- */
async function laddaProv() {
  const pre = $('#provvarde'), avtal = $('#provavtal');
  if (!pre || !avtal) return;
  /* Bara om senaste leveransen är distribution B: värdet OCH avtalet som dess
     id pekar på, slaget upp live. Annars ligger de statiska, samstämmiga
     exemplen kvar (aldrig ett värde ur distribution A). */
  const {ok, data} = await api('/api/steg/5/ursprung?lang=' + SPRAK);
  if (!ok || !data.varde || !data.avtal) return;
  pre.innerHTML = lankaAvtal(esc(data.varde));
  avtal.innerHTML = lankaAvtal(esc(data.avtal));
  const not = $('#provstatus');
  if (not) not.textContent = TX.provLive;
}

/* ---- begrepp: tipsrutor vid hover, fokus och tryck (K9) ---- */
const ORDRE = ORD.map(o => ({id: o.id,
  re: new RegExp('(?<![\\p{L}\\p{N}])(?:' + o.re + ')', 'u' + (o.cs ? '' : 'i'))}));

/* Märker första förekomsten av varje begrepp inom en behållare. */
function markeraBegrepp(rot) {
  if (!rot) return;
  const anvanda = new Set();
  const hoppa = el => el.closest('button, pre, code, .tag, h1, h2, h3, h4, dt, .term, .lstatus, .tstatus, .tnamn, .rollchip, svg, .kat, .org, .stegnr, table, a, summary, .nod, script, style');
  const gang = document.createTreeWalker(rot, NodeFilter.SHOW_TEXT, {
    acceptNode: n => (!n.nodeValue.trim() || hoppa(n.parentElement))
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  const noder = [];
  while (gang.nextNode()) noder.push(gang.currentNode);
  noder.forEach(nod => {
    const delar = []; let rest = nod.nodeValue, hittat = false;
    for (;;) {
      let basta = null;
      ORDRE.forEach(r => {
        if (anvanda.has(r.id)) return;
        const m = r.re.exec(rest);
        if (m && (basta === null || m.index < basta.index)) basta = {index: m.index, len: m[0].length, id: r.id};
      });
      if (!basta) break;
      hittat = true; anvanda.add(basta.id);
      delar.push(document.createTextNode(rest.slice(0, basta.index)));
      const t = document.createElement('span');
      t.className = 'term'; t.tabIndex = 0; t.dataset.term = basta.id;
      t.setAttribute('role', 'button'); t.setAttribute('aria-describedby', 'tips');
      t.textContent = rest.substr(basta.index, basta.len);
      delar.push(t);
      rest = rest.slice(basta.index + basta.len);
    }
    if (!hittat) return;
    delar.push(document.createTextNode(rest));
    const f = document.createDocumentFragment();
    delar.forEach(d => f.appendChild(d));
    nod.parentNode.replaceChild(f, nod);
  });
}

/* Första förekomsten per block, så att varje kort och ruta förklarar sina egna ord. */
function markeraAllt() {
  $$('.intro, #om .omkol, #om .omdata, .pgrid, .sinnehall p, .odrlintro, .forklaring, .knappkort, .kovruta, .svadaruta, .teknikruta, .anteckning, .ingaknappar, .provruta')
    .forEach(markeraBegrepp);
}

const tips = document.createElement('div');
tips.id = 'tips'; tips.setAttribute('role', 'tooltip'); tips.hidden = true;
let tipsTimer = null, tipsFor = null;
function visaTips(el) {
  clearTimeout(tipsTimer);
  const o = ORD.find(x => x.id === el.dataset.term);
  if (!o) return;
  tips.innerHTML = `<b>${esc(o.term)}</b><span>${esc(o.def)}</span>`
    + `<a href="#ordlista-${esc(o.id)}">${esc(TX.helaListan)}</a>`;
  tips.hidden = false; tipsFor = el;
  const r = el.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 32);
  tips.style.width = w + 'px';
  let x = r.left + window.scrollX;
  x = Math.max(16 + window.scrollX, Math.min(x, window.scrollX + window.innerWidth - w - 16));
  tips.style.left = x + 'px';
  const h = tips.offsetHeight, ovan = r.top > h + 12;
  tips.style.top = (ovan ? r.top + window.scrollY - h - 8 : r.bottom + window.scrollY + 8) + 'px';
}
function doljTips(nu) {
  clearTimeout(tipsTimer);
  tipsTimer = setTimeout(() => { tips.hidden = true; tipsFor = null; }, nu ? 0 : 200);
}

/* En ordförklaring ska aldrig bli hängande: tryck någon annanstans, eller scrolla, stänger den. */
document.addEventListener('pointerdown', e => { if (!tips.hidden && !e.target.closest('#tips, .term')) doljTips(true); });
window.addEventListener('scroll', () => { if (!tips.hidden) doljTips(true); }, {passive: true});

/* ---- språk (K2): servern renderar valt språk, kakan svada-sprak minns det ---- */
function sattSprakKaka(sp) {
  document.cookie = 'svada-sprak=' + sp + '; path=/; max-age=31536000; SameSite=Lax';
}
function bytSprak(nytt) {
  if (nytt === SPRAK) return;
  handelse('sprak_' + nytt);
  /* F6: det jobb som följdes senast överlever språkbytet (sidan laddas om): id och ruta sparas och tas upp igen, om jobbet pågår
     eller blev klart för under en halv minut sedan. */
  try {
    const f = senastFoljd, kort = f && f.plats.dataset.jid === String(f.jid) && f.plats.closest('.knappkort, .kovval');
    if (kort && kort.id && (!f.slut || Date.now() - f.slut < 30000)) sessionStorage.setItem('svada-jobb-kvar', JSON.stringify({jid: f.jid, kort: kort.id, nr: valt, t: Date.now()}));
  } catch (e) {}
  try { localStorage.setItem('svada-sprak', nytt); } catch (e) {}
  sattSprakKaka(nytt);
  const u = new URL(location.href);
  u.searchParams.set('lang', nytt);          // en delad länk bär språket
  history.replaceState(null, '', u.pathname + u.search + u.hash);
  location.reload();
}
/* Returnerar true om sidan laddas om för att matcha det sparade språket. */
function synkaSprak() {
  const uttryckligt = new URLSearchParams(location.search).get('lang');
  try {
    if (uttryckligt) { localStorage.setItem('svada-sprak', SPRAK); return false; }
    const sparat = localStorage.getItem('svada-sprak');
    if ((sparat === 'sv' || sparat === 'en') && sparat !== SPRAK
        && sessionStorage.getItem('svada-omladdad') !== sparat) {
      sessionStorage.setItem('svada-omladdad', sparat);
      sattSprakKaka(sparat);
      location.reload();
      return true;
    }
  } catch (e) {}
  return false;
}

/* ------------------------------------------------------------------ start */
/* M2 (gränssnittstesterna 2026-10-17/18, F15): hävning och avslag kräver ett andra klick inom 15 s (besökartestet 2026-10-22: 8 s var för kort för den som läser texten, och gav ett eget fel i testet när sidan var upptagen). Första klicket ger knappen en
   KORT text ("Klicka igen för att häva") och förklaringen står under knappen (en statusruta som läses av skärmläsare); efter 15 s
   återställs allt. Godkänn kräver bara ett klick. */
const BEKRAFTA_MS = 15000;          // fönstret för det andra klicket
function aterstallBekrafta(knapp) {
  clearTimeout(knapp._bekraftaTimer);
  if (knapp.dataset.bekraftaOrig) knapp.textContent = knapp.dataset.bekraftaOrig;
  if (knapp._bekraftaInfo) { knapp._bekraftaInfo.remove(); knapp._bekraftaInfo = null; }
  delete knapp.dataset.bekraftaTill; delete knapp.dataset.bekraftaOrig; knapp.classList.remove('bekrafta');
}
function bekraftat(knapp, text) {
  if (knapp.dataset.bekraftaTill && Date.now() < +knapp.dataset.bekraftaTill) { aterstallBekrafta(knapp); return true; }
  aterstallBekrafta(knapp);           // ett utgånget men ännu inte återställt läge städas först (annars skrivs originaltexten över)
  const kort = text.split('. ')[0];
  knapp.dataset.bekraftaOrig = knapp.textContent;
  knapp.dataset.bekraftaTill = String(Date.now() + BEKRAFTA_MS);
  knapp.textContent = kort; knapp.classList.add('bekrafta');
  const info = document.createElement('span');
  info.className = 'bekrafta-info'; info.setAttribute('role', 'status'); info.textContent = text;
  if (knapp.parentElement) knapp.parentElement.appendChild(info);
  knapp._bekraftaInfo = info;
  knapp._bekraftaTimer = setTimeout(() => aterstallBekrafta(knapp), BEKRAFTA_MS);
  return false;
}
const BEKRAFTA_HAV = () => L('Klicka igen för att häva. Det går inte att ångra, men ett nytt avtal kan tecknas efteråt (ny förhandling och nytt KoV-beslut).',
                             'Click again to revoke. It cannot be undone, but a new agreement can be made afterwards (a new negotiation and a new KoV decision).');
const BEKRAFTA_AVSLA = () => L('Klicka igen för att avslå. Staden kan begära A på nytt efteråt.',
                               'Click again to reject. The city can request A again afterwards.');

/* Knappar och reglage vars data (id, läge) kommer från servern: id:t läses ur ett dataattribut och skrivs aldrig in i
   JavaScript-kod. HTML-escaping skyddar inte en JavaScript-sträng i ett onclick (del a2, A2-03): webbläsaren avkodar
   attributet innan koden tolkas, så ett id med en apostrof skulle kunna bryta sig ur strängen. */
document.addEventListener('click', e => {
  const kb = e.target.closest('button[data-kov-id]');
  if (kb) { if (kb.dataset.kovVal !== 'avsla' || bekraftat(kb, BEKRAFTA_AVSLA())) kovBeslut(kb.dataset.kovId, kb.dataset.kovVal); return; }
  const hb = e.target.closest('button[data-hav-id]');
  if (hb) { if (bekraftat(hb, BEKRAFTA_HAV())) kovHav(hb.dataset.havId); return; }
});
document.addEventListener('change', e => {
  const r = e.target.closest('input[data-fellage]');
  if (r) sattFel(r.dataset.fellage, r.checked);
});
document.addEventListener('click', e => {
  const t = e.target.closest('.term');
  if (t) { if (tipsFor === t && !tips.hidden) doljTips(true); else visaTips(t); return; }
  if (!e.target.closest('#tips')) doljTips(true);

  const nod = e.target.closest('.nod');
  if (nod) { oppna(nod.id === 'nod-kov' ? 3 : +nod.dataset.steg, true, nod.id === 'nod-kov'); return; }
  const hopp = e.target.closest('[data-hopp]');
  if (hopp) {
    oppna(+hopp.dataset.hopp, true, hopp.dataset.kov === '1');
    /* "Nästa" flyttar fokus till knappen som ska tryckas, så att den syns och går att aktivera med tangentbordet. */
    if (!hopp.dataset.fokus && hopp.id === 'nastaknapp') setTimeout(() => { const p = document.getElementById('steg-' + hopp.dataset.hopp); if (p) { p.tabIndex = -1; p.focus({preventScroll: true}); } }, 250);
    if (hopp.dataset.fokus) setTimeout(() => { const b = $(hopp.dataset.fokus); if (b && !ejAktiv(b)) { b.scrollIntoView({block: 'center', behavior: lugnt() ? 'auto' : 'smooth'}); b.focus({preventScroll: true}); } }, 250);
    return;
  }
  const hoppid = e.target.closest('[data-hoppid]');
  if (hoppid) { const m = document.getElementById(hoppid.dataset.hoppid); if (m) m.scrollIntoView({behavior: lugnt() ? 'auto' : 'smooth', block: 'start'}); return; }
  const stegknapp = e.target.closest('[data-steg]');
  if (stegknapp) { oppna(+stegknapp.dataset.steg, true); return; }
  if (e.target.closest('.stang')) { stang(); return; }
  const upp = e.target.closest('[data-upp]');
  if (upp) { $('.bildram').scrollIntoView({behavior: lugnt() ? 'auto' : 'smooth', block: 'start'}); return; }
  const sprak = e.target.closest('.sprak button');
  if (sprak) { bytSprak(sprak.dataset.lang); return; }
  const flik = e.target.closest('[data-flik]');
  if (flik) { e.preventDefault(); if (flik.dataset.flik === 'jobb') valtJobb = null; visa(flik.dataset.flik); return; }
  const gaFor = e.target.closest('[data-gaforhandla]');
  if (gaFor) {
    e.preventDefault(); knappTipsBort(); oppna(3, true);
    const fk = $('#steg-3 button.kor[data-atgard="forhandla-a"]'); if (fk) { fk.scrollIntoView({block: 'center'}); fk.focus(); }
    return;
  }
  if (!e.target.closest('.knapptips')) knappTipsBort();
  const sflik = e.target.closest('[data-sflik]');
  const sstep = e.target.closest('[data-sstep]');
  if (sstep) {
    const rot = sstep.closest('.sehur'), flikar = $$('[data-sflik]', rot);
    const nu = flikar.findIndex(x => x.getAttribute('aria-selected') === 'true');
    const mal = flikar[Math.max(0, Math.min(flikar.length - 1, nu + (+sstep.dataset.sstep)))];
    if (mal) mal.click();
    return;
  }
  if (sflik) {
    const rot = sflik.closest('.sehur');
    $$('[data-sflik]', rot).forEach(x => x.setAttribute('aria-selected', String(x === sflik)));
    $$('[data-sinn]', rot).forEach(x => { x.hidden = x.dataset.sinn !== sflik.dataset.sflik; });
    const alla = $$('[data-sflik]', rot), i = alla.indexOf(sflik);
    const rak = $('.sraknare', rot); if (rak) rak.textContent = `${i + 1} ${L('av', 'of')} ${alla.length}`;
    $$('[data-sstep]', rot).forEach(b => { b.disabled = (+b.dataset.sstep < 0 && i === 0) || (+b.dataset.sstep > 0 && i === alla.length - 1); });
    return;
  }
  /* Svadas knappar bär också klassen kor och data-atgard, så de måste fångas FÖRE åtgärdsknapparna. */
  const svada = e.target.closest('button[data-svada]');
  if (svada) { svadaAtgard(svada); return; }
  if (e.target.closest('#svadaprov')) { svadaProv(); return; }
  const atgard = e.target.closest('.panel button.kor[data-atgard]');
  if (atgard) {
    kor(atgard.dataset.atgard, {}, {inline: atgard.closest('.knappkort').querySelector('.loggplats')});
    return;
  }
  const beslut = e.target.closest('button[data-kovbeslut]');
  if (beslut && beslut.getAttribute('aria-disabled') === 'true') { visaKnappTips(beslut); return; }
  if (beslut) {
    const v = beslut.dataset.kovbeslut;
    if (v === 'hav' && !bekraftat(beslut, BEKRAFTA_HAV())) return;
    if (v === 'avsla' && !bekraftat(beslut, BEKRAFTA_AVSLA())) return;
    kovBeslutInline(v, beslut.closest('.kovval').querySelector('.loggplats')); return;
  }
  const lank = e.target.closest('a[href^="#"]');
  if (lank && lank.getAttribute('href').length > 1) { e.preventDefault(); visa(lank.getAttribute('href').slice(1)); }
});
document.addEventListener('mouseover', e => {
  const t = e.target.closest('.term');
  if (t) visaTips(t); else if (e.target.closest('#tips')) clearTimeout(tipsTimer);
});
document.addEventListener('mouseout', e => { if (e.target.closest('.term, #tips')) doljTips(); });
document.addEventListener('focusin', e => { const t = e.target.closest('.term'); if (t) visaTips(t); });
document.addEventListener('focusout', e => {
  if (e.target.closest('.term') && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('#tips'))) doljTips();
  if (e.target.closest('#tips') && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('#tips'))) doljTips();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !tips.hidden) {
    /* Står fokus i rutans länk flyttas det tillbaka till ordet innan rutan stängs (annars står fokus kvar på ett dolt element). */
    if (tipsFor && e.target.closest && e.target.closest('#tips')) tipsFor.focus({preventScroll: true});
    doljTips(true); e.stopPropagation(); return;
  }
  if (e.key === 'Tab' && !e.shiftKey && !tips.hidden && tipsFor && e.target === tipsFor) {
    const a = tips.querySelector('a');
    if (a) { e.preventDefault(); clearTimeout(tipsTimer); a.focus(); return; }
  }
  /* Rutan ligger sist i dokumentet men hör till ordet: Tab vidare från länken i rutan fortsätter efter ORDET (annars lämnade fokus sidan och
     nästa Tab började om i sidhuvudet; provrunda 2026-10-26), och Skift+Tab går tillbaka till ordet. */
  if (e.key === 'Tab' && !tips.hidden && tipsFor && e.target.closest && e.target.closest('#tips')) {
    clearTimeout(tipsTimer);
    const ord = tipsFor;
    if (e.shiftKey) { ord.focus(); if (document.activeElement === ord) e.preventDefault(); return; }      // dolt ord: låt webbläsaren sköta Skift+Tab
    ord.focus({preventScroll: true});     // webbläsarens egen Tab flyttar sedan till nästa fokuserbara efter ordet
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('term')) {
    e.preventDefault(); visaTips(e.target); return;
  }
  /* Pilarna flyttar mellan flikarna i "Se hur det ser ut" (tab-mönstret). */
  if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && !e.altKey && !e.ctrlKey && !e.metaKey
      && e.target.matches && e.target.matches('[role="tab"]')) {
    const flikar = $$('[role="tab"]', e.target.closest('[role="tablist"]'));
    const i = flikar.indexOf(e.target) + (e.key === 'ArrowRight' ? 1 : -1);
    if (flikar[i]) { flikar[i].click(); flikar[i].focus(); }
    e.preventDefault(); e.stopPropagation(); return;
  }
  if (valt === null || e.target.closest('input,textarea,select') || !$('section#kedjan.aktiv')) return;
  if (e.key === 'Escape') stang();
  /* Pilarna byter steg bara när fokus är på sidan i övrigt eller på bilden/stegraden,
     aldrig med modifierartangent (Alt+← är webbläsarens "bakåt") och inte inne i en panel. */
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  if (e.target !== document.body && !e.target.closest('.nod, .stegrad')) return;
  if (e.key === 'ArrowRight' && valt < 6) oppna(valt + 1, false);
  if (e.key === 'ArrowLeft' && valt > 1) oppna(valt - 1, false);
}, true);

window.addEventListener('DOMContentLoaded', () => {
  if (synkaSprak()) return;
  document.body.appendChild(tips);
  markeraAllt();
  /* Startvy: #steg-N, annars steget som var öppet senast, annars steg 6.
     Ett uttryckligt #kedjan ger bilden utan öppen panel. */
  let start = location.hash.slice(1);
  if (!start) {
    let sp = null;
    try { sp = localStorage.getItem('svada-steg'); } catch (e) {}
    start = sp === 'stangd' ? 'kedjan' : 'steg-' + (+sp >= 1 && +sp <= 6 ? +sp : 3);
  }
  visa(start);
  /* Webbläsaren har redan hoppat till fragmentet innan JS hann köra – rulla
     tillbaka så att sidhuvudet syns. */
  window.scrollTo(0, 0);
  /* Fragmentet (#steg-6 …) pekar på ett id, och webbläsaren kan hoppa dit
     först efter DOMContentLoaded. Rulla tillbaka även då. */
  let rort = false; const t0 = Date.now();
  ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(h =>
    window.addEventListener(h, () => { rort = true; }, {once: true, passive: true}));
  window.addEventListener('scroll', () => {
    if (!rort && Date.now() - t0 < 2000 && window.scrollY > 0) window.scrollTo(0, 0);
  });
  /* Någon skriver in en ny djuplänk (#steg-5, #jobb-3 …) i adressfältet. */
  window.addEventListener('hashchange', () => visa(location.hash.slice(1) || 'kedjan', 'replace'));
  /* Bakåt/Framåt mellan flikarna (pushState i visa): adressen är redan ändrad, så bara visa den. */
  window.addEventListener('popstate', () => visa(location.hash.slice(1) || 'kedjan', 'replace'));
  laddaStatus(); laddaDetaljer();
  /* F6: ett jobb som följdes när språket byttes tas upp igen i samma ruta (sparat av bytSprak, giltigt i två minuter). */
  try {
    const kvar = JSON.parse(sessionStorage.getItem('svada-jobb-kvar') || 'null');
    sessionStorage.removeItem('svada-jobb-kvar');
    if (kvar && Date.now() - kvar.t < 120000) {
      const kort = document.getElementById(kvar.kort), plats = kort && kort.querySelector('.loggplats');
      if (plats) { if (kvar.nr && kvar.nr !== valt) oppna(kvar.nr, false); foljJobb(+kvar.jid, plats); }
    }
  } catch (e) {}
  setInterval(laddaStatus, 5000);
  setInterval(laddaDetaljer, 15000);
  /* Utestängningstabellen läses om medan steg 3 är öppet (tidigare bara vid öppning och efter egna klick, så en
     utestängning som löpt ut stod kvar som UTESTÄNGD). data-stabil gör att knapparna inte byts ut i onödan. */
  /* En dold flik läses också om, men glesare (var 15:e s): i gränssnittstestet 2026-10-18 (M8) räknades testarens flik som
     dold hela tiden, och då stod en utgången utestängning kvar i över en minut. När fliken blir synlig läses den om direkt. */
  let svadaSenast = 0;
  setInterval(() => {
    const s = $('section.flik.aktiv');
    if (!(s && s.id === 'kedjan' && valt === 3)) return;
    if (document.hidden && Date.now() - svadaSenast < 15000) return;
    svadaSenast = Date.now(); laddaSvada();
  }, 3000);
  document.addEventListener('visibilitychange', () => {
    const s = $('section.flik.aktiv');
    if (!document.hidden && s && s.id === 'kedjan' && valt === 3) { svadaSenast = Date.now(); laddaSvada(); hamtaSkydd(); }
  });
  setInterval(() => {
    const s = $('section.flik.aktiv');
    if (!s) return;
    if (s.id === 'audit') laddaAudit();
    if (s.id === 'jobb') laddaJobb();
    if (s.id === 'suveranitet') laddaKov();
    if (s.id === 'kedjan' && valt === 3) laddaKovRuta();
  }, 8000);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(en => { bildSynlig = en[0].isIntersecting; uppdateraStegrad(); }, {threshold: 0})
      .observe($('.bildram'));
  }
  window.addEventListener('resize', ritaPilar);
  smal.addEventListener('change', () => { placera(); ritaPilar(); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(ritaPilar);
  ritaPilar();
});
"""
def _gamla_flikar(troskel, sprak="sv"):
    """Flikarna Följ, Audit, Suveränitet, Avvikelse, Felinjektion, FAIR och Jobb.
    Texten skrivs med S(svenska, engelska); data (loggar, värden) översätts inte."""
    def S(sv, en):
        return sv if sprak == "sv" else en
    pct = int(troskel * 100)
    return f"""
<section id="folj" class="flik">
  <div class="ruta">
    <h2>{S('Följ ett värde genom kedjan', 'Follow a value through the chain')}</h2>
    <p class="text">{S('Samma bräddbrunn led för led, med de <b>faktiska objekten</b>. Avtalets id, som binder ihop avtalet, leveranskvittot och ursprungsmärkningen i stadens dataplattform, är', 'The same overflow chamber stage by stage, with the <b>actual objects</b>. The agreement id, which ties together the agreement, the delivery receipt and the provenance in the city’s data platform, is')}
       <mark id="tradid">…</mark>. {S('Leta efter det i steg 3, 4 och 5. Vid modelleringssteget visas metadata och inte nyttolasten: kontrollrummet läser bara det som redan är exponerat, samma avgränsning som i resten av vyn.', 'Look for it in steps 3, 4 and 5. At the modelling step metadata is shown, not the payload: the control room only reads what is already exposed, the same limit as in the rest of the view.')}</p>
    <div id="foljinvarianter"></div>
    <div class="knappar"><button class="kor sek" onclick="laddaFolj()">{S('Uppdatera', 'Refresh')}</button></div>
  </div>
  <div id="foljhopp"><p>{S('hämtar …', 'fetching …')}</p></div>
</section>

<section id="audit" class="flik">
  <div class="ruta">
    <h2>{S('Auditlogg – hela kedjan i kronologisk ordning', 'Audit log – the whole chain in chronological order')}</h2>
    <p class="text"><b>{S('Det komponenterna kan bevisa efteråt.', 'What the components can prove afterwards.')}</b>
       {S('Det du själv körde, med raderna från körningen, finns under Jobb.', 'What you ran yourself, with the lines from the run, is under Jobs.')}
       <button class="kor sek" onclick="visa('jobb')">{S('Till jobben', 'To the jobs')}</button></p>
    <p class="text">{S('Ingen komponent äger loggen. Den sammanställs ur stadens connector (förhandlingar och leveranser), DHI:s KoV-kö, mottagningens kvitton och avvisningar och hävda avtal, och kompletteras med kontrollrummets egna knapptryck.', 'No component owns the log. It is compiled from the city’s connector (negotiations and deliveries), DHI’s KoV queue, the intake’s receipts and rejections and revoked agreements, and complemented with the control room’s own button presses.')}</p>
    <p class="meta" id="auditsammanfattning"></p>
    <p class="meta" id="auditkedja"></p>
    <label>{S('Filtrera på steg:', 'Filter by step:')}
      <select id="auditfilter" onchange="laddaAudit()">
        <option value="">{S('alla', 'all')}</option>
        <option value="1">1 – {S('modellen (FCF)', 'the model (FCF)')}</option>
        <option value="2">2 – {S('DSP-katalog', 'DSP catalogue')}</option>
        <option value="3">3 – {S('förhandling och KoV', 'negotiation and KoV')}</option>
        <option value="4">4 – {S('leverans och mottagning', 'delivery and intake')}</option>
        <option value="5">5 – {S('värde med ursprung', 'value with provenance')}</option>
        <option value="6">6 – {S('användning', 'use')}</option>
      </select></label>
    <table><tr><th>{S('Tid (UTC)', 'Time (UTC)')}</th><th>{S('Steg', 'Step')}</th><th>{S('Källa', 'Source')}</th><th>{S('Resultat', 'Result')}</th>
      <th>{S('Händelse', 'Event')}</th></tr><tbody id="auditlogg" data-stabil></tbody></table>
  </div>
</section>

<section id="suveranitet" class="flik">
  <div class="ruta">
    <h2>{S('KoV-godkännande – dataägarens beslut', 'KoV approval – the data owner’s decision')}</h2>
    <p class="text">{S('Knapparna går till <b>DHI:s</b> connector', 'The buttons go to <b>DHI’s</b> connector')}<span id="kovapirad" hidden> (<code id="kovapi"></code>)</span>.
       {S('Spärren sitter hos den som lämnar ut data. Stadens connector har ingen sådan funktion alls, så det finns ingen bakväg att klicka på.', 'The barrier sits with the party releasing the data. The city’s connector has no such function at all, so there is no back door to click.')}</p>
    <div class="roll-banner">
      <p class="text">{S('<b>Här agerar du KoV.</b> I steget Förhandla A (i kedjevyn) är du en tekniker som startar en förhandling. När du klickar Godkänn eller Avslå (knapparna visas bredvid en väntande förhandling) byter du roll: du fattar det beslut som i verkligheten hör hemma hos Kretslopp och Vatten, inte hos den som driver kedjan. Kontrollrummet ska alltid visa VEM som agerar, så att rollerna aldrig glider ihop till en enda anonym operatör.', '<b>Here you act as KoV.</b> In the Negotiate A step (in the chain view) you are an engineer starting a negotiation. When you click Approve or Reject (the buttons appear next to a waiting negotiation) you change role: you make the decision that in reality belongs to Kretslopp och Vatten, not to whoever runs the chain. The control room must always show WHO is acting, so that the roles never blur into one anonymous operator.')}</p>
    </div>
    <p class="text">{S('När du kör Förhandla A väntar jobbet högst 25 sekunder (oftast 3–8) och läser sedan av providerns kö. Det är inte en tidsfrist för beslutet, utan tid för förhandlingen att hinna fram och registreras som väntande. Görs inget beslut händer inget dramatiskt: jobbet blir klart och förhandlingen ligger kvar i kön tills någon godkänner eller avslår den, om fem sekunder eller nästa dag. När du godkänner eller avslår väntar jobbet upp till 60 sekunder på att stadens förhandling får sitt avtal, så du behöver inte köra Förhandla A igen.', 'When you run Negotiate A the job waits up to 25 seconds (usually 3–8) and then reads the provider’s queue. That is not a deadline for the decision, but time for the negotiation to arrive and be registered as waiting. If no decision is made nothing dramatic happens: the job completes and the negotiation stays in the queue until someone approves or rejects it, in five seconds or the next day. When you approve or reject, the job waits up to 60 seconds for the city’s negotiation to get its agreement, so you do not need to run Negotiate A again.')}</p>
    <div class="framtid">
      <p><b>{S('I framtiden', 'In the future')}</b> – {S('DHI:s spärr kräver redan i dag ett kryptografiskt verifierat KoV-rollintyg innan ett godkännande eller avslag accepteras, och kontrollrummet hämtar intyget åt dig. Det som återstår är själva automatiseringen: i dag klickar en människa (du, som KoV). Om den som startar en förhandling i stället själv bar ett verifierat KoV-intyg skulle spärren kunna godkänna automatiskt. Knapparna blir då en manuell reservväg. Ändringen ligger i spärrens policy, inte i var beslutet fattas eller i identitetskontrollen, som redan finns.', 'DHI’s barrier already requires a cryptographically verified KoV role credential before an approval or rejection is accepted, and the control room fetches the credential for you. What remains is the automation itself: today a human (you, as KoV) clicks. If the party starting a negotiation itself carried a verified KoV credential, the barrier could approve automatically. The buttons would then become a manual fallback. The change lies in the barrier’s policy, not in where the decision is made or in the identity check, which already exists.')}</p>
    </div>
    <p class="meta" id="kovantal"></p>
    <table><tr><th>{S('DHI:s förhandlings-id', 'DHI’s negotiation id')}</th><th>{S('Dataprodukt (asset)', 'Data product (asset)')}</th>
      <th>{S('Tillstånd', 'State')}</th><th>{S('KoV-beslut', 'KoV decision')}</th><th>{S('Åtgärd / avtal', 'Action / agreement')}</th></tr>
      <tbody id="kovlista" data-stabil></tbody></table>
    <h3>{S('Avtal – gäller tills de hävs eller löper ut', 'Agreements – valid until revoked or expired')}</h3>
    <p class="text">{S('Ett avtal gäller tills det hävs eller löper ut, inte bara för en enda datahämtning. Statusen ägs av DHI:s connector och synkas till stadens avtalsregister ungefär varje sekund (PoC-förenkling). <b>Så fungerar PoC:en:</b> KoV kan häva ett avtal direkt med knappen. Regeln att ett avslag av en ny begäran om A häver tidigare avtal för samma part finns också, men är avstängd i den delade demon (besökarna delar tillgången). Det är en medveten förenkling: i ett riktigt dataspace kan hävning kräva en egen åtgärd. Avtalets id är olika hos DHI och staden, och förhandlingens id likaså.', 'An agreement is valid until it is revoked or expires, not just for a single data fetch. The status is owned by DHI’s connector and synced to the city’s agreement register about every second (PoC simplification). <b>How the PoC works:</b> KoV can revoke an agreement directly with the button. A rule where rejecting a new request for A revokes earlier agreements for the same party also exists, but it is switched off in the shared demo (visitors share the asset). This is a deliberate simplification: in a real data space, revocation may need a separate action. The agreement id differs between DHI and the city, and so does the negotiation id.')}</p>
    <p class="meta" id="avtalantal"></p>
    <p class="meta">{S('Varje förhandling ger ett eget avtal, så det kan finnas flera som gäller. Vid en leverans används det senaste.', 'Every negotiation produces its own agreement, so several can be valid at once. A delivery uses the latest one.')}</p>
    <table class="brytbar"><tr><th>{S('Stadens avtals-id', 'City’s agreement id')}</th><th>{S('Distribution', 'Distribution')}</th>
      <th>{S('Status', 'Status')}</th><th>{S('Villkor', 'Terms')}</th><th>{S('Åtgärd', 'Action')}</th></tr>
      <tbody id="avtallista" data-stabil></tbody></table>
    <div class="knappar">
      <button class="kor" data-atgard="forhandla-a"
              onclick="kor('forhandla-a')">{S('Begär distribution A (fyller kön)', 'Request distribution A (fills the queue)')}</button>
      <button class="kor sek" onclick="laddaKov()">{S('Uppdatera', 'Refresh')}</button>
    </div>
  </div>
  <div id="odrlsvar"></div>
</section>

<section id="felinjektion" class="flik">
  <div class="ruta">
    <h2>{S('Felinjektion i modellen – och vad mottagningen gör med den', 'Fault injection in the model – and what the intake does with it')}</h2>
    <p class="text">{S('Lägena manipulerar dataprodukten <b>tyst</b>: nyttolasten bär ingen flagga om att den är felaktig. Stadens mottagning ska upptäcka det själv: schemadrift och saknade parametrar mot avtalet, och framför allt <code>gis_i_b</code>, som är ett rent avtalsbrott: brunnarnas position tillbaka i den distribution som är öppna data.', 'The modes tamper with the data product <b>silently</b>: the payload carries no flag saying it is faulty. The city’s intake must detect it on its own: schema drift and missing parameters against the agreement, and above all <code>gis_i_b</code>, which is a plain breach of the agreement: chamber positions back in the distribution that is open data.')}</p>
    <p class="meta" id="felomfattning"></p>
    <div id="felreglage" data-stabil></div>
    <p id="felstatus"></p>
    <div class="knappar">
      <button class="kor" onclick="nollstallFel()">{S('Nollställ felinjektionen', 'Reset the fault injection')}</button>
      <button class="kor" data-atgard="kor-batch"
              onclick="kor('kor-batch')">{S('Kör en ny batch', 'Run a new batch')}</button>
      <button class="kor" data-atgard="transfer-b"
              onclick="kor('transfer-b')">{S('Leverera B (kör transfer) och se utfallet', 'Deliver B (run transfer) and see the outcome')}</button>
      <span class="last-hint" role="status" hidden></span>
    </div>
  </div>
  <div class="ruta">
    <h3>{S('Resultat: mottagningens senaste leveranser', 'Result: the intake’s latest deliveries')}</h3>
    <table><tr><th>{S('Tid', 'Time')}</th><th>{S('Resultat', 'Result')}</th><th>{S('Detalj', 'Detail')}</th></tr>
      <tbody id="felresultat" data-stabil></tbody></table>
  </div>
</section>

<section id="jobb" class="flik">
  <div class="ruta">
    <button class="kor sek" onclick="tillbakaFranJobb()">{S('← Tillbaka', '← Back')}</button>
    <h2>{S('Jobb – körda steg', 'Jobs – steps that have run')}</h2>
    <p class="text"><b>{S('Jobb och auditlogg är inte samma sak.', 'Jobs and the audit log are not the same thing.')}</b>
       {S('Ett jobb är <b>det du körde</b>: ett knapptryck och raderna som körningen skrev medan den pågick. Auditloggen är <b>det komponenterna kan bevisa efteråt</b>: förhandlingar, avtal, kvitton och avvisningar hämtade ur connectorerna och mottagningen, i kronologisk ordning och hash-kedjade.', 'A job is <b>what you ran</b>: one button press and the lines the run wrote while it was going. The audit log is <b>what the components can prove afterwards</b>: negotiations, agreements, receipts and rejections fetched from the connectors and the intake, in chronological order and hash-chained.')}
       <button class="kor sek" onclick="visa('audit')">{S('Till auditloggen', 'To the audit log')}</button></p>
    <p class="meta">{S('Ett jobb i taget: kedjan körs i följd, annars blir utfallet obegripligt för den som tittar. Tillbaka stänger den här vyn och för dig till fliken du kom ifrån, kvar där du var.', 'One job at a time: the chain runs in sequence, otherwise the outcome becomes incomprehensible to the viewer. Back closes this view and takes you to the tab you came from, where you were.')}</p>
    <div class="roll-banner">
      <p class="text">{S('<b>Ett kört jobb är inte samma sak som ett beslut.</b> Förhandla distribution A startar bara förhandlingen. Den ligger sedan och väntar tills någon agerar <b>KoV</b> och godkänner eller avslår den. Det gör du inte här, utan i kedjevyn (steg 3) eller i fliken', '<b>A job that has run is not the same as a decision.</b> Negotiate distribution A only starts the negotiation. It then waits until someone acts as <b>KoV</b> and approves or rejects it. You do not do that here, but in the chain view (step 3) or in the')}
         <button class="kor sek" onclick="visa('suveranitet')">{S('Suveränitet', 'Sovereignty')}</button>{S('', ' tab')}.</p>
    <p class="text">{S('<b>Vad "klar" betyder.</b> <b>Förhandla distribution B</b> blir ett avtal direkt: B förhandlas fram automatiskt, så när jobbet är klart är avtalet tecknat och gäller (se Avtal). <b>Förhandla distribution A</b> är klart när förhandlingen är startad; avtalet finns först efter KoV:s godkännande, och tills dess står statusen "väntar på KoV".', '<b>What "done" means.</b> <b>Negotiate distribution B</b> turns into an agreement straight away: B is negotiated automatically, so when the job is done the agreement is made and valid (see Agreements). <b>Negotiate distribution A</b> is done when the negotiation has started; the agreement exists only after KoV approves, and until then the status says "waiting for KoV".')}</p>
    </div>
    <table><tr><th>#</th><th>{S('Åtgärd', 'Action')}</th><th>{S('Status', 'Status')}</th><th>{S('Startad', 'Started')}</th></tr>
      <tbody id="jobblista" data-stabil></tbody></table>
  </div>
  <div class="ruta"><p id="jobbpagar" class="jobbpagar" role="status" aria-live="polite"></p><pre id="jobblogg">{S('Välj ett jobb i listan.', 'Pick a job in the list.')}</pre></div>
</section>
"""


# ---------------------------------------------------------------------------
# Hjälpare
# ---------------------------------------------------------------------------
def e(text):
    return html.escape("" if text is None else str(text))


def fet(text):
    """Escapar text och gör **fet** till <b>. Stegtexterna i steg.py skrivs så."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e(text))


def _mall(mall, **varden):
    """Fyller i {namn} i en gränssnittstext utan att tolka andra klammrar."""
    for namn, varde in varden.items():
        mall = mall.replace("{%s}" % namn, str(varde))
    return mall


def _tx(sprak, nyckel, **varden):
    return _mall(TEXTER[sprak][nyckel], **varden)


# Kategori i steg.py -> klassnamn och symbol i CSS/bilden (mockupens namn)
_KAT = {"dataspace": ("ds", "◆"), "princip": ("princip", "◇"),
        "helhet": ("kedja", "□")}
# Bana -> rad i bildens grid (kolumn = stegnummer + 1)
_BANRAD = {"dhi": "2", "dhi-stad": "2 / 5", "stad": "4"}
_FLIKINDEX = {"folj": 1, "suveranitet": 3, "felinjektion": 4}
_FLIKORDNING = ("kedjan", "folj", "audit", "suveranitet",
                "felinjektion", "jobb", "om", "ordlista")
# "Prova i den här ordningen": vilket steg varje knapp i remsan hoppar till
_ORDNING_HOPP = (1, 2, 3, 4, 3, 4, 6)

# Nycklar i TEXTER som webbläsarens JavaScript behöver
_JS_NYCKLAR = (
    "sammanfattning", "statusTitel", "jobbRad", "jobbKor", "jobbPagar", "jobbKo", "jobbRadKo", "jobbStartar",
    "jobbFelStart", "jobbSvararInte", "loggRub", "tidigare1", "tidigareN",
    "helaLogg", "klar", "vantar", "avvisad", "ingetavtal", "fel", "nekad", "kovVantar", "kovInget", "kovFel",
    "kovAvtal", "kovAvtalN", "kovIngetAvtal", "kovIngetStart", "avtalFel", "odrlLive", "odrlStatisk", "provLive", "kunde", "kovVantarN", "svarar", "tidUtc",
    "statusNamn", "nasta", "nastaKnapp", "nastaSlut")


def _antal_teknik(steg):
    n = {"akta": 0, "forenklad": 0, "simulerad": 0}
    for s in steg:
        for x in s.get("teknik") or []:
            n[x["status"]] += 1
    return n


def _taggar(distributioner, t=None):
    ut = []
    # B före A (K20)
    for d in sorted(distributioner, key=lambda x: {"B": 0, "A": 1}.get(x, 2)):
        if d == "-A":
            ut.append('<span class="tag x"><s aria-hidden="true">A</s> %s</span>'
                      % e(t["aNarInte"] if t else "A når inte hit"))
        else:
            ut.append('<span class="tag %s">%s</span>' % (d.lower(), e(d)))
    return "".join(ut)


def _sidlank(flik, t, text=None):
    namn = t["flikar"][_FLIKINDEX[flik]]
    return ('<a class="sidlank" href="#%s" data-flik="%s">%s</a>'
            % (flik, flik, text or t["helaSidan"].replace("{f}", e(namn))))


def _rollchip(roll, t):
    return ('<span class="rollchip %s">%s: <b>%s</b></span>'
            % (e(roll), e(t["agerarSom"]), e(t["roll"][roll])))


# ---------------------------------------------------------------------------
# Sidhuvud, introduktion och ordningsremsa
# ---------------------------------------------------------------------------
def _sidhuvud(t, sprak):
    def S(sv, en):
        return e(en if sprak == 'en' else sv)

    flikar = list(t["flikar"]) + [t["omFlik"], ORDTEXT[sprak]["flik"]]
    knappar = "".join(
        '<button type="button" data-flik="%s"%s>%s</button>'
        % (fid, ' class="aktiv"' if i == 0 else "", e(namn))
        for i, (fid, namn) in enumerate(zip(_FLIKORDNING, flikar)))
    sprakknappar = "".join(
        '<button type="button" data-lang="%s" aria-pressed="%s">%s</button>'
        % (sp, "true" if sp == sprak else "false", sp.upper()) for sp in SPRAK)
    return f"""
<header>
  <div class="krtopp">
    <div class="krvanster">
      <img class="logga" src="{LOGGA_DATAURI}" alt="SVADA – Svenska vattendatalabbet" width="194" height="240">
      <div>
        <h1>{e(t['h1'])}</h1>
        <p class="underrubrik">{e(t['under'])} <span id="sammanfattning">{e(t['hamtar'])}</span></p>
      </div>
    </div>
    <div class="krhoger">
      <div class="sprak" role="group" aria-label="Språk / Language">{sprakknappar}</div>
      <div class="aterstallrad">
        <p class="aterstall" id="aterstall" hidden></p>
        <button type="button" class="aterstallinfo" id="aterstallinfo" hidden aria-haspopup="dialog"
                aria-label="{S('Om nollställningen', 'About the reset')}" title="{S('Om nollställningen', 'About the reset')}">?</button>
      </div>
    </div>
  </div>
  <div class="aterstallremsa" id="aterstallremsa" hidden><span id="aterstallremsatext"></span>
    <button type="button" class="lank" data-aterstallinfo>{S('Vad betyder det här?', 'What does this mean?')}</button></div>
  <dialog class="jobb" id="aterstalldialog" aria-labelledby="aterstalldialogrubrik">
    <div class="jhuvud"><h2 id="aterstalldialogrubrik"></h2>
      <button type="button" id="aterstallstang">{S('Stäng', 'Close')}</button></div>
    <div class="jkropp" id="aterstalldialogtext"></div>
  </dialog>
  <p class="srdold" id="aterstallsr" role="status"></p>
  <div class="pausremsa" id="pausremsa" hidden></div>
  <p class="srdold" id="skyddsr" role="status"></p>
  <nav id="flikar" aria-label="{e(t['flikarRub'])}">{knappar}</nav>
  <p id="lanknot" class="lanknot" role="status" hidden></p>
  <p class="meta" id="jobbrad" data-stabil></p>
</header>"""


def _intro(t, antal):
    return f"""
  <div class="intro">
    <div class="ingress">
      <h2>{e(t['introH'])}</h2>
      <p>{e(t['ingress'])}</p>
      <ul class="fakta">
        <li><span class="fikon f-ds">◆</span><span>{t['fakta1']}</span></li>
        <li><span class="fikon f-akta">✓</span><span>{_mall(t['faktaAkta'], a=antal['akta'], f=antal['forenklad'], r=antal['simulerad'])}</span></li>
        <li><span class="fikon f-gps">⌖</span><span>{t['fakta3']}</span></li>
      </ul>
      <button type="button" class="omlank" data-flik="om">{e(t['omLank'])} →</button>
    </div>
  </div>"""


def _ordningsremsa(t):
    knappar = ['<button type="button" data-hopp="%d"%s><span class="snr">%d</span>%s</button>'
               % (hopp, ' data-kov="1"' if i == 4 else "", hopp, e(namn))
               for i, (hopp, namn) in enumerate(zip(_ORDNING_HOPP, t["ordning"]))]
    return ('<div class="ordning" id="ordning"><div class="ordningtopp"><span class="etikett">%s</span></div>'
            '<div class="ordningsteg">%s<button type="button" class="nastaknapp" id="nastaknapp" hidden></button>'
            '<span class="nastaslut" id="nastaslut" role="status" hidden></span></div></div>'
            % (e(t["ordningEtikett"]), '<span class="pil">→</span>'.join(knappar)))


# ---------------------------------------------------------------------------
# Kedjebilden
# ---------------------------------------------------------------------------
def _nod(s, t, sprak):
    ped = s["pedagogik"]
    nr = s["nr"]
    kk, ikon = _KAT[ped["kategori"]]
    ikonklass = "ikon" if kk != "kedja" else "ikon kedjeikon"
    simulerad = any(x["status"] == "simulerad" for x in s["teknik"])
    taggar = _taggar(ped["distributioner"], t) + (
        '<span class="tag sim" title="%s">%s</span>'
        % (e(TEKNIKTEXT[sprak]["simulerad"]), e(t["simKort"])) if simulerad else "")
    org = stegmodul.text(ped["org"], sprak)
    return f"""
      <button type="button" class="nod {kk}" id="nod-{nr}" data-steg="{nr}"
              style="grid-column:{nr + 1};grid-row:{_BANRAD[ped['bana']]}"
              aria-expanded="false" aria-controls="steg-{nr}">{
        '<span class="borjahar">%s</span>' % e(t["borja"]) if nr == 1 else ''}
        <span class="topp"><span class="nr">{nr}</span><span class="{ikonklass}">{ikon}</span><span class="status" data-stegstatus="{nr}" title="{e(t['statusTitel'])}"></span></span>
        <span class="titel">{e(stegmodul.text(ped['titel'], sprak))}</span>
        <span class="orgmini">{e(org)} · {e(t['kat'][kk][2:])}</span>
        <span class="taggar">{taggar}</span>
      </button>"""


def _kovnod(t):
    return f"""
      <button type="button" class="nod kov" id="nod-kov" aria-controls="steg-3" aria-expanded="false"
              style="grid-column:4;grid-row:5">
        <span class="topp"><span class="nr">3</span><span class="ikon">◆</span></span>
        <span class="titel">{e(t['kovTitel'])}</span>
        <span class="orgmini">{e(t['kovOrg'])}</span>
        <span class="taggar"><span class="tag a">A</span></span>
      </button>"""


def _bild(steg, t, sprak):
    zonrubrik = {1: ("zon1", ""), 2: ("zon2", "ds"), 5: ("zon3", "")}
    noder = []
    for s in steg:
        if s["nr"] in zonrubrik:
            nyckel, klass = zonrubrik[s["nr"]]
            noder.append('<div class="zonrubrik %s">%s</div>' % (klass, e(t[nyckel])))
        noder.append(_nod(s, t, sprak))
        if s["nr"] == 3:
            noder.append(_kovnod(t))
    return f"""
  <div class="bildram">
    <div class="bild" id="bild">
      <div class="zon" style="grid-column:2/3"><span>{e(t['zon1'])}</span><small>{e(t['zon1s'])}</small></div>
      <div class="zon ds" style="grid-column:3/6"><span>{e(t['zon2'])}</span><small>{e(t['zon2s'])}</small></div>
      <div class="zon" style="grid-column:6/8"><span>{e(t['zon3'])}</span><small>{e(t['zon3s'])}</small></div>
      <div class="dsfalt" aria-hidden="true"></div>
      <div class="bildleg" aria-label="{e(t['legH'])}">
        <h3>{e(t['legH'])}</h3>
        <div class="lrad"><span class="prov ds">◆</span><span>{t['legDs']}</span></div>
        <div class="lrad"><span class="prov princip">◇</span><span>{t['legPrincip']}</span></div>
        <div class="lrad"><span class="prov statusbar"><span class="statusprick"></span></span><span>{t['legStatus']}</span></div>
        <div class="lfull">{t['legDist']}</div>
        <div class="lfull">{t['legSim']}</div>
      </div>

      <div class="bana" style="grid-row:2"><b>DHI</b><span>{e(t['banaDhi'])}</span></div>
      <div class="grans" aria-hidden="true"><span>{e(t['grans'])}</span></div>
      <div class="stadram" aria-hidden="true"></div>
      <div class="bana" style="grid-row:4"><i>{e(t['stad'])}</i><b>Intraservice</b><span>{e(t['banaIs'])}</span></div>
      <div class="banlinje inre" style="grid-row:5" aria-hidden="true"></div>
      <div class="bana" style="grid-row:5"><i>{e(t['stad'])}</i><b>Kretslopp och Vatten</b><span>{e(t['banaKov'])}</span></div>
      {"".join(noder)}
      <svg class="pilar" id="pilar" aria-hidden="true"></svg>
    </div>
  </div>"""


def _stegrad(steg, t, sprak):
    knappar = "".join(
        '<button type="button" class="s-%s" data-steg="%d" title="%s" aria-label="%d. %s">'
        '<span class="si" aria-hidden="true">%s</span>%d</button>'
        % (_KAT[s["pedagogik"]["kategori"]][0], s["nr"],
           e(stegmodul.text(s["pedagogik"]["titel"], sprak).replace("­", "")),
           s["nr"], e(stegmodul.text(s["pedagogik"]["titel"], sprak).replace("­", "")),
           _KAT[s["pedagogik"]["kategori"]][1], s["nr"]) for s in steg)
    return ('<nav class="stegrad" id="stegrad" aria-label="%s" hidden>'
            '<span class="srub">%s</span>%s'
            '<button type="button" class="upp" data-upp="1">%s</button></nav>'
            % (e(t["stegradRub"]), e(t["stegradRub"]), knappar, e(t["tillBilden"])))


# ---------------------------------------------------------------------------
# Panelen per steg
# ---------------------------------------------------------------------------
def _knappkort(aid, k, atgard, t, sprak):
    etikett = stegmodul.text(atgard["etikett"] if atgard else k["etikett"], sprak)
    roll = (atgard or k)["roll"]
    sida = (atgard or k).get("sida")
    extra = ""
    if aid == "forhandla-a":
        extra += ('<p class="tillkov"><button type="button" class="lank" data-hopp="3" data-kov="1">→ %s</button></p>'
                  % e(t["kovTillA"]))
    if sida:
        extra += _sidlank(sida, t)
    return f"""
        <div class="knappkort" id="kort-{e(aid)}">
          {_rollchip(roll, t)}
          <div class="knapprad"><button type="button" class="kor {e(k.get('klass', ''))}" data-atgard="{e(aid)}">{e(etikett)}</button>
            <span class="last-hint" role="status" hidden></span></div>
          <dl><div><dt>{e(t['dtGor'])}</dt><dd>{e(stegmodul.text(k['gor'], sprak))}</dd></div>
              <div><dt>{e(t['dtTitta'])}</dt><dd>{e(stegmodul.text(k['titta'], sprak))}</dd></div>
              <div><dt>{e(t['dtKraver'])}</dt><dd>{e(stegmodul.text(k['kraver'], sprak))}</dd></div></dl>
          <p class="livetal"></p>
          {extra}
          <div class="loggplats" aria-live="polite"></div>
        </div>"""


def _kovruta(kovknappar, t, sprak):
    kort = "".join(f"""
          <div class="kovval" id="kort-{e(aid)}">
            <button type="button" class="kor {e(k.get('klass', ''))}" data-kovbeslut="{ {'kov-godkann': 'godkann', 'kov-avsla': 'avsla', 'kov-hav': 'hav'}[aid] }" disabled>{e(stegmodul.text(k['etikett'], sprak))}</button>
            <div class="kovtext"><span class="last-hint" role="status" hidden></span>
              <dl><div><dt>{e(t['dtGor'])}</dt><dd>{e(stegmodul.text(k['gor'], sprak))}</dd></div>
                  <div><dt>{e(t['dtTitta'])}</dt><dd>{e(stegmodul.text(k['titta'], sprak))}</dd></div></dl></div>
            <div class="loggplats" aria-live="polite"></div>
          </div>""" for aid, k in kovknappar)
    return f"""
        <div class="kovruta" id="kovruta" data-id="">
          <div class="kovtopp"><span class="rollchip kov">{e(t['agerarSom'])}: <b>{e(t['roll']['kov'])}</b></span></div>
          <h4>{e(t['kovRub'])}</h4>
          <p class="kovintro">{e(t['kovIntro'])}</p>
          <p class="kovko"><span class="vantar" id="kovprick"></span><span id="kovstatus">{e(t['ladda'])}</span></p>
          <p class="kovko"><span id="kovavtalrad">{e(t['ladda'])}</span></p>{kort}
          {_sidlank('suveranitet', t, t['kovSidlank'])}
        </div>"""


def _prova(s, t, sprak):
    ped = s["pedagogik"]
    knappar = ped.get("knappar") or {}
    if not knappar:
        sida = ped.get("inga_knappar_sida")
        return ('<p class="ingaknappar">%s</p>%s'
                % (e(stegmodul.text(ped["inga_knappar"], sprak)),
                   _sidlank(sida, t) if sida else ""))
    atgarder = {a["id"]: a for a in s["atgarder"]}
    vanliga = [(i, k) for i, k in knappar.items() if k["roll"] != "kov"]
    kov = [(i, k) for i, k in knappar.items() if k["roll"] == "kov"]
    forklaringar = "".join(
        '<div class="forklaring"><p><b>%s</b> %s</p><p><b>%s</b> %s</p></div>'
        % (e(t["vadArRub"]), e(stegmodul.text(k["vad_ar"], sprak)),
           e(t["varforTestaRub"]), e(stegmodul.text(k["varfor_testa"], sprak)))
        for _, k in vanliga if k.get("vad_ar"))
    kort = "".join(_knappkort(i, k, atgarder.get(i), t, sprak) for i, k in vanliga)
    nyckel = ('<p class="distnyckel">%s</p>' % t["distNyckel"]) if s["nr"] in (3, 4) else ""
    return ('%s<div class="knappar%s">%s%s</div>%s'
            % (forklaringar, " medkov" if kov else "", kort,
               _kovruta(kov, t, sprak) if kov else "", nyckel))


def _odrlruta(t):
    o = t["odrl"]

    def kolumn(k, klass, json_text):
        regler = "".join('<li title="%s: %s"><code>%s</code><span>%s</span></li>'
                         % (e(r[0]), e(r[1]), e(r[0]), e(r[1])) for r in o[k]["regler"])
        bnot = '<p class="bnot">%s</p>' % e(o["bnot"]) if k == "B" else ""
        return (f'<div class="odrlkol {klass}" data-odrl="{k}"><h4><span class="tag {klass}">{k}</span> {e(o[k]["rub"])}</h4>'
                f'<ul>{regler}</ul>{bnot}'
                f'<details><summary>{e(o["visaJson"])}</summary><pre class="logg">{e(json_text)}</pre></details></div>')
    verkstall = "".join("<dt>%s</dt><dd>%s</dd>" % (e(r[0]), e(r[1])) for r in o["verkstall"]["rader"])
    las = "".join('<li class="las"><b>%s</b> <span class="vem">%s</span><br>%s</li>' % (e(x[0]), e(x[1]), e(x[2]))
                  for x in o["verkstall"]["las"])
    return (f'<div class="odrlruta"><h3>{e(o["rub"])}</h3><p class="odrlintro">{e(o["intro"])}</p>'
            f'<div class="odrlgrid" id="odrlkolumner">{kolumn("B", "b", _ODRL_B)}{kolumn("A", "a", _ODRL_A)}</div>'
            f'<div class="verkstall"><h4>{e(o["verkstall"]["rub"])}</h4><dl>{verkstall}</dl>'
            f'<h5>{e(o["verkstall"]["lasRub"])}</h5><ol class="laslista">{las}</ol></div>'
            f'<p class="anteckning" id="odrlstatus">{e(o["not"])}</p></div>')


def _sehur(t, sprak="sv"):
    o = t["sehur"]
    flikar = [("kat", o["katFlik"], o["katText"]), ("vc", o["vcFlik"], o["vcText"]),
              ("nej", o["nejFlik"], o["nejText"])]
    knappar = "".join(
        '<button type="button" role="tab" aria-selected="%s" data-sflik="%s">%s</button>'
        % ("true" if i == 0 else "false", f[0], e(f[1])) for i, f in enumerate(flikar))

    def innehall(i, f):
        if f[0] == "kat":
            kropp = (f'<div class="katpar"><div><h4><span class="tag b">B</span> {e(o["katB"])}</h4>'
                     f'<pre class="logg">{e(_ex_sprak(_EX_KAT_B, sprak))}</pre></div>'
                     f'<div><h4><span class="tag a">A</span> {e(o["katA"])}</h4>'
                     f'<pre class="logg">{e(_ex_sprak(_EX_KAT_A, sprak))}</pre></div></div>')
        else:
            kropp = '<pre class="logg">%s</pre>' % e(_ex_sprak(_EX_VC if f[0] == "vc" else _EX_401, sprak))
        return ('<div class="sinnehall" data-sinn="%s"%s><p>%s</p>%s</div>'
                % (f[0], "" if i == 0 else " hidden", e(f[2]), kropp))
    bladdra = (f'<div class="sstep"><button type="button" class="kor sek" data-sstep="-1" disabled>◀ {e(o["foreg"])}</button>'
               f'<span class="sraknare" aria-live="polite">1 {e(o["av"])} {len(flikar)}</span>'
               f'<button type="button" class="kor sek" data-sstep="1">{e(o["nasta"])} ▶</button></div>')
    return (f'<div class="sehur"><h3>{e(o["rub"])}</h3><p class="stips">{e(o["tips"])}</p><div class="sflikar" role="tablist">{knappar}</div>'
            + "".join(innehall(i, f) for i, f in enumerate(flikar))
            + bladdra + f'<p class="anteckning">{e(o["not"])}</p></div>')


def _svadaruta(t, sprak, aktiv=True):
    """Steg 3: samordnaren Svada stänger ute eller släpper in en deltagare (fylls av laddaSvada()). I den externa varianten
    (`aktiv=False`) finns inga knappar: utestängningen fungerar men stänger ute ALLA besökare samtidigt, så den visas som ett
    inspelat exempel (utdragen är riktiga svar ur en lokal körning 2026-10-20, förkortade)."""
    def S(sv, en):
        return sv if sprak == "sv" else en
    if not aktiv:
        return f"""
    <p class="hopplank"><button type="button" class="lank" data-hoppid="kort-forhandla-b">↓ {S('Hoppa till knapparna Förhandla B och A', 'Jump to the Negotiate B and A buttons')}</button></p>
    <div class="svadaruta" id="svadaruta">
      <div class="kovtopp"><span class="rollchip kov">{S('Samordnaren', 'The coordinator')}: <b>{S('Svada', 'Svada')}</b></span></div>
      <h4>{S('Samordnaren kan stänga ute en deltagare', 'The coordinator can exclude a participant')}</h4>
      <p class="kovintro">{S('Svadas utfärdare har gett DHI och staden medlemsintyg. Återkallas stadens intyg nekar DHI staden (ingen katalog, inga nya avtal). Återkallas DHI:s intyg avvisar staden DHI:s meddelanden, så ett nytt avtal kan inte ingås. Redan ingångna avtal berörs inte av det; de gäller tills KoV häver dem eller de löper ut (för A efter 30 dagar). Utestängningen fungerar, men den är avstängd i den publika demon eftersom den stänger ute alla besökare samtidigt. Så här ser det ut:', 'The Svada issuer has given DHI and the city membership credentials. If the credential of the city is revoked, DHI refuses the city (no catalogue, no new agreements). If the credential of DHI is revoked, the city rejects messages from DHI, so a new agreement cannot be made. Agreements already made are not affected by it; they stay valid until KoV revokes them or they expire (for A after 30 days). The exclusion works, but it is switched off in the public demo because it would exclude all visitors at the same time. This is what it looks like:')}</p>
      <div class="utdrag">
        <h5>{S('Statuslistan hos Svadas utfärdare, efter att stadens medlemsintyg återkallats', 'The status list at the Svada issuer, after the city’s membership credential was revoked')}</h5>
        <pre>{{ "mottagare": "dhi",  "typ": "SvadaMembershipCredential", "aterkallat": false }}
{{ "mottagare": "stad", "typ": "SvadaMembershipCredential", "aterkallat": true }}</pre>
        <h5>{S('DHI:s connector svarar på stadens katalogförfrågan (Dataspace Protocol)', 'DHI’s connector answers the city’s catalogue request (Dataspace Protocol)')}</h5>
        <pre>{{ "@type": "CatalogError", "code": "401", "reason": ["Unauthorized"] }}</pre>
        <h5>{S('Jobbloggens rad när staden försöker hämta katalogen', 'The job log line when the city tries to fetch the catalogue')}</h5>
        <pre>{S('NEKAD av spärren: Staden nekas av DHI (401): DHI godtar inte stadens medlemsintyg.', 'REFUSED by the safeguard: The city is refused by DHI (401): DHI does not accept the city’s membership credential.')}</pre>
      </div>
      <p class="meta">{S('Utdragen är riktiga svar ur en lokal körning 2026-10-20, förkortade (statuslistan har fyra poster: medlems- och deltagarintyg för DHI och staden).', 'The excerpts are real responses from a local run on 2026-10-20, shortened (the status list has four entries: membership and participant credentials for DHI and the city).')}</p>
      <p class="kovko"><button type="button" class="kor" id="svadaprov">{S('Prova katalogförfrågan nu (staden → DHI)', 'Try a catalogue request now (city → DHI)')}</button> <span id="svadautfall" aria-live="polite"></span></p>
    </div>"""
    return f"""
    <p class="hopplank"><button type="button" class="lank" data-hoppid="kort-forhandla-b">↓ {S('Hoppa till knapparna Förhandla B och A', 'Jump to the Negotiate B and A buttons')}</button></p>
    <div class="svadaruta" id="svadaruta">
      <div class="kovtopp"><span class="rollchip kov">{S('Agerar som', 'Acting as')}: <b>{S('Svada (samordnaren)', 'Svada (the coordinator)')}</b></span></div>
      <h4>{S('Samordnaren stänger ute en deltagare', 'The coordinator excludes a participant')}</h4>
      <p class="kovintro">{S('Svadas utfärdare har gett DHI och staden medlemsintyg. Återkallas stadens intyg nekar DHI staden (ingen katalog, inga nya avtal). Återkallas DHI:s intyg avvisar staden DHI:s meddelanden, så ett nytt avtal kan inte ingås. Det är den styrning på dataspacets nivå som annars bara är en rad i en tabell. Uteslutningen stoppar nya meddelanden och förhandlingar; redan ingångna avtal berörs inte av den och gäller tills KoV häver dem eller de löper ut (30 dagar). Återinsätt intyget så fungerar allt igen, utan omstart. I den publika demon släpps parten in igen av sig själv efter några minuter.', 'The Svada issuer has given DHI and the city membership credentials. If the credential of the city is revoked, DHI refuses the city (no catalogue, no new agreements). If the credential of DHI is revoked, the city rejects messages from DHI, so a new agreement cannot be made. This is the data-space-level governance that is otherwise just a row in a table. The exclusion stops new messages and negotiations; agreements already made are not affected by it and stay valid until KoV revokes them or they expire (30 days). Reinstate the credential and everything works again, with no restart. In the public demo the party is let back in automatically after a few minutes.')}</p>
      <table class="analystabell" id="svadatabell" data-stabil><tr><td>{S('hämtar …', 'fetching …')}</td></tr></table>
      <p class="kovko"><button type="button" class="kor" id="svadaprov">{S('Prova katalogförfrågan nu (staden → DHI)', 'Try a catalogue request now (city → DHI)')}</button> <span id="svadautfall" aria-live="polite"></span></p>
    </div>"""


def _analysruta(t, sprak):
    """Steg 6: inspektionsprioriteringen (fylls av laddaAnalys() i webbläsaren)."""
    def S(sv, en):
        return sv if sprak == "sv" else en
    return f"""
    <div class="analys" id="analysruta">
      <h3>{S('Inspektionsprioritering', 'Inspection priority')}</h3>
      <p class="meta">{S('Vilka bräddbrunnar bör staden inspektera först? Brunnarna rangordnas efter modellerad bräddvolym. Välj vilken distribution analysen bygger på.', 'Which overflow chambers should the city inspect first? The chambers are ranked by modelled overflow volume. Choose which distribution the analysis is based on.')}</p>
      <div class="analyskontroll">
        <fieldset class="lagevaljare">
          <legend>{S('Välj distribution', 'Choose distribution')}</legend>
          <div class="segment" role="presentation">
            <label class="seg"><input type="radio" name="analyslage" value="a" checked onchange="laddaAnalys()" aria-label="{S('A – skyddade data (kräver ett gällande avtal)', 'A – protected data (requires a current agreement)')}"><span><b>A</b> {S('skyddade data', 'protected data')}<small>{S('med position på karta', 'with position on a map')}</small></span></label>
            <label class="seg"><input type="radio" name="analyslage" value="b" onchange="laddaAnalys()" aria-label="{S('B – öppna data', 'B – open data')}"><span><b>B</b> {S('öppna data', 'open data')}<small>{S('utan position', 'without position')}</small></span></label>
          </div>
        </fieldset>
        <label>{S('Peka ut de', 'Point out the')} <input type="number" id="analystopp" min="1" max="91" value="10" onchange="laddaAnalys()"> {S('brunnarna med störst bräddvolym', 'chambers with the largest overflow volume')}</label> <span class="meta">{S('(tryck Enter eller lämna fältet)', '(press Enter or leave the field)')}</span>
      </div>
      <div id="analysstatus" class="meta" aria-live="polite"></div>
      <div id="analysresultat"></div>
      <div class="brunnjamfor" id="brunnjamfor">
        <h4>{S('Samma brunn i B och A', 'The same chamber in B and A')}</h4>
        <p class="meta">{S('Samma bräddbrunn ur stadens plattform, läst ur den öppna distributionen B och den skyddade distributionen A. B saknar brunnens position; A har den, men bara så länge det finns ett gällande avtal.', 'The same overflow chamber from the city’s platform, read from the open distribution B and the protected distribution A. B lacks the chamber’s position; A has it, but only while there is a current agreement.')}</p>
        <div class="katpar" id="brunnjamforkol"><p class="meta">{S('hämtar …', 'fetching …')}</p></div>
      </div>
    </div>"""


def _provruta(t, sprak="sv"):
    o = t["prov"]
    return (f'<div class="sehur provruta"><h3>{e(o["rub"])}</h3><p>{e(o["intro"])}</p>'
            f'<div class="katpar"><div><h4>{e(o["v1"])}</h4><pre class="logg" id="provvarde">{e(_EX_PROV)}</pre></div>'
            f'<div><h4>{e(o["v2"])}</h4><pre class="logg" id="provavtal">{e(_ex_sprak(_EX_AVTAL, sprak))}</pre></div></div>'
            f'<p class="anteckning" id="provstatus">{e(o["not"])}</p></div>')


def _teknikruta(s, t, sprak):
    tt = TEKNIKTEXT[sprak]
    ped = s["pedagogik"]
    rader = []
    for x in s["teknik"]:
        lankar = "".join(
            '<a href="%s" target="_blank" rel="noopener">%s ↗</a>' % (e(url), e(namn))
            for namn, url in x.get("lankar") or [])
        rader.append(
            '<li><span class="tstatus s-%s">%s</span>'
            '<span class="tnamn">%s%s%s</span><span class="tgor">%s</span></li>'
            % (x["status"], e(tt["akta_egen"] if x["status"] == "akta" and x.get("egen") else tt[x["status"]]), e(stegmodul.text(x["namn"], sprak)),
               '<span class="tlankar">%s</span>' % lankar if lankar else "",
               '<span class="tegen">%s</span>' % e(tt["egen"]) if x.get("egen") else "",
               e(stegmodul.text(x["gor"], sprak))))
    return (f'<div class="teknikruta"><h3>{e(tt["rub"])}</h3><ul class="tlista">{"".join(rader)}</ul>'
            f'<div class="akta"><div><h4>{e(t["akta"])}</h4><p>{e(stegmodul.text(ped["akta"], sprak))}</p></div>'
            f'<div><h4>{e(t["forenklat"])}</h4><p>{e(stegmodul.text(ped["forenklat"], sprak))}</p></div></div></div>')


def _teknikdetaljer(s, komponenter, t, sprak, variant):
    tt = TEKNIKTEXT[sprak]
    ped = s["pedagogik"]
    nr = s["nr"]
    chips = "".join(
        '<span class="chip" data-komponent="%s"><span class="prick"></span>%s</span>'
        % (e(k["id"]), e(k["namn"])) for k in komponenter if k["steg"] == nr)
    intern = ""
    if variant == "intern":
        blue = (s.get("fordjupning") or {}).get("blueprint")
        if blue:
            intern = ('<p class="anteckning"><b>Relation till målarkitekturen.</b> %s</p>' % e(blue))
    return f"""
    <details class="teknik">
      <summary>{e(tt['mer'])}</summary>
      <div class="tgrid">
        <div>{'' if variant == 'extern' else f"<p><b>{e(tt['kompEtikett'])}</b> <code>{e(ped['komponenter'])}</code></p>"}
          <p>{chips}</p>
          <p><b>{e(t['prot'])}</b> {e(stegmodul.text(ped['protokoll'], sprak))}</p>
          <p class="anteckning">{e(t['teknikNot'])}</p>{intern}</div>
        <div><table class="siffror"><caption style="text-align:left;font-size:.75rem;color:var(--dov);padding-bottom:.2rem">{e(t['siffrorRub'])}</caption>
          <tbody data-detaljer="{nr}" data-stabil><tr><td>{e(t['ladda'])}</td><td></td></tr></tbody></table>
          <details class="exempeldetalj" data-laddat="" ontoggle="oppnaExempel(this, {nr})">
            <summary>{e(t['visaExempel'])}</summary>
            <div class="exempelinnehall"><p class="meta">{e(t['ladda'])}</p></div>
          </details></div>
      </div>
    </details>"""


def _panel(s, steg, komponenter, t, sprak, variant, utestangning=True):
    ped = s["pedagogik"]
    nr = s["nr"]
    i = steg.index(s)
    kk, _ = _KAT[ped["kategori"]]
    titel = stegmodul.text(ped["titel"], sprak)
    foreg = steg[i - 1] if i > 0 else None
    nasta = steg[i + 1] if i < len(steg) - 1 else None
    namn = lambda x: "%s %d: %s" % (t["steg"], x["nr"], stegmodul.text(x["pedagogik"]["titel"], sprak).replace("­", ""))
    byggblock = ('<div class="byggblock">%s</div>' % e(stegmodul.text(ped["byggblock"], sprak))
                 if ped.get("byggblock") else "")
    styrning = ('<div class="styrning"><b>%s</b> %s</div>' % (e(t["styrning"]), e(stegmodul.text(ped["styrning"], sprak)))
                if ped.get("styrning") else "")
    sehanda = ""
    extra_ruta = ""
    if nr == 2:
        extra_ruta = _odrlruta(t) + _sehur(t, sprak)
    if nr == 5:
        extra_ruta = _provruta(t, sprak)
    if nr == 3:
        extra_ruta = _svadaruta(t, sprak, utestangning)
    if nr == 6:
        extra_ruta = _analysruta(t, sprak)
    extra_text = ("<p class=\"anteckning\">%s</p>" % e(stegmodul.text(ped["extra"], sprak))
                  if ped.get("extra") else "")
    return f"""
  <div class="panel" id="steg-{nr}" data-steg-panel="{nr}" hidden aria-labelledby="steg-{nr}-titel">
    <div class="phuvud">
      <span class="stegnr">{e(_mall(t['stegAv'], n=nr))}</span>
      <span class="kat {kk}">{e(t['kat'][kk])}</span>
      <span class="org">{e(stegmodul.text(ped['org'], sprak))}</span>
      <button type="button" class="stang" aria-label="{e(t['stangAria'])}">{e(t['stang'])}</button>
    </div>
    <h2 id="steg-{nr}-titel">{e(titel.replace(chr(0xAD), ''))}</h2>
    <div class="prova">
      <h3>{e(t['prova'])}</h3>
      {_prova(s, t, sprak)}
      {extra_text}
    </div>
    <div class="pgrid">
      <div>
        <h3>{e(t['vad'])}</h3><p>{fet(stegmodul.text(ped['vad'], sprak))}</p>
        <h3>{e(t['varfor'])}</h3><p>{fet(stegmodul.text(ped['varfor'], sprak))}</p>
      </div>
      <div class="hogerkol">
        <div class="dsruta {kk}">
          <h3>{e(t['dsH'][kk])}</h3>
          <p>{fet(stegmodul.text(ped['dataspace'], sprak))}</p>
          {byggblock}
          {styrning}
        </div>
        {sehanda}
      </div>
    </div>
    {extra_ruta}
    {_teknikruta(s, t, sprak)}
    {_teknikdetaljer(s, komponenter, t, sprak, variant)}
    <div class="pnav">
      <button type="button" data-steg="{foreg['nr'] if foreg else nr}"{'' if foreg else ' disabled'}>← {e(namn(foreg)) if foreg else ''}</button>
      {f'<button type="button" data-steg="{nasta["nr"]}">{e(namn(nasta))} →</button>' if nasta else ''}
    </div>
  </div>"""


# ---------------------------------------------------------------------------
# Om demon och ordlistan
# ---------------------------------------------------------------------------
def _omsida(t, antal):
    return f"""
<section id="om" class="flik">
  <div class="omsida">
    <h2>{e(t['omH'])}</h2>
    <div class="omkol">
      <div>
        <h3>{e(t['omVadH'])}</h3>
        <p>{e(t['intro1'])}</p>
        <p>{t['intro2']}</p>
        <p class="aktaintro">{t['introAkta']}</p>
        <p class="stapelrad">{_mall(t['stapel'], a=antal['akta'], f=antal['forenklad'], r=antal['simulerad'])}</p>
      </div>
      <div class="euruta"><h3>{e(t['euH'])}</h3><p>{e(t['eu1'])}</p><p>{e(t['eu2'])}</p></div>
    </div>
    <div class="omprojekt" id="omprojekt">
      <div><h3>{e(t['omProjH'])}</h3><p>{t['omProj']}</p></div>
      <div><h3>{e(t['omBpH'])}</h3><p>{t['omBp']}</p></div>
      <div><h3>{e(t['omKredH'])}</h3><p>{e(t['omKred'])}</p></div>
    </div>
    <div class="omdata" id="omdata">
      <h2>{e(t['omdataH'])}</h2>
      <div class="omgrid">
        <div><h3>{e(t['omMatH'])}</h3><p>{e(t['omMat'])}</p></div>
        <div><h3>{e(t['omKoordH'])}</h3><p>{t['omKoord']}</p></div>
        <div><h3>{e(t['omModellH'])}</h3><p>{e(t['omModell'])}</p></div>
        <div><h3>{e(t['omFartH'])}</h3><p>{e(t['omFart'])}</p></div>
        <div><h3>{e(t['omLiveH'])}</h3><p>{e(t['omLive'])}</p></div>
      </div>
    </div>
  </div>
</section>"""


_SORT_SV = str.maketrans({"å": "z{", "ä": "z|", "ö": "z}"})


def _ordlistesida(sprak):
    ot = ORDTEXT[sprak]
    nyckel = (lambda o: o[sprak]["term"].lower().translate(_SORT_SV)) if sprak == "sv" \
        else (lambda o: o[sprak]["term"].lower())
    rader = []
    for o in sorted(ORDLISTA, key=nyckel):
        lank = ""
        if o.get("lank"):
            lank = (' <a class="lasmer" href="%s" target="_blank" rel="noopener">%s ↗</a>'
                    % (e(o["lank"]), "Läs mer" if sprak == "sv" else "Read more"))
        rader.append('<div id="ordlista-%s"><dt>%s</dt><dd>%s%s</dd></div>'
                     % (e(o["id"]), e(o[sprak]["term"]), e(o[sprak]["def"]), lank))
    return f"""
<section id="ordlista" class="flik">
  <div class="ordsida">
    <h2>{e(ot['rub'])}</h2>
    <p class="ordintro">{e(ot['intro'])}</p>
    <dl class="ordlista">{"".join(rader)}</dl>
  </div>
</section>"""


def _ingangar(portar, vard, publika, t, sprak, variant):
    """Rutan längst ned i kedjevyn: vilka adresser besökaren når."""
    if variant == "extern" and not publika:
        return ""      # inga portnummer i den externa varianten
    if publika:
        # Publik demo: besökaren når bara de publika ingångarna (Caddy).
        def visad(url):
            # De publika ingångarna visas EXAKT som de nås. Lokalt har Caddy en port (t.ex. :38080) som hör till adressen;
            # utan den fungerar inte texten. Interna portar (EDC, Orion …) rensas på andra ställen (rensa.py), inte här.
            return url
        rader = "".join(
            '<tr><td>%s</td><td><a href="%s" target="_blank" rel="noopener"><code>%s</code></a></td></tr>'
            % (e(t.get("pub_" + nyckel, nyckel)),
               e(url + ("?lang=en" if sprak == "en" and nyckel in ("brunnar", "cip") else "")), e(visad(url)))
            for nyckel, url in publika)
        rubrik, text = t["ingangarRub"], t["ingangarText"]
    else:
        rader = "".join(
            '<tr><td><code>%s</code></td><td><a href="http://%s:%s" target="_blank" '
            'rel="noopener"><code>http://%s:%s</code></a></td></tr>'
            % (e(namn), e(vard), e(port), e(vard), e(port))
            for namn, port in sorted(portar.items()))
        rubrik, text = t["nasRub"], t["nasText"]
    return (f'<div class="ruta" id="ingangar"><h3>{e(rubrik)}</h3><p class="meta">{e(text)}</p>'
            f'<table><tr><th>{e(t["kolKomponent"])}</th><th>{e(t["kolAdress"])}</th></tr>{rader}</table></div>')


# ---------------------------------------------------------------------------
# Hela sidan
# ---------------------------------------------------------------------------
def sida(steg, komponenter, portar, vard, troskel, publika=None,
         sprak="sv", variant="intern", utestangning=None):
    """Renderar kontrollrummet. `sprak` är sv eller en, `variant` extern eller
    intern (extern: inga portnummer och inga interna hänvisningar)."""
    if sprak not in SPRAK:
        sprak = "sv"
    t = TEXTER[sprak]
    antal = _antal_teknik(steg)
    # Samordnarens utestängning har knappar bara om den får användas: i den externa varianten är den avstängd (main.py,
    # UTESTANGNING_TILLATEN) och rutan visar ett inspelat exempel. `utestangning` sätts bara av tester som vill rendera den ena eller andra.
    aktiv_utestangning = (variant != "extern") if utestangning is None else utestangning
    panelerna = "".join(_panel(s, steg, komponenter, t, sprak, variant, aktiv_utestangning) for s in steg)
    js_texter = {k: t[k] for k in _JS_NYCKLAR}
    js_texter["helaListan"] = ORDTEXT[sprak]["helaListan"]
    js_ord = [{"id": o["id"], "term": o[sprak]["term"], "re": o[sprak]["re"],
               "cs": bool(o[sprak].get("cs")), "def": o[sprak]["def"]}
              for o in ORDLISTA]
    skript = (SKRIPT
              .replace("__TX__", json.dumps(js_texter, ensure_ascii=False))
              .replace("__ORD__", json.dumps(js_ord, ensure_ascii=False))
              .replace("__KODER__", json.dumps(i18n.KODER, ensure_ascii=False))
              .replace("__SPRAK__", sprak)
              .replace("__VARIANT__", variant))

    kropp = f"""
{_stegrad(steg, t, sprak)}
{_sidhuvud(t, sprak)}
<main>

<section id="kedjan" class="flik aktiv">
  {_intro(t, antal)}
  {_ordningsremsa(t)}
  {_bild(steg, t, sprak)}
  <div id="paneler">{panelerna}</div>
  {_ingangar(portar, vard, publika, t, sprak, variant)}
</section>
{_gamla_flikar(troskel, sprak)}
{_omsida(t, antal)}
{_ordlistesida(sprak)}

<footer>
  <p>{e(t['sidfot1'])} <a href="/statistik?lang={sprak}">{'Statistik' if sprak == 'sv' else 'Statistics'}</a> · <a href="/nyheter?lang={sprak}">{'Version' if sprak == 'sv' else 'Version'} <span id="demoversion">{e(DEMO_VERSION)}</span></a>{'' if variant == 'extern' else ' API: <a href="/api/status">/api/status</a> · <a href="/api/steg">/api/steg</a> · <a href="/api/audit">/api/audit</a> · <a href="/api/analys">/api/analys</a> · <a href="/api/kov">/api/kov</a> · <a href="/health">/health</a>'}</p>
  <p>{e(t['sidfot2'])} <span id="testlage" hidden></span></p>
</footer>
</main>"""

    sidan = (f"<!doctype html><html lang=\"{sprak}\"><head><meta charset=\"utf-8\">"
             "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
             f"<title>{e(t['h1'])}</title>"
             f"<style>{STIL}:root{{--rullhint:'{'↔ scroll sideways' if sprak == 'en' else '↔ dra i sidled'}'}}</style></head><body>{kropp}"
             f"<script>{skript}</script></body></html>")
    # Externa varianten: inga containernamn eller interna värdnamn i did:web på sidan (hård regel 4).
    return rensa.utan_containernamn(sidan) if variant == "extern" else sidan


# SVADA-loggan (svada_logo_240.png, nedskalad från
# vattendatalabbet.se) som data-URI, så att kontrollrummet inte hämtar något utifrån.
LOGGA_DATAURI = "data:image/png;base64,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"
