/* The state language cannot drift from the states it describes.
 *
 *     node tools/state-checks.js
 *
 * WHAT THIS IS GUARDING AGAINST
 *
 * scripts/state-language.js is a second description of something the code
 * already knows. Every second description drifts — this session has spent most
 * of its time finding pairs that had to agree and nothing compared them, from
 * PROMOTION in the module but not the schema, to a tier called "Afrinkong
 * Signature" on one side of a link and "signature" on the other.
 *
 * A state language is the most drift-prone thing yet built here, because it
 * touches twelve vocabularies in six modules and a stylesheet. So it is
 * written to be checkable and then checked in every direction:
 *
 *     module -> language    no state exists without a sentence
 *     language -> module    no sentence exists for a state that does not
 *     language -> CSS       every tone has a treatment
 *     CSS -> language       no treatment exists for a tone that does not
 *     language -> language  no customer label means two different things
 *     language -> code      transitions are READ from the owning module
 *     page -> language      every state written into HTML is a real one
 *
 * The last one is the point of the whole exercise. A page may only show a
 * state the language knows, in the tone the language chose.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const L = require(path.join(ROOT, 'scripts', 'state-language.js'));
const Points = require(path.join(ROOT, 'scripts', 'points-ledger.js'));
const Booking = require(path.join(ROOT, 'scripts', 'booking.js'));
const Buyback = require(path.join(ROOT, 'scripts', 'buyback.js'));
const Account = require(path.join(ROOT, 'scripts', 'account.js'));
const Risk = require(path.join(ROOT, 'scripts', 'risk.js'));
const Plan = require(path.join(ROOT, 'scripts', 'purchase-plan.js'));

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

const values = (v) => Array.isArray(v) ? v.slice() : Object.values(v);

/* THE MAP FROM VOCABULARY NAME TO THE MODULE THAT OWNS IT.
   This is the only list in the repository that says which module is
   authoritative for which set of states, and every check below reads it. */
const VOCABULARIES = {
  'points':    values(Points.STATES).concat(values(Points.TRANSFER_KINDS)),
  'payment':   values(Points.PAYMENT_STATES),
  'programme': values(Points.COMPLIANCE_STATES),
  'product':   values(Points.PRODUCT_STATE),
  'booking':   values(Booking.BOOKING_STATES),
  'buyback':   values(Buyback.REQUEST_STATES),
  'account':   values(Account.ACCOUNT_STATES),
  'auth':      values(Account.AUTH),
  'risk':      values(Risk.DECISIONS),
  'hold':      values(Risk.HOLD_STATES),
  'plan':      values(Plan.PLAN_STATES),
  /* Read off travel-goal.js rather than typed here. It publishes the six
     stages beside every goal it builds, and its own comment calls them "the
     vocabulary this product uses" — so this list is whatever that module
     says it is, and a stage added there fails check 1 until it is described. */
  'journey':   require(path.join(ROOT, 'scripts', 'travel-goal.js'))
                 .build(480000, 12, 0, new Date('2026-08-21')).journeyStates
};

/* ---- 1. every state the system can be in has a sentence ---------------- */

const missing = [];
let stateCount = 0;
Object.keys(VOCABULARIES).forEach(vocab => {
  VOCABULARIES[vocab].forEach(state => {
    stateCount++;
    if (!L.describe(vocab, state)) missing.push(vocab + ':' + state);
  });
});
check('every state a module can produce has a customer sentence',
  !missing.length,
  missing.length ? missing.length + ' without one: ' + missing.slice(0, 6).join(', ')
    : stateCount + ' states across ' + Object.keys(VOCABULARIES).length
      + ' vocabularies, all described');

/* ---- 2. and nothing is described that does not exist -------------------- */

const phantom = L.all().filter(k => {
  const i = k.indexOf(':');
  const vocab = k.slice(0, i), state = k.slice(i + 1);
  return !VOCABULARIES[vocab] || VOCABULARIES[vocab].indexOf(state) === -1;
});
check('every sentence describes a state that really exists', !phantom.length,
  phantom.length ? phantom.join(', ')
    : L.all().length + ' entries, none of them describing a state nothing '
      + 'can reach');

/* ---- 3. THE RULE THE BRIEF ASKED FOR IN SO MANY WORDS -------------------
   "Never use one word to represent multiple meanings merely because it looks
   simpler." The system ALREADY breaks this internally: measured across the
   twelve vocabularies, ten words carry more than one meaning and between them
   they occupy 22 of the state slots. SETTLED means three different things and
   so does REJECTED.

   That is tolerable inside the code, where the vocabulary name disambiguates.
   It is not tolerable on a screen, where there is no vocabulary name — so the
   customer-facing labels must be unique even though the internal words are
   not. This check is the whole reason the language is a table rather than a
   prettifier. */

