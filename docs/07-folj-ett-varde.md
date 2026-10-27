# 7. Följ ett värde genom kedjan – med faktiska API-svar

Det här kapitlet visar hur objekten faktiskt ser ut i varje led, med riktig data ur ett
körande system. Exemplen hänger ihop: **samma bräddbrunn** (SSO1_01-4526, Krokängsparken) och
**samma kontraktsavtal** återkommer led för led. Lägg särskilt märke till avtals-id:t
(`contractAgreementId`) – det knyter ihop kontraktet, ingest-kvittot, proveniensen i CIP och
raden i stegens analys, så att frågan *"under vilket avtal kom det här värdet in?"* har ett
spårbart svar. Id:n varierar mellan körningar – EDC:s stores är in-memory. **Avtalets id är
olika hos DHI och staden**; det som följer med datat är stadens id.

| Steg | Objektet blir | Avsnitt |
|---|---|---|
| 1 | Post i Distribution A (med GIS) / B (utan) | §7.1 |
| 2–3 | ODRL-offert + kontraktsavtal | §7.2 |
| 4 | Ingest-kvitto | §7.3 |
| 5 | CIP-entitet med proveniens | §7.4 |
| 5 | Distribution B för människor (webbvyn) | §7.5 |
| 6 | Rad ur inspektionsprioriteringen, med ursprung | §7.6 |
| 3, 6 | Avtalets status och hävning | §7.7 |

Alla kommandon förutsätter `set -a; . ./.env; set +a` i repots rot.

## 7.1 Dataprodukten: en post i Distribution B – och skillnaden mot A

```bash
curl -s localhost:38050/distributions/b/latest | jq '.records[0]'
```

En post ur **Distribution B** (öppna data). Läs koordinaterna rätt: det
som tas bort i B är **brunnens egen position** – fälten `location` och
`sourceSrs` på postens toppnivå. Koordinaten nedan ligger inuti `outlet`
och är **utsläppspunktens** position, som ska vara kvar enligt §8.5.
Notera också `dataSource: "modelled-synthetic"` och `syntheticScale` –
produkten redovisar öppet att just den brunnen har en syntetisk serie:

```json
{
  "weirId": "SSO1_01-3552", "weirName": "Ruskvädersgatan", "recipient": "Göta Älv",
  "outlet": { "name": "G4", "location": { "type": "Point", "coordinates": [11.9893415, 57.6958130] } },
  "modelledDay": "2026-07-27", "periodStart": "2026-07-27T00:00:00Z", "periodEnd": "2026-07-28T00:00:00Z",
  "overflowVolumeM3": 0, "overflowDurationMin": 0, "waterLevelMaxM": 0,
  "inflowMeanM3S": 0.045565, "inflowPeakM3S": 0.776258, "inflowVolumeM3": 3936.79,
  "unitCodes": { "overflowVolumeM3": "MTQ", "inflowMeanM3S": "MQS", "waterLevelMaxM": "MTR" },
  "dataSource": "modelled-synthetic", "modelVersion": "fcf-sim 1.0.0 / enkel-overfallsmodell",
  "syntheticScale": 0.6409
}
```

**Samma post i Distribution A** har dessutom brunnens egen position på
toppnivå – det är den enda skillnaden, och det är den som gör A känslig
(K1R1T1). Koordinaten är en annan än utsläppspunktens:

```json
{ "weirId": "SSO1_01-3552", "weirName": "Ruskvädersgatan",
  "location": { "type": "Point", "coordinates": [11.9940140, 57.6933174] },
  "sourceSrs": "EPSG:4619",
  "outlet": { "...": "samma som i B" },
  "...": "övriga fält identiska med B" }
```

## 7.2 Kontraktet: ODRL-offerten och avtalet

Hämta katalogen via consumern (`POST :29193/management/v3/catalog/request`
mot providerns DSP-adress). A:s offert bär de tre policydelarna – se
[`05-dataomradet.md`](05-dataomradet.md) §5.2 för hela offerten och
gotchorna vid förhandling via API. Ett finaliserat kontraktsavtal ser ut
så här – `contractAgreementId` är nyckeln som följer med hela vägen in i
CIP:en:

```json
{ "state": "FINALIZED",
  "contractAgreementId": "ef838802-c333-4392-b328-d95b1d99bc72",
  "counterPartyId": "dhi" }
```

## 7.3 Ingest-kvittot

```bash
curl -s localhost:38060/leveranser | jq '{counters, senaste}'
```

Kvittologgen med räknare och senaste posten – samma avtal som i §7.2:

