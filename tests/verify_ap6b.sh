#!/usr/bin/env bash
# =====================================================================
# verify_ap6b.sh – dashboarden (kontrollrummet)
# Prövar testfallen 6b.1–6b.4, 6b.6–6b.11.
# Svada-mini: sex steg, inget sensorled och inga portaler. 6b.5 prövar i stället steg 6
# (inspektionsprioriteringen) via /api/analys.
# =====================================================================
# Självständigt och idempotent: startar de profiler som behövs, och prövar
# ENBART dashboardens egna API:er – dvs. exakt det en människa ser i vyn.
#
# STÄDNING (EXIT-fällan): felinjektionen slås alltid av igen och Mintaka lämnas
# igång. Lämnas felinjektionen på blir verify_ap3.sh 3.8 röd.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Dashboarden (kontrollrummet) ####"

set -a; . ./.env; set +a
kontrollera_mal

DASH="http://localhost:${DASHBOARD_PORT}"
FCF="http://localhost:${FCF_SIM_PORT}"
DHI="docker compose -f compose.dhi.yml"
STAD="docker compose -f compose.stad.yml"
STADPROF="--profile stad-dataplan --profile stad-identitet --profile stad-edc --profile stad-ingest"
KONTROLLRUM="docker compose -f compose.kontrollrum.yml"

TMP="$(mktemp -d)"
stada() {
  curl -s -o /dev/null --max-time 10 -X POST "${FCF}/felinjektion/reset"
  # Mintaka stoppas av 6b.2 – lämna den igång.
  ${STAD} ${STADPROF} up -d mintaka >/dev/null 2>&1
  rm -rf "${TMP}"
}
trap stada EXIT

vanta_url() {   # vanta_url <url> <försök>
  for _ in $(seq 1 "${2:-60}"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$1")" = "200" ] \
      && return 0
    sleep 2
  done
  return 1
}

# jobbklart <jobb-id> <sekunder> – väntar tills jobbet inte längre "kör".
jobbklart() {
  local jid="$1" sek="${2:-120}" status
  for _ in $(seq 1 $((sek / 2))); do
    status=$(curl -s --max-time 10 "${DASH}/api/jobb/${jid}" | jq -r '.status')
    [ "${status}" != "kör" ] && { echo "${status}"; return 0; }
    sleep 2
  done
  echo "timeout"; return 1
}

# kor_atgard <åtgärd> -> jobb-id (tom sträng om API:t nekade)
kor_atgard() {
  curl -s --max-time 30 -X POST "${DASH}/api/atgard/$1" \
    -H 'content-type: application/json' -d '{}' | jq -r '.id // empty'
}

# ---------------------------------------------------------------------
section "Förutsättningar (hela kedjan + kontrollrummet)"
# ---------------------------------------------------------------------
docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

if vanta_url "http://localhost:${FCF_SIM_PORT}/health" 1 \
   && vanta_url "http://localhost:${INGEST_PORT}/health" 1; then
  ok "DHI- och stadsleden var redan uppe"
else
  echo "  startar dhi-fcf, dhi-edc, stad-dataplan, stad-edc, stad-ingest ..."
  ${DHI} --profile dhi-fcf --profile dhi-edc up -d >/dev/null 2>&1
  ${STAD} ${STADPROF} up -d >/dev/null 2>&1
  if vanta_url "http://localhost:${FCF_SIM_PORT}/health" 60 \
     && vanta_url "http://localhost:${INGEST_PORT}/health" 60; then
    ok "kedjans dataled uppe"
  else
    no "kedjans dataled startade inte"
  fi
fi

echo "  registrerar EDC-assets (idempotent; in-memory stores) ..."
${DHI} --profile edc-bootstrap run --rm registrera-edc >"${TMP}/boot.log" 2>&1 \
  && ok "registrera-edc körde igenom" || no "registrera-edc misslyckades"

if vanta_url "${DASH}/health" 1; then
  ok "dashboarden var redan uppe"
