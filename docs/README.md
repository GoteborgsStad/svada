# Svada-mini – dokumentation

Svada-mini är den förenklade SVADA-PoC:en. Den följer dataprodukten **Modellerad bräddata**
från DHI:s modell (FCF) genom ett riktigt dataspace mellan DHI och Göteborgs Stad till att
staden använder data för analys och beslut, lokalt i Docker Compose, med riktiga komponenter
och protokoll: Dataspace Protocol, ODRL, NGSI-LD och verifierbara intyg (DCP). PoC:en är
referensimplementationen av *Målarkitektur SVADA v1.9* – en regressionsmiljö där arkitekturens
krav är uttryckta som körbara tester.

Sensorledet (MQTT, IoT-agent) och dataportalerna (CKAN, skördare, FAIR) ingår **inte**. Den
tidigare PoC:en med tio steg ingår inte i det här paketet.


## Läsvägen: tre nivåer

**Nivå 1 – överblick och användning.**

| Fil | Läs när du vill |
|---|---|
| [`01-oversikt.md`](01-oversikt.md) | förstå kedjan, rollerna, dataprodukten och komponenterna |
| [`02-kom-igang.md`](02-kom-igang.md) | installera, köra, verifiera och felsöka |
| [`03-demo.md`](03-demo.md) | visa systemet för publik |

**Nivå 2 – koncepten.**

| Fil | Täcker |
|---|---|
| [`05-dataomradet.md`](05-dataomradet.md) | steg 2–4: connectorn, DSP-katalogen, ODRL, KoV-spärren, hävning, transfer och ingest |
| [`07-folj-ett-varde.md`](07-folj-ett-varde.md) | samma bräddbrunn och samma avtal genom alla led – med faktiska API-svar |
| [`08-drift-identitet-skalning.md`](08-drift-identitet-skalning.md) | det tvärgående: identiteten, resursstrategin, driftfrågorna, skalningen |
| [`09-vad-ar-data-space.md`](09-vad-ar-data-space.md) | DSSC:s data space-teori, applicerad på PoC:en |

**Nivå 3 – referens.**

| Fil | Täcker |
|---|---|
| [`10-gapanalys.md`](10-gapanalys.md) | vad som skiljer PoC:en från målarkitekturens krav, gap för gap |
| [`11-verifiering.md`](11-verifiering.md) | testsviten och vad varje skript bevisar |
| [`12-fragor.md`](12-fragor.md) | frågorna som faktiskt ställs efter demon, med korta svar |
| [`13-ordlista.md`](13-ordlista.md) | kanonisk terminologi |
| [`14-dataprodukten.md`](14-dataprodukten.md) | dataproduktens specifikation och kvalitetsdeklaration, som katalogen pekar på |
| [`koncept/`](koncept/README.md) | konceptbiblioteket: tekniska fördjupningar med kodhänvisningar och `KONCEPT:`-ankare in i källkoden |

Hänvisningar på formen §N.N avser *Målarkitektur SVADA v1.9*, Göteborgs Stads arkitekturdokument
(följer inte med i det här paketet). Kodhänvisningar
(`services/…`, `edc/…`, `tests/…`) pekar in i repot.
