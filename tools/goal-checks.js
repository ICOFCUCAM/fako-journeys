#!/usr/bin/env node
/* The Travel Goal is a planning calculation, and these are the checks that
 * keep it one.
 *
 *     node tools/goal-checks.js
 *
 * The risk this file exists to manage is not arithmetic. It is that a planning
 * feature drifts, one reasonable-looking commit at a time, into something that
 * reads like an account — and that a customer somewhere concludes they own
 * something. So roughly half of these checks are about vocabulary and product
 * state rather than about numbers.
 */

const path = require("path");
const fs = require("fs");
const G = require("../scripts/travel-goal.js");
const L = require("../scripts/points-ledger.js");

let pass = 0, fail = 0;
function report(ok, what, detail) {
  console.log(`${ok ? "PASS" : "FAIL"}\t${what}\t${detail}`);
  ok ? pass++ : fail++;
}
function threw(fn) { try { fn(); return null; } catch (e) { return e.message; } }

/* --------------------------------------------- the money maps to the goal */

/* The brief's own worked example: a $4,000 journey is a 4,000-point goal, and
   at 1,250 recorded that is 31.25% with 2,750 to go. */
const kenya = G.build(4000, 12, 1250, "1d60cf455f9a");
report(kenya.target === 4000 && kenya.remaining === 2750,
       "a journey estimate becomes a point target by the program's issue rate",
       `$4,000 -> ${kenya.display.target}, ${kenya.display.remaining} remaining`);

report(Math.abs(kenya.progress - 0.3125) < 1e-9 && kenya.display.progress === "31.3%",
       "progress is a proportion of the target",
       kenya.display.progress);

report(kenya.monthly === 230,
       "the monthly target is the remainder over whole months, rounded up",
       `2,750 over 12 -> ${kenya.display.monthly}`);

/* DETERMINISM. The same inputs must give the same answer on every device, in
   every session, forever — there is no clock, no randomness and no state. */
const again = G.build(4000, 12, 1250, "1d60cf455f9a");
report(JSON.stringify(kenya) === JSON.stringify(again),
       "the same plan produces a byte-identical goal every time",
       "no clock, no randomness, no stored state");

/* The 16-month case from the brief: 4,000 points at 250 a month. */
const sixteen = G.build(4000, 16, 0, "v");
report(sixteen.monthly === 250 && sixteen.display.time === "16 months",
       "the brief's worked example reproduces",
       `${sixteen.display.target} over ${sixteen.display.time} -> ${sixteen.display.monthly}`);

report(G.build(4000, 0, 0, "v").monthly === null,
       "a month too close to plan against returns no monthly figure",
       "rather than dividing by zero or inventing one");

/* --------------------------------------------- NOTHING IS ISSUED, EVER */

report(kenya.issued === false && kenya.sellable === false,
       "a goal states that nothing has been issued and nothing is for sale",
       `issued ${kenya.issued}, sellable ${kenya.sellable}`);

report(kenya.productState === "DRAFT_PROGRAM",
       "the product is in DRAFT_PROGRAM, not ACTIVE_PROGRAM",
       kenya.productState);

report(L.stateOf(null) === "PLANNING" && L.mayIssue(G.DRAFT_PROGRAM) === false,
       "no program means PLANNING, and the draft program may not issue",
       "PLANNING / DRAFT_PROGRAM / ACTIVE_PROGRAM");

/* THE CHECK THAT MATTERS MOST. Building a goal must be incapable of creating
   a point, and the ledger must refuse even if somebody tries directly. */
const attempt = threw(() => L.fold([{
  id: "TP-1", kind: "PURCHASE", quantity: 4000, status: "SETTLED",
  idempotencyKey: "k1", programVersion: G.DRAFT_PROGRAM
}]));
report(attempt !== null && /ACTIVE_PROGRAM/.test(attempt),
       "issuing a point under the draft program is refused by the ledger",
       attempt);

report(L.wallet([]).available === 0,
       "no wallet anywhere holds anything",
       "0 available — there is nothing to hold");

/* --------------------------------------------- the vocabulary of ownership */

/* A goal is a plan. If any of these words appear in what it returns, a reader
   can reasonably conclude they own something, and that is the failure mode
   this whole phase exists to avoid.
 *
 * The disclosure is exempt, and has to be: its whole job is to name the things
 * this is NOT — "not an account or a balance" — so a rule that forbids the
 * words everywhere would forbid the sentence that does the work. The exemption
 * is narrow on purpose: everything a page renders as a figure or a label is
 * still covered. */
const { disclosure, ...assertions } = kenya;
const rendered = JSON.stringify(assertions).toLowerCase();
const forbidden = ["balance", "your points", "owned", "available", "wallet",
                   "deposit", "savings", "account", "withdraw", "invest"];
