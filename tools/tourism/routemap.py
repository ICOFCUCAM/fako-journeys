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

SO THE TERMINUS RINGS CARRY NO CITY NAME. A larger marker says "this is where
the road starts", which is true of the country; "NAIROBI" printed on Kenya's
centroid would be false by about two hundred kilometres. The city pair lives in
the panel, where the route's own `shape` string says it in words and claims
nothing about a position. What appears on the plate when a crossing is selected
is the COUNTRY name at each node, which is exactly what the node is.

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
import os

from .model import ROOT

MAP = os.path.join(ROOT, "tourism", "map.json")

# How wide each road is drawn. The spine is the road; South is a length of it,
# East a shorter length again, and West is its own arc. Descending width with
# the spine underneath makes the overlap read as nesting rather than as three
# lines fighting, and it is the hierarchy the section argues in words.
WIDTHS = {"great": 7.0, "south": 4.0, "east": 2.6, "west": 4.6}
ORDER = ("great", "south", "east", "west")


def load_map():
    with open(MAP, encoding="utf-8") as fh:
        return json.load(fh)


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

    There is no graticule, no scale bar, no city, no shadow and no label that
    is not a country on a chosen road. Everything else the file could draw was
    left out: this plate has one job, which is to show four journeys, and a map
    that also shows rivers is a map that shows a journey less well.
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
    out.append('<g class="tf-plate-roads" aria-hidden="true">')
    for rid in ORDER:
        r = routes.get(rid)
        if not r:
            continue
        pts = [at[s_] for s_ in (r.get("countries") or []) if s_ in at]
        if len(pts) < 2:
            continue
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
        ends = [s_ for s_ in (r.get("countries") or []) if s_ in at]
        for s_ in ({ends[0], ends[-1]} if len(ends) > 1 else set(ends)):
            out.append('<circle class="tf-term" cx="%.1f" cy="%.1f" r="9.5" '
                       'data-route="%s" data-country="%s"/>'
                       % (at[s_][0], at[s_][1], rid, _esc(s_)))
    out.append('</g>')

    # 6. Country names, one per node, hidden until a crossing is chosen. Drawn
    #    for every route so that choosing one is a CSS state change and not a
    #    re-render, and so the plate is complete with scripting off.
    out.append('<g class="tf-plate-names" aria-hidden="true">')
    for slug in sorted(crosses):
        if slug not in at:
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
    out.append('</svg>')
    return "".join(out)


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
