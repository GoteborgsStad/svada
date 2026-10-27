#!/usr/bin/env bash
# =====================================================================
# verify_docs.sh – dokument/kod-synk för konceptbiblioteket
# =====================================================================
# Skyddar samma sak för dokumentationen som verify_ap*.sh gör för
# invarianterna: att manual, demo, konceptdokument och kod inte glider
# isär obemärkt. Se docs/koncept/README.md.
#
# Kontroller:
#   A. Varje KONCEPT-ankare i koden pekar på ett dokument som finns.
#   B. Varje konceptdokument (NN-*.md) är måltavla för minst ett ankare.
#   C. Varje konceptdokument hänvisar till minst ett verify-script som finns.
#   D. Kodhänvisningar i konceptdokumenten upplöses (filen/mappen finns).
#   E. Maskinellt låsta termer (<!-- SYNK ... -->) förekommer i koden.
#
# Idempotent, läser bara filer – startar inga containrar.
# OBS: alla loopar körs i HUVUDSKALET (process substitution < <(...) eller
# for-in-$()) så att lib.sh:s FAIL-räknare inte nollställs i en pipe-subshell.
# =====================================================================
set -uo pipefail
. "$(dirname "$0")/lib.sh"
ROOT="$(repo_root)"
cd "$ROOT"

KONCEPT_DIR="docs/koncept"
# Rötter där kodhänvisningar (D) och SYNK-strängar (E) får bo.
KOD_ROTTER="services edc tests data identity-hub compose.dhi.yml compose.stad.yml compose.dsga.yml compose.kontrollrum.yml .env"
# E (låsta termer) söker bara i PRODUKTIONSKOD: en gammal förväntan i ett test ska inte kunna hålla en term vid liv
# efter att implementationen bytt namn (del e, E12).
KOD_ROTTER_E="services edc data identity-hub compose.dhi.yml compose.stad.yml compose.dsga.yml compose.kontrollrum.yml .env"

# Alla KONCEPT-ankare i koden -> unika dokumentsökvägar de pekar på.
ANKARDOCS="$(grep -rIn --exclude-dir=upstream --exclude-dir=vendor \
              "KONCEPT: ${KONCEPT_DIR}/" services edc identity-hub tests 2>/dev/null \
            | sed -E 's|.*KONCEPT: (docs/koncept/[A-Za-z0-9._-]+\.md).*|\1|' \
            | sort -u)"

# ---------------------------------------------------------------------
section "A. KONCEPT-ankare pekar på dokument som finns"
# ---------------------------------------------------------------------
if [ -z "$ANKARDOCS" ]; then
  no "A inga KONCEPT-ankare hittades i koden"
else
  for doc in $ANKARDOCS; do
    if [ -f "$doc" ]; then ok "A ankare -> $doc finns"
    else no "A ankare pekar på saknat dokument: $doc"; fi
  done
fi

