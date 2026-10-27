#!/usr/bin/env bash
# Startar hela SVADA PoC-kedjan igen infor demo.
# Baserat pa README.md "Manuellt, om stacken redan ar byggd" + kanda Mac-fallgropar
# (Docker Desktop på Mac).
set -e
cd "$(dirname "$0")"

echo "== 0. Ladda .env =="
set -a; . ./.env; set +a

echo "== 0b. Kontrollerar att .env har variablerna för Svadas utfardare =="
# En variabel som saknas ger inget fel i Compose (tom strang) utan tysta 401 i
# varje DSP-anrop. Stanna hellre har (granskningen 2026-10-09).
SAKNAS=""
for v in SVADA_PARTICIPANT_ID_SVADA SVADA_PARTICIPANT_DID_SVADA SVADA_PARTICIPANT_ID_DHI \
         SVADA_PARTICIPANT_DID_DHI SVADA_PARTICIPANT_ID_STAD SVADA_PARTICIPANT_DID_STAD \
         IDENTITY_HUB_SVADA_DEFAULT_PORT IDENTITY_HUB_SVADA_IDENTITY_PORT \
         IDENTITY_HUB_SVADA_DID_PORT IDENTITY_HUB_SVADA_CREDENTIALS_PORT \
         SVADA_KOV_ROLLINNEHAVARE SVADA_ROLLINNEHAVARE_DHI \
         EDC_PROVIDER_STATUS_KEY SVADA_STATUS_ADMIN_KEY; do
  [ -n "${!v:-}" ] || SAKNAS="${SAKNAS} ${v}"
done
if [ -n "${SAKNAS}" ]; then
  echo "FEL: .env saknar:${SAKNAS}" >&2
  exit 1
fi

echo "== 1. Skapa delat natverk (ofarligt om det redan finns) =="
docker network create ${SVADA_PREFIX:-svada}-dsp-public 2>/dev/null || echo "  (fanns redan, OK)"
# Delad volym för attestutbyte mellan IdentityHub-instanserna (verifierbar DCP-identitet).
if ! docker volume inspect ${SVADA_PREFIX:-svada}-vc-utbyte >/dev/null 2>&1; then
  docker volume create ${SVADA_PREFIX:-svada}-vc-utbyte >/dev/null
  docker run --rm --entrypoint sh -v ${SVADA_PREFIX:-svada}-vc-utbyte:/vc-utbyte "${CURL_IMAGE}" -c "chmod 777 /vc-utbyte"
  echo "  skapade volymen ${SVADA_PREFIX:-svada}-vc-utbyte"
fi

echo "== 1b. Svadas utfarddare (DSGA 0.1): FORST, DHI och Staden importerar sina intyg darifran =="
# Utfärdare med rätt mandat: medlems- och deltagarintygen kommer fran Svadas egen utfardare.
# Startordning svada -> dhi -> stad. Vi vantar tills utfardaren ar frisk och har
# skrivit sina intyg innan de andra hubbarna startar.
docker compose -f compose.dsga.yml --profile dsga-utfardare up -d --build --wait --wait-timeout 300

echo "== 2. Org DHI (provider): fcf, edc =="
docker compose -f compose.dhi.yml --profile dhi-fcf --profile dhi-identitet --profile dhi-edc up -d --build

echo "== 3. Org Staden (consumer): dataplan, edc, ingest =="
docker compose -f compose.stad.yml --profile stad-dataplan --profile stad-identitet --profile stad-edc --profile stad-ingest up -d --build

echo "== 4. Kontrollrum + publik ingång (Caddy) =="
# Lösenordsgrinden: Caddy vägrar starta utan den. Skapas bara första gången;
# ett befintligt lösenord behålls (även över den nattliga återställningen).
if [ -n "${PUBLIK_URL_KONTROLLRUM:-}" ]; then
  bash tools/nytt-demo-losenord.sh --om-saknas
fi
docker compose -f compose.kontrollrum.yml --profile dashboard --profile publik-ingang up -d --build

echo "== 5. Vantar 20s sa tjansterna hinner bli klara innan engangsjobben =="
sleep 20

echo "== 5b. Kontroll: connectorerna har avtals-API:t =="
# Observerat 2026-10-14: edc-consumer kunde starta utan POST /v3/contractagreements/request (405) medan allt annat svarade.
# Stadens avtalsregister (ingest) kan då inte läsa avtalen och stänger (status OKAND), så leveranser nekas. En omstart av
# connectorn räcker. Kontrollera därför båda connectorerna och starta om en som saknar API:t (högst tre försök).
for ROLL in consumer provider; do
  if [ "${ROLL}" = "consumer" ]; then PORT="${EDC_CONSUMER_MGMT_PORT}"; NYCKEL="${EDC_CONSUMER_MGMT_KEY}"; else PORT="${EDC_PROVIDER_MGMT_PORT}"; NYCKEL="${EDC_PROVIDER_MGMT_KEY}"; fi
  for FORSOK in 1 2 3; do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST -H "X-Api-Key: ${NYCKEL}" -H 'Content-Type: application/json' \
          -d '{"@context":{"@vocab":"https://w3id.org/edc/v0.0.1/ns/"},"@type":"QuerySpec","limit":1}' \
          "http://localhost:${PORT}/management/v3/contractagreements/request" || true)
    [ "${KOD}" = "200" ] && { echo "  edc-${ROLL}: avtals-API:t svarar (200)"; break; }
    echo "  edc-${ROLL}: avtals-API:t svarade ${KOD:-inget svar}; startar om connectorn (försök ${FORSOK}/3)"
    docker restart "${SVADA_PREFIX:-svada}-edc-${ROLL}" >/dev/null
    for _ in $(seq 1 40); do
      [ "$(docker inspect -f '{{.State.Health.Status}}' "${SVADA_PREFIX:-svada}-edc-${ROLL}" 2>/dev/null)" = "healthy" ] && break
      sleep 3
    done
  done
  [ "${KOD}" = "200" ] || echo "  VARNING: edc-${ROLL} saknar fortfarande avtals-API:t efter tre försök" >&2
done

echo "== 6. Engangsjobb (registrera-edc MASTE koras om efter varje omstart av providern) =="
docker compose -f compose.stad.yml --profile laddning run --rm ladda-brunnar
docker compose -f compose.dhi.yml --profile edc-bootstrap run --rm registrera-edc
echo ""
echo "== Klart. Kontrollrummet: http://localhost:${DASHBOARD_PORT:-8800}  =="
if [ -n "${PUBLIK_URL_KONTROLLRUM:-}" ]; then
  echo "== PUBLIK INGÅNG (det besökaren ser): ${PUBLIK_URL_KONTROLLRUM} =="
  echo "== Lösenordsskyddad – användare och lösenord: cat .demo-losenord =="
fi
echo ""
echo "GLOM INTE: macOS-brandvaggen ska vara PA (tillat INTE Docker om den fragar)."
echo "Kolla: bash tests/verify_ap0.sh"