const byLabel = {};
L.all().forEach(k => {
  const label = L.LANGUAGE[k].label;
  (byLabel[label] = byLabel[label] || []).push(k);
});
const shared = Object.keys(byLabel).filter(l => byLabel[l].length > 1);
check('no customer label is used for two different states', !shared.length,
  shared.length
    ? shared.map(l => JSON.stringify(l) + ' <- ' + byLabel[l].join(' + ')).join(' | ')
    : L.all().length + ' distinct sentences for ' + L.all().length + ' states; '
      + 'internally 10 words are reused, and none of that reaches a reader');

/* Show the internal collisions as a measurement rather than a failure: they
   are a fact about the code, and the check that matters is the one above. */
const owners = {};
Object.keys(VOCABULARIES).forEach(v =>
  VOCABULARIES[v].forEach(s => {
    const w = String(s).toUpperCase();
    (owners[w] = owners[w] || []).push(v);
  }));
/* Asserted as a SET rather than a count. A count passes when one collision is
   removed and another appears, which is the shape of a regression that looks
   like standing still. Adding the `journey` vocabulary added PLANNING to this
   list and the check caught it on the first run — which is the only reason it
   is written down rather than assumed.

   These eleven are tolerated because the vocabulary name disambiguates them in
   code and the customer never sees them: `product:PLANNING` is the platform in
   planning mode, `journey:PLANNING` is a person planning a trip, and their
   customer labels are "Planning only" and "Planning this journey". RESERVED
   now means three things and SETTLED still means three. A twelfth entry here
   is not forbidden — it is a decision, and this line is where it gets made. */
const KNOWN_COLLISIONS = ['ACCEPTED', 'ACTIVE', 'APPROVED', 'CANCELLED',
  'CLOSED', 'PLANNING', 'REDEEMED', 'REJECTED', 'REQUESTED', 'RESERVED',
  'SETTLED'];
const collided = Object.keys(owners).filter(w => owners[w].length > 1).sort();
const surprise = collided.filter(w => KNOWN_COLLISIONS.indexOf(w) === -1);
const gone = KNOWN_COLLISIONS.filter(w => collided.indexOf(w) === -1);
check('the internal collisions are exactly the ones we know about',
  !surprise.length && !gone.length,
  surprise.length || gone.length
    ? (surprise.length ? 'new: ' + surprise.join(', ') + ' ' : '')
      + (gone.length ? 'no longer colliding: ' + gone.join(', ') : '')
    : collided.length + ' words carry more than one meaning in code, and none '
      + 'of the ambiguity reaches a reader: '
      + collided.map(w => w + '×' + owners[w].length).join(' '));

/* ---- 4. tones ---------------------------------------------------------- */

const TONES = Object.keys(L.TONE).map(k => L.TONE[k]);
const badTone = L.all().filter(k => TONES.indexOf(L.LANGUAGE[k].tone) === -1);
check('every state resolves to one of the six tones', !badTone.length,
  badTone.length ? badTone.join(', ') : TONES.join(' '));

const css = fs.readFileSync(path.join(ROOT, 'styles', 'states.css'), 'utf8');
const cssTones = [...css.matchAll(/\.af-state--([a-z]+)\b/g)]
  .map(m => m[1])
  .filter((v, i, a) => a.indexOf(v) === i)
  .sort();
check('the stylesheet paints exactly the tones the language declares',
  cssTones.length === TONES.length
    && TONES.slice().sort().every((t, i) => cssTones[i] === t),
  'language [' + TONES.slice().sort().join(' ') + '] vs css [' + cssTones.join(' ') + ']');

/* Every tone must actually be used, or it is a treatment nobody can reach. */
const usedTones = TONES.filter(t => L.all().some(k => L.LANGUAGE[k].tone === t));
check('no tone exists that no state uses', usedTones.length === TONES.length,
  TONES.filter(t => usedTones.indexOf(t) === -1).join(', ')
    || TONES.map(t => t + '=' + L.all().filter(k => L.LANGUAGE[k].tone === t).length)
       .join(' '));

/* ---- 5. ENDED IS NOT BROKEN -------------------------------------------
   The distinction the whole tone system exists to protect. An ordinary ending
   must never be painted as a fault, so the states allowed to be `broken` are
   named here and nothing else may join them without this line changing. */

