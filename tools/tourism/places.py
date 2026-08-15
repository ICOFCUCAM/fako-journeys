"""A real page for every place: /places/<country>/<place>.

    python3 tools/tourism/build.py places

Five hundred and seventy-two pieces of editorial existed only inside three
JavaScript interfaces. The atlas could show you Bwindi, the journey engine could
put it in an itinerary and the human layer could file it under Culture, but
there was no address for it — nothing a search engine could index, nothing
somebody could send, and nothing at all for a visitor with JavaScript switched
off. That is a lot of writing to keep behind a hash.

So each one gets a page. Not a new document type: the same caption, the same
description and the same country the other three surfaces already draw, laid out
once as a page and cross-linked back into all of them.

    /places                          every place, by country
    /places/uganda/where-the-nile-begins

Why not /uganda/bwindi. Three of the twenty-two countries are run by sister
companies and `/uganda` is their site, not ours — nesting under a path we do not
own would be a promise the routing cannot keep. `/places/` is the same shape for
all twenty-two, which matters more than being one segment shorter.

Nothing here is written by this file. Every page is a caption, a description, a
country and an operator that already existed, plus its own address.
"""

import html as html_mod
import json
import os
import re

from . import plate
from .model import ROOT, load_operators, load_regions, region_of

OUT = os.path.join(ROOT, "places")
ATLAS_DATA = os.path.join(ROOT, "data", "atlas")
SHAPES = os.path.join(ROOT, "tourism", "shapes.json")
LINKS = os.path.join(ROOT, "data", "links.json")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def read(path, fallback):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def slugify(text):
    """A caption becomes an address. Deterministic, so a page keeps its URL for
    as long as its caption does — and if a caption is edited the old address is
    gone, which is the honest consequence of naming a page after its content."""
    out = re.sub(r"[^a-z0-9]+", "-", (text or "").lower().replace("'", ""))
    return out.strip("-") or "place"


def slugs_for(pack):
    """Unique within a country.

    The payload already carries each place's address, computed by atlas.py from
    the same rule, so this reads it rather than deriving it a second time — two
    derivations of one address is one too many. The fallback is only for a
    payload written before that field existed.
    """
    seen, out = {}, {}
    for p in pack["places"]:
        if p.get("url"):
            out[p["id"]] = p["url"].rsplit("/", 1)[-1]
            continue
        base = slugify(p["title"])
        seen[base] = seen.get(base, 0) + 1
        out[p["id"]] = base if seen[base] == 1 else "%s-%d" % (base, seen[base])
    return out


# ---- one page --------------------------------------------------------------------


def hero(country, place, shape, tone):
    """The photograph, or the plate that stands in for it at the same size."""
    img = place.get("image") or {}
    if img.get("url"):
        return ('<figure class="pl-hero"><img src="%s" alt="%s" width="1600" height="900" '
                'fetchpriority="high" decoding="async" style="aspect-ratio:16/9">'
                '%s</figure>'
                % (esc(img["url"]), esc(img.get("alt") or place["text"]),
                   ('<figcaption>Photograph %s</figcaption>' % esc(img["credit"]))
                   if img.get("credit") else ""))
    art = ('<svg class="af-plate-shape" viewBox="0 0 %s %s" aria-hidden="true">'
           '<path d="%s"/></svg>' % (shape["w"], shape["h"], shape["d"])) if shape else ""
    return ('<figure class="pl-hero"><div class="af-plate af-plate--ground" '
            'style="aspect-ratio:16/9;--plate-tone:%s" aria-hidden="true">%s</div>'
            '<figcaption>No photograph for this one yet &mdash; the ground is '
            '%s&rsquo;s own region.</figcaption></figure>'
            % (esc(tone), art, esc(country.name)))


