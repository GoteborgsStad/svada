# Improvements for better MIM conformance

A running list of what we would have to change to follow the MIMs better, across all the MIMs we have assessed. Each item names the requirements it would
fix. It is a list of what is needed, **not a plan or a promise**. Update it whenever an assessment changes. Items marked *(choice)* are things we have not done; items
marked *(PoC)* need an operating organisation that a PoC does not have.

Last updated 2026-10-28 (MIM0, MIM1, MIM2, MIM3, MIM6 assessed).

## Would change our claim ("Not followed" today)

| # | Change | Fixes | Effort | Notes |
|---|---|---|---|---|
| F1 | ~~Publish a JSON-LD `@context` for our types and attributes.~~ **Done 2026-10-29:** a draft (a temporary PoC model, see [docs/modell](../modell/README.md)) is served at `/modell`, the data carries its context, every term has a definition, unit and links. | MIM1 R2.1, R2.2; MIM2 R1 | – | Done. The model is temporary and not proposed as a general one. |
| F2 | ~~Decide which models to combine and try the mapping.~~ **Done 2026-10-29 as a temporary choice for the PoC** ([docs/modell/grund.md](../modell/grund.md)): NGSI-LD, Smart Data Models, INSPIRE, Dublin Core, PROV-O, UN/CEFACT; our own terms for the overflow event. To be redone with the data owner, the provider and the custodian in a real service. | MIM2 R1.2a (met as a temporary choice) | – | Done for the PoC. |
| F3 | ~~Describe each entity type as a Smart Data Models artefact set.~~ **Partly done:** the draft has JSON Schema, context, specification and examples. **Not planned:** submitting it (decided 2026-10-29: a PoC does not propose a general model). | MIM2 R1.2b (PoC limitation) | – | PoC limitation. |
| F4 | ~~Let the `dct:conformsTo` address resolve to the specification.~~ **Done 2026-10-29:** both distributions' `dct:conformsTo` in the DSP catalogue also names `<open view>/modell`; the open view's JSON and OpenAPI link to it. | MIM2 R1 | – | Done. |
| F5 | Offer a way to apply extra semantics: serve our context, and decide how the public time series interface treats a visitor's `Link` header safely (for example an allowlist of known contexts instead of dropping it). | MIM1 R3.2 | Small to medium | The proxy drops `Link` today to stop Mintaka fetching arbitrary addresses; keep that protection. *(choice)* |
| F6 | ~~After F1 to F3: meet MIM2 R3.~~ **Done 2026-10-29.** | MIM2 R3 | – | Done. |

### Route we lean towards for F1 to F4 (reviewed 2026-10-28, not decided)

Contribute our own model(s) to the Smart Data Models initiative and link to existing terms, instead of extending other people's models. Reasons and risks are in
the answer given to the project on that date; in short: the term addresses (`https://smartdatamodels.org/dataModel.<Subject>/<term>`) resolve and are governed by the
initiative (FIWARE Foundation, TM Forum, IUDX, OASC), contributions are open to anyone through a pull request to the subject repository (a drafting repository,
`incubated`, exists), and the licence is preferably CC BY 4.0. Risks: approved models are stable and cannot be changed in breaking ways, so definitions must be agreed with
the data owner and the provider first; decisions rest with the subject administrators; we found no description of the submission steps or the review time; and the same
term name can mean different things in different subjects (`waterLevel` is "in the water storage tank" in one). **Correction, tested 2026-10-29:** stored data does *not* keep short names. Orion-LD stores the full term addresses, so the base address
sits in the stored data and cannot be changed later without rewriting it.

### Done 2026-10-29: the data carries the draft context (F1, F5, F6)

Every write and read of the broker and the time series database sends the draft context as a `Link` header (ingest, chamber loader, gateway, control room, open view,
tests); the public proxy replaces a visitor's `Link` with ours (tested). The context is JSON-LD 1.0 (Mintaka 0.7 cannot read 1.1, and a nested context gave HTTP 500).
Orion-LD's default-context option (`-duc`) was tried and dropped: it is read once at start without a retry and falls back silently on the core context (91 chamber entities
written, 0 found after a restart). Left over:
* The delivery types `SewerOverflowModelA` and `SewerOverflowModelB` are not terms in the context yet; they expand under the default namespace. Making them terms must keep A
  and B apart (the access check depends on the type), so each needs its own address.
* `ld+json` answers name the context address Orion or Mintaka was given, which is internal. The gateway (distribution A) and the Caddy proxy for the time series (B) now
  replace it with the public address; Caddy does it with the `replace-response` module (caddyserver; no version tags, pinned to a commit in `.env`, approved 2026-10-29).
  Both paths are checked by tests in `verify_ap9.sh`.
* The base address is stored in the data and must be chosen once. It is derived from the installation's own open-view address, so nothing needs to be registered.
* The image of the chamber loader is built once; after changing it, rebuild it (`docker compose -f compose.stad.yml --profile laddning build ladda-brunnar`).
* F4 (let `dct:conformsTo` resolve to the model) is not done.

## Would settle "Not assessed" or weaken a note

