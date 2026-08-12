"""Resize and re-encode the placed images so the site is deliverable.

    python3 tools/tourism/build.py optimise --dry-run     # what it would do
    python3 tools/tourism/build.py optimise

The home page carries sixteen local images and, before this ran, 23 MB of
them — single 3 MB frames feeding 190px columns. That is not a detail to
tidy up later. On a Cameroonian mobile connection it is the difference
between a site that loads and one that does not, and no amount of
interactive cartography on top of it makes up the difference.

What it does, per image: work out the largest box the layout will ever paint
it in, from the slot's own delivered width; resize to twice that for high-DPI
screens; re-encode as JPEG at q82 (or keep PNG when the source has real
transparency); and only keep the result if it is actually smaller. Every
`<img>` that pointed at the old file is repointed, including the srcset width
descriptor, which would otherwise be a lie about a file that changed size.

Requires Pillow. It is the one dependency in this project and it is
deliberately not a runtime one: it is needed to *prepare* images, never to
serve them, so it stays out of package.json and the deployed site remains
static files. Where Pillow is missing the command says so and changes
nothing — `.github/workflows/tourism-optimise.yml` runs it on a runner,
which is the same arrangement the resolver and the generator already use for
work this sandbox cannot do.
"""

import os
import re

from . import adopt, placements as pl
from .model import ROOT

QUALITY = 82
DPR = 2                 # serve twice the CSS box, so it is sharp on a retina screen
MIN_SAVING = 0.05       # rewriting a file to save 4% is churn, not optimisation


def pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def target_width(placement):
    """Twice the widest box this slot is ever painted at.

    `width` on a slot spec is the delivered width the stylesheet asks for, so
    it already accounts for the grid. Doubling covers high-DPI; capping stops a
    full-bleed band from being re-encoded at 6000px.
    """
    return min(int(placement["width"]) * DPR, 3000)


def plan(country):
    """[(path, target_width, [placements using it])] for every local image."""
    by_path = {}
    for p in pl.scan(country):
        src = (p.get("current") or "").split("?")[0]
        if not src.startswith("/images/") or src.endswith(".svg"):
            continue
        path = os.path.join(ROOT, src.lstrip("/"))
        if not os.path.exists(path):
            continue
        entry = by_path.setdefault(path, {"url": src, "width": 0, "slots": []})
        entry["width"] = max(entry["width"], target_width(p))
        entry["slots"].append(p)
    return by_path


def optimised_name(url, width):
    stem, ext = os.path.splitext(os.path.basename(url))
    return "%s-%dw%s" % (stem, width, ext)


def encode(Image, path, width, out_dir, log=print):
    """-> (new_path, new_url, new_width, saved_bytes) or None if not worth it."""
    with Image.open(path) as im:
        im.load()
        has_alpha = im.mode in ("RGBA", "LA") or (
            im.mode == "P" and "transparency" in im.info)
        source_w, source_h = im.size
        w = min(width, source_w)
        h = max(1, round(source_h * w / float(source_w)))
        if (w, h) != im.size:
            im = im.resize((w, h), Image.LANCZOS)

        # Transparency is the only reason to stay a PNG here; a photograph
        # kept as PNG is several times the size of the same frame as JPEG.
        if has_alpha:
            out_ext, params = ".png", {"optimize": True}
            im = im.convert("RGBA")
        else:
            out_ext, params = ".jpg", {"quality": QUALITY, "optimize": True,
                                       "progressive": True}
            im = im.convert("RGB")

        stem = os.path.splitext(os.path.basename(path))[0]
        name = "%s-%dw%s" % (stem, w, out_ext)
        out_path = os.path.join(out_dir, name)
        os.makedirs(out_dir, exist_ok=True)
        im.save(out_path, **params)

    before, after = os.path.getsize(path), os.path.getsize(out_path)
    if after >= before * (1 - MIN_SAVING):
        os.remove(out_path)
        log("    %-46s already small enough" % os.path.basename(path))
        return None
    return out_path, name, w, before - after


def repoint(old_url, new_url, new_width, write=True):
    """Every <img> using the old file now uses the new one, at its real width."""
    changed = 0
    for page in pl.PAGES:
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        src = open(path).read()

        def fix(m):
            nonlocal changed
            tag = m.group(0)
            if old_url not in tag:
                return tag
            changed += 1
            tag = tag.replace(old_url, new_url)
            # The width descriptor described the old file. Left alone it tells
            # the browser a 900px image is 3000px wide, and it will pick it for
            # a 3000px slot and scale it up.
            tag = re.sub(r'srcset="[^"]*"', 'srcset="%s %dw"' % (new_url, new_width), tag)
            return tag

        out = adopt.IMG_RE.sub(fix, src)
        if write and out != src:
            open(path, "w").write(out)
    return changed


def run(country, dry_run=False, log=print):
    Image = pillow()
    work = plan(country)
    total_before = sum(os.path.getsize(p) for p in work)
    log("%d local image(s) on the site, %.1f MB" % (len(work), total_before / 1048576.0))

    if Image is None:
        log("\nPillow is not installed, so nothing was changed.")
        log("  pip install Pillow   — then run this again")
        log("  or: Actions -> Optimise images -> Run workflow, which does it on a runner")
        return {"optimised": 0, "saved": 0, "available": False}

    if dry_run:
        for path, info in sorted(work.items()):
            log("  %-46s %5.1f MB -> %dpx wide"
                % (os.path.basename(path), os.path.getsize(path) / 1048576.0, info["width"]))
        log("\ndry run: nothing was re-encoded and no page was changed.")
        return {"optimised": 0, "saved": 0, "available": True}

    done = saved = 0
    for path, info in sorted(work.items()):
        out_dir = os.path.dirname(path)
        result = encode(Image, path, info["width"], out_dir, log=log)
        if not result:
            continue
        _out_path, name, w, bytes_saved = result
        new_url = os.path.dirname(info["url"]) + "/" + name
        n = repoint(info["url"], new_url, w)
        os.remove(path)
        done += 1
        saved += bytes_saved
        log("  %-46s -> %-42s %5.1f MB saved, %d slot(s)"
            % (os.path.basename(path), name, bytes_saved / 1048576.0, n))

    log("\nre-encoded %d image(s), saved %.1f MB" % (done, saved / 1048576.0))
    log("run `verify` and look at the pages before committing: this rewrites "
        "src and srcset on every slot it touches.")
    return {"optimised": done, "saved": saved, "available": True}
