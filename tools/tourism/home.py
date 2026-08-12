"""A standalone home page for every country in the dataset.

    python3 tools/tourism/build.py homes
    -> /kenya.html, /rwanda.html, /tanzania.html, ...

Each one has to work on its own. Somebody arriving on /kenya from a search
result should find a complete site for Kenya — what it is, what you can do
there, what makes it worth the flight, and how to start — without ever needing
the gateway that links to it. That is the test these pages are written against.

They are generated, not hand-written, because the material for them already
exists: every country carries twenty-seven categories, each with a caption, a
description and a subject, written for that country. A hand-written page per
country would be five copies of the same structure drifting apart within a
month, and the eighth country would still need writing.

Cameroon is the deliberate exception. Its home page is hand-built at
cameroon.html — it has photographs, a fourteen-day route and a transect none of
the others have yet — so this generator skips it rather than overwriting a
better page with a poorer one.

Where a country has resolved photographs they are used; where it does not, the
page is typographic and says nothing it cannot support. A country page with
twenty-seven grey boxes on it would be worse than one with none.
"""

import html as html_mod
import json
import os

from . import imaging
from .model import ROOT

SHAPES_PATH = os.path.join(ROOT, "tourism", "shapes.json")


def shapes():
    """slug -> {w, h, d}: every country's own outline, projected at build time.

    Vendored rather than computed here. The geometry comes from Natural Earth by
    way of `tools/africa_map.py --solo`, which needs a 2 MB boundary file this
    generator has no business depending on. Twenty-nine kilobytes of finished
    path data is the right thing to keep in the repository; the tool that made
    it is one command away when a country is added.
    """
    try:
        with open(SHAPES_PATH) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {}


def window(country, entry_for):
    """The country's outline, with its hero photograph masked into it.

    This is the site's signature and it belongs on every country page, not only
    on the gateway: the same country reads as the same object wherever you meet
    it. Where the resolver has found a photograph it fills the shape; where it
    has not, the shape is filled in accent — which is a finished state, not a
    placeholder, so a country with no photography still has a hero.
    """
    shape = shapes().get(country.slug)
    if not shape:
        return ""
    art = ""
    hero = entry_for("hero")
    rec = getattr(hero, "image", None) if hero else None
    if rec and rec.get("imageUrl"):
        try:
            src = imaging.cdn_url(rec, {"width": 1200, "aspect": [4, 5]}, hero.focal)
            art = ('<image clip-path="url(#shape-%s)" href="%s" x="0" y="0" width="%s" '
                   'height="%s" preserveAspectRatio="xMidYMid slice"/>'
                   % (esc(country.slug), esc(src), shape["w"], shape["h"]))
        except (ValueError, KeyError):
            art = ""
    label = ("%s, with a photograph of the country inside its own borders" % country.name
             if art else "The outline of %s" % country.name)
    return ('<div class="af-window ct-window">\n'
            '        <svg viewBox="0 0 %s %s" role="img" aria-label="%s">\n'
            '          <defs><clipPath id="shape-%s"><path d="%s"/></clipPath></defs>\n'
            '          <path class="af-window-fill" d="%s"/>%s\n'
            '        </svg>\n      </div>'
            % (shape["w"], shape["h"], esc(label), esc(country.slug),
               shape["d"], shape["d"], art))


MONTHS = ("J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D")
MONTH_NAMES = ("January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December")


def calendar(country):
    """This country's own year, as twelve cells rather than a paragraph.

    Every country carries the months it is actually good in. Printing that as a
    strip means a visitor can answer "can I go when I am free" in about a second,
    which is the question that decides most trips and the one a season paragraph
    buries.
    """
    if not country.months:
        return ""
    cells = "".join(
        '<span class="ct-mon%s" title="%s"><b>%s</b></span>'
        % (" is-on" if (i + 1) in country.months else "", esc(MONTH_NAMES[i]), MONTHS[i])
        for i in range(12))
    note = ('<p class="ct-cal-note">%s</p>' % esc(country.when)) if country.when else ""
    return ('<section class="ct-cal"><div class="af-frame">'
            '<h2 class="ct-cal-h">When to come</h2>'
            '<div class="ct-cal-row" role="img" aria-label="%s is at its best in %s">%s</div>'
            '%s</div></section>'
            % (esc(country.name),
               esc(", ".join(MONTH_NAMES[m - 1] for m in sorted(country.months))),
               cells, note))


