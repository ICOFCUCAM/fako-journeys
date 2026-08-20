# The first-party image baseline

Measured by `tools/weigh.js` on a GitHub runner with open network, at a 390×844
viewport at 3× — the phone the budget checks use. Bytes are what crossed the
wire for image responses, not decoded size. "Before" is the same page at
`c26c33a^`, the commit before the rewrite, served from a git worktree so the
only variable is where the photographs come from.

Measured twice: once on **20 August 2026** with 19 photographs migrated, and
again the same day with **527** migrated. The second run is the interesting one,
and not for the reason expected.

## The second measurement

| page | before | 19 live | 527 live | change | requests |
|---|---:|---:|---:|---:|---|
| `/algeria` | 0.54 MB | 0.54 MB | 0.54 MB | 0% | 3 → 3 |
| `/angola` | 0.38 MB | 0.38 MB | 0.38 MB | 0% | 3 → 3 |
| `/tourism/algeria` | 1.88 MB | 1.86 MB | 1.76 MB | −7% | 8 → 8 |
| `/tourism/angola` | 1.13 MB | 1.07 MB | 1.07 MB | −5% | 8 → 8 |
| `/portrait/algeria` | 3.58 MB | 3.58 MB | 3.58 MB | 0% | 4 → 4 |
| `/places/algeria/a-thousand-kilometres-of-mediterranean` | 3.76 MB | 0.07 MB | **0.07 MB** | **−98%** | 2 → 2 |
| **total** | **11.27 MB** | **7.49 MB** | **7.40 MB** | **−34%** | |

**Five hundred and eight additional migrated photographs bought ninety
kilobytes.** The headline percentage is unchanged to the digit. One page moved —
`/tourism/algeria`, by 0.10 MB — and the other five are byte-for-byte where they
were.

I predicted before reading this run that all six pages would move, and that
`/portrait/algeria` in particular would fall the way `/places/algeria/…` did,
because four of its fourteen unbounded provider references had been migrated. It
did not move at all. That prediction was wrong in a way worth keeping, because
chasing why is what produced the rest of this document.

## Why nothing moved

Not because migration does not work. `/places/algeria/…` is still −98%.

Because **a phone only fetches the eager image**. Every photograph on these
pages except one is `loading="lazy"`, and a lazy card below the fold is never
requested at all, so migrating it changes zero bytes until a visitor scrolls to
it. Counting references makes the migration look broad — `/tourism/algeria`
carries 72 first-party references against 103 provider ones — and the count is
irrelevant to what crosses the wire.

The image that always crosses the wire is the eager one, and this site has
exactly one per page. There are no exceptions: across all 1,597 HTML files,
**no page has more than one eager remote photograph.** Page weight on a phone is
therefore decided almost entirely by a single question per page — who serves the
hero.

That reads the six results cleanly, where "how many photographs are migrated"
did not:

- `/places/algeria/…` — hero migrated, and it had been unbounded. **−98%.**
- `/tourism/algeria`, `/tourism/angola` — hero is still a Pexels hotlink, but a
  width-limited one. The first-party bytes that do appear (0.21 MB, 0.25 MB) are
  near-viewport lazy cards the browser pulled in early. **−7%, −5%.**
- `/algeria`, `/angola`, `/portrait/algeria` — **no eager remote hero at all.**
  What a phone fetches is whichever lazy cards fall near the first screen, and
  on these three those are still provider images. **0%, correctly.**

`/portrait/algeria` is the sharp case. Its 3.55 MB is three or four *lazy*
Pexels images pulled in by the browser's near-viewport threshold, and every
provider reference on that page is unbounded. Migrating four of them changed
nothing because they were not among the ones the threshold reached.

## The hero census

Run `node tools/heroes.js`. No network; it reads the built HTML and the
register.

