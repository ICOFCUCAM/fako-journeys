"""Turn Natural Earth boundaries into the inline SVG map on the gateway home page.

    curl -sSLO https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
    python3 tools/africa_map.py ne_50m_admin_0_countries.geojson > map.svg

(TopoJSON in the world-atlas layout is still accepted; a FeatureCollection is
detected and converted.)

The map on the home page is meant to become the way people navigate the whole
platform, which rules out a drawn approximation of the continent: a country you
can click has to be the shape of that country. So the paths come from Natural
Earth — public domain, and the survey world-atlas is itself derived from —
read here, projected once, at build time. Nothing ships to the browser but the
finished path data: no map library, no tiles, no requests, and a map that is
still there with scripting off.

The data file is not vendored. It is 2 MB to carry for something that changes
when borders change, which is to say almost never; the twenty lines above
fetch it when the map next needs regenerating.

Projection is Lambert azimuthal equal-area centred on the middle of the
continent. Africa straddles the equator, so plate carrée leaves the Cape and
the Maghreb visibly stretched, and equal-area keeps countries in honest
proportion to each other — the point of the thing is comparison.
"""

import json
import math
import re
import sys

# ISO 3166-1 numeric, which is what the world-atlas ids are. Listing them beats
# filtering on a bounding box, which drags in Yemen, Israel and half of Iberia.
AFRICA = {
    12: "Algeria", 24: "Angola", 204: "Benin", 72: "Botswana", 854: "Burkina Faso",
    108: "Burundi", 132: "Cabo Verde", 120: "Cameroon", 140: "Central African Rep.",
    148: "Chad", 174: "Comoros", 178: "Congo", 180: "Dem. Rep. Congo", 262: "Djibouti",
    818: "Egypt", 226: "Eq. Guinea", 232: "Eritrea", 748: "Eswatini", 231: "Ethiopia",
    266: "Gabon", 270: "Gambia", 288: "Ghana", 324: "Guinea", 624: "Guinea-Bissau",
    384: "Côte d'Ivoire", 404: "Kenya", 426: "Lesotho", 430: "Liberia", 434: "Libya",
    450: "Madagascar", 454: "Malawi", 466: "Mali", 478: "Mauritania", 480: "Mauritius",
    504: "Morocco", 508: "Mozambique", 516: "Namibia", 562: "Niger", 566: "Nigeria",
    646: "Rwanda", 678: "São Tomé and Príncipe", 686: "Senegal", 690: "Seychelles",
    694: "Sierra Leone", 706: "Somalia", 710: "South Africa", 728: "South Sudan",
    729: "Sudan", 834: "Tanzania", 768: "Togo", 788: "Tunisia", 800: "Uganda",
    894: "Zambia", 716: "Zimbabwe", 732: "W. Sahara", 736: "Sudan",
}

# The roster, by how far along the country is. `ours` is a company of our own,
# `live` has a destination page, `soon` is named but has nothing behind it yet —
# and the map paints all three differently, because a visitor should be able to
# tell at a glance what is bookable today.
#   iso: (slug, label, tagline, href, tier)
ROSTER = {
    # North Africa and the Horn, added when the atlas went past the first
    # twenty-two. ISO 3166-1 numeric, which is what the topojson keys on.
    12:  ("algeria", "Algeria", "The largest country in Africa, and the emptiest", "/algeria", "live"),
    434: ("libya", "Libya", "Leptis Magna, and the sand sea behind it", "/libya", "live"),
    729: ("sudan", "Sudan", "More pyramids than Egypt", "/sudan", "live"),
    728: ("south-sudan", "South Sudan", "The Sudd, and the second-largest migration on earth", "/south-sudan", "live"),
    232: ("eritrea", "Eritrea", "Art deco Asmara, and the Dahlak islands", "/eritrea", "live"),
    262: ("djibouti", "Djibouti", "Where three plates pull apart", "/djibouti", "live"),
    706: ("somalia", "Somalia", "The longest coastline in mainland Africa", "/somalia", "live"),
    120: ("cameroon", "Cameroon", "Africa in miniature", "/cameroon", "ours"),
    800: ("uganda", "Uganda", "The Pearl of Africa", "https://pearl-trails-uganda.vercel.app", "ours"),
    516: ("namibia", "Namibia", "Where the desert meets the wild", "https://namib-skyline.vercel.app", "ours"),
    404: ("kenya", "Kenya", "Where the wild runs free", "/kenya", "live"),
    834: ("tanzania", "Tanzania", "Wild Africa, island Africa", "/tanzania", "live"),
    646: ("rwanda", "Rwanda", "A thousand hills", "/rwanda", "live"),
    894: ("zambia", "Zambia", "Into the real wilderness", "/zambia", "live"),
    710: ("south-africa", "South Africa", "A world in one country", "/south-africa", "live"),
    504: ("morocco", "Morocco", "Atlas, Sahara and the medinas", "/morocco", "live"),
    818: ("egypt", "Egypt", "The Nile, and five thousand years", "/egypt", "live"),
    288: ("ghana", "Ghana", "The forts, the forest and the highlife", "/ghana", "live"),
    231: ("ethiopia", "Ethiopia", "The roof of Africa", "/ethiopia", "live"),
     72: ("botswana", "Botswana", "A delta that never reaches the sea", "/botswana", "live"),
    450: ("madagascar", "Madagascar", "An island that evolved alone", "/madagascar", "live"),
    566: ("nigeria", "Nigeria", "The loudest country on the continent", "/nigeria", "live"),
    686: ("senegal", "Senegal", "Where the Sahel meets the Atlantic", "/senegal", "live"),
    716: ("zimbabwe", "Zimbabwe", "Great Zimbabwe and the Zambezi", "/zimbabwe", "live"),
    508: ("mozambique", "Mozambique", "Two thousand kilometres of coast", "/mozambique", "live"),
    384: ("cote-divoire", "Côte d'Ivoire", "Lagoons, forest and the Atlantic", "/cote-divoire", "live"),
    788: ("tunisia", "Tunisia", "Carthage, the Sahel and the desert south", "/tunisia", "live"),
    690: ("seychelles", "Seychelles", "Granite islands in the Indian Ocean", "/seychelles", "live"),
    480: ("mauritius", "Mauritius", "Reef, sugar and the volcanic interior", "/mauritius", "live"),
}
LIVE = ROSTER          # the map treats every roster country as a marked country

