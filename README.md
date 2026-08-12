# WankonAfritour, and Kamerun

Two sites in one repository, on purpose.

    /            WankonAfritour — the group's gateway to the whole continent
    /cameroon    Kamerun — the Cameroon operator, and everything under it
    /tourism/*   generated country pages, 27 categories each, seven countries

The gateway sells Africa and hands the visitor to a country. The country site
sells the country and hands them to a circuit. That is why `index.html` is
deliberately light — a page whose only job is routing should load instantly —
while `cameroon.html` carries the photographs, the six climates and the
fourteen-day route.

`cameroon.html` and its four pages (services, pricing, about, contact) are the
Kamerun site; they are still at the repository root rather than under
`/cameroon/`, which keeps their URLs and every internal link stable. Moving them
into a folder is a later decision, not a blocker.

The repository is still named `fako-journeys` — the original operator name.
"Fako" survives in the sites themselves only as the name of the mountain the
first circuit climbs.

No build step, no dependencies, no framework — plain HTML and CSS. Deploy the
folder as-is.

## Deploying

Import the repository into Vercel (or any static host) and deploy. The repo root
*is* the deployable output — there is no build.

`vercel.json` sets `cleanUrls`, so `/services` serves `services.html`. It also
pins `framework: null` with empty `installCommand` and `buildCommand`, because
`package.json` (which exists only to give the tourism tooling npm-style
commands) would otherwise trip Vercel's zero-config detection into running a
Node build and publishing something other than these files.

Note that `vercel.json` is schema-validated on every deploy and rejects any key
it does not recognise — including a `"//"` comment key, which fails the build
outright. Explanations go here, not in that file.

`.vercelignore` keeps the engine out of the deployment: `tools/`, the country
datasets, the cache and this README are build-time inputs, not things a visitor
should be able to fetch. The generated `tourism/*.html` and `images/` still ship.

## Before this goes live

Two things are placeholders, and both are deliberate:

**1. The contact details.** Phone numbers, addresses, opening hours, licence numbers and
the bonjour@kamerun.cm address are illustrative. Search the HTML and replace them.

**2. The enquiry form.** A static site cannot receive a form submission, so the form
composes a pre-filled email to bonjour@kamerun.cm and opens the visitor's mail app. It does not
post anywhere and it never claims a message was delivered when it wasn't. To take real
submissions, point the form at a service (Formspree, Basin, a Vercel function) and
replace the submit handler at the bottom of each page.

Prices, itineraries and figures are illustrative too. Check them before publishing.

## The pictures

Apart from the two band posters, every image in `images/` is an original SVG
illustration — twenty-seven scenes drawn in
the site's own five colours, in a flat relief-print style: the upper slopes of Fako, the
Lobé falls, the Waza waterholes, the Bénoué, the Mandara spires, Foumban's craft street,
the offices in Buea and Bonapriso. Each one is drawn to match the `alt` text of the slot
it fills, so no picture is used for two different things.

They are generated, not hand-edited. The source is `tools/build_images.py`:

    python3 tools/build_images.py        # rewrites images/, no dependencies

Nothing on the site depends on that script — it is a static folder of SVGs at deploy
time, and there is still no build step.

**They are stand-ins, and the site no longer uses most of them.** Once the tourism
resolver has fetched real photographs, `npm run tourism:adopt` swaps them onto the
five hand-written pages — 32 of the 34 slots at the time of writing. The drawing
stays behind in `data-illustration` on each `<img>`, so `npm run tourism:adopt --
--revert` puts every one back, byte for byte, and a slot with no resolved photo
keeps its drawing rather than breaking.

The mapping is exact rather than guessed: each Cameroon category names the
illustration it stands in for (`local` in the country dataset), and those subjects
were written *from* the drawings in the first place.

**Swapping in your own photographs.** Drop one in at the same path and change the
extension and the `src` (grep for the name). Landscape, roughly 3:2, at least
1600px wide for the full-bleed bands. The page crops these to 3/4, 4/5, 5/4 and
1/1 with `object-fit: cover`, so keep the subject near the centre — the
illustrations are composed the same way, inside the middle 800px. Add
`data-locked="true"` to the `<img>` if the choice is deliberate and the resolver
should never overwrite it.

## The image generation engine

Every `<img>` on the five hand-written pages is a **slot**: a shape the
stylesheet already decided, and a sentence already written about what belongs in
it. That sentence is the slot's alt text, written for the drawing before any
photograph existed — so it describes intent, not a search result. The engine
compiles it into an instruction, generates a picture from it, and puts the
result beside the stock photograph so you can choose.

    npm run tourism:placements      # every image slot, and what belongs in each
    npm run tourism:prompts         # the instruction each one compiles to
    npm run tourism:generate -- --dry-run    # what it would send, and the cost
    npm run tourism:generate        # make the candidates
    npm run tourism:intake          # match images you uploaded to slots
    npm run tourism:compare         # contact sheet: every option, side by side
    npm run tourism:place -- picks.json      # publish the ones you chose

**A category is not a placement.** "Waterfalls" is a subject; the third picture
down on services.html is a *place*, and generating for one is not generating for
the other. The Lobé falls appear on two pages at two ratios, so they are two
jobs and two pictures — a 4:5 crop of a frame composed for 5:4 is a photograph
of the middle third of a waterfall. `placements` prints exactly where each
duplicate lands and at what shape.

**Instructions are readable before they are expensive.** `prompts` prints all 32
without sending anything; `generate --dry-run` adds the size and the estimated
cost per slot. Every instruction is built from `tourism/style.json` — the
photographic look, the direction for each of the 27 categories, the composition
phrases and the things to avoid — so changing how every generated image looks is
one edit to a data file, not a code change. Same input, same instruction, every
time.

The avoid-list is not boilerplate. It bans text, lettering, watermarks, collage
and travel-poster layouts, because the two band pictures on the home page
arrived as finished posters with their own headlines baked in and the whole page
had to be rebuilt around them. A generator will produce exactly that unless told
not to.

### Choosing

Nothing generated goes near the site. Candidates land in `tourism/candidates/`,
and `compare` writes a contact sheet — one row per slot, showing what the page
uses now next to every generated and uploaded candidate, **all cropped to the
shape that slot actually imposes**, because judging a 3:2 frame that will be
delivered at 4:5 tells you nothing.

Picking writes to localStorage and downloads a `picks.json`; `place` applies it.
That round trip is deliberate — a static page cannot write to the repository,
and a review tool that could silently change the site would be a worse tool.

`place` copies the chosen file into `images/generated/` (or `images/uploads/`),
rewrites that one `<img>`, and marks it `data-placed="true"` so `adopt` can
never overwrite a picture a person chose. `place --revert` returns a slot to its
illustration; run `adopt` after it to put a resolved stock photograph back,
which together is a byte-identical round trip.

### Images you upload

Drop files in `incoming/` and run `npm run tourism:intake`. Each one is measured
and matched against every slot, using three signals in ascending cost:

    name         a file named exactly after a slot IS that slot's picture.
                 Not a guess — the same identifier.
    filename     failing that, the words in the name. "mount-cameroon-trekkers.jpg"
                 says more about where it belongs than any pixel analysis.
    shape        how much of the frame the slot's crop discards. A penalty,
                 never a veto.
    description  with --describe, the vision model is asked what the picture
                 shows, and that sentence is scored against each slot's
                 instruction.

A filename that *is* a slot id — `waza-elephants.jpg` — is decisive: it is not a
guess, it is the same identifier. Shape is a penalty and never a veto, because
every slot on this site crops with `object-fit: cover` and the drawings these
photographs replace were 3:2 frames cropped to 4:5 and 1:1 from the start; a 47%
crop of the right subject beats a perfect fit of the wrong one.

Without `--describe` it says so, so a confident-looking match is never mistaken
for one the machine actually looked at.

**Pictures a model made** go in `incoming/generated/` instead. They are matched
identically, but they carry the generated provider, so their credit reads
"AI-generated" rather than passing as somebody's photograph. Matches are **proposals**: they go into
the same pool, appear on the same contact sheet, and are placed by the same
command. An unmatched file is reported by name rather than guessed at.

### Disclosure

A generated picture and an uploaded photograph are two different things to a
visitor, so they are two providers with two hosts rather than one with a flag.
A generated image's credit line reads *"AI-generated · gpt-image-1"* — a
synthetic photograph of a real place presented as a photograph of that place is
a lie told to a visitor. An uploaded photograph carries its owner's credit, or
none, and is never labelled AI.

Neither has a CDN behind it, so `srcset` carries the one real width instead of
four identical URLs with four different width descriptors — the browser believes
descriptors, and told a 1024px file is 2400px wide it will pick it for a 2400px
slot and scale it up.

**Weight.** `place` copies files as-is, so the site accumulated 40 MB across
29 images — 23 MB of it on the home page, with 3 MB frames feeding 190px
columns. `npm run tourism:optimise` fixes it: each image is resized to twice
the widest box its slot is ever painted at, re-encoded as JPEG q82 (PNG only
where there is real transparency), and every `src` and `srcset` pointing at it
is rewritten — including the width descriptor, which would otherwise tell the
browser a 900px file is 3000px wide.

It needs Pillow, which is the one dependency in this project and deliberately
not a runtime one: it prepares images, it never serves them, so it stays out of
`package.json` and the deployed site is still static files. Where Pillow is
missing the command says so and changes nothing;
`.github/workflows/tourism-optimise.yml` runs it on a runner, weighs the pages
before and after, fails if any image reference is left dangling, and commits.

`OPENAI_API_KEY` is server-side only, on exactly the same terms as the other
two: read from the environment by a CLI on a developer or CI machine, never
written to the cache, never rendered into a page, never committed.
`.github/workflows/tourism-generate.yml` runs it on a runner, defaults to a dry
run, and fails if the key appears anywhere in the working tree.

## The tourism image system

`/tourism/<country>` pages are generated, one per country, each covering the same
27 tourism categories. Adding a country is one JSON file — no template, no
component, no code change.

    tourism/categories.json          the 27 categories, their order, and delivery presets
    tourism/countries/<slug>.json    editorial content: caption, description, subject, focal
    tourism/cache/images.json        resolved image metadata — written only by the resolver
    tools/tourism/providers/         one file per image provider
    tourism/<slug>.html              GENERATED — do not edit by hand
    tourism/REPORT.md                GENERATED — completeness report
    tools/tourism/                   the engine

Content and resolved images are deliberately separate files. An editor can rewrite
every caption without refetching an image, the resolver can refresh every image
without touching a word of copy, and no one editing content can hand-write an
image URL that nobody fetched.

### Commands

    npm run tourism:resolve-images     # fill image slots: Unsplash, then Pexels
    npm run tourism:validate           # completeness + integrity per country
    npm run tourism:status             # Country | Category | Photo ID | CDN URL | Status
    npm run tourism:queries            # the search query for every slot
    npm run tourism:render             # write tourism/<slug>.html
    npm run tourism:verify             # check the rendered HTML
    npm run tourism:scaffold -- --country ghana
    npm run tourism:providers          # country x provider report
    npm run tourism:all                # validate, render, verify, report
    npm test                           # the resolver suite, against local mocks

Each is a one-line wrapper over `python3 tools/tourism/build.py <command>`; use
either. Flags: `--country <slug>`, `--category <id>`,
`--provider unsplash|pexels`, `--force`.

Stdlib only, no npm dependencies, and deliberately **no `build` script** — the
deployed site is static files, and a build script here would make the host try to
run one.

### Where the images come from

Two providers, in priority order:

    Unsplash  ->  Pexels  ->  local illustration  ->  unresolved

Both are official APIs, and in both cases the URL is fetched to prove it works
before it is stored:

    cp .env.example .env      # then fill in either key, or both
    npm run tourism:resolve-images

    UNSPLASH_ACCESS_KEY=      free, https://unsplash.com/developers
    PEXELS_API_KEY=           free, https://www.pexels.com/api/

Either key alone is enough. With both, Unsplash is tried first and Pexels fills
what it cannot — Unsplash wins ties, and Pexels only displaces it when it scores
*clearly* better, so the fallback cannot quietly become the default.

For each slot, `resolve` walks the query ladder; at every rung it asks each
available provider, scores the candidates, rejects anything the intended crop
would ruin or that is already used anywhere in the dataset, fetches the delivery
URL, and only then writes the record:

    { country, category, caption, description, provider, photoId, imageUrl,
      thumbnailUrl, sourceUrl, photographer, photographerUrl, width, height,
      aspectRatio, alt, query, focalPoint, createdAt, verifiedAt }

Every value comes from the API response or the country dataset. Nothing is
assembled from an id, on either provider.

**Relevance is judged, not assumed.** Search rank alone is how a generic savanna
sunset ends up under "Uganda / Wildlife" — it came back for the query and it was
big enough. `relevance.py` reads the text each provider writes about a photo
(Unsplash's `alt_description`, `description`, tags and location; Pexels' `alt`)
and weighs it against the subject, the category, the resolution and how much of
the frame the intended crop discards. A photo whose description matches nothing
but the country name scores below the floor and is rejected: containing the word
"Uganda" is not a reason to publish a picture under gorilla trekking.

**Adding a third provider** is one file in `tools/tourism/providers/` and one
entry in the registry. The resolver, renderer, cache, validator and pages need
no change — none of them knows a provider name.

**Both keys are server-side only.** They are read from the environment by a CLI
that runs on a developer or CI machine, never written to the cache, never
rendered into HTML, never committed, and never sent to a browser — the site is
static files, so a visitor's browser talks to the image CDNs and nothing else.
`.env` is git-ignored; `.env.example` declares both variables with no values.

The run is **resumable**: anything already cached is skipped and its photo id
stays reserved, so re-running after a rate limit costs nothing and cannot hand
the same picture to a second slot. `--force` re-resolves anyway. The cache is
saved even if the run is interrupted.

**There is no offline path that produces an image URL.** With no key or no route
to either API, `resolve` reports *"Tourism image resolution requires
UNSPLASH_ACCESS_KEY or PEXELS_API_KEY."* and writes nothing; unresolved slots render that same
sentence in place of the picture rather than a broken `<img>`. A photo id nobody
has fetched is a broken image with extra steps, so the system will not invent one.

Until a slot is resolved, the page renders the entry's `local` illustration if it
has one, and the warning above if it does not. Nothing breaks; the page is only
less specific.

### Resolving without a local setup

`.github/workflows/tourism-resolve.yml` runs the resolver on a GitHub runner,
which has the internet access a sandboxed environment may not. Add the key once
as a repository secret — Settings → Secrets and variables → Actions →
`UNSPLASH_ACCESS_KEY` — then Actions → *Resolve tourism images* → Run workflow.
It takes `country`, `category` and `force` inputs, commits the cache and the
regenerated pages back to the branch, and fails the run if the key value appears
anywhere in the working tree.

Use the Unsplash **Access Key**. The Secret key is for OAuth token exchange and
this system never needs it.

### Tests

    npm test

73 checks against local mocks of **both** provider APIs — no credentials, no
network. They prove that each provider's responses are parsed correctly, that
ids and URLs come from the response, that no code path fabricates an id, that
Pexels takes over when Unsplash is empty or down, that both being unavailable
fails safely, that relevance outranks search order, that duplicates are caught
(and that the same id on two providers is *not* a duplicate), that the cache
prevents repeat requests, that a half-finished run resumes, that all 27
categories resolve, that queries are country-specific, that the rendered page
is identical in shape whichever provider won, and that neither key appears in
any committed artifact.

`.github/workflows/tourism-tests.yml` runs the same suite on every push, plus
validate, render and verify, and fails if `tourism/*.html` is stale relative to
the data. No secret required.

### Delivery

`categories.json` defines six roles — hero, feature, card, portrait, panoramic,
thumb — each with an aspect ratio, a CDN width, a `srcset` ladder and a `sizes`
hint. Each provider builds its own delivery URLs, so a component never learns
where a photograph came from. A category's role is its *canonical* shape and decides which orientation
the resolver searches for. The shape it is *delivered* at is decided by the
section that renders it, because the same photograph legitimately appears as a
21:9 band on one page and a 4:3 tile on another.

Every entry carries a `focal` point, which is pushed into the CDN crop
(`crop=focalpoint&fp-x&fp-y`) as well as CSS `object-position`. Without it the
CDN throws away whatever is not in the middle of the frame. Every `<img>` gets
`width`, `height` and `aspect-ratio` so the box is reserved before the bytes
arrive, and everything below the hero is `loading="lazy"`.

### Completeness

`validate` refuses to publish a country that is not complete. A country missing
three categories reports `24/27` and names them, and `render` skips it rather
than shipping a page with holes in it. `verify` then reads the generated HTML
back and checks that all 27 categories actually rendered, that no image
reference is broken, and that every image carries alt text and a reserved box.

## The fixed-window bands

The home page has two **fixed-window bands**: the picture locks to the viewport and
the section travels across it like a window. It is CSS only, no JavaScript.

The construction is fragile in one specific way. The section clips its own fixed child
with `clip-path: inset(0)`, but the section must never become that child's *containing
block* — so **do not add `transform`, `filter`, `backdrop-filter`, `perspective`,
`will-change` or `contain`** to `.band`, to the picture, or to anything between them and
`<html>`. Any one of those turns `fixed` into `absolute`: the picture starts scrolling
with the page, nothing errors, and the effect is silently gone. `background-attachment:
fixed` is not a substitute — iOS Safari ignores it.

**Nothing is laid over the photograph.** Both bands run a chosen poster —
`images/band-cameroon.png` and `images/band-africa.png` — which already carries
its own set headline, so there is no scrim, no tint and no wash: the veil spans
are still there, but their `background` is `none`.

Legibility comes from an opaque plate instead. That is not decoration. Bare type
fails here twice over: it collides with the wording baked into the artwork, and
the copy travels across a picture that does not move, so there is no safe corner
to place it in — every corner passes under the copy at some scroll position. A
plate in the site's own paper answers both, and it lightens the area it covers
rather than darkening it.

Those two `<img>` tags carry `data-locked="true"`. That is what keeps
`tourism:adopt` from replacing hand-picked artwork with a search result; it is
honoured in both directions, so `--revert` leaves them alone as well.

## Origin

Generated from the `tour-fakojourneys01` master (style: `laterite-relief`) in the
[Architect-AI](https://github.com/ICOFCUCAM/Architect-AI) master library, then extracted
as a standalone site. The design inverts the usual pairing: condensed uppercase display over a transitional serif for reading, with a transect bar on the home page whose column heights are real altitudes, 0 m at Kribi to 4,095 m on Mount Cameroon.
