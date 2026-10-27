#!/usr/bin/env python3
"""Åtkomstbesluten framför stadens CIP (åtgärd av gapanalysens G22).

Varför den finns
----------------
Distribution A är märkt `access-right/NON_PUBLIC`, informationsklass K1R1T1,
och bär brunnarnas fulla GIS. Fram till den här åtgärden var den märkningen
enbart en ETIKETT i katalogen: `orion-stad` publicerade port 2026 rakt ut på
värden utan någon som helst kontroll, så vem som helst som följde
Distribution A:s `accessURL` fick ut alla 91 brunnars koordinater.

Arbetsdelningen (providern äger policyverkställningen)
-----------------------------------------------------
Det här är INTE en andra KoV-gate. Providern (DHI:s connector) äger
fortfarande beslutet OM ett avtal för Distribution A alls får ingås – det
är KoV-gaten och den ligger kvar orörd. Den här modulen är stadens egen
KONSUMTIONSKONTROLL: staden har nu A-datat i sin CIP och måste själv se
till att bara den som KoV godkänt kan läsa ut det. Samma förhållande som
mellan providerns policy och ingest-servicens mottagningskontroll
(services/ingest-service/auktorisation.py).

Två vägar till en token
-----------------------
1. KoV-vägen (demons väg, den som betyder något):

       POST /auktorisation {"contractAgreementId": "..."} -> {"token": ...}

   Gatewayen slår upp avtalet i STADENS EGEN EDC-connector
   (`GET /management/v3/contractagreements/{id}`). Finns avtalet inte där
   finns inget kontrakt – ingen token. Ett avtal existerar bara om
   providerns KoV-gate släppte igenom förhandlingen, så token är i praktiken
   ett kvitto på KoV-beslutet.

2. Driftvägen: en statisk token ur .env (`STAD_GATEWAY_DRIFT_TOKEN`) för
   stadens egna komponenter – dashboarden, FAIR-lagret och
   verifieringsskripten. De är innanför stadens förtroendegräns och kan
   inte förhandla fram ett avtal per anrop.

NYCKELSKYDDADE MANAGEMENT-API:ER (docs/koncept/C1-identitet.md, bindande miniminivå): avtalsuppslaget
mot stadens EDC-connector (`_hamta_avtal`) skickar nu en delad
management-nyckel (`X-Api-Key`) eftersom edc-consumers management-API inte
längre tar emot anonyma anrop – det stänger den delen av gapanalysens G1.

MEDVETEN FÖRENKLING, MEDVETET KVARLÄMNAD (ställningstagande):
drifttoken (`STAD_GATEWAY_DRIFT_TOKEN`) och KoV-tokens (utfärdade av
`utfarda()`) är fortfarande egna, enkla hemligheter/slumptal – de BÄR
ingen egen kryptografisk koppling till en dataspace-identitet, och är
alltså i sig själva INTE verifierbara identiteter.

Det ursprungliga antagandet här var att verifierbar identitet skulle ersätta dem med en
egen, Python-sidig VC/JWT-verifiering (t.ex. mot Keycloak eller direkt mot
IdentityHub). Efter att steg 5 och steg 6 nedan införts är den bedömningen
omprövad, och det MEDVETNA VALET är att INTE bygga det: en sådan
Python-sidig verifiering skulle bara upprepa en kontroll som redan har
gjorts, kryptografiskt, längre in i kedjan – inte lägga till någon.

Resonemanget, led för led:

1. Steg 5 gjorde stadens EDC-connector (edc-consumer) till den enda parten
   som kan FÅ ett avtal för Distribution A registrerat hos sig – och det
   sker bara efter att DHI:s connector kryptografiskt verifierat stadens
   `did:web`-identitet via DCP/IdentityHub (se DeltagareFunktion.java). Ett avtal i edc-consumers
   contractagreements-lista är alltså redan ett bevis på en verifierad
   dataspace-identitet, inte en påstådd sträng.
2. Steg 6 gjorde providerns KoV-godkännande (`KovController.godkann`)
   villkorat av ett kryptografiskt verifierat SvadaRoleCredential (se
   KovIdentitetsverifiering.java) – ett avtal kan alltså bara uppstå för en
   förhandling som en verifierad Data Rights Holder faktiskt godkänt.
3. `_hamta_avtal` (nedan) slår upp EXAKT detta avtal i stadens EGEN
   EDC-connector, skyddat av den delade management-nyckeln
   (`X-Api-Key`, se nedan). Att ett avtal existerar där är alltså ett
   TRANSITIVT bevis på hela den kryptografiska kedjan ovan – gatewayens
   token är ett KVITTO på det beviset, inte en ersättning för det.

Att bygga en andra, oberoende VC-verifiering i Python HÄR skulle alltså
inte stänga något kvarstående gap – den skulle verifiera samma attest en
gång till, i ett språk utan EDC:s beprövade DCP-stack (jämför
KovIdentitetsverifiering.java, som medvetet ÅTERANVÄNDER EDC:s egen
IdentityService i stället för att implementera VC/JWT-verifiering på
nytt). Den enda återstående, ärliga förenklingen är att gatewayens EGNA
sessionstoken (efter `_hamta_avtal`) är en enkel hemlighet – men den lever
bara inom stadens egen förtroendegräns och representerar bara "detta
avtal är redan verifierat", inte en identitet i sig.
"""

