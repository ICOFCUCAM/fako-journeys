"""The Image Acquisition Plan: 1,426 photographs as a commissioning brief.

    python3 tools/tourism/build.py acquire            # the summary
    python3 tools/tourism/build.py acquire --fetch    # write the spreadsheet

"FIND BETTER PHOTOS" IS NOT AN INSTRUCTION ANYBODY CAN ACT ON.

`assets` decides which photographs are wrong. That is a verdict, and a verdict
is not a brief. Somebody commissioning a shoot or buying a licence needs to
know, for one photograph: which country, which destination, which page, what
the picture has to show, what shape it has to be, how much it matters, and
what to call the file when it comes back. This turns the classification into
exactly that, one row per photograph, and writes it as CSV so it opens in a
spreadsheet and can be handed to a photographer, an agency or a picture editor
without any of them reading a line of this repository.

---------------------------------------------------------------------------
NOTHING HERE IS INVENTED, AND THAT IS THE POINT

Every column is read off something the site already asserts:

  required subject     altIntended — what the page meant to show, written when
                       the slot was specified rather than when the photograph
                       was found. This is the brief, and it already exists for
                       all 1,426. The current alt is what the provider called
                       the picture, which for 290 of them is how we know it is
                       wrong.
  required composition the aspect-ratio the tag is rendered at, and the widest
                       width it is displayed at, taken from the markup. A
                       photograph used at 16/9 on one page and 3/2 on another
                       needs to survive both crops, so both are listed.
  priority             where the photograph actually sits. fetchpriority="high"
                       is the site's own statement that a picture is above the
                       fold; loading="lazy" is its statement that it is not.
                       1,426 tags carry the first, which is one hero placement
                       per photograph.
  destination          the place page that uses it, when one does.

The one judgement this file makes is the class, and it is a lookup, not an
opinion. See CLASSES.

---------------------------------------------------------------------------
WHY SIGNATURE IS SEPARATE FROM REPLACE

A wrong photograph on a page nobody reaches and a wrong photograph at the top
of the Kenya landing page are the same verdict and completely different money.
Splitting them is the difference between a budget somebody can approve and a
number that gets refused. Signature is the intersection of "wrong" and "the
first thing a visitor sees on a page that sells" — those are the frames worth
commissioning. The rest of the wrong ones are a licensing exercise.
"""

import csv
import os
import re

from . import library
from .model import ROOT

INVENTORY = os.path.join(ROOT, "data", "asset-inventory.json")
PLAN = os.path.join(ROOT, "data", "image-acquisition.csv")

IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
RATIO_RE = re.compile(r"aspect-ratio:\s*([0-9./ ]+)")
WIDTH_RE = re.compile(r'\swidth="(\d+)"')

# Pages that sell. A wrong photograph at the top of one of these costs money;
# the same photograph on a reference page costs credibility more slowly.
COMMERCIAL = ("/index.html", "/trans-afrique.html", "/journey.html",
              "/journey-fund.html", "/how-it-works.html", "/enquire.html",
              "/atlas.html", "/wonders.html", "/about.html", "/contact.html")


def tier(page):
    """How much a page matters, as a letter. THE HERO FLAG IS NOT A RANKING.

    Every page on this site marks its first photograph fetchpriority="high",
    so 1,426 tags carry it — one per photograph. Read on its own it says
    everything is a hero, which ranked 1,413 of 1,426 as top priority and made
    the column worthless. What separates them is not whether a photograph is
    the first thing on its page, but which page that is:

      A  the ten pages that sell — the homepage, Trans Afrique, the Builder,
         the Fund, how it works, the atlas, enquire, about, contact
      B  the 110 country landings, /kenya.html and /tourism/kenya.html
      C  the 54 country portraits
      D  the ~1,400 place pages, twenty-six per country

    Roughly 1,400 of the photographs are the hero of a D. That is the long
    tail, and it is the difference between a licensing exercise and a shoot.
    """
    if page in COMMERCIAL:
        return "A"
    if re.match(r"/tourism/[a-z-]+\.html$", page):
        return "B"
    if re.match(r"/[a-z-]+\.html$", page):
        return "B"
    if re.match(r"/portrait/[a-z-]+\.html$", page):
        return "C"
    return "D"

