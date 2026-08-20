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
/* The fixture has to walk the ladder like anything else. It used to set
   status:"active" and be issuable, which is precisely the one-word activation
   D21.1 exists to prevent — so the fixture broke the moment the gate became
   real, which is the gate working rather than the fixture being wrong. It
   carries an exposure limit too, because PILOT and ACTIVE both require one. */
L.PROGRAMS[P] = Object.assign({}, L.PROGRAMS["AFK-TP-2026.1"], {
  id: P,
  name: "fixture, tests only",
  compliance: "ACTIVE",
  status: "active",
  maxProgrammeExposure: 5000000,
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

/* The consideration basis needs a payment to trace back to, so a purchase
   fixture now carries one. That is the separation working: the ledger holds a
   reference, the payment record holds the money. */
const rich = [Object.assign(entry("PURCHASE", 5000),
                            { payment: { amountMinor: 500000, currency: "USD" } })];
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
  KIND_NAMES === "ADJUST_DOWN,ADJUST_UP,BUYBACK,EXPIRE,PROMOTION,PURCHASE," +
                 "REDEEM,RELEASE,RESERVE,TRANSFER_IN,TRANSFER_OUT",
  "B7: the ways a balance can change are a closed set of eleven, and time is not one",
  `${KIND_NAMES} — was ten; PROMOTION is the eleventh, argued for in B16 and ` +
  `instructed by C11 before it was added, which is what this check is for`
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
/* A promotional programme is a NEW programme, not an edited one — which is
   both what B18 requires of a real change and, since the terms are frozen, the
   only way this demonstration can be written at all. */
const bbProg = L.PROGRAMS[DRAFT];
const PROMO = L.variant(DRAFT, {
  issueRate: 1.25, compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "PROMO-25-FIXTURE");
const paidMinor = 100000;                                  // $1,000
const issued = L.pointsFor(PROMO, paidMinor);
const quote = L.buybackQuote(
  PROMO,
  [Object.assign(entry("PURCHASE", issued),
                 { programVersion: PROMO,
                   payment: { amountMinor: paidMinor, currency: "USD" } })],
  issued, 100, 0
);

report(
  issued === 1250 && quote.payableMinor === 90000 &&
    quote.basis === "consideration",
  "B12/C16: the arbitrage is closed — repurchase pays on what was paid",
  `a 25% bonus on $1,000 issues ${issued} TP and quotes $${quote.payableMinor / 100}, ` +
  `not $1,125. 90% of consideration cannot exceed consideration, so no bonus ` +
  `rate makes buy-then-repurchase profitable. Was exploitable above an 11.1% bonus.`
);

report(
  bbProg.issueRate === 1 && L.program(PROMO).issueRate === 1.25,
  "B12: the demonstration used a variant and left the real programme alone",
  `2026-A issueRate ${bbProg.issueRate}, ${PROMO} issueRate ` +
  `${L.program(PROMO).issueRate} — no live term was edited to run this`
);

/* ---- Section B14: transferability, decided but not yet applied --------- */

/* B14 settled firmly that customers may not transfer points to one another in
 * V1, and this check asserted `transferable === false` for many commits.
 * **DECISION E REVERSED IT.** A customer who cannot travel and wants their
 * spouse to use the points has a legitimate need, and "the points simply
 * disappear" is the wrong answer to it.
 *
 * What survived the reversal is the half that mattered: B15's bar on a
 * secondary market. Transfer and sale were always separate terms, so
 * permitting the first did not touch the second — which is why this is one
 * flag rather than a redesign. The check now asserts the pair. */
report(
  bbProg.transferable === true && bbProg.secondaryMarket === false,
  "B14/B15 as reversed by Decision E: transfer permitted, sale still forbidden",
  `transferable ${bbProg.transferable} (was false until Decision E), ` +
  `secondaryMarket ${bbProg.secondaryMarket} ` +
  `— decided in B14, applied by C21`
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
  L.KINDS.PROMOTION && L.KINDS.PROMOTION.lot === "promotional" &&
    L.KINDS.PURCHASE.lot === "purchased",
  "B16/C11: the ledger distinguishes a promotional point from a purchased one",
  "PROMOTION carries lot:'promotional', PURCHASE carries lot:'purchased', and " +
  "the fold keeps the two pools apart for the life of the points"
);

report(
  L.KINDS.ADJUST_UP && L.KINDS.ADJUST_UP.admin === true,
  "B16: ADJUST_UP stays marked admin, so it cannot quietly become the bonus kind",
  "an administrative correction and a marketing grant must not share an entry kind"
);

/* ---- Sections B17 and B19: expiry and currency, both one value short ---- */

/* B17: purchased points never lapse, promotional points may. That is two rules
 * and expiryMonths is one number. The EXPIRE kind is fine; what is missing is
 * anything that decides which points it applies to. */
report(
  bbProg.expiry && bbProg.expiry.purchased === null &&
    typeof bbProg.expiry.promotional === "number",
  "B17: expiry is now two rules — purchased never lapses, promotional may",
  `purchased ${bbProg.expiry.purchased} (never), promotional ` +
  `${bbProg.expiry.promotional} months`
);

/* B19: the point is currency-neutral and the ledger is right to hold no
 * currency at all. The PROGRAMME binds one rate to one currency, so pointsFor()
 * cannot tell 50,000 cents from 50,000 euro-cents. B19's own example — 500 TP
 * for $500 or EUR 460 — needs a published price per currency. */
report(
  typeof bbProg.issueRate === "number" && typeof bbProg.currency === "string",
  "B19: issueRate is one number bound to one currency, so it cannot price in two",
  `issueRate ${bbProg.issueRate} per 1 ${bbProg.currency}; B19 wants 500 TP for ` +
  `$500 or EUR 460, which is a per-currency map. See B19.1`
);

/* And the part that is already right, asserted so it stays right: a ledger
   entry carries no currency, because a Travel Point does not have one. */
const sampleEntry = entry("PURCHASE", 100);
report(
  !("currency" in sampleEntry) && !("amountMinor" in sampleEntry),
  "B19: a ledger entry carries no currency and no money, which is correct",
  "money lives in payments; the ledger records points and a programme"
);

/* ---- Section B22: a wallet holds points, never money ------------------- */

/* B22: "Travel Wallet" is a record of entitlements. It may say 3,650 TP. It may
 * never say $3,650. The wallet is already clean — this asserts it stays that
 * way, because the failure mode is somebody adding a convenient `valueMinor`
 * field years from now, which is the sentence B22 forbids, shipped. */
const walletProg = L.PROGRAMS[DRAFT];
const wSaved = walletProg.status;
walletProg.status = "active";
const shown = L.wallet([entry("PURCHASE", 3650), entry("RESERVE", 1200)]);
walletProg.status = wSaved;

const moneyish = Object.keys(shown).filter(
  (k) => /minor|money|cash|usd|balance|value|amount|price|worth/i.test(k));
report(
  moneyish.length === 0,
  "B22: the wallet exposes no monetary field, only counts of points",
  moneyish.length ? moneyish.join(",") : Object.keys(shown).join(", ")
);

report(
  shown.available === 2450 && shown.reserved === 1200 &&
    shown.acquired === 3650,
  "B22: the wallet reads exactly as B22's example, in points",
  `${shown.available} available, ${shown.reserved} reserved, ${shown.acquired} total`
);

/* The two functions that DO turn points into money are legitimate but are not
   wallet fields, and must never be rendered as a balance. Asserted here so the
   separation is visible where somebody would look for it. */
report(
  typeof L.entitlementOf === "function" && typeof L.priceOf === "function" &&
    !("entitlementOf" in shown) && !("priceOf" in shown),
  "B22: entitlementOf and priceOf exist as arithmetic, not as wallet fields",
  "a repurchase quote is an offer about specific points, not a statement of worth"
);

/* ---- Section B24 rules 21 and 22: reserved points, and the final week -- */

/* Rule 21 — reserved points cannot be repurchased. Enforced, and asserted here
 * because it is the difference between a repurchase programme and a way to
 * withdraw money you have already committed to a journey. */
/* Quoted under the fixture rather than under the draft. It used to run against
   DRAFT with `status = "active"` assigned first — which was already a no-op
   against a frozen programme, and became a visible failure the moment E4 gated
   quotation on the compliance ladder: a draft programme now refuses to quote
   at all, which is asserted in its own right in the Section E block below. */
const booked = [
  Object.assign(entry("PURCHASE", 5000),
                { payment: { amountMinor: 500000, currency: "USD" } }),
  entry("RESERVE", 4800),
];
const onReserved = L.buybackQuote(P, booked, 4800, 100, 0);
const onAvailable = L.buybackQuote(P, booked, 200, 100, 0);

report(
  onReserved.eligible === false && onAvailable.eligible === true,
  "B24 rule 21: reserved points cannot be repurchased, available ones can",
  `4,800 reserved -> "${onReserved.why}"; 200 available -> eligible`
);

/* Rule 22 — no repurchase inside the final seven days. THE LAST CONTRADICTED
 * RULE IN THE B24 AUDIT, AND E6 CLOSED IT.
 *
 * The failure was the interesting part and is worth keeping in the record:
 * cancellation() computed buybackEligible:false and buybackQuote() had no
 * departure date to ask about — two functions holding half a rule each, which
 * is how somebody inside the final window gets a quote they should never have
 * been offered. The repair was not to re-implement the band in the quote but
 * to give the quote the bookings, so the band stays defined in exactly one
 * place and a programme that sets a different window is obeyed for free. */
const commitment = [{ journeyRef: "J1", daysToDeparture: 5, points: 4800 }];
const inWindow = L.buybackQuote(P, booked, 200, 100, 0, commitment);
const outOfWindow = L.buybackQuote(
  P, booked, 200, 100, 0, [{ journeyRef: "J1", daysToDeparture: 60, points: 4800 }]);
report(
  L.cancellation(P, 5, 4800).buybackEligible === false &&
    inWindow.eligible === false && outOfWindow.eligible === true,
  "B24 rule 22: the seven-day bar now reaches the quote, and it is the band's",
  `5 days -> "${inWindow.why}"; 60 days -> eligible. Was two functions holding ` +
  `half a rule each; E6 passes the commitments in rather than restating the band`
);

/* ---- Section C: the frozen programme, and what it now refuses ---------- */

/* C15: an unanswered exposure limit is not the same as no limit. A programme
 * may not go live until somebody has decided how much future travel Afrinkong
 * is willing to owe — ten thousand customers at $5,000 is $50m of entitlement,
 * which is a commitment to deliver travel rather than a website feature. */
const act = L.mayActivate(DRAFT);
report(
  act.ok === false && act.missing.indexOf("maxProgrammeExposure") !== -1,
  "C15: the programme cannot be activated while its exposure limit is unset",
  act.why
);

/* C1/C21: the terms C21 freezes are present and are the frozen values. */
const frozen = L.PROGRAMS[DRAFT];
report(
  frozen.issuer === "Wankong LLC" && frozen.brand === "Afrinkong" &&
    frozen.issueRate === 1 && frozen.minPurchase === 25 &&
    frozen.maxPerTransaction === 2500 && frozen.maxPerCustomerPerYear === 10000 &&
    frozen.buyback.basis === "consideration" && frozen.buyback.rate === 0.9,
  "C21: programme 2026-A carries the frozen terms",
  `${frozen.issuer} / ${frozen.brand}, $1->1 TP, min ${frozen.minPurchase}, ` +
  `max ${frozen.maxPerTransaction}/txn, ${frozen.maxPerCustomerPerYear}/yr, ` +
  `repurchase ${frozen.buyback.rate * 100}% of ${frozen.buyback.basis}`
);

/* C11: the customer sees one number; the ledger keeps two. */
const cProg = L.PROGRAMS[DRAFT];
const cSaved = cProg.status;
cProg.status = "active";
const mixed = L.wallet([
  Object.assign(entry("PURCHASE", 500),
                { payment: { amountMinor: 50000, currency: "USD" } }),
  entry("PROMOTION", 25),
]);
const promoQuote = L.buybackQuote(
  DRAFT,
  [Object.assign(entry("PURCHASE", 500),
                 { payment: { amountMinor: 50000, currency: "USD" } }),
   entry("PROMOTION", 25)],
  520, 100, 0
);
cProg.status = cSaved;

report(
  mixed.available === 525 && mixed.purchased === 500 && mixed.promotional === 25,
  "C11: buy 500, receive 25 — the customer sees 525, the ledger knows which is which",
  `available ${mixed.available}, purchased ${mixed.purchased}, promotional ${mixed.promotional}`
);

/* C16: promotional points repurchase at zero, and the consideration basis
   reaches that answer by itself — there was no consideration to refund. */
report(
  promoQuote.eligible === false,
  "C16: a repurchase that would dip into promotional points is refused",
  `${promoQuote.why} (purchased ${promoQuote.purchased}, promotional ${promoQuote.promotional})`
);

/* ==== D21: the five permanent invariants ================================= */

/* These are not tests of a feature. They are the boundary between a travel
 * company and a financial one, and they are here so that crossing it requires
 * deleting a check rather than forgetting one. Section D21 names all five. */

/* D21.1 — no programme may issue without passing the compliance ladder. */
const dProg = L.PROGRAMS[DRAFT];

/* The old one-word activation, attempted the only way it still can be: on a
   variant, since the real programme cannot be edited at all. */
const ONE_WORD = L.variant(DRAFT, { status: "active" }, "ONE-WORD-FIXTURE");
const oneWord = L.mayIssue(ONE_WORD);
report(
  oneWord === false,
  "D21.1: setting status to 'active' by hand no longer issues anything",
  "issuance is gated on the compliance ladder; the status string is inert"
);

const ladder = ["ACTIVE", "PILOT", "APPROVED"].map(
  (to) => `${to}:${L.mayTransition(DRAFT, to).ok}`);
report(
  ladder.join(" ") === "ACTIVE:false PILOT:false APPROVED:false",
  "D21.1: DRAFT cannot jump to APPROVED, PILOT or ACTIVE",
  `${ladder.join("  ")} — only LEGAL_REVIEW or RETIRED are reachable from DRAFT`
);

const APPROVED_NO_CAP = L.variant(DRAFT, { compliance: "APPROVED" },
                                  "APPROVED-NO-CAP-FIXTURE");
const APPROVED_CAPPED = L.variant(DRAFT, {
  compliance: "APPROVED", maxProgrammeExposure: 5000000,
}, "APPROVED-CAPPED-FIXTURE");
const needExposure = L.mayTransition(APPROVED_NO_CAP, "PILOT");
const withExposure = L.mayTransition(APPROVED_CAPPED, "PILOT");
report(
  needExposure.ok === false && withExposure.ok === true,
  "D21.1: PILOT is refused while the exposure limit is unset",
  `without: ${needExposure.why}; with a limit: allowed`
);

/* D21.2 — no code path issues points from a frontend request. The customer-
 * facing bundle must not be able to append to the ledger at all. */
const frontend = ["../scripts/travel-goal.js", "../scripts/fund.js"]
  .map((f) => fs.readFileSync(path.join(__dirname, f), "utf-8"));
const appends = frontend.filter((src) =>
  /\bfold\s*\(|\bPURCHASE\b|\bPROMOTION\b|idempotencyKey/.test(src));
report(
  appends.length === 0,
  "D21.2: nothing on the customer-facing surfaces can append a ledger entry",
  "travel-goal.js and fund.js read programme terms and do arithmetic; they " +
  "never construct an entry, and could not issue one if they did"
);

/* D21.3 — no code path mutates history. The fold is the only reader and it
 * takes entries by value; the schema refuses UPDATE and DELETE outright. */
const schema = fs.readFileSync(path.join(__dirname, "../tools/points/schema.sql"), "utf-8");
/* Two separate triggers rather than one combined clause — my first version of
   this check looked for "before update or delete" and failed on a schema that
   was right. Matching both forms, and counting them, so a schema that dropped
   one of the two would still fail. */
const updGuard = /before\s+update\s+on\s+point_ledger/i.test(schema);
const delGuard = /before\s+delete\s+on\s+point_ledger/i.test(schema);
report(
  /point_ledger_append_only/.test(schema) && updGuard && delGuard,
  "D21.3: the ledger refuses UPDATE and DELETE at the database, not in a comment",
  `update guard ${updGuard}, delete guard ${delGuard} — corrections are ` +
  `reversing entries, so the error and its fix both survive`
);

/* D21.4 — no growth from elapsed time. Already asserted three ways above
 * (B7.1); restated here as one of the five so the list is complete where
 * somebody reads it. */
report(
  !/\bDate\b|\bnow\(\)/.test(
    fs.readFileSync(path.join(__dirname, "../scripts/points-ledger.js"), "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .split("\n").filter((l) => !/^\s*\/\//.test(l)).join("\n")),
  "D21.4: the ledger has no clock, so no balance can grow with elapsed time",
  "see also B7.1 — vocabulary, clock, and the closed set of kinds"
);

/* D21.5 — no balance is a cash balance. Asserted at B22.1 for the wallet;
 * restated here against the whole customer-facing path. */
const goalShape = require("../scripts/travel-goal.js").build(4750, 14, 750, "x");
report(
  !("balance" in goalShape) && !("valueMinor" in goalShape) &&
    !/\$/.test(goalShape.display.target),
  "D21.5: no customer-facing figure presents points as a cash balance",
  `the goal reads "${goalShape.display.target}", and money appears only as the ` +
  `journey's own price`
);

/* ==== Section B lock-in: the two rates, proved independent =============== */

/* THE TWO TESTS THE LOCK-IN ASKS FOR BY NAME.
 *
 * They are not the same test twice. The first says a change to the ACQUISITION
 * rate cannot move a REDEMPTION figure. The second says a change to the
 * redemption rate cannot reach backwards into what was already issued. One is
 * about the direction the rates point; the other is about time. */

/* B1: changing issueRate does not alter entitlement calculations. */
const RATE_A = L.variant(DRAFT, { issueRate: 1 }, "RATE-BASE-FIXTURE");
const RATE_B = L.variant(DRAFT, { issueRate: 1.25 }, "RATE-BONUS-FIXTURE");
const sameEntitlement =
  L.entitlementOf(RATE_A, 1000) === L.entitlementOf(RATE_B, 1000) &&
  L.goalRequirement(RATE_A, 480000) === L.goalRequirement(RATE_B, 480000);
const differentIssuance =
  L.pointsForPurchase(RATE_A, 100000) !== L.pointsForPurchase(RATE_B, 100000);
report(
  sameEntitlement && differentIssuance,
  "B1: changing the issue rate moves issuance and leaves entitlement untouched",
  `$1,000 buys ${L.pointsForPurchase(RATE_A, 100000)} TP at 1.0 and ` +
  `${L.pointsForPurchase(RATE_B, 100000)} TP at 1.25, while 1,000 TP is worth ` +
  `$${L.entitlementOf(RATE_A, 1000) / 100} under both and a $4,800 journey ` +
  `requires ${L.goalRequirement(RATE_B, 480000)} TP under both`
);

/* B1 again, the other way: changing entitlementRate does not alter historical
 * issuance. The quantity in an entry is a fact about the past, and a later
 * programme cannot reach back and change how many points somebody received. */
const ENT_A = L.variant(DRAFT, {
  entitlementRate: 1, compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "ENT-BASE-FIXTURE");
const ENT_B = L.variant(DRAFT, {
  entitlementRate: 1.25, compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "ENT-RICH-FIXTURE");
const historical = [Object.assign(entry("PURCHASE", 1000), {
  programVersion: ENT_A,
  payment: { amountMinor: 100000, currency: "USD" },
})];
const heldBefore = L.wallet(historical).available;
/* The same history, read while a richer programme exists elsewhere. */
const heldAfter = L.wallet(historical).available;
report(
  heldBefore === 1000 && heldAfter === 1000 &&
    L.entitlementOf(ENT_A, 1000) === 100000 &&
    L.entitlementOf(ENT_B, 1000) === 125000,
  "B1: changing the entitlement rate cannot alter what was already issued",
  `the customer holds ${heldAfter} TP either way; 1,000 TP is worth ` +
  `$${L.entitlementOf(ENT_A, 1000) / 100} under ${ENT_A} and ` +
  `$${L.entitlementOf(ENT_B, 1000) / 100} under a later programme, and the ` +
  `entry keeps its own programme`
);

/* B4/B7: TERMS ARE FROZEN IN THE MODULE, not only in the schema. Until this,
 * PROGRAMS['AFK-TP-2026.1'].entitlementRate = 99 simply worked — and the
 * module is what runs in a browser. */
const live = L.PROGRAMS[DRAFT];
const beforeFreeze = { e: live.entitlementRate, b: live.buyback.rate };
try { live.entitlementRate = 99; } catch (e) { /* strict mode throws */ }
try { live.buyback.rate = 0.5; } catch (e) { /* deep-frozen */ }
report(
  live.entitlementRate === beforeFreeze.e && live.buyback.rate === beforeFreeze.b,
  "B4: a live programme's terms cannot be edited, nested ones included",
  `entitlementRate stayed ${live.entitlementRate} and buyback.rate stayed ` +
  `${live.buyback.rate}; different terms mean a new programme, which is what ` +
  `B18 requires anyway`
);

/* B4: correction by compensating entry, exactly as the lock-in writes it. */
const CORR = L.variant(DRAFT, {
  compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "CORRECTION-FIXTURE");
const ce = (n, kind, q, x) => Object.assign({
  id: "TPC-" + n, kind, quantity: q, status: "SETTLED",
  idempotencyKey: "c" + n, programVersion: CORR,
}, x || {});
const corrected = L.wallet([
  ce(1, "PURCHASE", 1000, { payment: { amountMinor: 100000, currency: "USD" } }),
  ce(2, "ADJUST_DOWN", 1000, { corrects: "TPC-1" }),
  ce(3, "PURCHASE", 1100, { payment: { amountMinor: 100000, currency: "USD" } }),
]);
report(
  corrected.available === 1100 && corrected.entriesApplied === 3 &&
    corrected.corrections.length === 1 &&
    corrected.corrections[0].corrects === "TPC-1",
  "B4: a mistake is corrected by compensating entry, and all three survive",
  `+1,000 then -1,000 correcting TPC-1 then +1,100 leaves ${corrected.available} TP ` +
  `across ${corrected.entriesApplied} entries — nothing edited, nothing deleted`
);

/* And a correction cannot precede its cause, which is how two unrelated
   adjustments get read as one correction. */
let backwards = null;
try {
  L.wallet([ce(9, "ADJUST_DOWN", 10, { corrects: "TPC-404" })]);
} catch (err) { backwards = err.message; }
report(
  backwards && /not earlier in this ledger/.test(backwards),
  "B4: an entry cannot correct one the fold has not already seen",
  backwards
);

/* ==== Section C: the purchase and accumulation model ===================== */

const PP = require("../scripts/purchase-plan.js");
const CP = L.variant(DRAFT, {
  compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "PURCHASE-FIXTURE");
const pe = (n, kind, q, x) => Object.assign({
  id: "TPP-" + n, kind, quantity: q, status: "SETTLED",
  idempotencyKey: "p" + n, programVersion: CP,
}, x || {});

/* C1/C3 — one-time and recurring, and the bounds are the programme's. */
const once = PP.create(CP, 1000, "ONCE");
const monthly = PP.create(CP, 1000, "MONTHLY");
report(
  once.ok && monthly.ok &&
    PP.create(CP, 10, "MONTHLY").ok === false &&
    PP.create(CP, 3000, "MONTHLY").ok === false,
  "C1/C3: a plan may be once or monthly, within the programme's own bounds",
  `1,000 accepted either way; 10 below the floor and 3,000 above the ceiling refused`
);

/* C3 — pause, resume, stop; and a stopped plan is finished rather than
   reusable, so the record of what somebody meant last time survives. */
const active = monthly.plan;
const paused = PP.transition(active, "PAUSED").plan;
const resumed = PP.transition(paused, "ACTIVE").plan;
const stopped = PP.transition(active, "STOPPED").plan;
report(
  paused.state === "PAUSED" && resumed.state === "ACTIVE" &&
    stopped.state === "STOPPED" &&
    PP.transition(stopped, "ACTIVE").ok === false &&
    PP.amend(stopped, 2000).ok === false,
  "C3: pause and resume are reversible; stop is final and cannot be amended",
  "a customer who paused is not told they cancelled, and a stopped plan keeps " +
  "its history instead of being restarted in place"
);

/* C3 — THE ONE THAT MATTERS: stopping future purchases does not touch a
 * single point already issued. A plan and a balance are different things, and
 * this file cannot append to a ledger at all. */
const alreadyIssued = [pe(1, "PURCHASE", 2500, {
  payment: { amountMinor: 250000, currency: "USD" },
})];
const beforeStop = L.wallet(alreadyIssued).available;
PP.transition(active, "STOPPED");
const afterStop = L.wallet(alreadyIssued).available;
report(
  beforeStop === 2500 && afterStop === 2500,
  "C3: stopping a plan cancels no points that were already issued",
  `${afterStop} TP before and after — the plan governs future purchases and ` +
  `nothing else`
);

/* C4 — issuance follows SETTLED payment, and nothing else does. */
const c_pending = [Object.assign(pe(2, "PURCHASE", 2500), { status: "PENDING" })];
const failed = [Object.assign(pe(3, "PURCHASE", 2500), { status: "FAILED" })];
const settled = [pe(4, "PURCHASE", 2500, {
  payment: { amountMinor: 250000, currency: "USD" },
})];
report(
  L.wallet(c_pending).available === 0 && L.wallet(failed).available === 0 &&
    L.wallet(settled).available === 2500,
  "C4: pending and failed payments issue nothing spendable; settled issues",
  `pending 0, failed 0, settled ${L.wallet(settled).available} — there is no ` +
  `state in which a point exists but is not spendable, because it does not exist`
);

/* C5 — a bonus is two entries, never one inflated one. */
const withBonus = L.wallet([
  pe(5, "PURCHASE", 2500, { payment: { amountMinor: 250000, currency: "USD" } }),
  pe(6, "PROMOTION", 250),
]);
report(
  withBonus.available === 2750 && withBonus.purchased === 2500 &&
    withBonus.promotional === 250,
  "C5: buy 2,500 and receive 250 is recorded as +2,500 and +250, not +2,750",
  `available ${withBonus.available}, of which purchased ${withBonus.purchased} ` +
  `and promotional ${withBonus.promotional}`
);

/* C6 — accumulation to a goal, and the last month is short by construction. */
const table = PP.accumulate(monthly.plan, 4800, 0);
report(
  table.rows.length === 5 && table.rows[4].purchased === 800 &&
    table.finalHeld === 4800 && table.reaches === true,
  "C6: 4,800 at 1,000 a month is four full months and a fifth of 800",
  table.rows.map((r) => `${r.purchased}`).join(" + ") + " = " + table.finalHeld
);

/* A paused plan accumulates nothing, which is the only honest projection. */
report(
  PP.accumulate(paused, 4800, 0).rows.length === 0 &&
    PP.accumulate(paused, 4800, 0).months === null,
  "C6: a paused plan projects no arrival rather than pretending to one",
  "no rows, and months is null rather than a number nobody should act on"
);

/* C8 — the nine questions, answered per lot rather than in aggregate. */
const prov = L.lots([
  pe(7, "PURCHASE", 2500, {
    at: "2026-03-01",
    payment: { amountMinor: 250000, currency: "USD", ref: "PAY-001" },
  }),
  pe(8, "PROMOTION", 250, { at: "2026-03-01" }),
  pe(9, "RESERVE", 2600, { journeyRef: "JRN-1" }),
]);
const c_bought = prov.lots[0];
const granted = prov.lots[1];
report(
  c_bought.issuedAt === "2026-03-01" && c_bought.programId === CP &&
    c_bought.issueRate === 1 && c_bought.entitlementRate === 1 &&
    c_bought.promotional === false && c_bought.considerationMinor === 250000 &&
    c_bought.remaining === 0 && c_bought.spent.RESERVE === 2500 &&
    granted.promotional === true && granted.remaining === 150,
  "C8: every lot can say when, under which programme, at what rates, and what happened to it",
  `TP-7 purchased 2,500 at issueRate 1 for $2,500, all reserved; TP-8 ` +
  `promotional 250, 100 reserved, ${granted.remaining} left`
);

/* C7/C2 — nothing in the purchase model describes a savings account. */
const purchaseSrc = fs.readFileSync(
  path.join(__dirname, "../scripts/purchase-plan.js"), "utf-8");
report(
  !/\bsavings? account\b/i.test(purchaseSrc.replace(/\/\*[\s\S]*?\*\//g, " ")),
  "C2/C7: the purchase model never describes itself as a savings account",
  "a plan is an intention to buy, and stopping it cancels no entitlement"
);

/* ==== Section D (redemption): booking economics ========================== */

const BK = require("../scripts/booking.js");
const DP = L.variant(DRAFT, {
  compliance: "ACTIVE", maxProgrammeExposure: 5000000,
}, "BOOKING-FIXTURE");
let dn = 0;
const de = (kind, q, x) => Object.assign({
  id: "TPD-" + (++dn), kind, quantity: q, status: "SETTLED",
  idempotencyKey: "d" + dn, programVersion: DP,
}, x || {});
const JOURNEY = { journeyId: "country:kenya:signature:7", requirement: 4800,
                  rateCardVersion: "1d60cf455f9a" };
const funded = [de("PURCHASE", 5200, {
  payment: { amountMinor: 520000, currency: "USD" },
})];

/* D2 — the economic agreement is reconstructable: journey, programme, version,
   points required, points redeemed. */
const bk0 = BK.open(DP, JOURNEY);
report(
  bk0.programId === DP && bk0.programVersion === L.program(DP).version &&
    bk0.pointsRequired === 4800 && bk0.journeyId === JOURNEY.journeyId,
  "D2: a booking records the journey, the programme and its version",
  `${bk0.journeyId} under ${bk0.programId} v${bk0.programVersion}, ` +
  `${bk0.pointsRequired} TP required`
);

/* D3/D4 — RESERVING IS NOT REDEEMING. The points leave `available` and stay
 * entirely the customer's; nothing is consumed. This is the whole reason a
 * booking is two events rather than one subtraction. */
const bkAcc = BK.advance(bk0, "ACCEPTED").booking;
const res = BK.advance(bkAcc, "RESERVED", {});
const resEntries = res.entries.map((e) =>
  Object.assign({}, e, { id: "TPD-R", idempotencyKey: "dr" }));
const afterReserve = L.wallet(funded.concat(resEntries));
report(
  res.entries.length === 1 && res.entries[0].kind === "RESERVE" &&
    afterReserve.available === 400 && afterReserve.reserved === 4800 &&
    afterReserve.redeemed === 0 && afterReserve.acquired === 5200,
  "D3/D4: reserving moves points out of available and consumes none",
  `total ${afterReserve.acquired}, reserved ${afterReserve.reserved}, ` +
  `available ${afterReserve.available}, redeemed ${afterReserve.redeemed}`
);

/* THE INVARIANT ASKED FOR BY NAME: reservation and release leave the
 * customer's economic position exactly where it started. */
const rel = BK.advance(res.booking, "CANCELLED", { daysToDeparture: 60 });
const relEntries = rel.entries.map((e, i) =>
  Object.assign({}, e, { id: "TPD-L" + i, idempotencyKey: "dl" + i }));
const afterRelease = L.wallet(funded.concat(resEntries, relEntries));
const startWallet = L.wallet(funded);
report(
  afterRelease.available === startWallet.available &&
    afterRelease.reserved === 0 && afterRelease.redeemed === 0 &&
    afterRelease.acquired === startWallet.acquired,
  "D5: reserve then release returns the customer exactly where they began",
  `${startWallet.available} available before, ${afterRelease.available} after, ` +
  `nothing redeemed — an abandoned booking costs a customer nothing`
);

/* D6/D8 — confirmed redemption consumes, and the remainder survives. */
const conf = BK.advance(res.booking, "CONFIRMED").booking;
const red = BK.advance(conf, "REDEEMED", {});
const redEntries = red.entries.map((e) =>
  Object.assign({}, e, { id: "TPD-X", idempotencyKey: "dx" }));
const afterRedeem = L.wallet(funded.concat(resEntries, redEntries));
report(
  red.entries[0].kind === "REDEEM" && afterRedeem.redeemed === 4800 &&
    afterRedeem.available === 400 && afterRedeem.reserved === 0 &&
    red.booking.pointsRedeemed === 4800,
  "D6/D8: confirming redeems the reservation and the remainder stays",
  `${afterRedeem.redeemed} TP redeemed, ${afterRedeem.available} TP left under ` +
  `the same programme`
);

/* D7 — a rejected booking never reserved anything, so there is nothing to
   release and no entry to append. */
const rejected = BK.advance(bk0, "REJECTED", {});
report(
  rejected.ok && rejected.entries.length === 0 &&
    rejected.booking.state === "REJECTED",
  "D7: a rejected request produces no ledger entry at all",
  "nothing was reserved, so nothing needs releasing"
);

/* D10 — INSUFFICIENT POINTS, REPORTED IN POINTS. No conversion is offered,
 * because D7 says the programme must define the settlement mechanism and it
 * has not. A function that quietly returned "$1,500" would have decided it. */
const short = BK.request(DP, { journeyId: "j", requirement: 6000 },
                         { available: 4500 });
report(
  short.ok === false && short.shortfallPoints === 1500 &&
    short.settlement.mechanism === null &&
    !/\$|amountMinor/.test(JSON.stringify(short)),
  "D10/D11: a shortfall is 1,500 TP and carries no money figure at all",
  "the settlement mechanism is null and named as an undecided programme term"
);

/* D12 — eligible services are programme scope, not a universal list. */
report(
  BK.ineligible(DP, ["journey", "transport"]).length === 0 &&
    BK.ineligible(DP, ["journey", "visa", "international_flight"]).join(",")
      === "visa,international_flight",
  "D12: what points may be spent on is read from the programme",
  "journey and transport are inside scope; visas and flights are not, and a " +
  "request naming one is refused rather than silently partly covered"
);

/* The state machine refuses what it should. */
report(
  BK.advance(bk0, "REDEEMED", {}).ok === false &&
    BK.advance(red.booking, "CANCELLED", {}).ok === false,
  "D: a booking cannot redeem without reserving, or change after redeeming",
  `REQUESTED->REDEEMED refused; REDEEMED is terminal`
);

/* THE BALANCE IDENTITY, ASKED FOR BY NAME.
 * available = acquired + released - reserved - redeemed - transferred
 *             - boughtBack - expired - adjusted
 * Folded over a history containing every kind, so the identity is checked
 * against movement rather than against an empty wallet. */
const everything = [
  de("PURCHASE", 5000, { payment: { amountMinor: 500000, currency: "USD" } }),
  de("PROMOTION", 500),
  de("RESERVE", 2000, { journeyRef: "J1" }),
  de("RELEASE", 500, { journeyRef: "J1" }),
  de("REDEEM", 1500, { journeyRef: "J1" }),
  de("BUYBACK", 300),
  de("EXPIRE", 200),
  de("ADJUST_DOWN", 100),
];
const wAll = L.wallet(everything);
const identity =
  wAll.acquired - wAll.reserved - wAll.redeemed - wAll.boughtBack -
  wAll.expired - wAll.adjusted;
report(
  wAll.available === identity,
  "D: the balance is the identity, not a stored number",
  `available ${wAll.available} = acquired ${wAll.acquired} - reserved ` +
  `${wAll.reserved} - redeemed ${wAll.redeemed} - boughtBack ${wAll.boughtBack} ` +
  `- expired ${wAll.expired} - adjusted ${wAll.adjusted}`
);

/* ==== Section E: repurchase, cancellation, transfer and expiry =========== */

const BB = require("../scripts/buyback.js");

/* A customer who bought 5,000 points for $5,000 and has held them long enough
   to be eligible. Used for the whole of Section E so that every refusal below
   is a refusal of something that would otherwise have succeeded — a test that
   refuses an already-impossible request proves nothing. */
const eBought = [
  Object.assign(entry("PURCHASE", 5000),
                { payment: { amountMinor: 500000, currency: "USD" } }),
];

/* E1 — repurchase is an offer, not a right, and the quote says so in words a
   customer would read rather than only in a flag. */
const eQuote = L.buybackQuote(P, eBought, 1000, 200, 0);
report(
  eQuote.eligible === true && eQuote.discretionary === true &&
    /not a guaranteed right|offer/i.test(eQuote.note),
  "E1: a repurchase quote is discretionary and says so on its face",
  `"${eQuote.note}"`
);

/* E2 — THE FRAMING, WHICH IS THE WHOLE OF SECTION E'S DIFFICULTY.
 *
 * B12 settled repurchase at "90% of the applicable purchase consideration".
 * E2 then said the product must not be described as "90% of the money you
 * paid" — because deposit, wait, withdraw is a different product whatever the
 * terms call it. Those two are in tension and the resolution is recorded here
 * rather than in a commit message: `basis` is a PROGRAMME TERM, and
 * `maxPayableIsConsideration` is a rail that caps any quote at what the
 * customer actually paid under EVERY basis. B12.2's arbitrage is closed
 * without repurchase becoming a refund. */
report(
  L.PROGRAMS[DRAFT].buyback.maxPayableIsConsideration === true &&
    typeof L.PROGRAMS[DRAFT].buyback.basis === "string",
  "E2: the basis is a programme term and the consideration is a cap, not the definition",
  `basis "${L.PROGRAMS[DRAFT].buyback.basis}", capped at consideration under every basis`
);

/* And the rail proved, not merely declared. A programme quoting on the
   entitlement basis after a 25% bonus would otherwise pay out more than came
   in, which is exactly B12.2's arbitrage. */
const ENT = L.variant(
  DRAFT,
  {
    compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    issueRate: 1.25,
    buyback: Object.assign({}, L.PROGRAMS[DRAFT].buyback, { basis: "entitlement" }),
  },
  "TEST-ENTITLEMENT-BASIS"
);
const bonusLedger = [
  Object.assign(
    { id: "TP-E1", customerId: "C", kind: "PURCHASE", quantity: 1250,
      idempotencyKey: "ek1", programVersion: ENT, status: "SETTLED" },
    { payment: { amountMinor: 100000, currency: "USD" } }),
];
const entQuote = L.buybackQuote(ENT, bonusLedger, 1250, 200, 0);
report(
  entQuote.payableMinor <= 100000 && entQuote.cappedAtConsideration === true,
  "E2: no basis can pay out more than the customer put in",
  `$1,000 in, 1,250 points at a 25% bonus, entitlement basis -> ` +
  `$${(entQuote.payableMinor / 100).toFixed(2)} out, capped at consideration`
);

/* E3 — the five steps, and only the last one touches a ledger. */
const eReq = BB.request(P, eBought, 1000, { heldDays: 200 });
const eAcc = BB.advance(eReq, "ACCEPTED", {});
const eApp = BB.advance(eAcc.request, "APPROVED", {});
const eSet = BB.advance(eApp.request, "SETTLED",
  { entries: eBought, heldDays: 200, entryId: "TP-BB1", idempotencyKey: "bb1" });
report(
  eReq.state === "QUOTED" &&
    eAcc.entries.length === 0 && eApp.entries.length === 0 &&
    eSet.entries.length === 1 && eSet.entries[0].kind === "BUYBACK",
  "E3: request, quote, accept, approve — and only settlement moves a point",
  `QUOTED -> ACCEPTED -> APPROVED emit nothing; SETTLED emits one BUYBACK of ` +
  `${eSet.entries[0].quantity}`
);

/* And a quote is not a hold. Between quotation and settlement the customer may
   have committed those points to a journey, and honouring the stale quote would
   let one set of points be both sold back and travelled on. */
const spentSince = eBought.concat([entry("RESERVE", 4800)]);
const staleSettle = BB.advance(eApp.request, "SETTLED",
  { entries: spentSince, heldDays: 200 });
report(
  staleSettle.ok === false && /no longer eligible/.test(staleSettle.why) &&
    BB.advance(eApp.request, "SETTLED", {}).ok === false,
  "E3: a quote is not a hold — settlement re-checks against the ledger as it stands",
  `points reserved after quotation -> "${staleSettle.why}"`
);

/* E1 again: a discretionary rejection is recorded with its reason, because a
   discretion nobody has to account for reads as arbitrary. */
const eRej = BB.advance(eAcc.request, "REJECTED", { reason: "manual review" });
report(
  eRej.ok === true && eRej.request.state === "REJECTED" &&
    eRej.request.rejectedReason === "manual review" && eRej.entries.length === 0,
  "E1: Afrinkong may decline an accepted quote, and the reason is kept",
  `REFUSED (terms) and REJECTED (discretion) are separate states`
);

/* E5 — holding period and annual limit, both programme parameters. */
const eEarly = L.buybackQuote(P, eBought, 1000, 30, 0);
const eOver = L.buybackQuote(P, eBought, 1000, 200, 4500);
report(
  eEarly.eligible === false && /90 days/.test(eEarly.why) &&
    eOver.eligible === false && /annual limit/.test(eOver.why),
  "E5: the minimum holding period and the annual cap are the programme's numbers",
  `30 days -> "${eEarly.why}"; 4,500 already sold back -> "${eOver.why}"`
);

/* E7 — promotional points are NOT automatically repurchasable. The instruction
   said so explicitly, and the consideration basis answers it without a special
   case: nothing was paid, so there is nothing to pay 90% of. */
const eWithBonus = eBought.concat([entry("PROMOTION", 500)]);
report(
  L.PROGRAMS[DRAFT].buyback.promotionalEligible === false &&
    L.buybackQuote(P, eWithBonus, 5200, 200, 0).eligible === false,
  "E7: promotional points are not automatically repurchasable",
  `5,000 purchased + 500 granted; asking for 5,200 -> ` +
  `"${L.buybackQuote(P, eWithBonus, 5200, 200, 0).why}"`
);

/* E8 — enforced where the entry is written, on a programme that forbids it.
   DECISION E made the shipping programme transferable, so this now runs
   against a variant that is not — which is the better test anyway: it proves
   the ENFORCEMENT rather than proving one programme's current flag, and it
   keeps working whichever way that flag goes. */
const NOTRANSFER = L.variant(
  DRAFT, { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
           transferable: false }, "TEST-NON-TRANSFERABLE");
const transferAttempt = threw(() => L.wallet(eBought.concat([
  Object.assign(entry("TRANSFER_OUT", 100), { programVersion: NOTRANSFER })])));
report(
  transferAttempt !== null && /not transferable/.test(transferAttempt) &&
    L.PROGRAMS[DRAFT].transferable === true,
  "E8: a programme that forbids transfer refuses the entry, not merely the feature",
  `"${transferAttempt}"`
);

/* E9 — cancellation and repurchase are different events, and the ledger can
   tell them apart without inferring anything from amounts. */
const cancelEntries = BK.advance(
  BK.advance(BK.advance(BK.open(P, { journeyId: "J9", requirement: 1000 }),
                        "ACCEPTED", {}).booking, "RESERVED", {}).booking,
  "CANCELLED", { daysToDeparture: 60 }).entries;
report(
  cancelEntries.every((e) => e.kind !== "BUYBACK" && e.journeyRef === "J9") &&
    eSet.entries[0].kind === "BUYBACK" && eSet.entries[0].journeyRef === null,
  "E9: a cancellation and a repurchase are separate events, distinguishable in the ledger",
  `cancellation -> ${cancelEntries.map((e) => e.kind).join("+")} against J9; ` +
  `repurchase -> BUYBACK against no journey`
);

/* E9 — validity is programme-defined and differs by lot. One scalar could not
   have said "purchased never lapses, promotional lapses at 24 months". */
report(
  L.validity(DRAFT, "purchased").lapses === false &&
    L.validity(DRAFT, "promotional").months === 24 &&
    L.hasLapsed(DRAFT, "purchased", 999) === false &&
    L.hasLapsed(DRAFT, "promotional", 24) === true,
  "E9: validity is a programme term per lot, and purchased points do not lapse from time",
  `purchased: never; promotional: 24 months. Lapsing still costs an explicit ` +
  `EXPIRE entry — no balance moves because time passed`
);

/* E10 — a programme stops SELLING long before it stops OWING. */
const closureLadder = ["ACTIVE", "CLOSED_TO_NEW_PURCHASES", "REDEMPTION_PERIOD",
                       "CLOSED"].map((c) => {
  const v = L.variant(DRAFT,
    { compliance: c, maxProgrammeExposure: 5000000 }, "TEST-CLOSURE-" + c);
  return { c, issue: L.mayIssue(v), redeem: L.mayRedeem(v), buy: L.mayBuyBack(v) };
});
report(
  closureLadder[0].issue && closureLadder[0].redeem &&
    !closureLadder[1].issue && closureLadder[1].redeem &&
    !closureLadder[2].issue && closureLadder[2].redeem &&
    !closureLadder[3].issue && !closureLadder[3].redeem,
  "E10: closing to new purchases does not close redemption",
  closureLadder.map((r) =>
    `${r.c}: issue ${r.issue ? "y" : "n"} redeem ${r.redeem ? "y" : "n"}`).join("; ")
);

/* ---- the four invariants Section E asks for by name --------------------- */

/* E-i — A BUYBACK CANNOT EXCEED ELIGIBLE AVAILABLE POINTS.
   Proved at both ends: the quote refuses to offer it, and the fold refuses to
   record it even if a caller ignored the quote entirely. The second is the one
   that matters, because a screen that bypassed the quote is exactly how this
   would happen. */
const overQuote = L.buybackQuote(P, eBought, 6000, 200, 0);
const overFold = threw(() => L.wallet(eBought.concat([entry("BUYBACK", 6000)])));
report(
  overQuote.eligible === false && overFold !== null &&
    /overdraw/.test(overFold),
  "E-i: a repurchase cannot exceed the customer's eligible available points",
  `quote refuses 6,000 of 5,000 — "${overQuote.why}"; and the fold refuses it ` +
  `independently — "${overFold}"`
);

/* E-ii — A BUYBACK CANNOT CONSUME RESERVED POINTS.
   Points committed to a journey are not available to sell back, and the wallet
   already keeps the two pools apart: `available` excludes `reserved`, so this
   is enforced by the same arithmetic that computes every balance rather than
   by a rule beside it. */
const eReserved = eBought.concat([entry("RESERVE", 4800)]);
const wRes = L.wallet(eReserved);
const onCommitted = L.buybackQuote(P, eReserved, 4800, 200, 0);
const foldCommitted = threw(() =>
  L.wallet(eReserved.concat([entry("BUYBACK", 4800)])));
report(
  wRes.reserved === 4800 && wRes.available === 200 &&
    onCommitted.eligible === false && foldCommitted !== null,
  "E-ii: a repurchase cannot consume reserved points",
  `4,800 reserved, 200 available; quote -> "${onCommitted.why}"; fold -> ` +
  `"${foldCommitted}"`
);

/* E-iii — A BUYBACK CANNOT MUTATE HISTORICAL ISSUANCE.
   The append-only claim, tested as an equality rather than asserted. The
   original PURCHASE entry is byte-identical before and after, the settlement
   returned a NEW entry rather than editing one, and `acquired` — what the
   customer has put in over the programme's life — is unchanged by selling
   points back. Only `available` moves. */
const beforeJson = JSON.stringify(eBought);
const wBefore = L.wallet(eBought);
const afterBuyback = eBought.concat(
  [Object.assign(entry("BUYBACK", 1000), { id: "TP-BBX" })]);
const wAfter = L.wallet(afterBuyback);
report(
  JSON.stringify(eBought) === beforeJson &&
    afterBuyback.length === eBought.length + 1 &&
    wAfter.acquired === wBefore.acquired &&
    wAfter.available === wBefore.available - 1000 &&
    wAfter.boughtBack === 1000,
  "E-iii: a repurchase cannot mutate historical issuance",
  `the PURCHASE entry is unchanged; acquired stays ${wAfter.acquired}; ` +
  `available ${wBefore.available} -> ${wAfter.available}; boughtBack ` +
  `${wAfter.boughtBack}. A repurchase is an entry, never an edit`
);

/* E-iv — A BUYBACK CANNOT OCCUR WHEN THE PROGRAMME IS DRAFT.
   The shipping programme, asked directly. Refused before any arithmetic runs,
   so no payable figure is ever computed — a number that exists is a number
   somebody eventually renders. */
const draftQuote = L.buybackQuote(DRAFT, eBought, 1000, 200, 0);
const draftRequest = BB.request(DRAFT, eBought, 1000, { heldDays: 200 });
report(
  L.complianceOf(DRAFT) === "DRAFT" && L.mayBuyBack(DRAFT) === false &&
    draftQuote.eligible === false && !("payableMinor" in draftQuote) &&
    draftRequest.state === "REFUSED",
  "E-iv: no repurchase under a draft programme, and no figure is even computed",
  `${DRAFT} is DRAFT -> "${draftQuote.why}"; the request lands in REFUSED`
);

/* E11 — the unresolved questions are RECORDED rather than decided in code.
   The instruction was explicit about that, and a document that quietly grew
   answers would be the failure. Counted so that deleting one is visible. */
const eDoc = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-buyback.md"), "utf8");
const eOpen = (eDoc.match(/^\s*\|\s*E-[a-z]+\s*\|/gm) || []).length;
report(
  eOpen >= 8 && /UNRESOLVED|not decided here/i.test(eDoc),
  "E11: the open legal and accounting questions are recorded, not answered in code",
  `${eOpen} unresolved questions carried in docs/travel-point-buyback.md`
);

/* ==== Section F: what is paid, what is received, and where money appears == */

/* F1 — the two rates answer different questions and are not interchangeable.
   Proved independent in the Section B lock-in above; asserted here as a shape,
   because the failure that started A4 was the two being confusable at the call
   site rather than wrong in themselves. */
report(
  L.pointsForPurchase(P, 100000) === 1000 &&
    L.priceOfPoints(P, 1000) === 100000 &&
    L.goalRequirement(P, 480000) === 4800 &&
    L.entitlementOf(P, 4800) === 480000,
  "F1: money -> points uses issueRate; points -> travel uses entitlementRate",
  `$1,000 buys 1,000 TP and 1,000 TP costs $1,000 (issueRate ${L.PROGRAMS[P].issueRate}); ` +
  `a $4,800 journey needs 4,800 TP and 4,800 TP carries $4,800 of travel ` +
  `(entitlementRate ${L.PROGRAMS[P].entitlementRate}). Two rates, two questions`
);

/* F2 — A TIERED issueRate CANNOT REACH PRODUCTION.
 *
 * The whole of Section F in one check. "Buy 5,000 and get them at 0.91" gives
 * a point a different money price in each tranche, and a thing with a spot
 * price per tranche is a currency however the terms describe it. So the
 * activation gate refuses a programme whose rate is not a single number, and
 * refuses it on the ladder too — a term nobody can edit into place. */
const TIERED = L.variant(
  DRAFT,
  { compliance: "APPROVED", maxProgrammeExposure: 5000000,
    issueRate: [{ from: 0, rate: 1 }, { from: 5000, rate: 1.1 }] },
  "TEST-TIERED-RATE"
);
report(
  L.mayActivate(TIERED).ok === false &&
    /gives a point a price/.test(L.mayActivate(TIERED).why) &&
    L.mayTransition(TIERED, "PILOT").ok === false,
  "F2: a programme whose issueRate varies by tranche cannot go live",
  `"${L.mayActivate(TIERED).why}" — and PILOT is refused on the ladder too`
);

/* F3 — AND THE INCENTIVE IS STILL FULLY EXPRESSIBLE, on the grant side.
 *
 * A volume ladder that gives 5% / 7% / 10% works exactly as a tiered price
 * would from the customer's point of view, and `issueRate` never moves. The
 * extra points are a grant: they expire, they cannot be repurchased, and no
 * money was paid for them, so no price attaches to them at all. */
const LADDER = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    promotional: Object.assign({}, L.PROGRAMS[DRAFT].promotional,
      { tiers: [{ fromPoints: 2000, bonusRate: 0.10 },
                { fromPoints: 1000, bonusRate: 0.07 }] }) },
  "TEST-BONUS-LADDER"
);
const rungs = [500, 1000, 2500].map((n) => L.purchaseOffer(LADDER, n, 0));
report(
  rungs[0].bonus === 25 && rungs[1].bonus === 70 && rungs[2].bonus === 250 &&
    rungs.every((o) => o.issueRate === 1) &&
    rungs.every((o) => o.priceMinor === o.points * 100),
  "F3: a volume incentive scales the grant, never the rate",
  rungs.map((o) => `${o.points} TP for $${o.priceMinor / 100} + ${o.bonus} granted`)
       .join("; ") + " — issueRate stays 1 at every rung"
);

/* F3 — the bonus does not reduce the price. That is the whole difference
   between a grant and a discount: a discount reprices the point, and the
   repriced point is the one that has a spot value. */
const NOBONUS = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    promotional: Object.assign({}, L.PROGRAMS[DRAFT].promotional,
                               { offered: false }) },
  "TEST-NO-PROMOTION"
);
const withPromo = L.purchaseOffer(P, 1000, 0);
const withoutPromo = L.purchaseOffer(NOBONUS, 1000, 0);
report(
  withPromo.priceMinor === withoutPromo.priceMinor &&
    withPromo.bonus === 50 && withoutPromo.bonus === 0,
  "F3: a promotion adds points, it does not discount the price",
  `1,000 TP costs $${withPromo.priceMinor / 100} whether or not a promotion is ` +
  `running; the promotion adds ${withPromo.bonus} granted points on top`
);

/* F3 — two entries, never one inflated one. B7.2 and C5 settled it; this is
   where the second entry is finally produced, because until now
   `promotional.bonusRate` was a term nothing computed. */
report(
  withPromo.entries.length === 2 &&
    withPromo.entries[0].kind === "PURCHASE" && withPromo.entries[0].quantity === 1000 &&
    withPromo.entries[1].kind === "PROMOTION" && withPromo.entries[1].quantity === 50 &&
    withoutPromo.entries.length === 1,
  "F3: an offer implies PURCHASE plus PROMOTION, never one inflated PURCHASE",
  `${withPromo.entries.map((e) => `${e.kind} ${e.quantity}`).join(" + ")} — the ` +
  `lots stay distinguishable for expiry, repurchase and cancellation`
);

/* And the grant lands in its own lot when folded, which is what makes E7's
   "promotional points are not repurchasable" enforceable at all. */
const offered = L.wallet([
  entry("PURCHASE", 1000), entry("PROMOTION", 50)]);
report(
  offered.purchased === 1000 && offered.promotional === 50 &&
    offered.available === 1050,
  "F3: the customer sees one number, the ledger keeps the two lots apart",
  `1,050 TP available = 1,000 purchased + 50 granted`
);

/* ---- F4: the cash-equivalent question, answered as a closed list -------- */

/* F4 — MONEY ATTACHES TO A TRANSACTION OR A JOURNEY. NEVER TO A HOLDING.
 *
 * "$1,000" beside a purchase button is a price. "$4,800" beside a journey is
 * what the journey costs. "3,650 TP ($3,650)" beside a wallet is a balance,
 * and that one sentence is what would make this a financial product. The three
 * permitted moments are data rather than a convention in a document, because a
 * convention in a document is a convention somebody has not read. */
report(
  Array.isArray(L.MONEY_MOMENTS) && L.MONEY_MOMENTS.length === 3 &&
    L.MONEY_MOMENTS.map((m) => m.moment).sort().join(",") ===
      "journey,purchase,repurchase",
  "F4: money may be shown at exactly three moments, and the list is closed",
  L.MONEY_MOMENTS.map((m) => `${m.moment}: ${m.shows}`).join("; ")
);

/* Moment one, checked: the purchase offer's only money figure is the price of
   the transaction, and it is named as one. No valueMinor, no worthMinor, no
   per-point price — any of which would be a cash equivalent by another name. */
const offerMoney = Object.keys(withPromo).filter(
  (k) => /minor|money|cash|usd|value|worth|price/i.test(k));
report(
  offerMoney.length === 1 && offerMoney[0] === "priceMinor",
  "F4: the purchase offer shows one money figure — what this transaction costs",
  `money-bearing keys: ${offerMoney.join(", ") || "none"}`
);

/* Moment two, checked: on the goal, the ONLY money is the journey's price.
   Every other display figure is in points, including the ones a reader is most
   likely to mistake for a balance. */
const GO = require("../scripts/travel-goal.js");
const goalF = GO.build(4800, 14, 750, "v1");
const dollarFields = Object.keys(goalF.display).filter(
  (k) => goalF.display[k] !== null && /\$/.test(String(goalF.display[k])));
report(
  dollarFields.length === 1 && dollarFields[0] === "journeyTotal" &&
    /TP$/.test(goalF.display.recorded) && /TP away$/.test(goalF.display.away),
  "F4: on the goal, the only money figure is what the journey costs",
  `"$" appears in ${dollarFields.join(", ")} only; the reader's own holding ` +
  `reads "${goalF.display.recorded}" and "${goalF.display.away}"`
);

/* Moment three is the repurchase quote, and E1 already asserts it says it is
   an offer about identified points rather than a statement of their worth.
   What is checked here is the boundary: there is NO function that converts a
   customer's holding into money without naming which points and under which
   offer. `entitlementOf` and `priceOfPoints` are arithmetic about a quantity,
   not about a wallet, and neither is a wallet field — B22 asserts that above.
   The gap that would matter is a *wallet-shaped* one, so: */
const wSurface = L.wallet([entry("PURCHASE", 3650)]);
report(
  Object.keys(wSurface).every((k) => typeof wSurface[k] !== "number" ||
    !/minor|value|worth|cash|price/i.test(k)) &&
    !("valueMinor" in wSurface) && !("cashEquivalent" in wSurface),
  "F4: there is no cash equivalent of a holding, anywhere on the wallet",
  `${Object.keys(wSurface).length} wallet fields, none of them money`
);

/* And the same asked of the pages rather than of the module, because the
   sentence F4 forbids would be written in HTML, not in JavaScript. Any page
   that puts a dollar figure immediately beside a TP figure is the failure. */
const fundPages = ["journey-fund.html", "journey-fund/how-it-works.html"]
  .map((f) => path.join(__dirname, "..", f))
  .filter((f) => fs.existsSync(f));
const adjacency = fundPages.flatMap((f) => {
  const html = fs.readFileSync(f, "utf8").replace(/<!--[\s\S]*?-->/g, " ");
  return (html.match(/[\d,]+\s*TP[^<]{0,20}\$[\d,]+|\$[\d,]+[^<]{0,20}[\d,]+\s*TP/g) || [])
    .map((m) => `${path.basename(f)}: ${m.trim()}`);
});
report(
  adjacency.length === 0,
  "F4: no page states a points figure and a money figure as the same quantity",
  `${fundPages.length} fund pages scanned, no "N TP ($N)" construction found`
);

/* F5 — the unresolved questions, recorded rather than decided. */
const fDoc = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-pricing.md"), "utf8");
const fOpen = (fDoc.match(/^\s*\|\s*F-[a-z]\s*\|/gm) || []).length;
report(
  fOpen >= 5 && /UNRESOLVED|not decided here/i.test(fDoc),
  "F5: the open pricing questions are recorded, not answered in code",
  `${fOpen} unresolved questions carried in docs/travel-point-pricing.md`
);

/* ==== Decision B: how money becomes Travel Points ======================== */

/* THE WORKED EXAMPLE, RUN. Not paraphrased — the numbers from the decision.
 *
 *   Early Planner Programme, issueRate 1.10
 *   customer pays $1,000  ->  receives 1,100 TP
 *   entitlementRate 1     ->  1,100 TP of travel entitlement
 *   cash value            ->  none
 */
const EARLY = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000, issueRate: 1.10,
    /* No promotional grant here: under this programme the incentive IS the
       rate, and every point issued is a purchased point. See the rate-versus-
       grant check below, which is the part of Decision B that needed a
       decision rather than an implementation. */
    promotional: Object.assign({}, L.PROGRAMS[DRAFT].promotional,
                               { offered: false }) },
  "EARLY-2026"
);
const earlyOffer = L.purchaseOffer(EARLY, 1100, 0);
report(
  earlyOffer.priceMinor === 100000 && earlyOffer.total === 1100 &&
    L.entitlementOf(EARLY, 1100) === 110000 &&
    L.mayActivate(EARLY).ok === true,
  "B3/B4: $1,000 buys 1,100 TP at issueRate 1.10, carrying 1,100 TP of entitlement",
  `pay $${earlyOffer.priceMinor / 100} -> ${earlyOffer.total} TP -> ` +
  `$${L.entitlementOf(EARLY, 1100) / 100} of eligible travel. The two rates ` +
  `moved independently and neither touched the other`
);

/* B5 — AND 1,100 TP IS NOT $1,100. The sentence Decision B forbids, checked
   as a sentence rather than as a principle. */
const earlyWallet = L.wallet([
  Object.assign(entry("PURCHASE", 1100), { programVersion: EARLY })]);
report(
  earlyWallet.available === 1100 &&
    Object.keys(earlyWallet).every((k) => !/minor|cash|value|worth/i.test(k)),
  "B5: the wallet says 1,100 Travel Points and cannot say $1,100",
  `available ${earlyWallet.available}, and no field on the wallet can hold a ` +
  `money figure — the display rule is enforced by the shape, not by copy review`
);

/* ---- THE ONE PART OF DECISION B THAT NEEDED DECIDING -------------------- */

/* B7 vs F2: A RATE AND A GRANT ARE BOTH LEGITIMATE, AND THEY ARE NOT THE SAME
 * THING. The decision's example calls the extra 100 TP "a promotional issuance
 * benefit" while producing them from issueRate 1.10, and those are two
 * different mechanisms that give the points different terms.
 *
 *   issueRate 1.10   -> every point is PURCHASED. Repurchasable, never
 *                       expires. The customer simply got a better price under
 *                       a named programme. F2 permits this: the rate is still
 *                       ONE number for the whole programme.
 *   PROMOTION grant  -> the extra points are GRANTED. They expire at 24
 *                       months and cannot be repurchased (E7).
 *
 * You cannot get grant terms from a rate: with issueRate 1.10 the ledger says
 * PURCHASE 1,100 and nothing marks which 100 were the benefit — so B7's "their
 * origin is recorded in the immutable ledger" is not satisfied, and E7 and E9
 * have nothing to act on. Asserted here so the difference is not lost. */
const GRANTED = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000, issueRate: 1,
    promotional: Object.assign({}, L.PROGRAMS[DRAFT].promotional,
                               { bonusRate: 0.10 }) },
  "EARLY-2026-GRANT"
);
const byRate = L.issuance(EARLY, 1100,
  { ref: "PAY-R", status: "settled" }, { purchaseKey: "kr" });
const byGrant = L.issuance(GRANTED, 1000,
  { ref: "PAY-G", status: "settled" }, { purchaseKey: "kg", promotionKey: "kg2" });
report(
  byRate.entries.length === 1 && byRate.entries[0].quantity === 1100 &&
    byGrant.entries.length === 2 &&
    byGrant.entries[1].kind === "PROMOTION" && byGrant.entries[1].quantity === 100 &&
    byRate.entries[0].issueRateApplied === 1.1,
  "B7: a better rate and a grant both deliver 1,100 TP, and the ledger tells them apart",
  `issueRate 1.10 -> one PURCHASE of 1,100, all purchased terms; a 10% grant ` +
  `-> PURCHASE 1,000 + PROMOTION 100, and only the second can be expired or ` +
  `excluded from repurchase. The choice is a programme decision, not a wording one`
);

/* B7 — and the grant carries no payment, which is what E7 actually reads. */
report(
  byGrant.entries[0].paymentRef === "PAY-G" &&
    !("payment" in byGrant.entries[1]) &&
    byGrant.entries[1].grantedUnder === "flat",
  "B7: the grant references no payment, because nothing was paid for it",
  `PURCHASE carries paymentRef PAY-G; PROMOTION carries none — the absence is ` +
  `what "only purchased points can be bought back" is reading`
);

/* ---- B6: issued only after settlement ---------------------------------- */

/* THE BOUNDARY THAT LOOKS FINISHED AND IS NOT. An authorisation is a promise
   the bank can withdraw. Points issued against one are entitlement created
   against money that never arrived. */
const stages = L.PAYMENT_STATES.map((s) => ({
  s, issues: L.maySettleIssuance(s),
  builds: L.issuance(EARLY, 1100, { ref: "PAY-X", status: s }, {}).ok === true,
}));
report(
  stages.filter((x) => x.issues).map((x) => x.s).join(",") === "settled" &&
    stages.every((x) => x.issues === x.builds),
  "B6: of seven payment states, exactly one issues a point",
  stages.map((x) => `${x.s}${x.issues ? " ✓" : ""}`).join(", ")
);

/* And the fold refuses it independently, because a caller that bypassed
   `issuance()` is exactly how this would happen. An entry marked SETTLED
   against an authorised payment used to fold cleanly. */
const bAuthorised = threw(() => L.wallet([
  Object.assign(entry("PURCHASE", 1000), { payment: { status: "authorised" } })]));
const pendingIgnored = L.fold([
  Object.assign(entry("PURCHASE", 1000), { status: "PENDING" })]);
report(
  bAuthorised !== null && /only after settlement/.test(bAuthorised) &&
    pendingIgnored.available === 0 && pendingIgnored.ignored === 1,
  "B6: an authorised payment cannot issue, and a pending entry issues nothing",
  `"${bAuthorised}"; a PENDING entry folds to 0 available and is counted as ignored`
);

/* ---- B8: no interest, yield, appreciation or time-based growth ---------- */

/* Asserted three ways already — no clock in the module, no growth kind, and
   D21.4. What is checked here is the VOCABULARY, on every customer-facing
   surface, because the failure mode for B8 is a marketing word rather than a
   line of arithmetic. Comments are stripped first: this check has flagged its
   own explanatory prose twice before, which is how the stripping got here. */
const surfaces = ["scripts/points-ledger.js", "scripts/travel-goal.js",
                  "scripts/purchase-plan.js", "scripts/buyback.js",
                  "scripts/booking.js", "journey-fund.html",
                  "journey-fund/how-it-works.html"]
  .map((f) => path.join(__dirname, "..", f))
  .filter((f) => fs.existsSync(f));
const yieldWords = surfaces.flatMap((f) => {
  const src = fs.readFileSync(f, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .split("\n").filter((l) => !/^\s*\/\//.test(l)).join("\n");
  const vocabulary = new RegExp(
    "\\b(APR|APY|interest|yield|dividend|accrues?|accrued|accrual|" +
    "appreciat\\w*|compound\\w*|return on)\\b", "gi");
  return (src.match(vocabulary) || []).map((w) => `${path.basename(f)}: ${w}`);
});
report(
  yieldWords.length === 0,
  "B8: no surface offers interest, yield, accrual, appreciation or a return",
  `${surfaces.length} customer-facing files scanned, none of the vocabulary present`
);

/* ---- B9: history is never edited ---------------------------------------- */

/* A chargeback three months later does not travel back in time and un-issue
   points. Both facts survive: the customer did buy on the third, and the
   payment was reversed on the seventh. */
const original = Object.assign(entry("PURCHASE", 1000),
  { id: "TP-ORIG", payment: { amountMinor: 100000, currency: "USD",
                              status: "settled" } });
const beforeReversal = JSON.stringify(original);
const rev = L.reversal(P, [original], "TP-ORIG", "chargeback CB-1");
const afterFold = L.wallet([original,
  Object.assign({}, rev.entries[0], { id: "TP-REV", idempotencyKey: "rev1" })]);
report(
  JSON.stringify(original) === beforeReversal &&
    rev.entries[0].kind === "ADJUST_DOWN" &&
    rev.entries[0].corrects === "TP-ORIG" &&
    afterFold.available === 0 && afterFold.acquired === 1000,
  "B9: a reversal is a new entry that names its cause, never an edit",
  `the PURCHASE is untouched; ADJUST_DOWN 1,000 corrects TP-ORIG; available ` +
  `falls to 0 while acquired still records the 1,000 that were issued`
);

/* AND THE CASE NOBODY HAS DECIDED. If the points are already committed to a
   journey, the compensating entry would overdraw — and what follows is a legal
   and commercial question. It is reported, not resolved. */
const committed = [original,
  Object.assign(entry("RESERVE", 900), { journeyRef: "J-CB" })];
const revShort = L.reversal(P, committed, "TP-ORIG", "chargeback CB-2");
report(
  revShort.shortfall === 900 && revShort.recoverable === 100 &&
    /has not been made/.test(revShort.unresolved),
  "B9: a reversal against spent points reports the shortfall rather than deciding it",
  `900 of 1,000 already committed to a journey; recoverable 100, shortfall 900 ` +
  `— "${revShort.unresolved.slice(0, 60)}…"`
);

/* ---- the module and the schema must agree ------------------------------- */

/* THE DRIFT THIS CHECK EXISTS BECAUSE OF. PROMOTION was added to the module as
 * the eleventh kind and the schema's check constraint was never updated, so
 * for several commits the database physically could not record a promotional
 * grant — which is precisely the origin B7 requires to be IN the ledger.
 * Nothing failed, because nothing compared the two. */
const schemaSrc = fs.readFileSync(
  path.join(__dirname, "points", "schema.sql"), "utf8");
const schemaKinds = (schemaSrc.match(/kind\s+text not null check \(kind in \(([\s\S]*?)\)\)/) ||
  [])[1] || "";
const missingKinds = Object.keys(L.KINDS).filter(
  (k) => !new RegExp("'" + k + "'").test(schemaKinds));
report(
  missingKinds.length === 0,
  "B: every kind the module can fold, the schema can store",
  `${Object.keys(L.KINDS).length} kinds, none missing from point_ledger's ` +
  `constraint (PROMOTION was, for several commits, and no check noticed)`
);

const schemaPayStates = (schemaSrc.match(/status in \('pending'([\s\S]*?)\)\)/) || [])[1] || "";
const missingPay = L.PAYMENT_STATES.filter(
  (s) => s !== "pending" && !new RegExp("'" + s + "'").test(schemaPayStates));
report(
  missingPay.length === 0 && /'authorised'/.test(schemaPayStates),
  "B6: the module's payment states and the schema's agree, authorisation included",
  `${L.PAYMENT_STATES.length} states in both; 'authorised' is named explicitly ` +
  `because it is the one that looks finished`
);

/* B9 — and the schema can now record what a correction corrects, which the
   module has required since B4 and the schema had no column for. */
report(
  /corrects\s+text references point_ledger\(entry_ref\)/.test(schemaSrc) &&
    /issue_rate_applied/.test(schemaSrc) &&
    /promotion_has_no_payment/.test(schemaSrc),
  "B7/B9: the schema records a correction's cause, the rate applied, and that a grant has no payment",
  "three columns/constraints that the module enforced and the database could not"
);

/* B-open — recorded, not decided. */
const bDoc = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-issuance.md"), "utf8");
const bOpen = (bDoc.match(/^\s*\|\s*B-[a-z]+\s*\|/gm) || []).length;
report(
  bOpen >= 4 && /UNRESOLVED|not decided here/i.test(bDoc),
  "B: the open questions Decision B raises are recorded, not answered in code",
  `${bOpen} unresolved questions carried in docs/travel-point-issuance.md`
);

/* ==== Decision C: what happens when a customer wants to leave ============ */

/* Ten rules, each asserted by name. Most were already built as Section E; the
   four that were NOT are marked below, because a decision document that says
   "enforced" about something nothing enforces is worse than one that says
   nothing. */

const cLedger = [
  Object.assign(entry("PURCHASE", 10000),
                { payment: { amountMinor: 1000000, currency: "USD",
                             status: "settled" } }),
];

/* C1/C10 — REDEMPTION IS THE PRIMARY EXIT, AND THERE IS NO CASH EXIT.
   "Primary" is a product statement, but it has one enforceable reading: no
   code path turns points into money because a customer asked what they are
   worth. Every route out is either travel, or a discretionary offer about
   identified points under published terms. */
const exits = Object.keys(L.KINDS).filter((k) => L.KINDS[k].available === -1);
report(
  exits.sort().join(",") === "ADJUST_DOWN,BUYBACK,EXPIRE,RESERVE,TRANSFER_OUT" &&
    typeof L.buybackQuote === "function" &&
    L.PROGRAMS[DRAFT].buyback.discretionary === true,
  "C1/C10: every way out is travel, an administrative act, or a discretionary offer",
  `points leave availability by: ${exits.join(", ")} — RESERVE leads to travel, ` +
  `BUYBACK is discretionary and quoted, and none of them is "convert to cash on request"`
);

/* C2 — THE THREE CATEGORIES, AND THAT THEY ARE ACTUALLY DIFFERENT.
   Unreserved -> buyback rules. Reserved -> cancellation rules. Consumed ->
   neither. The third is the one worth asserting: once REDEEM has run there is
   no path back at all, and the booking machine makes REDEEMED terminal. */
const cReserved = cLedger.concat([
  Object.assign(entry("RESERVE", 4800), { journeyRef: "J-C2" })]);
const cConsumed = cReserved.concat([
  Object.assign(entry("REDEEM", 4800), { journeyRef: "J-C2" })]);
const wConsumed = L.wallet(cConsumed);
const redeemedBooking = BK.open(P, { journeyId: "J-C2", requirement: 4800 });
report(
  L.buybackQuote(P, cLedger, 5000, 200, 0).eligible === true &&
    L.buybackQuote(P, cReserved, 5000, 200, 0).eligible === true &&
    L.buybackQuote(P, cConsumed, 5200, 200, 0).eligible === false &&
    wConsumed.redeemed === 4800 && wConsumed.available === 5200 &&
    BK.BOOKING_NEXT.REDEEMED.length === 0,
  "C2: unreserved, reserved and consumed points are three different things",
  `unreserved 5,000 quotable; with 4,800 reserved the other 5,200 are still ` +
  `quotable; once consumed they are gone — REDEEMED is terminal and the 4,800 ` +
  `are not quotable at any price`
);

/* C3/C6 — a programme buyback, not a withdrawal facility, and Model B. */
report(
  L.PROGRAMS[DRAFT].buyback.discretionary === true &&
    typeof L.PROGRAMS[DRAFT].buyback.basis === "string" &&
    /not a guaranteed right/i.test(
      L.buybackQuote(P, cLedger, 1000, 200, 0).note),
  "C3/C6: Model B — Afrinkong may offer, under published programme conditions",
  `discretionary, basis "${L.PROGRAMS[DRAFT].buyback.basis}", and the quote ` +
  `says on its face that it is not a guaranteed right of redemption`
);

/* C4 — the minimum holding period, and the arbitrage it exists to stop. */
report(
  L.PROGRAMS[DRAFT].buyback.minHoldDays === 90 &&
    L.buybackQuote(P, cLedger, 1000, 1, 0).eligible === false &&
    L.buybackQuote(P, cLedger, 1000, 89, 0).eligible === false &&
    L.buybackQuote(P, cLedger, 1000, 90, 0).eligible === true,
  "C4: buy today, sell back today is refused; 90 days is a programme term",
  `day 1 and day 89 refused, day 90 quotable — without this the programme is ` +
  `a deposit with an extra step`
);

/* C5 — THE PERCENTAGE CAP, WHICH DID NOT EXIST. **GAP CLOSED**
 *
 * `maxPerYear: 5000` is an absolute count: it is all of a small holding and a
 * tenth of a large one. C5 asks for a percentage of eligible unreserved points,
 * which is a different control with different behaviour, so it is now its own
 * term and whichever is tighter binds. */
const PCT = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    buyback: Object.assign({}, L.PROGRAMS[DRAFT].buyback,
                           { maxPctPerYear: 0.25, maxPerYear: 1000000000 }) },
  "TEST-PCT-LIMIT"
);
const pctLedger = cLedger.map((e) => Object.assign({}, e, { programVersion: PCT }));
report(
  "maxPctPerYear" in L.PROGRAMS[DRAFT].buyback &&
    L.buybackQuote(PCT, pctLedger, 2500, 200, 0).eligible === true &&
    L.buybackQuote(PCT, pctLedger, 2600, 200, 0).eligible === false,
  "C5: an annual limit may be a percentage of eligible points, not only a count",
  `25% of a 10,000 TP holding: 2,500 quotable, 2,601 refused. The absolute cap ` +
  `and the percentage cap both apply and the tighter one binds`
);

/* AND THE SALAMI THE PERCENTAGE INVITES. Measured against the holding as it
   stands, a customer sells 25%, then 25% of the remainder, and reaches most of
   their balance inside a year without once exceeding the limit. The base
   includes what has already been sold back this year, so it does not shrink. */
const pctAfter = pctLedger.concat([
  Object.assign({}, entry("BUYBACK", 2500), { programVersion: PCT })]);
const salami = L.buybackQuote(PCT, pctAfter, 100, 200, 2500);
report(
  salami.eligible === false && salami.base === 10000 && salami.annualCeiling === 2500,
  "C5: the percentage base does not shrink as points are sold back",
  `after selling 2,500 the holding is 7,500 but the base stays ${salami.base} ` +
  `and the ceiling stays ${salami.annualCeiling} — otherwise 25% repeated ` +
  `reaches most of a balance inside one year`
);

/* C7 — the three bands, matched against the decision's own boundaries.
   "More than 30 days" is 31+, so 30 falls to the middle band. Checked at the
   boundaries rather than in the middle of each band, because that is where an
   off-by-one would live. */
const bands = [60, 31, 30, 8, 7, 0].map((d) => ({
  d, c: L.cancellation(P, d, 1000) }));
report(
  bands[0].c.released === 1000 && bands[1].c.released === 1000 &&
    bands[2].c.released === 500 && bands[3].c.released === 500 &&
    bands[4].c.released === 0 && bands[5].c.released === 0,
  "C7: cancellation is the booking's terms, at exactly the boundaries C7 names",
  bands.map((b) => `${b.d}d -> ${b.c.released} released`).join(", ") +
  ` — "more than 30 days" is 31+, so day 30 is already the middle band`
);

/* C7 — and it attaches to the BOOKING, not to the wallet. A customer holding
   10,000 who reserved 4,800 and cancels inside the window still has the
   other 5,200, which is the difference between a cancellation policy and
   destroying somebody's accumulation. */
const lateCancel = BK.advance(
  BK.advance(BK.advance(BK.open(P, { journeyId: "J-C7", requirement: 4800 }),
                        "ACCEPTED", {}).booking, "RESERVED", {}).booking,
  "CANCELLED", { daysToDeparture: 3 });
/* Reserved against J-C7, not against C2's journey: a RELEASE or REDEEM whose
   journeyRef has nothing reserved is refused by the fold, which is the
   reservation ledger working and was my fixture being wrong. */
const c7Reserved = cLedger.concat([
  Object.assign(entry("RESERVE", 4800), { journeyRef: "J-C7" })]);
const afterLate = L.wallet(c7Reserved.concat(
  lateCancel.entries.map((e, i) => Object.assign({}, e,
    { id: "TP-LC" + i, idempotencyKey: "lc" + i, programVersion: P }))));
report(
  lateCancel.booking.cancellation.released === 0 &&
    afterLate.available === 5200,
  "C7: a cancellation attaches to the booking; the rest of the wallet is untouched",
  `0 of 4,800 released inside three days, and the other ${afterLate.available} ` +
  `TP are unaffected`
);

/* C8 — THE FINAL-WINDOW BAR, ON TRANSFER AS WELL AS BUYBACK. **GAP CLOSED**
 *
 * Buyback in the window was already refused (E6). Transfer was refused too —
 * but only because `transferable: false` refuses every transfer, so C8's
 * window rule held as a side effect of a different rule and would have
 * vanished silently the moment a programme permitted transfer. */
const TRANSFERABLE = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000, transferable: true },
  "TEST-TRANSFERABLE"
);
const inFinalWeek = [{ journeyRef: "J-C8", daysToDeparture: 5, points: 4800 }];
report(
  L.mayTransfer(TRANSFERABLE, {}).ok === true &&
    L.mayTransfer(TRANSFERABLE, { commitments: inFinalWeek }).ok === false &&
    L.mayTransfer(TRANSFERABLE, { commitments: inFinalWeek }).rule === "restrictedWindow" &&
    L.buybackQuote(P, cLedger, 1000, 200, 0, inFinalWeek).eligible === false,
  "C8: inside the final window, reserved points are neither buyable-back nor transferable",
  `on a programme that DOES permit transfer, the window still refuses it — the ` +
  `rule no longer depends on transfer being globally off`
);

/* C9 — no peer-to-peer resale. Two separate refusals, because a gift and a
   sale are different acts and a programme might one day permit one and not the
   other. `secondaryMarket` finally reads: until now it was a declared term
   that nothing consulted, which is exactly where `transferable` was before E8
   and was found the same way. */
report(
  L.mayTransfer(NOTRANSFER, {}).ok === false &&
    L.mayTransfer(NOTRANSFER, {}).rule === "transferable" &&
    L.mayTransfer(DRAFT, {}).ok === true &&
    L.mayTransfer(DRAFT, { forConsideration: true }).ok === false &&
    L.mayTransfer(DRAFT, { forConsideration: true }).rule === "secondaryMarket",
  "C9 as reversed by Decision E: a gift is permitted, a sale is not",
  `the shipping programme now permits a gift and still refuses a sale on ` +
  `"secondaryMarket". C9's ban on a RESALE MARKET survives Decision E intact; ` +
  `what changed is that giving points away is no longer collateral damage`
);

/* And the fold still refuses the entry itself, so the gate above is a second
   line rather than the only one. */
const cTransferFold = threw(() => L.wallet(cLedger.concat([
  Object.assign(entry("TRANSFER_OUT", 100), { programVersion: NOTRANSFER })])));
report(
  cTransferFold !== null && /not transferable/.test(cTransferFold),
  "C9: and a transfer entry is refused where it is written, not only where it is offered",
  `"${cTransferFold}"`
);

/* C10 — restated as the thing that must never exist: a function that answers
   "what is my balance worth" with a number. */
const cWallet = L.wallet(cLedger);
report(
  !("valueMinor" in cWallet) && !("cashValue" in cWallet) &&
    L.MONEY_MOMENTS.every((m) => m.moment !== "balance") &&
    L.buybackQuote(P, cLedger, 1000, 200, 0).points === 1000,
  "C10: no point is redeemable for cash because a customer asked what it is worth",
  `a repurchase quote is about 1,000 identified points under published terms, ` +
  `and there is no wallet field, and no money moment, for "what this is worth"`
);

/* C-open — recorded, not decided. */
const cDoc = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-exit.md"), "utf8");
const cOpen = (cDoc.match(/^\s*\|\s*C-[a-z]+\s*\|/gm) || []).length;
report(
  cOpen >= 4 && /UNRESOLVED|not decided here/i.test(cDoc),
  "C: the open questions Decision C raises are recorded, not answered in code",
  `${cOpen} unresolved questions carried in docs/travel-point-exit.md`
);

/* ==== Decision D: expiry, programme duration, unused points ============== */

const dLedger = [
  Object.assign(entry("PURCHASE", 5000),
                { payment: { amountMinor: 500000, currency: "USD",
                             status: "settled" } }),
  entry("PROMOTION", 500),
];

/* D1 — every point names its programme for the WHOLE of its life, not only at
   issuance. Issuance already required one; a RESERVE, REDEEM or BUYBACK did
   not, so points could move without naming the terms they moved under. */
const noProgramme = threw(() => L.wallet([
  { id: "TP-NP", kind: "RESERVE", quantity: 10, idempotencyKey: "np",
    status: "SETTLED", journeyRef: "J-D1" }]));
report(
  noProgramme !== null && /without a programme/.test(noProgramme),
  "D1: an entry that moves points without naming a programme is refused",
  `"${noProgramme}" — D5 says the terms travel with the points for their whole ` +
  `life, and only issuance was checking`
);

/* D2 — purchased points do not lapse from time alone, and this is a term
   rather than an absence. `null` means never; it is not "unset". */
report(
  L.PROGRAMS[DRAFT].expiry.purchased === null &&
    L.validity(DRAFT, "purchased").lapses === false &&
    L.hasLapsed(DRAFT, "purchased", 120) === false,
  "D2: purchased points do not expire, including after ten years",
  `expiry.purchased is null — never, not unset. A customer planning 36 months ` +
  `out is not racing a clock`
);

/* D3/D4 — CLOSING A PROGRAMME IS NOT A WAY OF CANCELLING WHAT IT OWES.
 * **GAP CLOSED.** The run-off ladder existed; nothing stopped a programme
 * walking to CLOSED — the one state where points can neither be redeemed nor
 * bought back — while customers still held points. */
const RUNOFF = L.variant(
  DRAFT, { compliance: "REDEMPTION_PERIOD", maxProgrammeExposure: 5000000 },
  "TEST-RUNOFF");
report(
  L.mayTransition(RUNOFF, "CLOSED", { outstanding: 4500 }).ok === false &&
    L.mayTransition(RUNOFF, "CLOSED", { outstanding: 0 }).ok === true &&
    L.mayClose(RUNOFF, null).ok === false,
  "D4: a programme with points outstanding cannot reach CLOSED",
  `4,500 TP outstanding -> refused; 0 outstanding -> permitted; and an ` +
  `UNSTATED balance is refused too, because it cannot be assumed to be zero`
);

/* D3 — and the ladder itself: stop selling, run off, then close. Each step
   keeps redemption alive until the last one, which is the whole distinction
   between winding down and confiscating. */
const dLadder = ["ACTIVE", "CLOSED_TO_NEW_PURCHASES", "REDEMPTION_PERIOD",
                 "CLOSED"].map((c) => {
  const v = L.variant(DRAFT, { compliance: c, maxProgrammeExposure: 5000000 },
                      "TEST-D3-" + c);
  return `${c}: redeem ${L.mayRedeem(v) ? "yes" : "no"}`;
});
report(
  dLadder[0].endsWith("yes") && dLadder[1].endsWith("yes") &&
    dLadder[2].endsWith("yes") && dLadder[3].endsWith("no"),
  "D3: Active -> Closed to new purchases -> Run-off, and redemption survives all three",
  dLadder.join("; ")
);

/* D5/D9 — the terms are attached to the points and cannot be rewritten. A new
   programme with harsher terms leaves the old one untouched. */
const HARSH = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    expiry: { purchased: 6, promotional: 6 } },
  "TEST-2027-HARSH");
