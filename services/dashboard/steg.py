#!/usr/bin/env python3
"""
steg.py – kedjan "FCF -> dataspace -> stadens användning av data" i sex steg (Svada-mini).

Varje steg känner till
  * vilka KOMPONENTER som utför det (och hur man sonderar deras hälsa),
  * vilka SIFFROR som visar att steget verkligen gör sitt jobb just nu,
  * vilka ÅTGÄRDER en demonstratör kan utlösa ("kör steget").

Numreringen 1–6 är den som är kanonisk i docs/01-oversikt.md §1.4.
Komponentnumreringen (komponent 1–13) hör till den arkiverade
komponentplanens §3.1 – docs/01-oversikt.md §1.6 numrerar om dem, så följ
inte komponentnummer mellan de två. Rollerna är organisationsgränserna: DHI äger steg
1–3:s provider-sida, Göteborgs Stad steg 3:s consumer-sida till och med 6.

Varje steg har också PEDAGOGIK (texterna som den pedagogiska kedjevyn i
vy.py visar, på svenska och engelska) och TEKNIK (vilka system som körs och
om de är riktiga, förenklade eller simulerade). Se avsnittet "Pedagogisk
kedjevy" nedan. Kontrollen kontrollera_knapptackning() körs vid import och
stoppar en åtgärd som saknar knapptext.

Alla läsningar är LÄSNINGAR. Åtgärderna ligger i jobb.py/kedjan.py, och
ingen av dem kan flytta data förbi kontraktet – dashboarden anropar samma
publika API:er som verifieringsskripten.
"""

import datetime
import json
import re

import kallor
from gemensam import rensa
from kallor import KallFel, kallfel
import i18n
import meddelanden
import sessioner

# ---------------------------------------------------------------------------
# Sonder som inte är rena GET:ar
# ---------------------------------------------------------------------------
def _sond_mintaka():
    # Micronaut-appens egen /health. En temporal fråga duger inte som sond:
    # Mintaka kräver timerel/timeAt och svarar annars 400.
    return kallor.anrop(kallor.url("mintaka", "/health"))


# ---------------------------------------------------------------------------
# Komponenter: id -> (namn, organisation, stegnummer, sond)
# Sonden ska vara BILLIG – den körs var DASH_HALSA_INTERVALL_S sekund.
# ---------------------------------------------------------------------------
KOMPONENTER = [
    {"id": "fcf-sim", "namn": "Future City Flow (fcf-sim)", "org": "DHI",
     "steg": 1, "port": "fcf", "sond": kallor.fcf_health},
    {"id": "edc-provider", "namn": "Eclipse EDC – provider", "namn_en": "Eclipse EDC – provider", "org": "DHI",
     "steg": 2, "port": "edc_provider",
     "sond": lambda: kallor.edc_health("provider")},
    {"id": "edc-consumer", "namn": "Eclipse EDC – consumer", "namn_en": "Eclipse EDC – consumer", "org": "Staden",
     "steg": 3, "port": "edc_consumer",
     "sond": lambda: kallor.edc_health("consumer")},
    {"id": "ingest-service", "namn": "ingest-service (mottagning)", "namn_en": "ingest-service (intake)",
     "org": "Staden", "steg": 4, "port": "ingest", "sond": kallor.ingest_health},
    {"id": "orion-stad", "namn": "Orion-LD Staden (CIP)", "namn_en": "Orion-LD City (CIP)", "org": "Staden",
     "steg": 5, "port": "orion_stad", "sond": kallor.orion_stad_version},
    {"id": "mintaka", "namn": "Mintaka (temporal API)", "org": "Staden",
     "steg": 5, "port": "mintaka", "sond": _sond_mintaka},
]


# ---------------------------------------------------------------------------
# Detaljläsningar per steg. Får ALDRIG kasta – ett dött led ska visa sitt fel,
# inte fälla hela vyn.
# ---------------------------------------------------------------------------
def _skyddad(fn):
    try:
        return fn()
    except KallFel as fel:
        return [("fel", str(fel))]
    except Exception as fel:                             # noqa: BLE001
        return [("fel", "%s: %s" % (type(fel).__name__, fel))]


