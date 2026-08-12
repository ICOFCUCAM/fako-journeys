"""The living atlas: /atlas, built from the dataset.

    python3 tools/tourism/build.py atlas

The gateway's hero carries a map. This is not that. The map on the home page is
a way into twenty-two countries; the atlas is the geography itself as the
interface, with one ladder running all the way down:

    Africa -> region -> country -> place -> what you would do there -> who takes you

Everything on every rung comes out of the dataset. There is no list of countries
in this file, no list of regions, no hand-placed pin and no coordinate typed by
hand. The continent's geometry is tourism/map.json (africa_map.py --map), the
regions are tourism/regions.json, the countries are tourism/countries/*.json,
the boxes to fly to are tourism/views.json, and the six things a country can
lead on are tourism/lenses.json. Add the fifty-fifth country's file and it is on
the map, in its region, under the right lenses, in the right months.

What ships:

    atlas.html            the page: chrome, the map, and the continent pane
    data/atlas/<slug>.json  one country's places, fetched when it is opened

The split is the performance story. The spine — every country's name, tagline,
summary, season, operator and box — is ten kilobytes and is inlined, so moving
Africa -> region -> country costs no request at all. The twenty-six places
inside a country are four kilobytes each and are fetched the first time that
country is opened, and never again.

Without JavaScript the page is still an atlas: the map's countries are links to
their own pages, and the continent pane lists every region and every country in
it. The script upgrades that into navigation; it does not create it.
"""

import html as html_mod
import json
import os

from . import plate
from .model import (ROOT, load_countries, load_operators, load_picks,
                    load_regions, load_views)

PAGE = os.path.join(ROOT, "atlas.html")
DATA = os.path.join(ROOT, "data", "atlas")
MAP = os.path.join(ROOT, "tourism", "map.json")
LENSES = os.path.join(ROOT, "tourism", "lenses.json")

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")
MON3 = tuple(m[:3].upper() for m in MONTHS)

# How much air round a zoomed view, as a fraction of its long side. A country
# pressed against the frame reads as a diagram; one with room round it reads as
# a place with neighbours.
PAD_COUNTRY = 0.45
PAD_REGION = 0.12


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def pad(box, k):
    x, y, w, h = box
    m = max(w, h) * k
    return [round(x - m, 1), round(y - m, 1), round(w + 2 * m, 1), round(h + 2 * m, 1)]


def union(boxes):
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def read(path, fallback):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def load_lenses():
    """The six lenses, minus the `$comment` the file explains itself with."""
    return dict((k, v) for k, v in read(LENSES, {}).items() if not k.startswith("$"))


# ---- the spine -------------------------------------------------------------------


def spine(countries, lenses):
    """Everything the atlas needs to move between rungs, without a request.

    Names, taglines, summaries, seasons, operators and boxes for every country,
    plus the regions they group into and the lenses they answer to. It is the
    country files re-cut for the browser: nothing here is authored, and nothing
    here is a second copy of anything a human maintains.
    """
    views = load_views()
    boxes = views.get("countries") or {}
    regions = load_regions()
    ops = load_operators()
    live = [c for c in countries if c.published]

    out = {"view": views.get("africa") or [0, 0, 1000, 1060],
           "months": list(MONTHS), "regions": [], "countries": {},
           "lenses": [], "picks": load_picks()}

    for key, reg in regions.items():
        members = [c for c in live if c.region in reg.includes]
        member_boxes = [boxes[c.slug] for c in members if c.slug in boxes]
        if not members:
            continue
        out["regions"].append({
            "key": key, "name": reg.name, "line": reg.line,
            "terrain": reg.terrain,
            "countries": [c.slug for c in members],
            "view": pad(union(member_boxes), PAD_REGION) if member_boxes
                    else out["view"],
        })

    region_of = {}
    for r in out["regions"]:
        for slug in r["countries"]:
            region_of[slug] = r["key"]

    for c in live:
        op = ops.get(c.operator_key)
        out["countries"][c.slug] = {
            "name": c.name, "adjective": c.adjective,
            "region": c.region, "regionKey": region_of.get(c.slug, ""),
            "tagline": c.tagline, "summary": c.summary,
            "when": c.when, "months": c.months, "url": c.url,
            "calls": c.calls, "places": len([e for e in c.entries if e.category != "hero"]),
            "view": pad(boxes[c.slug], PAD_COUNTRY) if c.slug in boxes else out["view"],
            "box": boxes.get(c.slug),
            "window": c.window, "windowAlt": c.window_alt,
            "operator": ({"name": op.name, "base": op.base, "since": op.since,
                          "line": op.line, "url": op.url} if op else None),
        }

    for key, lens in lenses.items():
        members = [c.slug for c in live if key in c.calls]
        out["lenses"].append({"key": key, "title": lens.get("title") or key,
                              "line": lens.get("line") or "",
                              "categories": lens.get("categories") or [],
                              "countries": members})
    out["lenses"].sort(key=lambda l: (-len(l["countries"]), l["title"]))
    return out