const MAY_BE_BROKEN = [
  'payment:failed', 'payment:charged_back',
  'buyback:REJECTED', 'risk:REJECT', 'hold:REJECTED'
];
const wronglyBroken = L.all().filter(k =>
  L.LANGUAGE[k].tone === L.TONE.BROKEN && MAY_BE_BROKEN.indexOf(k) === -1);
check('nothing that merely ended is painted as broken', !wronglyBroken.length,
  wronglyBroken.length ? wronglyBroken.join(', ')
    : MAY_BE_BROKEN.length + ' faults out of ' + L.all().length
      + '; expiry, cancellation, refusal and closure are all `ended`');

/* The converse: an expiry or a cancellation is an ending, and if one of them
   ever drifts into `broken` the check above catches it — but if one drifts
   into `done` the customer is congratulated for losing something. */
const ENDINGS = ['points:EXPIRED', 'points:CANCELLED', 'booking:CANCELLED',
                 'booking:REJECTED', 'buyback:LAPSED', 'buyback:DECLINED',
                 'buyback:REFUSED', 'account:CLOSED', 'programme:CLOSED',
                 'programme:RETIRED', 'plan:STOPPED', 'payment:refunded'];
const notEnded = ENDINGS.filter(k => L.LANGUAGE[k] &&
  L.LANGUAGE[k].tone !== L.TONE.ENDED);
check('every ordinary ending is toned as an ending', !notEnded.length,
  notEnded.length ? notEnded.map(k => k + '=' + L.LANGUAGE[k].tone).join(', ')
    : ENDINGS.length + ' endings, none of them congratulated and none alarmed');

/* ---- 6. domains -------------------------------------------------------- */

const DOMAINS = Object.keys(L.DOMAIN).map(k => L.DOMAIN[k]);
const badDomain = L.all().filter(k => DOMAINS.indexOf(L.LANGUAGE[k].domain) === -1);
check('every state says which of the five kinds it is', !badDomain.length,
  badDomain.length ? badDomain.join(', ')
    : DOMAINS.map(d => d + '=' + L.all().filter(k =>
        L.LANGUAGE[k].domain === d).length).join(' '));

/* A vocabulary must not straddle domains: `booking:*` is travel, all of it.
   Mixed domains inside one vocabulary is how "cancelled" starts meaning both
   the money and the journey again. */
const straddle = Object.keys(VOCABULARIES).filter(v => {
  const ds = VOCABULARIES[v]
    .map(s => (L.describe(v, s) || {}).domain)
    .filter((d, i, a) => d && a.indexOf(d) === i);
  return ds.length > 1;
});
check('no vocabulary straddles two kinds of state', !straddle.length,
  straddle.length
    ? straddle.map(v => v + ' spans ' + VOCABULARIES[v]
        .map(s => (L.describe(v, s) || {}).domain)
        .filter((d, i, a) => a.indexOf(d) === i).join('+')).join(', ')
    : Object.keys(VOCABULARIES).length + ' vocabularies, each one about a '
      + 'single subject');

/* ---- 7. transitions are read, never copied ----------------------------- */

const TABLE_OWNERS = {
  booking: 'booking.js BOOKING_NEXT',
  buyback: 'buyback.js REQUEST_NEXT',
  programme: 'points-ledger.js COMPLIANCE_NEXT',
  plan: 'purchase-plan.js PLAN_NEXT',
  hold: 'risk.js HOLD_NEXT'
};
const notWired = Object.keys(TABLE_OWNERS).filter(v => !L.TABLES[v]);
check('every transition table the language uses is the module’s own',
  !notWired.length,
  notWired.length ? notWired.join(', ') + ' not exported'
    : Object.keys(TABLE_OWNERS).map(v => v + ' <- ' + TABLE_OWNERS[v]).join('; '));

/* And every transition must land on a state that exists in the same
   vocabulary, which is the check that would catch a table gaining a target
   the language never heard of. */
const badTarget = [];
Object.keys(TABLE_OWNERS).forEach(v => {
  VOCABULARIES[v].forEach(s => {
    (L.nextOf(v, s) || []).forEach(t => {
      if (VOCABULARIES[v].indexOf(t) === -1) badTarget.push(v + ':' + s + ' -> ' + t);
    });
  });
});
check('every transition lands on a state in the same vocabulary',
  !badTarget.length,
  badTarget.length ? badTarget.join(', ')
    : Object.keys(TABLE_OWNERS).reduce((n, v) =>
        n + VOCABULARIES[v].reduce((m, s) =>
          m + (L.nextOf(v, s) || []).length, 0), 0) + ' transitions, all resolving');

