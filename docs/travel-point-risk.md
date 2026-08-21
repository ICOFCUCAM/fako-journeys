# Item Y — fraud and risk, as economic architecture

**ARCHITECTURE BUILT. No fraud model exists, deliberately.**
`AFK-TP-2026.1`: `compliance: DRAFT`, `issuanceEnabled: false`.

> Fraud controls must protect the **ledger**, not merely Stripe.

---

## Why this is not a security checklist

A payment provider tells you whether a card worked. It cannot tell you whether
*entitlement* should be created, because it does not know what entitlement is.

So a settled payment is a **necessary** condition for issuance and never a
**sufficient** one — and the gap between those two words is where every
stolen-card loss lives:

```
Stripe payment → appears successful → RISK HOLD → no Travel Points issued
```

**Money can be refunded. Points that were issued, spent on a journey and flown
cannot be.** That asymmetry is the whole reason the hold sits *before* issuance
rather than after it.

---

## The engine

```
CUSTOMER
   ├── authentication      is this the account holder?
   ├── paymentIdentity     does the instrument match them?
   ├── deviceSession       is this device/session recognised?
   └── history             is this consistent with the account?
             │
             ▼
       RISK ENGINE
       ┌─────┴─────┐
     ALLOW       HOLD ──────► MANUAL REVIEW ──► RELEASE / REJECT
       │
   ISSUE TP
```

### The most important line in the module

**A caller that supplies no signals gets `HOLD`, not `ALLOW`.**

Absent evidence is not favourable evidence. If the default were ALLOW, then
forgetting to wire up a signal would silently open the gate — and that failure
looks like nothing at all. It fails closed.

Every decision carries its **reasons**, because a hold nobody can explain is a
hold nobody can review, and manual review is the entire point of the branch
existing.

---

## Account takeover — why one decision at login is not enough

An attacker inside somebody's account does not need to buy anything. They need
to move what is already there. So each way value leaves a customer gets its own
decision:

| action | step-up | why |
|---|---|---|
| `ISSUE` | no | creates entitlement from a payment |
| `TRANSFER` | **yes** | moves points to another person |
| `RESERVE` | **yes** | commits points to a journey |
| `BUYBACK` | **yes** | converts entitlement toward money |
| `PAYOUT_CHANGE` | **yes** | changes where money would be sent |

All four sensitive actions **HOLD on a fully clean session** and allow only
with step-up — because a session is exactly what an attacker has.

An unauthenticated request is `REJECT`, not `HOLD`: there is nothing for a
reviewer to review.

---

## A hold is a state somebody ends, and the ending names them

```
HELD ──► RELEASED   (requires reviewedBy)
     └─► REJECTED
```

A release must name its reviewer; a rejection need not. Releasing is the
direction that costs money, so it is the one that needs a name — the difference
between a reviewed release and a script that released everything at three in
the morning.

---

## Chargeback after redemption

The case that makes this economic rather than merely a security concern. **The
customer flew.**

The ledger does **not** erase the redemption — history is append-only and the
journey happened. What is created instead is a **liability**:

| | |
|---|---|
| still in the wallet | recoverable as points |
| already flown | a money debt, `TRAVEL_DELIVERED_AGAINST_REVERSED_PAYMENT` |

Worked: 5,000 TP bought, 4,800 flown, payment reversed → **200 TP recoverable**,
**4,800 TP of liability**.

Deliberately **not** a negative points balance: the points are gone, correctly,
and inventing a negative would misstate what the customer holds.

And **`amountMinor: null`** — what the debt is worth depends on the reversed
payment, which lives in `payments`, and Decision I forbids attaching a money
figure to a quantity of points. Even here, especially here.

How the debt is pursued is **B-recovery**, still open.

---

## What is deliberately absent

No scores. No thresholds. No model. Those need traffic that does not exist, and
a threshold invented today would be a number nobody could defend.

This is the **architecture** — the decision points, the states, and the
refusals — so that a real model has somewhere to plug in, and so that nothing
built in the meantime can bypass the place it will go.

---

## UNRESOLVED

| | question | owner |
|---|---|---|
| Y-model | What are the actual signals and thresholds, and where does the model live — Stripe Radar, a third party, or ours? | risk + engineering |
| Y-stepup | What satisfies step-up? It must be something an attacker holding a session cannot produce. | security |
| Y-velocity | Multiple accounts, promotional abuse and resale rings are patterns *across* customers; nothing here looks across accounts. | risk |
| Y-review | Who reviews a hold, in what time, and what does a customer see while it stands? A silent indefinite hold is its own harm. | operations |
| Y-recovery | B-recovery, unchanged: how a post-travel debt is actually pursued. | counsel + finance |

---

## What this did **not** do

- No fraud model, no scores, no thresholds.
- No programme was activated; `issuanceUnderRisk()` cannot issue under
  `AFK-TP-2026.1` regardless of how clean the signals are.
- No money figure was attached to any quantity of points, including the
  liability.
- No redemption was reversed.