else
  echo "  startar profilen dashboard ..."
  ${KONTROLLRUM} --profile dashboard up -d >/dev/null 2>&1
  vanta_url "${DASH}/health" 60 && ok "dashboarden uppe" \
    || no "dashboarden startade inte"
fi

# ---------------------------------------------------------------------
section "6b.1 Uppe: vyn och API:t svarar"
# ---------------------------------------------------------------------
KOD=$(curl -s -o "${TMP}/index.html" -w '%{http_code}' --max-time 15 "${DASH}/")
[ "${KOD}" = "200" ] && ok "6b.1 GET / svarar 200" \
  || no "6b.1 GET / svarade ${KOD}"
if grep -q "SVADA PoC – kontrollrum" "${TMP}/index.html"; then
  ok "6b.1 sidan är kontrollrummet"
else
  no "6b.1 oväntat innehåll på startsidan"
fi
# Alla sex stegen ska vara renderade i HTML:en (inte bara i API:t).
SAKNAS=""
for n in 1 2 3 4 5 6; do
  grep -q "id=\"steg-${n}\"" "${TMP}/index.html" || SAKNAS="${SAKNAS} ${n}"
done
[ -z "${SAKNAS}" ] && ok "6b.1 alla sex stegen renderas i vyn" \
  || no "6b.1 steg saknas i vyn:${SAKNAS}"
curl -s --max-time 15 "${DASH}/health" >"${TMP}/health.json"
if [ "$(jq -r '.status' "${TMP}/health.json")" = "ok" ]; then
  ok "6b.1 /health: $(jq -r '.komponenter.uppe' "${TMP}/health.json") av \
$(jq -r '.komponenter.totalt' "${TMP}/health.json") komponenter svarar"
else
  no "6b.1 /health svarade inte ok"
fi

# ---------------------------------------------------------------------
section "6b.2 Statusvyn speglar verkligheten (stoppa -> rött -> starta -> grönt)"
# ---------------------------------------------------------------------
STATUS_FOR() {
  curl -s --max-time 15 "${DASH}/api/status" \
    | jq -r --arg k "$1" '.komponenter[] | select(.id == $k) | .status'
}
STEG_FOR() {
  curl -s --max-time 15 "${DASH}/api/status" \
    | jq -r --arg n "$1" '.steg[] | select(.nr == ($n|tonumber)) | .status'
}
if [ "$(STATUS_FOR mintaka)" = "upp" ]; then
  ok "6b.2 mintaka visas som UPP innan testet"
else
  no "6b.2 mintaka var inte upp från början"
fi
echo "  stoppar mintaka ..."
${STAD} ${STADPROF} stop mintaka >/dev/null 2>&1
NED=0
for _ in $(seq 1 20); do
  sleep 3
  [ "$(STATUS_FOR mintaka)" = "ned" ] && { NED=1; break; }
done
if [ "${NED}" = "1" ]; then
  ok "6b.2 statusvyn visar mintaka som NED efter stopp"
else
  no "6b.2 statusvyn märkte inte att mintaka stoppades"
fi
if [ "$(STEG_FOR 5)" = "delvis" ] && [ "$(STEG_FOR 6)" = "delvis" ]; then
  ok "6b.2 steg 5 och 6 visas som DELVIS (orion-stad lever, Mintaka är nere)"
else
  no "6b.2 steg 5 har status '$(STEG_FOR 5)' och steg 6 '$(STEG_FOR 6)' – förväntade delvis"
fi
echo "  startar mintaka igen ..."
${STAD} ${STADPROF} up -d mintaka >/dev/null 2>&1
UPP=0
for _ in $(seq 1 25); do
  sleep 3
  [ "$(STATUS_FOR mintaka)" = "upp" ] && { UPP=1; break; }
done
[ "${UPP}" = "1" ] && ok "6b.2 statusvyn visar mintaka som UPP igen" \
  || no "6b.2 mintaka blev aldrig grön igen"

