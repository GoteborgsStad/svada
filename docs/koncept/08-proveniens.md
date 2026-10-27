# 08. Proveniens i CIP

> Varje bräddbrunn i stadens CIP bär modellerad bräddata **med proveniens**:
> vilket avtal, vilken dataprodukt, vilken distribution, vilken batch och vilken
> informationsklass. Frågan "vem lämnade ut vad, under vilket avtal?" har ett
> svar på varje entitet.

Detta är kedjans **steg 5** (`docs/01-oversikt.md` §1.4) och arkitekturens lagrings- och
kontextsteg (Målarkitektur v1.9 §4.3 steg 6, §6.6 spårbarhet).

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Proveniens**, **CIP**,
**NGSI-LD**, **TRoE / temporal**. Klassningsfälten kommer från
[[04-informationsklassning]]; skrivningen sker i [[07-transfer-ingest]].

## Vad problemet är

Målarkitektur v1.9 §4.3 steg 6: *"Data transformeras till Smart Data Models,
informationsklassas, förses med proveniens (avtal, källa, tidpunkt) och lagras
med tidsseriehistorik."* §6.6 (spårbarhet): mottagen data ska bära proveniens –
källa, avtal och tidpunkt – som underlag för revision och tvistlösning.

## Hur PoC:en löser det

När ingest har validerat leveransen bygger den ett `provenance`-objekt och sätter
det som en NGSI-LD-`Property` på varje modellentitet (`SewerOverflowModelB` för öppna data, `SewerOverflowModelA` för skyddade). Fälten:

* `contractAgreementId` – vilket EDC-avtal leveransen skedde under (**stadens** id; DHI:s id för samma avtal är ett annat, se koncept 06)
* `contractAgreementUrl` – löstbar adress till avtalet (kontrollrummets sida `/avtal/{id}`) med status och ODRL-ögonblicksbild
* `dataset` (`"Modellerad bräddata"`), `distribution` (`A`/`B`), `distributionId`
* `batchId`, `producedAt`, `ingestedAt`
* `accessRights`, `informationClass`, `license`, `publisher`
* `receivedVia = "Eclipse EDC transfer (Dataspace Protocol)"`
* `transferProcessId` (om `X-Transfer-Process-Id` fanns)

**A och B ligger på varsin entitet** (`urn:ngsi-ld:SewerOverflowModelB:<brunn>` och `…ModelA:…`), och brunnsregistret från
[[02-ngsi-ld]] (geometri, namn, recipient) rörs inte alls av leveranserna; modellentiteten pekar på sin brunn med relationen
`refWeir`. Tidigare skrevs båda distributionerna på registerentiteten, så en A-leverans ersatte B:s värden och en hävning av A
fick B-vyn att falla bort. Nu berör en hävning av A bara A:s entiteter, B:s värden och tidsserie består, och den publika
tidsserien kan begränsas till B (Caddy har en positiv allowlist på den råa frågesträngen: exakt ett `type=SewerOverflowModelB` och bara kända parametrar; att leta efter förbjudna strängar räckte inte, eftersom kodade och dubbla `type`-värden slank igenom – `verify_ap9.sh` 9.9c; Mintaka kan inte filtrera per typ själv).
Skrivningen sker med batch-upsert i läget `options=update`, som skapar entiteten om den saknas och annars uppdaterar de
skickade attributen.

Mintaka exponerar historiken via NGSI-LD temporal API, så både aktuellt tillstånd
och tidsserie nås genom samma standardiserade gränssnitt.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/ingest-service/ngsild.py` | `bygg_proveniens()` | Bygger proveniensdicten; droppar None-värden. |
| `services/ingest-service/ngsild.py` | `till_entiteter()` | Sätter `provenance` som `Property` (observedAt = postens `periodEnd`). |
| `services/ingest-service/ngsild.py` | `skriv()` | Batch-upsert `POST …/entityOperations/upsert?options=update` (`ensure_ascii=False`). |
| `services/ingest-service/main.py` | `ingest()` | Anropar `bygg_proveniens()` med transfer-id och `till_entiteter()`. |

Styrs av `.env`: `ORION_URL` (default `http://orion-stad:1026`),
`EDC_ASSET_A_ID`/`_B_ID` (assetId → distribution-mappning i proveniensen).

## Bevis

`tests/verify_ap4c.sh`:

* **4c.2** – proveniensen på brunnen har `contractAgreementId`, `dataset ==
  "Modellerad bräddata"`, `distribution == "B"`, `batchId ~ ^batch-`,
  `accessRights == "public"`, `informationClass == "K0R1T1"`.
* **4c.4 (led 2)** – A-datats proveniens har `distribution == "A"`,
  `informationClass == "K1R1T1"`.
* **4c.6** – två batchar → ≥2 tidssteg i Mintaka.

Kör själv:

> 🔒 CIP:en ligger bakom `stad-gateway` sedan åtgärden av G22 – `orion-stad`
> publicerar ingen värdport. Kommandona nedan kräver därför en token:
> `TOKEN="$(grep ^STAD_GATEWAY_DRIFT_TOKEN .env | cut -d= -f2)"`, sedan
> `-H "Authorization: Bearer $TOKEN"`. Utan token svarar adressen 403 med
> motiveringen utskriven.

```bash
curl -s -H "Authorization: Bearer $TOKEN" 'localhost:32026/ngsi-ld/v1/entities/urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526' \
  | jq '.provenance.value'
```

## Förenkling → produktion

* **Spårbarheten är en vy, inte ett register** (gapanalysens G10). Proveniensen på
  entiteten är beständig (mongo-volym), men EDC:s förhandlings-/transferloggar och
  kontrollrummets auditlogg är in-memory och överlever inte omstart. Revision och
  tvistlösning kräver ett persistent, attribuerbart transaktionsregister –
  vilket i sin tur förutsätter riktig identitet ([[C1-identitet]]).

## Läs vidare

* Gotchas: upsert-läget `options=update` (annars raderas brunnsregistret) och
  `ensure_ascii=False` (annars lagrar Orion-LD `\uXXXX`).
* Relaterat: [[07-transfer-ingest]] (skrivningen), [[04-informationsklassning]]
  (klassfälten), [[02-ngsi-ld]] (grundentiteterna).
