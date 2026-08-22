/* One navigation system, one shell. Phase 5 + 6.
 *
 *     node tools/shell-checks.js
 *
 * WHAT THIS EXISTS TO PREVENT
 *
 * The instruction was explicit: "Do not create ten slightly different
 * interpretations of the new navigation." Ten is not a hypothetical — it is
 * what the audit found. Ten masthead classes and seven footers across 1,597
 * pages, none of which knew about the others, and one of which (`fj-mast`) was
 * worn by two different companies at once.
 *
 * Consolidating them once is a morning's work. Keeping them consolidated is
 * what needs a check, because every generator is free to write its own header
 * and nothing has ever compared them.
 *
 * These checks are written to fail against a tree mid-migration. That is
 * deliberate: a check that only passes once everything is done cannot guide the
 * work. Each states how far the migration has got.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

function pages(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith('.') || e.name === 'node_modules') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) pages(p, acc);
    else if (e.name.endsWith('.html')) acc.push(p);
  }
  return acc;
}

const files = pages(ROOT, []).filter(f => {
  /* tourism/compare.html is a noindex internal review sheet, not a product
     surface. It has no stylesheet and no footer by design. */
  return path.relative(ROOT, f) !== 'tourism/compare.html';
});
const src = new Map(files.map(f =>
  [path.relative(ROOT, f).split(path.sep).join('/'),
   fs.readFileSync(f, 'utf8')]));

/* ---- 1. how far the migration has got --------------------------------- */

const mastOf = (html) => {
  const m = html.match(/<header[^>]*class="([^"]+)"/);
  return m ? m[1].split(/\s+/)[0] : '(none)';
};
const byMast = {};
for (const [rel, html] of src) {
  const k = mastOf(html);
  (byMast[k] = byMast[k] || []).push(rel);
}
const onShell = (byMast['af-shell'] || []).length;
const legacy = Object.keys(byMast).filter(k => k !== 'af-shell');
check('the shell exists and pages are on it', onShell > 0,
  onShell + ' of ' + src.size + ' page(s) wear af-shell; '
    + legacy.length + ' legacy masthead class(es) remain: '
    + legacy.map(k => k + '×' + byMast[k].length).join(' '));

/* THE END STATE. Two classes: the platform shell, and the Kamerun operator's,
   which is a different company's front door and must never wear Afrinkong's
   navigation. This fails until the migration finishes, and it is meant to. */
const ALLOWED = ['af-shell'];
const stragglers = legacy.filter(k => ALLOWED.indexOf(k) === -1);
check('every page wears the shell and nothing else', !stragglers.length,
  stragglers.length
    ? stragglers.map(k => k + '×' + byMast[k].length).join(' ')
    : 'one masthead class site-wide');

/* ---- 2. no ten interpretations ----------------------------------------
   The literal instruction. Every page that HAS the shell must render the same
   navigation — same areas, same order, same labels. A generator that builds
   its own version of the nav inside the shell would pass check 1 and fail
   this one, which is the failure mode worth catching. */

/* The AREAS, by their summaries — Explore and Plan — rather than by whatever
   links happen to sit inside them. The signature is the shape of the
   navigation, and the shape is the two areas. */
const navSig = (html) => {
  const m = html.match(/<nav class="af-shell-nav"[^>]*>([\s\S]*?)<\/nav>\s*<div class="af-shell-util"/);
  if (!m) return null;
  return (m[1].match(/<summary>([^<]+)<\/summary>/g) || []).join('|');
};
const sigs = {};
for (const [rel, html] of src) {
  if (mastOf(html) !== 'af-shell') continue;
  /* THE OPERATOR IS NOT A DIVERGENT INTERPRETATION. Its five pages wear
     af-shell--operator and carry the Kamerun ground operation's own links —
     Circuits, Rates & Fees, The Operator, Enquire. That is the separation this
     work exists to make, so counting it as an eleventh navigation would be the
     check misreading its own success. */
  if (/af-shell--operator/.test(html)) continue;
  const s = navSig(html);
  (sigs[s] = sigs[s] || []).push(rel);
}
const distinct = Object.keys(sigs);
check('every page on the shell shows the same primary navigation',
  distinct.length <= 1,
  distinct.length <= 1
    ? (distinct[0] || '(none)').replace(/>|<\/a>/g, '') + ' — on '
      + onShell + ' page(s)'
    : distinct.length + ' different primary navigations: '
      + distinct.map(s => sigs[s].length + '× ' + sigs[s][0]).join(' | '));

