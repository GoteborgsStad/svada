#!/usr/bin/env bash
# =====================================================================
# aterstall-med-forsok.sh – nattens återställning med ETT nytt försök
# =====================================================================
# Kör aterstall-demo.sh. Misslyckas den (t.ex. en kallstart som hakar upp
# sig) väntar vi PAUS_S sekunder (standard 600 = 10 min) och kör den en gång
# till. Fler försök görs inte: ett tredje skulle bara dölja ett verkligt fel.
# Slutstatus = det sista försökets. Anropas under flock (cron/systemd).
#   ATERSTALL_SKRIPT och PAUS_S kan överstyras för test (se tests/aterstall_forsok.sh).
# =====================================================================
set -u
HIT="$(cd "$(dirname "$0")/../.." && pwd)"
SKRIPT="${ATERSTALL_SKRIPT:-$HIT/aterstall-demo.sh}"
PAUS_S="${PAUS_S:-600}"

if bash "$SKRIPT"; then
  exit 0
fi
echo "== $(date '+%F %T') Försök 1 misslyckades – väntar ${PAUS_S} s och försöker en gång till =="
sleep "$PAUS_S"
if bash "$SKRIPT"; then
  echo "== $(date '+%F %T') Försök 2 lyckades =="
  exit 0
fi
echo "== $(date '+%F %T') Försök 2 misslyckades – kräver manuell åtgärd =="
exit 1
