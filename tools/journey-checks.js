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

/* ---- reading a sentence -------------------------------------------------- */

/* The parser's whole claim is that it never guesses. So the tests are mostly
   about what it declines to do. */
const said = E.parse('I have 12 days in September and want wildlife and mountains', D);
check('a sentence becomes the same brief the buttons make',
  said.month === 9 && said.days === 12
  && said.wants.sort().join() === 'mountains,wildlife', JSON.stringify(said.wants));
check('a length lands in an existing band', said.pacing === 'fortnight', said.pacing);
check('it reports every field it took', said.took.length >= 4,
  said.took.map(t => t.field).join(','));
const withCountry = E.parse('two weeks in Uganda with my family', D);
check('a country in the sentence is picked up', withCountry.country === 'uganda');
check('"two weeks" is fourteen days', withCountry.days === 14, String(withCountry.days));
check('who you are travelling with is picked up', withCountry.party === 'family');
const nonsense = E.parse('zzzz qqqq wobble', D);
check('a sentence it does not understand takes nothing',
  !nonsense.wants.length && !nonsense.month && !nonsense.pacing && !nonsense.country);
check('and it says so rather than guessing', nonsense.missed.length === 1);
check('an empty sentence is not an error',
  E.parse('', D).took.length === 0 && E.parse(null, D).wants.length === 0);
check('it never invents a country that is not in the set',
  !E.parse('I want to go to Wakanda and Chad', D).country);
check('a lens is matched only on its own recorded words',
  !E.parse('I want something nice', D).wants.length);
check('every lens can be reached by at least one word',
  lensKeys.every(k => (D.lenses[k].words || []).some(w => E.parse('I want ' + w, D)
    .wants.indexOf(k) >= 0)),
  lensKeys.filter(k => !(D.lenses[k].words || []).length).join(','));
check('the parser is deterministic',
  JSON.stringify(E.parse('ten days in May, coast', D))
  === JSON.stringify(E.parse('ten days in May, coast', D)));

/* ---- how good a match is this -------------------------------------------- */

const bBrief = {wants: ['wildlife', 'mountains'], month: 9};
const bTop = E.recommend(D, bBrief).picks[0];
const bandTop = E.band(D, bBrief, bTop);
check('a match is described in words, not in a percentage',
  bandTop && !/\d+\s*%/.test(bandTop.label + bandTop.why), bandTop.label);
check('a full match on what and when is called strong',
  bandTop.matched === bandTop.asked ? bandTop.label.indexOf('Strong') === 0 : true,
  bandTop.label + ' — ' + bandTop.why);
const looser = E.recommend(D, bBrief).picks.find(p => p.matched.length < 2);
check('a partial match says how many of how many',
  !looser || /\d of the \d/.test(E.band(D, bBrief, looser).why),
  looser ? E.band(D, bBrief, looser).why : 'no partial in the top three');
check('asking for nothing is not scored as a failure',
  E.band(D, {wants: [], month: null}, E.recommend(D, {wants: []}).picks[0]).label
  === 'Where we would start');
check('out of season is said, not scored away',
  (function () {
    const m = 1;
    const row = E.rank(D, {wants: ['wildlife'], month: m}).filter(r => r.outOfSeason)[0];
    return !row || E.band(D, {wants: ['wildlife'], month: m}, row).season === false;
  })());

/* ---- carrying on over a border ------------------------------------------- */

const web = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'links.json'), 'utf8'));
const on = E.onward(D, web, 'uganda', {wants: ['wildlife']});
check('onward only crosses a real land border',
  on.every(r => r.why.some(w => w.kind === 'border')), on.map(r => r.to).join(','));
check('onward only offers countries that answer the same brief',
  on.every(r => D.countries[r.to].calls.indexOf('wildlife') >= 0));
check('an island is offered nowhere to carry on to',
  E.onward(D, web, 'seychelles', {wants: []}).length === 0);
check('a stage knows which country it is in',
  E.stageOf('rwanda~wildlife', 'uganda').country === 'rwanda'
  && E.stageOf('wildlife', 'uganda').country === 'uganda');
