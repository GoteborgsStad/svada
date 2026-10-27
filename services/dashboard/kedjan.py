#!/usr/bin/env python3
"""
kedjan.py – de flöden dashboarden kan UTLÖSA (till skillnad från att läsa).

Allt här är samma sekvenser som tests/verify_ap4b.sh och verify_ap4c.sh kör
med curl (förhandlingsflödet). Att de
finns i två implementationer är avsiktligt: verifieringen ska kunna fälla
dashboarden, inte dela kod med den.

Flödena:
  * hamta_katalog / offert       – DSP-katalogen och ODRL-offerterna
  * forhandla / vanta_avtal      – kontraktsförhandling (B auto, A gate:ad)
  * kor_transfer                 – transfer + ingest-kvitto (med omtag)
  * villkor_a                   – villkoren för Distribution A (läsning)

HÅRD REGEL 7: KoV-beslutet fattas på PROVIDERNS management-API. Den enda
vägen dit i den här filen går via kallor.kov_beslut() mot port 19193 –
consumerns API har ingen sådan endpoint alls (testfall 4b.4).
"""

import time

import kallor
from kallor import KallFel, kallfel
import meddelanden

# Hur länge flödena väntar. Samma storleksordning som verifieringsskripten.
VANTA_AVTAL_S = 90
VANTA_TRANSFER_S = 90
VANTA_KVITTO_S = 40
# GOTCHA: startas en ny transfer direkt efter
# en misslyckad dör pushen i providerns dataplan med "IOException: closed".
ANDRUM_S = 20


def _dataset_lista(katalog):
    ds = katalog.get("dataset") or katalog.get("dcat:dataset") or []
    return [ds] if isinstance(ds, dict) else list(ds)


def _policyer(dataset):
    p = dataset.get("hasPolicy") or dataset.get("odrl:hasPolicy") or []
    return [p] if isinstance(p, dict) else list(p)


def hamta_katalog():
    return kallor.dsp_katalog()


def dataset_for(katalog, asset):
    for d in _dataset_lista(katalog):
        if d.get("@id") == asset:
            return d
    raise kallfel("kallfel.asset_saknas", asset=asset)


def offert_for(katalog, asset):
    policyer = _policyer(dataset_for(katalog, asset))
    if not policyer:
        raise kallfel("kallfel.offert_saknas", asset=asset)
    return policyer[0]


def forhandla(asset, katalog=None):
    """Startar en kontraktsförhandling och returnerar consumerns förhandlings-id.

    GOTCHA: policyn i ContractRequest måste
    vara HELA katalogofferten plus assigner och target. Skickar man bara
    dess @id terminerar consumern förhandlingen på PolicyEquality.
    """
    katalog = katalog or hamta_katalog()
    offert = dict(offert_for(katalog, asset))
    offert["@context"] = ["http://www.w3.org/ns/odrl.jsonld",
                          {"svada": "https://svada.goteborg.se/ns/"}]
    offert["assigner"] = kallor.PROVIDER_ID
    offert["target"] = asset
    svar = kallor.anrop(
        kallor.url("edc_consumer_mgmt", "/management/v3/contractnegotiations"),
        "POST", {
            "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
            "@type": "ContractRequest",
            "counterPartyAddress": kallor.PROVIDER_DSP,
            "protocol": kallor.DSP_PROTOKOLL,
            "policy": offert},
        headers=kallor.EDC_CONSUMER_MGMT_HUVUD, timeout=30)
    fid = svar.get("@id")
    if not fid:
        raise kallfel("kallfel.ingen_forhandling", svar=str(svar)[:300])
    return fid


def vanta_avtal(forhandlings_id, sekunder=VANTA_AVTAL_S):
    """Pollar tills förhandlingen har ett avtal. None = inget avtal (ännu)."""
    slut = time.time() + sekunder
    tillstand = "?"
    while time.time() < slut:
        f = kallor.forhandling(forhandlings_id)
        tillstand = f.get("state")
        avtal = f.get("contractAgreementId")
        if avtal:
            # Avtalet får sitt id redan i VERIFIED; vänta (högst 20 s) in
            # FINALIZED så att loggen och texten i vyn säger samma sak.
            for _ in range(10):
                if tillstand == "FINALIZED":
                    break
                time.sleep(2)
                tillstand = kallor.forhandling(forhandlings_id).get("state")
            return avtal, tillstand
        if tillstand == "TERMINATED":
            return None, tillstand
        time.sleep(2)
    return None, tillstand


def kov_kon():
    return kallor.kov_forhandlingar()


def kov_post_for(correlation_id):
    """Providerns kö-id för en av consumerns förhandlingar."""
    for f in kov_kon():
        if f.get("correlationId") == correlation_id:
            return f
    return None


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------
def _senaste_kvitto():
    poster = (kallor.ingest_leveranser().get("deliveries") or [])
    kvitton = [p for p in poster if p.get("resultat") in ("LEVERERAD",
                                                          "AVVISAD")]
    return kvitton[-1] if kvitton else None


