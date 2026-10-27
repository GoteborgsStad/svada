#!/usr/bin/env python3
"""
audit.py – auditloggen: en kronologisk händelsekedja över HELA PoC:en.

Ingen komponent äger loggen; dashboarden AGGREGERAR den ur källorna och
normaliserar posterna till samma form. Det är också poängen – i ett riktigt
dataspace ligger spåren hos olika parter, och den som ska kunna svara på
"vem lämnade ut vad till vem, under vilket avtal, och vad hände sedan?"
måste kunna lägga ihop dem.

KÄLLORNA:

  | Led  | Källa                                    | Vad den bidrar med          |
  |------|------------------------------------------|-----------------------------|
  | 3    | consumerns management-API                | förhandlingar och tillstånd |
  | 3    | PROVIDERNS /management/kov/forhandlingar | KoV-besluten (hård regel 7) |
  | 3    | PROVIDERNS /management/kov/avtal         | hävda avtal (avtal-havning) |
  | 4    | transferprocesses (consumer)             | transferarnas utfall        |
  | 4    | ingest-service /leveranser               | kvitton OCH avvisningar     |

Dashboardens EGNA händelser (de knapptryck som utlöst något) läggs till av
jobb.py via `notera()` – de har inget annat hem.
"""

import datetime as dt
import hashlib
import json
import os
import threading

import kallor
import meddelanden
from kallor import KallFel, kallfel
from meddelanden import msg

RETENTION = int(os.environ.get("DASH_AUDIT_RETENTION", "300"))

# Dashboardens egna händelser (knapptryck, jobbutfall).
_EGNA = []
_LAS = threading.Lock()
# Tiden då kontrollrummet förmedlade ett KoV-beslut, per providerns förhandlings-id. Providerns kö saknar beslutstid
# och consumerns förhandling bär ingen tillståndstid; utan den här skulle beslutet få förhandlingens starttid.
_BESLUTSTID = {}

# G10-uppfoljning: HASH-KEDJA ("enkla varianten", 2026-09-02).
#
# Tre krav stalls pa en logg
# som ska kunna bara revision/tvistlosning: (1) overleva omstart,
# (2) vara attribuerbar (= G1, redan stangt genom verifierbar identitet), (3) inte ga att
# skriva om obemarkt. Det som byggs har ar ENDAST (3) - ett bevis pa
# mekanism, INTE en losning pa G10 i sin helhet.
#
# Metoden: samma ide som ett Certificate Transparency-register. Varje NY
# handelse (dedupad pa sitt eget innehall) far en lank
#     lank[n].hash = SHA256(lank[n-1].hash + kanonisk_json(handelse[n]))
# hash_kedja_kontrollera() raknar om HELA kedjan fran den lagrade
# kanoniska texten - inte fran de lagrade hasharna - sa en mixtrad lank
# upptacks oavsett vilket falt som andrats.
#
# STOR RESERVATION - vad detta INTE loser:
#   * Kedjan lever bara i dashboardens process-minne, precis som _EGNA.
#     En omstart av containern nollstaller den helt till genesis. Det ar
#     G10-kravet "overleva omstart" - och det ar INTE lost har. Det
#     kraver persistent lagring, ett kant separat, storre gap.
#   * Kedjan bevisar bara att DASHBOARDENS EGEN redan hamtade vy av en
#     handelse inte andrats i efterhand - INGET om kallorna sjalva.
#   * Root-hashen signeras/publiceras INTE till nagon motpart har - det
#     var nasta steg i resonemanget, inte "enkla varianten".
#   * Nyckeln per handelse ar ett SHA256 av HELA den normaliserade
#     posten (innehalls-adresserad), inte ett ID fran kallan - de flesta
#     av de sex kallorna saknar ett sadant.

_KEDJA = []              # ordnad lista av lankar
_KEDJA_NYCKLAR = {}      # handelse-nyckel -> index i _KEDJA (dedup)
_KEDJA_LAS = threading.Lock()
_KEDJA_GENESIS = "0" * 64


def _kanonisk(handelse):
    """Stabil JSON-strang for en normaliserad handelse (utan kedjans
    egna falt, som annars skulle andra hashen sa fort den kedjats en
    gang). Texten (`text`) ingar INTE: den ar en rendering av `kod` och `p`
    pa ett visst sprak, sa hashen ar densamma oavsett vilket sprak
    nagon tittar pa."""
    stab = {k: v for k, v in handelse.items() if not k.startswith("_kedja") and k != "text"}
    return json.dumps(stab, sort_keys=True, ensure_ascii=False, default=str)


