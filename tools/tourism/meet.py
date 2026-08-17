"""The human layer: /meet, built from the dataset.

    python3 tools/tourism/build.py meet

Every country in this set was written up through the same twenty-seven
categories. Twelve of them are about people — who lives here, what is cooked,
what is made by hand, what is kept, what a city is like on a Tuesday — and until
now they sat in a grid of twenty-seven tiles where the twelve looked exactly like
the fifteen about scenery.

This page is the argument that they are not the same thing. It has two axes:

    one country, seven doors     — Cameroon: people, culture, food, craft,
                                   cities, heritage, responsibility
    one door, twenty-two countries — food, asked of the whole continent at once

The second is the point. A tourism site can always find one photograph of one
market. What it cannot do is ask the same question of twenty-two countries and
print twenty-two different answers, each naming a particular people, a
particular dish, a particular workshop in a particular town. The uniform
taxonomy makes that possible and nothing else on the site uses it that way.

Nothing here is invented. Every line behind every door is a caption and a
description already written for that country. Guides come from people.json and
operator notes from voices.json, both of which are empty and stay empty until
somebody has asked a real person — the components render nothing rather than
render a plausible stranger.

What ships:

    meet.html        the page and the spine
    data/meet.json   seven strands x twenty-two countries, fetched once
"""

import html as html_mod
import json
import os

from . import plate
from .model import (ROOT, load_operators, load_people, load_regions,
                    load_strands, load_voices)

PAGE = os.path.join(ROOT, "meet.html")
DATA = os.path.join(ROOT, "data", "meet.json")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


# ---- the payload -----------------------------------------------------------------


def strands_payload(countries, taxonomy):
    """Seven doors x twenty-two countries, in one file.

    It is the same source as data/atlas/<slug>.json, cut the other way. The
    atlas needs one country at a time and fetches one file; this page needs one
    question across the whole continent and would otherwise fetch twenty-two.
    Both are generated from tourism/countries/*.json in the same build, so
    neither can drift from the other.
    """
    strands = load_strands()
    ops = load_operators()
    titles = {c["id"]: c["title"] for c in taxonomy.categories}
    live = [c for c in countries if c.published]

    out = {"strands": [], "countries": {}, "answers": {}}
    for key, s in strands.items():
        out["strands"].append({"key": key, "title": s.get("title") or key,
                               "asks": s.get("asks") or "",
                               "line": s.get("line") or "",
                               "categories": s.get("categories") or []})

    for c in live:
        op = ops.get(c.operator_key)
        out["countries"][c.slug] = {
            "name": c.name, "adjective": c.adjective, "region": c.region,
            "tagline": c.tagline, "url": c.url,
            "window": c.window, "windowAlt": c.window_alt,
            "operator": ({"key": c.operator_key, "name": op.name, "base": op.base,
                          "since": op.since, "line": op.line, "url": op.url}
                         if op else None),
        }

    for key, s in strands.items():
        rows = {}
        for c in live:
            answers = []
            for cat in s.get("categories") or []:
                e = c.entry(cat)
                if not e or not e.caption:
                    continue
                img = e.image or {}
                answers.append({
                    "id": cat, "group": titles.get(cat, cat),
                    "title": e.caption, "text": e.description or "",
                    "image": ({"url": img.get("imageUrl"),
                               "alt": img.get("alt") or e.description,
                               "credit": img.get("photographer"),
                               "provider": img.get("provider")}
                              if img.get("imageUrl") else None),
                })
            if answers:
                rows[c.slug] = answers
        out["answers"][key] = rows
    return out


def people_payload():
    """Real people, if any have been recorded. Usually none, deliberately."""
    people = load_people()
    ops = load_operators()
    out = []
    for key, p in people.items():
        op = ops.get(p.operator_key)
        out.append({
            "key": key, "name": p.name, "role": p.role, "country": p.country,
            "base": p.base, "languages": p.languages, "since": p.since,
            "speciality": p.speciality, "line": p.line,
            "photo": p.photo, "photoAlt": p.photo_alt,
            "operator": ({"name": op.name, "url": op.url} if op else None),
        })
    return out


