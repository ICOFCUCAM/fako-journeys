# The Afrinkong state language

**Item 4.** Generated from `scripts/state-language.js` by
`node tools/state-doc.js > docs/state-language.md`. Do not edit by hand —
`state-checks.js` regenerates it and fails if this file differs.

> The system can distinguish **72 states**. Before this, the website
> could express **one**, and it was `empty`.

The published figure for the gap was 39 states across five vocabularies.
That undercounted by 33: it missed account states, auth levels,
the buyback request lifecycle, risk holds, purchase plans, product state,
transfer kinds, and the journey’s own six stages.

## The two vocabularies

A small vocabulary and an unambiguous one pull in opposite directions. They
are therefore different vocabularies:

| | size | job |
|---|---|---|
| **tones** | 6 | the visual language. Learned once, recognised everywhere |
| **labels** | 72 | one per state, never shared. Precise |

A customer learns six shapes and reads a specific sentence. **One word never
does two jobs.**

### Why that rule is not optional

Internally, 11 words already carry more than one
meaning:

```
REJECTED   ×3   buyback · booking · hold
RESERVED   ×3   points · booking · journey
SETTLED    ×3   points · payment · buyback
ACCEPTED   ×2   buyback · booking
ACTIVE     ×2   plan · programme
APPROVED   ×2   buyback · programme
CANCELLED  ×2   points · booking
CLOSED     ×2   account · programme
PLANNING   ×2   journey · product
REDEEMED   ×2   points · booking
REQUESTED  ×2   buyback · booking
```

That is tolerable in code, where the vocabulary name disambiguates. It is
not tolerable on a screen, where there is no vocabulary name — which is why
the customer labels must be unique even though the internal words are not.

## The 6 tones

| tone | means | used by |
|---|---|---|
| `neutral` | a fact. Nothing is happening and nothing is wrong | 16 states |
| `working` | we are doing it; it finishes without anybody | 15 states |
| `waiting` | it needs a person. It will **not** finish on its own | 14 states |
| `done` | finished the way it was meant to | 10 states |
| `ended` | over, by choice or by time. **Not** a failure | 12 states |
| `broken` | went wrong, and somebody has to look | 5 states |

### ENDED is not BROKEN

The most important line in the system. An expired point, a cancelled
journey, a declined quote and a closed programme are **ordinary endings**. A
failed payment and a chargeback are **faults**. Painting both the same
colour teaches a customer that ordinary endings are their fault, and a
customer who believes that stops pressing things.

Only 5 states out of 72 may be `broken`, and a
check names them:

- `payment:failed` — Payment did not go through
- `payment:charged_back` — Payment disputed
- `buyback:REJECTED` — Repurchase stopped after review
- `risk:REJECT` — Cannot go ahead
- `hold:REJECTED` — Review did not clear

`working` is the only tone that animates, because it is the only one making
a claim about the future. A spinner over “we need you to confirm” is a lie
told in motion.

## The five kinds of state

| kind | question it answers | states |
|---|---|---|
| **points** | what happened to entitlement | 13 |
| **money** | what happened to money | 19 |
| **travel** | what happened to the journey or booking | 13 |
| **account** | what the customer is permitted to do | 7 |
| **system** | what the platform is currently doing | 20 |

No vocabulary straddles two kinds, and a check enforces it — mixed domains
inside one vocabulary is how “cancelled” starts meaning both the money and
the journey again.

## Every state

Seven columns, as the brief asked: canonical state, customer label,
explanation, allowed transitions, visual treatment, which kind of state it
is, and what the customer can do.

### Journey stages  `journey:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `PLANNING` | **Planning this journey** | You are working out what it takes. Nothing is booked and nothing is owed. | — | `neutral` | travel | plan-a-journey |
| `FUNDED` | **Journey funded** | You have reached what this journey takes. This is the beginning of booking, not the end of saving. | — | `done` | travel | plan-a-journey |
| `BOOKING` | **Being booked** | We are turning this into a real itinerary with the people who run it. | — | `working` | travel | wait |
| `RESERVED` | **Held for you** | Your place is held at the price you were shown. | — | `waiting` | travel | confirm, cancel |
| `TRAVELLING` | **Travelling** | You are on it. This is the part the rest was for. | — | `working` | travel | contact-us |
| `COMPLETED` | **Journey complete** | You went and you came back. The record stays with you. | — | `done` | travel | plan-a-journey |

