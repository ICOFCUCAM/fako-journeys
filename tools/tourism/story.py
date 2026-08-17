"""The Living Story Engine: /portrait/<country>, and /stories to find them from.

    python3 tools/tourism/build.py story

The site could already show you Africa four ways — a map, a journey, seven human
doors and five hundred and seventy-two addresses — and none of them was a read.
Every one of those surfaces hands you a paragraph and then asks you to click.
Nobody has ever sat down with this dataset.

So: one long read per country, and a place to find them.

Why twenty-two and not two hundred. Eleven arcs times twenty-two countries is
two hundred and forty-two stories, and two hundred and forty-two pages of three
paragraphs each is a content farm with better typography. The arcs are real —
they are how the page is built and how the index is cut — but they are chapters
of one long read rather than pages of their own, each with an address inside it
(/portrait/uganda#the-table) that a link can land on and the contents can jump
to. One excellent piece about a country beats twenty about its regions.

Nothing on these pages is written here. Every headline is a caption from
tourism/countries/<slug>.json, every paragraph is that caption's description,
every arc's question is a question rather than a claim, and the geography comes
out of the boundary data rather than out of prose. The three things that *are*
written by Afrinkong — the arc questions, the respect notes and the trust block
— all say so on the page.

What ships:

    portrait/<slug>.html   twenty-two long reads
    stories.html           non-linear discovery, search, and Africa this month
    data/stories.json      every story, for the discovery surface and search
"""

import datetime
import html as html_mod
import json
import os

from . import gateway, plate
from .model import (ROOT, load_operators, load_regions, load_voices, region_of)

OUT = os.path.join(ROOT, "portrait")
INDEX_PAGE = os.path.join(ROOT, "stories.html")
DATA = os.path.join(ROOT, "data", "stories.json")
ATLAS_DATA = os.path.join(ROOT, "data", "atlas")
ARCS = os.path.join(ROOT, "tourism", "arcs.json")
RESPECT = os.path.join(ROOT, "tourism", "respect.json")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")
LINKS = os.path.join(ROOT, "data", "links.json")

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# The long line. Four questions rather than four dates, because the dataset
# holds no dates and a timeline that invented them would be the exact failure
# this whole system is built to avoid.
LINE = [
    ("What happened here", ["heritage", "historic-sites"]),
    ("What is kept", ["culture", "festivals", "traditional-people"]),
    ("What is being built", ["cities", "architecture"]),
    ("What is being kept", ["eco-tourism", "forests"]),
]


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def read(path, fallback):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def load_arcs(path=ARCS):
    return (read(path, {}) or {}).get("arcs") or []


class Shim(object):
    """What plate.plate() needs of an entry, from an atlas place."""

    def __init__(self, place):
        self.category = place.get("id")
        self.caption = place.get("title")


# ---- the pieces ------------------------------------------------------------------


def frame(country, place, aspect, tone, shape, sizes, klass="st-frame", eager=False,
          typed=False, caption=False):
    """A photograph at a given shape, or the plate that stands in for it.

    Same box either way, so the day the resolver runs nothing on this page
    moves. Below-the-fold frames are lazy and carry their own dimensions, which
    is most of what keeps a page with a dozen pictures on it fast.

    `typed` is the difference between one plate and twelve. A plate with no type
    on it is right on a page that shows one; a photo essay of seven of them is
    seven copies of the same outline, which reads as a page that failed to load
    rather than as a page whose pictures have not been taken. Where the layout
    does not print the caption beside the frame, the plate carries it, and the
    seven become seven different things.
    """
    aw, ah = aspect
    img = (place.get("image") or {})
    # A credit is never optional; a caption is, because in most of these layouts
    # the same sentence is already set beside the frame and printing it under
    # the frame as well is the commonest way a generated page reads as generated.
    words = esc(place["text"]) if caption else ""
    if img.get("url"):
        credit = (('<i>Photograph %s</i>' % esc(img["credit"]))
                  if img.get("credit") else "")
        return ('<figure class="%s"><img src="%s" alt="%s" width="%d" height="%d" '
                'sizes="%s" %s decoding="async" style="aspect-ratio:%d/%d">'
                '%s</figure>'
                % (klass, esc(img["url"]), esc(img.get("alt") or place["text"]),
                   aw * 100, ah * 100, esc(sizes),
                   'fetchpriority="high"' if eager else 'loading="lazy"',
                   aw, ah,
                   ('<figcaption>%s%s</figcaption>' % (words, credit))
                   if (words or credit) else ""))
    return ('<figure class="%s">%s%s</figure>'
            % (klass, plate.plate(country, Shim(place), aspect, place["title"],
                                  shape=shape, ident="st-%s-%s" % (country.slug, place["id"]),
                                  ground=not typed),
               ('<figcaption>%s</figcaption>' % words) if words else ""))


