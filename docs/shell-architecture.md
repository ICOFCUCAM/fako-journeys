# The Afrinkong shell — Phase 5 + 6

**The single architectural frame the whole experience fits into.** Navigation,
header, footer, page identity, active state and product-level identity, owned
in one place.

---

## The settled decisions

| question | decision |
|---|---|
| Journey Fund | **PLAN** |
| Every place | **→ Destinations** |
| TRAVEL in navigation | **no, not yet** — bookable travel is not operational |
| FUND in navigation | **no, not yet** — issuance and the wallet are gated |
| About page | **`/about-afrinkong`** |

The conceptual spine stays **EXPLORE → PLAN → TRAVEL**. The public navigation
exposes **EXPLORE · PLAN**. That is the honest subset, and TRAVEL joins it the
day something is bookable without any architecture changing.

---

## The navigation

```
EXPLORE                          PLAN
├── Destinations   /places       ├── Journey Planner  /journey
├── Countries      /tourism/     ├── Journey Fund     /journey-fund
├── The Atlas      /atlas        └── Travel Goal      /journey-fund#jf-goal
├── Stories        /stories
├── Meet Africa    /meet
└── Trans Afrique  /trans-afrique

utility:  Search (⌘K)  ·  About Afrinkong  /about-afrinkong
```

**Travel Goal is a section of the Journey Fund today**, so it links to the
anchor rather than pretending to be a page. It becomes its own surface when
there are accounts to hold goals — and the link changes in one file.

---

## The shell, structurally

Two rows, and **the second row is contextual**:

```
┌─────────────────────────────────────────────────────────────┐
│  ◈ AFRINKONG        EXPLORE   PLAN          ⌘K   About      │  platform
├─────────────────────────────────────────────────────────────┤
│  Destinations · Countries · The Atlas · Stories · Meet ...   │  area
└─────────────────────────────────────────────────────────────┘
   ▲ the children of the area THIS page belongs to
```

A place page shows EXPLORE's children. The journey builder shows PLAN's. A
visitor always sees where they are and what else is in the room they are
standing in.

### Why not a dropdown

**The shell must work with no JavaScript.** `portrait.js` states the site's
rule in its own header — *the page is complete before the script arrives* — and
1,596 pages currently satisfy it. A hover menu fails that, fails touch, and
fails keyboard without work that a two-row bar does not need.

The contextual second row is also more useful than a dropdown: it is always
visible, so the area's contents are discovered rather than hunted for.

### Product identity — the third level

Instruction 5. Trans Afrique, the Journey Fund and the journey builder keep
their character **beneath** the platform bar, not instead of it:

| level | who | what |
|---|---|---|
| platform | every page | the mark, the two areas, search, About |
| area | every page | the current area's children |
| **product** | Trans Afrique · Journey Fund · Journey Builder · The Atlas | its own band: own name, own sub-navigation, own tone |
| **operator** | `/cameroon` `/about` `/pricing` `/services` `/contact` | **a different shell.** Kamerun's own front door |

The product band is where identity lives, and it is optional. Most of the 1,405
place pages have no product band — they are Afrinkong, plainly.

---

## Mobile

| width | behaviour |
|---|---|
| **> 900** | both rows, full |
| **760–900** | platform row full; area row scrolls horizontally within its own container |
| **≤ 760** | one row: mark + `Menu`. A `<details>` discloses both areas with all children, as a list |

`<details>`/`<summary>` because it opens with no JavaScript, is keyboard
operable by default, and announces its own expanded state. No script, no ARIA
that has to be kept in sync with a class.

**Touch targets ≥ 44px in the disclosed menu**, 24px minimum in the bars.

---

## Active state

Three levels, all derived rather than authored per page:

```
<body class="af af--place" data-area="explore">
  <a href="/places" aria-current="page">      the exact page
  <a href="/places" class="is-here">          the area
```

- `aria-current="page"` — the page you are on. Announced by screen readers.
- `data-area` on `<body>` — which of the two areas is current, so the area row
  can render and the platform bar can mark itself without JavaScript.
