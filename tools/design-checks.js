/* The two absolutes from the design blueprint, measured in a browser.
 *
 *     node tools/design-checks.js    (or: python3 tools/tourism/build.py test)
 *
 * The blueprint states two rules and calls them absolutes, on the grounds that
 * they do most of the work on their own:
 *
 *     No accent fill larger than a button.
 *     Nothing is a card — no element carries a border on four sides plus a fill.
 *
 * Both are the kind of rule that is true on the day it is written and quietly
 * false a fortnight later, because every individual violation arrives with a
 * good local reason. A section needs a highlight; a panel needs to be told
 * apart from the panel beside it; a chip needs to look pressed. None of those
 * is wrong on its own and the sum of them is the site the blueprint was
 * written to stop.
 *
 * So they are measured rather than remembered, and measured the way a reader
 * meets them: rendered, at three widths, with the computed colour read off the
 * element rather than inferred from the stylesheet. A rule in a comment is a
 * preference. A rule with a number and a failing exit code is a rule.
 *
 * ---------------------------------------------------------------------------
 * WHAT COUNTS AS AN ACCENT FILL
 *
 * Burnt sienna and terracotta, within a tolerance, as a background or an SVG
 * fill on a box the reader can actually see. Not text — the blueprint is
 * explicit that the accent's job is "labels, rules, ordinals, links", so a
 * heading set in it is correct use and a continent painted in it is not.
 *
 * Two refinements, both of which the first run of this file earned by getting
 * them wrong.
 *
 * COMPOSITED, NOT DECLARED. The accent at six percent over ivory is a tint you
 * can barely find; the accent at forty-two percent over ivory is the atlas's
 * pale wash, which the blueprint names as already at the standard. Read as
 * declared they are both "an accent fill the size of a continent" and the
 * check condemns the two calmest surfaces on the site. Composited against the
 * ground behind them they are what the eye sees, which is a wash and a
 * whisper, and neither is a fill. Alpha is the difference between a mark and a
 * ground and the measurement has to respect it.
 *
 * THE FIVE REGION TONES ARE NOT THE ACCENT. North is #865A28 and sits nine,
 * twenty-five and zero away from burnt sienna per channel — inside any
 * tolerance loose enough to catch terracotta. They mean something different
 * ("where you are going", and the blueprint grants them map fills outright),
 * so they are excluded by exact value rather than by hoping a threshold can
 * separate two colours that a threshold cannot separate.
 *
 * ---------------------------------------------------------------------------
 * WHAT COUNTS AS A CARD
 *
 * Four borders of the same visible colour, plus a background that differs from
 * whatever is behind it. A bordered box on the page's own ground is not a card
 * — that is a rule drawn round something — and a filled box with no border is
 * a ground, which the blueprint asks for. It is the pair that makes an object
 * float, and it is the pair this checks for.
 *
 * The card rule is reported per surface rather than site-wide, because the
 * blueprint rebuilds the surfaces one at a time and a count that cannot fall
 * until the last one lands tells nobody anything. Every surface carries the
 * number it measured on the day its allowance was written; the number only
 * ever goes down, the check says so when a run comes in under it, and lowering
 * it is what "that surface is done" means. Set this way it is a ratchet from
 * today rather than a budget to spend: no surface may add a card, and every
 * surface the blueprint reaches should leave it lower than it found it.
 */
'use strict';

const fs = require('fs');
const http = require('http');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PORT = 8971;

/* A generous button: 220 × 56 with room to spare. Anything painted in the
   accent larger than this is a fill, whatever it calls itself. */
const BUTTON = 220 * 56;

/* The widths a reader meets: phone, tablet, laptop. The accent rule is width
   independent in the stylesheet and is not in the rendering — a slab that is
   a chip at 1440 is a full-bleed bar at 390, which is the third thing the
   blueprint's own step one names. */
const WIDTHS = [[390, 844], [768, 1024], [1440, 900]];

/* The surfaces, and what each is allowed to still be carrying. A number here
   is a debt, not a target: it is what that surface measured on the day its
   step in the blueprint had not been taken yet. When a surface is rebuilt its
   number goes to 0 and stays there. */
