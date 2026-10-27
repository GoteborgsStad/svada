#!/usr/bin/env bash
# =====================================================================
# verify_ap9.sh – publik demo (gren publik-demo)
# =====================================================================
# Bevisar att kedjan kan visas för externa besökare utan att något mer än
# de publika rollerna blir nåbart, och att demodatat är förfalskat:
#
#   9.1  Caddy är uppe och är den enda publika ingången (bindningar).
#   9.2  Alla övriga värdportar är bundna till VARD_BIND_IP.
#   9.3  De publika värdnamnen svarar – B släpps, A nekas.
#   9.4  Okända värdnamn (försök att nå interna tjänster) ger 404.
#   9.5  Distribution B nås publikt (webbvy och API) genom Caddy.
#   9.6  Kontrollrummet visar de publika ingångarna, inga interna portar.
#   9.7  Demodatat: Krokängsparken på Lisebergsbanan, alla 149 punkter
#        inom Liseberg (de riktiga koordinaterna finns inte i filen).
#   9.9  Inga kända utvecklingshemligheter på en publik server.
#   9.10 Hastighetsbegränsning på POST-knappar.
#   9.11 Lösenordsgrinden: utan inloggning svarar inget värdnamn (401),
#        rätt lösenord ger en kaka för hela domänen, fel lösenord och falsk
#        kaka nekas, robots.txt är fri, lösenordsgissning stryps (429).
#
# 9.1–9.10 körs INLOGGADE (demo_inloggning i tests/lib.sh); 9.11 kör sina
# oinloggade anrop med "curl -q" (utan kakan).
#
# Körs mot den lokala publika stacken (bash starta-demo.sh) och senare mot
# servern. Kräver att PUBLIK_URL_* är satta i .env – i originalet (utan
# publik ingång) hoppar skriptet över sig självt.
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
. tests/lib.sh
set -a; . ./.env; set +a

echo "== Publik demo =="
if [ -z "${PUBLIK_URL_KONTROLLRUM:-}" ]; then
  echo "  PUBLIK_URL_KONTROLLRUM saknas i .env – inte den publika varianten, hoppar över."
  echo ">> verify_ap9: GRÖNT (ej tillämpligt)"
  exit 0
fi
P="${SVADA_PREFIX:-svada}"
TMP="$(mktemp -d)"; trap 'rm -rf "${TMP}"' EXIT
# Allt nedan går genom Caddys lösenordsgrind: logga in en gång (9.11 provar
# själva grinden, utan kakan).
T0_EPOK="$(date +%s)"       # 9.12 granskar bara loggrader från den här körningen (äldre rader kan vara skrivna med en äldre inställning); inloggningen nedan är en Basic-begäran
demo_inloggning "${TMP}"
# Användarnamnet kan vara valt (nytt-demo-losenord.sh --valj): ta det ur
# lösenordsfilen, inte standardvärdet i .env.
DEMO_ANVANDARE="$(sed -n 's/^användare: //p' .demo-losenord 2>/dev/null)"

kod() { curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$@"; }

# --- 9.1 Caddy är den enda publika ingången ---------------------------
section "9.1 Caddy är uppe och binder bara CADDY_BIND_IP"
if [ "$(docker inspect -f '{{.State.Running}}' "${P}-caddy" 2>/dev/null)" = "true" ]; then
  ok "${P}-caddy kör"
else
  no "${P}-caddy kör inte (starta med profilen publik-ingang)"
fi
CADDY_BIND="$(docker inspect -f '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostIp}} {{end}}{{end}}' "${P}-caddy" 2>/dev/null)"
FEL_BIND=0
# IPv4 (CADDY_BIND_IP) och IPv6 (CADDY_BIND_IP6) – inget annat.
for ip in ${CADDY_BIND}; do
  [ "${ip}" = "${CADDY_BIND_IP:-0.0.0.0}" ] || [ "${ip}" = "${CADDY_BIND_IP6:-::1}" ] || FEL_BIND=1
done
if [ -n "${CADDY_BIND}" ] && [ "${FEL_BIND}" = "0" ]; then
  ok "Caddy binder ${CADDY_BIND_IP:-0.0.0.0} och [${CADDY_BIND_IP6:-::1}] (portar ${CADDY_HTTP_PORT}/${CADDY_HTTPS_PORT})"
else
  no "Caddy binder oväntade adresser: '${CADDY_BIND}'"
fi

if printf '%s\n' ${CADDY_BIND} | grep -qxF "${CADDY_BIND_IP6:-::1}"; then
  ok "Caddy lyssnar även på IPv6 [${CADDY_BIND_IP6:-::1}] (AAAA-posterna)"
else
  no "Caddy saknar IPv6-bindning – AAAA-posterna leder till en stängd port"
fi

# Lyssnar Caddy på alla IPv6-adresser (servern) måste dess nät ha IPv6 –
# annars ser Caddy alla IPv6-besökare som nätets gateway, och de delar en
# enda hastighetsgräns (en skanner stänger ute alla).
if [ "${CADDY_BIND_IP6:-::1}" = "::" ]; then
  NAT="$(docker inspect -f '{{range $n, $_ := .NetworkSettings.Networks}}{{$n}} {{end}}' "${P}-caddy" 2>/dev/null | awk '{print $1}')"
  if [ "$(docker network inspect -f '{{.EnableIPv6}}' "${NAT}" 2>/dev/null)" = "true" ]; then
    ok "Caddys nät (${NAT}) har IPv6: IPv6-besökare behåller sin adress"
  else
    no "Caddys nät (${NAT}) saknar IPv6 – alla IPv6-besökare delar en hastighetsgräns (INGANG_IPV6=true)"
  fi
fi

# --- 9.2 Övriga värdportar ------------------------------------------
section "9.2 Alla övriga värdportar är bundna till VARD_BIND_IP (${VARD_BIND_IP:-0.0.0.0})"
FEL_PORTAR=""
for c in $(docker ps --format '{{.Names}}' | grep "^${P}-" | grep -v "^${P}-caddy$"); do
  for ip in $(docker inspect -f '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostIp}} {{end}}{{end}}' "${c}"); do
    [ "${ip}" = "${VARD_BIND_IP:-0.0.0.0}" ] || FEL_PORTAR="${FEL_PORTAR} ${c}(${ip})"
  done
done
if [ -z "${FEL_PORTAR}" ]; then
  ok "inga värdportar utanför ${VARD_BIND_IP:-0.0.0.0}"
else
  no "portar bundna till fel adress:${FEL_PORTAR}"
fi

# --- 9.3 De publika värdnamnen ---------------------------------------
section "9.3 De publika värdnamnen svarar genom Caddy"
B_API="${PUBLIK_URL_TIDSSERIE}/temporal/entities?type=SewerOverflowModelB&attrs=overflowVolumeM3&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1"
while read -r namn url forvantat; do
  svar="$(kod "${url}")"
  if [ "${svar}" = "${forvantat}" ]; then
    ok "${namn}: ${svar} (${url%%\?*})"
  else
    no "${namn}: ${svar}, förväntade ${forvantat} (${url})"
  fi
done <<EOF
kontrollrum ${PUBLIK_URL_KONTROLLRUM}/health 200
B-webbvy ${PUBLIK_URL_BRUNNAR}/brunnar 200
B-API ${B_API} 200
EOF
# A är non-public: stad-gateway kräver token (G22) – nekas, oavsett ingång.
A_KOD="$(kod "${PUBLIK_URL_CIP}/ngsi-ld/v1/entities?type=SewerOverflowModelA")"
case "${A_KOD}" in
  401|403) ok "CIP (Distribution A) nekas utan token: ${A_KOD}" ;;
  *)       no "CIP (Distribution A) svarade ${A_KOD} utan token – ska nekas" ;;
