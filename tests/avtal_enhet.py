#!/usr/bin/env python3
"""Enhetstest: avtalsstatus är stängd som standard (avtal-havning).

Ingen stack behövs. Provar de vägar som verify_ap10.sh inte kan nå mot en frisk stack:
  * registret svarar OKAND för ett A-avtal när providern inte går att nå,
  * gatewayen nekar (403 avtal-status-okand) när avtalsregistret inte svarar,
  * ett avtal som en gång setts som HAVT förblir HAVT även om providern tystnar,
  * ett avtal vars giltighetstid gått ut är UTGANGET (även om providern tystnar) och ger 403 avtal-utgatt.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "ingest-service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "stad-gateway"))
import avtalsregister  # noqa: E402
import atkomst         # noqa: E402

fel = 0


def kolla(ok, text):
    global fel
    print("  [%s] %s" % ("OK" if ok else "FEL", text))
    if not ok:
        fel += 1


NU = 1_000_000.0
DEAD = "http://127.0.0.1:9"        # ingen lyssnar

# 1. Register: A-avtal utan nåbar provider -> OKAND, B-avtal -> GALLANDE
r = avtalsregister.Avtalsregister(DEAD, "", DEAD, "", {"asset-a": "a", "asset-b": "b"})
r._avtal = {
    "A1": {"id": "A1", "distribution": "A", "status": "GALLANDE", "havning": None},
    "B1": {"id": "B1", "distribution": "B", "status": "OKAND", "havning": None},
}
r._senast_ok = 0.0
r._tillampa(NU)
kolla(r._avtal["A1"]["status"] == "OKAND", "A-avtal utan bekräftelse från providern -> OKAND")
kolla(r._avtal["B1"]["status"] == "GALLANDE", "B-avtal (ingen KoV-spärr) -> GALLANDE")

# 2. Bekräftad hävning består även när providern tystnar
r._provider_status = {"DHI1": {"id": "DHI1", "status": "HAVT", "havning": {"orsak": "AVSLAG"}}}
r._dhi_avtal_for = {"A1": "DHI1"}
r._senast_ok = NU
r._tillampa(NU)
kolla(r._avtal["A1"]["status"] == "HAVT", "providern bekräftar hävning -> HAVT")
r._senast_ok = 0.0
r._tillampa(NU + 100)
kolla(r._avtal["A1"]["status"] == "HAVT", "hävningen består när providern sedan tystnar")

# 3. Gateway: avtalsregistret nere -> 403 avtal-status-okand
g = atkomst.Atkomstregister("http://127.0.0.1:9", "asset-a", "drift", avtalsstatus_url=DEAD)
g._tokens["T"] = {"token": "T", "sort": "kov", "contractAgreementId": "A1", "assetId": "asset-a",
                  "utfardadAt": 0, "gallerTill": 9e12}
try:
    g.avgor("/ngsi-ld/v1/entities", "Bearer T")
    kolla(False, "gatewayen nekar när avtalsregistret inte svarar")
except atkomst.Atkomstfel as e:
    kolla(e.status == 403 and e.orsak == "avtal-status-okand",
          "gatewayen nekar när avtalsregistret inte svarar (403 %s)" % e.orsak)


# 4. Giltighetstid: policyn bär inForceDate lteq contractAgreement+<tid>
def policy(tid, form="prefix"):
    c = {"odrl:leftOperand": {"@id": "edc:inForceDate"}, "odrl:operator": {"@id": "odrl:lteq"},
         "odrl:rightOperand": tid}
    if form == "iri":
        c = {"http://www.w3.org/ns/odrl/2/leftOperand": {"@id": "https://w3id.org/edc/v0.0.1/ns/inForceDate"},
             "http://www.w3.org/ns/odrl/2/operator": {"@id": "http://www.w3.org/ns/odrl/2/lteq"},
             "http://www.w3.org/ns/odrl/2/rightOperand": {"@value": tid}}
        return {"http://www.w3.org/ns/odrl/2/permission": [{"http://www.w3.org/ns/odrl/2/constraint": [c]}]}
    return {"odrl:permission": [{"odrl:constraint": [c]}]}


kolla(avtalsregister.giltighet_s(policy("contractAgreement+30d")) == 30 * 86400, "giltighet 30d tolkas (prefixform)")
kolla(avtalsregister.giltighet_s(policy("contractAgreement+20s", "iri")) == 20, "giltighet 20s tolkas (full IRI-form)")
kolla(avtalsregister.giltighet_s(policy("2030-01-01")) is None, "en annan högeroperand ger ingen giltighetsgräns")
kolla(avtalsregister.giltighet_s({"odrl:permission": [{}]}) is None, "policy utan villkor ger ingen giltighetsgräns")

r2 = avtalsregister.Avtalsregister(DEAD, "", DEAD, "", {"asset-a": "a"})
gt = avtalsregister.Avtalsregister._giltig_till(NU - 100, policy("contractAgreement+60s"))
kolla(gt == NU - 40, "giltigTill = signerat + giltighet")
r2._avtal = {"A2": {"id": "A2", "distribution": "A", "status": "GALLANDE", "havning": None,
                    "giltigTill": gt, "signerat": NU - 100}}
kolla(avtalsregister.Avtalsregister._med_utgang(r2._avtal["A2"], NU - 50)["status"] == "GALLANDE", "före utgången gäller avtalet")
kolla(avtalsregister.Avtalsregister._med_utgang(r2._avtal["A2"], NU)["status"] == "UTGANGET", "efter utgången är avtalet UTGANGET")
r2._avtal["A2"]["status"] = "HAVT"
kolla(avtalsregister.Avtalsregister._med_utgang(r2._avtal["A2"], NU)["status"] == "HAVT", "en hävning går före utgången")

g2 = atkomst.Atkomstregister("http://127.0.0.1:9", "asset-a", "drift", avtalsstatus_url=DEAD)
g2._tokens["T"] = dict(g._tokens["T"])
g2._hamta_status = None
import urllib.request as _ur
_orig = _ur.urlopen


class _Svar:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return b'{"status": "UTGANGET"}'


_ur.urlopen = lambda *a, **k: _Svar()
try:
    g2.avgor("/ngsi-ld/v1/entities", "Bearer T")
    kolla(False, "gatewayen nekar ett utgånget avtal")
except atkomst.Atkomstfel as e:
    kolla(e.status == 403 and e.orsak == "avtal-utgatt", "gatewayen nekar ett utgånget avtal (403 %s)" % e.orsak)
finally:
    _ur.urlopen = _orig

# 5. Ett tidsvillkor som inte går att räkna ut är inte obegränsad giltighet: stängt som standard
def policy_med(hoger, oper="odrl:lteq"):
    return {"odrl:permission": [{"odrl:constraint": [{"odrl:leftOperand": {"@id": "edc:inForceDate"},
                                                      "odrl:operator": {"@id": oper}, "odrl:rightOperand": hoger}]}]}


kolla(avtalsregister.har_tidsvillkor(policy_med("contractAgreement+30d")), "har_tidsvillkor ser ett inForceDate-villkor")
kolla(not avtalsregister.har_tidsvillkor({"odrl:permission": [{}]}), "har_tidsvillkor: ingen gräns när villkoret saknas")
r3 = avtalsregister.Avtalsregister(DEAD, "", DEAD, "", {"asset-a": "a"})
okand = {"id": "A3", "distribution": "A", "status": "GALLANDE", "havning": None, "giltigTill": None, "tidsvillkorOkant": True}
kolla(avtalsregister.Avtalsregister._med_utgang(okand, NU)["status"] == "OKAND",
      "ett tidsvillkor som inte går att räkna ut ger OKAND (inte obegränsad giltighet)")
okand["status"] = "HAVT"
kolla(avtalsregister.Avtalsregister._med_utgang(okand, NU)["status"] == "HAVT", "en hävning går före ett okänt tidsvillkor")
post = r3._post_fran_edc({"@id": "X", "assetId": "asset-a", "policy": policy_med("contractAgreement+30d"),
                          "contractSigningDate": None}, NU)
kolla(post["tidsvillkorOkant"] is True and post["giltigTill"] is None,
      "saknat signeringsdatum med ett tidsvillkor i policyn markeras som okänt")
post = r3._post_fran_edc({"@id": "Y", "assetId": "asset-a", "policy": policy_med("2030-01-01"),
                          "contractSigningDate": NU}, NU)
kolla(post["tidsvillkorOkant"] is True, "ett tidsvillkor med en gräns vi inte tolkar markeras som okänt")
post = r3._post_fran_edc({"@id": "Z", "assetId": "asset-a", "policy": policy_med("contractAgreement+30d"),
                          "contractSigningDate": NU}, NU)
kolla(post["tidsvillkorOkant"] is False and post["giltigTill"] == NU + 30 * 86400, "ett tolkat tidsvillkor ger en giltighetsgräns")

# --- reserv när connectorn saknar listan över avtal (EDC 0.17.0 kunde starta utan POST /v3/contractagreements/request) ---
import urllib.error as _ue

r4 = avtalsregister.Avtalsregister(DEAD, "", "", "", {"asset-b": "b"})
AGREEMENT = {"@id": "ag-1", "assetId": "asset-b", "consumerId": "stad", "providerId": "dhi", "contractSigningDate": 1791230400,
             "policy": {"odrl:permission": [{"odrl:action": {"@id": "odrl:use"}}]}}
anrop = []


def stub(url, nyckel, metod="GET", kropp=None):
    anrop.append((metod, url))
    if url.endswith("/v3/contractnegotiations/request"):
        return [{"@id": "forh-1", "contractAgreementId": "ag-1"}, {"@id": "forh-2", "contractAgreementId": "ag-2"}]
    if url.endswith("/v3/contractagreements/request"):
        raise _ue.HTTPError(url, 405, "Method Not Allowed", {}, None)
    if url.endswith("/v3/contractagreements/ag-1"):
        return AGREEMENT
    if url.endswith("/v3/contractagreements/ag-2"):
        raise _ue.HTTPError(url, 404, "Not Found", {}, None)
    raise AssertionError("oväntat anrop " + url)


r4._anrop = stub
r4._synka()
kolla("ag-1" in r4._avtal, "när listan svarar 405 hämtas avtalen ett och ett via förhandlingarnas avtals-id")
kolla("ag-2" not in r4._avtal and r4._fel_stad is None, "ett avtal som inte finns (404) hoppas över utan att synken fallerar")
kolla(any(u.endswith("/v3/contractagreements/ag-1") for _, u in anrop), "reserven använder GET /v3/contractagreements/{id}")

r5 = avtalsregister.Avtalsregister(DEAD, "", "", "", {"asset-b": "b"})


def stub_401(url, nyckel, metod="GET", kropp=None):
    if url.endswith("/v3/contractnegotiations/request"):
        return []
    raise _ue.HTTPError(url, 401, "Unauthorized", {}, None)


r5._anrop = stub_401
r5._synka()
kolla(r5._fel_stad is not None and not r5._avtal, "andra fel än 404/405 (till exempel 401) ger fortfarande ett synkfel, ingen tyst reserv")

# Skyldigheten som hänger på en tillåten handling (duty på use, attribueringsplikten i B) ska synas som skyldighet.
_b = avtalsregister.sammanfatta_policy({"permission": [{"action": "odrl:use", "duty": [{"action": "odrl:attribute"}]}, {"action": "odrl:distribute"}],
                                        "prohibition": [], "obligation": []})
kolla(_b["plikter"] == ["attribute (duty on use)"], "B: attribueringsplikten (duty på use) visas som skyldighet, inte som 'inga'")
kolla(avtalsregister.sammanfatta_policy({"permission": [{"action": "odrl:use"}]})["plikter"] == [], "ingen duty ger inga skyldigheter")

sys.exit(1 if fel else 0)