### Bookings  `booking:*`

Transitions read from `booking.js` `BOOKING_NEXT`.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `REQUESTED` | **Journey requested** | We have your journey and somebody is reading it. | ACCEPTED, REJECTED | `working` | travel | wait, cancel |
| `ACCEPTED` | **Journey accepted** | We can run this journey. Next it is reserved. | RESERVED, REJECTED | `working` | travel | view-details, cancel |
| `REJECTED` | **Journey not accepted** | We cannot run this one, and we will say what would work instead. | *terminal* | `ended` | travel | contact-us, plan-a-journey |
| `RESERVED` | **Journey reserved** | Held for you, at the price shown. That price is now locked. | CONFIRMED, CANCELLED | `waiting` | travel | confirm, cancel |
| `CONFIRMED` | **Journey confirmed** | It is booked. The price cannot change from here. | REDEEMED, CANCELLED | `done` | travel | view-details, cancel |
| `CANCELLED` | **Journey cancelled** | This journey is off, and anything held for it has been released. | *terminal* | `ended` | travel | plan-a-journey |
| `REDEEMED` | **Journey travelled** | You went. This is the end of the journey, not of the account. | *terminal* | `done` | travel | view-details |

### Travel Points  `points:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `CREATED` | **Being prepared** | The record exists and the point is not yours yet. | — | `working` | points | wait |
| `ISSUED` | **Issued to you** | The point is yours. It is about to become available to spend. | — | `working` | points | wait |
| `AVAILABLE` | **Ready to use** | You can put this towards a journey whenever you choose. | — | `neutral` | points | plan-a-journey |
| `RESERVED` | **Held for a booking** | Set aside for a journey you have started. Still yours, not yet spent. | — | `waiting` | points | view-details, cancel |
| `REDEEMED` | **Used for travel** | Spent on a journey. This is what a Travel Point is for. | — | `done` | points | view-details |
| `TRANSFERRED` | **Given to someone** | Passed to another person. It is theirs now, not yours. | — | `done` | points | view-details |
| `BUYBACK_REQUESTED` | **Repurchase asked for** | You have asked us to buy this back. Nothing has moved yet. | — | `waiting` | points | wait |
| `BUYBACK_APPROVED` | **Repurchase agreed** | We have agreed to buy it back, and the payment is being arranged. | — | `working` | points | wait |
| `SETTLED` | **Repurchase completed** | Bought back, and the payment has left us. | — | `done` | points | view-details |
| `CANCELLED` | **Cancelled** | This point was undone, and the record of why it existed remains. | — | `ended` | points | view-details |
| `EXPIRED` | **Expired** | Past the date it could be used by. Nothing was taken from you. | — | `ended` | points | view-details |
| `TRANSFER_IN` | **Received from someone** | Somebody passed these to you. | — | `neutral` | points | view-details |
| `TRANSFER_OUT` | **Sent to someone** | You passed these on. They belong to the person you sent them to. | — | `neutral` | points | view-details |

### Payments  `payment:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `pending` | **Payment starting** | Your bank has the request. This usually takes a few seconds. | — | `working` | money | wait |
| `requires_capture` | **Payment needs one more step** | Your bank has asked you to confirm this before it will go through. | — | `waiting` | money | confirm |
| `authorised` | **Payment approved, not yet taken** | Your bank has approved it. Nothing has left your account. | — | `working` | money | wait |
| `settled` | **Payment received** | The money has reached us. | — | `done` | money | view-details |
| `failed` | **Payment did not go through** | Your bank declined it. Nothing was taken, and you can try again. | — | `broken` | money | retry-payment, contact-us |
| `refunded` | **Payment returned** | The money has gone back to where it came from. | — | `ended` | money | view-details |
| `charged_back` | **Payment disputed** | Your bank has reversed this and we are looking into it with them. | — | `broken` | money | contact-us |

### Repurchase requests  `buyback:*`

