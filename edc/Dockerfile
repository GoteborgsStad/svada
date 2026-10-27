# =====================================================================
# SVADA PoC – Eclipse EDC-connector (komponent 6 och 7)
# =====================================================================
# EN image, TVÅ roller: samma jar körs som edc-provider (DHI) och
# edc-consumer (Göteborgs Stad). Rollen bestäms enbart av vilken
# konfigurationsfil som monteras in på /config/connector.properties.
#
# Multi-stage: Java/Gradle behövs bara i byggsteget, aldrig i drift
# (Java behövs inte på värden – EDC byggs och körs i
# container). Slutimagen är en ren JRE + fat jar.
#
# Alla taggar/versioner kommer ur .env via build args (hård regel 4).
# =====================================================================

ARG EDC_GRADLE_IMAGE
ARG EDC_BASE_IMAGE

# ---------------------------------------------------------------------
# Steg 1: bygg fat jar:en med Gradle.
# ---------------------------------------------------------------------
FROM ${EDC_GRADLE_IMAGE} AS bygge

ARG EDC_VERSION

WORKDIR /bygge

# Byggfilerna först: ändras de inte kan Docker återanvända lagret med
# nedladdade beroenden (EDC drar ~200 artefakter).
COPY gradle.properties settings.gradle.kts build.gradle.kts ./
COPY src ./src

# --no-daemon: engångsbygge i container, ingen daemon att återanvända.
RUN gradle --no-daemon -PedcVersion=${EDC_VERSION} shadowJar

# ---------------------------------------------------------------------
# Steg 2: driftimagen – enbart JRE + jar.
# ---------------------------------------------------------------------
FROM ${EDC_BASE_IMAGE}

# Kör inte som root (imagen har ingen icke-privilegierad användare i sig).
RUN useradd --system --uid 10001 --create-home edc

WORKDIR /app
COPY --from=bygge /bygge/build/libs/connector.jar /app/connector.jar

USER edc

# edc.fs.config pekar ut konfigurationsfilen som compose monterar in.
# JVM-taket (-Xmx512m) sätts av compose via JAVA_TOOL_OPTIONS ur .env
# (EDC_JVM_XMX) – bindande resursstrategi (hård regel 3).
ENTRYPOINT ["java", "-Dedc.fs.config=/config/connector.properties", \
            "-jar", "/app/connector.jar"]
