# Decisions F, G, H — price changes, discontinuation, redemption scope

**SETTLED as canonical.** `AFK-TP-2026.1` remains `compliance: DRAFT`.

---

## A note on the letters, because two of these change earlier answers

These arrived as F, G and H, and two overlap ground already settled:

| this decision | overlaps | what actually changed |
|---|---|---|
| **F — price changes** | B18, C8 | **new**: a confirmed booking is price-locked |
| **G — discontinuation** | Decision D (closure ladder) | **new**: a wind-down *path*, and migration |
| **H — redemption scope** | Decision F (`travel-point-redemption.md`) | **two reversals**, below |

Nothing was renumbered. Where a rule reversed, it is recorded as a reversal
rather than quietly overwritten — the house style, and the only way the next
reader can tell a decision from a drift.

---

## F — price changes

> Point balances are never devalued by price changes; unbooked journey
> requirements may change, while confirmed bookings are price-locked.

### The two sides

| | |
|---|---|
| **customer side** | 5,000 TP → 5,000 TP → 5,000 TP. No decay, no repricing of a balance. |
| **Afrinkong side** | 2026: 5,000 TP · 2027: 5,500 TP · 2028: 6,000 TP. |

Already enforced: `entitlementRate` is frozen per programme, and nothing
recomputes a holding. What was **not** enforced is the lock.

### The new rule: a reserved booking is locked

> "The price increased to 6,000 TP, so give us another 1,000."

That is the sentence this refuses. The lock takes effect the moment points are
**reserved** — not at `ACCEPTED`, where nothing is committed and a customer who
has not reserved should see the current price rather than a stale one that
happens to favour them.

**It was already true structurally.** Every branch of `advance()` reads
`booking.pointsRequired` and nothing recomputes it. But structural truth is not
a refusal: a caller passing a new requirement was *silently ignored* rather than
told, and silently ignoring a reprice and refusing one look identical until
somebody relies on the first.

The lock records what it locked, with the rate card that produced it:

```js
lockedAt: { state: 'RESERVED', pointsRequired: 5000,
            rateCardVersion: 'v1', programVersion: 1 }
```

so *"why 5,000 and not 6,000"* is answerable from the booking rather than from
somebody's memory of when the customer clicked.

### Before the lock, the requirement may move — and is shown moving

A customer still saving is **not** protected, and must not be told they are.
`reprice()` returns both numbers, the difference, and the sentence that matters:

> The journey's requirement changed. The Travel Points you hold did not.

A requirement that moved and a balance that moved look identical on a screen
unless somebody says which one it was. The goal then reads **3,000 / 6,000 TP**
rather than pretending the old target still applies.

---

## G — programme discontinuation

> Closure does not by itself extinguish points already issued. Existing points
> must have a defined wind-down path.

Decision D already refuses `CLOSED` while anything is outstanding. What it did
not provide is a **path** — a refusal to close is not somewhere for the points
to go, and a programme that can neither close nor honour is *stuck* rather than
safe.

### The order, and why it is that order

| rank | step | available when |
|---|---|---|
| 1 | **redeem** | the programme may still redeem — through closure and run-off |
| 2 | **migrate** | a successor programme is named, on defined terms |
| 3 | **buyback** | the programme offers it and is in a state that permits it |

Redemption first because travel is what the points are *for*. Repurchase last
because turning entitlement back into money is the exit this product least
wants to lead with. Cancellation appears at no rank, and the return value says
so in a field: `neverAnOption`.

`windDown()` reports only what is **actually** available, so nobody offers a
migration into a successor that does not exist. If every step were closed it
returns `exhausted: true` — a human decision, explicitly not a lapse.

### Migration is the only place a point changes programme

E4 says the programme travels with the entitlement: a *gift* cannot move
somebody onto different terms. Migration deliberately does the opposite, which
is exactly why it needs more than a gift does — **three gates**:

1. **the successor must be the one the old programme named.** Not any
   programme, and not one chosen at the call site.
2. **the customer must consent.** A migration nobody agreed to is a retroactive
   change of terms wearing a different word — D9.