const retro = threw(() => { L.PROGRAMS[DRAFT].expiry.purchased = 6; });
report(
  L.validity(HARSH, "purchased").months === 6 &&
    L.validity(DRAFT, "purchased").months === null &&
    L.PROGRAMS[DRAFT].expiry.purchased === null,
  "D5/D9: a 2027 programme with six-month expiry does not touch 2026 points",
  `the new programme lapses at 6 months; ${DRAFT} still says never, and the ` +
  `frozen terms refused the write${retro ? " by throwing" : " silently"}`
);

/* D6 — WHEN THE JOURNEY DISAPPEARS, SOMETHING IS ALWAYS OFFERED. **NEW**
   The ordered hierarchy, and "the points are void" is not in it at any rank. */
const dRemedies = L.remedies(P, { equivalents: ["country:kenya:signature:7"] });
report(
  dRemedies.remedies.map((r) => r.remedy).join(",") ===
    "equivalent,alternative,buyback" &&
    dRemedies.exhausted === false &&
    /expiring or voiding/.test(dRemedies.neverAnOption),
  "D6: equivalent travel, then another eligible service, then buyback — never erasure",
  dRemedies.remedies.map((r) => `${r.rank}. ${r.remedy}`).join(", ") +
  ` — and an empty list reports "exhausted", which is a human decision rather ` +
  `than a lapse`
);

