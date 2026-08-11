"""Generate the country tourism pages.

The design system is not re-implemented here. The masthead, the footer, the token
block and the reveal script are lifted out of index.html at render time, so these
pages cannot drift from the rest of the site: change a token on the home page and
every country page follows.

Output is plain static HTML — tourism/<slug>.html — which vercel.json's cleanUrls
serves at /tourism/<slug>. No build step is introduced for the deployed site.
"""

import html
import os
import re

from . import imaging, validate
from .resolve import MISSING_KEY_WARNING
from .model import ROOT

OUT_DIR = os.path.join(ROOT, "tourism")

# The 27 categories, grouped into the page's narrative sections.
#
# A category's role in categories.json is its *canonical* shape — it drives which
# orientation the resolver searches for and how the photo is judged suitable. The
# shape it is *delivered* at is decided here, by the section, because the same
# photograph legitimately appears as a 21:9 band on one page and a 4:3 tile on
# another. Mixing canonical roles inside one grid is what produces a ragged wall
# of different-height tiles, so a grid delivers every tile at one role.
#
# layout: "band"     full-bleed panoramic
#         "lead"     first item as a large 16:9 feature row, remainder as cards
#         "cards"    uniform 4:3 grid
SECTIONS = [
    ("hero", "band", None, None, ["hero"]),
    ("destinations", "cards", "Featured destinations", "Where the country actually takes you.",
     ["nature", "mountains", "waterfalls", "lakes-rivers", "beaches", "forests"]),
    ("wildlife", "lead", "Wildlife & safari", "What lives here, and how you see it without disturbing it.",
     ["wildlife", "safari", "eco-tourism"]),
    ("culture", "lead", "Culture & heritage", "The part of a country you cannot photograph from a vehicle.",
     ["culture", "traditional-people", "food", "festivals", "crafts", "historic-sites", "heritage"]),
    ("cities", "cards", "Cities & everyday life", "Where people actually live between the landmarks.",
     ["cities", "architecture", "local-life", "family-community"]),
    ("adventure", "lead", "Adventure & outdoors", "For travellers who would rather walk it than watch it.",
     ["adventure", "outdoor", "luxury"]),
    ("inspiration", "cards", "Travel inspiration", "The frames people come home with.",
     ["photography", "hidden-gems"]),
    ("why", "band", None, None, ["why-visit"]),
]


def esc(s):
    return html.escape(s or "", quote=True)


# ---- design system extraction --------------------------------------------------


def _between(src, start_pat, end_pat):
    m = re.search(start_pat + r"(.*?)" + end_pat, src, re.S)
    return m.group(0) if m else ""


class Shell:
    """The site's own chrome, read off index.html."""

    def __init__(self, index_path=None):
        with open(index_path or os.path.join(ROOT, "index.html")) as f:
            src = f.read()
        self.style = _between(src, r"<style>", r"</style>")
        self.masthead = _between(src, r'<header class="fj-mast">', r"</header>")
        self.footer = _between(src, r'<footer class="fj-foot">', r"</footer>")
        self.script = _between(src, r"<script>", r"</script>")
        if not (self.style and self.masthead and self.footer):
            raise RuntimeError("could not read the shell out of index.html")
        # the masthead CTA jumps to an on-page form that country pages do not have
        self.masthead = self.masthead.replace('href="#quote"', 'href="/contact"')