CLASSES = {
    # verdict + placement          -> class, what to do about it
    "SIGNATURE": ("commission an original photograph from an African "
                  "photographer"),
    "REPLACE": "licence a photograph that actually shows the subject",
    "RECROP": "cut a second crop from the file we already hold",
    "REVIEW": "a person decides — provenance is unclear",
    "KEEP": "migrate as it is",
    "REMOVE": "take the photograph off the page",
}


def _pages_index(log=print):
    """Every provider URL on the site, with how each page renders it.

    One walk over the built HTML rather than one per photograph. Returns
    {url without query: [{page, ratio, width, hero}, ...]}.
    """
    out = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            page = "/" + os.path.relpath(path, ROOT).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            if "images.pexels.com" not in html and \
                    "images.unsplash.com" not in html:
                continue
            for m in IMG_RE.finditer(html):
                tag = m.group(0)
                found = re.search(
                    r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+", tag)
                if not found:
                    continue
                url = found.group(0).split("?")[0]
                ratio = RATIO_RE.search(tag)
                width = WIDTH_RE.search(tag)
                out.setdefault(url, []).append({
                    "page": page,
                    "ratio": (ratio.group(1).strip().replace(" ", "")
                              if ratio else ""),
                    "width": int(width.group(1)) if width else 0,
                    # The site's own statement about the fold. Not a guess.
                    "hero": 'fetchpriority="high"' in tag,
                })
    return out


def _destination(pages):
    """The place a photograph illustrates, when a place page uses it.

    /places/<country>/<place>.html is the only path that names a destination;
    everything else is a country or a category view, and saying so is more
    use to a photographer than repeating the country twice.
    """
    for p in pages:
        m = re.match(r"/places/[^/]+/([^/]+)\.html$", p)
        if m:
            return m.group(1).replace("-", " ")
    return ""


def _priority(uses):
    """P1 to P4, from where the photograph sits rather than from taste.

    Ranked on the best page it is the hero of, then on the best page it
    appears on at all. A photograph nobody sees first, on one deep page, is
    the bottom of the list however wrong it is.
    """
    if not uses:
        return "P4"
    hero_tiers = sorted(tier(u["page"]) for u in uses if u["hero"])
    any_tiers = sorted(tier(u["page"]) for u in uses)
    best_hero = hero_tiers[0] if hero_tiers else "Z"
    best_any = any_tiers[0] if any_tiers else "Z"
    if best_hero in ("A", "B"):
        return "P1"
    if best_hero == "C":
        return "P2"
    # The hero of a place page, but the country's own landing page shows it
    # too — so it is seen by somebody browsing the country, not only by
    # somebody who has already gone three levels deep.
    if best_any in ("A", "B"):
        return "P3"
    return "P4"


def classify(rec, uses, recrop):
    """One photograph's class. A lookup over the verdict and the placement."""
    verdict = rec.get("verdict")
    if verdict == "REMOVE":
        return "REMOVE"
    if verdict == "PROVENANCE REVIEW":
        return "REVIEW"
    if verdict == "REPLACE":
        # Wrong AND first thing seen on a page that sells. These are the
        # frames worth paying a photographer to go and take.
        if _priority(uses) == "P1":
            return "SIGNATURE"
        return "REPLACE"
    if rec.get("imageUrl", "").split("?")[0] in recrop:
        return "RECROP"
    return "KEEP"


def rows(log=print):
    """Every photograph as one acquisition row."""
    inv = library._read(INVENTORY, {"assets": []})
    recs = inv["assets"]
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    index = _pages_index(log=log)
    recrop = library.artdirected()

    out = []
    for rec in recs:
        url = (rec.get("imageUrl") or "").split("?")[0]
        uses = index.get(url, [])
        cls = classify(rec, uses, recrop)

        # Every shape it has to work at. A photograph cropped 16/9 on the
        # landing page and 3/2 in a card has to survive both, and a
        # photographer who is told only one of them delivers a frame that
        # loses a head in the other.
        ratios = []
        for u in uses:
            if u["ratio"] and u["ratio"] not in ratios:
                ratios.append(u["ratio"])
        widest = max([u["width"] for u in uses] or [0])

        country = library._slug(rec.get("country") or "world")
        category = library._slug(rec.get("category") or "general")
        stem = library._slug(rec.get("caption") or rec.get("altIntended")
                             or rec.get("photoId"))
        out.append({
            "class": cls,
            "priority": _priority(uses),
            "country": country,
            "destination": _destination([u["page"] for u in uses]),
            "category": category,
            "required subject": rec.get("altIntended") or rec.get("alt") or "",
            "required composition": " and ".join(ratios) or "unconstrained",
            "widest display px": widest,
            "action": CLASSES.get(cls, ""),
            "replacement filename": "%s/%s/%s.avif" % (country, category, stem),
            "pages": len(uses) or rec.get("pageCount") or 0,
            "hero on": next((u["page"] for u in uses if u["hero"]), ""),
            "first page": (uses[0]["page"] if uses
                           else (rec.get("pages") or [""])[0]),
            # What is being replaced, so the decision is auditable and the
            # licence of the outgoing photograph is never lost.
            "why": rec.get("why") or "",
            "current provider": rec.get("provider") or "",
            "current photographer": rec.get("photographer") or "",
            "current source": rec.get("sourceUrl") or "",
        })
    out.sort(key=lambda r: (r["priority"], r["class"], r["country"],
                            r["category"]))
    return out


FIELDS = ["class", "priority", "country", "destination", "category",
          "required subject", "required composition", "widest display px",
          "action", "replacement filename", "pages", "hero on", "first page",
          "why", "current provider", "current photographer", "current source"]


def run(write=False, log=print):
    data = rows(log=log)
    by_class, by_priority, spend = {}, {}, {}
    for r in data:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1
        by_priority[r["priority"]] = by_priority.get(r["priority"], 0) + 1
        if r["class"] in ("SIGNATURE", "REPLACE"):
            spend[r["country"]] = spend.get(r["country"], 0) + 1

    log("")
    log("  THE IMAGE ACQUISITION PLAN")
    log("  ---------------------------------------------------------------")
    for cls in ("SIGNATURE", "REPLACE", "RECROP", "REVIEW", "KEEP", "REMOVE"):
        if by_class.get(cls):
            log("  %-10s %6d   %s" % (cls, by_class[cls], CLASSES.get(cls, "")))
    log("")
    log("  by placement, which is what the money follows:")
    for p, label in (("P1", "opens a selling page or a country landing"),
                     ("P2", "opens a country portrait"),
                     ("P3", "opens a place page, and the country shows it too"),
                     ("P4", "opens a place page, seen nowhere else")):
        if by_priority.get(p):
            log("  %-4s %6d   %s" % (p, by_priority[p], label))
    log("")
    to_source = by_class.get("SIGNATURE", 0) + by_class.get("REPLACE", 0)
    log("  %d photograph(s) to source across %d countries"
        % (to_source, len(spend)))
    top = sorted(spend.items(), key=lambda kv: -kv[1])[:5]
    if top:
        log("  heaviest: %s" % ", ".join("%s %d" % (c, n) for c, n in top))

    if not write:
        log("")
        log("  dry run — add --fetch to write data/image-acquisition.csv")
        return 0

    with open(PLAN, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in data:
            w.writerow(r)
    log("")
    log("  wrote %s — %d row(s)"
        % (os.path.relpath(PLAN, ROOT), len(data)))
    return 0
