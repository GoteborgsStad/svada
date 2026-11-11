// kedjevy_webblasare.mjs – webbläsartest av kontrollrummets kedjevy.
//
// Öppnar den körande dashboarden i en riktig (headless) Chrome via
// playwright-core och prövar det som bara syns i en webbläsare: djuplänkar,
// tangentbord, språkbyte, JS-fel, horisontell scroll i 1280/800/400 px,
// listvyn under 1100 px, KoV-rutan (utan blink), inspektionsprioriteringen i steg 6
// och att steg 5 visar ett värde ur distribution B med det avtal dess id pekar på. Körs mot den EXTERNA varianten (samordnarrutan har där
// ett inspelat exempel i stället för knappar). Skriver [OK]/[FEL] och avslutar
// med antalet fel.
// SIDOEFFEKTER (del e, E9): testet startar batchjobb och skickar ett nekat (403) försök att stänga ute staden via Caddy-vägen (samordnarens knappar
// finns bara i den interna varianten och prövas i fixturen), och
// det mesta i övrigt prövas mot mockade svar. Kör det bara mot en lokal stack som ingen annan använder.
//
//   cd tools && npm install        (hämtar playwright-core)
//   DASH=http://localhost:38800 CHROME="/sökväg/till/chrome" node tests/kedjevy_webblasare.mjs
import { createRequire } from 'node:module';
const require = createRequire(new URL('../tools/', import.meta.url));
const { chromium } = require('playwright-core');

const DASH = process.env.DASH || 'http://localhost:8800';
const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium'].find(p => { try { require('node:fs').accessSync(p); return true; } catch { return false; } });
let fel = 0;
const kolla = (ok, text) => { console.log(`  [${ok ? 'OK' : 'FEL'}] ${text}`); if (!ok) fel++; };
// Delkörning: ONLY=bubblor,guiderad kör bara de blocken (namnen står i `if (kor('…'))` och 'grund' är allt före Smal skärm).
// Utan ONLY körs allt. Slutkontrollen av sidfel körs alltid.
const ONLY = (process.env.ONLY || '').split(',').map(x => x.trim()).filter(Boolean);
const sedda = new Set();   // alla blocknamn som kor() frågats om, så att ett okänt namn i ONLY underkänns
const kor = namn => { sedda.add(namn); return !ONLY.length || ONLY.includes(namn); };
// Stadens KoV-kö hos providern är gemensam och kan innehålla en väntande förfrågan från en tidigare körning. Block som prövar Nästa-knappen
// mockar den som tom, så att provet inte beror på kvarlämnat läge.
const kovTom = pg => pg.route('**/api/kov', r => r.fulfill({ json: { forhandlingar: [] } }));

const b = await chromium.launch({ executablePath: CHROME, headless: true });
const jsfel = [];
// Provsidor som fångar sidfel i jsfel: slutkontrollen längst ned underkänner allt som hamnat där, även från sena block.
// Hämtar det riktiga svaret för en route som ändrar det. Tappar dashboarden anslutningen (belastning, omstart) fortsätter anropet orört
// i stället för att ett obehandlat undantag fäller hela testet.
const hamtaEkta = async r => { try { return await (await r.fetch()).json(); } catch (e) { await r.continue().catch(() => {}); return null; } };
// A är startläge: för att prova bytet till A väljs B först (utan att läsa om), sedan klickas A så att en riktig change utlöses.
const valjA = async pg => { await pg.evaluate(() => { document.querySelector('input[name="analyslage"][value="b"]').checked = true; }); await pg.click('input[name="analyslage"][value="a"]'); };
const ny = async (namn, villkor) => { const pg = await b.newPage({ locale: 'sv-SE', ...villkor }); pg.on('pageerror', e => jsfel.push(`${namn}: ${e.message}`)); return pg; };
// Väntar högst STILLA_MAX ms (taket sattes vid gallringen 2026-11-11) och därefter tills nätverket är tyst, så att en långsam maskin inte ger en tidsrace.
// Gallring 2026-11-11: den fasta delen är högst STILLA_MAX ms (standard 1200); resten avgörs av networkidle. STILLA_MAX=4000 ger gamla beteendet.
const STILLA_MAX = Number(process.env.STILLA_MAX || 1200);
const stilla = async (sida, ms) => { await sida.waitForTimeout(Math.min(ms, STILLA_MAX)); await sida.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {}); await sida.waitForTimeout(250); };
// Väntar tills sidans höjd varit oförändrad tre mättillfällen i rad (innehåll som laddas efter sidstart ändrar höjden).
const stabil = async sida => { let f = -1, lika = 0; for (let i = 0; i < 40 && lika < 3; i++) { const h = await sida.evaluate(() => document.documentElement.scrollHeight); lika = h === f ? lika + 1 : 0; f = h; await sida.waitForTimeout(250); } };
// Självprov av testet: PLANTERA_SIDFEL=<blocknamn,…> kastar ett asynkront sidfel i det blocket, och testet måste då underkännas.
const plantera = async (pg, namn) => { if ((process.env.PLANTERA_SIDFEL || '').split(',').includes(namn)) await pg.evaluate(() => setTimeout(() => { throw new Error('planterat sidfel'); }, 50)); };
if (kor('grund')) {   // blocket "grund": breddprov, övervakning, steg 1–6 och Nästa-knappen på en sida (kan inte delas utan omskrivning)
for (const bredd of [1280, 800, 400]) {
  const p = await b.newPage({ locale: 'sv-SE', viewport: { width: bredd, height: 900 } });
  p.on('pageerror', e => jsfel.push(`${bredd}px: ${e.message}`));
  await p.goto(`${DASH}/?lang=sv#steg-6`); await stilla(p, 2500);
  kolla(await p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
        `${bredd} px: ingen horisontell scroll`);
  const lista = await p.evaluate(() => getComputedStyle(document.querySelector('#bild')).display === 'flex');
  kolla(lista === (bredd <= 1100), `${bredd} px: ${bredd <= 1100 ? 'listvy' : 'kedjebild'}`);
  if (bredd <= 1100) {
    const brutna = await p.evaluate(() => [...document.querySelectorAll('.nod .titel')].filter(t => {
      const o = t.scrollWidth > t.clientWidth + 1; return o; }).length);
    kolla(brutna === 0, `${bredd} px: inga nodtitlar som flödar över`);
  }
  kolla(await p.evaluate(() => !document.getElementById('steg-6').hidden && location.hash === '#steg-6'),
        `${bredd} px: #steg-6 öppnar steg 6`);
  await p.close();
}

const p = await b.newPage({ locale: 'sv-SE', viewport: { width: 1280, height: 900 } });
p.on('pageerror', e => jsfel.push(e.message));
// Nätverksövervakningen registreras FÖRE första navigeringen, så att automatiska externa anrop vid sidstart syns.
const externa = [];
const overvaka = (sida, lista) => sida.on('request', r => {
  const u = new URL(r.url());
  if (!['localhost', '127.0.0.1'].includes(u.hostname) && u.protocol.startsWith('http')) lista.push(u.host);
});
overvaka(p, externa);
{ // Övervakningen själv: ett simulerat externt startanrop (blockeras lokalt, ingen verklig kontakt) ska upptäckas.
  const p2 = await b.newPage({ locale: 'sv-SE' }); const ext2 = [];
  overvaka(p2, ext2);
  await p2.route('**://cdn.invalid.example/**', r => r.abort());
  await p2.setContent('<img src="https://cdn.invalid.example/x.png">'); await p2.waitForTimeout(600);
  kolla(ext2.includes('cdn.invalid.example'), 'övervakningen upptäcker ett externt anrop vid sidstart (simulerat och blockerat lokalt)');
  await p2.close();
}
await p.goto(`${DASH}/?lang=sv#steg-1`); await stilla(p, 2500);
kolla(/UTC/.test(await p.textContent('#sammanfattning')), 'sidhuvudets tid anges i UTC');
await p.keyboard.press('ArrowRight');
kolla(await p.evaluate(() => location.hash) === '#steg-2', 'pil höger öppnar steg 2');
/* Pilarna byter steg inte med modifierartangent eller när fokus står inne i panelen. */
await p.keyboard.press('Alt+ArrowRight');
kolla(await p.evaluate(() => location.hash) === '#steg-2', 'Alt+pil byter inte steg');
await p.evaluate(() => document.querySelector('#steg-2 button, #steg-2 summary')?.focus());
await p.keyboard.press('ArrowRight');
kolla(await p.evaluate(() => location.hash) === '#steg-2', 'pil inne i panelen byter inte steg');
/* Status och flikrad är namngivna för skärmläsare, inte bara färg. */
const statusnamn = await p.getAttribute('#nod-1 .status', 'aria-label');
kolla(!!statusnamn && statusnamn.length > 10, `stegets status har ett textnamn ('${statusnamn}')`);
kolla(await p.getAttribute('nav#flikar', 'aria-label') === 'Flikar', "flikraden heter 'Flikar'");
await p.keyboard.press('Escape');
kolla(await p.evaluate(() => document.querySelectorAll('.panel:not([hidden])').length) === 0, 'Esc stänger panelen');
// Steg 6: inspektionsprioriteringen. Läge B är öppet; läge A kräver ett gällande avtal.
await p.goto(`${DASH}/?lang=sv#steg-6`);
kolla(await p.evaluate(() => document.querySelector('input[name="analyslage"]:checked')?.value) === 'a'
      && await p.evaluate(() => document.querySelectorAll('.lagevaljare label.seg').length) === 2, 'steg 6: distribution A är startläge och växlingen är en tydlig tvåvalsknapp (A, B)');
kolla(await p.waitForFunction(() => !!(window.L && window.L.map) && !!document.querySelector('link[rel="preconnect"][href*="tile.openstreetmap.org"]'), null, { timeout: 8000 }).then(() => true).catch(() => false),
      'steg 6: kartan förvärms när steget öppnas (kartbiblioteket laddat och anslutningen till kartplattorna förberedd)');
await p.click('input[name="analyslage"][value="b"]');
await p.waitForSelector('#analysresultat table.analystabell', { timeout: 25000 }).catch(() => {});
const antalRader = await p.evaluate(() => document.querySelectorAll('#analysresultat table.analystabell tr.inspektera').length);
kolla(antalRader >= 1 && antalRader <= 10, `steg 6 (B): ${antalRader} brunnar pekas ut för inspektion (högst 10)`);
kolla(await p.evaluate(() => !!document.querySelector('#analysstatus a[href*="/avtal/"]')),
      'steg 6 (B): raden bär sitt ursprung (länk till avtalet)');
kolla(await p.evaluate(() => !document.querySelector('svg.karta')), 'steg 6 (B): ingen karta, positionerna ingår inte i B');
await p.evaluate(() => { document.querySelector('#analystopp').value = '3'; });
await p.dispatchEvent('#analystopp', 'change');
await p.waitForFunction(() => document.querySelectorAll('#analysresultat table.analystabell tr.inspektera').length <= 3, null, { timeout: 15000 }).catch(() => {});
kolla(await p.evaluate(() => document.querySelectorAll('#analysresultat table.analystabell tr.inspektera').length) <= 3,
      'steg 6: att ändra antalet brunnar ändrar urvalet');
// F8 (fientliga testet 2026-10-19): 1e9 är ett stort tal och ska bli 91 som ett långt heltal, inte 1 (parseInt läste bara "1").
await p.evaluate(() => { document.querySelector('#analystopp').value = '1e9'; });
await p.dispatchEvent('#analystopp', 'change'); await stilla(p, 1500);
kolla(await p.inputValue('#analystopp') === '91', 'steg 6: antalet 1e9 blir 91 (högsta), inte 1');
await p.evaluate(() => { document.querySelector('#analystopp').value = '3.7'; });
await p.dispatchEvent('#analystopp', 'change'); await stilla(p, 1500);
kolla(await p.inputValue('#analystopp') === '3', 'steg 6: antalet 3,7 avrundas nedåt till 3');
// F11: kartetiketterna ska formatera volymen som resten av sidan (decimalkomma på svenska), inte skriva ut det råa talet.
kolla(!(await p.content()).includes('${r.volymM3} m³'), 'steg 6: kartetiketten formaterar volymen med tal() (decimalkomma), inte rått');
// Läge A med mockade svar: hävt avtal -> tydligt nekat, B fungerar; gällande avtal -> karta.
const mockRad = (i, v) => ({rang: i, id: 'SSO1_01-' + i, namn: 'brunn ' + i, volymM3: v, toppM3S: 0.1, nivaM: 0.1, tidMin: 155,
  recipient: 'Göta Älv', utslapp: 'G1', inspektera: i <= 2, position: [11.99 + i / 1000, 57.69 + i / 1000]});
const A = {lage: 'A', topp: 2, blockerad: null, avtal: {id: 'aaaaaaaa-1', status: 'GALLANDE'},
  rader: [mockRad(1, 900), mockRad(2, 800), mockRad(3, 100)], perRecipient: [{recipient: 'Göta Älv', brunnar: 3, volymM3: 1800, utslapp: ['G1']}],
  ursprung: {avtal: 'aaaaaaaa-1', batch: 'batch-1', distribution: 'A', klass: 'K1R1T1'},
  sammanfattning: {brunnar: 3, braddar: 3, totalVolymM3: 1800, hogstaVolymM3: 900, samtligaTidLika: true}};
await p.route('**/api/analys?lage=a*', r => r.fulfill({json: A}));
kolla(externa.length === 0, 'inget externt anrop under första sidladdningarna och steg 6' + (externa.length ? ' (' + externa.join(', ') + ')' : ''));
// Kartbakgrunden från OpenStreetMap visas alltid när brunnarna ur A visas (ingen knapp, ingen valfrihet).
// Plattorna ersätts här av en stubb så att provet inte behöver nätet; anropen registreras ändå av nätverksövervakningen.
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
await p.route('https://*.openstreetmap.org/**', r => r.fulfill({status: 200, contentType: 'image/png', body: PNG}));
await valjA(p); await stilla(p, 1800);
await p.waitForFunction(() => document.querySelector('svg.karta')?.style.display === 'none', null, { timeout: 12000 }).catch(() => {});
kolla(externa.length > 0 && externa.every(h => /openstreetmap\.org$/.test(h)),
      'steg 6 (A): kartbakgrunden hämtas automatiskt och anropen går bara till OpenStreetMap (' + [...new Set(externa)].join(', ') + ')');
kolla(await p.evaluate(() => document.querySelector('svg.karta')?.style.display === 'none' && !!document.querySelector('#osmkarta') && !document.querySelector('#osmkarta').hidden),
      'steg 6 (A): kartplattorna ersätter den schematiska kartan utan att besökaren väljer något');
kolla(await p.evaluate(() => !document.querySelector('#kartbakgrund')), 'steg 6 (A): det finns ingen knapp för kartbakgrunden');
kolla(await p.evaluate(() => !/Hämtar kartplattor från OpenStreetMap: OpenStreetMap ser då/.test(document.body.textContent)), 'steg 6 (A): ingen infotext om att besökaren behöver välja kartbakgrund');
// Ett identiskt analyssvar ska rita om kartan (cachen får inte hoppa över den): kartan finns kvar, antingen som plattor eller som schematisk karta.
kolla(await p.evaluate(() => !document.querySelector('#analysruta button[onclick="laddaAnalys()"]')), 'steg 6: ingen Uppdatera-knapp (analysen uppdateras vid varje ändring)');
await p.evaluate(() => laddaAnalys()); await stilla(p, 2500);
kolla(await p.evaluate(() => { const s = document.querySelector('svg.karta'); const o = document.querySelector('#osmkarta');
        return (!!o && !o.hidden) || (!!s && s.getBoundingClientRect().width > 0); }),
      'steg 6 (A): Uppdatera med identiskt svar visar kartan igen (plattor eller schematisk)');
// F11: etiketterna för de fem främsta överlappar inte, även när brunnarna ligger tätt (krockkontroll i visaKartbakgrund).
{
  const tat = i => ({...mockRad(i, 1000.25 - i * 10), inspektera: i <= 5, position: [11.9918 + (i % 3) * 0.00025, 57.6943 + (i % 2) * 0.0002]});
  await p.unroute('**/api/analys?lage=a*');
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: {...A, topp: 5, rader: [1, 2, 3, 4, 5, 6].map(tat)}}));
  await p.evaluate(() => laddaAnalys()); await stilla(p, 1800);
  await p.waitForFunction(() => document.querySelectorAll('.leaflet-tooltip').length >= 5, null, { timeout: 12000 }).catch(() => {});
  await p.waitForTimeout(800);
  const rutor = await p.$$eval('.leaflet-tooltip', ts => ts.map(t => { const b = t.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }));
  let overlapp = 0;
  for (let i = 0; i < rutor.length; i++) for (let j = i + 1; j < rutor.length; j++) {
    const a = rutor[i], c = rutor[j];
    if (a[0] < c[2] && c[0] < a[2] && a[1] < c[3] && c[1] < a[3]) overlapp++;
  }
  kolla(rutor.length === 5 && overlapp === 0, `steg 6 (A): de fem etiketterna på kartan överlappar inte varandra (${rutor.length} etiketter, ${overlapp} överlapp)`);
  const texter = await p.$$eval('.leaflet-tooltip', ts => ts.map(t => t.textContent));
  kolla(texter.length === 5 && texter.every(t => /\d,\d/.test(t) && !/\d\.\d/.test(t)), `F11: kartetiketterna har decimalkomma på svenska (${texter[0]})`);
}
// F1: steg 6 läser om när avtalet om A slutar gälla (statusrundan bär avtalA), och kartan öppnas aldrig på cachade positioner.
{
  const A_BLOCK = {lage: 'A', topp: 2, blockerad: {orsak: 'avtal-havt', avtal: 'aaaaaaaa-1', havning: {orsak: 'EXPLICIT', tid: '2026-10-19T10:00:00Z'}}, rader: [], perRecipient: [], avtal: null};
  let avtalGaller = true;
  await p.unroute('**/api/analys?lage=a*');
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: A}));
  await p.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.avtalA = {gallande: avtalGaller}; r.fulfill({json: j}); });
  await p.evaluate(() => { document.querySelector('input[name="analyslage"][value="a"]').checked = true; laddaAnalys(); }); await stilla(p, 1800);
  kolla(await p.evaluate(() => !!document.querySelector('svg.karta') || !!document.querySelector('#osmkarta:not([hidden])')), 'F1: steg 6 visar positioner ur A medan avtalet gäller');
  avtalGaller = false;
  await p.unroute('**/api/analys?lage=a*');
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: A_BLOCK}));
  await p.waitForFunction(() => !document.querySelector('svg.karta') && !document.querySelector('#osmkarta:not([hidden])') && /kan inte läsas/.test(document.querySelector('#analysresultat').textContent), null, {timeout: 12000}).catch(() => {});
  kolla(await p.evaluate(() => !document.querySelector('svg.karta') && /kan inte läsas/.test(document.querySelector('#analysresultat').textContent)),
        'F1: när avtalet om A slutar gälla ersätts positionerna av nekandet inom en statusrunda, utan att besökaren klickar');
  // kartkontrollen: avtalet hävs utan att statusrundan hunnit märka det (flaggan förblir true); sidans svar visar A men kontrollen
  // som görs innan kartan ritas får nekandet, och då öppnas ingen karta.
  avtalGaller = true;
  await p.unroute('**/api/analys?lage=a*');
  let anrop = 0;
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: (anrop++ === 0) ? A : A_BLOCK}));
  await p.evaluate(() => laddaAnalys()); await stilla(p, 2500);
  kolla(await p.evaluate(() => !document.querySelector('#osmkarta') || document.querySelector('#osmkarta').hidden) && await p.evaluate(() => /kan inte läsas/.test(document.querySelector('#analysresultat').textContent)),
        'F1: kartan kontrollerar avtalet mot servern först; en hävning gör att kartan inte öppnas');
  await p.unroute('**/api/status*');
  await p.unroute('**/api/analys?lage=a*');
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: A}));
}
// F1 (andra granskningen): även i analysläge B visar rutan "samma brunn i B och A" A:s position, och den ska försvinna när avtalet
// om A slutar gälla utan att besökaren klickar.
{
  let galler = true;
  const jamfor = () => ({brunn: 'SSO1_01-4526', B: {rad: {...mockRad(1, 365.22), distribution: 'B', klass: 'K0R1T1', position: null}, blockerad: null, avtal: null},
    A: galler ? {rad: {...mockRad(1, 365.22), distribution: 'A', klass: 'K1R1T1'}, blockerad: null, avtal: null} : {rad: null, blockerad: {orsak: 'avtal-havt'}, avtal: null}});
  await p.route('**/api/analys/brunn*', r => r.fulfill({json: jamfor()}));
  await p.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.avtalA = {gallande: galler}; r.fulfill({json: j}); });
  await p.evaluate(() => { document.querySelector('input[name="analyslage"][value="b"]').checked = true; laddaAnalys(); }); await stilla(p, 1800);
  kolla(await p.evaluate(() => /\d+\.\d{4}/.test(document.querySelector('[data-jamfor="A"]')?.textContent || '')), 'F1: i läge B visar "samma brunn" A:s position medan avtalet gäller');
  galler = false;
  await p.waitForFunction(() => /Nekad/.test(document.querySelector('[data-jamfor="A"]')?.textContent || '') && !/\d+\.\d{4}/.test(document.querySelector('[data-jamfor="A"]')?.textContent || ''), null, {timeout: 12000}).catch(() => {});
  kolla(await p.evaluate(() => /Nekad/.test(document.querySelector('[data-jamfor="A"]')?.textContent || '') && !/\d+\.\d{4}/.test(document.querySelector('[data-jamfor="A"]')?.textContent || '')),
        'F1: även i läge B ersätts A:s position i "samma brunn" av nekandet när avtalet slutar gälla, utan att besökaren klickar');
  await p.unroute('**/api/analys/brunn*');
  await p.unroute('**/api/status*');
  await p.evaluate(() => { document.querySelector('input[name="analyslage"][value="a"]').checked = true; });    // de följande proven utgår från läge A
}
await p.unroute('https://*.openstreetmap.org/**');
await p.route('https://*.openstreetmap.org/**', r => r.abort());    // aldrig ut på nätet; en dold SVG skulle göra krockproven tomma
await p.unroute('**/api/analys?lage=a*');
await p.route('**/api/analys?lage=a*', r => r.fulfill({json: {lage: 'A', topp: 2, rader: [], perRecipient: [], avtal: null,
  blockerad: {orsak: 'avtal-havt', avtal: 'aaaaaaaa-1', havning: {orsak: 'EXPLICIT', tid: '2026-10-10T13:01:01Z'}}}}));
await p.dispatchEvent('input[name="analyslage"][value="a"]', 'change'); await stilla(p, 1500);
const nekad = await p.textContent('#analysresultat');
kolla(/hävts av KoV/.test(nekad) && /Distribution B är öppen/.test(nekad) && !(await p.evaluate(() => !!document.querySelector('svg.karta'))),
      'steg 6 (A, hävt avtal): nekat i klartext, ingen karta, B pekas ut som fungerande');
