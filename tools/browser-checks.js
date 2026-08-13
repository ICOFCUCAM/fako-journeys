/* What the browser actually does with these pages.
 *
 *     node tools/browser-checks.js          (or: python3 tools/tourism/build.py test)
 *
 * Two passes, both of them measuring something no amount of reading the source
 * will tell you: does the page move under the reader while it loads, and is
 * there anything left of it when scripting is off.
 *
 * ---------------------------------------------------------------------------
 * PASS ONE — layout shift
 *
 * Layout shift is the one quality of a page that cannot be read off the source.
 * You can look at an <img> all day and not know whether its box was reserved:
 * the answer depends on the CSS that ends up applying to it, the srcset
 * candidate the browser picks at that viewport, and what else is in the grid
 * row. So this measures it, in a browser, with the images arriving late.
 *
 * Late is the point. On a fast connection nothing shifts because nothing is
 * ever missing — every image is there before first paint and a page with no
 * reserved space at all scores zero. Every image response is held back 1.2
 * seconds here, which is roughly a phone on a bad link, and is the only
 * condition under which reserving space does anything at all.
 *
 * This check exists because of what it found the first time it was run. The
 * intention had been to add width and height to the forty images on the five
 * hand-written pages, which is standard practice and looks obviously correct in
 * a diff. Measured, four of the five pages were already at zero — their CSS
 * reserves every box with aspect-ratio — and on the fifth the attributes took
 * layout shift from 0.002 to 0.17, past the threshold where Google calls a page
 * bad. The change was reverted. Without a measurement it would have shipped,
 * and the commit message would have claimed an improvement.
 *
 * The budget is 0.1, which is the boundary of "good" in Core Web Vitals.
 */
'use strict';

const fs = require('fs');
const http = require('http');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const BUDGET = 0.1;
const HOLD = 1200;          // ms every image is held back
const SETTLE = 2600;        // ms to watch after the HTML lands

/* The pages worth watching: one of each kind, not all 650. A place page and a
   portrait stand for their 571 and 21 siblings, which are built by the same
   generator from the same template and cannot differ in layout. */
const PAGES = [
  '/index.html', '/atlas.html', '/journey.html', '/stories.html',
  '/places/index.html', '/compare.html', '/meet.html', '/404.html',
  '/portrait/kenya.html', '/places/kenya/balloon-over-the-mara.html',
  '/tourism/kenya.html', '/tourism/index.html', '/kenya.html',
  '/cameroon.html', '/contact.html', '/about.html', '/pricing.html',
  '/services.html'
];

const TYPES = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp',
  '.xml': 'application/xml', '.txt': 'text/plain'
};

/* ---------------------------------------------------------------------------
 * PASS TWO — with scripting off
 *
 * Every page here is meant to be readable without a script; several say so in
 * their own comments. Two were not. /contact and the twenty-three tourism pages
 * reveal their content with an IntersectionObserver adding a class to elements
 * that start at opacity 0, so with no observer the words were there in the DOM
 * and invisible on the screen — sixteen blocks on one, twenty-five on the other.
 * /compare builds its entire table in script into an empty div, and after the
 * layout-shift fix reserved 3,300 pixels for it, so with no script it was a
 * headline followed by three and a half thousand pixels of nothing.
 *
 * The bar is deliberately low and absolute: a page must render at least a
 * quarter of the words it renders with scripting on, and must not leave a
 * screenful of empty space where its main content should be. This is a check
 * against total failure, not a demand that every feature work without a script.
 */
const NOJS_MIN_WORDS = 0.25;

/* ---------------------------------------------------------------------------
 * PASS THREE — text you can actually read
 *
 * Contrast has been measured by hand half a dozen times in this project and
 * every time it found something: a plate whose caption sat at 2.5:1 on two of
 * five region tones, a panel at 1.03:1 because its photograph was never placed,
 * two tokens at 4.16 and 4.46 against a 4.5 requirement. Measuring it by hand
 * means measuring it once; this measures it on every page, every run.
 *
 * WCAG 1.4.3 AA: 4.5:1 for text under 24px (or under 18.66px bold), 3:1 above.
 * Colours are read from getComputedStyle, which returns color(srgb r g b) with
 * floats — not rgb() with 0-255 — wherever color-mix() computed the value. A
 * probe that assumed 0-255 once reported this site failing at 1.0:1 everywhere,
 * so the parser handles both and the ratio is checked against known pairs.
 */
const AA_SMALL = 4.5;
const AA_LARGE = 3.0;

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

