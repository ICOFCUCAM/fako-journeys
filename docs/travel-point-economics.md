# Section B — the Travel Point economic model

**Status — recorded 20 August 2026**

| | |
|---|---|
| **B1–B25** | **DESIGN APPROVED — PENDING LEGAL/REGULATORY REVIEW BEFORE ACTIVATION** |
| conformance | 21 of B24's 28 rules enforced; 7 recorded and pinned. See B24. |
| open questions | seventeen |
| all four exposure features | now answered — **two easier, two harder**. See B17.2 |
| awaiting your word | **B14** — `transferable: false`, one word, blocked on nothing |
| larger pending work | **B16** — a promotional lot type the ledger cannot yet express |
| resolves | **Section A1c** — repurchase is refund of consideration |
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

## B6. Existing points keep their programme terms

**Settled.**

> A customer buys 1,000 TP under Programme 2026-A. Six months later Afrinkong
> launches Programme 2027-B with different economics. **The 2026-A points do not
> silently become 2027-B points.** Their ledger rows record `2026-A`, and the
> original terms remain attached to them.

### B6.1 Where this is enforced, and where it is not

Enforced:

| | |
|---|---|
| every ledger row records its programme | `point_ledger.program_id`, `not null`, foreign key |
| a programme's economics cannot be edited after creation | trigger at `tools/points/schema.sql:87` refuses any `UPDATE` to `issue_rate`, `entitlement`, `buyback` or `cancellation` |
| history cannot be rewritten | `point_ledger` is append-only; corrections are reversing entries |

**Not enforced — and this is a real gap.** The JavaScript `wallet()` folds every
entry into one aggregate and discards the programme. Measured:

    1,000 TP under AFK-TP-2026.1  +  500 TP under AFK-TP-2027.2
      -> { available: 1500 }        with no per-programme breakdown

So the *history* is programme-aware and recoverable, while the *balance* is not.
Nothing is lost, but B6 cannot be answered from a wallet — you cannot ask "how
many of my points are 2026-A points" and get an answer.

This is not a decision to make; it is work B6 requires and which has not been
done. It is not done here, because it is economic implementation and the
standing instruction is to hold. Recorded so it is not mistaken for finished.

## B7. No interest

**Settled.**

> Absolutely no interest, APY, APR, investment return, appreciation, yield,
> dividend, or "growth". Someone who buys 1,000 TP does not wake six months
> later with 1,050 TP because time passed.
>
> A balance changes only through legitimate ledger events — purchase, bonus,
> reservation, redemption, cancellation, approved adjustment. **Not time.**

### B7.1 Now enforced rather than merely absent

This was true by construction — no code did it — and "true because nobody has
written it yet" stops being true quietly. Three checks in `points-checks.js`
make it a rule:

- **no growth vocabulary in live code.** The source of the ledger, the goal and
  the schema is read, comment lines excluded. A field named `interestRate` would
  have been caught by nothing else in the suite, and by the time it reached a
  balance it would be a financial product.
- **no clock in the ledger.** No `Date`, no `now()`, no randomness. A ledger
  that cannot read the time cannot pay for its passage — a stronger guarantee
  than any rule about what may be done with a date once you have one.
- **a closed set of ten kinds.** `PURCHASE`, `TRANSFER_IN`, `ADJUST_UP`,
  `RESERVE`, `RELEASE`, `REDEEM`, `TRANSFER_OUT`, `BUYBACK`, `EXPIRE`,
  `ADJUST_DOWN`. An eleventh fails the check, so adding one has to be said out
  loud.

### B7.2 Where "bonus" lives, which is not obvious

B7 lists *bonus* among the events that change a balance, and there is no `BONUS`
kind. Under B5 an incentive is expressed in the **quantity of the PURCHASE
entry** — $100 at `issueRate 1.1` is one entry of 110 — rather than as a
separate event.

That is a defensible choice and it has a consequence worth naming: reconciliation
asks "does every settled payment have exactly one issuance", and it still does,
but the *ratio* is no longer 1:1 and an auditor reading a $100 payment against a
110-point issuance needs the programme to explain the difference.

The alternative — `PURCHASE 100` plus a separate `BONUS 10` — makes the
incentive visible in the history at the cost of two entries per payment.
**Open.** Added to the register below.

## B8. Applying points to travel

**Settled.**

> When the customer is ready: Travel Goal → itinerary → quote → points applied.
>
>     journey price under the applicable programme    4,800 TP
>     customer holds                                  5,200 TP
>     applied                                         4,800 TP
>     remaining                                         400 TP
>
> **The remaining 400 TP continues under its original programme terms.**

### B8.1 The question B8 raises and does not answer

The closing sentence is only meaningful if the remaining points *have* an
identifiable programme — which is B6.1's gap. It also raises a question neither
section settles:

**Which points are consumed first?** A customer holding 1,000 TP under 2026-A
and 500 TP under 2027-B who redeems 1,200 TP has spent some of each, and which
ones determines what their remaining 300 TP is worth and what terms it carries.
Oldest first, most-favourable-to-the-customer first, cheapest first, or
proportional are all defensible and they give different answers.

This is **not one of the seventeen** in Section A and is added to the register
now. It cannot be answered before A1b, since "most favourable" has no meaning
until a unit basis exists.

---

