#!/usr/bin/env bash
# =====================================================================
# verify_ap8_fas3.sh – utfärdare med rätt mandat: identitet med rätt ansvarsfördelning
# (docs/koncept/C1-identitet.md)
# =====================================================================
# Principen: den som intygar något ska ha mandat att intyga just det.
#   * Svadas utfärdare (samordningsrollen, DSGA 0.1, compose.dsga.yml)
#     utfärdar SvadaParticipantCredential och SvadaMembershipCredential åt
#     DHI och Staden.
#   * Rollintyg utfärdar organisationen själv: staden intygar KoV:s roll
#     (rättighetsinnehavare), DHI sin egen. Svada utfärdar inga rollintyg.
#   * Verifieringen godtar varje intygstyp bara från rätt utfärdare
#     (edc.iam.trustedissuer.*.supportedtypes).
#
# Testfall (8f3.x):
#   1  utfärdaren är uppe och dess DID-dokument kan lösas från båda connectorerna
#   2  DHI:s och Stadens medlems- och deltagarintyg har Svadas DID som issuerId
#   3  Stadens rollintyg har stadens DID som issuerId; DHI utfärdar inget åt staden
#   4  DHI:s hub har inga utfärdade intyg om andra parter (och Svada inga egna)
#   5  hela kedjan går som förut: förhandling, KoV-godkännande av A (verifierad roll)
#   6  NEGATIVT: ett rollintyg som Svada har signerat avvisas av KoV-grinden
#   7  NEGATIVT: ett medlemsintyg som staden har självutfärdat avvisas
#
# 6 och 7 kör hubbarna i TESTLÄGE (SVADA_TEST_NEGATIV, tomt = av) och startar
# om hubbar och connectorer; SIST i skriptet återställs allt och kedjan
# prövas igen. Omstarten nollställer connectorernas in-memory-tillstånd
# (registreringen görs om här). Kör inte i två sessioner samtidigt.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Utfärdare med rätt mandat (docs/koncept/C1-identitet.md) ####"

set -a; . ./.env; set +a
P="${SVADA_PREFIX:-svada}"

PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"
IDENTITY_SVADA="http://localhost:${IDENTITY_HUB_SVADA_IDENTITY_PORT}/api/identity"
IDENTITY_DHI="http://localhost:${IDENTITY_HUB_DHI_IDENTITY_PORT}/api/identity"
IDENTITY_STAD="http://localhost:${IDENTITY_HUB_STAD_IDENTITY_PORT}/api/identity"
KATALOG_FIL="/tmp/svada_ap8fas3_katalog.json"

DHI="docker compose -f compose.dhi.yml"
STAD="docker compose -f compose.stad.yml"
DSGA="docker compose -f compose.dsga.yml"

vanta_friska() {   # vanta_friska <sekunder> <container...>
  local sek="$1"; shift
  for _ in $(seq 1 $((sek / 2))); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$@" 2>/dev/null | sort -u)" = "healthy" ] && return 0
    sleep 2
  done
  return 1
}

# Admin-nyckeln skrivs i hubbens logg vid varje uppstart (visas bara då).
hubbnyckel() {   # hubbnyckel <container>
  docker logs "$1" 2>&1 | sed 's/\x1b\[[0-9;]*m//g' \
    | grep -o 'API-NYCKEL[^:]*: [^ ]*' | tail -1 | sed 's/.*: //'
}

# intyg <identity-url> <container> <deltagar-id> -> JSON-lista med hubbens intyg
intyg() {
  curl -s --max-time 15 -H "x-api-key: $(hubbnyckel "$2")" "$1/v1alpha/participants/$3/credentials"
}

# Kort rad per intyg: typ|utfärdare|innehavare
intygsrader() {   # intygsrader <identity-url> <container> <deltagar-id>
  intyg "$1" "$2" "$3" | jq -r '.[] | [ (.verifiableCredential.credential.type
      | map(select(. != "VerifiableCredential")) | join(",")), .issuerId, .holderId ] | join("|")'
}

hamta_katalog() {
  curl -s --max-time 40 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\"
    }" > "${KATALOG_FIL}"
}

