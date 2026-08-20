# Section D — the legal, regulatory and operational boundary

    D — APPROVED AS THE CONTROL FRAMEWORK
        NOT legally approved for customer-money activation

| | |
|---|---|
| the framework | approved, D1–D22 |
| the programme | `compliance: DRAFT` — see D20 |
| taking customer money | **blocked**, and now blocked by a ladder rather than a word |
| what counsel must answer | twelve questions, §D19 |
| permanent CI invariants | five, §D21, all live |

Section D does not decide whether Travel Points are inside or outside prepaid
and stored-value regulation. **It decides that we will not assume the answer**,
and it builds the controls that make waiting for one survivable.

---

## D1. What we are not claiming

We do not claim Travel Points are legally outside prepaid or stored-value
regulation. The product has characteristics that deserve formal review:
customers pay in advance, receive a digital entitlement, redeem it later, may
reload it with further purchases, may be offered repurchase, and the service is
travel-related and often international.

FinCEN's prepaid-access rules contemplate travel programmes and distinguish
closed-loop arrangements from broader ones. That does not make this product an
MSB. It means the characterisation is obtained, not assumed.

## D2/D5. Closed loop, and no external redemption

Travel Points are usable only toward eligible travel services from Wankong LLC
trading as Afrinkong, and — where legally appropriate — defined participating
travel providers. They are not general-purpose payment instruments, not
transferable money, not ATM-accessible, not customer-to-customer currency, not
a marketplace asset, not an investment, not a cash account.

A customer cannot ask for the cash, for a bank transfer, for credit elsewhere,
or to spend points anywhere. The redemption is Travel Points → eligible
Afrinkong travel. That is the product.

**Encoded:** `eligibleServices` lists what a point may be redeemed against;
`transferable: false` and `secondaryMarket: false` close D4.

## D3. The $2,000 question, which we are not designing around

FinCEN's closed-loop exclusion turns on maximum value associated with the
access vehicle on a day. Our product lets a customer accumulate over months,
which raises a question we cannot answer ourselves: **is the Travel Wallet one
access vehicle for this purpose?** If it is, unlimited accumulation may fall
outside the exclusion.

We are deliberately **not** setting a $2,000 product limit to manufacture an
exemption. `maxPerTransaction` and `maxPerCustomerPerYear` exist for the
commercial reason in C14 — bounded exposure — and their values are placeholders
that counsel may replace. Designing to a number we do not understand is how a
control becomes a fiction.

## D6. Repurchase is an offer, never a right

The 90% figure stays as the economic target. What changes is how it is
published:

> Afrinkong **may offer** repurchase of eligible Travel Points under the
> applicable Programme terms.

Not *"Afrinkong guarantees you can cash out at 90%"*. A published, unconditional
cash exit makes the product look considerably more like a prepaid instrument
with a redemption feature, and the features are what the analysis turns on.

**Encoded:** `buyback.discretionary: true`, and the quote's own note says it is
an offer rather than a right.

## D7/D8. What we say about money, corrected

Never *"save money with Afrinkong"*. The mental model of a savings account is
money deposited, held, returned. Ours is payment → travel entitlement → travel.

**And a correction this section forced.** `/journey-fund/how-it-works` said:

> *"Afrinkong does not hold it, does not receive it, does not touch it… That is
> not a temporary arrangement pending something better. It is what this is."*

True today, and **false the moment a Travel Point is sold** — Wankong LLC
necessarily receives the payment. The page claimed permanence for something the
roadmap contradicts. It now says that nothing on the planner moves money, that
Afrinkong does not operate a customer bank or deposit account and will not, and
that buying a Travel Point would be a purchase of entitlement rather than money
placed with us for safekeeping.

That is D8's precise formulation, and it is true before and after launch.

## D9/D10. Stripe settles money; it does not confer compliance

Stripe is the payment rail and the issuer of nothing. It answers *did the
customer pay*. Afrinkong's engine answers *what entitlement, if any, that
payment creates*.

Using Stripe does not make the model compliant — a processor can move money
while the underlying business still carries obligations. **Stripe integration
is downstream of legal classification**, which is why the economic model and
ledger were built first.

## D11. Consumer protection, assumed rather than hoped for

The CFPB has extensive rules for certain prepaid accounts — disclosures, error
resolution, protection against loss and theft. Whether they reach this product
is a legal question. We design as though records will be demanded: transaction
history, issuance records, programme terms, cancellations, redemptions,
refunds and repurchases, disputes, corrections, support history, and an
immutable economic history.

The append-only ledger already provides the last of those, and the others hang
off it.

## D12/D13. Accounting and tax are separate systems, and not ours to invent

The economic ledger answers *how many points does this customer hold*. The
accounting system answers *what does Wankong LLC owe or recognise*. These are
not the same question and must not be the same store.

    customer purchases 1,000 TP
        ├── payment record      $1,000
        ├── point ledger        +1,000 TP
        └── accounting event    deferred obligation / pending revenue

