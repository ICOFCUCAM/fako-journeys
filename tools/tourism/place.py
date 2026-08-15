"""Put a chosen candidate into the slot it was generated for.

`generate` makes options. This is the separate, deliberate step that publishes
one, and it is separate on purpose: generating is cheap and reversible, and
putting a synthetic photograph of a real place on a live page is neither.

    python3 tools/tourism/build.py place picks.json
    python3 tools/tourism/build.py place picks.json --dry-run
    python3 tools/tourism/build.py place --revert            # every placed slot back

`--revert` returns a slot to its illustration, which is the only thing an <img>
remembers about what it held before. If a resolved stock photograph was in that
slot before you placed over it, run `adopt` afterwards to put it back — the two
commands together are a byte-identical round trip, and neither one alone is.

picks.json is what the contact sheet downloads:

    {"site:index:mount-dawn-cinder": "site:index:mount-dawn-cinder/gpt-image-1-01.png"}

slot -> candidate id. A slot missing from the file is left exactly as it is, so
you can approve four pictures today and the rest next week.

What it does per pick:

  1. copies the candidate out of tourism/candidates/ (workshop, not deployed)
     into images/generated/ (shipped), because a file the site serves must not
     live in a directory the deploy ignores;
  2. rewrites that <img> on that page — src, srcset at the file's real width,
     alt, object-position from the entry's focal point;
  3. keeps data-illustration and data-illustration-alt, so the drawing can
     always come back, and marks the tag data-placed="true" so a later `adopt`
     run cannot silently overwrite a picture a person chose.

The alt text is the slot's own instruction — the sentence the picture was
generated from — because that is what the image was made to show. It is never
copied from a stock photograph's description.
"""

import os
import re
import shutil

from . import adopt, candidates as pool, imaging, placements as pl
from .model import ROOT

# Two destinations, because the two kinds of picture are not interchangeable to
# a visitor: one is synthetic and its credit line must say so, the other is the
# owner's own photograph and must never be labelled AI. Keeping them in separate
# folders means the host a URL sits on is itself the proof of which it is.
DESTINATIONS = {
    "openai": (os.path.join(ROOT, "images", "generated"), "/images/generated/"),
    "upload": (os.path.join(ROOT, "images", "uploads"), "/images/uploads/"),
}
PLACEABLE = tuple(DESTINATIONS)


def published_name(slot, candidate):
    """Stable, readable, and unique per slot: site-index-mount-dawn-cinder.png"""
    stem = slot.replace("site:", "site-").replace(":", "-").replace("/", "-")
    ext = os.path.splitext(candidate.get("file") or "")[1] or ".png"
    return "%s%s" % (stem, ext)


def publish(slot, candidate, dry_run=False):
    """Copy a candidate into the deployed folder. Returns its site URL."""
    source = os.path.join(ROOT, candidate["file"])
    if not os.path.exists(source):
        raise IOError("candidate file is missing: %s" % candidate["file"])
    directory, url_base = DESTINATIONS[candidate["source"]]
    name = published_name(slot, candidate)
    if not dry_run:
        os.makedirs(directory, exist_ok=True)
        shutil.copy2(source, os.path.join(directory, name))
    return url_base + name


