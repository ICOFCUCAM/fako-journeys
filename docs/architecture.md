# How this site is put together

Everything here is derived from something else. There is one hand-written page
family, one dataset, and a chain of generators between them — so the useful
question about any pixel on this site is *which command wrote it*, and this is
the answer to that.

## The shape

1,594 HTML files, no server, no framework, no build step at deploy time. The
repository IS the site: Vercel serves the files as they are committed, with
`cleanUrls: true` and `trailingSlash: false`, so `/about` is `about.html` and
`/places/kenya/x` is `places/kenya/x.html`.

```
tourism/countries/*.json     54 country files — the dataset
tourism/*.json               taxonomy, regions, cities, operators, company, …
tourism/cache/images.json    what the resolver found, and what the audit rejected
images/uploads/              269 photographs this project holds itself
```

Out of those come six families of page, and one hand-written family that
predates all of them:

| what | how many | written by |
|---|---|---|
| the gateway | 1 | `build.py gateway` splices into `index.html` |
| country pages | 56 | `build.py render` → `/tourism/<slug>` |
| places | 1,404 | `build.py places` → `/places/<country>/<place>` |
| portraits | 54 | `build.py story` → `/portrait/<slug>` |
| crossings | 9 | `build.py transafrique` |
| wonders, trust, how-it-works, enquiry, atlas, journey, meet | 1 each | their own commands |
| the operator's own pages | 5 | by hand — `/about`, `/contact`, `/pricing`, `/services`, `/cameroon` |

`build.py all` runs the whole chain in dependency order. It is meant to be the
thing you can always run: drop a JSON file into `tourism/countries/` and `all`
gives you a country on the map, in the atlas, in the journey engine, on the
homepage and in the sitemap, with no code change.

## The passes that run over the output

Four generators write *pages*; four passes then rewrite what the generators
produced. They are late on purpose — the same tag comes out of six different
families, and one pass over the output is one place to be right instead of six
places to remember. All four are idempotent and all four run inside `all`.

| pass | what it does |
|---|---|
| `company` | splices the legal entity and the three statements into `<!-- gen:company -->` on 1,587 pages |
| `graft` | carries the breadcrumb trail and the font preload to the six pages that write their own `<head>` |
| `srcset` | offers every width a photograph exists at |
| `sizeattr` | says how wide the box is, from `data/sizes.json` |

`sizeattr` has to run after `srcset`, because it writes the hint that decides
which of the widths `srcset` just offered gets taken.

## What is measured rather than decided

Three things in this repository are numbers somebody read off a browser, not
numbers somebody chose. Each has a note in its own file explaining the
measurement; the point of listing them here is that **they go stale**, and the
way they go stale is silent.

- **`data/sizes.json`** — the painted width of every photograph at fifteen
  viewport widths, from `tools/tourism/measure_sizes.js`. Regenerate after a
  layout change. Guarded two ways: each tag's `src` must match the src measured
  at that position, and four browser checks compare every hint against the
  paint.
- **the region tones** in `tourism/regions.json` — cut against measured
  contrast bars, with the four constraints written into the file.
- **the metric-corrected fallback face** in `styles/afrinkong.css` — a width
  ratio measured across eight of this site's own headlines.

## The gates

Four suites, and the reason there are four is that each can see something the
others cannot.

```
python3 tools/tourism/build.py verify     55 country pages, structurally
node tools/journey-checks.js              99 checks — the engine, events, the
                                          colophon, the manifest
node tools/link-checks.js                 3 checks over 76,954 links
node tools/browser-checks.js              243 checks in a real browser
node tools/fund-checks.js                 64 checks — the estimator's
                                          arithmetic and the promises it makes
node tools/design-checks.js               16 checks — the design blueprint's
                                          two absolutes, at 390/768/1440
```

`design-checks.js` answers a different question from `browser-checks.js`. That
suite asks whether a page works; this one asks whether it is the page the
design direction asked for. A page can be perfectly accessible, perfectly
stable, and still be the tourism marketplace the blueprint exists to delete.
Its card allowances are a ratchet: the number beside each surface is what that
surface measured when the line was written, it only ever goes down, and a run
that comes in under its allowance says so and asks for the number to be
lowered.

`build.py test` runs the lot and folds every line into one report.

**`browser-checks.js` exits 0 whether or not checks fail.** Read the tally, not
the exit code. Node also buffers stdout when it is not a TTY, so a log file
stays empty until the run ends — an empty log is a running suite, not a hung
one.

Only one instance may run at a time: they all bind the same port.

## Things that are load-bearing and do not look it

- **The fixed-window band.** A `position: fixed` picture inside a
  `clip-path: inset(0)` section. Six properties on *any* ancestor silently
  destroy it by creating a containing block: `transform`, `filter`,
  `backdrop-filter`, `perspective`, `will-change`, `contain`. See
  `docs/window-band.md`, which is long because this was got wrong repeatedly.
- **The headline fitter.** `AFRICA` is sized by measuring the face and dividing
  the column by it, so the type scale under it is a proportion of a number that
  only exists at run time. It re-runs on `document.fonts.ready`, because the
  face it measures can change mid-load.
- **The dark-ground token list** in `styles/afrinkong.css` re-points
  `--c-muted` and `--c-accent` for every dark surface. A new dark panel that
  does not join the list gets paper colours on basalt. One member of that list,
  `.pl-foot`, is painted in the country's own region tone rather than basalt,
  and needs its own treatment for exactly that reason.
- **`opacity` is invisible to the contrast checks.** `getComputedStyle` reports
  the undimmed colour, so text faded with opacity can sit below AA and pass
  every check. Fade with a colour where the ratio matters.

## Where the work happens that cannot happen here

Three things need network access this repository's development environment does
not have, and they live in `.github/workflows/`:

- **`tourism-resolve.yml`** — fills image slots from Unsplash and Pexels, audits
  what it took, moves the hard crops off dead centre, rebuilds and commits.
  Needs `UNSPLASH_ACCESS_KEY` or `PEXELS_API_KEY` as repository secrets.
- **`tourism-wonders.yml`** — the same for the wonders' photographs.
- **`tourism-optimise.yml`** — resize and re-encode placed images.

The resolve workflow is the one that matters, and it has now run: 1,416 of
1,458 slots are filled, and the crops have been decided. Forty-two slots remain
— the tail where search returns nothing the audit will accept — and they render
as designed plates rather than as damage.

## What is specified and not built

One item, recorded here because the page it concerns reads as finished and is
not, and three separate audits have had to rediscover it.

**The Journey Builder has no map.** `/journey` ships at 121 KB with **zero
`<svg>` and zero `<path>`** in it. What exists is a four-step questionnaire —
eight elements hidden until scripting advances them, which is also why the page
renders 232 words to a visitor who has not interacted with it — and it works.
What was specified is:

    question -> geographic response -> question -> geographic response
             -> the finished journey, drawn

Every answer landing on the continent: an intention lighting the countries that
answer it, a country flown to, a stage drawn, and a last screen that is the
journey as a route rather than as a list of names. The geometry for it already
exists and is proven twice — `tools/africa_map.py` projects it, the hero draws
all fifty-four from it, and each crossing page draws fifty-five paths of it — so
this is a wiring and design problem, not a data one.

Until it is built, `/journey` should be described as a questionnaire that
returns a country, not as a map-based journey builder.
