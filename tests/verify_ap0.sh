#!/usr/bin/env bash
# =====================================================================
# verify_ap0.sh – miljö och repo-skelett
# Prövar testfallen 0.1–0.7. Läsande/idempotent. Exit-kod = antal fel (0 = grönt).
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Miljö och repo-skelett ####"

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

section "0.3 WSL-minne konfigurerat"
# PORTABILITET (2026-07-31, inför överlämning): sökvägen
# var hårdkodad till /mnt/c/Users/anvandare/.wslconfig och blev därför automatiskt
# röd på varje annan maskin. Kravet (testfall
# 0.3) är bara "att .wslconfig innehåller memory=" – inte VEMS .wslconfig.
# Ordningen: explicit override → Windows egen USERPROFILE → enda träffen under
# /mnt/c/Users/ → den ursprungliga sökvägen som sista fallback.
hitta_wslconfig() {
  if [ -n "${WSLCONFIG_SOKVAG:-}" ]; then echo "$WSLCONFIG_SOKVAG"; return; fi
  local profil sokvag
  # cmd.exe måste köras från en Windows-synlig katalog, annars varnar den och
  # byter till C:\. Utdata är CRLF-terminerat.
  profil=$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r\n')
  if [ -n "$profil" ] && sokvag=$(wslpath -u "$profil" 2>/dev/null) && [ -d "$sokvag" ]; then
    echo "${sokvag}/.wslconfig"; return
  fi
  local f
  for f in /mnt/c/Users/*/.wslconfig; do
    [ -f "$f" ] && { echo "$f"; return; }
  done
  echo /mnt/c/Users/anvandare/.wslconfig
}
WSLCONFIG=$(hitta_wslconfig)
MEMGB=$(free -g | awk '/^Mem:/{print $2}')
if [ "${MEMGB:-0}" -ge 18 ]; then
  ok "0.3 WSL total RAM ${MEMGB} GiB (>=18 → ~konfigurerat 20GB)"
else
  no "0.3 WSL total RAM ${MEMGB} GiB (<18 → .wslconfig ej applicerad?)"
fi
if grep -Eq '^memory=' "$WSLCONFIG" 2>/dev/null; then
  ok "0.3 $WSLCONFIG innehåller memory="
else
  no "0.3 $WSLCONFIG saknar memory= (eller oläsbar)"
fi

section "0.4 Repo-struktur"
# De styrande dokumenten är docs/01-oversikt.md (arkitekturen) och
# docs/11-verifiering.md (testsviten), med docs/README.md som ingång.
for f in compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml .env \
         docs/README.md docs/01-oversikt.md docs/11-verifiering.md; do
  if [ -f "$f" ]; then ok "0.4 finns: $f"; else no "0.4 saknas: $f"; fi
done

section "0.5 Testdata på plats"
GPKG_SZ=$(stat -c%s "data/dbsvadaexample.gpkg" 2>/dev/null || echo 0)
if [ "$GPKG_SZ" -gt 102400 ]; then ok "0.5 gpkg ${GPKG_SZ} B (>100 kB)"; else no "0.5 gpkg för liten/saknas (${GPKG_SZ} B)"; fi
for csv in "data/Weir_4526-Discharge_0_5_000.csv" "data/Weir_4526-Spill, Transport_0_5_000.csv"; do
  SZ=$(stat -c%s "$csv" 2>/dev/null || echo 0)
  if [ "$SZ" -gt 10240 ]; then ok "0.5 CSV ${SZ} B (>10 kB): $(basename "$csv")"; else no "0.5 CSV för liten/saknas: $csv"; fi
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
COMMITS=$(git log --oneline 2>/dev/null | wc -l)
if [ "${COMMITS:-0}" -ge 1 ]; then ok "0.7 git: ${COMMITS} commit(ar)"; else no "0.7 inga git-commits"; fi

section "Testberoenden"
# curl, jq och python3 ska finnas.
for t in curl jq python3 git; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "§1.5 $t finns"
  else
    no "§1.5 $t SAKNAS (behövs av verify_ap1/ap2)"
  fi
done

# ---------------------------------------------------------------------
# Extra kontroller (utöver kontraktet – höjer förtroendet)
# ---------------------------------------------------------------------
section "Extra: compose-filer parsar (rule 10)"
for f in compose.dhi.yml compose.stad.yml compose.kontrollrum.yml compose.dsga.yml; do
  if docker compose -f "$f" config >/dev/null 2>&1; then ok "extra: $f parsar"; else no "extra: $f parsar EJ"; fi
done

section "Extra: WSL-nätverksläge (inneslutning)"
# VARFÖR: compose-filerna publicerar samtliga portar utan lyssnaradress,
# så Docker binder dem till 0.0.0.0 inne i WSL-burken. I WSL:s STANDARDLÄGE
# (NAT) stoppas det av Windows – bara den egna maskinen kommer in, vilket
# är hela premissen för att PoC:en får köra utan autentisering.
#
# I `networkingMode=mirrored` gäller INTE det: WSL speglar då värdens
# nätverkskort, och 0.0.0.0-bindningarna blir nåbara från kontorsnätet.
# Då ligger bl.a. Orion-LD på 1026 öppen UTAN lösenord – med Distribution
# A:s fullständiga brunns-GIS, det som enligt hård regel 8 aldrig får
# spridas. Bindningen kan inte flyttas till 127.0.0.1 utan att dashboarden
# och FAIR-tjänsten slutar fungera (de observerar kedjan utifrån via
# host.docker.internal, services/dashboard/kallor.py §29) – därför denna
# kontroll i stället.
#
# $WSLCONFIG är redan uppslagen i 0.3 ovan (samma portabla sökordning).
if [ -r "$WSLCONFIG" ]; then
  if grep -Eqi '^[[:space:]]*networkingMode[[:space:]]*=[[:space:]]*mirrored' "$WSLCONFIG"; then
    no "extra: WSL kör i MIRRORED-läge – hela kedjan exponeras mot nätverket du sitter på"
    echo "        Åtgärd: ta bort networkingMode=mirrored ur $WSLCONFIG"
    echo "        och kör 'wsl --shutdown' från Windows."
  else
    ok "extra: WSL i NAT-läge (inget networkingMode=mirrored i .wslconfig)"
  fi
else
  # Oläsbar .wslconfig är inte ett fel i sig (0.3 fäller den saknade filen),
  # men inneslutningen går då inte att bevisa – säg det rakt ut.
  no "extra: kan inte läsa $WSLCONFIG – WSL:s nätverksläge går inte att verifiera"
fi

section "Extra: gpkg-integritet (md5) + systemd"
EXPECT_MD5=153abe5fee86ecc97d4e8fb8c027b47f
GOT_MD5=$(md5sum "data/dbsvadaexample.gpkg" 2>/dev/null | awk '{print $1}')
if [ "$GOT_MD5" = "$EXPECT_MD5" ]; then ok "extra: gpkg md5 = $EXPECT_MD5"; else no "extra: gpkg md5 avviker: ${GOT_MD5:-saknas}"; fi
if systemctl is-system-running 2>/dev/null | grep -qE "running|degraded"; then ok "extra: systemd kör"; else no "extra: systemd kör ej"; fi

finish "verify_ap0"