def operator_block(country):
    """Who actually runs this country, with enough about them to be evidence."""
    op = country.operator
    if not op:
        return ('<div class="ct-op ct-op--none"><span>Local operator</span>'
                '<b>A licensed company based in %s</b>'
                '<p>Every destination here is run by a company in the country itself, working '
                'through the same twenty-seven categories, so two countries can be compared on '
                'the same terms. Tell us the month and we will put you with the right one.</p>'
                '<a class="af-go" href="/contact">Start a journey &rarr;</a></div>'
                % esc(country.name))
    return ('<div class="ct-op"><span>Operated locally by</span><b>%s</b>'
            '<p class="ct-op-base">%s &middot; since %s</p><p>%s</p>'
            '<a class="af-go" href="%s">Enter %s &rarr;</a></div>'
            % (esc(op.name), esc(op.name), esc(op.base), esc(op.since), esc(op.line),
               esc(op.url), esc(op.name)))


def neighbours(country, countries, limit=5):
    """The other countries in this region, so a country page is part of an atlas.

    A visitor who lands on /senegal from a search result and finds nothing but
    Senegal has met a leaflet. The region strip is what makes twenty-two
    separate pages behave like one continent, and it scales: it reads the
    dataset, so a fifty-fourth country appears in its neighbours' strips the day
    its file is added.
    """
    same = [c for c in countries
            if c.slug != country.slug and c.published and c.region == country.region]
    return same[:limit]

# The six that carry a country's landscape argument, in the order a visitor
# meets them. Kept short on purpose: this is the highlight reel, and the full
# twenty-seven are one link away.
HIGHLIGHTS = ("nature", "wildlife", "mountains", "beaches", "forests", "culture")

# The four that answer "why here rather than the country next door".
REASONS = ("why-visit", "hidden-gems", "eco-tourism", "heritage")

# Everything else, grouped so the index reads as a list of things to do rather
# than a wall of twenty-seven tiles.
GROUPS = (
    ("Landscapes", ("nature", "mountains", "waterfalls", "lakes-rivers", "beaches", "forests")),
    ("Wildlife", ("wildlife", "safari", "eco-tourism", "outdoor")),
    ("People and culture", ("culture", "traditional-people", "festivals", "crafts",
                            "food", "family-community", "local-life")),
    ("Places", ("cities", "architecture", "historic-sites", "heritage")),
    ("Ways to travel", ("adventure", "luxury", "photography", "hidden-gems")),
)


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def picture(entry, role):
    """An <img> for an entry, or nothing. Never a placeholder box."""
    rec = getattr(entry, "image", None)
    if not rec or not rec.get("imageUrl"):
        return ""
    try:
        src = imaging.cdn_url(rec, role, entry.focal)
        srcset = imaging.srcset(rec, role, entry.focal)
    except (ValueError, KeyError):
        return ""
    return ('<span class="ct-shot"><img src="%s" srcset="%s" sizes="%s" alt="%s" '
            'loading="lazy" decoding="async" style="object-position:%s"></span>'
            % (esc(src), esc(srcset), esc(role["sizes"]), esc(rec.get("alt") or ""),
               imaging.object_position(entry.focal)))