def _hash_kedja_bygg(handelser):
    """Lankar in nya handelser (aldst forst). Redan kedjade handelser
    (samma innehall som en tidigare lank) far bara sin befintliga
    lankinfo kopierad tillbaka - ingen ny lank skapas."""
    with _KEDJA_LAS:
        foregaende = _KEDJA[-1]["hash"] if _KEDJA else _KEDJA_GENESIS
        for h in handelser:
            kanon = _kanonisk(h)
            nyckel = hashlib.sha256(kanon.encode("utf-8")).hexdigest()
            idx = _KEDJA_NYCKLAR.get(nyckel)
            if idx is not None:
                lank = _KEDJA[idx]
                h["_kedjaSeq"] = lank["seq"]
                h["_kedjaHash"] = lank["hash"]
                continue
            ny_hash = hashlib.sha256(
                (foregaende + kanon).encode("utf-8")).hexdigest()
            lank = {"seq": len(_KEDJA), "nyckel": nyckel,
                    "foregaende": foregaende, "kanonisk": kanon,
                    "hash": ny_hash, "tid": h.get("tid"),
                    "led": h.get("led"), "kalla": h.get("kalla")}
            _KEDJA_NYCKLAR[nyckel] = len(_KEDJA)
            _KEDJA.append(lank)
            h["_kedjaSeq"] = lank["seq"]
            h["_kedjaHash"] = ny_hash
            foregaende = ny_hash


def hash_kedja_kontrollera():
    """Raknar om HELA kedjan fran genesis, fran den lagrade kanoniska
    handelsetexten - inte fran de lagrade hasharna - och jamfor. GRONT
    (intakt: true) betyder att ingen lank manipulerats sedan den
    skapades I DEN HAR PROCESSEN. Se STOR RESERVATION ovan for varfor
    det inte ar samma sak som "aldrig manipulerad sedan handelsen
    intraffade i kallan"."""
    with _KEDJA_LAS:
        foregaende = _KEDJA_GENESIS
        for lank in _KEDJA:
            if lank["foregaende"] != foregaende:
                return {"intakt": False, "antalLankar": len(_KEDJA),
                        "trasigLank": lank["seq"],
                        "fel": meddelanden.visa("audit.kedja_foregaende", {"seq": lank["seq"]}, "sv"),
                        "kod": "audit.kedja_foregaende", "p": {"seq": lank["seq"]}}
            ratt_hash = hashlib.sha256(
                (foregaende + lank["kanonisk"]).encode("utf-8")).hexdigest()
            if ratt_hash != lank["hash"]:
                return {"intakt": False, "antalLankar": len(_KEDJA),
                        "trasigLank": lank["seq"],
                        "fel": meddelanden.visa("audit.kedja_hash", {"seq": lank["seq"]}, "sv"),
                        "kod": "audit.kedja_hash", "p": {"seq": lank["seq"]}}
            foregaende = lank["hash"]
        return {"intakt": True, "antalLankar": len(_KEDJA),
                "senasteHash": foregaende}


# ENDAST for tests/verify_hash_kedja.sh - bevisar att
# hash_kedja_kontrollera() FAKTISKT slar larm, genom att lata ett test
# mixtra med en lagrad lank och sedan se att intakt blir false. Nas
# bara via main.py:s POST /api/audit/kedja/test-mixtra/{seq}, som i sin
# tur bara existerar om DASH_AUDIT_KEDJA_TESTLAGE=1 ar satt (se
# main.py) - annars finns endpointen inte alls. ROR ALDRIG en riktig
# driftsatt instans med detta.
def kedja_mixtra_for_test(seq):
    with _KEDJA_LAS:
        if seq < 0 or seq >= len(_KEDJA):
            raise kallfel("audit.kedja_seq", seq=seq, antal=len(_KEDJA))
        gammal = _KEDJA[seq]["hash"]
        ny = "0" * 64 if gammal != "0" * 64 else "f" * 64
        _KEDJA[seq]["hash"] = ny
        return {"seq": seq, "gammalHash": gammal, "nyHash": ny}


def nu():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def notera(led, typ, resultat, kod, p=None, detaljer=None):
    """Skriver en händelse i dashboardens egen del av auditloggen (som kod + parametrar)."""
    post = {"tid": nu(), "led": led, "kalla": "dashboard", "typ": typ,
            "resultat": resultat, "kod": kod, "p": p or {}, "detaljer": detaljer or {}}
    with _LAS:
        _EGNA.append(post)
        del _EGNA[:-RETENTION]
    print("[audit] steg %s %s: %s" % (led, resultat, meddelanden.visa(kod, p or {}, "sv")), flush=True)
    return post


