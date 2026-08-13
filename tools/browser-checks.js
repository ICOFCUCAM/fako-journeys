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

/* ---------------------------------------------------------------------------
 * PASS FOUR — horizontal overflow
 *
 * A page wider than the screen is the one layout fault a reader cannot work
 * around: they scroll sideways to read a paragraph, or they never find the
 * button that is off the edge. It is also the one that hides from a desktop
 * browser, and from a phone emulator set to a common width, because it usually
 * lives in a band — a masthead between the width where its nav is still shown
 * and the width where its content stops fitting.
 *
 * Four of those bands were live when this pass was written: the country pages'
 * call sat 179px off screen between 1011 and 1180, the journey masthead 97px
 * off between 721 and 836, /meet's door list 8px off at 320, and Cameroon's
 * opening column 93px off at 320 because a hand-broken headline had no space
 * around its <br> and became one 393-pixel word when the break was hidden.
 * None of the four is visible at 1440, 390 or 768.
 */
const WIDTHS = [320, 360, 390, 430, 560, 768, 900, 1024, 1100, 1180, 1440, 1920];

/* ---------------------------------------------------------------------------
 * PASS FIVE — measure
 *
 * The comfortable line for continuous prose is 45-85 characters; past ninety
 * the eye starts losing its place on the return sweep. Five rules on this site
 * set their width in em or left it unset and produced 96, 104, 118, 148 and
 * 167 characters — the last of them the sentence under the experiences picker,
 * running the full 1240px frame.
 *
 * Only paragraphs of fourteen words or more count. A three-word caption at 200
 * characters would be a different fault and this is not the check for it.
 */
const MEASURE_CAP = 92;

/* ---------------------------------------------------------------------------
 * PASS SIX — target size
 *
 * WCAG 2.5.8 asks for 24 by 24 CSS pixels. On a 390px phone with a coarse
 * pointer, twelve of the eighteen page families had targets at 23, 20, 17 and
 * 13 pixels tall: mono type at 9 to 11px with a rule under it and no padding.
 * Every one of them was wide enough. None was tall enough.
 *
 * It has to run in a touch context — `pointer:coarse` is what the fix keys on,
 * so a desktop context measures the un-fixed setting and reports nothing wrong.
 */
const TARGET_MIN = 24;

/* ---------------------------------------------------------------------------
 * PASS SEVEN — focus that lands on nothing
 *
 * Hiding something with opacity hides it from the eye and from nothing else. It
 * stays in the tab order and in the accessibility tree, so a keyboard user
 * walks through controls that are not on the screen and the focus ring appears
 * to vanish.
 *
 * Two of those here. The gateway stacks twenty-two country captions in one box
 * and shows one — twenty-two invisible links in the tab order, in the hero.
 * And the reveal starts every block at zero opacity until it is scrolled to, so
 * tabbing into the enquiry form put the cursor in a field that was not yet
 * visible and the first characters went into nothing.
 */
const TAB_STOPS = 80;

/* ---------------------------------------------------------------------------
 * PASS EIGHT — the hero is one composition
 *
 * The widths are chosen where the composition changes its mind rather than
 * where devices are: 2560 and 1920 are past the frame's cap, 1440 is the width
 * it was drawn at, 1366 is the commonest laptop, 960 and 900 are inside the
 * band where the two columns used to sit on top of each other, and 390 and 320
 * are the stacked layout.
 *
 * HERO_BLEED is how far the continent may run past the text frame. It is meant
 * to be a constant, which is the whole point — written as right:0 it was 100 at
 * 1440 and 660 at 2560.
 *
 * HERO_BAND is how much empty space the stage may open between the calls and
 * the rail. Unbounded it reached 594px.
 */
const HERO_WIDTHS = [[2560, 1440], [1920, 1080], [1440, 900], [1366, 768],
                     [1180, 820], [960, 760], [900, 700], [390, 844], [320, 700]];