def build(country, taxonomy, countries=()):
    """-> the full HTML for one country's home page."""
    def entry(cat_id):
        return country.entry(cat_id)

    hero_window = window(country, entry)
    cal = calendar(country)
    op = operator_block(country)
    near = neighbours(country, countries)
    near_html = "".join(
        '<a href="%s"><em>%s</em><span>%s</span></a>' % (esc(c.url), esc(c.name), esc(c.tagline))
        for c in near)

    highlights = []
    for cid in HIGHLIGHTS:
        e = entry(cid)
        if not e or not e.caption:
            continue
        cat = taxonomy.by_id.get(cid) or {"title": cid}
        highlights.append(
            '      <article class="ct-high">%s\n'
            '        <b>%s</b>\n        <h3>%s</h3>\n        <p>%s</p>\n      </article>'
            % (picture(e, taxonomy.role(cid)), esc(cat["title"].split("/")[0].strip()),
               esc(e.caption), esc(e.description)))

    reasons = []
    for cid in REASONS:
        e = entry(cid)
        if not e or not e.caption:
            continue
        reasons.append('      <div class="ct-reason"><b>%s</b><h3>%s</h3><p>%s</p></div>'
                       % (esc((taxonomy.by_id.get(cid) or {}).get("title", cid).split("/")[0].strip()),
                          esc(e.caption), esc(e.description)))

    groups = []
    listed = 0
    for title, ids in GROUPS:
        rows = []
        for cid in ids:
            e = entry(cid)
            if not e or not e.caption:
                continue
            # `subject` is the search phrase written for the image resolver — it
            # was being printed to visitors as if it were copy, so every country
            # page read "the Great Rift Valley escarpment seen from the Naivasha
            # road" under its own caption. `description` is the sentence written
            # for a reader.
            rows.append('        <li><b>%s</b><span>%s</span></li>'
                        % (esc(e.caption), esc(e.description or "")))
            listed += 1
        if rows:
            groups.append('      <div class="ct-group"><b>%s</b>\n        <ul>\n%s\n        </ul>\n      </div>'
                          % (esc(title), "\n".join(rows)))

    resolved = sum(1 for c in taxonomy.enabled
                   if entry(c["id"]) and (entry(c["id"]).image or {}).get("imageUrl"))

    return TEMPLATE % {
        "name": esc(country.name),
        "slug": esc(country.slug),
        "adjective": esc(country.adjective or country.name),
        "region": esc(country.region),
        "tagline": esc(country.tagline),
        "summary": esc(country.summary),
        "title": esc("%s — %s | Guided Journeys and Experiences" % (country.name, country.tagline)),
        "description": esc("%s: %s Twenty-seven kinds of experience, from wildlife and mountains "
                           "to culture, food and heritage, with local guides."
                           % (country.name, country.summary)),
        "hero_window": hero_window,
        "calendar": cal,
        "operator": op,
        "hero_class": " has-shape" if hero_window else " no-shape",
        "near": near_html,
        "near_block": ('<section class="ct-near"><div class="af-frame"><h2>Also in %s</h2>'
                       '<div class="ct-near-row">%s</div></div></section>'
                       % (esc(country.region), near_html)) if near_html else "",
        "highlights": "\n".join(highlights),
        "reasons": "\n".join(reasons),
        "groups": "\n".join(groups),
        "count": len(taxonomy.enabled),
        "listed": listed,
        "resolved": resolved,
    }


# Three are skipped: each already has a better home page than this generator can
# make. Cameroon's is hand-built at cameroon.html; Uganda and Namibia have whole
# operator sites of their own at Pearl Trails Uganda and Namib Skyline. A
# generated page would be a second, poorer front door to each. They keep their
# datasets, because the gateway, the map and their neighbours' region strips all
# read a country from the same place whether or not it has a page here.
def write_all(countries, taxonomy, skip=("cameroon", "uganda", "namibia"), out_dir=None, log=print):
    out_dir = out_dir or ROOT
    written = []
    for c in countries:
        if c.slug in skip or not c.published:
            continue
        path = os.path.join(out_dir, "%s.html" % c.slug)
        with open(path, "w") as f:
            f.write(build(c, taxonomy, countries))
        written.append(path)
        log("  wrote %s" % os.path.relpath(path, ROOT))
    return written


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="stylesheet" href="/styles/afrinkong.css">
<style>
/* Tokens, reset, type scale and primitives are in /styles/afrinkong.css.
   What follows is this page shape only. */
