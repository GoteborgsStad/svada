# 9. Vad är ett data space? Från DSSC:s teori till SVADA PoC

**För dig som är informations- eller dataarkitekt** och kan SVADA:s
bakgrund och dataarkitektur i allmänhet, men möter EU Data Spaces för
första gången. Den här filen är en guide i tio steg: varje steg tar ett
begrepp ur teorin, visar hur SVADA PoC realiserar det – med faktiska
objekt ur det körande systemet – och pekar på koden för den som vill se
alla detaljer. Du behöver aldrig installera PoC:en för att följa guiden.

**Teorikällorna** är dessa publikationer från DSSC och FIWARE (de följer inte med i paketet; sök dem vid titeln):

| Dokument | Vad det är |
|---|---|
| *Summary of the DSSC Blueprint 3.0* (februari 2026) | Huvudkällan: EU:s gemensamma referensram för data spaces, ordnad i byggblock. Guiden nedan följer den |
| *DSSC Starter Kit for Data Space Designers 1.5* | Startpaket med checklistor för den som ska designa ett data space |
| *DSSC Data Space Design Principles* | Designprinciper tvärs över byggblocken |
| *DSSC Maturity Model V2* (september 2025) | Mognadsmodell med indikatorer för att bedöma var ett data space-initiativ står |
| *FIWARE for Data Spaces* (positionspapper, 2021) | Hur FIWARE-komponenter (NGSI-LD, context brokers) bär byggblocken – relevant eftersom PoC:ens dataplan är FIWARE |

DSSC (Data Spaces Support Centre) är EU-finansierat och förvaltar
referensramen. Kodhänvisningar (`services/…`, `edc/…`) pekar in i
repot; kapitelhänvisningar (kapitel 01–13) avser
dokumentationen i samma mapp, och §N.N avser *Målarkitektur SVADA v1.9*
(Göteborgs Stads arkitekturdokument; följer inte med i det här paketet).
Citat ur DSSC-dokumenten står på engelska med originalets ordalydelse.

---

## Steg 1: definitionen – och vad ett data space INTE är

Blueprintens definition:

> "Interoperable framework, based on common governance principles,
> standards, practices and enabling services, that enables trusted data
> transactions between participants."

Läs definitionen långsamt: den nämner ramverk, principer, standarder,
tjänster och transaktioner. Den nämner ingen plattform. Det är den
största begreppsförskjutningen för en dataarkitekt som är van vid
datalager och integrationsplattformar: **ett data space saknar gemensam
lagringsplats, med avsikt.** Datat ligger kvar hos den som
tillhandahåller det, tills ett maskinellt förhandlat avtal auktoriserar
en överföring direkt mellan två parter. Federationen består av
protokollet, tillitsramverket och spelreglerna.

**I PoC:en** syns det direkt i topologin: DHI:s data ligger i DHI:s
containrar, stadens i stadens, och det enda som korsar
organisationsgränsen är förhandlingsprotokollet och den avtalade
nyttolasten. Kapitel 01 ger överblicken i text.

## Steg 2: rollerna – vem är vem i SVADA

Blueprinten definierar deltagarklasserna Data Provider, Data Consumer,
Data Space Governance Authority och Service Provider – och betonar att
det är **roller**, inte organisationstyper. SVADA:s rollbesättning:

| DSSC-roll | I SVADA | Kommentar |
|---|---|---|
| Data Provider | **DHI** (Future City Flow) | Producerar dataprodukten, driver provider-connectorn |
| Data Consumer | **Staden** (Göteborgs Stad) | Tar emot, lagrar i CIP, publicerar vidare |
| Data Rights Holder (dataägare) | **KoV** (Kretslopp och Vatten) | Äger användningsvillkoren och beslutar om den känsliga distributionen |
| Data Space Governance Authority | **Saknas** | PoC:en har två deltagare konfigurerade av samma person; förvaltarrollen är ett känt gap (G15) |
| Service Provider / operatör | **Intraservice** (mönstret) | Teknisk dataförvaltare som driver connector och katalog åt staden – Blueprintens byggblock "Intermediaries and Operators" i miniatyr |

Lägg märke till Data Rights Holder-rollen: dataägaren och
dataproducenten är olika parter. Det är själva kärnan i SVADA-fallet –
KoV äger villkoren för data som DHI producerar och staden konsumerar –
och det är den rollfördelningen som resten av guiden bygger på.

