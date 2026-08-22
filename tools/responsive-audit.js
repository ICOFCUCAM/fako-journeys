/* Responsive audit: horizontal overflow and tap targets, at four widths.
 *
 *     node tools/responsive-audit.js
 *
 * COMMIT 17 OF THE 50-COMMIT INTEGRATION MANDATE.
 *
 * WHY THIS EXISTS BESIDE browser-checks.js, WHICH ALREADY MEASURES TAP TARGETS.
 *
 * That suite runs its tap-target pass in a TOUCH context, and says so in its
 * own comment: the CSS fix keys on @media(pointer:coarse), "so a desktop
 * context measures the un-fixed setting and reports nothing wrong." Entirely
 * reasonable — and it meant the desktop numbers were never looked at.
 *
 * They were 23.4px (.af-go), 23.6px (.mt-flag) and 22.8px (.pi-jump a). WCAG
 * 2.5.8 asks for 24 by 24 and says nothing about pointer type: a mouse is a
 * pointer, and a target six tenths of a pixel short fails for a mouse user
 * exactly as it would for a thumb. The jump links on /places were the worst of
 * them — 22.8px on a 390px phone, in a STICKY row, which is the control a
 * reader is most likely to reach for with a thumb while scrolling past.
 *
 * TWO EXCLUSIONS, BOTH FROM THE SUCCESS CRITERION ITSELF, NEITHER A LOOPHOLE.
 *
 *   SVG shapes   the atlas draws fifty-four countries and Rwanda is seven
 *                pixels square. 2.5.8 allows that where an equivalent control
 *                exists, and the tick rail beside the map is that control —
 *                asserted separately, by name, in tools/tourism/tests.py.
 *   prose links  "in a sentence, or constrained by the line-height of
 *                non-target text". Anything inside a p, li, figcaption, dd or
 *                blockquote is left alone.
 *
 * AND A METRIC I WROTE AND THREW AWAY. A first version also reported line
 * length, and flagged the footer's legal line at "256ch". It was measuring the
 * width of the BOX, not the length of the line — so any wide container holding
 * a short sentence looked like unreadable prose. A measurement that cannot
 * tell those apart is not evidence, and it is not in this file.
 */
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const TYPES = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.webp': 'image/webp', '.avif': 'image/avif',
  '.woff2': 'font/woff2',
};

/* One page from each family, rather than 1,599 of them: the failures this
   finds are CSS failures, and a second place page tests the same rules. */
const PAGES = [
  '/', '/journey', '/journey-fund', '/travel-points', '/trust', '/places',
  '/atlas', '/stories', '/meet', '/trans-afrique', '/enquire',
  '/tourism/kenya', '/portrait/kenya', '/places/algeria/the-kabylie-cedars',
  '/wonders', '/compare', '/about-afrinkong',
];
const WIDTHS = [[390, 844, 'phone'], [768, 1024, 'tablet'],
                [1280, 860, 'desktop'], [1920, 1080, 'wide']];
const TARGET_MIN = 24;

function serve() {
  return http.createServer((req, res) => {
    let rel = decodeURIComponent(req.url.split('?')[0]);
    if (rel.endsWith('/')) rel += 'index.html';
    let file = path.join(ROOT, rel);
    if (!fs.existsSync(file) && fs.existsSync(file + '.html')) file += '.html';
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()
        && fs.existsSync(path.join(file, 'index.html'))) {
      file = path.join(file, 'index.html');
    }
    if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404); return res.end('not found');
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
}

function chromiumPath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  if (!fs.existsSync(base)) return null;
  for (const d of fs.readdirSync(base).filter((n) => n.startsWith('chromium')).sort().reverse()) {
    for (const rel of ['chrome-linux/chrome', 'chrome-linux/headless_shell']) {
      const f = path.join(base, d, rel);
      if (fs.existsSync(f)) return f;
    }
  }
  return null;
}

(async function main() {
  let chromium;
  for (const r of ['playwright-core', 'playwright']) {
    try { chromium = require(r).chromium; break; } catch (e) { /* next */ }
  }
  const exe = chromiumPath();
  if (!chromium || !exe) {
    /* No browser, no check — the same way the journey checks skip when node is
       missing. A test that cannot run must say so rather than pass. */
    console.log('SKIP\tno chromium available; nothing measured');
    process.exit(0);
  }

  const server = serve();
  await new Promise((r) => server.listen(8213, r));
  const browser = await chromium.launch({ executablePath: exe });

  const overflow = [];
  const small = [];
  let checked = 0;

  for (const [w, h, label] of WIDTHS) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    for (const url of PAGES) {
      await page.goto('http://127.0.0.1:8213' + url, { waitUntil: 'networkidle' })
        .catch(() => {});
      await page.waitForTimeout(120);
      const r = await page.evaluate((min) => {
        const de = document.documentElement;
        const over = de.scrollWidth - de.clientWidth;
        const tiny = [];
        const sel = 'a,button,summary,input,select,[role=button]';
        for (const el of document.querySelectorAll(sel)) {
          if (el.ownerSVGElement || el instanceof SVGElement) continue;
          if (el.closest('p,li,figcaption,dd,blockquote')) continue;
          /* A visually-hidden input behind a styled label is not the target;
             the label is, and it is measured on its own. browser-checks.js
             makes the same exemption for the same reason. */
          if (el.matches('input') && el.closest('label')) continue;
          const b = el.getBoundingClientRect();
          if (b.width === 0 || b.height === 0) continue;
          if (b.height < min - 0.01 || b.width < min - 0.01) {
            tiny.push(`${(String(el.className).split(' ')[0] || el.tagName)}${
              el.className ? '' : '[' + (el.textContent || '').trim().slice(0, 14) + ']'
              } ${b.width.toFixed(1)}x${b.height.toFixed(1)}`);
          }
        }
        return { over, tiny: [...new Set(tiny)] };
      }, TARGET_MIN);
      checked++;
      if (r.over > 1) overflow.push(`${label} ${url} +${r.over}px`);
      if (r.tiny.length) small.push(`${label} ${url}: ${r.tiny.slice(0, 3).join(' | ')}`);
    }
    await page.close();
  }
  await browser.close();
  server.close();

  const say = (ok, name, detail) =>
    console.log(`${ok ? 'PASS' : 'FAIL'}\t${name}\t${detail}`);

  say(overflow.length === 0, 'no page scrolls sideways at any width',
    overflow.length ? overflow.slice(0, 5).join(' | ')
                    : `${checked} page-widths across ${PAGES.length} families`);
  say(small.length === 0, `every control is at least ${TARGET_MIN}px, for every pointer`,
    small.length ? small.slice(0, 5).join(' | ')
                 : `${checked} page-widths; SVG map shapes and prose links are ` +
                   'exempt under the criterion itself, not by convenience');

  process.exit(overflow.length || small.length ? 1 : 0);
}());
