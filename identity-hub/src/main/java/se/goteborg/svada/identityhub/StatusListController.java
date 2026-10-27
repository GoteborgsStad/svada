/*
 * SVADA PoC – Svadas statuslista och återkallelse.
 *
 * KONCEPT: docs/koncept/C1-identitet.md
 *
 * Två delar på utfärdarens DID-sammanhang (port 49197):
 *   GET  /status/revocation/1                          – statuslisteintyget (JWT, publikt, som en DID):
 *                                                        det connectorernas verifierare hämtar
 *                                                        (StatusListPublik, egen rotklass)
 *   GET  /svada-status                                 – vilka intyg som har vilket index (kräver nyckel)
 *   POST /svada-status/{mottagare}/{typ}/aterkalla     – sätter återkallelsebiten (kräver nyckel)
 *   POST /svada-status/{mottagare}/{typ}/aterinsatt    – rensar den igen (kräver nyckel)
 *
 * {mottagare} = dhi | stad. {typ} = medlemskap | deltagare. Nyckeln är samordningsrollens egen
 * (X-Api-Key). Det är samordnaren som har mandat att återkalla medlems- och deltagarintyg;
 * ingen deltagare kan återkalla en annans.
 */
package se.goteborg.svada.identityhub;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.edc.spi.monitor.Monitor;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * GOTCHA: klassen får INTE ha @Path("/"). IdentityHubs DID-resurs ligger på samma sammanhang med
 * @Path("/"), och JAX-RS väljer då bara en av rotklasserna med samma sökväg: våra metoder nås aldrig
 * (alla anrop svarar 204). Därför en rotklass per prefix, med en egen, mer specifik sökväg.
 */
@Path("/svada-status")
public class StatusListController {

    private static final Map<String, String> TYPER = Map.of(
            "medlemskap", "SvadaMembershipCredential",
            "deltagare", "SvadaParticipantCredential");

    private final StatusLista lista;
    private final String adminNyckel;
    private final Monitor monitor;

    public StatusListController(StatusLista lista, String adminNyckel, Monitor monitor) {
        this.lista = lista;
        this.adminNyckel = adminNyckel;
        this.monitor = monitor;
    }

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public Response poster(@HeaderParam("X-Api-Key") String nyckel) {
        if (!behorig(nyckel)) {
            return nekad();
        }
        return Response.ok(lista.poster()).build();
    }

    @POST
    @Path("/{mottagare}/{typ}/{atgard}")
    @Produces(MediaType.APPLICATION_JSON)
    public Response satt(@HeaderParam("X-Api-Key") String nyckel, @PathParam("mottagare") String mottagare,
                         @PathParam("typ") String typ, @PathParam("atgard") String atgard) {
        if (!behorig(nyckel)) {
            return nekad();
        }
        var typnamn = TYPER.get(typ);
        var aterkalla = "aterkalla".equals(atgard);
        if (typnamn == null || !(aterkalla || "aterinsatt".equals(atgard))) {
            return fel(Response.Status.BAD_REQUEST, "typ måste vara medlemskap|deltagare och åtgärd aterkalla|aterinsatt");
        }
        if (!lista.satt(mottagare, typnamn, aterkalla)) {
            return fel(Response.Status.NOT_FOUND, "Inget " + typnamn + " utfärdat åt '" + mottagare + "'");
        }
        monitor.info("SVADA statuslista: " + typnamn + " åt '" + mottagare + "' " + (aterkalla ? "ÅTERKALLAT" : "återinsatt")
                + " av samordningsrollen.");
        var svar = new LinkedHashMap<String, Object>();
        svar.put("mottagare", mottagare);
        svar.put("typ", typnamn);
        svar.put("aterkallat", aterkalla);
        return Response.ok(svar).build();
    }

    private boolean behorig(String nyckel) {
        return adminNyckel != null && !adminNyckel.isEmpty() && adminNyckel.equals(nyckel);
    }

    private Response nekad() {
        return fel(Response.Status.UNAUTHORIZED, "X-Api-Key saknas eller är fel");
    }

    private Response fel(Response.Status status, String text) {
        return Response.status(status).type(MediaType.APPLICATION_JSON).entity(Map.of("fel", text)).build();
    }
}