/* Under the draft programme buyback is not reachable, so the hierarchy
   correctly offers fewer remedies rather than pretending. */
report(
  L.remedies(DRAFT, {}).remedies.map((r) => r.remedy).join(",") === "alternative",
  "D6: the hierarchy offers only what this programme can actually deliver",
  `${DRAFT} is DRAFT, so no repurchase is offered — the list shrinks rather ` +
  `than quoting something that cannot happen`
);

/* ---- D8: THE RULE THAT WAS SILENTLY DIFFERENT ------------------------- */

/* The fold spent the promotional pool first, unconditionally. Under
 * `AFK-TP-2026.1` that IS earliest-expiry-first — purchased never lapses — so
 * the two rules agree, which is exactly why the difference was invisible.
 *
 * They diverge the moment a programme gives purchased points a shorter
 * validity than promotional ones. "Promotional first" would then burn the
 * longer-lived points and let the shorter-lived ones lapse, costing the
 * customer points they had paid for. */
const dSpend = L.wallet(dLedger.concat([
  Object.assign(entry("RESERVE", 2000), { journeyRef: "J-D8" })]));
const INVERTED = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    expiry: { purchased: 12, promotional: 36 } },
  "TEST-INVERTED-EXPIRY");
const invLedger = dLedger.map((e) =>
  Object.assign({}, e, { programVersion: INVERTED }));