esac

# Den publika tidsserien släpper bara igenom den öppna distributionen (B): A ligger på en egen entitetstyp.
TS="${PUBLIK_URL_TIDSSERIE}/temporal/entities"
for q in "?type=SewerOverflowModelA&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1" \
         "?type=SewerOverflowModelB&type=SewerOverflowModelA&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1" \
         "?type=SewerOverflowWeir&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1" ""; do
  svar="$(kod "${TS}${q}")"
  [ "${svar}" = "403" ] && ok "publik tidsserie nekar ${q:-(ingen typ)}: 403" || no "publik tidsserie svarade ${svar} på ${q:-(ingen typ)} – bara B ska släppas igenom"
done
svar="$(kod "${TS}/urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526?attrs=overflowVolumeM3&timerel=after&timeAt=2020-01-01T00:00:00Z")"
[ "${svar}" = "403" ] && ok "publik tidsserie nekar en enskild A-entitet: 403" || no "publik tidsserie svarade ${svar} på en A-entitet"
svar="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "${PUBLIK_URL_TIDSSERIE}/temporal/entityOperations/query" -H 'content-type: application/json' -d '{"type":"Query","entities":[{"type":"SewerOverflowModelA"}],"temporalQ":{"timerel":"after","timeAt":"2020-01-01T00:00:00Z"}}')"
[ "${svar}" = "403" ] && ok "publik tidsserie nekar POST-frågor (kan inte gå runt typfiltret): 403" || no "publik tidsserie svarade ${svar} på en POST-fråga"

# --- 9.4 Okända värdnamn ----------------------------------------------
section "9.4 Interna tjänster har inget värdnamn (404)"
BAS_SCHEMA="${PUBLIK_URL_KONTROLLRUM%%://*}"
for vard in edc identity fcf ingest katalog portal-se portal-eu; do
  u="${BAS_SCHEMA}://${vard}.${DEMO_DOMAN}${DEMO_URL_PORT:-}/"
  svar="$(kod "${u}")"
  # Lokalt (http) svarar Caddys uppsamlingsblock 404; ett 000 vore DNS- eller anslutningsfel och bevisar inget om
  # routningen (del e, E5). På servern (https) saknar okända värdnamn certifikat, så där är 000 det väntade.
  if [ "${svar}" = "404" ] || { [ "${svar}" = "000" ] && [ "${BAS_SCHEMA}" = "https" ]; }; then
    ok "${vard}.${DEMO_DOMAN}: ${svar} (ingen ingång)"
  else
    no "${vard}.${DEMO_DOMAN}: ${svar} – ska inte svara"
  fi
done
# Management-API:ets sökväg via kontrollrummets värdnamn ska inte nå EDC.
# Med rätt Origin (annars svarar dashboardens ursprungskontroll 403 och döljer routningen, del e E5): anropet ska nå
# dashboarden och få dess 404 för en okänd sökväg, inte EDC:s svar.
MGMT="$(curl -s --max-time 15 -w '\n%{http_code}' "${PUBLIK_URL_KONTROLLRUM}/management/v3/assets/request" \
     -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' -d '{}')"
MGMT_KOD="${MGMT##*$'\n'}"; MGMT="${MGMT%$'\n'*}"
if [ "${MGMT_KOD}" = 404 ] && printf '%s' "${MGMT}" | jq -e '.detail == "Not Found"' >/dev/null 2>&1; then
  ok "EDC:s management-API nås inte via kontrollrummets värdnamn (dashboardens 404 för okänd sökväg)"
else
  no "management-sökvägen via kontrollrummet gav ${MGMT_KOD}: $(printf '%s' "${MGMT}" | head -c 120)"
fi

# --- 9.5 Distribution B nås publikt ----------------------------------
section "9.5 Distribution B nås publikt (webbvy och API) genom Caddy"
for u in "${PUBLIK_URL_BRUNNAR}/brunnar" "${B_API}"; do
  accept='text/html'
  case "${u}" in "${PUBLIK_URL_TIDSSERIE}/"*) accept='application/json' ;; esac
  svar="$(kod -H "Accept: ${accept}" "${u}")"
  # 2xx: Mintaka svarar 206 när resultatet pagineras.
  if [ "${svar#2}" != "${svar}" ]; then
    ok "publik adress fungerar (${svar}): ${u%%\?*}"
  else
    no "publik adress svarar ${svar}: ${u}"
  fi
done