katalog_ok() {
  jq -e '(.["@type"] // "") | test("Catalog")' "${KATALOG_FIL}" >/dev/null 2>&1 \
    && ! grep -q "CatalogError" "${KATALOG_FIL}"
}

offert() {   # offert <asset-id>
  jq -c --arg a "$1" '[ .dataset ] | flatten
      | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' "${KATALOG_FIL}"
}

forhandla() {   # forhandla <asset-id> -> consumerns förhandlings-id
  local asset="$1" policy
  policy=$(offert "$asset" | jq -c --arg a "$asset" \
    '. + {"@context": ["http://www.w3.org/ns/odrl.jsonld",
                       {"svada": "https://svada.goteborg.se/ns/"}],
          "assigner": "'"${EDC_PROVIDER_ID}"'", "target": $a}')
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/contractnegotiations" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"@type\": \"ContractRequest\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\",
      \"policy\": ${policy}
    }" | jq -r '.["@id"] // empty'
}

tillstand() {   # tillstand <consumerns förhandlings-id>
  curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    "${CONS_MGMT}/v3/contractnegotiations/$1" | jq -r '.state // empty'
}

# Hela identitetsstacken i ett definierat läge. Hubbarna får nya nyckelpar vid
# varje start, så connectorerna startas om (DID-resolverns cache) och
# tillgångarna registreras om (in-memory). $1 = värde för SVADA_TEST_NEGATIV.
starta_om_identitet() {
  export SVADA_TEST_NEGATIV="$1"
  $DSGA --profile dsga-utfardare up -d --no-deps --force-recreate --wait --wait-timeout 240 identity-hub-svada >/tmp/svada_ap8fas3_up.log 2>&1 \
    || { echo "  (identity-hub-svada kunde inte återskapas: $(tail -1 /tmp/svada_ap8fas3_up.log))"; return 1; }
  $DHI --profile dhi-identitet up -d --no-deps --force-recreate --wait --wait-timeout 240 identity-hub-dhi >/tmp/svada_ap8fas3_up.log 2>&1 \
    || { echo "  (identity-hub-dhi kunde inte återskapas: $(tail -1 /tmp/svada_ap8fas3_up.log))"; return 1; }
  $STAD --profile stad-identitet up -d --no-deps --force-recreate --wait --wait-timeout 240 identity-hub-stad >/tmp/svada_ap8fas3_up.log 2>&1 \
    || { echo "  (identity-hub-stad kunde inte återskapas: $(tail -1 /tmp/svada_ap8fas3_up.log))"; return 1; }
  # Återskapas (inte docker restart): rollsträngen och andra .env-värden läses bara när
  # containern skapas, och en omstart tömmer DID-resolverns cache.
  # Alla profiler krävs: compose validerar depends_on mot hela projektet (jfr stoppa-demo.sh).
  $DHI --profile dhi-fcf --profile dhi-identitet --profile dhi-edc \
    up -d --no-deps --force-recreate --wait --wait-timeout 240 edc-provider >/tmp/svada_ap8fas3_up.log 2>&1 \
    || { echo "  (edc-provider kunde inte återskapas: $(tail -1 /tmp/svada_ap8fas3_up.log))"; return 1; }
  $STAD --profile stad-dataplan --profile stad-identitet --profile stad-edc --profile stad-ingest \
    up -d --no-deps --force-recreate --wait --wait-timeout 240 edc-consumer >/tmp/svada_ap8fas3_up.log 2>&1 \
    || { echo "  (edc-consumer kunde inte återskapas: $(tail -1 /tmp/svada_ap8fas3_up.log))"; return 1; }
  vanta_friska 180 "${P}-edc-provider" "${P}-edc-consumer" || return 1
  $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap8fas3_bootstrap.log 2>&1
}

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (utfärdare + DHI + Staden + connectorer, normalläge)"
PROV_ROLL="$(docker exec "${P}-edc-provider" printenv SVADA_KOV_ROLLINNEHAVARE 2>/dev/null)"
# Hubbarna får nya nycklar vid varje start; connectorer som är äldre än någon hub har en
# föråldrad DID-cache (tyst 401 eller "JWT signature not valid"). Connectorerna ska alltså
# vara startade EFTER alla tre hubbar.
startad() { docker inspect -f '{{.State.StartedAt}}' "$1" 2>/dev/null; }
SENASTE_HUBB="$(for h in svada dhi stad; do startad "${P}-identity-hub-${h}"; done | sort | tail -1)"
AELDSTA_CONN="$(for c in edc-provider edc-consumer; do startad "${P}-${c}"; done | sort | head -1)"
if [ "${PROV_ROLL}" = "${SVADA_KOV_ROLLINNEHAVARE}" ] && [ -n "${SENASTE_HUBB}" ] \
   && [[ "${AELDSTA_CONN}" > "${SENASTE_HUBB}" ]] \
   && [ "$(intygsrader "${IDENTITY_DHI}" "${P}-identity-hub-dhi" dhi | grep -c "|${SVADA_PARTICIPANT_DID_SVADA}|")" = "2" ] \
   && [ "$(intygsrader "${IDENTITY_STAD}" "${P}-identity-hub-stad" stad | grep -c "|${SVADA_PARTICIPANT_DID_SVADA}|")" = "2" ] \
   && docker inspect "${P}-identity-hub-svada" >/dev/null 2>&1 \
   && vanta_friska 4 "${P}-identity-hub-svada" "${P}-identity-hub-dhi" "${P}-identity-hub-stad" \
     "${P}-edc-provider" "${P}-edc-consumer"; then
  ok "utfärdaren, båda hubbarna och båda connectorerna var redan uppe"
