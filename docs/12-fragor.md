# 12. Frågor som faktiskt ställs – med korta svar

Frågorna nedan är de som ställs när någon sett SVADA PoC, ordnade efter
frågan. Varje svar är kort och pekar vidare till kapitlet där det står
utförligt. Fyll på efter varje demo – även frågor utan svar hör hemma
här; listan är också mätdata på vad publiken undrar över.

## 12.1 Kedjan och komponenterna

**Varför måste `registrera-edc` köras om efter varje omstart?** EDC kör
in-memory stores – ett medvetet val i resursstrategin för att allt ska
rymmas på en laptop. Assets, policyer, avtal och KoV-besluten ligger i
minnet och nollställs.
→ [`02-kom-igang.md`](02-kom-igang.md) §2.3 · [`08-…`](08-drift-identitet-skalning.md) §8.2

**Vad är egentligen en "connector"?** Ett program som representerar en
deltagare i dataområdet. Provider och consumer kör samma image och öppnar
fyra API-ytor med olika publik – bara DSP-ytan och dataplanet korsar
organisationsgränsen.
→ [`05-dataomradet.md`](05-dataomradet.md) §5.1

**Vad händer när KoV häver ett avtal?** Ett avtal gäller tills det hävs, inte bara för en
datahämtning. När KoV häver avtalet om A nekar DHI:s connector nya överföringar, och stadens
gateway slutar släppa in nycklar som hör till avtalet. Statusen kontrolleras vid varje
användning, så en nyckel som redan finns går inte längre att använda för att hämta data.
Distribution B påverkas inte. Hävningen är en PoC-mekanism: DSP definierar ingen hävning av ett
slutfört avtal.
→ [`koncept/06-kov-gate.md`](koncept/06-kov-gate.md) · G23 i [`10-gapanalys.md`](10-gapanalys.md)

**Varför har avtalet olika id hos DHI och staden?** Så fungerar EDC 0.17.0: varje connector
sparar sin egen avtalspost, och bara förhandlingen binder ihop dem (stadens förhandlings-id är
DHI:s `correlationId`). Det som följer med datat är stadens id; DHI:s id behövs för att häva.
→ [`07-folj-ett-varde.md`](07-folj-ett-varde.md) §7.7

**Vad visar steg 6, och är det en riktig analys?** En enkel inspektionsprioritering: brunnarna
rangordnas efter modellerad bräddvolym och de största pekas ut. Med öppna data (B) ser man
vilka vattendrag som tar emot mest; med skyddade data (A, kräver gällande avtal) ser man vilka
brunnar det gäller och kan lägga dem på en karta. Det är en demonstration av hur avtalet styr
användningen, inte en färdig analystjänst, och datat är delvis syntetiskt.
→ [`03-demo.md`](03-demo.md)

**Vad hände med sensorledet och portalerna?** De ingår inte i Svada-mini. FCF är datakällan och
läser en brunns riktiga värden direkt ur filer; fokus är dataspace och användning av data. Den
tidigare PoC:en med tio steg ingår inte i det här paketet.
→ [`01-oversikt.md`](01-oversikt.md)

## 12.2 Suveränitet, policy och klassning

**Varför sitter KoV-godkännandet hos DHI och inte hos staden?** Därför
att Dataspace Protocol lägger policyverkställigheten hos den som lämnar
ut. Sitter grinden hos mottagaren kan mottagaren öppna den själv.
Consumern har ingen KoV-endpoint alls – testet visar 404.
→ [`05-dataomradet.md`](05-dataomradet.md) §5.3

**Distribution B har ju kvar en koordinat – är inte GIS borttaget?** Det
som tas bort i B är brunnens egen position (`location`/`sourceSrs` på
toppnivå). Koordinaten inuti `outlet` är utsläppspunktens och ska vara
kvar enligt §8.5. Om brunnens läge går att räkna ut ur det som blir kvar
är en öppen fråga som PoC:en inte besvarar.
→ [`07-folj-ett-varde.md`](07-folj-ett-varde.md) §7.3 · G5 i [`10-gapanalys.md`](10-gapanalys.md)

## 12.3 PoC kontra produktion

**Hur skulle Orion-LD se ut i produktion?** Replica set, TLS och
autentisering, backup med prövad återläsning, hypertables med
komprimering. Men huvudsvaret är arkitektoniskt: CIP finns redan och
förvaltas av Intraservice – SVADA lägger ett kontrollplan ovanpå.
→ [`08-drift-identitet-skalning.md`](08-drift-identitet-skalning.md) §8.3

**Hur mycket data blir det på ett år?** Det vet vi inte – en verklig
lucka. PoC:en levererar dygnsaggregat medan arkitekturen specificerar
femminutersupplösning (faktor 288), proveniensen är denormaliserad, och
ingen gallringsregel finns. Gallring kräver ett beslut enligt
Arkivnämnden, ingen konfigurationsrad.
→ G13, G20, G21 i [`10-gapanalys.md`](10-gapanalys.md)

**Är identiteten på riktigt?** Nej. EDC kör `iam-mock` och
management-API:erna går utan autentisering. Hela suveränitetsbeviset
vilar därmed på en mockad identitet – gapanalysens enda kritiska gap.
Ersätts av verifierbar identitet (IdentityHub, DCP).
→ G1 i [`10-gapanalys.md`](10-gapanalys.md) · [`08-…`](08-drift-identitet-skalning.md) §8.1

**Vad krävs för att en tredje kommun ska kunna ansluta?** Tekniskt: en
connector som talar Dataspace Protocol – det är poängen med att
protokollet är åtagandet. Organisatoriskt: en regelbok, federerad
identitet och en dataområdesförvaltare. Det senare är det som saknas.
→ [`08-drift-identitet-skalning.md`](08-drift-identitet-skalning.md) §8.4 · G15

## 12.4 Under demon