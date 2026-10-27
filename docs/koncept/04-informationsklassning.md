# 04. Informationsklassning (K/R/T) i dataprodukten

> Distribution A är K1R1T1, Distribution B är K0R1T1. Klassningen sätts vid
> källan (FCF), bärs som proveniens genom hela kedjan och uttrycks som
> `accessRights` i katalogen. Den lever i **produkten**, inte i en åtkomstlista.

Detta är arkitekturens klassningsled (Målarkitektur v1.9 §8.4, invariant 2 i §6.6)
och genomsyrar kedjans steg 4, 7, 8 och 9.

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Informationsklassning
(K/R/T)**, **Distribution A**, **Distribution B**, **accessRights**, **proveniens**.
K = Konfidentialitet, R = Riktighet, T = Tillgänglighet.

## Vad problemet är

Målarkitektur v1.9 §8.4: Distribution A klassas **K1R1T1** (behörighetsstyrd,
full GIS), Distribution B **K0R1T1** (positionsuppgifter för brunnar borttagna,
öppna data). §6.6 invariant 2: *"den öppna distributionen innehåller aldrig
positionsuppgifter för bräddbrunnar; framställningen ur den fullständiga
distributionen kontrolleras maskinellt i varje led."* §9 princip 9: klassningen
ska **följa informationen genom hela kedjan**.

## Hur PoC:en löser det

Klassningen sätts på ett ställe och bärs vidare:

1. **fcf-sim** definierar klassen i `DIST_META` och exponerar `informationClass`
   + `accessRights` i utlämningskuvertet per distribution.
2. **ingest-service** läser kuvertet och kopierar `accessRights` +
   `informationClass` in i `provenance`, som sätts på varje modellentitet i CIP (en entitetstyp per distribution:
   `SewerOverflowModelB` och `SewerOverflowModelA`). Ingest **validerar** dessutom att B inte bär brunns-GIS.
3. **stad-gateway** läser klassningen i praktiken: A (`non-public`) kräver ett gällande avtal,
   B (`public`) är öppen.

Klassen bärs som **strängliteral** (`K1R1T1`/`K0R1T1`) genom fcf → ingest → CIP. (I den tidigare
PoC:en uttrycktes `access_rights` dessutom som NAL-URI i en CKAN-katalog som skördarna filtrerade
på; den katalogen ingår inte i Svada-mini.)

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/fcf-sim/distributioner.py` | `DIST_META` | **Källan**: `informationsklass` K1R1T1(A)/K0R1T1(B) + `accessRights`. |
| `services/fcf-sim/distributioner.py` | `kuvert()` | Exponerar `informationClass` + `accessRights` i utlämningskuvertet. |
| `services/ingest-service/ngsild.py` | `bygg_proveniens()` | Bär `accessRights` + `informationClass` in i `provenance`. |
| `services/ingest-service/validering.py` | `granska_poster()` | Avvisar B om `BRUNNS_GIS_FALT=("location","sourceSrs")` förekommer. |

## Bevis

`tests/verify_ap3.sh` (klassningens integritetslöfte) och `tests/verify_ap4c.sh`
(klassningen i proveniens):

* **3.1** – A annonseras `non-public` + `containsWeirGis`; B `public` utan GIS.
* **3.4** – B saknar `location`/`sourceSrs` (integritetslöftet bakom K0R1T1).
* **4c.2** – proveniensen i CIP bär `informationClass == "K0R1T1"`, `accessRights == "public"`.

Kör själv:

> 🔒 CIP:en ligger bakom `stad-gateway` sedan åtgärden av G22 – `orion-stad`
> publicerar ingen värdport. Kommandona nedan kräver därför en token:
> `TOKEN="$(grep ^STAD_GATEWAY_DRIFT_TOKEN .env | cut -d= -f2)"`, sedan
> `-H "Authorization: Bearer $TOKEN"`. Utan token svarar adressen 403 med
> motiveringen utskriven.

```bash
curl -s -H "Authorization: Bearer $TOKEN" 'localhost:32026/ngsi-ld/v1/entities/urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526' \
  | jq '.provenance.value | {informationClass, accessRights, distribution}'
```

## Förenkling → produktion

* **Klassen dubbeldeklareras** – i fcf-sim och åter i tillgångarnas egenskaper (`edc/bootstrap/asset-distribution-a.json` och `asset-distribution-b.json`). I
  produktion bör den ha en enda auktoritativ källa (dataproduktspecifikationen,
  gapanalysens G3).
* **Ingen aggregeringsanalys** bakom K0-klassningen (gapanalysens G5, §8.5): att
  fältet är borta är verifierat, men att positionen inte kan *återskapas* ur B:s
  övriga innehåll (brunnsnamn, recipient, utsläppspunkt) är inte analyserat.
* **Metadata klassas inte separat** (gapanalysens G19, §7.2).

## Läs vidare

* Kuvertexemplet visar B (`K0R1T1`); A är `K1R1T1`
  (lätt att citera fel klass om man tar exemplet rakt av).
* Relaterat: [[03-fcf-modellen]] (framställningen), [[08-proveniens]] (bäraren).
