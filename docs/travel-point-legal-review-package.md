# Travel Point Programme — legal and compliance review package

**For:** counsel, and the accounting adviser where marked.
**Subject:** the Afrinkong Travel Point Programme, issued by Wankong LLC.
**Status of the product:** `compliance: DRAFT`, `issuanceEnabled: false`.
**No customer money has been accepted. No Travel Point exists.**

---

## How to use this document

The economic model is **built, tested and frozen**. This package exists so that
counsel is asked to rule on a *defined* product rather than to design one.

- **§1–§3** describe what has been decided and built. These are not questions.
- **§4** is the list of questions. Each is one counsel must answer before
  issuance; none is rhetorical.
- **§5** states what already blocks activation, in code.

Where an answer would change the architecture, that is said explicitly. Several
questions are load-bearing: a different answer means a different product, not a
different clause.

---

## 1 — The two entities, and why the distinction is load-bearing

| | |
|---|---|
| **Wankong LLC** | a Delaware limited liability company. **The legal entity.** It issues the Travel Point Programme, is the counterparty to every Travel Point, repurchases points where the programme permits, and carries every obligation arising from them. |
| **Afrinkong** | **a trade name of Wankong LLC.** The customer-facing travel brand. It arranges and delivers journeys. |

This is not branding hygiene. **A Travel Point is an obligation of Wankong LLC**,
and a customer must never be left believing their counterparty is a travel
brand rather than a company.

The distinction is carried in the programme record (`issuer: 'Wankong LLC'`,
`brand: 'Afrinkong'`) and in the customer-facing text. It was **wrong in one
place** and has been corrected: the repurchase quote read *"Afrinkong may
repurchase these points"*, and repurchase is a financial act by the issuer.

---

## 2 — What a Travel Point is

> One unit of **travel purchasing entitlement**, issued under a specific,
> versioned Travel Point Programme.

**It is not, and the architecture prevents it becoming:**

| not | how that is enforced |
|---|---|
| currency | no cash value is displayed anywhere; `MONEY_MOMENTS` is a closed list of three, none attached to a holding |
| a bank balance | the wallet is a *view* derived from an append-only ledger; there is no stored balance to edit |
| an investment | no interest, yield, APR, APY, dividend, accrual or appreciation — scanned as vocabulary across seven customer-facing files |
| subject to time-based growth | the module contains **no clock at all**; time cannot be an input to a balance |
| a general-purpose credit | redemption is limited to an explicit eligible-services list, with exclusions carrying their reasons |

**Indivisible.** Whole units only; the ledger refuses a fractional quantity.
Rounding is half-up with a single documented exception (journey requirements
round up, because a customer fractionally short cannot travel).

**Programme-bound.** Terms attach at issuance and are immutable. A 2027
programme with different terms does not touch a 2026 point. Enforced by a
deep-freeze in the module and an UPDATE-refusing trigger in the schema.

---

## 3 — What happens to customer money

```
Customer  →  payment rail  →  settlement  →  economic event  →  point ledger
                                                                     │
                                                            travel entitlement
```

**Payment ≠ points.** Two systems, two records, one reference between them:

- the payment system records **money movement**;
- the ledger records **economic events** and holds no money field at all.

**Issuance happens only after settlement.** Seven payment states; exactly one
issues. `authorised` is named explicitly because it is the state that *looks*
finished — the bank has agreed to pay and has not paid, and an authorisation
can be withdrawn.

Enforced twice: the issuance builder refuses an unsettled payment, and the fold
independently refuses an entry marked settled whose payment is not.

**Wankong LLC does not represent Travel Points as a deposit**, and the schema
deliberately contains no noun that would let anybody later argue it did — no
`balance` column, no `interest`, no `maturity`, no `accounts` in the banking
sense.

---

## 4 — The questions counsel must answer

### A — Regulatory characterisation *(the gate)*

1. Are Travel Points **stored value**?
2. Are they **prepaid access** under FinCEN's rules?
3. Could issuing or repurchasing them constitute **money transmission**,
   federally or in any state where Wankong LLC would sell?
4. Could they constitute a **gift card or prepaid product** under CARD Act
   rules or state equivalents?
5. Does the **repurchase mechanism** change the classification?
6. Does **transferability** change the classification?
7. Does **geographic scope** change it — customers outside the United States,
   and travel delivered in African jurisdictions?

