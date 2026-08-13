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
from .model import (CATEGORY_FILE, ROOT, load_picks, load_regions, load_views,
                    region_of)

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

MARKERS = ("window", "captions", "ticks", "regions", "claim", "months", "scale",
           "destinations", "operators", "picks", "nownote", "now", "stories", "footer")

# How much air to leave round a zoomed view, as a fraction of its long side.
VIEW_PAD = 0.34

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

# The one category that is a country's opening picture rather than a place, and
# so is the one entry in twenty-seven that never gets a page of its own.
HERO = "hero"


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


# This page spells its numbers. A figure in the middle of a display line reads
# as a statistic; a word reads as a sentence, and these are sentences. Above
# ninety-nine it goes back to figures, because "five hundred and ninety-four"
# is a different kind of sentence and not this one.
ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety")


def _spell(n):
    """Small numbers read as words in this typeface; the rest stay figures."""
    n = int(n)
    if n < 20:
        word = ONES[n] if 0 <= n < len(ONES) else str(n)
    elif n < 100:
        word = TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    else:
        return "{:,}".format(n)
    return word[0].upper() + word[1:]


def block_claim(countries):
    """What this site is, in three lines, counted from the files.

    It used to open "Fifty-four countries" — the number of countries in Africa,
    printed where a reader takes it as the number of countries here. Twenty-two
    are written up. The map caption two screens above had it right all along
    ("Fifty-four countries. Twenty-two of them are destinations here"), which is
    how the overclaim survived: the honest sentence existed, just not in the
    place that says it loudest.

    Every number below is len() of something on disk, so the sentence cannot
    drift from the dataset the way a hand-typed one did.
    """
    n = len(countries)
    regions = len(REGION_GROUPS)
    cats = len(read_json(CATEGORY_FILE, {}).get("categories", []))
    # Not len(entries). Twenty-seven of the twenty-seven categories are written,
    # but one of them is `hero` — the country's own opening picture, which has no
    # page of its own. /places counts 572 for exactly that reason, and a homepage
    # saying 594 while /places says 572 is two numbers for one thing.
    places = sum(1 for c in countries for e in c.entries
                 if getattr(e, "category", None) != HERO)
    return ('      <p class="wa-claim">%s countries. %s regions.<br>'
            '%s ways to experience each of them.<br>'
            '<em>%s places, each written up on its own.</em></p>'
            % (_spell(n), _spell(regions), _spell(cats), _spell(places)))


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
    # The fourth card used to read "A licensed operator in each". There are three
    # operators in tourism/operators.json and there have only ever been three, so
    # that line was asserting nineteen companies that do not exist anywhere in
    # this project. What is true about those nineteen is that they are written up
    # on the same twenty-seven categories as the three — which is the more useful
    # thing to say anyway, and it now goes somewhere instead of sitting there.
    rest = len(countries) - len(ours)
    cards.append(
        '      <a class="wa-op wa-op--rest" href="/places"><span class="wa-op-where">Everywhere else</span>'
        '<b>%s more countries</b><span class="wa-op-base">Written up, no operator of ours yet</span>'
        '<p>We run companies in %s. The other %s are written up to the same '
        'twenty-seven categories by the same hands, so any two countries here can be '
        'compared on the same terms &mdash; you are just booking them through someone else.</p>'
        '<span class="wa-op-go">Every place, all %s countries &rarr;</span></a>'
        % (_spell(rest), _and_list([c.name for c in ours]),
           _spell(rest).lower(), _spell(len(countries)).lower()))
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
            # This section argues the continent is bigger than the map people
            # carry in their heads and then stopped. The atlas is that argument
            # continuing — same equal-area projection, and you can move in it.
            '        <p class="wa-scale-go"><a class="af-go" href="/atlas">'
            'See it at that size in the atlas &rarr;</a></p>\n'
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


NOW_ARCS = ("the-table", "made-by-hand", "the-city-now")
NOW_CARDS = 6


