#!/usr/bin/env bash
# =====================================================================
# verify_ap3.sh – FCF-simulatorn (dataprodukten Modellerad bräddata)
# Prövar testfallen 3.1–3.9: kuvert, klassning, felinjektion och nätisolering.
# =====================================================================
# Självständigt och idempotent: startar profilen dhi-fcf vid behov och väntar in
# första batchen. Svada-mini: FCF läser brunn 4526:s CSV-filer direkt (inget sensorled). Lämnar ALLTID felinjektionen avstängd när det är klart.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 99
. tests/lib.sh

echo "#### FCF-simulatorn ####"

# Portkartan/konfigurationen ur .env (enda källan, hård regel 5).
set -a; . ./.env; set +a

FCF="http://localhost:${FCF_SIM_PORT}"
COMPOSE="docker compose -f compose.dhi.yml"

# Krokängsparkens koordinater ur gpkg:n – används för att leta efter
# brunns-GIS i Distribution B (3.4).
KROK_LON="11.99184"
KROK_LAT="57.69434"

docker network inspect ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1 \
  || docker network create ${SVADA_PREFIX:-svada}-dsp-public >/dev/null 2>&1

vanta_fcf() {
  for _ in $(seq 1 "${1:-90}"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${FCF}/health")" \
      = "200" ] && return 0
    sleep 1
  done
  return 1
}

antal_batchar() {
  curl -s --max-time 10 "${FCF}/health" | jq '.batches // 0' 2>/dev/null || echo 0
}

felinjektion() {   # felinjektion '{"schemadrift":true}'
  curl -s --max-time 10 -X POST "${FCF}/felinjektion" \
    -H 'Content-Type: application/json' -d "$1"
}

# --- Förutsättningar ---------------------------------------------------
section "Förutsättningar (startar dhi-fcf vid behov)"
if vanta_fcf 3; then
  ok "fcf-sim var redan uppe"
else
  echo "  (startar profilen dhi-fcf ...)"
  $COMPOSE --profile dhi-fcf up -d >/dev/null 2>&1
  if vanta_fcf 180; then ok "fcf-sim uppe"; else no "fcf-sim startade inte"; fi
fi
# Vänta in den första batchen (warmup + modellering).
for _ in $(seq 1 120); do
  [ "$(antal_batchar)" -ge 1 ] 2>/dev/null && break
  sleep 1
done
[ "$(antal_batchar)" -ge 1 ] 2>/dev/null \
  && ok "första batchen producerad" || no "ingen batch producerad inom 2 min"
# Utgå ALLTID från ett rent läge (skriptet kan ha avbrutits mitt i 3.6/3.7).
curl -s -X POST "${FCF}/felinjektion/reset" >/dev/null 2>&1

# --- 3.1 API friskt ----------------------------------------------------
section "3.1 Dataplans-API:t är friskt"
kod=$(curl -s -o /tmp/ap3_health.json -w '%{http_code}' --max-time 10 "${FCF}/health")
if [ "$kod" = "200" ]; then
  ok "3.1 GET /health -> 200"
  jq -c . /tmp/ap3_health.json | sed 's/^/        /'
else
  no "3.1 GET /health -> $kod"
fi
if jq -e '.weirs == 91' /tmp/ap3_health.json >/dev/null 2>&1; then
  ok "3.1 brunnsregistret laddat ur gpkg:n (91 brunnar)"
else
  no "3.1 fel antal brunnar i registret"
fi
# Båda distributionerna ska annonseras med rätt accessRights.
dl=$(curl -s --max-time 10 "${FCF}/distributions")
if printf '%s' "$dl" | jq -e '
     ([.distributions[] | select(.distribution=="A")
       | .accessRights == "non-public" and .containsWeirGis] | all) and
     ([.distributions[] | select(.distribution=="B")
       | .accessRights == "public" and (.containsWeirGis | not)] | all)
   ' >/dev/null 2>&1; then
  ok "3.1 /distributions: A=non-public (med GIS), B=public (utan GIS)"
else
  no "3.1 distributionslistans metadata är fel: $dl"
fi

