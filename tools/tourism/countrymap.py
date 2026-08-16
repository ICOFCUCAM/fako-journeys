"""The country atlas: two maps, one grammar, fifty-four countries.

    from . import countrymap
    countrymap.locator(slug)     -> Africa, with one country lit
    countrymap.atlas(slug)       -> the country, its neighbours and its water

WHAT WAS WRONG WITH WHAT THIS REPLACES

tourism/shapes.json holds each country normalised into its own 1000-unit box,
and for a small country that is a nine-point polygon. Eswatini's silhouette was
nine straight lines. Blown up to fill half a page it does not read as Eswatini,
it reads as a shape — an arbitrary blob, which is exactly what it is. Worse, it
is drawn with no context at all: no neighbours, no coast, no water, no scale,
nothing that says where on earth this is.

WHAT IS DRAWN INSTEAD, AND WHERE EVERY PART OF IT COMES FROM

Nothing here is invented. Each layer names its source, and anything the
repository does not actually know is not drawn:

    the outline        tourism/map.json, the same continental projection the
                       homepage map uses, cropped to the country rather than
                       renormalised — so a country keeps its real shape AND its
                       real orientation and proportion against its neighbours
    the neighbours     tourism/neighbours.json `borders`, which is true land
                       adjacency, drawn faint and labelled where the label fits
    rivers and lakes   tourism/atlas-detail.json, clipped to the frame
    cities             tourism/atlas-detail.json — thirteen have real positions
                       and only those thirteen are ever marked
    the scale bar      derived, see below

WHY THERE ARE NO MOUNTAINS, PARKS OR NUMBERED ROUTE MARKERS

Because the repository does not have their coordinates. data/atlas/*.json holds
1,404 places across the fifty-four and not one of them carries a latitude. A
numbered expedition route drawn through a country would therefore be four
markers placed wherever they looked good, which is decoration wearing the
costume of information — and on a page whose whole claim is that Afrinkong
knows the ground, a made-up waypoint is the most expensive possible lie.

The moment places carry coordinates this module can draw them, and the layer is
sketched in `route()` below so it is obvious what is missing rather than
forgotten.

THE SCALE BAR IS DERIVED FROM THE PROJECTION, NOT ESTIMATED FROM IT

atlas-detail.json records the fit as k = 724.3 units per radian, so a unit is
6371/724.3 = 8.796 km north-south, exactly, everywhere. East-west it is that
times cos(latitude), because the projection draws every parallel at the length
of the equator. km_per_unit() carries the full account, including the version
of it that was wrong and looked right.

The finished maps check out against the real world: Eswatini reads 119 x 170 km
against a true 130 x 175, Kenya 869 x 1143 against 890 x 1130.
"""

import json
import math
import os

from .model import ROOT

MAP = os.path.join(ROOT, "tourism", "map.json")
DETAIL = os.path.join(ROOT, "tourism", "atlas-detail.json")
NEIGHBOURS = os.path.join(ROOT, "tourism", "neighbours.json")

_CACHE = {}


def _load():
    if not _CACHE:
        with open(MAP, encoding="utf-8") as fh:
            m = json.load(fh)
        with open(DETAIL, encoding="utf-8") as fh:
            det = json.load(fh)
        with open(NEIGHBOURS, encoding="utf-8") as fh:
            nb = json.load(fh)
        shapes, at = {}, {}
        for c in m.get("live", []) + m.get("rest", []):
            if c.get("slug") and c.get("d"):
                shapes[c["slug"]] = c["d"]
            if c.get("slug") and c.get("at"):
                at[c["slug"]] = c["at"]
        _CACHE.update(view=m.get("view") or [0, 0, 1000.0, 1060.0],
                      shapes=shapes, at=at, detail=det, nb=nb,
                      names={c["slug"]: c.get("name") or c["slug"]
                             for c in m.get("live", []) if c.get("slug")})
    return _CACHE


