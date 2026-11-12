# MIM7 – Geospatial data

**Our claim: MIM7 cannot be assessed against requirements, because the v9.0 page publishes none. We say what we do with geospatial data instead. It is of limited relevance to Svada-mini: we only show the positions of the chambers as points on a map, and only in the non-public Distribution A.**

How the statuses work is explained in [How Svada-mini follows the MIMs](README.md). We read the page on 2026-10-29
(<https://mims.oascities.org/mims-specification-v9.0/geospatial-data/>; it is listed among the MIMs Plus of v9.0 at <https://mims.oascities.org/mims-plus-specification-9.0.md>).

## What the page says

The page has a **description** and one item of **interoperability guidance**, and nothing else: no capabilities, no numbered requirements, no must, should or may, no conditions and no conformance test.

* **Description (our reading):** cities and communities find it hard to integrate and transfer geospatial data between internal and external IT systems; spatial assets must be reachable as linked data for many IT and IoT systems over long periods, which makes persistent identifiers important.
* **Guidance:** for standards-based geospatial encodings such as GML and CityGML shared through OGC WFS, a proxy OGC API "could be considered" on top of the WFS service.

The GitHub repository the page lists for MIM7 was empty when we looked (`oasc/geospatial-data-mim-7`). We found no other text for MIM7, so we have not read more than the page.

## What we do with geospatial data

| Subject | What we do | Note |
|---|---|---|
| Which data is geospatial | The position of each of the 91 chambers (`location`) and the coordinate system it came from (`sourceSrs`). | Only in Distribution A (non-public, needs the data owner's approval). Distribution B, the open data, has no position by design (information class K0R1T1). |
| Encoding | A point as GeoJSON in an NGSI-LD `GeoProperty`; longitude and latitude in degrees. `location` is a term borrowed from NGSI-LD as it is (see [docs/modell](../modell/grund.md)). | Open, standard encoding. |
| Coordinate system | The source is EPSG:4619 (SWEREF99, geographic). It is written as WGS84, which is what GeoJSON and NGSI-LD assume, and the source system is kept in `sourceSrs`. | A deliberate simplification: for Gothenburg the difference is far below a metre (the loader's comment says so). We did not transform the coordinates. |
| Use | Step 6 of the control room shows the points of A on a map (OpenStreetMap tiles, or a local background). | We only display points. We do no spatial analysis, no polygons and no network topology. |
| Offered through OGC services | No. We offer no WFS, no OGC API Features and no GML or CityGML. | The guidance in the page is about those services, so it does not apply to us. An OGC API Features view of A would be a possible addition (F27, not planned). |
| Persistent identifiers for spatial assets | A chamber has the data owner's key (`weirId`), which follows it through the whole chain and ends the entity identifier. | The PoC cannot promise that identifiers last or are never reused: see MIM1 R1.5 (PoC limitation). |

## Effect on the claims about the other MIMs

None. The position is one more attribute that MIM0 to MIM3 and MIM6 already cover (access to it goes through the same agreement and the same approval as the rest of Distribution A).

## Svenska (sammanfattning)
**Vårt påstående: MIM7 går inte att bedöma mot krav, eftersom v9.0-sidan inte har några. Vi redovisar i stället vad vi gör med geodata. Det är av begränsad betydelse för Svada-mini: vi visar bara brunnarnas positioner som punkter på en karta, och bara i den icke-offentliga distribution A.**
Sidan har en beskrivning och en rad vägledning (en OGC API-proxy över WFS kan övervägas) men inga numrerade krav, ingen skall-/bör-nivå och inget prov. Positionen är en punkt som GeoJSON i NGSI-LD, med källans koordinatsystem (EPSG:4619) bevarat i `sourceSrs` och behandlat som WGS84 (en medveten förenkling, skillnaden är långt under en meter). Vi erbjuder inga OGC-tjänster, så vägledningen gäller inte oss. Bestående identifierare för brunnarna är samma PoC-begränsning som i MIM1 R1.5.
