# Decision D — expiry, programme duration, and unused Travel Points

**SETTLED as canonical.** Eleven rules, each backed by a named check in
`tools/points-checks.js`. `AFK-TP-2026.1` remains `compliance: DRAFT`.

> You are not putting money into an Afrinkong account. You are acquiring Travel
> Points under a defined programme and building an entitlement toward a
> journey. The programme remains responsible for honouring the terms attached
> to those points.

---

## Numbering

There is an earlier Section D — the legal and compliance boundary, in
`travel-point-compliance.md` — and a second one covering redemption inside
`travel-point-purchase.md`. This is **Decision D**, the third and canonical
use of the letter, and it is about duration. All three are kept; the routing
table in `CLAUDE.md` points at the right one.

---

## The eleven rules, audited

| | rule | enforced by | |
|---|---|---|---|
| D1 | Every point belongs permanently to a named programme | `fold()` refuses **any** entry without `programVersion` | ⚠️ **gap closed** |
| D2 | No short arbitrary expiry on purchased points | `expiry.purchased: null` — never, not unset | ✅ |
| D3 | Active → Closed → Run-off | four-state ladder, redemption alive for three of them | ✅ |
| D4 | Closing does not cancel existing entitlements | `CLOSED` refused while anything is outstanding | ⚠️ **gap closed** |
| D5 | Points stay governed by their issuing programme | immutable versioned programmes, deep-frozen | ✅ |
| D6 | An orderly alternative when the service disappears | `remedies()` — ranked, and erasure is not in the list | ⚠️ **new** |
| D7 | Promotional points may have separate, **disclosed** expiry | `expiryDisclosure()` — sentences, not arithmetic | ⚠️ **new** |
| D8 | Earliest expiry consumed first | `consumptionOrder()` derived from programme terms | ⚠️ **behaviour changed** |
| D9 | Purchased-point terms cannot change retroactively | `deepFreeze()`; a new programme is a new programme | ✅ |
| D10 | Inactivity does not make points disappear | there is no clock in the module at all | ✅ |
| D11 | Reaching a goal is *funded*, not a balance | `journeyState: 'FUNDED'`, `"Journey funded"` | ⚠️ **new** |

---

## D8 — the rule that was quietly a different rule

**This is the one that changed behaviour, and it is worth reading carefully.**

The fold spent the promotional pool first, unconditionally, with a comment
saying promotional points *"are the ones that expire… so spending them first
is the treatment that costs the customer least."*

Under `AFK-TP-2026.1` that **is** earliest-expiry-first: purchased points never
lapse, promotional ones lapse at 24 months. The two rules agree on every
programme that exists — which is exactly why the difference was invisible.

They stop agreeing the moment a programme gives purchased points a *shorter*
validity than promotional ones:

| programme | purchased | promotional | old rule spends | D8 spends |
|---|---|---|---|---|
| `AFK-TP-2026.1` | never | 24 months | promotional first | promotional first ✅ same |
| inverted | 12 months | 36 months | **promotional first** ✗ | **purchased first** ✅ |

Under the old rule the inverted programme would burn the *longer-lived* points
and let the shorter-lived ones lapse — costing the customer points they had
paid for. The order is now derived from the programme's own validity terms.

Still clock-free: it compares validity in **months**, not dates, so no balance
can move because time passed. `null` sorts last, which is the whole of D2.

**The tie-break is stated rather than incidental.** When neither pool lapses,
promotional still goes first — it is the pool that cannot be repurchased (E7)
and is forfeited on cancellation, so spending it first still costs the customer
least.

### This answers a long-open question

**B-ii** — *"on redemption, which lot is consumed first?"* — has been open since
Section B. Decision D answers its purchased-versus-promotional dimension:
earliest expiry first. The *programme* and *currency* dimensions of B-ii remain
open.

---

## D1 — the programme travels with the points, for their whole life

**Gap closed.** Issuance already required a programme. A `RESERVE`, `REDEEM` or
`BUYBACK` did not — so points could *move* without naming the terms they moved
under, while D5 says the terms are attached for the whole of their life rather
than only at the moment of creation.

`fold()` now refuses any entry without `programVersion`, whatever its kind.

---

## D4 — closure is never confiscation

**Gap closed, and this is the strongest rule in Decision D.**

The run-off ladder existed. Nothing stopped a programme walking all the way to
`CLOSED` — the one state where points can be neither redeemed nor bought back —
while customers still held points. The rule was a promise in a document.

```
ACTIVE                    sells, redeems
CLOSED_TO_NEW_PURCHASES   stops selling, still redeems
REDEMPTION_PERIOD         run-off; still redeems
CLOSED                    redeems nothing  ← now gated
```

