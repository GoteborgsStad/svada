# 13. Ordlista – kanonisk terminologi

Detta är källan till sanning för ordval. När ett begrepp förekommer i
dokumentation och kod ska det skrivas likadant och betyda samma sak.
Definitionerna följer i första hand *Målarkitektur SVADA v1.9* (kapitel 2
och 11); PoC-specifika termer definieras här. Ett antal termer är
dessutom maskinellt låsta mot koden via `verify_docs.sh`
([`11-verifiering.md`](11-verifiering.md) §11.3).

## Roller och organisationer

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **DHI** | Dataproducent/provider. Driver Future City Flow och providerns connector. | `EDC_PROVIDER_ID=dhi` |
| **KoV** (Kretslopp och Vatten) | Rättighetsinnehavare (data rights holder), genom dataägaren. Beslutar om åtkomst till Distribution A. | – |
| **Intraservice** | Teknisk dataförvaltare (data custodian). Driftar stadens förmåga: CIP, consumer-connectorn, katalogen och stadens IdentityHub. Svada undviker termen data holder. | – |
| **Staden** | Consumer-sidan i PoC:en; Göteborgs Stad. | `EDC_CONSUMER_ID=stad` |
| **Rättighetsinnehavare** (data rights holder) | DSSC-rollen som äger användningsvillkoren. I SVADA = KoV, genom dataägaren. | `SVADA_KOV_ROLLINNEHAVARE` |
| **Utfärdare** (issuer) | Den som signerar ett intyg. I SVADA utfärdar **Svadas utfärdare** (samordningsrollen, DSGA 0.1) medlems- och deltagarintyg; rollintyg utfärdar organisationen själv. Medveten förenkling: simulerar DSGA 0.1:s tillitstjänst, inte förankrad i eIDAS. | `svada.credential.issuer`, `compose.dsga.yml` |
| **Återkallelse** (av intyg) | Samordnaren markerar ett medlems- eller deltagarintyg som återkallat i Svadas statuslista (Bitstring Status List). Verifierarna nekar sedan intygets innehavare: parten är utesluten tills intyget återinsätts. Skiljs från **hävning**, som gäller ett avtal. | `StatusLista.java`, `verify_ap11.sh` |
| **Rollintyg** | `SvadaRoleCredential`: intygar en organisations roll, utfärdat av organisationen själv (staden intygar KoV:s roll, DHI sin egen). KoV-grinden godtar det bara från stadens DID. | `SvadaRoleCredential` |
| **DSGA** | Data Space Governance Authority: Svadas styrningsorgan (version 0.1). Samordningsrollen som utfärdar medlemskap. | `identity-hub-svada` |

## Dataprodukten

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **Modellerad bräddata** | Dataprodukten. Tidsserier per bräddbrunn, två distributioner. | `modellerad-bradddata` |
| **Distribution A** | K1R1T1, full GIS, non-public, kräver KoV-godkännande, får ej spridas. | `modellerad-bradddata-a` |
| **Distribution B** | K0R1T1, brunns-GIS borttaget, öppna data. | `modellerad-bradddata-b` |
| **Informationsklassning (K/R/T)** | Stadens modell: Konfidentialitet/Riktighet/Tillgänglighet. | `informationClass` |
| **Bräddning** | Utsläpp av avloppsvatten till recipient när nätets kapacitet överskrids. | – |

## Kontrollplanet (DSP)

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **Kontrollplan** | Den domänoberoende delen: katalog, förhandling, policyverkställighet, överföringskoordinering. | – |
| **Dataplan** | Den domänspecifika delen där data lagras och tillgängliggörs (CIP, FCF). | – |
| **Dataspace Protocol (DSP)** | Standarden för katalog (DCAT), villkor (ODRL), förhandling och överföring mellan connectorer. | `EDC_DSP_VERSION=2025-1` |
| **DCAT** | Data Catalog Vocabulary, W3C:s standard för att beskriva datamängder och kataloger maskinläsbart. Dataprodukten beskrivs i DCAT i DSP-katalogen. DCAT-AP och DCAT-AP-SE är profiler som bygger på DCAT och används inte i demon. | `dcat:` i DSP-katalogen |
| **Verifierbart intyg (VC, Verifiable Credential)** | W3C:s standard: ett signerat intyg som bevisar vem en part är eller vilken roll den har. | `SvadaMembershipCredential`, `SvadaRoleCredential` |
| **Decentralized Claims Protocol (DCP)** | Protokollet för hur en part visar upp verifierbara intyg för en annan part utan en central tjänst. Demon använder det för medlemskap, deltagare och roller. | `SvadaDcpIdentityExtension` |
| **Connector** | Programvara som representerar en deltagare i dataområdet (EDC provider/consumer). | `edc-provider`, `edc-consumer` |
| **ODRL** | Maskinläsbara användningsvillkor: permission, prohibition, obligation. | `edc/bootstrap/policy-*.json` |
| **KoV-gaten** | Provider-sidig mekanism som pausar förhandlingen om Distribution A tills Data Rights Holder-beslut registrerats. | `KovGate` |
| **KoV-godkännande** | Data Rights Holder-beslutet som släpper A-förhandlingen. Deklareras i ODRL, verkställs av KoV-gaten. | `svada:kovGodkannande` |
| **Kontraktsförhandling** | DSP:s tillståndsmaskin: REQUESTED → … → FINALIZED/TERMINATED. | `contractnegotiations` |
| **Transfer** | Den auktoriserade dataöverföringen. I PoC:en HttpData-PUSH. | `HttpData-PUSH` |

