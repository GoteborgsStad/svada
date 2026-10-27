# 11. Verifieringen: vad som är bevisat, och hur

PoC:en är byggd som en regressionsmiljö (§9.2): arkitekturens krav är
uttryckta som körbara tester, och **hård regel 11** säger att ett
arbetspaket är klart först när allt är grönt.

```bash
bash tests/verify_all.sh      # alla etapper, ~25 minuter
bash tests/verify_ap6b.sh     # bara kontrollrummet + fullkedjan
```

Skripten är idempotenta och startar själva de förutsättningar de behöver.

## 11.1 Vad varje skript bevisar

| Skript | Bevisar |
|---|---|
| `verify_ap0.sh` | Docker, Compose v2, WSL-minne, repo-struktur, testdata, git, och (0.6b, `tests/bildtaggar.py`) att varje `FROM`, `image:` och `*_IMAGE` har en uttrycklig tagg som inte är `latest`, med variablerna lösta mot `.env` |
| `verify_ap1.sh` | 91 brunnar i CIP, Krokängsparken rätt placerad, ingen brunn på `[0,0]`, temporal fungerar, persistens, resurstak, **åtkomstkontrollen framför CIP:en** |
| `verify_kedjevy.sh` | Den pedagogiska kedjevyn (K1b: svenska meddelanden översätts till engelska, `engelska_enhet.py`/`engelska_live.py`): ingen intern text och inga portnummer i den externa varianten, ljust tema, svenska och engelska, id/data-attribut, K21-prefixen, knapptäckning, ODRL-villkoren live, och i den externa varianten att inget API-svar innehåller port eller internt värdnamn (K14); ett krasch i delprovet ger rött (körs i `verify_all.sh`, före `verify_docs.sh`) |
| `tests/aterstall_enhet.py`, `aterstall_forsok.sh`, `skydd_enhet.py` (körs som K23 i `verify_kedjevy.sh`, utan stack) | Nedräkningens tidsberäkning (sommar-/vintertid, tidszon, ogiltigt värde), omslaget med nytt försök och upptidskontrollen, och skydden för den öppna ytan (ursprung, rättvis kö, automatisk återinsättning, avstängd felinjektion). Kontroll 9.9b i `verify_ap9.sh` prövar via Caddy att POST utan eget ursprung ger 403, att `cip.` är skrivskyddad (405) och att A:s tidsserie inte släpps ut. 9.9c prövar tidsseriens positiva allowlist med 13 fientliga frågor mot **verkligt laddade** A- och B-data (utan data: `[EJ PRÖVAT]`, som `verify_all` räknar som rött). 9.9d prövar avvisade, avbrutna och långsamma kroppar genom Caddy **inloggat**, med en positiv kontroll på samma transport, och mäter sidoeffekter med jobb-id och felinjektionens frist, inte listlängd. |
| `tests/sessioner_enhet.py` (K28 i `verify_kedjevy.sh`, utan stack) och `tests/sessioner_http.py` (K29, mot stacken) | En egen vy per besökare, inklusive tillståndsmaskinen för nästa åtgärd (avslag, hävning, nekad leverans, gallring av jobblistan): kakan (128 bitars slump, ogiltiga kakor ger ny session, tidsgräns, tak), jobbkön (en annan besökares jobb köas i ordning, högst ett jobb per besökare, kön har tak, utan session gäller det gamla), ägande av förhandlingar och avtal; K29: två besökare via proxyhuvud ser inte varandras jobb, KoV-förfrågningar, avtal, stegdetaljer, "Följ ett värde" eller `avtalA.gallande`, nekas (403) att besluta eller häva den andres, ingen rättvisepaus efter ett jobb för en besökare med egen vy (jobbkön ger rättvisan), och anrop direkt mot porten berörs inte; eget felinjektionsläge: slås på i FCF bara medan besökarens egen leverans körs och av direkt efteråt (även vid fel), utan session gäller det gemensamma läget (sessioner_enhet), och en besökare ser inte en annans läge och ingen gemensam timer (K29) |
| `tests/statistik_enhet.py` (K26 i `verify_kedjevy.sh`, utan stack), K27 i `verify_kedjevy.sh` och 9.12 i `verify_ap9.sh` | Statistik: räkningen (sidvisningar, inte polling; unika som kapad adress + webbläsare; robotar; avvisade = besökare som aldrig fick en sida; fel utan 429 och 409; begränsade 429; API-träffar; kampanj med tak; svensk tid; roterade och gzippade loggfiler; uteslutna adresser; trasiga filer flyttas åt sidan; 0644), historiken (dagar vars rålogg roterats bort finns kvar), händelsevitlistan och att räknaren bara sparar tal; K27: `/api/handelse` tar emot vitlistade händelser, räknar inte robotar, avvisar allt annat (400) och lagrar ingen IP eller text, `/statistik` svarar sv/en utan skript eller externa adresser, `/api/status` bär `avtalA`; 9.12: Caddys åtkomstlogg är giltig JSON utan kaka, lösenord, auktoriseringshuvud, vidarebefordringshuvuden, port, användarnamn eller okapad IP (alla filer lästa), och 30 händelser på rad via Caddy får inget 429; testläget (`?test=1`, kakan `svada-test`): loggrader med `test=1` och själva `?test=1`-anropet räknas inte (statistik_enhet), händelser med kakan räknas inte (K27j), Caddy sätter kakan och loggar fältet `test` utan att kakan finns i loggen (9.12t/u i `verify_ap9.sh`) |
| `tests/ngsild_enhet.py` (K30 i `verify_kedjevy.sh`, utan stack) | Ingest-tjänstens tolkning av Orion-LD:s svar: 207 godtas bara när `errors` är tom; trasig JSON, lista eller sträng, avbruten läsning och icke-tom `errors` ger `OrionFel` (502, aldrig LEVERERAD) |
| K27j i `verify_kedjevy.sh` | Statistiksidan: stegnamnen kommer ur samma texter som kontrollrummet (svenska och engelska, "Step 1" i stället för "Steps 1") |
| `tests/version_enhet.py` och K31 i `verify_kedjevy.sh` | Versionsnumret: `.env` är källan, översta posten i `nyheter.py` är samma version, formatet ÅÅÅÅ.MM.DD-N, nyast överst; `/api/status`, `/nyheter`, kontrollrummets och brunnsvyns sidfot bär versionen |
| `tests/portforskjutning_enhet.py` (K32 i `verify_kedjevy.sh`, utan stack) | Portförskjutningen (`tools/portforskjutning.py`): värdportarna läses ur compose-filerna, varje portvariabel i `.env` är klassad (en ny oklassad fäller provet), interna portar står aldrig på värdsidan, alla värdportar flyttas lika mycket utan krock med de gamla, `DEMO_URL_PORT` följer Caddyporten, förskjutning 0 ändrar inget, fel upptäcks |
| `tests/skydd_integration.py` (K24, i dashboard-imagen utan nätverk), `tests/vy_handelser_webblasare.mjs` (K25, isolerad fixtur) och `tests/mutationsprov.sh` | Skydden i den **riktiga appen**: middleware, rutter, jobbmodul och städning med styrd klocka och stubbade källor (avbruten kropp, paus efter jobb, absolut frist, idempotens, återhämtning, städning efter källfel, klartext vid nekad stad, okänt avtal). Avsnitt 4b: samordnarens utestängning är avstängd i den externa varianten (403 via Caddy, orörd statuslista, direkt mot porten som förut), och mutationerna M32–M34 (spärren borttagen, för bred, påslagen som standard) gör det rött; fixturen i K25 prövar samordnarrutans knappar, omritning, fel, omläsning och nedräkning när utestängning får användas. Sedan del a2 även kroppskontroll på alla skrivande rutter, trådscheman med `Event` (korsande anrop, samtidiga uteslutningar, gammal ögonblicksbild), pausen vid antagning, en loop-ticker mot blockerande källanrop och felklassningen. K25 prövar att id:n med apostrof, citattecken, backslash och radslut aldrig körs som kod. `mutationsprov.sh` planterar ett fel i taget (se skriptet för listan) i en kopia av koden och kräver att rätt test blir rött för vart och ett. |
| `verify_ap3.sh` | Batch täcker 91 brunnar, A har GIS, **B saknar brunns-GIS**, sensorbrunnen bygger på mätvärden ur CSV-filerna, batchproduktion där **varje batch modellerar ett eget dygn**, felinjektionslägen, default av |
| `verify_ap4a.sh` | Connectorer friska, DSP-katalog med ODRL-offert, dataplanskoppling, `MEDVETEN FÖRENKLING` markerad, JVM-tak |
| `verify_ap4b.sh` | B finaliseras automatiskt, **A stannar hos providern**, KoV-godkännande på provider-sidan, **ingen consumer-bakväg**, avslag möjligt |
| `verify_ap4c.sh` | E2E för B, proveniens satt, transfer utan avtal avvisas, A gate:ad hela vägen, **felinjektion fångas**, tidsserier ackumuleras |
| `verify_ap6b.sh` | Kontrollrummet uppe, statusvyn speglar verkligheten, KoV-knappen, villkoren för A, **steg 6: inspektionsprioriteringen** (B öppet utan positioner, A med positioner bara med gällande avtal, nekat efter hävning), auditlogg |
| `verify_ap8_fas3.sh` | Svadas utfärdare och intygstyper per utfärdare: medlems- och deltagarintyg har Svadas DID som utfärdare, rollintyget har organisationens egen, två negativa tester (Svada kan inte intyga en roll, staden kan inte självutfärda medlemskap) |
| `verify_ap11.sh` | **Återkallelse av intyg:** Svadas utfärdare publicerar en signerad statuslista; bara samordningsrollens nyckel får ändra den; återkallas stadens medlemsintyg nekar DHI staden (401), återinsätts det fungerar allt igen utan omstart; återkallas DHI:s intyg avvisar staden DHI och ett nytt avtal ingås inte; samordnaren agerar från kontrollrummet |
| `verify_ap10.sh` | **Avtal gäller tills de hävs:** avtalets id skiljer sig mellan DHI och staden (kopplas via förhandlingen), stadens avtalsregister med ODRL-ögonblicksbild och löstbar adress, ett avslag av en ny begäran om A häver tidigare avtal (när regeln är på; med `SVADA_KOV_AVSLAG_HAVARTIDIGARE=false`, som i den delade demon, bevisas i stället att avslaget inte häver något), efter hävningen ingen ny nyckel och den gamla nyckeln hämtar ingen data (HTTP 403), **DHI:s connector stoppar en överföring på hävt avtal**, KoV häver direkt (401 utan rollintyg), B påverkas inte |

