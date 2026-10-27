# C1. Identitet och tillit (mock-IAM → verifierbar identitet)

> Hela suveränitetsbeviset vilar på identitet – och i PoC:en är identiteten
> mockad. EDC kör `iam-mock`, management-API:erna går utan autentisering, och
> deltagar-id är strängar parterna själva påstår. Det är den medvetna
> förenkling som den verifierbara identiteten (verifierbara intyg via IdentityHub, DCP) tar bort.

Detta är en **tvärgående** förenkling som berör steg 5–7 och som gapanalysen
rankar som sitt enda **kritiska** gap (G1).

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Mock-IAM**, **connector**,
**Data Rights Holder**, **KoV-godkännande**. Verkställigheten som förlitar sig på
identiteten: [[06-kov-gate]] och [[05-dsp-odrl]].

## Vad problemet är

Målarkitektur v1.9 §6.5: *"deltagaridentitet och behörigheter uttrycks som
verifierbara attest (W3C Verifiable Credentials) ... och kontrolleras maskinellt
vid katalogåtkomst, förhandling och överföring. Minst tre attesttyper förutses:
identitet, medlemskap i dataområdet samt efterlevnad av specifika policyer."* §3.4
kräver att dataägarbeslutet fattas av en **namngiven** roll.

Mock-IAM är en uttrycklig, tidssatt förenkling: den markeras
`MEDVETEN FÖRENKLING – ersätts i …` i koden och ersätts med Keycloak eller EDC:s
DCP/IdentityHub.

## Hur PoC:en gör (och varför det är en förenkling)

EDC drar in modulen `org.eclipse.edc:iam-mock`, som utfärdar och godtar tokens
**utan verifiering**. `MockIamSeedExtension` lägger dessutom EDC:s officiella
samples-testnyckelpar i vaulten (publikt på GitHub – ger ingen säkerhet) så att
transfer-token-flödet fungerar. Deltagar-id är `dhi` respektive `stad`, satta i
konfigfilerna.

Konsekvenserna är två, och båda är verkliga:

1. **ODRL-constrainten `svada:deltagare eq "stad"`** ([[05-dsp-odrl]]) utvärderas
   mot en identitet som motparten själv påstår. Rätt *plats*, men inte bevisad *part*.
2. **KoV-godkännandet kan utlösas av vem som helst** som når port 19193 –
   `POST /management/kov/forhandlingar/{id}/godkann` kräver ingen identitet.
   Beslutet är därmed anonymt och kan inte knytas till Data Rights Holder-rollen.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `edc/src/main/java/se/goteborg/svada/edc/dcp/SvadaTransferProxyNyckelExtension.java` (döpt om från `MockIamSeedExtension`; en uppföljning bytte det hårdkodade nyckelparet mot ett runtime-genererat) | `SvadaTransferProxyNyckelExtension`, `initialize()` | Genererar numera ett RSA-nyckelpar slumpmässigt vid uppstart och lägger det i vaulten (BARA för dataplanets transfer-proxy-tokens, inte deltagaridentiteten – se "Läget efter nyckelskyddade API:er och DCP-identitet" nedan); loggar det vid start. |
| `edc/build.gradle.kts` | `implementation("org.eclipse.edc:iam-mock:…")` | Drar in mock-identitetsmodulen. |
| `edc/konfig/provider.properties` / `consumer.properties` | `edc.transfer.proxy.token.*.alias`, `edc.participant.id` | Pekar token-nycklar på mock-vaultens alias; ingen `management.auth.type`. |
| `edc/src/main/java/se/goteborg/svada/edc/odrl/DeltagareFunktion.java` | `evaluate()` | Utvärderar mot en identitet som aldrig verifieras. |

Markören `MEDVETEN FÖRENKLING – ersätts i …` sätts på varje ställe i `edc/` som är en kvarvarande förenkling.

## Läget efter nyckelskyddade API:er och DCP-identitet (2026-09-02)

Ovanstående beskriver läget FÖRE den verifierbara identiteten. Sedan dess: nyckelskyddade
management-API:er stängde management-API:erna bakom en delad nyckel, och verifierbar
DCP-identitet i stället för mock-IAM ersatte `iam-mock` helt med verifierbar DCP-identitet
via EDC:s IdentityHub – `did:web` per part, tre attesttyper, och `KovController` kräver numera
ett kryptografiskt verifierat `SvadaRoleCredential` innan ett KoV-beslut accepteras. Gapanalysens
G1 är därmed stängt. Den sista kvarvarande, medvetna förenklingen – dataplanets separata
transfer-proxy-token-signeringsnyckelpar (`SvadaTransferProxyNyckelExtension`, tabellen ovan),
en annan mekanism än dataspace-identiteten – är också stängd, i en fristående uppföljningscommit
efter att DCP-identiteten var klar: extensionen genererar numera ett RSA-nyckelpar slumpmässigt
vid varje uppstart i stället för det hårdkodade testnyckelparet. Testfall 8.4 (`grep "MEDVETEN
FÖRENKLING" edc/` ger 0 träffar) är därmed uppfyllt. Se
`docs/08-drift-identitet-skalning.md` §8.1 för migrationsanteckningarna.