**Four structures remain reachable** and the architecture keeps all four open,
which is why programme terms are versioned data rather than constants:
Afrinkong travel credit · Travel Points as built · membership/benefit ·
a licensed financial partner holding the money.

> **The customer experience is close to identical across all four. The legal
> character is not.**

---

### B — Repurchase ("buyback")

8. Is a repurchase offer at a **programme-defined discount** legally
   permissible in the jurisdictions concerned?
9. Should it remain **discretionary**? The programme currently says
   `discretionary: true` and the quote tells the customer it is *"an offer
   under the terms of this programme, not a guaranteed right of redemption."*
10. **Does publishing a discretionary offer in programme terms create a
    redemption right in substance regardless of that wording?** This is the
    single question most likely to change the classification.
11. What **consumer-protection obligations** arise from offering it at all?
12. What happens to points once repurchased — extinguished, or returned to
    programme inventory?

**Currently modelled:** 90% of purchase consideration, `minHoldDays: 90`,
`minPoints: 100`, `maxPerYear: 5,000`, promotional points excluded, reserved
points excluded, refused inside a journey's final window. **The *basis* is a
programme term, not a definition** — and a rail caps any quote at what the
customer actually paid, under every basis.

---

### C — Transferability *(a standing blocker)*

13. **Can transferable Travel Points lawfully be offered under this
    structure?**

Decision E retains transferability: gift, family pooling, corporate gift and
estate transfer, with identified parties on both ends, no sale, no secondary
market, and conservation of supply.

This is **already a hard blocker in code**. `transferabilityLegallyConfirmed`
is `false`, and a transferable programme cannot reach issuance until it is
true. A non-transferable programme is unaffected, so the gate bites exactly
where the exposure is.

14. What **identity verification** does a *recipient* require — somebody who
    may not be a customer at all until the moment they receive points?
15. Is a **gift** a taxable event for either party, and does the answer differ
    for a corporate gift?
16. Does an unredeemed holding form part of an **estate**?

---

### D — Cancellation

Bands as implemented, attaching to the **booking** and never to the wallet:

| days to departure | released | repurchase eligible |
|---|---|---|
| 31+ | 100% | yes |
| 8–30 | 50% *(placeholder — tied to actual supplier cost)* | no |
| 0–7 | 0% | no |

17. Are these bands permissible, and is the final-week restriction on
    repurchase and transfer enforceable?
18. Must forfeiture inside seven days be characterised as a **cancellation
    charge** rather than as a loss of entitlement?
19. What **disclosures** are required, and at what moment — at purchase, at
    booking, or both?

---

### E — Expiry

**The economic rule is decided.** Purchased points do **not** expire from the
passage of time. Promotional grants expire at 24 months. Inactivity does
nothing. This programme did **not** reserve a right to introduce expiry later.

20. Is that treatment **permissible** in every jurisdiction concerned — and is
    it *required* anywhere? Several US states regulate expiry under
    unclaimed-property and gift-card law, and some prohibit it outright.
21. Purchased points that never expire are a **liability with no end date.**
    Does that create an obligation the company must provide against, and does
    it make breakage recognition impossible? *(also §H)*
22. If points remain outstanding indefinitely, does **unclaimed-property law**
    compel a treatment the programme cannot choose?

---

### F — Cessation and wind-down

23. What obligation exists toward outstanding points if Wankong LLC stops
    offering eligible travel?
24. Must there be a **wind-down or redemption period**, and of what length?
25. What happens if the **company ceases entirely**?

**The economic architecture is settled: no silent extinction.** Closure cannot
by itself extinguish points, a programme cannot reach a terminal state while
anything is outstanding or before its obligations are recorded as performed,
and the wind-down hierarchy is redeem → alternative eligible service →
migration to a named successor → repurchase. Erasure appears at no rank.

A programme that has ceased providing travel reports redemption as
*permitted but unavailable* and falls through to repurchase.

26. **No cessation rule creates a universal cash value for a Travel Point.**
    Is that sustainable, or does an insolvency scenario force a monetary
    valuation the product otherwise refuses to state?

---

### G — Customer protection

27. What **disclosures** are required before purchase, and which must be
    acknowledged rather than merely available?
28. What **refund and cancellation rights** attach to a purchase of points, as
    distinct from a booking?
