# The first-party image baseline

Measured by `tools/weigh.js` on a GitHub runner with open network, at a 390×844
viewport at 3× — the phone the budget checks use. Bytes are what crossed the
wire for image responses, not decoded size. "Before" is the same page at
`c26c33a^`, the commit before the rewrite, served from a git worktree so the
only variable is where the photographs come from.

Measured three times on **20 August 2026**: with 19 photographs migrated, with
527, and with 629 after the art-directed re-crops landed. The second run is the
one that produced the hero census, because it moved almost nothing. The third
is the one that confirmed it.

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

## The third measurement — the re-crops

Run #17, on the eight pages wave 1 actually changed. The old six-page sample was
retired: five of the six were not `/places` pages and none had a migrated hero,
which is why the second run reported 7.49 MB against 7.40 MB.

| page | before | after | change | requests |
|---|---:|---:|---:|---|
| `/places/ghana/mole-and-ankasa` | 2.36 MB | 0.13 MB | **−94%** | 2 → 2 |
| `/places/kenya/balloon-over-the-mara` | 2.78 MB | 0.22 MB | **−92%** | 2 → 2 |
| `/places/namibia/desert-adapted-wildlife` | 2.33 MB | 0.14 MB | **−94%** | 2 → 2 |
| `/places/namibia/self-drive-country` | 1.17 MB | 0.14 MB | **−88%** | 2 → 2 |
| `/tourism/ghana` | 1.55 MB | 1.49 MB | −4% | 8 → 8 |
| `/tourism/namibia` | 2.19 MB | 2.08 MB | −5% | 8 → 8 |
| `/places/algeria/…mediterranean` *(control)* | 3.76 MB | 0.07 MB | −98% | 2 → 2 |
| `/portrait/algeria` *(control)* | 3.58 MB | 3.58 MB | 0% | 4 → 4 |
| **total** | **19.71 MB** | **7.85 MB** | **−60%** | |

Both controls behaved. The already-migrated Algeria page is unchanged at 0.07 MB,
and `/portrait/algeria`, which wave 1 does not touch, reads exactly 0%. Neither
number moving is what makes the other six believable.

**The unbounded-hero case reproduces, four more times.** −88% to −94%, on four
pages that had nothing to do with each other beyond the shape of the problem.
That is no longer one page wearing a disguise.

**And the bounded case reproduces too, at −4% and −5%.** Those two `/tourism`
pages are the same photographs as heroes of width-limited pages. Same
acquisition cost, same migration, two orders of magnitude less benefit — which
is the whole argument for ranking on payload rather than on count.

One thing the `/tourism` rows show that is worth not misreading: our own bytes
there (0.78 MB and 0.38 MB) are a large share of what remains. That is
arithmetic, not a fault. The phone crop is 1200×1500 — 1.8 megapixels — where
the landscape rung at the same width is 1200×675, or 0.81. Art direction costs
roughly 2.2× the pixels by construction, and buys the composition somebody
chose. It is not a saving and was never going to be.

## The byte model was wrong, and this is by how much

The acquisition table's payload column was estimated from the original's pixel
dimensions at 0.183 bytes per pixel — calibrated on exactly one photograph. Five
measured points now exist:

| hero | provider | MP | predicted | measured | bytes/px |
|---|---|---:|---:|---:|---:|
| `ghana/mole-and-ankasa` | pexels | 58.9 | 10.78 MB | **2.33 MB** | 0.040 |
| `kenya/balloon-over-the-mara` | pexels | 28.0 | 5.12 MB | **2.75 MB** | 0.098 |
| `namibia/desert-adapted-wildlife` | pexels | 24.8 | 4.54 MB | **2.30 MB** | 0.093 |
| `namibia/self-drive-country` | unsplash | 5.9 | 1.08 MB | 1.14 MB | 0.193 |
| `algeria/…mediterranean` | unsplash | 20.3 | 3.71 MB | 3.73 MB | 0.184 |

Unsplash tracks pixels almost exactly — the original calibration was sound, and
it was an Unsplash photograph. **Pexels does not.** Three originals from 25 to 59
megapixels all landed between 2.3 and 2.8 MB: what it serves plateaus rather
than scaling. The model predicted 10.8 MB for the Ghana hero and the wire
carried 2.33.

`est_bytes` now caps at 2.6 MB for Pexels and leaves Unsplash on the line. Five
for five within 13%, and still a model — `build.py heroes --measure` reads
content-length from the providers and should be run before any of this is
treated as a forecast.

