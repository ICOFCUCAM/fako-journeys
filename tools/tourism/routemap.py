"""The crossings, drawn on the continent they cross.

Built by tools/tourism/transafrique.py. It is the whole of /trans-afrique/
crossings: a plate on the left and the four journeys as an editorial index on
the right, one object rather than a map with a legend beside it.

WHY IT IS A MAP AND NOT FOUR MAPS

The four crossings are not four independent products, and the geometry says so
out loud once it is plotted. Trans Afrique East is the first four countries of
the Continental Expedition. Trans Afrique South is its last five, reversed.
Drawn as four separate lines, three of them lie on top of each other and the
picture is a muddle that also happens to be a lie — it shows three roads where
there is one.

So the spine is the object and the regional crossings are lengths of it, drawn
coincident, narrower, and on top. Selecting one does not draw a new road; it
lights the part of the road that journey uses. That is the hierarchy the copy
claims and until now only the copy claimed it.

WHY THE NODES ARE COUNTRIES AND NOT CITIES

The routes in tourism/transafrique.json are chains of countries, and the only
coordinates that exist for all of them are country centroids in
tourism/map.json. Thirteen cities have real positions in
tourism/atlas-detail.json and four of the eight route endpoints are among them —
Dakar, Accra, Nairobi and Cape Town — while Arusha and Victoria Falls are not.
Anchoring half the ends to cities and half to centroids would put city names on
country middles, which is the one thing the rest of this site refuses to do.

SO A TERMINUS IS NAMED ONLY WHERE THE CITY HAS A POSITION. Each route's own
`shape` string names its two ends — "Nairobi to Cape Town" — and four of the
eight are in the city file: Dakar, Accra, Nairobi and Cape Town. Those four are
drawn AT THE CITY, which is a real coordinate, and the road is extended to
reach them, which is not a liberty but the journey: the Continental Expedition
starts in Nairobi, not at Kenya's centroid.

Arusha and Victoria Falls have no position, so East and South keep a plain ring
on the country at that end and say the city in the panel instead. Half the map
labelled and half not is the honest shape of what this repository knows, and it
is visibly better than either alternative — four invented positions, or four
real ones withheld to make the plate look consistent.

THE LINES ARE CURVES, AND THE CURVE IS NOT DECORATION

Straight segments between centroids read as a transit diagram — the thing the
brief rules out and the thing a chain of dots between capitals always becomes.
A Catmull-Rom spline through the same anchors reads as a road: it arrives at
every point the data actually knows and bends between them the way a route
does. No anchor moves, so nothing is claimed that the straight version did not
claim. The tension is held well under 1 so the curve never bulges far enough
from the segment to imply a detour that is not there.
"""

import json
import math
import os

from . import countrymap
from .model import ROOT

MAP = os.path.join(ROOT, "tourism", "map.json")
DETAIL = os.path.join(ROOT, "tourism", "atlas-detail.json")

# Where the plate's furniture sits, in viewBox units. All of it is over open
# water or empty Sahara, checked against the drawn coastline rather than
# eyeballed — a compass rose on top of Chad is a rose nobody trusts.
OCEANS = ((132.0, 214.0, "Atlantic Ocean"), (905.0, 872.0, "Indian Ocean"))
CONTINENT = (470.0, 330.0, "Africa")
ROSE = (96.0, 806.0)
SCALE = (56.0, 900.0, 210.0)      # x, y, drawn length in units

# How wide each road is drawn. The spine is the road; South is a length of it,
# East a shorter length again, and West is its own arc. Descending width with
# the spine underneath makes the overlap read as nesting rather than as three
# lines fighting, and it is the hierarchy the section argues in words.
WIDTHS = {"great": 7.0, "south": 4.0, "east": 2.6, "west": 4.6}
ORDER = ("great", "south", "east", "west")


def load_map():
    with open(MAP, encoding="utf-8") as fh:
        return json.load(fh)


def cities():
    """The thirteen places on this site that have a real position.

    Four of them are Trans Afrique termini — Dakar, Accra, Nairobi and Cape
    Town — which is why the ends of West and of the Continental Expedition can
    be marked and named while Arusha and Victoria Falls cannot: those two are
    not in the file, and a city label on a country centroid is wrong by a
    couple of hundred kilometres.
    """
    with open(DETAIL, encoding="utf-8") as fh:
        det = json.load(fh)
    return {c["name"].lower(): c for c in det.get("cities") or []}


