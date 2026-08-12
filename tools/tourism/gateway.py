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
import os
import re

from .model import ROOT

PAGE = os.path.join(ROOT, "index.html")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")

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

MARKERS = ("window", "captions", "ticks", "months", "destinations", "footer")

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
    return ("Operated locally by %s" % esc(c.operator)) if c.operator \
        else "Run with a licensed local operator"


def block_window(countries, shape_by_slug):
    out = []
    for i, c in enumerate(countries):
        s = shape_by_slug.get(c.slug)
        if not s:
            continue
        art = ""
        if c.window:
            art = ('<image clip-path="url(#wc-%s)" href="%s" x="0" y="0" width="%s" height="%s" '
                   'preserveAspectRatio="xMidYMid slice"/>'
                   % (esc(c.slug), esc(c.window), s["w"], s["h"]))
        label = esc(c.window_alt) if (c.window and c.window_alt) else \
            "The outline of %s" % esc(c.name)
        out.append(
            '      <figure class="wa-win-state" data-slug="%s">\n'
            '        <svg class="wa-win-shape" viewBox="0 0 %s %s" role="img" aria-label="%s">\n'
            '          <defs><clipPath id="wc-%s"><path d="%s"/></clipPath></defs>\n'
            '          <path class="wa-win-fill" d="%s"/>%s\n        </svg>\n      </figure>'
            % (esc(c.slug), s["w"], s["h"], label, esc(c.slug), s["d"], s["d"], art))
    return "\n".join(out)


def block_captions(countries):
    return "\n          ".join(
        '<div class="wa-win-cap" data-slug="%s"><span class="wa-win-region">%s</span>'
        '<b>%s</b><span class="wa-win-tag">%s</span><span class="wa-win-op">%s</span>'
        '<a class="wa-win-go" href="%s">Enter %s &rarr;</a></div>'
        % (esc(c.slug), esc(c.region), esc(c.name), esc(c.tagline),
           operator_line(c), esc(c.url), esc(c.name))
        for c in countries)


def block_ticks(countries):
    return "".join('<button class="wa-tick" type="button" data-slug="%s">%s</button>'
                   % (esc(c.slug), esc(c.name)) for c in countries)


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


def block_destinations(countries):
    """The grid, grouped by region, each card carrying what it leads on."""
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
        rows.append('      <h3 class="wa-dest-reg" data-region="%s">%s</h3>' % (key, title))
        for c in sorted(group, key=lambda x: (0 if x.operator else 1, x.name)):
            rows.append(
                '      <div class="wa-dest" data-region="%s" data-tags="%s" data-months="%s">'
                '<b>%s</b><h3>%s</h3><p>%s</p>'
                '<p class="wa-dest-when">%s</p>'
                '<a href="%s">Explore %s &rarr;</a></div>'
                % (key, esc(" ".join(c.calls)), esc(",".join(str(m) for m in c.months)),
                   esc(c.operator), esc(c.name), esc(c.summary), esc(c.when),
                   esc(c.url), esc(c.name)))
    return "\n".join(rows)


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
    with_shape = [c for c in seq if c.slug in shape_by_slug]
    return {
        "window": block_window(with_shape, shape_by_slug),
        "captions": block_captions(with_shape),
        "ticks": block_ticks(with_shape),
        "months": block_months(seq),
        "destinations": block_destinations(seq),
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
