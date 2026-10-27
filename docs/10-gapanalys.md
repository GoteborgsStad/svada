# 10. Gapanalys: målarkitekturens krav mot implementationen

> **Svada-mini.** Analysen skrevs för den tidigare PoC:en med tio steg
> (ingår inte i det här paketet). Svada-mini har inget sensorled och inga dataportaler
> (CKAN, skördare, FAIR/MQA). Gapen som gäller metadatakatalogen och portalerna – **G8, G9,
> G18, G19** och substitutionerna CKAN/skördare i §10.4 – samt **G12** (sensor till CIP) är
> därför **inte längre aktuella i kedjan**; de står kvar som historik och som arbete om
> portalerna tas tillbaka. Verifieringsskripten `verify_ap2/5/6a/7` som nämns nedan finns bara
> i den historiska bilden. Nytt: **G23** (hävning av avtal).

**Så här läses analysen.** Ett **gap** är ett krav i *Målarkitektur SVADA
v1.9* som implementationen inte uppfyller. Att ett gap är känt och
planerat (den verifierbara identiteten, separata organisationer) gör det till ett gap med känd åtgärd, aldrig till ett
icke-gap. **Ej gap** är medvetna PoC-avgränsningar där arkitekturens krav
ändå är uppfyllt – till exempel CKAN i stället för EntryScape, där kravet
gäller DCAT-AP-SE-protokollet. **Allvarlighetsgraden** avser risken för
att arkitekturen inte håller i skarp drift, och säger ingenting om hur
svårt gapet är att stänga. Driftegenskaper som arkitekturen inte reglerar
(MQTT-kvalitetsnivåer, replikering, backup) har inga G-nummer – de står i
[`08-drift-identitet-skalning.md`](08-drift-identitet-skalning.md) §8.3.

**Helhetsbilden:** PoC:en uppfyller arkitekturens kontrollplan i hög
grad. De tre invarianterna är realiserade och verifierade – det är kärnan
i dokumentet och den är bevisad. Gapen är koncentrerade till tre områden
som arkitekturen väger lika tungt men PoC:en knappt rör: identitet och
tillit (§6.5), datakvalitet och dataproduktbeskrivning (§5.4, §8.3–8.4)
samt grunddata, betrodda källor och aggregeringsanalys (§5.3, §8.5).

| Allvarlighetsgrad | Antal | Gap |
|---|---|---|
| Kritisk | 1 | G1 |
| Väsentlig | 6 | G2, G3, G4, G5, G10, G15 |
| Måttlig | 8 | G6, G7, G8, G11, G12, G16, G21, G23 |
| Låg | 5 | G13, G17, G18, G19, G20 |
| Åtgärdad | 2 | G9 (stängd 2026-07-24), G22 (stängd 2026-07-28) |

*(Numreringen hoppar över G14 – den punkten visade sig vara en medveten
substitution och står i §10.4.)*

## 10.1 Kritiska och väsentliga gap

**G1 – Identitet och tillit är mockad · Kritisk (delvis stängt: nyckelskyddade API:er, verifierbar DCP-identitet, utfärdare med rätt mandat).** §6.5 kräver
verifierbara attest, kontrollerade maskinellt vid katalogåtkomst,
förhandling och överföring. Implementationen kör `iam-mock`, utan
autentisering på management-API:erna, med självdeklarerade deltagar-id.
Det här är gapet som underminerar alla övriga bevis: ODRL-constrainten
utvärderas mot en sträng motparten själv påstår, och KoV-godkännandet kan
utlösas av vem som helst som når port 19193 – beslutet är anonymt, trots
att §3.4 kräver en namngiven roll. Åtgärd: verifierbar identitet (Keycloak eller
DCP/IdentityHub); testkontraktet finns redan, med negativtest. Fas- och designförslag: [`docs/koncept/C1-identitet.md`](koncept/C1-identitet.md) "Vägen till produktion".

