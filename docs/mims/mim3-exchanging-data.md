# MIM3 – Exchanging data

**Our claim: Svada-mini follows MIM3 (self-assessed). No requirement has the status "Not followed". The core of an exchange is met: terms, the right to audit, identification of the parties, discovery of the data a provider shares and of the participants, agreement and termination. The governance requirements (C1) and the requests for new data (C7) are PoC limitations, and RC3.2 has a PoC caveat.**

How the statuses work is explained in [How Svada-mini follows the MIMs](README.md). The text of MIM3 is from MIMs v9.0 as we read it on 2026-10-28
(<https://mims.oascities.org/mims-specification-v9.0/exchanging-data>); see the version caveats in the overview. MIM3 is about setting up and running a trustworthy
data-sharing ecosystem: governance, terms, compliance, discovery of data and of participants, agreeing and ending an exchange, and asking for new data. It has no
conformance test. Almost all of its requirements say "should"; only RC3.1 says "must". We report every one of them in the same way. Three of the first statuses were changed the same day (RC3.2 and RC4.1 after the project's review, RC5.1 after the directory was built), and each change is explained in its row.

Two things about the page. Its introduction says the MIM "is about Accessing Data", which is the MIM0 text (we take it as a copy error), and v9.0 has no Mechanisms page
for MIM3, so we judge the requirements as written. We also had assumed in the MIM0 assessment that MIM3 is about identifying actors; in v9.0 that is requirement RC5.3
and RC5.4, one part of a wider MIM.

Who is who in the PoC, in MIM3's words: the **data provider** is DHI, the **data user** is the City, the **data rights owner** is Kretslopp och Vatten (through the data
owner), the **data ecosystem orchestrator** is Svada's coordinating role (the issuer of membership credentials, DSGA 0.1), and the **administrator** is the City's custodian
(Intraservice) for the City's side. The roles are played by the PoC; there is no real organisation behind the orchestrator.

## Capabilities and requirements

### C1 – Governance rules for the ecosystem can be defined

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC1.1 | The orchestrator can define a governance model (a rulebook): membership rules, roles, responsibilities, obligations, principles. | **PoC limitation** | The rules exist as code and configuration, not as a rulebook: who may be a member (a membership credential from Svada's issuer), which roles exist (role credentials, each accepted only from the right issuer) and what a distribution requires (ODRL). The text of a rulebook has to be decided by a real orchestrator; the data owner's gap G15 says it is missing. |
| RC1.2 | Members are aware of the governance model and of changes to it. | **PoC limitation** | There is no rulebook to be aware of, and no way to announce a change. |
| RC1.3 | The governance model is easy to understand. | **PoC limitation** | Follows from RC1.1: nothing written yet. The control room explains the roles and the chain in plain language. |

### C2 – Terms and conditions can be defined

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC2.1 | Data providers are free to define their terms (after ensuring they have permission from the data owners). | **Followed** | The provider sets an ODRL policy for each distribution (B: use, distribute, publish; A: only the City, 30 days, no distribution or publication). Permission from the data rights owner is built in: Distribution A is paused at the provider until Kretslopp och Vatten decides. |
| RC2.2 | Terms are clear and unambiguous to data users. | **Followed** | Each distribution's policy is machine-readable (ODRL) and is explained in the control room and in `docs/koncept/05-dsp-odrl.md`. |
| RC2.3 | Terms are expressed through licences or agreements based on templates or standards. | **Followed** (technically) | B has a standard licence (CC BY 4.0); A is an ODRL agreement. The legal text behind A ("Agreement DHI–City of Gothenburg") is a label, not a reviewed contract template (G15). |
| RC2.4 | Terms are in line with the governance model. | **PoC limitation** | There is no governance model to compare with (RC1.1). |

### C3 – Compliance can be validated

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC3.1 | (*must*) The orchestrator can ascertain that participants comply with the governance model. | **PoC limitation** | Membership and role credentials are checked at every Dataspace Protocol call, so the membership rules are enforced when the parties talk. A review that participants follow the rulebook needs a rulebook and a real orchestrator. |
| RC3.2 | Providers can ascertain that the use of data complies with the agreed terms. | **Followed** (by a contract term; PoC limitation noted) | The agreement for Distribution A carries the obligation `svada:medgerGranskning` (`edc/bootstrap/policy-distribution-a.json`): the recipient grants the provider the right to audit how the data is used. That gives the provider the right to ascertain compliance. It is a **declaration**: no connector can check use after the transfer, there is no audit routine, and the legal text that would back it is missing (the data owner's gap G15). The City also checks the agreement at every use, and the PoC's audit view collects the events of all parties inside the PoC. Distribution B, open data under CC BY 4.0, has only an attribution duty and no audit right (there is nothing to audit). |
| RC3.3 | Data users can ascertain that the provider's supply follows the agreed terms. | **Followed** | The City's ingest checks each delivery against the agreement before anything is written, and every entity carries its provenance (agreement, distribution, batch, information class, time). |

### C4 – Available data assets can be discovered

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC4.1 | Data users can discover what is available without prior knowledge of it. | **Followed** (for one provider) | Asking a connector what it shares is exactly what the Dataspace Protocol catalogue request does: the City asks DHI's connector and gets the distributions with their terms and metadata, without knowing the data beforehand. What a data user does need to know is where the provider is. With one provider that is configuration; with several it needs a way to find the providers, which is RC5.1 below (and, to search across all of them at once, a federated catalogue, see the improvement list). We first read this requirement more strictly and called it "Not followed"; we changed it on 2026-10-28 after the project pointed out that the catalogue request is the discovery. |
| RC4.2 | Assets are described with metadata enough to decide on further use. | **Followed** | The catalogue entry of each distribution carries the licence, access rights, information class, update frequency, time coverage and quality facts (`docs/14-dataprodukten.md`, section on the catalogue), and the product has a written specification. |
| RC4.3 | The metadata uses well-defined formats that are human- and machine-readable. | **Followed** (with a note) | DCAT-style JSON-LD from the connector for machines, a written specification and the control room for people. The address named in `dct:conformsTo` is an identifier and does not return the specification (see MIM2 R1). |

### C5 – Participants can be discovered

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC5.1 | Participants can discover each other. | **Followed** (with notes) | The orchestrator's issuer keeps a participant directory, `GET /participants`: each participant with its DID, name, membership and participation status (read from the revocation list at each request, so a revocation shows at once; revoked participants stay in the list with status "revoked") and the address of its connector. It states no roles (each organisation attests its own). The City's control room uses it: step 2 finds the provider in the directory before asking its catalogue, and shows the participants by name and status (never DIDs or addresses, which hold internal host names). Tested in `tests/verify_ap11.sh` (section 11.8) and `tests/leverantor_enhet.py`. **Notes:** the directory is not restricted by credentials, but it sits on the issuer's internal address and is not exposed on the public demo; visitors see it through the control room. The connector address is the participant's own statement to the orchestrator and is not verified. The list lives in the issuer's memory and has no application or removal flow (G15). Before 2026-10-28 this was "Not followed". |
| RC5.2 | Enough metadata about each participant is available to judge trustworthiness. | **Followed** (PoC limitation noted) | Each party has a DID document and holds credentials (membership, participation, role), each accepted only from the right issuer. The issuer itself is not anchored in eIDAS and has no revocation of the issuer's own standing (a deliberate simplification, see [MIM6](mim6-securing-data.md)). |
| RC5.3 | Providers can reliably identify the data users and verify their metadata before access. | **Followed** | The provider checks the City's credentials (signature, issuer, status) at every call; for A the data rights owner also decides. |
| RC5.4 | Data users can identify the providers before using the data. | **Followed** | The check goes both ways in the Decentralized Claims Protocol: the City verifies DHI's credentials. |
| RC5.5 | Participants may stay anonymous if the governance model allows. | Not applicable | The exchange does not allow anonymity. (The open view's readers are anonymous, but they are not parties to an exchange.) |

### C6 – A data exchange can be agreed upon

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC6.1 | The parties can agree to an exchange and its terms (acceptance, signature or negotiation). | **Followed** | Contract negotiation in the Dataspace Protocol. B is finalised automatically; A waits at the provider for the data rights owner's decision. |
| RC6.2 | The parties can terminate an agreed exchange in accordance with the terms. | **Followed** (with a note) | The provider can revoke an agreement; the City checks the status at every use of a key (closed by default). The Dataspace Protocol itself defines no termination of a completed agreement, so the revocation is our addition. The rule that a refusal revokes earlier agreements of the same asset and party is a deliberate simplification. |
| RC6.3 | Electronic means for agreement and termination may be provided. | **Followed** | All of it is done electronically, through the connectors and the control room. |

### C7 – New data that is not available can be requested

| Req. | What it says | Status | What we do, and what is missing |
|---|---|---|---|
| RC7.1 | Data users can express interest in data that is not available. | **PoC limitation** (out of scope) | Out of scope for the PoC, by the project's decision on 2026-10-28: there is no way to ask for data that is not in the catalogue. A real data space would need one. |
| RC7.2 | Providers can obtain such requests. | **PoC limitation** (out of scope) | As above. |

## Effect on MIM0

MIM0's capability C4 says that restrictions on access follow MIM3 and MIM6. The part of MIM3 that is about restrictions is the identification of the parties (RC5.2 to RC5.4),
which we follow. MIM0 stays **Followed**; the row in the MIM0 page is updated. This is a reading of which requirements MIM0 means, and MIM0 does not name them.

## PoC limitations
RC1.1 to RC1.3, RC2.4 and RC3.1 are held back because Svada-mini is a PoC: they need a real orchestrator who decides a rulebook, and the PoC has only a role played by us. RC7.1 and
RC7.2 (requests for new data) are out of scope for the PoC by decision. RC3.2 has a PoC caveat (no audit routine, no legal text). RC5.1 is met by a directory with PoC simplifications (held in memory,
unverified addresses). None of these changes the claim.

## Svenska (sammanfattning)
**Vårt påstående: Svada-mini följer MIM3 (egen bedömning). Inget krav har statusen "Följs inte". Kärnan i ett utbyte uppfylls: villkor, rätten att granska, identifiering av parterna, upptäckt av den data en leverantör delar och av deltagarna, avtal och avslut. Styrningskraven (C1) och förfrågningar om ny data (C7) är PoC-begränsningar, och RC3.2 har ett PoC-förbehåll.**
Leverantören (DHI) sätter ODRL-villkor per distribution och rättighetsinnehavaren (Kretslopp och Vatten) beslutar om A. Avtalet för A innehåller åtagandet `svada:medgerGranskning`, alltså rätt att granska hur datan används (RC3.2); det är en deklaration utan granskningsrutin och med en juridisk text som saknas. En katalogfråga till en connector är precis upptäckten av vad den delar (RC4.1).
Samordnarens utfärdare har ett öppet deltagarregister (`/participants`): varje deltagare med DID, namn, medlems- och deltagarstatus (en återkallelse syns direkt) och connectorns adress, men inga roller (RC5.1).
Parterna identifierar varandra med verifierbara intyg, avtalet förhandlas och kan hävas hos leverantören, och stadens mottagning kontrollerar varje leverans mot avtalet och sparar proveniens. Det saknas en regelbok (kräver en riktig dataområdesförvaltare). Förfrågningar om ny data ligger utanför PoC:en. MIM0:s krav om begränsad åtkomst följer MIM3:s identifiering av parter (RC5.2–RC5.4).
