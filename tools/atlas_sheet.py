"""Draw the sheet the map is printed on.

    python3 tools/atlas_sheet.py

The map on the home page was a good object sitting on a page. This makes the
page the sheet the object is printed on: the graticule of the same projection,
extended off every side of the map's own frame and running behind the headline,
the navigation and the rails, so that the whole first screen reads as one
unfolded atlas rather than a picture placed on a background.

The one thing that makes it work is registration. The lines behind the type are
not a decorative grid that happens to look cartographic — they are the parallels
and meridians of the Lambert azimuthal equal-area projection the continent
itself is drawn in, at the same scale and the same origin, so a meridian leaving
the top of the map arrives at the top of the page on the line it would have. It
holds without a line of JavaScript because the sheet is a second <svg> inside
the map's own frame with the same viewBox and the same preserveAspectRatio and
`overflow: visible` — identical box, identical transform, geometry that runs
past the edge. Whatever the frame does at any width, the sheet has already done.

Recovering the transform
------------------------
`africa_map.py` fits the projection to the shapes' bounding box at build time
and never writes the resulting scale down, so it has to be recovered from what
map.json does record: the two island marks, whose longitude and latitude are in
africa_map.ISLAND_MARKS and whose projected positions are in map.json. Three
unknowns, four equations. Scale comes from the vertical baseline alone —
Seychelles and Mauritius are two hundred pixels apart in y and three in x, so
the horizontal pair resolves nothing and averaging the two makes the answer
worse. The result reproduces Cape Agulhas, Cape Guardafui and Bizerte to within
a pixel and a half of the path data, which is the check at the bottom of this
file.

The sheet is generated geometry, not an image: nine kilobytes of path data, no
request, nothing to load. A parchment JPEG would have been twenty times that,
would have needed a second one for the dark ground, and would not have been in
the projection.
"""

import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import africa_map as am

MAP_JSON = os.path.join(ROOT, "tourism", "map.json")
HOME = os.path.join(ROOT, "index.html")

# How far past the map's own 1000x1060 the sheet is drawn. The stage is a screen
# tall and the frame is pinned to its right, so at 1920
# the graticule has to reach two and a half thousand units to the left of the
# map's own box to arrive at the edge of the page — except that it cannot,
# because the projection itself runs out first. Lambert azimuthal reaches rho=2
# at the antipode and no further, which lands 922 units left of the map's origin
# and is drawn as the limb. These bounds are the union of every viewport from
# 1280 to ultrawide; past them, the sheet is bounded by the world, not by us.
SHEET = (-960.0, -580.0, 1420.0, 2000.0)   # x0, y0, x1, y1 in map units

STEP = 10          # degrees between ordinary parallels and meridians
SAMPLE = 2.0       # degrees between sampled points along one of them
# Map units a dropped point may sit off the line it came from. One unit is
# 0.42 CSS pixels at the width the frame renders on a desktop, so the ordinary
# graticule is simplified to within a pixel and the four lines that are drawn
# to be seen — the equator, the two tropics and the prime meridian — to within
# half of one. Untuned, at a quarter of a pixel, the sheet was 20 kB of decimals
# describing a curve nobody can see the difference in.
TOLERANCE = 2.4
KEY_TOLERANCE = 1.0

TROPIC = 23.4394   # the obliquity, which is what a tropic is


def transform():
    """Recover scale and offset from the two island marks. See the note above."""
    with open(MAP_JSON) as fh:
        data = json.load(fh)
    at = {}
    for mark in data["marks"]:
        at[mark["name"]] = mark["at"]
    pairs = []
    for iso, (lon, lat) in am.ISLAND_MARKS.items():
        name = am.AFRICA.get(iso)
        if name in at:
            pairs.append((am.project(lon, lat), at[name]))
    if len(pairs) < 2:
        raise SystemExit("atlas_sheet: need two island marks to recover the fit, "
                         "found %d — has map.json been regenerated?" % len(pairs))
    (p0, s0), (p1, s1) = pairs[0], pairs[1]
    if abs(p1[1] - p0[1]) < 1e-6:
        raise SystemExit("atlas_sheet: the two marks share a latitude, so the "
                         "vertical baseline resolves no scale")
    k = (s1[1] - s0[1]) / (p1[1] - p0[1])
    ox = sum(s[0] - k * p[0] for p, s in pairs) / len(pairs)
    oy = sum(s[1] - k * p[1] for p, s in pairs) / len(pairs)
    return k, ox, oy