.mast{position:sticky;top:0;z-index:70;background:var(--c-bg);border-bottom:2px solid var(--c-primary)}
.mast-in{display:flex;align-items:center;gap:34px;padding:14px 0}
.mark{margin-right:auto;display:flex;flex-direction:column;gap:3px}
.mark-up{font-family:var(--fj-mono);font-size:8.5px;letter-spacing:.28em;text-transform:uppercase;color:var(--c-accent)}
.mark b{font-family:var(--fj-display);font-size:26px;font-weight:700;text-transform:uppercase;line-height:1;white-space:nowrap}
.mark span{font-family:var(--fj-mono);font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--c-muted);white-space:nowrap}
.routes{display:flex;gap:26px}
.routes a{font-family:var(--fj-mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;white-space:nowrap;color:var(--c-muted);padding:4px 0;border-bottom:2px solid transparent;transition:color .2s,border-color .2s}
.routes a:hover{color:var(--c-primary);border-color:var(--c-accent)}
.btn{font-family:var(--fj-mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--c-bg);background:var(--c-primary);padding:12px 20px;transition:background .2s}
.btn:hover{background:var(--c-accent)}
@media(max-width:1010px){.routes{display:none}}
@media(max-width:560px){.frame{padding:0 20px}.mark b{font-size:20px}.btn{padding:10px 14px;font-size:10px;letter-spacing:.12em}}

.open{padding:calc(var(--sp-6) + 8px) 0 var(--sp-6);border-bottom:var(--fj-rule)}
.open-grid{display:grid;grid-template-columns:1.06fr .94fr;gap:56px;align-items:center}
.open-grid.no-shape{grid-template-columns:1fr;max-width:36em}
.open h1{font-size:clamp(46px,7vw,104px);margin:14px 0 0;letter-spacing:-.02em}
/* The tagline is the country's argument and gets its own line at display size,
   rather than being appended to the name in accent — which made the name the
   smaller half of its own headline. */
.open-tag{font-family:var(--fj-display);font-weight:700;text-transform:uppercase;
  font-size:clamp(20px,2.6vw,34px);line-height:1.05;color:var(--c-accent);margin-top:10px}
.lede{font-size:19px;color:var(--c-muted);margin-top:22px;max-width:38em}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:32px}

/* The window. Height-led, so every country is drawn at the same visual weight
   whatever its proportions — Chad and Rwanda should feel like the same kind of
   object on the page. */
.ct-window{height:min(58vh,520px)}
.ct-window svg{height:100%%}

/* This country's year. Twelve cells beats a season paragraph: a visitor answers
   "can I go when I am free" in about a second. */
.ct-cal{padding:30px 0;border-bottom:var(--fj-rule)}
.ct-cal-h{font-family:var(--fj-mono);font-size:10px;font-weight:400;letter-spacing:.22em;
  text-transform:uppercase;color:var(--c-muted);margin-bottom:14px}
.ct-cal-row{display:grid;grid-template-columns:repeat(12,1fr);gap:0;border:var(--fj-rule)}
.ct-mon{display:flex;align-items:center;justify-content:center;padding:12px 0;
  border-right:var(--fj-rule);background:var(--c-bg)}
.ct-mon:last-child{border-right:0}
.ct-mon b{font-family:var(--fj-mono);font-size:11px;font-weight:400;letter-spacing:.1em;color:var(--c-muted)}
.ct-mon.is-on{background:var(--c-accent)}
.ct-mon.is-on b{color:var(--c-bg);font-weight:700}
.ct-cal-note{margin-top:12px;font-size:15px;color:var(--c-muted);max-width:52em}

/* Who runs this country. The platform's whole claim is that somebody local
   does, so the page says which company, from where, and since when. */
.ct-close{padding-bottom:8px}
.ct-op{border-top:2px solid var(--c-accent);padding-top:22px;max-width:44em}
.ct-op>span{display:block;font-family:var(--fj-mono);font-size:9.5px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--c-muted)}
.ct-op b{display:block;font-family:var(--fj-display);font-size:clamp(24px,3vw,36px);
  font-weight:700;text-transform:uppercase;line-height:1.04;margin-top:8px}
.ct-op-base{font-family:var(--fj-mono);font-size:9.5px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--c-accent);margin-top:8px}
.ct-op p{color:var(--c-muted);margin-top:12px}
.ct-op .af-go{margin-top:16px}
.ct-op--none b{font-size:clamp(20px,2.2vw,27px)}
@media(max-width:640px){.ct-cal-row{grid-template-columns:repeat(6,1fr)}
  .ct-mon:nth-child(6n){border-right:0}
  .ct-mon:nth-child(-n+6){border-bottom:var(--fj-rule)}}

/* The region strip: the page's one link outward, and what makes a country page
   part of an atlas rather than a leaflet. */
.ct-note-go{white-space:nowrap;color:var(--c-accent);border-bottom:1px solid var(--c-accent)}
.ct-near{background:var(--fj-dust);border-bottom:var(--fj-rule);padding:26px 0}
.ct-near h2{font-family:var(--fj-mono);font-size:10px;font-weight:400;letter-spacing:.22em;
  text-transform:uppercase;color:var(--c-muted);margin-bottom:14px}
