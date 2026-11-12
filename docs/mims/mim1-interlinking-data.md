# MIM1 – Interlinking data

**Our claim: Svada-mini follows MIM1 (self-assessed), with one caveat: the model that gives our types and attributes their meaning is a draft that is not agreed with the data owner, the provider or the custodian. No requirement has the status "Not followed". The identifier requirements (C1) are met, with one PoC limitation.**

How the statuses work is explained in [How Svada-mini follows the MIMs](README.md). The text of MIM1 is from MIMs v9.0 as we read it on 2026-10-28
(<https://mims.oascities.org/mims-specification-v9.0/interlinking-data>); see the version caveats in the overview. MIM1 is about relating data from
different systems in an automated way: identifiers, types and relations. It has no conformance test.

We read the requirements, not the example mechanism in the same page. The mechanism (RDF, OWL, SHACL, SPARQL, dereferenceable IRIs) is one way to meet
them, and the text says so itself. We use NGSI-LD, which is JSON-LD based, so we judge each requirement on what our system does.

## What our identifiers look like

Every entity in the city's broker is an NGSI-LD entity with an id of the form `urn:ngsi-ld:<Type>:<weirId>`, for example
`urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4402`. There are three entity types for one chamber: the register entity (`SewerOverflowWeir`, positions and names,
protected), and one delivery entity per distribution (`SewerOverflowModelB` open, `SewerOverflowModelA` protected). The delivery entities point to their
chamber with the relationship `refWeir`. The `weirId` is the one used in the data owner's own register and in the provider's model, so the same key follows the
chamber through the whole chain. The code is `services/ingest-service/ngsild.py`; the concept is described in `docs/koncept/08-proveniens.md`.

## Capabilities and requirements

### C1 – Entities are identified using unique identifiers

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R1.1 | Every entity has a unique identifier. | **Followed** | The id is an NGSI-LD URN made of the entity type and the chamber's `weirId`, so it is unique in the broker. It is built from the register's key, not from a database row or a host name. |
| R1.2 | Information about an entity can be retrieved by looking up its identifier within a system. | **Followed** | On the time series interface `GET /temporal/entities/<urn>` returns the Distribution B entity (checked against the running stack on 2026-10-28), and the open view answers `GET /brunnar/<weirId>`. For Distribution A the same lookup goes through the City's gateway and needs an approved agreement. A URN is not a web address, so the lookup needs to know where to ask; see R1.3. |
| R1.3 | If an identifier points to the same entity in several systems, it is possible to derive how to look it up in each. | **Followed** (by a written rule) | The rule is simple and fixed: the `weirId` is the same everywhere, and the prefix is the entity type. The open view shows the full URN next to the short id (`id_fullt`). The rule is written in prose in our documentation; it is not published in a machine-readable form (see R2.1). |
| R1.4 | If several identifiers point to the same entity, it is possible to map them. | **Followed** (inside the City's broker) | Inside the broker the delivery entities carry `refWeir`, a standard NGSI-LD relationship to the register entity, and the shared `weirId` gives the same mapping by rule. The public time series answer for Distribution B does not include `refWeir` (checked on 2026-10-28; the register is protected, so it would lead nowhere for an outsider). We do not use `owl:sameAs`, `skos:exactMatch` or any other published mapping vocabulary. The requirement does not ask for one. |
| R1.5 | It is possible to create identifiers that are persistent over time. | **PoC limitation** | The construction is persistent: the same chamber and type always give the same id, and a new delivery updates the same entity. What a PoC cannot give is the commitment: nobody governs the identifier space, and the public demo is reset every night. A real service would need an owner who promises that identifiers are kept and never reused. |

### C2 – Entities can be typed

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R2.1 | The semantics of an entity can be retrieved using only its identifier. | **Followed** (with notes) | Since 2026-10-29 the data carries the draft data model's context. The broker stores the attributes that are terms of the model under the model's own address (for example `<base>/overflowVolumeM3`), and that address opens a page with the definition, the unit, the origin and links to other vocabularies (`/modell`, also as JSON). The base address is the installation's own open-view address, so it works for anyone who runs the PoC. Notes: (1) the delivery types `SewerOverflowModelA` and `SewerOverflowModelB`, and the register attributes `source`, `dataProvider` and `description`, are not terms of the model yet; (2) the model is a draft; (3) a JSON-LD answer from the time series interface or the gateway names the public context address, which opens the context; the definitions are one step further, at the term addresses and in the footer link of the open view. |
| R2.2 | These semantics are described in a machine-readable format. | **Followed** (the model is a draft) | A JSON-LD 1.0 `@context` that maps each term to its address, where the definition, unit and origin are served as JSON and HTML; a JSON Schema, a specification, examples and a mapping file (SSSOM) with the links to other vocabularies are served at the model's address, and tests check them against the term list. The context file itself holds addresses, not definitions. SHACL is not used. |

### C3 – Entities can be (de)referenced

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| R3.1 | A relation defined on an entity can be dereferenced. | Not assessed | `refWeir` is a standard NGSI-LD relationship whose object is the URN of the register entity, and the broker can return that entity by its id. We have not tested the step through the City's gateway with an approved agreement, and for Distribution B the relation is not shown to outsiders. We will assess this when we have tested it. |
| R3.2 | There is a way to apply additional semantics to an existing ontology. | **Followed** (with a note) | Our context adds terms to the NGSI-LD core, and the mapping file and the term pages link each term to the nearest term in other vocabularies (`skos:closeMatch`); that is how semantics are added on top of an existing vocabulary. A visitor cannot make the time series interface or the gateway use a context of their own: both replace a visitor's `Link` header with ours, because Mintaka would otherwise fetch any address a visitor names (the time series path is checked by a test). We took that choice for security and it stays. |

## What it took (done 2026-10-29)

The context is served by the open view and every call to the broker and the time series database sends it as a `Link` header (the writers, the readers, the gateway and the
proxy). Orion-LD's default-context option was tried and dropped: it is read once at start without a retry, and a failed read falls back silently on the core context
(see [forbattringar.md](forbattringar.md)). Mintaka 0.7 cannot read JSON-LD 1.1, so the context is JSON-LD 1.0 with simple terms. The base address is stored in the data, so it
has to be chosen once; the nightly reset makes that harmless in the PoC. Still open: the delivery types as terms, and the agreement on the terms (MIM2).

## A note on the specification

The example mechanism in the MIM1 page calls itself a mechanism of "MIM2 (Interlinking Data)", and the introduction of the page says it is "about Accessing
Data", which is the MIM0 text. We take both as copy errors in v9.0 and assess against the requirements of the MIM1 page.

## PoC limitations
Only R1.5 is held back because Svada-mini is a PoC (no one governs identifiers over time, and the public demo is reset every night). It does not change the
claim.

## Svenska (sammanfattning)
**Vårt påstående: Svada-mini följer MIM1 (egen bedömning), med ett förbehåll: modellen som ger våra typer och attribut deras betydelse är ett utkast som inte är överenskommet med dataägaren, leverantören eller förvaltaren. Inget krav har statusen "Följs inte". Kraven på identifierare (C1) uppfylls, med en PoC-begränsning.**
Varje entitet har ett unikt NGSI-LD-id av typ och brunns-id (`urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4402`) och går att slå upp på tidsserien och i den öppna vyn. Samma
brunns-id följer brunnen genom hela kedjan, och leveransentiteterna pekar på sin brunn med relationen `refWeir`. Sedan 2026-10-29 bär datat datamodellutkastets kontext: attributen lagras under modellens
egna adresser, och varje adress öppnar en sida med definition, enhet och länkar till andra ordförråd (R2.1, R2.2). Kontexten ger bara betydelse åt det vi själva äger; en besökares egen kontext ersätts av vår (R3.2).
Att ett id består över tid (R1.5) kan en PoC inte lova: ingen förvaltar identifierna och demon återställs varje natt. Att följa relationen genom stadens gateway har vi inte prövat (R3.1, ej bedömd).