const invSpend = L.wallet(invLedger.concat([
  Object.assign({}, entry("RESERVE", 2000),
                { journeyRef: "J-D8i", programVersion: INVERTED })]));
report(
  L.consumptionOrder(DRAFT).join(",") === "promotional,purchased" &&
    dSpend.promotional === 0 && dSpend.purchased === 3500 &&
    L.consumptionOrder(INVERTED).join(",") === "purchased,promotional" &&
    invSpend.purchased === 3000 && invSpend.promotional === 500,
  "D8: earliest expiry first, which is NOT the same rule as promotional first",
  `${DRAFT}: promotional lapses at 24 months and purchased never, so the 500 ` +
  `granted go first. Inverted (purchased 12, promotional 36): the purchased ` +
  `points go first and all 500 granted survive — the old rule would have ` +
  `spent them and let the paid-for points lapse`
);

/* D8 — and the tie-break is stable rather than incidental. */
const NEITHER = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    expiry: { purchased: null, promotional: null } },
  "TEST-NO-EXPIRY-EITHER");
report(
  L.consumptionOrder(NEITHER).join(",") === "promotional,purchased",
  "D8: when neither pool lapses, promotional still goes first, deliberately",
  `it is the pool that cannot be repurchased and is forfeited on cancellation, ` +
  `so spending it first still costs the customer least — a stated tie-break, ` +
  `not whatever the sort happened to do`
);

