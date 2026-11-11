#!/usr/bin/env bash
# =====================================================================
# verify_kedjevy.sh – den pedagogiska kedjevyn i kontrollrummet
# =====================================================================
# Prövar (1) renderingen i processen, utan stack: ingen intern text och inga
# portnummer i den externa varianten, ljust tema, båda språken, K21-prefixen
# och knapptäckningen (tests/kedjevy_rendering.py), och (2) den körande
# dashboarden: sidan på båda språken, id/data-attribut, djuplänkarnas mål,
# ODRL-villkoren live och översatta API-texter.
# Kräver profilen dashboard för del 2 (starta-demo.sh); del 1 kräver inget.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh
set -a; . ./.env; set +a
kontrollera_mal
DASH="http://localhost:${DASHBOARD_PORT}"
TMP="$(mktemp -d)"; trap 'rm -rf "${TMP}"' EXIT

echo "#### Kedjevyn ####"

section "K1 Rendering i processen (kedjevy_rendering.py)"
python3 tests/kedjevy_rendering.py 2>&1 | tee "${TMP}/rendering.log"
RC=${PIPESTATUS[0]}
FEL=$(grep -c '^  \[FEL\]' "${TMP}/rendering.log")
# Ett krasch (undantag före första raden) ger inga [FEL]-rader men exitkod ≠ 0.
if [ "${RC}" -ne 0 ]; then no "K1 renderingstestet avslutades med kod ${RC} (${FEL} [FEL]-rader)"
elif ! grep -q '\[OK\]' "${TMP}/rendering.log"; then no "K1 renderingstestet skrev inga kontroller"
elif [ "${FEL}" -eq 0 ]; then ok "K1 alla renderingskontroller gröna"
else no "K1 ${FEL} renderingskontroller röda"; fi

section "K1b Engelska: svenska meddelanden översätts (engelska_enhet.py) och det engelska API:t är rent (engelska_live.py)"
python3 tests/engelska_enhet.py 2>&1 | tee "${TMP}/eng.log"
[ "${PIPESTATUS[0]}" -eq 0 ] && ok "K1b alla kända meddelanden översätts" || no "K1b svenska meddelanden utan översättning (se ovan)"
if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${DASH}/health")" = "200" ]; then
  # Testet läser jobb och auditposter: utan något jobb (rent läge) finns inget att granska, så kör en batch först.
  if [ "$(curl -s --max-time 10 "${DASH}/api/jobb" | jq '.jobb | length')" = "0" ]; then
    JID0=$(curl -s --max-time 30 -X POST "${DASH}/api/atgard/kor-batch" -H 'content-type: application/json' -d '{}' | jq -r '.id // empty')
    for _ in $(seq 1 40); do [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${JID0}" | jq -r '.status')" != "kör" ] && break; sleep 2; done
  fi
  python3 tests/engelska_live.py 2>&1 | tee "${TMP}/engl.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] && ok "K1b det engelska API-svaret innehåller inga svenska meddelanden" || no "K1b svenska texter i det engelska API-svaret (se ovan)"
fi

# Felmeddelandet i "Följ ett värde" (ett led som inte kunde hämtas) ska vara på vyns språk.
# Felleden väljs strukturellt (fel: true), inte på engelsk text: en helt svensk feltext ska också fångas (del e, E5).
# Ett lyckat, icke-tomt svar krävs först; att ett fel FAKTISKT renderas på rätt språk prövas med framtvingat fel i
# tests/kedjevy_rendering.py (inget här kan garantera att den levande kedjan har ett trasigt led).
FOLJ=$(curl -s --max-time 30 -w '\n%{http_code}' "${DASH}/api/folj?lang=en"); FOLJKOD="${FOLJ##*$'\n'}"; FOLJ="${FOLJ%$'\n'*}"
if [ "${FOLJKOD}" != 200 ] || ! printf '%s' "${FOLJ}" | jq -e '.hopp | length > 0' >/dev/null 2>&1; then
  no "K1b Följ ett värde: inget giltigt svar (HTTP ${FOLJKOD})"
else
  FELRADER=$(printf '%s' "${FOLJ}" | jq -r '[.hopp[] | select(.fel == true) | .innehall] | join("\n")')
  ANTALFEL=$(printf '%s' "${FOLJ}" | jq '[.hopp[] | select(.fel == true)] | length')
  if printf '%s' "${FELRADER}" | grep -Eq '[åäöÅÄÖ]|kunde inte|inga brunnar|saknas'; then
    no "K1b Följ ett värde: svenskt felmeddelande i den engelska vyn: ${FELRADER}"
  else
    ok "K1b Följ ett värde: ${ANTALFEL} felled i den engelska vyn, inget på svenska"
  fi
fi

section "K2 Den körande dashboarden"
if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${DASH}/health")" != "200" ]; then
  no "K2 dashboarden svarar inte på ${DASH}/health (starta profilen dashboard)"