def _dygn_ur_batchid(batch_id):
    """Datumet sist i batch-id:t (batch-015-2026-06-29) är det MODELLERADE dygnet batchen avser, inte när den kördes."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})$", str(batch_id or ""))
    return m.group(1) if m else "–"


def _d1():
    h = kallor.fcf_health()
    fel = kallor.fcf_felinjektion()
    aktiva = [k for k, v in (fel.get("lagen") or {}).items() if v]
    return [
        ("Producerade batchar", h.get("batchesTotal", h.get("batches"))),     # löpnumret, inte antalet sparade (högst 10)
        ("Senaste batch", h.get("latestBatchId")),
        ("Modellerat dygn (datumet i batch-id:t)", _dygn_ur_batchid(h.get("latestBatchId"))),
        ("Mätpunkter i fönstret", h.get("measurementWindow")),
        ("Brunnar i modellen", h.get("weirs")),
        ("Felinjektion", ", ".join(aktiva) if aktiva else "av"),
    ]


def _d2():
    kat = kallor.dsp_katalog()
    dataset = kat.get("dcat:dataset") or kat.get("dataset") or []
    if isinstance(dataset, dict):
        dataset = [dataset]
    rader = [("Datamängder i DSP-katalogen", len(dataset))]
    for d in dataset:
        policyer = d.get("odrl:hasPolicy") or d.get("hasPolicy") or []
        if isinstance(policyer, dict):
            policyer = [policyer]
        rader.append(("Asset: %s" % d.get("@id"),
                      "%d ODRL-offert(er)" % len(policyer)))
    return rader


def _egen_forhandling(f):
    """Med en session (sessioner.py) tillhör en förhandling bara den som startade den; utan session (direktanrop) alla."""
    sess = sessioner.aktuell()
    return sess is None or f.get("@id") in sess.forhandlingar


def _eget_avtal(avtals_id):
    """Besökarens egna avtals-id, annars None: någon annans avtal visas inte (utan session visas alla)."""
    sess = sessioner.aktuell()
    return avtals_id if sess is None or avtals_id in sess.avtal else None


def _d3():
    forh = [f for f in kallor.forhandlingar(limit=20) if _egen_forhandling(f)]
    sess = sessioner.aktuell()
    kov = [f for f in kallor.kov_forhandlingar() if sess is None or f.get("correlationId") in sess.forhandlingar]
    vantande = [f for f in kov if f.get("kovBeslut") == "VANTANDE"]
    tillstand = {}
    for f in forh:
        tillstand[f.get("state")] = tillstand.get(f.get("state"), 0) + 1
    return [
        ("Förhandlingar (consumer)", len(forh)),
        ("Förhandlingstillstånd (consumer)", ", ".join("%s: %d" % kv for kv in tillstand.items())
         or "inga"),
        ("A-förhandlingar hos KoV (alla hittills)", len(kov)),
        ("VÄNTAR på KoV-beslut", len(vantande)),
    ]


def _d4():
    h = kallor.ingest_health()
    r = h.get("counters") or {}
    senaste = h.get("latestDelivery") or {}
    return [
        ("Mottagna pushar", r.get("mottagna")),
        ("Accepterade", r.get("accepterade")),
        ("Avvisade", r.get("avvisade")),
        ("Skrivna entiteter", r.get("entiteter")),
        ("Senaste", "%s %s" % (senaste.get("resultat", "-"),
                               senaste.get("detalj") or "")),
    ]


def _d5():
    ent = kallor.orion_stad_brunn()
    prov = (ent.get("provenance") or {}).get("value") or {}
    hist = kallor.mintaka_historik()
    tidssteg = len({p.get("observedAt")
                    for p in (hist.get("overflowVolumeM3") or [])})
    return [
        ("Brunnar i CIP:en", kallor.orion_stad_antal_brunnar()),
        ("overflowVolumeM3", (ent.get("overflowVolumeM3") or {}).get("value")),
        ("Proveniens: distribution", prov.get("distribution")),
        ("Proveniens: avtal", _eget_avtal(prov.get("contractAgreementId"))),
        ("Proveniens: informationsklass", prov.get("informationClass")),
        ("Tidssteg i Mintaka", tidssteg),
    ]


def _d6():
    import analys
    return analys.sammanfatta_for_steg()


# ---------------------------------------------------------------------------
# Pedagogisk kedjevy: texterna som kontrollrummet visar per steg.
#
# Varje text finns på svenska och engelska, {"sv": …, "en": …}. Servern väljer
# språk vid renderingen; loggar, komponentnamn och värden är data och
# översätts inte. **fet** blir fetstil i vyn. Texterna i _P och _TEKNIK är
# den enda källan: vy.py renderar dem men skriver inga egna stegtexter.
# ---------------------------------------------------------------------------
def _t(sv, en):
    return {"sv": sv, "en": en}


_P = {}

_P[1] = {
    "titel": _t(
        "Modellen (simulerad) skapar data\u00adprodukten",
        "The model (simulated) creates the data product"),
    "org": _t(
        "DHI",
        "DHI"),
    "kategori": "princip",
    "zon": "producent",
    "bana": "dhi",
    "distributioner": ["A", "B"],
    "vad": _t(
        "En modell räknar ut ett dygns bräddning för alla 91 brunnar och "
        "paketerar resultatet som dataprodukten Modellerad bräddata. Hos "
        "DHI görs det av Future City Flow; i demon av en simulerad, enkel "
        "beräkning (se Det här körs i steget). Den delas upp i två "
        "distributioner. Distribution A, skyddade data, är originalet med "
        "brunnarnas position. Distribution B, öppna data, tas alltid fram "
        "ur A genom att positionerna plockas bort. I demon är alla "
        "positioner påhittade.",
        "A model calculates one day of overflow for all 91 chambers and "
        "packages the result as the data product Modelled overflow data. At"
        " DHI this is done by Future City Flow; in the demo by a simple "
        "simulated calculation (see What runs in this step). It is split "
        "into two distributions. Distribution A, protected data, is the "
        "original with the chambers' positions. Distribution B, open data, "
        "is always derived from A by removing the positions. In the demo "
        "all positions are made up."),
    "varfor": _t(
        "I verkligheten räknas brunnarnas position som skyddsvärd "
        "information om VA-nätet, och demon behandlar de påhittade "
        "positionerna likadant. När produkten delas upp redan här kan "
        "distribution B spridas fritt som öppna data medan distribution A "
        "skyddas.",
        "In reality the chambers' positions count as sensitive information "
        "about the sewer network, and the demo treats the made-up positions"
        " the same way. Splitting the product here means distribution B can"
        " be shared freely as open data while distribution A is protected."),
    "dataspace": _t(
        "Själva modellen är DHI:s egen sak. Men att paketera data som en "
        "produkt, med klassning och villkor inbyggda, är en central idé i "
        "dataspaces.",
        "The model itself is DHI's business. But packaging data as a "
        "product, with classification and terms built in, is a central idea"
        " in data spaces."),
    "byggblock": _t(
        "Begrepp i DSSC: data products",
        "DSSC concept: data products"),
    "styrning": _t(
        'Dataägaren (KoV) har beslutat informationsklassningen och att produkten delas i den öppna distributionen B och den skyddade distributionen A. Det är ett styrbeslut på användningsfallets nivå; modellen utför det bara.',
        'The data owner (KoV) has decided the information classification and that the product is split into the open distribution B and the protected distribution A. That is a governance decision at the use-case level; the model merely carries it out.'),
    "akta": _t(
        "Uppdelningen i den öppna distributionen B och den skyddade "
        "distributionen A är riktig och testas automatiskt vid varje körning. "
        "B är klassad K0R1T1 och A K1R1T1.",
        "The split into the open distribution B and the protected "
        "distribution A is real and tested automatically on every run. B is "
        "classified K0R1T1 and A K1R1T1."),
    "forenklat": _t(
        "Modellen är simulerad. I stället för DHI:s hydrodynamiska Future "
        "City Flow räknas bräddvolym, bräddtid, medelflöde och vattennivå "
        "per brunn med en enkel formel. Siffrorna ser rimliga ut men är "
        "inga riktiga modellresultat.",
        "The model is simulated. Instead of DHI's hydrodynamic Future City "
        "Flow, overflow volume, overflow time, mean flow and water level "
        "per chamber are computed with a simple formula. The figures look "
        "plausible but are not real model results."),
    "komponenter": "fcf-sim",
    "protokoll": _t(
        "HTTP/JSON",
        "HTTP/JSON"),
    "knappar": {
        "kor-batch": {
            "roll": "dhi",
            "gor": _t(
                "Ber modellen räkna fram en ny dygnsbatch direkt, i stället"
                " för att vänta på nästa schemalagda körning.",
                "Asks the model to compute a new daily batch right away "
                "instead of waiting for the next scheduled run."),
            "titta": _t(
                "Producerade batchar ökar med ett och Senaste batch får ett"
                " nytt id. Datumet sist i id:t (till exempel 2026-06-29) är det"
                " modellerade dygnet batchen avser, inte när den kördes: demon"
                " spelar upp ett nytt dygn per batch.",
                "Batches produced goes up by one and Latest batch gets a "
                "new id. The date at the end of the id (for example "
                "2026-06-29) is the modelled day the batch covers, not when it "
                "was run: the demo plays back a new day for each batch."),
            "kraver": _t(
                "Inget.",
                "Nothing."),
        },
    },
}

_P[2] = {
    "titel": _t(
        "DHI erbjuder produkten med villkor",
        "DHI offers the product with terms"),
    "org": _t(
        "DHI",
        "DHI"),
    "kategori": "dataspace",
    "zon": "dataspace",
    "bana": "dhi",
    "distributioner": ["A", "B"],
    "vad": _t(
        "**Så gör vi i PoC:en.** DHI:s connector (Eclipse EDC) visar en "
        "katalog över vad DHI erbjuder. Varje distribution har ett "
        "erbjudande med villkor "
        "skrivna i ODRL, ett maskinläsbart språk för användningsvillkor. "
        "Den öppna distributionen B får användas, spridas och publiceras om"
        " källan anges. Distribution B har licensen CC BY 4.0, och "
        "erbjudandet uttrycker motsvarande villkor i ODRL. Den skyddade "
        "distributionen A får bara användas av Göteborgs Stad, får inte "
        "spridas och kräver att KoV godkänner. Staden får bara läsa "
        "katalogen om den bevisar vem den är med ett verifierbart intyg.",
        "**What we do in the PoC.** DHI's connector (Eclipse EDC) shows a "
        "catalogue of what DHI offers. Each distribution has an offer with"
        " terms written in ODRL,"
        " a machine-readable language for usage terms. The open "
        "distribution B may be used, shared and published if the source is "
        "credited. Distribution B is licensed CC BY 4.0, and the offer "
        "expresses the corresponding terms in ODRL. The protected "
        "distribution A may only be used by the City of Gothenburg, may not"
        " be shared, and requires KoV's approval. The city can only read "
        "the catalogue if it proves who it is with a verifiable "
        "credential."),
    "varfor": _t(
        "Den som vill ha data ska kunna se vad som finns och på vilka "
        "villkor innan något lämnas ut. Villkoren följer med erbjudandet i "
        "stället för att stå i ett separat pappersavtal. De sätts av den som "
        "äger data och binder den som tar emot data.",
        "Whoever wants data should be able to see what is available and on "
        "what terms before anything is released. The terms travel with the "
        "offer instead of sitting in a separate paper contract. They are set "
        "by whoever owns the data and bind whoever receives it."),
    "dataspace": _t(
        "**Gäller dataspace generellt.** Kärnan i ett dataspace. Varje part"
        " har en connector, och Dataspace Protocol (DSP) är det "
        "standardiserade sättet att prata med varandra. Varje part visar sin"
        " egen katalog över vad den erbjuder, och villkoren följer med "
        "erbjudandet. Parterna bevisar vem de är innan något visas eller "
        "delas. Det som ska hindras hindras hos den som lämnar ut data; vad "
        "mottagaren gör efteråt regleras i avtalet.",
        "**True of data spaces in general.** The core of a data space. Each"
        " party has a connector, and the Dataspace Protocol (DSP) is the "
        "standard way of talking to each other. Each party shows its own "
        "catalogue of what it offers, and the terms travel with the offer. "
        "The parties prove who they are before anything is shown or "
        "shared. What must be prevented is prevented at whoever owns the "
        "data; what the recipient does afterwards is governed by the "
        "agreement."),
    "byggblock": _t(
        "Byggblock i EU:s referensram för dataspaces (DSSC): Publication & "
        "Discovery, Access & Usage Policies, Identity & Attestation",
        "Building blocks in the EU data space reference framework (DSSC): "
        "Publication & Discovery, Access & Usage Policies, Identity & "
        "Attestation"),
    "styrning": _t(
        'Vilka standarder som gäller (DSP, ODRL, verifierbara intyg) bestäms för hela dataspacet, inte av DHI ensamt. I demon ligger valet fast i koden; i verkligheten skrivs det i dataspacets regelbok (rulebook), som saknas ännu.',
        "Which standards apply (DSP, ODRL, verifiable credentials) is decided for the whole data space, not by DHI alone. In the demo the choice is fixed in the code; in reality it is written in the data space's rulebook, which does not exist yet."),
    "akta": _t(
        "Dataspace Protocol och ODRL körs på riktigt i Eclipse EDC 0.17. "
        "Parternas identitet kontrolleras kryptografiskt vid varje anrop: "
        "redan när katalogen hämtas, och igen vid avtal och leverans.",
        "Dataspace Protocol and ODRL run for real in Eclipse EDC 0.17. The "
        "parties' identities are checked cryptographically on every "
        "request: already when the catalogue is fetched, and again for the "
        "agreement and the delivery."),
    "forenklat": _t(
        "Intygen och kryptografin är riktiga, men utfärdaren är simulerad. "
        "Svadas utfärdare (samordningsrollen, DSGA 0.1) utfärdar medlems- och "
        "deltagarintyg åt DHI och staden, och varje organisation intygar sin "
        "egen roll. I verkligheten drivs utfärdaren på styrningsorganets "
        "uppdrag; här är den en tjänst bredvid de andra. Intygen är inte "
        "förankrade i eIDAS. Samordnaren kan återkalla medlems- och deltagarintygen "
        "(medlemsintyget visas i steg 3). Rollintygen kan inte återkallas. I den publika demon är återkallelsen "
        "avstängd, eftersom den stänger ute alla besökare samtidigt; steg 3 visar den som ett inspelat exempel. "
        "Listan över återkallade intyg sparas inte utan försvinner vid omstart. Allt ligger på en server och identiteterna "
        "pekar på interna adresser utan krypterad trafik.",
        "The credentials and the cryptography are real, but the issuer is "
        "simulated. Svada's issuer (the coordination role, DSGA 0.1) issues "
        "membership and participant credentials to DHI and the city, and "
        "each organisation attests its own role. In reality the issuer is "
        "run on behalf of the governing body; here it is one more service "
        "next to the others. The credentials are not anchored in eIDAS, "
        "the coordinator can revoke the membership and participant credentials "
        "(the membership credential is shown in step 3). Role credentials cannot be revoked. In the public demo "
        "revocation is switched off, because it would exclude all visitors at the same time; step 3 shows it as a "
        "recorded example. The list of revoked "
        "credentials is not stored and disappears on restart. Everything runs on one server and the identities point to "
        "internal addresses without encrypted traffic."),
    "komponenter": "edc-provider, identity-hub-dhi, identity-hub-stad, identity-hub-svada",
    "protokoll": _t(
        "Dataspace Protocol 2025-1, ODRL, DCP",
        "Dataspace Protocol 2025-1, ODRL, DCP"),
    "knappar": {
        "hamta-katalog": {
            "roll": "stad",
            "gor": _t(
                "Stadens connector frågar DHI:s connector efter katalogen "
                "över organisationsgränsen, precis som en riktig motpart "
                "skulle göra. Det är bara en listning av vad som erbjuds "
                "och på vilka villkor; inga data lämnas ut. Själva data "
                "begärs i steg 3 (avtal) och 4 (leverans).",
                "The city's connector asks DHI's connector for the "
                "catalogue across the organisational boundary, just as a "
                "real counterpart would. This only lists what is offered "
                "and on what terms; no data is released. The data itself is"
                " requested in step 3 (agreement) and 4 (delivery)."),
            "titta": _t(
                "Loggen sammanfattar svaret som stadens connector får: en "
                "rad per distribution med klass och villkor. Hela svaret, "
                "katalogen i DCAT med villkoren i ODRL, visas under Se hur "
                "det ser ut nedan. Får du felkoden 401 (Unauthorized, "
                "”obehörig”) godtog DHI inte stadens intyg, t.ex. om "
                "stadens identitetstjänst inte svarar. Samma kontroll görs "
                "igen vid avtal och leverans.",
                "The log summarises the response the city's connector "
                "receives: one line per distribution with class and terms. "
                "The full response, the catalogue in DCAT with the terms in"
                " ODRL, is shown under See what it looks like below. The "
                "error code 401 (Unauthorized) means DHI did not accept the"
                " city's credential, for example if the city's identity "
                "service is not responding. The same check is made again "
                "for the agreement and the delivery."),
            "kraver": _t(
                "Inget.",
                "Nothing."),
        },
    },
}

_P[3] = {
    "titel": _t(
        "Avtal förhand\u00adlas, KoV säger ja eller nej",
        "Agreement negotiated, KoV says yes or no"),
    "org": _t(
        "DHI ↔ Staden (Intraservice), beslut av KoV",
        "DHI ↔ City (Intraservice), decision by KoV"),
    "kategori": "dataspace",
    "zon": "dataspace",
    "bana": "dhi-stad",
    "distributioner": ["A", "B"],
    "vad": _t(
        "**Så gör vi i PoC:en.** Stadens connector, som Intraservice "
        "driver, ber om ett avtal för en distribution av produkten. För den"
        " öppna distributionen B blir "
        "avtalet klart automatiskt. För den skyddade distributionen A "
        "stannar förhandlingen hos DHI:s connector och väntar på att KoV "
        "godkänner eller avslår. Det färdiga avtalet, med villkoren i ODRL "
        "och ett eget id, sparas hos båda parternas connectorer (id:t är "
        "olika i de två). Avtalet gäller tills det hävs eller löper ut (för A efter 30 dagar), inte bara för en "
        "enda datahämtning. Stadens id följer med data ända in i stadens "
        "plattform (steg 5).",
        "**What we do in the PoC.** The city's connector, run by "
        "Intraservice, asks for an agreement for one distribution of the "
        "product. For the open distribution B "
        "the agreement completes automatically. For the protected "
        "distribution A the negotiation stops at DHI's connector and waits "
        "for KoV to approve or reject. The finished agreement, with the "
        "terms in ODRL and its own id, is stored in both parties' "
        "connectors (the id differs between the two). The agreement is "
        "valid until it is revoked or expires (for A after 30 days), not just for one data fetch. The "
        "city's id follows the data all the way into the city's platform "
        "(step 5)."),
    "varfor": _t(
        "Data gäller stadens egna brunnar. KoV, stadens VA-förvaltning, "
        "äger data och bestämmer villkoren även om DHI tar fram data. "
        "Spärren sitter hos DHI, som lämnar ut: en spärr hos mottagaren "
        "skulle mottagaren kunna öppna själv. Villkoren sätts av ägaren och "
        "binder mottagaren. För den skyddade distributionen A sätter KoV "
        "villkoren. Intraservice tar emot data på KoV:s uppdrag och är bunden "
        "av villkoren, precis som en framtida extern mottagare skulle vara.",
        "The data concerns the city's own chambers. KoV, the city's water "
        "and sewage administration, owns the data and sets the terms even "
        "though DHI produces the data. The barrier sits at DHI, the party "
        "releasing the data: a barrier at the recipient could be opened by "
        "the recipient itself. The terms are set by the owner and bind the "
        "recipient. For the protected distribution A, KoV sets the terms. "
        "Intraservice receives the data on KoV's behalf and is bound by the "
        "terms, just as a future external recipient would be."),
    "dataspace": _t(
        "**Gäller dataspace generellt.** Kärnan i ett dataspace: "
        "dataägarens villkor verkställs maskinellt i protokollet i stället "
        "för att stå i ett pappersavtal. Mottagaren startar alltid "
        "förhandlingen. Avtalet är en maskinläsbar överenskommelse med ett "
        "eget id. Om ett mänskligt godkännande krävs, och av vem, bestämmer"
        " dataägaren för varje dataprodukt.",
        "**True of data spaces in general.** The core of a data space: the "
        "data owner's terms are enforced by machine in the protocol "
        "instead of sitting in a paper contract. The recipient always "
        "starts the negotiation. The agreement is a machine-readable "
        "arrangement with its own id. Whether a human approval is "
        "required, and by whom, is decided by the data owner for each data"
        " product."),
    "byggblock": _t(
        "Byggblock i DSSC: Contractual Framework (datadelningsavtal), Data "
        "Sovereignty",
        "DSSC building blocks: Contractual Framework (data sharing "
        "agreement), Data Sovereignty"),
    "styrning": _t(
        'Här möts tre lager. Dataspacets nivå: Svadas utfärdare avgör vem som är medlem och kan stänga ute en part genom att återkalla intyget (rutan nedan; i den publika demon visas det som ett inspelat exempel). Deltagarnas nivå: staden intygar KoV:s roll, DHI sin egen. Användningsfallets nivå: KoV, dataägaren, avgör om A får lämnas ut och kan häva avtalet.',
        "Three layers meet here. The data space level: Svada's issuer decides who is a member and can exclude a party by revoking the credential (the box below; in the public demo it is shown as a recorded example). The participant level: the city attests KoV's role, DHI its own. The use-case level: KoV, the data owner, decides whether A may be released and can revoke the agreement."),
    "akta": _t(
        "Spärren hos DHI är riktig och testas automatiskt: utan KoV:s "
        "beslut går förhandlingen om A aldrig vidare. "
        "KoV-beslutet kräver ett verifierat rollintyg; utan det svarar DHI "
        "med felkoden 401 (Unauthorized, ”obehörig”): DHI vägrar eftersom "
        "den som frågar inte kan visa att hen har rätt roll. Hävningen är "
        "också riktig: under ett hävt avtal nekar DHI:s connector nya "
        "överföringar, och stadens gateway och mottagning kontrollerar "
        "avtalets status vid varje användning.",
        "The barrier at DHI is real and tested automatically: without KoV's"
        " decision the negotiation for A never moves on."
        " KoV's decision requires a verified role credential; without it "
        "DHI answers with the error code 401 (Unauthorized): DHI refuses "
        "because the requester cannot show it holds the right role. "
        "Revocation is real too: under a revoked agreement DHI's connector "
        "refuses new transfers, and the city's gateway and intake check the "
        "agreement's status on every use."),
    "forenklat": _t(
        "Beslutet fattas med en knapp i kontrollrummet, inte i KoV:s "
        "riktiga ärendehantering. I PoC:en ligger avtal och KoV-beslut bara "
        "i minnet: avtalen i båda parternas connectorer, KoV:s beslut och "
        "hävningar i DHI:s connector och avtalens status i stadens "
        "avtalsregister. Allt försvinner vid omstart. I drift sparas de "
        "beständigt, så att det långt efteråt går att visa vilket avtal som "
        "gällde och vem som beslutade, och avtalen registreras och diarieförs "
        "enligt stadens rutin. Så fungerar "
        "PoC:en: KoV häver ett avtal direkt. PoC:en har också en regel där ett "
        "avslag av en ny begäran om A häver tidigare avtal för samma part, men den "
        "är avstängd i den här delade demon (besökarna delar tillgången, så ett "
        "avslag skulle häva andras avtal). I ett "
        "riktigt dataspace kan hävning kräva en egen åtgärd. Det här är "
        "en medveten förenkling.",
        "The decision is made with a button in the control room, not in "
        "KoV's real case management. In the PoC, agreements and KoV "
        "decisions are kept only in memory: the agreements in both parties' "
        "connectors, KoV's decisions and revocations in DHI's connector and "
        "the agreements' status in the city's agreement register. All of it "
        "is lost on restart. In production they are stored persistently, so "
        "that long afterwards it is possible to show which agreement applied "
        "and who decided, and the agreements are registered and filed in the "
        "city's records according to its routine. How the PoC works: KoV revokes an agreement directly. The PoC also has a rule "
        "where rejecting a new request for A revokes earlier agreements for the same party, "
        "but it is switched off in this shared demo (visitors share the asset, so a "
        "rejection would revoke other visitors' agreements). In a real data space, "
        "revocation may need a separate action. This is a deliberate "
        "simplification."),
    "komponenter": "edc-consumer, edc-provider med KoV-gate",
    "protokoll": _t(
        "Dataspace Protocol (förhandling), ODRL",
        "Dataspace Protocol (negotiation), ODRL"),
    "knappar": {
        "forhandla-b": {
            "roll": "stad",
            "gor": _t(
                "Staden begär ett avtal om den öppna distributionen B. "
                "Ingen människa behöver godkänna.",
                "The city requests an agreement for the open distribution "
                "B. No human needs to approve."),
            "titta": _t(
                "Inom några sekunder är avtalet klart. I loggen står det "
                "FINALIZED.",
                "Within a few seconds the agreement is done. The log says "
                "FINALIZED."),
            "kraver": _t(
                "Steg 2 fungerar.",
                "Step 2 works."),
        },
        "forhandla-a": {
            "roll": "stad",
            "gor": _t(
                "Staden begär ett avtal om den skyddade distributionen A.",
                "The city requests an agreement for the protected "
                "distribution A."),
            "titta": _t(
                "Jobbet (knapptrycket) är klart när begäran har kommit "
                "fram. Avtalet är inte klart: loggen visar att begäran "
                "väntar hos DHI (VANTANDE). Avtalet blir klart (FINALIZED) "
                "först när någon fattar beslut som KoV.",
                "The job (the button press) is done once the request has "
                "arrived. The agreement is not: the log shows the request "
                "waiting at DHI (WAITING, meaning pending). The agreement "
                "is only concluded (FINALIZED) once someone decides as KoV."),
            "kraver": _t(
                "Steg 2 fungerar.",
                "Step 2 works."),
        },
        "kov-godkann": {
            "roll": "kov",
            "klass": "ja",
            "etikett": _t(
                "KoV godkänner",
                "KoV approves"),
            "gor": _t(
                "Skickar KoV:s ja till DHI:s connector, tillsammans med ett"
                " intyg som bevisar att den som klickar har rollen KoV.",
                "Sends KoV's yes to DHI's connector, together with a "
                "credential proving that the person clicking holds the KoV "
                "role."),
            "titta": _t(
                "Avtalet för distribution A blir klart (FINALIZED). Nu kan "
                "distribution A levereras i steg 4.",
                "The agreement for distribution A completes (FINALIZED). "
                "Distribution A can now be delivered in step 4."),
            "kraver": _t(
                "En förhandling om distribution A väntar (knappen ovan).",
                "A negotiation for distribution A is waiting (button "
                "above)."),
        },
        "kov-avsla": {
            "roll": "kov",
            "klass": "fara",
            "etikett": _t(
                "KoV avslår",
                "KoV rejects"),
            "gor": _t(
                "Skickar KoV:s nej till DHI:s connector.",
                "Sends KoV's no to DHI's connector."),
            "titta": _t(
                "Den här begäran får inget avtal (TERMINATED), så ingen data "
                "lämnas ut på den. Så fungerar PoC:en: i den delade demon "
                "häver avslaget inget tidigare avtal (det skulle drabba andra "
                "besökare). Vill du häva ett avtal, använd ”KoV häver avtalet”.",
                "This request gets no agreement (TERMINATED), so no data is "
                "released on it. How the PoC works: in the shared demo "
                "the rejection revokes no earlier agreement (it would affect other "
                "visitors). To revoke an agreement, use “KoV revokes the agreement”."),
            "kraver": _t(
                "En förhandling om distribution A väntar.",
                "A negotiation for distribution A is waiting."),
        },
        "kov-hav": {
            "roll": "kov",
            "klass": "fara",
            "etikett": _t(
                "KoV häver avtalet",
                "KoV revokes the agreement"),
            "gor": _t(
                "Häver det gällande avtalet om A hos DHI, med samma "
                "rollbevis som vid ett beslut. Ett avtal gäller tills det "
                "hävs eller löper ut, så det här är sättet att dra tillbaka det i förtid utan att "
                "staden först begär något nytt.",
                "Revokes the current agreement for A at DHI, with the same "
                "role proof as for a decision. An agreement is valid until "
                "it is revoked or expires, so this is how to withdraw it early without the "
                "city first requesting anything new."),
            "titta": _t(
                "Avtalet får status HÄVT. DHI:s connector nekar nya "
                "överföringar och staden ger inga nya åtkomstnycklar. En "
                "nyckel som redan finns går inte längre att använda för att "
                "hämta data.",
                "The agreement becomes REVOKED. DHI's connector refuses new "
                "transfers and the city issues no new access keys. A key "
                "that already exists can no longer be used to fetch data."),
            "kraver": _t(
                "Ett gällande avtal om distribution A finns.",
                "A current agreement for distribution A exists."),
        },
    },
}

_P[4] = {
    "titel": _t(
        "Data levereras och kontrol\u00adleras",
        "The data is delivered and checked"),
    "org": _t(
        "Staden · Intraservice",
        "City · Intraservice"),
    "kategori": "dataspace",
    "zon": "dataspace",
    "bana": "stad",
    "distributioner": ["A", "B"],
    "vad": _t(
        "**Så gör vi i PoC:en.** Stadens connector beställer leveransen med"
        " ett avtal från steg 3 och anger vart data ska skickas. Vi har "
        "valt push: DHI:s connector hämtar den senaste beräkningen och "
        "skickar den direkt till stadens mottagningstjänst, som "
        "Intraservice driver. Data passerar inte genom stadens connector, "
        "som bara sköter avtal och beställning. Kontroller görs på båda "
        "sidor. Hos DHI kontrollerar connectorn före leveransen att avtalet"
        " finns och gäller och att det är rätt part som beställer. "
        "Beställningen bär stadens verifierbara intyg (VC), och det är med "
        "dem connectorn vet att det är staden som beställer, inte bara "
        "någon som påstår det. "
        "Innehållet granskas inte på DHI:s sida. Där räcker det att den "
        "öppna distributionen B alltid tas fram ur A genom att brunnarnas"
        " positioner plockas bort (utsläppspunkterna, där vattnet rinner ut, behåller sina koordinater). Leveransen bär en engångsnyckel som mottagningen har "
        "kopplat till avtalet. Hos staden slår mottagningen upp avtalet i "
        "stadens egen connector, kontrollerar att det gäller rätt "
        "dataprodukt och granskar själva innehållet innan något sparas, och"
        " en öppen leverans som innehåller brunnspositioner stoppas. Staden"
        " kan beställa nya leveranser under samma avtal, och varje leverans"
        " ger det som är senast just då. Ett avtal om A gäller i 30 dagar "
        "efter ingåendet, om det inte hävs dessförinnan. Var staden sedan lagrar data är stadens eget val (här "
        "CIP:en i steg 5).",
        "**What we do in the PoC.** The city's connector orders the "
        "delivery with an agreement from step 3 and says where the data "
        "should go. We chose push: DHI's connector fetches the latest "
        "calculation and sends it straight to the city's intake service, "
        "run by Intraservice. The data does not pass through the city's "
        "connector, which only handles the agreement and the order. Checks "
        "happen on both sides. At DHI, the connector checks before delivery"
        " that the agreement exists and is valid and that the right party "
        "is ordering. The order carries the city's verifiable credentials "
        "(VC), and it is by them that the connector knows it is the city "
        "ordering, not just someone claiming to be. The content is not "
        "inspected on DHI's side. There it is enough that the open "
        "distribution B is always derived from A by removing the chambers' "
        "positions (the outlet points, where the water ends up, keep their coordinates). The delivery "
        "carries a one-time key that the intake has tied to the agreement. "
        "At the city, the intake looks up the agreement in the city's own "
        "connector, checks that it covers the right data product and "
        "inspects the content itself before anything is stored, and an open "
        "delivery that contains chamber positions is stopped. The city can order new deliveries under the "
        "same agreement, and each delivery brings whatever is latest at "
        "that moment. An agreement for A is valid for 30 days after it is made, unless revoked earlier. Where the"
        " city then stores the data is the city's own choice (here the CIP "
        "in step 5)."),
    "varfor": _t(
        "Mottagaren ska inte behöva lita blint på avsändaren. Kontrollen "
        "fångar fel och avtalsbrott innan de hamnar i stadens system.",
        "The recipient shouldn't have to trust the sender blindly. The "
        "check catches errors and breaches of agreement before they reach "
        "the city's systems."),
    "dataspace": _t(
        "**Gäller dataspace generellt.** En överföring startas via "
        "dataspace-protokollet, alltid av mottagaren, och kräver ett "
        "giltigt avtal. Själva data går direkt mellan parterna, aldrig via "
        "en mellanhand. Protokollet tillåter två mönster: **push**, där "
        "avsändaren skickar data till en adress som mottagaren anger, och "
        "**pull**, där mottagaren får en tidsbegränsad nyckel och själv "
        "hämtar data hos avsändaren. Ett avtal kan användas för flera "
        "överföringar inom sina villkor, och villkoren kan begränsa till "
        "exempel giltighetstid. Var mottagaren lagrar data ligger utanför "
        "dataspacet. I PoC:en är det stadens dataplattform i steg 5. "
        "**Verifierbara intyg (VC)** är en grundteknik i dataspaces: varje "
        "part har en digital identitet och visar intyg som andra kontrollerar"
        " kryptografiskt, utan att fråga en central part. Protokollet heter "
        "DCP. I varje led (katalog, avtal, överföring) visar mottagaren "
        "intyg och den som lämnar ut data kontrollerar dem. Därför kan ingen "
        "beställa data genom att bara påstå vem den är.",
        "**True of data spaces in general.** A transfer is started through "
        "the data space protocol, always by the recipient, and requires a "
        "valid agreement. The data itself goes directly between the "
        "parties, never through an intermediary. The protocol allows two "
        "patterns: **push**, where the sender sends the data to an address "
        "the recipient gives, and **pull**, where the recipient gets a "
        "time-limited key and fetches the data from the sender itself. One "
        "agreement can be used for several transfers within its terms, and "
        "the terms can limit, for example, the validity period. Where the "
        "recipient stores the data lies outside the data space. In the PoC "
        "that is the city's data platform in step 5. **Verifiable "
        "credentials (VC)** are a basic technique in data spaces: every "
        "party has a digital identity and shows credentials that others "
        "check cryptographically, without asking a central party. The "
        "protocol is called DCP. At every step (catalogue, agreement, "
        "transfer) the recipient shows credentials and whoever releases the "
        "data checks them. That is why no one can order data by merely "
        "claiming who they are."),
    "byggblock": _t(
        "Byggblock i DSSC: Data Exchange, Identity & Attestation",
        "DSSC building blocks: Data Exchange, Identity & Attestation"),
    "styrning": _t(
        'Avtalet är den styrande handlingen. Mottagaren kontrollerar leveransen mot avtalet och klassningen utan att någon central part godkänner överföringen.',
        'The agreement is the governing document. The receiver checks the delivery against the agreement and the classification without any central party approving the transfer.'),
    "akta": _t(
        "Avtalskontrollen i mottagningen är riktig, körande kod.",
        "The agreement check in the intake is real, running code."),
    "forenklat": _t(
        "Engångsnyckeln för leveransen är ett slumptal och inte "
        "kryptografiskt kopplad till avtalet. Det är ett medvetet val, "
        "eftersom avtalet i sig redan bygger på verifierade parter. "
        "Intygen som beställningen bär är riktiga och kontrolleras vid "
        "varje meddelande.",
        "The one-time key for the delivery is a random number, not "
        "cryptographically bound to the agreement. That is a deliberate "
        "choice, since the agreement itself already rests on verified "
        "parties. The credentials the order carries are real and are "
        "checked on every message."),
    "komponenter": "edc-provider (dataplan), ingest-service",
    "protokoll": _t(
        "DSP (transfer) + HTTP-push",
        "DSP (transfer) + HTTP push"),
    "knappar": {
        "transfer-b": {
            "roll": "stad",
            "sida": "felinjektion",
            "gor": _t(
                "Levererar den öppna distributionen B med det senaste "
                "avtalet för distribution B.",
                "Delivers the open distribution B using the latest "
                "agreement for distribution B."),
            "titta": _t(
                "Loggen säger att mottagningen KVITTERADE, och Accepterade "
                "ökar med ett.",
                "The log says the intake acknowledged it (ACKNOWLEDGED), and "
                "Accepted goes up by one."),
            "kraver": _t(
                "Ett avtal för distribution B (steg 3).",
                "An agreement for distribution B (step 3)."),
        },
        "transfer-a": {
            "roll": "stad",
            "gor": _t(
                "Levererar den skyddade distributionen A om KoV har "
                "godkänt.",
                "Delivers the protected distribution A if KoV has approved."),
            "titta": _t(
                "Utan godkännande får du ett felmeddelande i loggen. Det är spärren som "
                "fungerar, inte något som är trasigt.",
                "Without approval you get an error message in the log. "
                "That's the barrier working, not something broken."),
            "kraver": _t(
                "KoV har godkänt distribution A i steg 3.",
                "KoV has approved distribution A in step 3."),
        },
    },
    "extra": _t(
        "Vill du se kontrollen slå till? I fliken Felinjektion kan du få "
        "modellen att smyga in brunnspositioner i den öppna distributionen "
        "B. Mottagningen avvisar då leveransen. Ett avtal för A gäller "
        "tills det hävs eller löper ut. Avslår KoV en ny begäran om A häver "
        "avslaget inget tidigare avtal i den delade demon; det gör ”KoV häver avtalet”, "
        "och då nekas leveransen av A.",
        "Want to see the check kick in? In the Fault injection tab you can "
        "make the model sneak chamber positions into the open distribution "
        "B. The intake then rejects the delivery. An agreement for A stays "
        "valid until it is revoked or expires. If KoV rejects a new request "
        "for A, the rejection revokes no earlier agreement in the shared demo; "
        "“KoV revokes the agreement” does, and the delivery of A is then refused."),
}

_P[5] = {
    "titel": _t(
        "Staden lagrar med ursprungs\u00admärkning",
        "The city stores with provenance"),
    "org": _t(
        "Staden · Intraservice",
        "City · Intraservice"),
    "kategori": "princip",
    "zon": "publicering",
    "bana": "stad",
    "distributioner": [],
    "vad": _t(
        "Leveransen görs om till stadens format och sparas i stadens "
        "dataplattform (kallas CIP), som Intraservice driver. Varje värde "
        "får en ursprungsmärkning. Det mesta följer med från DHI i "
        "leveransen (batch, distribution, klass, licens och utgivare); "
        "staden lägger själv till avtalets nummer, en länk till avtalet och "
        "när leveransen togs emot. Historiken sparas också. Så följer "
        "villkoren med: ODRL-texten ligger inte i själva värdena, men "
        "avtalets id gör det, och via id:t går villkoren att slå upp i "
        "stadens connector så länge avtalet finns kvar (i PoC:en till "
        "nästa omstart).",
        "The delivery is converted to the city's format and stored in the "
        "city's data platform (called CIP), run by Intraservice. Every "
        "value gets a provenance label. Most of it comes along from DHI in "
        "the delivery (batch, distribution, class, licence and publisher); "
        "the city itself adds the agreement number, a link to the agreement "
        "and when the delivery was received. The history is stored too. This is "
        "how the terms follow along: the ODRL text is not inside the "
        "values, but the agreement's id is, and through the id the terms "
        "can be looked up in the city's connector as long as the agreement "
        "exists (in the PoC until the next restart)."),
    "varfor": _t(
        "Det ska gå att svara på frågan varifrån ett värde kommer, och om "
        "staden fick använda det, långt efteråt.",
        "It must be possible, long afterwards, to answer where a value came"
        " from and whether the city was allowed to use it."),
    "dataspace": _t(
        "Lagringen är stadens egen. Ursprungsmärkningen knyter värdet till "
        "dataspace-avtalet: samma avtals-id som i steg 3.",
        "The storage is the city's own. The provenance label ties the value"
        " to the data space agreement: the same agreement id as in step 3."),
    "byggblock": _t(
        "Byggblock i DSSC: Provenance & Traceability",
        "DSSC building block: Provenance & Traceability"),
    "styrning": _t(
        'Stadens egen datastyrning gäller för lagringen: informationsklassning, proveniens och gallring. Gallring enligt Arkivnämndens beslut är inte på plats i demon.',
        "The city's own data governance applies to storage: information classification, provenance and retention. Retention according to the archive board's decision is not in place in the demo."),
    "akta": _t(
        "NGSI-LD-lagringen och historiken är riktiga. Stadens gateway nekar"
        " läsning av den skyddade distributionen A utan behörighet.",
        "The NGSI-LD storage and history are real. The city's gateway "
        "refuses to read the protected distribution A without "
        "authorisation."),
    "forenklat": _t(
        "Datamodellen för brunnen är egen och inte en publicerad "
        "standardmodell.",
        "The data model for the chamber is a local one, not a published "
        "standard model."),
    "komponenter": "orion-stad / CIP, mintaka, stad-gateway",
    "protokoll": _t(
        "NGSI-LD, NGSI-LD temporal",
        "NGSI-LD, NGSI-LD temporal"),
    "inga_knappar": _t(
        "Steget har inga knappar. Fliken Följ ett värde visar samma "
        "avtals-id i steg 3, 4 och 5.",
        "This step has no buttons. The Follow a value tab shows the same "
        "agreement id in steps 3, 4 and 5."),
    "inga_knappar_sida": "folj",
}

_P[6] = {
    "titel": _t(
        "Staden använder data för analys och beslut",
        "The city uses the data for analysis and decisions"),
    "org": _t(
        "Staden · Kretslopp och Vatten",
        "City · Kretslopp och Vatten"),
    "kategori": "princip",
    "zon": "publicering",
    "bana": "stad",
    "distributioner": ["A", "B"],
    "vad": _t(
        "Nu används data. Vyn nedan rangordnar de 91 brunnarna efter "
        "modellerad bräddvolym och pekar ut vilka som bör inspekteras "
        "först. Med den öppna distributionen B går det att se vilka "
        "vattendrag som tar emot mest bräddning. Med den skyddade "
        "distributionen A, som kräver ett gällande avtal, går det att peka "
        "ut vilka brunnar det gäller och lägga dem på en karta. Raden "
        "ovanför tabellen visar vilket avtal, vilken batch och vilken "
        "distribution analysen bygger på.",
        "Now the data is used. The view below ranks the 91 chambers by "
        "modelled overflow volume and points out which to inspect first. "
        "With the open distribution B it shows which watercourses receive "
        "the most overflow. With the protected distribution A, which "
        "requires a current agreement, it can point out which chambers are "
        "concerned and place them on a map. The line above the table shows "
        "the agreement, the batch and the distribution the analysis is "
        "based on."),
    "varfor": _t(
        "Ett dataspace handlar inte bara om att flytta data utan om att "
        "data kommer till användning. Här syns varför avtalet och "
        "klassningen spelar roll: med öppna data ser staden var bräddningen "
        "är störst, med skyddade data vilka brunnar som ska inspekteras, "
        "och den delen fungerar bara så länge avtalet gäller.",
        "A data space is not only about moving data but about the data "
        "being used. This shows why the agreement and the classification "
        "matter: with open data the city sees where overflow is greatest, "
        "with protected data which chambers to inspect, and that part only "
        "works as long as the agreement is valid."),
    "dataspace": _t(
        "Användningen sker under avtalet. Hävs avtalet för A slutar den "
        "delen av vyn att fungera, medan öppna data fortsätter. Förbuden "
        "mot att sprida och publicera gäller också här, men efter en "
        "överföring kan ingen avsändare tekniskt tvinga fram dem. De är en "
        "del av avtalet och mottagarens eget ansvar.",
        "The use takes place under the agreement. If the agreement for A is "
        "revoked that part of the view stops working, while open data "
        "continues. The prohibitions on sharing and publishing apply here "
        "too, but after a transfer no sender can technically enforce them. "
        "They are part of the agreement and the recipient's own "
        "responsibility."),
    "byggblock": _t(
        "Begrepp i DSSC: data consumer (användning av data)",
        "DSSC concept: data consumer (use of data)"),
    "styrning": _t(
        'Staden ansvarar för sin användning inom avtalet. Att användningen följer ändamålet kan inte kontrolleras tekniskt; det vilar på avtalet och på granskning. Hävningen visar att styrningen gäller även efter leveransen.',
        'The city is responsible for its use within the agreement. That the use follows the purpose cannot be checked technically; it rests on the agreement and on audit. The revocation shows that governance still applies after delivery.'),
    "akta": _t(
        "Läsningen ur stadens dataplattform och kontrollen av avtalet är "
        "riktiga. För A hämtar vyn en nyckel med det gällande avtalets id, "
        "och stadens gateway nekar när avtalet har hävts.",
        "Reading from the city's data platform and the check of the "
        "agreement are real. For A the view fetches a key with the current "
        "agreement's id, and the city's gateway refuses once the agreement "
        "has been revoked."),
    "forenklat": _t(
        "Analysen är medvetet enkel: en rangordning efter modellerad "
        "bräddvolym, där du väljer hur många brunnar som pekas ut. Datat är delvis "
        "syntetiskt (90 av 91 brunnar) och bräddtiden är lika för alla "
        "brunnar i modellen, så den används inte. Vyn visar hur ett beslut "
        "kan stödjas av data som kommit genom ett avtal, inte att modellen "
        "är rätt.",
        "The analysis is deliberately simple: a ranking by modelled "
        "overflow volume, where you choose how many chambers are pointed out. The data is "
        "partly synthetic (90 of 91 chambers) and the overflow time is the "
        "same for all chambers in the model, so it is not used. The view "
        "shows how a decision can be supported by data that arrived through "
        "an agreement, not that the model is right."),
    "komponenter": "orion-stad, mintaka, stad-gateway, avtalsregistret",
    "protokoll": _t(
        "NGSI-LD, HTTP/JSON",
        "NGSI-LD, HTTP/JSON"),
    "inga_knappar": _t(
        "Steget har inga knappar. Vyn här nedanför är steget: välj distribution och"
        " hur många brunnar som ska pekas ut.",
        "This step has no buttons. The view below is the step: choose the "
        "distribution and how many chambers to point out."),
}


_TEKNIK = {
    1: [
        {"namn": _t("fcf-sim (står i för DHI:s Future City Flow)",
                  "fcf-sim (stands in for DHI's Future City Flow)"),
         "status": "simulerad",
         "egen": True,
         "gor": _t(
             "Simulerad modell. Den riktiga Future City Flow hos DHI är en "
             "hydrodynamisk modell av hela ledningsnätet. Här görs en enkel"
             " beräkning per brunn i stället: bräddvolym, bräddtid, "
             "medelflöde och vattennivå över krönet, räknat ur mätvärdena "
             "med en enkel formel. Bara Krokängsparken räknas på riktiga "
             "mätvärden; de andra 90 brunnarna får påhittade serier.",
             "Simulated model. The real Future City Flow at DHI is a "
             "hydrodynamic model of the whole sewer network. Here a simple "
             "per-chamber calculation is done instead: overflow volume, "
             "overflow time, mean flow and water level above the weir, "
             "computed from the readings with a simple formula. Only "
             "Krokängsparken is computed from real readings; the other 90 "
             "chambers get made-up series.")},
        {"namn": _t("Distribution B, öppna data (K0R1T1)",
                  "Distribution B, open data (K0R1T1)"),
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Riktig produktlogik: samma resultat med brunnarnas position "
             "borttagen. Märks som öppna data och får spridas fritt mot "
             "källhänvisning. Testas vid varje körning så att ingen "
             "position slinker med.",
             "Real product logic: the same result with chamber positions "
             "removed. Marked as open data and may be shared freely with "
             "attribution. Tested on every run so no position slips "
             "through.")},
        {"namn": _t("Distribution A, skyddade data (K1R1T1)",
                  "Distribution A, protected data (K1R1T1)"),
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Riktig produktlogik: hela resultatet med brunnarnas position."
             " Märks som icke-offentlig och får bara lämnas ut till staden "
             "efter KoV:s godkännande.",
             "Real product logic: the full result with chamber positions. "
             "Marked non-public and may only be released to the city after "
             "KoV's approval.")},
    ],
    2: [
        {"namn": "Eclipse EDC 0.17, connector (DHI)",
         "status": "akta",
         "lankar": [["GitHub", "https://github.com/eclipse-edc/Connector"]],
         "gor": _t(
             "Katalog, villkor i ODRL och Dataspace Protocol mot staden.",
             "Catalogue, ODRL terms and Dataspace Protocol towards the "
             "city.")},
        {"namn": _t("Eclipse EDC IdentityHub (DCP), DHI och staden",
                    "Eclipse EDC IdentityHub (DCP), DHI and the city"),
         "status": "forenklad",
         "lankar": [["GitHub", "https://github.com/eclipse-edc/IdentityHub"]],
         "gor": _t(
             "Riktig programvara för verifierbara intyg, byggd för "
             "dataspaces. Varje part har en egen instans med egen "
             "identitet och egna nycklar, och intygar sin egen roll: "
             "staden intygar att Kretslopp och Vatten är "
             "rättighetsinnehavare, DHI intygar sin egen roll. "
             "Verifieringen godtar varje intygstyp bara från rätt "
             "utfärdare. Allt körs på en server utan krypterad trafik och "
             "utan beständig lagring.",
             "Real software for verifiable credentials, built for data "
             "spaces. Each party has its own instance with its own "
             "identity and keys, and attests its own role: the city "
             "attests that Kretslopp och Vatten is the rights holder, DHI "
             "attests its own role. The verification accepts each "
             "credential type only from the right issuer. Everything runs "
             "on one server without encrypted traffic and without "
             "persistent storage.")},
        {"namn": _t("Svadas utfärdare (DSGA 0.1), simulerad tillitstjänst",
                    "Svada's issuer (DSGA 0.1), simulated trust service"),
         "status": "simulerad",
         "lankar": [["GitHub", "https://github.com/eclipse-edc/IdentityHub"]],
         "gor": _t(
             "Samma programvara som de andra instanserna, men med en annan "
             "uppgift: den utfärdar medlems- och deltagarintyg åt DHI och "
             "staden och inga rollintyg. Den simulerar dataspacets "
             "tillitstjänst. Intygen är inte förankrade i eIDAS och listan över "
             "återkallade intyg ligger bara i minnet, och i verkligheten drivs utfärdaren av "
             "Intraservice på styrningsorganets uppdrag, skild från "
             "stadens egen instans.",
             "The same software as the other instances, with a different "
             "job: it issues membership and participant credentials to DHI "
             "and the city, and no role credentials. It simulates the data "
             "space's trust service. The credentials are not anchored in "
             "eIDAS and the list of revoked credentials is only kept in memory, and in reality the issuer is "
             "run by Intraservice on behalf of the governing body, "
             "separate from the city's own instance.")},
    ],
    3: [
        {"namn": _t("Eclipse EDC 0.17, connector (staden)",
                  "Eclipse EDC 0.17, connector (city)"),
         "status": "akta",
         "lankar": [["GitHub", "https://github.com/eclipse-edc/Connector"]],
         "gor": _t(
             "Förhandlar avtal med DHI:s connector enligt Dataspace "
             "Protocol.",
             "Negotiates agreements with DHI's connector under the "
             "Dataspace Protocol.")},
        {"namn": _t("KoV-spärr (tillägg i EDC hos DHI)",
                  "KoV gate (EDC extension at DHI)"),
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Pausar förhandlingen om distribution A tills KoV har "
             "beslutat, och kräver KoV-intyg.",
             "Pauses the negotiation for distribution A until KoV decides, "
             "and requires a KoV credential.")},
        {"namn": _t("KoV-beslutet i kontrollrummet",
                  "The KoV decision in the control room"),
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Skickar ett riktigt beslut med riktigt KoV-intyg till DHI:s "
             "connector. Det enda som spelas är personen: du klickar i "
             "stället för en handläggare på KoV.",
             "Sends a real decision with a real KoV credential to DHI's "
             "connector. Only the person is played: you click instead of a "
             "KoV case officer.")},
    ],
    4: [
        {"namn": _t("Eclipse EDC dataplan (DHI)",
                  "Eclipse EDC data plane (DHI)"),
         "status": "akta",
         "lankar": [["GitHub", "https://github.com/eclipse-edc/Connector"]],
         "gor": _t(
             "Skickar data direkt till staden när avtal finns.",
             "Sends the data directly to the city once there is an "
             "agreement.")},
        {"namn": _t("ingest-service (staden)",
                  "ingest-service (city)"),
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Kontrollerar leveransen mot avtalet innan något sparas. "
             "Engångsnyckeln är förenklad.",
             "Checks the delivery against the agreement before anything is "
             "stored. The one-time key is simplified.")},
    ],
    5: [
        {"namn": _t("FIWARE Orion-LD (stadens CIP)",
                  "FIWARE Orion-LD (the city's CIP)"),
         "status": "akta",
         "lankar": [["GitHub", "https://github.com/FIWARE/context.Orion-LD"]],
         "gor": _t(
             "Stadens dataplattform med ursprungsmärkning.",
             "The city's data platform with provenance.")},
        {"namn": "FIWARE Mintaka + TimescaleDB",
         "status": "akta",
         "lankar": [["Mintaka", "https://github.com/FIWARE/mintaka"], ["TimescaleDB", "https://github.com/timescale/timescaledb"]],
         "gor": _t(
             "Lagrar och visar historiken.",
             "Stores and serves the history.")},
        {"namn": "stad-gateway",
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Släpper bara ut distribution A till den som har avtal.",
             "Releases distribution A only to holders of an agreement.")},
    ],
    6: [
        {"namn": _t("Analysvyn (kontrollrummet)", "The analysis view (control room)"),
         "status": "forenklad",
         "egen": True,
         "gor": _t(
             "Rangordnar brunnarna efter bräddvolym och visar ursprunget.",
             "Ranks the chambers by overflow volume and shows the origin.")},
        {"namn": _t("FIWARE Orion-LD (stadens CIP)",
                  "FIWARE Orion-LD (the city's CIP)"),
         "status": "akta",
         "lankar": [["GitHub", "https://github.com/FIWARE/context.Orion-LD"]],
         "gor": _t(
             "Källan för de värden som analyseras.",
             "The source of the values that are analysed.")},
        {"namn": "stad-gateway",
         "status": "akta",
         "egen": True,
         "gor": _t(
             "Ger en nyckel för A bara om avtalet gäller.",
             "Gives a key for A only if the agreement is valid.")},
        {"namn": _t("Stadens avtalsregister", "The city's agreement register"),
         "status": "forenklad",
         "egen": True,
         "gor": _t(
             "Visar om avtalet gäller. Statusen hämtas från DHI.",
             "Shows whether the agreement is valid. The status is fetched "
             "from DHI.")},
    ],
}

# status i _TEKNIK: "akta" = riktig tjänst, "forenklad" = riktig tjänst men
# förenklad, "simulerad" = låtsas göra något den inte gör (mätdatat i steg 1,
# modellberäkningen i steg 1 och Svadas utfärdare i steg 2). "egen" = egen kod i PoC:en.


# ---------------------------------------------------------------------------
# Stegen
# ---------------------------------------------------------------------------
STEG = [
    {"nr": 1, "titel": "Future City Flow modellerar dataprodukten",
     "org": "DHI", "protokoll": "HTTP/JSON",
     "beskrivning": "FCF aggregerar dygnet för alla 91 brunnar och producerar "
                    "\"Modellerad bräddata\" i två distributioner: A "
                    "(K1R1T1, med brunns-GIS) och B (K0R1T1, GIS borttagen).",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "G17 (Låg) – modellens realism är en medveten, väl redovisad "
            "avgränsning enligt §8.4:s krav på att ange kända brister. G4 "
            "(Väsentlig) – grunddata kopieras in i produkten i stället för "
            "att refereras från en betrodd källa (§5.3); det är just dessa "
            "inkopierade positioner som gör att den skyddade distributionen A bär känsliga uppgifter och "
            "tvingar fram A/B-uppdelningen. G2 (Väsentlig, delvis stängd) – "
            "kvalitetsdeklarationen finns i katalogen men inga kvalitetsregler "
            "mäts, trots att §5.4/§8.4 kräver det.")},
     "detaljer": _d1,
     "atgarder": [{"id": "kor-batch", "roll": "dhi",
                   "etikett": _t("Kör en batch nu",
                                 "Run a batch now")}],
     "pedagogik": _P[1], "teknik": _TEKNIK[1]},

    {"nr": 2, "titel": "EDC-providern annonserar i DSP-katalogen",
     "org": "DHI", "protokoll": "Dataspace Protocol",
     "beskrivning": "Providerns katalog bär en ODRL-offert per distribution. "
                    "A:s offert förbjuder distribute/publish och kräver "
                    "KoV-godkännande; B:s tillåter båda mot attribution.",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "G1 (Kritisk) är därmed delvis stängt sedan verifierbar identitet och utfärdare med rätt mandat infördes – "
            "identitet och tillit är inte längre mockad, och Svadas "
            "utfärdare (simulerad DSGA 0.1) utfärdar medlems- och "
            "deltagarintyg medan organisationerna intygar sina egna roller. "
            "DSSC Blueprint rekommenderar för "
            "tillitsnivå två att deltagaridentitet uttrycks som verifierbara "
            "attest (W3C Verifiable Credentials), vilket nu är fallet (tre "
            "attesttyper: SvadaParticipantCredential, "
            "SvadaMembershipCredential, SvadaRoleCredential). G16 (Måttlig) "
            "kvarstår – organisationsgränsen i sig är simulerad: en maskin, "
            "docker-nät, ingen TLS – men två riktigt separata EDC-connectorer"
            " talar äkta DSP över den. Riktig gräns mellan organisationer är "
            "planerad (separata organisationer).")},
     "detaljer": _d2,
     "atgarder": [{"id": "hamta-katalog", "roll": "stad",
                   "etikett": _t("Hämta DSP-katalogen",
                                 "Fetch the DSP catalogue")}],
     "pedagogik": _P[2], "teknik": _TEKNIK[2]},

    {"nr": 3, "titel": "Kontraktsförhandling och KoV-gate",
     "org": "DHI ↔ Staden", "protokoll": "Dataspace Protocol",
     "beskrivning": "B finaliseras automatiskt. A stannar hos PROVIDERN tills "
                    "Kretslopp och Vatten (Data Rights Holder) fattar beslut "
                    "– gaten sitter aldrig på consumer-sidan.",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "Kärnan i arkitekturinvariant 1, Suveränitet (§6.6). G1 (Kritisk)"
            " är stängt: mekanismen är äkta OCH vem som trycker på knappen "
            "verifieras nu kryptografiskt (verifierbar DCP-identitet). Det här är DSSC"
            " Blueprint-nivån ”datadelningsavtal”: avtalet per dataprodukt, "
            "med ODRL-policyn som maskinläsbar del – en av avtalsramverkets "
            "tre nivåer, utöver institutionella avtal och tjänsteavtal.")},
     "detaljer": _d3,
     "atgarder": [{"id": "forhandla-b", "roll": "stad",
                   "etikett": _t("Förhandla Distribution B",
                                 "Negotiate Distribution B")},
                  {"id": "forhandla-a", "roll": "stad",
                   "etikett": _t("Förhandla Distribution A",
                                 "Negotiate Distribution A")}],
     "pedagogik": _P[3], "teknik": _TEKNIK[3]},

    {"nr": 4, "titel": "Transfer och stadens mottagning", "org": "Staden",
     "protokoll": "DSP + HTTP-push",
     "beskrivning": "Providerns dataplan hämtar ur fcf-sim och PUSHAR till "
                    "ingest-service med en engångsauktorisation. Ingest "
                    "validerar mot avtalet innan något skrivs.",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "Bär upp arkitekturinvariant 2 (§6.6). G1 (identitet) är stängt "
            "sedan verifierbar identitet – auktorisationstokenens egen svaghet kvarstår "
            "som ett medvetet, dokumenterat designval (se docstrings i "
            "auktorisation.py/atkomst.py), inte längre ett utflöde av en "
            "mockad identitet.")},
     "detaljer": _d4,
     "atgarder": [{"id": "transfer-b", "roll": "stad", "sida": "felinjektion",
                   "etikett": _t("Leverera B (kör transfer)",
                                 "Deliver B (run transfer)")},
                  {"id": "transfer-a", "roll": "stad",
                   "etikett": _t("Leverera A (kör transfer)",
                                 "Deliver A (run transfer)")}],
     "pedagogik": _P[4], "teknik": _TEKNIK[4]},

    {"nr": 5, "titel": "CIP:en och tidsserierna", "org": "Staden",
     "protokoll": "NGSI-LD + temporal",
     "beskrivning": "Ingest transformerar till en egen entitet per distribution "
                    "(SewerOverflowModelB och SewerOverflowModelA) med "
                    "proveniens (avtal, dataprodukt, distribution, batch) och "
                    "skriver till orion-stad. Mintaka läser TRoE-historiken.",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "G22 (åtgärdad 2026-07-28) – innan gatewayen fanns publicerade "
            "orion-stad port 2026 rakt ut utan kontroll. G7 (Måttlig) – ingen"
            " publicerad Smart Data Model. G21 (Väsentlig) – proveniensen "
            "växer okontrollerat (≈2,9 MB för en enda brunns historik). G12 "
            "(Måttlig, indirekt): i arkitekturen möts uppmätt och modellerat "
            "värde i CIP:en, men i PoC:en görs den jämförelsen i "
            "kontrollrummet i stället (och ingår inte i Svada-mini).")},
     "detaljer": _d5, "atgarder": [],
     "pedagogik": _P[5], "teknik": _TEKNIK[5]},


    {"nr": 6, "titel": "Staden använder data för analys och beslut",
     "org": "Staden", "protokoll": "NGSI-LD",
     "beskrivning": "Inspektionsprioritering: brunnarna rangordnas efter "
                    "modellerad bräddvolym. B-läget är öppet; A-läget kräver "
                    "ett gällande avtal och nekas av gatewayen när avtalet "
                    "har hävts.",
     "fordjupning": {
         # Visas bara i den interna varianten (DEMO_VARIANT=intern).
         "blueprint": (
            "Steget visar användningen av data i ett dataspace (docs/01-"
            "oversikt.md). Det är en demonstration av hur avtalet styr "
            "användningen, inte en färdig analystjänst.")},
     "detaljer": _d6, "atgarder": [],
     "pedagogik": _P[6], "teknik": _TEKNIK[6]},
]

# Vilket steg varje åtgärd hör till (används av API:t för att slippa
# skicka med stegnumret separat).
ATGARD_STEG = {a["id"]: s["nr"] for s in STEG for a in s["atgarder"]}


# ---------------------------------------------------------------------------
# Språk, åtgärdsmetadata och kontrollen av knapptäckning
# ---------------------------------------------------------------------------
SPRAK = ("sv", "en")
ROLLER = ("stad", "dhi", "kov", "demo", "portal")
SIDOR = ("folj", "suveranitet", "avvikelse", "felinjektion")
KATEGORIER = ("dataspace", "princip", "helhet")
ZONER = ("producent", "dataspace", "publicering")
BANOR = ("dhi", "dhi-stad", "stad", "portal")
TEKNIKSTATUS = ("akta", "forenklad", "simulerad")


def text(varde, sprak="sv"):
    """Väljer språk ur en {"sv": …, "en": …}-text. Vanliga strängar och None
    returneras som de är, så att anropare inte behöver skilja på dem."""
    if isinstance(varde, dict):
        return varde.get(sprak) or varde.get("sv")
    return varde


def kontrollera_knapptackning(steg=None):
    """Returnerar en lista med fel (tom = allt täckt). Körs när modulen
    importeras, så att en ny åtgärd inte kan läggas till utan förklaring:
    varje åtgärd måste ha roll och etikett, och en text om vad den gör, vad
    man ska titta efter och vad den förutsätter, på båda språken."""
    fel = []
    for s in (STEG if steg is None else steg):
        nr = s["nr"]
        ped = s.get("pedagogik") or {}
        if not ped:
            fel.append("steg %s saknar pedagogik" % nr)
            continue
        for nyckel in ("titel", "org", "vad", "varfor", "dataspace", "akta",
                       "forenklat", "protokoll"):
            for sp in SPRAK:
                if not text(ped.get(nyckel), sp):
                    fel.append("steg %s: pedagogik.%s saknas på %s"
                               % (nr, nyckel, sp))
        for nyckel, tillatna in (("kategori", KATEGORIER), ("zon", ZONER),
                                 ("bana", BANOR)):
            if ped.get(nyckel) not in tillatna:
                fel.append("steg %s: pedagogik.%s=%r är ogiltig"
                           % (nr, nyckel, ped.get(nyckel)))
        knappar = ped.get("knappar") or {}
        atgard_id = [a["id"] for a in s["atgarder"]]
        for a in s["atgarder"]:
            if a.get("roll") not in ROLLER:
                fel.append("åtgärd %s saknar giltig roll" % a["id"])
            if a.get("sida") is not None and a["sida"] not in SIDOR:
                fel.append("åtgärd %s: ogiltig sida %r" % (a["id"], a["sida"]))
            for sp in SPRAK:
                if not text(a.get("etikett"), sp):
                    fel.append("åtgärd %s saknar etikett på %s" % (a["id"], sp))
        for aid, k in knappar.items():
            if aid not in atgard_id and k.get("roll") != "kov":
                fel.append("steg %s: knappen %s finns inte som åtgärd" % (nr, aid))
            if aid not in atgard_id:
                if k.get("roll") not in ROLLER:
                    fel.append("knappen %s saknar giltig roll" % aid)
                for sp in SPRAK:
                    if not text(k.get("etikett"), sp):
                        fel.append("knappen %s saknar etikett på %s" % (aid, sp))
            for nyckel in ("gor", "titta", "kraver"):
                for sp in SPRAK:
                    if not text(k.get(nyckel), sp):
                        fel.append("knappen %s saknar %s på %s" % (aid, nyckel, sp))
        for aid in atgard_id:
            if aid not in knappar:
                fel.append("åtgärd %s saknar knapptext (pedagogik.knappar)" % aid)
        if not knappar:
            for sp in SPRAK:
                if not text(ped.get("inga_knappar"), sp):
                    fel.append("steg %s saknar knappar och inga_knappar på %s"
                               % (nr, sp))
        for x in s.get("teknik") or []:
            if x.get("status") not in TEKNIKSTATUS:
                fel.append("steg %s: teknik %r har ogiltig status"
                           % (nr, x.get("namn")))
            for sp in SPRAK:
                if not text(x.get("gor"), sp):
                    fel.append("steg %s: teknik %r saknar text på %s"
                               % (nr, x.get("namn"), sp))
        if not s.get("teknik"):
            fel.append("steg %s saknar teknik" % nr)
    return fel


def kontrollera_mot_jobb(jobb_atgarder):
    """Varje åtgärd i jobb.ATGARDER ska ha en knapptext i något steg, och
    varje knapp med roll i steg.py ska kunna startas som jobb. Anropas från
    main.py (steg.py får inte importera jobb.py)."""
    fel = []
    knappar = {}
    for s in STEG:
        for aid, k in (s["pedagogik"].get("knappar") or {}).items():
            knappar[aid] = s["nr"]
    for aid in jobb_atgarder:
        if aid not in knappar:
            fel.append("jobbåtgärden %s saknar knapptext i steg.py" % aid)
    for aid, nr in knappar.items():
        if aid not in jobb_atgarder:
            fel.append("knappen %s (steg %s) saknar jobbåtgärd" % (aid, nr))
    return fel


_TACKNINGSFEL = kontrollera_knapptackning()
if _TACKNINGSFEL:
    raise AssertionError("steg.py: " + "; ".join(_TACKNINGSFEL))


# Etiketterna i detaljtabellerna kommer ur _d1.._d10 på svenska. De översätts
# här; värden och identifierare (observedAt, device_id …) är data och rörs inte.
_DETALJ_EN = {
    "Skickade mätvärden": "Readings sent",
    "Senaste observedAt": "Latest observedAt",
    "Totalflöde tf (m³/s)": "Total flow tf (m³/s)",
    "Spillflöde sf (m³/s)": "Spill flow sf (m³/s)",
    "Avvikelseläge": "Deviation mode",
    "MQTT-topic": "MQTT topic",
    "Provisionerade enheter": "Provisioned devices",
    "Entitet": "Entity",
    "Producerade batchar": "Batches produced",
    "Senaste batch": "Latest batch",
    "Modellerat dygn (datumet i batch-id:t)": "Modelled day (the date in the batch id)",
    "Mätpunkter i fönstret": "Measurement points in the window",
    "Brunnar i modellen": "Chambers in the model",
    "Felinjektion": "Fault injection",
    "Datamängder i DSP-katalogen": "Datasets in the DSP catalogue",
    "Förhandlingar (consumer)": "Negotiations (consumer)",
    "Förhandlingstillstånd (consumer)": "Negotiation states (consumer)",
    "A-förhandlingar hos KoV (alla hittills)": "A negotiations at KoV (all so far)",
    "VÄNTAR på KoV-beslut": "WAITING for KoV decision",
    "Mottagna pushar": "Pushes received",
    "Accepterade": "Accepted",
    "Avvisade": "Rejected",
    "Skrivna entiteter": "Entities written",
    "Senaste": "Latest",
    "Brunnar i CIP:en": "Chambers in the CIP",
    "Proveniens: distribution": "Provenance: distribution",
    "Proveniens: avtal": "Provenance: agreement",
    "Proveniens: informationsklass": "Provenance: information class",
    "Tidssteg i Mintaka": "Time steps in Mintaka",
    "Datamängd": "Dataset",
    "Distributioner": "Distributions",
    "Brunnar i stadens plattform": "Chambers in the city's platform",
    "Brunnar som bräddar": "Chambers overflowing",
    "Total bräddvolym (m³)": "Total overflow volume (m³)",
    "Högsta bräddvolym (m³)": "Highest overflow volume (m³)",
    "Gällande avtal om A": "Current agreement for A",
}
_DETALJ_EN_DEL = (
    (" – datamängder", " – datasets"),
    (" – distributioner", " – distributions"),
    (" – bortfiltrerade (accessRights)", " – filtered out (accessRights)"),
    (" – avvisade (SHACL)", " – rejected (SHACL)"),
    (" – senaste skörd", " – latest harvest"),
)


def oversatt_detalj(etikett, varde, sprak="sv"):
    """(etikett, värde) -> samma par på önskat språk."""
    if sprak != "en":
        return etikett, varde
    en = _DETALJ_EN.get(etikett)
    if en is None:
        en = etikett
        for sv, eng in _DETALJ_EN_DEL:
            en = en.replace(sv, eng)
    if varde in ("av", "inga"):
        varde = "off" if varde == "av" else "none"
    elif isinstance(varde, str):
        for sv, eng in (("ODRL-offert(er)", "ODRL offer(s)"), ("PÅ (x", "ON (x")):
            varde = varde.replace(sv, eng)
        import i18n
        # Statuskoder och meddelanden från mottagningen ("Senaste": AUKTORISATION-NEKAD avtalet …).
        koder = [k for k in i18n.KODER if varde.startswith(k + " ")]
        if koder:
            varde = i18n.kod(koder[0]) + varde[len(koder[0]):]
        varde = i18n.oversatt(varde)
    return en, varde


# ---------------------------------------------------------------------------
# ODRL-villkoren i klartext (steg 2)
# ---------------------------------------------------------------------------
_ODRL_TEXT = {
    # (regeltyp, handling) -> {språk: text}
    ("permission", "use"): {"sv": "får användas", "en": "may be used"},
    ("permission", "distribute"): {"sv": "får spridas vidare",
                                   "en": "may be passed on"},
    ("permission", "publish"): {"sv": "får publiceras",
                                "en": "may be published"},
    ("prohibition", "distribute"): {"sv": "får inte spridas vidare",
                                    "en": "may not be passed on"},
    ("prohibition", "publish"): {"sv": "får inte publiceras",
                                 "en": "may not be published"},
    ("duty", "attribute"): {"sv": "… om källan anges",
                            "en": "… if the source is credited"},
    ("obligation", "kovGodkannande"): {
        "sv": "KoV måste godkänna innan avtal blir klart",
        "en": "KoV must approve before an agreement is made"},
    ("obligation", "medgerGranskning"): {
        "sv": "mottagaren medger granskning av hur data används (deklaration, verkställs inte tekniskt)",
        "en": "the recipient allows audit of how the data is used (a declaration, not technically enforced)"},
}


def _lokal(term):
    """'odrl:use', 'https://…/ns/deltagare' -> 'use', 'deltagare'."""
    return str(term or "").replace("#", "/").rsplit("/", 1)[-1].split(":")[-1]


def _som_lista(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _kompakt_odrl(v):
    """Avtalets policy ur connectorns management-API har odrl:-prefix på nycklarna och actions som {"@id": ...}
    ({"odrl:action": {"@id": "odrl:use"}}); katalogens policy har det inte. Gör om till katalogens form."""
    if isinstance(v, list):
        return [_kompakt_odrl(x) for x in v]
    if isinstance(v, dict):
        if set(v) == {"@id"}:
            return v["@id"]
        return {(k[5:] if k.startswith("odrl:") else k): _kompakt_odrl(x) for k, x in v.items()}
    return v


_ODRL_OPERATOR = {"eq": "=", "neq": "≠", "gteq": "≥", "lteq": "≤", "gt": ">", "lt": "<", "isAnyOf": "∈", "isNoneOf": "∉", "isAllOf": "⊇"}
# Övriga operatorer (isA, hasPart, isPartOf) visas som de heter: den här kolumnen är formell text och ska vara engelsk i båda vyerna.


def odrl_klartext(policy, sprak="sv", extern=False):
    """Översätter en ODRL-policy ur DSP-katalogen till rader
    [[kod, klartext], …]. Koden är regeln som den står i policyn; texten
    säger vad den betyder. Okända termer visas som de är."""
    en = sprak == "en"
    rader = []

    def rad(typ, handling, extra=None):
        text = (_ODRL_TEXT.get((typ, handling)) or {}).get(sprak)
        rader.append(["%s: %s" % (typ, handling), text or handling])
        return rader[-1]

    for p in _som_lista(policy.get("permission")):
        h = _lokal(p.get("action"))
        villkor = _som_lista(p.get("constraint"))
        r = rad("permission", h)
        if h == "use" and not villkor:
            r[1] = "may be used …" if en else "får användas …"
        elif villkor:
            r[1] += " …"
        for c in villkor:
            vanster = _lokal(c.get("leftOperand"))
            hoger = c.get("rightOperand")
            oper = _lokal(c.get("operator"))
            kod = str(hoger)
            if extern:
                kod = re.sub(r"%3A\d+", "", kod)
            stad = vanster == "deltagare" and str(hoger).startswith("did:web:")
            if stad:
                text = ("… but only by the City of Gothenburg" if en
                        else "… men bara av Göteborgs Stad")
            elif vanster == "inForceDate":
                m = re.fullmatch(r"contractAgreement\+(\d+)([smhd])", str(hoger))
                if m and oper == "gteq" and int(m.group(1)) == 0:
                    text = ("… from the moment the agreement is made" if en
                            else "… från det att avtalet ingåtts")
                elif m and oper == "lteq":
                    namn = {"s": ("seconds", "sekunder"), "m": ("minutes", "minuter"),
                            "h": ("hours", "timmar"), "d": ("days", "dagar")}[m.group(2)]
                    text = ("… and for %s %s at most" % (m.group(1), namn[0]) if en
                            else "… och i högst %s %s" % (m.group(1), namn[1]))
                else:
                    text = "… %s %s %s" % (vanster, oper, hoger)
            else:
                text = "… %s %s %s" % (vanster, _lokal(c.get("operator")), hoger)
            # Operatorn visas som den är (≥ och ≤ för start och slut): ett tidsintervall i ODRL är två villkor på samma operand.
            rader.append(["constraint: %s %s %s" % (vanster, _ODRL_OPERATOR.get(oper, oper or "="), kod), text])
        for d in _som_lista(p.get("duty")):
            rad("duty", _lokal(d.get("action")))
    for p in _som_lista(policy.get("prohibition")):
        rad("prohibition", _lokal(p.get("action")))
    for p in _som_lista(policy.get("obligation")):
        rad("obligation", _lokal(p.get("action")))
    return rader


def odrl_villkor(sprak="sv", extern=False):
    """Villkoren för B och A live ur DSP-katalogen:
    {"B": {"regler": [...], "json": policy}, "A": {...}}. Samma anrop som
    knappen Hämta DSP-katalogen."""
    katalog = kallor.dsp_katalog()
    dataset = katalog.get("dataset") or katalog.get("dcat:dataset") or []
    if isinstance(dataset, dict):
        dataset = [dataset]
    ut = {}
    for nyckel, asset in (("B", kallor.ASSET_B), ("A", kallor.ASSET_A)):
        d = next((x for x in dataset if x.get("@id") == asset), None)
        if d is None:
            raise kallfel("kallfel.asset_saknas", asset=asset)
        pol = d.get("hasPolicy") or d.get("odrl:hasPolicy") or {}
        if isinstance(pol, list):
            pol = pol[0] if pol else {}
        visad = json.loads(re.sub(r"%3A\d+", "", json.dumps(pol))
                           if extern else json.dumps(pol))
        ut[nyckel] = {"regler": odrl_klartext(pol, sprak, extern),
                      "json": visad}
    return ut


# Steg 6 (användningen) har inga egna komponenter: det läser stadens plattform, så dess
# status är plattformens (steg 5).
_STATUS_FRAN = {6: 5}


def komponenter_for(nr):
    nr = _STATUS_FRAN.get(nr, nr)
    return [k for k in KOMPONENTER if k["steg"] == nr]


# Sätts av main.py i den externa varianten: besökaren ska inte se portnummer.
UTAN_PORTAR = False


def utan_portar(text):
    """Tar bort portnummer ur ett meddelande (host:1234, "porten 1234",
    port=1234, %3A1234). Bara i den externa varianten (UTAN_PORTAR)."""
    if text is None or not UTAN_PORTAR:
        return text
    return rensa.utan_portar(text)


def utan_intern_adress(text):
    """Som utan_portar, men tar också bort interna värdnamn ur adresser och
    urllib3-feltexter. För felmeddelanden och loggar som visas för en
    besökare i den externa varianten: 'når inte http://host.docker.internal:
    39193/management/…' blir 'når inte /management/…'."""
    if text is None or not UTAN_PORTAR:
        return text
    return rensa.utan_intern_adress(text)