# --- 9.6 Kontrollrummet ------------------------------------------------
section "9.6 Kontrollrummet visar de publika ingångarna"
curl -s --max-time 30 "${PUBLIK_URL_KONTROLLRUM}/" >"${TMP}/index.html"
if grep -q "Publika ingångar" "${TMP}/index.html"; then
  ok "rubriken \"Publika ingångar\" finns"
else
  no "kontrollrummet visar inte de publika ingångarna"
fi
SAKNAS=""
for u in "${PUBLIK_URL_BRUNNAR}" "${PUBLIK_URL_TIDSSERIE}" "${PUBLIK_URL_CIP}"; do
  grep -q "href=\"${u}\"" "${TMP}/index.html" || SAKNAS="${SAKNAS} ${u}"
done
if [ -z "${SAKNAS}" ]; then
  ok "alla tre publika adresser är länkade"
else
  no "saknade länkar:${SAKNAS}"
fi
if grep -q 'href="http://host.docker.internal' "${TMP}/index.html"; then
  no "kontrollrummet länkar till interna värdportar"
else
  ok "inga länkar till interna värdportar"
fi

# --- 9.7 Demodatat ----------------------------------------------------
section "9.7 Demodatat ligger på Liseberg"
if python3 - <<'PY'
import sqlite3, struct, sys
c = sqlite3.connect("data/dbsvadaexample.gpkg")
def pt(b):
    f = b[3]; e = "<" if f & 1 else ">"
    env = [0, 32, 48, 48, 64][(f >> 1) & 7]
    return struct.unpack_from(e + "dd", b, 8 + env + 14)
punkter = []
for t in ("Weirs", "Outlet", "Measurepoints"):
    punkter += [pt(b) for (b,) in c.execute('SELECT location FROM "%s"' % t) if b]
krok = pt(c.execute("SELECT location FROM Weirs WHERE weirid='SSO1_01-4526'").fetchone()[0])
utanfor = [p for p in punkter
           if not (11.9885 <= p[0] <= 11.9971 and 57.6921 <= p[1] <= 57.6973)]
print("  punkter: %d, utanför Liseberg: %d, Krokängsparken: %s" % (len(punkter), len(utanfor), krok))
sys.exit(0 if len(punkter) == 149 and not utanfor and krok == (11.99184, 57.69434) else 1)
PY
then
  ok "alla 149 punkter inom Liseberg, Krokängsparken på Lisebergsbanan"
else
  no "gpkg:n innehåller punkter utanför Liseberg"
fi

# --- 9.9 Inga kända utvecklingshemligheter på en publik server --------
section "9.9 Inga kända utvecklingshemligheter (K2)"
# Gäller bara servern (DEMO_URL_SCHEMA=https). Lokalt (http) är det den
# medvetna PoC-uppsättningen med .env-värden; hoppa då över.
if [ "${DEMO_URL_SCHEMA:-http}" = "https" ]; then
  KANDA="svada-dhi-mgmt-6ad959db43fb svada-stad-mgmt-56667be228eb
    svada-drift-2c1f9a7b4e6d 9e5a73f052658abd10ef5ebc2dd3a937
    svada-dhi-status-4be1f07a92c3 svada-samordnare-5d90c2e7b184"
  HITTADE=""
  for h in ${KANDA}; do grep -q "^[A-Z_]*=${h}\$" .env && HITTADE="${HITTADE} ${h}"; done
  if [ -z "${HITTADE}" ]; then
    ok "inga kända dev-hemligheter kvar i .env (kör tools/nya-hemligheter.sh)"
  else
    no "kända dev-hemligheter kvar i .env:${HITTADE}"
  fi
else
  ok "lokal demo (http): medvetna PoC-hemligheter, hoppar över kravet"
fi

# --- 9.9b Skydd som gäller även utan lösenord --------------------------
# Lösenordet tas bort inför lansering; då får den publika ytan inte gå att använda på annat sätt än
# i kontrollrummets egen sida. Inloggad besökare (kaka via .curlrc).
section "9.9b Skydd utan lösenord: ursprungskontroll, cip är skrivskyddad, bara B-data på tidsserie"
S1="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST "${PUBLIK_URL_KONTROLLRUM}/api/atgard/okand-prov" -d '{}')"
S2="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST -H 'Origin: https://ond.example' "${PUBLIK_URL_KONTROLLRUM}/api/atgard/okand-prov" -d '{}')"
[ "${S1}" = 403 ] && [ "${S2}" = 403 ] && ok "POST utan eller med främmande origin nekas (403)" || no "POST-ursprungskontrollen: utan origin ${S1}, främmande ${S2} (väntade 403)"
S3="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST "${PUBLIK_URL_CIP}/ngsi-ld/v1/entities" -d '{}')"
[ "${S3}" = 405 ] && ok "stadens CIP utifrån är skrivskyddad (POST ger 405)" || no "POST mot CIP gav ${S3}, väntade 405"
S4="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${PUBLIK_URL_TIDSSERIE}/temporal/entities?type=SewerOverflowModelA")"
[ "${S4}" = 403 ] && ok "A:s tidsserie släpps inte ut (403)" || no "ModelA på tidsserie gav ${S4}, väntade 403"