def chapter_body(place, country):
    """One write-up, as prose with its own address.

    The link is not decoration. It is the same place's page, which is the only
    thing on this site that can be indexed, sent, or read with JavaScript off.
    """
    return ('<div class="st-say"><h3><a href="%s">%s</a></h3><p>%s</p></div>'
            # The fallback is for a place whose page was not written; /places/<slug>
            # is a folder with no index and would 404, so it falls back to that
            # country's section on the places index instead.
            % (esc(place.get("url") or "/places#%s" % country.slug),
               esc(place["title"]), esc(place["text"])))


def arc_section(country, arc, chapters, ctx):
    """One arc, printed in its format's own shape.

    Ten formats, ten layouts. The rule they share is that none of them is a grid
    of equal rectangles — a country whose heritage looks exactly like its food
    looks like a database, and this is the part of the site that is supposed to
    read like a magazine.
    """
    tone = ctx["tone"]
    shape = ctx["shape"]
    fmt = arc["format"]
    lead, rest = chapters[0], chapters[1:]
    # Headline, standfirst, body — in that order and each sentence used once.
    # The headline is the lead write-up's own caption, which is why a story here
    # is called "Rolex, Matoke, Luwombo" and not "Food in Uganda"; the standfirst
    # is that write-up's description; and the body is everything else. Printing
    # the lead again further down is the single easiest way to make a generated
    # page look generated, and it is what the split above exists to prevent.
    head = ('<header class="st-head">'
            '<span class="af-stamp">%s &middot; %s</span>'
            '<h2 class="st-h2" id="%s">%s</h2>'
            '<p class="st-asks">%s</p>'
            '<p class="st-stand"><a href="%s">%s</a></p>'
            '<p class="st-line">%s</p></header>'
            % (esc(country.name), esc(arc["title"]), esc(arc["key"]),
               esc(lead["title"]), esc(arc["asks"]),
               esc(lead.get("url") or "#"), esc(lead["text"]), esc(arc["line"])))

    if fmt == "essay":
        # A photo essay. Capped at twelve, which is the point at which a reader
        # stops reading captions and starts scrolling past pictures.
        #
        # The shape of each frame follows the width it will be given, rather than
        # being chosen and then stretched: a sixteen-by-nine frame six columns
        # wide is six hundred pixels tall and has stopped being a frame. The
        # opening one carries no type because the headline above it is already
        # its caption; the rest carry their own, which is what stops seven
        # unresolved plates reading as one picture that failed to load.
        shapes = [(21, 9), (4, 3), (4, 3), (4, 5), (16, 9), (4, 3)]
        plates = "".join(
            frame(country, p, shapes[i % 6], tone, shape,
                  "(min-width:900px) 46vw, 92vw", klass="st-plate",
                  typed=i > 0, caption=i > 0)
            for i, p in enumerate(chapters[:12]))
        return ('<section class="st st--essay" style="--tone:%s">%s'
                '<div class="st-essay">%s</div>'
                '<p class="st-count">%d frames. Every one of them a different '
                'part of %s, and each caption written for that one.</p></section>'
                % (esc(tone), head, plates, len(chapters[:12]), esc(country.name)))

    if fmt == "now":
        # The contemporary panel, set dark and set apart, because the thing it is
        # arguing against is the rest of the category — a continent filed under
        # wildlife and left there.
        cards = "".join(
            '<article class="st-nowcard"><a href="%s"><b>%s</b><p>%s</p>'
            '<span>%s</span></a></article>'
            % (esc(p.get("url") or "#"), esc(p["title"]), esc(p["text"]), esc(p["group"]))
            for p in rest)
        return ('<section class="st st--now" style="--tone:%s">%s'
                '<div class="st-nowgrid">%s</div>'
                '<p class="st-count">Africa is not a museum. Nothing above is a '
                'ruin, a costume or an animal &mdash; it is where people in %s '
                'live, build and work.</p></section>'
                % (esc(tone), head, cards, esc(country.name)))

    if fmt == "note":
        return ('<section class="st st--note" style="--tone:%s">%s'
                '<div class="st-notebody">%s</div></section>'
                % (esc(tone), head,
                   "".join('<p class="st-big"><a href="%s">%s</a> &mdash; %s</p>'
                           % (esc(p.get("url") or "#"), esc(p["title"]), esc(p["text"]))
                           for p in rest)))

    if fmt == "journey":
        return ""       # built separately: it comes from geography, not prose

    if fmt == "people":
        # Portrait proportions and a Local Voice slot that stays empty. The slot
        # is the honest part: it is where a person's own words would go, and
        # printing a plausible-sounding one would be the single worst thing this
        # site could do.
        return ('<section class="st st--people" style="--tone:%s">%s'
                '<div class="st-two">%s<div class="st-col">%s%s</div></div></section>'
                % (esc(tone), head,
                   frame(country, lead, (4, 5), tone, shape,
                         "(min-width:900px) 42vw, 92vw", klass="st-portrait"),
                   "".join(chapter_body(p, country) for p in rest),
                   ctx["voice"]))

    if fmt == "heritage":
        rows = "".join(
            '<li><a href="%s"><b>%s</b><span>%s</span></a><p>%s</p></li>'
            % (esc(p.get("url") or "#"), esc(p["title"]), esc(p["group"]), esc(p["text"]))
            for p in rest)
        return ('<section class="st st--heritage" style="--tone:%s">%s'
                '<div class="st-two">%s<ol class="st-evidence">%s</ol></div>'
                '<p class="st-count">Undated on purpose. Where a date belongs to '
                'one of these claims it is in the country file; this page does not '
                'supply one that is not.</p></section>'
                % (esc(tone), head,
                   frame(country, lead, (16, 9), tone, shape,
                         "(min-width:900px) 46vw, 92vw"), rows))

    if fmt in ("food", "craft"):
        # Ingredient-to-table, or material-to-object: an order, not a grid.
        steps = "".join(
            '<li class="st-step"><span class="st-n">%d</span>%s'
            '<div><h3><a href="%s">%s</a></h3><p>%s</p></div></li>'
            % (i + 1,
               frame(country, p, (3, 2), tone, shape,
                     "(min-width:900px) 34vw, 92vw", klass="st-strip"),
               esc(p.get("url") or "#"), esc(p["title"]), esc(p["text"]))
            for i, p in enumerate(rest))
        return ('<section class="st st--%s" style="--tone:%s">%s'
                '<ol class="st-steps">%s</ol></section>'
                % (esc(fmt), esc(tone), head, steps))

    if fmt == "wild":
        return ('<section class="st st--wild" style="--tone:%s">%s'
                '<div class="st-guide">%s<div class="st-col">%s</div></div>'
                '<p class="st-count">The animals are the easy half. Which habitat, '
                'whose land, and what a visitor&rsquo;s money does when it arrives '
                'is the rest of it, and %s answers it in its own words above.</p>'
                '</section>'
                % (esc(tone), head,
                   frame(country, lead, (16, 9), tone, shape, "100vw",
                         klass="st-wide"),
                   "".join(chapter_body(p, country) for p in rest),
                   esc(country.name)))

    # culture, and anything a new format has not been drawn for yet
    return ('<section class="st st--culture" style="--tone:%s">%s'
            '<div class="st-two">%s<div class="st-col">%s</div></div></section>'
            % (esc(tone), head,
               frame(country, lead, (16, 9), tone, shape,
                     "(min-width:900px) 50vw, 92vw"),
               "".join(chapter_body(p, country) for p in rest)))