else
  for sp in sv en; do
    curl -s --max-time 15 "${DASH}/?lang=${sp}" >"${TMP}/sida-${sp}.html"
    grep -q "<html lang=\"${sp}\"" "${TMP}/sida-${sp}.html" \
      && ok "K2 GET /?lang=${sp} ger <html lang=${sp}>" || no "K2 fel språk för ?lang=${sp}"
  done
  grep -q "Följ data från modellen till stadens beslut" "${TMP}/sida-sv.html" \
    && grep -q "Follow data from the model to the city" "${TMP}/sida-en.html" \
    && ok "K2 rubriken finns på båda språken" || no "K2 rubriken saknas på något språk"
  # Kakan svada-sprak minns valet
  [ "$(curl -s --max-time 10 -H 'Cookie: svada-sprak=en' "${DASH}/" | grep -c '<html lang="en"')" = "1" ] \
    && ok "K2 kakan svada-sprak=en ger engelska" || no "K2 kakan styr inte språket"
  SAKNAS=""
  for n in 1 2 3 4 5 6; do
    for attr in "id=\"steg-${n}\"" "id=\"nod-${n}\"" "data-stegstatus=\"${n}\"" "data-detaljer=\"${n}\""; do
      grep -q "${attr}" "${TMP}/sida-sv.html" || SAKNAS="${SAKNAS} ${attr}"
    done
  done
  [ -z "${SAKNAS}" ] && ok "K2 alla sex steg har panel, nod, status och detaljer" || no "K2 saknas:${SAKNAS}"
  grep -q 'id="nod-kov"' "${TMP}/sida-sv.html" && ok "K2 KoV-noden finns" || no "K2 KoV-noden saknas"
  grep -q 'data-kovbeslut="godkann"' "${TMP}/sida-sv.html" && grep -q 'data-kovbeslut="avsla"' "${TMP}/sida-sv.html" \
    && ok "K4 KoV-knapparna (godkänn/avslå) finns i steg 3" || no "K4 KoV-knapparna saknas"
  # En åtgärd per knapp: alla jobbåtgärder har en knapp i vyn
  for a in kor-batch hamta-katalog forhandla-b forhandla-a transfer-b transfer-a; do
    grep -q "data-atgard=\"${a}\"" "${TMP}/sida-sv.html" || { no "K3 knapp saknas för ${a}"; KNAPPFEL=1; }
  done
  [ "${KNAPPFEL:-0}" -eq 0 ] && ok "K3 alla åtgärder har knapp med roll (kontrollerat vid import)"

  section "K17 ODRL-villkoren live ur DSP-katalogen"
  curl -s --max-time 40 "${DASH}/api/odrl-villkor?lang=en" >"${TMP}/odrl.json"
  if jq -e '.B.regler | length >= 3' "${TMP}/odrl.json" >/dev/null 2>&1 \
     && jq -e '.A.regler | map(.[0]) | any(startswith("obligation"))' "${TMP}/odrl.json" >/dev/null 2>&1; then
    ok "K17 /api/odrl-villkor ger villkoren för B och A (A har obligation)"
    jq -e '.A.regler | map(.[1]) | any(test("only by the City"))' "${TMP}/odrl.json" >/dev/null \
      && ok "K17 klartexten följer språket (en)" || no "K17 klartexten är inte engelsk"
  else
    no "K17 /api/odrl-villkor svarade inte med villkor (kör registrera-edc?)"
  fi

  section "K2 API-texter på valt språk, utan interna hänvisningar (K10)"
  curl -s --max-time 30 "${DASH}/api/steg?lang=en" >"${TMP}/steg-en.json"
  jq -e '.steg[0].detaljer | map(.etikett) | index("Batches produced")' "${TMP}/steg-en.json" >/dev/null \
    && ok "K2 detaljetiketterna översätts (Batches produced)" || no "K2 detaljetiketterna är inte översatta"
  : >"${TMP}/apitext.txt"
  for n in 1 2 3 4 5 6; do
    for sp in sv en; do
      curl -s --max-time 40 "${DASH}/api/steg/${n}/exempel?lang=${sp}" | jq -r '.rubrik, .not // empty' >>"${TMP}/apitext.txt"
    done
  done
  curl -s --max-time 60 "${DASH}/api/folj?lang=sv" | jq -r '.invarianter[], (.hopp[] | .titel, .rubrik, (.not // empty), (.markering.text // empty))' >>"${TMP}/apitext.txt"
  if grep -Eiq 'AP[0-9]|\bG[0-9]{1,2}\b|workshop|hård regel|etapp|MANUAL|§|kallor\.py' "${TMP}/apitext.txt"; then
    no "K10 interna hänvisningar i API-texterna: $(grep -Eio 'AP[0-9]|\bG[0-9]{1,2}\b|workshop|hård regel|etapp|MANUAL|§|kallor\.py' "${TMP}/apitext.txt" | sort -u | tr '\n' ' ')"
  else
    ok "K10 inga interna hänvisningar i exempelobjektens och följ-värdets texter"
  fi
  # K10b: SJÄLVA exempelobjekten (.innehall: datat som visas under "Visa exempelobjekt", t.ex. katalogens egenskaper)
  # får inte bära interna hänvisningar. Externfiltret rensar adresser och portar men inte hänvisningar, så en text i
  # datat som säger "målarkitekturen §8.4" nådde besökaren.
  : >"${TMP}/exempelinnehall.txt"
  for n in 1 2 3 4 5 6; do
    for sp in sv en; do
      curl -s --max-time 40 "${DASH}/api/steg/${n}/exempel?lang=${sp}" | jq -r '.innehall // empty' >>"${TMP}/exempelinnehall.txt"
    done
  done
  INTERN='§|målarkitektur|hård regel|arbetspaket|etapp [0-9]|docs/|docs-archive|gapanalys|\bG[0-9]{1,2}\b[^"]{0,3}(Väsentlig|Måttlig|Låg|Kritisk)'
  if [ ! -s "${TMP}/exempelinnehall.txt" ]; then
    no "K10b exempelobjekten gick inte att hämta"
  elif grep -Eiq "${INTERN}" "${TMP}/exempelinnehall.txt"; then
    no "K10b interna hänvisningar i exempelobjektens innehåll: $(grep -Eio "${INTERN}" "${TMP}/exempelinnehall.txt" | sort -u | tr '\n' ' ')"
  else
    ok "K10b inga interna hänvisningar i exempelobjektens innehåll (katalogens egenskaper, avtal, intyg)"
  fi

  # K14: i den externa varianten får inget API-svar innehålla port eller internt
  # värdnamn, varken i felmeddelanden, loggar eller policyer (DEMO_VARIANT ur .env).
  if [ "${DEMO_VARIANT:-intern}" = "extern" ]; then
    section "K14 Inga portar i API-svaren (extern variant)"
    # Mönstret: värd:port, %3A<port>, port=N, host=', internt värdnamn, driftkommando.
    # + en URL vars värd saknar punkt (http://edc-provider/…, http://mintaka …): interna värdnamn även UTAN port (del e, E6).
    LACKA='[A-Za-z]:[0-9]{2,5}([^0-9]|$)|%3A[0-9]|port=[0-9]|host=.|host\.docker\.internal|docker compose|https?://[A-Za-z0-9-]+([/:"'"'"'[:space:]\\]|$)'
    # Skördarnas JSON innehåller katalogdata (accessURL m.m.) som aldrig får
    # ändras (hård regel 8); där prövas bara textfälten kalla, detalj och fel.
    TEXTFALT='[.. | objects | (.kalla?, .detalj?, .fel?) | strings] | join("\n")'
    k14() {  # k14 <etikett> <url> [max-tid] [jq-filter för vilka delar som prövas]
      local KOD SVAR
      SVAR=$(curl -s --max-time "${3:-90}" -w '\n%{http_code}' "$2"); KOD="${SVAR##*$'\n'}"; SVAR="${SVAR%$'\n'*}"
      # Ett tomt svar, en timeout eller ett 500 får aldrig räknas som rent.
      # Bara ett lyckat svar med innehåll kan bevisa frånvaro av läckor (del e, E5): 404/409/502 och {} eller [] räknades
      # tidigare som rena. I en frisk stack svarar varje rutt nedan 200.
      if [ "${KOD}" != "200" ]; then no "K14 $1: statuskod '${KOD}', väntade 200 (ett felsvar bevisar inget)"; return; fi
      if ! printf '%s' "${SVAR}" | jq -e '(type == "object" or type == "array") and length > 0' >/dev/null 2>&1; then
        no "K14 $1: svaret är inte ett icke-tomt JSON-objekt eller en lista"; return
      fi
      [ -n "${4:-}" ] && SVAR=$(printf '%s' "${SVAR}" | jq -r "$4")
      # De publika ingångarnas egna adresser (lokalt med Caddys port :38080) är besökarens väg in och ska stå kvar
      # (rensa.utan_portar skyddar dem). Bara exakt de adresserna undantas; en annan port eller ett annat värdnamn räknas.
      for PUB in "${PUBLIK_URL_KONTROLLRUM:-}" "${PUBLIK_URL_BRUNNAR:-}" "${PUBLIK_URL_TIDSSERIE:-}" "${PUBLIK_URL_CIP:-}"; do
        [ -n "${PUB}" ] && SVAR="${SVAR//${PUB}/PUBLIK_INGANG}"
      done
      if printf '%s' "${SVAR}" | grep -Eq "${LACKA}"; then
        no "K14 $1: port, värdnamn eller driftkommando i svaret: $(printf '%s' "${SVAR}" | grep -Eo "[A-Za-z0-9.-]+:[0-9]{2,5}|%3A[0-9]+|port=[0-9]+|host=.[^,]*|host\.docker\.internal" | sort -u | head -3 | tr '\n' ' ')"
      else
        ok "K14 $1: inga portar eller interna värdnamn"
      fi
    }
    for vag in /health /api/status /api/jobb /api/audit /api/kov /api/avtal /api/analys /api/analys?lage=a /api/svada/status /api/svada/prov /api/odrl/a /api/steg/2/exempel /api/steg/3/exempel /api/folj /api/steg/5/ursprung /api/odrl-villkor; do
      for sp in sv en; do                      # båda språken: en läcka bara på engelska ska också fångas (E6)
        case "${vag}" in *\?*) URL="${DASH}${vag}&lang=${sp}" ;; *) URL="${DASH}${vag}?lang=${sp}" ;; esac
        k14 "kontrollrummet ${vag} (${sp})" "${URL}" 200
      done
    done
    # Dokumentationssidorna finns inte i den externa varianten.
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${DASH}/openapi.json")" = "404" ] \
      && ok "K14 /openapi.json finns inte externt" || no "K14 /openapi.json svarar i den externa varianten"
    # Avtalssidan (HTML): ODRL-ögonblicksbilden bär stadens DID – ingen port får synas.
    AVTAL_ID=$(curl -s --max-time 20 "${DASH}/api/avtal" | jq -r '.avtal[0].id // empty')
    if [ -n "${AVTAL_ID}" ]; then
      SIDA=$(curl -s --max-time 20 "${DASH}/avtal/${AVTAL_ID}")
      if printf '%s' "${SIDA}" | grep -Eq "${LACKA}"; then
        no "K14 avtalssidan: port eller internt värdnamn i sidan"
      else
        ok "K14 avtalssidan: inga portar eller interna värdnamn"
      fi
    else
      echo "  [HOPPAR ÖVER] K14 avtalssidan (inget avtal finns än)"
    fi
    # Sidans egen text (inte bara API-svaren): inga containernamn, ingen internt värdnamn i did:web och ingen API-lista i sidfoten.
    INTERNT='fcf-sim([^u]|$)|orion-stad|stad-gateway|edc-consumer|edc-provider|ingest-service|identity-hub|host\.docker\.internal|did:web:[a-z-]*(hub|gateway)'
    for sp in sv en; do
      # Det besökaren läser: sidan utan skriptet och utan data-komponent (nyckeln skriptet matchar mot statussvaret).
      SIDAN=$(curl -s --max-time 30 "${DASH}/?lang=${sp}" | perl -0pe 's/<script.*?<\/script>//gs; s/data-komponent="[^"]*"//g')
      TRAFF=$(printf '%s' "${SIDAN}" | grep -Eo "${INTERNT}" | sort -u | tr '\n' ' ')
      [ -z "${TRAFF}" ] && ok "K14 sidan (${sp}): inga containernamn eller interna did:web-värdnamn" \
                        || no "K14 sidan (${sp}): interna namn i sidans text: ${TRAFF}"
      printf '%s' "${SIDAN}" | grep -q 'href="/api/status"' \
        && no "K14 sidan (${sp}): sidfoten listar API-sökvägar" || ok "K14 sidan (${sp}): sidfoten listar inga API-sökvägar"
    done
    if [ -n "${AVTAL_ID}" ] && curl -s --max-time 20 "${DASH}/avtal/${AVTAL_ID}" | grep -Eq "${INTERNT}"; then
      no "K14 avtalssidan: containernamn eller internt did:web-värdnamn i sidan"
    fi
  fi
