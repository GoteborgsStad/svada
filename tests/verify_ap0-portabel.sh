#!/usr/bin/env bash
# =====================================================================
# verify_ap0-portabel.sh – miljö och repo-skelett, portabel variant (WSL / Linux / macOS)
#
# Skillnad mot tests/verify_ap0.sh: de fyra kontroller som antog Linux/WSL
# är omskrivna att MÄTA FÖRMÅGAN i stället för att fråga VEM värden är.
# Samma egenskaper bevisas; de bara bevisas plattformsoberoende.
#
#   0.3 minne     free -g            -> docker info --format {{.MemTotal}}
#                                       (daemonens minne, korrekt även på
#                                        Docker Desktop där free-g ljuger)
#   0.3 .wslconfig cmd.exe/wslpath   -> körs BARA på WSL; annars n/a
#   0.5 filstorlek stat -c%s (GNU)   -> wc -c (POSIX, funkar på BSD/mac)
#   nätläge        mirrored i wslcfg -> körs BARA på WSL; annars n/a
#   systemd        systemctl         -> körs BARA om systemctl finns
#
# Kör:  bash tests/verify_ap0-portabel.sh
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

# Är vi på WSL? (Windows-integrationen finns bara då.)
ar_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

echo "#### Miljö och repo-skelett (portabel variant) ####"

section "0.1 Docker fungerar"
if docker run --rm hello-world 2>/dev/null | grep -qi "working correctly"; then
  ok "0.1 docker run --rm hello-world (exit 0)"
else
  no "0.1 docker run hello-world misslyckades"
fi

section "0.2 Compose v2 finns"
CV=$(docker compose version --short 2>/dev/null)
CV_MAJOR=${CV%%.*}
if [ -n "$CV" ] && [ "${CV_MAJOR:-0}" -ge 2 ] 2>/dev/null; then
  ok "0.2 docker compose $CV (major >= 2)"
else
  no "0.2 docker compose saknas eller version < 2 (fick: '${CV:-inget}')"
fi

section "0.3 Minne tillgängligt för containrarna"
# PORTABELT: fråga DAEMONEN, inte värdskalet. På WSL med Engine sammanfaller
# de; på Docker Desktop gör de inte det, och då är daemonens siffra den
# enda som betyder något för mem_limit. free -g finns dessutom inte på macOS.
# Golvet är 7 GiB (var 18 GiB): det är vad hela kedjan bevisat räcker med. Den publika
# demoservern kör alla tjänster på 8 GB RAM (Docker ser ca 7,5 GiB) och Macen ger Docker
# 10 GiB. 18 GiB gäller WSL-installationen på Windows (tests/verify_ap0.sh),
# där bygget, Docker och Ubuntu delar samma minne.
MIN_GIB=7
MEM_BYTES=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
MEMGB=$(( MEM_BYTES / 1024 / 1024 / 1024 ))
if [ "${MEMGB:-0}" -ge "${MIN_GIB}" ]; then
  ok "0.3 Docker-daemonen ser ${MEMGB} GiB (>=${MIN_GIB})"
else
  no "0.3 Docker-daemonen ser ${MEMGB} GiB (<${MIN_GIB} – höj minnet i Docker Desktop → Resources)"
