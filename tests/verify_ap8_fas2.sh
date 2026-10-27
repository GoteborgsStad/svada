#!/usr/bin/env bash
# =====================================================================
# verify_ap8_fas2.sh – verifierbar DCP-identitet i stället för mock-IAM: negativtest
# (testfall 8.1–8.7)
# =====================================================================
# Detta kompletterar verify_ap8_fas1.sh (den bindande miniminivån: delad
# management-nyckel, se docs/koncept/C1-identitet.md). Det här skriptet bevisar den
# fulla identitetskedjan: verifierbar attest via DCP/IdentityHub i stället
# för ett påstående, och att anrop UTAN giltigt attest avvisas – inte bara
# att anrop utan RÄTT NYCKEL avvisas (det är redan verify_ap8_fas1.sh:s jobb).
#
# Numreringen här (8f2.x) följer samma "fN"-konvention som
# verify_ap8_fas1.sh (8f1.x), eftersom tabellens 8.1–8.6 spänner över
# BÅDA faserna och ingen enskild fil kan äga hela numreringen ensam.
#
# Självständigt och idempotent på samma sätt som verify_ap4b.sh/
# verify_ap8_fas1.sh – startar dataplanet + båda connectorerna + IdentityHub
# och kör en egen A-förhandling för 8f2.2/8f2.3.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### Verifierbar DCP-identitet – negativtest ####"

set -a; . ./.env; set +a

PROV_API="http://localhost:${EDC_PROVIDER_DEFAULT_PORT}/api"
PROV_MGMT="http://localhost:${EDC_PROVIDER_MGMT_PORT}/management"
CONS_API="http://localhost:${EDC_CONSUMER_DEFAULT_PORT}/api"
CONS_MGMT="http://localhost:${EDC_CONSUMER_MGMT_PORT}/management"
PROV_DSP="http://edc-provider:19194/protocol/${EDC_DSP_VERSION}"
# Samma DSP-endpoint, men nådd DIREKT från host (porten är publicerad,
# compose.dhi.yml: "${EDC_PROVIDER_DSP_PORT}:19194") – till skillnad från
# PROV_DSP ovan, som är motpartens INTERNA adress på det egna
# docker-nätet (används som counterPartyAddress i förhandlingsanropen,
# aldrig anropad direkt av testskriptet självt).
PROV_DSP_LOKAL="http://localhost:${EDC_PROVIDER_DSP_PORT}/protocol/${EDC_DSP_VERSION}"
DSP_PROTOKOLL="dataspace-protocol-http:${EDC_DSP_VERSION}"
IDHUB_DHI="http://localhost:${IDENTITY_HUB_DHI_DEFAULT_PORT}/api"
IDHUB_STAD="http://localhost:${IDENTITY_HUB_STAD_DEFAULT_PORT}/api"

DHI="docker compose -f compose.dhi.yml"
STAD="docker compose -f compose.stad.yml"

docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

vanta_health() {   # vanta_health <url> <sekunder>
  for _ in $(seq 1 "$2"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1/check/health")" \
      = "200" ] && return 0
    sleep 2
  done
  return 1
}

hamta_katalog() {
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/catalog/request" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\"
    }" > /tmp/svada_ap8fas2_katalog.json
}

offert() {   # offert <asset-id>
  jq -c --arg a "$1" '[ .dataset ] | flatten
      | map(select(.["@id"] == $a)) | .[0].hasPolicy | [.] | flatten | .[0]' \
      /tmp/svada_ap8fas2_katalog.json
}

forhandla() {   # forhandla <asset-id> -> consumerns förhandlings-id
  local asset="$1" offer policy
  offer=$(offert "$asset")
  policy=$(printf '%s' "$offer" | jq -c --arg a "$asset" \
    '. + {"@context": ["http://www.w3.org/ns/odrl.jsonld",
                       {"svada": "https://svada.goteborg.se/ns/"}],
          "assigner": "'"${EDC_PROVIDER_ID}"'", "target": $a}')
  curl -s --max-time 30 -X POST "${CONS_MGMT}/v3/contractnegotiations" \
    -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" \
    -H 'content-type: application/json' -d "{
      \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
      \"@type\": \"ContractRequest\",
      \"counterPartyAddress\": \"${PROV_DSP}\",
      \"protocol\": \"${DSP_PROTOKOLL}\",
      \"policy\": ${policy}
    }" | jq -r '.["@id"] // empty'
}

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (dataplan + båda connectorerna + IdentityHub + registrering)"