## New open questions raised by B6–B8

| # | question | raised by | blocked on |
|---|---|---|---|
| B-i | Should a purchase incentive be one entry or two — `PURCHASE 110`, or `PURCHASE 100` plus `BONUS 10`? | B7.2 | reconciliation design; independent of A1b |
| B-ii | On redemption, which lot is consumed first when a customer holds points under more than one programme? | B8.1 | A1b |
| B-iii | Should `wallet()` return per-programme balances rather than one aggregate? | B6.1 | nothing — it is required work, not a decision |

---

## B9. When the journey costs more than the customer holds

**Settled.**

>     journey    5,400 TP
>     customer   4,800 TP
>
> Two routes:
>
> **A — buy additional points.** Purchase the remaining requirement.
>
> **B — settle an allowed balance through the normal booking process.**
>
> Cash is **not** automatically interchangeable with points on every screen.
> The product stays *Travel Points first* rather than becoming a dollar wallet
> with a different name.

The last clause is the load-bearing one, and it is a design constraint rather
than a preference. A product where every screen offers "or just pay the
difference in cash" has taught the customer that points are a denomination of
money, which is precisely what B2 denies. Route B exists because a real customer
will occasionally be 600 TP short a fortnight before departure; it is a booking
accommodation, not a payment method.

### B9.1 How a mixed settlement can work without valuing a point

This is the part that needs care, because the obvious implementation breaks B2.

**The obvious one, which fails.** "You are 600 TP short; 600 TP costs $600, pay
that." This assigns a cash value to a point, creating exactly the independent
monetary value B2 says does not exist. Do this and the product has a published
exchange rate.

**One that does not.** A journey carries both a money price and a point
requirement. The customer's points cover a *proportion of the journey*, and the
balance is the remaining proportion, priced in money off the journey's own money
price:

    journey        5,400 TP   /   $5,400
    points applied 4,800 TP   =   88.9% of the journey
    balance due       11.1%   =   $600

Arithmetically identical here, because the draft programme's rates are 1. But it
values a *fraction of a journey*, never a point — and the two stop being the
same number the moment a promotional programme exists. Only the second survives
B2 intact.

Recorded as an approach, not a decision.

### B9.2 What B9 leaves open

| | |
|---|---|
| how the shortfall is split | proportional-of-journey (B9.1) or a point-to-cash rate. The second conflicts with B2. |
| whether points must be exhausted first | "Travel Points first" suggests a floor — apply everything available before any cash — but does not state one |
| which journeys allow route B at all | "an allowed balance" implies not all of them |
| whether a partial booking can be held while the customer buys the shortfall | route A takes time; a reservation may need to survive it |

These are added to the register below.

## B10. Reservations

**Settled, and already implemented.**

> Points committed to a booking become **HELD / RESERVED** and are no longer
> available for another journey.
>
>     balance      5,000 TP
>     reservation  4,800 TP
>     available      200 TP
>
> This prevents double spending.

This one needed no design work — it was built and is tested. Verified against
the ledger:

| B10 requires | behaviour | check |
|---|---|---|
| reserving moves points out of available | 5,000 → available 200, reserved 4,800 | `reserving moves points between pools without destroying any` |
| reserved points are attributable to a booking | `reservations: {"JRN-1044": 4800}` | folded per `journeyRef` |
| a second journey cannot claim them | refused: *not enough available points, available 200, wanted 4,800* | `can() refuses before the entry is appended, with a reason` |
| the ledger cannot be overdrawn even by force | `fold` throws | `a wallet cannot be overdrawn` |

Note the shape: `can()` answers *before* an entry is appended, and `fold` refuses
*even if* one is appended anyway. The check and the guarantee are separate, so a
caller that forgets to ask still cannot overdraw a wallet.

Two of my own test errors are worth recording, because both looked like defects
and neither was: `can()` takes the ledger entries rather than a folded wallet,
and the per-journey map is keyed on `journeyRef`, not `journeyId`. Passing a
wallet returned "unknown entry kind" and passing `journeyId` returned an empty
reservations map. The code was right both times.

---

## New open questions raised by B9

| # | question | raised by | blocked on |
|---|---|---|---|
| B-iv | Is a shortfall settled as a proportion of the journey, or at a point-to-cash rate? The latter conflicts with B2. | B9.1 | A1b |
| B-v | Must a customer apply all available points before any cash balance? | B9 | nothing — a product decision |
| B-vi | Which journeys permit a cash balance at all? | B9 | nothing — a commercial decision |
| B-vii | Can a reservation be held while the customer buys the shortfall, and for how long? | B9.2 | nothing — a product decision |

---

## B11. Cancellation

**Settled.**

| window | treatment |
|---|---|
| **31+ days** | **Full point release.** Reserved points return to available, subject to the programme's stated cancellation terms. |
| **8–30 days** | **Controlled release.** Points may return, but cancellation charges or non-refundable supplier costs can apply according to the booking terms. |
| **0–7 days** | **Final commitment window.** Points become non-refundable and non-buyback-eligible **to the extent stated in the booking agreement**. |

By the final week Afrinkong may already have committed money to hotels, guides,
transport, permits, conservation fees, operators and flights. The customer's
points cannot become an unlimited cancellation liability for Afrinkong.

### B11.1 The bands match; two numbers inside them do not

