# 03. FCF-modellen och framställning av Distribution A/B

> Future City Flow modellerar dygnet för alla 91 brunnar och framställer
> dataprodukten i två distributioner: A med full brunns-GIS, B med brunns-GIS
> borttaget. Informationsklassningen byggs in i **produkten**, inte i en
> åtkomstlista.

Detta är kedjans **steg 1** (`docs/01-oversikt.md` §1.4) och arkitekturens modelleringssteg
(Målarkitektur v1.9 §4.3 steg 2–3, §8).

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Modellerad bräddata**,
**Distribution A**, **Distribution B**, **bräddning**. Klassningen som sådan
behandlas i [[04-informationsklassning]].

## Vad problemet är

Målarkitektur v1.9 §4.3 steg 2: *"Future City Flow (DHI) beräknar bräddning för
samtliga bräddbrunnar utifrån mät- och nederbördsdata."* Steg 3: resultaten
paketeras som dataprodukten med *"två distributioner med olighet informationsklassning
och ODRL-villkor"*. §8.3 (aggregeringsanalys) kräver att den öppna distributionen
framställs ur den fullständiga genom att positionsuppgifter tas bort.

## Hur PoC:en löser det

`fcf-sim` läser brunn 4526:s mätvärden direkt ur CSV-filerna (`CSV_TOTAL`, `CSV_SPILL`; klassen
`CsvFonster`) till ett fönster om 576 punkter à 5 minuter – hela serien finns från start, så
täckningen är full och resultatet reproducerbart. En batch representerar **ett modellerat dygn** för alla 91 brunnar
(`FCF_BATCH_INTERVAL_S=600` s per dygn). Modellen är avsiktligt enkel: en
överfallsberäkning per brunn (`h = (Q/(C·b))^(2/3)`), inte en hydrodynamisk
MIKE+/MOUSE-modell.

**Bara Krokängsparken (`SSO1_01-4526`) har en riktig mätserie.** Övriga 90
brunnar får **deterministiskt syntetiska** serier: en id-hash (SHA256, ingen
slump) ger varje brunn en skala och en fasförskjutning, så resultatet är
reproducerbart. Det redovisas öppet i varje post via `dataSource`
(`measured` / `measured-partial` / `modelled-synthetic`) och `syntheticScale`.

Distributionerna framställs så här: alla poster byggs först i **A-form** (med
GIS). Distribution B skapas genom att kopiera posterna **utan** nycklarna i
`KANSLIGA_FALT = ("location", "sourceSrs")`. Utsläppspunkt (`outlet`) och
recipient behålls i B – det är brunnens egen position som skyddas, inte hela
geografin.

**Dygnssekvensen har ett fruset ankare.** Batch `n` modellerar dygnet
`startdygn + n`, där `startdygn` härleds **en gång** – ur `FCF_START_DAY` om
den är satt, annars ur mätseriens egen `observedAt` – och sedan ligger fast
(`_startdygn()` i `main.py`). Ankaret får inte läsas om per batch:
den tidigare PoC:ens sensor-simulator spelade CSV:n i **loop**, så senaste `observedAt` vandrade
genom 2026-06-13…06-15 och började om (i Svada-mini ligger serien fast, men ankaret är kvar). Med ett rörligt ankare blir sekvensen
icke-monoton och två batchar kan landa på samma `modelledDay` – vilket bryter
löftet att en batch *är* ett dygn, och gör `batchId` tvetydigt för
proveniensen i [[08-proveniens]]. Löpnumret `BATCH_RAKNARE` är frusen av
samma skäl (det får inte härledas ur `len(BATCHAR)`, som kapas av
retentionen).

Batch 1 ska dessutom vila på **riktiga mätvärden**, inte på reservmönstret.
Därför väntar batchloopen in `FCF_MIN_SAMPLES` mätpunkter innan första
batchen; `FCF_WARMUP_S` är bara ett tak för det fall då mätkedjan är trasig,
och då loggas en varning och `measurementSource` redovisar fallbacken.