check('a stage at home keeps the short form',
  E.stageId('uganda', 'wildlife', 'uganda') === 'wildlife'
  && E.stageId('rwanda', 'wildlife', 'uganda') === 'rwanda~wildlife');
const two = {country: 'uganda', stages: ['wildlife', 'rwanda~safari'], month: 9,
  pacing: 'fortnight', party: null, wants: ['wildlife'], style: [], seed: 0};
check('a two-country journey survives its own link',
  JSON.stringify(E.decode(E.encode(two))) === JSON.stringify(two), E.encode(two));

/* ---- the weights are data, not code -------------------------------------- */

check('the weights come from the dataset',
  typeof D.weights.lens === 'number' && typeof D.weights.season === 'number');
const zeroed = JSON.parse(JSON.stringify(D));
zeroed.weights.season = 0;
check('changing a weight changes the ranking',
  JSON.stringify(E.rank(D, {wants: [], month: 1}).map(function (x) { return x.slug; }))
  !== JSON.stringify(E.rank(zeroed, {wants: [], month: 1}).map(function (x) { return x.slug; })));

/* ---- search over the story graph ------------------------------------------ */

/* The interesting assertions about a search are the ones about what it refuses.
   This one has no model behind it and no fuzzy matching on purpose: it can only
   answer with a country, a theme or a proper name the dataset itself already
   contains, and a word it has never seen has to come back empty rather than
   rounded to the nearest thing in stock. */

const G = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'graph.json'), 'utf8'));
const SX = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'stories.json'), 'utf8'));
const Q = require(path.join(ROOT, 'scripts', 'story-search.js'));
const rowsOf = SX.stories || [];

check('a word this dataset has never used finds nothing',
  Q.search('quantum tractors in Narnia', G, rowsOf).hits.length === 0);
check('and it says so rather than showing the nearest thing',
  /Nothing here is written about/.test(
    Q.said(Q.search('quantum tractors', G, rowsOf), G)));
check('it never returns a country the query did not lead to',
  Q.search('food in Cameroon', G, rowsOf).hits
    .every(function (h) { return h.country === 'cameroon'; }));
check('a theme and a place are both read out of one sentence',
  (function () {
    const r = Q.parse('food in Cameroon', G);
    return r.theme === 'food' && r.country === 'cameroon' && !r.missed.length;
  })());
check('a name narrows what follows it instead of widening it',
  (function () {
    const r = Q.search('history of Buea', G, rowsOf);
    const named = G.names['Buea'].in;
    return r.read.name === 'Buea'
      && r.hits.every(function (h) { return named.indexOf(h.country) >= 0; });
  })(), JSON.stringify(G.names['Buea'] && G.names['Buea'].in));
check('a name only answers with write-ups that actually say it',
  (function () {
    const r = Q.search('Bwindi', G, rowsOf);
    const at = G.names['Bwindi'].at.map(function (a) { return a.c + '/' + a.e; });
    return r.hits.length > 0 && r.hits.every(function (h) {
      return h.kind !== 'place' || at.indexOf(h.country + '/' + h.category) >= 0;
    });
  })());
const everyUrl = {};
rowsOf.forEach(function (s) { everyUrl[s.url] = true; });
Object.keys(G.countries).forEach(function (slug) {
  everyUrl['/portrait/' + slug] = true;
  const places = G.countries[slug].places || {};
  Object.keys(places).forEach(function (k) { everyUrl[places[k].u] = true; });
});
check('every address a search offers is one the build actually wrote',
  ['food in Cameroon', 'Bwindi', 'heritage in Ethiopia', 'Kampala', 'wildlife']
    .every(function (q) {
      return Q.search(q, G, rowsOf).hits.every(function (h) { return everyUrl[h.url]; });
    }));
check('it never invents a country', Object.keys(G.countries).length === 22
  && ['Wakanda', 'Zamunda', 'Genovia'].every(function (n) {
    return Q.parse(n, G).country === null;
  }));
check('the same question gives the same answer twice',
  JSON.stringify(Q.search('craft in Kenya', G, rowsOf).hits)
  === JSON.stringify(Q.search('craft in Kenya', G, rowsOf).hits));
check('it says what it did not understand',
  /Nothing matched "narnia"/.test(Q.said(Q.search('food in Narnia', G, rowsOf), G)));