# --- 3.2 Batchen täcker alla 91 brunnar --------------------------------
section "3.2 Batchen täcker alla 91 brunnar"
curl -s --max-time 30 "${FCF}/distributions/a/latest" > /tmp/ap3_a.json
curl -s --max-time 30 "${FCF}/distributions/b/latest" > /tmp/ap3_b.json
for d in a b; do
  # tr i stället för ${d^^}: versal-expansion kräver bash 4+, och macOS
  # stock /bin/bash är 3.2.
  D=$(printf '%s' "$d" | tr '[:lower:]' '[:upper:]')
  n=$(jq '[.records[].weirId] | unique | length' "/tmp/ap3_${d}.json" 2>/dev/null)
  if [ "${n:-0}" = "91" ]; then
    ok "3.2 Distribution ${D}: 91 unika brunnar"
  else
    no "3.2 Distribution ${D}: ${n:-0} unika brunnar (förväntat 91)"
  fi
done
jq -c '{batchId,modelledDay,batchClock,measurementSource}' /tmp/ap3_a.json \
  | sed 's/^/        /'

# --- 3.3 Distribution A har brunns-GIS ---------------------------------
section "3.3 Distribution A innehåller brunnarnas GIS-position"
if jq -e '[.records[] | select(.location.type == "Point"
     and (.location.coordinates | length) == 2)] | length == 91' \
     /tmp/ap3_a.json >/dev/null 2>&1; then
  ok "3.3 alla 91 poster i A har en GeoJSON-punkt"
else
  no "3.3 poster i A saknar giltig location"
fi
if jq -e --arg lon "$KROK_LON" --arg lat "$KROK_LAT" '
     .records[] | select(.weirId == "SSO1_01-4526")
     | (.location.coordinates[0] | tostring | startswith($lon[0:9]))
       and (.location.coordinates[1] | tostring | startswith($lat[0:9]))' \
     /tmp/ap3_a.json >/dev/null 2>&1; then
  ok "3.3 Krokängsparkens koordinat i A stämmer mot gpkg:n"
else
  no "3.3 Krokängsparkens koordinat i A är fel: $(jq -c '.records[]|select(.weirId=="SSO1_01-4526")|.location' /tmp/ap3_a.json)"
fi
if jq -e '[.records[] | select(has("sourceSrs"))] | length == 91' \
     /tmp/ap3_a.json >/dev/null 2>&1; then
  ok "3.3 ursprungs-SRS (EPSG:4619) följer med i A"
else
  no "3.3 sourceSrs saknas i A"
fi

# --- 3.4 Distribution B saknar brunns-GIS ------------------------------
section "3.4 Distribution B saknar brunns-GIS (integritetslöftet)"
n=$(jq '[.records[] | select(has("location") or has("sourceSrs"))] | length' \
     /tmp/ap3_b.json)
if [ "$n" = "0" ]; then
  ok "3.4 0 poster i B har fälten location/sourceSrs"
else
  no "3.4 $n poster i B har brunns-GIS kvar"
fi
# Hårdare kontroll: leta efter brunnskoordinaterna som RÅTEXT i hela B:s
# nyttolast (ett omdöpt fält skulle annars slinka igenom).
if grep -q "$KROK_LON" /tmp/ap3_b.json || grep -q "$KROK_LAT" /tmp/ap3_b.json; then
  no "3.4 brunnskoordinater hittades som råtext i B"
else
  ok "3.4 brunnarnas koordinater finns inte som råtext någonstans i B"
fi
# ... men utsläppspunkt och recipient SKA ligga kvar.
if jq -e '[.records[] | select(.outlet.name != null
     and .outlet.location.type == "Point" and .recipient != null)]
     | length == 91' /tmp/ap3_b.json >/dev/null 2>&1; then
  ok "3.4 utsläppspunkt (med koordinat) och recipient finns kvar i alla poster"
else
  no "3.4 utsläppspunkt/recipient saknas i B: $(jq -c '.records[0]|{outlet,recipient}' /tmp/ap3_b.json)"
fi
# Modellresultatet måste finnas i B – annars är distributionen värdelös.
if jq -e '[.records[] | select(has("overflowVolumeM3") and has("overflowDurationMin")
     and has("inflowMeanM3S") and has("waterLevelMaxM"))] | length == 91' \
     /tmp/ap3_b.json >/dev/null 2>&1; then
  ok "3.4 modellparametrarna (bräddvolym/-tid, tillrinning, nivå) finns i B"
else
  no "3.4 modellparametrar saknas i B"
fi

