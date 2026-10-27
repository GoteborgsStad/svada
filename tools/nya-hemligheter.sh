#!/usr/bin/env bash
# =====================================================================
# tools/nya-hemligheter.sh – byter PoC:ens utvecklingshemligheter mot
# slumpade värden i en .env (publik demo, säkerhetsfynd K1/K2)
# =====================================================================
# .env är spårad i git och bär därför kända utvecklingsvärden (lösenord,
# management-nycklar, STS-hemligheter, drifttoken). På en server som nås
# utifrån får de ALDRIG användas – den som sett repot kunde annars t.ex.
# logga in som CKAN-administratör.
#
# Körs EN gång på servern före första starten (eller lokalt för att prova),
# därefter kräver bytet tomma volymer: databaserna har lösenordet inbakat
# från sin första start. Kör därför aterstall-demo.sh direkt efteråt.
#
#   bash tools/nya-hemligheter.sh            # skriver om ./.env
#   bash tools/nya-hemligheter.sh annan.env  # skriver om en annan fil
#
# Värdena skrivs BARA i filen – aldrig på skärmen eller i någon logg.
# Lösenordsgrinden byts samtidigt (tools/nytt-demo-losenord.sh).
# =====================================================================
set -euo pipefail
FIL="${1:-$(dirname "$0")/../.env}"
[ -f "${FIL}" ] || { echo "hittar inte ${FIL}" >&2; exit 1; }

HEMLIGHETER="STAD_GATEWAY_DRIFT_TOKEN EDC_PROVIDER_MGMT_KEY EDC_CONSUMER_MGMT_KEY
SVADA_STS_CLIENT_SECRET_DHI SVADA_STS_CLIENT_SECRET_STAD
EDC_PROVIDER_STATUS_KEY SVADA_STATUS_ADMIN_KEY
TIMESCALE_PASSWORD"

python3 - "${FIL}" ${HEMLIGHETER} <<'PY'
import re, secrets, sys
fil, namn = sys.argv[1], sys.argv[2:]
s = open(fil, encoding="utf-8").read()
for n in namn:
    # 32 hex-tecken: bara [0-9a-f], så inga citat- eller skalproblem i .env.
    s, antal = re.subn(r"^%s=.*$" % n, "%s=%s" % (n, secrets.token_hex(16)),
                       s, flags=re.M)
    if antal != 1:
        sys.exit("%s: förväntade exakt en rad, hittade %d" % (n, antal))
    print("  %-30s nytt slumpat värde" % n)
open(fil, "w", encoding="utf-8").write(s)
PY
# Lösenordsgrinden (Caddy) får också ett nytt lösenord och en ny kak-token.
bash "$(dirname "$0")/nytt-demo-losenord.sh"
echo "Klart. Kör nu aterstall-demo.sh så att databaserna skapas med de nya värdena."