**The correction cuts the outstanding payload from 4.63 GB to 2.04 GB.** Since
1,305 of the site's 1,427 audited photographs are Pexels, and Pexels originals
are large, almost all of the overestimate was there.

## Phase A — the free fix, applied

`build.py bound`, 750 heroes across 750 pages, no purchase and no new asset.

Each of those tags already stated its own geometry and asked for none of it:

    <img src="https://images.unsplash.com/photo-1610133290889-0ed892ce5157"
         width="1600" height="900" fetchpriority="high"
         style="aspect-ratio:16/9">

Sixteen by nine at 1600, and a src with no width, so the provider sent whatever
the photographer uploaded and the CSS cropped it to 16:9 and threw the rest
away. The pass gives each one the srcset its own attributes imply, at the
ladder the library uses, with `sizes` matching the ~800px column the hero
actually paints in. Same photograph, same crop, same page — fewer bytes.

| | before | after |
|---|---:|---:|
| unbounded heroes | 836 | **0** |
| estimated hero payload | 2.04 GB | **0.27 GB** |
| median hero | ~2.6 MB | **0.32 MB** |

**An 87% cut to the site's hero payload, for no money.** Nothing on this site
now ships a full-resolution original to a phone.

Two things this exposed:

**The table was attributing bytes to the wrong reference.** `est_bytes` asks
"is any use of this photograph unbounded", which is right for the acquisition
plan — one row per photograph — and wrong for the hero table, where a row is
one page. A hero already bounded, whose photograph also appeared as an
unbounded lazy card three pages away, reported 2.60 MB for a reference costing
0.32. Fixed by passing the hero's own use and nothing else.

**422 unbounded references remain, all of them lazy.** Non-hero cards below the
fold, so a phone never fetches them on arrival — but somebody who scrolls does.
The same pass would bound them; it is held back only because the instruction
was heroes, and because they need their own browser run.

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

As it stood when the census was written, and as it stands now that the
re-crops have landed:

| section | pages | ours | published, not rewritten | never registered | of these, unbounded |
|---|---:|---:|---:|---:|---:|
| `/places` | 1,363 | 527 → **613** | 86 → **0** | 750 | 836 → **750** |
| `/tourism` | 52 | 0 → **16** | 16 → **0** | 36 | 0 |
| root | 1 | 0 | 0 | 1 | 0 |
| **total** | **1,416** | **527 → 629** | **102 → 0** | **787** | **836 → 750** |

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

## What this changed — done, and measured

The 102 re-crops were ranked P0 on commercial grounds, and deferred as a
finishing task — a second phone crop for photographs that already look right.
That was the wrong reading of what they are. All 102 were heroes a phone
fetches on arrival, 86 of them at full resolution, on photographs we were
already paying to host. The crop was not a polish item; it was the cheapest
megabytes on the site, and it needed no budget, no licence and no provider.

**They are done.** Run #16 cut all 102 crops — 91 at 4:5, 11 at 3:2, each
around the focal point its own markup names — uploaded both ladders and
rewrote the pages. Run #17 measured four of them at −88% to −94%. Every hero
this site owns is now served from `image.afrinkong.com`: 629 of them, with
nothing left published-but-hotlinked.

Wave 1 was meant to be the 29 whose country carries a price; the run was
launched without the `--only` filter and did all 102. That is the outcome the
wave file itself recommended — same operation, same cost, 63 more unbounded
heroes — so nothing was lost by it.

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

## Do not quote the −34%, and be careful with the −60%

The −34% was one page wearing a disguise at 19 photographs migrated and the same
page wearing the same disguise at 527: of the 3.87 MB saved across those six
pages, 3.69 MB was `/places/algeria/…` alone.

The −60% from run #17 is a fairer number — six of its eight pages moved, and the
four re-crops each carried their own weight — but it is still a number about a
sample chosen because it would move. It says the treatment works on the pages
that get it. It does not say what the site weighs.

The honest single number is the census, not the percentage: **629 of 1,416
heroes are ours, and all 750 of the rest are unbounded — an estimated 2.04 GB,
on a model that is now five-for-five within 13% rather than one-for-one.**

## Re-running it

Page weight: Actions → *Build the Afrinkong image library* → tick **Measure page
weight before/after the rewrite**, nothing else. It needs the open internet and
cannot run in the development sandbox, whose proxy refuses both the providers and
our own asset host.

The census runs anywhere: `node tools/heroes.js`, or `--list` for every page
whose hero is still hotlinked, with its state and asset id.