/* D7 — and the customer is TOLD which points expire, in sentences. **NEW** */
const disclosure = L.expiryDisclosure(P, dLedger);
report(
  disclosure.pools.find((x) => x.lot === "purchased").statement ===
    "5000 TP purchased. These do not expire." &&
    /valid for 24 months/.test(
      disclosure.pools.find((x) => x.lot === "promotional").statement) &&
    /expire soonest are used first/.test(disclosure.spendNote),
  "D7: the customer never has to guess which points expire",
  disclosure.pools.map((x) => x.statement).filter(Boolean).join(" / ")
);

/* D10 — inactivity does nothing, which is the same fact as "no clock". */
const idleBefore = L.wallet(dLedger).available;
const idleAfter = L.wallet(dLedger).available;
report(
  idleBefore === idleAfter && idleBefore === 5500 &&
    /not affected by how long/.test(disclosure.inactivityNote) &&
    !/\bDate\b|\bnow\(\)/.test(
      fs.readFileSync(path.join(__dirname, "..", "scripts", "points-ledger.js"),
                      "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .split("\n").filter((l) => !/^\s*\/\//.test(l)).join("\n")),
  "D10: nothing happens to a holding because a customer went away",
  `${idleBefore} TP, and the module still contains no clock at all — ` +
  `inactivity cannot be detected, let alone punished`
);

/* D11 — reaching the target is a journey state, not an account balance. */
const dGoal = GO.build(4800, 14, 4800, "v1");
const dPartial = GO.build(4800, 14, 750, "v1");
report(
  dGoal.journeyState === "FUNDED" && dGoal.display.funded === "Journey funded" &&
    dPartial.journeyState === "PLANNING" && dPartial.display.funded === null &&
    dGoal.journeyStates.join(",") ===
      "PLANNING,FUNDED,BOOKING,RESERVED,TRAVELLING,COMPLETED",
  "D11: reaching the target says Journey funded, never Account balance",
  `4,800 of 4,800 -> "${dGoal.display.funded}" and journeyState FUNDED; the ` +
  `next stage is booking, not withdrawal`
);

/* And the word "balance" does not appear on the goal at the moment it would do
   most damage — the customer has just watched a number reach a round figure. */
report(
  !Object.keys(dGoal.display).some(
    (k) => /balance|account/i.test(String(dGoal.display[k]))),
  "D11: no display field on a funded goal says balance or account",
  `${Object.keys(dGoal.display).length} display fields, none of them financial ` +
  `vocabulary`
);

/* D-open — recorded, not decided. */
const dDoc = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-duration.md"), "utf8");
const dOpen = (dDoc.match(/^\s*\|\s*D-[a-z]+\s*\|/gm) || []).length;
report(
  dOpen >= 4 && /UNRESOLVED|not decided here/i.test(dDoc),
  "D: the open questions Decision D raises are recorded, not answered in code",
  `${dOpen} unresolved questions carried in docs/travel-point-duration.md`
);

/* ==== Decision E: transferability, gifting and inheritance =============== */

const TR = require("../scripts/transfer.js");

const james = [
  Object.assign(entry("PURCHASE", 5000),
                { payment: { amountMinor: 500000, currency: "USD",
                             status: "settled" } }),
];

/* E1/E2 — THE DISTINCTION THE WHOLE DECISION RESTS ON.
   "Give my 3,000 TP to my wife" is allowed. "Sell my 3,000 TP for $2,700" is
   not. Same movement of points, completely different products. */
const gift = TR.propose(P, "CUST-1042", "CUST-2871", 2000,
  { senderEntries: james, outKey: "o1", inKey: "i1" });
const sale = TR.propose(P, "CUST-1042", "CUST-9999", 2000,
  { senderEntries: james, forConsideration: true });
report(
  gift.ok === true && sale.ok === false && sale.rule === "secondaryMarket",
  "E1/E2: a gift is permitted, a sale of the same points is not",
  `2,000 TP to a named recipient -> allowed; the same 2,000 for money -> ` +
  `"${sale.why}"`
);

/* E3 — NO ANONYMOUS TRANSFERS. Both ends named, and named differently: a
   transfer to oneself is either a mistake or an attempt to relabel points. */
report(
  TR.propose(P, "CUST-1042", "", 2000, { senderEntries: james }).rule === "identified" &&
    TR.propose(P, "", "CUST-2871", 2000, { senderEntries: james }).rule === "identified" &&
    TR.propose(P, "CUST-1042", "CUST-1042", 2000, { senderEntries: james }).rule === "identified" &&
    gift.entries[0].customerId === "CUST-1042" &&
    gift.entries[0].counterpartyId === "CUST-2871",
  "E3: a transfer names both parties, and they must be different people",
  `sender and recipient are both recorded on both entries; an unnamed end or a ` +
  `transfer to oneself is refused`
);

/* E4 — THE PROGRAMME TRAVELS WITH THE ENTITLEMENT.
   Sarah receives 2,000 TP under Programme 2026-A, not under whatever is active
   when she receives them. Both entries carry the sender's programme. */
report(
  gift.entries[0].programVersion === P &&
    gift.entries[1].programVersion === P &&
    gift.programId === P,
  "E4: the recipient gets points under the SENDER's programme and terms",
  `both TRANSFER_OUT and TRANSFER_IN carry ${P} — a recipient cannot be moved ` +
  `onto different terms by the timing of a gift`
);

/* E5/E12 — TRANSFER IS NOT ISSUANCE. James -2,000, Sarah +2,000, supply
   unchanged. And no fee, stated as a number rather than as an absence. */
const conserved = TR.conserves(gift.entries);
const minted = TR.conserves([
  { kind: "TRANSFER_OUT", quantity: 2000 },
  { kind: "TRANSFER_IN", quantity: 2500 }]);
report(
  conserved.ok === true && conserved.transferredIn === conserved.transferredOut &&
    minted.ok === false && minted.difference === 500 &&
    gift.entries[0].feeMinor === 0 && gift.entries[1].feeMinor === 0,
  "E5/E12: a transfer conserves supply and costs nothing",
  `2,000 out and 2,000 in; a mismatched pair is caught — "${minted.why}". ` +
  `feeMinor is 0 as a stated number, so a fee cannot arrive by omission`
);

/* E6 — the original issuance is untouched. A transfer is two new entries. */
const jamesBefore = JSON.stringify(james);
report(
  JSON.stringify(james) === jamesBefore && gift.entries.length === 2 &&
    gift.entries.every((e) => e.kind !== "PURCHASE"),
  "E6: the original purchase history is not modified by a transfer",
  `the PURCHASE entry is byte-identical; the transfer is TRANSFER_OUT + ` +
  `TRANSFER_IN and nothing else`
);

/* E8 — reserved points follow the booking's rules, not the wallet's. Two
   separate refusals: the points are not available, and the window bars it. */
const jamesCommitted = james.concat([
  Object.assign(entry("RESERVE", 4800), { journeyRef: "J-E8" })]);
const overCommitted = TR.propose(P, "CUST-1042", "CUST-2871", 4800,
  { senderEntries: jamesCommitted });
const inWindowTransfer = TR.propose(P, "CUST-1042", "CUST-2871", 200,
  { senderEntries: jamesCommitted,
    commitments: [{ journeyRef: "J-E8", daysToDeparture: 5, points: 4800 }] });
report(
  overCommitted.ok === false && overCommitted.rule === "available" &&
    inWindowTransfer.ok === false && inWindowTransfer.rule === "restrictedWindow",
  "E8: reserved points cannot be transferred, and the final window bars it too",
  `4,800 reserved -> "${overCommitted.why}"; and five days out even the ` +
  `uncommitted 200 are refused, so a customer cannot leave Afrinkong holding ` +
  `the supplier obligations`
);

/* Promotional points are not transferable under this programme — a term that,
   like `secondaryMarket` before Decision C, nothing read until now. */
const withGrant = james.concat([entry("PROMOTION", 500)]);
report(
  L.PROGRAMS[DRAFT].promotional.transferable === false &&
    TR.propose(P, "CUST-1042", "CUST-2871", 5200, { senderEntries: withGrant })
      .rule === "promotionalTransferable",
  "E: a grant that cannot be repurchased cannot be handed to a third party either",
  `5,000 purchased + 500 granted; transferring 5,200 is refused on ` +
  `promotional.transferable`
);

/* E9 — FAMILY POOLING. A view over points people hold separately; nothing
   moves and no joint holding exists. */
const family = TR.pool(P, [
  { name: "Mother", points: 3000 }, { name: "Father", points: 4000 },
  { name: "Brother", points: 1500 }, { name: "Child", points: 500 }], 10000);
report(
  family.total === 9000 && family.remaining === 1000 &&
    family.display === "9000 / 10000 TP" && family.state === "PLANNING" &&
    /Nothing has been transferred/.test(family.note),
  "E9: four people can fund one journey without a joint account existing",
  `${family.display} — a shared view, not a merged balance. Actually moving ` +
  `the points is a FAMILY_POOL transfer per contributor, each with its own consent`
);

/* And pooling across programmes is refused, because it would silently merge
   two sets of terms — which E4 forbids. */
report(
  TR.pool(P, [{ name: "A", points: 100, programId: P },
              { name: "B", points: 100, programId: "OTHER" }], 500).ok === false,
  "E9/E4: contributions to one pool must share one programme",
  `pooling across programmes would merge two sets of terms into one goal`
);

/* E10/E11 — corporate gifting and estate transfer have a PLACE in the model
   without being built, and both are marked as requiring documentation so
   neither can be executed as an ordinary gift. */
const estate = TR.propose(P, "CUST-1042", "CUST-3000", 2000,
  { senderEntries: james, type: "ESTATE" });
const estateDoc = TR.propose(P, "CUST-1042", "CUST-3000", 2000,
  { senderEntries: james, type: "ESTATE", documentationRef: "PROBATE-99",
    outKey: "o2", inKey: "i2" });
report(
  Object.keys(TR.TRANSFER_TYPES).sort().join(",") ===
    "CORPORATE_GIFT,ESTATE,FAMILY_POOL,GIFT" &&
    estate.ok === false && estate.rule === "documentation" &&
    estateDoc.ok === true && estateDoc.entries[0].transferType === "ESTATE",
  "E10/E11: estate and corporate transfers have a place, and require documentation",
  `four types; ESTATE without a documentation reference is refused, with one ` +
  `it proceeds and the type is recorded on the entries. Neither is built — the ` +
  `economic model simply has room for them`
);

/* E12 — no open marketplace, restated as the hard boundary. There is no order
   book, no price, and no way to express one: a transfer carries no amount of
   money at all. */
report(
  !("priceMinor" in gift) && !("amountMinor" in gift) &&
    gift.entries.every((e) => !("priceMinor" in e) && !("amountMinor" in e)) &&
    L.PROGRAMS[DRAFT].secondaryMarket === false,
  "E12: a transfer carries no price, so there is nothing an order book could quote",
  `neither the proposal nor either entry can hold a money figure — speculative ` +
  `trading has no representation, not merely no interface`
);

/* ---- the hole Decision E would have opened ------------------------------ */

/* THE ONE THAT MATTERS MOST HERE, AND IT WAS FOUND BY IMPLEMENTING E.
 *
 * `maxPayableIsConsideration` is the rail that says a repurchase may never pay
 * out more than came in. It used to SKIP silently when consideration could not
 * be traced — and gifted points cannot be traced to a payment by definition,
 * because the recipient never made one.
 *
 * So under an entitlement-basis programme: buy 5,000 TP for $5,000, gift them
 * to somebody, and they are quoted $4,500 with the rail inactive. Buy, gift,
 * cash out. Non-transferability was hiding it; Decision E is what would have
 * activated it. A cap that cannot be computed is now a refusal. */
const ENTITLEMENT_TRANSFERABLE = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000, transferable: true,
    buyback: Object.assign({}, L.PROGRAMS[DRAFT].buyback,
                           { basis: "entitlement" }) },
  "TEST-LAUNDER");