check('an empty search asks nothing and finds nothing',
  Q.search('', G, rowsOf).hits.length === 0 && Q.said(Q.search('', G, rowsOf), G) === '');

/* "This month" is derived, never scheduled: no event in this project has a
   date, so the only true thing to say is which countries the files call good. */
const offBook = [];
for (let mo = 1; mo <= 12; mo++) {
  Q.monthly(mo, G).forEach(function (slug) {
    if ((G.countries[slug].months || []).indexOf(mo) < 0) offBook.push(slug + '@' + mo);
  });
}
check('a month only lists countries whose own file says that month',
  !offBook.length, offBook.join(',') || 'all twelve months checked');
check('no month is empty, and none is all twenty-two',
  (function () {
    for (var m = 1; m <= 12; m++) {
      var n = Q.monthly(m, G).length;
      if (!n || n === Object.keys(G.countries).length) return false;
    }
    return true;
  })());

/* ---- what the product counts --------------------------------------------- */

/* The event layer is worth testing for the opposite reason to the engine: not
   that it records the right things, but that it cannot record the wrong ones.
   The rules are only worth as much as the code that enforces them, so these run
   against the real module, loaded with the real schema as it was inlined into
   the built page — not a copy the test wrote for itself. */

const evBlock = page.match(
  /<script type="application\/json" id="af-events">([\s\S]*?)<\/script>/);
check('the built page carries the event schema', !!evBlock);

const evFile = JSON.parse(fs.readFileSync(path.join(ROOT, 'tourism', 'events.json'), 'utf8'));
const shipped = evBlock ? JSON.parse(evBlock[1]) : {events: {}};
function canonical(obj) {
  return Object.keys(obj || {}).sort().map(function (k) {
    return k + ':' + (obj[k] || []).slice().sort().join('+');
  }).join('|');
}
check('the page ships the schema the dataset holds',
  canonical(shipped.events) === canonical(evFile.events));
check('the page ships the rules and nothing else',
  Object.keys(shipped).join(',') === 'events', Object.keys(shipped).join(','));

/* events.js reads its schema from the document, because on a page that is where
   it is. Standing one up is the whole of the browser this module needs. */
global.document = {getElementById: function (id) {
  return id === 'af-events' ? {textContent: JSON.stringify(shipped)} : null;
}};
const V = require(path.join(ROOT, 'scripts', 'events.js'));

const SENTENCE = 'twelve days in September, wildlife and mountains';
const names = Object.keys(evFile.events);

check('an event the schema does not name is dropped',
  V.shape('page_view', {country: 'uganda'}) === null
  && V.shape('', {}) === null && V.shape('__proto__', {}) === null);
check('a property not named under its event is stripped',
  JSON.stringify(V.shape('meet_strand_opened', {strand: 'food', country: 'uganda'}))
  === '{"strand":"food"}',
  JSON.stringify(V.shape('meet_strand_opened', {strand: 'food', country: 'uganda'})));
check('a property named under its event travels',
  V.shape('journey_composed', {country: 'uganda', stages: 3}).country === 'uganda');

/* The one that matters. The journey builder has a box a visitor types a
   sentence into; try to push that sentence out through every door there is. */
check('the sentence a visitor types cannot travel under any name',
  names.every(function (n) {
    const props = {};
    (evFile.events[n] || []).forEach(function (k) { props[k] = SENTENCE; });
    props.sentence = SENTENCE;
    props.text = SENTENCE;
    return JSON.stringify(V.shape(n, props)) === '{}';
  }));
check('free text is refused whatever it is called',
  V.shape('journey_revealed', {band: 'we thought you might like Uganda, because'})
  && Object.keys(V.shape('journey_revealed',
    {band: 'we thought you might like Uganda, because'})).length === 0);
check('a value that is not a short token or a small number is refused',
  JSON.stringify(V.shape('journey_composed',
    {country: {slug: 'uganda'}, stages: 1e9, month: NaN, pacing: ['a']})) === '{}');
check('every property a schema names is described',
  names.every(function (n) {
    return (evFile.events[n] || []).every(function (k) {
      return Object.prototype.hasOwnProperty.call(evFile.$props, k);
    });
  }));

