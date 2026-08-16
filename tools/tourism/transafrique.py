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
SUB = os.path.join(ROOT, "trans-afrique")

# The crossing whose id is "great" answers to /trans-afrique/continental, because
# "great" is a flag in the data and "continental" is what the journey is called.
SLUGS = {"great": "continental"}


def route_url(r):
    return "/trans-afrique/%s" % SLUGS.get(r["id"], r["id"])


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
    # The name is the way in. The card used to be the whole record because it
    # was the only place a crossing existed; each one has its own page now, so
    # the card's job is to be chosen rather than to be read to the end.
    return (
        '<article class="tf-route%s" data-route="%s">'
        '<div class="tf-route-in">'
        '<h3 class="tf-route-name"><a href="%s">%s</a></h3>'
        '<p class="tf-route-where">%s</p>'
        '<p class="tf-route-strands">%s</p>'
        '<p class="tf-route-say">%s</p>'
        '%s<a class="tf-route-go" href="%s">See this crossing<i>&rarr;</i></a>'
        '</div></article>'
        % (" tf-route--great" if r.get("great") else "", esc(r["id"]),
           esc(route_url(r)), esc(r["name"]), chain(r, by_slug), strands,
           esc(r["say"]), facts, esc(route_url(r))))


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
        # Each name now opens its own crossing rather than dropping the reader
        # at an anchor on a page that no longer has that section on it.
        rows.append('<a href="' + route_url(r) + '"><b>%s</b><i>%d</i></a>'
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


# block_trans() lived here: the homepage's Trans Afrique section, deleted when
# the door absorbed it. It outlived its only caller and went on calling
# route_card(preview=True) after that argument was removed, so it was a second
# broken generator sitting in the file next to block_door — found the same way,
# by running the build rather than by reading it.


# ---- the series: nine pages instead of one ---------------------------------
#
# ONE PAGE WAS DOING THE WORK OF NINE. Desire, philosophy, trust, price, four
# itineraries and an invitation, stacked in one scroll, so a reader met the
# medical protocol two screens after being shown a photograph and three screens
# before deciding they wanted a crossing at all. Length was never the problem;
# the problem was that every question was being answered on the same page as
# every other question, so none of them could be answered properly.
#
#   /trans-afrique                the door: want it, see where it goes, come in
#   /trans-afrique/why            the argument, at the length an argument needs
#   /trans-afrique/crossings      the map, and four ways across
#   /trans-afrique/east|west|
#     south|continental           one journey each, at its own scale
#   /trans-afrique/ways           private, signature, expedition
#   /trans-afrique/support        the six disciplines, and the medical note
#   /trans-afrique/fee            what the fee is, and is not
#
# NOTHING WAS CUT. Every block that was on the long page is on one of these,
# and most of them have more room than they had. The overview is the only page
# that got shorter, which is the whole point of an overview.
#
# The overview keeps the fixed-window opening spread and it is the ONLY page
# that has one. Nothing between .tf-band and .tf-band-pic may carry transform,
# filter, backdrop-filter, perspective, will-change or contain — see
# docs/window-band.md. The child pages open on a still photograph instead: a
# second fixed band on every page of a series turns a technique into a tic.


def series_nav(d, active):
    """The bar that makes nine pages one thing.

    Without it every child page is a cul-de-sac reachable only by going back,
    which is how a split turns a long page into a worse long page. It is an
    ordered list because the series has an order — why, where, how, who, what it
    costs — and a reader who follows it end to end has been told the whole
    argument in the order it makes sense in.
    """
    # NOT STICKY ON THE DOOR. The overview opens on the fixed-window band, and
    # a bar pinned over it is what broke that band at every width: the headline
    # travels the full height of a fixed photograph, so anything parked in its
    # path is something the copy slides under. It also has nothing to offer
    # there — a reader on the first page of a series does not need a way back to
    # the first page of the series. Static here, sticky on the eight pages where
    # it is genuinely a way out.
    out = ['<nav class="tf-series%s" aria-label="Trans Afrique">'
           % (" tf-series--top" if active == "overview" else ""),
           '<a class="tf-series-mark%s" href="/trans-afrique"%s>Trans Afrique</a>'
           % (" is-on" if active == "overview" else "",
              ' aria-current="page"' if active == "overview" else ""),
           '<ol class="tf-series-list">']
    for s_ in d["series"]:
        on = s_["id"] == active
        out.append('<li><a href="/trans-afrique/%s"%s>%s</a></li>'
                   % (esc(s_["id"]),
                      ' aria-current="page"' if on else "", esc(s_["nav"])))
    out.append('</ol></nav>')
    return "".join(out)


def page_top(s_, eyebrow=None, line=None, sub=None):
    """A child page's opening: a still photograph, the eyebrow, the line.

    Deliberately not the band. The fixed-window effect is the door's, and it
    earns its cost once — repeated on eight more pages it stops being an event.
    """
    art = ""
    if s_.get("image"):
        art = ('<div class="tf-top-pic">'
               '<img src="%s" width="%d" height="%d" alt="%s" '
               'fetchpriority="high" decoding="async" data-provider="upload">'
               '<span class="tf-top-tint" aria-hidden="true"></span></div>'
               % (esc(s_["image"]), s_["width"], s_["height"], esc(s_["alt"])))
    return ('<header class="tf-top%s">%s<div class="tf-top-in">'
            '<p class="tf-top-eyebrow">%s</p>'
            '<h1 class="tf-top-h">%s</h1>'
            '<p class="tf-top-sub">%s</p>'
            '</div></header>'
            % (" has-pic" if art else " no-pic", art,
               esc(eyebrow if eyebrow is not None else s_.get("eyebrow")),
               esc(line if line is not None else s_.get("line")),
               esc(sub if sub is not None else s_.get("sub"))))


def next_step(label, href, say=""):
    """One way on, at the foot of a page. A page in a series that ends without
    one has handed the reader back to the browser's Back button."""
    return ('<div class="tf-next">%s'
            '<a class="af-btn tf-next-go" href="%s">%s<i>&rarr;</i></a></div>'
            % ('<p class="tf-next-say">%s</p>' % esc(say) if say else "",
               esc(href), esc(label)))


def by_id(d, key, ident):
    return next((x for x in d[key] if x["id"] == ident), None)


def overview_body(d, by_slug):
    """The door. Want it, see where it goes, understand what it is in one
    paragraph, and be handed the argument rather than given it.

    THIS IS THE ONLY PAGE THAT GOT SHORTER, and everything it lost is one click
    away rather than gone. What stays is what a door is for: the opening spread,
    the chain of countries, the single strongest idea, the thesis on a
    photograph, and the way in. What left is everything that answers a question
    the reader has not asked yet — six support disciplines, three price bands,
    four itineraries, the fee breakdown.
    """
    i = d["idea"]
    return "\n".join([
        # The band already carries the sub, the chain and the way to the
        # crossings — printed ON the photograph, which is the better place for
        # all three. A .tf-lead section repeating them directly underneath said
        # the same three things twice within one screen, which is what happens
        # when a page is split by moving blocks rather than by reading it.
        hero(d, by_slug),
        # THE BAR GOES AFTER THE BAND ON THIS PAGE, not before it. It has to
        # follow the reader down — that is what a series bar is for — and it
        # cannot be pinned over the opening spread, because the headline
        # travels the full height of a FIXED photograph and anything parked in
        # its path is something the copy slides under. Placed here it is out of
        # the band's way entirely and sticky from the moment the band ends,
        # which is the first moment there is anything to navigate away from.
        series_nav(d, "overview"),
        '<div class="tf-page">',
        # The idea, at door length: the line and one paragraph. The rest of it,
        # including the frontier logistics, is /why.
        '<section class="tf-block tf-idea" id="idea">'
        '<h2 class="tf-h2">%s</h2>'
        '<div class="tf-idea-in"><p class="tf-idea-line">%s</p>'
        '<div class="tf-idea-body"><p class="tf-idea-say">%s</p></div></div>'
        '</section>' % (esc(i["title"]), esc(i["line"]), esc(i["say"][0])),
        '</div>',
        philosophy_band(d),
        '<div class="tf-page tf-page--after">',
        # NOT the band's own paragraph again. Handing off with the sentence the
        # reader has just finished reading, forty pixels higher, is the giveaway
        # of a page that was cut up rather than rewritten.
        next_step("Why Trans Afrique", "/trans-afrique/why",
                  "Why it has to be driven, what changes on the way, and why "
                  "nobody assembles a month like this from home."),
        series_index(d),
        '</div>',
        close_block(d),
    ])


def series_index(d):
    """Every page of the series, named, on the page that opens it. The nav bar
    is a way back; this is the table of contents, and it is the reason a reader
    who wants the fee before the philosophy can have it."""
    rows = "".join(
        '<li><a href="/trans-afrique/%s"><b>%s</b><span>%s</span>'
        '<i aria-hidden="true">&rarr;</i></a></li>'
        % (esc(s_["id"]), esc(s_["title"]), esc(s_["sub"]))
        for s_ in d["series"])
    return ('<section class="tf-index"><h2 class="tf-index-h">In this series</h2>'
            '<ol class="tf-index-list">%s</ol></section>' % rows)


def why_body(d, by_slug):
    """The full argument, which is what the overview hands off.

    On the long page this was one section between a photograph and the support
    grid, and it had to be short enough not to delay the machinery. It is the
    reason for the whole product, so here it is the page.
    """
    i = d["idea"]
    ph = d["philosophy"]
    says = "".join('<p class="tf-say">%s</p>' % esc(t) for t in i["say"])
    return "\n".join([
        page_top(by_id(d, "series", "why")),
        '<div class="tf-page tf-page--after">',
        '<section class="tf-block tf-read">'
        '<h2 class="tf-h2">%s</h2>%s</section>' % (esc(i["line"]), says),
        '</div>',
        philosophy_band(d),
        '<div class="tf-page tf-page--after">',
        '<section class="tf-block tf-read">'
        '<h2 class="tf-h2">Nobody assembles that from home</h2>'
        '<p class="tf-say">%s</p></section>' % esc(i["tail"]),
        next_step("The crossings", "/trans-afrique/crossings",
                  "Four ways across, drawn on the continent."),
        '</div>',
    ])


def crossings_body(d, by_slug):
    """The map, and the four journeys as cards that go somewhere.

    The cards used to be the whole record — shape, length, fee, chain, strands —
    printed four times on a page that had already printed a great deal. They are
    a way in now: enough to choose between, and each one opens its own page.
    """
    # THE ROUTE CARDS ARE GONE AND NOTHING WENT WITH THEM. They printed the
    # same four names, the same four country chains and the same shape, length
    # and fee that the plate's own index now carries, one screen further down —
    # so the page said everything about all four crossings twice. Every field
    # from the card is in routemap.build()'s summaries, plus the link to the
    # crossing's own page that the card had.
    return "\n".join([
        page_top(by_id(d, "series", "crossings")),
        '<div class="tf-page tf-page--after">',
        # No heading over the plate: the page's own h1 two hundred pixels above
        # says "Four ways across a continent." and an h3 repeating it under the
        # same sentence was the section talking to itself.
        '<section class="tf-block" id="map">%s</section>'
        % routemap.build(d, by_slug),
        next_step("Ways to travel", "/trans-afrique/ways",
                  "The same roads, run three ways."),
        '</div>',
    ])


def crossing_body(d, r, by_slug):
    """One journey, at its own scale.

    Four itineraries on one page made them a list to be compared rather than
    four journeys to be wanted, and the Continental Expedition — the reason the
    other three exist — was the fourth card in a row of four. Here each one gets
    a photograph, the road drawn on the continent, its countries as a chain, and
    the three answers a reader needs next, which are how to travel it, who
    travels with them, and what the fee covers.
    """
    art = (d.get("crossing_art") or {}).get(r["id"]) or {}
    strands = " &middot; ".join(esc(x) for x in (r.get("strands") or []))
    # A literal middot, not the entity: page_top() escapes what it is handed, so
    # "&middot;" arrived on the page spelled out as &MIDDOT; in the eyebrow.
    top = page_top({"image": art.get("image"), "width": art.get("width", 0),
                    "height": art.get("height", 0), "alt": art.get("alt", "")},
                   eyebrow="%s · Trans Afrique" % d["stamp"],
                   line=r["name"].split("—")[-1].strip(),
                   sub=r["shape"])
    facts = ('<dl class="tf-facts">'
             '<div><dt>Shape</dt><dd>%s</dd></div>'
             '<div><dt>Length</dt><dd>%s days</dd></div>'
             '<div><dt>Countries</dt><dd>%d</dd></div>'
             '<div><dt>Journey fee</dt><dd>%s</dd></div>'
             '</dl>' % (esc(r["shape"]), esc(r["days"]),
                        len(r.get("countries") or []), band(r)))
    return "\n".join([
        top,
        '<div class="tf-page tf-page--after">',
        # The prose keeps a reading measure; the facts do NOT. Left inside the
        # 60ch column, "Nairobi to Arusha, the long way round." broke over three
        # lines in a 150-pixel cell while two thirds of the page sat empty.
        '<section class="tf-block"><div class="tf-read">'
        '<p class="tf-crossing-strands">%s</p>'
        '<p class="tf-crossing-say">%s</p>'
        '<p class="tf-crossing-chain">%s</p></div>'
        '%s</section>' % (strands, esc(r["say"]), chain(r, by_slug), facts),
        '<section class="tf-block" id="map">%s</section>'
        % routemap.build(d, by_slug, only=r["id"],
                         title="%s, on the continent"
                               % (r.get("short") or r["name"]),
                         say=r["shape"],
                         act=("See all four crossings", "/trans-afrique/crossings")),
        onward(d),
        '</div>',
        close_block(d),
    ])


def onward(d):
    """The three questions a reader has once they want a particular crossing,
    each pointing at the page that answers it in full. On the long page these
    were sections above and below; here they are the choice."""
    rows = [("ways", "How you cross", "Private, Signature or Expedition."),
            ("support", "Who travels with you", "Six disciplines, per route."),
            ("fee", "What the fee covers", "And what stays yours.")]
    return ('<section class="tf-onward"><h2 class="tf-index-h">Next</h2>'
            '<ol class="tf-index-list">%s</ol></section>'
            % "".join('<li><a href="/trans-afrique/%s"><b>%s</b><span>%s</span>'
                      '<i aria-hidden="true">&rarr;</i></a></li>'
                      % (k, esc(t), esc(sy)) for k, t, sy in rows))


def ways_body(d, by_slug):
    levels = "\n".join(level_card(v, i) for i, v in enumerate(d["levels"], 1))
    return "\n".join([
        page_top(by_id(d, "series", "ways")),
        '<div class="tf-page tf-page--after">',
        '<section class="tf-block" id="levels">'
        '<div class="tf-levels">%s</div></section>' % levels,
        next_step("Expedition support", "/trans-afrique/support",
                  d["motto"]),
        '</div>',
    ])


def support_body(d, by_slug):
    return "\n".join([
        page_top(by_id(d, "series", "support")),
        '<div class="tf-page tf-page--after">',
        # The motto is this page's headline. Printed again as .tf-motto
        # directly under it, the same fourteen words appeared twice on one
        # screen — the page having been assembled from the old page's blocks
        # without noticing that one of them had been promoted.
        '<section class="tf-block" id="team">'
        '<p class="tf-sup-lede">%s</p>%s</section>'
        % (esc(d["support_say"]), support_grid(d)),
        medical_note(d),
        next_step("What the fee includes", "/trans-afrique/fee",
                  "What Afrinkong earns, what it arranges, and what stays yours."),
        '</div>',
    ])


def fee_body(d, by_slug):
    return "\n".join([
        page_top(by_id(d, "series", "fee")),
        '<div class="tf-page tf-page--after">',
        '<section class="tf-block" id="fee">%s'
        '<p class="tf-fine">%s</p></section>' % (money_lists(d), esc(d["fine"])),
        '</div>',
        close_block(d),
    ])


def run(countries, log=print):
    """Write the nine pages of the series."""
    from . import plate
    d = load()
    by_slug = {c.slug: c for c in countries}
    written = []

    def write(path, title, desc, url, body, active, skip="Skip to the page"):
        html = TEMPLATE % {
            "title": esc(title),
            "desc": esc(desc),
            "og": plate.open_graph(title, desc, url),
            "events": plate.events_block(),
            "nav": series_nav(d, active) if active else "",
            "skip": esc(skip),
            "body": body,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        written.append((os.path.relpath(path, ROOT), len(html)))

    # The overview carries its own bar inside the body, under the band; the
    # slot above <main> stays empty there and is filled on the eight others.
    write(PAGE, "Trans Afrique — Afrinkong", d["say"], "/trans-afrique",
          overview_body(d, by_slug), None, "Skip to the expedition")

    bodies = {"why": why_body, "crossings": crossings_body,
              "ways": ways_body, "support": support_body, "fee": fee_body}
    for s_ in d["series"]:
        write(os.path.join(SUB, "%s.html" % s_["id"]),
              "%s — Trans Afrique" % s_["title"], s_["sub"],
              "/trans-afrique/%s" % s_["id"],
              bodies[s_["id"]](d, by_slug), s_["id"])

    for r in d["routes"]:
        slug = SLUGS.get(r["id"], r["id"])
        write(os.path.join(SUB, "%s.html" % slug),
              "%s — Trans Afrique" % r["name"], r["say"], route_url(r),
              crossing_body(d, r, by_slug), "crossings")

    log("trans-afrique: %d pages, %.1f KB total, %d route(s), %d level(s), %s to %s"
        % (len(written), sum(n for _, n in written) / 1024.0,
           len(d["routes"]), len(d["levels"]),
           money(min(v["low"] for v in d["levels"])),
           money(max(v["high"] for v in d["levels"]))))
    for rel, n in written:
        log("  %-38s %5.1f KB" % (rel, n / 1024.0))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<link rel="stylesheet" href="/styles/transafrique.css">
</head>
<body class="tf-body">
<a class="af-skip" href="#main">%(skip)s</a>
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
%(nav)s

<main id="main">
%(body)s

<div class="tf-page tf-page--foot">
  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</div>
</main>
%(events)s
<script src="/scripts/crossings.js" defer></script>
</body>
</html>
"""