def detaljer(nr, sprak="sv"):
    """Detaljraderna för ett steg, som lista av {etikett, varde}."""
    for s in STEG:
        if s["nr"] == nr:
            rader = _skyddad(s["detaljer"])
            rader = [oversatt_detalj(e, utan_portar(None if v is None else str(v)),
                                     sprak) for e, v in rader]
            return [{"etikett": e, "varde": v} for e, v in rader]
    return []


# ---------------------------------------------------------------------------
# EXEMPELOBJEKT per steg
#
# Visar hur objektet som passerar steget FAKTISKT ser ut – men BARA det
# kontrollrummet redan lagligt hämtar (samma kallor.py-funktioner som
# hälsopollningen och detaljvyn). Ingen ny åtkomst: särskilt läser
# inspektören ALDRIG dataproduktens nyttolast. Vid steg 1 är den luckan själv
# poängen och redovisas öppet.
#
# Rubrik och anmärkning finns på svenska och engelska; objektet är data och
# översätts inte. Funktionerna tar språk och använder _s(sv, en, sprak).
# ---------------------------------------------------------------------------
def _s(sv, en, sprak):
    return en if sprak == "en" else sv


def _ex(rubrik, obj, sprak_typ="json", anmarkning=None):
    if sprak_typ == "json":
        innehall = json.dumps(obj, indent=2, ensure_ascii=False)
    else:
        innehall = obj if isinstance(obj, str) else str(obj)
    ut = {"rubrik": rubrik, "sprak": sprak_typ, "innehall": innehall}
    if anmarkning:
        ut["not"] = anmarkning
    return ut


