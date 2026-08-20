# The economic model: eleven decisions nobody has made yet

Wankong LLC, trading as Afrinkong. Every question below is **open**, and each
one is open on purpose: assuming an answer in code is how a product acquires a
legal character nobody chose for it.

Where the code needs a value to run, it takes the **most conservative** option
and marks it as provisional. Those defaults are listed so a reader can see what
would change, not so anybody can treat them as settled.

**Current product state: `DRAFT_PROGRAM`.** No point can be issued —
`points-ledger.js` refuses any issuing entry under a non-active programme, and
`tools/goal-checks.js` asserts that refusal. The site shows a Travel *Goal*,
which is arithmetic, and sells nothing.

---

## How to read the tables

| column | meaning |
|---|---|
| **provisional** | what the code does today so it can run |
| **why it matters** | what actually turns on the answer |
| **owner** | who has to decide — not who implements it |

---

### 1. What exactly does one Travel Point represent?

| | |
|---|---|
| provisional | one unit of Afrinkong travel purchasing entitlement, `entitlement: 1` |
| why it matters | this is the definition every other answer inherits. "One dollar of value" and "one unit of entitlement redeemable per the terms" are different products with different regulators. |
| owner | legal counsel, with the founder |

The code deliberately holds `issueRate` (points per dollar paid) and
`entitlement` (travel value applied per point) as **two separate numbers**, even
though both are currently 1. Collapsing them into one is what makes a point
look like a dollar.

### 2. Is a point's value fixed, or specific to its programme?

| | |
|---|---|
| provisional | programme-specific. `point_programs` is versioned and its economic terms are immutable after creation. |
| why it matters | a fixed universal value is close to a stored-value instrument. Programme-specific terms let a 2026 point keep 2026 rules while 2028 offers something different. |
| owner | legal counsel |

The schema enforces this: a trigger refuses any UPDATE that changes
`issue_rate`, `entitlement`, `buyback` or `cancellation` on an existing
programme. Changing terms means issuing a new version.

### 3. Do points expire?

| | |
|---|---|
| provisional | **no** — `expiryMonths: 0` |
| why it matters | expiry is regulated in many US states under unclaimed-property and gift-card law, and several prohibit it outright or set minimum periods. It is also the single most resented feature of any points scheme. |
| owner | legal counsel |

### 4. Are points transferable to a third party?

| | |
|---|---|
| provisional | `transferable: true` in the programme, but **no transfer is implemented** |
| why it matters | transferability is one of the strongest signals that something is a payment instrument rather than a customer credit. A gift to a family member and an open secondary market are different things and the terms must say which is allowed. |
| owner | legal counsel |

The ledger has `TRANSFER_IN` / `TRANSFER_OUT` kinds and the schema requires a
counterparty, so the accounting is ready. Nothing executes them.

### 5. Is buyback contractual or discretionary?

| | |
|---|---|
| provisional | **discretionary** — `buyback.discretionary: true` |
| why it matters | **this is the most consequential question in the document.** A guaranteed right to convert points back to cash is close to a deposit or stored-value obligation. A discretionary programme is a commercial gesture. The difference may decide whether money-transmitter licensing applies. |
| owner | legal counsel, before any customer money is taken |

`buybackQuote()` returns the sentence *"Buyback is offered at Afrinkong's
discretion under the terms of this program. It is not a guaranteed right of
redemption."* and a test asserts it. If counsel makes it contractual, that
sentence changes and so does the regulatory analysis.

### 6. Is buyback available before and after a reservation?

| | |
|---|---|
| provisional | **available points only**; reserved points cannot be bought back |
| why it matters | once points are reserved against a journey, Afrinkong may have committed to suppliers. Allowing buyback then transfers that risk to Afrinkong. |
| owner | operations, with legal |

Implemented and tested: a buyback request covering reserved points is refused
with *"only available points can be bought back"*.

### 7. What happens when a journey price increases?