function done(code) {
  process.stdout.write(out.join('\n') + '\n');
  process.exit(code);
}

function chromium() {
  /* playwright-core is installed globally in this image and not in the repo, so
     it is found rather than depended on. No browser, no check — the same way
     the journey checks skip when node is missing, because a test that cannot
     run must say so rather than pass. */
  const roots = [
    '/opt/node22/lib/node_modules/playwright/node_modules/playwright-core',
    'playwright-core', 'playwright'
  ];
  for (const r of roots) {
    try { return require(r).chromium; } catch (e) { /* next */ }
  }
  return null;
}

function browserPath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || '/opt/pw-browsers';
  let names = [];
  try { names = fs.readdirSync(base); } catch (e) { return null; }
  const dirs = names.filter(n => n.indexOf('chromium') === 0).sort().reverse();
  for (const d of dirs) {
    for (const rel of ['chrome-linux/headless_shell', 'chrome-linux/chrome']) {
      const full = path.join(base, d, rel);
      if (fs.existsSync(full)) return full;
    }
  }
  return fs.existsSync(path.join(base, 'chromium')) ? path.join(base, 'chromium') : null;
}

function serve() {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      let rel = decodeURIComponent(req.url.split('?')[0]);
      let file = path.join(ROOT, rel);
      try {
        if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
      } catch (e) { /* fall through to the 404 */ }
      fs.readFile(file, (err, body) => {
        if (err) { res.writeHead(404); res.end('no'); return; }
        res.writeHead(200, {'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream'});
        res.end(body);
      });
    });
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

