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
import os

from . import imaging
from .model import ROOT

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


def build(country, taxonomy):
    """-> the full HTML for one country's home page."""
    def entry(cat_id):
        return country.entry(cat_id)

    hero = entry("hero")
    hero_pic = picture(hero, taxonomy.role("hero")) if hero else ""

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
    for title, ids in GROUPS:
        rows = []
        for cid in ids:
            e = entry(cid)
            if not e or not e.caption:
                continue
            rows.append('        <li><b>%s</b><span>%s</span></li>' % (esc(e.caption), esc(e.subject or "")))
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
        "hero_pic": hero_pic or "",
        "hero_class": " has-pic" if hero_pic else " no-pic",
        "highlights": "\n".join(highlights),
        "reasons": "\n".join(reasons),
        "groups": "\n".join(groups),
        "count": len(taxonomy.enabled),
        "resolved": resolved,
    }


# Cameroon and Uganda are skipped: both already have a better home page than
# this generator can make. Cameroon's is hand-built at cameroon.html, and
# Uganda has a whole operator site of its own at Pearl Trails Uganda. A
# generated page would be a second, poorer front door to each.
def write_all(countries, taxonomy, skip=("cameroon", "uganda"), out_dir=None, log=print):
    out_dir = out_dir or ROOT
    written = []
    for c in countries:
        if c.slug in skip or not c.published:
            continue
        path = os.path.join(out_dir, "%s.html" % c.slug)
        with open(path, "w") as f:
            f.write(build(c, taxonomy))
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
<style>
:root{
  --c-bg:#F7F2E7;--c-primary:#1C2A25;--c-accent:#BE5527;--c-ink:#1F211C;
  --c-muted:#6E7166;--c-border:#DDD4C1;
  --dust:color-mix(in srgb,var(--c-bg) 88%%,var(--c-primary));
  --basalt:color-mix(in srgb,var(--c-primary) 95%%,#000);
  --onbasalt:color-mix(in srgb,var(--c-bg) 88%%,var(--c-primary));
  --onbasalt-dim:color-mix(in srgb,var(--c-bg) 62%%,var(--c-primary));
  --rule:1px solid var(--c-border);
  --rule-dark:1px solid color-mix(in srgb,var(--c-bg) 20%%,transparent);
  --display:"Archivo Narrow","Roboto Condensed","Arial Narrow",Arial,sans-serif;
  --text:Charter,"Iowan Old Style","Source Serif Pro",Palatino,Georgia,serif;
  --mono:"IBM Plex Mono","SFMono-Regular",Menlo,Consolas,monospace;
  color-scheme:light;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--text);background:var(--c-bg);color:var(--c-ink);line-height:1.66;font-size:17px;-webkit-font-smoothing:antialiased}
img{max-width:100%%;display:block}
a{color:inherit;text-decoration:none}
h1,h2,h3{font-family:var(--display);font-weight:700;line-height:1.02;letter-spacing:-.01em;text-transform:uppercase;text-wrap:balance}
ul{list-style:none}
::selection{background:var(--c-accent);color:var(--c-bg)}
.frame{max-width:1240px;margin:0 auto;padding:0 44px}
.stamp{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.26em;text-transform:uppercase;color:var(--c-accent)}
.note{margin-top:16px;color:var(--c-muted);max-width:44em}

.mast{position:sticky;top:0;z-index:70;background:var(--c-bg);border-bottom:2px solid var(--c-primary)}
.mast-in{display:flex;align-items:center;gap:34px;padding:14px 0}
.mark{margin-right:auto;display:flex;flex-direction:column;gap:3px}
.mark b{font-family:var(--display);font-size:26px;font-weight:700;text-transform:uppercase;line-height:1;white-space:nowrap}
.mark span{font-family:var(--mono);font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--c-muted);white-space:nowrap}
.routes{display:flex;gap:26px}
.routes a{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;white-space:nowrap;color:var(--c-muted);padding:4px 0;border-bottom:2px solid transparent;transition:color .2s,border-color .2s}
.routes a:hover{color:var(--c-primary);border-color:var(--c-accent)}
.btn{font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--c-bg);background:var(--c-primary);padding:12px 20px;transition:background .2s}
.btn:hover{background:var(--c-accent)}
@media(max-width:1010px){.routes{display:none}}
@media(max-width:560px){.frame{padding:0 20px}.mark b{font-size:20px}.btn{padding:10px 14px;font-size:10px;letter-spacing:.12em}}

