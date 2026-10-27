# 14. Dataprodukten: specifikation och kvalitetsdeklaration

Det här är den läsbara specifikationen som connectorns katalog pekar på
(`dct:conformsTo = urn:svada:dataprodukt:modellerad-bradddata:1.0.0`). Den följer
strukturen i målarkitekturens §8.3 (dataproduktspecifikation) och §8.4 (kvalitetsdeklaration),
men bara så långt PoC:en kan stå för det. Det som inte är mätt eller beslutat står som
"ej" och inte som ett värde. I verkligheten publiceras dokumentet av DHI och godkänns av
dataägaren (KoV); här är det ett utkast som ingen har godkänt.

## 14.1 Specifikation

| Avsnitt | Innehåll |
|---|---|
| Namn | Modellerad bräddata, version 1.0.0 |
| Syfte och användning | Modellerade bräddhändelser per brunn och dygn, som underlag för prioritering av inspektion. Inte avsedd för skarpa beslut |
| Dataägare | Kretslopp och Vatten (KoV). Namngiven person ej utsedd i PoC:en |
| Producent / provider | DHI (Future City Flow) |
| Innehåll | Per brunn och modellerat dygn: bräddvolym, toppflöde, nivå, tid för bräddning, mottagare (recipient), utsläppspunkt, enheter. Brunnarnas position (`location`, `sourceSrs`) bara i distribution A |
| Omfattning | 91 bräddbrunnar |
| Tidsupplösning | Dygnsaggregat. Indata har fem minuters upplösning. Målarkitekturen vill ha fem minuter ut (G20) |
| Uppdatering | Ett modellerat dygn per batch; i demon en batch var tionde minut |
| Distributioner | A (K1R1T1, skyddad, kräver KoV-godkännande, får inte spridas eller publiceras) och B (K0R1T1, öppen, CC BY 4.0, brunnarnas position borttagen) |
| Leverans | Dataspace Protocol, HttpData-PUSH till mottagarens ingest |
| Begreppsmodell | NGSI-LD-entiteter; `SewerOverflowWeir` är ingen publicerad Smart Data Model (G7) |
| Höjdreferens | Ej angiven (G18) |

## 14.2 Vad som är riktigt och vad som är syntetiskt

* **En brunn av 91** (SSO1_01-4526, Krokängsparken) bygger på riktiga mätvärden. De övriga **90 är
  syntetiska**: deterministiskt skalade mönster som ser ut som data men inte är det.
* Varje post redovisar det (`dataSource`: `measured`, `measured-partial` eller
  `modelled-synthetic`, och `syntheticScale` för de syntetiska).
* Modellen är en förenklad överfallsberäkning; Future City Flow är i verkligheten en
  hydrodynamisk MIKE+/MOUSE-modell.
* Bräddtiden är lika för alla brunnar som bräddar och används därför inte för rangordning.
* Positionerna i distribution A är påhittade (de ligger på Liseberg).

## 14.3 Kvalitetsdeklaration

Dimensionerna och målnivåerna är de som målarkitekturen §8.4 ger som exempel. **Ingen av dem
mäts ännu i PoC:en.** Tabellen säger det öppet.

| Dimension | Regel (målarkitekturen §8.4) | Målnivå | Senaste mätning |
|---|---|---|---|
| Fullständighet | Andel förväntade femminuterspunkter per dygn | 99 % (tröskel 97 %) | Ej mätt |
| Unikhet | Inga dubblerade tidpunkter per brunn | 100 % | Ej mätt |
| Aktualitet | Daglig leverans före avtalad tidpunkt | 98 % | Ej mätt |
| Validitet | Värden inom fysikaliskt rimliga intervall | 99,9 % | Ej mätt |
| Konsistens | Bräddflöde överstiger inte tillrinning | 99,5 % | Ej mätt |
| Korrekthet | Avvikelse mot uppmätta värden där sensor finns | Redovisas per brunn | Kan bara jämföras för 1 av 91 brunnar |

De tre mått som katalogen bär som `dqv:QualityMeasurement` är fakta om produkten, inte
kvalitetsresultat: antal serier med riktiga mätvärden (1 av 91), andel syntetiska serier
(0,989) och tidsupplösning (1 440 minuter).

## 14.4 Var deklarationen finns i systemet

* **I katalogen:** tillgångsegenskaper i `edc/bootstrap/asset-distribution-{a,b}.json`,
  registrerade av `registrera-edc` och synliga för mottagaren i DSP-katalogen före avtalet:
  `dct:conformsTo`, `dct:accrualPeriodicity`, `dct:temporal`, `dqv:hasQualityMeasurement`
  samt `svada:kvalitetsdeklaration`, `svada:kvalitetsregler` och `svada:modellensBegransning`.
  Båda distributionerna pekar på samma specifikation (en produkt, två distributioner).
* **I kontrollrummet:** steg 2, *Visa exempelobjekt*, visar offerten tillsammans med deklarationen.
* **Test:** `tests/verify_ap4a.sh` 4a.2 kontrollerar att båda distributionerna bär deklarationen.

## 14.5 Vad deklarationen inte är

* Den är ett **påstående från DHI**. Ingen part kontrollerar att det stämmer. Det finns ingen
  ODRL-motsvarighet för kvalitet: ODRL uttrycker vad som får göras, inte hur bra datat är. Om
  kvaliteten ska bli ett åtagande hör den hemma i datadelningsavtalet.
* Egenskaperna är DCAT och DQV, men inte en validerad DCAT-AP-SE-profil. Valideringen mot
  profilen är inte gjord.
