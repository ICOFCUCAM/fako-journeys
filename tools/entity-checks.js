/* Which entity is acting, and does the customer know.
 *
 *     node tools/entity-checks.js
 *
 * Three layers run through this product:
 *
 *     AFRINKONG    experience   explore, plan, enquire
 *     WANKONG LLC  commercial   points, agreements, the ledger, payment
 *     OPERATOR     operations   the ground, the suppliers, the local desk
 *
 * They can work together without being confused, and the way to keep them
 * unconfused is not three footers with three legal names on them. It is that
 * every act which touches a customer's money, entitlement or trip says who is
 * doing it, on the surface where it happens.
 *
 * WHAT THIS REPLACES
 *
 * A guard that classified links BY URL — a list of operator paths, forbidden in
 * certain places. Wrong twice: /cameroon is a country before it is an operator
 * base, and /contact is correct wherever the visitor is explicitly dealing with
 * that operator. A link is entity + context + position + action, and any one of
 * those alone gives the wrong answer.
 *
 * THE ONE THAT MATTERS WHEN PAYMENTS ARRIVE
 *
 * A booking or payment flow must never move a customer into the operator's desk
 * because that desk already has the infrastructure. Nothing on this site takes
 * a payment today, which is exactly why the rule is written now: the checks
 * below fail the moment a payment surface appears without naming Wankong LLC,
 * rather than after somebody has shipped one.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const E = require(path.join(ROOT, 'scripts', 'entities.js'));
const L = require(path.join(ROOT, 'scripts', 'state-language.js'));

const out = [];
function check(name, ok, detail) {
  out.push((ok ? 'PASS' : 'FAIL') + '\t' + name + '\t' + (detail || ''));
}

const company = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'tourism', 'company.json'), 'utf8'));
const operators = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'tourism', 'operators.json'), 'utf8'));

/* ---- 1. the model itself ------------------------------------------------ */

const acts = Object.keys(E.ACTS);
const orphan = acts.filter(a => !E.LAYER[E.actor(a)]);
check('every act names an entity that exists', !orphan.length,
  orphan.length ? orphan.join(', ')
    : acts.length + ' acts across ' + Object.keys(E.LAYER).length + ' layers');

/* Each layer must own something. A layer that owns no act is a box on a
   diagram rather than a party to anything. */
const idle = Object.keys(E.LAYER).filter(k =>
  !acts.some(a => E.actor(a) === k));
check('every layer actually acts', !idle.length,
  idle.length ? idle.join(', ')
    : Object.keys(E.LAYER).map(k =>
        k + '=' + acts.filter(a => E.actor(a) === k).length).join(' '));

/* ---- 2. the model agrees with the data ---------------------------------- */

check('the commercial layer is the legal entity in company.json',
  E.LAYER.wankong.legal === company.legal,
  'entities.js says ' + JSON.stringify(E.LAYER.wankong.legal)
    + ', company.json says ' + JSON.stringify(company.legal));

check('the experience layer is the trading name',
  E.LAYER.afrinkong.name === company.brand
    && E.LAYER.afrinkong.legal === null,
  company.relation);

check('the operations layer is named per country, never in the abstract',
  E.LAYER.operator.name === null && Object.keys(operators).length > 0,
  Object.keys(operators).length + ' named operations: '
    + Object.values(operators).map(o => o.name).join(', '));

/* ---- 3. MONEY IS WANKONG'S, AND ONLY WANKONG'S -------------------------
   The single most consequential line in the model. If any act that moves money
   named Afrinkong, the site would be telling a customer they are paying a
   trading name; if it named the operator, they would be told they are paying
   their supplier. */

const MONEY = ['pay', 'book', 'cancel', 'points'];
const misowned = MONEY.filter(a => E.actor(a) !== E.ENTITY.WANKONG);
check('everything that moves money or entitlement belongs to Wankong LLC',
  !misowned.length,
  misowned.length ? misowned.map(a => a + ' -> ' + E.actor(a)).join(', ')
    : MONEY.join(', ') + ' — all commercial');

check('company.json says the same thing about where money goes',
  /Wankong LLC/.test(company.money || ''),
  company.money);

/* And the site must never say a customer pays Afrinkong or pays the operator.
   Read off the built pages rather than asserted. */
function pages(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith('.') || e.name === 'node_modules') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) pages(p, acc);
    else if (e.name.endsWith('.html')) acc.push(p);
  }
  return acc;
}
const wrongPayee = [];
const PAY_TO_BRAND = /\bpay(?:ing|ment[s]?)?\s+(?:to\s+)?Afrinkong\b/i;
for (const f of pages(ROOT, [])) {
  const html = fs.readFileSync(f, 'utf8');
  if (PAY_TO_BRAND.test(html)) wrongPayee.push(path.relative(ROOT, f));
}
check('no page tells a customer they pay Afrinkong', !wrongPayee.length,
  wrongPayee.length ? wrongPayee.slice(0, 4).join(', ')
    : 'Afrinkong is a trading name; the payee is Wankong LLC');