# --- 9.9c Tidsserien släpper bara exakt EN B-typ (positiv allowlist) ----
# Regressionstest för Codex del d, fynd D4: `type=B&type=SewerOverflowModel%41` (kodat A som andra värde) passerade
# Caddys gamla textsökning och gav A-entiteter utan A-token. Ett tomt svar är INGET bevis, så provet kräver
# riktigt laddade A-data (hämtas direkt från Mintaka, förbi Caddy) och att B också finns.
section "9.9c Tidsserien: bara exakt en B-typ passerar, A läcker inte genom kodade eller dubbla type-parametrar"
# Värdportarna är bundna till VARD_BIND_IP (på servern 172.17.0.1, lokalt 127.0.0.1): läs Mintaka där, inte på localhost.
MINTAKA_DIREKT="http://${VARD_BIND_IP:-localhost}:${MINTAKA_PORT}/temporal/entities"
TS_TID="timerel=after&timeAt=2020-01-01T00:00:00Z"
antal_typ() {  # antal_typ <fil> <typ> -> antal entiteter av typen i ett JSON-svar (0 om svaret inte är en lista)
  python3 -c "
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: d=[]
print(sum(1 for e in d if isinstance(e,dict) and e.get('type')==sys.argv[2]) if isinstance(d,list) else 0)" "$1" "$2"
}
MK_A="$(curl -s --max-time 30 -o "${TMP:-/tmp}/ts-a-direkt.json" -w '%{http_code}' "${MINTAKA_DIREKT}?type=SewerOverflowModelA&${TS_TID}&limit=1")"
MK_B="$(curl -s --max-time 30 -o "${TMP:-/tmp}/ts-b-direkt.json" -w '%{http_code}' "${MINTAKA_DIREKT}?type=SewerOverflowModelB&${TS_TID}&limit=1")"
A_FINNS="$(antal_typ "${TMP:-/tmp}/ts-a-direkt.json" SewerOverflowModelA)"
B_FINNS="$(antal_typ "${TMP:-/tmp}/ts-b-direkt.json" SewerOverflowModelB)"
# Rent läge (nollställningen kör verify_ap9 innan något levererats): då finns inget att läcka och provet bevisar inget.
# Det redovisas som EJ PRÖVAT, inte som grönt och inte som fel; verify_all.sh kör ap9 efter ap4c/ap6b, när A och B är levererade.
TS_PROVAS=1
# Ett läsfel är inte ett tomt lager (fynd i serverkörningen 2026-10-18: localhost i stället för VARD_BIND_IP gav A=0, B=0
# och "ej prövat" fast data fanns). Kunde Mintaka inte läsas är det ett fel, inte ett rent läge.
if ! { [ "${MK_A}" = 200 ] || [ "${MK_A}" = 206 ]; } || ! { [ "${MK_B}" = 200 ] || [ "${MK_B}" = 206 ]; }; then
  TS_PROVAS=0
  no "9.9c: Mintaka kunde inte läsas direkt (${MINTAKA_DIREKT}: A gav ${MK_A}, B gav ${MK_B}); provet kan inte avgöras"
elif [ "${A_FINNS}" -gt 0 ] && [ "${B_FINNS}" -gt 0 ]; then
  ok "förutsättning: riktiga A-data (${A_FINNS}) och B-data (${B_FINNS}) finns i plattformen, så ett nekat svar betyder något"
else
  TS_PROVAS=0
  echo "  [EJ PRÖVAT] 9.9c: A=${A_FINNS}, B=${B_FINNS} entiteter i Mintaka (rent läge). Leverera transfer-a/-b och kör om; ett tomt svar bevisar ingenting"
fi
ts_hamta() {  # ts_hamta <fraga> -> HTTP-kod; svaret i ts-prov.json. Vid hastighetsgränsen (429) väntar den ut fönstret en gång.
  local kod; kod="$(curl -s --max-time 30 -o "${TMP:-/tmp}/ts-prov.json" -w '%{http_code}' "${PUBLIK_URL_TIDSSERIE}/temporal/entities$1")"
  if [ "${kod}" = 429 ]; then sleep 62; kod="$(curl -s --max-time 30 -o "${TMP:-/tmp}/ts-prov.json" -w '%{http_code}' "${PUBLIK_URL_TIDSSERIE}/temporal/entities$1")"; fi
  echo "${kod}"
}
if [ "${TS_PROVAS}" = 1 ]; then
LACKTA=""
for FRAGA in \
  "type=SewerOverflowModelA" \
  "type=SewerOverflowModelB&type=SewerOverflowModel%41" \
  "type=SewerOverflowModel%41&type=SewerOverflowModelB" \
  "type=SewerOverflowModelB&type=SewerOverflowModelA" \
  "type=SewerOverflowModelB&type=SewerOverflowModelB" \
  "type=SewerOverflowModelB&type=" \
  "type=SewerOverflowModelB&type=.*" \
  "type=SewerOverflowModelB&typ%65=SewerOverflowModelA" \
  "type=SewerOverflowModelB;type=SewerOverflowModelA" \
  "type=SewerOverflowModelB%2CSewerOverflowModel%41" \
  "type=SewerOverflowModelB&id=urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526" \
  "type=SewerOverflowModelB&idPattern=.*" \
  "type=SewerOverflowModelBX"; do
  KOD="$(ts_hamta "?${FRAGA}&${TS_TID}")"
  NA="$(antal_typ "${TMP:-/tmp}/ts-prov.json" SewerOverflowModelA)"
  if [ "${KOD}" != 403 ] || [ "${NA}" != 0 ]; then LACKTA="${LACKTA} [${FRAGA} -> ${KOD}, ${NA} A-entiteter]"; fi
done
[ -z "${LACKTA}" ] && ok "13 frågor som väljer A, flera typer eller oväntade parametrar nekas (403) utan en enda A-entitet" || no "släpptes igenom:${LACKTA}"
KOD="$(ts_hamta "?type=SewerOverflowModelB&attrs=overflowVolumeM3&limit=1&${TS_TID}")"
NB="$(antal_typ "${TMP:-/tmp}/ts-prov.json" SewerOverflowModelB)"; NA="$(antal_typ "${TMP:-/tmp}/ts-prov.json" SewerOverflowModelA)"
{ [ "${KOD}" = 200 ] || [ "${KOD}" = 206 ]; } && [ "${NB}" -ge 1 ] && [ "${NA}" = 0 ] \
  && ok "positivt fall: exakt en B-typ med kända parametrar ger B-entiteter (${KOD}) och ingen A" \
  || no "B-frågan gav ${KOD}, ${NB} B- och ${NA} A-entiteter (väntade 200/206, minst en B, ingen A)"