## Steg 3: dataprodukten – "data sharing units"

Blueprintens definition av data product: *"Data sharing units, packaging
data and metadata, and any associated license terms."* Poängen med
paketeringen förklaras i byggblocket Data Space Offerings: att tänka
produkt i stället för data buntar ihop policyer, affärs- och
avtalsinformation, vilket gör livscykelhantering, kvalitetssäkring och
regelefterlevnad hanterbara.

**I PoC:en** är dataprodukten **Modellerad bräddata**, och paketeringen
är bokstavlig: produkten framställs i två distributioner med
informationsklassning och användningsvillkor inbyggda.

| | Distribution A | Distribution B |
|---|---|---|
| Innehåll | Full, med brunnarnas GIS-position | Brunns-GIS borttaget; utsläppspunkt och recipient kvar |
| Informationsklass | K1R1T1 | K0R1T1 (öppna data) |
| Villkor (ODRL) | använd, sprid aldrig, kräver KoV-godkännande | använd/sprid/publicera mot attribution |

En post ur Distribution B, ur det körande systemet – notera att
produkten bär sina egna deklarationer (`dataSource`, `syntheticScale`
redovisar att serien är syntetisk):

```json
{ "weirId": "SSO1_01-3552", "weirName": "Ruskvädersgatan", "recipient": "Göta Älv",
  "outlet": { "name": "G4", "location": { "type": "Point", "coordinates": [11.9893415, 57.6958130] } },
  "modelledDay": "2026-07-27", "overflowVolumeM3": 0, "inflowMeanM3S": 0.045565,
  "dataSource": "modelled-synthetic", "syntheticScale": 0.6409 }
```

**Koden:** `services/fcf-sim/distributioner.py` – `DIST_META` (klassen
per distribution), `bygg_poster()` (posterna i A-form) och `till_b()`
(B framställs genom att kopiera utan `KANSLIGA_FALT = ("location",
"sourceSrs")`). Fördjupning: kapitel 04.

## Steg 4: kontrollplan och dataplan – arkitekturens viktigaste snitt

Blueprintens byggblock Data Exchange drar det snitt hela tekniken vilar
på:

> "Whereas the data plane is often domain-specific (implementing a
> domain-specific data exchange protocol), the control plane is generic.
> … Exchanges between control planes of different parties shall use the
> data space protocol as a standard."

Kontrollplanet (katalog, förhandling, policyverkställighet,
överföringskoordinering) är alltså generiskt och standardiserat;
dataplanet (var datat bor och hur det hämtas) är domänspecifikt.
Programvaran som bär kontrollplanet är **connectorn** – Blueprintens
"participant agent". Dataspace Protocol (DSP) specificerar exakt vad två
connectorer säger till varandra: katalog med DCAT, villkor med ODRL,
förhandlingens tillståndsmaskin och överföringens koordinering.

**I PoC:en**: Eclipse EDC 0.17.0 spelar connector för båda parter –
samma programvara, olika konfigurationsfil. Dataplanet är
domänspecifikt precis som teorin säger: FIWARE/NGSI-LD (CIP hos staden,
Future City Flow hos DHI). Varje connector öppnar fyra API-ytor, och
bara DSP-ytan plus dataplanet korsar organisationsgränsen –
management-ytan (där besluten fattas) hålls alltid intern. Bilden
`bilder/connector-anatomi.png` är kartan.

**Koden:** `edc/konfig/provider.properties` och `consumer.properties` –
connectorns hela anatomi uttryckt som konfiguration
(`web.http.{management,protocol,control,public}`). Fördjupning:
kapitel 05, avsnitt 5.1.

## Steg 5: katalog och upptäckt – DSP-katalogen

Blueprintens byggblock Publication & Discovery rekommenderar DSP för
katalogutbytet, med DCAT-AP som syntax och ODRL för policyer. Byggblocket
Data, Services & Offerings Descriptions lägger grunden: maskinläsbar
metadata (DCAT/DCAT-AP) som låter en konsument bedöma innehåll, villkor
och teknisk åtkomst.

**I PoC:en** finns DSP-katalogen (EDC) som förhandlingsyta. Consumern begär den över
protokollet och får varje distribution med sin ODRL-offert – ett maskinellt erbjudande som
går att förhandla till avtal. En separat metadatakatalog för upptäckt (till exempel
DCAT-AP-SE-poster som skördas vidare till nationella och europeiska portaler) ingår inte i
Svada-mini; den fanns i den tidigare PoC:en med tio steg, som inte ingår i det här paketet.

