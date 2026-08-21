# F — Interaction principles · G — Premiumisation strategy

**Specification. Not implemented.**

---

# F — Interaction principles

## F1 — The five rules

**1 · Motion explains a relationship or it does not happen.**
Instruction 14. The legitimate cases are all the same shape — *this came from
that*:

| transition | what motion says |
|---|---|
| destination → journey | the place you chose is the journey's first stage |
| plan → goal | this figure became that target |
| goal → progress | this is how far along it is |
| card → detail | the thing you pressed opened |

Anything else — an arrival fade, a counting number, a parallax — is decoration
and is refused. A figure that counts up on arrival is a figure performing at
you, and the Journey Fund already says so in its own stylesheet.

**2 · Motion never delays.** The interface is usable at the first frame. No
transition gates an action.

**3 · `working` is the only state that animates.** A waiting state must not:
it is not progressing, and a spinner over *"we need you to confirm"* is a lie
told in motion. This is already enforced in `states.css`.

**4 · Reduced motion is honoured in the token layer**, not per component, so a
component cannot forget it.

**5 · Every surface has one next step, and it is visible without scrolling to
the end.** Instruction 6. A page that leaves a visitor asking *"what now?"* has
failed regardless of how it looks.

## F2 — The next step, per family

Instruction 6's chain, made concrete. Bold is what this session already built.

| surface | the one next step | state |
|---|---|---|
| homepage | choose somewhere | built |
| `/atlas` | open a country | built |
| `/places/<c>/<p>` | **what a journey to this country costs** | **built** |
| `/portrait/<c>` | see the places | **missing** — a 16-section read that ends |
| `/<country>` | **the four depths, then build a journey** | **built** |
| `/tourism/<c>` | **build a journey, or the rest of the country** | **built** |
| `/journey` (composed) | **price it in the Journey Fund** | **built** (tier now carries) |
| `/journey-fund` | **compose a journey**, or talk to us | **built** |
| `/stories` | go to the destination the story is about | **missing** |
| `/meet` | go to the country | partial |
| `/trans-afrique` | build the crossing | built |

**Two gaps remain: the portrait, and Stories.** Both are editorial surfaces
that end without an exit — the same defect that was found on `/tourism/<c>`,
and the same fix.

## F3 — Responsive is a composition, not a reflow

Instruction 13. Four intentional compositions, not one design that shrinks.

| width | the change that matters |
|---|---|
| **≤ 560** | hero crops to `4:5`; navigation collapses to the mark + index; four-up grids become one; the state chip goes full width |
| **≤ 760** | product band and platform bar merge into one row; three-up becomes one |
| **≤ 900** | asymmetric splits (7/5) become stacked; four-up becomes two-up |
| **> 1100** | the container stops growing at 1180px. **The page does not fill a 2560px screen** — a measure of 65ch is the point |

Specific attention, per instruction 13:

- **hero cropping** — art direction per breakpoint, not one crop scaled
- **maps** — the atlas and route maps need touch targets ≥ 44px; the country
  hit-discs already exist (54 of them)
- **tables and itineraries** — scroll in their own `overflow-x` container; the
  page body never scrolls sideways
- **touch targets** — 24px minimum, 44px for anything on a map. The Journey
  Fund masthead already documents having measured this
- **focus states** — currently unmeasured. Every interactive element needs a
  visible focus ring that is not the browser default over a photograph

## F4 — Forms

94 form rules exist and none is a component. `af-field` carries label, control,
hint and error — and **the error state is the state language**, not a red
border invented per form. That is the point of having 72 sentences.

---

# G — Premiumisation strategy

## G1 — What premium means here

The target in instruction 3: *international premium travel platform + African
authority + futuristic digital product.*

Those three pull apart if you chase them with styling. They converge on one
thing:

> **Premium is the visible evidence that somebody decided.**

A generic site is generic because nothing on it was chosen — the type is the
default, the spacing is whatever, the photograph is whatever was available. The
opposite of generic is not *more*; it is *specific*.

This site already has the specifics: 629 first-party photographs with
provenance, 54 country outlines projected from Natural Earth, five region tones
read from a data file, a rate card that no page may contradict, and 1,405 place
pages written one at a time. **The premiumisation task is to stop hiding
them.**

## G2 — Africa without clichés

Instruction 3 is explicit that Africa is expressed through photography,
geography, editorial voice, stories, destinations, people and journeys —
**not decoration.**

| do | do not |
|---|---|
| the country's own outline as a window | pattern borders, kente motifs, mudcloth textures |
| region tone from `regions.json` | "warm African" gradients |
| a named operator, their base, since when | stock "local guide" imagery |
| 581 proper names read from the dataset's own sentences | invented place-name typography |
| the material palette — basalt, canopy, raffia | orange-and-acacia-silhouette |

The window — a photograph masked into a country's own borders — is the single
strongest device the site owns. It is the site's signature, it is geographic
rather than decorative, and it is currently used on the gateway and country
pages only.

## G3 — The eight representative surfaces

Instruction 17's Phase 8 list, with what "excellent" means for each:

| surface | the standard it must reach |
|---|---|
| **homepage** | establishes the world, not the feature list. Desire → confidence → action, in that order. The 17-section desire-first spine survives |
| **country** | one Kenya at four depths, visibly. The window, the year, the operator, the four ways in |
| **place** | 1,405 of these. A place is a *reason to go somewhere*, and the page should read as an argument, not an entry |
| **tourism** | stops being a catalogue of 27. Becomes: this is what a journey here costs and what it contains |
| **portrait** | the richest reading on the site. It needs an ending |
| **Trans Afrique** | keeps its identity; adopts the shell. The proof that the system allows product character |
| **journey builder** | already excellent. Needs the shell and nothing else |
| **Travel Goal** | already the reference implementation. Everything else conforms to what it proves |

Only after all eight are excellent does the system propagate. **1,405 place
pages are not redesigned until one place page is right.**

## G4 — The trust layer

Instruction 15. Trust from clarity, never from badges.

**No invented certifications, no trust seals, no "5-star" marks, no partner
logos we do not have.** What the site says instead, and mostly already does:

| claim | where it is true |
|---|---|
| Wankong LLC is the legal entity; Afrinkong is the trade name | the company line, on 1,511 pages |
| Afrinkong holds none of the customer's money | the Journey Fund says it in those words |
| Nothing is for sale yet | the Travel Goal panel is tagged *planning only — not for sale* |
| Every figure comes from one rate card | `rates.drift()` proves no page carries a figure the card cannot account for |
| Park fees, permits and entrance charges are extra, at cost | stated on the page that gives the figure |
| Our own ground operation in three countries; named partners elsewhere | the operator block, per country |

**The gap:** there is no "About Afrinkong". `/about` belongs to the Kamerun
operator. A visitor who wants to know who they are dealing with has nowhere to
go, and that is a trust hole no amount of design closes.

## G5 — What premiumisation must not cost

The four refusals from the mandate, restated as tests:

| never sacrifice | the test |
|---|---|
| the economic architecture | `points-checks` stays at 245+; no economic file is edited for visual reasons |
| legal clarity | no disclosure is shortened, moved below a figure, or set smaller than the figure |
| accessibility | contrast, focus and target size are checked *before* a surface is called done |
| performance | page weight is measured per surface; no surface gets heavier without a recorded reason |

The last one has teeth: `docs/weight-baseline.md` exists, and a premium
redesign that adds 400KB of webfont to a page that loads in 1.2s has made the
product worse in the one dimension every international traveller on a slow
connection actually feels.