def page(country, place, pack, order, tax, ctx):
    lens_titles = ctx["lenses"]
    here = [p for p in pack["places"] if p["id"] != place["id"]]
    tone = plate.tone_for(country, ctx["regions"])
    key, reg = region_of(country, ctx["regions"])
    op = ctx["operators"].get(country.operator_key)
    mine = order[place["id"]]

    tags = "".join(
        '<a class="pl-tag" href="/atlas#/%s">%s</a>' % (esc(k), esc(lens_titles.get(k, k)))
        for k in (place.get("lenses") or []))

    siblings = "".join(
        '<li><a href="/places/%s/%s"><b>%s</b><span>%s</span></a></li>'
        % (esc(country.slug), esc(order[p["id"]]), esc(p["title"]), esc(p["group"]))
        for p in here[:12])

    # /places/<slug> is a folder of place pages with no index in it, so every one
    # of these was a 404 — four of them on each of 572 pages, in the block whose
    # entire job is "where to go next". /places#<slug> is that country's section
    # on the index, which is the list this link was always describing.
    near = "".join(
        '<a href="/places#%s"%s>%s<i>%s</i></a>'
        % (esc(r["to"]), ' data-border="true"' if any(
            w["kind"] == "border" for w in r["why"]) else "", esc(r["name"]),
           esc("%d km" % r["km"] if r.get("km") is not None else ""))
        for r in (ctx["links"].get(country.slug) or [])[:4])

    who = ('<div class="pl-who"><span class="af-stamp">Who would take you</span>'
           '<b>%s</b><p>%s &middot; %s</p>%s</div>'
           % (esc(op.name), esc(op.base), esc(op.line),
              ('<a class="af-go" href="%s">Open %s &rarr;</a>' % (esc(op.url), esc(op.name)))
              if op.url else "")) if op else (
           # "A licensed company based in <Country>" named a company that does
           # not exist. tourism/operators.json holds three and has only ever held
           # three; for the other nineteen there is no company here, licensed or
           # otherwise. What is true is that nobody of ours runs it.
           '<div class="pl-who pl-who--none"><span class="af-stamp">Who would take you</span>'
           '<b>Not us, in %s</b>'
           '<p>We run companies in three countries and %s is not one of them. '
           'It is written up here to the same twenty-seven categories as the '
           'rest &mdash; tell us the month and we will say who to ask.</p>'
           '<a class="af-go" href="/contact">Ask anyway &rarr;</a></div>'
           % (esc(country.name), esc(country.name)))

    title = "%s, %s" % (place["title"], country.name)
    return TEMPLATE % {
        "title": esc("%s — %s | Afrinkong" % (place["title"], country.name)),
        "description": esc(place["text"]),
        "og": plate.open_graph(esc(title), esc(place["text"]),
                               "/places/%s/%s" % (country.slug, mine), kind="article"),
        "country": esc(country.name),
        "slug": esc(country.slug),
        "regionKey": esc(key),
        "region": esc(country.region),
        "group": esc(place["group"]),
        "caption": esc(place["title"]),
        "text": esc(place["text"]),
        "hero": hero(country, place, ctx["shapes"].get(country.slug), tone),
        "tags": ('<div class="pl-tags"><span>Also across Africa</span>%s</div>' % tags)
                if tags else "",
        "tagline": esc(country.tagline),
        "siblings": siblings,
        "more": len(here),
        "who": who,
        "near": ('<div class="foot-next"><span>Next to %s</span>%s<p>Straight-line '
                 'distances between country centres. Solid names share a land '
                 'border with it.</p></div>' % (esc(country.name), near)) if near else "",
        "tone": esc(tone),
        "url": esc(country.url),
        "events": plate.events_block(),
        "explore": plate.explore_block(),
    }


# ---- the index -------------------------------------------------------------------