def voices_payload():
    """What operators have actually said. Empty until somebody says something."""
    ops = load_operators()
    out = []
    for v in load_voices():
        op = ops.get(v.operator_key)
        if not op:
            continue
        out.append({"country": v.country, "asked": v.asked, "said": v.said,
                    "by": v.by, "operator": {"name": op.name, "base": op.base,
                                             "url": op.url}})
    return out


# ---- the page --------------------------------------------------------------------


def door_list(data):
    """The seven doors, written into the page so they exist without script."""
    out = []
    for i, s in enumerate(data["strands"]):
        n = len(data["answers"].get(s["key"]) or {})
        out.append(
            '        <li>\n'
            '          <button class="mt-door" type="button" data-strand="%s" '
            'aria-pressed="%s">\n'
            '            <span class="mt-door-no">%02d</span>\n'
            '            <span class="mt-door-body"><b>%s</b>'
            '<span class="mt-door-asks">%s</span></span>\n'
            '            <span class="mt-door-n">%d</span>\n'
            '          </button>\n        </li>'
            % (esc(s["key"]), "true" if i == 0 else "false", i + 1,
               esc(s["title"]), esc(s["asks"]), n))
    return "\n".join(out)


def country_strip(data):
    """Every country, in the order the continent is read, as real links.

    With no script these are links to the country's own page, so the page is a
    working index of twenty-two countries before anything runs.
    """
    regions = load_regions()
    order = {}
    for i, (key, reg) in enumerate(regions.items()):
        for inc in reg.includes:
            order[inc] = i
    rows = sorted(data["countries"].items(),
                  key=lambda kv: (order.get(kv[1]["region"], 99), kv[1]["name"]))
    return "\n            ".join(
        '<a class="mt-flag" href="%s" data-country="%s">%s</a>'
        % (esc(c["url"]), esc(slug), esc(c["name"])) for slug, c in rows)


def opening(data):
    """The first thing behind the first door, so the page is never blank.

    Rendered from the payload at build time rather than drawn by script: the
    continent-wide answer to the first question is the whole argument of the
    page, and it should be readable with JavaScript switched off.
    """
    first = data["strands"][0]
    rows = data["answers"].get(first["key"]) or {}
    out = []
    regions = load_regions()
    order = {}
    for i, (key, reg) in enumerate(regions.items()):
        for inc in reg.includes:
            order[inc] = i
    for slug in sorted(rows, key=lambda s: (order.get(data["countries"][s]["region"], 99),
                                            data["countries"][s]["name"])):
        c = data["countries"][slug]
        a = rows[slug][0]
        out.append(
            '      <article class="mt-answer">\n'
            '        <p class="mt-answer-where"><a href="%s">%s</a>'
            '<span>%s</span></p>\n'
            '        <h3 class="mt-answer-title">%s</h3>\n'
            '        <p class="mt-answer-text">%s</p>\n'
            '      </article>'
            % (esc(c["url"]), esc(c["name"]), esc(c["region"]),
               esc(a["title"]), esc(a["text"])))
    return "\n".join(out)


def render(countries, taxonomy):
    data = strands_payload(countries, taxonomy)
    if not data["countries"]:
        raise IOError("no published countries — nothing to meet")
    people = people_payload()
    return TEMPLATE % {
        "events": plate.events_block(),
        "explore": plate.explore_block(),
        "foot": plate.colophon_foot("/meet"),
        "og": plate.open_graph('Meet Africa — Afrinkong', 'Seven questions, asked of twenty-two countries. The same question changes its answer at every border.', '/meet'),
        "doors": door_list(data),
        "strip": country_strip(data),
        "opening": opening(data),
        "first": esc(data["strands"][0]["title"]),
        "firstAsks": esc(data["strands"][0]["asks"]),
        "firstLine": esc(data["strands"][0]["line"]),
        "n": len(data["countries"]),
        "doorCount": len(data["strands"]),
        "answers": sum(len(v) for v in data["answers"].values()),
        # People are inlined because there are none: an empty array is twelve
        # bytes and a request for twelve bytes is a request too many. The day
        # somebody is added this stays true until the file is large enough to
        # be worth splitting, which is a long way off.
        "people": json.dumps(people, separators=(",", ":")),
        "voices": json.dumps(voices_payload(), separators=(",", ":")),
    }


