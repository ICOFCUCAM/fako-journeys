"""Read images somebody uploaded and work out which slot each one belongs in.

    (drop files into incoming/)
    python3 tools/tourism/build.py intake --dry-run     # what it would match
    python3 tools/tourism/build.py intake --describe    # ask the vision model first
    python3 tools/tourism/build.py intake               # add them to the pool

Placement is *proposed*, never applied. Matches land in the candidate pool
alongside the generated and stock options, the contact sheet shows them with
their score and the reason for it, and `place` is still a separate command. A
system that decided by itself where somebody's photographs went would be wrong
often enough to be worse than useless, and confidently wrong at that.

Three signals, cheapest first:

  name        a file named exactly after a slot is that slot's picture. Nothing
              else comes close as a signal, and it costs nothing.
  filename    failing that, the words in the name. "mount-cameroon-dawn-trek.jpg"
              says more about where it goes than any pixel analysis would.
  shape       how much of the frame the slot's crop would discard. A penalty,
              never a veto: every slot on this site crops with object-fit:cover,
              and the drawings these photographs replace were themselves 3:2
              frames cropped to 4:5 and 1:1. A 47% crop of the right picture
              still beats a perfect fit of the wrong one.
  description with --describe, the vision model is asked what the picture
              actually shows, and that sentence is scored against every slot's
              instruction the same way a stock photo's caption is.

Without --describe the matcher runs on shape and filename alone and says so, so
a confident-looking assignment is never mistaken for one the machine actually
looked at.
"""

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request

from . import candidates as pool, generate as gen, placements as pl, prompting
from .model import ROOT
from .providers import RateLimited, Unavailable
from .providers.uploaded import Uploaded

INCOMING = os.path.join(ROOT, "incoming")
EXTS = (".jpg", ".jpeg", ".png", ".webp")

# incoming/generated/ is for pictures a model made — ones you generated in
# ChatGPT or anywhere else and are bringing in by hand. They are matched exactly
# like the rest, but they carry the generated provider, so their credit line
# reads "AI-generated" instead of passing as somebody's photograph. Getting that
# wrong is not a formatting detail: it is a false claim about a real place.
GENERATED_SUBDIR = "generated"

# Words that appear in nearly every slot instruction and so separate nothing.
NOISE = {
    "the", "a", "an", "and", "of", "in", "on", "at", "with", "into", "from",
    "for", "to", "by", "over", "under", "above", "below", "near", "between",
    "img", "image", "photo", "photograph", "final", "copy", "new", "edit",
    "cameroon", "africa", "african",
}

MIN_SCORE = 1.0          # below this it is a guess, not a match
EXACT_NAME = 6.0         # a filename that *is* a slot id — decisive


def words(text):
    out = []
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) > 2 and w not in NOISE and w not in out:
            out.append(w)
    return out


