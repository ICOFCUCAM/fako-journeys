# Phase 2 — Information architecture

**Explore · Plan · Fund · Travel · Account**

These five are **not new sections to build.** Every one of them already exists
in the repository under a different name, built to a high standard, and
disconnected from the others. Phase 2 is naming and wiring, not construction.

---

## The rule that decides every placement

> **A visitor moves through one question at a time, and the architecture should
> answer the question they are actually asking.**

```
I want to go somewhere          →  EXPLORE
I want to know what it's like   →  EXPLORE
I want to know what it costs    →  PLAN
Can I afford it?                →  FUND
I want to work toward it        →  FUND
I want to travel                →  TRAVEL
What do I hold?                 →  ACCOUNT
```

**Travel Points appear when they become useful, not before.** They belong to
Fund and Account. They must not appear in Explore at all, and in Plan only as
the *second* denomination of a price already stated in money.

---

## EXPLORE — the emotional front door

*Africa should feel enormous, sophisticated and desirable.*

| already exists | route | what it is |
|---|---|---|
| the atlas | `/atlas` | geography as interface; map, panel, breadcrumb and URL cannot disagree |
| country overviews | `/<country>` × 54 | "Where the safari was invented" |
| portraits | `/portrait/<country>` × 54 | 16-section long reads, complete without JavaScript |
| places | `/places/<country>/<place>` × 1,363 | the individual experiences |
| meet | `/meet` | seven human questions × 22 countries |
| stories | `/stories` | the story graph, with search over 581 proper names |
| wonders · cities · scale · compare | various | thematic entries |
| the universal index | Cmd/Ctrl-K | one search over all of it |

**Nothing here needs building.** What Explore needs is a *spine* — see
"the missing edges" below.

## PLAN — inspiration becomes a journey

| already exists | route | what it is |
|---|---|---|
| the journey builder | `/journey` | **four questions, deterministic, URL-as-state, shareable** |
| the reasoning | `journey-engine.js` | pure; runs identically in browser and Node |
| experiences per country | `/tourism/<country>` × 56 | "all 27 experiences" |
| the rate card | `tourism/rates.json` | tiers, durations, service, destination charges |
| the requirement | `journey-catalogue.js` | journey → points, versioned and explicable |
| Trans Afrique | `/trans-afrique` | the four crossings |

**Phase 7's transactional experience is already built.** It needs entrances and
an exit, not writing.

## FUND — the economics, made understandable

| already exists | route / module | what it is |
|---|---|---|
| the Journey Fund | `/journey-fund` | the planner; now records what a reader has set aside |
| the Travel Goal | `travel-goal.js` | target, progress, projection, **funded state** |
| how it works | `/journey-fund/how-it-works` | the explanation |
| the questions | `/journey-fund/questions` | |

**What Fund must never become:** *"open a savings account."* The framing is
**build your journey before you book it**, and the panel already carries the
disclosure that says nothing is for sale.

```
Journey        $4,800
Travel Goal    4,800 TP
Set aside      1,200 TP
Remaining      3,600 TP
Progress       25%
```

That reads as travel with a measure, not as a balance — which is Decision I,
already enforced.

## TRAVEL — after booking

**This is the one area with almost nothing built**, and that is correct:
booking cannot happen until issuance is on and counsel has answered.

`booking.js` holds the states — requested → accepted → reserved → confirmed →
redeemed, with the price lock. **The states exist and have no surface**, which
is the largest single item in Phase 10's state language.

## ACCOUNT — what I hold

| already exists | module |
|---|---|
| the wallet view | `account.js` — available · reserved · total held · pending · restricted |
| security levels | which actions need step-up |
| recovery | tiers scaled by holding |
| the ledger | `points-ledger.js`, 2,677 lines |

**Designed, deliberately unwired.** Four readiness blockers stand between this
and a customer. The brief's own instruction holds: *the wallet is subordinate
to travel.* Afrinkong is a travel company that invented a better way to make
travel achievable — not a fintech that sells safaris.

---

## The missing edges

Phase 1 measured this: **the nodes are excellent and the graph is broken.**

### What exists today

```
        /kenya ──────────► /tourism/kenya ──► /journey
           ▲                  (dead end: 8 links, 4 of them fonts)
           │
    /portrait/kenya ──────► 22 × /places/kenya/…
       (reachable from                (no way back up)
        neither of the above)
```

### What it must become

**One Kenya at four depths**, with edges in both directions:

```
                    EXPLORE                     PLAN            FUND
                       │                          │               │
  /kenya  ────────────────────────────────────────────────────────────
  overview        │  portrait  │   places    │  experiences  │  goal
  "why here"      │ "the long  │  "the 26    │  "what it     │ "what it
                  │   read"    │   things"   │   costs"      │  takes"
       │                │             │             │             │
       └────────────────┴─────────────┴─────────────┴─────────────┘
                    every depth reaches every other
```

### The specific edges to add

| from | to | why it is missing today |
|---|---|---|
| `/kenya` | `/portrait/kenya` | the richest page on the site, linked from nowhere |
| `/kenya` | `/places/kenya/*` | only the portrait goes down |
| `/tourism/kenya` | `/kenya`, `/portrait/kenya`, `/places/*` | it is a dead end |
| `/tourism/kenya` | `/journey?place=kenya` | it has `/journey` but not seeded |
| `/places/kenya/<place>` | `/kenya`, `/tourism/kenya` | nothing leads back up |
| `/journey` (composed) | `/journey-fund?journey=…` | **the Plan → Fund handoff does not exist** |
| `/journey-fund` | `/journey` | the Fund cannot start a journey |

**The last two are the most valuable in the whole brief.** A visitor who has
composed a journey — a real, deterministic, shareable journey — currently has
nowhere to take it. The Fund can price a journey the builder already chose, and
the two never meet.

---

## Navigation

Today: *The Atlas · Trans Afrique · Journey Fund · Stories · Meet Africa ·
Every place* — five content destinations, one product surface.

Proposed: **Explore · Plan · Fund · Travel**, with everything above nested
beneath, and Account appearing only when there is an account.

Two cautions, both real:

1. **This touches all 1,597 pages** and is the change a visitor notices first.
   It is proposed, not made.
2. **Trans Afrique, Stories and Meet are strong products with their own
   identity.** Folding them into "Explore" must not bury them — they should be
   first-class within it, not a dropdown nobody opens.

---

## Order of work

| | | why |
|---|---|---|
| 1 | **token layer** | done — nothing visual, but every later phase costs 15× without it |
| 2 | **the Plan → Fund edge** | highest value, smallest diff, no navigation change |
| 3 | **country graph repair** | four Kenyas become one Kenya at four depths |
| 4 | **the state language** | 39 system states, one expressible |
| 5 | **navigation** | needs approval; touches everything |
| 6 | components, homepage, destinations, wallet shell | after the above |

---

## What Phase 2 did not do

- Nothing was renamed, moved or removed. This is the map, and the map is not
  the territory yet.
- No navigation change was made.
- Trans Afrique, Meet, Stories, the atlas and the builder were left exactly as
  they are. **They are the product's best work**, and the finding was never
  that they are weak — it was that they are unconnected.
