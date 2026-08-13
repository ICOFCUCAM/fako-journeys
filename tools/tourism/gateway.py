"""Regenerate the country-dependent parts of the gateway from the dataset.

    python3 tools/tourism/build.py gateway

The gateway is a hand-designed page and stays one. But five regions of it were
lists of countries typed out by hand — the hero's window states, its captions,
its destination ticks, the destination grid, and the footer columns — and a
twenty-third country meant editing all five and hoping none of them was missed.
That is not a design that grows to fifty-four.

So those five regions are marked in index.html:

    <!-- gen:destinations -->  ...generated...  <!-- /gen:destinations -->

and this rewrites what is between the markers from tourism/countries/*.json plus
tourism/shapes.json. Everything outside the markers — the layout, the copy, the
narrative, the CSS — is untouched, because that part is a design decision and
not a data one.

Adding a country is now: write its dataset, add its outline to shapes.json with
`africa_map.py --solo`, run `build.py all`. Nothing in this file, and nothing in
index.html, names a country.
"""

import html as html_mod
import json
import os
import re

from . import plate
from .model import ROOT, load_picks, load_regions, load_views

LINKS = os.path.join(ROOT, "data", "links.json")


def read_json(path, fallback=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback if fallback is not None else {}

PAGE = os.path.join(ROOT, "index.html")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")
SCALE = os.path.join(ROOT, "tourism", "scale.json")

# Regions in the order the continent is read on this site, north-west round to
# the islands. The only structural list here: five regions, not fifty-four
# countries, and a country declares which one it is in.
REGION_ORDER = ("Central & West Africa", "West Africa", "East Africa",
                "Southern Africa", "North Africa", "Islands")

# The grid's headings group several dataset regions into one column heading —
# Cameroon files itself as "Central & West Africa" and Ghana as "West Africa",
# and on the page they belong together.
REGION_GROUPS = (
    ("central", "Central &amp; West Africa", ("Central & West Africa", "West Africa")),
    ("east", "East Africa", ("East Africa",)),
    ("southern", "Southern Africa", ("Southern Africa",)),
    ("north", "North Africa", ("North Africa",)),
    ("islands", "Islands", ("Islands",)),
)

MARKERS = ("window", "captions", "ticks", "regions", "months", "scale", "destinations",
           "operators", "picks", "stories", "footer")

# How much air to leave round a zoomed view, as a fraction of its long side.
VIEW_PAD = 0.34

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def ordered(countries):
    """Published countries, our own operators first, then by region and name.

    Our three lead because they are the strongest thing we have to offer, not
    because of where they are; after that the order is geographic so the ticks
    read as a sweep across the continent rather than an alphabet.
    """
    def key(c):
        region = c.region if c.region in REGION_ORDER else "Islands"
        return (0 if c.operator else 1, REGION_ORDER.index(region), c.name)
    return sorted([c for c in countries if c.published], key=key)


def shapes():
    import json
    try:
        with open(SHAPES) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {}


def operator_line(c):
    return ("Operated locally by %s" % esc(c.operator.name)) if c.operator \
        else "Run with a licensed local operator"


def block_operators(countries):
    """The three companies of our own, as identities rather than three names.

    "Run by people who live there" is the platform's whole claim, and it was
    being made by printing a company name three times. An operator has a base, a
    year it started and a sentence about what it actually runs; printing those is
    the difference between a claim and evidence.
    """
    ours = [c for c in countries if c.operator]
    cards = []
    for c in ours:
        op = c.operator
        cards.append(
            '      <a class="wa-op" href="%s"><span class="wa-op-where">%s</span>'
            '<b>%s</b><span class="wa-op-base">%s &middot; since %s</span>'
            '<p>%s</p><span class="wa-op-go">Enter %s &rarr;</span></a>'
            % (esc(op.url), esc(c.name), esc(op.name), esc(op.base), esc(op.since),
               esc(op.line), esc(op.name)))
    cards.append(
        '      <div class="wa-op wa-op--rest"><span class="wa-op-where">Everywhere else</span>'
        '<b>%d more countries</b><span class="wa-op-base">A licensed operator in each</span>'
        '<p>Every other destination is covered by a company based in it, working through the '
        'same twenty-seven categories, so two countries can be compared on the same terms.</p></div>'
        % (len(countries) - len(ours)))
    return "\n".join(cards)


def pad_box(box, pad=VIEW_PAD):
    """Grow a box so a zoomed country is not pressed against the frame."""
    x, y, w, h = box
    m = max(w, h) * pad
    return [round(x - m, 1), round(y - m, 1), round(w + 2 * m, 1), round(h + 2 * m, 1)]


def union(boxes):
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def block_regions(countries, views):
    """Africa, then five regions — the middle rung of the atlas.

    A region is a view of the map and a list of countries, so its button carries
    both: the box to fly the viewBox to, and the slugs that stay lit while it is
    selected. The box is the union of its members', computed here rather than
    typed, so a new country widens its region's view automatically.
    """
    regions = load_regions()
    boxes = views.get("countries") or {}
    out = ['<button class="wa-reg" type="button" data-reg="africa" aria-pressed="true" '
           'data-view="%s" data-line="%s" data-terrain="%s">Africa</button>'
           % (" ".join(str(v) for v in views.get("africa") or [0, 0, 1000, 1060]),
              esc("Fifty-four countries. Twenty-two of them are destinations here."),
              esc("Desert|Rainforest|Savanna|Mountain|Coast|Island"))]
    for key, reg in regions.items():
        members = [c for c in countries if c.region in reg.includes]
        member_boxes = [boxes[c.slug] for c in members if c.slug in boxes]
        if not member_boxes:
            continue
        out.append(
            '<button class="wa-reg" type="button" data-reg="%s" aria-pressed="false" '
            'data-view="%s" data-slugs="%s" data-line="%s" data-terrain="%s">%s</button>'
            % (esc(key), " ".join(str(v) for v in pad_box(union(member_boxes))),
               esc(" ".join(c.slug for c in members)), esc(reg.line),
               esc("|".join(reg.terrain)), esc(reg.name)))
    return "      " + "".join(out)


def block_window(countries, shape_by_slug):
    """The hero's window states — one per country, from the shared component.

    This function used to build its own clip-path, which made it the fourth
    place on the site that knew how to mask a photograph into a country. It is
    now the same `window_svg` the country pages, the journey engine and the
    human layer draw, so the signature cannot drift into four dialects of
    itself. The wrapper class stays local because the hero sizes it.
    """
    out = []
    for c in countries:
        s = shape_by_slug.get(c.slug)
        if not s:
            continue
        out.append(
            '      <figure class="wa-win-state" data-slug="%s">\n        %s\n      </figure>'
            % (esc(c.slug),
               plate.window_svg(s, c.name, image=c.window or None,
                                alt=c.window_alt or None,
                                ident="wc-%s" % c.slug,
                                classes="wa-win-shape af-window-svg")))
    return "\n".join(out)


def block_captions(countries):
    return "\n          ".join(
        '<div class="wa-win-cap" data-slug="%s"><span class="wa-win-region">%s</span>'
        '<b>%s</b><span class="wa-win-tag">%s</span><span class="wa-win-op">%s</span>'
        '<a class="wa-win-go" href="%s">Enter %s &rarr;</a></div>'
        % (esc(c.slug), esc(c.region), esc(c.name), esc(c.tagline),
           operator_line(c), esc(c.url), esc(c.name))
        for c in countries)


def block_ticks(countries, views):
    boxes = views.get("countries") or {}
    out = []
    for c in countries:
        box = boxes.get(c.slug)
        view = (' data-view="%s"' % " ".join(str(v) for v in pad_box(box, 0.9))) if box else ""
        out.append('<button class="wa-tick" type="button" data-slug="%s"%s>%s</button>'
                   % (esc(c.slug), view, esc(c.name)))
    return "".join(out)


def block_months(countries):
    """Twelve buttons, each knowing how many destinations are good in it.

    "When can I go" is the second question a traveller asks, and across a
    continent it has a real answer: the dry season in Zambia is the cyclone
    season in Mauritius. Answering it with a paragraph is what every tourism
    site does; answering it with a control is the point of holding the same
    twenty-seven categories and the same calendar for every country.
    """
    out = []
    for i, name in enumerate(MONTHS, start=1):
        n = sum(1 for c in countries if i in c.months)
        out.append('<button class="wa-month" type="button" data-month="%d" '
                   'aria-pressed="false"><b>%s</b><span>%d</span></button>'
                   % (i, esc(name[:3]), n))
    return "      " + "".join(out)


def block_picks(countries):
    """The answer to "what do you want", written rather than listed.

    Eight wants, each with one country named and a reason to name it. The
    counter-suggestion — "then don't start with Kilimanjaro" — is what makes it
    a recommendation instead of a filter, and it is the closest thing this site
    has to a voice.
    """
    picks = load_picks()
    by_slug = dict((c.slug, c) for c in countries)
    out = []
    for want, p in picks.items():
        c = by_slug.get(p.get("country"))
        if not c:
            continue
        out.append(
            '      <article class="wa-pick" data-pick="%s" hidden>\n'
            '        <p class="wa-pick-hook">%s</p>\n'
            '        <div class="wa-pick-body">\n'
            '          <span class="wa-pick-where">%s</span>\n'
            '          <b>%s</b>\n'
            '          <p>%s</p>\n'
            '          <p class="wa-pick-why">%s</p>\n'
            '          <a class="wa-pick-go" href="%s">Explore %s &rarr;</a>\n'
            '        </div>\n      </article>'
            % (esc(want), esc(p.get("hook")), esc(c.region), esc(c.name),
               esc(c.summary), esc(p.get("why")), esc(c.url), esc(c.name)))
    return "\n".join(out)


def block_scale():
    """Africa at true size, with one country laid inside it at a time.

    Everybody's mental map of the world is Mercator, which inflates everything
    away from the equator and shrinks everything on it, and the result is that
    Africa is remembered as roughly the size of Greenland. These outlines are
    drawn with the same equal-area projection as the map in the hero — each
    centred on itself, which is what keeps the areas honest — so this is
    geometry rather than an illustration of a fact.
    """
    import json
    try:
        with open(SCALE) as fh:
            data = json.load(fh)
    except (IOError, ValueError):
        return ""
    shapes = data.get("shapes") or []
    if not shapes:
        return ""
    figs = "".join(
        '<g class="wa-scale-in" data-scale="%d" transform="translate(%d,%d)">'
        '<path d="%s"/></g>' % (i, s["x"], s["y"], s["d"])
        for i, s in enumerate(shapes))
    btns = "".join(
        '<button class="wa-scale-btn" type="button" data-scale="%d" aria-pressed="%s">'
        '<b>%s</b><span>%s m km&sup2;</span></button>'
        % (i, "true" if i == 0 else "false", esc(s["label"]), esc(s["area"]))
        for i, s in enumerate(shapes))
    total = sum(float(s["area"]) for s in shapes)
    return ('      <div class="wa-scale-map">\n'
            '        <svg viewBox="0 0 1000 1060" role="img" aria-label="Africa at true scale, '
            'with the United States, China, India and western Europe drawn inside it at the same '
            'equal-area scale.">\n'
            '          <path class="wa-scale-land" d="%s"/>\n'
            '          %s\n        </svg>\n      </div>\n'
            '      <div class="wa-scale-side">\n'
            '        <div class="wa-scale-btns" role="group" aria-label="Lay a country inside Africa">%s</div>\n'
            '        <p class="wa-scale-sum"><b>%s</b><span>million km&sup2;</span></p>\n'
            '        <p class="wa-scale-note">All four together come to %.1f million. Africa is %s. '
            'These are drawn with the same equal-area projection as the map above, each centred on '
            'itself &mdash; so this is geometry, not an illustration of a fact.</p>\n'
            '      </div>'
            % (data.get("land", ""), figs, btns, esc(data.get("africa", "30.4")),
               total, esc(data.get("africa", "30.4"))))


def _neighbours(slug, links, live):
    """Which of the published countries this one shares a land border with.

    Read off links.json, which links.py built by finding shared vertices in the
    Natural Earth polygons — so this is geometry rather than a typed list, and a
    country that borders nothing published here says so instead of being given a
    neighbour it does not have. Islands are the honest empty case: Seychelles
    touches nobody, and printing nothing for it is correct.
    """
    rows = links.get(slug) or []
    out = []
    for r in rows:
        if r["to"] not in live:
            continue
        if not any(w["kind"] == "border" for w in r.get("why") or []):
            continue
        out.append((r["to"], r["name"]))
    return out


def _and_list(parts):
    """a, b and c — an Oxford-free list, because this is prose not a table."""
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def block_destinations(countries):
    """The grid, grouped by region, each card carrying what it leads on and
    what it touches."""
    links = (read_json(LINKS) or {}).get("links") or {}
    region_meta = load_regions()
    live = {c.slug for c in countries}
    by_region = {}
    for c in countries:
        for key, _title, regions in REGION_GROUPS:
            if c.region in regions:
                by_region.setdefault(key, []).append(c)
                break
    rows = []
    for key, title, _regions in REGION_GROUPS:
        group = by_region.get(key) or []
        if not group:
            continue
        # The region tier was a bare label between two grids. It carries its
        # own sentence and its own count now, and routes into the atlas at that
        # region — so the ladder AFRICA / REGION / COUNTRY is legible on the
        # page rather than only in the markup. All of it out of regions.json.
        reg = region_meta.get(key)
        rows.append(
            '      <div class="wa-dest-band" data-region="%s">'
            '<h3 class="wa-dest-reg">%s</h3>'
            '<p class="wa-dest-line">%s</p>'
            '<p class="wa-dest-count"><a href="/atlas#/%s">%d %s in the atlas &rarr;</a></p>'
            '</div>'
            # `title` is already HTML in REGION_GROUPS ("Central &amp; West"),
            # so escaping it here would print &amp;amp;.
            % (key, title, esc(reg.line if reg else ""), esc(key), len(group),
               "country" if len(group) == 1 else "countries"))
        for c in sorted(group, key=lambda x: (0 if x.operator else 1, x.name)):
            reg = region_meta.get(key)
            tone = reg.tone if reg else ''
            near = _neighbours(c.slug, links, live)
            # One sentence, not a stack of links. Tanzania borders five of the
            # published countries; five underlined blocks under every write-up
            # added more than a thousand pixels to the section and read as five
            # more calls to action.
            borders = ('<p class="wa-dest-near">Walk out of it into %s.</p>'
                       % _and_list('<a href="/portrait/%s">%s</a>' % (esc(sl), esc(n))
                                   for sl, n in near)) if near else ""
            rows.append(
                '      <div class="wa-dest"%s data-region="%s" data-tags="%s" data-months="%s"'
                ' style="--reg-tone:%s">'
                '<b>%s</b><h3>%s</h3><p>%s</p>'
                '<p class="wa-dest-when">%s</p>%s'
                '<a href="%s">Explore %s &rarr;</a></div>'
                % (' data-ours="true"' if c.operator else '',
                   key, esc(" ".join(c.calls)), esc(",".join(str(m) for m in c.months)),
                   esc(tone),
                   esc(c.operator.name if c.operator else ''), esc(c.name), esc(c.summary), esc(c.when),
                   borders, esc(c.url), esc(c.name)))
    return "\n".join(rows)


def block_stories(countries):
    """The reading room, as it actually is.

    This section used to name five stories that were "being written now" and
    link to none of them. Twenty-two long reads have existed since the story
    engine shipped, so the homepage was promising work it had already done and
    sending nobody to it — a section with no links at all.

    One story per region, chosen by taking the first arc each region offers, so
    the five are five different countries rather than five chapters of one; plus
    the count, which is a fact rather than a promise.
    """
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    rows = data.get("stories") or []
    if not rows:
        return ('      <p class="wa-note">The reading room has not been built yet. '
                'Run <code>build.py story</code>.</p>')
    regions = load_regions()
    live = {c.slug: c for c in countries}
    # A different arc per region, so the five read as five kinds of story rather
    # than the same chapter five times — taking the first arc each region offers
    # gives "The first thing you would see" five times over.
    order = []
    for r in rows:
        if r["arc"] not in order:
            order.append(r["arc"])
    picked, seen = [], set()
    for i, key in enumerate(regions):
        want = [order[(i + n) % len(order)] for n in range(len(order))]
        best = None
        for arc in want:
            for r in rows:
                if r["regionKey"] == key and r["arc"] == arc \
                        and r["country"] not in seen and r["country"] in live:
                    best = r
                    break
            if best:
                break
        if best:
            picked.append(best)
            seen.add(best["country"])
    out = []
    for i, r in enumerate(picked):
        out.append(
            '      <a class="wa-story%s" href="%s"><i>%s &middot; %s</i>'
            '<h3>%s</h3><p>%s</p><span class="wa-story-go">Read %s &rarr;</span></a>'
            % (" wide" if i == 0 else "", esc(r["url"]), esc(r["countryName"]),
               esc(r["arcTitle"]), esc(r["title"]), esc(r["text"]),
               esc(r["countryName"])))
    out.append(
        '      <a class="wa-story wa-story--all" href="/stories">'
        '<i>The reading room</i><h3>All %d, across %d countries</h3>'
        '<p>Every chapter is cut from what that country says about itself, and '
        'every paragraph in it has an address of its own.</p>'
        '<span class="wa-story-go">Open the reading room &rarr;</span></a>'
        % (len(rows), len({r["country"] for r in rows})))
    return "\n".join(out)


def block_footer(countries):
    """Two columns, split evenly, so the footer never becomes one long list."""
    half = (len(countries) + 1) // 2
    cols = (("Destinations", countries[:half]), ("More destinations", countries[half:]))
    out = []
    for title, group in cols:
        links = "\n".join('        <a href="%s">%s</a>' % (esc(c.url), esc(c.name)) for c in group)
        out.append('      <div class="wa-foot-col">\n        <b>%s</b>\n%s\n      </div>' % (title, links))
    return "\n".join(out)


def render(countries):
    seq = ordered(countries)
    shape_by_slug = shapes()
    views = load_views()
    with_shape = [c for c in seq if c.slug in shape_by_slug]
    return {
        "regions": block_regions(seq, views),
        "window": block_window(with_shape, shape_by_slug),
        "captions": block_captions(with_shape),
        "ticks": block_ticks(with_shape, views),
        "months": block_months(seq),
        "destinations": block_destinations(seq),
        "scale": block_scale(),
        "operators": block_operators(seq),
        "picks": block_picks(seq),
        "stories": block_stories(seq),
        "footer": block_footer(seq),
    }


def splice(src, blocks):
    """Replace between each pair of markers. Missing markers are an error, not a
    silent no-op: a marker that got lost in an edit would otherwise mean a
    section quietly stopped tracking the dataset."""
    missing = [name for name in MARKERS if ("<!-- gen:%s -->" % name) not in src]
    if missing:
        raise ValueError("index.html is missing markers: %s" % ", ".join(missing))
    for name, body in blocks.items():
        pattern = re.compile(r"(<!-- gen:%s -->\n).*?(\s*<!-- /gen:%s -->)" % (name, name), re.S)
        src = pattern.sub(lambda m: m.group(1) + body + m.group(2), src, count=1)
    return src


def run(countries, page=None, log=print):
    page = page or PAGE
    with open(page) as fh:
        src = fh.read()
    out = splice(src, render(countries))
    changed = out != src
    if changed:
        with open(page, "w") as fh:
            fh.write(out)
    seq = ordered(countries)
    log("%s %d countries (%d with an operator of ours) into %s"
        % ("rewrote" if changed else "no change:", len(seq),
           sum(1 for c in seq if c.operator), os.path.relpath(page, ROOT)))
    return changed