TOURISM_CSS = """
/* ---- tourism country pages -------------------------------------------------- */
.tq-hero{position:relative;background:var(--fj-basalt);color:var(--fj-onphoto)}
.tq-hero-pic{position:absolute;inset:0;overflow:hidden}
.tq-hero-pic img{width:100%;height:100%;object-fit:cover}
.tq-hero-scrim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,19,16,.22),rgba(20,19,16,.72))}
.tq-hero-in{position:relative;padding:132px 0 56px;min-height:clamp(440px,66vh,760px);display:flex;flex-direction:column;justify-content:flex-end}
.tq-hero h1{font-size:clamp(42px,7vw,88px);color:var(--fj-onphoto);max-width:14em}
.tq-hero .tq-lede{margin-top:18px;max-width:38em;color:var(--fj-onphoto-soft);font-size:19px}
.tq-hero .fj-stamp{color:var(--fj-onphoto-dim);margin-bottom:18px}
.tq-facts{display:flex;flex-wrap:wrap;gap:34px;margin-top:34px;padding-top:22px;border-top:var(--fj-rule-dark)}
.tq-facts div b{display:block;font-family:var(--fj-display);font-size:24px;letter-spacing:.01em}
.tq-facts div span{font-family:var(--fj-mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--fj-onphoto-dim)}

.tq-sec{padding:84px 0;border-bottom:var(--fj-rule)}
.tq-sec-head{display:grid;grid-template-columns:150px 1fr;gap:30px;margin-bottom:44px;align-items:start}
.tq-sec-head .tq-no{font-family:var(--fj-display);font-size:34px;color:var(--c-accent);line-height:1}
.tq-sec-head h2{font-size:clamp(26px,3.4vw,42px);max-width:16em}
.tq-sec-head p{margin-top:12px;color:var(--c-muted);max-width:40em}

.tq-grid{display:grid;gap:26px}
.tq-grid.cols-3{grid-template-columns:repeat(3,1fr)}
.tq-grid.cols-2{grid-template-columns:repeat(2,1fr)}
.tq-item{display:flex;flex-direction:column}
.tq-item figure{margin:0;position:relative;overflow:hidden;background:var(--fj-dust)}
.tq-item img{width:100%;height:100%;display:block;object-fit:cover}
.tq-item h3{margin-top:14px;font-size:17px;letter-spacing:.02em}
.tq-item p{margin-top:6px;color:var(--c-muted);font-size:15px}
.tq-tag{position:absolute;left:0;bottom:0;background:var(--fj-basalt);color:var(--fj-onphoto);
  font-family:var(--fj-mono);font-size:9px;letter-spacing:.2em;text-transform:uppercase;padding:7px 11px}

.tq-feature{display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:center;margin-bottom:34px}
.tq-feature:nth-child(even) .tq-feature-txt{order:-1}
.tq-feature figure{margin:0;overflow:hidden;background:var(--fj-dust)}
.tq-feature img{width:100%;height:100%;object-fit:cover;display:block}
.tq-feature h3{font-size:clamp(22px,2.6vw,30px)}
.tq-feature p{margin-top:12px;color:var(--c-muted)}

.tq-band{position:relative;overflow:hidden;background:var(--fj-basalt)}
.tq-band img{width:100%;display:block;object-fit:cover}
.tq-band-txt{position:absolute;inset:auto 0 0 0;padding:44px 0;
  background:linear-gradient(180deg,rgba(20,19,16,0),rgba(20,19,16,.78))}
.tq-band-txt h3{color:var(--fj-onphoto);font-size:clamp(24px,3.4vw,40px)}
.tq-band-txt p{color:var(--fj-onphoto-soft);max-width:40em;margin-top:10px}

.tq-hero-pic .tq-empty{width:100%;height:100%;aspect-ratio:auto;align-items:flex-start;
  justify-content:flex-end;padding:100px 28px 0;background:var(--fj-basalt);border:0;
  color:var(--fj-onphoto-dim)}
.tq-empty em{display:block;margin-top:8px;font-style:normal;text-transform:none;
  letter-spacing:.02em;font-family:var(--fj-text);font-size:13px;opacity:.75}
.tq-empty{display:flex;align-items:center;justify-content:center;background:var(--fj-raffia);
  border:1px dashed var(--c-border);color:var(--c-muted);font-family:var(--fj-mono);
  font-size:10px;letter-spacing:.18em;text-transform:uppercase;text-align:center;padding:20px}
.tq-credit{margin-top:6px;font-family:var(--fj-mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--c-muted)}
.tq-credit a{border-bottom:1px solid var(--c-border)}

.tq-cta{padding:84px 0;text-align:center}
.tq-cta h2{font-size:clamp(28px,4vw,54px);max-width:16em;margin:0 auto}
.tq-cta p{margin:16px auto 0;color:var(--c-muted);max-width:40em}
.tq-cta .btn{margin-top:28px;display:inline-block}

.tq-countries{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
.tq-countries a{display:block}
.tq-countries figure{margin:0;overflow:hidden;background:var(--fj-dust)}
.tq-countries img{width:100%;height:100%;object-fit:cover;display:block}
.tq-countries h3{margin-top:12px;font-size:19px}
.tq-countries p{color:var(--c-muted);font-size:15px;margin-top:4px}

@media(max-width:1000px){
  .tq-grid.cols-3{grid-template-columns:repeat(2,1fr)}
  .tq-countries{grid-template-columns:repeat(2,1fr)}
  .tq-feature{grid-template-columns:1fr;gap:22px}
  .tq-feature:nth-child(even) .tq-feature-txt{order:0}
  .tq-sec-head{grid-template-columns:1fr;gap:10px}
}
@media(max-width:640px){
  .tq-grid.cols-3,.tq-grid.cols-2,.tq-countries{grid-template-columns:1fr}
  .tq-sec{padding:56px 0}
  .tq-hero-in{padding:96px 0 40px;min-height:clamp(380px,60vh,620px)}
}
@media(prefers-reduced-motion:reduce){.fj-rise{transition:none}}
"""


# ---- image markup --------------------------------------------------------------