# ---------------------------------------------------------------------
section "B. Varje konceptdokument är ankrat från koden"
# ---------------------------------------------------------------------
shopt -s nullglob
KONCEPTDOK=()
for _d in "$KONCEPT_DIR"/*.md; do
  [ "$(basename "$_d")" = "README.md" ] && continue   # navet, inget koncept
  KONCEPTDOK+=("$_d")
done
if [ "${#KONCEPTDOK[@]}" -eq 0 ]; then
  no "B inga NN-*.md konceptdokument hittades"
fi
for doc in "${KONCEPTDOK[@]}"; do
  if grep -qxF "$doc" <<<"$ANKARDOCS"; then
    ok "B $doc har minst ett kod-ankare"
  else
    no "B $doc saknar KONCEPT-ankare i koden (lägg 'KONCEPT: $doc' i primärfilen)"
  fi
done

# ---------------------------------------------------------------------
section "C. Konceptdokument hänvisar till ett verify-script som finns"
# ---------------------------------------------------------------------
for doc in "${KONCEPTDOK[@]}"; do
  hittad=0
  while read -r t; do
    [ -n "$t" ] && [ -f "$t" ] && hittad=1
  done < <(grep -oE 'tests/verify_[A-Za-z0-9._-]+\.sh' "$doc" | sort -u)
  if [ "$hittad" -eq 1 ]; then
    ok "C $(basename "$doc") hänvisar till ett verify-script som finns"
  else
    no "C $(basename "$doc") saknar giltig tests/verify_*.sh-hänvisning (avsnitt Bevis)"
  fi
done

# ---------------------------------------------------------------------
section "D. Kodhänvisningar i konceptdokumenten upplöses"
# ---------------------------------------------------------------------
D_FEL=0
for doc in "${KONCEPTDOK[@]}"; do
  while read -r p; do
    [ -n "$p" ] || continue
    p="${p%.}"          # trimma en avslutande mening-punkt (ingen fil slutar på .)
    if [ ! -e "$p" ]; then
      no "D $(basename "$doc"): hänvisning till saknad sökväg '$p'"
      D_FEL=$((D_FEL+1))
    fi
  # BSD/macOS grep saknar -P (PCRE) och därmed negativa lookbehinds.
  # Samma två-stegs-knep som sektion F: greppa MED ett kant-tecken (radstart
  # eller ett tecken som INTE är bokstav/siffra/understreck/snedstreck/punkt/
  # bindestreck) och skala sedan bort det kant-tecknet, i stället för
  # (?<![\w/.]). Bindestrecket måste vara med i kant-klassen (till skillnad
  # från ursprungets \w/.) annars matchar t.ex. "eclipse-edc/Connector"
  # (en GitHub-organisation, inte en sökväg i det här repot) som om det vore
  # en lokal edc/-sökväg.
  done < <(grep -oE "(^|[^A-Za-z0-9_/.-])(services|edc|tests)/[A-Za-z0-9._/-]+" "$doc" \
           | grep -oE "(services|edc|tests)/[A-Za-z0-9._/-]+" | sort -u)
done
[ "$D_FEL" -eq 0 ] && ok "D alla kodhänvisningar i konceptdokumenten upplöstes"

# ---------------------------------------------------------------------
section "E. Maskinellt låsta termer förekommer i koden"
# ---------------------------------------------------------------------
ORDLISTA="docs/13-ordlista.md"
if [ ! -f "$ORDLISTA" ]; then
  no "E $ORDLISTA saknas"
else
  while read -r rad; do
    [ -n "$rad" ] || continue
    term="$(sed -E 's/.*term="([^"]*)".*/\1/' <<<"$rad")"
    strang="$(sed -E 's/.*strang="([^"]*)".*/\1/' <<<"$rad")"
    if grep -rIqF --exclude-dir=upstream --exclude-dir=vendor "$strang" $KOD_ROTTER_E 2>/dev/null; then
      ok "E term '$term' -> '$strang' finns i koden"
    else
      no "E term '$term' -> '$strang' HITTAS INTE i koden (drift?)"
    fi
  done < <(grep -oE 'SYNK: term="[^"]*" strang="[^"]*"' "$ORDLISTA")
fi

# ---------------------------------------------------------------------
section "F. Dokumentsökvägar i repot upplöses"
# ---------------------------------------------------------------------
# TILLKOM vid docs-v4-omstuvningen (2026-07-30). Omstuvningen visade att
# döda docs/-sökvägar kan ligga kvar länge i kodkommentarer, compose-filer
# och .env utan att något test klagar. F greppar samtliga spårade filer
# efter sökvägar under docs/ och arkivkataloger (docs-archive-*/) och kräver att de finns.
#
# UNDANTAG (sökvägar som avsiktligt inte finns som filer):
#   docs/standards.md      DIGG:s DCAT-AP-SE-spec, inte detta repo
#   docs/arbetspaket.md    planerade leverabler som aldrig skrevs
#   docs/natverksgrans.md
#   docs/etapp-8-journal.md, docs/etapp-9-journal.md   journaler som aldrig skrevs
#   */etapp-N-journal.md   platshållare med litteralt N, inte en fil
F_UNDANTAG='docs/standards\.md|docs/arbetspaket\.md|docs/natverksgrans\.md|docs/etapp-[89]-journal\.md|.*/etapp-N-journal\.md'
F_FEL=0
F_ANTAL=0
while read -r fil; do
  [ -f "$fil" ] || continue
  [ "$fil" = "tests/verify_docs.sh" ] && continue     # skriptet nämner själva mönstren
  case "$fil" in *arbetspaket.md) continue ;; esac   # arbetspaketspecen i utvecklingsrepots arkiv: leveransinstruktioner, inga länkar
  while read -r p; do
    [ -n "$p" ] || continue
    p="${p%.}"
    grep -qE "^(${F_UNDANTAG})$" <<<"$p" && continue
    F_ANTAL=$((F_ANTAL+1))
    if [ ! -e "$p" ]; then
      no "F $fil: hänvisning till saknad sökväg '$p'"
      F_FEL=$((F_FEL+1))
    fi
  done < <(grep -oIE "(^|[^A-Za-z0-9/._-])(docs|docs-archive-[0-9]+)/[A-Za-zÅÄÖåäö0-9_.-]+\.(md|txt|html|png)" "$fil" 2>/dev/null \
           | grep -oE "(docs|docs-archive-[0-9]+)/[A-Za-zÅÄÖåäö0-9_.-]+\.(md|txt|html|png)" | sort -u)
done < <(git ls-files)
[ "$F_FEL" -eq 0 ] && ok "F alla ${F_ANTAL} dokumentsökvägar i repot upplöstes"

# ---------------------------------------------------------------------
section "G. Körbara exempel använder portkartan i .env"
# ---------------------------------------------------------------------
# localhost:<port> i aktiva dokument ska vara en publicerad värdport ur .env (del e, E11: 8800 i stället för 38800).
# Gapanalysen, målarkitekturen och arkiven är historik och prövas inte.
G_UT="$(python3 - <<'PY'
import glob, os, re
portar = set(re.findall(r"^[A-Z0-9_]*PORT=(\d+)", open(".env" if os.path.exists(".env") else ".env.exempel").read(), re.M))
filer = ["README.md"] + sorted(glob.glob("docs/0*.md") + glob.glob("docs/1[1-3]*.md") + glob.glob("docs/koncept/*.md"))
fel = []
for f in filer:
    for nr, rad in enumerate(open(f, encoding="utf-8"), 1):
        for p in re.findall(r"localhost:(\d{2,5})\b", rad):
            if p not in portar:
                fel.append("%s:%d localhost:%s" % (f, nr, p))
print("\n".join(fel) if fel else "OK %d" % len(filer))
PY
)"
case "${G_UT}" in OK*) ok "G alla localhost-portar i ${G_UT#OK } aktiva dokument finns i portkartan" ;; *) while read -r r; do no "G port som inte finns i .env: ${r}"; done <<<"${G_UT}" ;; esac

