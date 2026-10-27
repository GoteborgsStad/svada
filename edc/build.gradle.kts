/*
 * SVADA PoC – byggfil för EDC-connectorn.
 * KONCEPT: docs/koncept/C2-resursstrategi.md
 *
 * Modulvalet är taget RAKT UR Eclipse EDC:s officiella samples,
 * transfer/transfer-00-prerequisites/connector/build.gradle.kts, för att
 * PoC:en ska följa den väg EDC-projektet självt dokumenterar.
 *
 * Versionen kommer in som -PedcVersion från Dockerfile:n, som i sin tur
 * får den ur .env (EDC_VERSION) – hård regel 4: inga rörliga versioner.
 */

val edcVersion: String by project

plugins {
    `java-library`
    application
    // Bygger fat jar:en. GOTCHA: Gradles plugins-block kräver en KONSTANT
    // version – den går inte att läsa ur en property, och därför inte
    // heller ur .env (till skillnad från edcVersion nedan). Versionen är
    // låst här i stället, samma 9.6.0 som eclipse-edc/Samples kör.
    id("com.gradleup.shadow") version "9.6.0"
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        // Java 17 (EDC 0.17.0 kräver minst 17).
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

dependencies {
    // ---------------------------------------------------------------
    // Kontrollplanet. controlplane-dcp-bom (DCP-identiteten, ersätter
    // controlplane-base-bom) är EDC:s "batteries included"-BOM PLUS DCP:
    // den utökar controlplane-base-bom (boot, connector-core,
    // control-plane-core, dsp, management-api, api-observability,
    // token-core, configuration-filesystem m.fl. – oförändrat) med
    // decentralized-claims-*/identity-did-*/verifiable-credentials
    // (uppströmskällans dist/bom/controlplane-dcp-bom/build.gradle.kts,
    // verifierat rad för rad). Det ersätter en lista med åtta enskilda
    // moduler – en enda BOM
    // är enklare och mindre felbenäget än att lista dem själva (en
    // tidigare lista hade ett fel artefakt-ID). IN-MEMORY-stores är
    // fortfarande default – vi tar medvetet INTE med
    // controlplane-feature-sql-bom (resursstrategin, hård regel 3).
    // ---------------------------------------------------------------
    runtimeOnly("org.eclipse.edc:controlplane-dcp-bom:$edcVersion")

    implementation("org.eclipse.edc:control-plane-api-client:$edcVersion")

    // ---------------------------------------------------------------
    // HISTORIK (DCP-identiteten): ett tidigare försök kompilerade här mot
    // protocol-spi/decentralized-claims-core för att registrera en egen
    // ParticipantIdExtractionFunction (SvadaParticipantIdExtractionFunction,
    // nu borttagen). Det visade sig krocka med EDC:s eget kontrollplan
    // (ContractNegotiationProtocolServiceImpl återanvänder samma
    // ParticipantAgent.getIdentity()-värde som förhandlingens
    // counterPartyId/mål-audience - se SvadaDcpIdentityExtension.java:s
    // klasskommentar för hela
    // felsökningskedjan), så DCP-modulens EGEN default-identitetskälla
    // används numera i stället. Inget av SVADA:s egna extensions
    // kompilerar längre mot de två modulerna - de togs bort härifrån.
    //
    // DCP-identitetens verifieringssteg: verifiable-credentials-spi läggs
    // DÄREMOT tillbaka här (var med i det första försöket ovan, togs bort i samma
    // städning, men behövs nu igen av ett helt annat skäl) -
    // KovIdentitetsverifiering (se.goteborg.svada.edc.kov) kompilerar mot
    // dess VerifiableCredential/CredentialSubject-modeller för att läsa ut
    // "role"-claimet ur den verifierade SvadaRoleCredential-attesten.
    // Modulen ligger redan på körtidsklassvägen via controlplane-dcp-bom
    // ovan (den drar in den transitivt) - implementation-raden krävs bara
    // för att KOMPILERA mot samma typer, samma mönster som core-spi/
    // policy-model nedan.
    // ---------------------------------------------------------------
    implementation("org.eclipse.edc:verifiable-credentials-spi:$edcVersion")

    // ---------------------------------------------------------------
    // SPI:er som PoC:ens egna extensions kompilerar mot (ODRL-
    // bindningarna och KoV-gaten). Modulerna ligger redan på
    // körtidsklassvägen via BOM:en ovan, men runtimeOnly lägger inte ut
    // dem på KOMPILERINGSklassvägen – därför upprepas de här.
    // ---------------------------------------------------------------
    implementation("org.eclipse.edc:core-spi:$edcVersion")
    implementation("org.eclipse.edc:web-spi:$edcVersion")
    implementation("org.eclipse.edc:policy-model:$edcVersion")
    implementation("org.eclipse.edc:policy-engine-spi:$edcVersion")
    implementation("org.eclipse.edc:contract-spi:$edcVersion")
    implementation("org.eclipse.edc:catalog-spi:$edcVersion")

    // ---------------------------------------------------------------
    // iam-mock (EDC:s mock-identitetstjänst - utfärdade
    // och godtog tokens utan någon verifierbar identitet alls) är BORTTAGEN
    // härifrån. Verifierbar identitet kommer nu från controlplane-dcp-bom
    // ovan (riktig DCP-verifiering mot IdentityHub) - se
    // konfigurationen i edc/konfig/*.properties.
    // ---------------------------------------------------------------
    // Token-baserad autentisering på management-API:t (delad
    // nyckel, docs/koncept/C1-identitet.md). EDC 0.8.0+ kräver BÅDA
    // modulerna för att web.http.<kontext>.auth.type=tokenbased ska
    // wireas automatiskt av konfigurationssystemet (github.com/eclipse-edc/
    // Connector, diskussion #4416) – controlplane-base-bom drar INTE in
    // dem transitivt.
    // ---------------------------------------------------------------
    implementation("org.eclipse.edc:auth-tokenbased:$edcVersion")
    implementation("org.eclipse.edc:auth-configuration:$edcVersion")
    // AuthenticationRequestFilter och ApiAuthenticationRegistry för avtalsstatus-sammanhanget.
    implementation("org.eclipse.edc:auth-spi:$edcVersion")

    // Transfer-/dataplansledet (används fullt ut vid överföring och mottagning).
    //
    // STÄLLNINGSTAGANDE (överföring och mottagning): runtimen varnade
    // vid varje uppstart för att `transfer-data-plane-signaling` är
    // deprecated. Modulen är BYTT mot efterföljaren `data-plane-signaling`
    // – exakt det byte varningstexten föreskriver ("...by adding the
    // `data-plane-signaling` module to your runtime and removing the legacy
    // `transfer-data-plane-signaling` one").
    implementation("org.eclipse.edc:data-plane-signaling:$edcVersion")
    implementation("org.eclipse.edc:validator-data-address-http-data:$edcVersion")
    implementation("org.eclipse.edc:edr-cache-api:$edcVersion")
    implementation("org.eclipse.edc:edr-store-core:$edcVersion")
    implementation("org.eclipse.edc:edr-store-receiver:$edcVersion")
    implementation("org.eclipse.edc:data-plane-self-registration:$edcVersion")
    implementation("org.eclipse.edc:data-plane-signaling-api:$edcVersion")
    implementation("org.eclipse.edc:data-plane-signaling-client:$edcVersion")
    implementation("org.eclipse.edc:data-plane-core:$edcVersion")
    implementation("org.eclipse.edc:data-plane-http:$edcVersion")
    implementation("org.eclipse.edc:data-plane-iam:$edcVersion")
}

application {
    // EDC:s generiska runtime – laddar alla ServiceExtension:er via SPI.
    mainClass.set("org.eclipse.edc.boot.system.runtime.BaseRuntime")
}

tasks.shadowJar {
    // Utan mergeServiceFiles() slås META-INF/services-filerna ut mot
    // varandra och runtimen startar utan sina extensions.
    mergeServiceFiles()
    archiveFileName.set("connector.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
}
