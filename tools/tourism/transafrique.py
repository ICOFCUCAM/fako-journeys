"""Trans Afrique — the expedition, and the one thing on the site that is not a country.

    python3 tools/tourism/build.py transafrique

WHY IT IS NOT THE NINTH EXPERIENCE

The eight experiences are lenses: ways of looking at the continent, any of which
can be applied to any of the fifty-four. Trans Afrique is not a lens. It is a
month of somebody's life, five borders, and a team that travels with them. Put
in the grid it would have been a ninth tile in a row of eight, and the most
expensive thing Afrinkong sells would have looked like a filter.

WHERE IT SITS

    Feel  ->  Wonder  ->  Cross  ->  Discover  ->  Choose  ->  Journey

After the wonders, which is the moment the question stops being "what do you
want" and starts being "why choose one country at all". Tourist, then traveller,
then explorer.

THE PRICE IS A BAND, NOT A DAILY RATE TIMES DAYS

The first version multiplied the Bespoke daily rate by the length and printed
the answer, which was tidy and wrong. Twenty-one days at $1,000 is $21,000
against a band that tops out at $12,000, and the gap is not a discount — it is
the shape of the product. One vehicle and one driver committed for a month cost
less per day than the same pair for four days; coordination written once serves
thirty days as easily as seven; a route that repeats across departures is a
route already solved.

So the bands live in tourism/transafrique.json as bands, per journey, and the
file records why they are lower per day than the daily rate. Nothing here
multiplies anything.

WHAT IS SAID CAREFULLY

"Medical accompaniment on selected expeditions", and only ever with the
qualifier attached. Whether a doctor travels depends on the route, the season
and who is free; a site that promises one on every crossing has promised
something it cannot always deliver, and this is exactly the product where being
caught out would matter most.
"""

import html as html_mod
import json
import os

from .model import ROOT

DATA = os.path.join(ROOT, "tourism", "transafrique.json")
PAGE = os.path.join(ROOT, "trans-afrique.html")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def money(n):
    return "${:,}".format(int(n))


def band(o):
    return "%s&ndash;%s" % (money(o["low"]), money(o["high"]))


def chain(r, by_slug):
    """The countries as a route, with arrows, because that is what a crossing
    looks like on paper. A comma-separated list is a set; a chain is a journey."""
    return " &rarr; ".join(
        '<a href="%s">%s</a>' % (esc(by_slug[s].url), esc(by_slug[s].name))
        for s in (r.get("countries") or []) if s in by_slug)


def route_card(r, by_slug):
    strands = " &middot; ".join(esc(x) for x in (r.get("strands") or []))
    return (
        '<article class="tf-route%s" data-route="%s">'
        '<div class="tf-route-in">'
        '<h3 class="tf-route-name">%s</h3>'
        '<p class="tf-route-where">%s</p>'
        '<p class="tf-route-strands">%s</p>'
        '<p class="tf-route-say">%s</p>'
        '<dl class="tf-route-facts">'
        '<div><dt>Shape</dt><dd>%s</dd></div>'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>Journey fee</dt><dd>%s</dd></div>'
        '</dl></div></article>'
        % (" tf-route--great" if r.get("great") else "", esc(r["id"]),
           esc(r["name"]), chain(r, by_slug), strands, esc(r["say"]),
           esc(r["shape"]), esc(r["days"]), band(r)))


def level_card(v):
    seats = ('<p class="tf-level-seats">%d seats on each departure</p>'
             % v["seats"]) if v.get("seats") else ""
    return (
        '<article class="tf-level%s" data-level="%s">'
        '<h3 class="tf-level-name">%s</h3>'
        '<p class="tf-level-line">%s</p>'
        '<p class="tf-level-say">%s</p>%s'
        '<dl class="tf-level-facts">'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>Journey fee</dt><dd>%s</dd></div>'
        '</dl>'
        '<p class="tf-level-who">%s</p></article>'
        % (" is-rec" if v.get("recommended") else "", esc(v["id"]),
           esc(v["name"]), esc(v["line"]), esc(v["say"]), seats,
           esc(v["days"]), band(v), esc(v["who"])))