def stem_words(filename):
    """Filenames are not sentences: split on every separator people use."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)      # camelCase
    return words(re.sub(r"[^A-Za-z]+", " ", stem))


# ---- reading the files ---------------------------------------------------------


def scan_folder(directory=None):
    """Every image in the folder, plus any in its generated/ subfolder."""
    directory = directory or INCOMING
    out = []
    for root_dir, origin in ((directory, "upload"),
                             (os.path.join(directory, GENERATED_SUBDIR), "openai")):
        if not os.path.isdir(root_dir):
            continue
        for name in sorted(os.listdir(root_dir)):
            if not name.lower().endswith(EXTS) or name.startswith("."):
                continue
            path = os.path.join(root_dir, name)
            with open(path, "rb") as f:
                head = f.read(2 * 1024 * 1024)
            dims = gen.measure(head)
            out.append({
                "name": name,
                "path": path,
                "origin": origin,
                "rel": os.path.relpath(path, ROOT).replace(os.sep, "/"),
                "width": dims[0] if dims else None,
                "height": dims[1] if dims else None,
                "bytes": os.path.getsize(path),
                "words": stem_words(name),
                "caption": None,
            })
    return out


# ---- asking the model what it is looking at ------------------------------------


def describe(image, style, log=print):
    """One vision call. Returns a sentence, or None if it could not be had."""
    provider = Uploaded()
    if not provider.available():
        raise Unavailable("OPENAI_API_KEY is not set, so --describe cannot run")
    model = (style.get("vision") or {}).get("model") or "gpt-5"
    mime = mimetypes.guess_type(image["path"])[0] or "image/jpeg"
    with open(image["path"], "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")

    body = json.dumps({
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text":
                    "Describe this photograph in one sentence for a travel "
                    "website: what is in it, where it looks like, what the "
                    "people if any are doing. Plain description, no adjectives "
                    "of praise, no guessing at a place name you cannot see."},
                {"type": "image_url",
                 "image_url": {"url": "data:%s;base64,%s" % (mime, data)}},
            ],
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        gen.api_base().rstrip("/") + "/chat/completions",
        data=body,
        headers={"User-Agent": gen.UA, "Content-Type": "application/json",
                 **provider.auth_headers()},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        if exc.code == 429:
            raise RateLimited("openai: rate limited. %s" % detail)
        if exc.code in (401, 403):
            raise Unavailable("openai: key rejected (HTTP %d). %s" % (exc.code, detail))
        log("    could not describe %s: HTTP %d %s" % (image["name"], exc.code, detail))
        return None
    choices = payload.get("choices") or []
    if not choices:
        return None
    return (choices[0].get("message") or {}).get("content")


# ---- matching ------------------------------------------------------------------


def aspect_fit(image, aspect):
    """How well the frame suits the slot's crop: a multiplier, and why.

    Deliberately not a veto. Every image slot on this site is `object-fit:
    cover`, and the illustrations these photographs replace were 3:2 frames
    cropped to 4:5, 1:1 and 5:4 from the start — so "loses 47%" describes normal
    operation here, not a disqualification. It ranks a well-shaped candidate
    above a badly-shaped one and otherwise gets out of the way, because a 47%
    crop of the right subject beats a perfect fit of the wrong one every time.
    """
    if not image.get("width") or not image.get("height"):
        return 0.7, "dimensions unknown"
    have = image["width"] / float(image["height"])
    want = aspect[0] / float(aspect[1])
    kept = min(have, want) / max(have, want)
    # Continuous, not banded. Bands looked tidier and were useless: a frame
    # losing 58% and one losing 73% landed in the same bucket and scored
    # identically, so the ranking they were there to provide did not exist.
    fit = 0.5 + 0.5 * kept
    if kept >= 0.92:
        return fit, "fits %d:%d" % tuple(aspect)
    lost = "%d:%d crop discards %d%%" % (aspect[0], aspect[1], round((1 - kept) * 100))
    return fit, lost + ("" if kept >= 0.5 else " — check the subject survives it")


def names_slot(image, placement):
    """The filename is the slot id. `waza-elephants.jpg` -> the waza-elephants
    slot, which is not a guess — it is the same identifier."""
    stem = os.path.splitext(image["name"])[0].strip().lower()
    return stem == (placement["id"] or "").lower()


def score(image, placement):
    """(score, reasons) for one image in one slot."""
    reasons = []
    fit, why = aspect_fit(image, placement["aspect"])
    reasons.append(why)

    target = set(words(placement["instruction"]))
    total = 0.0

    if names_slot(image, placement):
        total += EXACT_NAME
        reasons.insert(0, "named for this slot")

    hits = [w for w in image["words"] if w in target]
    if hits:
        total += 1.4 * len(hits)
        reasons.append("filename says %s" % ", ".join(hits))

    if image.get("caption"):
        cap = set(words(image["caption"]))
        shared = sorted(cap & target)
        if shared:
            total += 1.1 * len(shared)
            reasons.append("described as %s" % ", ".join(shared[:6]))
        else:
            total -= 1.0
            reasons.append("description matches nothing in this slot")

    if placement.get("category"):
        cat_words = set(words(placement["category"].replace("-", " ")))
        cat_hits = [w for w in image["words"] + words(image.get("caption")) if w in cat_words]
        if cat_hits:
            total += 0.6
            reasons.append("category %s" % placement["category"])

    if image.get("width") and image["width"] < placement["width"]:
        total -= 0.5
        reasons.append("smaller than the %dpx this slot delivers" % placement["width"])

    return round(total * fit, 2), reasons


def assign(images, placements):
    """Greedy global assignment: best pair first, one image per slot.

    Greedy rather than optimal on purpose. The alternative is a full assignment
    solve, which would shuffle a confident match into a worse slot to improve
    the total — and the person reviewing this wants their obvious matches where
    they obviously go, not a better sum.
    """
    pairs = []
    for image in images:
        for p in placements:
            s, why = score(image, p)
            if s >= MIN_SCORE:
                pairs.append((s, why, image, p, names_slot(image, p)))
    pairs.sort(key=lambda t: -t[0])

    used_images, used_slots, matched = set(), set(), []
    for s, why, image, p, exact in pairs:
        slot = pool.placement_slot(p)
        if slot in used_slots:
            continue
        # One image per slot always. One slot per image *unless* the filename is
        # the slot id: the same illustration fills the same subject on two pages
        # at two shapes, and a photograph named after it belongs in both, the
        # same way the drawing did.
        if image["name"] in used_images and not exact:
            continue
        used_images.add(image["name"])
        used_slots.add(slot)
        matched.append({"score": s, "reasons": why, "image": image,
                        "placement": p, "slot": slot})
    unmatched = [i for i in images if i["name"] not in used_images]
    return matched, unmatched


# ---- the run -------------------------------------------------------------------


def run(country, taxonomy, directory=None, do_describe=False, dry_run=False,
        log=print):
    style = prompting.load_style()
    images = scan_folder(directory)
    directory = directory or INCOMING
    if not images:
        log("no images in %s/ — drop .jpg, .png or .webp files there and run again."
            % os.path.relpath(directory, ROOT))
        return {"matched": 0, "unmatched": 0, "described": 0}

    log("%d image(s) in %s/" % (len(images), os.path.relpath(directory, ROOT)))
    described = 0
    if do_describe:
        for image in images:
            image["caption"] = describe(image, style, log=log)
            if image["caption"]:
                described += 1
                log("  %-34s %s" % (image["name"], image["caption"][:90]))
    else:
        log("matching on shape and filename only — add --describe to have the "
            "model look at the pictures.")

    targets = pl.targetable(pl.scan(country))
    matched, unmatched = assign(images, targets)

    index = pool.load()
    for m in matched:
        log("\n  %s%s" % (m["image"]["name"],
                            "  [AI-generated]" if m["image"].get("origin") == "openai" else ""))
        log("    -> %s  (%s · %d:%d)  score %.2f"
            % (m["placement"]["id"], m["placement"]["page"],
               m["placement"]["aspect"][0], m["placement"]["aspect"][1], m["score"]))
        log("       %s" % "; ".join(m["reasons"]))
        log("       slot wants: %s" % m["placement"]["instruction"])
        if not dry_run:
            origin = m["image"].get("origin", "upload")
            index.add(m["slot"], {
                "source": origin,
                "model": "an image model" if origin == "openai" else None,
                "id": "%s:%s" % (origin, m["image"]["name"]),
                "file": m["image"]["rel"],
                "url": "/" + m["image"]["rel"],
                "width": m["image"]["width"],
                "height": m["image"]["height"],
                "bytes": m["image"]["bytes"],
                "caption": m["image"]["caption"],
                "score": m["score"],
                "reasons": m["reasons"],
                "where": "%s · %d:%d" % (m["placement"]["page"],
                                         m["placement"]["aspect"][0],
                                         m["placement"]["aspect"][1]),
                "aspect": list(m["placement"]["aspect"]),
                "matchedOn": "description" if m["image"].get("caption") else "filename",
                "inUse": False,
            })

    if unmatched:
        log("\n%d image(s) matched nothing above the floor:" % len(unmatched))
        for image in unmatched:
            best = max((score(image, p)[0] for p in targets), default=0)
            log("  %-34s best score %.2f — rename it after what it shows, or "
                "run --describe" % (image["name"], best))

    if not dry_run:
        index.save()
        log("\nadded %d proposal(s) to the candidate pool. Nothing has been placed."
            % len(matched))
        log("next: build.py compare   then   build.py place picks.json")
    else:
        log("\ndry run: the pool was not written.")
    return {"matched": len(matched), "unmatched": len(unmatched), "described": described}
