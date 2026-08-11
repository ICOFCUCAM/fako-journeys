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
