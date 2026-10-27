#!/usr/bin/env bash
# =====================================================================
# verify_ap4a.sh – Eclipse EDC-grund (provider + consumer): katalog och förhandling
# Prövar testfallen 4a.1–4a.6.
# =====================================================================
# Självständigt och idempotent: startar profilerna dhi-fcf (dataplanet),
# dhi-edc (providern) och stad-edc (consumern) vid behov, och kör
# registreringen av Distribution B (som i sig är idempotent).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Eclipse EDC-grund (katalog och förhandling) ####"

# Portkartan/konfigurationen ur .env (enda källan, hård regel 5).
set -a; . ./.env; set +a

PROV_API="http://localhost:${EDC_PROVIDER_DEFAULT_PORT}/api"
PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_API="http://localhost:${EDC_CONSUMER_DEFAULT_PORT}/api"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"

# Providerns DSP-adress sedd FRÅN consumer-containern (delat nät
# svada-dsp-public). DSP-versionen har egen sökväg i EDC 0.17.0.
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"

DHI="docker compose -f compose.dhi.yml"
STAD="docker compose -f compose.stad.yml"

docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

vanta_health() {   # vanta_health <url> <sekunder>
  for _ in $(seq 1 "$2"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1/check/health")" \
      = "200" ] && return 0
    sleep 2
  done
  return 1
}

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (startar dataplanet + båda connectorerna)"

if vanta_health "$PROV_API" 1; then
  ok "edc-provider var redan uppe"
else
  echo "  (startar dhi-fcf + dhi-edc ...)"
  $DHI --profile dhi-fcf --profile dhi-edc up -d >/dev/null 2>&1
  if vanta_health "$PROV_API" 90; then ok "edc-provider uppe"
  else no "edc-provider startade inte"; fi
fi

if vanta_health "$CONS_API" 1; then
  ok "edc-consumer var redan uppe"
else
  echo "  (startar stad-edc ...)"
  $STAD --profile stad-edc up -d >/dev/null 2>&1
  if vanta_health "$CONS_API" 90; then ok "edc-consumer uppe"
  else no "edc-consumer startade inte"; fi
fi

# Registrera Distribution B (idempotent – PUT om objekten redan finns).
echo "  (registrerar Distribution B hos providern ...)"
if $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap4a_bootstrap.log 2>&1; then
  ok "registrera-edc körde igenom"
else
  no "registrera-edc misslyckades (se /tmp/svada_ap4a_bootstrap.log)"
  tail -n 15 /tmp/svada_ap4a_bootstrap.log | sed 's/^/      /'
fi

# --- 4a.1 Connectorer friska ------------------------------------------
section "4a.1 Connectorer friska (health-endpoints)"
PH=$(curl -s --max-time 10 "${PROV_API}/check/health")
CH=$(curl -s --max-time 10 "${CONS_API}/check/health")
if echo "$PH" | jq -e '.isSystemHealthy == true' >/dev/null 2>&1; then
  ok "4a.1 provider ${EDC_PROVIDER_DEFAULT_PORT}/api/check/health rapporterar isHealthy"
else
  no "4a.1 provider health: $PH"
fi
if echo "$CH" | jq -e '.isSystemHealthy == true' >/dev/null 2>&1; then
  ok "4a.1 consumer ${EDC_CONSUMER_DEFAULT_PORT}/api/check/health rapporterar isHealthy"
else
  no "4a.1 consumer health: $CH"
fi

# --- 4a.2 DSP-katalog --------------------------------------------------
section "4a.2 DSP-katalog: consumern frågar providern"
# Katalogförfrågan går via consumerns MANAGEMENT-API, som i sin tur talar
# DSP mot providern över svada-dsp-public. Det är alltså hela
# Dataspace-Protocol-kedjan som testas, inte ett internt anrop.
KATALOG=$(curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
  -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
    \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
    \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
    \"counterPartyAddress\": \"${PROV_DSP}\",
    \"protocol\": \"${DSP_PROTOKOLL}\"
  }")

echo "$KATALOG" > /tmp/svada_ap4a_katalog.json