.open{padding:78px 0 62px;border-bottom:var(--rule)}
.open-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:56px;align-items:end}
.open-grid.no-pic{grid-template-columns:1fr;max-width:34em}
.open h1{font-size:clamp(34px,4.4vw,64px);margin:20px 0 0}
.open h1 em{font-style:normal;color:var(--c-accent)}
.lede{font-size:19px;color:var(--c-muted);margin-top:22px;max-width:40em}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:32px}
.act{display:inline-block;font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;padding:12px 20px;border:1px solid var(--c-primary);transition:background .2s,color .2s}
.act i{font-style:normal;margin-left:9px}
.act.go{background:var(--c-primary);color:var(--c-bg)}
.act.go:hover{background:var(--c-accent);border-color:var(--c-accent)}
.act.faint{border-color:var(--c-border);color:var(--c-muted)}
.act.faint:hover{border-color:var(--c-primary);color:var(--c-primary)}
.open-plate .ct-shot img{width:100%%;aspect-ratio:4/5;object-fit:cover}
.key{display:grid;grid-template-columns:repeat(3,1fr);margin-top:52px;border-top:2px solid var(--c-primary)}
.key div{padding:18px 22px 0 0}
.key b{display:block;font-family:var(--display);font-size:29px;font-weight:700;color:var(--c-primary)}
.key span{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-muted);margin-top:7px}
@media(max-width:940px){.open{padding:52px 0 44px}.open-grid{grid-template-columns:1fr;gap:34px;align-items:start}.open-plate .ct-shot img{aspect-ratio:4/3}}
@media(max-width:520px){.key{grid-template-columns:1fr}.key div{padding:14px 0 12px;border-bottom:var(--rule)}}

.zone{padding:84px 0}
.zone.dust{background:var(--dust)}
.zone.basalt{background:var(--basalt);color:var(--onbasalt)}
.zone.basalt h2,.zone.basalt h3{color:var(--c-bg)}
.zone.basalt .note,.zone.basalt p{color:var(--onbasalt-dim)}
.head{display:grid;grid-template-columns:150px 1fr;gap:40px;align-items:start;margin-bottom:44px}
.head-no{border-top:2px solid var(--c-accent);padding-top:12px}
.head-no b{display:block;font-family:var(--display);font-size:38px;font-weight:700;line-height:1;color:var(--c-accent)}
.head-no span{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--c-muted);margin-top:8px}
.zone.basalt .head-no span{color:var(--onbasalt-dim)}
.head h2{font-size:clamp(29px,3.8vw,50px);max-width:24ch}
.head h2 em{font-style:normal;color:var(--c-accent)}
@media(max-width:880px){.zone{padding:60px 0}.head{grid-template-columns:1fr;gap:18px;margin-bottom:32px}}

.highs{display:grid;grid-template-columns:repeat(3,1fr);gap:34px 32px}
.ct-high b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent)}
.ct-high h3{font-size:22px;margin:8px 0 8px}
.ct-high p{font-size:15px;color:var(--c-muted)}
.ct-high .ct-shot{display:block;margin-bottom:16px}
.ct-high .ct-shot img{width:100%%;aspect-ratio:4/3;object-fit:cover}
@media(max-width:900px){.highs{grid-template-columns:1fr 1fr;gap:28px 24px}}
@media(max-width:560px){.highs{grid-template-columns:1fr}}

.groups{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:2px solid var(--c-primary)}
.ct-group{padding:24px 26px 20px 0;border-right:var(--rule);border-bottom:var(--rule)}
.ct-group>b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent);margin-bottom:14px}
.ct-group li{padding:9px 0;border-bottom:var(--rule)}
.ct-group li:last-child{border-bottom:0}
.ct-group li b{display:block;font-family:var(--display);font-size:16px;font-weight:700;text-transform:uppercase}
.ct-group li span{display:block;font-size:13.5px;color:var(--c-muted);margin-top:2px}
@media(max-width:900px){.groups{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.groups{grid-template-columns:1fr}.ct-group{border-right:0;padding-right:0}}

.reasons{display:grid;grid-template-columns:repeat(2,1fr);gap:0;border-top:2px solid var(--c-accent)}
.ct-reason{padding:28px 34px 24px 0}
.ct-reason b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--c-accent);margin-bottom:10px}
.ct-reason h3{font-size:24px;margin-bottom:10px}
.ct-reason p{font-size:15px}
@media(max-width:760px){.reasons{grid-template-columns:1fr}}

