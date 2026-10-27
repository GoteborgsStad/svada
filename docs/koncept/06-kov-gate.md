# 06. KoV-gaten: provider-sidig policyverkställighet

> Distribution A får inte lämna DHI förrän dataägaren (Kretslopp och Vatten)
> har godkänt det – och det beslutet verkställs i **providerns** connector, inte
> hos mottagaren. KoV-gaten är den mekanism som pausar kontraktsförhandlingen
> tills beslutet finns.

Detta är kedjans **steg 3** (`docs/01-oversikt.md` §1.4; demominut 7–12) och realiseringen av
**arkitekturinvariant 1: suveränitet**.

## Begrepp

Termerna nedan är definierade i [ordlistan](../13-ordlista.md): **KoV-gaten**,
**KoV-godkännande**, **Data Rights Holder**, **kontraktsförhandling**, **ODRL**,
**Dataspace Protocol**, **connector**. Använd dem likadant i manual, demo och kod.

## Vad problemet är

Målarkitektur v1.9 §6.2 slår fast designbeslutet:

> "Den tillhandahållande partens kontrollplan äger policyverkställigheten.
> Kontraktsförhandlingen för en behörighetsstyrd distribution stannar därför hos
> tillhandahållaren tills dataägarens godkännande har registrerats där.
> Konsumenten kan aldrig ensidigt finalisera sin egen åtkomst."

§6.4 preciserar tillståndsförloppet, och §6.6 gör suveräniteten till en
invariant som verifieras kontinuerligt. Komponentplanen kodifierar det som
**hård regel 7**: *"KoV-godkännandet för Distribution A implementeras på
PROVIDER-sidan – aldrig på consumer-sidan."*

Kravet är alltså inte bara *att* A ska godkännas, utan *var* beslutet verkställs:
i DHI:s connector, vid källan. En lösning som lät consumern finalisera sig själv
efter ett godkännande någon annanstans skulle bryta invarianten även om den
formellt "krävde godkännande".

## Hur PoC:en löser det

Eclipse EDC har en inbyggd förlängningspunkt för exakt detta:
`ContractNegotiationPendingGuard`. Providerns statsmaskin kör guarden före varje
processteg i en förhandling. Returnerar guarden `true` sätts
`negotiation.pending = true`, och posten filtreras bort ur statsmaskinens frågor
– den ligger kvar i `REQUESTED` och rör sig inte förrän någon sätter
`pending = false`. Det *är* "förhandlingen pausar hos DHI:s connector".

Tre designval bär lösningen:

1. **Utlösaren är ODRL-policyn, inte ett asset-id.** Gaten biter på en
   förhandling vars kontraktsoffert bär obligationen `svada:kovGodkannande`.
   Policyn *deklarerar* kravet; gaten *verkställer* det. Registrerar man fler
   K1-produkter i framtiden behöver gatens kod inte ändras.

2. **Samma image, olika roll via konfiguration.** Provider och consumer kör
   samma jar. Gaten och dess `/kov`-endpoints aktiveras bara av inställningen
   `svada.kov.gate.enabled=true`, som **enbart** står i
   `edc/konfig/provider.properties`. Därför har consumern (port 29193) ingen
   `/kov`-endpoint alls – det finns ingen bakväg (verifieringens testfall 4b.4).

3. **Gaten biter bara i `REQUESTED` och på provider-sidan.** Andra tillstånd
   måste släppas igenom, annars skulle även ett *avslag* (som går via
   `TERMINATING`) fastna.

Alternativen som valdes bort – en ODRL-constraint som returnerar `false` (ger
`TERMINATED` direkt, fel semantik) och en proxy framför management-API:t (hade
inte pausat något, bara legat utanför connectorn) – dokumenteras i
klassens egen header.

## Koden

Primär hemvist: `edc/src/main/java/se/goteborg/svada/edc/kov/` (KONCEPT-ankrad).