KOD="$(ts_hamta "/urn:ngsi-ld:SewerOverflowModelA:SSO1_01-4526?${TS_TID}")"
[ "${KOD}" = 403 ] && ok "enskild A-entitet på tidsserien nekas (403)" || no "enskild A-entitet gav ${KOD}, väntade 403"
grep -q "Only the open distribution (B)" "${TMP:-/tmp}/ts-prov.json" && grep -q "Bara den öppna distributionen (B)" "${TMP:-/tmp}/ts-prov.json" \
  && ok "nekandet förklaras på både svenska och engelska (proxyn vet inte besökarens språk)" \
  || no "nekandets text saknar svenska eller engelska: $(head -c 120 "${TMP:-/tmp}/ts-prov.json")"
fi

# --- 9.9d Avvisade anrop ändrar inget; störningar har absolut frist ----
# Regressionstest för Codex del d, fynd D1/D2/D5/D6 (kroppen läses före varje sidoeffekt, hälsosvaret är rensat).
section "9.9d Avvisad kropp startar inget jobb, felinjektion förnyas inte, brunnar-health och dokumentation är rena"
# Sidoeffekter mäts med invarianter, inte jobblistans längd (fynd E2 i del e: listan kapas vid 40 poster och en längd är
# konstant när ett nytt jobb tränger ut ett gammalt). Ett läsfel ger LÄSFEL och underkänner provet i stället för att två
# tomma värden jämförs lika.
tillstand_sig() {
  local J S
  J="$(curl -s --max-time 10 "${PUBLIK_URL_KONTROLLRUM}/api/jobb")" || { echo LÄSFEL; return; }
  S="$(curl -s --max-time 10 "${PUBLIK_URL_KONTROLLRUM}/api/skydd")" || { echo LÄSFEL; return; }
  python3 -c '
import json,sys
try:
    j=json.loads(sys.argv[1]); s=json.loads(sys.argv[2])
    ids=[x["id"] for x in j["jobb"]]
    print("maxid=%s ids=%s aktivt=%s felinjektion=%s" % (max(ids or [0]), ",".join(map(str,ids)), (j.get("aktivt") or {}).get("id"), s["felinjektionS"]))
except Exception:
    print("LÄSFEL")' "${J}" "${S}"
}
FORE="$(tillstand_sig)"
python3 -c 'import json; print(json.dumps({"padding":"x"*1100000}))' >"${TMP:-/tmp}/stor-kropp.json"
K1="$(curl -s --max-time 20 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' --data-binary @"${TMP:-/tmp}/stor-kropp.json" "${PUBLIK_URL_KONTROLLRUM}/api/atgard/kor-batch")"
K2="$(curl -s --max-time 20 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' -d '[1,2' "${PUBLIK_URL_KONTROLLRUM}/api/atgard/kor-batch")"
K3="$(curl -s --max-time 20 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' -d '[]' "${PUBLIK_URL_KONTROLLRUM}/api/atgard/kor-batch")"
sleep 2
EFTER="$(tillstand_sig)"
{ [ "${FORE}" != LÄSFEL ] && [ "${K1}" = 413 ] && [ "${K2}" = 400 ] && [ "${K3}" = 400 ] && [ "${FORE}" = "${EFTER}" ]; } \
  && ok "för stor (413), trasig och icke-objekt (400) kropp: jobb-id, aktivt jobb och felinjektionens frist oförändrade" \
  || no "kropp 1,1 MB=${K1}, trasig=${K2}, lista=${K3}; före [${FORE}] efter [${EFTER}] (väntade 413/400/400 och oförändrat)"

# Rå transport genom Caddy, INLOGGAD med samma kaka som curl (fynd E1 i del e: utan kaka stannade provet i lösenordsgrinden
# och kunde vara grönt oavsett backend). Först en positiv kontroll med samma transport: den ska nå dashboarden (400 + kod).
POS="$(python3 tests/raa_kropp.py "${PUBLIK_URL_KONTROLLRUM}" "${CURL_HOME:-/nonexistent}/demo-kakor" positiv)"
case "${POS}" in
  "POSITIV 400 fel.okand_atgard") ok "rå transport når dashboarden genom Caddy och grinden (positiv kontroll: ${POS})" ;;
  *) no "rå transport når inte dashboarden (${POS}); provet för avbruten kropp vore meningslöst" ;;
esac
FORE="$(tillstand_sig)"
python3 tests/raa_kropp.py "${PUBLIK_URL_KONTROLLRUM}" "${CURL_HOME:-/nonexistent}/demo-kakor" avbryt >/dev/null
sleep 3
EFTER="$(tillstand_sig)"
FEL_AKTIV="$(curl -s --max-time 10 "${PUBLIK_URL_KONTROLLRUM}/api/felinjektion" | python3 -c "import json,sys;print(json.load(sys.stdin)['aktiv'])" 2>/dev/null || echo LÄSFEL)"
{ [ "${FORE}" != LÄSFEL ] && [ "${FORE}" = "${EFTER}" ] && [ "${FEL_AKTIV}" = False ]; } \
  && ok "avbruten kropp (rubrik utan full kropp, inloggad): inget jobb, oförändrad frist, felinjektionen av" \
  || no "avbruten kropp ändrade tillstånd: före [${FORE}] efter [${EFTER}], felinjektion aktiv=${FEL_AKTIV}"
# Långsam kropp: Caddy ska avbryta efter read_body (15 s), inte hålla anslutningen öppen (del d, D6).
LANG="$(python3 tests/raa_kropp.py "${PUBLIK_URL_KONTROLLRUM}" "${CURL_HOME:-/nonexistent}/demo-kakor" langsam)"
SEK="$(printf '%s' "${LANG}" | awk '{print $2}')"
if python3 -c "import sys; sys.exit(0 if 12 <= float(sys.argv[1]) <= 22 else 1)" "${SEK:-0}" 2>/dev/null; then
  ok "långsam kropp: Caddy släpper anslutningen efter ${SEK} s (read_body 15 s; ${LANG})"
else
  no "långsam kropp: ${LANG} (väntade avbrott efter 12–22 s)"
