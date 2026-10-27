/*
 * SVADA PoC – ODRL-bindningar.
 * KONCEPT: docs/koncept/05-dsp-odrl.md
 *
 * VARFÖR DEN HÄR EXTENSIONEN FINNS
 * ================================
 * Eclipse EDC:s policymotor utvärderar INTE en ODRL-regel bara för att den
 * står i policyn. Innan utvärderingen kör motorn ett SCOPE-FILTER
 * (org.eclipse.edc.policy.engine.ScopeFilter): varje permission/prohibition/
 * duty vars ACTION inte är bunden till det aktuella scope:t tas bort ur
 * policyn, och varje atomär constraint vars LEFT OPERAND inte är bunden tas
 * bort ur sin regel. En regel som ingen binder försvinner alltså tyst – den
 * syns i katalogen och i avtalet, men den verkställer ingenting.
 *
 * Det var precis därför Distribution B:s policy lämnades TOM i katalog- och förhandlingsprovet: en obunden ODRL-regel hade sett ut som
 * ett bevis utan att vara det. Den här extensionen gör deltagarvillkoret och förbuden
 * verkliga, så att HavdAvtalSparr körs i transfer-scope.
 *
 * SVADA:S ODRL-PROFIL
 * ===================
 * ODRL:s kärnvokabulär (http://www.w3.org/ns/odrl/2/) räcker för actions:
 * use, distribute, publish, attribute. Det som är SVADA-specifikt får en
 * egen namnrymd, https://svada.goteborg.se/ns/ – det är så ett dataspace
 * definierar sin egen ODRL-profil, och en av lärdomarna att ta med:
 *
 *   svada:deltagare      – left operand: vilken dataspace-deltagare som
 *                          begär avtalet (Distribution A får bara förhandlas
 *                          av Göteborgs Stad).
 *   svada:kovGodkannande – action på en ODRL-obligation. Den DEKLARERAR att
 *                          avtalet kräver Data Rights Holder-beslut från
 *                          Kretslopp och Vatten. Själva verkställandet gör
 *                          KovGate (se se.goteborg.svada.edc.kov) på
 *                          PROVIDER-sidan – hård regel 7.
 *   svada:medgerGranskning – action på en ODRL-obligation. Deklarerar att mottagaren medger
 *                          granskning (revision) av hur datat används. Verkställs inte av
 *                          någon komponent; den hör till datadelningsavtalet.
 */

package se.goteborg.svada.edc.odrl;

import org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext;
import org.eclipse.edc.policy.engine.spi.PolicyEngine;
import org.eclipse.edc.policy.engine.spi.RuleBindingRegistry;
import org.eclipse.edc.policy.model.Permission;
import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;

import java.util.List;

import static org.eclipse.edc.connector.controlplane.catalog.spi.policy.CatalogPolicyContext.CATALOG_SCOPE;
import static org.eclipse.edc.connector.controlplane.contract.spi.policy.ContractNegotiationPolicyContext.NEGOTIATION_SCOPE;
import static org.eclipse.edc.connector.controlplane.contract.spi.policy.TransferProcessPolicyContext.TRANSFER_SCOPE;

public class SvadaOdrlExtension implements ServiceExtension {

    /** ODRL:s kärnvokabulär. Termen "use" i JSON-LD expanderas hit. */
    public static final String ODRL_NS = "http://www.w3.org/ns/odrl/2/";
    /** SVADA:s egen ODRL-profil (dataspacets egna termer). */
    public static final String SVADA_NS = "https://svada.goteborg.se/ns/";

    public static final String ACTION_USE = ODRL_NS + "use";
    public static final String ACTION_DISTRIBUTE = ODRL_NS + "distribute";
    public static final String ACTION_PUBLISH = ODRL_NS + "publish";
    public static final String ACTION_ATTRIBUTE = ODRL_NS + "attribute";

    /** Action på obligationen som säger "detta avtal kräver KoV-beslut". */
    public static final String ACTION_KOV_GODKANNANDE = SVADA_NS + "kovGodkannande";
    /**
     * Action på obligationen som säger "mottagaren medger granskning av hur datat används".
     * ENBART en deklaration: ingen connector kan verkställa den. Efterlevnaden vilar på
     * datadelningsavtalet och på granskning, inte på tekniken.
     */
    public static final String ACTION_MEDGER_GRANSKNING = SVADA_NS + "medgerGranskning";
    /** Left operand: den deltagare som begär avtalet. */
    public static final String LEFT_DELTAGARE = SVADA_NS + "deltagare";

    /**
     * De tre scope:n EDC utvärderar en dataprodukts policy i:
     * catalog            – vem får SE datasetet (accessPolicy)
     * contract.negotiation – vem får ingå AVTAL om det (contractPolicy)
     * transfer.process   – vad får göras vid själva överföringen
     */
    private static final List<String> SCOPES =
            List.of(CATALOG_SCOPE, NEGOTIATION_SCOPE, TRANSFER_SCOPE);

    private static final List<String> ACTIONS = List.of(
            ACTION_USE, ACTION_DISTRIBUTE, ACTION_PUBLISH, ACTION_ATTRIBUTE,
            ACTION_KOV_GODKANNANDE, ACTION_MEDGER_GRANSKNING);

    @Inject
    private RuleBindingRegistry ruleBindingRegistry;

    @Inject
    private PolicyEngine policyEngine;

    @Override
    public String name() {
        return "SVADA ODRL-bindningar";
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        var monitor = context.getMonitor();

        // 1. Bind alla actions i alla tre scope:n. Utan detta filtreras
        //    reglerna bort före utvärdering (se klasskommentaren).
        for (var scope : SCOPES) {
            for (var action : ACTIONS) {
                ruleBindingRegistry.bind(action, scope);
            }
        }

        // 2. svada:deltagare binds ENBART i contract.negotiation.
        //    GOTCHA: en bunden left operand UTAN registrerad funktion ger
        //    "No evaluation function found" => regeln utvärderas till FALSKT
        //    och hela policyn faller. Bind därför bara i det scope där
        //    funktionen nedan faktiskt är registrerad; i katalog- och
        //    transferscope filtreras constrainten bort och permissionen
        //    passerar (ScopeFilter: en regel utan constraints är sann).
        ruleBindingRegistry.bind(LEFT_DELTAGARE, NEGOTIATION_SCOPE);
        policyEngine.registerFunction(
                ContractNegotiationPolicyContext.class, Permission.class,
                LEFT_DELTAGARE, new DeltagareFunktion(monitor));

        monitor.info("SVADA ODRL: bundna actions " + ACTIONS
                + " i scope " + SCOPES
                + "; left operand " + LEFT_DELTAGARE
                + " bunden i " + NEGOTIATION_SCOPE
                + " med utvärderingsfunktion.");
    }
}