| | |
|---|---|
| provisional | **nothing is promised.** The goal recalculates against today's rate card, and the rate card version is displayed. |
| why it matters | a customer accumulating for eighteen months will see the target move. Whether the earlier price is honoured is a commercial promise nobody has made, and honouring it is a real liability that must be priced. |
| owner | founder / commercial |

The panel already shows *"Calculated from rate card 1d60cf455f9a"* so the change
is explicable rather than mysterious. `journey_prices` in the schema records the
version and the price shown, which is what a price-protection promise would need
if one is ever made.

### 8. What happens when a journey price decreases?

| | |
|---|---|
| provisional | nothing — the goal simply becomes easier to reach |
| why it matters | the symmetric case, and the easy one. Worth an explicit answer only because a price-protection promise in question 7 usually implies a floor here too. |
| owner | founder / commercial |

### 9. Afrinkong journeys only, or third-party services too?

| | |
|---|---|
| provisional | **Afrinkong service only** — recommended, not yet decided |
| why it matters | `tourism/rates.json` separates **Afrinkong service** from **destination charges** (park fees, permits, entrance charges) because the latter are settled at cost to third parties. If points redeem against those, Afrinkong is holding value against third-party obligations, which is a materially different risk and much closer to a general payment instrument. |
| owner | legal counsel, with operations |

This is the recommendation the audit makes most strongly: keep redemption to
Afrinkong's own service, at least initially.

### 10. What happens to unused points if a programme is discontinued?

| | |
|---|---|
| provisional | **undecided.** `point_programs.status` has a `withdrawn` state and nothing defines its consequences. |
| why it matters | this is the question that becomes urgent exactly when the company is least able to answer it well. It should be settled in the terms before the first point is sold, not improvised later. |
| owner | legal counsel |

### 11. What legal structure applies before accepting customer money?

| | |
|---|---|
| provisional | **none established.** No money may be taken. |
| why it matters | a product that takes money over time for redeemable units, with cash buyback, may be regulated as stored value or money transmission in the United States — federally and state by state — regardless of the name on the unit. Questions 1, 3, 4, 5 and 9 all feed this assessment. |
| owner | legal counsel |

Four possible structures were raised and the architecture keeps all four
reachable, which is the main reason `point_programs` is versioned data rather
than constants:

| model | what it is | what would change in code |
|---|---|---|
| **A — Afrinkong travel credit** | credit purchased for Afrinkong services specifically | narrow `entitlement` to service only; likely drop transfer |
| **B — Travel Points** | units with defined redemption rules — what is built | as-is, once terms are approved |
| **C — Membership / benefit** | a recurring membership producing travel benefits | a programme whose `issueRate` is a benefit schedule rather than a purchase |
| **D — Regulated financial partner** | a licensed institution provides the savings component; Afrinkong stays a travel company | the ledger records entitlement only; money is held elsewhere |

The customer experience is close to identical across all four. The legal
character is not. **That is precisely why the decision can be deferred without
stalling the build — and precisely why it cannot be deferred past the first
payment.**

---

## What is safe to build before these are answered

Everything currently built, and one more thing.

- The **Travel Goal** panel — arithmetic over the existing rate card, issuing
  nothing. Live now.
- The **ledger and schema** — needed identically under models A, B and C, and
  under D for the entitlement half.
- **Reconciliation views** — same.

What is **not** safe: any purchase flow, any wallet showing a holding, any
buyback execution, any transfer, and any language on the live site that implies
a customer owns or can buy a Travel Point today.

## The line the code will not let anyone cross by accident

    PLANNING  ->  DRAFT_PROGRAM  ->  ACTIVE_PROGRAM
                                     only here may a point be issued

`PROGRAMS['AFK-TP-2026.1'].status` is `'draft'`. Moving it to `'active'` is a
one-word change, and it is the single most consequential one-word change in
this repository. It should not be made in the same commit as anything else, and
it should not be made before questions 1, 3, 4, 5, 9 and 11 have answers.

`tools/points-checks.js` and `tools/goal-checks.js` both fail if that word
changes without the rest of the work being done — which is the point of writing
the boundary as a test rather than as a paragraph.
