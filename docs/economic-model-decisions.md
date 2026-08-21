# The economic model: what is settled, and what still gates activation

> **The canonical entry point is [`travel-point-decisions.md`](travel-point-decisions.md).**
> This document is the reconciliation register — the original eleven questions
> and what became of each. Read the index first.

Wankong LLC, trading as Afrinkong.

**This document was the register of eleven open questions. Nine decisions (A–I)
have since been settled and it had drifted badly out of step with them** — it
cited a programme field that no longer exists, described a feature as
unimplemented that now is, recommended against something Decision F decided to
do, and repeated a claim about activation that has been false since the
compliance ladder was built.

It is now the **reconciliation register**: for each original question, whether
it is answered, by which decision, and what remains.

**Current product state: `DRAFT_PROGRAM`, `compliance: DRAFT`.** No point can be
issued.

---

## The correction that matters most

This document, and `CLAUDE.md`, both said:

> `PROGRAMS['AFK-TP-2026.1'].status` is `'draft'`. Moving it to `'active'` is a
> one-word change, and it is the single most consequential one-word change in
> this repository.

**That has been false since Section D.** `status` is inert:

```
variant with status: 'active'  ->  mayIssue: false, stateOf: DRAFT_PROGRAM
```

Issuance is gated on `compliance`, not on `status`, and reaching an issuing
state is **not a one-word change**. It requires walking a ladder that cannot be
skipped —

```
DRAFT → LEGAL_REVIEW → ACCOUNTING_REVIEW → APPROVED → PILOT
```

— and `mayActivate()` refuses the final step while any of `maxProgrammeExposure`,
`maxPerTransaction`, `maxPerCustomerPerYear`, `buyback.basis` or `minPurchase` is
unset, or while `issueRate` is anything but a single positive number.

**Decision G then added a second condition**, because reaching `ACTIVE` was
still turning issuance on by itself — so the last rung carried two decisions at
once. `mayIssue` now requires an issuing compliance state **and**
`issuanceEnabled === true`. Either alone is inert, which is the same failure
`status` was: one flag must never be the whole gate.

Ask `readiness(programId)`. It reports the rung, both conditions and every
unmet one, and never consults `status`.

The old sentence was more alarming and less true. Worth correcting precisely
because a reader who believed it would have been guarding the wrong word.

---

## The eleven questions, reconciled

| | question | state | where |
|---|---|---|---|
| 1 | what does one Travel Point represent? | **frame settled**, unit basis open | A, B |
| 2 | fixed value, or programme-specific? | **settled** — programme-specific, immutable, versioned | B |
| 3 | do points expire? | **settled** — purchased never; promotional at 24 months | D |
| 4 | transferable to a third party? | **settled** — gift yes, sale no | E |
| 5 | buyback contractual or discretionary? | **settled as discretionary**; *the legal characterisation is still open* | C, E |
| 6 | buyback before/after reservation? | **settled** — available points only | C, E |
| 7 | journey price increases? | **settled** — both numbers shown, no revaluation | F |
| 8 | journey price decreases? | **settled** — the journey gets cheaper, the point does not change | F |
| 9 | Afrinkong journeys only, or third-party charges? | **settled twice — F said in, H said includable-but-not-included** | F, H |
| 10 | unused points if a programme is discontinued? | **settled** — closure is not confiscation; **cessation** handled too | D, G |
| 11 | what legal structure applies? | **STILL OPEN. This is the gate.** | — |

### 3. Do points expire?

**Was:** *"no — `expiryMonths: 0`"*. That field does not exist and did not at
the time of writing.

**Now:** `expiry: { purchased: null, promotional: 24,
reservedRightToIntroduce: false }` — purchased points never lapse from time
alone, promotional grants lapse at 24 months, and this programme did **not**
reserve a right to introduce expiry later. Decision D, and D8 settles which
lot is consumed first: earliest expiry.

