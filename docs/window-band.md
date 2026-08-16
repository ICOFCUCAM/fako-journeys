# The window band

*How the "Imagine tomorrow morning" section is built, and why every part of it is
the way it is. Written so it can be rebuilt from scratch by somebody who has
never seen this repository.*

The band is the section where a photograph appears to stand still while the words
travel across it. On the homepage it appears twice: once at Amboseli before
sunrise (`.wa-seam--dawn`), once over the Waza herds. It is two CSS properties and
no JavaScript.

---

## 1. The concept

### What the section is for

The homepage asks *what do you want to feel* in the abstract, eight ways, in a
grid of type. That grid is good at breadth and bad at conviction — a reader who
has never been can pick the word "wildlife" off a card without any picture in
their head of what the word costs them to get to.

The band answers the same question **once, concretely, in the second person**:

> You wake before it is light. No alarm, no traffic, no office — just voices
> outside and somebody loading the vehicle. You step out into air cold enough to
> see, and the grass is still wet through.

Second person, present tense, one morning. Not "our safaris begin early."

### And it is the door into one product, not a general mood

The band used to end on "a whole day in front of you" with a button to the
journey tunnel — the same invitation every other section on the homepage makes.
The strongest picture on the site was spending itself on a link an eight-card
grid already provides.

It is now the first morning of a **Trans Afrique** crossing: same photograph,
same effect, different meaning. *A beautiful African morning* became *the first
morning of a continental journey*, which is a difference in what the reader is
being asked to want.

Two facts happen to be literally inside this frame, and both of them are the
product:

- the grass is in Kenya and the mountain on its horizon is in Tanzania, so **the
  border is in the picture** — which is why the section can carry
  `Kenya → Tanzania` as a caption rather than a claim;
- the roof is loaded — a box and a bag strapped over the rack — so *"the roof is
  loaded for longer than a day"* is a description.

The copy rule did not bend to accommodate a new product. The frame already held
it.

### The band is a door, not a summary

No routes, no lengths, no prices, no team, no park fees. A visitor two screens
into a homepage is not choosing between a 21-day East and a 24-day West; they
are deciding whether crossing a continent is a thing they want at all. A price
there answers a question they have not asked, and invites them to compare four
options before wanting any of them.

So the split is:

| | says |
|---|---|
| **The band** | *Imagine tomorrow morning.* → **Enter Trans Afrique** |
| **Homepage §07** | where it goes — four names, four country chains, one floor price → **See how a crossing works** |
| **`/trans-afrique`** | levels, lengths, bands, the six support domains, the medical note, what the fee is and is not |

Each step answers exactly one more question than the last. Nothing on the
homepage explains the expedition; the reader who wants that arrives at the page
by choosing to. Two doors to the same place must never use the same verb —
"Enter" and "See how it works" are different offers, "Explore" twice is one
offer printed twice.

### The rule that makes the copy work

**The copy is written to the photograph. The photograph is not found for the
copy.** Every noun in the paragraph above is visible in the frame behind it —
the loaded vehicle, the wet grass, the mountain on the horizon.

This rule has teeth. The section was originally set at the Mount Cameroon
registration hut in Buea, and its best line was *somebody writing your name in a
book and pointing at a mountain drawn in chalk*. When the photograph changed to
Amboseli there was no register and no chalk map in the frame, so the line was
deleted rather than kept over a picture that does not show it. A better line lost
is cheaper than a sentence the picture contradicts.

### Not parallax

Parallax moves the picture slower than the page. This does not move the picture
at all. The photograph is nailed to the viewport; the *section* is a window that
slides down over it. The reader's sense is of standing still inside a moment
rather than of an effect being performed at them.

---

## 2. The mechanism

Two rules. Everything else is decoration.

```css
.wa-seam     { position: relative; clip-path: inset(0); min-height: 130svh;
               display: flex; align-items: center; }
.wa-seam-pic { position: fixed; inset: 0; z-index: 0; }
.wa-seam-pic img { width: 100%; height: 100%; object-fit: cover; display: block; }
```

Why it works:

1. `position: fixed` on the picture takes it out of the scroll entirely. It is
   one viewport of photograph, permanently filling the screen.
2. `clip-path: inset(0)` on the section establishes a **clip region**. A
   fixed-position descendant is clipped to its nearest clipping ancestor — so the
   fixed picture is only painted inside the section's own box.
3. The section box scrolls normally. The picture does not. What the reader sees
   is a moving aperture onto a stationary image.

