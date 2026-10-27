/*
 * SVADA PoC – KoV-gaten (provider-sidig verkställighet).
 * KONCEPT: docs/koncept/06-kov-gate.md
 *
 * Kopplar in KoV-gaten i EDC-runtimen:
 *
 *  1. @Provider ContractNegotiationPendingGuard – ersätter EDC:s default
 *     (ContractNegotiationDefaultServicesExtension registrerar
 *     "it -> false" med @Provider(isDefault = true), så vår vinner).
 *  2. Registrerar KovController på management-kontexten.
 *  3. Registrerar AvtalsstatusController på ett EGET api-sammanhang (avtalsstatus, egen nyckel).
 *
 * ROLLBEROENDE: hela gaten aktiveras av inställningen
 *
 *     svada.kov.gate.enabled=true
 *
 * som ENBART står i edc/konfig/provider.properties. Provider och consumer
 * kör samma image; det är konfigurationen
 * som gör den ena till Data Rights Holder-grind och lämnar den andra utan.
 * Utan flaggan levereras den öppna guarden och ingen /kov-endpoint finns –
 * verifieringens testfall 4b.4 (ingen consumer-bakväg) beror på det.
 *
 * VERIFIERBAR IDENTITET, STEG 6 (docs/koncept/C1-identitet.md):
 * KovController kräver numera dessutom ett verifierat SvadaRoleCredential i
 * anropets Authorization-header, inte bara den delade management-nyckeln
 * (de nyckelskyddade management-API:erna). Den här extensionen bygger verifieraren
 * (KovIdentitetsverifiering) genom att injicera EDC:s egen IdentityService
 * (samma SPI som DSP-lagret redan använder, se KovIdentitetsverifiering.java
 * för hela motiveringen) och läsa den egna DHI-identiteten ur
 * edc.participant.id.
 */

package se.goteborg.svada.edc.kov;

import org.eclipse.edc.connector.controlplane.contract.spi.negotiation.ContractNegotiationPendingGuard;
import org.eclipse.edc.connector.controlplane.contract.spi.negotiation.store.ContractNegotiationStore;
import org.eclipse.edc.connector.controlplane.contract.spi.policy.TransferProcessPolicyContext;
import org.eclipse.edc.policy.engine.spi.PolicyEngine;
import org.eclipse.edc.policy.model.Duty;
import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.runtime.metamodel.annotation.Provider;
import org.eclipse.edc.spi.iam.IdentityService;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;
import org.eclipse.edc.web.spi.WebService;
import org.eclipse.edc.api.auth.spi.AuthenticationRequestFilter;
import org.eclipse.edc.api.auth.spi.registry.ApiAuthenticationRegistry;
import org.eclipse.edc.web.spi.configuration.ApiContext;
import org.eclipse.edc.web.spi.configuration.PortMapping;
import org.eclipse.edc.web.spi.configuration.PortMappingRegistry;

public class KovGateExtension implements ServiceExtension {

    /** Konfigurationsnyckeln som gör connectorn till KoV-grind. */
    public static final String INSTALLNING_AKTIV = "svada.kov.gate.enabled";

    /**
     * Namngivet KoV-rollnamn (docs/koncept/C1-identitet.md).
     * Default gäller bara om SVADA_KOV_ROLLINNEHAVARE av misstag saknas –
     * provider.properties/.env sätter alltid det riktiga värdet.
     */
    public static final String INSTALLNING_ROLLINNEHAVARE = "svada.kov.rollinnehavare";
    private static final String ROLLINNEHAVARE_DEFAULT = "Kretslopp och Vatten";

    /**
     * DCP-identitetens verifieringssteg: samma konfigurationsnyckel som connectorns egen DCP-
     * identitet redan sätts med (edc/konfig/provider.properties, STEG 5) –
     * KovIdentitetsverifiering behöver DHI:s egen participantContextId för
     * att be IdentityService verifiera avsändarens (KoV:s) token.
     */
    private static final String INSTALLNING_PARTICIPANT_ID = "edc.participant.id";

