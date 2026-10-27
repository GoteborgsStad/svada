#!/usr/bin/env python3
"""Stadens avtalsregister (avtal-havning).

KONCEPT: docs/koncept/C6-drift-och-uthallighet.md

Varför det finns
----------------
Staden behöver kunna svara på tre frågor om ett avtal utan att fråga
DHI varje gång någon tittar: vad innebär avtalet (ODRL-ögonblicksbild), gäller
det fortfarande, och om inte – varför. Samma register avgör också om en
åtkomstnyckel får användas: ett avtal gäller tills det hävs, och statusen
kontrolleras vid VARJE användning (stängt som standard).

Statusen ÄGS av providern (DHI:s connector, KoV-grinden – hård regel 7).
Registret är en kopia som synkas därifrån:

    GET {EDC_PROVIDER_STATUS_URL}/avtalsstatus  ->  [{id, correlationId, status, havning, ...}]

Det är providerns SMALA, skrivskyddade statusendpoint, med en egen nyckel. Staden
håller alltså inte providerns management-nyckel (som även ger rätt att skapa och
ändra tillgångar, policyer och avtal).

MEDVETEN FÖRENKLING – ersätts av en riktig statusmekanism: staden hämtar
(pollar) providerns lista ca varje sekund. I ett riktigt dataområde bör en
hävning nå parten genom protokollet eller en signerad statuslista, inte genom
att stadens tjänst pollar providern. Se docs/koncept/06 om vad DSP säger om detta.

Livscykel: registret ligger i minnet och nollställs med demon, precis som
avtalen i EDC:s minneslager (resursstrategin, hård regel 3). Det sparar alltså inte avtal
permanent.

Statusar
--------
GALLANDE  – providern bekräftade nyligen att avtalet gäller (eller det saknar
            KoV-spärr, t.ex. B, och kan inte hävas).
HAVT      – KoV har hävt det (ORSAK: AVSLAG eller EXPLICIT).
UTGANGET  – avtalets giltighetstid (ODRL inForceDate, relativt avtalets ingående) har gått ut.
            Utgången räknas ut ur policyn och gäller även om providern inte svarar.
OKAND     – avtalet kräver KoV men providern kunde inte bekräfta det
            (nåbart inte, eller avtalet finns inte hos den). Behandlas som
            nekat.
"""

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ODRL = "odrl:"
# Hur gammal en bekräftelse från providern får vara när en nyckel används.
MAX_ALDER_S = 1.5