# Small enough that at continental scale they are a pixel or two. They get a
# marker instead of an outline, or they are simply invisible on the map that is
# supposed to be the way into them.
ISLAND_MARKS = {
    690: (55.5, -4.6), 480: (57.5, -20.3), 174: (43.3, -11.7), 132: (-23.6, 16.0),
}

LON0, LAT0 = math.radians(19.0), math.radians(2.0)
VIEW_W, VIEW_H = 1000.0, 1060.0
PAD = 14.0

# A country smaller than this in either direction, in map units, cannot be hit
# with a finger and is given a transparent disc to hit instead. HIT_R is sized
# so that disc lands at roughly 24 CSS pixels on a 390px phone.
SMALL_COUNTRY = 60.0
HIT_R = 34.0
PRECISION = 1          # tenths of a viewBox unit; the map is ~600px wide in use
MIN_RING_AREA = 4.0    # drop specks: unclickable, and they cost bytes
# Measured rather than chosen. At continent scale the map is about 500 CSS px
# wide for a 1000-unit viewBox, so a map unit is half a pixel and 1.2 was
# invisible — but the hero flies to a country, and a country view is ~200 units
# in the same 500px, where one unit is 2.5px and 1.2 was three pixels of error
# on every coastline. Source resolution was never the constraint: 110m and 50m
# simplify to the same thing at tolerance 1.2. The tolerance was.
#
#   tol    vertices   path bytes   error at country zoom
#   1.20      2,192       25 KB         3.0 px
#   0.80      2,844       32 KB         2.0 px
#   0.50      3,825       43 KB         1.3 px
#   0.35      4,711       53 KB         0.9 px      <- sub-pixel, and this
#   0.25      5,717       65 KB         0.6 px
#
# 10m would add nothing here: at country zoom one map unit is 2.5px and 10m
# resolves detail far below a unit, so the tolerance would still be what binds,
# against a 25 MB source instead of a 3 MB one.
TOLERANCE = 0.35       # sub-pixel at the deepest zoom the hero uses
SOLO_TOLERANCE = 2.0   # a silhouette is drawn large, but from a 1000-unit box
# The true-size comparison draws a country inside Africa at a few hundred pixels
# and never zooms. Sharing the hero's tolerance took that block from 31 KB to
# 105 KB of path data inlined on the home page for detail nothing renders: one
# tolerance for artefacts drawn at different sizes is one tolerance too few.
SCALE_TOLERANCE = 2.0