def run(countries, taxonomy, log=print):
    data = strands_payload(countries, taxonomy)
    folder = os.path.dirname(DATA)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(DATA, "w") as fh:
        json.dump(data, fh, separators=(",", ":"), sort_keys=True)
        fh.write("\n")
    html = render(countries, taxonomy)
    with open(PAGE, "w") as fh:
        fh.write(html)
    answers = sum(len(v) for v in data["answers"].values())
    people = len(load_people())
    log("meet: %s (%.1f KB) + %s (%.1f KB), %d doors x %d countries = %d answers"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           os.path.relpath(DATA, ROOT), os.path.getsize(DATA) / 1024.0,
           len(data["strands"]), len(data["countries"]), answers))
    log("      %d guide profile(s), %d operator note(s) — both empty until a real "
        "person has been asked" % (people, len(load_voices())))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meet Africa &mdash; Afrinkong</title>
<meta name="description" content="Seven questions, asked of twenty-two countries. Who lives here, what is cooked, what is made by hand, what is kept — and the same question changes its answer at every border.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/meet.css">
</head>
<body>
<a class="af-skip" href="#doors">Skip to the questions</a>
<header class="mt-mast">
  <a class="mt-mark" href="/"><i>Afrinkong</i><b>Meet Africa</b></a>
  <nav class="mt-routes" aria-label="Primary">
    <a href="/atlas">The Atlas</a>
    <a href="/journey">Build a journey</a>
    <a href="/places">Every place</a>
    <a href="/stories">Stories</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/enquire">Talk to us<i>&rarr;</i></a>
</header>

<main class="mt" id="mt" data-mode="strand">

  <section class="mt-open">
    <span class="af-stamp">The human layer</span>
    <h1 class="mt-h1">Africa is not a backdrop.</h1>
    <p class="mt-lede">Every country here was written up through the same
      twenty-seven headings, and twelve of them are about people. So the same
      question can be put to all %(n)d at once &mdash; and it comes back %(n)d
      different ways, which is the part a photograph of a sunset cannot tell you.
      %(doorCount)d questions, %(answers)d answers, none of them about
      &ldquo;African culture&rdquo; in general.</p>
  </section>

  <div class="mt-grid">
    <nav class="mt-doors" id="doors" aria-label="The seven questions">
      <ol>
%(doors)s
      </ol>
      <p class="mt-doors-note">Pick a country to put all seven to one place.</p>
      <div class="mt-strip" role="group" aria-label="Countries">
            %(strip)s
      </div>
    </nav>

    <section class="mt-stage" id="stage" aria-live="polite">
      <header class="mt-stage-head" id="stage-head">
        <span class="af-stamp" id="mt-eyebrow">%(n)d countries</span>
        <h2 class="mt-h2" id="mt-asks">%(firstAsks)s</h2>
        <p class="mt-stage-line" id="mt-line">%(firstLine)s</p>
      </header>
      <div class="mt-answers" id="mt-answers">
%(opening)s
      </div>
    </section>
  </div>

  <noscript>
    <p class="mt-nojs">The seven questions above are shown one at a time, which
      needs JavaScript &mdash; without it you are reading the first one,
      answered by all %(n)d countries. Every country name is a link to its own
      page, where all twenty-seven headings are written out in full.</p>
  </noscript>
</main>
%(foot)s

<script type="application/json" id="mt-people">%(people)s</script>
<script type="application/json" id="mt-voices">%(voices)s</script>
%(events)s
%(explore)s
<script src="/scripts/window.js" defer></script>
<script src="/scripts/meet.js" defer></script>
</body>
</html>
"""
