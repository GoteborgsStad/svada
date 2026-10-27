#!/usr/bin/env bash
# =====================================================================
# verify_ap11.sh – Återkallelse av intyg: samordnaren stänger ute en part
# =====================================================================
# Bevisar (se docs/koncept/C1-identitet.md):
#  11.1 Svadas utfärdare publicerar en signerad statuslista (Bitstring Status List, JWT).
#  11.2 Bara samordningsrollens nyckel får läsa eller ändra den; rollintygen finns inte i listan.
#  11.3 Återkallas stadens medlemsintyg nekar DHI:s connector staden (401); katalogen svarar inte längre.
#  11.4 Återinsätts intyget fungerar allt igen, utan omstart.
#  11.5 Återkallas DHI:s medlemsintyg avvisar staden DHI:s meddelanden: ett nytt avtal kan inte ingås.
#  11.6 Kontrollrummet: samordnaren stänger ute och släpper in, och utfallet syns.
# MEDVETEN FÖRENKLING: listan ligger i utfärdarens minne; ingen ansökan eller invändning (G15).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Återkallelse av intyg ####"
set -a; . ./.env; set +a
kontrollera_mal

CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"
HUB="http://localhost:${IDENTITY_HUB_SVADA_DID_PORT}"
KAT=$(mktemp)
FAIL=0
c() { local d="$1"; if eval "$2" >/dev/null 2>&1; then ok "$d"; else no "$d"; fi; }

katalogkod() {   # HTTP-statusen i providerns svar syns som CatalogError code i consumerns svar
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\" }" > "$KAT"
  if jq -e '(.["@type"] // "") | test("Catalog")' "$KAT" >/dev/null 2>&1; then echo 200
  elif grep -q 'CatalogError' "$KAT"; then jq -r '.[0].message // "" | fromjson | .code' "$KAT" 2>/dev/null || echo 4xx
  else echo "OKÄNT"; fi
}
vanta_katalog() {   # vanta_katalog <kod> <sek> -> 0 om den väntade koden syns
  for _ in $(seq 1 $(($2 / 2))); do [ "$(katalogkod)" = "$1" ] && return 0; sleep 2; done; return 1
}
satt() { curl -s --max-time 10 -o /dev/null -w '%{http_code}' -X POST -H "X-Api-Key: ${SVADA_STATUS_ADMIN_KEY}" \
    "${HUB}/svada-status/$1/$2/$3"; }
# Städning även vid avbrott (del e, E9): lämna aldrig ett intyg återkallat åt nästa test.
stada_intyg() { for m in dhi stad; do for t in medlemskap deltagare; do satt "$m" "$t" aterinsatt >/dev/null; done; done; }
trap 'stada_intyg; rm -f "$KAT"' EXIT INT TERM
PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
# Kausalt bevis för ett nekande (del e, E7): providerns förhandling med samma correlationId som stadens är TERMINATED
# och felet är 401 Unauthorized från staden. Att stadens förhandling bara inte blivit FINALIZED inom 30 s kunde
# lika gärna vara en långsam förhandling eller ett transportfel.
nekad_av_staden() {  # nekad_av_staden <stadens förhandlings-id> <sek>
  local id="$1" sek="$2" svar
  for _ in $(seq 1 $((sek / 2))); do
    svar=$(curl -s --max-time 15 -X POST "${PROV_MGMT}/v3/contractnegotiations/request" -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
      -H 'content-type: application/json' -d '{"@context":{"@vocab":"https://w3id.org/edc/v0.0.1/ns/"},"@type":"QuerySpec","filterExpression":[{"operandLeft":"correlationId","operator":"=","operandRight":"'"${id}"'"}]}')
    if printf '%s' "${svar}" | jq -e 'length == 1 and .[0].state == "TERMINATED" and ((.[0].errorDetail // "") | test("\"code\":\"401\""))' >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}
# Och den förhandlingen får inte finaliseras senare, när intyget återinsatts, utan att en ny begäran görs.
aldrig_finaliserad() { ! vanta_tillstand "$1" "$2" FINALIZED >/dev/null; }

