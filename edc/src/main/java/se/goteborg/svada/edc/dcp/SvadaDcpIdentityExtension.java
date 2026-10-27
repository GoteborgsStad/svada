/*
 * SVADA PoC – verifierbar DCP-identitet, steg 5 (docs/koncept/C1-identitet.md).
 *
 * ===================================================================
 * VARFÖR DEN HÄR EXTENSIONEN BEHÖVS
 * ===================================================================
 * Seedar EDC-connectorns EGEN vault med den DETERMINISTISKA STS-
 * klienthemligheten (samma värde som IdentityHub-sidans
 * SvadaParticipantBootstrapExtension sätter via StsAccountService
 * #updateSecret - se den klassens "STS-KLIENTHEMLIGHET"-avsnitt).
 * Utan denna kan EDC-connectorn inte autentisera sig mot sin egen
 * IdentityHub-instans "embedded STS" och kan alltså inte hämta ett
 * self-issued token för utgående DSP-anrop
 * (edc.iam.sts.oauth.client.secret.alias i edc/konfig/*.properties
 * pekar på ALIASET denna extension seedar).
 *
 * Motsvarar samma "seeda direkt i Vault vid uppstart"-mönster som förut
 * täcktes av MockIamSeedExtension (borttagen i och med detta steg - se
 * edc/build.gradle.kts, iam-mock är helt bortplockad). OBS: den ENDA
 * kvarvarande biten av MockIamSeedExtension är transfer-proxy-tokens
 * signeringsnyckelpar, som INTE hör till dataspace-identiteten (DCP)
 * utan till dataplanets EGNA, separata token-mekanism - den ligger kvar
 * som en egen, mindre, ärligt omdöpt extension (se
 * SvadaTransferProxyNyckelExtension) eftersom verifierbar DCP-identitet inte omfattar en
 * ombyggnad av DATAPLANETS signeringsnycklar, bara DSP-lagrets identitet.
 *
 * ===================================================================
 * VARFÖR DEN INTE (LÄNGRE) BYTER UT PARTICIPANT-IDENTITETSKÄLLAN
 * ===================================================================
 * Ett tidigare försök i det här steget registrerade en egen, icke-default
 * @Provider för DefaultParticipantIdExtractionFunction (SvadaParticipant-
 * IdExtractionFunction, nu borttagen) som lät ParticipantAgent.getIdentity()
 * returnera den verifierade VC:ns "participantId"-claim ("stad"/"dhi")
 * i stället för motpartens riktiga DID - tanken var att slippa ändra
 * DeltagareFunktion.java:s ODRL-jämförelse (svada:deltagare eq "stad").
 *
 * Det visade sig vara fel avvägning: EDC:s EGET kontrollplan återanvänder
 * SAMMA ParticipantAgent.getIdentity()-värde till annat än ODRL, bl.a.
 * ContractNegotiationProtocolServiceImpl som sätter förhandlingens
 * counterPartyId direkt från agent.getIdentity() - och det värdet blir
 * sedan mål-audience (aud-claim) i de self-issued-tokens som krävs för
 * DSP-anrop TILLBAKA till samma motpart (t.ex. providerns
 * ContractAgreementMessage till consumern). Ett kortnamn som "stad" är
 * inte en giltig audience, så VARJE sådant återanrop floppade med 401
 * ("Token audience claim did not contain expected audience") - upptäckt
 * när verify_ap4b.sh:s förhandlingar fastnade i REQUESTED trots att
 * 4a.2:s enkelriktade katalogfråga gick igenom (felsökningen
 * beskrivs ovan).
 *
 * Lösningen: låt DCP-modulens EGEN default-funktion vara kvar (motpartens
 * riktiga DID, exakt vad resten av EDC:s kontrollplan redan förutsätter),
 * och gör i stället "stad"/"dhi"-jämförelsen DID-baserad: policy-
 * distribution-a.json:s svada:deltagare-constraint pekar numera på
 * Stadens DID (__STAD_DID__-platshållaren, se edc/bootstrap/registrera.py)
 * i stället för strängen "stad". DeltagareFunktion.java:s egen jämförelse-
 * logik är oförändrad - bara vilket värde den jämförs MOT är annorlunda.
 * ===================================================================
 */