## Utfärdarmodellen (utfärdare med rätt mandat)

DCP-identiteten gjorde DHI:s hub till utfärdare för hela dataspacet som en medveten
förenkling: den signerade alla sex intygen, även stadens. Det gav fel
ansvarsfördelning (en leverantör intygade stadens roller, en deltagare utfärdade
medlemskap). Utfärdarmodellen rättar det efter principen att **den som intygar något ska ha
mandat att intyga just det**. Den som verifierar godtar varje intygstyp bara
från rätt utfärdare.

| Funktion | Ansvarig | Driftas av | Lager |
| --- | --- | --- | --- |
| Stadens IdentityHub (DID, nycklar, intyg, STS) | Staden som deltagare | Intraservice, som del av förmågan | Förmåga |
| DHI:s IdentityHub | DHI som deltagare (datatillhandahållare i PoC-scenariot) | DHI | Förmåga, hos DHI |
| Utfärdare av medlems- och deltagarintyg | Svadas styrningsorgan (DSGA 0.1) | Intraservice på DSGA:s uppdrag, skild från stadens hub: egen DID, egna nycklar, egen konfiguration | Samordning |
| Rollintyg för staden (KoV är rättighetsinnehavare) | Staden, eftersom det gäller stadens interna rollfördelning | Stadens IdentityHub | Deltagande |
| Rollintyg för DHI | DHI själv | DHI:s IdentityHub | – |
| Identitetsintyg mot extern förankring (eIDAS, organisationsnummer) | Extern betrodd källa | – | Utanför PoC:en (gap) |

**Så är det byggt.** `identity-hub-svada` (`compose.dsga.yml`, samma image och
bootstrap-extension, `svada.credential.issuer=true`, egen DID
`did:web:identity-hub-svada%3A49197`) utfärdar `SvadaParticipantCredential` och
`SvadaMembershipCredential` åt DHI och Staden och exporterar dem till
utbytesvolymen (rw hos utfärdaren, ro hos de andra). Utfärdaren har inga egna intyg
och utfärdar inga rollintyg. DHI och Staden importerar intygen (och vägrar intyg
från någon annan än den konfigurerade utfärdaren, `svada.issuer.did`) och mintar
sitt EGET `SvadaRoleCredential` med den egna DID:en som utfärdare. Startordning:
svada, dhi, stad.

**Verifieringen per intygstyp.** EDC 0.17.0 kan begränsa en betrodd utfärdare till
vissa intygstyper: `edc.iam.trustedissuer.<alias>.supportedtypes` är en JSON-lista
(standard `["*"]`), och regeln `HasValidIssuer` avvisar ett intyg vars typ inte är
registrerad för utfärdaren (läst i källan på taggen v0.17.0). Därför räcker
konfiguration, utan egen utfärdarkontroll i `KovIdentitetsverifiering` eller
`DeltagareFunktion` (KoV-grinden verifierar via EDC:s egen `verifyJwtToken`):

* providern litar på Svada för medlems- och deltagarintyg och på staden bara för
  `SvadaRoleCredential` (`edc/konfig/provider.properties`),
* consumern litar på Svada för samma två typer och på DHI bara för
  `SvadaRoleCredential` (`edc/konfig/consumer.properties`).

Därmed kan staden inte utfärda giltigt medlemskap åt sig själv, och ett rollintyg
som Svada signerat avvisas, trots att texten är rätt. De två negativa testerna
8f3.6 och 8f3.7 (`tests/verify_ap8_fas3.sh`) visar det; de kör hubbarna i ett
testläge (`SVADA_TEST_NEGATIV`, av som standard) som bara finns för testet.

**MEDVETEN FÖRENKLING – simulerar DSGA 0.1:s tillitstjänst.** Inga intyg är
förankrade i eIDAS. Återkallelse finns (se nedan) men listan ligger i minnet. In-memory-lagring. Utfärdaren
körs som en container bredvid de andra; i målbilden driftas den av Intraservice på
DSGA:s uppdrag. Utanför PoC:en: MVP-topologin med en leverantörsconnector som staden
driftar (scenario 2 i WS4 är det PoC:en visar).