fi

section "K15 Auditloggens KoV-beslut bär beslutstiden, inte förhandlingens starttid"
# Förhandla A, vänta, låt KoV godkänna: beslutet ska vara minst 3 s efter förhandlingens start i loggen.
kor_jobb() {
  local jid; jid=$(curl -s --max-time 30 -X POST "${DASH}/api/atgard/$1" -H 'content-type: application/json' -d '{}' | jq -r '.id // empty')
  for _ in $(seq 1 60); do
    [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${jid}" | jq -r '.status')" != "kör" ] && break
    sleep 2
  done
}
FORE=$(curl -s --max-time 15 "${DASH}/api/kov" | jq -c '[.forhandlingar[] | select(.kovBeslut=="VANTANDE") | .id]')
kor_jobb forhandla-a
sleep 5
# Kön har ingen ordning att lita på: beslutet gäller den förhandling som tillkom nu.
KID=$(curl -s --max-time 15 "${DASH}/api/kov" | jq -r --argjson fore "${FORE}" '[.forhandlingar[] | select(.kovBeslut=="VANTANDE" and (.id as $i | $fore | index($i) | not))] | first | .id // empty')
if [ -n "${KID}" ]; then
  JIDK=$(curl -s --max-time 30 -X POST "${DASH}/api/kov/${KID}/godkann" | jq -r '.id // empty')
  for _ in $(seq 1 60); do
    [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${JIDK}" | jq -r '.status')" != "kör" ] && break
    sleep 2
  done
  curl -s --max-time 30 "${DASH}/api/audit?lang=en" >"${TMP}/audit-k15.json"
  if jq -e --arg id "${KID}" '
      ([.handelser[] | select(.detaljer.providerForhandling == $id and (.kod | startswith("audit.kov_godkand")))] | last) as $b
      | ([.handelser[] | select(.kod == "audit.forhandling" and .detaljer.forhandlingId == $b.detaljer.consumerForhandling)] | last) as $f
      | ($b.tid | fromdateiso8601) - ($f.tid | fromdateiso8601) >= 3' "${TMP}/audit-k15.json" >/dev/null; then
    ok "K15 KoV-beslutet i auditloggen ligger efter förhandlingens start (beslutstid, inte starttid)"
  else
    no "K15 KoV-beslutets tid i auditloggen är förhandlingens starttid: $(jq -c '[.handelser[] | select(.kalla|test("KoV")) | {tid, kod}] | last' "${TMP}/audit-k15.json")"
  fi
else
  no "K15 ingen väntande förhandling att besluta om"
fi

section "K16 Publika vyns felsidor: rätt språk och inga interna uppgifter (publik_vy_fel.py, körs i publik-vy-containern)"
if docker exec "${SVADA_PREFIX:-svada}-publik-vy" true >/dev/null 2>&1; then
  docker exec -i "${SVADA_PREFIX:-svada}-publik-vy" python - < tests/publik_vy_fel.py 2>&1 | tee "${TMP}/pvfel.log"
  PRC=${PIPESTATUS[0]}                 # exitkoden räknas också: ett fel efter de 20 OK-raderna får inte maskeras (del e)
  PFEL=$(grep -c '^  \[FEL\]' "${TMP}/pvfel.log"); POK=$(grep -c '^  \[OK\]' "${TMP}/pvfel.log")
  [ "${PRC}" -eq 0 ] && [ "${POK}" -ge 20 ] && [ "${PFEL}" -eq 0 ] && ok "K16 felsidorna är på rätt språk och utan interna uppgifter (${POK} kontroller)" \
    || no "K16 felsidorna: exit ${PRC}, ${PFEL} fel, ${POK} godkända kontroller"
else
  no "K16 publik-vy-containern körs inte"
fi

section "K23 Nedräkning till nattens nollställning: tidsberäkning, nytt försök och upptidskontroll (utan stack)"
python3 -I tests/aterstall_enhet.py >"${TMP}/aterstall-enhet.log" 2>&1 && ok "K23 tidsberäkningen (sommar-/vintertid, ogiltigt värde, identiska kopior)" \
  || no "K23 tidsberäkningen: $(grep -c FEL "${TMP}/aterstall-enhet.log") fel"
python3 -I tests/skydd_enhet.py >"${TMP}/skydd-enhet.log" 2>&1 && ok "K23 skydden utan lösenord (ursprung, rättvis kö, automatisk återinsättning och avstängd felinjektion)" \
  || no "K23 skydden: $(grep -c FEL "${TMP}/skydd-enhet.log") fel"
python3 -I tests/statistik_enhet.py >"${TMP}/statistik-enhet.log" 2>&1 && ok "K26 statistikrapporten räknar sidvisningar, unika, robotar, fel och kampanjer rätt (statistik_enhet.py, $(grep -c '\[OK\]' "${TMP}/statistik-enhet.log") kontroller)" \
  || no "K26 statistik_enhet.py: $(grep -c FEL "${TMP}/statistik-enhet.log") fel"
python3 -I tests/fcf_csv_enhet.py >"${TMP}/fcf-csv.log" 2>&1 && ok "K23 FCF bygger sin bas på brunn 4526:s CSV (fcf_csv_enhet.py, $(grep -c '\[OK\]' "${TMP}/fcf-csv.log") kontroller)" \
  || no "K23 fcf_csv_enhet.py: $(grep -c FEL "${TMP}/fcf-csv.log") fel"
bash tests/aterstall_forsok.sh >"${TMP}/aterstall-forsok.log" 2>&1 && ok "K23 återställningsomslaget gör ett nytt försök och upptidskontrollen skiljer ok/nollställs/fel" \
  || no "K23 omslaget/upptidskontrollen: $(grep -c FEL "${TMP}/aterstall-forsok.log") fel"

# K24: skydden i den RIKTIGA appen (middleware, rutter, jobbmodul, städning) med kontrollerad klocka och stubbade källor, i
# dashboard-imagen utan nätverk. Skiljer sig från K23 (hjälpfunktionerna): här prövas att kopplingarna finns. En bortkopplad
# städloop, en saknad återhämtningskontroll eller ett jobb som inte markerar sitt slut gör testet rött (tests/mutationsprov.sh).
section "K24 Skydden i den körande appen (skydd_integration.py, utan stack och utan nätverk)"
DASH_IMAGE="$(docker inspect "${SVADA_PREFIX:-svada}-dashboard" --format '{{.Config.Image}}' 2>/dev/null)"
if [ -z "${DASH_IMAGE}" ]; then
  no "K24 hittar ingen dashboard-image (${SVADA_PREFIX:-svada}-dashboard saknas); testet kan inte köras"
