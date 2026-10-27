#!/usr/bin/env bash
# =====================================================================
# verify_ap1.sh – Stadens dataplan (CIP)
# Prövar testfallen 1.1–1.8.
# =====================================================================
# Skriptet är självständigt (startar stacken vid behov och väntar på
# health) och idempotent (kan köras om hur många gånger som helst).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Stadens dataplan (CIP) ####"

# Ladda portkartan/taggarna ur .env (enda källan, hård regel 5).
set -a; . ./.env; set +a

ORION="http://localhost:${ORION_STAD_PORT}"
MINTAKA="http://localhost:${MINTAKA_PORT}"
# ÅTGÄRD G22: :2026 är numera stad-gateway, inte orion-stad rakt ut. All
# läsning och skrivning av CIP:en kräver token; bara liveness är öppen.
# Verifieringen är stadens egen komponent och använder drifttoken.
ORION_AUTH=(-H "Authorization: Bearer ${STAD_GATEWAY_DRIFT_TOKEN}")
COMPOSE="docker compose -f compose.stad.yml"
KROK_ID="urn:ngsi-ld:SewerOverflowWeir:SSO1_01-4526"
# Attribut som bara verifieringen skriver – används för temporaltestet 1.5.
TEST_ATTR="verifieringsTestvarde"

# --- Förutsättning: delat nät + stacken uppe (verifiering.md §1.4) ------
docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

antal_brunnar() {
  curl -s --max-time 15 "${ORION_AUTH[@]}" \
    "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000" \
    | jq 'if type=="array" then length else -1 end' 2>/dev/null || echo -1
}

vanta_orion() {
  for _ in $(seq 1 "${1:-90}"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
        "${ORION}/ngsi-ld/ex/v1/version")" = "200" ] && return 0
    sleep 1
  done
  return 1
}

vanta_mintaka() {
  for _ in $(seq 1 "${1:-90}"); do
    # SONDEN ÄR BEGRÄNSAD (limit=1&lastN=1), inte snällare.
    #
    # Historik: sonden hämtade först HELA historiken för ALLA 91 brunnar.
    # Den tog ~6 s när överföringen precis börjat fylla TRoE, och tidsgränsen
    # höjdes då 5 -> 20 s. Mätt 2026-07-28, med 80 411 attributrader i
    # timescale-stad, tar samma fråga **61 s** – sonden slog i taket och
    # 1.5 blev röd trots att Mintaka svarade (HTTP 206). Felet var sondens,
    # inte tjänstens.
    #
    # Sonden ska svara på EN fråga: lever Mintaka och når den TRoE? Det gör
    # limit=1&lastN=1 på 2 s och med oförändrad frågeform (kollektion +
    # typfilter). Själva påståendet i 1.5 – att ett skrivet värde återfinns
    # i historiken – är orört och läser fortfarande riktig historik.
    kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      "${MINTAKA}/temporal/entities?type=SewerOverflowWeir&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1&lastN=1")
    # 206 Partial Content är ett GILTIGT svar från NGSI-LD:s temporal-API:
    # när historiken vuxit (överföringen fyller den med dygnsbatchar) sidindelar
    # Mintaka svaret. Testet skärptes alltså inte – det var för snävt.
    { [ "$kod" = "200" ] || [ "$kod" = "206" ]; } && return 0
    sleep 1
  done
  return 1
}

section "Förutsättningar (startar stacken vid behov)"
if vanta_orion 3 && [ "$(antal_brunnar)" = "91" ]; then
  ok "stacken var redan uppe med laddade brunnar"
else
  echo "  (startar profil stad-dataplan ...)"
  $COMPOSE --profile stad-dataplan up -d >/dev/null 2>&1
  if vanta_orion 120; then ok "orion-stad uppe"; else no "orion-stad startade inte"; fi
  if [ "$(antal_brunnar)" != "91" ]; then
    echo "  (kör engångsjobbet ladda-brunnar ...)"
    $COMPOSE --profile laddning run --rm ladda-brunnar >/dev/null 2>&1 \
      && ok "brunnar laddade" || no "laddningsjobbet misslyckades"
  fi
