#!/usr/bin/env bash
# =====================================================================
# verify_ap4c.sh – överföring och mottagning: transfer, ingest och enforcement
# Prövar testfallen 4c.1–4c.7.
# =====================================================================
# Självständigt och idempotent: startar stadens dataplan, båda
# connectorerna, fcf-sim och ingest-service, kör registreringen och
# genomför HELA sekvensen i en följd. Precis som i förhandlingsprovet (verify_ap4b.sh) är det ett krav:
# EDC:s stores är in-memory, så avtal, transferar
# och KoV-beslut överlever inte en omstart.
#
# Kedjan som bevisas:
#   fcf-sim -> edc-provider (dataplan) --HTTP-PUSH--> ingest-service
#           -> orion-stad (CIP) + Mintaka, med proveniens.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Transfer, ingest och enforcement ####"

set -a; . ./.env; set +a

PROV_API="http://localhost:${EDC_PROVIDER_DEFAULT_PORT}/api"
PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_API="http://localhost:${EDC_CONSUMER_DEFAULT_PORT}/api"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"
INGEST="http://localhost:${INGEST_PORT}"
FCF="http://localhost:${FCF_SIM_PORT}"
ORION="http://localhost:${ORION_STAD_PORT}"
# ÅTGÄRD G22: :2026 är numera stad-gateway. Läsning av CIP:en kräver token –
# verifieringen är stadens egen komponent och använder drifttoken. Att
# läsningen NEKAS utan token verifieras i 1.8.
ORION_AUTH=(-H "Authorization: Bearer ${STAD_GATEWAY_DRIFT_TOKEN}")
MINTAKA="http://localhost:${MINTAKA_PORT}"
BRUNN="urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526"          # brunnsregistret (orört av leveranserna)
BRUNN_B="urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526"      # modellerat värde, öppen distribution
BRUNN_A="urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526"      # modellerat värde, skyddad distribution

DHI="docker compose -f compose.dhi.yml"
STAD="docker compose -f compose.stad.yml"

docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

# Felinjektionen ska ALLTID vara avstängd när skriptet lämnar maskinen,
# även om något testfall faller (annars blir verify_ap3.sh 3.8 rött).
avsluta() { curl -s -o /dev/null --max-time 10 -X POST "${FCF}/felinjektion/reset"; }
trap avsluta EXIT

vanta_url() {   # vanta_url <url> <sekunder>
  for _ in $(seq 1 "$2"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1")" = "200" ] \
      && return 0
    sleep 2
  done
  return 1
}

# ---------------------------------------------------------------------
# Hjälpare (förhandlingsdelen är samma mönster som i verify_ap4b.sh)
# ---------------------------------------------------------------------
hamta_katalog() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\"
    }" > /tmp/svada_ap4c_katalog.json
}

# GOTCHA: policyn i ContractRequest måste vara HELA
# katalogofferten + assigner + target, annars faller PolicyEquality.
forhandla() {
  local asset="$1" offer policy
  offer=$(jq -c --arg a "$asset" '[ .dataset ] | flatten
      | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' \
      /tmp/svada_ap4c_katalog.json)
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

avtal_for() {   # avtal_for <förhandlings-id> <sekunder> -> contractAgreementId
  local id="$1" sek="$2" a
  for _ in $(seq 1 $((sek / 2))); do
    a=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/$id" \
          | jq -r '.contractAgreementId // empty')
    [ -n "$a" ] && { echo "$a"; return 0; }
    sleep 2
  done
  return 1
}

# engangstoken <avtals-id> -> token (tom sträng om ingest nekar)
engangstoken() {
  curl -s --max-time 20 -X POST "${INGEST}/auktorisation" \
    -H 'content-type: application/json' \
    -d "{\"contractAgreementId\": \"$1\"}" | jq -r '.token // empty'
}

# starta_transfer <avtals-id> <token> -> transferprocess-id
#
# HttpData-PUSH: providerns dataplan hämtar ur fcf-sim och pushar till
# stadens ingest. Engångstoken följer med som Authorization-header via
# dataDestination.authKey/authCode.
starta_transfer() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/transferprocesses" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"@type\": \"TransferRequest\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"contractId\": \"$1\",
      \"protocol\": \"${DSP_PROTOKOLL}\",
      \"transferType\": \"${EDC_TRANSFER_TYPE}\",
      \"dataDestination\": {
        \"type\": \"HttpData\",
        \"baseUrl\": \"${INGEST_PUSH_URL}\",
        \"authKey\": \"Authorization\",
        \"authCode\": \"Bearer $2\"
      }
    }" | jq -r '.["@id"] // empty'
}

