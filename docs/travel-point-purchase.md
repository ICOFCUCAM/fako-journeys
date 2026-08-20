# Section C — the customer purchase and accumulation model

> **A note on numbering.** An earlier Section C settled the *Programme and
> Pricing Architecture* (C1–C23) and is implemented in `scripts/points-ledger.js`
> and `docs/travel-point-economics.md`. This is a second Section C covering how
> a customer *acquires* points over time. Both are kept; neither overwrites the
> other. Where this document says "C4" it means the purchase model's C4.

| | |
|---|---|
| the model | settled |
| the programme | `compliance: DRAFT` — nothing can issue |
| Stripe | not connected, and nothing here could use it |
| what is deliberately undecided | buyback, refunds, transferability, expiry terms, guaranteed pricing, regulatory classification, accounting and tax — all recorded in Sections B and D |

---

## C1/C2. Buying points, not opening an account

The customer purchases Travel Points under a named programme from Wankong LLC.
They are not depositing money into anything.

The copy consequence is a rule rather than a preference: never *"save $500 a
month"*, always *"build your Travel Points over time"*. The customer knows what
they are accumulating and which programme it belongs to. `scripts/purchase-plan.js`
is checked for the phrase "savings account" and does not contain one.

## C3. A plan is an intention, not a mandate

**Nothing in this repository charges anybody.** A plan records what a customer
says they mean to buy and how often; every actual purchase stays a separate,
separately authorised act. There is no payment mandate, no stored card, no
scheduled debit, and no code that could become one without a payment provider
that does not exist.

That is a product decision, not an unfinished feature. Automatic recurring
payment brings mandates, cancellation rights, failed payments and refunds; a
customer can buy every month by choosing to, and *Automatic Travel Point
Purchase* can be its own product later if it is ever wanted.

    ACTIVE  ⇄  PAUSED
       ↓         ↓
        STOPPED (final)

`PAUSED` and `STOPPED` differ in intent rather than effect — a pause says *not
now*, a stop says *no more* — and keeping them apart means a customer who
paused is never told they cancelled. A stopped plan cannot be amended or
restarted in place: a returning customer starts a new one, so the record of
what they meant last time survives.

**And the sentence this section exists for:** stopping a plan stops *future
purchases* and touches no point already issued. Proved rather than asserted —
2,500 TP before the stop and 2,500 TP after. A plan and a balance are different
things, and `purchase-plan.js` cannot append to a ledger at all.

## C4. Issuance follows settled payment, and nothing else

    payment SETTLED  →  points issued  →  ledger records it
    payment PENDING  →  nothing
    payment FAILED   →  nothing

There is no state in which a point exists but is not spendable, because it does
not exist. "Pending points" are not modelled and should not be: a balance a
customer can see but not use is a support ticket waiting to happen, and a
balance they can use before the money settles is fraud.

Enforced twice over — the fold ignores a `PURCHASE` that is not `SETTLED`, and
the compliance ladder refuses issuance under a non-`PILOT`/`ACTIVE` programme
regardless.

## C5. A bonus is two entries

    PURCHASE   +2,500 TP
    PROMOTION    +250 TP

never `PURCHASE +2,750`. The customer sees 2,750; the ledger knows 2,500
purchased and 250 granted, permanently. Everything that depends on the
distinction — repurchase eligibility, expiry, cancellation treatment — becomes
expressible, and none of it is once the two are added together.

## C6. Accumulating toward a goal

    target 4,800 TP, at 1,000 a month

    month 1   1,000 →  1,000
    month 2   1,000 →  2,000
    month 3   1,000 →  3,000
    month 4   1,000 →  4,000
    month 5     800 →  4,800

The last month is short by construction: the customer buys what they still need
rather than what divides evenly.

**No promise attached.** Nothing here says the journey will still require 4,800
TP on arrival. The goal carries the programme and rate-card version that
produced it, and the pricing section's C8 is how a change is shown — both
figures and the difference, with the customer's own points untouched.

