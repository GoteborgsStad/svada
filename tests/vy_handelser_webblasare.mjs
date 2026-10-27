// vy_handelser_webblasare.mjs – A2-03 (del a2): id:n från servern får aldrig köras som JavaScript.
//
// Helt isolerad fixtur: sidan renderas utan stack (tests/rendera_sida.py) och serveras från en påhittad adress, alla
// /api/*-svar mockas och inget nätverk används. Avtals- och förhandlings-id:n med apostrof, citattecken, backslash och
// radslut ska behandlas som data: ett klick på Godkänn eller KoV häver får inte köra kod, och id:t ska hamna URL-kodat i
// anropet. Skriver [OK]/[FEL]; exitkoden är antalet fel.
//   node tests/vy_handelser_webblasare.mjs
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
const require = createRequire(new URL('../tools/', import.meta.url));
const { chromium } = require('playwright-core');
const CHROME = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium']
  .find(p => { try { require('node:fs').accessSync(p); return true; } catch { return false; } });
let fel = 0;
const kolla = (ok, text) => { console.log(`  [${ok ? 'OK' : 'FEL'}] ${text}`); if (!ok) fel++; };

const HTML = execFileSync('python3', [new URL('rendera_sida.py', import.meta.url).pathname, 'sv']).toString();
// Samordnarens ruta MED knappar (i den externa varianten visas bara ett inspelat exempel; utestängningen är avstängd där).
const HTML_UTE = execFileSync('python3', [new URL('rendera_sida.py', import.meta.url).pathname, 'sv', 'utestangning']).toString();
const HTML_UTE_EN = execFileSync('python3', [new URL('rendera_sida.py', import.meta.url).pathname, 'en', 'utestangning']).toString();
const ELAKA = ["x');window.__a2=1;//", 'x");window.__a2=2;//', "x\\');window.__a2=3;//", "x'\n;window.__a2=4;//"];
const b = await chromium.launch({ executablePath: CHROME, headless: true });
for (const id of ELAKA) {
  const p = await b.newPage();
  const anrop = [];
  await p.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();                     // inget nätverk utanför fixturen
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML });
    if (r.request().method() === 'POST') { if (u.pathname !== '/api/handelse') anrop.push(u.pathname); return r.fulfill({ json: { id: 1 } }); }   // statistikhändelser (204) är inga åtgärder
    if (u.pathname === '/api/kov') return r.fulfill({ json: { count: 1, vantande: [{ id, assetId: 'a', state: 'REQUESTED', kovBeslut: 'VANTANDE' }],
      forhandlingar: [{ id, assetId: 'a', state: 'REQUESTED', kovBeslut: 'VANTANDE' }] } });
    if (u.pathname === '/api/avtal') return r.fulfill({ json: { avtal: [{ id: 'aaaaaaaa-1', dhiAvtalId: id, distribution: 'A', status: 'GALLANDE', regler: {} }] } });
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=sv#suveranitet');
  // Knapparna väljs på klass (finns i alla versioner), inte på dataattribut: provet ska klicka även i en sårbar version.
  const syns = await p.waitForSelector('#kovlista button.godkann', { timeout: 15000 }).then(() => true).catch(() => false);
  kolla(syns, `fixtur: Godkänn-knappen ritas för id ${JSON.stringify(id)}`);
  if (syns) {
    await p.click('#kovlista button.godkann'); await p.waitForTimeout(400);
    await p.goto('about:blank'); await p.goto('http://fixtur.test/?lang=sv#suveranitet');   // godkännandet flyttar till fliken Jobb
    await p.waitForSelector('#avtallista button.fara', { timeout: 10000 }).catch(() => {});
    await p.click('#avtallista button.fara').catch(() => {}); await p.waitForTimeout(200);
    await p.click('#avtallista button.fara').catch(() => {}); await p.waitForTimeout(400);   // M2: hävning kräver ett andra klick
  }
  const satt = await p.evaluate(() => window.__a2);
  kolla(satt === undefined, `id ${JSON.stringify(id)} kördes inte som kod vid klick (window.__a2=${satt})`);
  const enc = encodeURIComponent(id);
  kolla(anrop.includes(`/api/kov/${enc}/godkann`), `Godkänn skickade id:t URL-kodat (${anrop[0] || 'inget anrop'})`);
  kolla(anrop.includes(`/api/kov/avtal/${enc}/hav`), `KoV häver skickade id:t URL-kodat (${anrop[1] || 'inget anrop'})`);
  await p.close();
}
// --- M8 (gränssnittstestet 2026-10-18): en dold flik ska också få veta att utestängningen gått ut -------------------
{
  const p = await b.newPage();
  const t0 = Date.now();
  await p.addInitScript(() => { Object.defineProperty(document, 'hidden', { get: () => true });
                                Object.defineProperty(document, 'visibilityState', { get: () => 'hidden' }); });
  await p.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML_UTE });
    if (u.pathname === '/api/svada/status') return r.fulfill({ json: { poster: [
      { mottagare: 'dhi', typ: 'SvadaMembershipCredential', index: 1, aterkallat: Date.now() - t0 < 2500 },
      { mottagare: 'stad', typ: 'SvadaMembershipCredential', index: 3, aterkallat: false }] } });
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=sv#steg-3');
  const forst = await p.waitForFunction(() => /UTESTÄNGD/.test(document.querySelector('#svadatabell')?.textContent || ''), null, { timeout: 8000 }).then(() => true).catch(() => false);
  kolla(forst, 'M8: DHI visas först som utestängd (dold flik)');
  const sen = await p.waitForFunction(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell')?.textContent || 'UTESTÄNGD'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  kolla(sen, `M8: även i en dold flik byter raden till medlem när servern säger det (inom ${Math.round((Date.now() - t0) / 1000)} s)`);
  await p.close();
}
// --- M2: hävning och avslag kräver ett andra klick; godkänn gör det inte -----------------------------------------------
{
  const p = await b.newPage();
  const anrop = [];
  await p.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML });
    if (r.request().method() === 'POST') { if (u.pathname !== '/api/handelse') anrop.push(u.pathname); return r.fulfill({ json: { id: 1 } }); }   // statistikhändelser är inga åtgärder
    if (u.pathname === '/api/kov') return r.fulfill({ json: { count: 1, vantande: [{ id: 'f-1', assetId: 'a', state: 'REQUESTED', kovBeslut: 'VANTANDE' }],
      forhandlingar: [{ id: 'f-1', assetId: 'a', state: 'REQUESTED', kovBeslut: 'VANTANDE' }] } });
    if (u.pathname === '/api/avtal') return r.fulfill({ json: { avtal: [{ id: 'aaaaaaaa-1', dhiAvtalId: 'd-1', distribution: 'A', status: 'GALLANDE', regler: {} }] } });
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=sv#suveranitet');
  await p.waitForSelector('#avtallista button.fara', { timeout: 15000 }).catch(() => {});
  await p.click('#avtallista button.fara').catch(() => {}); await p.waitForTimeout(300);
  // F15: knappen får en kort text och förklaringen står under den (bekrafta-info), så att den inte täcker texten bredvid.
  const efterEtt = { anrop: anrop.length, text: (await p.textContent('#avtallista button.fara').catch(() => '')) || '', info: (await p.textContent('#avtallista .bekrafta-info').catch(() => '')) || '' };
  kolla(efterEtt.anrop === 0 && /Klicka igen/.test(efterEtt.text) && !/nytt avtal/.test(efterEtt.text) && /nytt avtal kan tecknas/.test(efterEtt.info),
        `M2: ett klick på KoV häver skickar inget och förklarar att ett nytt avtal kan tecknas ('${efterEtt.text.slice(0, 60)}')`);
  await p.click('#avtallista button.fara', { timeout: 3000 }).catch(() => {}); await p.waitForTimeout(300);
  kolla(anrop.includes('/api/kov/avtal/d-1/hav'), 'M2: det andra klicket inom 15 s häver');
  await p.goto('about:blank'); anrop.length = 0; await p.goto('http://fixtur.test/?lang=sv#suveranitet');
  await p.waitForSelector('#kovlista button.fara', { timeout: 15000 }).catch(() => {});
  await p.click('#kovlista button.fara', { timeout: 3000 }).catch(() => {}); await p.waitForTimeout(300);
  kolla(anrop.length === 0, 'M2: ett klick på Avslå skickar inget');
  await p.goto('about:blank'); anrop.length = 0; await p.goto('http://fixtur.test/?lang=sv#suveranitet');
  await p.waitForSelector('#kovlista button.godkann', { timeout: 15000 }).catch(() => {});
  await p.click('#kovlista button.godkann', { timeout: 3000 }).catch(() => {}); await p.waitForTimeout(300);
  kolla(anrop.includes('/api/kov/f-1/godkann'), 'M2: Godkänn kräver bara ett klick');
  await p.close();
}
// --- M3: hopp till Jobb visar det NYA jobbets logg direkt, och Bakåt går tillbaka till fliken man kom från --------------
{
  const p = await b.newPage();
  let startat = false;
  await p.route('**/*', async r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML });
    if (r.request().method() === 'POST' && u.pathname === '/api/atgard/kor-batch') { startat = true; return r.fulfill({ json: { id: 2, status: 'kör', rader: [] } }); }
    if (u.pathname === '/api/kov') { await new Promise(f => setTimeout(f, 4000)); return r.fulfill({ json: { count: 0, vantande: [], forhandlingar: [] } }); }
    if (u.pathname === '/api/jobb') return r.fulfill({ json: { aktivt: null, jobb: [
      { id: 1, atgard: 'kor-batch', etikett: 'Kör en FCF-batch', status: 'klar', startad: 't1', rader: [{ tid: 't1', text: 'GAMMALT JOBB' }] },
      ...(startat ? [{ id: 2, atgard: 'kor-batch', etikett: 'Kör en FCF-batch', status: 'klar', startad: 't2', rader: [{ tid: 't2', text: 'NYTT JOBB' }] }] : [])] } });
    if (u.pathname.startsWith('/api/jobb/')) return r.fulfill({ json: { id: 2, status: 'klar', rader: [{ tid: 't2', text: 'NYTT JOBB' }] } });
    if (u.pathname === '/api/felinjektion') return r.fulfill({ json: { aktiv: false, lagen: { schemadrift: false, saknade_parametrar: false, gis_i_b: false },
      beskrivning: { schemadrift: 'a', saknade_parametrar: 'b', gis_i_b: 'c' } } });
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=sv#jobb-1'); await p.waitForTimeout(500);          // ett tidigare jobb visas
  await p.evaluate(() => visa('felinjektion')); await p.waitForTimeout(400);
  await p.click('#felinjektion button[onclick="kor(\'kor-batch\')"]', { timeout: 5000 }).catch(() => {});
  await p.waitForTimeout(900);
  const logg = await p.textContent('#jobblogg');
  kolla(/NYTT JOBB/.test(logg) && !/GAMMALT JOBB/.test(logg), `M3: efter hoppet visar Jobb det nya jobbets logg inom 1 s fast kön svarar efter 4 s ('${logg.trim().slice(0, 40)}')`);
  await p.goBack(); await p.waitForTimeout(400);
  const tillbaka = await p.evaluate(() => ({ hash: location.hash, aktiv: document.querySelector('section.flik.aktiv')?.id }));
  kolla(tillbaka.aktiv === 'felinjektion' && tillbaka.hash === '#felinjektion', `M3: webbläsarens Bakåt går tillbaka till Felinjektion (${JSON.stringify(tillbaka)})`);
  await p.close();
}
// --- L6: den publika vyn rullar inte i sidled vid 560 px (tabellen rullar för sig själv) ------------------------------------
{
  const PV = execFileSync('python3', ['-c', `
import sys; sys.path.insert(0, ${JSON.stringify(new URL('../services/publik-vy', import.meta.url).pathname)})
import vy
rader = [{"id": "urn:ngsi-ld:SewerOverflowModelB:SSO1_01-%04d" % i, "overflowVolumeM3": 1234.567, "overflowDurationMin": 155, "observedAt": "2026-07-28T00:00:00Z"} for i in range(30)]
serie = [{"observedAt": "2026-07-28T00:00:00Z", "overflowVolumeM3": 591.53, "overflowDurationMin": 155, "overflowPeakM3S": 0.12, "inflowMeanM3S": 0.25, "inflowPeakM3S": 0.4, "inflowVolumeM3": 900.1, "waterLevelMaxM": 1.2}] * 5
print(vy.landning(rader, "http://tidsserie.fixtur.test/temporal/entities?type=SewerOverflowModelB&timerel=after&timeAt=2020-01-01T00:00:00Z", "http://k", "2020-01-01", "http://fixtur.test/", "sv"))
print("\\x00")
print(vy.brunn("urn:ngsi-ld:SewerOverflowModelB:SSO1_01-4526", serie, "http://tidsserie.fixtur.test/x", "http://k", "sv"))`]).toString().split('\x00');
  for (const [namn, html] of [['listan', PV[0]], ['en brunn', PV[1]]]) {
    const p = await b.newPage({ viewport: { width: 560, height: 900 } });
    await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'fixtur.test') return r.abort();
      if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: html }); return r.fulfill({ json: {} }); });
    await p.goto('http://fixtur.test/'); await p.waitForTimeout(500);
    const bred = await p.evaluate(() => ({ sida: document.documentElement.scrollWidth, vy: document.documentElement.clientWidth }));
    kolla(bred.sida <= bred.vy + 1, `L6: publika vyn (${namn}) rullar inte i sidled vid 560 px (${bred.sida} mot ${bred.vy})`);
    await p.close();
  }
}
// Samordnarens ruta när utestängning får användas (renderad som den interna varianten): knappar, ingen onödig omritning, fel, omläsning,
// namn för skärmläsare och nedräkning. (Flyttat hit från det levande webbläsartestet: den externa varianten har inga knappar.)
{
  const p = await b.newPage();
  let stadUte = false, nasta502 = false, jobbPagar = false;
  const anrop = [];
  await p.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML_UTE });
    if (u.pathname === '/api/svada/status') return r.fulfill({ json: { poster: [
      { mottagare: 'dhi', typ: 'SvadaMembershipCredential', index: 1, aterkallat: false },
      { mottagare: 'stad', typ: 'SvadaMembershipCredential', index: 3, aterkallat: stadUte }] } });
    if (u.pathname === '/api/skydd') return r.fulfill({ json: { utestangningS: stadUte ? { stad: 161 } : {}, felinjektionS: null, pausS: 0,
      regler: { utestangningS: 180, felinjektionS: 300, pausS: 8 } } });
    if (u.pathname === '/api/status') return r.fulfill({ json: { tid: '2026-10-20T10:00:00Z', komponenter: [], steg: [], sammanfattning: { uppe: 0, totalt: 0, nere: 0 },
      jobbAktivt: jobbPagar ? { id: 5, etikett: 'Kör en batch', status: 'kör' } : null, avtalA: { gallande: false } } });
    if (r.request().method() === 'POST' && /^\/api\/svada\//.test(u.pathname)) {
      anrop.push(u.pathname);
      if (nasta502) return r.fulfill({ status: 502, json: { fel: 'simulerat fel' } });
      stadUte = /aterkalla$/.test(u.pathname);
      return r.fulfill({ json: { ok: true } });
    }
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=sv#steg-3');
  await p.waitForSelector('#svadatabell button[data-svada]', { timeout: 15000 }).catch(() => {});
  kolla(await p.evaluate(() => document.querySelectorAll('#svadatabell button[data-svada]').length) === 2, 'samordnaren: en knapp per deltagare (DHI och staden)');
  kolla(await p.evaluate(() => /Svada \(samordnaren\)/.test(document.querySelector('#svadaruta .rollchip').textContent)), 'samordnaren: rutan visar VEM som agerar');
  kolla(await p.evaluate(() => [...document.querySelectorAll('#svadatabell button[data-svada]')].every(x => /: (DHI|Staden)/.test(x.getAttribute('aria-label') || ''))), 'samordnarens knappar har namn med deltagaren (aria-label)');
  // ett pågående jobb låser inte samordnarens knappar (man ska kunna släppa in en part medan ett jobb hänger), men låser åtgärdsknapparna
  jobbPagar = true;
  await p.waitForFunction(() => [...document.querySelectorAll('button.kor[data-atgard]:not([data-svada])')].some(x => x.disabled), null, { timeout: 8000 }).catch(() => {});
  kolla(await p.evaluate(() => document.querySelectorAll('button.kor[data-atgard]:not([data-svada]):disabled').length > 0 && document.querySelectorAll('#svadatabell button[data-svada]:disabled').length === 0),
        'ett pågående jobb låser åtgärdsknapparna men inte samordnarens knappar');
  jobbPagar = false;
  await p.evaluate(() => { document.querySelector('#svadatabell button[data-svada]').dataset.markerad = '1'; });
  await p.waitForTimeout(3600);
  kolla(await p.evaluate(() => document.querySelector('#svadatabell button[data-svada]').dataset.markerad === '1'), 'samordnarens knappar byts inte ut vid varje avfrågning (inga tappade klick)');
  nasta502 = true;
  await p.click('#svadatabell button[data-svada="stad"]'); await p.waitForTimeout(2200);
  kolla(await p.evaluate(() => document.querySelectorAll('#svadatabell button[data-svada]:disabled').length) === 0, 'efter ett misslyckat anrop (502) är knapparna aktiva igen');
  kolla(await p.evaluate(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent)), 'ett misslyckat anrop ändrar inte medlemskapet');
  nasta502 = false;
  await p.click('#svadatabell button[data-svada="stad"]');
  await p.waitForFunction(() => /UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent), null, { timeout: 15000 }).catch(() => {});
  kolla(await p.evaluate(() => /UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent)), 'klicket på Stäng ute återkallar stadens intyg (UTESTÄNGD i tabellen)');
  kolla(anrop.filter(x => /stad\/aterkalla$/.test(x)).length === 2, `båda försöken (502 och lyckat) nådde servern (${anrop.join(', ')})`);
  await p.waitForFunction(() => /[0-2]:\d\d/.test(document.querySelector('[data-utestang="stad"]')?.textContent || ''), null, { timeout: 10000 }).catch(() => {});
  const ned = await p.evaluate(() => document.querySelector('[data-utestang="stad"]')?.textContent || '');
  kolla(/[0-2]:\d\d/.test(ned) && /automatiskt/.test(ned), `uteslutningen visar nedräkning till automatisk återinsättning ("${ned}")`);
  await p.click('#svadatabell button[data-svada="stad"]');
  await p.waitForFunction(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent), null, { timeout: 15000 }).catch(() => {});
  kolla(await p.evaluate(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent)) && anrop.some(x => /stad\/aterinsatt$/.test(x)), 'klicket på Släpp in igen återinsätter intyget (anropet nådde servern)');
  // omläsning av sig själv medan steg 3 är öppet (en utestängning som löpt ut stod kvar som UTESTÄNGD i flera minuter, 2026-10-17)
  stadUte = true;
  await p.waitForFunction(() => /UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent), null, { timeout: 9000 }).catch(() => {});
  kolla(await p.evaluate(() => /UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent)), 'omläsning: när servern säger utesluten visar tabellen det av sig själv');
  stadUte = false;
  await p.waitForFunction(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent), null, { timeout: 9000 }).catch(() => {});
  kolla(await p.evaluate(() => !/UTESTÄNGD/.test(document.querySelector('#svadatabell').textContent)), 'omläsning: när servern säger medlem byter tabellen av sig själv, utan klick eller omladdning');
  await p.close();
}
// Samma ruta på engelska och vid 400 px: nedräkningen på engelska, inga knappar som sticker ut, ingen sidledsrullning.
{
  const p = await b.newPage({ viewport: { width: 400, height: 900 } });
  await p.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'fixtur.test') return r.abort();
    if (u.pathname === '/') return r.fulfill({ contentType: 'text/html; charset=utf-8', body: HTML_UTE_EN });
    if (u.pathname === '/api/svada/status') return r.fulfill({ json: { poster: [
      { mottagare: 'dhi', typ: 'SvadaMembershipCredential', index: 1, aterkallat: false },
      { mottagare: 'stad', typ: 'SvadaMembershipCredential', index: 3, aterkallat: true }] } });
    if (u.pathname === '/api/skydd') return r.fulfill({ json: { utestangningS: { stad: 161 }, felinjektionS: null, pausS: 0,
      regler: { utestangningS: 180, felinjektionS: 300, pausS: 8 } } });
    return r.fulfill({ json: {} });
  });
  await p.goto('http://fixtur.test/?lang=en#steg-3');
  await p.waitForFunction(() => /\d:\d\d/.test(document.querySelector('[data-utestang="stad"]')?.textContent || ''), null, { timeout: 10000 }).catch(() => {});
  const ned = await p.evaluate(() => document.querySelector('[data-utestang="stad"]')?.textContent || '');
  kolla(/Let back in automatically in \d:\d\d/.test(ned), `engelska: nedräkningen till automatisk återinsättning ("${ned}")`);
  kolla(await p.evaluate(() => /EXCLUDED/.test(document.querySelector('#svadatabell').textContent)), 'engelska: statusen visas på engelska (EXCLUDED)');
  kolla(await p.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), '400 px: samordnarrutan ger ingen sidledsrullning');
  await p.close();
}
await b.close();
process.exit(Math.min(fel, 99));