def _e1(sp="sv"):
    h = kallor.fcf_health()
    obj = {k: h.get(k) for k in ("weirs", "batchesTotal", "batches", "latestBatchId",
                                 "measurementWindow", "faultInjectionActive")}
    return _ex(_s("Vad kontrollrummet ser av FCF (batch-metadata)",
                  "What the control room sees of FCF (batch metadata)", sp), obj,
               anmarkning=_s(
                   "Kontrollrummet läser medvetet inte nyttolasten i "
                   "distribution B och A: kontraktsledet lämnar ut "
                   "dataprodukten, inte kontrollrummet.",
                   "The control room deliberately does not read the payload "
                   "of distributions B and A: the contract layer releases "
                   "the data product, not the control room.", sp))


def _e2(sp="sv"):
    kat = kallor.dsp_katalog()
    dataset = kat.get("dataset") or kat.get("dcat:dataset") or []
    if isinstance(dataset, dict):
        dataset = [dataset]
    offerter = {}
    for d in dataset:
        pol = d.get("hasPolicy") or d.get("odrl:hasPolicy") or {}
        if isinstance(pol, list):
            pol = pol[0] if pol else {}
        offerter[d.get("@id")] = {k: pol.get(k) for k in
                                  ("permission", "prohibition", "obligation")}
        # Produktdeklarationen: vad produkten är och hur bra den är, innan avtalet.
        dekl = {k.rsplit("/", 1)[-1]: v for k, v in d.items()
                if k in ("dct:conformsTo", "dct:accrualPeriodicity")
                or k.startswith("https://svada.goteborg.se/ns/")}
        if dekl:
            offerter[d.get("@id")]["deklaration"] = dekl
    return _ex(_s("ODRL-offerter och produktdeklaration i DSP-katalogen (per distribution)",
                  "ODRL offers and product declaration in the DSP catalogue (per distribution)", sp),
               offerter,
               anmarkning=_s(
                   "A: use med villkoren deltagare=staden och giltighet i 30 dagar, "
                   "förbud mot distribute/publish, skyldigheterna kovGodkannande och "
                   "medgerGranskning. B: "
                   "use/distribute/publish utan förbud.",
                   "A: use with the constraints participant=the city and a 30-day "
                   "validity, prohibitions on distribute/publish, obligations "
                   "kovGodkannande and medgerGranskning. B: use/distribute/publish without "
                   "prohibitions.", sp))