else
  docker run --rm --network none -e DEMO_VARIANT=extern -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" \
    python /tst/skydd_integration.py 2>&1 | grep -v '^\[jobb \|^\[audit\]' | tee "${TMP}/skydd-integration.log"
  IRC=${PIPESTATUS[0]}
  IFEL=$(grep -c '^  \[FEL\]' "${TMP}/skydd-integration.log"); IOK=$(grep -c '^  \[OK\]' "${TMP}/skydd-integration.log")
  if [ "${IRC}" -eq 0 ] && [ "${IFEL}" -eq 0 ] && [ "${IOK}" -ge 40 ]; then ok "K24 skydden i appen: ${IOK} kontroller gröna"
  else no "K24 skydden i appen: exit ${IRC}, ${IFEL} fel, ${IOK} OK (väntade minst 40)"; fi
fi

section "K24b Samordnarens utestängning: flaggan DASH_UTESTANGNING och standard per variant (appen i dashboard-imagen, utan nätverk)"
if [ -n "${DASH_IMAGE:-}" ]; then
  flagga() {  # flagga <DEMO_VARIANT> <DASH_UTESTANGNING> -> True/False
    docker run --rm --network none -e DEMO_VARIANT="$1" -e DASH_UTESTANGNING="$2" -v "${PWD}/services:/srv:ro" "${DASH_IMAGE}" \
      python -c "import sys; sys.path[:0]=['/srv/dashboard','/srv']; import main; print(main.UTESTANGNING_TILLATEN)" 2>/dev/null | tail -1
  }
  [ "$(flagga extern "")" = False ] && ok "K24b extern, variabeln tom: avstängd (en tom variabel räknas som osatt)" || no "K24b extern utan variabel är inte avstängd"
  [ "$(flagga intern "")" = True ] && ok "K24b intern, variabeln tom: på" || no "K24b intern utan variabel är inte på"
  [ "$(flagga extern ja)" = True ] && ok "K24b extern med DASH_UTESTANGNING=ja: på" || no "K24b DASH_UTESTANGNING=ja slår inte på i extern variant"
  [ "$(flagga intern nej)" = False ] && ok "K24b intern med DASH_UTESTANGNING=nej: av" || no "K24b DASH_UTESTANGNING=nej stänger inte av i intern variant"
  docker inspect "${SVADA_PREFIX:-svada}-dashboard" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -q '^DASH_UTESTANGNING=' \
    && ok "K24b variabeln når dashboard-containern (compose skickar den vidare)" || no "K24b DASH_UTESTANGNING finns inte i dashboard-containern (saknas i compose)"
else
  no "K24b ingen dashboard-image"
fi

section "K25 Id:n från servern körs aldrig som kod (vy_handelser_webblasare.mjs, isolerad fixtur, utan stack)"
# Del a2, A2-03: sidan renderas utan stack och alla API-svar mockas; id:n med apostrof, citattecken, backslash och radslut
# ska vara data vid klick på Godkänn och KoV häver. Kräver node och playwright-core, annars [HOPPAR ÖVER] (= rött i verify_all).
if [ -d tools/node_modules/playwright-core ] && command -v node >/dev/null 2>&1; then
  node tests/vy_handelser_webblasare.mjs 2>&1 | tee "${TMP}/vy-handelser.log"
  VRC=${PIPESTATUS[0]}; VOK=$(grep -c '^  \[OK\]' "${TMP}/vy-handelser.log")
  [ "${VRC}" -eq 0 ] && [ "${VOK}" -ge 16 ] && ok "K25 id:n behandlas som data (${VOK} kontroller)" || no "K25 id-injektion: exit ${VRC}, ${VOK} OK"
else
  echo "  [HOPPAR ÖVER] K25 kräver 'cd tools && npm install' och Chrome"
fi

section "K3 Webbläsartest (Chrome via playwright-core)"
if [ -d tools/node_modules/playwright-core ] && command -v node >/dev/null 2>&1; then
  # Steg 6 i läge B förutsätter en B-leverans. B-vyn döljer rader ur hävda A-avtal, så testet litar inte på
  # tillstånd från tidigare tester utan levererar B själv (batch, förhandling, transfer).
  for ATG in kor-batch forhandla-b transfer-b; do
    JID=$(curl -s --max-time 30 -X POST "${DASH}/api/atgard/${ATG}" -H 'content-type: application/json' -d '{}' | jq -r '.id // empty')
    for _ in $(seq 1 60); do
      [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${JID}" | jq -r '.status')" != "kör" ] && break
      sleep 2
    done
    ST=$(curl -s --max-time 10 "${DASH}/api/jobb/${JID}" | jq -r '.status // "okänd"')
    [ "${ST}" = "klar" ] || no "K3 förberedelsen: ${ATG} blev inte klar (status ${ST}); proven av steg 5 och 6 i läge B förutsätter en B-leverans"
  done
  # Delkörning och förkortade väntor (ONLY, STILLA_MAX) är till för nivå 1–2; ett fullt prov får aldrig ärva dem ur skalet.
  env -u ONLY -u STILLA_MAX DASH="${DASH}" PUBLIKVY="http://localhost:${PUBLIK_VY_PORT}" node tests/kedjevy_webblasare.mjs 2>&1 | tee "${TMP}/webblasare.log"
  WRC=${PIPESTATUS[0]}
  WFEL=$(grep -c '^  \[FEL\]' "${TMP}/webblasare.log")
  if [ "${WRC}" -ne 0 ]; then no "K3 webbläsartestet avslutades med kod ${WRC} (${WFEL} [FEL]-rader)"
  elif [ "${WFEL}" -eq 0 ]; then ok "K3 webbläsartestet grönt"
  else no "K3 ${WFEL} fel i webbläsartestet"; fi
else
  echo "  [HOPPAR ÖVER] webbläsartestet kräver 'cd tools && npm install' och Chrome"
fi

# K39: nedladdningarna (nedladdning.py, filer.py): registret, åtkomst, interna adresser, kontrollsummor; utan stack
section "K39 Nedladdning (nedladdning_enhet.py, utan stack)"
python3 -I tests/nedladdning_enhet.py > "${TMP}/nedladdning-enhet.log" 2>&1; NDRC=$?
cat "${TMP}/nedladdning-enhet.log"
[ "${NDRC}" -eq 0 ] && ok "K39 nedladdningarna: $(grep -c '\[OK\]' "${TMP}/nedladdning-enhet.log") kontroller gröna" || no "K39 nedladdningarna misslyckades (exit ${NDRC})"

# K40: nedladdningarna mot stacken. Filerna är det kedjan faktiskt har, med SHA-256 som stämmer med de byte som skickas, leveransens summa
# är den ingest-service räknade vid mottagandet (och som auditloggen bär), och inget internt läcker.
section "K40 Nedladdning mot stacken: faktiska filer, kontrollsumma, auditloggen, inget internt"
PUBV="http://localhost:${PUBLIK_VY_PORT}"
for ATG in kor-batch forhandla-b transfer-b; do        # en B-leverans ska finnas (den ska vara mottagen under ett avtal)
  JID=$(curl -s --max-time 30 -X POST "${DASH}/api/atgard/${ATG}" -H 'content-type: application/json' -d '{}' | jq -r '.id // empty')
  for _ in $(seq 1 60); do [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${JID}" | jq -r '.status')" != "kör" ] && break; sleep 2; done
