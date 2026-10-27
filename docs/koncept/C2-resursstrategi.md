# C2. Resursstrategin (in-memory stores, heap-tak, profiler)

> Hela kedjan – 20+ containrar, flera JVM:er, Solr, två Mongo – ska rymmas på en
> laptop utan att OOM-killern slår till. Det kräver medvetna, bindande tak:
> Compose-profiler, in-memory stores, fasta heap-gränser och `mem_limit` per
> tjänst.

Detta är en **tvärgående** strategi (bindande) som förklarar
flera annars förvånande designval i repot.

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **In-memory stores**,
**context broker**. Strategin är orsaken till omstartsregeln i
[`02-kom-igang.md`](../02-kom-igang.md).

## Vad problemet är

Komponentplanen §3.3 gör resursstrategin **bindande**: utan åtgärd riskerar
Solr + 2×JVM + 2×Mongo att trigga OOM-killern i WSL2. Samtidigt ska hela poängen
med PoC:en bevaras – att alla komponenter är synliga och reproducerbara på en
maskin (den medvetna avvikelsen från granskningsutlåtandet, §3.3).

## Hur PoC:en löser det

Fem grepp, alla verifierade:

1. **Compose-profiler.** Varje organisations stack är en egen profil, så att bara det som
   behövs körs.
2. **EDC med in-memory stores.** Bygget drar in `controlplane-base-bom` (default
   in-memory) och utelämnar medvetet SQL-BOM:en – sparar två Postgres-containrar.
   Priset: assets, avtal och KoV-beslut nollställs vid omstart ([[C1-identitet]],
   se [`02-kom-igang.md`](../02-kom-igang.md)).
3. **Fasta JVM-heaptak.** `EDC_JVM_XMX=-Xmx512m` per connector, Mintaka `-Xmx256m`. Satta via `JAVA_TOOL_OPTIONS` (som alltid respekteras).
4. **Mongo-cachetak.** `--wiredTigerCacheSizeGB 0.25` per instans.
5. **`mem_limit` per tjänst.** Från 128m (Caddy) till 1g (mongo, Mintaka).

**Varför inte `-XX:MaxRAMPercentage`?** JVM:en (OpenJDK 17) läser **inte** cgroup
v2-gränsen under WSL2 – containern ser sig som `0::/`. `MaxRAMPercentage=25.0` gav
`MaxHeapSize = 5247074304` (25 % av *värdens* 20 GiB) i en container med 1 GiB-tak
→ OOM. Därför fasta `-Xmx`-tal, och därför mäts Solrs tak via Solrs admin-API,
inte via `PrintFlagsFinal`.

## Koden

| Plats | Nyckel | Ansvar |
|---|---|---|
| `.env` | `EDC_JVM_XMX=-Xmx512m` | EDC-heaptak per connector. |
| `.env` | `MONGO_WT_CACHE_GB=0.25` | WiredTiger-cache per Mongo. |
| `.env` | `SOLR_JAVA_MEM="-Xms256m -Xmx512m"` | Solr-heaptak. |
| `compose.dhi.yml`, `compose.stad.yml` | `JAVA_TOOL_OPTIONS: ${EDC_JVM_XMX}` | Sätter EDC-heapen; Mintaka `-Xmx256m` + `MICRONAUT_METRICS_ENABLED: false`. |
| `edc/build.gradle.kts` | `runtimeOnly("…controlplane-base-bom…")` | In-memory stores (SQL-BOM utelämnad). |
| alla fyra compose-filer | `mem_limit:` per tjänst | Hårt minnestak per container. |

## Bevis

* `tests/verify_ap1.sh` **1.7** – Mongo kör `--wiredTigerCacheSizeGB`; mem_limit satt; Mintaka-heaptak satt.
* `tests/verify_ap4a.sh` **4a.5** – EDC-connectorer kör med `${EDC_JVM_XMX}`; in-memory (ingen SQL-BOM).

Kör själv:

```bash
docker inspect svada-edc-provider --format '{{.HostConfig.Memory}}'   # 805306368 = 768m
docker exec svada-orion-stad printenv | grep -i java
```

## Läs vidare

* Mintaka höjd 512m → 1g (off-heap växte, heapen
  oförändrad), och den fullständiga förklaringen till cgroup v2/WSL2-mätningen som
  förbjöd `MaxRAMPercentage`.
* Motpol: resursstrategin är också ett gap mot produktion – [[C1-identitet]] (G1)
  och den saknade persistensen (gapanalysens G10, G16).