else
  echo "  (återskapar identitetsstacken i normalläge: nya intyg, ny rollsträng, connectorer ...)"
  if starta_om_identitet ""; then ok "identitetsstacken uppe i normalläge"; else no "identitetsstacken kom inte upp"; fi
fi

# --- 8f3.1 Utfärdaren uppe, DID lösbar från båda connectorerna ---------------
section "8f3.1 Utfärdaren uppe och dess DID-dokument kan lösas från båda connectorerna"
[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://localhost:${IDENTITY_HUB_SVADA_DEFAULT_PORT}/api/check/health")" = "200" ] \
  && ok "8f3.1 identity-hub-svada svarar frisk" || no "8f3.1 identity-hub-svada svarar inte frisk"
for c in edc-provider edc-consumer; do
  DID_DOK="$(docker exec "${P}-${c}" curl -s --max-time 10 "http://identity-hub-svada:49197/.well-known/did.json")"
  if [ "$(echo "${DID_DOK}" | jq -r '.id // empty')" = "${SVADA_PARTICIPANT_DID_SVADA}" ] \
     && echo "${DID_DOK}" | jq -e '.verificationMethod | length > 0' >/dev/null 2>&1; then
    ok "8f3.1 ${c} löser utfärdarens DID-dokument (${SVADA_PARTICIPANT_DID_SVADA}) med publik nyckel"
  else
    no "8f3.1 ${c} kan inte lösa utfärdarens DID-dokument: $(echo "${DID_DOK}" | head -c 150)"
  fi
done

# --- 8f3.2 Medlems- och deltagarintygen kommer från Svada --------------------
section "8f3.2 DHI:s och Stadens medlems- och deltagarintyg har Svada som utfärdare"
for part in dhi stad; do
  if [ "${part}" = "dhi" ]; then DID_PART="${SVADA_PARTICIPANT_DID_DHI}"; URL_PART="${IDENTITY_DHI}"
  else DID_PART="${SVADA_PARTICIPANT_DID_STAD}"; URL_PART="${IDENTITY_STAD}"; fi
  RADER="$(intygsrader "${URL_PART}" "${P}-identity-hub-${part}" "${part}")"
  for typ in SvadaParticipantCredential SvadaMembershipCredential; do
    if echo "${RADER}" | grep -qx "${typ}|${SVADA_PARTICIPANT_DID_SVADA}|${DID_PART}"; then
      ok "8f3.2 ${part}: ${typ} utfärdat av Svada (${SVADA_PARTICIPANT_DID_SVADA})"
    else
      no "8f3.2 ${part}: ${typ} saknas eller har fel utfärdare. Intyg: $(echo "${RADER}" | tr '\n' ' ')"
    fi
  done
done

# --- 8f3.3 Rollintyget intygas av staden själv -------------------------------
section "8f3.3 Stadens rollintyg har stadens DID som utfärdare; DHI utfärdar inget åt staden"
RADER_STAD="$(intygsrader "${IDENTITY_STAD}" "${P}-identity-hub-stad" stad)"
if echo "${RADER_STAD}" | grep -qx "SvadaRoleCredential|${SVADA_PARTICIPANT_DID_STAD}|${SVADA_PARTICIPANT_DID_STAD}"; then
  ok "8f3.3 stadens SvadaRoleCredential har stadens DID som både utfärdare och innehavare"
else
  no "8f3.3 stadens rollintyg har fel utfärdare. Intyg: $(echo "${RADER_STAD}" | tr '\n' ' ')"
fi
if echo "${RADER_STAD}" | grep -q "^[^|]*|${SVADA_PARTICIPANT_DID_DHI}|"; then
  no "8f3.3 DHI förekommer som utfärdare av ett av stadens intyg"
else
  ok "8f3.3 DHI förekommer inte som utfärdare av något av stadens intyg"
fi
ROLL_TEXT="$(intyg "${IDENTITY_STAD}" "${P}-identity-hub-stad" stad \
  | jq -r '[.[] | select(.verifiableCredential.credential.type | index("SvadaRoleCredential"))][0].verifiableCredential.credential.credentialSubject[0].role // empty')"
[ "${ROLL_TEXT}" = "${SVADA_KOV_ROLLINNEHAVARE}" ] \
  && ok "8f3.3 rollintygets text är '${ROLL_TEXT}'" \
  || no "8f3.3 rollintygets text är '${ROLL_TEXT}', förväntat '${SVADA_KOV_ROLLINNEHAVARE}'"

# --- 8f3.4 DHI:s hub utfärdar inget åt andra; Svada har inga egna intyg -------
section "8f3.4 DHI:s hub har inga intyg om andra parter; Svada har inga egna intyg"
RADER_DHI="$(intygsrader "${IDENTITY_DHI}" "${P}-identity-hub-dhi" dhi)"
if echo "${RADER_DHI}" | grep -q . && ! echo "${RADER_DHI}" | awk -F'|' -v d="${SVADA_PARTICIPANT_DID_DHI}" '$3 != d {f=1} END {exit !f}'; then
  ok "8f3.4 alla intyg i DHI:s hub gäller DHI själv ($(echo "${RADER_DHI}" | wc -l | tr -d ' ') intyg)"
else
  no "8f3.4 DHI:s hub har intyg om andra parter eller inga alls: $(echo "${RADER_DHI}" | tr '\n' ' ')"
fi
if echo "${RADER_DHI}" | grep -qx "SvadaRoleCredential|${SVADA_PARTICIPANT_DID_DHI}|${SVADA_PARTICIPANT_DID_DHI}"; then
  ok "8f3.4 DHI:s egen roll är intygad av DHI självt"
else
  no "8f3.4 DHI:s rollintyg saknas eller har fel utfärdare: $(echo "${RADER_DHI}" | tr '\n' ' ')"
fi
SVADA_EGNA="$(intyg "${IDENTITY_SVADA}" "${P}-identity-hub-svada" svada | jq 'length')"
[ "${SVADA_EGNA}" = "0" ] && ok "8f3.4 Svadas utfärdare har inga egna intyg (och utfärdar inga rollintyg)" \
  || no "8f3.4 Svadas hub har ${SVADA_EGNA} intyg i sitt eget lager (förväntat 0)"
if docker exec "${P}-identity-hub-svada" sh -c 'ls /vc-utbyte/*/' 2>/dev/null | grep -qx 'roll.json'; then
  no "8f3.4 Svada har exporterat ett rollintyg (roll.json)"
else
  ok "8f3.4 Svada har inte exporterat något rollintyg"
fi

# --- 8f3.5 Hela kedjan som förut ---------------------------------------------
section "8f3.5 Kedjan går som förut: katalog, förhandling om B, förhandling om A och KoV-godkännande"
hamta_katalog
if katalog_ok; then ok "8f3.5 DSP-katalogen svarar (båda parter verifierade med de nya utfärdarna)"; else
  no "8f3.5 DSP-katalogen svarar inte: $(head -c 200 "${KATALOG_FIL}")"; fi

NEG_B="$(forhandla "${EDC_ASSET_B_ID}")"
TILL=""
for _ in $(seq 1 20); do sleep 2; TILL="$(tillstand "${NEG_B}")"; [ "${TILL}" = "FINALIZED" ] && break; done
[ "${TILL}" = "FINALIZED" ] && ok "8f3.5 förhandlingen om B blev FINALIZED" || no "8f3.5 förhandlingen om B blev '${TILL}'"

NEG_A="$(forhandla "${EDC_ASSET_A_ID}")"
PROV_ID=""
for _ in $(seq 1 15); do
  sleep 2
  PROV_ID="$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/kov/forhandlingar" \
    | jq -r --arg c "${NEG_A}" '[ .[] | select(.correlationId == $c) ] | .[0].id // empty')"
  [ -n "${PROV_ID}" ] && break
