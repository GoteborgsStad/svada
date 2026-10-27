#!/usr/bin/env bash
# =====================================================================
# kontrollera-demo.sh – enkel upptidskontroll av den publika demon
# =====================================================================
# Hämtar demons startsida och API:t. Avslutar med 0 vid OK, annars 1 och en rad
# om vad som saknas. Körs från en ANNAN maskin eller tjänst än demoservern
# (t.ex. en gratis upptidsövervakare, eller cron på en annan dator), så att
# man märker om hela servern ligger nere. Använd:
#   bash kontrollera-demo.sh https://demo.exempel.se
# Under nattens nollställning (ca 04:00, ~10 min) svarar demon 503 med en
# underhållssida; det räknas som "nollställs", inte som fel, exit 2.
# =====================================================================
set -u
BAS="${1:?Ange demons adress, t.ex. https://demo.exempel.se}"
BAS="${BAS%/}"

SIDA="$(mktemp)"; trap 'rm -f "$SIDA"' EXIT
kod=$(curl -s -o "$SIDA" -m 15 -w '%{http_code}' "$BAS/") || kod=000
case "$kod" in
  200) ;;
  503)
    # Bara demons egen underhållssida räknas som nollställning; ett annat 503 är ett fel (del e, E10).
    if grep -q "Demon nollställs" "$SIDA"; then echo "NOLLSTÄLLS: $BAS svarar 503 (underhållssida)"; exit 2; fi
    echo "FEL: $BAS/ svarar 503 utan demons underhållssida"; exit 1 ;;
  *)   echo "FEL: $BAS/ svarar $kod"; exit 1 ;;
esac
# API:t ska svara 200 med ett JSON-objekt som har fältet nastaUtc (null eller en tid) – inte bara innehålla ordet.
akod=$(curl -s -o "$SIDA" -m 15 -w '%{http_code}' "$BAS/api/aterstallning") || akod=000
if [ "$akod" = 200 ] && python3 -c 'import json,sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if isinstance(d, dict) and "nastaUtc" in d and (d["nastaUtc"] is None or isinstance(d["nastaUtc"], str)) else 1)' "$SIDA" 2>/dev/null; then
  echo "OK: $BAS svarar, API:t lever ($(head -c 200 "$SIDA"))"
else
  echo "FEL: $BAS/api/aterstallning svarar $akod och inte med väntat JSON"; exit 1
fi
