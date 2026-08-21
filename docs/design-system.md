# C — Visual design system · E — Component architecture

**Specification. Not implemented.** `styles/tokens.css` and `styles/states.css`
exist and are the first two pieces; everything else here is designed and
unbuilt.

---

## C0 — The governing idea

> **The site should feel expensive because it is confident, not because it is
> decorated.**

Three facts from the audit decide the direction, and all three are in the
site's favour:

1. **Four `border-radius` values exist, three of them structural.** The site
   has never had rounded cards. It is a *sharp, ruled, editorial* system
   already — and that is exactly the idiom that reads as premium and as
   institutional at the same time.
2. **The palette is a material vocabulary, not a brand palette.** `basalt`,
   `canopy`, `ember`, `raffia`, `dust`, `sand`, `gold` — African materials,
   already in use. Nothing needs inventing.
3. **The photography is first-party**, 629 registered assets with provenance.

So the direction is not "make it futuristic". It is: **take the editorial
system that is already latent in this repository and make it deliberate.**
Rules, not shadows. Type, not chrome. Photography, not decoration.

### What this system explicitly refuses

Instruction 10, made checkable:

| refused | why |
|---|---|
| gradients as surface | the palette is material; a gradient is a screen effect |
| glassmorphism | a 2021 idiom that will date the site by 2027 |
| glow, particles, animated AI motifs | gimmick, not future |
| oversized rounded cards | the site has never had them; adding them is regression |
| dashboard aesthetics on editorial pages | a portrait is a long read, not a console |
| badge inflation | the state language has 6 tones and that is the whole budget |
| shadow-based elevation | 22 shadows exist and the system will end with **at most 2** |

---

## C1 — Type

The token layer already declares the scale, measured out of 840 declarations.
**183 distinct sizes migrate onto eleven.**

| token | value | role |
|---|---|---|
| `--fj-t-label` | 10px, `.14em` tracked, mono, upper | the eyebrow. 47% of all declarations were already this |
| `--fj-t-micro` | 12px | fine print |
| `--fj-t-small` | 13.5px | captions, notes |
| `--fj-t-body` | 15px | running text |
| `--fj-t-body-lg` | 17px | lede |
| `--fj-t-lead` | `clamp(19px, 1.9vw, 25px)` | section intro |
| `--fj-t-title` | `clamp(21px, 2.4vw, 30px)` | card and section titles |
| `--fj-t-display` | `clamp(28px, 3.6vw, 48px)` | page titles |
| `--fj-t-hero` | `clamp(30px, 4vw, 54px)` | hero |
| `--fj-t-mega` | `clamp(48px, 7vw, 88px)` | the homepage, and nothing else |

**Three faces, already in the repository:** a display face, a text face, and a
mono. The mono is not decorative — it carries every label, every figure and
every state chip, and it is what makes the system read as an instrument rather
than a brochure.

**Measure stays at 65ch.** Running text has one width across the whole site.

### The rule that must survive

> **A figure is never the largest thing on the screen.**

Already enforced on the Journey Fund by a browser check. It becomes global: no
price, no point total, no progress figure may exceed `--fj-t-title`. This is a
trust decision wearing a typographic costume — a large number is a sales page,
a small one beside a large place name is a travel company.

## C2 — Space, grid, containers

- **4px base.** Ten steps, 4 → 144.
- **One container**, `max-width: 1180px`, `padding: 0 5vw` (22px under 760).
  `.af-frame` already does this and is the closest thing to a global primitive.
- **Grid is 12 columns** on the container, but editorial pages use *asymmetric
  splits* (7/5, 8/4) rather than centred columns — the composition idiom the
  portraits already use.

## C3 — Breakpoints

**31 distinct → four.** Three already carry the majority.

```
--fj-bp-s   560px      phone
--fj-bp-m   760px      large phone / small tablet
--fj-bp-l   900px      tablet / small laptop
--fj-bp-xl  1100px     laptop and up
```

**Custom properties do not work inside media queries.** `@media (max-width:
var(--fj-bp-m))` is invalid CSS and fails silently. These four are therefore
*canon for a check to assert*, not a mechanism to write against — recorded in
`tokens.css` and repeated here because it is the single easiest way to break
the migration.

## C4 — Border, radius, elevation

| | decision |
|---|---|
| **rules** | `1px solid var(--c-border)` is the default; `2px solid var(--c-accent)` is a section opening. Two weights, no more |
| **radius** | `0` everywhere except `50%` for a dot and `2px` for a control. **No new radius may be introduced.** |
| **shadow** | **two, total.** One for a floating control, one for a modal. 22 today → 2 |
| **elevation** | expressed by *ground colour and rule*, not by shadow. `--c-bg` → `--c-sand` → `--fj-basalt` is the entire z-axis |