Felinjektionsläget manipulerar utlämningskuvertet för att testa nedströmsledens
kontroller – se [[07-transfer-ingest]] för hur de fångas.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/fcf-sim/modell.py` | `brunnsprofil()`, `_hash_tal()` | Deterministiska brunnsparametrar ur id-hash (reproducerbart, ingen slump). |
| `services/fcf-sim/modell.py` | `aggregera()` | Dygnsaggregat: `overflowVolumeM3`, `overflowDurationMin`, `waterLevelMaxM` (`DT_S=300`, 288 punkter/dygn). |
| `services/fcf-sim/brunnar.py` | `las_brunnar()`, `parse_gpkg_point()` | Läser 91 brunnar ur gpkg:n; kastar fel vid nollön. |
| `services/fcf-sim/distributioner.py` | `bygg_poster()` | En post per brunn i A-form; sätter `dataSource`, `syntheticScale`/`measuredCoverage`. |
| `services/fcf-sim/distributioner.py` | `till_b()` | **GIS-reduceringen**: kopierar utan `KANSLIGA_FALT`. |
| `services/fcf-sim/distributioner.py` | `tillampa_felinjektion()` | Manipulerar kuvertet enligt aktiva felflaggor (vid utlämning). |
| `services/fcf-sim/matvarden.py` | `CsvFonster` | Läser CSV-serierna för brunn 4526 (Svada-mini). `MatvardesFonster` (poll av orion-dhi) finns kvar för den tidigare PoC:en. |
| `services/fcf-sim/main.py` | `kor_batch()`, `_svar()` | Producerar batchen; kör `till_b` för B, sedan felinjektion vid utlämning. |
| `services/fcf-sim/main.py` | `_startdygn()`, `BATCH_RAKNARE` | **Dygnssekvensen**: fruset ankare + monotont löpnummer. Båda måste vara frusna för att `modelledDay` ska bli unikt per batch (3.5). |
| `services/fcf-sim/main.py` | `_batchloop()` | Väntar in `FCF_MIN_SAMPLES` mätpunkter före batch 1; loggar varning om taket `FCF_WARMUP_S` nås. |

Styrs av `.env`: `FCF_BATCH_INTERVAL_S`, `FCF_BATCH_HOUR`, `FCF_BATCH_RETENTION`,
`FCF_WARMUP_S`, `FCF_START_DAY`, `FCF_FAULT_SCHEMA_DRIFT`,
`FCF_FAULT_MISSING_FIELDS`, `FCF_FAULT_GIS_IN_B`.

## Bevis

`tests/verify_ap3.sh` (testfallen 3.1–3.9):

* **3.2** – batchen täcker 91 unika brunnar i både A och B.
* **3.3** – A har `location` i alla 91; Krokängs-koordinaten matchar gpkg:n.
* **3.4** – **B saknar brunns-GIS**: 0 poster har `location`/`sourceSrs`, och
  koordinaten finns inte ens som råtext; `outlet` + `recipient` kvar.
* **3.x** – modellinvarianter: 1 ≤ bräddande < 91; bräddflöde ≤ tillrinning;
  exakt 90 `modelled-synthetic` med `syntheticScale` – dvs. sensorbrunnen
  bygger på **mätvärden** och inte på reservmönstret.
* **3.5** – ny batch produceras, `/latest` följer med i båda distributionerna,
  den gamla batchen finns kvar, och **varje batch modellerar ett eget dygn**
  (det testfallet fångar ett vandrande dygnsankare).
* **3.6/3.7** – felinjektionslägena påvisbara; **3.8** – av som default.

Kör själv:

```bash
curl -s localhost:38050/distributions/b/latest | grep -c '"location"'   # ska ge 0
curl -s localhost:38050/distributions/a/latest | grep -c '"location"'   # > 0
curl -s -X POST localhost:38050/batches/run | jq '{batchId, weirs}'
```

## Förenkling → produktion

* **FCF är en miniatyr.** Riktiga Future City Flow är en hydrodynamisk modell över
  hela ledningsnätet. Här: en överfallsberäkning per brunn.
* **90 syntetiska serier** – redovisat i produkten, men innehållet är inte verkligt.
* **Nederbörd saknas som indata** (gapanalysens G6) – modellen har bara en
  syntetisk regnterm, ingen extern nederbördskälla.
* **Dygnsaggregat, inte femminutersserier** som §8.2 specificerar (gapanalysens G20).

## Läs vidare

* Gotchas: varför sensorbrunnen inte får skalas och varför mätfönstret inte får
  upprepas cykliskt (tenant-kravet gäller den tidigare PoC:en).
* Varför `BATCH_RAKNARE` inte
  får härledas ur `len(BATCHAR)` (löpnumret skulle frysa efter
  `FCF_BATCH_RETENTION`).
* Samma buggklass i
  `_startdygn()`: ankaret räknades om per batch och vandrade med den loopande
  mätserien.
* Nästa: [[04-informationsklassning]] och [[05-dsp-odrl]].