transfertillstand() {   # transfertillstand <id> <sekunder> <tillstånd...>
  local id="$1" sek="$2"; shift 2
  local s
  for _ in $(seq 1 $((sek / 2))); do
    s=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/transferprocesses/$id" \
          | jq -r '.state // "OKÄNT"')
    for t in "$@"; do [ "$s" = "$t" ] && { echo "$s"; return 0; }; done
    sleep 2
  done
  echo "$s"; return 1
}

# Fingeravtryck av brunnen i CIP:en: vilket avtal och vilken batch som
# senast skrev. Används för "inget skrevs"-kontrollerna (4c.3, 4c.5).
fingeravtryck() {
  curl -s --max-time 15 "${ORION_AUTH[@]}" "${ORION}/ngsi-ld/v1/entities/${BRUNN_B}" \
    | jq -r '[(.provenance.value.contractAgreementId // "-"),
              (.provenance.value.batchId // "-"),
              (.provenance.value.ingestedAt // "-")] | join("|")'
}

senaste_leverans() { curl -s --max-time 15 "${INGEST}/leveranser" | jq -c '.deliveries[-1]'; }

senaste_kvitto() {   # sista LEVERERAD/AVVISAD-posten (auktorisationer räknas inte)
  curl -s --max-time 15 "${INGEST}/leveranser" \
    | jq -c '[ .deliveries[] | select(.resultat == "LEVERERAD"
                                      or .resultat == "AVVISAD") ] | .[-1] // empty'
}

# kor_transfer <avtals-id> -> sätter globalerna KVITTO och TP_TILLSTAND.
# (Globaler, inte utskrift: anropad i $( ) hade funktionen kört i en
# SUBSHELL och tilldelningarna försvunnit med den.)
#
# GOTCHA: providerns dataplan tappar ibland
# pushen med "java.io.IOException: closed" när en transfer startas kort
# efter en annan – ingest får då aldrig något anrop och transfern dör i
# tomma intet. Det är en känd svaghet i EDC:s DEPRECATED inbäddade
# dataplan (§2), inte i kedjan vi verifierar. Därför: upptäck att inget
# kvitto kom, andas ut och gör om. Testet väntar på KVITTOT, inte bara på
# transferns tillstånd.
TP_TILLSTAND=""
KVITTO=""
kor_transfer() {
  local avtal="$1" fore token tp post
  fore=$(senaste_kvitto)
  for _ in 1 2 3; do
    token=$(engangstoken "$avtal")
    tp=$(starta_transfer "$avtal" "$token")
    TP_TILLSTAND=$(transfertillstand "$tp" 90 COMPLETED TERMINATED)
    for _ in $(seq 1 15); do
      post=$(senaste_kvitto)
      if [ -n "$post" ] && [ "$post" != "$fore" ]; then
        KVITTO="$post"; return 0
      fi
      sleep 2
    done
    echo "  (pushen nådde aldrig ingest – EDC-dataplanets 'IOException: closed'; gör om) ..." >&2
    sleep 20
  done
  return 1
}

# senaste_a_leverans -> sista LEVERERAD-posten för Distribution A (4c.4).
# Jämförs som IDENTITET, inte som antal: kvittologgen kapas av
# INGEST_LOG_RETENTION och kan dessutom bära poster från en tidigare
# körning. Tom sträng = ingen A-leverans finns kvar i loggen.
senaste_a_leverans() {
  curl -s --max-time 15 "${INGEST}/leveranser" \
    | jq -c '[ .deliveries[] | select(.resultat == "LEVERERAD"
                                      and .distribution == "A") ] | .[-1] // empty'
}

# GOTCHA: startas en ny transfer inom några
# sekunder efter en MISSLYCKAD, dör pushen i providerns dataplan med
# "java.io.IOException: closed" och ingest får aldrig något anrop – den
# föregående transferns failsafe-retry ligger kvar. Andrum krävs.
andrum_efter_misslyckad_transfer() { sleep 20; }

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (dataplan, connectorer, ingest, registrering)"

