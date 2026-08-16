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

THE MONEY IS NOT TYPED HERE

An expedition is quoted at the Afrinkong Bespoke daily rate, and that rate lives
in tourism/rates.json with every other figure on the site. This file reads it
and multiplies. Typing $24,000 into a template would have been one more number
to forget when the rate moves — and the pricing page, the tunnel and the
expedition would have started disagreeing about what Bespoke costs.

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

from . import rates
from .model import ROOT

DATA = os.path.join(ROOT, "tourism", "transafrique.json")
PAGE = os.path.join(ROOT, "trans-afrique.html")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def day_rate(d):
    """The Bespoke rate, from the file the whole site prices out of."""
    r = rates.load()
    for t in r["tiers"]:
        if t["id"] == d["tier"]:
            return t["rate"], t["name"]
    return r["tiers"][-1]["rate"], r["tiers"][-1]["name"]


def route_card(r, d, by_slug, rate):
    where = " &rarr; ".join(
        '<a href="%s">%s</a>' % (esc(by_slug[s].url), esc(by_slug[s].name))
        for s in (r.get("countries") or []) if s in by_slug)
    if r.get("open"):
        where = '<span class="tf-open">Wherever you decide</span>'
    return (
        '<article class="tf-route" data-route="%s">'
        '<div class="tf-route-in">'
        '<h3 class="tf-route-name">%s</h3>'
        '<p class="tf-route-where">%s</p>'
        '<p class="tf-route-say">%s</p>'
        '<dl class="tf-route-facts">'
        '<div><dt>Shape</dt><dd>%s</dd></div>'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>From</dt><dd>%s</dd></div>'
        '</dl></div></article>'
        % (esc(r["id"]), esc(r["name"]), where, esc(r["say"]),
           esc(r["shape"]), r["days"],
           esc(rates.money(rate * r["days"]))))


def block_trans(countries):
    d = load()
    by_slug = {c.slug: c for c in countries}
    rate, tier = day_rate(d)
    out = ['<div class="tf-team">']
    for t in d["team"]:
        out.append('<div class="tf-team-row"><b>%s</b><span>%s</span></div>'
                   % (esc(t["who"]), esc(t["say"])))
    out.append('</div>')
    out.append('<div class="tf-routes">')
    out += [route_card(r, d, by_slug, rate) for r in d["routes"]]
    out.append('</div>')
    out.append('<p class="tf-fine">%s Every figure above is %s at %s a day, per '
               'vehicle, for the length shown.</p>'
               % (esc(d["fine"]), esc(tier), esc(rates.money(rate))))
    return "\n".join(out)


def block_translede(countries):
    d = load()
    return ('<span class="wa-eyebrow">%s</span>\n'
            '        <h2>%s</h2>\n'
            '        <p class="wa-say">%s</p>'
            % (esc(d["stamp"]), esc(d["line"]), esc(d["say"])))


def run(countries, log=print):
    from . import plate
    d = load()
    by_slug = {c.slug: c for c in countries}
    rate, tier = day_rate(d)
    html = TEMPLATE % {
        "og": plate.open_graph("Trans Afrique — Afrinkong", d["say"],
                               "/trans-afrique"),
        "events": plate.events_block(),
        "stamp": esc(d["stamp"]),
        "line": esc(d["line"]),
        "say": esc(d["say"]),
        "team": "\n".join(
            '<div class="tf-team-row"><b>%s</b><span>%s</span></div>'
            % (esc(t["who"]), esc(t["say"])) for t in d["team"]),
        "routes": "\n".join(route_card(r, d, by_slug, rate) for r in d["routes"]),
        "fine": esc(d["fine"]),
        "rate": esc(rates.money(rate)),
        "tier": esc(tier),
    }
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("trans-afrique: %s (%.1f KB), %d route(s) at %s a day"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           len(d["routes"]), rates.money(rate)))
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
    <p class="tf-lede">%(say)s</p>
  </div>

  <section class="tf-block">
    <h2 class="tf-h2">Who travels with you</h2>
    <div class="tf-team">
%(team)s
    </div>
  </section>

  <section class="tf-block">
    <h2 class="tf-h2">Three crossings</h2>
    <div class="tf-routes">
%(routes)s
    </div>
    <p class="tf-fine">%(fine)s Every figure above is %(tier)s at %(rate)s a day,
      per vehicle, for the length shown.</p>
  </section>

  <div class="tf-end">
    <p>An expedition is quoted as a whole, in writing, before anything is held.</p>
    <a class="af-btn af-btn--solid" href="/enquire">Ask about an expedition<i>&rarr;</i></a>
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
