#!/usr/bin/env python3
"""KONCEPT: docs/koncept/07-transfer-ingest.md

Valideringen av en inkommande leverans (komponent 8).

Ingest litar ALDRIG på nyttolasten. Tre lager kontrolleras, i den ordning
de blir dyrare att köra:

  1. Kuvertet   – är det över huvud taget dataprodukten "Modellerad
                  bräddata", och vilken distribution påstår den sig vara?
  2. Avtalet    – matchar distributionen det avtal leveransen skickades
                  under? (En B-transfer får inte leverera A-innehåll.)
  3. Posterna   – bär varje post de fält som modellen/avtalet utlovar, och
                  – för Distribution B – saknas brunns-GIS verkligen?

Punkt 3 är den som fångar fcf-sims felinjektionslägen:

  schemadrift          -> obligatoriska fält har bytt namn        -> saknas
  saknade_parametrar   -> overflowDurationMin/unitCodes borta     -> saknas
  gis_i_b (AVTALSBROTT)-> location/sourceSrs tillbaka i B         -> GIS-fel

Felinjektionen är avsiktligt "tyst" (se distributioner.py): det finns
ingen flagga i nyttolasten som avslöjar den. Valideringen nedan måste alltså
upptäcka felen på egen hand – det är hela poängen med testfall 4c.5.
"""

# Fält som varje post MÅSTE bära. Listan speglar fcf-sims kuvert
# (services/fcf-sim/distributioner.py) och är det som i praktiken utgör
# schemat i dataproduktavtalet.
OBLIGATORISKA_FALT = (
    "weirId",
    "modelledDay",
    "periodStart",
    "periodEnd",
    "inflowMeanM3S",
    "inflowPeakM3S",
    "inflowVolumeM3",
    "overflowVolumeM3",
    "overflowPeakM3S",
    "overflowDurationMin",
    "waterLevelMaxM",
    "unitCodes",
    "modelVersion",
    "dataSource",
)

# Brunnens GIS – exakt de nycklar som skiljer Distribution A från B
# (KANSLIGA_FALT i fcf-sims distributioner.py). Får ALDRIG förekomma i B.
BRUNNS_GIS_FALT = ("location", "sourceSrs")

# Kuvertets egna fält.
OBLIGATORISKA_KUVERTFALT = ("dataset", "distribution", "distributionId",
                            "batchId", "modelledDay", "producedAt", "records")

DATASET = "Modellerad bräddata"

# Hur många postfel som redovisas i felsvaret (resten räknas bara).
MAX_EXEMPEL = 5


class Avvisad(Exception):
    """Leveransen avvisas. `orsak` är maskinläsbar, `detalj` för människor."""

    def __init__(self, status, orsak, detalj, exempel=None, kod=None, parametrar=None, exempel_p=None):
        super().__init__(detalj)
        self.status = status          # HTTP-status som ska returneras
        self.orsak = orsak            # kort kod, loggas och testas
        self.detalj = detalj
        self.exempel = exempel or []
        self.kod = kod                # språkoberoende meddelande (se kontrollrummets meddelandekatalog)
        self.parametrar = parametrar or {}
        self.exempel_p = exempel_p or []   # exemplen som [{"kod":…, "parametrar":…}]


