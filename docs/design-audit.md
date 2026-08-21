# Design audit — where the architecture exists in code and not on screen

**Item 1 of the design brief.** Measured, not asserted: every figure below comes
from the repository as it stands.

The conclusion first, because it is the whole finding:

> **The economic system can express 39 distinct states. The website can express
> one, and it is "empty".**

---

## 1 — The state gap

The model built over this session distinguishes:

| system | states |
|---|---|
| ledger kinds | 11 |
| payment states | 7 |
| compliance states | 11 |
| booking states | 7 |
| risk decisions | 3 |
| **total** | **39** |

Scanned across every HTML and CSS file in the repository:

| state | files that express it |
|---|---|
| `empty` | 56 |
| `loading` · `pending` · `confirmed` · `cancelled` · `unavailable` · `restricted` · `error` · `success` · `skeleton` | **0** |

**A customer cannot be shown a pending payment, a held booking, a restricted
account, a cancelled journey or a failure, because no visual language for any
of them exists.** The brief asks for nine states designed. The site currently
has one.

This is not a styling gap. It is the reason the product feels like a magazine
with a calculator attached: **a magazine has no states.**

---

## 2 — There is no design system. There are fifteen.

**9,876 lines of CSS across 15 stylesheets**, each with its own type scale:

| stylesheet | lines | distinct `font-size` values |
|---|---|---|
| `gateway.css` | 3,501 | **88** |
| `tourism.css` | 616 | 50 |
| `transafrique.css` | 981 | 47 |
| `kamerun.css` | 408 | 41 |
| `journey.css` | 988 | 40 |
| *(ten more)* | | 13–28 each |

**418 distinct font-size declarations site-wide.** There is no type scale —
there are fifteen, and none of them is authoritative.

### Tokens

**52 custom properties in total**, the most-used appearing five times. That is
not a token system; those are local variables with a hyphen in the name. A real
system would have a dozen tokens used hundreds of times, not fifty used twice.

### Breakpoints

**45 distinct breakpoints.** The most common is 900px (43 uses), then 760px
(25), 560px (24) — followed by 820, 640, 520, 1000, 880 and thirty-seven
others. Mobile behaviour is not designed; it is negotiated separately in every
file.

### Components

Twelve distinct `-card` classes across five prefixes (`jn-`, `sx-`, `wo-`), four
button classes. **A card has been invented at least three times**, and none of
the three knows about the others.

---

## 3 — 96% of pages have no template identity

| body class | pages |
|---|---|
| *(none)* | **1,526** |
| `po-body` | 53 |
| `tf-body` | 9 |
| `tr-body` | 3 |
| `jf-page` | 3 |
| others | 3 |

1,526 of 1,597 pages carry no class on `<body>`. Nothing in the markup says
what kind of page it is, so nothing can be styled *by kind* — which is why
every stylesheet re-specifies everything.

---

## 4 — The information architecture is place-organised; the product is journey-organised

Primary navigation, as a visitor sees it:

> The Atlas · Trans Afrique · Journey Fund · Stories · Meet Africa · Every place

**Five of six are content destinations. One is a product surface.** The brief's
spine —

```
Discover → Plan → Fund → Book → Experience
```

— appears nowhere in the navigation, so a visitor cannot see that a path
exists, let alone where they are on it.

The homepage does better than the nav: seventeen sections running *feel →
moments → scale → wonders → destinations → cities → year → now → plan →
stories → decide*. That is a genuine desire-first editorial spine and it should
survive. **The nav does not reflect it**, and the two are the same product
telling two different stories.

---

## 5 — Where architecture exists and is invisible

The specific instances, each verifiable:

| built | visible? |
|---|---|
| Travel Goal progress, projection, funded state | **was permanently 0%** — fixed this session; the reader can now record what they have set aside |
| eleven ledger kinds with per-lot provenance | no surface |
| wallet: available / reserved / pending / restricted | no surface |
| booking: requested → reserved → confirmed → redeemed | no surface |
| price lock on a reserved booking | no surface |
| repurchase quote, non-standing, with deduction | no surface |
| wind-down: redeem → alternative → migrate → repurchase | no surface |
| risk holds and manual review | no surface |
| recovery tiers scaled by holding | no surface |
| programme terms, versioned and immutable | no surface |

Most of that list *should* have no surface yet — issuance is off and Z's
boundary is deliberate. **But the design system for them has to exist before
they are switched on**, or each will arrive as an ad-hoc screen and the
fifteen-stylesheet problem will repeat inside the product.

The Travel Goal is the exception and the proof: it was **live, correct and
invisible** — rendering a progress figure that could never move.

---

## 6 — What I recommend, in order

**A — the token layer.** One scale, one set of tokens, one breakpoint ladder.
Not a redesign: a substrate the fifteen stylesheets can be migrated onto
incrementally. Without this, everything after it multiplies by fifteen.

**B — the state language.** Nine states designed once — empty, loading,
pending, confirmed, cancelled, unavailable, restricted, error, success — as
components rather than per-page CSS. This is the largest gap and the cheapest
to close, because there is nothing to migrate.

**C — the navigation.** Make the spine visible: Explore / Plan / Fund / Travel.
This is the one change a visitor notices immediately, and it is the smallest
diff — but it touches every page, so it wants approval before it is made.

**D — the component set.** Destination card, journey card, itinerary timeline,
goal progress, price breakdown, readiness. One of each, replacing twelve.

**E — the authenticated shell.** Designed last, deliberately. It cannot be
built honestly until the states in B exist, and it must not be built at all
until counsel answers — but the *design* can be ready so that activation is a
switch rather than a project.

---

## What I have NOT done

- Not redesigned anything. This is the audit the brief asks for first; C in
  particular changes every page and should be approved rather than assumed.
- Not touched the economic rules, the ledger, the legal model or the
  architecture. The brief puts the design role *above* that work, not through
  it.
- Not written a "2036 design system" on spec. The token layer and the state
  language are the parts that must exist before any of it means anything, and
  inventing a visual language before those exist is how fifteen stylesheets
  happened the first time.