fi
F1="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' "${PUBLIK_URL_KONTROLLRUM}/api/felinjektion")"
F2="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' -d '{}' "${PUBLIK_URL_KONTROLLRUM}/api/felinjektion")"
F3="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'Content-Type: application/json' -d '{"finns_inte":true}' "${PUBLIK_URL_KONTROLLRUM}/api/felinjektion")"
{ [ "${F1}" = 400 ] && [ "${F2}" = 400 ] && [ "${F3}" = 400 ]; } \
  && ok "tom kropp, {} och okänt läge på felinjektion ger 400 (ingen frist förnyas av ett tomt anrop)" \
  || no "felinjektion: tom=${F1}, {}=${F2}, okänt läge=${F3} (väntade 400)"
BH="$(curl -s --max-time 10 -w '\n%{http_code}' "${PUBLIK_URL_BRUNNAR}/health")"; BH_KOD="${BH##*$'\n'}"; BH="${BH%$'\n'*}"
INTERN_ADRESS='https?://[A-Za-z0-9-]+([/:"[:space:]]|$)|[A-Za-z]:[0-9]{2,5}([^0-9]|$)|host\.docker\.internal'
if [ "${BH_KOD}" = 200 ] && printf '%s' "${BH}" | jq -e '.status == "ok"' >/dev/null 2>&1 \
   && ! printf '%s' "${BH}" | grep -Eq "${INTERN_ADRESS}"; then
  ok "brunnar /health: 200, status ok och ingen intern adress eller port"
else
  no "brunnar /health: HTTP ${BH_KOD}, svar ${BH:0:160}"
fi
D1="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "${PUBLIK_URL_BRUNNAR}/docs")"
D2="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "${PUBLIK_URL_BRUNNAR}/openapi.json")"
{ [ "${D1}" = 404 ] && [ "${D2}" = 404 ]; } && ok "brunnar: /docs och /openapi.json är stängda (404)" || no "brunnar /docs=${D1}, /openapi.json=${D2} (väntade 404)"

# --- 9.10 Hastighetsbegränsning (K3/K4) -------------------------------
# Testas mot kontrollrummets POST-zon: en okänd åtgärd har ingen sidoeffekt
# (dashboarden svarar 400/404) men räknas ändå av ratelimit-tillägget. Ingen
# annan kontroll läser den zonen, så provet stör inte resten och tål omkörning.
section "9.10 Hastighetsbegränsning på POST-knappar (gräns ${RATE_SKRIV_ANTAL}/${RATE_SKRIV_FONSTER})"
ANTAL=$(( RATE_SKRIV_ANTAL + 8 ))
KODER="$(for _ in $(seq 1 ${ANTAL}); do
  curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 \
    -X POST "${PUBLIK_URL_KONTROLLRUM}/api/atgard/ratelimit-prov"
done)"
ANTAL_429="$(printf '%s\n' "${KODER}" | grep -c '^429$' || true)"
if [ "${ANTAL_429}" -gt 0 ]; then
  ok "ratelimit slår in efter gränsen (${ANTAL_429} av ${ANTAL} fick 429)"
else
  no "ingen 429 på ${ANTAL} snabba POST – hastighetsbegränsningen är inte aktiv"
fi

# --- 9.11 Lösenordsgrinden ----------------------------------------------
# Demon ska inte indexeras eller spridas före lanseringen: hela ingången
# ligger bakom ett gemensamt lösenord (Caddyfile, snippet "inloggning").
# "curl -q" = utan .curlrc, alltså UTAN tillträdeskakan.
if [ "${DEMO_GATE:-on}" = "off" ]; then
  section "9.11 Lösenordsgrinden (avstängd)"
  ok "9.11 lösenordsgrinden är avstängd (DEMO_GATE=off): inloggningsproven hoppas över"
else
section "9.11 Lösenordsgrinden (alla värdnamn, en inloggning för hela domänen)"
VARDAR="${PUBLIK_URL_KONTROLLRUM} ${PUBLIK_URL_BRUNNAR}
  ${PUBLIK_URL_TIDSSERIE} ${PUBLIK_URL_CIP}"
oinl() { curl -q -s --max-time 30 "$@"; }

# Utan inloggning: 401 med Basic-utmaning på alla fyra – med en djup sökväg
# och en POST, så att inget handle-block hinner före grinden. Bara EN
# sökväg per värdnamn: varje oinloggat anrop räknas mot inloggningsgränsen
# (RATE_INLOGG_ANTAL/min per IP), och testet ska inte förbruka den själv –
# gissningsprovet sist ska vara det som slår i taket.
FEL_401=""
for u in ${VARDAR}; do
  svar="$(oinl -o /dev/null -w '%{http_code}' "${u}/api/status")"
  [ "${svar}" = "401" ] || FEL_401="${FEL_401} ${u}/api/status(${svar})"
done
POST_SVAR="$(oinl -o /dev/null -w '%{http_code}' -X POST "${PUBLIK_URL_KONTROLLRUM}/api/atgard/grind-prov")"
[ "${POST_SVAR}" = "401" ] || FEL_401="${FEL_401} POST-knapp(${POST_SVAR})"
if [ -z "${FEL_401}" ]; then
  ok "utan inloggning: 401 på alla fyra värdnamn (GET och POST)"
else
  no "släpps igenom utan inloggning:${FEL_401}"
fi
if oinl -D - -o /dev/null "${PUBLIK_URL_KONTROLLRUM}/" | grep -qi '^www-authenticate: Basic realm="SVADA'; then
  ok "401 bär Basic-utmaningen (webbläsarens inloggningsruta)"
else
  no "401 saknar WWW-Authenticate: Basic realm=\"SVADA …\""
fi

# robots.txt är fri och säger nej till allt.
if oinl "${PUBLIK_URL_BRUNNAR}/robots.txt" | grep -qx 'Disallow: /'; then
  ok "robots.txt fri utan inloggning: Disallow: /"
else
  no "robots.txt saknas eller säger inte Disallow: /"
fi

# Fel lösenord: 401 och INGEN kaka.
printf 'user = "%s:fel-%s"\n' "${DEMO_ANVANDARE}" "$(date +%s)" \
  | oinl -K - -D "${TMP}/fel.hdr" -o /dev/null "${PUBLIK_URL_KONTROLLRUM}/health"
