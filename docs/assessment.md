# Afrinkong: where it stands, and what is missing

Written after fifty commits of work on the architecture. This is the honest
version — what is finished, what is blocked, and on whom.

---

## The short version

The site is **built and correct and cannot yet take a booking**. Every path a
visitor can walk works, and the path they walk at the end delivers an email to a
domain nobody owns. That single fact is worth more than everything else on this
page, so it is first.

| | |
|---|---|
| Pages that exist and are correct | 1,594 |
| Countries written up 27 ways | 54 |
| Image slots filled | 1,119 of 1,458 (77%) |
| Automated checks passing | 400 across four suites |
| Ways to pay | none |
| Domain | not registered |

---

## What is genuinely finished

**The content architecture.** Fifty-four countries, each written up through the
same twenty-seven categories, so any two can be compared on the same terms.
1,404 place pages, 54 portraits, 9 crossings, an atlas, a journey builder. Add a
JSON file and one command gives you a country on the map, in the atlas, in the
journey engine, on the homepage and in the sitemap. No code change.

**The machinery around it.** Four check suites that between them cover
structure, the journey engine's arithmetic, 76,954 links, and 243 measurements
taken in a real browser — contrast against composited grounds, the hero's
composition at nine widths, keyboard focus, what the page weighs.

**The things a professional site is expected to have and this one did not**, all
added in the last fifty commits: breadcrumb trails on every page, the company's
legal identity and its three statements on all 1,587 pages that carry a footer,
a Content-Security-Policy and five other response headers, a display face that
actually renders on an iPhone, a maskable app icon, and a first screen that
costs 4.37 MB on a phone instead of 12.29 MB.

---

## The gaps, in the order they cost money

### 1. Nobody can pay you, and nobody can reach you

`afrinkong.com` is not registered. Every enquiry path on the site — the journey
builder, the enquiry form, the footer of 1,587 pages — ends at
`hello@afrinkong.com`, which bounces. The forms `POST` to a `mailto:`, because
there is no server to post to.

There is no payment provider, no deposit flow, no booking record. A visitor who
reads 1,594 pages, builds a journey, and decides to spend four thousand dollars
has nowhere to do it.

**This is the whole business, and none of it is a code problem.** Everything
below is smaller.

*What unblocks it:* buy the domain; point it at the deployment; decide whether
enquiries go to a mailbox or an endpoint. A real endpoint also lets
`form-action` in the CSP tighten from `mailto:` to `'self'`.

### 2. Twenty-three per cent of the photographs are missing

339 of 1,458 image slots have no photograph. They do not look broken — an
unresolved slot draws the country's own outline on its region's tone, captioned
with what the picture would have shown — but a visitor to Eritrea, Cabo Verde,
DR Congo or Mauritania sees ten to thirteen of those on one page.

Three country pages have no hero photograph at all: **Ethiopia**, Burkina Faso,
and São Tomé and Príncipe. Ethiopia is a headline destination arriving with a
drawn outline where its photograph should be.

*What unblocks it:* add `UNSPLASH_ACCESS_KEY` or `PEXELS_API_KEY` under
Settings → Secrets and variables → Actions, then run **Resolve tourism images**.
The same run also fixes gap 3.

### 3. A hundred and sixty-eight photographs are cropped at dead centre

Hero, panoramic and portrait boxes throw away most of the frame, and 50/50 is
the absence of a decision — in a tall box it is the setting most likely to take
the top off whatever the picture is of.

The tool to fix this is written and validated, and it cannot run in a
development environment: it has to read the photographs, and they live on the
providers' CDNs. It is a step in the resolve workflow, so it happens on the same
run as gap 2.

### 4. Eight wonders cannot be photographed honestly

Great Zimbabwe, Bazaruto, Gorongosa, Timbuktu and four others have no usable
stock photograph. What the archives return is not what the page claims — Great
Zimbabwe brings back Türkiye, Spain and France; Bazaruto brings back Brazil;
Gorongosa brings back Minnesota and a carabao; Timbuktu brings back Kano.

These are recorded in `tourism/wonders.json` as `$photo_needs_commission`
rather than filled with something approximate, because a photograph that is
not of the place is worse than a drawn outline that is honest about it.

*What unblocks it:* commissioned or licensed photography. This is a purchase,
not a task.

### 5. There is no social proof

`tourism/voices.json` holds an empty list. The site
currently makes its case entirely on its own authority. For a company selling
four-thousand-dollar journeys to a country most buyers have not visited,
testimony from someone who went is the single most persuasive thing that could
be added — and inventing it is not an option.

*What unblocks it:* one completed journey, and permission to quote.

### 6. Nothing has met a real browser

The security headers, the domain, the canonical URLs, the manifest — all correct
in the files and none of them ever served. The Content-Security-Policy is the
one that can break a page quietly. The first deploy to the real domain wants
somebody watching the browser console, not the page.

---

## What I looked at and deliberately did not change

- **The five pages branded "Kamerun"** — `/about`, `/contact`, `/pricing`,
  `/services`, `/cameroon`. Kamerun is the name of the operating company in
  Cameroon, those pages are that operator's, and they are linked only from
  `/cameroon`. The branding is correct.
- **Two slots whose alt text is only the country name.** That is deliberate
  conservatism: a record with no provider description gets a generic alt rather
  than a claim the site cannot support. It resolves itself on the next resolve
  run.
- **`sizes` on the homepage's photographs.** Added, measured, and it saves
  nothing today — those photographs really are painted 950 pixels wide. Kept for
  what it protects rather than what it saves, and recorded as a negative result.

---

## If I had one more day

Not more architecture. The architecture is ahead of the business now: 1,594
pages of a company that cannot be paid. The next useful commit is a domain
registration and an endpoint behind the enquiry form, and everything after that
is easier to justify once a single real enquiry has arrived.
