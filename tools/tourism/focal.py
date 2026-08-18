"""Move the crop off dead centre, from the photograph rather than from taste.

    python3 tools/tourism/build.py focal            what it would change
    python3 tools/tourism/build.py focal --fetch    write it

WHAT WAS WRONG

A hundred and sixty-eight slots in three roles that crop hard — hero,
panoramic and portrait — sat at 50,50, which validate.py has been warning
about for as long as it has existed. Fifty per cent is not a decision about a
photograph, it is the absence of one, and in a tall portrait box it is the
setting most likely to take the top off whatever the picture is of.

WHAT THIS CAN AND CANNOT KNOW

It cannot see. There is no face detector here and no model, so it does not know
where a person is; what it has is where the DETAIL is. Downscale to 160 pixels,
take the edge magnitude, and find the centroid of that energy: a sky is flat, a
skyline is not, a herd on plain grass is not. That is a proxy and it is honest
to call it one.

Which is why every number it produces is damped and clamped. The centroid is
pulled 55% of the way back towards the middle and then held inside 30–70, so
the worst case is a crop slightly off centre rather than a crop that has gone
somewhere strange on the strength of a bright cloud. And a shift smaller than
five points is not written at all: below that the centre was already right and
a number in the file would only look like a decision somebody made.

Only the axis the role actually crops on moves. A panoramic box is wide and
short, so it throws away the top and bottom and keeps the width: its `y`
matters and its `x` barely does. Portrait is the other way round. Hero crops
both. Moving an axis that is not cropped is noise in the dataset that reads
like intent.

THE RIGHT ANSWER IS STILL A PERSON

This is a better starting point than 50,50 and it is not a substitute for
somebody looking at the picture. Anything set by hand is left alone — the pass
only ever touches a slot still sitting on dead centre.
"""

import json
import os
import re

from .model import ROOT

ROLES = ("hero", "panoramic", "portrait")

# What each role actually crops, and so which axis is worth deciding.
AXES = {"hero": ("x", "y"), "panoramic": ("y",), "portrait": ("x",)}

DAMP = 0.55
FLOOR, CEIL = 30, 70
LEAST = 5          # points; below this the centre was already right
PROBE = 160        # px on the long side — detail, not resolution
CACHE = os.path.join(ROOT, "data", "focal-cache.json")


