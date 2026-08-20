# Decision B — how money becomes Travel Points

**SETTLED as canonical. Enforced in code and in the schema.** The programme
remains `compliance: DRAFT`; nothing is on sale.

---

## A note on the numbering, because it now collides

This repository already has Sections A–F, and Decision B overlaps two of them.
Rather than invent a third register, the mapping is stated once:

| Decision | already lives in | relationship |
|---|---|---|
| **Decision B** (this) | Section B (`travel-point-economics.md`) + Section F (`travel-point-pricing.md`) | Decision B is the **canonical statement**; B and F are the working record of how it was arrived at |
| **Decision C** (proposed next: cancel, sell back, transfer, dispose) | **Section E** (`travel-point-buyback.md`) — already built | see the closing section |

Where they disagree, this document wins, and the disagreements are named below
rather than smoothed over.

---

## The nine rules, and what enforces each

| | rule | enforced by | status |
|---|---|---|---|
| B1 | Money is the payment medium | `payments` table; no money on any ledger row | ✅ |
| B2 | Travel Points are the issued entitlement unit | `point_ledger.quantity`, whole points only | ✅ |
| B3 | `issueRate` determines points issued from a **settled** purchase | `pointsForPurchase()`, `issuance()` | ✅ |
| B4 | `entitlementRate` independently determines what points redeem for | `entitlementOf()`, `goalRequirement()` | ✅ |
| B5 | No cash balance, no intrinsic monetary value | `wallet()` has no money field; `MONEY_MOMENTS` is a closed list of three | ✅ |
| B6 | Issued **only** after payment settlement | `maySettleIssuance()`; refused at the builder **and** in `fold()` | ✅ **new** |
| B7 | Promotional points are points; origin recorded in the immutable ledger | `PROMOTION` kind, own lot, no `payment_id` | ✅ **schema repaired** |
| B8 | No interest, yield, appreciation or time-based growth | no clock in the module; vocabulary scanned across seven surfaces | ✅ **new** |
| B9 | History never edited; corrections are new events | append-only triggers; `reversal()` returns `ADJUST_DOWN` + `corrects` | ✅ **new** |

---

## B3/B4 — the worked example, run

```
Early Planner Programme          issueRate 1.10, entitlementRate 1
customer pays                    $1,000
receives                         1,100 TP
which carry                      1,100 TP of travel entitlement
cash value                       none
```

The two rates moved independently and neither touched the other. This is the
whole reason they are separate variables while both read 1 in the standard
programme: **a model where the two are the same number is indistinguishable
from a model where there is only one, right up until somebody changes it.**

---

## B6 — the boundary that looks finished

Seven payment states. Exactly one issues a point.

| state | issues? | |
|---|---|---|
| `pending` | no | |
| `requires_capture` | no | we have not asked for the money |
| `authorised` | **no** | ← **the dangerous one** |
| `settled` | **yes** | the money is ours |
| `failed` / `refunded` / `charged_back` | no | it was never ours, or is not now |

`authorised` is named explicitly because it is the one that looks finished. The
bank has agreed to pay and has not paid, and an authorisation can be withdrawn.
Points issued against one are entitlement created against money that never
arrived.

The sequence, exactly as the decision states it:

```
customer payment → payment confirmed → ledger entry → points issued → balance derived
```

**Enforced twice, deliberately.** `issuance()` refuses to build entries against
an unsettled payment; and `fold()` throws on an entry marked `SETTLED` whose
`payment.status` is not — because a caller that bypassed `issuance()` is
exactly how this would happen. Before this, such an entry folded cleanly.

---

## B7 — the one part of Decision B that needed deciding

The decision's example says the extra 100 TP is *"a promotional issuance
benefit"* while producing it from `issueRate 1.10`. **Those are two different
mechanisms, and they give the points different terms.** Both are legitimate;
they are not interchangeable.

| | `issueRate 1.10` | `PROMOTION` grant |
|---|---|---|
| what the ledger says | `PURCHASE 1,100` | `PURCHASE 1,000` + `PROMOTION 100` |
| the extra points are | **purchased** | **granted** |
| repurchasable (E7) | yes | no |
| expires (E9) | never | 24 months |
| forfeited on cancellation | no | yes |
| origin in the ledger | *not distinguishable* | recorded as its own entry |
| money paid for them | $1,000 for all 1,100 | $1,000 for 1,000; nothing for 100 |

**You cannot get grant terms from a rate.** Under `issueRate 1.10` the ledger
says `PURCHASE 1,100` and nothing marks which 100 were the benefit — so B7's
own requirement, *"their origin is recorded in the immutable ledger"*, is not
met, and E7 and E9 have nothing to act on.

### The recommendation

Use the **rate** when the intent is *"this programme is simply better value"* —
an early-planner cohort that has genuinely committed earlier, whose points
should behave exactly like anyone else's. Use a **grant** when the intent is
*"here is a bonus"* — something temporary, marked, expiring, and not
repurchasable.

Both are now expressible and the code will not let one masquerade as the
other. Which one `EARLY-2026` should actually use is **B-mechanism**, below.

### This does not conflict with F2

