# 07. Transfer (HttpData-PUSH) och ingest-validering

> Efter finaliserat avtal hämtar providerns dataplan ur fcf-sim och *pushar* till
> stadens ingest-service, som validerar leveransen mot avtalet **innan** något
> skrivs. Mottagaren litar inte på avsändaren – den kontrollerar.

Detta är kedjans **steg 4** (`docs/01-oversikt.md` §1.4) och arkitekturens överförings- och
valideringssteg (Målarkitektur v1.9 §4.3 steg 5).

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Transfer**, **connector**,
**Dataspace Protocol**. Proveniensen som skrivs behandlas i [[08-proveniens]];
klassningskontrollen i [[04-informationsklassning]].

## Vad problemet är

Målarkitektur v1.9 §4.3 steg 5: *"Överföringen auktoriseras av kontrollplanet,
loggas och valideras vid mottagning: schema kontrolleras och för den öppna
distributionen verifieras att positionsuppgifter för brunnar saknas. Data som
bryter mot avtalade villkor avvisas."* §5.1 (datapipeline): fel ska skapa
incident, inte tyst felaktig information.

## Hur PoC:en löser det

Transfern är **HttpData-PUSH**: consumern begär en transfer med en
`dataDestination` som pekar på ingest (`INGEST_PUSH_URL`) med en Bearer-token.
Providerns dataplan GET:ar fcf-sim och PUSH:ar nyttolasten till ingest med token
i `Authorization`-headern.

Ingest kör tre led före något skrivs:

1. **Auktorisation.** `/ingest` växlar först `contractAgreementId` mot en
   **engångstoken** via `/auktorisation` – som slår upp avtalet i *stadens* EDC.
   Saknad token → 401; okänd/förbrukad/utgången → 403. Token är engångs.
2. **Kuvert- och avtalsvalidering.** `granska_kuvert()` kontrollerar obligatoriska
   fält och att distributionen matchar avtalet (ett B-avtal får inte bära
   A-innehåll → 409).
3. **Postvalidering.** `granska_poster()` kontrollerar schemat, och för B att
   `BRUNNS_GIS_FALT = ("location", "sourceSrs")` **saknas**. Gör det inte det –
   felinjektionens `gis_i_b` – kastas `Avvisad(422, "brunns-gis-i-distribution-b")`
   och **hela leveransen** avvisas. Avvisningen slår igenom till EDC som TERMINATED.

Poängen: nyttolasten bär ingen flagga om att den är fel. Ingest upptäcker det
själv.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/ingest-service/main.py` | `ingest()` (`POST /ingest`) | Tar emot pushen; Bearer + `X-Transfer-Process-Id`; kör auktorisation → validering → skrivning. |
| `services/ingest-service/main.py` | `auktorisera()` (`POST /auktorisation`) | Växlar `contractAgreementId` mot engångstoken. |
| `services/ingest-service/auktorisation.py` | `Auktorisationer.utfarda()`, `.konsumera()` | Slår upp avtal i stadens EDC; engångskonsumtion (401/403). |
| `services/ingest-service/validering.py` | `granska_kuvert()`, `granska_mot_avtal()`, `granska_poster()` | Tre valideringsled; `Avvisad`-undantag med maskinläsbar orsak. |

Styrs av `.env`: `EDC_TRANSFER_TYPE=HttpData-PUSH`, `INGEST_PUSH_URL`,
`INGEST_TOKEN_TTL_S=600`, `INGEST_LOG_RETENTION=50`, `EDC_ASSET_A_ID`/`_B_ID`.

## Bevis

`tests/verify_ap4c.sh` (testfallen 4c.1–4c.7):

* **4c.1** – E2E för B: förhandling → transfer → 91 B-entiteter (`SewerOverflowModelB`) i `orion-stad`; brunnsregistret orört.
* **4c.3** – **transfer utan avtal avvisas**: push utan token → 401; påhittad
  token → 403; auktorisation mot obefintligt avtal → 403; **återanvänd
  engångstoken → 403**; fingeravtryck oförändrat = inget skrevs.
* **4c.5** – **felinjektion fångas**: `gis_i_b` → `orsak == "brunns-gis-i-distribution-b"`,
  transfer TERMINATED; `schemadrift`+`saknade_parametrar` → `orsak == "schema-avviker"`;
  orion-stad opåverkat.

Kör själv:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:38060/ingest \
  -H 'Content-Type: application/json' -d '{}'     # 401 – ingen auktorisation
curl -s localhost:38060/leveranser | jq '.counters'
```

## Förenkling → produktion

* **Dataplanet publiceras på värden** (`:38050`) för demons skull; i skarp drift
  publiceras det inte alls – skyddet är kontraktsledet, inte nätverket.
* **Deprecerat inbäddat dataplan.** EDC:s inbäddade dataplan är den svaga länken
  (se gotchan nedan); ett fristående dataplan är en produktionsuppgift.
* **Mock-IAM** – tokenväxlingen sker utan verifierad identitet ([[C1-identitet]]).

## Läs vidare

* Gotcha: `java.io.IOException: closed` i det deprecerade
  dataplanet vid tät transferstart; `kor_transfer()` väntar på **kvittot** och gör
  om upp till 3 gånger med 20 s andrum.
* Nästa: [[08-proveniens]] – vad ingest skriver till CIP.
