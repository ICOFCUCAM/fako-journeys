"""The journey engine: /journey, built from the dataset.

    python3 tools/tourism/build.py journey

The atlas answers "where is this". This answers "what am I looking for" — the
question a traveller actually starts with. Four short questions, a quiet moment,
and then one country, named, with a journey already shaped inside it.

    intention -> experience -> country -> stages -> a journey with a name

It reuses rather than duplicates. The places a journey is assembled from are the
same data/atlas/<slug>.json payloads the atlas fetches, so a country written up
once appears in both. The silhouettes are tourism/shapes.json, the seasons and
the operators are the country files, the six lenses are lenses.json, and the
planning vocabulary and the scoring weights are journeys.json — out of code, so
the reasoning can be read by somebody who does not read JavaScript.

The one number this page computes that the dataset does not hold is `lensCounts`
— how many of a country's twenty-six write-ups fall under each lens. It is a
count of what is there, computed here so the browser can rank twenty-two
countries without fetching twenty-two files.

Nothing here books anything, quotes a price, or claims availability. The engine
proposes a shape and hands it to a person who lives there.

THE CONTINENT IS ON THE PAGE, AND IT IS IN THE DOCUMENT.

    question -> geographic response -> question -> geographic response
             -> the finished journey, drawn

Each of those verbs is wired. `continent()` below writes the fifty-two country
paths, two island marks and one disputed territory out of tourism/map.json —
the same projection and the same 1000x1060 viewBox the homepage hero and the
crossing pages draw — into the document itself rather than into a script.
Answering a question colours them by how well each answers it; choosing one
flies the viewBox to it; composing a journey draws the route across it.

The honest limit, recorded so it is not rediscovered as a bug: PLACES HAVE NO
COORDINATES. data/atlas/<slug>.json gives each place a group, a lens set and a
write-up and no position, so a node cannot be put on the Mara without inventing
where the Mara is. Thirteen places in tourism/atlas-detail.json have a real
position and every country has a centroid; that is what the route is drawn
from, and the map's own caption says which of the two each node is rather than
letting a reader assume the stronger one. Place coordinates would upgrade the
drawn journey from a shape to an itinerary, and nothing else here needs them.

"""

import html as html_mod
import json
import os

from . import company, plate, rates
from .model import ROOT, load_operators, load_regions, load_strands

PAGE = os.path.join(ROOT, "journey.html")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")
LENSES = os.path.join(ROOT, "tourism", "lenses.json")
PLAN = os.path.join(ROOT, "tourism", "journeys.json")
ATLAS_DATA = os.path.join(ROOT, "data", "atlas")
MAP = os.path.join(ROOT, "tourism", "map.json")
DETAIL = os.path.join(ROOT, "tourism", "atlas-detail.json")

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")
MON3 = tuple(m[:3].upper() for m in MONTHS)


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def read(path, fallback):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def clean(raw):
    return dict((k, v) for k, v in raw.items() if not k.startswith("$"))


