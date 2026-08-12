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
"""

import html as html_mod
import json
import os

from .model import ROOT, load_operators, load_regions, load_strands

PAGE = os.path.join(ROOT, "journey.html")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")
LENSES = os.path.join(ROOT, "tourism", "lenses.json")
PLAN = os.path.join(ROOT, "tourism", "journeys.json")
ATLAS_DATA = os.path.join(ROOT, "data", "atlas")

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

    out = {
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
                              "categories": lens.get("categories") or []}

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


def render(countries, taxonomy):
    data = brief(countries, taxonomy)
    if not data["countries"]:
        raise IOError("no published countries — nothing to plan")
    return TEMPLATE % {
        "data": json.dumps(data, separators=(",", ":"), sort_keys=True),
        "wants": want_cards(data),
        "months": month_cells(),
        "pacing": pacing_cards(data),
        "party": party_chips(data),
        "style": style_chips(data),
        "carried": esc(data["carried"]),
        "n": len(data["countries"]),
    }


def run(countries, taxonomy, log=print):
    if not os.path.isdir(ATLAS_DATA):
        raise IOError("data/atlas is missing — run: build.py atlas")
    html = render(countries, taxonomy)
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
    <a href="/#destinations">Destinations</a>
    <a href="/compare">Compare</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/contact">Talk to us<i>&rarr;</i></a>
</header>

<main class="jn" id="jn" data-step="1">

  <!-- the questions ------------------------------------------------------- -->
  <form class="jn-ask" id="ask" novalidate>
    <div class="jn-progress" aria-hidden="true"><span data-on></span><span></span><span></span><span></span></div>

    <section class="jn-step" data-step="1" aria-labelledby="q1">
      <span class="af-stamp">Question one of four</span>
      <h1 class="jn-h1" id="q1">What kind of Africa<br>are you looking for?</h1>
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

  <!-- the composer -------------------------------------------------------- -->
  <section class="jn-compose" id="compose" hidden>
    <div class="jn-compose-head">
      <span class="af-stamp" id="jn-c-stamp"></span>
      <h1 class="jn-h1" id="jn-c-name"></h1>
      <p class="jn-lede" id="jn-c-line"></p>
      <div class="jn-carry" id="jn-c-why"></div>
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
          <a class="af-btn af-btn--solid" id="jn-begin" href="/contact">Begin this journey<i>&rarr;</i></a>
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

  <noscript>
    <p class="jn-nojs">This page builds a journey as you answer, which needs
      JavaScript. Without it, the same countries and the same twenty-six places
      each are all readable in <a href="/atlas">the atlas</a> and on every
      destination page, and <a href="/contact">a person</a> will do the rest.</p>
  </noscript>
</main>

<script type="application/json" id="jn-data">%(data)s</script>
<script src="/scripts/window.js" defer></script>
<script src="/scripts/journey-engine.js" defer></script>
<script src="/scripts/journey.js" defer></script>
</body>
</html>
"""