def index(rows, ctx):
    blocks = []
    for country, pack, order in rows:
        items = "".join(
            '<li><a href="/places/%s/%s">%s<i>%s</i></a></li>'
            % (esc(country.slug), esc(order[p["id"]]), esc(p["title"]), esc(p["group"]))
            for p in pack["places"])
        blocks.append(
            '<section class="pi-country" id="%s" style="--plate-tone:%s">'
            '<h2><a href="/places/%s/%s">%s</a><span>%s &middot; %d places</span></h2>'
            '<ul>%s</ul></section>'
            % (esc(country.slug), esc(plate.tone_for(country, ctx["regions"])),
               esc(country.slug), esc(order[pack["places"][0]["id"]]),
               esc(country.name), esc(country.region), len(pack["places"]), items))
    # Eighteen screens on a desktop and thirty-eight on a phone, with twenty-two
    # country sections in it and, until now, one in-page link. Somebody arriving
    # at /places#zimbabwe from a place page — which every one of the 572 does —
    # had no way to reach Zambia except to scroll back through nine countries.
    jump = "".join(
        '<a href="#%s">%s<i>%d</i></a>'
        % (esc(country.slug), esc(country.name), len(pack["places"]))
        for country, pack, _o in rows)
    total = sum(len(p["places"]) for _c, p, _o in rows)
    return INDEX % {"blocks": "\n".join(blocks), "n": total, "countries": len(rows),
                    "jump": ('<nav class="pi-jump" aria-label="Jump to a country">%s</nav>'
                             % jump),
                    "explore": plate.explore_block(),
                    "og": plate.open_graph("Every place — Afrinkong",
                                           "%d places across %d countries, each with its "
                                           "own page." % (total, len(rows)), "/places")}


def sitemap(rows, ctx):
    """Every real address on the site, so the 572 pages can be found at all.

    Hash states are shareable but not indexable; a page nobody can find is a page
    that may as well not exist, and this is a list of every one that can be.
    """
    base = "https://afrinkong.com"
    urls = ["/", "/atlas", "/journey", "/meet", "/stories", "/compare", "/contact",
            "/places",
            # /tourism is the hub every /tourism/<country> page hangs off and it
            # is linked from twenty-four footers; all twenty-two children were
            # listed and the parent was not.
            "/tourism",
            # The operator's own pages. They are substantial — a thousand words
            # each — they are real, and their titles say whose they are, so
            # leaving them out only meant the operator was unfindable while
            # their enquiry page was listed.
            "/about", "/pricing", "/services"]
    for country, pack, order in rows:
        if country.url.startswith("/"):
            urls.append(country.url)
        urls.append("/tourism/%s" % country.slug)
        urls.append("/portrait/%s" % country.slug)
        for p in pack["places"]:
            urls.append("/places/%s/%s" % (country.slug, order[p["id"]]))
    body = "".join("<url><loc>%s%s</loc></url>" % (base, esc(u)) for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n'
            % body), len(urls)


# ---- build -----------------------------------------------------------------------


def run(countries, taxonomy, log=print):
    from . import atlas as atlas_mod
    ctx = {
        "regions": load_regions(),
        "operators": load_operators(),
        "shapes": read(SHAPES, {}),
        "links": (read(LINKS, {}) or {}).get("links") or {},
        "lenses": {k: (v.get("title") or k)
                   for k, v in atlas_mod.load_lenses().items()},
    }
    rows, written = [], 0
    live = [c for c in countries if c.published]
    for country in live:
        pack = read(os.path.join(ATLAS_DATA, "%s.json" % country.slug), None)
        if not pack or not pack.get("places"):
            continue
        order = slugs_for(pack)
        rows.append((country, pack, order))
        folder = os.path.join(OUT, country.slug)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        keep = set()
        for p in pack["places"]:
            name = "%s.html" % order[p["id"]]
            keep.add(name)
            with open(os.path.join(folder, name), "w") as fh:
                fh.write(page(country, p, pack, order, taxonomy, ctx))
            written += 1
        # A caption that changes changes its address; the page at the old one has
        # to go, or the site accumulates orphans nobody will ever notice.
        for stale in os.listdir(folder):
            if stale.endswith(".html") and stale not in keep:
                os.remove(os.path.join(folder, stale))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    with open(os.path.join(OUT, "index.html"), "w") as fh:
        fh.write(index(rows, ctx))
    xml, n = sitemap(rows, ctx)
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as fh:
        fh.write(xml)

    size = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _dn, fn in os.walk(OUT) for f in fn)
    log("places: %d pages across %d countries (%.1f MB), plus /places and "
        "sitemap.xml with %d addresses"
        % (written, len(rows), size / 1048576.0, n))
    return written


