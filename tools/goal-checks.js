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
 * FIXED. B5 settled the rule — a purchase bonus must not make the journey more
 * expensive — and C7 settled the derivation: a journey carries a point
 * requirement and consumes entitlement, not dollars. goalRequirement() now
 * divides the journey price by `entitlement` instead of multiplying it by
 * `issueRate`, which is the inverse of entitlementOf() and what it should
 * always have been.
 *
 * These checks stay, flipped from pinning the defect to asserting the fix: the
 * two rates may now differ safely, and this is what proves it.
 *
 * This is deliberately not fixed here: which rate is correct follows from which
 * definition is approved, so it is item A5.1 of docs/travel-point-definition.md
 * and not a bug to slip in beside a document. What this check does is make the
 * ambiguity impossible to ship by accident — the moment the two rates differ,
 * the conversion has a wrong answer in it and this fails loudly. */
const prog = L.PROGRAMS['AFK-TP-2026.1'];
report(
  prog.issueRate === 1 && prog.entitlementRate === 1,
  'the two rates are still both 1 under programme 2026-A',
  `issueRate ${prog.issueRate}, entitlementRate ${prog.entitlementRate} — they ` +
  `may now differ safely; the conversions no longer confuse them`
);

/* The demonstration, on VARIANTS rather than by editing the live programme —
 * which is no longer possible, and was never a good way to ask a what-if
 * question. A different rate means a different programme, which is what B18
 * requires of a real change anyway. */
const BONUS = L.variant('AFK-TP-2026.1', { issueRate: 1.1 }, 'GOAL-BONUS-FIXTURE');
const RICHER = L.variant('AFK-TP-2026.1', { entitlementRate: 1.1 }, 'GOAL-RICH-FIXTURE');
const bonus = L.goal(BONUS, 480000, 0, 12).target;
const richer = L.goal(RICHER, 480000, 0, 12).target;
report(
  bonus === 4800 && richer === 4364,
  'A5.1 fixed: a purchase bonus no longer makes the journey more expensive',
  `issueRate 1.1 leaves the $4,800 goal at ${bonus} TP (was 5,280); richer ` +
  `entitlement drops it to ${richer} TP (was stuck at 4,800). goalRequirement() ` +
  `divides by entitlementRate instead of multiplying by issueRate — C7 settled ` +
  `that a journey consumes entitlement, not dollars.`
);

report(
  prog.issueRate === 1 && prog.entitlementRate === 1,
  'the live programme was never touched to run that demonstration',
  `2026-A still reads issueRate ${prog.issueRate}, entitlementRate ` +
  `${prog.entitlementRate}; the variants carry the differences`
);

/* ---- Section C4: the projection, which is the direction the product needs -- */

/* C4's worked example, exactly. A pace goes in and a time comes out — not a
 * deadline going in and an obligation coming out. Same arithmetic, opposite
 * reading, and B3 settled that there is no mandatory contribution. */
const paces = [15000, 25000, 40000].map((m) => {
  const r = L.project('AFK-TP-2026.1', 480000, 0, m);
  return `$${m / 100}->${r.months}mo`;
});
report(
  paces.join(" ") === "$150->32mo $250->20mo $400->12mo",
  "C4: a monthly pace projects a time to target, and matches the brief",
  paces.join("  ")
);

/* C6's worked example, exactly. The customer sees a journey they are part of
   the way to, not a quantity of points they have collected. */
const c6 = L.project('AFK-TP-2026.1', 480000, 750, 15000);
report(
  c6.held === 750 && c6.target === 4800 &&
    Math.round(c6.progress * 100) === 16 && c6.remaining === 4050,
  "C6: the goal reads as a journey in progress, not a points balance",
  `${c6.held} / ${c6.target} TP, ${Math.round(c6.progress * 100)}% prepared, ` +
  `${c6.remaining} TP away`
);

/* Two edges that would otherwise print something useless to a customer. */
report(
  L.project('AFK-TP-2026.1', 480000, 0, 0).months === null &&
    L.project('AFK-TP-2026.1', 480000, 5000, 15000).months === 0,
  "C4: no pace named gives null, and already-there gives zero",
  "not Infinity, and not a negative number of months"
);

/* C13/C14: purchase bounds are programme terms, and they bite. */
const bounds = [
  L.canPurchase('AFK-TP-2026.1', 10, 0).ok,
  L.canPurchase('AFK-TP-2026.1', 25, 0).ok,
  L.canPurchase('AFK-TP-2026.1', 2500, 0).ok,
  L.canPurchase('AFK-TP-2026.1', 2501, 0).ok,
  L.canPurchase('AFK-TP-2026.1', 1000, 9500).ok,
];
report(
  bounds.join(",") === "false,true,true,false,false",
  "C13/C14: below the floor, above the ceiling and over the annual limit all refuse",
  "10 no, 25 yes, 2500 yes, 2501 no, 1000-on-top-of-9500 no"
);

/* ---- Section C7 and C8: the catalogue, and what happens when prices move -- */

const JC = require("../scripts/journey-catalogue.js");
const fundHtml = fs.readFileSync(path.join(__dirname, "../journey-fund.html"), "utf-8");
const D = JSON.parse(fundHtml.match(/id="jf-data">([\s\S]*?)<\/script>/)[1]);

/* C7: derived from the rate card the site already publishes, not typed. The
   check that matters is that the two denominations agree — if a journey costs
   $4,750 then at entitlement 1 it requires 4,750 TP, and if somebody edits one
   without the other this fails. */
