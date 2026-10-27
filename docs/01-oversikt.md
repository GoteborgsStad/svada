# 1. Översikt: vad Svada-mini är

Svada-mini är den förenklade SVADA-PoC:en: en körbar referensimplementation av
*Målarkitektur SVADA v1.9* där fokus ligger på **data space och på hur data används**. Den
följer dataprodukten **Modellerad bräddata** från DHI:s modell (Future City Flow, FCF), genom
ett riktigt dataspace mellan DHI och Göteborgs Stad, till att staden använder data för
analys och beslut. Ett produktionssystem är det avsiktligt inte –
[`08-drift-identitet-skalning.md`](08-drift-identitet-skalning.md) och
[`10-gapanalys.md`](10-gapanalys.md) beskriver vad som skiljer.

Allt körs lokalt i Docker Compose. Protokollen är riktiga: Dataspace Protocol (DSP), ODRL,
NGSI-LD och verifierbara intyg (DCP).

**Vad som inte ingår.** Sensorledet (MQTT, IoT-agent, råmätvärdeslagret) och dataportalerna
(CKAN, skördare, FAIR/MQA, DCAT-AP-SE-publicering) finns inte i Svada-mini. FCF läser brunn
SSO1_01-4526:s riktiga värden direkt ur CSV-filerna i `data/`, så data är oförändrat. Den
tidigare PoC:en med tio steg ingår inte heller.

## 1.1 Rollerna

| Roll | Organisation | Ansvar i PoC:en |
|---|---|---|
| Dataägare / Data Rights Holder | **KoV** (Kretslopp och Vatten) | Beslutar om åtkomst till Distribution A och kan häva avtalet |
| Dataproducent / provider | **DHI** (Future City Flow) | Modellen, provider-connector och KoV-spärren |
| Teknisk dataförvaltare (data custodian) | **Intraservice** | Driver stadens connector, plattform och avtalsregister |
| Consumer | **Staden** (Göteborgs Stad) | Tar emot, lagrar och använder data |
| Samordnare | **Svada** (DSGA 0.1) | Svadas utfärdare: medlems- och deltagarintyg (simulerad) |

## 1.2 Dataprodukten: två distributioner

Informationsklassningen (K/R/T = Konfidentialitet, Riktighet, Tillgänglighet) är inbyggd i
produkten:

| | Distribution A | Distribution B |
|---|---|---|
| Informationsklass | K1R1T1 | K0R1T1 |
| Innehåll | Fullständig, inklusive brunns-GIS | Brunns-GIS borttaget; utsläppspunkt och recipient kvar |
| ODRL-policy | `use` tillåtet, i 30 dagar från avtalets ingående (`inForceDate`); förbud mot `distribute`/`publish`; skyldigheter: KoV-godkännande och att mottagaren medger granskning (deklaration) | `use`/`distribute`/`publish` tillåtet mot attribution |
| Åtkomst hos staden | Kräver ett gällande avtal (stadens gateway nekar annars) | Öppen |

Det som tas bort i B är brunnens egen position (`location` och `sourceSrs` på postens
toppnivå). Koordinaten inuti `outlet` är utsläppspunktens och ska vara kvar.

## 1.3 Invarianterna

Systemet är byggt för att bevisa tre egenskaper. De testas om i varje regressionskörning:

1. **Suveränitet** – Distribution A lämnar aldrig providern utan KoV:s godkännande
   (verkställt i providerns kontrollplan), och går inte att läsa ur stadens plattform utan ett
   gällande avtal (stadens gateway nekar).
2. **Integritet i klassningen** – Distribution B innehåller aldrig brunnarnas GIS-position.
3. **Ett avtal gäller tills det hävs eller löper ut** – inte per datahämtning. Hävs avtalet nekar providern nya
   överföringar och staden slutar släppa in nycklar som hör till avtalet; statusen kontrolleras
   vid varje användning (stängt som standard).

## 1.4 Kedjan i sex steg

1. **Data finns hos DHI (FCF).** `fcf-sim` modellerar dygnet för alla 91 brunnar och
   framställer Distribution A och B. Modellen bygger på brunn 4526:s riktiga mätserie (CSV).
2. **DSP-katalogen.** `edc-provider` (DHI) annonserar båda distributionerna med varsin
   ODRL-policy.
3. **Avtal och KoV-beslut.** `edc-consumer` (staden) förhandlar kontrakt. B finaliseras
   automatiskt; A pausar hos providern tills KoV beslutat. KoV kan också häva ett avtal.
   Identiteten bevisas med verifierbara intyg (Svadas utfärdare, DHI:s och stadens
   IdentityHub).
4. **Leverans och kontroll.** Providerns dataplan pushar (HttpData-PUSH) till stadens
   `ingest-service`, som validerar mot avtalet innan något skrivs.