def topology(gj):
    """Natural Earth GeoJSON -> the shape the rest of this module expects.

    The module was written against world-atlas, which is TopoJSON: shared arcs,
    quantised deltas, a transform. Natural Earth publishes GeoJSON, and it is
    the authoritative source world-atlas is itself derived from — so reading it
    directly removes an intermediary and a version to keep in step. It also
    removes a dependency that cannot currently be fetched from here at all.

    No arcs are shared, which costs nothing: the arcs exist so a border drawn
    twice is stored once, and every ring is decoded to absolute coordinates
    immediately afterwards regardless. Each ring becomes its own arc.

    ISO_N3_EH rather than ISO_N3: the `_EH` variants are Natural Earth's own
    "as most maps show it" codes, and plain ISO_N3 is -99 for several African
    entities, which would silently drop them from a continent map.
    """
    arcs, geoms = [], []
    for f in gj["features"]:
        props = f.get("properties") or {}
        raw = props.get("ISO_N3_EH") or props.get("ISO_N3")
        try:
            code = int(raw)
        except (TypeError, ValueError):
            continue
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        polys = [coords] if geom.get("type") == "Polygon" else coords
        out = []
        for poly in polys:
            rings = []
            for r in poly:
                arcs.append([(float(pt[0]), float(pt[1])) for pt in r])
                rings.append([len(arcs) - 1])
            if rings:
                out.append(rings)
        if out:
            geoms.append({"id": str(code), "type": "MultiPolygon", "arcs": out,
                          "properties": {"name": props.get("NAME") or props.get("ADMIN") or ""}})
    return {"objects": {"countries": {"geometries": geoms}}, "arcs": arcs}


def decode(topo):
    """TopoJSON arcs -> absolute lon/lat rings. Deltas are quantised integers.

    A topology built by topology() above carries no transform and its arcs are
    already absolute, so there is nothing to undo.
    """
    if "transform" not in topo:
        return topo["arcs"]
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        out = []
        for dx, dy in arc:
            x += dx
            y += dy
            out.append((x * sx + tx, y * sy + ty))
        arcs.append(out)
    return arcs


def ring(arcs, indices):
    """Stitch one ring. A negative index means that arc, reversed."""
    pts = []
    for i in indices:
        a = arcs[~i][::-1] if i < 0 else arcs[i]
        pts.extend(a[1:] if pts else a)
    return pts


def project(lon, lat):
    """Lambert azimuthal equal-area, y already flipped for screen coordinates."""
    lo, la = math.radians(lon), math.radians(lat)
    cos_c = math.sin(LAT0) * math.sin(la) + math.cos(LAT0) * math.cos(la) * math.cos(lo - LON0)
    k = math.sqrt(2.0 / max(1e-9, 1.0 + cos_c))
    x = k * math.cos(la) * math.sin(lo - LON0)
    y = k * (math.cos(LAT0) * math.sin(la) - math.sin(LAT0) * math.cos(la) * math.cos(lo - LON0))
    return x, -y


def polygons(geom):
    """Every geometry as a list of rings, so Polygon and MultiPolygon are one case."""
    if geom["type"] == "Polygon":
        return [geom["arcs"]]
    if geom["type"] == "MultiPolygon":
        return geom["arcs"]
    return []