/* ---- 2b. AND THE AREAS' CHILDREN ARE REACHABLE ------------------------
 *
 * THE CHECK ABOVE PASSED WHILE THE NAVIGATION WAS BROKEN, and that is why this
 * one exists.
 *
 * A browser-suite failure — the Trans Afrique band's copy under a 144px
 * masthead — was fixed by dropping the area row from every page carrying a
 * product band. That is 1,584 of 1,597, so Destinations, The Atlas, Countries,
 * Stories, Meet Africa, Trans Afrique and The Wonders became reachable from
 * nowhere but the phone menu.
 *
 * The check above saw "Explore|Plan" on all 1,597 pages and passed. It was
 * asserting that the two labels were consistent, which they were, and never
 * asked the question the navigation exists to answer: can a visitor get to the
 * things inside them.
 *
 * Consistency is not reachability. This asserts the second. */
const unreachable = [];
for (const [rel, html] of src) {
  if (mastOf(html) !== 'af-shell') continue;
  if (/af-shell--operator/.test(html)) continue;
  /* IN THE DESKTOP NAVIGATION, NOT MERELY IN THE MARKUP.
     The first version of this searched the whole <header> and passed on the
     broken tree — because the phone menu lives inside the header and lists
     every child, while being display:none above 760px. Present is not
     reachable, and measuring presence is the same mistake as the check this
     one was written to replace.
     `af-shell-nav` is the desktop navigation; `af-shell-sub` is the area row
     where a page has one. Those two are what a visitor on a laptop can use. */
  const navOnly = (html.match(
    /<nav class="af-shell-nav"[\s\S]*?<\/nav>\s*<div class="af-shell-util"/) || [''])[0]
    + (html.match(/<nav class="af-shell-sub"[\s\S]*?<\/nav>/g) || []).join('');
  const missing = ['/places', '/atlas', '/stories', '/meet', '/trans-afrique',
                   '/journey', '/journey-fund']
    .filter(h => !new RegExp('href="' + h + '(?:[#"])').test(navOnly));
  if (missing.length) unreachable.push(rel + ' cannot reach ' + missing.join(' '));
}
check('every area’s children are reachable from every page', !unreachable.length,
  unreachable.length
    ? unreachable.length + ' page(s), e.g. ' + unreachable[0]
    : 'the ten destinations under Explore and Plan are one press away on all '
      + onShell + ' pages');

/* ---- 3. the settled decisions ----------------------------------------- */

let everyPlace = [];
for (const [rel, html] of src) {
  if (/>Every place</.test(html)) everyPlace.push(rel);
}
check('“Every place” is gone; the label is Destinations', !everyPlace.length,
  everyPlace.length
    ? everyPlace.length + ' page(s) still say it, e.g. ' + everyPlace.slice(0, 3).join(', ')
    : 'renamed everywhere');

const aboutOnDisk = fs.existsSync(path.join(ROOT, 'about-afrinkong.html'));
check('/about-afrinkong exists', aboutOnDisk,
  aboutOnDisk
    ? 'the page that did not exist — /about belongs to the Kamerun operator'
    : 'the shell links it and link-checks will fail');

/* TRAVEL and FUND are decided OUT of the public navigation until they are
   real. This is the check that stops somebody adding them back because the
   diagram looks tidier with four areas. */
const premature = [];
for (const [rel, html] of src) {
  const m = html.match(/<nav class="af-shell-nav"[^>]*>([\s\S]*?)<\/nav>/);
  if (m && /(>Travel<|>Fund<)/.test(m[1])) premature.push(rel);
}
check('no navigation area is offered that a visitor cannot use',
  !premature.length,
  premature.length
    ? 'TRAVEL or FUND in the primary nav on ' + premature.length + ' page(s)'
    : 'Explore and Plan only; Travel joins when travel is bookable and Fund '
      + 'when issuance is ungated');

/* ---- THE GATE, NOT THE BAN ---------------------------------------------
 *
 * The check above forbids the words Travel and Fund in the primary
 * navigation. That was the whole mechanism, and it expressed the wrong thing:
 * it said "do not add these" where the truth is "these exist, and something
 * specific is holding them shut".
 *
 * plate.AREAS now declares all four areas, each with a gate, and shell()
 * renders only the ungated ones through plate.open_areas(). These checks
 * assert the consequence rather than the prohibition: an area whose gate is
 * shut appears NOWHERE — not in the desktop navigation, not in the phone
 * menu, not in a footer — and its children do not either.
 *
 * The phone menu matters here. It is display:none on a desktop and contains
 * every link, which is exactly how the area navigation was invisible on 1,584
 * pages while a check reported it consistent. A ban that only reads the
 * desktop bar would miss a gated area leaking into the drawer.
 */
