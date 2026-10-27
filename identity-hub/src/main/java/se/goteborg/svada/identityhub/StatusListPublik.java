/*
 * SVADA PoC – Svadas statuslista, den publika delen (se StatusListController och StatusLista).
 */
package se.goteborg.svada.identityhub;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
/** Statuslisteintyget (publikt, som en DID). Egen rotklass med sökvägen /status, se GOTCHA ovan. */
@Path("/status")
public class StatusListPublik {

    private final StatusLista lista;

    public StatusListPublik(StatusLista lista) {
        this.lista = lista;
    }

    @GET
    @Path("/revocation/1")
    @Produces("application/vc+jwt")
    public String statuslista() {
        return lista.signeradLista();
    }
}
