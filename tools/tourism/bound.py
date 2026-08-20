"""Ask the provider for the size the page actually paints. No purchase.

    python3 tools/tourism/build.py bound            # what it would change
    python3 tools/tourism/build.py bound --fetch    # change it

THE WORST THING THIS SITE DOES TO A PHONE, AND IT IS FREE TO STOP.

750 `/places` heroes are hotlinked with no width in the URL:

    <img src="https://images.unsplash.com/photo-1610133290889-0ed892ce5157"
         width="1600" height="900" fetchpriority="high"
         style="aspect-ratio:16/9">

The tag states the geometry — 1600x900, sixteen by nine — and the src asks for
none of it, so the provider sends whatever the photographer uploaded. Measured:
2.3 to 3.7 MB, to a 390-pixel phone, as the one image on the page it is certain
to fetch. The CSS then crops it to 16:9 and throws most of it away.

Fixing that needs no licence, no shoot, no agency and no new asset. It is the
same photograph from the same URL, asked for politely — and it is the treatment
the rest of this site already uses: the /tourism heroes have carried
`fit=crop&w=2400&h=1350` with a srcset since they were built. These pages
simply never got it.

WHY IT IS WORTH DOING TO PHOTOGRAPHS WE INTEND TO REPLACE

Because acquisition takes months and page weight is costing money now. A
visitor downloading 2.5 MB for a hero we already know is wrong is paying twice.
Bounding it changes nothing about whether the picture is any good, and stops
the bleeding while that question is answered properly.

WHAT IT DOES NOT DO

It does not crop differently, recolour, or choose a focal point. The aspect it
requests is the aspect the tag already declares, and the largest width it
requests is the width the tag already declares. Nothing here is a judgement
about composition; a photograph looks exactly as it did, in fewer bytes.
"""

import html as html_mod
import os
import re

from .model import ROOT

IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
PROVIDER_RE = re.compile(r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+")
W_ATTR = re.compile(r'\swidth="(\d+)"')
H_ATTR = re.compile(r'\sheight="(\d+)"')

# The rungs, matching the library's own ladder so a page that later migrates
# does not change shape when it does.
LADDER = (480, 800, 1200, 1600)

# THE HERO RENDERS AT ABOUT 800 CSS PIXELS, NOT AT THE FULL VIEWPORT.
#
# `.pl` is a 1240px frame with 44px of padding either side and a 300px rail
# beside the body, so the main column is roughly 800 wide on a desktop and the
# viewport minus its padding on a phone. Saying `100vw` would be simpler and
# would make every desktop browser fetch a rung larger than it paints.
#
# At 390px this resolves to 302 CSS px, which at 3x asks for 906 and takes the
# 1200 rung. At 1440 it resolves to 800, which at 2x asks for 1600 and takes
# the largest rung there is. Both correct, neither wasteful.
SIZES = "(min-width: 1000px) 800px, calc(100vw - 88px)"


def _query(provider, width, height):
    """The provider's own resize parameters. Not invented — copied from the
    /tourism heroes, which have used exactly these since they were built."""
    if provider == "unsplash":
        q = "auto=format&fit=crop&w=%d&q=70" % width
    else:
        q = "auto=compress&cs=tinysrgb&fit=crop&w=%d" % width
    if height:
        q += "&h=%d" % height
    return q


def _bound(url, provider, width, height):
    return "%s?%s" % (url.split("?")[0], _query(provider, width, height))


def plan_tag(tag):
    """The rewritten tag, or None if this one needs nothing.

    Only heroes: fetchpriority="high" is the site's own statement that a
    photograph is the one a phone fetches on arrival, and a lazy card below the
    fold costs nothing until somebody scrolls to it. Only unbounded ones: a URL
    that already names a width is already being asked politely.
    """
    found = PROVIDER_RE.search(tag)
    if not found:
        return None
    url = html_mod.unescape(found.group(0))
    if re.search(r"[?&]w=\d+", url):
        return None
    if 'fetchpriority="high"' not in tag:
        return None
    provider = "unsplash" if "images.unsplash.com" in url else "pexels"

    wm, hm = W_ATTR.search(tag), H_ATTR.search(tag)
    declared_w = int(wm.group(1)) if wm else LADDER[-1]
    declared_h = int(hm.group(1)) if hm else 0
    # The declared box is the ceiling. Asking for more than the tag says it
    # paints is the same mistake in a smaller size.
    rungs = [w for w in LADDER if w <= declared_w] or [LADDER[0]]
    if declared_w not in rungs and declared_w < LADDER[-1]:
        rungs.append(declared_w)
    rungs = sorted(set(rungs))

    def h_for(w):
        if not declared_h or not declared_w:
            return 0
        return round(w * declared_h / declared_w)

    srcset = ", ".join("%s %dw" % (_bound(url, provider, w, h_for(w)), w)
                       for w in rungs)
    biggest = rungs[-1]

    out = tag
    out = out.replace(found.group(0),
                      _bound(url, provider, biggest, h_for(biggest)))
    # Escape the ampersands: these live in an HTML attribute, and a bare & is
    # what made the first unbounded count read 100% — &w= does not match a
    # search for &amp;w=, and vice versa.
    out = out.replace("?auto=", "?auto=").replace("&", "&amp;")
    out = out.replace("&amp;amp;", "&amp;")
    # The tag had no srcset (that is what "unbounded" means here), so add one
    # rather than trying to merge with something that is not there.
    srcset = srcset.replace("&", "&amp;")
    add = ' srcset="%s" sizes="%s"' % (srcset, SIZES)
    out = out[:-1].rstrip() + add + ">"
    return out


def run(write=False, log=print):
    changed_tags, changed_pages = 0, 0
    per_provider = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            if "images.pexels.com" not in html and \
                    "images.unsplash.com" not in html:
                continue
            out, cut, n = [], 0, 0
            for m in IMG_RE.finditer(html):
                new = plan_tag(m.group(0))
                if not new:
                    continue
                out.append(html[cut:m.start()])
                out.append(new)
                cut = m.end()
                n += 1
                p = "unsplash" if "unsplash" in m.group(0) else "pexels"
                per_provider[p] = per_provider.get(p, 0) + 1
            if not n:
                continue
            out.append(html[cut:])
            changed_tags += n
            changed_pages += 1
            if write:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("".join(out))
    log("bound: %d hero(es) across %d page(s) %s  (%s)"
        % (changed_tags, changed_pages,
           "bounded" if write else "would be bounded",
           ", ".join("%s %d" % kv for kv in sorted(per_provider.items()))
           or "none"))
    if not write and changed_tags:
        log("  dry run — add --fetch to write the pages")
    return 0