def places(country, taxonomy, lenses):
    """One country's places, in the order that country would tell them.

    A place here is one of the twenty-six things already written about the
    country — a caption, a description and the category it was written for.
    They are not invented, and no coordinate is claimed for them: the atlas
    knows which country a place is in, which is exactly what the dataset knows.

    The order is editorial rather than alphabetical: whatever the country calls
    itself on comes first, so Uganda opens on gorillas and Morocco on the Atlas.
    """
    lens_of = {}
    for key, lens in lenses.items():
        for cat in lens.get("categories") or []:
            lens_of.setdefault(cat, []).append(key)

    from .places import slugify
    titles = {c["id"]: c["title"] for c in taxonomy.categories}
    lead = [k for k in country.calls]
    seen_slug, rows = {}, []
    for e in country.entries:
        if e.category == "hero" or not e.caption:
            continue
        keys = lens_of.get(e.category, [])
        rank = min([lead.index(k) for k in keys if k in lead] or [99])
        img = e.image or {}
        # Its own address. The same rule places.py uses, so the interfaces and
        # the pages cannot disagree about where a place lives.
        base = slugify(e.caption)
        seen_slug[base] = seen_slug.get(base, 0) + 1
        path = base if seen_slug[base] == 1 else "%s-%d" % (base, seen_slug[base])
        rows.append((rank, {
            "id": e.category, "group": titles.get(e.category, e.category),
            "title": e.caption, "text": e.description or "",
            "url": "/places/%s/%s" % (country.slug, path),
            "lenses": keys,
            "image": ({"url": img.get("imageUrl"), "alt": img.get("alt") or e.description,
                       "credit": img.get("photographer"), "provider": img.get("provider")}
                      if img.get("imageUrl") else None),
        }))
    rows.sort(key=lambda r: r[0])
    return {"slug": country.slug, "name": country.name,
            "places": [r[1] for r in rows]}


# ---- the map ---------------------------------------------------------------------


def map_svg(data, spine_data):
    """The continent, once, as one SVG.

    Every country on the roster is an anchor to its own page, so the map works
    before a line of script runs and is reachable by keyboard for free. The
    clip paths are what let a country stop being an outline and become a window
    on to a photograph without swapping any geometry: the same path draws the
    border and masks the picture.
    """
    view = " ".join(str(v) for v in data.get("view") or [0, 0, 1000, 1060])
    n_live = len(data.get("live") or []) + len(data.get("marks") or [])
    out = ['<svg class="at-svg" id="at-svg" viewBox="%s" '
           'aria-label="Map of Africa. %d countries can be opened." role="group" '
           'xmlns="http://www.w3.org/2000/svg">' % (view, n_live)]

    out.append('  <g class="at-rest" aria-hidden="true">')
    for row in data.get("rest") or []:
        out.append('    <path d="%s"><title>%s</title></path>' % (row["d"], esc(row["n"])))
    out.append("  </g>")

    # Windows first in document order so the outlines and the labels paint over
    # them. An empty <image> is written for every country that has a picture;
    # the ones that do not simply stay filled, which is the empty state and is
    # meant to look like a decision rather than a gap.
    out.append('  <defs>')
    for row in data.get("live") or []:
        out.append('    <clipPath id="ac-%s"><path d="%s"/></clipPath>' % (row["slug"], row["d"]))
    out.append('  </defs>')
    out.append('  <g class="at-wins" aria-hidden="true">')
    for row in data.get("live") or []:
        meta = spine_data["countries"].get(row["slug"]) or {}
        box = meta.get("box")
        if not box:
            continue
        out.append('    <image class="at-win" id="aw-%s" clip-path="url(#ac-%s)" '
                   'x="%s" y="%s" width="%s" height="%s" '
                   'preserveAspectRatio="xMidYMid slice"/>'
                   % (row["slug"], row["slug"], box[0], box[1], box[2], box[3]))
    out.append("  </g>")

    out.append('  <g class="at-live">')
    for row in data.get("live") or []:
        out.append('    <a class="at-c" data-slug="%s" data-tier="%s" href="%s" '
                   'aria-label="%s — %s"><path d="%s"/><title>%s — %s</title></a>'
                   % (row["slug"], row["tier"], esc(row["href"]),
                      esc(row["name"]), esc(row["tag"]), row["d"],
                      esc(row["name"]), esc(row["tag"])))
    for row in data.get("marks") or []:
        out.append('    <a class="at-c at-c--mark" data-slug="%s" data-tier="%s" href="%s" '
                   'aria-label="%s — %s"><circle cx="%s" cy="%s" r="%s"/>'
                   '<title>%s — %s</title></a>'
                   % (row["slug"], row["tier"], esc(row["href"]),
                      esc(row["name"]), esc(row["tag"]),
                      row["at"][0], row["at"][1], row.get("r") or 9,
                      esc(row["name"]), esc(row["tag"])))
    out.append("  </g>")

    # Labels are geography, so they live in map coordinates and travel with the
    # zoom. Their size is not: the script rescales this group as the viewBox
    # narrows, or a country name becomes a headline the moment you fly to it.
    # The constellation: the same continent read as a network. Nodes sit at each
    # country's own centre in these coordinates, and every line drawn is a fact —
    # a shared land border, or the thing both countries say they lead on. Empty
    # markup until the mode is opened, because filling it costs a request.
    out.append('  <g class="at-web" id="at-web" aria-hidden="true"></g>')
    out.append('  <g class="at-labels" id="at-labels" aria-hidden="true" font-size="13">')
    for row in data.get("live") or []:
        if not row.get("at"):
            continue
        out.append('    <text class="at-label" data-slug="%s" x="%s" y="%s">%s</text>'
                   % (row["slug"], row["at"][0], row["at"][1], esc(row["name"])))
    for row in data.get("marks") or []:
        out.append('    <text class="at-label" data-slug="%s" x="%s" y="%s">%s</text>'
                   % (row["slug"], row["at"][0], row["at"][1] - 14, esc(row["name"])))
    out.append("  </g>")
    out.append("</svg>")
    return "\n".join(out)


