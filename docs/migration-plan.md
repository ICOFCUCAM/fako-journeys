# H — Migration plan

**How 1,597 pages move onto one system without a rewrite, and without breaking
the engineering discipline instruction 16 protects.**

---

## H1 — The fact that decides the whole plan

> **Every one of the 1,597 pages is generated. There is no page a designer can
> edit.**

`cameroon.html` is hand-built and even it is rewritten by four late passes. So:

```
a visual change lands in    a generator  (6 of them)
                     or     a stylesheet (15 of 17 are source)
                     never  in HTML
```

This is better news than it sounds. **1,597 pages are reachable from 21
files.**

| what | files | writes |
|---|---|---|
| `places.py` | 1 | 1,405 pages |
| `home.py` | 1 | 51 pages + `country.css` |
| `render.py` | 1 | 56 pages + `tourism.css` |
| `story.py` | 1 | 54 portraits + `/stories` |
| `transafrique.py` | 1 | 9 pages |
| `fund.py` | 1 | 3 pages |
| `gateway.py` `journey.py` `atlas.py` `meet.py` `wonders.py` `trust.py` `enquire.py` | 7 | 12 pages |
| source stylesheets | 15 | all of it |
| **generated stylesheets** | **2** | `tourism.css`, `country.css` — **edit the generator, not the file** |

## H2 — Three hazards, named before they are hit

**1 · `tourism.css` is generated from `cameroon.html`'s `<style>` block.**
It carries a documented, browser-verified hand-edit at 1140px that the
generator reverts to 1010px. *Any `render` silently undoes a real fix and only
`git diff` says so.* **The migration's first task in that family is to move
that rule into the shell the generator reads.** Until then, check the file after
every regeneration.

**2 · Late passes edit built HTML.** `bound`, `srcset`, `sizeattr`, `modern`
and `library.rewrite` run at the end of `cmd_all` in a fixed order. Any new
pass must join that chain or one build erases it and no check notices. And a
*single* generator run does not run `company` or `graft`, so a lone
`build.py places` strips the company legal line from 1,405 pages.

**3 · `LANDING_TEMPLATE` in `fund.py` is printf-style.** A bare `%` anywhere in
it breaks the build — this has happened twice, once in the comment warning
about it.

## H3 — The order

Instruction 17's phases, with the dependency that determines them.

```
Phase 5   navigation architecture      ← PRESENTED, awaiting review
              │  cannot ship without the shell
Phase 6   visual system + shell        ← the unblocker
              │
   ┌──────────┼──────────┐
Phase 7    Phase 8    Phase 9
interaction premium    QA
```

### Phase 6 is the unblocker, and it starts with one line

**The body class.** 1,529 pages carry none, so nothing can be styled by kind.
Six generators, one line each:

```html
<body class="af af--place">      1,405
<body class="af af--country">       51
<body class="af af--tourism">       56
<body class="af af--portrait">      54
<body class="af af--crossing">       9
<body class="af af--fund">           3
<body class="af af--operator">       5   ← a different product
```

**This is the cheapest change in the entire programme and it unblocks
everything after it.** Cost: six edits, one full rebuild, one browser run.

Then, in order:

| step | files touched | risk |
|---|---|---|
| 1 · body class in 6 generators | 6 | none — additive |
| 2 · `af-shell` in a shared Python module, adopted by 6 generators | 7 | **high** — this is the masthead/footer consolidation |
| 3 · move the 1140px rule into the generator's shell source | 2 | medium — the known hazard |
| 4 · tokens applied: `afrinkong.css` first, then per-family | 15 CSS | low, incremental |
| 5 · breakpoints 31 → 4 | 15 CSS | medium — must be measured at each width |
| 6 · shadows 22 → 2, radius frozen | 15 CSS | low |
| 7 · `af-card` replaces 14 card classes | 6 CSS + 6 generators | **high** — do last, one family at a time |

### Phases 8 and 9

Phase 8 applies the system to eight representative surfaces and **stops**.
1,405 place pages are not touched until one place page is right.

Phase 9 is the full-site QA: the 44 images missing dimensions, the 2,940 with
no `loading`, the 26% `srcset` coverage, the two multiple-`h1` pages, the eight
heading jumps, focus states, contrast, touch targets, and page weight per
family.

## H4 — Verification, per step

Nothing merges without the full gate suite. The suite grows with the system:

```
existing   245 points · 31 library · 112 journey · 64 fund · 17 design
            36 goal · 8 link · 25 state · 55 pages · heroes · provenance
            259 browser

added       every page declares its family          (the body-class check)
            one shell: ≤2 masthead classes site-wide
            only the four canonical breakpoints
            no font-size outside the eleven tokens
            radius ∈ {0, 2px, 50%}
            ≤2 box-shadow values
            region tone read from regions.json, never a literal
            every surface has a next step
```

**Every new check must fail against the tree as it stands before it is
trusted.** That standard has held all session — 51 dangling ARIA references, a
tier that never carried, four broken graph edges and three state defects were
all found by writing the check first and watching it fail. It does not relax
because the work is now visual.

## H5 — The disposition of all 1,597 pages

| disposition | pages | families | what happens |
|---|---|---|---|
| **preserve** | 12 | instruments and indexes | shell only. `/journey`, `/atlas`, `/meet`, `/stories`, `/compare`, `/wonders`, `/places`, `/tourism/`, the trust pages |
| **conform** | 1,510 | places 1,405 · countries 51 · tourism 56 (minus redesign overlap) · portraits 54 | body class, shell, tokens, components. Content and structure unchanged |
| **redesign** | 56 | tourism | the catalogue of 27 becomes a priced proposition. **Fix the CSS generation chain first** |
| **promote** | 54 | portraits | from linked-by-nothing to a named destination in EXPLORE, with an ending |
| **separate** | 5 | operator | `/cameroon`, `/about`, `/pricing`, `/services`, `/contact` get their own shell. They are a different company's front door |
| **defer** | 0 built | FUND, TRAVEL, wallet, auth | designed, unbuilt, and **absent from navigation** until the gates clear |
| **remove** | **0** | — | nothing is deleted |

**Nothing is removed.** The audit found no dead pages, no orphans, no broken
links and no unstyled product surfaces. The site's problem has never been that
it contains too much — it is that 24 vocabularies describe it.

### One page needs creating

**There is no "About Afrinkong".** `/about` is the Kamerun operator's. A
visitor who wants to know who they are dealing with has nowhere to go. That is
a trust hole, not a design preference, and it is the only *new* page this
architecture requires.

## H6 — What this plan deliberately does not do

- **It does not redesign 1,597 pages.** It redesigns eight and propagates.
- **It does not touch the economic model, the ledger, the compliance ladder or
  any legal decision.** No file under the points, buyback, transfer, risk,
  account or booking modules is edited for a visual reason.
- **It does not activate anything.** The programme stays `DRAFT`.
- **It does not add a navigation area whose children are unreachable.**
- **It does not begin before the navigation is reviewed.** Instruction 18.