await p.unroute('**/api/analys?lage=a*');
{ // Kartan: etiketterna får inte ligga över varandra, även när brunnarna ligger tätt.
  const rader10 = Array.from({length: 10}, (_, i) => ({rang: i + 1, id: 'SSO1_01-' + (6700 + i), namn: 'b' + i, volymM3: 900 - i * 10, toppM3S: 0.1,
    nivaM: 0.1, tidMin: 155, recipient: 'Göta Älv', utslapp: 'G1', inspektera: true, position: [11.9900 + (i % 4) * 0.00006, 57.6900 + Math.floor(i / 4) * 0.00004]}));
  const A10 = {...A, rader: rader10, topp: 10, sammanfattning: {...A.sammanfattning, brunnar: 10}};
  await p.route('**/api/analys?lage=a*', r => r.fulfill({json: A10}));
  await p.dispatchEvent('input[name="analyslage"][value="a"]', 'change'); await stilla(p, 1500);
  const krock = await p.evaluate(() => {
    const t = [...document.querySelectorAll('svg.karta text')].filter(x => /^SSO1_/.test(x.textContent)).map(x => x.getBoundingClientRect());
    let n = 0;
    for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) {
      const a = t[i], b = t[j];
      if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) n++;
    }
    return {n, antal: t.length};
  });
  kolla(krock.antal >= 4 && krock.n === 0, `steg 6 (A): kartans etiketter ligger inte över varandra (${krock.antal} etiketter, ${krock.n} krockar)`);
  kolla(await p.evaluate(() => { const k = document.querySelector('svg.karta'), t = document.querySelector('#analysresultat table.analystabell');
    return !!k && !!t && (k.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0; }), 'steg 6 (A): kartan ligger före tabellen');
  await p.unroute('**/api/analys?lage=a*');
}
// Steg 3: samordnarens utestängning är AVSTÄNGD i den externa varianten: rutan förklarar och visar ett inspelat exempel, utan knappar.
// (Gränssnittet med knappar prövas i den isolerade fixturen, tests/vy_handelser_webblasare.mjs, där rutan renderas som den interna varianten.)
await p.goto(`${DASH}/?lang=sv#steg-3`);
await p.waitForSelector('#svadaruta .utdrag pre', { timeout: 15000 }).catch(() => {});
kolla(await p.evaluate(() => !document.querySelector('#svadatabell') && document.querySelectorAll('#svadaruta button[data-svada]').length === 0),
      'steg 3: samordnarrutan har inga knappar för att stänga ute (avstängt externt)');
kolla(await p.evaluate(() => /Samordnaren/.test(document.querySelector('#svadaruta .rollchip').textContent)),
      'steg 3: rutan visar VEM som agerar (samordnaren, Svada)');
kolla(await p.evaluate(() => { const u = [...document.querySelectorAll('#svadaruta .utdrag pre')].map(x => x.textContent).join(' ');
        return /SvadaMembershipCredential/.test(u) && /"aterkallat": true/.test(u) && /CatalogError/.test(u) && /"code": "401"/.test(u) && /NEKAD av spärren/.test(u); }),
      'steg 3: det inspelade exemplet visar statuslistan, DHI:s 401 och jobbloggens rad');
kolla(await p.evaluate(() => !!document.querySelector('#svadaprov')), 'steg 3: den läsande katalogförfrågan finns kvar');
await p.click('#svadaprov');
await p.waitForFunction(() => /Staden når DHI|reaches DHI/.test(document.querySelector('#svadautfall')?.textContent || ''), null, { timeout: 20000 }).catch(() => {});
kolla(await p.evaluate(() => /Staden når DHI|reaches DHI/.test(document.querySelector('#svadautfall').textContent)), 'steg 3: Prova katalogförfrågan svarar att staden når DHI (ingen är utesluten)');
// Servern vägrar också när någon försöker ändå: via Caddy (X-Forwarded-For) ger återkallelse 403 och ändrar inte statuslistan.
{
  const fore = await p.evaluate(async () => JSON.stringify((await (await fetch('/api/svada/status')).json()).poster));
  const svar = await p.evaluate(async () => { const r = await fetch('/api/svada/stad/aterkalla', {method: 'POST', headers: {'content-type': 'application/json', 'x-forwarded-for': '203.0.113.7'}, body: '{}'}); return [r.status, (await r.json()).kod]; });
  const efter = await p.evaluate(async () => JSON.stringify((await (await fetch('/api/svada/status')).json()).poster));
  kolla(svar[0] === 403 && svar[1] === 'fel.utestangning_avstangd' && fore === efter,
        `steg 3: återkallelse via Caddy nekas (${svar[0]}, ${svar[1]}) och statuslistan är oförändrad`);
}
// Förklaringsdialogen om nattens nollställning nämner inte en regel som inte längre gäller: ingen utestängningstid i /api/skydd externt.
{
  const sk = await p.evaluate(async () => (await fetch('/api/skydd')).json());
  kolla(sk.regler.utestangningS === 0 && Object.keys(sk.utestangningS).length === 0, `/api/skydd har ingen utestängningsregel externt (${JSON.stringify(sk.regler)})`);
}
// KoV-rutan i steg 3 med mockade API-svar: knapparnas tillstånd ska följa av
// en enda funktion (inget blink) och Häv-knappen kräva ett gällande avtal.
const mock = async (kon, avtal) => {
  await p.route('**/api/kov', r => r.fulfill({json: {count: kon.length, vantande: kon, forhandlingar: kon}}));
  await p.route('**/api/avtal', r => r.fulfill({json: {avtal, synkfel: null}}));
};
const knappar = () => p.evaluate(() => Object.fromEntries([...document.querySelectorAll('#kovruta button[data-kovbeslut]')]
  .map(b => [b.dataset.kovbeslut, b.disabled || b.getAttribute('aria-disabled') === 'true'])));