## 11.2 Invarianterna och deras testfall

| Invariant | Var den verkställs | Nyckelbevis |
|---|---|---|
| 1. Suveränitet | `edc-provider` (KovGate), `stad-gateway` | 4b.2 (A står kvar i `REQUESTED`/`pending`), 4b.4 (consumerns KoV-anrop ger 404), 1.8 (A:s adress ger 403 utan nyckel), 10.5 (hävt avtal: ingen nyckel, ingen överföring) |
| 2. Integritet i klassningen | `fcf-sim` (framställning), `ingest-service` (kontroll vid mottagning) | 3.4 (B saknar `location`/`sourceSrs`, inte ens som råtext), 4c.5 (felinjektionen `gis_i_b` avvisas, inget skrivs) |
| 3. Ett avtal gäller tills det hävs | `edc-provider` (HavdAvtalSparr), `ingest-service` (avtalsregister), `stad-gateway` | 10.1–10.11 i `verify_ap10.sh` (10.11: giltighetstiden, avtalet blir UTGANGET och överföringen nekas): id olika hos DHI och staden, staden läser en smal status med egen nyckel (inte management-API:t), avslag häver tidigare avtal (när regeln är på), ingen ny nyckel, gammal nyckel ger 403, DHI stoppar överföringen, stängt som standard |