```json
{
  "counters": { "mottagna": 2, "accepterade": 2, "avvisade": 0, "entiteter": 182 },
  "senaste": {
    "resultat": "AUKTORISERAD", "distribution": "B",
    "contractAgreementId": "ef838802-c333-4392-b328-d95b1d99bc72",
    "detalj": "engångstoken utfärdad för Distribution B",
    "at": "2026-07-22T14:36:32Z"
  }
}
```

En avvisad leverans (felinjektionen `gis_i_b`) får i stället
`resultat: "AVVISAD"` och `orsak: "brunns-gis-i-distribution-b"` – och
ingenting skrivs.

## 7.4 CIP-entiteten med proveniens

```bash
curl -s -H "Authorization: Bearer $STAD_GATEWAY_DRIFT_TOKEN" \
  "localhost:$ORION_STAD_PORT/ngsi-ld/v1/entities/urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526" \
  | jq '{overflowVolumeM3, provenance: .provenance.value}'
```

Det modellerade värdet ligger nu på entiteten, och `provenance` svarar på
*varifrån, under vilket avtal och i vilken klass* det kom – samma avtal
som i §7.2 och §7.3, hela tråden knuten:

```json
{
  "overflowVolumeM3": { "value": 367.28, "unitCode": "MTQ" },
  "provenance": {
    "contractAgreementId": "ef838802-c333-4392-b328-d95b1d99bc72",
    "dataset": "Modellerad bräddata", "distribution": "B",
    "distributionId": "modellerad-bradddata-b", "batchId": "batch-005-2026-06-17",
    "producedAt": "2026-07-22T14:43:10.824089Z", "ingestedAt": "2026-07-22T14:45:24Z",
    "accessRights": "public", "informationClass": "K0R1T1", "license": "CC BY 4.0",
    "publisher": "DHI – Future City Flow (SVADA PoC)",
    "receivedVia": "Eclipse EDC transfer (Dataspace Protocol)"
  }
}
```

Tidsseriehistoriken nås via Mintaka – notera de två obligatoriska
delarna, `Accept`-headern och en tidsrelation:

```bash
curl -s -H 'Accept: application/json' \
  'localhost:38083/temporal/entities/urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526?attrs=overflowVolumeM3&timerel=after&timeAt=2026-01-01T00:00:00Z'
```

## 7.5 Distribution B för människor: webbvyn

Samma adress svarar HTML till en webbläsare och JSON till den som ber om
det:

```bash
curl -s -H 'Accept: application/json' localhost:38085/brunnar | jq '{antal, forsta: .brunnar[0]}'
```

```json
{ "antal": 91,
  "forsta": { "id": "SSO1_01-3552", "overflowVolumeM3": 0.0,
              "overflowDurationMin": 0.0, "observedAt": "2026-09-15T00:00:00Z" } }
```

Vyn läser Mintaka med en fast allowlist av öppna attribut, så brunnarnas
koordinater går aldrig att nå härifrån.

## 7.6 Staden använder datat: en rad ur inspektionsprioriteringen

```bash
curl -s "localhost:$DASHBOARD_PORT/api/analys?lage=b&topp=3" | jq '{ursprung, rad: .rader[0]}'
```

Raden bär sitt ursprung – avtal, batch, distribution och klass – så att beslutet går att
härleda till datat och avtalet det kom genom:

```json
{ "ursprung": { "avtal": "ef838802-…", "batch": "batch-005-2026-06-17",
                "distribution": "B", "klass": "K0R1T1" },
  "rad": { "rang": 1, "id": "SSO1_01-6526", "volymM3": 1304.97, "recipient": "Göta Älv",
           "inspektera": true, "avtal": "ef838802-…" } }
```

Med `lage=a` läser analysen Distribution A med brunnarnas position, men bara med en nyckel som
stadens gateway ger för ett **gällande** avtal. Finns inget gällande avtal svarar den
`{"blockerad": {"orsak": "avtal-havt", …}}` i stället.

## 7.7 Avtalets status och hävning

```bash
curl -s "localhost:$DASHBOARD_PORT/api/avtal" | jq '.avtal[] | {id, distribution, status, dhiAvtalId, havning}'
```

Stadens avtalsregister visar varje avtal med status `GALLANDE` eller `HAVT`, avtalets id hos
staden och hos DHI (de är olika) och, om det är hävt, orsak (`AVSLAG` eller `EXPLICIT`), tid
och den verifierade roll som hävde. Varje avtal har också en egen sida,
`/avtal/<id>`, med villkoren i klartext och ODRL-ögonblicksbilden.