# ---------------------------------------------------------------------
section "6b.3 KoV-knappen ändrar förhandlingens tillstånd hos PROVIDERN"
# ---------------------------------------------------------------------
JID=$(kor_atgard forhandla-a)
if [ -n "${JID}" ]; then
  ok "6b.3 dashboarden startade en A-förhandling (jobb ${JID})"
else
  no "6b.3 kunde inte starta A-förhandlingen"
fi
STATUS=$(jobbklart "${JID}" 120)
curl -s --max-time 15 "${DASH}/api/jobb/${JID}" >"${TMP}/jobb-a.json"
if jq -e '[.rader[].text] | join(" ") | test("väntar hos PROVIDERN")' \
     "${TMP}/jobb-a.json" >/dev/null; then
  ok "6b.3 jobbloggen redovisar att A stannar hos providern (hård regel 7)"
else
  no "6b.3 jobbloggen nämner inte provider-gaten"
fi
curl -s --max-time 15 "${DASH}/api/kov" >"${TMP}/kov.json"
KOV_ID=$(jq -r '.vantande[-1].id // empty' "${TMP}/kov.json")
if [ -n "${KOV_ID}" ]; then
  ok "6b.3 A-förhandlingen ligger VÄNTANDE i providerns kö (${KOV_ID})"
else
  no "6b.3 ingen väntande A-förhandling i kön (jobbstatus ${STATUS})"
fi
# Knappen ska anropa PROVIDERNS API – kontrollera adressen vyn redovisar.
if jq -r '.api' "${TMP}/kov.json" | grep -q ":${EDC_PROVIDER_MGMT_PORT}/management/kov"; then
  ok "6b.3 KoV-panelen pekar på providerns management-API (:${EDC_PROVIDER_MGMT_PORT})"
elif [ "${DEMO_VARIANT:-intern}" = "extern" ] \
     && [ "$(jq -r '.api' "${TMP}/kov.json")" = "/management/kov/forhandlingar" ]; then
  ok "6b.3 KoV-panelen pekar på providerns management-API (extern variant: sökväg utan port)"
else
  no "6b.3 KoV-panelen pekar på fel API: $(jq -r '.api' "${TMP}/kov.json")"
fi
if [ -n "${KOV_ID}" ]; then
  JID2=$(curl -s --max-time 30 -X POST "${DASH}/api/kov/${KOV_ID}/godkann" \
          | jq -r '.id // empty')
  STATUS=$(jobbklart "${JID2}" 150)
  curl -s --max-time 15 "${DASH}/api/jobb/${JID2}" >"${TMP}/jobb-kov.json"
  # Prövar det LAGRADE beslutet (kod + parameter), inte visningstexten: på svenska visas koden GODKAND som "godkänd".
  if jq -e '[.rader[] | select(.kod == "jobb.kov_beslut") | .p.beslut] | index("GODKAND") != null' \
       "${TMP}/jobb-kov.json" >/dev/null; then
    ok "6b.3 KoV-knappen registrerade GODKAND hos providern"
  else
    no "6b.3 KoV-beslutet syns inte i jobbloggen"
  fi
  if jq -e '[.rader[].text] | join(" ") | test("fick avtal")' \
       "${TMP}/jobb-kov.json" >/dev/null; then
    ok "6b.3 förhandlingen gick vidare till avtal efter godkännandet"
  else
    no "6b.3 inget avtal efter KoV-godkännandet (jobbstatus ${STATUS})"
  fi
  BESLUT=$(jq -r --arg i "${KOV_ID}" \
    '.forhandlingar[] | select(.id == $i) | .kovBeslut' \
    <(curl -s --max-time 15 "${DASH}/api/kov"))
  [ "${BESLUT}" = "GODKAND" ] \
    && ok "6b.3 providerns kö visar beslutet GODKAND" \
    || no "6b.3 providerns kö visar '${BESLUT}'"
fi

