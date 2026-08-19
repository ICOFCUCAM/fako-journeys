# Afrinkong: where it stands, and what is missing

Re-measured today, against the repository as it is rather than against the last
time somebody wrote this page down. Every number below came out of a command in
this repository; where a number is a judgement rather than a measurement, it
says so.

---

## The short version

The site is **built, correct, comprehensively checked, and cannot yet take a
booking or a message**. Every path a visitor can walk works. The path they walk
at the end delivers an email to a domain nobody owns. That single fact outranks
everything else on this page, so it is first, and it has not changed since the
last time this page was written.

| | | how it was counted |
|---|---|---|
| HTML files that exist and are correct | 1,597 | `find . -name '*.html'` |
| Internal links, all of which resolve | 78,543 | `link-checks.js` |
| Countries written up 27 ways | 54 | `tourism/countries/*.json` |
| Image slots filled | 1,416 | `tourism/cache/images.json` |
| Candidates the audit refused | 337 | same file, `rejected` |
| Automated checks passing | **497** | six suites, below |
| Ways to pay | none | — |
| Ways to reach a human | one `mailto:` to an unregistered domain | `enquire.html` |

The six suites, and what each can see that the others cannot:

```
build.py verify         55   every category rendered, every image sized
journey-checks.js       99   the engine's structure, icons, manifest
fund-checks.js          64   the estimator's arithmetic and its promises
link-checks.js           3   78,543 links, every asset, every #fragment
design-checks.js        17   the blueprint's absolutes, in a browser
browser-checks.js      259   contrast, focus, CLS, weight, no-JS reading
                       ---
                       497   failing: 0
```

---

## What is genuinely finished

**The content architecture.** Fifty-four countries through the same
twenty-seven categories, so any two compare on the same terms. 1,404 place
pages, 54 portraits, 9 crossings, an atlas, a fund. Drop a JSON file into
`tourism/countries/` and one command puts that country on the map, in the
atlas, in the journey engine, on the homepage and in the sitemap, with no code
change.

**The measuring.** 497 checks is not the useful number; what is useful is that
three of the suites measure a *rendered* page rather than a file — composited
contrast, focus rings, layout shift, transferred weight, and what the page says
with scripting off. The gap this repository keeps finding is the one where
every file is right and the render is wrong, and that gap is now instrumented.

**The Journey Fund door** on the homepage, and the fund's own surfaces. Twenty
commits of composition work, measured at every width the section changes shape
in, closed most recently.

---

## The gaps, in the order they cost money

### 1. Nobody can pay you, and nobody can reach you

`afrinkong.com` is not registered. Every enquiry path on the site ends at
`hello@afrinkong.com`, which bounces, and the one form on the site `POST`s to a
`mailto:` because there is no endpoint to post to. There is no payment
provider, no deposit flow, no booking record.

`tourism/company.json` says so itself, in a `$change_me` note beside the
address: it is one edit here and the tunnel, the enquiry page and 1,587
footers follow it.

**This is the whole business, and none of it is a code problem.** Everything
below is smaller. It needs a purchase and a decision, not a commit.

### 2. The Journey Builder has no map — and it is the page whose name promises one

This is the largest *buildable* gap on the site, and it is the one this round
of work takes on.

Measured: `/journey` ships at 122 KB with **zero `<svg>` and zero `<path>`**,
and renders **270 words** with scripting off — the thinnest page on the site
apart from `/404`. What exists is a four-step questionnaire that returns a
country, and it works. What was specified is:

    question -> geographic response -> question -> geographic response
             -> the finished journey, drawn

The geometry to do it already exists and is proven three times over:
`tourism/map.json` holds 52 country paths, 2 island marks and a centroid for
each, in one 1000×1060 viewBox; the homepage hero draws all of them; every
crossing page draws fifty-five paths of the same projection.

One honest limit, recorded here so it is not rediscovered as a bug: **places
have no coordinates.** `data/atlas/*.json` gives each place a group, a lens set
and a write-up, and no position. Thirteen cities in `tourism/atlas-detail.json`
have a real position and nothing else does. So a journey can be drawn honestly
across countries and across those thirteen cities, and cannot be drawn as pins
inside a country without inventing where things are — which this repository
does not do.

### 3. There is no social proof

`tourism/voices.json` holds an empty list. The site makes its case entirely on
its own authority, for four-thousand-dollar journeys to countries most buyers
have not visited. Testimony from someone who went is the single most persuasive
thing that could be added, and inventing it is not an option.

*What unblocks it:* one completed journey, and permission to quote.

### 4. Photographs: the tail, and the eight that cannot be taken

1,416 slots are filled and 337 candidates were refused by the audit. The
remainder render as designed plates — the country's outline on its region's
tone, captioned with what the picture would have shown — on 86 pages. Honest
rather than broken, but a plate is not a photograph.

Separately, the wonders that stock photography cannot serve honestly stay
recorded as `$photo_needs_commission` rather than filled with something
approximate. That is a purchase, not a task.

### 5. Nothing has met a real browser at a real domain

The security headers, the canonical URLs, the manifest, the
Content-Security-Policy — all correct in the files and none of them ever
served. The CSP is the one that can break a page quietly. The first deploy to
the real domain wants somebody watching the console.

---

## What I looked at and deliberately did not change

- **The five pages branded "Kamerun"** — `/about`, `/contact`, `/pricing`,
  `/services`, `/cameroon`. Kamerun is the operating company in Cameroon and
  those are that operator's pages. The branding is correct.
- **`compare.html` reads 55% of its words with scripting off.** It is a
  comparison tool whose whole content is the comparison; the words it withholds
  are the ones it has not been asked for yet.
- **The 42-slot photographic tail.** Re-running the resolver picks at it and
  stops. Better search terms per slot is a content decision, not a code one.

---

## If I had one more day

The same answer as last time, and it is still not a code answer: register the
domain and put an endpoint behind the enquiry form. Everything the architecture
can do for the business, it has now done — the next thing that changes the
business is a single real enquiry arriving somewhere a person reads.
