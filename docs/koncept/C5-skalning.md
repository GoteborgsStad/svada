# C5. Skalningen: från PoC till Sverige och EU

> Förhandlingen förblir bilateral mellan två connectorer även när dataområdet
> växer till nationell och europeisk nivå. Det som federeras är tilliten,
> upptäckten och regelverket. Detta dokument skissar ett troligt
> framtidsscenario, grundat på fakta i juli 2026.

**Ingång:** öppna skalningsbilden
[`skalning-sverige-eu.html`](skalning-sverige-eu.html) vid sidan av texten.
Den visar tre ringar: SVADA i produktion, ett svenskt vattendataområde och
EU-federationen – och markerar vad som korsar varje gräns.

*Detta är ett scenariodokument, till skillnad från koncepten 01–10 och C1–C4
som beskriver byggd och verifierad kod. Läs det som en karta över den
sannolika terrängen, med öppna frågor redovisade i slutet.*

## Begrepp

Kanoniska termer ur [`13-ordlista.md`](../13-ordlista.md): **connector**,
**kontrollplan**, **dataplan**, **Dataspace Protocol (DSP)**,
**Data Rights Holder**. Nya termer för skalningsnivån:

* **Dataområdesförvaltare** (data space governance authority) – organisationen
  som förvaltar dataområdets regelbok, antar deltagare och pekar ut
  tillitsankare. Beslutar om spelreglerna och står utanför enskilda affärer.
* **Regelbok** (rulebook) – dataområdets gemensamma regler: juridiska mallar,
  tekniska krav, semantiska standarder och tillitskrav (jämför Målarkitektur
  v1.9 bilaga 2).
* **Tillitsankare** – utfärdare av verifierbara attest (W3C Verifiable
  Credentials) som deltagarna kontrollerar maskinellt via Decentralized Claims
  Protocol (DCP).
* **Federerad katalog** – sökbar samling av deltagarnas metadata. Skördas; data ligger kvar
  hos källan. (Svada-mini har ingen sådan katalog; den tidigare PoC:en hade en.)
* **Dataförmedlingstjänst** (data intermediation service) – reglerad
  mellanhand enligt EU:s dataförvaltningsförordning (DGA) som kan driva
  connectorer åt andra. I Sverige registreras de hos Post- och telestyrelsen
  (PTS).

## Scenariots antaganden

Två antaganden ramar in dokumentet: SVADA är en framgång och konceptet är
accepterat på Sverigenivå, med flera leverantörer och konsumenter i Sverige
och EU. EU:s dataområden är samtidigt en framgång och används brett.
En professionell läsare av PoC ställer då två följdfrågor, och båda
förtjänar raka svar.

**Fråga 1: vem är den betrodda part som sköter förhandlingen på nationell
nivå och EU-nivå?**

**Fråga 2: hur byggs den tekniska integrationen när konsumenten ska hämta
datat över Sverige och EU?**

## Svar 1: förhandlingen får aldrig en mellanhand – tilliten federeras

Den intuitiva bilden av en nationell förhandlingscentral stämmer varken med
protokollet eller med EU:s regelverk. Dataspace Protocol är bilateralt:
förhandlingen går alltid direkt mellan providerns och consumerns connector,
och policyverkställigheten ägs alltid av den som tillhandahåller datat
(Målarkitektur v1.9 §6.2). Det gäller vid 2 deltagare och vid 2 000.

Jämför med webben. Ingen gemensam server utför världens krypterade
sessioner; varje webbläsare talar direkt med varje webbplats. Det som gör
samtalet möjligt är certifikatutfärdare som båda parter litar på. Dataområden
bygger på samma mönster. Den betrodda part läsaren letar efter finns, men den
har en annan arbetsuppgift än förhandling. Den delas upp i fyra roller:

1. **Dataområdesförvaltaren** förvaltar regelboken och beslutar vilka som
   får delta. För ett svenskt vattendataområde är detta en organisation som
   sektorn utser; kandidater diskuteras i öppna frågor nedan.
2. **Tillitsankaren** utfärdar attest: identitet, medlemskap i dataområdet
   och efterlevnad av specifika policyer (v1.9 §6.5 förutser just dessa tre).
   Varje connector kontrollerar motpartens attest maskinellt vid katalog,
   förhandling och överföring. Det ersätter PoC:ens mock-IAM ([[C1-identitet]]).
