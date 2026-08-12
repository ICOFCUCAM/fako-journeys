/* Checks for the journey engine, run against the code the page actually runs.
 *
 *     node tools/journey-checks.js          (or: python3 tools/tourism/build.py test)
 *
 * The engine is JavaScript because it has to answer between one click and the
 * next, so testing it from Python would mean testing a Python impression of it.
 * This loads the same module the browser loads and the same data the built page
 * carries, prints one tab-separated line per check, and exits non-zero if any
 * of them failed. The Python suite runs it and folds the lines into its own
 * report so there is still one place to look.
 *
 * What is worth checking here is not that the arithmetic runs. It is that the
 * engine cannot say something the dataset does not support: every reason it
 * gives has to be checkable against the country file it came from, and the two
 * answers it deliberately does not score have to stay unscored.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const E = require(path.join(ROOT, 'scripts', 'journey-engine.js'));

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

/* The data the built page carries, read out of the page itself — so a build
   that shipped something different would fail here rather than pass on a copy
   that only the test can see. */
const page = fs.readFileSync(path.join(ROOT, 'journey.html'), 'utf8');
const m = page.match(/<script type="application\/json" id="jn-data">([\s\S]*?)<\/script>/);
if (!m) {
  check('the built page carries the engine data', false, 'no jn-data block');
  process.stdout.write(out.join('\n') + '\n');
  process.exit(1);
}
const D = JSON.parse(m[1]);
const slugs = Object.keys(D.countries);
const lensKeys = Object.keys(D.lenses);

const places = {};
slugs.forEach(function (s) {
  const p = path.join(ROOT, 'data', 'atlas', s + '.json');
  if (fs.existsSync(p)) places[s] = JSON.parse(fs.readFileSync(p, 'utf8'));
});

check('the built page carries every published country', slugs.length > 0,
  slugs.length + ' countries');
check('every country has places to build a journey from',
  slugs.every(function (s) { return places[s] && places[s].places.length > 0; }));

/* ---- every reason is checkable ------------------------------------------- */

/* The whole trust argument of the page is that a reason can be verified against
   the dataset. So verify all of them, for every question a visitor can ask. */
let unbacked = [];
let asked = 0;
lensKeys.forEach(function (k) {
  for (let month = 0; month <= 12; month++) {
    asked++;
    const r = E.recommend(D, {wants: [k], month: month || null, seed: 0});
    r.picks.forEach(function (p) {
      const c = D.countries[p.slug];
      p.reasons.forEach(function (reason) {
        let ok = true;
        if (reason.key === 'lens') ok = c.calls.indexOf(k) >= 0;
        else if (reason.key === 'gap') ok = true;             /* absence, checked below */
        else if (reason.key === 'season') ok = month && c.months.indexOf(month) >= 0;
        else if (reason.key === 'operator') ok = !!c.operator && reason.text === c.operator.name;
        else if (reason.key === 'depth') {
          ok = (c.lensCounts[k] || 0) === parseInt(reason.text, 10);
        }
        if (!ok) unbacked.push(p.slug + '/' + reason.key);
      });
    });
  }
});
check('every reason given is backed by the country file', !unbacked.length,
  unbacked.slice(0, 3).join(', ') || asked + ' questions asked');

/* A country is never recommended for something it does not declare. */
let wrong = [];
lensKeys.forEach(function (k) {
  E.rank(D, {wants: [k]}).forEach(function (p) {
    if (D.countries[p.slug].calls.indexOf(k) < 0) wrong.push(p.slug + ' for ' + k);
  });
});
check('no country is offered for something it does not lead on', !wrong.length,
  wrong.slice(0, 3).join(', '));

/* And a partial match says what it is missing. */
const everything = lensKeys.slice();
const partial = E.recommend(D, {wants: everything, seed: 0}).picks[0];
const gaps = partial.reasons.filter(function (r) { return r.key === 'gap'; });
const missing = everything.filter(function (k) {
  return D.countries[partial.slug].calls.indexOf(k) < 0;
});
check('a partial match names what it does not cover',
  missing.length === 0 ? gaps.length === 0 : gaps.length === 1,
  missing.join(',') || 'full match');

/* ---- the two answers that are deliberately not scored -------------------- */

/* The page tells the traveller that who they are travelling with and how they
   like to travel are carried to the operator rather than scored. That is a
   promise, and this is the test of it. */
let moved = [];
const base = E.rank(D, {wants: ['wildlife'], month: 7, seed: 0});
D.party.forEach(function (p) {
  D.style.forEach(function (st) {
    const other = E.rank(D, {wants: ['wildlife'], month: 7, seed: 0,
      party: p.key, style: [st.key]});
    if (other.map(function (x) { return x.slug + ':' + x.score; }).join('|')
        !== base.map(function (x) { return x.slug + ':' + x.score; }).join('|')) {
      moved.push(p.key + '/' + st.key);
    }
  });
});
check('who you travel with never changes the ranking', !moved.length,
  moved.slice(0, 2).join(', '));

/* ---- determinism --------------------------------------------------------- */

const b = {wants: ['coast', 'culture'], month: 11, pacing: 'fortnight', seed: 3};
check('the same question gives the same answer twice',
  JSON.stringify(E.recommend(D, b)) === JSON.stringify(E.recommend(D, b)));
check('a different seed only re-orders ties',
  E.rank(D, b)[0].score === E.rank(D, Object.assign({}, b, {seed: 5}))[0].score);