# ---- the page --------------------------------------------------------------------


def pane_africa(sp):
    """The continent pane, written into the HTML rather than drawn by script.

    This is the no-JavaScript floor: five regions, every country in each, every
    one of them a link to its own page. The script turns the same buttons into
    flights across the map; without it they are still an index of Africa.
    """
    rows = []
    for reg in sp["regions"]:
        names = ", ".join(sp["countries"][s]["name"] for s in reg["countries"])
        rows.append(
            '        <li>\n'
            '          <button class="at-row" type="button" data-go="region" data-key="%s"\n'
            '                  data-slugs="%s">\n'
            '            <span class="at-row-no">%02d</span>\n'
            '            <span class="at-row-body"><b>%s</b>\n'
            '              <span class="at-row-line">%s</span>\n'
            '              <span class="at-row-meta">%d %s &middot; %s</span>\n'
            '            </span>\n'
            '            <span class="at-row-go" aria-hidden="true">&rarr;</span>\n'
            '          </button>\n'
            '          <noscript><p class="at-nojs">%s</p></noscript>\n'
            '        </li>'
            % (esc(reg["key"]), esc(" ".join(reg["countries"])),
               sp["regions"].index(reg) + 1, esc(reg["name"]),
               esc(reg["line"]), len(reg["countries"]),
               "country" if len(reg["countries"]) == 1 else "countries",
               esc(u" · ".join(reg["terrain"][:3])),
               esc(names)))
    return "\n".join(rows)


def lens_chips(sp):
    out = []
    for lens in sp["lenses"]:
        out.append('<button class="at-chip" type="button" data-lens="%s" aria-pressed="false">'
                   '%s<i>%d</i></button>'
                   % (esc(lens["key"]), esc(lens["title"]), len(lens["countries"])))
    return "\n            ".join(out)


def month_chips():
    return "\n            ".join(
        '<button class="at-chip at-chip--m" type="button" data-month="%d" '
        'aria-pressed="false" aria-label="%s">%s</button>' % (i + 1, MONTHS[i], MON3[i])
        for i in range(12))