The day boundaries encoded in the programme are exactly B11's — 31, 8, 0. What
sits inside two of them is not what B11 says.

| window | B11 | encoded | assessment |
|---|---|---|---|
| 31+ | full release | `release: 1.00` | ✅ agrees |
| 8–30 | charges *"can apply according to the booking terms"* | `release: 0.50` — a flat half, always | **a policy the code asserts and B11 does not** |
| 0–7 | non-refundable *"to the extent stated in the booking agreement"* | `release: 0.00` — total forfeiture, always | **stricter than B11** |

B11 ties the middle band to *actual* cancellation charges and supplier costs.
The code applies a flat 50% regardless of what was actually committed — which
will be too harsh on a journey with no supplier exposure yet and too generous on
one already paid for. Likewise the final window: "to the extent stated" is not
"all of it".

Both numbers were placeholders, and they read as policy. Whether release should
be a published ladder (simple, predictable, occasionally unfair in both
directions) or driven by real incurred cost (accurate, unpredictable, needs
supplier data at cancellation time) is a decision B11 leaves open, and it is
registered below.

Not changed — `cancellation` is programme economics, the schema's immutability
trigger treats it as such, and the instruction is to hold.

## B12. Repurchase, not withdrawal

**Settled, and it resolves Section A1c.**

> Afrinkong **may offer** an eligible Travel Point Repurchase at **90% of the
> applicable purchase consideration**, subject to the Programme's repurchase
> rules.
>
>     customer paid          $1,000
>     potential repurchase     $900
>     Afrinkong retains        $100
>
> This is a repurchase programme, **not a customer right to withdraw money
> whenever they want**. Buyback stays discretionary and programme-controlled
> rather than a guaranteed cash redemption.

Cash redemption is the feature most likely to change the regulatory character of
a prepaid arrangement, and FinCEN treats prepaid access as its own category,
assessed on a programme's features and controls rather than on its label. Keeping
repurchase discretionary is a control; making it a guaranteed right removes one.

### B12.1 A1c is now answered

Section A1c set out two mechanisms and said one had to be chosen before the unit
basis could be. B12 chooses:

> **Refund of consideration** — 90% of what the customer actually paid for the
> points they have not used. Not "90% of what the points are worth".

This is the mechanism A1c identified as consistent with B2 by construction: it
never assigns a cash value to a Travel Point. It refers to the recorded payment,
which `payments.amount_minor` already holds. **A1c is closed, and A1b is
unblocked to that extent.**

### B12.2 The code implements the other one, and it is exploitable

`buybackQuote()` computes `entitlementOf(points) × 0.90` — 90% of the *travel
value*. That is redemption at value: the mechanism B12 has just rejected.

Invisible while `issueRate` and `entitlement` are both 1. Measured with a
promotional programme, on a $1,000 purchase:

| bonus | points issued | B12 pays | code pays | customer |
|---:|---:|---:|---:|---|
| 0% | 1,000 | $900 | $900 | −$100 |
| 10% | 1,100 | $900 | $990 | −$10 |
| **15%** | 1,150 | $900 | **$1,035** | **+$35** |
| **25%** | 1,250 | $900 | **$1,125** | **+$125** |

The break-even is `issueRate > 1 / 0.90`, so **any promotional programme
offering more than an 11.1% bonus turns repurchase into a money-out machine**:
buy points at a bonus, wait out `minHoldDays`, claim more than you paid, repeat
to the annual cap.

Under B12's consideration basis this is impossible by construction — 90% of what
you paid can never exceed what you paid. That is the strongest argument for the
choice B12 made, and it is measured rather than asserted.

`points-checks.js` now pins this the way the §A4 defect is pinned: the current
behaviour is asserted, the arbitrage is demonstrated, and the check names B12 as
the authority. **Not fixed** — buyback is programme economics and the standing
instruction is to hold — but it cannot now ship silently.

### B12.3 What still needs deciding

The three guards already encoded — `minHoldDays: 90`, `minPoints: 100`,
`maxPerYear: 5000` — are controls in the FinCEN sense, and their values are
placeholders. B12 settles the *basis* and the *discretion*; it does not settle
the thresholds, whether an offer may be refused case by case or only by rule,
or what happens to a repurchase request from a customer with an active
reservation. Registered below.

---

## New open questions raised by B11–B12

| # | question | raised by | blocked on |
|---|---|---|---|
| B-viii | Is the 8–30 day release a published ladder or driven by actual incurred supplier cost? | B11.1 | nothing — a product decision |
| B-ix | What does "to the extent stated in the booking agreement" mean inside 7 days — is any release ever possible? | B11.1 | booking terms |
| B-x | Are `minHoldDays`, `minPoints` and `maxPerYear` the right controls, and at what values? | B12.3 | counsel, on the prepaid-access analysis |
| B-xi | May a repurchase offer be refused case by case, or only by published rule? | B12.3 | counsel |
| B-xii | Can a customer with an active reservation request repurchase of their unreserved points? | B12.3 | nothing — a product decision |

---

## B13. Repurchase eligibility

**Settled.**

**Eligible** — points unused; not reserved; not attached to an active booking;
minimum holding period passed; customer within annual repurchase limits;
programme accepting repurchases; customer passes required identity and payment
checks.

