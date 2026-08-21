# The decision matrix — A to AJ, reconciled against the code

The complete register, with each item's stated status checked against what is
actually enforced. **Several items marked OPEN are already settled and tested.**
The one conflict — N versus Decision E — has since been resolved: retain E, and
make the legal review a gate.

Read `travel-point-decisions.md` first for the canonical index. This is the
coverage map.

**`AFK-TP-2026.1`: `compliance: DRAFT`, `issuanceEnabled: false`.** Nothing can
issue.

---

## N — resolved: retain E, and gate it

The conflict is settled. **Decision E's design is retained** — `transferable:
true`, `secondaryMarket: false`, four transfer types — because E was later,
explicit and detailed.

But transferability materially increases prepaid-access exposure, so it does
not reach a customer on the strength of a code flag.
`transferabilityLegallyConfirmed: false` is now a **blocker in
`readiness()`**: a transferable programme cannot issue until counsel has
confirmed that specific term.

A non-transferable programme has nothing to confirm and is unblocked, so the
gate bites exactly where the exposure is. The legal review is a gate rather
than a reminder.

---

## The matrix

Legend — **✅ enforced**: a check asserts it · **📋 recorded**: written down,
not executable · **⬜ open**: nobody has decided · **⚖ counsel**.

| | item | stated | actual | where |
|---|---|---|---|---|
| **A** | Definition | settled | ✅ frame · ⬜ unit basis | `travel-point-definition.md` |
| **B** | Issuance | settled in principle | ✅ nine rules, settlement-gated | `travel-point-issuance.md` |
| **C** | Entitlement | settled in principle | ✅ two rates proved independent | `travel-point-pricing.md` |
| **D** | Programmes | mostly settled | ✅ versioned, deep-frozen, 13 of your 13 terms present | `points-ledger.js` |
| **E** | Travel Wallet | settled | ✅ a fold, never a stored balance | `points-ledger.js` |
| **F** | Travel Goal | settled | ✅ planning only, issues nothing | `travel-goal.js` |
| **G** | Cessation | settled in principle | ✅ four-rung wind-down; permission ≠ capability | `travel-point-continuity.md` |
| **H** | Redemption scope | settled in principle | ✅ basket + exclusions with reasons | `travel-point-redemption.md` |
| **I** | Cash-equivalent | settled | ✅ four concepts, never one `value` | `travel-point-display.md` |
| **J** | **Rounding** | open | ✅ **settled — half-up, one exception** | below |
| **K** | Buying points | open | ✅ limits · ⬜ journey-linked points | `travel-point-purchase.md` |
| **L** | Buyback | open | ✅ **9 of your 10 questions answered** | `travel-point-buyback.md` |
| **M** | Cancellation | partly defined | ✅ bands, release, forfeit, final week | `travel-point-exit.md` |
| **N** | Transferability | open | ✅ **E retained, gated on legal confirmation** | `travel-point-transfer.md` |
| **O** | Expiry | settled | ✅ no time-based expiry; D8 spend order | `travel-point-duration.md` |
| **P** | Price changes | open | ✅ **settled — reserved bookings lock** | `travel-point-continuity.md` |
| **Q** | Journey reservation | open | ✅ available→reserved→redeemed, price-locked · ⬜ reservation expiry | `booking.js` |
| **R** | Redemption moment | open | ✅ consumed at CONFIRMED · ⬜ **should it be completion?** | C-completion |
| **S** | Supplier costs | open | ✅ **settled by H** — includable, not included | `travel-point-redemption.md` |
| **T** | Payment mechanism | do not implement | ✅ **not implemented, deliberately** | — |
| **U** | Refunds/chargebacks | open | ✅ reversal by compensating entry · ⬜ recovery when spent | B-recovery |
| **V** | Accounting | counsel | 📦 **in the package** — §H, eight questions | `travel-point-legal-review-package.md` |
| **W** | Regulatory | counsel | 📦 **package delivered** — 46 questions | `travel-point-legal-review-package.md` |
| **X** | Customer protection | open | ✅ recovery tiers, restriction visibility · ⬜ complaint process | `travel-point-wallet.md` |
| **Y** | Fraud/abuse | open | ✅ **architecture built** · ⬜ no model | `travel-point-risk.md` |
| **Z** | Customer account | open | ✅ **architecture built** — account ≠ wallet ≠ ledger | `travel-point-wallet.md` |
| **AA** | Identity/KYC | counsel | ✅ levels shaped · 📦 in the package §C, §I | `travel-point-legal-review-package.md` |
| **AB** | Limits/exposure | open | ✅ **all seven exist**; `mayActivate` refuses unset | `points-ledger.js` |
| **AC** | Multi-currency | open | ⬜ single currency; B-xviii/F-e recorded | — |
| **AD** | Programme changes | open | ✅ versioned; old points keep old terms | `points-ledger.js` |
| **AE** | Programme closure | — | ✅ ladder + wind-down + migration | `travel-point-continuity.md` |
| **AF** | Death/estate | open | ✅ `ESTATE` type, documentation required · ⚖ E-estate | `transfer.js` |
| **AG** | Disputes | open | ✅ append-only, corrections name their cause · ⬜ dispute process | `schema.sql` |
| **AH** | Data architecture | settled | ✅ **your diagram is the implementation**, eleven kinds | `schema.sql` |
| **AI** | Immutable history | settled | ✅ triggers refuse UPDATE and DELETE | `schema.sql` |
| **AJ** | Activation gate | settled in principle | ✅ **ladder + `issuanceEnabled`; `status` inert** | `readiness()` |

**Count: 26 enforced, 4 recorded for counsel, 6 genuinely open, 0 conflicts.**

---

## J — rounding, settled this commit

Your recommendation, implemented — and the audit found the problem was worse
than a missing rule.

**Every site delivering a quantity to the customer used `Math.floor`:**

| site | was | exact | now |
|---|---|---|---|
| purchase (projection) | floor | 1073.925 | **1074** |
| promotional grant | floor | 69.93 | **70** |
| cancellation release | floor | 2400.5 | **2401** |
| migration | floor | — | half-up |
| annual buyback allowance | floor | — | half-up |

**Not one of those was a decision.** `Math.floor` is the obvious way to make a
fraction whole, and choosing it five times produced a system that rounds
against the customer everywhere. Each individual loss is under one point; the
*pattern* is what your rule forbids.

**The rule is half-up**, deliberately not "always round up in the customer's
favour" — ceiling on issuance would mint a whole point for a one-cent purchase,
and a rule that can be gamed is not a protection.

**One knowing exception**, listed in `ROUNDING.exceptions`: `goalRequirement`
ceilings, because a point is indivisible and somebody 0.3 short cannot travel.
Bounded under one point, and a check asserts nothing else joins it.

**Customer-facing points are whole units** — the ledger refuses a fractional
quantity outright, so `4,364.7 TP` cannot reach a balance however the
arithmetic upstream behaved.

### The subtlety worth knowing

Half-up on money→points would let somebody pay $25.50 for 26 points,
repeatedly. It is safe **only because that direction never issues**:
`pointsForPurchase` feeds `project()` alone, and issuance runs the other way —
`purchaseOffer(points)` derives the price from the points the customer chose.
Wiring it into an issuance path would reintroduce the exploit, and the code
says so where somebody would do it.

---

## What is genuinely still open

| | needs | who |
|---|---|---|
| **W / question 11** | the legal structure. **No money may be taken until answered.** | ⚖ |
| **Y-model** | the signals and thresholds themselves — the architecture is built, the model is not | risk |
| **X** | customer disclosures, complaint and recovery processes | product + ⚖ |
| **Z-auth** | the authentication mechanism, and what step-up actually is | security |
| **AC** | programme accounting currency, FX source and timestamp | finance |
| **K** | journey-linked versus general points, kept separable in the ledger | commercial |
| **R** | should redemption move from confirmation to completion? | product + ⚖ |
| **G-enable** | who may set `issuanceEnabled`, on what evidence | operations |

**W / question 11 is now the only thing left that blocks everything.** Every
engineering item on this matrix has an architecture; what remains of each is
either a decision somebody must make or an implementation that cannot begin
until the legal characterisation lands. The sequence Z asked for —
define → implement → test → legal review → operational controls → activate —
has reached the fourth step.

---

## The build gate

> The implementation phase should begin only after the economic + legal gates
> are complete.

Enforced, not merely agreed. Three independent refusals stand between this
repository and an issued point:

1. `fold()` refuses issuance under a non-issuing programme;
2. `mayActivate()` refuses a programme with an unset exposure limit or a rate
   that varies by tranche;
3. `issuanceEnabled` is `false`, and reaching compliance `ACTIVE` does not
   change it.

Ask `readiness('AFK-TP-2026.1')` — three blockers, and it never consults
`status`.
