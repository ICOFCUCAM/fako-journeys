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
const fs = require("fs");
const path = require("path");

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

/* ---- Section B7: no interest, and time is not a ledger event ------------ */

/* B7 settles that a holding cannot grow because time passed. That is currently
 * true by construction rather than by enforcement — there is simply no code
 * that does it — and "true because nobody wrote it yet" is the kind of property
 * that stops being true in a hurry. These three make it a rule.
 *
 * The vocabulary check is deliberately crude: it reads the source. A field
 * called `interestRate` would be caught by nothing else in this suite, and by
 * the time it reached a balance it would be a financial product. */
const CORE = [
  "../scripts/points-ledger.js",
  "../scripts/travel-goal.js",
  "../tools/points/schema.sql",
];
const GROWTH = /\b(interest|apy|apr|yield|dividend|appreciat\w*|accrue\w*|compound\w*|rate_of_return|maturity)\b/gi;
const offenders = [];
for (const rel of CORE) {
  const src = fs.readFileSync(path.join(__dirname, rel), "utf-8");
  for (const line of src.split("\n")) {
    /* A line that NAMES the prohibition is the prohibition being documented,
       not violated. Comment markers only — a comment cannot pay interest. */
    if (/^\s*(\*|\/\/|--|#)/.test(line)) continue;
    const hit = line.match(GROWTH);
    if (hit) offenders.push(`${path.basename(rel)}: ${hit.join(",")}`);
  }
}
report(
  offenders.length === 0,
  "B7: the economic core contains no growth vocabulary outside its own comments",
  offenders.length ? offenders.join(" | ") : "no interest, apy, yield, dividend, accrual or maturity in live code"
);

/* No clock. A ledger that cannot read the time cannot pay for the passage of
 * it, which is a stronger guarantee than any rule about what the code may do
 * with a date once it has one. */
const ledgerSrc = fs.readFileSync(
  path.join(__dirname, "../scripts/points-ledger.js"), "utf-8");
const clock = ledgerSrc.split("\n").filter(
  (l) => !/^\s*(\*|\/\/)/.test(l) && /\bDate\b|\bnow\(\)|getTime|Math\.random/.test(l));
report(
  clock.length === 0,
  "B7: the ledger has no clock, so time cannot be an input to a balance",
  clock.length ? clock[0].trim().slice(0, 60) : "no Date, no now(), no randomness"
);

/* And the closed set. Every way a balance may move is one of these; none of
 * them is "time passed". If somebody adds an eleventh, this fails and they
 * have to say so out loud. */
const KIND_NAMES = Object.keys(L.KINDS).sort().join(",");
report(
  KIND_NAMES === "ADJUST_DOWN,ADJUST_UP,BUYBACK,EXPIRE,PURCHASE,REDEEM,RELEASE," +
                 "RESERVE,TRANSFER_IN,TRANSFER_OUT",
  "B7: the ways a balance can change are a closed set of ten, and time is not one",
  KIND_NAMES
);

/* ---- Section B12: the repurchase basis, and what it currently costs ----- */

/* B12 settled that repurchase pays 90% of the PURCHASE CONSIDERATION — what the
 * customer actually paid. buybackQuote() pays 90% of the ENTITLEMENT VALUE,
 * which is the mechanism B12 rejected.
 *
 * Harmless while issueRate and entitlement are both 1, and exploitable the
 * moment a promotional programme exists: profit appears when
 * issueRate x buyback.rate > 1, i.e. any bonus above 1/0.9 - 1 = 11.1%.
 * Buy at a bonus, wait out minHoldDays, claim more than you paid, repeat to the
 * annual cap.
 *
 * Not fixed — buyback is programme economics and those are on hold. Pinned so
 * it cannot ship silently, and so the number is on the record. */
const bbProg = L.PROGRAMS[DRAFT];
const bbSaved = { rate: bbProg.issueRate, status: bbProg.status };
bbProg.status = "active";
bbProg.issueRate = 1.25;
const paidMinor = 100000;                                  // $1,000
const issued = L.pointsFor(DRAFT, paidMinor);
const quote = L.buybackQuote(
  DRAFT,
  [entry("PURCHASE", issued)],
  issued, 100, 0
);
bbProg.issueRate = bbSaved.rate;
bbProg.status = bbSaved.status;

report(
  issued === 1250 && quote.payableMinor === 112500,
  "B12: the encoded repurchase basis is exploitable under a promotional programme",
  `a 25% bonus on $1,000 issues ${issued} TP and quotes $${quote.payableMinor / 100} ` +
  `— $${(quote.payableMinor - paidMinor) / 100} MORE than was paid. B12 says $900. ` +
  `Break-even bonus is 1/0.9 = 11.1%. See docs/travel-point-economics.md B12.2`
);

report(
  bbProg.issueRate === 1 && bbProg.status === "draft",
  "B12: the demonstration restored the programme it borrowed",
  `issueRate ${bbProg.issueRate}, status ${bbProg.status}`
);

/* ---- Section B14: transferability, decided but not yet applied --------- */

/* B14 settled firmly that customers may not transfer points to one another in
 * V1. The programme still says they may. This is a one-word change that is
 * blocked on nothing — it sits unmade only because programme economics are
 * under a hold, and changing a term of the economic model unprompted is what
 * that hold exists to prevent.
 *
 * When it is made, this check flips to asserting `false` and the message
 * becomes a record of when. Until then it fails loudly if anyone *relies* on
 * transferability in the meantime. */
report(
  bbProg.transferable === true,
  "B14: the programme still permits transfer, which B14 has decided against",
  "transferable: true — B14 requires false. One word, blocked on nothing, " +
  "awaiting confirmation. See docs/travel-point-economics.md B14.1"
);

/* The kinds stay whatever the programme decides: a programme that forbids
   transfer simply never emits them. Deleting the capability to enforce a policy
   would be the wrong layer. */
report(
  Object.keys(L.KINDS).includes("TRANSFER_IN") &&
    Object.keys(L.KINDS).includes("TRANSFER_OUT"),
  "B14: the ledger keeps the transfer kinds, because policy is not capability",
  "an administrative correction or a later programme still needs them"
);

/* ---- Section B16: promotional points, which the ledger cannot yet tell apart */

/* B16 settled that a purchased point and a granted one are different things and
 * the ledger must know which is which — they may carry different expiry,
 * redemption, cancellation, buyback and transfer rules.
 *
 * It cannot today. There is no promotional kind and no lot type, so once a
 * bonus is written it is indistinguishable from a paid point. ADJUST_UP is not
 * a substitute: it is an administrative correction and using it for marketing
 * grants would make every promotion look like a manual intervention in an
 * audit.
 *
 * Pinned rather than built — this is a ledger kind, a programme sub-structure,
 * and everything downstream that reads a balance. */
report(
  !Object.keys(L.KINDS).some((k) => /PROMO|BONUS|GRANT/.test(k)),
  "B16: the ledger still cannot distinguish a promotional point from a paid one",
  "no PROMOTION kind and no lot type — B16 requires the distinction. " +
  "ADJUST_UP is admin:true and is not a substitute. " +
  "See docs/travel-point-economics.md B16.2"
);

report(
  L.KINDS.ADJUST_UP && L.KINDS.ADJUST_UP.admin === true,
  "B16: ADJUST_UP stays marked admin, so it cannot quietly become the bonus kind",
  "an administrative correction and a marketing grant must not share an entry kind"
);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
