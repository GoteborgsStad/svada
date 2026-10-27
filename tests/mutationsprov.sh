#!/usr/bin/env bash
# =====================================================================
# mutationsprov.sh – bevisar att skydd_integration.py faktiskt blir RÖTT när en koppling tas bort
# =====================================================================
# OBS: mutationstexterna avkodas med unicode_escape (för \n). Förankra dem på ASCII-text: å, ä och ö förstörs annars.
# Kopierar services/ och tests/ till en tillfällig katalog, planterar ETT fel i taget i KOPIAN och kör integrationstestet i
# dashboard-imagen utan nätverk. Varje mutation måste ge ett rött test; grönt = testet fångar inte felet (FEL i denna körning).
# Rör inte arbetskopian, inte stacken och inte servern. Kräver bara docker och en byggd dashboard-image.
#   bash tests/mutationsprov.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. tests/lib.sh
P="${SVADA_PREFIX:-svadamini}"
IMG="$(docker inspect "${P}-dashboard" --format '{{.Config.Image}}' 2>/dev/null)"
[ -n "${IMG}" ] || { echo "  [FEL] ingen dashboard-image (${P}-dashboard saknas)"; exit 1; }
KOPIA="$(mktemp -d)"; trap 'rm -rf "${KOPIA}"' EXIT

kor() {  # kor <kopia> -> exit-kod för integrationstestet
  docker run --rm --network none -e DEMO_VARIANT=extern -v "$1/services:/srv:ro" -v "$1/tests:/tst:ro" "${IMG}" \
    python /tst/skydd_integration.py >"$1/utdata.log" 2>&1
}

section "Grundkörning (ingen mutation): ska vara grön"
cp -R services tests "${KOPIA}/" 2>/dev/null
if kor "${KOPIA}"; then ok "omutat kod: grönt (${KOPIA##*/})"; else no "omutat kod är rött – mutationsproven är meningslösa"; fi

mutera() {  # mutera <namn> <fil under services/> <gammal text> <ny text> <förväntat rött avsnitt> [testkommando i kopian]
  local namn="$1" fil="$2" gammal="$3" ny="$4" vilken="$5" prov="${6:-}" d
  d="$(mktemp -d)"; cp -R services tests "${d}/"
  if ! python3 - "${d}/services/${fil}" "${gammal}" "${ny}" <<'PY'
import sys
p, gammal, ny = sys.argv[1], sys.argv[2].encode().decode("unicode_escape"), sys.argv[3].encode().decode("unicode_escape")
s = open(p, encoding="utf-8").read()
if gammal not in s:
    sys.exit(3)
open(p, "w", encoding="utf-8").write(s.replace(gammal, ny, 1))
PY
  then no "${namn}: mutationen kunde inte planteras (texten finns inte i ${fil}); uppdatera mutationsprovet"; rm -rf "${d}"; return; fi
  if [ -n "${prov}" ]; then
    if (cd "${d}" && eval "${prov}" >"${d}/utdata.log" 2>&1); then no "${namn}: testet förblev GRÖNT trots mutationen (${vilken})"
    else ok "${namn}: testet blev rött som väntat ($(grep -c '\[FEL\]' "${d}/utdata.log") kontroller föll; ${vilken})"; fi
    rm -rf "${d}"; return
  fi
  if kor "${d}"; then
    no "${namn}: testet förblev GRÖNT trots mutationen (${vilken})"
  else
    ok "${namn}: testet blev rött som väntat ($(grep -c '^  \[FEL\]' "${d}/utdata.log") kontroller föll; ${vilken})"
  fi
  rm -rf "${d}"
}

section "Mutationer (ett fel i taget i en kopia)"
mutera "M1 städtråden startas aldrig" dashboard/main.py 'threading.Thread(target=_stada_loop, name="stada", daemon=True).start()' 'pass' "uppstarten"
mutera "M2 jobbet markerar inte sitt slut" dashboard/jobb.py 'skydd.jobb_slut(jid)' 'pass' "pausen efter jobb"
mutera "M3 återhämtning efter utestängning ignoreras" dashboard/main.py 'kvar = skydd.avkylning_kvar("ute:" + mottagare)' 'kvar = 0' "429 efter återinsättning"
mutera "M4 avbruten kropp blir tom kropp" dashboard/main.py 'raise Kroppsfel("fel.kropp_avbruten", 400)' 'return {}' "avbruten kropp startar jobb"
mutera "M5 /api/skydd svarar alltid noll" dashboard/main.py 'return skydd.kvar_sekunder(begaran, jobbmodul.aktivt() is not None)' 'return {"utestangningS": {}, "felinjektionS": None, "pausS": 0, "regler": skydd.regler()}' "tickande tider"
mutera "M6 en upprepad utestängning når källan igen" dashboard/main.py '            if mottagare in skydd.UTESTANGDA:\n                return {"redan": True, "mottagare": mottagare, "atgard": atgard}\n' '' "idempotens i rutten"
mutera "M7 kroppsgränsen tas bort" dashboard/main.py 'MAX_KROPP_BYTES = 64 * 1024' 'MAX_KROPP_BYTES = 10**9' "413"
mutera "M8 återhämtning efter felinjektion ignoreras" dashboard/main.py 'kvar = skydd.avkylning_kvar("fel")' 'kvar = 0' "429 efter avslag"
mutera "M9 städningen glömmer posten vid källfel" dashboard/skydd.py '    return inslapp, av\n' '    for m in inslapp:\n        UTESTANGDA.pop(m, None)\n    return inslapp, av\n' "städning med källfel"
mutera "M10 Förhandla B visar rå 502 när staden nekas" dashboard/jobb.py 'raise Jobbfel("fel.stad_nekad_dhi")' 'raise' "klartext vid utestängd stad"


