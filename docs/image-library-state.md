# The image library: where it stands, and what is left

Written 20 August 2026, at the point the work was paused. This is the handover
— read it before touching the image pipeline, because several of the obvious
next moves have already been tried and are recorded below as mistakes rather
than as options.

---

## The one fact the whole system turns on

**A phone only fetches the eager image, and this site has exactly one per
page.** Every other photograph is `loading="lazy"` and is never requested until
somebody scrolls. There are no exceptions across all 1,597 HTML files.

So page weight is one question per page — who serves the hero — and counting
references tells you about the library rather than about the download. This was
learned the expensive way: migrating 527 photographs moved a six-page sample
from 7.49 MB to 7.40 MB, because none of those six had a migrated hero.

`node tools/heroes.js` is the census. No network, runs anywhere.

## Where it stands

| | |
|---|---:|
| heroes served from `image.afrinkong.com` | **629** of 1,416 |
| heroes asking a provider for the full original | **0** |
| heroes still hotlinked, but width-bounded | 750 |
| pages with no eager remote photograph | 181 |
| registered photographs | 629 (595 Pexels, 34 Unsplash) |
| objects on R2 | ~9,400, about 1.5 GB of the 10 GB free tier |
| estimated remaining hero payload | 0.27 GB |

Nothing on this site ships a full-resolution original to a phone. Every hosted
photograph has a named photographer, a source URL and a licence recorded, and
`build.py library provenance` refuses to commit a register where that is untrue.

**Nothing has been bought.** All 629 are free-licence stock. The only image
money leaving the account is R2 storage.

## What is left, in the order it is worth doing

### 1. Real byte counts (one run, no code)

Actions → *Build the Afrinkong image library* → tick **measure_heroes** alone.
HEADs all 750 remaining heroes, writes `data/hero-bytes.json`, rebuilds the
table against measured bytes and commits. The table already prefers measured
over estimated wherever it has an answer.

Worth doing because the estimate has been wrong once already at a factor of
four — see "the byte model" below.

### 2. The 422 lazy unbounded references (one flag, free)

422 provider references still name no width. All of them are lazy cards below
the fold, so no phone fetches them on arrival — but anybody who scrolls does.
`tools/tourism/bound.py` currently returns early on any tag without
`fetchpriority="high"`; removing that condition bounds them too. Needs its own
browser-checks run because it touches many pages.

### 3. Acquisition — the only item that costs money

`data/hero-acquisition.csv`, 750 rows, regenerate with `build.py heroes
--fetch`:

| band | pages | what it means |
|---|---:|---|
| RE-CROP | 0 | no owned photograph fits any of these slots |
| RETAIN | 74 | relevance 6+ and nothing to sell, or 7.2+ anywhere — leave alone |
| P1 | 94 | tier 1–2 country **and** the picture is badly wrong |
| P2 | 116 | sells, or badly wrong, not both |
| P3 | 466 | no price attached and no strong visual case |

Ranked on commercial weight × visual inadequacy ÷ cost. **Never on reference
count.** Cost is a relative weight (retain 0, re-crop 1, licence 3, licence+ 5,
commission 12), not a price — supply real vendor rates and they drop in at
`heroplan.COST_WEIGHT`.

The standing decision: **buy nothing until this list has been reviewed.**

### 4. Older, unrelated, still open

- Social proof section — blocked until `voices.json` holds real testimonials.
- The window band's video clips — blocked until somebody provides footage.
- 36 nested `<picture>` blocks, pre-existing and invalid. Present since before
  this work; 259 browser checks pass with them. Not caused by the migration,
  measured twice to confirm.

## Things already tried that did not work

Recorded so they are not tried again.

**Ranking on reference count.** A photograph on forty pages sorts identically
to one on a single page, because thirty-nine of those forty are lazy cards
nobody's first screen fetches.

**Ranking on the hero flag alone.** 1,415 of 1,416 photographs carry
`fetchpriority="high"`. Read on its own it says everything is a hero.

