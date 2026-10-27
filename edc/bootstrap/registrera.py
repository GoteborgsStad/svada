#!/usr/bin/env python3
"""Registrerar Distribution B hos edc-provider.

ENGÅNGSJOBB i egen Compose-profil (samma mönster som
provisionera-iota och ladda-brunnar). Körs mot PROVIDERNS
management-API:

    docker compose -f compose.dhi.yml --profile edc-bootstrap \\
      run --rm registrera-edc

Tre objekt i EDC:s datamodell, i den ordning de hänger ihop:

  1. policydefinition   – ODRL-villkoren
  2. asset              – dataprodukten + var datat ligger (dataAddress)
  3. contractdefinition – binder asset till policy => syns i DSP-katalogen

Idempotent: finns objektet redan uppdateras det med PUT i stället för POST,
så skriptet kan köras om utan att ge 409 Conflict.

NYCKELSKYDDADE MANAGEMENT-API:ER (docs/koncept/C1-identitet.md, bindande miniminivå): management-
API:t kräver numera en delad nyckel (EDC_PROVIDER_MGMT_KEY, X-Api-Key) –
ingen anonym åtkomst längre. Verifierbar identitet via DCP kommer ovanpå detta.

GOTCHA: JSON tillåter inga kommentarer, men
hård regel 9 kräver kommenterade konfigfiler. Lösningen är nycklar som
börjar med "_kommentar" i JSON-filerna – de plockas bort här innan
nyttolasten skickas, så att inga påhittade egenskaper hamnar i EDC:s
JSON-LD-modell. Jobbet körs därför på python:3.12-slim och inte på
alpine/curl (den imagen saknar jq).
"""

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

MGMT = os.environ.get("EDC_MGMT_URL", "http://edc-provider:19193/management")
HEALTH = os.environ.get("EDC_HEALTH_URL", "http://edc-provider:19191/api/check/health")
ASSET_ID = os.environ["EDC_ASSET_B_ID"]
ASSET_URL = os.environ["EDC_ASSET_B_URL"]
ASSET_A_ID = os.environ["EDC_ASSET_A_ID"]
ASSET_A_URL = os.environ["EDC_ASSET_A_URL"]
# verifierbar DCP-identitet (steg 5): Stadens VERIFIERADE DID, ersätter __STAD_DID__-platshållaren
# i policy-distribution-a.json:s svada:deltagare-constraint (se den filens
# egen kommentar för varför det numera måste vara en DID, inte "stad").
STAD_DID = os.environ["EDC_STAD_DID"]
# Hur länge ett avtal om Distribution A gäller efter ingåendet: <heltal><s|m|h|d>, t.ex. 30d.
# Ändras bara av tester (verify_ap10 10.11) som behöver en kort giltighet.
AVTAL_GILTIGHET = os.environ.get("AVTAL_GILTIGHET", "30d")
# Delad nyckel mot edc-providerns management-API.
MGMT_KEY = os.environ.get("EDC_PROVIDER_MGMT_KEY", "")
BOOTSTRAP_DIR = pathlib.Path(os.environ.get("BOOTSTRAP_DIR", "/bootstrap"))


def logg(text: str) -> None:
    print(f"[registrera] {text}", flush=True)


def vanta_pa_providern(sekunder: int = 240) -> None:
    """EDC:n startar långsammare än curl-jobbet – vänta in health."""
    slut = time.time() + sekunder
    while time.time() < slut:
        try:
            with urllib.request.urlopen(HEALTH, timeout=5) as svar:
                if svar.status == 200:
                    logg("edc-provider är frisk")
                    return
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(2)
    sys.exit(f"[registrera] FEL: edc-provider blev aldrig frisk ({HEALTH})")


def rensa_kommentarer(nod):
    """Tar bort alla nycklar som börjar med '_kommentar', på alla nivåer."""
    if isinstance(nod, dict):
        return {
            n: rensa_kommentarer(v)
            for n, v in nod.items()
            if not n.startswith("_kommentar")
        }
    if isinstance(nod, list):
        return [rensa_kommentarer(v) for v in nod]
    return nod