**Koden:** `edc/bootstrap/registrera.py` (DSP-katalogens innehåll: asset + policy +
kontraktsdefinition per distribution). Fördjupning: kapitel 05.

## Steg 6: policyer och avtal – från juridik till ODRL

Två byggblock möts här. **Contractual Framework** (juridiken) delar
avtalen i tre nivåer: institutionella avtal (grunden, mellan förvaltaren
och deltagarna), datadelningsavtal (per transaktion, mellan provider och
consumer) och tjänsteavtal (för tjänsteleverantörer). **Access & Usage
Policies Enforcement** (tekniken) säger att policyer ska vara
maskinläsbara, rekommenderar ODRL och konstaterar varför:

> "Machine-readable policies enable automated contract negotiation for
> standard terms and automated enforcement during data access. This
> allows data spaces to scale without requiring manual review for every
> transaction."

Bryggan mellan nivåerna: **ODRL-policyn är datadelningsavtalets
maskinläsbara del.** Juristernas villkor översätts till permission,
prohibition och obligation, följer med i katalogens erbjudande, blir del
av det förhandlade avtalet och verkställs av kontrollplanet vid varje
transaktion.

**I PoC:en** är Distribution A:s offert exakt en sådan översättning –
tre juridiska villkor i maskinläsbar form:

```json
{ "@type": "Offer",
  "permission":  [ { "action": "use",
                     "constraint": [ { "leftOperand": "https://svada.goteborg.se/ns/deltagare",
                                       "operator": "eq", "rightOperand": "stad" } ] } ],
  "prohibition": [ { "action": "odrl:distribute" }, { "action": "odrl:publish" } ],
  "obligation":  [ { "action": "https://svada.goteborg.se/ns/kovGodkannande" } ] }
```

Rad för rad: endast Göteborgs Stad får ingå avtal; vidarespridning och
publicering är förbjudna (det är villkoret som hindrar att KoV:s data
når tredje part); och åtkomst kräver dataägarens godkännande.
Förhandlingen är DSP:s tillståndsmaskin (`REQUESTED → … →
FINALIZED/TERMINATED`), och det finaliserade avtalets id följer sedan
med datat hela vägen in i stadens plattform.

**Koden:** `edc/bootstrap/policy-distribution-a.json` och
`-b.json` (policyerna), `edc/src/main/java/se/goteborg/svada/edc/odrl/`
(`SvadaOdrlExtension` registrerar SVADA:s egna ODRL-termer,
`DeltagareFunktion` utvärderar deltagar-constrainten vid förhandling).
Fördjupning: kapitel 05, avsnitt 5.2.

## Steg 7: suveränitet – verkställd, inte utlovad

Blueprinten kräver att policyer verkställs i **alla** transaktionens
faser: publicering, upptäckt, förhandling och själva delningen. Det är
skillnaden mellan ett villkor som står i ett dokument och ett villkor
som inte går att bryta.

**I PoC:en** verkställs A-policyn i fyra led, av olika mekanismer:

1. **Vid förhandling – KoV-gaten.** En A-förhandling pausar i providerns
   connector (`pending: true`) tills dataägaren beslutat via providerns
   management-API. Beslutsknappen finns bara hos providern – consumerns
   connector saknar endpointen helt. Två anrop bevisar det: samma väg
   svarar 200 hos providern och 404 hos consumern. Konsumenten kan
   aldrig finalisera sin egen åtkomst.
2. **Vid mottagning – ingest-valideringen.** Stadens mottagning växlar
   avtal mot engångstoken och granskar leveransen mot avtalet innan
   något skrivs. En öppen leverans som smugglar brunns-GIS avvisas i sin
   helhet, med maskinläsbar orsak.
3. **Vid utlämning från stadens plattform – gatewayen.** Distribution A går bara att läsa
   med en nyckel som staden får genom att visa ett *gällande* avtals id; statusen
   kontrolleras vid varje användning.
4. **Vid hävning.** Ett avtal gäller tills det hävs. Hävs det nekar providern nya överföringar
   och gatewayen slutar släppa in nycklar som hör till avtalet.

