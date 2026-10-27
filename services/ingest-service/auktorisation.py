#!/usr/bin/env python3
"""Engångsauktorisationen framför ingest.

Varför den finns
----------------
EDC:s providerdataplan gör en HTTP-PUSH mot stadens ingest-endpoint. Utan
skydd hade vem som helst som når `ingest-service:8060/ingest` kunnat lägga
in "modellerad bräddata" i CIP:en – utan avtal, utan proveniens, utan
KoV-beslut. Testfall 4c.3 ("transfer utan giltigt avtal avvisas") är exakt
det hålet.

Mekanismen
----------
Stadens sida måste, INNAN den startar en transfer, växla sitt
`contractAgreementId` mot en ENGÅNGSTOKEN:

    POST /auktorisation {"contractAgreementId": "..."}   -> {"token": ...}

Ingest slår då upp avtalet i STADENS EGEN EDC-connector
(`GET /management/v3/contractagreements/{id}`). Finns avtalet inte där finns
det inget kontrakt – ingen token utfärdas. Ur avtalet läses `assetId`, som
avgör vilken distribution (A eller B) token får bära in; kuvertet måste
sedan stämma med det (validering.granska_mot_avtal).

Token skickas sedan med som `authCode` i transferns `dataDestination` och
följer med providerns push som Authorization-header. Den är
**engångs** (konsumeras vid första användning) och har kort TTL.

Notera arbetsdelningen, DSP:s arbetsdelning: det är fortfarande PROVIDERN som
avgör OM ett avtal alls får ingås (KoV-gaten). Auktorisationen här
är stadens egen mottagningskontroll – "vi tar bara emot det vi har avtal
för" – inte en andra policyverkställighet.

NYCKELSKYDDADE MANAGEMENT-API:ER (docs/koncept/C1-identitet.md, bindande miniminivå): avtalsuppslaget
mot stadens EDC-connector (`_hamta_avtal`) skickar nu en delad
management-nyckel (`X-Api-Key`) eftersom edc-consumers management-API inte
längre tar emot anonyma anrop.

MEDVETEN FÖRENKLING, MEDVETET KVARLÄMNAD (ställningstagande):
engångstoken ovan är fortfarande ett slumptal – det bär i sig ingen
kryptografisk koppling till en dataspace-identitet. Det ursprungliga
antagandet var att verifierbar identitet skulle ersätta det med en egen, Python-sidig
VC/JWT-verifiering. Efter att verifierbar identitet (punkt 5 och 6 i listan nedan) införts är det bedömt att
den byggnationen inte tillför något: en sådan kontroll skulle bara
upprepa, i Python, en verifiering som redan skett kryptografiskt längre in
i kedjan.

`_hamta_avtal` (nedan) slår upp avtalet i STADENS EGEN EDC-connector, och
att det avtalet finns där är redan ett TRANSITIVT bevis på hela kedjan:
steg 5 gjorde ett registrerat avtal beroende av att DHI:s connector
kryptografiskt verifierat stadens `did:web`-identitet (DeltagareFunktion.java),
och steg 6 gjorde providerns KoV-godkännande (KovController.godkann)
villkorat av ett verifierat SvadaRoleCredential (KovIdentitetsverifiering.java)
– ett avtal kan alltså bara existera för en förhandling en verifierad Data
Rights Holder faktiskt godkänt. Engångstoken här är ett KVITTO på det
redan bevisade, inte en ersättning för det; att bygga en andra VC-
verifiering i Python skulle betyda att verifiera samma attest en gång
till, utan EDC:s beprövade DCP-stack bakom sig (jämför
KovIdentitetsverifiering.java, som medvetet ÅTERANVÄNDER EDC:s egen
IdentityService i stället för att implementera VC/JWT-verifiering på
nytt).
"""

import json
import secrets
import threading
import time
import urllib.error
import urllib.request


class Auktorisationsfel(Exception):
    """Ett nej. `orsak` är maskinläsbar, `detalj` svensk text för den som anropar direkt, och `kod` +
    `parametrar` är samma sak som språkoberoende meddelande (kontrollrummet visar katalogens text)."""

    def __init__(self, status, orsak, detalj, kod=None, parametrar=None):
        super().__init__(detalj)
        self.status = status
        self.orsak = orsak
        self.detalj = detalj
        self.kod = kod
        self.parametrar = parametrar or {}