const HERO_BLEED = 140;
const HERO_BAND = 200;

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
    /* ---- pass eight: the hero is one composition ------------------------- */
    /*
     * Everything the other seven passes measure is true of a page. This one is
     * true of a picture, and a picture is what the first screen of this site
     * is: one word set to the width of its column, a continent bled off the
     * right edge of it, and two rails under both.
     *
     * Every fault it looks for was live in the file when it was written, and
     * none of them broke anything the other passes can see. The headline ran
     * 109% of its column at 1600 and 62% at 768. The map's overhang past the
     * frame was 100px at 1440 and 660px at 2560, because it was written as
     * right:0 against a frame that stops growing. The frame was 640 wide around
     * a map that painted 425 of it, so the bleed the composition is built on
     * was not happening at all. The destination rail crossed the map's legend
     * at five widths between 880 and 960. The readout's box was seventeen
     * pixels shorter than the readout, on the view the page opens in.
     *
     * Overflow was zero through all of it. Contrast was AA through all of it.
     * A layout can be composed wrongly and still be, in every measurable
     * respect the rest of this file knows about, correct.
     */
    for (const [w, h] of HERO_WIDTHS) {
      const page = await browser.newPage({viewport: {width: w, height: h}});
      const errs = [];
      page.on('pageerror', e => errs.push(String(e.message).slice(0, 60)));
      await page.goto(base + '/index.html', {waitUntil: 'networkidle'});
      const seen = await page.evaluate(([bleed, band]) => {
        const q = s => document.querySelector(s);
        const B = s => { const e = q(s); return e && e.getBoundingClientRect(); };
        const bad = [];

        /* AFRICA is set to the width of its column. Measured on the glyph run,
           because the element is a block and its box is the column either way. */
        const big = q('.wa-h1-big'), col = q('.wa-open-say');
        if (big && col) {
          const r = document.createRange();
          r.selectNodeContents(big);
          const fill = r.getBoundingClientRect().width / col.getBoundingClientRect().width;
          if (fill < 0.94 || fill > 1.02) bad.push('headline fills ' + Math.round(fill * 100) + '% of its column');
        }

        /* The map's overhang past the text frame is a distance, not a share. */
        const frame = B('.wa-open-stage > .wa-frame'), win = B('.wa-win-frame');
        const say = B('.wa-open-say');
        /* Stacked means the map is under the copy rather than beside it, and
           the test for that is whether it starts left of where the copy ends.
           Comparing it to the text frame's own left edge does not work: the
           frame's box is the full width and its padding is inside it, so on a
           phone the map's left is 20 and the frame's is 0, and every stacked
           width reported itself as a desktop. */
        const stacked = !!(win && say && win.left < say.right - 8);
        if (frame && win && !stacked) {
          const over = Math.round(win.right - frame.right);
          if (over > bleed) bad.push('map overhangs the frame by ' + over);
        }

        /* The frame is the continent's box. Letterboxing inside it is the
           bleed being eaten by empty space nobody can see. */
        const svg = B('.wa-map-svg');
        if (svg && svg.width && svg.height) {
          const k = Math.min(svg.width / 1000, svg.height / 1060);
          const slack = Math.round(Math.max(svg.width - 1000 * k, svg.height - 1060 * k));
          if (slack > 8) bad.push(slack + 'px of letterbox around the map');
        }

        /* Nothing in the hero sits on top of anything else in it. This is the
           one the other passes structurally cannot find: two columns can
           occupy the same pixels without the document overflowing by one. */
        const parts = ['.wa-ticks', '.wa-regs', '.wa-lens', '.wa-win-cap[data-on]',
                       '.wa-win-key', '.wa-win-go', '.wa-acts'];
        for (let i = 0; i < parts.length; i++) {
          for (let j = i + 1; j < parts.length; j++) {
            const a = B(parts[i]), c = B(parts[j]);
            if (!a || !c || !a.width || !c.width) continue;
            if (q(parts[j]).closest(parts[i]) || q(parts[i]).closest(parts[j])) continue;
            const x = Math.min(a.right, c.right) - Math.max(a.left, c.left);
            const y = Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top);
            if (x > 1 && y > 1) bad.push(parts[i] + ' overlaps ' + parts[j]
              + ' by ' + Math.round(x) + 'x' + Math.round(y));
          }
        }

        /* The stage does not grow a gap instead of a composition — but only
           where there is a composition to grow it in. Stacked, the map and its
           readout are between the calls and the rail, so the distance between
           those two is content rather than nothing, and reading it as a gap
           reported 646px at 390 on a layout that has no gap at all. */
        const acts = B('.wa-acts'), rail = B('.wa-win-rail');
        if (!stacked && acts && rail && rail.top > acts.bottom) {
          const gap = Math.round(rail.top - acts.bottom);
          if (gap > band) bad.push(gap + 'px of nothing between the calls and the rail');
        }

        /* The readout's stack stays inside the stage it belongs to. */
        const stage = B('.wa-open-stage'), side = B('.wa-win-side');
        if (stage && side && side.bottom > stage.bottom + 2) {
          bad.push('the readout runs ' + Math.round(side.bottom - stage.bottom) + 'px past the stage');
        }
        return bad;
      }, [HERO_BLEED, HERO_BAND]);
      await page.close();
      check('the hero composes at ' + w + 'x' + h, !seen.length && !errs.length,
            errs.length ? 'script threw: ' + errs[0]
                        : (seen.length ? seen.slice(0, 2).join(' | ') : 'composed'));
    }

    /* ---- pass seven: where the keyboard can go --------------------------- */
    for (const url of PAGES) {
      const page = await browser.newPage({viewport: {width: 1280, height: 900}});
      await page.goto(base + url, {waitUntil: 'networkidle'});
      let stops = 0;
      const blind = [];
      for (let i = 0; i < TAB_STOPS; i++) {
        await page.keyboard.press('Tab');
        const seen = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          /* Opacity is inherited down the tree by compositing, so the lowest
             value on the way up is the one the eye gets. */
          let node = el, opacity = 1;
          while (node && node !== document.body) {
            opacity = Math.min(opacity, +getComputedStyle(node).opacity);
            node = node.parentElement;
          }
          const box = el.getBoundingClientRect();
          return {
            hidden: opacity < 0.05 || getComputedStyle(el).visibility === 'hidden',
            real: box.width > 1 && box.height > 1,
            what: el.tagName + '.' + String(el.className).slice(0, 20)
          };
        });
        if (!seen) continue;
        stops++;
        if (seen.hidden && seen.real) blind.push(seen.what);
      }
      await page.close();
      check(url + ' never puts the focus ring on something invisible',
            !blind.length,
            blind.length ? blind.length + ' of ' + stops + ' stops: '
              + [...new Set(blind)].slice(0, 2).join(' | ')
            : stops + ' stops, all visible');
    }

    /* ---- pass six: what a finger can hit --------------------------------- */
    const touch = await browser.newContext({viewport: {width: 390, height: 844},
                                            isMobile: true, hasTouch: true});
    for (const url of PAGES) {
      const page = await touch.newPage();
      await page.goto(base + url, {waitUntil: 'networkidle'});
      const small = await page.evaluate((min) => {
        const out = [];
        document.querySelectorAll(
          'a[href],button,input:not([type=hidden]),select,summary').forEach(el => {
          const box = el.getBoundingClientRect();
          if (!box.width || !box.height) return;
          if (el.closest('svg')) return;
          const cs = getComputedStyle(el);
          /* Two exceptions the success criterion itself grants. A link set
             inline inside a sentence, where enlarging it would break the line;
             and a control whose real target is something else — a visually
             hidden radio inside a label the size of a card. */
          if (cs.display === 'inline'
              && el.closest('p,li,blockquote,figcaption')) return;
          if (el.matches('input') && el.closest('label')) return;
          if (box.height < min || box.width < min) {
            out.push(Math.round(box.width) + 'x' + Math.round(box.height) + ' '
              + el.tagName + '.'
              + (String(el.className) || el.parentElement.className).slice(0, 18));
          }
        });
        return [...new Set(out)];
      }, TARGET_MIN);
      await page.close();
      check(url + ' has nothing too small to press', !small.length,
            small.length ? small.length + ' under ' + TARGET_MIN + 'px: '
              + small.slice(0, 2).join(' | ') : 'all at least ' + TARGET_MIN + 'px');
    }
    await touch.close();

    /* ---- pass five: how long a line of prose gets ------------------------ */
    for (const url of PAGES) {
      const page = await browser.newPage({viewport: {width: 1440, height: 900}});
      await page.goto(base + url, {waitUntil: 'networkidle'});
      const long = await page.evaluate((cap) => {
        /* Measured in average lowercase letters, not CSS ch. `ch` is the width
           of a zero, which in this serif is 1.09x the average letter, so a rule
           saying max-width:72ch produces 78 characters of prose and a rule
           saying 44em produces 96. The number that matters is the one a reader
           actually crosses. */
        const probe = document.createElement('span');
        probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre';
        document.body.appendChild(probe);
        const over = [];
        document.querySelectorAll('p,li,blockquote,dd').forEach(el => {
          const text = [...el.childNodes]
            .filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
          if (text.split(/\s+/).length < 14) return;   // a label is not prose
          const cs = getComputedStyle(el);
          if (+cs.opacity < 0.9 || cs.visibility === 'hidden') return;
          const box = el.getBoundingClientRect();
          if (!box.width) return;
          probe.style.font = cs.font;
          probe.style.letterSpacing = cs.letterSpacing;
          probe.textContent = 'abcdefghijklmnopqrstuvwxyz';
          const per = probe.getBoundingClientRect().width / 26;
          const ch = Math.round(box.width / per);
          if (ch > cap) {
            over.push(ch + 'ch — ' + el.tagName + '.'
              + (String(el.className) || el.parentElement.className).slice(0, 20)
              + ' [' + text.slice(0, 22) + ']');
          }
        });
        probe.remove();
        return [...new Set(over)];
      }, MEASURE_CAP);
      await page.close();
      check(url + ' keeps its prose to a readable line', !long.length,
            long.length ? long.length + ' over ' + MEASURE_CAP + 'ch: '
              + long.slice(0, 2).join(' | ') : 'all within ' + MEASURE_CAP + 'ch');
    }

    /* ---- pass four: nothing runs off the side ---------------------------- */
    for (const url of PAGES) {
      const wrong = [];
      for (const width of WIDTHS) {
        const page = await browser.newPage({viewport: {width, height: 900}});
        await page.goto(base + url, {waitUntil: 'networkidle'});
        const seen = await page.evaluate(() => {
          const over = document.documentElement.scrollWidth - window.innerWidth;
          if (over <= 1) return null;
          const who = [];
          document.querySelectorAll('body *').forEach(el => {
            const box = el.getBoundingClientRect();
            if (box.right > window.innerWidth + 1 && box.width > 30
                && getComputedStyle(el).position !== 'fixed') {
              who.push(el.tagName + '.' + String(el.className).slice(0, 18));
            }
          });
          return {over, who: who.slice(0, 2)};
        });
        await page.close();
        if (seen) wrong.push(width + 'px +' + seen.over + ' [' + seen.who.join(', ') + ']');
      }
      check(url + ' fits every screen from 320 to 1920', !wrong.length,
            wrong.slice(0, 2).join(' | '));
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