def _rdp(points, tol):
    """Douglas-Peucker over an open polyline."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        span = math.hypot(dx, dy)
        worst, at = 0.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            d = (abs(dy * px - dx * py + bx * ay - by * ax) / span) if span else math.hypot(px - ax, py - ay)
            if d > worst:
                worst, at = d, i
        if worst > tol and at > 0:
            keep[at] = True
            stack.append((a, at))
            stack.append((at, b))
    return [p for p, k in zip(points, keep) if k]


def thin(points, tol):
    """Simplify a closed ring.

    50m boundaries draw a far better Cameroon than 110m — the coast stops being a
    polygon — but they carry five times the vertices, and this map is inlined in
    the page. Dropping every vertex within `tol` of the line its neighbours
    already describe keeps the shape and most of the saving.

    A ring has to be cut before it is simplified. Douglas-Peucker anchors on the
    first and last vertex, and on a closed ring those are the same point: the
    baseline has no length, every vertex measures zero away from it, and the
    whole country collapses to two points. So the ring is split at the vertex
    furthest from its start and simplified in two halves.
    """
    if len(points) < 4:
        return points
    closed = points[0] == points[-1]
    ring_pts = points[:-1] if closed else points
    if not closed:
        return _rdp(points, tol)
    ax, ay = ring_pts[0]
    far = max(range(1, len(ring_pts)),
              key=lambda i: (ring_pts[i][0] - ax) ** 2 + (ring_pts[i][1] - ay) ** 2)
    head = _rdp(ring_pts[:far + 1], tol)
    tail = _rdp(ring_pts[far:] + [ring_pts[0]], tol)
    return head[:-1] + tail


def area(points):
    s = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def prune_outliers(rings, share=6.0):
    """Drop far-flung territory that is not what the map is about.

    At 50m, South Africa carries the Prince Edward Islands nineteen hundred
    kilometres into the Southern Ocean. Fitting a silhouette to a bounding box
    that includes them shrinks the country to a third of the frame; fitting the
    continental map to them pushes Africa up and off centre. Zanzibar sits just
    off Tanzania and has to survive, so the test is distance rather than size:
    keep a ring only if it overlaps the main landmass's box, grown by a sixth.
    `share` tightens that for the true-size comparison, where Alaska rides along
    with the United States and doubles the width of a shape meant to be the
    contiguous country people picture.
    """
    if len(rings) < 2:
        return rings
    main = max(rings, key=area)
    xs = [p[0] for p in main]
    ys = [p[1] for p in main]
    mx, my = (max(xs) - min(xs)) / share, (max(ys) - min(ys)) / share
    x0, x1 = min(xs) - mx, max(xs) + mx
    y0, y1 = min(ys) - my, max(ys) + my
    keep = []
    for r in rings:
        rx = [p[0] for p in r]
        ry = [p[1] for p in r]
        if max(rx) >= x0 and min(rx) <= x1 and max(ry) >= y0 and min(ry) <= y1:
            keep.append(r)
    return keep or [main]


def build(topo, tol=None):
    """tol lets a caller drawn at a different size ask for a different fidelity.

    It was a module global, which meant the hero's sub-pixel tolerance also
    applied to the true-size comparison — a silhouette a few hundred pixels
    wide that never zooms — and put 52 KB of invisible coastline on the home
    page.
    """
    tol = TOLERANCE if tol is None else tol
    arcs = decode(topo)
    shapes = []
    for geom in topo["objects"]["countries"]["geometries"]:
        # A few geometries in the set carry no id at all (disputed ground, mostly).
        if not str(geom.get("id", "")).isdigit():
            continue
        code = int(geom["id"])
        if code not in AFRICA:
            continue
        rings = []
        for poly in polygons(geom):
            for part in poly:
                pts = [project(lon, lat) for lon, lat in ring(arcs, part)]
                if len(pts) > 3:
                    rings.append(pts)
        if rings:
            shapes.append((code, geom["properties"]["name"], prune_outliers(rings)))

    # The island marks are part of the map, so they belong in the fit. Left out,
    # Seychelles lands past the right edge of the viewBox and is clipped away.
    flat = [p for _c, _n, rs in shapes for r in rs for p in r]
    flat += [project(lon, lat) for code, (lon, lat) in ISLAND_MARKS.items() if code in ROSTER]
    x0, x1 = min(p[0] for p in flat), max(p[0] for p in flat)
    y0, y1 = min(p[1] for p in flat), max(p[1] for p in flat)
    k = min((VIEW_W - 2 * PAD) / (x1 - x0), (VIEW_H - 2 * PAD) / (y1 - y0))
    ox = (VIEW_W - k * (x1 - x0)) / 2.0 - k * x0
    oy = (VIEW_H - k * (y1 - y0)) / 2.0 - k * y0

    out = []
    for code, name, rings in shapes:
        parts = []
        for r in rings:
            scaled = [(round(p[0] * k + ox, PRECISION), round(p[1] * k + oy, PRECISION)) for p in r]
            scaled = thin(scaled, tol)
            if area(scaled) < MIN_RING_AREA:
                continue
            # Drop a vertex that rounded onto its neighbour rather than emitting it.
            trimmed = [scaled[0]]
            for pt in scaled[1:]:
                if pt != trimmed[-1]:
                    trimmed.append(pt)
            if len(trimmed) > 3:
                parts.append("M" + "L".join("%g %g" % p for p in trimmed) + "Z")
        if parts:
            out.append((code, name, "".join(parts)))
    out.sort(key=lambda s: (s[0] not in ROSTER, s[1]))
    return out, (k, ox, oy)


def marks(shapes):
    """Island states rendered as a marker, since their outline is a pixel here."""
    flat = [p for _c, _n, _d in shapes for p in []]
    return flat


def render(shapes, frame):
    """frame = (k, ox, oy) from build, so the island marks land in the same space."""
    k, ox, oy = frame
    lines = ['<svg class="wa-map-svg" viewBox="0 0 %g %g" role="img" '
             'aria-label="Map of Africa. %d countries are marked; %d have a destination page." '
             'xmlns="http://www.w3.org/2000/svg">'
             % (VIEW_W, VIEW_H, len(ROSTER),
                sum(1 for v in ROSTER.values() if v[4] in ("ours", "live"))),
             '<g class="wa-map-rest" aria-hidden="true">']
    for code, name, d in shapes:
        if code in ROSTER:
            continue
        lines.append('<path d="%s"><title>%s</title></path>' % (d, name))
    lines.append("</g>")
    for code, _name, d in shapes:
        # An island state gets a marker below; drawing its two-pixel outline as
        # well would put two hit areas on the same country.
        if code not in ROSTER or code in ISLAND_MARKS:
            continue
        slug, label, tag, href, tier = ROSTER[code]
        title = "%s &#8212; %s" % (label, tag)
        # tabindex -1: the shape is a pointer target, not a tab stop. The rail of
        # twenty-two names below the map is the keyboard route to the same
        # twenty-two places, and the svg's own label says so. Left in the tab
        # order it put twenty-two stops on shapes inside a role="img" — which a
        # screen reader does not expose in the first place — between the
        # masthead and this page's own calls to action.
        attrs = ('tabindex="-1" class="wa-map-live" data-tier="%s" data-slug="%s" data-name="%s" data-tag="%s"'
                 % (tier, slug, label, tag))
        # A country whose own shape is smaller than SMALL map units in either
        # direction is not a pointer target — Rwanda draws 7.8 by 7.8 CSS pixels
        # on a 390px phone — so it gets a transparent disc at its label anchor
        # to hit instead. Sized to reach roughly 24px at that width. It is
        # allowed to spill into its neighbours: where it overlaps another
        # roster country that country's own path is later in the document and
        # wins, so the only ground it actually takes is the unlisted continent
        # around it, which was not a target to begin with.
        hit = ""
        nums = [float(t) for t in re.findall(r"-?\d+\.?\d*", d)]
        xs, ys = nums[0::2], nums[1::2]
        if xs and min(max(xs) - min(xs), max(ys) - min(ys)) < SMALL_COUNTRY:
            at = anchor(d)
            if at:
                hit = '<circle class="wa-map-hit" cx="%.1f" cy="%.1f" r="%.1f"/>' % (
                    at[0], at[1], HIT_R)
        if href:
            lines.append('<a %s href="%s">%s<path d="%s"/><title>%s</title></a>' % (attrs, href, hit, d, title))
        else:
            lines.append('<g %s>%s<path d="%s"/><title>%s</title></g>' % (attrs, hit, d, title))
    for code, (lon, lat) in sorted(ISLAND_MARKS.items()):
        if code not in ROSTER:
            continue
        slug, label, tag, href, tier = ROSTER[code]
        x, y = project(lon, lat)
        cx, cy = x * k + ox, y * k + oy
        attrs = ('tabindex="-1" class="wa-map-live wa-map-mark" data-tier="%s" data-slug="%s" data-name="%s" data-tag="%s"'
                 % (tier, slug, label, tag))
        # Two circles: a transparent one for the pointer and a smaller one for
        # the eye. At r=9 the visible mark was a six-pixel dot on a phone.
        dot = ('<circle class="wa-map-hit" cx="%.1f" cy="%.1f" r="36"/>'
               '<circle cx="%.1f" cy="%.1f" r="12"/><title>%s &#8212; %s</title>'
               % (cx, cy, cx, cy, label, tag))
        lines.append(('<a %s href="%s">%s</a>' % (attrs, href, dot)) if href
                     else ('<g %s>%s</g>' % (attrs, dot)))
    lines.append("</svg>")
    return "\n".join(lines)


def anchor(d):
    """A point inside a country to hang its label on.

    The centre of a bounding box is wrong for anything shaped like Namibia or
    Mozambique — it lands in the neighbour. This takes the centroid of the
    largest ring, which for every shape on the roster is inside the country.
    """
    rings, best, best_area = d.split("M")[1:], None, -1.0
    for part in rings:
        pts = []
        for pair in part.rstrip("Z").split("L"):
            x, _sep, y = pair.partition(" ")
            if y:
                pts.append((float(x), float(y)))
        if len(pts) < 3:
            continue
        a = area(pts)
        if a > best_area:
            best_area, best = a, pts
    if not best:
        return None
    cx = sum(p[0] for p in best) / len(best)
    cy = sum(p[1] for p in best) / len(best)
    return [round(cx, 1), round(cy, 1)]


def as_map(topo):
    """The continent as data rather than as markup.

    The gateway carries the map as inline SVG, written once and pasted in. That
    is right for one page and wrong for two: the atlas needs the same geometry
    with different behaviour attached to it, and a second copy of thirty
    kilobytes of path data that has to be kept in step by hand is not a map, it
    is a liability. So the geometry is emitted once as JSON and whatever needs
    to draw it builds its own SVG from it.

    `rest` is the continent as context — the countries with nothing behind them
    yet. `live` is the roster: shape, tier, and an anchor to label it at.
    `marks` are the island states, which at continental scale are a dot.
    """
    shapes, (k, ox, oy) = build(topo)
    out = {"view": [0, 0, VIEW_W, VIEW_H], "rest": [], "live": [], "marks": []}
    for code, name, d in shapes:
        if code not in ROSTER:
            out["rest"].append({"n": name, "d": d})
            continue
        if code in ISLAND_MARKS:
            continue            # drawn as a marker below, not as a two-pixel outline
        slug, label, tag, href, tier = ROSTER[code]
        out["live"].append({"slug": slug, "name": label, "tag": tag, "href": href,
                            "tier": tier, "d": d, "at": anchor(d)})
    for code, (lon, lat) in sorted(ISLAND_MARKS.items()):
        if code not in ROSTER:
            continue
        slug, label, tag, href, tier = ROSTER[code]
        x, y = project(lon, lat)
        out["marks"].append({"slug": slug, "name": label, "tag": tag, "href": href,
                             "tier": tier, "at": [round(x * k + ox, 1), round(y * k + oy, 1)],
                             "r": 9})
    return out


# ---- what borders what ------------------------------------------------------------

# Natural Earth's polygons share their boundaries: where two countries meet,
# both carry the same vertices. So adjacency is not something to be looked up in
# a table somebody typed — it is in the geometry, and this reads it out.
#
# The tolerance is in degrees. Neighbouring outlines are usually vertex-for-vertex
# identical along the border; a fifth of a degree (~22 km at the equator) is
# loose enough for the few places where they are only nearly identical, and tight
# enough that Kenya does not come out bordering Zambia.
BORDER_TOL = 0.2
EARTH_KM = 6371.0


def lonlat_rings(topo, arcs, geom):
    """One country's rings in degrees, before any projection."""
    out = []
    for poly in polygons(geom):
        for part in poly:
            pts = list(ring(arcs, part))
            if len(pts) > 3:
                out.append(pts)
    return out


