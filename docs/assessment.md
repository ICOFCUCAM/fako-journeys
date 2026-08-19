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
| Internal links, all of which resolve | 78,595 | `link-checks.js` |
| Countries written up 27 ways | 54 | `tourism/countries/*.json` |
| Image slots filled | 1,416 | `tourism/cache/images.json` |
| Candidates the audit refused | 337 | same file, `rejected` |
| Automated checks passing | **503** | six suites, below |
| Ways to pay | none | — |
| Ways to reach a human | one `mailto:` to an unregistered domain | `enquire.html` |

The six suites, and what each can see that the others cannot:

```
build.py verify         55   every category rendered, every image sized
journey-checks.js      105   the engine, icons, manifest, the map
fund-checks.js          64   the estimator's arithmetic and its promises
link-checks.js           3   78,595 links, every asset, every #fragment
design-checks.js        17   the blueprint's absolutes, in a browser
browser-checks.js      259   contrast, focus, CLS, weight, no-JS reading
                       ---
                       503   failing: 0
```

---

## What is genuinely finished

**The content architecture.** Fifty-four countries through the same
twenty-seven categories, so any two compare on the same terms. 1,404 place
pages, 54 portraits, 9 crossings, an atlas, a fund. Drop a JSON file into
`tourism/countries/` and one command puts that country on the map, in the
atlas, in the journey engine, on the homepage and in the sitemap, with no code
change.

**The measuring.** 503 checks is not the useful number; what is useful is that
three of the suites measure a *rendered* page rather than a file — composited
contrast, focus rings, layout shift, transferred weight, and what the page says
with scripting off. The gap this repository keeps finding is the one where
every file is right and the render is wrong, and that gap is now instrumented.

**The Journey Fund door** on the homepage, and the fund's own surfaces. Twenty
commits of composition work, measured at every width the section changes shape
in.

**The Journey Builder's map**, which was the largest buildable gap on this page
when it was written this morning and is gap 2 below, now closed.

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

### 2. The Journey Builder's map is built; place coordinates are not

This was the largest buildable gap on the site when this page was written
earlier today, and it is closed. `/journey` now carries the continent in the
document — fifty-two country paths, two island marks and one disputed
territory out of `tourism/map.json`, in the same projection and the same
1000×1060 viewBox the hero and the crossing pages draw. Answering a question
colours the countries by how each answers it; choosing one flies the viewBox to
it; composing a journey draws the route across it. Six checks in
`journey-checks.js` hold the map in the document rather than in a script, which
is the way it could quietly stop existing. The browser suite reads the page
after the change at 259 checks and no failures: CLS 0.0000, 78 focus stops with
every ring at 3:1 or better, nothing under 24px to press, and every text
contrast at AA.

One thing that is *not* fixed and was worth checking: the page still renders
only 282 words with scripting off, up from 270. The fifty-four country names
are in the document, but they sit in `<title>` elements, which a screen reader
announces and a word counter does not read. The real gain is that a visitor
with no JavaScript now gets a map of Africa where every country links to its
own pages, rather than a page of four hidden questions.

What remains is the data underneath it, and it is a real limit rather than a
loose end. **Places have no coordinates.** `data/atlas/*.json` gives each place
a group, a lens set and a write-up and no position, so a node cannot be put on
the Mara without inventing where the Mara is. Thirteen places in
`tourism/atlas-detail.json` have a real position and every country has a
centroid; that is what the route is drawn from, and the map's caption says
which of the two each node is rather than letting a reader assume the stronger
one.

*What unblocks it:* a latitude and longitude on each place record. That is a
content task, and it would upgrade the drawn journey from a shape to an
itinerary. Nothing else in the repository is waiting on it.

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
