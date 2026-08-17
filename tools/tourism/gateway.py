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
from . import transafrique as _trans
from . import wonders as _wonders
from .model import (CATEGORY_FILE, ROOT, load_cities, load_lenses, load_moments,
                    load_motion, load_picks, load_regions, load_views, region_of)

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

MARKERS = ("wonders", "wonderslede", "door",
           "window", "captions", "ticks", "regions", "cities", "experiences",
           "wants", "expcards", "mapunder", "maplive", "mapover", "claim", "months", "scale",
           "lede", "capafrica", "destlede", "readslede", "mapsvg", "citylede",
           "destinations", "operators", "picks", "plannote", "planfork", "plansteps",
           "nownote", "now", "stories", "footer", "regiontone", "feel",
           "moments", "momentsay", "seasons", "seasonsay", "motion",
           "motiontracks")

# Markers that live inside <style> rather than in the document. An HTML comment
# there is not a comment: `<!--` and `-->` are CDO/CDC tokens the CSS parser
# skips, but the words between them are parsed as CSS, and the error recovery
# for a qualified rule with no block runs forward to the next `{` and eats the
# first real rule with it. So these are written as CSS comments instead.
CSS_MARKERS = ("regiontone",)

# How much air to leave round a zoomed view, as a fraction of its long side.
VIEW_PAD = 0.34

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

# The one category that is a country's opening picture rather than a place, and
# so is the one entry in twenty-seven that never gets a page of its own.
HERO = "hero"


IN_AFRICA = 54                 # UN member states. Western Sahara is not one.


def all_of_them(countries):
    """"Fifty-four countries. Twenty-two of them are destinations here" was an
    honest sentence for as long as those were different numbers. It is a strange
    one when they are the same, and it reads as a mistake rather than as an
    achievement — so at parity the second clause says what actually happened."""
    n = len(countries)
    if n >= IN_AFRICA:
        return "%s countries. Every one of them a destination here." % _spell(IN_AFRICA)
    return "%s countries. %s of them are destinations here." % (_spell(IN_AFRICA), _spell(n))


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
    """The line under a country's name on the homepage.

    It said "Written up here, run by somebody else" on fifty-one of the
    fifty-four cards — a disclaimer stamped across most of the continent, in
    the grid whose job is to make somebody want to open one. Where the company
    on the ground is ours that is worth naming, because it is evidence. Where
    it is not, the true and useful thing is that the journey is ours anyway.
    """
    return ("Operated locally by %s" % esc(c.operator.name)) if c.operator \
        else "Your journey here, run by Afrinkong"


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


SHOW_CITIES = 8



# Label placement, in viewBox units, calibrated against a real getBBox rather
# than assumed: ADDIS ABABA measures 161.5 x 22.7 units, which is 14.69 per
# character across eleven of them. The width formula was already right; the
# height was set to 15 by eye and is two thirds of the truth, which is why the
# first pass left ACCRA and ABIDJAN overlapping by two pixels vertically —
# their boxes were shorter than their type.
LAB_CH = 21 * 0.6 + 21 * 0.1     # 14.7, and the measurement agrees
LAB_H = 22.7
LAB_PAD = 8.0                    # about 4px at the size this renders

# The four places a label can go, in the order an atlas would try them: east of
# the dot first because that is where the eye expects it, then west, then above
# and below on the dot's own vertical.
LAB_SIDES = (
    ("east",  11.0, 4.0, "start"),
    ("west", -11.0, 4.0, "end"),
    ("north",  0.0, -13.0, "middle"),
    ("south",  0.0, 19.0, "middle"),
)


def _lab_box(x, y, name, dx, dy, anchor):
    w = LAB_CH * len(name)
    left = x + dx
    if anchor == "end":
        left -= w
    elif anchor == "middle":
        left -= w / 2.0
    top = y + dy - LAB_H
    return (left, top, left + w, top + LAB_H)


def _overlap_area(a, b, pad=LAB_PAD):
    """How much two label boxes fight over, padded. 0 means they do not."""
    w = min(a[2] + pad, b[2] + pad) - max(a[0] - pad, b[0] - pad)
    h = min(a[3] + pad, b[3] + pad) - max(a[1] - pad, b[1] - pad)
    return w * h if w > 0 and h > 0 else 0.0


def place_labels(cities, named):
    """Which side of its dot each label sits on, so that none of them collide.

    Every label used to be written at x + 11 — always east, no exceptions —
    which is fine until two cities are close. Measured on the built page at
    three widths, five pairs overlapped every time: ACCRA over ABIDJAN by
    29x11px, DOUALA over YAOUNDE by 35x12, and LAGOS across both of the first
    two. A map whose labels sit on top of each other is decoration; resolving
    them is most of what makes it an instrument.

    Greedy, in importance order — the cities with a photograph are placed first
    and keep the east side they were designed around, and the rest take the
    first free side. Deterministic, so the same dataset always draws the same
    map.
    """
    order = sorted(cities, key=lambda c: (c["slug"] not in named, c["slug"]))
    taken, out = [], {}
    for c in order:
        name = c["name"].upper()
        best = None
        for i, (side, dx, dy, anchor) in enumerate(LAB_SIDES):
            box = _lab_box(c["x"], c["y"], name, dx, dy, anchor)
            cost = sum(_overlap_area(box, t) for t in taken)
            # Ties go to the earlier side, so east stays the default where it
            # is free and the order of preference still means something.
            if best is None or cost < best[0]:
                best = (cost, i, box, dx, dy, anchor, side)
            if cost == 0:
                break
        # Least overlap, not first-free. The West African cluster — Abidjan,
        # Accra, Lagos within a few degrees of each other — can exhaust all
        # four sides, and an earlier version treated that as failure and put
        # every one of them back on the east side it was trying to escape.
        # Minimising leaves the crowded ones only as bad as they have to be.
        _, _, box, dx, dy, anchor, side = best
        taken.append(box)
        out[c["slug"]] = (dx, dy, anchor, side)
    return out


def shown(cities, countries):
    """The eight the homepage shows, out of however many the collection holds.

    Every city was printed straight into the page. Fine at nine, a growing block
    of the homepage at seventeen, and it grows again every time one is added —
    the same fault section 03 had against the atlas. Nothing is hidden by
    capping it: each card leads to its country and the closing card leads to the
    atlas, which holds them all.

    Which eight is the harder question, and "the first eight" is the wrong
    answer. In authored order that is Cape Town, Marrakech, Lagos, Nairobi,
    Accra, Addis Ababa, Kigali and Dakar — a rail that makes exactly the point
    this section exists to argue against, because the collection was built to
    show the cities a reader would not think of. Capping by region does not fix
    it either: the famous ones are spread across the regions, so a cap of two
    per region still returns six of those eight.

    So it alternates. The two wide cards are the first two with a photograph,
    because a lead card is the strongest picture and not the strongest argument.
    After that it takes one from the end of the collection, one from the front,
    one from the end — the recently added against the long established — and no
    country appears twice. What comes out is Cape Town and Marrakech leading,
    and then Asmara, Lagos, Zanzibar City, Nairobi, Luanda, Accra.
    """
    if len(cities) <= SHOW_CITIES:
        return cities

    leads = [c for c in cities if c.get("photo")][:2]
    used = {c["slug"] for c in leads}
    countries_used = {c.get("country") for c in leads}

    # A card with no photograph falls back to a typographic plate, which is the
    # right treatment in a full listing where most cards are pictures and the
    # wrong one as an eighth of the section whose whole argument is the
    # photography. So the eight are drawn from the cities that have a photograph
    # first; a plate only appears here if there are not eight of those. Asmara
    # was in this rail for exactly as long as it took to look at it, and comes
    # straight back the day it has a picture.
    rest = [c for c in cities if c["slug"] not in used and c.get("photo")]
    if len(rest) + len(leads) < SHOW_CITIES:
        rest = [c for c in cities if c["slug"] not in used]
    picked, head, tail = list(leads), 0, len(rest) - 1
    from_tail = True
    while len(picked) < SHOW_CITIES and head <= tail:
        c = rest[tail] if from_tail else rest[head]
        if from_tail:
            tail -= 1
        else:
            head += 1
        # The side only changes on a card that was actually taken. Flipping on a
        # skip as well handed the turn back to the front every time a duplicate
        # country was passed over, and since the duplicates cluster at the end —
        # Dar es Salaam behind Zanzibar, Durban behind Cape Town — the rail
        # drifted towards the cities everyone can already name.
        if c.get("country") in countries_used:
            continue
        countries_used.add(c.get("country"))
        picked.append(c)
        from_tail = not from_tail
    # One country per card is a preference, not a rule: if the collection is all
    # one or two countries the grid would come out short, and a grid with a hole
    # in it reads as something that failed to load.
    if len(picked) < SHOW_CITIES:
        for c in cities:
            if c["slug"] not in {p["slug"] for p in picked}:
                picked.append(c)
                if len(picked) == SHOW_CITIES:
                    break
    return picked


def block_citylede(countries):
    """The sentence above the city grid, and the number in it.

    It said eleven while nine were shown, and would have said eleven while eight
    are shown. It is the count of what is on the page, so the page counts it.
    """
    every = load_cities()
    n = len(shown(every, countries))
    return ('        <p class="wa-note">The continent is not only wilderness. %s '
            'cities here, each one a reason to come rather than a place to sleep '
            'before the drive out &mdash; and a first collection rather than a '
            'closed list.</p>' % _spell(n))


def rest_note(showing, total):
    """What the closing card says about the ones it is not showing.

    While the section printed every city, "These nine are a choice, and the
    choice is ours" was the whole truth. It is not once the rail is capped: a
    reader looking for Dar es Salaam has no way to know it is in the collection
    at all, and a card that quietly leaves eight cities out while claiming to be
    a choice is a smaller claim than it sounds. So it says both numbers.
    """
    if showing >= total:
        return "These %s are a choice, and the choice is ours." % _spell(showing).lower()
    return ("These are %s of the %s in the collection, and the choice is ours."
            % (_spell(showing).lower(), _spell(total).lower()))


