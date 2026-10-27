# =====================================================================
# SVADA PoC – Eclipse EDC IdentityHub (verifierbar identitet)
# =====================================================================
# KONCEPT: docs/koncept/C1-identitet.md. 
#
# EN image, TVÅ instanser (identity-hub-dhi/identity-hub-stad i respektive
# compose-fil) – samma jar, ingen konfiguration bakas in i imagen (rollen
# är bara "vilken part kör den här instansen", och all den skillnaden
# uttrycks i miljövariabler i compose, inte här). Samma princip som
# edc/Dockerfile.
#
# SKILLNAD mot edc/Dockerfile: IdentityHub är INTE vår egen enkla
# Gradle-modul – det är Eclipse EDC-projektets EGNA stora monorepo (ett
# 50-tal moduler). Vi återskapar inte den strukturen i en egen
# build.gradle.kts (som vi gör för edc/, taget ur EDC:s samples) – i
# stället byggs uppströmsprojektets EGEN launcher-modul
# (launcher/identityhub) rakt ur källkoden, exakt det kommandot
# IdentityHubs egen README föreskriver. Verifierat i spiken 2026-09-01
# (lokal provbyggning av uppströmskällan): "BUILD SUCCESSFUL" på både bygget och
# den efterföljande körningen (hälsokoll grön).
#
# Multi-stage: Java/Gradle behövs bara i byggsteget (samma motivering som
# edc/Dockerfile). Källkoden hämtas med git clone LÅST till en exakt tagg
# (hård regel 4) – .env äger versionen (IDENTITY_HUB_VERSION), inte den
# här filen. IdentityHub publicerar inte sin launcher-modul till Maven
# Central (den är avsedd att byggas ur källkod), så en Maven-koordinat
# att pinna mot finns inte – git-taggen ÄR pinningen här.
#
# TREDJE INGREDIENSEN (utöver EDC_GRADLE_IMAGE/EDC_BASE_IMAGE ovan): en
# EGEN, liten SVADA-modul (src/, build.gradle.kts i den här mappen)
# byggs i ett separat steg (bootstrap-bygge) och lägger sin tunna jar
# BREDVID uppströms identity-hub.jar på klassvägen i slutimagen - se
# steg "bootstrap-bygge" och ENTRYPOINT nedan. Den löser ett verkligt
# problem: IdentityHub har ingen inbyggd väg att skapa sin FÖRSTA
# identitet via REST-API:t (kräver redan en admin-identitet för att
# skapa identiteter alls, se SvadaParticipantBootstrapExtension.java för
# den fulla motiveringen), så vi bootstrap:ar in-process vid uppstart.
# =====================================================================

ARG EDC_GRADLE_IMAGE
ARG EDC_BASE_IMAGE

# ---------------------------------------------------------------------
# Steg 1: hämta uppströmskällan och bygg fat jar:en (identity-hub.jar)
# med IdentityHub-projektets egen Gradle-modul launcher:identityhub.
# ---------------------------------------------------------------------
FROM ${EDC_GRADLE_IMAGE} AS bygge

ARG IDENTITY_HUB_VERSION

# git ingår inte i gradle-basimagen.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bygge

# --depth 1 + exakt tagg (IDENTITY_HUB_VERSION ur .env, t.ex. "v0.17.0"):
# samma pinning-princip som edcVersion i edc/, fast som git-referens i
# stället för Maven-koordinat.
RUN git clone --branch ${IDENTITY_HUB_VERSION} --depth 1 \
    https://github.com/eclipse-edc/IdentityHub.git .

# --no-daemon: engångsbygge i container, ingen daemon att återanvända
# (samma motivering som edc/Dockerfile). -x test: vi bygger uppströms
# release-kod, inte vår egen – deras egen CI har redan kört testerna.
RUN gradle --no-daemon :launcher:identityhub:build -x test

# ---------------------------------------------------------------------
# Steg 2: bygg SVADA:s EGEN bootstrap-extension (se
# SvadaParticipantBootstrapExtension.java och build.gradle.kts i den här
# mappen). Litet, snabbt bygge mot IdentityHubs publicerade SPI:er på
# Maven Central - ingen git clone, ingen uppströms-källkod inblandad.
# ---------------------------------------------------------------------
FROM ${EDC_GRADLE_IMAGE} AS bootstrap-bygge

WORKDIR /bootstrap
COPY gradle.properties settings.gradle.kts build.gradle.kts ./
COPY src ./src
RUN gradle --no-daemon jar

# ---------------------------------------------------------------------
# Steg 3: driftimagen – enbart JRE + de två jarna. Samma bas-image som
# våra egna EDC-connectorer (EDC_BASE_IMAGE ur .env), INTE uppströms-
# launcherns egen Dockerfile (som pinnar en annan, egen Alpine/Temurin-
# tagg) – ett gemensamt bas-lager för hela stacken, hård regel 4.
# ---------------------------------------------------------------------
FROM ${EDC_BASE_IMAGE}

RUN useradd --system --uid 10002 --create-home identityhub

WORKDIR /app
COPY --from=bygge /bygge/launcher/identityhub/build/libs/identity-hub.jar /app/identity-hub.jar
COPY --from=bootstrap-bygge /bootstrap/build/libs/identity-hub-bootstrap.jar /app/identity-hub-bootstrap.jar

USER identityhub

# -cp med BÅDA jarna (inte -jar identity-hub.jar): Javas ServiceLoader
# läser META-INF/services från varje post på klassvägen och slår ihop
# dem automatiskt - ingen sammanslagning av jar-filerna krävs. Alla
# web.http.*-portar/vägar, JVM-heaptaket OCH svada.participant.*-
# inställningarna sätts av compose via miljövariabler (WEB_HTTP_*,
# JAVA_TOOL_OPTIONS, SVADA_PARTICIPANT_* ur .env) – ingenting
# konfigureras här, se identity-hub-dhi/identity-hub-stad i respektive
# compose-fil.
ENTRYPOINT ["java", "-cp", "/app/identity-hub.jar:/app/identity-hub-bootstrap.jar", "org.eclipse.edc.boot.system.runtime.BaseRuntime"]