if vanta_health "$PROV_API" 1; then
  ok "edc-provider var redan uppe"
else
  echo "  (startar dhi-fcf + dhi-edc ...)"
  $DHI --profile dhi-fcf --profile dhi-edc up -d >/dev/null 2>&1
  if vanta_health "$PROV_API" 90; then ok "edc-provider uppe"; else no "edc-provider startade inte"; fi
fi
if vanta_health "$CONS_API" 1; then
  ok "edc-consumer var redan uppe"
else
  echo "  (startar stad-edc ...)"
  $STAD --profile stad-edc up -d >/dev/null 2>&1
  if vanta_health "$CONS_API" 90; then ok "edc-consumer uppe"; else no "edc-consumer startade inte"; fi
fi

echo "  (registrerar Distribution A och B hos providern ...)"
if $DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap8fas2_bootstrap.log 2>&1; then
  ok "registrera-edc körde igenom (båda distributionerna)"
else
  no "registrera-edc misslyckades (se /tmp/svada_ap8fas2_bootstrap.log)"
  tail -n 15 /tmp/svada_ap8fas2_bootstrap.log | sed 's/^/      /'
fi

# --- 8f2.1 Identitetstjänsten uppe --------------------------------------
section "8f2.1 Identitetstjänsten (DCP/IdentityHub) uppe hos båda parter"

if vanta_health "$IDHUB_DHI" 30; then
  ok "8f2.1 identity-hub-dhi svarar frisk (/api/check/health)"
else
  no "8f2.1 identity-hub-dhi svarar INTE frisk"
fi
if vanta_health "$IDHUB_STAD" 30; then
  ok "8f2.1 identity-hub-stad svarar frisk (/api/check/health)"
else
  no "8f2.1 identity-hub-stad svarar INTE frisk"
fi

# --- 8f2.2 E2E med riktig identitet (regression) ------------------------
section "8f2.2 E2E med riktig identitet: 4b.1–4b.3 + 4c.1 (regression)"
# Den faktiska körningen sker via verify_all.sh:s ordning (samma mönster
# som 6a.7/5.9 – körs INTE inline här för att undvika att köra samma
# förhandling två gånger). verify_ap4b.sh och verify_ap4c.sh kräver båda
# numera ett verifierat SvadaRoleCredential (hamta_kov_token(), STEG 6) på
# sina riktiga KoV-anrop, så en grön körning av dem ÄR redan beviset för
# 8f2.2: att en riktig, verifierad identitet kan ta sig igenom hela kedjan.
for s in tests/verify_ap4b.sh tests/verify_ap4c.sh; do
  [ -f "$s" ] && [ -x "$s" ] && ok "8f2.2 $s finns och är körbar" || no "8f2.2 $s saknas eller är inte körbar"
done

# --- 8f2.3 Negativtest: anrop utan giltigt attest avvisas ---------------
section "8f2.3 Negativtest: katalog, förhandling och transfer UTAN attest avvisas"
# DspRequestHandlerImpl (uppströmskällan connector-0.17.0, data-protocols/dsp/
# dsp-core/dsp-http-core/.../message/DspRequestHandlerImpl.java) verifierar
# identiteten FÖRST i sin egen kod – innan meddelandet ens tolkas (se
# konstanten UNAUTHORIZED och att både getResource() och createResource()
# returnerar unauthorized(request) så fort token == null, långt innan
# JsonObjectValidatorRegistry nås). MEN detta är EDC:s kontrollerkod, inte
# hela Jersey-kedjan: ett HELT TOMT `{}` visade sig i praktiken ge 400,
# inte 401 (upptäckt genom att faktiskt köra det – se
# bytets sista steg). Orsaken, bekräftad via svarskroppen
# ("Failed to expand JsonObject: ... result was empty, it could be
# caused by missing '@context'"): EDC:s JSON-LD-expansion körs som ett
# EGET steg i Jersey-lagret, FÖRE kontrollermetoden ens anropas – en tom
# `{}` expanderar till ingenting alls, och det underkänns innan
# DspRequestHandlerImpl:s token-kontroll ens nås. Lösningen är INTE att
# skicka en fullt giltig DSP-begäran (identitetskontrollen ska ju testas
# ISTÄLLET för meddelandevalideringen) utan minsta möjliga kropp som
# ÖVERLEVER JSON-LD-expansionen: ett `@type` med en fullt kvalificerad
# IRI (ingen `@context` behövs, en absolut IRI är redan meningsfull för
# JSON-LD). Verifierat: alla tre ger nu 401 med korrekt DSP-felkropp
# (`CatalogError`/`ContractNegotiationError`/`TransferError`). Status är
# därefter ALLTID exakt 401 (Response.Status.UNAUTHORIZED, hårdkodat i
# unauthorized()), aldrig 403.

