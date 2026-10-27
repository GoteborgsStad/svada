// html2png.mjs – renderar HTML-konceptdokument till PNG i WSL.
//
// Varför så här: Docker Desktop används inte och Playwrights egen Linux-Chromium
// saknar systembibliotek (kräver sudo). Däremot finns Windows-Chrome installerat,
// och den kan köras headless direkt från WSL via /mnt/c utan några Linux-beroenden.
// Nuvarande Chrome tog bort "gamla" headless, så --headless=new fångar bara
// fönsterhöjden (inte hela sidan). Därför renderar vi generöst högt och beskär
// sedan bottenmarginalen automatiskt med pngjs (ren JS, inga native-beroenden).
//
// Användning (från repo-roten eller tools/):
//   node tools/html2png.mjs                      # alla *.html i docs/koncept/
//   node tools/html2png.mjs docs/koncept/x.html  # en eller flera specifika filer
//   WIDTH=1280 SCALE=2 PAD=40 node tools/html2png.mjs   # justera via miljövariabler
//
// PNG:en skrivs bredvid HTML-filen med samma basnamn (x.html -> x.png).

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, unlinkSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join, basename, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PNG } from 'pngjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');

// ---- Inställningar (kan överstyras via miljövariabler) --------------------
const WIDTH = Number(process.env.WIDTH || 1280);   // CSS-bredd på "fönstret"
const SCALE = Number(process.env.SCALE || 2);      // device-scale-factor (2 = skarp text)
const PAD = Number(process.env.PAD || 40);         // extra bottenmarginal i device-pixlar
const START_HEIGHT = Number(process.env.HEIGHT || 3000); // CSS-höjd, dubblas vid behov
const MAX_HEIGHT = 24000;                           // säkerhetstak för höjden
const DEFAULT_DIR = join(REPO_ROOT, 'docs', 'koncept');

// Hitta en Windows-webbläsare (Chrome först, annars Edge).
function findBrowser() {
  const candidates = [
    '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
    '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    '/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe',
  ];
  const hit = candidates.find((p) => existsSync(p));
  if (!hit) {
    throw new Error(
      'Hittade varken Windows-Chrome eller Edge under /mnt/c. ' +
      'Installera Chrome i Windows eller ange sökväg i skriptet.'
    );
  }
  return hit;
}

// WSL-sökväg -> Windows-sökväg (\\wsl.localhost\...).
function toWin(p) {
  return execFileSync('wslpath', ['-w', p]).toString().trim();
}

// Rendera HTML till en temporär PNG vid given CSS-höjd. Returnerar en pngjs-instans.
function renderAt(browser, htmlPath, tmpPng, height) {
  const winIn = toWin(htmlPath);
  const winOut = toWin(tmpPng);
  execFileSync(browser, [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--force-color-profile=srgb',
    '--run-all-compositor-stages-before-draw',
    '--virtual-time-budget=4000',       // ge webbfonter/layout tid att sätta sig
    `--force-device-scale-factor=${SCALE}`,
    `--window-size=${WIDTH},${height}`,
    `--screenshot=${winOut}`,
    winIn,
  ], { stdio: 'ignore' });
  if (!existsSync(tmpPng)) {
    throw new Error(`Chrome skrev ingen PNG för ${htmlPath}`);
  }
  return PNG.sync.read(readFileSync(tmpPng));
}

// Kolla om nedersta raden är enfärgad bakgrund (då syns hela sidan + tomrum).
// Om nedersta raden INTE är enfärgad har innehållet troligen klippts.
function bottomRowIsUniform(png) {
  const { width, height, data } = png;
  const y = height - 1;
  const i0 = (y * width) * 4;
  const [r, g, b] = [data[i0], data[i0 + 1], data[i0 + 2]];
  for (let x = 1; x < width; x++) {
    const i = (y * width + x) * 4;
    if (Math.abs(data[i] - r) > 4 || Math.abs(data[i + 1] - g) > 4 || Math.abs(data[i + 2] - b) > 4) {
      return false;
    }
  }
  return true;
}