K, OX, OY = transform()


def place(lon, lat):
    """Longitude and latitude to a point on the sheet, or None past the limb.

    Lambert azimuthal is defined over the whole globe but the far side folds
    back over the near one, so everything within twelve degrees of the antipode
    is dropped rather than drawn on top of West Africa.
    """
    lo, la = math.radians(lon), math.radians(lat)
    cos_c = (math.sin(am.LAT0) * math.sin(la)
             + math.cos(am.LAT0) * math.cos(la) * math.cos(lo - am.LON0))
    if cos_c < -0.978:
        return None
    x, y = am.project(lon, lat)
    return K * x + OX, K * y + OY


def inside(pt):
    x0, y0, x1, y1 = SHEET
    return x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1


def runs(coords):
    """Sample a line of constant latitude or longitude into drawable runs.

    A run breaks wherever the line leaves the sheet or passes behind the limb,
    so one parallel can come back as two segments and neither of them carries a
    stroke across the empty half of the page to reach the other.
    """
    out, run = [], []
    for lon, lat in coords:
        pt = place(lon, lat)
        if pt is None or not inside(pt):
            # keep one point past the edge so the stroke leaves cleanly rather
            # than stopping short of it
            if pt is not None and run:
                run.append(pt)
            if len(run) > 1:
                out.append(run)
            run = []
            continue
        run.append(pt)
    if len(run) > 1:
        out.append(run)
    return out


def d(run, tol=TOLERANCE):
    # africa_map's own simplifier, on the same terms the coastlines get: a
    # meridian sampled every two degrees is sixty points of which eight carry
    # the curve, and the rest are page weight.
    pts = am._rdp(run, tol)
    return "M" + "L".join("%.1f %.1f" % (x, y) for x, y in pts)


def frange(lo, hi, step):
    n, out = 0, []
    while lo + n * step <= hi + 1e-9:
        out.append(lo + n * step)
        n += 1
    return out


def meridian(lon, lo=-72.0, hi=56.0):
    return runs([(lon, lat) for lat in frange(lo, hi, SAMPLE)])


def parallel(lat, lo=-104.0, hi=132.0):
    return runs([(lon, lat) for lon in frange(lo, hi, SAMPLE)])


def graticule():
    ordinary, keyed = [], []
    for lon in frange(-90.0, 120.0, STEP):
        (keyed if abs(lon) < 1e-9 else ordinary).extend(meridian(lon))
    for lat in frange(-70.0, 50.0, STEP):
        (keyed if abs(lat) < 1e-9 else ordinary).extend(parallel(lat))
    for lat in (TROPIC, -TROPIC):
        keyed.extend(parallel(lat))
    return ordinary, keyed


# Open ocean north-east of the Horn: far enough off the coast that the rose is
# never behind the continent, near enough the right edge of the frame that it
# lands in the top-right corner of the sheet at every desktop width without
# running off it. Its position is a longitude and a latitude rather than two
# numbers in map space, because that is the only way it stays put if the map is
# ever refitted.
ROSE_AT = (57.0, 16.0)   # lon, lat
ROSE_R = 152.0           # map units; about 64 CSS pixels at a desktop width