/* ---- 4. the six that must declare --------------------------------------- */

const undeclared = E.MUST_DECLARE.filter(a => !E.ACTS[a] || !E.ACTS[a].declares);
check('every act touching money, entitlement or a trip declares its actor',
  !undeclared.length,
  undeclared.length ? undeclared.join(', ')
    : E.MUST_DECLARE.join(', '));

/* A declaration with no reason is a label. Every one has to say WHY that
   entity, because "Wankong LLC" on its own means nothing to a traveller. */
const reasonless = acts.filter(a => !(E.ACTS[a].why || '').trim());
check('every act says why that entity and not another', !reasonless.length,
  reasonless.length ? reasonless.join(', ')
    : acts.length + ' acts, each with its reason in a sentence');

/* The two-party acts name both. A booking is an agreement with one company and
   days run by another, and telling a customer only half of that is how "who do
   I call" becomes unanswerable. */
const TWO_PARTY = ['enquire', 'book', 'support'];
const halfTold = TWO_PARTY.filter(a => {
  const d = E.declare(a, 'Kamerun');
  return !d || !d.and;
});
check('the acts with two parties name both', !halfTold.length,
  halfTold.length ? halfTold.join(', ')
    : TWO_PARTY.map(a => a + ' = ' + E.declare(a, 'Kamerun').name
        + ' + ' + E.declare(a, 'Kamerun').and.name).join('; '));

/* ---- 5. classification is not by URL ------------------------------------
   The correction that produced this file. The same href must be able to come
   back with different verdicts, or the model has collapsed into a path list
   again. */

const same = { targetEntity: 'operator', surfaceEntity: 'afrinkong',
               declared: false };
const verdicts = ['body', 'nav', 'footer-nav', 'cta']
  .map(p => E.classify(Object.assign({}, same, { position: p })));
check('position changes the verdict on an identical link',
  new Set(verdicts).size > 1,
  ['body', 'nav', 'footer-nav', 'cta']
    .map((p, i) => p + '=' + verdicts[i]).join(' '));

check('an operator link on the operator’s own page is its own, not a crossing',
  E.classify({ targetEntity: 'operator', surfaceEntity: 'operator',
               position: 'cta' }) === E.VERDICT.OWN,
  'context decides, not the path');

check('a declared crossing is legitimate where an undeclared one is not',
  E.classify(Object.assign({}, same, { position: 'cta', declared: true }))
    === E.VERDICT.HANDOVER
  && E.classify(Object.assign({}, same, { position: 'cta' }))
    === E.VERDICT.MISDIRECTED,
  'declaring it is what makes it a handover rather than a misdirection');

/* ---- 6. the state language agrees about who acts ------------------------
   72 states already say WHAT is happening and which of five kinds it is. The
   entity layer says WHO. The two are orthogonal and both are needed, but they
   must not contradict: a state about entitlement or money is the commercial
   layer's, whatever else is true of it. */

const DOMAIN_ENTITY = {
  points:  E.ENTITY.WANKONG,
  money:   E.ENTITY.WANKONG,
  travel:  E.ENTITY.WANKONG,    /* the agreement; the days are operated */
  account: E.ENTITY.WANKONG,
  system:  E.ENTITY.AFRINKONG   /* the platform itself */
};
const uncovered = Object.keys(DOMAIN_ENTITY).filter(d =>
  !L.all().some(k => L.LANGUAGE[k].domain === d));
check('every kind of state maps to an acting entity', !uncovered.length,
  uncovered.length ? uncovered.join(', ')
    : Object.entries(DOMAIN_ENTITY)
        .map(([d, e]) => d + '->' + e).join(' '));

/* Decision I, restated as an entity rule: a points state may not name the
   trading name as the issuer, because the trading name issues nothing. */
const brandIssues = L.all().filter(k => {
  const s = L.LANGUAGE[k];
  if (s.domain !== 'points') return false;
  return /\bAfrinkong (?:issues|holds|owes)\b/i.test(s.label + ' ' + s.explain);
});
check('no entitlement state says the trading name issued it', !brandIssues.length,
  brandIssues.length ? brandIssues.join(', ')
    : L.all().filter(k => L.LANGUAGE[k].domain === 'points').length
      + ' entitlement states, none attributing issuance to a trading name');

/* ---- 7. THE FUTURE ONE --------------------------------------------------
   Nothing on this site takes a payment, and this is the check that makes that
   fact load-bearing rather than incidental. When a payment surface appears it
   must name Wankong LLC on itself — not in a footer, not on a terms page. */