def _lista(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _id(v):
    if isinstance(v, dict):
        return v.get("@id") or v.get("@value")
    return v


_ENHET_S = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def giltighet_s(policy):
    """Avtalets giltighetstid i sekunder ur policyn, eller None om den saknar gräns.

    Letar efter en tillåtelse med villkoret inForceDate lteq contractAgreement+<tid>,
    t.ex. "contractAgreement+30d". Samma villkor verkställer EDC hos providern vid överföring.
    """
    if not isinstance(policy, dict):
        return None
    for nyckel in ("odrl:permission", "permission", ODRL + "permission",
                   "http://www.w3.org/ns/odrl/2/permission"):
        for regel in _lista(policy.get(nyckel)):
            if not isinstance(regel, dict):
                continue
            for c in _lista(regel.get("odrl:constraint") or regel.get("constraint")
                            or regel.get("http://www.w3.org/ns/odrl/2/constraint")):
                if not isinstance(c, dict):
                    continue
                vanster = str(_id(c.get("odrl:leftOperand") or c.get("leftOperand")
                                  or c.get("http://www.w3.org/ns/odrl/2/leftOperand")) or "")
                oper = str(_id(c.get("odrl:operator") or c.get("operator")
                               or c.get("http://www.w3.org/ns/odrl/2/operator")) or "")
                hoger = str(_id(c.get("odrl:rightOperand") or c.get("rightOperand")
                                or c.get("http://www.w3.org/ns/odrl/2/rightOperand")) or "")
                m = re.fullmatch(r"contractAgreement\+(\d+)([smhd])", hoger)
                if vanster.endswith("inForceDate") and oper.endswith("lteq") and m:
                    return int(m.group(1)) * _ENHET_S[m.group(2)]
    return None


def har_tidsvillkor(policy):
    """Sant om policyn har NÅGOT villkor på inForceDate (oavsett om vi kan räkna ut gränsen eller inte)."""
    if not isinstance(policy, dict):
        return False
    for nyckel in ("odrl:permission", "permission", ODRL + "permission",
                   "http://www.w3.org/ns/odrl/2/permission"):
        for regel in _lista(policy.get(nyckel)):
            if not isinstance(regel, dict):
                continue
            for c in _lista(regel.get("odrl:constraint") or regel.get("constraint")
                            or regel.get("http://www.w3.org/ns/odrl/2/constraint")):
                if isinstance(c, dict) and str(_id(c.get("odrl:leftOperand") or c.get("leftOperand")
                                                   or c.get("http://www.w3.org/ns/odrl/2/leftOperand")) or "").endswith("inForceDate"):
                    return True
    return False


def sammanfatta_policy(policy):
    """Läsbar sammanfattning av en ODRL-policy: tillåtet, förbjudet, plikter.

    Tål att EDC skriver en post som objekt eller lista och att prefixet
    varierar. Råpolicyn sparas oförändrad bredvid.
    """
    if not isinstance(policy, dict):
        return {"tillatet": [], "forbjudet": [], "plikter": []}

    def nyckel(namn):
        for k in (ODRL + namn, namn, "http://www.w3.org/ns/odrl/2/" + namn):
            if k in policy:
                return _lista(policy[k])
        return []

    def kort(a):
        a = str(_id(a) or "")
        return a.rsplit("/", 1)[-1].replace("odrl:", "")

    def regel(r):
        text = kort(r.get("odrl:action") or r.get("action"))
        for c in _lista(r.get("odrl:constraint") or r.get("constraint")):
            if isinstance(c, dict):
                text += " [%s %s %s]" % (
                    kort(c.get("odrl:leftOperand") or c.get("leftOperand")),
                    kort(c.get("odrl:operator") or c.get("operator")),
                    _id(c.get("odrl:rightOperand") or c.get("rightOperand")))
        return text

    # Skyldigheter är dels avtalets egna (obligation), dels de som hänger på en tillåten handling (duty, t.ex. attribute på use).
    plikter = [regel(r) for r in nyckel("obligation")]
    for perm in nyckel("permission"):
        for d in _lista(perm.get("odrl:duty") or perm.get("duty")) if isinstance(perm, dict) else []:
            if isinstance(d, dict):
                plikter.append("%s (duty on %s)" % (regel(d), kort(perm.get("odrl:action") or perm.get("action"))))
    return {
        "tillatet": [regel(r) for r in nyckel("permission")],
        "forbjudet": [regel(r) for r in nyckel("prohibition")],
        "plikter": plikter,
    }


class Avtalsregister:
    def __init__(self, konsument_mgmt_url, konsument_nyckel,
                 provider_mgmt_url, provider_nyckel, asset_dist_karta,
                 offentlig_bas=""):
        self.k_url = konsument_mgmt_url.rstrip("/")
        self.k_nyckel = konsument_nyckel or ""
        self.p_url = (provider_mgmt_url or "").rstrip("/")
        self.p_nyckel = provider_nyckel or ""
        self.asset_dist_karta = asset_dist_karta
        # Adress som visas i avtalets URL, t.ex. dashboardens vy.
        self.offentlig_bas = offentlig_bas.rstrip("/")
        self._avtal = {}            # {id: post}
        self._las = threading.Lock()
        self._senast_ok = 0.0       # tid för senaste lyckade providersvar
        self._provider_status = {}  # {DHI:s avtals-id: post ur providerns lista}
        self._dhi_avtal_for = {}    # {stadens avtals-id: DHI:s avtals-id}
        self._forhandling_for = {}  # {stadens avtals-id: stadens förhandlings-id}
        self._fel_stad = None
        self._fel_provider = None
        # En synk i taget: bakgrundstråden och status() får inte köra samtidigt
        # (en äldre ögonblicksbild får inte skriva över en nyare).
        self._synklas = threading.Lock()

    # -- HTTP --------------------------------------------------------------
    def _anrop(self, url, nyckel, metod="GET", kropp=None):
        data = json.dumps(kropp).encode() if kropp is not None else None
        req = urllib.request.Request(url, data=data, method=metod)
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        if nyckel:
            req.add_header("X-Api-Key", nyckel)
        with urllib.request.urlopen(req, timeout=10) as svar:
            return json.loads(svar.read().decode("utf-8", "replace"))

    # -- registrera -----------------------------------------------------------
    def _post_fran_edc(self, a, nu):
        asset = a.get("assetId") or a.get("edc:assetId")
        policy = a.get("policy")
        avtals_id = a.get("@id")
        return {
            "id": avtals_id,
            "assetId": asset,
            "distribution": (self.asset_dist_karta.get(asset) or "").upper(),
            "konsument": a.get("consumerId"),
            "provider": a.get("providerId"),
            "signerat": a.get("contractSigningDate"),
            "sedd": nu,
            "regler": sammanfatta_policy(policy),
            "policy": policy,
            "forhandlingId": self._forhandling_for.get(avtals_id),
            "dhiAvtalId": self._dhi_avtal_for.get(avtals_id),
            "status": "OKAND",
            "giltigTill": self._giltig_till(a.get("contractSigningDate"), policy),
            # Stängt som standard: har policyn ett tidsvillkor som vi inte kan räkna ut (otolkbar gräns, saknat
            # signeringsdatum) vet vi inte när avtalet går ut, och då räknas det som okänt, inte som obegränsat.
            "tidsvillkorOkant": har_tidsvillkor(policy)
                                and self._giltig_till(a.get("contractSigningDate"), policy) is None,
            "havning": None,
            "statusKontrollerad": None,
        }

    def synka(self):
        """En synkning: stadens avtal + providerns status. Fångar alla fel."""
        with self._synklas:
            self._synka()

    def _synka_om_gammal(self):
        """Synka på begäran, men bara om ingen annan tråd hunnit före."""
        with self._synklas:
            if time.time() - self._senast_ok > MAX_ALDER_S:
                self._synka()

    def _synka(self):
        nu = time.time()
        try:
            fraga = {"@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
                     "@type": "QuerySpec", "limit": 500}
            forh = self._anrop(self.k_url + "/v3/contractnegotiations/request", self.k_nyckel, "POST", fraga)
            try:
                lista = self._anrop(self.k_url + "/v3/contractagreements/request", self.k_nyckel, "POST", fraga)
            except urllib.error.HTTPError as e:
                # Observerat (2026-10-14, ca 2 % av starterna): edc-consumer 0.17.0 kan starta utan POST
                # /v3/contractagreements/request (405 från Jetty) medan GET /v3/contractagreements/{id} och allt annat
                # fungerar. Utan listan stängde registret (OKAND). Hämta då avtalen ett och ett via de id som
                # förhandlingarna bär; formatet är detsamma (V3). Andra fel (401, 500 …) är fortfarande fel.
                if e.code not in (404, 405):
                    raise
                lista = []
                for f in forh:
                    aid = f.get("contractAgreementId")
                    if not aid or aid in self._avtal:
                        continue
                    try:
                        lista.append(self._anrop(
                            self.k_url + "/v3/contractagreements/" + urllib.parse.quote(aid, safe=""), self.k_nyckel))
                    except urllib.error.HTTPError as e2:
                        if e2.code != 404:
                            raise
                if not getattr(self, "_reserv_loggad", False):
                    self._reserv_loggad = True
                    print("[avtalsregister] listan över avtal saknas hos stadens connector (HTTP %s): hämtar avtalen ett och ett"
                          % e.code, flush=True)
            with self._las:
                self._forhandling_for = {
                    f["contractAgreementId"]: f["@id"] for f in forh
                    if f.get("contractAgreementId")}
                for a in lista:
                    if a.get("@id") and a["@id"] not in self._avtal:
                        self._avtal[a["@id"]] = self._post_fran_edc(a, nu)
            self._fel_stad = None
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
            self._fel_stad = "stadens connector: %s" % e
        try:
            if self.p_url:
                lev = self._anrop(self.p_url + "/avtalsstatus", self.p_nyckel)
                with self._las:
                    self._provider_status = {p["id"]: p for p in lev}
                    # Avtalets id är OLIKA hos DHI och staden (EDC 0.17.0).
                    # Kopplingen går via förhandlingen: stadens förhandlings-id
                    # är DHI:s correlationId, och providern redovisar det per avtal.
                    dhi_for_forh = {p["correlationId"]: p["id"]
                                    for p in lev if p.get("correlationId")}
                    self._dhi_avtal_for = {
                        a: dhi_for_forh.get(f)
                        for a, f in self._forhandling_for.items()
                        if dhi_for_forh.get(f)}
                    self._senast_ok = time.time()
                    self._fel_provider = None
        except (urllib.error.URLError, OSError, ValueError, TimeoutError,
                KeyError) as e:
            self._fel_provider = "providern: %s" % e
        self._tillampa(time.time())

    @staticmethod
    def _giltig_till(signerat, policy):
        """Tidpunkt (epok, s) då avtalet går ut, eller None om policyn saknar giltighetsgräns."""
        sek = giltighet_s(policy)
        try:
            return float(signerat) + sek if sek is not None and signerat is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _med_utgang(p, nu):
        """Kopia av posten där ett utgånget avtal har status UTGANGET (en hävning går före)."""
        gt = p.get("giltigTill")
        if gt is not None and nu > gt and p["status"] != "HAVT":
            return dict(p, status="UTGANGET")
        if p.get("tidsvillkorOkant") and p["status"] != "HAVT":
            return dict(p, status="OKAND", orsak="tidsvillkor-okant")
        return p

    def _tillampa(self, nu):
        with self._las:
            farsk = (nu - self._senast_ok) <= MAX_ALDER_S
            for id_, p in self._avtal.items():
                kraver_kov = p["distribution"] == "A"
                p["forhandlingId"] = self._forhandling_for.get(id_)
                p["dhiAvtalId"] = self._dhi_avtal_for.get(id_)
                ps = self._provider_status.get(p["dhiAvtalId"])
                if not kraver_kov:
                    # Utan KoV-spärr kan avtalet inte hävas i PoC:en.
                    p["status"], p["havning"] = "GALLANDE", None
                    p["statusKontrollerad"] = nu
                elif ps is not None and ps.get("status") == "HAVT":
                    # En hävning är slutgiltig: gäller även om providern
                    # sedan inte svarar.
                    p["status"], p["havning"] = "HAVT", ps.get("havning")
                    p["statusKontrollerad"] = self._senast_ok
                elif ps is not None and farsk:
                    p["status"], p["havning"] = "GALLANDE", None
                    p["statusKontrollerad"] = self._senast_ok
                elif p["status"] != "HAVT":
                    p["status"] = "OKAND"

    # -- läsa -----------------------------------------------------------------
    def status(self, avtals_id):
        """Färsk status för användning av en nyckel. Stängt som standard."""
        if time.time() - self._senast_ok > MAX_ALDER_S:
            self._synka_om_gammal()
        with self._las:
            p = self._avtal.get(avtals_id)
        if p is None:
            self.synka()
            with self._las:
                p = self._avtal.get(avtals_id)
        if p is None:
            return {"id": avtals_id, "status": "OKAND", "orsak": "okant-avtal"}
        return self._offentlig(self._med_utgang(p, time.time()), med_policy=False)

    def hamta(self, avtals_id):
        with self._las:
            p = self._avtal.get(avtals_id)
        return self._offentlig(self._med_utgang(p, time.time()), med_policy=True) if p else None

    def lista(self):
        with self._las:
            poster = [self._med_utgang(p, time.time()) for p in self._avtal.values()]
        poster.sort(key=lambda p: -(p.get("signerat") or 0))
        return [self._offentlig(p, med_policy=False) for p in poster]

    def _offentlig(self, p, med_policy):
        ut = {n: v for n, v in p.items() if n not in ("policy", "sedd")}
        ut["url"] = "%s/avtal/%s" % (self.offentlig_bas, p["id"]) \
            if self.offentlig_bas else "/avtal/%s" % p["id"]
        if med_policy:
            ut["policy"] = p.get("policy")
        return ut

    def hamta_url(self, avtals_id):
        """Löstbar adress till avtalet, eller None om ingen bas är satt."""
        if not self.offentlig_bas:
            return None
        return "%s/avtal/%s" % (self.offentlig_bas, avtals_id)

    def fel(self):
        return self._fel_stad or self._fel_provider

    def kor(self, intervall_s=1.0):
        def slinga():
            while True:
                self.synka()
                time.sleep(intervall_s)
        threading.Thread(target=slinga, daemon=True,
                         name="avtalsregister-synk").start()