def brief(countries, taxonomy):
    """Everything the engine needs to rank twenty-two countries, inlined.

    Ranking has to be instant — it happens between one keystroke and the next —
    so nothing here may require a request. The places themselves are not here;
    they are fetched when a country is chosen, which is the only moment they
    are needed.
    """
    lenses = clean(read(LENSES, {}))
    plan = clean(read(PLAN, {}))
    strands = load_strands()
    regions = load_regions()
    ops = load_operators()
    shapes = read(SHAPES, {})
    live = [c for c in countries if c.published]

    region_of = {}
    region_name = {}
    for key, reg in regions.items():
        region_name[key] = reg.name
        for c in live:
            if c.region in reg.includes:
                region_of[c.slug] = key

    # Which of the twenty-seven categories belongs to which lens, inverted once.
    lens_of = {}
    for key, lens in lenses.items():
        for cat in lens.get("categories") or []:
            lens_of.setdefault(cat, []).append(key)

    # The thirteen places on this site with a real position, in the same
    # viewBox units the continent is drawn in. Nothing else has one: a place
    # page carries a group, a lens set and a write-up, and no coordinates. So
    # a journey can put a node on Nairobi and cannot put one on the Mara, and
    # the map says which of those it is doing rather than guessing.
    det = read(DETAIL, {})
    cities = []
    for c in (det.get("cities") or []):
        x, y = c.get("x"), c.get("y")
        if x is None or y is None:
            continue
        cities.append({"name": c["name"], "x": float(x), "y": float(y)})

    out = {
        "cities": cities,
        "months": list(MONTHS),
        "weights": plan.get("weights") or {},
        "pacing": plan.get("pacing") or [],
        "party": plan.get("party") or [],
        "style": plan.get("style") or [],
        "carried": plan.get("carried") or "",
        "regions": [{"key": k, "name": r.name, "line": r.line}
                    for k, r in regions.items()],
        "lenses": {}, "countries": {},
    }
    for key, lens in lenses.items():
        out["lenses"][key] = {"title": lens.get("title") or key,
                              "line": lens.get("line") or "",
                              "categories": lens.get("categories") or [],
                              # What somebody might type for this. The parser
                              # matches against these and nothing else.
                              "words": lens.get("words") or []}

    for c in live:
        op = ops.get(c.operator_key)
        counts = {}
        for e in c.entries:
            if e.category == "hero" or not e.caption:
                continue
            for k in lens_of.get(e.category, []):
                counts[k] = counts.get(k, 0) + 1
        shape = shapes.get(c.slug) or {}
        # Who lives there, in that country's own words. One line, from the
        # write-up that already exists — so the moment a country arrives it
        # arrives with people in it rather than as an outline and a season.
        meets = []
        for key, st in strands.items():
            if key not in ("people", "culture"):
                continue
            for cat in st.get("categories") or []:
                e = c.entry(cat)
                if e and e.caption:
                    meets.append({"strand": key, "title": e.caption})
                    break
        out["countries"][c.slug] = {
            "name": c.name, "adjective": c.adjective,
            "region": c.region, "regionKey": region_of.get(c.slug, ""),
            "tagline": c.tagline, "summary": c.summary,
            "months": c.months, "when": c.when, "url": c.url,
            "calls": c.calls, "lensCounts": counts, "meets": meets,
            "window": c.window, "windowAlt": c.window_alt,
            "shape": {"w": shape.get("w"), "h": shape.get("h"), "d": shape.get("d")}
                     if shape.get("d") else None,
            "operator": ({"name": op.name, "base": op.base, "since": op.since,
                          "line": op.line, "url": op.url} if op else None),
        }
    return out


# ---- the question cards ----------------------------------------------------------


def want_cards(data):
    """The first question, written into the page rather than drawn by script.

    Six choices, each with the sentence that says what it means here. They are
    checkboxes underneath — one control, one label, no invented widget — so the
    keyboard, the screen reader and the browser's own form behaviour all work
    before a line of script runs.
    """
    order = sorted(data["lenses"].items(),
                   key=lambda kv: (-len([1 for c in data["countries"].values()
                                         if kv[0] in c["calls"]]), kv[1]["title"]))
    out = []
    for i, (key, lens) in enumerate(order):
        n = len([1 for c in data["countries"].values() if key in c["calls"]])
        out.append(
            '        <label class="jn-card">\n'
            '          <input type="checkbox" name="want" value="%s">\n'
            '          <span class="jn-card-in"><b>%s</b>'
            '<span class="jn-card-line">%s</span>'
            '<span class="jn-card-n">%d %s</span></span>\n'
            '        </label>'
            % (esc(key), esc(lens["title"]), esc(lens["line"]), n,
               "country" if n == 1 else "countries"))
    return "\n".join(out)


def month_cells():
    return "\n            ".join(
        '<label class="jn-mon"><input type="radio" name="month" value="%d">'
        '<span>%s</span></label>' % (i + 1, MON3[i]) for i in range(12))