# ---------------------------------------------------------------------
section "6b.4 Villkoren för distribution A (läsning)"
# ---------------------------------------------------------------------
curl -s --max-time 60 "${DASH}/api/odrl/a" >"${TMP}/odrl.json"
if jq -e '.policy.prohibition | (index("publish") != null)
          and (index("distribute") != null)' "${TMP}/odrl.json" >/dev/null; then
  ok "6b.4 villkoren innehåller förbuden publish och distribute"
else
  no "6b.4 förbuden saknas: $(jq -c '.policy' "${TMP}/odrl.json")"
fi
if jq -e '.policy.obligation | index("kovGodkannande") != null' \
     "${TMP}/odrl.json" >/dev/null; then
  ok "6b.4 skyldigheten om KoV-godkännande redovisas"
else
  no "6b.4 obligationen om KoV saknas"
fi
if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "${DASH}/api/demo/publicera-a")" != "200" ]; then
  ok "6b.4 blockeringsdemon med portaler finns inte kvar (inga portaler i kedjan)"
else
  no "6b.4 /api/demo/publicera-a svarar fortfarande"
fi

# ---------------------------------------------------------------------
section "6b.5 Steg 6: inspektionsprioriteringen (läge B öppet, läge A kräver ett gällande avtal)"
# B-vyn säger "ingen data levererad" så länge inget har levererats: testet levererar B själv.
for ATG in kor-batch forhandla-b transfer-b transfer-a; do
  JIDP=$(kor_atgard "${ATG}")
  jobbklart "${JIDP}" 120 >/dev/null
done
# ---------------------------------------------------------------------
curl -s --max-time 60 "${DASH}/api/analys?lage=b&topp=10" >"${TMP}/analys-b.json"
# A och B ligger på varsin entitet: efter en A-leverans är B-vyn fortfarande B (inte A-värden under B:s rubrik).
if jq -e '(.rader | length) == 91 and ([.rader[].distribution] | all(. == "B")) and .ursprung.distribution == "B"' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: efter en A-leverans är B-vyns alla rader fortfarande märkta B (A skriver inte över B)"
else
  no "6b.5 B: B-vyn blandar in A efter en A-leverans: $(jq -c '{ursprung, d: ([.rader[].distribution] | unique)}' "${TMP}/analys-b.json")"
fi
if jq -e '.rader | length == 91' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: alla 91 brunnar rangordnas"
else
  no "6b.5 B: oväntat antal brunnar: $(jq -r '.rader | length' "${TMP}/analys-b.json")"
fi
if jq -e '[.rader[].volymM3] as $v | $v == ($v | sort | reverse)' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: rangordningen är fallande efter bräddvolym"
else
  no "6b.5 B: raderna är inte sorterade efter volym"
fi
if jq -e '[.rader[] | select(.inspektera)] | length >= 1 and length <= 10' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: högst 10 brunnar pekas ut för inspektion"
else
  no "6b.5 B: urvalet är fel"
fi
if jq -e '[.rader[] | has("position")] | any | not' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: ingen rad bär en position (brunns-GIS ingår inte i B)"
else
  no "6b.5 B: positioner läcker in i den öppna analysen!"
fi
if jq -e '.ursprung.avtal != null and .ursprung.batch != null and .ursprung.distribution != null' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: ursprunget (avtal, batch, distribution) redovisas"
else
  no "6b.5 B: ursprunget saknas"
fi
if jq -e '.perRecipient | length >= 1' "${TMP}/analys-b.json" >/dev/null; then
  ok "6b.5 B: bräddningen summeras per mottagande vattendrag"
else
  no "6b.5 B: ingen sammanställning per recipient"
fi
# A: 6b.3 godkände ett A-avtal, så det finns ett gällande avtal.
curl -s --max-time 60 "${DASH}/api/analys?lage=a&topp=5" >"${TMP}/analys-a.json"
if jq -e '.blockerad == null and (.rader | length) == 91 and ([.rader[] | has("position")] | all)' "${TMP}/analys-a.json" >/dev/null; then
  ok "6b.5 A: med ett gällande avtal ger analysen positioner för alla brunnar"