def rose():
    """A compass rose that points where north actually is.

    On a globe north is one direction; on a projection of one it is a different
    direction at every point, and in Lambert azimuthal centred on 19E it leans
    several degrees anticlockwise out here east of the Horn. Drawing the rose
    upright would be the one detail on this sheet that is wrong on purpose, so
    the bearing is measured the way you would measure it on the ground: project
    a point half a degree further north and see which way that came out.

    Each of the eight points is drawn as two triangles meeting along its own
    axis rather than as one, which is the whole difference between a compass
    rose and an asterisk: the two halves take a light and a shadow tone, and the
    point reads as a folded facet catching the light from one side. Drawn as
    single triangles first, at the first attempt, it came out as a spiky star.

    The base corners sit at forty-five degrees either side of the point, so each
    point's base is bounded by its neighbours' and the eight of them close into
    an octagon at the centre. Only north is filled in the accent, because a rose
    with eight solid lozenges is a nineteenth-century engraving's worth of ink
    next to a graticule drawn at twelve percent.
    """
    cx, cy = place(*ROSE_AT)
    up = place(ROSE_AT[0], ROSE_AT[1] + 0.5)
    turn = math.atan2(up[0] - cx, cy - up[1])   # radians clockwise from screen up

    def at(angle, radius):
        return (cx + radius * math.sin(angle), cy - radius * math.cos(angle))

    def tri(a, b, c):
        return "M%.1f %.1fL%.1f %.1fL%.1f %.1fZ" % (a + b + c)

    out = ['<g class="wa-sheet-rose">']
    for r in (ROSE_R * 1.20, ROSE_R * 1.14):
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f"/>' % (cx, cy, r))
    # the ring of minute ticks between the two circles
    ticks = []
    for i in range(32):
        a = turn + i * math.pi / 16.0
        long_one = (i % 4 == 0)
        ticks.append("M%.1f %.1fL%.1f %.1f"
                     % (at(a, ROSE_R * 1.14) + at(a, ROSE_R * (1.20 if long_one else 1.175))))
    out.append('<path class="wa-rose-ticks" d="%s"/>' % "".join(ticks))
    for i in range(8):
        major = (i % 2 == 0)
        a = turn + i * math.pi / 4.0
        tip = at(a, ROSE_R if major else ROSE_R * 0.55)
        # Waist is what separates a rose from a starburst. At a sixth of the
        # radius the eight points came out as spider legs; a third is roughly
        # the proportion an engraved rose actually uses, and it is wide enough
        # that the bases meet each other and close into an octagon.
        waist = ROSE_R * (0.31 if major else 0.26)
        left = at(a - math.pi / 4.0, waist)
        right = at(a + math.pi / 4.0, waist)
        north = ' wa-rose-north' if i == 0 else ''
        out.append('<path class="wa-rose-lit%s" d="%s"/>' % (north, tri(tip, left, (cx, cy))))
        out.append('<path class="wa-rose-dim%s" d="%s"/>' % (north, tri(tip, (cx, cy), right)))
    out.append('</g>')
    return "".join(out)


def build():
    ordinary, keyed = graticule()
    limb = 2.0 * K          # the projection reaches rho = 2 at the antipode
    out = []
    out.append('<svg class="wa-sheet" viewBox="0 0 1000 1060" aria-hidden="true" '
               'focusable="false" xmlns="http://www.w3.org/2000/svg">')
    out.append('<circle class="wa-sheet-limb" cx="%.1f" cy="%.1f" r="%.1f"/>'
               % (OX, OY, limb))
    out.append('<g class="wa-sheet-grid">')
    for run in ordinary:
        out.append('<path d="%s"/>' % d(run))
    out.append('</g>')
    out.append('<g class="wa-sheet-key">')
    for run in keyed:
        out.append('<path d="%s"/>' % d(run, KEY_TOLERANCE))
    out.append('</g>')
    out.append(rose())
    out.append('</svg>')
    return "".join(out), len(ordinary) + len(keyed)


MARK = re.compile(r"(<!-- gen:sheet -->).*?(<!-- /gen:sheet -->)", re.S)


def write():
    svg, lines = build()
    src = open(HOME).read()
    if not MARK.search(src):
        raise SystemExit("atlas_sheet: index.html has no gen:sheet marker — "
                         "refusing to guess where the sheet goes")
    out = MARK.sub(lambda m: m.group(1) + svg + m.group(2), src)
    if out != src:
        open(HOME, "w").write(out)
    return lines, len(svg)


def check():
    """The recovered fit against points whose position the path data already
    knows: the bounding box of every shape in map.json."""
    with open(MAP_JSON) as fh:
        data = json.load(fh)
    xs, ys = [], []
    for group in ("rest", "live"):
        for shape in data[group]:
            nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", shape.get("d", ""))]
            xs += nums[0::2]
            ys += nums[1::2]
    known = {
        "Cape Agulhas": ((20.0, -34.83), None, max(ys)),
        "Bizerte": ((9.87, 37.28), None, min(ys)),
        "Cape Guardafui": ((51.4, 11.8), max(xs), None),
    }
    worst = 0.0
    for name, ((lon, lat), wx, wy) in known.items():
        x, y = place(lon, lat)
        if wx is not None:
            worst = max(worst, abs(x - wx))
        if wy is not None:
            worst = max(worst, abs(y - wy))
    return worst


if __name__ == "__main__":
    off = check()
    lines, size = write()
    print("k=%.4f ox=%.2f oy=%.2f — %d lines, %.1f kB, fit within %.1f units"
          % (K, OX, OY, lines, size / 1024.0, off))