await mock([], []);
await p.goto('about:blank');   // samma adress som förra sidan laddar inte om, och mockarna skulle inte slå igenom
await p.goto(`${DASH}/?lang=sv#steg-3`); await stilla(p, 2500);
let kb = await knappar();
kolla(kb.godkann === true && kb.avsla === true && kb.hav === true, `KoV-rutan: inget väntar och inget gäller -> alla knappar låsta (${JSON.stringify(kb)})`);
// En grå KoV-knapp förklarar sig: mouseover, och en kort ruta vid klick som försvinner av sig själv och inte skickar något anrop.
{
  let posts = 0; p.on('request', r => { if (r.method() === 'POST' && /\/api\/kov\//.test(r.url())) posts++; });
  await p.waitForFunction(() => { const b = document.querySelector('#kovruta button[data-kovbeslut="godkann"]'); return b && b.getAttribute('aria-disabled') === 'true' && /Ingen förfrågan väntar/.test(b.title); }, null, { timeout: 15000 }).catch(() => {});   // knappens hanterare och titel är på plats
  // Rutan försvinner vid rullning: lägg knappen i bild och låt rullningen avklinga innan hovring och klick (annars rullar klicket sidan efter att rutan visats).
  await p.evaluate(() => document.querySelector('#kovruta button[data-kovbeslut="godkann"]').scrollIntoView({ block: 'center' })); await p.waitForTimeout(700);
  await p.hover('#kovruta button[data-kovbeslut="godkann"]', { force: true }); await p.waitForTimeout(250);
  const t0 = await p.evaluate(() => { const b = document.querySelector('#kovruta button[data-kovbeslut="godkann"]'); return { titel: b.title, aria: b.getAttribute('aria-disabled'), dis: b.disabled, bg: getComputedStyle(b).backgroundColor }; });
  kolla(t0.bg === 'rgb(230, 232, 231)', `grå KoV-knapp (Godkänn) är grå, inte grön, även vid hovring (${t0.bg})`);
  await p.click('#kovruta button[data-kovbeslut="godkann"]', { force: true });   // Playwright räknar aria-disabled som avstängd
  await p.waitForSelector('.knapptips', { timeout: 3000 }).catch(() => {});
  const ruta = await p.evaluate(() => { const r = document.querySelector('.knapptips'); return r ? { text: r.textContent, lank: !!r.querySelector('[data-gaforhandla]') } : null; });
  await p.waitForTimeout(4600);
  const kvar = await p.evaluate(() => !!document.querySelector('.knapptips'));
  kolla(t0.aria === 'true' && !t0.dis && /Ingen förfrågan väntar/.test(t0.titel), `grå KoV-knapp: mouseover förklarar varför ('${t0.titel}') och knappen går att klicka på`);
  kolla(!!ruta && ruta.text.trim().length > 0 && ruta.lank && posts === 0, `klick på en grå KoV-knapp visar en förklarande ruta med länk och skickar inget anrop (${posts} anrop; ruta ${JSON.stringify(ruta)})`);
  kolla(!kvar, 'rutan försvinner av sig själv efter några sekunder');
  // Esc stänger bara rutan, inte hela steg 3 (granskningen 2026-10-23), med fokus på knappen och med fokus i rutan.
  for (const iRutan of [false, true]) {
    await p.click('#kovruta button[data-kovbeslut="godkann"]', { force: true }); await p.waitForTimeout(300);
    if (iRutan) await p.focus('.knapptips [data-gaforhandla]');
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);
    const e = await p.evaluate(() => ({ ruta: !!document.querySelector('.knapptips'), panel: !!document.querySelector('section#kedjan.aktiv') }));
    kolla(!e.ruta && e.panel, `Esc stänger bara tipsrutan och lämnar steg 3 öppet (fokus ${iRutan ? 'i rutan' : 'på knappen'}; ruta ${e.ruta}, panel öppen ${e.panel})`);
  }
}
await p.unroute('**/api/kov'); await p.unroute('**/api/avtal');
await mock([], [{id: 'aaaaaaaa-1', dhiAvtalId: 'bbbbbbbb-2', distribution: 'A', status: 'GALLANDE', regler: {}, url: '/avtal/aaaaaaaa-1'}]);
await p.goto(`${DASH}/?lang=sv&mock=2#steg-3`); await stilla(p, 2500);
kb = await knappar();
kolla(kb.hav === false && kb.godkann === true, `KoV-rutan: ett gällande avtal -> bara Häv är öppen (${JSON.stringify(kb)})`);
const rad = await p.textContent('#kovavtalrad');
kolla(/gäller tills det hävs/.test(rad), `KoV-rutan säger att avtalet gäller tills det hävs ('${rad}')`);
// Knappläget är stabilt över flera statusrundor (inget blink): läs det 6 gånger under 8 s.
const lagen = [];
for (let i = 0; i < 6; i++) { lagen.push(JSON.stringify(await knappar())); await p.waitForTimeout(1400); }
kolla(new Set(lagen).size === 1, `KoV-knapparna blinkar inte mellan statusrundor (${new Set(lagen).size} olika lägen)`);
await p.unroute('**/api/kov'); await p.unroute('**/api/avtal');
await p.goto(`${DASH}/#jobb-3`); await stilla(p, 1200);
kolla(await p.evaluate(() => document.querySelector('section.flik.aktiv').id) === 'jobb', '#jobb-ID öppnar fliken Jobb');
// Fliken Jobb visar att ett jobb pågår (snurra + text) och släpper det när jobbet är klart. Mockad jobblista, inga riktiga jobb.
{
  let klar = false;
  const jobb = () => ({aktivt: !klar, jobb: [{id: 3, atgard: 'forhandla-b', steg: 3, etikett: 'Förhandla Distribution B', status: klar ? 'klar' : 'kör', startad: '2026-10-23T10:00:00Z',
    klar: klar ? '2026-10-23T10:00:05Z' : null, utfall: null, kopos: null, rader: [{tid: '2026-10-23T10:00:00Z', kod: 'jobb.start', p: {}, text: 'startar'}]}]});
  await p.route('**/api/jobb', r => r.fulfill({json: jobb()}));
  await p.goto(`${DASH}/#jobb-3`); await stilla(p, 2500);
  const under = await p.evaluate(() => ({rad: document.querySelector('#jobbpagar .snurr') !== null && /pågår/.test(document.querySelector('#jobbpagar').textContent),
    lista: document.querySelector('#jobblista .snurr') !== null, anim: getComputedStyle(document.querySelector('#jobbpagar .snurr') || document.body).animationName}));
  kolla(under.rad && under.lista && under.anim === 'snurra', `fliken Jobb: ett pågående jobb visar snurra och "pågår" i raden och i listan (${JSON.stringify(under)})`);
  klar = true; await p.evaluate(() => laddaJobb()); await p.waitForTimeout(800);
  kolla(await p.evaluate(() => !document.querySelector('#jobbpagar .snurr') && !document.querySelector('#jobblista .snurr') && document.querySelector('#jobbpagar').textContent === ''), 'fliken Jobb: snurran försvinner när jobbet är klart');
  await p.unroute('**/api/jobb');
}
await p.goto(`${DASH}/#ordlista-dsp`); await stilla(p, 1200);
kolla(await p.evaluate(() => document.getElementById('ordlista-dsp').classList.contains('markerad')), '#ordlista-ID markerar begreppet');
await p.goto(`${DASH}/?lang=en#steg-1`); await stilla(p, 2500);
kolla(await p.evaluate(() => document.documentElement.lang) === 'en', 'engelska via ?lang=en');
const namn = await p.textContent('#steg-1 .teknikruta');
kolla(/stands in for DHI/.test(namn) && !/står i för/.test(namn), 'teknikrutan på engelska utan svenska delar');
await p.goto(`${DASH}/?lang=sv#steg-5`); await stilla(p, 3500);
const vard = await p.textContent('#provvarde'), avtal = await p.textContent('#provavtal');
const id = (vard.match(/"contractAgreementId":\s*"([^"]+)"/) || [])[1];
kolla(/"distribution":\s*"B"/.test(vard) && !/"distribution":\s*"A"/.test(vard), 'steg 5 visar ett värde ur distribution B');
kolla(id && avtal.includes(id), 'avtalet till höger har samma id som värdet till vänster');
kolla(!/\(M\d\)/.test(vard + avtal), 'ingen intern licensbeteckning (M2)');
kolla(/"statusIKlartext":\s*"(gällande|hävt|utgånget|okänt)"/.test(avtal) && /"signeratUtc":\s*"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC"/.test(avtal), 'steg 5: avtalet har status och signeringstid i klartext bredvid de ursprungliga fälten (F10)');
kolla(!/T\d\d\.\d|T\d\d:\d\dZ/.test(vard), 'tidsstämplarna är hela');
kolla(jsfel.length === 0, `inga JS-fel${jsfel.length ? ': ' + jsfel.join('; ') : ''}`);
// F13: länkar till ett steg eller jobb som inte finns får en kort notis i stället för att tyst skrivas om.
await p.goto(`${DASH}/?lang=sv#steg-7`); await stilla(p, 2000);
kolla(await p.evaluate(() => { const n = document.querySelector('#lanknot'); return !!n && !n.hidden && /Steg 7 finns inte/.test(n.textContent); }), 'F13: #steg-7 ger en notis om att steget inte finns');
await p.goto(`${DASH}/?lang=sv#jobb-99999`); await stilla(p, 2500);
kolla(await p.evaluate(() => { const n = document.querySelector('#lanknot'); return !!n && !n.hidden && /Jobb 99999 finns inte/.test(n.textContent); }), 'F13: #jobb-99999 ger en notis om att jobbet inte finns');
// Knapparna (besökartestet 2026-10-22): åtgärdsknappar har en egen färg (dataspace-lila), är minst 44 px höga, "Prova själv" ligger
// först i steget, och nästa rimliga åtgärd markeras (ring och märke) med en knapp i ordningsraden.
await p.goto(`${DASH}/?lang=sv#steg-1`); await stilla(p, 3500);
const kn = await p.evaluate(() => {
  const k = document.querySelector('#steg-1 button.kor'); const cs = getComputedStyle(k); const nk = document.querySelector('#nastaknapp');
  return { bg: cs.backgroundColor, h: k.getBoundingClientRect().height, forst: document.querySelector('#steg-1 .prova') === document.querySelector('#steg-1 h2 + div'),
           antalNasta: document.querySelectorAll('button.kor.nasta').length, nk: nk && !nk.hidden ? nk.textContent : '' };
});
kolla(kn.bg === 'rgb(76, 60, 167)' && kn.h >= 43.5, `knappar: egen färg och minst 44 px (${kn.bg}, ${kn.h} px)`);
kolla(kn.forst, 'knappar: "Prova själv" ligger först i steget, före förklaringarna');
kolla(kn.antalNasta <= 2 && (kn.nk === '' || /^Nästa: /.test(kn.nk)), `knappar: nästa åtgärd markeras (${kn.antalNasta} knapp, ordningsraden: '${kn.nk}')`);
const pos = await p.evaluate(() => { const k = document.querySelector('#steg-1 button.kor[data-atgard="kor-batch"]');
  const textX = () => { const r = document.createRange(); const n = [...k.childNodes].find(c => c.nodeType === 3 && c.nodeValue.trim()); r.selectNodeContents(n); return Math.round(r.getBoundingClientRect().left * 10) / 10; };
  const normal = textX(); const d0 = k.disabled; k.disabled = true; const grå = textX(); k.classList.add('pagar'); const snurr = textX(); k.classList.remove('pagar'); k.disabled = d0;
  return { normal, grå, snurr }; });
kolla(pos.normal === pos.grå && pos.normal === pos.snurr, `texten börjar på samma ställe i knappen före klick, avstängd och under körning (${pos.normal} / ${pos.grå} / ${pos.snurr} px)`);
// Besökartestet 2026-10-22: spärrtexten står till höger om knappen och får inte flytta sidan; ODRL-raderna bryts i stället för att
// kapas; rullningslisterna syns alltid; en nyckel för A och B står under knapparna i steg 3; varje flik har en väg tillbaka.
{
  const h = await p.evaluate(async () => {
    const kort = document.querySelector('#steg-1 .knappkort'), kn = kort.querySelector('button.kor'), tx = kort.querySelector('.last-hint');
    const fore = kort.getBoundingClientRect().height;
    tx.textContent = 'Vänta några sekunder innan nästa körning.'; tx.hidden = false;
    await new Promise(r => setTimeout(r, 100));
    const efter = kort.getBoundingClientRect().height, rk = kn.getBoundingClientRect(), rt = tx.getBoundingClientRect();
    tx.hidden = true; tx.textContent = '';
    return { fore, efter, hogerOm: rt.left >= rk.right - 1, sammaRad: Math.abs(rt.top + rt.height / 2 - (rk.top + rk.height / 2)) < rk.height };
  });
  kolla(h.fore === h.efter && h.hogerOm && h.sammaRad, `spärrtexten: till höger om knappen och sidan hoppar inte (höjd ${h.fore} -> ${h.efter})`);
  await p.goto(`${DASH}/?lang=sv#steg-2`); await stilla(p, 3000);
  const o = await p.evaluate(() => {
    const koder = [...document.querySelectorAll('#steg-2 .odrlkol li code')];
    return { antal: koder.length, kapad: koder.filter(c => c.scrollWidth > c.clientWidth + 1).length,
             titlar: [...document.querySelectorAll('#steg-2 .odrlkol li')].every(li => li.title && li.title.length > 4),
             avAlla: /\bav alla\b/.test(document.querySelector('#steg-2 .odrlruta')?.textContent || ''),
             rullning: getComputedStyle(document.documentElement, '::-webkit-scrollbar').width };
  });
  kolla(o.antal > 0 && o.kapad === 0 && o.titlar, `ODRL-raderna: ingen kapad (${o.kapad} av ${o.antal}) och hela texten vid hovring`);
  kolla(!o.avAlla, 'ODRL: "får användas …" lyder lika för A och B (ingen "av alla" bara för B)');
  // "Se hur det ser ut": riktiga flikar och bläddring (1 av 3), och inget som pulserar på nästa-knappen
  // Nästa-markeringen provas med ett fastlagt tillstånd (annars är "nästa" tomt efter en körd kedja och proven blir tomma).
  await p.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = 'hamta-katalog'; r.fulfill({json: j}); });
  await p.waitForFunction(() => document.querySelectorAll('button.kor.nasta').length === 1 && !document.querySelector('#nastaknapp').hidden, null, { timeout: 15000 }).catch(() => {});
  const sh = await p.evaluate(async () => {
    const rot = document.querySelector('#steg-2 .sehur'); const fl = [...rot.querySelectorAll('[data-sflik]')];
    const ras = () => rot.querySelector('.sraknare').textContent;
    const start = ras(), nast = rot.querySelector('[data-sstep="1"]'), foreg = rot.querySelector('[data-sstep="-1"]');
    const startFore = foreg.disabled;
    nast.click(); await new Promise(r => setTimeout(r, 100));
    const efter1 = { ras: ras(), vald: fl.findIndex(x => x.getAttribute('aria-selected') === 'true'), synlig: !rot.querySelector('[data-sinn="vc"]').hidden };
    nast.click(); await new Promise(r => setTimeout(r, 100)); const slutDis = nast.disabled;
    foreg.click(); foreg.click(); await new Promise(r => setTimeout(r, 100));
    return { start, startFore, efter1, slutDis, tillbaka: ras(), tips: !!rot.querySelector('.stips'), animation: getComputedStyle(document.querySelector('button.kor.nasta') || document.body).animationName };
  });
  kolla(sh.start === '1 av 3' && sh.startFore && sh.efter1.ras === '2 av 3' && sh.efter1.vald === 1 && sh.efter1.synlig && sh.slutDis && sh.tillbaka === '1 av 3' && sh.tips,
        `"Se hur det ser ut": flikar med bläddring (${sh.start} → ${sh.efter1.ras} → slut avstängd ${sh.slutDis} → ${sh.tillbaka})`);
  const rad1 = await p.evaluate(() => { const st = [...document.querySelectorAll('#ordning .ordningsteg button[data-hopp]:not(.nastaknapp)')]; const t = st.map(b => Math.round(b.getBoundingClientRect().top));
    const nk = document.querySelector('#nastaknapp'), rn = nk.hidden ? null : nk.getBoundingClientRect(), sista = st[st.length - 1].getBoundingClientRect();
    const topp = document.querySelector('#ordning .ordningtopp').getBoundingClientRect().bottom, steg = document.querySelector('#ordning .ordningsteg').getBoundingClientRect();
    return { antal: t.length, enRad: new Set(t).size === 1, underEtikett: steg.top >= topp - 1,
             nastaPaRaden: !rn || (rn.left >= sista.right && Math.abs((rn.top + rn.bottom) / 2 - (sista.top + sista.bottom) / 2) <= 1.5 && rn.height <= sista.height + 2), radHojd: Math.round(steg.height), stegHojd: Math.round(sista.height) }; });
  const nkText = await p.evaluate(() => document.querySelector('#nastaknapp')?.hidden ? '' : document.querySelector('#nastaknapp')?.textContent);
  kolla(nkText === '' || /^Nästa: (?!Nästa)/.test(nkText), `Nästa-knappen i ordningsraden har rätt text ('${nkText}')`);
  kolla(rad1.antal === 8 && rad1.enRad && rad1.underEtikett && rad1.nastaPaRaden, `ordningsraden: alla ${rad1.antal} stegen på en rad med Nästa-knappen direkt efter, i samma höjdmitt och inte högre (rad ${rad1.radHojd} px, steg ${rad1.stegHojd} px)`);
  const pilar = await p.evaluate(() => { const st = [...document.querySelectorAll('#ordning .ordningsteg button[data-hopp]:not(.nastaknapp)')], pl = [...document.querySelectorAll('#ordning .ordningsteg .pil')];
    const mitt = r => (r.top + r.bottom) / 2; return { antal: pl.length, maxAvvikelse: Math.max(...pl.map((x, i) => Math.abs(mitt(x.getBoundingClientRect()) - mitt(st[i].getBoundingClientRect())))) }; });
  kolla(pilar.antal === 7 && pilar.maxAvvikelse <= 1.5, `ordningsraden: pilarna mellan stegen ligger i chipens höjdmitt (${pilar.antal} pilar, störst avvikelse ${pilar.maxAvvikelse.toFixed(1)} px)`);
  kolla(sh.animation === 'none', `nästa-knappen pulserar inte (animation: ${sh.animation})`);
  kolla(await p.evaluate(() => document.querySelectorAll('button.kor.nasta').length === 1 && /^Nästa: /.test(document.querySelector('#nastaknapp').textContent)), 'nästa-markering: exakt en knapp är markerad och ordningsraden säger Nästa: …');
  await p.unroute('**/api/status*');
  // Tomma läget provas mot ett mockat svar (annars beror provet på stackens tillstånd).
  await p.route('**/api/analys?lage=b*', r => r.fulfill({contentType: 'application/json', body: JSON.stringify({rader: [], blockerad: {orsak: 'no-delivery', distribution: 'B'}})}));
  await p.evaluate(() => { document.querySelector('input[name="analyslage"][value="b"]').checked = true; laddaAnalys(); }); await stilla(p, 1500);
  kolla(await p.evaluate(() => !!document.querySelector('#analysresultat a[data-hopp="1"]') && !!document.querySelector('#analysresultat a[data-hopp="4"]')), 'steg 6: tomma läget länkar till steg 1 och steg 4');
  await p.unroute('**/api/analys?lage=b*');
  kolla(o.rullning === '14px', `rullningslisterna är alltid synliga och 14 px breda (${o.rullning})`);
  await p.goto(`${DASH}/?lang=sv#steg-3`); await stilla(p, 3000);
  kolla(await p.evaluate(() => /B<\/b> = öppna data/.test(document.querySelector('#steg-3 .distnyckel')?.innerHTML || '') && /<b>A<\/b> = skyddade data/.test(document.querySelector('#steg-3 .distnyckel')?.innerHTML || '')),
        'steg 3: under knapparna står i klartext vilken distribution som är vilken');
  kolla(await p.evaluate(() => ['forhandla-b', 'forhandla-a'].every(x => document.querySelector(`#steg-3 button.kor[data-atgard="${x}"]`).getBoundingClientRect().height <= 48)),
        'steg 3: knapparna Förhandla Distribution A och B står på en rad (höjd högst 48 px)');
  kolla(await p.evaluate(() => { const fl = document.querySelector('#felinjektion'); return !!fl && !!fl.querySelector('button[onclick*="tillbakaFran"]'); }), 'fliken Felinjektion har en tillbaka-knapp');
  const nasta = await p.evaluate(() => {
    const b = document.querySelector('button.kor[data-kovbeslut="godkann"]'); const gamla = aktuellaVantande;
    aktuellaVantande = new Set(['x']); b.disabled = true; markeraNasta(); const avstangd = b.classList.contains('nasta');
    b.setAttribute('aria-disabled', 'true'); b.disabled = false; markeraNasta(); const grå = b.classList.contains('nasta');
    b.removeAttribute('aria-disabled'); markeraNasta(); const paslagen = b.classList.contains('nasta');
    aktuellaVantande = gamla; markeraNasta(); return { avstangd: avstangd || grå, paslagen };
  });
  kolla(nasta.avstangd === false && nasta.paslagen === true, 'KoV-knappen markeras som nästa först när den är påslagen och aldrig medan den är grå (ingen blinkning)');
  kolla(await p.evaluate(() => { const u = lankaAvtal(esc('"http://x:1/avtal/ab-12"'), 'steg-5'); return u.includes('<a href="http://x:1/avtal/ab-12?lang=') && u.includes('&amp;fran=steg-5"'); }), 'avtalets adress i de grå rutorna blir en klickbar länk som bär språket och var besökaren kom ifrån');
}
// F15: bekräftelsen har en KORT knapptext, förklaringen under, och ett fönster på 15 s (förr 8 s och 5 s).
await p.goto(`${DASH}/?lang=sv#steg-3`); await stilla(p, 2000);
const bekr = await p.evaluate(async () => {
  const k = document.createElement('button'); k.textContent = 'KoV häver avtalet'; document.querySelector('#steg-3').appendChild(k);
  const forsta = bekraftat(k, 'Klicka igen för att häva. Det går inte att ångra, men ett nytt avtal kan tecknas efteråt.');
  const kort = k.textContent, info = k.parentElement.querySelector('.bekrafta-info')?.textContent || '';
  await new Promise(r => setTimeout(r, 6500));
  const kvar = !!k.dataset.bekraftaTill && Date.now() < +k.dataset.bekraftaTill;
  const andra = bekraftat(k, 'Klicka igen för att häva. Det går inte att ångra, men ett nytt avtal kan tecknas efteråt.');
  const efter = k.textContent, infoKvar = !!k.parentElement.querySelector('.bekrafta-info');
  k.remove();
  return {forsta, kort, info, kvar, andra, efter, infoKvar};
});
kolla(bekr.forsta === false && bekr.kort === 'Klicka igen för att häva' && /Det går inte att ångra/.test(bekr.info), `F15: första klicket ger en kort knapptext (${bekr.kort}) och förklaringen under`);
kolla(bekr.kvar && bekr.andra === true && bekr.efter === 'KoV häver avtalet' && !bekr.infoKvar, 'F15: bekräftelsen gäller fortfarande efter 6,5 s, andra klicket bekräftar och knappen återställs');
// Besökartestet 2026-11-01: sidans uppdatering byggde om avtalstabellen och nollställde "Klicka igen för att häva" efter några sekunder.
{
  await p.route('**/api/avtal', r => r.fulfill({json: {avtal: [{id: 'aaaaaaaa-1111', distribution: 'A', status: 'GALLANDE', dhiAvtalId: 'dhi-1', regler: {}}], synkfel: null}}));
  const hv = await p.evaluate(async () => {
    await laddaAvtalLista();
    const k = document.querySelector('#avtallista button[data-hav-id]');
    if (!k) return {saknas: true};
    k.click();
    await laddaAvtalLista();
    const samma = document.querySelector('#avtallista button[data-hav-id]') === k;
    return {samma, text: k.textContent, kvar: !!k.dataset.bekraftaTill};
  });
  await p.unroute('**/api/avtal');
  kolla(!hv.saknas && hv.samma && hv.kvar && hv.text === 'Klicka igen för att häva', `Häv-bekräftelsen överlever en uppdatering av avtalstabellen (${JSON.stringify(hv)})`);
}
// Välkomstrutan (första besöket): visas med ?valkomst=1, märkena följer bedömningen, Esc stänger, "Starta" öppnar steg 1,
// och en styrd webbläsare (som den här) får ingen ruta framför sig utan ?valkomst=1.
for (const sprak of ['sv', 'en']) {
  const v = await ny('valkomst-' + sprak);
  await v.goto(`${DASH}/?lang=${sprak}`); await stilla(v, 1500);
  kolla(await v.evaluate(() => !document.getElementById('valkomstdialog').open), `välkomstrutan (${sprak}): visas inte av sig själv för en styrd webbläsare`);
  await v.goto(`${DASH}/?lang=${sprak}&valkomst`); await stilla(v, 1500);
  kolla(await v.evaluate(() => document.getElementById('valkomstdialog').open), `välkomstrutan (${sprak}): den korta adressen ?valkomst (utan =1) öppnar den också`);
  kolla(await v.evaluate(() => { const d = document.getElementById('valkomstdialog'); return /data ?space/i.test(d.querySelector('h2, h1').textContent) && !/tekn|technical/i.test(d.querySelector('h2, h1').textContent) && /data ?space/i.test(d.querySelector('p').textContent); }),
        `välkomstrutan (${sprak}): rubriken säger dataspace (inte "teknisk demo") och inledningen förklarar vad som gör det till ett dataspace`);
  await v.goto(`${DASH}/?lang=${sprak}&valkomst=1`); await stilla(v, 1500);
  const r = await v.evaluate(() => {
    const d = document.getElementById('valkomstdialog');
    const m = [...d.querySelectorAll('.vmerke')].map(a => ({ok: a.classList.contains('ok'), delvis: a.classList.contains('delvis'), bp: a.classList.contains('bp'), text: a.textContent.trim()}));
    return {open: d.open, marken: m, rubrik: d.querySelector('h2').textContent};
  });
  kolla(r.open && r.marken.length === 6, `välkomstrutan (${sprak}): öppen med sex MIM-märken (${r.marken.length})`);
  // (Att märkena följer mim.MIM:s nivåer prövas i tests/mim_enhet.py.)
  const bp = await v.evaluate(() => ({ tekniker: document.querySelectorAll('#valkomstdialog .vtekniker li').length, lank: document.querySelector('#valkomstdialog .vblueprint a')?.href || '',
                                       bockarOppen: document.querySelector('#valkomstdialog .vbockar').open }));
  kolla(bp.tekniker === 5 && /blueprint\.dssc\.eu/.test(bp.lank), `välkomstrutan (${sprak}): Blueprint-panelen har fem grundtekniker och en länk (${bp.tekniker})`);
  kolla(await v.evaluate(() => { const li = [...document.querySelectorAll('#valkomstdialog .vtekniker li')].map(x => x.textContent); return li.some(x => /^DCAT-AP/.test(x.trim()) && /DCAT/.test(x) && /(inte|not) used|används inte/.test(x)); }),
        `välkomstrutan (${sprak}): DCAT-AP finns bland grundteknikerna och säger ärligt att profilen inte används i demon`);
  kolla(await v.evaluate(() => /(följer med|travel with)/.test(document.querySelector('#valkomstdialog .jkropp p').textContent) && [...document.querySelectorAll('#valkomstdialog .vtekniker li')].some(x => /ODRL/.test(x.textContent) && /(följer med|travel with)/.test(x.textContent))),
        `välkomstrutan (${sprak}): villkoren följer med data som delas (inledningen och ODRL-punkten)`);
  kolla(bp.bockarOppen === false, `välkomstrutan (${sprak}): förklaringen av bockarna är hopfälld från början`);
  await v.click('#valkomstdialog .vbockar > summary'); await v.waitForTimeout(200);
  kolla(await v.evaluate(() => document.querySelector('#valkomstdialog .vbockar').open && document.querySelector('#valkomstdialog .vbockar p').offsetHeight > 0), `välkomstrutan (${sprak}): ett klick på "Vad betyder bockarna?" visar förklaringen`);
  const okMarken = r.marken.filter(x => x.ok).length;
  kolla(okMarken >= 1 && okMarken < 6, `välkomstrutan (${sprak}): minst ett men inte alla MIM-märken är gröna (${okMarken}), så rutan inte lovar mer än bedömningen`);
  kolla(r.marken.every(x => x.text.replace(/\s+/g, ' ').trim().length > 8), `välkomstrutan (${sprak}): varje märke har en statustext för skärmläsare och titel`);
  await v.keyboard.press('Escape'); await stilla(v, 300);
  kolla(await v.evaluate(() => !document.getElementById('valkomstdialog').open), `välkomstrutan (${sprak}): Esc stänger den`);
  await v.setViewportSize({width: 390, height: 800}); await v.goto(`${DASH}/?lang=${sprak}&valkomst=1`); await stilla(v, 1000);
  const bredd = await v.evaluate(() => ({sb: document.documentElement.scrollWidth, ib: window.innerWidth, d: document.getElementById('valkomstdialog').getBoundingClientRect().right}));
  kolla(bredd.sb <= bredd.ib && bredd.d <= bredd.ib + 1, `välkomstrutan (${sprak}): ryms vid 390 px utan sidled rullning (${JSON.stringify(bredd)})`);
  await v.setViewportSize({width: 1280, height: 900}); await v.goto(`${DASH}/?lang=${sprak}&valkomst=1`); await stilla(v, 1000);
  await v.click('[data-valkomst-start]'); await stilla(v, 1200);
  const sb = await v.evaluate(() => ({ stangd: !document.getElementById('valkomstdialog').open, remsaTop: Math.round(document.getElementById('ordning').getBoundingClientRect().top),
                                       fokus: document.activeElement && (document.activeElement.id || document.activeElement.closest('#ordning')?.id), steg1: !document.getElementById('steg-1').hidden }));
  kolla(sb.stangd && sb.remsaTop >= -2 && sb.remsaTop < 150 && !sb.steg1 && (sb.fokus === 'nastaknapp' || sb.fokus === 'ordning'), `välkomstrutan (${sprak}): Starta den guidade banan visar remsan överst med fokus på Nästa, utan att öppna steg 1 (${JSON.stringify(sb)})`);
  const malSteg = await v.evaluate(() => document.getElementById('nastaknapp').dataset.hopp);      // Nästa pekar på olika steg beroende på hur långt kedjan har kommit
  await v.click('#nastaknapp'); await stilla(v, 1500);
  const nl = await v.evaluate(s => { const b = document.querySelector(document.getElementById('nastaknapp').dataset.fokus || 'x'); const rb = b && b.getBoundingClientRect();
    return { steg: s, panelTop: Math.round(document.getElementById('steg-' + s).getBoundingClientRect().top), h: innerHeight, panelSynlig: !document.getElementById('steg-' + s).hidden,
             knappSynlig: b ? (rb.top >= 0 && rb.bottom <= innerHeight) : true }; }, malSteg);
  kolla(nl.panelSynlig && nl.panelTop >= -2 && nl.panelTop < 200 && nl.knappSynlig, `Nästa från remsan (${sprak}): landar på själva steget (panelens överkant överst) och knappen som ska tryckas syns (${JSON.stringify(nl)})`);
  // Samma landning vid smalare fönster (under 1100 px ligger panelen direkt under noden) och med stegknappen i remsan.
  for (const bredd of [1000, 800]) {
    await v.setViewportSize({width: bredd, height: 900}); await v.goto(`${DASH}/?lang=${sprak}#kedjan`); await stilla(v, 1200);
    await v.click('#ordning [data-hopp="1"]'); await stilla(v, 1500);
    const sm = await v.evaluate(() => ({ nodTop: Math.round(document.getElementById('nod-1').getBoundingClientRect().top), panelTop: Math.round(document.getElementById('steg-1').getBoundingClientRect().top), h: innerHeight }));
    kolla(sm.nodTop >= -2 && sm.nodTop < 150 && sm.panelTop < sm.h, `stegknappen i remsan (${sprak}, ${bredd} px): steg 1:s nod hamnar överst, inte förbi noden (${JSON.stringify(sm)})`);
  }
  await v.close();
}
// Språkbyte inifrån välkomstrutan: sidan laddas om och rutan öppnas igen på det nya språket (utan ?valkomst=1 i adressen).
{
  const v = await ny('valkomst-sprakbyte', { viewport: { width: 1280, height: 900 } });
  await v.goto(`${DASH}/?lang=sv`); await stilla(v, 1200);
  await v.click('[data-valkomst-oppna]'); await stilla(v, 400);
  await v.click('#valkomstdialog .sprak button[data-lang="en"]');
  await v.waitForFunction(() => document.documentElement.lang === 'en' && document.getElementById('valkomstdialog').open, null, { timeout: 10000 }).catch(() => {});
  const r = await v.evaluate(() => ({ lang: document.documentElement.lang, open: document.getElementById('valkomstdialog').open,
                                      en: document.querySelector('#valkomstdialog .sprak [data-lang="en"]')?.getAttribute('aria-pressed'), url: location.search }));
  kolla(r.lang === 'en' && r.open && r.en === 'true', `välkomstrutan: språkbyte inifrån rutan laddar om och rutan är öppen på engelska (${JSON.stringify(r)})`);
  await v.close();
}
// Rubrikerna "Guidad bana" och "Flödet" och den hopfällbara introduktionen: utfälld på första sidan man kommer till (även ett djupt steg från en länk),
// hopfälld så fort man går vidare (steg, flik eller stäng), med en tydlig knapp för att öppna den igen (tangentbord med). Inget sparas mellan besök.
for (const sprak of ['sv', 'en']) {
  const i = await ny('intro-' + sprak, { viewport: { width: 1280, height: 900 } });
  const oppen = () => i.evaluate(() => document.getElementById('intro').open);
  await i.goto(`${DASH}/?lang=${sprak}`); await stilla(i, 1200);
  kolla(await oppen(), `introduktionen (${sprak}): utfälld på första sidan`);
  await i.click('#nod-2'); await stilla(i, 500);
  kolla(!(await oppen()), `introduktionen (${sprak}): hopfälld när man öppnar ett steg`);
  const a = await i.evaluate(() => {
    const d = document.getElementById('intro'), kn = d.querySelector('.introknapp'), r = e => e.getBoundingClientRect();
    const bana = document.getElementById('rubrik-bana'), flode = document.getElementById('rubrik-flode'), bild = document.querySelector('.bildram');
    return { open: d.open, hojd: Math.round(r(d).height), knappSynlig: r(kn).width > 0 && getComputedStyle(kn).display !== 'none', knappText: kn.textContent.trim(),
             ordning: !!bana && !!flode && r(bana).top < r(flode).top && r(flode).top < r(bild).top, banaH2: bana?.tagName === 'H2' && flode?.tagName === 'H2' };
  });
  kolla(!a.open && a.hojd < 90 && a.knappSynlig && a.knappText.length > 5, `introduktionen (${sprak}): hopfälld tar liten plats och har en synlig knapp ('${a.knappText}', ${a.hojd} px)`);
  kolla(a.ordning && a.banaH2, `rubrikerna (${sprak}): Guidad bana och Flödet är egna rubriker (h2), banan före flödet`);
  await i.focus('#intro > summary'); await i.keyboard.press('Enter'); await stilla(i, 400);
  kolla(await oppen(), `introduktionen (${sprak}): Enter på knappen öppnar den`);
  await i.click('[data-flik="om"]'); await stilla(i, 400);
  await i.click('[data-flik="kedjan"]'); await stilla(i, 400);
  kolla(!(await oppen()), `introduktionen (${sprak}): hopfälld efter flikbyte`);
  await i.reload(); await stilla(i, 1200);
  kolla(await oppen(), `introduktionen (${sprak}): utfälld igen vid nytt besök (inget minne)`);
  await i.goto(`${DASH}/?lang=${sprak}#steg-4`); await i.reload(); await stilla(i, 1200);
  kolla(await oppen(), `introduktionen (${sprak}): utfälld när första sidan är ett djupt steg (#steg-4)`);
  await i.keyboard.press('Escape'); await stilla(i, 300);
  kolla(!(await oppen()), `introduktionen (${sprak}): hopfälld när steget stängs`);
  await i.close();
}
// F2: dubbelklick på Leverera B i fliken Felinjektion ger ett jobb och ingen dialog (en window.alert låste hela fliken i testet 2026-10-19).
{
  const dialoger = [], anrop = [];
  const f = await ny('F2-felinjektion');
  f.on('dialog', async d => { dialoger.push(d.message()); await d.dismiss(); });
  f.on('request', r => { if (r.method() === 'POST' && /\/api\/atgard\/transfer-b/.test(r.url())) anrop.push(r.url()); });
  await f.goto(`${DASH}/?lang=sv#felinjektion`); await stilla(f, 2500);
  await f.waitForFunction(() => !document.querySelector('#felinjektion button[data-atgard="transfer-b"]')?.disabled, null, { timeout: 40000 }).catch(() => {});
  await f.dblclick('#felinjektion button[data-atgard="transfer-b"]'); await stilla(f, 2500);
  kolla(dialoger.length === 0 && anrop.length === 1, `F2: dubbelklick på Leverera B ger ett anrop och ingen dialog (${anrop.length} anrop, ${dialoger.length} dialoger)`);
  kolla(!(await f.content()).includes('alert('), 'F2: sidan innehåller inget alert()');
  await f.close();
}
await p.goto(`${DASH}/?lang=sv#steg-3`); await stilla(p, 2500);
const jobbKlart = () => p.waitForFunction(() => typeof jobbAktivtNu !== 'undefined' && !jobbAktivtNu, null, { timeout: 90000 }).catch(() => {});
await jobbKlart();
// Snurran (besökartestet 2026-10-22): knappen som startade jobbet visar en snurra på pilens plats medan jobbet kör, ingen text om att vänta,
// och den försvinner när knapparna låses upp. De andra knapparna är avstängda utan symbol.
const toppFore = await p.evaluate(() => Math.round(document.querySelector('#steg-3 h2').getBoundingClientRect().top + scrollY));
// Knapparna är låsta medan ett jobb kör och under pausen efter ett jobb: vänta tills de går att klicka på (annars startar klicket inget jobb).
await p.waitForFunction(() => { const b = document.querySelector('#steg-3 button.kor[data-atgard="forhandla-a"]'); return b && !b.disabled; }, null, { timeout: 30000 }).catch(() => {});
await p.click('#steg-3 button.kor[data-atgard="forhandla-a"]'); await p.waitForTimeout(500);
const toppUnder = await p.evaluate(() => Math.round(document.querySelector('#steg-3 h2').getBoundingClientRect().top + scrollY));
kolla(Math.abs(toppUnder - toppFore) <= 2, `sidan hoppar inte när ett jobb startas (rubrikens läge ${toppFore} → ${toppUnder} px)`);
const sn = await p.evaluate(() => { const k = document.querySelector('#steg-3 button.kor[data-atgard="forhandla-a"]'), ann = document.querySelector('#steg-3 button.kor[data-atgard="forhandla-b"]');
  return { pagar: k.classList.contains('pagar'), busy: k.getAttribute('aria-busy'), anim: getComputedStyle(k, '::before').animationName,
           annan: ann.classList.contains('pagar'), annanInnehall: getComputedStyle(ann, '::before').content, annanKant: getComputedStyle(ann).borderStyle,
           text: [...document.querySelectorAll('.last-hint')].filter(e => !e.hidden && e.offsetParent !== null).map(e => e.textContent).join('|') }; });
