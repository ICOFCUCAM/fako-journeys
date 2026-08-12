"""Put the resolved photographs on the main site, not just the tourism pages.

The five hand-written pages — home, services, pricing, about, contact — were
built against the SVG illustrations, because when they were written there was no
network and no photo source. The illustrations were always a stand-in. The real
photographs have been arriving into tourism/cache/images.json, but only the
generated /tourism/<country> pages consume them, so the site a visitor lands on
still shows drawings.

This bridges the two. Each Cameroon category names the illustration it stands in
for (`local` in the country dataset), which gives an exact mapping from every
illustration on the main site to the photograph that replaced it. The mapping is
tight because the Cameroon subjects were written *from* those illustrations:
"villagers and guides repairing a stone section of mountain trail" is both the
family-community subject and the trail-repair drawing.

    python3 tools/tourism/build.py adopt              # rewrite the five pages
    python3 tools/tourism/build.py adopt --revert     # back to the illustrations

Rules it follows:

  * alt text comes from the photograph, not the drawing. If the resolved photo
    is a waterfall in Cameroon rather than specifically the Lobe falls, the page
    must not claim otherwise.
  * the illustration is remembered in data-illustration, so a slot can be put
    back, re-pointed at a better photo later, or fall back if a photo is dropped.
  * a slot with no resolved photo keeps its drawing. Nothing is left broken.
  * an <img data-locked="true"> is never touched, by adopt or by revert: it is
    artwork somebody chose, not a slot for a search result. The same goes for
    data-placed="true", which `place` sets on a generated or uploaded picture
    somebody selected from the contact sheet — use `place --revert` to undo
    those, so the two tools never fight over the same slot.
  * idempotent: running it twice changes nothing the second time.
"""

import os
import re

from . import cache as cache_mod
from . import imaging
from .model import ROOT, attach_cache, load_countries, load_taxonomy

# The site root is WankonAfritour, the group's continental gateway; the Kamerun
# pages hang off cameroon.html. Only these five carry photograph slots — the
# gateway is deliberately typographic, so it has none to manage.
PAGES = ("cameroon.html", "services.html", "about.html", "contact.html", "pricing.html")

# These are not the tourism taxonomy roles. They are the shapes the five
# hand-written pages already impose in their own CSS:
#
#   .fj-open-plate img { aspect-ratio: 3/4 }      .fj-slip-pic  img { 5/4 }
#   .fj-craft-pic  img { aspect-ratio: 4/5 }      .fj-cal-col   img { 4/5 }
#   .fj-crew-card  img { aspect-ratio: 1/1 }      .fj-vista/seam: height:100%
#
# Delivering a taxonomy role instead means the CDN crops to one shape and CSS
# then crops that to another — the picture arrives the wrong shape, gets cut a
# second time, and the page looks off. So each slot is delivered at exactly the
# ratio its own stylesheet asks for, and the width/height attributes agree with
# it, which is what keeps the box reserved correctly.
#
# `sizes` is computed from the real layout: .fj-frame is 1240px with 44px
# padding, so the content column is 1152px, divided by that slot's grid.
SLOT_SPECS = (
    ("fj-vista-pic",  {"aspect": [16, 9], "width": 2400, "srcset": [1200, 1800, 2400, 3000],
                       "sizes": "100vw", "quality": 82, "box": False}),
    ("fj-seam-pic",   {"aspect": [16, 9], "width": 2400, "srcset": [1200, 1800, 2400, 3000],
                       "sizes": "100vw", "quality": 82, "box": False}),
    ("fj-open-plate", {"aspect": [3, 4], "width": 960, "srcset": [480, 720, 960, 1440],
                       "sizes": "(min-width: 1240px) 480px, (min-width: 940px) 40vw, 92vw",
                       "quality": 82}),
    ("fj-slip-pic",   {"aspect": [5, 4], "width": 1000, "srcset": [500, 750, 1000, 1500],
                       "sizes": "(min-width: 1240px) 500px, (min-width: 900px) 45vw, 92vw",
                       "quality": 82}),
    ("fj-craft-pic",  {"aspect": [4, 5], "width": 880, "srcset": [440, 660, 880, 1320],
                       "sizes": "(min-width: 1240px) 440px, (min-width: 900px) 38vw, 92vw",
                       "quality": 82}),
    ("fj-cal-col",    {"aspect": [4, 5], "width": 600, "srcset": [300, 450, 600, 900],
                       "sizes": "(min-width: 1240px) 264px, (min-width: 640px) 24vw, 45vw",
                       "quality": 80}),
    ("fj-crew-card",  {"aspect": [1, 1], "width": 720, "srcset": [360, 540, 720, 1080],
                       "sizes": "(min-width: 1240px) 360px, (min-width: 640px) 30vw, 45vw",
                       "quality": 80}),
    # The six climate columns. Narrow — 1152px of content over six columns is
    # about 190px each — and easy to miss: without an entry here they fall to
    # DEFAULT_SPEC and `optimise` sizes them for a 1600px box, which is how a
    # 3 MB frame ends up feeding a 190px column.
    ("fj-transect-pic", {"aspect": [4, 3], "width": 200, "srcset": [200, 300, 400, 600],
                         "sizes": "(min-width: 900px) 190px, 33vw", "quality": 80}),
)

# Anything the classes above do not cover kept its shape from the illustration,
# which is 3:2. Deliver 3:2 so nothing about the layout changes.
DEFAULT_SPEC = {"aspect": [3, 2], "width": 1600, "srcset": [800, 1200, 1600, 2400],
                "sizes": "100vw", "quality": 82}