section "Del a2: en mutation per rättning (ska alla ge rött)"
mutera "M11 Svada-rutten läser inte kroppen (A2-01)" dashboard/main.py '        await las_json_kropp(begaran, tillat_tom=True)      # A2-01: ingen' '        pass  # A2-01: ingen' "kroppsmatrisen"
mutera "M12 inget lås kring utestängningen (A2-02)" dashboard/main.py '    with skydd.STORNINGSLAS["ute:" + mottagare]:\n        if proxy and atgard == "aterkalla":' '    if True:\n        if proxy and atgard == "aterkalla":' "korsande anrop"
mutera "M13 nollställningen tar inte felinjektionens lås (A2-02)" dashboard/main.py 'def _nollstall_fel_synk():\n    with skydd.STORNINGSLAS["fel"]:' 'def _nollstall_fel_synk():\n    if True:' "nollställning mot påslagning"
mutera "M14 städningen prövar inte fristen igen under låset (A2-02)" dashboard/main.py '                if not skydd.utestangning_forfallen(m):\n                    continue\n' '' "gammal ögonblicksbild"
mutera "M15 antagningen prövar inte pausen (A2-04)" dashboard/main.py '    if proxy:\n        sek = skydd.vanta_efter_jobb(begaran, jobbmodul.aktivt() is not None)\n        if sek:\n            return _fel_svar(jobbmodul.Jobbfel("fel.vanta", sek=sek), 429, vantaSek=sek)\n    try:\n        jobb = jobbmodul.starta(' '    try:\n        jobb = jobbmodul.starta(' "kropp öppen över jobbslutet"
mutera "M16 felinjektionens källanrop i händelseloopen (A2-05)" dashboard/main.py 'return await run_in_threadpool(_satt_fel_synk, kropp, _EXTERN and skydd.via_proxy(begaran))' 'return _satt_fel_synk(kropp, _EXTERN and skydd.via_proxy(begaran))' "ticker"
mutera "M17 felklassning på fri text igen (A2-06)" dashboard/jobb.py '    return getattr(fel, "status", None) == 502 and bool(_DSP_NEKAD.search(str(getattr(fel, "kropp", "") or "")))' '    return getattr(fel, "status", None) in (401, 502) and bool(re.search(r"\\b401\\b|Unauthorized", str(getattr(fel, "kropp", "") or "")))' "felklassningstabellen"
mutera "M18 KoV-jobbens id prövas inte före antagning (A2-01)" dashboard/jobb.py '    if atgard in _KRAVER_ID and not' '    if False and not' "felaktigt id"
mutera "M19a förutsägbar platshållare i rensningen (A2-07)" gemensam/rensa.py '        nyckel = uuid.uuid4().hex' '        nyckel = "abc"' "platshållaren går att förfalska" "python3 tests/kedjevy_rendering.py"
mutera "M19b ingen URL-gräns för publik bas (A2-07)" gemensam/rensa.py '(?=[/?#' '(?=|[/?#' "prefix och userinfo" "python3 tests/kedjevy_rendering.py"
if command -v node >/dev/null 2>&1 && [ -d tools/node_modules/playwright-core ]; then
  mutera "M20 id i onclick igen (A2-03)" dashboard/vy.py '<button class="kor fara" data-hav-id="${esc(a.dhiAvtalId)}">' '<button class="kor fara" onclick="kovHav('"'"'${esc(a.dhiAvtalId)}'"'"')">' "isolerad webbläsarfixtur" \
    "mkdir -p tools && ln -sf '${PWD}/tools/node_modules' tools/node_modules && node tests/vy_handelser_webblasare.mjs"
else
  no "M20 kräver node och playwright-core (cd tools && npm install)"
fi

