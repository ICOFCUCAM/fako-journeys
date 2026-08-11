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
  * idempotent: running it twice changes nothing the second time.
"""

import os
import re

from . import cache as cache_mod
from . import imaging
from .model import ROOT, attach_cache, load_countries, load_taxonomy

PAGES = ("index.html", "services.html", "about.html", "contact.html", "pricing.html")

# The main pages crop with CSS; the wrapper class says which shape, which decides
# how big a file to ask the CDN for. Getting this wrong means a 368px card
# downloading a 2400px hero.
CLASS_ROLE = (
    ("fj-vista-pic", "hero"),
    ("fj-seam-pic", "hero"),
    ("fj-open-plate", "portrait"),
    ("fj-act", "portrait"),
    ("fj-craft-pic", "portrait"),
    ("fj-cal-col", "portrait"),
    ("fj-crew-card", "card"),
    ("fj-slip-pic", "feature"),
)

IMG_RE = re.compile(r"<img\b[^>]*>", re.S)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def role_for(html, position, taxonomy):
    """Nearest preceding wrapper class decides the delivery shape."""
    before = html[max(0, position - 400):position]
    best, best_at = "feature", -1
    for cls, role in CLASS_ROLE:
        at = before.rfind(cls)
        if at > best_at:
            best, best_at = role, at
    return taxonomy.roles[best]


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
    attrs["width"] = str(w)
    attrs["height"] = str(h)
    attrs["data-illustration"] = illustration
    attrs["data-illustration-alt"] = original_alt
    attrs["data-provider"] = record.get("provider", "")
    attrs.setdefault("decoding", "async")
    style = attrs.get("style", "")
    if "object-position" not in style:
        attrs["style"] = (style + ";" if style else "") + \
            "object-position:%s" % imaging.object_position(focal)

    order = ["src", "srcset", "sizes", "alt", "width", "height", "loading",
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

    report = {"adopted": 0, "kept": 0, "reverted": 0, "pages": [], "missing": set()}

    for page in PAGES:
        path = os.path.join(ROOT, page)
        src = open(path).read()
        changed = 0

        def replace(m):
            nonlocal changed
            tag = m.group(0)
            attrs = dict(ATTR_RE.findall(tag))
            if revert:
                if attrs.get("data-illustration"):
                    changed += 1
                    report["reverted"] += 1
                    return revert_tag(tag)
                return tag
            illustration = attrs.get("data-illustration") or attrs.get("src", "")
            record = photos.get(illustration)
            if not record:
                report["kept"] += 1
                report["missing"].add(os.path.basename(illustration))
                return tag
            role = role_for(src, m.start(), taxonomy)
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
