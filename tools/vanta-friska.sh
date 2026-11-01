#!/usr/bin/env bash
# =====================================================================
# vanta-friska.sh – väntar in att containrar blir friska, och startar om en som inte blir det
# =====================================================================
# Varför: en EDC- eller IdentityHub-container startar ibland med en API-route som saknas (hälsovägen svarar 404 i
# evighet fast "Runtime ... ready" står i loggen, utan fel). Mätt 2026-11-01: 5 av 180 omstarter under CPU-last (providern 2 av 90, identitetstjänsten 3 av 90), 0 av 80 utan last. Samma fenomen
# sågs 2026-10-14 (edc-consumer utan avtals-API:t). Docker markerar containern "unhealthy" först efter
# start_period + retries x interval (ca 4-5 minuter), så det går inte att vänta på Dockers status.
# Skriptet kör i stället containerns EGEN hälsokontroll (samma kommando som compose-filen anger) direkt, och
# startar om containern en gång per misslyckat försök. Efter hälsokontrollen prövas också de vägar kedjan använder (se vagar() nedan):
# en tjänst med frisk hälsa men saknad route räknas som inte frisk.
#
#   bash tools/vanta-friska.sh edc-provider edc-consumer identity-hub-dhi identity-hub-stad
#
# Namnen är tjänstenamn utan prefix; prefixet läses ur SVADA_PREFIX (som i övriga skript).
# SEKUNDER = väntetid per försök (standard 60), FORSOK = antal försök (standard 3).
# Slutstatus 0 om alla blev friska, annars 1. Rör ingenting utom att starta om en container som inte svarar.
set -uo pipefail

PREFIX="${SVADA_PREFIX:-svada}"
SEKUNDER="${SEKUNDER:-60}"
FORSOK="${FORSOK:-3}"
STEG=2
fel=0

halsokommando() {   # halsokommando <container> -> skriver kommandot som "sh -c"-sträng, tomt om containern saknar hälsokontroll
  local test
  test="$(docker inspect -f '{{json .Config.Healthcheck.Test}}' "$1" 2>/dev/null)" || return 1
  [ -n "${test}" ] && [ "${test}" != "null" ] || return 1
  python3 - "${test}" <<'PY'
import json, shlex, sys
t = json.loads(sys.argv[1])
if not t or t[0] == "NONE":
    sys.exit(1)
if t[0] == "CMD-SHELL":
    print(t[1])
elif t[0] == "CMD":
    print(" ".join(shlex.quote(a) for a in t[1:]))
else:
    sys.exit(1)
PY
}

# Vägar som kedjan faktiskt använder och som kan saknas trots frisk hälsokontroll (samma startfel, annan route). Format: "METOD url".
# Ett svar med 000, 404 eller 405 betyder att vägen saknas; 401/400/500 betyder att den finns (vi skickar ingen nyckel eller kropp).
# Mätt 2026-11-01: edc-consumer startade utan POST /v3/contractnegotiations/request (405) fast hälsovägen svarade 200;
# stadens avtalsregister kunde då inte para ihop avtalet med DHI och stängde (OKAND) – hela avtalsflödet föll.
vagar() {   # vagar <tjänstenamn> -> en rad per väg
  case "$1" in
    edc-consumer) echo "POST http://localhost:29193/management/v3/contractnegotiations/request"
                  echo "POST http://localhost:29193/management/v3/contractagreements/request" ;;
    edc-provider) echo "GET http://localhost:19195/status/avtalsstatus"
                  echo "POST http://localhost:19193/management/v3/contractnegotiations/request" ;;
    identity-hub-dhi)  echo "POST http://localhost:19199/api/sts/token" ;;
    identity-hub-stad) echo "POST http://localhost:29199/api/sts/token" ;;
  esac
}

frisk() {   # frisk <container> <tjänstenamn> <hälsokommando> -> 0 om hälsokontrollen och alla vägar svarar
  local c="$1" namn="$2" kommando="$3" metod url kod
  docker exec "${c}" sh -c "${kommando}" >/dev/null 2>&1 || return 1
  while read -r metod url; do
    [ -n "${url}" ] || continue
    kod="$(docker exec "${c}" curl -s -o /dev/null -m 3 -X "${metod}" -w '%{http_code}' "${url}" 2>/dev/null)"
    case "${kod}" in 000|404|405|"") return 1 ;; esac
  done < <(vagar "${namn}")
  return 0
}

for namn in "$@"; do
  c="${PREFIX}-${namn}"
  kommando="$(halsokommando "${c}")" || { echo "  ${namn}: saknar hälsokontroll eller finns inte, hoppar över"; continue; }
  friska=nej
  for forsok in $(seq 1 "${FORSOK}"); do
    for _ in $(seq 1 $((SEKUNDER / STEG))); do
      if frisk "${c}" "${namn}" "${kommando}"; then friska=ja; break; fi
      sleep "${STEG}"
    done
    [ "${friska}" = ja ] && break
    if [ "${forsok}" -lt "${FORSOK}" ]; then
      echo "  ${namn}: inte frisk efter ${SEKUNDER} s; startar om (försök ${forsok}/${FORSOK})"
      docker restart "${c}" >/dev/null 2>&1
    fi
  done
  if [ "${friska}" = ja ]; then
    echo "  ${namn}: frisk"
  else
    echo "  VARNING: ${namn} blev aldrig frisk efter ${FORSOK} försök" >&2
    fel=1
  fi
done
exit "${fel}"