def money_lists(d):
    def ul(key, title, cls=""):
        return ('<div class="tf-money-col%s"><h3 class="tf-money-h">%s</h3>'
                '<ul class="tf-money-list">%s</ul></div>'
                % (cls, esc(title),
                   "".join("<li>%s</li>" % esc(x) for x in d[key])))
    return ('<div class="tf-money">%s%s%s</div>'
            % (ul("included", "In the journey fee"),
               ul("arranged", "Arranged by us, at cost"),
               ul("excluded", "Yours", " is-not")))


def block_trans(countries):
    d = load()
    by_slug = {c.slug: c for c in countries}
    out = ['<div class="tf-levels">']
    out += [level_card(v) for v in d["levels"]]
    out.append('</div>')
    out.append('<div class="tf-routes">')
    out += [route_card(r, by_slug) for r in d["routes"]]
    out.append('</div>')
    out.append('<p class="tf-fine">%s</p>' % esc(d["fine"]))
    return "\n".join(out)


def block_translede(countries):
    d = load()
    return ('<span class="wa-eyebrow">%s</span>\n'
            '        <h2>%s</h2>\n'
            '        <p class="wa-say"><b class="tf-sub">%s</b> %s</p>'
            % (esc(d["stamp"]), esc(d["line"]), esc(d["sub"]), esc(d["say"])))


def run(countries, log=print):
    from . import plate
    d = load()
    by_slug = {c.slug: c for c in countries}
    html = TEMPLATE % {
        "og": plate.open_graph("Trans Afrique — Afrinkong", d["say"],
                               "/trans-afrique"),
        "events": plate.events_block(),
        "stamp": esc(d["stamp"]),
        "line": esc(d["line"]),
        "sub": esc(d["sub"]),
        "say": esc(d["say"]),
        "levels": "\n".join(level_card(v) for v in d["levels"]),
        "routes": "\n".join(route_card(r, by_slug) for r in d["routes"]),
        "team": "\n".join(
            '<div class="tf-team-row"><b>%s</b><span>%s</span></div>'
            % (esc(t["who"]), esc(t["say"])) for t in d["team"]),
        "money": money_lists(d),
        "fine": esc(d["fine"]),
    }
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("trans-afrique: %s (%.1f KB), %d route(s), %d level(s), %s to %s"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           len(d["routes"]), len(d["levels"]),
           money(min(v["low"] for v in d["levels"])),
           money(max(v["high"] for v in d["levels"]))))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trans Afrique &mdash; Afrinkong</title>
<meta name="description" content="One continent, several countries, one journey that does not stop at a border. Weeks on the road with a team that stays with you.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<link rel="stylesheet" href="/styles/transafrique.css">
</head>
<body class="tf-body">
<a class="af-skip" href="#main">Skip to the expedition</a>
<header class="jn-mast">
  <a class="jn-mark" href="/"><i>Afrinkong</i><b>Trans Afrique</b></a>
  <nav class="jn-routes" aria-label="Primary">
    <a href="/wonders">The Wonders</a>
    <a href="/atlas">The Atlas</a>
    <a href="/places">Every place</a>
    <a href="/stories">Stories</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/enquire">Ask about an expedition<i>&rarr;</i></a>
</header>

<main class="tf-page" id="main">
  <div class="tf-open">
    <span class="af-stamp">%(stamp)s</span>
    <h1 class="tf-h1">%(line)s</h1>
    <p class="tf-sub">%(sub)s</p>
    <p class="tf-lede">%(say)s</p>
  </div>

  <section class="tf-block">
    <h2 class="tf-h2">Three ways to cross</h2>
    <div class="tf-levels">
%(levels)s
    </div>
  </section>

  <section class="tf-block">
    <h2 class="tf-h2">The crossings</h2>
    <div class="tf-routes">
%(routes)s
    </div>
  </section>

  <section class="tf-block">
    <h2 class="tf-h2">Who travels with you</h2>
    <div class="tf-team">
%(team)s
    </div>
  </section>

  <section class="tf-block">
    <h2 class="tf-h2">What the fee is, and is not</h2>
%(money)s
    <p class="tf-fine">%(fine)s</p>
  </section>

  <div class="tf-end">
    <p>Every crossing is quoted as a whole, in writing, before anything is held.</p>
    <a class="af-btn af-btn--solid" href="/enquire">Ask about a crossing<i>&rarr;</i></a>
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