(async function () {
  const launcher = chromium();
  const exe = browserPath();
  if (!launcher || !exe) {
    check('layout shift was measured', false,
          'no headless browser available; nothing was measured');
    done(1);
  }

  const server = await serve();
  const base = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    browser = await launcher.launch({executablePath: exe});
    for (const url of PAGES) {
      const page = await browser.newPage({viewport: {width: 1280, height: 900}});
      await page.route(/\.(jpe?g|png|webp|avif)(\?|$)|images\.(unsplash|pexels)\.com/i,
        async route => {
          await new Promise(go => setTimeout(go, HOLD));
          try { await route.continue(); } catch (e) { /* page closed */ }
        });
      await page.addInitScript(() => {
        window.__cls = 0;
        window.__worst = null;
        new PerformanceObserver(list => {
          for (const e of list.getEntries()) {
            if (e.hadRecentInput) continue;
            window.__cls += e.value;
            if (!window.__worst || e.value > window.__worst.v) {
              const s = (e.sources || [])[0];
              window.__worst = {
                v: e.value,
                what: s && s.node
                  ? (s.node.nodeName + '.' + String(s.node.className || '').slice(0, 24))
                  : 'unknown'
              };
            }
          }
        }).observe({type: 'layout-shift', buffered: true});
      });
      let failed = null;
      try {
        await page.goto(base + url, {waitUntil: 'domcontentloaded'});
        await page.waitForTimeout(SETTLE);
      } catch (e) { failed = e.message.split('\n')[0]; }
      const seen = failed ? null : await page.evaluate(
        () => ({cls: window.__cls, worst: window.__worst}));
      await page.close();
      if (failed) {
        check(url + ' could be measured', false, failed.slice(0, 70));
        continue;
      }
      const cls = Math.round(seen.cls * 10000) / 10000;
      check(url + ' holds still while its images arrive', cls <= BUDGET,
            'CLS ' + cls.toFixed(4)
            + (seen.worst ? ' — worst mover ' + seen.worst.what : ''));
    }
    /* ---- pass three: contrast ------------------------------------------- */
    for (const url of PAGES) {
      const page = await browser.newPage({viewport: {width: 1280, height: 900}});
      await page.goto(base + url, {waitUntil: 'networkidle'});
      const bad = await page.evaluate(([small, large]) => {
        function rgb(text) {
          let m = String(text).match(/^color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)/);
          if (m) return [+m[1], +m[2], +m[3]];
          m = String(text).match(/^rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
          if (!m) return null;
          if (m[4] !== undefined && +m[4] < 0.95) return null;   // translucent: skip
          return [m[1] / 255, m[2] / 255, m[3] / 255];
        }
        function lum(c) {
          const f = v => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
          return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
        }
        function ratio(a, b) {
          const x = lum(a), y = lum(b);
          return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
        }
        /* The ground a piece of text is actually painted on: the nearest
           ancestor with an opaque background. Walking up is the only way —
           an element with no background of its own inherits nothing, it just
           shows whatever is behind it. */
        function ground(el) {
          for (let n = el; n; n = n.parentElement) {
            const c = rgb(getComputedStyle(n).backgroundColor);
            if (c) return c;
          }
          return [1, 1, 1];
        }
        const out = [];
        document.querySelectorAll('body *').forEach(el => {
          /* Only elements that hold their own words. A wrapper's colour is not
             what the reader sees, and exempting inline tags from this rule —
             which the first version did, on the theory that a <span> is always
             text — produced two false failures immediately: a month cell whose
             <b> is recoloured on the accent ground, and a pressed door whose
             <b> is recoloured on the dark one. Both wrappers inherit the page
             ink and neither paints a pixel with it. */
          const text = [...el.childNodes]
            .filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
          if (!text) return;
          const box = el.getBoundingClientRect();
          if (!box.width || !box.height) return;
          const cs = getComputedStyle(el);
          if (cs.visibility === 'hidden' || +cs.opacity < 0.95) return;
          /* Text over a photograph is measured against the veil, which this
             cannot see; those components carry their own ground and are
             excluded by having an image between them and the page. */
          if (el.closest('[data-photo],.wa-now-art,.af-window-svg,picture')) return;
          const fg = rgb(cs.color);
          if (!fg) return;
          const size = parseFloat(cs.fontSize);
          const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
          const need = (size >= 24 || (bold && size >= 18.66)) ? large : small;
          const got = ratio(fg, ground(el));
          if (got + 0.005 < need) {
            out.push(Math.round(got * 100) / 100 + ':1 needs ' + need + ' — '
              + el.tagName + '.' + String(el.className).slice(0, 20)
              + ' [' + text.slice(0, 24) + ']');
          }
        });
        return [...new Set(out)];
      }, [AA_SMALL, AA_LARGE]);
      await page.close();
      check(url + ' has no text under the contrast it needs', !bad.length,
            bad.length ? bad.length + ' below AA: ' + bad.slice(0, 2).join(' | ') : 'all AA');
    }

    /* ---- pass two: with scripting off ---------------------------------- */
    const off = await browser.newContext({viewport: {width: 1280, height: 900},
                                          javaScriptEnabled: false});
    for (const url of PAGES) {
      const lit = await browser.newPage({viewport: {width: 1280, height: 900}});
      await lit.goto(base + url, {waitUntil: 'networkidle'});
      const withJs = await lit.evaluate(
        () => (document.body.innerText || '').trim().split(/\s+/).length);
      await lit.close();

      const dark = await off.newPage();
      await dark.goto(base + url, {waitUntil: 'domcontentloaded'});
      await dark.waitForTimeout(200);
      const seen = await dark.evaluate(() => {
        const text = (document.body.innerText || '').trim();
        /* The tallest run of nothing: an element whose box is a screen or more
           and which paints no text at all. That is what a reserved-but-never-
           filled container looks like, and it is invisible to word counting. */
        let void_ = 0, culprit = '';
        document.querySelectorAll('main *').forEach(el => {
          const box = el.getBoundingClientRect();
          if (box.height < 900) return;
          if ((el.innerText || '').trim()) return;
          /* A tall box with no words in it is fine if it is a picture. It is
             only a hole if nothing is painted there at all. */
          if (el.matches('img,svg,picture,video,canvas')) return;
          if (el.closest('svg')) return;             // drawing, not layout
          if (el.querySelector('img,svg,picture,video,canvas')) return;
          const cs = getComputedStyle(el);
          /* Taken out of flow, so it reserves nothing and cannot be the hole —
             a gradient veil over a photograph is the usual case. */
          if (cs.position === 'absolute' || cs.position === 'fixed') return;
          if (cs.backgroundImage && cs.backgroundImage !== 'none') return;
          if (box.height > void_) { void_ = Math.round(box.height); culprit = el.tagName + '.' + String(el.className).slice(0, 20); }
        });
        return {words: text ? text.split(/\s+/).length : 0, void_, culprit};
      });
      await dark.close();

      const share = withJs ? seen.words / withJs : 1;
      check(url + ' still reads with scripting off',
            share >= NOJS_MIN_WORDS && seen.void_ === 0,
            seen.words + ' of ' + withJs + ' words ('
            + Math.round(share * 100) + '%)'
            + (seen.void_ ? ' — ' + seen.void_ + 'px of nothing at ' + seen.culprit : ''));
    }
    await off.close();
  } catch (e) {
    check('the browser checks ran', false, String(e.message).slice(0, 90));
  } finally {
    if (browser) await browser.close();
    server.close();
  }
  done(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
}());
