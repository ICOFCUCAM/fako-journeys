"""AVIF and WebP beside every photograph, and a <picture> around every tag.

    python3 tools/tourism/build.py modern            # what it would do
    python3 tools/tourism/build.py modern --fetch    # encode and rewrite

THE SITE SHIPPED 276 JPEGs AND NOTHING ELSE.

Measured before this existed: the homepage's first screen at 390/3x came to
4.45 MB over 22 requests. It passed the browser suite's budget, which is 6 MB —
a number this repository chose for itself and roughly four times what a site
selling four-thousand-dollar journeys should ask a phone to download. Every
photograph on the site was a JPEG, and JPEG is thirty years old.

On this site's own heroes, at qualities chosen by looking rather than by
copying a blog post:

    cross-convoy-on-the-road-1600w   JPEG 258 KB   WebP 180 KB   AVIF 145 KB

That is the whole of it. No layout changes, no crops re-decided, no photograph
replaced — the same picture, encoded by something that was not designed in
1992.

---------------------------------------------------------------------------
WHY A LATE PASS AND NOT A CHANGE IN THE GENERATORS

The same <img> comes out of six page families. Rewriting all six to emit
<picture> is six places to be right and six places to drift, and this
repository has an established answer to that shape of problem: `company`,
`graft`, `srcset` and `sizeattr` all rewrite built HTML after the generators
have run. This is the fifth, and it runs after `srcset` for the same reason
`sizeattr` does — it copies the srcset ladder srcset has just written, so it
has to see the finished one.

---------------------------------------------------------------------------
WHAT IT WILL NOT TOUCH

- Anything not on disk under /images. A photograph the resolver left as a
  remote provider URL cannot be re-encoded by us and is left alone.
- The company's mark. It is a PNG with an alpha channel drawn at 26 to 60
  pixels; the modern formats save bytes on photographs, not on a 26 KB logo,
  and re-encoding a logo is how a logo picks up artefacts.
- Anything already inside a <picture>. Idempotent, so `all` can run it every
  time and running it twice costs a scan.

---------------------------------------------------------------------------
THE ONE LAYOUT RISK, AND WHY IT IS NOT ONE

Wrapping an <img> changes its parent, which breaks any CSS that reaches the
image as a direct child. Checked before writing a line of this: `> img` appears
zero times across all fifteen stylesheets, and so do img:first-child and
img:nth-*. `picture{display:contents}` in afrinkong.css removes the wrapper
from layout entirely in any case, so the image participates in its container
exactly as it did.
"""

import os
import re
import time

from .model import ROOT

IMAGES = os.path.join(ROOT, "images")

# Quality, decided by encoding this site's own photographs and looking at them
# beside the JPEG at 1:1 rather than by picking the number a blog post used.
# AVIF's scale is not WebP's and neither is JPEG's; these two land within a
# rounding error of the original on the heroes and save a third to a half.
AVIF_Q = 62
WEBP_Q = 82

IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r'\bsrc="([^"]+)"')
SET_RE = re.compile(r'\bsrcset="([^"]+)"')
SIZES_RE = re.compile(r'\bsizes="([^"]+)"')

CONVERTIBLE = (".jpg", ".jpeg", ".png")
# The mark is a PNG and stays one. See the note above.
SKIP = ("/images/brand/",)


def _local(url):
    """The file on disk a src or srcset entry names, or None.

    Absolute site paths only. A protocol-relative or remote URL is somebody
    else's file and this pass has no business re-encoding it.
    """
    if not url.startswith("/images/"):
        return None
    if any(url.startswith(s) for s in SKIP):
        return None
    if not url.lower().endswith(CONVERTIBLE):
        return None
    path = os.path.join(ROOT, url.lstrip("/"))
    return path if os.path.exists(path) else None


def _urls_in(tag):
    """Every image URL a tag names, src first then each srcset candidate."""
    out = []
    m = SRC_RE.search(tag)
    if m:
        out.append(m.group(1))
    m = SET_RE.search(tag)
    if m:
        for part in m.group(1).split(","):
            url = part.strip().split()[0] if part.strip() else ""
            if url:
                out.append(url)
    return out


def wanted(log=print):
    """Every local photograph any built page actually asks for.

    Referenced, not present. 127 of the 276 files in images/uploads are named
    by no page — originals that were never wired up — and encoding those would
    be several minutes of work to make the repository bigger.
    """
    seen = []
    for base, _dirs, files in os.walk(ROOT):
        if any(p in base for p in ("/node_modules", "/.git", "/incoming")):
            continue
        for name in files:
            if not name.endswith(".html"):
                continue
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                html = fh.read()
            for tag in IMG_RE.findall(html):
                for url in _urls_in(tag):
                    if url not in seen and _local(url):
                        seen.append(url)
    return sorted(seen)