def great_circle(a, b):
    """Kilometres between two lon/lat points, along the surface.

    A straight-line distance is a fact about the map. It is deliberately not
    presented anywhere as a travel time: how long the road takes is a thing this
    project does not know, and a number that looks like an answer is worse than
    no number.
    """
    lo1, la1 = math.radians(a[0]), math.radians(a[1])
    lo2, la2 = math.radians(b[0]), math.radians(b[1])
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(d)))


def centroid_lonlat(rings):
    """The middle of the largest ring, in degrees. Inside the country for every
    shape on this roster, which is what matters for hanging a node on."""
    best = max(rings, key=lambda r: abs(sum(
        r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1]
        for i in range(len(r)))))
    return (round(sum(p[0] for p in best) / len(best), 3),
            round(sum(p[1] for p in best) / len(best), 3))


def links(topo):
    """Who borders whom, and how far apart the middles are.

    Two facts, both read off Natural Earth rather than asserted: a shared land
    border, and the great-circle distance between country centres. Everything
    else the site calls a connection — a shared experience, an overlapping
    season, the same operator — comes from the dataset and is joined to this in
    tools/tourism/links.py. Keeping the geometry here and the editorial there is
    the whole point: one of them can be checked against a map.
    """
    arcs = decode(topo)
    by_slug, centres = {}, {}
    for geom in topo["objects"]["countries"]["geometries"]:
        if not str(geom.get("id", "")).isdigit():
            continue
        code = int(geom["id"])
        if code not in ROSTER:
            continue
        rings = lonlat_rings(topo, arcs, geom)
        if not rings:
            continue
        slug = ROSTER[code][0]
        by_slug[slug] = rings
        centres[slug] = centroid_lonlat(rings)
    # Island states have no outline in the roster geometry at this scale; they
    # get their marker's own position and border nobody, which is true.
    for code, (lon, lat) in ISLAND_MARKS.items():
        if code in ROSTER and ROSTER[code][0] not in centres:
            centres[ROSTER[code][0]] = (lon, lat)

    # A grid over the vertices, so this is a sweep rather than every country
    # against every other country's every point.
    cell = BORDER_TOL
    grid = {}
    for slug, rings in by_slug.items():
        for r in rings:
            for lon, lat in r:
                grid.setdefault((int(lon / cell), int(lat / cell)), set()).add(slug)

    borders = {slug: set() for slug in centres}
    for (gx, gy), here in grid.items():
        near = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near |= grid.get((gx + dx, gy + dy), set())
        for a in here:
            for b in near:
                if a != b:
                    borders[a].add(b)
                    borders[b].add(a)

    out = {"centres": {}, "borders": {}, "km": {}}
    for slug in sorted(centres):
        out["centres"][slug] = list(centres[slug])
        out["borders"][slug] = sorted(borders.get(slug, ()))
    for a in sorted(centres):
        out["km"][a] = {b: int(round(great_circle(centres[a], centres[b])))
                        for b in sorted(centres) if b != a}
    return out