fi

# --- 1.1 Orion-LD friskt -----------------------------------------------
section "1.1 Orion-LD friskt"
kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${ORION}/ngsi-ld/ex/v1/version")
if [ "$kod" = "200" ]; then
  ok "1.1 GET :${ORION_STAD_PORT}/ngsi-ld/ex/v1/version -> HTTP 200"
else
  no "1.1 version-endpointen gav HTTP $kod (förväntat 200)"
fi

# --- 1.2 91 brunnar ----------------------------------------------------
section "1.2 Alla 91 bräddbrunnar finns som SewerOverflowWeir"
n=$(antal_brunnar)
if [ "$n" = "91" ]; then
  ok "1.2 type=SewerOverflowWeir -> $n entiteter"
else
  no "1.2 fick $n entiteter (förväntat 91)"
fi

# --- 1.3 Krokängsparken rätt placerad ----------------------------------
section "1.3 Krokängsparken (SSO1_01-4526) rätt placerad"
# Hämtas via weirId-mönstret 4526 – inte via hårdkodad ordning eller id.
# GOTCHA: Orion-LD 1.6.0 vill ha regexpen OCITERAD efter ~= ("after match
# operator must come a RegExp"); q=weirId~="4526" ger HTTP 400.
krok=$(curl -s --max-time 15 "${ORION_AUTH[@]}" -G "${ORION}/ngsi-ld/v1/entities" \
  --data-urlencode "type=SewerOverflowWeir" \
  --data-urlencode "q=weirId~=.*4526.*" \
  --data-urlencode "limit=10")
koord=$(echo "$krok" | jq -r '.[0].location.value.coordinates | @tsv' 2>/dev/null)
lon=$(echo "$koord" | cut -f1); lat=$(echo "$koord" | cut -f2)
serie=$(echo "$krok" | jq -r '.[0].seriesRef.value // "saknas"' 2>/dev/null)
if [ -n "${lon:-}" ] && [ "$lon" != "null" ] && \
   python3 -c "import sys; sys.exit(0 if abs($lon-11.9918)<=0.01 and abs($lat-57.6943)<=0.01 else 1)" 2>/dev/null; then
  ok "1.3 koordinater [$lon, $lat] inom ±0.01 av [11.9918, 57.6943] (seriesRef=$serie)"
else
  no "1.3 fel/saknade koordinater: [${lon:-?}, ${lat:-?}]"
fi
# Delkontroll: namnet ska vara korrekt UTF-8 (inte \uXXXX-escaper).
namn=$(curl -s --max-time 10 "${ORION_AUTH[@]}" \
  "${ORION}/ngsi-ld/v1/entities/${KROK_ID}" | jq -r '.name.value')
if [ "$namn" = "Krokängsparken" ]; then
  ok "1.3 namnet lagrat som korrekt UTF-8: $namn"
else
  no "1.3 namnet är '$namn' (förväntat Krokängsparken)"
fi

# --- 1.4 Ingen brunn på nollön -----------------------------------------
section "1.4 Ingen brunn på nollön [0,0]"
nollor=$(curl -s --max-time 15 "${ORION_AUTH[@]}" \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000" \
  | jq '[.[] | select((.location.value.coordinates[0]|fabs) < 0.0001
                  and (.location.value.coordinates[1]|fabs) < 0.0001)] | length')
if [ "$nollor" = "0" ]; then
  ok "1.4 0 entiteter med koordinater [0,0]"
else
  no "1.4 $nollor entiteter hamnade på nollön"
fi
# Delkontroll: alla brunnar ska ligga inom Göteborgs bounding box.
utanfor=$(curl -s --max-time 15 "${ORION_AUTH[@]}" \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000" \
  | jq '[.[] | .location.value.coordinates
         | select(.[0] < 11.6 or .[0] > 12.3 or .[1] < 57.5 or .[1] > 58.0)] | length')
