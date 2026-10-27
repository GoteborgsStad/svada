# =====================================================================
# Caddy med ratelimit-tillägget (publik demo, K3/K4)
# =====================================================================
# Stock-Caddy saknar hastighetsbegränsning. Vi bygger därför in
# mholt/caddy-ratelimit med xcaddy. Versionerna är LÅSTA (hård regel 4):
# basbild och plugin-tagg anges som byggargument från .env.
# =====================================================================
ARG CADDY_BUILDER_IMAGE
ARG CADDY_RUNTIME_IMAGE

FROM ${CADDY_BUILDER_IMAGE} AS byggare
ARG CADDY_RATELIMIT_VERSION
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@${CADDY_RATELIMIT_VERSION}

FROM ${CADDY_RUNTIME_IMAGE}
# Säkerhetsrättning: uppgradera OS-paketen (libssl/libcrypto m.fl.) så att
# kanten inte kör kända sårbara bibliotek.
RUN apk upgrade --no-cache
COPY --from=byggare /usr/bin/caddy /usr/bin/caddy
# Bevisa att tillägget faktiskt byggdes in (annars faller bygget här).
RUN caddy list-modules | grep -q "http.handlers.rate_limit"
