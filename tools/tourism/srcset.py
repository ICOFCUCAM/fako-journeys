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
            out, did = offer(m.group(0), have)
            if did:
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