def block_cities(countries):
    """Africa in cities — the collection, with the photography doing the work.

    The site's categories were wildlife, mountains, rainforest, coast, culture
    and food, which is a complete description of Africa's landscape and a
    stereotype of the continent: safari, nature, beach, village. Cape Town,
    Lagos, Marrakech, Nairobi, Dakar and Accra are not places to sleep before a
    game drive. They are the reason a great many people come, and they were
    represented on this page by one word in a list of twenty-seven.

    So they get a section, immediately below the hero, at the size the argument
    deserves. "Africa isn't one place" is the headline; twelve cities that look
    nothing like each other is the proof, and it has to be seen rather than
    read — which is why this block is photography first and prose second.

    A city with no photograph yet gets a typographic plate in its region's tone.
    That is a treatment, not a placeholder: it carries the same name, the same
    three words and the same link, and it is never filled with a generated
    picture of a real city. The moment a photograph lands in the dataset the
    plate becomes a photograph with no other change.
    """
    every = load_cities()
    total = len(every)
    cities = shown(every, countries)
    by_slug = dict((c.slug, c) for c in countries)
    regions = load_regions()
    rows = []
    for i, city in enumerate(cities):
        c = by_slug.get(city.get("country"))
        # A city whose country the atlas has not written up yet still belongs in
        # the collection — the owner's rule is that anywhere in Africa may be
        # added, and the atlas catches up afterwards. What it may not do is link
        # to a country page that is not there, so it leads to the atlas instead
        # and names its country from its own record. Dropping the card silently,
        # which is what this did before, meant a city could be added to the
        # dataset, verified, committed, and simply not appear.
        if c:
            key, reg = region_of(c)
            where, href = c.name, c.url
        else:
            key = city.get("region") or ""
            reg = regions.get(key)
            where, href = city.get("country_name") or "", "/places"
            if not where:
                continue                  # unnamed country, unplaceable card
        tone = reg.tone if reg else ""
        photo = city.get("photo")
        # The first two run wide. Twelve equal cards is a catalogue; a collection
        # has a lead in it.
        wide = ' data-wide="true"' if i < 2 else ''
        if photo:
            art = ('<img src="%s" width="%d" height="%d" alt="%s" loading="lazy" '
                   'decoding="async" data-provider="upload">'
                   % (esc(photo), int(city.get("photo_w") or 0), int(city.get("photo_h") or 0),
                      esc(city.get("alt") or "")))
        else:
            art = ('<span class="wa-city-plate" aria-hidden="true"><b>%s</b></span>'
                   % esc(city["name"][:2].upper()))
        rows.append(
            '      <a class="wa-city" href="%s"%s data-region="%s" data-photo="%s" '
            'style="--reg-tone:%s">'
            '<span class="wa-city-art">%s</span>'
            '<span class="wa-city-say">'
            '<b>%s</b>'
            '<span class="wa-city-where">%s</span>'
            '<span class="wa-city-line">%s</span>'
            '<span class="wa-city-note">%s</span>'
            '</span></a>'
            % (esc(href), wide, esc(key), "true" if photo else "false", esc(tone),
               art, esc(city["name"]), esc(where), esc(city["line"]), esc(city["say"])))
    # The grid is four columns and the first two cards are double, so the cards
    # occupy 2*2 + (n-2) cells. Eleven cities leave three empty, and three empty
    # cells at the end of a bordered grid read as a card that failed to render.
    # The closing card takes exactly the remainder — and it is the sentence this
    # collection needs anyway, because twelve chosen cities on a continent of
    # thousands is a beginning and should say so rather than imply completeness.
    if rows:
        span = (-len(rows) - 2) % 4 or 4
        rows.append(
            '      <a class="wa-city wa-city--rest" href="/places" data-span="%d">'
            '<span class="wa-city-say">'
            '<b>And every other place</b>'
            '<span class="wa-city-where">The atlas</span>'
            '<span class="wa-city-line">A first collection, not a closed list</span>'
            '<span class="wa-city-note">%s The atlas holds every place written '
            'up on this site, in all %s countries, with no editor standing in '
            'front of it.</span>'
            '</span></a>' % (span, rest_note(len(rows), total),
                             _spell(len(countries)).lower()))
    return "\n".join(rows)


# One line drawing per lens. Presentation, so it lives here rather than in
# lenses.json — but keyed by lens id, so a lens without an icon is a KeyError at
# build time instead of a blank button on the page.
LENS_ICONS = {
    "cities": '<path d="M3 21h18"/><path d="M5 21V9l5-3v15"/><path d="M14 21V4l5 3v14"/>'
              '<path d="M7.5 11v0M7.5 14v0M16.5 10v0M16.5 13v0"/>',
    "wildlife": '<circle cx="8" cy="8" r="1.6"/><circle cx="13" cy="6.5" r="1.6"/>'
                '<circle cx="17.5" cy="9.5" r="1.6"/>'
                '<path d="M12 12c-3 0-5 2-5 4.5S9 20 12 20s5-1 5-3.5S15 12 12 12z"/>',
    "culture": '<path d="M6 4h12v8a6 6 0 0 1-12 0z"/><circle cx="9.5" cy="10" r="1"/>'
               '<circle cx="14.5" cy="10" r="1"/><path d="M10 15c1 .8 3 .8 4 0"/>'
               '<path d="M12 18v3"/>',
    "coast": '<path d="M3 9c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>'
             '<path d="M3 14c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>'
             '<path d="M3 19c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>',
    "nature": '<path d="M3 19h18L14 6l-3.2 5.6L9 9z"/><path d="M9.5 19c0-4 2.5-6.5 6.5-7"/>',
    "food": '<path d="M5 11h14a7 7 0 0 1-7 7 7 7 0 0 1-7-7z"/>'
            '<path d="M12 8V5M9 8V6.5M15 8V6.5"/><path d="M4 21h16"/>',
    "history": '<path d="M4 20h16M6 20V11h12v9"/><path d="M4 11 12 5l8 6"/>'
               '<path d="M11 20v-4h2v4"/>',
    "adventure": '<path d="M6 4h4v9l6 3v4H6z"/><path d="M10 13h3"/>',
}

# EACH GLYPH'S INK, CENTRED IN ITS OWN BOX.
#
# Eight drawings made one at a time are eight drawings centred by eye, and by
# eye is not centred: measured in the browser, the ink of every one of them sat
# below the middle of the 24-box, and the three waves of `coast` sat two whole
# units low — 1.8px inside a 44px disc, which is exactly the kind of thing that
# reads as "the icons are not aligned" without a reader being able to say why.
#
# The numbers are the measured offset from the union of each glyph's geometric
# bounding boxes to the centre of the box, so they are corrections rather than
# taste. Re-measure before changing a drawing:
#
#   union of svg.children getBBox() -> centre -> (12 - cx, 12 - cy)
#
# Geometric boxes, so the stroke is not counted; the stroke is the same weight
# on every glyph, so it moves all eight equally and cancels.
LENS_INK = {
    "cities": (0, -0.5),
    "wildlife": (-0.75, -0.45),
    "culture": (0, -0.5),
    "coast": (0, -2),
    "nature": (0, -0.5),
    "food": (0, -1),
    "history": (0, -0.5),
    "adventure": (1, 0),
}


def lens_icon(key):
    """-> the glyph's markup, nudged onto the centre of its box.

    A KeyError here is the point: a lens with a drawing and no measurement is a
    glyph nobody has looked at, and it should stop the build rather than ship
    half a pixel off in a row of eight.
    """
    dx, dy = LENS_INK[key]
    if not dx and not dy:
        return LENS_ICONS[key]
    return ('<g transform="translate(%s %s)">%s</g>'
            % (("%g" % dx), ("%g" % dy), LENS_ICONS[key]))


def block_experiences(countries):
    """The picker, generated from the lenses rather than typed beside them.

    It was eight hand-written buttons, and two of them — `rainforest` and
    `adventure` — were not lenses at all. Nothing declared them, so pressing
    either filtered the destinations grid to nothing and the page answered a
    question with an empty row. Nobody noticed because the answer panel above
    still spoke: the recommendation came from picks.json and the filter came
    from the lens vocabulary, and the two had quietly stopped being the same
    list.

    So the buttons are the lenses now, in the lenses' own order, with the
    country each one recommends taken from picks.json. A lens with no pick, or a
    pick naming a country that is not published, raises here rather than
    shipping a button that leads nowhere.
    """
    lenses = load_lenses()
    picks = load_picks()
    live = {c.slug for c in countries}
    out = []
    for key, lens in lenses.items():
        pick = picks.get(key)
        if not pick:
            raise ValueError("lens %r has no pick in picks.json" % key)
        if pick.get("country") not in live:
            raise ValueError("lens %r recommends %r, which is not published"
                             % (key, pick.get("country")))
        out.append(
            '<button class="wa-tag" type="button" data-exp="%s" data-slug="%s" data-line="%s">'
            '<svg viewBox="0 0 24 24" aria-hidden="true">%s</svg>%s</button>'
            % (esc(key), esc(pick["country"]), esc(lens["line"]),
               lens_icon(key), esc(lens["title"])))
    return "".join(out)


def block_wants(countries):
    """The filter bar over the destinations grid, from the same eight lenses.

    This was six hand-written buttons and the picker in the hero was eight, and
    neither list knew about the other. Two of the hero's — `rainforest` and
    `adventure` — were not lenses at all, so they filtered nothing; two of the
    lenses the bar did offer had since been renamed. Four copies of one
    taxonomy, none of them derived. There is one now.
    """
    lenses = load_lenses()
    return "\n      ".join(
        '<button class="wa-want" type="button" data-want="%s" data-line="%s">'
        '<i>%s</i><b>%s</b></button>'
        % (esc(key), esc(lens["filterline"]), esc(lens["verb"]), lens["label"])
        for key, lens in lenses.items())


