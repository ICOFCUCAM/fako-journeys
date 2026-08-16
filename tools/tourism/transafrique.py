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
import re

from . import routemap
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


def level_card(v, n=0):
    """A way of crossing a continent, not a row in a pricing table.

    The order on the card is the argument: number, name, the promise in the
    traveller's own words, what it actually is, then — last, small, and in the
    metadata voice — how long and how much. A SaaS tier leads with the figure
    because the figure is the product. Here the figure is a consequence of the
    product, and putting it first would invite somebody to choose a crossing
    the way they choose a subscription.
    """
    seats = ('<p class="tf-level-seats">%d seats on each departure</p>'
             % v["seats"]) if v.get("seats") else ""
    return (
        '<article class="tf-level%s" data-level="%s">'
        '<p class="tf-level-no">%02d</p>'
        '<h3 class="tf-level-name">%s</h3>'
        '<p class="tf-level-line">%s</p>'
        '<p class="tf-level-say">%s</p>%s'
        '<dl class="tf-level-facts">'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>Journey fee</dt><dd>%s</dd></div>'
        '</dl>'
        '<p class="tf-level-who">%s</p></article>'
        % (" is-rec" if v.get("recommended") else "", esc(v["id"]), n,
           esc(v["name"]), esc(v["line"]), esc(v["say"]), seats,
           esc(v["days"]), band(v), esc(v["who"])))


def support_grid(d):
    """Six domains, numbered, as an expedition dossier rather than six cards.

    A list of people — doctor, nurse, driver, historian, chef — reads as
    staffing. Naming what is covered reads as capability, and it is the more
    honest shape as well: which individual travels changes with the route, while
    what has to be covered does not. It also keeps the medical line from turning
    the page into a medical tour, which is what a month-long expedition with a
    doctor on it starts to sound like if the doctor is the headline.

    The numbers are the premiumisation and they are nearly free: 01 / MEDICAL
    reads as a manifest, six unnumbered boxes read as a features grid. They are
    generated from position, so a seventh domain numbers itself.
    """
    out = []
    for i, s_ in enumerate(d["support"], 1):
        roles = "".join("<li>%s</li>" % esc(r) for r in s_["roles"])
        out.append(
            '<article class="tf-sup" data-support="%s">'
            '<p class="tf-sup-no"><b>%02d</b><i aria-hidden="true"></i></p>'
            '<h3 class="tf-sup-name">%s</h3>'
            '<p class="tf-sup-say">%s</p>'
            '<ul class="tf-sup-roles">%s</ul></article>'
            % (esc(s_["id"]), i, esc(s_["name"]), esc(s_["say"]), roles))
    return '<div class="tf-support">%s</div>' % "".join(out)


def medical_note(d):
    """The offer and its limit, and the limit is not a disclaimer.

    Written as a footnote it read as legal cover, which is the worst possible
    register for the one thing on this page a traveller is entitled to be angry
    about later if it were buried. Written as preparation it says the same
    words and means confidence: here is what we arrange, here is what decides
    it, here is what it does not replace. Nothing is softened — insurance stays
    mandatory, and rates.json already marks it as the one requirement never
    waived — but the sentence sounds like an expedition company rather than a
    liability paragraph.

    The stamp under it is the whole promise in five words.
    """
    m = d["medical"]
    return ('<aside class="tf-med">'
            '<p class="tf-med-h">%s</p>'
            '<p class="tf-med-say">%s</p>'
            '<p class="tf-med-but">%s</p>'
            '<p class="tf-med-stamp">%s</p></aside>'
            % (esc(m["title"]), esc(m["say"]), esc(m["but"]), m["stamp"]))


