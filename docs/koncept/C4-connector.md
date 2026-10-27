# C4. Connectorn: organisationens ombud i dataområdet

> En connector är programvaran som företräder en organisation i ett dataområde.
> Den gör fyra saker: annonserar dataprodukter i en katalog, förhandlar kontrakt,
> verkställer användningsvillkor och auktoriserar överföringar. Den som ska
> driftsätta en behöver framför allt veta **vilken API-yta som exponeras åt vem**.

**Ingång:** öppna anatomibilden
[`connector-anatomi.html`](connector-anatomi.html) vid sidan av den här
texten. Den visar tre nivåer: dataområdet (federationen), connectorns fyra
funktioner och de fyra API-ytorna. Texten fyller i kartan nivå för nivå.

## Förklaringen på en minut

EU:s datastrategi bygger dataområden (data spaces): federationer där
organisationer delar data och behåller rådigheten över dem. Ett dataområde
saknar gemensam dataplattform. Datat ligger kvar hos den som tillhandahåller
det, tills ett maskinellt förhandlat avtal auktoriserar en överföring direkt
mellan parterna.

Connectorn är den programvara varje deltagare kör för att vara med. Den är
deltagarens tekniska ombud utåt: den visar upp organisationens erbjudanden,
förhandlar villkor med motpartens connector och släpper igenom en överföring
först när avtalet finns. Själva datat tar en annan väg, dataplanet, och
passerar aldrig förhandlingen. Diplomatin och godset går skilda vägar.

Det är hela idén. Resten av dokumentet förklarar vad ombudet består av, vad
EU-nivån har standardiserat, vilka missförstånd som brukar ställa till det och
hur PoC bevisar varje påstående med körbar kod.

## Begrepp

Kanoniska termer ur [`13-ordlista.md`](../13-ordlista.md):

* **Connector** – programvaran som representerar en deltagare i dataområdet
  (`edc-provider`, `edc-consumer`).
* **Kontrollplan** – den domänoberoende delen: katalog, förhandling,
  policyverkställighet, överföringskoordinering.
* **Dataplan** – den domänspecifika delen där data faktiskt tillgängliggörs.
* **Dataspace Protocol (DSP)** – standarden connectorer talar med varandra.
* **Kontraktsförhandling** – DSP:s tillståndsmaskin (REQUESTED → … →
  FINALIZED/TERMINATED).
* **ODRL** (Open Digital Rights Language) – maskinläsbara användningsvillkor.

## Vad EU-nivån har bestämt

Frågan "vad är en connector?" har fått ett skarpare svar under 2025–2026,
eftersom protokollet mellan connectorer nu är formellt standardiserat.

**Dataspace Protocol definierar connectorn.** DSP specificerar exakt vad två
connectorer säger till varandra: hur en katalog begärs och besvaras (med W3C:s
katalogvokabulär DCAT, Data Catalogue Vocabulary), hur villkor uttrycks (ODRL),
hur kontraktsförhandlingens
tillståndsmaskin fortskrider och hur en överföring koordineras. Version 2025-1
är den första officiella utgåvan, förvaltad av Eclipse Dataspace Working Group,
och har lämnats in till ISO/IEC för global standardisering (ISO/IEC DIS 26450).
Systerprotokollet Decentralized Claims Protocol (DCP) standardiseras samma väg
och täcker identitetsdelen: verifierbara attest enligt W3C Verifiable
Credentials.

**Connectorn är därmed en roll, definierad av ett protokoll.** Jämför med
"webbserver": ordet pekar ut vad programvaran gör i ett standardiserat samtal,
och flera produkter kan spela rollen. IDSA:s (International Data Spaces
Association) connectorrapport från juni 2026 listar ett stort antal
implementationer som talar DSP. Eclipse Dataspace Components (EDC) är den
referens som flest EU-initiativ bygger på, bland andra Catena-X; alternativ
finns från bland andra FIWARE- och Sovity-hållet. Målarkitektur v1.9 §6.1 drar
konsekvensen: arkitekturens åtagande ligger på protokollnivå, och varje
komponent som implementerar DSP kan ersätta EDC.

**DSSC:s byggblock placerar connectorn.** I Data Spaces Support Centres
blueprint realiserar connectorn byggblocken för datautbyte (Data Exchange) och
delar av avtalshanteringen, medan identitet och tillit är egna byggblock som
connectorn förlitar sig på. Det stämmer med PoC:ens erfarenhet: identiteten
([[C1-identitet]]) är en egen fråga som connectorn konsumerar, och den går att
mocka utan att katalog och förhandling slutar fungera – vilket samtidigt är
PoC:ens största medvetna förenkling.

## Fem vanliga missförstånd

Diskussionen om connectorer fastnar ofta i samma feltankar. Här är de fem
vanligaste, med det korrekta svaret efter varje.