if [ "$utanfor" = "0" ]; then
  ok "1.4 alla 91 brunnar ligger inom Göteborgs bounding box"
else
  no "1.4 $utanfor brunnar hamnade utanför Göteborg"
fi

# --- 1.5 Temporal fungerar (Mintaka) -----------------------------------
section "1.5 Temporal historik via Mintaka"
if vanta_mintaka 90; then
  ok "1.5 mintaka svarar på :${MINTAKA_PORT}/temporal/entities"
else
  no "1.5 mintaka svarar inte"
fi
# Skriv ett testvärde med observedAt och läs tillbaka det ur historiken.
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
VARDE=$(( RANDOM % 9000 + 1000 ))
kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
  "${ORION_AUTH[@]}" -X POST "${ORION}/ngsi-ld/v1/entities/${KROK_ID}/attrs" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d "{\"${TEST_ATTR}\":{\"type\":\"Property\",\"value\":${VARDE},\"observedAt\":\"${TS}\"}}")
if [ "$kod" = "204" ] || [ "$kod" = "207" ]; then
  ok "1.5 testvärde $VARDE skrivet till orion-stad (HTTP $kod)"
else
  no "1.5 kunde inte skriva testvärde (HTTP $kod)"
fi
traff=""
for _ in $(seq 1 20); do
  traff=$(curl -s --max-time 15 \
    "${MINTAKA}/temporal/entities/${KROK_ID}?timerel=after&timeAt=2020-01-01T00:00:00Z&attrs=${TEST_ATTR}" \
    | jq --argjson v "$VARDE" '[.. | objects | select(.value? == $v)] | length' 2>/dev/null)
  [ "${traff:-0}" != "0" ] && break
  sleep 1
done
if [ "${traff:-0}" != "0" ]; then
  ok "1.5 värdet $VARDE återfinns i Mintakas historik för Krokängsparken"
else
  no "1.5 värdet $VARDE saknas i Mintakas historik"
fi
# Delkontroll: TRoE-lagret har historik för alla 91 brunnarna.
ents=$(docker exec ${SVADA_PREFIX:-svada}-timescale-stad psql -U "${TROE_DB_USER}" -d "${TROE_DB_NAME}" \
  -tAc "select count(distinct id) from entities where type like '%SewerOverflowWeir'" 2>/dev/null | tr -d ' \r')
if [ "${ents:-0}" -ge 91 ] 2>/dev/null; then
  ok "1.5 TRoE (timescale-stad) har historik för $ents entiteter"
else
  no "1.5 TRoE har historik för endast ${ents:-0} entiteter"
fi

# --- 1.6 Persistens över omstart ---------------------------------------
section "1.6 Persistens efter omstart av orion-stad + mongo-stad"
$COMPOSE --profile stad-dataplan restart orion-stad mongo-stad >/dev/null 2>&1
if vanta_orion 120; then
  n2=$(antal_brunnar)
  if [ "$n2" = "91" ]; then
    ok "1.6 fortfarande $n2 brunnar efter restart"
  else
    no "1.6 $n2 brunnar efter restart (förväntat 91)"
  fi
else
  no "1.6 orion-stad kom inte upp efter restart"
fi

# --- 1.7 Resurstak enligt resursstrategin (hård regel 3) ---------------------------
section "1.7 Resurstak satta (resursstrategin)"
args=$(docker inspect ${SVADA_PREFIX:-svada}-mongo-stad --format '{{json .Args}}' 2>/dev/null)
if echo "$args" | grep -q -- "--wiredTigerCacheSizeGB" && \
   echo "$args" | grep -q "${MONGO_WT_CACHE_GB}"; then
  ok "1.7 mongo-stad kör med --wiredTigerCacheSizeGB ${MONGO_WT_CACHE_GB}"
else
  no "1.7 mongo-stads cache-tak saknas (args: $args)"
