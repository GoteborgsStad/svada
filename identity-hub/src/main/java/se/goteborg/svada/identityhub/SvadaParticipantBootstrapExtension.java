/*
 * SVADA PoC – verifierbar identitet i IdentityHub (docs/koncept/C1-identitet.md).
 *
 * ===================================================================
 * VARFÖR DEN HÄR FILEN BEHÖVS
 * ===================================================================
 * IdentityHubs eget säkerhetsdokument (docs/developer/architecture/
 * identity-api.security.md i uppströmskällan) är uttryckligt: "Out-of-the
 * box, IdentityHub does NOT have any users/participant contexts/principals
 * configured" – och EFTERSOM varje anrop mot Identity API:t (även att SKAPA
 * en participant context) kräver en redan autentiserad service principal
 * med rollen "admin", finns det inget sätt att bootstrap:a den FÖRSTA
 * identiteten via REST-API:t. Det måste göras in-process, vid uppstart,
 * med direkt tillgång till IdentityHubParticipantContextService – exakt
 * det den här extensionen gör.
 *
 * Den här instansen av IdentityHub är EN-TENANT (en part: DHI eller
 * Staden, aldrig båda) – därför behövs ingen separat "superuser"-identitet
 * skild från partens egen identitet. Vi skapar EN participant context per
 * instans, ger den rollen "admin" (så att parten kan administrera sig
 * själv, t.ex. regenerera sin egen API-nyckel senare) och publicerar dess
 * did:web direkt.
 *
 * Idempotent: körs vid VARJE uppstart (in-memory lagring nollställs annars
 * varje omstart; resursstrategin, hård regel 3), men skapar inte om identiteten
 * redan finns.
 *
 * AES-KRYPTERING (UPPTÄCKT 2026-09-01, verifierat live): IdentityHubs
 * ParticipantContextConfigService krypterar "sensitive config" (bl.a. det
 * STS-klienthemlighet som ParticipantManifest#clientSecretAlias() alltid
 * refererar till, även om vi inte bett om en) med AES som DEFAULT-
 * algoritm (edc.participants.config.encryption.algorithm=aes,
 * ParticipantContextConfigServicesExtension). AES-tillägget
 * (AesEncryptionExtension, ingår redan i identityhub-base-bom) registrerar
 * dock BARA "aes"-algoritmen om edc.encryption.aes.key.alias är satt OCH
 * en nyckel faktiskt finns i vaulten under det aliaset – annars: "Failed
 * to encrypt entries: Unsupported encryption algorithm: aes". Vi äger
 * båda halvorna här: seedar en slumpad AES-256-nyckel i vaulten under
 * ALIAS_INSTALLNING:s värde (samma inställning som AesEncryptionExtension
 * själv läser, satt via EDC_ENCRYPTION_AES_KEY_ALIAS i compose/.env – en
 * enda sanningskälla för aliasnamnet).
 *
 * VARFÖR prepare() OCH INTE initialize(): AesEncryptionExtension
 * REGISTRERAR "aes" i EncryptionAlgorithmRegistry i sin egen initialize().
 * Vår extension har ingen @Inject-relation till AesEncryptionExtension,
 * så ordningen mellan de två initialize()-anropen är INTE garanterad.
 * ServiceExtension#prepare() körs (per sin egen javadoc) "after all other
 * extensions are guaranteed to have completed initialization" – exakt den
 * garanti vi behöver för att "aes" garanterat redan är registrerat innan
 * vi anropar createParticipantContext (som utlöser krypteringen).
 *
 * DID-PUBLICERING – EXPLICIT, INTE IMPLICIT (UPPTÄCKT 2026-09-01,
 * verifierat live): ParticipantManifest#active(true) ANTAS (enligt
 * ParticipantContextEventCoordinators egen kodkommentar i uppströmskällan)
 * "implicitly publish the did document" via en händelsekedja:
 * ParticipantContextCreated -> nyckelpar läggs till (utlöser ett FÖRVÄNTAT
 * MISSLYCKAT tidigt publiceringsförsök, eftersom staten fortfarande är
 * CREATED) -> updateParticipant(::activate) -> ParticipantContextUpdated
 * (newState=ACTIVATED) -> DidDocumentServiceImpl.updated() -> publish().
 * Den kedjan spårades i sin helhet i uppströmskällan och SER logiskt
 * komplett ut (inga fel loggas), men fungerade INTE i praktiken: efter att
 * ha satt active(true) visade participant context korrekt state=ACTIVATED
 * (200) via API, men did-porten fortsatte svara 204 (opublicerat) även
 * flera minuter senare på samma körande container. Grundorsaken visade sig
 * INTE vara en publiceringsbugg alls, utan en testmetodik-artefakt:
 * DidWebController slår upp DID-dokumentet baserat på request-URL:ens
 * host:port, och identiteten är registrerad under containerns
 * Docker-nätverksnamn (t.ex. identity-hub-dhi:19197), inte "localhost" som
 * testerna curlade mot. Med rätt Host-header svarar båda instanserna 200
 * med ett korrekt DID-dokument. Den explicita aktiverings-/publicerings-
 * koden behölls ändå (manifestet skapas med active(false), och vi
 * anropar sedan själva, i tur och ordning: (1)
 * participantContextService.updateParticipant(id, ::activate), (2)
 * documentService.publish(did)) för tydlig, loggad felhantering i stället
 * för att förlita sig på den opaka interna händelsekedjan.
 *
 * UTFÄRDARE MED RÄTT MANDAT (docs/koncept/C1-identitet.md, "Utfärdarmodellen"):
 * stycket nedan beskriver den verifierbara DCP-identitetens förenkling där DHI:s hub utfärdade ALLA sex intyg.
 * Det gäller inte längre. Numera gäller att den som intygar något ska ha mandat att
 * intyga just det:
 *   - Svadas utfärdare (egen hub, compose.dsga.yml, svada.credential.issuer=true) signerar
 *     SvadaParticipantCredential och SvadaMembershipCredential åt DHI och Staden, och
 *     inget annat. Den utfärdar inga rollintyg och har inga egna intyg.
 *   - Varje deltagare (DHI, Staden) intygar sin EGEN roll själv: SvadaRoleCredential med den
 *     egna DID:en som både utfärdare och innehavare. Stadens roll (Kretslopp och Vatten är
 *     rättighetsinnehavare) är stadens interna rollfördelning och intygas av staden.
 *   - Deltagarna importerar medlems- och deltagarintygen från Svadas utfärdare och vägrar
 *     intyg från någon annan (svada.issuer.did).
 *   - Verifieringen godtar varje intygstyp bara från rätt utfärdare: edc.iam.trustedissuer.*
 *     .supportedtypes i edc/konfig/*.properties (EDC 0.17.0, HasValidIssuer).
 * MEDVETEN FÖRENKLING – simulerar DSGA 0.1:s tillitstjänst. Inga intyg är förankrade i
 * eIDAS. Återkallelse finns (Bitstring Status List, se StatusLista) men listan ligger i minnet.
 * Utfärdaren körs som en container
 * bredvid de andra; i målbilden driftas den av Intraservice på DSGA:s uppdrag.
 *
 * ATTEST-UTFÄRDANDE (STEG 4, docs/koncept/C1-identitet.md
 * "Tillitsramverk/utfärdare"): konceptdokumentet föreslog "en enda part
 * spelar utfärdare åt båda" som en medveten förenkling (PoC:en har ingen
 * separat "dataspace authority"-part), men lämnade det som en öppen fråga
 * HUR. Beslutet (2026-09-01): DHI:s IdentityHub-instans är i den
 * här PoC:en BÅDE deltagare OCH den delade utfärdaren – dess did:web/
 * nyckelpar signerar SAMTLIGA sex attest (tre åt sig själv, tre åt
 * Staden). Staden mintar inget själv, den bara tar emot. Detta undviker
 * att behöva en TREDJE, fristående utfärdaridentitet (som i sin tur skulle
 * behöva en egen publicerad DID för att vara verifierbar - onödig
 * komplexitet för en PoC) och undviker en tredje, ständigt körande tjänst
 * (konceptdokumentets egen restriktion).
 *
 * Det olösta praktiska problemet var HUR ett DHI-signerat attest når
 * Stadens IdentityHub-instans, givet att: (a) IdentityHubs API-nycklar
 * genereras slumpmässigt vid varje uppstart (ingen deterministisk
 * konfiguration möjlig, verifierat i IdentityHubParticipantContextServiceImpl
 * #createTokenAndStoreInVault - "apiKeyAlias" styr bara VAR nyckeln lagras,
 * inte VILKET värde den får), så DHI kan inte förutsäga Stadens API-nyckel
 * för att pusha attest dit via REST, och (b) containrarnas in-memory
 * vaults är processlokala - DHI har ingen åtkomst till Stadens privata
 * nyckelmaterial och behöver det inte heller (DHI behöver bara Stadens
 * REDAN KÄNDA, statiskt konfigurerade DID för att skriva ett attest OM
 * Staden - inte Stadens nyckel).
 *
 * Lösningen: en delad Docker-volym (SVADA_VC_UTBYTE_DIR, monterad rw hos
 * DHI och ro hos Staden - se compose.dhi.yml/compose.stad.yml). DHI
 * skriver sina tre attest åt Staden som JSON-filer i en Staden-namngiven
 * undermapp, avslutat med en tom .klar-markörfil (skriven SIST, efter alla
 * tre attest-filerna, så att Stadens läsning aldrig ser ett halvfärdigt
 * set). Staden pollar efter markörfilen vid uppstart (upp till
 * VANTA_MAX_FORSOK försök, se importeraAttestFranUtfardare) och läser sedan
 * in filerna direkt i sin egen CredentialStore - ingen REST, ingen
 * API-nyckel, inget delat nyckelmaterial. Eftersom compose.dhi.yml och
 * compose.stad.yml körs som två SEPARATA docker compose-anrop (se
 * README.md) kan "depends_on" inte uttrycka ordningen över filgränsen -
 * operatören måste starta identity-hub-dhi FÖRE identity-hub-stad (precis
 * som redan är den etablerade ordningen i alla körkommandon i det här
 * projektet), och polling-loopen är den faktiska korrekthetsgarantin, inte
 * bara ett defensivt extralager.
 *
 * RÄTTAT 2026-10-06 (startordningsberoendet): att bara
 * vänta på markörfilen räckte INTE. Volymen överlever omstarter, så när
 * alla containrar startar samtidigt (Docker-omstart, restart-policy) låg
 * förra körningens .klar kvar: Staden läste in de GAMLA attesten 0,14 s
 * innan DHI hunnit skriva nya. De är signerade med DHI:s förra nyckel
 * (nyckelparet genereras om vid varje start), och varje DSP-anrop gav
 * sedan ett tyst 401 trots att alla tjänster var "healthy". Nu gäller:
 *   - DHI tar bort den gamla markören INNAN nya attest skrivs.
 *   - Staden godtar bara attest vars signatur går att verifiera mot
 *     nyckeln i utfärdarens AKTUELLA DID-dokument (hämtat direkt, utan
 *     DID-resolverns femminuterscache) - annars fortsätter den vänta.
 * Därmed är identitetsstarten oberoende av startordningen.
 *
 * Signeringen replikerar mönstret i IdentityHubs egen (opublicerade)
 * issuerservice-issuance-modul (JwtCredentialGenerator, läst i
 * uppströmskällan för referens - modulen saknar maven-publish och kan
 * alltså inte beroendedeklareras här) med redan publicerade byggstenar:
 * JwsSignerProvider (jwt-spi, injiceras - identity-hub-core:s egen
 * DefaultServicesExtension registrerar en DefaultJwsSignerProvider som
 * @Provider(isDefault = true), så den är redan tillgänglig utan extra
 * kod) + JwtGenerationService (token-lib, instansieras direkt, ingen DI
 * behövs för själva klassen).
 *
 * Mönster i övrigt: skriv direkt till Vault/tjänsten, @Inject löser
 * beroendeordningen, paketerad som en egen, tunn jar
 * (identity-hub-bootstrap.jar) i stället för att patcha in källkod i den
 * klonade uppströms-monorepot – se identity-hub/Dockerfile.
 *
 * ===================================================================
 * STS-KLIENTHEMLIGHET (verifierbar DCP-identitet, STEG 5 - byt ut iam-mock i edc/)
 * ===================================================================
 * När edc/ byter från iam-mock till riktig DCP-verifiering måste VARJE parts EDC-connector kunna
 * begära ett självutfärdat token från sin EGEN IdentityHub-instans
 * "embedded STS" (bekräftat i STEG 2/3:s loggar). Det kräver ett OAuth2
 * client_credentials-anrop med client_id=den egna DID:en och en
 * client_secret som måste finnas i BÅDA processernas vault (IdentityHubs
 * OCH EDC-connectorns - två helt separata, processlokala vaults, se
 * samma resonemang som attest-exporten i steg 4).
 *
 * participantContextService.createParticipantContext(...) ovan skapar
 * REDAN, synkront, ett StsAccount via StsAccountProvisionerImpl
 * (uppströmskällan, identity-hub/extensions/sts/sts-account-provisioner)
 * - men med en SLUMPAD hemlighet (StsClientSecretGenerator), lagrad
 * ENDAST i IdentityHubs egen vault. I stället för att bygga ännu en
 * fil-baserad exportmekanism (som steg 4:s VC-utbyte): StsAccountService
 * #updateSecret(...) (spi/sts-spi) tillåter oss att SÄTTA en explicit,
 * deterministisk hemlighet i stället för att låta den förbli slumpad -
 * se koden nedan i prepare(). Samma deterministiska värde (läst ur
 * .env:s SVADA_STS_CLIENT_SECRET_DHI/_STAD) seedas separat in i
 * EDC-connectorns EGNA vault av se.goteborg.svada.edc.dcp.
 * SvadaDcpIdentityExtension i edc/ - en delad hemlighet via .env, exakt
 * samma medvetna förenkling som den nyckelskyddade management-API-nyckeln,
 * dokumenterad i stället för gissad.
 * ===================================================================
 */