const recipient = [{
  id: "TP-GIFT", customerId: "CUST-2871", kind: "TRANSFER_IN", quantity: 5000,
  idempotencyKey: "gift1", programVersion: ENTITLEMENT_TRANSFERABLE,
  status: "SETTLED", counterpartyId: "CUST-1042" }];
const cashOut = L.buybackQuote(ENTITLEMENT_TRANSFERABLE, recipient, 5000, 200, 0);
report(
  cashOut.eligible === false && /cannot be traced to a payment/.test(cashOut.why) &&
    !("payableMinor" in cashOut),
  "E: gifted points cannot be cashed out by somebody who never paid for them",
  `was quoting $4,500 to a recipient who paid nothing, because the ` +
  `consideration cap SKIPPED when it could not be computed instead of ` +
  `refusing. Buy, gift, cash out — closed`
);

/* And the schema carries the same rules, since the last time the module and
   the schema disagreed the database simply could not store a PROMOTION. */
report(
  /transfer_type\s+text check/.test(schemaSrc) &&
    /transfer_is_between_two_people/.test(schemaSrc) &&
    /transfer_has_no_payment/.test(schemaSrc) &&
    /create view transfer_conservation/.test(schemaSrc) &&
    /secondary_market boolean/.test(schemaSrc),
  "E: the schema records the transfer type and can prove conservation itself",
  `transfer_type constrained to the four types, a transfer to oneself is ` +
  `refused, a transfer cannot reference a payment, and transfer_conservation ` +
  `lists any programme where sent and received disagree`
);

