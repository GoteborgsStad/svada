# C6. Från laptop till drift: uthållighet, lagring och gallring

> PoC:en bevisar **protokoll och beslutsvägar**. Den bevisar ingenting om vad som händer när en
> komponent är nere, hur mycket data som samlas på ett år eller vad som får gallras. Detta
> dokument är hemvisten för den tredje axeln – driftegenskaperna – och svarar på frågorna *var
> ligger data egentligen*, *försvinner det om något går sönder* och *hur ser samma led ut i
> skarp drift*.

**Läsanvisning.** De flesta punkter här är **inte gap** mot Målarkitektur v1.9: arkitekturen
reglerar inte databasreplikering och kan därför inte ha ett krav att avvika ifrån. De är ändå de
första frågor som ställs när någon sett demon. Där en punkt *är* ett gap står G-numret utsatt.

*Den tidigare PoC:en med tio steg (ingår inte i det här paketet) hade även ett sensorled
(MQTT, IoT-agent, orion-dhi) med egna driftfrågor – meddelandeleverans, QoS, retained messages. De
ingår inte i Svada-mini och behandlas inte här.*

## Begrepp

Kanoniska termer ur [`13-ordlista.md`](../13-ordlista.md): **TRoE / temporal**, **CIP**,
**in-memory stores**, **avtalsregister**, **hävning**.

## Vad problemet är

Målarkitektur v1.9 §5.1 *Lagra*: **"Informationsklassad lagring i CIP med tidsseriehistorik;
lagringstid och gallring enligt Arkivnämndens beslut; långsiktig kvalitetssäkrad lagring
utvärderas mot stadens kommande gemensamma dataplattform."** Princip 0 tillägger att *"fel i
flöden skapar incident enligt tekniskt regelverk i stället för tyst felaktig information"*.

Det är driftkrav formulerade på verksamhetsnivå. Komponentplanens §3.3 (resursstrategin, se
[[C2-resursstrategi]]) drar samtidigt åt motsatt håll av goda skäl: **allt ska rymmas på en
laptop.** Detta dokument redovisar var de två drar isär.

## Hur PoC:en gör

Kedjans lagringspunkter, i den ordning data passerar dem:

| # | Led | Vad som lagras | Var |
|---|---|---|---|
| 1 | `fcf-sim` | batchar; mätserien läses ur CSV-filerna vid start | **RAM** |
| 2 | `edc-provider` / `-consumer` | assets, policyer, avtal, KoV-beslut **inklusive hävningar** | **RAM** (in-memory stores) |
| 3 | `ingest-service` | avtalsregistret: status och ODRL-ögonblicksbild per avtal; engångsnycklar | **RAM** |
| 4 | `orion-stad` (CIP) | senaste tillstånd, 91 brunnar + proveniens | `mongo-stad` (volym) |
| 5 | `timescale-stad` | **TRoE – historiken** | disk (volym) |

**Konsekvenser.**

* **Startas providern om försvinner avtalen och besluten.** Det gäller också hävningar: ett hävt
  avtal kan inte väckas till liv, eftersom avtalet försvinner med det. Registret hos staden
  nollställs också vid omstart av ingest-servicen, men fylls på igen ur stadens connector och
  providerns lista.
* **Startas `fcf-sim` om försvinner batcharna men inte mätserien.** Den ligger i filerna, så
  modellen får full täckning från första batchen.
* **Historiklagret är det enda som växer – utan styrning.** TRoE-tabellerna är vanliga
  PostgreSQL-tabeller (noll hypertables, ingen komprimering), och det som kallas "retention" i
  PoC:en är minnestak utan koppling till Arkivnämndens beslut (**G13**).
* **Statusen på avtal hämtas genom polling** (staden läser providerns API ungefär varje sekund).
  Om providern inte svarar blir statusen `OKAND` och åtkomsten nekas: stängt som standard
  (**G23**).

## Samma led i skarp drift

* **EDC:** Postgres-persistens för connectorerna (ett dataägarbeslut och en hävning får inte
  tappas av en omstart), och avtal och hävningar som sprids genom protokollet eller en
  statuslista i stället för genom att staden läser providerns API.
* **CIP:** MongoDB som replica set med autentisering och backup med prövad återläsning.
* **Historik:** hypertables med chunkning och komprimering (först då gör TimescaleDB nytta; komprimeringen ingår inte i Apache-varianten `-oss` som PoC:en kör, så skarp drift behöver den fullständiga imagen och dess licens);
  gallring enligt Arkivnämndens beslut – ett verksamhetsbeslut, ingen konfigurationsrad.
* **Identitet:** IdentityHub med beständiga nycklar. I PoC:en får varje hubb nya nycklar vid
  varje start, så en enskild omstart av Svadas utfärdare ger tysta 401 tills alla hubbar och
  connectorer startats om (se `docs/08-drift-identitet-skalning.md` punkt 10).

## Koden

| Fil | Symbol | Ansvar |
|---|---|---|
| `services/ingest-service/avtalsregister.py` | `Avtalsregister` | Avtalsregistret i RAM: synk från providern, stängt som standard – **primär hemvist för detta dokument** |
| `edc/src/main/java/se/goteborg/svada/edc/kov/KovGate.java` | `havda`, `Havning` | Hävningar i providerns minne |
| `compose.stad.yml` | `mongo-stad`, `timescale-stad` | Volymerna för CIP och historik |

## Språk i kontrollrummet

Språket är en egenskap hos vyn, inte hos datat, avtalet eller loggen. Formell text (avtalsklausuler,
roller, villkor i katalogen) är engelsk i båda vyerna; löptext och beskrivningar skapas på vyns språk; data
står i originalet. Händelser (jobbrader, auditposter, felmeddelanden) lagras som **kod och parametrar**, och
en meddelandekatalog (`services/dashboard/meddelanden.py`) har en svensk och en engelsk mall per kod. Hashkedjan
räknas därför över kod och parametrar och är densamma oavsett språk. Tjänsterna skickar `kod` och `parametrar`
i sina felsvar; en regelbaserad reservöversättare (`i18n.py`) tar det som saknar kod. Testas av
`tests/engelska_enhet.py` och `tests/engelska_live.py`.

## Bevis

* `tests/verify_ap10.sh` **10.9** – okänd status nekas (OKAND i registret, 403
  `avtal-status-okand` i gatewayen), en bekräftad hävning består även när providern tystnar.
* `tests/verify_ap1.sh` – persistens i CIP och historik över en omstart.

## Förenkling → produktion

Se punkterna under *Samma led i skarp drift* ovan och gapanalysens G13, G20, G21 och G23 i
[`10-gapanalys.md`](../10-gapanalys.md).

## Läs vidare

* [[C2-resursstrategi]] – varför allt är in-memory och hur taken sätts.
* [[06-kov-gate]] – hävning och avtalsstatus.
* [[C5-skalning]] – nästa steg när fler parter ansluter.