**Not eligible** — points already redeemed; points currently reserved; points
inside the final 7-day travel window; promotional points where the programme
excludes repurchase; points already subject to a cancellation or settlement
process; fraudulent or disputed transactions.

### B13.1 Six of thirteen conditions are enforced; seven are not

`buybackQuote(programId, entries, points, heldDays, boughtBackThisYear)` — its
whole surface. Anything not in that signature it cannot know.

| condition | enforced | how, or why not |
|---|---|---|
| points unused | ✅ | only `available` points qualify |
| not reserved | ✅ | `reserved` is a separate pool and is excluded from `available` |
| already redeemed | ✅ | redeemed points have left `available` |
| minimum holding period | ✅ | `heldDays < minHoldDays` |
| within annual limit | ✅ | `boughtBackThisYear + points > maxPerYear` |
| programme accepting | ✅ | `buyback.offered` |
| **not attached to an active booking** | ⚠️ partial | reserved points are excluded, but a booking may hold points in states the wallet does not distinguish |
| **inside the final 7-day window** | ❌ | takes no booking or departure date. The cancellation ladder carries `buybackEligible` flags; `buybackQuote` never consults them. |
| **promotional points excluded from repurchase** | ❌ | no per-lot promotional flag exists. B5 puts the incentive in the PURCHASE quantity (B7.2), so a bonus lot is indistinguishable afterwards — **this is the second consequence of that choice**, and it is a real cost of it. |
| **already in cancellation or settlement** | ❌ | not modelled |
| **fraudulent or disputed** | ❌ | `payments.status` has `charged_back`, but nothing joins it to eligibility |
| **identity checks** | ❌ | not modelled |
| **payment checks** | ❌ | not modelled |

Two of these are worth pulling out.

**The 7-day window is checked in one place and ignored in another.** The
cancellation ladder computes `buybackEligible: false` inside 7 days, and the
repurchase quote cannot see it. Two functions hold half the rule each, which is
exactly how a customer inside the final window gets a quote they should never
have been offered.

**Promotional exclusion is currently impossible, and B7.2 is why.** Putting the
incentive in the quantity of the PURCHASE entry means a bonus point is not
distinguishable from a paid point once written. B13 requires exactly that
distinction. This is the strongest argument yet for open question B-i — the
`PURCHASE 100` + `BONUS 10` shape — and the two questions should be decided
together.

## B14. No customer-to-customer marketplace in V1

**Settled firmly.**

> Customers may **not** sell or transfer Travel Points to one another in V1.
>
>     ❌  James → sells 500 TP → Sarah
>     ✅  Customer → Afrinkong, which may repurchase if eligible
>
> Person-to-person transfer is one of the features FinCEN identifies as relevant
> to prepaid-access treatment. A marketplace can be revisited later.

### B14.1 The encoded programme currently says the opposite

| | |
|---|---|
| B14 | no customer-to-customer transfer |
| `PROGRAMS['AFK-TP-2026.1'].transferable` | **`true`** |
| ledger kinds | `TRANSFER_IN`, `TRANSFER_OUT` both exist |

This is the first settled decision in Section B that requires a **code change**
rather than future work, and it is a one-word change: `transferable: false`.

It is blocked on nothing. A1b does not touch it, counsel does not need to rule
on it — B14 *is* the decision, and it makes the programme easier to characterise
rather than harder. It sits unmade only because programme economics have been
under a standing hold, and flipping a term of the economic model on my own
initiative is precisely what that hold exists to prevent.

**Ready to make on your word.** The ledger kinds can stay: `TRANSFER_IN` and
`TRANSFER_OUT` are how an administrative correction or a future programme would
express a movement, and a programme that forbids transfer simply never emits
them. Removing the kinds would be deleting capability to enforce a policy, which
is the wrong layer.

`points-checks.js` records the contradiction so it cannot be forgotten.

### B14.2 It closes one of the four exposure features

B1.3 listed four features sitting at the higher-exposure end by drafting default.
B14 decides one of them:

| feature | was | after B14 |
|---|---|---|
| transferability | `true` | **`false`** — decided |
| cash redemption | offered, discretionary | discretionary confirmed by B12; basis corrected to consideration |
| reloadability | not modelled | still open |
| no expiry | `expiryMonths: 0` | still open |

Two of four have answers at this point in the section, and both moved toward the
easier characterisation. **That reading did not survive B17** — B3 had already
settled reloadability as *yes* and B17 settles expiry as *never*, both of which
move the other way. The corrected tally is in B17.2.

---

## New open questions raised by B13

| # | question | raised by | blocked on |
|---|---|---|---|
| B-xiii | Should `buybackQuote` take the booking and departure date so the 7-day window can be enforced where the quote is produced? | B13.1 | nothing — required work |
| B-xiv | How are promotional points marked so a programme can exclude them from repurchase? | B13.1 | decide with B-i |
| B-xv | What identity and payment checks are required before a repurchase settles? | B13 | counsel |
| B-xvi | How do disputed or charged-back payments propagate to repurchase eligibility? | B13.1 | reconciliation design |

---

## B15. No secondary market

**Settled.**

V1 supports:

    purchase  →  hold  →  redeem
    purchase  →  hold  →  eligible Afrinkong repurchase

V1 does not support:

    purchase  →  speculate  →  trade  →  sell to another customer

