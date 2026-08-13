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
                     [1180, 820], [960, 760], [900, 700], [390, 844], [320, 700],
                     /* Short windows, which are a different axis and were not
                        covered by any of the above. A browser at half a screen,
                        a laptop carrying two toolbars, and 1440x900 at 200%
                        zoom — which is 720x450 CSS pixels and is the shape WCAG
                        1.4.4 asks a page to survive. At 1440x500 the map was
                        96x102 inside a 707-pixel stage before 080. */
                     [1440, 500], [1920, 540], [1280, 600], [720, 450]];
/* The map has to stay big enough to pick a country out of, at every shape. */
const HERO_MAP_MIN = 240;

/* Pass nine walks a few pages with prefers-reduced-motion on. The gateway is
   the one with a cross-fade in it; the others are here because a delay left
   behind by a removed animation is not a hero-specific mistake. */
const REDUCED_PAGES = ['/index.html', '/atlas.html', '/kenya.html', '/meet.html'];
const HERO_BLEED = 190;
const HERO_BAND = 200;

/* 101 made the continent the first screen. What that means as a number: the
   ink — the drawn continent, not the viewBox around it — fills the stage from
   the masthead's lower edge to the foot, at every desktop width. Sized from
   the frame instead it rides up behind a fixed masthead and loses Morocco.
   HERO_INK_MIN is the share of the *screen* the continent has to hold — the
   viewport less the masthead, not the stage. The stage is content-tall and on a
   short window it is taller than the screen, so measuring against it reported
   38% at 1440x500 for a map that was filling every pixel available to it.
   Below this threshold the map has gone back to being an object in the corner
   and the composition this hero is built on has quietly reverted. */
const HERO_INK_MIN = 0.78;
const HERO_INK_TOP = 12;   // px the continent's top may sit off the masthead line

/* Pass ten. AFRICA is set at 213px, which is large text, so WCAG 1.4.3 asks
   3:1 — but a headline this size carries the page and 3:1 is the floor for
   reading a word, not for a word being the composition. 4.5 is the number the
   rest of this site is held to and there is no reason for the largest type on
   it to be the exception. */