**Läge efter utfärdare med rätt mandat (delvis stängt).** Mock-IAM är borta; deltagare bevisar sig med verifierbara intyg via IdentityHub, och KoV-beslutet kräver ett verifierat rollintyg. Det sista steget rättade ansvarsfördelningen: Svadas utfärdare (simulerad DSGA 0.1) utfärdar medlems- och deltagarintyg, organisationerna intygar sina egna roller, och verifieringen godtar varje intygstyp bara från rätt utfärdare (`supportedtypes`, med två negativa tester). **Återstår:** förankring mot en extern betrodd källa (eIDAS, organisationsnummer), utträde som process (regelboken; återkallelse av intyg finns sedan 2026-10-11, `verify_ap11.sh`), beständiga nycklar, och MVP-topologin med en leverantörsconnector.

**G2 – Kvalitetsdeklarationen saknas i huvudsak · Väsentlig (delvis stängt 2026-10-11: deklarationen finns i katalogen, men inga kvalitetsregler mäts).** §5.4 och §8.4
kräver mätbara kvalitetsregler i sex dimensioner med målnivå och tröskel,
automatisk mätning och publicering i katalogen – §8.4 innehåller till och
med den färdiga tabellen för Modellerad bräddata. Implementationen har
ingenting av detta. PoC:en bevisar att data kan delas kontrollerat, men
en utsaga om att den delade produkten är pålitlig saknas – den andra
halvan av arkitekturens löfte. Inget planerat arbete täcker detta i dag;
fyra av sex dimensioner är mätbara direkt på befintlig data i CIP.

**G3 – Dataproduktspecifikation (DPS) är ett utkast · Väsentlig (delvis stängt 2026-10-11: [`14-dataprodukten.md`](14-dataprodukten.md), ej godkänd av dataägaren).** §8.3 och
§7.1 kräver en DPS per dataprodukt – syfte, datainnehåll, begreppsmodell,
kvalitet, leverans. CKAN-posten bär DCAT-AP-fälten, och de svarar på en
annan fråga: DCAT-AP beskriver *var produkten finns och på vilka
villkor*, DPS beskriver *vad värdena betyder*. Utan DPS är anspråket på
semantisk interoperabilitet obelagt: en mottagare kan hämta
`overflowVolumeM3` men saknar normerad källa för vad det avser och hur
det beräknats. Underlaget finns till stor del i koden; det som saknas är
den förvaltade, publicerade artefakten.

**G4 – Grunddata kopieras i stället för att refereras · Väsentlig.**
§5.3, principen en uppgift en gång: positionsuppgifter hämtas från
utpekade betrodda källor och refereras med stabila identifierare.
Implementationen kopierar in koordinaterna ur testdatats GeoPackage – i
CIP, i Distribution A och i utsläppspunkten i B – och `recipient` är
fritext utan kodlista. Konsekvensen är större än den ser ut: **det är
just de inkopierade positionerna som gör Distribution A känslig och
tvingar fram hela A/B-uppdelningen.** Refererades positionerna i stället
skulle klassningsfrågan se annorlunda ut – åtkomsten till positionen
skulle styras där positionen förvaltas.

**G5 – Aggregeringsanalys och ODRL-villkor mot återskapande saknas ·
Väsentlig.** §8.5 kräver en dokumenterad, av dataägaren godkänd analys av
om borttagna positionsuppgifter kan återskapas genom samkörning med andra
öppna källor, samt ett uttryckligt ODRL-villkor mot återskapande i den
öppna distributionen. Ingetdera finns. Invariant 2 är verifierad som en
**fältkontroll** – att koordinatfälten är borta – men B bär fortfarande
`weirId`, `weirName` (ofta ett gatunamn), `recipient` och
utsläppspunktens koordinater. Kan positionen härledas ur detta faller
invarianten i sak även när den håller i form. Båda delarna är billiga:
en policyrad plus ett verksamhetsbeslut.