def las(filnamn: str) -> dict:
    """Läser en JSON-mall, byter ut placeholders och rensar kommentarer."""
    text = (BOOTSTRAP_DIR / filnamn).read_text(encoding="utf-8")
    text = (text.replace("__ASSET_ID__", ASSET_ID)
                .replace("__ASSET_URL__", ASSET_URL)
                .replace("__ASSET_A_ID__", ASSET_A_ID)
                .replace("__ASSET_A_URL__", ASSET_A_URL)
                .replace("__STAD_DID__", STAD_DID)
                .replace("__AVTAL_GILTIGHET__", AVTAL_GILTIGHET))
    return rensa_kommentarer(json.loads(text))


def anropa(metod: str, url: str, kropp: dict | None = None):
    data = json.dumps(kropp).encode("utf-8") if kropp is not None else None
    begaran = urllib.request.Request(url, data=data, method=metod)
    if data is not None:
        begaran.add_header("content-type", "application/json")
    if MGMT_KEY:
        begaran.add_header("X-Api-Key", MGMT_KEY)
    try:
        with urllib.request.urlopen(begaran, timeout=30) as svar:
            return svar.status, svar.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as fel:
        return fel.code, fel.read().decode("utf-8", "replace")


def skapa_eller_uppdatera(sokvag: str, objekt_id: str, filnamn: str) -> None:
    kropp = las(filnamn)
    status, _ = anropa("GET", f"{MGMT}/v3/{sokvag}/{objekt_id}")

    if status == 200:
        logg(f"{sokvag}/{objekt_id} finns redan – uppdaterar (PUT)")
        # GOTCHA: management-API:t är inte enhetligt i var id:t ska stå vid
        # uppdatering. policydefinitions vill ha det i SÖKVÄGEN
        # (PUT /v3/policydefinitions/{id}), medan assets och
        # contractdefinitions tar det ur kroppen (PUT /v3/assets). Fel
        # variant ger HTTP 405 – vi provar därför båda.
        forsok = [
            ("PUT", f"{MGMT}/v3/{sokvag}/{objekt_id}"),
            ("PUT", f"{MGMT}/v3/{sokvag}"),
        ]
    else:
        logg(f"{sokvag}/{objekt_id} saknas – skapar (POST)")
        forsok = [("POST", f"{MGMT}/v3/{sokvag}")]

    for metod, url in forsok:
        kod, text = anropa(metod, url, kropp)
        if 200 <= kod < 300:
            logg(f"  OK ({metod} {kod}) {text.strip()[:160]}")
            return
        if kod != 405:
            break
    sys.exit(f"[registrera] FEL (HTTP {kod}): {text[:600]}")


def main() -> None:
    logg(f"management-API: {MGMT}")
    logg(f"asset B {ASSET_ID} -> {ASSET_URL}")
    logg(f"asset A {ASSET_A_ID} -> {ASSET_A_URL}")
    vanta_pa_providern()

    # --- Distribution B (öppna data, K0R1T1) -------------------------
    skapa_eller_uppdatera(
        "policydefinitions", "policy-distribution-b", "policy-distribution-b.json"
    )
    skapa_eller_uppdatera("assets", ASSET_ID, "asset-distribution-b.json")
    skapa_eller_uppdatera(
        "contractdefinitions",
        "kontrakt-distribution-b",
        "contractdefinition-distribution-b.json",
    )

    # --- Distribution A (non-public, K1R1T1, bakom KoV-gaten) --
    # EGEN policy, EGET asset och EGEN kontraktsdefinition. Se
    # contractdefinition-distribution-a.json om varför B:s inte återanvänds.
    skapa_eller_uppdatera(
        "policydefinitions", "policy-distribution-a", "policy-distribution-a.json"
    )
    skapa_eller_uppdatera("assets", ASSET_A_ID, "asset-distribution-a.json")
    skapa_eller_uppdatera(
        "contractdefinitions",
        "kontrakt-distribution-a",
        "contractdefinition-distribution-a.json",
    )

    logg("KLART – båda distributionerna annonseras i providerns DSP-katalog "
         "(A bakom KoV-gaten, B automatisk).")


if __name__ == "__main__":
    main()
