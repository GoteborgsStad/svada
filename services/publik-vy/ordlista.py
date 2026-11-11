"""ordlista.py – ordlistan (begreppen och deras förklaringar) och den lilla motor som
understryker begreppen på sidor utan egen motor: brunnsvyn, /modell, /mim, /nyheter
och /ordlista.

Kontrollrummets egen motor (services/dashboard/vy.py) använder bara ORDLISTA härifrån.
Filen finns i två identiska kopior (services/dashboard och services/publik-vy);
tests/mim_enhet.py kontrollerar att de är lika.
"""

import html
import json
import os

# Ordlistan: id, regex (JavaScript-syntax) och förklaring per språk. cs=True
# betyder skiftlägeskänslig matchning. Driver både tipsrutorna och fliken Ordlista.
ORDLISTA = [
    {"id": "poc",
     "sv": {"term": "PoC (proof of concept)", "re": "PoC(?::e?n)?(?!\\p{L})", "cs": True,
            "def": "Ett bevis på att något fungerar i praktiken: här en körbar demo i liten skala av hela kedjan, med riktiga komponenter men utan att vara en driftsatt tjänst."},
     "en": {"term": "PoC (proof of concept)", "re": "PoC", "cs": True,
            "def": "A proof that something works in practice: here a small-scale, runnable demo of the whole chain, with real components but not a deployed service."}},
    {"id": "braddbrunn",
     "sv": {"term": "Bräddbrunn",
            "re": "bräddbrunn\\p{L}*",
            "def": (
                    "En brunn i avloppsnätet där vattnet kan rinna över till "
                    "ett utsläpp när ledningen är full. Här sitter givaren som "
                    "mäter.")},
     "en": {"term": "Overflow chamber",
            "re": "overflow chambers?",
            "def": (
                    "A chamber in the sewer network where water can spill over "
                    "to an outlet when the pipe is full. This is where the "
                    "measuring sensor sits.")},
    },
    {"id": "bradd",
     "sv": {"term": "Bräddning, brädda",
            "re": "brädd(?:ning\\p{L}*|ar|ade|a(?!\\p{L})|händelse\\p{L}*|flöde\\p{L}*|data)",
            "def": (
                    "När avloppsledningen är full, till exempel vid kraftigt "
                    "regn, rinner en del av avloppsvattnet över och ut i ett "
                    "vattendrag i stället för till reningsverket. Det kallas "
                    "att det bräddar. Bräddning ska hållas så liten som "
                    "möjligt.")},
     "en": {"term": "Overflow",
            "re": "overflows?(?! chamber)(?! data)|overflowing",
            "def": (
                    "When the sewer pipe is full, for example in heavy rain, "
                    "some of the sewage spills over into a watercourse instead "
                    "of going to the treatment plant. Overflow should be kept "
                    "as small as possible.")},
    },
    {"id": "spillflode",
     "sv": {"term": "Spillflöde",
            "re": "spillflöde\\p{L}*",
            "def": (
                    "Den del av flödet som bräddar ut, mätt i kubikmeter per "
                    "sekund (m³/s).")},
     "en": {"term": "Spill flow",
            "re": "spill flow",
            "def": (
                    "The part of the flow that overflows, measured in cubic "
                    "metres per second (m³/s).")},
    },
    {"id": "totalflode",
     "sv": {"term": "Totalflöde",
            "re": "totalflöde\\p{L}*",
            "def": "Allt vatten som rinner genom brunnen, mätt i m³/s."},
     "en": {"term": "Total flow",
            "re": "total flow",
            "def": "All water flowing through the chamber, measured in m³/s."},
    },
    {"id": "eudataspace",
     "lank": "https://digital-strategy.ec.europa.eu/en/policies/data-spaces",
     "sv": {"term": "Gemensamma europeiska dataspaces",
            "re": "europeiska dataspace\\p{L}*|Common European Data Spaces",
            "def": (
                    "EU:s satsning, enligt datastrategin från 2020, på "
                    "dataspaces inom bland annat hälsa, energi, mobilitet, "
                    "jordbruk och miljö. Bygger på gemensamma regler och "
                    "byggstenar så att dataspaces kan kopplas ihop.")},
     "en": {"term": "Common European data spaces",
            "re": "common European data spaces|European ones",
            "def": (
                    "The EU initiative, under the 2020 data strategy, for data "
                    "spaces in areas such as health, energy, mobility, "
                    "agriculture and the environment. Built on shared rules and"
                    " building blocks so data spaces can be connected.")},
    },
    {"id": "dsp",
     "lank": "https://eclipse-dataspace-protocol-base.github.io/DataspaceProtocol/",   # specifikationen (L21)
     "sv": {"term": "Dataspace Protocol (DSP)",
            "re": "Dataspace Protocol|DSP(?!\\p{L})",
            "cs": True,
            "def": (
                    "Standardprotokollet som connectorer använder för att visa "
                    "katalog, förhandla avtal och styra överföringar.")},
     "en": {"term": "Dataspace Protocol (DSP)",
            "re": "Dataspace Protocol|DSP(?!\\p{L})",
            "cs": True,
            "def": (
                    "The standard protocol connectors use to show catalogues, "
                    "negotiate agreements and control transfers.")},
    },
    {"id": "dataspace",
     "lank": "https://dssc.eu/",
     "sv": {"term": "Dataspace",
            "re": "dataspace\\p{L}*",
            "def": (
                    "Ett sätt för organisationer att dela data utan gemensam "
                    "databas. Data ligger kvar hos den som har det och lämnas "
                    "ut först när ett maskinellt avtal säger ja. Villkoren "
                    "följer med och kontrolleras automatiskt.")},
     "en": {"term": "Data space",
            "re": "data spaces?",
            "def": (
                    "A way for organisations to share data without a shared "
                    "database. Data stays with whoever holds it and is released"
                    " only when a machine-readable agreement says yes. The "
                    "terms travel with it and are checked automatically.")},
    },
    {"id": "connector",
     "sv": {"term": "Connector",
            "re": "connector\\p{L}*",
            "def": (
                    "Programvaran varje part kör för att delta i dataspacet. "
                    "Den visar katalog, förhandlar avtal och styr överföringar."
                    " Här används Eclipse EDC.")},
     "en": {"term": "Connector",
            "re": "connectors?",
            "def": (
                    "The software each party runs to take part in the data "
                    "space. It shows the catalogue, negotiates agreements and "
                    "controls transfers. Eclipse EDC is used here.")},
    },
    {"id": "edc",
     "lank": "https://projects.eclipse.org/projects/technology.edc",
     "sv": {"term": "Eclipse EDC",
            "re": "Eclipse EDC|EDC(?!\\p{L})",
            "cs": True,
            "def": (
                    "Connector med öppen källkod från Eclipse Foundation, en "
                    "vanlig grund för dataspaces i EU.")},
     "en": {"term": "Eclipse EDC",
            "re": "Eclipse EDC|EDC(?!\\p{L})",
            "cs": True,
            "def": (
                    "Open-source connector from the Eclipse Foundation, a "
                    "common basis for data spaces in the EU.")},
    },
    {"id": "odrl",
     "lank": "https://www.w3.org/TR/odrl-model/",
     "sv": {"term": "ODRL",
            "re": "ODRL",
            "cs": True,
            "def": (
                    "W3C-standard för maskinläsbara användningsvillkor: vad som"
                    " är tillåtet, vad som är förbjudet och vilka skyldigheter "
                    "som gäller.")},
     "en": {"term": "ODRL",
            "re": "ODRL",
            "cs": True,
            "def": (
                    "W3C standard for machine-readable usage terms: what is "
                    "permitted, what is prohibited and which duties apply.")},
    },
    {"id": "intyg",
     "lank": "https://www.w3.org/TR/vc-data-model-2.0/",
     "sv": {"term": "Verifierbart intyg",
            "re": "verifierbar\\p{L}* intyg\\p{L}*|intyg\\p{L}*|rollintyg\\p{L}*|VC(?![\\p{L}\\p{N}])",
            "def": (
                    "Digitalt intyg med kryptografisk signatur (W3C Verifiable "
                    "Credential, VC) som bevisar vem en part är eller vilken "
                    "roll den har. En grundteknik i dataspaces: intygen visas "
                    "och kontrolleras i varje led, enligt protokollet DCP.")},
     "en": {"term": "Verifiable credential",
            "re": "verifiable credentials?|credentials?|VCs?(?![\\p{L}\\p{N}])",
            "def": (
                    "A digital certificate with a cryptographic signature (W3C "
                    "Verifiable Credential, VC) that proves who a party is or "
                    "which role it holds. A basic technique in data spaces: the "
                    "credentials are shown and checked at every step, under the "
                    "protocol DCP.")},
    },
    {"id": "dssc",
     "lank": "https://dssc.eu/",
     "sv": {"term": "DSSC",
            "re": "DSSC",
            "cs": True,
            "def": (
                    "Data Spaces Support Centre, EU:s stödcentrum för "
                    "dataspaces. Förvaltar referensramen (Blueprint) med "
                    "byggblock som PoC:en jämförs mot.")},
     "en": {"term": "DSSC",
            "re": "DSSC",
            "cs": True,
            "def": (
                    "Data Spaces Support Centre, the EU support centre for data"
                    " spaces. It maintains the reference framework (Blueprint) "
                    "whose building blocks the PoC is compared against.")},
    },
    {"id": "ngsild",
     "lank": "https://en.wikipedia.org/wiki/NGSI-LD",
     "sv": {"term": "NGSI-LD",
            "re": "NGSI-LD",
            "cs": True,
            "def": (
                    "Standard för att beskriva saker och deras tillstånd över "
                    "tid, till exempel en brunn och dess flöde.")},
     "en": {"term": "NGSI-LD",
            "re": "NGSI-LD",
            "cs": True,
            "def": (
                    "A standard for describing things and their state over "
                    "time, such as a chamber and its flow.")},
    },
    {"id": "kontextbroker",
     "lank": "https://github.com/FIWARE/context.Orion-LD",
     "sv": {"term": "Kontextbroker",
            "re": "kontextbroker\\p{L}*",
            "def": (
                    "Databas som håller det senaste tillståndet för saker, här "
                    "brunnar, och svarar på NGSI-LD. Här används Orion-LD.")},
     "en": {"term": "Context broker",
            "re": "context brokers?",
            "def": (
                    "A database holding the latest state of things, here "
                    "chambers, answering in NGSI-LD. Orion-LD is used here.")},
    },
    {"id": "fiware",
     "lank": "https://www.fiware.org/",
     "sv": {"term": "FIWARE",
            "re": "FIWARE",
            "cs": True,
            "def": (
                    "Öppen plattform med komponenter för smarta städer, bland "
                    "annat Orion-LD och Mintaka.")},
     "en": {"term": "FIWARE",
            "re": "FIWARE",
            "cs": True,
            "def": (
                    "Open platform with components for smart cities, including "
                    "Orion-LD and Mintaka.")},
    },
    {"id": "dataprodukt",
     "sv": {"term": "Dataprodukt",
            "re": "dataprodukt\\p{L}*",
            "def": (
                    "Data som paketerats tillsammans med beskrivning, klassning"
                    " och användningsvillkor, så att det kan delas som en "
                    "enhet.")},
     "en": {"term": "Data product",
            "re": "data products?",
            "def": (
                    "Data packaged together with a description, classification "
                    "and usage terms, so it can be shared as one unit.")},
    },
    {"id": "klass",
     "sv": {"term": "Informationsklass (K1R1T1, K0R1T1)",
            "re": "K[01]R1T1|informationsklass\\p{L}*|klassning\\p{L}*",
            "def": (
                    "Stadens klassning av information efter konfidentialitet "
                    "(K), riktighet (R) och tillgänglighet (T). K1 betyder "
                    "känslig, K0 betyder öppen.")},
     "en": {"term": "Information class (K1R1T1, K0R1T1)",
            "re": "K[01]R1T1|information class\\p{L}*|classification",
            "def": (
                    "The city's classification of information by "
                    "confidentiality (K), integrity (R) and availability (T). "
                    "K1 means sensitive, K0 means open.")},
    },
    {"id": "kov",
     "sv": {"term": "KoV",
            "re": "KoV(?!-gate)",
            "cs": True,
            "def": (
                    "Kretslopp och Vatten, Göteborgs Stads förvaltning för "
                    "vatten och avlopp. Informationsägare: sätter villkoren, som "
                    "binder den som hämtar data.")},
     "en": {"term": "KoV",
            "re": "KoV(?! gate)",
            "cs": True,
            "def": (
                    "Kretslopp och Vatten, the City of Gothenburg's water and "
                    "sewage administration. The information owner: sets the terms, "
                    "which bind whoever fetches the data.")},
    },
    {"id": "intraservice",
     "sv": {"term": "Intraservice",
            "re": "Intraservice",
            "cs": True,
            "def": (
                    "Göteborgs Stads förvaltning för digitala tjänster. Driver "
                    "stadens connector och dataplattform och tar emot data på "
                    "KoV:s uppdrag, bunden av KoV:s villkor.")},
     "en": {"term": "Intraservice",
            "re": "Intraservice",
            "cs": True,
            "def": (
                    "The City of Gothenburg's digital services administration. "
                    "Runs the city's connector and data platform and receives "
                    "data on KoV's behalf, bound by KoV's terms.")},
    },
    {"id": "dhi",
     "lank": "https://www.dhigroup.com/",
     "sv": {"term": "DHI",
            "re": "DHI(?!:)",
            "cs": True,
            "def": (
                    "Konsultföretag inom vatten som håller data och tar fram dem"
                    " åt staden med modellen Future City Flow.")},
     "en": {"term": "DHI",
            "re": "DHI(?!')",
            "cs": True,
            "def": (
                    "Water engineering consultancy that holds the data and "
                    "produces it for the city with the Future City Flow "
                    "model.")},
    },
    {"id": "fcf",
     "lank": "https://www.dhigroup.com/se/teknologier/future-city-flow",
     "sv": {"term": "Future City Flow",
            "re": "Future City Flow",
            "cs": True,
            "def": (
                    "DHI:s modell för flöden och bräddning i avloppsnätet. I "
                    "PoC:en ersatt av en simulerad, enkel beräkning.")},
     "en": {"term": "Future City Flow",
            "re": "Future City Flow",
            "cs": True,
            "def": (
                    "DHI's model for flows and overflow in the sewer network. "
                    "Replaced in the PoC by a simple simulated calculation.")},
    },
    {"id": "batch",
     "sv": {"term": "Batch",
            "re": "batch\\p{L}*",
            "def": (
                    "En omgång beräknade data, här ett modellerat dygn för alla"
                    " brunnar. Datumet sist i batch-id:t (till exempel"
                    " batch-015-2026-06-29) är det modellerade dygnet, inte"
                    " när batchen kördes.")},
     "en": {"term": "Batch",
            "re": "batch(?:es)?",
            "def": (
                    "One round of computed data, here a modelled day for all "
                    "chambers. The date at the end of the batch id (for example "
                    "batch-015-2026-06-29) is the modelled day, not when the "
                    "batch was run.")},
    },
    {"id": "modellerat-dygn",
     "sv": {"term": "Modellerat dygn",
            "re": "modellerade? dygn\\p{L}*",
            "def": (
                    "Det dygn en batch avser. Demon visar inte mätningar i"
                    " realtid: modellen räknar fram ett nytt dygn för varje"
                    " batch (här en var tionde minut), och datumet står i"
                    " batch-id:t. Det är alltså inte dagens datum och inte"
                    " tiden då batchen kördes.")},
     "en": {"term": "Modelled day",
            "re": "modelled days?",
            "def": (
                    "The day a batch covers. The demo does not show"
                    " measurements in real time: the model computes a new day"
                    " for each batch (here one every ten minutes), and the date"
                    " is in the batch id. It is neither today's date nor the"
                    " time the batch was run.")},
    },
    {"id": "dsga",
     "sv": {"term": "DSGA",
            "re": "DSGA(?: 0\\.1)?",
            "cs": True,
            "def": "Data Space Governance Authority: den part som styr ett dataspace, med regler, medlemmar och intyg. I demon spelas den av Svadas utfärdare (version 0.1)."},
     "en": {"term": "DSGA",
            "re": "DSGA(?: 0\\.1)?",
            "cs": True,
            "def": "Data Space Governance Authority: the party that governs a data space, with rules, members and credentials. In the demo it is played by the Svada issuer (version 0.1)."}},
    {"id": "cip",
     "sv": {"term": "CIP",
            "re": "CIP(?!-)",
            "cs": True,
            "def": (
                    "Stadens dataplattform (City Information Platform) där data"
                    " lagras och delas vidare.")},
     "en": {"term": "CIP",
            "re": "CIP(?!-)",
            "cs": True,
            "def": (
                    "The city's data platform (City Information Platform), "
                    "where data is stored and shared onwards.")},
    },
    {"id": "proveniens",
     "lank": "https://www.w3.org/TR/prov-overview/",
     "sv": {"term": "Ursprungsmärkning (proveniens)",
            "re": "ursprungsmärkning\\p{L}*|proveniens\\p{L}*",
            "def": (
                    "Uppgifter som följer med varje värde om varifrån det "
                    "kommer: avtal, batch, distribution och klass.")},
     "en": {"term": "Provenance",
            "re": "provenance",
            "def": (
                    "Information attached to every value about where it came "
                    "from: agreement, batch, distribution and class.")},
    },
    {"id": "dcat",
     "lank": "https://docs.dataportal.se/dcat/sv/",
     "sv": {"term": "DCAT-AP-SE",
            "re": "DCAT-AP(?:-SE)?",
            "cs": True,
            "def": (
                    "Den svenska nationella profilen av DCAT-AP, EU:s "
                    "gemensamma standard för att beskriva datamängder i "
                    "kataloger, till exempel för Sveriges och EU:s portaler. "
                    "Används inte i demon: DHI:s katalog bygger på DCAT i "
                    "den form Dataspace Protocol beskriver.")},
     "en": {"term": "DCAT-AP-SE",
            "re": "DCAT-AP(?:-SE)?",
            "cs": True,
            "def": (
                    "The Swedish national profile of DCAT-AP, the EU's common "
                    "standard for describing datasets in catalogues, for example "
                    "for Swedish and EU portals. Not used in the demo: "
                    "DHI's catalogue is built on DCAT in the form the "
                    "Dataspace Protocol describes.")},
    },
    {"id": "dcatbegrepp",
     "lank": "https://www.w3.org/TR/vocab-dcat-3/",
     "sv": {"term": "DCAT",
            "re": "DCAT(?![-\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Data Catalog Vocabulary, W3C:s standard för att beskriva "
                    "datamängder och kataloger så att de kan läsas av maskiner. "
                    "I demon beskrivs dataprodukten i DCAT i den form "
                    "Dataspace Protocol använder i DHI:s katalog. Profilerna "
                    "DCAT-AP och DCAT-AP-SE bygger på DCAT.")},
     "en": {"term": "DCAT",
            "re": "DCAT(?![-\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Data Catalog Vocabulary, the W3C standard for describing "
                    "datasets and catalogues so that machines can read them. "
                    "In the demo the data product is described in DCAT in the "
                    "form the Dataspace Protocol uses in DHI's catalogue. The "
                    "profiles DCAT-AP and DCAT-AP-SE build on DCAT.")},
    },
    {"id": "dcp",
     "lank": "https://eclipse-dataspace-dcp.github.io/decentralized-claims-protocol/",
     "sv": {"term": "Decentralized Claims Protocol (DCP)",
            "re": "DCP(?![\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "Protokollet för hur en part visar upp verifierbara intyg "
                    "för en annan part i ett dataspace, utan en central "
                    "tjänst. Demon använder det för att kontrollera medlemskap, "
                    "deltagare och roller.")},
     "en": {"term": "Decentralized Claims Protocol (DCP)",
            "re": "DCP(?![\\p{L}\\p{N}])",
            "cs": True,
            "def": (
                    "The protocol for how one party presents verifiable "
                    "credentials to another in a data space, without a central "
                    "service. The demo uses it to check membership, participants "
                    "and roles.")},
    },
    {"id": "mim",
     "lank": "https://mims.oascities.org/",
     "sv": {"term": "MIM (Minimal Interoperability Mechanism)", "re": "MIM(?:\\d)?(?::\\p{L}+)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Ett minimikrav för interoperabilitet från organisationen OASC. Det finns flera, numrerade MIM0, MIM1 och så vidare, och vart och ett gäller ett område (åtkomst, länkning, representation, utbyte, säkerhet, geodata). Vi bedömer oss själva mot dem; det är ingen certifiering. En PoC-begränsning betyder att ett krav hålls tillbaka just för att det här är en PoC."},
     "en": {"term": "MIM (Minimal Interoperability Mechanism)", "re": "MIMs?(?:\\d)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A minimal requirement for interoperability from the organisation OASC. There are several, numbered MIM0, MIM1 and so on, each covering one area (access, linking, representation, exchange, security, geodata). We assess ourselves against them; it is not a certification. A PoC limitation means a requirement is held back precisely because this is a PoC."}},
    {"id": "mimkrav",
     "sv": {"term": "Kravkoder (RC3.2, R1.2b)", "re": "(?:RC|R)\\d\\.\\d[a-z]?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Numret på ett enskilt krav i en MIM. RC står för ett krav under en förmåga (capability), R för ett krav i en MIM utan den nivån. Bokstaven efter numret (R1.2b) skiljer delkrav åt."},
     "en": {"term": "Requirement codes (RC3.2, R1.2b)", "re": "(?:RC|R)\\d\\.\\d[a-z]?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The number of one requirement in a MIM. RC is a requirement under a capability, R a requirement in a MIM without that level. The letter after the number (R1.2b) tells sub-requirements apart."}},
    {"id": "jsonld",
     "lank": "https://www.w3.org/TR/json-ld10/",
     "sv": {"term": "JSON-LD", "re": "JSON-LD(?![\\p{L}\\p{N}])", "cs": True,
            "def": "JSON med en kontext som kopplar varje fältnamn till en adress där betydelsen står. Det är så NGSI-LD gör att samma data går att tolka lika överallt."},
     "en": {"term": "JSON-LD", "re": "JSON-LD(?![\\p{L}\\p{N}])", "cs": True,
            "def": "JSON with a context that links every field name to an address where its meaning is given. This is how NGSI-LD makes the same data readable the same way everywhere."}},
    {"id": "schemakontroll",
     "sv": {"term": "Schemakontroll (JSON Schema)", "re": "(?:[Ss]chemakontroll\\p{L}*|JSON Schema)", "cs": False,
            "def": "Kontrollen att en leverans har rätt fält, typer och enheter enligt modellens schema (en maskinläsbar beskrivning i JSON Schema) innan staden lagrar den. Resultatet visas i steg 4."},
     "en": {"term": "Schema check (JSON Schema)", "re": "(?:[Ss]chema check\\p{L}*|JSON Schema)", "cs": False,
            "def": "The check that a delivery has the right fields, types and units according to the model's schema (a machine-readable description in JSON Schema) before the City stores it. The result is shown in step 4."}},
    {"id": "leveransjson",
     "sv": {"term": "Leverans-JSON", "re": "[Ll]everans-JSON", "cs": False,
            "def": "Själva leveransen från leverantören: värdena inpackade tillsammans med uppgifter om vem som levererar, på vilka villkor och vilken modell de följer."},
     "en": {"term": "Delivery JSON", "re": "[Dd]elivery JSON", "cs": False,
            "def": "The delivery itself from the provider: the values wrapped together with who delivers, on what terms and which model they follow."}},
    {"id": "openapi",
     "lank": "https://www.openapis.org/",
     "sv": {"term": "OpenAPI", "re": "OpenAPI(?![\\p{L}\\p{N}])", "cs": True,
            "def": "En standard för att beskriva ett webbgränssnitt (API) så att både människor och program kan läsa vilka anrop som finns och vad de svarar."},
     "en": {"term": "OpenAPI", "re": "OpenAPI(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A standard for describing a web interface (API) so that both people and programs can read which calls exist and what they answer."}},
    {"id": "sssom",
     "lank": "https://mapping-commons.github.io/sssom/",
     "sv": {"term": "SSSOM", "re": "SSSOM(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Ett filformat för att lista hur termer i en modell hänger ihop med termer i andra modeller (lika, nära, besläktade)."},
     "en": {"term": "SSSOM", "re": "SSSOM(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A file format for listing how the terms in one model relate to terms in other models (equal, close, related)."}},
    {"id": "geojson",
     "lank": "https://geojson.org/",
     "sv": {"term": "GeoJSON", "re": "GeoJSON(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Ett JSON-format för geografiska former. Brunnarnas positioner är GeoJSON-punkter."},
     "en": {"term": "GeoJSON", "re": "GeoJSON(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A JSON format for geographic shapes. The chambers' positions are GeoJSON points."}},
    {"id": "ogc",
     "sv": {"term": "OGC-tjänster (WFS, OGC API)", "re": "(?:OGC API|OGC|WFS)(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Standardiserade webbtjänster för geodata från organisationen OGC. Med dem kan andra system hämta kartdata. Vi erbjuder inga; vi visar bara punkterna på en karta."},
     "en": {"term": "OGC services (WFS, OGC API)", "re": "(?:OGC API|OGC|WFS)(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Standardised web services for geodata from the organisation OGC. With them other systems can fetch map data. We offer none; we only show the points on a map."}},
    {"id": "gateway",
     "sv": {"term": "Gateway (stadens ingång)", "re": "[Gg]ateway(?![\\p{L}\\p{N}])", "cs": False,
            "def": "Stadens ingång för Distribution A. Den släpper bara igenom den som har ett giltigt avtal och en nyckel, och förklarar varför om svaret blir nej."},
     "en": {"term": "Gateway (the City's entrance)", "re": "[Gg]ateway(?![\\p{L}\\p{N}])", "cs": False,
            "def": "The City's entrance for Distribution A. It lets through only a party with a valid agreement and a key, and explains why if the answer is no."}},
    {"id": "tidsserie",
     "sv": {"term": "Tidsserie", "re": "[Tt]idsserie\\p{L}*", "cs": False,
            "def": "Värden för samma sak över tid, till exempel utsläppsvolymen från en brunn dygn för dygn. Stadens tidsserie-gränssnitt går att fråga på tid och attribut."},
     "en": {"term": "Time series", "re": "[Tt]ime series", "cs": False,
            "def": "Values for the same thing over time, for example the overflow volume from a chamber day by day. The City's time series interface can be queried on time and attributes."}},
    {"id": "sdm",
     "lank": "https://smartdatamodels.org/",
     "sv": {"term": "Smart Data Models", "re": "Smart Data Models", "cs": True,
            "def": "En öppen samling färdiga datamodeller för bland annat städer och miljö. Vår modell länkar till dem men är inte inskickad dit."},
     "en": {"term": "Smart Data Models", "re": "Smart Data Models", "cs": True,
            "def": "An open collection of ready-made data models for cities, the environment and more. Our model links to them but has not been submitted there."}},
    {"id": "inspire",
     "lank": "https://knowledge-base.inspire.ec.europa.eu/",
     "sv": {"term": "INSPIRE", "re": "INSPIRE(?![\\p{L}\\p{N}])", "cs": True,
            "def": "EU:s ramverk för geografisk information, med bland annat ordlistor för avloppsnät. Vi länkar några av våra termer till INSPIRE."},
     "en": {"term": "INSPIRE", "re": "INSPIRE(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The EU framework for geographic information, with code lists for sewer networks among other things. We link some of our terms to INSPIRE."}},
    {"id": "dublincore",
     "lank": "https://www.dublincore.org/",
     "sv": {"term": "Dublin Core", "re": "Dublin Core", "cs": True,
            "def": "En vanlig uppsättning termer för att beskriva resurser, till exempel beskrivning, källa och licens. Flera av våra termer är lånade därifrån."},
     "en": {"term": "Dublin Core", "re": "Dublin Core", "cs": True,
            "def": "A common set of terms for describing resources, for example description, source and licence. Several of our terms are borrowed from it."}},
    {"id": "conformsto",
     "sv": {"term": "conformsTo", "re": "conformsTo(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Fältet i katalogens beskrivning som säger vilken specifikation eller modell dataprodukten följer. Hos oss pekar det på datamodellen."},
     "en": {"term": "conformsTo", "re": "conformsTo(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The field in the catalogue's description that says which specification or model the data product follows. With us it points to the data model."}},
    {"id": "refweir",
     "sv": {"term": "refWeir", "re": "refWeir(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Relationen som pekar från en leverans till brunnen den gäller. Id:t är brunnens id."},
     "en": {"term": "refWeir", "re": "refWeir(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The relationship that points from a delivery to the chamber it concerns. The id is the chamber's id."}},
    {"id": "entitet",
     "sv": {"term": "Entitet", "re": "[Ee]ntitet\\p{L}*", "cs": False,
            "def": "En sak som har ett eget id i NGSI-LD, till exempel en brunn eller en leverans, med attribut och relationer."},
     "en": {"term": "Entity", "re": "[Ee]ntit(?:y|ies)", "cs": False,
            "def": "A thing with an id of its own in NGSI-LD, for example a chamber or a delivery, with attributes and relationships."}},
    {"id": "eidas",
     "lank": "https://digital-strategy.ec.europa.eu/en/policies/eidas-regulation",
     "sv": {"term": "eIDAS", "re": "eIDAS(?![\\p{L}\\p{N}])", "cs": True,
            "def": "EU:s regelverk för elektronisk identifiering och betrodda tjänster. Svadas utfärdare är inte förankrad i eIDAS; det är en medveten förenkling."},
     "en": {"term": "eIDAS", "re": "eIDAS(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The EU rules for electronic identification and trust services. Svada's issuer is not anchored in eIDAS; that is a deliberate simplification."}},
    {"id": "aterkallelse",
     "sv": {"term": "Återkallelse (av intyg)", "re": "[Åå]terkall\\p{L}*", "cs": False,
            "def": "Att ett intyg förklaras ogiltigt så att innehavaren inte längre får använda det. Det är något annat än hävning, som gäller ett avtal. Samordnaren återkallar intyg."},
     "en": {"term": "Revocation (of a credential)", "re": "[Rr]evocation of (?:a |the )?credentials?\\p{L}*|[Rr]evoke[sd]? (?:a |the )?credential\\p{L}*", "cs": False,
            "def": "Declaring a credential invalid so that its holder can no longer use it. Not the same as termination, which concerns an agreement. The coordinator revokes credentials."}},
    {"id": "deltagarregister",
     "sv": {"term": "Deltagarregister", "re": "[Dd]eltagarregist\\p{L}*", "cs": False,
            "def": "Förteckningen över de parter som är med i dataspacet, med namn och adressen där deras connector svarar. Staden slår upp leverantören här. I PoC:en ligger den i minnet hos utfärdaren."},
     "en": {"term": "Participant directory", "re": "[Pp]articipant (?:directory|register)", "cs": False,
            "def": "The list of parties that take part in the data space, with their names and the address where their connector answers. The City looks the provider up here. In the PoC it is held in the issuer's memory."}},
    {"id": "samordnare",
     "sv": {"term": "Samordnare", "re": "[Ss]amordnar\\p{L}*", "cs": False,
            "def": "Rollen som driver dataspacets gemensamma delar: utfärdar medlems- och deltagarintyg och kan stänga ute en part. I PoC:en spelas den av Svada."},
     "en": {"term": "Coordinator", "re": "[Cc]oordinator\\p{L}*", "cs": False,
            "def": "The role that runs the data space's shared parts: it issues membership and participant credentials and can exclude a party. In the PoC it is played by Svada."}},
    {"id": "identityhub",
     "sv": {"term": "IdentityHub", "re": "IdentityHub\\p{L}*", "cs": True,
            "def": "Parternas egen identitetstjänst: håller partens DID, nycklar och verifierbara intyg och bevisar vem parten är mot de andra. Varje part har en."},
     "en": {"term": "IdentityHub", "re": "IdentityHub\\p{L}*", "cs": True,
            "def": "A party's own identity service: it holds the party's DID, keys and verifiable credentials and proves who the party is to the others. Each party has one."}},
    {"id": "havning",
     "sv": {"term": "Hävning (av avtal)", "re": "[Hh]ävning\\p{L}*", "cs": False,
            "def": "Att ett avtal tas bort så att det inte längre ger åtkomst. Ett avtal gäller tills det hävs eller löper ut, och hävningen sker hos leverantören."},
     "en": {"term": "Termination (of an agreement)", "re": "[Tt]ermination\\p{L}*|[Tt]erminat(?:e|ed)|[Rr]evoke[sd]? the agreement|[Rr]evocation(?! of (?:a |the )?credential)\\p{L}*", "cs": False,
            "def": "An agreement being ended so that it no longer gives access. An agreement holds until it is ended or expires, and the ending happens at the provider."}},
    {"id": "ccby",
     "lank": "https://creativecommons.org/licenses/by/4.0/",
     "sv": {"term": "CC BY 4.0", "re": "CC BY(?: 4\\.0)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Öppen licens: vem som helst får använda datan om hen anger källan. Distribution B har den."},
     "en": {"term": "CC BY 4.0", "re": "CC BY(?: 4\\.0)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "An open licence: anyone may use the data if they credit the source. Distribution B has it."}},
    {"id": "provo",
     "lank": "https://www.w3.org/TR/prov-o/",
     "sv": {"term": "PROV-O", "re": "PROV-O(?![\\p{L}\\p{N}])", "cs": True,
            "def": "W3C:s standardordförråd för att beskriva var data kommer ifrån: vem eller vad som gjorde den, när och av vad. Modellens proveniensfält hämtar sina begrepp därifrån."},
     "en": {"term": "PROV-O", "re": "PROV-O(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The W3C standard vocabulary for describing where data comes from: who or what made it, when and from what. The model's provenance fields take their terms from it."}},
    {"id": "uncefact",
     "sv": {"term": "UN/CEFACT", "re": "UN/CEFACT", "cs": True,
            "def": "FN:s organ för handelsunderlättande. Det har fastställt koder för måttenheter, till exempel MTQ för kubikmeter, MQS för kubikmeter per sekund, MTR för meter och MIN för minut, som modellen använder."},
     "en": {"term": "UN/CEFACT", "re": "UN/CEFACT", "cs": True,
            "def": "The UN body for trade facilitation. It has fixed codes for units of measure, such as MTQ for cubic metre, MQS for cubic metre per second, MTR for metre and MIN for minute, which the model uses."}},
    {"id": "jsonschema",
     "lank": "https://json-schema.org/",
     "sv": {"term": "JSON Schema", "re": "JSON Schema", "cs": True,
            "def": "Ett sätt att i en fil beskriva hur en JSON-leverans ska se ut: vilka fält som får finnas, vilka som måste finnas och vilken sorts värden de har. Schemakontrollen använder det."},
     "en": {"term": "JSON Schema", "re": "JSON Schema", "cs": True,
            "def": "A way to describe in a file what a JSON delivery must look like: which fields may exist, which are required and what kind of values they hold. The schema check uses it."}},
    {"id": "epsg",
     "sv": {"term": "EPSG", "re": "EPSG(?::\\d+)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Ett nummer som anger vilket koordinatsystem positionerna är angivna i, till exempel EPSG:4326 för vanlig latitud och longitud."},
     "en": {"term": "EPSG", "re": "EPSG(?::\\d+)?(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A number that says which coordinate system the positions are given in, for example EPSG:4326 for ordinary latitude and longitude."}},
    {"id": "iso8601",
     "sv": {"term": "ISO 8601", "re": "ISO 8601", "cs": True,
            "def": "Den internationella standarden för att skriva datum och klockslag, till exempel 2026-10-30T12:00:00Z."},
     "en": {"term": "ISO 8601", "re": "ISO 8601", "cs": True,
            "def": "The international standard for writing dates and times, for example 2026-10-30T12:00:00Z."}},
    {"id": "urn",
     "sv": {"term": "URN", "re": "URN(?![\\p{L}\\p{N}])|urn:[\\w:.-]+", "cs": True,
            "def": "Ett namn som aldrig ändras och som inte är en webbadress, till exempel urn:svada:dataprodukt:modellerad-bradddata:1.0.0. Används som id för saker som inte behöver gå att öppna."},
     "en": {"term": "URN", "re": "URN(?![\\p{L}\\p{N}])|urn:[\\w:.-]+", "cs": True,
            "def": "A name that never changes and is not a web address, for example urn:svada:dataprodukt:modellerad-bradddata:1.0.0. Used as an id for things that do not need to be opened."}},
    {"id": "did",
     "sv": {"term": "DID (decentraliserat id)", "re": "did:web[\\w:.-]*|DID(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Ett id som en organisation själv råder över och som andra kan slå upp för att få dess nycklar. Här identifierar det DHI, staden och Svada i utbytet av intyg."},
     "en": {"term": "DID (decentralised identifier)", "re": "did:web[\\w:.-]*|DID(?![\\p{L}\\p{N}])", "cs": True,
            "def": "An id that an organisation controls itself and that others can look up to get its keys. Here it identifies DHI, the city and Svada in the exchange of credentials."}},
    {"id": "etsi",
     "sv": {"term": "ETSI", "re": "ETSI(?![\\p{L}\\p{N}])", "cs": True,
            "def": "Europeisk standardiseringsorganisation för telekom och IT. Den har fastställt NGSI-LD, gränssnittet som kontextbrokern använder."},
     "en": {"term": "ETSI", "re": "ETSI(?![\\p{L}\\p{N}])", "cs": True,
            "def": "The European standards organisation for telecom and IT. It has fixed NGSI-LD, the interface the context broker uses."}},
    {"id": "sha256",
     "sv": {"term": "Kontrollsumma (SHA-256)", "re": "SHA-256|kontrollsumm\\p{L}*", "cs": False,
            "def": "Ett långt tal som räknas ut ur filens innehåll. Ändras en enda byte blir summan en helt annan, så två filer med samma summa är identiska. Den som laddat ned en fil kan räkna ut summan själv och jämföra."},
     "en": {"term": "Checksum (SHA-256)", "re": "SHA-256|checksum\\p{L}*", "cs": False,
            "def": "A long number computed from the contents of a file. Change a single byte and the sum becomes completely different, so two files with the same sum are identical. Anyone who has downloaded a file can compute the sum and compare."}},
    {"id": "csv",
     "sv": {"term": "CSV", "re": "CSV(?![\\p{L}\\p{N}])", "cs": True,
            "def": "En enkel tabellfil där värdena står på rader och skiljs åt med kommatecken. Går att öppna i Excel och andra kalkylprogram."},
     "en": {"term": "CSV", "re": "CSV(?![\\p{L}\\p{N}])", "cs": True,
            "def": "A simple table file where the values are on rows separated by commas. It opens in Excel and other spreadsheet programs."}},
]


_SORT_SV = str.maketrans({"å": "z{", "ä": "z|", "ö": "z}"})

_TEXT = {
    "sv": {"hela": "Hela ordlistan →", "titel": "Ordlista", "rub": "Ordlista",
           "intro": "Begreppen på sidorna, i alfabetisk ordning. Understrukna ord i texten visar sin förklaring när du pekar på dem eller går dit med Tab.",
           "tillbaka": "← Tillbaka", "lasmer": "Läs mer", "ny": "öppnas i ny flik, extern sida", "andra": ("English", "en")},
    "en": {"hela": "Full glossary →", "titel": "Glossary", "rub": "Glossary",
           "intro": "The terms on the pages, in alphabetical order. Underlined words in the text show their explanation when you hover over them or reach them with Tab.",
           "tillbaka": "← Back", "lasmer": "Read more", "ny": "opens in a new tab, external site", "andra": ("Svenska", "sv")},
}


def js_ord(sprak):
    """Listan som motorn får: id, term, regex (JavaScript), skiftlägeskänslighet, förklaring."""
    return [{"id": o["id"], "term": o[sprak]["term"], "re": o[sprak]["re"],
             "cs": bool(o[sprak].get("cs")), "def": o[sprak]["def"]} for o in ORDLISTA]


def _json_i_skript(data):
    # Inuti <script> får "<" aldrig stå som den är (</script>, <!--).
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


CSS = """
.term { text-decoration: underline dotted; text-decoration-thickness: 1.5px; text-underline-offset: 3px; cursor: help; border-radius: 2px; }
.term:hover, .term:focus-visible { background: #3b6ea826; }
.term:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
#tips { position: absolute; z-index: 50; max-width: min(24rem, calc(100vw - 24px)); background: CanvasText; color: Canvas; border-radius: 8px; padding: .55rem .7rem; font: .85rem/1.45 system-ui, sans-serif; box-shadow: 0 6px 18px rgb(0 0 0 / .25); display: grid; gap: .25rem; }
#tips[hidden] { display: none; }
#tips a { color: inherit; font-weight: 600; font-size: .8rem; text-decoration: underline; }
"""

# Motorn: understryker första förekomsten av varje begrepp per block och visar en tipsruta
# vid hover, fokus och tryck. Esc stänger bara rutan. Samma regler som kontrollrummets motor
# (hoppar över knappar, kod, rubriker, tabeller och länkar).
SKRIPT = r"""
(function () {
  const ORD = __ORD__, TX = __TX__, LANK = __LANK__, BLOCK = __BLOCK__;
  const ORDRE = ORD.map(o => ({id: o.id,
    re: new RegExp('(?<![\p{L}\p{N}])(?:' + o.re + ')', 'u' + (o.cs ? '' : 'i'))}));
  const hoppa = el => el.closest('button, pre, code, h1, h2, h3, h4, dt, .term, svg, table, a, summary, script, style, footer, nav, dialog, .aterstallrad, .topp, .sprakrad, #tips');
  function markera(rot) {
    const anvanda = new Set();
    const gang = document.createTreeWalker(rot, NodeFilter.SHOW_TEXT, {
      acceptNode: n => (!n.nodeValue.trim() || hoppa(n.parentElement))
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
    const noder = [];
    while (gang.nextNode()) noder.push(gang.currentNode);
    noder.forEach(nod => {
      const delar = []; let rest = nod.nodeValue, hittat = false;
      for (;;) {
        let basta = null;
        ORDRE.forEach(r => {
          if (anvanda.has(r.id)) return;
          const m = r.re.exec(rest);
          if (m && (basta === null || m.index < basta.index)) basta = {index: m.index, len: m[0].length, id: r.id};
        });
        if (!basta) break;
        hittat = true; anvanda.add(basta.id);
        delar.push(document.createTextNode(rest.slice(0, basta.index)));
        const t = document.createElement('span');
        t.className = 'term'; t.tabIndex = 0; t.dataset.term = basta.id;
        t.setAttribute('role', 'button'); t.setAttribute('aria-describedby', 'tips');
        t.textContent = rest.substr(basta.index, basta.len);
        delar.push(t);
        rest = rest.slice(basta.index + basta.len);
      }
      if (!hittat) return;
      delar.push(document.createTextNode(rest));
      const f = document.createDocumentFragment();
      delar.forEach(d => f.appendChild(d));
      nod.parentNode.replaceChild(f, nod);
    });
  }
  document.querySelectorAll(BLOCK).forEach(markera);

  const tips = document.createElement('div');
  tips.id = 'tips'; tips.setAttribute('role', 'tooltip'); tips.hidden = true;
  document.body.appendChild(tips);
  let timer = null, fran = null;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  function visa(el) {
    clearTimeout(timer);
    const o = ORD.find(x => x.id === el.dataset.term);
    if (!o) return;
    tips.innerHTML = '<b>' + esc(o.term) + '</b><span>' + esc(o.def) + '</span>'
      + '<a href="' + esc(LANK.replace('{id}', o.id)) + '">' + esc(TX.hela) + '</a>';
    tips.hidden = false; fran = el;
    const r = el.getBoundingClientRect();
    const sx = window.scrollX, sy = window.scrollY;
    tips.style.left = Math.max(sx + 8, Math.min(sx + r.left, sx + document.documentElement.clientWidth - tips.offsetWidth - 8)) + 'px';
    tips.style.top = (sy + r.bottom + 6) + 'px';
  }
  function dolj(direkt) {
    clearTimeout(timer);
    const gor = () => { tips.hidden = true; fran = null; };
    if (direkt) gor(); else timer = setTimeout(gor, 150);
  }
  document.addEventListener('mouseover', e => {
    const t = e.target.closest && e.target.closest('.term');
    if (t) visa(t); else if (e.target.closest && e.target.closest('#tips')) clearTimeout(timer);
  });
  document.addEventListener('mouseout', e => { if (e.target.closest && e.target.closest('.term, #tips')) dolj(); });
  document.addEventListener('focusin', e => {
    const t = e.target.closest && e.target.closest('.term');
    if (t) visa(t); else if (!e.target.closest || !e.target.closest('#tips')) dolj(true);
  });
  document.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('.term');
    if (t) { visa(t); return; }
    if (!e.target.closest || !e.target.closest('#tips')) dolj(true);
  });
  document.addEventListener('keydown', e => {
    const t = e.target.closest && e.target.closest('.term');
    if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); visa(t); return; }
    if (e.key === 'Escape' && !tips.hidden) {
      e.stopPropagation();
      const f = fran; dolj(true);
      if (f) f.focus({preventScroll: true});
    }
  }, true);
})();
"""

# Block som får understrykta begrepp på sidor utan egen motor. "li:not(:has(p))" så att
# ett begrepp inte markeras två gånger när en listpunkt innehåller ett stycke.
BLOCK = "p, li:not(:has(p)), dd, .utkast:not(:has(p)), .underrubrik"


def tillagg(sprak, lank_mall):
    """<style> och <script> som läggs före </body>. lank_mall: adressen till ordlistan, med {id}."""
    sprak = sprak if sprak in _TEXT else "sv"
    skript = (SKRIPT.replace("__ORD__", _json_i_skript(js_ord(sprak)))
              .replace("__TX__", _json_i_skript({"hela": _TEXT[sprak]["hela"]}))
              .replace("__LANK__", _json_i_skript(lank_mall))
              .replace("__BLOCK__", _json_i_skript(BLOCK)))
    return "<style>" + CSS + "</style><script>" + skript + "</script>"


def med_ordlista(sida_html, sprak, lank_mall):
    """Lägger motorn sist i en färdig sida."""
    return sida_html.replace("</body>", tillagg(sprak, lank_mall) + "</body>", 1)


def sida(sprak="sv", lank_tillbaka="/"):
    """Fristående ordlistesida (brunnsvyn har ingen egen flik för den)."""
    sprak = sprak if sprak in _TEXT else "sv"
    t = _TEXT[sprak]
    e = html.escape
    nyckel = (lambda o: o[sprak]["term"].lower().translate(_SORT_SV)) if sprak == "sv" \
        else (lambda o: o[sprak]["term"].lower())
    rader = []
    for o in sorted(ORDLISTA, key=nyckel):
        lank = ""
        if o.get("lank"):
            lank = (' <a class="lasmer" href="%s" target="_blank" rel="noopener" aria-label="%s: %s (%s)">%s ↗</a>'
                    % (e(o["lank"]), e(t["lasmer"]), e(o[sprak]["term"]), e(t["ny"]), e(t["lasmer"])))
        rader.append('<div id="ordlista-%s"><dt>%s</dt><dd>%s%s</dd></div>'
                     % (e(o["id"]), e(o[sprak]["term"]), e(o[sprak]["def"]), lank))
    return f"""<!doctype html><html lang="{sprak}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t["titel"])}</title><style>
:root{{color-scheme:light dark}}
body{{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:1rem 16px 3rem}}
h1{{margin:.6rem 0 .2rem}} dt{{font-weight:650;margin-top:1rem}} dd{{margin:.1rem 0 0}}
.topp{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
div:target dt{{background:#3b6ea826}}
</style></head><body>
<div class="topp"><a href="{e(lank_tillbaka)}">{e(t["tillbaka"])}</a><a href="/ordlista?lang={t["andra"][1]}" hreflang="{t["andra"][1]}">{e(t["andra"][0])}</a></div>
<h1>{e(t["rub"])}</h1>
<p>{e(t["intro"])}</p>
<dl>{"".join(rader)}</dl>
<p style="font-size:.85rem;opacity:.8;margin-top:2rem">Version {e(os.environ.get("SVADA_VERSION", "okänd"))} · <a href="https://github.com/GoteborgsStad/svada" target="_blank" rel="noopener">{"Källkod på GitHub" if sprak == "sv" else "Source code on GitHub"} ↗</a></p>
</body></html>"""
