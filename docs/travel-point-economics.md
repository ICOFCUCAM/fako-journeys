# Section B — the Travel Point economic model

**Status — recorded 20 August 2026**

| | |
|---|---|
| B1–B5 | **settled** as product and economic decisions |
| B6 onward | not yet written |
| what these are not | **a legal opinion.** They do not determine the regulatory characterisation of the product. |
| before activation | counsel must confirm the characterisation. See §B1.3. |
| the programme | stays `draft`; `PRODUCT_STATE` stays `DRAFT_PROGRAM` |
| code changed by B1–B3 | **none.** B3 contradicts shipped copy; the discrepancy is recorded in §B3.1, not fixed. |

Section A defines *what a Travel Point is*. Section B defines *what happens
economically when somebody buys one*: what the customer is buying (B1), the rule
that governs what they hold (B2), how they acquire it (B3), what the planner
tells them (B4), and how the two rates work (B5).

B2 reaches back into Section A and closes one of its open questions — see
§B2.1.

---

## B1. What the customer is actually buying

**Settled.**

> A customer does not deposit money with Afrinkong. They purchase Travel Points
> issued under a specific Travel Point Programme.
>
> The money becomes company revenue or obligation according to the programme
> and the applicable accounting treatment. The customer's Travel Points are not
> a bank balance.
>
> **A point cannot be withdrawn as cash merely because the customer owns it.**

### The transaction

    customer
       │  pays
       ▼
    Wankong LLC                      ← the legal entity receives the payment
       │  issues
       ▼
    Travel Points                    ← under a named programme, on its terms
       │  held by
       ▼
    customer                         ← holds travel entitlement, not a balance

Three parties are absent from that diagram on purpose. There is no account
holding the customer's money. There is no custodian. There is no obligation to
return cash on demand.

### What B1 settles

**Ownership does not imply withdrawal.** This is the sentence that separates
this product from a deposit. A customer who holds 10,000 Travel Points holds a
right to Afrinkong travel; they do not hold $10,000 that Afrinkong is keeping
for them. Any buyback that exists is a **separate, bounded, programme-defined
offer** — not a property of ownership. (Section A1c: whether that offer is
"90% of what your points are worth" or "90% of what you paid for the ones you
haven't used" is still open, and the second needs no valuation of a point at
all.)

**The money is the company's on receipt.** Subject to accounting treatment,
which is a determination for the accountant and not settled here — see A5.13.
What is settled is that it is not held *for* the customer.

**The obligation is to provide travel.** Not to return money. That is what makes
this a travel product rather than a financial one, and it is the substance
behind every wording choice in Section A.

### B1.1 What this already means in the code

None of these is new; B1 ratifies them.

| commitment | where |
|---|---|
| no stored balance — every figure folded from an append-only ledger | `wallet()`, `tools/points/schema.sql:191` |
| no interest, no yield, no growth with time | absent by design, and its absence is asserted |
| buyback is a bounded programme offer, not a withdrawal | `buyback.minHoldDays`, `minPoints`, `maxPerYear`, `discretionary` |
| nothing may be issued under a non-active programme | `PRODUCT_STATE`, `fold()` throws |
| payment and issuance are two records with one reference | `payments` and `point_ledger` |

The last one matters more than it looks. Stripe is the payment rail and is not
the ledger; a reconciliation can ask "does every settled payment have exactly
one issuance, and vice versa" and get an answer. That is what makes the money
side auditable independently of the entitlement side — which is exactly the
separation B1 asserts.

### B1.2 What B1 does not settle

- **Accounting treatment.** Deferred revenue against a performance obligation,
  or a liability. A5.13. Owner: accountant.
- **When revenue is recognised.** At purchase, at reservation, or at travel.
  Follows from the above.
- **Tax point of supply.** A5.14.
- **What is owed if a programme is discontinued.** Decision 10.
- **Whether any of the money must be segregated.** Some characterisations
  require it. B1 asserts the money is not held *for* the customer; whether it
  must nonetheless be held *apart* is a regulatory question, not a product one.

### B1.3 The qualification, and why it has teeth

**B1 is a product and economic decision. It is not a legal opinion and does not
determine how a regulator will characterise this product.**

US regulators distinguish loyalty and reward arrangements from prepaid and
stored-value products. Certain features move an arrangement across that line
regardless of how its terms are drafted. Four of them are live here, and the
draft programme currently sits at the **higher-exposure end of every one**:

| feature | current setting | why it matters | where |
|---|---|---|---|
| **transferability** | `transferable: true` | A right that can be passed to a third party looks less like a loyalty benefit and more like an instrument. | programme |
| **cash redemption** | `buyback.offered: true` at `0.90` | The single feature most likely to change the characterisation. `discretionary: true` is the safer form and is what is encoded — a *contractual guarantee* would be materially different. | programme |
| **reloadability** | **not yet modelled** | Recurring monthly purchase plans are proposed in the brief. Repeated top-ups over time is a characteristic pattern of prepaid products. | absent from code and schema |
| **no expiry** | `expiryMonths: 0` | A claim that never lapses is a more durable obligation than a benefit that does. | programme |

That all four currently sit at the permissive end is a **drafting default, not a
decision**. Each is a single parameter. A first programme could plausibly be
non-transferable, non-reloadable, buyback-by-application-only and time-limited,
and be a much easier characterisation — at the cost of product features that
may matter commercially. That trade is a decision for the founder with counsel,
and it is not made here.

**Nothing in this repository may accept a customer payment until that
characterisation is confirmed.** The code enforces the gate rather than relying
on this paragraph: `PROGRAMS['AFK-TP-2026.1'].status` is `'draft'`, `fold()`
throws on any issuing entry under a non-active programme, and two test files
assert it.

---

## B2. The fundamental economic rule

**Settled.**

> **A Travel Point has no independent cash value.** Its value exists only as an
> entitlement toward eligible Afrinkong travel services under the Programme
> that issued it.

Therefore, and each of these is a commitment the product must keep everywhere:

- 1 TP ≠ $1, and 1 TP is not a dollar
- a point cannot be deposited
- a point cannot earn interest
- a point cannot generate yield
- a point cannot be used as general-purpose money
- a point cannot be withdrawn from Afrinkong as cash on demand

This is the rule that keeps the product centred on travel instead of becoming a
pseudo-bank account. B1 said the money is not held for the customer; B2 says the
thing they hold instead is not money either.

### B2.1 What B2 decides in Section A

B2 is not only a restatement. It reaches back and closes questions Section A had
left open.

**It eliminates A1b basis 1.** "Currency-denominated — 1 TP = $1 of travel
value" cannot survive "no independent cash value". That candidate is now closed
by decision rather than by argument, and A1b is down to four.

**It makes one of the two buyback mechanisms very hard to state.** A1c set out
the choice:

- *Redemption at value* — "90% of what your points are worth." This needs the
  points to be *worth* something in cash. B2 says they are not. A contractual
  formula could still be drafted — "we will pay $0.90 per point on application"
  is an offer rather than an assertion of value — but the distinction is fine
  enough that it would need careful drafting to avoid contradicting B2 in
  substance, and a customer would not hear the difference.
- *Refund of consideration* — "90% of what you actually paid for the points you
  have not used." This is **consistent with B2 by construction.** It never
  values a point; it refers to the recorded payment. `payments.amount_minor`
  already holds that figure, lot by lot.

B2 therefore points hard at refund of consideration without formally selecting
it. That selection remains A1c and remains open, but the ground has narrowed.

**It confirms the code has no growth surface.** "Cannot earn interest, cannot
generate yield" is already true by construction — there is no function anywhere
in `points-ledger.js` that makes a holding larger with the passage of time, and
its absence is deliberate. B2 makes that a rule rather than an accident.

## B3. How points are purchased

**Settled.**

> There is no mandatory monthly contribution. A customer may buy 100 TP today,
> 250 TP next month, 500 TP three months later, 75 TP when convenient.
>
> The Travel Goal reports progress and projects arrival:
>
> *"To reach your planned journey you need approximately 4,800 TP. At your
> current pace you are projected to reach that target in 14 months."*

This is the answer to the problem the whole product exists for. Somebody who
cannot hold themselves to a savings discipline can still use a structured
travel-purchase programme — without Afrinkong pretending to be their bank.

### B3.1 It inverts what the planner currently says

The shipped Travel Goal panel is prescriptive where B3 is projective. For a
$4,800 journey over 14 months it currently prints:

    Suggested monthly target        343 TP a month

B3 asks for the same arithmetic stated the other way round: not *"to hit this
deadline, contribute this much"* but *"at this pace, you arrive then"*. One
tells the customer what they must do; the other tells them where they are
heading. Only the second is honest about a programme with no mandatory
contribution.

Two places carry the prescriptive framing:

| what it says | where |
|---|---|
| `Suggested monthly target` | `scripts/fund.js:234` |
| "this becomes your **planned monthly contribution**" | `journey-fund.html:113` |

**Not changed.** Both are downstream of the Travel Goal's arithmetic, which is
blocked on A1b, and the standing instruction is that `goal()` is not to be
touched until the definition and A5.1 are decided. Recorded here so the
discrepancy between the settled model and the shipped copy is on the record
rather than discovered later.

### B3.2 A projection needs a pace, and there is no pace yet

"At your current pace" requires a purchase history to observe. Under
`PLANNING` and `DRAFT_PROGRAM` nobody has bought anything, so there is no pace
and none can be inferred.

For the planning-only site the honest form of B3 is therefore an **intended**
pace supplied by the customer, projecting a date:

    you need        4,800 TP
    you intend      350 TP a month
    projected       14 months

Same arithmetic, but the input moves from *deadline* to *intended
contribution*, and the output moves from *obligation* to *projection*. Once
real purchases exist the intended pace can be replaced by the observed one
without changing the shape of the calculation.

This is a design consequence of B3, not a decision, and it is not implemented.

---

## B4. The Travel Goal

**Settled.**

> The customer chooses: destination → itinerary → estimated journey → Travel
> Point requirement.
>
>     Kenya Safari
>     Target                4,800 TP
>     You currently have    1,750 TP
>     Remaining             3,050 TP
>
> The system may say: *"If you purchase approximately 220 TP per month, you
> could reach your target in approximately 14 months."*
>
> **This is a planning calculation, not a promise.**

B4 confirms the projective framing B3 asked for, and confirms §B3.2's reading of
how it has to work while nobody owns any points: the customer supplies an
intended pace and the system projects a date. "If you purchase approximately
220 TP per month" is an assumption offered to the customer, not an obligation
placed on them — and the conditional mood is doing real work.

"Not a promise" is already enforced rather than stated. The Travel Goal carries
`issued: false`, `sellable: false` and its product state on every render, and
`goal-checks.js` asserts that it never claims otherwise.

## B5. How the price of points works

**Settled — and this settles the rule the §A4 defect breaks.**

Two rates, and they must remain independent.

### A. Issue rate — what a purchase yields

How many points the customer receives for a payment.

    Programme 2026-A      $100 purchase → 100 TP
    a promotional programme   $100 purchase → 110 TP

**That additional 10 TP is a purchase incentive, not interest.** The distinction
matters: interest accrues on a holding over time, an incentive attaches to a
transaction at the moment it happens. The first is a financial-product feature
and the second is a discount. Nothing in the ledger makes a holding grow with
time, which is what keeps this on the right side of that line.

### B. Entitlement rate — what travel costs

How many points are required to obtain a given travel service.

    Kenya Safari
    estimated entitlement requirement    4,800 TP

### The rule

> **A purchase bonus must not make the journey more expensive.**

The two rates answer different questions and neither may stand in for the other.
`issueRate` prices the *acquisition* of points; the entitlement requirement
prices the *journey*. A programme that gives 110 TP per $100 has made points
cheaper to acquire — it has not changed what the Kenya Safari costs.

### B5.1 This confirms §A4 as a defect against settled policy

`goal()` computes its target as `journeyCost × issueRate`. Under B5 that is
wrong, and no longer merely latently wrong: a promotional programme at
`issueRate 1.1` raises a $4,800 goal to **5,280 TP**, which is precisely "a
purchase bonus made the journey more expensive."

Before B5 this was a question. After B5 it is a violation of a stated rule, and
`tools/goal-checks.js` now cites B5 as the authority rather than describing the
behaviour neutrally.

**Still not fixed, and the reason is narrow.** B5 settles *the rule*; A1b still
governs *how the entitlement requirement is derived from a journey* — computed
from the money price, or published per journey on the rate card. B4's phrasing
("estimated entitlement requirement: 4,800 TP", stated against the journey
rather than derived in front of the customer) leans toward the published form,
which is A1b basis 4. That is an observation, not a decision.

Once A1b lands the fix is one line and one test.

---

## B6 onward

Not yet written. The remaining economic model — pricing, packages, recurring
purchase, the wallet, reservation and redemption mechanics, price protection —
follows once B1 is recorded and Section A's open questions (A1b, A1c) have
answers.

## Sign-off

| | |
|---|---|
| B1 settled by | |
| date | |
| counsel engaged on §B1.3 | not yet |
| characterisation confirmed | **no — activation blocked until it is** |