def pacing_cards(data):
    return "\n".join(
        '        <label class="jn-card jn-card--row">\n'
        '          <input type="radio" name="pacing" value="%s">\n'
        '          <span class="jn-card-in"><b>%s</b>'
        '<span class="jn-card-line">%s</span>'
        '<span class="jn-card-n">%s</span></span>\n'
        '        </label>' % (esc(p["key"]), esc(p["label"]), esc(p["line"]),
                              esc(p["short"]))
        for p in data["pacing"])


def party_chips(data):
    return "\n            ".join(
        '<label class="jn-chip"><input type="radio" name="party" value="%s">'
        '<span>%s</span></label>' % (esc(p["key"]), esc(p["label"]))
        for p in data["party"])


def style_chips(data):
    return "\n            ".join(
        '<label class="jn-chip"><input type="checkbox" name="style" value="%s">'
        '<span>%s</span></label>' % (esc(s["key"]), esc(s["label"]))
        for s in data["style"])


def continent():
    """The continent, drawn into the document rather than into a script.

    This is the thing this page was specified to have and did not: every
    country of Africa, on the page, from the first question, so that an answer
    has somewhere to land. The projection is not new — `tourism/map.json` holds
    the same fifty-two paths, two island marks and one disputed territory the
    homepage hero draws, in the same 1000x1060 viewBox — so nothing here
    invents geometry. It reads a file three other surfaces already read.

    Three decisions worth stating, because each was the alternative's opposite.

    IT IS SERVER-RENDERED, NOT DRAWN BY THE SCRIPT. A map assembled in the
    browser is a map that does not exist for anything that does not run
    JavaScript, and this page was already the thinnest on the site by that
    measure — 270 words, against 4,174 on the homepage. Fifty-four country
    names and taglines in the document is the same fix as the map.

    EVERY COUNTRY IS A LINK. Not a <path> with a click handler: an <a> to that
    country's own page, which is where it goes with scripting off and what a
    keyboard can reach without a roving tabindex. The script intercepts the
    click and picks the country instead; the link is what it degrades to.

    THE HIT AREA IS NOT THE OUTLINE. The Gambia is a river and Comoros is three
    dots, and neither is a target a thumb can find. Each country carries a
    transparent disc at its own centroid, sized for a finger, painted under
    nothing and hit before the outline. The outline is the drawing; the disc is
    the control.
    """
    m = read(MAP, {})
    live = m.get("live") or []
    if len(live) < 40:
        raise IOError("tourism/map.json holds %d countries — run: build.py map"
                      % len(live))
    view = m.get("view") or [0, 0, 1000.0, 1060.0]

    def at(row):
        raw = row.get("at")
        if isinstance(raw, str):
            raw = json.loads(raw)
        return [float(raw[0]), float(raw[1])] if raw else None

    rest = "".join(
        '<path d="%s"><title>%s</title></path>' % (esc(r["d"]), esc(r.get("n") or ""))
        for r in (m.get("rest") or []))

    shapes, discs = [], []
    for row in live:
        p = at(row)
        title = row["name"] + (" — " + row["tag"] if row.get("tag") else "")
        shapes.append(
            '<a class="jn-map-c" href="%s" data-slug="%s"%s>'
            '<title>%s</title><path d="%s"/></a>'
            % (esc(row.get("href") or "/" + row["slug"]), esc(row["slug"]),
               ' data-at="%.1f %.1f"' % (p[0], p[1]) if p else "",
               esc(title), esc(row["d"])))
        if p:
            discs.append('<circle class="jn-map-hit" data-slug="%s" cx="%.1f" '
                         'cy="%.1f" r="17"/>' % (esc(row["slug"]), p[0], p[1]))

    marks = []
    for row in (m.get("marks") or []):
        p = at(row)
        if not p:
            continue
        title = row["name"] + (" — " + row["tag"] if row.get("tag") else "")
        marks.append(
            '<a class="jn-map-c is-isle" href="%s" data-slug="%s" '
            'data-at="%.1f %.1f"><title>%s</title>'
            '<circle cx="%.1f" cy="%.1f" r="%s"/></a>'
            % (esc(row.get("href") or "/" + row["slug"]), esc(row["slug"]),
               p[0], p[1], esc(title), p[0], p[1], esc(row.get("r") or 9)))
        discs.append('<circle class="jn-map-hit" data-slug="%s" cx="%.1f" '
                     'cy="%.1f" r="17"/>' % (esc(row["slug"]), p[0], p[1]))

    return """
      <figure class="jn-atlas-fig">
        <svg class="jn-map" id="jn-map" viewBox="%(view)s"
             preserveAspectRatio="xMidYMid meet"
             aria-labelledby="jn-map-t jn-map-d">
          <title id="jn-map-t">Africa, with every country this site writes up</title>
          <desc id="jn-map-d">An outline map of the continent. Every country is
            a link to its own pages, and every country is also a button in the
            list of all fifty-four below, which is the easier target on a small
            screen. Answering the questions colours them by how well each one
            answers what you asked for.</desc>
          <g class="jn-map-rest" aria-hidden="true">%(rest)s</g>
          <g class="jn-map-live">%(shapes)s</g>
          <g class="jn-map-isles">%(marks)s</g>
          <g class="jn-map-route" id="jn-map-route" aria-hidden="true"></g>
          <g class="jn-map-hits" aria-hidden="true">%(discs)s</g>
        </svg>
        <figcaption class="jn-map-say" id="jn-map-say">Fifty-four countries.
          Answer a question and watch them answer back.</figcaption>
      </figure>""" % {
        "view": "%g %g %g %g" % tuple(view),
        "rest": rest,
        "shapes": "".join(shapes),
        "marks": "".join(marks),
        "discs": "".join(discs),
    }


