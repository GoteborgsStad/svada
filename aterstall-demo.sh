#!/usr/bin/env bash
# =====================================================================
# aterstall-demo.sh – nattlig återställning av den PUBLIKA demon
# =====================================================================
# Besökare driver kedjan med kontrollrummets knappar (förhandlingar,
# KoV-beslut, avvikelser, felinjektioner). Varje natt återställs allt till
# ett rent utgångsläge, så att nästa dags besökare börjar från början:
#
#   1. Kontrollrummet stoppas och tas bort (audit- och KoV-logg lever i minnet
#      och nollställs). Caddy står KVAR och visar en underhållssida medan
#      resten byggs om; dess volymer (TLS-certifikat) behålls i vilket fall
#      – Let's Encrypt har utfärdandegränser.
#   2. Staden och DHI: "down -v". Brunnar, tidsserier, katalog och
#      connectorernas tillstånd raderas.
#   3. Den delade attestvolymen (vc-utbyte) raderas; den skapas om vid start.
#   4. starta-demo.sh bygger upp kedjan igen; verify_ap9.sh kontrollerar
#      att de publika ingångarna fungerar.
#
# SKYDD: vägrar köra med prefixet "svada" (originalet), så att skriptet
# aldrig kan radera originalstackens data på en maskin där båda finns.
#
# Schemaläggs på servern: nattligen kl. 04:00 (cron) och
# efter varje Docker-start (svada-aterstall.service). Båda tar samma lås så att två
# återställningar aldrig kör samtidigt:
#   0 4 * * * /usr/bin/flock -n /run/svada-aterstall.lock /opt/svada-demo/aterstall-demo.sh >>/var/log/svada-aterstall.log 2>&1
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a

P="${SVADA_PREFIX:-svada}"
if [ "${P}" = "svada" ]; then
  echo "VÄGRAR: SVADA_PREFIX är '${P}' (originalet). Återställningen raderar"
  echo "volymer och får bara köras mot den publika demon."
  exit 1
fi

echo "== $(date '+%F %T') Återställer den publika demon (prefix ${P}) =="

echo "== 1. Kontrollrummet (Caddy står kvar med underhållssida) =="
docker compose -f compose.kontrollrum.yml --profile dashboard stop dashboard
docker compose -f compose.kontrollrum.yml --profile dashboard rm -f dashboard

echo "== 2. Staden och DHI (volymer raderas) =="
docker compose -f compose.stad.yml --profile stad-dataplan --profile stad-identitet \
  --profile stad-edc --profile stad-ingest down -v
docker compose -f compose.dhi.yml --profile dhi-fcf \
  --profile dhi-identitet --profile dhi-edc down -v

echo "== 2b. Svadas utfärdare (DSGA 0.1) =="
docker compose -f compose.dsga.yml --profile dsga-utfardare down

echo "== 3. Delad attestvolym =="
docker volume rm "${P}-vc-utbyte" >/dev/null 2>&1 && echo "  ${P}-vc-utbyte raderad" \
  || echo "  (fanns inte)"

echo "== 4. Bygger upp kedjan igen =="
# Ett fel här får inte passera tyst: utan slutraden nedan syns det inte i
# loggen att natten gick snett (hände 2026-10-06).
if ! bash starta-demo.sh; then
  echo "== $(date '+%F %T') Återställning MISSLYCKADES i uppbyggnaden – demon är ofullständig. Kör aterstall-demo.sh igen. =="
  exit 1
fi

echo "== 5. Kontroll av de publika ingångarna =="
# CKAN och skördarna behöver en stund efter en kallstart.
sleep 30
if bash tests/verify_ap9.sh; then
  echo "== $(date '+%F %T') Återställning klar: GRÖNT =="
else
  echo "== $(date '+%F %T') Återställning klar men verify_ap9 är RÖTT – se ovan =="
  exit 1
fi