def crossing(country, ctx):
    """The journey arc. Geography, read off the boundary file.

    Every other arc is prose the country wrote about itself. This one is the
    only thing on the page the country did not say: which countries it actually
    touches, taken from the Natural Earth polygons that links.json was built
    from, and how far apart the two centres are in a straight line. Straight
    line, said every time, because this site holds no road and no timetable and
    a number labelled otherwise would be a promise.
    """
    rows = ctx["links"].get(country.slug) or []
    if not rows:
        return ""
    cards = []
    for r in rows[:6]:
        borders = any(w["kind"] == "border" for w in r["why"])
        calls = ", ".join((ctx["graph"].get(r["to"]) or {}).get("calls") or [])
        cards.append(
            '<li class="st-cross%s"><a href="/portrait/%s"><b>%s</b>'
            '<span>%s</span><i>%s</i></a>%s</li>'
            % (" is-border" if borders else "", esc(r["to"]), esc(r["name"]),
               esc("shares a land border" if borders else "no land border"),
               esc("%d km in a straight line" % r["km"]) if r.get("km") is not None else "",
               ('<p>Leads on %s.</p>' % esc(calls)) if calls else ""))
    return ('<section class="st st--journey" style="--tone:%s">'
            '<header class="st-head"><span class="af-stamp">%s &middot; The crossing</span>'
            '<h2 class="st-h2" id="the-crossing">What is on the other side</h2>'
            '<p class="st-asks">Where does %s actually stop?</p>'
            '<p class="st-line">Read off the boundary data rather than written: '
            'countries whose polygons share a vertex with this one share a land '
            'border with it. Distances are between country centres, in a straight '
            'line &mdash; not a drive, and not a flight.</p></header>'
            '<ul class="st-crossings">%s</ul>'
            '<a class="af-btn af-btn--solid" href="/journey#/j/%s/">Build a journey '
            'that crosses one<i>&rarr;</i></a></section>'
            % (esc(ctx["tone"]), esc(country.name), esc(country.name),
               "".join(cards), esc(country.slug)))