fi
for c in ${SVADA_PREFIX:-svada}-orion-stad ${SVADA_PREFIX:-svada}-mongo-stad ${SVADA_PREFIX:-svada}-mintaka ${SVADA_PREFIX:-svada}-timescale-stad; do
  mem=$(docker inspect "$c" --format '{{.HostConfig.Memory}}' 2>/dev/null)
  if [ "${mem:-0}" -gt 0 ] 2>/dev/null; then
    ok "1.7 mem_limit satt på $c ($((mem/1024/1024)) MiB)"
  else
    no "1.7 mem_limit saknas på $c"
  fi
done
xmx=$(docker inspect ${SVADA_PREFIX:-svada}-mintaka --format '{{json .Config.Env}}' 2>/dev/null)
if echo "$xmx" | grep -q 'Xmx'; then
  ok "1.7 JVM-heaptak satt för mintaka (JAVA_TOOL_OPTIONS)"
else
  no "1.7 JVM-heaptak saknas för mintaka"
fi
# Inga rörliga taggar smugit in (hård regel 4, regression mot 0.6).
if grep -Eq '^[A-Z_]+_IMAGE=.*:latest' .env; then
  no "1.7 rörlig tagg i .env"
else
  ok "1.7 alla images är låsta till fasta taggar"
fi

# --- 1.8 Åtkomstkontroll framför CIP:en (åtgärd av gapanalysens G22) ----
# Invarianten om suveränitet gäller inte bara
# överlämningen från DHI utan också stadens egen utlämning. Distribution A
# är non-public och bär brunnarnas fulla GIS – märkningen ska vara
# VERKSTÄLLD, inte bara skriven i katalogen.
section "1.8 Åtkomstkontroll framför CIP:en (G22)"

# 1.8.1 orion-stad får inte vara nåbar förbi gatewayen.
publ=$(docker inspect ${SVADA_PREFIX:-svada}-orion-stad \
  --format '{{json .NetworkSettings.Ports}}' 2>/dev/null)
if echo "$publ" | grep -q '"HostPort"'; then
  no "1.8 orion-stad publicerar en värdport förbi gatewayen: $publ"
else
  ok "1.8 orion-stad publicerar INGEN värdport – gatewayen är enda vägen in"
fi
natverk=$(docker inspect ${SVADA_PREFIX:-svada}-orion-stad \
  --format '{{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{end}}' 2>/dev/null)
if echo "$natverk" | grep -q 'dsp-public'; then
  no "1.8 orion-stad ligger kvar på dsp-public ($natverk)"
else
  ok "1.8 orion-stad ligger bara på stadens interna nät ($natverk)"
fi

# 1.8.2 Liveness är öppen (annars kan inget kontrollrum se att CIP:en lever).
kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  "${ORION}/ngsi-ld/ex/v1/version")
if [ "$kod" = "200" ]; then
  ok "1.8 liveness (/ngsi-ld/ex/v1/version) öppen utan token -> HTTP $kod"
else
  no "1.8 liveness gav HTTP $kod (förväntat 200)"
fi