# --- 3.x Modellen är rimlig (bräddmodellens invarianter) ---------------
section "3.x Bräddmodellens invarianter"
python3 - <<'PY'
import json, sys

a = json.load(open("/tmp/ap3_a.json"))
poster = a["records"]
fel = 0

braddande = [p for p in poster if p["overflowVolumeM3"] > 0]
if not 1 <= len(braddande) < len(poster):
    print(f"  [FEL] 3.x orimligt: {len(braddande)} av {len(poster)} brunnar bräddar")
    fel += 1
else:
    print(f"  [OK]  3.x {len(braddande)} av {len(poster)} brunnar bräddar detta dygn")

for p in poster:
    # Bräddflödet kan aldrig överstiga totalflödet genom brunnen.
    if p["overflowPeakM3S"] > p["inflowPeakM3S"] + 1e-9:
        print(f"  [FEL] 3.x {p['weirId']}: bräddflöde > tillrinning")
        fel += 1
        break
    # Nivån ska följa överfallsformeln h = (Q/(C*b))^(2/3), C=1,7 b=1,0.
    vantad = (p["overflowPeakM3S"] / 1.7) ** (2 / 3) if p["overflowPeakM3S"] > 0 else 0.0
    if abs(p["waterLevelMaxM"] - vantad) > 1e-3:
        print(f"  [FEL] 3.x {p['weirId']}: nivå {p['waterLevelMaxM']} != {vantad:.4f}")
        fel += 1
        break
    # Bräddvolym > 0 kräver bräddtid > 0 och tvärtom.
    if (p["overflowVolumeM3"] > 0) != (p["overflowDurationMin"] > 0):
        print(f"  [FEL] 3.x {p['weirId']}: volym och varaktighet är inkonsekventa")
        fel += 1
        break
else:
    print("  [OK]  3.x alla poster: bräddflöde <= tillrinning, nivå enligt "
          "överfallsformeln, volym/varaktighet konsekventa")

sensor = [p for p in poster if p["weirId"] == "SSO1_01-4526"]
if not sensor:
    print("  [FEL] 3.x sensorbrunnen SSO1_01-4526 saknas i batchen")
    fel += 1
elif sensor[0]["dataSource"].startswith("measured"):
    print(f"  [OK]  3.x sensorbrunnen bygger på mätvärden ur CSV-filerna "
          f"(dataSource={sensor[0]['dataSource']}, "
          f"täckning={sensor[0].get('measuredCoverage')})")
else:
    print(f"  [FEL] 3.x sensorbrunnens dataSource är {sensor[0]['dataSource']} "
          "– mätvärdena nådde inte fram")
    fel += 1

syntetiska = [p for p in poster if p["dataSource"] == "modelled-synthetic"]
if len(syntetiska) == 90 and all("syntheticScale" in p for p in syntetiska):
    print("  [OK]  3.x de 90 sensorlösa brunnarna är märkta som syntetiska "
          "med redovisad skalfaktor")
else:
    print(f"  [FEL] 3.x {len(syntetiska)} syntetiska poster (förväntat 90)")
    fel += 1

sys.exit(1 if fel else 0)
PY
if [ $? -ne 0 ]; then FAIL=$((FAIL+1)); fi

# --- 3.5 Batchproduktion -----------------------------------------------
section "3.5 Ny batch produceras (daglig batch, komprimerat intervall)"
fore_id=$(jq -r '.batchId' /tmp/ap3_a.json)
fore_tid=$(jq -r '.producedAt' /tmp/ap3_a.json)
ny=$(curl -s --max-time 60 -X POST "${FCF}/batches/run")
efter_id=$(printf '%s' "$ny" | jq -r '.batchId')
efter_tid=$(printf '%s' "$ny" | jq -r '.producedAt')
if [ "$efter_id" != "$fore_id" ] && [ "$efter_tid" \> "$fore_tid" ]; then
  ok "3.5 ny batch: $fore_id ($fore_tid) -> $efter_id ($efter_tid)"
else
  no "3.5 ingen ny batch producerades ($fore_id / $efter_id)"
fi
if [ "$(curl -s "${FCF}/distributions/a/latest" | jq -r '.batchId')" = "$efter_id" ] \
   && [ "$(curl -s "${FCF}/distributions/b/latest" | jq -r '.batchId')" = "$efter_id" ]; then
  ok "3.5 /latest pekar på den nya batchen i BÅDA distributionerna"