else
  no "6b.5 A: analysen gav inte positioner trots ett avtal: $(jq -c '.blockerad' "${TMP}/analys-a.json")"
fi
# Samma brunn i B och A sida vid sida (webinariet 2026-10, punkt 3): samma brunn, position bara i A. (Värdena kan
# komma från olika batcher om en ny batch hinner räknas mellan leveranserna, så de jämförs inte.)
curl -s --max-time 90 "${DASH}/api/analys/brunn" >"${TMP}/brunn.json"
if jq -e '.brunn as $b | .B.rad.id == $b and .A.rad.id == $b and (.B.rad | has("position") | not)
          and (.A.rad.position | length) == 2 and .B.rad.distribution == "B" and .A.rad.distribution == "A"' "${TMP}/brunn.json" >/dev/null; then
  ok "6b.5 samma brunn ($(jq -r .brunn "${TMP}/brunn.json")) i B och A: B utan position, A med position, var och en med sin distribution"
else
  no "6b.5 samma brunn i B och A stämmer inte: $(jq -c '{brunn, B: .B.rad, A: (.A.rad // .A.blockerad)}' "${TMP}/brunn.json" | head -c 400)"
fi
# Häv ALLA gällande A-avtal (tidigare tester i sviten kan ha lämnat fler än ett): A ska då
# nekas av stadens gateway, och B ska fortsätta fungera.
DHI_AVTAL=$(curl -s --max-time 15 "${DASH}/api/avtal" | jq -r '[.avtal[] | select(.distribution=="A" and .status=="GALLANDE")][].dhiAvtalId // empty')
if [ -n "${DHI_AVTAL}" ]; then
  for id in ${DHI_AVTAL}; do
    JIDH=$(curl -s --max-time 30 -X POST "${DASH}/api/kov/avtal/${id}/hav" | jq -r '.id // empty')
    jobbklart "${JIDH}" 60 >/dev/null
  done
  sleep 2
  curl -s --max-time 60 "${DASH}/api/analys?lage=a&topp=5" >"${TMP}/analys-a2.json"
  if jq -e '.blockerad.orsak == "avtal-havt"' "${TMP}/analys-a2.json" >/dev/null; then
    ok "6b.5 A: efter hävningen nekas analysen (orsak avtal-havt)"
  else
    no "6b.5 A: analysen nekades inte efter hävningen: $(jq -c '.blockerad' "${TMP}/analys-a2.json")"
  fi
  curl -s --max-time 90 "${DASH}/api/analys/brunn" >"${TMP}/brunn2.json"
  if jq -e '.A.rad == null and .A.blockerad.orsak == "avtal-havt" and .B.rad.id == .brunn and (.B.rad | has("position") | not)' "${TMP}/brunn2.json" >/dev/null; then
    ok "6b.5 samma brunn efter hävningen: A nekas (avtal-havt), B visas som förut utan position"
  else
    no "6b.5 samma brunn efter hävningen: $(jq -c '{A, B: .B.rad}' "${TMP}/brunn2.json" | head -c 400)"
  fi
  # A och B ligger på varsin entitet: en hävning av A rör inte B, som fungerar utan ny leverans.
  curl -s --max-time 60 "${DASH}/api/analys?lage=b&topp=5" >"${TMP}/analys-b2.json"
  if jq -e '.blockerad == null and (.rader | length) == 91 and ([.rader[].distribution] | all(. == "B"))' "${TMP}/analys-b2.json" >/dev/null; then
    ok "6b.5 B: efter hävningen av A fungerar B-analysen oförändrad, utan ny leverans (alla 91 rader märkta B)"
  else
    no "6b.5 B: B-analysen påverkades av hävningen av A: $(jq -c '{blockerad, n: (.rader|length)}' "${TMP}/analys-b2.json")"
  fi