done
shasum_fil() { shasum -a 256 "$1" | cut -d' ' -f1; }
NDFEL=0
for F in matvarden matvarden-csv katalog deltagare odrl-b odrl-a avtal leverans-b schemakontroll cip-b analys-b-csv analys-b-json ordlista mim; do
  KOD=$(curl -s --max-time 60 -D "${TMP}/nd-$F.h" -o "${TMP}/nd-$F.body" -w '%{http_code}' "${DASH}/api/ladda-ned/${F}")
  if [ "${KOD}" != "200" ]; then echo "  [FEL] ${F}: HTTP ${KOD} ($(head -c 200 "${TMP}/nd-$F.body"))"; NDFEL=$((NDFEL+1)); continue; fi
  HS=$(grep -i '^x-content-sha256:' "${TMP}/nd-$F.h" | tr -d '\r' | awk '{print $2}'); BS=$(shasum_fil "${TMP}/nd-$F.body")
  if [ "${F}" != "leverans-b" ]; then
    [ "${HS}" = "${BS}" ] && echo "  [OK] ${F}: kontrollsumman stämmer med filen" || { echo "  [FEL] ${F}: huvudet ${HS} men filen ${BS}"; NDFEL=$((NDFEL+1)); }
  fi
  grep -qiE 'edc-provider|edc-consumer|orion-stad|stad-gateway|ingest-service|identity-hub|host\.docker\.internal|127\.0\.0\.1|mintaka:' "${TMP}/nd-$F.body" && { echo "  [FEL] ${F}: interna adresser i filen"; NDFEL=$((NDFEL+1)); }
  grep -qi '^content-disposition: attachment; filename="svada-' "${TMP}/nd-$F.h" || { echo "  [FEL] ${F}: saknar Content-Disposition med filnamn"; NDFEL=$((NDFEL+1)); }
done
[ "${NDFEL}" -eq 0 ] && ok "K40 14 filer: 200, kontrollsumma rätt, inga interna adresser, filnamn" || no "K40 ${NDFEL} fel bland de 14 filerna"
# Leveransen: byte för byte det som togs emot; summan är den som räknades vid mottagandet och som auditloggen bär.
HS=$(grep -i '^x-content-sha256:' "${TMP}/nd-leverans-b.h" | tr -d '\r' | awk '{print $2}'); BS=$(shasum_fil "${TMP}/nd-leverans-b.body")
[ "${HS}" = "${BS}" ] && ok "K40 leverans-b: summan som räknades vid mottagandet är summan av filen" || no "K40 leverans-b: mottagningssumman ${HS} är inte filens ${BS}"
curl -s --max-time 30 "${DASH}/api/audit" | jq -e --arg s "${HS}" '[.handelser[]? | select(.typ=="leverans") | .detaljer.sha256] | index($s) != null' >/dev/null \
  && ok "K40 auditloggen bär leveransens SHA-256" || no "K40 auditloggen saknar leveransens SHA-256 ${HS}"
[ "$(jq '.records | length' "${TMP}/nd-leverans-b.body")" = "91" ] && ok "K40 leverans-b innehåller 91 poster" || no "K40 leverans-b har inte 91 poster"
# Engelska: filen ska komma som den är, med summa och filnamn (översättningen av API-svar får inte röra nedladdningar).
curl -s --max-time 60 -D "${TMP}/nd-en.h" -o "${TMP}/nd-en.body" -H 'Accept-Language: en-US' "${DASH}/api/ladda-ned/odrl-b?lang=en" >/dev/null
HS=$(grep -i '^x-content-sha256:' "${TMP}/nd-en.h" | tr -d '\r' | awk '{print $2}')
[ -n "${HS}" ] && [ "${HS}" = "$(shasum_fil "${TMP}/nd-en.body")" ] && grep -qi '^content-disposition: attachment; filename="svada-.*\.json"' "${TMP}/nd-en.h" \
  && ok "K40 engelska: nedladdningen bär kontrollsumma och filnamn, och summan stämmer med filen" || no "K40 engelska: nedladdningen saknar summa eller filnamn, eller summan stämmer inte"
[ "$(jq 'length' "${TMP}/nd-cip-b.body")" -ge 91 ] && ok "K40 stadens plattform (B) har minst 91 poster" || no "K40 cip-b har färre än 91 poster"
! head -1 "${TMP}/nd-analys-b-csv.body" | grep -qi 'position\|lon\|lat' && ok "K40 analysen för B saknar positioner" || no "K40 analys-b-csv har positioner"
curl -s --max-time 30 "${DASH}/api/audit" | jq -e '[.handelser[]? | select(.typ=="nedladdning")] | length > 0' >/dev/null && ok "K40 nedladdningarna syns i auditloggen" || no "K40 nedladdningar saknas i auditloggen"
# A följer avtalet: finns inget GÄLLANDE A-avtal i stadens register ska varje A-fil nekas med exakt 403; finns ett får svaret vara 200 (eller 409 när
# ingen leverans är mottagen än), aldrig 403 av fel skäl eller ett serverfel. (Förr godkändes 200, 403 och 409 oavsett, så en fil som lämnades ut utan avtal gav grönt.)
GALLANDE_A=$(curl -s --max-time 30 "${DASH}/api/avtal" | jq '[.avtal[]? | select(.distribution=="A" and .status=="GALLANDE")] | length')
for A in leverans-a cip-a analys-a-csv analys-a-geojson; do
  KOD=$(curl -s --max-time 60 -o "${TMP}/nd-a.body" -w '%{http_code}' "${DASH}/api/ladda-ned/${A}")
  if [ "${GALLANDE_A:-0}" -eq 0 ]; then
    [ "${KOD}" = "403" ] && ok "K40 ${A}: 403 utan gällande A-avtal" || no "K40 ${A}: ${KOD} men inget gällande A-avtal finns (förväntat 403)"
  else
    case "${KOD}" in 200|409) ok "K40 ${A}: ${KOD} med gällande A-avtal";; *) no "K40 ${A}: ${KOD} med gällande A-avtal (förväntat 200 eller 409)";; esac
  fi
done
# Efter en hävning: webbläsartestet strax före lämnar ett gällande A-avtal, så grenen "403 utan avtal" ovan körs annars nästan aldrig. Här häver vi
# alla gällande A-avtal (testtillstånd; senare skript förhandlar nya) och kräver exakt 403 på varje A-fil, även leverans-a som läser ur ingest.
# Hävningen är ett jobb och kedjan kör ett jobb i taget: häv ett avtal, vänta tills jobbet är klart, ta nästa.
for _ in $(seq 1 12); do
  DHI=$(curl -s --max-time 30 "${DASH}/api/avtal" | jq -r '[.avtal[]? | select(.distribution=="A" and .status=="GALLANDE" and .dhiAvtalId) | .dhiAvtalId][0] // empty')
  [ -z "${DHI}" ] && break
  JID=$(curl -s --max-time 60 -X POST "${DASH}/api/kov/avtal/${DHI}/hav" | jq -r '.id // empty')
  [ -z "${JID}" ] && { sleep 3; continue; }      # upptaget: ett annat jobb kör, försök igen
  for _ in $(seq 1 30); do [ "$(curl -s --max-time 10 "${DASH}/api/jobb/${JID}" | jq -r '.status')" != "kör" ] && break; sleep 2; done
done
for _ in $(seq 1 30); do     # hävningen är ett jobb: vänta tills registret säger att inget A-avtal gäller
  GALLANDE_EFTER=$(curl -s --max-time 30 "${DASH}/api/avtal" | jq '[.avtal[]? | select(.distribution=="A" and .status=="GALLANDE")] | length')
  [ "${GALLANDE_EFTER:-1}" -eq 0 ] && break; sleep 2
done
if [ "${GALLANDE_EFTER:-1}" -eq 0 ]; then
  for A in leverans-a cip-a analys-a-csv analys-a-geojson; do
    KOD=$(curl -s --max-time 60 -o "${TMP}/nd-a.body" -w '%{http_code}' "${DASH}/api/ladda-ned/${A}")
    [ "${KOD}" = "403" ] && ok "K40 ${A}: 403 efter att alla A-avtal hävts" || no "K40 ${A}: ${KOD} efter hävning (förväntat 403)"
  done
else
  no "K40 kunde inte häva A-avtalen (${GALLANDE_EFTER} gäller fortfarande), så nekandet efter hävning är inte prövat"
