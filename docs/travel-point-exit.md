# Decision C — what happens when a customer wants to leave

**SETTLED as canonical.** Ten rules, each backed by a named check in
`tools/points-checks.js`. The programme remains `compliance: DRAFT`; no
repurchase can be quoted, let alone settled.

> Travel redemption is the primary purpose. Buyback is a controlled exit
> mechanism, not the purpose of the product.

---

## Numbering

Decision C is the canonical statement of ground already worked as **Section E**
(`travel-point-buyback.md`), which remains the record of *how* it was arrived
at — including the B12/E2 reconciliation and the four named invariants. Where
they differ, this document wins.

Six of the ten rules were already enforced by Section E. **Four were not**, and
they are marked below. A decision document that claims "enforced" about
something nothing enforces is worse than one that says nothing.

---

## The ten rules, audited

| | rule | enforced by | |
|---|---|---|---|
| C1 | Redemption for eligible services is the primary use | every exit is travel, an administrative act, or a discretionary offer — no cash-on-request path exists | ✅ |
| C2 | Unreserved points may qualify for programme buyback | `available` excludes reserved; three categories proved distinct | ✅ |
| C3 | Buyback is not an unrestricted withdrawal facility | `discretionary: true`; the quote says so in the customer's own sentence | ✅ |
| C4 | A minimum holding period applies | `minHoldDays: 90`, refused at day 1 and day 89 | ✅ |
| C5 | A programme-level annual buyback limit applies | `maxPerYear` **and now `maxPctPerYear`** | ⚠️ **gap closed** |
| C6 | Buyback is discretionary/programme-based (Model B) | `discretionary: true`; `REFUSED` and `REJECTED` kept apart | ✅ |
| C7 | Reserved points are governed by the booking's cancellation terms | three bands, checked at C7's own boundaries | ✅ |
| C8 | In the final window, reserved points are not buyable-back **or transferable** | buyback ✅ (E6); **transfer newly independent** | ⚠️ **gap closed** |
| C9 | No peer-to-peer resale marketplace | `transferable` ✅; **`secondaryMarket` now actually reads** | ⚠️ **gap closed** |
| C10 | No point redeemable for cash merely because a customer asks its "value" | no wallet money field; `MONEY_MOMENTS` has no "balance" | ✅ |

---

## C2 — the three categories, and why the third matters most

| situation | treatment | in the ledger |
|---|---|---|
| unreserved | eligible for the programme's buyback rules | counted in `available` |
| reserved for an upcoming journey | the booking's cancellation terms | `reserved`, excluded from `available` |
| **already consumed for completed services** | **not refundable as points** | `redeemed`; no path back exists |

The third is the one worth asserting rather than assuming. Once `REDEEM` has
run the points are gone: `REDEEMED` is a terminal booking state with no
successor, and the quantity is not quotable at any price. A customer holding
10,000 who reserves 4,800 can still be quoted on the other 5,200 — the
categories partition the holding rather than freezing it.

### One thing worth your attention

Redemption currently happens at **confirmation**, not at journey completion.
So between `CONFIRMED` and actually travelling, the points are already
consumed and there is no route back — the booking machine allows
`CONFIRMED → CANCELLED`, but not after `REDEEMED`.

That is the conservative direction and it matches C2's wording, but C2 says
*"consumed for completed services"* and confirmation is not completion. Whether
redemption should move to completion — or whether a post-confirmation
cancellation should emit a compensating entry — is **C-completion**, below.

---

## C4 — the holding period, and the product it prevents

Without it: buy points, request buyback, receive almost all the money back.
That is a deposit with an extra step, and no wording fixes it.

`minHoldDays: 90` is refused at day 1 and at day 89, quotable at day 90. The
number is a programme term pending review — **C-limits**.

---

## C5 — the percentage cap, which did not exist

**Gap closed.** `maxPerYear: 5000` is an *absolute count*: it is the whole of a
small holding and a tenth of a large one. C5 asks for *"no more than X% of
their eligible unreserved points"*, which is a different control with different
behaviour.

Both now exist and whichever is tighter binds:

```js
maxPerYear:    5000,
maxPctPerYear: null    // e.g. 0.25 — a programme decision, C-limits
```

### The salami this invites, and the defence

Measured against the holding *as it stands*, a customer sells 25%, then 25% of
the remainder, then 25% of that — and reaches most of their balance inside a
year without once exceeding the limit.

So the base includes what has already been sold back this year:

