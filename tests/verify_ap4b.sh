#!/usr/bin/env bash
# =====================================================================
# verify_ap4b.sh – ODRL, kontraktsförhandling och KoV-gaten
# Prövar testfallen 4b.1–4b.6.
# =====================================================================
# Självständigt och idempotent: startar dataplanet + båda connectorerna,
# kör registreringen (idempotent) och genomför HELA förhandlingssekvensen
# i en följd. Det sista är ett krav, inte en stilfråga: EDC:s stores är
# in-memory (resursstrategin, hård regel 3), så förhandlingar och avtal överlever
# inte en omstart av providern.
#
# Förhandlingsflödet körs med curl direkt mot management-API:erna (se skriptet nedan).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### ODRL, förhandling och KoV-gaten ####"

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

# ---------------------------------------------------------------------
# Hjälpare: hämta katalogen och starta en förhandling om ett dataset.
# ---------------------------------------------------------------------
hamta_katalog() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\"
    }" > /tmp/svada_ap4b_katalog.json
}

# offert <assetId> -> hela hasPolicy[0] ur katalogen (offer-id + ODRL-regler)
offert() {
  jq -c --arg a "$1" '[ .dataset ] | flatten
      | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' \
      /tmp/svada_ap4b_katalog.json
}

# forhandla <assetId> -> consumerns förhandlings-id
#
# GOTCHA: policyn i ContractRequest måste vara HELA offerten ur katalogen,
# inte bara dess @id. Consumern jämför i validateConfirmed sitt eget
# offert-exemplar med providerns avtal (PolicyEquality) och terminerar med
# "Policy in the contract agreement is not equal to the one in the contract
# offer" om reglerna saknas. I katalogprovet märktes det inte – då var policyerna tomma.
forhandla() {
  local asset="$1"
  local offer policy
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

tillstand() {   # tillstand <consumer-förhandlings-id>
  curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/$1" | jq -r '.state // "OKÄNT"'
}

# vanta_pa_tillstand <id> <sekunder> <tillstånd...>
vanta_pa_tillstand() {
  local id="$1" sek="$2"; shift 2
  local i s
  for i in $(seq 1 $((sek / 2))); do
    s=$(tillstand "$id")
    for t in "$@"; do [ "$s" = "$t" ] && { echo "$s"; return 0; }; done
    sleep 2
  done
  echo "$s"
  return 1
}

# providerpost <consumer-förhandlings-id> -> providerns motsvarande post
providerpost() {
  curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/kov/forhandlingar" \
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
if $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap4b_bootstrap.log 2>&1; then
  ok "registrera-edc körde igenom (båda distributionerna)"
else
  no "registrera-edc misslyckades (se /tmp/svada_ap4b_bootstrap.log)"
  tail -n 15 /tmp/svada_ap4b_bootstrap.log | sed 's/^/      /'
fi

hamta_katalog

# --- 4b.0 Katalogen bär båda distributionernas ODRL-regler -------------
section "4b.0 Båda distributionerna annonseras med verkställda ODRL-regler"

OFFER_B=$(offert "${EDC_ASSET_B_ID}")
OFFER_A=$(offert "${EDC_ASSET_A_ID}")

if [ -n "$OFFER_B" ] && [ -n "$OFFER_A" ]; then
  ok "4b.0 båda datasetten finns i DSP-katalogen"
else
  no "4b.0 saknat dataset i katalogen (A='$OFFER_A' B='$OFFER_B')"
fi

# B: use + distribute + publish, med duty attribute på use.
if echo "$OFFER_B" | jq -e '
      ([ .permission ] | flatten | map(.action | tostring)
        | map(sub("^odrl:";"")) | sort) == ["distribute","publish","use"]' >/dev/null 2>&1; then
  ok "4b.0 B:s offert bär permission use/distribute/publish"
else
  no "4b.0 B:s permissions fel: $(echo "$OFFER_B" | jq -c '.permission')"
fi
if echo "$OFFER_B" | jq -e '(.. | strings) | select(test("attribute"))' >/dev/null 2>&1; then
  ok "4b.0 B:s offert bär attribueringsplikten (duty attribute)"
else
  no "4b.0 B saknar duty attribute"
fi

# A: förbud mot distribute/publish + obligationen som utlöser KoV-gaten.
if echo "$OFFER_A" | jq -e '
      ([ .prohibition ] | flatten | map(.action | tostring)
        | map(sub("^odrl:";"")) | sort) == ["distribute","publish"]' >/dev/null 2>&1; then
  ok "4b.0 A:s offert förbjuder distribute och publish"
else
  no "4b.0 A:s prohibitions fel: $(echo "$OFFER_A" | jq -c '.prohibition')"
fi
if echo "$OFFER_A" | jq -e '(.. | strings)
      | select(. == "https://svada.goteborg.se/ns/kovGodkannande")' >/dev/null 2>&1; then
  ok "4b.0 A:s offert bär obligationen svada:kovGodkannande"
else
  no "4b.0 A saknar obligationen svada:kovGodkannande"
fi
if echo "$OFFER_A" | jq -e '(.. | strings)
      | select(. == "https://svada.goteborg.se/ns/deltagare")' >/dev/null 2>&1; then
  ok "4b.0 A:s use-permission är begränsad av constrainten svada:deltagare"
else
  no "4b.0 A saknar constrainten svada:deltagare"
fi

# Hård regel 7/8: A har EGEN policy och EGEN kontraktsdefinition – B:s
# öppna policy får aldrig gälla för A.
APOL=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/v3/contractdefinitions/kontrakt-distribution-a" \
        | jq -r '.. | .contractPolicyId? // empty' | head -n 1)
if [ "$APOL" = "policy-distribution-a" ]; then
  ok "4b.0 kontrakt-distribution-a pekar på sin EGEN policy ($APOL)"
else
  no "4b.0 kontrakt-distribution-a har fel contractPolicyId: '$APOL'"
fi

# --- 4b.1 Distribution B förhandlas automatiskt ------------------------
section "4b.1 Distribution B: förhandling -> FINALIZED automatiskt"
NEG_B=$(forhandla "${EDC_ASSET_B_ID}")
if [ -n "$NEG_B" ]; then
  ok "4b.1 förhandling om B startad ($NEG_B)"
else
  no "4b.1 kunde inte starta förhandling om B"
fi
S_B=$(vanta_pa_tillstand "$NEG_B" 60 FINALIZED TERMINATED)
if [ "$S_B" = "FINALIZED" ]; then
  ok "4b.1 B nådde FINALIZED utan någon manuell åtgärd"
else
  no "4b.1 B hamnade i '$S_B' (förväntat FINALIZED)"
fi

# --- 4b.2 Distribution A stannar hos providern -------------------------
section "4b.2 Distribution A: förhandlingen stannar i vänteläge hos providern"
NEG_A=$(forhandla "${EDC_ASSET_A_ID}")
if [ -n "$NEG_A" ]; then
  ok "4b.2 förhandling om A startad ($NEG_A)"
else
  no "4b.2 kunde inte starta förhandling om A"
fi

echo "  (väntar 30 s – gaten ska hålla förhandlingen kvar) ..."
sleep 30
S_A=$(tillstand "$NEG_A")
if [ "$S_A" != "FINALIZED" ] && [ "$S_A" != "TERMINATED" ]; then
  ok "4b.2 A är varken finaliserad eller terminerad efter 30 s (state=$S_A)"
else
  no "4b.2 A nådde '$S_A' UTAN KoV-beslut – gaten läcker!"
fi

POST_A=$(providerpost "$NEG_A")
if [ -n "$POST_A" ]; then
  ok "4b.2 providern har förhandlingen i KoV-kön ($(echo "$POST_A" | jq -r .id))"
else
  no "4b.2 förhandlingen syns inte i providerns KoV-kö"
fi
if echo "$POST_A" | jq -e '.pending == true and .state == "REQUESTED"
                            and .kovBeslut == "VANTANDE"' >/dev/null 2>&1; then
  ok "4b.2 providersidan: state=REQUESTED, pending=true, kovBeslut=VANTANDE"
else
  no "4b.2 providersidans post ser fel ut: $POST_A"
fi
if echo "$POST_A" | jq -e '.contractAgreementId == null' >/dev/null 2>&1; then
  ok "4b.2 inget avtal har ingåtts för A"
else
  no "4b.2 A har fått ett avtal utan KoV-beslut"
fi

# --- 4b.4 Ingen consumer-bakväg (körs MEDAN A väntar) ------------------
section "4b.4 Ingen väg runt gaten på consumer-sidan (hård regel 7)"
KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
        -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
        "${CONS_MGMT}/kov/forhandlingar/${NEG_A}/godkann")
if [ "$KOD" = "404" ]; then
  ok "4b.4 consumerns management-API (${EDC_CONSUMER_MGMT_PORT}) har ingen /kov-endpoint (HTTP $KOD)"
else
  no "4b.4 consumern svarade HTTP $KOD på ett KoV-godkännande – bakväg!"
fi
# Consumerns egna förhandlings-API får inte heller kunna knuffa fram den.
curl -s -o /dev/null --max-time 15 -X POST \
     -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
     "${CONS_MGMT}/v3/contractnegotiations/${NEG_A}/finalize" 2>/dev/null
sleep 8
S_A2=$(tillstand "$NEG_A")
if [ "$S_A2" != "FINALIZED" ]; then
  ok "4b.4 A är fortfarande inte finaliserad efter consumer-försöken (state=$S_A2)"
else
  no "4b.4 consumern lyckades finalisera A utan provider-godkännande"
fi

# --- 4b.3 KoV-godkännande på PROVIDER-sidan ----------------------------
section "4b.3 KoV-godkännande på providerns management-API -> FINALIZED"
PROV_ID=$(echo "$POST_A" | jq -r '.id')

# Verifierbar identitet (KovIdentitetsverifiering.java):
# gaten kräver numera OCKSÅ ett verifierat SvadaRoleCredential, inte bara
# den delade management-nyckeln. Bevisa det FÖRST: ett anrop utan
# Authorization-header ska avvisas med 401, och förhandlingen ska INTE röra
# sig, innan vi ens hämtar ett giltigt token.
KOD_UTAN_TOKEN=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST \
        -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
        "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann")