def render(countries, taxonomy):
    lenses = load_lenses()
    sp = spine(countries, lenses)
    geo = read(MAP, {})
    if not geo.get("live"):
        raise IOError("tourism/map.json is missing or empty — "
                      "run: python3 tools/africa_map.py <topojson> --map > tourism/map.json")
    return TEMPLATE % {
        "og": plate.open_graph('The Atlas — Afrinkong', 'Africa as the interface. Continent, region, country, place — and who can take you there.', '/atlas'),
        "map": map_svg(geo, sp),
        "spine": json.dumps(sp, separators=(",", ":"), sort_keys=True),
        "regions": pane_africa(sp),
        "lenses": lens_chips(sp),
        "months": month_chips(),
        "n": len(sp["countries"]),
        "nplaces": sum(c["places"] for c in sp["countries"].values()),
    }


def run(countries, taxonomy, log=print):
    if not os.path.isdir(DATA):
        os.makedirs(DATA)
    lenses = load_lenses()
    written = 0
    live = [c for c in countries if c.published]
    for c in live:
        payload = places(c, taxonomy, lenses)
        path = os.path.join(DATA, "%s.json" % c.slug)
        with open(path, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"), sort_keys=True)
            fh.write("\n")
        written += len(payload["places"])
    # Country files come and go; a stale payload for a country that has been
    # removed would still be fetchable, so the directory is pruned to the set.
    keep = set("%s.json" % c.slug for c in live)
    for name in os.listdir(DATA):
        if name.endswith(".json") and name not in keep:
            os.remove(os.path.join(DATA, name))
    html = render(countries, taxonomy)
    with open(PAGE, "w") as fh:
        fh.write(html)
    log("atlas: %s (%.1f KB), %d country payload(s), %d places"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0, len(live), written))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Atlas &mdash; Afrinkong</title>
<meta name="description" content="Africa as the interface. Move from the continent to a region, a country, a place and the people who can take you there.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/atlas.css">
</head>
<body>
<a class="af-skip" href="#atlas">Skip to the atlas</a>
<header class="at-mast">
  <a class="at-mark" href="/"><i>Afrinkong</i><b>The Atlas</b></a>
  <nav class="at-routes" aria-label="Primary">
    <a href="/#window">Home</a>
    <a href="/journey">Build a journey</a>
    <a href="/meet">Meet Africa</a>
    <a href="/places">Every place</a>
    <a href="/#destinations">Destinations</a>
    <a href="/compare">Compare</a>
  </nav>
  <a class="af-btn af-btn--solid" href="/contact">Begin a journey<i>&rarr;</i></a>
</header>

<main class="at" id="atlas" data-level="africa">
  <div class="at-map">
    <div class="at-stage">
      <nav class="at-crumb" id="at-crumb" aria-label="Where you are">
        <button class="at-crumb-seg" type="button" data-go="africa" aria-current="page">Africa</button>
      </nav>
%(map)s
      <div class="at-mode" role="group" aria-label="How the map is drawn">
        <button class="at-modeb" type="button" data-mode="map" aria-pressed="true">Map</button>
        <button class="at-modeb" type="button" data-mode="links" aria-pressed="false">Links</button>
      </div>
    </div>
    <div class="at-tools">
      <div class="at-lens" role="group" aria-label="What do you want">
        <span class="at-lens-say">I want</span>
        <div class="at-chips">
            %(lenses)s
        </div>
      </div>
      <div class="at-lens at-lens--when" role="group" aria-label="When are you travelling">
        <span class="at-lens-say">In</span>
        <div class="at-chips">
            %(months)s
        </div>
      </div>
      <p class="at-count" id="at-count" role="status">%(n)d countries &middot; %(nplaces)d places</p>
      <button class="at-surprise" id="at-surprise" type="button">Take me somewhere<i>&rarr;</i></button>
    </div>
  </div>

  <aside class="at-panel" id="at-panel" aria-live="polite">
    <div class="at-pane" data-pane="africa" data-on>
      <span class="af-stamp">The continent</span>
      <h1 class="at-h1">Africa</h1>
      <p class="at-sub">Five regions. Fifty-four countries. Not one place.</p>
      <p class="at-lede">%(n)d of them are destinations here, and every one was
        written up through the same twenty-seven categories &mdash; so two
        countries on opposite sides of the continent can be compared on the same
        terms rather than on whichever one had the better photographer.</p>
      <ol class="at-rows">
%(regions)s
      </ol>
      <p class="at-foot-note">Choose a region, or press a country on the map.</p>
    </div>
    <div class="at-pane" data-pane="lens"></div>
    <div class="at-pane" data-pane="region"></div>
    <div class="at-pane" data-pane="country"></div>
    <div class="at-pane" data-pane="place"></div>
  </aside>
</main>

<script type="application/json" id="at-spine">%(spine)s</script>
<script src="/scripts/atlas.js" defer></script>
</body>
</html>
"""
