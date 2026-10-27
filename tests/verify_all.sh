#!/usr/bin/env bash
# =====================================================================
# verify_all.sh – kör alla tests/verify_ap*.sh i ordning (hård regel 11)
# =====================================================================
# GRÖNT (exit 0) = alla etappverifieringar passerar. Annars RÖTT (exit 1).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99

# Skriver hela körningen (stdout+stderr) till en loggfil OCH till skärmen,
# så resultatet går att dela utan att klippa/klistra terminalen ihop för
# hand. Skrivs över varje körning (senaste resultatet, inte en historik) –
# git-ignorerad, inte tänkt att committas.
LOGGFIL="tests/verify-senaste-korning.log"
exec > >(tee "$LOGGFIL") 2>&1
echo "(fullständig logg för den här körningen sparas i $LOGGFIL)"

# Ett lås: två samtidiga verify_all mot samma stack skulle störa varandras jobb, avtal och återkallelser (del e, E9).
LAS="${TMPDIR:-/tmp}/svada-verify-all-$(grep -E '^SVADA_PREFIX=' .env 2>/dev/null | cut -d= -f2 | tr -d ' ').las"
if ! mkdir "${LAS}" 2>/dev/null; then
  echo "verify_all kör redan mot den här stacken (${LAS}); ta bort katalogen om en tidigare körning dog."; exit 1
fi
trap 'rmdir "${LAS}" 2>/dev/null' EXIT

shopt -s nullglob
# Portabel "natural sort": mapfile/readarray kräver bash 4+ (macOS stock
# /bin/bash är 3.2), och GNU:s sort -V finns inte i BSD/macOS sort. Bygger
# därför SCRIPTS med en klassisk while-read-loop och sorterar siffersviten
# efter "ap" nollutfylld till två tecken (decorate-sort-undecorate), så
# ap9/ap10 (om de tillkommer) hamnar rätt i stället för att sorteras som
# text. GOTCHA: ap0.sh vs ap0-portabel.sh kan byta inbördes ordning mot
# tidigare (GNU-versionens finlir för suffix) – utan betydelse, varje
# verify-script är självständigt och idempotent (se filernas headers).
# Är vi på WSL? (samma test som tests/verify_ap0-portabel.sh använder för
# att avgöra om .wslconfig-kontrollerna är tillämpliga.) Avgör HÄR vilken
# av verify_ap0.sh/verify_ap0-portabel.sh som hör hemma på den här
# maskinen - annars körs blint båda (globbet tests/verify_ap*.sh hittar
# ju båda), och du får sju "förväntade" WSL-fel i utskriften varje gång
# du kör verify_all.sh på Mac/Linux, trots att verify_ap0-portabel.sh
# redan bevisar samma egenskaper korrekt för den plattformen.
ar_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

SCRIPTS=()
while IFS= read -r rad; do
  [ -n "$rad" ] && SCRIPTS+=("$rad")
done < <(
  for f in tests/verify_ap*.sh; do
    if [ "$f" = "tests/verify_ap0.sh" ] && ! ar_wsl; then
      continue
    fi
    if [ "$f" = "tests/verify_ap0-portabel.sh" ] && ar_wsl; then
      continue
    fi
    nyckel=$(printf '%s' "$f" \
      | sed 's/ap\([0-9]\)\([^0-9]\)/ap0\1\2/; s/ap\([0-9]\)$/ap0\1/')
    printf '%s\t%s\n' "$nyckel" "$f"
  done | sort | cut -f2-
)

if [ "${#SCRIPTS[@]}" -eq 0 ]; then
  echo "INGA tests/verify_apN.sh hittades."
  exit 1
fi

# Dokument/kod-synk (konceptbiblioteket) körs SIST – regressionsskydd för
# dokumentationen, inte ett arbetspaket. Läser bara filer, kräver ingen stack.
# Se docs/koncept/README.md.
[ -f tests/verify_kedjevy.sh ] && SCRIPTS+=("tests/verify_kedjevy.sh")
[ -f tests/verify_docs.sh ] && SCRIPTS+=("tests/verify_docs.sh")

# MANIFEST (del e, fynd E3): de skript som MÅSTE köras för att sviten ska kunna kallas grön inför en publik version.
# Saknas ett, eller hoppar ett över något (raderna [HOPPAR ÖVER] / [EJ PRÖVAT] / "ej tillämpligt"), är slutstatusen RÖD:
# grönt ska betyda fullständigt prövat. VERIFY_TILLAT_HOPP=1 tillåter hopp för en snabb lokal körning (utskriften säger det).
# Medvetet UTANFÖR manifestet: tests/verify_hash_kedja.sh – dess huvudprov mixtrar med auditkedjan i testläge
# (DASH_AUDIT_KEDJA_TESTLAGE=1) och ska bara köras i en isolerad stack, aldrig i en delad demo (docs/11-verifiering.md).
# Återställningen (aterstall-demo.sh) kör bara verify_ap9.sh som hälsokontroll i rent läge; där är [EJ PRÖVAT] väntat.
MANIFEST=(tests/verify_ap1.sh tests/verify_ap3.sh tests/verify_ap4a.sh tests/verify_ap4b.sh tests/verify_ap4c.sh
          tests/verify_ap6b.sh tests/verify_ap8_fas1.sh tests/verify_ap8_fas2.sh tests/verify_ap8_fas3.sh tests/verify_ap9.sh
          tests/verify_ap10.sh tests/verify_ap11.sh tests/verify_kedjevy.sh tests/verify_docs.sh)