F2 forbids `issueRate` varying **by tranche within one programme** — "buy 5,000
and get them at $0.91" — because that gives a point a different money price in
each tranche, and a thing with a spot price per tranche is a currency.

A **named programme with its own single rate** is a different thing entirely,
and `mayActivate()` permits it: `EARLY-2026` at 1.10 activates cleanly. Every
point in that programme cost the same, and B18 keeps the terms with the points
forever. The distinction is *one rate per programme*, not *one rate ever*.

---

## B8 — no interest, no yield, no growth

Asserted four ways:

1. no clock anywhere in the module (D21.4 — `Date` and `now()` are absent);
2. no ledger kind that adds points without an explicit entry;
3. `hasLapsed()` and `cancellation()` take elapsed time **from the caller**, so
   even expiry costs a human-appended `EXPIRE` entry;
4. the **vocabulary** — `APR`, `APY`, interest, yield, dividend, accrual,
   appreciation, compounding, "return on" — scanned across seven customer-facing
   files, comments stripped. None present.

The fourth is there because B8's realistic failure mode is a marketing word,
not a line of arithmetic.

The extra points under `EARLY-2026` exist **because the customer purchased
under that programme**, not because time passed. That sentence is the whole
distinction and it survives only if nothing else in the product implies growth.

---

## B9 — history is never edited

A chargeback in June does not travel back to March and un-issue points. Both
facts survive: the customer *did* buy 1,000 points on the third, and the payment
*was* reversed on the seventh.

```
reversal() -> ADJUST_DOWN 1,000, corrects: TP-ORIG, reason: "chargeback CB-1"
```

After folding: `available` falls to 0, and `acquired` still records the 1,000
that were issued. The original entry is byte-identical.

`ADJUST_DOWN` rather than a new kind — B7.1 fixed the set of kinds so adding
one has to be argued for, and a reversal *is* an administrative removal. The
`corrects` pointer is what makes it a reversal rather than an unexplained
deduction, and `fold()` refuses a correction that names an entry it has not
already seen.

### The case that is reported, not decided

If the customer already committed the points to a journey, the compensating
entry would overdraw the wallet. `reversal()` returns `recoverable: 100,
shortfall: 900` and says the question has not been answered. What follows —
pursue the debt, void the booking, absorb it — is legal and commercial. See
**B-recovery**.

---

## A defect this decision surfaced

**`PROMOTION` was in the module and not in the database.** It was added as the
eleventh kind (B16, instructed by C11), and `point_ledger`'s `kind` check
constraint was never updated with it. For several commits the database
physically could not record a promotional grant — which is exactly the origin
B7 requires to be *in the ledger*. Nothing failed, because nothing compared the
two.

Repaired, along with three related gaps, and a check now asserts the module and
the schema agree on every kind:

- `PROMOTION` added to the `kind` constraint and to the `travel_wallets` view,
  which also now exposes `purchased` and `granted` separately;
- `promotion_has_no_payment` — a grant with a `payment_id` would be a purchase
  wearing a grant's label;
- `issue_rate_applied` — stamped so one row is readable on its own, and so a
  disagreement with the programme is detectable rather than silent;
- `corrects` — the module has required it since B4; the schema had no column.

The amount paid is still **not** stamped on the ledger row. B19/B22 keep money
in `payments` and entitlement in the ledger, joined by a reference, and an
amount recorded in two places is one that can disagree with itself. The
decision's sketch line *"money paid: $1,000"* is satisfied by `payment_id`.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| B-mechanism | Should `EARLY-2026` deliver its 10% as a **rate** (purchased points, repurchasable, never expiring) or as a **grant** (marked, expiring, not repurchasable)? They are different products and the code now permits either. | commercial + counsel |
| B-recovery | When a payment is reversed after the points are committed or consumed, what follows? Recovery of the debt, voiding the booking, or absorbing the loss. | counsel + finance |
| B-clawback | Can a *repurchase* already settled be clawed back if the original purchase is later charged back? (E-f, unchanged) | counsel |
| B-cohort | Does offering different `issueRate`s to different cohorts at the same time create a pricing or discrimination exposure, and must the rate differences be published? | counsel |
| B-recognition | Is a point issued under a 1.10 rate recognised differently from one issued under 1.00 plus a grant? The customer's position is identical; the accounting may not be. | accounting |

Plus everything still open in `travel-point-pricing.md` (F-a … F-g) and
`travel-point-buyback.md` (E-a … E-k).

---

## Decision C is already built

The next decision named — *"what happens when a customer wants to cancel, sell
back, transfer, or otherwise dispose of Travel Points"* — is **Section E**,
implemented and pushed last turn: `docs/travel-point-buyback.md`.

It covers repurchase as a discretionary offer with a five-step lifecycle,
cancellation bands attached to the booking, non-transferability in V1 enforced
at the fold, programme-defined validity per lot, and the closure ladder. Four
invariants are proved by name.

Two things there want your decision rather than more code:

- **the B12/E2 reconciliation** — `basis` is a programme term with
  `maxPayableIsConsideration` as the arbitrage rail (E2, and E-c);
- **whether `basis` should be `consideration` at activation** at all.

Worth reading before restating Decision C, so the two do not diverge the way
Decision B and Section F nearly did.