def ends(route):
    """The two place names in a crossing's own `shape` string.

    "Nairobi to Cape Town." is the route describing itself, so the ends come
    from the data rather than from a table somebody has to keep in step.
    """
    shape = (route.get("shape") or "").strip().rstrip(".")
    if " to " not in shape:
        return None, None
    a, b = shape.split(" to ", 1)
    return a.strip().strip(","), b.split(",")[0].strip()


def _esc(v):
    import html as h
    return h.escape(str(v if v is not None else ""), quote=True)


def spline(pts, tension=0.62):
    """A Catmull-Rom spline through every point, as one cubic path.

    Every anchor is on the curve — this smooths the road between the countries,
    it does not move the countries. Tension is deliberately below the classic 1
    so a bend never travels far enough from the straight line to suggest a
    detour the itinerary does not take.
    """
    if len(pts) < 2:
        return ""
    if len(pts) == 2:
        return "M%.1f %.1f L%.1f %.1f" % (pts[0][0], pts[0][1], pts[1][0], pts[1][1])
    d = ["M%.1f %.1f" % (pts[0][0], pts[0][1])]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 6.0,
              p1[1] + (p2[1] - p0[1]) * tension / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 6.0,
              p2[1] - (p3[1] - p1[1]) * tension / 6.0)
        d.append("C%.1f %.1f %.1f %.1f %.1f %.1f"
                 % (c1[0], c1[1], c2[0], c2[1], p2[0], p2[1]))
    return " ".join(d)