    /** Namnet på api-sammanhanget i konfigurationen: web.http.avtalsstatus.*. */
    private static final String STATUS_SAMMANHANG = "avtalsstatus";

    @Inject
    private ContractNegotiationStore forhandlingsStore;

    @Inject
    private WebService webService;

    @Inject
    private PortMappingRegistry portMappingRegistry;

    @Inject
    private ApiAuthenticationRegistry authenticationRegistry;

    @Inject
    private IdentityService identityService;

    @Inject
    private PolicyEngine policyEngine;

    private KovGate gate;

    @Override
    public String name() {
        return "SVADA KoV-gate (provider-sidig)";
    }

    /**
     * Lat initiering: @Provider-metoden och initialize() kan köras i valfri
     * ordning beroende på hur beroendena löses, och båda behöver SAMMA
     * gate-instans (beslutsregistret ligger i den).
     */
    private KovGate gate(ServiceExtensionContext context) {
        if (gate == null) {
            var rollinnehavare = context.getConfig()
                    .getString(INSTALLNING_ROLLINNEHAVARE, ROLLINNEHAVARE_DEFAULT);
            gate = new KovGate(context.getMonitor(), rollinnehavare);
        }
        return gate;
    }

    private boolean aktiv(ServiceExtensionContext context) {
        return context.getConfig().getBoolean(INSTALLNING_AKTIV, false);
    }

    @Provider
    public ContractNegotiationPendingGuard kovPendingGuard(ServiceExtensionContext context) {
        if (!aktiv(context)) {
            // Consumer-rollen: samma default som EDC själv har.
            return forhandling -> false;
        }
        return gate(context);
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        var monitor = context.getMonitor();
        if (!aktiv(context)) {
            monitor.info("KoV-gaten är AV i den här connectorn (" + INSTALLNING_AKTIV
                    + " ej satt). Inga /management/kov-endpoints registreras.");
            return;
        }

        var egetParticipantId = context.getConfig().getString(INSTALLNING_PARTICIPANT_ID);
        var verifierare = new KovIdentitetsverifiering(identityService, egetParticipantId,
                gate(context).rollinnehavare());

        // Hävning: spärren vid överföringens start (se HavdAvtalSparr). Hård regel 7: hos providern.
        policyEngine.registerFunction(TransferProcessPolicyContext.class, Duty.class,
                new HavdAvtalSparr(gate(context), monitor));

        webService.registerResource(ApiContext.MANAGEMENT,
                new KovController(forhandlingsStore, gate(context), verifierare, monitor,
                        context.getConfig().getBoolean("svada.kov.avslag.havartidigare", true)));
        // Smal, skrivskyddad status för mottagaren: eget api-sammanhang och egen nyckel
        // (web.http.avtalsstatus.*), så att staden inte behöver management-nyckeln.
        // Ett eget api-sammanhang är inget EDC skapar av sig självt: porten registreras här,
        // och autentiseringen (web.http.avtalsstatus.auth.*) sätts av auth-configuration.
        var statusCfg = context.getConfig("web.http." + STATUS_SAMMANHANG);
        portMappingRegistry.register(new PortMapping(STATUS_SAMMANHANG,
                statusCfg.getInteger("port", 19195), statusCfg.getString("path", "/status")));
        webService.registerResource(STATUS_SAMMANHANG,
                new AuthenticationRequestFilter(authenticationRegistry, STATUS_SAMMANHANG));
        webService.registerResource(STATUS_SAMMANHANG,
                new AvtalsstatusController(forhandlingsStore, gate(context)));

        monitor.info("KoV-gaten är PÅ (hård regel 7: provider-sidig "
                + "policyverkställighet). Data Rights Holder-beslut ges på "
                + "management-API:t: GET/POST /management/kov/forhandlingar[/{id}/godkann|/avsla]"
                + " och GET /management/kov/avtal, POST /management/kov/avtal/{id}/hav");
    }
}
