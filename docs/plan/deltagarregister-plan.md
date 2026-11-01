# Plan: a participant directory (MIM3 RC5.1)

Status: **stages 1 to 6 done (2026-10-28), stage 7 not planned.** Written and decided 2026-10-28. Goal: change MIM3 RC5.1 from "Not followed" to "Followed", which would leave MIM3 with
no requirement that is not followed (see [MIM3](../mims/mim3-exchanging-data.md)).

## The requirement and what is missing

RC5.1: *participants can discover each other within the data-sharing ecosystem.* Today the City knows DHI because its connector is configured with DHI's address and DID, and DHI
knows the City the same way. A new participant could not be found, and a data user cannot list who the providers are. The orchestrator's role (Svada's issuer) already knows the
members: it issues the membership and participation credentials and keeps the status list. It just does not tell anyone.

## What the directory is

A list, kept by the orchestrator and readable over HTTP on the issuer's own address, of the participants the orchestrator has issued credentials to, with the status of each (a revoked participant stays in the list with status `revoked`). One entry per participant:

| Field | Meaning | Source |
|---|---|---|
| `did` | The participant's DID (did:web) | the issuer's register |
| `name` | Display name | the issuer's register |
| `membership`, `participation` | `valid`, `revoked` or `unknown` (read from the issuer's revocation list at each request; no date, and expiry is not considered) | the issuer's status list |
| `dspEndpoint` | Where the participant's connector answers the Dataspace Protocol (empty for a participant that only consumes) | the participant's DID document, if it carries a service entry; otherwise registered with the issuer |
| `roles` | Not stated by the directory (see below) | – |

**The directory does not state roles.** The principle in this project is that whoever attests something must have the mandate to attest exactly that: the City attests the data
rights owner's role, DHI its own. The orchestrator therefore lists membership only; a role is shown by the participant's role credential when it is presented, as today.

## Options, and the one we recommend

1. **A directory in the orchestrator's issuer (recommended).** A small read-only endpoint next to the existing issuer. It fits the roles, adds no new service and no new trust anchor, and
   the data already exists. Revoking a membership removes the participant from the valid list automatically.
2. **A federated catalogue as well (later).** EDC has a Federated Catalog whose crawler takes its list of nodes from a "target node directory". Our directory can be that list, which would also
   give search across several providers (improvement F21). It is larger, and EDC's documentation calls the crawler module unstable, so it is a second step and only worth it with more than one provider.
3. **Only a document or wiki page with the members.** Easy, but not machine-readable and not tied to the credentials; it would not make participants discoverable by software.

## Stages

Each stage is small, tested and committed locally; nothing is published without a yes from the project.

| # | Stage | Result | Test |
|---|---|---|---|
| 1 | **Decide** the open questions below; check whether the connectors' DID documents can carry a `service` entry with the Dataspace Protocol address (and add it if IdentityHub allows). | A short decision note. | – |
| 2 | **The directory in the issuer:** `GET /participants` (JSON), built from the issuer's register and status list; entries as in the table; marked as a deliberate simplification (the register lives in the issuer's memory, there is no application flow, see gap G15). | The endpoint works for the two PoC participants (DHI and the City). | Unit and HTTP checks of the list (both participants, only the intended fields, no keys or secrets). The connector address is an internal host name; the endpoint is not exposed on the public demo. |
| 3 | **Revocation shows:** revoking a participant's membership removes it from the valid list; reinstating brings it back. | Extends the credential revocation proof. | `verify_ap11.sh` extended. |
| 4 | **The City uses it:** in the control room, the step that lists what the provider shares starts from the directory ("who are the providers?") and then asks the chosen provider's connector for its catalogue. The configured address stays as a fallback. | A visitor sees participants being discovered before data is. | Browser test (K3) and a check that the catalogue request goes to an endpoint from the directory. |
| 5 | **Show and explain:** a small panel or page that lists the directory in Swedish and English, with the plain statement that it is the orchestrator's list and that roles come from the credentials. New version and news post. | Visible in the demo. | Language and layout checks. |
| 6 | **Update the MIM3 assessment** and the improvement list. | RC5.1 becomes Followed, with the caveats of stage 2. | `verify_docs`. |
| 7 | *(Later, optional)* a federated catalogue that crawls the directory's nodes. | Search across several providers. | Own plan. |

## Decisions (2026-10-28)