**G10 – Spårbarheten är en vy, aldrig ett register · Väsentlig.** §6.6
kräver att varje transaktion loggas hos båda parter som underlag för
revision och tvistlösning. Kontrollrummets auditlogg byggs vid läsning ur
sex källor, hålls i minnet, kapas vid 300 poster och försvinner vid
omstart – och EDC:s egna poster försvinner med providerns in-memory
stores. Revision förutsätter en post som överlever, är attribuerbar och
inte kan skrivas om obemärkt. PoC:en löser numera bitvis det tredje av
de tre kraven (2026-09-02): en hash-kedja (`services/dashboard/audit.py`,
`tests/verify_hash_kedja.sh`) bevisar att kontrollrummets EGEN, redan
hämtade vy av loggen inte kan mixtras med obemärkt. Det skyddar varken
de sex underliggande källorna, är förankrat mot en oberoende extern part,
eller kryptografiskt signerat – och försvinner själv vid omstart precis
som resten av loggen. De två första kraven (persistens, fullständig
attribuerbarhet) är alltså fortsatt olösta. Bör lösas ihop med G1 – en
logg utan identiteter duger ändå inte för tvistlösning – och med G21:s
leveransentitet som registrets objekt.

**G15 – Rulebook och avtalsramverk saknas · Väsentlig
(organisatoriskt).** Bilaga 2 föreskriver en regelbok enligt DSSC:s
modell – deltagarroller, anslutningskrav, standarder, tillitsramverk,
förändringsprocess – och ett avtalsramverk i tre nivåer. Endast
ODRL-policyerna finns. Regelboken är det som gör dataområdet till ett
*område* i stället för en punktintegration: den definierar vad som krävs
för att en tredje part ska få ansluta. Gapet är förväntat i en teknisk
PoC och ska ändå aldrig förväxlas med att vara litet – arkitekturens egen
slutsats är att styrning, roller och kvalitetsarbete avgör framgången mer
än tekniken.

## 10.2 Måttliga gap

**G6 – Nederbördsdata saknas som indata.** §4.3 anger två indata till
modellen (mät- och nederbördsdata); implementationen har en syntetisk
regnterm. Anslutningsmönstret för en andra extern datakälla prövas därmed
aldrig – trots att SMHI är part i SVADA.

**G7 – `SewerOverflowWeir` är ingen publicerad Smart Data Model.**
Modellen är NGSI-LD-formmässigt korrekt men semantiskt lokal. Särskilt
värt att notera: PoC:ens eget kvalitetsverktyg (FAIRness Evaluator)
fäller den maskinellt – gapet är bevisat i den körande miljön.

**G8 – Metadatakvaliteten ligger under ambitionen.** SHACL passerar de
*obligatoriska* shapesen – golvet, aldrig målet. `dct:spatial` och
`dct:temporal` saknas helt, vilket gör en VA-dataprodukt svårupptäckt i
precis de sökningar en konsument gör. Fälten finns i CKAN-schemat men
fylls aldrig – billigt att stänga.

**G11 – Avvikelser skapar ingen incident.** §5.1 kräver att fel skapar
incident i stället för tyst felaktig information, och §5.4 att avvikelser
notifierar datasteward. PoC:en upptäcker utmärkt (avvisningar med spårbar
orsak, avvikelselarm) och reagerar aldrig vidare: ingen eskalering, ingen
mottagare. Kontrollen fungerar bara så länge någon tittar på skärmen.

**G12 – Avvikelsejämförelsen görs i fel lager.** I arkitekturen möts
uppmätta och modellerade värden i **CIP**. I PoC:en stannar mätvärdena
hos DHI, och kontrollrummet gör jämförelsen genom att titta in i båda
organisationerna samtidigt – något ingen part gör i verkligheten.
Pedagogiskt riktigt, arkitektoniskt fel plats, och det döljer en obesvarad
fråga: hur kommer mätdata in i CIP? Kedjan sensor → CIP är obyggd.

**G16 – Organisationsgränsen och driftegenskaperna är simulerade.** En
maskin, docker-nät, ingen TLS, inga certifikat, ingen latens, in-memory
stores. Frågorna en driftorganisation ställer först – vilka portar öppnas
åt vilket håll, hur hanteras certifikat, vad händer vid omstart mitt i en
förhandling – saknar svar. Känt och avgränsat (separata organisationer med eget tillitsramverk, planerat, samt persistenspåslaget).

