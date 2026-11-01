# C7. Nedladdning: se att det är riktig data bakom

> Att läsa om en leverans är inte samma sak som att se den. Varje steg i kontrollrummet har därför
> en ruta "Ladda ned det som passerar det här steget", och brunnsvyn och datamodellen har
> motsvarande filer. Syftet är dubbelt: besökaren kan **kontrollera** att datat är det som kedjan
> faktiskt har, och förstå mer genom att **se hur det ser ut**.

## Principer

1. **Faktiskt, inte inspelat.** En fil är det som steget just nu har: mätvärdena modellen räknar på,
   leverantörens katalog, besökarens egna avtal, leveransen som togs emot, posterna i stadens
   plattform, analysens rangordning. Det som bara är referens (ordlistan, MIM-bedömningen) märks
   som det i svarshuvudet `X-Svada-Art`.
2. **Samma åtkomst som sidan.** Distribution B är öppen. Distribution A, och allt med brunns-GIS,
   kräver ett gällande avtal för besökaren. Modulen har ingen egen åtkomstlogik: den återanvänder
   analysens (`analys.senaste_gallande_a_avtal`). Distribution A är inte hemlig i demon
   (koordinaterna är påhittade) men är icke-publik: filnamnet bär `DISTRIBUTION-A-ej-for-spridning`
   och svarshuvudet `X-Svada-Klass: K1R1T1`. Regel 8 (som den lyder i Svada-mini) gäller: A går inte att läsa ur
   stadens plattform utan ett gällande avtal, och ingen komponent flyttar data förbi kontraktet.
3. **Kontrollsumma.** Varje svar bär SHA-256 av exakt de byte som skickas (`X-Content-SHA256`),
   och sidan visar summan efter nedladdningen. För leveransen (steg 4) är summan den som
   ingest-service räknade när leveransen togs emot, och samma summa står i auditloggen
   (`detaljer.sha256`). Då går filen att jämföra byte för byte med det som gick genom kedjan.
4. **Inget internt.** I den externa varianten rensas filerna med samma regler som sidorna
   (`gemensam/rensa.py`: containernamn, portar, DID-namn). Leveransen skrivs aldrig om, eftersom
   poängen är att den är oförändrad. En fil som ändå innehåller något internt vägras (stängt som
   standard, HTTP 500).
5. **Spår.** Varje nedladdning ger en rad i auditloggen: vad, filnamn, storlek och summa, inte vem.

## Var det finns

| Steg | Filer |
|---|---|
| 1 | mätvärdena modellen räknar på (JSON, CSV). Batchen själv hämtas aldrig av kontrollrummet (6b.9): den når staden bara genom avtalet och laddas ned i steg 4 |
| 2 | katalogen (JSON-LD), deltagarregistret |
| 3 | besökarens avtal, villkoren för B och A (ODRL) |
| 4 | den mottagna leveransen för B och A, schemakontrollens resultat |
| 5 | posterna i stadens plattform för B och A |
| 6 | analysen för B (CSV, JSON) och för A (CSV, GeoJSON) |
| Ordlistan | ordlistan och MIM-bedömningen (JSON) |
| Brunnsvyn | `/brunnar?format=csv\|json`, `/brunnar/<id>?format=csv\|json` |
| `/modell` | `utkast.zip` (alla filer, `MANIFEST.json` med SHA-256 per fil och en LÄS-MIG som säger utkast), `termlista.csv` |

Koden: `services/dashboard/nedladdning.py` (registret `POSTER`, API:t `/api/ladda-ned/{id}`),
`services/publik-vy/filer.py` och `services/publik-vy/modell.py` (`genererad`),
`services/ingest-service/main.py` (`/leveranser/{avtal}/innehall`, summan vid mottagandet).

## Begränsningar

* Leveransen sparas i ingest-services minne (högst 30 avtal, äldst faller först) och försvinner
  vid omstart. Det är samma hållning som resten av demon.
* 90 av 91 brunnars serier är påhittade; filerna säger inte det själva. Det står på Om-sidan.
* Kontrollsumman visar att filen är det som kedjan skickade, inte att modellen är riktig.

## Verifiering

`tests/nedladdning_enhet.py` (K39, utan stack) och avsnitt K40 i `tests/verify_kedjevy.sh` (mot
stacken: kontrollsumma i huvud = filens, leveransens summa = auditloggens, inga interna adresser,
A följer avtalet, zip-manifestet stämmer, zip-filen är densamma vid varje hämtning). Webbläsaren:
`tests/kedjevy_webblasare.mjs`.