**1. "Connectorn är en produkt man köper."** Connectorn är en roll i ett
protokoll. Produkter som EDC implementerar rollen, och provider och consumer
är i sin tur roller inom protokollet. I PoC kör båda parter samma EDC-image;
skillnaden är en konfigurationsfil.

**2. "Datat går genom förhandlingen."** Kontrollplanet utbyter metadata,
villkor och tillstånd. Datat går på dataplanet, direkt mellan parternas
system, och först när avtalet finns. Kontrollplanet bär aldrig nyttolasten.

**3. "Dataområdet har en gemensam plattform som samlar datat."** Varje
deltagare kör sin egen connector, och data ligger kvar hos källan tills ett
avtal auktoriserar en överföring mellan två parter. Federationen består av
protokollet och tillitsramverket. En gemensam lagringsplats saknas, med avsikt.

**4. "Connectorn lagrar och förädlar data."** Connectorn koordinerar. Lagring,
transformation och tillgängliggörande hör hemma i dataplanet – i SVADA:s fall
CIP (City Information Platform) på stadens sida och Future City Flow på
leverantörens. Den som väntar sig
en integrationsplattform med formatkonvertering och kögarantier tittar på fel
komponent.

**5. "En connector är en tjänst med ett API."** En connector öppnar flera
API-ytor med olika publik och olika förtroendekrav. Endast DSP-ytan och
dataplanet vetter mot omvärlden. Detta är den operativa kärnfrågan vid
driftsättning, och resten av dokumentet handlar om den.

## Vad problemet är

Målarkitektur v1.9 §6.1 föreskriver att **två organisationers kontrollplan
kommunicerar över DSP**, och §6.2–6.4 att den tillhandahållande partens
kontrollplan äger policyverkställigheten. Komponentplan §2 pekar ut EDC som
referensrealisering (komponent 6 provider, komponent 7 consumer).

Den fråga arkitekturen lämnar öppen i prosa, men som varje driftorganisation
ställer först, är: *vilka portar öppnar vi åt vilket håll?* "Connector" låter
som en enda tjänst. I själva verket är den flera API-ytor, och den vanligaste
feltanken (nummer 2 ovan) kommer av att man missat att kontrollplan och
dataplan är skilda vägar.

## Hur PoC:en visar det

Både `edc-provider` och `edc-consumer` byggs från **samma EDC-image** (`edc/`,
`controlplane-base-bom`). Skillnaden är konfigurationen:
`edc/konfig/provider.properties` respektive `consumer.properties`, som öppnar
exakt fyra HTTP-kontexter. Portarna följer portkartan (`.env`); providern ligger på 191xx och consumern speglar på 291xx.

| Yta (`web.http.*`) | Provider-port | Vem talar hit | Korsar org-gränsen? |
|---|---|---|---|
| **Management** (`/management`) | 19193 | Deltagarens **egna** appar och operatörer – registrerar assets/policyer, startar förhandlingar, och här sitter **KoV-godkännandet** (hård regel 7) | Nej – internt |
| **DSP/protocol** (`/protocol`) | 19194 | **Motpartens connector**, över Dataspace Protocol | **Ja – enda kontrollplansytan som korsar gränsen** |
| **Control** (`/control`) | 19192 | Connectorns egna komponenter (kontrollplan ↔ dataplan) | Nej – internt |
| **Default/observability** (`/api`) | 19191 | Health och drift-metrik | Nej – internt |

Därtill kommer dataplanets publika kontext (`/public`, 19291), den enda väg
**datat** tar. Poängen som ska fastna: **det enda som passerar
organisationsgränsen är DSP-porten (förhandling) och dataplanet (nyttolast).
Management-ytan hålls alltid stängd utåt.** Att öppna 19193 mot omvärlden vore
att ge vem som helst rätten att godkänna Distribution A.

Förhandlingen på DSP resulterar i ett avtal; själva överföringen sker på
dataplanet (`HttpData-PUSH` till `ingest-service`, se [[07-transfer-ingest]]),
och `accessURL` pekar alltid tillbaka på stadens endpoints (hård regel 8).

**Var suveräniteten sitter.** ODRL-policyn följer med i DSP-katalogens offert,
blir del av avtalet och verkställs vid varje transaktion ([[05-dsp-odrl]]).
KoV-gaten är SVADA:s egen utbyggnad av providern
(`ContractNegotiationPendingGuard`) och exponeras *bara* på providerns
management-yta – därför att policyverkställighet enligt DSP ägs av den som
tillhandahåller data ([[06-kov-gate]]). Detta är dataområdets svar på stadens
skall-krav att dataägaren ansvarar för användningsvillkoren: beslutet fattas av
Kretslopp och Vatten (KoV) i rollen Data Rights Holder, och tekniken hindrar
consumern från att finalisera sin egen åtkomst.

## Koden