else
  no "3.5 /latest följde inte med till den nya batchen"
fi
# Modellerat dygn ska stega framåt och den gamla batchen finnas kvar i listan.
if curl -s "${FCF}/distributions/b/batches" \
     | jq -e --arg b "$fore_id" '[.batches[].batchId] | index($b) != null' \
     >/dev/null 2>&1; then
  ok "3.5 den tidigare batchen finns kvar och är hämtbar via /batches"
else
  no "3.5 den tidigare batchen försvann ur batchlistan"
fi
if curl -s "${FCF}/distributions/a/batches" \
     | jq -e '[.batches[].modelledDay] | . == (. | unique)' >/dev/null 2>&1; then
  ok "3.5 varje batch modellerar ett eget dygn (kl-05-batchen)"
else
  no "3.5 flera batchar modellerar samma dygn"
fi

# 3.5b Räknaren "Producerade batchar" i kontrollrummet är löpnumret, inte antalet sparade batchar (högst
# FCF_BATCH_RETENTION). Gränssnittstestet 2026-10-17 fann att den stod still på 10 trots nya batchar.
HEALTH_B="$(curl -s --max-time 10 "${FCF}/health")"
TOTALT_B="$(printf '%s' "${HEALTH_B}" | jq -r '.batchesTotal // empty')"
LOPNR_B="$(printf '%s' "${HEALTH_B}" | jq -r '.latestBatchId // empty' | sed -E 's/^batch-0*([0-9]+)-.*/\1/')"
SPARADE_B="$(printf '%s' "${HEALTH_B}" | jq -r '.batches // empty')"
if [ -n "${TOTALT_B}" ] && [ "${TOTALT_B}" = "${LOPNR_B}" ] && [ "${TOTALT_B}" -ge "${SPARADE_B}" ]; then
  ok "3.5b /health: batchesTotal (${TOTALT_B}) är senaste batchens löpnummer och minst så stort som antalet sparade (${SPARADE_B})"
else
  no "3.5b /health: batchesTotal=${TOTALT_B:-saknas}, senaste löpnummer=${LOPNR_B:-saknas}, sparade=${SPARADE_B:-saknas}"
fi

# --- 3.6 Felinjektion: schemadrift + saknade parametrar ----------------
section "3.6 Felinjektion: schemadrift och saknade parametrar"
felinjektion '{"schemadrift":true}' >/dev/null
b_drift=$(curl -s --max-time 30 "${FCF}/distributions/b/latest")
if printf '%s' "$b_drift" | jq -e '
     [.records[] | select(has("bradd_volym_m3") and (has("overflowVolumeM3") | not)
       and has("tillrinning_medel_m3s"))] | length == 91' >/dev/null 2>&1; then
  ok "3.6 schemadrift: overflowVolumeM3 -> bradd_volym_m3, inflowMeanM3S -> tillrinning_medel_m3s"
else
  no "3.6 schemadriften slog inte igenom: $(printf '%s' "$b_drift" | jq -c '.records[0]' | head -c 300)"
fi
if curl -s "${FCF}/felinjektion" | jq -e '.aktiv and .lagen.schemadrift' >/dev/null 2>&1; then
  ok "3.6 /felinjektion redovisar aktivt läge"
else
  no "3.6 /felinjektion redovisar inte läget"
fi
felinjektion '{"schemadrift":false,"saknade_parametrar":true}' >/dev/null
b_saknad=$(curl -s --max-time 30 "${FCF}/distributions/b/latest")
if printf '%s' "$b_saknad" | jq -e '
     [.records[] | select((has("overflowDurationMin") | not)
       and (has("unitCodes") | not) and has("overflowVolumeM3"))]
     | length == 91' >/dev/null 2>&1; then
  ok "3.6 saknade parametrar: overflowDurationMin och unitCodes är borta"
else
  no "3.6 fältborttagningen slog inte igenom"
fi
# Felinjektionen får INTE annonsera sig i nyttolasten – ingest-tjänstens validering
# ska upptäcka felet själv.
if printf '%s' "$b_saknad" | grep -qi "felinjek\|fault"; then
  no "3.6 nyttolasten skvallrar om felinjektionen (mottagarens kontroll skulle fuska)"
else
  ok "3.6 nyttolasten innehåller ingen flagga om manipulationen"
fi

