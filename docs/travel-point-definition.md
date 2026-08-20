# Section A — the canonical commercial definition of a Travel Point

**Status: PROPOSAL. Not approved, not implemented.**

This paper settles one question and deliberately settles nothing else: *what
is one Travel Point?* Everything in `docs/economic-model-decisions.md` inherits
the answer, which is why it is decision 1 there and why it is worth its own
document here.

Nothing in this paper has been built. The programme remains `draft`, the
product state remains `DRAFT_PROGRAM`, and `scripts/points-ledger.js` still
refuses to issue a point. Approving the definition does not release any of the
downstream work in §A5 — each of those is a separate decision that becomes
*answerable* once this one is fixed.

---

## A1. The recommended definition

> **A Travel Point is one unit of travel purchasing entitlement issued by
> Wankong LLC under a named Travel Point Programme, redeemable toward eligible
> Afrinkong travel services on the terms of the programme under which it was
> issued.**
>
> A Travel Point is not money, is not redeemable for cash as of right, carries
> no interest, confers no ownership, and has no value outside the programme
> that issued it.

Three properties do the work, and each is a commitment rather than a phrasing
preference:

**It is a unit of entitlement, not of currency.** What a point entitles you to
is *travel*, quantified in Afrinkong travel value. It is never defined as a
quantity of money, even when the arithmetic happens to line up.

**Its terms belong to its programme, not to the company.** A point issued under
`AFK-TP-2026.1` keeps 2026 terms permanently. Afrinkong can offer different
terms in 2028 by issuing a new programme; it cannot reach back and change what
an existing point means.

**It is indivisible and integral.** One point is the smallest unit. There are
no fractional points. (See §A5.2 — the code currently rounds in three different
directions and that is a consequence of this clause, not an accident.)

## A2. The alternatives, and why not

| candidate | reading | why rejected |
|---|---|---|
| **1 point = $1** | a point is a dollar held on account | This is stored value. It makes the balance a monetary claim, invites the "so it's a bank account" reading, and in several jurisdictions is the definition of a regulated instrument. It also destroys the ability to price a programme differently later, because a dollar cannot be worth something else next year. |
| **1 point = 1 dollar of Afrinkong travel** | a point is a discount voucher denominated in currency | Better, but still denominates the entitlement in money, which means every display becomes a cash figure and every price change becomes a revaluation of an existing holding. |
| **1 point = 1 unit of travel purchasing entitlement** ✅ | a point is a contractual right against the programme | Keeps the unit non-monetary, lets `entitlement` be a programme parameter rather than an identity, and survives a change in journey pricing without changing what anybody already holds. |

The distinction is not cosmetic. Under candidate 1 a customer holding 4,800
points holds $4,800 of somebody else's money. Under the recommendation they
hold a right to 4,800 units of Afrinkong travel, and what those units buy is a
matter of the programme and the journey price on the day.

## A3. What the code has already committed to

The definition is not being invented here; most of it is already load-bearing.
Approving §A1 ratifies these; rejecting it means unwinding them.

| commitment | where | what it means |
|---|---|---|
| two separate rates, never one | `scripts/points-ledger.js` — `issueRate`, `entitlement` | The price of acquiring a point and the travel value it redeems are different numbers. Collapsing them is what makes a point look like a dollar. |
| terms are immutable after issue | `tools/points/schema.sql:87` | A trigger refuses any `UPDATE` changing `issue_rate`, `entitlement`, `buyback` or `cancellation` on an existing programme. |
| the ledger is append-only | `tools/points/schema.sql:191` | An error is corrected by appending a reversing entry, never by editing history. |
| no balance is ever stored | `wallet()` folds from entries | The balance is derived, so it cannot disagree with the history. |
| no interest, no growth, no yield | absent by design | There is no function anywhere that makes a holding larger with the passage of time. |
| buyback is discretionary | programme `buyback.discretionary: true` | A *guaranteed* cash redemption is the clause most likely to change the product's regulatory character. The safe default is encoded. |
| nothing may be issued yet | `PRODUCT_STATE`, `fold()` | Issuance under a non-active programme throws. Two tests assert it. |

## A4. A defect this review found

`goal()` — the one function that turns a journey price into a point target, and
therefore the only place the definition currently reaches a customer — uses the
**wrong one of the two rates**.

```js
var target = Math.ceil(journeyCostMinor / 100 * program(programId).issueRate);
```

`issueRate` is points-per-dollar-*paid*. The question "how many points does
this journey need?" is answered by `entitlement`, the travel value a point
*redeems*. The correct form is the inverse of `entitlementOf()`:
`journeyCost / entitlement`.

It is invisible today because both numbers are `1`. Measured with them apart:

| programme | journey | target now | target correct |
|---|---|---:|---:|
| `issueRate 1, entitlement 1` | $4,800 | 4,800 TP | 4,800 TP ✅ |
| `issueRate 1.1` (a purchasing bonus) | $4,800 | **5,280 TP** | 4,800 TP |
| `entitlement 1.1` (richer redemption) | $4,800 | **4,800 TP** | 4,364 TP |

The middle row is backwards in a way a customer would notice: offering a bonus
on purchase makes the goal *larger*. The bottom row ignores the bonus entirely.

The other three conversions are correct — `pointsFor` and `priceOf` use
`issueRate`, `entitlementOf` uses `entitlement`. Only `goal()` conflates them,
in exactly the way decision 1 of the decisions paper warns against.

**Not fixed here.** Which rate is correct follows directly from which definition
is approved, so the fix is a §A5 item, not a bug fix to slip in beside a
document. A regression test now pins the current state and fails the moment the
two rates diverge, so this cannot ship silently — see `tools/goal-checks.js`.