if echo "$KATALOG" | jq -e '(.["@type"] // "") | test("Catalog")' >/dev/null 2>&1; then
  ok "4a.2 svaret är en dcat:Catalog"
else
  no "4a.2 inget katalogsvar: $(echo "$KATALOG" | head -c 400)"
fi

# DSP-kontexten 2025-1 komprimerar dcat:dataset till "dataset", och ett
# ensamt dataset kommer som objekt i stället för lista – normalisera båda.
DATASET=$(echo "$KATALOG" | jq -c '[ .dataset ] | flatten
            | map(select(.["@id"] == "'"${EDC_ASSET_B_ID}"'")) | .[0] // empty')

if [ -n "$DATASET" ]; then
  ok "4a.2 datasetet ${EDC_ASSET_B_ID} finns i katalogen"
else
  no "4a.2 datasetet ${EDC_ASSET_B_ID} saknas i katalogen (se /tmp/svada_ap4a_katalog.json)"
fi

if [ -n "$DATASET" ] && echo "$DATASET" | jq -e '.hasPolicy' >/dev/null 2>&1; then
  ok "4a.2 datasetet bär ett ODRL-offer (odrl:hasPolicy)"
else
  no "4a.2 datasetet saknar odrl:hasPolicy"
fi

# Kontraktsofferten måste ha ett @id – det är det consumern förhandlar om
# i förhandlingsprovet (verify_ap4b.sh). Utan det bevisar katalogen ingenting.
if [ -n "$DATASET" ] && \
   echo "$DATASET" | jq -e '[ .hasPolicy ] | flatten | .[0]["@id"] | length > 0' >/dev/null 2>&1; then
  ok "4a.2 offerten har ett förhandlingsbart @id"
else
  no "4a.2 offerten saknar @id"
fi

# Produktdeklarationen (förstudie-nasta-steg §1): båda distributionerna ska i
# katalogen peka på SAMMA specifikation och bära en kvalitetsdeklaration, så att
# mottagaren ser vad produkten är och hur bra den är innan avtalet.
for ID in "${EDC_ASSET_B_ID}" "${EDC_ASSET_A_ID}"; do
  DS=$(echo "$KATALOG" | jq -c '[ .dataset ] | flatten | map(select(.["@id"] == "'"${ID}"'")) | .[0] // empty')
  if [ -n "$DS" ] && echo "$DS" | jq -e '
        (.["dct:conformsTo"]["@id"] // "") == "urn:svada:dataprodukt:modellerad-bradddata:1.0.0"
        and ([.[] | strings | select(test("90 av 91 serier är syntetiska"))] | length) >= 1
        and ([.["http://www.w3.org/ns/dqv#hasQualityMeasurement"]] | flatten | length) >= 3' >/dev/null 2>&1; then
    ok "4a.2 ${ID} deklarerar specifikation, kvalitet (dqv) och att 90 av 91 serier är syntetiska"
  else
    no "4a.2 ${ID} saknar produktdeklarationen i katalogen"
  fi
done

# Metadata ur kuvertet ska följa med som dataset-egenskaper.
if [ -n "$DATASET" ] && \
   echo "$DATASET" | jq -e '(.. | strings) | select(. == "K0R1T1")' >/dev/null 2>&1; then
  ok "4a.2 informationsklassen K0R1T1 följer med i katalogposten"
else
  no "4a.2 informationsklassen K0R1T1 saknas i katalogposten"
fi

# Hård regel 8/röd tråd 1: inget av Distribution A får sippra in i
# Distribution B:s katalogpost.
#
# Distribution A annonseras i katalogen (tidigare var den oregistrerad
# och kontrollen kunde göras på HELA katalogen). Nu är annonseringen avsiktlig: det är så consumern
# får se att produkten finns och på vilka villkor (obligationen
# svada:kovGodkannande). Katalogen är kontrollplan, inte dataplan: A:s DATA
# kräver fortfarande KoV-beslut, och A når aldrig portalerna (testfall 6a.2).
# Kontrollen är därför skärpt till B:s post i stället för uppmjukad.
if echo "$DATASET" | jq -e '(.. | strings) | select(test("non-public|K1R1T1|distributions/a/"))' \
     >/dev/null 2>&1; then
  no "4a.2 KATALOGLÄCKA: spår av Distribution A i B:s katalogpost"
else
  ok "4a.2 inga spår av Distribution A i Distribution B:s katalogpost"
fi

# --- 4a.3 Dataplans-koppling ------------------------------------------
section "4a.3 Assetets dataAddress pekar på fcf-sim"
ASSET=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/v3/assets/${EDC_ASSET_B_ID}")
BASEURL=$(echo "$ASSET" | jq -r '.. | objects | .baseUrl? // empty' | head -n 1)
if [ "$BASEURL" = "${EDC_ASSET_B_URL}" ]; then
  ok "4a.3 dataAddress.baseUrl = ${BASEURL}"
else
  no "4a.3 dataAddress.baseUrl = '${BASEURL}' (förväntat ${EDC_ASSET_B_URL})"
fi

# Adressen ska dessutom faktiskt svara – och göra det med
# Distribution B-kuvert. Anropet körs INIFRÅN providern, eftersom fcf-sim
# bara ligger på dhi-internal.
KUVERT=$(docker exec ${SVADA_PREFIX:-svada}-edc-provider curl -s --max-time 15 "${EDC_ASSET_B_URL}" 2>/dev/null)
if echo "$KUVERT" | jq -e '.distribution == "B" and .accessRights == "public"' >/dev/null 2>&1; then
  ok "4a.3 providern når dataplanet och får Distribution B (accessRights: public)"
else
  no "4a.3 dataplanet svarade inte med Distribution B: $(echo "$KUVERT" | head -c 200)"
fi

# Röd tråd 2 (integritet): B som EDC:n pekar på saknar brunns-GIS.
if echo "$KUVERT" | jq -e '[.records[]? | select(has("location") or has("sourceSrs"))] | length == 0' \
     >/dev/null 2>&1; then
  ok "4a.3 kuvertet bakom assetet saknar brunns-GIS (röd tråd 2)"
else
  no "4a.3 brunns-GIS i Distribution B bakom EDC-assetet"
fi

# --- 4a.4 Mock-IAM helt borta -------------------------------------------
section "4a.4 Mock-identitet helt borttagen ur edc/ (hård regel 6)"
# Sedan bytet till verifierbar DCP-identitet (2026-09-01/02) är
# DSP-lagrets deltagaridentitet INTE längre mockad - iam-mock och
# MockIamSeedExtension.java är helt borttagna. Den sista kvarvarande
# MEDVETNA FÖRENKLINGEN (dataplanets transfer-proxy-token-nyckelpar,
# SvadaTransferProxyNyckelExtension.java) stängdes i en egen,
# fristående uppföljningscommit EFTER att bytet markerades klart.
# Testfall 8.4 är därmed helt uppfyllt: 0
# träffar på markören någonstans i edc/. De allra äldsta kontrollerna
# (som letade efter MockIamSeedExtension.java och org.eclipse.edc:iam-mock)
# beskrev ett tillstånd som slutade existera redan i STEG 5.
TRAFFAR=$(grep -rl "MEDVETEN FÖRENKLING" edc/ 2>/dev/null | wc -l)
if [ "$TRAFFAR" -eq 0 ]; then
  ok "4a.4 'MEDVETEN FÖRENKLING' ger 0 träffar i edc/ (testfall 8.4 uppfyllt)"
else
  no "4a.4 'MEDVETEN FÖRENKLING' finns fortfarande i $TRAFFAR fil(er) under edc/"
fi
check "4a.4 mock-IAM-extensionen (MockIamSeedExtension.java) är borttagen" \
  test '!' -f edc/src/main/java/se/goteborg/svada/edc/MockIamSeedExtension.java
check "4a.4 iam-mock-beroendet är borttaget ur build.gradle.kts" \
  test -z "$(grep 'org.eclipse.edc:iam-mock' edc/build.gradle.kts 2>/dev/null)"
check "4a.4 transfer-proxy-nyckelparet genereras i koden, inte hårdkodat" \
  grep -q "KeyPairGenerator" edc/src/main/java/se/goteborg/svada/edc/dcp/SvadaTransferProxyNyckelExtension.java
check "4a.4 inget hårdkodat testcertifikat kvar i SvadaTransferProxyNyckelExtension" \
  test -z "$(grep 'BEGIN CERTIFICATE' edc/src/main/java/se/goteborg/svada/edc/dcp/SvadaTransferProxyNyckelExtension.java 2>/dev/null)"
# ... och genereringen ska synas i driftloggen, inte bara i källkoden.
# GOTCHA: loggen fångas i en VARIABEL först – "docker logs |
# grep -q" ger SIGPIPE och fäller pipefail. Sökningen görs med
# logg_innehaller (tests/lib.sh), som dessutom gör om läsningen: `docker logs`
# har observerats returnera ofullständigt utdata under belastning.
if logg_innehaller ${SVADA_PREFIX:-svada}-edc-provider "Transfer-proxy-nyckelpar"; then
  ok "4a.4 nyckelgenereringen loggas vid uppstart av edc-provider"
else
  no "4a.4 nyckelgenereringen loggas inte av edc-provider"
fi

# --- 4a.5 JVM-tak ------------------------------------------------------
section "4a.5 Resurstak (resursstrategin, bindande)"
for c in ${SVADA_PREFIX:-svada}-edc-provider ${SVADA_PREFIX:-svada}-edc-consumer; do
  OPTS=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$c" 2>/dev/null \
         | grep '^JAVA_TOOL_OPTIONS=' | cut -d= -f2-)
  if [ "$OPTS" = "${EDC_JVM_XMX}" ]; then
    ok "4a.5 $c kör med JAVA_TOOL_OPTIONS=${OPTS}"
  else
    no "4a.5 $c saknar JVM-tak (JAVA_TOOL_OPTIONS='${OPTS}')"
  fi
  MEM=$(docker inspect -f '{{.HostConfig.Memory}}' "$c" 2>/dev/null)
  if [ "${MEM:-0}" -gt 0 ]; then
    ok "4a.5 $c har mem_limit satt ($((MEM / 1024 / 1024)) MiB)"
  else
    no "4a.5 $c saknar mem_limit"
  fi
done
# In-memory stores (§3.3): inga SQL-/Postgres-moduler ska vara inbyggda.
# OBS: matcha DEPENDENSRADER, inte kommentaren som förklarar varför
# SQL-BOM:en är bortvald (annars ger den egna förklaringen falskt RÖTT).
if grep -qE '^[[:space:]]*(implementation|runtimeOnly|api)\(.*sql' edc/build.gradle.kts; then
  no "4a.5 SQL-BOM inbyggd – strider mot in-memory-beslutet i §3.3"
else
  ok "4a.5 in-memory stores (ingen SQL-BOM, inga Postgres-containrar)"
fi

# --- Nätverksgränsen (hård regel 8) ------------------------------------
section "4a.x Nätverksgränsen"
NAT=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
        ${SVADA_PREFIX:-svada}-fcf-sim 2>/dev/null)
if echo "$NAT" | grep -q "dsp-public"; then
  no "4a.x fcf-sim ligger på dsp-public – dataplanet ska inte nås utanför DHI"
else
  ok "4a.x fcf-sim ligger fortfarande enbart på DHI:s interna nät ($NAT)"
fi
for c in ${SVADA_PREFIX:-svada}-edc-provider ${SVADA_PREFIX:-svada}-edc-consumer; do
  if docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$c" \
       2>/dev/null | grep -q "dsp-public"; then
    ok "4a.x $c ligger på dsp-public (kontrollplanet korsar org-gränsen)"
  else
    no "4a.x $c saknas på dsp-public"
  fi
done

# --- 4a.6 Regression ---------------------------------------------------
section "4a.6 Regression"
ok "4a.6 hanteras av tests/verify_all.sh (kör ap0–ap4a i ordning)"

finish "verify_ap4a"