Notera var grinden sitter: hos den som lämnar ut. Det följer av
protokollet – en grind hos mottagaren kan mottagaren öppna själv. Detta
är Blueprintens "data sovereignty" omsatt: dataägarens beslut, verkställt
i providerns kontrollplan.

**Koden:** `edc/src/main/java/se/goteborg/svada/edc/kov/KovGate.java`
(pausen, via EDC:s `ContractNegotiationPendingGuard`),
`services/ingest-service/validering.py` (mottagningskontrollen),
`services/ingest-service/avtalsregister.py` och `services/stad-gateway/atkomst.py`
(avtalsstatus vid varje användning). Fördjupning: kapitel 05, avsnitt 5.3–5.4.

## Steg 8: identitet och tillit – teorins krav, PoC:ens ärliga mock

Blueprintens byggblock Identity & Attestation Management är entydigt:
data spaces behöver minst tre typer av verifierbara attest – identitet,
medlemskap i dataområdet och efterlevnad av policyer – enligt W3C
Verifiable Credentials, utbytta via protokoll som DCP eller OpenID4VC.
Tillitsramverket pekar ut tillitsankare: auktoritativa utfärdare som
alla litar på.

**I PoC:en är exakt detta mockat, med avsikt och öppet redovisat.** EDC
kör `iam-mock`, deltagar-id är självdeklarerade strängar och
management-API:erna går utan autentisering. Konsekvensen är ärligt
formulerad i gapanalysen: PoC:en bevisar att dataägarbeslutet verkställs
på rätt *plats*, men aldrig att det fattas av rätt *part*. Det är det
enda kritiska gapet (G1), markören `MEDVETEN FÖRENKLING` står på 14
ställen i koden, och den verifierbara identiteten (verifierbara intyg via IdentityHub, DCP) ersätter mocken med
Keycloak eller EDC:s DCP/IdentityHub – med färdigt testkontrakt.

För en arkitekt är lärdomen dubbel: identiteten är ett eget byggblock
som connectorn *konsumerar* (därför gick den att mocka utan att katalog
och förhandling slutade fungera), och samtidigt vilar hela
suveränitetskedjan på den. Teorin och PoC:en säger samma sak från var
sitt håll.

**Koden:** `edc/src/main/java/se/goteborg/svada/edc/MockIamSeedExtension.java`.
Fördjupning: kapitel 08, avsnitt 8.1.

## Steg 9: proveniens, spårbarhet och observerbarhet

Blueprintens byggblock skiljer tre förmågor: **proveniens** (bakåt –
varifrån kom datat?), **spårbarhet** (hela vägen – hur hanterades det
och av vem?) och **observerbarhet** (förstå beslut och utfall). Syftet
är förtroende, ansvarsutkrävande och tvistlösning.

**I PoC:en** bär varje mottagen entitet i stadens plattform ett
`provenance`-attribut – svaret på "under vilket avtal kom det här värdet
in?" står på datat självt:

```json
{ "contractAgreementId": "ef838802-c333-4392-b328-d95b1d99bc72",
  "dataset": "Modellerad bräddata", "distribution": "B",
  "batchId": "batch-005-2026-06-17",
  "informationClass": "K0R1T1", "accessRights": "public",
  "license": "CC BY 4.0",
  "receivedVia": "Eclipse EDC transfer (Dataspace Protocol)" }
```

Avtals-id:t knyter ihop kontraktet, mottagningskvittot och datat – hela
tråden går att följa i kapitel 07. Spårbarheten i övrigt är däremot en
demonstration och inget register: kontrollrummets auditlogg byggs vid
läsning och överlever ingen omstart (G10). Blueprintens fråga "how will
the logs be stored securely, and who can access them?" har alltså inget
svar i PoC:en ännu – och den hänger ihop med steg 8, för en logg utan
verifierade identiteter duger ändå inte för tvistlösning.

**Koden:** `services/ingest-service/ngsild.py` (`bygg_proveniens()`).
Fördjupning: kapitel 06, avsnitt 6.1.

## Steg 10: det som ligger utanför tekniken – och avgör

Blueprintens fem sammanfattande regler för varje data space:

1. En **rulebook** som dokumenterar alla regler och tillitsramverket.
2. En **governance authority** som förvaltar rulebooken.
3. Data modelleras som **data products** och delas via kataloger.
4. Avtal fångas i **data sharing contracts**.
5. **Använd standarderna** – lägg energin på det domänspecifika.

