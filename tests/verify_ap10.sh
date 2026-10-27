#!/usr/bin/env bash
# =====================================================================
# verify_ap10.sh – Avtal gäller tills de hävs (gren avtal-havning)
# =====================================================================
# Bevisar:
#  10.1 Avtalets id är OLIKA hos DHI och staden (EDC 0.17.0, uppmätt); kopplingen går via förhandlingen.
#  10.2 Stadens avtalsregister ser avtalet, med ODRL-ögonblicksbild och status.
#  10.3 Ett godkänt avtal ger en nyckel som släpps in; B påverkas inte av något nedan.
#  10.4 Ett AVSLAG av en ny begäran om A häver det tidigare avtalet (PoC-regel), eller häver inget när SVADA_KOV_AVSLAG_HAVARTIDIGARE=false.
#  10.5 Efter hävningen: ingen ny nyckel, och den gamla nyckeln hämtar ingen data.
#  10.6 KoV kan häva ett avtal direkt (knappen), men bara med KoV-rollintyget.
#  10.7 Ett nytt godkännande ger ett NYTT avtal som gäller; det hävda förblir hävt.
#  10.11 Avtalets giltighetstid: UTGANGET i registret, ingen ny nyckel, överföringen nekas.
#  10.10 Staden läser en smal, skrivskyddad avtalsstatus med egen nyckel, inte providerns management-API.
# MEDVETEN FÖRENKLING: hävningen är en PoC-mekanism (se docs/koncept/06).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Avtal gäller tills de hävs ####"
set -a; . ./.env; set +a
kontrollera_mal

PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"
INGEST="http://localhost:${INGEST_PORT}"
GATEWAY="http://localhost:${ORION_STAD_PORT}"
KAT=$(mktemp)
FAIL=0
c() { local d="$1"; if eval "$2" >/dev/null 2>&1; then ok "$d"; else no "$d"; fi; }

hamta_katalog() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\" }" > "$KAT"
}
offert() {
  jq -c --arg a "$1" '[ .dataset ] | flatten | map(select(.["@id"] == $a))
      | .[0].hasPolicy | [.] | flatten | .[0]' "$KAT"
}
forhandla() {
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
      \"protocol\": \"${DSP_PROTOKOLL}\", \"policy\": ${policy} }" | jq -r '.["@id"] // empty'
}
neg() { curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/$1"; }
vanta_pa() {   # vanta_pa <id> <sek> <tillstånd>...
  local id="$1" sek="$2" s t; shift 2
  for _ in $(seq 1 $((sek / 2))); do
    s=$(neg "$id" | jq -r '.state // "OKÄNT"')
    for t in "$@"; do [ "$s" = "$t" ] && { echo "$s"; return 0; }; done
    sleep 2
  done
  echo "$s"; return 1
}
providerpost() {
  curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/kov/forhandlingar" \
    | jq -c --arg c "$1" '[ .[] | select(.correlationId == $c) ] | .[0] // empty'
}
vanta_pa_provider() {   # väntar tills providerposten finns (A parkerar hos providern)
  local p
  for _ in $(seq 1 20); do
    p=$(providerpost "$1"); [ -n "$p" ] && { echo "$p"; return 0; }; sleep 2
  done; return 1
}
kov() {   # kov <godkann|avsla> <providerns-id> -> svaret
  curl -s --max-time 20 -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
    -H "Authorization: Bearer $(hamta_kov_token)" "${PROV_MGMT}/kov/forhandlingar/$2/$1"
}
avtalsstatus() { curl -s --max-time 10 "${INGEST}/avtal/$1/status" | jq -r '.status // "OKÄNT"'; }
vanta_status() {   # vanta_status <avtal> <status> <sek>
  local s
  for _ in $(seq 1 $(($3 / 1))); do
    s=$(avtalsstatus "$1"); [ "$s" = "$2" ] && { echo "$s"; return 0; }; sleep 1
  done; echo "$s"; return 1
}
token_for() { curl -s --max-time 10 -X POST "${INGEST}/auktorisation" -H 'content-type: application/json' \
    -d "{\"contractAgreementId\":\"$1\"}"; }
gw_token_for() { curl -s --max-time 10 -X POST "${GATEWAY}/auktorisation" -H 'content-type: application/json' \
    -d "{\"contractAgreementId\":\"$1\"}"; }
PROV_CONT="${SVADA_PREFIX:-svada}-edc-provider"
# transfer <avtals-id> <token> -> slutläge (COMPLETED/TERMINATED/OKÄNT)
transfer() {
  local tp s="OKÄNT"
  tp=$(curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/transferprocesses" \
      -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"@type\": \"TransferRequest\", \"counterPartyAddress\": \"${PROV_DSP}\",
      \"contractId\": \"$1\", \"protocol\": \"${DSP_PROTOKOLL}\",
      \"transferType\": \"${EDC_TRANSFER_TYPE}\",
      \"dataDestination\": { \"type\": \"HttpData\", \"baseUrl\": \"http://ingest-service:8060/ingest\",
        \"authKey\": \"Authorization\", \"authCode\": \"Bearer $2\" } }" | jq -r '.["@id"] // empty')
  [ -n "$tp" ] || { echo "OKÄNT"; return; }
  for _ in $(seq 1 25); do
    s=$(curl -s -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/transferprocesses/${tp}" | jq -r '.state // "OKÄNT"')
    case "$s" in TERMINATED|COMPLETED) break;; esac; sleep 2
  done
  echo "$s"
}
gw_las() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H "Authorization: Bearer $1" \
    -H 'Accept: application/json' "${GATEWAY}/ngsi-ld/v1/entities?type=Manhole&limit=1"; }

