/* Content architecture: one name per thing, and no engineering in the copy.
 *
 *     node tools/content-checks.js
 *
 * COMMIT 04 OF THE 50-COMMIT INTEGRATION MANDATE.
 *
 * WHY THIS SUITE EXISTS SEPARATELY FROM shell-checks.
 *
 * shell-checks.js already asserted that the destination index is labelled
 * "Destinations" and not "Every place". It passed. The label was still "every
 * place" on 1,404 place-page trails, "Every place, all fifty-four countries" on
 * the homepage, and "Every place we write up" on the country plates — because
 * the check was pinned to the primary navigation, which is one of the places a
 * product name appears and not the only one.
 *
 * That is the same fault as every other one in this repository: a check
 * measuring where something was rather than what is true. So this scans the
 * rendered text of every published page, and it does it for two rules.
 *
 * RULE ONE — ONE NAME PER THING.
 * A product with two names is two products to the person reading it. The names
 * are listed as (retired, current) pairs so the retirement is legible, and the
 * scan is over visible text, not markup: prose that happens to contain the
 * words "every place" in an ordinary English sentence is not a product name and
 * must not fail. The distinction is made by requiring the retired name to be
 * acting as a LABEL — inside a link, a heading, or a nav-ish span.
 *
 * RULE TWO — NO ENGINEERING IN THE COPY.
 * 54 portrait pages told a customer that their content came from
 * `tourism/countries/<slug>.json` and that the months were "not out of a
 * weather API". Both sentences were making a good point — the writing is not
 * rewritten for display, and we do not forecast — and both said it in the
 * vocabulary of the people who built it rather than the people reading it.
 *
 * COMMENTS ARE NOT COPY, and this suite learned that the hard way elsewhere:
 * `<[^>]+>` does not remove an HTML comment containing a `>`, and this codebase
 * writes long explanatory comments full of them. Comments go first.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SKIP = new Set(['node_modules', '.git', 'incoming', '.vercel']);
const out = [];
let pass = 0, fail = 0;

function check(name, ok, detail) {
  out.push(`${ok ? 'PASS' : 'FAIL'}\t${name}\t${detail || ''}`);
  ok ? pass++ : fail++;
}

function ignored() {
  const f = path.join(ROOT, '.vercelignore');
  if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, 'utf8').split('\n')
    .map((l) => l.trim().replace(/\/$/, ''))
    .filter((l) => l && !l.startsWith('#'));
}

function pages() {
  const rules = ignored();
  const out2 = [];
  (function walk(dir) {
    for (const name of fs.readdirSync(dir)) {
      if (SKIP.has(name) || name[0] === '.') continue;
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (name.endsWith('.html')) {
        const rel = path.relative(ROOT, full);
        if (!rules.some((r) => rel === r || rel.startsWith(r + '/'))) out2.push(rel);
      }
    }
  })(ROOT);
  return out2.sort();
}

/* Retired name -> the name that replaced it. A pair, so the history is legible
   and so a reader of this file can tell a rename from a ban. */
const RENAMED = [
  ['Every place', 'Destinations'],
];

/* Words that belong to the people who built this, not to the people reading
   it. Deliberately short: a long list produces false positives in ordinary
   English and gets switched off. Each of these was found in live copy. */
const ENGINEERING = [
  [/\b[\w/]+\.json\b/i, 'a file path'],
  [/\bweather API\b/i, 'an API'],
  [/\bsrcset\b/i, 'an HTML attribute'],
  [/\bquerySelector|innerHTML|localStorage\b/, 'a DOM API'],
];

const all = pages();
const strip = (s) => s
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/<(script|style|svg)\b[\s\S]*?<\/\1>/gi, ' ');

/* ---- rule one: one name per thing --------------------------------------- */
for (const [retired, current] of RENAMED) {
  const asLabel = [];
  for (const rel of all) {
    const html = strip(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
    /* Acting as a LABEL, not as English. Inside an anchor, a heading, or a
       span whose class marks it as a control. "every place we have been" in a
       sentence is prose and stays. */
    const re = new RegExp(
      `<(?:a|h[1-6]|span|b|strong)\\b[^>]*>\\s*${retired}\\b`, 'i');
    if (re.test(html)) asLabel.push(rel);
  }
  check(`the destination index is called "${current}" everywhere it is named`,
    asLabel.length === 0,
    asLabel.length
      ? `"${retired}" is still a label on ${asLabel.length} page(s), e.g. ${asLabel[0]}`
      : `"${retired}" appears as a label on no page; the rename reached the ` +
        `trails and the plates, not only the navigation`);
}

/* ---- rule two: no engineering in the copy -------------------------------- */
for (const [re, what] of ENGINEERING) {
  const hits = [];
  for (const rel of all) {
    const text = strip(fs.readFileSync(path.join(ROOT, rel), 'utf8'))
      .replace(/<[^>]+>/g, ' ');
    if (re.test(text)) hits.push(rel);
  }
  check(`no page shows a customer ${what}`,
    hits.length === 0,
    hits.length
      ? `${hits.length} page(s), e.g. ${hits[0]}`
      : `scanned ${all.length} published pages`);
}

/* ---- rule three: nothing unfinished shipped ------------------------------ */
const UNFINISHED = /\b(TODO|TBD|FIXME|lorem ipsum|coming soon|under construction)\b/i;
const unfinished = all.filter((rel) => {
  const text = strip(fs.readFileSync(path.join(ROOT, rel), 'utf8'))
    .replace(/<[^>]+>/g, ' ');
  return UNFINISHED.test(text);
});
check('no published page carries unfinished copy',
  unfinished.length === 0,
  unfinished.length ? unfinished.slice(0, 4).join(', ')
                    : `scanned ${all.length} published pages`);

process.stdout.write(out.join('\n') + '\n');
process.stdout.write(`\n${pass} passed, ${fail} failed, ${pass + fail} checks\n`);
process.exit(fail ? 1 : 0);