section "Förutsättningar"
c "katalogen svarar innan något återkallas" "vanta_katalog 200 20"

section "11.1 Statuslistan"
JWT=$(curl -s --max-time 10 "${HUB}/status/revocation/1")
c "11.1a statuslistan hämtas som en JWT (tre delar)" "[ \"\$(echo '$JWT' | awk -F. '{print NF}')\" = 3 ]"
PLF=$(mktemp)
echo "$JWT" | python3 -c 'import sys,base64,json; p=sys.stdin.read().strip().split(".")[1]; sys.stdout.write(base64.urlsafe_b64decode(p+"="*(-len(p)%4)).decode())' > "$PLF"
c "11.1b den är ett BitstringStatusListCredential med syftet revocation" \
  "jq -e '(.vc.type|index(\"BitstringStatusListCredential\")) != null and .vc.credentialSubject.statusPurpose==\"revocation\"' '$PLF'"
c "11.1c utfärdaren är Svadas utfärdare" "jq -e '.iss==\"${SVADA_PARTICIPANT_DID_SVADA}\"' '$PLF'"
rm -f "$PLF"

section "11.2 Behörighet"
LISTA=$(curl -s --max-time 10 -H "X-Api-Key: ${SVADA_STATUS_ADMIN_KEY}" "${HUB}/svada-status")
c "11.2a med samordningsrollens nyckel syns fyra intyg (medlem och deltagare, DHI och staden)" "[ \"\$(echo '$LISTA' | jq 'length')\" = 4 ]"
c "11.2b inget rollintyg finns i listan (rollen intygar organisationen själv)" "! echo '$LISTA' | jq -e 'map(select(.typ|test(\"Role\")))|length>0' >/dev/null"
c "11.2c utan nyckel nekas läsning (401)" "[ \"\$(curl -s -o /dev/null -w '%{http_code}' ${HUB}/svada-status)\" = 401 ]"
c "11.2d utan nyckel nekas återkallelse (401)" "[ \"\$(curl -s -o /dev/null -w '%{http_code}' -X POST ${HUB}/svada-status/stad/medlemskap/aterkalla)\" = 401 ]"
c "11.2e en okänd typ avvisas (400)" "[ \"\$(satt stad rollintyg aterkalla)\" = 400 ]"
c "11.2f en okänd mottagare avvisas (404)" "[ \"\$(satt ingen medlemskap aterkalla)\" = 404 ]"

section "11.3 Stadens medlemsintyg återkallas: staden stängs ute"
c "11.3a återkallelsen godtas (200)" "[ \"\$(satt stad medlemskap aterkalla)\" = 200 ]"
c "11.3b DHI nekar staden: katalogen svarar 401" "vanta_katalog 401 30"

section "11.4 Intyget återinsätts: staden släpps in igen, utan omstart"
c "11.4a återinsättningen godtas (200)" "[ \"\$(satt stad medlemskap aterinsatt)\" = 200 ]"
c "11.4b katalogen svarar igen" "vanta_katalog 200 30"