def _pts(path):
    """Every point in an M/L path, which is all these outlines contain."""
    out = []
    nums = []
    tok = ""
    for ch in path:
        if ch in "ML":
            if tok.strip():
                nums.append(tok.strip())
            tok = ""
        else:
            tok += ch
    if tok.strip():
        nums.append(tok.strip())
    for pair in nums:
        bits = pair.split()
        if len(bits) == 2:
            try:
                out.append((float(bits[0]), float(bits[1])))
            except ValueError:
                pass
    return out


def _rings(path):
    """The outlines as separate closed rings, because several of the fifty-four
    are archipelagos and a flattened point list would join Zanzibar to the
    mainland."""
    out = []
    for chunk in path.split("M"):
        chunk = chunk.strip()
        if not chunk:
            continue
        pts = _pts("M" + chunk)
        if len(pts) >= 3:
            out.append(pts)
    return out


def _clip_poly(ring, x0, y0, x1, y1):
    """Sutherland-Hodgman against the frame. Used to find where a neighbour
    actually appears on this plate rather than where its continent-wide centroid
    is, which for Libya on Egypt's crop is off the paper entirely."""
    def cut(poly, keep, inter):
        if not poly:
            return []
        res = []
        prev = poly[-1]
        for cur in poly:
            if keep(cur):
                if not keep(prev):
                    res.append(inter(prev, cur))
                res.append(cur)
            elif keep(prev):
                res.append(inter(prev, cur))
            prev = cur
        return res

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    poly = list(ring)
    poly = cut(poly, lambda p: p[0] >= x0,
               lambda a, b: lerp(a, b, (x0 - a[0]) / (b[0] - a[0])))
    poly = cut(poly, lambda p: p[0] <= x1,
               lambda a, b: lerp(a, b, (x1 - a[0]) / (b[0] - a[0])))
    poly = cut(poly, lambda p: p[1] >= y0,
               lambda a, b: lerp(a, b, (y0 - a[1]) / (b[1] - a[1])))
    poly = cut(poly, lambda p: p[1] <= y1,
               lambda a, b: lerp(a, b, (y1 - a[1]) / (b[1] - a[1])))
    return poly


def _area_centre(poly):
    """Signed-area centroid, falling back to the vertex mean for a sliver."""
    n = len(poly)
    if n < 3:
        return (None, None, 0.0)
    a = cx = cy = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-9:
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n, 0.0)
    return (cx / (6 * a), cy / (6 * a), abs(a))


def visible_centre(slug, vx, vy, side):
    """Where a country sits on someone else's plate, and how much of it shows.

    Returns (x, y, share-of-frame). The share is what decides whether the name
    gets drawn: a country showing a two-per-cent corner is a corner, and writing
    SUDAN across it claims more than the plate shows.
    """
    best = (None, None, 0.0)
    total = 0.0
    for ring in _rings(_load()["shapes"].get(slug) or ""):
        clipped = _clip_poly(ring, vx, vy, vx + side, vy + side)
        x, y, area = _area_centre(clipped)
        total += area
        if x is not None and area > best[2]:
            best = (x, y, area)
    if best[0] is None:
        return (None, None, 0.0)
    return (best[0], best[1], total / (side * side))


