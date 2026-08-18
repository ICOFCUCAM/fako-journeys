/* Checks for the Journey Fund, run against the code and the data the page
 * actually ships.
 *
 *     node tools/fund-checks.js     (or: python3 tools/tourism/build.py test)
 *
 * Two kinds of check, and the split matters.
 *
 * THE ARITHMETIC is loaded from scripts/fund-math.js — the same module the
 * browser loads — and exercised against the payload read out of the built
 * page. Not a fixture: if the build shipped different numbers, these fail
 * here rather than passing against a copy only the test can see.
 *
 * THE PROMISES are checks on the finished HTML for things this product is not
 * allowed to do. No percentage anywhere in the interface, no "balance", no
 * figure larger than the destination's name, nothing that implies a rate of
 * return, no field that could collect a card. Those are constraints from the
 * approved creative direction and security model, and a constraint nobody can
 * fail is a preference. These can be failed.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const F = require(path.join(ROOT, 'scripts', 'fund-math.js'));

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

/* ---- the data the built page carries -------------------------------------- */

const LANDING = path.join(ROOT, 'journey-fund.html');
const HOW = path.join(ROOT, 'journey-fund', 'how-it-works.html');
const ASKED = path.join(ROOT, 'journey-fund', 'questions.html');

let page;
try {
  page = fs.readFileSync(LANDING, 'utf8');
} catch (e) {
  check('the landing page exists', false, 'run: build.py fund');
  process.stdout.write(out.join('\n') + '\n');
  process.exit(1);
}

const m = page.match(
  /<script type="application\/json" id="jf-data">([\s\S]*?)<\/script>/);
if (!m) {
  check('the built page carries the estimator data', false, 'no jf-data block');
  process.stdout.write(out.join('\n') + '\n');
  process.exit(1);
}
const D = JSON.parse(m[1]);

/* The rate card, read directly, so the page's copy can be compared against
   the source rather than against itself. */
const RATES = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'tourism', 'rates.json'), 'utf8'));

/* ---- the payload ---------------------------------------------------------- */

check('the payload carries every published country',
  D.countries.length >= 50,
  D.countries.length + ' countries');

check('every country in the payload names a region',
  D.countries.every(c => c.r && D.tones[c.r]),
  'and every region names a tone');

check('the crossings carry both ends of their band',
  D.routes.length > 0 && D.routes.every(r => r.lo > 0 && r.hi > r.lo),
  D.routes.length + ' crossings');

check('the tiers match tourism/rates.json exactly',
  D.tiers.length === RATES.tiers.length
    && D.tiers.every((t, i) => t.rate === RATES.tiers[i].rate
                            && t.id === RATES.tiers[i].id),
  D.tiers.map(t => t.id + ' ' + t.rate).join(', '));

check('the payload carries the rate card version',
  typeof D.v === 'string' && D.v.length === 12,
  D.v);

check('the payload is small enough to be on a first screen',
  m[1].length < 12000,
  (m[1].length / 1024).toFixed(1) + ' KB');

/* ---- the arithmetic -------------------------------------------------------- */

const sig = RATES.tiers.find(t => t.id === 'signature');
const seven = F.price(D, { kind: 'country', place: 'kenya', tier: 'signature', days: 7 });

check('a week of Signature is the rate card, times seven, plus arrival',
  seven.total === sig.rate * 7 + RATES.arrival.rate,
  '$' + sig.rate + ' x 7 + $' + RATES.arrival.rate + ' = $' + seven.total);

check('the figure the rhythm is worked out against is the whole journey',
  seven.plan === seven.total,
  'plan and total agree for a single country');

const band = F.price(D, { kind: 'crossing', place: D.routes[0].s });
check('a crossing is planned against the bottom of its band',
  band.band === true && band.plan === band.low && band.high > band.low,
  D.routes[0].s + ': ' + F.money(band.low) + ' to ' + F.money(band.high));

check('a crossing is never priced as a daily rate times its length',
  band.plan !== sig.rate * parseInt(D.routes[0].d, 10),
  'priced whole, as tourism/transafrique.json says it must be');

/* Months. `now` is passed in, so December can be tested in August. */
const AUG = new Date(2026, 7, 15);   /* August 2026 */
check('the month count is whole months, not part ones',
  F.monthsAhead('2027-8', AUG) === 12
    && F.monthsAhead('2026-9', AUG) === 1
    && F.monthsAhead('2026-8', AUG) === 0,
  'a month chosen inside the current one is zero, not one');

