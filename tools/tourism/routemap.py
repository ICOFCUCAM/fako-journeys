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


def build(d, by_slug=None, only=None, act=None, title=None, say=None):
    """`d` is the loaded tourism/transafrique.json.

    `only` is a route id. The crossings page draws all four; a single crossing's
    own page draws the same continent with that one lit and the other three left
    out of the legend — the same plate, not a second map, so a reader who has
    seen the four recognises where this one sits in them.
    """
    by_slug = by_slug or {}
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

    shown = [r for r in d["routes"] if only is None or r["id"] == only]
    say = ('<p class="tf-map-say">%s</p>' % _esc(say)) if say else (
          '<p class="tf-map-say">Two roads and four crossings: East is the '
           'first four countries of the Continental Expedition and South is its '
           'last five, so the regional journeys are lengths of the same spine '
           'rather than separate routes.</p>' if only is None else "")
    crosses = {}
    for r in shown:
        for s_ in r.get("countries") or []:
            crosses.setdefault(s_, []).append(r["id"])

    out = ['<svg class="tf-map-svg" viewBox="%s %s %s %s" role="img" '
           'aria-labelledby="tf-map-t">' % tuple(view)]
    # The alt text has to describe THIS plate. Left as the four-crossing
    # sentence, a single-crossing map would have told a screen reader about
    # three roads that are not drawn on it — the accessible name being the one
    # description nobody sighted ever proofreads.
    if only is None:
        out.append('<title id="tf-map-t">The four crossings drawn on Africa: East '
                   'through Kenya, Uganda, Rwanda and Tanzania; West down the '
                   'Atlantic from Senegal to Ghana; South from South Africa up to '
                   'Zambia; and the Continental Expedition running the whole '
                   'length from Kenya to South Africa.</title>')
    else:
        one = next((r for r in shown), {})
        out.append('<title id="tf-map-t">%s drawn on Africa: %s, through %s.</title>'
                   % (_esc(one.get("name") or only), _esc(_shape(one.get("shape"))),
                      _esc(", ".join(
                          (by_slug[s_].name if s_ in by_slug
                           else s_.replace("-", " ").title())
                          for s_ in (one.get("countries") or [])))))

    # 1. The continent, flat and quiet. Everything Afrinkong does not cross is
    #    still drawn: thirteen countries alone on a dark field is a diagram, and
    #    the point of putting a crossing on Africa is that Africa is around it.
    out.append('<g class="tf-map-rest" aria-hidden="true">')
    out += ['<path d="%s"/>' % p for p in rest]
    out += ['<path d="%s"/>' % p for _, p in base]
    out.append('</g>')

    out.append('<g class="tf-map-in" aria-hidden="true">')
    for slug, path in base:
        if slug in crosses:
            out.append('<path d="%s" data-in="%s"/>' % (path, " ".join(crosses[slug])))
    out.append('</g>')

    # 2. THE ROADS, AND WHY FOUR LINES RATHER THAN TWO.
    #
    #    East is the Continental Expedition's first four countries and South is
    #    its last five reversed, so three of the four lines are geometrically
    #    coincident. Drawn as four equals they would collide and read as a
    #    mistake. Drawn in descending width — the spine widest and underneath,
    #    then South, then East on top — the overlap reads as what it is: the
    #    regional crossings are lengths of the trunk, visibly sitting inside it.
    #    Each keeps its own colour so the legend can point at it.
    order = [k for k in ("great", "south", "east", "west")
             if only is None or k == only]
    # Wide enough apart to read as nesting rather than as a colour clash: the
    # spine is the road, South is a length of it, East is a shorter length
    # again. Three strokes within a pixel of each other would look like one
    # badly antialiased line.
    widths = {"great": 10.0, "south": 5.8, "east": 2.8, "west": 5.8}
    routes = {r["id"]: r for r in shown}
    out.append('<g class="tf-map-lines" aria-hidden="true">')
    for rid in order:
        r = routes.get(rid)
        if not r:
            continue
        pts = [at[s_] for s_ in (r.get("countries") or []) if s_ in at]
        if len(pts) < 2:
            continue
        dpath = "M" + "L".join("%.1f %.1f" % (x, y) for x, y in pts)
        out.append('<path class="tf-map-line" data-route="%s" d="%s" '
                   'style="stroke-width:%s"/>' % (rid, dpath, widths[rid]))
    out.append('</g>')

    # 3. One node per country, coloured by the narrowest route through it, so a
    #    dot on the spine that East also uses reads as East's.
    priority = {"east": 0, "west": 1, "south": 2, "great": 3}
    out.append('<g class="tf-map-nodes" aria-hidden="true">')
    for slug in sorted(crosses):
        if slug not in at:
            continue
        owner = sorted(crosses[slug], key=lambda k: priority.get(k, 9))[0]
        out.append('<circle cx="%.1f" cy="%.1f" r="6" data-route="%s" data-in="%s"/>'
                   % (at[slug][0], at[slug][1], owner, " ".join(crosses[slug])))
    out.append('</g>')

    out.append('<g class="tf-map-labels" aria-hidden="true">')
    for rid, (x, y, anchor) in LABELS.items():
        r = routes.get(rid)
        if not r:
            continue
        out.append('<text class="tf-map-label" x="%.1f" y="%.1f" '
                   'text-anchor="%s">%s</text>' % (x, y, anchor, _shape(r.get("shape"))))
    out.append('</g>')
    out.append('</svg>')

    # 4. The legend names every country, because "6 countries" raises exactly
    #    the question it refuses to answer. It is also the hover control for the
    #    map: :has() on the figure lights the matching line and countries.
    legend = "".join(
        '<li data-route="%s"><span class="tf-key-dot" aria-hidden="true"></span>'
        '<span class="tf-key-in"><b>%s</b>'
        '<span class="tf-key-where">%s</span></span>'
        '<i>%d countries</i></li>'
        % (r["id"], _esc(r["name"]),
           " &middot; ".join(_esc(by_slug[s_].name) if s_ in by_slug
                             else _esc(s_.replace("-", " ").title())
                             for s_ in (r.get("countries") or [])),
           len(r.get("countries") or []))
        for r in shown)

    return ('<figure class="tf-map">'
            '<div class="tf-map-art">%s</div>'
            '<figcaption class="tf-map-cap">'
            '<h3 class="tf-map-h">%s</h3>'
            '%s'
            '<ul class="tf-map-key">%s</ul>'
            '%s'
            '</figcaption></figure>'
            % ("".join(out),
               _esc(title or d.get("map_title") or "Four ways across a continent."),
               say, legend,
               ('<a class="af-btn tf-map-go" href="%s">%s<i>&rarr;</i></a>'
                % (_esc(act[1]), _esc(act[0]))) if act else ""))


def _esc(v):
    import html as h
    return h.escape(str(v if v is not None else ""), quote=True)