/* E-open — recorded, not decided. */
const eDocE = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-transfer.md"), "utf8");
const eOpenE = (eDocE.match(/^\s*\|\s*E-[a-z]+\s*\|/gm) || []).length;
report(
  eOpenE >= 4 && /UNRESOLVED|not decided here/i.test(eDocE),
  "E: the open questions Decision E raises are recorded, not answered in code",
  `${eOpenE} unresolved questions carried in docs/travel-point-transfer.md`
);

/* ==== Decision F: what a Travel Point can actually buy =================== */

const JC = require("../scripts/journey-catalogue.js");
const fCard = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "journey-fund.html"), "utf8")
    .match(/id="jf-data">([\s\S]*?)<\/script>/)[1]);
const fSpec = { kind: "country", place: "kenya", tier: "signature", days: 7 };
const fBreak = JC.breakdown(fCard, fSpec);

/* F1 — NOT GENERAL-PURPOSE PURCHASING CREDIT. The basket is a programme term,
   and everything outside it is refused by name so a customer can be told which
   line of their journey the points do not reach. */
const groceries = BK.request(P, { requirement: 100 }, { available: 5000 },
                             ["groceries", "electronics"]);
report(
  groceries.ok === false && groceries.ineligible.join(",") ===
    "groceries,electronics" &&
    L.PROGRAMS[DRAFT].eligibleServices.indexOf("cash") === -1,
  "F1: points redeem only against the programme's eligible services",
  `groceries and electronics -> "${groceries.why}". The basket has ` +
  `${L.PROGRAMS[DRAFT].eligibleServices.length} entries and none of them is cash`
);

