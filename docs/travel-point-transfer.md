# Decision E — transferability, gifting and inheritance

**SETTLED as canonical. This decision REVERSES a previously settled rule**, and
the reversal is the first thing to read.

`AFK-TP-2026.1` remains `compliance: DRAFT`. Nothing has been issued and
nothing can be transferred, because there is nothing to transfer.

---

## The reversal, stated plainly

| | before | after Decision E |
|---|---|---|
| `transferable` | `false` | **`true`** |
| `secondaryMarket` | `false` | `false` — **unchanged** |

**B14** settled non-transferability for V1, on the grounds that person-to-person
transfer is one of the features that moves a prepaid-access analysis. **C9**
restated it. The fold enforced it, refusing any `TRANSFER_IN`/`TRANSFER_OUT`
entry outright.

Decision E reverses that, and the reasoning is sound: a customer who cannot
travel and wants their spouse to use the points has a legitimate need, and *"the
points simply disappear"* is the wrong answer to it.

### Why this is one flag and not a redesign

The two halves were already separate terms, and `mayTransfer()` already refused
on them independently — built that way for Decision C, before this decision
existed:

| rule | governs | Decision E |
|---|---|---|
| `transferable` | may points move between people **at all** | now yes |
| `secondaryMarket` | may they move **for money** | still no |
| `restrictedWindow` | committed inside a journey's final window | still no |

So permitting a gift did not touch the ban on a sale. C9's real content — no
resale market — survives intact; what changed is that giving points away is no
longer collateral damage of that ban.

**What does not go away** is the prepaid-access exposure B14 was avoiding. It
moves into **E-analysis**, and counsel must answer it before activation exactly
as before.

---

## The hole this opened, found by implementing it

**This is the most important thing in Decision E.**

`maxPayableIsConsideration` is the rail from Section E/F: a repurchase may never
pay out more than came in. It **skipped silently** when consideration could not
be traced to a payment — and gifted points cannot be traced by definition,
because the recipient never made a payment.

Under an entitlement-basis transferable programme:

```
buy 5,000 TP for $5,000  →  gift to an accomplice  →  quoted $4,500
```

The rail was inactive and reported `cappedAtConsideration: false`, which reads
as "no cap was needed". Buy, gift, cash out.

**Non-transferability was hiding it.** The bug has been latent since the rail
was written; Decision E is what would have activated it in production.

Fixed: a cap that cannot be computed is now a **refusal**, not a skip.

> these points cannot be traced to a payment, so the repurchase cap cannot be
> applied

---

## The twelve rules

| | rule | enforced by |
|---|---|---|
| E1 | Transferable under controlled programme rules | `transferable: true`, `mayTransfer()` |
| E2 | Personal/family gifting permitted | `TRANSFER_TYPES.GIFT` |
| E3 | Sender and recipient identified | refused unless both named **and different** |
| E4 | The programme travels with the entitlement | both entries carry the **sender's** `programVersion` |
| E5 | Transfers create no new points | `conserves()` — in must equal out |
| E6 | Original issuance history immutable | two new entries; the `PURCHASE` is untouched |
| E7 | No fee on ordinary personal transfers | `transferFeeMinor: 0`, `feeMinor: 0` on each entry |
| E8 | Reserved points follow booking rules | excluded from `available`; window bars the rest |
| E9 | Family pooling supported conceptually | `pool()` — a view, not a joint account |
| E10 | Corporate gifting later, same unit | `CORPORATE_GIFT` type, documentation required |
| E11 | Estate transfer subject to law | `ESTATE` type, documentation required |
| E12 | No open secondary market | `secondaryMarket: false`; a transfer carries no price |

---

## E4 — the programme travels, and this is the load-bearing rule

James holds 5,000 TP under Programme 2026-A and transfers 2,000 to his wife.
She receives **2,000 TP under Programme 2026-A** — not under whatever programme
happens to be active on the day she receives them.

```
Programme 2026-A
    ├── James: 3,000 TP
    └── Wife:  2,000 TP
```

Both the `TRANSFER_OUT` and the `TRANSFER_IN` carry the sender's
`programVersion`. Without this, a recipient could be quietly moved onto worse
terms by the *timing* of a gift, which is the same devaluation D9 forbids
arriving by a different route.

---

## E12/E5 — a transfer is not an issuance

```
James  -2,000 TP
Sarah  +2,000 TP
supply  unchanged
```

