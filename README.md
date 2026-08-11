# Fako Journeys

Mount Cameroon treks, the Kribi coast, Waza in the Sahel and the Bamenda highlands — a Cameroonian tour operator's website.

A five-page static site: home, services, pricing, about, contact. No build step, no
dependencies, no framework — plain HTML and CSS. Deploy the folder as-is.

## Deploying

Import the repository into Vercel (or any static host) and deploy. There is nothing to
configure: `vercel.json` sets `cleanUrls`, so `/services` serves `services.html`.

## Before this goes live

Three things are placeholders, and all three are deliberate:

**1. The photographs.** Every image is an SVG placeholder in `images/`, each labelled
with the slot it fills (`hero`, `coverage.2`, `services-grid.1`, and so on). Drop a real
photograph in at the same path — keep the filename, change the extension and update the
`src` if you use `.jpg`. Eleven slots in total. Landscape, roughly 3:2, and at least
1600px wide for the full-bleed bands.

**2. The contact details.** Phone numbers, addresses, opening hours, licence numbers and
the bonjour@fakojourneys.cm address are illustrative. Search the HTML and replace them.

**3. The enquiry form.** A static site cannot receive a form submission, so the form
composes a pre-filled email to bonjour@fakojourneys.cm and opens the visitor's mail app. It does not
post anywhere and it never claims a message was delivered when it wasn't. To take real
submissions, point the form at a service (Formspree, Basin, a Vercel function) and
replace the submit handler at the bottom of each page.

Prices, itineraries and figures are illustrative too. Check them before publishing.

## The fixed-window bands

The home page has two **fixed-window bands**: the photograph locks to the viewport and
the section travels across it like a window. It is CSS only, no JavaScript.

The construction is fragile in one specific way. The section clips its own fixed child
with `clip-path: inset(0)`, but the section must never become that child's *containing
block* — so **do not add `transform`, `filter`, `backdrop-filter`, `perspective`,
`will-change` or `contain`** to `.band`, to the picture, or to anything between them and
`<html>`. Any one of those turns `fixed` into `absolute`: the photograph starts scrolling
with the page, nothing errors, and the effect is silently gone. `background-attachment:
fixed` is not a substitute — iOS Safari ignores it.

The scrim lives inside the picture, not on the band, and is a tint rather than a
blackout, so the photograph keeps its own light.

## Origin

Generated from the `tour-fakojourneys01` master (style: `laterite-relief`) in the
[Architect-AI](https://github.com/ICOFCUCAM/Architect-AI) master library, then extracted
as a standalone site. The design inverts the usual pairing: condensed uppercase display over a transitional serif for reading, with a transect bar on the home page whose column heights are real altitudes, 0 m at Kribi to 4,095 m on Mount Cameroon.
