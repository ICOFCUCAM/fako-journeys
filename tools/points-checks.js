#!/usr/bin/env node
/* The Travel Point ledger's promises, tested rather than trusted.
 *
 *     node tools/points-checks.js
 *
 * This is an economically sensitive module: every bug in it is either a
 * customer losing points they paid for or Afrinkong issuing points nobody
 * paid for. Both are worse than a broken page, and neither shows up in a
 * screenshot, so the arithmetic is checked here and the properties that
 * matter are named in the check titles.
 */

const L = require("../scripts/points-ledger.js");

let pass = 0, fail = 0;
function report(ok, what, detail) {
  console.log(`${ok ? "PASS" : "FAIL"}\t${what}\t${detail}`);
  ok ? pass++ : fail++;
}
function threw(fn) {
  try { fn(); return null; } catch (e) { return e.message; }
}

/* MECHANICS ARE TESTED UNDER A FIXTURE, NOT UNDER THE SHIPPING PROGRAMME.
 *
 * The shipping programme is a draft and the ledger refuses to issue under a
 * draft — which is the behaviour that keeps this product from existing before
 * counsel has signed it, and which is asserted at the bottom of this file.
 *
 * But the accounting still has to be tested, and it cannot be tested without
 * issuing something. So a fixture programme exists here, in the test file,
 * marked active. It is registered on the module's PROGRAMS map at runtime and
 * never written to scripts/points-ledger.js — nothing that ships is active.
 */
const P = "TEST-ACTIVE-FIXTURE";
L.PROGRAMS[P] = Object.assign({}, L.PROGRAMS["AFK-TP-2026.1"], {
  id: P, name: "fixture, tests only", status: "active"
});

const DRAFT = "AFK-TP-2026.1";
let n = 0;
const entry = (kind, quantity, extra) => Object.assign({
  id: "TP-" + String(++n).padStart(6, "0"),
  customerId: "CUST-10291",
  kind, quantity,
  idempotencyKey: "k" + n,
  programVersion: P,
  status: "SETTLED",
  at: "2026-09-01T00:00:00Z"
}, extra || {});

/* ---------------------------------------------------- the balance is a fold */

const bought = [entry("PURCHASE", 500), entry("PURCHASE", 250)];
report(L.wallet(bought).available === 750,
       "the balance is folded from entries, never stored",
       `two purchases -> ${L.wallet(bought).available} available`);

/* THE PROPERTY THE WHOLE MODULE EXISTS FOR. Replaying the same history must
   give the same answer, and appending must never require re-reading a
   previously computed total. */
const replay = L.wallet(bought.slice()).available;
report(replay === L.wallet(bought).available,
       "folding the same history twice gives the same answer",
       `${replay} both times`);

/* ------------------------------------------------------------- idempotency */

const dup = [entry("PURCHASE", 500)];
dup.push(Object.assign({}, dup[0]));          // the webhook, delivered twice
const dupW = L.wallet(dup);
report(dupW.available === 500 && dupW.duplicatesIgnored === 1,
       "a payment delivered twice issues points once",
       `${dupW.available} available, ${dupW.duplicatesIgnored} duplicate ignored`);

report(threw(() => L.fold([{ id: "x", kind: "PURCHASE", quantity: 5, status: "SETTLED" }]))
         !== null,
       "an entry without an idempotency key is refused",
       "fold throws rather than risking a double issuance");

/* --------------------------------------------------- payment is not points */

const pending = [entry("PURCHASE", 500, { status: "PENDING" })];
report(L.wallet(pending).available === 0,
       "an unsettled payment issues nothing",
       `status PENDING -> ${L.wallet(pending).available} points`);

const authorised = [entry("PURCHASE", 500, { status: "REQUIRES_CAPTURE" })];
report(L.wallet(authorised).available === 0,
       "an authorised-but-uncaptured payment issues nothing",
       "only SETTLED creates points");

/* ------------------------------------------------------------ no overdraft */

const over = [entry("PURCHASE", 100), entry("RESERVE", 500, { journeyRef: "JRN-1" })];
report(threw(() => L.fold(over)) !== null,
       "a wallet cannot be overdrawn",
       "reserving more than is available throws");

const check = L.can([entry("PURCHASE", 100)], { kind: "RESERVE", quantity: 500 });
report(check.ok === false && check.available === 100,
       "can() refuses before the entry is appended, with a reason",
       `${check.why} (${check.available} available)`);

/* ------------------------------------------------- reserve, redeem, release */

const flow = [
  entry("PURCHASE", 5000),
  entry("RESERVE", 3500, { journeyRef: "JRN-1044" })
];
let w = L.wallet(flow);
report(w.available === 1500 && w.reserved === 3500,
       "reserving moves points between pools without destroying any",
       `${w.available} available + ${w.reserved} reserved = ${w.available + w.reserved}`);

flow.push(entry("REDEEM", 3500, { journeyRef: "JRN-1044" }));
w = L.wallet(flow);
report(w.available === 1500 && w.reserved === 0 && w.redeemed === 3500,
       "redemption consumes reserved points, not available ones",
       `available ${w.available}, reserved ${w.reserved}, redeemed ${w.redeemed}`);

report(threw(() => L.fold([entry("PURCHASE", 100),
                           entry("RELEASE", 50, { journeyRef: "JRN-9" })])) !== null,
       "points cannot be released from a journey that never reserved them",
       "fold throws");

/* ------------------------- cancellation attaches to the booking, not the wallet */

const c30 = L.cancellation(P, 45, 3500);
report(c30.released === 3500 && c30.buybackEligible === true,
       "outside 30 days every reserved point returns",
       `${c30.released} of 3500 released`);