def long_line(country, by_cat, ctx):
    cols = []
    for title, cats in LINE:
        items = [by_cat[c] for c in cats if c in by_cat]
        if not items:
            continue
        cols.append('<div class="po-lane"><h3>%s</h3>%s</div>'
                    % (esc(title),
                       "".join('<a href="%s"><b>%s</b><span>%s</span></a>'
                               % (esc(p.get("url") or "#"), esc(p["title"]), esc(p["text"]))
                               for p in items)))
    if not cols:
        return ""
    return ('<section class="po-line" id="the-long-line">'
            '<span class="af-stamp">%s &middot; The long line</span>'
            '<h2 class="po-h2">Four questions, not four dates</h2>'
            '<p class="po-lede">A timeline would need dates, and the write-ups '
            'behind this page do not carry them. So this is the same country '
            'asked four things instead, in the order they tend to answer them.</p>'
            '<div class="po-lanes">%s</div></section>'
            % (esc(country.name), "".join(cols)))


def season(country):
    good = set(country.months or [])
    chips = "".join(
        '<li%s data-month="%d"><b>%s</b><span>%s</span></li>'
        % (' class="is-good"' if (i + 1) in good else "", i + 1, esc(m[:3]),
           esc("good" if (i + 1) in good else "&mdash;"))
        for i, m in enumerate(MONTHS))
    when = ('<p class="po-when">%s</p>' % esc(country.when)) if country.when else ""
    return ('<section class="po-season" id="when">'
            '<span class="af-stamp">%s &middot; When</span>'
            '<h2 class="po-h2">The months this country is good in</h2>'
            '<p class="po-lede">Out of the country file, not out of a weather API. '
            'These are the months %s is written up as good in, which is a coarser '
            'and more honest thing than a forecast.</p>'
            '<ol class="po-months" aria-label="Months">%s</ol>%s'
            '<p class="po-now" id="po-now" role="status"></p></section>'
            % (esc(country.name), esc(country.name), chips, when))


def voice_block(country, ops):
    """Local Voice. Empty, and saying why.

    tourism/voices.json has been empty since the day it was created and it will
    stay empty until somebody has actually asked a person and written down what
    they said. A component that renders nothing looks like a bug; a component
    that renders this looks like a decision, which is what it is.
    """
    voices = [v for v in load_voices() if getattr(v, "country", None) == country.slug]
    if voices:
        v = voices[0]
        return ('<blockquote class="po-voice"><span class="af-stamp">Local voice</span>'
                '<p>%s</p><cite>%s%s</cite></blockquote>'
                % (esc(v.quote), esc(v.name),
                   (", %s" % esc(v.role)) if getattr(v, "role", None) else ""))
    op = ops.get(country.operator_key)
    return ('<div class="po-voice po-voice--empty"><span class="af-stamp">Local voice</span>'
            '<p>Nobody from %s has been quoted on this page, so nobody is. '
            'This slot takes one sentence from one named person who agreed to it '
            '&mdash; a guide, a cook, a maker, a ranger &mdash; and until there is '
            'one it stays as it is rather than borrowing something plausible.</p>'
            '%s</div>'
            % (esc(country.name),
               ('<p class="po-voice-who">The company that works here is <b>%s</b>, '
                'based in %s. Nothing above is a quotation from them; it is written '
                'by Afrinkong.</p>' % (esc(op.name), esc(op.base))) if op else ""))


def respect_block(notes):
    kinds = [("camera", "With a camera"), ("people", "With people"),
             ("place", "With the place"), ("money", "With money")]
    cols = []
    for key, title in kinds:
        rows = [n for n in notes if n.get("kind") == key]
        if not rows:
            continue
        cols.append('<div class="po-care"><h3>%s</h3>%s</div>'
                    % (esc(title),
                       "".join('<p><b>%s</b> %s</p>' % (esc(n["title"]), esc(n["line"]))
                               for n in rows)))
    return ('<section class="po-respect" id="how-to-be-here">'
            '<span class="af-stamp">Ours, not theirs</span>'
            '<h2 class="po-h2">How to be here</h2>'
            '<p class="po-lede">The one thing on this page that is a position '
            'rather than a fact. It is not any country&rsquo;s rule and no '
            'community here was asked to write it &mdash; it is what Afrinkong asks '
            'of the people it sends, and the reasons are the part worth carrying.</p>'
            '<div class="po-cares">%s</div></section>' % "".join(cols))


