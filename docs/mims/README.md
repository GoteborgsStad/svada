# How Svada-mini follows the MIMs

The MIMs are the *Minimal Interoperability Mechanisms* of OASC (Open & Agile Smart Cities and Communities). They describe a small set of mechanisms
that cities and data spaces should share so that their data and services can work together. Svada-mini is a proof of concept (PoC) for a data space
for water and wastewater data. This chapter says openly, MIM by MIM, what we follow, what we do not follow, and why.

*Svenska: se sammanfattningen längst ned.*

**Who made these assessments.** They were prepared by the project's authors together with AI assistants (among them Claude, Codex and Gemini), and have not been reviewed by anyone outside the project.

## Which version we read
We read **MIMs v9.0** on 2026-10-28 (the web version at mims.oascities.org). v9.0 was opened for review in February 2026 and the review ran until 31 May 2026.
We could not confirm that it has been formally finalised, so every statement here is about the text as we read it, and it may change. The pages we read
carry no change history, so any comparison with v8 is ours. MIMs have **no conformance test**: the assessments below are our own, made by the project.

## How we assess a MIM
Each requirement of a MIM gets exactly one of the statuses below. Most are the first three; the last one is for requirements that only apply under a condition.

| Status | Meaning | Effect on "we follow this MIM" |
|---|---|---|
| **Followed** | The requirement is implemented in Svada-mini, with a pointer to where it can be seen or tested. | Counts as followed. |
| **PoC limitation** | We cannot follow the requirement fully *only because* Svada-mini is a PoC and not a real operation: there is no operating organisation, no staff, no production environment, and stores are in memory. We say what is missing. | Reported openly, but does **not** change whether we say that we follow the MIM. |
| **Not followed** | We have chosen not to follow it, or it is outside what we do, for a reason that is not "this is a PoC". The reason is stated. | Counts against the claim. One such requirement means we say "partly". |
| **Not applicable** | The requirement is conditional ("for use cases that require ...") and the condition does not hold for our use case. We say why. | Does not change the claim. If the use case changes, we assess it again. |
| **Not assessed** | A requirement that depends on a MIM we have not assessed yet. | Listed, and not counted either way. |

**The claim.** We say "Svada-mini follows MIM N" when no requirement has the status *Not followed*. We say "partly" when one or more do, and "not" when
the capabilities themselves are not addressed. A PoC limitation never lowers the claim, but it is always listed, so a reader can see what a real
operation would still have to do.

A statement that we follow a MIM is not a certification. Where a MIM refers to a standard such as ISO/IEC 27001, following the MIM means addressing the
referenced control for the purpose of that MIM, not holding the certificate.

## Status

| MIM | Name (as in v9.0 links) | Our claim | Page |
|---|---|---|---|
| MIM0 | Accessing data | **Followed** (self-assessed); R3.1 not applicable | [mim0-accessing-data.md](mim0-accessing-data.md) |
| MIM1 | Interlinking data | **Followed** (self-assessed), with the caveat that the data model is a draft; identifiers (C1) met | [mim1-interlinking-data.md](mim1-interlinking-data.md) |
| MIM2 | Representing data | **Followed** (self-assessed), with a PoC limitation: the model is a temporary PoC model, not proposed as a general one (R1.2b); transport formats (C3) met | [mim2-representing-data.md](mim2-representing-data.md) |
| MIM3 | Exchanging data | **Followed** (self-assessed); governance (C1) and requests for new data (C7) are PoC limitations, RC3.2 has a PoC caveat | [mim3-exchanging-data.md](mim3-exchanging-data.md) |
| MIM7 | Geospatial data | **Cannot be assessed**: v9.0 publishes no numbered requirements; we describe what we do (points on a map, only in A) | [mim7-geospatial-data.md](mim7-geospatial-data.md) |
| MIM6 | Securing data | **Followed** (self-assessed), with PoC limitations | [mim6-securing-data.md](mim6-securing-data.md) |

We started with MIM6, then MIM0, MIM1, MIM2 and MIM3, and looked at MIM7. MIM4 (Personal data) and MIM8 (Local digital twins) are listed in v9.0 but are not assessed yet. What we would have to change to follow the MIMs better is kept in [forbattringar.md](forbattringar.md). The MIM names above come from the page addresses in v9.0 and are not confirmed against the
specification text. Other MIMs are not assessed yet; we do not claim anything about them.

## Svenska (sammanfattning)
Bedömningarna är framtagna av projektets upphovspersoner tillsammans med AI-assistenter (bland annat Claude, Codex och Gemini) och har inte granskats av någon utanför projektet.
MIM:arna är OASC:s minimikrav för interoperabilitet mellan städer och dataspaces. Här redovisar vi öppet, MIM för MIM, vad Svada-mini följer, vad vi
inte följer och varför. Varje krav får en av tre statusar: **Följs**, **PoC-begränsning** (kravet kan inte följas fullt ut bara för att det här är en PoC
och inte en riktig verksamhet; redovisas men påverkar inte om vi säger att vi följer MIM:en) och **Följs inte** (vi har valt bort det, med skäl). Vi säger
att vi följer en MIM när inget krav har statusen *Följs inte*. Bedömningen är vår egen: MIM:arna har inget konformitetsprov, och v9.0 var ute på remiss
till 31 maj 2026 (slutligt läge inte bekräftat). Vi har bedömt MIM6, MIM0, MIM1, MIM2 och MIM3, och tittat på MIM7 (inga numrerade krav i v9.0, så den går inte att bedöma; vi redovisar vad vi gör). Vad vi skulle behöva ändra för att följa MIM:arna bättre finns i [forbattringar.md](forbattringar.md). Två statusar till: **Gäller inte** (villkorat krav vars villkor inte uppfylls av vårt användningsfall) och **Ej bedömd** (hänger på en MIM vi inte bedömt).