`clip-path` also makes the section a stacking context, which is why the copy's
`z-index: 1` cannot climb over a fixed masthead and no `isolation` is needed.

### 130svh, not 130vh

On a phone, `vh` is the *large* viewport and changes as browser toolbars hide and
reveal during scroll — which would resize the window while the reader is inside
it. `svh` is the small viewport and does not move.

### The one way this breaks, and it breaks silently

Six properties make an element a **containing block for fixed-position
descendants**:

```
transform   filter   backdrop-filter   perspective   will-change   contain
```

Any one of them, on any element between `.wa-seam-pic` and `<html>` — including
the section itself — demotes that `fixed` to `absolute`. The picture then scrolls
like an ordinary image. **No error is raised.** The page does not look broken; it
looks merely ordinary. A hover effect or a drop-shadow added to the section two
years later is enough to do it.

This is why the effect is asserted in a test rather than described in a comment
(§5). A comment does not survive the next hover effect.

### Why not `background-attachment: fixed`

It is the other way to do this, and it is not used: iOS Safari ignores it
outright. That is a silent failure on the platform most of this page's readers
are on.

---

## 3. The tint

Ivory type over a photograph needs the photograph darkened. How that darkening is
applied is where most implementations of this effect go wrong.

### The tint is fixed *with* the picture, not laid on the band

```html
<div class="wa-seam-pic">
  <img …>
  <span class="wa-seam-tint" aria-hidden="true"></span>
</div>
```

`.wa-seam-tint` is `position: absolute; inset: 0` **inside the fixed picture**, so
it inherits the picture's stillness. Put the tint on the scrolling band instead
and it travels while the photograph stands still — the shading visibly crawls
across the image.

### A wash, not a scrim

The point of the band is the photograph. A flat 80% black makes the contrast
trivial and the picture pointless. This is a transparent wash in the brand's deep
forest (`#10251F`) rather than black, so the band belongs to the palette and the
frame stays warm and luminous under it.

### Graded on desktop, because the copy is pinned left

```css
.wa-seam-tint { position: absolute; inset: 0; background:
  linear-gradient(100deg,
    color-mix(in srgb, var(--c-primary) 82%, transparent)  0%,
    color-mix(in srgb, var(--c-primary) 78%, transparent) 34%,
    color-mix(in srgb, var(--c-primary) 62%, transparent) 50%,
    color-mix(in srgb, var(--c-primary) 24%, transparent) 72%,
    color-mix(in srgb, var(--c-primary)  6%, transparent) 100%); }
```

A **flat** wash cannot carry a photograph with a range in it. Measured against
the actual pixels behind the glyphs on the Waza frame: the herd is lit from the
front under a pale sky, so ivory crossing a sunlit elephant came out at **1.00:1
— invisible** — while the same wash over the shaded left was already heavier than
it needed to be. Raising a flat wash until the worst pixel passes means about 80%
everywhere, which is the scrim this is built not to be.

So the weight goes where the type is and is released where it is not. Across the
width it averages 44%; the right third is under 10% and the plain keeps its
light.

### Every photograph gets its own grade

```css
.wa-seam--dawn .wa-seam-tint { background:
  linear-gradient(100deg,
    color-mix(in srgb, var(--c-primary) 76%, transparent)  0%,
    color-mix(in srgb, var(--c-primary) 72%, transparent) 34%,
    color-mix(in srgb, var(--c-primary) 54%, transparent) 50%,
    color-mix(in srgb, var(--c-primary) 18%, transparent) 72%,
    color-mix(in srgb, var(--c-primary)  3%, transparent) 100%); }
```

The dawn frame is pre-sunrise — the ground under the copy is shadow and the only
bright thing is the canopy along the top — so the Waza wash was spending twenty
points it did not need and taking the photograph down with it.

**The headroom was much less than it looked.** Giving back all twenty points
(62/56/40/14/2) put the worst line at **2.93:1**. The relationship between wash
strength and measured contrast over this frame is far steeper than the spare
margin suggests, because most of the copy sits over forest already close to the
tint's own colour. Six points was what there was to give. Do not estimate this —
measure it, per photograph.

### Flat below 950px, and it has to be flat

