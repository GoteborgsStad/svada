/*
 * SVADA PoC – Gradle-inställningar för identity-hub-bootstrap-modulen.
 *
 * Detta är INTE en kopia/fork av eclipse-edc/IdentityHubs eget stora
 * monorepo (det klonas separat i Dockerfile:ns "bygge"-steg) - det här är
 * en LITEN, egen SVADA-modul som bara innehåller vår
 * bootstrap-extension (SvadaParticipantBootstrapExtension), byggd mot
 * IdentityHubs publicerade SPI-artefakter på Maven Central. Samma princip
 * som edc/: eget, litet Gradle-projekt, låst version, ingen uppströms-
 * källkod att underhålla.
 */

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

rootProject.name = "svada-identity-hub-bootstrap"