if grep -q '^HTTP/[0-9.]* 401' "${TMP}/fel.hdr" && ! grep -qi '^set-cookie: svada_tilltrade' "${TMP}/fel.hdr"; then
  ok "fel lösenord: 401, ingen tillträdeskaka"
else
  no "fel lösenord gav inte 401 utan kaka"
fi

# Rätt lösenord (demo_inloggning ovan): kakans egenskaper.
KAKA_RAD="$(grep svada_tilltrade "${TMP}/demo-kakor" 2>/dev/null)"
if [ -n "${KAKA_RAD}" ]; then
  # Netscape-format: domän, underdomäner, sökväg, secure, utgång, namn, värde
  read -r k_doman k_under k_sokvag k_secure _ _ _ <<<"${KAKA_RAD#\#HttpOnly_}"
  [ "${k_doman}" = ".${DEMO_DOMAN}" ] && [ "${k_under}" = "TRUE" ] && [ "${k_sokvag}" = "/" ] \
    && ok "kakan gäller hela domänen (.${DEMO_DOMAN}, sökväg /)" \
    || no "kakan har fel omfång: ${k_doman} ${k_under} ${k_sokvag}"
  case "${KAKA_RAD}" in
    "#HttpOnly_"*) ok "kakan är HttpOnly (når inte JavaScript)" ;;
    *)             no "kakan saknar HttpOnly" ;;
  esac
  if [ "${DEMO_URL_SCHEMA:-http}" = "https" ]; then
    [ "${k_secure}" = "TRUE" ] && ok "kakan är Secure (https)" \
      || no "kakan saknar Secure på https-servern (DEMO_KAKA_SECURE)"
  fi
else
  no "ingen tillträdeskaka efter inloggning"
fi

# Med kakan: alla fyra värdnamn släpper igenom (inget 401 från Caddy) – en
# och samma inloggning räcker för hela demon.
# Kräver ett lyckat svar bakom grinden (200), inte bara frånvaro av Basic-huvudet: en timeout eller ett 500 är inte
# åtkomst (del e, E5). tidsserie. har bara B-frågan öppen, så den prövas med en sådan.
FEL_KAKA=""
for u in ${VARDAR}; do
  case "${u}" in
    *tidsserie.*) prov="${u}/temporal/entities?type=SewerOverflowModelB&timerel=after&timeAt=2020-01-01T00:00:00Z&limit=1" ;;
    *) prov="${u}/health" ;;
  esac
  k="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' "${prov}")"
  [ "${k}" = 200 ] || FEL_KAKA="${FEL_KAKA} ${u}(${k})"
done
[ -z "${FEL_KAKA}" ] && ok "med kakan: alla fyra värdnamn släpper igenom utan ny inloggning" \
  || no "kräver ny inloggning trots kakan:${FEL_KAKA}"

# En påhittad kaka nekas.
FALSK="$(oinl -o /dev/null -w '%{http_code}' -b "svada_tilltrade=$(printf '%064d' 0)" \
  "${PUBLIK_URL_KONTROLLRUM}/health")"
[ "${FALSK}" = "401" ] && ok "påhittad kaka nekas: 401" \
  || no "påhittad kaka gav ${FALSK} (förväntade 401)"

# Lösenordsgissning stryps per klient-IP. SIST i skriptet: efteråt är
# grinden stängd för den här IP:n i upp till ${RATE_INLOGG_FONSTER} (redan
# inloggade, med kaka, påverkas inte).
ANTAL=$(( RATE_INLOGG_ANTAL + 8 ))
KODER="$(seq 1 "${ANTAL}" | xargs -P 8 -I{} sh -c \
  "printf 'user = \"%s:gissning-{}\"\n' '${DEMO_ANVANDARE}' \
   | curl -q -s -K - -o /dev/null -w '%{http_code}\n' --max-time 30 '${PUBLIK_URL_KONTROLLRUM}/health'")"
ANTAL_429="$(printf '%s\n' "${KODER}" | grep -c '^429$' || true)"
if [ "${ANTAL_429}" -gt 0 ]; then
  ok "lösenordsgissning stryps (${ANTAL_429} av ${ANTAL} fick 429, gräns ${RATE_INLOGG_ANTAL}/${RATE_INLOGG_FONSTER})"
else
  no "ingen 429 på ${ANTAL} felaktiga inloggningar – gissning stryps inte"
fi
# Den som redan har kakan påverkas inte av spärren.
EFTER="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${PUBLIK_URL_KONTROLLRUM}/health")"
[ "${EFTER}" = "200" ] && ok "inloggad besökare påverkas inte av spärren: 200" \
  || no "inloggad besökare fick ${EFTER} under spärren"

fi