/* A vocabulary with no table returns null rather than [] — "nobody wrote one
   down" is different news from "this state is terminal", and collapsing them
   would let a missing table read as a finished one. */
check('a vocabulary with no table says so rather than claiming terminal',
  L.nextOf('points', 'AVAILABLE') === null && L.nextOf('booking', 'REDEEMED') !== null,
  'points has no transition table in code and nextOf returns null, not []');

/* ---- 8. Decision I: a point never shows a cash value ------------------- */

const MONEY_WORDS = /\b(worth|cash|value|balance|\$|USD|refund)\b/i;
const priced = L.all().filter(k => {
  if (L.LANGUAGE[k].domain !== L.DOMAIN.POINTS) return false;
  return MONEY_WORDS.test(L.LANGUAGE[k].label)
      || MONEY_WORDS.test(L.LANGUAGE[k].explain);
});
check('no entitlement state names a cash value', !priced.length,
  priced.length ? priced.join(', ')
    : L.all().filter(k => L.LANGUAGE[k].domain === L.DOMAIN.POINTS).length
      + ' points states, none of them naming money — Decision I');

/* Nor may a buyback label call itself a refund of the purchase price: the
   distinction is settled and it is the one counsel is most exposed on. */
const asRefund = L.all().filter(k =>
  /buyback|repurchase/i.test(k) && /\brefund/i.test(
    L.LANGUAGE[k].label + ' ' + L.LANGUAGE[k].explain));
check('no repurchase is described as a refund', !asRefund.length,
  asRefund.length ? asRefund.join(', ')
    : 'repurchase is a separate transaction, never a reversal of a purchase');

/* ---- 9. actions -------------------------------------------------------- */

const ACTIONS = Object.keys(L.ACTION).map(k => L.ACTION[k]);
const badAction = [];
L.all().forEach(k => {
  const a = L.LANGUAGE[k].actions;
  if (!Array.isArray(a) || !a.length) { badAction.push(k + ' (none)'); return; }
  a.forEach(x => { if (ACTIONS.indexOf(x) === -1) badAction.push(k + ' -> ' + x); });
});
check('every state offers only actions the language defines', !badAction.length,
  badAction.length ? badAction.slice(0, 5).join(', ')
    : ACTIONS.length + ' named actions; no surface can invent a verb');

/* A broken state that offers nothing to do is a dead end with a red mark on
   it, which is the worst screen a product can show. */
const helpless = L.all().filter(k =>
  L.LANGUAGE[k].tone === L.TONE.BROKEN &&
  L.LANGUAGE[k].actions.every(a => a === L.ACTION.NONE || a === L.ACTION.WAIT));
check('nothing is shown as broken without a way forward', !helpless.length,
  helpless.length ? helpless.join(', ')
    : 'every fault offers retrying, contacting us, or both');

/* ---- 10. the journey stage is READ, never recomputed -------------------
   The first draft of the language invented `goal:NO_TARGET / UNDERWAY /
   FUNDED` and derived them from `target` and `remaining`. travel-goal.js had
   published `journeyState` and its six stages all along, calling them in its
   own comment "the vocabulary this product uses".

   Two derivations of one fact agree on the day they are written and disagree
   the first time either changes, and the reader is shown whichever the
   surface happened to ask. So `journeyStateOf` reads the module's answer, and
   this check proves it reads rather than computes: given a goal object whose
   numbers say one thing and whose journeyState says another, the language
   must follow the journeyState. */

const G = require(path.join(ROOT, 'scripts', 'travel-goal.js'));
const contradictory = { target: 4800, remaining: 0, journeyState: 'TRAVELLING' };
check('the journey stage is read from the goal, not recomputed from it',
  L.journeyStateOf(contradictory) === 'TRAVELLING',
  'numbers say funded, journeyState says TRAVELLING, language says '
    + L.journeyStateOf(contradictory));

/* And on real goals the two must line up, or the panel and the chip beside it
   disagree in front of a reader. */
const real = [
  [G.build(480000, 12, 0, new Date('2026-08-21')), 'PLANNING'],
  [G.build(480000, 12, 480000, new Date('2026-08-21')), 'FUNDED']
];
const off = real.filter(r => L.journeyStateOf(r[0]) !== r[1]);
check('the goal module and the state language agree on every real goal',
  !off.length,
  off.length ? off.map(r => 'expected ' + r[1] + ', got ' + L.journeyStateOf(r[0])).join(' | ')
    : 'an unfunded goal is PLANNING and a funded one is FUNDED, and the '
      + 'language did not decide either');