if vanta_url "${PROV_API}/check/health" 1; then
  ok "edc-provider var redan uppe"
else
  echo "  (startar dhi-iot + dhi-fcf + dhi-edc ...)"
  $DHI --profile dhi-fcf --profile dhi-edc up -d >/dev/null 2>&1
  if vanta_url "${PROV_API}/check/health" 90; then ok "edc-provider uppe"
  else no "edc-provider startade inte"; fi
fi
if vanta_url "${CONS_API}/check/health" 1; then
  ok "edc-consumer var redan uppe"
else
  echo "  (startar stad-dataplan + stad-edc ...)"
  $STAD --profile stad-dataplan --profile stad-edc up -d >/dev/null 2>&1
  if vanta_url "${CONS_API}/check/health" 90; then ok "edc-consumer uppe"
  else no "edc-consumer startade inte"; fi
fi
if vanta_url "${ORION}/ngsi-ld/ex/v1/version" 1; then
  ok "orion-stad (CIP) var redan uppe"
else
  echo "  (startar stad-dataplan ...)"
  $STAD --profile stad-dataplan up -d >/dev/null 2>&1
  if vanta_url "${ORION}/ngsi-ld/ex/v1/version" 90; then ok "orion-stad uppe"
  else no "orion-stad startade inte"; fi
fi
if vanta_url "${INGEST}/health" 1; then
  ok "ingest-service var redan uppe"
else
  echo "  (startar stad-ingest ...)"
  $STAD --profile stad-ingest up -d >/dev/null 2>&1
  if vanta_url "${INGEST}/health" 60; then ok "ingest-service uppe"
  else no "ingest-service startade inte"; fi
fi

# Felinjektionen AV innan vi börjar (4c.5 slår på den själv).
curl -s -o /dev/null --max-time 10 -X POST "${FCF}/felinjektion/reset"

echo "  (registrerar Distribution A och B hos providern ...)"
if $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap4c_bootstrap.log 2>&1; then
  ok "registrera-edc körde igenom"
else
  no "registrera-edc misslyckades (se /tmp/svada_ap4c_bootstrap.log)"
fi

# Ingest måste kunna nås av PROVIDERNS dataplan – dvs. ligga på dsp-public.
NAT=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
        ${SVADA_PREFIX:-svada}-ingest-service 2>/dev/null)
if echo "$NAT" | grep -q "dsp-public" && echo "$NAT" | grep -q "stad-internal"; then
  ok "ingest-service ligger på både stad-internal och dsp-public"
else
  no "ingest-service har fel nätverk: '$NAT'"
fi
# Stadens avtalsregister läser avtalen ur edc-consumers POST /v3/contractagreements/request. Observerat 2026-10-14: connectorn
# kunde starta utan den endpointen (405), och då stänger registret (OKAND) och alla leveranser nekas. Tydligt fel i stället för ett mysterium.
KOD_AVTALSAPI=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'Content-Type: application/json' \
  -d '{"@context":{"@vocab":"https://w3id.org/edc/v0.0.1/ns/"},"@type":"QuerySpec","limit":1}' \
  "http://localhost:${EDC_CONSUMER_MGMT_PORT}/management/v3/contractagreements/request" || true)
if [ "${KOD_AVTALSAPI}" = "200" ]; then
  ok "edc-consumer har avtals-API:t (POST /v3/contractagreements/request ger 200)"
else
  no "edc-consumer saknar avtals-API:t (svarade ${KOD_AVTALSAPI}): starta om connectorn (docker restart ${SVADA_PREFIX:-svada}-edc-consumer); stadens avtalsregister kan annars inte läsa avtal"
fi

hamta_katalog

# --- 4c.1 E2E för Distribution B ---------------------------------------
section "4c.1 E2E för Distribution B: förhandling -> transfer -> orion-stad"

NEG_B=$(forhandla "${EDC_ASSET_B_ID}")
AG_B=$(avtal_for "$NEG_B" 60)
if [ -n "$AG_B" ]; then
  ok "4c.1 avtal för Distribution B: $AG_B"
else
  no "4c.1 fick inget avtal för B (förhandling $NEG_B)"
fi

if [ -n "$(engangstoken "$AG_B")" ]; then
  ok "4c.1 ingest utfärdade en engångsauktorisation mot avtalet"
else
  no "4c.1 ingest vägrade utfärda auktorisation för ett giltigt avtal"