section "11.5 DHI:s medlemsintyg återkallas: staden avvisar DHI"
hamta_offert() { jq -c --arg a "$EDC_ASSET_B_ID" '[ .dataset ] | flatten | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' "$KAT"; }
forhandla_b() {
  local policy
  katalogkod >/dev/null
  policy=$(hamta_offert | jq -c --arg a "$EDC_ASSET_B_ID" \
    '. + {"@context": ["http://www.w3.org/ns/odrl.jsonld", {"svada": "https://svada.goteborg.se/ns/"}], "assigner": "'"${EDC_PROVIDER_ID}"'", "target": $a}')
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/contractnegotiations" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" }, \"@type\": \"ContractRequest\",
      \"counterPartyAddress\": \"${PROV_DSP}\", \"protocol\": \"${DSP_PROTOKOLL}\", \"policy\": ${policy} }" | jq -r '.["@id"] // empty'
}
tillstand() { curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/$1" | jq -r '.state // "OKÄNT"'; }
vanta_tillstand() {  # vanta_tillstand <id> <sek> <tillstånd>...
  local id="$1" sek="$2" s t; shift 2
  for _ in $(seq 1 $((sek / 2))); do
    s=$(tillstand "$id"); for t in "$@"; do [ "$s" = "$t" ] && { echo "$s"; return 0; }; done; sleep 2
  done; echo "$s"; return 1
}
c "11.5a återkallelsen av DHI:s medlemsintyg godtas (200)" "[ \"\$(satt dhi medlemskap aterkalla)\" = 200 ]"
sleep 4
NEG=$(forhandla_b)
c "11.5b staden avvisar DHI:s avtalsmeddelande: providerns förhandling (samma correlationId) är TERMINATED med 401" "[ -n '$NEG' ] && nekad_av_staden '$NEG' 40"
c "11.5c DHI:s intyg återinsätts (200)" "[ \"\$(satt dhi medlemskap aterinsatt)\" = 200 ]"
c "11.5c2 den nekade förhandlingen finaliseras inte i efterhand (samma id, ingen ny begäran)" "aldrig_finaliserad '$NEG' 16"
sleep 4
NEG2=$(forhandla_b)
c "11.5d positiv kontroll: när intyget är återinsatt ingås en ny förhandling om B (FINALIZED)" "[ -n '$NEG2' ] && [ \"\$(vanta_tillstand '$NEG2' 40 FINALIZED)\" = FINALIZED ]"

section "11.7 Deltagarintyget återkallas separat (medlemskapet förblir giltigt)"
# Kravet gäller BÅDA intygstyperna. Varje intyg ska bära en egen statusreferens, och en återkallelse av deltagarintyget
# ska nekas även när medlemsintyget fortfarande gäller. (En regression där deltagarens index finns kvar i listan men
# credentialStatus saknas i det signerade intyget skulle annars undgå testerna ovan, som bara återkallar medlemskapet.)
HUBB="${SVADA_PREFIX:-svada}-identity-hub-svada"
STATUS_URL="http://identity-hub-svada:49197/status/revocation/1"
intygsstatus() {  # intygsstatus <mottagare> <deltagare|medlemskap> -> "<typ> <index> <lista-url>" ur det SIGNERADE intyget
  docker exec "$HUBB" cat "/vc-utbyte/$1/$2.json" 2>/dev/null | python3 -c '
import sys, json, base64
jwt = json.load(sys.stdin)["rawJwt"].split(".")[1]
vc = json.loads(base64.urlsafe_b64decode(jwt + "=" * (-len(jwt) % 4)))["vc"]
st = vc.get("credentialStatus") or {}
typ = [t for t in vc["type"] if t != "VerifiableCredential"][0]
print(typ, st.get("statusListIndex"), st.get("statusListCredential"), st.get("type"), st.get("statusPurpose"))'
}
index_i_listan() { echo "$LISTA2" | jq -r --arg m "$1" --arg t "$2" '.[] | select(.mottagare==$m and .typ==$t) | .index'; }
LISTA2=$(curl -s --max-time 10 -H "X-Api-Key: ${SVADA_STATUS_ADMIN_KEY}" "${HUB}/svada-status")
for m in dhi stad; do
  for par in "deltagare SvadaParticipantCredential" "medlemskap SvadaMembershipCredential"; do
    set -- $par
    RAD=$(intygsstatus "$m" "$1")
    c "11.7a det signerade ${1}intyget åt ${m} bär en statusreferens med rätt typ, index och lista" \
      "[ \"$RAD\" = \"$2 $(index_i_listan "$m" "$2") ${STATUS_URL} BitstringStatusListEntry revocation\" ]"
  done
done
c "11.7b deltagarens och medlemskapets index skiljer sig åt för samma part" \
  "[ \"$(index_i_listan stad SvadaParticipantCredential)\" != \"$(index_i_listan stad SvadaMembershipCredential)\" ]"
c "11.7c stadens deltagarintyg återkallas (200)" "[ \"\$(satt stad deltagare aterkalla)\" = 200 ]"
LISTA2=$(curl -s --max-time 10 -H "X-Api-Key: ${SVADA_STATUS_ADMIN_KEY}" "${HUB}/svada-status")
c "11.7d bara deltagarintyget är återkallat, medlemsintyget gäller fortfarande" \
  "[ \"\$(echo '$LISTA2' | jq -c '[.[] | select(.mottagare==\"stad\") | {t: .typ, a: .aterkallat}] | sort_by(.t)')\" = '[{\"t\":\"SvadaMembershipCredential\",\"a\":false},{\"t\":\"SvadaParticipantCredential\",\"a\":true}]' ]"
c "11.7e DHI nekar staden även när bara deltagarintyget är återkallat (katalogen svarar 401)" "vanta_katalog 401 30"
c "11.7f stadens deltagarintyg återinsätts (200)" "[ \"\$(satt stad deltagare aterinsatt)\" = 200 ]"
c "11.7g efter återinsättningen når staden DHI igen (katalogen svarar)" "vanta_katalog 200 30"
c "11.7h DHI:s deltagarintyg återkallas (200)" "[ \"\$(satt dhi deltagare aterkalla)\" = 200 ]"
sleep 4
NEG3=$(forhandla_b)
c "11.7i staden avvisar DHI när bara DHI:s deltagarintyg är återkallat (providerns förhandling TERMINATED med 401)" "[ -n '$NEG3' ] && nekad_av_staden '$NEG3' 40"
c "11.7j DHI:s deltagarintyg återinsätts (200)" "[ \"\$(satt dhi deltagare aterinsatt)\" = 200 ]"
sleep 4
NEG4=$(forhandla_b)
c "11.7k positiv kontroll: efter återinsättningen ingås en ny förhandling om B (FINALIZED)" "[ -n '$NEG4' ] && [ \"\$(vanta_tillstand '$NEG4' 40 FINALIZED)\" = FINALIZED ]"

section "11.6 Kontrollrummet: samordnaren agerar och utfallet syns"
DASH="http://localhost:${DASHBOARD_PORT}"
c "11.6a kontrollrummet visar de fyra intygen i statuslistan" "[ \"\$(curl -s ${DASH}/api/svada/status | jq '.poster|length')\" = 4 ]"
c "11.6a2 statusen bär inga intygssubjekt (DID med internt värdnamn)" "[ \"\$(curl -s ${DASH}/api/svada/status | jq 'any(.poster[]; has(\"subjekt\"))')\" = false ]"
c "11.6b en okänd mottagare avvisas (400)" "[ \"\$(curl -s -o /dev/null -w '%{http_code}' -X POST ${DASH}/api/svada/ingen/aterkalla)\" = 400 ]"
# Baslinje för auditkravet (11.6e): bara händelser som tillkommer under provet räknas (del e, E7).
# (Tid och inte antal: auditlistan är kapad, så ett antal kan stå still när äldre poster faller bort.)
AUDIT_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
audit_ny() { curl -s "${DASH}/api/audit" | jq -e --arg k "$1" --arg t "${AUDIT_START}" \
  'any(.handelser[]; .kod == $k and (.p.mottagare // "") == "stad" and .tid >= $t)' >/dev/null; }
curl -s -X POST "${DASH}/api/svada/stad/aterkalla" >/dev/null
prov_nekad() { for _ in $(seq 1 15); do [ "$(curl -s ${DASH}/api/svada/prov | jq -r .ok)" = false ] && return 0; sleep 2; done; return 1; }
prov_ok() { for _ in $(seq 1 15); do [ "$(curl -s ${DASH}/api/svada/prov | jq -r .ok)" = true ] && return 0; sleep 2; done; return 1; }
c "11.6c efter att samordnaren stängt ute staden visar kontrollrummet att staden nekas" "prov_nekad"
curl -s -X POST "${DASH}/api/svada/stad/aterinsatt" >/dev/null
c "11.6d efter återinsättning når staden DHI igen" "prov_ok"
c "11.6e en NY utestängning och en NY återinsättning av staden finns i auditloggen (som kod, med mottagare)" \
  "audit_ny audit.svada_aterkallat && audit_ny audit.svada_aterinsatt"

# Städa: lämna listan utan återkallelser (görs även av trap vid avbrott).
stada_intyg
finish "Återkallelse av intyg"