section "Förutsättningar"
hamta_katalog
[ -n "$(offert "$EDC_ASSET_A_ID")" ] && ok "katalogen har offerten för A" || no "katalogen saknar A (kör registrera-edc)"
[ "$(curl -s -o /dev/null -w '%{http_code}' "${INGEST}/health")" = 200 ] && ok "ingest uppe" || no "ingest nere"

section "10.1/10.2/10.3 Ett godkänt A-avtal"
N1=$(forhandla "$EDC_ASSET_A_ID")
c "10.1a förhandling 1 startad" "[ -n '$N1' ]"
P1=$(vanta_pa_provider "$N1"); PID1=$(echo "$P1" | jq -r '.id // empty')
c "10.1b providerns förhandlings-id skiljer sig från stadens" "[ -n '$PID1' ] && [ '$PID1' != '$N1' ]"
kov godkann "$PID1" >/dev/null
c "10.3a avtal 1 FINALIZED" "[ \"$(vanta_pa "$N1" 40 FINALIZED)\" = FINALIZED ]"
AV1=$(neg "$N1" | jq -r '.contractAgreementId // empty')
c "10.1c avtalet 1 finns och har ett id" "[ -n '$AV1' ]"
DAV1=$(providerpost "$N1" | jq -r '.contractAgreementId // empty')
c "10.1d DHI har ett eget avtals-id som skiljer sig från stadens" "[ -n '$DAV1' ] && [ '$DAV1' != '$AV1' ]"
c "10.1e kopplingen: stadens förhandlings-id är DHI:s correlationId" "[ \"\$(providerpost '$N1' | jq -r .correlationId)\" = '$N1' ]"
c "10.2a stadens register: avtal 1 GALLANDE" "[ \"$(vanta_status "$AV1" GALLANDE 10)\" = GALLANDE ]"
REG=$(curl -s "${INGEST}/avtal/${AV1}")
c "10.2d registret kopplar stadens avtal till DHI:s avtals-id" "[ \"\$(curl -s ${INGEST}/avtal/$AV1 | jq -r .dhiAvtalId)\" = '$DAV1' ]"
c "10.2b registret har ODRL-ögonblicksbild med KoV-plikten" "echo '$REG' | jq -e '.regler.plikter|map(select(test(\"kovGodkannande\")))|length>0' >/dev/null"
c "10.2e avtalet bär revisionsskyldigheten (medgerGranskning) som deklaration" "echo '$REG' | jq -e '.regler.plikter|map(select(test(\"medgerGranskning\")))|length>0' >/dev/null"
c "10.2c avtalet har en löstbar adress" "echo '$REG' | jq -e '.url|test(\"/avtal/\")' >/dev/null"
T1=$(gw_token_for "$AV1" | jq -r '.token // empty')
c "10.3b gatewayen ger nyckel för avtal 1" "[ -n '$T1' ]"
c "10.3c nyckeln släpps in (HTTP 200)" "[ \"$(gw_las "$T1")\" = 200 ]"
# Positiv kontroll: UTAN hävning går överföringen igenom (så att nekandet nedan inte beror på något annat).
IT1=$(token_for "$AV1" | jq -r '.token // empty')
IS1=$(transfer "$AV1" "$IT1")
c "10.3d positiv kontroll: en överföring på det gällande avtalet slutförs (COMPLETED)" "[ -n '$IT1' ] && [ '$IS1' = COMPLETED ]"