fi

kor_transfer "$AG_B"; LEV="$KVITTO"
if [ "$TP_TILLSTAND" = "COMPLETED" ]; then
  ok "4c.1 transferprocessen nådde COMPLETED"
else
  no "4c.1 transfern hamnade i '$TP_TILLSTAND'"
fi

if echo "$LEV" | jq -e '.resultat == "LEVERERAD" and .distribution == "B"
                         and .entiteter == 91' >/dev/null 2>&1; then
  ok "4c.1 ingest kvitterade 91 entiteter ur Distribution B ($(echo "$LEV" | jq -r .batchId))"
else
  no "4c.1 ingest-kvittot ser fel ut: $LEV"
fi

ENT=$(curl -s --max-time 15 "${ORION_AUTH[@]}" "${ORION}/ngsi-ld/v1/entities/${BRUNN_B}")
if echo "$ENT" | jq -e '.type == "SewerOverflowModelB"
                         and .overflowVolumeM3.value != null
                         and .inflowMeanM3S.value != null
                         and .overflowVolumeM3.unitCode == "MTQ"' >/dev/null 2>&1; then
  ok "4c.1 B-leveransen ligger på en egen entitet (SewerOverflowModelB) med brädd-attribut och unitCode"
else
  no "4c.1 brädd-attributen saknas på B-entiteten: $(echo "$ENT" | jq -c '{type,overflowVolumeM3,inflowMeanM3S}')"
fi
# B-entiteten pekar på sin brunn och bär aldrig brunnens geometri (B innehåller inget brunns-GIS).
if echo "$ENT" | jq -e '.refWeir.object == "urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526" and (has("location") | not)' >/dev/null 2>&1; then
  ok "4c.1 B-entiteten pekar på brunnen i registret (refWeir) och bär ingen geometri"
else
  no "4c.1 B-entiteten har fel refWeir eller bär geometri: $(echo "$ENT" | jq -c '{refWeir, harGeometri: has("location")}')"
fi
# Brunnsregistret får INTE ha skrivits över, och leveranser skriver inte på det.
REG=$(curl -s --max-time 15 "${ORION_AUTH[@]}" "${ORION}/ngsi-ld/v1/entities/${BRUNN}")
if echo "$REG" | jq -e '(.location.value.coordinates | length == 2) and (has("overflowVolumeM3") | not) and (has("provenance") | not)' >/dev/null 2>&1; then
  ok "4c.1 brunnsregistret är orört: geometrin kvar, inga leveransattribut"
else
  no "4c.1 en leverans har skrivit på brunnsregistret eller raderat dess grunddata: $(echo "$REG" | jq -c 'keys')"
fi
ANTAL=$(curl -s --max-time 30 "${ORION_AUTH[@]}" \
         "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000" | jq 'length')
if [ "$ANTAL" = "91" ]; then
  ok "4c.1 CIP:en innehåller fortfarande exakt 91 brunnar i registret"
else
  no "4c.1 antalet brunnar i registret är $ANTAL (förväntat 91)"
fi
ANTAL_B=$(curl -s --max-time 30 "${ORION_AUTH[@]}" \
           "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowModelB&limit=1000" | jq 'length')
[ "$ANTAL_B" = "91" ] && ok "4c.1 91 B-entiteter (en per brunn)" || no "4c.1 antalet B-entiteter är $ANTAL_B (förväntat 91)"

# --- 4c.2 Proveniens ---------------------------------------------------
section "4c.2 Proveniens: avtals-ID, dataprodukt och tidpunkt på entiteterna"

PROV=$(echo "$ENT" | jq -c '.provenance.value')
if [ "$(echo "$PROV" | jq -r '.contractAgreementId')" = "$AG_B" ]; then
  ok "4c.2 provenance.contractAgreementId = avtalet transfern gjordes under"
else
  no "4c.2 fel avtals-ID i proveniensen: $(echo "$PROV" | jq -c '.contractAgreementId')"
fi
if [ "$(echo "$PROV" | jq -r '.dataset')" = "Modellerad bräddata" ] \
   && [ "$(echo "$PROV" | jq -r '.distribution')" = "B" ]; then
  ok "4c.2 proveniensen namnger dataprodukten och distributionen (B)"
else
  no "4c.2 dataprodukt/distribution fel i proveniensen: $PROV"