def trust_block(country, pack, ops, arcs_used):
    op = ops.get(country.operator_key)
    shot = sum(1 for p in pack["places"] if (p.get("image") or {}).get("url"))
    total = len(pack["places"])
    return ('<section class="po-trust" id="who-is-telling-you-this">'
            '<span class="af-stamp">Provenance</span>'
            '<h2 class="po-h2">Who is telling you this</h2>'
            '<dl class="po-dl">'
            '<div><dt>The writing</dt><dd>Afrinkong editorial. Every headline and '
            'paragraph on this page is a caption and a description from '
            '<code>tourism/countries/%s.json</code>, printed here unchanged. There '
            'is no second copy that could drift from it: this page is generated '
            'from that file on every build.</dd></div>'
            '<div><dt>What it is not</dt><dd>Not sourced reporting. These are '
            'summaries written for a travel site, not claims with citations behind '
            'them, and they should be read as the former. Where a fact matters to '
            'your plans, check it against the country.</dd></div>'
            '<div><dt>The photographs</dt><dd>%s Every photograph carries its '
            'photographer&rsquo;s name. Nothing here is an AI image dressed as a '
            'photograph; where there is no picture, the shape of %s is drawn '
            'instead and says so.</dd></div>'
            '<div><dt>The geography</dt><dd>Borders and distances come from Natural '
            'Earth boundary data, not from the prose. Distances are straight lines '
            'between country centres. This site holds no road, no timetable and no '
            'travel time, and prints none.</dd></div>'
            '<div><dt>The company</dt><dd>%s</dd></div>'
            '<div><dt>The reading</dt><dd>%d chapters, cut from the %d write-ups '
            'this country has. The cut is editorial; the words are not.</dd></div>'
            '</dl></section>'
            % (esc(country.slug),
               ("%d of the %d slots on this page have a photograph." % (shot, total))
               if shot else
               ("None of the %d photographs for %s has been placed yet." % (total, country.name)),
               esc(country.name),
               ('<b>%s</b>, based in %s, since %s. They are the company who would '
                'run a journey here. Nothing on this page is a quotation from them '
                'or written by them.' % (esc(op.name), esc(op.base), esc(op.since)))
               if op else
               # Was "No operator of ours runs <Country>." The useful half of
               # that sentence is the second one — that nothing here is an
               # operator's marketing — and it is true either way, so it is
               # the only half kept.
               'The ground journey in %s is run by Afrinkong. Nothing on this '
               'page is written by an operator either way.' % esc(country.name),
               arcs_used, total))


# ---- one portrait ----------------------------------------------------------------


def chapters_for(arc, by_cat):
    """The write-ups behind one arc in one country, in reading order, or none.

    One rule, used twice: once to print the section and once to index it. Two
    rules would eventually disagree, and the disagreement would be a story in
    the index pointing at an anchor that is not on the page.
    """
    chapters = [by_cat[c] for c in arc["categories"] if c in by_cat]
    if len(chapters) < max(1, arc.get("min") or 1):
        return []
    # The lead category leads if the country has it; otherwise the first chapter
    # it does have does, rather than the arc being dropped for want of one
    # write-up.
    if arc.get("lead") and arc["lead"] in by_cat:
        head = by_cat[arc["lead"]]
        chapters = [head] + [c for c in chapters if c["id"] != head["id"]]
    return chapters


def story_row(country, region_key, arc, chapters):
    return {
        "id": "%s/%s" % (country.slug, arc["key"]),
        "country": country.slug, "countryName": country.name,
        "region": country.region, "regionKey": region_key,
        "arc": arc["key"], "arcTitle": arc["title"], "format": arc["format"],
        "asks": arc["asks"], "now": bool(arc.get("now")),
        "title": chapters[0]["title"], "text": chapters[0]["text"],
        "url": "/portrait/%s#%s" % (country.slug, arc["key"]),
        "chapters": [p["id"] for p in chapters],
        "lenses": sorted({l for p in chapters for l in (p.get("lenses") or [])}),
        "image": (chapters[0].get("image") or {}).get("url"),
    }