def render(countries, taxonomy):
    data = brief(countries, taxonomy)
    money = rates.load()
    co = company.load()
    if not data["countries"]:
        raise IOError("no published countries — nothing to plan")
    return TEMPLATE % {
        "events": plate.events_block(),
        "explore": plate.explore_block(),
        "foot": plate.colophon_foot("/journey"),
        "og": plate.open_graph('Build a journey — Afrinkong', 'Four questions, then one country, a journey shaped inside it, and the company that would run it.', '/journey'),
        "data": json.dumps(data, separators=(",", ":"), sort_keys=True),
        "wants": want_cards(data),
        "months": month_cells(),
        "pacing": pacing_cards(data),
        "party": party_chips(data),
        "style": style_chips(data),
        "carried": esc(data["carried"]),
        "n": len(data["countries"]),
        "ground": rates.block_ground(money),
        "notincluded": rates.block_notincluded(money),
        "whopays": company.block_whopays(co),
        "continent": continent(),
    }


def run(countries, taxonomy, log=print):
    if not os.path.isdir(ATLAS_DATA):
        raise IOError("data/atlas is missing — run: build.py atlas")
    html = render(countries, taxonomy)
    stray = rates.drift(html, rates.load())
    if stray:
        raise ValueError(
            "the tunnel prints %s, which tourism/rates.json does not price — a "
            "figure in the copy has drifted from the cards under it."
            % ", ".join(rates.money(v) for v in stray))
    with open(PAGE, "w") as fh:
        fh.write(html)
    log("journey: %s (%.1f KB), %d countries rankable without a request"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           len([c for c in countries if c.published])))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Build a journey &mdash; Afrinkong</title>
<meta name="description" content="Tell us what kind of Africa you are looking for. Four questions, then one country, a journey shaped inside it, and the company that would run it.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
</head>
<body>
<a class="af-skip" href="#ask">Skip to the questions</a>
<header class="jn-mast">
  <a class="jn-mark" href="/"><i>Afrinkong</i><b>Build a journey</b></a>
  <nav class="jn-routes" aria-label="Primary">
    <a href="/atlas">The Atlas</a>
    <a href="/meet">Meet Africa</a>
    <a href="/places">Every place</a>
    <a href="/stories">Stories</a>
    <a href="/how-it-works">How it works</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/enquire">Talk to us<i>&rarr;</i></a>