section "10.4 Avslag av ny begäran häver det tidigare avtalet"
N2=$(forhandla "$EDC_ASSET_A_ID")
P2=$(vanta_pa_provider "$N2"); PID2=$(echo "$P2" | jq -r '.id // empty')
SV=$(kov avsla "$PID2")
if [ "${SVADA_KOV_AVSLAG_HAVARTIDIGARE:-true}" = "false" ]; then
  # Regeln är avstängd (delad demo): ett avslag häver INGET. Avtal 1 hävs därefter explicit, så att resten av provet (som bygger på ett hävt
  # avtal 1) gäller oförändrat.
  c "10.4a avslaget häver inga avtal när regeln är avstängd" "echo '$SV' | jq -e '(.havdaAvtal|length)==0' >/dev/null"
  c "10.4b avtal 1 gäller fortfarande efter avslaget" "[ \"$(vanta_status "$AV1" GALLANDE 10)\" = GALLANDE ]"
  curl -s -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" -H "Authorization: Bearer $(hamta_kov_token)" "${PROV_MGMT}/kov/avtal/${DAV1}/hav" >/dev/null
  c "10.4c avtal 1 hävs explicit (orsak EXPLICIT) så att resten av provet kan följa" "[ \"$(vanta_status "$AV1" HAVT 10)\" = HAVT ] && [ \"$(curl -s ${INGEST}/avtal/$AV1 | jq -r '.havning.orsak')\" = EXPLICIT ]"
else
  c "10.4a avslaget svarar med avtal 1 som hävt" "echo '$SV' | jq -e --arg a '$DAV1' '.havdaAvtal|index(\$a)!=null' >/dev/null"
  c "10.4b registret visar avtal 1 som HAVT" "[ \"$(vanta_status "$AV1" HAVT 10)\" = HAVT ]"
  c "10.4c orsaken är AVSLAG" "[ \"$(curl -s ${INGEST}/avtal/$AV1 | jq -r '.havning.orsak')\" = AVSLAG ]"
fi

section "10.5 Efter hävningen"
c "10.5a ingen ny nyckel i staden (ingest, 403 avtal-havt)" "[ \"$(token_for "$AV1" | jq -r .fel)\" = avtal-havt ]"
c "10.5b ingen ny nyckel i gatewayen (orsak avtal-havt)" "[ \"$(gw_token_for "$AV1" | jq -r '.orsak // empty')\" = avtal-havt ]"
OR5=$(curl -s -H "Authorization: Bearer $T1" -H 'Accept: application/json' "${GATEWAY}/ngsi-ld/v1/entities?type=Manhole&limit=1" | jq -r '.orsak // .fel // empty')
c "10.5c den gamla nyckeln hämtar ingen data (HTTP 403, orsak avtal-havt)" "[ \"$(gw_las "$T1")\" = 403 ] && [ '$OR5' = avtal-havt ]"

# Providern själv stoppar en överföring på ett hävt avtal (HavdAvtalSparr). Beviset är
# providerns egen loggrad för just det här avtalet efter tidpunkten T0; consumerns felkod
# är allmän ("agreement not found or not valid") och skiljer inte spärren från annat.
T0=$(date -u +%Y-%m-%dT%H:%M:%S)
TPS=$(transfer "$AV1" ingen)
c "10.5d providern avvisar en överföring på hävt avtal (TERMINATED)" "[ '$TPS' = TERMINATED ]"
c "10.5e spärren i providern säger varför, för just detta avtal (loggrad efter T0)" "docker logs --since '${T0}Z' '$PROV_CONT' 2>&1 | grep -q 'överföring nekad.*$DAV1'"