if ar_wsl; then MANIFEST+=(tests/verify_ap0.sh); else MANIFEST+=(tests/verify_ap0-portabel.sh); fi

FAILED=()
SAKNAS=()
HOPP=()
for m in "${MANIFEST[@]}"; do
  [ -f "$m" ] || { SAKNAS+=("$m"); FAILED+=("$m (saknas)"); }
done
SKRIPTLOGG="$(mktemp)"
for s in "${SCRIPTS[@]}"; do
  echo ""
  echo "######################################################################"
  echo "# $s"
  echo "######################################################################"
  bash "$s" 2>&1 | tee "${SKRIPTLOGG}"
  RC=${PIPESTATUS[0]}
  [ "${RC}" -eq 0 ] || FAILED+=("$s")
  if grep -Eq '\[HOPPAR ÖVER\]|\[EJ PRÖVAT\]|GRÖNT \(ej tillämpligt\)' "${SKRIPTLOGG}"; then
    HOPP+=("$s: $(grep -Eo '\[HOPPAR ÖVER\].*|\[EJ PRÖVAT\].*|GRÖNT \(ej tillämpligt\)' "${SKRIPTLOGG}" | head -2 | cut -c1-120 | tr '\n' ';')")
  fi
done
rm -f "${SKRIPTLOGG}"
if [ "${#HOPP[@]}" -gt 0 ]; then
  echo ""
  echo "HOPP OCH EJ PRÖVADE DELAR:"
  printf '  %s\n' "${HOPP[@]}"
  if [ "${VERIFY_TILLAT_HOPP:-0}" = 1 ]; then
    echo "  (VERIFY_TILLAT_HOPP=1: tillåtet i denna körning, men sviten är INTE fullständigt prövad)"
  else
    for h in "${HOPP[@]}"; do FAILED+=("${h%%:*} (hoppade över något)"); done
  fi
fi
[ "${#SAKNAS[@]}" -eq 0 ] || { echo ""; echo "SAKNADE OBLIGATORISKA SKRIPT: ${SAKNAS[*]}"; }

echo ""
echo "======================================================================"
echo "SAMMANSTÄLLNING (grönt/rött per testgrupp, med FEL-raderna för de röda)"
echo "======================================================================"
# Läser den egna loggfilen (redan skriven av tee-redirectet högst upp) i
# stället för att bygga om samma sak i bash - varje testskripts egen
# ">> NAMN: GRÖNT/RÖTT (N fel)"-slutrad (tests/lib.sh:s finish()) blir en
# rubrikrad här, och för RÖTT-block returneras även själva [FEL]-raderna,
# så att man slipper bläddra i hela loggen för att se VAD som gick fel.
# awk i stället för bash: portabelt (BSD-awk på macOS, ingen bash 4+-
# funktion), och slipper bygga om multirad-buffring i skalet.
#
# Defensiv kontroll + diagnostik (2026-09-02): en riktig, lång körning på
# en Mac visade "awk: can't open file" här trots att en isolerad
# minimaltest av EXAKT samma exec/tee/awk-mekanik fungerade felfritt - så
# felet hänger ihop med något som händer UNDER den långa körningen (många
# `bash "$s"`-anrop, mycket Docker-I/O), inte med mekaniken i sig. I
# stället för att gissa: skriv ut diagnostik om filen saknas, så nästa
# körning ger ett facit i stället för ett nytt gissningsläge.
if [ -f "$LOGGFIL" ]; then
  awk '
    { buf = buf $0 "\n" }
    /^>> / {
      status = $0
      sub(/^>> /, "", status)
      if (status ~ /RÖTT/) {
        print "✗ " status
        n = split(buf, rader, "\n")
        for (i = 1; i <= n; i++) {
          if (rader[i] ~ /\[FEL\]/) print "   " rader[i]
        }
      } else {
        print "✓ " status
      }
      buf = ""
    }
  ' "$LOGGFIL"
else
  echo "(kunde inte läsa $LOGGFIL för sammanställning - filen saknas här)"
  echo "DIAGNOSTIK: pwd=$(pwd)"
  echo "DIAGNOSTIK: ls -la tests/*.log:"
  ls -la tests/*.log 2>&1 | sed 's/^/  /'
fi
echo "======================================================================"
if [ "${#FAILED[@]}" -eq 0 ]; then
  echo "RESULTAT: GRÖNT – alla ${#SCRIPTS[@]} verifieringar passerade, inga hopp, manifestet (${#MANIFEST[@]} skript) komplett."
  exit 0
else
  echo "RESULTAT: RÖTT – misslyckade: ${FAILED[*]}"
  exit 1
fi
