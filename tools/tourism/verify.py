"""Check the rendered HTML, not just the data.

A dataset can validate perfectly and still produce a page with twenty-four tiles
on it. These checks read the generated files back off disk and assert the things
that actually matter to a visitor: every category present, every image reachable,
every image boxed so the page does not jump, and every image carrying alt text.
"""

import os
import re

from . import providers
from .model import COUNTRY_DIR, ROOT

TOURISM = os.path.join(ROOT, "tourism")


def asset_host():
    """Where our own photographs are served from, read from the register.

    Not a constant here, because there must be exactly one place that decides
    it. tourism/assets.json already holds it — the pipeline writes those URLs
    from that field — and a second copy in this file would be a copy that can
    disagree with the pages it is checking.
    """
    from . import library
    return (library.register().get("host") or "").rstrip("/")


def country_names():
    """Every country's name, for the one alt text that is allowed to be short.

    A photograph with no evidence behind it describes itself as its country, or
    as its category in its country — that is what commit 057 does and why. Both
    are correct and one of them is seven characters long, so a flat minimum
    length reports the honest state as a fault.
    """
    import json
    out = set()
    try:
        names = sorted(os.listdir(COUNTRY_DIR))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json") or name.startswith("_"):
            continue
        try:
            with open(os.path.join(COUNTRY_DIR, name)) as fh:
                out.add((json.load(fh).get("name") or "").strip())
        except (IOError, ValueError):
            continue
    return {n for n in out if n}

IMG_RE = re.compile(r"<img\b[^>]*>", re.S)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def attrs(tag):
    return dict(ATTR_RE.findall(tag))


COUNTRIES = country_names()
# Computed once, like COUNTRIES above, and read from the register so this
# file cannot hold an opinion about the host that disagrees with the pages.
ASSET_HOST = asset_host()


def check_page(path, taxonomy, expect_categories=True):
    problems = []
    src = open(path).read()
    name = os.path.basename(path)

    # THE COMPANY'S OWN MARK IS NOT ONE OF THE TWENTY-SEVEN SLOTS.
    # Everything this function does is written for a photograph that arrived
    # from a provider and was cropped into a box: it is counted against the
    # taxonomy, it must describe what it shows, declare its aspect so the box
    # does not move, and say where the subject sits so the crop keeps it. The
    # mark is none of those. It is one file, drawn at the size it is drawn at,
    # never cropped, and it stands beside the word "Afrinkong" in every footer
    # it appears in — so alt="" is correct and alt text would read the
    # company's name twice in a row. Dropped before the count as well as
    # before the checks, or every country page reports twenty-eight slots
    # against an expected twenty-seven. Recognised by its class rather than by
    # its path, so a second brand file cannot slip in by being called
    # something else.
    tags = [t for t in IMG_RE.findall(src) if "af-emblem" not in t]
    # An unresolved slot is the plate component. It used to be a `tq-empty` div,
    # and this line was never updated when it changed, so a country with no
    # photographs counted zero slots against an expected twenty-seven, `verify`
    # returned problems, `build.py all` exited 1, and the resolve workflow died
    # at its rebuild step before it could commit anything it had just found.
    # That is what both of the runs on 13 August did. Count either shape.
    empties = src.count('class="tq-empty') + src.count('class="af-plate ')

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
        elif len(a["alt"]) < 12 and a["alt"].strip() not in COUNTRIES:
            problems.append("%s: alt text too thin: %r" % (name, a["alt"]))
        if not (a.get("width") and a.get("height")):
            problems.append("%s: <img> without width/height — layout shift (%s)"
                            % (name, src_url[:60]))
        style = a.get("style", "")
        if "aspect-ratio" not in style:
            problems.append("%s: <img> without aspect-ratio (%s)" % (name, src_url[:60]))
        if "object-position" not in style:
            problems.append("%s: <img> without object-position (%s)" % (name, src_url[:60]))
        # A CDN's rules only apply to a CDN. Two of the providers are local
        # folders — /images/generated/ and /images/uploads/ — so owns_any() is
        # true for them and this used to demand `w=`/`h=` query parameters from
        # a file sitting on disk. What a local file needs is to exist, which is
        # the branch below.
        if providers.owns_any(src_url) and src_url.startswith("http"):
            if "srcset" not in a:
                problems.append("%s: remote image without srcset (%s)" % (name, src_url[:60]))
            if "sizes" not in a:
                problems.append("%s: remote image without sizes (%s)" % (name, src_url[:60]))
            if "w=" not in src_url or "h=" not in src_url:
                problems.append("%s: remote image without CDN sizing params" % name)
        elif src_url.startswith("/"):
            local = os.path.join(ROOT, src_url.lstrip("/"))
            if not os.path.exists(local):
                problems.append("%s: broken local image reference %s" % (name, src_url))
        elif ASSET_HOST and src_url.startswith(ASSET_HOST):
            # Our own asset host. The library's `verify` step is what checks
            # these against the register — every URL resolving to a registered
            # asset, with a photographer and a licence behind it. Repeating a
            # weaker version of that here would only mean two places to fix.
            pass
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
    # compare.html is the image contact sheet — a working document, gitignored,
    # and written only when somebody runs `build.py compare` locally. It is not a
    # rendered country page and checking it produces forty spurious failures
    # about a review sheet doing exactly what a review sheet does. It never
    # appeared on CI, where the file does not exist, which is why this went
    # unnoticed.
    pages = sorted(p for p in os.listdir(TOURISM)
                   if p.endswith(".html") and p != "compare.html")
    for p in pages:
        problems += check_page(os.path.join(TOURISM, p), taxonomy,
                               expect_categories=(p != "index.html"))
    problems += check_site(taxonomy)
    return pages, problems
