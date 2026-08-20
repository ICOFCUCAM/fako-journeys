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
const bbProg = L.PROGRAMS[DRAFT];
const bbSaved = { rate: bbProg.issueRate, status: bbProg.status };
bbProg.status = "active";
bbProg.issueRate = 1.25;
const paidMinor = 100000;                                  // $1,000
const issued = L.pointsFor(DRAFT, paidMinor);
const quote = L.buybackQuote(
  DRAFT,
  [Object.assign(entry("PURCHASE", issued),
                 { payment: { amountMinor: paidMinor, currency: "USD" } })],
  issued, 100, 0
);
bbProg.issueRate = bbSaved.rate;
bbProg.status = bbSaved.status;

report(
  issued === 1250 && quote.payableMinor === 90000 &&
    quote.basis === "consideration",
  "B12/C16: the arbitrage is closed — repurchase pays on what was paid",
  `a 25% bonus on $1,000 issues ${issued} TP and quotes $${quote.payableMinor / 100}, ` +
  `not $1,125. 90% of consideration cannot exceed consideration, so no bonus ` +
  `rate makes buy-then-repurchase profitable. Was exploitable above an 11.1% bonus.`
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
  bbProg.transferable === false && bbProg.secondaryMarket === false,
  "B14/B15: the programme forbids transfer and any secondary market",
  `transferable ${bbProg.transferable}, secondaryMarket ${bbProg.secondaryMarket} ` +
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
const r21Prog = L.PROGRAMS[DRAFT];
const r21Saved = r21Prog.status;
r21Prog.status = "active";
const booked = [
  Object.assign(entry("PURCHASE", 5000),
                { payment: { amountMinor: 500000, currency: "USD" } }),
  entry("RESERVE", 4800),
];
const onReserved = L.buybackQuote(DRAFT, booked, 4800, 100, 0);
const onAvailable = L.buybackQuote(DRAFT, booked, 200, 100, 0);
r21Prog.status = r21Saved;

report(
  onReserved.eligible === false && onAvailable.eligible === true,
  "B24 rule 21: reserved points cannot be repurchased, available ones can",
  `4,800 reserved -> "${onReserved.why}"; 200 available -> eligible`
);

/* Rule 22 — no repurchase inside the final seven days. NOT enforced, and the
 * shape of the failure is the interesting part: cancellation() computes
 * buybackEligible:false and buybackQuote() has no departure date to ask about.
 * Two functions holding half a rule each, which is how somebody inside the
 * final window gets a quote they should never have been offered. */
const ladderSaysNo = L.cancellation(DRAFT, 5, 4800).buybackEligible === false;
const quoteCanAsk = /departure|daysTo|booking/i.test(
  L.buybackQuote.toString().match(/\(([^)]*)\)/)[1]);
report(
  ladderSaysNo && !quoteCanAsk,
  "B24 rule 22: the seven-day bar is computed in one place and ignored in another",
  "cancellation() returns buybackEligible:false at 5 days; buybackQuote() takes " +
  "no booking or departure date and cannot consult it. See B13.1"
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
const dSaved = { compliance: dProg.compliance, status: dProg.status,
                 exposure: dProg.maxProgrammeExposure };

dProg.status = "active";                       // the old one-word activation
const oneWord = L.mayIssue(DRAFT);
dProg.status = dSaved.status;
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

dProg.compliance = "APPROVED";
const needExposure = L.mayTransition(DRAFT, "PILOT");
dProg.maxProgrammeExposure = 5000000;
const withExposure = L.mayTransition(DRAFT, "PILOT");
dProg.maxProgrammeExposure = dSaved.exposure;
dProg.compliance = dSaved.compliance;
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

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