fi
# .wslconfig-kontrollen är WSL-specifik. På annan plattform finns ingen
# sådan fil, och minnet konfigureras på annat sätt (redan mätt ovan).
if ar_wsl; then
  hitta_wslconfig() {
    if [ -n "${WSLCONFIG_SOKVAG:-}" ]; then echo "$WSLCONFIG_SOKVAG"; return; fi
    local profil sokvag f
    profil=$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r\n')
    if [ -n "$profil" ] && sokvag=$(wslpath -u "$profil" 2>/dev/null) && [ -d "$sokvag" ]; then
      echo "${sokvag}/.wslconfig"; return
    fi
    for f in /mnt/c/Users/*/.wslconfig; do [ -f "$f" ] && { echo "$f"; return; }; done
    echo ""
  }
  WSLCONFIG=$(hitta_wslconfig)
  if [ -n "$WSLCONFIG" ] && grep -Eq '^memory=' "$WSLCONFIG" 2>/dev/null; then
    ok "0.3 $WSLCONFIG innehåller memory="
  else
    no "0.3 .wslconfig med memory= hittades inte (${WSLCONFIG:-ingen sökväg})"
  fi
else
  WSLCONFIG=""
  ok "0.3 .wslconfig ej tillämpligt på denna plattform (minnet mätt mot daemonen ovan)"
fi

section "0.4 Repo-struktur"
for f in compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml .env \
         docs/README.md docs/01-oversikt.md docs/11-verifiering.md; do
  if [ -f "$f" ]; then ok "0.4 finns: $f"; else no "0.4 saknas: $f"; fi
done

section "0.5 Testdata på plats"
# PORTABELT: wc -c i stället för stat -c%s. GNU:s -c%s finns inte på BSD/mac
# (där heter det stat -f%z), och det gamla anropet föll tyst tillbaka på 0 –
# ett falskt negativt som anklagade testdatat. wc -c är POSIX och läser
# filen direkt, så resultatet är detsamma överallt.
filstorlek() { wc -c < "$1" 2>/dev/null | tr -d ' ' || echo 0; }
GPKG_SZ=$(filstorlek "data/dbsvadaexample.gpkg")
if [ "${GPKG_SZ:-0}" -gt 102400 ]; then ok "0.5 gpkg ${GPKG_SZ} B (>100 kB)"; else no "0.5 gpkg för liten/saknas (${GPKG_SZ} B)"; fi
for csv in "data/Weir_4526-Discharge_0_5_000.csv" "data/Weir_4526-Spill, Transport_0_5_000.csv"; do
  SZ=$(filstorlek "$csv")
  if [ "${SZ:-0}" -gt 10240 ]; then ok "0.5 CSV ${SZ} B (>10 kB): $(basename "$csv")"; else no "0.5 CSV för liten/saknas: $csv"; fi
done

section "0.6 Inga rörliga taggar (:latest)"
if grep -Rq ':latest' compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml .env 2>/dev/null; then
  no "0.6 hittade ':latest' i compose.*.yml/.env (rule 4)"
  grep -Rn ':latest' compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml .env 2>/dev/null | sed 's/^/        /'
else
  ok "0.6 inga ':latest'-träffar i compose.*.yml/.env"
fi

# 0.6b Varje image-referens (FROM, image:, *_IMAGE), med variabler lösta: uttrycklig tagg, aldrig latest (del e, E14).
TAGGAR="$(python3 tests/bildtaggar.py)"
case "${TAGGAR}" in
  OK*) ok "0.6b alla ${TAGGAR#OK } image-referenser har en uttrycklig tagg (ingen latest, ingen taggfri)" ;;
  *) while read -r r; do no "0.6b ${r}"; done <<<"${TAGGAR}" ;;
esac

section "0.7 Git initierat"
COMMITS=$(git log --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "${COMMITS:-0}" -ge 1 ]; then ok "0.7 git: ${COMMITS} commit(ar)"; else no "0.7 inga git-commits"; fi

section "Testberoenden (verifiering.md §1.5)"
for t in curl jq python3 git; do
  if command -v "$t" >/dev/null 2>&1; then ok "§1.5 $t finns"; else no "§1.5 $t SAKNAS (behövs av verify_ap1/ap2)"; fi
done

section "Extra: compose-filer parsar (rule 10)"
for f in compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml; do
  if docker compose -f "$f" config >/dev/null 2>&1; then ok "extra: $f parsar"; else no "extra: $f parsar EJ"; fi
done

section "Extra: inneslutning (WSL-nätverksläge)"
# WSL: den farliga inställningen är networkingMode=mirrored i .wslconfig.
# Annan plattform: egenskapen som ska gälla är att kedjan inte är nåbar
# från nätverket du sitter på. Vi mäter den direkt i stället för att leta
# efter en WSL-specifik orsak: nå en publicerad port via värdens LAN-IP.
if ar_wsl; then
  if [ -n "${WSLCONFIG:-}" ] && [ -r "$WSLCONFIG" ]; then
    if grep -Eqi '^[[:space:]]*networkingMode[[:space:]]*=[[:space:]]*mirrored' "$WSLCONFIG"; then
      no "extra: WSL kör i MIRRORED-läge – hela kedjan exponeras mot nätverket du sitter på"
      echo "        Åtgärd: ta bort networkingMode=mirrored ur $WSLCONFIG och kör wsl --shutdown."
    else
      ok "extra: WSL i NAT-läge (inget networkingMode=mirrored)"
    fi
  else
    ok "extra: ingen .wslconfig – WSL:s standardläge är NAT (innesluten)"
  fi
else
  # Direkt förmågeprov: svarar en publicerad port på värdens LAN-IP?
  ORION_P="${ORION_STAD_PORT:-2026}"
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
           || ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
  if [ -z "$LAN_IP" ]; then
    ok "extra: ingen LAN-IP hittad – inget att exponera (innesluten)"
  elif curl -s --max-time 3 "http://${LAN_IP}:${ORION_P}/ngsi-ld/ex/v1/version" >/dev/null 2>&1; then
    no "extra: kedjan svarar på ${LAN_IP}:${ORION_P} – exponerad mot nätverket du sitter på"
  else
    ok "extra: ingen tjänst svarar på ${LAN_IP}:${ORION_P} (innesluten)"
  fi
fi

section "Extra: gpkg-integritet (md5) + systemd"
EXPECT_MD5=153abe5fee86ecc97d4e8fb8c027b47f
# md5sum finns på Linux och via Homebrew coreutils; macOS eget verktyg är md5.
if command -v md5sum >/dev/null 2>&1; then
  GOT_MD5=$(md5sum "data/dbsvadaexample.gpkg" 2>/dev/null | awk '{print $1}')
elif command -v md5 >/dev/null 2>&1; then
  GOT_MD5=$(md5 -q "data/dbsvadaexample.gpkg" 2>/dev/null)
else
  GOT_MD5=""
fi
if [ "$GOT_MD5" = "$EXPECT_MD5" ]; then ok "extra: gpkg md5 = $EXPECT_MD5"; else no "extra: gpkg md5 avviker: ${GOT_MD5:-inget md5-verktyg}"; fi
# systemd är en Linux-init. Docker-hälsan är redan bevisad i 0.1; kontrollera
# bara systemd där det över huvud taget är relevant.
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-system-running 2>/dev/null | grep -qE "running|degraded"; then ok "extra: systemd kör"; else no "extra: systemd kör ej"; fi
else
  ok "extra: systemd ej tillämpligt på denna plattform (Docker bevisad i 0.1)"
fi

finish "verify_ap0-portabel"