fi
if echo "$PROV" | jq -e '.ingestedAt | test("^20[0-9]{2}-")' >/dev/null 2>&1 \
   && echo "$PROV" | jq -e '.batchId | test("^batch-")' >/dev/null 2>&1; then
  ok "4c.2 proveniensen bär tidpunkt (ingestedAt) och batch-ID"
else
  no "4c.2 tidpunkt/batch saknas i proveniensen: $PROV"
fi
if [ "$(echo "$PROV" | jq -r '.accessRights')" = "public" ] \
   && [ "$(echo "$PROV" | jq -r '.informationClass')" = "K0R1T1" ]; then
  ok "4c.2 proveniensen bär informationsklassningen (K0R1T1, public)"
else
  no "4c.2 informationsklassning saknas i proveniensen: $PROV"
fi

# --- 4c.3 Transfer utan giltigt avtal avvisas --------------------------
section "4c.3 Transfer utan giltig auktorisation avvisas (inget skrivs)"

FORE=$(fingeravtryck)

KOD=$(curl -s -o /tmp/svada_ap4c_svar.json -w '%{http_code}' --max-time 20 \
       -X POST "${INGEST}/ingest" -H 'content-type: application/json' \
       -d '{"dataset":"Modellerad bräddata","distribution":"B","records":[]}')
if [ "$KOD" = "401" ]; then
  ok "4c.3 push UTAN Authorization-header avvisas (HTTP $KOD)"
else
  no "4c.3 push utan auktorisation gav HTTP $KOD (förväntat 401)"
fi

KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
       -X POST "${INGEST}/ingest" -H 'Authorization: Bearer pahittad-token' \
       -H 'content-type: application/json' -d '{"dataset":"x"}')
if [ "$KOD" = "403" ]; then
  ok "4c.3 push med påhittad token avvisas (HTTP $KOD)"
else
  no "4c.3 push med påhittad token gav HTTP $KOD (förväntat 403)"
fi

KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
       -X POST "${INGEST}/auktorisation" -H 'content-type: application/json' \
       -d '{"contractAgreementId": "det-har-avtalet-finns-inte"}')
if [ "$KOD" = "403" ]; then
  ok "4c.3 ingen auktorisation utfärdas utan ett avtal hos stadens EDC (HTTP $KOD)"
else
  no "4c.3 auktorisation mot påhittat avtal gav HTTP $KOD (förväntat 403)"
fi

# Engångsprincipen: en giltig token konsumeras vid FÖRSTA användningen –
# även när nyttolasten sedan underkänns (auktorisationen prövas först).
TOKEN_ENG=$(engangstoken "$AG_B")
curl -s -o /dev/null --max-time 20 -X POST "${INGEST}/ingest" \
     -H "Authorization: Bearer ${TOKEN_ENG}" \
     -H 'content-type: application/json' -d '{"dataset":"x"}'
KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
       -X POST "${INGEST}/ingest" -H "Authorization: Bearer ${TOKEN_ENG}" \
       -H 'content-type: application/json' -d '{"dataset":"x"}')
if [ "$KOD" = "403" ]; then
  ok "4c.3 auktorisationen är ENGÅNGS – återanvändning avvisas (HTTP $KOD)"
else
  no "4c.3 förbrukad token gick att återanvända (HTTP $KOD)"
fi

if [ "$(fingeravtryck)" = "$FORE" ]; then
  ok "4c.3 inget skrevs till orion-stad av de avvisade försöken"
else
  no "4c.3 CIP:en ändrades trots avvisade försök ($FORE -> $(fingeravtryck))"
fi

# --- 4c.4 Distribution A är gate:ad hela vägen -------------------------
section "4c.4 Distribution A flödar först efter KoV-godkännande (hård regel 7)"

A_FORE=$(senaste_a_leverans)
NEG_A=$(forhandla "${EDC_ASSET_A_ID}")
echo "  (A-förhandling $NEG_A – väntar in gaten) ..."
sleep 20
AG_A=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" "${CONS_MGMT}/v3/contractnegotiations/${NEG_A}" \
        | jq -r '.contractAgreementId // empty')
if [ -z "$AG_A" ]; then
  ok "4c.4 LED 1: utan KoV-beslut finns inget A-avtal – transfern kan inte ens startas"