def img_tag(entry, role, alt, extra_class=""):
    d = imaging.delivery(entry, role)
    box = 'width="%d" height="%d" style="aspect-ratio:%s;object-position:%s"' % (
        d["width"], d["height"], d["aspect"], d["objectPosition"])
    if not d["src"]:
        # No resolved photo and no local stand-in. Show an honest placeholder that
        # names the missing prerequisite, rather than a broken <img> or a guess.
        return ('<div class="tq-empty %s" style="aspect-ratio:%s" data-unresolved="true">'
                '<span>%s<br><em>%s</em></span></div>'
                % (extra_class, d["aspect"], esc(MISSING_KEY_WARNING), esc(alt[:70])))
    attrs = ['src="%s"' % esc(d["src"]), 'alt="%s"' % esc(alt), box]
    if d["srcset"]:
        attrs.append('srcset="%s"' % esc(d["srcset"]))
        attrs.append('sizes="%s"' % esc(d["sizes"]))
    if d["priority"]:
        attrs.append('fetchpriority="high"')
        attrs.append('decoding="async"')
    else:
        attrs.append('loading="lazy"')
        attrs.append('decoding="async"')
    if extra_class:
        attrs.append('class="%s"' % extra_class)
    return "<img " + " ".join(attrs) + ">"


def credit(entry):
    if not entry.image:
        return ""
    name = entry.image.get("photographer")
    link = entry.image.get("unsplashUrl") or entry.image.get("photographerUrl")
    if not name:
        return ""
    who = '<a href="%s" rel="nofollow noopener">%s</a>' % (esc(link), esc(name)) if link else esc(name)
    return '<p class="tq-credit">Photo %s / Unsplash</p>' % who


# ---- sections ------------------------------------------------------------------


def render_hero(country, entry, cat, taxonomy):
    role = taxonomy.role(cat["id"])
    alt = validate.alt_text(country, entry)
    facts = [
        (country.region or "Africa", "Region"),
        ("27", "Tourism experiences"),
        (country.tagline or "Guided travel", "Known for"),
    ]
    return """
<section class="tq-hero" data-category="hero">
  <div class="tq-hero-pic">%s<div class="tq-hero-scrim"></div></div>
  <div class="fj-frame tq-hero-in">
    <span class="fj-stamp">%s <i>&middot; Tourism</i></span>
    <h1>%s</h1>
    <p class="tq-lede">%s</p>
    <div class="tq-facts">%s</div>
  </div>
</section>""" % (
        img_tag(entry, role, alt),
        esc(country.name.upper()),
        esc(entry.caption),
        esc(country.summary or entry.description),
        "".join("<div><b>%s</b><span>%s</span></div>" % (esc(v), esc(k)) for v, k in facts),
    )


def render_cards(country, items, taxonomy, cols=3):
    out = []
    role = taxonomy.roles["card"]          # one shape for the whole grid
    for cat, entry in items:
        alt = validate.alt_text(country, entry)
        out.append("""
      <article class="tq-item fj-rise" data-category="%s">
        <figure>%s<span class="tq-tag">%s</span></figure>
        <h3>%s</h3>
        <p>%s</p>%s
      </article>""" % (
            esc(cat["id"]), img_tag(entry, role, alt), esc(cat["title"]),
            esc(entry.caption), esc(entry.description), credit(entry)))
    return '<div class="tq-grid cols-%d">%s\n    </div>' % (cols, "".join(out))


def render_features(country, items, taxonomy):
    out = []
    role = taxonomy.roles["feature"]
    for cat, entry in items:
        alt = validate.alt_text(country, entry)
        out.append("""
      <div class="tq-feature fj-rise" data-category="%s">
        <figure>%s</figure>
        <div class="tq-feature-txt">
          <span class="fj-stamp">%s</span>
          <h3>%s</h3>
          <p>%s</p>%s
        </div>
      </div>""" % (esc(cat["id"]), img_tag(entry, role, alt), esc(cat["title"]),
                   esc(entry.caption), esc(entry.description), credit(entry)))
    return "".join(out)


def render_band(country, cat, entry, taxonomy, role_name=None):
    role = taxonomy.roles[role_name] if role_name else taxonomy.role(cat["id"])
    alt = validate.alt_text(country, entry)
    return """
<section class="tq-band" data-category="%s">
  %s
  <div class="tq-band-txt"><div class="fj-frame">
    <span class="fj-stamp">%s</span>
    <h3>%s</h3><p>%s</p>
  </div></div>
</section>""" % (esc(cat["id"]), img_tag(entry, role, alt), esc(cat["title"]),
                 esc(entry.caption), esc(entry.description))


