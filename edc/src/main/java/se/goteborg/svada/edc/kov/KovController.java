/*
 * SVADA PoC – KoV-godkännandets API.
 * KONCEPT: docs/koncept/06-kov-gate.md
 *
 * Registreras på PROVIDERNS management-kontext (ApiContext.MANAGEMENT) och
 * blir därmed nåbar på http://localhost:19193/management/kov/... enligt
 * portkartan. Consumerns 29193 har den INTE – KovGateExtension registrerar
 * bara controllern när svada.kov.gate.enabled=true, vilket enbart står i
 * edc/konfig/provider.properties. Det är verifieringens testfall 4b.4:
 * det finns ingen väg runt gaten på consumer-sidan.
 *
 * Endpoints (Data Rights Holder = Kretslopp och Vatten):
 *   GET  /management/kov/forhandlingar              – kön av A-förhandlingar
 *   POST /management/kov/forhandlingar/{id}/godkann – godkänn -> FINALIZED
 *   POST /management/kov/forhandlingar/{id}/avsla   – avslå   -> TERMINATED
 *   GET  /management/kov/avtal                      – avtalen med status GALLANDE/HAVT
 *   POST /management/kov/avtal/{id}/hav             – KoV häver ett avtal direkt
 *
 * Dashboardets "KoV-knapp" (komponent 14) anropar exakt de här
 * endpointsen – knappen representerar dataägarbeslutet verkställt i DHI:s
 * connector.
 *
 * NYCKELSKYDDADE MANAGEMENT-API:ER (docs/koncept/C1-identitet.md, bindande miniminivå): management-
 * API:t kräver en delad nyckel (web.http.management.auth.*), så anonym
 * åtkomst över huvud taget är stängd. Det skyddar TRANSPORTLAGRET – vem som
 * helst utan nyckeln avvisas redan av EDC innan ett anrop ens når den här
 * klassen.
 *
 * VERIFIERBAR IDENTITET, STEG 6 (docs/koncept/C1-identitet.md):
 * lägger till BEVISET för VEM, utöver den delade nyckeln. godkann()/avsla()
 * kräver nu dessutom en Authorization-header med ett self-issued DCP-token
 * som KovIdentitetsverifiering verifierar mot avsändarens IdentityHub – och
 * kontrollerar att avsändaren faktiskt innehar ett SvadaRoleCredential för
 * den konfigurerade Data Rights Holder-rollen (svada.kov.rollinnehavare).
 * Saknas eller är token ogiltigt/fel roll: 401 UNAUTHORIZED, ingen
 * statsövergång sker. Fram till verifieringssteget var beslutsfattarens "roll" bara en
 * konfigurationssträng som loggades men aldrig bevisades – se
 * KovIdentitetsverifiering.java för hela den kryptografiska mekanismen och
 * den identitetsgrund den bygger vidare på.
 */