else
  no "6b.5 inget gällande A-avtal att häva (6b.3 borde ha skapat ett)"
fi

# ---------------------------------------------------------------------
section "6b.6 Auditloggen: minst en händelse per led"
# ---------------------------------------------------------------------
curl -s --max-time 60 "${DASH}/api/audit" >"${TMP}/audit.json"
if [ "$(jq -r '.kallfel | length' "${TMP}/audit.json")" = "0" ]; then
  ok "6b.6 alla auditkällor svarade"
else
  no "6b.6 källfel: $(jq -c '.kallfel' "${TMP}/audit.json")"
fi
for led in 3 4; do
  ANTAL=$(jq -r --arg l "${led}" '.perLed[$l] // 0' "${TMP}/audit.json")
  if [ "${ANTAL:-0}" -ge 1 ] 2>/dev/null; then
    ok "6b.6 led ${led} har ${ANTAL} händelser"
  else
    no "6b.6 led ${led} saknar händelser"
  fi
done
for kalla in "edc-consumer" "edc-provider (KoV-gate)" "ingest-service" \
             "dashboard"; do
  if jq -e --arg k "${kalla}" '[.handelser[] | select(.kalla == $k)] | length >= 1' \
       "${TMP}/audit.json" >/dev/null; then
    ok "6b.6 källan '${kalla}' bidrar till loggen"
  else
    no "6b.6 källan '${kalla}' saknas i loggen"
  fi
done
# Kronologin: tiderna ska vara sorterade (loggen är en händelsekedja).
if jq -e '[.handelser[].tid | select(. != null)] as $t
          | $t == ($t | sort)' "${TMP}/audit.json" >/dev/null; then
  ok "6b.6 händelserna ligger i kronologisk ordning"
else
  no "6b.6 auditloggen är inte kronologisk"
fi

# ---------------------------------------------------------------------
section "6b.10 Felinjektionsreglaget och resultatvyn"
# ---------------------------------------------------------------------
curl -s --max-time 20 -X POST "${DASH}/api/felinjektion" \
  -H 'content-type: application/json' -d '{"gis_i_b": true}' >"${TMP}/fel.json"
if jq -e '.lagen.gis_i_b == true and .aktiv == true' "${TMP}/fel.json" >/dev/null; then
  ok "6b.10 reglaget slog på avtalsbrottet (brunns-GIS i Distribution B)"
else
  no "6b.10 felinjektionen gick inte att slå på via dashboarden"
fi
if curl -s --max-time 15 "${FCF}/felinjektion" | jq -e '.lagen.gis_i_b == true' >/dev/null; then
  ok "6b.10 fcf-sim bekräftar samma läge (reglaget når verkligen simulatorn)"
else
  no "6b.10 fcf-sim känner inte till det påslagna läget"
fi
JID=$(kor_atgard transfer-b)
STATUS=$(jobbklart "${JID}" 300)
curl -s --max-time 15 "${DASH}/api/jobb/${JID}" >"${TMP}/jobb-fel.json"
if jq -e '[.rader[].text] | join(" ") | test("AVVISADE leveransen")' \
     "${TMP}/jobb-fel.json" >/dev/null; then
  ok "6b.10 resultatvyn visar att ingest AVVISADE den felinjicerade leveransen"
else
  no "6b.10 avvisningen syns inte i jobbloggen (status ${STATUS})"
fi
# En avvisad leverans får inte se lyckad ut i jobblistan: jobbet bär utfallet "avvisad".
if jq -e '.utfall == "avvisad"' "${TMP}/jobb-fel.json" >/dev/null; then
  ok "6b.10 jobbet bär utfallet 'avvisad' (visas inte som en ren lyckad körning)"
else
  no "6b.10 jobbet saknar utfallet 'avvisad': $(jq -c '{status, utfall}' "${TMP}/jobb-fel.json")"