1. **Who may read the directory:** open, in the demo (the project's decision): no credential is needed. In practice it sits on the issuer's own address, which the public demo does not expose, so visitors see the directory through the control room (names and status only).
2. **Where the Dataspace Protocol address comes from: registered with the orchestrator** (decided by the assistant after looking, as the project asked). Why: the participants' DID documents carry a single service entry, `CredentialService` (checked on the running stack), so a protocol address in the DID document would mean changing three identity hubs through their management interface, and we could not verify that a standard service type exists for the Dataspace Protocol address. Registering the address with the orchestrator is how a participant registry works in practice, needs no change in the participants, and keeps one source of truth. The address is the participant's own statement and is not verified; the DID document is a possible later alternative.
3. **Where it lives: in the issuer** (the project's decision): `Deltagarregister` and `DeltagarregisterPublik` next to the status list in `identity-hub/`.
4. **Federated catalogue (stage 7): no** (the project's decision).

## Progress

| # | Stage | State |
|---|---|---|
| 1 | Decide | Done, see Decisions above. |
| 2 | The directory in the issuer | Done: `GET /participants` on the issuer's DID address (`identity-hub/…/Deltagarregister.java`, `DeltagarregisterPublik.java`); names and addresses from `.env` (`SVADA_DELTAGARNAMN_*`, `SVADA_DSP_ADRESS_*`) through `SVADA_ISSUER_DELTAGARINFO`. |
| 3 | Revocation shows | Done and tested: `verify_ap11.sh`, section 11.8 (six checks; the whole file green after a reset). |
| 4 | The City uses it in the control room | Done: `kallor.valj_leverantor()` picks the provider in the directory (the configured address is the fallback); the catalogue request, the negotiation and the transfer use it. Unit test `tests/leverantor_enhet.py` (K36). |
| 5 | Show and explain, new version and news post | Done as step 2 of the control room: it says how the provider was found and lists the participants by name and status; version 2026.10.28-2 and a news post. There is no separate directory page. |
| 6 | Update the MIM3 assessment | Done: RC5.1 is Followed, with notes. |
| 7 | Federated catalogue | Not planned. |

## Open questions for the project (answered above)

1. **Who may read the directory?** Public (anyone can see who the members are), or only members (a valid credential needed). A public list is simpler; for a real data space, the rulebook would decide. In the demo it can
   be public, since the participants are the PoC's three roles.
2. **Where does the Dataspace Protocol address come from:** the participant's DID document (the standard place, no extra registration) or a field the participant registers with the orchestrator?
3. **Does the directory belong in the issuer service, or in a separate small service?** The issuer is the only party that knows the members, so we lean towards the issuer.
4. **Do we want stage 7 now?** Our recommendation: no, not with one provider.

## What stays a simplification

* The register lives in the issuer's memory and is rebuilt at start (as the issuer's list is today); there is no application, objection or removal flow (G15).
* The issuer is not anchored in eIDAS, and the directory inherits that.
* The directory lists participants; it does not tell whether they can be trusted for a given purpose. That is what the credentials are for.

## Risks

* **A public surface, if it is ever exposed:** the list holds DIDs and connector addresses with internal host names. Today it is not exposed (the issuer's port is bound to the host's loopback and the proxy has no route to it), and the control room shows names and status only. Exposing it would need the list to be filtered first. `svada-reviewer` and the export scanner look at it before any public version.
* **Two sources of truth:** if the address is both in the DID document and in the directory, they can differ. We pick one (question 2).
* **Looking more finished than it is:** the page must say "the orchestrator's list in a PoC" in plain words, like the data model draft does.

## Svenska (sammanfattning)

RC5.1 kräver att deltagarna kan upptäcka varandra. Förslaget är ett deltagarregister som orkestratorns utfärdare (Svada) ger ut: en lista över deltagare med giltigt medlemskap (DID, namn, medlemsstatus och
adressen där deras connector svarar). Listan anger inte roller, eftersom den som intygar en roll ska vara den som har mandat till det. Sju etapper: besluta, bygga listan i utfärdaren, låta återkallelse synas,
låta staden utgå från registret i kontrollrummet, visa och förklara det, uppdatera bedömningen, och senare eventuellt en federerad katalog. Fyra frågor behöver ett beslut, främst om listan ska vara öppen för alla eller bara för medlemmar.