- **A link to the page you are already on is not offered.** `colophon_foot()`
  already does this and the shell follows it.

---

## Page-family mapping

| family | pages | `body` class | area | product band |
|---|---|---|---|---|
| places | 1,405 | `af--place` | explore | — |
| tourism | 56 | `af--tourism` | explore | — |
| portrait | 54 | `af--portrait` | explore | — |
| country | 51 | `af--country` | explore | country name |
| trans-afrique | 9 | `af--crossing` | explore | **Trans Afrique** |
| journey-fund | 3 | `af--fund` | plan | **Journey Fund** |
| journey builder | 1 | `af--journey` | plan | **Build a journey** |
| atlas | 1 | `af--atlas` | explore | **The Atlas** |
| meet · stories · wonders · places index · compare | 6 | `af--index` | explore | own name |
| homepage | 1 | `af--home` | — | — |
| trust | 6 | `af--trust` | — | — |
| **operator** | 5 | `af--operator` | — | **Kamerun's own shell** |

**1,529 pages gain a `body` class.** This is the cheapest change in the
programme and it is what makes styling by kind possible at all.

---

## How ten mastheads become one

| today | pages | becomes |
|---|---|---|
| `pl-mast` | 1,461 | `af-shell`, area=explore |
| `fj-mast` (tourism) | 55 | `af-shell`, area=explore |
| `fj-mast` (operator) | 5 | **`af-shell--operator`** — separated |
| `mast` | 52 | `af-shell`, area=explore, product band = country |
| `jn-mast` | 17 | `af-shell`, product band = builder / Trans Afrique |
| `jf-mast` | 3 | `af-shell`, area=plan, product band = Journey Fund |
| `wa-` `mt-` `at-` `top` | 4 | `af-shell` |

**Ten classes → two**, and the second is a different company's.

The `.fj-mast` split is not cosmetic. Today one class serves Afrinkong's 55
tourism pages and Kamerun's 5 pages, which carry entirely different navigation
— so any change to it changes two products at once.

---

## Where it is built

Instruction 16: never change generated output without changing its source.

| piece | file | kind |
|---|---|---|
| markup | `tools/tourism/plate.py` → `shell()` | **source**, shared by every generator |
| styles | `styles/afrinkong.css` | **source**, linked by 1,596 of 1,597 pages |
| footer | `plate.colophon_foot()` | **source** — already shared, gains *Destinations* |
| adoption | 6 generators + 7 page writers | source |

**No new stylesheet.** `afrinkong.css` is already universal, so the shell costs
no additional request.

### The hazard to clear first

`styles/tourism.css` is generated from `cameroon.html`'s `<style>` block and
carries a browser-verified hand-edit at 1140px that the generator reverts to
1010px. The shell replaces that masthead entirely, which **removes the reason
the hand-edit exists** — the right moment to retire it rather than carry it
forward.

---

## Validation before propagation

The user's instruction: *do not propagate the navigation until the shell has
been validated.*

```
1  build the shell + its CSS                     nothing adopts it yet
2  adopt on ONE family — journey-fund (3 pages)  smallest, and the reference
3  full gates + browser + accessibility          on those 3
4  adopt on the remaining families               one at a time
5  full gates again, then propagate to places    1,405 pages last
```

Places is last precisely because it is 88% of the site: a shell defect found
there costs a full rebuild to correct.

### New checks the shell requires

Each must fail against the tree as it stands before it is trusted.

1. every page declares a `body` class naming its family
2. **at most two masthead classes site-wide** (`af-shell`, `af-shell--operator`)
3. every page in an area carries `data-area`, and it is one of the two
4. no page links to the page it is on
5. the navigation is identical on every page of a family — *no ten
   interpretations*
6. `Every place` appears nowhere; `Destinations` points at `/places`
7. `/about-afrinkong` exists and is reachable
8. the shell renders with no JavaScript