**G21 – Proveniensen är denormaliserad och versionsförs per leverans.**
Mätt: 519 byte proveniens per entitet, 52 instanser i historiken för en
enda brunn, ≈ 2,9 MB totalt. Tre konsekvenser: uppdateringsanomalier
(en rättelse kräver omskrivning av 91 entiteter gånger historiken),
lagring som växer med produkten av tre faktorer, och ingen
leveransentitet för G10:s register att peka på. En kärna måste ändå följa
med datat (`informationClass`, `accessRights`, `license`,
`contractAgreementId` – en nedladdad öppna data-fil ska bära sin licens);
resten hör i produktion hemma i en leveransentitet enligt
PROV-O-mönstret. Det beskrevs i den tidigare tiostegsversionen, som inte ingår i det här paketet.

## 10.3 Låga gap

| # | Punkt | Läge | Bedömning |
|---|---|---|---|
| G13 | Lagring och gallring (§5.1: enligt Arkivnämndens beslut) | Ingen gallringsregel; "retention" är minnestak utan rättslig koppling | Låg för PoC, verkligt krav med legal grund före produktion |
| G17 | Modellens realism | Enkel överfallsberäkning; 90 av 91 syntetiska serier | Låg – medveten avgränsning, väl hanterad: redovisas i produkten (`dataSource`, `syntheticScale`), precis vad §8.4 "kända brister" kräver |
| G18 | Höjdreferens | `unitCodes` finns; RH2000 nämns ingenstans, `waterLevelMaxM` saknar höjdreferens | Låg, trivial att stänga – nivåvärden utan referens är formellt otolkbara |
| G19 | Klassning av metadata (§7.2: separat) | Datat klassas; metadataposten klassas aldrig separat | Låg |
| G20 | Tidsupplösning (§8.2: fem minuter) | Dygnsaggregat levereras | Måttlig–låg: protokollmässigt identisk kedja, innehållsmässigt en annan produkt – och flera av §8.4:s kvalitetsregler blir omätbara |
| G23 | Hävning och utgång av avtal | Hävning är en PoC-mekanism (avslag häver tidigare avtal, KoV-knapp); DSP definierar ingen hävning av ett slutfört avtal; statusen synkas genom att staden pollar en smal, skrivskyddad statusendpoint hos DHI med egen nyckel (inte management-API:t) | Måttlig – i drift ska hävning och statusspridning gå genom protokollet eller en statuslista, inte genom att en stadstjänst pollar providern; kräver också beständig lagring av avtal och hävningar |
| G24 | Engelska versionen | Kontrollrummet och den publika vyn finns på engelska; händelser lagras som kod och parametrar och visas ur en meddelandekatalog (`meddelanden.py`); formell text är engelsk, data svenskt | Låg – gatewayens HTML-sida, identitetsverifieringens felsvar och exempelobjektens datavärden är svenska |

## 10.4 Åtgärdade gap och medvetna substitutioner