```css
@media (max-width: 950px) {
  .wa-seam       { min-height: 104svh; }
  .wa-seam-copy  { padding: 0 28px; }
  .wa-seam-inner { max-width: none; }
  .wa-seam-tint  { background: color-mix(in srgb, var(--c-primary) 68%, transparent); }
  .wa-seam--dawn .wa-seam-tint
                 { background: color-mix(in srgb, var(--c-primary) 66%, transparent); }
}
```

The desktop wash can be graded **horizontally** because the copy's horizontal
position never changes — it is pinned to the left column, so weight put on the
left stays under the type for the whole travel.

Vertically there is no such thing. The copy traverses the entire viewport while
the tint is fixed to it, so **every line passes through every band of a vertical
gradient**. Grading it does not fix anything; it only moves which scroll position
fails. Measured, a 16/64/78/16 vertical band left 16px type at **1.81:1** at the
moment the copy crossed the released edge.

So on narrow screens it is flat, and flat must be set by the worst pixel the copy
will ever cross. Cover-fitting a 1600×1067 frame into a phone crops to the middle
of the picture — sunlit dust at `rgb(246,204,147)` with the tint taken back out —
and carrying ivory over that at 4.5:1 needs **68%**.

That is more than half strength, and it is the honest price of putting 16px of
text over a bright photograph on a narrow screen. The alternative worth knowing
about: stop putting copy on the picture below 950px and let the band be picture
alone. That keeps it fully luminous and is a design decision, not a defect.

The band also loses height on a phone. 130svh of one photograph is three
thumb-flicks, which stops reading as a moment and starts reading as a stall.

---

## 4. The type

```css
.wa-seam-copy  { position: relative; z-index: 1; width: 100%; max-width: 1240px;
                 margin: 0 auto; padding: 0 44px; }
.wa-seam-inner { max-width: 560px; }

.wa-seam-stamp { font-family: var(--fj-mono); font-size: 10px; letter-spacing: .22em;
                 text-transform: uppercase; color: var(--c-bg); margin: 0; }
.wa-seam-copy h2 { font-family: var(--fj-display); font-weight: 700;
                 text-transform: uppercase; letter-spacing: -.01em; line-height: 1.04;
                 font-size: clamp(29px, 3.5vw, 52px); margin: 16px 0 0; color: var(--c-bg); }
.wa-seam-hr    { display: block; width: 64px; height: 2px; margin: 26px 0;
                 background: var(--c-accent-lit); }
.wa-seam-say   { font-size: 17px; line-height: 1.6; color: var(--c-bg);
                 max-width: 44ch; margin: 0; }
.wa-seam-go    { display: inline-block; margin-top: 26px; font-family: var(--fj-mono);
                 font-size: 10px; letter-spacing: .2em; text-transform: uppercase;
                 color: var(--c-bg); border-bottom: 2px solid var(--c-accent-lit);
                 padding-bottom: 6px; }
```

Six elements, in this order, and no more: **stamp → route → headline → rule →
paragraph → kicker → link.** The stamp (`Trans Afrique · before six, engine
already running`) does the work of a caption without being one — it names the
product and the hour before the headline asks the reader to imagine it. The
route line under it (`Kenya → Tanzania`) is the same mono size at wider tracking
rather than a smaller subtitle: it is not subordinate to the stamp, it is the
other half of it.

The **kicker** — `One continent is waiting.` — is the turn. Everything above it
is one morning in the second person; that sentence makes the morning the first
of many, and it is the only reason the band can carry a Trans Afrique button
without the button arriving from nowhere. It is set in the display face and in
caps so it reads as a second headline, and well under the `h2` so it answers it
rather than competes with it.

Both new lines are ivory, including the route's arrow. Gold measured 3.15:1 over
these pixels, and an arrow made of type is type.

`max-width: 44ch` on the paragraph and `560px` on the block are what keep the
right-hand side of the photograph empty. The empty half is the composition.

### Ivory, not gold

Muted gold is the metadata voice everywhere else on this site and was the obvious
choice for the stamp. Measured against the pixels it actually sits on it reaches
**3.15:1 where 4.5 is required** — the wash that carries a 52px headline at 5:1
is nowhere near enough for 10px of gold. The voice is kept by size and
letterspacing instead of by hue.

### Video instead of a still

A clip in a band autoplays muted and loops — the one arrangement a browser will
start without being asked — and carries the still it replaced as its `poster`, so
the frame is filled from first paint and stays filled if the file never arrives:

```css
@media (prefers-reduced-motion: reduce) {
  .wa-seam-pic video { display: none; }
  .wa-seam-pic { background: var(--c-primary); }
  .wa-seam-pic::after { content: ""; position: absolute; inset: 0;
    background: url(/images/uploads/…-1600w.jpg) center / cover; }
}
```

---

## 5. How it is verified

The effect has no JavaScript, which is the point and also the problem: **there is
nothing to throw when it breaks.** `tools/browser-checks.js` pass eleven asserts
the mechanism rather than the appearance, at five widths (1920, 1440, 1280, 950,
390) across every band on the page:

1. **None of the six containing-block properties** is set anywhere on the chain
   from `.wa-seam-pic` up to `<html>`.
2. **The picture's bounding rect is byte-identical** at all thirteen scroll
   positions. If it moved, `fixed` was demoted.
3. **The copy clears the fixed masthead** when the band is at rest.
4. **Every line clears WCAG AA** against the pixels actually behind it.

Assertion 4 is the one that cannot be reasoned about, and it is the reason this
section is measured rather than eyeballed. The tint is fixed to the viewport
while the copy travels the whole height of it, so the ground under any given line
**changes continuously as the reader scrolls**. The number that matters is the
worst one across the travel, not the one at rest.

The method: park the copy at thirteen offsets spanning the viewport; at each one
hide the copy, screenshot, sample the darkest and lightest pixel under each
line's client rects off the canvas, un-hide, and take the worse of the two ratios
against the text colour. Sample below the masthead only — it is fixed and opaque
and paints its own background, which reads as 1.00:1 on any line passing behind
it.

Measured that way the first build put the headline at **1.00:1** and 16px body at
**1.81:1**, both of which looked perfectly fine in a screenshot taken at the
position I happened to choose. Current worst: 4.37:1 for the headline against a
3.0 bar, 5.79:1 for 16px body against 4.5.

Two practical notes for anybody writing this harness: force `loading="lazy"`
images to eager and wait for `scrollHeight` to stop changing before computing a
scroll target, or the target lands on a different section by the time the scroll
happens and you sample the ivory of whatever you actually hit — which looks
exactly like a contrast failure. And index every lookup: when a second band was
added, `querySelector` meant it was never measured, and an untested band is an
unheld one.

---

## 6. Minimal reproduction

Self-contained. Paste into an empty file and open it.