/* Drift: an event the site emits that the schema never heard of would be
   silently dropped, which is the right failure at runtime and the wrong one to
   discover there. */
const emitted = [];
fs.readdirSync(path.join(ROOT, 'scripts')).filter(function (f) {
  return f.endsWith('.js') && f !== 'events.js';
}).forEach(function (f) {
  const src = fs.readFileSync(path.join(ROOT, 'scripts', f), 'utf8');
  let hit;
  const re = /\btrack\(\s*'([a-z_]+)'/g;
  while ((hit = re.exec(src))) if (emitted.indexOf(hit[1]) < 0) emitted.push(hit[1]);
});
const placeSrc = fs.readFileSync(path.join(ROOT, 'tools', 'tourism', 'places.py'), 'utf8');
if (/track\('place_page_opened'/.test(placeSrc)) emitted.push('place_page_opened');
check('every event the site emits is named in the schema',
  emitted.every(function (n) { return names.indexOf(n) >= 0; }),
  emitted.filter(function (n) { return names.indexOf(n) < 0; }).join(',') || emitted.length + ' emitted');
check('every event the schema names is actually emitted',
  names.every(function (n) { return emitted.indexOf(n) >= 0; }),
  names.filter(function (n) { return emitted.indexOf(n) < 0; }).join(','));

/* Nothing leaves, and nothing is kept between two page-loads. */
const evSrc = fs.readFileSync(path.join(ROOT, 'scripts', 'events.js'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '');
check('the event layer has no way to reach the network',
  !/\b(fetch|XMLHttpRequest|sendBeacon|WebSocket|EventSource|import\s*\()/.test(evSrc));
check('the event layer mints and stores no identifier',
  !/\b(localStorage|sessionStorage|indexedDB|cookie|crypto|Math\.random|Date\.now)\b/
    .test(evSrc));

let sent = 0;
V.sink(null);
const payload = V.track('atlas_country_opened', {country: 'rwanda', region: 'east'});
check('with no destination configured an event validates and stops there',
  payload && payload.country === 'rwanda' && sent === 0);
V.sink(function (name, props) { sent += 1; check.last = [name, props]; });
V.track('atlas_country_opened', {country: 'rwanda', region: 'east', extra: 'x'});
check('a destination receives only what survived validation',
  sent === 1 && JSON.stringify(check.last[1]) === '{"country":"rwanda","region":"east"}',
  JSON.stringify(check.last && check.last[1]));
V.sink(function () { throw new Error('a badly behaved destination'); });
let broke = false;
try { V.track('atlas_place_opened', {country: 'kenya'}); } catch (e) { broke = true; }
check('a destination that throws does not break the page', !broke);
V.sink(null);
V.track('page_view', {country: 'kenya'});
check('an event that was refused is not counted',
  !Object.prototype.hasOwnProperty.call(V.counted(), 'page_view'));
check('what was counted can be read back', V.counted().atlas_country_opened === 2,
  JSON.stringify(V.counted()));

/* Do Not Track and Global Privacy Control stop the counting too: a count that
   is kept is data that is held, whatever it was meant for. */
const realNav = Object.getOwnPropertyDescriptor(global, 'navigator');
function says(signal) {
  Object.defineProperty(global, 'navigator', {value: signal, configurable: true});
}
says({globalPrivacyControl: true});
const before = V.counted().atlas_place_opened || 0;
let afterSink = 0;
V.sink(function () { afterSink += 1; });
check('a visitor who has said no is not counted and not sent',
  V.refused() && V.track('atlas_place_opened', {country: 'kenya'}) === null
  && (V.counted().atlas_place_opened || 0) === before && afterSink === 0);
says({doNotTrack: '1'});
check('Do Not Track is honoured as well',
  V.refused() && V.track('atlas_place_opened', {country: 'kenya'}) === null);
if (realNav) Object.defineProperty(global, 'navigator', realNav);
V.sink(null);
check('with no signal set, counting resumes',
  !V.refused() && V.track('atlas_place_opened', {country: 'kenya'}) !== null);

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(function (l) { return l.indexOf('FAIL') === 0; }) ? 1 : 0);
