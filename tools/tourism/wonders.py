"""The Wonders of Africa — the third way in.

    python3 tools/tourism/build.py wonders

WHY IT EXISTS

The site had three ways in and every one of them starts with the traveller or
with the map. Experiences ask what you want to feel. The atlas asks where you
want to go. The tunnel asks both and then prices the ground. Nothing on the
site started with Africa — with a thing that is simply there, and is worth
arranging a year around.

    Feel  ->  Wonder  ->  Discover  ->  Choose  ->  Journey

So it sits directly after the experience grid, which is where the question
changes from "what do you want" to "here is what there is".

AN AFRINKONG COLLECTION, AND IT SAYS SO

There is no official ranking of African wonders and this does not invent one.
The standing line on the section is "An Afrinkong collection of places worth
crossing a continent to see" — a claim about our editorial judgement rather
than about the continent, which is the only version that is both true and
defensible, and which leaves the list free to grow and reorder without anybody
having been misled. "Top ten" would have been shorter and would have been a
travel blog.

GROUPED BY WHAT MAKES THEM EXTRAORDINARY, NOT BY COUNTRY

Earth, wildlife, civilisations, ocean, human culture. Grouping by country is
what the atlas already does, and doing it again here would produce a second and
worse atlas. It also handles the wonders that refuse to sit in one country:
Victoria Falls is Zambia and Zimbabwe, the Virunga are Rwanda and Uganda and
the DRC, the Sahara runs through six of the fifty-four. A country list has to
pick one and be wrong; a strand does not.

THE RHYTHM IS DELIBERATELY NOT THE EXPERIENCE GRID

Two at hero scale, then a row of smaller cards. Eight identical tiles under
eight identical tiles is the same section twice, and the homepage already has
the eight-card grid directly above this one.
"""

import html as html_mod
import json
import os

from .model import ROOT

DATA = os.path.join(ROOT, "tourism", "wonders.json")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def where(w, by_slug):
    """The countries a wonder belongs to, named and linked where we have them.

    A wonder that spans a border names every country it spans. Naming one and
    calling it that country's would be the small lie that a border does not
    matter to the people either side of it.
    """
    out = []
    for slug in w.get("countries") or []:
        c = by_slug.get(slug)
        if c:
            out.append('<a href="%s">%s</a>' % (esc(c.url), esc(c.name)))
        else:
            out.append(esc(slug.replace("-", " ").title()))
    return " &middot; ".join(out)


def card(w, by_slug, big=False):
    return (
        '<article class="wo-card%s" data-strand="%s">'
        '<div class="wo-card-in">'
        '<h3 class="wo-name">%s</h3>'
        '<p class="wo-where">%s</p>'
        '<p class="wo-say">%s</p>'
        '</div></article>'
        % (" wo-card--big" if big else "", esc(w["strand"]),
           esc(w["name"]), where(w, by_slug), esc(w["say"])))


def block_wonders(countries):
    d = load()
    by_slug = {c.slug: c for c in countries}
    ws = d["wonders"]
    leads = [w for w in ws if w.get("lead")][:2]
    rest = [w for w in ws if not w.get("lead")][:6]

    out = ['<div class="wo-lead">']
    out += [card(w, by_slug, big=True) for w in leads]
    out.append('</div>')
    out.append('<div class="wo-rest">')
    out += [card(w, by_slug) for w in rest]
    out.append('</div>')

    # The strands, named under the cards rather than above them: they explain
    # how the collection is cut, which is a thing a reader wants after seeing
    # some of it and not before.
    out.append('<ul class="wo-strands">')
    for s in d["strands"]:
        n = len([w for w in ws if w["strand"] == s["id"]])
        out.append('<li><b>%s</b><span>%s</span><i>%d</i></li>'
                   % (esc(s["name"]), esc(s["say"]), n))
    out.append('</ul>')
    return "\n".join(out)


def block_wonderslede(countries):
    d = load()
    return ('<span class="wa-eyebrow">%s</span>\n'
            '        <h2>%s</h2>\n'
            '        <p class="wa-say">%s</p>'
            % (esc(d["stamp"]), esc(d["line"]), esc(d["say"])))


def counts():
    d = load()
    return len(d["wonders"]), len(d["strands"])


# ---- /wonders, the whole collection ----------------------------------------
#
# The homepage shows eight of twenty-three under a button reading "Explore all
# the wonders". Pointing that at /atlas would have been a button that does not
# do what it says — the atlas is countries, and a wonder is deliberately not a
# country. This is the page the button promises: all of them, by strand, in the
# order the file holds them.

PAGE = os.path.join(ROOT, "wonders.html")


def run(countries, log=print):
    from . import company, plate
    d = load()
    by_slug = {c.slug: c for c in countries}
    groups = []
    for st in d["strands"]:
        mine = [w for w in d["wonders"] if w["strand"] == st["id"]]
        if not mine:
            continue
        groups.append(
            '<section class="wo-strand" id="%s">'
            '<div class="wo-strand-head"><span class="af-stamp">%s</span>'
            '<h2 class="wo-strand-h">%s</h2><p class="wo-strand-say">%s</p></div>'
            '<div class="wo-rest">%s</div></section>'
            % (esc(st["id"]), esc("%d in this strand" % len(mine)),
               esc(st["name"]), esc(st["say"]),
               "".join(card(w, by_slug) for w in mine)))

    html = TEMPLATE % {
        "og": plate.open_graph(
            "The Wonders of Africa — Afrinkong",
            d["say"], "/wonders"),
        "events": plate.events_block(),
        "stamp": esc(d["stamp"]),
        "line": esc(d["line"]),
        "say": esc(d["say"]),
        "n": len(d["wonders"]),
        "strands": "\n".join(groups),
    }
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("wonders: %s (%.1f KB), %d wonders across %d strands"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           len(d["wonders"]), len(d["strands"])))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Wonders of Africa &mdash; Afrinkong</title>
<meta name="description" content="An Afrinkong collection of places worth crossing a continent to see. Grouped by what makes them extraordinary rather than by country.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<link rel="stylesheet" href="/styles/wonders.css">
</head>
<body class="wo-body">
<a class="af-skip" href="#main">Skip to the wonders</a>
<header class="jn-mast">
  <a class="jn-mark" href="/"><i>Afrinkong</i><b>The Wonders of Africa</b></a>
  <nav class="jn-routes" aria-label="Primary">
    <a href="/atlas">The Atlas</a>
    <a href="/places">Every place</a>
    <a href="/meet">Meet Africa</a>
    <a href="/stories">Stories</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/journey">Build a journey<i>&rarr;</i></a>
</header>

<main class="wo-page" id="main">
  <div class="wo-open">
    <span class="af-stamp">%(stamp)s</span>
    <h1 class="wo-h1">%(line)s</h1>
    <p class="wo-lede">%(say)s</p>
    <p class="wo-count">%(n)d places, and the list is ours &mdash; there is no
      official ranking of African wonders and this is not pretending to be one.</p>
  </div>
%(strands)s
  <div class="wo-end">
    <p>Any of them can be the reason for the journey.</p>
    <a class="af-btn af-btn--solid" href="/journey">Build a journey<i>&rarr;</i></a>
  </div>
  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</main>
%(events)s
</body>
</html>
"""
