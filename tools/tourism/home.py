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

from . import company, imaging, plate
from . import countrymap
from .model import ROOT, region_of

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
    src = None
    if rec and rec.get("imageUrl"):
        try:
            src = imaging.cdn_url(rec, {"width": 1200, "aspect": [4, 5]}, hero.focal)
        except (ValueError, KeyError):
            src = None
    # One definition of the window, shared with the gateway, the journey engine
    # and the human layer. This function used to build its own clip-path.
    return ('<div class="af-window ct-window">\n        %s\n      </div>'
            % plate.window_svg(shape, country.name, image=src,
                               alt=("%s, with a photograph of the country inside its "
                                    "own borders" % country.name) if src else None,
                               ident="shape-%s" % country.slug,
                               classes="af-window-svg"))


def next_to(country):
    """The countries next to this one, and why they count as next to it.

    Straight from the same links payload the atlas and the journey engine use,
    so a country page, a map and a journey all agree about what borders what.
    Prints nothing where nothing connects rather than reaching for filler.
    """
    try:
        with open(os.path.join(ROOT, "data", "links.json")) as fh:
            rows = (json.load(fh).get("links") or {}).get(country.slug) or []
    except (IOError, ValueError):
        return ""
    if not rows:
        return ""
    out = []
    for r in rows[:4]:
        border = any(w["kind"] == "border" for w in r["why"])
        out.append('<a href="/atlas#/%s"%s>%s<i>%s</i></a>'
                   % (esc(r["to"]), ' data-border="true"' if border else "",
                      esc(r["name"]),
                      esc("%d km" % r["km"] if r.get("km") is not None else "")))
    return ('<div class="foot-next"><span>Next to it</span>%s'
            '<p>Straight-line distances between country centres. Solid names share '
            'a land border with %s.</p></div>' % ("".join(out), esc(country.name)))


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
        # Was "None of ours in <Country>" and "Ask anyway". The homepage is
        # where somebody decides whether Africa is possible for them, and the
        # answer to that is what we do, not the shape of our subsidiaries.
        return company.block_who(company.load(), "ct-op ct-op--house", stamp=False)
    return ('<div class="ct-op"><span>Operated locally by</span><b>%s</b>'
            '<p class="ct-op-base">%s &middot; since %s</p><p>%s</p>'
            '<a class="af-go" href="%s">Enter %s &rarr;</a></div>'
            % (esc(op.name), esc(op.name), esc(op.base), esc(op.since), esc(op.line),
               esc(op.url), esc(op.name)))


# Published, but with no generated landing page: Cameroon has a hand-built one
# and the other two are not generated here. The one place that decides whether
# /<slug> exists — write_all() skips these, and nothing on any page may link to
# them.
NO_PAGE = ("cameroon", "uganda", "namibia")


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


def _map_links(country, countries):
    """Which countries on the plate are pages you can actually go to.

    Built from the dataset rather than assumed, so a neighbour is a link exactly
    when it has a page — the day a fifty-fourth country is published it becomes
    clickable on every map that already shows it, and a country we do not
    publish is drawn but not offered.

    `published` is NOT the test. Three published countries have no generated
    page — see NO_PAGE — and keying off `published` alone put a link to a
    missing /uganda on twelve maps. Whether a page exists is decided in exactly
    one place and both this and write_all() read it.
    """
    return {c.slug: "/%s" % c.slug for c in countries
            if c.published and c.slug != country.slug and c.slug not in NO_PAGE}


def brief_block(country):
    """THE LAND IN BRIEF, beside the map that produced it.

    Every row is measured off the plate or read out of the border table —
    countrymap.brief() will not return a line it cannot derive. The last row is
    the only one from editorial copy, and it is the country's own `when`, which
    is the fact a visitor is actually here for.

    There is deliberately no population and no area in square kilometres. The
    repository holds neither, and one invented number beside four derived ones
    does not read as one weak line, it makes the reader stop trusting the other
    four — and the map they came from.
    """
    rows = list(countrymap.brief(country.slug, country.name))
    when = (country.when or "").strip()
    if when:
        rows.append(("Best time", esc(when)))
    if not rows:
        return ""
    return ('<div class="ct-brief"><h3 class="ct-brief-h">The land in brief</h3>'
            '<dl class="ct-brief-list">%s</dl></div>'
            % "".join('<div class="ct-brief-row"><dt>%s</dt><dd>%s</dd></div>'
                      % (esc(k), v) for k, v in rows))


