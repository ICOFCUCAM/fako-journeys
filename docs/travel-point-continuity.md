# Decisions F, G, H — price changes, discontinuation, cessation, redemption scope

**SETTLED as canonical.** `AFK-TP-2026.1` remains `compliance: DRAFT`.

---

## A note on the letters, because two of these change earlier answers

These arrived as F, G and H, and two overlap ground already settled:

| this decision | overlaps | what actually changed |
|---|---|---|
| **F — price changes** | B18, C8 | **new**: a confirmed booking is price-locked |
| **G — discontinuation** | Decision D (closure ladder) | **new**: a wind-down *path*, migration, cessation, and `active` ≠ `mayIssue` |
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

*(Four rungs — the full table, including `alternative` and the cessation case,
is under "The fourth rung, which was missing" below.)*

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

### If Wankong itself stops offering travel — G-cessation, now settled

> Business cessation is not itself an economic event that destroys a
> customer's accumulated entitlement.

**This broke an assumption every earlier decision rested on.** `windDown()`
read `mayRedeem()` alone — which asks whether the compliance state *permits*
redemption. A company that has ceased providing eligible travel is still
permitted to redeem and simply **cannot**. Offering that step would have been
the cruellest possible answer: one the customer takes and nobody can perform.

**Permission is not capability**, and the wind-down was reading only the
permission.

`cessation` is now a programme term, separate from the compliance state:

```js
cessation: { ceased: false, ceasedOn: null, reason: null,
             obligationsCompleted: false }
```

When `ceased` is true, redemption and alternative services report
`available: false` with `permitted: true` — the distinction stated rather than
collapsed — and the hierarchy **falls through to the repurchase mechanism**
rather than to nothing. That fall-through is the entire reason the order has
four rungs.

### The fourth rung, which was missing

Decision G names four steps. `windDown()` had three: `alternative` — another
eligible Afrinkong service where the original is unavailable — lived in
`remedies()` as a separate function, so a wind-down and a discontinued journey
answered the same question in two places. One list now:

| rank | step | unavailable when |
|---|---|---|
| 1 | redeem | the state forbids it **or travel has ceased** |
| 2 | **alternative eligible service** | travel has ceased, or scope is empty |
| 3 | migrate | no successor is named |
| 4 | buyback | the programme does not offer it |

`alternative` sits above migration because it is still travel under *this*
programme. Repurchase stays last.

### TERMINATED means the obligations were performed

D4 refused `CLOSED` while points were outstanding. That checked a **balance**,
and Decision G asks for something else: a balance can reach zero because every
holder was served, *or* because something upstream went wrong and the fold is
reading an empty ledger.

`mayClose()` now requires both — nothing outstanding **and**
`obligationsCompleted: true` — so somebody has to assert that the wind-down
happened rather than the system inferring it from an absence.

### What a winding-down programme must show

`windDownDisclosure()` assembles Decision G's five items, because a wind-down
is exactly when nobody has time to design a screen carefully: outstanding
points, the options with real availability, deadlines, successor options, and
the buyback **mechanism**.

**No money anywhere in it.** G is explicit that no cessation rule creates a
universal cash value, and a wind-down is precisely the moment somebody reaches
for a per-point figure. `cashEquivalent: null`, and the whole object is checked
to contain no `$`.

Deadlines are stated honestly: `periodMonths` is unset, and *null* is different
from *no deadline*, so the disclosure says which.

---

## `active` is not `mayIssue`

**The more consequential half of this decision.**

Reaching compliance `ACTIVE` used to turn issuance on by itself — so the last
rung of the ladder carried two decisions at once, and somebody completing a
compliance review would have enabled a shop.

They are now separate conditions and **both** must hold:

| | |
|---|---|
| the compliance ladder | says the programme **may** operate |
| `issuanceEnabled` | says it **is** issuing — a distinct act requiring the operational readiness the ladder does not test |

```
compliance ACTIVE alone       → mayIssue: false
issuanceEnabled alone         → mayIssue: false
both                          → mayIssue: true
```

`issuanceEnabled` alone is as inert as `status: 'active'` was, and for the same
reason: **one flag must never be the whole gate.**

### A bug this immediately caused, and the check that caught it

`stateOf()` read the compliance state alone. The moment issuance gained a second
condition the two disagreed, and the ledger produced a genuinely absurd refusal:

> program X is ACTIVE_PROGRAM. Points may only be issued under an
> ACTIVE_PROGRAM.

A product state that contradicts the gate it describes is worse than no product
state. `stateOf()` now derives from `mayIssue()`, so they cannot disagree again.

### "Can we ship?" is a function now

The register drifted because readiness was answered by *reading prose*.
`readiness(programId)` answers it from the programme — ladder position,
`issuanceEnabled`, and precisely what is unset — and **deliberately does not
consult `status`**, since a readiness function that read it would re-create the
confusion the ladder was built to end.

```
AFK-TP-2026.1 → ready: false, 3 blockers
  1. compliance is DRAFT; issuance requires PILOT or ACTIVE
  2. unset before activation: maxProgrammeExposure
  3. issuanceEnabled is not true
```

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
| G-settlement | The economic architecture for cessation is settled — no silent extinction, and a four-rung fall-through. What the *legal* settlement mechanism is, where continued travel redemption is no longer reasonably available, is counsel's and must not become a universal cash value. | counsel |
| G-reasonable | What is a "reasonable" wind-down period, and reasonable by whose measure? `periodMonths` is unset and the disclosure says so rather than implying no deadline. | counsel + commercial |
| G-enable | Who may set `issuanceEnabled`, and what operational readiness must be evidenced first? The ladder tests legal and accounting; this tests neither. | operations + counsel |
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