const PAY_MARKERS = /\b(card number|cvv|expiry date|pay now|checkout|complete payment)\b/i;
const paySurfaces = [];
for (const f of pages(ROOT, [])) {
  const rel = path.relative(ROOT, f);
  const html = fs.readFileSync(f, 'utf8');
  if (!PAY_MARKERS.test(html)) continue;
  if (!/Wankong LLC/.test(html)) paySurfaces.push(rel);
}
check('any surface that takes a payment names Wankong LLC on itself',
  !paySurfaces.length,
  paySurfaces.length ? paySurfaces.join(', ')
    : 'no payment surface exists yet; this fails the day one appears '
      + 'without naming the payee');

/* ---- /trust: the model, where a customer can read it -------------------- *
 *
 * entities.js was loaded by no page. Seventeen checks, a 169-line document,
 * and no surface — a customer could not learn from this website which of three
 * companies was acting, which is the one thing the model exists to make
 * knowable. /trust is that surface, generated FROM the module.
 *
 * These guard the two ways it stops being true: it can fall behind the model,
 * and it can become unreachable. */
const TRUST = path.join(ROOT, 'trust.html');
const trust = fs.existsSync(TRUST) ? fs.readFileSync(TRUST, 'utf8') : '';

check('the entity model has a page a customer can read',
  trust.length > 0,
  trust.length ? `/trust, ${(trust.length / 1024).toFixed(1)} KB`
    : 'MISSING — the model is enforced everywhere and stated nowhere');

/* EVERY act, not most of them. The generator's first regex consumed the
   newline the next entry needed and silently took 5 of 10 — including four of
   the six where money is at stake. A short table reads exactly as completely
   as a full one, so the page is checked against ACTS rather than eyeballed. */
const actNames = Object.keys(E.ACTS);
const missingActs = actNames.filter(
  (a) => !new RegExp(`<th scope="row">${a}</th>`).test(trust));
check('every act in the model appears on the page',
  trust.length > 0 && missingActs.length === 0,
  missingActs.length ? `missing: ${missingActs.join(', ')}`
    : `all ${actNames.length} acts, each with the party that performs it`);

/* And every act that must declare is marked as such on the page, since that
   mark is the entire customer-facing consequence of MUST_DECLARE. */
const rows = trust.split(/<tr/).filter((r) => r.includes('scope="row"'));
const markedWrong = actNames.filter((a) => {
  const row = rows.find((r) => r.includes(`>${a}</th>`));
  if (!row) return true;
  return E.ACTS[a].declares !== row.includes('is-declare');
});
check('the acts marked as declaring are exactly the ones that do',
  trust.length > 0 && markedWrong.length === 0,
  markedWrong.length ? `mismatched: ${markedWrong.join(', ')}`
    : `${actNames.filter((a) => E.ACTS[a].declares).length} of ` +
      `${actNames.length} declare; ${E.MUST_DECLARE.length} of those are the ` +
      `money acts, the rest is the operator's desk naming itself`);

/* All three layers, with the company named as the company. */
check('the page names all three layers, and Wankong LLC as the company',
  trust.includes('Afrinkong') && trust.includes('Wankong LLC') &&
    /experience/i.test(trust) && /commercial/i.test(trust) &&
    /operations/i.test(trust),
  'experience, commercial, operations — and the money is the company');

/* THE TRAP THIS PAGE IS MOST LIKELY TO FALL INTO.
   operators.json gives Kamerun a url of /cameroon, and linking an operator to
   the country it works in is the exact conflation this page argues against —
   on the page that argues it. The operator's own surface, or nothing. */
const opsBlock = (trust.match(/<ul class="af-ops">[\s\S]*?<\/ul>/) || [''])[0];
const countryLinked = (opsBlock.match(/href="\/([a-z-]+)"/g) || [])
  .filter((h) => !/\/(about|contact|services|pricing)"/.test(h));
check('no ground operation is linked to the country it works in',
  countryLinked.length === 0,
  countryLinked.length ? `links a country: ${countryLinked.join(', ')}`
    : "an operator is linked to its own surface or to nothing — /cameroon is " +
      'a destination, and saying otherwise here would prove the page wrong');

/* REACHABILITY, WHICH IS NOT THE SAME AS EXISTENCE.
   /trust rendered correctly and was linked from 0 of 1,598 pages — the same
   failure as the area navigation that was present in the markup of every page
   and visible on none. A page nobody can reach has not been shipped. */
let reach = 0;
for (const f of pages(ROOT, [])) {
  if (fs.readFileSync(f, 'utf8').includes('href="/trust"')) reach++;
}
check('the page is reachable from the site, not merely present in it',
  reach > 1000,
  `linked from ${reach} page(s) — it is in the colophon, so it is on every ` +
  'Afrinkong page rather than on none');

process.stdout.write(out.join('\n') + '\n');
process.exit(out.some(l => l.indexOf('FAIL') === 0) ? 1 : 0);