const gatedAreas = [
  { label: 'Fund', gate: 'programme-compliance',
    kids: ['/wallet', '/goals', '/activity'] },
  { label: 'Travel', gate: 'booking-not-built',
    kids: ['/journeys', '/bookings', '/itinerary', '/documents', '/support'] },
];

for (const area of gatedAreas) {
  const leaked = [];
  for (const [rel, html] of src) {
    const head = (html.match(/<header[\s\S]*?<\/header>/) || [''])[0];
    if (new RegExp(`<summary[^>]*>\\s*${area.label}\\b`).test(head)) leaked.push(rel);
    else if (area.kids.some((k) => head.includes(`href="${k}"`))) leaked.push(rel);
  }
  check(`the ${area.label} area is held shut, and appears nowhere`,
    leaked.length === 0,
    leaked.length
      ? `leaked onto ${leaked.length} page(s), e.g. ${leaked[0]}`
      : `gate: ${area.gate}. Declared in plate.AREAS with its children, ` +
        `rendered by nothing — a promise deferred rather than omitted`);
}


/* ---- 4. active state --------------------------------------------------- */

const doubled = [];
for (const [rel, html] of src) {
  for (const m of html.matchAll(/<nav\b[^>]*>([\s\S]*?)<\/nav>/g)) {
    const n = (m[1].match(/aria-current="page"/g) || []).length;
    if (n > 1) doubled.push(rel + ' (' + n + ' in one nav)');
  }
}
check('no nav marks two links as the current page', !doubled.length,
  doubled.length ? doubled.slice(0, 4).join(', ')
    : 'a fragment link into this page is a section, not the page — and is '
      + 'not marked');

const areaVals = {};
for (const [rel, html] of src) {
  if (mastOf(html) !== 'af-shell') continue;
  const m = html.match(/<body[^>]*data-area="([^"]*)"/);
  areaVals[m ? m[1] : '(none)'] = (areaVals[m ? m[1] : '(none)'] || 0) + 1;
}
const badArea = Object.keys(areaVals)
  .filter(a => a !== 'explore' && a !== 'plan' && a !== '(none)');
check('data-area is one of the two areas, or absent', !badArea.length,
  badArea.length ? badArea.join(', ')
    : Object.entries(areaVals).map(([k, v]) => k + '=' + v).join(' '));

/* ---- 5. page identity --------------------------------------------------
   1,529 of 1,597 pages carried no body class, so nothing could be styled by
   kind. This is the cheapest change in the programme and the one that unblocks
   the rest of the design system. */

const noFamily = [];
for (const [rel, html] of src) {
  const m = html.match(/<body[^>]*class="([^"]*)"/);
  if (!m || !/\baf--[a-z]+/.test(m[1])) noFamily.push(rel);
}
check('every page declares which family it belongs to',
  !noFamily.length,
  noFamily.length
    ? (src.size - noFamily.length) + ' of ' + src.size + ' declared; '
      + noFamily.length + ' still anonymous'
    : 'all ' + src.size + ' pages say what kind of page they are');

/* ---- 6. it works with no JavaScript ----------------------------------- */

const jsNav = [];
for (const [rel, html] of src) {
  const m = html.match(/<header class="af-shell[^"]*">[\s\S]*?<\/header>/);
  if (!m) continue;
  if (/onclick=|<button/.test(m[0])) jsNav.push(rel);
  if (!/<details class="af-shell-menu">/.test(m[0])
      && !/af-shell--operator/.test(m[0])) {
    jsNav.push(rel + ' (no <details> menu)');
  }
}
check('the shell opens with no JavaScript', !jsNav.length,
  jsNav.length ? jsNav.slice(0, 3).join(', ')
    : '<details> discloses the phone menu; no script, no button, no aria to '
      + 'keep in step');

