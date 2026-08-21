# B — Navigation architecture

**PROPOSED, FOR REVIEW. NOT BUILT.** Instruction 18 is explicit: the final
navigation and page hierarchy are presented before any label changes. Nothing
in this document has been applied to a page.

---

## The correction that produced it

The first draft of this was a rename — *The Atlas → Explore, Stories → Explore,
Meet Africa → Explore.* **That is a navigation cleanup and it is the wrong
shape.** It flattens five named products into four generic words and calls the
loss a simplification.

Trans Afrique, Stories and Meet Africa are products with their own character,
built to a standard the rest of the site is measured against. The resolution:
**the areas are the spine, and the named products are first-class within
them.** One platform, multiple experiences.

---

## The spine

**EXPLORE · PLAN · TRAVEL.** Three areas, not four.

FUND is architecturally reserved and **absent from public navigation** until the
compliance gates clear. An area whose three children are all unreachable is a
sign on an empty room, and Afrinkong's whole economic discipline has been about
not making promises the product cannot keep.

---

## The proposed hierarchy

```
AFRINKONG

EXPLORE ─────────── discover Africa
├── Destinations ................ /places      1,405 place pages, 54 countries
├── The Atlas ................... /atlas       geography as interface
├── Countries ................... /tourism/    54 country fronts
├── Stories ..................... /stories     the story graph
├── Meet Africa ................. /meet        seven human questions × 22
├── Trans Afrique ............... /trans-afrique   the four crossings
└── The Wonders ................. /wonders

PLAN ────────────── turn discovery into a journey
├── Build a Journey ............. /journey     four questions, shareable
├── Journey Fund ................ /journey-fund   what it costs, and what it takes
│   ├── How it works ............ /journey-fund/how-it-works
│   └── Questions ............... /journey-fund/questions
└── Compare ..................... /compare

TRAVEL ──────────── actually go
└── (reserved — booking.js holds seven states with no surface)

──────────────────────────────────────────────────────────
About ......... /about-afrinkong   ← does not exist yet; see §Open 5
Trust ......... /terms /privacy /accessibility /how-it-works

RESERVED, NOT SHOWN
FUND → Travel Points → Travel Wallet → Travel Goals → redemption
```

### Per-country, the four depths

Already built this session, and the model the whole IA should follow:

```
/kenya ──────── overview ──── "why here"
   ├── /portrait/kenya ────── "the long read"
   ├── /places#kenya ──────── "the 26 things"
   └── /tourism/kenya ─────── "what it costs"
```

---

## What survives

| product | today | proposed | lost? |
|---|---|---|---|
| The Atlas | top level | EXPLORE › The Atlas | no |
| Trans Afrique | top level | EXPLORE › Trans Afrique | no |
| Stories | top level | EXPLORE › Stories | no |
| Meet Africa | top level | EXPLORE › Meet Africa | no |
| Every place | top level | EXPLORE › Destinations | **renamed** |
| Journey Fund | top level | PLAN › Journey Fund | no |

**Five named products, five still named.** The only rename is *Every place →
Destinations*, and it is proposed rather than assumed — see Open question 3.

What changes is that a visitor can see **Explore → Plan → Travel** exists,
which today nothing tells them.

---

## The shell, and why product identity survives it

The audit found **ten mastheads and seven footers**. The proposal is **one
shell with three levels of identity**:

| level | who gets it | what it means |
|---|---|---|
| **platform** | every page | the Afrinkong mark, the three areas, the index (⌘K), the footer with Wankong LLC |
| **product** | Trans Afrique, Journey Fund, the journey builder, the atlas | a product band **below** the platform bar: its own name, its own sub-navigation, its own tone |
| **operator** | `/cameroon`, `/about`, `/pricing`, `/services`, `/contact` | **a different shell entirely.** These are the Kamerun ground operation's pages |

The operator separation is not cosmetic. Those five pages currently share the
`.fj-mast` class with 55 Afrinkong tourism pages while carrying a completely
different navigation, so any change to that class changes two products at once.

---

## The seven open questions

These are decisions, not details, and they are why this is presented rather than
applied.

**1 · Does the Journey Fund belong to PLAN or FUND?**
It is a planner that holds nothing, which argues for PLAN. But "Fund" is the
word people will look for under FUND, and FUND does not exist yet.
*Recommendation: PLAN, and revisit when FUND is real.* Two front doors is how a
product loses one.

**2 · "Travel Goal" or "My Goals"?**
`travel-goal.js` says Travel Goal and the state language uses it. *"My Goals"
implies an account, and there are no accounts.*
*Recommendation: Travel Goal.*

**3 · "Every place" or "Destinations"?**
*Every place* is distinctive and honest — there are 1,405 of them.
*Destinations* is what an international traveller searches for.
*Recommendation: Destinations, with "every place we write about" as the
sub-line.* This one is genuinely a brand decision and I would take direction.

**4 · Does TRAVEL appear before anything is bookable?**
It has no surfaces at all. Showing it is a promise; hiding it makes the spine
invisible.
*Recommendation: show it, unlinked, as a stated third stage on the how-it-works
surface only — not as a clickable nav item.*

**5 · There is no "About Afrinkong".**
`/about` is the **Kamerun operator's** about page. A visitor who wants to know
who Afrinkong is has nowhere to go. This is a gap, not a design decision.
*Recommendation: a new surface. Needs a URL — `/about-afrinkong` is ugly.*

**6 · Trans Afrique keeps its own masthead — under the platform bar, or
instead of it?**
Two bars costs vertical space on a phone. One bar loses the product.
*Recommendation: platform bar collapses to a slim rule on product pages, with
the product band beneath it.*

**7 · ⌘K is currently the only thing holding the surfaces together.**
Under the new architecture it becomes a convenience rather than the
architecture. *No action — but worth stating, because it changes what the index
is for.*

---

## What must not happen

- **No area may appear whose children are unreachable.** FUND stays out.
- **No product identity is deleted to tidy the diagram.**
- **No navigation change ships without the shell.** Changing labels across
  1,597 pages while ten mastheads still exist would multiply the inconsistency
  rather than resolve it. The shell comes first; the labels come with it.
- **The operator's five pages do not get Afrinkong's navigation.** They are a
  different company's front door hosted on the same domain, and the footer
  already says so.