check('the month count crosses a year end correctly',
  F.monthsAhead('2027-1', new Date(2026, 10, 1)) === 2,
  'November to January is two');

check('a malformed month is null rather than a wrong number',
  F.monthsAhead('', AUG) === null
    && F.monthsAhead('2027-13', AUG) === null
    && F.monthsAhead('nonsense', AUG) === null);

/* The rhythm. */
const r12 = F.rhythm(4750, 12, 'monthly');
check('monthly is the journey divided by the months',
  Math.round(r12.per) === Math.round(4750 / 12) && r12.n === 12,
  F.money(r12.per) + ' a month over 12 months');

const q12 = F.rhythm(4750, 12, 'quarterly');
check('quarterly is the same total in fewer, larger amounts',
  q12.n === 4 && Math.round(q12.per * q12.n) === 4750,
  q12.n + ' x ' + F.money(q12.per));

check('a rhythm never reaches more than the journey costs',
  Math.abs(r12.per * r12.n - 4750) < 1 && Math.abs(q12.per * q12.n - 4750) < 1,
  'no rounding leak in either rhythm');

check('a month too close is a problem named, not an exception',
  F.rhythm(4750, 0, 'monthly').problem === 'toosoon'
    && F.rhythm(4750, 2, 'quarterly').problem === 'toosoonquarterly'
    && F.rhythm(4750, null, 'monthly').problem === 'nomonth');

check('no interest, growth or return is ever applied',
  F.rhythm(4750, 24, 'monthly').per * 24 === 4750,
  'the total put aside equals the journey exactly');

/* The doors offered when the figure is large. */
const doors = F.doors(D, seven, 6,
  { kind: 'country', days: 14, tier: 'bespoke' }, F.CEILING);
check('a figure that is hard to reach offers ways out, not a refusal',
  doors.length === 3 && doors.every(d => !/too much|cannot|afford/i.test(d)),
  doors.length + ' doors, none of them about the reader');

check('the cheapest journey at the longest horizon offers nothing extra',
  F.doors(D, seven, 27,
    { kind: 'country', days: D.days[0], tier: D.tiers[0].id },
    F.CEILING).length === 0,
  'the page says nothing rather than inventing an option');

/* ---- the promises ---------------------------------------------------------- */

const pages = [
  ['/journey-fund', page],
  ['/journey-fund/how-it-works', fs.readFileSync(HOW, 'utf8')],
  ['/journey-fund/questions', fs.readFileSync(ASKED, 'utf8')],
];

/* Text only: the JSON payload and the class names are not what a reader sees,
   and a check that reads them fails for the wrong reasons. */
function words(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&[a-z]+;/gi, ' ');
}

/* THE RULE IS ABOUT USE, NOT ABOUT OCCURRENCE, AND THE FIRST VERSION OF THIS
   CHECK GOT THAT WRONG.
 *
 * It banned the words outright and failed three pages — including the one
 * whose entire job is to say "this is not a savings account, there is no
 * balance and nothing to withdraw". A page cannot deny being something without
 * naming the thing, and a check that forces vaguer copy on the clearest page
 * on the site is a check working against its own purpose.
 *
 * So the rule is: this vocabulary may appear only inside an explicit denial.
 * "No balance" passes; "your balance" does not. Sentence by sentence, because
 * a denial two paragraphs away is not a denial of this sentence — with one
 * exception, which is that a heading may be answered by the line beneath it.
 * "Is this a savings account?" followed by "No, and no." is a denial written
 * the way people write; requiring the negation inside the question itself
 * would only produce worse headings. A sentence with no denial in it and none
 * after it still fails, which is the case that matters. */
const FORBIDDEN = [
  [/\bbalance\b/i, 'balance'],
  [/\bdeposit/i, 'deposit'],
  [/\bwithdraw/i, 'withdraw'],
  [/\bwallet\b/i, 'wallet'],
  [/\binterest\b/i, 'interest'],
  [/\bsavings\b/i, 'savings'],
];

const DENIAL = /\b(no|not|nothing|never|neither|nor|nowhere|none|without|cannot)\b/i;

function sentences(text) {
  return text.replace(/\s+/g, ' ').split(/(?<=[.?!])\s+/);
}

