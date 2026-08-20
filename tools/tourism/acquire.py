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
import html as html_mod
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
                # UNBOUNDED: the tag asks the provider for the original at
                # whatever size the photographer uploaded, on every device.
                # 18.6% of the site's references do this, and they are where
                # migration is worth megabytes rather than kilobytes — the
                # Algeria coast page went 3.76 MB to 0.07 MB on exactly this.
                # Entities matter: the attribute holds &amp;w=800, so a search
                # for &w= finds nothing and reports every reference unbounded.
                whole = html_mod.unescape(found.group(0))
                out.setdefault(url, []).append({
                    "unbounded": not re.search(r"[?&]w=\d+", whole),
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

    # How wrong a country's photography is, as a share of its own set. The
    # denominator matters: every country has about twenty-seven slots, so a
    # raw count of bad photographs is nearly the same everywhere and the share
    # is what separates Botswana at 81% from Kenya at 33%.
    tally = {}
    for r in recs:
        c = r.get("country") or "?"
        t = tally.setdefault(c, [0, 0])
        t[0] += 1
        if r.get("verdict") == "REPLACE":
            t[1] += 1
    deficiency = {c: (bad / tot if tot else 0.0) for c, (tot, bad) in tally.items()}

    # An asset already in the register keeps its identity: a re-crop is the
    # same photograph, and a commissioned replacement TAKES OVER the key of the
    # one it replaces so no page needs editing. Found by sourceKey, which is
    # the provider's own id and cannot change.
    reg = library.register()
    known = {a.get("sourceKey"): a["id"] for a in reg["assets"].values()
             if a.get("sourceKey")}

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
        t = commerce_tier(country)
        prio = _priority(uses)
        route, cost = route_and_cost(cls, t, prio)
        skey = library.source_key("provider", rec.get("provider"),
                                  rec.get("photoId"))
        aid = known.get(skey)
        out.append({
            "class": cls,
            # The provider's own id, which is how a reserved identity is found
            # again on a later run. Carried in the CSV too, so a delivery can
            # be matched back to the photograph it replaces.
            "sourceKey": skey,
            "commercial tier": t,
            "tier why": TIERS[t],
            "country deficiency": "%.0f%%" % (deficiency.get(country, 0) * 100),
            "acquisition route": route,
            "cost band": cost,
            # Blank here for anything not yet in the register; run() reserves
            # an identity for those so the plan can name one.
            "canonical asset id": aid or "",
            # Any reference to this photograph that names no width. One is
            # enough: that page is shipping the original to a phone.
            "unbounded": "yes" if any(u.get("unbounded") for u in uses) else "no",
            "current reference": rec.get("imageUrl") or "",
            "priority": prio,
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
    # THE BUY ORDER, AFTER THE MEASUREMENT CHANGED IT.
    #
    # The first version ranked on commercial weight and where a photograph
    # sits. Then weigh.js found the thing neither of those captures: about one
    # reference in five asks the provider for the full-resolution original on
    # every device, and replacing one of those took a page from 3.76 MB to
    # 0.07 MB. The same work on an already width-limited reference was worth
    # two to five per cent. Same acquisition cost, two orders of magnitude of
    # difference in what it buys.
    #
    # So unbounded is a ranking signal now, and the order is: what costs
    # nothing, then what is worth megabytes, then what is worth the money,
    # then everything else.
    #
    #   P0  owned re-crops — no acquisition at all, files we already hold
    #   P1  unbounded AND seen first or commercially live — megabytes
    #   P2  opens a selling page or a country landing — the frames that sell
    #   P3  the rest of the sixteen countries that carry a price
    #   P4  everything else that needs replacing
    #   P5  unbounded nowhere, seen nowhere, sold nowhere — do not spend yet
    def band(r):
        """WHERE THE MEGABYTES ARE IS NOT WHERE THE MONEY IS.

        Ranking the ACQUISITION set on unbounded turned out to add nothing:
        all 36 signature frames carry a width, all 750 replacements do not, so
        the flag is a restatement of where a photograph sits. Worth knowing
        before treating it as a new axis.

        What it did find is bigger. 508 of the 527 KEEP assets are unbounded —
        photographs the audit already approved, shipping full-resolution
        originals to phones today, needing no licence, no shoot and no
        decision. They are the megabyte wins, and they cost nothing but a run
        of the pipeline that is already built and proven.

        So the bands separate migration from purchase, because they are
        different kinds of work with different budgets:

          P0-P2  nothing to buy. Re-crop or migrate what is already ours.
          P3-P6  the photography budget, in the order it should be spent.
        """
        live = r["commercial tier"] <= 3
        seen = r["priority"] in ("P1", "P2")
        cls = r["class"]
        if cls == "RECROP":
            return (0, "P0 owned re-crop, no acquisition")
        if cls == "KEEP":
            if r["unbounded"] == "yes":
                return (1, "P1 migrate — approved, unbounded, megabytes")
            return (2, "P2 migrate — approved, already width-limited")
        if cls not in ("REPLACE", "SIGNATURE"):
            return (9, "P9 no acquisition — a person decides")
        if cls == "SIGNATURE" and live:
            return (3, "P3 commission — commercially live hero")
        if cls == "REPLACE" and (live or seen):
            return (4, "P4 licence — commercially live or prominent")
        if cls == "SIGNATURE":
            return (5, "P5 commission — remaining heroes")
        return (6, "P6 licence — long tail, do not spend yet")

    def sortkey(r):
        n, label = band(r)
        r["wave"] = label
        return (n,
                r["commercial tier"],
                -float(r["country deficiency"].rstrip("%")),
                r["priority"], r["country"], r["category"])
    out.sort(key=sortkey)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


# ---------------------------------------------------------------------------
# COMMERCIAL WEIGHT, READ OFF THE SITE RATHER THAN GUESSED
#
# I said before that this repository could not rank countries commercially and
# that somebody would have to name them. That was half wrong: the site states
# its own commercial shape in three places, and none of it is opinion.
#
#   an operator      data/graph.json names an operator for three countries.
#                    Those are the ones with offices, phone numbers, a licence
#                    number and rates — the journeys somebody can actually buy
#                    today. Nothing outranks that.
#   a priced route   the Trans Afrique pages are where the money is: crossings,
#                    ways, east, south, west and continental carry every real
#                    figure on the site. Nine countries are named on three of
#                    them (the East and South arms plus continental); six more
#                    on two (the West arm). A country on a priced page is a
#                    country the site is selling.
#   everything else  the remaining thirty-eight. Real pages, no price attached.
#
# What was NOT usable, having tried it: inbound links. They run 38–53 per
# country and are driven by shared borders and the atlas, so Mali and DR Congo
# top the table. That measures geography, not demand.
OPERATOR = ("cameroon", "namibia", "uganda")
ROUTE_MAJOR = ("botswana", "kenya", "namibia", "rwanda", "south-africa",
               "tanzania", "uganda", "zambia", "zimbabwe")
ROUTE_WEST = ("cote-divoire", "gambia", "ghana", "guinea", "guinea-bissau",
              "senegal")

TIERS = {1: "operator — bookable today",
         2: "priced route — East, South and continental",
         3: "priced route — West",
         4: "no price attached"}

# What each route costs, as a band rather than a number. Real figures depend on
# who you commission and which agency you licence from, and inventing them
# would be the least useful thing in this file.
COST = {
    "re-crop":   "A — none. We hold the file; this is an hour of somebody's "
                 "attention, not a purchase.",
    "licence":   "B — one stock or agency licence at the going rate.",
    "licence+":  "C — a licence worth paying up for: this frame opens a page "
                 "that carries a price.",
    "commission": "D — a commissioned shoot. The most expensive route and the "
                  "only one that produces something nobody else has.",
}


def commerce_tier(country):
    """Commercial weight 1-4. NOT the page tier above — different question.

    `tier()` asks how prominent a page is. This asks how much money is
    attached to a country. Two separate axes, and naming them both `tier`
    shadowed the first one, which `_priority` calls on every use.
    """
    if country in OPERATOR:
        return 1
    if country in ROUTE_MAJOR:
        return 2
    if country in ROUTE_WEST:
        return 3
    return 4


def route_and_cost(cls, t, priority):
    """Which way this photograph is obtained, and roughly what that costs."""
    if cls == "RECROP":
        return "re-crop", COST["re-crop"]
    if cls == "SIGNATURE":
        return "commission", COST["commission"]
    if cls in ("REVIEW", "REMOVE"):
        return "decide", "— a person decides; no acquisition until they do."
    if cls == "KEEP":
        return "none", "— already ours."
    # REPLACE. A licence on a page that carries a price is worth more care.
    if t <= 3 or priority == "P1":
        return "licence", COST["licence+"]
    return "licence", COST["licence"]


FIELDS = ["rank", "wave", "class", "sourceKey", "commercial tier", "tier why",
          "country deficiency", "unbounded", "priority", "country", "destination",
          "category", "required subject", "required composition",
          "widest display px", "action", "acquisition route", "cost band",
          "canonical asset id", "current reference", "replacement filename",
          "pages", "hero on", "first page", "why",
          "current provider", "current photographer", "current source"]


def reserve(data, write=False, log=print):
    """Give every planned acquisition a canonical identity, now.

    The plan has to name the identity a delivered photograph will carry —
    otherwise "which asset is this replacing?" is answered by a filename, and
    filenames are exactly what the identity change removed. A re-crop and a
    commissioned replacement already have one: they take over the key of the
    photograph they replace, so every page pointing there shows the new
    picture with nothing edited.

    What has no identity yet is the REPLACE set, which was never registered —
    the register holds the 629 the audit approved. So the identities are
    reserved here, in the buy order, and `nextId` is advanced past the block.
    That last part is the whole point: a reservation written only into a
    spreadsheet is not a reservation, and the next ingest would hand the same
    number to something else.
    """
    reg = library.register()
    # RESERVATION IS BY sourceKey, SO RUNNING THIS TWICE RESERVES NOTHING NEW.
    # Keyed on a counter alone it was not idempotent: the second run found the
    # same 786 rows still absent from `assets`, handed out AKL-001416..002201
    # and left the first block stranded. The identity of a planned photograph
    # has to be found again the same way a real one is.
    book = (reg.get("reserved") or {}).get("ids") or {}
    for r in data:
        if not r["canonical asset id"]:
            r["canonical asset id"] = book.get(r["sourceKey"], "")
    need = [r for r in data if not r["canonical asset id"]
            and r["acquisition route"] in ("commission", "licence")]
    if not write:
        log("  %d identity/identities would be reserved from AKL-%06d "
            "(%d already reserved)"
            % (len(need), int(reg.get("nextId") or 1), len(book)))
        return
    if not need:
        log("  every planned acquisition already has an identity (%d reserved)"
            % len(book))
        return
    first = int(reg.get("nextId") or 1)
    for r in need:
        r["canonical asset id"] = library.new_id(reg)
        book[r["sourceKey"]] = r["canonical asset id"]
    reg["reserved"] = {
        "ids": book,
        "$comment": "Identities handed out to data/image-acquisition.csv for "
                    "photographs that do not exist yet. Pin them in the "
                    "ingest manifest's `id` column when the files arrive; "
                    "nextId is already past them so nothing else can be "
                    "given the same number.",
        "from": "AKL-%06d" % first,
        "to": "AKL-%06d" % (int(reg["nextId"]) - 1),
        "count": len(book),
    }
    library._write_register(reg, log=lambda *a: None)
    log("  reserved %d identity/identities, %s..%s"
        % (len(need), reg["reserved"]["from"], reg["reserved"]["to"]))


def run(write=False, log=print):
    data = rows(log=log)
    reserve(data, write=write, log=log)
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
    log("  the buy order:")
    waves, wcost = {}, {}
    for r in data:
        w = r.get("wave") or ""
        # P9 is the rows that need nothing bought — already ours, or waiting
        # on a person. Listing it in a buy order inflates the total and gives
        # it a cost band, neither of which is true.
        if not w.startswith("P") or w.startswith("P9"):
            continue
        waves[w] = waves.get(w, 0) + 1
        wcost.setdefault(w, set()).add(r["cost band"].split(" —")[0])
    for w in sorted(waves):
        log("  %-32s %5d   cost band %s"
            % (w, waves[w], "/".join(sorted(wcost[w]))))
    log("")
    live = [r for r in data if r["commercial tier"] <= 3
            and r["acquisition route"] in ("commission", "licence", "re-crop")
            and not (r.get("wave") or "").startswith("P9")]
    free = sum(n for w, n in waves.items() if w[:2] in ("P0", "P1", "P2"))
    buy = sum(n for w, n in waves.items() if w[:2] in ("P3", "P4", "P5", "P6"))
    log("  %d already ours — re-crop or migrate, no acquisition" % free)
    log("  %d to acquire, of which %d are in the 16 countries that carry a "
        "price" % (buy, len([r for r in live
                             if (r.get("wave") or "")[:2] in
                             ("P3", "P4", "P5", "P6")])))
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