# --- 3.7 Felinjektion: avtalsbrott (GIS kvar i B) ----------------------
section "3.7 Felinjektion: avtalsbrott – brunns-GIS kvar i Distribution B"
felinjektion '{"saknade_parametrar":false,"gis_i_b":true}' >/dev/null
b_gis=$(curl -s --max-time 30 "${FCF}/distributions/b/latest")
if printf '%s' "$b_gis" | jq -e \
     '[.records[] | select(.location.type == "Point")] | length == 91' \
     >/dev/null 2>&1; then
  ok "3.7 B innehåller nu brunns-GIS i alla 91 poster (ska fångas av mottagarens kontroll)"
else
  no "3.7 avtalsbrottsläget gav inget GIS i B"
fi
if printf '%s' "$b_gis" | grep -q "$KROK_LON"; then
  ok "3.7 Krokängsparkens exakta koordinat läcker (avtalsbrottet är verkligt)"
else
  no "3.7 koordinaten läckte inte – felinjektionen är ofarlig"
fi
# Distribution A ska vara oförändrad av B-felet.
if curl -s "${FCF}/distributions/a/latest" \
     | jq -e '[.records[] | select(.location.type == "Point")] | length == 91' \
     >/dev/null 2>&1; then
  ok "3.7 Distribution A är opåverkad"
else
  no "3.7 Distribution A skadades av felinjektionen"
fi

# --- 3.8 Felinjektion AV som default -----------------------------------
section "3.8 Felinjektionen är AV som default"
curl -s -X POST "${FCF}/felinjektion/reset" >/dev/null
b_ren=$(curl -s --max-time 30 "${FCF}/distributions/b/latest")
# OBS jq-precedens: "|" binder lösare än "and", så villkoren måste stå som
# två separata uttryck (annars utvärderas det andra mot fel indata).
if printf '%s' "$b_ren" | jq -e '
     ([.records[] | select(has("location") or has("sourceSrs"))] | length) == 0
     and ([.records[] | select(has("overflowVolumeM3")
           and has("overflowDurationMin") and has("unitCodes"))] | length) == 91
   ' >/dev/null 2>&1; then
  ok "3.8 efter reset är B åter GIS-fri och schemat intakt (3.4 igen)"
else
  no "3.8 B återställdes inte efter felinjektionen"
fi
for v in FCF_FAULT_SCHEMA_DRIFT FCF_FAULT_MISSING_FIELDS FCF_FAULT_GIS_IN_B; do
  if [ "$(eval echo \$$v)" = "false" ]; then
    ok "3.8 .env: $v=false (av som default)"
  else
    no "3.8 .env: $v är påslaget"
  fi
done
if docker inspect ${SVADA_PREFIX:-svada}-fcf-sim --format '{{json .Config.Env}}' 2>/dev/null \
   | grep -q '"FCF_FAULT_GIS_IN_B=false"'; then
  ok "3.8 den körande containern har felinjektionen avstängd i env"
else
  no "3.8 containerns env har felinjektionen påslagen"
fi

# --- 3.x Resurstak (resursstrategin, hård regel 3) --------------------------------
section "3.x Resurstak och nätverksgräns"
mem=$(docker inspect ${SVADA_PREFIX:-svada}-fcf-sim --format '{{.HostConfig.Memory}}' 2>/dev/null)
if [ "${mem:-0}" -gt 0 ] 2>/dev/null; then
  ok "3.x mem_limit satt på ${SVADA_PREFIX:-svada}-fcf-sim ($((mem/1024/1024)) MiB)"
else
  no "3.x mem_limit saknas på ${SVADA_PREFIX:-svada}-fcf-sim"
fi
# Hård regel 8: fcf-sim ligger inte på det publika DSP-nätet – Distribution A
# får bara nå ut via EDC:ns kontrakt.
if docker inspect ${SVADA_PREFIX:-svada}-fcf-sim \
     --format '{{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{end}}' \
     2>/dev/null | grep -q "dsp-public"; then
  no "3.x fcf-sim ligger på det publika DSP-nätet (hård regel 8)"
else
  ok "3.x fcf-sim ligger enbart på DHI:s interna nät"
fi

# --- 3.9 Regression ----------------------------------------------------
section "3.9 Regression"
ok "3.9 hanteras av tests/verify_all.sh (kör ap0, ap1, ap2 och ap3 i ordning)"

finish "verify_ap3"