</header>

<main class="jn" id="jn" data-step="1">

  <!-- The continent, from the first question rather than after the last one.
       It is the page's subject and it was not on the page: a visitor answering
       four questions about where to go had nothing in front of them that was
       anywhere. It stays put through the questions, the answer and the
       composing, and every stage of those three writes to it.

       It is first in the document as well as on the screen, which it can afford
       to be because the script gives it ONE tab stop: the fifty-four countries
       are moved out of the tab order and navigated with the arrow keys, the way
       a grid is. With the script off they are fifty-four ordinary links, which
       is what they are then. -->
  <aside class="jn-atlas" id="jn-atlas" aria-labelledby="jn-atlas-h">
    <div class="jn-atlas-in">
      <h2 class="af-stamp" id="jn-atlas-h">The continent</h2>
      %(continent)s
      <ul class="jn-map-key" id="jn-map-key" hidden>
        <li data-match="leads">Leads on what you asked</li>
        <li data-match="region">Its region does</li>
        <li data-match="open">Written up here too</li>
      </ul>
    </div>
  </aside>



  <!-- the questions ------------------------------------------------------- -->
  <form class="jn-ask" id="ask" novalidate>
    <div class="jn-progress" aria-hidden="true"><span data-on></span><span></span><span></span><span></span></div>

    <section class="jn-step" data-step="1" aria-labelledby="q1">
      <span class="af-stamp">Question one of four</span>
      <h1 class="jn-h1" id="q1">What kind of Africa<br>are you looking for?</h1>

      <!-- A sentence, for anybody who would rather write one than press six
           things. It is a parser and not a model: it matches months, countries,
           a length and the words recorded for each lens, and it fills the
           controls below rather than acting on its own. Every control it
           touches stays editable, and it says what it took. -->
      <div class="jn-say">
        <label for="jn-said-it">Or say it in a sentence</label>
        <div class="jn-say-row">
          <input id="jn-said-it" type="text" autocomplete="off"
                 placeholder="Twelve days in September, wildlife and mountains">
          <button class="af-btn af-btn--quiet" type="button" data-read>Read it</button>
        </div>
        <p class="jn-say-got" id="jn-say-got" role="status"></p>
      </div>

      <p class="jn-lede">Choose as many as are true. Every country here declares
        what it leads on, in its own words &mdash; this asks against that, so a
        match means something. Or say nothing and let us open the atlas for you.</p>
      <div class="jn-cards" role="group" aria-labelledby="q1">
%(wants)s
      </div>
      <div class="jn-acts">
        <button class="af-btn af-btn--solid" type="button" data-next>Next<i>&rarr;</i></button>
        <button class="af-btn af-btn--quiet" type="button" data-open>I don't know yet<i>&rarr;</i></button>
      </div>
    </section>

    <section class="jn-step" data-step="2" aria-labelledby="q2" hidden>
      <span class="af-stamp">Question two of four</span>
      <h1 class="jn-h1" id="q2">When?</h1>
      <p class="jn-lede">Every country carries the months it is actually good in.
        Pick one and the ones at their best then come first &mdash; the others
        are still here, and will say so.</p>
      <div class="jn-months" role="group" aria-labelledby="q2">
            %(months)s
      </div>
      <label class="jn-chip jn-chip--wide"><input type="radio" name="month" value="" checked><span>I'm flexible</span></label>
      <div class="jn-acts">
        <button class="af-btn af-btn--solid" type="button" data-next>Next<i>&rarr;</i></button>
        <button class="af-btn af-btn--quiet" type="button" data-back>Back</button>
      </div>
    </section>

    <section class="jn-step" data-step="3" aria-labelledby="q3" hidden>
      <span class="af-stamp">Question three of four</span>
      <h1 class="jn-h1" id="q3">How long<br>have you got?</h1>
      <p class="jn-lede">This decides the shape of the journey rather than the
        place: how many stages it is worth splitting into. It is a planning
        convention, not a claim about the roads.</p>
      <div class="jn-cards jn-cards--rows" role="group" aria-labelledby="q3">
