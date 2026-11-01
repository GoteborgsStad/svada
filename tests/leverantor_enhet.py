#!/usr/bin/env python3
"""K36 (utan stack, körs i dashboard-imagen): staden hittar leverantören i deltagarregistret (MIM3 RC5.1), faller tillbaka på den konfigurerade
när registret inte nås, väljer en deltagare med återkallat medlemskap ändå (connectorerna nekar, provet 11.5), sparar svaret kort tid,
och steg 2 visar deltagarna utan DID eller adress."""
import os
import sys

for sok in ("/app", "/srv", "/srv/dashboard"):
    if os.path.isdir(sok):
        sys.path.insert(0, sok)
os.environ.setdefault("DEMO_VARIANT", "extern")
os.environ["SVADA_PARTICIPANT_DID_STAD"] = "did:web:identity-hub-stad%3A29197"
import kallor  # noqa: E402
import steg  # noqa: E402

fel = 0


def kolla(villkor, text):
    global fel
    print("  [%s] %s" % ("OK" if villkor else "FEL", text))
    fel += 0 if villkor else 1


def post(id_, did, namn, endpoint, medlem="valid", delt="valid"):
    return {"id": id_, "did": did, "name": namn, "membership": {"status": medlem}, "participation": {"status": delt}, "dspEndpoint": endpoint}


DHI = post("dhi", "did:web:identity-hub-dhi%3A19197", "DHI – Future City Flow", "http://edc-provider:19194/protocol")
STAD = post("stad", "did:web:identity-hub-stad%3A29197", "Göteborgs Stad", "http://edc-consumer:29194/protocol")
anrop_orig = kallor.anrop
anropslogg = []


def stub(register):
    def anrop(adress, metod="GET", kropp=None, **k):
        anropslogg.append((adress, kropp))
        if "/participants" in adress:
            if isinstance(register, Exception):
                raise register
            return {"participants": register}
        return {"dataset": []}
    return anrop


def ny(register):
    kallor._leverantor.update({"tid": 0.0, "svar": None})
    kallor.anrop = stub(register)
    anropslogg.clear()


ny([STAD, DHI])
l = kallor.valj_leverantor()
kolla(l["kalla"] == "registret" and l["id"] == DHI["did"] and l["namn"] == DHI["name"], "leverantören hittas i registret och staden hoppas över")
kolla(l["adress"] == "http://edc-provider:19194/protocol/" + kallor.DSP_VERSION, "adressen får DSP-versionen på slutet (%s)" % l["adress"])
n = len(anropslogg)
kallor.valj_leverantor()
kolla(len(anropslogg) == n, "svaret sparas några sekunder: inget nytt anrop till registret")
kallor.dsp_katalog()
kat = [k for a, k in anropslogg if k and "counterPartyAddress" in k][-1]
kolla(kat["counterPartyAddress"] == l["adress"] and kat["counterPartyId"] == DHI["did"], "katalogfrågan går till adressen och DID:et ur registret")

ny(kallor.KallFel("registret nås inte"))
l = kallor.valj_leverantor()
kolla(l["kalla"] == "konfiguration" and l["adress"] == kallor.PROVIDER_DSP and l["id"] == kallor.PROVIDER_ID, "når staden inte registret används den konfigurerade leverantören")
ny([STAD])
kolla(kallor.valj_leverantor()["kalla"] == "konfiguration", "finns ingen annan deltagare i registret används den konfigurerade leverantören")
ny([STAD, post("dhi", DHI["did"], DHI["name"], None)])
kolla(kallor.valj_leverantor()["kalla"] == "konfiguration", "en deltagare utan connectoradress kan inte väljas")
ny([STAD, post("dhi", DHI["did"], DHI["name"], DHI["dspEndpoint"], medlem="revoked")])
l = kallor.valj_leverantor()
kolla(l["kalla"] == "registret" and l["medlemskap"] == "revoked", "en deltagare med återkallat medlemskap väljs ändå (connectorerna verkställer och nekar)")

# Steg 2: raderna visar deltagarna men varken DID eller adress
ny([STAD, DHI])
kallor.dsp_katalog = lambda: {"dataset": []}
rader = steg._d2()
text = " ".join("%s %s" % r for r in rader)
kolla(rader[0] == ("Leverantör hittad via", "deltagarregistret"), "steg 2 säger att leverantören hittades via deltagarregistret")
kolla(any(r[0] == "Deltagare i registret: DHI – Future City Flow" and r[1] == "medlemskap giltigt, deltagande giltigt" for r in rader), "steg 2 visar DHI med medlemsstatus")
kolla("did:web" not in text and "edc-provider" not in text and "19194" not in text, "steg 2 visar varken DID eller connectoradress")
en = [steg.oversatt_detalj(a, b, "en") for a, b in rader]
kolla(en[0] == ("Provider found through", "the participant directory"), "steg 2 på engelska: leverantör hittad via the participant directory")
kolla(("Participant in the directory: DHI – Future City Flow", "membership valid, participation valid") in en, "steg 2 på engelska: deltagarna och statusen")
ny(kallor.KallFel("fel.test"))
rader = steg._d2()
kolla(rader[0][1].startswith("inställningen") and "ingen leverantör i registret, eller" in rader[0][1] and not any(r[0].startswith("Deltagare i registret") for r in rader),
      "utan register: steg 2 säger det (utan att påstå att registret inte nåddes) och listar inga deltagare")
ny([STAD])
kolla("eller registret nåddes inte" in steg._d2()[0][1], "finns bara staden i registret säger steg 2 inte enbart att registret inte nåddes")
kallor.anrop = anrop_orig
print("\nFEL: %d" % fel if fel else "\nLeverantörsvalet: GRÖNT")
sys.exit(1 if fel else 0)
