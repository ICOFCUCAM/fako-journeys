/* Render docs/state-language.md from the state language itself.
 *
 *     node tools/state-doc.js > docs/state-language.md
 *
 * The document is the seven-column table the brief asked for — canonical
 * state, label, explanation, transitions, tone, kind, actions — and it is
 * GENERATED because a hand-written copy of 72 states would be wrong within a
 * week and nobody would be able to tell which half.
 *
 * state-checks.js re-runs this and fails if the committed file differs, so the
 * document cannot drift from the module any more than the module can drift
 * from the code it describes. Every figure in the prose below is computed for
 * the same reason: a sentence saying "72 states" that is not counting them is
 * a sentence that will one day be wrong in public.
 */
'use strict';

const path = require('path');
const ROOT = path.join(__dirname, '..');
const L = require(path.join(ROOT, 'scripts', 'state-language.js'));

const out = [];
const w = (s) => out.push(s);

const N = L.all().length;
const TONE = L.TONE;

/* The internal collisions, counted rather than remembered. */
const owners = {};
L.all().forEach(k => {
  const i = k.indexOf(':');
  const word = k.slice(i + 1).toUpperCase();
  (owners[word] = owners[word] || []).push(k.slice(0, i));
});
const collisions = Object.keys(owners)
  .filter(x => owners[x].length > 1)
  .sort((a, b) => owners[b].length - owners[a].length || a.localeCompare(b));

w('# The Afrinkong state language');
w('');
w('**Item 4.** Generated from `scripts/state-language.js` by');
w('`node tools/state-doc.js > docs/state-language.md`. Do not edit by hand —');
w('`state-checks.js` regenerates it and fails if this file differs.');
w('');
w('> The system can distinguish **' + N + ' states**. Before this, the website');
w('> could express **one**, and it was `empty`.');
w('');
w('The published figure for the gap was 39 states across five vocabularies.');
w('That undercounted by ' + (N - 39) + ': it missed account states, auth levels,');
w('the buyback request lifecycle, risk holds, purchase plans, product state,');
w('transfer kinds, and the journey’s own six stages.');
w('');
w('## The two vocabularies');
w('');
w('A small vocabulary and an unambiguous one pull in opposite directions. They');
w('are therefore different vocabularies:');
w('');
w('| | size | job |');
w('|---|---|---|');
w('| **tones** | ' + Object.keys(TONE).length + ' | the visual language. '
  + 'Learned once, recognised everywhere |');
w('| **labels** | ' + N + ' | one per state, never shared. Precise |');
w('');
w('A customer learns six shapes and reads a specific sentence. **One word never');
w('does two jobs.**');
w('');
w('### Why that rule is not optional');
w('');
w('Internally, ' + collisions.length + ' words already carry more than one');
w('meaning:');
w('');
w('```');
collisions.forEach(word => {
  w(word.padEnd(11) + '×' + owners[word].length + '   '
    + owners[word].join(' · '));
});
w('```');
w('');
w('That is tolerable in code, where the vocabulary name disambiguates. It is');
w('not tolerable on a screen, where there is no vocabulary name — which is why');
w('the customer labels must be unique even though the internal words are not.');
w('');
w('## The ' + Object.keys(TONE).length + ' tones');
w('');
w('| tone | means | used by |');
w('|---|---|---|');
const MEANS = {
  neutral: 'a fact. Nothing is happening and nothing is wrong',
  working: 'we are doing it; it finishes without anybody',
  waiting: 'it needs a person. It will **not** finish on its own',
  done:    'finished the way it was meant to',
  ended:   'over, by choice or by time. **Not** a failure',
  broken:  'went wrong, and somebody has to look'
};
Object.keys(TONE).map(k => TONE[k]).forEach(t => {
  const n = L.all().filter(k => L.LANGUAGE[k].tone === t).length;
  w('| `' + t + '` | ' + MEANS[t] + ' | ' + n + ' states |');
});
w('');
w('### ENDED is not BROKEN');
w('');
w('The most important line in the system. An expired point, a cancelled');
w('journey, a declined quote and a closed programme are **ordinary endings**. A');
w('failed payment and a chargeback are **faults**. Painting both the same');
w('colour teaches a customer that ordinary endings are their fault, and a');
w('customer who believes that stops pressing things.');
w('');
const broken = L.all().filter(k => L.LANGUAGE[k].tone === TONE.BROKEN);
w('Only ' + broken.length + ' states out of ' + N + ' may be `broken`, and a');
w('check names them:');
w('');
broken.forEach(k => w('- `' + k + '` — ' + L.LANGUAGE[k].label));
w('');
w('`working` is the only tone that animates, because it is the only one making');
w('a claim about the future. A spinner over “we need you to confirm” is a lie');
w('told in motion.');
w('');
w('## The five kinds of state');
w('');
w('| kind | question it answers | states |');
w('|---|---|---|');
const ASKS = {
  points:  'what happened to entitlement',
  money:   'what happened to money',
  travel:  'what happened to the journey or booking',
  account: 'what the customer is permitted to do',
  system:  'what the platform is currently doing'
};
Object.keys(L.DOMAIN).map(k => L.DOMAIN[k]).forEach(d => {
  w('| **' + d + '** | ' + ASKS[d] + ' | '
    + L.all().filter(k => L.LANGUAGE[k].domain === d).length + ' |');
});
w('');
w('No vocabulary straddles two kinds, and a check enforces it — mixed domains');
w('inside one vocabulary is how “cancelled” starts meaning both the money and');
w('the journey again.');
w('');
w('## Every state');
w('');
w('Seven columns, as the brief asked: canonical state, customer label,');
w('explanation, allowed transitions, visual treatment, which kind of state it');
w('is, and what the customer can do.');
w('');