def hero(d, by_slug):
    """The opening spread, on the site's fixed-window architecture.

    Full-bleed photograph at position:fixed inside a band with
    clip-path:inset(0), so the road stands still while the title travels over
    it. NOTHING between .tf-band and .tf-band-pic may carry transform, filter,
    backdrop-filter, perspective, will-change or contain — each makes an element
    a containing block for fixed descendants, demotes that fixed to absolute,
    and kills the effect with no error and nothing visibly broken.
    docs/window-band.md is the full account and browser-checks.js asserts it.

    The picture is the same journey the homepage door opens on, one beat later:
    the same loaded vehicle, now going, on a road that leaves the frame.

    The type is a title card and not a summary. Name, series, proposition, the
    whole road as a chain, one restrained way in. No prices, no lengths, no
    team — every one of those has a section of its own below.
    """
    h = d["hero"]
    great = next((r for r in d["routes"] if r.get("great")), d["routes"][0])
    chain = "".join('<span>%s</span>' % esc(by_slug[s_].name)
                    for s_ in great["countries"] if s_ in by_slug)
    return (
        '<section class="tf-band">'
        '<div class="tf-band-pic">'
        '<img src="%s" width="%d" height="%d" alt="%s" '
        'fetchpriority="high" decoding="async" data-provider="upload">'
        '<span class="tf-band-tint" aria-hidden="true"></span>'
        '</div>'
        '<div class="tf-band-copy"><div class="tf-band-in">'
        '<p class="tf-band-mark">%s</p>'
        '<p class="tf-band-series">%s</p>'
        '<h1 class="tf-h1">%s</h1>'
        '<p class="tf-band-chain">%s</p>'
        '<a class="af-btn tf-band-go" href="#crossings">%s<i>&rarr;</i></a>'
        '</div></div></section>'
        % (esc(h["image"]), h["width"], h["height"], esc(h["alt"]),
           esc(h["mark"]), esc(d["stamp"]), esc(d["line"]), chain,
           esc(h["act"])))


def idea_block(d):
    """What a crossing is, before anything about how one is run.

    A reader who came through the door has been sold a morning. Putting six
    support domains and three price bands next asks them to judge a product
    nobody has described yet, so this describes it — in distances, which is the
    only argument that actually lands, rather than in adjectives.
    """
    i = d["idea"]
    # The pull quote lands between the two paragraphs rather than after them.
    # After, it is a conclusion nobody needed; between, it is the turn — the
    # first paragraph says a week in one country is a week in one country, the
    # quote says what the alternative actually is, and the second paragraph
    # then has something to explain.
    says = ['<p class="tf-idea-say">%s</p>' % esc(t) for t in i["say"]]
    pull = '<p class="tf-idea-pull">%s</p>' % esc(i["pull"])
    body = says[0] + pull + "".join(says[1:]) if says else pull
    return ('<section class="tf-block tf-idea" id="idea">'
            '<h2 class="tf-h2">%s</h2>'
            '<div class="tf-idea-in"><p class="tf-idea-line">%s</p>'
            '<div class="tf-idea-body">%s</div></div></section>'
            % (esc(i["title"]), esc(i["line"]), body))


# Three line drawings for the door's facts, in the same 24x24 stroke convention
# as the lens icons in gateway.py. Presentation, so it lives in code — but the
# text beside each one is derived, never typed.
DOOR_ICONS = {
    "days": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.3l3.4 2"/>',
    "where": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/>'
             '<path d="M12 3.5c2.6 2.8 4 5.6 4 8.5s-1.4 5.7-4 8.5'
             'c-2.6-2.8-4-5.6-4-8.5s1.4-5.7 4-8.5z"/>',
    "levels": '<circle cx="9" cy="9" r="3"/>'
              '<path d="M3.5 19.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/>'
              '<path d="M16 6.6a3 3 0 0 1 0 4.8"/>'
              '<path d="M17.5 14.9c1.9.6 3 2.4 3 4.6"/>',
}


def _spread(levels):
    """The shortest and longest a crossing runs, read off the levels.

    Typed on the homepage as "14 to 60+ days" it would be a number in a second
    place, and the ground journey has already taught this file what that costs:
    a hero plate said $350 while the tier beside it said $650 for a fortnight,
    because somebody changed one and not the other. So the range is read from
    the same `days` strings the level cards print — "30 to 60+", "14 to 25",
    "34" — and a new level or a changed length moves the homepage with it.
    """
    lows, highs, plus = [], [], False
    for v in levels:
        nums = [int(n) for n in re.findall(r"\d+", str(v.get("days") or ""))]
        if not nums:
            continue
        lows.append(nums[0])
        highs.append(nums[-1])
        if str(v.get("days") or "").rstrip().endswith("+"):
            plus = True
    if not lows:
        return ""
    return "%d to %d%s days" % (min(lows), max(highs), "+" if plus else "")