.end{text-align:center;padding:92px 0}
.end h2{font-size:clamp(30px,4.6vw,60px)}
.end h2 em{font-style:normal;color:var(--c-accent)}
.end p{margin:16px auto 0;max-width:46ch;color:var(--c-muted)}
.end .acts{justify-content:center}

.foot{background:var(--basalt);color:var(--onbasalt);padding:56px 0 0}
.foot-grid{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:40px}
.foot-brand{font-family:var(--display);font-size:26px;font-weight:700;text-transform:uppercase;color:var(--c-bg)}
.foot-brand span{display:block;font-family:var(--mono);font-size:9.5px;font-weight:400;letter-spacing:.28em;color:var(--c-accent);margin-top:7px}
.foot-grid p{margin-top:14px;font-size:14.5px;max-width:32em;color:var(--onbasalt-dim)}
.foot-col b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--c-accent);margin-bottom:12px;font-weight:400}
.foot-col a,.foot-col span{display:block;font-size:14.5px;padding:5px 0;color:var(--onbasalt-dim)}
.foot-col a:hover{color:var(--c-bg)}
.foot-bar{margin-top:40px;padding:20px 0;border-top:var(--rule-dark);font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--onbasalt-dim)}
.foot-bar a{border-bottom:1px solid var(--c-accent)}
@media(max-width:820px){.foot-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition-duration:.001ms !important}}
</style>
</head>
<body>
<header class="mast">
  <div class="frame mast-in">
    <a class="mark" href="/%(slug)s"><b>%(name)s</b><span>%(tagline)s</span></a>
    <nav class="routes">
      <a href="#highlights">Highlights</a>
      <a href="#experiences">Experiences</a>
      <a href="#why">Why go</a>
      <a href="/tourism/%(slug)s">All %(count)d</a>
    </nav>
    <a class="btn" href="/contact">Plan a journey</a>
  </div>
</header>

<section class="open">
  <div class="frame">
    <div class="open-grid%(hero_class)s">
      <div>
        <span class="stamp">%(region)s</span>
        <h1>%(name)s. <em>%(tagline)s</em>.</h1>
        <p class="lede">%(summary)s</p>
        <div class="acts">
          <a class="act go" href="/contact">Plan a journey <i>&rarr;</i></a>
          <a class="act faint" href="#experiences">What you can do here <i>&rarr;</i></a>
        </div>
      </div>
      <div class="open-plate">%(hero_pic)s</div>
    </div>
    <div class="key">
      <div><b>%(count)d</b><span>Kinds of experience</span></div>
      <div><b>%(region)s</b><span>Where it sits</span></div>
      <div><b>Local</b><span>Guides, vehicles and permits</span></div>
    </div>
  </div>
</section>

<section class="zone" id="highlights">
  <div class="frame">
    <div class="head">
      <div class="head-no"><b>01</b><span>Highlights</span></div>
      <div>
        <h2>What %(name)s is <em>known for</em>.</h2>
        <p class="note">Six of the twenty-seven, and the ones most people come for. The rest are below &mdash; and none of them is filler.</p>
      </div>
    </div>
    <div class="highs">
%(highlights)s
    </div>
  </div>
</section>

<section class="zone dust" id="experiences">
  <div class="frame">
    <div class="head">
      <div class="head-no"><b>02</b><span>Experiences</span></div>
      <div>
        <h2>Twenty-seven ways to <em>spend the time</em>.</h2>
        <p class="note">Every country we cover works through the same twenty-seven categories, so you can hold two of them side by side and compare like with like rather than one brochure against another.</p>
      </div>
    </div>
    <div class="groups">
%(groups)s
    </div>
  </div>
</section>

<section class="zone basalt" id="why">
  <div class="frame">
    <div class="head">
      <div class="head-no"><b>03</b><span>Why go</span></div>
      <div>
        <h2>The case for <em>%(name)s</em>.</h2>
      </div>
    </div>
    <div class="reasons">
%(reasons)s
    </div>
  </div>
</section>

<section class="zone">
  <div class="frame end">
    <span class="stamp">Begin</span>
    <h2>Your %(name)s <em>starts here</em>.</h2>
    <p>Tell us the month, or simply the thing you want to see, and a guide who works there will answer.</p>
    <div class="acts">
      <a class="act go" href="/contact">Plan a journey <i>&rarr;</i></a>
      <a class="act faint" href="/tourism/%(slug)s">See all %(count)d experiences <i>&rarr;</i></a>
    </div>
  </div>
</section>

<footer class="foot">
  <div class="frame">
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