%(pacing)s
      </div>
      <div class="jn-acts">
        <button class="af-btn af-btn--solid" type="button" data-next>Next<i>&rarr;</i></button>
        <button class="af-btn af-btn--quiet" type="button" data-back>Back</button>
      </div>
    </section>

    <section class="jn-step" data-step="4" aria-labelledby="q4" hidden>
      <span class="af-stamp">Question four of four</span>
      <h1 class="jn-h1" id="q4">Who is coming,<br>and how do you travel?</h1>
      <p class="jn-lede">%(carried)s</p>
      <div class="jn-chips" role="group" aria-label="Who is coming">
            %(party)s
      </div>
      <div class="jn-chips jn-chips--style" role="group" aria-label="How you travel">
            %(style)s
      </div>
      <div class="jn-acts">
        <button class="af-btn af-btn--solid" type="button" data-reveal>Show me<i>&rarr;</i></button>
        <button class="af-btn af-btn--quiet" type="button" data-back>Back</button>
      </div>
    </section>
  </form>
  <!-- The continent, from the first question rather than after the last one.
       It is the page's subject and it was not on the page: a visitor answering
       four questions about where to go had nothing in front of them that was
       anywhere. It stays put through the questions, the answer and the
       composing, and every stage of those three writes to it. -->


  <!-- the reveal ---------------------------------------------------------- -->
  <section class="jn-reveal" id="reveal" hidden aria-live="polite">
    <div class="jn-reveal-in">
      <span class="af-stamp jn-reveal-stamp">Your Africa</span>
      <div class="jn-shape" id="jn-shape"></div>
      <h1 class="jn-h1 jn-reveal-name" id="jn-name"></h1>
      <p class="jn-reveal-tag" id="jn-tag"></p>
      <div class="jn-why" id="jn-why"></div>
      <div class="jn-acts">
        <button class="af-btn af-btn--solid" type="button" data-compose>Build this journey<i>&rarr;</i></button>
        <button class="af-btn af-btn--quiet" type="button" data-others>The other two</button>
      </div>
      <div class="jn-alts" id="jn-alts"></div>
      <button class="jn-restart" type="button" data-restart>Ask me again</button>
    </div>
  </section>

  <!-- the whole continent, coloured rather than filtered --------------------
         Afrinkong recommends; the traveller decides. A lens does not remove a
         country from the page, it changes how strongly the page answers with
         it, and every one of the fifty-four stays here and stays clickable.
       Somebody who arrived knowing they want Ghana finds Ghana.

       It is its own section and not a child of .jn-reveal, which is a
       full-height flex row: dropped in there the grid became the reveal's
       second column and printed fifty-four countries one per line down a
       half-width gutter. -->
  <section class="jn-field" id="jn-field" hidden>
    <div class="jn-field-in">
      <div class="jn-field-head">
        <span class="af-stamp">The continent</span>
        <h2 class="jn-field-h">All fifty-four, <em>and how each one answers</em>.</h2>
        <p class="jn-field-say" id="jn-field-say"></p>
      </div>
      <div class="jn-field-key" aria-hidden="true">
        <span data-match="leads">Leads on what you asked</span>
        <span data-match="region">Its region does</span>
        <span data-match="open">Written up here too</span>
      </div>
      <div class="jn-field-grid" id="jn-field-grid" role="group"
           aria-label="Every country. Choose any one."></div>
      <p class="jn-field-fine">We can recommend a direction. You choose the destination.</p>
    </div>
  </section>

  <!-- the composer -------------------------------------------------------- -->
  <section class="jn-compose" id="compose" hidden>
    <div class="jn-compose-head">
      <span class="af-stamp" id="jn-c-stamp"></span>
      <h1 class="jn-h1" id="jn-c-name"></h1>
      <p class="jn-lede" id="jn-c-line"></p>
      <div class="jn-carry" id="jn-c-why"></div>
      <!-- Change one thing rather than start again. Each control edits the
           brief in place and the journey re-shapes around it. -->
      <div class="jn-tweak" id="jn-tweak" aria-label="Change one thing"></div>
    </div>
    <div class="jn-compose-grid">
      <div class="jn-line-col">
        <h2 class="jn-h2">The journey</h2>
        <ol class="jn-line" id="jn-line"></ol>
        <p class="jn-caveat" id="jn-caveat"></p>
        <h2 class="jn-h2">What it is made of</h2>
        <div class="jn-dna" id="jn-dna"></div>
        <div class="jn-who" id="jn-who"></div>
        <div class="jn-acts jn-acts--end">
          <button class="af-btn af-btn--solid" id="jn-begin" type="button" data-ground>Price the ground<i>&rarr;</i></button>
          <a class="af-btn af-btn--quiet" id="jn-meet" href="/meet">Meet the country</a>
          <button class="af-btn af-btn--quiet" type="button" data-save>Save this journey</button>
          <button class="af-btn af-btn--quiet" type="button" data-share>Copy the link</button>
        </div>
        <p class="jn-said" id="jn-said" role="status"></p>
      </div>
      <aside class="jn-pick-col">
        <h2 class="jn-h2">Add a stage</h2>
        <p class="jn-note" id="jn-pick-note"></p>
        <ul class="jn-picks" id="jn-picks"></ul>
      </aside>
    </div>
  </section>

  <!-- the ground --------------------------------------------------------- -->
  <!-- The tunnel used to end at the composer and hand the traveller to
       /contact with a shape and no figure. This is the last question: what the
       ground costs, asked only once the journey has a name, and carrying the
       days already answered rather than asking for them twice. -->
  <section class="jn-ground" id="ground" hidden aria-labelledby="qg">
    <div class="jn-ground-in">
      <span class="af-stamp">The ground</span>
      <h1 class="jn-h1" id="qg">Your flight gets you to Africa.<br>We get you through it.</h1>
      <p class="jn-lede">From the moment you land, the road is ours: a vehicle,
        a driver who stays with your journey, the movement between destinations,
        and somebody coordinating all of it while you are here. Priced by the
        vehicle and by the day, so four of you pay what two of you would. You
        bring the passport, the visa, the ticket and the insurance.</p>
