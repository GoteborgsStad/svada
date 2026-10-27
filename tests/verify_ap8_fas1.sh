#!/usr/bin/env bash
# =====================================================================
# verify_ap8_fas1.sh – nyckelskyddade management-API:er: bindande miniminivå (docs/koncept/C1-identitet.md)
# =====================================================================
# Detta är INTE hela identitetskontraktet (8.1–8.6 är i stället format för
# verifierbar identitet via DCP/IdentityHub, se verify_ap8_fas2.sh). Miniminivån lovar bara tre saker, och det är
# EXAKT vad det här skriptet prövar:
#
#   1. Anonym åtkomst till EDC:s management-API (provider OCH consumer)
#      är stängd (web.http.management.auth.type=tokenbased).
#   2. Samma delade nyckel släpper igenom (X-Api-Key).
#   3. Varje KoV-beslut svarar med vilket rollnamn (beslutsfattare) som
#      fattade det, satt via SVADA_KOV_ROLLINNEHAVARE.
#
# Självständigt och idempotent på samma sätt som verify_ap4b.sh – startar
# dataplanet + båda connectorerna och kör en egen A-förhandling.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Nyckelskyddade management-API:er – bindande miniminivå (docs/koncept/C1-identitet.md) ####"

set -a; . ./.env; set +a

PROV_API="http://localhost:${EDC_PROVIDER_DEFAULT_PORT}/api"
PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_API="http://localhost:${EDC_CONSUMER_DEFAULT_PORT}/api"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
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

hamta_katalog() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\"
    }" > /tmp/svada_ap8fas1_katalog.json
}

offert() {   # offert <asset-id>
  jq -c --arg a "$1" '[ .dataset ] | flatten
      | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' \
      /tmp/svada_ap8fas1_katalog.json
}

forhandla() {   # forhandla <asset-id> -> consumerns förhandlings-id
  local asset="$1" offer policy
  offer=$(offert "$asset")
  policy=$(printf '%s' "$offer" | jq -c --arg a "$asset" \
    '. + {"@context": ["http://www.w3.org/ns/odrl.jsonld",
                       {"svada": "https://svada.goteborg.se/ns/"}],
          "assigner": "'"${EDC_PROVIDER_ID}"'", "target": $a}')
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/contractnegotiations" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"@type\": \"ContractRequest\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\",
      \"policy\": ${policy}
    }" | jq -r '.["@id"] // empty'
}

providerpost() {   # providerpost <consumer-förhandlings-id>
  curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
       "${PROV_MGMT}/kov/forhandlingar" \
    | jq -c --arg c "$1" '[ .[] | select(.correlationId == $c) ] | .[0] // empty'
}

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (dataplan + båda connectorerna + registrering)"

if vanta_health "$PROV_API" 1; then
  ok "edc-provider var redan uppe"
else
  echo "  (startar dhi-fcf + dhi-edc ...)"
  $DHI --profile dhi-fcf --profile dhi-edc up -d >/dev/null 2>&1
  if vanta_health "$PROV_API" 90; then ok "edc-provider uppe"; else no "edc-provider startade inte"; fi
fi
if vanta_health "$CONS_API" 1; then
  ok "edc-consumer var redan uppe"
else
  echo "  (startar stad-edc ...)"
  $STAD --profile stad-edc up -d >/dev/null 2>&1
  if vanta_health "$CONS_API" 90; then ok "edc-consumer uppe"; else no "edc-consumer startade inte"; fi
fi

echo "  (registrerar Distribution A och B hos providern ...)"
if $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap8fas1_bootstrap.log 2>&1; then
  ok "registrera-edc körde igenom (båda distributionerna)"
else
  no "registrera-edc misslyckades (se /tmp/svada_ap8fas1_bootstrap.log)"
  tail -n 15 /tmp/svada_ap8fas1_bootstrap.log | sed 's/^/      /'
fi

# --- 8f1.1/8f1.2 Providerns management-API kräver nyckeln --------------
section "8f1.1–8f1.2 Providerns management-API: anonymt nekas, nyckeln släpps in"

KOD_ANON=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
             "${PROV_MGMT}/v3/assets/${EDC_ASSET_B_ID}")
if [ "$KOD_ANON" = "401" ] || [ "$KOD_ANON" = "403" ]; then
  ok "8f1.1 anonymt anrop mot providerns management-API nekas (HTTP $KOD_ANON)"
else
  no "8f1.1 providerns management-API svarade HTTP $KOD_ANON UTAN nyckel – anonym åtkomst är inte stängd"
fi

KOD_AUTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
             -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
             "${PROV_MGMT}/v3/assets/${EDC_ASSET_B_ID}")
if [ "$KOD_AUTH" = "200" ]; then
  ok "8f1.2 samma anrop MED X-Api-Key släpps igenom (HTTP $KOD_AUTH)"