def door_facts(d):
    """Shape without price: how long, how far, and how it is bought.

    Deliberately no money. A reader on the homepage has not asked what it costs
    and a five-figure band in a door is a question answered before it is put;
    /trans-afrique carries every number.
    """
    countries = {s for r in d["routes"] for s in (r.get("countries") or [])}
    # Each fact is a list of lines, not a sentence, and each line is set on its
    # own row inside its column. Run together with middots they wrapped wherever
    # the column happened to end — "15 countries, 4" over "crossings", and a
    # separator orphaned at the start of a line, which is the one break
    # typography has no excuse for. Stacked, the wrap is the design.
    rows = [
        ("days", [_spread(d["levels"])]),
        ("where", ["%d countries" % len(countries),
                   "%d crossings" % len(d["routes"])]),
        ("levels", [v["name"].replace("Trans Afrique", "").strip()
                    for v in d["levels"]]),
    ]
    return ('<ul class="wa-door-facts">%s</ul>'
            % "".join(
                '<li><span class="wa-door-ico" aria-hidden="true">'
                '<svg viewBox="0 0 24 24">%s</svg></span>'
                '<b>%s</b></li>'
                % (DOOR_ICONS[key],
                   "".join("<span>%s</span>" % esc(line) for line in lines if line))
                for key, lines in rows if any(lines)))


def block_door(countries):
    """The homepage band's copy: a title sequence, not a paragraph.

    Order is film grammar. The proposition opens cold — "Cross Africa. Don't
    just visit it." — then a line that is pure invitation, then the road as a
    chain of countries, and only then the name. The eyebrow says "series" and
    not "Trans Afrique" so that the title card still has somewhere to land.

    What it does NOT do is explain. No support domains, no bands, no lengths per
    crossing; three derived facts and a way in. The page is two clicks of scroll
    away and carries all of it.
    """
    d = load()
    by_slug = {c.slug: c for c in countries}
    dr = d["door"]
    great = next((r for r in d["routes"] if r.get("great")), d["routes"][0])
    # Four names and an ellipsis, in the order the crossing actually drives
    # them. Printing all nine would make the door a route listing, and printing
    # a prettier order would be a route nobody drives.
    names = [by_slug[s].name for s in great["countries"] if s in by_slug]
    chain = "".join('<span>%s</span>' % esc(n) for n in names[:4])
    return (
        '<p class="wa-seam-stamp">%s</p>\n'
        '      <h2>%s</h2>\n'
        '      <span class="wa-seam-hr" aria-hidden="true"></span>\n'
        '      <p class="wa-seam-say">%s</p>\n'
        '      <p class="wa-door-chain">%s<i aria-hidden="true">&hellip;</i></p>\n'
        '      <p class="wa-door-mark">Trans Afrique</p>\n'
        '      <p class="wa-door-sub">%s</p>\n'
        '      %s\n'
        '      <a class="wa-seam-go" href="/trans-afrique">%s &rarr;</a>'
        % (esc(dr["eyebrow"]), esc(dr["line"]), esc(dr["lede"]), chain,
           esc(dr["sub"]), door_facts(d), esc(dr["act"])))


def great_block(d, by_slug):
    """The flagship, and it does not share a hierarchy with the other three.

    East, West and South are three crossings. The Continental Expedition is the
    reason the other three exist — nine countries, two oceans, one road — and
    setting it as a fourth card in the same grid said it was one of four
    options. It is the option the other three are portions of, which is a
    different kind of thing and gets a different kind of block: full width, the
    name at the scale of a section heading, the chain running the whole measure,
    and the facts as a row rather than a column.
    """
    r = next((x for x in d["routes"] if x.get("great")), None)
    if not r:
        return ""
    strands = " &middot; ".join(esc(x) for x in (r.get("strands") or []))
    return (
        '<section class="tf-great" id="continental">'
        '<p class="tf-great-eyebrow">%s</p>'
        '<h2 class="tf-great-name">%s</h2>'
        '<p class="tf-great-strands">%s</p>'
        '<p class="tf-great-where">%s</p>'
        '<p class="tf-great-say">%s</p>'
        '<dl class="tf-great-facts">'
        '<div><dt>Shape</dt><dd>%s</dd></div>'
        '<div><dt>Length</dt><dd>%s days</dd></div>'
        '<div><dt>Journey fee</dt><dd>%s</dd></div>'
        '</dl>'
        '<p class="tf-great-close">One continent. One expedition.</p>'
        '</section>'
        % (esc(d["name"]), esc(r["name"].split("&mdash;")[-1].replace("Trans Afrique — ", "")),
           strands, chain(r, by_slug), esc(r["say"]),
           esc(r["shape"]), esc(r["days"]), band(r)))


