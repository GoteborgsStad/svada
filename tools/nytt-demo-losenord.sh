#!/usr/bin/env bash
# =====================================================================
# tools/nytt-demo-losenord.sh – lösenordsgrinden för den publika demon
# =====================================================================
# Hela demon ligger bakom ett gemensamt lösenord tills projektet är redo
# att kommunicera den (services/caddy/Caddyfile, snippet "inloggning").
# Skriptet skapar ett nytt slumpat lösenord och skriver två filer, båda
# ignorerade av git och läsbara bara för ägaren (chmod 600):
#
#   .demo-losenord        användarnamn + lösenord i klartext – för
#                         människor (dela med dem som ska se demon) och
#                         för testerna (tests/lib.sh, demo_inloggning).
#   .demo-inloggning.env  det Caddy behöver: bcrypt-hashen av lösenordet
#                         och kakans token (DEMO_TILLTRADE_TOKEN).
#
#   bash tools/nytt-demo-losenord.sh              # nytt slumpat lösenord
#   bash tools/nytt-demo-losenord.sh --valj       # välj användare + lösenord
#   bash tools/nytt-demo-losenord.sh --om-saknas  # bara om filerna saknas
#
# --valj frågar efter användarnamn (standard: DEMO_ANVANDARE i .env) och
# lösenord två gånger, med dold inmatning. Kör det själv i en terminal.
#
# Lösenordet skrivs ALDRIG på skärmen eller i någon logg, och hashas via
# stdin (aldrig som kommandoradsargument, som syns i processlistan).
# Läs det med:  cat .demo-losenord
#
# Ett byte gäller direkt: kör Caddy startas den om. Token byts samtidigt,
# så alla som var inloggade måste logga in igen.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

LOSENORD_FIL=.demo-losenord
ENV_FIL=.demo-inloggning.env

# (En fil från före --valj saknar DEMO_ANVANDARE och skapas då om.)
if [ "${1:-}" = "--om-saknas" ] && [ -s "${LOSENORD_FIL}" ] && [ -s "${ENV_FIL}" ] \
   && grep -q '^DEMO_ANVANDARE=' "${ENV_FIL}"; then
  echo "  lösenordsgrinden finns redan (${LOSENORD_FIL}), behåller lösenordet"
  exit 0
fi

# Allt som skapas härifrån är bara läsbart för ägaren.
umask 077

ANVANDARE="${DEMO_ANVANDARE}"
if [ "${1:-}" = "--valj" ]; then
  IFS= read -r -p "Användarnamn [${ANVANDARE}]: " svar
  ANVANDARE="${svar:-${ANVANDARE}}"
  # Användarnamnet hamnar i Caddyfile och i Basic Auth ("namn:lösenord"):
  # inga mellanslag eller kolon.
  if ! printf '%s' "${ANVANDARE}" | grep -Eq '^[A-Za-z0-9._-]{1,64}$'; then
    echo "Användarnamnet får bara innehålla A–Z, a–z, 0–9, . _ -" >&2; exit 1
  fi
  # IFS= : inledande/avslutande blanksteg är en del av lösenordet.
  IFS= read -r -s -p "Lösenord (12–72 tecken, syns inte): " LOSENORD; echo
  IFS= read -r -s -p "Lösenord igen: " igen; echo
  [ "${LOSENORD}" = "${igen}" ] || { echo "Lösenorden matchar inte." >&2; exit 1; }
  unset igen
  [ "${#LOSENORD}" -ge 12 ] || { echo "För kort – minst 12 tecken." >&2; exit 1; }
  # bcrypt läser bara de första 72 byten – längre vore en falsk trygghet.
  [ "$(printf '%s' "${LOSENORD}" | wc -c)" -le 72 ] \
    || { echo "För långt – högst 72 byte (bcrypt)." >&2; exit 1; }
else
  # 16 tecken ur ett alfabet utan förväxlingsbara tecken (0/o, 1/l/i), i
  # grupper om fyra så att det går att läsa upp på ett möte: ~79 bitar.
  LOSENORD="$(python3 -c '
import secrets
a = "abcdefghjkmnpqrstuvwxyz23456789"
print("-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(4)))')"
fi
TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

# bcrypt med kostnad 12 (~0,2 s): skyddar en stulen hash utan att varje
# inloggningsförsök kostar servern mycket CPU (gissning stryps dessutom).
HASH="$(printf '%s\n' "${LOSENORD}" \
  | docker run --rm -i "${CADDY_IMAGE}" caddy hash-password \
      --algorithm bcrypt --bcrypt-cost 12)"
case "${HASH}" in
  '$2a$'*) ;;
  *) echo "hash-password gav inget bcrypt-värde – avbryter" >&2; exit 1 ;;
esac

cat > "${LOSENORD_FIL}" <<EOF
# SVADA publik demo – inloggning ($(date '+%F'), tools/nytt-demo-losenord.sh)
# Dela bara med dem som ska se demon. Filen ignoreras av git.
användare: ${ANVANDARE}
lösenord: ${LOSENORD}
EOF
# Enkla citattecken: hashen innehåller "$", som compose annars skulle
# tolka som en variabel.
cat > "${ENV_FIL}" <<EOF
# Lösenordsgrinden (Caddy). Skapad av tools/nytt-demo-losenord.sh – ändra
# inte för hand. Ignoreras av git.
DEMO_ANVANDARE=${ANVANDARE}
DEMO_LOSENORD_HASH='${HASH}'
DEMO_TILLTRADE_TOKEN=${TOKEN}
EOF
chmod 600 "${LOSENORD_FIL}" "${ENV_FIL}"
echo "  nytt lösenord för användaren '${ANVANDARE}' – läs det med: cat ${LOSENORD_FIL}"

P="${SVADA_PREFIX:-svada}"
if [ "$(docker inspect -f '{{.State.Running}}' "${P}-caddy" 2>/dev/null)" = "true" ]; then
  echo "  startar om ${P}-caddy så att det nya lösenordet gäller"
  docker compose -f compose.kontrollrum.yml --profile publik-ingang \
    up -d --force-recreate caddy >/dev/null
fi