def energy_centroid(im):
    """-> (x%, y%) of where the detail in this image sits.

    Grayscale, downscaled, edge magnitude, weighted mean. The downscale is what
    makes it about composition rather than texture: at 160 pixels a field of
    grass is flat and the animals standing in it are not.
    """
    from PIL import Image, ImageFilter
    g = im.convert("L")
    g.thumbnail((PROBE, PROBE), Image.LANCZOS)
    e = g.filter(ImageFilter.FIND_EDGES)
    w, h = e.size
    px = list(e.getdata())
    total = sx = sy = 0
    for i, v in enumerate(px):
        if v < 12:          # noise floor; a smooth sky should not vote
            continue
        total += v
        sx += v * (i % w)
        sy += v * (i // w)
    if not total or w < 2 or h < 2:
        return 50.0, 50.0
    return (sx / total) / (w - 1) * 100.0, (sy / total) / (h - 1) * 100.0


def propose(im, role):
    """-> {"x": .., "y": ..} for this photograph in this role, or None."""
    cx, cy = energy_centroid(im)
    want = AXES.get(role, ())
    out = {}
    for axis, raw in (("x", cx), ("y", cy)):
        if axis not in want:
            continue
        v = 50 + (raw - 50) * DAMP
        v = max(FLOOR, min(CEIL, v))
        if abs(v - 50) >= LEAST:
            out[axis] = int(round(v))
    return out or None


def _cache():
    try:
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(d):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
        fh.write("\n")


def source_url(rec):
    """-> a small copy of the photograph, from whichever CDN holds it.

    Small on purpose: the centroid is computed at 160 pixels, so fetching a
    1600-wide original to throw 99% of it away would be a hundred megabytes of
    somebody else's bandwidth for a number that does not change.
    """
    u = rec.get("imageUrl") or ""
    if not u:
        return None
    if "images.pexels.com" in u:
        return re.sub(r"[?&](w|h)=\d+", "", u) + (
            "&w=480" if "?" in u else "?w=480")
    if "images.unsplash.com" in u:
        return re.sub(r"[?&]w=\d+", "", u) + ("&w=480" if "?" in u else "?w=480")
    return u


# A BROWSER'S USER AGENT, AND A PAUSE BETWEEN FETCHES.
#
# The first run of this on a runner read one photograph out of 149 and was
# refused the other 148 — in four seconds, which is far too fast to be
# timeouts and exactly right for a CDN answering "no" 148 times. One request
# succeeded and then the burst was cut off, which is what rate limiting looks
# like from the inside.
#
# So: a real User-Agent, because "afrinkong-focal" is the sort of string a CDN
# declines on sight; a fifth of a second between requests, which costs half a
# minute over the whole set and is nothing next to the two minutes the resolver
# already spends; and one retry after a longer wait, because the second refusal
# is the one worth believing.
AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/126.0 Safari/537.36")
PAUSE = 0.2
RETRY_AFTER = 2.0


def fetch(url, role):
    """-> ({"x":..} or {}, None) on success, or (None, why) — with the reason.

    THE REASON IS THE POINT. The first version logged str(exc) truncated to 44
    characters and counted the rest, so a run that was refused 148 times said
    "148 could not be read" and nothing about 403, 429 or DNS. A pass that
    cannot say why it did nothing cannot be fixed from its own output, which is
    the whole reason this returns the status rather than a bool.
    """
    import io
    import time
    import urllib.error
    import urllib.request
    if not url:
        return None, "no imageUrl on the record"
    for attempt in (0, 1):
        try:
            from PIL import Image
            req = urllib.request.Request(url, headers={
                "User-Agent": AGENT,
                "Accept": "image/avif,image/webp,image/jpeg,image/png,*/*",
            })
            with urllib.request.urlopen(req, timeout=25) as r:
                im = Image.open(io.BytesIO(r.read()))
                im.load()
            return (propose(im, role) or {}), None
        except urllib.error.HTTPError as exc:
            why = "HTTP %s" % exc.code
        except Exception as exc:                # noqa: BLE001 — fetch or decode
            why = type(exc).__name__ + ": " + str(exc)[:40]
        if attempt == 0:
            time.sleep(RETRY_AFTER)
    return None, why


def run(write=False, log=print, limit=None):
    import time

    from .cache import load as load_cache
    from .model import attach_cache, load_countries, load_taxonomy

    tax = load_taxonomy()
    countries = attach_cache(load_countries(), load_cache(), tax)
    seen = _cache()
    role_of = dict((c["id"], c["role"]) for c in tax.enabled)

    todo = []
    for c in countries:
        for cat in tax.enabled:
            e = c.entry(cat["id"])
            if not e or role_of.get(cat["id"]) not in ROLES:
                continue
            if (e.focal["x"], e.focal["y"]) != (50, 50):
                continue
            if not e.image or not e.image.get("imageUrl"):
                continue
            todo.append((c, cat["id"], role_of[cat["id"]], e.image))
    if limit:
        todo = todo[:limit]
    if not todo:
        log("every cropping slot with a photograph already has a focal point")
        return 0

    moved, held, failed = [], 0, 0
    reasons = {}
    fetched = 0
    for c, cid, role, rec in todo:
        key = "%s/%s" % (c.slug, cid)
        got = seen.get(key)
        if got is None:
            url = source_url(rec)
            got, why = fetch(url, role)
            if got is None:
                failed += 1
                reasons[why] = reasons.get(why, 0) + 1
                if failed <= 6:
                    log("  %-34s %s" % (key, why))
                continue
            seen[key] = got
            _save(seen)
            fetched += 1
            # Paced, not hammered. See AGENT above.
            time.sleep(PAUSE)
        if not got:
            held += 1
            continue
        moved.append((c, cid, role, got))

    for c, cid, role, got in moved:
        log("  %-34s %-9s -> %s" % ("%s/%s" % (c.slug, cid), role,
                                    ", ".join("%s %d" % kv for kv in sorted(got.items()))))
    if write and moved:
        # SURGERY, NOT A REWRITE.
        #
        # dump_country() is the repository's own writer and using it here
        # reformatted a whole country file — 214 lines in, 295 out — to change
        # two numbers. The dataset is not written in one style: thirty-eight of
        # the fifty-five country files are indented with one space and
        # seventeen with two, so ANY whole-file rewrite reformats one group or
        # the other and buries the change it came to make.
        #
        # So the numbers are edited where they sit. The entry is found by its
        # own category line and the next "focal" after it belongs to that entry
        # — the key order in every one of these files is category, caption,
        # description, subject, focal — and nothing else in the file is
        # touched, at any indent.
        by_country = {}
        for c, cid, _role, got in moved:
            by_country.setdefault(c.slug, []).append((cid, got))
        for slug, items in sorted(by_country.items()):
            path = os.path.join(ROOT, "tourism", "countries", slug + ".json")
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for cid, got in items:
                at = text.find('"category": "%s"' % cid)
                if at < 0:
                    log("  %-34s no such entry in the file" % ("%s/%s" % (slug, cid)))
                    continue
                m = re.compile(r'("focal":\s*\[\s*)(-?\d+)(\s*,\s*)(-?\d+)(\s*\])').search(
                    text, at)
                if not m:
                    log("  %-34s no focal pair after it" % ("%s/%s" % (slug, cid)))
                    continue
                x = str(int(got.get("x", int(m.group(2)))))
                y = str(int(got.get("y", int(m.group(4)))))
                text = (text[:m.start()] + m.group(1) + x + m.group(3) + y
                        + m.group(5) + text[m.end():])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

    log("%s %d crop(s); %d left on centre because the detail was already there"
        "%s" % ("moved" if write else "WOULD move", len(moved), held,
                "; %d could not be read" % failed if failed else ""))
    if reasons:
        log("why they could not be read: %s"
            % ", ".join("%s x%d" % kv for kv in
                        sorted(reasons.items(), key=lambda kv: -kv[1])))
    if not write:
        log("dry run. Add --fetch to write it.")
    return 0