section "10.6 KoV häver direkt (knappen)"
N3=$(forhandla "$EDC_ASSET_A_ID")
P3=$(vanta_pa_provider "$N3"); PID3=$(echo "$P3" | jq -r '.id // empty')
kov godkann "$PID3" >/dev/null
vanta_pa "$N3" 40 FINALIZED >/dev/null
AV3=$(neg "$N3" | jq -r '.contractAgreementId // empty')
DAV3=$(providerpost "$N3" | jq -r '.contractAgreementId // empty')
c "10.7a nytt godkännande ger ett nytt avtal" "[ -n '$AV3' ] && [ '$AV3' != '$AV1' ]"
c "10.7b nya avtalet gäller" "[ \"$(vanta_status "$AV3" GALLANDE 10)\" = GALLANDE ]"
c "10.7c det första är fortfarande hävt" "[ \"$(avtalsstatus "$AV1")\" = HAVT ]"
RE=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" -H "Authorization: Bearer $(hamta_kov_token)" "${PROV_MGMT}/kov/forhandlingar/${PID2}/avsla")
c "10.7d ett upprepat avslag avvisas (409) och häver inte det nya avtalet" "[ '$RE' = 409 ] && [ \"$(avtalsstatus "$AV3")\" = GALLANDE ]"
c "10.6a utan rollintyg avvisas hävningen (401)" "[ \"$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/kov/avtal/${DAV3}/hav")\" = 401 ]"
c "10.6b avtal 3 gäller fortfarande efter avvisad hävning" "[ \"$(avtalsstatus "$AV3")\" = GALLANDE ]"
HV=$(curl -s -X POST -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" -H "Authorization: Bearer $(hamta_kov_token)" "${PROV_MGMT}/kov/avtal/${DAV3}/hav")
c "10.6c explicit hävning ger status HAVT" "echo '$HV' | jq -e '.status==\"HAVT\"' >/dev/null"
c "10.6d registret visar orsak EXPLICIT" "vanta_status '$AV3' HAVT 10 >/dev/null && [ \"\$(curl -s ${INGEST}/avtal/$AV3 | jq -r '.havning.orsak')\" = EXPLICIT ]"

section "10.8 Distribution B påverkas inte"
NB=$(forhandla "$EDC_ASSET_B_ID")
c "10.8a B förhandlas fram automatiskt" "[ \"$(vanta_pa "$NB" 40 FINALIZED)\" = FINALIZED ]"
AVB=$(neg "$NB" | jq -r '.contractAgreementId // empty')
c "10.8b B-avtalet gäller" "[ \"$(vanta_status "$AVB" GALLANDE 10)\" = GALLANDE ]"
IB=$(token_for "$AVB" | jq -r '.token // empty')
IBS=$(transfer "$AVB" "$IB")
c "10.8c en B-överföring slutförs trots att A-avtal hävts (COMPLETED)" "[ -n '$IB' ] && [ '$IBS' = COMPLETED ]"

section "10.10 Staden läser bara en smal, skrivskyddad status (inte providerns management-API)"
IN_BEHALLARE="${SVADA_PREFIX:-svada}-ingest-service"
# Anropet görs inifrån stadens ingest-container: statusporten publiceras aldrig på värden.
httpkod() {   # httpkod <url> [nyckel]  ->  statuskod (000 om ingen kontakt)
  docker exec -e U="$1" -e K="${2:-}" "$IN_BEHALLARE" python -c '
import os, urllib.request, urllib.error
r = urllib.request.Request(os.environ["U"])
if os.environ.get("K"): r.add_header("X-Api-Key", os.environ["K"])
try: print(urllib.request.urlopen(r, timeout=10).status)
except urllib.error.HTTPError as e: print(e.code)
except Exception: print("000")' 2>/dev/null
}
STATUS_URL="http://edc-provider:19195/status/avtalsstatus"
# Läs miljön FÖRST och kräv att det lyckades; annars blir ett misslyckat docker exec "nyckeln saknas" (del e, E5).
IN_ENV="$(docker exec "$IN_BEHALLARE" env 2>/dev/null)"; IN_ENV_RC=$?
c "10.10a stadens ingest-container har inte providerns management-nyckel (miljön lästes: rc=${IN_ENV_RC})" \
  "[ ${IN_ENV_RC} -eq 0 ] && printf '%s' \"\$IN_ENV\" | grep -q '^PATH=' && ! printf '%s' \"\$IN_ENV\" | grep -qF '${EDC_PROVIDER_MGMT_KEY}'"
c "10.10b utan nyckel nekas statusen (401)" "[ \"\$(httpkod '$STATUS_URL')\" = 401 ]"
c "10.10c management-nyckeln öppnar inte statusen (401): nycklarna är åtskilda" \
  "[ \"\$(httpkod '$STATUS_URL' '${EDC_PROVIDER_MGMT_KEY}')\" = 401 ]"
c "10.10d statusnyckeln ger statusen (200)" "[ \"\$(httpkod '$STATUS_URL' '${EDC_PROVIDER_STATUS_KEY}')\" = 200 ]"
c "10.10e statusnyckeln öppnar inte management-API:t (401)" \
  "[ \"\$(httpkod 'http://edc-provider:19193/management/kov/avtal' '${EDC_PROVIDER_STATUS_KEY}')\" = 401 ]"
c "10.10f statusen visar det hävda avtalet med correlationId och orsak" \
  "docker exec -e K='${EDC_PROVIDER_STATUS_KEY}' -e U='$STATUS_URL' -e A='$DAV3' '$IN_BEHALLARE' python -c '
import os, json, urllib.request
r = urllib.request.Request(os.environ[\"U\"]); r.add_header(\"X-Api-Key\", os.environ[\"K\"])
l = json.load(urllib.request.urlopen(r, timeout=10))
p = [x for x in l if x[\"id\"] == os.environ[\"A\"]][0]
assert p[\"status\"] == \"HAVT\" and p[\"havning\"][\"orsak\"] == \"EXPLICIT\" and p[\"correlationId\"]'"

section "10.11 Avtalets giltighetstid: ett avtal gäller i en bestämd tid eller tills det hävs"
# Policyn för A registreras om med en kort giltighet (45 s) och återställs sist.
registrera_giltighet() {
  AVTAL_GILTIGHET="$1" docker compose -f compose.dhi.yml --profile edc-bootstrap run --rm registrera-edc >/dev/null 2>&1
}
# Giltigheten återställs till stackens egen inställning även om provet avbryts (del e, E9): annars ärver nästa test
# en 45-sekunderspolicy.
GILTIGHET_URSPRUNG="${AVTAL_GILTIGHET:-30d}"
trap 'if [ "${GILTIGHET_ANDRAD:-0}" = 1 ]; then echo "  (återställer avtalsgiltigheten till ${GILTIGHET_URSPRUNG} efter avbrott)"; registrera_giltighet "${GILTIGHET_URSPRUNG}"; fi' EXIT INT TERM
GILTIGHET_ANDRAD=1
registrera_giltighet 45s && hamta_katalog
NX=$(forhandla "$EDC_ASSET_A_ID")
PX=$(vanta_pa_provider "$NX"); PIDX=$(echo "$PX" | jq -r '.id // empty')
kov godkann "$PIDX" >/dev/null
vanta_pa "$NX" 40 FINALIZED >/dev/null
AVX=$(neg "$NX" | jq -r '.contractAgreementId // empty')
c "10.11a avtalet gäller i början" "[ \"$(vanta_status "$AVX" GALLANDE 10)\" = GALLANDE ]"
RX=$(curl -s "${INGEST}/avtal/${AVX}")
c "10.11b registret har läst giltighetstiden ur policyn (giltigTill = signerat + 45 s)" \
  "[ \"\$(echo '$RX' | jq -r '.giltigTill - .signerat | floor')\" = 45 ]"
IX=$(token_for "$AVX" | jq -r '.token // empty')
c "10.11c en nyckel utfärdas och en överföring slutförs inom giltigheten (COMPLETED)" \
  "[ -n '$IX' ] && [ \"\$(transfer '$AVX' '$IX')\" = COMPLETED ]"
IX2=$(token_for "$AVX" | jq -r '.token // empty')
GT=$(gw_token_for "$AVX" | jq -r '.token // empty')
c "10.11c2 före utgången ger gatewayen en nyckel och släpper in den (HTTP 200)" "[ -n '$GT' ] && [ \"\$(gw_las '$GT')\" = 200 ]"
SLUT=$(echo "$RX" | jq -r '.giltigTill | floor')
while [ "$(date +%s)" -le $((SLUT + 2)) ]; do sleep 1; done
c "10.11d efter utgången är status UTGANGET i registret" "[ \"$(vanta_status "$AVX" UTGANGET 10)\" = UTGANGET ]"
c "10.11e ingen ny nyckel: ingest nekar med avtal-utgatt" \
  "[ \"\$(token_for '$AVX' | jq -r '.fel // empty')\" = avtal-utgatt ]"
c "10.11f gatewayen nekar nyckeln som utfärdades före utgången (403, avtal-utgatt)" \
  "[ \"\$(gw_las '$GT')\" = 403 ] && [ \"\$(curl -s -H 'Authorization: Bearer $GT' -H 'Accept: application/json' '${GATEWAY}/ngsi-ld/v1/entities?type=Manhole&limit=1' | jq -r '.orsak // empty')\" = avtal-utgatt ]"
# Providern verkställer giltighetstiden SJÄLV: den svarar på TransferRequestMessage med 409 "agreement not found or not valid".
# Nyckeln IX2 är utfärdad före utgången och oanvänd, så det är inte stadens mottagning som nekar.
c "10.11g överföringen nekas efter utgången (TERMINATED)" "[ \"\$(transfer '$AVX' '$IX2')\" = TERMINATED ]"
SENASTE=$(curl -s -X POST "${CONS_MGMT}/v3/transferprocesses/request" -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' \
  -d '{"@context":{"@vocab":"https://w3id.org/edc/v0.0.1/ns/"},"limit":1,"sortField":"createdAt","sortOrder":"DESC"}' | jq -r '.[0].errorDetail // empty')
c "10.11g2 det är DHI:s connector som nekar: dess svar säger att avtalet inte är giltigt (409)" \
  "echo '$SENASTE' | grep -q 'agreement not found or not valid'"
registrera_giltighet "${GILTIGHET_URSPRUNG}" && GILTIGHET_ANDRAD=0 && hamta_katalog
c "10.11h giltigheten är återställd till 30 dagar i katalogen" \
  "offert '$EDC_ASSET_A_ID' | jq -e 'tostring | test(\"contractAgreement\\\\+30d\")' >/dev/null"

rm -f "$KAT"
section "10.9 Stängt som standard (enhetstest, utan stack)"
c "10.9 okänd status nekas: OKAND i registret och 403 avtal-status-okand i gatewayen när statusen inte kan bekräftas" "python3 -I tests/avtal_enhet.py"
c "10.12 avtalssidan har rubrikerna på vyns språk, villkoren i klartext (F9)" "curl -s http://localhost:${DASHBOARD_PORT}/avtal/$AV3?lang=sv | grep -q 'Tillåtet (permitted)' && curl -s http://localhost:${DASHBOARD_PORT}/avtal/$AV3?lang=en | grep -q '<h3>Permitted</h3>'"
c "10.13 cip-sidan: Växla (inte Väx), Kretslopp och Vatten med stort V och rubriken på svenska (F12)" "T=\$(curl -s -H 'Accept: text/html' '${GATEWAY}/ngsi-ld/v1/entities?type=SewerOverflowModelA&limit=1'); grep -q 'Växla avtalets' <<<\"\$T\" && ! grep -q 'Väx avtalets' <<<\"\$T\" && ! grep -q 'Kretslopp och vatten' <<<\"\$T\" && grep -q 'Åtkomst kräver godkännande' <<<\"\$T\""

finish "Avtalsgiltighet och hävning"