KONCEPT-ankare i koden: `identity-hub/src/main/java/se/goteborg/svada/identityhub/
SvadaParticipantBootstrapExtension.java` (klasskommentaren om utfärdarmodellen),
`compose.dsga.yml`, `edc/konfig/provider.properties` och `consumer.properties`
(`trustedissuer`).

### Återkallelse av intyg: samordnaren stänger ute en part (2026-10-11)

Svadas utfärdare håller en **bitsträngslista** (W3C Bitstring Status List, syfte `revocation`) i
`StatusLista.java`. Varje medlems- och deltagarintyg som utfärdaren ger någon annan bär ett
`credentialStatus`-fält (`BitstringStatusListEntry`: listans adress och intygets index).
Rollintygen (organisationens eget) och självutfärdade intyg gör det inte.

* **Publik del:** `GET /status/revocation/1` på utfärdarens DID-sammanhang (`StatusListPublik`)
  svarar med statuslisteintyget som en JWT, signerad med utfärdarens nyckel. Den signeras vid varje
  hämtning, så en ändrad bit syns direkt.
* **Samordnarens del:** `/svada-status` (`StatusListController`, nyckeln `SVADA_STATUS_ADMIN_KEY`)
  listar intygen och sätter eller rensar biten (`aterkalla`/`aterinsatt`). Bara samordningsrollen har
  mandat att återkalla; en deltagare kan inte återkalla en annans intyg.
* **Verifieringen:** connectorernas verifierare (EDC:s `IsNotRevoked`) hämtar listan
  (`edc.iam.credential.revocation.cache.validity=2000`, standard är 15 minuter) och nekar en
  presentation med ett återkallat intyg. Hos DHI ger det 401 mot staden: ingen katalog, inga
  nya avtal, ingen överföring. Återkallas DHI:s intyg avvisar staden DHI:s meddelanden, så ett
  nytt avtal kan inte ingås. Återinsättning ger full funktion utan omstart.
* **I kontrollrummet:** steg 3 har rutan *Samordnaren stänger ute en deltagare* i den interna varianten. **I den externa varianten är
  utestängningen avstängd (2026-10-20):** den stänger ute alla besökare samtidigt i en delad demo. Rutan visar då ett inspelat
  exempel, och `POST /api/svada/{mottagare}/{åtgärd}` ger 403 (`fel.utestangning_avstangd`) för anrop via Caddy; anrop direkt mot
  dashboardens port (testerna) berörs inte. Slås på igen med `DASH_UTESTANGNING=ja`. Funktionen finns kvar och prövas (återkallelse av intyg,
  `tests/skydd_integration.py` avsnitt 4 och 4b, fixturen i `tests/vy_handelser_webblasare.mjs`). Rollintygen kan inte återkallas
  (testfall 11.2b/e).

GOTCHA: en JAX-RS-klass med `@Path("/")` på samma sammanhang som IdentityHubs DID-resurs nås aldrig
(alla anrop svarar 204): JAX-RS väljer bara en rotklass per sökväg. Därför en rotklass per prefix
(`/status`, `/svada-status`).

Medveten förenkling: listan ligger i utfärdarens minne och index tilldelas vid start; inget
ansöknings- eller invändningsflöde (regelboken, G15); utfärdaren är inte förankrad i eIDAS.
Testas av `tests/verify_ap11.sh`.

## Bevis

Idag: `tests/verify_ap4a.sh` **4a.4** – markören finns (`grep "MEDVETEN
FÖRENKLING" edc/` ger ≥1 träff). Planerat (identitetsproven, `tests/verify_ap8_fas2.sh`):

* **8.1** – identitetstjänsten uppe (Keycloak eller DCP/IdentityHub).
* **8.2** – 4b.1–4b.3 + 4c.1 körs om med riktig identitet, gröna.
* **8.3** – **negativtest**: anrop utan giltig attest mot katalog, förhandling och
  transfer avvisas alla tre (401/403).
* **8.4** – mock borta: `grep "MEDVETEN FÖRENKLING" edc/` ger **0** träffar.

## Vägen till produktion

Ersätt mock-IAM med en lättviktig lokal
identitetslösning så att konfigurationen blir migrerbar. Målbilden (§6.5) är
verifierbara attest inom dataområdets tillitsramverk, integrerade med stadens IAM
och eIDAS. Detta är gapanalysens **G1 (kritisk)** – och en förutsättning för att
G10 (persistent, attribuerbar spårbarhet) ska bli meningsfullt.