SOLO_BOX = 1000.0       # the long side of a single-country silhouette


# The true-size comparison. Africa is 30.4 million km2 and the world map most
# people carry in their heads is Mercator, which inflates everything away from
# the equator and shrinks everything on it. These four are projected with the
# same equal-area projection as the continent — each centred on itself, which is
# what keeps the areas honest — scaled by the same factor, and nested inside.
# The offsets are the only hand-set numbers: where a shape sits is composition.
# Each is laid into the middle of the continent one at a time rather than packed
# alongside the others: four irregular outlines that between them cover most of
# Africa's area do not tile, and a packing tuned by eye would be the one part of
# this that was not honest geometry. Offsets centre each shape in the outline.
SCALE_SET = (
    (840, "United States", "9.8", (62, 200)),
    (156, "China", "9.6", (174, 283)),
    (356, "India", "3.3", (290, 342)),
    ((250, 276, 724, 380, 826, 616, 620, 300, 208, 756, 40, 56, 528, 203, 348),
     "Western Europe", "3.9", (329, 377)),
)


def centroid(rings):
    flat = [p for r in rings for p in r]
    return (sum(p[0] for p in flat) / len(flat), sum(p[1] for p in flat) / len(flat))


def land_path(topo):
    """Africa as one silhouette, with the internal borders left out.

    The comparison is about the whole continent, and a country grid inside it
    invites the eye to read borders instead of area.
    """
    shapes, _frame = build(topo, SCALE_TOLERANCE)
    return "".join(d for _code, _name, d in shapes)