def plate(d, by_slug=None, only=None):
    """The cartographic object: continent, roads, nodes, names.

    Six layers and no more, in this order, because each one is only legible
    against the one under it:

        1  the continent, flat and quiet, every country Afrinkong does not
           cross included — thirteen countries alone on a dark field is a
           diagram, and the point of drawing a crossing on Africa is that
           Africa is around it
        2  the countries the roads enter, a shade up from the rest
        3  the roads, curved, in descending width
        4  a node at every country the road stops in
        5  a ring at each end of each road
        6  the country names, which appear only for the selected crossing
        7  the furniture: two oceans, the continent, a rose and a scale

    The furniture is what makes it a plate rather than a diagram, and every
    piece of it is either a fact of the page or derived: the oceans and the
    continent are named because they are, the rose points north because the
    projection does, and the scale bar is COMPUTED at the latitude it is drawn
    at rather than stated. There is still no graticule, no river and no city
    that is not the end of a road — this plate has one job, and a map that
    also shows rivers shows a journey less well.
    """
    by_slug = by_slug or {}
    m = load_map()
    view = m.get("view") or [0, 0, 1000.0, 1060.0]
    at, base = {}, []
    for c in m.get("live", []):
        if c.get("d"):
            base.append((c["slug"], c["d"]))
        if c.get("at"):
            at[c["slug"]] = c["at"]
    rest = [r["d"] for r in m.get("rest", []) if r.get("d")]

    shown = [r for r in d["routes"] if only is None or r["id"] == only]
    routes = {r["id"]: r for r in shown}
    crosses = {}
    for r in shown:
        for s_ in r.get("countries") or []:
            crosses.setdefault(s_, []).append(r["id"])

    out = ['<svg class="tf-plate-svg" viewBox="%s %s %s %s" role="img" '
           'aria-labelledby="tf-plate-t">' % tuple(view)]
    if only is None:
        out.append('<title id="tf-plate-t">Africa, with the four Trans Afrique '
                   'crossings drawn on it: the Continental Expedition running '
                   'from Kenya to South Africa, East and South as lengths of '
                   'that same road, and West along the Atlantic from Senegal '
                   'to Ghana.</title>')
    else:
        one = shown[0] if shown else {}
        out.append('<title id="tf-plate-t">%s drawn on Africa: %s, through '
                   '%s.</title>'
                   % (_esc(one.get("name") or only),
                      _esc((one.get("shape") or "").rstrip(".")),
                      _esc(", ".join((by_slug[s_].name if s_ in by_slug
                                      else s_.replace("-", " ").title())
                                     for s_ in (one.get("countries") or [])))))

    # 1 + 2. The continent. Borders are drawn on the crossed countries only:
    # picking every border out turns the plate into an atlas index, and picking
    # none out leaves the road running across an undifferentiated shape.
    out.append('<g class="tf-plate-rest" aria-hidden="true">')
    out += ['<path d="%s"/>' % p for p in rest]
    out += ['<path d="%s"/>' % p for s_, p in base if s_ not in crosses]
    out.append('</g>')
    out.append('<g class="tf-plate-in" aria-hidden="true">')
    for slug, path in base:
        if slug in crosses:
            out.append('<path d="%s" data-country="%s" data-in="%s"/>'
                       % (path, _esc(slug), " ".join(crosses[slug])))
    out.append('</g>')

    # 3. The roads. Widest first and underneath, so a regional crossing reads
    #    as a length of the spine rather than a line beside it.
    #
    #    Where a terminus is a city we hold a position for, the road runs on to
    #    the city. That is the journey — the Continental Expedition begins in
    #    Nairobi and not at Kenya's centroid — so extending it is more accurate
    #    than stopping short, not less.
    town = cities()
    termini = {}
    for r in shown:
        a, b = ends(r)
        cc = r.get("countries") or []
        pair = []
        for name, slug in ((a, cc[0] if cc else None), (b, cc[-1] if cc else None)):
            c = town.get((name or "").lower())
            pair.append(c if (c and slug and c.get("country") == slug) else None)
        termini[r["id"]] = pair
    # Collected once, here, because both the town layer and the country-name
    # layer need it and the name layer is emitted first.
    seen = {}
    for rid in ORDER:
        for c in (termini.get(rid) or []):
            if c:
                seen.setdefault(c["slug"], [c, []])[1].append(rid)

    out.append('<g class="tf-plate-roads" aria-hidden="true">')
    for rid in ORDER:
        r = routes.get(rid)
        if not r:
            continue
        pts = [at[s_] for s_ in (r.get("countries") or []) if s_ in at]
        if len(pts) < 2:
            continue
        head, tail = termini.get(rid) or (None, None)
        if head:
            pts = [[head["x"], head["y"]]] + pts
        if tail:
            pts = pts + [[tail["x"], tail["y"]]]
        path = spline(pts)
        # The halo is a wider stroke of the ground colour under the road, so a
        # narrower road crossing a wider one is separated by a hair of dark
        # rather than merging into it. Cheaper and crisper than a filter, and
        # filters are forbidden anywhere near this page's fixed picture.
        out.append('<path class="tf-plate-halo" data-route="%s" d="%s" '
                   'style="stroke-width:%s"/>' % (rid, path, WIDTHS[rid] + 3.4))
        out.append('<path class="tf-plate-road" data-route="%s" d="%s" '
                   'style="stroke-width:%s"/>' % (rid, path, WIDTHS[rid]))
    out.append('</g>')

    # 4 + 5. A node at every country on a road; a ring at each end of each road.
    priority = {"east": 0, "west": 1, "south": 2, "great": 3}
    out.append('<g class="tf-plate-nodes" aria-hidden="true">')
    for slug in sorted(crosses):
        if slug not in at:
            continue
        owner = sorted(crosses[slug], key=lambda k: priority.get(k, 9))[0]
        out.append('<circle class="tf-node" cx="%.1f" cy="%.1f" r="4.6" '
                   'data-route="%s" data-country="%s" data-in="%s"/>'
                   % (at[slug][0], at[slug][1], owner, _esc(slug),
                      " ".join(crosses[slug])))
    for rid in ORDER:
        r = routes.get(rid)
        if not r:
            continue
        stops = [s_ for s_ in (r.get("countries") or []) if s_ in at]
        for s_ in ({stops[0], stops[-1]} if len(stops) > 1 else set(stops)):
            out.append('<circle class="tf-term" cx="%.1f" cy="%.1f" r="9.5" '
                       'data-route="%s" data-country="%s"/>'
                       % (at[s_][0], at[s_][1], rid, _esc(s_)))
    out.append('</g>')

    # 6. Country names, one per node, hidden until a crossing is chosen. Drawn
    #    for every route so that choosing one is a CSS state change and not a
    #    re-render, and so the plate is complete with scripting off.
    # A country whose terminus city is named does not also get its country
    # name: "NAIROBI" and "KENYA" set fourteen pixels apart is one place
    # labelled twice, and the more precise of the two is the one to keep.
    named_by_town = {c["country"] for c, _ in seen.values() if c.get("country")}
    out.append('<g class="tf-plate-names" aria-hidden="true">')
    for slug in sorted(crosses):
        if slug not in at or slug in named_by_town:
            continue
        x, y = at[slug]
        name = (by_slug[slug].name if slug in by_slug
                else slug.replace("-", " ").title())
        # West runs down the bulge with the ocean to its left, so its names sit
        # left of the node; everything else has open ground to the east.
        west = "west" in crosses[slug] and len(crosses[slug]) == 1
        out.append('<text class="tf-name" x="%.1f" y="%.1f" data-in="%s" '
                   'text-anchor="%s">%s</text>'
                   % (x + (-14 if west else 14), y + 4.5,
                      " ".join(crosses[slug]), "end" if west else "start",
                      _esc(name.upper())))
    out.append('</g>')

    # 5b. The terminus cities we hold a position for, marked and named at the
    #     city rather than at the country. Four of eight; the other four ends
    #     keep the country ring and say the city in the panel.
    # ONE MARKER PER CITY, not one per route that ends there. Nairobi is the
    # head of both East and the Continental Expedition and Cape Town is the tail
    # of one and the head of another, so drawing them per route stacked two
    # identical labels on the same pixel — legible only because they were
    # exactly on top of each other, and doubled in weight against everything
    # else. `data-in` carries every route that uses the city, which is what the
    # selection rules key off anyway.
    out.append('<g class="tf-plate-towns" aria-hidden="true">')
    for slug in sorted(seen):
        c, rids = seen[slug]
        # Cape Town is the southern tip with no room to its right on the plate,
        # so its name goes above the dot; the rest read outward from it.
        up = c["y"] > 900
        out.append('<g class="tf-town" data-in="%s">'
                   '<circle cx="%.1f" cy="%.1f" r="7"/>'
                   '<circle class="tf-town-pip" cx="%.1f" cy="%.1f" r="2.6"/>'
                   '<text x="%.1f" y="%.1f" text-anchor="%s">%s</text></g>'
                   % (" ".join(rids), c["x"], c["y"], c["x"], c["y"],
                      c["x"] if up else c["x"] + 14,
                      c["y"] - 15 if up else c["y"] + 5,
                      "middle" if up else "start",
                      _esc(c["name"].upper())))
    out.append('</g>')

    out.append(furniture(view))
    out.append('</svg>')
    return "".join(out)