SVADA PoC mot de fem reglerna: regel 3 är bevisad (dataprodukten med
inbyggd klassning), regel 4 är tekniskt bevisad (ODRL-avtal förhandlas
och verkställs) med juridiken kvar att knyta, regel 5 är följd rakt
igenom (DSP, ODRL, NGSI-LD – all utveckling ligger i
det domänspecifika: klassningen, KoV-gaten, VA-modellen). Regel 1 och 2
återstår, och det är ett medvetet läge: en teknisk PoC kan aldrig utse
en dataområdesförvaltare eller skriva spelreglerna – det är
verksamhetsarbete (G15), och arkitekturens egen slutsats är att
styrning, roller och kvalitetsarbete avgör framgången mer än tekniken.

Här kommer de övriga teorikällorna in när SVADA tar nästa steg:
*Starter Kit* för designfrågorna och checklistorna, *Maturity Model* för
att lägesbedöma initiativet, *Design Principles* för vägvalen tvärs
över byggblocken. Skalningsbilden – vad som federeras när fler parter
ansluter och varför förhandlingen förblir bilateral – står i kapitel 08,
avsnitt 8.4.

---

## Kartan: DSSC:s byggblock mot SVADA PoC

Blueprintens tolv byggblock, radade mot implementationen. Kolumnen
"Läge" använder tre ord: *bevisat* (byggt och regressionstestat),
*mockat* (medveten förenkling med plan) och *återstår* (utanför PoC:ens
avgränsning).

| DSSC-byggblock | I SVADA PoC | Kod / kapitel | Läge |
|---|---|---|---|
| Business model | Utanför PoC:en; nyttan pekades ut i workshop 1 (avvikelselarmet) | kapitel 03 | Återstår |
| Use case development | Bräddbrunnsfallet: mätning → modell → delning → EU | kapitel 01 | Bevisat som fall |
| Data space offerings | Dataprodukten Modellerad bräddata, två distributioner | `services/fcf-sim/` · kapitel 04 | Bevisat |
| Intermediaries & operators | Intraservice-mönstret: operatör som driver connector åt deltagaren | kapitel 08 §8.4 | Mönstret visat |
| Organisational form & governance authority | Ingen förvaltare utsedd | G15 · kapitel 10 | Återstår |
| Participation management | Två hårdkodade deltagare | `.env` | Återstår |
| Regulatory compliance | Utanför PoC:en (dataförordningen med flera berörs i kapitel 08) | kapitel 08 §8.4 | Återstår |
| Contractual framework | ODRL som datadelningsavtalets maskinläsbara del; nivåerna ovanför saknas | `edc/bootstrap/` · G15 | Delvis |
| Data models | NGSI-LD + `SewerOverflowWeir` (lokal modell, G7) | `services/ladda_brunnar/` | Bevisat, med känt gap |
| Data exchange | DSP 2025-1 mellan kontrollplanen; HttpData-PUSH på dataplanet | `edc/` · kapitel 05 | Bevisat |
| Provenance, traceability & observability | Proveniens på varje entitet; auditlogg som vy | `services/ingest-service/` · G10 | Delvis |
| Identity & attestation + trust framework | Mock-IAM; verifierbara intyg via IdentityHub/DCP | `MockIamSeedExtension.java` · G1 | Mockat |
| Access & usage policies enforcement | ODRL + KoV-gate + ingest-validering + gateway + hävning | `edc/src/…/kov/` · kapitel 05 | Bevisat |
| Publication & discovery | DSP-katalog (ingen separat metadatakatalog i Svada-mini) | `edc/bootstrap/` | Delvis |
| Value creation services | Inspektionsprioritering i steg 6 (en enkel demonstration av användning) | `services/dashboard/analys.py` | Demonstration |

Läst som helhet ger tabellen samma bild som gapanalysen: tekniken i
mitten är bevisad, kanterna – identitet, styrning, juridik – är
nästa arbete. Det stämmer med Blueprintens egen ordning: byggblocken för
affär, styrning och juridik står först i boken.

## Läs vidare

I den här mappen: kapitel 01 (överblicken), 05 (dataområdet i detalj),
07 (följ ett värde, med alla API-svar), 08 (identitet, drift, skalning),
10 (gapanalysen). Av teorikällorna: börja med
Blueprint-sammanfattningen, ta *Starter Kit* när designdiskussionerna
startar.
