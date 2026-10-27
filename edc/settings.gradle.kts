/*
 * SVADA PoC – Gradle-inställningar för EDC-connectorn.
 *
 * ETT ENDA Gradle-projekt ("svada-connector") som byggs till en fat jar
 * (shadowJar). Samma jar körs som BÅDE provider (DHI) och consumer
 * (Göteborgs Stad) – rollskillnaden ligger enbart i konfigurationsfilen
 * som monteras in i containern (edc/konfig/*.properties). Det är också så
 * Eclipse EDC:s officiella samples gör det.
 */

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

rootProject.name = "svada-connector"