const ORDER = ['journey', 'booking', 'points', 'payment', 'buyback', 'plan',
               'account', 'auth', 'risk', 'hold', 'programme', 'product'];
const TITLE = {
  journey: 'Journey stages', booking: 'Bookings', points: 'Travel Points',
  payment: 'Payments', buyback: 'Repurchase requests', plan: 'Purchase plans',
  account: 'Accounts', auth: 'Sign-in', risk: 'Risk decisions',
  hold: 'Risk holds', programme: 'The programme', product: 'Product state'
};
const OWNER = {
  booking:   '`booking.js` `BOOKING_NEXT`',
  buyback:   '`buyback.js` `REQUEST_NEXT`',
  programme: '`points-ledger.js` `COMPLIANCE_NEXT`',
  plan:      '`purchase-plan.js` `PLAN_NEXT`',
  hold:      '`risk.js` `HOLD_NEXT`'
};

/* Every vocabulary must appear. If a new one is added to the language and not
   to ORDER, its states would silently vanish from the document — which is the
   same class of defect this whole file guards against, so it is an error. */
const known = L.all()
  .map(k => k.slice(0, k.indexOf(':')))
  .filter((v, i, a) => a.indexOf(v) === i);
const unlisted = known.filter(v => ORDER.indexOf(v) === -1);
if (unlisted.length) {
  process.stderr.write('state-doc: vocabulary not in ORDER: '
    + unlisted.join(', ') + '\n');
  process.exit(1);
}

ORDER.forEach(v => {
  const keys = L.all().filter(k => k.slice(0, k.indexOf(':')) === v);
  if (!keys.length) return;
  w('### ' + TITLE[v] + '  `' + v + ':*`');
  w('');
  w(OWNER[v]
    ? 'Transitions read from ' + OWNER[v] + '.'
    : 'No transition table exists in code for this vocabulary, so `nextOf` '
      + 'returns `null` — which is different news from “terminal”.');
  w('');
  w('| state | label | explanation | → | tone | kind | actions |');
  w('|---|---|---|---|---|---|---|');
  keys.forEach(k => {
    const d = L.LANGUAGE[k];
    const s = k.slice(k.indexOf(':') + 1);
    const n = L.nextOf(v, s);
    const nx = n === null ? '—' : (n.length ? n.join(', ') : '*terminal*');
    w('| `' + s + '` | **' + d.label + '** | ' + d.explain + ' | ' + nx
      + ' | `' + d.tone + '` | ' + d.domain + ' | ' + d.actions.join(', ') + ' |');
  });
  w('');
});

w('## How this cannot silently drift');
w('');
w('`tools/state-checks.js` runs in both directions:');
w('');
w('```');
w('module   -> language   no state exists without a sentence');
w('language -> module     no sentence exists for a state that does not');
w('language -> CSS        every tone has a treatment');
w('CSS      -> language   no treatment exists for a tone that does not');
w('language -> language   no customer label means two different things');
w('language -> code       transitions are READ from the owning module');
w('page     -> language   every state in HTML is real, and wears the right tone');
w('doc      -> language   this file is regenerated and compared');
w('```');
w('');
w('Each was verified by breaking it deliberately. Writing');
w('`data-state="journey:DAYDREAMING"` into the built page, painting');
w('`journey:PLANNING` as `broken`, and removing the stylesheet from a page that');
w('shows a state all three fail, naming the cause.');
w('');
w('## What is adopted so far');
w('');
w('**One surface: the Travel Goal on `/journey-fund`.** It is the only place on');
w('the site with a live state today — issuance is off, the wallet is');
w('deliberately unwired, and there are no bookings.');
w('');
w('The chip is server-rendered in its opening stage, so it is correct before');
w('any script runs and `fund.js` only ever moves it on. The other ' + (N - 1));
w('sentences exist so that when a state does need showing, the words and the');
w('treatment are already decided rather than invented under pressure.');
w('');
w('## What this phase did not do');
w('');
w('- No economic rule was changed, and no state was added, removed or renamed');
w('  internally.');
w('- No transition was invented. Five tables already existed and are read;');
w('  `risk.js` gained one export so its table could be read rather than copied.');
w('- Travel Points were not activated. The programme is still `DRAFT`.');
w('- Navigation was not touched.');
w('');
w('### One correction worth keeping');
w('');
w('The first draft of the language invented `goal:NO_TARGET / UNDERWAY /');
w('FUNDED` for the Travel Goal, believing it had no state vocabulary.');
w('');
w('It has had one all along. `travel-goal.js` publishes `journeyState` and its');
w('six stages, and its own comment calls them **“the vocabulary this product');
w('uses.”** Inventing a parallel set would have been exactly the defect this');
w('file exists to prevent — two vocabularies for one thing, with nothing');
w('comparing them — committed inside the module written to stop it. The six');
w('real stages are used, and `journeyStateOf()` reads the module’s answer');
w('rather than recomputing it.');

process.stdout.write(out.join('\n') + '\n');