def now_rows(countries):
    """Which contemporary chapters the strip shows, in order.

    Pulled out of block_now so the sentence above the strip and the strip itself
    count the same thing. They did not: the section was cut from nine cards to
    six and the paragraph beside it went on saying "Nine of them here" for two
    commits, because the cards are generated and the paragraph was typed.
    """
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    rows = [r for r in (data.get("stories") or []) if r.get("now")]
    live = {c.slug: c for c in countries}
    picked, taken = [], set()

    def take(r):
        picked.append(r)
        taken.add(r["country"])

    # One card per country, without exception. Letting the photographed ones in
    # first put Cameroon and Uganda on this strip three times each — the two
    # countries whose over-promotion is the reason the section they replaced was
    # removed. So a country with a photograph gets that arc, and one card.
    for r in rows:
        if r.get("image") and r["country"] in live and r["country"] not in taken:
            take(r)
    i = 0
    while len(picked) < NOW_CARDS and i < 200:
        arc = NOW_ARCS[i % len(NOW_ARCS)]
        i += 1
        for r in rows:
            if r["arc"] == arc and r["country"] in live and r["country"] not in taken:
                take(r)
                break
    return picked[:NOW_CARDS]


def block_nownote(countries):
    """The sentence beside the strip, counting what the strip actually holds."""
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    total = len([r for r in (data.get("stories") or []) if r.get("now")])
    shown = len(now_rows(countries))
    if not shown:
        return ('        <p class="wa-note">No contemporary chapters have been built '
                'yet.</p>')
    return ('        <p class="wa-note">%s chapters across the %s countries are about '
            'what is cooked, made and built this decade rather than what is behind '
            'glass. %s of them here. Not a feed and not an events calendar &mdash; '
            'this site holds no dates and will not invent any; these are evergreen, '
            'and they are true for longer than a week.</p>'
            % (_spell(total), _spell(len(countries)).lower(), _spell(shown)))


def block_now(countries):
    """Africa now — the contemporary layer, and the argument against a museum.

    Three of the eleven story arcs are marked `now` in arcs.json: the table,
    made by hand, and the city now. Sixty-six chapters across the twenty-two,
    all of them about what a country cooks, makes and builds this decade rather
    than what is behind glass in it. None of that was on the homepage.

    Evergreen and saying so. There is no feed behind this and no dated event in
    the dataset, so it does not pretend to be current — it is the part of the
    writing that is about now, which is a different and true claim.

    Six of them, across six countries, with the three arcs alternating. Six
    rather than nine because this replaced a section of 984 pixels and nine cards
    made it 1693 — the argument does not get better for being three rows tall,
    and this page has grown in every wave already.
    """
    picked = now_rows(countries)
    if not picked:
        return '      <p class="wa-note">No contemporary chapters built yet.</p>'
    live = {c.slug: c for c in countries}
    regions = load_regions()

    out = []
    for r in picked:
        c = live[r["country"]]
        key, _reg = region_of(c, regions)
        art = ('<img src="%s" alt="%s" width="800" height="600" loading="lazy" '
               'decoding="async">' % (esc(r["image"]), esc(r["text"]))) if r.get("image") else (
              '<span class="wa-now-plate" aria-hidden="true"></span>')
        out.append(
            '      <a class="wa-now%s" href="%s" style="--reg-tone:%s">'
            '<span class="wa-now-art">%s</span>'
            '<span class="wa-now-say"><i>%s &middot; %s</i><b>%s</b><p>%s</p></span></a>'
            % (" has-shot" if r.get("image") else "", esc(r["url"]),
               esc((regions.get(key).tone if regions.get(key) else "")), art,
               esc(r["countryName"]), esc(r["arcTitle"]), esc(r["title"]), esc(r["text"])))
    return "\n".join(out)


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
        "claim": block_claim(seq),
        "months": block_months(seq),
        "destinations": block_destinations(seq),
        "scale": block_scale(),
        "operators": block_operators(seq),
        "picks": block_picks(seq),
        "nownote": block_nownote(seq),
        "now": block_now(seq),
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
