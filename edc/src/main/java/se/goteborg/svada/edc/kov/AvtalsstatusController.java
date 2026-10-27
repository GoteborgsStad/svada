/*
 * SVADA PoC – providerns smala statusendpoint för avtal.
 *
 * KONCEPT: docs/koncept/06-kov-gate.md
 *
 * Varför den finns: staden behöver veta om ett avtal gäller, men ska inte behöva
 * providerns management-nyckel för det. Management-API:t ger även rätt att skapa och
 * ändra tillgångar, policyer och avtal. Den här endpointen ligger på ett EGET
 * api-sammanhang (web.http.avtalsstatus), med EN EGEN nyckel, och kan bara läsa:
 *
 *   GET /avtalsstatus   – avtalen som KoV-spärren gäller: id, tillgång, part,
 *                         consumerns förhandlings-id (correlationId), status, hävning.
 *
 * Inga beslut, ingen hävning, inga andra avtal än de KoV-spärren gäller. Kopplingen mellan
 * avtalets id hos providern och hos staden går via correlationId (DSP consumerPid).
 *
 * Observera: statusen avser HÄVNING (GALLANDE eller HAVT). Ett avtal vars giltighetstid gått ut står kvar som
 * GALLANDE här; utgången läser mottagaren ur avtalets policy (inForceDate), och providern verkställer den vid
 * överföring.
 *
 * Medveten förenkling (se G23): staden hämtar (pollar) listan. I ett riktigt dataområde bör en
 * hävning nå parten genom protokollet eller en signerad statuslista (G23).
 */
package se.goteborg.svada.edc.kov;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import org.eclipse.edc.connector.controlplane.contract.spi.negotiation.store.ContractNegotiationStore;
import org.eclipse.edc.connector.controlplane.contract.spi.types.negotiation.ContractNegotiation;
import org.eclipse.edc.spi.query.QuerySpec;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Path("/avtalsstatus")
@Produces(MediaType.APPLICATION_JSON)
public class AvtalsstatusController {

    private final ContractNegotiationStore store;
    private final KovGate gate;

    public AvtalsstatusController(ContractNegotiationStore store, KovGate gate) {
        this.store = store;
        this.gate = gate;
    }

    @GET
    public List<Map<String, Object>> avtal() {
        // avtalets id -> consumerns förhandlings-id, ur providerns egna förhandlingar
        var korrelation = new HashMap<String, String>();
        try (var forh = store.queryNegotiations(QuerySpec.max())) {
            forh.filter(n -> n.getType() == ContractNegotiation.Type.PROVIDER)
                    .filter(n -> n.getContractAgreement() != null)
                    .forEach(n -> korrelation.put(n.getContractAgreement().getId(), n.getCorrelationId()));
        }
        try (var avtal = store.queryAgreements(QuerySpec.max())) {
            return avtal
                    .filter(a -> gate.kraverGodkannande(a.getPolicy()))
                    .map(a -> {
                        var m = new LinkedHashMap<String, Object>();
                        m.put("id", a.getId());
                        m.put("correlationId", korrelation.get(a.getId()));
                        m.put("assetId", a.getAssetId());
                        m.put("consumerId", a.getConsumerId());
                        var h = gate.havning(a.getId());
                        m.put("status", h == null ? "GALLANDE" : "HAVT");
                        if (h != null) {
                            var hm = new LinkedHashMap<String, Object>();
                            hm.put("tid", h.tid());
                            hm.put("orsak", h.orsak());
                            m.put("havning", hm);
                        }
                        return (Map<String, Object>) m;
                    })
                    .toList();
        }
    }
}
