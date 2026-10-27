# 2. Kom igång: installera, köra och felsöka

## 2.1 Förutsättningar

| Krav | Kontroll |
|---|---|
| Docker Engine eller Docker Desktop/OrbStack med minst 8 GiB minne | `docker info` |
| Docker Compose v2 | `docker compose version` |
| `curl`, `jq`, `python3`, `git` | `command -v curl jq python3 git` |
| Repot med `data/` (GeoPackage + brunn 4526:s två CSV-serier) | `ls data/` |

På Windows används WSL2 Ubuntu med Docker Engine i WSL (repot i WSL-filsystemet, aldrig
`/mnt/c/`) och WSL ska se minst 18 GiB (`.wslconfig`).

Katalogen `data/` ska innehålla `dbsvadaexample.gpkg` (91 bräddbrunnar) och Krokängsparkens
två CSV-serier. FCF läser CSV-serierna direkt; det finns inget sensorled.

## 2.2 Starta

Svada-mini har prefixet `svadamini` (egna images, containrar och volymer), så den kan
ligga bredvid den historiska bilden utan att skriva över den. Kör en stack åt gången: de
delar portar.

```bash
bash starta-demo.sh        # Svadas utfärdare först, sedan DHI, staden, kontrollrummet
```

Skriptet kontrollerar `.env`, bygger images (`up --build`), startar i rätt ordning och
kör engångsjobben (`ladda-brunnar`, `registrera-edc`). Samma sak för hand:

```bash
set -a; . ./.env; set +a
docker network create ${SVADA_PREFIX}-dsp-public          # en gång
# 0. Svadas utfärdare FÖRST (DHI och staden hämtar sina intyg därifrån)
docker compose -f compose.dsga.yml --profile dsga-utfardare up -d --wait
# 1. DHI: FCF + provider-connector
docker compose -f compose.dhi.yml --profile dhi-fcf --profile dhi-identitet --profile dhi-edc up -d
# 2. Staden: plattform, consumer-connector, ingest
docker compose -f compose.stad.yml --profile stad-dataplan --profile stad-identitet \
  --profile stad-edc --profile stad-ingest up -d
# 3. Kontrollrummet
docker compose -f compose.kontrollrum.yml --profile dashboard up -d
# Engångsjobben
docker compose -f compose.stad.yml --profile laddning run --rm ladda-brunnar
docker compose -f compose.dhi.yml --profile edc-bootstrap run --rm registrera-edc
```

Öppna kontrollrummet på <http://localhost:38800>. Rubriken ska visa **"6 av 6 komponenter
svarar"**. Samma kontroll i terminalen:

```bash
curl -s localhost:38800/api/status | jq '[.komponenter[] | select(.status != "upp")]'
```

## 2.3 Regeln att komma ihåg

> **`registrera-edc` måste köras om varje gång `edc-provider` har startats om.** EDC kör
> in-memory stores. Assets, policyer, avtal **och KoV-besluten, inklusive hävningar**,
> ligger i minnet och nollställs. En A-transfer kräver därför ett nytt godkännande efter
> omstart.

Vad som överlever en omstart (ligger i volym): de 91 brunnarna i CIP och tidsseriehistoriken.
Vad som går förlorat (ligger i minnet): EDC:s assets/policyer/avtal, KoV-besluten, FCF:s
batchar, ingest-kvittona, avtalsregistret och auditloggen.

## 2.4 Daglig drift

**Pausa:** `bash stoppa-demo.sh` (`down` utan `-v`: containrar bort, volymer kvar). **Starta:**
`bash starta-demo.sh`. **Nollställ allt till rent läge:** `bash aterstall-demo.sh` (raderar
Svada-minis volymer, aldrig någon annan stacks). **Processorkrav:** MongoDB 5.0 och senare kräver AVX på x86-datorer; saknas det startar inte databasen (Apple Silicon och moderna x86 klarar det). **Två installationer på samma dator eller server.** Kontrollrummet och Caddy når komponenterna över värdens portar, så två stackar med samma portnummer pratar med varandra av misstag. Skapa en `.env` för den andra med flyttade portar och eget prefix: `python3 tools/portforskjutning.py --forskjutning 1000 --prefix svadamini3 --in .env --ut /sokvag/.env --kontrollera-lediga` (kopiera sedan repot, lägg `.env` där och kör `bash starta-demo.sh`). Verktyget flyttar bara värdportarna (avgörs ur compose-filerna) och lämnar de interna portarna; provet `tests/portforskjutning_enhet.py` bevakar klassningen. Caddy hamnar då på en alternativ port (`CADDY_HTTP_PORT` i den nya `.env`, till exempel `http://svada-demo.localhost:` följt av den flyttade porten). **Uppgradera från en äldre version av repot:** databaserna byter format (MongoDB 4.4 → 7.0, PostgreSQL 13 → 17), så de gamla volymerna går inte att öppna. Kör `bash aterstall-demo.sh` (raderar Svada-minis volymer och bygger upp allt på nytt) i stället för en vanlig `starta-demo.sh`. **Starta om en enskild tjänst:**
`docker compose -f compose.stad.yml restart mintaka`; efter varje omstart som rör
`edc-provider`, kör om `registrera-edc`. Har du ändrat kod krävs `up -d --build`.

Nyckelparametrar i `.env`: `FCF_BATCH_INTERVAL_S=600` (10 minuter = ett modellerat dygn) samt
`FCF_FAULT_*` som ska stå på `false` vid start.

## 2.5 Verifiering

Hård regel 11: ett arbetspaket är klart först när allt är grönt.

```bash
bash tests/verify_all.sh      # alla delar, ~20 minuter
bash tests/verify_ap10.sh     # avtalshävningen
bash tests/verify_ap6b.sh     # kontrollrummet, inklusive steg 6
```

Skripten bevisar delarna var för sig, är idempotenta och startar själva de förutsättningar de
behöver. `verify_docs.sh` kontrollerar att dokumentation, ordlista och kod använder samma
termer.

## 2.6 Felsökning

| Symptom | Orsak | Åtgärd |
|---|---|---|
| "det finns inget kontraktsavtal för Distribution B" | Providern omstartad – in-memory stores | Kör om `registrera-edc`, förhandla sedan igen |
| KoV-godkännandet "försvann" | Samma sak – omregistreringen nollställer besluten | Begär A igen och godkänn på nytt |
| Transfern hänger, inget ingest-kvitto | Känd svaghet i EDC:s deprecerade inbäddade dataplan | Kontrollrummet gör om upp till tre gånger – vänta ut det |
| Steg 6 visar "Distribution A kan inte läsas just nu" | Inget gällande avtal om A, eller avtalet har hävts | Förhandla A (steg 3) och låt KoV godkänna |
| Förhandling `TERMINATED` med "Policy … not equal" | `ContractRequest` bar bara offertens `@id` | Skicka hela katalogofferten + `assigner` + `target` |
| Offert-`@id` fungerar plötsligt sämre | Id:t är base64-kodat och ändras vid varje omregistrering | Hämta alltid offerten ur katalogen strax före förhandlingen |
| Tyst 401 i varje DSP-anrop | En hubb startades om ensam och har nya nycklar | Starta om hubbarna och connectorerna tillsammans, kör `registrera-edc` |
| OOM, containrar dör | Dockers minne för lågt | Höj minnet, kör färre profiler |