`mayClose()` refuses `CLOSED` while anything is outstanding, and **refuses an
unstated balance too** — it cannot be assumed to be zero. Somebody has to state
the number, which is the point: closing a programme becomes an act with a
figure attached to it.

A customer's 4,500 TP under Programme 2026-A remain 4,500 TP under Programme
2026-A. Launching 2027-B does nothing to them.

---

## D6 — when the journey disappears

The hard case, and the one where **doing nothing is itself the failure**.
`remedies()` returns an ordered list of what is actually available:

| rank | remedy | condition |
|---|---|---|
| 1 | equivalent travel | a comparable eligible journey exists |
| 2 | another eligible service | anything still in programme scope |
| 3 | programme buyback | the programme offers it *and* is in a state that permits it |

Erasing the points is not in the list at any rank, and the return value says so
in a field: `neverAnOption`.

If the list would be empty, that is reported as `exhausted: true` — **a human
decision, explicitly not a lapse**. Under the draft programme the list is
just `["alternative"]`, because a draft programme cannot quote a repurchase;
the hierarchy shrinks rather than offering something that cannot happen.

---

## D7 — the customer never has to guess

`expiryDisclosure()` returns the two pools separately, each as a sentence:

> 5,000 TP purchased. These do not expire.
> 500 TP acquired as a promotional grant, valid for 24 months from issue.

plus the spend order in words —

> Points that expire soonest are used first, so nothing lapses that could have
> been spent.

— and the inactivity line, so no surface can imply the opposite by omission:

> Purchased Travel Points are not affected by how long you go without using
> your account.

A wallet that says *5,500 TP* with a footnote is exactly the guess D7 forbids.

---

## D9/D5 — no retroactive expiry, proved rather than promised

A 2027 programme with six-month expiry leaves 2026 points at `null`. The frozen
terms refuse the write directly — `PROGRAMS['AFK-TP-2026.1'].expiry.purchased =
6` does not take. This is what programme immutability was for; D9 is the case
it was built to survive.

---

## D11 — funded, not a balance

Reaching the target is a **journey state**, not an account figure:

```
PLANNING → FUNDED → BOOKING → RESERVED → TRAVELLING → COMPLETED
```

At 4,800 of 4,800 the goal reads **"Journey funded"** and `journeyState`
becomes `FUNDED`. It never reads *"Account balance: $4,800"*.

This is the moment a customer is most likely to read their holding as money —
they have just watched a number reach a round figure — so the word is chosen so
that the next thing they do is book rather than withdraw. Checked: no display
field on a funded goal contains "balance" or "account".

### But nothing can reach it on the site today, and that is worth stating

`scripts/fund.js` calls `G.build(total, months, 0, …)` — **`recorded` is
hard-coded to 0** — and `readRecorded()` is exported but called from nowhere.
So progress on the Journey Fund panel is always 0%, and `FUNDED` can never
render. The state exists in the module and has no route to a screen.

That gap predates Decision D and closing it is a product change rather than an
economic one: it means giving a reader somewhere to record what they have set
aside, which is a holding-shaped surface and needs D11's and F4's vocabulary
rules applied to it deliberately. **Not built here.** Recorded as
**D-goalinput**.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| D-runoff | How long is a run-off period, and what triggers the move from `CLOSED_TO_NEW_PURCHASES` to `REDEMPTION_PERIOD`? | counsel + commercial |
| D-outstanding | D4 forbids closing with points outstanding. What if points remain outstanding *indefinitely* — a customer who never returns? Escheatment/unclaimed-property law may compel a treatment the programme cannot choose. | counsel |
| D-equivalent | What makes a journey "reasonably comparable" for D6 rank 1, and who decides — is a 7-day Kenya signature equivalent to a 7-day Tanzania signature? | commercial |
| D-liability | Purchased points that never expire are a liability with no end date. What is the accounting treatment, and does breakage recognition become impossible? | accounting |
| D-promoexpiry | Is 24 months the right promotional validity, and must the expiry date be shown per grant rather than as a duration? D7 shows months; a date needs an issuance date. | commercial + counsel |
| D-goalinput | The Journey Fund passes `recorded: 0`, so `FUNDED` can never render. Giving a reader somewhere to record what they have set aside is a holding-shaped surface and needs D11/F4 applied deliberately. | product |

Everything open in `travel-point-exit.md` (C-…), `travel-point-issuance.md`
(B-…), `travel-point-pricing.md` (F-…) and `travel-point-buyback.md` (E-…)
remains open. **B-ii is partly answered** — see D8.

---

## What this decision did **not** do

- No programme was activated.
- No point expired, and nothing acquired a clock.
- No customer-facing surface gained a money figure.
- No legal conclusion was drawn about unclaimed property, breakage, or the
  accounting treatment of an open-ended liability.