## Dataplanet (CIP)

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **CIP** | City Information Platform – stadens context broker (`orion-stad`) + tidsserier. | `orion-stad` |
| **NGSI-LD** | ETSI-standardiserat API för kontextinformation (länkade data). | – |
| **Smart Data Models** | Öppet bibliotek av standardiserade NGSI-LD-datamodeller. | `SewerOverflowWeir` |
| **Proveniens** | Ursprungsmärkning på mottagen data: avtal, dataprodukt, distribution, tidpunkt. | `provenance` |
| **TRoE / temporal** | Temporal Representation of Entities – tidsseriehistoriken Mintaka exponerar. | `mintaka` |

## Avtal och användning

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **Hävning** | Ett avtal gäller tills det hävs. En hävning sker hos providern (KoV) och gör att nya överföringar och nycklar nekas. I PoC:en kan KoV häva direkt. Regeln att ett avslag av en ny begäran häver tidigare avtal för samma tillgång och part finns men är avstängd i den delade demon (`SVADA_KOV_AVSLAG_HAVARTIDIGARE=false`). DSP definierar ingen hävning av ett slutfört avtal. | `HavdAvtalSparr`, `/kov/avtal/{id}/hav` |
| **Avtalsregister** | Stadens kopia av avtalen: status (`GALLANDE`/`HAVT`/`OKAND`), ODRL-ögonblicksbild och löstbar adress. Statusen synkas från providern och kontrolleras vid varje användning (stängt som standard). | `services/ingest-service/avtalsregister.py` |
| **Inspektionsprioritering** | Steg 6: brunnarna rangordnas efter modellerad bräddvolym och de största pekas ut för inspektion. B är öppet; A kräver ett gällande avtal. | `services/dashboard/analys.py` |

## Tvärgående

| Term | Definition | Kanonisk i koden |
|---|---|---|
| **Mock-IAM** | Medveten förenkling: EDC kör `iam-mock` utan riktig identitet. Ersätts av verifierbar identitet (IdentityHub, DCP). | `MockIamSeedExtension` |
| **In-memory stores** | EDC:s lagring i minnet (ingen Postgres) – nollställs vid omstart. | – |
| **Arkitekturinvariant** | En av tre egenskaper som aldrig får brytas (suveränitet, integritet i klassningen, ett avtal gäller tills det hävs). | `tests/verify_*.sh` |

## Maskinellt låsta termer (synk-kontroll)

Direktiven nedan låser en term till en sträng som **måste** förekomma i
koden. `tests/verify_docs.sh` kontroll E grep:ar efter strängen; en
omdöpning i koden utan uppdaterad ordlista blir rött. Direktiven är
HTML-kommentarer och syns därför inte i renderad markdown.

<!-- SYNK: term="KoV-godkännande (ODRL-obligation)" strang="svada:kovGodkannande" -->
<!-- SYNK: term="KoV-godkännande (kodkonstant)" strang="ACTION_KOV_GODKANNANDE" -->
<!-- SYNK: term="KoV-gatens förlängningspunkt" strang="ContractNegotiationPendingGuard" -->
<!-- SYNK: term="KoV-gatens aktiveringsflagga" strang="svada.kov.gate.enabled" -->
<!-- SYNK: term="hävningsspärr i providern" strang="HavdAvtalSparr" -->
<!-- SYNK: term="deltagar-constraint" strang="svada:deltagare" -->
<!-- SYNK: term="Smart Data Model-typ" strang="SewerOverflowWeir" -->
<!-- SYNK: term="transfertyp" strang="HttpData-PUSH" -->
<!-- SYNK: term="avvisningsorsak (avtalsbrott)" strang="brunns-gis-i-distribution-b" -->
<!-- SYNK: term="dataSource för syntetiska serier" strang="modelled-synthetic" -->
<!-- SYNK: term="informationsklass A" strang="K1R1T1" -->
<!-- SYNK: term="informationsklass B" strang="K0R1T1" -->
<!-- SYNK: term="proveniens-attribut" strang="provenance" -->
<!-- SYNK: term="mock-IAM-markör" strang="MEDVETEN FÖRENKLING" -->
<!-- SYNK: term="betrodd utfärdare per intygstyp" strang="supportedtypes" -->
<!-- SYNK: term="utfärdarläge i IdentityHub" strang="svada.credential.issuer" -->
<!-- SYNK: term="EDC in-memory-BOM" strang="controlplane-base-bom" -->
