# Section A — the canonical commercial definition of a Travel Point

**Status — recorded 20 August 2026**

| | |
|---|---|
| this document | **approved as the working specification** |
| the definition itself (A1a and A1b) | **not commercially approved** |
| the programme | stays `draft`; `PRODUCT_STATE` stays `DRAFT_PROGRAM` |
| downstream decisions A5.1–A5.17 | none may be implemented |
| `goal()` (the §A4 defect) | **must not be changed** until the definition and
  the redemption question are formally decided |
| `issueRate` / `entitlement` | the distinction is preserved and now tested |

Approving the specification means this is the document the decisions are made
*in*. It is not approval of the answers it proposes.

This paper addresses one question and deliberately addresses nothing else:
*what is one Travel Point?* Review split it in two — the **frame** (A1a), which
is ready, and the **unit basis** (A1b), which is not. Everything in `docs/economic-model-decisions.md` inherits
the answer, which is why it is decision 1 there and why it is worth its own
document here.

Nothing in this paper has been built. The programme remains `draft`, the
product state remains `DRAFT_PROGRAM`, and `scripts/points-ledger.js` still
refuses to issue a point. Approving the definition does not release any of the
downstream work in §A5 — each of those is a separate decision that becomes
*answerable* once this one is fixed.

---

## A1. The definition, in two parts

Review of the first draft established that this is **two separable decisions**,
and that presenting them as one blocks the half that is ready. They are split
here so the frame can be settled while the unit basis stays open.

### A1a. The frame — proposed, not yet commercially approved

> **A Travel Point is a unit of travel purchasing entitlement issued by Wankong
> LLC under a named Travel Point Programme, redeemable toward eligible
> Afrinkong travel services on the terms of the programme under which it was
> issued.**
>
> A Travel Point is not money, is not redeemable for cash as of right, carries
> no interest, confers no ownership, and has no value outside the programme
> that issued it.

Four commitments, each load-bearing rather than a phrasing preference:

**Wankong LLC is the issuer; Afrinkong is the brand.** The obligation runs from
the legal entity. Afrinkong is the trade name the customer sees. Terms,
invoices, programme documents and disclosures must name the entity, and the
architecture should keep the two apart everywhere rather than treating them as
synonyms.

**Terms belong to the programme, not to the company.** A point issued under the
2026 Edition keeps 2026 terms permanently. A 2027 Edition may offer different
economics to new points without touching anybody's existing holding. This is
what makes the versioned `point_programs` table the right shape and what stops
a future pricing change from silently rewriting what somebody already bought.

**Redeemable toward eligible Afrinkong travel services.** The point stays
attached to the thing Afrinkong actually sells. It is not money held on a
customer's behalf.

**Indivisible.** One point is the smallest unit; there are no fractional points.

Note what A1a does *not* say: it does not say how much travel one point
entitles you to. That is A1b, and it is deliberately absent.

### A1b. The unit basis — OPEN, not proposed for approval

"One unit of travel purchasing entitlement" is architecturally sound and
commercially incomplete. *One unit of what?* Five candidate answers, with what
each commits Afrinkong to.

**Basis 1 is now closed.** Section B2 settled that a Travel Point has no
independent cash value, which a currency-denominated unit cannot satisfy. It is
kept in the table struck through, because a rejected option on the record is
worth more than a missing row. **Four remain live.**

| basis | 1 TP = | destination-flexible | regulatory weight | problem |
|---|---|---|---|---|
| ~~**1. currency-denominated**~~ **CLOSED by B2** | $1 of travel value | yes | **highest** | Denominates the entitlement in money. Every display becomes a cash figure and the product reads as stored value whatever the terms say. |
| **2. journey fraction** | 1/N of one named journey | **no** | lowest | Points bought for Kenya cannot move to Namibia without a conversion rule, which reintroduces the problem it avoided. Kills the flexibility in §8 of the brief. |
| **3. journey percentage** | 0.01% of any eligible journey | yes | low | A point is worth more against an expensive journey than a cheap one, so the rational customer always redeems against the most expensive — an arbitrage the programme pays for. |
| **4. rate-card unit** | one unit of the published Afrinkong rate card | yes | low–medium | Requires journeys to carry a published TP price, versioned like the money price. More machinery — but the machinery already exists. |
| **5. abstract, table-defined** | whatever the programme's conversion table says | yes | medium | Maximum flexibility, minimum customer comprehension. Hard to explain in a sentence, which is itself a consumer-protection problem. |

**Where the existing architecture points, without deciding anything.**
`tourism/rates.json` already prices every journey — USD, per vehicle per day, at
three tier rates — and the fund page already carries a rate-card version hash
(`"v":"1d60cf455f9a"`). Basis 4 would give that rate card a second column
denominated in points and version it the same way, which means the journey price
and the point price move together under one version stamp rather than drifting
apart. That is the cheapest of the five to build correctly and the only one that
inherits price-versioning for free. It is a recommendation about *fit*, not a
commercial judgement, and it is not proposed for approval here.

### A1c. The buyback tension, which A1b decides