def rewrite_tag(tag, url, candidate, alt, focal):
    """Swap one <img> onto a generated file, keeping the slot's identity."""
    attrs = dict(adopt.ATTR_RE.findall(tag))
    illustration = attrs.get("data-illustration") or attrs.get("src")
    original_alt = attrs.get("data-illustration-alt") or attrs.get("alt", "")

    attrs["src"] = url
    # One file, one width. There is no CDN behind a static path, so a srcset
    # listing four widths for the same bytes would be four lies; the browser is
    # told the one width there actually is.
    attrs["srcset"] = "%s %dw" % (url, candidate.get("width") or 0)
    attrs["alt"] = alt or original_alt
    attrs["data-illustration"] = illustration
    attrs["data-illustration-alt"] = original_alt
    attrs["data-provider"] = candidate["source"]
    # Marks the slot as filled by hand rather than by the resolver, so `adopt`
    # cannot quietly overwrite it and `place --revert` knows what it put there.
    attrs["data-placed"] = "true"
    if candidate["source"] == "openai":
        attrs["data-generated"] = "true"
    attrs.setdefault("decoding", "async")
    style = attrs.get("style", "")
    if "object-position" not in style:
        attrs["style"] = (style + ";" if style else "") + \
            "object-position:%s" % imaging.object_position(focal)
    # The placed file's own pixels, so the box is held before it arrives. These
    # were left off, following adopt.rewrite_tag, for a reason that was real and
    # is now fixed: without height:auto on the slot the attributes made both
    # dimensions definite, aspect-ratio was dropped, and the picture rendered at
    # its own shape. styles/afrinkong.css carries height:auto on
    # img[data-illustration] now, so they are a ratio hint and nothing else.
    if candidate.get("width") and candidate.get("height"):
        attrs["width"] = str(candidate["width"])
        attrs["height"] = str(candidate["height"])

    order = ["src", "srcset", "sizes", "alt", "width", "height", "loading", "decoding", "fetchpriority",
             "class", "style", "data-illustration", "data-illustration-alt",
             "data-provider", "data-placed", "data-generated"]
    parts = []
    for k in order:
        if k in attrs:
            parts.append('%s="%s"' % (k, attrs.pop(k)))
    for k, v in attrs.items():
        parts.append('%s="%s"' % (k, v))
    return "<img " + " ".join(parts) + ">"


def revert_tag(tag):
    """Back to whatever the slot held before a generated image went in."""
    attrs = dict(adopt.ATTR_RE.findall(tag))
    illustration = attrs.get("data-illustration")
    if not illustration:
        return tag
    keep = {k: v for k, v in attrs.items() if k in ("loading", "class", "fetchpriority")}
    keep["src"] = illustration
    keep["alt"] = attrs.get("data-illustration-alt") or attrs.get("alt", "")
    order = ["src", "alt", "loading", "fetchpriority", "class"]
    return "<img " + " ".join('%s="%s"' % (k, keep[k]) for k in order if k in keep) + ">"


def backfill_sizes(write=True, log=print):
    """Put width and height on placed photographs that were written without them.

    The tags are already in the pages and `place` cannot rewrite them without
    the picks file that produced them, so the dimensions are read back off the
    files the tags point at. Nothing else is touched: only <img> tags carrying
    data-placed, only ones missing a dimension, and only where the file is on
    disk and can be measured. Idempotent — a second run finds nothing to do.
    """
    from PIL import Image
    pages = [os.path.join(ROOT, f) for f in
             ("cameroon.html", "services.html", "about.html",
              "contact.html", "pricing.html")]
    done, skipped = 0, []
    for page in pages:
        if not os.path.exists(page):
            continue
        with open(page, encoding="utf-8") as fh:
            src = fh.read()
        out, changed = [], 0
        pos = 0
        for m in re.finditer(r"<img\b[^>]*>", src):
            tag = m.group(0)
            out.append(src[pos:m.start()])
            pos = m.end()
            # Placed pictures and locked ones alike: a locked slot is artwork
            # somebody chose rather than a search result, which is a reason not
            # to change WHICH picture it is, and no reason at all to leave it
            # reserving no space.
            if (("data-placed" not in tag and "data-locked" not in tag)
                    or ('width="' in tag and 'height="' in tag)):
                out.append(tag)
                continue
            got = re.search(r'src="([^"]+)"', tag)
            url = got.group(1) if got else ""
            rel = url.split("?")[0]
            path = os.path.join(ROOT, rel.lstrip("/"))
            if rel.startswith("/") and os.path.exists(path):
                with Image.open(path) as im:
                    w, h = im.size
            else:
                # A remote photograph has no file here to open, and does not
                # need one: the CDN URL asked for a size and the answer is in
                # the query string it was asked with.
                qs = dict(re.findall(r"[?&](w|h)=(\d+)", url))
                if not (qs.get("w") and qs.get("h")):
                    skipped.append(rel or tag[:40])
                    out.append(tag)
                    continue
                w, h = int(qs["w"]), int(qs["h"])
            tag = tag.replace(' loading=', ' width="%d" height="%d" loading=' % (w, h), 1) \
                if " loading=" in tag else \
                tag[:-1] + ' width="%d" height="%d">' % (w, h)
            out.append(tag)
            changed += 1
        out.append(src[pos:])
        if changed and write:
            with open(page, "w", encoding="utf-8") as fh:
                fh.write("".join(out))
        done += changed
        if changed:
            log("  %-16s %d image(s) sized" % (os.path.basename(page), changed))
    for rel in skipped:
        log("  could not measure %s" % rel)
    log("%d placed image(s) now reserve their box" % done)
    return done