3. **Den federerade katalogen** gör erbjudanden sökbara över hela
   federationen. Den skördar metadata, och förhandlingen sker ändå direkt med
   den provider katalogposten pekar på. Sveriges dataportal och
   data.europa.eu arbetar redan så för öppna data.
4. **Dataförmedlingstjänsten** är det närmaste en förhandlande mellanhand
   regelverket känner. Enligt DGA får en registrerad förmedlare driva
   connectorer och förhandla **på uppdrag av** en deltagare, under neutralitets-
   och registreringskrav. Rådigheten flyttar aldrig: förmedlaren spelar samma
   roll som connector-operatören i stadens rollmodell – verkställer
   dataägarens beslut men fattar dem aldrig (v1.9 kap 3).

Punkt 4 är skalningens viktigaste operatörsmönster. Små kommuner och
VA-organisationer kommer sällan att drifta egna connectorer. De köper rollen
av en delad driftorganisation (i Göteborgsregionen finns mönstret redan:
Intraservice driftar åt staden, SOLTAK åt sina ägarkommuner) eller av en
registrerad dataförmedlingstjänst. Beslutet om varje delning ligger kvar hos
respektive Data Rights Holder, precis som KoV-gaten visar i PoC:en
([[06-kov-gate]]).

## Svar 2: integrationen är protokollet plus semantiken

Farhågan bakom fråga 2 är parvis integration: n deltagare ger n² kopplingar,
och det skalar aldrig. Dataområdets svar har två delar.

**Kontrollplanet är färdigintegrerat genom standarden.** Varje deltagare
ansluter en gång, till protokollet. DSP 2025-1 är första officiella utgåvan
och ligger hos ISO/IEC som DIS 26450; systerprotokollet DCP standardiseras
samma väg. EU-kommissionens program Simpl bygger dessutom gemensam öppen
programvara (Simpl-Open) som de sektorsvisa dataområdena förväntas använda
för just dessa funktioner. För SVADA betyder det: en connector som talar DSP
i dag talar med det som rullas ut i EU:s sektorsdataområden i morgon.

**Dataplanet skalar genom semantik.** Datat ligger kvar hos källan; det som gör en överföring användbar hos
mottagaren är gemensamma datamodeller och metadata. Här ligger Sveriges och
EU:s val redan fast, och SVADA:s val ligger i linje med dem:

| Lager | Standard i scenariot | SVADA i dag |
|---|---|---|
| Metadata för upptäckt | DCAT-AP (EU), DCAT-AP-SE 3.0.1 (Sverige) | Ingen separat metadatakatalog i Svada-mini; DSP-katalogen bär ODRL-erbjudandena ([[05-dsp-odrl]]) |
| Datamodell för nyttolast | Sektorsmodeller: Smart Data Models, OGC-standarder (till exempel SensorThings inom miljöområdet) | NGSI-LD + SewerOverflowWeir ([[02-ngsi-ld]]) |
| Villkor | ODRL-profiler definierade i regelboken | ODRL med SVADA-namnrymd ([[05-dsp-odrl]]) |
| Kvalitet | Dataproduktspecifikation + kvalitetsdeklaration per produkt | DPS och kvalitetsdeklaration enligt v1.9 kap 8 |
| Grunddata | Nationella grunddata via Ena; stabila identifierare | Betrodda källor-principen (v1.9 kap 5) |

Konsumentens tekniska arbete vid skalning blir därmed begränsat: anslut en
DSP-connector, läs dataproduktspecifikationen, ta emot enligt den avtalade
datamodellen. PoC:ens ingest-mönster – validera mot avtalet innan datat
skrivs till egna system ([[07-transfer-ingest]]) – är samma mönster varje
konsument i federationen behöver.

## Scenariot i tre ringar

**Ring 1: SVADA i produktion (cirka 2027).** Kedjan från PoC flyttar till
stadens drift. Gapanalysens lista blir arbetsordern: verifierbar identitet i
stället för mock-IAM (G1), TLS och certifikat över verkliga
organisationsgränser (G16), persistenta stores i stället för in-memory
([[C2-resursstrategi]]). Deltagarna är namngivna och få: DHI som provider,
staden som consumer, därefter Tjörn, SOLTAK-kommunerna och SMHI. Tilliten är
i detta skede ömsesidigt konfigurerad mellan kända parter, precis som v1.9
§6.5 beskriver etableringsskedet. KoV godkänner Distribution A-förhandlingar
via management-ytan, nu med autentiserad och attribuerbar identitet.

