#!/usr/bin/env bash
# =====================================================================
# skarmdumpar.sh – tar skärmdumparna av kontrollrummet till docs/
# =====================================================================
# Etapp 6b:s DoD kräver skärmdumpar i docs/. WSL saknar grafisk miljö, så
# bilderna tas med Windows-sidans Chrome i headless-läge (samma maskin,
# localhost når WSL genom WSL2:s portvidarebefordran).
#
#   bash tests/skarmdumpar.sh
#
# Kräver att dashboarden är uppe (profil dashboard) och att Chrome finns
# på CHROME nedan. Bilderna hamnar i docs/skarmdumpar/.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
set -a; . ./.env; set +a

CHROME="${CHROME:-/mnt/c/Program Files/Google/Chrome/Application/chrome.exe}"
UT="docs/skarmdumpar"
# Chrome är ett Windows-program och vill ha en Windows-sökväg för utdata.
WIN_TMP="C:\\Users\\${WIN_USER:-anvandare}\\AppData\\Local\\Temp"
LIN_TMP="/mnt/c/Users/${WIN_USER:-anvandare}/AppData/Local/Temp"

[ -x "${CHROME}" ] || { echo "Hittar inte Chrome: ${CHROME}"; exit 1; }
mkdir -p "${UT}"

# dump <filnamn> <höjd> <sökväg efter #>
dump() {
  local namn="$1" hojd="$2" flik="$3"
  "${CHROME}" --headless=new --disable-gpu --hide-scrollbars \
    --window-size="1280,${hojd}" --virtual-time-budget=9000 \
    --screenshot="${WIN_TMP}\\${namn}.png" \
    "http://localhost:${DASHBOARD_PORT}/#${flik}" >/dev/null 2>&1
  if [ -f "${LIN_TMP}/${namn}.png" ]; then
    mv "${LIN_TMP}/${namn}.png" "${UT}/${namn}.png"
    echo "  [OK]  ${UT}/${namn}.png ($(stat -c%s "${UT}/${namn}.png") byte)"
  else
    echo "  [FEL] ${namn} kunde inte tas"
  fi
}

echo "Tar skärmdumpar av kontrollrummet på :${DASHBOARD_PORT} ..."
dump "01-kedjan"        2600 kedjan
dump "02-auditlogg"     1500 audit
dump "03-suveranitet"   1400 suveranitet
dump "04-steg6"         2400 steg-6
dump "05-felinjektion"  1100 felinjektion
dump "06-jobb"          1000 jobb
echo "Klart."
