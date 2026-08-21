# Decision I — cash-equivalent display

**SETTLED as canonical.** `AFK-TP-2026.1` remains `compliance: DRAFT`.

> Travel Points must not be presented as cash, a cash balance, a deposit, or a
> universal monetary equivalent.

---

## What was already true

Most of this was settled as §F4 in `travel-point-pricing.md`: money attaches to
a **transaction** or a **journey** and never to a **holding**, `MONEY_MOMENTS`
is a closed list of three, `wallet()` exposes no monetary field, and the fund
pages are scanned for the `N TP ($N)` construction.

Three things in Decision I were **not** already true, and they are what this
document adds.

---

## 1. The four concepts, and the asymmetry

| concept | denomination | attaches to |
|---|---|---|
| money paid | **money** | a transaction |
| travel points | points | a **holding** |
| journey requirement | points | a journey |
| buyback quote | **money** | a specific offer |

**Money appears twice, and both times it is attached to a transaction** — one
that happened, one being offered. Neither attaches to a holding, and a holding
has no money denomination at all.

That asymmetry is the whole decision, and it is now data (`CONCEPTS`) rather
than a paragraph, so a check can assert it.

### They must never collapse into one field called `value`

The failure this prevents is not a bad decision — it is a well-meaning label
written by somebody who never read the rule. So every object a customer-facing
path actually produces is scanned for a field named `value`, `worth`, `balance`,
`cash` or `equivalent`: the wallet (14 fields), the holding display (10), the
purchase offer (11), the goal display (10). None has one.

---

## 2. The buyback quote is an offer, not a valuation

> Eligible points: 2,000 TP
> Buyback quote: $1,440
> Programme deduction: 10%

That is fine, **on request, about those points**. What is not fine is
displaying `2,000 TP = $400` permanently, because a standing figure like that
*becomes* the definition of the point whatever the terms say.

The quote now carries three fields that make the difference legible to a
surface rather than only to a reader:

```js
standing:     false   // never a valuation of a holding
quotedFor:    2000    // these points, not points in general
deductionPct: 10      // the programme's deduction, as a customer reads it
```

`deductionPct` is there because "90% of the applicable consideration" and "a
10% deduction" are the same arithmetic and not the same sentence, and the
second is the one a customer is owed.

---

## 3. The words, decided once

Assembled in the module rather than left to each page, because the failure mode
is a page inventing a label:

```
Your Travel Points      5,000 TP
Journey target          7,500 TP
Progress                66.7%
Remaining               2,500 TP remaining to your journey
```

Every figure is in points. `cashEquivalent` is **present and null** — so a
surface cannot add one by omission, and a reader of the object sees the absence
was deliberate.

Checked to contain no `$` at all.

---

## 4. And nothing converts a holding into money

`entitlementOf()` and `priceOfPoints()` are arithmetic about a **quantity** and
are legitimate — F4 argued that, and neither is a wallet field.

The dangerous thing is a caller passing a *wallet figure* into one of them:

```js
entitlementOf(programme, wallet.available)   // ← "your 5,000 TP are worth $5,000"
```

That is how the sentence gets written without anybody deciding to write it. All
22 scripts are scanned for it. None does it.

---

## What may still be shown

| | |
|---|---|
| **the price paid** | `Price: $450 · Points issued: 500 TP` — a purchase transaction, not a declaration that points are currency |
| **the journey's price** | what the journey costs as a travel product |
| **the journey's requirement** | `This journey requires 7,500 TP` |
| **a specific buyback quote** | on request, about identified points |

The purchase line is worth being precise about: showing `$450 → 500 TP` records
**price paid** and **points issued** as two separate facts about one
transaction. It is not a rate, not an exchange, and not a statement that 500 TP
are worth $450 — which is exactly why `purchaseOffer()` returns `points` and
`bonus` separately rather than one blended total (F3).

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| I-statement | If a customer ever receives a statement or tax document, does it have to state a monetary value — and would that be the cash equivalent this decision forbids, arriving by regulatory obligation rather than by design? | counsel + accounting |
| I-quotelife | A quote is `standing: false`, but nothing yet expires one. How long may a customer hold an unaccepted quote before it must be re-quoted? | product + counsel |
| I-aggregate | May a customer see the total they have *paid* over time — a true fact about transactions — or does an accumulated money figure beside a holding read as a balance regardless? | product + counsel |
| I-support | What may a support agent see? An internal valuation that exists only in an admin tool is still an internal cash equivalent, and internal figures leak into customer conversations. | operations + counsel |

---

## What this decision did **not** do

- No cash equivalent was created, displayed, or computed anywhere.
- No existing surface changed — this hardened and named rules the code already
  followed, and added the vocabulary so future surfaces follow them too.
- No programme was activated.