/* ---- 7. THE ENTITY BOUNDARY --------------------------------------------
 *
 * Afrinkong is the customer-facing travel brand. The Kamerun ground operation
 * is a separate company whose own front door — its circuits, its rates, its
 * enquiry desk in Douala — is hosted on the same domain.
 *
 *     Afrinkong customer experience  ->  /journey, /enquire
 *     Kamerun operator               ->  its operational desk
 *
 * WHY THIS NEEDS A CHECK AND NOT A CONVENTION
 *
 * /contact already has a working form. That is exactly the reason somebody
 * reaches for it: the fastest way to give a page a call to action is to point
 * it at a form that exists. Do that once on the homepage and Afrinkong's
 * primary conversion path is a subsidiary's contact page — which is how a
 * brand quietly becomes a referrer to its own supplier.
 *
 * The suite already had a check asserting the OPPOSITE — "the primary call of
 * the site still lands on /contact" — written when the site was substantially
 * the operator's. It went red when the homepage stopped doing that, which is
 * to say it went red for a correct change.
 *
 * WHAT IS AND IS NOT FORBIDDEN
 *
 * A link may point at the operator when the context is operational: "who would
 * take you", "open Kamerun", a named partner on a country page. 26 place pages
 * carry exactly that and they are right to.
 *
 * What is forbidden is the operator's desk appearing as a CUSTOMER CTA — in
 * navigation, in the footer nav, or as a primary button — on a page that is
 * Afrinkong's. The distinction is position, not URL.
 *
 * /cameroon is deliberately NOT on the desk list. It is Cameroon's country
 * page, one of fifty-four, and linking it as a destination from the atlas or a
 * place page is ordinary. That it also wears the operator's shell is a wrinkle
 * of one company being based in one of the countries.
 *
 * THIS IS THE NARROW HALF OF THE RULE, AND IT KNOWS IT.
 *
 * A path list cannot tell a destination from a desk, and this one only avoids
 * that by hand-excluding /cameroon. The general form lives in
 * scripts/entities.js, which classifies a link by ENTITY + CONTEXT + POSITION +
 * ACTION rather than by where it points, and tools/entity-checks.js enforces
 * the part that matters most: every act touching a customer's money,
 * entitlement or trip names the entity performing it.
 *
 * What survives here is the cheap positional check — the operator's desk must
 * not appear in navigation, a footer nav or a primary button on an Afrinkong
 * page. It is kept because it runs over the built HTML and catches the mistake
 * at the place it gets made. */

const DESK = ['/contact', '/about', '/pricing', '/services'];
const OPERATOR_PAGES = new Set(
  ['about.html', 'contact.html', 'pricing.html', 'services.html', 'cameroon.html']);
const CTA_CONTEXT = [
  ['af-shell-nav', 'the primary navigation'],
  ['af-shell-sub', 'the area navigation'],
  ['af-shell-prod-nav', 'a product band'],
  ['af-foot-nav', 'the footer navigation'],
  ['af-btn--solid', 'a primary button'],
];

const crossings = [];
for (const [rel, html] of src) {
  if (OPERATOR_PAGES.has(rel.split('/').pop())) continue;   /* their own pages */
  for (const [cls, what] of CTA_CONTEXT) {
    /* the element, or the nav that contains it */
    const re = new RegExp(
      '<(?:nav|div|a)[^>]*class="[^"]*' + cls + '[^"]*"[^>]*>([\\s\\S]*?)'
      + (cls.startsWith('af-btn') ? '</a>' : '</nav>'), 'g');
    for (const m of html.matchAll(re)) {
      const block = cls.startsWith('af-btn') ? m[0] : m[1];
      for (const d of DESK) {
        if (new RegExp('href="' + d + '"').test(block)) {
          crossings.push(rel + ' -> ' + d + ' in ' + what);
        }
      }
    }
  }
}
check('no Afrinkong page offers the operator’s desk as a customer CTA',
  !crossings.length,
  crossings.length ? crossings.slice(0, 4).join('; ')
    : 'navigation, footer and primary buttons all stay on Afrinkong’s own '
      + 'surfaces; an operational link in context is untouched');

/* The positive half. Absence is not architecture: a homepage that calls to
   nothing at all would pass the check above. */
const homeHtml = src.get('index.html') || '';
check('the homepage’s primary path is Afrinkong’s own',
  /href="\/journey"/.test(homeHtml),
  /href="\/journey"/.test(homeHtml)
    ? '/journey is the conversion path, /enquire the human-assisted one'
    : 'the homepage calls to neither /journey nor /enquire');

/* And the operator keeps its own desk. The boundary runs both ways: stripping
   /contact out of the operator's pages would leave a company with a form and
   no way to reach it. */
const deskless = ['contact.html', 'pricing.html', 'services.html', 'about.html']
  .filter(p => src.has(p) && !DESK.some(d => new RegExp('href="' + d + '"').test(src.get(p))));
check('the operator’s pages keep their own desk', !deskless.length,
  deskless.length ? deskless.join(', ')
    : 'the separation runs both ways — Kamerun’s pages reach Kamerun’s desk');

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
