# The decision matrix — A to AJ, reconciled against the code

The complete register, with each item's stated status checked against what is
actually enforced. **Several items marked OPEN are already settled and tested**,
and one contradicts a decision settled earlier — flagged below rather than
resolved unilaterally.

Read `travel-point-decisions.md` first for the canonical index. This is the
coverage map.

**`AFK-TP-2026.1`: `compliance: DRAFT`, `issuanceEnabled: false`.** Nothing can
issue.

---

## ⚠ One conflict needing your word

**N — Transferability** is marked OPEN with *"Recommendation:
restricted/non-transferable at launch."*

**Decision E settled the opposite**, in detail: `transferable: true`,
`secondaryMarket: false`, with gift / family-pool / corporate / estate types,
identified parties, programme-preserving terms and conservation of supply. It
explicitly reversed B14/C9 and recorded the reversal.

The code follows Decision E. I have **not** changed it back, because E was
later, explicit and detailed, whereas N reads as the earlier position restated.
If N is the current intent, say so and it is one flag — `transferable: false` —
plus updating four checks. **The prepaid-access exposure E accepted (E-analysis)
is the reason this matters.**

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
| **J** | **Rounding** | open | ✅ **now settled — see below** | this commit |
| **K** | Buying points | open | ✅ limits · ⬜ journey-linked points | `travel-point-purchase.md` |
| **L** | Buyback | open | ✅ **9 of your 10 questions answered** | `travel-point-buyback.md` |
| **M** | Cancellation | partly defined | ✅ bands, release, forfeit, final week | `travel-point-exit.md` |
| **N** | Transferability | open | ⚠ **conflicts with E — see above** | `travel-point-transfer.md` |
| **O** | Expiry | settled | ✅ no time-based expiry; D8 spend order | `travel-point-duration.md` |
| **P** | Price changes | open | ✅ **settled — reserved bookings lock** | `travel-point-continuity.md` |
| **Q** | Journey reservation | open | ✅ available→reserved→redeemed, price-locked · ⬜ reservation expiry | `booking.js` |
| **R** | Redemption moment | open | ✅ consumed at CONFIRMED · ⬜ **should it be completion?** | C-completion |
| **S** | Supplier costs | open | ✅ **settled by H** — includable, not included | `travel-point-redemption.md` |
| **T** | Payment mechanism | do not implement | ✅ **not implemented, deliberately** | — |
| **U** | Refunds/chargebacks | open | ✅ reversal by compensating entry · ⬜ recovery when spent | B-recovery |
| **V** | Accounting | counsel | 📋 five questions recorded | ⚖ |
| **W** | Regulatory | counsel | 📋 **the gate** — question 11 | ⚖ |
| **X** | Customer protection | open | ⬜ disclosures partly assembled | — |
| **Y** | Fraud/abuse | open | ⬜ **nothing built** | — |
| **Z** | Customer account | open | ✅ planning needs no account · ⬜ authenticated wallet | — |
| **AA** | Identity/KYC | counsel | 📋 E-kyc recorded | ⚖ |
| **AB** | Limits/exposure | open | ✅ **all seven exist**; `mayActivate` refuses unset | `points-ledger.js` |
| **AC** | Multi-currency | open | ⬜ single currency; B-xviii/F-e recorded | — |
| **AD** | Programme changes | open | ✅ versioned; old points keep old terms | `points-ledger.js` |
| **AE** | Programme closure | — | ✅ ladder + wind-down + migration | `travel-point-continuity.md` |
| **AF** | Death/estate | open | ✅ `ESTATE` type, documentation required · ⚖ E-estate | `transfer.js` |
| **AG** | Disputes | open | ✅ append-only, corrections name their cause · ⬜ dispute process | `schema.sql` |
| **AH** | Data architecture | settled | ✅ **your diagram is the implementation**, eleven kinds | `schema.sql` |
| **AI** | Immutable history | settled | ✅ triggers refuse UPDATE and DELETE | `schema.sql` |
| **AJ** | Activation gate | settled in principle | ✅ **ladder + `issuanceEnabled`; `status` inert** | `readiness()` |

**Count: 24 enforced, 4 recorded for counsel, 8 genuinely open, 1 conflict.**

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
| **Y** | fraud controls — stolen cards, chargeback-after-redemption, account takeover, promotional abuse, multiple accounts. **Nothing is built.** | risk |
| **X** | customer disclosures, complaint and recovery processes | product + ⚖ |
| **Z** | the authenticated wallet — planning needs no account, holding points does | product |
| **AC** | programme accounting currency, FX source and timestamp | finance |
| **K** | journey-linked versus general points, kept separable in the ledger | commercial |
| **R** | should redemption move from confirmation to completion? | product + ⚖ |
| **G-enable** | who may set `issuanceEnabled`, on what evidence | operations |

**Y is the one I would raise hardest.** Every other open item is a decision
waiting to be made; fraud is the only one where the absence itself creates
exposure the moment issuance is enabled, and it is the item with no
architecture at all behind it.

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