Transitions read from `buyback.js` `REQUEST_NEXT`.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `REQUESTED` | **Repurchase request received** | We have your request and are working out what we can offer. | QUOTED, REFUSED | `working` | money | wait |
| `REFUSED` | **Repurchase not available** | We cannot buy these back at the moment, and here is why. | *terminal* | `ended` | money | contact-us |
| `QUOTED` | **Repurchase offer ready** | Here is what we can offer. It is a quote, not a hold, and it can change. | ACCEPTED, DECLINED, LAPSED | `waiting` | money | accept-quote, decline-quote |
| `LAPSED` | **Repurchase offer expired** | This offer was not taken up in time. You can ask again. | *terminal* | `ended` | money | view-details |
| `DECLINED` | **Repurchase offer declined** | You turned this offer down. Your points are untouched. | *terminal* | `ended` | money | view-details |
| `ACCEPTED` | **Repurchase offer accepted** | You have accepted. We are checking it before anything moves. | APPROVED, REJECTED | `working` | money | wait |
| `APPROVED` | **Repurchase approved** | Checked and agreed. The payment is being arranged. | SETTLED, REJECTED | `working` | money | wait |
| `REJECTED` | **Repurchase stopped after review** | Our checks stopped this one. Talk to us and we will explain. | *terminal* | `broken` | money | contact-us |
| `SETTLED` | **Repurchase paid** | The money has been sent. | *terminal* | `done` | money | view-details |

### Purchase plans  `plan:*`

Transitions read from `purchase-plan.js` `PLAN_NEXT`.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `ACTIVE` | **Plan running** | Your plan is set. Nothing is charged automatically. | PAUSED, STOPPED | `neutral` | money | pause-plan |
| `PAUSED` | **Plan paused** | On hold, and nothing about it is lost. | ACTIVE, STOPPED | `waiting` | money | resume-plan |
| `STOPPED` | **Plan stopped** | Finished. Starting again begins a new plan, and this one stays on record. | *terminal* | `ended` | money | plan-a-journey |

### Accounts  `account:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `UNVERIFIED` | **Not verified yet** | You can plan and explore. Holding or moving points needs verification. | — | `neutral` | account | verify-identity |
| `VERIFIED` | **Verified** | Everything on your account is open to you. | — | `neutral` | account | none |
| `RESTRICTED` | **Temporarily limited** | Some actions are paused while we check something. You keep what you hold. | — | `waiting` | account | contact-us |
| `CLOSED` | **Account closed** | Closed. The record of what happened stays, and we can still talk to you. | — | `ended` | account | contact-us |

### Sign-in  `auth:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `NONE` | **Signed out** | Planning needs no account. Anything you own does. | — | `neutral` | account | none |
| `NORMAL` | **Signed in** | You are signed in. | — | `neutral` | account | none |
| `STEP_UP` | **One more confirmation needed** | This one matters enough that we would like to be sure it is you. | — | `waiting` | account | confirm |

### Risk decisions  `risk:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `ALLOW` | **Checks passed** | Nothing needed looking at. | — | `neutral` | system | none |
| `HOLD` | **Being checked** | We are looking at this before it goes ahead. It is usually quick. | — | `waiting` | system | wait |
| `REJECT` | **Cannot go ahead** | This one cannot proceed. Talk to us and a person will look again. | — | `broken` | system | contact-us |

### Risk holds  `hold:*`

Transitions read from `risk.js` `HOLD_NEXT`.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `HELD` | **Waiting on a review** | Somebody is reviewing this. Nothing has been decided against you. | RELEASED, REJECTED | `waiting` | system | wait |
| `RELEASED` | **Review cleared** | The review is finished and this can carry on. | *terminal* | `done` | system | view-details |
| `REJECTED` | **Review did not clear** | The review stopped this. Talk to us and we will explain what we can. | *terminal* | `broken` | system | contact-us |

### The programme  `programme:*`