def portrait(country, pack, arcs, ctx):
    """-> (the page, the stories on it). Both from one walk of the arcs, so the
    index cannot describe a chapter the page does not have."""
    by_cat = {p["id"]: p for p in pack["places"]}
    tone = plate.tone_for(country, ctx["regions"])
    shape = ctx["shapes"].get(country.slug)
    key, _reg = region_of(country, ctx["regions"])
    inner = dict(ctx, tone=tone, shape=shape,
                 voice=voice_block(country, ctx["operators"]))

    sections, contents, stories = [], [], []
    for arc in arcs:
        if arc["format"] == "journey":
            continue
        chapters = chapters_for(arc, by_cat)
        if not chapters:
            continue
        sections.append(arc_section(country, arc, chapters, inner))
        contents.append('<a href="#%s">%s</a>' % (esc(arc["key"]), esc(arc["title"])))
        stories.append(story_row(country, key, arc, chapters))

    cross = crossing(country, inner)
    if cross:
        contents.append('<a href="#the-crossing">The crossing</a>')
    contents.append('<a href="#the-long-line">The long line</a>')
    contents.append('<a href="#when">When</a>')

    hero = by_cat.get("why-visit") or pack["places"][0]
    window = plate.window_svg(shape, country.name, ident="po-%s" % country.slug)

    # The portrait and /tourism/<slug> both describe the same country, and both
    # were using its summary — two indexable pages with one description, each
    # arguing the other's case. The catalogue keeps the summary; a portrait is
    # described by what it actually is, which is a read of a particular shape.
    named = [a["title"].lower() for a in arcs
             if a["key"] in {s["arc"] for s in stories}][:3]
    blurb = ("%s in %d chapters%s. Every paragraph is %s's own writing, not "
             "an article about Africa."
             % (country.name, len(sections),
                (" — " + ", ".join(named)) if named else "", country.name))

    # Fitted to the ~155 characters a search result shows. The blurb names
    # every section of the portrait, so on the countries with the most written
    # about them it was the longest — and the most truncated.
    blurb = plate.fit("", blurb)
    return stories, TEMPLATE % {
        "title": esc("%s: a portrait — Afrinkong" % country.name),
        "description": esc(blurb),
        "og": plate.open_graph(esc("%s: a portrait" % country.name), esc(blurb),
                               "/portrait/%s" % country.slug, kind="article"),
        "jsonld": json_ld(country, key, len(sections)),
        "country": esc(country.name),
        "slug": esc(country.slug),
        "adjective": esc(country.adjective or country.name),
        "regionKey": esc(key),
        "region": esc(country.region),
        "tagline": esc(country.tagline),
        "summary": esc(country.summary),
        "tone": esc(tone),
        "window": window,
        "windowNote": esc("The outline of %s. No photograph is inside it yet."
                          % country.name) if window else "",
        "contents": "".join(contents),
        "chapters": len(sections),
        "places": len(pack["places"]),
        "sections": "\n".join(sections),
        "crossing": cross,
        "line": long_line(country, by_cat, inner),
        "season": season(country),
        "respect": respect_block(ctx["respect"]),
        "trust": trust_block(country, pack, ctx["operators"], len(sections)),
        "url": esc(country.url),
        "hero": esc(hero["text"]),
        "events": plate.events_block(),
        "explore": plate.explore_block(),
    }


