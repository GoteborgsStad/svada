#!/usr/bin/env bash
# Gemensamma hjälpfunktioner för verify_apN.sh.
# Källas in: . "$(dirname "$0")/lib.sh"

# Räknare för fel i aktuellt skript.
FAIL=0

# Cd:a till repo-roten (tests/ ligger direkt under roten).
repo_root() { cd "$(dirname "${BASH_SOURCE[1]}")/.." && pwd; }

ok()  { echo "  [OK]  $1"; }
no()  { echo "  [FEL] $1"; FAIL=$((FAIL+1)); }

# check "beskrivning" <kommando...>  -> [OK]/[FEL] beroende på exit-kod.
check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else no "$desc"; fi
}

section() { echo ""; echo "== $1 =="; }

# logg_innehaller <container> <mönster> – söker i containerns logg med RETRY.
#
# FYND: `docker logs` kan under
# hög belastning returnera OFULLSTÄNDIGT utdata. Testfall 4a.4 och 4b.x letar
# efter uppstartsrader i edc-providerns logg och blev då slumpvis röda i
# verify_all – trots att raderna fanns kvar (containern hade varken startats
# om (RestartCount 0) eller tappat loggen). Tre försök gör kontrollen stabil
# utan att göra den snällare: mönstret måste fortfarande finnas.
logg_innehaller() {
  local container="$1" monster="$2" logg
  for _ in 1 2 3; do
    logg="$(docker logs "${container}" 2>&1)"
    if grep -q "${monster}" <<<"${logg}"; then return 0; fi
    sleep 2
  done
  return 1
}

# Verifierbar identitet (KovIdentitetsverifiering.java):
# hamta_kov_token – hämtar ett self-issued DCP-token som bevisar KoV:s
# SvadaRoleCredential, för att skickas som Authorization: Bearer-header till
# providerns POST /management/kov/forhandlingar/{id}/godkann|avsla.
#
# Hämtas från Stadens EGEN inbäddade STS (identity-hub-stad:29199/api/sts/token,
# OAuth2 client_credentials). Porten är MEDVETET inte publicerad mot host (se
# compose.stad.yml) – anropet görs därför via `docker exec` i en container
# som redan ligger på nätverket stad-internal (svada-edc-consumer, precis
# som verify_ap4a.sh redan gör med sina docker exec-curl-anrop mot providern).
#
# Förutsätter att .env redan är källat (SVADA_PARTICIPANT_DID_STAD,
# SVADA_STS_CLIENT_SECRET_STAD, EDC_PROVIDER_ID). Skriver tokenet på stdout,
# tomt vid fel – anroparen avgör själv om ett tomt token ska räknas som fel.
hamta_kov_token() {
  local svar
  svar=$(docker exec ${SVADA_PREFIX:-svada}-edc-consumer curl -s --max-time 15 -X POST \
      "http://identity-hub-stad:29199/api/sts/token" \
      --data-urlencode "grant_type=client_credentials" \
      --data-urlencode "client_id=${SVADA_PARTICIPANT_DID_STAD}" \
      --data-urlencode "client_secret=${SVADA_STS_CLIENT_SECRET_STAD}" \
      --data-urlencode "audience=${EDC_PROVIDER_ID}" \
      --data-urlencode "bearer_access_scope=org.eclipse.dspace.dcp.vc.type:SvadaRoleCredential:read" \
      2>/dev/null)
  echo "$svar" | jq -r '.access_token // empty'
}

# demo_inloggning <katalog> – loggar in i den publika demons lösenordsgrind
# (Caddy, snippet "inloggning") EN gång och låter sedan ALLA curl-anrop i
# skriptet bära tillträdeskakan.
#
# Testerna går genom de publika adresserna (accessURL ur katalogen m.m.),
# och där kräver Caddy lösenordet. Inloggningen görs som i en webbläsare:
# Basic Auth mot kontrollrummet, kakan sparas, och den gäller för hela
# domänen. Därmed provas också att kakan faktiskt delas av underdomänerna.
#
# Mekanism: curl läser $CURL_HOME/.curlrc; där pekar "cookie" ut kakburken.
# Kakan är bunden till DEMO_DOMAN, så anrop mot localhost:<port> påverkas
# inte. Lösenordet läses ur .demo-losenord och skickas till curl via stdin
# (-K -) – aldrig som argument, och det skrivs aldrig ut.
#
# Utan PUBLIK_URL_KONTROLLRUM (originalet, ingen publik ingång): no-op.
# Returnerar 1 (och skriver ett FEL) om inloggningen misslyckas.
demo_inloggning() {
  local dir="$1" anv pw svar
  [ -n "${PUBLIK_URL_KONTROLLRUM:-}" ] || return 0
  # Lösenordsgrinden är avstängd (DEMO_GATE=off): ingen inloggning behövs och ingen kaka finns.
  [ "${DEMO_GATE:-on}" = "off" ] && { echo "  (lösenordsgrinden är avstängd: ingen inloggning)"; return 0; }
  if [ ! -s .demo-losenord ]; then
    no "demo_inloggning: .demo-losenord saknas (kör tools/nytt-demo-losenord.sh)"
    return 1
  fi
  anv="$(sed -n 's/^användare: //p' .demo-losenord)"
  pw="$(sed -n 's/^lösenord: //p' .demo-losenord)"
  # curl-konfigurationens citat: \ och " måste skyddas (valfritt lösenord).
  pw="${pw//\\/\\\\}"; pw="${pw//\"/\\\"}"
  svar="$(printf 'user = "%s:%s"\n' "${anv}" "${pw}" \
    | curl -s -q -K - -c "${dir}/demo-kakor" -o /dev/null -w '%{http_code}' \
        --max-time 30 "${PUBLIK_URL_KONTROLLRUM}/health")"
  if [ "${svar}" != "200" ] || ! grep -q svada_tilltrade "${dir}/demo-kakor" 2>/dev/null; then
    no "demo_inloggning: inloggningen i lösenordsgrinden gav ${svar} (ingen kaka)"
    return 1
  fi
  printf 'cookie = "%s"\n' "${dir}/demo-kakor" >"${dir}/.curlrc"
  export CURL_HOME="${dir}"
}

# kontrollera_mal – skrivande tester (jobb, avtal, återkallelser, policyändringar) vägrar köra mot fel stack (del e, E9).
# Kräver att .env är läst. Stoppar om prefixet saknas eller är originalets "svada" (dess volymer ska aldrig röras), eller
# om stackens kontrollrum inte körs med det prefixet.
kontrollera_mal() {
  if [ -z "${SVADA_PREFIX:-}" ] || [ "${SVADA_PREFIX}" = "svada" ]; then
    echo "  [FEL] SVADA_PREFIX='${SVADA_PREFIX:-}': skrivande tester körs inte mot originalet eller ett okänt mål"; exit 2
  fi
  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${SVADA_PREFIX}-dashboard"; then
    echo "  [FEL] ingen körande ${SVADA_PREFIX}-dashboard: fel stack eller stacken är nere"; exit 2
  fi
}

# Skriv slutrad och returnera FAIL som exit-kod.
finish() {
  echo ""
  if [ "$FAIL" -eq 0 ]; then
    echo ">> $1: GRÖNT"
  else
    echo ">> $1: RÖTT ($FAIL fel)"
  fi
  return "$FAIL"
}
