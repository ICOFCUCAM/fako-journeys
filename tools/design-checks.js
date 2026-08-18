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
const SURFACES = [
  {url: '/index.html',              name: 'the homepage',        cards: 4},
  {url: '/trans-afrique.html',      name: 'Trans Afrique',       cards: 2},
  {url: '/trans-afrique/east.html', name: 'a crossing',          cards: 1},
  {url: '/atlas.html',              name: 'the atlas',           cards: 2},
  {url: '/journey.html',            name: 'the journey builder', cards: 1},
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

  /* -> [r,g,b,a] on bytes and a 0..1 alpha, from any of the three shapes
     Chromium hands back: rgb(), rgba(), and color(srgb f f f / a). */
  function rgba(s){
    if(!s) return null;
    var m = String(s).match(/[\\d.]+/g);
    if(!m) return null;
    var v = m.slice(0,3).map(Number);
    if(/^color\\(/.test(s)) v = v.map(function(x){ return Math.round(x*255); });
    v.push(m.length > 3 ? +m[3] : 1);
    return v;
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
      var bg = bytes(cs.backgroundColor);
      var paintedBg = (bgR && bgR[3] > 0.02) ? over(bgR, under) : null;
      var paintedFl = (flR && flR[3] > 0.02) ? over(flR, under) : null;
      if((isAccent(paintedBg) || isAccent(paintedFl)) && area > button){
        fills.push({sel: name(el), area: area,
          w: Math.round(r.width), h: Math.round(r.height),
          how: isAccent(paintedBg) ? 'background' : 'fill'});
      }

      /* ABSOLUTE TWO — nothing is a card. Four borders of one visible colour
         plus a fill that differs from the ground behind it. */
      var w4 = ['Top','Right','Bottom','Left'].map(function(s){
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
        await page.addScriptTag({content: SCAN});
        const r = await page.evaluate('__design(' + BUTTON + ')');
        r.fills.forEach(f => fills.push(Object.assign({at: w}, f)));
        if (r.cards > cards) { cards = r.cards; worst = r.worst; }
        await ctx.close();
      }

      const biggest = fills[0];
      check('no accent fill larger than a button on ' + surface.name,
        fills.length === 0,
        biggest
          ? fills.length + ' at 390/768/1440 — largest ' + biggest.sel + ' '
            + biggest.w + '×' + biggest.h + ' (' + biggest.area + 'px²) '
            + biggest.how + ' at ' + biggest.at
          : 'three widths, nothing painted over ' + BUTTON + 'px²');

      check('nothing new is a card on ' + surface.name,
        cards <= surface.cards,
        cards + ' of ' + surface.cards + ' allowed'
          + (worst ? ' — largest ' + worst.sel : '')
          + (cards < surface.cards
              ? ' — lower the allowance in tools/design-checks.js' : ''));
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