def _e3(sp="sv", foredra=None):
    """Ett finaliserat kontraktsavtal. Om `foredra` (ett contractAgreementId)
    ges väljs det avtalet – så att "Följ ett värde" visar SAMMA avtal som
    ursprungsmärkningen i steg 5. Utan det visas det nyaste."""
    forh = [f for f in kallor.forhandlingar(limit=20) if _egen_forhandling(f)]
    fin = [f for f in forh
           if f.get("state") == "FINALIZED" and f.get("contractAgreementId")]
    ex = None
    if foredra:
        ex = next((f for f in fin if f.get("contractAgreementId") == foredra), None)
    if ex is None:
        ex = fin[0] if fin else (forh[0] if forh else {})
    obj = {k: ex.get(k) for k in ("state", "contractAgreementId",
                                  "counterPartyId")}
    sammma = foredra and ex.get("contractAgreementId") == foredra
    return _ex(_s("Ett finaliserat kontraktsavtal", "A finalised contract "
                  "agreement", sp)
               + (_s(" (samma som ursprungsmärkningens)",
                     " (the same as in the provenance)", sp) if sammma
                  else _s(" (nyast först)", " (newest first)", sp)), obj,
               anmarkning=_s(
                   "contractAgreementId är nyckeln som följer med in i "
                   "stadens ursprungsmärkning (steg 5).",
                   "contractAgreementId is the key that follows into the "
                   "city's provenance (step 5).", sp))