29. What **complaint handling** is required?
30. How must **dormant balances** be treated?
31. What **geographic restrictions** should apply to who may buy?
32. If a customer receives a statement or tax document, must it state a
    **monetary value** — and would that be the cash equivalent the product
    otherwise forbids, arriving by regulatory obligation?

---

### H — Accounting and tax *(accounting adviser)*

33. When is **revenue recognised** — at issuance, at redemption, or at travel?
34. How are **outstanding points** carried?
35. How are **forfeited** points treated?
36. How is a **repurchase** treated — derecognition, liability settlement, or
    contra-issuance?
37. Is **breakage** recognisable given that purchased points do not expire?
38. What is the **accounting currency**, and how are other collection
    currencies handled?
39. What is the **tax point of supply** — where the customer is, where Wankong
    LLC is, or where the travel occurs?
40. Is a point issued under a better *rate* recognised differently from one
    issued at the standard rate plus a *grant*? The customer's position is
    identical; the accounting may not be.

---

### I — Fraud, chargebacks and recovery

41. **Chargeback after redemption.** The customer travelled. The ledger does
    not erase the redemption; it records a liability. Is that treatment
    sound, and how may the debt be pursued?
42. What obligations arise on a **stolen payment instrument** where points were
    issued and spent?
43. What must be done on **account takeover**?
44. What identity assurance is required before a **repurchase pays out**?
45. Can a repurchase already settled be **clawed back** if the original
    purchase is later charged back?
46. What **recovery** requirements are lawful for a customer locked out of a
    high-value holding?

---

## 5 — What has already been decided, and should not be re-opened

Counsel is asked to rule on these, not to redesign them.

| area | current architecture |
|---|---|
| definition | travel purchasing entitlement |
| currency equivalence | **no** |
| interest / yield / growth | **none, and no clock exists** |
| balance model | derived from an immutable ledger |
| payment vs points | separate systems, joined by a reference |
| programme terms | versioned and immutable |
| transferability | **yes, retained** — sale and secondary market forbidden |
| transfer legal confirmation | **required before activation** |
| repurchase | discretionary, 90% concept, legal confirmation required |
| cancellation | banded model, implemented |
| final-week restriction | **yes** — no repurchase, no transfer |
| expiry | purchased never; promotional 24 months |
| rounding | half-up, one documented exception |
| fraud | fail-closed architecture; absent signals hold |
| chargeback | does not erase historical redemption |
| authenticated wallet | designed, not wired |
| planning without an account | **remains available** |
| issuance | **OFF** |
| programme | **DRAFT / non-issuing** |

---

## 6 — The hard blocker

> **No customer money may be accepted for Travel Points, and no Travel Point
> may be issued, until the legal and compliance questions in §4 have been
> resolved and the programme has passed the activation readiness gate.**

This does not rely on anybody remembering a variable. `readiness('AFK-TP-2026.1')`
currently reports **four unmet conditions**:

1. compliance is `DRAFT`; issuance requires `PILOT` or `ACTIVE`
2. `maxProgrammeExposure` is unset
3. `issuanceEnabled` is not true
4. transferability has not been confirmed in legal review

The ladder — `DRAFT → LEGAL_REVIEW → ACCOUNTING_REVIEW → APPROVED → PILOT →
ACTIVE` — cannot be skipped, and reaching `ACTIVE` still does not start
issuance: that is a separate act.

**Three earlier attempts to guard this with a single flag all failed**, which
is why the gate has this shape. `status: 'active'` is inert. Compliance
`ACTIVE` alone is inert. `issuanceEnabled` alone is inert. One flag is never
the whole gate.

---

## 7 — Where the detail lives

| question area | document |
|---|---|
| the whole model, indexed | `travel-point-decisions.md` |
| every item's status | `travel-point-matrix.md` |
| what a point is | `travel-point-definition.md` |
| issuance and settlement | `travel-point-issuance.md` |
| repurchase | `travel-point-buyback.md`, `travel-point-exit.md` |
| expiry and duration | `travel-point-duration.md` |
| transferability | `travel-point-transfer.md` |
| redemption scope | `travel-point-redemption.md` |
| price changes, cessation | `travel-point-continuity.md` |
| cash-equivalent display | `travel-point-display.md` |
| fraud and risk | `travel-point-risk.md` |
| accounts and the wallet | `travel-point-wallet.md` |
| the compliance ladder | `travel-point-compliance.md` |

Roughly forty further recorded questions sit in those documents under their own
identifiers. **This package is the subset that blocks activation.**