.ct-near-row{display:flex;flex-wrap:wrap;gap:0 34px}
.ct-near-row a{padding:8px 0;transition:color var(--t-fast) var(--ease)}
.ct-near-row a:hover{color:var(--c-accent)}
.ct-near-row em{font-style:normal;font-family:var(--fj-display);font-size:19px;font-weight:700;text-transform:uppercase}
.ct-near-row span{font-family:var(--fj-mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--c-muted);margin-left:10px}
@media(max-width:900px){.open-grid{grid-template-columns:1fr;gap:34px}
  .ct-window{height:min(46vh,360px);max-width:420px}
  .ct-near-row{gap:0 22px}}

.highs{display:grid;grid-template-columns:repeat(3,1fr);gap:34px 32px}
.ct-high b{display:block;font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent)}
.ct-high h3{font-size:22px;margin:8px 0 8px}
.ct-high p{font-size:15px;color:var(--c-muted)}
.ct-high .ct-shot{display:block;margin-bottom:16px}
.ct-high .ct-shot img{width:100%%;aspect-ratio:4/3;object-fit:cover}
@media(max-width:900px){.highs{grid-template-columns:1fr 1fr;gap:28px 24px}}
@media(max-width:560px){.highs{grid-template-columns:1fr}}

/* Two columns, not three: these carry a sentence each now, and a sentence
   in a third of the measure sets to four words a line. */
.groups{display:grid;grid-template-columns:repeat(2,1fr);gap:0;border-top:2px solid var(--c-primary)}
.ct-group{padding:26px 34px 22px 0;border-right:var(--fj-rule);border-bottom:var(--fj-rule)}
.ct-group:nth-child(2n){border-right:0;padding-right:0}
.ct-group>b{display:block;font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent);margin-bottom:14px}
.ct-group li{padding:13px 0;border-bottom:var(--fj-rule)}
.ct-group li:last-child{border-bottom:0}
.ct-group li b{display:block;font-family:var(--fj-display);font-size:16px;font-weight:700;text-transform:uppercase}
.ct-group li span{display:block;font-size:14px;line-height:1.5;color:var(--c-muted);margin-top:5px}
@media(max-width:900px){.groups{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.groups{grid-template-columns:1fr}.ct-group{border-right:0;padding-right:0}}

.reasons{display:grid;grid-template-columns:repeat(2,1fr);gap:0;border-top:2px solid var(--c-accent)}
.ct-reason{padding:28px 34px 24px 0}
.ct-reason b{display:block;font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent);margin-bottom:10px}
.ct-reason h3{font-size:24px;margin-bottom:10px}
.ct-reason p{font-size:15px}
@media(max-width:760px){.reasons{grid-template-columns:1fr}}

.end{text-align:center;padding:92px 0}
.end h2{font-size:clamp(30px,4.6vw,60px)}
.end h2 em{font-style:normal;color:var(--c-accent)}
.end p{margin:16px auto 0;max-width:46ch;color:var(--c-muted)}
.end .acts{justify-content:center}

.foot{background:var(--fj-basalt);color:var(--fj-onbasalt);padding:56px 0 0}
.foot-grid{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:40px}
.foot-brand{font-family:var(--fj-display);font-size:26px;font-weight:700;text-transform:uppercase;color:var(--c-bg)}
.foot-brand span{display:block;font-family:var(--fj-mono);font-size:9.5px;font-weight:400;letter-spacing:.28em;color:var(--c-accent);margin-top:7px}
.foot-grid p{margin-top:14px;font-size:14.5px;max-width:32em;color:var(--fj-onbasalt-dim)}
.foot-col b{display:block;font-family:var(--fj-mono);font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--c-accent);margin-bottom:12px;font-weight:400}
.foot-col a,.foot-col span{display:block;font-size:14.5px;padding:5px 0;color:var(--fj-onbasalt-dim)}
.foot-col a:hover{color:var(--c-bg)}
.foot-bar{margin-top:40px;padding:20px 0;border-top:var(--fj-rule-dark);font-family:var(--fj-mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--fj-onbasalt-dim)}
.foot-bar a{border-bottom:1px solid var(--c-accent)}
@media(max-width:820px){.foot-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition-duration:.001ms !important}}
</style>
</head>
<body>
<a class="af-skip" href="#main">Skip to content</a>
<header class="mast">
  <div class="af-frame mast-in">
    <a class="mark" href="/%(slug)s"><span class="mark-up">Afrinkong</span><b>%(name)s</b><span>%(tagline)s</span></a>
    <nav class="routes">
      <a href="/atlas#/%(slug)s">The Atlas</a>
      <a href="#highlights">Highlights</a>
      <a href="#why">Why go</a>
      <a href="/tourism/%(slug)s">All %(count)d</a>
    </nav>
    <a class="af-btn af-btn--solid" href="/contact">Plan a journey</a>
  </div>