# --- 9.12 Statistikloggen: bra data, inga hemligheter --------------------
# Användningsstatistik: Caddy skriver en JSON-logg i statistik/logg. Den får aldrig bära
# tillträdeskakan, lösenordet eller hela IP-adresser, och den ska gå att räkna på.
c() { local d="$1"; if eval "$2" >/dev/null 2>&1; then ok "$d"; else no "$d"; fi; }
section "9.12 Statistikloggen (statistik/logg/access.log): giltig JSON, kapade adresser och inga hemligheter"
curl -s -o /dev/null --max-time 30 -b "${TMP}/demo-kakor" "${PUBLIK_URL_KONTROLLRUM}/?k=ap9" || true
# en begäran MED lösenord (Basic) och en med vidarebefordringshuvuden, så att user_id och dessa huvuden verkligen skulle synas om de loggades
_anv="$(sed -n 's/^användare: //p' .demo-losenord)"; _pw="$(sed -n 's/^lösenord: //p' .demo-losenord)"; _pw="${_pw//\\/\\\\}"; _pw="${_pw//\"/\\\"}"
printf 'user = "%s:%s"\n' "${_anv}" "${_pw}" | curl -s -q -K - -o /dev/null --max-time 30 -H 'Forwarded: for=203.0.113.9' -H 'X-Real-Ip: 203.0.113.9' -H 'Via: 1.1 proxy.example' "${PUBLIK_URL_KONTROLLRUM}/health" || true
sleep 2
STAT_LOGG="statistik/logg/access.log"
TOKEN_VARDE="$(sed -n 's/^DEMO_TILLTRADE_TOKEN=//p' .demo-inloggning.env 2>/dev/null | head -1)"
LOSEN_VARDE="$(sed -n 's/^lösenord: //p' .demo-losenord 2>/dev/null | head -1)"
c "9.12a loggfilen finns och har rader" "[ -s '${STAT_LOGG}' ]"
# grep ger 1 när värdet inte finns och 2 när en fil inte gick att läsa: bara 1 är ett bevis (en oläsbar fil bevisar ingenting)
inget_i_loggen() { local f r; for f in statistik/logg/access*; do case "$f" in *.gz) gzip -dc "$f" 2>/dev/null | grep -qF -- "$1";; *) grep -qF -- "$1" "$f" 2>/dev/null;; esac; r=$?; [ $r -eq 1 ] || return 1; done; return 0; }
c "9.12b tillträdeskakans värde finns inte i loggen (alla filer lästa)" "[ -n \"\$TOKEN_VARDE\" ] && inget_i_loggen \"\$TOKEN_VARDE\""
c "9.12c lösenordet finns inte i loggen (alla filer lästa)" "[ -n \"\$LOSEN_VARDE\" ] && inget_i_loggen \"\$LOSEN_VARDE\""
# Testläget: ?test=1 sätter kakan svada-test, och ett anrop med kakan loggas med fältet test=1 (kakan själv tas bort ur loggen).
c "9.12t ?test=1 sätter kakan svada-test" "curl -s -D - -o /dev/null --max-time 20 -b '${TMP}/demo-kakor' '${PUBLIK_URL_KONTROLLRUM}/health?test=1' | grep -qi '^set-cookie: svada-test=1'"
TL_ID="tl$(date +%s)${RANDOM}"
curl -s -o /dev/null --max-time 20 -b "${TMP}/demo-kakor" -b "svada-test=1" -A "Mozilla/5.0 (testlage)" "${PUBLIK_URL_KONTROLLRUM}/health?${TL_ID}=1"
sleep 3
c "9.12u ett anrop med kakan svada-test loggas med test=1 (utan att kakan finns i loggen)" "grep -h '${TL_ID}' '${STAT_LOGG}' | grep -q '\"test\":\"1\"' && ! grep -h '${TL_ID}' '${STAT_LOGG}' | grep -qi 'svada-test=1'"
STAT_PROV="$(python3 -I - "${STAT_LOGG}" "${T0_EPOK}" <<'PY'
import json, sys, ipaddress
import glob, gzip
rader = []
for fil in ([sys.argv[1]] if not sys.argv[1].endswith("access.log") else sorted(glob.glob(sys.argv[1].replace("access.log", "access*")))):   # aktuell och roterade (.gz) filer
    with (gzip.open(fil, "rt", encoding="utf-8") if fil.endswith(".gz") else open(fil, encoding="utf-8")) as f:
        rader += [r for r in f if r.strip()]
ts_min = float(sys.argv[2]) if len(sys.argv) > 2 else 0   # bara rader efter provets start: äldre rader kan vara skrivna med en äldre inställning
fel = []
ok_rader = 0
for r in rader:
    try:
        p = json.loads(r)
    except ValueError:
        continue          # en avklippt sista rad är inte ett fel i sig, men räknas inte
    if float(p.get("ts", 0)) < ts_min:
        continue
    ok_rader += 1
    req = p.get("request", {})
    hdr = {k.lower() for k in req.get("headers", {})}
    # begärans huvuden som kan bära hemligheter eller adresser; svarshuvudet Via (Caddys eget) är ingen hemlighet, Set-Cookie är det
    for hemlig in ("cookie", "authorization", "x-forwarded-for", "forwarded", "x-real-ip", "true-client-ip", "client-ip", "cf-connecting-ip", "x-client-ip", "via"):
        if hemlig in hdr: fel.append("huvud " + hemlig)
    if "set-cookie" in {k.lower() for k in p.get("resp_headers", {})}: fel.append("svarshuvud set-cookie")
    if "remote_port" in req: fel.append("remote_port")
    if p.get("user_id"): fel.append("user_id")
    for f in ("remote_ip", "client_ip"):
        v = req.get(f)
        if not v: continue
        a = ipaddress.ip_address(v)
        # IPv4 kapas till /24 (sista oktetten 0), IPv6 till /48 (de 80 sista bitarna 0)
        if (a.version == 4 and int(a) & 0xFF) or (a.version == 6 and int(a) & ((1 << 80) - 1)):
            fel.append("okapad adress i " + f)
print("OK %d" % ok_rader if ok_rader and not fel else "FEL %s (giltiga rader: %d)" % (sorted(set(fel)), ok_rader))
PY
)"
c "9.12d raderna är JSON och bär varken kaka, auktorisering, port eller okapad IP-adress (${STAT_PROV})" "[ \"\${STAT_PROV%% *}\" = OK ]"
# Händelserna har en egen hastighetsgräns i Caddy (RATE_HANDELSE_*) och ska inte äta knapparnas (RATE_SKRIV_ANTAL, 20/min): 30 stycken
# på rad via Caddy får inget 429, trots att en POST-knapp hade stoppats efter 20.
HANDELSER_429="$(for _ in $(seq 1 30); do curl -s -o /dev/null -w '%{http_code}\n' --max-time 20 -b "${TMP}/demo-kakor" -X POST -H "Origin: ${PUBLIK_URL_KONTROLLRUM}" -H 'content-type: application/json' -A "curl/test" -d '{"h":"js_fel"}' "${PUBLIK_URL_KONTROLLRUM}/api/handelse"; done | grep -c '^429$' || true)"
c "9.12f 30 händelser på rad via Caddy får inget 429 (egen gräns, inte knapparnas)" "[ \"\${HANDELSER_429:-1}\" = 0 ]"
c "9.12e rapporten räknar på loggen (tools/statistik-rapport.py)" "python3 -I tools/statistik-rapport.py --katalog statistik | grep -q 'kontrollrum'"

finish "Publik demo"
