# Data model draft for Svada-mini (DRAFT v0.1)

**DRAFT. This is not a decided model.** It is a working draft that Svada-mini uses and shows to visitors, to learn what a real model would need. It is **not** agreed with the data owner (KoV), the provider (DHI) or the City's technical custodian (Intraservice), and it is **not submitted to Smart Data Models**. Nobody should treat the terms, names or addresses in it as final.

**UTKAST. Detta är ingen beslutad modell.** Det är ett arbetsutkast som Svada-mini använder och visar för besökare för att lära sig vad en riktig modell behöver. Det är inte överenskommet med dataägaren (KoV), leverantören (DHI) eller stadens tekniska förvaltare (Intraservice) och inte inskickat till Smart Data Models. Ingen ska ta termer, namn eller adresser här för slutgiltiga.

## Why we have a draft

The MIM assessments ([MIM1](../mims/mim1-interlinking-data.md), [MIM2](../mims/mim2-representing-data.md)) show that our data has no published, findable
definition of its terms. The delivered data was produced by a calculation model (FCF); that model is not our concern here. What the receiver needs is a
**data model**: which fields there are, what each one means, its unit and format, and how the records relate. We start that journey in the PoC with a draft,
and say so wherever it is shown.

## How we work

1. **Term list** (stage 1): [termlista.md](termlista.md). Every term is borrowed, own or linked.
2. **Draft model** (stage 2): [`datamodell/utkast/`](../../datamodell/utkast/): one model with two profiles (A with position, B without), a JSON-LD context, JSON Schema,
   a specification, links to other vocabularies and examples. Everything is generated from one file, `termer.json`, by `tools/bygg-datamodell.py`.
3. **Use in the PoC** (stage 3, not done): serve the files on the open view's address so that the terms can be looked up, and show the model to visitors with the
   draft label. Until then the stored data and the running chain are unchanged.
4. **Agree** (later, and not in the PoC): the data owner, the provider and the custodian decide the definitions.
5. **Submit** (later, and not in the PoC): to Smart Data Models, as a new model in the water domain. Only then do the terms get permanent addresses there.

## What the draft is, and is not

* One model, `SewerOverflowModelResult`, for the modelled result of one chamber and one modelled day. Distribution A and B have the same model; **B is a profile that leaves
  out the position** (`location`, `sourceSrs`). The running PoC still stores A and B as two entity types (`SewerOverflowModelA`, `SewerOverflowModelB`), because the
  access check in front of the time series interface relies on the type. How the profiles should be stored is open.
* The chamber itself is `SewerOverflowWeir`, the register entity. It is described in the same draft, because its fields travel in the delivery.
* The addresses of the terms are under `modell.svada.invalid`. The `.invalid` ending is reserved so that the addresses can never resolve: they are placeholders. When the
  files are served (stage 3) the base address is replaced, and when the model is accepted somewhere, the terms get their real addresses there. Since 2026-10-29 the data carries
  this context and the broker stores the full addresses (tested), so the base address is stored in the data and has to be chosen once; the nightly reset makes that
  harmless in the PoC.
* The identifiers of our entities (`urn:ngsi-ld:...`) are ours. They are not covered by the addresses of the terms, whoever hosts those.
* Links to other terms (INSPIRE, Smart Data Models, Dublin Core, PROV-O) say "related" or "nearly the same", never more than the definitions support. See the term list.
* Most terms are our own, because we found no model of an overflow event (see the search in [MIM2](../mims/mim2-representing-data.md)).

## Files

[`grund.md`](grund.md) says what the model is built on (a temporary choice for the PoC).

| File | What |
|---|---|
| [`datamodell/utkast/termer.json`](../../datamodell/utkast/termer.json) | The source: every term with definition, unit, origin and links. The only file edited by hand. |
| [`datamodell/utkast/SPEC.md`](../../datamodell/utkast/SPEC.md) | The specification, generated. |
| [`datamodell/utkast/context.jsonld`](../../datamodell/utkast/context.jsonld) | JSON-LD context, generated. |
| [`datamodell/utkast/schema.json`](../../datamodell/utkast/schema.json), [`schema-profil-B.json`](../../datamodell/utkast/schema-profil-B.json) | JSON Schema for profiles A and B, generated. |
| [`datamodell/utkast/mappings.sssom.tsv`](../../datamodell/utkast/mappings.sssom.tsv) | Links to other vocabularies (SSSOM), generated. |
| [`datamodell/utkast/examples/`](../../datamodell/utkast/examples/) | Examples (key-value and NGSI-LD). The position in example A is invented. |
| [termlista.md](termlista.md) | The term list, generated. |

Change a term by editing `termer.json`, run `python3 tools/bygg-datamodell.py`, and `python3 -I tests/datamodell_enhet.py` checks that the draft still matches what the
code delivers (field names, units, the difference between A and B, the provenance members) and that the draft label is in place.

## What we checked, and what not

The schemas and the examples were validated with a JSON Schema validator and the context was expanded with a JSON-LD processor, once, on 2026-10-28 (outside the repository's
tests, which use only the standard library). The definitions are our reading of the code, not an agreed text. In particular the height reference of the water level is
not specified (gap G18), and "overflow duration" is the sum of the time steps with overflow, which is how the PoC's calculation counts it.

## Svenska (sammanfattning)

Vi har en modell, `SewerOverflowModelResult`, för det modellerade resultatet för en brunn och ett dygn. A och B har samma modell; B är en profil utan position. Utkastet har
51 termer (varav fyra entitetstyper: modellen, brunnen och de två leveranstyperna A och B) med definition, enhet och länkar till andra ordförråd där betydelsen stämmer. Allt genereras ur `termer.json`, och ett prov håller utkastet i takt med
koden. Utkastet serveras i demon på `/modell`, data bär modellens kontext och varje leverans kontrolleras mot dess schema. **Det är en tillfällig modell framtagen för PoC:en, inte en föreslagen allmän modell**; vad den bygger på står i [grund.md](grund.md).
Att komma överens om definitionerna med KoV, DHI och Intraservice och att skicka in modellen till Smart Data Models ingår inte i PoC:en.