def notera_beslutstid(forhandlings_id):
    with _LAS:
        _BESLUTSTID[forhandlings_id] = nu()
        for gammal in list(_BESLUTSTID)[:-RETENTION]:
            del _BESLUTSTID[gammal]


def egna():
    with _LAS:
        return list(_EGNA)


def _fran_ms(millis):
    if not millis:
        return None
    return dt.datetime.fromtimestamp(millis / 1000.0, dt.timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def _dist(asset):
    """Distributionsbokstaven ur ett asset-id (för läsbarheten i vyn)."""
    if asset == kallor.ASSET_A:
        return "A"
    if asset == kallor.ASSET_B:
        return "B"
    return "?"


def _forhandlingar(handelser, fel):
    try:
        poster = kallor.forhandlingar(limit=40)
    except KallFel as f:
        fel.append(msg("audit.kallfel_forhandlingar", fel=f.meddelande()))
        return {}
    per_id = {}
    for f in poster:
        fid = f.get("@id")
        tid = _fran_ms(f.get("createdAt"))
        per_id[fid] = {"tid": tid, "asset": f.get("assetId")}
        handelser.append({
            "tid": tid, "led": 3, "kalla": "edc-consumer",
            "typ": "kontraktsförhandling",
            # Händelsen är STARTEN och bär starttiden. Förhandlingens nuvarande tillstånd hör inte hit: med starttidens klockslag
            # såg ett senare avslag ut att ha kommit före KoV:s beslut, och posten bytte innehåll (och hash) varje gång
            # tillståndet ändrades (gränssnittstestet 2026-10-18, M6). Utfallet syns i KoV- och avtalshändelserna.
            "resultat": "PABORJAD",
            "kod": "audit.forhandling",
            "p": {"dist": _dist(f.get("assetId")), "asset": f.get("assetId")},
            "detaljer": {"forhandlingId": fid,
                         "avtal": f.get("contractAgreementId"),
                         "motpart": f.get("counterPartyId")}})
    return per_id


def _kov(handelser, per_forhandling, fel):
    try:
        poster = kallor.kov_forhandlingar()
    except KallFel as f:
        fel.append(msg("audit.kallfel_kov", fel=f.meddelande()))
        return
    for p in poster:
        # Kön saknar egen tidsstämpel – ordna efter förhandlingens tid.
        ref = per_forhandling.get(p.get("correlationId")) or {}
        beslut = p.get("kovBeslut")
        # Verifierbar identitet ger providern "beslutsfattare": den kryptografiskt
        # verifierade rollen (SvadaRoleCredential) som godkände/avslog.
        # Tillagd i KovController/KovGate 2026-09-02 – innan dess
        # fanns värdet bara i engångssvaret på POST .../godkann|avsla, inte
        # här i listan denna auditlogg faktiskt läser, så attribuerbarheten
        # (målarkitekturens fjärde invariant) gick förlorad i just den här
        # av auditloggens sex källor.
        beslutsfattare = p.get("beslutsfattare")
        # Kön saknar beslutstid. Ett beslut som gått via kontrollrummet har sin tid noterad; annars (beslut direkt mot
        # providern, eller efter omstart av kontrollrummet) får posten förhandlingens starttid.
        tid = ref.get("tid")
        if beslut in ("GODKAND", "AVSLAGEN"):
            tid = _BESLUTSTID.get(p.get("id")) or tid
        kod = {"VANTANDE": "audit.kov_vantar", "GODKAND": "audit.kov_godkand",
               "AVSLAGEN": "audit.kov_avslagen"}.get(beslut, "audit.kov_annat")
        p_kod = {"beslut": beslut} if kod == "audit.kov_annat" else {}
        if beslutsfattare and beslut in ("GODKAND", "AVSLAGEN"):
            kod += "_roll"
            p_kod["roll"] = beslutsfattare
        handelser.append({
            "tid": tid, "led": 3, "kalla": "edc-provider (KoV-gate)",
            "typ": "policybeslut", "resultat": beslut, "kod": kod, "p": p_kod,
            "detaljer": {"providerForhandling": p.get("id"),
                         "consumerForhandling": p.get("correlationId"),
                         "tillstand": p.get("state"),
                         "pending": p.get("pending"),
                         "avtal": p.get("contractAgreementId"),
                         "orsak": p.get("errorDetail"),
                         "beslutsfattare": beslutsfattare}})


def _havningar(handelser, fel):
    """Hävda avtal ur providerns KoV-grind: vem hävde vad, när och varför."""
    try:
        poster = kallor.kov_avtal()
    except KallFel as f:
        fel.append(msg("audit.kallfel_avtal", fel=f.meddelande()))
        return
    for a in poster:
        h = a.get("havning")
        if a.get("status") != "HAVT" or not h:
            continue
        orsak = {"AVSLAG": msg("audit.orsak_avslag"),
                 "EXPLICIT": msg("audit.orsak_explicit")}.get(h.get("orsak"), meddelanden.fri(h.get("orsak")))
        tid = str(h.get("tid") or "")[:19]
        handelser.append({
            "tid": (tid + "Z") if tid else None, "led": 3,
            "kalla": "edc-provider (KoV-gate)", "typ": "avtal-havt",
            "resultat": "HAVT",
            "kod": "audit.avtal_havt_roll" if h.get("av") else "audit.avtal_havt",
            "p": dict({"dist": _dist(a.get("assetId")), "orsak": orsak}, **({"roll": h["av"]} if h.get("av") else {})),
            "detaljer": {"dhiAvtal": a.get("id"),
                         "orsak": h.get("orsak"),
                         "avslagenForhandling": h.get("forhandlingId")}})


def _transferar(handelser, fel):
    try:
        poster = kallor.transferprocesser(limit=40)
    except KallFel as f:
        fel.append(msg("audit.kallfel_transfer", fel=f.meddelande()))
        return
    for t in poster:
        handelser.append({
            "tid": _fran_ms(t.get("stateTimestamp") or t.get("createdAt")),
            "led": 4, "kalla": "edc-consumer", "typ": "transfer",
            "resultat": t.get("state"),
            "kod": "audit.transfer",
            "p": {"dist": _dist(t.get("assetId")), "typ": t.get("transferType"), "tillstand": t.get("state")},
            "detaljer": {"transferProcessId": t.get("@id"),
                         "avtal": t.get("contractId"),
                         "mal": ("city-intake" if os.environ.get("DEMO_VARIANT") == "extern"
                                 else (t.get("dataDestination") or {}).get("baseUrl"))}})


def _ingest(handelser, fel):
    try:
        svar = kallor.ingest_leveranser()
    except KallFel as f:
        fel.append(msg("audit.kallfel_ingest", fel=f.meddelande()))
        return
    for lev in (svar.get("deliveries") or []):
        resultat = lev.get("resultat")
        inre = (msg(lev["kod"], **(lev.get("parametrar") or {})) if lev.get("kod")
                else meddelanden.fri(lev.get("detalj") or resultat))
        if resultat == "AVVISAD":
            kod, p = "audit.ingest_avvisad", {"orsak": lev.get("orsak"), "detalj": inre}
        else:
            kod, p = inre["kod"], inre["p"]
        handelser.append({
            "tid": lev.get("at"), "led": 4, "kalla": "ingest-service",
            "typ": "leverans", "resultat": resultat, "kod": kod, "p": p,
            "detaljer": {k: v for k, v in lev.items()
                         if k not in ("at", "resultat", "detalj", "kod", "parametrar", "exempelParametrar")}})


def _sortnyckel(post):
    # Poster utan tid (t.ex. en KoV-post vars förhandling fallit ur listan)
    # hamnar först, inte sist – de är alltid äldre än det som händer nu.
    return post.get("tid") or ""


def logg():
    """Hela auditloggen, äldst först."""
    handelser = []
    fel = []
    per_forhandling = _forhandlingar(handelser, fel)
    _kov(handelser, per_forhandling, fel)
    _havningar(handelser, fel)
    _transferar(handelser, fel)
    _ingest(handelser, fel)
    handelser.extend(egna())
    handelser.sort(key=_sortnyckel)
    # Hash-kedjan lankas in FORE retention-avklippet, pa hela mangden
    # kallorna just nu gor synlig - annars tappar en handelse sin lank
    # sa fort den rullar ur de sista RETENTION raderna, trots att den
    # redan hann kedjas in vid ett tidigare anrop.
    _hash_kedja_bygg(handelser)
    # Texten skapas EFTER hashningen: den är en rendering av kod + parametrar (svenska här;
    # engelska i middleware), och ingår inte i det som kedjas.
    for h in handelser:
        h["text"] = meddelanden.visa(h["kod"], h["p"], "sv")
    handelser = handelser[-RETENTION:]
    per_led = {}
    for h in handelser:
        per_led[h["led"]] = per_led.get(h["led"], 0) + 1
    return {"count": len(handelser), "perLed": per_led,
            "kallfel": [dict(m, text=meddelanden.visa(m["kod"], m["p"], "sv")) for m in fel],
            "handelser": handelser,
            "kedja": hash_kedja_kontrollera()}