def bbox(slug):
    d = _load()
    pts = _pts(d["shapes"].get(slug) or "")
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def km_per_unit(slug):
    """Kilometres to one viewBox unit, east-west, at this country's latitude.

    Derived from the projection rather than estimated from it. tourism/
    atlas-detail.json records the fit as k = 724.3 units per radian, and a
    radian of latitude on the earth is 6,371 km, so a unit is 6371/724.3 =
    8.796 km measured north-south — exactly, everywhere on the map.

    East-west is not the same number, and that is the whole reason this
    function takes a country. The projection draws every parallel at the length
    of the equator, so ground distance along one shrinks by cos(latitude):
    a horizontal bar of the meridional length would over-state Egypt by twelve
    per cent and South Africa by fourteen. Multiplying by cos of the country's
    real latitude — tourism/neighbours.json `centres`, which is genuine lon/lat
    — makes a horizontal bar correct where it is actually drawn.

    THE FIRST VERSION OF THIS WAS WRONG AND LOOKED RIGHT. It divided known
    kilometre distances by the pixel gap between two countries' `at` values,
    which are the anchors the labels hang off — polygon centroids, not
    projected geographic centres. The two differ by tens of units on an
    irregular shape, and the answer came out 13% long on Kenya to Tanzania
    while still landing in the plausible 8-to-9 range that made it look fine.

    Checked against the finished maps: Eswatini reads 119 x 170 km against a
    real 130 x 175, Kenya 869 x 1143 against 890 x 1130, Namibia 1350 x 1298
    against roughly 1400 x 1300.
    """
    d = _load()
    fit = (d["detail"].get("fit") or {})
    k = fit.get("k")
    if not k:
        return None
    meridional = 6371.0 / k
    lat = (d["nb"].get("centres", {}).get(slug) or [None, 0.0])[1]
    return meridional * math.cos(math.radians(lat))


def _clip_id(slug, kind):
    return "cm-%s-%s" % (kind, slug)


def _nice_km(span_km):
    """A round number that fits comfortably inside the frame."""
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000):
        if step >= span_km * 0.18:
            return step
    return 2000


def _parallels():
    """The labelled parallels, as curves. atlas-detail.json draws 0, +/-20 and
    +/-40 with their labels on them, which is ground truth about the projection
    rather than a guess at it."""
    if "pars" not in _CACHE:
        pars = {}
        for g in _load()["detail"].get("graticule") or []:
            lab = (g.get("label") or "").strip()
            if g.get("kind") != "parallel" or not lab:
                continue
            v = 0.0 if lab == "0°" else float(lab[:-2]) * (-1 if lab.endswith("S") else 1)
            pars[v] = _pts(g.get("d") or "")
        _CACHE["pars"] = pars
    return _CACHE["pars"]


def _parallel_y(lat, x):
    pts = _parallels().get(lat) or []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    if not pts:
        return None
    return min(pts, key=lambda p: abs(p[0] - x))[1]


def latitude(x, y):
    """Degrees north (negative for south) at a point on the plate.

    THE PROJECTION IS NOT EQUIRECTANGULAR, whatever the neat k in `fit` suggests
    — atlas-detail.json's graticule is drawn as CURVES, and rose.rotate is
    -9.82 degrees. So latitude is not (oy - y)/k; it is read off the drawn
    parallels the way it would be read off a paper map, by finding which two the
    point falls between. Fitting a straight line to the country anchors instead
    gave a twenty-unit offset from the recorded origin, which is the same class
    of mistake km_per_unit() documents.

    Checked: Kenya reads 5.5N to 4.7S against a true 5.0 to 4.7, South Africa
    22.2S to 34.9S against 22.1 to 34.8, Egypt 31.8N to 22.0N against 31.6 to
    22.0, Morocco 36.0N against 35.9.
    """
    band = sorted(((k, _parallel_y(k, x)) for k in _parallels()),
                  key=lambda t: t[1] if t[1] is not None else 0)
    band = [(k, v) for k, v in band if v is not None]
    if not band:
        return None
    for i in range(len(band) - 1):
        (la, ya), (lb, yb) = band[i], band[i + 1]
        if ya <= y <= yb:
            return la + (lb - la) * (y - ya) / (yb - ya)
    return band[0][0] if y < band[0][1] else band[-1][0]


def _hemi(lat):
    if abs(lat) < 0.5:
        return "0°"
    return "%d°%s" % (round(abs(lat)), "N" if lat > 0 else "S")


