# Section F — what is paid, what is received, and where money may appear

**Status: architecture implemented, rates provisional, pricing questions
UNRESOLVED.** `AFK-TP-2026.1` remains `compliance: DRAFT`. Nothing here is on
sale.

Section F answers four questions:

1. money paid → points issued (`issueRate`)
2. points held → travel entitlement (`entitlementRate`)
3. is a cash equivalent ever displayed to the customer?
4. how does a pricing or bonus structure work **without** turning points into
   stored currency?

The fourth is the one that decides the other three, so it is where most of the
argument sits.

---

## F1 — two rates, two questions, and they are not interchangeable

```js
issueRate: 1        // points acquired per unit of money paid
entitlementRate: 1  // travel entitlement carried per point held
```

| direction | function | rate used |
|---|---|---|
| money → points | `pointsForPurchase()` | `issueRate` |
| points → money (price of a purchase) | `priceOfPoints()` | `issueRate` |
| points → travel | `entitlementOf()` | `entitlementRate` |
| journey → points required | `goalRequirement()` | `entitlementRate` |

They currently both read 1, which is exactly why they must stay separate
variables: **a model where the two are the same number is indistinguishable
from a model where there is only one, right up until the day somebody changes
it.** A5.1 was that day in miniature — `goalRequirement` used `issueRate`, and
a 10% purchase bonus silently made every journey 10% more expensive in points.

Section B proves the independence in both directions, by name:

- changing `issueRate` does not alter any entitlement calculation;
- changing `entitlementRate` does not alter historical issuance.

Points already issued keep the rates of the programme version they were issued
under, forever. That is B18 and it is the reason a programme is a versioned
record rather than two constants.

---

## F2 — the decision: `issueRate` is ONE number per programme

**A volume incentive may never move `issueRate`.** This is the rule that keeps
a Travel Point from becoming money, and the alternative looks harmless enough
that most loyalty schemes take it.

There are two ways to build "buy more, get more":

### (a) Move the rate — REJECTED

> "Buy 5,000 and get them at $0.91 each."

Now a point has a money price; that price differs between tranches and between
customers; and a customer holding 5,000 points can reasonably ask what theirs
cost and what somebody else's cost. **A thing with a spot price per tranche is
a currency, and a wallet of them is a balance**, whatever the terms call it.
Every downstream question — is this stored value, is this money transmission,
what is the redemption liability — gets harder to answer in the same direction.

### (b) Grant the extra — ADOPTED

> "Buy 5,000 at the programme's single rate, and receive 500 more."

The customer pays the same rate everyone pays. The extra points are a separate
issuance in their own lot: **not paid for at all**, expiring at 24 months,
excluded from repurchase (E7), forfeited on cancellation.

Under (b) the question "what is a Travel Point worth" has one answer for
purchased points — what the programme charges, one number — and **no answer at
all** for granted ones, because no money was paid for them. The incentive is
fully expressible and the point never acquires a variable price.

### It is enforced, not merely preferred

`mayActivate()` refuses a programme whose `issueRate` is not a single positive
finite number, and `mayTransition()` refuses `PILOT` on the same grounds. A
tiered rate cannot be reached by editing a term.

---

## F3 — so where does the incentive live?

```js
promotional: {
  offered: true,
  bonusRate: 0.05,   // flat: buy 500, receive 25
  tiers: null        // or [{ fromPoints, bonusRate }, …] — a ladder
}
```

`promotional.tiers` is the **only** place a volume incentive may live. A
worked ladder at 5% / 7% / 10%:

| purchase | pays | receives | granted | `issueRate` |
|---|---|---|---|---|
| 500 TP | $500 | 500 | +25 | **1** |
| 1,000 TP | $1,000 | 1,000 | +70 | **1** |
| 2,500 TP | $2,500 | 2,500 | +250 | **1** |

From the customer's side this behaves exactly as a tiered price would. The rate
never moves.

### A grant is not a discount

`purchaseOffer()` computes `priceMinor` from `issueRate` alone, and **the bonus
does not reduce it**. 1,000 TP costs $1,000 whether or not a promotion is
running; when one is, the customer receives 50 more. That is the entire
difference between a grant and a discount — a discount reprices the point, and
a repriced point is one that has a spot value.

### Two entries, never one