/* A ruled exception, not a hole in the rule.
 *
 * The hero continent is the object the blueprint names by hand — "never a fill
 * larger than a button, and never a continent" — and it is drawn in terracotta
 * anyway, because both renderings were built, put side by side and looked at,
 * and this is the one the company chose. That is a decision the direction does
 * not get to overrule; a design document is an argument, and an argument that
 * survives being tested against the thing itself is the only kind worth having.
 *
 * What it does not get to do is disappear. Written here it stays visible in
 * every run, it is scoped to the one selector on the one surface rather than
 * loosening the predicate for everybody, and the day the map changes again
 * this line is what says the exemption is spent. An unrecorded exception is
 * how a rule stops being a rule; a recorded one is how a rule survives being
 * overruled once.
 */
const WAIVED = [
  {url: '/index.html', sel: 'path.',
   why: 'the hero continent — terracotta chosen over the ink ladder, 18 August'},
  {url: '/index.html', sel: 'circle.',
   why: 'the island marks, which carry the continent’s own tier colour'}
];

const SURFACES = [
  {url: '/index.html',              name: 'the homepage',        cards: 4},
  {url: '/trans-afrique.html',      name: 'Trans Afrique',       cards: 2},
  {url: '/trans-afrique/east.html', name: 'a crossing',          cards: 1},
  {url: '/atlas.html',              name: 'the atlas',           cards: 2},
  /* AN ANSWERED STATE, NOT THE RESTING ONE.
     This page draws its continent unlit until somebody answers a question, so
     scanning it as it loads measures a surface nobody is looking at: the wash
     that lights thirty-one countries never gets measured at all. `prep` runs
     in the page before the scan and answers the first question.

     One lens, not six. Checking all of them lights the map no harder — one
     lens already washes thirty-one countries — and it presses six choice
     cards, each of which takes a fill and a border and is then counted as a
     card by the rule below. A pressed control is not a card, and the honest
     way to say so here is to put the page into a state a reader actually
     reaches rather than to teach the card rule an exception. */
  {url: '/journey.html',            name: 'the journey builder', cards: 1,
   prep: function () {
     var el = document.querySelector('[name="want"][value="nature"]')
           || document.querySelector('[name="want"]');
     if (!el) return;
     el.checked = true;
     el.dispatchEvent(new Event('change', {bubbles: true}));
   }},
  {url: '/journey-fund.html',       name: 'the journey fund',    cards: 2},
  {url: '/uganda.html',             name: 'a country',           cards: 0},
  {url: '/how-it-works.html',       name: 'how it works',        cards: 0}
];

const TYPES = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
  '.webp': 'image/webp', '.avif': 'image/avif', '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2', '.json': 'application/json',
  '.webmanifest': 'application/json', '.mp4': 'video/mp4', '.ico': 'image/x-icon'
};

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}
function done(code) {
  process.stdout.write(out.join('\n') + '\n');
  process.exit(code);
}

function chromium() {
  const roots = [
    '/opt/node22/lib/node_modules/playwright/node_modules/playwright-core',
    path.join(ROOT, 'node_modules', 'playwright-core'),
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
  const flat = path.join(base, 'chromium');
  return fs.existsSync(flat) ? flat : null;
}

function serve() {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      let file = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
      try {
        if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
      } catch (e) {
        if (fs.existsSync(file + '.html')) file += '.html';
      }
      fs.readFile(file, (err, body) => {
        if (err) { res.writeHead(404); res.end('no'); return; }
        res.writeHead(200, {
          'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream'
        });
        res.end(body);
      });
    });
    server.listen(PORT, () => resolve(server));
  });
}

/* Read in the page, because the only colour that matters is the one the
   compositor arrived at. color-mix(), currentColor, a variable redefined three
   selectors deep and an inherited fill all resolve here and nowhere else.
   Chromium reports mixed colours as `color(srgb 0.1 0.2 0.3)`, on fractions
   rather than bytes, which is the shape that has silently broken every
   ad-hoc contrast script written against this site. Handled once, here. */