package se.goteborg.svada.identityhub;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.eclipse.edc.iam.verifiablecredentials.spi.VcConstants;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.CredentialFormat;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.CredentialSubject;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.DataModelVersion;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.Issuer;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.VerifiableCredential;
import org.eclipse.edc.iam.verifiablecredentials.spi.model.VerifiableCredentialContainer;
import org.eclipse.edc.identityhub.spi.authentication.ServicePrincipal;
import org.eclipse.edc.identityhub.spi.did.DidDocumentService;
import org.eclipse.edc.identityhub.spi.participantcontext.IdentityHubParticipantContextService;
import org.eclipse.edc.identityhub.spi.participantcontext.model.IdentityHubParticipantContext;
import org.eclipse.edc.identityhub.spi.participantcontext.model.KeyDescriptor;
import org.eclipse.edc.identityhub.spi.participantcontext.model.ParticipantManifest;
import org.eclipse.edc.iam.did.spi.document.Service;
import org.eclipse.edc.identityhub.spi.verifiablecredentials.model.VcStatus;
import org.eclipse.edc.identityhub.spi.verifiablecredentials.model.VerifiableCredentialResource;
import org.eclipse.edc.identityhub.spi.verifiablecredentials.store.CredentialStore;
import org.eclipse.edc.iam.decentralizedclaims.sts.spi.service.StsAccountService;
import org.eclipse.edc.jwt.spi.JwtRegisteredClaimNames;
import org.eclipse.edc.jwt.spi.signer.JwsSignerProvider;
import org.eclipse.edc.runtime.metamodel.annotation.Inject;
import org.eclipse.edc.spi.monitor.Monitor;
import org.eclipse.edc.spi.result.Result;
import org.eclipse.edc.spi.security.Vault;
import org.eclipse.edc.spi.system.ServiceExtension;
import org.eclipse.edc.spi.system.ServiceExtensionContext;
import org.eclipse.edc.spi.system.configuration.Config;
import org.eclipse.edc.web.spi.WebService;
import org.eclipse.edc.token.JwtGenerationService;
import org.eclipse.edc.token.spi.KeyIdDecorator;
import org.eclipse.edc.token.spi.TokenDecorator;
import org.eclipse.edc.token.spi.TokenGenerationService;