### 4. Are points transferable?

**Was:** *"`transferable: true` in the programme, but no transfer is
implemented"* — wrong in both halves at different times. The flag was `false`
for most of the model's life, and transfer is now implemented.

**Now:** `transferable: true`, `secondaryMarket: false`, and
`scripts/transfer.js` executes gift, family-pool, corporate and estate
transfers with identified parties, programme-preserving terms, and conservation
of supply. Decision E — which **reversed** B14/C9.

### 5. Contractual or discretionary?

**Settled as discretionary** and enforced: `discretionary: true`, `REFUSED`
(the terms said no) kept apart from `REJECTED` (Afrinkong chose to).

The quoted sentence in the old version no longer exists verbatim. The live text
is:

> Afrinkong may repurchase these points at 90% of what you paid for them. This
> is an offer under the terms of this programme, not a guaranteed right of
> redemption.

**The commercial decision is made; the legal one is not.** Whether a published
discretionary offer creates a redemption right *in substance* is E-a, and it
still feeds question 11.

### 9. Afrinkong service only? — **this one reversed**

**Was:** *"Afrinkong service only — recommended, not yet decided… This is the
recommendation the audit makes most strongly: keep redemption to Afrinkong's
own service, at least initially."*

**Decision F went the other way,** deliberately. Park fees, conservation fees,
permits, entrance fees and government charges **are** eligible — when Afrinkong
arranges and settles them. The distinction that makes this safer than the audit
feared is that Afrinkong is not holding value against third-party obligations
in the abstract: the charge is part of an itinerary Afrinkong is contractually
arranging, and the customer's points cover it while Afrinkong settles the
supplier separately.

**Then Decision H moved the default back.** The charges remain *includable* —
`includableServices`, adoptable by any programme — and `AFK-TP-2026.1` no
longer covers them, because a customer should not believe every unpredictable
government charge is already paid for. The capability and the default are
different questions and only the default moved. This line has now changed
direction twice and all three positions are recorded in
`travel-point-continuity.md`.

The audit's underlying concern survives as **F-charges**: *which* charges
Afrinkong is actually contractually responsible for varies by destination, and
nobody has enumerated that.

### 10. A discontinued programme

**Was:** *"undecided. `point_programs.status` has a `withdrawn` state and
nothing defines its consequences."*

**Now:** the closure ladder is defined and enforced —

```
ACTIVE  →  CLOSED_TO_NEW_PURCHASES  →  REDEMPTION_PERIOD  →  CLOSED
```

redemption survives the first three, and **a programme cannot reach `CLOSED`
while points are outstanding** — an unstated outstanding balance is refused
too. D6's remedy hierarchy covers the case where the journey itself disappears:
equivalent travel, another eligible service, then buyback, with erasure not on
the list at any rank. Decision D.

**Decision G then answered the harder case**: what if Afrinkong can no longer
*provide* the travel? `windDown()` read only whether the compliance state
permitted redemption — and a ceased company is permitted to redeem and simply
cannot. Permission is not capability. Cessation is now its own programme term,
the hierarchy has four rungs and falls through to repurchase, and `CLOSED`
requires the obligations to be recorded as performed rather than the balance
merely reaching zero.

What remains is **D-outstanding**: what happens if points remain outstanding
*indefinitely*, where unclaimed-property law may compel a treatment the
programme cannot choose.

---

## 11. The one that still gates everything

**OPEN. No money may be taken.**

Questions 1, 3, 4, 5 and 9 all fed this assessment and all now have answers — but
answering them does not answer this. Two of the answers moved the analysis
**toward** higher exposure, on purpose and with that recorded:

| decision | direction | recorded as |
|---|---|---|
| E — transferability permitted | toward | E-analysis |
| F — third-party charges eligible | toward | F-charges |
| D — purchased points never expire | a liability with no end date | D-liability |
| C/E — discretionary buyback published in terms | possibly a right in substance | E-a |

