# What the draft data model is based on (a temporary choice for the PoC)

**This is a temporary model made for the PoC, to learn what a data model needs. It is not a decided model, it is not proposed as a general model for sewer overflows, and it is not
submitted to Smart Data Models.** The choice of what it builds on was made by the project (with AI assistants) without the data owner, the provider or the custodian, and it would be
redone with them in a real service. MIM2 R1.2a asks that data models are based on recognised models wherever possible; this page is how we meet it for the PoC, and R1.2b (offering the
model to a community) is a PoC limitation we have chosen not to cross. See [MIM2](../mims/mim2-representing-data.md).

## What each part comes from

| Part of the model | Built on | How | Terms |
|---|---|---|---|
| Structure and the terms `location`, `name` | NGSI-LD core (ETSI GS CIM 009) | **Borrowed** as they are (`lånad`) | `location`, `name`, `id`, `type`, the relationship `refWeir` |
| Flow and level of water | Smart Data Models, `Environment` (WaterObserved) and `OpenChannelManagement` | **Linked** term by term (`rdfs:seeAlso`): close in meaning, but ours are modelled daily aggregates with their own units and period | `inflowVolumeM3`, `inflowMeanM3S`, `inflowPeakM3S`, `overflowVolumeM3`, `overflowPeakM3S` (discharge / inflow), `waterLevelMaxM` (water level) |
| The modelled period | Smart Data Models `Environment` | **Linked** (`skos:closeMatch`) | `periodStart` (`dateObservedFrom`), `periodEnd` (`dateObservedTo`) |
| What the chamber is | INSPIRE Utility Networks, Sewer Network (code list `SewerAppurtenanceTypeValue`) | **Linked** (`rdfs:seeAlso`) to the kind "discharge structure"; the exact class is for the data owner to decide | `SewerOverflowWeir`, `weirType` |
| Provenance (where a delivery came from, under which agreement) | Dublin Core terms and PROV-O | **Linked** (`skos:closeMatch`) | `provenance.dataset`, `.producedAt`, `.accessRights`, `.license`, `.publisher` |
| Description and source of the chamber record | Dublin Core terms | **Linked** (`skos:closeMatch`) | `description`, `source`, `dataProvider` |
| Coordinate reference system | EPSG registry | **Linked** (`rdfs:seeAlso`) | `sourceSrs` |
| Units | UN/CEFACT common codes | **Used** as the unit of every measure | `MTQ`, `MQS`, `MIN`, `MTR` |
| **The overflow event itself** (volume, peak, duration, start and end, how much is measured or synthetic) | Nothing we found | **Our own** terms (`egen`) | `overflowDurationMin`, `overflowStart`, `overflowEnd`, `measuredCoverage`, `syntheticScale`, `syntheticOverflowScale`, `dataSource`, `modelVersion`, and the delivery types `SewerOverflowModelA`, `SewerOverflowModelB` (two profiles of one model) |

The search behind this is in [MIM2](../mims/mim2-representing-data.md): Smart Data Models, INSPIRE, SAREF4WATR, the English EDM returns, OGC and others. No source models an overflow *event*;
everything found describes what the chamber is, or generic water observations.

## What this is not

* Not an extension of someone else's model (we do not change Smart Data Models, INSPIRE or SAREF4WATR).
* Not a standard and not a recommendation to other cities or utilities.
* Not checked by a hydrologist or by the data owner (Kretslopp och Vatten), the provider (DHI) or the custodian (Intraservice).
* Not stable: terms, names and addresses can change, and the base address is stored in the data (see [forbattringar.md](../mims/forbattringar.md)).

## Svenska (sammanfattning)

Det här är en tillfällig modell framtagen för PoC:en, för att lära oss vad en datamodell behöver. Den är inte beslutad, inte föreslagen som allmän modell och inte inskickad till Smart Data Models.
Vi bygger den av erkända modeller (NGSI-LD, Smart Data Models, INSPIRE, Dublin Core, PROV-O, UN/CEFACT) och länkar termerna dit de passar; bräddhändelsen i sig finns ingen modell för, så de termerna är våra egna.
Valet gjordes av projektet (med AI-assistenter) utan dataägaren, leverantören och förvaltaren och skulle göras om med dem i en riktig tjänst.