| Fil | Symbol / nyckel | Ansvar |
|---|---|---|
| `edc/konfig/provider.properties` | `web.http.{protocol,management,control,public}.*` | Definierar de fyra API-ytorna + dataplanet. Connectorns anatomi i konfig. |
| `edc/konfig/consumer.properties` | samma nycklar, 291xx | Samma image, consumer-roll – speglar ytorna, saknar `svada.kov.gate.enabled`. |
| `edc/build.gradle.kts` | `controlplane-base-bom` | BOM:en som avgör vilka EDC-moduler (och därmed ytor) connectorn får. |
| `edc/src/main/java/se/goteborg/svada/edc/kov/KovGateExtension.java` | `KovGateExtension` | Registrerar KoV-gaten + dess endpoints på management-ytan – bara när flaggan är på. |
| `edc/src/main/java/se/goteborg/svada/edc/odrl/SvadaOdrlExtension.java` | `SvadaOdrlExtension` | Registrerar constraint-/obligation-utvärderarna som verkställs vid förhandling. |
| `edc/src/main/java/se/goteborg/svada/edc/dcp/SvadaDcpIdentityExtension.java` (ersätter den tidigare `MockIamSeedExtension`) | `SvadaDcpIdentityExtension` | Identitetsdelen – verifierbar DCP-identitet (se [[C1-identitet]]), inte längre mockad. |

## Bevis

`tests/verify_ap4a.sh` prövar connectorns tre synliga ytor:

* **4a.1** – båda connectorernas health-yta (`/api/check/health`) rapporterar
  `isHealthy`.
* **4a.2** – DSP-ytan: consumern frågar providerns katalog över DSP och får en
  `dcat:Catalog` med ODRL-offert.
* **4a.3** – dataplanet: assetets `dataAddress` pekar på fcf-sim, och providern
  hämtar Distribution B den vägen.

Kör själv – de fyra ytorna, var för sig:

```bash
# DSP-ytan (19194): versionshandskakningen motpartens connector gör först
curl -s http://localhost:39194/protocol/.well-known/dspace-version
# -> {"protocolVersions":[{"version":"2025-1","path":"/2025-1","binding":"HTTPS"}]}

# Observability-ytan (19191): drift
curl -s http://localhost:39191/api/check/health        # -> "isSystemHealthy": true

# Management-ytan: KoV-kön finns på PROVIDERN …
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:39193/management/kov/forhandlingar  # 200
# … och saknas på consumern (hård regel 7 – ingen väg runt gaten)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:39393/management/kov/forhandlingar  # 404
```

De två sista raderna är hela suveränitetspoängen på två curl: samma image, men
beslutet om Distribution A kan bara fattas där datat tillhandahålls.

## Förenkling → produktion

* **Identiteten är mockad** (gapanalysens G1, [[C1-identitet]]). Management-ytan
  saknar autentisering och deltagar-id är en självdeklarerad sträng
  (`MEDVETEN FÖRENKLING`). I skarp drift gäller verifierbara attest (W3C
  Verifiable Credentials) via DCP/IdentityHub eller Keycloak, kontrollerade vid
  katalog, förhandling och överföring. Det är förutsättningen för att DSP-ytans
  motpart *är* den den utger sig för.
* **Organisationsgränsen är simulerad** (gapanalysens G16). PoC:en saknar TLS,
  certifikat och brandvägg mellan ytorna; allt är docker-nät på en maskin. I
  produktion är tabellen ovan säkerhetsdesignen: DSP + dataplan öppnas
  kontrollerat utåt, management/control hålls interna.
* **In-memory stores** ([[C2-resursstrategi]]): assets, policyer, avtal och
  KoV-beslut överlever ingen omstart – därför `registrera-edc` efter varje
  providerstart.

## Läs vidare

* Relaterade koncept: [[05-dsp-odrl]] · [[06-kov-gate]] · [[07-transfer-ingest]]
  · [[C1-identitet]] · [[C2-resursstrategi]] · [[C5-skalning]] (samma anatomi
  på nationell och europeisk nivå)
* Gap: `docs/10-gapanalys.md` G1 (identitet), G16 (organisationsgräns).

## Externa källor (kontrollerade 2026-07-27)

* [Dataspace Protocol 2025-1, specifikationen](https://eclipse-dataspace-protocol-base.github.io/DataspaceProtocol/2025-1/)
* [ISO/IEC DIS 26450 – Eclipse Dataspace Protocol under ISO-standardisering](https://www.iso.org/standard/93502.html)
* [Eclipse Dataspace Working Group: DSP och DCP mot ISO/IEC-standardisering (dec 2025)](https://newsroom.eclipse.org/news/announcements/eclipse-dataspace-working-group-edwg-advances-two-open-protocols-toward-global)
* [IDSA Data Space Connector Report nr 2, juni 2026 (implementationsöversikt)](https://internationaldataspaces.org/wp-content/uploads/dlm_uploads/IDSA-Data-Space-Connector-Report-2-June-2026.pdf)
* [DSSC Blueprint, byggblocket Data Exchange](https://dssc.eu/space/BVE/357075193/Data+Exchange)

---

*C4, 2026-07-27*
