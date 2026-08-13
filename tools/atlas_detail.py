"""The cartographic layers under and over the continent.

    python3 tools/atlas_detail.py <lakes.geojson> <rivers.geojson> <coastline.geojson>

The map was a political infographic: beige polygon, orange polygon, white
stroke. Recognisable, and nothing like the object it is meant to be. What makes
a map read as a map rather than as a diagram is the material under the
countries — water, graticule, the marks of a survey — and it cannot be faked
with a texture, because a river in the wrong place is worse than no river.

So every line here is projected from real coordinates through the same Lambert
azimuthal equal-area projection africa_map.py uses, with the same fit, and the
fit is recovered rather than assumed: two island marks whose longitude and
latitude are known and whose SVG positions are already in the page give k, ox
and oy exactly. Draw a layer with a fit of its own and the Nile lands in Chad.

  lakes, rivers   Natural Earth 110m, the same survey the countries come from.
  graticule       computed, not drawn: meridians and parallels every 20 degrees.
  cities          city-centre coordinates from tourism/cities.json.
  routes          the same, joined — a journey is a sequence of real places.

Nothing here is decorative in the sense of being invented. The compass rose is
the one mark on the map that is a drawing rather than a measurement, and it
points at true north for this projection, which is not up: on an azimuthal
projection centred at 19E the meridian through the centre is vertical and every
other one leans. The rose is placed on that meridian so that it is telling the
truth.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import africa_map as am                                        # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CITIES = os.path.join(ROOT, "tourism", "cities.json")
OUT = os.path.join(ROOT, "tourism", "atlas-detail.json")

# The two island marks are emitted by africa_map at known coordinates, and their
# SVG positions are in index.html. Two points fix a uniform scale and offset, so
# the fit is derived from the map that exists rather than recomputed from source
# data this script would then have to download and agree with.
FIT_FROM = ((690, 979.6, 604.7), (480, 982.5, 812.8))     # Seychelles, Mauritius


def fit():
    (ca, ax, ay), (cb, bx, by) = FIT_FROM
    pa, pb = am.project(*am.ISLAND_MARKS[ca]), am.project(*am.ISLAND_MARKS[cb])
    k = (by - ay) / (pb[1] - pa[1])
    ox, oy = ax - k * pa[0], ay - k * pa[1]
    # A scale solved on one axis has to hold on the other, or the assumption
    # that this is a uniform fit is wrong and every layer is subtly sheared.
    if abs(pb[0] * k + ox - bx) > 0.15:
        raise SystemExit("the fit is not uniform: x check off by %.3f"
                         % (pb[0] * k + ox - bx))
    return k, ox, oy


K, OX, OY = fit()
W, H = am.VIEW_W, am.VIEW_H


def xy(lon, lat):
    x, y = am.project(lon, lat)
    return x * K + OX, y * K + OY


def inside(p, pad=6.0):
    return -pad <= p[0] <= W + pad and -pad <= p[1] <= H + pad


def path(points, close=False, prec=1):
    if len(points) < 2:
        return ""
    d = "M" + "L".join("%.*f %.*f" % (prec, p[0], prec, p[1]) for p in points)
    return d + ("Z" if close else "")


def clipped_runs(lonlats, step=1):
    """Split a line into the runs of it that are actually on the map.

    A river that leaves the frame and comes back is two strokes, not one long
    one across the corner.
    """
    runs, run = [], []
    for lon, lat in lonlats[::step]:
        p = xy(lon, lat)
        if inside(p, 30):
            run.append(p)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    return [r for r in runs if len(r) > 1]


# ---- water ---------------------------------------------------------------------


# Natural Earth is global; Africa is what this map draws. A generous box rather
# than a precise one, because the clipper above removes what falls outside.
BOX = (-26.0, -37.0, 56.0, 39.0)      # west, south, east, north


def in_box(lon, lat):
    return BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]


def rings_of(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in c]
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return list(c)
    return []


def lakes(features):
    out = []
    for f in features:
        pts = []
        for ring in rings_of(f["geometry"]):
            if not any(in_box(lon, lat) for lon, lat in ring):
                continue
            scr = [xy(lon, lat) for lon, lat in ring]
            if not any(inside(p) for p in scr):
                continue
            # Lake Victoria is 68,000 km2 and reads; a pond is one rounded pixel
            # and reads as dirt on the paper.
            xs = [p[0] for p in scr]
            ys = [p[1] for p in scr]
            if max(xs) - min(xs) < 5 and max(ys) - min(ys) < 5:
                continue
            pts.append(path(am.thin(scr, 0.8), close=True))
        if pts:
            out.append("".join(pts))
    return out


# Natural Earth 50m carries every meander; at this scale a meander is smaller
# than the stroke drawing it, so the file would be forty kilobytes of detail
# nobody can see. Simplified with the same Douglas-Peucker the countries use.
RIVER_TOLERANCE = 1.1          # map units
MIN_RIVER = 14.0               # a stroke shorter than this reads as a scratch


def _len(run):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(run, run[1:]))


def rivers(features):
    out = []
    for f in features:
        for line in rings_of(f["geometry"]):
            if not any(in_box(lon, lat) for lon, lat in line):
                continue
            for run in clipped_runs(line):
                run = am.thin(run, RIVER_TOLERANCE)
                if len(run) > 2 and _len(run) >= MIN_RIVER:
                    out.append(path(run))
    return out


# ---- the survey marks ------------------------------------------------------------


def graticule():
    """Meridians and parallels every twenty degrees, as the projection bends them.

    Straight lines in longitude are curves on the page here, which is the point:
    a graticule drawn as a rectangular grid would be a decoration contradicting
    the projection underneath it.
    """
    lines = []
    for lon in range(-20, 61, 20):
        pts = [xy(lon, lat) for lat in range(-40, 41, 2)]
        for run in clipped_runs([(lon, lat) for lat in range(-40, 41, 2)]):
            lines.append({"d": path(run), "label": "%d°%s" % (abs(lon), "E" if lon > 0 else
                                                                  ("W" if lon < 0 else "")),
                          "at": run[0], "kind": "meridian"})
        del pts
    for lat in range(-40, 41, 20):
        for run in clipped_runs([(lon, lat) for lon in range(-30, 61, 2)]):
            lines.append({"d": path(run), "label": "%d°%s" % (abs(lat), "N" if lat > 0 else
                                                                   ("S" if lat < 0 else "")),
                          "at": run[-1], "kind": "parallel"})
    return lines


def rose(lon=-14.0, lat=-24.0, r=26.0):
    """A compass in open water, west of the Namib.

    It was on the central meridian at 31S, which is the one place on that line
    where the projection is honest AND there is a country underneath — it landed
    across South Africa and Namibia. Out here it is over ocean, so it is a mark
    on the chart rather than a sticker on a country; the bearing is computed for
    wherever it is put, because north is only straight up on the meridian
    through the projection's centre and leans everywhere else.
    """
    cx, cy = xy(lon, lat)
    up = xy(lon, lat + 1.2)
    ang = math.degrees(math.atan2(up[0] - cx, cy - up[1]))
    return {"cx": round(cx, 1), "cy": round(cy, 1), "r": r, "rotate": round(ang, 2)}


# ---- places and journeys ---------------------------------------------------------


def great_circle(a, b, n=24):
    """Points along the shorter arc between two coordinates.

    A straight line between two points on the page is not the way anybody
    travels, and on this projection it is not even the shorter distance. The arc
    is what makes these read as routes rather than as connections in a diagram.
    """
    (lon1, lat1), (lon2, lat2) = a, b
    f1, l1, f2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = 2 * math.asin(math.sqrt(math.sin((f2 - f1) / 2) ** 2
                                + math.cos(f1) * math.cos(f2) * math.sin((l2 - l1) / 2) ** 2))
    if d == 0:
        return [(lon1, lat1)]
    out = []
    for i in range(n + 1):
        t = i / float(n)
        A = math.sin((1 - t) * d) / math.sin(d)
        B = math.sin(t * d) / math.sin(d)
        x = A * math.cos(f1) * math.cos(l1) + B * math.cos(f2) * math.cos(l2)
        y = A * math.cos(f1) * math.sin(l1) + B * math.cos(f2) * math.sin(l2)
        z = A * math.sin(f1) + B * math.sin(f2)
        out.append((math.degrees(math.atan2(y, x)),
                    math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))))
    return out


COAST_TOLERANCE = 0.9
MIN_COAST = 20.0


def coastline(features):
    """The edge of the land, as its own stroke.

    An internal border has the same line drawn on both sides of it and reads as
    a hairline; a coast has it on one side only. Stroking the country polygons
    harder does not produce that difference — it just makes every border heavier.
    The only way to get an engraved coast is to draw the coast, so here it is,
    from the same survey, clipped to the same box.
    """
    out = []
    for f in features:
        for line in rings_of(f["geometry"]):
            if not any(in_box(lon, lat) for lon, lat in line):
                continue
            for run in clipped_runs(line):
                run = am.thin(run, COAST_TOLERANCE)
                if len(run) > 2 and _len(run) >= MIN_COAST:
                    out.append(path(run))
    return out


def main(lakes_path, rivers_path, coast_path):
    lk = json.load(open(lakes_path))["features"]
    rv = json.load(open(rivers_path))["features"]
    ct = json.load(open(coast_path))["features"]
    data = json.load(open(CITIES))

    cities = []
    for c in data["cities"]:
        if not c.get("lonlat"):
            continue
        x, y = xy(*c["lonlat"])
        cities.append({"slug": c["slug"], "name": c["name"], "country": c["country"],
                       "x": round(x, 1), "y": round(y, 1)})

    routes = []
    for r in data.get("routes") or []:
        pts = []
        for i in range(len(r["stops"]) - 1):
            a = (r["stops"][i][1], r["stops"][i][2])
            b = (r["stops"][i + 1][1], r["stops"][i + 1][2])
            arc = great_circle(a, b)
            pts.extend(arc if not pts else arc[1:])
        routes.append({"slug": r["slug"], "name": r["name"], "line": r["line"],
                       "d": path([xy(*p) for p in pts]),
                       "stops": [{"name": s[0], "x": round(xy(s[1], s[2])[0], 1),
                                  "y": round(xy(s[1], s[2])[1], 1)} for s in r["stops"]]})

    # The island states are drawn as a marker because their outline is a pixel
    # at this scale. Unlabelled they are two circles in open ocean with no
    # stated reason to exist, which on a chart is worse than leaving them off.
    islands = []
    for code, (lon, lat) in sorted(am.ISLAND_MARKS.items()):
        if code not in am.ROSTER:
            continue
        x, y = xy(lon, lat)
        slug, name = am.ROSTER[code][0], am.ROSTER[code][1]
        islands.append({"slug": slug, "name": name, "x": round(x, 1), "y": round(y, 1)})

    # Madagascar is not adrift; the channel is 400km and there is a boat.
    strait = path([xy(*p) for p in great_circle((36.9, -18.6), (44.3, -19.6), 14)])

    out = {"fit": {"k": round(K, 4), "ox": round(OX, 4), "oy": round(OY, 4),
                   "view": [0, 0, W, H]},
           "lakes": lakes(lk), "rivers": rivers(rv), "coast": coastline(ct),
           "graticule": graticule(), "rose": rose(),
           "cities": cities, "routes": routes,
           "islands": islands, "strait": strait}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    sys.stderr.write("lakes %d  rivers %d  coast %d  graticule %d  cities %d  routes %d -> %s\n"
                     % (len(out["lakes"]), len(out["rivers"]), len(out["coast"]),
                        len(out["graticule"]), len(cities), len(routes),
                        os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