| Fil | Symbol | Ansvar |
|---|---|---|
| `KovGate.java` | `KovGate implements ContractNegotiationPendingGuard` | Själva gaten. `test()` avgör om en förhandling ska pausa; `kraverGodkannande()` letar efter ODRL-obligationen; `registrera()`/`beslut()` håller besluten (in-memory). |
| `KovController.java` | `KovController` (`@Path("/kov")`) | Providerns management-API: `GET /forhandlingar` (kön), `POST /forhandlingar/{id}/godkann` → FINALIZED, `POST /forhandlingar/{id}/avsla` → TERMINATED. |
| `KovGateExtension.java` | `KovGateExtension` | Kopplar in gaten (`@Provider` som slår ut EDC:s default `it -> false`) och registrerar controllern – men **bara** när `svada.kov.gate.enabled=true`. |

Utlösaren – ODRL-termen – definieras separat:

| Fil | Symbol | Ansvar |
|---|---|---|
| `edc/src/main/java/se/goteborg/svada/edc/odrl/SvadaOdrlExtension.java` | `ACTION_KOV_GODKANNANDE = "https://svada.goteborg.se/ns/kovGodkannande"` | Registrerar SVADA:s egna ODRL-termer. `KovGate` importerar konstanten – termen finns på ett ställe. |
| `edc/bootstrap/policy-distribution-a.json` | `obligation: svada:kovGodkannande` | A-policyn som *deklarerar* kravet gaten verkställer. |

Anropskedjan i demon: kontrollrummets **KoV-knapp** (komponent 14) →
`POST :19193/management/kov/forhandlingar/{id}/godkann` → `KovController.godkann()`
→ `KovGate.registrera(GODKAND)` → nästa gång statsmaskinen kör guarden släpps
förhandlingen och når `FINALIZED`.

## Bevis

`tests/verify_ap4b.sh` (testfallen 4b.0–4b.6):

* **4b.2** – A står kvar i `REQUESTED` med `pending=true` efter 30 s, utan avtal.
* **4b.3** – efter `POST .../godkann` når A `FINALIZED`.
* **4b.4** – samma anrop mot **consumerns** 29193 ger **HTTP 404**: ingen bakväg.
* **4b.5** – `POST .../avsla` ger `TERMINATED` med skäl.

Kör själv (kräver att kedjan är uppe och `registrera-edc` körd, se [`02-kom-igang.md`](../02-kom-igang.md)):

```bash
# KoV-kön hos providern
curl -s localhost:39193/management/kov/forhandlingar | jq .

# Godkänn en väntande A-förhandling
curl -s -X POST localhost:39193/management/kov/forhandlingar/<id>/godkann | jq .

# Bevisa att consumern saknar endpointen (ska ge 404)
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST localhost:39393/management/kov/forhandlingar/<id>/godkann
```

## Avtal gäller tills de hävs (gren avtal-havning)

Ett avtal om A gäller **tills det hävs**, inte bara för en enda datahämtning. Hävningen sker på
**providerns** sida (hård regel 7), i `KovGate`/`KovController`:

* **Avslag häver tidigare avtal.** Ett avslag av en ny begäran om A häver de gällande avtalen om
  samma tillgång och samma part (`havTidigareAvtal`, orsak `AVSLAG`). Det är en **PoC-regel** och en
  MEDVETEN FÖRENKLING: i ett riktigt dataområde kan hävning kräva en egen åtgärd. Regeln kan stängas av med `SVADA_KOV_AVSLAG_HAVARTIDIGARE=false` (flaggan `svada.kov.avslag.havartidigare` i providern); den är avstängd i den delade demon, där ett avslag annars skulle häva andra besökares avtal.
* **KoV häver direkt.** `POST /management/kov/avtal/{id}/hav` (kräver KoV-rollintyget, 401 annars,
  orsak `EXPLICIT`). `GET /management/kov/avtal` listar avtalen med status `GALLANDE`/`HAVT`.
* **Providern stoppar överföringen.** `HavdAvtalSparr` är en `PolicyRuleFunction` på plikten
  `kovGodkannande` i scopet `transfer.process`; ett hävt avtal ger `reportProblem` och
  överföringen blir `TERMINATED` (bevisat i `verify_ap10.sh` 10.5d).