fi
[ "$(curl -s -o /dev/null -w '%{http_code}' "${DASH}/api/ladda-ned/finns-inte")" = "404" ] && ok "K40 en okänd fil ger 404" || no "K40 okänd fil ger inte 404"
# Brunnsvyn: CSV, JSON med summa, datamodellen som zip med manifest och termlistan som CSV
curl -s --max-time 30 -D "${TMP}/pv.h" -o "${TMP}/pv.csv" "${PUBV}/brunnar?format=csv"
[ "$(grep -i '^x-content-sha256:' "${TMP}/pv.h" | tr -d '\r' | awk '{print $2}')" = "$(shasum_fil "${TMP}/pv.csv")" ] && [ "$(wc -l < "${TMP}/pv.csv")" -ge 92 ] \
  && ok "K40 brunnsvyn: CSV med kontrollsumma och minst 91 brunnar" || no "K40 brunnsvyns CSV"
curl -s --max-time 30 -D "${TMP}/pj.h" -o "${TMP}/pj.json" "${PUBV}/brunnar?format=json"
[ "$(grep -i '^x-content-sha256:' "${TMP}/pj.h" | tr -d '\r' | awk '{print $2}')" = "$(shasum_fil "${TMP}/pj.json")" ] && ok "K40 brunnsvyn: JSON bär kontrollsumman av de byte som skickas" || no "K40 brunnsvyns JSON-summa"
curl -s --max-time 30 -D "${TMP}/z.h" -o "${TMP}/utkast.zip" "${PUBV}/modell/utkast/0.1/utkast.zip"
curl -s --max-time 30 -o "${TMP}/utkast2.zip" "${PUBV}/modell/utkast/0.1/utkast.zip"
python3 -I - "${TMP}/utkast.zip" > "${TMP}/zipprov.log" 2>&1 <<'PY' && ok "K40 datamodellen som zip: manifestet stämmer med varje fil och LÄS-MIG säger utkast" || { cat "${TMP}/zipprov.log"; no "K40 zip-provet"; }
import hashlib, json, sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); m = json.loads(z.read("MANIFEST.json"))["sha256"]
assert m and all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in m.items()), "manifest"
assert b"DRAFT" in z.read("READ-ME.txt")
assert b"invalid" not in z.read("context.jsonld") and b"modell.svada" not in z.read("context.jsonld")
PY
cmp -s "${TMP}/utkast.zip" "${TMP}/utkast2.zip" && ok "K40 zip-filen är densamma vid varje hämtning (samma summa)" || no "K40 zip-filen skiljer mellan hämtningar"
[ "$(grep -i '^x-content-sha256:' "${TMP}/z.h" | tr -d '\r' | awk '{print $2}')" = "$(shasum_fil "${TMP}/utkast.zip")" ] && ok "K40 zip: kontrollsumman i huvudet stämmer" || no "K40 zip-summan"
[ "$(curl -s --max-time 30 "${PUBV}/modell/utkast/0.1/termlista.csv" | wc -l)" -ge 52 ] && ok "K40 termlistan som CSV har alla termer" || no "K40 termlistan som CSV"

# K28: en egen vy per besökare (sessioner.py och sessionsdelarna i jobb.py): kaka, tidsgräns, tak, jobbkö, ägande. Utan stack och nätverk.
section "K28 En egen vy per besökare: sessioner, jobbkö och ägande (sessioner_enhet.py, utan stack och utan nätverk)"
if [ -n "${DASH_IMAGE:-}" ]; then
  docker run --rm --network none -e DEMO_VARIANT=extern -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" \
    python /tst/sessioner_enhet.py 2>&1 | grep -v '^\[jobb \|^\[audit\]' | tee "${TMP}/sessioner-enhet.log"
  SRC=${PIPESTATUS[0]}
  SFEL=$(grep -c '^  \[FEL\]' "${TMP}/sessioner-enhet.log"); SOK=$(grep -c '^  \[OK\]' "${TMP}/sessioner-enhet.log")
  if [ "${SRC}" -eq 0 ] && [ "${SFEL}" -eq 0 ] && [ "${SOK}" -ge 30 ]; then ok "K28 sessioner och jobbkö: ${SOK} kontroller gröna"
  else no "K28 sessioner och jobbkö: exit ${SRC}, ${SFEL} fel, ${SOK} OK (väntade minst 30)"; fi
else
  no "K28 hittar ingen dashboard-image; testet kan inte köras"
fi

# K30: batch-upserten mot Orion-LD (ngsild.py): 200/201/204 godtas, 207 bara utan fel, allt annat och en trasig 207-kropp ger OrionFel.
section "K30 Mottagningens upsert mot Orion-LD: 207 och felsvar (ngsild_enhet.py, stubbserver, utan stack)"
if [ -n "${DASH_IMAGE:-}" ]; then
  docker run --rm --network none -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" \
    python /tst/ngsild_enhet.py 2>&1 | tee "${TMP}/ngsild-enhet.log"
  NRC=${PIPESTATUS[0]}
  NFEL=$(grep -c '^  \[FEL\]' "${TMP}/ngsild-enhet.log"); NOK=$(grep -c '^  \[OK\]' "${TMP}/ngsild-enhet.log")
  if [ "${NRC}" -eq 0 ] && [ "${NFEL}" -eq 0 ] && [ "${NOK}" -ge 12 ]; then ok "K30 upserten mot Orion-LD: ${NOK} kontroller gröna"
  else no "K30 upserten mot Orion-LD: exit ${NRC}, ${NFEL} fel, ${NOK} OK (väntade minst 12)"; fi
else
  no "K30 hittar ingen dashboard-image; testet kan inte köras"
fi