def furniture(view):
    """Two oceans, the continent, a north mark and a scale.

    THE SCALE IS COMPUTED WHERE IT IS DRAWN, WHICH IS THE ONLY WAY A SCALE ON A
    CONTINENTAL MAP IS TRUE. This projection draws every parallel at the length
    of the equator, so a horizontal bar means a different distance at Cairo than
    at Cape Town — by about a quarter across the range Africa covers. The bar
    sits in the South Atlantic, its latitude is read off the drawn parallels the
    same way tools/tourism/countrymap.py reads any other, and the label says
    which latitude it is true at rather than pretending it is true everywhere.

    A bar stated instead of derived is the kind of thing nobody checks and
    everybody trusts, which is the worst combination on a page whose argument
    is that Afrinkong knows the ground.
    """
    x, y, want = SCALE
    lat = countrymap.latitude(x + want / 2, y)
    fit = countrymap.load_map_fit()
    km_per_unit = None
    if fit and lat is not None:
        km_per_unit = (6371.0 / fit) * math.cos(math.radians(lat))
    bits = []
    for ox, oy, name in OCEANS:
        bits.append('<text class="tf-sea" x="%.1f" y="%.1f" '
                    'text-anchor="middle">%s</text>' % (ox, oy, _esc(name.upper())))
    bits.append('<text class="tf-land" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                % (CONTINENT[0], CONTINENT[1], _esc(CONTINENT[2].upper())))
    rx, ry = ROSE
    bits.append('<g class="tf-rose">'
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                '<circle cx="%.1f" cy="%.1f" r="15"/>'
                '<text x="%.1f" y="%.1f" text-anchor="middle">N</text></g>'
                % (rx, ry - 11, rx, ry + 11, rx, ry, rx, ry - 20))
    if km_per_unit:
        step = 500
        while step * 4 < want * km_per_unit:
            step *= 2
        length = (step * 2) / km_per_unit
        bits.append('<g class="tf-scale">'
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                    '<text x="%.1f" y="%.1f">0</text>'
                    '<text x="%.1f" y="%.1f" text-anchor="end">%s KM</text>'
                    '<text class="tf-scale-at" x="%.1f" y="%.1f">at %d&#176;%s</text>'
                    '</g>'
                    # Two labels, not three. The bar is about eighty pixels on
                    # a desktop plate and "0 500 1000 KM" ran the middle figure
                    # straight through the last one; the half-way tick still
                    # marks the interval without printing a number on top of a
                    # number.
                    % (x, y, x + length, y,
                       x, y - 5, x, y + 5,
                       x + length / 2, y - 4, x + length / 2, y + 4,
                       x + length, y - 5, x + length, y + 5,
                       x, y - 11,
                       x + length, y - 11, "{:,}".format(step * 2),
                       x, y + 22, abs(round(lat)), "S" if lat < 0 else "N"))
    return '<g class="tf-plate-furn" aria-hidden="true">%s</g>' % "".join(bits)


def build(d, by_slug=None, only=None, act=None, title=None, say=None):
    """The whole section: the plate, and the four journeys as an index.

    THE INDEX IS NOT A LEGEND. A legend explains a picture; this chooses what
    the picture shows. Each entry is a button that lights its road, dims the
    other three, names the countries it stops in on the plate itself and opens
    its own summary — which is why the route cards that used to sit under this
    map are gone: they printed the same four names, the same four chains and
    the same three figures a screen further down.

    WITH SCRIPTING OFF IT IS STILL COMPLETE. Every summary is in the DOM and
    open; the script adds a class that turns them into an accordion and wires
    the buttons. Nothing here is built by JavaScript, so nothing here is lost
    without it — the reader gets the full map and all four journeys, laid out
    rather than selected.
    """
    by_slug = by_slug or {}
    shown = [r for r in d["routes"] if only is None or r["id"] == only]
    rows = []
    for r in shown:
        chain = " &middot; ".join(
            _esc(by_slug[s_].name) if s_ in by_slug
            else _esc(s_.replace("-", " ").title())
            for s_ in (r.get("countries") or []))
        short = (r.get("short") or r["name"].split("—")[-1].strip())
        rows.append(
            '<li class="tf-pick%s" data-route="%s">'
            '<button class="tf-pick-hit" type="button" data-route="%s" '
            'aria-expanded="true" aria-controls="tf-sum-%s">'
            '<span class="tf-pick-dot" aria-hidden="true"></span>'
            '<span class="tf-pick-name">%s</span>'
            '<span class="tf-pick-n">%d countries</span>'
            '<span class="tf-pick-where">%s</span>'
            '</button>'
            '<div class="tf-sum" id="tf-sum-%s">'
            '<p class="tf-sum-say">%s</p>'
            '<dl class="tf-sum-facts">'
            '<div><dt>Shape</dt><dd>%s</dd></div>'
            '<div><dt>Length</dt><dd>%s days</dd></div>'
            '<div><dt>Journey fee</dt><dd>%s</dd></div>'
            '</dl>'
            '<a class="tf-sum-go" href="/trans-afrique/%s">See %s<i>&rarr;</i></a>'
            '</div></li>'
            % (" is-great" if r.get("great") else "", _esc(r["id"]),
               _esc(r["id"]), _esc(r["id"]), _esc(r["name"]),
               len(r.get("countries") or []), chain, _esc(r["id"]),
               _esc(r["say"]), _esc(r["shape"]), _esc(r["days"]),
               "%s&ndash;%s" % (_money(r["low"]), _money(r["high"])),
               _esc("continental" if r["id"] == "great" else r["id"]),
               _esc(short)))

    head = ''
    if title or say:
        head = ('<div class="tf-atlas-head">%s%s</div>'
                % ('<h3 class="tf-atlas-h">%s</h3>' % _esc(title) if title else "",
                   '<p class="tf-atlas-say">%s</p>' % _esc(say) if say else ""))
    return ('<figure class="tf-atlas" data-crossings>'
            '<div class="tf-atlas-art">%s</div>'
            '<figcaption class="tf-atlas-panel">%s'
            '<ol class="tf-picks">%s</ol>%s'
            '</figcaption></figure>'
            % (plate(d, by_slug, only), head, "".join(rows),
               ('<a class="af-btn tf-atlas-go" href="%s">%s<i>&rarr;</i></a>'
                % (_esc(act[1]), _esc(act[0]))) if act else ""))


def _money(n):
    return "${:,}".format(int(n))