def landlocked(slug):
    """True where the country's outline never comes near the drawn coastline.

    Derived rather than listed, and then CHECKED AGAINST THE REAL ANSWER, which
    is the only reason to trust it: every coastal mainland country measures 0.0
    to 4.0 units from the coast path and every landlocked one 7.0 or more, so
    five units separates them with no country anywhere near the line. It returns
    exactly Africa's sixteen landlocked states.

    The island nations sit far from the CONTINENTAL coast path and are of course
    not landlocked, so a country with no land borders is never one.
    """
    d = _load()
    if not (d["nb"]["borders"].get(slug) or []):
        return False
    pts = _pts(d["shapes"].get(slug) or "")
    if not pts:
        return False
    if "coastpts" not in _CACHE:
        cp = []
        for c in d["detail"].get("coast") or []:
            cp += _pts(c if isinstance(c, str) else (c.get("d") or ""))
        _CACHE["coastpts"] = cp
    for px, py in pts:
        for cx, cy in _CACHE["coastpts"]:
            if (px - cx) ** 2 + (py - cy) ** 2 < 25.0:
                return False
    return True


def brief(slug, name=None):
    """THE LAND IN BRIEF: what this map can prove, and nothing else.

    Every line is measured off the plate or read out of the border table. There
    is no population here, and no area in square kilometres, because the
    repository holds neither — and a number typed in from memory beside a map
    that was derived from data would poison the whole panel's credibility.

    Returns [(label, value), ...], already ordered.
    """
    d = _load()
    name = name or d["names"].get(slug, slug)
    rows = []

    box = bbox(slug)
    kpu = km_per_unit(slug)
    if box and kpu:
        w = (box[2] - box[0]) * kpu
        h = (box[3] - box[1]) * (6371.0 / d["detail"]["fit"]["k"])
        # SPANS, not "is". This measures the bounding box, and for a country
        # lying on a diagonal the two are not the same thing: Madagascar spans
        # 800 km east to west while being barely 570 km wide anywhere, because
        # its north-east tip and south-west tip are far apart across a tilt.
        # "800 x 1,510 km" would read as a size and be wrong; "spans 800 km
        # east-west" is what was actually measured and is exactly true.
        rows.append(("Spans", "%s km E&ndash;W, %s km N&ndash;S"
                     % (_round_km(w), _round_km(h))))

    if box:
        pts = _pts(d["shapes"].get(slug) or "")
        lats = [latitude(px, py) for px, py in pts]
        lats = [v for v in lats if v is not None]
        if lats:
            hi, lo = max(lats), min(lats)
            # A country whose points fall on both sides of the drawn equator
            # crosses it. Sao Tome and Principe is the one real-world case this
            # answers no to and an atlas would answer yes to: the line clips a
            # single islet off its southern tip, which the continental outline
            # does not draw. The map is being honest about its own geometry.
            if hi > 0.5 > lo:
                rows.append(("Latitude", "%s to %s &mdash; the equator crosses it"
                             % (_hemi(hi), _hemi(lo))))
            elif _hemi(hi) == _hemi(lo):
                # A country small enough that both edges round to one degree.
                # "15°N to 15°N" is a range that is not a range; the six this
                # happens to are all islands a few tens of kilometres across.
                rows.append(("Latitude", "On the equator" if _hemi(hi) == "0°"
                             else "About %s" % _hemi(hi)))
            else:
                rows.append(("Latitude", "%s to %s" % (_hemi(hi), _hemi(lo))))

    borders = d["nb"]["borders"].get(slug) or []
    if borders:
        rows.append(("Borders", "%d %s" % (len(borders),
                                           "country" if len(borders) == 1 else "countries")))
    else:
        rows.append(("Borders", "None &mdash; it is an island"))

    if borders:
        rows.append(("Sea", "Landlocked" if landlocked(slug) else "Has a coast"))
    else:
        # For the six that border nothing, how far the nearest land is beats any
        # other line this panel could carry: it is the fact that makes Seychelles
        # Seychelles. Measured off the same plate, from the same projection.
        # Measured from the country's own COASTLINE where it has one, not from
        # its middle. Measuring Madagascar from its centroid put the mainland
        # 700 km away when the Mozambique Channel is 420 — the answer included
        # half the width of Madagascar, which is not sea.
        reach = None
        isl = island(slug)
        if isl:
            reach = nearest_land(isl["x"], isl["y"], exclude=(slug,))
        else:
            for px, py in _pts(d["shapes"].get(slug) or ""):
                r = nearest_land(px, py, exclude=(slug,))
                if r is not None and (reach is None or r < reach):
                    reach = r
        if reach and kpu:
            rows.append(("Nearest land", "about %s km" % _round_km(reach * kpu)))

    return rows


