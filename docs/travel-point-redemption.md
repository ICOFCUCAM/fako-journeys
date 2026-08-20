# Decision F — what a Travel Point can actually buy

**SETTLED as canonical.** `AFK-TP-2026.1` remains `compliance: DRAFT`.

> A Travel Point may be redeemed only against eligible Afrinkong travel
> services explicitly included in the applicable Travel Point Programme.
> 1 TP = one unit of travel entitlement, not $1.

---

## Numbering

There is already a **Section F** — pricing, in `travel-point-pricing.md`. This
is **Decision F**, redemption scope. Both are kept; `CLAUDE.md` routes to the
right one. The economic identity now reads:

| | question | document |
|---|---|---|
| A | what is a Travel Point? | `travel-point-definition.md` |
| B | how is it issued? | `travel-point-issuance.md` |
| C | how does the customer exit? | `travel-point-exit.md` |
| D | what happens over time? | `travel-point-duration.md` |
| E | can it move between people? | `travel-point-transfer.md` |
| **F** | **what can it buy?** | **this document** |

---

## F1 — the boundary

Broad enough to be genuinely useful; precise enough not to become money.
A Travel Point cannot buy groceries, electronics, cash, or unrelated services,
and asking produces a named refusal rather than a silent zero:

> outside the programme's eligible services — `groceries, electronics`

The customer is told **which line of their journey the points do not reach**,
which is the only version of this that helps anybody.

---

## F2/F3/F4 — the basket

**Journey services.** accommodation · transport · guiding · excursion ·
activity · destination_service · domestic_transport · journey

**Government and supplier charges** — in, when Afrinkong arranges and settles
them: park_fee · conservation_fee · permit · entrance_fee · government_charge

Afrinkong does not absorb these. The customer's points cover an eligible $500
permit and Afrinkong settles the supplier separately.

**Afrinkong's own service fee** — `afrinkong_service`. Without it a customer
could accumulate a large holding and still discover Afrinkong must be paid
separately, which is the kind of surprise that makes a product feel like a
trick.

---

## F5–F8 / F12 — the exclusions, as a list with reasons

| excluded | why |
|---|---|
| international flights | third-party ticketing, fare changes, airline credit, chargebacks |
| visas | government-controlled, applicant-specific, nationality-dependent |
| travel insurance | personal cover the traveller arranges |
| personal meals | outside the booked itinerary |
| personal spending | shopping, souvenirs, entertainment, alcohol, incidentals |
| tips | discretionary and personal |
| personal upgrades | not part of the booked Afrinkong itinerary |

**"Not in `eligibleServices`" was not good enough.** A page cannot render a list
that exists only as the *absence* of entries in another list, and F12 requires
the customer to see exclusions before booking. So exclusions are now a positive
list carrying its own reasons.

### And they agree with what the site already publishes

`tourism/rates.json` carries an `excluded` array the pages already render.
Rather than write a second list, the programme's exclusions are held against
the published one by a check — **terms that disagree with the pages are worse
than either.**

---

## F8/F13 — the journey, broken into what it is made of

> Your selected journey requires 4,750 Travel Points, and here is which parts
> of it produced that figure.

Not *"your Travel Points are worth $4,750."*

```
Afrinkong Signature — 7 days     4,550 TP   [transport]
Arrival coordination                200 TP   [afrinkong_service]
─────────────────────────────────────────
Total                             4,750 TP
```

**The components sum to the requirement.** A table that does not add up to the
number beside it is decorative, which is worse than no table — so that equality
is a check.

### What this deliberately does *not* do

It does not invent a seven-line split. The rate card prices a **tier per day**,
and that tier's `includes` list names what the day covers (vehicle, driver,
fuel, movement, coordination); it carries no separate accommodation or safari
figure. Manufacturing one would hand the customer a table that looks precise
and is fiction.

Where a real component exists it is listed. Where the rate card only knows a
bundle, the bundle is named **along with what it contains**.

### Eligible but not in the figure

Destination charges are eligible and priced per journey, so they are listed
as such rather than silently omitted — a customer who meets a $700 permit at
booking has been misled by an omission just as surely as by a wrong number.

---

## F9/F10 — points and money may be combined

A customer 300 TP short must not be forced to buy another whole block.

```
shortfallPoints: 300
settlement: { permitted: true, mechanism: null, pointsFirst: true }
alternatives: [ acquire the additional points · change the itinerary ·
                choose another journey · wait — they do not expire ]
```

