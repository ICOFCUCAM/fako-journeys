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


def shot(w, sizes, klass="wo-shot"):
    """A wonder's photograph, or nothing at all.

    Four of the twenty-three have one. There is no placeholder and no borrowed
    frame: a photograph under a place name is a claim that the photograph is OF
    that place, and the repository can only stand behind four of those. On the
    homepage a wonder with no photograph is named in the index instead of being
    given an empty frame; on /wonders, where every one of the twenty-three has
    to appear, the card simply has no picture in it.
    """
    if not w.get("photo"):
        return ""
    # width and height on every one, from the file rather than guessed: the
    # frames are 4:3 and 16:10 boxes with object-fit, so without the intrinsic
    # size the browser has nothing to reserve and the whole section below the
    # gallery jumps when the photographs land.
    # The crop is named in the file, not left to the centre. Kilimanjaro's
    # photograph is a tall portrait — summit at the top, elephant at the
    # bottom — and a centred cover crop of it into a 4:3 frame is a rectangle
    # of cloud with no mountain in it.
    focal = w.get("focal")
    pos = (' style="object-position:%s%% %s%%"' % (focal[0], focal[1])) if focal else ""
    return ('<div class="%s"><img src="%s" alt="%s" width="%d" height="%d"%s '
            'loading="lazy" decoding="async" sizes="%s" data-provider="upload"></div>'
            % (klass, esc(w["photo"]), esc(w.get("photo_alt") or ""),
               int(w.get("photo_w") or 1600), int(w.get("photo_h") or 900),
               pos, esc(sizes)))


def card(w, by_slug):
    """A supporting wonder, on the homepage gallery and on every strand of
    /wonders. Image-led where there is an image; the type is the same either
    way, so a strand that is half photographed still reads as one grid.

    It used to take a `big` flag for the two leads. They have their own shape
    now — see feature() — and a flag that nothing passes is a second design
    still sitting in the file pretending to be reachable.
    """
    return (
        '<article class="wo-card%s" data-strand="%s">'
        '%s'
        '<div class="wo-card-in">'
        '<h3 class="wo-name">%s</h3>'
        '<p class="wo-where">%s</p>'
        '<p class="wo-say">%s</p>'
        '</div></article>'
        % (" has-shot" if w.get("photo") else " no-shot", esc(w["strand"]),
           shot(w, "(max-width:700px) 92vw, (max-width:1100px) 46vw, 30vw"),
           esc(w["name"]), where(w, by_slug), esc(w["say"])))


def feature(w, by_slug, n):
    """A featured wonder, at the scale of the thing it is describing.

    The photograph is the card where there is one; where there is not, the
    strand's own ground carries it and the line is set larger to hold the same
    weight — which is why the pair still balances with a picture on one side.
    """
    d = load()
    strand = next((s for s in d["strands"] if s["id"] == w["strand"]), None)
    if w.get("photo"):
        return (
            '<article class="wo-feat has-shot" data-strand="%s">%s'
            '<div class="wo-feat-in">'
            '<span class="wo-feat-no">%s</span>'
            '<h3 class="wo-feat-name">%s</h3>'
            '<p class="wo-say">%s</p>'
            '<p class="wo-where">%s</p>'
            '</div></article>'
            % (esc(w["strand"]), shot(w, "(max-width:880px) 94vw, 47vw", "wo-feat-shot"),
               esc("0%d" % n), esc(w["name"]), esc(w["say"]), where(w, by_slug)))
    # NO PHOTOGRAPH IS NOT A HOLE TO BE PADDED. Set the same way as the card
    # beside it, the Serengeti came out an empty dark rectangle that read as a
    # picture that had failed to load. It is set as a statement instead: the
    # strand at the top, the name, and the line at display size carrying the
    # frame the way the photograph carries the other one. A pair of a
    # photograph and a sentence is a rhythm; a photograph and a blank is a bug.
    return (
        '<article class="wo-feat no-shot" data-strand="%s">'
        '<div class="wo-feat-in">'
        '<span class="wo-feat-no">%s<i>%s</i></span>'
        '<h3 class="wo-feat-name">%s</h3>'
        '<p class="wo-feat-line">%s</p>'
        '<p class="wo-where">%s</p>'
        '</div></article>'
        % (esc(w["strand"]), esc("0%d" % n),
           esc(strand["name"] if strand else ""),
           esc(w["name"]), esc(w["say"]), where(w, by_slug)))