const found = forbidden.filter((w) => rendered.indexOf(w) !== -1);
report(found.length === 0,
       "a goal never uses the vocabulary of an account or a holding",
       found.length ? "found: " + found.join(", ") : "target/recorded/remaining only");

report(typeof kenya.disclosure === "string" && kenya.disclosure.length > 80 &&
       /not on sale|nothing has been purchased/.test(kenya.disclosure),
       "every goal carries its disclosure as data, not as page copy",
       "so numbers cannot be rendered without it");

report(/not an account or a balance/.test(kenya.disclosure),
       "the disclosure denies the two things a reader is most likely to assume",
       "an account, and a balance");

/* --------------------------------------------- provenance of the figure */

report(kenya.rateCardVersion === "1d60cf455f9a" &&
       kenya.programId === "AFK-TP-2026.1" && kenya.programVersion === 1,
       "a goal records the rate card and program version that produced it",
       `rates ${kenya.rateCardVersion}, program ${kenya.programId} v${kenya.programVersion}`);

report(G.build(4000, 12, 0).rateCardVersion === "unknown",
       "an unstamped calculation says so rather than implying provenance",
       "rateCardVersion 'unknown'");

report(kenya.programStatus === "draft",
       "the program status travels with the figure",
       "a page cannot show the number without being handed 'draft'");

/* --------------------------------------------- the reader's own note */

report(G.readRecorded("1250") === 1250 && G.readRecorded("-5") === 0 &&
       G.readRecorded("abc") === 0 && G.readRecorded("99999999") === 1000000,
       "what the reader records is clamped, never trusted raw",
       "negatives and nonsense become 0; absurd values are capped");

report(G.build(4000, 12, 9999).remaining === 0 &&
       G.build(4000, 12, 9999).progress === 1,
       "recording more than the target does not produce negative remaining",
       "progress caps at 100%");

/* --------------------------------------------- the module cannot issue */

const src = fs.readFileSync(
  path.join(__dirname, "..", "scripts", "travel-goal.js"), "utf-8");
const code = src.replace(/\/\*[\s\S]*?\*\//g, "");
const issuing = ["fold(", "PURCHASE", "TRANSFER_IN", "ADJUST_UP", "wallet("]
  .filter((w) => code.indexOf(w) !== -1);
report(issuing.length === 0,
       "the goal module does not touch the ledger's issuing side at all",
       issuing.length ? "found: " + issuing.join(", ") : "it calls goal() and program() only");

/* --------------------------------------------- the planner is untouched */

const fundMath = fs.readFileSync(
  path.join(__dirname, "..", "scripts", "fund-math.js"), "utf-8");
report(fundMath.indexOf("Point") === -1 && fundMath.indexOf("TP") === -1,
       "the existing fund arithmetic is unchanged and knows nothing of points",
       "the planner works exactly as it did");

/* ---- the two rates, and the defect Section A found --------------------- */

/* `goal()` converts a journey price to a point target using issueRate — points
 * per dollar PAID — where the definition requires entitlement, the travel value
 * a point REDEEMS. It is invisible today because the programme sets both to 1.
 *
 * This is deliberately not fixed here: which rate is correct follows from which
 * definition is approved, so it is item A5.1 of docs/travel-point-definition.md
 * and not a bug to slip in beside a document. What this check does is make the
 * ambiguity impossible to ship by accident — the moment the two rates differ,
 * the conversion has a wrong answer in it and this fails loudly. */
const prog = L.PROGRAMS['AFK-TP-2026.1'];
report(
  prog.issueRate === 1 && prog.entitlement === 1,
  'the two rates are still equal, which is the only reason goal() looks right',
  `issueRate ${prog.issueRate}, entitlement ${prog.entitlement} — if these ever ` +
  `differ, fix goal() per A5.1 before changing this check`
);

/* And the demonstration, so the failure above is self-explanatory rather than
 * a number somebody has to go and re-derive. */
const saved = { i: prog.issueRate, e: prog.entitlement };
prog.issueRate = 1.1;
const bonus = L.goal('AFK-TP-2026.1', 480000, 0, 12).target;
prog.issueRate = saved.i;
prog.entitlement = 1.1;
const richer = L.goal('AFK-TP-2026.1', 480000, 0, 12).target;
prog.entitlement = saved.e;
report(
  bonus === 5280 && richer === 4800,
  'the defect is present and behaves as Section A records it',
  `a purchase bonus RAISES the $4,800 goal to ${bonus} TP (should stay 4800); ` +
  `richer entitlement leaves it at ${richer} TP (should fall to 4364)`
);

/* The programme must be restored exactly, or every later check in this file is
 * measuring a programme this one edited. */
report(
  prog.issueRate === 1 && prog.entitlement === 1,
  'the demonstration restored the programme it borrowed',
  `issueRate ${prog.issueRate}, entitlement ${prog.entitlement}`
);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
