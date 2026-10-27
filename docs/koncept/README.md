# Konceptbiblioteket – teknisk fördjupning per koncept

**Syfte:** låta en teknisk läsare gå från *"jag kör demon"* till *"jag förstår
koden bakom steget och kan bygga det i produktion"* – med en tydlig hemvist per
koncept och spårbara hänvisningar till berörd kod, arkitektur, verifiering och
gap.

Detta är **navet** som binder ihop repots övriga dokument. Konceptdokumenten
skriver inte om det som redan står i kapitlen under `docs/` – de *pekar in* i
dem och tillför den topiska läsvägen som saknas. Hänvisningar till *Målarkitektur
SVADA v1.9* och dess §N.N (Göteborgs Stads arkitekturdokument; följer inte med i
det här paketet) gäller den arkitekturen.

> **Var biblioteket hör hemma i läsvägen.** Konceptbiblioteket är den
> tekniska djupnivån under kapitlen i [`docs/README.md`](../README.md).
> Börja där: nivå 1 (`01`–`03`) för överblick och körning, nivå 2
> (`05`–`09`) för mekanismerna per kedjesteg. Kommer du hit vill du se
> koden bakom ett enskilt koncept.

---

## 1. Hur de tre lagren hänger ihop

Terminologin är synkad genom ett enkelt kontrakt:

```
docs/13-ordlista.md       Lager 1: EN definition per begrepp. Källan för ordval.
        │  (samma term används i…)
        ▼
docs/koncept/NN-*.md      Lager 2: EN hemvist per koncept. Djupet bor här.
        │  (pekar på…)
        ▼
källkoden (KONCEPT-ankare) Lager 3: kodens egna förklaringar, greppbart märkta.
```

* **Manual och demo förblir slanka.** De får en kort ruta i slutet av berört
  avsnitt: `> **Under huven →** [konceptets namn](koncept/NN-slug.md)`. Prosan
  dupliceras inte – rutan är ett hopp, inte en sammanfattning.
* **Konceptdokumentet är den enda platsen** den tekniska prosan lever. Ordlistan
  ger en mening; koden ger mekanismen; konceptdokumentet ger förklaringen.
* **Synken är ett test.** `tests/verify_docs.sh` (körs av `verify_all.sh`) gör
  att lagren inte kan glida isär obemärkt – precis som `verify_ap*.sh` skyddar
  invarianterna.

---

## 2. Kod-ankare (lager 3)

Varje fil som är ett konceptdokuments **primära hemvist i koden** bär ett
greppbart ankare på exakt formen:

```
KONCEPT: docs/koncept/NN-slug.md
```

Tokenet fungerar i alla filtyper (Java-/shell-/Python-kommentar, JSON-sträng):

```java
// KONCEPT: docs/koncept/06-kov-gate.md
```
```json
"_kommentar": ["KONCEPT: docs/koncept/06-kov-gate.md", "…"]
```

**Regler (verifieras):**

1. Varje ankare måste peka på ett konceptdokument som finns.
2. Varje konceptdokument (utom denna README) måste vara måltavla för minst ett
   ankare.

**Varför ankare och inte radnummer:** radnummer ruttnar vid första
refaktorering. Hänvisningar sker till **fil + symbolnamn** (`KovGate.java` →
`ContractNegotiationPendingGuard`) eller till ett greppbart ankare – aldrig till
`fil:42`. En symbol överlever att kod flyttas; ett radnummer gör det inte.

---

## 3. Mall för ett konceptdokument (lager 2)

Varje `NN-slug.md` följer denna struktur. Avvik inte utan skäl – enhetlig form
gör biblioteket läsbart och synk-scriptet enkelt.

```markdown
# NN. Konceptets namn

> En mening: vad konceptet är och varför det finns.

## Begrepp
De kanoniska termer dokumentet använder, var och en länkad till ordlistan.

## Vad problemet är
Arkitekturkravet. Citat/hänvisning till Målarkitektur v1.9 §.

## Hur PoC:en löser det
Mekanismen i prosa. Det tunga "varför-just-så" som annars ligger begravt i en
tidigare arbetslogg – här topiskt, inte kronologiskt.

## Koden
Filer + symboler (de KONCEPT-ankrade). En tabell: fil → symbol → ansvar.

## Bevis
Vilket verify-testfall som bevisar konceptet + ett curl-exempel som läsaren
själv kan köra.

## Förenkling → produktion
Vad som är medveten PoC-förenkling och vad som ändras i skarp drift. Länk till
docs/10-gapanalys.md.

## Läs vidare
Relaterade konceptdokument (`[[NN-slug]]`).
```