def _region_phrase(region):
    """Four of the five region names read straight after "Also in". The fifth is
    "Islands", and "Also in Islands" is not English."""
    return "the islands" if (region or "").strip().lower() == "islands" else region


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
    w, h = imaging.dimensions(role)
    return ('<span class="ct-shot"><img src="%s" srcset="%s" sizes="%s" alt="%s" '
            'width="%d" height="%d" loading="lazy" decoding="async" '
            'style="object-position:%s"></span>'
            % (esc(src), esc(srcset), esc(role["sizes"]), esc(rec.get("alt") or ""),
               w, h, imaging.object_position(entry.focal)))


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
        "regionKey": esc(region_of(country)[0]),
        "og": plate.open_graph(
            esc("%s — %s | Afrinkong" % (country.name, country.tagline)),
            esc(country.summary), "/%s" % country.slug),
        "nextTo": next_to(country),
        "description": esc("%s: %s Twenty-seven kinds of experience, from wildlife and mountains "
                           "to culture, food and heritage, with local guides."
                           % (country.name, country.summary)),
        "hero_window": hero_window,
        "calendar": cal,
        "operator": op,
        "hero_class": " has-shape" if hero_window else " no-shape",
        "near": near_html,
        # WHERE IT IS, AND WHAT IT LOOKS LIKE. Two maps and one grammar, the
        # same on all fifty-four: a locator that answers "where in Africa",
        # then the country cropped out of the continental projection with its
        # true land neighbours around it, its rivers and lakes, and a scale bar
        # derived from the projection at its own latitude. What used to stand
        # in for geography here was a link list; the silhouette elsewhere on
        # the site is the country renormalised into its own box, which for a
        # small country is nine straight lines and reads as a shape rather than
        # a place. tools/tourism/countrymap.py records every source, and says
        # why mountains, parks and numbered route markers are not drawn: this
        # repository has no coordinates for any of them.
        "near_block": (
            '<section class="ct-where"><div class="af-frame ct-where-in">'
            '<div class="ct-where-side">'
            '<h2 class="ct-where-h">Where it is</h2>'
            '<p class="ct-where-line">Africa &middot; %s &middot; %s</p>'
            '<div class="ct-where-loc">%s</div>'
            '%s%s</div>'
            '<figure class="ct-where-map">%s'
            '<figcaption>%s</figcaption>'
            '</figure></div></section>'
            % (esc(country.region), esc(country.name),
               countrymap.locator(country.slug, country.name),
               brief_block(country),
               ('<h3 class="ct-where-also">Also in %s</h3>'
                '<div class="ct-near-row">%s</div>'
                % (esc(_region_phrase(country.region)), near_html))
               if near_html else "",
               countrymap.atlas(country.slug, country.name,
                                links=_map_links(country, countries)),
               esc(countrymap.caption(country.slug, country.name)))),
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
COUNTRY_CSS = """/* Tokens, reset, type scale and primitives are in /styles/afrinkong.css.
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
/* The masthead row, measured rather than guessed. The 1010px breakpoint was set
   before the Explore key existed; with it there the row wanted 1,271px on the
   longest country name and pushed "Plan a journey" 179px off a 1011 screen and
   126px off a 1024 one, on nineteen pages.

   Two in-page anchors — Highlights, Why go — came out of the nav as well: a
   masthead that scrolls with you is for leaving the page, and the page's own
   sections are a scroll away. Four routes left, all of them somewhere else.

   Below 1180 the routes go. Below 480 the mark's tagline goes with them: one
   line of nowrap mono, and it was the whole of the 320px overflow. */
@media(max-width:1180px){.routes{display:none}}
@media(max-width:560px){.frame{padding:0 20px}.mark b{font-size:20px}
  .mast-in{gap:12px}
  .btn{padding:10px 14px;font-size:10px;letter-spacing:.12em}}
@media(max-width:480px){.mark span{display:none}
  .mark-up{font-size:8px;letter-spacing:.2em}}
/* "Madagascar" and "South Africa" set at 20px are 147 and 150 pixels of nowrap
   on their own; with the Explore key and the call beside them the row wanted
   349 on a 320 screen. The country name is the one thing on this masthead that
   cannot be shortened, so everything around it gives way instead. */
@media(max-width:400px){.frame{padding:0 16px}.mast-in{gap:10px}
  .mark b{font-size:17px}}

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
.ct-window svg{height:100%}

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
/* The operator block's own width is 44em of a 17px face — 748 pixels, 96
   average characters. Capped where the paragraph is, not where the block is,
   so the heading above it keeps the block's full width. */
.ct-op p{color:var(--c-muted);margin-top:12px;max-width:72ch}
.ct-op .af-go{margin-top:16px}
.ct-op--none b{font-size:clamp(20px,2.2vw,27px)}
@media(max-width:640px){.ct-cal-row{grid-template-columns:repeat(6,1fr)}
  .ct-mon:nth-child(6n){border-right:0}
  .ct-mon:nth-child(-n+6){border-bottom:var(--fj-rule)}}

/* The region strip: the page's one link outward, and what makes a country page
   part of an atlas rather than a leaflet. */
.ct-note-go{white-space:nowrap;color:var(--c-accent);border-bottom:1px solid var(--c-accent)}
/* WHERE IT IS: the locator, the atlas and the neighbours, in one section.
   It was a row of links called "Also in East Africa", which answered the
   question a reader has after the map rather than the one they have before it.
   The two maps are built by tools/tourism/countrymap.py and are identical in
   grammar on all fifty-four countries — only the geography changes. */
.ct-where{background:var(--fj-dust);border-bottom:var(--fj-rule);padding:var(--sp-5) 0}
.ct-where-in{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);
  gap:var(--sp-5);align-items:start}
.ct-where-h{font-family:var(--fj-mono);font-size:10px;font-weight:400;
  letter-spacing:.22em;text-transform:uppercase;color:var(--c-accent);margin:0}
.ct-where-line{margin-top:10px;font-family:var(--fj-mono);font-size:9.5px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--c-muted)}
.ct-where-loc{margin-top:var(--sp-3);max-width:190px}
/* THE LAND IN BRIEF. A reading of the plate next to it, not a fact box bought
   in from somewhere else: every row is measured off the same projection or read
   out of the same border table, which is why there is no population and no area
   here. Set as a definition list because that is what it is — the label is the
   question and the value is the answer — and ruled row by row so the eye can
   run down the answers without reading the labels twice. */
.ct-brief{margin-top:var(--sp-4);border-top:var(--fj-rule);padding-top:14px}
.ct-brief-h{font-family:var(--fj-mono);font-size:9.5px;font-weight:400;
  letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent);margin:0}
.ct-brief-list{margin:12px 0 0}
.ct-brief-row{display:grid;grid-template-columns:78px minmax(0,1fr);
  gap:14px;padding:9px 0;border-bottom:1px solid
  color-mix(in srgb,var(--c-primary) 10%,transparent)}
.ct-brief-row:last-child{border-bottom:0}
.ct-brief-row dt{font-family:var(--fj-mono);font-size:9px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--c-muted);padding-top:2px}
.ct-brief-row dd{margin:0;font-size:14px;line-height:1.45;color:var(--c-primary)}
/* A neighbour we publish is a link on the plate, in its shape and in its name.
   Hover and focus lift it out of the quiet layer rather than adding anything to
   it, so nothing moves and the map does not reflow. The focus ring is drawn as
   a stroke because an outline on an svg child is not reliably painted. */
.cm-link{cursor:pointer}
.cm-link path{transition:fill .18s}
.cm-link:hover path,.cm-link:focus-visible path{
  fill:color-mix(in srgb,var(--c-accent) 22%,var(--c-bg))}
.cm-link:hover .cm-near-name,.cm-link:focus-visible .cm-near-name{
  fill:var(--c-accent)}
.cm-link:focus-visible{outline:none}
.cm-link:focus-visible path{stroke:var(--c-accent);
  stroke-width:calc(var(--u) * .008)}
.ct-where-also{margin-top:var(--sp-4);font-family:var(--fj-mono);font-size:9.5px;
  font-weight:400;letter-spacing:.2em;text-transform:uppercase;color:var(--c-muted)}
.ct-where-also+.ct-near-row{margin-top:10px}
.ct-where-map{margin:0;min-width:0}
.ct-where-map figcaption{margin-top:12px;font-family:var(--fj-mono);font-size:9px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--c-muted)}
@media(max-width:860px){.ct-where-in{grid-template-columns:minmax(0,1fr)}}
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
/* A grid item will not shrink below the widest unbreakable thing inside it, and
   here that is the country's name set at the clamp's 46px floor: "MADAGASCAR"
   is 328 pixels on its own, so the whole opening column stayed 328 wide inside
   a 320 screen and took the stamp, the tagline, the lede and the calls out with
   it. The floor comes down before the phone does. */
@media(max-width:420px){.open h1{font-size:clamp(30px,10vw,46px)}}

.highs{display:grid;grid-template-columns:repeat(3,1fr);gap:34px 32px}
.ct-high b{display:block;font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent)}
.ct-high h3{font-size:22px;margin:8px 0 8px}
.ct-high p{font-size:15px;color:var(--c-muted)}
.ct-high .ct-shot{display:block;margin-bottom:16px}
/* height:auto is what lets the <img> carry width and height. Without it both
   dimensions are definite from the attributes, aspect-ratio is ignored, and a
   4:3 slot renders at the photograph's own 16:9 — which is why these tags were
   written without them and 122 images across twenty pages reserved no space at
   all. With it the attributes are a ratio hint, aspect-ratio still decides the
   shape, and the box is held before the file arrives. */
.ct-high .ct-shot img{width:100%;height:auto;aspect-ratio:4/3;object-fit:cover}
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
/* Where you are, at the foot of the page: the ladder you came down and the
   countries beside this one. It replaces nothing — the site map is still below
   — but it is the last chance to say that this country has neighbours. */
.foot-where{padding-bottom:26px;margin-bottom:26px;border-bottom:var(--fj-rule-dark)}
.foot-where ol{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;
  font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase}
.foot-where li+li::before{content:"/";margin-right:10px;color:var(--fj-onbasalt-dim);
  opacity:.5}
.foot-where a{color:var(--fj-onbasalt-dim)}
.foot-where a:hover{color:var(--c-bg)}
.foot-where [aria-current]{color:var(--c-accent)}
.foot-next{margin-top:18px;display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px}
.foot-next>span{font-family:var(--fj-mono);font-size:9px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--fj-onbasalt-dim);width:100%}
.foot-next a{font-family:var(--fj-display);font-size:19px;text-transform:uppercase;
  color:var(--fj-onbasalt-dim);border-bottom:1px solid transparent}
.foot-next a[data-border]{color:var(--c-bg)}
.foot-next a:hover{border-color:var(--c-accent)}
.foot-next i{font-style:normal;font-family:var(--fj-mono);font-size:9px;letter-spacing:.14em;
  margin-left:7px;color:var(--fj-onbasalt-dim)}
.foot-next p{width:100%;margin-top:6px;font-size:12.5px;line-height:1.6;
  color:var(--fj-onbasalt-dim)}
.foot-bar{margin-top:40px;padding:20px 0;border-top:var(--fj-rule-dark);font-family:var(--fj-mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--fj-onbasalt-dim)}
.foot-bar a{border-bottom:1px solid var(--c-accent)}
@media(max-width:820px){.foot-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition-duration:.001ms !important}}
@media(pointer:coarse){
  .mark{padding:5px 0}
  .foot-bar a{padding-block:6px;display:inline-block}
}

"""