**Inbound links as a commercial signal.** They run 38–53 per country and are
driven by shared borders and the atlas, so Mali and DR Congo top the table.
That measures geography, not demand. Commercial weight comes from
`data/graph.json` (three countries with named operators) and the priced Trans
Afrique pages (fifteen more).

**Rebuilding a sourceKey from a page URL to find the asset.** Works for Pexels,
silently fails for every Unsplash photograph: the register holds Unsplash's
photo id (`JaD-db16oAE`) and the URL carries a different slug
(`1503592687001-f8d008454cbf`). This reported 82 heroes as never audited when
none were. Match on `originalUrl`, which the register itself recorded.

**Estimating provider bytes as pixels × a constant.** Calibrated on one
Unsplash photograph at 0.183 B/px, it predicted 10.8 MB for a hero that
measured 2.33. Unsplash tracks pixels almost exactly; **Pexels plateaus** —
three originals from 25 to 59 megapixels all landed between 2.3 and 2.8 MB.
`acquire.BYTE_CAP` now caps Pexels at 2.6 MB. Five for five within 13%, and
still a model.

**Asking `est_bytes` for a page's hero cost.** It answers "is any use of this
photograph unbounded", which is right for the acquisition plan (one row per
photograph) and wrong for the hero table (one row per page). Pass the hero's
own use.

**`rm -rf incoming`.** That directory holds real Cameroon source photographs,
not scratch files.

## Traps in the pipeline

**Late passes are wiped by any regeneration.** `cmd_places` rewrites 1,363 place
pages from scratch, so `bound`, `srcset`, `sizeattr` and `modern` all run at the
end of `cmd_all` for that reason. **Anything that edits built HTML must join
that chain** or one `build.py all` silently undoes it.

**The disk decides what `fetch` downloads, not the register.** `incoming/` and
`images/library/` are gitignored, so a fresh runner has a register saying
everything is downloaded and an empty disk.

**Art-directed photographs need the full original, not `w=1600`.** Cutting 4:5
out of 1600×900 leaves 720×900, so the phone would get a 480-wide source where
the provider serves 1200×1500 — worse, while becoming ours.

**Commit the register before the reachability gate.** What was downloaded is a
fact about the run; whether somebody's nameservers have propagated is not, and
run 1 threw away a 25-photograph download record by ordering these wrongly.

**`browser-checks.js` takes 30–40 minutes and Node buffers its stdout.** An
empty log means running, not hung.

**The development sandbox cannot reach the providers or our own asset host.**
Its proxy refuses both, and it MITMs all TLS, so no certificate observed from
there means anything. Anything needing network is a workflow step.

## The strategic position

The goal is not zero third-party URLs. It is first-party ownership of the
photographs that carry Afrinkong's commercial identity — the heroes. A minor
card left on Pexels below somebody's fold costs no bytes on arrival and no
credibility that anybody sees.

What would genuinely improve the site from here is not more migration. It is
better photographs in the 94 P1 slots: pages that carry a price, opened by an
image the audit scored below 3 out of 9. Free stock also means a competitor can
run the identical frame, which is the real argument for commissioning those —
a brand argument, not a licensing one.

## The commands

    node tools/heroes.js                      the census
    node tools/heroes.js --check              CI gate: no unbounded hero
    node tools/heroes.js --list               every hero still hotlinked
    python3 tools/tourism/build.py heroes     the acquisition matrix
    python3 tools/tourism/build.py bound      width-bound unbounded heroes
    python3 tools/tourism/build.py acquire    the whole-site plan, 1,427 rows
    node tools/weigh.js                       before/after page weight (network)

Workflow inputs on *Build the Afrinkong image library*: `limit`, `publish`,
`encode`, `only`, `rewrite`, `weigh`, `measure_heroes`, `check_host_only`. The
jobs are mutually exclusive — anything ticked alongside `weigh` or
`measure_heroes` is ignored.