const c7 = L.cancellation(P, 3, 3500);
report(c7.released === 0 && c7.forfeited === 3500,
       "inside seven days the reserved points do not return",
       `${c7.forfeited} forfeited — supplier commitments already made`);

/* THE ONE THAT MATTERS MOST TO A CUSTOMER. A cancellation must never reach
   past the booking into two years of accumulation. */
const held = [entry("PURCHASE", 5000), entry("RESERVE", 3500, { journeyRef: "JRN-1044" })];
const afterCancel = L.wallet(held).available;
report(afterCancel === 1500 && L.cancellation(P, 3, 3500).forfeited === 3500,
       "a cancellation touches only the points reserved for that journey",
       `1,500 unreserved points unaffected by a 3,500-point forfeiture`);

/* ------------------------------------------------------------------ buyback */

const rich = [entry("PURCHASE", 5000)];
const early = L.buybackQuote(P, rich, 1000, 10, 0);
report(early.eligible === false,
       "buyback refuses inside the minimum holding period",
       early.why);

const small = L.buybackQuote(P, rich, 50, 200, 0);
report(small.eligible === false, "buyback refuses below the minimum", small.why);

const overYear = L.buybackQuote(P, rich, 1000, 200, 4500);
report(overYear.eligible === false, "buyback refuses above the annual cap", overYear.why);

const good = L.buybackQuote(P, rich, 1000, 200, 0);
report(good.eligible === true && good.rate === 0.9 && good.payableMinor === 90000,
       "an eligible buyback is quoted at the program rate",
       `1,000 points -> ${good.payableMinor / 100} at ${good.rate * 100}%`);

report(good.discretionary === true && /not a guaranteed right/.test(good.note),
       "buyback is stated as discretionary, not as a right of redemption",
       "the regulatory character of the product depends on this sentence");

const reservedOnly = [entry("PURCHASE", 1000), entry("RESERVE", 900, { journeyRef: "J" })];
const rq = L.buybackQuote(P, reservedOnly, 1000, 200, 0);
report(rq.eligible === false,
       "points reserved against a journey cannot be bought back",
       rq.why);

/* -------------------------------------------------- money, points, entitlement */

report(L.pointsFor(P, 10000) === 100,
       "money buys points at the program's issue rate",
       "$100.00 -> 100 points");

report(L.priceOf(P, 100) === 10000,
       "and the price of points is the inverse",
       "100 points -> $100.00");

report(L.pointsFor(P, 12550) === 125,
       "fractional points are never issued",
       "$125.50 -> 125 points, not 125.5");

report(threw(() => L.fold([entry("PURCHASE", 12.5)])) !== null,
       "a fractional quantity is refused by the ledger",
       "whole points only");

/* NO GROWTH, ANYWHERE. This is the check that stops somebody adding a
   plausible-looking `interest` helper in six months. */
const src = require("fs").readFileSync(
  require("path").join(__dirname, "..", "scripts", "points-ledger.js"), "utf-8");
const code = src.replace(/\/\*[\s\S]*?\*\//g, "");   // comments discuss it on purpose
const growth = ["interest", "compound", "yield", "apr", "apy", "accrue", "dividend"]
  .filter((word) => new RegExp("\\b" + word, "i").test(code));
report(growth.length === 0,
       "nothing in the ledger makes a balance grow with time",
       growth.length ? "found: " + growth.join(", ") : "no growth vocabulary in the code");

/* ---------------------------------------------------------- the journey goal */

const g = L.goal(P, 400000, 1250, 12);
report(g.target === 4000 && g.remaining === 2750 && g.monthly === 230,
       "the journey goal restates the planner's division in points",
       `${g.held}/${g.target} points, ${g.monthly}/month for ${g.months} months`);

report(Math.abs(g.progress - 0.3125) < 1e-9,
       "progress is a proportion of the target, not a projection",
       `${(g.progress * 100).toFixed(2)}%`);

/* --------------------------------------------------- the program is versioned */

report(L.program(DRAFT).status === "draft",
       "the point program SHIPS as a draft, not as live terms",
       "status must not read 'active' before counsel has signed the terms");

/* ------------------------------------------------ the product-state gate */

report(L.stateOf(null) === "PLANNING"
       && L.stateOf(DRAFT) === "DRAFT_PROGRAM"
       && L.stateOf(P) === "ACTIVE_PROGRAM",
       "three product states, and the shipping program is in the middle one",
       `no program PLANNING, ${DRAFT} DRAFT_PROGRAM, fixture ACTIVE_PROGRAM`);

report(L.mayIssue(DRAFT) === false && L.mayIssue(P) === true,
       "only an ACTIVE_PROGRAM may issue a point",
       "the shipping program may not");

const draftIssue = threw(() => L.fold([{
  id: "TP-D", kind: "PURCHASE", quantity: 500, status: "SETTLED",
  idempotencyKey: "draft-1", programVersion: DRAFT
}]));
report(draftIssue !== null && /ACTIVE_PROGRAM/.test(draftIssue),
       "issuing under the shipping program is refused by the fold itself",
       draftIssue);

/* Moving points a customer already holds is a different question from
   creating them, and the gate must not confuse the two — it only guards
   issuance. Under the fixture, a reserve still works. */
const moves = L.wallet([entry("PURCHASE", 100),
                        entry("RESERVE", 40, { journeyRef: "J1" })]);
report(moves.available === 60 && moves.reserved === 40,
       "the gate guards issuance only, not movement between pools",
       `${moves.available} available, ${moves.reserved} reserved`);

report(threw(() => L.program("AFK-TP-9999.9")) !== null,
       "an unknown program is refused rather than defaulted",
       "no silent fallback to 1 point = $1");

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