IMG_RE = re.compile(r"<img\b[^>]*>", re.S)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def spec_for(html, position):
    """Nearest preceding wrapper class decides the delivered shape."""
    before = html[max(0, position - 400):position]
    best, best_at = DEFAULT_SPEC, -1
    for cls, spec in SLOT_SPECS:
        at = before.rfind(cls)
        if at > best_at:
            best, best_at = spec, at
    return best


def build_map(country, taxonomy):
    """illustration path -> resolved image record."""
    out = {}
    for cat in taxonomy.enabled:
        entry = country.entry(cat["id"])
        if entry and entry.local and entry.image and entry.image.get("imageUrl"):
            out.setdefault(entry.local, entry.image)
    return out


def rewrite_tag(tag, record, role, focal):
    """Swap one <img> onto a photograph, preserving everything else about it."""
    attrs = dict(ATTR_RE.findall(tag))
    illustration = attrs.get("data-illustration") or attrs.get("src")
    # The drawing's own alt describes the drawing. Keep it, or --revert would
    # restore the illustration with a caption written for a different picture.
    original_alt = attrs.get("data-illustration-alt") or attrs.get("alt", "")

    src = imaging.cdn_url(record, role, focal)
    srcset = imaging.srcset(record, role, focal)
    w, h = imaging.dimensions(role)

    attrs["src"] = src
    attrs["srcset"] = srcset
    attrs["sizes"] = role["sizes"]
    attrs["alt"] = record.get("alt") or attrs.get("alt", "")
    # Deliberately no width/height attributes.
    #
    # They look like the right thing — they are exactly what prevents layout
    # shift on the generated tourism pages. Here they break the layout. The
    # attributes become presentational hints, and these slots are styled
    # `width:100%; aspect-ratio:3/4` with no height. The hint supplies the
    # missing height, both dimensions become definite, and aspect-ratio is
    # ignored: the picture renders at 479x1280 instead of 479x638.
    #
    # Measured, not assumed: with the attributes an image box is 479x1280,
    # without them 479x638, which is byte-identical to the illustration it
    # replaced. The CSS aspect-ratio already reserves the box, so nothing
    # shifts while the photograph loads.
    _ = (w, h)
    attrs["data-illustration"] = illustration
    attrs["data-illustration-alt"] = original_alt
    attrs["data-provider"] = record.get("provider", "")
    attrs.setdefault("decoding", "async")
    style = attrs.get("style", "")
    if "object-position" not in style:
        attrs["style"] = (style + ";" if style else "") + \
            "object-position:%s" % imaging.object_position(focal)

    order = ["src", "srcset", "sizes", "alt", "loading",
             "decoding", "fetchpriority", "class", "style", "data-illustration",
             "data-illustration-alt", "data-provider"]
    parts = []
    for k in order:
        if k in attrs:
            parts.append('%s="%s"' % (k, attrs.pop(k)))
    for k, v in attrs.items():
        parts.append('%s="%s"' % (k, v))
    return "<img " + " ".join(parts) + ">"


def revert_tag(tag):
    attrs = dict(ATTR_RE.findall(tag))
    illustration = attrs.get("data-illustration")
    if not illustration:
        return tag
    keep = {k: v for k, v in attrs.items()
            if k in ("loading", "class", "fetchpriority")}
    keep["src"] = illustration
    if attrs.get("data-illustration-alt"):
        keep["alt"] = attrs["data-illustration-alt"]
    elif attrs.get("alt"):
        keep["alt"] = attrs["alt"]
    order = ["src", "alt", "loading", "fetchpriority", "class"]
    return "<img " + " ".join('%s="%s"' % (k, keep[k]) for k in order if k in keep) + ">"


def run(country_slug="cameroon", revert=False, write=True):
    taxonomy = load_taxonomy()
    cache = cache_mod.load()
    countries = attach_cache(load_countries(), cache)
    matches = [c for c in countries if c.slug == country_slug]
    if not matches:
        raise KeyError("no country %r" % country_slug)
    country = matches[0]

    photos = build_map(country, taxonomy)
    focal_by_local = {}
    for cat in taxonomy.enabled:
        e = country.entry(cat["id"])
        if e and e.local:
            focal_by_local.setdefault(e.local, e.focal)

    report = {"adopted": 0, "kept": 0, "reverted": 0, "locked": 0,
              "pages": [], "missing": set()}

    for page in PAGES:
        path = os.path.join(ROOT, page)
        src = open(path).read()
        changed = 0

        def replace(m):
            nonlocal changed
            tag = m.group(0)
            attrs = dict(ATTR_RE.findall(tag))
            held = attrs.get("data-locked") == "true" or attrs.get("data-placed") == "true"
            if revert:
                if held:
                    report["locked"] += 1
                    return tag
                if attrs.get("data-illustration"):
                    changed += 1
                    report["reverted"] += 1
                    return revert_tag(tag)
                return tag
            if held:
                # Artwork chosen by hand. A resolver result must never displace
                # a picture somebody deliberately put there.
                report["locked"] += 1
                return tag
            illustration = attrs.get("data-illustration") or attrs.get("src", "")
            record = photos.get(illustration)
            if not record:
                report["kept"] += 1
                report["missing"].add(os.path.basename(illustration))
                return tag
            role = spec_for(src, m.start())
            focal = focal_by_local.get(illustration, {"x": 50, "y": 50})
            new = rewrite_tag(tag, record, role, focal)
            if new != tag:
                changed += 1
            report["adopted"] += 1
            return new

        out = IMG_RE.sub(replace, src)
        if write and out != src:
            open(path, "w").write(out)
        report["pages"].append((page, changed))

    report["missing"] = sorted(report["missing"])
    return report