> That keeps Afrinkong a travel company, not an exchange.

B15 is B14 stated as a shape rather than a prohibition, and the distinction is
useful: B14 forbids an act, B15 describes the only flows that exist. A design
that cannot express a trade is stronger than one that can and declines to.

The ledger already matches. `TRANSFER_OUT` has no counterparty field, no
recipient, no price — a movement out, with nothing to make it a sale. There is
no order book, no matching, no quotation between customers, and nothing to add
one to. **Nothing to remove; the shape is already the V1 shape.**

## B16. Promotional points are a different thing

**Settled, and it resolves two open questions.**

> Distinguish **purchased points** — the customer paid for them — from
> **promotional points** — Afrinkong issued them as a bonus.
>
>     buy       1,000 TP
>     receive     100 TP promotional
>
> **The ledger must know the difference.** Promotional points may carry
> different expiry, redemption, cancellation, buyback and transfer rules.
>
> A promotional point is never advertised as cash-equivalent value.

### B16.1 This supersedes how I read B5

B5's example — *"$100 purchase → 110 TP"* — I read as **one entry of 110**, and
recorded the consequence in B7.2: the incentive lives in the quantity, so a
bonus point becomes indistinguishable from a paid point the moment it is
written.

B16 says that is wrong. Buy 1,000, *receive* 100 promotional: two things, and
the ledger must be able to tell them apart. **The correct shape is two entries**
(or one entry carrying a lot type), not one entry of 1,100.

That resolves two registered questions:

| # | was | now |
|---|---|---|
| **B-i** | one entry of 110, or `PURCHASE 100` + `BONUS 10`? | **two.** Settled by B16. |
| **B-xiv** | how are promotional points marked so a programme can exclude them from repurchase? | **as their own issuance**, which makes B13's promotional exclusion expressible for the first time |

It also removes the cost I flagged in B13.1. Promotional exclusion from
repurchase was *impossible* under the one-entry reading; under B16 it is simply
a property of the lot.

### B16.2 The ledger cannot express this yet

| | |
|---|---|
| issuing kinds today | `PURCHASE`, `TRANSFER_IN`, `ADJUST_UP` |
| any promotional kind | **none** |
| any lot type on an entry | **none** — `fold` reads kind, quantity, status, idempotency key, programme, journey ref |
| in the schema | no lot or promotional concept |

`ADJUST_UP` is not it: that is an administrative correction, flagged `admin:
true`, and using it for marketing grants would make every promotional issuance
look like a manual intervention in an audit.

So B16 needs an eleventh kind — `PROMOTION` — or a `lotType` field, and a
programme block describing the rules that apply to promotional lots. Distinct
expiry, redemption, cancellation, buyback and transfer rules per B16 means the
programme grows a parallel set of terms, not a single flag.

**Not built.** This is larger than B14's one word: a ledger kind, a programme
sub-structure, and everything downstream that reads a balance. Blocked on
nothing, but genuinely economic implementation.

### B16.3 The closed-set check is about to fire, exactly as designed

B7.1 added a check asserting that the ways a balance can change are **a closed
set of ten**, with the stated reason: *"An eleventh fails the check, so adding
one has to be said out loud."*

B16 is the first eleventh, and this is it being said out loud. When `PROMOTION`
is added the check will fail until somebody updates it deliberately, with B16 as
the citation. That is the guard working rather than an obstacle to route around
— and it is worth noting that it took four sections to catch something, which is
about the right rate for a guard of that kind.

### B16.4 One thing B16 does not settle

Whether promotional points are consumed **before or after** purchased points on
redemption. It matters: burn promotional first and the customer keeps the points
with repurchase rights; burn purchased first and the customer is left holding
grants that may expire and cannot be repurchased.

This is open question **B-ii** — lot consumption order — which B8.1 raised for
multiple programmes and which B16 now sharpens. The two are the same question
and should be answered together.

---

## Open questions after B15–B16

Two resolved, one sharpened, one added.

| # | question | status |
|---|---|---|
| B-i | one entry or two for a bonus | ✅ **resolved by B16** — two |
| B-xiv | how promotional points are marked | ✅ **resolved by B16** — their own issuance |
| B-ii | which lot is consumed first | sharpened: now spans programme *and* purchased-vs-promotional |
| B-xvii | do promotional points carry a parallel set of programme terms, or overrides on the main set? | new, raised by B16.2 |

---

## B17. Expiry

**Settled.**

> **Purchased points do not expire because time passed.** They remain valid
> under their programme until redeemed, repurchased, cancelled under programme
> terms, or the programme is discontinued under properly disclosed rules.
>
> **Promotional points may carry an expiry date.**
>
> *The points you paid for don't disappear simply because you didn't travel
> this year.*

### B17.1 One scalar where two rules are needed

`expiryMonths: 0` is programme-wide. B17 needs a *differential* rule — never for
purchased, optionally dated for promotional — and a single number cannot carry
it.

This is the third consequence of B16 in as many sections: expiry joins
redemption, cancellation, buyback and transfer on the list of terms that differ
by lot type. The programme does not need a promotional flag; it needs a
promotional **terms block**, and B17 is more evidence for open question B-xvii.

The `EXPIRE` kind already exists and is correct as it stands — what is missing is
anything that would decide *which* points it applies to.