def _e4(sp="sv", trad_id=None):
    lev = kallor.ingest_leveranser()
    poster = lev.get("deliveries") or [{}]                  # loggen är äldst först
    # Kvittot som hör till TRÅDENS avtal (samma contractAgreementId som steg 3 och 5), inte bara den senaste leveransen:
    # efter en A-leverans visade steg 4 annars A:s avtal mellan B:s i steg 3 och 5 (gränssnittstestet 2026-10-18, M7).
    egna = [d for d in poster if trad_id and d.get("contractAgreementId") == trad_id]
    if sessioner.aktuell() is not None:                     # med en session: bara besökarens egna kvitton, aldrig någon annans
        poster = [d for d in poster if _eget_avtal(d.get("contractAgreementId"))] or [{}]
    obj = {"counters": lev.get("counters"),
           "senaste": (egna or poster)[-1]}
    return _ex(_s("Mottagningens kvittologg",
                  "The intake's receipt log", sp), obj,
               anmarkning=_s(
                   "En avvisad leverans bär orsak, t.ex. "
                   "brunns-gis-i-distribution-b (felinjektionen).",
                   "A rejected delivery carries a reason, e.g. "
                   "brunns-gis-i-distribution-b (well-gis-in-distribution-b, the fault injection).", sp))


def _e5(sp="sv"):
    ent = kallor.orion_stad_brunn()
    prov = dict((ent.get("provenance") or {}).get("value") or {})
    if prov.get("license"):
        prov["license"] = re.sub(r"\s*\(M\d\)", "", prov["license"])
    if prov.get("contractAgreementId") and not _eget_avtal(prov["contractAgreementId"]):
        prov["contractAgreementId"] = prov["contractAgreementUrl"] = None     # någon annans avtal: varken id eller länk
    obj = {"id": ent.get("id"),
           "overflowVolumeM3": ent.get("overflowVolumeM3"),
           "provenance": prov}
    return _ex(_s("Bräddbrunnen i stadens dataplattform – modellerat värde "
                  "MED ursprungsmärkning",
                  "The overflow chamber in the city's data platform – "
                  "modelled value WITH provenance", sp), obj,
               anmarkning=_s(
                   "Ursprungsmärkningen svarar på varifrån, under vilket "
                   "avtal och i vilken klass värdet kom. "
                   "contractAgreementId knyter det till steg 3–4.",
                   "The provenance answers where the value came from, under "
                   "which agreement and in which class. contractAgreementId "
                   "ties it to steps 3–4.", sp))