KOD_KATALOG=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
  "${PROV_DSP_LOKAL}/catalog/request" \
  -H 'content-type: application/json' \
  -d '{"@type":"https://w3id.org/dspace/2025/1/CatalogRequestMessage"}')
if [ "$KOD_KATALOG" = "401" ]; then
  ok "8f2.3 katalogbegäran utan Authorization-header avvisas (HTTP $KOD_KATALOG)"
else
  no "8f2.3 katalogbegäran utan Authorization-header svarade HTTP $KOD_KATALOG (förväntat 401)"
fi

KOD_FORHANDLING=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
  "${PROV_DSP_LOKAL}/negotiations/request" \
  -H 'content-type: application/json' \
  -d '{"@type":"https://w3id.org/dspace/2025/1/ContractRequestMessage"}')
if [ "$KOD_FORHANDLING" = "401" ]; then
  ok "8f2.3 förhandlingsbegäran utan Authorization-header avvisas (HTTP $KOD_FORHANDLING)"
else
  no "8f2.3 förhandlingsbegäran utan Authorization-header svarade HTTP $KOD_FORHANDLING (förväntat 401)"
fi

KOD_TRANSFER=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
  "${PROV_DSP_LOKAL}/transfers/request" \
  -H 'content-type: application/json' \
  -d '{"@type":"https://w3id.org/dspace/2025/1/TransferRequestMessage"}')
if [ "$KOD_TRANSFER" = "401" ]; then
  ok "8f2.3 överföringsbegäran utan Authorization-header avvisas (HTTP $KOD_TRANSFER)"
else
  no "8f2.3 överföringsbegäran utan Authorization-header svarade HTTP $KOD_TRANSFER (förväntat 401)"
fi

# Kompletterande negativtest specifikt för KoV-gaten (STEG 6): ett
# GILTIGT förhandlings-id men INGET Authorization-attest ska nekas 401
# INNAN förhandlingen rör sig – detta är redan bevisat löpande av
# verify_ap4b.sh testfall 4b.3, men vi upprepar det kort här eftersom det
# är en del av samma 8.3-negativtestskrav (KoV-beslutet är också "en
# handling som kräver giltigt attest").
hamta_katalog
NEG_A=$(forhandla "${EDC_ASSET_A_ID}")
if [ -n "$NEG_A" ]; then
  ok "8f2.3 förhandling om A startad för KoV-negativtestet ($NEG_A)"
else
  no "8f2.3 kunde inte starta förhandling om A"
fi

PROV_ID=""
echo "  (väntar in gaten) ..."
for _ in $(seq 1 15); do
  sleep 2
  PROV_ID=$(curl -s --max-time 15 -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
              "${PROV_MGMT}/kov/forhandlingar" \
            | jq -r --arg c "$NEG_A" '[ .[] | select(.correlationId == $c) ] | .[0].id // empty')
  [ -n "$PROV_ID" ] && break
done