class Auktorisationer:
    """In-memory-register över utfärdade engångstokens.

    In-memory av samma skäl som EDC:s stores (resursstrategin, hård regel 3) – en
    omstart av ingest nollställer utfärdade tokens, och det är rätt: de är
    kortlivade och hör till en pågående transfer.
    """

    def __init__(self, edc_mgmt_url, asset_dist_karta, mgmt_key="",
                 ttl_s=600, register=None):
        self.edc_mgmt_url = edc_mgmt_url.rstrip("/")
        self.asset_dist_karta = asset_dist_karta      # {assetId: "a"|"b"}
        # Nyckelskyddat management-API: delad nyckel mot edc-consumers management-API.
        self.mgmt_key = mgmt_key or ""
        self.ttl_s = ttl_s
        self.register = register
        self._tokens = {}
        self._las = threading.Lock()

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
            raise Auktorisationsfel(
                502, "edc-svarar-inte",
                "stadens EDC svarade HTTP %d vid avtalsuppslag" % fel.code,
                "ingest.edc_http", {"http": fel.code})
        except (urllib.error.URLError, OSError, TimeoutError) as fel:
            raise Auktorisationsfel(
                502, "edc-svarar-inte",
                "kunde inte nå stadens EDC (%s): %s" % (url, fel),
                "ingest.edc_otillganglig", {"url": url, "fel": str(fel)})

    # -- utfärda ---------------------------------------------------------
    def utfarda(self, avtals_id):
        if not avtals_id:
            raise Auktorisationsfel(400, "avtals-id-saknas",
                                    "contractAgreementId måste anges",
                                    "ingest.avtals_id_saknas")
        avtal = self._hamta_avtal(avtals_id)
        if not avtal:
            raise Auktorisationsfel(
                403, "inget-avtal",
                "inget kontraktsavtal %s finns hos stadens EDC-connector – "
                "ingen auktorisation utfärdas" % avtals_id,
                "ingest.inget_avtal", {"avtal": avtals_id})

        asset_id = avtal.get("assetId") or avtal.get("edc:assetId")
        dist = self.asset_dist_karta.get(asset_id)
        if not dist:
            raise Auktorisationsfel(
                403, "okant-asset",
                "avtalet gäller assetet '%s', som inte är någon känd "
                "distribution av dataprodukten" % asset_id,
                "ingest.okant_asset", {"asset": asset_id})

        # Avtal gäller tills de hävs: ett hävt avtal ger ingen ny nyckel.
        if self.register is not None:
            st = self.register.status(avtals_id)
            if st["status"] != "GALLANDE":
                raise Auktorisationsfel(
                    403, {"HAVT": "avtal-havt", "UTGANGET": "avtal-utgatt"}.get(
                        st["status"], "avtal-status-okand"),
                    "avtalet %s har status %s hos stadens avtalsregister – "
                    "ingen nyckel utfärdas" % (avtals_id, st["status"]),
                    "ingest.avtal_status_nyckel", {"avtal": avtals_id, "status": st["status"]})

        token = secrets.token_urlsafe(24)
        post = {
            "token": token,
            "contractAgreementId": avtals_id,
            "assetId": asset_id,
            "distribution": dist,
            "utfardadAt": time.time(),
            "gallerTill": time.time() + self.ttl_s,
            "anvand": False,
        }
        with self._las:
            self._tokens[token] = post
            self._stada()
        return post

    # -- konsumera (engångs) ---------------------------------------------
    def konsumera(self, token):
        if not token:
            raise Auktorisationsfel(
                401, "auktorisation-saknas",
                "leveransen saknar Authorization-header – ingen "
                "engångsauktorisation, ingen ingest",
                "ingest.auktorisation_saknas")
        with self._las:
            post = self._tokens.get(token)
            if not post:
                raise Auktorisationsfel(
                    403, "okand-token",
                    "okänd eller redan förbrukad engångsauktorisation",
                    "ingest.okand_token")
            if post["anvand"]:
                raise Auktorisationsfel(
                    403, "token-forbrukad",
                    "engångsauktorisationen är redan förbrukad",
                    "ingest.token_forbrukad")
            if time.time() > post["gallerTill"]:
                del self._tokens[token]
                raise Auktorisationsfel(403, "token-utgangen",
                                        "engångsauktorisationen har gått ut",
                                        "ingest.token_utgangen")
            post["anvand"] = True
            post["anvandAt"] = time.time()
            return dict(post)

    def _stada(self):
        nu = time.time()
        for t in [t for t, p in self._tokens.items()
                  if p["gallerTill"] < nu - 300]:
            del self._tokens[t]

    def lage(self):
        with self._las:
            return [{n: v for n, v in p.items() if n != "token"}
                    for p in self._tokens.values()]