def render_section(country, taxonomy, index, layout, title, blurb, ids):
    items = []
    for cid in ids:
        cat = taxonomy.by_id.get(cid)
        if not cat or not cat.get("enabled", True):
            continue
        entry = country.entry(cid)
        if entry:
            items.append((cat, entry))
    if not items:
        return ""
    if layout == "lead" and len(items) > 1:
        body = render_features(country, items[:1], taxonomy) + render_cards(
            country, items[1:], taxonomy, cols=3 if len(items) > 3 else 2)
    elif layout == "lead":
        body = render_features(country, items, taxonomy)
    else:
        body = render_cards(country, items, taxonomy, cols=3 if len(items) > 2 else 2)
    return """
<section class="tq-sec">
  <div class="fj-frame">
    <div class="tq-sec-head">
      <div><span class="tq-no">%02d</span></div>
      <div><h2>%s</h2><p>%s</p></div>
    </div>
    %s
  </div>
</section>""" % (index, esc(title), esc(blurb), body)


# ---- pages ---------------------------------------------------------------------


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="preconnect" href="https://images.unsplash.com" crossorigin>
<style>%(style)s
%(tourism_css)s</style>
</head>
<body>
%(masthead)s
%(body)s
%(footer)s
<script>%(script)s</script>
</body>
</html>
"""


def render_country(country, taxonomy, shell):
    parts = []
    n = 0
    for key, layout, title, blurb, ids in SECTIONS:
        if key == "hero":
            cat, entry = taxonomy.by_id["hero"], country.entry("hero")
            if entry:
                parts.append(render_hero(country, entry, cat, taxonomy))
            continue
        if key == "why":
            cat, entry = taxonomy.by_id["why-visit"], country.entry("why-visit")
            if entry:
                parts.append(render_band(country, cat, entry, taxonomy, "panoramic"))
                parts.append("""
<section class="tq-cta">
  <div class="fj-frame">
    <h2>%s</h2>
    <p>%s</p>
    <a class="btn" href="/contact">Plan a circuit</a>
  </div>
</section>""" % (esc(entry.caption), esc(entry.description)))
            continue
        n += 1
        parts.append(render_section(country, taxonomy, n, layout, title, blurb, ids))

    hero = country.entry("hero")
    return PAGE % {
        "title": esc("%s Tourism — 27 Experiences | Fako Journeys" % country.name),
        "description": esc(country.summary or (hero.description if hero else country.name)),
        "style": shell.style.replace("<style>", "").replace("</style>", ""),
        "tourism_css": TOURISM_CSS,
        "masthead": shell.masthead,
        "body": "\n".join(parts),
        "footer": shell.footer,
        "script": shell.script.replace("<script>", "").replace("</script>", ""),
    }


def render_index(countries, taxonomy, shell):
    cards = []
    for c in countries:
        entry = c.entry("hero")
        if not entry:
            continue
        role = taxonomy.roles["card"]
        alt = validate.alt_text(c, entry)
        cards.append("""
      <a href="/tourism/%s" class="fj-rise">
        <figure>%s</figure>
        <h3>%s</h3>
        <p>%s</p>
      </a>""" % (esc(c.slug), img_tag(entry, role, alt), esc(c.name), esc(c.tagline)))
    body = """
<section class="fj-open">
  <div class="fj-frame">
    <span class="fj-stamp">Tourism <i>&middot; by country</i></span>
    <h1 style="font-size:clamp(38px,6vw,74px);margin-top:16px">Every country, twenty-seven ways in.</h1>
    <p class="fj-lede" style="margin-top:18px">Each country below is described through the same
      twenty-seven tourism experiences, so you can compare them like for like.</p>
  </div>
</section>
<section class="tq-sec">
  <div class="fj-frame">
    <div class="tq-countries">%s
    </div>
  </div>
</section>""" % "".join(cards)
    return PAGE % {
        "title": "Tourism by Country | Fako Journeys",
        "description": "Country tourism guides, each covering the same 27 travel experiences.",
        "style": shell.style.replace("<style>", "").replace("</style>", ""),
        "tourism_css": TOURISM_CSS,
        "masthead": shell.masthead,
        "body": body,
        "footer": shell.footer,
        "script": shell.script.replace("<script>", "").replace("</script>", ""),
    }


def write_all(countries, taxonomy, publishable=None, out_dir=None):
    """Write a page per country plus the index. Countries that failed validation
    are skipped — incomplete tourism data does not get published."""
    shell = Shell()
    out = out_dir or OUT_DIR
    os.makedirs(out, exist_ok=True)
    written = []
    ok = [c for c in countries if c.published and (publishable is None or c.slug in publishable)]
    for c in ok:
        path = os.path.join(out, c.slug + ".html")
        with open(path, "w") as f:
            f.write(render_country(c, taxonomy, shell))
        written.append(path)
    path = os.path.join(out, "index.html")
    with open(path, "w") as f:
        f.write(render_index(ok, taxonomy, shell))
    written.append(path)
    return written
