# Section E — repurchase, cancellation, transferability and expiry

**Status: architecture implemented, terms provisional, legal questions
UNRESOLVED.** Nothing in this section may be offered to a customer. The
shipping programme `AFK-TP-2026.1` is `compliance: DRAFT`, and as of this
section a draft programme refuses to *quote* a repurchase, not merely to
settle one.

This is the section where a travel product is most likely to turn accidentally
into a financial one, so the reasoning is written out rather than summarised.

---

## E1 — repurchase is an offer, never a right

`buyback.discretionary: true`, and the quote says so in the sentence a customer
would actually read:

> Afrinkong may repurchase these points at 90% of what you paid for them. This
> is an offer under the terms of this programme, not a guaranteed right of
> redemption.

A discretion that is never exercised is not a discretion, so the request
lifecycle keeps two different refusals apart:

| state | meaning |
|---|---|
| `REFUSED` | the **terms** did not permit it, and the customer can be told exactly which term |
| `REJECTED` | the terms permitted it and **Afrinkong chose not to**, with a reason recorded |

Collapsing them would present a discretionary decision as a rule, which is
precisely the misrepresentation this section exists to avoid.

---

## E2 — the framing problem, and how B12 and E2 were reconciled

This is the one genuine contradiction in the specification, and it is recorded
here rather than resolved silently.

- **B12 settled** repurchase at *"90% of the applicable purchase
  consideration"* — i.e. of the money the customer paid.
- **E2 then said** the product must not be described as *"you get 90% of the
  money you paid"*, and the decision table added: *"Basis of 90% —
  programme-defined; not automatically original purchase price."*

Both are right about different risks. B12's concern is arbitrage: under a
promotional bonus above `1/rate − 1`, a repurchase quoted on *entitlement*
pays out more than came in, and the programme becomes a machine for turning
$1,000 into $1,050. E2's concern is characterisation: money in, wait, money
out is a deposit product whatever the terms call it.

**The resolution.** `basis` became a programme term with three permitted
values — `consideration`, `entitlement`, `programme` — and a new rail sits
above all of them:

```js
maxPayableIsConsideration: true   // never pay out more than came in
```

The rail closes B12.2's arbitrage under *every* basis rather than under one,
and does it without defining repurchase as a refund of a purchase price. A
quote states which basis produced it, and whether it was capped.

`AFK-TP-2026.1` sets `basis: 'consideration'` — provisionally, and that
provisionality is the point: the basis is now a term counsel can change
without a code change.

---

## E3 — five steps, and only the last one touches a ledger

```
REQUESTED
├── REFUSED           (ineligible; nothing was ever quoted)
└── QUOTED
    ├── LAPSED        (the customer did not answer in time)
    ├── DECLINED      (the customer said no)
    └── ACCEPTED
        ├── REJECTED  (Afrinkong's discretion — E1)
        └── APPROVED
            └── SETTLED   -> implies exactly one BUYBACK ledger entry
```

A single `buyback(points)` call would collapse five separable decisions into
one. Each of them is one somebody can refuse, and the customer asking what they
would be offered has not sold anything: **a quote removes no points and leaves
no trace**.

`scripts/buyback.js` appends nothing — it returns the entry a settlement
*implies*, the same discipline `scripts/booking.js` follows, so a screen cannot
consume points on its own.

### A quote is not a hold

Between quotation and settlement the customer may have reserved those same
points against a journey. Honouring a stale quote would let one set of points
be both sold back and travelled on, so `settle()` **re-quotes against the
ledger as it stands now** and refuses if the request no longer qualifies.
Settlement requires the current ledger to be supplied; defaulting to the
quotation's own figures would restore exactly that bug.

### It moves no money

`SETTLED` means the ledger event: the points have left the wallet. Paying the
customer is a separate act in a system that does not exist yet, and the result
carries `payment: null` rather than implying otherwise.

---