const HERO_TYPE_WIDTHS = [[1920, 1080], [1440, 900], [1366, 768]];
const HERO_TYPE_MIN = 4.5;

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
    /* ---- pass nine: the same page with the motion turned off ------------ */
    /*
     * Reduced motion is a setting, not a rendering mode, and a page can be
     * correct in one and wrong in the other. This one was: the hero holds a
     * hidden caption out of the tab order with `visibility 0s linear .45s`, a
     * delay sized to cover an opacity fade, and the reduced-motion block zeroes
     * durations without touching delays. So the fade went away, the delay did
     * not, and for 450ms after every selection there was an invisible,
     * focusable link in the hero — under the one setting chosen by people who
     * are least able to tolerate a page that misbehaves.
     *
     * PASS SEVEN walks the tab order and would have caught it in a second. It
     * runs with motion on, so it never has.
     */
    {
      const rm = await browser.newContext({viewport: {width: 1280, height: 900},
                                           reducedMotion: 'reduce'});
      for (const url of REDUCED_PAGES) {
        const page = await rm.newPage();
        await page.goto(base + url, {waitUntil: 'networkidle'});
        /* Move through whatever states the page has, then look for anything
           that is invisible and still reachable. Selecting is what triggers a
           cross-fade, and a cross-fade is where the delays live. */
        const ghosts = await page.evaluate(async () => {
          const pick = [...document.querySelectorAll('.wa-tick, .wa-reg, [data-slug]')]
            .filter(el => typeof el.click === 'function').slice(0, 3);
          const seen = new Set();
          const sweep = () => {
            document.querySelectorAll('body *').forEach(el => {
              const cs = getComputedStyle(el);
              if (cs.visibility === 'hidden' || cs.display === 'none') return;
              if (+cs.opacity >= 0.05) return;
              const box = el.getBoundingClientRect();
              if (box.width < 2 || box.height < 2) return;
              /* Only things a keyboard can land on. */
              const hot = el.matches('a[href],button,input,select,textarea,[tabindex]')
                || el.querySelector('a[href],button,input,select,textarea');
              if (hot) seen.add(el.tagName + '.' + String(el.className || '').slice(0, 22));
            });
          };
          sweep();
          for (const el of pick) {
            el.click();
            await new Promise(r => setTimeout(r, 120));
            sweep();
            await new Promise(r => setTimeout(r, 260));
            sweep();
          }
          return [...seen];
        });
        await page.close();
        check(url + ' hides nothing it can still focus, with motion off',
              !ghosts.length,
              ghosts.length ? ghosts.length + ' invisible and reachable: '
                              + ghosts.slice(0, 2).join(', ') : 'nothing reachable is invisible');
      }
      await rm.close();
    }

    /* ---- pass ten: the word over the continent --------------------------- */
    /*
     * 101 set AFRICA across the map instead of beside it. That is the whole
     * composition, and it puts a charcoal headline on top of whatever the map
     * happens to be drawing underneath — which includes the operator tier,
     * deep forest, where charcoal measures 1.09:1 and the word simply stops
     * existing.
     *
     * It does not currently happen, and the reason it does not is luck rather
     * than design. Pressing East Africa puts Cameroon under the headline at
     * 1440, 1920 and 1366; pressing Islands puts Uganda there. Both are legible
     * only because 090 paints a country outside the chosen region in a
     * lightened fill rather than dimming it with opacity, which lifts the real
     * measured contrast to 5.95:1. Change how dimming works and the headline
     * disappears at two of six region views, on a page where every other
     * contrast is checked.
     *
     * So it is checked where it is actually decided: sample the fill of every
     * map shape the headline's glyphs cross, in every region view, and measure
     * the headline's ink against it.
     */
    for (const [w, h] of HERO_TYPE_WIDTHS) {
      const page = await browser.newPage({viewport: {width: w, height: h}});
      await page.goto(base + '/index.html', {waitUntil: 'networkidle'});
      const bad = await page.evaluate(async (need) => {
        function lum(c) {
          const f = c.map(v => (v /= 255) <= 0.03928 ? v / 12.92
                                                     : Math.pow((v + 0.055) / 1.055, 2.4));
          return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
        }
        function parse(text) {
          let m = text.match(/color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)/);
          if (m) return [+m[1] * 255, +m[2] * 255, +m[3] * 255];
          m = text.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)/);
          return m ? [+m[1], +m[2], +m[3]] : null;
        }
        function ratio(a, b) {
          const x = lum(a), y = lum(b);
          return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
        }
        const big = document.querySelector('.wa-h1-big');
        const regs = [...document.querySelectorAll('.wa-reg')];
        if (!big || !regs.length) return [];
        const ink = parse(getComputedStyle(big).color);
        const out = [];
        for (const reg of regs) {
          reg.click();
          await new Promise(r => setTimeout(r, 900));
          const range = document.createRange();
          range.selectNodeContents(big);
          const t = range.getBoundingClientRect();
          document.querySelectorAll('.wa-map-live, .wa-map-rest path').forEach(el => {
            const b = el.getBoundingClientRect();
            if (!b.width || !b.height) return;
            const x = Math.min(t.right, b.right) - Math.max(t.left, b.left);
            const y = Math.min(t.bottom, b.bottom) - Math.max(t.top, b.top);
            /* A sliver of a country clipping a serif is not the headline
               sitting on it; this wants real overlap. */
            if (x < 12 || y < 12) return;
            const paint = el.tagName === 'path' ? el : el.querySelector('path');
            if (!paint) return;
            const fill = parse(getComputedStyle(paint).fill);
            if (!fill) return;
            const got = ratio(ink, fill);
            if (got + 0.005 < need) {
              out.push(reg.dataset.reg + ': the headline is '
                + (Math.round(got * 100) / 100) + ':1 over '
                + (el.dataset && el.dataset.name ? el.dataset.name : 'the map'));
            }
          });
        }
        return [...new Set(out)];
      }, HERO_TYPE_MIN);
      await page.close();
      check('the headline reads wherever the map puts itself, at ' + w,
            !bad.length,
            bad.length ? bad.slice(0, 2).join(' | ') : 'legible in all six region views');
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
      const seen = await page.evaluate(([bleed, band, mapMin, inkMin, inkTop]) => {
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

        /* The continent is the first screen. Measured on the drawn ink via
           getBBox rather than on the frame, because the frame is a viewBox with
           ocean in it and 101's whole point is that those are different boxes. */
        const mapSvg = q('.wa-map-svg');
        const stage0 = B('.wa-open-stage'), win0 = B('.wa-win');
        if (mapSvg && stage0 && win0 && say && !(win0.left < say.right - 8)) {
          let bb = null;
          try { bb = mapSvg.getBBox(); } catch (e) { /* not rendered */ }
          const vb = mapSvg.viewBox && mapSvg.viewBox.baseVal;
          const box = mapSvg.getBoundingClientRect();
          if (bb && vb && vb.height && bb.height) {
            const k = Math.min(box.width / vb.width, box.height / vb.height);
            const top = box.top + (box.height - vb.height * k) / 2 + (bb.y - vb.y) * k;
            const inkH = bb.height * k;
            const mast = parseFloat(getComputedStyle(document.documentElement)
                           .getPropertyValue('--mast')) || 78;
            /* The lesser of the screen and the stage. 066 caps the stage so a
               very tall monitor gets a composition rather than a stretched one,
               and the continent fills the stage rather than the screen there —
               at 2560x1440 that is 820 of an 897-pixel stage, which is right,
               and 60% of the viewport, which would read as a fault. */
            const room = Math.min(window.innerHeight - mast, stage0.height);
            const share = inkH / room;
            if (share < inkMin) {
              bad.push('the continent is ' + Math.round(share * 100)
                       + '% of the room it has, wants ' + Math.round(inkMin * 100) + '%');
            }
            if (Math.abs(top - mast) > inkTop) {
              bad.push('the continent starts ' + Math.round(top - mast)
                       + 'px off the masthead line');
            }
          }
        }

        /* The frame is the continent's box. Letterboxing inside it is the
           bleed being eaten by empty space nobody can see. */
        const svg = B('.wa-map-svg');
        if (svg && svg.width && svg.height) {
          const k = Math.min(svg.width / 1000, svg.height / 1060);
          const slack = Math.round(Math.max(svg.width - 1000 * k, svg.height - 1060 * k));
          if (slack > 8) bad.push(slack + 'px of letterbox around the map');
          /* And it is still a map. Sized off the viewport while the stage sizes
             off its own content, it collapsed to 102px tall inside a 707px
             stage on a short window — small enough that the countries stop
             being things a pointer can hit. */
          if (svg.height < mapMin) {
            bad.push('the map is ' + Math.round(svg.width) + 'x' + Math.round(svg.height)
              + ' in a ' + Math.round(B('.wa-open-stage').height) + 'px stage');
          }
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

        /* The hero's type is one scale, and every step in it is a proportion
           of the headline rather than of the window. Three of these were
           independently clamped on vw before 072 and 079, and the ratios they
           produced drifted with the viewport: the qualifying line ran 0.243 at
           1440 and 0.253 at 1920, and the map's caption collapsed to 0.136 at
           768 where the headline is at its largest. Checked only above the
           phone floors, which deliberately break the ratio to keep small type
           readable. */
        const fs = s => { const e = q(s); return e ? parseFloat(getComputedStyle(e).fontSize) : 0; };
        const head = fs('.wa-h1-big');
        /* Above the width at which the last of the three floors stops binding.
           They are 26, 17 and 26 against ratios of .244, .141 and .178, so the
           map's caption is the last to come off its floor, at a headline of
           146px. Below that the clamps are deliberately breaking the ratio to
           keep small type readable and there is nothing here to assert. */
        if (head > 150) {
          const steps = [['.wa-h1-rest', 0.244], ['.wa-find', 0.141],
                         ['.wa-win-cap[data-on] b', 0.178]];
          for (const [sel, want] of steps) {
            const got = fs(sel) / head;
            if (!got) continue;
            if (Math.abs(got - want) > 0.006) {
              bad.push(sel + ' is ' + got.toFixed(3) + ' of the headline, wants ' + want);
            }
          }
        }

        /* The map argues three things with three colours, and it has to go on
           doing that in every state it has. Two ways it stopped: the land was
           1.19:1 against the page, so the continent itself was not one of the
           three; and hover filled every tier the same sienna, so pointing at an
           operator produced a destination. Both were invisible in a screenshot
           of the default view, which is the only view anything else checks. */
        const L = c => {
          const n = (c.match(/[\d.]+/g) || []).map(Number);
          if (n.length < 3) return null;
          const f = v => { v = v > 1 ? v / 255 : v;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
          return 0.2126 * f(n[0]) + 0.7152 * f(n[1]) + 0.0722 * f(n[2]);
        };
        const CR = (a, b) => { const x = L(a), y = L(b);
          return (x == null || y == null) ? null : (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
        const land = q('.wa-map-rest path');
        if (land) {
          const lf = getComputedStyle(land).fill;
          const page = getComputedStyle(document.body).backgroundColor;
          const r = CR(lf, page);
          /* The coastline has to be a coastline. */
          if (r != null && r < 1.35) bad.push('the land is ' + r.toFixed(2) + ':1 against the page');
          /* And a destination has to stay louder than the coast is. */
          const dest = q('.wa-map-live[data-tier="live"] path');
          if (dest) {
            const dr = CR(getComputedStyle(dest).fill, lf);
            if (dr != null && dr < r) bad.push('a destination is ' + dr.toFixed(2)
              + ':1 against the land, under the land\'s ' + r.toFixed(2) + ' against the page');
          }
        }
        /* The three tiers are three colours, in every state. */
        const tiers = ['rest', 'live', 'ours'];
        const fills = {};
        for (const t of tiers) {
          const el = t === 'rest' ? q('.wa-map-rest path')
                                  : q('.wa-map-live[data-tier="' + t + '"] path');
          if (el) fills[t] = getComputedStyle(el).fill;
        }
        if (Object.keys(fills).length === 3 && new Set(Object.values(fills)).size < 3) {
          bad.push('the map draws its three tiers in ' + new Set(Object.values(fills)).size + ' colours');
        }

        /* And the monospace voice is three settings, not seven. Counted over
           every element in the hero that holds its own words. */
        const mono = new Set();
        document.querySelectorAll('#window *').forEach(el => {
          const own = [...el.childNodes].filter(n => n.nodeType === 3)
            .map(n => n.textContent).join('').trim();
          if (!own) return;
          const cs = getComputedStyle(el);
          if (cs.fontFamily.indexOf('mono') < 0 && cs.fontFamily.indexOf('Mono') < 0) return;
          if (cs.visibility === 'hidden' || !el.getBoundingClientRect().width) return;
          mono.add(cs.fontSize + '/' + cs.letterSpacing);
        });
        if (mono.size > 3) bad.push('the mono voice has ' + mono.size
          + ' settings: ' + [...mono].sort().join(' '));

        /* And it stays inside the section it belongs to.
           This is the check 104 needed and did not have. The map grew until it
           was 1284px tall in an 897px stage and ran six hundred pixels down
           over the next section, drawing Namibia across its headline — and
           every assertion here passed, because the only thing being measured
           was the continent against the stage and the continent had swallowed
           the stage. Nothing in this hero clips, so overflowing it is silent:
           no scrollbar, no reflow, nothing PASS FOUR can see. */
        if (mapSvg && stage0) {
          /* The ink again, not the box. The frame is a viewBox with ocean in it
             and it legitimately hangs below the last of South Africa — measured
             on the box this flagged the *fixed* build at 75px while flagging
             the broken one at 580, which is a check that cannot tell the two
             apart. Run against a state known to be right and a state known to
             be wrong, it said the same thing about both. */
          let bb2 = null;
          try { bb2 = mapSvg.getBBox(); } catch (e) { /* not rendered */ }
          const vb2 = mapSvg.viewBox && mapSvg.viewBox.baseVal;
          const box2 = mapSvg.getBoundingClientRect();
          if (bb2 && vb2 && vb2.height && bb2.height) {
            const k2 = Math.min(box2.width / vb2.width, box2.height / vb2.height);
            const inkBottom = box2.top + (box2.height - vb2.height * k2) / 2
                              + (bb2.y - vb2.y + bb2.height) * k2;
            const spill = Math.round(inkBottom - stage0.bottom);
            if (spill > 8) bad.push('the map runs ' + spill + 'px past the foot of the hero');
          }
        }

        /* The readout's stack stays inside the stage it belongs to. */
        const stage = B('.wa-open-stage'), side = B('.wa-win-side');
        if (stage && side && side.bottom > stage.bottom + 2) {
          bad.push('the readout runs ' + Math.round(side.bottom - stage.bottom) + 'px past the stage');
        }
        return bad;
      }, [HERO_BLEED, HERO_BAND, HERO_MAP_MIN, HERO_INK_MIN, HERO_INK_TOP]);
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