# OBS: K27 skriver riktiga (vitlistade) händelser i statistik/data och ska därför bara köras mot en lokal stack, inte mot servern.
section "K27 Statistik: sidan /statistik och händelseräknaren (vitlista, ingen identifierare, robotar räknas inte)"
UA_BESOKARE="Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Safari/537.36"
steg3() { curl -s --max-time 20 "${DASH}/api/statistik?ny=1" | python3 -c 'import sys,json;print(json.load(sys.stdin)["handelser"].get("steg_3",0))'; }
hpost() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "${DASH}/api/handelse" -H 'content-type: application/json' -A "$1" -d "$2"; }
sleep 6; ST0="$(steg3)"
[ "$(hpost "${UA_BESOKARE}" '{"h":"steg_3"}')" = 204 ] && ok "K27a en vitlistad händelse tas emot (204)" || no "K27a vitlistad händelse nekades"
sleep 6; ST1="$(steg3)"
[ "${ST1}" = "$((ST0 + 1))" ] && ok "K27b händelsen räknas upp med ett (${ST0} -> ${ST1})" || no "K27b steg_3: ${ST0} -> ${ST1}"
[ "$(hpost curl/8.7.1 '{"h":"steg_3"}')" = 204 ] && sleep 6 && [ "$(steg3)" = "${ST1}" ] && ok "K27c en robot (curl) får 204 men räknas inte" || no "K27c roboten räknades eller nekades"
hposttest() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "${DASH}/api/handelse" -H 'content-type: application/json' -H 'Cookie: svada-test=1' -A "$1" -d "$2"; }
[ "$(hposttest "${UA_BESOKARE}" '{"h":"steg_3"}')" = 204 ] && sleep 6 && [ "$(steg3)" = "${ST1}" ] && ok "K27j testläge: en händelse med kakan svada-test får 204 men räknas inte" || no "K27j testlägeshändelsen räknades eller nekades"
OKANDA="$(for b in '{"h":"steg_9"}' '{"h":"atgard_rm-rf"}' '{"h":"flik_x"}' '{"h":"1.2.3.4"}' '{"h":["steg_1"]}' '{"x":1}' '[1]' ''; do hpost "${UA_BESOKARE}" "$b"; echo; done | sort -u | tr '\n' ' ')"
[ "${OKANDA}" = "400 " ] && ok "K27d okända händelser, fritext och fel form avvisas (400)" || no "K27d okända händelser gav ${OKANDA}"
hpost "${UA_BESOKARE}" '{"h":"steg_3","ip":"1.2.3.4","text":"hemligt"}' >/dev/null; sleep 6; steg3 >/dev/null
c_stat() { local d="$1"; if eval "$2" >/dev/null 2>&1; then ok "$d"; else no "$d"; fi; }
c_stat "K27e det lagrade innehåller bara vitlistade namn och tal, ingen IP eller text" "python3 -I - statistik/data/handelser.json <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
tillatna = re.compile(r'^(steg_[1-6]|flik_[a-z]+|sprak_(sv|en)|karta_osm|analys_(a|b)|js_fel|atgard_[a-z0-9-]+)$')
sys.exit(0 if d and all(re.match(r'^\d{4}-\d\d-\d\d$', dag) and all(tillatna.match(k) and isinstance(v, int) for k, v in h.items()) for dag, h in d.items()) else 1)
PY"
SV="$(curl -s -o "${TMP}/stat-sv.html" -w '%{http_code}' --max-time 20 "${DASH}/statistik?lang=sv")"; EN="$(curl -s -o "${TMP}/stat-en.html" -w '%{http_code}' --max-time 20 "${DASH}/statistik?lang=en")"
[ "${SV}" = 200 ] && [ "${EN}" = 200 ] && grep -q "Besökare per dag" "${TMP}/stat-sv.html" && grep -q "Visitors per day" "${TMP}/stat-en.html" && ok "K27f sidan /statistik svarar på svenska och engelska" || no "K27f /statistik: sv ${SV}, en ${EN}"
# Enda tillåtna externa adressen är den vanliga länken till källkoden (ingen resurs som laddas, inget som spårar).
! sed 's#<a href="https://github.com/GoteborgsStad/svada" target="_blank" rel="noopener">##' "${TMP}/stat-sv.html" | grep -qiE 'https?://|<script|cookie=' && ok "K27g sidan har inget skript och inga externa adresser utom länken till källkoden" || no "K27g sidan har skript eller externa adresser"
grep -q "Step 1 – The model (simulated) creates the data product" "${TMP}/stat-en.html" && ! grep -q "Steps 1" "${TMP}/stat-en.html" && grep -q "Steg 1 – Modellen (simulerad) skapar" "${TMP}/stat-sv.html" && ok "K27j stegen heter detsamma som i kontrollrummet, på rätt språk ('Step 1', inte 'Steps 1')" || no "K27j stegnamnen i statistiken stämmer inte med kontrollrummets, eller engelskan är halvöversatt"
curl -s --max-time 20 "${DASH}/api/status" | jq -e '.avtalA | has("gallande")' >/dev/null && ok "K27i /api/status bär avtalA.gallande, som sidan använder för att läsa om steg 6 när avtalet om A slutar gälla (F1)" || no "K27i /api/status saknar avtalA"
grep -q 'href="/statistik' <(curl -s --max-time 20 "${DASH}/?lang=sv") && ok "K27h kontrollrummets sidfot länkar till statistiken" || no "K27h länken till /statistik saknas i sidfoten"
# K27k: avtalssidan följer vyns språk (även utan ?lang, via webbläsarens språk), har en växlare sv/en och Tillbaka går dit besökaren kom ifrån (?fran=).
AVT_K27=$(curl -s --max-time 20 "${DASH}/api/avtal" | jq -r '.avtal[0].id // empty')
if [ -n "${AVT_K27}" ]; then
  A1=$(curl -s --max-time 20 -H 'Accept-Language: en' "${DASH}/avtal/${AVT_K27}?fran=steg-5"); A2=$(curl -s --max-time 20 "${DASH}/avtal/${AVT_K27}?lang=sv&fran=steg-5"); A3=$(curl -s --max-time 20 "${DASH}/avtal/${AVT_K27}?lang=en&fran=%22%3Cx")
  printf '%s' "${A1}" | grep -q '<html lang="en"' && printf '%s' "${A1}" | grep -q 'href="/?lang=en#steg-5"' && printf '%s' "${A1}" | grep -q 'hreflang="sv"' \
    && printf '%s' "${A2}" | grep -q '<html lang="sv"' && printf '%s' "${A2}" | grep -q 'hreflang="en"' && printf '%s' "${A3}" | grep -q 'href="/?lang=en#suveranitet"' \
    && ok "K27k avtalssidan: följer språket, har växlare och Tillbaka går till stegets flik (okänt ursprung ger Suveränitet)" || no "K27k avtalssidans språk, växlare eller Tillbaka-länk"
else
  echo "  [HOPPAR ÖVER] K27k avtalssidan (inget avtal finns än)"
fi

# K33: språket följer sidan (X-Svada-Lang) och felsidor (404-sida för webbläsare, 404 för ogiltigt avtals-id), i dashboard-imagen utan nätverk
section "K33 Språk per sida och felsidor (sprak_enhet.py, i dashboard-imagen, utan stack)"
if docker image inspect "${DASH_IMAGE}" >/dev/null 2>&1; then
  docker run --rm --network none -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" python /tst/sprak_enhet.py 2>&1 | tee "${TMP}/sprak-enhet.log"
  SPRC=${PIPESTATUS[0]}
  SPFEL=$(grep -c '^  \[FEL\]' "${TMP}/sprak-enhet.log"); SPOK=$(grep -c '^  \[OK\]' "${TMP}/sprak-enhet.log")
  if [ "${SPRC}" -eq 0 ] && [ "${SPFEL}" -eq 0 ] && [ "${SPOK}" -ge 12 ]; then ok "K33 språk och felsidor: ${SPOK} kontroller gröna"
  else no "K33 språk och felsidor: exit ${SPRC}, ${SPFEL} fel, ${SPOK} OK (väntade minst 12)"; fi
else
  no "K33 hittar ingen dashboard-image; testet kan inte köras"
fi
# K33b: språkregeln efter webbläsaren är samma i kontrollrummet, brunnsvyn och gatewayen (ingen stack, inga beroenden)
python3 tests/sprak_publik_enhet.py 2>&1 | tee "${TMP}/sprak-publik.log" | grep -E '^  \[FEL\]'
[ "${PIPESTATUS[0]}" -eq 0 ] && ok "K33b språkregeln är lika i de tre tjänsterna ($(grep -c '^  \[OK\]' "${TMP}/sprak-publik.log") kontroller gröna)" || no "K33b språkregeln i de tre tjänsterna"

# K36: staden hittar leverantören i deltagarregistret (MIM3 RC5.1), i dashboard-imagen utan nätverk
section "K36 Leverantören hittas i deltagarregistret (leverantor_enhet.py, i dashboard-imagen, utan stack)"
if docker image inspect "${DASH_IMAGE}" >/dev/null 2>&1; then
  docker run --rm --network none -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" python /tst/leverantor_enhet.py 2>&1 | tee "${TMP}/leverantor-enhet.log"
  LVRC=${PIPESTATUS[0]}
  LVFEL=$(grep -c '^  \[FEL\]' "${TMP}/leverantor-enhet.log"); LVOK=$(grep -c '^  \[OK\]' "${TMP}/leverantor-enhet.log")
  if [ "${LVRC}" -eq 0 ] && [ "${LVFEL}" -eq 0 ] && [ "${LVOK}" -ge 12 ]; then ok "K36 leverantörsvalet: ${LVOK} kontroller gröna"
  else no "K36 leverantörsvalet: exit ${LVRC}, ${LVFEL} fel, ${LVOK} OK (väntade minst 12)"; fi
else
  no "K36 hittar ingen dashboard-image; testet kan inte köras"
fi

# K32: portförskjutningen (två installationer på samma värd)
section "K32 Portförskjutning: värdportarna flyttas, de interna lämnas (portforskjutning_enhet.py, utan stack)"
python3 -I tests/portforskjutning_enhet.py > "${TMP}/portforskjutning.log" 2>&1; PRC=$?
cat "${TMP}/portforskjutning.log"
[ "${PRC}" -eq 0 ] && ok "K32 portförskjutningen: klassningen och förskjutningen stämmer" || no "K32 portförskjutningen misslyckades (exit ${PRC})"

