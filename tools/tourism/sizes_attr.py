"""Tell the browser how wide the photograph will be, from a measurement.

    python3 tools/tourism/build.py sizeattr             what it would change
    python3 tools/tourism/build.py sizeattr --fetch     write it

WHAT WAS WRONG

Every photograph on this site that has more than one width offers all of them
through `srcset`, and none of them said how wide the picture would be laid out.
With no `sizes` the browser assumes the image fills the viewport, which is the
safe assumption and, on a desktop, an expensive one: the homepage at 1440 by
two device pixels downloaded 8.4 MB of photographs, because a card painted 287
pixels wide was assumed to want 2,880 and took the 1600.

Measured rather than inferred — see tools/tourism/measure_sizes.js, which lays
each page out at twelve widths in a real browser and writes down what it got.
srcset.py's note about `sizes` is right that this cannot be inferred from a
file name. It can be read off a layout.

ROUNDING UP, ALWAYS

Too large a hint costs bytes. Too small a hint ships a photograph the browser
cannot un-blur to a site whose entire argument is its photographs. So every
band takes the widest measurement anywhere inside it, and a further 8% is added
on top — enough to absorb a scrollbar appearing, a longer country name pushing
a grid around, or a font that changes a card's height and so its width. The
tags are only rewritten where the change is worth making.

WHY THE BUILT HTML AND NOT THE GENERATORS

Same reason srcset.py works this way: these tags come out of six families of
generator plus two hand-written pages, and one pass over the output is one
place to be right instead of eight places to remember. It runs after srcset in
`all`, and it is idempotent.
"""

import html as html_mod
import json
import os
import re

from .model import ROOT

DATA = os.path.join(ROOT, "data", "sizes.json")
IMG = re.compile(r"<img\b[^>]*>", re.I)
HAS_SIZES = re.compile(r'\ssizes="[^"]*"', re.I)
# WHAT THIS PASS WROTE, AND SO WHAT IT IS ALLOWED TO TAKE BACK.
#
# A hint is only true of the photograph it was measured against. Three resolve
# runs replaced hundreds of photographs, the src guard correctly refused to
# vouch for the new ones — and left the old hint sitting on the tag, because
# this pass could write and overwrite and had no way to withdraw. Two images on
# /tourism/kenya were promised 368 pixels and painted at 563, which is a
# photograph fetched too small and shown soft. The width check caught it, which
# is the whole reason that check exists.
#
# The marker is what makes withdrawal safe. Generators write their own `sizes`
# on some tags and those are none of this pass's business; only a tag carrying
# this attribute was written here, and only that one is stripped when the
# measurement no longer covers it.
MINE = ' data-sizes="fit"'
HAS_MINE = re.compile(r'\sdata-sizes="fit"', re.I)
HAS_SRCSET = re.compile(r'\ssrcset="[^"]*"', re.I)

# Room for the layout to move without the hint becoming a lie. A scrollbar is
# 15px on a 320px phone, which is 5%; a grid that reflows because a name got
# longer can be more. Eight per cent costs almost nothing — the file the
# browser picks changes only if the measurement was within 8% of a boundary —
# and it is the difference between a hint that is tight and one that is wrong.
HEADROOM = 1.08

# THE BANDS ARE A DECISION AND THEY LIVE HERE, NOT IN THE MEASUREMENT.
#
# data/sizes.json records the painted width at every viewport it visited and
# takes no view about where the breakpoints are. That separation is what let
# the first banding be corrected without opening a browser again: 900 and 1024
# had been put in the same band, and this site's grid goes from one column to
# two between them, so the band held ratios of 1.00 and 0.66 and could only
# describe them as a number of pixels that was right at neither end.
#
# Each band is (upper edge, the measured viewports inside it). Every band needs
# at least two viewports or the ratio test below has nothing to compare.
BANDS = [
    (430, [320, 360, 390, 430]),
    (900, [560, 700, 768, 900]),
    (1440, [1024, 1100, 1200, 1280, 1440]),
    (None, [1920, 2560]),
]


