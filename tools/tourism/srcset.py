"""Offer the smaller photograph to the smaller screen.

    python3 tools/tourism/build.py srcset            what it would change
    python3 tools/tourism/build.py srcset --fetch     write it

WHAT WAS WRONG

Sixty of the uploaded photographs exist at two widths — an 800 and a 1600, or
a 600 and a 1200 — and 111 pages already use srcset to offer both. Forty-eight
image tags did not: they named the largest file and nothing else, so a phone on
a 390-pixel screen downloaded the 1600-wide original.

Twenty-six distinct files, and 5.4 MB of photograph a small screen was made to
carry for nothing. Twenty-one of the forty-eight are on the homepage.

WHY THIS ADDS srcset AND NOT sizes

`sizes` tells the browser how wide the picture will be laid out, and getting it
wrong is worse than leaving it out: too small a hint and the browser fetches a
blurry file it cannot undo. Working that out per image means knowing the grid
each one sits in on every breakpoint, which is a per-component decision and not
something to infer from a file name.

With no `sizes`, the browser assumes the image is the full width of the
viewport. That is conservative in exactly the right direction: on a phone it
picks the 800, on a desktop it keeps the 1600, and it can never choose a file
too small for the space. Strictly better than one fixed URL, and it cannot
regress.

A LATE PASS, ON PURPOSE

This rewrites built HTML rather than the generators, because the same tags come
out of six different families — the gateway's blocks, the wonders, the
crossings, the country pages, the places and two hand-written pages — and one
pass over the output is one place to be right instead of six places to
remember. It is idempotent: a tag that already has a srcset is left alone.
"""

import os
import re

from .model import ROOT

UPLOADS = os.path.join(ROOT, "images", "uploads")
NAMED = re.compile(r"^(.+)-(\d+)w\.(jpg|jpeg|png|webp)$")
IMG = re.compile(r"<img\b[^>]*>", re.I)
SRC = re.compile(r'src="(/images/uploads/([^"]+))"')


def variants():
    """-> {(base, ext): [width, ...]} for every upload that has more than one."""
    out = {}
    try:
        names = os.listdir(UPLOADS)
    except OSError:
        return out
    for f in names:
        m = NAMED.match(f)
        if not m:
            continue
        out.setdefault((m.group(1), m.group(3)), []).append(int(m.group(2)))
    return dict((k, sorted(v)) for k, v in out.items() if len(v) > 1)


def offer(tag, have):
    """-> the tag with a srcset, or unchanged.

    Unchanged when it already has one, when the file has no siblings, or when
    the page is already naming something other than the largest — a page that
    deliberately asks for the 800 is making a choice, and this is not the place
    to overrule it.
    """
    if "srcset" in tag.lower():
        return tag, False
    m = SRC.search(tag)
    if not m:
        return tag, False
    n = NAMED.match(m.group(2))
    if not n:
        return tag, False
    key = (n.group(1), n.group(3))
    widths = have.get(key)
    if not widths or int(n.group(2)) != max(widths):
        return tag, False
    sets = ", ".join("/images/uploads/%s-%dw.%s %dw" % (key[0], w, key[1], w)
                     for w in widths)
    return tag[:-1].rstrip() + ' srcset="%s">' % sets, True


STALE = re.compile(r'\s+srcset="[^"]*"', re.I)


def drop_stale(tag):
    """-> the tag with a srcset removed if any file in it is gone.

    Deleting twenty-five siblings left twenty-three pages naming them. A
    srcset entry pointing at a 404 is not inert: the browser may pick it, get
    nothing, and show no image at all. Anything that rewrites the set of files
    on disk has to be able to clean up after itself.
    """
    m = re.search(r'srcset="([^"]+)"', tag, re.I)
    if not m:
        return tag, False
    for part in m.group(1).split(","):
        ref = part.strip().split(" ")[0]
        if ref.startswith("/") and not os.path.exists(
                os.path.join(ROOT, ref.lstrip("/"))):
            return STALE.sub("", tag, count=1), True
    return tag, False