pages.forEach(function ([name, html]) {
  const text = words(html);
  const bare = [];
  const said = sentences(text);
  said.forEach(function (s, i) {
    const answered = DENIAL.test(s) || DENIAL.test(said[i + 1] || '');
    if (answered) return;
    FORBIDDEN.forEach(function ([re, word]) {
      if (re.test(s) && bare.indexOf(word) < 0) {
        bare.push(word + ' — in "' + s.trim().slice(0, 70) + '"');
      }
    });
  });
  check(name + ': this vocabulary appears only inside a denial',
    bare.length === 0,
    bare.length ? bare.join(' | ')
                : 'balance, deposit, withdraw, wallet, interest, savings — each denied or absent');
});

/* A percentage has no legitimate denial use: the product measures progress in
   days of journey, so a digit next to a per-cent sign is always the mistake. */
pages.forEach(function ([name, html]) {
  check(name + ': no percentage anywhere a reader can see',
    !/\d\s*%/.test(words(html)),
    'progress here is days of journey, never a proportion');
});

check('no page can collect a card, a bank detail or a password',
  pages.every(([, html]) =>
    !/type="password"/i.test(html)
    && !/\b(card ?number|cardnumber|cvv|cvc|iban|routing ?number|sort ?code)\b/i.test(html)),
  'no such field exists on any Journey Fund page');

/* The central promise of Phase 0, and it has to be on every page rather than
   on the one a reader might not reach. Checked as a denial of holding or
   charging rather than as a fixed phrase, so the copy can be rewritten without
   the guarantee quietly falling off. */
pages.forEach(function ([name, html]) {
  const said = sentences(words(html)).filter(s =>
    /\b(hold|holds|held|charge|charged|receive|receives)\b/i.test(s)
    && DENIAL.test(s));
  check(name + ': says in words that Afrinkong holds nothing',
    said.length > 0,
    said.length ? '"' + said[0].trim().slice(0, 72) + '"' : 'not stated');
});

/* The creative direction's one measurable typographic rule. */
const css = fs.readFileSync(path.join(ROOT, 'styles', 'fund.css'), 'utf8');
function ceilingOf(selector) {
  const rule = css.match(
    new RegExp(selector.replace('.', '\\.') + '\\s*\\{[^}]*\\}'));
  if (!rule) return null;
  const clamp = rule[0].match(/font-size:\s*clamp\([^,]+,[^,]+,\s*([\d.]+)px\)/);
  if (clamp) return parseFloat(clamp[1]);
  const px = rule[0].match(/font-size:\s*([\d.]+)px/);
  return px ? parseFloat(px[1]) : null;
}
const nameSize = ceilingOf('.jf-where');
const figureSize = ceilingOf('.jf-sum .jf-rule');
check('a figure is never larger than the destination it is for',
  nameSize && figureSize && figureSize < nameSize,
  'destination ' + nameSize + 'px, total ' + figureSize + 'px');

/* THE TONE IS SET AT RUN TIME, WHICH PUTS IT OUT OF REACH OF EVERY OTHER
   CHECK ON THIS SITE.
 *
 * browser-checks.js measures contrast as the page loads. On this page the
 * accent is whatever region the reader last chose, so five of the six colours
 * it can be are never on screen when anything is measuring — and the two that
 * failed, East at 4.48:1 and North at 4.47:1, failed on the most important
 * sentence on the page by two hundredths of a point.
 *
 * So every place the tone carries text is enumerated here and multiplied by
 * every tone the file can produce. Adding a sixth region, or moving a rule to
 * a smaller size, fails this before it reaches a browser. */