## 11.3 Dokumentsynken

`verify_docs.sh` (körs av `verify_all.sh`) håller dokumentation, ordlista
och kod ihop. Ordlistan ([`13-ordlista.md`](13-ordlista.md)) är källan
till sanning för ordval, och ett antal termer är maskinellt låsta till
strängar som måste förekomma i koden – till exempel
`svada:kovGodkannande`, `ContractNegotiationPendingGuard`,
`brunns-gis-i-distribution-b`, `K1R1T1`/`K0R1T1` och `HttpData-PUSH`. En
omdöpning i koden utan uppdaterade dokument blir rött. Kodfiler som är
ett koncepts primära hemvist bär dessutom ett greppbart ankare
(`KONCEPT: …`), och hänvisningar sker till fil + symbolnamn, aldrig till
radnummer – en symbol överlever att kod flyttas.

## 11.4 Vad ett grönt resultat betyder (och inte betyder)

`verify_all.sh` kör en **lista över obligatoriska skript** (manifestet i skriptet). Saknas ett skript, eller skriver något skript
`[HOPPAR ÖVER]`, `[EJ PRÖVAT]` eller "ej tillämpligt", är slutstatusen **röd**: grönt betyder fullständigt prövat. `VERIFY_TILLAT_HOPP=1`
tillåter hopp i en snabb lokal körning, och utskriften säger då att sviten inte är fullständigt prövad. Två saker är medvetet
utanför: `verify_hash_kedja.sh` (dess huvudprov mixtrar med auditkedjan i testläge och körs bara i en isolerad stack) och
återställningens egen hälsokontroll (`aterstall-demo.sh` kör `verify_ap9.sh` i rent läge, där `[EJ PRÖVAT]` för 9.9c är väntat).