def granska_kuvert(kropp):
    """Kontrollerar kuvertet och returnerar distributionsbokstaven (a/b)."""
    if not isinstance(kropp, dict):
        raise Avvisad(400, "ogiltig-json",
                      "nyttolasten är inte ett JSON-objekt", kod="ingest.ogiltig_json_objekt")

    saknade = [f for f in OBLIGATORISKA_KUVERTFALT if f not in kropp]
    if saknade:
        raise Avvisad(422, "kuvert-ofullstandigt",
                      "kuvertet saknar fält: %s" % ", ".join(saknade),
                      kod="ingest.kuvert_ofullstandigt", parametrar={"falt": saknade})

    if kropp["dataset"] != DATASET:
        raise Avvisad(422, "fel-dataprodukt",
                      "förväntade dataprodukten '%s', fick '%s'"
                      % (DATASET, kropp["dataset"]),
                      kod="ingest.fel_dataprodukt",
                      parametrar={"forvantad": DATASET, "fick": str(kropp["dataset"])})

    dist = str(kropp["distribution"]).strip().lower()
    if dist not in ("a", "b"):
        raise Avvisad(422, "okand-distribution",
                      "okänd distribution '%s'" % kropp["distribution"],
                      kod="ingest.okand_distribution", parametrar={"dist": str(kropp["distribution"])})

    if not isinstance(kropp["records"], list) or not kropp["records"]:
        raise Avvisad(422, "tom-leverans",
                      "leveransen innehåller inga poster", kod="ingest.tom_leverans")

    return dist


def granska_mot_avtal(dist, avtalad_dist):
    """Distributionen i kuvertet måste vara den avtalet gäller.

    Utan den här kontrollen hade ett B-avtal kunnat användas för att bära
    in A-innehåll i staden – hård regel 8 i praktiken.
    """
    if dist != avtalad_dist:
        raise Avvisad(409, "distribution-matchar-inte-avtalet",
                      "avtalet gäller Distribution %s men leveransen bär "
                      "Distribution %s" % (avtalad_dist.upper(), dist.upper()),
                      kod="ingest.distribution_matchar_inte",
                      parametrar={"avtalad": avtalad_dist.upper(), "levererad": dist.upper()})


def granska_poster(dist, poster):
    """Schemakontroll + (för B) kontroll att brunns-GIS verkligen saknas."""
    saknade_fel = []
    gis_fel = []

    for post in poster:
        if not isinstance(post, dict):
            raise Avvisad(422, "ogiltig-post", "en post är inte ett objekt", kod="ingest.ogiltig_post")
        brunn = post.get("weirId", "<utan weirId>")

        saknade = [f for f in OBLIGATORISKA_FALT if f not in post]
        if saknade:
            saknade_fel.append(("%s saknar %s" % (brunn, ", ".join(saknade)),
                                {"kod": "ingest.exempel_saknar", "parametrar": {"id": brunn, "falt": saknade}}))

        if dist == "b":
            gis = [f for f in BRUNNS_GIS_FALT if f in post]
            if gis:
                gis_fel.append(("%s bär %s" % (brunn, ", ".join(gis)),
                                {"kod": "ingest.exempel_gis", "parametrar": {"id": brunn, "falt": gis}}))

    # Avtalsbrottet redovisas FÖRST: att brunns-GIS läckt in i öppna data är
    # allvarligare än att ett mätetal bytt namn (röd tråd 2 i verifiering.md).
    if gis_fel:
        raise Avvisad(
            422, "brunns-gis-i-distribution-b",
            "AVTALSBROTT: Distribution B innehåller brunns-GIS (%s) i %d av "
            "%d poster – leveransen avvisas i sin helhet"
            % (", ".join(BRUNNS_GIS_FALT), len(gis_fel), len(poster)),
            [t for t, _ in gis_fel[:MAX_EXEMPEL]],
            kod="ingest.gis_i_b",
            parametrar={"falt": list(BRUNNS_GIS_FALT), "antal": len(gis_fel), "totalt": len(poster)},
            exempel_p=[m for _, m in gis_fel[:MAX_EXEMPEL]])

    if saknade_fel:
        raise Avvisad(
            422, "schema-avviker",
            "schemat avviker från dataproduktavtalet i %d av %d poster "
            "(omdöpta eller uteblivna fält)" % (len(saknade_fel), len(poster)),
            [t for t, _ in saknade_fel[:MAX_EXEMPEL]],
            kod="ingest.schema_avviker", parametrar={"antal": len(saknade_fel), "totalt": len(poster)},
            exempel_p=[m for _, m in saknade_fel[:MAX_EXEMPEL]])