if [ -n "$PROV_ID" ]; then
  ok "8f2.3 förhandlingen hamnade i KoV-kön ($PROV_ID)"
  KOD_KOV=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST \
    -H "X-Api-Key: ${EDC_PROVIDER_MGMT_KEY}" \
    "${PROV_MGMT}/kov/forhandlingar/${PROV_ID}/godkann")
  if [ "$KOD_KOV" = "401" ]; then
    ok "8f2.3 KoV-godkännande utan Authorization-header avvisas (HTTP $KOD_KOV)"
  else
    no "8f2.3 KoV-godkännande utan Authorization-header svarade HTTP $KOD_KOV (förväntat 401)"
  fi
else
  no "8f2.3 förhandlingen dök aldrig upp i KoV-kön – kunde inte köra KoV-negativtestet"
fi

# --- 8f2.4 Mock-markören: stängd i en fristående uppföljningscommit ----
section "8f2.4 Mock-markören 'MEDVETEN FÖRENKLING' i edc/ (testfall 8.4)"
# Bytet till verifierbar identitet bytte ut iam-mock men lämnade MEDVETET
# transfer-proxy-tokens signeringsnyckelpar utanför bytet till verifierbar identitet
# - se docs/08-drift-identitet-skalning.md §8.1, migrationsanteckning 6
# (historik). Ett fynd under bytets sista steg visade att fixen var mindre än
# väntat (data-plane-iam-modulen läser redan nyckelmaterialet via
# vault-alias, aldrig hårdkodat i den generiska EDC-koden), så gapet
# stängdes i en egen, fristående commit EFTER att bytet markerades
# klart - se SvadaTransferProxyNyckelExtension.java. Testfallet förväntar sig nu
# GRÖNT (0 träffar); en regression hit vore en riktig bugg, inte ett
# känt gap.
TRAFFAR=$(grep -rl "MEDVETEN FÖRENKLING" edc/ 2>/dev/null | wc -l | tr -d ' ')
if [ "$TRAFFAR" -eq 0 ]; then
  ok "8f2.4 'MEDVETEN FÖRENKLING' ger noll träffar i edc/ – testfall 8.4 uppfyllt"
else
  no "8f2.4 'MEDVETEN FÖRENKLING' ger fortfarande $TRAFFAR träff(ar) i edc/ – REGRESSION (var stängt)"
fi

# --- 8f2.5 Migrationsanteckningar i journalen ---------------------------
section "8f2.5 Migrationsanteckningar (vad ändras mot produktion) finns"
check "docs/08-drift-identitet-skalning.md §8.1 uppdaterad med migrationsanteckningar (identitetens migrationsanteckningar)" \
  grep -q "Migrationsanteckningar" docs/08-drift-identitet-skalning.md

# --- 8f2.6 Regression: verify_all.sh ------------------------------------
section "8f2.6 Regression (verify_ap0–ap8_fas1)"
# Regressionen körs av tests/verify_all.sh, som kör alla skript i ordning
# (samma mönster som 6a.7/5.9 – körs inte om inline här).
for s in tests/verify_ap0.sh tests/verify_ap1.sh tests/verify_ap3.sh \
         tests/verify_ap4a.sh tests/verify_ap4b.sh tests/verify_ap4c.sh \
         tests/verify_ap6b.sh tests/verify_ap8_fas1.sh; do
  [ -f "$s" ] && ok "regressionsskriptet $s finns" || no "$s saknas"
done

# --- 8f2.7 Identitetsstarten är oberoende av startordningen -------------
# Fynd 2026-10-06: när alla containrar startade
# SAMTIDIGT (Docker-omstart, restart-policy) läste Staden in förra
# körningens attest från vc-utbyte-volymen 0,14 s innan DHI skrivit nya –
# signerade med en nyckel som inte längre fanns – och varje DSP-anrop gav
# ett tyst 401 trots att alla tjänster var "healthy". Rättat i
# SvadaParticipantBootstrapExtension: DHI tar bort den gamla markören
# först, och Staden godtar bara attest som går att verifiera mot
# utfärdarens AKTUELLA DID-dokument. Provet startar om båda
# identitetstjänsterna och båda connectorerna samtidigt och kräver att
# DSP-katalogen svarar. SIST i skriptet: omstarten nollställer
# connectorernas in-memory-tillstånd (registreringen görs om här).
section "8f2.7 Samtidig omstart: identiteten oberoende av startordningen"
P="${SVADA_PREFIX:-svada}"
# Utfärdare med rätt mandat: utfärdaren är en egen hub (Svada), så den startas om tillsammans med
# de andra fyra (fem containrar tillsammans): DHI och Staden ska importera intyg som utfärdaren signerat NU.
FEM="${P}-identity-hub-svada ${P}-identity-hub-dhi ${P}-identity-hub-stad ${P}-edc-provider ${P}-edc-consumer"
for c in ${FEM}; do docker restart "${c}" >/dev/null 2>&1 & done; wait
FRISKA=0
for _ in $(seq 1 90); do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' ${FEM} 2>/dev/null | sort -u)" = "healthy" ]; then
    FRISKA=1; break
  fi
  sleep 2
