# Fako Journeys

Mount Cameroon treks, the Kribi coast, Waza in the Sahel and the Bamenda highlands — a Cameroonian tour operator's website.

A five-page static site: home, services, pricing, about, contact. No build step, no
dependencies, no framework — plain HTML and CSS. Deploy the folder as-is.

## Deploying

Import the repository into Vercel (or any static host) and deploy. There is nothing to
configure: `vercel.json` sets `cleanUrls`, so `/services` serves `services.html`.

## Before this goes live

Two things are placeholders, and both are deliberate:

**1. The contact details.** Phone numbers, addresses, opening hours, licence numbers and
the bonjour@fakojourneys.cm address are illustrative. Search the HTML and replace them.

**2. The enquiry form.** A static site cannot receive a form submission, so the form
composes a pre-filled email to bonjour@fakojourneys.cm and opens the visitor's mail app. It does not
post anywhere and it never claims a message was delivered when it wasn't. To take real
submissions, point the form at a service (Formspree, Basin, a Vercel function) and
replace the submit handler at the bottom of each page.

Prices, itineraries and figures are illustrative too. Check them before publishing.

## The pictures

Every image in `images/` is an original SVG illustration — twenty-seven scenes drawn in
the site's own five colours, in a flat relief-print style: the upper slopes of Fako, the
Lobé falls, the Waza waterholes, the Bénoué, the Mandara spires, Foumban's craft street,
the offices in Buea and Bonapriso. Each one is drawn to match the `alt` text of the slot
it fills, so no picture is used for two different things.

They are generated, not hand-edited. The source is `tools/build_images.py`:

    python3 tools/build_images.py        # rewrites images/, no dependencies

Nothing on the site depends on that script — it is a static folder of SVGs at deploy
time, and there is still no build step.

**Swapping in photographs.** Drop a photograph in at the same path and change the
extension and the `src` (each file is referenced once or twice; grep for the name).
Landscape, roughly 3:2, at least 1600px wide for the full-bleed bands. The page crops
these to 3/4, 4/5, 5/4 and 1/1 with `object-fit: cover`, so keep the subject near the
centre — the illustrations are composed the same way, inside the middle 800px.

## The tourism image system

`/tourism/<country>` pages are generated, one per country, each covering the same
27 tourism categories. Adding a country is one JSON file — no template, no
component, no code change.

    tourism/categories.json          the 27 categories, their order, and delivery presets
    tourism/countries/<slug>.json    one file per country, 27 entries each
    tourism/<slug>.html              GENERATED — do not edit by hand
    tourism/REPORT.md                GENERATED — completeness report
    tools/tourism/                   the engine

### Commands

    python3 tools/tourism/build.py scaffold --country ghana   # new country, 27 empty slots
    python3 tools/tourism/build.py validate                   # completeness per country
    python3 tools/tourism/build.py queries                    # the search query for every slot
    python3 tools/tourism/build.py resolve                    # fill images from Unsplash
    python3 tools/tourism/build.py render                     # write tourism/<slug>.html
    python3 tools/tourism/build.py verify                     # check the rendered HTML
    python3 tools/tourism/build.py all                        # validate, render, verify, report

Stdlib only. The deployed site is still static files; the engine is a developer
tool, not a runtime dependency.

### Where the images come from

Every image is resolved from **Unsplash**, by the API, and then fetched to prove
it works before the URL is stored:

    export UNSPLASH_ACCESS_KEY=...        # free, https://unsplash.com/developers
    python3 tools/tourism/build.py resolve

`resolve` searches a query built from the country name and the entry's `subject`,
rejects photos the intended crop would ruin, rejects any photo already used
anywhere in the dataset, fetches the delivery URL, and only then writes it into
the country JSON with its photographer credit.

**There is no offline path that produces an image URL.** With no key or no route
to Unsplash, `resolve` reports why and writes nothing. A photo id nobody has
fetched is a broken image with extra steps, so the system will not invent one.

Until a slot is resolved, the page renders the entry's `local` illustration if it
has one, and an honest "image pending" tile if it does not. Nothing breaks; the
page is only less specific.

### Delivery

`categories.json` defines six roles — hero, feature, card, portrait, panoramic,
thumb — each with an aspect ratio, a CDN width, a `srcset` ladder and a `sizes`
hint. A category's role is its *canonical* shape and decides which orientation
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

The scrim lives inside the picture, not on the band, and is a tint rather than a
blackout, so the picture keeps its own light.

## Origin

Generated from the `tour-fakojourneys01` master (style: `laterite-relief`) in the
[Architect-AI](https://github.com/ICOFCUCAM/Architect-AI) master library, then extracted
as a standalone site. The design inverts the usual pairing: condensed uppercase display over a transitional serif for reading, with a transect bar on the home page whose column heights are real altitudes, 0 m at Kribi to 4,095 m on Mount Cameroon.
