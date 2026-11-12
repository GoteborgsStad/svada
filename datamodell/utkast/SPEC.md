# SewerOverflowModelResult: DRAFT 0.1

**DRAFT v0.1. This is not a decided model.** It is a working draft that this demo uses and shows to visitors to learn what a model would need. It is a temporary model made for the PoC, not proposed as a general model. It is not agreed with the data owner, the provider or the City's technical custodian, and it is not submitted to Smart Data Models. Terms, names and addresses may change without notice. In the source files the addresses are placeholders; on the demo they point to the demo's own address. Both are provisional.

**UTKAST v0.1. Detta är ingen beslutad modell.** Det är ett arbetsutkast som den här demon använder och visar för besökare för att lära sig vad en modell behöver. Det är en tillfällig modell framtagen för PoC:en, inte en föreslagen allmän modell. Det är inte överenskommet med dataägaren, leverantören eller stadens tekniska förvaltare och inte inskickat till Smart Data Models. Termer, namn och adresser kan ändras utan förvarning. I källfilerna är adresserna platshållare; i demon pekar de på demons egen adress. Båda är provisoriska.

*This file is generated from the term list (`termer.json`). Do not edit it by hand.*

## What it describes

A modelled result for one sewer overflow chamber and one modelled day: inflow, overflow, level, the period, where the values come from and under which agreement they were delivered.

Swedish: Ett modellerat resultat för en bräddbrunn och ett modellerat dygn: tillrinning, bräddning, nivå, perioden, varifrån värdena kommer och under vilket avtal de levererades.

## Profiles

There is one model. The profiles say which terms a distribution uses.

| Profile | Terms |
|---|---|
| A | All terms, including location and sourceSrs. Non-public. |
| B | All terms except location and sourceSrs. Public. |

Profile B leaves out the position (`location`, `sourceSrs`). That is a decision about who may see the position, not a different model.

## Identifiers

An entity has an NGSI-LD identifier `urn:ngsi-ld:<type>:<weirId>`. The identifier of a result is built from the entity type and the data owner's key for the chamber (`weirId`). The identifiers are ours and are not covered by the addresses of the terms.

## Entity types

| Type | Definition |
|---|---|
| `SewerOverflowModelResult` | A modelled result for one sewer overflow chamber and one modelled day: inflow, overflow, level, the period, where the values come from and under which agreement they were delivered. |
| `SewerOverflowWeir` | A sewer overflow chamber (brunn) as recorded in the data owner's register. |
| `SewerOverflowModelA` | The entity type under which Distribution A (profile A, all terms including the position of the chamber, non-public) is stored in the City's platform. A profile of SewerOverflowModelResult, not a different model. |
| `SewerOverflowModelB` | The entity type under which Distribution B (profile B, all terms except the position of the chamber, open data) is stored in the City's platform. A profile of SewerOverflowModelResult, not a different model. |

## Terms of SewerOverflowModelResult