function luminance(hex) {
  const h = hex.replace('#', '');
  const c = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
    .map(v => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrast(a, b) {
  const l1 = luminance(a), l2 = luminance(b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

const REGIONS = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'tourism', 'regions.json'), 'utf8'));
const TONES = Object.keys(REGIONS)
  .filter(k => !k.startsWith('$'))
  .map(k => [k, REGIONS[k].tone]);

const IVORY = '#F6F1E7';   /* --c-bg   */
const SAND = '#E9DDCA';    /* --c-sand */

/* Every selector in styles/fund.css that paints text in var(--jf-tone), with
   the ground it sits on and the ratio that size demands. Kept by hand and
   asserted below to be complete, so a new one cannot be added silently. */
const TONED = [
  ['.jf-track b', IVORY, 4.5],
  ['.jf-chip input:checked+span', IVORY, 4.5],
  ['.jf-tier input:checked+span b', IVORY, 4.5],
  ['.jf-reach b', IVORY, 4.5],
  ['.jf-kept-note', IVORY, 4.5],
  ['.jf-where', SAND, 3.0],
];

const dim = [];
TONED.forEach(function ([sel, ground, need]) {
  TONES.forEach(function ([region, tone]) {
    const r = contrast(tone, ground);
    if (r < need) {
      dim.push(sel + ' in ' + region + ' = ' + r.toFixed(2) + ':1, needs ' + need);
    }
  });
});
check('every region tone clears AA everywhere it carries text',
  dim.length === 0,
  dim.length ? dim.join(' | ')
             : TONED.length + ' selectors x ' + TONES.length + ' regions, all clear');

/* Boundaries, not text: a chip's border when it is chosen, a select on hover.
   WCAG asks 3:1 of a control's own outline, and these are the only thing
   distinguishing a chosen chip from an unchosen one. */
const faint = [];
TONES.forEach(function ([region, tone]) {
  const r = contrast(tone, IVORY);
  if (r < 3) faint.push(region + ' = ' + r.toFixed(2) + ':1');
});
check('a chosen chip is distinguishable from an unchosen one, in every region',
  faint.length === 0,
  faint.length ? faint.join(', ') : 'every tone clears 3:1 as a control boundary');

/* The list above has to stay honest, so it is counted against the file.
   `color:` needs a boundary in front of it: the first version of this check
   matched `border-color:var(--jf-tone)` as well and reported eleven rules
   where six paint text — a check failing on its own bug, which is the most
   expensive kind because it teaches people to ignore it. */
const paints = (css.match(/(^|[^-\w])color:var\(--jf-tone\)/g) || []).length;
check('no rule paints text in the tone without being measured',
  paints === TONED.length,
  paints + ' rules paint text in styles/fund.css, ' + TONED.length + ' measured');

/* The figure is ink, not tone. A decision about hierarchy — colour marks the
   place, ink carries the arithmetic — that also happens to be what fixed the
   two failures above. */
check('the money is set in the reading ink, on every ground',
  /\.jf-said\s+b\s*\{[^}]*color:\s*var\(--c-ink\)/.test(css)
    && contrast('#171A17', SAND) > 10,
  contrast('#171A17', SAND).toFixed(1) + ':1 on sand, unaffected by the region');

check('nothing on these pages animates on arrival',
  !/@keyframes/.test(css) && !/animation\s*:/.test(css),
  'the only transition is on :hover, which is a response rather than a display');

/* Structure, the parts a browser check cannot see. */
pages.forEach(function ([name, html]) {
  check(name + ': carries the company statement',
    html.includes('<!-- gen:company -->') && /Wankong LLC/.test(html),
    'spliced from tourism/company.json like the other 1,587 pages');
  check(name + ': carries a breadcrumb trail',
    /"@type":"BreadcrumbList"/.test(html));
  check(name + ': preloads the display face',
    /archivo-narrow-latin\.woff2/.test(html));
  check(name + ': uses the site stylesheet, not its own reset',
    /styles\/afrinkong\.css/.test(html) && /styles\/fund\.css/.test(html));
  check(name + ': has one h1 and a skip link',
    (html.match(/<h1/g) || []).length === 1 && /class="af-skip"/.test(html));
});

check('the estimator degrades to a correct answer without scripting',
  /jf-rule/.test(page) && page.includes(F.money(seven.total)),
  'the default journey total is in the HTML: ' + F.money(seven.total));

check('destination charges are disclosed on the page that gives the figure',
  /not<\/b> in this figure|are <b>not<\/b> in this figure/.test(page)
    || /settled by us at cost/i.test(words(page)),
  'park fees, permits and conservation charges named as excluded');

/* ---- report ---------------------------------------------------------------- */

process.stdout.write(out.join('\n') + '\n');
const failed = out.filter(l => l.startsWith('FAIL')).length;
process.stdout.write('\n' + (out.length - failed) + ' passed, ' + failed
                     + ' failed, ' + out.length + ' checks\n');
process.exit(failed ? 1 : 0);