**The revenue-recognition treatment is the accountant's determination and is
not encoded.** Nothing in this repository asserts when revenue occurs. The
system records the facts — date, currency, amount, jurisdiction, programme,
points, redemption, cancellation, refund — and leaves the treatment to whoever
is qualified to decide it.

## D14. International customers

The programme must be able to restrict purchase and redemption by jurisdiction.
Recorded per customer and transaction: customer country, billing country,
currency, payment method, destination, programme, booking jurisdiction.

We do not assume a US company may sell one identical product everywhere.

## D15. Verification, proportionate and triggerable

An ordinary visitor planning a journey goes through no financial onboarding.
The architecture supports escalation — basic account, verified identity,
enhanced verification — triggered by purchase amount, cumulative exposure, a
repurchase request, fraud signals, a chargeback, jurisdiction, or a regulatory
requirement.

## D16/D17. Disputes and fraud: freeze, never delete

A chargeback must not delete points. The ledger is append-only and a dispute is
an event in it:

    +1,000 PURCHASE → PAYMENT DISPUTED → RESTRICTED
                    → resolution → reversal or restoration

And points do not become spendable because a webhook said *succeeded*:

    PURCHASE_PENDING → PAYMENT_SETTLED → AVAILABLE
                     → PAYMENT_DISPUTED → RESTRICTED

The fraud path this closes is stolen card → buy points → repurchase for clean
money. `minHoldDays: 90` already delays it; settlement state is what makes the
delay meaningful.

## D18. The boundary

Afrinkong is a travel company offering a closed-loop travel entitlement
programme. It is not a bank, a savings institution, an investment platform, a
money-transfer service, a currency exchange, a general-purpose wallet, or a
Travel Point exchange.

Whether regulators characterise every aspect that way is what counsel decides.

## D19. The twelve questions counsel must answer

Before `Programme 2026-A` may leave DRAFT:

| # | question |
|---:|---|
| 1 | Does this structure constitute prepaid access or a prepaid program under applicable US federal law? |
| 2 | Does restricting redemption to Afrinkong travel qualify as closed-loop treatment? |
| 3 | How does the $2,000 threshold apply to a digital wallet accumulating over months (D3)? |
| 4 | Does taking payment now and providing travel later create money-transmission obligations? |
| 5 | Does repurchase — discretionary or contractual — change the analysis? |
| 6 | What arises from selling to customers outside the United States? |
| 7 | Which federal and state consumer-protection rules apply? |
| 8 | Do state money-services laws require licences where customers are located? |
| 9 | When is revenue recognised, and what liability do outstanding points create? |
| 10 | What are the sales-tax and VAT consequences of purchase, redemption, cancellation and repurchase? |
| 11 | What disclosures are required for money received before travel is delivered? |
| 12 | What happens to outstanding points if a programme is discontinued? |

## D20. The compliance ladder

    DRAFT → LEGAL_REVIEW → ACCOUNTING_REVIEW → APPROVED → PILOT → ACTIVE

with `SUSPENDED` reachable from anything live, and `RETIRED` from anywhere.
**Only PILOT and ACTIVE may issue a point.**

The ladder is not skippable. `DRAFT` can reach only `LEGAL_REVIEW` or
`RETIRED`; `APPROVED` cannot be reached from `DRAFT` even by an administrator.
Naming legal and accounting review as *states* means somebody has to record, in
a commit, that each happened.

`status: 'active'` is now inert. It was one word away from taking money; it is
now a derived label the gate does not read.

Reaching `PILOT` additionally requires `mayActivate()` — an exposure limit that
nobody has set is not a limit, and C15's $50m question has to have an answer
before anyone is charged.

## D21. Five permanent invariants

Not tests of a feature. The boundary between a travel company and a financial
one, written so that crossing it means deleting a check rather than forgetting
one. All five are live in `tools/points-checks.js`.

| # | invariant | how it is enforced |
|---:|---|---|
| 1 | no issuance without passing the compliance ladder | `mayIssue` reads `compliance`; `mayTransition` refuses skips; `PILOT` requires `mayActivate` |
| 2 | no issuance from a frontend request | the customer-facing bundle is scanned; it constructs no entry and could not issue one |
| 3 | no mutation of history | `point_ledger` refuses `UPDATE` and `DELETE` at the database |
| 4 | no growth from elapsed time | the ledger has no clock, no growth vocabulary, and a closed set of kinds |
| 5 | no balance presented as cash | the wallet exposes no monetary field; the goal reads in TP |

## D22. Decision

**D — approved as the control framework. Not legally approved for
customer-money activation.**

Programme 2026-A stays `DRAFT` until counsel and the accountant answer D19.
This does not slow the work: everything except the money-taking boundary can be
built, and now the boundary is a ladder somebody has to climb deliberately.

> The financial infrastructure must serve the travel product — not turn the
> travel company into a financial product.