* **Staden.** `ingest-service/avtalsregister.py` håller en kopia av statusen (synkas från providern
  ungefär varje sekund – PoC-förenkling) och en ODRL-ögonblicksbild per avtal. Ingen ny nyckel ges
  för ett hävt avtal, och `stad-gateway` kontrollerar statusen vid **varje** användning av en nyckel
  (stängt som standard: kan statusen inte bekräftas nekas åtkomsten). En nyckel får alltså finnas så
  länge den inte kan användas för att hämta data.
* **Id:n skiljer sig.** Uppmätt i EDC 0.17.0: avtalets id är **olika** hos DHI och staden, och
  förhandlingens id likaså. Det enda som binder ihop sidorna är att stadens förhandlings-id är DHI:s
  `correlationId`; registret kopplar avtalen den vägen. Stadens id är det som följer med data
  (`contractAgreementId`, plus `contractAgreementUrl` till avtalssidan i kontrollrummet).
* **Vad säger DSP?** Specifikationen (contract.negotiation.protocol) har sju tillstånd; `TERMINATED`
  är ett slutläge som någon av parterna kan sätta med termination-meddelandet, och beskrivs som att
  avbryta förhandlingen (”cancelled the Contract Negotiation sequence”). Den säger också att
  händelser **inte** är avsedda för att sprida ett avtals status efter att förhandlingen nått ett
  slutläge. Någon definierad hävning av ett slutfört avtal finns alltså inte i DSP 2025-1, så
  hävningen här är en egen mekanism. **Ej undersökt i EDC 0.17.0:s källa:** om policy-monitor och
  terminering av pågående överföringar kan ersätta den; det är en öppen punkt.

## Giltighetstid och revisionsskyldighet (2026-10-11)

* **Giltighetstid.** Policyn för A bär `inForceDate gteq contractAgreement+0s` och
  `inForceDate lteq contractAgreement+30d` (registrera-edc, `AVTAL_GILTIGHET`). EDC verkställer
  den hos providern vid varje överföring (en överföring efter utgången blir `TERMINATED`).
  Stadens avtalsregister läser samma villkor (`giltighet_s` i `avtalsregister.py`), räknar ut
  `giltigTill` och sätter status `UTGANGET`, så att gatewayen nekar (403 `avtal-utgatt`) också för en
  nyckel som utfärdades före utgången. En hävning går före utgången.
* **Revisionsskyldighet.** Policyn för A bär obligationen `svada:medgerGranskning`. Den är bunden
  i `SvadaOdrlExtension` men utvärderas av ingen funktion: det är en deklaration som hör till
  datadelningsavtalet. En obunden regel hade tagits bort tyst av EDC:s scope-filter.

## Förenkling → produktion

**Medveten förenkling:** sedan de nyckelskyddade management-API:erna och DCP-identiteten kräver management-API:t en nyckel (`X-Api-Key`) och
KoV-besluten dessutom ett verifierat rollintyg (`SvadaRoleCredential`), men *stadens*
IdentityHub utfärdar KoV-rollen åt KoV (se [`C1-identitet.md`](C1-identitet.md)) och
ingest-servicen i staden pollar providerns smala statusendpoint (`AvtalsstatusController`,
eget api-sammanhang med egen skrivskyddad nyckel, så att staden inte håller management-nyckeln)
för att läsa avtalsstatus (gapanalysens **G1**, delvis stängd, och **G23**). I produktion ska
rollen intygas av en part med mandat och statusen nå staden genom protokollet eller en
signerad statuslista.

**In-memory stores (§3.3):** besluten ligger i `KovGate`:s minne och nollställs
när providern startas om – därför måste `registrera-edc` köras om och ett nytt
A-godkännande ges efter varje omstart (se [`02-kom-igang.md`](../02-kom-igang.md)). Persistent lagring
är ett dokumenterat senare påslag.

## Läs vidare

* Gotcha: PolicyEquality och de bortvalda alternativen (se ovan).
* Relaterat: [[05-dsp-odrl]] (planerad) – hur ODRL-offerten byggs och annonseras.
