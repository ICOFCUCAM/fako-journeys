"""What is connected to what, and on what evidence.

    python3 tools/tourism/build.py links

Every page on this site could already answer "where is this". None of them could
answer "what is next to it" — which is the question a traveller asks second, and
the one that turns twenty-two country pages into a continent.

A connection here is never asserted. It is one of five facts, each of which can
be checked against something:

    border     the two countries share a land border. Read out of Natural Earth
               by africa_map.py --links, not typed into a table.
    km         the great-circle distance between their centres. A fact about the
               map. Deliberately not a travel time: how long the road takes is
               something this project does not know, and a number that looks
               like an answer is worse than no number.
    lens       both declare the same thing in their own `calls`.
    season     their good months overlap, from their own `months`.
    operator   the same company of ours runs both.

`region` is not a connection. Every country in a region shares it, so it says
nothing about any particular pair; it is used to order what is left when nothing
stronger applies, and it is never printed as a reason.

Borders are within the roster. Cameroon borders six countries; one of them is a
destination here, so that is the one this file knows about, and the page says
"borders another destination here" rather than "borders", because the difference
matters.
"""

import json
import os

from .model import ROOT, load_operators, load_regions, region_of

NEIGHBOURS = os.path.join(ROOT, "tourism", "neighbours.json")
DATA = os.path.join(ROOT, "data", "links.json")

# How much each kind of evidence is worth when ordering what to offer next. A
# shared border outranks everything because it is the only one that changes what
# a journey can physically be.
WEIGHT = {"border": 40.0, "operator": 14.0, "lens": 12.0, "season": 0.6}

# Beyond this, two countries are not "next" to each other in any useful sense,
# whatever else they share. Roughly the width of the Sahara.
FAR_KM = 4200


def geometry(path=NEIGHBOURS):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {"centres": {}, "borders": {}, "km": {}}


def build(countries, lenses=None):
    """-> {slug: [connection]}, each connection carrying its own evidence."""
    geo = geometry()
    regions = load_regions()
    ops = load_operators()
    live = [c for c in countries if c.published]
    by_slug = {c.slug: c for c in live}
    lens_titles = {k: (v.get("title") or k) for k, v in (lenses or {}).items()}

    out = {}
    for a in live:
        rows = []
        for b in live:
            if b.slug == a.slug:
                continue
            km = (geo["km"].get(a.slug) or {}).get(b.slug)
            why, score = [], 0.0

            if b.slug in (geo["borders"].get(a.slug) or []):
                why.append({"kind": "border",
                            "say": "shares a land border with %s" % a.name})
                score += WEIGHT["border"]

            shared_lens = [k for k in a.calls if k in b.calls]
            if shared_lens:
                names = [lens_titles.get(k, k).lower() for k in shared_lens]
                why.append({"kind": "lens",
                            "say": "leads on " + " and ".join(names) + " too"})
                score += WEIGHT["lens"] * len(shared_lens)

            months = sorted(set(a.months) & set(b.months))
            if months:
                why.append({"kind": "season", "months": months,
                            "say": "%d months of the year overlap" % len(months)})
                score += WEIGHT["season"] * len(months)

            if a.operator_key and a.operator_key == b.operator_key:
                op = ops.get(a.operator_key)
                why.append({"kind": "operator",
                            "say": "run by %s as well" % (op.name if op else "the same company")})
                score += WEIGHT["operator"]

            if not why:
                continue
            if km is not None and km > FAR_KM and not any(
                    w["kind"] == "border" for w in why):
                continue
            # Distance is a tie-breaker rather than a term: two countries that
            # share a border and a season are connected whether they are four
            # hundred kilometres apart or fourteen hundred.
            if km is not None:
                score -= km / 2000.0
            rows.append({"to": b.slug, "name": b.name, "km": km,
                         "score": round(score, 2), "why": why,
                         "sameRegion": region_of(a, regions)[0] == region_of(b, regions)[0]})

        rows.sort(key=lambda r: (-r["score"], r["name"]))
        # Eight is more than anybody reads and enough that a country with three
        # land borders still has somewhere to go after them. Everything below it
        # is a pair of countries whose only connection is that both are in
        # Africa in November.
        out[a.slug] = rows[:8]
    return out


def payload(countries, lenses=None):
    """Everything the browser needs to draw the constellation and offer a next
    country, in one file. Positions are the real projected centres, so a node
    sits where the country is rather than where a layout put it."""
    geo = geometry()
    views = json.load(open(os.path.join(ROOT, "tourism", "views.json"))) \
        if os.path.exists(os.path.join(ROOT, "tourism", "views.json")) else {}
    boxes = (views.get("countries") or {})
    live = [c for c in countries if c.published]
    regions = load_regions()

    nodes = {}
    for c in live:
        box = boxes.get(c.slug)
        nodes[c.slug] = {
            "name": c.name,
            "region": region_of(c, regions)[0],
            "regionName": c.region,
            "calls": c.calls,
            "months": c.months,
            "url": c.url,
            "lonlat": geo["centres"].get(c.slug),
            # Where the node sits on the continental map, in the same
            # coordinates the atlas already flies around in.
            "at": [round(box[0] + box[2] / 2.0, 1),
                   round(box[1] + box[3] / 2.0, 1)] if box else None,
        }
    # The distance table travels too, rounded to whole kilometres. It is what
    # lets the constellation join each country to the nearest other country in
    # an answer rather than to all of them, and it is four kilobytes.
    km = {}
    for a in nodes:
        km[a] = {b: v for b, v in (geo["km"].get(a) or {}).items() if b in nodes}
    return {"nodes": nodes, "links": build(countries, lenses), "km": km,
            "borders": {k: v for k, v in (geo["borders"] or {}).items() if k in nodes}}


def run(countries, lenses=None, log=print):
    folder = os.path.dirname(DATA)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    data = payload(countries, lenses)
    with open(DATA, "w") as fh:
        json.dump(data, fh, separators=(",", ":"), sort_keys=True)
        fh.write("\n")
    pairs = sum(len(v) for v in data["borders"].values()) // 2
    edges = sum(len(v) for v in data["links"].values()) // 2
    log("links: %s (%.1f KB), %d countries, %d shared land borders, "
        "%d connections with evidence"
        % (os.path.relpath(DATA, ROOT), os.path.getsize(DATA) / 1024.0,
           len(data["nodes"]), pairs, edges))
    return DATA