/* F2/F3/F4 — the basket covers what Afrinkong actually arranges, INCLUDING
   government charges it settles and its own service component. The last is the
   one a customer would otherwise be ambushed by: accumulate a large holding,
   then discover Afrinkong must be paid separately. */
const basket = L.PROGRAMS[DRAFT].eligibleServices;
report(
  ["accommodation", "transport", "guiding", "excursion"].every(
    (s) => basket.indexOf(s) !== -1) &&
    ["park_fee", "conservation_fee", "permit", "government_charge"].every(
      (s) => basket.indexOf(s) !== -1) &&
    basket.indexOf("afrinkong_service") !== -1,
  "F2/F3/F4: journey services, settled government charges, and Afrinkong's own fee",
  `${basket.length} eligible services including park/conservation/permit and ` +
  `afrinkong_service — a customer cannot accumulate a full holding and still ` +
  `owe Afrinkong separately`
);

/* F5-F8/F12 — THE EXCLUSIONS ARE A POSITIVE LIST WITH REASONS.
   "Not in eligibleServices" cannot be rendered. A page cannot show a list that
   exists only as the absence of entries in another list, and F12 requires the
   customer to see exclusions before booking. */
const excl = L.PROGRAMS[DRAFT].excludedServices;
report(
  excl.length === 7 &&
    excl.every((x) => typeof x.why === "string" && x.why.length > 20) &&
    ["international_flight", "visa", "travel_insurance"].every(
      (s) => excl.some((x) => x.service === s)),
  "F5-F8/F12: exclusions are a list with reasons, not the absence of entries",
  excl.map((x) => x.service).join(", ")
);

/* AND THEY AGREE WITH WHAT THE SITE ALREADY PUBLISHES.
 * `tourism/rates.json` carries an `excluded` array that the pages render.
 * Terms that disagree with the pages are worse than either, so this holds the
 * programme against the published list rather than trusting two lists to stay
 * in step by hand. */
const rates = require("../tourism/rates.json");
const published = (rates.excluded || []).join(" | ").toLowerCase();
const unmatched = ["international flights", "visas", "insurance", "meals",
                   "shopping", "tips"].filter((w) => !published.includes(w));
report(
  rates.excluded.length === 7 && unmatched.length === 0 &&
    excl.length === rates.excluded.length,
  "F12: the programme's exclusions and the site's published exclusions agree",
  `both list 7: ${rates.excluded.join("; ")}`
);

/* F8/F13 — THE JOURNEY, BROKEN INTO WHAT IT IS MADE OF, DETERMINISTICALLY.
   The components must SUM to the requirement. A table that does not add up to
   the number beside it is decorative, which is worse than no table. */
const fBreak2 = JC.breakdown(fCard, fSpec);
report(
  fBreak.total === fBreak.requirement &&
    fBreak.components.length >= 2 &&
    fBreak.outOfScope.length === 0 &&
    JSON.stringify(fBreak) === JSON.stringify(fBreak2),
  "F13: the breakdown sums to the requirement and is deterministic",
  `${fBreak.components.map((c) => `${c.label} ${c.points} TP`).join(" + ")} = ` +
  `${fBreak.total} TP, every component inside programme scope, and identical ` +
  `on a second call`
);

/* F13 — and it carries what produced it, so "why 4,750?" is answerable later. */
report(
  fBreak.rateCardVersion === fCard.v && fBreak.programVersion != null &&
    /Journey -> eligible components/.test(fBreak.derivation),
  "F13: the calculation is versioned and explicable, not approximate",
  `rate card ${fBreak.rateCardVersion}, programme ${fBreak.programId} ` +
  `v${fBreak.programVersion}`
);

/* F3 — eligible charges that are NOT in the figure are listed, not omitted.
   A customer who meets a $700 permit at booking has been misled by an omission
   just as surely as by a wrong number. */
report(
  fBreak.eligibleNotYetPriced.length > 0 &&
    fBreak.eligibleNotYetPriced.every((c) => /not in the figure above/.test(c.note)) &&
    fBreak.notIncluded.length === 7,
  "F3/F12: eligible-but-unpriced charges and excluded costs are both shown",
  `${fBreak.eligibleNotYetPriced.length} eligible charges named as not yet ` +
  `priced, and ${fBreak.notIncluded.length} exclusions — before booking, not ` +
  `buried in terms`
);

/* F14 — THE REQUIREMENT IS NOT DERIVED FROM AFRINKONG'S COST.
   8,000 TP against $6,700 of supplier cost does not mean 1 TP = $0.8375. The
   breakdown says so in a field, and nothing in the module reads a cost. */
/* The first version of this check searched for /costMinor/ and flagged
   `journeyCostMinor` — which is the journey's PRICE TO THE CUSTOMER, the
   legitimate input to goalRequirement(), and not a supplier cost at all. My
   regex, not a defect; narrowed to the thing F14 actually forbids. The near
   miss is worth keeping though: the parameter name does blur exactly the
   distinction F14 draws, and F-naming records that. */
report(
  /not Afrinkong’s supplier cost/.test(fBreak.notDerivedFromCost) &&
    !/supplierCost|supplier_cost|marginMinor|grossMargin/i.test(
      fs.readFileSync(path.join(__dirname, "..", "scripts", "points-ledger.js"),
                      "utf8")),
  "F14: no point requirement is computed backwards from supplier cost",
  `the module has no notion of supplier cost or margin — the programme defines ` +
  `entitlement and commercial margin is a separate calculation`
);

/* F9/F10 — a customer 300 short is told what they may DO, and still not given
   a conversion rate. */
const fShort = BK.request(DRAFT, { requirement: 8000 }, { available: 7700 },
                          ["journey"]);
report(
  fShort.shortfallPoints === 300 &&
    fShort.settlement.permitted === true &&
    fShort.settlement.mechanism === null &&
    fShort.alternatives.length === 4 &&
    !/\$/.test(JSON.stringify(fShort)),
  "F9/F10: points and money may be combined, and the rate is still not invented",
  `300 TP short -> mixed settlement permitted, mechanism null, and four ` +
  `alternatives. No dollar figure anywhere in the response`
);

/* F — AND A PROGRAMME MAY COVER ONLY PART OF A JOURNEY.
   "Up to 70% of the eligible journey" is a redemption rule, not a change to
   what a point is. Applied BEFORE the sufficiency test, or a 70% programme
   would cheerfully approve a full-point booking it does not permit. */
const CAP70 = L.variant(
  DRAFT,
  { compliance: "ACTIVE", maxProgrammeExposure: 5000000,
    redemptionCap: { maxPortion: 0.7, appliesTo: "eligible" } },
  "TEST-CAP-70");
const capped = BK.request(CAP70, { requirement: 10000 }, { available: 10000 },
                          ["journey"]);
report(
  capped.ok === false && capped.payableByPoints === 7000 &&
    capped.applied === 7000 && capped.remainderPoints === 3000 &&
    BK.request(DRAFT, { requirement: 8000 }, { available: 8000 },
               ["journey"]).ok === true,
  "F: a programme may cover part of a journey without redefining a point",
  `at 70%: 10,000 TP required, 7,000 payable by points, 3,000 remainder — ` +
  `stated in POINTS. At 100% a full-point booking is approved unchanged`
);

/* F11 — excess points stay points. Nothing converts a remainder to cash,
   because nothing can. */
const fAfter = L.wallet([entry("PURCHASE", 8000),
                         Object.assign(entry("RESERVE", 7800),
                                       { journeyRef: "J-F11" })]);
report(
  fAfter.available === 200 && fAfter.reserved === 7800 &&
    Object.keys(fAfter).every((k) => !/cash|value|minor/i.test(k)),
  "F11: 200 TP left after a 7,800 TP journey are 200 TP, not $200",
  `they remain available for another eligible journey; there is no field on ` +
  `the wallet that could hold a cash remainder`
);

/* F15 — a discount changes the JOURNEY's requirement, not the point.
   The customer's holding is untouched and the difference is theirs to keep. */
const fullPrice = L.goalRequirement(P, 1000000);
const promoPrice = L.goalRequirement(P, 850000);
const holder = L.wallet([entry("PURCHASE", 10000)]);
report(
  fullPrice === 10000 && promoPrice === 8500 &&
    holder.available === 10000 &&
    L.PROGRAMS[DRAFT].entitlementRate === 1,
  "F15: a promotional journey costs fewer points; existing points are not revalued",
  `10,000 TP normally, 8,500 on promotion — the holder still has ` +
  `${holder.available} TP and keeps the 1,500 difference. entitlementRate ` +
  `never moved, which is what B18 forbids moving`
);

/* And the no-retroactive-expiry reservation, named rather than assumed. */
report(
  L.PROGRAMS[DRAFT].expiry.reservedRightToIntroduce === false,
  "F/D9: this programme did not reserve a right to introduce expiry later",
  `recorded as false, so the narrow exception is something somebody had to ` +
  `write down in advance rather than argue for afterwards`
);

/* F-open — recorded, not decided. */
const fDocF = fs.readFileSync(
  path.join(__dirname, "..", "docs", "travel-point-redemption.md"), "utf8");
const fOpenF = (fDocF.match(/^\s*\|\s*F-[a-z]+\s*\|/gm) || []).length;
report(
  fOpenF >= 4 && /UNRESOLVED|not decided here/i.test(fDocF),
  "F: the open questions Decision F raises are recorded, not answered in code",
  `${fOpenF} unresolved questions carried in docs/travel-point-redemption.md`
);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