### B17.2 Expiry was the last of the four exposure features, and the tally is not what I said

B1.3 listed four features that move a prepaid-access analysis, all sitting at
the higher-exposure end by drafting default. All four now have answers:

| feature | decided by | outcome | direction |
|---|---|---|---|
| transferability | **B14** | `false` — no customer-to-customer transfer | ↓ easier |
| cash redemption | **B12** | discretionary, on purchase consideration | ↓ easier |
| **reloadability** | **B3** | **yes** — buy any amount, any time, no fixed schedule | ↑ harder |
| **expiry** | **B17** | purchased points never lapse | ↑ harder |

After B14 I wrote that two of four had been answered and *"both moved toward the
easier characterisation"*. Reading B3 and B17 properly, that is wrong twice
over: all four are answered, and **two go each way**.

Flexible accumulation is reloadability, which is a characteristic prepaid
pattern. Points that never lapse are a more durable obligation than benefits
that do. Both are deliberate customer-trust choices with a real regulatory cost,
and both are the right kind of decision to have made knowingly — but counsel
should see this table rather than the earlier, rosier one.

## B18. If Afrinkong raises travel prices

**Settled.**

> No promise that a journey always costs the same number of points. Equally, no
> arrangement where points already purchased are quietly devalued.
>
> **Programme terms are locked.** Points bought under Programme 2026-A keep
> 2026-A's entitlement rules, identifiably. Changed economics means launching
> **Programme 2027-B**, not silently rewriting 2026-A.

The CFPB has warned that materially devaluing rewards consumers have already
earned or purchased raises consumer-protection concerns where a programme's own
representations create reasonable expectations of value. The defence is not a
disclaimer; it is that the terms attached to a point cannot move.

### B18.1 Already enforced, with one hole

This is B6 restated with the reason attached, and the schema already does the
work: `point_programs` economics are immutable after creation, the trigger at
`tools/points/schema.sql:87` refuses any `UPDATE` to `issue_rate`,
`entitlement`, `buyback` or `cancellation`, and every ledger row carries its
`program_id`.

The hole is B6.1's, and B18 makes it sharper. B18 requires that the rules for a
customer's points remain **identifiable** — and `wallet()` folds every programme
into one aggregate, so a customer holding 2026-A and 2027-B points cannot be
told which are which. The history is intact; the answer is not reachable.

**B18 turns B-iii from housekeeping into a requirement of the settled model.** It
is not a decision to make, it is work the model now depends on.

## B19. Currency

**Settled.**

> Payment may be taken in multiple currencies — USD, EUR, NOK, GBP and others.
> **The Travel Point itself stays currency-neutral.**
>
> The ledger never says *1 TP = $1*. It says: *customer purchased 500 TP under
> Programme 2026-A*, and the payment record separately says *$500 USD* or
> *€460 EUR*. Two records.

This is B1's separation of payment from entitlement doing exactly what it was
built for, and it is why Stripe is the rail rather than the ledger.

### B19.1 The payment side is ready; the programme side is not

| | |
|---|---|
| `payments.currency` | `char(3)`, present — a payment already knows its currency |
| `point_ledger` | records points and programme, no currency — **correct**, and B19 confirms it |
| `programme.currency` | `'USD'`, a single value |
| `programme.issueRate` | one number, *points per unit of that currency* |

So `pointsFor(50000)` returns 500 TP whether those 50,000 minor units are
dollars or euros. It cannot tell, because the programme binds one rate to one
currency.

B19's own example resolves it: 500 TP costs **$500 or €460** — a *published
price per currency*, not a conversion applied at payment time. That keeps the
point currency-neutral and avoids FX drift between purchase and redemption
entirely. `issueRate` therefore needs to become a map from currency to rate, and
the programme needs to declare which currencies it accepts.

### B19.2 Currency plus B12 means lot order decides what a refund is paid in

B12 settled repurchase as 90% of **purchase consideration**. If a customer paid
€460, the consideration is €460, and 90% of it is €414 — in euros.

A customer who bought some points in dollars and some in euros therefore holds
lots in two currencies, and **which lot is repurchased determines the currency
they are paid in**. That is now a third dimension of open question B-ii, which
already spanned programme and purchased-vs-promotional.

It also raises something new: whether a repurchase may be paid in a currency
other than the one paid, and who carries the FX movement if so. Registered.

---

## Open questions after B17–B19

| # | question | status |
|---|---|---|
| B-ii | which lot is consumed or repurchased first | **three dimensions now**: programme, purchased-vs-promotional, and currency |
| B-iii | should `wallet()` return per-programme balances | **no longer optional** — B18 requires the rules to stay identifiable |
| B-xvii | promotional terms: parallel block or overrides | more evidence from B17 — expiry joins the list of differing terms |
| B-xviii | must `issueRate` become a per-currency map, and which currencies does a programme accept? | new, B19.1 |
| B-xix | may a repurchase be paid in a currency other than the one paid, and who carries the FX movement? | new, B19.2 |

---

## B20. Stripe is the rail, not the authority

**Settled. Already the architecture.**

    CUSTOMER
       │
       ▼
    AFRINKONG TRAVEL POINT PROGRAMME
       │  programme rules · issuance · entitlement · travel goal
       │  reservations · redemption · repurchase rules
       ▼
    POINT LEDGER
       ▼
    PAYMENT RAIL  (Stripe)

