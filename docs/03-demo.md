# 3. Demo: körschema för 15 minuter

**För:** SVADA-projektet, workshopdeltagare och styrgrupp.
**Var:** kontrollrummet på <http://localhost:38800>.
**Vad publiken ska ta med sig:** de tre invarianterna i
[`01-oversikt.md`](01-oversikt.md) §1.3 – suveränitet, integritet i klassningen och att
ett avtal gäller tills det hävs – och att poängen med ett dataspace är att data kommer till
**användning** under ett avtal.

> **Teknisk fördjupning:** dataspace-ledet (steg 2–4) finns i
> [`05-dataomradet.md`](05-dataomradet.md). Får du en fråga du inte kan svara på:
> [`12-fragor.md`](12-fragor.md).

## 3.1 Förberedelse (10 minuter innan publiken kommer)

Starta hela kedjan och kör `registrera-edc` enligt [`02-kom-igang.md`](02-kom-igang.md) §2.2.
Kontrollera att kontrollrummet visar "6 av 6 komponenter svarar" och att felinjektionen står
av. Värm sedan kedjan: klicka *Kör en batch nu* (steg 1), *Förhandla Distribution B* (steg 3)
och *Leverera B (kör transfer)* (steg 4) en gång. Utan detta är steg 5 och 6 tomma. Om något är rött
fungerar demon ändå – stegvyn visar exakt vilken komponent som saknas.

## 3.2 Körschemat

| Min | Vy | Du gör | Publiken ska se |
|---|---|---|---|
| 0–1 | Kedjan 1–6 | Visa kedjebilden och peka på organisationsgränsen mellan DHI och Göteborgs Stad. Klicka på ett steg: panelen under bilden förklarar vad som händer, varför och vad knapparna gör. Ordningsremsan (Kör batch → Hämta katalog → Förhandla B → Leverera B → Förhandla A + KoV → Leverera A → Analysera) är körschemat nedan, och ←/→ bläddrar mellan stegen | Sex steg, tre organisationer. Varje steg är ett riktigt protokoll, ingen pil i en PowerPoint. |
| 1–3 | Steg 1 | **Kör en batch nu** | FCF modellerar dygnet för 91 brunnar och framställer produkten i två distributioner. Modellen bygger på en brunns riktiga mätserie. Klassningen är inbyggd i produkten. |
| 3–5 | Steg 2–3 | **Hämta DSP-katalogen** → **Förhandla Distribution B** | Providern annonserar båda distributionerna med varsin ODRL-policy. B finaliseras automatiskt – öppna data behöver inget beslut. |
| 5–7 | Steg 4–5 | **Leverera B (kör transfer)** | Providern pushar; stadens ingest validerar mot avtalet innan något skrivs. 91 brunnar i CIP bär modellerad bräddata med proveniens: avtal, batch, klass. |
| 7–9 | Steg 3 | **Förhandla Distribution A** → vänta in kön → **KoV godkänner** i KoV-rutan bredvid | Förhandlingen stannar hos DHI:s connector med `pending: true`. Knappen anropar providerns management-API och kräver ett verifierat rollintyg – consumern saknar en sådan endpoint. Dataägarbeslutet verkställs där det hör hemma. |
| 9–11 | Steg 4 + 6 | **Leverera A (kör transfer)**, öppna steg 6 och välj **A** | Analysen med brunnarnas positioner på en karta: "vilka brunnar ska inspekteras först". Varje rad bär sitt avtal, sin batch och sin distribution. |
| 11–12 | Steg 3 / Suveränitet | **KoV häver avtalet** | Avtalet gäller tills det hävs. Steg 6 för A svarar nu "Distribution A kan inte läsas just nu" – stadens gateway nekar – medan **B går att leverera och använda**. Loggen visar att DHI:s connector också stoppar nya överföringar. |
| 12–13 | Steg 4 + 6 | **Leverera B (kör transfer)** och välj sedan **B** i steg 6; ändra antalet brunnar | Är senaste leveransen i plattformen en A-leverans under det hävda avtalet visar B-vyn "inga öppna data" (värdena får inte användas när avtalet har hävts), och efter en ny B-leverans fungerar den igen. Med öppna data: samma rangordning och en sammanställning per mottagande vattendrag, men ingen karta – positionerna ingår inte i B. Det är därför klassningen spelar roll. |
| 13–14 | Suveränitet: stadens egen utlämning | Öppna <http://localhost:38085/brunnar> och försök läsa A via stadens gateway | **Samma stad, två distributioner, motsatt utfall.** A svarar 403 med en läsbar sida; B svarar med data. Skillnaden är *verkställd* i stadens gateway, inte bara påstådd i metadatan. |
| 14–15 | Auditlogg | Filtrera på steg 3 och 4 | Hela kedjan kronologiskt, inklusive hävningen och vem som fattade beslutet (verifierad roll). Frågan "vem lämnade ut vad till vem, under vilket avtal?" har ett svar. |