done
if [ -n "${PROV_ID}" ]; then
  ok "8f3.5 förhandlingen om A hamnade i KoV-kön"
  TOKEN="$(hamta_kov_token)"
  SVAR="$(curl -s --max-time 30 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" -H "Authorization: Bearer ${TOKEN}" \
    "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann")"
  if [ "$(echo "${SVAR}" | jq -r '.beslutsfattare // empty')" = "${SVADA_KOV_ROLLINNEHAVARE}" ]; then
    ok "8f3.5 KoV-godkännandet accepterades med stadens rollintyg (beslutsfattare '${SVADA_KOV_ROLLINNEHAVARE}')"
  else
    no "8f3.5 KoV-godkännandet accepterades inte: $(echo "${SVAR}" | head -c 300)"
  fi
  TILL=""
  for _ in $(seq 1 30); do sleep 2; TILL="$(tillstand "${NEG_A}")"; [ "${TILL}" = "FINALIZED" ] && break; done
  [ "${TILL}" = "FINALIZED" ] && ok "8f3.5 förhandlingen om A blev FINALIZED efter KoV-godkännandet" \
    || no "8f3.5 förhandlingen om A blev '${TILL}'"
else
  no "8f3.5 förhandlingen om A dök aldrig upp i KoV-kön"