## E4 — the compliance gate reaches quotation

`mayBuyBack()` permits repurchase in the same states as redemption —
`PILOT`, `ACTIVE`, `CLOSED_TO_NEW_PURCHASES`, `REDEMPTION_PERIOD`. That
symmetry is an argument, not a coincidence: repurchase discharges the
obligation a point represents, so a programme that may still honour a point may
still buy one back.

The gate runs **before any arithmetic**. A draft programme that computed a
payable figure and only then declined to pay it would have produced the number,
and a number that exists is a number somebody eventually renders.

---

## E5 — the eligibility controls, all programme parameters

| control | `AFK-TP-2026.1` | provisional? |
|---|---|---|
| `minHoldDays` | 90 | yes — B-x |
| `minPoints` | 100 | yes — B-x |
| `maxPerYear` | 5,000 | yes — B-x |
| `rate` | 0.90 | yes |
| `promotionalEligible` | `false` | settled (E7) |
| `reservedEligible` | `false` | settled (E-ii) |

None of these is a constant in the application. A different programme sets
different numbers and the code obeys without being edited.

---

## E6 — the restricted window finally reaches the quote

**This closes B24 rule 22, the last contradicted rule in that audit.**

The failure is worth keeping in the record. `cancellation()` computed
`buybackEligible: false` inside seven days, and `buybackQuote()` had no
departure date to ask about — two functions holding half a rule each, which is
how somebody inside the final window gets a quote they should never have been
offered.

The repair was *not* to re-implement the band inside the quote. It was to pass
the customer's commitments in:

```js
buybackQuote(programId, entries, points, heldDays, boughtBackThisYear,
             commitments)   // [{ journeyRef, daysToDeparture, points }]
```

The band stays defined in exactly one place, and a programme that sets a
different window is obeyed for free.

---

## E7 — promotional points are not automatically repurchasable

Instructed explicitly, and the consideration basis answers it without a special
case: nothing was paid for a granted point, so there is nothing to pay 90% of.
`promotionalEligible: false` states it as a term as well, so a programme that
changed basis does not accidentally change this.

---

## E8 — non-transferability in V1, enforced rather than declared

`transferable: false` was a term nothing read. The fold now refuses a
`TRANSFER_IN` or `TRANSFER_OUT` entry under a programme that forbids transfer —
at the point the entry is written, not at review.

The kinds themselves stay. B14 settled that **policy is not capability**: an
administrative correction, or a later programme, still needs them. A programme
that forbids transfer simply never emits one.

---

## E9 — cancellation and repurchase are different events

They are different in the ledger, not merely in the documentation:

| event | entries | against |
|---|---|---|
| cancellation | `RELEASE` + `REDEEM` (forfeit) | the `journeyRef` |
| repurchase | `BUYBACK` | no journey |

Nothing downstream has to infer which happened from amounts and timing.

### Validity is a programme term, per lot

```js
expiry: { purchased: null, promotional: 24 }   // months; null = never
```

Purchased points do not lapse because time passed — a customer-trust decision
that makes the obligation *more* durable, deliberately. One scalar could not
have expressed two rules, which is why this is a block.

`validity()` and `hasLapsed()` take elapsed months **from the caller**. No
clock: D21.4 forbids a balance moving because time passed, and lapsing still
costs an explicit `EXPIRE` entry that a human or a job appended.

---

## E10 — a programme stops selling long before it stops owing

| compliance state | may issue | may redeem | may repurchase |
|---|---|---|---|
| `ACTIVE` | yes | yes | yes |
| `CLOSED_TO_NEW_PURCHASES` | **no** | yes | yes |
| `REDEMPTION_PERIOD` | no | yes | yes |
| `CLOSED` | no | **no** | no |

Points already issued do not vanish because new ones are no longer offered, so
closure is a sequence with a redemption period in it rather than an off switch.
`CLOSED` is not `RETIRED`: closed means the redemption period ran and the
programme's terms say what became of anything outstanding; retired means it
never traded.