> Stripe answers: *did the customer successfully pay?*
> The Afrinkong ledger answers: *what Travel Points does that payment entitle
> the customer to receive?*

Nothing to change. The schema already says this in its own comments — *"Stripe is
the payment rail and is NOT the point ledger"* — and enforces it structurally:
`payments` records what the provider told us, `point_ledger` records what
Afrinkong then issued, and a single reference joins them. That is what lets a
reconciliation ask whether every settled payment has exactly one issuance and
get an answer.

B19 is the same principle seen from the currency side: money has a currency,
points do not, and they are different records because they are different things.

## B21. Stripe must never directly create points

**Settled. Already enforced.**

Never:

    Stripe payment succeeded  →  add points

Instead:

    Stripe → payment event → verify webhook → settled payment
           → economic transaction → ledger entry → Travel Points issued

> If Stripe sends the webhook twice, the customer gets points once.

### B21.1 Where each link is enforced

| link | enforced by |
|---|---|
| a webhook is verified before it is believed | `payment_events.signature_ok`, recorded per event |
| a redelivered webhook is recognised as one | `unique (provider, event_id)` — replay protection in the schema |
| one payment is one row, ever | `unique (provider, provider_ref)` on `payments` |
| only *settled* money issues points | `fold` ignores a `PURCHASE` whose status is not `SETTLED` |
| a repeated economic transaction issues once | every entry carries an idempotency key; `fold` ignores a key it has seen |
| an entry without a key is refused outright | `fold` throws rather than risk a double issuance |
| nothing issues at all under a draft programme | `fold` throws — the gate added with `PRODUCT_STATE` |

Three existing checks cover the last three directly: *a payment delivered twice
issues points once*, *an entry without an idempotency key is refused*, and
*folding the same history twice gives the same answer*.

Worth naming the shape, because it is the same one that made B10 sound:
**verification and idempotency are enforced at two independent layers.** The
schema refuses a duplicate event; the fold refuses a duplicate entry. Either
alone would be adequate on a good day. Both together survive a bad one.

## B22. The Travel Wallet

**Settled.**

> Keep the word *Travel Wallet* in the interface — it is intuitive. But it is a
> **record of Travel Point entitlements**, not a financial wallet.
>
>     Travel Wallet
>     2,450 TP available
>     1,200 TP reserved
>     3,650 TP total entitlement
>
> **Never** *$3,650 balance*. Enforced throughout the product.

### B22.1 The wallet is already clean, and now asserted to stay so

`wallet()` returns ten fields and every one is a count of points:

    available  reserved  redeemed  acquired  transferred
    boughtBack expired   reservations  entriesApplied  duplicatesIgnored

No `balance`, no `value`, no `amountMinor`, nothing denominated in money. That
is B22 already satisfied, and it is now a check rather than a happy accident —
the failure mode is somebody adding a convenience field years from now, and a
field named `valueMinor` on a wallet is the sentence B22 forbids, shipped.

### B22.2 Two functions can turn points into money, and neither is a wallet

`entitlementOf(points)` and `priceOf(points)` both return money. Both are
legitimate: the first is redemption arithmetic, the second prices an
acquisition, and B12's repurchase quote needs one of them.

B22's rule is about **where they may appear**. Neither is a wallet field and
neither may be rendered as a balance. A repurchase quote is a specific offer
about specific points at a moment — *"we may repurchase these 1,000 points for
$900"* — and that is a quotation, not a statement of what a holding is worth.

Note also that `entitlementOf(3650)` and `priceOf(3650)` currently return the
identical figure, because both rates are 1. They answer different questions and
diverge the moment a promotional programme exists — the same latent collapse as
§A4 and B12.2, in a third place. It is a good argument for never displaying
either as a single "your points are worth" number: there is no such number, and
under a promotional programme there are two.

---

## Open questions after B20–B22

None added. B20 and B21 are confirmations, and B22 is a rule the code already
keeps.

---

## B23. The complete economic lifecycle

**Settled.**

                          TRAVEL GOAL
                        "I want Kenya"
                              │
                              ▼
                     journey requirement
                            4,800 TP
                              │
                              ▼
                      BUY TRAVEL POINTS
                              │
                              ▼
                           PAYMENT
                              ▼
                          SETTLED ✓
                              ▼
                        POINT LEDGER
                              ▼
                           1,000 TP
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
               KEEP                     RESERVE
                 │                         ▼
                 │                       BOOKING
                 │                         │
                 │                ┌────────┴────────┐
                 │                ▼                 ▼
                 │             TRAVEL            CANCEL
                 │                ▼                 ▼
                 │             REDEEM         RELEASE / TERMS
                 ▼
         ELIGIBLE REPURCHASE
                 ▼
          AFRINKONG OFFER 90%

Every arrow on that diagram already exists as a ledger kind, a programme rule or
a documented gate. Nothing in the lifecycle is speculative — the parts that are
missing are *distinctions within* these steps, not steps.

## B24. The frozen rules, audited against the code

**Settled.** Twenty-eight rules. Each checked rather than agreed with.

