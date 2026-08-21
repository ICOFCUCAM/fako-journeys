"""Every image slot on the site, and what belongs in it.

A category is not a placement. "Waterfalls" is a subject; the third picture down
on services.html is a *place*, with a shape the stylesheet already decided, a
sentence already written about what it shows, and a crop that will cut anything
composed too close to the edge. An image generated for the category and an image
generated for the placement are not the same picture.

So the unit of work here is the slot, and the manifest is built by reading the
pages rather than by being maintained alongside them — the pages are the truth,
and a hand-kept list of slots would be wrong within a week.

For each <img> on the five hand-written pages this records:

    id           stable across runs: the illustration it was built around
    page         which file, and the slot's position in it
    wrapper      the CSS class that decides the delivered shape
    aspect       the ratio that class imposes, from adopt.SLOT_SPECS
    instruction  what the picture must show — the slot's own alt text, which
                 was written for the drawing before any photograph existed and
                 is therefore a description of intent, not of a search result
    category     the tourism category it corresponds to, where there is one,
                 which is what supplies the photographic direction
    locked       hand-picked artwork; generation must not target it

`build.py placements` prints it. `build.py prompts` turns it into instructions.
`build.py generate` makes the pictures. `build.py place` puts a chosen one in.
"""

import os
import re

from . import adopt
from .model import ROOT

PAGES = adopt.PAGES
IMG_RE = adopt.IMG_RE
ATTR_RE = adopt.ATTR_RE


def wrapper_for(html, position):
    """The nearest preceding wrapper class — the same lookup adopt uses to pick
    a delivery shape, returned by name so the manifest can show it."""
    # FOUR HUNDRED CHARACTERS WAS A GUESS, AND `modern` OUTGREW IT.
    #
    # This looked back a fixed 400 bytes. Then the `modern` late pass began
    # wrapping every photograph in <picture><source srcset="..."> — four URLs
    # and their widths per source, several hundred characters — which pushed
    # the wrapper class out of the window. Measured on cameroon.html, the three
    # real fj-slip-pic slots sit 402, 506 and 634 characters before their
    # <img>. All three missed by a margin of two.
    #
    # Nothing failed loudly. `spec` fell through to DEFAULT_SPEC, so 37 of 45
    # slots reported a 3:2 shape that appears in no spec, the 5:4 shape
    # vanished from the manifest entirely, and three checks that describe the
    # generation pipeline went red for a reason none of them names.
    #
    # So the bound is derived instead of guessed: a slot's wrapper is the last
    # wrapper class mentioned since the PREVIOUS image, because that is exactly
    # the region that can belong to this one. The 4,000-character ceiling is
    # only a leash for the first image on a page, where there is no previous
    # <img> to stop at and a class named in a <style> block could otherwise
    # match from far above.
    prev = html.rfind("<img", 0, position)
    floor = max(0, position - 4000, prev + 1 if prev != -1 else 0)
    before = html[floor:position]
    best, best_at = None, -1
    for cls, _spec in adopt.SLOT_SPECS:
        at = before.rfind(cls)
        if at > best_at:
            best, best_at = cls, at
    return best if best_at >= 0 else None


def slot_id(illustration):
    """The illustration path is the one thing about a slot that does not change
    when a photograph is adopted into it, so it is the identity."""
    name = os.path.basename(illustration or "").rsplit(".", 1)[0]
    return name or "unknown"


def scan_page(page, category_by_local):
    path = os.path.join(ROOT, page)
    if not os.path.exists(path):
        return []
    html = open(path).read()
    out = []
    for order, m in enumerate(IMG_RE.finditer(html), start=1):
        tag = m.group(0)
        attrs = dict(ATTR_RE.findall(tag))
        illustration = attrs.get("data-illustration") or attrs.get("src") or ""
        # After `adopt` the live alt describes the photograph that won. The
        # drawing's alt is what the slot was *for*, which is the instruction.
        instruction = attrs.get("data-illustration-alt") or attrs.get("alt") or ""
        cls = wrapper_for(html, m.start())
        spec = dict(adopt.SLOT_SPECS).get(cls, adopt.DEFAULT_SPEC)
        out.append({
            "id": slot_id(illustration),
            "page": page,
            "order": order,
            "wrapper": cls,
            "aspect": list(spec["aspect"]),
            "width": spec["width"],
            # What the crop must not throw away, carried from the role so the
            # review sheet and the generation brief say the same thing.
            "focus": spec.get("focus", ""),
            "illustration": illustration,
            "instruction": instruction.strip(),
            "category": category_by_local.get(illustration),
            "locked": attrs.get("data-locked") == "true",
            "current": attrs.get("src") or "",
            "provider": attrs.get("data-provider") or "",
        })
    return out


def category_map(country):
    """illustration path -> category id, from the country dataset's `local`."""
    out = {}
    for entry in country.entries:
        if entry.local:
            out.setdefault(entry.local, entry.category)
    return out


def scan(country):
    """Every slot on the five hand-written pages, in page then document order."""
    by_local = category_map(country)
    out = []
    for page in PAGES:
        out.extend(scan_page(page, by_local))
    return out


def targetable(placements):
    """The ones generation is allowed to aim at.

    Locked slots are excluded on purpose: they hold artwork somebody chose, and
    the engine that replaces images must not be the engine that quietly
    overwrites the one decision a person made by hand.
    """
    return [p for p in placements if not p["locked"] and p["instruction"]]


def by_id(placements):
    out = {}
    for p in placements:
        out.setdefault(p["id"], []).append(p)
    return out


def duplicates(placements):
    """Slots that reuse the same illustration on more than one page — they share
    an id, so a picture generated for one lands in both."""
    return {k: v for k, v in by_id(placements).items() if len(v) > 1}


def summarise(placements):
    pages = {}
    for p in placements:
        pages.setdefault(p["page"], []).append(p)
    return {
        "total": len(placements),
        "locked": len([p for p in placements if p["locked"]]),
        "targetable": len(targetable(placements)),
        "uncategorised": len([p for p in placements if not p["category"]]),
        "pages": {k: len(v) for k, v in pages.items()},
        "shapes": sorted({"%d:%d" % tuple(p["aspect"]) for p in placements}),
    }
