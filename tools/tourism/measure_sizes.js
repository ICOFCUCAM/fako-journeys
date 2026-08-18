/* Measure how wide every photograph is actually painted, at every width.
 *
 *     node tools/tourism/measure_sizes.js > data/sizes.json
 *
 * WHY THIS IS MEASURED AND NOT INFERRED
 *
 * srcset.py deliberately writes srcset and NOT sizes, and says why: getting
 * `sizes` wrong is worse than leaving it out, because too small a hint makes
 * the browser fetch a file it cannot un-blur, and working it out per image
 * "means knowing the grid each one sits in on every breakpoint, which is a
 * per-component decision and not something to infer from a file name."
 *
 * That is entirely right about inferring. It is not an argument against
 * measuring. This opens the built pages in the same browser the checks use,
 * lays them out at twelve widths, and reads getBoundingClientRect().width off
 * every <img> that has a srcset to choose from. Nothing is guessed; the number
 * written down is the number the browser laid out.
 *
 * WHAT IT COSTS TO BE WRONG, AND WHICH WAY TO BE WRONG
 *
 * Too large a hint wastes bytes. Too small a hint ships a blurry photograph to
 * a page whose whole argument is the photographs. So every band takes the
 * LARGEST width measured anywhere inside it, and the last band is measured out
 * to 2560 rather than stopping at the widest common laptop.
 *
 * Keyed by page and by the image's position in the document, not by file name:
 * the same photograph is 950px wide on one page and 287px on another, and a
 * key that could not tell those apart would have to take the larger and lose
 * most of the point.
 */
'use strict';

const path = require('path');
const fs = require('fs');
const PC = '/opt/node22/lib/node_modules/playwright/node_modules/playwright-core';
const { chromium } = require(PC);

const ROOT = path.join(__dirname, '..', '..');
const PORT = 8917;

/* The bands the site's own stylesheets break at, plus the widths inside each
   one where a layout actually changes. A band is only as good as the widest
   thing measured in it. */
const BANDS = [
  { upto: 430, at: [320, 360, 390, 430] },
  { upto: 768, at: [560, 700, 768] },
  { upto: 1200, at: [900, 1024, 1100, 1200] },
  { upto: null, at: [1280, 1440, 1920, 2560] },
];

/* One page per shape the site generates. Measuring 1,594 pages to learn the
   same four numbers 1,594 times would take an hour and teach nothing: pages of
   one family are the same layout with different content. */
const PAGES = process.argv.slice(2).length ? process.argv.slice(2) : [
  'index.html',
  'atlas.html',
  'journey.html',
  'meet.html',
  'stories.html',
  'wonders.html',
  'how-it-works.html',
  'enquire.html',
  'compare.html',
  'cameroon.html',
  'about.html',
  'services.html',
  'pricing.html',
  'contact.html',
  path.join('tourism', 'kenya.html'),
  path.join('tourism', 'index.html'),
  path.join('portrait', 'kenya.html'),
  path.join('places', 'index.html'),
  path.join('places', 'kenya', 'balloon-over-the-mara.html'),
  path.join('trans-afrique', 'west.html'),
  path.join('trans-afrique', 'crossings.html'),
];

function serve() {
  const http = require('http');
  const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
    '.json': 'application/json', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.webmanifest': 'application/manifest+json' };
  return http.createServer(function (req, res) {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const f = path.join(ROOT, p);
    if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
      res.writeHead(404); res.end(); return;
    }
    res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  }).listen(PORT);
}

(async function () {
  const server = serve();
  const browser = await chromium.launch();
  const out = {};
  for (const rel of PAGES) {
    if (!fs.existsSync(path.join(ROOT, rel))) continue;
    const url = 'http://127.0.0.1:' + PORT + '/' + rel.split(path.sep).join('/');
    const perImage = {};
    for (let bi = 0; bi < BANDS.length; bi++) {
      for (const w of BANDS[bi].at) {
        const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        const page = await ctx.newPage();
        try {
          await page.goto(url, { waitUntil: 'load', timeout: 60000 });
          await page.evaluate(() => document.fonts && document.fonts.ready);
          /* The carousels and the rotating strip move things after first
             paint, and a slide measured mid-transition is a slide measured
             at the wrong width. */
          await page.waitForTimeout(400);
          const rows = await page.evaluate(() => Array.from(document.images).map(function (img, i) {
            return { i: i, w: Math.ceil(img.getBoundingClientRect().width),
                     set: !!img.getAttribute('srcset'),
                     src: img.getAttribute('src') || '' };
          }));
          for (const r of rows) {
            if (!r.set || !r.w) continue;
            const k = String(r.i);
            perImage[k] = perImage[k] || { src: r.src, at: {} };
            /* EVERY VIEWPORT, NOT THE LARGEST PER BAND.
               The first version kept one number per band, and one number
               cannot say whether an image is 430 pixels wide because it is
               full-width on a 430 phone or because it is a fixed 430-pixel
               card. Those want opposite hints — `100vw` and `430px` — and
               guessing wrong made a phone download twice what it needed. The
               ratio to the viewport is the thing that distinguishes them, and
               it takes two measurements in a band to see it. */
            perImage[k].at[w] = Math.max(perImage[k].at[w] || 0, r.w);
          }
        } catch (e) {
          process.stderr.write('  ' + rel + ' @' + w + ': ' + e.message + '\n');
        }
        await ctx.close();
      }
    }
    if (Object.keys(perImage).length) out[rel.split(path.sep).join('/')] = perImage;
    process.stderr.write(rel + ': ' + Object.keys(perImage).length + ' image(s) with a srcset\n');
  }
  await browser.close();
  server.close();
  process.stdout.write(JSON.stringify({
    $comment: 'Painted width of every photograph that has a srcset, per page, '
      + 'at every viewport width measured, in a real browser. See '
      + 'tools/tourism/measure_sizes.js. Regenerate after any layout change.',
    bands: BANDS.map(b => b.upto),
    widths: BANDS.map(b => b.at),
    pages: out,
  }, null, 1) + '\n');
})();