def run(picks, country, revert=False, dry_run=False, write=True, log=print):
    """Apply a {slot: candidate_id} mapping to the pages. Returns a report."""
    index = pool.load()
    all_placements = pl.scan(country)
    by_slot = {pool.placement_slot(p): p for p in all_placements}

    report = {"placed": 0, "reverted": 0, "skipped": 0, "locked": 0,
              "errors": [], "pages": [], "files": []}

    # Resolve every pick before touching a page, so a bad id fails the run
    # rather than leaving four pages rewritten and the fifth not.
    resolved = {}
    if not revert:
        for slot, candidate_id in (picks or {}).items():
            placement = by_slot.get(slot)
            if not placement:
                report["errors"].append("no such slot on the site: %s" % slot)
                continue
            if placement["locked"]:
                report["locked"] += 1
                continue
            candidate = index.find(slot, candidate_id)
            if not candidate:
                report["errors"].append("%s: no candidate %r in the pool"
                                        % (slot, candidate_id))
                continue
            if candidate.get("source") not in PLACEABLE:
                report["errors"].append(
                    "%s: %s is a stock photograph — use `resolve` and `adopt` for those"
                    % (slot, candidate_id))
                continue
            try:
                url = publish(slot, candidate, dry_run=dry_run)
            except IOError as exc:
                report["errors"].append(str(exc))
                continue
            entry = country.entry(placement["category"]) if placement["category"] else None
            resolved[slot] = (placement, candidate, url,
                              placement["instruction"],
                              entry.focal if entry else {"x": 50, "y": 50})
            report["files"].append(url)
    if report["errors"]:
        return report

    for page in pl.PAGES:
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        html = open(path).read()
        changed = 0
        page_slots = {pool.placement_slot(p): p for p in all_placements if p["page"] == page}

        def replace(m):
            nonlocal changed
            tag = m.group(0)
            attrs = dict(adopt.ATTR_RE.findall(tag))
            if attrs.get("data-locked") == "true":
                report["locked"] += 1
                return tag
            illustration = attrs.get("data-illustration") or attrs.get("src") or ""
            slot = "site:%s:%s" % (page.rsplit(".", 1)[0], pl.slot_id(illustration))
            if slot not in page_slots:
                return tag
            if revert:
                if attrs.get("data-placed") == "true":
                    changed += 1
                    report["reverted"] += 1
                    return revert_tag(tag)
                return tag
            if slot not in resolved:
                report["skipped"] += 1
                return tag
            _placement, candidate, url, alt, focal = resolved[slot]
            new = rewrite_tag(tag, url, candidate, alt, focal)
            if new != tag:
                changed += 1
            report["placed"] += 1
            return new

        out = adopt.IMG_RE.sub(replace, html)
        if write and not dry_run and out != html:
            open(path, "w").write(out)
        report["pages"].append((page, changed))

    if not revert and not dry_run and resolved:
        # Mark what is live, so the contact sheet can show it next time.
        for slot, (_p, candidate, _u, _a, _f) in resolved.items():
            for other in index.all(slot):
                other["inUse"] = other.get("id") == candidate.get("id")
        index.save()
    return report


def load_picks(path):
    import json
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "picks" in raw:
        raw = raw["picks"]
    if not isinstance(raw, dict):
        raise ValueError("picks file must be an object of slot -> candidate id")
    return raw