def load():
    try:
        with open(DATA, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def band_hint(samples, edge):
    """-> the `sizes` clause for one band, from the measurements inside it.

    `samples` is [(viewport, painted width), ...] for the widths measured in
    this band. Two kinds of image live here and they want opposite hints:

      a picture that fills its column, whose painted width is a fixed FRACTION
      of the viewport — 100vw for a full-bleed photograph, 46vw for one of two
      side by side. Its ratio to the viewport barely moves across the band.

      a picture in a box of a fixed size — a 300px thumbnail that is 300px at
      360 and 300px at 430. Its ratio halves across the band while the number
      stays put.

    Telling the first kind a number is what broke the first version of this
    pass: an image measured at 430 on a 430-pixel screen was described as
    "430px", a 390-pixel phone believed it, and at two device pixels asked for
    860 — so it took the 1200 where it had been taking the 800. The homepage
    went from 3.76 MB to 7.33 MB on that phone, in the commit that was supposed
    to make it smaller. Measured, caught, and the reason this function exists.

    So: constant ratio -> vw. Constant width -> px. Neither -> the largest px
    in the band, which is the safe direction.
    """
    pts = [(v, w) for v, w in samples if v and w]
    if not pts:
        return None, 0
    ratios = [w / float(v) for v, w in pts]
    widest = max(w for _v, w in pts)
    spread = max(ratios) - min(ratios)
    if len(pts) > 1 and spread < 0.06:
        # Two points up, so a layout that moves a little does not clip the
        # photograph, and never past the whole viewport.
        vw = min(100, int(round(max(ratios) * 100)) + 2)
        return "%dvw" % vw, widest
    px = int(round(widest * HEADROOM))
    if edge:
        px = min(px, max(edge, widest))
    return "%dpx" % px, widest


def value(at, edges=None, widths=None):
    """-> the `sizes` string for this image, or None if it says nothing useful.

    A band with no measurement in it inherits the clause from the first band
    above that has one: an image absent at 360 and present at 700 is one the
    small band never got to ask about, and guessing small there is the one
    guess that cannot be undone.
    """
    clauses = []
    for edge, sample_widths in BANDS:
        hint, widest = band_hint(
            [(v, at.get(str(v)) or at.get(v) or 0) for v in sample_widths], edge)
        clauses.append([hint, widest])
    nxt = None
    for i in range(len(clauses) - 1, -1, -1):
        if clauses[i][0]:
            nxt = clauses[i][0]
        else:
            clauses[i][0] = nxt
    if not any(c[0] for c in clauses):
        return None
    # Adjacent bands that came out the same are one clause. Four bands that all
    # say 100vw is four ways of saying nothing, and `(max-width: 900px) 100vw,
    # 68vw` is the whole of what this image needs said about it.
    parts, last = [], None
    for i, (edge, _w) in enumerate(BANDS):
        hint = clauses[i][0]
        if hint == last and parts:
            parts.pop()
        last = hint
        parts.append(hint if edge is None else "(max-width: %dpx) %s" % (edge, hint))
    return ", ".join(parts)


def worth_it(v):
    """-> whether this hint changes any decision the browser would make.

    `100vw` in every band is exactly what a browser assumes when there is no
    `sizes` at all, so writing it out is bytes on the wire and nothing else.
    """
    if not v:
        return False
    return not all(part.strip().endswith("100vw") for part in v.split(","))


def withdraw(tag):
    """-> the tag with this pass's own hint removed, if it has one.

    Called wherever the measurement cannot vouch for the tag: no record at this
    position, or a src that does not match the one measured there. Leaving the
    old hint is the failure mode this exists to prevent — it is a promise about
    a photograph that is no longer in the slot.
    """
    if not HAS_MINE.search(tag):
        return tag
    return HAS_SIZES.sub("", HAS_MINE.sub("", tag, count=1), count=1)


def run(write=False, log=print):
    doc = load()
    if not doc:
        log("no data/sizes.json — run: node tools/tourism/measure_sizes.js "
            "> data/sizes.json")
        return 2
    pages = doc["pages"]

    touched = tags = skipped = 0
    for rel in sorted(pages):
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            log("  %-46s gone" % rel)
            continue
        per = pages[rel]
        n = [0]
        idx = [-1]

        def swap(m):
            tag = m.group(0)
            # THE COUNTER ADVANCES ON EVERY IMAGE, NOT ONLY THE ONES WITH A
            # SRCSET. The measurement is keyed by position in document.images,
            # which counts them all, so skipping the increment for a tag with
            # no srcset would slide every key after it by one and hand a card's
            # width to a portrait.
            idx[0] += 1
            if not HAS_SRCSET.search(tag):
                return tag
            rec = per.get(str(idx[0]))
            if not rec:
                return withdraw(tag)
            # And the src is checked, not trusted. Positions line up only while
            # the page has the same images in the same order as when it was
            # measured; a rebuild that adds one would otherwise apply every
            # width to the wrong photograph, silently and invisibly.
            got = re.search(r'src="([^"]*)"', tag)
            # Unescaped before comparing. The CDN URLs carry a query string —
            # ?auto=compress&cs=tinysrgb&w=1200 — which is `&amp;` in the file
            # and `&` from getAttribute(), so a straight comparison rejected
            # every photograph the resolver had placed and matched only the
            # uploads. Fifty-one images on /tourism became one.
            if not got or html_mod.unescape(got.group(1)) != rec.get("src"):
                return withdraw(tag)
            v = value(rec.get("at") or {})
            if not worth_it(v):
                return withdraw(tag)
            n[0] += 1
            out = tag
            if HAS_SIZES.search(out):
                out = HAS_SIZES.sub(' sizes="%s"' % v, out, count=1)
            else:
                out = out[:-1].rstrip() + ' sizes="%s">' % v
            if not HAS_MINE.search(out):
                out = out[:-1].rstrip() + MINE + ">"
            return out

        out = IMG.sub(swap, src)
        if n[0]:
            tags += n[0]
            touched += 1
            if write:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(out)
            log("  %-46s %d tag(s)" % (rel, n[0]))
        else:
            skipped += 1

    log("%s %d tag(s) across %d page(s); %d page(s) had nothing worth saying"
        % ("told the browser how wide" if write else "WOULD tell",
           tags, touched, skipped))
    if not write:
        log("dry run. Add --fetch to write it.")
    return 0