else
  no "4c.4 A fick ett avtal utan KoV-beslut ($AG_A) – gaten läcker!"
fi
# Utan avtal finns ingen auktorisation, och utan auktorisation ingen ingest.
KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
       -X POST "${INGEST}/auktorisation" -H 'content-type: application/json' \
       -d "{\"contractAgreementId\": \"${NEG_A}\"}")
if [ "$KOD" = "403" ]; then
  ok "4c.4 LED 1: ingest vägrar auktorisera A-förhandlingen (HTTP $KOD)"
else
  no "4c.4 ingest auktoriserade A utan avtal (HTTP $KOD)"
fi
A_NU=$(senaste_a_leverans)
if [ -z "$A_NU" ] || [ "$A_NU" = "$A_FORE" ]; then
  ok "4c.4 LED 1: ingen ny A-leverans har landat i staden"
else
  no "4c.4 A-data landade UTAN KoV-godkännande"
fi

PROV_ID=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" "${PROV_MGMT}/kov/forhandlingar" \
           | jq -r --arg c "$NEG_A" '.[] | select(.correlationId == $c) | .id')
# Verifierbar identitet: gaten kräver numera ett verifierat SvadaRoleCredential
# (Authorization: Bearer), inte bara management-nyckeln – se
# KovIdentitetsverifiering.java och tests/lib.sh:s hamta_kov_token().
KOV_TOKEN=$(hamta_kov_token)
curl -s -o /dev/null --max-time 20 -X POST \
  -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
  -H "Authorization: Bearer ${KOV_TOKEN}" \
  "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann"
AG_A=$(avtal_for "$NEG_A" 60)
if [ -n "$AG_A" ]; then
  ok "4c.4 LED 2: efter KoV-godkännandet finns ett A-avtal ($AG_A)"
else
  no "4c.4 inget A-avtal ens efter godkännande"
fi

kor_transfer "$AG_A"; KVITTO_A="$KVITTO"
if [ "$TP_TILLSTAND" = "COMPLETED" ] \
   && echo "$KVITTO_A" | jq -e '.resultat == "LEVERERAD" and .distribution == "A"' >/dev/null 2>&1; then
  ok "4c.4 LED 2: A-transfern nådde COMPLETED"
else
  no "4c.4 A-transfern hamnade i '$TP_TILLSTAND' (kvitto: $KVITTO_A)"
fi
PROV_A=$(curl -s --max-time 15 "${ORION_AUTH[@]}" "${ORION}/ngsi-ld/v1/entities/${BRUNN_A}" \
          | jq -c '.provenance.value')
PROV_B_EFTER_A=$(curl -s --max-time 15 "${ORION_AUTH[@]}" "${ORION}/ngsi-ld/v1/entities/${BRUNN_B}" \
          | jq -c '.provenance.value')
if [ "$(echo "$PROV_A" | jq -r '.distribution')" = "A" ] \
   && [ "$(echo "$PROV_A" | jq -r '.contractAgreementId')" = "$AG_A" ] \
   && [ "$(echo "$PROV_A" | jq -r '.informationClass')" = "K1R1T1" ]; then
  ok "4c.4 LED 2: A-data ligger på en egen entitet (ModelA) med A-avtalets proveniens (K1R1T1)"
else
  no "4c.4 A-datats proveniens ser fel ut: $PROV_A"
fi
# Kärnan i uppdelningen: A:s leverans lämnar B:s entitet orörd.
if [ "$(echo "$PROV_B_EFTER_A" | jq -r '.distribution')" = "B" ] \
   && [ "$(echo "$PROV_B_EFTER_A" | jq -r '.contractAgreementId')" = "$AG_B" ]; then
  ok "4c.4 LED 2: efter A-leveransen bär B-entiteten fortfarande B:s proveniens (A skriver inte över B)"
else
  no "4c.4 A-leveransen ändrade B-entiteten: $PROV_B_EFTER_A"
fi

# --- 4c.5 Felinjektionen fångas av valideringen ------------------------
section "4c.5 Felinjektion fångas av ingest-valideringen"

FORE=$(fingeravtryck)

# a) AVTALSBROTT: brunns-GIS tillbaka i Distribution B (testfall 3.7).
curl -s -o /dev/null --max-time 15 -X POST "${FCF}/felinjektion" \
  -H 'content-type: application/json' -d '{"gis_i_b": true}'
