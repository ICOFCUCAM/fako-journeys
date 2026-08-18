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

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