def close_block(d):
    """A way in, not a checkout.

    The page used to end like an article — one sentence and one link. Two
    buttons, because the two audiences are genuinely different: somebody who
    wants a crossing built around them, and somebody who wants to be told which
    of ours fits. Neither of them is Buy Now, which would be the wrong verb for
    a five-figure month that is quoted in writing before anything is held.
    """
    c = d["close"]
    acts = "".join(
        '<a class="af-btn %s" href="%s">%s<i>&rarr;</i></a>'
        % ("tf-close-go" if a_.get("solid") else "tf-close-alt",
           esc(a_["href"]), esc(a_["label"]))
        for a_ in c["acts"])
    return ('<section class="tf-close" id="begin">'
            '<div class="tf-close-in">'
            '<h2 class="tf-close-h">%s</h2>'
            '<p class="tf-close-say">%s</p>'
            '<div class="tf-close-acts">%s</div>'
            '<p class="tf-close-stamp">%s</p>'
            '</div></section>'
            % (esc(c["title"]), esc(c["say"]), acts, c["stamp"]))


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
        "hero": hero(d, by_slug),
        "idea": idea_block(d),
        "levels": "\n".join(level_card(v, i)
                             for i, v in enumerate(d["levels"], 1)),
        "routes": "\n".join(route_card(r, by_slug)
                            for r in d["routes"] if not r.get("great")),
        "great": great_block(d, by_slug),
        "motto": esc(d["motto"]),
        "support_title": esc(d["support_title"]),
        "support_say": esc(d["support_say"]),
        "support": support_grid(d),
        "medical": medical_note(d),
        "money": money_lists(d),
        "map": routemap.build(d, by_slug),
        "close": close_block(d),
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

<main id="main">
<!-- THE PAGE IS A JOURNEY AND THE ORDER IS THE ARGUMENT.
     Desire, idea, trust, choice, route, flagship, practical, invitation.
       01  the opening spread          — I want to do this
       02  the idea                    — why a crossing at all
       03  the team                    — this is professionally run
       04  when the route demands more — and it is prepared for
       05  three ways to cross         — which one am I
       06  the crossings, on the map   — where does it go
       07  east / west / south         — the records
       08  the continental expedition  — the flagship, alone
       09  what the fee is, and is not — what am I actually buying
       10  ready to cross              — a way in, not a checkout
     The team used to open the page because it is the strongest material on it,
     which is exactly why it was wrong: a reader who has not been told what a
     crossing is cannot judge whether six support domains are impressive or
     excessive. Trust has to follow the idea, never precede it. -->
%(hero)s

<div class="tf-page">
%(idea)s

  <section class="tf-block" id="team">
    <h2 class="tf-h2">%(support_title)s</h2>
    <p class="tf-motto">%(motto)s</p>
    <p class="tf-sup-lede">%(support_say)s</p>
%(support)s
%(medical)s
  </section>

  <section class="tf-block" id="levels">
    <h2 class="tf-h2">Three ways to cross</h2>
    <div class="tf-levels">
%(levels)s
    </div>
  </section>

  <section class="tf-block" id="crossings">
    <h2 class="tf-h2">The crossings</h2>
%(map)s
  </section>

  <section class="tf-block" id="records">
    <div class="tf-routes">
%(routes)s
    </div>
  </section>

%(great)s

  <section class="tf-block" id="fee">
    <h2 class="tf-h2">What the fee is, and is not</h2>
%(money)s
    <p class="tf-fine">%(fine)s</p>
  </section>
</div>

%(close)s

<div class="tf-page tf-page--foot">
  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</div>
</main>
%(events)s
</body>
</html>
"""
