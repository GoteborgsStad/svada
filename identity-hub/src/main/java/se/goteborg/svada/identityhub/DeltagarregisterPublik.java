/*
 * SVADA PoC – deltagarregistret, den publika delen (se Deltagarregister). Öppet för alla som når utfärdarens DID-adress
 * (beslut 2026-10-28: öppet i demon). Egen rotklass med sökvägen /participants, se GOTCHA i StatusListController.
 */
package se.goteborg.svada.identityhub;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import java.util.Map;

@Path("/participants")
public class DeltagarregisterPublik {

    private final Deltagarregister register;
    private final StatusLista status;

    public DeltagarregisterPublik(Deltagarregister register, StatusLista status) {
        this.register = register;
        this.status = status;
    }

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public Map<String, Object> deltagare() {
        return register.register(status);
    }
}