| Term | Kind | Type | Unit | Profile | Definition |
|---|---|---|---|---|---|
| `inflowMeanM3S` | Property | number | cubic metre per second (MQS) | A, B | Mean inflow rate to the chamber over the modelled day. |
| `inflowPeakM3S` | Property | number | cubic metre per second (MQS) | A, B | Highest modelled inflow rate to the chamber during the modelled day. |
| `inflowVolumeM3` | Property | number | cubic metre (MTQ) | A, B | Total volume that flowed into the chamber during the modelled day (sum of inflow rate times time step). |
| `overflowVolumeM3` | Property | number | cubic metre (MTQ) | A, B | Total volume that overflowed from the chamber during the modelled day. |
| `overflowPeakM3S` | Property | number | cubic metre per second (MQS) | A, B | Highest modelled overflow rate during the modelled day. |
| `overflowDurationMin` | Property | number | minute (MIN) | A, B | Total time within the modelled day during which the modelled overflow rate was above zero (a sum, not the longest single episode). |
| `waterLevelMaxM` | Property | number | metre (MTR) | A, B | Highest modelled water level in the chamber during the modelled day. The height reference is not specified in the source data. |
| `modelledDay` | Property | date |  | A, B | The calendar day (UTC) the result is modelled for. |
| `periodStart` | Property | date-time |  | A, B | Start of the modelled period (ISO 8601, UTC). |
| `periodEnd` | Property | date-time |  | A, B | End of the modelled period (ISO 8601, UTC). Also used as the observedAt time of the values. |
| `dataSource` | Property | string |  | A, B | Where the values come from: measured (a full day of measurements), measured-partial (part of the day) or modelled-synthetic (a synthetic series, not data). |
| `modelVersion` | Property | string |  | A, B | Name and version of the calculation model that produced the values. |
| `overflowStart` | Property | date-time |  | A, B | Start of the first time step with overflow in the modelled day. Absent when there was no overflow. |
| `overflowEnd` | Property | date-time |  | A, B | End of the last time step with overflow in the modelled day. Absent when there was no overflow. Overflow need not be continuous between start and end. |
| `measuredCoverage` | Property | number |  | A, B | Share (0 to 1) of the day's time steps that rest on measured values. Only for chambers with a sensor. |
| `syntheticScale` | Property | number |  | A, B | Scale factor applied to a measured pattern to make a synthetic inflow series. Present only when dataSource is modelled-synthetic. PoC specific. |
| `syntheticOverflowScale` | Property | number |  | A, B | Scale factor applied to make a synthetic overflow series. Present only when dataSource is modelled-synthetic. PoC specific. |
| `sampleCount` | Property | integer |  | A, B | Number of time steps the day's aggregates are computed from. |
| `refWeir` | Relationship | uri |  | A, B | The chamber this result belongs to (identifier of a SewerOverflowWeir entity). |
| `provenance` | Property | object |  | A, B | Where the delivery came from and under which agreement. A structured value; its members are the terms with the prefix provenance. below. |
| `location` | GeoProperty | geometry |  | only A | Position of the chamber (GeoJSON point, longitude and latitude). Only in the profile A. |
| `sourceSrs` | Property | string |  | only A | The coordinate reference system the source position was given in (for example EPSG:4619). Only in the profile A. |

## Terms of SewerOverflowWeir (the chamber)

| Term | Kind | Type | Unit | Profile | Definition |
|---|---|---|---|---|---|
| `name` | Property | string |  | A, B | Name of the chamber. |
| `weirId` | Property | string |  | A, B | The data owner's key for the chamber. The same key follows the chamber through the whole chain and ends the entity identifier. |
| `regionId` | Property | string |  | A, B | Identifier of the region (area) the chamber belongs to in the source register. |
| `category` | Property | string |  | A, B | Classification of the chamber in the source register. |
| `weirType` | Property | string |  | A, B | Type of chamber or weir structure in the source register. |
| `seriesRef` | Property | string |  | A, B | Reference to the sensor series of the chamber in the source system, when there is one. |
| `outlet` | Property | string |  | A, B | The discharge point (outlet) the chamber overflows to. |
| `recipient` | Property | string |  | A, B | The receiving water body (recipient) of the discharge point. |
| `source` | Property | string |  | A, B | Where the chamber's record comes from: the name of the data owner's register file it was read from. |
| `dataProvider` | Property | string |  | A, B | The party that supplied the chamber's record to the data space (the provider). |
| `description` | Property | string |  | A, B | A free-text description of the chamber from the data owner's register. |

A sewer overflow chamber (brunn) as recorded in the data owner's register.

## Notes on terms

* `overflowDurationMin`: Regulators report overflow duration (for example the English Event Duration Monitoring returns); no machine-readable vocabulary was found for it.
* `location`: Profile B leaves it out. That is a decision about who may see the position, not a different model.
* `name`: In the provider's delivery this field is called weirName; the City's register entity calls it name. The draft uses name.

## Units

Each measure has a UN/CEFACT unit code (in the table above). In the delivery the codes are listed once in `unitCodes`; in NGSI-LD every value carries its own `unitCode`. Times are ISO 8601 in UTC.

## Members of `provenance`

| Member | Type | Definition |
|---|---|---|
| `contractAgreementId` | string | Identifier of the contract agreement under which the data was delivered (provider side). |
| `contractAgreementUrl` | string | Address of the agreement in the City's agreement register. |
| `dataset` | string | Name of the data product. |
| `distribution` | string | Distribution of the data product: A (full) or B (open). |
| `distributionId` | string | Identifier of the distribution in the catalogue. |
| `batchId` | string | Identifier of the delivery batch. |
| `producedAt` | date-time | Time the values were produced (ISO 8601, UTC). |
| `ingestedAt` | date-time | Time the City's platform received the delivery (ISO 8601, UTC). |
| `accessRights` | string | Whether the distribution is public or non-public. |
| `informationClass` | string | The information class of the distribution (for example K0R1T1 or K1R1T1). |
| `license` | string | The licence or agreement terms the distribution is offered under. |
| `publisher` | string | The organisation that produced and published the data. |
| `receivedVia` | string | How the data reached the City's platform. |
| `transferProcessId` | string | Identifier of the transfer in the data space connector. |