import java.io.IOException;
import java.math.BigInteger;
import java.net.URI;
import java.net.URLDecoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.AlgorithmParameters;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.SecureRandom;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPublicKeySpec;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public class SvadaParticipantBootstrapExtension implements ServiceExtension {

    /** Konfigurationsnycklar (env: SVADA_PARTICIPANT_ID / SVADA_PARTICIPANT_DID i compose). */
    public static final String INSTALLNING_PARTICIPANT_ID = "svada.participant.id";
    public static final String INSTALLNING_DID = "svada.participant.did";

    /**
     * Samma inställningsnyckel som org.eclipse.edc.encryption.aes.AesEncryptionExtension
     * (uppströms) själv läser - se klasskommentaren ovan. Satt via
     * EDC_ENCRYPTION_AES_KEY_ALIAS i compose/.env, en enda sanningskälla.
     */
    public static final String INSTALLNING_AES_ALIAS = "edc.encryption.aes.key.alias";

    /** Steg 4 (attest-utfärdande), se klasskommentaren ovan. */
    public static final String INSTALLNING_AR_UTFARDARE = "svada.credential.issuer";
    /**
     * Utfärdare med rätt mandat (Svadas utfärdare, DSGA 0.1): utfärdaren får en lista mottagare
     * "id=did,id=did" (SVADA_ISSUER_MOTTAGARE) och mintar Participant- och
     * MembershipCredential åt var och en. Icke-utfärdarna (DHI, Staden) anger i
     * stället vilken utfärdare de litar på (SVADA_ISSUER_DID) och vägrar importera
     * intyg från någon annan.
     */
    public static final String INSTALLNING_ISSUER_MOTTAGARE = "svada.issuer.mottagare";
    public static final String INSTALLNING_ISSUER_DID = "svada.issuer.did";
    /**
     * TESTLÄGE för tests/verify_ap8_fas3.sh. Kommaseparerad lista, tom = av (standard).
     * "svada-roll": utfärdaren signerar dessutom ett RollIntyg åt mottagaren (rätt text,
     * FEL utfärdare) som mottagaren lagrar; "medlemskap-sjalvutfardat": mottagaren
     * självutfärdar dessutom ett medlemsintyg. Bara för att visa att verifieringen
     * avvisar dem. Aldrig satt i en driftsatt miljö.
     */
    public static final String INSTALLNING_TEST_NEGATIV = "svada.test.negativ";
    public static final String INSTALLNING_DATASPACE_ID = "svada.dataspace.id";
    public static final String INSTALLNING_ROLLINNEHAVARE = "svada.rollinnehavare";
    public static final String INSTALLNING_VC_UTBYTE_DIR = "svada.vc.utbyte.dir";
    /** Statuslista för återkallelse (StatusLista): listans publika adress och samordningsrollens nyckel. */
    public static final String INSTALLNING_STATUS_URL = "svada.status.list.url";
    public static final String INSTALLNING_STATUS_NYCKEL = "svada.status.admin.key";

    /** Steg 5 (DCP-identitet i EDC-connectorn), se klasskommentaren ovan. */
    public static final String INSTALLNING_STS_HEMLIGHET = "svada.sts.client.secret";

    /**
     * Steg 5 - CredentialService-tjänsteposten i DID-dokumentet.
     * Utan denna hittar motpartens edc-connector (DidCredentialServiceUrlResolver
     * i decentralized-claims-service) ingenstans att skicka sin PresentationQuery,
     * och varje DSP-anrop som kräver en verifierad presentation misslyckas med
     * "No Service endpoint 'CredentialService' found on DID Document" - upptäckt
     * som ett generiskt 401 vid steg 5:s första verifieringskörning. Satt via
     * SVADA_CREDENTIAL_SERVICE_URL i compose (egen literal per part, .env:s
     * SVADA_CREDENTIAL_SERVICE_URL_DHI/_STAD) - den HÄR partens egen
     * presentations-endpoint, byggd av WEB_HTTP_CREDENTIALS_PORT/_PATH plus
     * PresentationApiControllers fasta sökväg
     * (/v1/participants/{participantContextId}/presentations), MINUS det sista
     * "/query"-segmentet som DefaultCredentialServiceClient (uppströms,
     * connector-0.17.0) själv lägger på när den anropar denna URL.
     */
    public static final String INSTALLNING_CREDENTIAL_SERVICE_URL = "svada.credential.service.url";

    private static final int AES_256_BYTES = 32;

    private static final String TYP_DELTAGARE = "SvadaParticipantCredential";
    private static final String TYP_MEDLEMSKAP = "SvadaMembershipCredential";
    private static final String TYP_ROLL = "SvadaRoleCredential";
    private static final String VC_JWT_CLAIM = "vc";
    /** Giltighetstid för attesten: 1 år, godtyckligt val för en PoC utan förnyelseflöde. */
    private static final long GILTIGHET_SEKUNDER = 365L * 24 * 3600;
    /**
     * Hur länge DHI och Staden väntar på GILTIGA attest-filer från Svadas utfärdare - signerade med
     * utfärdarens aktuella nyckel - innan den ger upp (se klasskommentaren ovan).
     */
    // Utfärdare med rätt mandat: 150 s (var 60). Utfärdaren är nu en egen JVM, och vid en samtidig omstart av fem
    // JVM:er (utfärdare, två hubbar, två connectorer) på en dator med lite minne hann den inte bli
    // klar inom 60 s: deltagarna gav upp utan intyg (tyst 401, se 8f2.7). Hubbens hälsofönster är
    // ca 270 s (30 s start_period + 24 x 10 s), så 150 s ryms.
    private static final int VANTA_MAX_FORSOK = 150;
    private static final long VANTA_INTERVALL_MS = 1000L;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Inject
    private IdentityHubParticipantContextService participantContextService;

    @Inject
    private DidDocumentService documentService;

    @Inject
    private CredentialStore credentialStore;

    @Inject
    private StsAccountService stsAccountService;

    @Inject
    private JwsSignerProvider jwsSignerProvider;

    @Inject
    private Vault vault;

    @Inject
    private WebService webService;

    private ServiceExtensionContext contextRef;

    @Override
    public String name() {
        return "SVADA participant-bootstrap (verifierbar identitet)";
    }

    @Override
    public void initialize(ServiceExtensionContext context) {
        // Sparar bara referensen - själva arbetet görs i prepare(), se
        // klasskommentaren ovan för varför (AES-registrerings-ordningen).
        this.contextRef = context;
    }

    @Override
    public void prepare() {
        var context = contextRef;
        var monitor = context.getMonitor();
        var config = context.getConfig();

        seedAesNyckel(config, monitor);

        var participantId = config.getString(INSTALLNING_PARTICIPANT_ID, null);
        var did = config.getString(INSTALLNING_DID, null);

        if (participantId == null || did == null) {
            monitor.warning(("SVADA participant-bootstrap: %s/%s ej satta - hoppar över " +
                    "bootstrap, ingen identitet skapad.").formatted(INSTALLNING_PARTICIPANT_ID, INSTALLNING_DID));
            return;
        }

        var credentialServiceUrl = config.getString(INSTALLNING_CREDENTIAL_SERVICE_URL, null);
        // Utfärdaren (Svada) är ingen innehavare och ingen part i DSP: den behöver ingen
        // CredentialService-tjänstepost, bara en publicerad DID med sin publika nyckel.
        if (credentialServiceUrl == null && !config.getBoolean(INSTALLNING_AR_UTFARDARE, false)) {
            monitor.warning(("SVADA participant-bootstrap: %s ej satt - det publicerade " +
                    "DID-dokumentet kommer sakna en CredentialService-tjänstepost, och " +
                    "motparten kommer inte hitta var den ska begära en Verifiable " +
                    "Presentation (DSP-anrop kommer misslyckas med 401).")
                    .formatted(INSTALLNING_CREDENTIAL_SERVICE_URL));
        }

        var existing = participantContextService.getParticipantContext(participantId);
        if (existing.succeeded()) {
            monitor.info(("SVADA participant-bootstrap: participant context '%s' finns redan " +
                    "(in-memory-lagret överlevde alltså omstarten, eller detta är andra " +
                    "anropet) - skapar inte om, och rör inte publicering/attest igen.").formatted(participantId));
            return;
        }

        // EC/secp256r1: samma nyckeltyp IdentityHubs egen testsvit och
        // JsonWebKey2020-standarden (KeyDescriptor.Builder default) bygger på.
        var privatnyckelAlias = participantId + "-privatnyckel";
        // Steg 5 (felsökning 401 på DSP-katalogfrågan): key-ID:t MÅSTE vara den FULLA
        // DID-URL:en (did:...#fragment), inte bara kortnamnet
        // ("dhi-nyckel-1") - DidPublicKeyResolverImpl (uppströms,
        // identity-did-core) kräver att JWT:ns "kid"-header matchar mönstret
        // 'did:method:identifier[:fragment]' REDAN vid sin första regex-
        // kontroll, INNAN den ens slår upp DID-dokumentet och jämför mot
        // dess verificationMethod-id. IdentityHubs inbyggda STS signerar
        // self-issued-tokens med EXAKT detta key-ID rakt av (utan att själv
        // lägga på DID-prefixet), så kortnamnet gav "No public key could be
        // resolved" vid varje verifierat DSP-anrop. Samma mönster som redan
        // användes korrekt för attest-signering nedan (se composedKeyId i
        // mintaAttest) - byggs nu likadant här, en gång, för konsekvens.
        var fulltKeyId = did + "#" + verifieringsNyckelId(participantId);
        var nyckel = KeyDescriptor.Builder.newInstance()
                .keyId(fulltKeyId)
                .privateKeyAlias(privatnyckelAlias)
                .keyGeneratorParams(Map.of("algorithm", "EC", "curve", "secp256r1"))
                .build();

        var tjansteposter = credentialServiceUrl == null
                ? Set.<Service>of()
                : Set.of(new Service(did + "#credential-service", "CredentialService", credentialServiceUrl));

        var manifest = ParticipantManifest.Builder.newInstance()
                .participantContextId(participantId)
                .did(did)
                .key(nyckel)
                .roles(List.of(ServicePrincipal.ROLE_ADMIN))
                // Steg 5: se INSTALLNING_CREDENTIAL_SERVICE_URL ovan.
                // DidDocument.service byggs ENDAST från manifest.getServiceEndpoints()
                // (ParticipantContextEventCoordinator, uppströms) - sätts INTE av
                // aktiverings-/publiceringsstegen nedan, måste alltså vara med här,
                // vid participant context-SKAPANDET.
                .serviceEndpoints(tjansteposter)
                // active(false): vi aktiverar och publicerar EXPLICIT själva nedan
                // i stället för att lita på den inbyggda implicita kedjan - se
                // klasskommentaren ovan ("DID-PUBLICERING - EXPLICIT, INTE IMPLICIT").
                .active(false)
                .build();

        var skapaResultat = participantContextService.createParticipantContext(manifest);
        if (skapaResultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades skapa participant " +
                    "context '%s': %s").formatted(participantId, skapaResultat.getFailureDetail()));
            return;
        }

        var svar = skapaResultat.getContent();
        // VARNING-nivå (inte INFO) med avsikt: nyckeln visas ENDAST här, en gång,
        // och måste fångas ur loggen manuellt i PoC:en (jfr identity-api.security.md
        // §3.2: "the initial API key must be transmitted ... in a secure out-of-band
        // channel" - loggen ÄR den kanalen i den här utvecklingsmiljön).
        monitor.warning(("""
                SVADA participant-bootstrap: skapade participant context '%s' (did %s).
                API-NYCKEL (spara den nu - visas bara vid den här uppstarten): %s
                """).formatted(participantId, did, svar.apiKey()));

        var aktiveraResultat = participantContextService.updateParticipant(participantId,
                IdentityHubParticipantContext::activate);
        if (aktiveraResultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades aktivera participant " +
                    "context '%s': %s - DID-dokumentet publiceras INTE.")
                    .formatted(participantId, aktiveraResultat.getFailureDetail()));
            return;
        }
        monitor.info(("SVADA participant-bootstrap: participant context '%s' aktiverad (state=ACTIVATED)."
        ).formatted(participantId));

        var publiceraResultat = documentService.publish(did);
        if (publiceraResultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades publicera DID-dokumentet " +
                    "'%s': %s").formatted(did, publiceraResultat.getFailureDetail()));
            return;
        }
        monitor.info(("SVADA participant-bootstrap: DID-dokumentet '%s' publicerat.").formatted(did));

        // --- Steg 5: deterministisk STS-klienthemlighet. ---
        // participantContextService.createParticipantContext(...) ovan har REDAN
        // (synkront, i samma transaktion, se StsAccountProvisionerImpl/
        // IdentityHubParticipantContextServiceImpl#createParticipantContext i
        // uppströmskällan) skapat ett StsAccount med en SLUMPAD klienthemlighet,
        // lagrad i IdentityHubs EGEN vault. Den hemligheten kan inte läsas av
        // EDC-connectorn i det andra containern (processlokal vault, samma skäl
        // som gjorde attest-exporten i steg 4 nödvändig). I stället för att
        // bygga ÄNNU en fil-baserad exportmekanism: skriv över den slumpade
        // hemligheten med ett VÄRDE VI SJÄLVA VÄLJER (StsAccountService#
        // updateSecret tillåter en explicit newSecret, inte bara en
        // nygenererad) - samma deterministiska värde sätts i EDC-connectorns
        // EGNA vault av en liten seed-extension där (se
        // se.goteborg.svada.edc.dcp.SvadaDcpIdentityExtension), båda lästa ur
        // SAMMA .env-variabel (SVADA_STS_CLIENT_SECRET_DHI/_STAD). Exakt samma
        // "delad hemlighet via .env"-mönster som redan används för management-API-nyckeln
        // - en medveten förenkling, men en DOKUMENTERAD
        // sådan, i stället för en tyst gissning om att slumpvärdet av misstag
        // skulle stämma överens mellan två processer.
        var stsHemlighet = config.getString(INSTALLNING_STS_HEMLIGHET, null);
        if (stsHemlighet == null) {
            monitor.warning(("SVADA participant-bootstrap: %s ej satt - EDC-connectorn på " +
                    "den här sidan kan INTE autentisera mot STS:en (behåller IdentityHubs " +
                    "slumpade hemlighet, som ingen annan process känner till).")
                    .formatted(INSTALLNING_STS_HEMLIGHET));
        } else {
            // ParticipantManifest#clientSecretAlias() (uppströmskällan) - defaultformeln
            // när ingen "clientSecret"-additionalProperty satts vid manifest-bygget ovan
            // (vilket vi medvetet INTE gör): participantContextId + "-sts-client-secret".
            var stsAlias = participantId + "-sts-client-secret";
            var stsResultat = stsAccountService.updateSecret(participantId, participantId, stsAlias, stsHemlighet);
            if (stsResultat.failed()) {
                monitor.severe(("SVADA participant-bootstrap: misslyckades sätta deterministisk " +
                        "STS-klienthemlighet för '%s' (alias '%s'): %s").formatted(
                        participantId, stsAlias, stsResultat.getFailureDetail()));
            } else {
                monitor.info(("SVADA participant-bootstrap: deterministisk STS-klienthemlighet " +
                        "satt (alias '%s').").formatted(stsAlias));
            }
        }

        // --- Steg 4: attest-utfärdande, se klasskommentaren ovan. ---
        // OBS (rättad bugg): mintaOchLagraEgnaAttest() fick INTE anropas
        // ovillkorligt här - det gjorde att Stad (arUtfardare=false) både
        // självutfärdade sina egna tre attest OCH importerade DHI:s
        // signerade attest, dvs. dubblerade attest. Med utfärdare med rätt mandat gäller i stället: Svadas
        // utfärdare mintar medlems- och deltagarintygen; DHI och Staden
        // mintar bara sitt EGET rollintyg och importerar de två andra.
        // Självutfärdandet hör hemma i respektive gren nedan.
        var dataspaceId = config.getString(INSTALLNING_DATASPACE_ID, "svada");
        var egenRollinnehavare = config.getString(INSTALLNING_ROLLINNEHAVARE, participantId);
        var arUtfardare = config.getBoolean(INSTALLNING_AR_UTFARDARE, false);
        var utbytesDir = config.getString(INSTALLNING_VC_UTBYTE_DIR, null);
        var testNegativ = config.getString(INSTALLNING_TEST_NEGATIV, "");

        if (arUtfardare) {
            // Utfärdare med rätt mandat: Svadas utfärdare (samordningsrollen). Mintar Participant- och
            // MembershipCredential åt varje mottagare och exporterar dem till utbytesvolymen.
            // Mintar inga egna intyg och INGA rollintyg: rollen intygar organisationen själv.
            var mottagare = tolkaMottagare(config.getString(INSTALLNING_ISSUER_MOTTAGARE, null));
            var statusUrl = config.getString(INSTALLNING_STATUS_URL, null);
            if (statusUrl != null && !mottagare.isEmpty()) {
                // Statuslistan måste vara konfigurerad INNAN intygen mintas: varje intyg får sitt index.
                var statusLista = StatusLista.instans();
                statusLista.konfigurera(statusUrl, () -> signeraStatuslista(participantId, privatnyckelAlias, did,
                        statusUrl, statusLista.kodad()), mottagare);
                webService.registerResource("did", new StatusListPublik(statusLista));
                webService.registerResource("did", new StatusListController(statusLista,
                        config.getString(INSTALLNING_STATUS_NYCKEL, null), monitor));
                monitor.info("SVADA participant-bootstrap: statuslista för återkallelse aktiv på " + statusUrl);
            }
            if (mottagare.isEmpty() || utbytesDir == null) {
                monitor.warning(("SVADA participant-bootstrap: %s=true men %s/%s saknas - " +
                        "hoppar över export av intyg.").formatted(INSTALLNING_AR_UTFARDARE,
                        INSTALLNING_ISSUER_MOTTAGARE, INSTALLNING_VC_UTBYTE_DIR));
            } else {
                mintaOchExporteraTillMottagare(monitor, participantId, privatnyckelAlias, did, mottagare,
                        dataspaceId, utbytesDir, testNegativ, egenRollinnehavare);
            }
        } else if (utbytesDir != null) {
            // Deltagare (DHI, Staden): intygar SIN EGEN roll själv (utfärdare och innehavare är
            // samma DID) och tar emot medlems- och deltagarintygen från Svadas utfärdare.
            mintaOchLagra(monitor, participantId, privatnyckelAlias, did, did, TYP_ROLL,
                    Map.of("role", egenRollinnehavare), Instant.now());
            if (testNegativ.contains("medlemskap-sjalvutfardat")) {
                // TESTLÄGE: ett medlemsintyg som deltagaren själv har utfärdat. Verifieringen ska avvisa det.
                monitor.warning("SVADA participant-bootstrap: TESTLÄGE medlemskap-sjalvutfardat - självutfärdar ett medlemsintyg.");
                mintaOchLagra(monitor, participantId, privatnyckelAlias, did, did, TYP_MEDLEMSKAP,
                        Map.of("dataspaceId", dataspaceId), Instant.now());
            }
            importeraAttestFranUtfardare(monitor, participantId, utbytesDir,
                    config.getBoolean("edc.iam.did.web.use.https", true),
                    config.getString(INSTALLNING_ISSUER_DID, null), testNegativ);
        } else {
            // Varken utfärdare-flaggan eller en utbytes-katalog är satt
            // (t.ex. fristående utveckling/test utan den delade volymen) -
            // fall tillbaka till att självutfärda. OBS: med de
            // supportedtypes avvisar en verifierare ett självutfärdat
            // medlems- eller deltagarintyg, så grenen duger bara för
            // fristående utveckling.
            mintaOchLagraEgnaAttest(monitor, participantId, privatnyckelAlias, did, dataspaceId, egenRollinnehavare);
        }
    }

    /** "dhi=did:web:a%3A1,stad=did:web:b%3A2" -> {dhi: did, stad: did}. */
    private static Map<String, String> tolkaMottagare(String lista) {
        var mottagare = new LinkedHashMap<String, String>();
        if (lista == null || lista.isBlank()) {
            return mottagare;
        }
        for (var post : lista.split(",")) {
            var i = post.indexOf('=');
            if (i > 0 && i < post.length() - 1) {
                mottagare.put(post.substring(0, i).trim(), post.substring(i + 1).trim());
            }
        }
        return mottagare;
    }

    private String verifieringsNyckelId(String participantId) {
        return participantId + "-nyckel-1";
    }

    private void seedAesNyckel(Config config, Monitor monitor) {
        var alias = config.getString(INSTALLNING_AES_ALIAS, null);
        if (alias == null) {
            monitor.warning(("SVADA participant-bootstrap: %s ej satt - AES-krypteringen är " +
                    "inte registrerad och participant-context-skapandet kommer att misslyckas " +
                    "(ParticipantContextConfigService kräver AES som default, se " +
                    "klasskommentaren i SvadaParticipantBootstrapExtension.java).")
                    .formatted(INSTALLNING_AES_ALIAS));
            return;
        }
        if (vault.resolveSecret(alias) != null) {
            // Redan seedad (t.ex. om prepare() av någon anledning körs mer än en gång).
            return;
        }
        var nyckelBytes = new byte[AES_256_BYTES];
        new SecureRandom().nextBytes(nyckelBytes);
        var base64Nyckel = Base64.getEncoder().encodeToString(nyckelBytes);
        var resultat = vault.storeSecret(alias, base64Nyckel);
        if (resultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: kunde inte lagra AES-nyckeln i " +
                    "vaulten (alias '%s'): %s").formatted(alias, resultat.getFailureDetail()));
        } else {
            monitor.info(("SVADA participant-bootstrap: slumpad AES-256-nyckel lagrad i " +
                    "vaulten under alias '%s' (in-memory, ny vid varje omstart).").formatted(alias));
        }
    }


    // =========================================================================================
    // Steg 4: attest-utfärdande. Se klasskommentaren högst upp i filen för det fulla
    // resonemanget bakom design­valen (delad utfärdare, delad volym i stället för REST/API-nyckel).
    // =========================================================================================

    /** Ett i-minnet, signerat attest - innan det antingen lagras lokalt eller exporteras till en fil. */
    private record SigneratAttest(VerifiableCredential vc, String rawJwt) {
    }

    /** JSON-formatet Svadas utfärdare skriver till den delade volymen, och DHI och Staden läser tillbaka. */
    private record ExporteradAttest(String id, String rawJwt, String typ, String issuerId, String subjectId,
                                     Map<String, Object> claims, String utfardad, String utgangsdatum) {
    }

    private void mintaOchLagraEgnaAttest(Monitor monitor, String participantId, String privatnyckelAlias,
                                          String did, String dataspaceId, String rollinnehavare) {
        var nu = Instant.now();
        mintaOchLagra(monitor, participantId, privatnyckelAlias, did, did, TYP_DELTAGARE,
                Map.of("participantId", participantId), nu);
        mintaOchLagra(monitor, participantId, privatnyckelAlias, did, did, TYP_MEDLEMSKAP,
                Map.of("dataspaceId", dataspaceId), nu);
        mintaOchLagra(monitor, participantId, privatnyckelAlias, did, did, TYP_ROLL,
                Map.of("role", rollinnehavare), nu);
    }

    private void mintaOchLagra(Monitor monitor, String utfardarParticipantId, String utfardarPrivatnyckelAlias,
                                String utfardarDid, String subjektDid, String typ, Map<String, Object> claims,
                                Instant nu) {
        var resultat = mintaAttest(utfardarParticipantId, utfardarPrivatnyckelAlias, utfardarDid, subjektDid, typ, claims, nu);
        if (resultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades minta %s för '%s': %s")
                    .formatted(typ, subjektDid, resultat.getFailureDetail()));
            return;
        }
        var attest = resultat.getContent();
        var container = new VerifiableCredentialContainer(attest.rawJwt(), CredentialFormat.VC1_0_JWT, attest.vc());
        var lagringsResultat = credentialStore.create(VerifiableCredentialResource.Builder.newHolder()
                .id(attest.vc().getId())
                .participantContextId(utfardarParticipantId)
                .issuerId(utfardarDid)
                .holderId(subjektDid)
                .state(VcStatus.ISSUED)
                .credential(container)
                .build());
        if (lagringsResultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades lagra %s för '%s' i CredentialStore: %s")
                    .formatted(typ, subjektDid, lagringsResultat.getFailureDetail()));
        } else {
            monitor.info(("SVADA participant-bootstrap: %s utfärdat och lagrat (subjekt %s, utfärdare %s).")
                    .formatted(typ, subjektDid, utfardarDid));
        }
    }

    private void mintaOchExporteraTillMottagare(Monitor monitor, String egetParticipantId, String egetPrivatnyckelAlias,
                                                 String egetDid, Map<String, String> mottagare, String dataspaceId,
                                                 String utbytesDir, String testNegativ, String testRoll) {
        for (var post : mottagare.entrySet()) {
            var mottagarId = post.getKey();
            var mottagarDid = post.getValue();
            var nu = Instant.now();
            try {
                var katalog = Path.of(utbytesDir, mottagarId);
                Files.createDirectories(katalog);
                // Förra körningens markör bort FÖRST: intygen nedan signeras med
                // ett nytt nyckelpar, och en kvarlämnad .klar får inte locka
                // mottagaren att läsa de gamla filerna (eller en blandning).
                Files.deleteIfExists(katalog.resolve(".klar"));
                Files.deleteIfExists(katalog.resolve("testroll.json"));
                // Volymen överlever omstarter och modellbyten: i den tidigare DCP-varianten exporterade DHI ett
                // rollintyg (roll.json). Utfärdaren utfärdar inga rollintyg, så en kvarlämnad
                // fil från den gamla modellen tas bort i stället för att ligga kvar och förvirra.
                Files.deleteIfExists(katalog.resolve("roll.json"));

                exporteraTillFil(monitor, katalog, "deltagare", egetParticipantId, egetPrivatnyckelAlias, egetDid,
                        mottagarDid, TYP_DELTAGARE, Map.of("participantId", mottagarId), nu);
                exporteraTillFil(monitor, katalog, "medlemskap", egetParticipantId, egetPrivatnyckelAlias, egetDid,
                        mottagarDid, TYP_MEDLEMSKAP, Map.of("dataspaceId", dataspaceId), nu);
                if (testNegativ.contains("svada-roll")) {
                    // TESTLÄGE: ett rollintyg med RÄTT text men FEL utfärdare (Svada). Utfärdaren
                    // ska aldrig utfärda rollintyg, och verifieringen ska avvisa det.
                    monitor.warning("SVADA participant-bootstrap: TESTLÄGE svada-roll - utfärdar ett rollintyg åt '"
                            + mottagarId + "' som Svada INTE har mandat att utfärda.");
                    exporteraTillFil(monitor, katalog, "testroll", egetParticipantId, egetPrivatnyckelAlias, egetDid,
                            mottagarDid, TYP_ROLL, Map.of("role", testRoll), nu);
                }

                // Markörfilen skrivs SIST, efter alla intygsfiler, så att mottagarens
                // polling (importeraAttestFranUtfardare) aldrig kan se ett halvfärdigt set.
                Files.writeString(katalog.resolve(".klar"), Instant.now().toString());
                monitor.info(("SVADA participant-bootstrap: två attest (deltagare, medlemskap) exporterade till " +
                        "'%s' åt '%s' (%s).").formatted(katalog, mottagarId, mottagarDid));
            } catch (IOException e) {
                monitor.severe(("SVADA participant-bootstrap: kunde inte skriva attest-filer till delade volymen " +
                        "'%s' åt '%s': %s").formatted(utbytesDir, mottagarId, e.getMessage()));
            }
        }
    }

    private void exporteraTillFil(Monitor monitor, Path peerKatalog, String filnamn, String utfardarParticipantId,
                                   String utfardarPrivatnyckelAlias, String utfardarDid, String subjektDid,
                                   String typ, Map<String, Object> claims, Instant nu) throws IOException {
        var resultat = mintaAttest(utfardarParticipantId, utfardarPrivatnyckelAlias, utfardarDid, subjektDid, typ, claims, nu);
        if (resultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades minta %s åt motparten '%s': %s")
                    .formatted(typ, subjektDid, resultat.getFailureDetail()));
            return;
        }
        var attest = resultat.getContent();
        var dto = new ExporteradAttest(attest.vc().getId(), attest.rawJwt(), typ, utfardarDid, subjektDid,
                claims, attest.vc().getIssuanceDate().toString(), attest.vc().getExpirationDate().toString());
        objectMapper.writerWithDefaultPrettyPrinter().writeValue(peerKatalog.resolve(filnamn + ".json").toFile(), dto);
    }

    private void importeraAttestFranUtfardare(Monitor monitor, String egetParticipantId, String utbytesDir,
                                              boolean didWebHttps, String forvantadUtfardarDid,
                                              String testNegativ) {
        var egenKatalog = Path.of(utbytesDir, egetParticipantId);
        var markor = egenKatalog.resolve(".klar");

        // Vänta tills det finns ett KOMPLETT set attest som dessutom är
        // signerat med utfärdarens aktuella nyckel. Bara "markören finns"
        // räcker inte - den kan vara kvar från en tidigare körning.
        List<ExporteradAttest> attest = null;
        String senasteSkal = "markörfilen '%s' finns inte".formatted(markor);
        var skalLoggat = false;
        for (var forsok = 0; forsok < VANTA_MAX_FORSOK; forsok++) {
            if (Files.exists(markor)) {
                var kandidat = lasAttestFiler(egenKatalog);
                senasteSkal = kandidat == null
                        ? "attest-filerna i '%s' går inte att läsa (skrivs troligen just nu)".formatted(egenKatalog)
                        : verifieraMotUtfardarensNyckel(kandidat, didWebHttps, forvantadUtfardarDid);
                if (kandidat != null && senasteSkal == null) {
                    attest = kandidat;
                    break;
                }
                if (!skalLoggat) {
                    monitor.info("SVADA participant-bootstrap: väntar på giltiga attest från utfärdaren - " + senasteSkal);
                    skalLoggat = true;
                }
            }
            try {
                Thread.sleep(VANTA_INTERVALL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                monitor.warning("SVADA participant-bootstrap: avbruten under väntan på utfärdarens attest-filer.");
                return;
            }
        }
        if (attest == null) {
            monitor.severe(("SVADA participant-bootstrap: väntade %d sekunder på giltiga attest från utfärdaren " +
                    "(Svada) men fick inga - %s. Inga importerade attest: DSP-anrop kommer att nekas (401) tills " +
                    "utfärdaren är uppe och den här instansen startats om.")
                    .formatted(VANTA_MAX_FORSOK * VANTA_INTERVALL_MS / 1000, senasteSkal));
            return;
        }

        for (var dto : attest) {
            lagraImporterat(monitor, egetParticipantId, dto);
        }

        if (testNegativ.contains("svada-roll")) {
            // TESTLÄGE: ta emot ett rollintyg som Svada (fel utfärdare) har signerat. Det är signerat
            // med utfärdarens riktiga nyckel; det som ska avvisa det är verifieringen, inte importen.
            try {
                var testroll = egenKatalog.resolve("testroll.json");
                if (Files.exists(testroll)) {
                    monitor.warning("SVADA participant-bootstrap: TESTLÄGE svada-roll - lagrar ett rollintyg utfärdat av Svada.");
                    lagraImporterat(monitor, egetParticipantId,
                            objectMapper.readValue(testroll.toFile(), ExporteradAttest.class));
                }
            } catch (IOException e) {
                monitor.severe("SVADA participant-bootstrap: kunde inte läsa testroll.json: " + e.getMessage());
            }
        }
    }

    private void lagraImporterat(Monitor monitor, String egetParticipantId, ExporteradAttest dto) {
        var amne = CredentialSubject.Builder.newInstance()
                .id(dto.subjectId())
                .claims(dto.claims())
                .build();
        var vc = VerifiableCredential.Builder.newInstance()
                .id(dto.id())
                .context(VcConstants.W3C_CREDENTIALS_URL)
                .issuer(new Issuer(dto.issuerId()))
                .dataModelVersion(DataModelVersion.V_1_1)
                .issuanceDate(Instant.parse(dto.utfardad()))
                .expirationDate(Instant.parse(dto.utgangsdatum()))
                .types(List.of("VerifiableCredential", dto.typ()))
                .credentialSubject(amne)
                .build();
        var container = new VerifiableCredentialContainer(dto.rawJwt(), CredentialFormat.VC1_0_JWT, vc);
        var lagringsResultat = credentialStore.create(VerifiableCredentialResource.Builder.newHolder()
                .id(dto.id())
                .participantContextId(egetParticipantId)
                .issuerId(dto.issuerId())
                .holderId(dto.subjectId())
                .state(VcStatus.ISSUED)
                .credential(container)
                .build());
        if (lagringsResultat.failed()) {
            monitor.severe(("SVADA participant-bootstrap: misslyckades lagra importerat %s: %s")
                    .formatted(dto.typ(), lagringsResultat.getFailureDetail()));
        } else {
            monitor.info(("SVADA participant-bootstrap: %s importerat från utfärdaren och lagrat.")
                    .formatted(dto.typ()));
        }
    }

    /** Läser de två attest-filerna (deltagare, medlemskap). Returnerar null om någon saknas eller är halvskriven. */
    private List<ExporteradAttest> lasAttestFiler(Path katalog) {
        var attest = new ArrayList<ExporteradAttest>();
        for (var filnamn : List.of("deltagare", "medlemskap")) {
            try {
                attest.add(objectMapper.readValue(katalog.resolve(filnamn + ".json").toFile(), ExporteradAttest.class));
            } catch (IOException e) {
                return null;
            }
        }
        return attest;
    }

    /**
     * Kontrollerar att varje attest (VC-JWT, ES256) är signerat med en nyckel som står i
     * utfärdarens AKTUELLA DID-dokument. Returnerar null om alla stämmer, annars skälet
     * (för loggen). DID-dokumentet hämtas direkt över HTTP - inte via DID-resolvern, vars
     * femminuterscache annars kunde ge ett gammalt dokument.
     */
    private String verifieraMotUtfardarensNyckel(List<ExporteradAttest> attest, boolean didWebHttps,
                                                  String forvantadUtfardarDid) {
        try {
            var utfardarDid = attest.get(0).issuerId();
            // Utfärdare med rätt mandat: bara intyg från den utfärdare vi litar på (Svada) tas emot. Intyg som
            // är signerade av någon annan, hur giltiga de än är i sig, väntar vi inte på.
            if (forvantadUtfardarDid != null) {
                for (var a : attest) {
                    if (!forvantadUtfardarDid.equals(a.issuerId())) {
                        return "%s är utfärdat av '%s', men förväntad utfärdare är '%s'"
                                .formatted(a.typ(), a.issuerId(), forvantadUtfardarDid);
                    }
                }
            }
            var nycklar = hamtaDidNycklar(utfardarDid, didWebHttps);
            for (var a : attest) {
                var delar = a.rawJwt().split("\\.");
                if (delar.length != 3) {
                    return "%s är inte en signerad JWT".formatted(a.typ());
                }
                var huvud = objectMapper.readTree(Base64.getUrlDecoder().decode(delar[0]));
                if (!"ES256".equals(huvud.path("alg").asText())) {
                    return "%s har oväntad signaturalgoritm '%s'".formatted(a.typ(), huvud.path("alg").asText());
                }
                var nyckel = nycklar.get(huvud.path("kid").asText());
                if (nyckel == null) {
                    return "%s pekar på nyckeln '%s', som inte finns i utfärdarens DID-dokument"
                            .formatted(a.typ(), huvud.path("kid").asText());
                }
                // JWS ES256 = R||S (IEEE P1363), inte DER.
                var signatur = Signature.getInstance("SHA256withECDSAinP1363Format");
                signatur.initVerify(nyckel);
                signatur.update((delar[0] + "." + delar[1]).getBytes(StandardCharsets.US_ASCII));
                if (!signatur.verify(Base64.getUrlDecoder().decode(delar[2]))) {
                    return ("%s på volymen är signerat med en ÄLDRE nyckel än den i utfärdarens DID-dokument " +
                            "(kvarlämnat från en tidigare körning) - väntar på nya").formatted(a.typ());
                }
            }
            return null;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return "avbruten";
        } catch (Exception e) {
            return "utfärdarens DID-dokument kunde inte hämtas eller tolkas ännu (%s)".formatted(e.getMessage());
        }
    }

    /** Hämtar ett did:web-dokument och returnerar dess EC P-256-nycklar, kid -> publik nyckel. */
    private Map<String, PublicKey> hamtaDidNycklar(String did, boolean https) throws Exception {
        var klient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
        var svar = klient.send(HttpRequest.newBuilder(URI.create(didWebTillUrl(did, https)))
                .timeout(Duration.ofSeconds(3)).GET().build(), HttpResponse.BodyHandlers.ofString());
        if (svar.statusCode() != 200) {
            throw new IOException("HTTP " + svar.statusCode());
        }
        var kurva = AlgorithmParameters.getInstance("EC");
        kurva.init(new ECGenParameterSpec("secp256r1"));
        var kurvparametrar = kurva.getParameterSpec(ECParameterSpec.class);

        var nycklar = new LinkedHashMap<String, PublicKey>();
        for (var metod : objectMapper.readTree(svar.body()).path("verificationMethod")) {
            var jwk = metod.path("publicKeyJwk");
            if (!"EC".equals(jwk.path("kty").asText()) || !"P-256".equals(jwk.path("crv").asText())) {
                continue;
            }
            var punkt = new ECPoint(
                    new BigInteger(1, Base64.getUrlDecoder().decode(jwk.path("x").asText())),
                    new BigInteger(1, Base64.getUrlDecoder().decode(jwk.path("y").asText())));
            nycklar.put(metod.path("id").asText(),
                    KeyFactory.getInstance("EC").generatePublic(new ECPublicKeySpec(punkt, kurvparametrar)));
        }
        return nycklar;
    }

    /** did:web:vard%3Aport[:sokvag...] -> http(s)://vard:port/.well-known/did.json (eller /sokvag/did.json). */
    static String didWebTillUrl(String did, boolean https) {
        var delar = did.substring("did:web:".length()).split(":");
        var vard = URLDecoder.decode(delar[0], StandardCharsets.UTF_8);
        var sokvag = delar.length == 1
                ? "/.well-known/did.json"
                : "/" + String.join("/", Arrays.copyOfRange(delar, 1, delar.length)) + "/did.json";
        return (https ? "https://" : "http://") + vard + sokvag;
    }

    /**
     * Bygger och signerar ett W3C Verifiable Credential som en JWT, enligt samma mönster som
     * IdentityHubs egen (opublicerade) JwtCredentialGenerator - se klasskommentaren högst upp.
     */
    private Result<SigneratAttest> mintaAttest(String utfardarParticipantId, String utfardarPrivatnyckelAlias,
                                                String utfardarDid, String subjektDid, String typ,
                                                Map<String, Object> claims, Instant nu) {
        var amne = CredentialSubject.Builder.newInstance()
                .id(subjektDid)
                .claims(claims)
                .build();

        var utgangsdatum = nu.plusSeconds(GILTIGHET_SEKUNDER);
        var vc = VerifiableCredential.Builder.newInstance()
                .id("urn:uuid:" + UUID.randomUUID())
                .context(VcConstants.W3C_CREDENTIALS_URL)
                .issuer(new Issuer(utfardarDid))
                .dataModelVersion(DataModelVersion.V_1_1)
                .issuanceDate(nu)
                .expirationDate(utgangsdatum)
                .types(List.of("VerifiableCredential", typ))
                .credentialSubject(amne)
                .build();

        TokenGenerationService tokenGenerationService = new JwtGenerationService(jwsSignerProvider);
        var composedKeyId = utfardarDid + "#" + verifieringsNyckelId(utfardarParticipantId);

        TokenDecorator vcDecorator = builder -> builder
                .claims(JwtRegisteredClaimNames.ISSUER, utfardarDid)
                .claims(JwtRegisteredClaimNames.SUBJECT, subjektDid)
                .claims(JwtRegisteredClaimNames.ISSUED_AT, Date.from(nu))
                .claims(JwtRegisteredClaimNames.NOT_BEFORE, Date.from(nu))
                .claims(JwtRegisteredClaimNames.EXPIRATION_TIME, Date.from(utgangsdatum))
                .claims(JwtRegisteredClaimNames.JWT_ID, UUID.randomUUID().toString())
                .claims(VC_JWT_CLAIM, byggVcClaim(vc, typ));

        var tokenResultat = tokenGenerationService.generate(utfardarParticipantId, utfardarPrivatnyckelAlias,
                vcDecorator, new KeyIdDecorator(composedKeyId));

        if (tokenResultat.failed()) {
            return Result.failure("Kunde inte signera %s (utfärdare %s): %s"
                    .formatted(typ, utfardarDid, tokenResultat.getFailureDetail()));
        }
        return Result.success(new SigneratAttest(vc, tokenResultat.getContent().getToken()));
    }

    /** Bygger den inbäddade "vc"-claimen i JWT-representationen, enligt W3C VC-JWT-konventionen. */
    private Map<String, Object> byggVcClaim(VerifiableCredential vc, String typ) {
        var subjektClaims = new LinkedHashMap<>(vc.getCredentialSubject().get(0).getClaims());
        subjektClaims.put("id", vc.getCredentialSubject().get(0).getId());

        var claim = new LinkedHashMap<String, Object>();
        claim.put("@context", vc.getContext());
        claim.put("type", List.of("VerifiableCredential", typ));
        claim.put("id", vc.getId());
        claim.put("issuanceDate", vc.getIssuanceDate().toString());
        claim.put("expirationDate", vc.getExpirationDate().toString());
        claim.put("issuer", vc.getIssuer().id());
        claim.put("credentialSubject", subjektClaims);
        // Återkallelse: medlems- och deltagarintyg som Svadas utfärdare utfärdar åt någon annan pekar på
        // utfärdarens statuslista. Rollintygen (organisationens eget) och självutfärdade intyg gör det inte.
        var status = StatusLista.instans();
        var subjektId = vc.getCredentialSubject().get(0).getId();
        if (status.aktiv() && !vc.getIssuer().id().equals(subjektId)
                && (TYP_DELTAGARE.equals(typ) || TYP_MEDLEMSKAP.equals(typ))) {
            var i = status.indexFor(subjektId, typ);
            var post = new LinkedHashMap<String, Object>();
            post.put("id", status.url() + "#" + i);
            post.put("type", "BitstringStatusListEntry");
            post.put("statusPurpose", "revocation");
            post.put("statusListIndex", String.valueOf(i));
            post.put("statusListCredential", status.url());
            claim.put("credentialStatus", post);
        }
        return claim;
    }

    /**
     * Statuslisteintyget (BitstringStatusListCredential) som en JWT, signerad med utfärdarens nyckel på
     * samma sätt som övriga intyg. Signeras vid varje hämtning, så att en ändrad bit syns direkt.
     */
    private String signeraStatuslista(String utfardarParticipantId, String utfardarPrivatnyckelAlias,
                                       String utfardarDid, String listUrl, String kodadLista) {
        var nu = Instant.now();
        var utgang = nu.plusSeconds(3600);
        var amne = new LinkedHashMap<String, Object>();
        amne.put("id", listUrl + "#list");
        amne.put("type", "BitstringStatusList");
        amne.put("statusPurpose", "revocation");
        amne.put("encodedList", kodadLista);
        var claim = new LinkedHashMap<String, Object>();
        claim.put("@context", List.of(VcConstants.W3C_CREDENTIALS_URL));
        claim.put("type", List.of("VerifiableCredential", "BitstringStatusListCredential"));
        claim.put("id", listUrl);
        claim.put("issuer", utfardarDid);
        claim.put("issuanceDate", nu.toString());
        claim.put("expirationDate", utgang.toString());
        claim.put("credentialSubject", amne);

        TokenGenerationService tokenGenerationService = new JwtGenerationService(jwsSignerProvider);
        var composedKeyId = utfardarDid + "#" + verifieringsNyckelId(utfardarParticipantId);
        TokenDecorator decorator = builder -> builder
                .claims(JwtRegisteredClaimNames.ISSUER, utfardarDid)
                .claims(JwtRegisteredClaimNames.SUBJECT, listUrl)
                .claims(JwtRegisteredClaimNames.ISSUED_AT, Date.from(nu))
                .claims(JwtRegisteredClaimNames.NOT_BEFORE, Date.from(nu))
                .claims(JwtRegisteredClaimNames.EXPIRATION_TIME, Date.from(utgang))
                .claims(JwtRegisteredClaimNames.JWT_ID, UUID.randomUUID().toString())
                .claims(VC_JWT_CLAIM, claim);
        var resultat = tokenGenerationService.generate(utfardarParticipantId, utfardarPrivatnyckelAlias,
                decorator, new KeyIdDecorator(composedKeyId));
        if (resultat.failed()) {
            throw new IllegalStateException("Kunde inte signera statuslistan: " + resultat.getFailureDetail());
        }
        return resultat.getContent().getToken();
    }
}