section "Gränssnittstestet 2026-10-18: M6, M7, M8"
mutera "M21 Följ ett värde steg 4 tar senaste leveransen igen (M7)" dashboard/steg.py '           "senaste": (egna or poster)[-1]}' '           "senaste": poster[-1]}' "kvittot för trådens avtal" "python3 tests/kedjevy_rendering.py"
mutera "M22 auditens förhandlingsstart bär nuvarande tillstånd igen (M6)" dashboard/audit.py '            "resultat": "PABORJAD",' '            "resultat": f.get("state"),' "förhandlingsstart utan senare tillstånd" "python3 tests/kedjevy_rendering.py"
if command -v node >/dev/null 2>&1 && [ -d tools/node_modules/playwright-core ]; then
  mutera "M23 dold flik läses aldrig om (M8)" dashboard/vy.py '    if (document.hidden && Date.now() - svadaSenast < 15000) return;' '    if (document.hidden) return;' "dold flik i fixturen" \
    "mkdir -p tools && ln -sf '${PWD}/tools/node_modules' tools/node_modules && node tests/vy_handelser_webblasare.mjs"
fi

if command -v node >/dev/null 2>&1 && [ -d tools/node_modules/playwright-core ]; then
  FIXTUR="mkdir -p tools && ln -sf '${PWD}/tools/node_modules' tools/node_modules && node tests/vy_handelser_webblasare.mjs"
  mutera "M24 hävning utan bekräftelse (M2)" dashboard/vy.py '  if (hb) { if (bekraftat(hb, BEKRAFTA_HAV())) kovHav(hb.dataset.havId); return; }' '  if (hb) { kovHav(hb.dataset.havId); return; }' "ett klick häver" "${FIXTUR}"
  mutera "M25 flikbyten utan historik (M3)" dashboard/vy.py "history.pushState(null, '', '#' + hash);" "history.replaceState(null, '', '#' + hash);" "Bakåt" "${FIXTUR}"
  mutera "M26 loggen väntar på kön igen (M3)" dashboard/vy.py '  ritaJobb(data);\n  await uppdateraVantande();\n  ritaJobb(data);' '  await uppdateraVantande();\n  ritaJobb(data);' "gammal logg efter hopp" "${FIXTUR}"
fi

mutera "M27 spärrens nekande visas som misslyckat igen (L1)" dashboard/jobb.py '                jobb.utfall = "nekad"' '                pass' "utfallet nekad"
mutera "M30 KoV:s avslag avslutar inte jobbet som 'inget avtal' (webinariet p2)" dashboard/jobb.py '                jobb.utfall = "inget-avtal"\n                jobb.logg("jobb.avslag_orsak"' '                jobb.logg("jobb.avslag_orsak"' "KoV avslår"
mutera "M31 ett hävt avtal ger MISSLYCKADES i stället för nekad (webinariet p2)" dashboard/jobb.py 'SPARR_KODER = ("fel.inget_avtal", "fel.inget_avtal_kov", "fel.avtal_havt", "fel.avtal_utgangit", ' 'SPARR_KODER = ("fel.inget_avtal", "fel.inget_avtal_kov", ' "Leverera A (fel.avtal_havt)"
mutera "M32 spärren mot utestängning via Caddy tas bort (externt avstängd)" dashboard/main.py '    if not UTESTANGNING_TILLATEN and skydd.via_proxy(begaran):' '    if False and skydd.via_proxy(begaran):' "avsnitt 4b: återkallelse via Caddy ska nekas"
mutera "M33 spärren stänger även anrop direkt mot porten (testerna)" dashboard/main.py '    if not UTESTANGNING_TILLATEN and skydd.via_proxy(begaran):' '    if not UTESTANGNING_TILLATEN:' "avsnitt 4b: direktanrop ska inte beröras"
mutera "M34 utestängningen är på som standard i extern variant" dashboard/main.py 'os.environ.get("DASH_UTESTANGNING", "nej" if _EXTERN else "ja") == "ja"' 'os.environ.get("DASH_UTESTANGNING", "ja") == "ja"' "avsnitt 4b: standardvärdet i extern variant"
mutera "M28 tomma objekt i Följ ett värde igen (L15)" dashboard/steg.py '        if isinstance(tolkat, dict) and _tomt(tolkat):' '        if False:' "Inget ännu" "python3 tests/kedjevy_rendering.py"

section "Mutation i skydd.py:s eget lager (täcks av enhetstestet skydd_enhet.py, inte av integrationstestet)"
D="$(mktemp -d)"; cp -R services tests "${D}/"
if python3 - "${D}/services/dashboard/skydd.py" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
gammal = "        if mottagare in UTESTANGDA:\n            return False\n"
if gammal not in s: sys.exit(3)
open(p, "w", encoding="utf-8").write(s.replace(gammal, "", 1))
PY
then
  if (cd "${D}" && python3 -I tests/skydd_enhet.py >"${D}/enhet.log" 2>&1); then no "M6b en upprepad utestängning skriver över starttiden: enhetstestet förblev GRÖNT"
  else ok "M6b en upprepad utestängning skriver över starttiden: enhetstestet blev rött ($(grep -c '\[FEL\]' "${D}/enhet.log") kontroller föll)"; fi
else no "M6b: mutationen kunde inte planteras"; fi
rm -rf "${D}"

finish "mutationsprov"