## A5. Downstream decisions that depend on this definition

Every item below becomes answerable once §A1 is approved, and every one is
currently unanswered. **None may be implemented before approval.** Ordered by
how early they bind.

### Immediate — the definition alone settles these

**A5.1 Which rate converts a journey price to a point target.** §A4. Under the
recommendation the answer is `entitlement`, because the target is a quantity of
travel value. Under "1 point = $1" the question does not arise, since the two
rates would be the same number by definition — which is precisely the collapse
the recommendation avoids. *Touches:* `goal()`, `travel-goal.js`, the fund page,
`goal-checks.js`.

**A5.2 Rounding and granularity.** If a point is indivisible, every conversion
must round, and the direction is a commercial choice with a customer-facing
consequence. The code currently rounds three ways: `pointsFor` floors (buying
$25.99 gets 25 points, the customer loses the remainder), `priceOf` rounds to
nearest, `goal` ceils. At least one of those is wrong and the definition decides
which. *Touches:* `pointsFor`, `priceOf`, `goal`, and every displayed figure.

**A5.3 Whether a cash equivalent may ever be displayed.** "You hold 4,800 TP
(worth $4,800)" is the sentence that turns an entitlement into a balance in the
customer's mind, whatever the terms say. The recommendation forbids it outside
an explicit buyback quotation. *Touches:* the Travel Goal panel, any future
wallet, all marketing copy.

**A5.4 What a wallet may total.** Related but separate: a wallet may show points
by state; whether it may show a single monetary "value of your holding" is a
different question and a liability-disclosure one. *Touches:* future wallet UI,
the admin console.

### Contractual — the definition constrains, counsel decides

**A5.5 Buyback valuation basis.** `buyback.rate: 0.90` is 90% of *what*: the
entitlement value, or the price originally paid? Under the recommendation these
diverge as soon as a programme offers a purchasing bonus, and the difference is
real money. Also unresolved: whether the 10% is a fee, a spread, or a
discretionary reduction. *Depends on:* §A1 plus decisions 5 and 6.

**A5.6 What a cancellation releases.** `cancellation[].release` is a fraction —
of the points reserved, or of their value at reservation, or of their value
today? These are the same number only while prices are static. *Depends on:*
§A1 plus decision 6.

**A5.7 Behaviour when a journey price rises.** If a point is a unit of travel
value and a journey's price rises, the customer's target rises and their
existing points are unaffected in *quantity* while being worth proportionally
less of that journey. Whether Afrinkong offers price protection — honouring the
price at goal-setting or at reservation — is a commercial promise this
definition permits but does not make. *Depends on:* §A1 plus decisions 7 and 8.

**A5.8 Expiry.** Expiring an entitlement and expiring a monetary balance are
different acts with different regulatory treatment. `expiryMonths: 0` currently
means never. *Depends on:* §A1 plus decision 3.

**A5.9 Transferability.** Transferring a right against a programme is not the
same as transferring value, and gift/family transfer is a likely product feature
whose legal shape follows from which of those it is. *Depends on:* §A1 plus
decision 4.

**A5.10 Eligible redemption scope.** Afrinkong journeys only is a closed-loop
product. The moment a point redeems against a third-party supplier it starts to
resemble a general instrument. *Depends on:* §A1 plus decision 9.

**A5.11 What is owed on programme discontinuation.** The answer differs sharply
between "you held a right we must honour" and "you held our money". *Depends
on:* §A1 plus decision 10.

### Structural — needed before a single payment is accepted

**A5.12 Regulatory characterisation.** Whether this is a closed-loop travel
credit, a stored-value instrument, or something requiring money-transmitter
registration. Decision 11, and the gate on everything. *Owner:* counsel.

**A5.13 Accounting treatment.** Deferred revenue against a performance
obligation, or a liability. The definition is the input to that determination,
and it changes the balance sheet. *Owner:* accountant.

**A5.14 Tax and point of supply.** When VAT/sales tax attaches — at point
purchase or at journey redemption — follows from what the customer bought.

**A5.15 Maximum exposure and purchase caps.** `minPurchase: 25` exists;
per-customer and aggregate ceilings do not. Outstanding entitlement is a
commitment to deliver travel, and it should be bounded before it is offered.

**A5.16 Currency.** `issueRate` is expressed per unit of `currency: 'USD'`. A
customer paying in another currency raises the question of whether the point is
defined against USD or against the programme, and who carries the FX movement
between purchase and redemption.

**A5.17 Refunds, chargebacks and reversal.** The ledger reverses by appending,
never by editing — but *what* is reversed when a payment is charged back after
the points have been partly redeemed is undecided.

## A6. What must not be built before approval

The current gates already refuse most of this; the list is here so that nobody
has to infer it.

- No database, no Supabase project, no Stripe integration, no payment flow.
- No purchase UI, no wallet UI, no redemption, transfer, reservation or buyback.
- `PROGRAMS['AFK-TP-2026.1'].status` stays `'draft'`. It is a one-word change
  and the most consequential one in this repository.
- The Travel Goal stays a planning calculation. It must continue to say that no
  points exist, nothing has been purchased, and no account has been created.

## A7. What approving this looks like

Approval means answering one question — *is §A1 the definition?* — and recording
it here with a date and who decided. It explicitly does **not** authorise
§A5.1–A5.17, any of which may still be answered either way afterwards.

| | |
|---|---|
| decision | §A1 adopted / amended / rejected |
| decided by | |
| date | |
| counsel reviewed | |
| notes | |

Once recorded, update decision 1 in `docs/economic-model-decisions.md` from
provisional to settled, and §A5.1 becomes the first piece of work that can
proceed — with a test, because it changes a number a customer reads.