fi

# --- 8f3.6 NEGATIVT: ett rollintyg som Svada signerat avvisas av KoV-grinden --
section "8f3.6 Negativt: ett rollintyg som Svada har signerat avvisas av KoV-grinden"
# Referens (normalläge): ett KoV-anrop med giltigt token passerar verifieringen och
# stoppas först av att id:t inte finns (404). Utfärdaren signerar nu dessutom ett
# rollintyg med RÄTT text men FEL utfärdare; då ska verifieringen avvisa (401).
TOKEN="$(hamta_kov_token)"
REF="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
  -H "Authorization: Bearer ${TOKEN}" "${PROV_MGMT}/kov/forhandlingar/finns-inte/godkann")"
[ "${REF}" = "404" ] && ok "8f3.6 referens: stadens eget rollintyg passerar verifieringen (HTTP ${REF} = okänt id)" \
  || no "8f3.6 referensanropet svarade HTTP ${REF}, förväntat 404"
echo "  (testläge svada-roll: startar om utfärdare, hubbar och connectorer ...)"
if starta_om_identitet "svada-roll"; then ok "8f3.6 stacken uppe i testläge svada-roll"; else no "8f3.6 stacken kom inte upp i testläge"; fi
docker logs "${P}-identity-hub-stad" 2>&1 | grep -q "TESTLÄGE svada-roll - lagrar ett rollintyg utfärdat av Svada" \
  && ok "8f3.6 staden håller nu ett rollintyg utfärdat av Svada (testlägets avsikt)" \
  || no "8f3.6 testläget lagrade inget Svada-signerat rollintyg"
TOKEN="$(hamta_kov_token)"
SVAR="$(curl -s -w '\n%{http_code}' --max-time 30 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
  -H "Authorization: Bearer ${TOKEN}" "${PROV_MGMT}/kov/forhandlingar/finns-inte/godkann")"
KOD="${SVAR##*$'\n'}"; KROPP="${SVAR%$'\n'*}"
if [ "${KOD}" = "401" ]; then
  ok "8f3.6 KoV-grinden avvisar ett rollintyg som Svada signerat (HTTP 401)"