%(ground)s
%(notincluded)s
%(whopays)s
      <div class="jn-acts jn-acts--end">
        <a class="af-btn af-btn--solid" id="jn-go" href="/enquire">Begin this journey<i>&rarr;</i></a>
        <!-- THE OTHER ANSWER TO THE SAME QUESTION.
             A traveller who has got this far has composed a real journey and
             seen a real figure. Some of them are ready and press the button
             to its left; some of them are not, and until now the tunnel had
             nothing to say to those people except a price they could not meet
             yet. This is the second door, and it carries the journey they just
             built rather than sending them back to an empty page.
             Quiet weight rather than solid, because the traveller who can go
             now should go now. -->
        <a class="af-btn af-btn--quiet" id="jn-toward" href="/journey-fund">Build toward this journey<i>&rarr;</i></a>
        <button class="af-btn af-btn--quiet" type="button" data-back-compose>Back to the journey</button>
      </div>
      <p class="jn-g-nothing">Nothing is charged here. This sends your journey to
        us as a sentence you can edit first, and we confirm your requirements
        before we confirm the journey.</p>
    </div>
  </section>

  <noscript>
    <p class="jn-nojs">This page builds a journey as you answer, which needs
      JavaScript. Without it, the same countries and the same twenty-six places
      each are all readable in <a href="/atlas">the atlas</a> and on every
      destination page, and <a href="/enquire">a person</a> will do the rest.</p>
  </noscript>
</main>
%(foot)s

<script type="application/json" id="jn-data">%(data)s</script>
%(events)s
%(explore)s
<script src="/scripts/window.js" defer></script>
<script src="/scripts/journey-engine.js" defer></script>
<script src="/scripts/journey.js" defer></script>
</body>
</html>
"""