3. **the ratio is explicit and both sides are recorded.** At 0.9, 5,000 TP
   become 4,500 and `changesHolding: true`, so a change in the number a
   customer holds can never be something they discover.

`AFK-TP-2026.1` names **no successor** — `windDown.successor: null`. That is
different from "there will never be one", which is why the field is present and
empty rather than absent.

### If Wankong itself stops offering travel

Not designed around. The economic model must not assume the company can walk
away from outstanding points, and what the wind-down obligation actually is —
including on cessation of business — belongs in the programme's legal terms.
**G-cessation**, below.

---

## H — redemption scope

> Travel Points redeem only toward eligible Afrinkong travel services. They are
> not general-purpose currency, cash, deposits, or a claim on unrelated goods.

Most of this was Decision F. **Two things changed.**

### Reversal 1 — government charges leave the default basket

This line has now changed direction **twice**, and all three positions are worth
keeping:

| | position |
|---|---|
| original audit | Afrinkong service only — "the recommendation the audit makes most strongly" |
| Decision F | park, conservation, permit, entrance and government charges **in** |
| **Decision H** | **includable, not included** |

They remain a named capability — `includableServices` — that a successor
programme may adopt. `AFK-TP-2026.1` no longer covers them, because a customer
should not believe every unpredictable government charge is already paid for by
points they accumulated.

**The capability and the default are different questions, and only the default
moved.** Both halves are asserted, so neither can drift into the other.

A charge must appear in *one* of the two customer-facing lists — eligible-but-
unpriced, or not-included — never neither. Under H they moved from the first to
the second; what matters is that they left neither.

### Reversal 2 — a mixed settlement must be *available*, not merely permitted

`mixedPayment` read `permitted: true, mechanism: null`. That is precisely what H
warns against: presenting a shortfall as settleable in money when the mechanism
that would settle it is undefined, unsupported and not contractually described.

**A permission whose mechanism is null is not one a customer can act on**, and
offering it invites exactly the automatic cash conversion H forbids.

```
permitted:  true    ← this programme intends to allow it
mechanism:  null    ← nobody has defined how
available:  false   ← so it cannot be offered
```

`mixedSettlement()` computes all three together so no caller can read the first
and skip the second. `F-mechanism` is what would flip it.

### The four exclusions that *are* the boundary

`cash` · `bank_deposit` · `unrelated_product` · `third_party_purchase`

The other exclusions are ordinary travel ones. These four are each a way the
unit would stop being travel entitlement and start being money, so each is named
and refused by name rather than left to follow from the basket's silence.

### The next question is already answered

> whether a Travel Point may ever be displayed with a cash equivalent

**No.** `MONEY_MOMENTS` is a closed list of three — purchase price, journey
price, repurchase offer — and money attaches to a transaction or a journey,
never to a holding. Settled in `travel-point-pricing.md` §F4 and checked at four
surfaces including the live fund pages.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| G-cessation | What is the wind-down obligation if Wankong LLC ceases offering eligible travel altogether? The model must not assume it can walk away, and this belongs in the legal terms before activation. | counsel |
| G-successor | Should a successor programme exist at launch, so a wind-down always has a migration path rather than acquiring one under pressure? | commercial |
| G-ratio | May a migration ratio ever be below 1, and does a below-1 migration differ in substance from the retroactive devaluation D9 forbids? | counsel |
| G-period | How long is a wind-down period, and what triggers each step? (D-runoff, unchanged) | counsel + commercial |
| H-charges | Which government charges could a programme responsibly adopt, and per destination is Afrinkong contractually the one arranging them? (F-charges, unchanged) | operations + counsel |
| F-lockwindow | The lock begins at reservation. Should a *quoted* requirement also hold for a short window, so a customer who is mid-checkout is not repriced between clicking and confirming? | product |

---

## What these decisions did **not** do

- No programme was activated, and no successor programme exists.
- No migration was executed; `AFK-TP-2026.1` names no successor.
- No conversion rate between points and money was defined — and the mixed
  settlement it would enable is now correctly reported as unavailable.
- No point's requirement was recomputed for any existing booking.
