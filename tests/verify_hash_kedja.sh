#!/usr/bin/env bash
# tests/verify_hash_kedja.sh – hash-kedjan ("enkla
# varianten") i services/dashboard/audit.py.
#
# Vad det här testet FAKTISKT visar (och inte mer):
#   1. Att /api/audit ger en hash-kedja vars länkar hänger ihop (INTAKT)
#      under normal drift.
#   2. Att /api/audit/kedja säger samma sak fristående.
#   3. Att hash_kedja_kontrollera() FAKTISKT larmar (INTAKT=false) när en
#      lagrad länk mixtras med – annars vore "intakt: true" bara en text
#      som alltid råkar stå där, aldrig prövad.
#
# Punkt 3 kräver att dashboard-containern körs med
# DASH_AUDIT_KEDJA_TESTLAGE=1 i miljön (annars svarar test-mixtra-endpointen
# 404, med flit – se main.py). Testet upptäcker det självt och hoppar då
# bara över punkt 3 med en tydlig TEXT, i stället för att räknas som rött.
#
# VAD DET INTE VISAR: att kedjan överlever en omstart (den gör det inte,
# se STOR RESERVATION i audit.py),
# och inte heller att någon av de sex UNDERLIGGANDE källorna är
# manipulationssäker – bara dashboardens egen, redan hämtade, vy av dem.

set -uo pipefail

# Portkartan kan vara förskjuten (publik demo, SVADA_PREFIX) – läs .env.
[ -f "$(dirname "$0")/../.env" ] && { set -a; . "$(dirname "$0")/../.env"; set +a; }
BAS="${DASH_URL:-http://localhost:${DASHBOARD_PORT:-8800}}"
ANTAL_OK=0
ANTAL_FEL=0

ok() { echo "  [OK]  $1"; ANTAL_OK=$((ANTAL_OK + 1)); }
no() { echo "  [FEL] $1"; ANTAL_FEL=$((ANTAL_FEL + 1)); }

echo "=== verify_hash_kedja.sh mot $BAS ==="

# --- 0. Vänta in att containern faktiskt tar emot anslutningar. Direkt
#        efter "docker compose up -d" kan uvicorn hinna starta lyssna
#        innan appen är helt klar - ett enda curl precis då ger
#        "Connection reset by peer", vilket INTE är ett kodfel, bara
#        dålig timing. Ge den upp till ~10 sekunder innan vi ger upp.
KLAR=0
for i in 1 2 3 4 5; do
  if curl -fsS -o /dev/null "$BAS/api/audit" 2>/dev/null; then
    KLAR=1
    break
  fi
  sleep 2
done
if [ "$KLAR" -ne 1 ]; then
  no "0. dashboarden svarar inte på $BAS/api/audit efter flera försök - kör 'docker compose ps' och kolla loggarna"
  echo "=== SAMMANSTÄLLNING: $ANTAL_OK OK, $ANTAL_FEL FEL ==="
  exit 1
fi

# --- 1. Bygg upp lite kedja genom att faktiskt anropa /api/audit två
#        gånger (dedupen ska göra det andra anropet en no-op för redan
#        sedda händelser, men kedjan ska ändå rapportera minst en länk om
#        auditloggen inte är helt tom).
AUDIT1=$(curl -fsS "$BAS/api/audit") || { no "första /api/audit-anropet misslyckades"; exit 1; }
sleep 1
AUDIT2=$(curl -fsS "$BAS/api/audit") || { no "andra /api/audit-anropet misslyckades"; exit 1; }

ANTAL1=$(echo "$AUDIT1" | jq -r '.kedja.antalLankar // 0')
INTAKT1=$(echo "$AUDIT1" | jq -r '.kedja.intakt // false')
ANTAL2=$(echo "$AUDIT2" | jq -r '.kedja.antalLankar // 0')
INTAKT2=$(echo "$AUDIT2" | jq -r '.kedja.intakt // false')

if [ "$INTAKT1" = "true" ]; then
  ok "1. kedjan är intakt efter första /api/audit ($ANTAL1 länkar)"
else
  no "1. kedjan rapporterar sig INTE intakt redan från start: $(echo "$AUDIT1" | jq -c '.kedja')"
fi

if [ "$ANTAL2" -ge "$ANTAL1" ] 2>/dev/null; then
  ok "2. kedjan växer aldrig baklänges mellan två anrop ($ANTAL1 -> $ANTAL2 länkar)"
else
  no "2. kedjans länkantal minskade mellan anropen ($ANTAL1 -> $ANTAL2) - dedupen är trasig"
fi

if [ "$INTAKT2" = "true" ]; then
  ok "3. kedjan är fortfarande intakt efter andra /api/audit"
else
  no "3. kedjan blev TRASIG av bara två normala /api/audit-anrop: $(echo "$AUDIT2" | jq -c '.kedja')"
fi

# --- 4. Samma sak, men mot den fristående /api/audit/kedja-endpointen.
FRISTAENDE=$(curl -fsS "$BAS/api/audit/kedja") || { no "4. /api/audit/kedja svarade inte"; exit 1; }
if [ "$(echo "$FRISTAENDE" | jq -r '.intakt // false')" = "true" ]; then
  ok "4. /api/audit/kedja (fristående) säger också INTAKT"
else
  no "4. /api/audit/kedja säger något annat än /api/audit gjorde: $(echo "$FRISTAENDE" | jq -c '.')"
fi

# --- 5. Bevis på att detektionen FAKTISKT fungerar – kräver testläge.
TESTLAGE_SVAR=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BAS/api/audit/kedja/test-mixtra/0")
if [ "$TESTLAGE_SVAR" = "404" ]; then
  echo "  [INFO] 5. testläge (DASH_AUDIT_KEDJA_TESTLAGE=1) är inte påslaget på $BAS -"
  echo "         hoppar över det faktiska manipulations-beviset. Det är EXPECTED för"
  echo "         alla riktiga uppsättningar - sätt env-"
  echo "         variabeln bara i en engångskörning för att pröva punkt 5."
elif [ "$ANTAL2" -lt 1 ]; then
  echo "  [INFO] 5. kedjan har 0 länkar - inget att mixtra med. Kör om testet efter"
  echo "         att ha utlöst minst en riktig händelse (t.ex. en avtalsförhandling)."
else
  MIXTRAT=$(curl -fsS -X POST "$BAS/api/audit/kedja/test-mixtra/0")
  EFTER=$(curl -fsS "$BAS/api/audit/kedja")
  if [ "$(echo "$EFTER" | jq -r '.intakt // true')" = "false" ]; then
    ok "5. efter avsiktlig mixtring med länk 0 rapporterar kedjan TRASIG, som den ska: $(echo "$EFTER" | jq -c '.')"
  else
    no "5. mixtrade med länk 0 ($(echo "$MIXTRAT" | jq -c '.')) men kedjan säger ändå INTAKT - detektionen fungerar INTE"
  fi
  echo "  [VARNING] dashboardens hash-kedja är nu MEDVETET trasig i minnet (testläge)."
  echo "            starta om dashboard-containern innan något annat litar på den."
fi

echo "=== SAMMANSTÄLLNING: $ANTAL_OK OK, $ANTAL_FEL FEL ==="
[ "$ANTAL_FEL" -eq 0 ]
