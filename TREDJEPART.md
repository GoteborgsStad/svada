# Tredjepartskomponenter

Imagen hämtas eller byggs av dig som kör stacken; det här repot distribuerar inte deras kod (utom Leaflet, se nedan). **Varje licens ska
kontrolleras mot källan före publicering.** Kolumnen "Källa för uppgiften" säger hur uppgiften framkom: *image-etikett* är avläst ur imagen
(`org.opencontainers.image.licenses`), övriga är lästa ur komponentens egen licensfil eller paketmetadata. Versionerna står i `.env.exempel`.

| Komponent | Version | Licens | Källa för uppgiften (kontrollerad 2026-10-21) |
|---|---|---|---|
| Caddy (proxy) | 2.11.7 | Apache-2.0 | image-etikett |
| caddy-ratelimit (plugin, byggs in) | v0.1.0 | Apache-2.0 | LICENSE i uppströmsrepot (mholt/caddy-ratelimit) |
| FIWARE Orion-LD | 1.12.0 | **AGPL-3.0** | LICENSE i uppströmsrepot (FIWARE/context.Orion-LD) |
| FIWARE Mintaka | 0.7.0 | **AGPL-3.0-only** | image-etikett (0.6.6); projektet är arkiverat uppströms sedan 2026-05-13 |
| MongoDB | 7.0.45 | **SSPL v1** (Server Side Public License, 2018) | LICENSE-Community.txt i uppströmsrepot (mongodb/mongo, gren v4.4; samma licens för 7.0 enligt MongoDB, men 7.0-grenens fil är inte läst) |
| TimescaleDB med PostGIS (`timescaledb-ha`, -oss) | pg17.11-ts2.31.0 | TimescaleDB: **Apache-2.0** (-oss-varianten har inga delar under Timescale License; `timescaledb.license=apache`); PostGIS: GPL-2.0-or-later; PostgreSQL: PostgreSQL License | variantens beskrivning och provet: `timescaledb-tsl-*`-biblioteket saknas i -oss-imagen. PostGIS- och PostgreSQL-licenserna är inte läst ur källan |
| Eclipse EDC (byggs från källkod i `edc/`) | 0.17.0 | Apache-2.0 | LICENSE i uppströmsrepot (eclipse-edc/Connector) |
| Eclipse IdentityHub (byggs från källkod i `identity-hub/`) | v0.17.0 | Apache-2.0 | LICENSE i uppströmsrepot (eclipse-edc/IdentityHub) |
| Eclipse Temurin (Java-runtime) | 17.0.20.1 | GPL-2.0 med Classpath Exception | licenstext och NOTICE i imagen (`/opt/java/openjdk/legal`, `NOTICE`) |
| Gradle (byggverktyg) | 9.8.2 | Apache-2.0 | LICENSE i uppströmsrepot (gradle/gradle) |
| Python | 3.12.15 | PSF License v2 | LICENSE i uppströmsrepot (python/cpython, gren 3.12) |
| FastAPI | 0.158.1 | MIT | paketmetadata i imagen |
| Starlette | 1.9.0 (följer med FastAPI 0.158.1, låses inte separat) | BSD-3-Clause | paketmetadata i imagen |
| Uvicorn | 0.54.0 | BSD-3-Clause | paketmetadata i imagen |
| Pydantic, pydantic-core, anyio, h11, click, idna, annotated-types, typing-inspection | enligt imagen | MIT eller BSD-3-Clause | paketmetadata i imagen |
| typing-extensions | enligt imagen | PSF-2.0 | paketmetadata i imagen |
| alpine/curl (curl) | 8.22.0 | curl-licensen (MIT-lik, "COPYRIGHT AND PERMISSION NOTICE") | COPYING i uppströmsrepot (curl/curl) |
| Leaflet (följer med i `services/dashboard/statiskt/leaflet/`) | enligt filen | BSD-2-Clause | `LICENSE.txt` i filen |

**Vad det betyder.** Det här repot innehåller och distribuerar ingen kod från AGPL-, SSPL- eller TSL-komponenterna: du hämtar imagen själv och kör
dem oförändrade. AGPL ställer krav på den som erbjuder *egna ändrade versioner* som en tjänst. SSPL (§13) går längre: den som erbjuder programmet som en tjänst till andra, även oförändrat, ska göra tjänstens hela källkod tillgänglig. Kör du dem som de är i den här
demon för eget bruk gäller inte det, men erbjuder du dem som en tjänst till andra ska du läsa licensen. Timescale License (TSL) gäller inte: vi kör -oss-varianten av TimescaleDB-imagen (kontrollerat: inga `timescaledb-tsl-*`- eller toolkit-bibliotek i imagen, och `timescaledb.license=apache`), som bara har de Apache-licensierade delarna.
EDC:s och IdentityHubs byggberoenden hämtas från Maven Central av dig vid bygget. De transitiva beroendena är genomgångna 2026-10-26 (runtime-klassväg; licens läst ur POM-filen och dess föräldrar): 331 unika artefakter, alla med licens. 291 är enbart Apache-2.0; resten är MIT, BSD-3, EDL 1.0 (BSD), Bouncy Castle-licensen (MIT-lik) eller flerlicensierade: Jakarta/HK2-paketen (EPL-2.0 eller GPL-2.0 med Classpath Exception: välj EPL-2.0, som är svag copyleft och inte permissiv), Jersey (EPL-2.0 eller Apache-2.0), Jetty (Apache-2.0 eller EPL-2.0) och javassist (Apache-2.0, MPL 1.1 eller LGPL 2.1). Ingen artefakt är enbart GPL, LGPL, AGPL eller SSPL. EPL-2.0 är svag copyleft på filnivå och spelar roll först för den som ändrar och vidaredistribuerar de komponenterna. Inte kontrollerat: licensfiler inne i jar-filerna (Jerseys POM nämner inbäddad kod under Public Domain, W3C och jQuery), build-time- och testberoenden, och bildlagren. Python-paketens licenser ovan är avlästa ur de byggda imagen; paketen hämtas från PyPI vid bygget.

Kartplattor hämtas alltid direkt från OpenStreetMap av besökarens webbläsare när en karta visas (den visar då besökarens IP-adress och ungefär vilket område som visas)
(© OpenStreetMap-bidragsgivare, ODbL).

Python-paketen i `services/*` installeras från PyPI vid bygget (se respektive `Dockerfile`).
