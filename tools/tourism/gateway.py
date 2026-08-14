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
from .model import (CATEGORY_FILE, ROOT, load_cities, load_lenses, load_picks,
                    load_regions, load_views, region_of)

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

MARKERS = ("window", "captions", "ticks", "regions", "cities", "experiences",
           "wants", "expcards", "mapunder", "mapover", "claim", "months", "scale",
           "destinations", "operators", "picks", "plannote", "plansteps",
           "nownote", "now", "stories", "footer", "regiontone", "feel")

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
        else "Written up here, run by somebody else"


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
    cities = load_cities()
    by_slug = dict((c.slug, c) for c in countries)
    rows = []
    for i, city in enumerate(cities):
        c = by_slug.get(city.get("country"))
        if not c:
            continue                      # a card has to lead somewhere real
        key, reg = region_of(c)
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
            % (esc(c.url), wide, esc(key), "true" if photo else "false", esc(tone),
               art, esc(city["name"]), esc(c.name), esc(city["line"]), esc(city["say"])))
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
            '<span class="wa-city-note">These %s are a choice, and the choice is ours. '
            'The atlas holds every place written up on this site, in all twenty-two '
            'countries, with no editor standing in front of it.</span>'
            '</span></a>' % (span, _spell(len(rows)).lower()))
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
               LENS_ICONS[key], esc(lens["title"])))
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
            '      <a class="wa-feel" href="/journey#/?w=%s" data-lens="%s">'
            '<span class="wa-feel-say">%s</span>'
            '<span class="wa-feel-what">%s</span>'
            '<span class="wa-feel-n">%s %s</span></a>'
            % (esc(key), esc(key), esc(lens.get("feel") or lens["line"]),
               lens["label"],
               _spell(len(names)).lower() if len(names) < 20 else len(names),
               "country leads on this" if len(names) == 1 else "countries lead on this"))
    return "\n".join(out)


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
        icon = LENS_ICONS[key]
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
    for c in d["cities"]:
        lead = ' data-lead="true"' if c["slug"] in named else ''
        # A point that cannot be pressed is decoration. These are places with a
        # page behind them, so they are links — which also puts them in the tab
        # order and gives a screen reader something to announce.
        out.append('<a class="wa-map-city" href="%s"%s data-slug="%s">'
                   % (esc(urls.get(c["country"], "/places")), lead, esc(c["slug"])))
        out.append('<g class="wa-map-city-in" data-slug="%s">'
                   '<circle class="wa-map-city-dot" cx="%.1f" cy="%.1f" r="3.4"/>'
                   '<circle class="wa-map-city-ring" cx="%.1f" cy="%.1f" r="7"/>'
                   '<text class="wa-map-city-say" x="%.1f" y="%.1f">%s</text>'
                   '<title>%s</title></g>'
                   % (esc(c["slug"]), c["x"], c["y"], c["x"], c["y"],
                      c["x"] + 11, c["y"] + 4, esc(c["name"].upper()), esc(c["name"])))
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
    note = ('We can book anywhere on the continent through operators who live '
            'there. In %s the operator is ours &mdash; we own the company, and '
            'the guide on the day works for it. The other %s in this atlas are '
            'written up to the same twenty-seven categories and booked through '
            'somebody else, which we say before you write, not after.'
            % (names, _spell(rest).lower()))

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
        ('/contact', 'Ask',
         'Enquiries reach %s in %s. For %s they are the operator; for the other '
         '%s they will tell you who is.'
         % (esc(host.operator.name), esc(host.operator.base), esc(host.name),
            _spell(rest).lower()),
         'Write to them'),
    ]
    out = []
    for i, (url, title, text, go) in enumerate(steps, 1):
        out.append('      <a class="wa-step wa-step--go" href="%s"><i>%02d</i>'
                   '<b>%s</b><p>%s</p><span class="wa-step-go">%s &rarr;</span></a>'
                   % (esc(url), i, esc(title), text, esc(go)))
    # The last step is the only one that is not a link, because it is the only
    # one that happens away from this website.
    out.append('      <div class="wa-step"><i>%02d</i><b>Travel</b><p>Where the '
               'operator is ours, the guide on the day works for the company you '
               'booked: %s. Where it is not, we are not going to describe a day '
               'run by people we have not named.</p></div>'
               % (len(steps) + 1,
                  _and_list(['%s in %s' % (esc(c.operator.name), esc(c.name))
                             for c in ours])))
    return note, "\n".join(out)


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


def block_captions(countries):
    return "\n          ".join(
        '<div class="wa-win-cap" data-slug="%s"><span class="wa-win-region">%s</span>'
        '<b>%s</b><span class="wa-win-tag">%s</span><span class="wa-win-op">%s</span>'
        '<a class="wa-win-go" href="%s">Enter %s &rarr;</a></div>'
        % (esc(c.slug), esc(c.region), esc(c.name), esc(c.tagline),
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
        "cities": block_cities(seq),
        "experiences": block_experiences(seq),
        "wants": block_wants(seq),
        "expcards": block_expcards(seq),
        "mapunder": block_mapunder(seq),
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
        "plannote": block_plannote(seq),
        "plansteps": block_plansteps(seq),
        "nownote": block_nownote(seq),
        "now": block_now(seq),
        "stories": block_stories(seq),
        "footer": block_footer(seq),
        "feel": block_feel(seq),
        "regiontone": block_regiontone(),
    }


def marker(name, close=False):
    """The opening or closing marker for a region, in the comment syntax that is
    legal where that region lives."""
    slash = "/" if close else ""
    if name in CSS_MARKERS:
        return "/* %sgen:%s */" % (slash, name)
    return "<!-- %sgen:%s -->" % (slash, name)


def splice(src, blocks):
    """Replace between each pair of markers. Missing markers are an error, not a
    silent no-op: a marker that got lost in an edit would otherwise mean a
    section quietly stopped tracking the dataset."""
    missing = [name for name in MARKERS if marker(name) not in src]
    if missing:
        raise ValueError("index.html is missing markers: %s" % ", ".join(missing))
    for name, body in blocks.items():
        pattern = re.compile(r"(%s\n).*?(\s*%s)"
                             % (re.escape(marker(name)), re.escape(marker(name, True))), re.S)
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