def _e6(sp="sv"):
    import analys
    return _ex(_s("En rad ur inspektionsprioriteringen – med ursprung",
                  "A row from the inspection priority – with origin", sp),
               json.loads(analys.exempelrad()),
               anmarkning=_s(
                   "Raden bär sitt ursprung: avtal, batch, distribution och "
                   "klass, så att beslutet går att härleda till data och "
                   "avtalet det kom genom.",
                   "The row carries its origin: agreement, batch, "
                   "distribution and class, so the decision can be traced to "
                   "the data and the agreement it came through.", sp))


EXEMPEL = {1: _e1, 2: _e2, 3: _e3, 4: _e4, 5: _e5, 6: _e6}


def exempel(nr, sprak="sv"):
    """Exempelobjektet för ett steg. Kastar aldrig – ett dött led visar sitt fel."""
    fn = EXEMPEL.get(nr)
    if not fn:
        return {"rubrik": _s("Inget exempel för steg %s", "No example for "
                             "step %s", sprak) % nr, "sprak": "text",
                "innehall": "–"}
    try:
        ut = fn(sprak)
    except KallFel as fel:
        return {"rubrik": _s("Kunde inte hämta exemplet", "Could not fetch "
                             "the example", sprak), "sprak": "text",
                "innehall": utan_portar(meddelanden.visa(fel.kod, fel.p, sprak) if fel.kod
                                        else (i18n.oversatt(str(fel)) if sprak == "en" else str(fel)))}
    except Exception as fel:                                 # noqa: BLE001
        return {"rubrik": _s("Fel vid exempelhämtning", "Error fetching the "
                             "example", sprak), "sprak": "text",
                "innehall": utan_portar("%s: %s" % (type(fel).__name__, fel))}
    ut["innehall"] = utan_portar(ut["innehall"])
    return ut


