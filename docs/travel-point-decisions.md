# The Travel Point economy — canonical index

**Start here.** This is the entry point for anything economic, in the order the
model is actually built:

```
Travel Point Definition  →  Economic Decisions  →  Programme State  →  Implementation
```

Not `CLAUDE.md` → scattered decisions → code. `CLAUDE.md` is working notes for
the *repository*; this is the source for the *product*.

**Current state: `compliance: DRAFT`, `issuanceEnabled: false`.** Nothing has
been issued and nothing can be. Ask `readiness('AFK-TP-2026.1')` rather than
reading prose.

---

## 1 — Travel Point Definition

> A Travel Point is one unit of Afrinkong travel purchasing entitlement, issued
> under a named programme. It is not currency, not a deposit, and has no cash
> value.

| | |
|---|---|
| **`travel-point-definition.md`** | Section A. The *frame* — issuer, programme-bound, travel-only, non-monetary, indivisible — is ready for sign-off. The **unit basis** is open and blocked on the repurchase basis. |

Everything below inherits this. If it changes, all of it is reopened.

---

## 2 — Economic Decisions

Nine canonical decisions. Each has one home; where a decision **reversed** an
earlier one, the reversal is recorded in place rather than overwritten.

| | decision | settled | canonical document |
|---|---|---|---|
| **A** | what a Travel Point is | frame ✅ · basis open | `travel-point-definition.md` |
| **B** | how money becomes points | ✅ nine rules | `travel-point-issuance.md` |
| **C** | what happens when a customer leaves | ✅ ten rules | `travel-point-exit.md` |
| **D** | expiry, duration, unused points | ✅ eleven rules | `travel-point-duration.md` |
| **E** | gifting, inheritance, transferability | ✅ twelve rules | `travel-point-transfer.md` |
| **F** | what a point can buy | ✅ | `travel-point-redemption.md` |
| **F′** | price changes | ✅ | `travel-point-continuity.md` |
| **G** | discontinuation **and cessation** | ✅ in principle; legal terms required | `travel-point-continuity.md` |
| **H** | redemption scope | ✅ — restates and **tightens** F | `travel-point-continuity.md` |
| **I** | cash-equivalent display | ✅ | `travel-point-display.md` |

### The letters collide, and pretending otherwise is how documents drift

Two numbering schemes ran in parallel and both are kept:

- **Sections A–F** — the *working record* of how each answer was reached,
  including the arguments that were rejected.
- **Decisions A–I** — the *canonical statements*.

`F` is used twice: **F** settled what a point can buy, and **F′** settled price
changes. **H** later restated redemption scope and changed two things about it.
Where they disagree, the later decision wins and says so.

| working record | covers |
|---|---|
| `travel-point-economics.md` | Section B, B1–B25 — the economics as argued |
| `travel-point-purchase.md` | Section C — the purchase model |
| `travel-point-compliance.md` | Section D — the legal boundary and the ladder |
| `travel-point-buyback.md` | Section E — repurchase, and the B12/E2 reconciliation |
| `travel-point-pricing.md` | Section F — one rate per programme |

### The reversals, in one place

A decision that changed an earlier one is the thing a reader most needs to find:

| what changed | from → to | where |
|---|---|---|
| transferability | `false` → `true` (sale still forbidden) | E |
| lot consumption | promotional-first → **earliest-expiry-first** | D8 |
| government charges | out → in → **includable, not included** | audit → F → H |
| repurchase basis | fixed to consideration → **a programme term** with a consideration *cap* | B12 → E2 |
| mixed settlement | `permitted` → `permitted && mechanism != null` | H |
| the activation gate | `status` → `compliance` → **`compliance` AND `issuanceEnabled`** | D → G |

---

## 3 — Programme State

The economic decisions are inert until a programme carries them, and a
programme cannot issue until two independent conditions hold.

```
DRAFT → LEGAL_REVIEW → ACCOUNTING_REVIEW → APPROVED → PILOT → ACTIVE
                                                      └── may operate
                        issuanceEnabled: true ────────────┴── is issuing
```

