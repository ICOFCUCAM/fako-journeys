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


def route_card(r, by_slug):
    """One crossing, as an expedition record.

    It was built twice — once here in full and once on the homepage with its
    numbers stripped — because the homepage carried a Trans Afrique section.
    That section is gone: it explained a product to a reader three screens into
    a homepage who had not yet decided they wanted one, and the only part of it
    a door can use is the four names, which the door now carries itself. So
    there is one card again, and it is the full one.
    """
    strands = " &middot; ".join(esc(x) for x in (r.get("strands") or []))
    facts = ('<dl class="tf-route-facts">'
             '<div><dt>Shape</dt><dd>%s</dd></div>'
             '<div><dt>Length</dt><dd>%s days</dd></div>'
             '<div><dt>Journey fee</dt><dd>%s</dd></div>'
             '</dl>' % (esc(r["shape"]), esc(r["days"]), band(r)))
    return (
        '<article class="tf-route%s" data-route="%s">'
        '<div class="tf-route-in">'
        '<h3 class="tf-route-name">%s</h3>'
        '<p class="tf-route-where">%s</p>'
        '<p class="tf-route-strands">%s</p>'
        '<p class="tf-route-say">%s</p>'
        '%s</div></article>'
        % (" tf-route--great" if r.get("great") else "", esc(r["id"]),
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
            '<div class="tf-med-pic"><img src="%s" width="%d" height="%d" alt="%s" '
            'loading="lazy" decoding="async" data-provider="upload"></div>'
            '<div class="tf-med-in">'
            '<p class="tf-med-h">%s</p>'
            '<p class="tf-med-say">%s</p>'
            '<p class="tf-med-but">%s</p>'
            '<p class="tf-med-stamp">%s</p></div></aside>'
            % (esc(m["image"]), m["width"], m["height"], esc(m["alt"]),
               esc(m["title"]), esc(m["say"]), esc(m["but"]), m["stamp"]))


# ---- the homepage door -----------------------------------------------------
#
# RESTORED. These four went out with the bathwater when hero() was rewritten
# into the four-slide band: the generated block in index.html survived, so
# nothing looked broken, but `build.py gateway` had been raising AttributeError
# on block_door ever since and the door could not be regenerated at all. A
# generator that cannot rebuild what it generated is not a generator.


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


def door_meta(d):
    """Shape without price, in one line.

    It was three chips in a grid, each with a line icon. Two things were wrong
    with that. The icons were decoration on a door that has a photograph doing
    the emotional work already — and the middle chip said "15 countries, 4
    crossings" directly above a row that names all four crossings and counts
    every one of them, which is the same fact printed twice and the taller of
    the two ways to print it.

    Derived, never typed: length off the levels, the tiers off the level names.
    The ground journey once shipped a $350 hero plate beside a $650 tier
    because one figure lived in two places and only one was updated.
    """
    tiers = " &middot; ".join(
        esc(v["name"].replace("Trans Afrique", "").strip()) for v in d["levels"])
    return ('<p class="wa-door-meta"><b>%s</b><i aria-hidden="true"></i><b>%s</b></p>'
            % (esc(_spread(d["levels"])), tiers))


def door_index(d):
    """The four crossings, by name, on the door.

    This is what the homepage's Trans Afrique section used to carry — four
    cards with country chains, strand lists, a line of description each and a
    floor price — and the section is gone. Nothing was lost that a door should
    have been saying: the cards explained a product the reader had not yet
    decided they wanted, on a homepage, three screens after being handed a
    photograph. What survives is the only part of it a door can use, which is
    the answer to *where does it go*: four names and how many countries each.

    They are links, so the door is a way into any one of them rather than a
    list of things that exist. One word each, from the file rather than sliced
    off the full name: the cards on /trans-afrique say "Trans Afrique — East",
    and repeating that prefix four times in one row is the brand shouting its
    own name at itself, while slicing gave "The Continental Expedition" — twice
    the width of its three neighbours in a row built to be scanned.
    """
    rows = []
    for r in d["routes"]:
        short = r.get("short") or r["name"].split("\u2014")[-1].strip()
        rows.append('<a href="/trans-afrique#crossings"><b>%s</b><i>%d</i></a>'
                    % (esc(short), len(r.get("countries") or [])))
    return ('<p class="wa-door-cross"><span>The crossings</span>%s</p>'
            % "".join(rows))


def block_door(countries):
    """The homepage band's copy: a title sequence, not a paragraph.

    Order is film grammar. The proposition opens cold — "Cross Africa. Don't
    just visit it." — then a line that is pure invitation, then the name, then
    what it is, then its shape, then where it goes. The eyebrow says "series"
    and not "Trans Afrique" so that the title card still has somewhere to land.

    It also carries what the homepage's Trans Afrique section used to say. That
    section is deleted: four cards explaining a crossing, three screens into a
    homepage, to somebody who had not decided they wanted one. The row of four
    crossings at the foot of this block is the only part of it a door can use.

    What it still does NOT do is explain. No support domains, no bands, no
    lengths per crossing. The page is one click away and carries all of it.
    """
    d = load()
    dr = d["door"]
    return (
        '<p class="wa-seam-stamp">%s</p>\n'
        '      <h2>%s</h2>\n'
        '      <span class="wa-seam-hr" aria-hidden="true"></span>\n'
        '      <p class="wa-seam-say">%s</p>\n'
        '      <p class="wa-door-mark">Trans Afrique</p>\n'
        '      <p class="wa-door-sub">%s</p>\n'
        '      %s\n'
        '      %s\n'
        '      <a class="wa-seam-go" href="/trans-afrique">%s &rarr;</a>'
        % (esc(dr["eyebrow"]), esc(dr["line"]), esc(dr["lede"]),
           esc(dr["sub"]), door_meta(d), door_index(d), esc(dr["act"])))


def hero(d, by_slug):
    """The opening spread: four photographs on the fixed-window architecture.

    ONE FRAME CANNOT ARGUE THIS HEADLINE. "Don't just cross Africa" needs more
    than one kind of crossing behind it, so there are four: a loaded vehicle on
    a red road, a convoy on tarmac with people walking beside it, an elephant
    crossing in front of that convoy, and a camel caravan in the Horn. Same
    idea, four Africas — which is what "many countries" has to look like if it
    is not going to stay a phrase.

    THE MECHANISM IS THE BAND AND MUST NOT BREAK. The picture sits at
    position:fixed inside a band with clip-path:inset(0), so the photographs
    stand still while the title travels over them. Nothing between the band and
    the picture may carry transform, filter, backdrop-filter, perspective,
    will-change or contain — each makes an element a containing block for fixed
    descendants and ends the effect with no error raised.

    Which is why the cross-fade is opacity and nothing else. Opacity creates a
    stacking context, not a containing block, so it is the one animation this
    element can safely have; a fade written with transform would have looked
    identical in a browser and silently killed the fixed picture.

    Every slide is in the DOM. With scripting off, or animation refused, the
    reader still gets the first frame and every alt text.
    """
    h = d["hero"]
    slides = h.get("slides") or [h]
    pics = "".join(
        '<img src="%s" width="%d" height="%d" alt="%s" style="--i:%d" '
        '%s decoding="async" data-provider="upload">'
        % (esc(s_["image"]), s_["width"], s_["height"], esc(s_["alt"]), i,
           'fetchpriority="high"' if i == 0 else 'loading="lazy"')
        for i, s_ in enumerate(slides))
    great = next((r for r in d["routes"] if r.get("great")), d["routes"][0])
    chain = "".join('<span>%s</span>' % esc(by_slug[s_].name)
                    for s_ in great["countries"] if s_ in by_slug)
    return (
        '<section class="tf-band" data-slides="%d">'
        '<div class="tf-band-pic">%s'
        '<span class="tf-band-tint" aria-hidden="true"></span>'
        '</div>'
        '<div class="tf-band-copy"><div class="tf-band-in">'
        '<p class="tf-band-mark">%s</p>'
        '<p class="tf-band-series">%s</p>'
        '<h1 class="tf-h1">%s</h1>'
        '<p class="tf-band-sub">%s</p>'
        '<p class="tf-band-chain">%s</p>'
        '<a class="af-btn tf-band-go" href="#crossings">%s<i>&rarr;</i></a>'
        '</div></div></section>'
        % (len(slides), pics, esc(h["mark"]), esc(d["stamp"]), esc(d["line"]),
           esc(h.get("sub") or d["sub"]), chain, esc(h["act"])))


def idea_block(d):
    """What a crossing is, before anything about how one is run.

    A reader who came through the door has been sold a morning. Putting six
    support domains and three price bands next asks them to judge a product
    nobody has described yet, so this describes it — in distances, which is the
    only argument that actually lands, rather than in adjectives.
    """
    i = d["idea"]
    says = "".join('<p class="tf-idea-say">%s</p>' % esc(t) for t in i["say"])
    tail = '<p class="tf-idea-say tf-idea-tail">%s</p>' % esc(i["tail"])
    return ('<section class="tf-block tf-idea" id="idea">'
            '<h2 class="tf-h2">%s</h2>'
            '<div class="tf-idea-in"><p class="tf-idea-line">%s</p>'
            '<div class="tf-idea-body">%s%s</div></div></section>'
            % (esc(i["title"]), esc(i["line"]), says, tail))


def philosophy_band(d):
    """The thesis, on a photograph, between the idea and the machinery.

    "You don't visit Africa. You move through it." was a pull quote wedged
    between two paragraphs. That is the right place for a good sentence and the
    wrong place for the page's thesis — a reader scanning goes straight past it.

    On a road with a convoy on it and a family walking the verge, the sentence
    stops being a phrase and becomes a description of the frame. Which is also
    the rule this site keeps: the copy is written to the photograph, and this
    one earns its line rather than decorating it.

    Not the fixed-window band. That belongs to the opening spread; a second
    fixed picture two screens later turns a technique into a tic.
    """
    ph = d["philosophy"]
    return ('<section class="tf-phil" id="philosophy">'
            '<img class="tf-phil-pic" src="%s" width="%d" height="%d" alt="%s" '
            'loading="lazy" decoding="async" data-provider="upload">'
            '<span class="tf-phil-tint" aria-hidden="true"></span>'
            '<div class="tf-phil-in">'
            '<p class="tf-phil-pull">%s</p>'
            '<p class="tf-phil-say">%s</p>'
            '</div></section>'
            % (esc(ph["image"]), ph["width"], ph["height"], esc(ph["alt"]),
               esc(ph["pull"]), esc(ph["say"])))


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
            '<img class="tf-close-pic" src="%s" width="%d" height="%d" alt="%s" '
            'loading="lazy" decoding="async" data-provider="upload">'
            '<span class="tf-close-tint" aria-hidden="true"></span>'
            '<div class="tf-close-in">'
            '<p class="tf-close-eyebrow">%s</p>'
            '<h2 class="tf-close-h">%s</h2>'
            '<p class="tf-close-say">%s</p>'
            '<div class="tf-close-acts">%s</div>'
            '<p class="tf-close-stamp">%s</p>'
            '</div></section>'
            % (esc(c["image"]), c["width"], c["height"], esc(c["alt"]),
               esc(c["title"]), esc(c["line"]), esc(c["say"]), acts, c["stamp"]))


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
        "philosophy": philosophy_band(d),
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
</div>

%(philosophy)s

<div class="tf-page tf-page--after">
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
