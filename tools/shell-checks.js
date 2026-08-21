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

const navSig = (html) => {
  const m = html.match(/<nav class="af-shell-nav"[^>]*>([\s\S]*?)<\/nav>/);
  if (!m) return null;
  return (m[1].match(/>([^<]+)<\/a>/g) || []).join('|');
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

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