# K34: datamodellens utkast (termlistan stämmer med koden, filerna är genererade, UTKAST-märkningen finns; utan stack)
section "K34 Datamodellens utkast stämmer med koden och är märkt som utkast (datamodell_enhet.py, utan stack)"
python3 -I tests/datamodell_enhet.py > "${TMP}/datamodell-enhet.log" 2>&1; DMRC=$?
cat "${TMP}/datamodell-enhet.log"
[ "${DMRC}" -eq 0 ] && ok "K34 datamodellens utkast: $(grep -c '\[OK\]' "${TMP}/datamodell-enhet.log") kontroller gröna" || no "K34 datamodellens utkast misslyckades (exit ${DMRC})"

# K35: datamodellen på brunnsvyns adress (modell.py): bara fasta filer, varje term uppslagbar, allt märkt som utkast; utan stack
section "K35 Datamodellens utkast på brunnsvyns adress (modell_publik_enhet.py, utan stack)"
python3 -I tests/modell_publik_enhet.py > "${TMP}/modell-publik-enhet.log" 2>&1; MPRC=$?
cat "${TMP}/modell-publik-enhet.log"
[ "${MPRC}" -eq 0 ] && ok "K35 datamodellen på brunnsvyn: $(grep -c '\[OK\]' "${TMP}/modell-publik-enhet.log") kontroller gröna" || no "K35 datamodellen på brunnsvyn misslyckades (exit ${MPRC})"

# K37: MIM-rutorna på stegen och sidorna (mim.py): status mot docs/mims, länkar, båda språken, inget internt; utan stack
section "K37 MIM-rutor (mim_enhet.py, utan stack)"
python3 -I tests/mim_enhet.py > "${TMP}/mim-enhet.log" 2>&1; MIRC=$?
cat "${TMP}/mim-enhet.log"
[ "${MIRC}" -eq 0 ] && ok "K37 MIM-rutorna: $(grep -c '\[OK\]' "${TMP}/mim-enhet.log") kontroller gröna" || no "K37 MIM-rutorna misslyckades (exit ${MIRC})"

# K38: schemakontrollen vid inläsning (schemakontroll.py): exempelfilerna godkänns, avvikelser hittas, saknat schema redovisas öppet; utan stack
section "K38 Schemakontroll vid inläsning (schemakontroll_enhet.py, utan stack)"
python3 -I tests/schemakontroll_enhet.py > "${TMP}/schemakontroll-enhet.log" 2>&1; SKRC=$?
cat "${TMP}/schemakontroll-enhet.log"
[ "${SKRC}" -eq 0 ] && ok "K38 schemakontrollen: $(grep -c '\[OK\]' "${TMP}/schemakontroll-enhet.log") kontroller gröna" || no "K38 schemakontrollen misslyckades (exit ${SKRC})"

# K41: avtalsscenariot "betrodd organisation" (jobb.py, _egen_betrodd): utpekningen hos providern görs före och tas bort efter besökarens egen A-förhandling
section "K41 Avtalsscenariot betrodd organisation (betrodd_enhet.py, utan stack)"
docker run --rm --network none -e DEMO_VARIANT=extern -v "${PWD}/services:/srv:ro" -v "${PWD}/tests:/tst:ro" "${DASH_IMAGE}" python /tst/betrodd_enhet.py 2>&1 | grep -v '^\[jobb \|^\[audit\]' > "${TMP}/betrodd-enhet.log"; BERC=${PIPESTATUS[0]}
cat "${TMP}/betrodd-enhet.log"
[ "${BERC}" -eq 0 ] && ok "K41 betrodd organisation: $(grep -c '\[OK\]' "${TMP}/betrodd-enhet.log") kontroller gröna" || no "K41 betrodd organisation misslyckades (exit ${BERC})"

# K41b: /api/scenario över HTTP: standard av, ogiltig kropp ger 400, sant och falskt sparas, och ett läge som slagits på städas direkt
section "K41b /api/scenario över HTTP (validering och eget val)"
SC0=$(curl -s --max-time 20 "${DASH}/api/scenario" | jq -r '.betrodd')
SC_BAD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST -H 'content-type: application/json' -d '{"betrodd":"ja"}' "${DASH}/api/scenario")
SC_EXTRA=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST -H 'content-type: application/json' -d '{"betrodd":true,"x":1}' "${DASH}/api/scenario")
SC_ON=$(curl -s --max-time 20 -X POST -H 'content-type: application/json' -d '{"betrodd":true}' "${DASH}/api/scenario" | jq -r '.betrodd')
SC_OFF=$(curl -s --max-time 20 -X POST -H 'content-type: application/json' -d '{"betrodd":false}' "${DASH}/api/scenario" | jq -r '.betrodd')
[ "${SC0}" = "false" ] && [ "${SC_BAD}" = 400 ] && [ "${SC_EXTRA}" = 400 ] && [ "${SC_ON}" = "true" ] && [ "${SC_OFF}" = "false" ] \
  && ok "K41b /api/scenario: av som standard, ogiltig kropp 400, sant och falskt sparas (av igen efter provet)" \
  || no "K41b /api/scenario: standard=${SC0}, felaktig=${SC_BAD}, extra fält=${SC_EXTRA}, på=${SC_ON}, av=${SC_OFF}"

# K31: versionsnumret (.env är källan; nyheter.py, sidfoten, /api/status, /nyheter och brunnsvyn följer det)
section "K31 Versionsnummer: .env, /nyheter, sidfoten och /api/status är samma version (version_enhet.py + mot stacken)"
python3 -I tests/version_enhet.py > "${TMP}/version-enhet.log" 2>&1; VRC2=$?
cat "${TMP}/version-enhet.log"
[ "${VRC2}" -eq 0 ] && ok "K31 versionsprovet utan stack" || no "K31 versionsprovet utan stack misslyckades (exit ${VRC2})"
SVER=$(grep -E '^SVADA_VERSION=' .env | head -1 | cut -d= -f2 | awk '{print $1}')
[ "$(curl -s --max-time 20 "${DASH}/api/status" | jq -r '.demoVersion')" = "${SVER}" ] && ok "K31 /api/status bär demoVersion ${SVER}" || no "K31 /api/status saknar eller har fel demoVersion (väntade ${SVER}); bygg om dashboarden"
grep -q "${SVER}" <(curl -s --max-time 20 "${DASH}/nyheter?lang=sv") && ok "K31 /nyheter visar versionen" || no "K31 /nyheter visar inte versionen"
grep -q "id=\"demoversion\">${SVER}<" <(curl -s --max-time 20 "${DASH}/?lang=sv") && ok "K31 kontrollrummets sidfot visar versionen" || no "K31 sidfoten visar inte versionen"
grep -q "id=\"demoversion\">${SVER}<" <(curl -s --max-time 20 "http://localhost:${PUBLIK_VY_PORT}/brunnar?lang=sv") && ok "K31 brunnsvyns sidfot visar versionen" || no "K31 brunnsvyn visar inte versionen; bygg om publik-vy"

# K29: samma sak mot den körande stacken över HTTP (två besökare via proxyhuvud). Skapar riktiga jobb och ett avtal: sist i filen, bara lokalt.
section "K29 En egen vy per besökare mot den körande stacken (sessioner_http.py)"
if curl -s -D - -o /dev/null -H 'X-Forwarded-For: 203.0.113.99' --max-time 20 "${DASH}/api/jobb" | grep -qi '^set-cookie: svada-sess='; then
  python3 -I tests/sessioner_http.py "${DASH}" 2>&1 | tee "${TMP}/sessioner-http.log"
  HRC=${PIPESTATUS[0]}
  HFEL=$(grep -c '^  \[FEL\]' "${TMP}/sessioner-http.log"); HOK=$(grep -c '^  \[OK\]' "${TMP}/sessioner-http.log")
  if [ "${HRC}" -eq 0 ] && [ "${HFEL}" -eq 0 ] && [ "${HOK}" -ge 24 ]; then ok "K29 besökarnas vyer är åtskilda över HTTP: ${HOK} kontroller gröna"
  else no "K29 ${HFEL} fel, ${HOK} OK (väntade minst 24), exitkod ${HRC}"; fi
else
  echo "  [HOPPAR ÖVER] K29 gäller bara en stack med DEMO_VARIANT=extern och DASH_SESSIONER=ja"
fi

finish "verify_kedjevy"
