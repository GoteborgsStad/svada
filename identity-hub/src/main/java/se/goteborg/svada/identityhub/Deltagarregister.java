/*
 * SVADA PoC – deltagarregistret (MIM3 RC5.1: deltagarna kan upptäcka varandra).
 *
 * KONCEPT: docs/koncept/C1-identitet.md, plan: docs/plan/deltagarregister-plan.md
 *
 * Samordningsrollens (Svadas utfärdare) lista över deltagarna: DID, namn, medlemsstatus och adressen där
 * deltagarens connector svarar på Dataspace Protocol. Utfärdaren känner redan deltagarna (den utfärdar deras
 * medlems- och deltagarintyg och håller statuslistan); registret berättar det för dem som frågar.
 *
 * Registret anger INTE roller. Den som intygar något ska ha mandat att intyga just det: stadens roll som
 * rättighetsinnehavare intygar staden själv, DHI sin egen. Samordnaren intygar bara medlemskap och deltagande.
 *
 * MEDVETEN FÖRENKLING: namn och adresser kommer ur utfärdarens konfiguration (SVADA_ISSUER_DELTAGARINFO) och
 * lagras i minnet; ingen ansökan, invändning eller borttagning (regelboken, G15). Adressen är deltagarens egen
 * uppgift till samordnaren och kontrolleras inte. DID-dokumenten bär bara en CredentialService-adress; att lägga
 * Dataspace Protocol-adressen i DID-dokumentet är ett senare alternativ.
 */
package se.goteborg.svada.identityhub;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Deltagarregister {

    /** Namn och Dataspace Protocol-adress för en deltagare. */
    public record Info(String namn, String dspAdress) {
    }

    private static final Deltagarregister INSTANS = new Deltagarregister();

    private final Map<String, Info> info = new LinkedHashMap<>();
    private String utfardarDid;

    public static Deltagarregister instans() {
        return INSTANS;
    }

    public synchronized void konfigurera(String utfardarDid, Map<String, Info> info) {
        this.utfardarDid = utfardarDid;
        this.info.clear();
        this.info.putAll(info);
    }

    /** Registret som ett JSON-träd. Status läses ur statuslistan vid varje anrop, så en återkallelse syns direkt. */
    public synchronized Map<String, Object> register(StatusLista status) {
        var deltagare = new ArrayList<Map<String, Object>>();
        for (var m : status.mottagare().entrySet()) {
            var post = new LinkedHashMap<String, Object>();
            var i = info.get(m.getKey());
            post.put("id", m.getKey());
            post.put("did", m.getValue());
            post.put("name", i == null ? null : i.namn());
            post.put("membership", Map.of("status", status.statusFor(m.getKey(), "SvadaMembershipCredential")));
            post.put("participation", Map.of("status", status.statusFor(m.getKey(), "SvadaParticipantCredential")));
            post.put("dspEndpoint", i == null ? null : i.dspAdress());
            deltagare.add(post);
        }
        var ut = new LinkedHashMap<String, Object>();
        ut.put("note", "The orchestrator's list of participants in the Svada PoC. Status is read from the revocation list at each request "
                + "(valid, revoked or unknown); it does not consider expiry. Roles are not stated here: each organisation attests its own role. "
                + "The endpoint is the participant's own registration with the orchestrator and is not verified. PoC: held in memory, "
                + "no application or removal flow, the issuer is not anchored in eIDAS.");
        ut.put("orchestrator", Map.of("did", utfardarDid == null ? "" : utfardarDid));
        ut.put("generatedAt", Instant.now().toString());
        ut.put("participants", deltagare);
        return ut;
    }

    /** "dhi=Namn|adress,stad=Namn|adress" -> {dhi: Info, stad: Info}. Namnet får inte innehålla , = eller |. */
    public static Map<String, Info> tolka(String lista) {
        var ut = new LinkedHashMap<String, Info>();
        if (lista == null || lista.isBlank()) {
            return ut;
        }
        for (var post : lista.split(",")) {
            var i = post.indexOf('=');
            if (i <= 0 || i >= post.length() - 1) {
                continue;
            }
            var delar = post.substring(i + 1).split("\\|", 2);
            ut.put(post.substring(0, i).trim(), new Info(delar[0].trim(), delar.length > 1 ? delar[1].trim() : null));
        }
        return ut;
    }
}