import json
import secrets
import threading
import time
import urllib.error
import urllib.request

# Sökvägar som får passera UTAN token. Enbart liveness – de bär ingen
# bräddata och inga koordinater. Behövs för att healthchecks, dashboardens
# statusvy och testfall 1.1 ska kunna se att CIP:en lever utan att därmed
# få läsa den.
OPPNA_SOKVAGAR = (
    "/health",
    "/ngsi-ld/ex/v1/version",
)


class Atkomstfel(Exception):
    """Nekad åtkomst. Bär statuskod och en orsak som går att visa i demo."""

    def __init__(self, status, orsak, detalj, kod=None, parametrar=None):
        super().__init__(detalj)
        self.status = status
        self.orsak = orsak
        self.detalj = detalj
        self.kod = kod                    # språkoberoende meddelande (kontrollrummets meddelandekatalog)
        self.parametrar = parametrar or {}


def ar_oppen(sokvag):
    """Sant för de få sökvägar som inte kräver token."""
    return sokvag.rstrip("/") in [s.rstrip("/") for s in OPPNA_SOKVAGAR]


class Atkomstregister:
    """In-memory-register över utfärdade åtkomsttokens.

    In-memory av samma skäl som EDC:s stores (resursstrategin, hård regel 3): en
    omstart av gatewayen nollställer utfärdade tokens, vilket är rätt – de
    hör till en pågående åtkomst, inte till en beständig rättighet.
    """

    def __init__(self, edc_mgmt_url, asset_a_id, drift_token, mgmt_key="",
                 ttl_s=3600, avtalsstatus_url=""):
        self.edc_mgmt_url = edc_mgmt_url.rstrip("/")
        self.asset_a_id = asset_a_id
        self.drift_token = drift_token or None
        # Nyckelskyddat management-API: delad nyckel mot edc-consumers management-API
        # (web.http.management.auth.*, EDC_CONSUMER_MGMT_KEY).
        self.mgmt_key = mgmt_key or ""
        self.ttl_s = ttl_s
        # Stadens avtalsregister (ingest-service). Avtal gäller tills de
        # hävs; statusen kontrolleras vid VARJE anrop med en KoV-token.
        self.avtalsstatus_url = (avtalsstatus_url or "").rstrip("/")
        self._tokens = {}
        self._las = threading.Lock()
        self.raknare = {"slappta": 0, "nekade": 0, "utfardade": 0}

    # -- avtalsuppslag mot stadens egen connector ------------------------
    def _hamta_avtal(self, avtals_id):
        url = "%s/v3/contractagreements/%s" % (self.edc_mgmt_url, avtals_id)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if self.mgmt_key:
            req.add_header("X-Api-Key", self.mgmt_key)
        try:
            with urllib.request.urlopen(req, timeout=20) as svar:
                return json.loads(svar.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as fel:
            if fel.code == 404:
                return None
            raise Atkomstfel(
                502, "edc-svarar-inte",
                "stadens EDC svarade HTTP %d vid avtalsuppslag" % fel.code,
                "gateway.edc_http", {"http": fel.code})
        except (urllib.error.URLError, OSError, TimeoutError) as fel:
            raise Atkomstfel(
                502, "edc-svarar-inte",
                "kunde inte nå stadens EDC (%s): %s" % (url, fel),
                "gateway.edc_otillganglig", {"url": url, "fel": str(fel)})

    # -- avtalsstatus (stängt som standard) --------------------------------
    def _kontrollera_avtal(self, avtals_id):
        """Kastar Atkomstfel om avtalet inte bevisligen GÄLLER just nu."""
        if not self.avtalsstatus_url:
            return
        url = "%s/avtal/%s/status" % (self.avtalsstatus_url, avtals_id)
        try:
            with urllib.request.urlopen(url, timeout=5) as svar:
                st = json.loads(svar.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            st = {"status": "OKAND"}
        if st.get("status") != "GALLANDE":
            with self._las:
                self.raknare["nekade"] += 1
            if st.get("status") == "HAVT":
                raise Atkomstfel(
                    403, "avtal-havt",
                    "avtalet %s har hävts av Kretslopp och Vatten – nyckeln "
                    "kan inte längre användas för att hämta data"
                    % avtals_id, "gateway.avtal_havt", {"avtal": avtals_id})
            if st.get("status") == "UTGANGET":
                raise Atkomstfel(
                    403, "avtal-utgatt",
                    "avtalets giltighetstid har gått ut (avtal %s) – nyckeln "
                    "kan inte längre användas för att hämta data" % avtals_id,
                    "gateway.avtal_utgatt", {"avtal": avtals_id})
            raise Atkomstfel(
                403, "avtal-status-okand",
                "avtalets status kunde inte bekräftas – åtkomst nekas",
                "gateway.avtal_status_okand")

    # -- utfärda (KoV-vägen) ---------------------------------------------
    def utfarda(self, avtals_id):
        if not avtals_id:
            raise Atkomstfel(400, "avtals-id-saknas",
                             "contractAgreementId måste anges", "gateway.avtals_id_saknas")
        avtal = self._hamta_avtal(avtals_id)
        if not avtal:
            raise Atkomstfel(
                403, "inget-avtal",
                "inget kontraktsavtal %s finns hos stadens EDC-connector – "
                "utan avtal ingen åtkomst till Distribution A" % avtals_id,
                "gateway.inget_avtal", {"avtal": avtals_id})

        asset_id = avtal.get("assetId") or avtal.get("edc:assetId")
        if asset_id != self.asset_a_id:
            raise Atkomstfel(
                403, "fel-distribution",
                "avtalet gäller assetet '%s'. Åtkomst till stadens CIP kräver "
                "ett avtal för Distribution A (%s). Distribution B läses "
                "öppet via Mintaka och den publika vyn – ingen token behövs."
                % (asset_id, self.asset_a_id),
                "gateway.fel_distribution", {"asset": asset_id, "asset_a": self.asset_a_id})

        self._kontrollera_avtal(avtals_id)

        token = secrets.token_urlsafe(24)
        post = {
            "token": token,
            "sort": "kov",
            "contractAgreementId": avtals_id,
            "assetId": asset_id,
            "utfardadAt": time.time(),
            "gallerTill": time.time() + self.ttl_s,
        }
        with self._las:
            self._tokens[token] = post
            self._stada()
            self.raknare["utfardade"] += 1
        return post

    # -- avgör (varje inkommande anrop) ----------------------------------
    def avgor(self, sokvag, authorization):
        """Returnerar en beslutspost, eller kastar Atkomstfel.

        Kastar ALDRIG igenom av misstag: default är neka.
        """
        if ar_oppen(sokvag):
            return {"sort": "oppen", "sokvag": sokvag}

        token = _bearer(authorization)
        if not token:
            self._rakna_nekad()
            raise Atkomstfel(
                403, "atkomst-kraver-godkannande",
                "Distribution A är non-public (informationsklass K1R1T1) och "
                "bär bräddbrunnarnas fulla GIS. Läsning kräver ett "
                "godkännande från Kretslopp och Vatten (Data Rights Holder). "
                "Växla ditt contractAgreementId mot en token på "
                "POST /auktorisation. Distribution B är öppna data och kräver "
                "ingenting – se den öppna distributionen B i katalogen.",
                "gateway.kraver_godkannande")

        if self.drift_token and secrets.compare_digest(token,
                                                       self.drift_token):
            with self._las:
                self.raknare["slappta"] += 1
            return {"sort": "drift", "sokvag": sokvag}

        with self._las:
            post = self._tokens.get(token)
            if not post:
                self.raknare["nekade"] += 1
                raise Atkomstfel(403, "okand-token",
                                 "okänd åtkomsttoken", "gateway.okand_token")
            if time.time() > post["gallerTill"]:
                del self._tokens[token]
                self.raknare["nekade"] += 1
                raise Atkomstfel(403, "token-utgangen",
                                 "åtkomsttoken har gått ut", "gateway.token_utgangen")
            kopia = dict(post, sokvag=sokvag)
        # Avtalet kontrolleras utanför låset (nätverksanrop).
        self._kontrollera_avtal(post["contractAgreementId"])
        with self._las:
            self.raknare["slappta"] += 1
        return kopia

    def _rakna_nekad(self):
        with self._las:
            self.raknare["nekade"] += 1

    def _stada(self):
        nu = time.time()
        for t in [t for t, p in self._tokens.items()
                  if p["gallerTill"] < nu - 300]:
            del self._tokens[t]

    def lage(self):
        with self._las:
            return [{n: v for n, v in p.items() if n != "token"}
                    for p in self._tokens.values()]


def _bearer(authorization):
    """Plockar ut token ur en Authorization-header. Tål 'Bearer x' och 'x'."""
    if not authorization:
        return None
    delar = authorization.split(None, 1)
    if len(delar) == 2 and delar[0].lower() == "bearer":
        return delar[1].strip()
    return authorization.strip() or None