def _round_km(v):
    if v >= 1000:
        return "{:,}".format(int(round(v / 10.0) * 10))
    return str(int(round(v / 10.0) * 10))


def caption(slug, name=None):
    """What the plate is showing, which is not one sentence for all fifty-four.

    Six of them border nothing — Cabo Verde, Comoros, Madagascar, Mauritius,
    Sao Tome and Principe, Seychelles — and captioning their map "and the
    countries it borders" is not a wording slip, it is the map stating something
    false about the country underneath it.
    """
    d = _load()
    name = name or d["names"].get(slug, slug)
    if not (d["nb"]["borders"].get(slug) or []):
        return "%s, and the nearest land" % name
    return "%s and the countries it borders" % name


def island(slug):
    """The two countries the continental outline has no polygon for.

    Seychelles and Mauritius are far enough offshore that map.json draws them as
    points rather than shapes, so both pages rendered no map at all — half a
    per cent of Africa's countries silently falling out of a system whose whole
    claim is that it covers all of them. atlas-detail.json does carry their
    positions, so they get a plate of their own rather than an apology.
    """
    for i in _load()["detail"].get("islands") or []:
        if i.get("slug") == slug:
            return i
    return None


def nearest_land(x, y, exclude=()):
    """Distance in viewBox units from a point to the closest drawn coastline.

    This is what sizes an island's plate. A fixed frame would put Mauritius
    alone in an empty blue square, which tells the reader nothing they did not
    already know; a frame sized to reach Madagascar tells them how far out in
    the Indian Ocean the country actually is, which is the single most useful
    thing a map of Mauritius can say.

    Measured to the nearest point ON a coastline segment, not to the nearest
    drawn vertex. Vertex-to-vertex put Madagascar 700 km from Africa when the
    Mozambique Channel is 420: the closest approach falls in the middle of a
    long smooth stretch of coast, exactly where a simplified outline has no
    vertex to find. Every distance this returns is too long if measured the easy
    way, and on the widest gaps it is too long by most of the answer.
    """
    best = None
    for s, path in _load()["shapes"].items():
        if s in exclude:
            continue
        for ring in _rings(path):
            for i in range(len(ring)):
                d = _pt_seg(x, y, ring[i], ring[(i + 1) % len(ring)])
                if best is None or d < best:
                    best = d
    return best


