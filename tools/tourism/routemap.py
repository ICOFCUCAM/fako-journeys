"""The crossings, drawn on the continent they cross.

Built by tools/tourism/transafrique.py and dropped into the crossings section
of /trans-afrique, above the route cards.

WHY IT IS A MAP AND NOT FOUR MAPS

The four crossings are not four independent products, and the geometry says so
out loud once it is plotted. Trans Afrique East is the first four countries of
the Continental Expedition. Trans Afrique South is its last five, reversed.
Drawn as four separate lines, three of them lie on top of each other and the
picture is a muddle that also happens to be a lie — it shows three roads where
there is one.

So the map draws two lines and tells the truth:

    the spine    Kenya down to South Africa, nine countries, the trunk
    the arc      Senegal along the Atlantic to Ghana, six countries

and East and South are what they actually are: portions of the spine, drawn
coincident with it and lit when the reader is looking at their card. That is
the "progressively highlighted" behaviour, and it costs no JavaScript — a
:has() selector on the section does it, and a browser without :has() shows the
complete map instead of a broken one.

WHY THE NODES ARE COUNTRIES AND NOT CITIES

The routes in tourism/transafrique.json are chains of countries, and the only
coordinates that exist for all of them are country centroids in
tourism/map.json. Thirteen cities have real positions in
tourism/atlas-detail.json and four of the eight route endpoints are among them —
Dakar, Accra, Nairobi and Cape Town — while Arusha and Victoria Falls are not.
Anchoring half the ends to cities and half to centroids would put city names on
country middles, which is the one thing the rest of this site refuses to do.

The two line labels are the routes' own `shape` strings, set beside the line
rather than at a point, so "Nairobi to Cape Town" describes the road and does
not claim to mark either city.
"""

import json
import os

from .model import ROOT

MAP = os.path.join(ROOT, "tourism", "map.json")

# Where the two line labels sit, in viewBox units, and which way they read.
# Beside the line and clear of every filled country: the spine label sits east
# of Kenya over open sea, the arc label north-west of Senegal over the Atlantic.
# The spine's label goes at the Cape Town end and not the Nairobi end. Measured,
# "NAIROBI TO CAPE TOWN" is about 252 viewBox units at this size; starting it
# east of Kenya at x=792 ran it to 1044 against a 1000-unit box and the last
# three characters were cut off by the edge. South-east of South Africa is open
# ocean, below Madagascar, and 676 to 928 fits with room either side.
LABELS = {
    "great": (676.0, 992.0, "start"),
    "west": (58.0, 322.0, "start"),
}


def load_map():
    with open(MAP, encoding="utf-8") as fh:
        return json.load(fh)


def _shape(text):
    return (text or "").rstrip(".").upper()


def build(d):
    """`d` is the loaded tourism/transafrique.json."""
    m = load_map()
    view = m.get("view") or [0, 0, 1000.0, 1060.0]
    at = {}
    base = []
    for c in m.get("live", []):
        if c.get("d"):
            base.append((c["slug"], c["d"]))
        if c.get("at"):
            at[c["slug"]] = c["at"]
    rest = [r["d"] for r in m.get("rest", []) if r.get("d")]

    routes = {r["id"]: r for r in d["routes"]}
    great = next((r for r in d["routes"] if r.get("great")), None)

    # slug -> the routes that cross it, so one path can be lit by any of them.
    crosses = {}
    for r in d["routes"]:
        for s in r.get("countries") or []:
            crosses.setdefault(s, []).append(r["id"])

    out = []
    out.append(
        '<svg class="tf-map-svg" viewBox="%s %s %s %s" role="img" '
        'aria-labelledby="tf-map-t">'
        % tuple(view))
    out.append('<title id="tf-map-t">%s</title>'
               % ("The crossings on the map of Africa: a spine of nine "
                  "countries from Kenya to South Africa, and an arc of six "
                  "along the Atlantic from Senegal to Ghana."))

    # 1. The continent, quiet. Everything Afrinkong does not cross is still
    #    drawn — a map of thirteen countries floating alone is a diagram, and
    #    the point of putting a crossing on Africa is that Africa is around it.
    out.append('<g class="tf-map-rest" aria-hidden="true">')
    out += ['<path d="%s"/>' % p for p in rest]
    out += ['<path d="%s"/>' % p for _, p in base]
    out.append('</g>')

    # 2. The countries a crossing actually enters.
    out.append('<g class="tf-map-in" aria-hidden="true">')
    for slug, path in base:
        if slug in crosses:
            out.append('<path d="%s" data-in="%s"/>'
                       % (path, " ".join(crosses[slug])))
    out.append('</g>')

    # 3. The roads. The spine and the arc are drawn; East and South are drawn
    #    coincident with the spine and carry no stroke until their card is
    #    under the cursor or the keyboard.
    out.append('<g class="tf-map-lines" aria-hidden="true">')
    for r in d["routes"]:
        pts = [at[s] for s in (r.get("countries") or []) if s in at]
        if len(pts) < 2:
            continue
        dpath = "M" + "L".join("%.1f %.1f" % (x, y) for x, y in pts)
        out.append('<path class="tf-map-line" data-route="%s" d="%s"/>'
                   % (r["id"], dpath))
    out.append('</g>')

    # 4. A node per country on a drawn road, once each rather than once per
    #    route: Kenya is on the spine and on East, and two circles at the same
    #    centre is a heavier dot for no reason.
    out.append('<g class="tf-map-nodes" aria-hidden="true">')
    for slug in sorted(crosses):
        if slug in at:
            out.append('<circle cx="%.1f" cy="%.1f" r="5.5" data-in="%s"/>'
                       % (at[slug][0], at[slug][1], " ".join(crosses[slug])))
    out.append('</g>')

    # 5. Two labels, and they name the road rather than mark a city.
    out.append('<g class="tf-map-labels" aria-hidden="true">')
    for rid, (x, y, anchor) in LABELS.items():
        r = great if rid == "great" else routes.get(rid)
        if not r:
            continue
        out.append('<text class="tf-map-label" x="%.1f" y="%.1f" '
                   'text-anchor="%s">%s</text>'
                   % (x, y, anchor, _shape(r.get("shape"))))
    out.append('</g>')

    out.append('</svg>')

    legend = "".join(
        '<li data-route="%s"><b>%s</b><span>%s</span></li>'
        % (r["id"], _esc(r["name"]),
           "%d countries" % len(r.get("countries") or []))
        for r in d["routes"])

    return ('<figure class="tf-map">%s'
            '<figcaption class="tf-map-cap">'
            '<p class="tf-map-say">Two roads and four crossings: East is the '
            'first four countries of the Continental Expedition and South is '
            'its last five, so the regional journeys are lengths of the same '
            'spine rather than separate routes.</p>'
            '<ul class="tf-map-key">%s</ul>'
            '</figcaption></figure>' % ("".join(out), legend))


def _esc(v):
    import html as h
    return h.escape(str(v if v is not None else ""), quote=True)