Målarkitekturen delar själv upp vägen dit i två nivåer (§6.5, Figur 5), och den
uppdelningen är användbar för att prioritera arbetet:

* **Nivå 1 – bindande miniminivå, gäller redan under etablering:** ömsesidigt
  konfigurerade identiteter mellan kända parter, och **anonym åtkomst till
  kontrollplanets besluts- och förvaltningsfunktioner är otillåten** – även nu.
  PoC:en uppfyller inte ens detta: `KovController` och båda connectorernas
  management-API går helt utan autentisering.
* **Nivå 2 – målbilden:** deltagaridentitet och behörigheter som verifierbara
  attest (W3C Verifiable Credentials), utfärdade i ett tillitsramverk, med minst
  tre attesttyper (identitet, medlemskap i dataområdet, efterlevnad av policy).
  Det här är DSSC Blueprint/Dataspace Protocol-rekommendationen och det andra
  alternativet – DCP/IdentityHub – realiserar.

Rekommendationen nedan är att stänga nivå 1 som ett eget, billigt steg innan man
lägger arbete på nivå 2 – i dag brister PoC:en på den nivå som arkitekturen
kallar bindande *även under etablering*, inte bara på målbilden.

### Steg 1 – nå bindande miniminivå (billigt, gör snart)

Ingen VC behövs för det här steget, bara att sluta vara anonym:

| Åtgärd | Var | Vad det stänger |
|---|---|---|
| Delad hemlig API-nyckel per känd part, satt via `.env` (samma mönster som `STAD_GATEWAY_DRIFT_TOKEN` men konsekvent för alla management-API:er) | `edc/konfig/provider.properties` (`web.http.management.auth.*`), `edc/konfig/consumer.properties`, `KovController` | Anonym åtkomst till EDC:s management-API |
| Ett namngivet KoV-rollnamn i konfiguration (t.ex. `KOV_ROLLINNEHAVARE=Kretslopp och Vatten – <funktion>`), loggat med varje `godkann`/`avsla`-anrop | `KovController.beslut()`, `KovGate` | Arkitekturinvariant 4 (attribuerbarhet) – i dag loggas beslutet men inte vem/vilken roll som fattade det |
| Samma nyckelmönster på `atkomst.py`:s och `auktorisation.py`:s management-anrop | `services/stad-gateway/atkomst.py`, `services/ingest-service/auktorisation.py` | De sista två ställena där management-API går utan auth |

Det här tar inte bort `MEDVETEN FÖRENKLING`-markörerna (identiteten är
fortfarande en delad hemlighet, inte ett verifierbart attest – G1 stängs inte),
men det tar PoC:en till den nivå arkitekturen kräver *redan under etablering*,
och det är en dags jobb snarare än en ny tjänst.

### Steg 2 – verifierbara attest via Eclipse EDC:s DCP/IdentityHub (målbild)

Eclipse EDC (samma projekt, redan på 0.17.0) har ett companion-projekt,
**IdentityHub**, som implementerar Decentralized Claims Protocol (DCP) – DSSC
Blueprints rekommenderade väg. Skiss för en PoC-skalad, inte
produktionsskalad, uppsättning:

**Deltagare och identitetsteknik**

* En IdentityHub-instans per part (DHI, Staden) – inte den fulla
  referensuppsättningen (`eclipse-edc/MinimumViableDataspace`, som per part drar
  in Postgres + HashiCorp Vault plus delad Keycloak/Traefik/Issuer-tjänst; redan
  deras egen dokumentation kallar det "inte produktionsgrad" som demo, och det
  skulle sannolikt spränga laptop-minnesbudgeten i §8.2). I stället: IdentityHubs
  lättviktiga "basic launcher" med minnesbaserad lagring, samma princip som
  EDC-connectorernas in-memory stores (§3.3).
* DID-metod: `did:key` i stället för `did:web`. `did:web` kräver att
  DID-dokumentet går att slå upp över nätverk på en riktig domän/URL – fel
  passform för en enda-maskin-PoC. `did:key` är självbärande (identiteten *är*
  nyckeln) och kräver ingen resolver alls.
* Tillitsramverk/utfärdare: PoC:en har ingen tredje "dataspace authority"-part
  i dag. I stället för en full Issuer-tjänst: ett litet bootstrap-skript – i
  samma anda som `MockIamSeedExtension` i dag – som mintar och delar ut de
  nödvändiga VC:erna till båda parter vid uppstart. Det här är en medveten
  förenkling av bilaga 2:s tillitsramverk (en enda part spelar utfärdare åt
  båda), och ska märkas som sådan, inte döljas.