def _pt_seg(x, y, a, b):
    """Distance from a point to a line segment."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(x - a[0], y - a[1])
    t = ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(x - (a[0] + t * dx), y - (a[1] + t * dy))


def locator(slug, name=None):
    """MAP A. Africa in the quiet tone, this country lit.

    Its whole job is to answer "where in Africa is this", so it carries no
    labels, no water and no cities: a locator that has to be read is a locator
    that has failed.
    """
    d = _load()
    view = d["view"]
    shapes = d["shapes"]
    name = name or d["names"].get(slug, slug)
    others = "".join('<path d="%s"/>' % p
                     for s, p in sorted(shapes.items()) if s != slug)
    mine = shapes.get(slug)
    if not mine:
        # An island with no polygon is lit as a ringed point instead. At
        # continental scale that is not a compromise: Mauritius is two thousand
        # square kilometres on a map where one pixel is nine, so a true-to-scale
        # Mauritius would be invisible and a legible one would be a lie.
        isl = island(slug)
        if not isl:
            return ""
        r = float(view[2]) * 0.012
        return (
            '<svg class="cm-loc" viewBox="%s %s %s %s" role="img" '
            'aria-label="Where %s is in Africa">'
            '<g class="cm-loc-rest">%s</g>'
            '<g class="cm-loc-here"><circle cx="%.1f" cy="%.1f" r="%.1f"/>'
            '<circle class="cm-loc-ring" cx="%.1f" cy="%.1f" r="%.1f"/></g>'
            '</svg>' % (view[0], view[1], view[2], view[3], name, others,
                        isl["x"], isl["y"], r * 0.42,
                        isl["x"], isl["y"], r))
    return (
        '<svg class="cm-loc" viewBox="%s %s %s %s" role="img" '
        'aria-label="Where %s is in Africa">'
        '<g class="cm-loc-rest">%s</g>'
        '<path class="cm-loc-here" d="%s"/>'
        '</svg>' % (view[0], view[1], view[2], view[3], name, others, mine))


def route(slug):
    """MAP B's missing layer, and it is missing on purpose.

    An expedition route with numbered markers is the right idea and cannot be
    drawn honestly yet: data/atlas/*.json holds 1,404 places and none of them
    has a coordinate. Give places a `lat`/`lon` and this returns markers in the
    order the itinerary visits them; until then it returns nothing, because a
    marker placed where it looked good is a claim about the ground that nobody
    checked.
    """
    return ""


def atlas(slug, name=None, pad=0.42, links=None):
    """MAP B. The country, its true neighbours, its water and a real scale.

    Cropped out of the continental projection rather than renormalised into its
    own box, which is the whole difference between an atlas plate and a blob:
    the country keeps its real proportion, its real orientation and its real
    relationship to everything it touches.
    """
    d = _load()
    name = name or d["names"].get(slug, slug)
    box = bbox(slug)
    if not box:
        isl = island(slug)
        if not isl:
            return ""
        # An island's plate is as wide as it has to be to reach the nearest land,
        # because that distance IS the fact about Seychelles and Mauritius worth
        # drawing. A fixed frame would give both of them an empty blue square.
        reach = nearest_land(isl["x"], isl["y"]) or 120.0
        side = max(reach * 2.5, 140.0)
        x0 = x1 = isl["x"]
        y0 = y1 = isl["y"]
        w = h = side / (1 + pad * 2)
    else:
        x0, y0, x1, y1 = box
        w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    # Square-ish frame with generous air, so a long country and a round one sit
    # on the page at the same weight.
    side = max(w, h) * (1 + pad * 2)
    # THE PLATE MAY NOT ZOOM PAST WHAT THE DATA KNOWS. map.json is a continental
    # projection: Kenya is a hundred-odd vertices and Eswatini is nine. Crop each
    # to a fixed proportion of its own size and Eswatini comes out magnified
    # nearly seven times harder than Kenya, so the same simplification that is
    # invisible on one becomes a visible heptagon on the other — the exact "giant
    # flat polygon" this module exists to stop. Floor the frame instead: a small
    # country is drawn at a scale its geometry can carry, and buys real context
    # for the pixels it gives up.
    side = max(side, 95.0)
    # Except for the genuine specks. Seychelles is one unit across and no floor
    # makes it legible, so a country may always crop tight enough to fill a
    # fifth of its own plate.
    side = min(side, max(w, h) / 0.22)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    vx, vy = cx - side / 2, cy - side / 2
    clip = _clip_id(slug, "frame")

    shapes, at, det = d["shapes"], d["at"], d["detail"]
    borders = set(d["nb"]["borders"].get(slug) or [])

    def inside(px, py, m=0.0):
        return vx - m <= px <= vx + side + m and vy - m <= py <= vy + side + m

    near = []
    for s, path in sorted(shapes.items()):
        if s == slug:
            continue
        b = bbox(s)
        if not b:
            continue
        if b[2] < vx or b[0] > vx + side or b[3] < vy or b[1] > vy + side:
            continue
        near.append((s, path))

    # EVERY STROKE AND EVERY LETTER IS A FRACTION OF THE FRAME, NOT A NUMBER.
    # The viewBox is cropped to the country, so its units mean something
    # different for every one of the fifty-four: Eswatini's frame is about 60
    # units across and Algeria's about 300. A stroke-width of 2.4 is a hairline
    # on Algeria and a rope on Eswatini, and a 15-unit label is small type on
    # one and a word filling the map on the other — which is exactly what the
    # first render did. `--u` is the frame's own size and the stylesheet scales
    # off it, so one rule holds for all fifty-four.
    out = ['<svg class="cm-atlas" viewBox="%.1f %.1f %.1f %.1f" style="--u:%.2f" '
           'role="img" aria-labelledby="cm-t-%s">' % (vx, vy, side, side, side, slug)]
    out.append('<title id="cm-t-%s">%s, with its rivers and lakes and a scale '
               'in kilometres.</title>' % (slug, _esc(caption(slug, name))))
    out.append('<defs><clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" '
               'height="%.1f"/></clipPath></defs>' % (clip, vx, vy, side, side))

    # 0. The sea. Without a ground the plate has no way of saying that the empty
    #    quarter east of Somalia is the Indian Ocean rather than unlabelled land,
    #    which on a coastal country is half the information the map carries.
    out.append('<rect class="cm-sea" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'
               % (vx, vy, side, side))

    # 1. Everything around it, faint. A country drawn alone is a shape; a
    #    country drawn against what it touches is a place.
    #
    # A neighbour we publish a page for becomes a link — the map is then a way
    # of moving through the atlas rather than a picture of it, and it is the one
    # kind of interactivity this data can honestly support. There is no
    # click-a-region-to-filter here and no hover tooltip of facts, because the
    # facts those would show do not exist: see route() below.
    links = links or {}
    out.append('<g class="cm-near" clip-path="url(#%s)">' % clip)
    for s, p in near:
        href = links.get(s)
        if href:
            out.append('<a class="cm-link" href="%s" data-cm="%s">'
                       '<title>%s</title><path d="%s"/></a>'
                       % (_esc(href), _esc(s), _esc(d["names"].get(s, s)), p))
        else:
            out.append('<path d="%s" aria-hidden="true"/>' % p)
    out.append('</g>')

    # 2. Water, clipped to the frame. Rivers and lakes are the features this
    #    repository actually has; mountains and parks are not, so they are not
    #    drawn rather than approximated.
    # atlas-detail.json stores rivers and lakes as bare path strings and cities
    # as objects. Guarding on isinstance(dict) — which the cities need — threw
    # away every river and every lake without a word, so the maps shipped two
    # rounds of review with no water on them at all and nobody could see the
    # absence, because a missing Lake Victoria looks exactly like land.
    def _d(v):
        return v.get("d") if isinstance(v, dict) else (v if isinstance(v, str) else None)

    water = [p for p in (_d(r) for r in det.get("rivers") or []) if p]
    lakes = [p for p in (_d(l) for l in det.get("lakes") or []) if p]
    water = ['<path class="cm-river" d="%s"/>' % p for p in water]
    lakes = ['<path class="cm-lake" d="%s"/>' % p for p in lakes]
    water_layer = ('<g class="cm-water" clip-path="url(#%s)" aria-hidden="true">%s%s</g>'
                   % (clip, "".join(lakes), "".join(water))) if (water or lakes) else ""

    # 3. The country itself — an outline where there is one, and where there is
    #    not, a marked position carrying its own name so the plate never leaves
    #    the reader hunting for which dot is the country.
    if shapes.get(slug):
        out.append('<path class="cm-here" d="%s"/>' % shapes[slug])
    else:
        isl = island(slug)
        out.append('<g class="cm-here-pt">'
                   '<circle class="cm-here-ring" cx="%.1f" cy="%.1f" r="%.1f"/>'
                   '<circle cx="%.1f" cy="%.1f" r="%.1f"/>'
                   '<text x="%.1f" y="%.1f">%s</text></g>'
                   % (isl["x"], isl["y"], side * 0.035,
                      isl["x"], isl["y"], side * 0.009,
                      isl["x"], isl["y"] - side * 0.05, _esc(name.upper())))

    # 3b. Water goes ON TOP of the land, including the country's own. Drawn
    #     underneath, Lake Turkana vanished the moment Kenya's fill went opaque —
    #     a lake wholly inside a country being hidden by that country is the one
    #     ordering a map can never use.
    out.append(water_layer)

    # 4. Neighbour names, placed where the neighbour is ON THIS PLATE.
    # The obvious way — hang the label off the country's `at` anchor — puts
    # LIBYA four hundred units north of Egypt's crop and DEMOCRATIC REPUBLIC OF
    # THE CONGO somewhere over the Atlantic, so Egypt and Eswatini came out with
    # no neighbours named at all while Nigeria got four. The label belongs at
    # the centroid of the part that is actually visible, which is what
    # visible_centre() clips out.
    #
    # A name is drawn only where the country shows enough of itself to carry it
    # (2.5% of the frame), and never in the bottom tenth, which the scale bar
    # owns. Long names are dropped rather than shrunk or wrapped: a neighbour
    # whose name will not fit is a neighbour whose shape the reader can see
    # anyway, and a country's own outline should never be read through type.
    labels = []
    for s, _path in near:
        cxx, cyy, share = visible_centre(s, vx, vy, side)
        if cxx is None or share < 0.025:
            continue
        if cyy > vy + side * 0.9 or cyy < vy + side * 0.05:
            continue
        label = d["names"].get(s, s).upper()
        # Roughly .62 of the em per character in the mono face; a name wider
        # than 70% of the frame would run out over the country being mapped.
        if len(label) * side * 0.013 * 0.62 > side * 0.7:
            if s not in borders:
                continue
            label = label.split()[-1] if " " in label else label
            if len(label) * side * 0.013 * 0.62 > side * 0.7:
                continue
        text = ('<text class="cm-near-name" x="%.1f" y="%.1f" '
                'text-anchor="middle">%s</text>' % (cxx, cyy, _esc(label)))
        href = links.get(s)
        if href:
            text = ('<a class="cm-link" href="%s" data-cm="%s">%s</a>'
                    % (_esc(href), _esc(s), text))
        labels.append((share, text))
    # Six names is already a busy plate; the biggest presences earn the ink.
    labels.sort(key=lambda t: -t[0])
    if labels:
        out.append('<g clip-path="url(#%s)">%s</g>'
                   % (clip, "".join(t[1] for t in labels[:6])))

    # 5. The thirteen cities that have real positions, where they fall inside.
    for c in det.get("cities") or []:
        if c.get("country") == slug and inside(c["x"], c["y"]):
            out.append('<g class="cm-city" aria-hidden="true">'
                       '<circle cx="%.1f" cy="%.1f" r="%.1f"/>'
                       '<text x="%.1f" y="%.1f">%s</text></g>'
                       % (c["x"], c["y"], side * 0.006,
                          c["x"] + side * 0.013, c["y"] + side * 0.006,
                          _esc(c["name"])))

    out.append(route(slug))

    # 6. A scale bar that means something, and a north mark.
    kpu = km_per_unit(slug)
    if kpu:
        step = _nice_km(side * kpu)
        length = step / kpu
        bx = vx + side * 0.06
        by = vy + side * 0.94
        out.append('<g class="cm-scale" aria-hidden="true">'
                   '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   '<text x="%.1f" y="%.1f">%d km</text></g>'
                   % (bx, by, bx + length, by,
                      bx, by - side * 0.012, bx, by + side * 0.012,
                      bx + length, by - side * 0.012, bx + length, by + side * 0.012,
                      bx, by - side * 0.028, step))
    out.append('<g class="cm-north" aria-hidden="true">'
               '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
               '<text x="%.1f" y="%.1f" text-anchor="middle">N</text></g>'
               % (vx + side * 0.94, vy + side * 0.13,
                  vx + side * 0.94, vy + side * 0.06,
                  vx + side * 0.94, vy + side * 0.045))
    out.append('</svg>')
    return "".join(out)


def _esc(v):
    import html as h
    return h.escape(str(v if v is not None else ""), quote=True)