def encode(write=False, log=print):
    """Write a .avif and a .webp beside every referenced photograph."""
    try:
        from PIL import Image
    except ImportError:
        log("modern: Pillow is not installed — nothing encoded")
        return 0

    urls = wanted(log=log)
    todo, done, bytes_before, bytes_after = [], 0, 0, 0
    for url in urls:
        src = _local(url)
        stem = os.path.splitext(src)[0]
        for ext, kwargs in ((".avif", {"quality": AVIF_Q}),
                            (".webp", {"quality": WEBP_Q, "method": 5})):
            out = stem + ext
            # Newer than its source is up to date. Re-encoding four hundred
            # photographs on every build would put minutes into `all` for
            # nothing.
            if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
                continue
            todo.append((src, out, kwargs))

    if not write:
        log("modern: %d file(s) to encode from %d photograph(s). dry run — "
            "add --fetch to write them." % (len(todo), len(urls)))
        return 0

    start = time.time()
    for src, out, kwargs in todo:
        try:
            with Image.open(src) as im:
                im = im.convert("RGBA" if im.mode in ("RGBA", "LA") else "RGB")
                im.save(out, **kwargs)
            done += 1
            bytes_before += os.path.getsize(src)
            bytes_after += os.path.getsize(out)
        except Exception as exc:                      # noqa: BLE001 — report, continue
            log("  modern: %s failed (%s)" % (os.path.relpath(out, ROOT), exc))
    if done:
        log("modern: encoded %d file(s) from %d photograph(s) in %.0fs"
            % (done, len(urls), time.time() - start))
    else:
        log("modern: %d photograph(s), all encodings up to date" % len(urls))
    return 0


def _swap(value, ext):
    """A srcset or src with every convertible extension swapped for `ext`.

    Returns None if any file it would name does not exist, because a <source>
    that 404s on one candidate is worse than no <source> at all: the browser
    has already committed to that source by the time it finds out.
    """
    out = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        url = bits[0]
        if not _local(url):
            return None
        new = os.path.splitext(url)[0] + ext
        if not os.path.exists(os.path.join(ROOT, new.lstrip("/"))):
            return None
        out.append(" ".join([new] + bits[1:]))
    return ", ".join(out) if out else None


def _wrap(tag):
    """One <img> into a <picture>, or the tag unchanged."""
    set_m = SET_RE.search(tag)
    src_m = SRC_RE.search(tag)
    base = set_m.group(1) if set_m else (src_m.group(1) if src_m else "")
    if not base:
        return tag
    sizes = SIZES_RE.search(tag)
    sizes_attr = ' sizes="%s"' % sizes.group(1) if sizes else ""

    sources = []
    # AVIF first: a browser takes the first <source> whose type it supports,
    # so the order of these two lines is the whole negotiation.
    for ext, mime in ((".avif", "image/avif"), (".webp", "image/webp")):
        swapped = _swap(base, ext)
        if swapped:
            sources.append('<source type="%s" srcset="%s"%s>'
                           % (mime, swapped, sizes_attr))
    if not sources:
        return tag
    return "<picture>" + "".join(sources) + tag + "</picture>"


def run(write=False, log=print):
    """Wrap every convertible <img> in the built HTML."""
    changed, tags = 0, 0
    for base, _dirs, files in os.walk(ROOT):
        if any(p in base for p in ("/node_modules", "/.git", "/incoming")):
            continue
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            if "<img" not in html:
                continue

            # Already inside a <picture> is left alone, which is what makes
            # this idempotent. Matched on the text immediately before the tag
            # rather than by parsing, because the alternative is a parser.
            out, cut, n = [], 0, 0
            for m in IMG_RE.finditer(html):
                before = html[max(0, m.start() - 400):m.start()]
                if "<picture>" in before and "</picture>" not in \
                        before[before.rindex("<picture>"):]:
                    continue
                wrapped = _wrap(m.group(0))
                if wrapped == m.group(0):
                    continue
                out.append(html[cut:m.start()])
                out.append(wrapped)
                cut = m.end()
                n += 1
            if not n:
                continue
            out.append(html[cut:])
            tags += n
            changed += 1
            if write:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("".join(out))

    if write:
        log("modern: %d tag(s) wrapped across %d page(s)" % (tags, changed))
    else:
        log("modern: %d tag(s) on %d page(s) would be wrapped. dry run — add "
            "--fetch to write." % (tags, changed))
    return 0