5. **Stadens plattform.** `orion-stad` (CIP) + Mintaka/TimescaleDB: 91 brunnar bär modellerad
   bräddata med proveniens (avtal, batch, distribution, klass). `stad-gateway` släpper bara
   ut A till den som har ett gällande avtal.
6. **Staden använder data.** Inspektionsprioritering: brunnarna rangordnas efter
   modellerad bräddvolym. Med B ser man vilka vattendrag som tar emot mest; med A (kräver
   gällande avtal) ser man vilka brunnar det gäller och kan lägga dem på en karta. Hävs
   avtalet slutar A-delen att fungera.

Tvärgående: **kontrollrummet** på `:38800` (läser och utlöser stegen, flyttar aldrig data
förbi kontraktet) och **stadens avtalsregister** (ODRL-ögonblicksbild och status per avtal,
synkad från DHI).

## 1.5 Organisationer, nät och compose-filer

Fyra compose-filer motsvarar rollerna. Docker-nätverk simulerar organisationsgränsen:
kontrollplanet (DSP) och publika endpoints korsar den. Nätet `<prefix>-dsp-public` är externt
och skapas av `starta-demo.sh`. **Ett undantag, medvetet:** stadens ingest-service läser en smal,
skrivskyddad avtalsstatus hos DHI (`/status/avtalsstatus` på port 19195, med en egen nyckel)
för att synka status till stadens avtalsregister. Staden har alltså inte DHI:s
management-nyckel. Pollningen är en PoC-förenkling (se G23); i drift ska statusen nå staden
genom protokollet eller en signerad statuslista.

| Compose-fil | Organisation | Nät |
|---|---|---|
| `compose.dhi.yml` | DHI (provider) | `dhi-internal` + `dsp-public` |
| `compose.stad.yml` | Göteborgs Stad (consumer) | `stad-internal` + `dsp-public` |
| `compose.dsga.yml` | Svadas utfärdare (samordningsrollen, DSGA 0.1) | `dsp-public` |
| `compose.kontrollrum.yml` | Kontrollrum och publik ingång (Caddy) | egna nät |

`fcf-sim` ligger med avsikt utanför `dsp-public`, så stadens sida når providerns dataplan
endast genom kontraktsledet. Providerns dataplan (port 19291) publiceras aldrig på värden.
Kontrollrummet ligger på eget nät och når komponenterna över värdens publicerade portar –
exakt det en människa kan nå med curl.

## 1.6 Komponentregister

| # | Container (prefix `svadamini-`) | Org | Port (intern → värd lokalt) | Roll |
|---|---|---|---|---|
| 1 | `fcf-sim` | DHI | 8050 → 38050 | Modell + batch + Distribution A/B + felinjektion; läser brunn 4526:s CSV |
| 2 | `edc-provider` | DHI | 19191–19194 (management på värden: 39193) | Kontrollplan: DSP-katalog, ODRL, KoV-spärr, hävning, transfer |
| 3 | `edc-consumer` | Staden | 29191–29194 (management på värden: 39393) | Kontrollplan: katalog, förhandling, transfer |
| 4 | `ingest-service` | Staden | 8060 → 38060 | Mottagning, avtalsvalidering, transformering, avtalsregister |
| 5 | `stad-gateway` | Staden | `ORION_STAD_PORT` | Åtkomstkontroll framför CIP:en; kontrollerar avtalsstatus vid varje användning |
| 6 | `orion-stad` (+ mongo) | Staden | intern | CIP – stadens kontextbroker |
| 7 | `mintaka` (+ timescale) | Staden | 8080 → 38083 | NGSI-LD temporal API (historik) |
| 8 | `publik-vy` | Staden | 8085 → 38085 | Distribution B:s läsbara webbvy |
| 9 | `dashboard` | – | 8800 → 38800 | Kontrollrummet, inklusive steg 6 |
| 10 | `identity-hub-svada` | Svada (DSGA 0.1) | 39595–39598 | Simulerad utfärdare av medlems- och deltagarintyg, med statuslista för återkallelse (medveten förenkling: inte eIDAS, listan i minnet) |
| 11 | `identity-hub-dhi` / `identity-hub-stad` | DHI / Staden | 39195–39198 / 39395–39399 | Egen IdentityHub per part: DID, nycklar, STS och partens eget rollintyg |
| 12 | `caddy` | – | 80/443 → 38080/38443 lokalt, 80/443 på servern | Publik ingång med lösenordsgrind (bara på publik demo) |

Värdportarna står i portkartan i `.env` (`*_PORT`); `verify_docs.sh` G kontrollerar att körbara exempel använder dem.

Engångsjobb körs med `run --rm`: `ladda-brunnar` (91 brunnar ur GeoPackage till CIP) och
`registrera-edc` (assets, policyer, kontraktsdefinitioner – **måste köras om efter varje
omstart av providern**).
