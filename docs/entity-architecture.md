# The three layers — who is acting, and why

**BUILT.** `scripts/entities.js` is the model, `tools/entity-checks.js` enforces
it (17 checks), and this document is what they mean.

> Three companies' worth of responsibility run through this product. A customer
> is entitled to know which one they are dealing with at any moment — **and the
> answer must be visible on the surface where it matters, not inferable from a
> footer.**

---

## The layers

| | layer | who | what it does |
|---|---|---|---|
| 1 | **experience** | **Afrinkong** | discover → explore → plan → journey → enquire |
| 2 | **commercial** | **Wankong LLC** | Travel Points, programmes, customer agreements, the ledger, and eventually payment |
| 3 | **operations** | **the operator**, named per country | destination operations, suppliers, local execution, the operational desk |

Afrinkong is a **trading name** of Wankong LLC — it is not a separate company
and it issues nothing. There are three named ground operations today: Kamerun,
Pearl Trails Uganda, Namib Skyline.

**These can work together without being confused.** The way to keep them
unconfused is *not* three footers with three legal names on them. It is that
every act touching a customer's money, entitlement or trip says who is doing it,
where it happens.

---

## Who acts

| act | actor | layer | declares? | also |
|---|---|---|---|---|
| `explore` | Afrinkong | experience | — | |
| `plan` | Afrinkong | experience | — | |
| `enquire` | Afrinkong | experience | **yes** | the operator |
| `book` | **Wankong LLC** | commercial | **yes** | the operator |
| `pay` | **Wankong LLC** | commercial | **yes** | |
| `cancel` | **Wankong LLC** | commercial | **yes** | |
| `points` | **Wankong LLC** | commercial | **yes** | |
| `support` | Afrinkong | experience | **yes** | the operator |
| `operate` | the operator | operations | — | |
| `desk` | the operator | operations | **yes** | |

**Six must declare** — enquiry, booking, payment, cancellation, Travel Points,
customer support. Those are the ones where a customer's money, entitlement or
trip is at stake.

### The two-party acts

A booking is an **agreement with one company** and **days run by another**.
Telling a customer only half of that is how *"who do I call"* becomes
unanswerable:

```
enquire   Afrinkong    + the operator who runs that country
book      Wankong LLC  + the operator who runs the days
support   Afrinkong    before you travel
          the operator while you are travelling
```

### Money

**Everything that moves money or entitlement is Wankong LLC's** — `pay`, `book`,
`cancel`, `points`. Not Afrinkong, which is a name. Not the operator, who is a
supplier.

`company.json` already said this: *"Journeys are quoted, invoiced and settled in
US dollars, to Wankong LLC."* A check asserts the model and that sentence agree,
and another scans all 1,597 pages for any claim that a customer pays Afrinkong.

---

## Classification: four inputs, never one

**The correction that produced this.** The first guard on this boundary
classified links **by URL** — a list of operator paths, forbidden in certain
places. That is wrong twice over:

- **`/cameroon`** is Cameroon, one of fifty-four countries, and belongs in
  Explore. It is *also* where a ground operation is based. The URL cannot tell
  you which a given link means.
- **`/contact`** is an operator desk, and is perfectly correct on a page where
  the visitor is explicitly dealing with that operator.

So a link is classified by **entity + context + position + action**, and any one
alone gives the wrong answer. The same href, four positions:

| position | verdict |
|---|---|
| in the body of a page about that operator | `operational` |
| in the primary navigation | `misdirected` |
| in the footer navigation | `misdirected` |
| as a primary button | `misdirected` |
| as a primary button, **declared** | `handover` |
| anywhere on the operator's own page | `own` |

**Declaring it is what turns a misdirection into a handover.** That is the whole
mechanism: crossing an entity boundary is fine, and doing it silently is not.

---

## The rule that matters more every month

> A booking or payment flow must **never** move a customer from Afrinkong's
> journey into the operator's desk *because that desk already has the
> infrastructure.*

That is the cheapest wrong turn available. The form exists, it works, and
pointing at it saves a week. It also makes the brand a referrer to its own
supplier — and once money moves, it makes *"who did I pay"* unanswerable from
the screen the customer was looking at.

**Nothing on this site takes a payment today, which is exactly why the rule is
written now.** `entity-checks.js` fails the moment a surface carrying a card
field or a "pay now" button appears without naming Wankong LLC **on itself** —
not in a footer, not on a terms page. Verified by creating such a page and
watching it fail.

---

## How this relates to the state language

They are **orthogonal, and both are needed**:

```
docs/state-language.md   72 states   WHAT is happening, and which of five kinds
docs/entity-architecture WHO is doing it, and why that entity
```

A state says *"Payment received."* The entity layer says *received by Wankong
LLC, because that is the company you contracted with.* Neither answers the
other's question.

The mapping is checked:

| state domain | acting entity |
|---|---|
| `points` | Wankong LLC |
| `money` | Wankong LLC |
| `travel` | Wankong LLC — the agreement; the days are operated |
| `account` | Wankong LLC |
| `system` | Afrinkong — the platform itself |

Decision I is restated here as an entity rule: **no entitlement state may name
the trading name as the issuer**, because a trading name issues nothing.

---

## What a customer should be able to tell, at any moment

The test this whole model exists to pass:

| when they are | they should see |
|---|---|
| reading about a place | Afrinkong, and no money anywhere |
| building a journey | Afrinkong, and nothing held or charged |
| enquiring | Afrinkong — answered by the named operation where there is one |
| **paying** | **Wankong LLC**, named on the surface taking the money |
| **holding Travel Points** | **Wankong LLC**, under a programme with written terms |
| **on the ground** | **the named operator**, and how to reach them |
| on the operator's own pages | that operation, with its own shell |

**Do not hide the relationships. Make them intelligible.** Three footers with
three legal names is compliance. Knowing who is acting, at the moment they act,
is architecture.