**Neither alone is sufficient.** `status: 'active'` is inert; compliance
`ACTIVE` alone is inert; `issuanceEnabled` alone is inert. One flag is never
the whole gate — that lesson cost two corrections and is the reason the gate
has this shape.

Wind-down runs the same ladder in reverse, and closure is not confiscation:

```
ACTIVE → CLOSED_TO_NEW_PURCHASES → REDEMPTION_PERIOD → CLOSED
         (issuance stops)          (run-off)           (obligations performed)
```

| ask | function |
|---|---|
| can this programme issue? | `readiness(programId)` |
| may it reach the next rung? | `mayTransition(id, to, {outstanding})` |
| what happens if it closes? | `windDown(id)` · `windDownDisclosure(id, outstanding)` |
| may it terminate? | `mayClose(id, outstanding)` |

`readiness()` deliberately never consults `status`.

---

## 4 — Implementation

| module | holds |
|---|---|
| `scripts/points-ledger.js` | the programme terms, the fold, the gates. Every balance is derived; nothing is stored |
| `scripts/booking.js` | reserve → confirm → redeem, and the price lock |
| `scripts/buyback.js` | the five-step repurchase request; appends nothing |
| `scripts/transfer.js` | gift, family pool, corporate, estate; conservation of supply |
| `scripts/purchase-plan.js` | a plan is an intention, never a mandate |
| `scripts/journey-catalogue.js` | requirements and the component breakdown |
| `scripts/travel-goal.js` | the planning surface. Issues nothing |
| `scripts/risk.js` | item Y — the risk engine, holds, and the ledger gate. No model |
| `scripts/account.js` | item Z — account, wallet view, recovery tiers, admin adjustments. No session, no database |
| `tools/points/schema.sql` | append-only ledger, designed and **not applied anywhere** |
| `tools/points-checks.js` | 239 checks — the decisions above, asserted |

**None of it can issue a point.** Three independent refusals stand in the way:
the fold refuses issuance under a non-issuing programme, `mayActivate()`
refuses an incomplete programme, and `issuanceEnabled` is false.

---

## The current phase — legal review

**`travel-point-legal-review-package.md`** is the deliverable for counsel: what
Travel Points are, what happens to customer money, 46 numbered questions, and
what has already been decided and should not be re-opened.

    Define → Implement → Test → **Legal/Compliance Review** → Operational Controls → Activate

The engineering foundation is substantially complete. Further financial
functionality should wait for counsel's answers rather than be built because it
can be.

---

## The full coverage map

**`travel-point-matrix.md`** reconciles the complete A–AJ register against the
code: 24 items enforced, 4 with counsel, 8 genuinely open, and one conflict
(item N versus Decision E) that needs a word rather than a commit.

---

## What is still open

Roughly forty legal, accounting and commercial questions across the documents
above. The **gate** is question 11 in `economic-model-decisions.md` — the legal
structure before accepting customer money — and two decisions moved that
analysis toward higher exposure deliberately (E permitting transfer, F/H
admitting third-party charges).

The three that block the most:

| | question | why it blocks |
|---|---|---|
| **C-basis / E-c** | which repurchase basis `AFK-TP-2026.1` carries at activation | several downstream answers resolve once it lands |
| **G-enable** | who may set `issuanceEnabled`, on what evidence | the ladder tests legal and accounting; this tests neither, and nothing defines it |
| **question 11** | the legal structure | no money may be taken until it is answered |

---

## The rule that produced most of the bugs

Every defect this model surfaced had one shape: **two things that had to agree,
and nothing compared them.** `PROMOTION` in the module and not the schema. The
repurchase cap and the transferability flag. Promotional-first and
earliest-expiry. Two rate cards with two shapes for one field. `stateOf()` and
`mayIssue()`. This index and the code.

That last one is why `points-checks.js` now asserts that the documents and the
programme agree — including that this file lists every decision that exists.