STYLE_NOTE = """/* The country landing pages — /botswana, /kenya, /ghana and sixteen more.
 * ---------------------------------------------------------------------------
 * GENERATED. Do not edit: `python3 tools/tourism/build.py homes` overwrites it
 * from TEMPLATE in tools/tourism/home.py. Edit that.
 *
 * Nineteen pages carried this same 10 KB block inline, which is 197 KB of CSS
 * describing one page shape. Tokens, reset and primitives are not here; they
 * are in /styles/afrinkong.css, which these pages already link.
 */

"""

STYLESHEET = os.path.join(ROOT, "styles", "country.css")


def write_all(countries, taxonomy, skip=NO_PAGE, out_dir=None, log=print):
    out_dir = out_dir or ROOT
    os.makedirs(os.path.dirname(STYLESHEET), exist_ok=True)
    with open(STYLESHEET, "w") as f:
        f.write(STYLE_NOTE + COUNTRY_CSS.strip() + "\n")
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


# THE COUNTRY FOOTER, AND TWO THINGS THAT WERE IN IT
#
# The bar read "0 of 27 slots illustrated - Figures and contact details are
# illustrative until verified". The first half is a build metric — how far our
# own photograph pipeline has got — printed to a traveller, and on a country
# whose photographs have not resolved yet it read as "this place has nothing".
# The second half stopped being true the moment the company acquired a name, a
# registration and an address. The bar carries the colophon now, the same one
# the homepage ends on; the fifty-one country pages had no company line at all
# until this.
#
# The Elsewhere column offered "Afrinkong / Cameroon / Every destination /
# Enquire". Cameroon was hardcoded, so /morocco proposed Cameroon as its one
# neighbour for no reason a reader of that page could see, and Enquire went to
# /contact, which is Kamerun's desk.
#
# Explanations like this belong here and not in the template. The first draft
# put them in the HTML and they shipped into all fifty-one pages.


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/country.css">
</head>
<body>
<a class="af-skip" href="#main">Skip to content</a>
<header class="mast">
  <div class="af-frame mast-in">
    <a class="mark" href="/%(slug)s"><span class="mark-up">Afrinkong</span><b>%(name)s</b><span>%(tagline)s</span></a>
    <nav class="routes" aria-label="Primary">
      <a href="/atlas#/%(slug)s">The Atlas</a>
      <a href="/journey">Build a journey</a>
      <a href="/meet#/%(slug)s">Meet %(name)s</a>
      <a href="/tourism/%(slug)s">All %(count)d</a>
      <a href="/how-it-works">How it works</a>
    </nav>
    <a class="af-btn af-btn--solid" href="/journey">Build a journey</a>
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
          <a class="af-btn af-btn--solid" href="/journey">Build a journey <i>&rarr;</i></a>
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
      <a class="act go" href="/journey">Build a journey <i>&rarr;</i></a>
      <a class="act faint" href="/tourism/%(slug)s">See all %(count)d experiences <i>&rarr;</i></a>
    </div>
  </div>
</section>

</main>

<footer class="foot">
  <div class="af-frame">
    <!-- Where you are, and what is next to it. A footer on this site is not a
         site map; it is the last place the visitor can be told that the country
         they are reading about has neighbours. -->
    <nav class="foot-where" aria-label="Where you are">
      <ol>
        <li><a href="/atlas">Africa</a></li>
        <li><a href="/atlas#/%(regionKey)s">%(region)s</a></li>
        <li><span aria-current="page">%(name)s</span></li>
      </ol>
      %(nextTo)s
    </nav>
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
        <a href="/atlas">The atlas of Africa</a>
        <a href="/places">Every place</a>
        <a href="/enquire">Begin a journey</a>
      </div>
    </div>
    <div class="foot-bar">
      <a href="/">Part of Afrinkong</a> &middot; %(name)s
      <span class="foot-co"><!-- gen:company -->
      <!-- /gen:company --></span>
    </div>
  </div>
</footer>
<script src="/scripts/story-search.js" defer></script>
<script src="/scripts/explore.js" defer></script>
</body>
</html>
"""