def block_feel(countries):
    """What do you want to feel — the eight lenses as desire rather than filter.

    The page could tell you what Africa is and could not tell you why to go. It
    opened on "Africa isn't one place", and then asked a visitor who did not yet
    want to travel to browse a comparison engine. Twenty-two countries written up
    on the same twenty-seven categories is the right answer to the second
    question a traveller has. This section is the first one.

    The sentence under each heading is authored — it is the one field in
    lenses.json that is written rather than derived, and the note there says so.
    Everything beside it is counted: how many countries lead on that lens, and
    which, out of their own `calls`. So the line that promises a feeling is
    printed next to the places it is true of, and a lens no country calls is not
    offered at all, because a feeling with nowhere to have it is the one kind of
    copy this site cannot print.
    """
    lenses = load_lenses()
    leads = {}
    for c in countries:
        for call in c.calls:
            leads.setdefault(call, []).append(c)
    out = []
    for key, lens in lenses.items():
        who = leads.get(key) or []
        if not who:
            continue                      # nowhere to have it, so it is not offered
        names = sorted(x.name for x in who)
        out.append(
            # The builder's own decoder reads `w=` out of the hash query, so
            # this hands it a want and it opens on "When?" instead of on the
            # question this card has already answered. `#/<lens>` was the first
            # form tried and the decoder ignores it silently — the page loaded
            # on question one as though the card had never been clicked, which
            # is a link that looks like it carries a choice and does not.
            '      <a class="wa-feel%s" href="/journey#/?w=%s" data-lens="%s"%s>%s'
            '<span class="wa-feel-in">'
            '<span class="wa-feel-say">%s</span>'
            '<span class="wa-feel-what">%s</span>'
            '<span class="wa-feel-n">%s %s</span></span></a>'
            % (" is-lit" if lens.get("photo") else "", esc(key), esc(key),
               # No data-photo any more. The words sit on the page's own ground
               # below the picture rather than on the picture, so the contrast
               # pass can read the colour out of the cascade and does not need
               # to be told to skip this. Measured by the suite, not by hand.
               "",
               ('<img class="wa-feel-art" src="%s" alt="" width="1600" '
                'height="1067" loading="lazy" decoding="async" '
                'data-provider="upload" style="--fj-feel-pos:%s">'
                % (esc(lens["photo"]), esc(lens.get("photo_pos") or "50% 50%")))
               if lens.get("photo") else "",
               esc(lens.get("feel") or lens["line"]),
               lens["label"],
               # Spelled all the way, not figures above twenty. This card is a
               # sentence — "twenty-six countries lead on this" — and it had its
               # own cutoff at 20 that _spell does not have, so the two disagreed
               # from the twentieth country onwards.
               _spell(len(names)).lower(),
               "country leads on this" if len(names) == 1 else "countries lead on this"))
    return "\n".join(out)


def block_moments():
    """Four photographs, at the size a photograph has to be to do any work.

    Section 01 asks what you want to feel and answers in type, eight ways, so
    that a reader who does not yet know can find the word for it. This answers
    four of the same question in pictures, because past a certain point the
    argument "Africa is not one place" cannot be made in prose to somebody who
    has only ever seen one Africa on television.

    Each card carries the lens it belongs to and hands the journey builder that
    want, exactly as the feel cards do — so the picture is a way in rather than
    decoration, and there is no card here you cannot act on.

    The alt text describes the frame and stops. Nothing here says who anybody in
    a photograph is, and nothing names a country: three of the four cannot be
    placed with certainty, and moments.json sets out why the fourth is not named
    either.
    """
    lenses = load_lenses()
    out = []
    for m in load_moments():
        lens = lenses.get(m.get("lens"))
        if not lens or not m.get("photo"):
            continue          # a picture with no way in is decoration
        out.append(
            '      <a class="wa-moment" href="/journey#/?w=%s" data-lens="%s">'
            '<span class="wa-moment-art">'
            '<img src="%s" width="%d" height="%d" alt="%s" loading="lazy" '
            'decoding="async" data-provider="upload"></span>'
            '<span class="wa-moment-say"><b>%s</b><i>%s</i></span></a>'
            % (esc(m["lens"]), esc(m["lens"]), esc(m["photo"]),
               int(m.get("photo_w") or 0), int(m.get("photo_h") or 0),
               esc(m.get("alt") or ""), esc(m.get("line") or ""),
               esc(m.get("label") or lens["label"])))
    return "\n".join(out)


def block_motion():
    """The window under the hero: three tracks, and a frame that advances.

    Built for footage that does not exist yet. Every shot carries a clip and
    every clip is null, so today the frame cross-fades photographs; the moment a
    clip is filled in that shot plays instead, with no other change. It is the
    same arrangement as a city plate becoming a photograph, and for the same
    reason — an empty slot should be a treatment rather than a gap.

    What it deliberately does not have is a play triangle. A play triangle is a
    promise of video, and there is none here yet. The control is a pause, which
    content that moves for longer than five seconds needs regardless.

    The first shot of the first track is eager: this sits directly under the
    hero and is the first picture after it. Everything else is lazy, because
    twenty photographs on load is the cost of a video without any of the
    benefit.
    """
    tracks = load_motion()
    if not tracks:
        return "      "
    rails, frames = [], []
    for ti, t in enumerate(tracks):
        shots = [s for s in t.get("shots") or [] if s.get("photo") or s.get("clip")]
        if not shots:
            continue                # a track with nothing to show is not offered
        rails.append(
            '<button class="wa-mo-pick" type="button" data-track="%s" aria-pressed="%s">'
            '<b>%s</b><i>%s</i></button>'
            % (esc(t["slug"]), "true" if not ti else "false",
               esc(t.get("label") or t["slug"]), esc(t.get("line") or "")))
        for si, s in enumerate(shots):
            first = not ti and not si
            if s.get("clip"):
                # No `loop`. The rail moves on when the clip ends, and a looping
                # video never fires `ended` — with it set, the film played for
                # ever and the cities behind it stopped changing.
                #
                # VP9 first: every browser that takes the mp4 takes the WebM too,
                # and the WebM is about a third smaller. The mp4 is the fallback
                # for older Safari. The .webm is found from the .mp4's name rather
                # than stored, so the data keeps naming one clip.
                web = s["clip"].rsplit(".", 1)[0] + ".webm"
                # `none`, for every piece including the first. The load event
                # waits on media the page has asked for, and this track is a
                # sixteen-piece film: at "auto" the first piece put a megabyte in
                # front of the load event, and at "metadata" all sixteen fetched
                # their headers at once. Both timed out a 30s navigation, which is
                # how each was found. So the markup asks for nothing, the poster
                # holds the frame, and show() promotes the current piece and the
                # one after it as the band is actually watched.
                # The poster is deferred with the same care as the video, and
                # for the same reason. `poster` has no lazy equivalent — the
                # browser fetches it whether the shot is visible or not — and
                # fifteen invisible posters is four megabytes on the page load
                # of every visitor. Only the first carries one in the markup;
                # show() hands the rest theirs as they come round.
                media = ('<video %s="%s" muted playsinline preload="none" '
                         'aria-label="%s">'
                         '<source src="%s" type="video/webm">'
                         '<source src="%s" type="video/mp4">'
                         '</video>'
                         % ("poster" if first else "data-poster",
                            esc(s.get("photo") or ""), esc(s.get("alt") or ""),
                            esc(web), esc(s["clip"])))
            else:
                media = ('<img src="%s" width="%d" height="%d" alt="%s" '
                         'loading="%s" decoding="async" data-provider="upload">'
                         % (esc(s["photo"]), int(s.get("photo_w") or 0),
                            int(s.get("photo_h") or 0), esc(s.get("alt") or ""),
                            "eager" if first else "lazy"))
            frames.append(
                '      <figure class="wa-mo-shot" data-track="%s"%s>%s'
                '<figcaption>%s</figcaption></figure>'
                % (esc(t["slug"]), ' data-on="true"' if first else "",
                   media, esc(s.get("say") or "")))
    # The window and the rail are siblings, not nested. The rail was inside the
    # frame at first and sat on top of the caption, so every shot's name was
    # underneath the controls that changed it.
    # Two blocks, not one. The rail belongs with the copy on the dark side of the
    # band and the window is cropped by the band on three edges, so they cannot
    # be siblings in one container any more.
    return ('      <div class="wa-mo-window">\n' + "\n".join(frames)
            + '\n      </div>', 
            '      <div class="wa-mo-rail" role="group" '
            'aria-label="Choose what the window shows">'
            + "".join(rails) + "</div>")


def block_momentsay():
    """The sentence over the four photographs, enumerating them.

    A sentence that lists what is below it is a sentence that goes stale the
    moment the list changes, and this page has removed several of those. The
    poetry is authored — each clause is written to its own frame and lives in
    moments.json beside the photograph it describes — and the enumeration is
    not, so a fifth moment rewrites the prose as well as the grid.
    """
    clauses = [m.get("clause") for m in load_moments()
               if m.get("clause") and m.get("photo")]
    if not clauses:
        return "      "
    # "or", not "and": these are four things one of which will be yours, not
    # four things you are promised. _and_list joins the other way.
    parts = [esc(c) for c in clauses]
    listed = parts[0] if len(parts) == 1 else \
        ", ".join(parts[:-1]) + " or " + parts[-1]
    return ("      In Africa, the moment you remember for the rest of your life "
            "might be %s.\n      <span class=\"wa-moment-turn\">You don&rsquo;t know "
            "your moment yet. That is why you have to come.</span>" % listed)


def block_seasons(countries):
    """Twelve months, and who is at their best in each.

    The destinations grid already carries a month filter, and it shows a count
    per month and nothing else. That is a control. This is the argument the
    control implies and the page never made: there is no month in which Africa
    has nothing to offer, and a reader whose leave is fixed in April is not out
    of luck.

    Nothing here is typed. The count is the countries whose own `months` include
    that month, and the names are the ones for which that month matters most —
    ordered by how few good months the country has altogether, so a place with a
    five-month window is named ahead of one that is good all year. That is a
    real distinction rather than an alphabetical cut: April belongs to the
    Seychelles in a way that October, when fifteen countries are open, belongs
    to nobody in particular.
    """
    # THE SHAPE OF THE YEAR IS THE ARGUMENT AND IT WAS THE ONE THING NOT DRAWN.
    # Twelve cells each printed a number spelled out in words — "Thirty-eight",
    # "Sixteen" — which is the site's voice and is also unreadable as a
    # quantity: nothing on the section showed that January is crowded and April
    # is thin, which is exactly what the lede above it claims. Each month now
    # carries a measure against the busiest, so the year has a silhouette before
    # a word of it is read. The bar is the same count as the words, drawn.
    counts = {i: sum(1 for c in countries if i in c.months) for i in range(1, 13)}
    top = max(counts.values()) or 1
    lo = min(n for n in counts.values() if n) if any(counts.values()) else 0
    rows = []
    for i, name in enumerate(MONTHS, 1):
        who = sorted((len(c.months), c.name, c.url) for c in countries if i in c.months)
        if not who:
            continue      # a month with nowhere to go is not offered
        lead = who[:3]
        rest = len(who) - len(lead)
        names = _and_list('<a href="%s">%s</a>' % (esc(u), esc(n)) for _l, n, u in lead)
        n = len(who)
        # The two ends of the year are marked because the lede names them, and a
        # sentence that says "the quietest is April" beside twelve identical
        # cells is a sentence the reader has to take on trust.
        mark = (" is-top" if n == top else (" is-low" if n == lo else ""))
        rows.append(
            '      <div class="wa-season%s" data-month="%d">'
            '<b>%s</b>'
            '<span class="wa-season-n">%s<i>%d</i></span>'
            '<span class="wa-season-bar" aria-hidden="true">'
            '<span style="width:%.1f%%"></span></span>'
            '<p class="wa-season-who">%s%s</p></div>'
            % (mark, i, esc(name[:3]), esc(_spell(n)), n, 100.0 * n / top,
               names,
               (", and %s more" % _spell(rest).lower()) if rest else ""))
    return "\n".join(rows)


