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


def route_card(r, by_slug, preview=False):
    """The same card twice, minus its numbers on the homepage.

    A visitor three screens into a homepage is not choosing between a
    twenty-one-day East at $6,000 and a twenty-four-day West at $7,000. They are
    deciding whether crossing a continent is a thing they want at all, and a
    price on that screen answers a question they have not asked yet — worse, it
    invites them to compare four options before they have wanted any of them.

    So the homepage card is name, countries, strands and one line: where it goes
    and what it is like. Shape, length and fee are on /trans-afrique, where the
    reader arrived by choosing to.
    """
    strands = " &middot; ".join(esc(x) for x in (r.get("strands") or []))
    facts = "" if preview else (
        '<dl class="tf-route-facts">'
        '<div><dt>Shape</dt><dd>%s</dd></div>'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>Journey fee</dt><dd>%s</dd></div>'
        '</dl>' % (esc(r["shape"]), esc(r["days"]), band(r)))
    return (
        '<article class="tf-route%s%s" data-route="%s">'
        '<div class="tf-route-in">'
        '<h3 class="tf-route-name">%s</h3>'
        '<p class="tf-route-where">%s</p>'
        '<p class="tf-route-strands">%s</p>'
        '<p class="tf-route-say">%s</p>'
        '%s</div></article>'
        % (" tf-route--great" if r.get("great") else "",
           " tf-route--peek" if preview else "", esc(r["id"]),
           esc(r["name"]), chain(r, by_slug), strands, esc(r["say"]), facts))


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


def support_grid(d):
    """Six domains, not twelve job titles.

    A list of people — doctor, nurse, driver, historian, chef — reads as
    staffing. Naming what is covered reads as capability, and it is the more
    honest shape as well: which individual travels changes with the route, while
    what has to be covered does not. It also keeps the medical line from turning
    the page into a medical tour, which is what a month-long expedition with a
    doctor on it starts to sound like if the doctor is the headline.
    """
    out = []
    for s_ in d["support"]:
        roles = "".join("<li>%s</li>" % esc(r) for r in s_["roles"])
        out.append(
            '<article class="tf-sup" data-support="%s">'
            '<h3 class="tf-sup-name">%s</h3>'
            '<p class="tf-sup-say">%s</p>'
            '<ul class="tf-sup-roles">%s</ul></article>'
            % (esc(s_["id"]), esc(s_["name"]), esc(s_["say"]), roles))
    return '<div class="tf-support">%s</div>' % "".join(out)


def medical_note(d):
    """The offer and its limit, in the same block.

    An accompanying medical professional is additional support and not a
    substitute for insurance or for local emergency services. That belongs
    beside the offer rather than in a footnote somebody has to go looking for —
    it is the single sentence a traveller would be most entitled to be angry
    about later if it were buried, and insurance stays mandatory regardless,
    which rates.json already marks as the one requirement that is never waived.
    """
    m = d["medical"]
    return ('<aside class="tf-med"><h3 class="tf-med-h">%s</h3>'
            '<p class="tf-med-say">%s</p>'
            '<p class="tf-med-but">%s</p></aside>'
            % (esc(m["title"]), esc(m["say"]), esc(m["but"])))


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
    """The homepage section: where it goes, and nothing about how it works.

    This used to be the whole page repeated inside the homepage — the motto, the
    six support domains, the medical note, three levels with their bands, four
    routes with shape and length and fee, and the fine print. A reader who had
    not yet decided they wanted to cross a continent was being handed doctors,
    drivers, security, seat counts, park fees and five-figure sums, all in one
    screen, before wanting any of it.

    The desire is made twice above this: the window band is the door, in the
    second person, on one morning. This section answers only the question that
    door leaves open — *where does it go* — in four names and four country
    chains, and then stops. Every "how does it work" answer moved to
    /trans-afrique, which the reader reaches by choosing to.
    """
    d = load()
    by_slug = {c.slug: c for c in countries}
    out = ['<p class="tf-motto">%s</p>' % esc(d["motto"])]
    out.append('<div class="tf-routes tf-routes--peek">')
    out += [route_card(r, by_slug, preview=True) for r in d["routes"]]
    out.append('</div>')
    # The one line of commerce the homepage carries, and it is a range across the
    # whole series rather than four prices to compare. It exists so that nobody
    # arrives at the page having imagined a different order of magnitude.
    out.append('<p class="tf-peek-fine">Crossings run from %s, quoted as a whole '
               'and in writing. Lengths, routes and what the fee covers are on '
               'the Trans Afrique page.</p>'
               % money(min(r["low"] for r in d["routes"])))
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
        "motto": esc(d["motto"]),
        "support_title": esc(d["support_title"]),
        "support_say": esc(d["support_say"]),
        "support": support_grid(d),
        "medical": medical_note(d),
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
    <p class="tf-motto">%(motto)s</p>
    <p class="tf-lede">%(say)s</p>
  </div>

  <section class="tf-block" id="team">
    <h2 class="tf-h2">%(support_title)s</h2>
    <p class="tf-sup-lede">%(support_say)s</p>
%(support)s
%(medical)s
  </section>

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
