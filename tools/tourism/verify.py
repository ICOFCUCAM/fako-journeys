"""Check the rendered HTML, not just the data.

A dataset can validate perfectly and still produce a page with twenty-four tiles
on it. These checks read the generated files back off disk and assert the things
that actually matter to a visitor: every category present, every image reachable,
every image boxed so the page does not jump, and every image carrying alt text.
"""

import os
import re

from . import imaging
from .model import ROOT

TOURISM = os.path.join(ROOT, "tourism")

IMG_RE = re.compile(r"<img\b[^>]*>", re.S)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def attrs(tag):
    return dict(ATTR_RE.findall(tag))


def check_page(path, taxonomy, expect_categories=True):
    problems = []
    src = open(path).read()
    name = os.path.basename(path)

    tags = IMG_RE.findall(src)
    empties = src.count('class="tq-empty')

    if expect_categories:
        # the renderer stamps data-category on every block it emits, so this is a
        # structural check rather than a fragile match on visible copy
        rendered = re.findall(r'data-category="([a-z-]+)"', src)
        counts = {}
        for cid in rendered:
            counts[cid] = counts.get(cid, 0) + 1
        for cat in taxonomy.enabled:
            n = counts.get(cat["id"], 0)
            if n == 0:
                problems.append("%s: category %r never rendered" % (name, cat["id"]))
            elif n > 1:
                problems.append("%s: category %r rendered %d times" % (name, cat["id"], n))
        slots = len(tags) + empties
        if slots != len(taxonomy.enabled):
            problems.append("%s: %d image slots, expected %d"
                            % (name, slots, len(taxonomy.enabled)))

    for tag in tags:
        a = attrs(tag)
        src_url = a.get("src", "")
        if not a.get("alt"):
            problems.append("%s: <img> without alt text (%s)" % (name, src_url[:60]))
        elif len(a["alt"]) < 12:
            problems.append("%s: alt text too thin: %r" % (name, a["alt"]))
        if not (a.get("width") and a.get("height")):
            problems.append("%s: <img> without width/height — layout shift (%s)"
                            % (name, src_url[:60]))
        style = a.get("style", "")
        if "aspect-ratio" not in style:
            problems.append("%s: <img> without aspect-ratio (%s)" % (name, src_url[:60]))
        if "object-position" not in style:
            problems.append("%s: <img> without object-position (%s)" % (name, src_url[:60]))
        if src_url.startswith(imaging.allowed_host()):
            if "srcset" not in a:
                problems.append("%s: remote image without srcset (%s)" % (name, src_url[:60]))
            if "sizes" not in a:
                problems.append("%s: remote image without sizes (%s)" % (name, src_url[:60]))
            if "w=" not in src_url or "q=" not in src_url:
                problems.append("%s: remote image without CDN sizing params" % name)
        elif src_url.startswith("/"):
            local = os.path.join(ROOT, src_url.lstrip("/"))
            if not os.path.exists(local):
                problems.append("%s: broken local image reference %s" % (name, src_url))
        elif src_url:
            problems.append("%s: image from an unexpected source: %s" % (name, src_url[:70]))

    # exactly one eager image per page: the hero. Everything else lazy.
    eager = sum(1 for t in tags if "loading=" not in t)
    if expect_categories and eager > 1:
        problems.append("%s: %d images not lazy-loaded, expected 1 (the hero)" % (name, eager))
    return problems


def check_site(taxonomy):
    """Also confirm the rest of the site has no dangling image references."""
    problems = []
    for f in sorted(os.listdir(ROOT)):
        if not f.endswith(".html"):
            continue
        src = open(os.path.join(ROOT, f)).read()
        for m in re.finditer(r'src="(/images/[^"]+)"', src):
            if not os.path.exists(os.path.join(ROOT, m.group(1).lstrip("/"))):
                problems.append("%s: broken image reference %s" % (f, m.group(1)))
    return problems


def run(taxonomy):
    problems = []
    pages = sorted(p for p in os.listdir(TOURISM) if p.endswith(".html"))
    for p in pages:
        problems += check_page(os.path.join(TOURISM, p), taxonomy,
                               expect_categories=(p != "index.html"))
    problems += check_site(taxonomy)
    return pages, problems