| # | Change | Fixes | Effort | Notes |
|---|---|---|---|---|
| F7 | Test dereferencing `refWeir` through the City's gateway with an approved agreement, and write the result down. | MIM1 R3.1 | Small | Needs a running chain. |
| F8 | ~~Assess MIM3~~ Done 2026-10-28 ([MIM3](mim3-exchanging-data.md)); MIM0 C4 is settled. | MIM0 C4 | – | Done. |
| F9 | ~~Put the unit codes in the open view's JSON and OpenAPI.~~ **Done 2026-10-29:** `enheter` (UN/CEFACT, from the term list) and `datamodell` in both JSON answers and in the OpenAPI description. | MIM2 R3.3 | – | Done. |
| F10 | Add an automated test of content negotiation on the open view and time series interface. | MIM0 R1.1 | Small | Today shown in docs only. |
| F11 | ~~Publish a JSON Schema and validate deliveries on ingest.~~ **Done 2026-10-29:** each entity is checked against the schema before it is stored; the result is in the receipt and in step 4, a deviation gives HTTP 422, a missing schema is shown as not checked ([K38](../11-verifiering.md)). | MIM2 R3.4 | – | Done. |
| F12 | Write down the mapping between the provider's envelope and the City's entities as a common model, as soon as a second provider or consumer exists. | MIM2 R2.1 | Medium | *(PoC)* |

## From the MIM3 assessment (2026-10-28)

| # | Change | Fixes | Effort | Notes |
|---|---|---|---|---|
| F21 | To search across several providers at once: a federated catalogue (EDC has a Federated Catalog, whose crawler its documentation calls unstable) that uses the participant directory (F22) as its list of nodes. | MIM3 RC4.1 across providers (not needed with one provider) | Medium to large | Only when there is more than one provider. *(choice)* |
| F22 | ~~A participant directory kept by the orchestrator's issuer.~~ **Built and used by the control room, 2026-10-28** ([plan](../plan/deltagarregister-plan.md)). | MIM3 RC5.1 (met) | – | Done. Remaining simplifications: in memory, unverified connector addresses, no application flow. |
| F23 | A routine and a legal text for the audit right on Distribution A (what is audited, how, how often, who pays), and a way for the City to report use. | MIM3 RC3.2 (makes the declared right real) | Medium | The right is declared in the agreement (`svada:medgerGranskning`); the routine and the text are missing (G15). *(PoC)* |
| F24 | Requests for new data: ~~a form~~ out of scope for the PoC by decision 2026-10-28. | MIM3 RC7.1, RC7.2 | – | Not planned. |
| F25 | A draft rulebook (membership rules, roles, obligations, how changes are announced), written as a draft like the data model, to show what a real orchestrator would decide. | MIM3 RC1.1 to RC1.3, RC2.4, RC3.1 | Medium | The real rulebook needs a real orchestrator. *(PoC)* |
| F26 | A reviewed legal template for the agreement on Distribution A, in place of the label "Agreement DHI–City of Gothenburg". | MIM3 RC2.3 | Medium | Needs legal review; the data owner's gap G15. *(PoC)* |

## From the look at MIM7 (2026-10-29)

| # | Change | Fixes | Effort | Notes |
|---|---|---|---|---|
| F27 | An OGC API Features view of the chambers in Distribution A (the guidance of MIM7 is about a proxy OGC API over WFS). | Nothing required: MIM7 has no numbered requirements in v9.0 | Medium | Not planned. We only show points on a map. *(choice)* |

## Best practices that are not requirements (MIM0)

| # | Change | Notes |
|---|---|---|
| F13 | Version the open view's API (for example `/v1/…`). | Public change. |
| F14 | Send standard caching headers and rate-limit headers on accepted requests. | Small. |
| F15 | Report the next expected update. | Needs a schedule; none exists for a batch started by hand. |

## Needs an operating organisation (MIM6 and MIM1 R1.5), not a code change

| # | Change | Fixes | Notes |
|---|---|---|---|
| F16 | A management process for keys and passwords: ownership, rotation, instruction to staff. | MIM6 R1.2 | *(PoC)* |
| F17 | A review of access rights at set intervals, and a written access policy including physical access. | MIM6 R1.1, R1.3 | *(PoC)* |
| F18 | Key life cycle (rotation, expiry of credentials, a managed vault) and TLS between containers. | MIM6 R2.1 | *(PoC)* Part of the identity life cycle note. |
| F19 | Integrity protection of stored data (broker and time series database) and a persistent audit log. | MIM6 C2 | *(PoC)* |
| F20 | A body that governs identifiers and promises that they are kept and never reused. | MIM1 R1.5 | *(PoC)* |

## Svenska (sammanfattning)
En löpande lista över vad vi skulle behöva ändra för att följa MIM:arna bättre. Den är en förteckning över behov, inte en plan eller ett löfte. Det som skulle ändra
vårt påstående (F1–F6) handlar om att publicera betydelsen av våra typer och attribut: en JSON-LD-kontext med definitioner (F1), en sökning efter befintliga modeller
som Smart Data Models (F2), ett fullständigt artefaktpaket och ett schema (F3, F11), en adress som går att slå upp (F4) och ett säkert sätt att lägga till betydelse (F5).
Därefter kommer sådant som gör bedömningen säkrare (F7–F12), rekommendationer i MIM0 (F13–F15) och sådant som kräver en driftsorganisation snarare än kod (F16–F20).