def scale_shapes(topo):
    """Each comparison country, drawn in the continental map's own units.

    Projected about its own centre rather than about Africa's: an azimuthal
    equal-area projection preserves area from any centre, and centring each on
    itself avoids the shear that would make the comparison look rigged.
    """
    global LON0, LAT0
    _shapes, (k, _ox, _oy) = build(topo, SCALE_TOLERANCE)
    arcs = decode(topo)
    keep = LON0, LAT0
    by_code = {}
    for geom in topo["objects"]["countries"]["geometries"]:
        if str(geom.get("id", "")).isdigit():
            by_code[int(geom["id"])] = geom

    out = []
    for codes, label, area_mkm2, (tx, ty) in SCALE_SET:
        codes = codes if isinstance(codes, tuple) else (codes,)
        lonlat = []
        for code in codes:
            geom = by_code.get(code)
            if not geom:
                continue
            for poly in polygons(geom):
                for part in poly:
                    pts = ring(arcs, part)
                    if len(pts) > 3:
                        lonlat.append(pts)
        if not lonlat:
            continue
        lon0, lat0 = centroid(lonlat)
        LON0, LAT0 = math.radians(lon0), math.radians(lat0)
        rings = [[project(lo, la) for lo, la in r] for r in lonlat]
        rings = prune_outliers(rings, share=2.5)
        LON0, LAT0 = keep
        flat = [p for r in rings for p in r]
        x0 = min(p[0] for p in flat)
        y0 = min(p[1] for p in flat)
        parts = []
        for r in rings:
            pts = [(round((p[0] - x0) * k, PRECISION), round((p[1] - y0) * k, PRECISION)) for p in r]
            pts = thin(pts, SCALE_TOLERANCE)
            if area(pts) < MIN_RING_AREA * 4:
                continue
            trimmed = [pts[0]]
            for pt in pts[1:]:
                if pt != trimmed[-1]:
                    trimmed.append(pt)
            if len(trimmed) > 3:
                parts.append("M" + "L".join("%g %g" % p for p in trimmed) + "Z")
        if parts:
            out.append({"label": label, "area": area_mkm2, "x": tx, "y": ty,
                        "d": "".join(parts)})
    return out


def views(topo):
    """Every roster country's box in the continental map's own coordinates.

    The map is meant to be navigated, not looked at: Africa, then a region, then
    a country. That needs each country's extent in the same space the continent
    is drawn in, so the viewBox can be animated to it. Computed here, at build
    time, because it is geometry and the browser should not be deriving it.
    """
    shapes, (k, ox, oy) = build(topo)
    arcs = decode(topo)
    out = {}
    for geom in topo["objects"]["countries"]["geometries"]:
        if not str(geom.get("id", "")).isdigit():
            continue
        code = int(geom["id"])
        entry = ROSTER.get(code)
        if not entry:
            continue
        rings = []
        for poly in polygons(geom):
            for part in poly:
                pts = [project(lon, lat) for lon, lat in ring(arcs, part)]
                if len(pts) > 3:
                    rings.append(pts)
        if code in ISLAND_MARKS:
            lon, lat = ISLAND_MARKS[code]
            x, y = project(lon, lat)
            rings = [[(x, y)]]
        if not rings:
            continue
        rings = prune_outliers(rings) if len(rings[0]) > 1 else rings
        flat = [(p[0] * k + ox, p[1] * k + oy) for r in rings for p in r]
        x0, x1 = min(p[0] for p in flat), max(p[0] for p in flat)
        y0, y1 = min(p[1] for p in flat), max(p[1] for p in flat)
        out[entry[0]] = [round(x0, 1), round(y0, 1),
                         round(max(x1 - x0, 24), 1), round(max(y1 - y0, 24), 1)]
    return {"africa": [0, 0, VIEW_W, VIEW_H], "countries": out}


