/* Every internal link on this site goes somewhere.
 *
 *     node tools/link-checks.js
 *
 * Fifteen hundred and ninety-four pages, cross-linked by six generators and a
 * handful of hand-written ones, and nothing anywhere checked that an href
 * resolves. A dead internal link is the cheapest possible way to lose somebody
 * who was already interested, and it is invisible until a visitor finds it.
 *
 * WHAT COUNTS AS RESOLVING
 *
 * vercel.json sets cleanUrls and trailingSlash: false, so /about is served from
 * about.html and /places/kenya/x from places/kenya/x.html. A link is good if it
 * names a file, a file with .html appended, or a directory with an index.html
 * in it — which is what the host will actually do with it.
 *
 * External links are not followed. This runs offline in the same places the
 * rest of the checks do, and a check that needs the internet is a check that
 * fails for reasons that have nothing to do with the site. mailto:, tel: and
 * javascript: are left alone for the same reason.
 *
 * FRAGMENTS ARE CHECKED, AND THAT IS WHERE THE FAULTS HIDE
 *
 * /#destinations is the kind of link that rots quietly: rename the section and
 * every page that pointed at it still resolves to a page and lands at the top
 * of it. So a fragment is looked up in the target page's ids, and a link to an
 * id that is not there is reported as its own kind of failure.
 *
 * Except a fragment with a slash in it, which is not an id at all. Three pages
 * route on the hash so they can be deep linked without a page load — the atlas
 * at #/algeria, the homepage at #r/east for a region and #w/food for a want —
 * and no id on this site has a slash in it. Nearly six thousand of those, and
 * treating them as ids made the first run of this check useless.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SKIP_DIRS = new Set(['.git', 'node_modules', 'incoming', 'tools', 'docs']);

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

function pages(dir, acc) {
  for (const name of fs.readdirSync(dir)) {
    if (SKIP_DIRS.has(name) || name.startsWith('.')) continue;
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) pages(full, acc);
    else if (name.endsWith('.html')) acc.push(full);
  }
  return acc;
}

const files = pages(ROOT, []);
const have = new Set(files.map(f => path.relative(ROOT, f).split(path.sep).join('/')));

/* The ids on each page, read once. Twelve hundred of these files are place
   pages of the same shape, so this is the expensive half and it is still one
   pass over the disk. */
const idsOf = new Map();
const HREF = /\shref="([^"]+)"/g;
const ID = /\sid="([^"]+)"/g;
const bodies = new Map();
for (const f of files) {
  const rel = path.relative(ROOT, f).split(path.sep).join('/');
  const src = fs.readFileSync(f, 'utf8');
  bodies.set(rel, src);
  const ids = new Set();
  let m;
  /* RESET, BECAUSE A /g REGEX REMEMBERS WHERE IT STOPPED.
     Without this the second file is scanned from wherever the first one
     finished, the third from wherever the second did, and almost every page's
     ids go unseen. The first run of this check reported ten dead anchors into
     the portrait pages; every one of those ids was in the file, and grep found
     them in a second. A shared /g regex in a loop is the bug that makes a
     check confidently wrong rather than merely silent. */
  ID.lastIndex = 0;
  while ((m = ID.exec(src))) ids.add(m[1]);
  idsOf.set(rel, ids);
}