## C5 — Colour

No new palette. The existing material names, plus the six state tones already
built in `states.css`.

**Region tone is a system, not a decoration.** The Journey Fund already takes
the region colour of the destination being planned. That mechanism —
`tourism/regions.json` → payload → `--jf-tone` → components — should extend to
country, place and portrait pages. *A Kenya page is East Africa's teal because
the page is about Kenya.* This is the single most distinctive thing in the
existing system and it is currently used on three pages.

## C6 — Photography

Instruction 11. The library is foundational, and the rules are mostly enforced
already:

| rule | state |
|---|---|
| every hero bounded | **enforced** — `heroes.js`, 1,416 heroes, 0 unbounded |
| provenance registered | **enforced** — 629 assets |
| focal point preserved | built (`focal.py`), applied per asset |
| `width`/`height` always set | **44 missing** — Phase 9 |
| `loading` always explicit | **2,940 unset** — Phase 9, in the late passes |
| `srcset` | 26% — the largest remaining perf item |

**Art direction, not background.** Three aspect roles: `21:9` band, `4:5`
portrait window, `4:3` tile. A photograph is chosen for the role, not cropped
into it after the fact — `imaging.cdn_url` already takes an aspect and a focal
point.

## C7 — Motion

One duration, one easing, already in the token layer. **`working` is the only
state tone that animates.** Editorial motion — a section revealing — is
composition and is decided per surface, not tokenised.

`prefers-reduced-motion` collapses every duration to 1ms in the token layer, so
a component cannot forget it.

---

# E — Component architecture

**Twenty-four prefixes and fourteen card classes become eleven primitives.**

The rule from instruction 2: *build a small number of exceptionally strong
primitives and compose the site from them.* Everything below carries the `af-`
prefix, which is the only shared vocabulary that already exists.

| primitive | replaces | notes |
|---|---|---|
| `af-shell` | 10 mastheads, 7 footers | platform bar + optional product band |
| `af-frame` | 6 container idioms | **exists** |
| `af-zone` | section wrappers across 8 sheets | **exists**; carries ground colour |
| `af-head` | section headers | **exists** — numbered eyebrow + title |
| `af-btn` | 6 button classes | **exists** — `--solid`, `--quiet`, and no third |
| `af-state` | nothing (there was nothing) | **exists** — 6 tones, 72 sentences |
| **`af-card`** | 14 card classes | one card, four aspects, optional figure |
| **`af-tile`** | grid item idioms in 5 sheets | a card with no prose |
| **`af-field`** | 94 unstyled form rules | label, control, hint, error — the error state is the state language |
| **`af-table`** | 15 table rules | figures right, `tabular-nums`, scrolls in its own container |
| **`af-empty`** | 56 ad-hoc empties | the one state that already had a name |

### The card, specified once

The audit found a card invented at least six times. One component:

```
af-card
├── af-card-fig      optional. 21:9 | 4:3 | 4:5 | none
├── af-card-eyebrow  --fj-t-label
├── af-card-title    --fj-t-title
├── af-card-line     --fj-t-small, muted
└── af-card-foot     optional: af-state chip, or a figure
```

**A card is never a link with a shadow.** It is a rule, a photograph and three
lines of type. Hover changes the ground, not the elevation.

### What stays special, deliberately

Instruction 2 says components either conform or are *deliberately identified as
a special product surface*. These are the special ones, and the list is closed:

| surface | why it is special |
|---|---|
| the atlas map | geography as interface; one state object, one render |
| the journey builder | four questions, URL-as-state, its own composition |
| the window (country outline masks) | the site's signature |
| the Trans Afrique route map | cartography, not a component |
| the Travel Goal panel | it is the reference implementation of the state language |

Everything else conforms.

---

## How this is enforced

A design system with no check is a document. `tools/design-checks.js` has 17
checks today. The system adds:

1. every stylesheet uses only the four canonical breakpoints
2. no `font-size` outside the eleven tokens (allow-list for the five special
   surfaces)
3. no `border-radius` beyond `0`, `2px`, `50%`
4. at most two `box-shadow` values site-wide
5. no `af-card` variant beyond the four aspects
6. **every page declares a `body` class naming its family** — 1,529 pages have
   none today, and this is the check that unblocks styling by kind
7. the region-tone mechanism reads `regions.json` and never a literal

Each must **fail against the tree as it stands** before it is trusted. That has
been the standard all session and it does not relax for design work.