def _starta_transfer(avtal, token):
    svar = kallor.anrop(
        kallor.url("edc_consumer_mgmt", "/management/v3/transferprocesses"),
        "POST", {
            "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
            "@type": "TransferRequest",
            "counterPartyAddress": kallor.PROVIDER_DSP,
            "contractId": avtal,
            "protocol": kallor.DSP_PROTOKOLL,
            "transferType": kallor.TRANSFER_TYPE,
            "dataDestination": {"type": "HttpData",
                                "baseUrl": kallor.INGEST_PUSH_URL,
                                "authKey": "Authorization",
                                "authCode": "Bearer %s" % token}},
        headers=kallor.EDC_CONSUMER_MGMT_HUVUD, timeout=30)
    tid = svar.get("@id")
    if not tid:
        raise kallfel("kallfel.ingen_transfer", svar=str(svar)[:300])
    return tid


def _vanta_transfer(tp_id, sekunder=VANTA_TRANSFER_S):
    slut = time.time() + sekunder
    tillstand = "?"
    while time.time() < slut:
        tillstand = kallor.transferprocess(tp_id).get("state", "?")
        if tillstand in ("COMPLETED", "TERMINATED"):
            return tillstand
        time.sleep(2)
    return tillstand


def _skriv(kod, **p):
    print(meddelanden.visa(kod, p, "sv"), flush=True)


def kor_transfer(avtal, logg=_skriv):
    """Engångsauktorisation -> transfer -> vänta in ingest-kvittot.

    Väntar på KVITTOT, inte bara på transferns tillstånd: det är kvittot som
    bevisar att data (eller avvisning) faktiskt nådde staden. Omtaget finns
    för EDC:s deprecated inbäddade dataplan, se ANDRUM_S ovan.
    """
    fore = _senaste_kvitto()
    for forsok in (1, 2, 3):
        token = (kallor.ingest_auktorisation(avtal) or {}).get("token")
        if not token:
            raise kallfel("kallfel.ingest_vagrade", avtal=avtal)
        logg("kedja.auktorisation", avtal=avtal)
        tp = _starta_transfer(avtal, token)
        logg("kedja.transfer_startad", tp=tp, typ=kallor.TRANSFER_TYPE)
        tillstand = _vanta_transfer(tp)
        logg("kedja.transfer_tillstand", tillstand=tillstand)
        slut = time.time() + VANTA_KVITTO_S
        while time.time() < slut:
            kvitto = _senaste_kvitto()
            if kvitto and kvitto != fore:
                return {"transferProcessId": tp, "tillstand": tillstand,
                        "kvitto": kvitto}
            time.sleep(2)
        logg("kedja.forsok", n=forsok, sek=ANDRUM_S)
        time.sleep(ANDRUM_S)
    raise kallfel("kallfel.inget_kvitto")


# ---------------------------------------------------------------------------
# ODRL-blockeringsdemon (ODRL-blockering)
# ---------------------------------------------------------------------------
def _handling(regel):
    """ODRL-action kan vara sträng eller {"@id": ...} beroende på expansion."""
    h = regel.get("action")
    if isinstance(h, dict):
        h = h.get("@id") or h.get("id")
    return str(h or "").rsplit("/", 1)[-1].replace("odrl:", "")


def villkor_a():
    """Villkoren som gäller för Distribution A, ur DHI:s DSP-katalog (läsning, ingen prövning).

    Förbuden mot att sprida och publicera kan ingen connector tvinga fram efter en
    leverans: de är en del av avtalet och mottagarens eget ansvar (hård regel 7: det
    DHI kan verkställa är vem som får ingå avtal, KoV:s godkännande och hävningen).
    """
    katalog = hamta_katalog()
    dataset = dataset_for(katalog, kallor.ASSET_A)
    offert = _policyer(dataset)[0]

    forbud = [_handling(r) for r in (offert.get("prohibition") or [])]
    skyldigheter = [_handling(r) for r in (offert.get("obligation") or [])]
    tillaten = [_handling(r) for r in (offert.get("permission") or [])]

    motivering = []
    if forbud:
        motivering.append(meddelanden.msg("kedja.motivering_forbud", asset=kallor.ASSET_A,
                                          forbud=sorted(set(forbud))))
    if skyldigheter:
        motivering.append(meddelanden.msg("kedja.motivering_skyldighet", skyldigheter=skyldigheter))
    motivering.append(meddelanden.msg("kedja.motivering_klass",
                                      klass=dataset.get("edc:informationClass", "K1R1T1"),
                                      access=dataset.get("edc:accessRights", "non-public")))
    # Varje motivering bär sin svenska text (`text`); engelska skapas av middleware ur kod + parametrar.
    motivering = [dict(m, text=meddelanden.visa(m["kod"], m["p"], "sv")) for m in motivering]
    return {
        "assetId": kallor.ASSET_A,
        "offertId": offert.get("@id"),
        "policy": {"permission": tillaten, "prohibition": forbud,
                   "obligation": skyldigheter},
        "dataRightsHolder": dataset.get("edc:dataRightsHolder"),
        "odrlTerms": dataset.get("odrl:terms"),
        "motivering": motivering,
        "raPolicy": offert,
    }
