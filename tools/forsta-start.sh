#!/usr/bin/env bash
# Första steget i en nyklonad kopia: skapar .env ur .env.exempel och slumpar fram hemligheterna (nycklar, lösenord, token) samt
# lösenordsgrindens lösenord. Skriver ALDRIG ut hemligheterna. Kör därefter: bash starta-demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  echo ".env finns redan: den lämnas orörd (radera den för att börja om)."
else
  cp .env.exempel .env
  bash tools/nya-hemligheter.sh .env | grep -v '^Klart. Kör nu aterstall-demo.sh'    # den raden gäller en redan startad server, inte en första start
  # På Linux (Docker Engine) når containrarna värden via bryggans adress, inte via 127.0.0.1 (det gör de bara i Docker Desktop på Mac och
  # Windows). Kontrollrummet och Caddy går över värdens portar, så värdportarna måste ligga på bryggans adress, annars blir allt
  # "anslutningsfel". Gäller bara en ny .env; en befintlig lämnas orörd.
  if [ "$(uname -s)" = "Linux" ]; then
    BRYGGA="$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || true)"
    if [ -n "${BRYGGA}" ]; then
      sed -i "s/^VARD_BIND_IP=.*/VARD_BIND_IP=${BRYGGA}/" .env
      echo "Linux: värdportarna binds till Docker-bryggans adress ${BRYGGA} (VARD_BIND_IP i .env)."
    else
      echo "VARNING: hittade inte Docker-bryggans adress. Sätt VARD_BIND_IP i .env till den (vanligen 172.17.0.1) innan du startar." >&2
    fi
  fi
  echo "Skapade .env med nya slumpade hemligheter. Lösenord för proxyn (http://svada-demo.localhost:38080) finns i .demo-losenord."
fi
echo "Nästa steg: bash starta-demo.sh"