```html
<!DOCTYPE html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --c-bg:         #F6F1E7;   /* warm ivory — the type */
    --c-primary:    #10251F;   /* deep forest — the wash */
    --c-accent-lit: #CB6F4B;   /* the rule and the underline */
    --display: "Archivo Narrow", "Arial Narrow", sans-serif;
    --mono:    "IBM Plex Mono", Menlo, monospace;
  }
  body { margin: 0; font-family: Georgia, serif; }
  .before, .after { min-height: 100vh; background: var(--c-bg); }

  /* --- the two load-bearing rules ------------------------------------- */
  .band     { position: relative; clip-path: inset(0); min-height: 130svh;
              display: flex; align-items: center; }
  .band-pic { position: fixed; inset: 0; z-index: 0; }
  /* Nothing above may carry transform / filter / backdrop-filter /
     perspective / will-change / contain. */

  .band-pic img  { width: 100%; height: 100%; object-fit: cover; display: block; }
  .band-tint     { position: absolute; inset: 0; background:
                    linear-gradient(100deg,
                      color-mix(in srgb, var(--c-primary) 76%, transparent)   0%,
                      color-mix(in srgb, var(--c-primary) 72%, transparent)  34%,
                      color-mix(in srgb, var(--c-primary) 54%, transparent)  50%,
                      color-mix(in srgb, var(--c-primary) 18%, transparent)  72%,
                      color-mix(in srgb, var(--c-primary)  3%, transparent) 100%); }

  .band-copy  { position: relative; z-index: 1; width: 100%; max-width: 1240px;
                margin: 0 auto; padding: 0 44px; }
  .band-inner { max-width: 560px; }
  .band-stamp { font-family: var(--mono); font-size: 10px; letter-spacing: .22em;
                text-transform: uppercase; color: var(--c-bg); margin: 0; }
  .band-route { font-family: var(--mono); font-size: 10px; letter-spacing: .3em;
                text-transform: uppercase; color: var(--c-bg); margin: 10px 0 0; }
  .band-route i { font-style: normal; margin: 0 .35em; }
  .band-kick  { font-family: var(--display); font-weight: 700; text-transform: uppercase;
                letter-spacing: .02em; line-height: 1.15;
                font-size: clamp(16px, 1.6vw, 21px); color: var(--c-bg); margin: 24px 0 0; }
  .band h2    { font-family: var(--display); font-weight: 700; text-transform: uppercase;
                letter-spacing: -.01em; line-height: 1.04;
                font-size: clamp(29px, 3.5vw, 52px); margin: 16px 0 0; color: var(--c-bg); }
  .band-hr    { display: block; width: 64px; height: 2px; margin: 26px 0;
                background: var(--c-accent-lit); }
  .band-say   { font-size: 17px; line-height: 1.6; color: var(--c-bg);
                max-width: 44ch; margin: 0; }
  .band-go    { display: inline-block; margin-top: 26px; font-family: var(--mono);
                font-size: 10px; letter-spacing: .2em; text-transform: uppercase;
                color: var(--c-bg); text-decoration: none;
                border-bottom: 2px solid var(--c-accent-lit); padding-bottom: 6px; }

  @media (max-width: 950px) {
    .band       { min-height: 104svh; }
    .band-copy  { padding: 0 28px; }
    .band-inner { max-width: none; }
    /* Flat, not graded — the copy crosses every horizontal band on the way
       through, so a vertical gradient only relocates the failure. */
    .band-tint  { background: color-mix(in srgb, var(--c-primary) 66%, transparent); }
    .band h2    { font-size: clamp(26px, 5vw, 38px); }
    .band-say   { font-size: 16px; }
  }
</style>

<div class="before"></div>

<section class="band">
  <div class="band-pic">
    <img src="YOUR-PHOTOGRAPH-1600w.jpg" width="1600" height="1067"
         alt="Describe what is in the frame, not what it is for"
         loading="lazy" decoding="async">
    <span class="band-tint" aria-hidden="true"></span>
  </div>
  <div class="band-copy">
    <div class="band-inner">
      <p class="band-stamp">Trans Afrique &middot; before six, engine already running</p>
      <p class="band-route">Kenya <i aria-hidden="true">&rarr;</i> Tanzania</p>
      <h2>Imagine tomorrow morning.</h2>
      <span class="band-hr" aria-hidden="true"></span>
      <p class="band-say">You wake before it is light. No alarm, no traffic, no
        office &mdash; just voices outside and somebody loading the vehicle.</p>
      <p class="band-kick">One continent is waiting.</p>
      <a class="band-go" href="/trans-afrique">Enter Trans Afrique &rarr;</a>
    </div>
  </div>
</section>

<div class="after"></div>
```

Choose a photograph with a **dark side and an empty side**, and put the copy on
the dark one. If the frame has no empty side, this section will not work with it,
and the fix is a different photograph rather than a heavier tint.

---

## 7. Checklist for a new band

- [ ] The photograph has a quiet region wide enough for 44ch of type.
- [ ] The copy names only things visible in the frame.
- [ ] Nothing on the ancestor chain carries any of the six killer properties.
- [ ] The tint is inside the fixed picture, not on the band.
- [ ] The tint is graded for **this** photograph, measured — not inherited.
- [ ] Below 950px the tint is flat, set by the brightest pixel the copy crosses.
- [ ] `svh`, never `vh`.
- [ ] Contrast measured at ~13 scroll positions per width, worst value recorded.
- [ ] Every line of copy is named in the gate's `BAND_TEXT`, or it ships unmeasured.
- [ ] The `alt` describes the frame; the stamp gives the product and the hour.
- [ ] The band's CTA verb is not repeated by any other link to the same page.
- [ ] `prefers-reduced-motion` has a still to fall back to if a clip is used.

---

## 8. Where the code lives

| Part | File |
|---|---|
| Section markup | `index.html` — search `wa-seam--dawn` |
| Section CSS | `index.html`, `/* ---- the window band ---- */` |
| Design tokens | `styles/afrinkong.css` |
| The gate | `tools/browser-checks.js`, pass eleven |

Run the gate with `node tools/browser-checks.js`. Only one instance at a time —
concurrent runs compete for the same port.

**Read the output, not the exit code.** The runner prints `PASS`/`FAIL` per
check and exits `0` either way, and node buffers its stdout when it is not
attached to a terminal, so a run that is killed early leaves a zero-byte log
that is indistinguishable from a clean one. Count the lines:

```sh
node tools/browser-checks.js > gate.out 2>&1
grep -c '^PASS' gate.out; grep '^FAIL' gate.out
```