def block_seasonsay(countries):
    """The one sentence the twelve months add up to, counted rather than typed."""
    per = {i: sum(1 for c in countries if i in c.months) for i in range(1, 13)}
    live = {i: n for i, n in per.items() if n}
    if not live:
        return "      "
    lo = min(live.values())
    quiet = [MONTHS[i - 1] for i, n in sorted(live.items()) if n == lo]
    return ("      No month is a bad month everywhere. The quietest is %s, and %s "
            "countries are at their best in it; the busiest is %s, with %s."
            % (_and_list(quiet), _spell(lo).lower(),
               _and_list([MONTHS[i - 1] for i, n in sorted(live.items())
                          if n == max(live.values())]),
               _spell(max(live.values())).lower()))


def block_expcards(countries):
    """The experience cards, with the counts derived rather than typed.

    Each said "11 of 22 countries lead on this" as a literal beside a list that
    is generated, so every count was a hostage to the next edit of the dataset —
    and after the taxonomy changed under them, four of the six were wrong.
    """
    lenses = load_lenses()
    out = []
    for key, lens in lenses.items():
        n = sum(1 for c in countries if key in c.calls)
        icon = lens_icon(key)
        art = ('<span class="wa-ico" aria-hidden="true"><svg viewBox="0 0 24 24">%s</svg></span>'
               % icon)
        body = ('<div><b>%s</b><span>%s</span><i class="wa-exp-n">%s</i></div>'
                % (lens["label"], esc(lens["examples"]),
                   ("%d of %d countries lead on this" % (n, len(countries))) if n
                   else ("Written up in all %d &mdash; no one leads it" % len(countries))))
        # A lens nothing leads on is not a filter — pressing it would empty the
        # grid. It becomes a link to everywhere instead, which is the honest
        # answer to "show me this" when no country claims it.
        if n:
            out.append('<button class="wa-exp" type="button" data-want="%s" aria-pressed="false">'
                       '%s%s</button>' % (esc(key), art, body))
        else:
            out.append('<a class="wa-exp wa-exp--all" href="/places">%s%s</a>' % (art, body))
    return "\n      ".join(out)


DETAIL = os.path.join(ROOT, "tourism", "atlas-detail.json")


def _detail():
    d = read_json(DETAIL, {})
    if not d:
        raise ValueError("tourism/atlas-detail.json is missing — run tools/atlas_detail.py")
    return d


def block_mapunder(countries):
    """What is under the countries: ocean graticule, then water on the land.

    Order matters and is the reason this is two blocks rather than one. The
    graticule belongs under everything, because a meridian drawn over Algeria is
    a scratch on the page. Lakes and rivers belong over the country fills and
    under the boundaries, because a river is a feature of the ground and a
    border is an argument about it — the Nile crosses Egypt, it does not stop at
    Sudan. SVG has no z-index, so the only way to say that is the document.
    """
    d = _detail()
    out = ['<g class="wa-map-grat wa-map-grat--minor" aria-hidden="true">']
    for g in d["graticule"]:
        if g["kind"] == "minor":
            out.append('<path d="%s"/>' % g["d"])
    out.append('</g><g class="wa-map-grat" aria-hidden="true">')
    for g in d["graticule"]:
        if g["kind"] != "minor":
            out.append('<path d="%s"/>' % g["d"])
    out.append('</g>')
    # The labels sit in the ocean where the lines leave the frame, small enough
    # that they are a texture until you look for them.
    out.append('<g class="wa-map-coord" aria-hidden="true">')
    seen = set()
    for g in d["graticule"]:
        x, y = g["at"]
        vw, vh = d["fit"]["view"][2], d["fit"]["view"][3]
        if g["kind"] == "minor" or not (12 < x < vw - 12 and 12 < y < vh - 12):
            continue
        key = (g["label"], round(x / 40), round(y / 40))
        if key in seen:
            continue
        seen.add(key)
        out.append('<text x="%.1f" y="%.1f">%s</text>' % (x + 4, y - 4, esc(g["label"])))
    out.append('</g>')
    return "".join(out)


MIN_HIT = 60.0                 # narrower than this and the shape is not clickable
HIT_R = "34.0"                 # so a 68-unit circle goes behind it