if [ "$KOD_UTAN_TOKEN" = "401" ]; then
  ok "4b.3 (steg 6) godkännande UTAN Authorization-header avvisas med 401"
else
  no "4b.3 (steg 6) godkännande utan token gav HTTP $KOD_UTAN_TOKEN (förväntat 401)"
fi
S_A_UTAN_TOKEN=$(tillstand "$NEG_A")
if [ "$S_A_UTAN_TOKEN" != "FINALIZED" ]; then
  ok "4b.3 (steg 6) A är fortfarande inte finaliserad efter det obevisade försöket"
else
  no "4b.3 (steg 6) A finaliserades trots ett anrop utan verifierat token!"
fi

KOV_TOKEN=$(hamta_kov_token)
if [ -n "$KOV_TOKEN" ]; then
  ok "4b.3 (steg 6) hämtade ett self-issued DCP-token från Stadens STS"
else
  no "4b.3 (steg 6) kunde inte hämta något token från Stadens STS"
fi

SVAR=$(curl -s --max-time 20 -X POST \
        -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
        -H "Authorization: Bearer ${KOV_TOKEN}" \
        "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann")
if echo "$SVAR" | jq -e '.beslut == "GODKAND" and .pending == false' >/dev/null 2>&1; then
  ok "4b.3 providern registrerade KoV-beslutet GODKAND och släppte förhandlingen"