`conserves()` states it as a checkable property over any set of entries: the
sum of `TRANSFER_IN` must equal the sum of `TRANSFER_OUT`. A mismatched pair is
caught and named — *"more points were received than were sent: a transfer
created 500 TP."*

---

## E3 — no anonymous transfers, and none to oneself

Every transfer records sender, recipient, amount, programme and type. A
transfer to oneself is refused: it is either a mistake or an attempt to relabel
points, and neither should append two entries.

The module checks that both ends are **named**, and deliberately does not know
what a customer is — verifying who they are belongs to a system that can.

---

## E8 — reserved points follow the booking, not the wallet

10,000 TP committed to a trip departing in five days cannot be handed to
somebody else, leaving Afrinkong holding the supplier obligations. Two separate
refusals:

- reserved points are not in `available` at all — the same arithmetic that
  refuses a repurchase of committed points;
- inside the restricted window, even the *uncommitted* remainder is refused.

This is where Decision E meets Decision C, and neither rule restates the other:
`mayTransfer()` reads the same cancellation band `cancellation()` defines.

---

## E9 — family pooling, the feature hiding inside this decision

| | |
|---|---|
| Mother | 3,000 TP |
| Father | 4,000 TP |
| Brother | 1,500 TP |
| Child | 500 TP |
| **Family Journey Goal** | **9,000 / 10,000 TP** |

**Nothing moves.** `pool()` is a *view* over points each person holds
separately — it transfers nothing, appends nothing, and creates no joint
holding. Actually moving points is a `FAMILY_POOL` transfer per contributor,
each with its own consent.

Contributions must share one programme: pooling across programmes would
silently merge two sets of terms, which E4 forbids.

It carries D11's vocabulary rather than a financial one — `9,000 / 10,000 TP`
and a `FUNDED` state, never a combined balance.

---

## E10/E11 — a place in the model, not machinery

`CORPORATE_GIFT` and `ESTATE` exist as types and are **not built**. Decision E
asks that the economic model have room for them, and naming them now costs
nothing and means neither becomes a new economic unit later.

Both carry `requiresDocumentation: true`, so neither can be executed as an
ordinary gift — an `ESTATE` transfer without a documentation reference is
refused before it is proposed.

Probate infrastructure, employer accounts, and identity verification are all
absent, deliberately.

---

## E12 — the hard boundary

No `"Travel Point Exchange"`. No order books, no anonymous resale, no
peer-to-peer cash settlement, no speculative trading, no price discovery.

Enforced by shape as well as by flag: **a transfer carries no price**. Neither
the proposal nor either entry can hold a money figure, so an order book has
nothing to quote. Speculative trading has no *representation* here, not merely
no interface.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| E-analysis | B14 avoided transferability because it moves a prepaid-access analysis. Decision E accepts that exposure. What does transferability do to the characterisation, and does gifting alone (without sale) move it at all? | counsel |
| E-kyc | What identity verification is required of a *recipient*, who may not be a customer at all until the moment they receive points? Does receiving points create a customer relationship with KYC obligations? | counsel |
| E-limits | `maxTransfersPerYear: 12` and `maxTransferredPerYear: 10000` are provisional and currently declared but not enforced by any gate. What are the right numbers, and what abuse are they actually preventing? | counsel + commercial |
| E-tax | Does a gift of travel entitlement create a taxable event for either party, and does the answer differ for `CORPORATE_GIFT`? | tax counsel |
| E-estate | What documentation satisfies an estate transfer, and does an unredeemed holding form part of an estate at all — or lapse on death under programme terms? These give opposite answers and only one can be right. | counsel |
| E-poolconsent | If four family members pool toward one journey and it is cancelled, whose points come back and in what proportion? A pool is a view, so the answer is "each person's own" — but a `FAMILY_POOL` transfer moves them, and then it is not. | product + counsel |

Everything open in `travel-point-duration.md` (D-…), `travel-point-exit.md`
(C-…), `travel-point-issuance.md` (B-…), `travel-point-pricing.md` (F-…) and
`travel-point-buyback.md` (E-a…E-k) remains open.

---

## What this decision did **not** do

- No programme was activated; nothing has been transferred because nothing has
  been issued.
- No corporate or probate machinery was built.
- No transfer limit is enforced yet — the terms are declared and E-limits is
  open.
- No conclusion was drawn about prepaid access, KYC, tax, or estate law.