CHROME = """<header class="pl-mast">
  <a class="pl-mark" href="/"><i>Afrinkong</i><b>%(country)s</b></a>
  <nav class="pl-routes" aria-label="Primary">
    <a href="/portrait/%(slug)s">Portrait</a>
    <a href="/atlas#/%(slug)s">The Atlas</a>
    <a href="/journey#/j/%(slug)s/">Build a journey</a>
    <a href="/places">Every place</a>
  </nav>
  <a class="af-btn af-btn--solid" href="/contact">Plan a journey<i>&rarr;</i></a>
</header>"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/places.css">
</head>
<body>
<a class="af-skip" href="#main">Skip to the place</a>
""" + CHROME + """

<main class="pl" id="main">
  <nav class="pl-where" aria-label="Where you are">
    <ol>
      <li><a href="/atlas">Africa</a></li>
      <li><a href="/atlas#/%(regionKey)s">%(region)s</a></li>
      <li><a href="/places#%(slug)s">%(country)s</a></li>
      <li><span aria-current="page">%(caption)s</span></li>
    </ol>
  </nav>

  <article class="pl-body">
    <span class="af-stamp">%(country)s &middot; %(group)s</span>
    <h1 class="pl-h1">%(caption)s</h1>
    <p class="pl-lede">%(text)s</p>
%(hero)s
    %(tags)s
    %(who)s
    <div class="pl-acts">
      <a class="af-btn af-btn--solid" href="/journey#/j/%(slug)s/">Build a journey here<i>&rarr;</i></a>
      <a class="af-btn af-btn--quiet" href="/portrait/%(slug)s">Read the portrait of %(country)s</a>
      <a class="af-btn af-btn--quiet" href="/atlas#/%(slug)s">Find %(country)s on the map</a>
      <a class="af-btn af-btn--quiet" href="%(url)s">All of %(country)s</a>
    </div>
  </article>

  <aside class="pl-more">
    <h2 class="pl-h2">%(more)s more in %(country)s</h2>
    <p class="pl-note">%(tagline)s</p>
    <ul class="pl-sibs">%(siblings)s</ul>
    <a class="af-go" href="/places#%(slug)s">Everything in %(country)s &rarr;</a>
  </aside>
</main>

%(events)s
%(explore)s
<script>
/* One event, on a page with nothing to interact with: that a place was opened,
   and which country it is in. No identifier, nothing about who, and nothing at
   all if the visitor has asked not to be counted. */
addEventListener('DOMContentLoaded',function(){
  if(window.AfrinkongEvents)window.AfrinkongEvents.track('place_page_opened',{country:'%(slug)s'});
});
</script>
<footer class="pl-foot" style="--plate-tone:%(tone)s">
  <div class="pl-foot-in">
    %(near)s
    <p class="pl-foot-bar"><a href="/">Afrinkong</a> &middot; %(country)s &middot;
      <a href="/places">every place</a> &middot;
      <a href="/contact">enquire</a></p>
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
<title>Every place &mdash; Afrinkong</title>
<meta name="description" content="Every place written up across twenty-two African countries, each with its own page.">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/places.css">
</head>
<body>
<a class="af-skip" href="#main">Skip to the list</a>
<header class="pl-mast">
  <a class="pl-mark" href="/"><i>Afrinkong</i><b>Every place</b></a>
  <nav class="pl-routes" aria-label="Primary">
    <a href="/stories">Stories</a>
    <a href="/atlas">The Atlas</a>
    <a href="/journey">Build a journey</a>
    <a href="/meet">Meet Africa</a>
  </nav>
  <a class="af-btn af-btn--solid" href="/contact">Plan a journey<i>&rarr;</i></a>
</header>

<main class="pi" id="main">
  <section class="pi-open">
    <span class="af-stamp">The index</span>
    <h1 class="pi-h1">%(n)d places.<br>%(countries)d countries.</h1>
    <p class="pi-lede">Everything written up on this site, each with an address of
      its own. The atlas will fly you to any of them and the journey engine will
      put them in an order; this is the plain list, which is the one a search
      engine can read and the one that works with nothing switched on.</p>
  </section>
%(jump)s
%(blocks)s
</main>
%(explore)s
</body>
</html>
"""