**That the combination is permitted is decided. The rate is not.**
`mechanism: null` is the honest record of an undecided programme term (B-iv);
a function that quietly returned "$1,500" would have decided it at a call site.
No dollar figure appears anywhere in the response.

---

## The eligible percentage

> Travel Points may cover up to 100% of eligible Afrinkong ground and
> accommodation services.
> Another programme might say: up to 70% of the eligible journey.

`redemptionCap: { maxPortion: 1.0, appliesTo: 'eligible' }`

At 70%, a 10,000 TP journey is 7,000 payable by points and a 3,000 TP
remainder — **stated in points**, never converted. This gives commercial
flexibility **without touching what a Travel Point is**: the definition is
unchanged and only the redemption rule moves.

Applied *before* the sufficiency test, or a 70% programme would cheerfully
approve a full-point booking it does not permit.

---

## F11 — excess points stay points

Journey 7,800 TP, holding 8,000 TP → **200 TP remain**, available for another
eligible journey. Not $200. There is no field on the wallet that could hold a
cash remainder, so this is enforced by shape rather than by policy.

---

## F14 — the requirement is not derived from cost

8,000 TP against $6,700 of supplier cost does **not** mean 1 TP = $0.8375. The
point economy is not computed backwards from Afrinkong's costs; the programme
defines entitlement and commercial margin is a separate business calculation.

The module contains no notion of cost or margin at all — checked, not asserted.

---

## F15 — discounts change the journey, not the point

| | |
|---|---|
| normal journey | 10,000 TP |
| promotional journey | 8,500 TP |
| customer's holding | **10,000 TP, unchanged** |
| they keep | 1,500 TP |

`entitlementRate` never moves, which is exactly what B18 forbids moving. A
discount is a cheaper journey, not a revalued point.

---

## No retroactive expiry, and the narrow exception named

`expiry.reservedRightToIntroduce: false`

A later programme change may not introduce an expiry for points already issued
**unless the original programme expressly reserved that right**. This one did
not, and recording `false` makes the reservation something somebody had to
write down in advance rather than argue for afterwards.

(The rest of expiry is Decision D — `travel-point-duration.md`. Purchased
points do not lapse; time alone cannot reduce an entitlement.)

---

## A bug this decision surfaced

**`fund-math.price()` was incompatible with `tourism/rates.json`.**

There are two rate cards. The one embedded in `journey-fund.html` carries
`arrival: 200`; the richer `tourism/rates.json` carries
`arrival: {name, rate, per}`. `price()` did `ground + D.arrival` against
whichever it was handed — and against the object that is **string
concatenation**:

```
plan: "4550[object Object]"   →  NaN downstream  →  goalRequirement() returns 0
```

The live page was unaffected because it uses the embedded card, so nothing ever
failed. A journey requirement of **0 TP** simply waited for somebody to point
the arithmetic at the other file — which `journey-catalogue.js`'s own header
says it does. Found by doing exactly that. Now coerced, and both cards produce
4,750 TP.

---

## UNRESOLVED. Recorded, not decided here.

| | question | owner |
|---|---|---|
| F-portion | Should `AFK-TP-2026.1` cap redemption below 100%, and does a cap below 100% weaken or strengthen the "not a cash balance" argument? | commercial + counsel |
| F-mechanism | How does a shortfall convert for mixed settlement? Still undecided (B-iv), and it is the last arithmetic gap between a customer and a booking. | counsel + finance |
| F-charges | Which government charges is Afrinkong *contractually responsible* for arranging, per destination? The basket permits them; whether Afrinkong settles them varies by country. | operations + counsel |
| F-newservices | New eligible services may be added without changing what issued points mean — but may a service ever be *removed* from an existing programme's basket, and what happens to points accumulated against it? | counsel |
| F-components | The breakdown decomposes what the rate card prices, which is a bundle plus arrival. Should the rate card carry per-component pricing so F8's fuller table becomes truthful? | product |
| F-naming | `goalRequirement(programId, journeyCostMinor)` names its input a *cost* when it is the journey's **price to the customer**. That blurs precisely the distinction F14 draws, and the F14 check flagged it on first run before the regex was narrowed. Renaming touches several call sites. | engineering |

Everything open in the other five decisions remains open.

---

## What this decision did **not** do

- No programme was activated.
- No conversion rate between points and money was invented, at any call site.
- No component figure was manufactured that the rate card cannot support.
- No exclusion was hidden in terms rather than shown before booking.
