# The photographic standard, and what fails it

The owner's brief for this site is that it should be *the world's most
considered way to discover Africa*. That has a photographic consequence, and it
is written down here so it can be applied to the next batch as well as this one.

## The standard

A picture on this site is

- **bright, at the exposure it was taken at.** Dark because the room was dark is
  fine. Dark because it was graded down is not.
- **naturally coloured.** Skin reads as skin. No orange/teal split-tone, no HDR
  halo, no haze added after the fact, no saturation past what the light gave.
- **documentary in composition.** Somebody was standing there. It shows a thing
  happening rather than a thing arranged to be photographed.
- **real.** Nothing generated, and nothing composited out of several places into
  one frame. `images/generated/` is where anything synthetic lives; being in
  `images/uploads/` is the claim that a camera made it.
- **unlettered.** No burnt-in titles, wordmarks, logos, watermarks or handles.
  `images/uploads/PROVENANCE.md` records a Douala photograph turned away for a
  handle in one corner; a whole headline across the frame is the same rule.

## Measuring it

`tools/tourism/grade.py` reports, for any list of images on stdin:

    lum     mean luminance, and how much of the frame is crushed or blown
    sat     mean and 90th-percentile saturation
    split   the orange/teal signature — the difference in (R−B) between the
            brightest and darkest quarter of the frame
    halo    the HDR signature — mean deviation from a heavily blurred copy

**These rank; they do not judge.** Three of the worst-scoring frames on this
site are honest: a bronze foundry is dark, a blue-hour city is saturated, and a
sunset is warm at the top and cool at the bottom because that is what a sunset
is. The numbers say where to look. The looking is still the decision.

## The audit of 15 August

Eighty-three placed images measured, the worst looked at.

### Fails the standard outright

| file | placed at | why |
|---|---|---|
| `images/band-africa-1536w.jpg` | cameroon.html | generated composite; headline burnt in; the continent drawn as elephants, giraffes, leopards, a jeep, thatched huts, pyramids, Kilimanjaro and Victoria Falls in one frame |
| `images/band-cameroon-1717w.jpg` | cameroon.html | the same, with a script wordmark and a strapline |
| `images/generated/site-pricing-park-permit-post-1536w.jpg` | pricing.html, tourism/compare.html | a fabricated national park entry post with invented fees, on the page about prices; one sign reads "INTERKENNVATION" |
| `images/generated/site-about-mount-guide-portrait-1254w.jpg` | about.html | a synthetic person standing in as a guide, skin graded hard orange |
| `images/uploads/window-zambia-1200w.jpg` | the window | monochrome orange, acacia silhouette, haze, a vehicle on a ridge. Saturation 216 of 255, the highest here |
| `images/uploads/window-kenya-1200w.jpg` | the window | orange/teal: peach sky and grass against a teal mountain |

### The owner's call

- `images/generated/site-index-mount-ascent-walkers-1536w.jpg` and
  `site-index-mount-summit-grass-1536w.jpg` (cameroon.html) meet every line of
  the standard except the last: bright, ungraded, documentary — and synthetic.
- `images/uploads/swahili-coast-ngalawa-1200w.jpg` is a real photograph of a
  real outrigger, and it is a faceless sunset silhouette.

### Flagged by the numbers, kept

- `site-index-foumban-bronze-caster` — luminance 25, 29% of the frame at black.
  It is a foundry lit by the pour.
- `city-dar-es-salaam-blue-hour`, `city-nairobi-night`, `city-cape-town` —
  saturation is high because sodium and LED light are.
- `gorilla-trekkers-768w` — over-sharpened, and the only image here below the
  800px floor. Kept for now; wants replacing rather than removing.
