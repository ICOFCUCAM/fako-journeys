# Phase 1 — Product archaeology

**Nothing changed. This is a map of what already exists.**

The finding, before the detail:

> **Afrinkong is not a thin product that needs more built. It is a large
> product whose parts do not know about each other.**
>
> There are nine substantial surfaces, four separate pages per country, and
> 1,597 pages — and the edges between them are missing, not the nodes.

---

## 1 — The diagnosis is already written in the codebase

`scripts/explore.js`, in its own header:

> *"Nine prompts built nine surfaces: a map, a builder, seven human doors, five
> hundred and seventy-two addresses, twenty-two long reads. Each one was a good
> way in and each one was a **different** way in, **which is what makes a
> product feel like a folder of features.**"*

Whoever wrote that had the diagnosis exactly right and built a universal index
as the answer. The index is real and good. **It is a search box over a folder
of features, not an architecture** — and it is the only thing currently holding
the surfaces together.

---

## 2 — What exists

### Content

| | |
|---|---|
| HTML pages | **1,597** |
| countries | 54, each with **four** separate surfaces |
| place pages | 1,363 (`/places/<country>/<place>`, ~26 per country) |
| long-form portraits | 54 (`/portrait/<country>`, 16 sections each) |
| experience pages | 56 (`/tourism/<country>`) |
| data files | **27** JSON sources — atlas, cities, wonders, scale, lenses, strands, moments, neighbours, transafrique, voices, respect, events, operators, rates, people, arcs, shapes, categories, views, picks, motion, style, journeys, map, regions, company, assets |
| build commands | **55** |

### Behaviour — 20 modules, ~9,900 lines

| module | what it is | phase it belongs to |
|---|---|---|
| `journey-engine.js` (673) | **the journey builder's reasoning.** Pure, deterministic, runs in browser and Node. Same inputs → same journey | **7** |
| `journey.js` (1,512) | its interface. Four questions, one at a time; **the address bar is the state**, so a composed journey is a real shareable link | **7** |
| `atlas.js` (971) | geography as interface. One state object, one render — map, panel, breadcrumb and URL cannot disagree | **6** |
| `explore.js` (313) | universal index. Cmd/Ctrl-K from any page including the 404 | **2** |
| `meet.js` (304) | seven human questions × 22 countries, three modes | **6** |
| `story-search.js` (229) | search over the story graph — 581 proper names read from the dataset's own sentences | **6** |
| `portrait.js` (131) | the long read. **The page is complete before the script arrives** | **6** |
| `table.js` (214) | progressive: 6 server-rendered cards become 44 | **6** |
| `points-ledger.js` (2,677) | the economic core | **8** |
| `booking.js` · `buyback.js` · `transfer.js` · `purchase-plan.js` · `journey-catalogue.js` | the economic surfaces | **8** |
| `account.js` · `risk.js` | wallet and risk architecture | **9** |
| `travel-goal.js` · `fund.js` · `fund-math.js` | the planning surface | **8** |

**Phase 7's "most important transactional experience" is already built.** It is
deterministic, URL-addressable and shareable. It is not connected to the Fund,
and nothing on a country page leads to it except one link.

---

## 3 — The structural finding: four Kenyas, and no graph

Every country has four surfaces, built separately:

| route | what it is | size |
|---|---|---|
| `/kenya` | "Where the safari was invented" | 79KB, 7 sections |
| `/tourism/kenya` | "all 27 experiences" | 70KB, 9 sections |
| `/portrait/kenya` | "a portrait" | 45KB, **16 sections** |
| `/places/kenya/*` | 26 individual places | 26 pages |

### Where each one lets you go

Measured on in-body links, with masthead and footer stripped:

| from | onward destinations | what they are |
|---|---|---|
| `/kenya` | 21 | **sideways** — neighbouring countries, `/compare` |
| `/tourism/kenya` | 8, of which **4 are fonts and icons** | **nowhere.** One real link: `/journey` |
| `/portrait/kenya` | 31 | **down** — 22 places, plus back to `/kenya` |

**The page titled "all 27 experiences" — the closest thing to a planning
surface — has essentially one outbound link.** The richest page, the portrait,
is reachable from neither of the other two. Nothing leads back *up* from a
place.

```
        /kenya ──────────► /tourism/kenya ──► /journey
           ▲                  (dead end)
           │
    /portrait/kenya ──────► 22 × /places/kenya/…
       (unreachable                (no way back up)
        from above)
```

**The nodes are excellent. The edges are missing.** That is a materially
different problem from "the pages need redesigning", and a much cheaper one to
fix.

---

## 4 — Navigation versus product

Primary navigation: *The Atlas · Trans Afrique · Journey Fund · Stories · Meet
Africa · Every place*

Five content destinations, one product surface. **A visitor cannot see that
Explore → Plan → Fund → Travel exists**, because nothing names it.

The homepage is better than the nav — seventeen sections running *feel →
moments → scale → wonders → destinations → cities → year → now → plan →
stories → decide*. That is a genuine desire-first spine and it should survive
Phase 5 largely intact.

---

## 5 — Built and unreachable

Things that work and cannot be got to:

| | |
|---|---|
| Travel Goal progress | **was** hard-coded to 0 — fixed; the reader can now record what they set aside |
| the journey builder | reachable from one link on one country surface |
| the portraits | linked from no country page |
| `/compare` | reachable from country pages only |
| 39 system states | **one** has any visual language, and it is "empty" |

---

## 6 — The presentation layer

| | |
|---|---|
| stylesheets | **15**, 9,876 lines |
| distinct `font-size` values | **418** (88 in `gateway.css` alone) |
| custom properties | **52**, most-used appearing 5 times |
| breakpoints | **45** distinct |
| card components | **12** classes across 5 prefixes |
| pages with no `body` class | **1,526 of 1,597** |

There is no design system. There are fifteen, and none is authoritative.

---

## 7 — What this means for Phases 2–10

**The work is smaller than it looks, and differently shaped.**

- **Phase 2 (IA)** is the highest-leverage phase, not Phase 5. The surfaces
  exist; they need naming and connecting. Explore / Plan / Fund / Travel /
  Account is a way of *describing what is already there*, not a thing to build.
- **Phase 6 (destinations)** is mostly **graph repair**: four Kenyas that need
  to become one Kenya with four depths — overview, experiences, portrait,
  places — and edges in both directions.
- **Phase 7 (journey builder)** is **already built and needs connecting**, not
  writing. It is deterministic and shareable; what it lacks is entrances and an
  exit into the Fund.
- **Phase 4 (design system)** must come before 5–9 but should be **tokens and
  states first**, not a visual language. 418 font sizes and 45 breakpoints are
  the reason every later phase would otherwise cost fifteen times what it
  should.
- **Phase 8** must not misrepresent what exists: issuance is off, four
  readiness blockers stand, and the Fund is a planner.
- **Phase 9** is designed and must stay unwired.

**Recommended order stands as briefed, with one change: Phase 2 and the token
layer of Phase 4 should run first and together.** Naming the architecture and
giving it one type scale are what make every later phase a normal amount of
work.

---

## What was NOT done in this phase

Nothing was changed. No file outside this document was touched. The single
edit in this session's earlier commit — the Journey Fund progress input — was
made before this phase began and is recorded in §5 as evidence rather than as
part of the archaeology.
