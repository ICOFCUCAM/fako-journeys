"""Turn Natural Earth boundaries into the inline SVG map on the gateway home page.

    npm pack world-atlas@2 && tar xzf world-atlas-2.0.2.tgz
    python3 tools/africa_map.py package/countries-110m.json > map.svg

The map on the home page is meant to become the way people navigate the whole
platform, which rules out a drawn approximation of the continent: a country you
can click has to be the shape of that country. So the paths come from Natural
Earth's 110m boundaries by way of the `world-atlas` package, decoded here and
projected once, at build time. Nothing ships to the browser but the finished
path data — no map library, no tiles, no requests.

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

# A country we sell is a link; the rest are scenery. Slug, label, tagline, href.
LIVE = {
    120: ("cameroon", "Cameroon", "Africa in miniature", "/cameroon"),
    800: ("uganda", "Uganda", "The Pearl of Africa", "https://pearl-trails-uganda.vercel.app"),
    404: ("kenya", "Kenya", "Where the wild runs free", "/kenya"),
    834: ("tanzania", "Tanzania", "Wild Africa, island Africa", "/tanzania"),
    646: ("rwanda", "Rwanda", "A thousand hills", "/rwanda"),
    516: ("namibia", "Namibia", "Where the desert meets the wild", "https://namib-skyline.vercel.app"),
    894: ("zambia", "Zambia", "Into the real wilderness", "/zambia"),
    710: ("south-africa", "South Africa", "A world in one country", "/south-africa"),
}

LON0, LAT0 = math.radians(19.0), math.radians(2.0)
VIEW_W, VIEW_H = 1000.0, 1060.0
PAD = 14.0
PRECISION = 1          # tenths of a viewBox unit; the map is ~600px wide in use
MIN_RING_AREA = 4.0    # drop specks: unclickable, and they cost bytes


def decode(topo):
    """TopoJSON arcs -> absolute lon/lat rings. Deltas are quantised integers."""
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


def area(points):
    s = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def build(topo):
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
            shapes.append((code, geom["properties"]["name"], rings))

    flat = [p for _c, _n, rs in shapes for r in rs for p in r]
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
    out.sort(key=lambda s: (s[0] not in LIVE, s[1]))
    return out


def render(shapes):
    lines = ['<svg class="wa-map-svg" viewBox="0 0 %g %g" role="img" '
             'aria-label="Map of Africa. Eight countries are live destinations." '
             'xmlns="http://www.w3.org/2000/svg">' % (VIEW_W, VIEW_H),
             '<g class="wa-map-rest" aria-hidden="true">']
    for code, name, d in shapes:
        if code in LIVE:
            continue
        lines.append('<path d="%s"><title>%s</title></path>' % (d, name))
    lines.append("</g>")
    for code, _name, d in shapes:
        if code not in LIVE:
            continue
        slug, label, tag, href = LIVE[code]
        lines.append(
            '<a class="wa-map-live" href="%s" data-slug="%s" data-name="%s" data-tag="%s">'
            '<path d="%s"/><title>%s — %s</title></a>' % (href, slug, label, tag, d, label, tag))
    lines.append("</svg>")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[2].strip())
    with open(sys.argv[1]) as fh:
        shapes = build(json.load(fh))
    svg = render(shapes)
    sys.stderr.write("%d countries, %d live, %.1f KB of path data\n"
                     % (len(shapes), sum(1 for c, _, _ in shapes if c in LIVE), len(svg) / 1024.0))
    print(svg)