## 3.3 Extranummer om tiden räcker (3 minuter)

**Felinjektion – avtalsbrottet.** Fliken **Felinjektion** → bocka i `gis_i_b` → **Leverera B (kör transfer)
och se utfallet**. FCF lägger då tyst tillbaka brunnarnas GIS-position i den öppna
distributionen. Nyttolasten bär ingen flagga om felet – stadens ingest-service upptäcker det
själv och avvisar leveransen med orsaken `brunns-gis-i-distribution-b`. Transfern blir
`TERMINATED` och ingenting skrivs till CIP:en. Poängen: mottagaren kontrollerar leveransen i
stället för att lita på avsändaren. Det är skillnaden mellan en filöverföring och ett
dataspace. Klicka **Nollställ felinjektionen** efteråt.

**Samordnaren kan stänga ute en deltagare (avstängt i den externa demon).** Steg 3, rutan *Samordnaren kan stänga ute en
deltagare*. Utestängningen fungerar, men den stänger ute alla besökare samtidigt och är därför avstängd i den externa varianten:
rutan har inga knappar utan visar ett inspelat exempel (statuslistan med stadens återkallade medlemsintyg, DHI:s 401 i
Dataspace Protocol och jobbloggens rad). Knappen **Prova katalogförfrågan nu** finns kvar och visar att staden når DHI.
I den interna varianten (`DEMO_VARIANT` utan värde, eller `DASH_UTESTANGNING=ja`) finns knapparna **Stäng ute** och **Släpp in igen**:
DHI nekar staden (401) när stadens medlemsintyg är återkallat, och allt fungerar igen utan omstart. Poängen: styrning på
dataspacets nivå är inte en text i en regelbok, utan ett beslut som verifieringen faktiskt efterlever.

**Avtalssidan.** Varje avtal har en egen adress, `/avtal/{id}`: status, villkor i klartext,
ODRL-ögonblicksbild, och avtalets id hos både DHI och staden (de är olika).

## 3.4 Vad du INTE ska lova

Var ärlig med de medvetna förenklingarna – de gör demon trovärdigare:

* **Identiteten är delvis simulerad.** Svadas utfärdare simulerar dataspacets tillitstjänst
  (DSGA 0.1): inte förankrad i eIDAS, återkallelsen ligger i minnet och saknar process. Staden intygar KoV:s roll själv.
* **FCF är en miniatyr.** Riktiga Future City Flow är en hydrodynamisk MIKE+/MOUSE-modell; här
  är det en enkel överfallsberäkning per brunn. Endast Krokängsparken har en riktig mätserie
  – övriga 90 brunnar får deterministiskt syntetiska serier, öppet redovisat i produkten
  (`dataSource`, `syntheticScale`). Bräddtiden är lika för alla brunnar i modellen och används
  därför inte i prioriteringen.
* **Prioriteringen är en demonstration**, inte en färdig analystjänst: en enkel regel
  (rangordna efter bräddvolym, peka ut de N största) som visar hur ett beslut kan stödjas av
  data som kommit genom ett avtal. Den visar inte att modellen är rätt.
* **Hävningen är en PoC-mekanism.** KoV kan häva ett avtal direkt. Regeln att ett avslag
  av en ny begäran häver tidigare avtal för samma tillgång och part finns men är avstängd i den
  delade demon (`SVADA_KOV_AVSLAG_HAVARTIDIGARE=false`), annars skulle ett avslag häva andra
  besökares avtal. DSP definierar ingen hävning av ett
  slutfört avtal. Statusen synkas från DHI genom att staden läser en smal, skrivskyddad
  statusendpoint hos DHI (egen nyckel, ungefär varje sekund): en förenkling.
* **Allt kör på en maskin.** Organisationsgränsen är compose-projekt och docker-nät.
* **Avtal och beslut ligger i minnet** och nollställs vid omstart.

## 3.5 Om något går fel under demon

Felsökningstabellen i [`02-kom-igang.md`](02-kom-igang.md) §2.6 täcker de vanliga fallen. Två
demospecifika: visar steg 6 "Distribution A kan inte läsas just nu" saknas ett gällande avtal
– kör steg 3 (förhandla A, låt KoV godkänna). Visar steg 6 inga brunnar har ingen leverans
gjorts ännu – kör steg 1, 3 och 4 en gång. Efterarbete efter varje demo: nollställ
felinjektionen.
