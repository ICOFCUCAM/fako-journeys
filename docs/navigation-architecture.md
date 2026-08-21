# Item 5 — navigation architecture

**PROPOSED. NOT BUILT.** Nothing in this document has been applied to a page.
It touches all 1,597 pages and is the change a visitor notices first, so it
waits for the larger mandate rather than being assumed.

---

## The correction that produced it

The first version of this was a rename:

```
The Atlas      → Explore
Trans Afrique  → Explore / Travel
Journey Fund   → Fund
Stories        → Explore
Meet Africa    → Explore
```

**That is a navigation cleanup, and it is the wrong shape.** It flattens five
named things into four generic words and calls the loss of three product
identities a simplification. Trans Afrique, Stories and Meet Africa are not
labels; they are products with their own character, built to a standard the
rest of the site is measured against.

The reservation recorded in `docs/information-architecture.md` was right, and
the resolution is that **the four areas are the spine and the named products
are first-class within them** — not a dropdown nobody opens, and not deleted.

---

## The architecture

### EXPLORE — discover Africa

```
EXPLORE
├── Destinations
├── The Atlas
├── Stories
├── Meet Africa
└── Trans Afrique
```

Also here, and already built: countries, places, wildlife, culture, wonders,
cities, scale, compare. The universal index (⌘K) spans all of it.

**The names survive.** "The Atlas" is what that product is called; "Explore" is
where it lives.

### PLAN — turn discovery into a journey

```
PLAN
├── Build a Journey
├── Journey Fund
└── My Goals
```

Also here: itineraries, journey pricing, the rate card, the Travel Goal.

The Plan → Fund edge this session repaired is the seam between the first two
entries, and it now carries in both directions.

### FUND — prepare financially

```
FUND
├── Travel Points
├── Travel Wallet
└── Activity
```

Also here: programme information, point activity.

**Nothing in this area may appear before it is real.** Issuance is off, the
wallet is deliberately unwired, and four readiness blockers stand. A navigation
entry for a Travel Wallet that cannot be opened is a promise the product cannot
keep, so FUND's children appear as the states behind them become reachable —
which is what the state language now makes expressible.

### TRAVEL — actually go

```
TRAVEL
├── My journeys
├── Bookings
├── Documents
├── Payments
└── Journey status
```

Also named in the brief: passport requirements, accommodation, transport,
permits.

**This area is almost entirely unbuilt, and that is correct.** `booking.js`
holds the seven states and they have no surface. The state language now gives
each of them a sentence and a tone, so when this area is built the words are
already decided.

### ACCOUNT

Identity, security, preferences, legal. **Appears only when there is an
account.** Planning needs no account; ownership does — item Z's rule, unchanged.

---

## What this preserves

| product | today | proposed | lost? |
|---|---|---|---|
| The Atlas | top level | EXPLORE › The Atlas | no |
| Trans Afrique | top level | EXPLORE › Trans Afrique | no |
| Stories | top level | EXPLORE › Stories | no |
| Meet Africa | top level | EXPLORE › Meet Africa | no |
| Journey Fund | top level | PLAN › Journey Fund | no |
| Every place | top level | EXPLORE › Destinations | renamed |

Five named products, five still named. What changes is that a visitor can see
**Explore → Plan → Fund → Travel** exists, which today nothing tells them.

---

## The open questions

These are decisions, not details, and they are the reason this is a proposal:

1. **Does "Journey Fund" belong to PLAN or FUND?** The brief places it in both.
   It is a *planner* that holds nothing, which argues for PLAN — but it is the
   entry point people will look for under FUND. Splitting the name across two
   areas is how a product ends up with two front doors.
2. **"My Goals" versus "Travel Goal".** The module says Travel Goal; the
   navigation draft says My Goals. One of them has to give.
3. **When does FUND appear at all?** An area whose three children are all
   unreachable is an empty room with a sign on it.
4. **Trans Afrique's own masthead.** It has one, with its own identity. Nesting
   it under EXPLORE in the global nav while it keeps its own chrome is either
   right or confusing, depending on a judgement nobody has made yet.

---

## The revised phase order

Recorded because it reframes what the remaining work is for:

```
1  Economic correctness        ─┐
2  Technical correctness        │  make the system CORRECT
3  Information architecture    ─┘
4  State language              ─── make the system LEGIBLE
5  Navigation architecture     ─┐
6  Visual / product architecture│
7  Interaction design           │  make the system DESIRABLE
8  International premiumisation │
9  Performance / accessibility  ─┘

   only then: the visual activation of the Travel Points infrastructure
```

1–3 are done. 4 is done. **5 onward begins on the larger mandate, not on this
document.**

The structural defects found on the way through — 51 dangling accessibility
references, 53 isolated country nodes, a tier vocabulary that silently did not
carry, a non-idempotent transform, eleven colliding state words — are the
reason this order is right. Each was invisible, each was cheap to fix before
the visual layer, and each would have been expensive to find underneath it.