const SCAN = `(function(){
  var ACCENT = [[143,65,40],[201,106,69],[203,111,75]];  /* accent, fill, lit */
  var REGION = [[17,50,34],[43,110,94],[103,46,29],[134,90,40],[26,81,81]];
  var TOL = 30;
  var PAPER = [246,241,231];   /* the page, when nothing above it is opaque */

  /* -> [r,g,b,a] on bytes and a 0..1 alpha, from ANY colour syntax.
     This was a regex over the three shapes Chromium was known to hand back —
     rgb(), rgba() and color(srgb f f f / a) — and it was one syntax behind the
     browser. color-mix(in srgb, ...) on an SVG fill computes to oklab() here,
     which the regex read as three numbers under 1 and called a near-black: a
     wash that could have been a flood fill and the check would not have known
     the difference. It passed, and it passed by accident.

     Painted instead of parsed. A 1x1 canvas accepts every syntax the engine
     accepts, including the ones that do not exist yet, and getImageData
     reports what was actually put on the pixel. An unparseable value leaves
     the transparent ground untouched and comes back at alpha 0, which is the
     safe failure: no paint rather than a wrong colour. */
  var _c = document.createElement('canvas');
  _c.width = _c.height = 1;
  var _x = _c.getContext('2d', {willReadFrequently: true});
  function rgba(s){
    if(!s || s === 'none' || s === 'transparent') return null;
    _x.clearRect(0,0,1,1);
    _x.fillStyle = 'rgba(0,0,0,0)';
    try { _x.fillStyle = s; } catch(e) { return null; }
    _x.fillRect(0,0,1,1);
    var d = _x.getImageData(0,0,1,1).data;
    if(!d[3]) return null;
    return [d[0], d[1], d[2], d[3]/255];
  }
  /* Alpha does not only live in the colour. fill-opacity and opacity paint the
     same wash and report a solid colour, which is the documented way text has
     slipped past the contrast checks on this site before. Folded in here so a
     fill cannot be hidden behind a property the predicate does not read. */
  function alphaOf(cs, key){
    var a = parseFloat(cs[key]);
    var o = parseFloat(cs.opacity);
    return (isNaN(a) ? 1 : a) * (isNaN(o) ? 1 : o);
  }
  function over(f, b){
    var a = f[3];
    return [0,1,2].map(function(i){ return Math.round(f[i]*a + b[i]*(1-a)); });
  }
  function exact(c, list){
    return list.some(function(t){
      return c[0]===t[0] && c[1]===t[1] && c[2]===t[2]; });
  }
  function isAccent(c){
    if(!c) return false;
    if(exact(c, REGION)) return false;
    return ACCENT.some(function(t){
      return Math.abs(c[0]-t[0]) <= TOL
          && Math.abs(c[1]-t[1]) <= TOL
          && Math.abs(c[2]-t[2]) <= TOL;
    });
  }
  function same(a,b){
    if(!a || !b) return false;
    return a[0]===b[0] && a[1]===b[1] && a[2]===b[2];
  }
  function bytes(s){
    var c = rgba(s);
    return (c && c[3] >= 0.999) ? c.slice(0,3) : null;
  }
  /* An element only counts if it is on screen somewhere in the document, not
     merely in the layout: the hero stacks thirteen window states on top of
     each other and twelve of them are at opacity 0 on an ancestor. */
  function shown(el){
    var n = el;
    while(n && n !== document.documentElement){
      var cs = getComputedStyle(n);
      if(cs.display === 'none' || cs.visibility === 'hidden') return false;
      if(+cs.opacity < 0.06) return false;
      n = n.parentElement;
    }
    return true;
  }
  function ground(el){
    var n = el.parentElement;
    while(n){
      var b = bytes(getComputedStyle(n).backgroundColor);
      if(b) return b;
      n = n.parentElement;
    }
    return null;
  }
  function name(el){
    return el.tagName.toLowerCase()
      + '.' + String(el.getAttribute('class') || '').split(' ')[0];
  }

  window.__design = function(button){
    var fills = [], cards = 0, worst = null;
    var els = document.querySelectorAll('body *, svg *');
    for(var i = 0; i < els.length; i++){
      var el = els[i], cs = getComputedStyle(el);
      var r = el.getBoundingClientRect();
      if(r.width < 2 || r.height < 2) continue;
      if(!shown(el)) continue;
      var area = Math.round(r.width * r.height);

      /* ABSOLUTE ONE — no accent fill larger than a button, judged on what the
         compositor arrives at rather than on what the declaration says. */
      var under = ground(el) || PAPER;
      var bgR = rgba(cs.backgroundColor);
      var flR = (cs.fill && cs.fill !== 'none') ? rgba(cs.fill) : null;
      /* The alpha the pixel actually gets, not the alpha the colour declares:
         the element's own opacity multiplies both, and fill-opacity multiplies
         the fill again. Without this a solid accent at fill-opacity .34 reads
         as a solid accent and a wash reads as a flood. */
      var own = parseFloat(cs.opacity);
      own = isNaN(own) ? 1 : own;
      if(bgR) bgR[3] = Math.min(1, bgR[3] * own);
      if(flR) flR[3] = Math.min(1, flR[3] * alphaOf(cs, 'fillOpacity'));
      var bg = bytes(cs.backgroundColor);
      var paintedBg = (bgR && bgR[3] > 0.02) ? over(bgR, under) : null;
      var paintedFl = (flR && flR[3] > 0.02) ? over(flR, under) : null;
      if((isAccent(paintedBg) || isAccent(paintedFl)) && area > button){
        fills.push({sel: name(el), area: area,
          w: Math.round(r.width), h: Math.round(r.height),
          how: isAccent(paintedBg) ? 'background' : 'fill'});
      }

      /* ABSOLUTE TWO — nothing is a card. Four borders of one visible colour
         plus a fill that differs from the ground behind it.

         A PRESSED CONTROL IS NOT A CARD. The box that says "you chose this
         one" takes a border and a fill for as long as the choice stands, and
         that is what a pressed control looks like in every medium including
         paper. Counting it makes the ratchet unusable for any page with
         choices on it — answer a question and the surface has grown a card.
         Recognised by the state rather than by the class name: the element is
         inside a label whose input is checked, or carries aria-checked
         itself. Unchecked, the same element is measured like everything else,
         so a design that ships four filled boxes cannot hide behind this. */
      var lab = el.closest ? el.closest('label') : null;
      var pressed = (lab && lab.querySelector('input:checked'))
        || el.getAttribute('aria-checked') === 'true'
        || (el.closest && el.closest('[aria-checked="true"]'));
      var w4 = pressed ? [0,0,0,0] : ['Top','Right','Bottom','Left'].map(function(s){
        return parseFloat(cs['border' + s + 'Width']) || 0; });
      if(w4.every(function(x){ return x >= 0.5; })){
        var c4 = ['Top','Right','Bottom','Left'].map(function(s){
          return bytes(cs['border' + s + 'Color']); });
        if(c4.every(Boolean) && same(c4[0],c4[1]) && same(c4[1],c4[2])
           && same(c4[2],c4[3]) && bg && !same(bg, ground(el))){
          cards++;
          if(!worst || area > worst.area) worst = {sel: name(el), area: area};
        }
      }
    }
    fills.sort(function(a,b){ return b.area - a.area; });
    return {fills: fills, cards: cards, worst: worst};
  };

  /* ABSOLUTE THREE — NO LINE OF TYPE REACHES THE WINDOW'S EDGE.
     Pictures bleed on this site and words do not. The frame's padding is the
     margin of the whole document and a line that starts outside it does not
     read as a deliberate exception; it reads as a bug, because on every other
     line the reader has met, it was one.

     Measured on the text, not on the box. This section deliberately bleeds the
     photograph's own <figure> to the window and hands its caption the frame's
     padding back by hand, so the caption's ELEMENT begins at x=0 at every
     width below 900 while its TEXT begins at 44 with everything else. A
     predicate written against getBoundingClientRect calls that a defect at
     five widths and is wrong at all five — which is exactly what a scratch
     sweep did before this was written, and why the check that survives is the
     one that walks text nodes and reads their Range rectangles.

     Scoped to the section rather than the document: a site-wide version of
     this would need a waiver list for every deliberate bleed on eight
     surfaces, and a rule with a waiver list per surface is a rule nobody
     reads. Here it guards the one composition that bleeds a box carrying
     words. */
  window.__inset = function(sel){
    var sec = document.querySelector(sel);
    if(!sec) return {ok:false, why:'no ' + sel + ' on the page'};
    var frame = sec.querySelector('.wa-frame') || sec;
    var fb = frame.getBoundingClientRect(), fcs = getComputedStyle(frame);
    var left  = fb.left  + parseFloat(fcs.paddingLeft);
    var right = fb.right - parseFloat(fcs.paddingRight);
    var bad = [], lines = 0;
    var tw = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
    var n;
    while((n = tw.nextNode())){
      if(!n.nodeValue.trim()) continue;
      var host = n.parentElement;
      if(!host || !shown(host)) continue;
      if(host.closest('svg')) continue;      /* map labels live in viewBox units */
      var rg = document.createRange();
      rg.selectNodeContents(n);
      var rects = rg.getClientRects();
      for(var j = 0; j < rects.length; j++){
        var rc = rects[j];
        if(rc.width < 1 && rc.height < 1) continue;
        lines++;
        if(rc.left < left - 1 || rc.right > right + 1){
          bad.push(name(host) + ' ' + Math.round(rc.left) + '..'
            + Math.round(rc.right));
        }
      }
    }
    return {ok: bad.length === 0, lines: lines, bad: bad.slice(0,3),
      count: bad.length, left: Math.round(left), right: Math.round(right)};
  };
}())`;