**Ring 2: ett svenskt vattendataområde (cirka 2028–2030).** Fler
VA-organisationer ansluter och tilliten formaliseras: en regelbok (utvecklad
ur SVADA:s Rulebook, v1.9 bilaga 2), en utsedd dataområdesförvaltare och ett
tillitsankare som utfärdar medlemskapsattest. Operatörsmönstret bär de små:
delade driftorganisationer och registrerade dataförmedlingstjänster kör
connectorer åt kommuner som saknar egen kapacitet. Den nationella
infrastrukturen och dataområdet kompletterar varandra: öppna distributioner kan skördas som i dag till Sveriges dataportal, grunddata
hämtas via Ena, och interoperabilitetslagen (prop. 2025/26:244) ger
offentliga aktörer skarpa krav på interoperabel datadelning som driver
anslutning. Digitaliseringsmyndigheten (från 1 januari 2027) och Nationella
Dataverkstaden är främjare och stöd; sektorn själv förvaltar dataområdet.

**Ring 3: EU-federationen (2030 och framåt).** Det svenska vattendataområdet
blir medlem i den gröna givens dataområde (Green Deal Data Space), vars
uppbyggnad pågår genom förberedelseprojekt som SAGE och AD4GD och vars
miljödata omfattar vatten. Medlemskapet är en federation av dataområden:
regelböcker erkänner varandras attest, kataloger skördar varandras metadata,
och en connector i Göteborg förhandlar direkt med en consumer i Rotterdam.
Hälsodataområdet EHDS (förordning (EU) 2025/327, i kraft sedan mars 2025)
visar slutläget för en sektor: ett dataområde med egen EU-förordning,
utpekade nationella organ och obligatorisk delning för vissa ändamål.
Vattensektorn kan vänta sig samma utveckling i mildare form via den gröna
givens regelverk, där rapporteringsflöden (till exempel enligt
avloppsdirektivet) blir naturliga dataprodukter.

## Vad PoC:en redan bevisar av scenariot

Scenariot står på mekanismer som PoC har verifierat i liten skala:

* **Bilateral förhandling utan mellanhand** – hela kedjan katalog, förhandling och överföring
  (`tests/verify_ap4a.sh`, `tests/verify_ap4b.sh`): katalog, förhandling och
  avtal direkt mellan två connectorer.
* **Policyverkställighet hos tillhandahållaren** – KoV-gaten svarar 200 på
  providern och 404 på consumern ([`C4-connector.md`](C4-connector.md)).
  Mönstret är oförändrat på EU-nivå.
* **Hävning och avtalsstatus hos staden** – ett avtal gäller tills det hävs och statusen
  kontrolleras vid varje användning ([[06-kov-gate]]); i federationen ska den spridas genom
  protokollet eller en statuslista.
* **Operatörsmönstret** – provider och consumer är samma programvara med
  olika konfiguration. Det är därför en driftorganisation kan köra många
  deltagares connectorer utan att röra deras mandat.
* **Semantisk interoperabilitet som förutsättning** – ingest-valideringen
  avvisar data som bryter mot avtalad modell. I federationen blir den
  kontrollen varje konsuments skydd.

## Vad som består och vad som ändras

| | PoC | Sverige/EU-scenariot |
|---|---|---|
| Förhandling | Bilateral över DSP | **Oförändrad** – bilateral över DSP |
| Policyverkställighet | Providerns kontrollplan (KoV-gaten) | **Oförändrad** – hos tillhandahållaren |
| Datats placering | Hos källan tills avtal finns | **Oförändrad** |
| Identitet | Mockad, självdeklarerad | Verifierbara attest från tillitsankare (DCP) |
| Upptäckt | En providers katalog | Federerade kataloger över dataområden |
| Deltagare | 2, hårdkodade | Många, antagna enligt regelbok |
| Drift | En laptop, docker-nät | Delade driftorganisationer och förmedlingstjänster |
| KoV-beslut | Manuellt per förhandling | Även attributbaserade förhandsgodkännanden (v1.9 §6.4) – beslutsrätten flyttar aldrig |
| Regelverk | Hårda regler i repot | Regelbok + DGA, Data Act, interoperabilitetslagen |

