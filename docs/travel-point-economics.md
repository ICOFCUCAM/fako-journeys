# Section B — the Travel Point economic model

**Status — recorded 20 August 2026**

| | |
|---|---|
| B1 | **settled** as a product and economic decision |
| what B1 is not | **a legal opinion.** It does not determine the regulatory characterisation of the product. |
| before activation | counsel must confirm the characterisation. See §B1.3. |
| the programme | stays `draft`; `PRODUCT_STATE` stays `DRAFT_PROGRAM` |
| B2 onward | not yet written |

Section A defines *what a Travel Point is*. Section B defines *what happens
economically when somebody buys one*. B1 settles the first and most important
part of that: what the customer is actually buying.

---

## B1. What the customer is actually buying

**Settled.**

> A customer does not deposit money with Afrinkong. They purchase Travel Points
> issued under a specific Travel Point Programme.
>
> The money becomes company revenue or obligation according to the programme
> and the applicable accounting treatment. The customer's Travel Points are not
> a bank balance.
>
> **A point cannot be withdrawn as cash merely because the customer owns it.**

### The transaction

    customer
       │  pays
       ▼
    Wankong LLC                      ← the legal entity receives the payment
       │  issues
       ▼
    Travel Points                    ← under a named programme, on its terms
       │  held by
       ▼
    customer                         ← holds travel entitlement, not a balance

Three parties are absent from that diagram on purpose. There is no account
holding the customer's money. There is no custodian. There is no obligation to
return cash on demand.

### What B1 settles

**Ownership does not imply withdrawal.** This is the sentence that separates
this product from a deposit. A customer who holds 10,000 Travel Points holds a
right to Afrinkong travel; they do not hold $10,000 that Afrinkong is keeping
for them. Any buyback that exists is a **separate, bounded, programme-defined
offer** — not a property of ownership. (Section A1c: whether that offer is
"90% of what your points are worth" or "90% of what you paid for the ones you
haven't used" is still open, and the second needs no valuation of a point at
all.)

**The money is the company's on receipt.** Subject to accounting treatment,
which is a determination for the accountant and not settled here — see A5.13.
What is settled is that it is not held *for* the customer.

**The obligation is to provide travel.** Not to return money. That is what makes
this a travel product rather than a financial one, and it is the substance
behind every wording choice in Section A.

### B1.1 What this already means in the code

None of these is new; B1 ratifies them.

| commitment | where |
|---|---|
| no stored balance — every figure folded from an append-only ledger | `wallet()`, `tools/points/schema.sql:191` |
| no interest, no yield, no growth with time | absent by design, and its absence is asserted |
| buyback is a bounded programme offer, not a withdrawal | `buyback.minHoldDays`, `minPoints`, `maxPerYear`, `discretionary` |
| nothing may be issued under a non-active programme | `PRODUCT_STATE`, `fold()` throws |
| payment and issuance are two records with one reference | `payments` and `point_ledger` |

The last one matters more than it looks. Stripe is the payment rail and is not
the ledger; a reconciliation can ask "does every settled payment have exactly
one issuance, and vice versa" and get an answer. That is what makes the money
side auditable independently of the entitlement side — which is exactly the
separation B1 asserts.

### B1.2 What B1 does not settle

- **Accounting treatment.** Deferred revenue against a performance obligation,
  or a liability. A5.13. Owner: accountant.
- **When revenue is recognised.** At purchase, at reservation, or at travel.
  Follows from the above.
- **Tax point of supply.** A5.14.
- **What is owed if a programme is discontinued.** Decision 10.
- **Whether any of the money must be segregated.** Some characterisations
  require it. B1 asserts the money is not held *for* the customer; whether it
  must nonetheless be held *apart* is a regulatory question, not a product one.

### B1.3 The qualification, and why it has teeth

**B1 is a product and economic decision. It is not a legal opinion and does not
determine how a regulator will characterise this product.**

US regulators distinguish loyalty and reward arrangements from prepaid and
stored-value products. Certain features move an arrangement across that line
regardless of how its terms are drafted. Four of them are live here, and the
draft programme currently sits at the **higher-exposure end of every one**:

| feature | current setting | why it matters | where |
|---|---|---|---|
| **transferability** | `transferable: true` | A right that can be passed to a third party looks less like a loyalty benefit and more like an instrument. | programme |
| **cash redemption** | `buyback.offered: true` at `0.90` | The single feature most likely to change the characterisation. `discretionary: true` is the safer form and is what is encoded — a *contractual guarantee* would be materially different. | programme |
| **reloadability** | **not yet modelled** | Recurring monthly purchase plans are proposed in the brief. Repeated top-ups over time is a characteristic pattern of prepaid products. | absent from code and schema |
| **no expiry** | `expiryMonths: 0` | A claim that never lapses is a more durable obligation than a benefit that does. | programme |

That all four currently sit at the permissive end is a **drafting default, not a
decision**. Each is a single parameter. A first programme could plausibly be
non-transferable, non-reloadable, buyback-by-application-only and time-limited,
and be a much easier characterisation — at the cost of product features that
may matter commercially. That trade is a decision for the founder with counsel,
and it is not made here.

**Nothing in this repository may accept a customer payment until that
characterisation is confirmed.** The code enforces the gate rather than relying
on this paragraph: `PROGRAMS['AFK-TP-2026.1'].status` is `'draft'`, `fold()`
throws on any issuing entry under a non-active programme, and two test files
assert it.

---

## B2 onward

Not yet written. The remaining economic model — pricing, packages, recurring
purchase, the wallet, reservation and redemption mechanics, price protection —
follows once B1 is recorded and Section A's open questions (A1b, A1c) have
answers.

## Sign-off

| | |
|---|---|
| B1 settled by | |
| date | |
| counsel engaged on §B1.3 | not yet |
| characterisation confirmed | **no — activation blocked until it is** |