# ---------------------------------------------------------------------
section "H. Relativa Markdown-länkar och bilder i docs/ upplöses"
# ---------------------------------------------------------------------
# F hittar bara sökvägar som börjar med docs/; H prövar varje [text](relativ) och ![](bild) i docs/ och README (del e, E12).
H_UT="$(python3 - <<'PY'
import glob, os, re
from urllib.parse import unquote
mall = {"koncept/NN-slug.md"}          # mall i koncept-README, inte en länk
fel, antal = [], 0
for f in ["README.md"] + sorted(glob.glob("docs/**/*.md", recursive=True)):
    if f.startswith("docs/testresultat/"):
        continue                       # arkiverade rapporter citerar andras texter
    text = open(f, encoding="utf-8").read()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for mal in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
        if re.match(r"^(https?:|mailto:|#)", mal) or mal in mal and mal in mall:
            continue
        sokvag = unquote(mal.split("#")[0])
        if not sokvag:
            continue
        antal += 1
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), sokvag))):
            fel.append("%s -> %s" % (f, mal))
print("\n".join(fel) if fel else "OK %d" % antal)
PY
)"
case "${H_UT}" in OK*) ok "H alla ${H_UT#OK } relativa länkar och bilder i docs/ och README upplöses" ;; *) while read -r r; do no "H trasig relativ länk: ${r}"; done <<<"${H_UT}" ;; esac

finish "verify_docs (dokument/kod-synk)"
