/*
 * SVADA PoC – KoV-gaten.
 * KONCEPT: docs/koncept/06-kov-gate.md
 *
 * HÅRD REGEL 7:
 * KoV-godkännandet för Distribution A implementeras på PROVIDER-sidan, i
 * DHI:s connector. Enligt Dataspace Protocol äger providern
 * policyverkställigheten – suveräniteten upprätthålls vid källan, inte hos
 * mottagaren. Consumern kan alltså inte kringgå gaten ens om den vill.
 *
 * MEKANISMEN – EDC:s ContractNegotiationPendingGuard
 * ==================================================
 * Eclipse EDC har en inbyggd förlängningspunkt för exakt det här fallet:
 *
 *   ContractNegotiationPendingGuard extends PendingGuard<ContractNegotiation>
 *   "a service that permits to choose whether a ContractNegotiation will be
 *    waiting for an external interaction"
 *
 * Providerns statsmaskin (ProviderContractNegotiationManagerImpl) kör guarden
 * FÖRE varje processteg. Returnerar den true sätts negotiation.pending = true
 * och posten filtreras bort ur statsmaskinens frågor (isNotPending()) – den
 * ligger kvar i sitt tillstånd (REQUESTED) och rör sig inte förrän någon
 * sätter pending = false igen. Det är precis "förhandlingen pausar hos DHI:s
 * connector tills Data Rights Holder-beslut ges".
 *
 * Alternativen som VALDES BORT:
 *  - ODRL-constraint som returnerar false tills godkännande: ger TERMINATED
 *    direkt, inte ett vänteläge. Fel semantik för testfall 4b.2.
 *  - Proxy/approval-tjänst framför management-API:t: hade inte pausat något,
 *    bara fördröjt registreringen. Gaten hade legat UTANFÖR connectorn.
 *
 * VAD SOM UTLÖSER GATEN
 * =====================
 * Inte ett hårdkodat asset-id, utan ODRL-policyn själv: en förhandling gate:as
 * om dess kontraktsoffert bär obligationen med action
 * svada:kovGodkannande (se se.goteborg.svada.edc.odrl.SvadaOdrlExtension).
 * Policyn DEKLARERAR kravet, gaten VERKSTÄLLER det. Registrerar man i
 * framtiden fler K1-produkter behöver den här koden inte ändras.
 */

package se.goteborg.svada.edc.kov;

import org.eclipse.edc.connector.controlplane.contract.spi.negotiation.ContractNegotiationPendingGuard;
import org.eclipse.edc.connector.controlplane.contract.spi.types.negotiation.ContractNegotiation;
import org.eclipse.edc.connector.controlplane.contract.spi.types.negotiation.ContractNegotiationStates;
import org.eclipse.edc.policy.model.Policy;
import org.eclipse.edc.policy.model.Rule;
import org.eclipse.edc.spi.monitor.Monitor;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Stream;

import static se.goteborg.svada.edc.odrl.SvadaOdrlExtension.ACTION_KOV_GODKANNANDE;

public class KovGate implements ContractNegotiationPendingGuard {

    /** Data Rights Holder-beslutet per förhandling. */
    public enum Beslut { GODKAND, AVSLAGEN }

    /**
     * Besluten. In-memory precis som EDC:s övriga stores i PoC:en
     * (resursstrategin, hård regel 3) – en omstart av providern nollställer både
     * förhandlingar och beslut.
     */
    private final Map<String, Beslut> beslut = new ConcurrentHashMap<>();

    /**
     * Den kryptografiskt verifierade rollen (SvadaRoleCredential-claimet)
     * som fattade respektive beslut, en per förhandling. Fylls av
     * KovController.beslut() vid samma tillfälle som beslut ovan.
     *
     * TILLKOM 2026-09-02: fram till dess
     * fanns den verifierade rollen bara i engångssvaret på
     * POST .../godkann|avsla, inte i negotiation-objektet – så
     * GET /management/kov/forhandlingar (dashboardens auditlogg-källa,
     * services/dashboard/audit.py _kov()) kunde aldrig visa VEM som
     * beslutat, bara VAD. Auditloggens källor måste bära den verifierade
     * identiteten i sina poster, annars förblir beslutsfattaren obevisad.
     */
    private final Map<String, String> beslutsfattare = new ConcurrentHashMap<>();
    private final Monitor monitor;

    /**
     * Namngivet KoV-rollnamn, satt via svada.kov.rollinnehavare i
     * provider.properties (env SVADA_KOV_ROLLINNEHAVARE).
     *
     * DCP-identitetens verifieringssteg: den här strängen har numera EN DUBBEL ROLL. Den är
     * fortfarande visningsnamnet som loggas här i gaten (t.ex. "Kretslopp
     * och Vatten ... väntar på Data Rights Holder-beslut"), men
     * KovGateExtension ger SAMMA värde vidare till KovIdentitetsverifiering
     * som det KRÄVDA värdet en avsändares verifierade SvadaRoleCredential
     * "role"-claim måste matcha exakt (se KovController.beslut()). Fram till
     * verifieringssteget var strängen bara attribuerbarhet i loggen, aldrig bevisad –
     * nu är den även den faktiska behörighetsgränsen.
     */
    private final String rollinnehavare;

    public KovGate(Monitor monitor, String rollinnehavare) {
        this.monitor = monitor;
        this.rollinnehavare = rollinnehavare;
    }

    /**
     * @return det konfigurerade rollnamnet – används dels för loggning här
     *     i gaten, dels (via KovGateExtension) som det KRÄVDA värdet i
     *     KovIdentitetsverifiering (DCP-identitetens verifieringssteg).
     */
    public String rollinnehavare() {
        return rollinnehavare;
    }