package se.goteborg.svada.edc.dcp;

import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.security.Vault;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;

public class SvadaDcpIdentityExtension implements ServiceExtension {

    /**
     * Aliaset EDC-connectorns egen vault lagrar STS-klienthemligheten under.
     * Refereras av edc.iam.sts.oauth.client.secret.alias i
     * edc/konfig/provider.properties/consumer.properties - ett fritt valt
     * namn, oberoende av IdentityHub-sidans egen aliasformel
     * ("<participantId>-sts-client-secret"), eftersom de två aliasen lever
     * i två helt olika vault-instanser (ingen namnkollision möjlig).
     */
    public static final String STS_HEMLIGHET_ALIAS = "svada-sts-client-secret";

    /**
     * Config-nyckeln det DETERMINISTISKA värdet läses ur (satt via
     * miljövariabeln SVADA_STS_CLIENT_SECRET i compose.dhi.yml/
     * compose.stad.yml, ur .env:s SVADA_STS_CLIENT_SECRET_DHI/_STAD -
     * samma värde som IdentityHub-sidans motsvarande extension sätter,
     * se SvadaParticipantBootstrapExtension.java).
     */
    public static final String INSTALLNING_STS_HEMLIGHET_VARDE = "svada.sts.client.secret";

    /**
     * Config-nyckeln för connectorns egen deltagaridentitet (samma DID som
     * edc.participant.id i edc/konfig/provider.properties/consumer.properties).
     *
     * MÅSTE användas som vault-PARTITION vid seedning nedan - se felsökningen
     * av ett DCP-katalogfel (2026-09-14): InMemoryVault#storeSecret(key, value) (utan
     * partition) seedar i partitionen "default" OM ParticipantContext ännu
     * inte hunnit initieras när DENNA extension körs (tidigt i uppstarten) -
     * men RemoteSecureTokenService#resolveSecret(participantContextId, alias)
     * slår vid ANROPSTILLFÄLLET upp EXPLICIT i deltagarens egen DID-partition.
     * En tyst mismatch: hemligheten hittas aldrig, secret == null,
     * Result.failure() returneras INNAN något nätverksanrop görs till STS:en
     * - vilket exakt matchade symptomen (401/502 på katalog/förhandling/
     * transfer, noll trafik till STS eller motparten, ingen loggrad alls).
     */
    public static final String INSTALLNING_PARTICIPANT_ID = "edc.participant.id";

    @Inject
    private Vault vault;

    @Override
    public String name() {
        return "SVADA DCP-identitet";
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        var monitor = context.getMonitor();
        var varde = context.getConfig().getString(INSTALLNING_STS_HEMLIGHET_VARDE, null);
        if (varde == null) {
            monitor.warning(("SVADA DCP-identitet: %s ej satt - denna connector kan INTE " +
                    "autentisera mot sin egen IdentityHub-instans STS, utgående DSP-anrop " +
                    "som kräver ett self-issued token kommer att misslyckas.")
                    .formatted(INSTALLNING_STS_HEMLIGHET_VARDE));
            return;
        }
        var participantId = context.getConfig().getString(INSTALLNING_PARTICIPANT_ID, null);
        if (participantId == null) {
            monitor.warning(("SVADA DCP-identitet: %s ej satt - kan inte seeda vaulten i " +
                    "rätt partition, utgående DSP-anrop kommer att misslyckas.")
                    .formatted(INSTALLNING_PARTICIPANT_ID));
            return;
        }
        // Seeda EXPLICIT i deltagarens egen DID-partition - se klasskommentaren
        // ovan för varför den parameterlösa storeSecret(key, value) INTE duger.
        vault.storeSecret(participantId, STS_HEMLIGHET_ALIAS, varde);
        monitor.info(("SVADA DCP-identitet: STS-klienthemlighet seedad i vaulten under " +
                "alias '%s' i partition '%s'.").formatted(STS_HEMLIGHET_ALIAS, participantId));
    }
}