(async function () {
  const launcher = chromium();
  const exe = browserPath();
  if (!launcher || !exe) {
    check('the design checks ran', false,
      launcher ? 'no browser under PLAYWRIGHT_BROWSERS_PATH'
               : 'playwright-core not installed');
    done(1);
  }

  const server = await serve();
  let browser = null;
  try {
    browser = await launcher.launch({executablePath: exe});

    for (const surface of SURFACES) {
      /* One context per width. Sharing one and resizing leaves the previous
         width's layout in the SVG viewBox the map was flown to. */
      let fills = [], cards = 0, worst = null;
      for (const [w, h] of WIDTHS) {
        const ctx = await browser.newContext({viewport: {width: w, height: h}});
        const page = await ctx.newPage();
        await page.goto('http://127.0.0.1:' + PORT + surface.url,
          {waitUntil: 'load'});
        await page.waitForTimeout(1200);
        if (surface.prep) {
          await page.evaluate(surface.prep);
          await page.waitForTimeout(500);
        }
        await page.addScriptTag({content: SCAN});
        const r = await page.evaluate('__design(' + BUTTON + ')');
        r.fills.forEach(f => fills.push(Object.assign({at: w}, f)));
        if (r.cards > cards) { cards = r.cards; worst = r.worst; }
        await ctx.close();
      }

      /* Split into what has been argued about and what has not. The waived
         ones are still counted and still printed — an exception nobody can see
         in the output is the same as no rule at all. */
      const waivers = WAIVED.filter(w => w.url === surface.url);
      const waived = fills.filter(f => waivers.some(w => w.sel === f.sel));
      const loose = fills.filter(f => !waivers.some(w => w.sel === f.sel));
      const biggest = loose[0];
      check('no unwaived accent fill larger than a button on ' + surface.name,
        loose.length === 0,
        (biggest
          ? loose.length + ' at 390/768/1440 — largest ' + biggest.sel + ' '
            + biggest.w + '×' + biggest.h + ' (' + biggest.area + 'px²) '
            + biggest.how + ' at ' + biggest.at
          : 'three widths, nothing painted over ' + BUTTON + 'px²')
        + (waived.length
            ? ' — ' + waived.length + ' waived: '
              + waivers.map(w => w.why).join('; ')
            : ''));

      check('nothing new is a card on ' + surface.name,
        cards <= surface.cards,
        cards + ' of ' + surface.cards + ' allowed'
          + (worst ? ' — largest ' + worst.sel : '')
          + (cards < surface.cards
              ? ' — lower the allowance in tools/design-checks.js' : ''));
    }

    /* Absolute three, over the section's own bands rather than the three
       widths above: the composition changes shape at 560, 680, 900 and 1100
       and the bled figure only exists below 900, so the widths that matter are
       the ones either side of each of those. */
    {
      const bands = [320, 390, 560, 680, 768, 900, 1100, 1440];
      const trouble = [];
      let lines = 0;
      for (const w of bands) {
        const ctx = await browser.newContext({viewport: {width: w, height: 900}});
        const page = await ctx.newPage();
        await page.goto('http://127.0.0.1:' + PORT + '/index.html',
          {waitUntil: 'load'});
        await page.waitForTimeout(700);
        await page.addScriptTag({content: SCAN});
        const r = await page.evaluate('__inset(".wa-fund")');
        lines += r.lines || 0;
        if (!r.ok) {
          trouble.push(w + ': ' + (r.why || r.count + ' outside '
            + r.left + '..' + r.right + ' — ' + r.bad.join(', ')));
        }
        await ctx.close();
      }
      check('no line of type reaches the window on the journey fund door',
        trouble.length === 0,
        trouble.length ? trouble.join(' | ')
          : lines + ' text rectangles across eight widths, every one inside '
            + 'the frame');
    }
  } catch (e) {
    check('the design checks ran', false, String(e.message).slice(0, 90));
    console.error('\n--- full stack ---\n' + (e.stack || e));
  } finally {
    if (browser) await browser.close();
    server.close();
  }
  done(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
}());
