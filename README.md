# Svada-mini

**Svenska** · [English below](#english)

Svada-mini är en lokal, fungerande demonstration av hur ett dataspace för VA-data kan se ut: mätning och modellering hos en leverantör (DHI,
simulerad), ett avtal och ett godkännande hos dataägaren (KoV), en överföring mellan två Eclipse EDC-connectorer enligt Dataspace Protocol
(ODRL-villkor, verifierbara intyg), stadens plattform (Orion-LD och Mintaka) och en analys som visar hur avtalet styr användningen av data.
Det är framtaget av projektet SVADA (Göteborgs Stad) för att visa vilka komponenter som behövs och hur de hänger ihop.

> **Status: demonstration, "som det är".** Allt data är syntetiskt eller godkänt som öppna data, och flera delar är medvetna förenklingar (till
> exempel en simulerad utfärdare av intyg som inte är förankrad i eIDAS, återkallelselistor som ligger i minnet, EDC-lager i minnet och en
> hävningsregel som inte finns i Dataspace Protocol). Det är **inte** en färdig produkt och ska inte användas för riktiga data. Ingen
> support eller förvaltning utlovas. Se [SECURITY.md](SECURITY.md).

## Kom igång

Krav: Docker (Engine eller Desktop) med Compose v2, `bash` och `python3`. På Linux sätter `tools/forsta-start.sh` värdportarna till Docker-bryggans adress (annars når kontrollrummet inte sina komponenter). Stacken använder omkring 2 GiB minne när den kör (mätt på en utvecklardator);
det första bygget är tyngre, så ge Docker minst 8 GiB. Det exakta minimikravet är inte uppmätt.

```bash
git clone https://github.com/GoteborgsStad/svada.git svada-mini
cd svada-mini
bash tools/forsta-start.sh     # skapar .env ur .env.exempel och slumpar fram hemligheterna
bash starta-demo.sh            # bygger och startar kedjan (första gången flera minuter)
```

Öppna kontrollrummet på <http://localhost:38800>. Det finns också en proxy med lösenordsgrind på `http://svada-demo.localhost:38080`; användarnamn och
lösenord ligger i `.demo-losenord`. Stoppa med `bash stoppa-demo.sh` (raderar ingen data). Nollställ med `bash aterstall-demo.sh`.

**Obs:** att köra från noll på en ren maskin är **inte provat än** (det är bara provat i utvecklingsmiljön). Skriv gärna ett ärende om något saknas.

## Vad som finns

* `services/` kontrollrummet, stadens gateway och mottagning, FCF-simulatorn, publika vyn
* `edc/` och `identity-hub/` anpassningar av Eclipse EDC och IdentityHub (KoV-spärren hos providern, hävning, avtalsstatus, intyg)
* `compose.*.yml`, `starta-demo.sh`, `stoppa-demo.sh`, `aterstall-demo.sh` hur kedjan startas
* `tests/` verifieringen: `bash tests/verify_all.sh` (cirka 40 minuter, kräver en körande stack och Chrome för webbläsarproven)
* `docs/` dokumentationen, med [docs/README.md](docs/README.md) som ingång

## Varianter

`DEMO_VARIANT` i `.env` väljer vy: `extern` (standard i `.env.exempel`) är läget för en delad, publik server: inga portnummer eller interna hänvisningar i
sidorna och samordnarens utestängning avstängd (steg 3 visar ett inspelat exempel). `intern` visar knapparna för att stänga ute en deltagare.
Testsviten är skriven för `extern`.

## Licens

[Apache-2.0](LICENSE) för koden i det här repot. Komponenterna som hämtas som images har egna licenser: se [TREDJEPART.md](TREDJEPART.md) och [NOTICE](NOTICE).

**Ansvar.** Du ansvarar själv för dina installationer och för att följa licenserna för de komponenter du hämtar, bygger och kör, i synnerhet AGPL (Orion-LD, Mintaka) och SSPL (MongoDB) om du erbjuder dem som en tjänst till andra. Licensbedömningen i [TREDJEPART.md](TREDJEPART.md) är gjord av projektet och **inte juridiskt granskad**.

## Kända begränsningar

* **EDC är låst på 0.17.0.** Nästa stora version (1.0) tar bort det inbyggda dataplanet som överföringen här bygger på, så ett byte är ett eget arbete. Det är inte säkert att vi gör det.
* **Orion-LD är på väg att ersättas.** Underhållaren har meddelat (2026-09-25, [ärende #280](https://github.com/FIWARE/context.Orion-LD/issues/280)) att Orion-LD går i underhållsläge, med felrättningar men troligen inga nya funktioner, och pekar på en ny mäklare, [coraine](https://github.com/SEAMWARE/coraine), som ersättare. Coraine finns ännu inte i någon stabil version (senast 0.5.0 vid vår undersökning i oktober 2026), så det är inte dags att byta än, och vi har inte lovat att göra det.
* **Ingen säkerhetsprocess.** Det finns ingen utsedd säkerhetsansvarig, ingen garanterad privat kanal för sårbarhetsrapporter och inga säkerhetsuppdateringar. Se [SECURITY.md](SECURITY.md).
* **Mintaka är arkiverad uppströms** (sedan 2026-05-13) men behövs för historiken (NGSI-LD temporal), som Orion-LD inte svarar på själv. Följ uppströmsprojektet.
* **MongoDB 7.0 kräver att Orion-LD körs med `-mongocOnly`** (så är det inställt), och MongoDB 7.0 stöds till 2027-08; databasen nås bara från stadens interna nät i den här demon.
* **Ingen oberoende granskning av en människa.** Koden har granskats med automatiska verktyg (projektets egna prov, en granskningsagent och en hemlighetsskanning), inte av en utomstående människa. Läs koden själv innan du förlitar dig på den.
* **Inte provat av någon utomstående på en ren maskin.** Följ [docs/02-kom-igang.md](docs/02-kom-igang.md) och rapportera gärna vad som inte fungerar.

## Upphov och tack

Svada-mini är framtaget inom **[Vattendatalabbet (SVADA)](https://vattendatalabbet.se)** (Göteborgs Stad), i samarbete med [RISE](https://www.ri.se/en/infrastructure/water/project/swedish-water-data-lab-svada-transition-for-smart-water-management).

**Upphovspersoner**
* **Björn Hagström**, expert på informationshantering och data spaces ([GitHub](https://github.com/bjornhagstrom))
* **Niklas Fjellman**, utvecklingsledare data, Göteborgs Stad

**Finansiärer av SVADA:** [Energimyndigheten](https://www.energimyndigheten.se), [Formas](https://www.formas.se), [Vinnova](https://www.vinnova.se) och [Water Wise Societies](https://waterwisesocieties.se). Projektbeskrivning hos [Vinnova](https://www.vinnova.se/en/p/the-swedish-water-data-lab-svada--transition-for-smart-water-management).

Om du använder eller bygger vidare på det här arbetet, behåll [NOTICE](NOTICE) och nämn gärna SVADA-projektet och upphovspersonerna. En färdig referens finns i
[CITATION.cff](CITATION.cff).

---

## English

Svada-mini is a local, working demonstration of what a data space for water and wastewater data can look like: measurement and modelling at a provider
(DHI, simulated), an agreement and an approval at the data owner (KoV), a transfer between two Eclipse EDC connectors using the Dataspace Protocol
(ODRL policies, verifiable credentials), the city's platform (Orion-LD and Mintaka), and an analysis that shows how the agreement governs the use of
data. It was made by the SVADA project (City of Gothenburg) to show which components are needed and how they fit together.

> **Status: a demonstration, "as is".** All data is synthetic or approved as open data, and several parts are deliberate simplifications (for example
> a simulated credential issuer that is not anchored in eIDAS, revocation lists kept in memory, in-memory EDC stores and a revocation rule that does
> not exist in the Dataspace Protocol). It is **not** a finished product and must not be used for real data. No support or maintenance is promised.
> See [SECURITY.md](SECURITY.md). Most documentation is in Swedish.

**Quick start** (requires Docker with Compose v2, `bash`, `python3`; about 2 GiB of memory while running, give Docker at least 8 GiB for the first build —
the exact minimum is not measured):

```bash
git clone https://github.com/GoteborgsStad/svada.git svada-mini && cd svada-mini
bash tools/forsta-start.sh     # creates .env from .env.exempel and generates random secrets
bash starta-demo.sh            # builds and starts the chain (several minutes the first time)
```

Open the control room at <http://localhost:38800>. Stop with `bash stoppa-demo.sh` (deletes no data); reset with `bash aterstall-demo.sh`.
Running from scratch on a clean machine has **not been tested yet** (only in the development environment).

Licence: [Apache-2.0](LICENSE) for the code in this repository; the images that are pulled have their own licences, see [TREDJEPART.md](TREDJEPART.md).

**Responsibility.** You are responsible for your own installations and for complying with the licences of the components you pull, build and run, in particular AGPL (Orion-LD, Mintaka) and SSPL (MongoDB) if you offer them as a service to others. The licence assessment in [TREDJEPART.md](TREDJEPART.md) was made by the project and has **not been legally reviewed**.

### Known limitations

* **EDC is pinned to 0.17.0.** The next major version (1.0) removes the embedded data plane that the transfer here relies on, so an upgrade is a piece of work of its own. We may not do it.
* **Orion-LD is about to be replaced.** The maintainer has announced (2026-09-25, [issue #280](https://github.com/FIWARE/context.Orion-LD/issues/280)) that Orion-LD is entering maintenance mode, with bug fixes but probably no new features, and points to a new broker, [coraine](https://github.com/SEAMWARE/coraine), as its successor. Coraine is not yet in a stable version (latest 0.5.0 when we looked in October 2026), so it is not time to switch yet, and we have not promised to do it.
* **No security process.** There is no designated security contact, no guaranteed private channel for vulnerability reports and no security updates. See [SECURITY.md](SECURITY.md).
* **Mintaka is archived upstream** (since 2026-05-13) but is needed for the history (NGSI-LD temporal), which Orion-LD does not answer itself. Follow the upstream project.
* **MongoDB 7.0 requires Orion-LD to run with `-mongocOnly`** (it is set up that way), and MongoDB 7.0 is supported until 2027-08; in this demo the database is reachable only from the city's internal network.
* **No independent human review.** The code has been reviewed with automated tools (the project's own tests, a review agent and a secret scan), not by an outside person. Read the code yourself before relying on it.
* **Not tried by an outside person on a clean machine.** Follow [docs/02-kom-igang.md](docs/02-kom-igang.md) and please report what does not work.

### Credits

Svada-mini was created within **[the Swedish Water Data Lab (SVADA)](https://vattendatalabbet.se)** (City of Gothenburg), in cooperation with [RISE](https://www.ri.se/en/infrastructure/water/project/swedish-water-data-lab-svada-transition-for-smart-water-management).

**Authors**
* **Björn Hagström**, expert on information management and data spaces ([GitHub](https://github.com/bjornhagstrom))
* **Niklas Fjellman**, development lead, data, City of Gothenburg

**SVADA is funded by** the [Swedish Energy Agency](https://www.energimyndigheten.se) (Energimyndigheten), [Formas](https://www.formas.se), [Vinnova](https://www.vinnova.se) and [Water Wise Societies](https://waterwisesocieties.se). Project description at [Vinnova](https://www.vinnova.se/en/p/the-swedish-water-data-lab-svada--transition-for-smart-water-management).

If you use or build on this work, keep the [NOTICE](NOTICE) file and please acknowledge the SVADA project and the authors. A ready-made reference is in
[CITATION.cff](CITATION.cff).