</header>

<main id="main">
<section class="open">
  <div class="af-frame">
    <div class="open-grid%(hero_class)s">
      <div>
        <span class="af-stamp">%(region)s &middot; Afrinkong</span>
        <h1>%(name)s</h1>
        <p class="open-tag">%(tagline)s.</p>
        <p class="lede">%(summary)s</p>
        <div class="acts">
          <a class="af-btn af-btn--solid" href="/contact">Plan a journey <i>&rarr;</i></a>
          <a class="af-btn af-btn--quiet" href="#experiences">What you can do here <i>&rarr;</i></a>
        </div>
      </div>
      %(hero_window)s
    </div>
  </div>
</section>

%(near_block)s
%(calendar)s

<section class="af-zone" id="highlights">
  <div class="af-frame">
    <div class="af-head">
      <div class="af-head-no"><b>01</b><span>Highlights</span></div>
      <div>
        <h2>What %(name)s is <em>known for</em>.</h2>
        <p class="af-note">Six of the twenty-seven, and the ones most people come for. The rest are below &mdash; and none of them is filler.</p>
      </div>
    </div>
    <div class="highs">
%(highlights)s
    </div>
  </div>
</section>

<section class="af-zone af-zone--dust" id="experiences">
  <div class="af-frame">
    <div class="af-head">
      <div class="af-head-no"><b>02</b><span>Experiences</span></div>
      <div>
        <h2>%(listed)d ways to <em>spend the time</em>.</h2>
        <p class="af-note">Every country we cover works through the same twenty-seven categories, so you can hold two of them side by side and compare like with like rather than one brochure against another. <a class="ct-note-go" href="/compare?a=%(slug)s">Compare %(name)s with another &rarr;</a> The two not listed here are the hero picture and the case for going, which has a section of its own below.</p>
      </div>
    </div>
    <div class="groups">
%(groups)s
    </div>
  </div>
</section>

<section class="af-zone af-zone--basalt" id="why">
  <div class="af-frame">
    <div class="af-head">
      <div class="af-head-no"><b>03</b><span>Why go</span></div>
      <div>
        <h2>The case for <em>%(name)s</em>.</h2>
      </div>
    </div>
    <div class="reasons">
%(reasons)s
    </div>
  </div>
</section>

<section class="af-zone">
  <div class="af-frame ct-close">
    %(operator)s
  </div>
  <div class="af-frame end">
    <span class="stamp">Begin</span>
    <h2>Your %(name)s <em>starts here</em>.</h2>
    <p>Tell us the month, or simply the thing you want to see, and a guide who works there will answer.</p>
    <div class="acts">
      <a class="act go" href="/contact">Plan a journey <i>&rarr;</i></a>
      <a class="act faint" href="/tourism/%(slug)s">See all %(count)d experiences <i>&rarr;</i></a>
    </div>
  </div>
</section>

</main>

<footer class="foot">
  <div class="af-frame">
    <div class="foot-grid">
      <div>
        <div class="foot-brand">%(name)s<span>%(tagline)s</span></div>
        <p>%(summary)s</p>
      </div>
      <div class="foot-col">
        <b>%(name)s</b>
        <a href="#highlights">Highlights</a>
        <a href="#experiences">Experiences</a>
        <a href="#why">Why go</a>
        <a href="/tourism/%(slug)s">All %(count)d experiences</a>
      </div>
      <div class="foot-col">
        <b>Elsewhere</b>
        <a href="/">Afrinkong</a>
        <a href="/cameroon">Cameroon</a>
        <a href="/tourism/">Every destination</a>
        <a href="/contact">Enquire</a>
      </div>
    </div>
    <div class="foot-bar">
      <a href="/">Part of Afrinkong</a> &middot; %(name)s &middot; %(resolved)d of %(count)d slots illustrated &middot; Figures and contact details are illustrative until verified
    </div>
  </div>
</footer>
</body>
</html>
"""