def solo(topo):
    """Each live country on its own, normalised — the hero window's shape.

    The window in the hero is the outline of the country you are looking at, so
    every silhouette has to arrive centred in a box of its own rather than in
    its place on the continent. Proportions stay true; only the framing changes.
    """
    arcs = decode(topo)
    out = {}
    for geom in topo["objects"]["countries"]["geometries"]:
        if not str(geom.get("id", "")).isdigit():
            continue
        entry = ROSTER.get(int(geom["id"]))
        if not entry or entry[4] == "soon":
            continue
        rings = []
        for poly in polygons(geom):
            for part in poly:
                pts = [project(lon, lat) for lon, lat in ring(arcs, part)]
                if len(pts) > 3:
                    rings.append(pts)
        rings = prune_outliers(rings)
        flat = [p for r in rings for p in r]
        x0, x1 = min(p[0] for p in flat), max(p[0] for p in flat)
        y0, y1 = min(p[1] for p in flat), max(p[1] for p in flat)
        k = SOLO_BOX / max(x1 - x0, y1 - y0)
        w, h = (x1 - x0) * k, (y1 - y0) * k
        parts = []
        for r in rings:
            pts = [(round((p[0] - x0) * k, PRECISION), round((p[1] - y0) * k, PRECISION)) for p in r]
            pts = thin(pts, SOLO_TOLERANCE)
            if area(pts) < MIN_RING_AREA:
                continue
            trimmed = [pts[0]]
            for pt in pts[1:]:
                if pt != trimmed[-1]:
                    trimmed.append(pt)
            if len(trimmed) > 3:
                parts.append("M" + "L".join("%g %g" % p for p in trimmed) + "Z")
        slug = entry[0]
        out[slug] = {"w": round(w, 1), "h": round(h, 1), "d": "".join(parts)}
    return out


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.strip().splitlines()[2].strip())
    with open(sys.argv[1]) as fh:
        topo = json.load(fh)
    if topo.get("type") == "FeatureCollection":
        topo = topology(topo)
    if len(sys.argv) == 3 and sys.argv[2] == "--scale":
        data = {"africa": "30.4", "land": land_path(topo), "shapes": scale_shapes(topo)}
        text = json.dumps(data, indent=1)
        sys.stderr.write("%d comparison shapes, %.1f KB\n" % (len(data["shapes"]), len(text) / 1024.0))
        print(text)
    elif len(sys.argv) == 3 and sys.argv[2] == "--views":
        data = views(topo)
        text = json.dumps(data, indent=1, sort_keys=True)
        sys.stderr.write("%d country views, %.1f KB\n" % (len(data["countries"]), len(text) / 1024.0))
        print(text)
    elif len(sys.argv) == 3 and sys.argv[2] == "--links":
        data = links(topo)
        text = json.dumps(data, indent=1, sort_keys=True)
        pairs = sum(len(v) for v in data["borders"].values()) // 2
        sys.stderr.write("%d countries, %d shared land borders, %.1f KB\n"
                         % (len(data["centres"]), pairs, len(text) / 1024.0))
        print(text)
    elif len(sys.argv) == 3 and sys.argv[2] == "--map":
        data = as_map(topo)
        text = json.dumps(data, indent=1, sort_keys=True)
        sys.stderr.write("%d context countries, %d on the roster, %d island marks, %.1f KB\n"
                         % (len(data["rest"]), len(data["live"]), len(data["marks"]),
                            len(text) / 1024.0))
        print(text)
    elif len(sys.argv) == 3 and sys.argv[2] == "--solo":
        shapes = solo(topo)
        text = json.dumps(shapes, indent=1, sort_keys=True)
        sys.stderr.write("%d silhouettes, %.1f KB\n" % (len(shapes), len(text) / 1024.0))
        print(text)
    else:
        shapes, frame = build(topo)
        svg = render(shapes, frame)
        sys.stderr.write("%d countries, %d on the roster, %.1f KB of path data\n"
                         % (len(shapes), sum(1 for c, _, _ in shapes if c in ROSTER), len(svg) / 1024.0))
        print(svg)