| section | pages | ours | published, not rewritten | never registered | of these, unbounded |
|---|---:|---:|---:|---:|---:|
| `/places` | 1,363 | 527 | 86 | 750 | 836 |
| `/tourism` | 52 | 0 | 16 | 36 | 0 |
| root | 1 | 0 | 0 | 1 | 0 |
| **total** | **1,416** | **527** | **102** | **787** | **836** |

The middle column is exactly the 102 art-directed assets, which is the check
that the census and the register agree. It did not agree at first: matching a
page's URL against a *rebuilt* sourceKey silently misses every Unsplash asset,
because the register holds Unsplash's photo id (`JaD-db16oAE`) and the URL
carries a different slug. That read 91 where the answer is 102. `heroes.js`
now matches on the `originalUrl` the register itself recorded.

A further 181 pages have no eager remote photograph at all.

Three facts fall out of it:

**1. Every migrated photograph is a `/places` hero.** 527 assets live, 527
`/places` heroes ours. The migration has been doing exactly the highest-value
thing available to it, which is why the six-page sample — five of whose pages
are not `/places` — barely registered it.

**2. Eight hundred and thirty-six heroes are unbounded.** The URL carries no
width, so the provider serves whatever resolution the photographer uploaded to a
390-pixel phone. `/places/algeria/…` was one of these before migration: 3.7 MB
for one photograph, now 40 KB. **This is the same case, 836 times over**, and it
is the whole of the remaining page-weight problem. The 52 `/tourism` heroes are
all width-limited, which is why those pages measured −5% and −7% rather than
−98%.

**3. A hundred and two of them need no acquisition at all.** They are already published
on `image.afrinkong.com`. The page still hotlinks them because `rewrite` excludes
art-directed assets — an asset that appears in an art-directed `<picture>`
anywhere is excluded everywhere, so it cannot be half-migrated onto two hosts.
Checked, not assumed:

    published, not rewritten, not held : 102 -> art-directed: 102

All 102 held-back assets are exactly the art-directed set, and every one of
them is somebody's hero — 86 on a `/places` page and 16 on a `/tourism` page.
All 86 of the `/places` ones are unbounded.

## What this changes

The 102 re-crops were ranked P0 on commercial grounds, and deferred as a
finishing task — a second phone crop for photographs that already look right.
That was the wrong reading of what they are. **All 102 are heroes that a phone
fetches on arrival, 86 of them at full resolution**, on photographs we are
already paying to host — an estimated 0.47 GB. The crop is not a polish item; it is
the cheapest megabytes on the site, and it needs no budget decision, no
licensing, and no provider.

For the acquisition plan, hero occupancy should outrank reference count. A
photograph that appears forty times below the fold is worth nothing to page
weight; a photograph that is one page's hero and unbounded is worth megabytes.
The ranking already weights placement and unboundedness — this says how much.
Migrating an unbounded hero saved 3.69 MB on one page; migrating everything
reachable on `/tourism/algeria`, whose hero is width-limited, saved 0.12 MB.
**Roughly thirty to one**, measured, and unboundedness alone is the difference
between −98% and −7%.

The 750 `/places` heroes that are not in the register at all remain the
acquisition question. `docs/hero-acquisition.md` now answers it — banded P0 to
P3, with the payload and the commercial argument on every row.

## Do not quote the −34%

It was one page wearing a disguise at 19 photographs migrated and it is the same
page wearing the same disguise at 527. Of the 3.87 MB saved across six pages,
3.69 MB is still `/places/algeria/…` alone.

The honest single number is the census, not the percentage: **527 of 1,416 heroes
are ours, and all 836 of the rest are unbounded — an estimated 4.63 GB.**

## Re-running it

Page weight: Actions → *Build the Afrinkong image library* → tick **Measure page
weight before/after the rewrite**, nothing else. It needs the open internet and
cannot run in the development sandbox, whose proxy refuses both the providers and
our own asset host.

The census runs anywhere: `node tools/heroes.js`, or `--list` for every page
whose hero is still hotlinked, with its state and asset id.