**G22 – Stadens utlämning av Distribution A var oskyddad · Åtgärdad
2026-07-28.** Kravet var uppfyllt på *överlämningen* – KoV-gaten i
providern och ingest-servicens mottagningskontroll var båda på plats och
verifierade. Men efter transfern låg A-datat i stadens CIP, och
`orion-stad` publicerade port 2026 rakt ut på värden utan någon kontroll
alls: den som följde Distribution A:s `accessURL` i katalogen fick alla 91
bräddbrunnars fulla GIS i klartext. `access-right/NON_PUBLIC` var en
etikett utan verkställighet, och det var den enda punkt i kedjan där
informationsklassningen kunde brytas utan att något system reagerade.
Fyndet kom av det motsägelsefulla beteendet: den *öppna* distributionen B
svarade 400 i en webbläsare (G9) medan den *icke-offentliga* A svarade 200
med data. Åtgärden är den nya tjänsten `stad-gateway`, som tar över
portkartans 2026; `orion-stad` publicerar ingen port och har lämnat
`dsp-public`. Liveness är öppen, all läsning och skrivning kräver token,
och token fås genom att växla ett kontraktsavtal för Distribution A hos
stadens egen connector – ett sådant avtal finns bara om providerns
KoV-gate släppte igenom förhandlingen. Avslag går att läsa: HTML till en
webbläsare, NGSI-LD-format till en maskin, ingen koordinat i något av dem.
Hård regel 7 är intakt – providern äger fortfarande beslutet om ett avtal
får ingås; detta är stadens konsumtionskontroll över data den redan tagit
emot. Drifttoken för stadens egna komponenter är märkt `MEDVETEN
FÖRENKLING – ersätts i …`, så G22 delar **G1**:s identitetsberoende:
gaten verkställer rätt regel, men vet inte säkert vem som knackar.
Verifieras av `verify_ap1.sh` 1.8 (13 kontroller) och, i den tidigare PoC:en, `verify_ap5.sh` 5.12.

**G9 – Distribution B:s `accessURL` svarade HTTP 400 · Åtgärdad
2026-07-24.** Två oberoende fel: Mintaka avvisar en webbläsares
`Accept`-huvud (kontrollen sker före allt annat), och tidsrelationen
saknades i adressen. Metadataprincipen var formellt uppfylld och
funktionellt bruten – en länk som inte gick att följa. Det intressanta är
hur defekten hittades: varken SHACL-valideringen eller de två
skördestegen såg den, utan först FAIR-/MQA-lagret – i sig ett argument
för att kvalitetslagret behövs. Åtgärden följde DCAT-AP:s egen modell,
en distribution per representation: tidsparametrar i API-adressen plus
den nya tjänsten `publik-vy` (`:8085`). Mätbar effekt: Tillgänglighet
0 → 50, totalpoäng 250 → 280 av 405. Verifierades av `verify_ap5.sh` 5.11 i den tidigare PoC:en.

**Medvetna substitutioner – ej gap i kravmening:** CKAN i stället för
EntryScape (kravet gäller DCAT-AP-SE-profilen, uppfyllt och
SHACL-verifierat; EntryStores eget valideringsbeteende är dock oprövat),
egna skördare i stället för dataportal.se/data.europa.eu (skördekedjan
transitiv, endast PUBLIC, endast metadata – verifierat; Diggs
anslutningsprocess är oprövad, och billigaste kontrollen är att skicka
`catalog.ttl` till Diggs publika validator), samt Eclipse EDC 0.17.0 med
DSP 2025-1 (kravet uppfyllt fullt ut – kedjans starkaste led).

## 10.5 Rekommenderad prioritering

| Ordning | Gap | Motiv |
|---|---|---|
| 1 | G1 (identitet) | Planerad som verifierbar identitet med färdigt testkontrakt. Allt annat vilar på detta |
| 2 | G5 (ODRL-villkor + aggregeringsanalys) | Halva gapet är en policyrad; andra halvan ett verksamhetsbeslut som ändå måste fattas. Rör invariant 2 direkt |
| 3 | G2 + G3 (kvalitetsdeklaration + DPS) | Störst avstånd mellan löfte och bevis; inget planerat arbete täcker dem i dag |
| 4 | G8 + G18 (metadatakvalitet, RH2000) | Billiga och mätbara – MQA-poängen visar effekten direkt |
| 5 | G4 (grunddata och betrodda källor) | Kräver verksamhetsbeslut om betrodd källa; påverkar A/B-uppdelningen i grunden |
| 6 | G12 + G6 (mätdata in i CIP, nederbörd) | Bygger ut kedjan till arkitekturens fulla bild |
| 7 | G16 + G10 + G21 (organisationsgräns, persistent spårbarhet, leveransentitet) | Separata organisationer (planerat) + persistenspåslaget; naturligt efter G1, och G10/G21 bör lösas ihop |
| 8 | G15 (rulebook) | Löper parallellt som verksamhetsarbete; måste finnas innan en tredje part ansluter |
