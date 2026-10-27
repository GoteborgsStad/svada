/*
 * SVADA PoC – byggfil för identity-hub-bootstrap-modulen (verifierbar identitet).
 * KONCEPT: docs/koncept/C1-identitet.md. 
 *
 * Producerar en TUNN jar (identity-hub-bootstrap.jar) som innehåller
 * ENDAST våra egna klasser (SvadaParticipantBootstrapExtension, StatusLista,
 * StatusListController, StatusListPublik) + META-INF/services-registreringen. Den läggs på klassvägen BREDVID
 * uppströms identity-hub.jar i slutimagen (se Dockerfile) - INTE
 * sammanslagen till en fat jar. Java-runtimens ServiceLoader läser
 * META-INF/services från VARJE post på klassvägen och slår ihop dem
 * automatiskt, så två separata jar-filer på samma -cp fungerar utan
 * någon shadowJar/mergeServiceFiles-mekanik här.
 *
 * SPI-beroendena nedan är REDAN med i identity-hub.jar (uppströms fat
 * jar innehåller sin egen kod), så "implementation" (inte "runtimeOnly")
 * räcker - vi kompilerar mot dem men skeppar dem inte med i vår egen jar.
 */

val edcVersion: String by project

plugins {
    `java-library`
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        // Samma Java-version som edc/ och uppströms IdentityHub (0.17.0 kräver minst 17).
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

dependencies {
    implementation("org.eclipse.edc:identity-hub-spi:$edcVersion")
    implementation("org.eclipse.edc:participant-context-spi:$edcVersion")
    // did-spi ger DidDocumentService.publish(did) - används för att explicit
    // publicera DID-dokumentet själva, se klasskommentaren i
    // SvadaParticipantBootstrapExtension.java om varför den inbyggda
    // "activate() publicerar implicit"-kedjan i IdentityHub inte gick att lita på.
    implementation("org.eclipse.edc:did-spi:$edcVersion")
    // Steg 4 (attest-utfärdande): JWT-VC-signering av de tre
    // attesttyperna (SvadaParticipantCredential/-MembershipCredential/
    // -RoleCredential). Se klasskommentaren i
    // SvadaParticipantBootstrapExtension.java ("ATTEST-UTFÄRDANDE") för
    // den fulla motiveringen till varför dessa (publicerade) byggstenar
    // används i stället för det upublicerade issuerservice-issuance-
    // modulen (som saknar maven-publish och därför inte går att bero på).
    //
    // OBS: två OLIKA moduler med snarlika namn, från två olika uppströms-
    // repon - inte en duplicering:
    //  - verifiable-credential-spi  (ENTAL, identityhub-repot) ger
    //    CredentialStore/VcStatus/VerifiableCredentialResource
    //    (org.eclipse.edc.identityhub.spi.verifiablecredentials.*).
    //  - verifiable-credentials-spi (PLURAL, connector-0.17.0-repot) ger
    //    W3C-datamodellen VerifiableCredential/CredentialSubject/Issuer/
    //    CredentialFormat/DataModelVersion/VcConstants
    //    (org.eclipse.edc.iam.verifiablecredentials.spi.*).
    implementation("org.eclipse.edc:verifiable-credential-spi:$edcVersion")
    implementation("org.eclipse.edc:verifiable-credentials-spi:$edcVersion")
    implementation("org.eclipse.edc:token-spi:$edcVersion")
    implementation("org.eclipse.edc:jwt-spi:$edcVersion")
    implementation("org.eclipse.edc:token-lib:$edcVersion")
    // Steg 5: StsAccountService (sätta en DETERMINISTISK STS-
    // klienthemlighet i stället för IdentityHubs slumpade, se
    // klasskommentaren i SvadaParticipantBootstrapExtension.java,
    // "STEG 5 - STS-KLIENTHEMLIGHET"). Modulnamnet är "sts-spi" (mappnamn
    // = artefaktnamn, samma konvention som redan verifierad tre gånger
    // för identity-hub-spi/participant-context-spi/did-spi/
    // verifiable-credential-spi).
    implementation("org.eclipse.edc:sts-spi:$edcVersion")
    // JAX-RS (via web-spi) och WebService för statuslistans endpoints (StatusListController).
    implementation("org.eclipse.edc:web-spi:$edcVersion")
}

tasks.jar {
    archiveFileName.set("identity-hub-bootstrap.jar")
}