done
[ "${FRISKA}" = "1" ] && ok "8f2.7 alla fem friska efter samtidig omstart" \
  || no "8f2.7 alla fem blev inte friska efter samtidig omstart"
$DHI --profile edc-bootstrap run --rm registrera-edc >/tmp/svada_ap8fas2_bootstrap2.log 2>&1 \
  || no "8f2.7 registrera-edc misslyckades efter omstarten (se /tmp/svada_ap8fas2_bootstrap2.log)"

# Staden ska ha importerat EFTER Svadas export i den här omstarten.
# Omförsök: `docker logs` kan under belastning ge ofullständigt utdata, och importen kan komma en stund efter exporten.
for _ in 1 2 3 4 5 6 7 8; do
  EXPORT_TID="$(docker logs "${P}-identity-hub-svada" 2>&1 | grep 'attest (deltagare, medlemskap) exporterade' | tail -1 | grep -oE '[0-9]{4}-[0-9-]+T[0-9:.]+' | head -1)"
  IMPORT_TID="$(docker logs "${P}-identity-hub-stad" 2>&1 | grep 'importerat från utfärdaren' | tail -1 | grep -oE '[0-9]{4}-[0-9-]+T[0-9:.]+' | head -1)"
  if [ -n "${EXPORT_TID}" ] && [ -n "${IMPORT_TID}" ] && [[ "${IMPORT_TID}" > "${EXPORT_TID}" ]]; then break; fi
  sleep 4
done
if [ -n "${EXPORT_TID}" ] && [ -n "${IMPORT_TID}" ] && [[ "${IMPORT_TID}" > "${EXPORT_TID}" ]]; then
  ok "8f2.7 Staden importerade attesten efter utfärdarens (Svadas) export (${EXPORT_TID#*T} -> ${IMPORT_TID#*T})"
else
  no "8f2.7 Staden importerade inte efter utfärdarens (Svadas) export (export '${EXPORT_TID}', import '${IMPORT_TID}')"
fi

for _ in 1 2 3 4 5 6; do          # katalogen kan svara 401 en kort stund medan intygen importeras: ett omförsök, inte en snällare kontroll
KATALOG_EFTER="$(curl -s --max-time 40 -X POST "${CONS_MGMT}/v3/catalog/request" \
  -H "X-Api-Key: ${EDC_CONSUMER_MGMT_KEY}" -H 'content-type: application/json' -d "{
    \"@context\": { \"@vocab\": \"https://w3id.org/edc/v0.0.1/ns/\" },
    \"counterPartyId\": \"${EDC_PROVIDER_ID}\",
    \"counterPartyAddress\": \"${PROV_DSP}\",
    \"protocol\": \"${DSP_PROTOKOLL}\"
  }")"
  if echo "${KATALOG_EFTER}" | jq -e '(.["@type"] // "") | test("Catalog")' >/dev/null 2>&1 && ! echo "${KATALOG_EFTER}" | grep -q "CatalogError"; then break; fi
  sleep 5
done
if echo "${KATALOG_EFTER}" | jq -e '(.["@type"] // "") | test("Catalog")' >/dev/null 2>&1 \
   && ! echo "${KATALOG_EFTER}" | grep -q "CatalogError"; then
  ok "8f2.7 DSP-katalogen svarar efter samtidig omstart (inget 401)"
else
  no "8f2.7 DSP-katalogen svarar inte efter samtidig omstart: $(echo "${KATALOG_EFTER}" | head -c 200)"
fi

finish "Verifierbar DCP-identitet"