else
  no "4b.3 godkännandet gick inte igenom: $(echo "$SVAR" | head -c 300)"
fi
if echo "$SVAR" | jq -e --arg roll "${SVADA_KOV_ROLLINNEHAVARE}" '.beslutsfattare == $roll' >/dev/null 2>&1; then
  ok "4b.3 (steg 6) beslutsfattare är den kryptografiskt VERIFIERADE rollen"
else
  no "4b.3 (steg 6) beslutsfattare matchar inte den verifierade rollen: $(echo "$SVAR" | head -c 300)"
fi
# Uppföljning 2026-09-02:
# beslutsfattare fanns tidigare BARA i engångssvaret ovan, inte i
# GET /forhandlingar - dvs. attribuerbarheten (4:e arkitekturinvarianten)
# gick förlorad ur den beständiga loggen så fort svaret gått tillbaka.
# Kontrollera nu att den ligger kvar i listan dashboardens auditlogg läser.
POST_A_EFTER=$(providerpost "$NEG_A")
if echo "$POST_A_EFTER" | jq -e --arg roll "${SVADA_KOV_ROLLINNEHAVARE}" '.beslutsfattare == $roll' >/dev/null 2>&1; then
  ok "4b.3 (uppföljning) beslutsfattare finns kvar i GET /forhandlingar (beständig logg, inte bara engångssvaret)"