The four structures remain reachable, which is still why `PROGRAMS` is
versioned data rather than constants:

| model | what it is | what would change |
|---|---|---|
| **A — Afrinkong travel credit** | credit for Afrinkong services specifically | narrow `eligibleServices`; set `transferable: false` |
| **B — Travel Points** | units with defined redemption rules — what is built | as-is, once terms are approved |
| **C — Membership / benefit** | recurring membership producing travel benefits | a programme whose issuance is a benefit schedule |
| **D — Regulated financial partner** | a licensed institution holds the money | the ledger records entitlement only |

The customer experience is close to identical across all four. The legal
character is not.

---

## The questions the six decisions opened

Settling A–F did not reduce the open set to one. It replaced eleven broad
questions with one gate and roughly thirty-five specific ones, which is
progress: a specific question can be sent to counsel.

| document | open items |
|---|---|
| `travel-point-issuance.md` | B-mechanism, B-recovery, B-clawback, B-cohort, B-recognition |
| `travel-point-exit.md` | C-limits, C-completion, C-model, C-basis, C-window |
| `travel-point-duration.md` | D-runoff, D-outstanding, D-equivalent, D-liability, D-promoexpiry, D-goalinput |
| `travel-point-transfer.md` | E-analysis, E-kyc, E-limits, E-tax, E-estate, E-poolconsent |
| `travel-point-redemption.md` | F-portion, F-mechanism, F-charges, F-newservices, F-components, F-naming |
| `travel-point-pricing.md` | F-a … F-g |
| `travel-point-buyback.md` | E-a … E-k |

**The one blocking the most others is `C-basis` / `E-c`:** which repurchase
basis `AFK-TP-2026.1` carries at activation. It is currently `consideration`,
provisionally, and several downstream questions resolve once it lands.

---

## Build order

| | step | state |
|---|---|---|
| A | product / legal definition | **frame settled; question 11 open** |
| B | programme engine | **built** — versioned, deep-frozen |
| C | database | **designed, not created** — schema written, no project |
| D | Stripe | **not started** — deliberately |
| E | customer account | ledger and fold exist; no accounts |
| F | Travel Goal | **planning-only version live** |
| G | purchase | architecture built, unreachable |
| H | redemption | architecture built, unreachable |
| I | cancellation / buyback / transfer | architecture built, unreachable |
| J | operations | not started |

**Why the order still matters more than the progress.** D is a payment rail,
not the definition of the economy. Building it first would have made Stripe's
data model the de facto answer to A — a Travel Point would have become
"whatever a Stripe object can represent", decided by an integration rather than
by anyone.

G, H and I now have architecture and no reachable path: every one of them
terminates in a refusal from the compliance gate.

---

## What is safe to build before question 11 is answered

- The **Travel Goal** panel — arithmetic over the rate card, issuing nothing.
- The **ledger, schema and reconciliation views** — needed identically under
  models A, B and C.
- The **economic architecture** itself, which is what A–F built: it encodes
  rules and executes none of them.

**Not safe:** any purchase flow, any wallet showing a real holding, any buyback
or transfer execution, and any language on the live site implying a customer
owns or can buy a Travel Point today.

---

## The line the code will not let anyone cross by accident

    PLANNING  ->  DRAFT_PROGRAM  ->  ACTIVE_PROGRAM
                                     only here may a point be issued

Enforced by `compliance`, not by `status`. `fold()` refuses any issuing entry
under a non-issuing programme; `mayTransition()` refuses a skipped rung; and
`mayActivate()` refuses a programme with an unset exposure limit or a rate that
varies by tranche.

`tools/points-checks.js` (181) and `tools/goal-checks.js` (36) both fail if that
boundary is weakened — which is the point of writing it as a test rather than as
a paragraph.

A check now also fails if **this document** cites a programme field that does
not exist, because that is exactly how it drifted the first time.