function resolve(href) {
  /* -> the repository-relative page a link lands on, or null if nothing does. */
  let p = href.replace(/^\//, '');
  if (p === '' ) return 'index.html';
  if (have.has(p)) return p;
  if (have.has(p + '.html')) return p + '.html';
  if (have.has(p.replace(/\/$/, '') + '/index.html')) {
    return p.replace(/\/$/, '') + '/index.html';
  }
  return null;
}

const EXTERNAL = /^(https?:|mailto:|tel:|javascript:|data:|#|\/\/)/i;
const ASSET = /\.(css|js|json|xml|txt|png|jpe?g|webp|svg|woff2?|mp4|webm|ico|webmanifest|pdf)$/i;

const deadPages = [];
const deadFragments = [];
const deadAssets = [];
let linksSeen = 0;

for (const [rel, src] of bodies) {
  HREF.lastIndex = 0;
  let m;
  const reported = new Set();
  while ((m = HREF.exec(src))) {
    const raw = m[1].trim();
    if (!raw || EXTERNAL.test(raw)) {
      /* A same-page fragment still has to name something on this page. */
      if (raw.startsWith('#') && raw.length > 1 && raw.indexOf('/') < 0) {
        linksSeen += 1;
        const id = decodeURIComponent(raw.slice(1));
        if (!idsOf.get(rel).has(id) && !reported.has(raw)) {
          reported.add(raw);
          deadFragments.push(rel + ' -> ' + raw);
        }
      }
      continue;
    }
    if (!raw.startsWith('/')) continue;      // relative links: none are used here
    linksSeen += 1;
    const [pathPart, frag] = raw.split('#');
    const clean = pathPart.split('?')[0];
    if (ASSET.test(clean)) {
      if (!have.has(clean.replace(/^\//, ''))
          && !fs.existsSync(path.join(ROOT, clean.replace(/^\//, '')))
          && !reported.has(raw)) {
        reported.add(raw);
        deadAssets.push(rel + ' -> ' + raw);
      }
      continue;
    }
    const target = resolve(clean);
    if (!target) {
      if (!reported.has(raw)) { reported.add(raw); deadPages.push(rel + ' -> ' + raw); }
      continue;
    }
    if (frag && frag.indexOf('/') < 0 && !idsOf.get(target).has(decodeURIComponent(frag))
        && !reported.has(raw)) {
      reported.add(raw);
      deadFragments.push(rel + ' -> ' + raw);
    }
  }
}

check('every internal link lands on a page', !deadPages.length,
  deadPages.length ? deadPages.slice(0, 3).join(' | ') + (deadPages.length > 3
    ? ' (+' + (deadPages.length - 3) + ' more)' : '')
    : linksSeen + ' links across ' + files.length + ' pages');
check('every asset a page links to is on disk', !deadAssets.length,
  deadAssets.length ? deadAssets.slice(0, 3).join(' | ') + (deadAssets.length > 3
    ? ' (+' + (deadAssets.length - 3) + ' more)' : '') : 'no missing stylesheet, script or file');
check('every fragment names an id that exists', !deadFragments.length,
  deadFragments.length ? deadFragments.slice(0, 3).join(' | ') + (deadFragments.length > 3
    ? ' (+' + (deadFragments.length - 3) + ' more)' : '') : 'every #anchor resolves');

/* ---- REFERENCES THAT ARE NOT HREFS -------------------------------------
 *
 * `aria-labelledby` names an id exactly the way `href="#x"` does, and until now
 * only the href form was checked. The difference is that a dead fragment lands
 * a sighted reader at the top of the page, while a dead aria-labelledby makes a
 * section nameless to a screen reader and shows nothing at all to anybody else.
 * Strictly worse, and strictly less visible.
 *
 * Found by writing one: a section added to 51 country pages in this session
 * carried aria-labelledby="ct-depths-h" pointing at an h2 that had never been
 * given the id. The rest of the site's references were clean — 130 of them —
 * so this check exists to keep it that way rather than to fix a backlog. */
/* Reuses `bodies` and `idsOf`, both already built above. Re-reading 1,597
   files to ask a second question about them is the kind of thing that turns a
   four-second check suite into a forty-second one. */
const danglingAria = [];
let ariaSeen = 0;
for (const [rel, src] of bodies) {
  const ids = idsOf.get(rel) || new Set();
  for (const m of src.matchAll(/aria-(?:labelledby|describedby)="([^"]+)"/g)) {
    for (const ref of m[1].split(/\s+/).filter(Boolean)) {
      ariaSeen++;
      if (!ids.has(ref)) danglingAria.push(rel + ' -> ' + ref);
    }
  }
}
check('every aria-labelledby names an id that exists', !danglingAria.length,
  danglingAria.length
    ? danglingAria.length + ' dangling, e.g. ' + danglingAria.slice(0, 3).join(' | ')
    : ariaSeen + ' references, every one naming something on its own page');

/* ---- THE COUNTRY GRAPH -------------------------------------------------
 *
 * Everything above asks whether a link that exists resolves. This asks the
 * opposite question: whether a link that SHOULD exist is there.
 *
 * That is a different kind of failure and nothing was looking for it. Every
 * link on the site resolved perfectly while 53 of 53 country pages linked to
 * neither their own portrait nor their own places, and 53 of 53
 * /tourism/<country> pages had exactly one real outbound link. Valid, and
 * disconnected. A link checker that only validates hrefs will pass a site made
 * of islands.
 *
 * Each country has four surfaces. This asserts the edges between them that
 * ought to hold in every direction, so that adding a fifty-fifth country
 * cannot quietly reintroduce the hole.
 *
 * WHAT IS DELIBERATELY NOT ASSERTED: /uganda and /namibia do not exist —
 * home.NO_PAGE skips them because both have operator sites of their own — so
 * no page may link there and the check must not demand it. Read from disk
 * rather than from a list copied into this file, which would be a third
 * vocabulary to keep in step. */

const inBody = (html) => html
  .replace(/<header[\s\S]*?<\/header>/g, '')
  .replace(/<footer[\s\S]*?<\/footer>/g, '')
  .replace(/<nav class="af-foot-nav"[\s\S]*?<\/nav>/g, '');

const hrefsIn = (html) => new Set(
  (inBody(html).match(/href="(\/[^"]*)"/g) || [])
    .map(h => h.slice(6, -1).split(/[?#]/)[0] || '/'));

const has = (p) => fs.existsSync(path.join(ROOT, p));
const readIf = (p) => has(p) ? fs.readFileSync(path.join(ROOT, p), 'utf8') : null;

const tourismDir = path.join(ROOT, 'tourism');
const countries = fs.existsSync(tourismDir)
  ? fs.readdirSync(tourismDir)
      .filter(f => f.endsWith('.html') && f !== 'index.html')
      .map(f => f.slice(0, -5))
      .filter(s => has(path.join('portrait', s + '.html')))
  : [];

/* 1 — the country page reaches its own depths. */
const noPortrait = [], noPlaces = [], noRootPage = [];
countries.forEach(s => {
  const html = readIf(s + '.html');
  /* NAMED, NOT SILENTLY DROPPED.
     This was a bare `return`. Uganda and Namibia have no root country page —
     they are sister-company sites — so the check ran over 52 of 54 countries
     and reported "52 of 52", which reads as complete. It was complete over a
     population it had quietly narrowed, and that is how an exemption becomes
     invisible. page-inventory.py names its operator exemption in the result
     line; so does this now. */
  if (html === null) { noRootPage.push(s); return; }
  const L = hrefsIn(html);
  if (!L.has('/portrait/' + s)) noPortrait.push(s);
  if (![...L].some(h => h === '/places' || h.startsWith('/places/' + s))) {
    noPlaces.push(s);
  }
});
const withHome = countries.filter(s => has(s + '.html'));
const exempt = noRootPage.length
  ? ` \u2014 ${noRootPage.length} exempt (${noRootPage.join(', ')}): no root ` +
    'country page, they are sister-company sites'
  : '';
check('every country page reaches its own portrait', !noPortrait.length,
  noPortrait.length ? noPortrait.slice(0, 5).join(', ')
    : withHome.length + ' of ' + countries.length + exempt + '; it is the richest page '
      + 'on the site and used to be linked from none of them');
check('every country page reaches its own places', !noPlaces.length,
  noPlaces.length ? noPlaces.slice(0, 5).join(', ')
    : withHome.length + ' of ' + countries.length + exempt);

/* 2 — the experiences page is not a dead end. This is the one that was
   isolated in both directions: nothing arrived from a place, nothing left. */
const deadEnds = [];
countries.forEach(s => {
  const html = readIf(path.join('tourism', s + '.html'));
  if (html === null) return;
  const L = [...hrefsIn(html)].filter(h => !/\.(woff2?|png|jpe?g|svg|css|js|webmanifest|ico)$/.test(h));
  /* Its own country's other surfaces, not merely "some links". */
  const reaches = L.some(h => h === '/' + s
    || h === '/portrait/' + s || h.startsWith('/places'));
  if (!reaches) deadEnds.push(s + ' (' + L.length + ' real links)');
});
check('no experiences page is a dead end', !deadEnds.length,
  deadEnds.length ? deadEnds.slice(0, 5).join(', ')
    : countries.length + ' of ' + countries.length + ' reach the rest of their '
      + 'own country; all 53 once had one outbound link, to /journey');

/* 3 — a place page reaches the page that prices its country. The other upward
   edges were already there; this was the only one missing, on all 1,363. */
const placeMisses = [];
countries.forEach(s => {
  const dir = path.join(ROOT, 'places', s);
  if (!fs.existsSync(dir)) return;
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.html'));
  files.forEach(f => {
    const L = hrefsIn(fs.readFileSync(path.join(dir, f), 'utf8'));
    if (!L.has('/tourism/' + s)) placeMisses.push(s + '/' + f.slice(0, -5));
  });
});
const placeTotal = countries.reduce((n, s) => {
  const d = path.join(ROOT, 'places', s);
  return n + (fs.existsSync(d)
    ? fs.readdirSync(d).filter(f => f.endsWith('.html')).length : 0);
}, 0);
check('every place page reaches what a journey to its country costs',
  !placeMisses.length,
  placeMisses.length
    ? placeMisses.length + ' without it, e.g. ' + placeMisses.slice(0, 3).join(', ')
    : placeTotal + ' place pages');

/* ---- THE DISCOVERY CHAIN, HOP BY HOP -----------------------------------
 *
 * Africa -> Country -> Place -> Experience -> Journey -> Plan. The mandate's
 * requirement is "no islands", and the checks above test three of those hops
 * on the ROOT country pages. The /tourism/<country> surface — 55 pages, the
 * one the navigation calls "Countries" — was tested by none of them.
 *
 * TWO FALSE ALARMS BEFORE THIS WAS WRITTEN, both from the same bug. Parsing
 * hrefs with /href="(\/[^"#?]*)"/ requires the quote to follow the path, so
 * `/places#algeria` matched nothing and the scan reported that all 55 country
 * pages failed to reach their destinations. They all reach them. A fragment
 * has to be STRIPPED, not excluded, and getting that wrong turns a healthy
 * graph into a five-alarm finding.
 */
function outbound(rel) {
  const html = readIf(rel);
  if (html === null) return new Set();
  const main = (html.match(/<main[\s\S]*?<\/main>/) || [html])[0];
  const out = new Set();
  for (const m of main.matchAll(/href="([^"]+)"/g)) {
    if (m[1][0] === '/') out.add(m[1].split('#')[0].split('?')[0] || '/');
  }
  return out;
}

const HOPS = [
  ['a country reaches its portrait', (c, L) => L.has('/portrait/' + c)],
  ['a country reaches its destinations',
   (c, L) => [...L].some((h) => h === '/places' || h.startsWith('/places/'))],
  ['a country reaches the journey planner',
   (c, L) => [...L].some((h) => h.startsWith('/journey'))],
];
for (const [label, ok] of HOPS) {
  const bad = countries.filter((c) => !ok(c, outbound(path.join('tourism', c + '.html'))));
  check(`on the Countries surface, ${label}`,
    bad.length === 0,
    bad.length ? `${bad.length} without it: ${bad.slice(0, 5).join(', ')}`
               : `${countries.length} of ${countries.length}`);
}

const placeHops = [];
for (const c of countries) {
  const dir = path.join(ROOT, 'places', c);
  if (!fs.existsSync(dir)) continue;
  const first = fs.readdirSync(dir).filter((f) => f.endsWith('.html')).sort()[0];
  if (!first) continue;
  const L = outbound(path.join('places', c, first));
  if (![...L].some((h) => h.startsWith('/atlas'))) placeHops.push(c + ':experience');
  if (![...L].some((h) => h.startsWith('/journey'))) placeHops.push(c + ':journey');
}
check('a place reaches an experience and a journey',
  placeHops.length === 0,
  placeHops.length ? placeHops.slice(0, 6).join(', ')
    : `${countries.length} countries sampled; the chain Africa \u2192 country ` +
      '\u2192 place \u2192 experience \u2192 journey \u2192 plan has no gap');

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