```
base = eligible now + already bought back this year
```

After selling 2,500 of 10,000 the holding is 7,500, but the base stays 10,000
and the ceiling stays 2,500. The limit means what it says.

---

## C7 — the bands, at the boundaries

| days to departure | released | buyback eligible |
|---|---|---|
| 31+ | 100% | yes |
| 8–30 | 50% *(placeholder — B11 ties this to actual supplier cost)* | no |
| 0–7 | 0% | no |

Checked at the boundaries rather than mid-band, because that is where an
off-by-one lives. *"More than 30 days"* is 31+, so **day 30 is already the
middle band** — which is what the code does.

**Cancellation attaches to the booking, not to the wallet.** A customer holding
10,000 who reserved 4,800 and cancels three days out loses those 4,800 and
keeps the other 5,200. Any rule that forgets this destroys two years of
somebody's accumulation over one changed plan.

The customer sees this sentence, not a number:

> Inside seven days Afrinkong has already committed to suppliers, so points
> reserved for this journey cannot be returned. The rest of your wallet is
> unaffected.

---

## C8 — the final-window bar, on transfer as well

**Gap closed, and the shape of the gap is the interesting part.**

Buyback inside the window was already refused (E6). Transfer was refused too —
but *only because `transferable: false` refuses every transfer*. C8's window
rule was holding as a side effect of a different rule, and would have vanished
silently the moment a programme permitted transfer. **A rule that holds only as
a consequence of another rule is a rule waiting to be lost.**

`mayTransfer()` now refuses for three independent reasons, and reports which:

| rule | refuses when |
|---|---|
| `transferable` | the programme forbids transfer at all |
| `secondaryMarket` | the transfer is a sale and the programme forbids a market |
| `restrictedWindow` | the points are committed inside a journey's final window |

Proved on a programme that *does* permit transfer: the window still refuses.

---

## C9 — no resale marketplace

`transferable: false` and `secondaryMarket: false`.

**`secondaryMarket` now actually reads.** Until this it was a declared term
that nothing consulted — precisely where `transferable` sat before E8, and
found the same way. A gift and a sale are different acts and a programme might
one day permit one and not the other, so they refuse separately.

Enforced in two places, deliberately: `mayTransfer()` refuses to offer it, and
`fold()` refuses the entry where it is written. The first is what a screen
calls; the second is what catches a screen that did not.

| | V1 |
|---|---|
| redeem for travel | **yes** |
| programme buyback | potentially, discretionary |
| peer-to-peer transfer | **no** |
| public resale marketplace | **no** |

---

## C10 — the function that must never exist

Nothing answers *"what is my balance worth"* with a number. There is no
`valueMinor` on the wallet, no `cashValue`, and `MONEY_MOMENTS` — the closed
list of the three moments money may appear — contains no `balance` moment.

A repurchase quote is an offer about **1,000 identified points under published
terms**, which is a different object from a statement of what a holding is
worth, and the code cannot produce the second.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| C-limits | What are the actual numbers — `minHoldDays` (90?), `maxPerYear` (5,000?), `maxPctPerYear` (unset)? And do they sit at defensible values, or read as friction designed to discourage a right? | counsel + commercial |
| C-completion | Should redemption move from confirmation to journey completion, so that "consumed for completed services" is literally true? Or should a post-confirmation cancellation emit a compensating entry? | product + counsel |
| C-model | C6 recommends Model B initially. What evidence would move it to Model A, and does publishing programme conditions for a discretionary offer create a redemption right in substance? (E-a) | counsel |
| C-basis | C3 is explicit that "5,000 TP = $5,000 cash" must never be said, and that the programme must specify exactly how buyback is calculated. Which basis does `AFK-TP-2026.1` carry at activation? (E-c) | counsel + finance |
| C-window | Does forfeiture inside seven days need to be characterised as a cancellation charge rather than as a loss of entitlement? (E-j) | counsel |

Everything open in `travel-point-buyback.md` (E-a … E-k) and
`travel-point-issuance.md` (B-mechanism, B-recovery …) remains open.

---

## What this decision did **not** do

- No programme was activated; `AFK-TP-2026.1` is `DRAFT` and cannot quote a
  repurchase at all.
- No money moved and no settlement mechanism was implemented.
- Buyback is nowhere described as a refund of a purchase price, or as a
  withdrawal.
- No legal conclusion was drawn about deposits, stored value, or redemption
  rights.