def run(write=False, log=print):
    have = variants()
    if not have:
        log("no upload has more than one width; nothing to offer")
        return 0

    pages = []
    for base, _dirs, files in os.walk(ROOT):
        if any(x in base for x in (".git", "node_modules", "incoming")):
            continue
        for f in files:
            if f.endswith(".html"):
                pages.append(os.path.join(base, f))

    touched, tags = 0, 0
    for p in sorted(pages):
        with open(p, encoding="utf-8") as fh:
            src = fh.read()
        n = [0]

        def swap(m):
            tag, dropped = drop_stale(m.group(0))
            out, did = offer(tag, have)
            if did or dropped:
                n[0] += 1
            return out

        out = IMG.sub(swap, src)
        if n[0]:
            tags += n[0]
            touched += 1
            if write:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(out)
            log("  %-46s %d tag(s)" % (os.path.relpath(p, ROOT), n[0]))

    log("%s %d tag(s) across %d page(s), from %d photographs with two widths"
        % ("offered a smaller file to" if write else "WOULD offer on",
           tags, touched, len(have)))
    if not write:
        log("dry run. Add --fetch to write it.")
    return 0


# 800, WHATEVER THE PARENT IS, AND THE FIRST ATTEMPT GOT THIS WRONG.
#
# The obvious move was to copy the pairings already in the repository — an 800
# beside a 1600, a 600 beside a 1200 — and it produced fifty files a phone
# almost never chose. With no `sizes` the browser assumes the picture fills the
# viewport, so a 390-pixel screen at two device pixels needs about 780: it takes
# the 800 happily and rejects the 600 as too small, falling back to the 1200 it
# was already downloading. Fifty new files, one of them used.
#
# The useful width is a property of the SCREEN, not of the parent file. 800 is
# the smallest size that still serves the common phone at 2x, so that is what
# gets made, whether the original is 1200 or 1920.
SIBLING = 800


def missing_siblings():
    """-> [(file, source width, width to make)] for uploads with nothing smaller.

    Fifty of the uploads are 1200 pixels wide or more and have no smaller
    version, which is 9.6 MB that srcset cannot help with: there is nothing to
    offer. Making the sibling is what turns those fifty into the same win the
    other twenty-six already got.
    """
    have = variants()
    out = []
    try:
        names = sorted(os.listdir(UPLOADS))
    except OSError:
        return out
    for f in names:
        m = NAMED.match(f)
        if not m:
            continue
        key, w = (m.group(1), m.group(3)), int(m.group(2))
        if key in have:
            continue                       # already has a sibling
        if w >= 1200:
            out.append((f, w, SIBLING))
    return out


def make(write=False, log=print):
    """Generate the missing smaller versions.

    Pillow, which this repository already depends on for `optimise` and
    deliberately only to PREPARE images, never to serve them. Where it is
    missing this says so and changes nothing.
    """
    todo = missing_siblings()
    if not todo:
        log("every upload of 1200px or more already has a smaller version")
        return 0
    try:
        from PIL import Image
    except ImportError:
        log("Pillow is not installed here, so nothing was made. "
            "%d upload(s) still have no smaller version." % len(todo))
        return 2

    saved = made = 0
    for f, w, want in todo:
        base, _n, ext = NAMED.match(f).groups()
        out = "%s-%dw.%s" % (base, want, ext)
        src = os.path.join(UPLOADS, f)
        dst = os.path.join(UPLOADS, out)
        if os.path.exists(dst):
            continue
        if not write:
            log("  would make %-46s from %dw" % (out, w))
            made += 1
            continue
        im = Image.open(src)
        h = int(round(im.height * (float(want) / im.width)))
        small = im.resize((want, h), Image.LANCZOS)
        # PNG only where the source really has transparency; everything else is
        # a photograph and JPEG at 82 is what the optimiser already uses.
        if ext.lower() == "png" and small.mode in ("RGBA", "LA"):
            small.save(dst, "PNG", optimize=True)
        else:
            small.convert("RGB").save(dst, "JPEG", quality=82, optimize=True,
                                      progressive=True)
        a, b = os.path.getsize(src), os.path.getsize(dst)
        saved += a - b
        made += 1
        log("  %-46s %5.0f KB from %5.0f KB" % (out, b / 1024.0, a / 1024.0))
    log("%s %d smaller version(s)%s"
        % ("made" if write else "WOULD make", made,
           "; a small screen loading all of them saves %.1f MB"
           % (saved / 1024.0 / 1024.0) if write and saved else ""))
    if not write:
        log("dry run. Add --fetch to write them.")
    return 0