## Links to other terms

A link says that a term of ours is related to a term somewhere else. `skos:exactMatch` means the same thing; `skos:closeMatch` means nearly; `rdfs:seeAlso` means related but not equal. The links are in `mappings.sssom.tsv` and are drafts like the rest.

| Our term | Link | Other term | Comment |
|---|---|---|---|
| `SewerOverflowWeir` | rdfs:seeAlso | <http://inspire.ec.europa.eu/codelist/SewerAppurtenanceTypeValue/dischargeStructure> | INSPIRE sewer appurtenance 'discharge structure'. A possible broader term; to be decided with the data owner. |
| `inflowMeanM3S` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.OpenChannelManagement/waterInflow> | Raw-water open-channel junction; same quantity, different domain. Not equal. |
| `inflowPeakM3S` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.OpenChannelManagement/waterInflow> | As inflowMeanM3S. |
| `inflowVolumeM3` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.OpenChannelManagement/waterInflow> | Smart Data Models OpenChannelManagement: water inflow. Close in meaning; the unit and the period differ. |
| `overflowVolumeM3` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.Environment/waterDischarge> | Volume (cubic metre) discharged into water, defined for stormwater and treatment plant discharges. Related, not equal. |
| `overflowPeakM3S` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.Environment/waterDischarge> | Smart Data Models Environment (WaterObserved): water discharge. Close in meaning; ours is the modelled peak overflow. |
| `waterLevelMaxM` | rdfs:seeAlso | <https://smartdatamodels.org/dataModel.Environment/waterLevel> | Current water level of an observation (in that subject: of a storage tank). Ours is a maximum over a day. Related, not equal. |
| `periodStart` | skos:closeMatch | <https://smartdatamodels.org/dataModel.Environment/dateObservedFrom> | Start of an observation period. Ours is a modelled period, not an observed one. |
| `periodEnd` | skos:closeMatch | <https://smartdatamodels.org/dataModel.Environment/dateObservedTo> | End of an observation period. Ours is a modelled period, not an observed one. |
| `location` | skos:exactMatch | <https://uri.etsi.org/ngsi-ld/location> | Core NGSI-LD term, reused as is. |
| `sourceSrs` | rdfs:seeAlso | <https://www.opengis.net/def/crs/EPSG/0/4619> | The OGC address of the EPSG code used in the PoC data. |
| `name` | skos:exactMatch | <https://uri.etsi.org/ngsi-ld/name> | Core NGSI-LD term, reused as is. |
| `weirType` | rdfs:seeAlso | <http://inspire.ec.europa.eu/codelist/SewerAppurtenanceTypeValue/dischargeStructure> | INSPIRE sewer appurtenance 'discharge structure'. Possible broader term; to be decided with the data owner. |
| `source` | skos:closeMatch | <http://purl.org/dc/terms/source> | Dublin Core: a related resource from which the described resource is derived. |
| `dataProvider` | skos:closeMatch | <http://purl.org/dc/terms/publisher> | Dublin Core: the entity responsible for making the resource available. |
| `description` | skos:closeMatch | <http://purl.org/dc/terms/description> | Dublin Core: an account of the resource. |
| `provenance.dataset` | skos:closeMatch | <http://purl.org/dc/terms/title> | Title of a dataset. |
| `provenance.producedAt` | skos:closeMatch | <http://www.w3.org/ns/prov#generatedAtTime> | PROV-O generatedAtTime. |
| `provenance.accessRights` | skos:closeMatch | <http://purl.org/dc/terms/accessRights> | Dublin Core accessRights. |
| `provenance.license` | skos:closeMatch | <http://purl.org/dc/terms/license> | Dublin Core license. |
| `provenance.publisher` | skos:closeMatch | <http://purl.org/dc/terms/publisher> | Dublin Core publisher. |

## Files

`context.jsonld` (term to address), `schema.json` and `schema-profil-B.json` (JSON Schema, key-value form), `mappings.sssom.tsv`, `examples/`. Not Smart Data Models' own artefact set yet: that would also need a description file in their layout and a review by the data owner.

## Swedish summary

Detta är ett utkast till datamodell för modellerade bräddresultat per brunn och dygn. Det finns en modell och två profiler: A med position, B utan. Varje term har en definition, en typ och en enhet, och en del är kopplade till termer hos andra. Utkastet är inte beslutat eller överenskommet med någon, och det är inte inskickat till Smart Data Models.