**De tre attesttyperna (§6.5 kräver minst detta)**

| Attest | Vad den intygar | Var den används |
|---|---|---|
| `SvadaParticipantCredential` | Deltagarens identitet (DHI respektive Staden), bunden till dess DID | Ersätter `context.participantAgent().getIdentity()` i `DeltagareFunktion` – `svada:deltagare eq "stad"` utvärderas mot ett verifierat DID i stället för en påstådd sträng |
| `SvadaMembershipCredential` | Medlemskap i SVADA-dataområdet | Kontrolleras vid katalogåtkomst och förhandling (DCP:s presentation-utbyte) |
| `SvadaRoleCredential` | Namngiven roll, t.ex. Data Rights Holder-funktionen hos Kretslopp och Vatten | `KovController` kräver denna innan `godkann`/`avsla` accepteras – detta är den delen som fullt ut stänger arkitekturinvariant 4, inte bara nyckelskyddets loggade rollnamn |

**Kodställen som berörs** (utöver de fyra som redan står i tabellen ovan i det
här dokumentet):

* `edc/build.gradle.kts` – byt `org.eclipse.edc:iam-mock` mot EDC:s
  identity-trust/DCP-moduler. *Exakta artefakt-koordinater för 0.17.0 måste
  verifieras i en spik innan kodning* – det här dokumentet ska inte gissa
  Maven-koordinater som fakta.
* `MockIamSeedExtension.java` tas bort helt (verifieringens testfall 8.4).
* `DeltagareFunktion.java` läser verifierad identitet från
  presentation-utbytet i stället för `participantAgent().getIdentity()` rakt av
  – exakt hur DCP exponerar det verifierade DID:et till policy-motorn hör också
  till spiken.
* `atkomst.py` och `auktorisation.py`: bytt ut slumptals-/delad-hemlighet-token
  mot att verifiera ett presenterat attest mot IdentityHub, i stället för att
  bara slå upp avtalet i egen EDC-connector.

**Nya komponenter, i linje med befintlig portkarta och resursbudget**

| Komponent | Org | Föreslagna portar | `mem_limit` (jfr §8.2:s spann 128 MiB–1 GiB) |
|---|---|---|---|
| identity-hub-dhi | DHI | 19195–19196 | 256–512m |
| identity-hub-stad | Staden | 29195–29196 | 256–512m |

Ingen ny långlivad container för utfärdaren om VC:erna mintas vid bootstrap
(samma mönster som dagens vault-seed) – annars ett kortlivat init-jobb, inte en
tredje ständigt körande tjänst.

**Negativtest (8.1–8.4, se `tests/verify_ap8_fas2.sh`)**

8.1 (tjänsten uppe), 8.2 (4b/4c om med riktig identitet), 8.3 (anrop utan
giltigt attest mot katalog/förhandling/transfer avvisas, 401/403) och 8.4
(mock-markören borta) håller som kontrakt oavsett uppdelning i nyckelskyddade API:er och DCP-identitet ovan
– DCP-identiteten är vad som faktiskt gör 8.1–8.4 gröna, nyckelskyddet gör bara PoC:en mindre
anonym på vägen dit.

### Öppna frågor innan kodning

1. Exakta EDC 0.17.0-modulnamn för DCP/identity-trust – kräver en kort spik mot
   `eclipse-edc/Connector` och `eclipse-edc/IdentityHub`, inte en gissning här.
2. `did:key` duger för en tvåparts-PoC, men bär inte vidare mot eIDAS-integrationen
   §6.5 nämner som senare federationssteg – det är avsiktligt utanför den
   verifierbara identitetens omfattning, inte en lucka i den här planen.
3. Om DCP-identiteten görs i sin helhet eller tidsboxas som en avgränsad spik: given
   resursbudgeten i §8.2 och att MVD-mönstret är för tungt, är en tidsboxad spik
   som bara byter ut EDC-sidans identitet (katalog + förhandling) ett rimligt
   första snitt, med `KovController`/`atkomst.py`/`auktorisation.py` som en andra
   omgång.

## Läs vidare

* Gotcha: `pipefail` + `grep -q` gjorde 4a.4-markörtestet falskt rött (SIGPIPE 141).
* Identitetsproven: `tests/verify_ap8_fas1.sh`, `verify_ap8_fas2.sh`, `verify_ap8_fas3.sh`. Relaterat: [[06-kov-gate]], [[05-dsp-odrl]].