else
  no "8f1.2 autentiserat anrop mot providern svarade HTTP $KOD_AUTH (förväntat 200)"
fi

# --- 8f1.3/8f1.4 Consumerns management-API kräver nyckeln --------------
section "8f1.3–8f1.4 Consumerns management-API: anonymt nekas, nyckeln släpps in"

QUERYSPEC='{"@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
            "@type": "QuerySpec", "limit": 1}'

KOD_ANON2=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
              "${CONS_MGMT}/v3/contractnegotiations/request" \
              -H 'content-type: application/json' -d "${QUERYSPEC}")
if [ "$KOD_ANON2" = "401" ] || [ "$KOD_ANON2" = "403" ]; then
  ok "8f1.3 anonymt anrop mot consumerns management-API nekas (HTTP $KOD_ANON2)"
else
  no "8f1.3 consumerns management-API svarade HTTP $KOD_ANON2 UTAN nyckel – anonym åtkomst är inte stängd"
fi

KOD_AUTH2=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
              -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
              "${CONS_MGMT}/v3/contractnegotiations/request" \
              -H 'content-type: application/json' -d "${QUERYSPEC}")
if [ "$KOD_AUTH2" = "200" ]; then
  ok "8f1.4 samma anrop MED X-Api-Key släpps igenom (HTTP $KOD_AUTH2)"
else
  no "8f1.4 autentiserat anrop mot consumern svarade HTTP $KOD_AUTH2 (förväntat 200)"
fi

# --- 8f1.5 KoV-beslutet bär det konfigurerade rollnamnet ---------------
section "8f1.5 KoV-beslutet svarar med konfigurerad beslutsfattare"

hamta_katalog
NEG_A=$(forhandla "${EDC_ASSET_A_ID}")
if [ -n "$NEG_A" ]; then
  ok "8f1.5 förhandling om A startad ($NEG_A)"
else
  no "8f1.5 kunde inte starta förhandling om A"
fi

PROV_ID=""
echo "  (väntar in gaten) ..."
for _ in $(seq 1 15); do
  sleep 2
  PROV_ID=$(providerpost "$NEG_A" | jq -r '.id // empty')
  [ -n "$PROV_ID" ] && break
done
if [ -n "$PROV_ID" ]; then
  ok "8f1.5 förhandlingen hamnade i KoV-kön ($PROV_ID)"
else
  no "8f1.5 förhandlingen dök aldrig upp i KoV-kön"
fi

# Verifierbar identitet: gaten kräver numera ett verifierat SvadaRoleCredential
# (Authorization: Bearer), inte bara management-nyckeln – se
# KovIdentitetsverifiering.java och tests/lib.sh:s hamta_kov_token(). Denna
# regression fortsätter alltså att bevisa samma sak som tidigare
# (beslutsfattare == SVADA_KOV_ROLLINNEHAVARE), men värdet är nu
# kryptografiskt VERIFIERAT i stället för en ren konfigurationssträng.
KOV_TOKEN=$(hamta_kov_token)
SVAR=$(curl -s --max-time 20 -X POST \
        -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
        -H "Authorization: Bearer ${KOV_TOKEN}" \
        "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann")
BESLUTSFATTARE=$(echo "$SVAR" | jq -r '.beslutsfattare // empty')
if [ "$BESLUTSFATTARE" = "${SVADA_KOV_ROLLINNEHAVARE}" ]; then
  ok "8f1.5 beslutssvaret bär beslutsfattare='${BESLUTSFATTARE}' (matchar SVADA_KOV_ROLLINNEHAVARE, nu verifierat)"
else
  no "8f1.5 beslutssvaret bär beslutsfattare='${BESLUTSFATTARE}', förväntat '${SVADA_KOV_ROLLINNEHAVARE}': $(echo "$SVAR" | head -c 300)"
fi

# --- 8f1.6 Statisk kontroll: konfigurationen är på plats ----------------
section "8f1.6 Konfigurationen är satt i .env och provider-/consumer.properties"

check ".env sätter EDC_PROVIDER_MGMT_KEY" \
  grep -q "^EDC_PROVIDER_MGMT_KEY=" .env
check ".env sätter EDC_CONSUMER_MGMT_KEY" \
  grep -q "^EDC_CONSUMER_MGMT_KEY=" .env
check ".env sätter SVADA_KOV_ROLLINNEHAVARE" \
  grep -q "^SVADA_KOV_ROLLINNEHAVARE=" .env
check "provider.properties slår på tokenbased auth" \
  grep -q "^web.http.management.auth.type=tokenbased" edc/konfig/provider.properties
check "consumer.properties slår på tokenbased auth" \
  grep -q "^web.http.management.auth.type=tokenbased" edc/konfig/consumer.properties

finish "Nyckelskyddade management-API:er"