    // -----------------------------------------------------------------
    // PendingGuard: körs av providerns statsmaskin före varje processteg.
    // -----------------------------------------------------------------
    @Override
    public boolean test(ContractNegotiation forhandling) {
        // Bara providerledet. Samma jar kör som consumer och
        // där ska guarden aldrig bita.
        if (forhandling.getType() != ContractNegotiation.Type.PROVIDER) {
            return false;
        }
        // Gate:a ENBART i REQUESTED. Andra tillstånd måste få passera, annars
        // fastnar även TERMINATING – dvs. avslaget (4b.5) hade aldrig kunnat
        // skickas till consumern.
        if (forhandling.getState() != ContractNegotiationStates.REQUESTED.code()) {
            return false;
        }
        if (!kraverGodkannande(forhandling)) {
            return false;
        }
        if (beslut.containsKey(forhandling.getId())) {
            return false;   // KoV har beslutat – släpp fram den
        }

        monitor.warning("KoV-GATE: förhandling " + forhandling.getId()
                + " om " + assetId(forhandling)
                + " väntar på Data Rights Holder-beslut (" + rollinnehavare + "). "
                + "Godkänn/avslå via providerns management-API: "
                + "POST /management/kov/forhandlingar/" + forhandling.getId()
                + "/godkann | /avsla");
        return true;
    }

    // -----------------------------------------------------------------
    // Beslutsregistret
    // -----------------------------------------------------------------
    public void registrera(String forhandlingsId, Beslut b, String verifieradRoll) {
        beslut.put(forhandlingsId, b);
        beslutsfattare.put(forhandlingsId, verifieradRoll);
        monitor.warning("KoV-GATE: " + rollinnehavare + " "
                + (b == Beslut.GODKAND ? "GODKÄNDE" : "AVSLOG")
                + " förhandling " + forhandlingsId + " (Distribution A).");
    }

    // ------------------------------------------------------------------
    // Hävning av avtal. Providern äger spärren (hård regel 7).
    // ------------------------------------------------------------------
    /**
     * Ett avtal som KoV har hävt. Avtal gäller tills de hävs, inte för en
     * enstaka datahämtning. Orsaken är antingen AVSLAG (PoC-regeln: ett avslag
     * av en ny begäran om samma tillgång från samma part häver tidigare avtal,
     * så att flödet går att testa ordentligt) eller EXPLICIT (KoV häver ett
     * avtal direkt). PoC-förenkling (se docs/koncept/06): i ett riktigt dataspace kan ett avslag
     * fungera så, eller så är hävning en egen åtgärd som måste byggas.
     */
    public record Havning(String avtalId, String tillgang, String konsument,
                          String orsak, String av, String tid, String forhandlingId) {
    }

    /** Avtal-id -> hävning. Minnet nollställs vid omstart, som all annan EDC-state i PoC:en. */
    private final Map<String, Havning> havda = new ConcurrentHashMap<>();

    /**
     * Häver ett avtal. Idempotent: det första beslutet gäller, en andra
     * hävning ändrar inte tid eller orsak.
     */
    public boolean hav(String avtalId, String tillgang, String konsument, String orsak,
                       String verifieradRoll, String forhandlingId) {
        var ny = new Havning(avtalId, tillgang, konsument, orsak, verifieradRoll,
                Instant.now().toString(), forhandlingId);
        var fanns = havda.putIfAbsent(avtalId, ny);
        if (fanns == null) {
            monitor.warning("KoV-GATE: " + verifieradRoll + " HÄVDE avtal " + avtalId
                    + " (" + tillgang + ", " + konsument + ", orsak " + orsak + ").");
            return true;
        }
        return false;
    }

    public boolean arHavd(String avtalId) {
        return avtalId != null && havda.containsKey(avtalId);
    }

    public Havning havning(String avtalId) {
        return havda.get(avtalId);
    }

    public Beslut beslut(String forhandlingsId) {
        return beslut.get(forhandlingsId);
    }

    /**
     * Den verifierade rollen som fattade beslutet, eller null om
     * förhandlingen ännu inte beslutats. Se fältets docstring ovan.
     */
    public String beslutsfattare(String forhandlingsId) {
        return beslutsfattare.get(forhandlingsId);
    }

    // -----------------------------------------------------------------
    // ODRL: bär offerten obligationen svada:kovGodkannande?
    // -----------------------------------------------------------------
    public boolean kraverGodkannande(ContractNegotiation forhandling) {
        var offert = forhandling.getLastContractOffer();
        return offert != null && kraverGodkannande(offert.getPolicy());
    }

    public boolean kraverGodkannande(Policy policy) {
        if (policy == null) {
            return false;
        }
        // Explicit uppcastning till Rule: getObligations/getPermissions/
        // getProhibitions returnerar tre OLIKA listtyper, och utan casten
        // klarar javac inte typinferensen i Stream.concat.
        Stream<Rule> regler = Stream.concat(
                Stream.concat(
                        policy.getObligations().stream().map(r -> (Rule) r),
                        policy.getPermissions().stream().map(r -> (Rule) r)),
                policy.getProhibitions().stream().map(r -> (Rule) r));
        return regler
                .map(Rule::getAction)
                .anyMatch(a -> a != null
                        && ACTION_KOV_GODKANNANDE.equals(a.getType()));
    }

    public String assetId(ContractNegotiation forhandling) {
        var offert = forhandling.getLastContractOffer();
        return offert == null ? null : offert.getAssetId();
    }
}