A paused plan projects no arrival at all rather than a number nobody should act
on.

## C7. No separate savings account

    Afrinkong → Travel Points → Travel Goal → Journey

not

    Afrinkong → open account → deposit → save → transfer → travel

The payment infrastructure sits behind the product rather than in front of the
customer.

## C8. Every point stays attributable

`lots()` answers, per lot: when it was issued, under which programme and
version, at what issue rate, carrying what entitlement rate, whether it was
promotional, what it cost, and how much of it has been reserved, redeemed,
expired, cancelled or bought back.

All of that was always in the ledger; this reads it back rather than folding it
away. It is deliberately **not** part of `wallet()` — a wallet is what a
customer is shown and B22 keeps it to counts of points, while this is what an
auditor, a dispute or a repurchase quote needs.

## What is deliberately not decided here

Buyback, refunds, transferability, expiry terms, guaranteed pricing, regulatory
classification, accounting treatment and tax. Those belong to Sections B and D,
several of them wait on counsel, and none is implied by anything above.

---

# Section D (redemption) — booking economics

> **Numbering again.** An earlier Section D settled the legal and compliance
> boundary (`docs/travel-point-compliance.md`). This is the redemption Section D.
> Both are kept.

## The one thing the booking machine exists to prevent

`balance -= 4800` when somebody clicks Book.

A booking is a conversation that can be rejected, abandoned or cancelled, and
points must survive all three. So Book **reserves**; only a confirmed itinerary
**redeems**. Two events, never one.

    REQUESTED ─┬─ REJECTED                    (nothing was reserved)
               └─ ACCEPTED ── RESERVED ─┬─ CANCELLED   (bands apply)
                                        └─ CONFIRMED ── REDEEMED

`scripts/booking.js` **appends nothing**. Every transition returns the ledger
entries it *implies*, for a caller with the authority to append them. That
keeps the machine testable without a ledger and makes it impossible for a
booking screen to consume points on its own — compliance D21.2.

## What each state costs the customer

| transition | ledger | wallet |
|---|---|---|
| REQUESTED → REJECTED | **nothing** | unchanged |
| ACCEPTED → RESERVED | `RESERVE` | 5,200 → 400 available, 4,800 reserved, **0 redeemed** |
| RESERVED → CANCELLED | `RELEASE` (+ `REDEEM` for any forfeit) | per the programme's band |
| CONFIRMED → REDEEMED | `REDEEM` | 4,800 consumed, 400 remains |

**Reserve then release returns the customer exactly where they began** —
proved, not asserted. An abandoned booking costs nothing.

## Insufficient points

Reported **in points**: 6,000 required, 4,500 held, shortfall **1,500 TP**.
`settlement.mechanism` is `null` and says so. No money figure appears anywhere
in the reply, because the programme has not defined a conversion and a function
that quietly returned "$1,500" would have decided it.

## Eligible services are programme scope

`journey`, `accommodation`, `transport`, `guiding`, `experience` are inside.
A request naming a visa or an international flight is **refused** rather than
silently part-covered, and the reply names which services fell outside. The
site already settles park fees and permits separately; this is that, as a
programme term rather than a hard-coded list.

## Cancellation is not buyback

Cancellation concerns **a booking** — *I don't want this journey*. Buyback
concerns **points** — *I don't want these any more*. Different transactions,
different terms, and buyback remains undecided.

## The invariant

    available = acquired − reserved − redeemed − boughtBack − expired − adjusted

Checked against a history containing every kind of movement, not an empty
wallet. Writing that check found that `adjusted` was tracked by the fold and
**never returned by `wallet()`** — so the identity could not be closed by any
caller. Fixed.

## Still undecided

Buyback pricing, transferability, expiry, refund rights, cancellation
penalties, the mixed-payment settlement mechanism, regulatory treatment,
accounting and tax.