else
  no "4b.3 (uppföljning) beslutsfattare saknas i GET /forhandlingar efter beslutet: $(echo "$POST_A_EFTER" | head -c 300)"
fi
S_A3=$(vanta_pa_tillstand "$NEG_A" 60 FINALIZED TERMINATED)
if [ "$S_A3" = "FINALIZED" ]; then
  ok "4b.3 A nådde FINALIZED EFTER godkännandet"
else
  no "4b.3 A hamnade i '$S_A3' efter godkännandet (förväntat FINALIZED)"
fi
if curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/${NEG_A}" \
     | jq -e '.contractAgreementId | length > 0' >/dev/null 2>&1; then
  ok "4b.3 consumern har fått ett avtal för Distribution A"
else
  no "4b.3 inget avtal hos consumern trots FINALIZED"
fi

# --- 4b.5 Avslag ------------------------------------------------------
section "4b.5 KoV kan avslå en ny A-förhandling -> TERMINATED"
NEG_A2=$(forhandla "${EDC_ASSET_A_ID}")
echo "  (ny A-förhandling $NEG_A2 – väntar in gaten) ..."
PROV_ID2=""
for _ in $(seq 1 15); do
  sleep 2
  PROV_ID2=$(providerpost "$NEG_A2" | jq -r '.id // empty')
  [ -n "$PROV_ID2" ] && break
done
if [ -n "$PROV_ID2" ]; then
  ok "4b.5 den nya förhandlingen hamnade i KoV-kön ($PROV_ID2)"
else
  no "4b.5 den nya A-förhandlingen dök aldrig upp i KoV-kön"
fi
# Verifierbar identitet: nytt token – det förra kan ha hunnit gå ut under
# 4b.3/4b.4:s väntetider, och varje anrop ska ändå verifieras för sig.
KOV_TOKEN2=$(hamta_kov_token)
SVAR2=$(curl -s --max-time 20 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
        -H "Authorization: Bearer ${KOV_TOKEN2}" \
        "${PROV_MGMT}/kov/forhandlingar/${PROV_ID2}/avsla")
if echo "$SVAR2" | jq -e '.beslut == "AVSLAGEN"' >/dev/null 2>&1; then
  ok "4b.5 providern registrerade beslutet AVSLAGEN"
else
  no "4b.5 avslaget gick inte igenom: $(echo "$SVAR2" | head -c 300)"
fi
S_A4=$(vanta_pa_tillstand "$NEG_A2" 60 TERMINATED FINALIZED)
if [ "$S_A4" = "TERMINATED" ]; then
  ok "4b.5 den avslagna förhandlingen blev TERMINATED hos consumern"
else
  no "4b.5 avslagen förhandling hamnade i '$S_A4' (förväntat TERMINATED)"