The 10% buyback and the non-monetary definition pull against each other, and
this was not visible until the two were written down together.

A cash buyback must convert points into money. If a point is *defined*
non-monetarily, that conversion has to invent a monetary value for it — and
inventing one is, in substance, the monetary characterisation A1a exists to
avoid. **The stronger the non-monetary definition, the more artificial any
buyback valuation becomes.**

There is a way out, and it is worth naming because it changes what needs
deciding. Two structurally different mechanisms both answer "the customer wants
out":

**Redemption at value** — "90% of what your points are worth." Requires a
point-to-cash valuation to exist. Straightforward under basis 1; increasingly
strained under 3, 4 and 5; close to meaningless under 2.

**Refund of consideration** — "90% of what you actually paid for the points you
have not used." Requires no valuation of a point whatsoever. It refers to the
recorded payment, not to the entitlement. The schema already supports it:
`payments.amount_minor` records what was taken and the ledger references the
payment, so unredeemed points can be traced to the money that bought them,
lot by lot.

The second is available under **every** basis in A1b, keeps the unit
non-monetary, and reads to a customer as a refund rather than a cash-out. It
also changes the shape of decision 5 — whether buyback is contractual or
discretionary — because refunding consideration is a much easier promise to
make than guaranteeing a valuation.

Not proposed for approval. Recorded because A1b cannot be decided sensibly
without knowing which of these two buyback mechanisms is intended, and the
question had not been asked in that form.

## A2. Why the frame refuses to denominate in money

A1b is open, but one thing is settled by A1a and worth stating on its own,
because it is the constraint every candidate basis has to satisfy.

A definition of the form *"a point is a dollar"* — or a dollar held on account,
or a dollar of travel — makes the customer's holding a **monetary claim**. Three
consequences follow immediately, and none of them is a matter of wording:

- **It reads as a balance.** Whatever the terms say, "you have 4,800 points
  worth $4,800" is a bank statement in the customer's mind. The product spends
  the rest of its life explaining that it is not one.
- **It fixes the economics forever.** A dollar cannot be worth something else
  next year, so a programme cannot offer different terms later without either
  breaking the identity or repricing what people already hold.
- **In several jurisdictions it is the test.** A monetary claim redeemable on
  demand is close to the statutory description of a stored-value instrument.
  Decision 11 turns on this and it is counsel's call, not a drafting choice.

So the frame commits to a non-monetary unit, and A1b picks which non-monetary
unit. Basis 1 is listed there for completeness and because rejecting it should
be a decision on the record rather than an omission — not because it is a live
candidate under this frame.

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

> **A note on numbering.** Review referred to the next piece of work as "A5.1 —
> define exactly what 1 Travel Point represents when redeemed". That question is
> **A1b** in this document; A5.1 below is the narrower coding consequence of it
> (which of the two rates `goal()` should use). They are one chain — A1b decides
> the meaning, A5.1 applies it — and both are blocked. The names are aligned
> here so the two are not mistaken for each other in a later discussion.

Every item below becomes answerable once §A1 is approved, and every one is
currently unanswered. **None may be implemented before approval.** Ordered by
how early they bind.

### Immediate — the definition alone settles these

**A5.1 Which rate converts a journey price to a point target.** §A4.
**Section B5 has since settled the rule** — a purchase bonus must not make the
journey more expensive — so this is no longer a question of principle, only of
derivation. **Blocked on A1b, not on A1a.** The frame does not answer it: `entitlement` is the right
rate under bases 3, 4 and 5, while under basis 1 the question dissolves because
the two rates are the same number by definition — which is precisely the
collapse the frame refuses. *Touches:* `goal()`, `travel-goal.js`, the fund page,
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

**A5.5 Buyback valuation basis.** `buyback.rate: 0.90` is 90% of *what*? See
A1c: this is not one question but two — *which mechanism* (redemption at value
or refund of consideration), and only then *on what basis*. The first must be
answered before A1b can be, because it constrains which unit bases are
workable. Under the recommendation these
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

Two decisions, recorded separately, because they are ready at different times.

### A7a. The frame — ready now

Answers one question: *is A1a the frame?* It authorises no downstream work. It
does not decide what one unit is worth, and it does not release A5.1–A5.17.

| | |
|---|---|
| decision | A1a adopted / amended / rejected |
| decided by | |
| date | |
| counsel reviewed | |
| notes | |

### A7b. The unit basis — not ready

Blocked on two prior questions, in this order:

1. **Which buyback mechanism is intended** — redemption at value, or refund of
   consideration (A1c). This constrains which bases in A1b are workable.
2. **Which basis** — one of the five in A1b, or another.

| | |
|---|---|
| buyback mechanism | redemption at value / refund of consideration / undecided |
| basis chosen | |
| decided by | |
| date | |
| counsel reviewed | |

Once A7a is recorded, update decision 1 in
`docs/economic-model-decisions.md` from provisional to settled **as to the
frame only**, and leave the unit basis open there. A5.1 — the defect in §A4 —
stays blocked until A7b, because which rate converts a journey price to a point
target is a direct consequence of what one unit is.
