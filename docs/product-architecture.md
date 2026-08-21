# A — Global product architecture · D — Page-family architecture

**Deliverables A and D of the international product mandate.** Nothing here has
been implemented. This is the specification the implementation will be measured
against.

---

## A1 — What Afrinkong is, stated once

> **Afrinkong is a travel company that has built a better way to make African
> travel achievable.**
>
> It is not a marketplace, not a fintech, and not a magazine. It sells journeys
> across 54 countries, runs the ground operation itself in three of them, and
> is building a way to work towards a journey before booking it.

Two consequences that decide almost every later question:

1. **Travel is the product; the economics are a mechanism.** The wallet is
   subordinate to the journey, always. A surface that makes Afrinkong look like
   a savings app is wrong even if it is beautiful.
2. **Wankong LLC is the legal entity; Afrinkong is the consumer brand.** Every
   trust surface names the first; every travel surface carries the second. They
   are never merged and never used interchangeably.

## A2 — The spine

```
        EXPLORE            PLAN              TRAVEL
        discovery          intent            execution
           │                 │                  │
   "where could I go"  "what would it   "I am going / I am
                        take"            going now"
           │                 │                  │
           └────────────► handoff ─────────► handoff
                             │
                     ┌───────┴────────┐
                     │  FUND          │   architecturally reserved.
                     │  (not present) │   Not in public navigation
                     └────────────────┘   until the gates clear.
```

**FUND is reserved, not hidden.** The architecture has a place for it, the
state language has sentences for all of it, and the navigation does not mention
it. Presenting an empty financial product as operational is the one failure
mode this whole programme has been designed to avoid, and it would be
gratuitous to introduce it at the design stage.

The Travel Goal lives in **PLAN**, because it is a planning calculation.
`travel-goal.js` says so in its own words — *"A financial wallet has a balance;
a journey has a stage."*

## A3 — The five kinds of surface

Every one of the 1,597 pages is exactly one of these. This is the taxonomy the
component system is built for.

| kind | job | count | example |
|---|---|---|---|
| **Editorial** | make somewhere desirable | 1,520 | `/portrait/kenya`, `/places/kenya/*`, `/stories` |
| **Index** | let somebody choose | 8 | `/atlas`, `/places`, `/tourism/`, `/meet` |
| **Instrument** | let somebody compose or compute | 4 | `/journey`, `/journey-fund`, `/compare` |
| **Trust** | say what is true and who is responsible | 6 | `/terms`, `/privacy`, `/accessibility`, `/how-it-works` |
| **Operator** | the Kamerun ground operation's own front | 5 | `/cameroon`, `/about`, `/pricing`, `/services`, `/contact` |

**The operator surfaces are a separate product** and the audit found them
sharing a masthead class with Afrinkong's. That is the first thing the shell
work must separate.

---

## D — Page-family architecture

Six families, six generators. This is where every visual decision has to land.

### D1 · Place — 1,405 pages · `places.py` · **the whole site by volume**

The single most consequential family and the least designed-for: 88% of the
site, one stylesheet of 258 lines, one masthead shared with portraits.

| | |
|---|---|
| does well | best-connected surface on the site — links up to country, portrait, places index, siblings, and now `/tourism/<c>` |
| does badly | no visual distinction between a two-paragraph place and a substantial one; the sibling list is the same twelve for every place in a country |
| next step | present |
| **verdict** | **redesign in place** — highest leverage per line of CSS in the repository |

### D2 · Country — 51 pages · `home.py`

| | |
|---|---|
| does well | the four depths block now exists; region strip, calendar, operator block, window |
| does badly | 26 distinct type sizes in `country.css` for one template; 10 breakpoints |
| next step | present — "Begin" plus the four depths |
| **verdict** | **conform to the system** |

### D3 · Portrait — 54 pages · `story.py`

| | |
|---|---|
| does well | 16 sections, complete without JavaScript, richest reading on the site |
| does badly | reachable from the country page only since this session; no next step at the end of a long read |
| **verdict** | **promote.** This is the most under-used asset Afrinkong owns |

### D4 · Tourism — 56 pages · `render.py`

| | |
|---|---|
| does well | the only page that prices anything; now has a way out |
| does badly | titled "all 27 experiences" and reads as a catalogue; `tourism.css` is GENERATED from `cameroon.html`'s `<style>` block, so it cannot be edited directly |
| **verdict** | **redesign, and fix the generation chain first.** The hand-edit at 1140px is a standing warning |

### D5 · Trans Afrique — 9 pages · `transafrique.py`

| | |
|---|---|
| does well | a genuine product with its own identity and 981 lines of its own CSS |
| **verdict** | **preserve the identity, adopt the shell.** Instruction 5 exactly |

### D6 · Journey Fund — 2 pages + landing · `fund.py`

| | |
|---|---|
| does well | the only surface with a live state; the region-tone system; the disclosure discipline |
| does badly | `LANDING_TEMPLATE` is printf-style, so a bare `%` breaks the build — twice, historically |
| **verdict** | **the reference implementation.** Everything else conforms to what this proves |

### D7 · Instruments and indexes — 12 pages

`/journey` (1,512 lines of JS, URL-as-state, shareable), `/atlas` (971),
`/meet` (304), `/stories`, `/compare`, `/wonders`, `/places`, `/tourism/`.

**Verdict: preserve wholesale.** These are the best work in the repository and
none of them is the problem. What they need is a shared shell and a consistent
way in and out — not redesign.

---

## The 1,597 pages, dispositioned

| disposition | pages | what it means |
|---|---|---|
| **preserve** | 12 | the instruments and indexes. Shell only |
| **conform** | 1,510 | places, countries, portraits, tourism — adopt shell, tokens, components; keep content and structure |
| **redesign** | 56 | tourism pages: the catalogue becomes a priced proposition |
| **promote** | 54 | portraits: from unreachable to a named destination in EXPLORE |
| **separate** | 5 | operator pages: their own shell, explicitly not Afrinkong's |
| **defer** | 0 built | the FUND surfaces, TRAVEL surfaces, wallet, auth — designed, not built |
| **remove** | 0 | nothing is deleted. `tourism/compare.html` stays as tooling |

**Nothing is removed.** The audit found no dead pages, no orphans and no broken
links. The site's problem has never been that it contains too much.

---

## The four rules the architecture must not break

Instruction 16, restated as constraints on this phase:

1. **Never patch generated output.** Every one of the 1,597 pages is generated.
   A change made to HTML is a change that survives until the next build.
2. **`tourism.css` and `country.css` are generated.** The other fifteen
   stylesheets are source and may be edited directly.
3. **`tourism.css` carries a documented hand-edit** (1140px, browser-verified)
   that `render` reverts. The design system must move that rule into the shell
   the generator reads, or the migration will silently undo a real fix.
4. **Late passes edit built HTML.** Any new pass must join the `cmd_all` chain
   or one build erases it, and no check will notice.