fi
if jq -e '[.rader[].text] | join(" ") | test("brunns-gis-i-distribution-b")' \
     "${TMP}/jobb-fel.json" >/dev/null; then
  ok "6b.10 orsaken är avtalsbrottet brunns-gis-i-distribution-b"
else
  no "6b.10 avvisningsorsaken redovisas inte"
fi
curl -s --max-time 20 -X POST "${DASH}/api/felinjektion/reset" >"${TMP}/fel2.json"
if jq -e '.aktiv == false' "${TMP}/fel2.json" >/dev/null; then
  ok "6b.10 felinjektionen nollställdes från dashboarden"
else
  no "6b.10 felinjektionen gick inte att nollställa"
fi

# ---------------------------------------------------------------------
section "6b.9 Resurstak, nätverksavgränsning och att inget ur kedjan lagras"
# ---------------------------------------------------------------------
GRANS=$(docker inspect ${SVADA_PREFIX:-svada}-dashboard --format '{{.HostConfig.Memory}}' 2>/dev/null)
if [ -n "${GRANS}" ] && [ "${GRANS}" != "0" ]; then
  ok "6b.9 mem_limit satt ($((GRANS / 1024 / 1024)) MiB)"
else
  no "6b.9 dashboarden saknar mem_limit"
fi
NAT=$(docker inspect ${SVADA_PREFIX:-svada}-dashboard \
  -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null)
if echo "${NAT}" | grep -qE "dhi-internal|stad-internal|dsp-public"; then
  no "6b.9 dashboarden ligger på ett org-nät: '${NAT}' – den ska bara nå värdens publicerade portar"
else
  ok "6b.9 dashboarden ligger inte på något org-nät (nät: ${NAT})"
fi
MONT=$(docker inspect ${SVADA_PREFIX:-svada}-dashboard \
  --format '{{range .Mounts}}{{.Destination}}:{{.RW}} {{end}}' 2>/dev/null)
# Enda tillåtna monteringar (användningsstatistik): Caddys åtkomstlogg SKRIVSKYDDAD och
# katalogen data/ där bara dagssummor (tal) och händelseräknaren sparas. Allt annat, eller att loggen blir skrivbar, är ett fel.
MONT_SORT="$(echo "${MONT}" | tr ' ' '\n' | sed '/^$/d' | sort | tr '\n' ' ')"
if [ "${MONT_SORT}" = "/statistik/data:true /statistik/logg:false " ]; then
  ok "6b.9 bara statistikens två monteringar: loggen skrivskyddad och data/ med dagssummor (inga data ur kedjan lagras)"
else
  no "6b.9 oväntade monteringar: '${MONT}'"
fi
# Kontrollrummet får inte hämta dataproduktens nyttolast någonstans.
# Sökningen gäller ANROPET (url("fcf", "/distributions...)) och inte ordet i
# löptext – kallor.py förklarar med flit varför funktionen inte finns.
if grep -rn 'url("fcf", *"/distributions' services/dashboard/ >/dev/null 2>&1; then
  no "6b.9 dashboardkoden hämtar dataproduktens nyttolast från fcf-sim"
else
  ok "6b.9 dashboardkoden hämtar aldrig dataproduktens nyttolast (bara /health, /batches/run, /felinjektion)"
fi
MEM=$(docker stats --no-stream --format '{{.MemUsage}}' ${SVADA_PREFIX:-svada}-dashboard 2>/dev/null)
[ -n "${MEM}" ] && ok "6b.9 minnesanvändning: ${MEM}" || no "6b.9 kunde inte mäta minnet"

