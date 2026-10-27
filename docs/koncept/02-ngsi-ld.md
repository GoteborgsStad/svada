# 02. NGSI-LD, Smart Data Models och context broker

> De 91 bräddbrunnarna laddas in i stadens CIP som NGSI-LD-entiteter av typen
> `SewerOverflowWeir` (brunnsregistret). Det är dataplanets grundtillstånd. Leveranserna
> från DHI skrivs inte på dessa entiteter utan på egna: `SewerOverflowModelB` (öppna data)
> och `SewerOverflowModelA` (skyddade), som pekar på sin brunn med `refWeir`
> (se [[08-proveniens]]).

Detta motsvarar arkitekturens dataplan (Målarkitektur v1.9 §5.1–5.2) och är
kedjans **steg 5** i vilande form (CIP:en) innan någon transfer landat.

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **CIP**, **NGSI-LD**,
**Smart Data Models**, **context broker**, **grunddata**.

## Vad problemet är

Målarkitektur v1.9 §5.2: *"Varje bräddbrunn representeras som en entitet enligt
FIWARE Smart Data Models (typ SewerOverflowWeir eller motsvarande domänmodell),
med egenskaper för bräddflöde, tillrinning och nivå samt relationer till
utsläppspunkt och recipient. Tidsseriehistoriken lagras via brokerns temporala
API."* §5.3 tillägger att anläggnings- och positionsuppgifter är **grunddata**
som ska hämtas från betrodda källor.

## Hur PoC:en löser det

Laddningsjobbet läser testdatats GeoPackage (`dbsvadaexample.gpkg`) direkt som
SQLite – ingen GDAL/fiona. Geometrin ligger som WKB-blob och parsas för hand
(MultiPoint, WKB-typ 4, en inre punkt). För varje brunn byggs en NGSI-LD-entitet:

* `id = urn:ngsi-ld:SewerOverflowWeir:<weirId>`, `type = SewerOverflowWeir`
* `location` som `GeoProperty` → `Point` → `[lon, lat]` (tolkas som WGS84/CRS84)
* `sourceSrs = "EPSG:4619"` (SWEREF99 geografisk) bevaras – källans SRS
* Property-attribut: `name`/`weirId`/`category`/`weirType`/`seriesRef`/`recipient`/`outlet` m.fl.

Entiteterna skrivs med batch-upsert
(`POST /ngsi-ld/v1/entityOperations/upsert?options=replace`) till `orion-stad`
(CIP). Mintaka exponerar tidsseriehistoriken via NGSI-LD temporal API – se
[[08-proveniens]] för hur modellerad data sedan skrivs på samma entiteter.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/ladda_brunnar/ladda_brunnar.py` | `parse_gpkg_point()` | Handparsar GeoPackage-WKB: header, envelope, `srs_id`, MultiPoint → `(lon, lat, srs_id)`. |
| `services/ladda_brunnar/ladda_brunnar.py` | `las_brunnar()` | Joinar `Weirs`/`Recipient`/`Outlet`, bygger `SewerOverflowWeir`-entiteterna. |
| `services/ladda_brunnar/ladda_brunnar.py` | `prop()` | NGSI-LD-omslag `{"type":"Property","value":…}`. |
| `services/ladda_brunnar/ladda_brunnar.py` | `main()` | Batch-upsert i klumpar; verifierar att 91 entiteter finns. |

Konstant i koden: `ID_PREFIX = "urn:ngsi-ld:SewerOverflowWeir:"`. Kör som
engångsjobbet `ladda-brunnar` (profil `laddning`), `./data:/data:ro`.

## Bevis

`tests/verify_ap1.sh` (testfallen 1.1–1.7):

* **1.2** – exakt **91** entiteter av `type=SewerOverflowWeir`.
* **1.3** – Krokängsparken på `[11.9918, 57.6943]` (±0.01); namnet korrekt UTF-8.
* **1.4** – ingen brunn på nollön `[0,0]`; alla inom Göteborgs bounding box.
* **1.5** – temporal historik via Mintaka fungerar.
* **1.6** – **persistens**: fortfarande 91 efter omstart (mongo-volym).

Kör själv:

> 🔒 CIP:en ligger bakom `stad-gateway` sedan åtgärden av G22 – `orion-stad`
> publicerar ingen värdport. Kommandona nedan kräver därför en token:
> `TOKEN="$(grep ^STAD_GATEWAY_DRIFT_TOKEN .env | cut -d= -f2)"`, sedan
> `-H "Authorization: Bearer $TOKEN"`. Utan token svarar adressen 403 med
> motiveringen utskriven.

```bash
curl -s -H "Authorization: Bearer $TOKEN" 'localhost:32026/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000' | jq length
curl -s -H "Authorization: Bearer $TOKEN" -G 'localhost:32026/ngsi-ld/v1/entities' --data-urlencode 'q=weirId~=.*4526.*' \
  | jq '.[0] | {id, location: .location.value.coordinates, sourceSrs: .sourceSrs.value}'
```

## Förenkling → produktion

* **`SewerOverflowWeir` är en lokal modell**, inte en publicerad Smart Data Model.
  Det är gapanalysens G7 (den tidigare PoC:ens FAIR-lager fällde den).
* **Grunddata kopieras in** i stället för att refereras till en betrodd källa
  (gapanalysens G4, §5.3). I produktion ska `location` refereras med stabil
  identifierare mot ett anläggningsregister – vilket också påverkar hur känslig
  Distribution A behöver vara.
* **En MongoDB-container per broker, och TRoE utan Timescale-förmågor.**
  Nulägeslagret körs standalone utan autentisering; historiklagret har inga
  hypertables, alltså varken chunkning eller komprimering, och ingen
  gallringspolicy (gapanalysens G13). Vad som ändras i drift – replica set,
  hypertables, gallring enligt Arkivnämndens beslut – står i
  [[C6-drift-och-uthallighet]].

## Läs vidare

* Gotchas: WKB-parsningen, EPSG:4619 och UTF-8 (`ensure_ascii=False`, annars lagrar
  Orion-LD `\uXXXX` bokstavligen).
* Nästa: [[03-fcf-modellen]].
