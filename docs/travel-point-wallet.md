# Item Z — the authenticated Travel Wallet

**ARCHITECTURE BUILT. Nothing wired.** No issuance, no Stripe, no database, no
production wallet, no live transfer or buyback. `AFK-TP-2026.1` reports **four
unmet conditions**.

> Planning does not require an account. Ownership of Travel Points does.

---

## The architecture

```
                    AFRINKONG
               Wankong LLC trade name
                         │
          ┌──────────────┴──────────────┐
          │                             │
      PLANNING                       OWNERSHIP
          │                             │
          ▼                             ▼
   Anonymous Visitor             Authenticated User
          │                             │
          ▼                             ▼
    Journey Planner               Customer Account
          │                             │
          ▼                             ▼
     Travel Goal                  Travel Wallet
          │                             │
          │                             ▼
          │                       Point Ledger
          │                             │
          │                    ┌────────┼────────┐
          │                    ▼        ▼        ▼
          │                 Purchase Transfer Redemption
          │
          └──────────────► Journey
                              │
                              ▼
                       Eligible Travel
                              │
                              ▼
                         Reservation
                              │
                              ▼
                          Redemption
```

And beside it, never inside it:

```
                 PAYMENT SYSTEM
                      │
                    Stripe
                      │
                      ▼
               Payment settlement
                      │
                      ▼
                Economic event
                      │
                      ▼
                 Point Ledger
```

> **Stripe never becomes the wallet. The wallet never becomes the ledger. The
> ledger never becomes a bank account.**

---

## Three layers, three questions

| layer | answers |
|---|---|
| **account** | who is this person? |
| **wallet** | what entitlements do they currently hold? |
| **ledger** | why does the wallet contain those entitlements? |

The arrow points one way. The wallet is **derived** and never a source of
truth — `account.wallet()` takes ledger entries as input and stores nothing, so
there is no figure that can drift.

---

## The boundary, as a list rather than a convention

Anonymous, forever: `EXPLORE` · `PRICE_JOURNEY` · `CREATE_GOAL`

Requires an account: `VIEW_POINTS` · `VIEW_LEDGER` · `BUY_POINTS` ·
`RESERVE_JOURNEY` · `TRANSFER_POINTS` · `REQUEST_BUYBACK` · `CHANGE_IDENTITY` ·
`CHANGE_PAYOUT`

`requiresAccount()` is data, not prose, because the failure mode is somebody
putting a sign-in wall in front of the product's front door and nothing
noticing. An **unknown** action requires an account — fails closed, so a new
action must be classified deliberately rather than inherit permission.

---

## The security table, enforced

| action | level |
|---|---|
| view points · view ledger | normal authentication |
| create a Travel Goal | **none — planning is not ownership** |
| buy points | authentication + risk decision |
| reserve a journey | authentication + entitlement check |
| transfer · request buyback | **step-up** |
| change identity · change payout | **step-up** |

`auth` and `stepUp` are separate inputs precisely so that **having a session
does not imply having authority**. All four step-up actions are refused on a
fully authenticated session:

> this action requires step-up verification; a session alone is not authority
> to move economic entitlement

A risk-gated action with **no verdict supplied** is refused — the same rule
`risk.js` applies, because forgetting to consult risk must fail closed in both
modules or it fails closed in neither.

### A restricted account may still look

Viewing stays available throughout a restriction. Being unable to see what you
hold while under review is a second injury, and the points are restricted, not
removed — the customer is told exactly that.

---

## The wallet

```
Available        4,250 TP
Reserved         2,000 TP
Total held       6,250 TP
Pending            500 TP
Restricted           0 TP
```

**Pending sits beside the balance, never inside it.** 4,250 + 2,000 = 6,250
held; the 500 pending are excluded, because B6 says nothing is issued before
settlement. *"I paid, where are my points"* is a fair question and this is the
honest answer to it — previously the fold merely skipped unsettled purchases
and the customer saw nothing at all.

**Restriction comes from the account, not the ledger.** A restriction is a fact
about a person under review, not a movement of points; inventing a ledger kind
for it would have broken B7's closed set of eleven for something that is not an
economic event.

`cashEquivalent: null`, and the wording comes from `holdingDisplay()` — Decision
I, restated at the surface most likely to break it.

---

## Recovery is an economic-control problem

*"We'll reset the account"* is a sentence that can move thousands of points to
whoever asked most convincingly.

| holding | tier | requires |
|---|---|---|
| ≤ 1,000 TP | LOW | contact verification |
| ≤ 10,000 TP | STANDARD | + identity verification |
| above | HIGH | + manual review, cooling-off period |

Stated in advance so the answer is the same every time, rather than argued case
by case at the moment somebody is upset.

And the distinction that stops a well-meaning agent being helpful in the wrong
direction:

> Recovery restores access to an account. It does not by itself restore
> authority to move Travel Points out of it.

Restoring authority additionally requires step-up and a restriction period
before transfer or buyback.

---

## There is no admin edit balance — and this found a real gap

The rule is absolute, and the gap was exactly the class this model keeps
producing: **two things that had to agree, and nothing compared them.**

`tools/points/schema.sql` has required `approved_by` on an adjustment since it
was written — `adjustment_needs_approval`. **The module did not.** So:

```js
{ kind: 'ADJUST_UP', quantity: 2000 }   // no approver, no reason
→ folded cleanly, created 2,000 points
```

…in the browser and in every test. The schema's own comment said *"an ADJUST
that nobody signed is indistinguishable from a bug that minted points"*, and
that was true of the code that actually runs.

`fold()` now refuses an administrative entry that names no approver, and one
that gives no reason. What an administrator gets instead of an edit is a
**proposed entry**:

```
ADJUST_UP  +2,000 TP
  approvedBy  ops-jane
  reason      goodwill, ticket 4471
  reference   SUP-4471
```

> This is an entry, not an edit. Nothing earlier changes.

### And it caught `reversal()` too

`reversal()` returned `approvedBy: null` with a comment saying *"the caller
supplies it"* — and nothing made them. The moment the fold became strict, every
reversal produced an entry the ledger would not accept. It now requires an
approver and refuses without one. A chargeback reversal nobody signed is
precisely what the rule guards against.

---

## UNRESOLVED

| | question | owner |
|---|---|---|
| Z-auth | What authentication mechanism — passkeys, email link, password + TOTP? Step-up must be something a session-holder cannot produce (Y-stepup). | security |
| Z-migration | A visitor with a browser-local plan creates an account. Does the plan move, and what happens if two devices hold different plans? | product |
| Z-closure | What does closing an account do to outstanding points? Not expiry (D), not cessation (G) — the customer leaving voluntarily while still holding entitlement. | product + ⚖ |
| Z-visibility | How much ledger detail does a customer see? The full history is the audit trail; it is also a list of everything they have ever done. | product |
| Z-restriction | Who may restrict an account, on what grounds, and for how long? An indefinite silent restriction is its own harm. | operations + ⚖ |

---

## What this did **not** do

- No account exists, no session exists, no database exists.
- No point can be issued: `readiness('AFK-TP-2026.1')` reports four unmet
  conditions and `mayIssue` is false.
- No Stripe, no payment flow, no customer money, no live transfer or buyback.
- No stored balance was created anywhere — the wallet remains a function of the
  ledger.