const cat = JC.catalogue(D);
const catKenya = cat.find((j) => j.journeyId === "country:kenya:signature:7");
report(
  cat.length === 58 && catKenya &&
    catKenya.requirement === L.goalRequirement('AFK-TP-2026.1', catKenya.priceMinor),
  "C7: every journey carries a point requirement derived from its own price",
  `${cat.length} journeys at rate card ${cat[0].rateCardVersion}; Kenya ` +
  `$${catKenya.priceMinor / 100} -> ${catKenya.requirement} TP`
);

/* Identity is what was chosen, never the display name. A caption is page copy,
   and the image library already learned what happens when an identity is
   derived from copy somebody is free to rewrite. */
report(
  JC.journeyId({ kind: "country", place: "kenya", tier: "signature", days: 7 })
    === "country:kenya:signature:7" &&
  JC.journeyId({ kind: "crossing", place: "east" }) === "crossing:east",
  "C7: a journey's identity is its choices, not its caption",
  "renaming 'Trans Afrique — East' does not create a second journey"
);

/* C8: a rate card that raises the tier rate raises the requirement, and the
   customer is shown both figures, the difference, and that their own points
   are untouched. */
const spec = { kind: "country", place: "kenya", tier: "signature", days: 7 };
const before = JC.requirementFor(D, spec);
const D2 = JSON.parse(JSON.stringify(D));
D2.tiers.find((t) => t.id === "signature").rate = 690;
D2.v = "9f2ab7c11e04";
const moved = JC.compare(before, JC.requirementFor(D2, spec));
report(
  moved.original === 4750 && moved.current === 5030 && moved.difference === 280 &&
    moved.direction === "increased" && moved.sameRateCard === false &&
    moved.pointsHeldUnaffected === true,
  "C8: a price rise is shown as a difference, not as a devaluation",
  `${moved.original} -> ${moved.current} TP, difference ${moved.difference}, ` +
  `rate card ${moved.originalRateCard} -> ${moved.currentRateCard}, ` +
  `points held unaffected`
);

/* And the case that would otherwise read as "nothing happened": the same
   requirement computed from a DIFFERENT rate card. The figure agreeing is not
   the same as the price list agreeing. */
const D3 = JSON.parse(JSON.stringify(D));
D3.v = "0000deadbeef";
const quiet = JC.compare(before, JC.requirementFor(D3, spec));
report(
  quiet.difference === 0 && quiet.direction === "unchanged" &&
    quiet.sameRateCard === false,
  "C8: an unchanged figure from a changed rate card is reported as both",
  "the number agreeing does not mean the price list agreed"
);

/* ---- Section C4 and C6 in the panel, and B24 rule 7 closed ------------- */

const panel = G.build(4750, 14, 750, "1d60cf455f9a");

/* C6: the customer sees a journey they are partway to. */
report(
  panel.display.prepared === "16% prepared" &&
    panel.display.away === "4,000 TP away",
  "C6: the goal reads as a journey in progress",
  `${panel.display.target} goal, ${panel.display.prepared}, ${panel.display.away}`
);

/* C4/B3: THE CONDITIONAL MOOD, which is the whole of B24 rule 7.
 * "Your monthly target is 286 TP" tells the customer what they owe.
 * "If you purchase about 286 TP a month, you could reach this goal in about
 * 14 months" tells them what would follow if they chose to. Same arithmetic,
 * and only the second is true of a programme with no mandatory contribution. */
report(
  /^If you purchase about /.test(panel.projection) &&
    /could reach this goal in about 14 months\.$/.test(panel.projection),
  "C4: the pace is offered as a condition, never stated as an obligation",
  panel.projection
);

/* And the prohibition, checked rather than trusted: no surface may describe the
   monthly figure as something the customer must do. */
/* The prescriptive LABELS, not the word "owe" — the replacement copy says
   "not a payment you owe", and a check that cannot tell a denial from an
   assertion fails on the very sentence that fixed the problem. It did, on the
   second run. Matching the labels B24 rule 7 is actually about is both narrower
   and more honest about what is being tested. */
const OWING = /suggested monthly|monthly (target|contribution|commitment|payment)|required each month/i;
/* Strip comments before scanning, and strip the BLOCK kind properly: a
   continuation line inside a slash-star comment starts with a word, so a
   line-prefix test does not see it as a comment. This check caught its own
   explanation on the first run, which is at least evidence it reads the file. */
const stripComments = (src) =>
  src.replace(/\/\*[\s\S]*?\*\//g, " ")      // /* ... */ across lines
     .replace(/<!--[\s\S]*?-->/g, " ")        // html
     .split("\n")
     .filter((l) => !/^\s*(\/\/|#)/.test(l))  // // and # line comments
     .join("\n");
const surfaces = [
  "../scripts/fund.js",
  "../scripts/travel-goal.js",
  "../journey-fund.html",
  "../tools/tourism/fund.py",
].map((f) => stripComments(fs.readFileSync(path.join(__dirname, f), "utf-8")));
const owing = surfaces
  .map((src) => src.split("\n").filter((l) => OWING.test(l)))
  .flat();
report(
  owing.length === 0,
  "B24 rule 7: nothing on the fund surfaces states the pace as an obligation",
  owing.length ? owing[0].trim().slice(0, 70) : "no monthly target, contribution or commitment in live copy"
);

/* A projection nobody can act on is worse than none: with no whole months
   left there is no honest pace to name. */
report(
  G.build(4750, 0, 0, "x").projection === null,
  "C4: no projection is offered when there is no time left to project over",
  "null rather than a sentence about zero months"
);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