# 1.8.3 UTAN token: nekas, och svaret får inte innehålla en enda koordinat.
utan=$(curl -s -w '\n%{http_code}' --max-time 15 -H 'Accept: application/json' \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000")
utan_kod=$(echo "$utan" | tail -n1)
utan_kropp=$(echo "$utan" | sed '$d')
if [ "$utan_kod" = "403" ]; then
  ok "1.8 läsning UTAN token -> HTTP 403"
else
  no "1.8 läsning utan token gav HTTP $utan_kod (förväntat 403)"
fi
lackage=0
for spar in "coordinates" "location" "GeoProperty" "sourceSrs"; do
  if grep -qi "$spar" <<<"$utan_kropp"; then
    no "1.8 avslagssvaret läcker '$spar'"; lackage=1
  fi
done
[ "$lackage" = "0" ] && ok "1.8 avslagssvaret innehåller ingen GIS (0 träffar på coordinates/location/GeoProperty/sourceSrs)"
# Avslaget ska vara begripligt – annars är det ett protokollfel, inte ett nej.
if grep -q "Kretslopp och Vatten" <<<"$utan_kropp" \
   && grep -q "NON_PUBLIC" <<<"$utan_kropp"; then
  ok "1.8 avslaget namnger Data Rights Holder och accessRights"
else
  no "1.8 avslaget saknar motivering (KoV / NON_PUBLIC)"
fi

# 1.8.4 En WEBBLÄSARE ska landa på en läsbar sida, inte ett protokollfel.
# Samma princip som G9-åtgärden: en accessURL ska gå att följa.
html=$(curl -s -w '\n%{http_code}' --max-time 15 \
  -H 'Accept: text/html,application/xhtml+xml' \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir")
html_kod=$(echo "$html" | tail -n1); html_kropp=$(echo "$html" | sed '$d')
if [ "$html_kod" = "403" ] && grep -qi '<!doctype html' <<<"$html_kropp"; then
  ok "1.8 webbläsarens Accept-huvud ger en läsbar HTML-sida (HTTP 403)"
else
  no "1.8 webbläsaren fick HTTP $html_kod utan HTML-sida"
fi
if grep -qi 'coordinates' <<<"$html_kropp"; then
  no "1.8 HTML-avslaget läcker koordinater"
else
  ok "1.8 HTML-avslaget innehåller inga koordinater"
fi

# 1.8.5 Fel token nekas lika hårt som ingen token (ingen bakväg).
kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  -H 'Authorization: Bearer inte-en-giltig-token' \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1")
if [ "$kod" = "403" ]; then
  ok "1.8 okänd token -> HTTP 403"
else
  no "1.8 okänd token gav HTTP $kod (förväntat 403)"
fi

# 1.8.6 SKRIVNING utan token avvisas – gaten skyddar båda riktningarna.
kod=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  -X POST "${ORION}/ngsi-ld/v1/entities/${KROK_ID}/attrs" \
  -H 'Content-Type: application/json' \
  -d '{"g22Skrivforsok":{"type":"Property","value":1}}')
if [ "$kod" = "403" ]; then
  ok "1.8 skrivning UTAN token -> HTTP 403"
else
  no "1.8 skrivning utan token gav HTTP $kod (förväntat 403)"
fi
skrivet=$(curl -s --max-time 10 "${ORION_AUTH[@]}" \
  "${ORION}/ngsi-ld/v1/entities/${KROK_ID}" | jq -r '.g22Skrivforsok // "saknas"')
if [ "$skrivet" = "saknas" ]; then
  ok "1.8 inget skrevs till CIP:en av det nekade försöket"
else
  no "1.8 det nekade skrivförsöket landade ändå: $skrivet"
fi

# 1.8.7 MED token: full åtkomst, inklusive den GIS som är hela poängen.
med=$(curl -s --max-time 20 "${ORION_AUTH[@]}" \
  "${ORION}/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000")
n_ent=$(echo "$med" | jq 'if type=="array" then length else -1 end' 2>/dev/null)
n_gis=$(echo "$med" | jq '[.[] | select(.location != null)] | length' 2>/dev/null)
if [ "$n_ent" = "91" ] && [ "$n_gis" = "91" ]; then
  ok "1.8 MED token: $n_ent entiteter, $n_gis med full GIS"
else
  no "1.8 med token fick $n_ent entiteter varav $n_gis med GIS (förväntat 91/91)"
fi

# 1.8.8 Förenklingen är markerad (samma krav som 4a.4 på EDC:s mock-IAM).
if grep -rq "MEDVETEN FÖRENKLING" services/stad-gateway/; then
  ok "1.8 mock-auktorisationen är markerad MEDVETEN FÖRENKLING (ersätts i AP8)"
else
  no "1.8 services/stad-gateway/ saknar markering av förenklingen"
fi

finish "verify_ap1"