/* ---- out of season is told, not hidden ----------------------------------- */

let hidden = [];
for (let month = 1; month <= 12; month++) {
  E.rank(D, {wants: ['wildlife'], month: month}).forEach(function (p) {
    const inSeason = D.countries[p.slug].months.indexOf(month) >= 0;
    if (!inSeason && !p.outOfSeason) hidden.push(p.slug + '/' + month);
  });
}
check('a country out of season is flagged rather than dropped', !hidden.length,
  hidden.slice(0, 3).join(', '));

/* ---- no dead ends -------------------------------------------------------- */

let empty = [];
lensKeys.forEach(function (k) {
  for (let month = 1; month <= 12; month++) {
    if (!E.recommend(D, {wants: [k], month: month}).picks.length) {
      empty.push(k + '/' + month);
    }
  }
});
check('every question a visitor can ask has an answer', !empty.length,
  empty.slice(0, 3).join(', '));
check('asking for nothing still answers',
  E.recommend(D, {wants: [], month: null}).picks.length === 3);

/* Three from three regions where the data allows it. */
const spread = E.recommend(D, {wants: [], month: null, seed: 0}).picks
  .map(function (p) { return D.countries[p.slug].regionKey; });
check('the three offered are from three different regions',
  new Set(spread).size === spread.length, spread.join(', '));

/* ---- the shape of a journey ---------------------------------------------- */

const pace = E.pacingFor(D, 'fortnight');
const uganda = places.uganda || places[slugs[0]];
const picked = E.suggestStages(uganda.places, {wants: ['wildlife']}, pace);
check('a journey has as many stages as the length allows',
  picked.length === pace.stages, picked.length + ' of ' + pace.stages);
check('the stages lead with what was asked for',
  (uganda.places.filter(function (p) { return p.id === picked[0]; })[0].lenses || [])
    .indexOf('wildlife') >= 0);
check('an unknown pacing key falls back rather than throwing',
  !!E.pacingFor(D, 'no-such-band'));

const st = picked.map(function (id) {
  return uganda.places.filter(function (p) { return p.id === id; })[0];
});
const rows = E.timeline(st, pace.days, 'Kampala');
check('the timeline starts on day one and ends on the last day',
  rows[0].from === 1 && rows[rows.length - 1].to === pace.days,
  rows[rows.length - 1].to + ' of ' + pace.days);
let gap = false;
for (let i = 1; i < rows.length; i++) {
  if (rows[i].from !== rows[i - 1].to + 1) gap = true;
}
check('no day is counted twice and none is missed', !gap);
check('the timeline names the operator\'s own base as the arrival',
  rows[0].label === 'Kampala');
check('an empty journey has no timeline rather than a broken one',
  E.timeline([], 12, 'Kampala').length === 0);
check('a journey too short for arrival days is still whole',
  E.timeline(st, 2, null).length === st.length);

/* ---- the name ------------------------------------------------------------ */

const named = E.name({name: 'Uganda'}, st);
check('the journey is named from its own stages', /\w/.test(named)
  && named === named.toUpperCase(), named);
check('changing a stage changes the name',
  E.name({name: 'Uganda'}, st) !== E.name({name: 'Uganda'}, st.slice(0, 2).reverse()));
check('one stage is named after itself',
  E.name({name: 'Uganda'}, [st[0]]) === st[0].title.toUpperCase());
check('no stage is named after a stop word or a verb',
  slugs.every(function (s) {
    return places[s].places.every(function (p) {
      const k = E.keyword(p.title).toLowerCase();
      return k.length > 2 && !/^(the|and|then|some|where|following|begins)$/.test(k);
    });
  }));

/* ---- what it is made of -------------------------------------------------- */

const mix = E.composition(D, st);
const sum = mix.reduce(function (t, x) { return t + x.share; }, 0);
check('the composition is a tally of the stages, not an estimate',
  Math.abs(sum - 1) < 0.001, sum.toFixed(3));
check('a stage under no lens is counted under its own heading',
  E.composition(D, [{id: 'x', group: 'Cities', lenses: []}])[0].label === 'Cities');
check('an empty journey has no composition', E.composition(D, []).length === 0);

/* ---- the link ------------------------------------------------------------ */

const state = {country: 'uganda', stages: ['wildlife', 'mountains'], month: 7,
  pacing: 'fortnight', party: 'family', wants: ['wildlife'], style: ['slow'], seed: 2};
const back = E.decode(E.encode(state));
check('a journey link rebuilds the journey exactly',
  JSON.stringify(back) === JSON.stringify(state), E.encode(state));
check('a malformed link is refused rather than half-read',
  E.decode('#/j//?m=99&d=').month === null);
check('a link with no journey in it decodes to no journey',
  E.decode('') .country === null && E.decode('#/nonsense').country === null);

/* ---- the weights are data, not code -------------------------------------- */

check('the weights come from the dataset',
  typeof D.weights.lens === 'number' && typeof D.weights.season === 'number');
const zeroed = JSON.parse(JSON.stringify(D));
zeroed.weights.season = 0;
check('changing a weight changes the ranking',
  JSON.stringify(E.rank(D, {wants: [], month: 1}).map(function (x) { return x.slug; }))
  !== JSON.stringify(E.rank(zeroed, {wants: [], month: 1}).map(function (x) { return x.slug; })));

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(function (l) { return l.indexOf('FAIL') === 0; }) ? 1 : 0);