// Hitta sista raden som skiljer sig från bakgrundsfärgen (nederkant på innehållet).
function findContentBottom(png) {
  const { width, height, data } = png;
  // Bakgrund = färgen i nedersta vänstra hörnet (ligger under allt innehåll).
  const bi = ((height - 1) * width) * 4;
  const [br, bg, bb] = [data[bi], data[bi + 1], data[bi + 2]];
  for (let y = height - 1; y >= 0; y--) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      if (Math.abs(data[i] - br) > 4 || Math.abs(data[i + 1] - bg) > 4 || Math.abs(data[i + 2] - bb) > 4) {
        return y; // första icke-bakgrundsraden nedifrån
      }
    }
  }
  return height - 1; // helt tom bild – borde inte hända
}

// Beskär pngjs-bilden till [0..cropH) i höjd.
function cropHeight(png, cropH) {
  const out = new PNG({ width: png.width, height: cropH });
  png.data.copy(out.data, 0, 0, cropH * png.width * 4);
  return out;
}

function processFile(browser, htmlPath) {
  const outPath = join(dirname(htmlPath), basename(htmlPath, extname(htmlPath)) + '.png');
  const tmpPng = join(dirname(htmlPath), '.' + basename(htmlPath) + '.tmp.png');

  let height = START_HEIGHT;
  let png = renderAt(browser, htmlPath, tmpPng, height);
  // Om innehållet klipptes (botten inte enfärgad) – dubbla höjden och försök igen.
  while (!bottomRowIsUniform(png) && height < MAX_HEIGHT) {
    height = Math.min(height * 2, MAX_HEIGHT);
    png = renderAt(browser, htmlPath, tmpPng, height);
  }

  const contentBottom = findContentBottom(png);
  const cropH = Math.min(png.height, contentBottom + 1 + PAD);
  const finalPng = cropHeight(png, cropH);
  writeFileSync(outPath, PNG.sync.write(finalPng));
  unlinkSync(tmpPng);

  const clipped = !bottomRowIsUniform(png);
  return { outPath, width: finalPng.width, height: finalPng.height, clipped };
}

// ---- Samla in filer att rendera -------------------------------------------
function resolveInputs(argv) {
  if (argv.length) {
    return argv.map((p) => resolve(process.cwd(), p));
  }
  if (!existsSync(DEFAULT_DIR)) {
    throw new Error(`Standardmappen saknas: ${DEFAULT_DIR}`);
  }
  return readdirSync(DEFAULT_DIR)
    .filter((f) => f.toLowerCase().endsWith('.html'))
    .sort()
    .map((f) => join(DEFAULT_DIR, f));
}

// ---- Kör -------------------------------------------------------------------
const browser = findBrowser();
const inputs = resolveInputs(process.argv.slice(2));
if (!inputs.length) {
  console.log('Inga HTML-filer att rendera.');
  process.exit(0);
}
console.log(`Webbläsare: ${browser}`);
console.log(`Renderar ${inputs.length} fil(er) @ ${WIDTH}px bredd, scale ${SCALE}x\n`);

let failed = 0;
for (const html of inputs) {
  if (!existsSync(html)) {
    console.error(`  ✗ saknas: ${html}`);
    failed++;
    continue;
  }
  try {
    const r = processFile(browser, html);
    const rel = r.outPath.replace(REPO_ROOT + '/', '');
    const warn = r.clipped ? '  ⚠ innehåll kan ha klippts (nådde höjdtaket)' : '';
    console.log(`  ✓ ${rel}  (${r.width}×${r.height})${warn}`);
  } catch (e) {
    console.error(`  ✗ ${basename(html)}: ${e.message}`);
    failed++;
  }
}
console.log(`\nKlart. ${inputs.length - failed}/${inputs.length} lyckades.`);
process.exit(failed ? 1 : 0);