---

## 4. Numrering och innehållsförteckning

Konceptdokumenten numreras mot **kedjans steg** (`docs/01-oversikt.md` §1.4; numren 01, 09 och 10 från den
tidigare tio-stegs-PoC:en finns inte i Svada-mini) plus en **C-serie för det tvärgående**. Då är konceptindexet samma karta som manualen
och demon redan använder.

| Nr | Koncept | Primär kod | Status |
|---|---|---|---|
| 02 | NGSI-LD, Smart Data Models, context broker | `services/ladda_brunnar/` | ✅ klar |
| 03 | FCF-modellen och framställning av Distribution A/B | `services/fcf-sim/` | ✅ klar |
| 04 | Informationsklassning (K/R/T) i dataprodukten | `services/fcf-sim/distributioner.py` | ✅ klar |
| 05 | DSP-katalog och ODRL-policyer | `edc/bootstrap/`, `edc/src/.../odrl/` | ✅ klar |
| **06** | **KoV-gaten: provider-sidig policyverkställighet** | `edc/src/.../kov/` | ✅ klar (pilot) |
| 07 | Transfer (HttpData-PUSH) och ingest-validering | `services/ingest-service/` | ✅ klar |
| 08 | Proveniens i CIP | `services/ingest-service/`, `services/fcf-sim/` | ✅ klar |
| C1 | Identitet och tillit (mock-IAM → verifierbar identitet) | `edc/src/.../MockIamSeedExtension.java` | ✅ klar |
| C2 | Resursstrategin (in-memory stores, heap-tak) | `.env`, compose-filerna | ✅ klar |
| C4 | Connectorn: kontrollplan, dataplan och de fyra API-ytorna | `edc/konfig/`, `edc/` | ✅ klar |
| C5 | Skalningen: från PoC till Sverige och EU (scenariodokument) | `edc/konfig/consumer.properties` (operatörsmönstret) | ✅ klar |
| C6 | Från laptop till drift: uthållighet, lagring och gallring | `.env`, compose-filerna | ✅ klar |

Piloten (06) är byggd först för att validera mall, ankarkonvention och
synk-script på ett verkligt fall innan resten skrivs. När mallen sitter är
övriga dokument mekaniskt arbete.

**Tre axlar, tre hemvister.** Frågan "hur skiljer sig PoC:en från produktion?"
har tre olika svar beroende på vad som avses, och de bor på olika ställen:

| Axel | Frågan som ställs | Hemvist |
|---|---|---|
| Arkitekturkrav vs implementation | *Uppfyller vi målarkitekturen?* | [`10-gapanalys.md`](../10-gapanalys.md), G-numren |
| Demoriggens rollspel | *Är IdentityHub verkligen DSGA:s tillitstjänst?* | [`01-oversikt.md` §1.6](../01-oversikt.md), [`03-demo.md` §3.4](../03-demo.md) |
| **Driftegenskaper** | *Försvinner data om något går sönder? Hur mycket blir det på ett år?* | **[C6](C6-drift-och-uthallighet.md)** |

Den tredje axeln saknade hemvist fram till 2026-07-27 och besvarades ad hoc i
kodkommentarer. Frågeingången till alla tre är [`docs/12-fragor.md`](../12-fragor.md).

---

## 5. Terminologiregeln (kortversion)

När ett begrepp förekommer i manual, demo, konceptdokument **och** kod ska det
skrivas **likadant**. Ordlistan (`docs/13-ordlista.md`) är auktoriteten. Några av
dessa termer är dessutom maskinellt låsta via `<!-- SYNK: ... -->`-direktiv i
ordlistan, som `verify_docs.sh` kontrollerar mot koden – så att en omdöpning i
koden utan motsvarande uppdatering i dokumenten blir rött.

---

*Konceptbiblioteket (12 koncept: 02–08 + C1, C2, C4–C6), Svada-mini 2026-10-10. Synk verifieras
av `tests/verify_docs.sh` i `verify_all.sh`. Svenska genomgående (hård regel 9).
C5 är ett scenariodokument (troligt framtidsläge), till skillnad från övriga som
beskriver byggd och verifierad kod. C6 beskriver driftaxeln – vad PoC:en
medvetet inte har – med siffror mätta på körande system.*