def block_wonders(countries):
    """The homepage section, in four movements rather than two rows of tiles.

        intro      the argument, with one large photograph beside it
        featured   two wonders at the scale of the thing they describe
        gallery    every other wonder we hold a photograph of
        index      the rest, named
        close      what the collection is cut by, and the way in

    It was two big text cards over a row of four small text cards. That is a
    contact sheet, not a gallery: nothing on it was ever the thing itself, and a
    section arguing that some places do not need explaining had nothing on it
    but explanation. The hierarchy is now the argument — one photograph large
    enough to stop you, two wonders given room, then the breadth.

    THE PHOTOGRAPHS PICKED THEMSELVES. Four of the twenty-three have one on
    file, so the gallery is those four and the index is the other nineteen.
    Filling the grid from the general wildlife and desert frames would have been
    easy and would have put a photograph nobody can place under a named place —
    see $photos in tourism/wonders.json.
    """
    d = load()
    by_slug = {c.slug: c for c in countries}
    ws = d["wonders"]
    leads = [w for w in ws if w.get("lead")][:2]
    # THE GALLERY IS WHAT WE CAN SHOW; THE REST IS A LIST, NOT AN EMPTY BOX.
    # The first attempt filled six cards regardless and drew a tinted 4:3 plate
    # where a photograph was missing. On the page those did not read as an
    # editorial choice, they read as three broken images — which is the worst of
    # both, because it neither shows the place nor admits that it cannot.
    # A gallery holds pictures. Everything else is named, and being named beside
    # a picture of somewhere else is not a demotion, it is an index.
    rest = [w for w in ws if not w.get("lead")]
    shown = [w for w in rest if w.get("photo")]
    listed = [w for w in rest if not w.get("photo")]

    out = []

    intro = d.get("intro") or {}
    if intro.get("photo"):
        out.append(
            '<div class="wo-intro">'
            '<figure class="wo-intro-shot">'
            '<img src="%s" alt="%s" width="%d" height="%d" loading="lazy" '
            'decoding="async" sizes="(max-width:900px) 94vw, 54vw" '
            'data-provider="upload">'
            '</figure>'
            '<div class="wo-intro-say"><p>%s</p>'
            '<p class="wo-intro-n">%d places, across %d strands</p></div>'
            '</div>'
            % (esc(intro["photo"]), esc(intro.get("photo_alt") or ""),
               int(intro.get("photo_w") or 1440), int(intro.get("photo_h") or 958),
               esc(d["say"]), len(ws), len(d["strands"])))

    out.append('<div class="wo-lead">')
    out += [feature(w, by_slug, i + 1) for i, w in enumerate(leads)]
    out.append('</div>')

    if shown:
        out.append('<div class="wo-rest">')
        out += [card(w, by_slug) for w in shown]
        out.append('</div>')

    if listed:
        out.append('<div class="wo-more"><h3 class="wo-more-h">And %d more</h3>'
                   '<ul class="wo-more-list">' % len(listed))
        for w in listed:
            out.append('<li><b>%s</b><span>%s</span></li>'
                       % (esc(w["name"]), where(w, by_slug)))
        out.append('</ul></div>')

    # The strands, named under the cards rather than above them: they explain
    # how the collection is cut, which is a thing a reader wants after seeing
    # some of it and not before.
    out.append('<div class="wo-close">')
    if d.get("close"):
        out.append('<p class="wo-close-line">%s</p>' % esc(d["close"]))
    out.append('<ul class="wo-strands">')
    for s in d["strands"]:
        n = len([w for w in ws if w["strand"] == s["id"]])
        out.append('<li><b>%s</b><span>%s</span><i>%d</i></li>'
                   % (esc(s["name"]), esc(s["say"]), n))
    out.append('</ul>')
    out.append('</div>')
    return "\n".join(out)


def block_wonderslede(countries):
    """Stamp and headline only.

    The section lede used to be here AND in the intro block below, so `say`
    printed twice within one screen of itself — the same forty words, once at
    reading size under the headline and once at display size beside the
    photograph. It belongs with the photograph, which is the half of the section
    that needs a caption; the headline does not need explaining underneath it.
    """
    d = load()
    return ('<span class="wa-eyebrow">%s</span>\n'
            '        <h2>%s</h2>'
            % (esc(d["stamp"]), esc(d["line"])))


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
