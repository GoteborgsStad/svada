# 05. DSP-katalog och ODRL-policyer

> Providern annonserar båda distributionerna i en DSP-katalog, var och en med
> sin ODRL-policy: B öppen (use/distribute/publish), A restriktiv (bara staden
> får använda, förbud mot spridning, kräver KoV-godkännande). Policyn är den
> maskinläsbara formen av dataägarens användningsvillkor.

Detta är kedjans **steg 2** (`docs/01-oversikt.md` §1.4) och arkitekturens kontrollplan
(Målarkitektur v1.9 §6.1–6.3).

## Begrepp

Kanoniska termer (se [ordlistan](../13-ordlista.md)): **Dataspace Protocol (DSP)**,
**ODRL**, **connector**, **KoV-godkännande**. Verkställigheten av A-policyn
behandlas i [[06-kov-gate]].

## Vad problemet är

Målarkitektur v1.9 §6.3: *"användningsvillkoren uttrycks som ODRL-policyer
knutna till varje distribution: tillåtelser, förbud och skyldigheter. Policyn
följer med i katalogens erbjudande, blir del av det förhandlade avtalet och
verkställs automatiskt av kontrollplanet vid varje transaktion."* §6.1:
connectorer kommunicerar enligt Dataspace Protocol, som bygger på DCAT (katalog)
och ODRL (villkor).

## Hur PoC:en löser det

Providern registreras med **asset + policy + kontraktsdefinition per
distribution** (aldrig delade – A och B har varsin allt igenom). Registreringen
körs ur `edc/bootstrap/`; assets pekar med `dataAddress`/`HttpData` på fcf-sims
`/distributions/{a,b}/latest`.

Consumern hämtar katalogen genom att POST:a mot providerns DSP-adress
(`http://edc-provider:19194/protocol/2025-1`, protokoll
`dataspace-protocol-http:2025-1`). Svaret är en `dcat:Catalog` där varje dataset
bär `odrl:hasPolicy` med ett förhandlingsbart offert-`@id`.

De två policyerna:

* **B** (`policy-distribution-b.json`): permission `odrl:use` (med duty
  `odrl:attribute`), `odrl:distribute`, `odrl:publish`. Tomma prohibition/obligation.
* **A** (`policy-distribution-a.json`): permission `odrl:use` **med constrainten**
  `svada:deltagare eq "stad"`; prohibition `odrl:distribute`/`odrl:publish`;
  obligation `svada:kovGodkannande`.

SVADA:s egna ODRL-termer (`svada:deltagare`, `svada:kovGodkannande`) definieras i
en egen namnrymd och binds i EDC-runtimen. `svada:deltagare` får en
utvärderingsfunktion registrerad **enbart** i förhandlingsscopet – utan den
skulle en bunden left operand ge "No evaluation function found" och fälla hela
policyn.

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `edc/bootstrap/registrera.py` | `main()`, `skapa_eller_uppdatera()` | Idempotent registrering av policy → asset → kontraktsdefinition för B och A. |
| `edc/bootstrap/policy-distribution-b.json` | `policy-distribution-b` | Öppen policy (use/distribute/publish + attribution). |
| `edc/bootstrap/policy-distribution-a.json` | `policy-distribution-a` | Restriktiv policy (constraint + prohibitions + KoV-obligation). |
| `edc/bootstrap/asset-distribution-a.json` / `-b.json` | `HttpData` dataAddress | Pekar assetet på fcf-sims distribution. |
| `edc/bootstrap/contractdefinition-distribution-a.json` / `-b.json` | `kontrakt-distribution-*` | Binder asset → policy; A har **egen** definition. |
| `edc/src/main/java/se/goteborg/svada/edc/odrl/SvadaOdrlExtension.java` | `initialize()`, `SVADA_NS`, `ACTION_KOV_GODKANNANDE`, `LEFT_DELTAGARE` | Registrerar SVADA:s ODRL-termer och scopes. |
| `edc/src/main/java/se/goteborg/svada/edc/odrl/DeltagareFunktion.java` | `evaluate()` | Jämför consumerns identitet mot `svada:deltagare`; loggar utvärderingen. |

Styrs av `.env`: `EDC_ASSET_A_ID`/`EDC_ASSET_B_ID`, `EDC_ASSET_A_URL`/`_B_URL`,
`EDC_DSP_VERSION=2025-1`, `EDC_PROVIDER_ID=dhi`.

## Bevis

`tests/verify_ap4a.sh` (och 4b.0 i `tests/verify_ap4b.sh`):

* **4a.2** – DSP-katalogen är en `dcat:Catalog`; `modellerad-bradddata-b` finns
  med `odrl:hasPolicy` och offert-`@id`; **inga spår av A** läcker in i B:s post.
* **4a.3** – assetens `dataAddress.baseUrl` == `EDC_ASSET_B_URL`; dataplanet
  svarar med Distribution B (public, utan GIS).
* **4b.0** – A:s offert förbjuder distribute/publish och bär `svada:kovGodkannande`
  och constrainten `svada:deltagare`; B:s bär use/distribute/publish + duty attribute.

Kör själv:

```bash
curl -s -X POST localhost:39393/management/v3/catalog/request \
  -H 'content-type: application/json' -d '{
    "@context":{"@vocab":"https://w3id.org/edc/v0.0.1/ns/"},
    "counterPartyId":"dhi",
    "counterPartyAddress":"http://edc-provider:19194/protocol/2025-1",
    "protocol":"dataspace-protocol-http:2025-1"}' | jq '."dcat:dataset"'
```

## Förenkling → produktion

* **Mock-IAM.** `svada:deltagare eq "stad"` utvärderas mot en identitet som
  motparten själv påstår ([[C1-identitet]], gapanalysens G1).
* **In-memory stores.** Assets och policyer nollställs vid omstart av providern –
  `registrera-edc` måste köras om ([[C2-resursstrategi]]).

## Läs vidare

* Varför obundna ODRL-regler filtreras bort av
  EDC:s ScopeFilter (därför lämnades B:s prohibition/obligation tomma), och varför
  `svada:deltagare` bara binds i förhandlingsscopet.
* Nästa: [[06-kov-gate]] – hur A-policyns obligation verkställs.