kolla(sn.pagar && sn.busy === 'true' && sn.anim === 'snurra', `snurra: knappen som startade jobbet snurrar (${sn.anim}, aria-busy ${sn.busy})`);
kolla(!sn.annan && (sn.annanInnehall === '""' || sn.annanInnehall === 'none' || sn.annanInnehall === 'normal') && sn.annanKant === 'dashed', `grå knapp: ingen paussymbol och streckad ram (${sn.annanInnehall}, ${sn.annanKant})`);
kolla(!/pågår|Vänta tills/.test(sn.text), `ingen text om att ett jobb pågår medan snurran visas ('${sn.text}')`);
await jobbKlart(); await stilla(p, 1500);
// F3: efter att KoV beslutat står inte Förhandla A-jobbet kvar med "väntar på KoV"
await p.waitForFunction(() => { const b = document.querySelector('#kovruta button[data-kovbeslut="godkann"]'); return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true'; }, null, { timeout: 30000 }).catch(() => {});
await p.click('#kovruta button[data-kovbeslut="godkann"]');
await jobbKlart(); await stilla(p, 2500);
kolla(await p.evaluate(() => !document.querySelector('#kort-forhandla-a .lstatus.vantar')), 'F3: efter KoV:s beslut står Förhandla A-jobbet inte kvar med etiketten "väntar på KoV"');
kolla(await p.evaluate(() => [...document.querySelectorAll('.last-hint')].filter(e => !e.closest('.kovval')).every(e => e.hidden) && !document.querySelector('button.kor.pagar')), 'F4: snurran och förklaringarna försvinner när jobbet är klart');
// F6: ett språkbyte mitt i ett KoV-jobb följer KOV-jobbet, inte det äldre Förhandla A-jobbet vars ruta också har ett jobb-id
await p.click('#steg-3 button.kor[data-atgard="forhandla-a"]'); await jobbKlart(); await stilla(p, 1500);
await p.waitForFunction(() => { const b = document.querySelector('#kovruta button[data-kovbeslut="godkann"]'); return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true'; }, null, { timeout: 30000 }).catch(() => {});
await p.click('#kovruta button[data-kovbeslut="godkann"]'); await p.waitForTimeout(400);
await p.click('.sprak button[data-lang="en"]');
await p.waitForSelector('#kort-kov-godkann .loggruta', { timeout: 20000 }).catch(() => {});
kolla(await p.evaluate(() => document.documentElement.lang === 'en' && !!document.querySelector('#kort-kov-godkann .loggruta') && !document.querySelector('#kort-forhandla-a .loggruta')),
      'F6: efter språkbytet mitt i KoV-jobbet följs just det jobbet (i KoV-rutan), inte det äldre i Förhandla A-rutan');
await jobbKlart();
// F6, enkla fallet: ett batchjobb
await p.goto(`${DASH}/?lang=sv#steg-1`); await stilla(p, 2500);
await p.waitForFunction(() => !document.querySelector('button.kor[data-atgard="kor-batch"]')?.disabled, null, { timeout: 30000 }).catch(() => {});
await p.click('button.kor[data-atgard="kor-batch"]'); await p.waitForTimeout(400);
await p.click('.sprak button[data-lang="en"]');
await p.waitForSelector('#kort-kor-batch .loggruta', { timeout: 20000 }).catch(() => {});
kolla(await p.evaluate(() => document.documentElement.lang === 'en' && !!document.querySelector('#kort-kor-batch .loggruta')), 'F6: efter språkbytet mitt i batchjobbet finns jobbrutan kvar (på engelska)');
await p.goto(`${DASH}/?lang=sv#steg-1`); await stilla(p, 1500);
// Statistikhändelserna: rätt namn, bara {h}, ingenting innan besökaren rört något, tak på 150 och ett svar 500 märks inte.
{
  const kroppar = [], sidfel = [];
  const h = await ny('handelser');
  h.on('pageerror', e => sidfel.push(e.message));
  h.on('request', r => { if (/\/api\/handelse/.test(r.url()) && r.method() === 'POST') kroppar.push(r.postDataJSON()); });
  await h.goto(`${DASH}/?lang=sv#steg-3`); await stilla(h, 2500);
  kolla(kroppar.length === 0, `statistik: ingen händelse skickas av själva sidladdningen (${kroppar.length})`);
  await h.click('#nod-6'); await h.waitForTimeout(600);
  await h.click('nav#flikar button[data-flik="jobb"]'); await h.waitForTimeout(600);
  kolla(kroppar.some(k => k.h === 'steg_6') && kroppar.some(k => k.h === 'flik_jobb'), `statistik: ett stegbyte och ett flikbyte ger steg_6 och flik_jobb (${kroppar.map(k => k.h).join(', ')})`);
  kolla(kroppar.every(k => JSON.stringify(Object.keys(k)) === '["h"]'), 'statistik: kroppen innehåller bara nyckeln h');
  await h.evaluate(() => { for (let i = 0; i < 200; i++) handelse('steg_' + (1 + i % 6)); }); await h.waitForTimeout(800);
  kolla(kroppar.length <= 150, `statistik: högst 150 händelser per sidladdning (${kroppar.length})`);
  await h.route('**/api/handelse', r => r.fulfill({status: 500, body: 'fel'}));
  const f2 = await ny('handelser-500'); f2.on('pageerror', e => sidfel.push(e.message));
  await f2.route('**/api/handelse', r => r.fulfill({status: 500, body: 'fel'}));
  await f2.goto(`${DASH}/?lang=sv#steg-3`); await stilla(f2, 2000);
  await f2.click('#nod-5'); await f2.waitForTimeout(800);
  kolla(sidfel.length === 0 && await f2.evaluate(() => document.querySelector('#lanknot').hidden), 'statistik: ett svar 500 från /api/handelse märks inte (inget JS-fel, ingen notis)');
  await h.close(); await f2.close();
}
}   // slut på blocket "grund"
if (kor('smal')) { // Smal skärm (400 px): stegraden, träffytor, textstorlek, nyckeltal intill knappen, utfallet synligt.
  const m = await ny('400px-steg', { viewport: { width: 400, height: 800 } });
  await m.goto(`${DASH}/?lang=sv#steg-6`); await stilla(m, 2500);
  await plantera(m, '400px-steg');
  await m.evaluate(() => window.scrollTo(0, 0)); await m.waitForTimeout(400);
  kolla(await m.evaluate(() => { const s = document.getElementById('stegrad'), h = document.querySelector('header'); return !s.hidden && !!s.checkVisibility() && s.getBoundingClientRect().top >= h.getBoundingClientRect().bottom - 1; }),
        '400 px: miniversionen av banan (stegraden) syns redan överst på Flödet, under sidrubriken och inte över den');
  await stabil(m);
  await m.evaluate(() => window.scrollTo(0, document.getElementById('steg-6').getBoundingClientRect().bottom + window.scrollY - 300)); await m.waitForTimeout(600);
  kolla(await m.evaluate(() => !document.getElementById('stegrad').hidden && Math.abs(document.getElementById('stegrad').getBoundingClientRect().top) <= 2),
        '400 px: stegraden sitter kvar överst i bild när man scrollat ned i en stegpanel (sticky)');
  await m.click('#stegrad button[data-steg="3"]'); await stilla(m, 1500);
  const toppen = await m.evaluate(() => (document.querySelector('#steg-3 .stegrubrik') || document.querySelector('#steg-3 h2, #steg-3 h3')).getBoundingClientRect().top);
  kolla(toppen > 0 && toppen < 260, `400 px: klick på ett steg i stegraden landar på panelens topp (rubriken ${Math.round(toppen)} px från kanten)`);
  await m.goto(`${DASH}/?lang=sv#steg-6`); await stilla(m, 2500);
  await m.evaluate(() => window.scrollTo(0, 1500)); await m.waitForTimeout(600);
  const sm = await m.evaluate(() => {
    const mat = e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; };
    const lilla = [];
    document.querySelectorAll('main *, .stegrad *, header *').forEach(e => {
      if (e.closest('svg, script, style, [hidden]') || !e.offsetParent) return;
      if (![...e.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim())) return;
      const fs = parseFloat(getComputedStyle(e).fontSize);
      if (fs < 11.9) lilla.push(e.tagName + '.' + e.className + ' ' + fs.toFixed(1));
    });
    return { lilla: [...new Set(lilla)].slice(0, 6),
      stegknapp: mat(document.querySelector('#stegrad button[data-steg]')),
      radio: mat(document.querySelector('input[name="analyslage"]')),
      kryss: document.querySelector('#felreglage input') ? mat(document.querySelector('#felreglage input')) : null };
  });
  kolla(sm.lilla.length === 0, `400 px: ingen synlig text under 12 px${sm.lilla.length ? ' (' + sm.lilla.join('; ') + ')' : ''}`);
  kolla(sm.stegknapp[1] >= 30, `400 px: stegradens knappar är minst 30 px höga (${sm.stegknapp[1]} px)`);
  kolla(sm.radio[0] >= 20 && sm.radio[1] >= 20, `400 px: radioknapparna är minst 20 px (${sm.radio.join('×')})`);
  // Nyckeltalen visas intill knappen, inte bara i den hopfällda rutan.
  // Väntar in texten (högst 15 s) i stället för en fast väntan: /api/steg kan ta flera sekunder när en källa är kall
  // (observerat 7 s i verify_all 2026-10-18), och då blev provet rött fast sidan gjorde rätt.
  await m.goto(`${DASH}/?lang=sv#steg-1`);
  await m.waitForFunction(() => /^Just nu: /.test(document.querySelector('#steg-1 .knappkort .livetal')?.textContent || ''),
                          null, { timeout: 15000 }).catch(() => {});
  const live = await m.evaluate(() => document.querySelector('#steg-1 .knappkort .livetal')?.textContent || '');
  kolla(/^Just nu: /.test(live) && live.length > 15, `steg 1: nyckeltalen visas intill knappen ('${live.slice(0, 60)}')`);
  // "…och se utfallet": loggen hamnar i bild.
  await m.evaluate(() => kor('kor-batch', {})); await stilla(m, 3500);
  const logg = await m.evaluate(() => { const r = document.getElementById('jobblogg').getBoundingClientRect(); return [Math.round(r.top), innerHeight]; });
  kolla(logg[0] >= 0 && logg[0] < logg[1], `400 px: efter en åtgärd som flyttar till Jobb ligger loggen i bild (${logg[0]} px från toppen)`);
  await m.close();
}
if (kor('fynd')) { // Fynd ur användartestet 2026-10-13: det som ska bevisa demons poäng ska stämma.
  const q = await ny('fynd', { viewport: { width: 1280, height: 900 } });
  await q.goto(`${DASH}/?lang=sv`); await q.waitForTimeout(800);
  await plantera(q, 'fynd');
  // Resultattabellen i Felinjektion fylls när det finns leveranser (en sidrensning hade döpt om 'ingest-service' i skriptet).
  const harLev = await q.evaluate(async () => (await (await fetch('/api/audit')).json()).handelser.some(h => h.kalla === 'ingest-service'));
  if (harLev) {
    await q.goto(`${DASH}/?lang=sv#felinjektion`);
    // Auditloggen läses i flera led och blir långsammare med många händelser: vänta på villkoret i stället för en fast tid.
    await q.waitForFunction(() => document.querySelectorAll('#felresultat tr').length > 0 && !/Inga leveranser ännu/.test(document.querySelector('#felresultat').textContent), null, { timeout: 25000 }).catch(() => {});
    const fr = await q.evaluate(() => ({text: document.querySelector('#felresultat').textContent.trim().slice(0, 60), rader: document.querySelectorAll('#felresultat tr').length, flik: document.querySelector('section.flik.aktiv')?.id}));
    kolla(!/Inga leveranser ännu/.test(fr.text) && fr.rader > 0, `Felinjektion: resultattabellen visar leveranserna när sådana finns (${fr.rader} rader, flik ${fr.flik}, '${fr.text.replace(/\s+/g, ' ')}')`);
  } else console.log('  [HOPPAR ÖVER] resultattabellen i Felinjektion (inga leveranser än)');
  // Statusbrickan "väntar på KoV" följer providerns kö i stället för att stå kvar för alltid.
  const brickor = await q.evaluate(() => {
    const j = {status: 'klar', utfall: null, resultat: {kov: {kovBeslut: 'VANTANDE', id: 'x1'}}};
    aktuellaVantande = new Set(); const a = loggStatus(j);
    aktuellaVantande = new Set(['x1']); const b2 = loggStatus(j);
    return [a, b2];
  });
  kolla(brickor[0] === 'klar' && brickor[1] === 'vantar', `statusbrickan "väntar på KoV" försvinner när förhandlingen är avgjord (${brickor.join(', ')})`);
  // Statuskoder ser rätt ut på svenska (å, ä, ö).
  kolla(await q.evaluate(() => resKod('HAVT') === 'HÄVT' && resKod('VANTANDE') === 'VÄNTANDE' && resKod('GODKAND') === 'GODKÄND'), 'svenska statuskoder med å/ä/ö (HÄVT, VÄNTANDE, GODKÄND)');
  // Tillgänglighet: inga tomma <summary>, logotypen har ett namn. (Samordnarens knappar nämner vem de gäller: se fixturen.)
  kolla(await q.evaluate(() => [...document.querySelectorAll('summary')].filter(x => !x.textContent.trim() && !x.getAttribute('aria-label')).length === 0), 'inga <summary> utan text');
  kolla(await q.evaluate(() => (document.querySelector('img.logga')?.alt || '').length > 8), 'logotypen har en beskrivande alt-text');
  // Ordningsradens "Förhandla A + KoV" öppnar KoV-rutan, inte bara steg 3.
  await q.goto(`${DASH}/?lang=sv#steg-1`); await stilla(q, 2000);
  await q.click('#ordning button[data-kov="1"]'); await stilla(q, 1200);
  kolla(await q.evaluate(() => !!document.querySelector('#kovruta.fokus') && location.hash === '#steg-3'), 'ordningsradens "Förhandla A + KoV" öppnar steg 3 med KoV-rutan i fokus');
  // Avtalslänkarna i Suveränitet är relativa (fungerar oavsett adress).
  await q.goto(`${DASH}/?lang=sv#suveranitet`); await stilla(q, 3000);
  kolla(await q.evaluate(() => { const l = [...document.querySelectorAll('#avtallista a')]; return l.length === 0 || l.every(a => a.getAttribute('href').startsWith('/avtal/')); }),
        'avtalslänkarna i Suveränitet är relativa (/avtal/<id>)');
  // Jobb-fliken öppnar på det senaste jobbet.
  await q.goto(`${DASH}/?lang=sv#kedjan`); await stilla(q, 1500);
  await q.click('nav#flikar button[data-flik="jobb"]'); await stilla(q, 1800);
  const jobbval = await q.evaluate(() => { const rader = [...document.querySelectorAll('#jobblista tr')]; return rader.length ? [rader[0].querySelector('a')?.textContent, valtJobb] : null; });
  kolla(!jobbval || String(jobbval[0]) === String(jobbval[1]), `Jobb-fliken öppnar på det senaste jobbet (${jobbval ? jobbval.join(' / ') : 'inga jobb'})`);
  await q.close();
  // Smal skärm: kartans etiketter och axeltal krockar inte, och breda tabeller får en "dra i sidled"-ledtråd.
  const r10 = Array.from({length: 10}, (_, i) => ({rang: i + 1, id: 'SSO1_01-' + (6700 + i), namn: 'b' + i, volymM3: 900 - i * 10, toppM3S: 0.1, nivaM: 0.1,
    tidMin: 155, recipient: 'Göta Älv', utslapp: 'G1', inspektera: true, position: [11.9900 + (i % 4) * 0.0006 + i * 0.0001, 57.6900 + Math.floor(i / 4) * 0.0004]}));
  const A400 = {lage: 'A', topp: 10, blockerad: null, avtal: {id: 'aaaaaaaa-1', status: 'GALLANDE'}, rader: r10,
    perRecipient: [{recipient: 'Göta Älv', brunnar: 10, volymM3: 9000, utslapp: ['G1']}],
    ursprung: {avtal: 'aaaaaaaa-1', batch: 'batch-1', distribution: 'A', klass: 'K1R1T1'},
    sammanfattning: {brunnar: 10, braddar: 10, totalVolymM3: 9000, hogstaVolymM3: 900, samtligaTidLika: true}};
  const m2 = await ny('400px-karta', { viewport: { width: 400, height: 800 } });
  await m2.route('**/api/analys?lage=a*', r => r.fulfill({json: A400}));
  // kartplattorna blockeras redan före sidladdningen (A är startläge och kartan startar direkt): provet gäller den schematiska kartans text, som annars döljs när plattorna visas
  await m2.route('https://*.openstreetmap.org/**', r => r.abort());
  await m2.goto(`${DASH}/?lang=sv#steg-6`); await stilla(m2, 2500);
  await plantera(m2, '400px-karta');
  await valjA(m2); await stilla(m2, 1800);
  const k400 = await m2.evaluate(() => {
    const t = [...document.querySelectorAll('svg.karta text')].map(x => x.getBoundingClientRect());
    let n = 0;
    for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) {
      const a = t[i], c = t[j];
      if (a.left < c.right - 1 && c.left < a.right - 1 && a.top < c.bottom - 1 && c.top < a.bottom - 1) n++;
    }
    const s = document.querySelector('svg.karta').getBoundingClientRect();
    const rot = document.querySelector('svg.karta').parentElement.getBoundingClientRect();
    const utanfor = t.filter(r => r.left < rot.left - 1 || r.right > rot.right + 1).length;
    return {n, antal: t.length, bredd: Math.round(s.width), hojd: Math.round(s.height), utanfor};
  });
  kolla(k400.antal >= 8 && k400.n === 0 && k400.utanfor === 0,
        `400 px: kartans texter krockar inte och ryms (${k400.antal} texter, ${k400.n} krockar, ${k400.utanfor} utanför; kartan ${k400.bredd}×${k400.hojd} px)`);
  await m2.goto(`${DASH}/?lang=sv#suveranitet`); await stilla(m2, 3500); await stabil(m2);
  const rull = await m2.evaluate(() => [...document.querySelectorAll('section.flik.aktiv table')].filter(t => t.scrollWidth > t.clientWidth + 4).map(t => t.hasAttribute('data-rull')));
  kolla(rull.every(Boolean), `400 px: tabeller som går att rulla i sidled har en ledtråd (${rull.filter(Boolean).length} av ${rull.length})`);
  await m2.close();
}
if (kor('polling')) { // Granskning c2 (C2-1): ett sent pollsvar får inte återfylla en jobbruta som tömts eller tagits över. Deterministiskt: svaren hålls
  // tillbaka tills rutan hunnit tömmas. Inga riktiga jobb startas; /api/jobb/900x och /api/kov är mockade.
  const j = await ny('jobbruta', { viewport: { width: 1280, height: 900 } });
  await j.goto(`${DASH}/?lang=sv#steg-1`); await stilla(j, 2500);
  await plantera(j, 'jobbruta');
  const jobb = id => ({id, status: 'klar', utfall: null, etikett: 'Testjobb', rader: [{tid: '2026-10-14T10:00:00Z', text: 'rad'}], resultat: null});
  const grind = () => { let slapp; const vantan = new Promise(r => { slapp = r; }); return {vantan, slapp}; };
  const tomt = () => j.evaluate(() => window.__ruta.innerHTML === '');
  // 1. Jobb 9001 är klart, men pollsvaret dröjer; ett nytt jobb tömmer rutan (rensaLoggplatser); svaret anländer: rutan ska förbli tom.
  let g = grind();
  await j.route('**/api/jobb/9001', async r => { await g.vantan; await r.fulfill({json: jobb(9001)}); });
  await j.evaluate(() => { window.__ruta = document.querySelector('#steg-1 .loggplats'); foljJobb(9001, window.__ruta); });
  await j.waitForTimeout(300);
  await j.evaluate(() => rensaLoggplatser(document.body));
  g.slapp(); await j.waitForTimeout(900);
  kolla(await tomt(), 'jobbruta: ett sent pollsvar återfyller inte en tömd ruta');
  await j.unroute('**/api/jobb/9001');
  // 2. Samma, men svaret kommer i tid och det är läsningen av KoV-kön (efter jobbet) som dröjer.
  g = grind();
  await j.route('**/api/jobb/9004', r => r.fulfill({json: jobb(9004)}));
  await j.route('**/api/kov', async r => { await g.vantan; await r.fulfill({json: {count: 0, vantande: [], forhandlingar: []}}); });
  await j.evaluate(() => { window.__ruta = document.querySelector('#steg-1 .loggplats'); foljJobb(9004, window.__ruta); });
  await j.waitForTimeout(500);
  await j.evaluate(() => rensaLoggplatser(document.body));
  g.slapp(); await j.waitForTimeout(900);
  kolla(await tomt(), 'jobbruta: väntan på KoV-kön återfyller inte en tömd ruta');
  await j.unroute('**/api/jobb/9004'); await j.unroute('**/api/kov');
  // 3. Ett nytt jobb i samma ruta: det gamla jobbets sena svar ska inte skriva över det nya.
  g = grind();
  await j.route('**/api/jobb/9001', async r => { await g.vantan; await r.fulfill({json: jobb(9001)}); });
  await j.route('**/api/jobb/9002', r => r.fulfill({json: jobb(9002)}));
  await j.evaluate(() => { window.__ruta = document.querySelector('#steg-1 .loggplats'); foljJobb(9001, window.__ruta); });
  await j.waitForTimeout(300);
  await j.evaluate(() => { foljJobb(9002, window.__ruta); });
  await j.waitForTimeout(600);
  g.slapp(); await j.waitForTimeout(900);
  const nyttjobb = await j.evaluate(() => window.__ruta.textContent);
  kolla(/9002/.test(nyttjobb) && !/9001/.test(nyttjobb), `jobbruta: det nyare jobbet behåller rutan (${nyttjobb.replace(/\s+/g, ' ').slice(0, 40)})`);
  await j.unroute('**/api/jobb/9001'); await j.unroute('**/api/jobb/9002');
  // 4. Felsvar efter att rutan tömts: inget felmeddelande får skrivas tillbaka.
  g = grind();
  await j.evaluate(() => rensaLoggplatser(document.body));
  await j.route('**/api/jobb/9003', async r => { await g.vantan; await r.fulfill({status: 500, json: {fel: 'simulerat fel'}}); });
  await j.evaluate(() => { window.__ruta = document.querySelector('#steg-1 .loggplats'); foljJobb(9003, window.__ruta); });
  await j.waitForTimeout(300);
  await j.evaluate(() => rensaLoggplatser(document.body));
  g.slapp(); await j.waitForTimeout(900);
  kolla(await tomt(), 'jobbruta: ett felsvar efter att rutan tömts skrivs inte tillbaka');
  await j.unroute('**/api/jobb/9003');
  await j.close();
}
if (kor('etiketter')) { // Granskning c2 (C2-2): kartans etiketter ryms i bilden åt alla håll, även när många etiketter ska flyttas. Mockad analys, inga jobb.
  const rad = (i, pos, rang) => ({rang, id: 'SSO1_01-' + (6700 + i), namn: 'b' + i, volymM3: 900 - i, toppM3S: 0.1, nivaM: 0.1, tidMin: 155,
    recipient: 'Göta Älv', utslapp: 'G1', inspektera: true, position: pos});
  const rader = [1, 2, 3, 4, 5].map(i => rad(i, [11.99, 57.69], i)).concat([rad(6, [11.99, 57.70], 6)]);
  const AK = {lage: 'A', topp: 10, blockerad: null, avtal: {id: 'aaaaaaaa-1', status: 'GALLANDE'}, rader,
    perRecipient: [{recipient: 'Göta Älv', brunnar: 6, volymM3: 5000, utslapp: ['G1']}],
    ursprung: {avtal: 'aaaaaaaa-1', batch: 'batch-1', distribution: 'A', klass: 'K1R1T1'},
    sammanfattning: {brunnar: 6, braddar: 6, totalVolymM3: 5000, hogstaVolymM3: 900, samtligaTidLika: true}};
  for (const bredd of [400, 1280]) {
    const k = await ny(`kartgrans-${bredd}`, { viewport: { width: bredd, height: 900 } });
    await k.route('**/api/analys?lage=a*', r => r.fulfill({json: AK}));
    await k.route('https://*.openstreetmap.org/**', r => r.abort());    // kartplattorna får inte dölja SVG:n som proven mäter
    await k.goto(`${DASH}/?lang=sv#steg-6`); await stilla(k, 2500);
    if (bredd === 400) await plantera(k, 'kartgrans');
    await valjA(k); await stilla(k, 1800);
    const g = await k.evaluate(() => {
      const svg = document.querySelector('svg.karta').getBoundingClientRect();
      const t = [...document.querySelectorAll('svg.karta text')].filter(x => /^SSO1_/.test(x.textContent)).map(x => x.getBoundingClientRect());
      let ut = 0, kr = 0;
      for (const r of t) if (r.top < svg.top - 0.5 || r.bottom > svg.bottom + 0.5 || r.left < svg.left - 0.5 || r.right > svg.right + 0.5) ut++;
      for (let i = 0; i < t.length; i++) for (let jx = i + 1; jx < t.length; jx++) {
        const a = t[i], c = t[jx];
        if (a.left < c.right - 1 && c.left < a.right - 1 && a.top < c.bottom - 1 && c.top < a.bottom - 1) kr++;
      }
      return {antal: t.length, ut, kr};
    });
    kolla(g.antal >= 1 && g.ut === 0 && g.kr === 0, `${bredd} px: kartans etiketter ligger helt inom bilden, uppåt och nedåt, och krockar inte (${g.antal} etiketter, ${g.ut} utanför, ${g.kr} krockar)`);
    await k.close();
  }
}
if (kor('nasta')) { // Externa webbläsartestet 2026-10-23: Nästa efter Leverera A (F1), Nästa-knappens mål (F3), KoV-rutan vid 1040 px och felsidor.
  const mock = async (pg, nasta) => { await kovTom(pg); return pg.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = nasta; r.fulfill({json: j}); }); };
  const f = await ny('nasta-analysera', { viewport: { width: 1280, height: 900 } });
  await mock(f, 'analysera');
  await f.goto(`${DASH}/?lang=sv#kedjan`); await stilla(f, 2500);
  const na = await f.evaluate(() => { const nk = document.querySelector('#nastaknapp'); return { synlig: !nk.hidden, text: nk.textContent, hopp: nk.dataset.hopp }; });
  kolla(na.synlig && /Ursprung/.test(na.text) && na.hopp === '5', `F1: efter Leverera A pekar "Nästa" först på Ursprung (steg 5, där villkor, klass och avtal följer med data) (${na.text})`);
  await f.click('#nastaknapp'); await stilla(f, 1500);
  await f.waitForFunction(() => location.hash === '#steg-5' && /Analysera/.test(document.querySelector('#nastaknapp').textContent), null, { timeout: 10000 }).catch(() => {});
  const efter5 = await f.evaluate(() => ({ hash: location.hash, text: document.querySelector('#nastaknapp').textContent, hopp: document.querySelector('#nastaknapp').dataset.hopp }));
  kolla(efter5.hash === '#steg-5' && /Analysera/.test(efter5.text) && efter5.hopp === '6', `F1: när steg 5 setts pekar "Nästa" på Analysera (steg 6) (${JSON.stringify(efter5)})`);
  await f.click('#nastaknapp'); await stilla(f, 1500);
  await f.waitForFunction(() => location.hash === '#steg-6' && document.querySelector('#nastaknapp').hidden, null, { timeout: 10000 }).catch(() => {});
  const slut = await f.evaluate(() => ({ steg6: location.hash, dold: document.querySelector('#nastaknapp').hidden }));
  kolla(slut.steg6 === '#steg-6' && slut.dold, `F1: när steg 6 öppnats tar raden slut (hash ${slut.steg6}, Nästa dold ${slut.dold})`);
  await f.unroute('**/api/status*');
  await mock(f, 'forhandla-a');
  await f.goto(`${DASH}/?lang=sv#kedjan`); await stilla(f, 2500);
  await f.click('#nastaknapp'); await stilla(f, 1500);
  await f.waitForFunction(() => document.activeElement && document.activeElement.dataset && document.activeElement.dataset.atgard, null, { timeout: 10000 }).catch(() => {});
  const fok = await f.evaluate(() => { const b = document.activeElement; return { ar: b && b.dataset && b.dataset.atgard, kov: !!document.querySelector('#kovruta.fokus') }; });
  kolla(fok.ar === 'forhandla-a' && !fok.kov, `F3: "Nästa: Förhandla A" flyttar fokus till knappen Förhandla A, inte till KoV-rutan (fokus på ${fok.ar})`);
  await f.close();
  // KoV-rutan vid 1040 px: förklaringarna ligger under knapparna och ryms i rutan
  const k = await ny('kov-1040', { viewport: { width: 1040, height: 900 } });
  await k.goto(`${DASH}/?lang=en#steg-3`); await stilla(k, 3000);
  const kov = await k.evaluate(() => { const r = document.querySelector('#kovruta'); if (!r) return { saknas: true };
    const pr = r.getBoundingClientRect(); const ut = [...r.querySelectorAll('*')].filter(e => { const x = e.getBoundingClientRect(); return x.width > 0 && x.right > pr.right + 1; }).length;
    return { ut, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }; });
  kolla(!kov.saknas && kov.ut === 0 && kov.sw <= kov.cw, `KoV-rutan vid 1040 px: ingenting utanför rutan och ingen vågrät rullning (${JSON.stringify(kov)})`);
  await k.close();
  // Felsidor: okänd adress ger en riktig sida (inte rå JSON), och ett konstigt avtals-id ger 404-sida (inte 500)
  const rs = await ny('felsidor', { viewport: { width: 1280, height: 900 } });
  for (const v of ['/finns-inte-alls', '/avtal/%3Cscript%3E%27%22%C3%A5', '/avtal/']) {
    const svar = await rs.goto(`${DASH}${v}`, { waitUntil: 'domcontentloaded' });
    const txt = await rs.evaluate(() => document.body.innerText);
    kolla(svar.status() === 404 && !/"detail"/.test(txt) && txt.length > 10, `felsida ${v}: 404 med en läsbar sida, inte rå JSON eller 500 (${svar.status()})`);
  }
  await rs.close();
}
if (kor('nedrakning')) { // Nedräkningen till nattens nollställning: fyra lägen, båda språken, 400 och 1280 px. Serverns klocka mockas via /api/aterstallning.
  const nu = Date.now();
  const svar = min => ({nastaUtc: new Date(nu + min * 60000).toISOString(), nuUtc: new Date(nu).toISOString(), klockslag: '04:00', varaktighetMin: 10});
  const lagen = [
    ['lugn', 192, /(Nollställs|Resets) \d\d:\d\d/, '', false, false],
    ['snart', 12, /om 12 min|in 12 min/, 'snart', false, false],
    ['nu', 4, /(om|in) [34]:\d\d/, 'nu', true, false],
    ['pagar', -3, /./, 'nu', true, true],
  ];
  for (const sp of ['sv', 'en']) for (const bredd of [1280, 400]) for (const [namn, min, mon, klass, remsa] of lagen) {
    const t = await ny(`aterstall-${namn}-${sp}-${bredd}`, { viewport: { width: bredd, height: 900 } });
    await t.route('**/api/aterstallning', r => r.fulfill({json: svar(min)}));
    await t.goto(`${DASH}/?lang=${sp}`); await t.waitForSelector('#aterstall:not([hidden])', { timeout: 15000 }).catch(() => {});
    const d = await t.evaluate(() => {
      const e = document.querySelector('#aterstall'), r = document.querySelector('#aterstallremsa');
      return {syns: !e.hidden, text: e.textContent, klass: e.className, remsaSyns: !r.hidden, remsaText: r.textContent,
        sidscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        inom: e.getBoundingClientRect().right <= window.innerWidth + 0.5};
    });
    const rubrik = `${namn}/${sp}/${bredd}px`;
    kolla(d.syns && (namn === 'pagar' || mon.test(d.text)), `nedräkning ${rubrik}: visas med rätt text ("${d.text.trim()}")`);
    kolla(klass === '' ? !/snart|nu/.test(d.klass) : d.klass.includes(klass), `nedräkning ${rubrik}: färgläge ${klass || 'lugnt'}`);
    kolla(d.remsaSyns === (namn === 'nu' || namn === 'pagar') && (!d.remsaSyns || d.remsaText.length > 20), `nedräkning ${rubrik}: banner ${d.remsaSyns ? 'visas' : 'dold'} som väntat`);
    kolla(!d.sidscroll && d.inom, `nedräkning ${rubrik}: ingen sidledsrullning, ligger inom bilden`);
    await t.close();
  }
  // Utan schema (lokalt) ska inget visas.
  const t0 = await ny('aterstall-saknas', { viewport: { width: 1280, height: 900 } });
  await t0.route('**/api/aterstallning', r => r.fulfill({json: {nastaUtc: null}}));
  await t0.goto(`${DASH}/`); await stilla(t0, 1500);
  kolla(await t0.evaluate(() => document.querySelector('#aterstall').hidden && document.querySelector('#aterstallremsa').hidden), 'nedräkningen är dold när inget schema är satt');
  await t0.close();
  // Extern variant: inga interna värdnamn i nedräkningen (sidan skrubbas av servern).
  const te = await ny('aterstall-lackage', { viewport: { width: 1280, height: 900 } });
  await te.route('**/api/aterstallning', r => r.fulfill({json: svar(4)}));
  await te.goto(`${DASH}/?lang=sv`); await te.waitForSelector('#aterstallremsa:not([hidden])', { timeout: 15000 }).catch(() => {});
  const lacka = await te.evaluate(() => (document.querySelector('#aterstall').textContent + document.querySelector('#aterstallremsa').textContent));
  kolla(!/edc-|ingest-service|orion-|docker|localhost/i.test(lacka), 'nedräkning och banner nämner inga interna namn');
  await te.close();
}
if (kor('uppdatering')) { // Planerad uppdatering (varselfilen): samma element som nattens nedräkning men med uppdateringens fasta texter. Remsan visas redan vid 15 minuter (orange).
  const nu = Date.now();
  const svar = min => ({nastaUtc: new Date(nu + min * 60000).toISOString(), nuUtc: new Date(nu).toISOString(), klockslag: '20:05', tz: 'Europe/Stockholm', varaktighetMin: 3, typ: 'uppdatering'});
  const lagen = [
    ['snart', 14, /(Uppdateras|Updates) \d\d:\d\d/, 'snart', true, /uppdateras om|updated in/i],
    ['nu', 4, /(Uppdateras om|Updates in) [34]:\d\d/, 'nu', true, /Avsluta det du gör|Finish what you are doing/],
    ['pagar', -1, /Uppdatering pågår|Update in progress/, 'nu', true, /uppdateras just nu|being updated right now/],
  ];
  for (const sp of ['sv', 'en']) for (const bredd of [1280, 400]) for (const [namn, min, mon, klass, remsa, remsamon] of lagen) {
    const t = await ny(`uppdatering-${namn}-${sp}-${bredd}`, { viewport: { width: bredd, height: 900 } });
    await t.route('**/api/aterstallning', r => r.fulfill({json: svar(min)}));
    await t.goto(`${DASH}/?lang=${sp}`); await t.waitForSelector('#aterstall:not([hidden])', { timeout: 15000 }).catch(() => {});
    const d = await t.evaluate(() => {
      const e = document.querySelector('#aterstall'), r = document.querySelector('#aterstallremsa');
      return {text: e.textContent, klass: e.className, remsaSyns: !r.hidden, remsaText: r.textContent, remsaKlass: r.className,
        sidscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth, inom: e.getBoundingClientRect().right <= window.innerWidth + 0.5};
    });
    const rubrik = `${namn}/${sp}/${bredd}px`;
    kolla(mon.test(d.text), `uppdatering ${rubrik}: raden säger uppdatering, inte nollställning ("${d.text.trim()}")`);
    kolla(d.klass.includes(klass), `uppdatering ${rubrik}: färgläge ${klass}`);
    kolla(d.remsaSyns && remsamon.test(d.remsaText) && !/raderas|deleted/.test(d.remsaText), `uppdatering ${rubrik}: remsan visas, säger uppdatering och lovar inte att data raderas`);
    if (namn === 'snart') kolla(d.remsaKlass.includes('snart'), `uppdatering ${rubrik}: remsan är orange vid 15 minuter (röd först de sista fem)`);
    kolla(!d.sidscroll && d.inom, `uppdatering ${rubrik}: ingen sidledsrullning, ligger inom bilden`);
    await t.close();
  }
  // Förklaringsdialogen säger uppdatering, att data finns kvar och spärren de sista två minuterna.
  for (const sp of ['sv', 'en']) {
    const t = await ny(`uppdatering-dialog-${sp}`, { viewport: { width: 1280, height: 900 } });
    await t.route('**/api/aterstallning', r => r.fulfill({json: svar(10)}));
    await t.goto(`${DASH}/?lang=${sp}`); await t.waitForSelector('#aterstallinfo:not([hidden])', { timeout: 15000 }).catch(() => {});
    await t.click('#aterstallinfo');
    const rubrikText = await t.evaluate(() => document.querySelector('#aterstalldialogrubrik').textContent + ' | ' + document.querySelector('#aterstalldialogtext').textContent);
    kolla(sp === 'sv' ? /Varför uppdateras demon\?/.test(rubrikText) && /Plattformens data finns kvar/.test(rubrikText) && /två minuterna/.test(rubrikText)
                      : /Why is the demo being updated\?/.test(rubrikText) && /platform's data stays/.test(rubrikText) && /two minutes/.test(rubrikText), `uppdatering: dialogen förklarar (${sp})`);
    await t.close();
  }
  { // Knappens namn följer typen (skärmläsare), spärrens felrad ligger kvar, och en misslyckad hämtning släcker inte läget "pågår".
    const t = await ny('uppdatering-knapp-och-fel', { viewport: { width: 1280, height: 900 } });
    let antal = 0;
    await t.route('**/api/aterstallning', r => { antal++; return antal === 1 ? r.fulfill({json: svar(-1)}) : r.fulfill({status: 503, contentType: 'text/html', body: '<h1>nere</h1>'}); });
    await t.route('**/api/atgard/**', r => r.fulfill({status: 409, json: {fel: 'Demon uppdateras strax.', kod: 'fel.uppdatering_strax'}}));
    await t.goto(`${DASH}/?lang=sv#steg-1`); await t.waitForSelector('#aterstallremsa:not([hidden])', { timeout: 15000 }).catch(() => {});
    kolla(/uppdater/i.test(await t.getAttribute('#aterstallinfo', 'aria-label') || ''), 'uppdatering: knappen "?" heter Om uppdateringen, inte Om nollställningen');
    await t.evaluate(() => hamtaAterstall()); await stilla(t, 800);
    kolla(await t.evaluate(() => !document.querySelector('#aterstallremsa').hidden), 'en misslyckad hämtning (503) släcker inte remsan medan uppdateringen pågår');
    const kb = t.locator('button.kor[data-atgard]:not([disabled])').first();
    if (await kb.count()) {
      await kb.click(); await stilla(t, 6500);
      kolla(await t.evaluate(() => /uppdateras strax/i.test(document.body.textContent) && !!document.querySelector('.felrad') && !document.querySelector('.upptagetfel')),
        'spärrens felrad ("Demon uppdateras strax") ligger kvar efter 6 s och räknas inte som "ett jobb kör"');
    } else kolla(false, 'uppdatering: ingen körknapp att pröva spärren med');
    await t.close();
  }
  // En nollställning som typ i svaret beter sig som nattens (inga ändrade texter): skyddar mot att typen läses fel.
  const tn = await ny('uppdatering-typ-nollstallning', { viewport: { width: 1280, height: 900 } });
  await tn.route('**/api/aterstallning', r => r.fulfill({json: {...svar(4), typ: 'nollstallning', varaktighetMin: 10}}));
  await tn.goto(`${DASH}/?lang=sv`); await tn.waitForSelector('#aterstallremsa:not([hidden])', { timeout: 15000 }).catch(() => {});
  kolla(/nollställs om/i.test(await tn.evaluate(() => document.querySelector('#aterstallremsatext').textContent)), 'planerad nollställning (typ nollstallning) visar nollställningens text');
  await tn.close();
}
if (kor('skydd')) { // Tickande tider i den publika demon (skydd.py): utestängd part, felinjektionens slut och väntan efter ett jobb.
  for (const sp of ['sv', 'en']) for (const bredd of [1280, 400]) {
    const t = await ny(`skydd-${sp}-${bredd}`, { viewport: { width: bredd, height: 900 } });
    const start = Date.now();     // serverns väntan räknas ned i verklig tid, som den riktiga
    await t.route('**/api/skydd', r => r.fulfill({json: {utestangningS: {stad: 161}, felinjektionS: 272, pausS: Math.max(0, Math.ceil(3 - (Date.now() - start) / 1000))}}));
    await t.goto(`${DASH}/?lang=${sp}#steg-3`);
    await t.waitForSelector('#pausremsa:not([hidden])', { timeout: 15000 }).catch(() => {});
    const d = await t.evaluate(() => ({
      paus: document.querySelector('#pausremsa').textContent,
      knappar: [...document.querySelectorAll('button.kor[data-atgard]:not([data-svada])')].filter(b => b.offsetParent).map(b => b.disabled),
      sidscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      srAntal: document.querySelector('#skyddsr').textContent.length }));
    const r = `${sp}/${bredd}px`;
    kolla(new RegExp(sp === 'sv' ? 'Vänta \\d s' : 'Wait \\d s').test(d.paus), `kön ${r}: banner med nedräkning ("${d.paus.slice(0, 40)}…")`);
    kolla(d.knappar.length > 0 && d.knappar.every(x => x), `kön ${r}: åtgärdsknapparna är låsta under väntan (${d.knappar.length} synliga)`);
    kolla(!d.sidscroll, `skydd ${r}: ingen sidledsrullning`);
    // Vänta in att bannern faktiskt släpper (tickandet kan släpa på en belastad maskin) i stället för en fast paus.
    await t.waitForSelector('#pausremsa', { state: 'hidden', timeout: 10000 }).catch(() => {});
    await t.waitForTimeout(300);
    const e = await t.evaluate(() => ({dold: document.querySelector('#pausremsa').hidden,
      knappar: [...document.querySelectorAll('button.kor[data-atgard]:not([data-svada])')].filter(b => b.offsetParent).map(b => b.disabled),
      sr: document.querySelector('#skyddsr').textContent }));
    kolla(e.dold && e.knappar.every(x => !x), `kön ${r}: banner borta och knapparna fria när väntan är slut`);
    kolla(/köra igen|run again/.test(e.sr), `kön ${r}: skärmläsaren får besked om bytet ("${e.sr}")`);
    await t.goto('about:blank'); await t.goto(`${DASH}/?lang=${sp}#felinjektion`);
    await t.waitForFunction(() => /\d:\d\d/.test(document.querySelector('#felrest')?.textContent || ''), null, { timeout: 15000 }).catch(() => {});
    const f = await t.evaluate(() => document.querySelector('#felrest')?.textContent || '');
    kolla(/[0-4]:\d\d/.test(f) && (sp === 'sv' ? /automatiskt/.test(f) : /automatically/.test(f)), `felinjektion ${r}: "${f}"`);
    await t.close();
  }
}
if (kor('aterstall')) { // ?aterstall=<minuter> simulerar nedräkningens lägen; texten växer och blir röd ju närmare nollställningen.
  const t = await ny('aterstall-sim', { viewport: { width: 1280, height: 900 } });
  const lage = async (min, sp = 'sv') => {
    await t.goto('about:blank'); await t.goto(`${DASH}/?lang=${sp}&aterstall=${min}`);
    await t.waitForSelector('#aterstall:not([hidden])', { timeout: 15000 }).catch(() => {});
    return t.evaluate(() => { const e = document.querySelector('#aterstall'), c = getComputedStyle(e);
      return {text: e.textContent, klass: e.className, px: parseFloat(c.fontSize), bg: c.backgroundColor, banner: !document.querySelector('#aterstallremsa').hidden}; });
  };
  const lugn = await lage(190), snart = await lage(12), nu = await lage(4), sista = await lage(0.5), pagar = await lage(-2);
  kolla(lugn.px < snart.px && snart.px < nu.px, `simulering: texten växer ju närmare (${lugn.px} → ${snart.px} → ${nu.px} px)`);
  kolla(/^aterstall nu$/.test(nu.klass) && /\d:\d\d/.test(nu.text) && /simulering/.test(nu.text) && nu.banner, `simulering: 4 min är röd, visar m:ss och banner ("${nu.text.trim()}")`);
  kolla(/sista/.test(sista.klass) && !/sista/.test(nu.klass), 'simulering: sista minuten får pulsklassen, 4 min inte');
  kolla(/pågår/.test(pagar.text) && pagar.banner, 'simulering: negativt värde visar "Nollställning pågår"');
  const en = await lage(4, 'en');
  kolla(/Resets in [34]:\d\d/.test(en.text), `simulering (en): "${en.text.trim()}"`);
  await t.close();
}
if (kor('forklaring')) { // Förklaringen bakom frågetecknet: öppnas, visar tiden i besökarens tidszon, stängs med Esc, fokus går tillbaka.
  const nu = Date.now();
  // Nästa 04:00 svensk tid, räknat från nu (ett fast datum blev gammalt och gav "0:00" – sommar-/vintertid ger 02:00 eller 03:00 UTC).
  const sv04 = d => new Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Stockholm', hour: '2-digit', minute: '2-digit', hour12: false}).format(d) === '04:00';
  let kand = new Date(Math.ceil((nu + 3600e3) / 900e3) * 900e3);               // närmaste kvart minst en timme fram
  while (!sv04(kand)) kand = new Date(kand.getTime() + 900e3);
  const nasta = kand.toISOString();
  const svar = {nastaUtc: nasta, nuUtc: new Date(nu).toISOString(), klockslag: '04:00', tz: 'Europe/Stockholm', varaktighetMin: 10};
  // Facit för New York räknas fram för just detta datum (del e, E8): 04:00 svensk tid är 22:00 i New York de flesta veckor,
  // men 23:00 när sommartiden bytts i bara den ena zonen (slutet av oktober, mars). Ett fast "22:00" blev falskt rött då.
  const nyKlocka = d => { const f = o => new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit', ...o}).format(d);
    return new RegExp(`${f({hourCycle: 'h23'}).padStart(5, '0')}|${f({hour12: true}).replace(/\s/g, '\\s?')}`); };
  const nyRe = nyKlocka(kand);
  const zoner = [['Europe/Stockholm', /04:00/, /svensk tid|Swedish time/, false], ['America/New_York', nyRe, /svensk tid|Swedish time/, true]];
  for (const [sp, bredd] of [['sv', 1280], ['en', 1280], ['sv', 400], ['en', 400]]) for (const [zon, lokalt, svenskt, skiljer] of zoner) {
    const t = await ny(`aterstallinfo-${sp}-${bredd}-${zon}`, { viewport: { width: bredd, height: 900 }, timezoneId: zon });
    await t.route('**/api/aterstallning', r => r.fulfill({json: svar}));
    await t.goto(`${DASH}/?lang=${sp}`); await t.waitForSelector('#aterstallinfo:not([hidden])', { timeout: 15000 }).catch(() => {});
    const rad = await t.textContent('#aterstall');
    kolla(lokalt.test(rad), `klockan i raden följer besökarens tidszon ${sp}/${bredd}px/${zon} (facit ${lokalt.source}): "${rad.trim()}"`);
    await t.focus('#aterstallinfo'); await t.keyboard.press('Enter');
    const d = await t.evaluate(() => { const g = document.querySelector('#aterstalldialog');
      return {open: g.open, text: g.textContent, scroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
              inom: g.getBoundingClientRect().right <= innerWidth + 0.5 && g.getBoundingClientRect().left >= -0.5}; });
    kolla(d.open && (skiljer ? svenskt.test(d.text) : !/din tidszon|your time zone/.test(d.text)), `förklaringen öppnas med tangentbord (${sp}/${bredd}px/${zon}) och ${skiljer ? 'nämner båda tidszonerna' : 'nämner bara en tid'}`);
    kolla(d.inom && !d.scroll && (/04:00/.test(d.text) || nyRe.test(d.text)), `förklaringen ryms i bilden (${sp}/${bredd}px/${zon})`);
    await t.keyboard.press('Escape');
    const efter = await t.evaluate(() => ({open: document.querySelector('#aterstalldialog').open, fokus: document.activeElement?.id}));
    kolla(!efter.open && efter.fokus === 'aterstallinfo', `Esc stänger och fokus går tillbaka till frågetecknet (${sp}/${bredd}px/${zon})`);
    await t.close();
  }
  { // Samma prov ett datum då skillnaden Stockholm–New York är den ANDRA (sommartiden bytt i bara en zon, eller tvärtom).
    let avv = new Date(kand.getTime() + 86400e3);
    for (let i = 0; i < 400 && nyKlocka(avv).source === nyRe.source; i++) {
      avv = new Date(avv.getTime() + 86400e3);
      while (!sv04(avv)) avv = new Date(avv.getTime() + 900e3);   // 04:00 svensk tid flyttar sig i UTC vid sommartidsbytet
    }
    const reAvv = nyKlocka(avv);
    const t = await ny('aterstallinfo-dst', { viewport: { width: 1280, height: 900 }, timezoneId: 'America/New_York' });
    await t.route('**/api/aterstallning', r => r.fulfill({json: {...svar, nastaUtc: avv.toISOString()}}));
    await t.goto(`${DASH}/?lang=sv`); await t.waitForSelector('#aterstallinfo:not([hidden])', { timeout: 15000 }).catch(() => {});
    const rad = await t.textContent('#aterstall');
    kolla(reAvv.source !== nyRe.source && reAvv.test(rad),
          `tidszon under ett annat sommartidsläge (${avv.toISOString().slice(0, 10)}, facit ${reAvv.source}, vanligt ${nyRe.source}): "${rad.trim()}"`);
    await t.close();
  }
  // Länken i den röda bannern öppnar samma förklaring.
  const tb = await ny('aterstallinfo-banner', { viewport: { width: 1280, height: 900 } });
  await tb.goto(`${DASH}/?lang=sv&aterstall=4`); await tb.waitForSelector('#aterstallremsa:not([hidden])', { timeout: 15000 }).catch(() => {});
  await tb.click('#aterstallremsa [data-aterstallinfo]');
  kolla(await tb.evaluate(() => document.querySelector('#aterstalldialog').open), 'länken i bannern öppnar förklaringen');
  kolla(!/edc-|ingest-service|orion-|docker|localhost/i.test(await tb.textContent('#aterstalldialog')), 'förklaringen nämner inga interna namn');
  await tb.close();
  // Publika vyn: samma knapp och förklaring.
  const PV = process.env.PUBLIKVY || 'http://localhost:38085';
  const tp = await ny('aterstallinfo-publik', { viewport: { width: 400, height: 800 }, timezoneId: 'America/New_York' });
  await tp.route('**/api/aterstallning', r => r.fulfill({json: svar}));
  await tp.goto(`${PV}/?lang=en`); await tp.waitForSelector('#aterstallinfo:not([hidden])', { timeout: 15000 }).catch(() => {});
  await tp.click('#aterstallinfo');
  const pt = await tp.evaluate(() => ({open: document.querySelector('#aterstalldialog').open, text: document.querySelector('#aterstalldialog').textContent}));
  kolla(pt.open && /Swedish time/.test(pt.text) && nyRe.test(pt.text), 'publika vyn: förklaringen öppnas och visar besökarens tid och svensk tid');
  await tp.keyboard.press('Escape');
  kolla(!(await tp.evaluate(() => document.querySelector('#aterstalldialog').open)), 'publika vyn: Esc stänger förklaringen');
  await tp.close();
}
if (kor('stegrad')) { // Miniversionen av banan (stegraden) syns överst på Flödet, under sidhuvudet, och sitter kvar överst när man scrollar (bred skärm)
  const sr = await ny('stegrad-topp', { viewport: { width: 1280, height: 900 } });
  await sr.goto(`${DASH}/?lang=sv#kedjan`); await stilla(sr, 1500);
  await sr.evaluate(() => window.scrollTo(0, 0)); await sr.waitForTimeout(300);
  const topp = await sr.evaluate(() => { const s = document.getElementById('stegrad'), h = document.querySelector('header'); const r = s.getBoundingClientRect();
    return { synlig: !s.hidden && !!s.checkVisibility(), knappar: s.querySelectorAll('button[data-steg]').length, underHuvud: r.top >= h.getBoundingClientRect().bottom - 1, scroll: Math.round(window.scrollY) }; });
  kolla(topp.synlig && topp.knappar === 6 && topp.underHuvud && topp.scroll === 0, `stegraden: syns överst på Flödet (scroll ${topp.scroll}), med sex steg och under sidhuvudet (${JSON.stringify(topp)})`);
  await sr.waitForFunction(() => document.documentElement.scrollHeight > 2200, null, { timeout: 15000 }).catch(() => {});   // sidan ska vara hög nog att rulla
  await sr.evaluate(() => window.scrollTo(0, 1500)); await sr.waitForTimeout(500);
  kolla(await sr.evaluate(() => Math.abs(document.getElementById('stegrad').getBoundingClientRect().top) <= 2), 'stegraden: sitter kvar överst i bild när man scrollar ned');
  await sr.evaluate(() => document.querySelector('nav#flikar button[data-flik="jobb"]').click()); await sr.waitForTimeout(500);
  kolla(await sr.evaluate(() => !document.getElementById('stegrad').checkVisibility()), 'stegraden: syns inte på andra flikar (Jobb)');
  await sr.close();
}
if (kor('lagen')) { // Raden som följer med har två lägen med eget namn: Flödet (steg 1–6) och Guidad bana (delarna A–H); guiden är vald tills man avslutar den
  for (const sprak of ['sv', 'en']) {
    const g = await ny('stegrad-lage-' + sprak, { viewport: { width: 1280, height: 900 } });
    await g.goto(`${DASH}/?lang=${sprak}#kedjan`); await stilla(g, 1500);
    const lage = () => g.evaluate(() => { const s = document.getElementById('stegrad'), syns = sel => [...s.querySelectorAll(sel)].filter(x => x.checkVisibility()).length;
      return { lage: s.dataset.lage, rub: [...s.querySelectorAll('.srub')].filter(x => x.checkVisibility()).map(x => x.textContent.trim()), flode: syns('button[data-steg]'), guide: syns('button.sg'),
               start: syns('.sstart'), avsluta: syns('.savsluta'), nasta: syns('#snasta'), bokstaver: [...s.querySelectorAll('button.sg')].map(x => x.textContent.replace('✓', '').trim()).join('') }; });
    const a = await lage();
    kolla(a.lage === 'flode' && a.flode === 6 && a.guide === 0 && a.start === 1 && a.avsluta === 0 && a.rub.length === 1, `raden (${sprak}): utan val står den i läget Flödet (6 steg, ingen guide) ${JSON.stringify(a)}`);
    kolla(a.rub[0] === (sprak === 'sv' ? 'Flödet:' : 'The flow:'), `raden (${sprak}): etiketten heter detsamma som bilden ('${a.rub[0]}')`);
    await g.click('#stegrad .sstart'); await stilla(g, 600);
    const b = await lage();
    kolla(b.lage === 'guide' && b.flode === 0 && b.guide === 8 && b.avsluta === 1 && b.start === 0 && b.bokstaver === 'ABCDEFGH' && b.rub[0] === (sprak === 'sv' ? 'Guidad bana:' : 'Guided path:'), `raden (${sprak}): Starta guidad bana byter raden till guiden med delarna A–H ${JSON.stringify(b)}`);
    kolla(b.nasta === 1 && await g.evaluate(() => document.getElementById('snasta').textContent.startsWith(document.getElementById('nastaknapp').textContent.trim())), `raden (${sprak}): guideraden har samma Nästa-knapp som remsan`);
    kolla(await g.evaluate(() => [...document.querySelectorAll('#ordning .ordningsteg button[data-hopp]:not(.nastaknapp) .snr')].map(x => x.textContent.replace('✓', '').trim()).join('') === 'ABCDEFGH'), `remsan (${sprak}): delarna heter A–H, siffrorna är flödets steg`);
    kolla(await g.evaluate(() => [...document.querySelectorAll('#stegrad button.sg')].every(x => /\b[1-6]\b/.test(x.title) && /\b[1-6]\b/.test(x.getAttribute('aria-label')))), `raden (${sprak}): varje guidedel säger vilket flödessteg den hör till (title och aria-label)`);
    await g.click('#nod-2'); await stilla(g, 600);
    kolla((await lage()).lage === 'guide', `raden (${sprak}): ett klick på en nod i bilden lämnar inte guiden`);
    await g.click('#stegrad button.sg[data-gi="2"]'); await stilla(g, 800);
    kolla(await g.evaluate(() => !document.getElementById('steg-3').hidden), `raden (${sprak}): del C i guideraden öppnar steg 3`);
    await g.reload(); await stilla(g, 1500);
    kolla((await lage()).lage === 'guide', `raden (${sprak}): guiden är kvar vald efter omladdning (samma besök)`);
    await g.click('#stegrad .savsluta'); await stilla(g, 400);
    const c = await lage();
    kolla(c.lage === 'flode' && c.flode === 6 && c.guide === 0 && c.start === 1, `raden (${sprak}): Avsluta guiden ger tillbaka Flödet-raden ${JSON.stringify(c)}`);
    await g.close();
  }
}
if (kor('synk')) { // Synk: jobbrutan får inte säga "klart" medan knappen som startade jobbet fortfarande snurrar (båda ändras i samma ögonblick)
  const sy = await ny('jobb-synk', { viewport: { width: 1280, height: 900 } });
  await sy.goto(`${DASH}/?lang=sv#steg-1`); await stilla(sy, 1500);
  await sy.waitForFunction(() => !document.querySelector('button.kor[data-atgard="kor-batch"]')?.disabled, null, { timeout: 60000 }).catch(() => {});
  await sy.evaluate(() => {
    window.__synk = { klarMedSnurra: 0, klarSedd: false, prov: 0 };
    const kn = document.querySelector('#steg-1 button.kor[data-atgard="kor-batch"]');
    setInterval(() => { const k = document.querySelector('#kort-kor-batch .lstatus.klar'); window.__synk.prov++;
      if (k) { window.__synk.klarSedd = true; if (kn.classList.contains('pagar') || kn.getAttribute('aria-busy') === 'true') window.__synk.klarMedSnurra++; } }, 40);
    kn.click();
  });
  await sy.waitForFunction(() => window.__synk.klarSedd, null, { timeout: 90000 }).catch(() => {});
  await sy.waitForTimeout(1500);
  const r = await sy.evaluate(() => window.__synk);
  kolla(r.klarSedd && r.klarMedSnurra === 0, `synk: "jobbet klart" visas aldrig medan knappen snurrar (klar sedd: ${r.klarSedd}, samtidigt med snurra: ${r.klarMedSnurra} av ${r.prov} avläsningar)`);
  kolla(await sy.evaluate(() => !document.querySelector('button.kor.pagar') && !document.querySelector('button.kor[data-atgard="kor-batch"]').disabled), 'synk: när klart står är snurran borta och knappen åter tryckbar');
  await sy.close();
}
if (kor('synkjobb')) { // Synk på fliken Jobb: listan får inte säga "klart" om det nyaste jobbet medan raden "Jobb körs" ännu står kvar
  const sj = await ny('jobb-synk-flik', { viewport: { width: 1280, height: 900 } });
  await sj.goto(`${DASH}/?lang=sv#kedjan`); await stilla(sj, 1500);
  await sj.waitForFunction(() => !document.querySelector('button.kor[data-atgard="kor-batch"]')?.disabled, null, { timeout: 60000 }).catch(() => {});
  await sj.evaluate(() => {
    window.__sj = { fel: 0, klar: false, prov: 0 };
    setInterval(() => { const rad = document.querySelector('#jobblista tr td:nth-child(3)'), kor = document.getElementById('jobbrad'); if (!rad) return; window.__sj.prov++;
      if (/klart/i.test(rad.textContent)) { window.__sj.klar = true; if (kor && kor.textContent.trim()) window.__sj.fel++; } }, 40);
    kor('kor-batch', {});
  });
  await sj.waitForFunction(() => window.__sj.klar, null, { timeout: 90000 }).catch(() => {});
  await sj.waitForTimeout(1500);
  const r = await sj.evaluate(() => window.__sj);
  kolla(r.klar && r.fel === 0, `synk (fliken Jobb): listan säger "klart" först när raden "Jobb körs" släppt (klar sedd: ${r.klar}, samtidigt: ${r.fel} av ${r.prov})`);
  await sj.close();
}
if (kor('vagval')) { // Vägvalet: guiden är huvudvalet med en flytande "Börja här!"-bubbla över knappen; den försvinner när man väljer väg, går vidare eller stänger den
  for (const sprak of ['sv', 'en']) {
    const v = await ny('vagval-' + sprak, { viewport: { width: 1280, height: 900 } });
    const syns = () => v.evaluate(() => { const b = document.getElementById('borjabubbla'); return !b.hidden && !!b.checkVisibility(); });
    await v.goto(`${DASH}/?lang=${sprak}#kedjan`); await stilla(v, 1500);
    kolla(await syns(), `vägvalet (${sprak}): "Börja här!"-bubblan syns första gången`);
    const lay = await v.evaluate(() => { const h = document.querySelector('.vagvalrub'), kort = document.querySelector('.vagvalkort'), kn = document.querySelector('.vagvalval.stor .vagknapp'), intro = document.getElementById('intro');
      const fs = e => parseFloat(getComputedStyle(e).fontSize), rh = h.getBoundingClientRect();
      return { rub: fs(h), knapp: fs(kn), tillKort: Math.round(kort.getBoundingClientRect().top - rh.bottom), franIntro: intro ? Math.round(rh.top - intro.getBoundingClientRect().bottom) : 999 }; });
    kolla(lay.rub >= lay.knapp && lay.tillKort < lay.franIntro, `vägvalet (${sprak}): rubriken är minst lika stor som knappen (${lay.rub} mot ${lay.knapp} px) och ligger närmare korten (${lay.tillKort} px) än introduktionen (${lay.franIntro} px)`);
    const g = await v.evaluate(() => { const r = e => e.getBoundingClientRect(), b = r(document.getElementById('borjabubbla')), k = r(document.querySelector('.vagvalval.stor')), kn = r(document.querySelector('.vagvalval.stor .vagknapp'));
      const h = document.querySelector('.vagvalrub').getBoundingClientRect();
      return { ovanKnapp: b.bottom <= kn.top + 1, inomKort: b.left >= k.left && b.right <= k.right, motRubrik: b.top >= h.bottom - 1, roll: document.getElementById('borjabubbla').getAttribute('role'), fokus: document.activeElement === document.getElementById('borjabubbla'),
               tva: document.querySelectorAll('.vagvalval .vagknapp').length, minH: Math.round(kn.height) }; });
    kolla(g.ovanKnapp && g.inomKort && g.motRubrik && g.roll === 'note' && !g.fokus && g.tva === 2 && g.minH >= 44, `vägvalet (${sprak}): bubblan ligger ovanför huvudknappen, täcker inte rubriken, stjäl inte fokus; två vägar, knapp minst 44 px ${JSON.stringify(g)}`);
    await v.click('[data-borja-stang]', { force: true }); await stilla(v, 300);   // force: bubblan flyter, så Playwright ser den aldrig som stilla
    kolla(!(await syns()), `vägvalet (${sprak}): ✕ döljer bubblan`);
    await v.reload(); await stilla(v, 1200);
    kolla(!(await syns()), `vägvalet (${sprak}): bubblan kommer inte tillbaka i samma besök`);
    await v.evaluate(() => sessionStorage.clear()); await v.reload(); await stilla(v, 1200);
    await v.click('#nod-2'); await stilla(v, 500);
    kolla(!(await syns()), `vägvalet (${sprak}): bubblan försvinner när man går vidare (öppnar ett steg)`);
    await v.goto(`${DASH}/?lang=${sprak}#steg-4`); await v.evaluate(() => sessionStorage.clear()); await v.reload(); await stilla(v, 1200);
    kolla(await syns(), `vägvalet (${sprak}): bubblan syns även när första sidan är ett djupt steg (#steg-4)`);
    await v.goto(`${DASH}/?lang=${sprak}#kedjan`); await v.evaluate(() => sessionStorage.clear()); await v.reload(); await stilla(v, 1200);
    const malsteg = await v.evaluate(() => { const n = document.getElementById('nastaknapp'); return n && !n.hidden && n.dataset.hopp ? n.dataset.hopp : '1'; });   // steget som står på tur (beror på vad som körts förut)
    await v.click('.vagvalval.stor .vagknapp'); await stilla(v, 1500);
    kolla(await v.evaluate((nr) => { const p = document.getElementById('steg-' + nr), r = p.getBoundingClientRect(), bar = document.getElementById('stegrad').getBoundingClientRect(), rem = document.getElementById('ordning').getBoundingClientRect();
      return !p.hidden && r.top >= bar.bottom - 2 && r.top < window.innerHeight * 0.6 && rem.bottom < bar.bottom + 4; }, malsteg),
      `vägvalet (${sprak}): Starta guidad bana öppnar steget som står på tur (steg ${malsteg}) och landar på det (remsan ligger ovanför, inte intill raden)`);
    kolla(!(await syns()) && await v.evaluate(() => document.getElementById('stegrad').dataset.lage === 'guide'), `vägvalet (${sprak}): Starta guidad bana väljer guiden och döljer bubblan`);
    await v.evaluate(() => sessionStorage.clear()); await v.reload(); await stilla(v, 1200);
    await v.click('.vagvalval:not(.stor) .vagknapp'); await stilla(v, 500);
    kolla(!(await syns()) && await v.evaluate(() => document.getElementById('stegrad').dataset.lage === 'flode'), `vägvalet (${sprak}): Utforska flödet själv väljer Flödet och döljer bubblan`);
    await v.close();
  }
  const rm = await b.newPage({ locale: 'sv-SE', viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
  await rm.goto(`${DASH}/?lang=sv#kedjan`); await stilla(rm, 1500);
  kolla(await rm.evaluate(() => getComputedStyle(document.getElementById('borjabubbla')).animationName === 'none'), 'vägvalet: med "minska rörelse" flyter bubblan inte');
  await rm.close();
  const sm = await ny('vagval-smal', { viewport: { width: 400, height: 800 } });
  await sm.goto(`${DASH}/?lang=sv#kedjan`); await stilla(sm, 1500);
  kolla(await sm.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1 && document.getElementById('borjabubbla').getBoundingClientRect().right <= window.innerWidth && document.getElementById('borjabubbla').getBoundingClientRect().left >= 0), 'vägvalet (400 px): bubblan ryms i bredd och sidan scrollar inte i sidled');
  await sm.close();
}
if (kor('startsida')) { // Startsidan är alltid överblicken (bilden utan öppen panel), för en ny besökare, en som kommer tillbaka och efter ett klick på loggan; en djuplänk öppnar sitt steg
  for (const sprak of ['sv', 'en']) {
    const h = await ny('startsida-' + sprak, { viewport: { width: 1280, height: 900 } });
    const lage = () => h.evaluate(() => ({ oppna: [...document.querySelectorAll('.panel')].filter(p => !p.hidden).map(p => p.id), hash: location.hash, nodOppen: !!document.querySelector('.nod[aria-expanded="true"]') }));
    await h.goto(`${DASH}/?lang=${sprak}`); await stilla(h, 1500);
    let a = await lage();
    kolla(a.oppna.length === 0 && a.hash === '#kedjan' && !a.nodOppen, `startsidan (${sprak}): en ny besökare utan fragment får överblicken, inget steg öppet ${JSON.stringify(a)}`);
    await h.evaluate(() => { localStorage.setItem('svada-steg', '5'); });          // ett gammalt minne av ett öppet steg ska inte styra längre
    await h.reload(); await stilla(h, 1200);
    a = await lage();
    kolla(a.oppna.length === 0, `startsidan (${sprak}): ett minne av ett tidigare öppet steg styr inte startsidan`);
    await h.click('#nod-4'); await stilla(h, 600);
    kolla((await lage()).oppna.join() === 'steg-4', `startsidan (${sprak}): ett klick på en nod öppnar steget`);
    await h.reload(); await stilla(h, 1200);
    kolla((await lage()).oppna.join() === 'steg-4', `startsidan (${sprak}): omladdning med #steg-4 i adressen öppnar steg 4 (adressen bär valet)`);
    await h.click('a.loggalank'); await stilla(h, 800);
    a = await lage();
    kolla(a.oppna.length === 0 && a.hash === '#kedjan', `startsidan (${sprak}): loggan leder till samma överblick ${JSON.stringify(a)}`);
    await h.goto(`${DASH}/?lang=${sprak}`); await stilla(h, 1200);
    kolla((await lage()).oppna.length === 0, `startsidan (${sprak}): adressen utan fragment ger samma överblick som loggan`);
    await h.close();
  }
}
if (kor('bornom')) { // Börja om i raden: bara i guiden; två klick; ett anrop; ingen dialog
  const bo = await ny('borja-om', { viewport: { width: 1280, height: 900 } });
  const anrop = [];
  await bo.route('**/api/session/ny', async r => { anrop.push(r.request().method()); await r.fulfill({ json: { ok: true } }); });
  await bo.goto(`${DASH}/?lang=sv#kedjan`); await stilla(bo, 1500);
  await bo.evaluate(() => sessionStorage.setItem('svada-lage', 'guide')); await bo.reload(); await stilla(bo, 1500);
  kolla(await bo.evaluate(() => document.getElementById('sbornom').checkVisibility()), 'börja om: syns i guideläget även lokalt (utan sessioner nollställer servern det delade tillståndet)');
  await bo.click('#stegrad .savsluta'); await stilla(bo, 300);
  kolla(await bo.evaluate(() => !document.getElementById('sbornom').checkVisibility()), 'börja om: syns inte i Flödet-läget');
  await bo.click('#stegrad .sstart'); await stilla(bo, 1200);
  await bo.click('#sbornom'); await stilla(bo, 300);
  kolla(await bo.evaluate(() => { const k = document.getElementById('sbornom').getBoundingClientRect(), r = document.getElementById('stegrad').getBoundingClientRect(); return k.right <= r.right + 1 && k.left >= r.left - 1 && document.getElementById('stegrad').scrollWidth <= document.getElementById('stegrad').clientWidth + 1; }), 'börja om: bekräftelsen ryms i raden, ingen text utanför fönstret');
  kolla(anrop.length === 0 && await bo.evaluate(() => document.getElementById('sbornom').classList.contains('sakert') && /igen|again/.test(document.getElementById('sbornom').textContent)), 'börja om: första klicket ber bara om bekräftelse, inget anrop');
  const laddad = bo.waitForNavigation({ timeout: 8000 }).catch(() => null);
  await bo.click('#sbornom'); await laddad; await stilla(bo, 1500);
  kolla(anrop.join() === 'POST', `börja om: andra klicket gör ett POST-anrop (${anrop.join()}) och laddar om`);
  const efter = await bo.evaluate(() => ({ lage: document.getElementById('stegrad').dataset.lage, hash: location.hash, minne: sessionStorage.getItem('svada-lage') }));
  const bub = await bo.evaluate(() => { const b = document.getElementById('borjabubbla'); return !b.hidden && !!b.checkVisibility(); });
  kolla(efter.lage === 'flode' && efter.hash === '#kedjan' && bub, `börja om: efter omladdningen står sidan på startsidan med "Börja här!"-bubblan ${JSON.stringify(efter)} bubbla=${bub}`);
  await bo.close();
}
if (kor('bubblor')) { // Pratbubblor: visas på varje sida och steg tills någon stänger en bubbla; då är alla av
  const g = await ny('guidebubblor', { viewport: { width: 1280, height: 900 } });
  await kovTom(g);
  let nasta = 'kor-batch';
  await g.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = nasta; j.avtalA = j.avtalA || {}; r.fulfill({ json: j }); });
  await g.addInitScript(() => { try { if (!sessionStorage.getItem('svada-lage')) sessionStorage.setItem('svada-lage', 'guide'); } catch (e) {} });
  await g.goto(`${DASH}/?lang=sv#kedjan`); await stilla(g, 2500);
  const gor = () => g.evaluate(() => { const b = document.getElementById('gorbubbla'), dl = b && b.nextElementSibling; return b ? { text: b.textContent, synlig: b.checkVisibility(), motDl: dl && dl.tagName === 'DL', over: b.getBoundingClientRect().bottom <= dl.getBoundingClientRect().top + 1, steg: b.closest('.panel') && b.closest('.panel').id } : null; });
  await g.click('#nastaknapp'); await stilla(g, 1200);
  const gh = await gor();
  kolla(gh && gh.synlig && gh.motDl && gh.over && gh.steg === 'steg-1' && /Vad händer här/.test(gh.text), `bubblor: Nästa i guiden ger "Vad händer här?" rakt över texten "Det här händer" (${JSON.stringify(gh)})`);
  await g.click('#nastaknapp').catch(() => {}); await stilla(g, 600);
  kolla(!!(await gor()), 'bubblor: bubblan finns kvar när man följer Nästa igen (den visas tills någon stänger en bubbla)');
  await g.evaluate(() => document.getElementById('nod-2').click()); await stilla(g, 800);
  const g2 = await gor();
  kolla(g2 && g2.synlig && g2.steg === 'steg-2', `bubblor: bubblan visas också på nästa steg som öppnas (${JSON.stringify(g2)})`);
  nasta = 'hamta-katalog'; await g.waitForFunction(() => !!document.getElementById('nastabubbla'), null, { timeout: 12000 }).catch(() => {});
  const nh = await g.evaluate(() => { const b = document.getElementById('nastabubbla'), s = document.getElementById('snasta'); if (!b) return null; const rb = b.getBoundingClientRect(), rs = s.getBoundingClientRect();
    return { text: b.textContent, under: rb.top >= rs.bottom, inom: rb.left >= 0 && rb.right <= innerWidth }; });
  kolla(nh && nh.under && nh.inom && /Nästa steg/.test(nh.text), `bubblor: när ett steg är klart pekar en bubbla på Nästa-knappen i raden (${JSON.stringify(nh)})`);
  await g.evaluate(() => document.querySelector('#nastabubbla [data-nasta-stang]').click()); await g.waitForTimeout(300);
  kolla(await g.evaluate(() => !document.getElementById('nastabubbla') && !document.getElementById('gorbubbla') && sessionStorage.getItem('svada-borja') === '1'), 'bubblor: ✕ på en bubbla stänger alla bubblor');
  await g.evaluate(() => document.getElementById('nod-1').click()); await stilla(g, 800);
  nasta = 'forhandla-b'; await g.waitForTimeout(6500);
  kolla(await g.evaluate(() => !document.getElementById('gorbubbla') && !document.getElementById('nastabubbla')), 'bubblor: efter stängning kommer inga nya bubblor, varken på steg eller efter klara steg');
  await g.reload(); await stilla(g, 1500);
  kolla(await g.evaluate(() => !document.getElementById('gorbubbla') && !document.getElementById('nastabubbla') && document.getElementById('borjabubbla').hidden), 'bubblor: de förblir av efter omladdning (samma besök)');
  await g.close();
}
if (kor('guiderad')) { // Guideraden medan ett jobb kör: den står kvar på steget som körs (servern svarar utan "nästa" under körningen)
  const gr = await ny('guiderad-jobb', { viewport: { width: 1280, height: 900 } });
  await gr.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = null; j.jobbAktivt = { id: 9999, atgard: 'forhandla-a', status: 'kör' }; r.fulfill({ json: j }); });
  await gr.addInitScript(() => { try { sessionStorage.setItem('svada-lage', 'guide'); sessionStorage.setItem('svada-borja', '1'); } catch (e) {} });
  await gr.goto(`${DASH}/?lang=sv#kedjan`); await stilla(gr, 2500);
  const rad = await gr.evaluate(() => { const nu = document.getElementById('snu'), kl = [...document.querySelectorAll('#stegrad .sg.klar')].length, ak = document.querySelector('#stegrad .sg[aria-current="step"]');
    return { nu: nu && !nu.hidden ? nu.textContent : null, klara: kl, aktuell: ak && ak.textContent.trim() }; });
  kolla(rad.nu && /Förhandla A/.test(rad.nu) && rad.klara === 4 && /E/.test(rad.aktuell || ''), `guideraden medan Förhandla A kör: "Nu:" och aktuellt steg (E) syns och de fyra första är bockade (${JSON.stringify(rad)})`);
  await gr.close();
}
if (kor('stegtips')) { // Bubblorna i guiden: tips i steg 5 och 6 med Nästa tips, Nästa-bubblan efter ett klart jobb (följer knappen vid scroll), Godkänn-bubblan
  for (const nr of [5, 6]) {
    const t = await ny('stegtips-' + nr, { viewport: { width: 1280, height: 900 } });
    await t.goto(`${DASH}/?lang=sv#steg-${nr}`); await stilla(t, 2000);
    const info = () => t.evaluate(() => { const g = document.getElementById('gorbubbla'); return g && { text: g.textContent, knapp: !!g.querySelector('.tipsnasta'), synlig: g.checkVisibility() }; });
    const i1 = await info();
    // Tips 2 i steg 5 pekar på avtalets länk och finns bara när värdet är live (efter en B-leverans); steg 6 har alltid två.
    const tva = nr === 6 || await t.evaluate(() => !!document.querySelector('#provvarde a'));
    if (!tva) {
      kolla(i1 && i1.synlig && !i1.knapp && !/av 2/.test(i1.text), `steg ${nr}: utan länk i värdet finns bara ett tips, utan räknare (${JSON.stringify(i1)})`);
      await t.close(); continue;
    }
    kolla(i1 && i1.synlig && /1 av 2/.test(i1.text) && i1.knapp, `steg ${nr}: första tipset visas med "1 av 2" och Nästa tips (${JSON.stringify(i1)})`);
    await t.evaluate(() => document.querySelector('#gorbubbla .tipsnasta').click()); await t.waitForTimeout(500);
    const i2 = await info();
    kolla(i2 && /2 av 2/.test(i2.text) && !i2.knapp && i2.text !== i1.text, `steg ${nr}: Nästa tips visar tips 2 av 2, utan fler knappar (${JSON.stringify(i2)})`);
    await t.evaluate(() => document.querySelector('#gorbubbla [data-gor-stang]').click());
    kolla(!(await info()), `steg ${nr}: ✕ stänger tipsen`);
    await t.close();
  }
  { // Nästa-bubblan: kommer när effektiva nästa åtgärd ändras (X → tom medan jobbet kör → Y) och följer knappen när sidan rullas
    const n = await ny('nastabubbla-foljer', { viewport: { width: 1280, height: 800 } });
    let fas = 0;
    await kovTom(n);
    await n.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = fas === 0 ? 'forhandla-b' : fas === 1 ? 'transfer-b' : 'transfer-b'; j.jobbAktivt = fas === 1 ? { id: 9, atgard: 'forhandla-b', status: 'kör', etikett: 'x' } : null; r.fulfill({ json: j }); });
    await n.addInitScript(() => { try { sessionStorage.setItem('svada-lage', 'guide'); sessionStorage.removeItem('svada-borja'); } catch (e) {} });
    await n.goto(`${DASH}/?lang=sv#kedjan`); await stilla(n, 2500);
    fas = 1; await n.waitForTimeout(6500);
    kolla(await n.evaluate(() => !document.getElementById('nastabubbla')), 'Nästa-bubblan kommer inte medan jobbet kör, även om servern redan räknat fram nästa åtgärd (B-stegen)');
    fas = 2;   // statusen hämtas var 5:e s: mellanläget ska hinna ses
    await n.waitForFunction(() => document.getElementById('nastabubbla'), null, { timeout: 15000 }).catch(() => {});
    const lage = () => n.evaluate(() => { const b = document.getElementById('nastabubbla'), s = document.getElementById('snasta'); if (!b || !s) return null; const br = b.getBoundingClientRect(), sr = s.getBoundingClientRect(); const pil = parseFloat(b.style.getPropertyValue('--pil')); return { avst: Math.round(br.top - sr.bottom), pilMitt: Math.round(br.left + pil - (sr.left + sr.width / 2)) }; });
    const l1 = await lage();
    kolla(!!l1, 'Nästa-bubblan kommer efter att jobbet kört klart (nästa åtgärd X → tom → Y)');
    if (l1) {
      kolla(Math.abs(l1.avst - 12) <= 3 && Math.abs(l1.pilMitt) <= 3, `Nästa-bubblan sitter 12 px under knappen med pilen på knappens mitt (${JSON.stringify(l1)})`);
      await n.evaluate(() => window.scrollTo(0, 700)); await n.waitForTimeout(300);
      await n.evaluate(() => window.scrollTo(0, 0)); await n.waitForTimeout(300);
      const l2 = await lage();
      kolla(l2 && Math.abs(l2.avst - 12) <= 3 && Math.abs(l2.pilMitt) <= 3, `efter scroll upp och ned pekar bubblan fortfarande på knappen (${JSON.stringify(l2)})`);
    }
    await n.close();
  }
  { // Godkänn-bubblan: när en väntande KoV-förfrågan dyker upp i det öppna steget 3 pekar bubblan direkt på Godkänn-kortet
    const g = await ny('godkann-bubbla', { viewport: { width: 1280, height: 900 } });
    let vantar = false;
    await g.route('**/api/kov', async r => { const j = await hamtaEkta(r); if (!j) return; j.forhandlingar = vantar ? [{ id: 'urn:test:kov-1', kovBeslut: 'VANTANDE', distribution: 'A' }] : []; r.fulfill({ json: j }); });
    await g.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = 'forhandla-a'; j.jobbAktivt = null; r.fulfill({ json: j }); });
    await g.addInitScript(() => { try { sessionStorage.setItem('svada-lage', 'guide'); sessionStorage.removeItem('svada-borja'); } catch (e) {} });
    await g.goto(`${DASH}/?lang=sv#steg-3`); await stilla(g, 2500);
    await g.evaluate(() => { const b = document.getElementById('gorbubbla'); if (b) b.remove(); });
    vantar = true; await g.evaluate(() => uppdateraVantande()); await g.waitForTimeout(800);
    const gb = await g.evaluate(() => { const b = document.getElementById('gorbubbla'); return b && { text: b.textContent, motKov: !!(b.nextElementSibling && b.closest('.kovval')) || !!(b.parentElement && b.parentElement.classList.contains('kovval')) }; });
    kolla(gb && /KoV/.test(gb.text) && /godkänn/i.test(gb.text) && gb.motKov, `Godkänn-bubblan visas på Godkänn-kortet när en förfrågan väntar (${JSON.stringify(gb)})`);
    await g.close();
  }
}
if (kor('loggan')) { // Loggan leder till startsidan utan välkomstruta (adressen bär #kedjan, och en adress med # öppnar aldrig rutan)
  const dolj = () => { try { Object.defineProperty(navigator, 'webdriver', { get: () => false }); } catch (e) {} };   // som en riktig besökare: rutan får öppnas
  const kon = await ny('logga-kontroll', { viewport: { width: 1280, height: 900 } });
  await kon.addInitScript(dolj);
  await kon.goto(`${DASH}/?lang=sv`); await stilla(kon, 1500);
  kolla(await kon.evaluate(() => document.getElementById('valkomstdialog').open), 'loggan: utgångsläget stämmer, en ny besökare på startsidan utan # får välkomstrutan');
  await kon.close();
  const lg = await ny('logga', { viewport: { width: 1280, height: 900 } });
  await lg.addInitScript(dolj);
  await lg.goto(`${DASH}/?lang=sv#steg-3`); await stilla(lg, 1500);
  const f0 = await lg.evaluate(() => ({ dialog: document.getElementById('valkomstdialog').open, href: document.querySelector('a.loggalank')?.getAttribute('href'),
    namn: document.querySelector('a.loggalank')?.getAttribute('aria-label') }));
  kolla(!f0.dialog && f0.href === '/?lang=sv#kedjan' && /startsidan/.test(f0.namn || ''), `loggan: en länk till startsidan med #kedjan och ett namn (${JSON.stringify(f0)})`);
  await lg.click('a.loggalank'); await stilla(lg, 1200);
  const f1 = await lg.evaluate(() => ({ hash: location.hash, dialog: document.getElementById('valkomstdialog').open, paneler: [...document.querySelectorAll('.panel')].filter(x => !x.hidden).length }));
  kolla(f1.hash === '#kedjan' && !f1.dialog && f1.paneler === 0, `loggan: från ett steg till startsidan, ingen välkomstruta och ingen öppen panel (${JSON.stringify(f1)})`);
  await lg.evaluate(() => window.scrollTo(0, 600)); await lg.waitForTimeout(300);
  await lg.click('a.loggalank').catch(() => {}); await lg.waitForTimeout(900);
  kolla(await lg.evaluate(() => window.scrollY) < 5 && !(await lg.evaluate(() => document.getElementById('valkomstdialog').open)), 'loggan: redan på startsidan scrollar den till toppen, utan ruta');
  await lg.close();
  const le = await ny('logga-en', { viewport: { width: 390, height: 800 } });
  await le.goto(`${DASH}/?lang=en#steg-2`); await stilla(le, 1200);
  kolla(await le.evaluate(() => document.querySelector('a.loggalank')?.getAttribute('href')) === '/?lang=en#kedjan', 'loggan: engelska behåller språket i länken');
  await le.close();
}
if (kor('visamer')) { // Visa mer: varje del med egen rubrik öppnas för sig, "Öppna alla" öppnar alla i steget, en länk inåt öppnar delen
  // ?visamer=0 tvingar hopfällt (styrd webbläsare får annars alla öppna, som introduktionen).
  const vm = await ny('visamer', { viewport: { width: 1280, height: 900 } });
  await vm.goto(`${DASH}/?lang=sv&visamer=0#steg-3`); await stilla(vm, 1500);
  const lage = () => vm.evaluate(() => { const g = document.querySelector('#steg-3 section.visamer'); const d = g ? [...g.querySelectorAll('details[data-visamer]')] : [];
    const syns = x => !!x?.checkVisibility();      // offsetParent räcker inte: innehåll i en hopfälld <details> har fortfarande en förälder
    return { grupper: document.querySelectorAll('section.visamer').length, delar: d.length, oppna: d.filter(x => x.open).length,
      rubriker: d.map(x => x.querySelector(':scope > summary').textContent.trim()),
      teknik: syns(document.querySelector('#steg-3 .teknikruta')), mim: syns(document.querySelector('#steg-3 .mimruta')), ned: syns(document.querySelector('#steg-3 .nedladdning')),
      varfor: syns(document.querySelector('#steg-3 .pgrid details.lasmer .lasinnehall')), begrepp: syns(document.querySelector('#steg-3 .dsruta details.lasmer .lasinnehall')),
      prova: syns(document.querySelector('#steg-3 .prova')), ds: syns(document.querySelector('#steg-3 .dsruta')),
      knapp: g?.querySelector('[data-vm-alla]')?.textContent.trim() }; });
  let l = await lage();
  kolla(l.grupper === 6 && l.delar >= 5 && l.oppna === 0 && !l.teknik && !l.mim && !l.ned && !l.varfor && !l.begrepp && l.prova && l.ds,
        `Visa mer: alla delar hopfällda, det centrala syns (${l.delar} delar: ${l.rubriker.join(' | ')})`);
  kolla(new Set(l.rubriker).size === l.rubriker.length && l.rubriker.every(r => r.length > 2), 'Visa mer: varje del har en egen, unik rubrik');
  // En del för sig: bara den öppnas.
  await vm.click('#steg-3 section.visamer details.lasmer:nth-of-type(2) > summary'); await vm.waitForTimeout(400);
  l = await lage();
  kolla(l.oppna === 1, `Visa mer: ett klick på en rubrik öppnar bara den delen (${l.oppna} öppna)`);
  await vm.click('#steg-3 section.visamer details.lasmer:nth-of-type(2) > summary'); await vm.waitForTimeout(400);
  kolla((await lage()).oppna === 0, 'Visa mer: ett klick till stänger den igen');
  // Öppna alla / Stäng alla.
  await vm.click('#steg-3 [data-vm-alla]'); await vm.waitForTimeout(500);
  l = await lage();
  kolla(l.oppna === l.delar && l.teknik && l.mim && l.ned && l.knapp === 'Stäng alla', `Visa mer: Öppna alla öppnar alla delar i steget och knappen blir "${l.knapp}" (${l.oppna} av ${l.delar})`);
  const annat = await vm.evaluate(() => [...document.querySelectorAll('#steg-2 section.visamer details[data-visamer]')].filter(x => x.open).length);
  kolla(annat === 0, 'Visa mer: Öppna alla gäller bara det egna steget');
  await vm.click('#steg-3 [data-vm-alla]'); await vm.waitForTimeout(500);
  l = await lage();
  kolla(l.oppna === 0 && l.knapp === 'Öppna alla', `Visa mer: Stäng alla stänger alla delar igen (${l.oppna} öppna, knappen "${l.knapp}")`);
  // Varför och Begrepp och styrning är egna delar under det de hör till.
  await vm.click('#steg-3 .pgrid > div:first-child details.lasmer > summary'); await vm.waitForTimeout(400);
  l = await lage();
  kolla(l.varfor && !l.begrepp && l.oppna === 0, 'Läs mer: Varför öppnas för sig, utan att Begrepp och styrning eller Visa mer följer med');
  await vm.evaluate(() => { location.hash = 'svadaruta'; }); await vm.waitForTimeout(500);
  kolla((await lage()).oppna >= 1 && await vm.evaluate(() => !!document.getElementById('svadaruta').checkVisibility()), 'Visa mer: en länk till något inuti (#svadaruta) öppnar just den delen');
  const tangent = await vm.evaluate(() => { const sm = document.querySelector('#steg-3 section.visamer details.lasmer > summary'); sm.focus(); return document.activeElement === sm; });
  kolla(tangent, 'Visa mer: rubrikerna går att nå med tangentbordet (riktiga <summary>)');
  await vm.close();
  const vt = await ny('visamer-test', { viewport: { width: 390, height: 800 } });
  await vt.goto(`${DASH}/?lang=sv#steg-3`); await stilla(vt, 1500);
  const sh = await vt.evaluate(() => ({ delar: document.querySelectorAll('#steg-3 section.visamer details[data-visamer]').length,
    oppna: [...document.querySelectorAll('#steg-3 section.visamer details[data-visamer]')].filter(d => d.open).length,
    hojd: Math.round(Math.min(...[...document.querySelectorAll('#steg-3 section.visamer details.lasmer > summary')].map(s => s.getBoundingClientRect().height))) }));
  kolla(sh.oppna === sh.delar && sh.delar >= 5, `Visa mer: styrd webbläsare utan val får delarna öppna, så att proven ser hela sidan (${sh.oppna} av ${sh.delar})`);
  kolla(sh.hojd >= 44, `Visa mer: rubrikerna är minst 44 px höga på mobil (${sh.hojd} px)`);
  await vt.close();
}
if (kor('scenarier')) { // Fliken heter Scenarier och avtalsscenariot "betrodd organisation" är besökarens eget val: kryssrutan sparas via API:t och ritas om rätt
  const sc = await ny('scenarier', { viewport: { width: 1280, height: 900 } });
  await sc.goto(`${DASH}/?lang=sv#felinjektion`);
  await sc.waitForSelector('#betroddval', { timeout: 8000 });
  await sc.waitForFunction(() => /^(AV|PÅ|ON|OFF):/.test(document.querySelector('#betroddtext')?.textContent || ''), null, { timeout: 8000 }).catch(() => {});      // texten fylls först när /api/scenario svarat
  const flik = await sc.evaluate(() => [...document.querySelectorAll('nav button, .flikar button, button[data-flik]')].map(b => b.textContent.trim()));
  kolla(flik.some(t => t === 'Scenarier') && !flik.some(t => t === 'Felinjektion'), `fliken heter Scenarier (${flik.filter(t => /Scenar|Felinj/.test(t)).join(', ')})`);
  kolla(await sc.evaluate(() => !document.querySelector('#betroddval').checked && /^AV:/.test(document.querySelector('#betroddtext').textContent)), 'betrodd organisation: avslaget som standard, med förklaring');
  await sc.click('#betroddval');
  await sc.waitForFunction(() => /^PÅ:/.test(document.querySelector('#betroddtext').textContent), null, { timeout: 5000 }).catch(() => {});
  kolla(await sc.evaluate(() => document.querySelector('#betroddval').checked && /direkt, utan KoV-prövning/.test(document.querySelector('#betroddtext').textContent)), 'betrodd organisation: påslaget förklarar att avtalet skrivs direkt, utan KoV-prövning');
  kolla((await sc.evaluate(async () => (await fetch('/api/scenario')).json())).betrodd === true, 'betrodd organisation: valet ligger i besökarens egen session (API:t säger sant)');
  await sc.reload(); await sc.waitForSelector('#betroddval', { timeout: 8000 });
  await sc.waitForFunction(() => document.querySelector('#betroddval').checked, null, { timeout: 5000 }).catch(() => {});
  kolla(await sc.evaluate(() => document.querySelector('#betroddval').checked), 'betrodd organisation: valet ligger kvar efter omladdning');
  await sc.click('#betroddval');
  await sc.waitForFunction(() => /^AV:/.test(document.querySelector('#betroddtext').textContent), null, { timeout: 5000 }).catch(() => {});
  kolla((await sc.evaluate(async () => (await fetch('/api/scenario')).json())).betrodd === false, 'betrodd organisation: avslaget igen');
  await sc.evaluate(async () => fetch('/api/scenario', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{"betrodd":false}'}));      // uttrycklig städning, oavsett hur klicken föll
  kolla((await sc.evaluate(async () => (await fetch('/api/scenario')).json())).betrodd === false, 'betrodd organisation: städat efter provet (valet är av)');
  await sc.close();
}
if (kor('felinjektion')) { // Felinjektionens kryssruta när servern nekar (återhämtningsperioden): rutan ritas om urkryssad och orsaken står vid rutan och räknar ned.
  const t = await ny('felavslag', { viewport: { width: 1280, height: 900 } });
  await t.route('**/api/felinjektion', r => r.request().method() === 'POST'
    ? r.fulfill({status: 429, json: {fel: 'Felinjektionen har just slagits av. Vänta 57 s innan den slås på igen, så att demon hinner återhämta sig.', vantaSek: 57}})
    : r.fulfill({json: {aktiv: false, lagen: {schemadrift: false, saknade_parametrar: false, gis_i_b: false},
        beskrivning: {schemadrift: 'a', saknade_parametrar: 'b', gis_i_b: 'c'}}}));
  await t.goto(`${DASH}/?lang=sv#felinjektion`);
  await t.waitForSelector('#felreglage input[type=checkbox]', { timeout: 8000 });
  await t.click('#felreglage input[type=checkbox] >> nth=2');
  await t.waitForSelector('#felavslag', { timeout: 5000 }).catch(() => {});
  kolla(await t.evaluate(() => [...document.querySelectorAll('#felreglage input[type=checkbox]')].every(c => !c.checked)),
        'felinjektion: en nekad aktivering lämnar inte kryssrutan ikryssad (servern säger av)');
  const text1 = await t.evaluate(() => (document.querySelector('#felavslag') || {}).textContent || '');
  kolla(/Vänta \d+ s/.test(text1), `felinjektion: orsaken står vid kryssrutorna ('${text1.slice(0, 60)}')`);
  await t.waitForTimeout(3300);         // en tick per sekund och avrundning uppåt: 3,3 s ger minst två steg, en stillastående text inget
  const text2 = await t.evaluate(() => (document.querySelector('#felavslag') || {}).textContent || '');
  const n1 = +(text1.match(/Vänta (\d+) s/) || [])[1], n2 = +(text2.match(/Vänta (\d+) s/) || [])[1];
  kolla(n1 > 0 && n2 > 0 && n2 <= n1 - 2, `felinjektion: väntetiden räknar ned (${n1} → ${n2})`);
  await t.close();
}
if (kor('antal')) { // Antalet i steg 6: fältet visar det värde som faktiskt användes (0 och -5 blev tidigare kvar i fältet medan rubriken sa 1).
  const t = await ny('antal', { viewport: { width: 1280, height: 900 } });
  await t.goto(`${DASH}/?lang=sv#steg-6`); await t.waitForSelector('#analystopp', { timeout: 8000 });
  const varde = async v => { await t.fill('#analystopp', v); await t.dispatchEvent('#analystopp', 'change'); await stilla(t, 1200);
                              return t.inputValue('#analystopp'); };
  kolla(await varde('0') === '1' && await varde('-5') === '1' && await varde('999') === '91',
        'steg 6: antal 0 och -5 blir 1 och 999 blir 91 i fältet (rubriken och fältet säger samma sak)');
  await t.close();
}
if (kor('ingangar')) { // Publika ingångar: adressen som visas är den som länken öppnar (inklusive port), och räknarna i steg 3 heter vad de mäter.
  const t = await ny('ingangar', { viewport: { width: 1280, height: 900 } });
  await t.goto(`${DASH}/?lang=sv`); await t.waitForSelector('#ingangar a', { timeout: 8000 }).catch(() => {});
  const par = await t.evaluate(() => [...document.querySelectorAll('#ingangar a')].map(a => [a.getAttribute('href').replace(/\?lang=en$/, ''), a.textContent.trim()]));
  kolla(par.length > 0 && par.every(([h, tx]) => h === tx), `publika ingångar: länktexten är exakt adressen som länken öppnar (${par.length} rader)`);
  const etiketter = await t.evaluate(async () => (await (await fetch('/api/steg/3')).json()).detaljer.map(d => d.etikett));
  kolla(etiketter.some(e => /alla hittills/.test(e)) && !etiketter.some(e => /KoV-kön/.test(e)),
        `steg 3: räknaren heter vad den mäter (${etiketter.join(' | ')})`);
  await t.close();
}
if (kor('sistaminuten')) { // Sista minuten: bannern säger inte "om 1 min" när raden visar sekunder (0:28 → "mindre än en minut").
  const t = await ny('sista-minuten', { viewport: { width: 1280, height: 900 } });
  await t.goto(`${DASH}/?lang=sv&aterstall=0.5`); await t.waitForSelector('#aterstallremsatext', { state: 'attached', timeout: 8000 }).catch(() => {});
  await stilla(t, 1500);
  const rem = await t.evaluate(() => (document.querySelector('#aterstallremsatext') || {}).textContent || '');
  kolla(/mindre än en minut/.test(rem) && !/om 1 min/.test(rem), `nedräkning: bannern i sista minuten säger "mindre än en minut" ('${rem.slice(0, 50)}')`);
  await t.close();
}
// Provrunda 2026-10-26: (1) raden "Nästa" tar slut med en tydlig text (inte tomt) när steg 6 setts efter Leverera A, (2) Tab från länken i en
// ordförklaring fortsätter efter ordet (förr lämnade fokus sidan och nästa Tab började om i sidhuvudet).
if (kor('nastaslut')) {
  const q = await ny('nasta-slut', { viewport: { width: 1250, height: 900 } });
  await kovTom(q);
  await q.route('**/api/status*', async r => { const j = await hamtaEkta(r); if (!j) return; j.nasta = 'analysera'; r.fulfill({json: j}); });
  await q.goto(DASH + '/#kedjan'); await q.evaluate(() => { sessionStorage.removeItem('svada-analys-sedd'); sessionStorage.setItem('svada-ursprung-sedd', '1'); });
  await q.reload();
  await q.waitForFunction(() => { const n = document.querySelector('#nastaknapp'); return n && !n.hidden; }, null, { timeout: 15000 }).catch(() => {});
  const fore = await q.evaluate(() => ({ knapp: !document.querySelector('#nastaknapp').hidden, slut: !document.querySelector('#nastaslut').hidden }));
  kolla(fore.knapp && !fore.slut, 'Nästa: före steg 6 pekar raden på Analysera och sluttexten är dold');
  await q.evaluate(() => { location.hash = '#steg-6'; });
  await q.waitForFunction(() => !document.querySelector('#nastaslut').hidden, null, { timeout: 15000 }).catch(() => {});
  const efter = await q.evaluate(() => ({ knapp: !document.querySelector('#nastaknapp').hidden, text: document.querySelector('#nastaknapp').textContent, slut: document.querySelector('#nastaslut').textContent.trim(), dold: document.querySelector('#nastaslut').hidden }));
  kolla(!efter.knapp && efter.text === '' && !efter.dold && /^(Klart|Done):/.test(efter.slut), `Nästa: när steg 6 setts tar knappen slut (och töms) och raden säger "${efter.slut}"`);
  await q.reload();
  await q.waitForFunction(() => document.querySelector('#nastaslut') && !document.querySelector('#nastaslut').hidden, null, { timeout: 15000 }).catch(() => {});
  const omladdad = await q.evaluate(() => ({ knapp: document.querySelector('#nastaknapp').hidden, text: document.querySelector('#nastaknapp').textContent, slut: !document.querySelector('#nastaslut').hidden }));
  kolla(omladdad.knapp && omladdad.text === '' && omladdad.slut, 'Nästa: efter omladdning står sluttexten kvar och den dolda knappen är tom');
  // MIM-rutorna: begreppen i dem (MIM, kravkoder, JSON-LD, OpenAPI …) ska vara understrukna och förklaras i ordlistan, i alla steg som har en ruta
  {
    const mimOrd = await q.evaluate(() => {
      const ut = {};
      for (const nr of [1, 2, 3, 4, 5, 6]) {
        const ruta = document.querySelector(`#steg-${nr} .mimruta, .panel[data-steg="${nr}"] .mimruta`) || [...document.querySelectorAll('.mimruta')][nr - 1];
        ut[nr] = ruta ? [...ruta.querySelectorAll('.term')].map(t => t.dataset.term) : null;
      }
      return ut;
    });
    kolla(Object.values(mimOrd).some(v => v && v.includes('mim')), 'ordlistan: "MIM" är understruket i MIM-rutorna');
    kolla(!Object.values(mimOrd).some(v => v && v.includes('mimkrav')), 'MIM-rutorna i stegen har inga kravkoder (RC…, R…) i löptexten (de finns på /mim)');
  }
  // Tab-ordning: ord -> länken i rutan -> nästa fokuserbara EFTER ordet (efter ordet i dokumentet, inte i sidhuvudet och inte sidans slut); Skift+Tab tillbaka till ordet
  await q.goto(DASH + '/#kedjan'); await q.reload(); await stilla(q, 1500);   // omladdning: en första sida, så introduktionen är utfälld
  for (let f = 0; f < 40 && !(await q.evaluate(() => document.activeElement.classList.contains('term'))); f++) await q.keyboard.press('Tab');   // före det första ordet kommer stegraden (sex steg och "Till bilden") och introduktionens sammanfattning
  const ord = await q.evaluate(() => { const a = document.activeElement; window.__ord = a; return a.classList.contains('term'); });
  await q.keyboard.press('Tab');
  const lank = await q.evaluate(() => !!document.activeElement.closest('#tips'));
  await q.keyboard.press('Tab');
  const nasta = await q.evaluate(() => { const a = document.activeElement, o = window.__ord;
    return { body: a === document.body, tips: !!a.closest('#tips'), sidhuvud: !!a.closest('header'), efter: !!(o.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING), tag: a.tagName }; });
  kolla(ord && lank && !nasta.body && !nasta.tips && !nasta.sidhuvud && nasta.efter, `Tab: ord -> länk i rutan -> nästa fokuserbara EFTER ordet: ${JSON.stringify(nasta)}`);
  await q.goto(DASH + '/#kedjan'); await q.reload(); await stilla(q, 1500);   // omladdning: en första sida, så introduktionen är utfälld
  for (let f = 0; f < 40 && !(await q.evaluate(() => document.activeElement.classList.contains('term'))); f++) await q.keyboard.press('Tab');   // före det första ordet kommer stegraden (sex steg och "Till bilden") och introduktionens sammanfattning
  await q.keyboard.press('Tab'); await q.keyboard.press('Shift+Tab');
  kolla(await q.evaluate(() => document.activeElement.classList.contains('term')), 'Skift+Tab från länken i rutan går tillbaka till ordet');
  await q.goto(DASH + '/#kedjan'); await q.reload(); await stilla(q, 1500);   // omladdning: en första sida, så introduktionen är utfälld
  for (let f = 0; f < 40 && !(await q.evaluate(() => document.activeElement.classList.contains('term'))); f++) await q.keyboard.press('Tab');
  await q.keyboard.press('Tab'); await q.keyboard.press('Escape'); await q.waitForTimeout(300);
  kolla(await q.evaluate(() => document.activeElement.classList.contains('term') && document.getElementById('tips').hidden), 'Esc i rutans länk stänger rutan och flyttar fokus tillbaka till ordet');
  await q.close();
}
// Nätavbrott (provrunda 2026-10-28): pollningarna ska hoppa över rundan tyst, inget ohanterat avslag och inget js_fel till statistiken.
if (kor('natavbrott')) {
  const n = await ny('natavbrott', { viewport: { width: 1250, height: 900 } });
  const handelser = [];
  await n.route('**/api/handelse', async r => { handelser.push(r.request().postData() || ''); await r.continue().catch(() => {}); });
  await n.addInitScript(() => { window.__rej = 0; window.addEventListener('unhandledrejection', () => { window.__rej++; }); });
  await n.goto(DASH + '/#kedjan'); await stilla(n, 3000);
  await n.context().setOffline(true); await n.waitForTimeout(9000); await n.context().setOffline(false);
  const pollningar = []; n.on('request', r => { if (/\/api\/status/.test(r.url())) pollningar.push(r.url()); });
  await n.waitForRequest(r => /\/api\/status/.test(r.url()), { timeout: 15000 }).catch(() => {}); await n.waitForTimeout(1500);
  const rej = await n.evaluate(() => window.__rej);
  kolla(rej === 0, `nätavbrott i 9 s: inga ohanterade avslag från pollningen (${rej})`);
  kolla(!handelser.some(t => /js_fel/.test(t)), 'nätavbrott: inget js_fel skickas till statistiken');
  kolla(pollningar.length >= 1 && await n.evaluate(() => !!document.querySelector('#sammanfattning').textContent), `efter nätavbrottet fungerar sidan och sidans egen pollning går vidare (${pollningar.length} anrop till /api/status)`);
  await n.close();
}
// Ordlistan på sidor utan egen motor (ordlista.py): brunnsvyn, brunnssidan, /modell, termsidan, /mim och /nyheter ska ha understrukna
// begrepp, en tipsruta vid fokus som Esc stänger (och bara den), inga radbrott runt orden i MIM-rutan och ingen rullning i sidled.
if (kor('publikbegrepp')) {
  const PUBLIKVY = process.env.PUBLIKVY || 'http://localhost:38085';
  const sidor = [[DASH, '/mim'], [DASH, '/nyheter'], [PUBLIKVY, '/'], [PUBLIKVY, '/brunnar/SSO1_01-4526'], [PUBLIKVY, '/modell'],
                 [PUBLIKVY, '/modell/utkast/0.1/source'], [PUBLIKVY, '/mim']];
  for (const sprak of ['sv', 'en']) for (const [bas, vag] of sidor) {
    const o = await ny('ordlista ' + vag, { viewport: { width: 1250, height: 900 } });
    await o.goto(`${bas}${vag}?lang=${sprak}&test=1`, { waitUntil: 'load' });
    const antal = await o.locator('.term').count();
    let tips = false, stangd = false;
    if (antal) {
      await o.locator('.term').first().focus();
      tips = await o.locator('#tips').isVisible();
      await o.keyboard.press('Escape');
      stangd = !(await o.locator('#tips').isVisible());
    }
    const brott = await o.locator('.mimruta .term').evaluateAll(l => l.filter(e => getComputedStyle(e).display === 'block').length);
    const rull = await o.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    kolla(antal > 0 && tips && stangd, `ordlistan (${sprak}) ${vag}: ${antal} understrukna begrepp, tipsruta vid fokus, Esc stänger rutan`);
    kolla(brott === 0 && !rull, `ordlistan (${sprak}) ${vag}: inga radbrott runt orden i MIM-rutan och ingen rullning i sidled`);
    await o.close();
  }
  const ol = await ny('ordlistesidan', { viewport: { width: 400, height: 900 } });
  await ol.goto(`${PUBLIKVY}/ordlista?lang=sv`, { waitUntil: 'load' });
  kolla(await ol.locator('dt').count() >= 50 && !(await ol.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), 'brunnsvyns egen ordlistesida: alla begrepp, ingen rullning i sidled vid 400 px');
  await ol.close();
}
// /modell vid 390 px: termnamnen i tabellerna får inte brytas mitt i ordet (tabellen ska rulla i sidled i stället), och sidan själv rullar inte.
if (kor('modell')) {
  const PUBLIKVY = process.env.PUBLIKVY || 'http://localhost:38085';
  for (const sprak of ['sv', 'en']) {
    const sm = await ny('modell 390 px', { viewport: { width: 390, height: 800 } });
    await sm.goto(`${PUBLIKVY}/modell?lang=${sprak}&test=1`, { waitUntil: 'load' });
    const m = await sm.evaluate(() => {
      const koder = [...document.querySelectorAll('table td:first-child code')];
      return { antal: koder.length, brutna: koder.filter(c => c.getClientRects().length > 1).map(c => c.textContent).slice(0, 5),
               sidrull: document.documentElement.scrollWidth > innerWidth + 1 };
    });
    kolla(m.antal >= 40 && m.brutna.length === 0, `/modell (${sprak}) vid 390 px: ${m.antal} termnamn, inget bryts mitt i ordet${m.brutna.length ? ' (brutna: ' + m.brutna.join(', ') + ')' : ''}`);
    kolla(!m.sidrull, `/modell (${sprak}) vid 390 px: sidan rullar inte i sidled (tabellen rullar för sig)`);
    await sm.close();
  }
}
// Nedladdning (nedladdning.py): varje steg har sin ruta, ett klick ger en fil med kontrollsumma, och A utan avtal ger en förklaring i stället för en fil.
if (kor('nedladdning')) {
  const dl = await b.newContext({ locale: 'sv-SE', viewport: { width: 1250, height: 1000 }, acceptDownloads: true });
  const nd = await dl.newPage();
  nd.on('pageerror', e => jsfel.push(`nedladdning: ${e.message}`));
  await nd.goto(DASH + '/?lang=sv&test=1'); await stilla(nd, 2500);
  const antal = {};
  for (const n of [1, 2, 3, 4, 5, 6]) antal[n] = await nd.locator(`#steg-${n} button.ladda`).count();
  kolla(Object.values(antal).every(v => v > 0), `nedladdning: varje steg 1-6 har en ruta med knappar (${JSON.stringify(antal)})`);
  await nd.locator('#nod-1').click(); await nd.waitForTimeout(400);
  const [fil] = await Promise.all([nd.waitForEvent('download', { timeout: 30000 }).catch(() => null), nd.locator('#steg-1 button.ladda[data-fil="matvarden"]').click()]);
  await nd.waitForTimeout(600);
  const svar = await nd.locator('#steg-1 li[data-fil="matvarden"] .lsvar').innerText();
  kolla(!!fil && /^svada-matvarden-.*\.json$/.test(fil.suggestedFilename()) && /SHA-256: [0-9a-f]{64}/.test(svar), `nedladdning: ett klick ger filen ${fil ? fil.suggestedFilename() : '(ingen)'} och visar kontrollsumman`);
  await nd.locator('#nod-6').click(); await nd.waitForTimeout(400);
  // Utan sessionskaka (direktanrop mot dashboardens port) gäller alla avtal; med sessioner av ett eget avtal. Antingen får A-filen sin
  // märkning i namnet, eller så förklaras varför den inte lämnas ut. Aldrig ett tyst fel.
  const [afil] = await Promise.all([nd.waitForEvent('download', { timeout: 15000 }).catch(() => null), nd.locator('#steg-6 button.ladda[data-fil="analys-a-geojson"]').click()]);
  await stilla(nd, 1200);
  const atext = await nd.locator('#steg-6 li[data-fil="analys-a-geojson"] .lsvar').innerText();
  kolla(afil ? /DISTRIBUTION-A-ej-for-spridning/.test(afil.suggestedFilename()) : /gällande avtal|current agreement|ingen leverans|No delivery/i.test(atext), `nedladdning: A märks i filnamnet eller förklaras (${afil ? afil.suggestedFilename() : atext.slice(0, 80)})`);
  await dl.close();
}
// ONLY: okända blocknamn underkänns (annars blir ett felstavat namn ett grönt prov där nästan inget kört), och körda block skrivs ut.
if (ONLY.length) { for (const n of ONLY) kolla(sedda.has(n), `delkörning: blocket '${n}' finns`); console.log(`  Delkörning: ${ONLY.join(', ')} (övriga block hoppades över)`); }
// Slutkontroll: sidfel i SENARE block (400 px, fynd, jobbruta, karta, uteslutning) ska också underkänna testet.
kolla(jsfel.length === 0, `inga JS-fel i någon provsida (slutkontroll)${jsfel.length ? ': ' + jsfel.join('; ') : ''}`);
await b.close();
process.exit(Math.min(fel, 99));