else
  no "8f3.6 KoV-grinden svarade HTTP ${KOD} (förväntat 401): $(echo "${KROPP}" | head -c 300)"
fi
if echo "${KROPP}" | grep -q "SvadaRoleCredential" && echo "${KROPP}" | grep -q "identity-hub-svada"; then
  ok "8f3.6 avslaget namnger intygstypen och utfärdaren (SvadaRoleCredential, identity-hub-svada)"
else
  no "8f3.6 avslaget namnger inte typ och utfärdare: $(echo "${KROPP}" | head -c 400)"
fi

# --- 8f3.7 NEGATIVT: ett medlemsintyg som staden självutfärdat avvisas -------
section "8f3.7 Negativt: ett medlemsintyg som staden har självutfärdat avvisas"
echo "  (testläge medlemskap-sjalvutfardat: startar om utfärdare, hubbar och connectorer ...)"
if starta_om_identitet "medlemskap-sjalvutfardat"; then ok "8f3.7 stacken uppe i testläge medlemskap-sjalvutfardat"; else no "8f3.7 stacken kom inte upp i testläge"; fi
for _ in 1 2 3 4 5 6; do          # omförsök: admin-nyckeln läses ur `docker logs`, som under belastning kan vara ofullständig
  SJALV="$(intygsrader "${IDENTITY_STAD}" "${P}-identity-hub-stad" stad \
    | grep -cx "SvadaMembershipCredential|${SVADA_PARTICIPANT_DID_STAD}|${SVADA_PARTICIPANT_DID_STAD}")"
  [ "${SJALV}" = "1" ] && break
  sleep 4
done
[ "${SJALV}" = "1" ] && ok "8f3.7 staden håller ett medlemsintyg som den själv utfärdat (testlägets avsikt)" \
  || no "8f3.7 testläget gav ${SJALV} självutfärdade medlemsintyg (förväntat 1)"
# Kontrollerat experiment: stacken är i övrigt identisk med normalläget, där DSP-katalogen
# godtogs (8f3.5) och godtas igen efter återställningen nedan. Enda skillnaden är att staden
# nu håller ett medlemsintyg som den själv utfärdat, utöver det Svada utfärdat. Att anropet
# avvisas just nu kan alltså bara bero på det intyget.
for _ in 1 2 3 4 5 6; do
  MEDLEM="$(intygsrader "${IDENTITY_STAD}" "${P}-identity-hub-stad" stad | grep -c '^SvadaMembershipCredential|')"
  [ "${MEDLEM}" = "2" ] && break
  sleep 4
done
[ "${MEDLEM}" = "2" ] && ok "8f3.7 staden håller två medlemsintyg: ett från Svada och ett självutfärdat" \
  || no "8f3.7 staden håller ${MEDLEM} medlemsintyg (förväntat 2)"
hamta_katalog
if ! katalog_ok && grep -q 'Unauthorized' "${KATALOG_FIL}"; then
  ok "8f3.7 providern avvisar DSP-anropet (401) när staden presenterar ett självutfärdat medlemsintyg"
else
  no "8f3.7 DSP-katalogen svarade trots ett självutfärdat medlemsintyg: $(head -c 200 "${KATALOG_FIL}")"
fi

# --- Återställning och kontroll att kedjan går igen --------------------------
section "Återställning: normalläge och kedjan igen"
if starta_om_identitet ""; then ok "stacken uppe i normalläge igen"; else no "stacken kom inte upp i normalläge"; fi
hamta_katalog
katalog_ok && ok "DSP-katalogen godtas igen i normalläge (kontrollen för 8f3.7: utan det självutfärdade intyget godtas samma anrop)" || no "DSP-katalogen svarar inte i normalläge: $(head -c 200 "${KATALOG_FIL}")"
TOKEN="$(hamta_kov_token)"
REF="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
  -H "Authorization: Bearer ${TOKEN}" "${PROV_MGMT}/kov/forhandlingar/finns-inte/godkann")"
[ "${REF}" = "404" ] && ok "KoV-grinden släpper igenom stadens eget rollintyg igen (HTTP ${REF})" \
  || no "KoV-grinden svarade HTTP ${REF} i normalläge, förväntat 404"

finish "Utfärdare med rätt mandat"