def json_ld(country, region_key, chapters):
    """Structured metadata, and only what is true.

    No author person, no dateModified invented for the occasion, no aggregate
    rating. An Article with a headline, a description and the place it is about.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "%s: a portrait" % country.name,
        "description": country.summary,
        "articleSection": "Travel",
        "isAccessibleForFree": True,
        "publisher": {"@type": "Organization", "name": "Afrinkong"},
        "about": {"@type": "Country", "name": country.name},
        "mainEntityOfPage": "https://afrinkong.com/portrait/%s" % country.slug,
        "hasPart": [{"@type": "WebPageElement", "name": "The crossing"}] if chapters else [],
    }
    return ('<script type="application/ld+json">%s</script>'
            % json.dumps(data, separators=(",", ":")))


# ---- the discovery surface -------------------------------------------------------


def index_page(stories, ctx, countries):
    """Everything, cut every way, with no order forced on it.

    Three ways in, which is the whole argument of the page: by what you are
    interested in, by where, or by what month it is when you arrive. None of
    them is the front of a queue.
    """
    now_rows = [s for s in stories if s["now"]][:24]
    now_cards = "".join(
        '<article class="sx-now"><a href="%s"><span>%s &middot; %s</span>'
        '<b>%s</b><p>%s</p></a></article>'
        % (esc(s["url"]), esc(s["countryName"]), esc(s["arcTitle"]),
           esc(s["title"]), esc(s["text"]))
        for s in now_rows)

    by_format = {}
    for s in stories:
        by_format.setdefault(s["format"], []).append(s)
    rails = []
    for fmt, note in ctx["formats"].items():
        rows = by_format.get(fmt) or []
        if not rows:
            continue
        rails.append(
            '<section class="sx-rail" data-format="%s"><h2>%s<span>%d</span></h2>'
            '<p class="sx-note">%s</p><div class="sx-scroll">%s</div></section>'
            % (esc(fmt), esc(fmt.title()), len(rows), esc(note),
               "".join('<a class="sx-card" href="%s" data-country="%s">'
                       '<span>%s</span><b>%s</b><p>%s</p></a>'
                       % (esc(s["url"]), esc(s["country"]), esc(s["countryName"]),
                          esc(s["title"]), esc(s["text"]))
                       for s in rows)))

    portraits = "".join(
        '<a class="sx-portrait" href="/portrait/%s" style="--tone:%s">'
        '<b>%s</b><span>%s</span><i>%s</i></a>'
        % (esc(c.slug), esc(plate.tone_for(c, ctx["regions"])), esc(c.name),
           esc(c.tagline), esc(c.region))
        for c in countries)

    # The months, inlined. This section is the first thing below the fold and it
    # needs one number from the visitor's clock and twenty-two lists of months —
    # about a kilobyte. Fetching the whole graph for it would put a hundred and
    # sixty kilobytes on the critical path of a page most people will scroll and
    # never search, so the graph waits until somebody puts a cursor in the box.
    when = {c.slug: {"name": c.name, "line": c.tagline or c.region,
                     "months": c.months} for c in countries}

    return INDEX % {
        "when": json.dumps(when, separators=(",", ":"), sort_keys=True),
        "og": plate.open_graph("Stories &mdash; Afrinkong",
                               "%d stories across %d countries, each one built out "
                               "of what that country says about itself."
                               % (len(stories), len(countries)), "/stories"),
        "n": len(stories), "countries": len(countries),
        # One portrait per country, spelled out because the heading is a
        # sentence and not a statistic. It read "Twenty-two portraits" over a
        # grid of fifty-four of them until this was derived.
        "nportraits": gateway._spell(len(countries)),
        "nspelled": gateway._spell(len(countries)).lower(),
        "now": now_cards, "rails": "\n".join(rails), "portraits": portraits,
        "events": plate.events_block(),
        "explore": plate.explore_block(),
        "explore": plate.explore_block(),
    }


# ---- build -----------------------------------------------------------------------


def run(countries, taxonomy, log=print):
    arcs = load_arcs()
    respect = (read(RESPECT, {}) or {}).get("notes") or []
    graph = (read(os.path.join(ROOT, "data", "graph.json"), {}) or {}).get("countries") or {}
    ctx = {
        "regions": load_regions(),
        "operators": load_operators(),
        "shapes": read(SHAPES, {}),
        "links": (read(LINKS, {}) or {}).get("links") or {},
        "respect": respect,
        "graph": graph,
        "formats": (read(ARCS, {}) or {}).get("$formats") or {},
    }

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    live = [c for c in countries if c.published]
    stories, written, keep = [], 0, set()
    for country in live:
        pack = read(os.path.join(ATLAS_DATA, "%s.json" % country.slug), None)
        if not pack or not pack.get("places"):
            continue
        rows, page = portrait(country, pack, arcs, ctx)
        name = "%s.html" % country.slug
        keep.add(name)
        with open(os.path.join(OUT, name), "w") as fh:
            fh.write(page)
        written += 1
        stories.extend(rows)
    for stale in os.listdir(OUT):
        if stale.endswith(".html") and stale not in keep:
            os.remove(os.path.join(OUT, stale))

    with open(INDEX_PAGE, "w") as fh:
        fh.write(index_page(stories, ctx, live))
    folder = os.path.dirname(DATA)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(DATA, "w") as fh:
        json.dump({"stories": stories,
                   "formats": ctx["formats"],
                   "built": datetime.date.today().isoformat()},
                  fh, separators=(",", ":"), sort_keys=True)

    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    log("story: %d portraits (%.1f KB), %d stories across %d arcs, plus /stories"
        % (written, size / 1024.0, len(stories),
           len({s["arc"] for s in stories})))
    return written


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
%(og)s
<link rel="canonical" href="https://afrinkong.com/portrait/%(slug)s">
%(jsonld)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/places.css">
<link rel="stylesheet" href="/styles/story.css">
</head>
<body class="po-body" style="--tone:%(tone)s">
<a class="af-skip" href="#main">Skip to the portrait</a>
<div class="po-progress" id="po-progress" aria-hidden="true"><i></i></div>
<header class="pl-mast">
  <a class="pl-mark" href="/"><i>Afrinkong</i><b>%(country)s</b></a>
  <nav class="pl-routes" aria-label="Primary">
    <a href="/stories">Stories</a>
    <a href="/atlas#/%(slug)s">The Atlas</a>
    <a href="/journey#/j/%(slug)s/">Build a journey</a>
    <a href="/places#%(slug)s">Every place</a>
  </nav>
  <a class="af-btn af-btn--solid" href="/journey">Build a journey<i>&rarr;</i></a>
</header>

<main class="po" id="main">
  <nav class="pl-where" aria-label="Where you are">
    <ol>
      <li><a href="/atlas">Africa</a></li>
      <li><a href="/atlas#/%(regionKey)s">%(region)s</a></li>
      <li><a href="/stories">Stories</a></li>
      <li><span aria-current="page">%(country)s</span></li>
    </ol>
  </nav>

  <header class="po-open">
    <div class="po-open-say">
      <span class="af-stamp">A portrait &middot; %(region)s</span>
      <h1 class="po-h1">%(country)s</h1>
      <p class="po-tag">%(tagline)s</p>
      <p class="po-lede">%(summary)s</p>
      <p class="po-meta">%(chapters)d chapters &middot; %(places)d write-ups &middot;
        one country, not a continent</p>
    </div>
    <div class="po-open-win">%(window)s<span>%(windowNote)s</span></div>
  </header>

  <nav class="po-contents" aria-label="Contents">
    <span>In this portrait</span>
    <div class="po-jump">%(contents)s</div>
  </nav>

%(sections)s
%(crossing)s
%(line)s
%(season)s
%(respect)s
%(trust)s

  <section class="po-onward">
    <h2 class="po-h2">From here</h2>
    <div class="po-acts">
      <a class="af-btn af-btn--solid" href="/journey#/j/%(slug)s/">Build a journey in %(country)s<i>&rarr;</i></a>
      <a class="af-btn af-btn--quiet" href="/atlas#/%(slug)s">Find it on the map</a>
      <a class="af-btn af-btn--quiet" href="/meet#/%(slug)s">Meet %(country)s</a>
      <a class="af-btn af-btn--quiet" href="/places#%(slug)s">All %(places)d write-ups</a>
      <a class="af-btn af-btn--quiet" href="%(url)s">The company that works here</a>
    </div>
  </section>
</main>

%(events)s
%(explore)s
<script src="/scripts/portrait.js" defer></script>
<footer class="pl-foot">
  <div class="pl-foot-in">
    <p class="pl-foot-bar"><a href="/">Afrinkong</a> &middot; %(country)s &middot;
      <a href="/stories">every story</a> &middot;
      <a href="/places">every place</a> &middot;
      <a href="/enquire">enquire</a></p>
    <p class="pl-foot-co"><!-- gen:company -->
    <!-- /gen:company --></p>
  </div>
</footer>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stories &mdash; Afrinkong</title>
<meta name="description" content="Africa read rather than browsed: portraits of %(nspelled)s countries, built entirely out of what each one says about itself.">
%(og)s
<link rel="canonical" href="https://afrinkong.com/stories">
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/places.css">
<link rel="stylesheet" href="/styles/story.css">
</head>
<body class="sx-body">
<a class="af-skip" href="#main">Skip to the stories</a>
<header class="pl-mast">
  <a class="pl-mark" href="/"><i>Afrinkong</i><b>Stories</b></a>
  <nav class="pl-routes" aria-label="Primary">
    <a href="/atlas">The Atlas</a>
    <a href="/journey">Build a journey</a>
    <a href="/meet">Meet Africa</a>
    <a href="/places">Every place</a>
  </nav>
  <a class="af-btn af-btn--solid" href="/journey">Build a journey<i>&rarr;</i></a>
</header>

<main class="sx" id="main">
  <section class="sx-open">
    <span class="af-stamp">The reading room</span>
    <h1 class="sx-h1">Africa,<br>at reading length.</h1>
    <p class="sx-lede">%(n)d stories across %(countries)d countries. Not articles
      written about Africa &mdash; each one is cut from what that country already
      says about itself, in that country&rsquo;s own file, and every paragraph in
      it has an address of its own you can open.</p>
    <form class="sx-find" role="search" autocomplete="off">
      <label for="sx-q">Ask for something</label>
      <input id="sx-q" type="search" placeholder="food in Cameroon &middot; heritage in Ethiopia &middot; Kampala">
      <p class="sx-said" id="sx-said" role="status"></p>
    </form>
    <div class="sx-results" id="sx-results" hidden></div>
  </section>

  <section class="sx-nowsec" id="africa-now">
    <div class="sx-nowhead">
      <span class="af-stamp">Africa now</span>
      <h2 class="sx-h2">Not a museum</h2>
      <p>The cities, the building, the cooking and the making &mdash; the parts of
        this continent a safari catalogue leaves out. Every one of them written
        for a particular country, not for a continent.</p>
    </div>
    <div class="sx-nowgrid">%(now)s</div>
  </section>

  <section class="sx-month" id="this-month">
    <span class="af-stamp">Right now</span>
    <h2 class="sx-h2" id="sx-monthh">Africa this month</h2>
    <p class="sx-lede">Not a live feed and not an events calendar &mdash; this site
      holds no dates and will not invent any. This is the plainer, truer version:
      which countries are written up as good in the month it is where you are
      sitting.</p>
    <div class="sx-monthlist" id="sx-monthlist"></div>
  </section>

  <section class="sx-portraits">
    <span class="af-stamp">The long reads</span>
    <h2 class="sx-h2">%(nportraits)s portraits</h2>
    <div class="sx-portgrid">%(portraits)s</div>
  </section>

%(rails)s
</main>

<script type="application/json" id="sx-boot">{"data":"/data/stories.json","graph":"/data/graph.json","when":%(when)s}</script>
%(events)s
%(explore)s
<script src="/scripts/story-search.js" defer></script>
<script src="/scripts/stories.js" defer></script>
<footer class="pl-foot">
  <div class="pl-foot-in">
    <p class="pl-foot-bar"><a href="/">Afrinkong</a> &middot;
      <a href="/places">every place</a> &middot;
      <a href="/atlas">the atlas</a> &middot;
      <a href="/enquire">enquire</a></p>
    <p class="pl-foot-co"><!-- gen:company -->
    <!-- /gen:company --></p>
  </div>
</footer>
</body>
</html>
"""