| # | rule | decision | in the code |
|---:|---|---|---|
| 1 | point meaning | travel entitlement | ✅ A1a frame |
| 2 | currency | not currency | ✅ a ledger entry carries none — asserted |
| 3 | cash value | none | ✅ no monetary field on a wallet — asserted |
| 4 | interest | none | ✅ asserted three ways (B7.1) |
| 5 | yield | none | ✅ same |
| 6 | investment | none | ✅ no growth vocabulary in live code |
| 7 | mandatory monthly saving | no | ⚠️ **shipped copy contradicts** — *"Suggested monthly target"* (B3.1) |
| 8 | customer chooses frequency | yes | ✅ nothing schedules or compels |
| 9 | programme-specific terms | yes | ✅ versioned `point_programs` |
| 10 | terms after issuance | immutable | ✅ schema trigger refuses the UPDATE |
| 11 | payment rail | Stripe later | ✅ not integrated |
| 12 | payment creates points | only after settlement | ✅ non-`SETTLED` purchases ignored |
| 13 | ledger | append-only | ✅ schema trigger |
| 14 | balance | derived | ✅ folded every time, never stored |
| 15 | customer wallet | entitlement record | ✅ asserted (B22.1) |
| 16 | customer-to-customer transfer | no in V1 | ❌ **`transferable: true`** (B14.1) |
| 17 | secondary market | no in V1 | ✅ no counterparty, recipient or price anywhere |
| 18 | redemption | Afrinkong eligible travel | ✅ A1a |
| 19 | buyback | possible, discretionary | ✅ `discretionary: true` |
| 20 | buyback reference | 90% | ⚠️ rate is `0.90`, **basis is wrong** (B12.2) |
| 21 | buyback of reserved points | no | ✅ *"only available points can be bought back"* |
| 22 | final 7 days | no buyback | ❌ `cancellation()` knows; `buybackQuote()` never asks (B13.1) |
| 23 | purchased-point expiry | no time expiry | ⚠️ `expiryMonths: 0`, but **not differentiated** (B17.1) |
| 24 | promotional-point expiry | possible | ❌ not expressible — no lot type (B16.2) |
| 25 | programme changes | new programme | ✅ schema |
| 26 | price changes | never rewrite issued terms | ✅ schema trigger |
| 27 | automatic growth | never | ✅ no clock in the ledger |
| 28 | investment return | never | ✅ same |

**Twenty-one conform. Three are contradicted. Four are partial.** None of the
seven is a surprise — each was found and recorded when its section was written,
and each is pinned by a check so it cannot ship quietly.

Grouped by what it would take to close them:

| | rules | work |
|---|---|---|
| **one word** | 16 | `transferable: false` — blocked on nothing but your word |
| **one line and one test** | 20 | repurchase on consideration rather than entitlement — B12's basis |
| **wiring, no new concepts** | 22 | give `buybackQuote` the booking so it can consult the ladder |
| **copy** | 7 | two prescriptive strings on the fund page |
| **a lot type** | 24, and the differentiated halves of 23 | the promotional issuance B16 requires |

That is the whole of the distance between the frozen model and the code. It is
shorter than the section is long, which is the point of having written it down.

## B25. How this is sold

**Settled, and it is the most important product decision in Section B.**

> **Not** *"saving money"*. That creates the wrong mental model.
>
> **Build your journey before you book it.**
> **Buy your journey in Travel Points, one purchase at a time.**
>
> The customer's problem: *"I want to travel to Kenya, but I can't afford the
> whole journey today."*
>
> Afrinkong's answer: *you don't have to pay for the whole journey today. Build
> your Travel Point balance over time, then use it toward the journey when
> you're ready.*

Every legal distinction in Sections A and B is downstream of this sentence. A
product sold as saving is a product a customer believes holds their money, and
no amount of careful drafting elsewhere survives a homepage that says otherwise.
Selling it as *buying a journey in instalments* is both truer and easier to
defend — the customer is acquiring travel, progressively, which is exactly what
the entitlement model says they are doing.

It also settles the framing question B3.1 raised. *"Suggested monthly target"*
is savings language: it tells the customer what they must set aside. *"You are
projected to arrive in fourteen months"* is purchase language: it tells them how
far along they are. The copy change and the economic model are the same decision
wearing different clothes.

---

## Section B status

    DESIGN APPROVED — PENDING LEGAL/REGULATORY REVIEW BEFORE ACTIVATION
    ECONOMIC AND LEDGER MODEL: LOCKED

Not `ACTIVE`. Not `START ACCEPTING MONEY`.

| | |
|---|---|
| the economic model | design approved, B1–B25 |
| activation | **blocked** pending legal and regulatory review |
| the programme | `draft`; `PRODUCT_STATE` is `DRAFT_PROGRAM` |
| money taken to date | none, and none can be — `fold` throws on any issuing entry under a non-active programme |
| open questions | seventeen, registered and unresolved |
| conformance | 21 of 28 rules enforced; 7 recorded and pinned |
| the ledger model | **locked** — the two rates are proved independent, terms are frozen in the module as well as the schema, and a correction names what it corrects |

Counsel needs, at minimum: the four exposure features and how they now sit
(B17.2 — two easier, two harder, all deliberate), the repurchase basis and its
discretionary character (B12), the absence of any secondary market (B14, B15),
and the prepaid-access analysis this is all pointed at.


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