---

## E-invariants — the four proved by name

In `tools/points-checks.js`:

| | invariant | how it is proved |
|---|---|---|
| E-i | a repurchase cannot exceed eligible available points | at both ends — the quote refuses 6,000 of 5,000, **and** the fold refuses the entry independently, because a screen that bypassed the quote is how this would happen |
| E-ii | a repurchase cannot consume reserved points | `available` excludes `reserved` by construction, so the same arithmetic that computes every balance enforces it |
| E-iii | a repurchase cannot mutate historical issuance | the `PURCHASE` entry is byte-identical before and after; `acquired` is unchanged; only `available` moves and a new entry carries it |
| E-iv | a repurchase cannot occur under a draft programme | `AFK-TP-2026.1` refused before any arithmetic, with no `payableMinor` in the result at all |

---

## E11 — UNRESOLVED. Recorded, not decided in code.

These are legal, accounting and regulatory questions. Nothing below has been
answered by an implementation choice, and none may be answered by one.

| | question | owner |
|---|---|---|
| E-a | Does a discretionary repurchase offer, published in programme terms, create a redemption right in substance regardless of the wording? | counsel |
| E-b | Does `maxPayableIsConsideration` — a cap at money paid in — itself push the product toward a deposit characterisation, or away from it? | counsel |
| E-c | Which basis (`consideration` / `entitlement` / `programme`) should `AFK-TP-2026.1` actually carry at activation? | counsel + finance |
| E-d | Is a repurchased point derecognised as revenue, as a liability settlement, or as a contra-issuance? | accounting |
| E-e | What identity, sanctions and payment-instrument checks must clear before a repurchase settles, and does repurchase to a different instrument than the one paid change the analysis? | counsel |
| E-f | How do disputed or charged-back purchases propagate to repurchase eligibility, and can a repurchase be clawed back after settlement? | counsel + reconciliation design |
| E-g | May a repurchase be paid in a currency other than the one paid, and who carries the FX movement? (B-xix, unchanged) | counsel + finance |
| E-h | On programme closure, what happens to points still outstanding when `REDEMPTION_PERIOD` ends — forfeiture, mandatory repurchase, or migration to a successor programme? | counsel |
| E-i-q | Do the E5 controls (`minHoldDays` 90, `maxPerYear` 5,000) sit at defensible values, or do they read as friction designed to discourage a right? | counsel |
| E-j | Does forfeiture on cancellation inside seven days need to be characterised as a cancellation charge rather than as a loss of entitlement? | counsel |
| E-k | Are promotional points, which expire and cannot be repurchased, a different instrument requiring separate treatment rather than a lot of the same one? (B-xvii, sharpened) | counsel + accounting |

### Carried forward from earlier sections, still open

| | question | change |
|---|---|---|
| B-ii | which lot is consumed or repurchased first | unchanged — three dimensions: programme, purchased-vs-promotional, currency |
| B-x | are `minHoldDays`, `minPoints`, `maxPerYear` the right controls, at what values | now E-i-q as well |
| B-xi | may a repurchase be refused case by case, or only by published rule | **architecture now supports both**; the decision is still counsel's |
| B-xii | may a customer with an active reservation repurchase their *unreserved* points | ✅ **resolved by E6** — yes, unless those points are committed inside a restricted window |
| B-xiii | should `buybackQuote` take the booking so the 7-day window is enforced where the quote is produced | ✅ **resolved by E6** |

---

## What this section did **not** do

- No money moved, and no settlement mechanism was implemented.
- No programme was activated; `AFK-TP-2026.1` remains `DRAFT`.
- No legal conclusion was drawn about stored value, money transmission,
  refunds, buyback rights, transferability, expiry or regulatory treatment.
- No promotional point became repurchasable.
- Repurchase is nowhere described as a refund of a purchase price.