Testerna är av fyra slag, och ett grönt resultat bevisar olika mycket beroende på slag:

| Slag | Exempel | Bevisar | Bevisar inte |
|---|---|---|---|
| Enhetstest (utan stack) | `skydd_enhet.py`, `aterstall_enhet.py`, `fcf_csv_enhet.py`, `engelska_enhet.py`, `kedjevy_rendering.py` | En funktion gör rätt för givna indata | Att funktionen är inkopplad |
| Integration i processen | `skydd_integration.py` (K24) | Att appens delar är kopplade (middleware → rutt → jobb → skydd → städning) | Verklig proxy, verklig klocka, verkliga källor |
| Mot den körande stacken | `verify_ap*.sh`, K14, 9.9c/9.9d genom Caddy | Beteendet i den riktiga kedjan | Annat än de prövade indata; multi-IP-rättvisa och belastning är inte prövade |
| Visningstest i webbläsaren | `kedjevy_webblasare.mjs` | Det sidan visar, ofta mot **mockade** API-svar | Att servern svarar så; det bevisas av raderna ovan |

Kvar som otestat: flera verkliga klient-IP:n, uthållig belastning och minne, riktig
04:00-växling och verklig underhållssida under en nollställning.

**Testernas sidoeffekter:** `verify_ap6b`, `verify_ap10`, `verify_ap11` och webbläsartestet startar jobb, förhandlar, häver avtal,
återkallar intyg och ändrar avtalsgiltigheten. De vägrar köra mot ett tomt prefix eller originalets `svada` och mot en stack som inte
körs (`kontrollera_mal` i `tests/lib.sh`), städar även vid avbrott (avtalsgiltigheten efter `verify_ap10`, intygen efter `verify_ap11`), och `verify_all.sh` tar
ett lås så att två körningar inte stör varandra. Kör dem bara mot en lokal stack som ingen annan använder.