def _extent(d):
    """How wide and how tall a path is, in map units."""
    ps = [(float(x), float(y)) for x, y in
          re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", d)]
    if not ps:
        return 0.0, 0.0
    xs = [p[0] for p in ps]
    ys = [p[1] for p in ps]
    return max(xs) - min(xs), max(ys) - min(ys)


def block_lede(countries):
    """The one sentence under the headline, and the number in it.

    It said twenty-two for as long as there were twenty-two, and then for a
    while after there were not. A count typed into copy is a claim with no
    owner: nothing recomputes it, nothing checks it, and it is wrong quietly.
    """
    return ('<p class="wa-lede">%s countries, written up one place at a time, '
            'by people who go there.</p>' % _spell(len(countries)))


def block_mapsvg(countries):
    """The map's own description — the only thing a screen reader gets of it.

    It said twenty-two while fifty-four shapes were filled in, which is the
    worst place on the page for a stale number: everybody else can see the map
    and check, and the one person relying on this sentence cannot.
    """
    n = len(countries)
    rest = ("Western Sahara is drawn in outline"
            if n >= IN_AFRICA else
            "the rest of the continent is drawn in outline, and can be booked "
            "through an operator who lives there")
    return ('        <svg class="wa-map-svg" viewBox="0 0 1000 1060" role="img" '
            'aria-label="Map of Africa. The %d countries written up on this site '
            'are filled in; %s. The same %d are listed as buttons directly below '
            'this map.">' % (n, rest, n))


def block_capafrica(countries):
    """The caption the window shows before a country is chosen.

    It sat outside every marker, one line above the block that generates the
    other fifty-four captions, and it was the loudest number on the page: the
    first thing said about the continent, and it said twenty-two for as long as
    it took to notice.
    """
    return ('          <div class="wa-win-cap" data-slug="africa" data-on="true">'
            '<span class="wa-win-region">The continent</span><b>Africa</b>'
            '<span class="wa-win-tag">%s</span>'
            '<span class="wa-win-op">Choose one on the map, or below</span>'
            '<a class="wa-win-go" href="#destinations">See all destinations &rarr;</a></div>'
            % esc(all_of_them(countries)))


def block_destlede(countries):
    """Section 06's headline. 'All of them live' is a claim about the roster, so
    the roster is where the number comes from."""
    return ('        <h2>%s countries, <em>all of them live</em>.</h2>'
            % _spell(len(countries)))


def block_readslede(countries):
    """Section 12's note. One portrait per country, so it is the same count —
    and story.py writes the portraits, so the two cannot be allowed to differ."""
    return ('        <p class="wa-note">%s long reads, one per country, each '
            'built out of what that country says about itself rather than '
            'written about it. One from each region below.</p>'
            % _spell(len(countries)))


def block_maplive(countries):
    """The countries themselves: the scenery, then the ones you can go to.

    This was thirty kilobytes of hand-pasted SVG, which was fine while the
    roster was twenty-two and stopped being fine the moment it was not. A
    country added to tourism/countries/ went onto every list on the site and
    stayed part of the unnamed background on the one thing the page is built
    around, with nothing to say it had — the shape was drawn, so nothing looked
    broken. Generating it means the map cannot disagree with the atlas.

    Two details that are easy to lose in a rewrite and expensive to lose in
    use. A shape narrower than sixty units cannot be hit with a finger — Rwanda
    is twenty-five across — so it gets a circle behind it at the label anchor,
    which is a pointer target and not a drawn thing. And the island states are
    a dot rather than a two-pixel outline, because at continental scale their
    true shape is smaller than the stroke that would draw it.
    """
    with open(os.path.join(ROOT, "tourism", "map.json"), encoding="utf-8") as fh:
        m = json.load(fh)

    # What each country leads on, and what its region leads on, carried onto the
    # shape itself. Pressing WILDLIFE used to fly the map to one country and
    # leave the other fifty-three exactly as they were, which answers "where is
    # the single best place" — a question nobody asked — instead of "where does
    # this come alive", which is the one on the button. Colouring needs to know
    # each country's own claim, so the claim travels with the shape rather than
    # in a second payload the page would have to fetch and keep in step.
    calls = {c.slug: list(c.calls or []) for c in countries}
    region_of = {c.slug: (c.region or "?") for c in countries}
    tally = {}
    for slug, ks in calls.items():
        r = tally.setdefault(region_of[slug], {"n": 0, "lens": {}})
        r["n"] += 1
        for k in ks:
            r["lens"][k] = r["lens"].get(k, 0) + 1
    region_leads = dict(
        (r, sorted(k for k, n in v["lens"].items() if n / float(v["n"]) >= 0.5))
        for r, v in tally.items())

    def lens_attrs(slug):
        mine = calls.get(slug) or []
        near = [k for k in region_leads.get(region_of.get(slug, "?"), [])
                if k not in mine]
        return ' data-calls="%s" data-near="%s"' % (
            esc(" ".join(sorted(mine))), esc(" ".join(near)))

    out = ['<g class="wa-map-rest" aria-hidden="true">']
    for row in m.get("rest") or []:
        out.append('\n<path d="%s"><title>%s</title></path>'
                   % (row["d"], esc(row.get("n") or "")))
    out.append('\n</g>')
    for row in sorted(m.get("live") or [], key=lambda r: r["slug"]):
        w, h = _extent(row["d"])
        hit = ""
        if row.get("at") and min(w, h) < MIN_HIT:
            hit = ('<circle class="wa-map-hit" cx="%s" cy="%s" r="%s"/>'
                   % (row["at"][0], row["at"][1], HIT_R))
        out.append('\n<a tabindex="-1" class="wa-map-live" data-tier="%s" '
                   'data-slug="%s" data-name="%s" data-tag="%s"%s href="%s">'
                   '%s<path d="%s"/><title>%s &#8212; %s</title></a>'
                   % (esc(row.get("tier") or "live"), esc(row["slug"]),
                      esc(row["name"]), esc(row["tag"]),
                      lens_attrs(row["slug"]), esc(row["href"]),
                      hit, row["d"], esc(row["name"]), esc(row["tag"])))
    for row in sorted(m.get("marks") or [], key=lambda r: r["slug"]):
        x, y = row["at"]
        out.append('\n<a tabindex="-1" class="wa-map-live wa-map-mark" '
                   'data-tier="%s" data-slug="%s" data-name="%s" data-tag="%s"%s '
                   'href="%s"><circle class="wa-map-hit" cx="%s" cy="%s" r="%s"/>'
                   '<circle cx="%s" cy="%s" r="12"/>'
                   '<title>%s &#8212; %s</title></a>'
                   % (esc(row.get("tier") or "live"), esc(row["slug"]),
                      esc(row["name"]), esc(row["tag"]),
                      lens_attrs(row["slug"]), esc(row["href"]),
                      x, y, row.get("r", 36), x, y,
                      esc(row["name"]), esc(row["tag"])))
    return "".join(out) + "\n"


def block_mapover(countries):
    """Water, then journeys, then cities, then the compass.

    The cities are the layer that changes what the map is for. A map with
    countries on it is a picture of a continent; a map that knows Lagos is
    somewhere you can go from.
    """
    d = _detail()
    out = []
    # The coast, as its own stroke. Stroking the country polygons harder cannot
    # produce this: an internal border carries the line on both sides and reads
    # as a hairline, a coast carries it on one and reads as an edge.
    out.append('<g class="wa-map-coast" aria-hidden="true">')
    for path_d in d["coast"]:
        out.append('<path d="%s"/>' % path_d)
    out.append('</g>')
    out.append('<g class="wa-map-water" aria-hidden="true">')
    for path_d in d["rivers"]:
        out.append('<path class="wa-map-river" d="%s"/>' % path_d)
    for path_d in d["lakes"]:
        out.append('<path class="wa-map-lake" d="%s"/>' % path_d)
    out.append('</g>')

    # Madagascar is not adrift. It keeps its geographic separation and gets the
    # channel drawn across it, which is a crossing rather than a gap.
    out.append('<path class="wa-map-strait" aria-hidden="true" d="%s"/>' % d["strait"])

    # The island states are markers because their outline is a pixel here. Two
    # unexplained circles in open water is worse on a chart than leaving them
    # off, so they are named like everything else that has a reason to be there.
    out.append('<g class="wa-map-isles" aria-hidden="true">')
    for i in d["islands"]:
        out.append('<text x="%.1f" y="%.1f">%s</text>'
                   % (i["x"] - 13, i["y"] + 4, esc(i["name"].upper())))
    out.append('</g>')

    # Journeys. Drawn as arcs rather than segments, because a straight line
    # between two points on this projection is not the way anybody travels.
    out.append('<g class="wa-map-routes" aria-hidden="true">')
    for r in d["routes"]:
        out.append('<path class="wa-map-route" data-route="%s" d="%s"><title>%s</title></path>'
                   % (esc(r["slug"]), r["d"], esc(r["name"] + " — " + r["line"])))
    out.append('</g>')

    # Cities. The three with a photograph in the collection are named on the
    # map; the rest are points until you ask. Labelling eleven would put type
    # across half of West Africa.
    named = {c["slug"] for c in load_cities() if c.get("photo")}
    urls = dict((x.slug, x.url) for x in countries)
    out.append('<g class="wa-map-cities">')
    sides = place_labels(d["cities"], named)
    for c in d["cities"]:
        lead = ' data-lead="true"' if c["slug"] in named else ''
        # A point that cannot be pressed is decoration. These are places with a
        # page behind them, so they are links — which also puts them in the tab
        # order and gives a screen reader something to announce.
        out.append('<a class="wa-map-city" href="%s"%s data-slug="%s">'
                   % (esc(urls.get(c["country"], "/places")), lead, esc(c["slug"])))
        dx, dy, anchor, side = sides[c["slug"]]
        out.append('<g class="wa-map-city-in" data-slug="%s">'
                   '<circle class="wa-map-city-dot" cx="%.1f" cy="%.1f" r="3.4"/>'
                   '<circle class="wa-map-city-ring" cx="%.1f" cy="%.1f" r="7"/>'
                   '<text class="wa-map-city-say" x="%.1f" y="%.1f"'
                   ' text-anchor="%s" data-side="%s">%s</text>'
                   '<title>%s</title></g>'
                   % (esc(c["slug"]), c["x"], c["y"], c["x"], c["y"],
                      c["x"] + dx, c["y"] + dy, anchor, side,
                      esc(c["name"].upper()), esc(c["name"])))
        out.append('</a>')
    out.append('</g>')

    r = d["rose"]
    out.append(
        '<g class="wa-map-rose" aria-hidden="true" transform="translate(%.1f %.1f) rotate(%.2f)">'
        '<circle r="%.1f"/><circle r="%.1f" class="wa-map-rose-in"/>'
        '<path d="M0 -%.1f L4 0 L0 %.1f L-4 0 Z"/>'
        '<path class="wa-map-rose-x" d="M-%.1f 0 H%.1f"/>'
        '<text y="-%.1f">N</text></g>'
        % (r["cx"], r["cy"], r["rotate"], r["r"], r["r"] * 0.62,
           r["r"] * 0.78, r["r"] * 0.78, r["r"], r["r"], r["r"] + 5))
    return "".join(out)


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


def block_plan(countries):
    """What actually happens after an enquiry, rather than what sells well.

    This section made four claims and three of them were false:

      "The person who answers your enquiry is in the country you are asking
      about"  —  every enquiry on this site opens a mailto to one address, in
      Douala. Ask about Kenya and a Cameroonian operator reads it. 038 put a bar
      on /contact saying exactly that; this paragraph, two screens above the
      button, said the opposite.

      "Meet the local operator responsible for your destination"  —  there are
      three operators for twenty-two countries.

      "Licensed, local, and working in the language you booked in"  —  nothing in
      this dataset records a licence, and nothing records a language.

    The fourth, "Return home with more than photographs", is not false because
    it does not say anything. It is gone with the rest.

    What replaces them is the same shape — numbered steps, two of them links —
    counted from operators.json, so the promise cannot outgrow the company.
    """
    ours = [c for c in countries if c.operator]
    host = ([c for c in ours if c.operator.url.startswith("/")] or ours)[0]
    rest = len(countries) - len(ours)
    names = _and_list([c.name for c in ours])

    # THREE THINGS THAT ARE NOT THE SAME THING, AND THIS SENTENCE KEEPS THEM APART.
    #   we own the company        3   Cameroon, Uganda, Namibia
    #   we have written it up    19   the rest of the atlas
    #   we can book it           54   the continent, through local partners
    # Collapsing any two of those is the overclaim this page has already been
    # corrected for once: 038 deleted "meet the local operator responsible for
    # your destination" because there were three operators for twenty-two
    # countries. Coverage is a real and much larger claim than ownership, and it
    # is worth making — but as its own clause, not by widening the first one.
    # The clause this replaces ended "booked through somebody else, which we
    # say before you write, not after" — a disclosure worn as a virtue, in the
    # sentence that is supposed to make somebody want to go. What is true and
    # stronger: the ground journey is ours on all fifty-four, and in three the
    # company on the ground is ours as well. The ownership claim stays exactly
    # as narrow as it was; it is the coverage claim that has grown, and it is
    # the one worth leading with.
    note = ('We take you anywhere on the continent: your vehicle, your driver '
            'for the whole journey, and a coordinator holding the days '
            'together. In %s the company on the ground is ours too &mdash; we '
            'own it, and the guide on the day works for it. The other %s are '
            'written up to the same twenty-seven categories, and travelled the '
            'same way.' % (names, _spell(rest).lower()))

    steps = [
        ('/journey', 'Discover',
         'Four questions, or a sentence in your own words, and the atlas opens '
         'somewhere rather than everywhere.', 'Start with a question'),
        ('/compare', 'Compare',
         'Any two of the %s, through the same %s categories in the same order, '
         'so the difference is the countries and not their marketing.'
         % (_spell(len(countries)).lower(),
            _spell(len(read_json(CATEGORY_FILE, {}).get("categories", []))).lower()),
         'Put two side by side'),
        # Was /contact — Kamerun's desk — with "Enquiries reach Kamerun in Buea
        # and Douala. For Cameroon they are the operator; for the other
        # fifty-one they will tell you who is." Wrong destination and the old
        # defensive framing in one step: the last rung of how-it-works handed
        # the whole continent to one country's office and then explained that
        # for the rest we would find somebody.
        ('/enquire', 'Ask',
         'Send us the journey and we come back with what can be arranged on '
         'your dates, in writing, in US dollars. In %s the company on the '
         'ground is ours as well.'
         % _and_list([c.name for c in countries if c.operator]),
         'Begin your journey'),
    ]
    out = []
    for i, (url, title, text, go) in enumerate(steps, 1):
        out.append('      <a class="wa-step wa-step--go" href="%s"><i>%02d</i>'
                   '<b>%s</b><p>%s</p><span class="wa-step-go">%s &rarr;</span></a>'
                   % (esc(url), i, esc(title), text, esc(go)))
    # The last step is the only one that is not a link, because it is the only
    # one that happens away from this website.
    # "Where it is not, we are not going to describe a day run by people we
    # have not named" was the last line of the how-it-works list — a refusal,
    # at the exact point the reader is imagining the trip. What is true and
    # better is that the ground is ours everywhere and in three countries the
    # guide is ours as well.
    out.append('      <div class="wa-step"><i>%02d</i><b>Travel</b><p>Your driver '
               'and your coordinator are ours for the whole journey, wherever it '
               'goes. In %s the guide on the day works for our own company '
               'there.</p></div>'
               % (len(steps) + 1,
                  _and_list(['%s in %s' % (esc(c.operator.name), esc(c.name))
                             for c in ours])))
    return note, "\n".join(out)


def block_planfork(countries):
    """THE HOMEPAGE NEVER SAID THERE WERE TWO KINDS OF JOURNEY.

    Section 11 went straight into four numbered steps that all begin at
    /journey, which builds a journey inside ONE country. A reader who wants to
    cross several was never told the other road exists — the door to Trans
    Afrique is six sections earlier and says nothing about how either is
    priced, and /how-it-works is a page nobody on the homepage was sent to.

    So the section opens on the fork instead of on step one. Two ways, the
    shape of each one's price under it, and the page that holds both.

    EVERY FIGURE IS READ, NOT TYPED. The day rate comes from rates.json and the
    lowest crossing band from transafrique.json — the same files /how-it-works
    reads. Three copies of a price is three things to forget, and this
    repository has been caught by exactly that before.
    """
    rates = read_json(os.path.join(ROOT, "tourism", "rates.json"), {})
    tf = read_json(os.path.join(ROOT, "tourism", "transafrique.json"), {})
    tiers = rates.get("tiers") or []
    routes = tf.get("routes") or []
    if not tiers or not routes:
        return "      "
    day = min(t["rate"] for t in tiers)
    band = min(r["low"] for r in routes)
    doors = [
        ("/journey", "One country, in depth",
         "A vehicle and a driver of your own, and days built around what you "
         "came for. Most journeys are this.",
         "From $%s" % "{:,}".format(int(day)), "per vehicle, per day"),
        ("/trans-afrique", "Several, by road",
         "%s crossings, a fortnight to two months, with a team that travels "
         "the whole way." % _spell(len(routes)),
         "From $%s" % "{:,}".format(int(band)), "for the whole crossing"),
    ]
    out = []
    for i, (url, title, say, price, unit) in enumerate(doors, 1):
        out.append('      <a class="wa-fork-door" href="%s"><i>%02d</i>'
                   '<b>%s</b><p>%s</p>'
                   '<span class="wa-fork-price">%s<em>%s</em></span></a>'
                   % (esc(url), i, esc(title), esc(say), esc(price), esc(unit)))
    out.append('      <p class="wa-fork-note">The two are quoted differently &mdash; '
               'a country by the day, a crossing as a whole. '
               '<a href="/how-it-works">Both, side by side &rarr;</a></p>')
    return "\n".join(out)


def block_plannote(countries):
    return '        <p class="wa-note">%s</p>' % block_plan(countries)[0]


def block_plansteps(countries):
    return block_plan(countries)[1]


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
        '<b>%s more countries</b><span class="wa-op-base">Your journey here, run by Afrinkong</span>'
        '<p>We own the companies on the ground in %s. The other %s are written '
        'up to the same twenty-seven categories by the same hands, so any two '
        'countries here can be compared on the same terms &mdash; and travelled '
        'the same way, with a vehicle, a driver and a coordinator of ours.</p>'
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
              esc(all_of_them(countries)),
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


def block_regiontone():
    """The hero window's fill, one rule per region, out of regions.json.

    These five rules carried a comment saying they were generated from the
    dataset. They were not — they were typed once, by hand, from the values that
    were current that day, and when the tones were re-cut they were the last
    place on the site still printing the old set. The comment was right about
    what should happen and wrong about what did, which is the worst of the two
    ways for a comment to be wrong: it stops anyone checking.

    Now it is true. This is the only block that writes into <style>, so it is
    fenced with CSS comments rather than HTML ones — see CSS_MARKERS.
    """
    out = ['.wa-win-state[data-region="%s"] .af-window-fill{fill:%s}' % (key, reg.tone)
           for key, reg in load_regions().items()]
    return "\n".join(out)


def block_window(countries, shape_by_slug, views):
    """The hero's window states — one per country, from the shared component.

    This function used to build its own clip-path, which made it the fourth
    place on the site that knew how to mask a photograph into a country. It is
    now the same `window_svg` the country pages, the journey engine and the
    human layer draw, so the signature cannot drift into four dialects of
    itself. The wrapper class stays local because the hero sizes it.

    Each state carries the viewBox the map flies to when that country is
    entered. It used to live on the country rail instead, which meant that
    taking the rail out of the hero silently took the flight with it — the
    experience buttons still swapped the card but the map sat at Africa. A
    country's own frame belongs on the country, not on one of the several
    controls that happen to select it.
    """
    boxes = views.get("countries") or {}
    out = []
    for c in countries:
        s = shape_by_slug.get(c.slug)
        if not s:
            continue
        box = boxes.get(c.slug)
        view = (' data-view="%s"' % " ".join(str(v) for v in pad_box(box, 0.9))) if box else ""
        # The region this country is in, so the window can be drawn on its
        # region's ground when there is no photograph. Five CSS rules keyed off
        # this attribute have been in the stylesheet for some time, under a
        # comment saying the figures carry it. They did not — nothing has ever
        # emitted it, so the rules matched no element and every unphotographed
        # country was drawn in the same house accent, which is the exact fault
        # the rules were written to fix.
        rkey, _reg = region_of(c)
        out.append(
            '      <figure class="wa-win-state" data-slug="%s" data-region="%s"%s>\n'
            '        %s\n      </figure>'
            % (esc(c.slug), esc(rkey or ""), view,
               plate.window_svg(s, c.name, image=c.window or None,
                                alt=c.window_alt or None,
                                ident="wc-%s" % c.slug,
                                classes="wa-win-shape af-window-svg")))
    return "\n".join(out)


# The fifty-five captions share one box and it is as tall as the tallest of
# them, so a name that takes two lines makes every caption two lines tall. At
# twenty-two countries the longest was "South Africa" and the box fitted the
# stage with a pixel to spare; "Central African Republic" is twenty-four
# characters, took a second line, and pushed the readout forty pixels below the
# hero — one country changing the height of a caption that is showing a
# different one. The generator knows the length and the CSS does not, so it
# marks the long ones and the stylesheet steps the size down for them.
LONG_NAME = 17


def block_captions(countries):
    return "\n          ".join(
        '<div class="wa-win-cap" data-slug="%s"%s><span class="wa-win-region">%s</span>'
        '<b>%s</b><span class="wa-win-tag">%s</span><span class="wa-win-op">%s</span>'
        '<a class="wa-win-go" href="%s">Enter %s &rarr;</a></div>'
        % (esc(c.slug), ' data-long="%d"' % len(c.name) if len(c.name) > LONG_NAME else '',
           esc(c.region), esc(c.name), esc(c.tagline),
           operator_line(c), esc(c.url), esc(c.name))
        for c in countries)


def block_ticks(countries, views):
    """Every destination as a button under the map.

    This is the keyboard and touch route to the twenty-two — the map's own
    shapes are the size of the countries they represent, and Rwanda is seven
    pixels square on a phone. WCAG 2.5.8 allows that only where an equivalent
    control exists, and this is it.
    """
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

    Each pick names its country in `data-slug`. The hero used to recover it from
    the href on the call below, stripped of its leading slash — which works only
    while every country's url is a path on this site. Three of them are not:
    where we have an operator of our own, `c.url` is that operator's site, so
    "https://pearl-trails-uganda.vercel.app" came back as the slug, matched
    nothing, and the map silently declined to fly. A slug is data; a href is a
    destination that is allowed to be somewhere else.
    """
    picks = load_picks()
    by_slug = dict((c.slug, c) for c in countries)
    out = []
    for want, p in picks.items():
        c = by_slug.get(p.get("country"))
        if not c:
            continue
        out.append(
            '      <article class="wa-pick" data-pick="%s" data-slug="%s" hidden>\n'
            '        <p class="wa-pick-hook">%s</p>\n'
            '        <div class="wa-pick-body">\n'
            '          <span class="wa-pick-where">%s</span>\n'
            '          <b>%s</b>\n'
            '          <p>%s</p>\n'
            '          <p class="wa-pick-why">%s</p>\n'
            '          <a class="wa-pick-go" href="%s">Explore %s &rarr;</a>\n'
            '        </div>\n      </article>'
            % (esc(want), esc(c.slug), esc(p.get("hook")), esc(c.region), esc(c.name),
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


# The grid is three columns wide, and an operator's card takes two of them.
LEAD_SLOTS = 3


def _leads(ranked):
    """How many of a region's countries get the full write-up: exactly one row.

    Counted in grid slots rather than in cards, because an operator's card is
    two columns wide. Three cards was the first rule and it was the wrong unit:
    in a region with an operator that is 2 + 1 + 1 = four slots, so the third
    card sat alone in a second row with two empty columns beside it — 275px of
    whitespace in each of the three regions that have an operator, which was
    most of what the restructure was meant to save.

    One row per region also means the lead block is the same height whether the
    region has five countries in it or fifteen, which is the property that stops
    this section growing with the atlas.
    """
    used, n = 0, 0
    for c in ranked:
        cost = 2 if c.operator else 1
        if used + cost > LEAD_SLOTS:
            break
        used += cost
        n += 1
    return n


def _season(months):
    """The good months as a compact range: "Nov-Apr", or "Jan-Mar, Jun-Oct".

    An index line has room for a season, not for a sentence about one. `when`
    is that sentence and stays on the card for the filtered view; this is the
    same fact at the width the line has.

    The runs are read off the calendar as a circle, so a dry season that crosses
    December is one range rather than two — which is most of them here.
    """
    have = sorted(set(int(m) for m in months if 1 <= int(m) <= 12))
    if not have:
        return ""
    if len(have) == 12:
        return "All year"
    runs, run = [], [have[0]]
    for m in have[1:]:
        if m == run[-1] + 1:
            run.append(m)
        else:
            runs.append(run)
            run = [m]
    runs.append(run)
    # December into January is one season, not the last run and the first.
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 12:
        runs[0] = runs.pop() + runs[0]
    short = lambda m: MONTHS[m - 1][:3]
    return ", ".join(short(r[0]) if len(r) == 1 else "%s-%s" % (short(r[0]), short(r[-1]))
                     for r in runs)


def block_destinations(countries):
    """The grid, grouped by region, each card carrying what it leads on and
    what it touches.

    This section used to grow without limit. Every published country got the
    same 275px write-up, so the grid was a straight function of how many
    countries exist: 22 of them made it 3,470px, which is 29% of the homepage,
    and the 54 we sell into would have made it about 6,200px and 40%. A homepage
    where two fifths of the scroll is one uniformly-weighted list is an index,
    not a front page.

    So a region leads with LEADS_PER_REGION write-ups and prints the rest as an
    index. The order is the one the site already uses and already justifies —
    our own operators first, then by name — so leading is a stated order rather
    than a quality ranking invented here.

    The tail is not a different kind of thing. Each entry is the same .wa-dest
    with the same data-tags, data-months and data-region, because that is what
    the filters read: a country that answered "wildlife" would otherwise vanish
    from the answer by virtue of being fourth alphabetically. It carries less
    prose, not less existence.
    """
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
        ranked = sorted(group, key=lambda x: (0 if x.operator else 1, x.name))
        tone = esc(reg.tone if reg else '')
        lead = _leads(ranked)
        for c in ranked[:lead]:
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
                   tone,
                   esc(c.operator.name if c.operator else ''), esc(c.name), esc(c.summary), esc(c.when),
                   borders, esc(c.url), esc(c.name)))
        tail = ranked[lead:]
        if not tail:
            continue
        # The tail sits in its own container rather than in the main grid,
        # because .wa-dest:nth-child(3n) is what clears the right-hand rule and
        # an index line is not on that three-column rhythm. Its own grid, its
        # own count, and the outer one stays arithmetic.
        entries = "".join(
            '<div class="wa-dest wa-dest--brief" data-region="%s" data-tags="%s"'
            ' data-months="%s" style="--reg-tone:%s">'
            '<a href="%s">%s</a><span class="wa-dest-brief-when">%s</span>'
            '<p class="wa-dest-when">%s</p></div>'
            % (key, esc(" ".join(c.calls)), esc(",".join(str(m) for m in c.months)),
               tone, esc(c.url), esc(c.name), esc(_season(c.months)), esc(c.when))
            for c in tail)
        rows.append(
            '      <div class="wa-dest-more" data-region="%s">'
            '<p class="wa-dest-more-head">Also in %s</p>%s</div>'
            % (key, title, entries))
    return "\n".join(rows)


NOW_ARC = "the-table"
NOW_ARCS = (NOW_ARC,)
NOW_CARDS = 6

# THE SIX, NAMED. Not derived, and deliberately so.
#
# Two rules were tried here and both were wrong in the same way. The first took
# photographed rows in file order and shipped these six by accident. The second
# rotated three arcs and spread five regions, and produced a technically
# excellent strip of six unrelated pictures — a plate, a loom, a skyline, a
# plate, a bolt of silk and a skyline — because a rule that optimises for spread
# cannot see that six plates of food are one collection and six other things are
# not.
#
# So the six are chosen and written down. What a rule cannot judge, a person
# can, and a list of six slugs is honest about which of the two picked them.
# Change the strip by changing this line.
NOW_PICK = ("algeria", "angola", "benin", "botswana", "burkina-faso", "burundi")

# WHO COMES ROUND NEXT, AND IN WHAT ORDER.
#
# The strip shows six of fifty-four tables, which meant forty-eight countries
# cooked for nobody. They rotate now, and the order they arrive in is the same
# kind of decision NOW_PICK is: a continent's best-known kitchens should not
# have to wait for the alphabet to reach them. These come round first, then
# everything else in file order.
#
# A slug here that is not a published country with a photographed chapter is
# skipped rather than raised on — this is a running order, not a promise that
# every name in it has a picture yet.
NOW_NEXT = ("cameroon", "nigeria", "ghana", "senegal", "ethiopia", "morocco",
            "south-africa", "kenya", "tanzania", "egypt", "cote-divoire",
            "tunisia", "mali", "uganda", "mozambique", "madagascar")

# Seconds one card holds before the next takes its place, and how long the
# whole strip takes to turn over once. One card at a time, never all six: six
# photographs changing together is a slideshow, and one changing while five
# hold still is a page that is alive.
NOW_HOLD = 4.0


def now_rows(countries):
    """Which contemporary chapters the strip shows, in order.

    Pulled out of block_now so the sentence above the strip and the strip itself
    count the same thing. They did not: the section was cut from nine cards to
    six and the paragraph beside it went on saying "Nine of them here" for two
    commits, because the cards are generated and the paragraph was typed. That
    is still what this function is for — NOW_PICK names the countries, and
    everything the sentence claims is counted off what comes back from here.

    ONE ARC, AND IT IS THE TABLE. Three of the eleven story arcs are marked
    `now` in arcs.json — the table, made by hand, the city now — and the strip
    shows one of them, on purpose. The heading is not what holds a row of six
    photographs together. The subject is.

    A named country with no chapter in this arc raises rather than quietly
    shipping five cards where the sentence beside them says six.
    """
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    rows = [r for r in (data.get("stories") or []) if r.get("now")]
    live = {c.slug: c for c in countries}
    by_country = {}
    for r in rows:
        if r["arc"] == NOW_ARC and r["country"] in live:
            by_country.setdefault(r["country"], r)

    picked = []
    for slug in NOW_PICK[:NOW_CARDS]:
        row = by_country.get(slug)
        if row is None:
            raise ValueError(
                "NOW_PICK names %r, which has no %r chapter among the published "
                "countries" % (slug, NOW_ARC))
        picked.append(row)
    return picked


TABLE_DECK = os.path.join(ROOT, "data", "table.json")


def table_deck(countries):
    """-> six running orders, one per card, no country in two of them.

    The strip holds six of the continent's fifty-four tables. Standing still,
    that meant forty-eight countries cooked for nobody — including Cameroon and
    Nigeria, which is an odd pair to leave out of a row about African food. So
    each card keeps its own deck and turns over to the next country in it.

    SIX DISJOINT DECKS, NOT ONE SHARED ONE. Every card drawing from a common
    pool eventually shows Ghana twice in the same row, and two identical
    photographs side by side reads as a bug however briefly it lasts. Dealing
    the countries out round-robin makes a duplicate impossible rather than
    unlikely, which is the difference between a rule and a hope.

    Frame nought of each deck is that card's NOW_PICK country, so the deck the
    script starts from is the strip the server already sent — the first turn is
    a change, not a correction.

    Photographed chapters only. A card that rotated to a grey plate would be
    the section briefly getting worse on a timer.
    """
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    live = {c.slug: c for c in countries}
    regions = load_regions()
    rows = {}
    for r in (data.get("stories") or []):
        if (r.get("now") and r["arc"] == NOW_ARC and r.get("image")
                and r["country"] in live and r["country"] not in rows):
            rows[r["country"]] = r

    order = [s for s in NOW_PICK if s in rows]
    for slug in NOW_NEXT:
        if slug in rows and slug not in order:
            order.append(slug)
    for slug in rows:
        if slug not in order:
            order.append(slug)

    decks = [[] for _ in range(NOW_CARDS)]
    for n, slug in enumerate(order):
        r = rows[slug]
        c = live[slug]
        key, _reg = region_of(c, regions)
        decks[n % NOW_CARDS].append({
            "country": slug,
            "name": r["countryName"],
            "arc": r["arcTitle"],
            "title": r["title"],
            "text": r["text"],
            "url": r["url"],
            "image": r["image"],
            "tone": (regions.get(key).tone if regions.get(key) else ""),
        })
    return decks


def write_table_deck(countries, log=print):
    """The decks as a file the page fetches when the strip comes into view.

    Inline it would be ten kilobytes of JSON in every homepage, carried by
    every reader including the ones who never scroll that far. Fetched on
    approach it costs nothing until the section is nearly on screen, which is
    the same argument the photographs already make with loading="lazy".
    """
    decks = table_deck(countries)
    doc = {
        "$made": "tools/tourism/build.py gateway",
        "$says": ("One running order per card in the homepage's table strip. "
                  "Frame nought of each is what the server already sent, so "
                  "the first turn is a change rather than a correction. The "
                  "decks share no country, which is what makes a duplicate "
                  "impossible rather than unlikely."),
        "hold": NOW_HOLD,
        "decks": decks,
    }
    with open(TABLE_DECK, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    log("table deck: %d countries across %d cards -> %s"
        % (sum(len(d) for d in decks), len(decks),
           os.path.relpath(TABLE_DECK, ROOT)))
    return decks


def block_nownote(countries):
    """The sentence beside the strip, counting what the strip actually holds.

    Every figure is measured off the same six rows the strip is built from. A
    typed "Nine of them here" over a six-card strip is what earned that rule,
    and a sentence promising what a continent COOKS, MAKES AND BUILDS over six
    plates of food is the same failure in better clothes: the strip is the
    table, so the sentence says the table, and the other two contemporary arcs
    are pointed at rather than implied.

    It counts no spread. It did for one commit, while the six were chosen by a
    rule that guaranteed five regions — and a sentence may only claim what
    something downstream keeps true. The six are named now, so the claim goes.

    It does claim the turn, because something downstream keeps that true: the
    count of countries the decks can reach is read off the decks themselves.
    Without the script the strip holds on its first six and the sentence is
    still not lying — six tables at a time is what a reader sees either way.
    """
    data = read_json(os.path.join(ROOT, "data", "stories.json"))
    now = [r for r in (data.get("stories") or []) if r.get("now")]
    picked = now_rows(countries)
    if not picked:
        return ('        <p class="wa-note">No contemporary chapters have been built '
                'yet.</p>')
    table = len([r for r in now if r["arc"] == NOW_ARC])
    other = len(now) - table
    # What the strip can actually reach, not what exists: a chapter with no
    # photograph is not in any deck, so counting all fifty-four here would be
    # the sentence promising countries the strip will never turn to.
    shot = sum(len(d) for d in table_deck(countries))
    return ('        <p class="wa-note">%s chapters on what this continent eats, one '
            'for every country, and %s more on what it makes and builds this decade '
            'rather than what is behind glass. %s tables at a time here, turning '
            'through the %s that have been photographed, and the rest of each '
            'country is on its own portrait. Not a feed and not an events calendar '
            '&mdash; this site holds no dates and will not invent any; these are '
            'evergreen, and they are true for longer than a week.</p>'
            % (_spell(table), _spell(other).lower(), _spell(len(picked)),
               _spell(shot).lower()))


def block_now(countries):
    """Africa now — the contemporary layer, and the argument against a museum.

    Three of the eleven story arcs are marked `now` in arcs.json: the table,
    made by hand, and the city now. Sixty-six chapters across the twenty-two,
    all of them about what a country cooks, makes and builds this decade rather
    than what is behind glass in it. None of that was on the homepage.

    Evergreen and saying so. There is no feed behind this and no dated event in
    the dataset, so it does not pretend to be current — it is the part of the
    writing that is about now, which is a different and true claim.

    Six of them, across six countries, all of them the table and all six named
    in NOW_PICK — see now_rows for why they are named and not derived. Six
    rather than nine because this replaced a section of 984 pixels and nine
    cards made it 1693 — the argument does not
    get better for being three rows tall, and this page has grown in every wave
    already.
    """
    picked = now_rows(countries)
    if not picked:
        return '      <p class="wa-note">No contemporary chapters built yet.</p>'
    live = {c.slug: c for c in countries}
    regions = load_regions()

    out = []
    for n, r in enumerate(picked):
        c = live[r["country"]]
        key, _reg = region_of(c, regions)
        art = ('<img src="%s" alt="%s" width="800" height="600" loading="lazy" '
               'decoding="async">' % (esc(r["image"]), esc(r["text"]))) if r.get("image") else (
              '<span class="wa-now-plate" aria-hidden="true"></span>')
        out.append(
            '      <a class="wa-now%s" href="%s" style="--reg-tone:%s" data-slot="%d">'
            '<span class="wa-now-art">%s</span>'
            '<span class="wa-now-say"><i>%s &middot; %s</i><b>%s</b><p>%s</p></span></a>'
            % (" has-shot" if r.get("image") else "", esc(r["url"]),
               esc((regions.get(key).tone if regions.get(key) else "")), n, art,
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
    """The colophon, not a second copy of the website.

    It used to be two columns headed "Destinations" and "More destinations",
    which split Africa in half at whatever index len(countries)//2 landed on —
    fifty-four names down two vertical lists, with Eritrea ending one column
    and Ethiopia starting the next for no reason a reader could see. Beside
    them sat a paragraph explaining that we run three operators and nineteen
    other countries are written up anyway, which is the same defensive sentence
    the rest of the site has stopped making, in the calmest place on the page.

    Now it is the five regions the atlas already uses, the eight lenses, and
    the three things a visitor can actually do. The links are real: the map
    reads the hash, so /#r/east opens the footer straight into East Africa and
    /#w/wildlife colours the continent for wildlife. A footer link that only
    scrolls somewhere is a footer link nobody presses twice.

    The deeper the visitor goes the more there is; the footer is where it gets
    quiet again.
    """
    # The same five the map's own region row uses, in the same order, so the
    # footer and the top of the page cannot disagree about how Africa is cut.
    regions = []
    for key, label, names in REGION_GROUPS:
        n = len([c for c in countries if c.region in names])
        if not n:
            continue
        regions.append('        <a href="/#r/%s">%s<i>%d</i></a>'
                       % (esc(key), label, n))

    lenses = []
    for key, lens in sorted(load_lenses().items(),
                            key=lambda kv: kv[1].get("title", kv[0])):
        if key.startswith("$"):
            continue
        lenses.append('        <a href="/#w/%s">%s</a>' % (esc(key), esc(lens["title"])))

    plan = [
        ("/journey", "Build a journey"),
        ("/trans-afrique", "Trans Afrique"),
        ("/enquire", "Begin your journey"),
        ("#destinations", "Travel seasons"),
    ]
    plan_links = "\n".join('        <a href="%s">%s</a>' % (esc(u), esc(t))
                           for u, t in plan)

    return (
        '      <div class="wa-foot-col">\n        <b>Destinations</b>\n%s\n      </div>\n'
        '      <div class="wa-foot-col">\n        <b>Experiences</b>\n%s\n      </div>\n'
        '      <div class="wa-foot-col">\n        <b>Plan</b>\n%s\n      </div>'
        % ("\n".join(regions), "\n".join(lenses), plan_links))


def render(countries):
    seq = ordered(countries)
    shape_by_slug = shapes()
    views = load_views()
    with_shape = [c for c in seq if c.slug in shape_by_slug]
    return {
        "regions": block_regions(seq, views),
        "cities": block_cities(seq),
        "experiences": block_experiences(seq),
        "wants": block_wants(seq),
        "expcards": block_expcards(seq),
        "mapunder": block_mapunder(seq),
        "maplive": block_maplive(seq),
        "lede": block_lede(seq),
        "citylede": block_citylede(seq),
        "mapsvg": block_mapsvg(seq),
        "capafrica": block_capafrica(seq),
        "destlede": block_destlede(seq),
        "readslede": block_readslede(seq),
        "mapover": block_mapover(seq),
        "window": block_window(with_shape, shape_by_slug, views),
        "captions": block_captions(with_shape),
        "ticks": block_ticks(with_shape, views),
        "claim": block_claim(seq),
        "months": block_months(seq),
        "destinations": block_destinations(seq),
        "scale": block_scale(),
        "operators": block_operators(seq),
        "picks": block_picks(seq),
        "planfork": block_planfork(seq),
        "plannote": block_plannote(seq),
        "plansteps": block_plansteps(seq),
        "nownote": block_nownote(seq),
        "now": block_now(seq),
        "stories": block_stories(seq),
        "footer": block_footer(seq),
        "feel": block_feel(seq),
        "moments": block_moments(),
        "momentsay": block_momentsay(),
        "motion": block_motion()[0],
        "motiontracks": block_motion()[1],
        "seasons": block_seasons(seq),
        "seasonsay": block_seasonsay(seq),
        "regiontone": block_regiontone(),
        "wonders": _wonders.block_wonders(seq),
        "wonderslede": _wonders.block_wonderslede(seq),
        "door": _trans.block_door(seq),
    }


def marker(name, close=False):
    """The opening or closing marker for a region, in the comment syntax that is
    legal where that region lives."""
    slash = "/" if close else ""
    if name in CSS_MARKERS:
        return "/* %sgen:%s */" % (slash, name)
    return "<!-- %sgen:%s -->" % (slash, name)


def splice(src, blocks, check=True):
    """Replace between each pair of markers. Missing markers are an error, not a
    silent no-op: a marker that got lost in an edit would otherwise mean a
    section quietly stopped tracking the dataset.

    `check` is off when splicing the stylesheet, which holds one marker and not
    the other forty — the completeness check belongs to the page.
    """
    if check:
        # The CSS markers are checked against the stylesheet, not the page.
        missing = [name for name in MARKERS
                   if name not in CSS_MARKERS and marker(name) not in src]
        if missing:
            raise ValueError("index.html is missing markers: %s" % ", ".join(missing))
    for name, body in blocks.items():
        # THIS HAS TO BE IDEMPOTENT, AND FOR A LONG TIME IT WAS NOT.
        #
        # The pattern was `(open\n).*?(\s*close)` and the replacement re-emitted
        # group 2 verbatim. `\s*` is greedy for whitespace and `.*?` is lazy, so
        # group 2 absorbed every newline sitting between the body and the
        # closing marker — and then the new body, which ends in a newline of its
        # own, was written in front of it. One extra blank line per build, every
        # build, for ever. index.html had accumulated thirty-two of them inside
        # gen:maplive, and two commits on main exist for no other reason than
        # that a resolver run which changed nothing still produced a diff.
        #
        # `\n?[ \t]*` cannot cross a line, so the lazy `.*?` gives it only the
        # last newline and the closing marker's own indentation. Everything
        # before that is body and is replaced. Run it twice and the second run
        # writes the same bytes as the first.
        #
        # rstrip on the body for the same reason: it is the body's job to say
        # what it contains, not how much air sits under it.
        pattern = re.compile(r"(%s\n).*?(\n?[ \t]*)(%s)"
                             % (re.escape(marker(name)), re.escape(marker(name, True))), re.S)
        src, hits = pattern.subn(
            lambda m: m.group(1) + body.rstrip() + m.group(2) + m.group(3),
            src, count=1)
        # A marker that is present but does not match is the same fault as one
        # that is absent, and it is the quieter of the two: the pattern wants a
        # newline directly after the opening marker, so a pair written inline —
        # `<!-- gen:lede --><!-- /gen:lede -->` — passes the check above, matches
        # nothing, and leaves the region empty for as long as nobody looks at the
        # page. It did, for one build.
        if not hits:
            raise ValueError(
                "gen:%s is in the page but nothing was written into it. The "
                "opening marker needs a newline directly after it, and the "
                "closing marker has to come after it." % name)
    return src


# The homepage's CSS lives in its own file now, so the one generated CSS block
# lives there too. Splicing writes to whichever file holds each marker rather
# than assuming both are in index.html — which they were, for as long as the
# stylesheet was a 180 KB <style> element.
SHEET = os.path.join(ROOT, "styles", "gateway.css")


def run(countries, page=None, log=print):
    page = page or PAGE
    with open(page) as fh:
        src = fh.read()
    blocks = render(countries)
    html_blocks = dict((k, v) for k, v in blocks.items() if k not in CSS_MARKERS)
    css_blocks = dict((k, v) for k, v in blocks.items() if k in CSS_MARKERS)
    out = splice(src, html_blocks)
    changed = out != src
    if changed:
        with open(page, "w") as fh:
            fh.write(out)
    if css_blocks:
        with open(SHEET) as fh:
            sheet_src = fh.read()
        sheet_out = splice(sheet_src, css_blocks, check=False)
        if sheet_out != sheet_src:
            with open(SHEET, "w") as fh:
                fh.write(sheet_out)
            changed = True
    write_table_deck(countries, log=log)
    seq = ordered(countries)
    log("%s %d countries (%d with an operator of ours) into %s"
        % ("rewrote" if changed else "no change:", len(seq),
           sum(1 for c in seq if c.operator), os.path.relpath(page, ROOT)))
    return changed
