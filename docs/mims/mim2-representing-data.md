# MIM2 – Representing data

**Our claim: Svada-mini follows MIM2 (self-assessed), with a PoC limitation: the data model is a temporary model made for the PoC. It is not a decided or proposed general model (R1.2b, a PoC limitation), and its basis in recognised models is a temporary choice by the project (R1.2a). No requirement has the status "Not followed". The transport-format requirements (C3) are met, and since 2026-10-29 every delivery is checked against the model's schema.**

How the statuses work is explained in [How Svada-mini follows the MIMs](README.md). The text of MIM2 is from MIMs v9.0 as we read it on 2026-10-28
(<https://mims.oascities.org/mims-specification-v9.0/representing-data>); see the version caveats in the overview. MIM2 is about consistent, machine-understandable
definitions of the entities in a data ecosystem: data models, how they are transformed, serialisations and application profiles. It has no conformance test.
The requirement numbers in the page are written "R.1", "R1.2a", "R1.2b", "R3" (sic); we use them as written.

## Our data models in short

* The **provider's envelope** (what the FCF simulator delivers over the Dataspace Protocol) and the **City's NGSI-LD entities** (`services/ingest-service/ngsild.py`).
* Three entity types for one chamber: `SewerOverflowWeir` (register, protected), `SewerOverflowModelB` (open) and `SewerOverflowModelA` (protected). The first is a
  local model that is not a published Smart Data Model (the data owner's gap analysis G7). The two delivery types are our own.
* The **open view's JSON** is a reduced projection of Distribution B, described by the OpenAPI document at `/openapi.json`.
* The product is specified in prose in `docs/14-dataprodukten.md`, and the catalogue entry of each distribution points to it with `dct:conformsTo`
  (`urn:svada:dataprodukt:modellerad-bradddata:1.0.0`).

## What the Smart Data Models catalogue has (searched 2026-10-28)

We searched the official list of the catalogue (updated 2026-07-19) for names with sewer, waste, water, weir, overflow, flow, manhole, drain, well, junction,
tank, outlet and similar words, and read the schemas of the closest models. Nothing is a model of a combined-sewer overflow chamber. These are the nearest:

| Model (repository) | What it is | Fits our attributes | Does not fit |
|---|---|---|---|
| `WasteWaterJunction` (dataModel.WasteWater) | A junction in a wastewater **treatment plant**, useful as a sensor location; relationships `startsAt` and `endsAt` | `flowrate` (but in m3/h, ours is m3/s), the idea of a node with up and downstream relations | Made for treatment processes (nitrogen, phosphorus, oxygen…), not for network chambers; no level, volume or duration |
| `WaterObserved` (dataModel.Environment) | An observation of water in a place, with `flow`, `waterLevel`, `waterDischarge`, dates (`dateObserved`, `dateObservedFrom/To`) and `refDevice`; units by UN/CEFACT code | `waterLevel` (our `waterLevelMaxM`), `flow`, `waterDischarge` ("discharge into the water from stormwater and wastewater treatment plants", unit given as cubic metre), observation period | Describes one observation; has no overflow duration, start or end; the unit of `waterDischarge` is a volume while our peak is a rate |
| `OpenChannelJunction` (dataModel.OpenChannelManagement) | A junction in a raw-water open-channel system, with `waterInflow`, `waterOutflow`, `waterLevel` (m3/s and m) and up and downstream relationships | `waterInflow` (our inflow flow rates), `waterLevel`, the node and relation structure | Raw-water channels, not sewers; no overflow volume or duration |
| `WasteWaterSimulationResult` (dataModel.WasteWater) | Results predicted by a simulation, for a treatment plant (airflow, power, concentrations) | The idea of a model result as its own entity | None of its attributes (no flow or level) |
| `Spillway` (dataModel.OpenChannelManagement) | A spillway of a dam or regulation structure, with `waterDischarge` in m3/s | The word and the discharge rate | A structure with design data, not a modelled overflow day |

In short: the catalogue can supply the vocabulary for **parts** of our data (level, flow rates, inflow, the observation period, units by UN/CEFACT code, and
node relations), and `WasteWaterJunction` and `OpenChannelJunction` are reasonable ideas for the chamber as a node. It has nothing for overflow volume, overflow
duration, overflow start and end, or for a modelled daily result per chamber. Those would need an extension of the closest model (R1.2b) or a new model built in the
catalogue's way. We have not checked the context files or licences of these models in detail, and we have not tested mapping our entities to them.

### A wider search (2026-10-28)

We also looked in other places than the Smart Data Models catalogue. Each result is what we read on the page named; we have not tested any mapping.

| Source | What it has for us | What it lacks |
|---|---|---|
| **INSPIRE Utility and Governmental Services**, Sewer Network (EU, a legal data specification) | `SewerPipe` (with `sewerWaterType`; the code list has `combined`, `sanitary`, `storm`, `reclaimed`), `Manhole` and `UtilityNode` (in the common utility elements), and the open code list `SewerAppurtenanceType`, which includes `dischargeStructure`, `regulator`, `meter`, `scadaSensor`, `watertankOrChamber` and `sewerNode`. The best fit for **what the chamber is** (a node or structure in a combined sewer, with an overflow discharge structure). It is an EU-wide, recognised model and the code lists have registry addresses. | No observation or result attributes: no overflow volume, duration, flow or level. A spatial data model, not an NGSI-LD model; the mapping to NGSI-LD is ours to make. Distribution B deliberately has no position, so the geometry part would stay empty. |
| **SAREF4WATR** (ETSI TS 103 410-10, v2.1.1, 2025-04-25; ETSI software licence) | `Manhole`, `Pit`, `Pipe`, `Channel`, `Wastewater` (a water kind), `WaterFlowProperty` with `FlowRate` and `FlowVolume`, and `MonitoringInfrastructure`. Gives ontology terms for flow rate and volume of wastewater, and it builds on SAREF4CITY. | No overflow event, duration, or discharge structure class that we found. We read the first part of the page only (about three quarters of it). |
| **Environment Agency, England: storm overflow Event Duration Monitoring (EDM) returns** (not a standard, but a regulator's published schema) | The closest to **our measure**: per overflow, permit reference, asset type, receiving water, total spill duration in hours, counted spills, monitor operation percentage, location. | Reports duration and counts, not volume; a national reporting format, not an interoperability model; no machine-readable vocabulary found. Useful for what a regulator asks of an overflow. |
| **OGC WaterML 2.0 / SensorThings API (WMO and OGC)** | General models for water observations (sites, time series, observations); SensorThings is JSON and REST. A way to represent our measures as observations. | Nothing sewer-specific. Another API and model family than NGSI-LD, so adopting it would mean a second representation. |
| **CityGML Utility Network ADE (OGC)** | A model for supply and disposal networks, including wastewater and manholes. | A 3D city model; heavy for our need. Not read in detail. |
| **oneM2M Base Ontology** (TS-0012) | A framework of base classes (Device, Service, MeasuringFunctionality and similar) for semantic interworking of devices, compatible with SAREF. | Nothing about sewers, flow or overflow; it is about devices and how their data is described, not about the domain. Read from search results only. |
| **ISO/IEC 5087-1 and 5087-2** (City Data Model; part 1 published 2023, part 2 on 2024-04-24) | Part 1 gives foundation concepts (time, location, activity, resource, agent, organisation); part 2 city-level concepts shared across city services. A possible upper layer for alignment. | The standards are paywalled; we saw only the scopes in catalogue entries, not the content, and could not tell whether part 2 touches wastewater. Not assessed in substance. |
| **Swedish sources** | Nothing found for a Swedish data model for the sewer network (we searched for Svenskt Vatten, VA-GIS and "bräddavlopp"). Svenskt Vatten publishes a report on documenting sewer network models (2020-15), which is not a data model. | We did not search the Swedish standards body, Lantmäteriet or Svenskt Vatten's member pages, and the search tool may miss them. Ask the data owner (KoV) and Svenskt Vatten whether a Swedish model exists. |
| **Norwegian object catalogue (Geonorge) "Sewer Network"** | A national sewer model that mirrors INSPIRE (`us-net-sw`). | Not read in detail. |

What this adds to the picture above: **no source has a model of an overflow event**. Everything found describes either what the chamber is (INSPIRE, SAREF4WATR, the
Smart Data Models junctions) or generic water observations (`WaterObserved`, WaterML, SensorThings, SAREF4WATR flow properties). Overflow duration is what regulators ask for
(the English EDM returns), and volume is usually estimated. The pieces would therefore be combined: **what it is** from INSPIRE (or SAREF4WATR), **observed or
modelled values** from `WaterObserved` or SOSA/SSN-style observations with UN/CEFACT units, and our own terms for the overflow event, which we would publish in a context
with definitions (R1.2b). That is what the improvement list calls F1 to F3.

## Capabilities and requirements

### C1 – All entities are described using consistent data models

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R1 | Data models are explicit and well documented with descriptive metadata; terms are semantically unambiguous; units and time formats are explicit; the models are catalogued so that they are findable. | **Followed** (the model is a temporary PoC model) | Explicit and documented in prose (`docs/14-dataprodukten.md`), in OpenAPI and in the draft model (`/modell`: a definition, unit, origin and links for each of the 51 terms). Units are explicit (UN/CEFACT codes in the model and in the open view's JSON; times are ISO 8601 UTC). Findable: since 2026-10-29 the `dct:conformsTo` of both distributions in the DSP catalogue also points to the model's address (`<open view>/modell`), next to the product's URN, and the open view's JSON and OpenAPI link to it. There is no external catalogue (Smart Data Models or similar): that is part of R1.2b. |
| R1.2a | Data models are based, wherever possible, on commonly recognised standardised models (the page lists ISO/IEC 5087, SAREF, oneM2M, Core Vocabularies, DTDL, MIM7, DATEX II and NGSI-LD Smart Data Models). | **Followed** (a temporary choice for the PoC) | The model is built on NGSI-LD and linked to recognised models: only `location`, `name` and the unit codes are taken over as they are; every other term is our own, with a link to the nearest term elsewhere. The choice is written down in [docs/modell/grund.md](../modell/grund.md): NGSI-LD core for the structure, `location` and `name`; Smart Data Models (Environment, OpenChannelManagement) for flow, level, discharge and dates, linked term by term; INSPIRE Sewer Network for the kind of structure, linked; Dublin Core and PROV-O for provenance and descriptions, linked; UN/CEFACT for units. No source we found has an overflow event, so those terms are our own (the search is in this document). **The combination is a temporary choice made for the PoC by the project, without the data owner, the provider or the custodian. It is not a final choice**, and it would be redone with the parties in a real service. |
| R1.2b | Where no standardised model fits, efforts are made to extend the closest one or to define a new one following community best practice. | **PoC limitation** | We define new terms for the overflow event with the parts of a Smart Data Models artefact set (JSON Schema, JSON-LD context, specification, examples). **We do not propose the model as a general model, and we do not submit it to Smart Data Models**: it is a draft made for the PoC to learn what a data model needs, not agreed with the data owner, the provider or the custodian. Doing it properly needs an operating organisation and agreement between the parties, which a PoC does not have (decided 2026-10-29). |
| R3 | The data models support exchange by meeting the relevant requirements of MIM0 (accessing data) and MIM1 (interlinking data). | **Followed** | MIM0 is followed and, since 2026-10-29, MIM1 is too (with the caveat that the model is a draft). |

### C2 – Different models of the same entity are transformable into a common model

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R2.1 | A common data model is developed for each key entity in the ecosystem, containing the fields of the models used, and each model can be transformed into it. | **PoC limitation** | The PoC ecosystem has one provider and one consumer, so there is only one source model to map: the envelope is transformed into NGSI-LD in `ngsild.py`, and the mapping lives in code and in `docs/koncept/08-proveniens.md`. A real data space has several providers with their own models, and then the common model has to be written down. We have not done that, and the PoC does not give us the need. |

### C3 – Data and metadata can be shared in open, standardised transport formats

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R3.1 | Each data model has at least one open, public, implementation-independent machine-readable serialisation. | **Followed** | NGSI-LD in JSON and JSON-LD (ETSI GS CIM 009); the open view answers plain JSON. |
| R3.2 | The documentation of the format is sufficient for anyone to write a non-proprietary reader. | **Followed** | The format is the public ETSI standard, and the open view's JSON is described in OpenAPI 3.1. |
| R3.3 | Where several formats are supported for one model, they carry the same information without loss of meaning. | **Followed** (with a note) | The time series interface gives the same content as `application/json` and `application/ld+json`; the second adds the `@context`. The open view is a separate, reduced projection with flat fields; since 2026-10-29 its JSON carries the unit of every field (`enheter`, UN/CEFACT codes taken from the term list) and a link to the model, and the OpenAPI description says so. It still leaves out the provenance by design. |
| R3.4 | The representation supports validation against openly published schemas where such mechanisms exist for the format. | **Followed** | ETSI publishes the NGSI-LD OpenAPI and schemas, the open view's OpenAPI contains the response schema, and we publish a JSON Schema for the model (`/modell/utkast/0.1/schema.json` and `schema-profil-B.json`). Since 2026-10-29 the ingest service checks each entity against it before it is stored; the result (`n of n records passed`, which schema) is in the receipt and shown in step 4, a delivery that does not follow is rejected (HTTP 422), and a missing schema is reported as "not checked" and never as passed. The check is a small validator for the keywords the schema uses, compared with the `jsonschema` library by a test when it is installed (K38). |

### C4 – Application profiles

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R4.1 | Application profiles that extend a model do not affect the original model or its users. | Not applicable | The capability is conditional ("when useful"). We have no application profile. Distributions A and B are separate entity types with their own data, not profiles of one model. |
| R4.2 | Extensions are documented separately from the base model. | Not applicable | As above. |

## The draft model: a temporary model made for the PoC

We have a **draft** data model, [docs/modell](../modell/README.md): a term list and a model with a JSON-LD context, JSON Schema, links to other vocabularies and examples, served on
the open view at `/modell`. It is a **temporary model made for the PoC, to learn what a data model needs**. It is not decided, not agreed with the data owner, the provider or the custodian,
not submitted to Smart Data Models and not proposed as a general model. Since 2026-10-29 the data carries its context (MIM1 R2.1, R2.2 and R3.2, and so R3 here), the catalogue and the open view point
to it (R1), its basis in recognised models is written down (R1.2a, a temporary choice) and each delivery is checked against its schema (R3.4). Making it a model that others should use (R1.2b) is outside what a PoC can do.

## Effect on MIM0 and MIM1

MIM0 R1.4 asks that the data models of the payloads are specified. They are, in prose and in the OpenAPI description, so R1.4 is **Followed**
(the deeper question of unambiguous, findable models is MIM2 R1 above). MIM1 is followed since 2026-10-29 (the model is a draft).

## A note on the specification

The page says the mechanism "fulfils all capabilities and requirements of MIM2", and R3 refers to "the MIMs on Accessing data and Interlinking data" without
numbers. We take R3 as MIM0 and MIM1.

## PoC limitations
Two requirements are held back because Svada-mini is a PoC, and they do not change the claim: C2 R2.1 (one source model, nothing to unify) and R1.2b (we do not propose
our draft as a general model, and we do not submit it). R1.2a is met only as a temporary choice for the PoC.

## Svenska (sammanfattning)
**Vårt påstående: Svada-mini följer MIM2 (egen bedömning), med en PoC-begränsning: datamodellen är en tillfällig modell framtagen för PoC:en. Den är inte en beslutad eller föreslagen allmän modell (R1.2b, PoC-begränsning), och dess grund i erkända modeller är ett tillfälligt val av projektet (R1.2a). Inget krav har statusen "Följs inte". Kraven på transportformat (C3) uppfylls, och sedan 2026-10-29 kontrolleras varje leverans mot modellens schema.**
Strukturen är NGSI-LD (öppen ETSI-standard) och enheter och tider är explicita. Modellen byggs av erkända modeller (NGSI-LD, Smart Data Models, INSPIRE, Dublin Core, PROV-O, UN/CEFACT) och grunden står i [docs/modell/grund.md](../modell/grund.md); ingen källa har en bräddhändelse, så de termerna är våra egna. Katalogens `conformsTo` och den öppna vyn pekar på modellens adress (R1). Valet av grund är tillfälligt och gjort utan dataägaren, leverantören och förvaltaren. Att föreslå modellen som allmän, eller skicka in den till Smart Data Models, gör vi inte i en PoC (R1.2b). En gemensam modell (C2) behövs först när det finns flera leverantörer, vilket PoC:en inte har. Applikationsprofiler (C4) gäller inte.
Därmed kan MIM0:s R1.4 bedömas som uppfylld.