/* The goal's own `display.funded` string and the language's FUNDED label are
   two sentences about one fact, and both reach the same panel. */
const fundedGoal = real[1][0];
check('the funded panel and the funded chip say the same thing',
  !!(fundedGoal.display && fundedGoal.display.funded)
    === (L.journeyStateOf(fundedGoal) === 'FUNDED'),
  'module display: ' + JSON.stringify((fundedGoal.display || {}).funded)
    + ' / language label: '
    + JSON.stringify(L.describe('journey', 'FUNDED').label));

/* ---- 11. THE PAGES ----------------------------------------------------- */

function pages(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith('.') || e.name === 'node_modules') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) pages(p, acc);
    else if (e.name.endsWith('.html')) acc.push(p);
  }
  return acc;
}
const html = pages(ROOT, []);
const unknownOnPage = [];
const untonedOnPage = [];
let onPage = 0;
html.forEach(f => {
  const src = fs.readFileSync(f, 'utf8');
  if (src.indexOf('data-state=') === -1) return;
  const rel = path.relative(ROOT, f);
  for (const m of src.matchAll(/data-state="([^"]+)"/g)) {
    onPage++;
    const k = m[1], i = k.indexOf(':');
    const d = i > 0 ? L.describe(k.slice(0, i), k.slice(i + 1)) : null;
    if (!d) { unknownOnPage.push(rel + ' -> ' + k); continue; }
    /* and the tone written next to it must be the tone the language chose */
    const near = src.slice(Math.max(0, m.index - 200), m.index + 200);
    if (near.indexOf('af-state--' + d.tone) === -1) {
      untonedOnPage.push(rel + ' -> ' + k + ' should be ' + d.tone);
    }
  }
});
check('every state written into a page is one the language knows',
  !unknownOnPage.length,
  unknownOnPage.length ? unknownOnPage.slice(0, 5).join(', ')
    : onPage + ' state(s) rendered across the site');
check('every state on a page wears the tone the language chose',
  !untonedOnPage.length,
  untonedOnPage.length ? untonedOnPage.slice(0, 5).join(', ')
    : 'no page may repaint a state it did not decide');

/* Any page that renders a state has to link the stylesheet, or the chip is
   unstyled text and the whole tone system is decoration nobody sees. */
const unlinked = html.filter(f => {
  const src = fs.readFileSync(f, 'utf8');
  return src.indexOf('data-state="') >= 0
    && src.indexOf('/styles/states.css') === -1;
}).map(f => path.relative(ROOT, f));
check('every page that shows a state links the state stylesheet', !unlinked.length,
  unlinked.length ? unlinked.slice(0, 5).join(', ')
    : 'the tone is always painted where a state is shown');

/* ---- 12. the document is the module, rendered -------------------------
   docs/state-language.md carries all 72 states in seven columns. A document
   like that is wrong within a week if anybody maintains it by hand, and the
   half that is wrong is not identifiable by reading it. So it is generated,
   and this regenerates it and compares — the same relationship the language
   has with the code, one level up. */

const { execFileSync } = require('child_process');
const docPath = path.join(ROOT, 'docs', 'state-language.md');
let fresh = null;
try {
  fresh = execFileSync(process.execPath,
    [path.join(ROOT, 'tools', 'state-doc.js')], { encoding: 'utf8' });
} catch (e) {
  check('the state document can be regenerated', false,
    'tools/state-doc.js exited non-zero: ' + (e.message || '').split('\n')[0]);
}
if (fresh !== null) {
  const onDisk = fs.existsSync(docPath) ? fs.readFileSync(docPath, 'utf8') : '';
  const same = onDisk === fresh;
  /* Name the first differing line rather than only saying "differs": a diff
     of a 310-line generated file is not something anybody wants to eyeball. */
  let where = '';
  if (!same) {
    const a = onDisk.split('\n'), b = fresh.split('\n');
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] !== b[i]) {
        where = ' first differs at line ' + (i + 1) + ': committed '
          + JSON.stringify((a[i] || '').slice(0, 60)) + ' vs generated '
          + JSON.stringify((b[i] || '').slice(0, 60));
        break;
      }
    }
  }
  check('the committed state document matches the language', same,
    same ? fresh.split('\n').length + ' lines, regenerated and identical'
      : 'run `node tools/state-doc.js > docs/state-language.md`.' + where);
}

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