fi
if providerpost "$NEG_A2" | jq -e '.errorDetail | test("KoV")' >/dev/null 2>&1; then
  ok "4b.5 avslagsskälet är sparat och spårbart på provider-sidan"
else
  no "4b.5 inget avslagsskäl på provider-sidan"
fi
# Uppföljning 2026-09-02, samma som 4b.3 ovan men för avslagsfallet.
if providerpost "$NEG_A2" | jq -e --arg roll "${SVADA_KOV_ROLLINNEHAVARE}" '.beslutsfattare == $roll' >/dev/null 2>&1; then
  ok "4b.5 (uppföljning) beslutsfattare finns kvar i GET /forhandlingar även för avslag"
else
  no "4b.5 (uppföljning) beslutsfattare saknas i GET /forhandlingar efter avslaget"
fi

# --- 4b.x ODRL verkställs ------------------
section "4b.x ODRL-reglerna är BUNDNA och utvärderas (inte bara metadata)"
# Sökningen görs med logg_innehaller (tests/lib.sh) som läser om loggen vid
# utebliven träff – `docker logs` kan returnera ofullständigt utdata under
# belastning och gjorde detta testfall slumpvis rött.
if logg_innehaller ${SVADA_PREFIX:-svada}-edc-provider "SVADA ODRL: bundna actions"; then
  ok "4b.x providern loggar sina RuleBindingRegistry-bindningar vid uppstart"
else
  no "4b.x inga ODRL-bindningar loggade av providern"
fi
# Beviset för att bindningen BETYDER något: constraintfunktionen har körts.
if logg_innehaller ${SVADA_PREFIX:-svada}-edc-provider "SVADA ODRL utvärderad: svada:deltagare"; then
  ok "4b.x constrainten svada:deltagare utvärderades faktiskt under förhandlingen"
else
  no "4b.x constrainten svada:deltagare utvärderades aldrig – regeln är obunden"
fi
check "4b.x KoV-gaten är en ContractNegotiationPendingGuard (provider-sidig)" \
  grep -q "ContractNegotiationPendingGuard" \
  edc/src/main/java/se/goteborg/svada/edc/kov/KovGate.java
check "4b.x gaten aktiveras bara av provider.properties (inte consumer)" \
  grep -q "^svada.kov.gate.enabled=true" edc/konfig/provider.properties
if grep -q "svada.kov.gate.enabled" edc/konfig/consumer.properties; then
  no "4b.x consumer.properties slår på KoV-gaten – strider mot hård regel 7"
else
  ok "4b.x consumer.properties nämner inte KoV-gaten"
fi

# --- Röd tråd 1: A får inte läcka ut ur DHI ----------------------------
section "4b.x Distribution A stannar bakom kontrollplanet (hård regel 8)"
NAT=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
        ${SVADA_PREFIX:-svada}-fcf-sim 2>/dev/null)
if echo "$NAT" | grep -q "dsp-public"; then
  no "4b.x fcf-sim ligger på dsp-public – A hade kunnat hämtas utan kontrakt"
else
  ok "4b.x fcf-sim (som har A:s GIS-data) ligger fortfarande bara på dhi-internal"
fi
# Katalogen får visa VILLKOREN för A, men A:s data ska inte gå att nå
# utanför DHI. Kontrollera att A:s dataAddress pekar inåt.
AURL=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/v3/assets/${EDC_ASSET_A_ID}" \
        | jq -r '.. | objects | .baseUrl? // empty' | head -n 1)
if [ "$AURL" = "${EDC_ASSET_A_URL}" ]; then
  ok "4b.x A:s dataAddress pekar på DHI-interna ${AURL}"
else
  no "4b.x A:s dataAddress är '$AURL' (förväntat ${EDC_ASSET_A_URL})"
fi

# --- 4b.6 Regression ---------------------------------------------------
section "4b.6 Regression"
ok "4b.6 hanteras av tests/verify_all.sh (kör ap0–ap4b i ordning)"

finish "verify_ap4b"