# ---------------------------------------------------------------------
section "6b.7 Demodokumentationen finns och följer kedjan 1–6"
# ---------------------------------------------------------------------
# Stegnumreringen är kanonisk i docs/01-oversikt.md §1.4 och körschemat i
# docs/03-demo.md. Testets avsikt:
# det ska finnas ett dokument som går igenom hela kedjan 1–6, och demon
# ska vara tidsatt.
STEGDOK="docs/01-oversikt.md"
DEMODOK="docs/03-demo.md"
if [ -f "${STEGDOK}" ] && [ -f "${DEMODOK}" ]; then
  ok "6b.7 ${STEGDOK} och ${DEMODOK} finns"
  SAKNAS=""
  for n in 1 2 3 4 5 6; do
    grep -qE "^\|?\s*\*?\*?${n}[\.\)]|^### ${n}\.|Steg ${n}" "${STEGDOK}" \
      || SAKNAS="${SAKNAS} ${n}"
  done
  [ -z "${SAKNAS}" ] && ok "6b.7 ${STEGDOK} går igenom steg 1–6" \
    || no "6b.7 ${STEGDOK} saknar steg:${SAKNAS}"
  grep -q "15" "${DEMODOK}" && ok "6b.7 ${DEMODOK} är tidsatt (15 minuter)" \
    || no "6b.7 ${DEMODOK} saknar körschema/tidsättning"
else
  no "6b.7 ${STEGDOK} eller ${DEMODOK} saknas"
fi

# ---------------------------------------------------------------------
section "6b.11 Exempelobjekt per steg och \"Följ ett värde\""
# ---------------------------------------------------------------------
# Nivå 1 (per-steg-inspektör) och Nivå 2 (följ-tråden) får BARA visa det
# kontrollrummet redan lagligt hämtar – aldrig dataproduktens nyttolast.
FOLJ="${TMP}/folj.json"
curl -s --max-time 20 "${DASH}/api/folj" >"${FOLJ}"
if jq -e '.hopp | length >= 6' "${FOLJ}" >/dev/null 2>&1; then
  ok "6b.11 /api/folj returnerar tråden (>=6 hopp)"
else
  no "6b.11 /api/folj saknar hopp"
fi
# Modelleringssteget MÅSTE markeras som medveten lucka (ingen nyttolast).
if jq -e '.hopp[] | select(.steg==1) | .markering.typ == "lucka"' \
     "${FOLJ}" >/dev/null 2>&1; then
  ok "6b.11 modelleringssteget visar metadata, inte nyttolast (lucka-markering)"
else
  no "6b.11 modelleringssteget saknar lucka-markering (avgränsningen otydlig)"
fi
# Per-steg-inspektören svarar med innehåll för alla tio stegen.
BRUTNA=""
for n in $(seq 1 6); do
  jq -e '(.innehall // "") | length > 0' \
     <(curl -s --max-time 20 "${DASH}/api/steg/${n}/exempel") >/dev/null 2>&1 \
     || BRUTNA="${BRUTNA} ${n}"
done
[ -z "${BRUTNA}" ] && ok "6b.11 /api/steg/{1..6}/exempel ger innehåll" \
  || no "6b.11 exempel saknas för steg:${BRUTNA}"
# AVGRÄNSNING: steg 1-exemplet får inte avslöja att kontrollrummet läst
# distributionens nyttolast (fält som bara finns i /distributions/*/latest).
if curl -s --max-time 20 "${DASH}/api/steg/1/exempel" \
     | jq -e '.innehall | test("syntheticScale|overflowVolumeM3|\"records\"")' \
       >/dev/null 2>&1; then
  no "6b.11 steg 1-exemplet innehåller distributions-nyttolast (avgränsning bruten!)"
else
  ok "6b.11 steg 1-exemplet läcker ingen distributions-nyttolast"
fi

# ---------------------------------------------------------------------
section "6b.8 Regression (verify_ap0–ap4c)"
# ---------------------------------------------------------------------
for s in tests/verify_ap0.sh tests/verify_ap1.sh tests/verify_ap3.sh \
         tests/verify_ap4a.sh tests/verify_ap4b.sh tests/verify_ap4c.sh; do
  [ -f "$s" ] && ok "regressionsskriptet $s finns" || no "$s saknas"
done

finish "Dashboarden"
