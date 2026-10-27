#!/usr/bin/env python3
"""
kallor.py – dashboardens klienter mot PoC:ens alla komponenter.

VARFÖR ÖVER VÄRDENS PORTAR OCH INTE ÖVER DE INTERNA NÄTEN
---------------------------------------------------------
Kontrollrummet talar med varje komponent på exakt den adress en människa
skulle curla: `http://<värd>:<port>` enligt portkartan i .env. Dashboarden
ligger alltså varken på `dhi-internal`, `stad-internal` eller `dsp-public`.
Två skäl:

  1. Kontrollrummet ska inte ha MER åtkomst än en operatör med curl.
     Det som bara går att nå container-till-container (EDC:s dataplan på
     19291/29291, brokrarnas interna portar) är osynligt för dashboarden.
     Vyn blir därmed ett ärligt mått på vad PoC:en faktiskt exponerar.
  2. Att lägga kontrollrummet på org-näten hade gjort det till en gemensam
     nod mellan två organisationer som i verkligheten är skilda åt – precis
     det som separata organisationer (planerat) är till för att undvika.

ÄRLIG AVGRÄNSNING: `fcf-sim` publicerar port 8050 på värden (för
demo och verifiering), så Distribution A:s nyttolast är i den här PoC:en
åtkomlig för den som är på värden. Det som skyddar A är kontraktsledet,
inte nätverkstopologin på värdnivå. Dashboarden hämtar därför ALDRIG
`/distributions/a/*` – ODRL-demon prövar policyn, den hämtar inga data.
I en skarp miljö publiceras dataplanet inte alls (jfr hård regel 8 och
verify_ap4c.sh 4c.x, som kontrollerar att fcf-sim inte ligger på
dsp-public).

`host.docker.internal` pekas till värdens gateway med `extra_hosts` i
compose.portaler.yml (DASH_VARD i .env).

GOTCHA som bärs med hit från tidigare etapper:
  * orion-dhi kräver headern `NGSILD-Tenant: dhi` – utan den svarar den med
    TOM LISTA i stället för 404 (Orion-LD kräver tenant-huvudet).
  * IoT Agentens API kräver `fiware-service` / `fiware-servicepath`.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

import meddelanden

VARD = os.environ.get("DASH_VARD", "host.docker.internal")
TIMEOUT = float(os.environ.get("DASH_TIMEOUT_S", "8"))

# Portkartan (.env, hård regel 5) – dashboarden hårdkodar inget.
PORTAR = {
    "fcf": os.environ.get("FCF_SIM_PORT", "8050"),
    "edc_provider": os.environ.get("EDC_PROVIDER_DEFAULT_PORT", "19191"),
    "edc_provider_mgmt": os.environ.get("EDC_PROVIDER_MGMT_PORT", "19193"),
    "edc_consumer": os.environ.get("EDC_CONSUMER_DEFAULT_PORT", "29191"),
    "edc_consumer_mgmt": os.environ.get("EDC_CONSUMER_MGMT_PORT", "29193"),
    "ingest": os.environ.get("INGEST_PORT", "8060"),
    "orion_stad": os.environ.get("ORION_STAD_PORT", "2026"),
    "mintaka": os.environ.get("MINTAKA_PORT", "8083"),
    # Verifierbar identitet: Stadens STS, publicerad ENDAST för att dashboarden
    # (som av design inte får nå org-interna nätverk, se moduldocstringen
    # ovan) ska kunna hämta ett self-issued DCP-token. Se .env/
    # compose.stad.yml för den fulla motiveringen.
    "identity_hub_stad_sts": os.environ.get("IDENTITY_HUB_STAD_STS_PORT", "29199"),
    # Samordningsrollens statuslista (Svadas utfärdare, DID-sammanhanget): återkallelse av intyg.
    "identity_hub_svada_did": os.environ.get("IDENTITY_HUB_SVADA_DID_PORT", "49197"),
}
SVADA_STATUS_HUVUD = {"X-Api-Key": os.environ.get("SVADA_STATUS_ADMIN_KEY", "")}


def url(nyckel, sokvag=""):
    return "http://%s:%s%s" % (VARD, PORTAR[nyckel], sokvag)


# Identiteter ur .env som flödena behöver.
# Demobrunnens modellerade värde i den ÖPPNA distributionen (B). A och B ligger på varsin entitet i stadens plattform;
# registerentiteten (SewerOverflowWeir) bär bara brunnens egna uppgifter.
BRUNN_ID = os.environ.get("DASH_BRUNN_ID",
                          "urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526")
ASSET_A = os.environ.get("EDC_ASSET_A_ID", "modellerad-bradddata-a")
ASSET_B = os.environ.get("EDC_ASSET_B_ID", "modellerad-bradddata-b")
PROVIDER_ID = os.environ.get("EDC_PROVIDER_ID", "dhi")
DSP_VERSION = os.environ.get("EDC_DSP_VERSION", "2025-1")
# DSP-adressen är CONTAINERNS – det är consumerns EDC som ringer providern,
# inte dashboarden, så här gäller det delade nätets namn (inte värden).
PROVIDER_DSP = "http://edc-provider:19194/protocol/%s" % DSP_VERSION
DSP_PROTOKOLL = "dataspace-protocol-http:%s" % DSP_VERSION
INGEST_PUSH_URL = os.environ.get("INGEST_PUSH_URL",
                                 "http://ingest-service:8060/ingest")
TRANSFER_TYPE = os.environ.get("EDC_TRANSFER_TYPE", "HttpData-PUSH")
# Drifttoken mot stad-gateway (G22). Kontrollrummet är stadens egen
# komponent och ligger innanför förtroendegränsen – externa konsumenter
# växlar i stället sitt contractAgreementId mot en token.
STAD_GATEWAY_HUVUD = {"Authorization": "Bearer %s" % os.environ.get(
    "STAD_GATEWAY_DRIFT_TOKEN", "")}

# Nyckelskyddade management-API:er (docs/koncept/C1-identitet.md): delade nycklar mot de två
# EDC-anläggningarnas management-API, som inte längre tar emot anonyma
# anrop (web.http.management.auth.*).
EDC_PROVIDER_MGMT_HUVUD = {"X-Api-Key": os.environ.get(
    "EDC_PROVIDER_MGMT_KEY", "")}
EDC_CONSUMER_MGMT_HUVUD = {"X-Api-Key": os.environ.get(
    "EDC_CONSUMER_MGMT_KEY", "")}

# Verifierbar identitet: KoV-godkännande/avslag
# kräver numera OCKSÅ ett kryptografiskt verifierat SvadaRoleCredential
# (KovIdentitetsverifiering.java), inte bara management-nyckeln ovan.
# Dessa tre är Stadens egna STS-klientuppgifter, samma värden
# tests/lib.sh:s hamta_kov_token() använder.
SVADA_PARTICIPANT_DID_STAD = os.environ.get("SVADA_PARTICIPANT_DID_STAD", "")
SVADA_STS_CLIENT_SECRET_STAD = os.environ.get(
    "SVADA_STS_CLIENT_SECRET_STAD", "")
KOV_ROLL_SCOPE = "org.eclipse.dspace.dcp.vc.type:SvadaRoleCredential:read"


def hamta_kov_token():
    """Hämtar ett self-issued DCP-token som bevisar KoV:s SvadaRoleCredential.

    Python-motsvarighet till tests/lib.sh:s hamta_kov_token() – SAMMA
    OAuth2 client_credentials-anrop mot Stadens inbäddade STS, bara nått
    över host.docker.internal (den publicerade porten, se PORTAR ovan)
    i stället för docker exec, eftersom dashboarden inte får ligga på
    stad-internal (se moduldocstringen). Formuläret måste vara
    application/x-www-form-urlencoded, inte JSON – därför byggs anropet
    här direkt i stället för via anrop()-hjälparen, som alltid skickar
    JSON.
    """
    formular = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": SVADA_PARTICIPANT_DID_STAD,
        "client_secret": SVADA_STS_CLIENT_SECRET_STAD,
        "audience": PROVIDER_ID,
        "bearer_access_scope": KOV_ROLL_SCOPE,
    }).encode("utf-8")
    adress = url("identity_hub_stad_sts", "/api/sts/token")
    begaran = urllib.request.Request(
        adress, data=formular, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(begaran, timeout=TIMEOUT) as svar:
            text = svar.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as fel:
        detalj = fel.read().decode("utf-8", "replace")[:400]
        raise kallfel("kallfel.sts_http", status=fel.code, http=fel.code, svar=meddelanden.fri(detalj)) from fel
    except (urllib.error.URLError, OSError) as fel:
        raise kallfel("kallfel.sts_nar", url=adress, orsak=meddelanden.fri(str(fel))) from fel
    token = json.loads(text).get("access_token") if text.strip() else None
    if not token:
        raise KallFel("STS-svaret saknade access_token: %s" % text[:400])
    return token


class KallFel(Exception):
    """Komponenten svarade inte, eller svarade med fel.

    `kod` och `p` är det lagrade, språkoberoende meddelandet (se meddelanden.py); `text` är dess
    svenska rendering för loggar och anropare som inte väljer språk.
    """

    def __init__(self, text, status=None, kropp=None, kod=None, p=None):
        super().__init__(text)
        self.status = status
        self.kropp = kropp
        self.kod = kod
        self.p = p or {}

    def meddelande(self):
        """Felet som ett lagringsbart meddelande (kod + parametrar), eller fri text."""
        if self.kod:
            return meddelanden.msg(self.kod, **self.p)
        return meddelanden.fri(str(self))


def kallfel(kod, status=None, kropp=None, **p):
    """Ett KallFel med text ur katalogen (svenska) och kod + parametrar för andra språk."""
    return KallFel(meddelanden.visa(kod, p, "sv"), status=status, kropp=kropp, kod=kod, p=p)


def _svar_som_meddelande(detalj):
    """Ett felsvar från en tjänst som meddelande: dess kod + parametrar om den skickade dem, annars fri text."""
    try:
        d = json.loads(detalj)
        if isinstance(d, dict) and d.get("kod"):
            return meddelanden.msg(d["kod"], **(d.get("parametrar") or {}))
    except ValueError:
        pass
    return meddelanden.fri(detalj)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def anrop(adress, metod="GET", kropp=None, headers=None, timeout=None,
          ratext=False):
    """Ett HTTP-anrop. Returnerar tolkad JSON (eller rå text med ratext=True).

    Fel blir KallFel – aldrig ett tyst None. Kontrollrummet ska kunna visa
    VARFÖR en komponent är röd, inte bara att den är det.
    """
    data = None
    huvuden = {"Accept": "application/json"}
    if kropp is not None:
        data = json.dumps(kropp).encode("utf-8")
        huvuden["Content-Type"] = "application/json"
    huvuden.update(headers or {})
    begaran = urllib.request.Request(adress, data=data, method=metod,
                                     headers=huvuden)
    try:
        try:
            with urllib.request.urlopen(begaran,
                                        timeout=timeout or TIMEOUT) as svar:
                text = svar.read().decode("utf-8", "replace")
        except urllib.error.URLError as fel:
            # Ett anslutningsfel innan begäran skickats (ingen väg, vägrad anslutning) är oftast en kort störning,
            # till exempel när Docker ändrar nätverk: försök en gång till. Skickade begäranden (HTTP-svar, timeout) upprepas inte.
            ursprung = fel.reason if isinstance(fel.reason, OSError) else None
            if ursprung is None or getattr(ursprung, "errno", None) not in (101, 111, 113):
                raise
            time.sleep(1.0)
            with urllib.request.urlopen(begaran,
                                        timeout=timeout or TIMEOUT) as svar:
                text = svar.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as fel:
        detalj = fel.read().decode("utf-8", "replace")[:1200]
        if fel.code in (405, 502, 503, 504) and "/management/" in adress:
            # En connector som just startats om svarar en kort stund 405 (hanteraren är inte registrerad än) eller 5xx.
            raise kallfel("kallfel.startar_om", status=fel.code, kropp=detalj[:400], http=fel.code) from fel
        raise kallfel("kallfel.http", status=fel.code, kropp=detalj[:400], http=fel.code, url=adress,
                      svar=_svar_som_meddelande(detalj)) from fel
    except urllib.error.URLError as fel:
        raise kallfel("kallfel.nar_inte", url=adress, orsak=meddelanden.fri(str(fel.reason))) from fel
    except OSError as fel:
        raise kallfel("kallfel.nar_inte", url=adress, orsak=meddelanden.fri(str(fel))) from fel
    if ratext:
        return text
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except ValueError:
        return {"rasvar": text[:2000]}



# ---------------------------------------------------------------------------
# Komponentvisa läsningar (används av hälsopollningen och stegvyn)
# ---------------------------------------------------------------------------


def fcf_health():
    return anrop(url("fcf", "/health"))


# OBS: det finns MED FLIT ingen funktion som hämtar
# /distributions/{a|b}/latest. Kontrollrummet läser aldrig dataproduktens
# nyttolast – det är kontraktsledets uppgift att lämna ut den, och en
# genväg förbi det hade varit precis den bakväg hård regel 7 och 8 stänger.
def fcf_kor_batch():
    return anrop(url("fcf", "/batches/run"), "POST", timeout=60)


def fcf_felinjektion():
    return anrop(url("fcf", "/felinjektion"))


def fcf_satt_fel(lagen):
    return anrop(url("fcf", "/felinjektion"), "POST", lagen)


def fcf_nollstall_fel():
    return anrop(url("fcf", "/felinjektion/reset"), "POST")


def edc_health(sida):
    nyckel = "edc_provider" if sida == "provider" else "edc_consumer"
    return anrop(url(nyckel, "/api/check/health"))


def kov_forhandlingar():
    """Providerns kö av A-förhandlingar (hård regel 7: gaten sitter HÄR)."""
    return anrop(url("edc_provider_mgmt", "/management/kov/forhandlingar"),
                 headers=EDC_PROVIDER_MGMT_HUVUD)


def kov_beslut(forhandlings_id, beslut):
    if beslut not in ("godkann", "avsla"):
        raise kallfel("kallfel.okant_beslut", beslut=beslut)
    # Verifierbar identitet: KovController verifierar FÖRST ett bifogat
    # SvadaRoleCredential (401 annars) – X-Api-Key ensam räcker inte
    # längre, se konstantblocket ovan.
    kov_token = hamta_kov_token()
    huvuden = dict(EDC_PROVIDER_MGMT_HUVUD)
    huvuden["Authorization"] = "Bearer %s" % kov_token
    return anrop(url("edc_provider_mgmt",
                     "/management/kov/forhandlingar/%s/%s"
                     % (forhandlings_id, beslut)), "POST",
                 headers=huvuden, timeout=30)


def kov_avtal():
    """Avtalen som KoV-spärren gäller, med status GALLANDE/HAVT (hos DHI)."""
    return anrop(url("edc_provider_mgmt", "/management/kov/avtal"),
                 headers=EDC_PROVIDER_MGMT_HUVUD)


def kov_hav(dhi_avtals_id):
    """KoV häver ett avtal direkt. Samma rollbevis som vid godkännande."""
    huvuden = dict(EDC_PROVIDER_MGMT_HUVUD)
    huvuden["Authorization"] = "Bearer %s" % hamta_kov_token()
    return anrop(url("edc_provider_mgmt",
                     "/management/kov/avtal/%s/hav" % dhi_avtals_id), "POST",
                 {}, headers=huvuden, timeout=30)


def svada_status():
    """Samordningsrollens lista över intyg i statuslistan: mottagare, typ, index, återkallat."""
    return anrop(url("identity_hub_svada_did", "/svada-status"), headers=SVADA_STATUS_HUVUD)


def svada_satt(mottagare, atgard):
    """Samordnaren återkallar (aterkalla) eller återinsätter (aterinsatt) mottagarens medlemsintyg."""
    return anrop(url("identity_hub_svada_did",
                     "/svada-status/%s/medlemskap/%s" % (mottagare, atgard)), "POST", {},
                 headers=SVADA_STATUS_HUVUD)


def avtalsregister():
    """Stadens avtalsregister (ingest-service): avtal, status, ODRL-sammanfattning."""
    return anrop(url("ingest", "/avtal"))


def avtalsstatus(avtals_id):
    return anrop(url("ingest", "/avtal/%s/status" % avtals_id))


def _query(sokvag, limit=50):
    """QuerySpec mot consumerns management-API (nyast först)."""
    return anrop(url("edc_consumer_mgmt", sokvag), "POST", {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
        "@type": "QuerySpec", "limit": limit,
        "sortField": "createdAt", "sortOrder": "DESC"},
        headers=EDC_CONSUMER_MGMT_HUVUD, timeout=30)


def forhandlingar(limit=50):
    return _query("/management/v3/contractnegotiations/request", limit)


def transferprocesser(limit=50):
    return _query("/management/v3/transferprocesses/request", limit)


def avtal(avtals_id):
    """Ett kontraktsavtal ur stadens connector (samma som ingest slår upp)."""
    return anrop(url("edc_consumer_mgmt",
                     "/management/v3/contractagreements/%s" % avtals_id),
                 headers=EDC_CONSUMER_MGMT_HUVUD)


def forhandling(fid):
    return anrop(url("edc_consumer_mgmt",
                     "/management/v3/contractnegotiations/%s" % fid),
                 headers=EDC_CONSUMER_MGMT_HUVUD)


def transferprocess(tid):
    return anrop(url("edc_consumer_mgmt",
                     "/management/v3/transferprocesses/%s" % tid),
                 headers=EDC_CONSUMER_MGMT_HUVUD)


def dsp_katalog():
    """Katalogförfrågan consumer -> provider över Dataspace Protocol."""
    return anrop(url("edc_consumer_mgmt", "/management/v3/catalog/request"),
                 "POST", {
                     "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
                     "counterPartyId": PROVIDER_ID,
                     "counterPartyAddress": PROVIDER_DSP,
                     "protocol": DSP_PROTOKOLL},
                 headers=EDC_CONSUMER_MGMT_HUVUD, timeout=30)


def ingest_health():
    return anrop(url("ingest", "/health"))


def ingest_leveranser():
    return anrop(url("ingest", "/leveranser"))


def ingest_auktorisation(avtals_id):
    return anrop(url("ingest", "/auktorisation"), "POST",
                 {"contractAgreementId": avtals_id}, timeout=30)


def orion_stad_version():
    # Liveness är den enda sökväg stad-gateway släpper igenom utan token
    # (G22) – kontrollrummet ska kunna se att CIP:en lever utan att därmed
    # få läsa den.
    return anrop(url("orion_stad", "/ngsi-ld/ex/v1/version"))


def orion_stad_brunn():
    """Demobrunnens B-entitet. Före första B-leveransen finns den inte: då en tom entitet, inte ett fel."""
    try:
        return anrop(url("orion_stad", "/ngsi-ld/v1/entities/%s" % BRUNN_ID),
                     headers=STAD_GATEWAY_HUVUD)
    except KallFel as fel:
        if fel.status == 404:
            return {}
        raise


def orion_stad_antal_brunnar():
    poster = anrop(url("orion_stad",
                       "/ngsi-ld/v1/entities?type=SewerOverflowWeir&limit=1000"),
                   headers=STAD_GATEWAY_HUVUD, timeout=30)
    return len(poster) if isinstance(poster, list) else 0



def mintaka_historik(attribut="overflowVolumeM3", fran="2020-01-01T00:00:00Z"):
    return anrop(url("mintaka",
                     "/temporal/entities/%s?attrs=%s&timerel=after&timeAt=%s"
                     % (BRUNN_ID, attribut, fran)), timeout=30)