An offer implies `PURCHASE 1000` **plus** `PROMOTION 50`, never `PURCHASE 1050`.
B7.2 and C5 settled that; F3 is where the second entry is finally produced,
because until now `promotional.bonusRate` was a term nothing computed. The lots
stay distinguishable for the whole of their life, which is what makes E7's
"promotional points are not repurchasable" enforceable at all.

The customer still sees one number. `wallet()` returns `available: 1050`
alongside `purchased: 1000` and `promotional: 50`.

### Neither of these is a bonus

Two things that look like incentives are deliberately not:

- **`entitlementRate` above 1** would make a point buy more travel than it
  cost — a discount on travel, not a bonus on purchase, and it revalues every
  point already outstanding. B18 forbids revaluing points somebody has already
  bought, in either direction.
- **A discount on the journey** is a travel price change and belongs in
  `tourism/rates.json`. It reaches points through `goalRequirement()` and is
  shown to the customer as a changed requirement with the difference named —
  C8 — rather than as a changed point.

---

## F4 — is a cash equivalent ever displayed? No. Money appears at three moments.

The distinction that decides every case:

> **Money attaches to a TRANSACTION or to a JOURNEY. It never attaches to a
> HOLDING.**

`$1,000` beside a purchase button is a price. `$4,800` beside a journey is what
the journey costs. `3,650 TP ($3,650)` beside a wallet is a balance — and that
one sentence is what would make this a financial product.

`MONEY_MOMENTS` is a closed list in the module, not a convention in this
document, because a convention in a document is one somebody has not read:

| moment | what is shown | why it is legitimate |
|---|---|---|
| purchase | the price of **this transaction** | the customer is being charged and must see what |
| journey | what **the journey** costs | a travel price, quoted in money because travel is sold in money |
| repurchase | what is offered for **specific identified points** | an offer, not a statement of worth (E1) |

### What is checked

- `purchaseOffer()` carries exactly one money-bearing key, `priceMinor`. No
  `valueMinor`, no `worthMinor`, no per-point price — each of which is a cash
  equivalent by another name.
- On the Travel Goal, `$` appears in exactly one display field —
  `journeyTotal`. The reader's own holding reads *"750 TP"* and *"4,050 TP
  away"*, never a dollar figure.
- `wallet()` exposes no monetary field at all (B22).
- The fund pages are scanned for the `N TP ($N)` construction — a points figure
  and a money figure presented as the same quantity. None exists.

`entitlementOf()` and `priceOfPoints()` remain as arithmetic about a
*quantity*, and neither is a wallet field. A quantity of points has a price to
buy and an entitlement to spend; a customer's holding has neither.

---

## F5 — UNRESOLVED. Recorded, not decided in code.

| | question | owner |
|---|---|---|
| F-a | Should `issueRate` stay at 1, or should the programme charge a spread (e.g. 0.95 points per dollar) to fund the buyback and the float? | finance + counsel |
| F-b | Does the grant-not-discount construction actually survive the accounting question — is a granted point recognised at zero, at fair value, or as a reduction of the associated purchase's revenue? | accounting |
| F-c | Is a bonus ladder wanted at all, and if so at what thresholds and rates? `promotional.tiers` is `null` because nobody has decided. | commercial |
| F-d | Does a standing promotion — as opposed to a time-boxed one — teach customers that the nominal rate is fiction, and does that itself create a price expectation the programme then has to honour? | commercial |
| F-e | Must `issueRate` become a per-currency map when a second currency is accepted, and is a single rate per currency still "one rate" for the purposes of F2? (B-xviii, sharpened) | counsel + finance |
| F-f | Does showing a price at the purchase moment and an offer at the repurchase moment, both in money, amount to displaying a cash equivalent in substance even though neither is attached to a holding? | counsel |
| F-g | If a journey's price falls, a customer's points buy more travel than when purchased. Is that a benefit to disclose, or a revaluation to avoid? B18 only forbids the downward case. | counsel + commercial |

### Carried forward

| | question | change |
|---|---|---|
| B-i | one entry or two for a bonus | ✅ resolved by B16 — two; **implemented in F3** |
| B-xviii | must `issueRate` become a per-currency map | now F-e |
| B-iii | should `wallet()` return per-programme balances | still required work, unchanged |

---

## What this section did **not** do

- No programme was activated, and no rate was changed.
- No cash equivalent of a holding was created, displayed, or computed.
- No conclusion was drawn about stored value, revenue recognition or
  regulatory treatment.
- No Stripe, no payment provider, no charge.