## Öppna frågor

Redovisas öppet eftersom scenariot står och faller med dem:

1. **Vem blir dataområdesförvaltare för svenskt vatten?** Kandidater finns
   (branschorganisation, myndighetssamverkan, konsortium ur SVADA), men
   frågan är oavgjord och avgörs av sektorn under fas 1–2.
2. **Finansieringen av federationstjänsterna.** Tillitsankare, katalog och
   regelboksförvaltning kostar; EHDS löser det med förordning och avgifter,
   vattensektorn saknar ännu motsvarande modell.
3. **Simpl kontra EDC i praktiken.** Båda talar DSP, och Simpl-Opens
   utvecklingsplan löper 2025–2026. Interoperabiliteten behöver ändå
   verifieras per version – ett naturligt PoC 3-tema.
4. **Juridiken kring maskinförhandlade avtal.** ODRL-policyn blir avtal i
   teknisk mening; regelbokens juridiska mallar avgör dess civilrättsliga
   bärighet. Här behövs stadens jurister tidigt.
5. **Data Act-effekten på leverantörsavtalen.** Förordningen (tillämplig
   sedan september 2025) stärker beställarens ställning kring data från
   upphandlade system – DHI-avtalets mönster bör omprövas mot den.

## Läs vidare

* [`C4-connector.md`](C4-connector.md) – connectorns anatomi; allt där
  gäller oförändrat i skalningen.
* [[C1-identitet]] – gapet mellan mock-IAM och attestbaserad tillit.
* [[06-kov-gate]] – avtalsstatus och hävning, som federationen måste sprida.
* Målarkitektur v1.9: kap 3 (rollmodellen), §6.4–6.5 (godkännanden,
  identitet), bilaga 2 (Rulebook).
* `docs/10-gapanalys.md` – G1 och G16 är scenariots ring 1-arbetsorder.

## Externa källor (kontrollerade 2026-07-27)

* [Dataspace Protocol 2025-1](https://eclipse-dataspace-protocol-base.github.io/DataspaceProtocol/2025-1/) och [ISO/IEC DIS 26450](https://www.iso.org/standard/93502.html)
* [Simpl-programmet, EU-kommissionen](https://simpl-programme.ec.europa.eu/) och [Simpl-Open utvecklingsplan 2025–2026](https://simpl-programme.ec.europa.eu/group/simpl-forum/discussion/simpl-open-development-roadmap-2025-2026)
* [Green Deal Data Space](https://green-deal-dataspace.eu/) samt förberedelseprojekten [SAGE](https://www.greendealdata.eu/) och [AD4GD](https://ad4gd.eu/)
* [EHDS, förordning (EU) 2025/327](https://www.european-health-data-space.com/) – sektorsdataområde med egen EU-förordning
* [Digg: samverkan för svenskt deltagande i europeiska dataområden (jan 2025)](https://www.digg.se/om-oss/nyheter/oppna-och-delade-data/nyheter/2025-01-14-samverkan-har-startat-for-okat-svenskt-deltagande-i-europeiska-dataomraden) och [Diggs uppdrag om samverkan kring data och AI (feb 2026)](https://www.digg.se/om-oss/nyheter/oppna-och-delade-data/nyheter/2026-02-06-digg-far-uppdrag-att-starka-samverkan-kring-data-och-ai)
* [Nationella Dataverkstaden, lägesrapport Q1 2026](https://internetstiftelsen.se/dataverkstaden/aktuellt/lagesrapport-fran-dataverkstaden-q1-2026/)
* [Nationella grunddata och Ena, Digg](https://www.digg.se/styrning-och-samordning/ena---sveriges-digitala-infrastruktur/nationella-grunddata)

---

*C5 v1, 2026-07-27. Scenariodokument; uppdateras när ring 1-beslut fattas.
Ankrat från `edc/konfig/consumer.properties` (operatörsmönstret) och listat i
konceptbibliotekets README. Synk verifieras av `tests/verify_docs.sh`.*