# ---------------------------------------------------------------------------
# FÖLJ ETT VÄRDE genom kedjan
#
# Samma bräddbrunn led för led, med de faktiska objekten – och tråden som
# knyter ihop dem: contractAgreementId ur ursprungsmärkningen återkommer i
# avtalet (steg 3) och leveranskvittot (steg 4). Modelleringssteget markeras
# som en medveten LUCKA: kontrollrummet visar metadata, inte nyttolasten.
# ---------------------------------------------------------------------------
# Statuskodens klartext (sv, en) i rutan "Så följer villkoren med data" (F10).
_STATUS_KLARTEXT = {"GALLANDE": ("gällande", "valid"), "HAVT": ("hävt", "revoked"),
                    "UTGANGET": ("utgånget", "expired"), "OKAND": ("okänt", "unknown")}


def ursprung_b(extern=False, sprak="sv"):
    """Steg 5, rutan Så följer villkoren med data: värdet i stadens
    dataplattform OCH avtalet som dess contractAgreementId pekar på, slaget
    upp i stadens connector. Bara om senaste leveransen är distribution B –
    ett värde ur distribution A visas aldrig. Annars kastas KallFel och
    vyn behåller de statiska, samstämmiga exemplen."""
    ent = kallor.orion_stad_brunn()
    prov = dict((ent.get("provenance") or {}).get("value") or {})
    if prov.get("distribution") != "B" or not prov.get("contractAgreementId"):
        raise kallfel("kallfel.inte_dist_b")
    sess = sessioner.aktuell()
    if sess is not None and prov["contractAgreementId"] not in sess.avtal:
        raise kallfel("kallfel.inte_dist_b")       # värdet kom ur någon annans leverans: visa inte någon annans avtal (sessioner.py)
    if prov.get("license"):
        prov["license"] = re.sub(r"\s*\(M\d\)", "", prov["license"])
    varde = {"id": ent.get("id"), "type": ent.get("type"),
             "overflowVolumeM3": ent.get("overflowVolumeM3"),
             "provenance": prov}
    ag = kallor.avtal(prov["contractAgreementId"])
    if ag.get("assetId") != kallor.ASSET_B:
        raise kallfel("kallfel.avtal_inte_b")
    # Webinariet 2026-10 (punkt 4): avtalet visas bredvid värdet med id, distribution, status och villkoren i
    # klartext överst; de formella fälten och ODRL-policyn under.
    avtal = {"@id": ag.get("@id"), "distribution": "B", "status": None, "statusIKlartext": None}
    pol = ag.get("policy") or {}
    avtal["villkorIKlartext"] = ["%s: %s" % (kod, text) for kod, text in odrl_klartext(_kompakt_odrl(pol), sprak, extern)]
    avtal.update({k: ag.get(k) for k in ("assetId", "providerId", "consumerId", "contractSigningDate")})
    # F10 (fientliga testet 2026-10-19): originalfälten står kvar som de är, men signeringstiden (Unix-sekunder) och statuskoden
    # (utan å, ä, ö) får en läsbar följeslagare på vyns språk.
    try:
        avtal["signeratUtc"] = datetime.datetime.fromtimestamp(float(ag.get("contractSigningDate")), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    # Avtalets status och löstbara adress kommer från stadens avtalsregister
    # (synkas från DHI). Ett avtal gäller tills det hävs.
    try:
        reg = [r for r in kallor.avtalsregister().get("avtal", [])
               if r.get("id") == prov["contractAgreementId"]]
        if reg:
            avtal["status"] = reg[0].get("status")
            avtal["statusIKlartext"] = _STATUS_KLARTEXT.get(reg[0].get("status"), (reg[0].get("status") or "?",) * 2)[1 if sprak == "en" else 0]
            avtal["adress"] = reg[0].get("url")
    except KallFel:
        pass
    if avtal["status"] is None:
        del avtal["status"]
    if avtal["statusIKlartext"] is None:
        del avtal["statusIKlartext"]
    avtal["policy"] = {k: pol.get(k) or pol.get("odrl:" + k)
                       for k in ("permission", "prohibition", "obligation")
                       if pol.get(k) or pol.get("odrl:" + k)}
    ut = json.dumps(avtal, indent=2, ensure_ascii=False)
    vt = json.dumps(varde, indent=2, ensure_ascii=False)
    if extern:
        ut = re.sub(r"%3A\d+", "", ut)
        vt = re.sub(r"%3A\d+", "", vt)
    return {"varde": vt,
            "avtal": ("GET …/contractagreements/%s\n%s" if extern else "GET /management/v3/contractagreements/%s\n%s")
                     % (prov["contractAgreementId"], ut)}


_SVENSKA_ORD = re.compile(r"[åäöÅÄÖ]|\b(kunde|inte|saknas|och|från|når|finns|fel)\b")


def _engelsk_feltext(text):
    """Fri (svensk) feltext på engelska: reservöversättaren först; är texten fortfarande svensk blir den ett generiskt
    engelskt besked i stället för att en svensk mening hamnar i den engelska vyn (del e, E5)."""
    t = i18n.oversatt(text)
    return "the source did not answer as expected" if _SVENSKA_ORD.search(t) else t


def _tomt(v):
    """True om ett exempelobjekt saknar innehåll: None, tomma objekt/listor, eller bara sådana nästlade (L15)."""
    if v is None or v == {} or v == []:
        return True
    if isinstance(v, dict):
        return all(_tomt(x) for x in v.values())
    return False


def folj_vardet(sprak="sv"):
    hopp = []

    def _lagg(nr, titel, byggare, markering=None):
        try:
            ex = byggare(sprak)
        except Exception as fel:                             # noqa: BLE001
            # Fri feltext (utan kod) är svensk: på engelska går den via översättaren, som i exempel() (del e, E5).
            orsak = (meddelanden.visa(fel.kod, fel.p, sprak) if getattr(fel, "kod", None)
                     else (_engelsk_feltext(str(fel)) if sprak == "en" else str(fel)))
            ex = {"rubrik": titel, "sprak": "text", "fel": True,
                  "innehall": _s("kunde inte hämtas: %s", "could not be fetched: %s", sprak) % utan_portar(orsak)}
        innehall = ex.get("innehall")
        try:                                                 # L15: ett objekt med bara null-värden betyder "inget ännu"
            tolkat = json.loads(innehall) if ex.get("sprak") == "json" else None
        except (TypeError, ValueError):
            tolkat = None
        if isinstance(tolkat, dict) and _tomt(tolkat):
            ex = dict(ex, sprak="text")
            innehall = _s("Inget ännu: kör kedjan fram till det här steget.", "Nothing yet: run the chain up to this step.", sprak)
        post = {"steg": nr, "titel": titel, "rubrik": ex.get("rubrik"),
                "sprak": ex.get("sprak"),
                "innehall": utan_portar(innehall)}
        if ex.get("fel"):
            post["fel"] = True                               # felled märks strukturellt: testerna väljer på detta, inte på text
        if ex.get("not"):
            post["not"] = ex["not"]
        if markering:
            post["markering"] = markering
        hopp.append(post)

    trad_id = None
    try:
        prov = (kallor.orion_stad_brunn().get("provenance") or {}).get("value") or {}
        trad_id = _eget_avtal(prov.get("contractAgreementId"))
    except Exception:                                        # noqa: BLE001
        pass

    _lagg(1, _s("Modellering (dataprodukten)", "Modelling (the data product)",
                sprak), _e1,
          markering={"typ": "lucka",
                     "text": _s("Kontrollrummet visar inte nyttolasten – "
                                "kontraktsledet lämnar ut den.",
                                "The control room does not show the payload "
                                "– the contract layer releases it.", sprak)})
    _lagg(2, _s("ODRL-offert (DSP-katalog)", "ODRL offer (DSP catalogue)",
                sprak), _e2)
    _lagg(3, _s("Kontraktsavtal", "Contract agreement", sprak),
          lambda sp: _e3(sp, trad_id),
          markering={"typ": "trad",
                     "text": _s("Detta avtals-id följer med hela vägen in i "
                                "stadens dataplattform.",
                                "This agreement id follows all the way into "
                                "the city's data platform.", sprak)})
    _lagg(4, _s("Leveranskvitto", "Delivery receipt", sprak), lambda sp: _e4(sp, trad_id))
    _lagg(5, _s("Värde i stadens dataplattform MED ursprungsmärkning",
                "Value in the city's data platform WITH provenance", sprak),
          _e5,
          markering={"typ": "trad",
                     "text": _s("Samma contractAgreementId som i steg 3–4.",
                                "The same contractAgreementId as in steps "
                                "3–4.", sprak)})
    _lagg(6, _s("Användning: rad ur inspektionsprioriteringen",
                "Use: a row from the inspection priority", sprak), _e6,
          markering={"typ": "trad",
                     "text": _s("Raden bär samma avtal och batch: beslutet "
                                "går att härleda till data.",
                                "The row carries the same agreement and "
                                "batch: the decision can be traced to the "
                                "data.", sprak)})

    return {"brunn": kallor.BRUNN_ID, "tradId": trad_id, "hopp": hopp,
            "invarianter": [
                _s("Integritet: distribution B bär aldrig brunnarnas "
                   "position (fältet location saknas i B).",
                   "Integrity: distribution B never carries the chambers' "
                   "positions (the location field is absent from B).",
                   sprak),
                _s("Suveränitet: A lämnar aldrig DHI utan KoV:s godkännande, "
                   "och går inte att läsa ur stadens plattform utan ett "
                   "gällande avtal.",
                   "Sovereignty: A never leaves DHI without KoV's approval, "
                   "and cannot be read from the city's platform without a "
                   "current agreement.", sprak),
                _s("Ett avtal gäller tills det hävs eller löper ut: efter en hävning "
                   "eller utgång nekas nya överföringar och nycklarna slutar fungera.",
                   "An agreement is valid until it is revoked or expires: after a "
                   "revocation or expiry new transfers are refused and keys "
                   "stop working.", sprak)]}