package se.goteborg.svada.edc.kov;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.edc.connector.controlplane.contract.spi.negotiation.store.ContractNegotiationStore;
import org.eclipse.edc.connector.controlplane.contract.spi.types.agreement.ContractAgreement;
import org.eclipse.edc.connector.controlplane.contract.spi.types.negotiation.ContractNegotiation;
import org.eclipse.edc.spi.monitor.Monitor;
import org.eclipse.edc.spi.query.QuerySpec;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Path("/kov")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class KovController {

    private final ContractNegotiationStore store;
    private final KovGate gate;
    private final KovIdentitetsverifiering verifierare;
    private final Monitor monitor;
    /**
     * PoC-regeln "ett avslag häver tidigare avtal" (en medveten förenkling). I en delad demo med många besökare häver ett avslag från en besökare
     * annars andras avtal, så den kan stängas av (svada.kov.avslag.havartidigare=false). Standard: på.
     */
    private final boolean avslagHavarTidigare;

    public KovController(ContractNegotiationStore store, KovGate gate,
                          KovIdentitetsverifiering verifierare, Monitor monitor, boolean avslagHavarTidigare) {
        this.store = store;
        this.gate = gate;
        this.verifierare = verifierare;
        this.monitor = monitor;
        this.avslagHavarTidigare = avslagHavarTidigare;
    }

    /** Kön: alla provider-förhandlingar vars ODRL-policy kräver KoV-beslut. */
    @GET
    @Path("/forhandlingar")
    public List<Map<String, Object>> forhandlingar() {
        try (var stream = store.queryNegotiations(QuerySpec.max())) {
            return stream
                    .filter(n -> n.getType() == ContractNegotiation.Type.PROVIDER)
                    .filter(gate::kraverGodkannande)
                    .map(this::sammanfatta)
                    .toList();
        }
    }

    @POST
    @Path("/forhandlingar/{id}/godkann")
    public Response godkann(@PathParam("id") String id,
                             @HeaderParam("Authorization") String authorization) {
        return beslut(id, KovGate.Beslut.GODKAND, authorization);
    }

    @POST
    @Path("/forhandlingar/{id}/avsla")
    public Response avsla(@PathParam("id") String id,
                           @HeaderParam("Authorization") String authorization) {
        return beslut(id, KovGate.Beslut.AVSLAGEN, authorization);
    }

    // -----------------------------------------------------------------

    private Response beslut(String id, KovGate.Beslut b, String authorization) {
        // DCP-identitetens verifieringssteg: verifiera FÖRST, innan förhandlingen ens slås
        // upp – ett obevisat anrop ska inte kunna avslöja om ett id
        // existerar eller vilket tillstånd det är i.
        var verifiering = verifierare.verifiera(authorization);
        if (verifiering.failed()) {
            return felFranVerifiering(verifiering.getFailureDetail());
        }
        var verifieradRoll = verifiering.getContent();

        var befintlig = store.findById(id);
        if (befintlig == null) {
            return fel(Response.Status.NOT_FOUND, "Ingen förhandling med id " + id,
                    "kov.ingen_forhandling", Map.of("id", id));
        }
        if (befintlig.getType() != ContractNegotiation.Type.PROVIDER) {
            return fel(Response.Status.CONFLICT,
                    "Förhandling " + id + " är av typen " + befintlig.getType()
                            + " – KoV-beslut ges bara på provider-sidan (hård regel 7).",
                    "kov.fel_typ", Map.of("id", id, "typ", String.valueOf(befintlig.getType())));
        }
        if (!gate.kraverGodkannande(befintlig)) {
            return fel(Response.Status.CONFLICT,
                    "Förhandling " + id + " om " + gate.assetId(befintlig)
                            + " bär ingen svada:kovGodkannande-obligation – "
                            + "den kräver inget Data Rights Holder-beslut.",
                    "kov.ingen_obligation", Map.of("id", id, "asset", String.valueOf(gate.assetId(befintlig))));
        }

        // Ett beslut är slutgiltigt: ett upprepat anrop får inte ändra beslutet
        // eller (vid avslag) häva avtal som ingåtts efter det första beslutet.
        var tidigare = gate.beslut(id);
        if (tidigare != null) {
            return fel(Response.Status.CONFLICT,
                    "Förhandling " + id + " är redan avgjord (" + tidigare
                            + ") – ett KoV-beslut kan inte ändras eller upprepas.",
                    "kov.redan_avgjord", Map.of("id", id, "beslut", String.valueOf(tidigare)));
        }

        gate.registrera(id, b, verifieradRoll);

        // Släpp posten till statsmaskinen igen. GOTCHA: statsmaskinen leasar
        // poster medan den arbetar med dem, så vi måste ta lease:t själva.
        // In-memory-storens save() frigör lease:t igen.
        var leasad = store.findByIdAndLease(id);
        if (leasad.failed()) {
            return fel(Response.Status.CONFLICT,
                    "Förhandlingen bearbetas just nu av statsmaskinen, försök igen: "
                            + leasad.getFailureDetail(),
                    "kov.statsmaskin", Map.of("orsak", String.valueOf(leasad.getFailureDetail())));
        }
        var forhandling = leasad.getContent();
        forhandling.setPending(false);

        if (b == KovGate.Beslut.AVSLAGEN && forhandling.canBeTerminated()) {
            forhandling.transitionTerminating(
                    "KoV (Kretslopp och Vatten) avslog begäran om Distribution A "
                            + "(K1R1T1, non-public).");
        }
        store.save(forhandling);

        // Hävning: ett avslag häver tidigare avtal för samma tillgång och samma part
        // (PoC-regel, se KovGate.Havning). Görs efter att avslaget sparats.
        var havdaIds = new java.util.ArrayList<String>();
        if (b == KovGate.Beslut.AVSLAGEN && avslagHavarTidigare) {
            havdaIds.addAll(havTidigareAvtal(befintlig, verifieradRoll, id));
        } else if (b == KovGate.Beslut.AVSLAGEN) {
            monitor.info("KoV-GATE: avslaget häver inga tidigare avtal (regeln är avstängd: svada.kov.avslag.havartidigare=false).");
        }

        monitor.info("KoV-GATE: beslut " + b + " registrerat för " + id
                + ", förhandlingen släppt till statsmaskinen i tillstånd "
                + forhandling.stateAsString());

        var svar = sammanfatta(forhandling);
        svar.put("beslut", b.name());
        svar.put("havdaAvtal", havdaIds);
        // DCP-identitetens verifieringssteg: "beslutsfattare" är inte längre bara en
        // konfigurationssträng – det är det kryptografiskt VERIFIERADE
        // "role"-claimet ur avsändarens SvadaRoleCredential
        // (verifierare.verifiera(...) ovan). Sedan 2026-09-02 sätts det
        // via gate.registrera(...) ovan och kommer därmed med automatiskt
        // från sammanfatta() nedan – både i det här engångssvaret OCH i
        // GET /management/kov/forhandlingar, dvs. det överlever nu i den
        // beständiga loggen i stället för att bara synas i svaret på just
        // detta anrop.
        return Response.ok(svar).build();
    }

    /**
     * Avtalen som KoV-spärren gäller (alla avtal vars policy kräver KoV-beslut), med
     * status GALLANDE eller HAVT. Avtal gäller tills de hävs.
     */
    @GET
    @Path("/avtal")
    public List<Map<String, Object>> avtal() {
        try (var stream = store.queryAgreements(QuerySpec.max())) {
            return stream
                    .filter(a -> gate.kraverGodkannande(a.getPolicy()))
                    .map(this::sammanfattaAvtal)
                    .toList();
        }
    }

    /** KoV häver ett avtal direkt, utan någon ny förfrågan. Kräver KoV-rollintyget. */
    @POST
    @Path("/avtal/{id}/hav")
    public Response hav(@PathParam("id") String id,
                        @HeaderParam("Authorization") String authorization) {
        var verifiering = verifierare.verifiera(authorization);
        if (verifiering.failed()) {
            return felFranVerifiering(verifiering.getFailureDetail());
        }
        var avtal = store.findContractAgreement(id);
        if (avtal == null) {
            return fel(Response.Status.NOT_FOUND, "Inget avtal med id " + id,
                    "kov.inget_avtal", Map.of("id", id));
        }
        if (!gate.kraverGodkannande(avtal.getPolicy())) {
            return fel(Response.Status.CONFLICT, "Avtal " + id + " om " + avtal.getAssetId()
                    + " bär ingen svada:kovGodkannande-obligation – det är inte KoV:s att häva.",
                    "kov.avtal_ingen_obligation", Map.of("id", id, "asset", String.valueOf(avtal.getAssetId())));
        }
        var nyHavning = gate.hav(id, avtal.getAssetId(), avtal.getConsumerId(), "EXPLICIT",
                verifiering.getContent(), null);
        var svar = sammanfattaAvtal(avtal);
        svar.put("nyligenHavt", nyHavning);
        return Response.ok(svar).build();
    }

    /**
     * PoC-regeln: ett avslag av en ny begäran om distribution A häver tidigare, gällande avtal
     * för samma tillgång och samma part. Returnerar id:na som hävdes.
     */
    private List<String> havTidigareAvtal(ContractNegotiation avslagen, String roll, String forhandlingId) {
        var tillgang = gate.assetId(avslagen);
        var part = avslagen.getCounterPartyId();
        var havdaIds = new java.util.ArrayList<String>();
        if (tillgang == null || part == null) {
            return havdaIds;
        }
        try (var stream = store.queryAgreements(QuerySpec.max())) {
            stream.filter(a -> tillgang.equals(a.getAssetId()) && part.equals(a.getConsumerId()))
                    .filter(a -> !gate.arHavd(a.getId()))
                    .forEach(a -> {
                        if (gate.hav(a.getId(), tillgang, part, "AVSLAG", roll, forhandlingId)) {
                            havdaIds.add(a.getId());
                        }
                    });
        }
        if (havdaIds.isEmpty()) {
            monitor.info("KoV-GATE: avslaget häver inga tidigare avtal (inga gällande avtal om "
                    + tillgang + " för " + part + ").");
        }
        return havdaIds;
    }

    private Map<String, Object> sammanfattaAvtal(ContractAgreement a) {
        var m = new LinkedHashMap<String, Object>();
        m.put("id", a.getId());
        m.put("assetId", a.getAssetId());
        m.put("providerId", a.getProviderId());
        m.put("consumerId", a.getConsumerId());
        m.put("contractSigningDate", a.getContractSigningDate());
        var h = gate.havning(a.getId());
        m.put("status", h == null ? "GALLANDE" : "HAVT");
        if (h != null) {
            var hm = new LinkedHashMap<String, Object>();
            hm.put("tid", h.tid());
            hm.put("av", h.av());
            hm.put("orsak", h.orsak());
            hm.put("forhandlingId", h.forhandlingId());
            m.put("havning", hm);
        }
        return m;
    }

    private Map<String, Object> sammanfatta(ContractNegotiation n) {
        var m = new LinkedHashMap<String, Object>();
        m.put("id", n.getId());
        // Consumerns förhandlings-id (DSP consumerPid). Utan det går det inte
        // att para ihop providerns kö med den förhandling staden startade –
        // id:na är olika på de två sidorna.
        m.put("correlationId", n.getCorrelationId());
        m.put("assetId", gate.assetId(n));
        m.put("counterPartyId", n.getCounterPartyId());
        m.put("state", n.stateAsString());
        m.put("pending", n.isPending());
        m.put("kraverKovGodkannande", gate.kraverGodkannande(n));
        var b = gate.beslut(n.getId());
        m.put("kovBeslut", b == null ? "VANTANDE" : b.name());
        // Den verifierade rollen som fattade beslutet (null om VANTANDE).
        // Se KovGate.beslutsfattare(...) och dess fälts docstring.
        m.put("beslutsfattare", gate.beslutsfattare(n.getId()));
        m.put("contractAgreementId", n.getContractAgreement() == null
                ? null : n.getContractAgreement().getId());
        m.put("errorDetail", n.getErrorDetail());
        return m;
    }

    /** 401 från identitetsverifieringen: texten bär sin kod och sina parametrar (se KovIdentitetsverifiering.kodatFel). */
    private Response felFranVerifiering(String detalj) {
        var delar = KovIdentitetsverifiering.delaFel(detalj);
        var parametrar = new java.util.LinkedHashMap<String, String>();
        if (!delar[1].isEmpty()) {
            for (var par : delar[1].split(";")) {
                var i = par.indexOf('=');
                if (i > 0) {
                    parametrar.put(par.substring(0, i), par.substring(i + 1));
                }
            }
        }
        return fel(Response.Status.UNAUTHORIZED, delar[2], delar[0], parametrar);
    }

    /** Fel utan språkoberoende kod: kontrollrummet visar texten som den är (på engelska via reservöversättaren). */
    private Response fel(Response.Status status, String meddelande) {
        return fel(status, meddelande, null, Map.of());
    }

    /**
     * Fel med svensk text för den som anropar direkt, plus {@code kod} och {@code parametrar}: samma meddelande
     * språkoberoende, som kontrollrummets meddelandekatalog visar på läsarens språk.
     */
    private Response fel(Response.Status status, String meddelande, String kod, Map<String, ?> parametrar) {
        var kropp = new HashMap<String, Object>();
        kropp.put("fel", meddelande);
        if (kod != null) {
            kropp.put("kod", kod);
            kropp.put("parametrar", parametrar);
        }
        monitor.warning("KoV-GATE avvisade anrop: " + meddelande);
        return Response.status(status).entity(kropp).build();
    }
}