Transitions read from `points-ledger.js` `COMPLIANCE_NEXT`.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `DRAFT` | **Programme in draft** | Being designed. Nothing can be bought or issued. | LEGAL_REVIEW, RETIRED | `neutral` | system | none |
| `LEGAL_REVIEW` | **Programme with our lawyers** | Under legal review before anything can be offered. | ACCOUNTING_REVIEW, DRAFT, RETIRED | `working` | system | none |
| `ACCOUNTING_REVIEW` | **Programme with our accountants** | Under accounting review before anything can be offered. | APPROVED, LEGAL_REVIEW, DRAFT, RETIRED | `working` | system | none |
| `APPROVED` | **Programme approved, not started** | Cleared to begin, and not begun. Still nothing to buy. | PILOT, ACCOUNTING_REVIEW, RETIRED | `neutral` | system | none |
| `PILOT` | **Programme in pilot** | Running with a small group before it opens. | ACTIVE, CLOSED_TO_NEW_PURCHASES, SUSPENDED, RETIRED | `working` | system | none |
| `ACTIVE` | **Programme open** | Open, subject to the same checks everything else is. | CLOSED_TO_NEW_PURCHASES, SUSPENDED, RETIRED | `neutral` | system | none |
| `CLOSED_TO_NEW_PURCHASES` | **Closed to new purchases** | No new points are being sold. Everything you hold still works. | REDEMPTION_PERIOD, ACTIVE, SUSPENDED | `waiting` | system | plan-a-journey |
| `REDEMPTION_PERIOD` | **Winding down** | The programme is ending. What you hold can still be used, until a date we will tell you. | CLOSED, SUSPENDED | `waiting` | system | plan-a-journey, contact-us |
| `CLOSED` | **Programme closed** | Closed. If you still hold anything we will have written to you. | RETIRED | `ended` | system | contact-us |
| `SUSPENDED` | **Programme paused** | Paused while something is resolved. Nothing you hold is lost. | ACTIVE, PILOT, RETIRED | `waiting` | system | contact-us |
| `RETIRED` | **Programme retired** | Finished for good, and kept on record. | *terminal* | `ended` | system | view-details |

### Product state  `product:*`

No transition table exists in code for this vocabulary, so `nextOf` returns `null` — which is different news from “terminal”.

| state | label | explanation | → | tone | kind | actions |
|---|---|---|---|---|---|---|
| `PLANNING` | **Planning only** | Everything here is an estimate. Nothing is for sale. | — | `neutral` | system | plan-a-journey |
| `DRAFT_PROGRAM` | **Not issuing yet** | The programme exists on paper and cannot issue anything. | — | `neutral` | system | plan-a-journey |
| `ACTIVE_PROGRAM` | **Issuing** | The programme can issue Travel Points. | — | `neutral` | system | none |

## How this cannot silently drift

`tools/state-checks.js` runs in both directions:

```
module   -> language   no state exists without a sentence
language -> module     no sentence exists for a state that does not
language -> CSS        every tone has a treatment
CSS      -> language   no treatment exists for a tone that does not
language -> language   no customer label means two different things
language -> code       transitions are READ from the owning module
page     -> language   every state in HTML is real, and wears the right tone
doc      -> language   this file is regenerated and compared
```

Each was verified by breaking it deliberately. Writing
`data-state="journey:DAYDREAMING"` into the built page, painting
`journey:PLANNING` as `broken`, and removing the stylesheet from a page that
shows a state all three fail, naming the cause.

## What is adopted so far

**One surface: the Travel Goal on `/journey-fund`.** It is the only place on
the site with a live state today — issuance is off, the wallet is
deliberately unwired, and there are no bookings.

The chip is server-rendered in its opening stage, so it is correct before
any script runs and `fund.js` only ever moves it on. The other 71
sentences exist so that when a state does need showing, the words and the
treatment are already decided rather than invented under pressure.

## What this phase did not do

- No economic rule was changed, and no state was added, removed or renamed
  internally.
- No transition was invented. Five tables already existed and are read;
  `risk.js` gained one export so its table could be read rather than copied.
- Travel Points were not activated. The programme is still `DRAFT`.
- Navigation was not touched.

### One correction worth keeping

The first draft of the language invented `goal:NO_TARGET / UNDERWAY /
FUNDED` for the Travel Goal, believing it had no state vocabulary.

It has had one all along. `travel-goal.js` publishes `journeyState` and its
six stages, and its own comment calls them **“the vocabulary this product
uses.”** Inventing a parallel set would have been exactly the defect this
file exists to prevent — two vocabularies for one thing, with nothing
comparing them — committed inside the module written to stop it. The six
real stages are used, and `journeyStateOf()` reads the module’s answer
rather than recomputing it.
