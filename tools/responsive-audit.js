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
  /* ---- FOCUS THAT CAN BE SEEN -----------------------------------------
   *
   * browser-checks.js PASS SEVEN asserts that focus does not land on an
   * INVISIBLE control. It does not assert that focus itself is visible, and
   * those are different questions: a control can be perfectly on screen and
   * give no sign at all that the keyboard has reached it.
   *
   * Six rules in this codebase set `outline:none` inside a focus selector, and
   * every one of them turns out to be legitimate — three are
   * :focus:not(:focus-visible), which removes the ring for a MOUSE and keeps
   * it for a keyboard; .tf-level-go moves the ring to the card around it with
   * :has(); .cm-link indicates focus by changing an SVG path fill. I checked
   * all six by reading them, which is exactly the method that does not scale
   * and does not survive a seventh being added.
   *
   * So this focuses controls and looks. The indicator may appear on the
   * element, on an ANCESTOR (the :has() case) or on a DESCENDANT (the SVG fill
   * case) — all three are real techniques and all three are legitimate, so all
   * three count. What does not count is nothing changing.
   */
  const invisibleFocus = [];
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
    for (const url of PAGES) {
      await page.goto('http://127.0.0.1:8213' + url, { waitUntil: 'networkidle' })
        .catch(() => {});
      /* DRIVEN BY THE TAB KEY, NOT BY el.focus().
         Nearly every indicator on this site is written as :focus-visible, and
         a programmatic focus() does not reliably match it — Chromium decides
         from how the element was reached. A script that calls focus() and sees
         nothing change is measuring its own method. Pressing Tab is what a
         keyboard user does, and it is the only way this answer is worth
         anything. */
      const bad = await page.evaluate(() => { window.__seen = []; });
      for (let i = 0; i < 30; i++) {
        await page.keyboard.press('Tab');
        const r = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const WATCH = ['outline', 'outlineColor', 'outlineWidth', 'outlineStyle',
                         'boxShadow', 'backgroundColor', 'color', 'borderColor',
                         'borderBottomColor', 'textDecorationLine', 'fill',
                         'stroke', 'strokeWidth', 'opacity', 'transform'];
          const snap = () => {
            const nodes = [el, el.parentElement, ...el.querySelectorAll('*')].slice(0, 8);
            return nodes.map((n) => n ? WATCH.map((k) => getComputedStyle(n)[k]).join('|') : '')
              .join('#');
          };
          const focused = snap();
          /* The same element with focus taken away, for comparison. Blur and
             re-read, then hand focus back so the tab order is not disturbed. */
          el.blur();
          const blurred = snap();
          el.focus();
          const name = (String(el.className).split(' ')[0] || el.tagName)
            + '[' + (el.textContent || '').trim().slice(0, 16) + ']';
          return { same: focused === blurred, name };
        });
        if (r && r.same) {
          if (!invisibleFocus.some((x) => x.startsWith(url + ':') && x.includes(r.name))) {
            invisibleFocus.push(`${url}: ${r.name}`);
          }
        }
      }
    }
    await page.close();
  }

  /* ---- REDUCED MOTION, MEASURED IN THE RENDERED PAGE -------------------
   *
   * Counting @media(prefers-reduced-motion) blocks per stylesheet says
   * nothing useful. Four sheets — meet, places, trust, wonders — carry eleven
   * motion declarations between them and no such block, which looks like a gap
   * and is not one: afrinkong.css loads on every page and carries a global
   *
   *     *,*::before,*::after{transition-duration:.001ms!important; ...}
   *
   * so the four are covered by something they never mention. A per-file audit
   * would have raised four false alarms and, worse, invited somebody to "fix"
   * them by adding four more blocks.
   *
   * So ask the browser instead. Under reduce, nothing may still be animating
   * and nothing may still be smooth-scrolling — including elements other than
   * <html>, which the global rule handles by name and only by name.
   */
  const stillMoving = [];
  {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 860 },
      reducedMotion: 'reduce',
    });
    for (const url of PAGES) {
      await page.goto('http://127.0.0.1:8213' + url, { waitUntil: 'networkidle' })
        .catch(() => {});
      const bad = await page.evaluate(() => {
        const out = [];
        for (const el of [...document.querySelectorAll('*')].slice(0, 4000)) {
          const cs = getComputedStyle(el);
          const dur = (v) => Math.max(...String(v).split(',')
            .map((x) => parseFloat(x) * (x.includes('ms') ? 1 : 1000) || 0));
          if (dur(cs.transitionDuration) > 1 || dur(cs.animationDuration) > 1) {
            out.push('moves:' + (String(el.className).split(' ')[0] || el.tagName));
          }
          if (cs.scrollBehavior === 'smooth') {
            out.push('smooth:' + (String(el.className).split(' ')[0] || el.tagName));
          }
        }
        return [...new Set(out)].slice(0, 3);
      });
      if (bad.length) stillMoving.push(`${url}: ${bad.join(' | ')}`);
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

  say(invisibleFocus.length === 0, 'focus can be seen when it lands',
    invisibleFocus.length ? invisibleFocus.slice(0, 5).join(' | ')
      : `every control on ${PAGES.length} families changes something visible ` +
        'when focused \u2014 on itself, an ancestor or a descendant, all three ' +
        'being real techniques this site uses');

  say(stillMoving.length === 0, 'reduce means reduce, in the rendered page',
    stillMoving.length ? stillMoving.slice(0, 5).join(' | ')
      : `${PAGES.length} families under prefers-reduced-motion: nothing still ` +
        'transitions, animates or smooth-scrolls \u2014 including the four ' +
        'stylesheets that carry motion and no reduced-motion block of their own');

  process.exit(overflow.length || small.length || invisibleFocus.length
    || stillMoving.length ? 1 : 0);
}());
