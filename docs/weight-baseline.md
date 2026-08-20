# The first-party image baseline

Measured 20 August 2026 by `tools/weigh.js`, on a GitHub runner with open
network, at a 390×844 viewport at 3× — the phone the budget checks use. Bytes
are what crossed the wire for image responses, not decoded size.

"Before" is the same page at `c26c33a^`, the commit before the rewrite, served
from a git worktree so the only variable is where the photographs come from.

## What was measured

| page | before | after | change | image requests |
|---|---:|---:|---:|---|
| `/algeria` | 0.54 MB | 0.54 MB | 0% | 3 → 3 |
| `/angola` | 0.38 MB | 0.38 MB | 0% | 3 → 3 |
| `/tourism/algeria` | 1.88 MB | 1.86 MB | −2% | 8 → 8 |
| `/tourism/angola` | 1.13 MB | 1.07 MB | −5% | 8 → 8 |
| `/portrait/algeria` | 3.58 MB | 3.58 MB | 0% | 4 → 4 |
| `/places/algeria/a-thousand-kilometres-of-mediterranean` | 3.76 MB | **0.07 MB** | **−98%** | 2 → 2 |
| **total** | **11.27 MB** | **7.49 MB** | **−34%** | |

## Do not quote the −34%

It is arithmetically true and it is one page wearing a disguise. Of the 3.78 MB
saved across six pages, 3.69 MB came from `/places/algeria/…` alone. Four of
the six pages did not move at all.

That is not a fault in the measurement. It is what a nineteen-photograph
migration looks like when each page carries twenty-seven.

## The three cases, which is the actual finding

**1. A migrated photograph in the first screen, previously unbounded.**
`/places/algeria/…` asked for this:

    https://images.unsplash.com/photo-1631396388004-f7415e1420d0

No width parameter, so Unsplash served the full-resolution original — 3.7 MB —
to a 390-pixel phone. It now asks for a width-matched AVIF and gets 40 KB.
**Ninety-eight per cent, from one photograph.**

**2. A migrated photograph in the first screen, previously width-limited.**
`/tourism/algeria` and `/tourism/angola`, −2% and −5%. The provider was already
being asked for a sensible width, so the gain is AVIF over JPEG rather than
right-size over full-size: 0.04 MB and 0.09 MB delivered from
`image.afrinkong.com`. Real, and an order of magnitude smaller than case 1.

**3. No migrated photograph in the first screen.** `/algeria`, `/angola`,
`/portrait/algeria` — 0%, correctly. Those pages do contain first-party URLs,
but on them the migrated photograph is a lazy card below the fold, so a phone
never fetches it. The hero is still somebody else's.

## How much of the site is case 1

Counted across every rendered reference on the live pages, with HTML entities
unescaped — `&amp;w=` does not match a naive search for `&w=`, which is how I
first got this wrong and read 100%:

| provider | references | width-limited | **unbounded** |
|---|---:|---:|---:|
| Pexels | 10,318 | 8,406 | **1,912** (19%) |
| Unsplash | 926 | 747 | **179** (19%) |
| total | 11,244 | 9,153 | **2,091 (18.6%)** |

**Roughly one reference in five asks a provider for the full-resolution
original**, at whatever size that photographer uploaded, on every device. Those
are the ones where migration is transformative rather than incremental, and
there are about two thousand of them.

## A separate problem this turned up

`/portrait/algeria` pulls **3.55 MB of Pexels imagery into the first screen on
a phone** — four requests, nothing migrated, no change from this work. That is
a page-weight problem in its own right and it has nothing to do with the image
library. It is not tracked by `browser-checks`, whose budgets cover four other
pages.

## What this predicts

Nothing, precisely. Six pages is a baseline, not a model, and the split between
case 1 and case 2 on any given page depends on which photograph happens to be
its hero. What can be said:

- migrating a photograph that is somebody's hero AND unbounded is worth
  megabytes;
- migrating one that is already width-limited is worth tens of kilobytes;
- migrating one nobody's first screen loads is worth nothing until the page
  changes.

The acquisition plan already ranks by placement, so the frames it puts first
are the ones in case 1 and 2. Re-run this after the next wave and compare.

## Re-running it

Actions → *Build the Afrinkong image library* → tick **Measure page weight
before/after the rewrite**. Nothing else. It needs the open internet and cannot
run in the development sandbox, whose proxy refuses both the providers and our
own asset host.