kor_transfer "$AG_B"; LEV="$KVITTO"
S="$TP_TILLSTAND"
if echo "$LEV" | jq -e '.orsak == "brunns-gis-i-distribution-b"' >/dev/null 2>&1; then
  ok "4c.5 avtalsbrottet (brunns-GIS i B) avvisades: $(echo "$LEV" | jq -r '.exempel[0]')"
else
  no "4c.5 avtalsbrottet fångades inte: $(senaste_leverans)"
fi
if [ "$S" = "TERMINATED" ]; then
  ok "4c.5 avvisningen slog igenom till EDC: transfern blev TERMINATED"
else
  no "4c.5 transfern blev '$S' trots att ingest avvisade leveransen"
fi
andrum_efter_misslyckad_transfer

# b) Schemadrift + saknade parametrar (testfall 3.6).
curl -s -o /dev/null --max-time 15 -X POST "${FCF}/felinjektion" \
  -H 'content-type: application/json' \
  -d '{"gis_i_b": false, "schemadrift": true, "saknade_parametrar": true}'
kor_transfer "$AG_B"; LEV="$KVITTO"
if echo "$LEV" | jq -e '.orsak == "schema-avviker"' >/dev/null 2>&1; then
  ok "4c.5 schemadriften/de saknade parametrarna avvisades ($(echo "$LEV" | jq -r '.exempel[0]'))"
else
  no "4c.5 schemafelet fångades inte: $(senaste_leverans)"
fi

curl -s -o /dev/null --max-time 15 -X POST "${FCF}/felinjektion/reset"
andrum_efter_misslyckad_transfer

if [ "$(fingeravtryck)" = "$FORE" ]; then
  ok "4c.5 orion-stad är opåverkat av de felinjicerade leveranserna"
else
  no "4c.5 felaktig data landade i CIP:en ($FORE -> $(fingeravtryck))"
fi

# --- 4c.6 Tidsserier ackumuleras --------------------------------------
section "4c.6 Två batchar ger tidsseriehistorik i Mintaka"

curl -s -o /dev/null --max-time 30 -X POST "${FCF}/batches/run"
kor_transfer "$AG_B"; LEV="$KVITTO"
if [ "$TP_TILLSTAND" = "COMPLETED" ] \
   && echo "$LEV" | jq -e '.resultat == "LEVERERAD"' >/dev/null 2>&1; then
  ok "4c.6 en andra batch levererades e2e ($(echo "$LEV" | jq -r .batchId))"
else
  no "4c.6 den andra batchens transfer hamnade i '$TP_TILLSTAND' (kvitto: $LEV)"
fi
sleep 5
TIDSSTEG=$(curl -s --max-time 30 \
  "${MINTAKA}/temporal/entities/${BRUNN_B}?attrs=overflowVolumeM3&timerel=after&timeAt=2020-01-01T00:00:00Z" \
  | jq '[ .overflowVolumeM3[]?.observedAt ] | unique | length')
if [ "${TIDSSTEG:-0}" -ge 2 ]; then
  ok "4c.6 Mintaka har $TIDSSTEG distinkta tidssteg för brunnens bräddvolym"
else
  no "4c.6 Mintaka har bara ${TIDSSTEG:-0} tidssteg (förväntat >= 2)"
fi

# --- Röda trådarna -----------------------------------------------------
section "4c.x Röd tråd: dataprodukten når staden ENBART via kontraktet"

NAT=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
        ${SVADA_PREFIX:-svada}-fcf-sim 2>/dev/null)
if echo "$NAT" | grep -q "dsp-public"; then
  no "4c.x fcf-sim ligger på dsp-public – data hade kunnat hämtas utan kontrakt"
else
  ok "4c.x fcf-sim ligger fortfarande bara på dhi-internal (hård regel 8)"
fi
check "4c.x ingest utfärdar aldrig auktorisation utan avtalsuppslag i EDC" \
  grep -q "contractagreements" services/ingest-service/auktorisation.py
check "4c.x ingest kontrollerar att B saknar brunns-GIS" \
  grep -q "BRUNNS_GIS_FALT" services/ingest-service/validering.py

# --- 4c.7 Regression ---------------------------------------------------
section "4c.7 Regression"
ok "4c.7 hanteras av tests/verify_all.sh (kör ap0–ap4c i ordning)"

finish "verify_ap4c"
