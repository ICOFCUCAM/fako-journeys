"""Generate candidate images from the dataset, for comparison against the
stock photographs.

    export OPENAI_API_KEY=...
    python3 tools/tourism/build.py prompts  --country cameroon   # read them first
    python3 tools/tourism/build.py generate --country cameroon --dry-run
    python3 tools/tourism/build.py generate --country cameroon

Nothing generated here goes near the live site. The bytes land in
tourism/candidates/, alongside whatever Unsplash and Pexels produced for the
same slot, and `compare` builds a contact sheet to choose from. A candidate only
becomes a published image when `pick` promotes it, which is a separate command
with a separate argument, because generation is cheap and publishing a synthetic
photograph of a real place is not a decision to make by accident.

Two rules carried over from the resolver, for the same reasons:

  * the key is read from the environment by a CLI on a developer or CI machine.
    It is never written to the cache, rendered into a page, committed, or sent
    to a browser.
  * nothing is recorded that was not actually produced. The API returns image
    bytes; those bytes are written to disk and the file is measured. There is no
    path here that writes a candidate for an image that does not exist.
"""

import base64
import datetime
import json
import os
import struct
import urllib.error
import urllib.request

from . import candidates as pool
from . import prompting
from .model import ROOT
from .providers import RateLimited, Unavailable
from .providers.generated import Generated

CANDIDATE_DIR = os.path.join(ROOT, "tourism", "candidates")
UA = "fako-journeys-tourism-image-system/2"

# What each image costs, so a run can say so before it spends anything. These
# are list prices at the time of writing and they move; they are shown as an
# estimate and labelled as one.
PRICE_USD = {
    ("1024x1024", "low"): 0.011, ("1024x1024", "medium"): 0.042, ("1024x1024", "high"): 0.167,
    ("1536x1024", "low"): 0.016, ("1536x1024", "medium"): 0.063, ("1536x1024", "high"): 0.25,
    ("1024x1536", "low"): 0.016, ("1024x1536", "medium"): 0.063, ("1024x1536", "high"): 0.25,
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_base():
    """Call-time, never import-time: the tests point this at a local mock, and a
    module-level read would freeze whatever the value was when build.py imported
    this file."""
    return os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"


def estimate(size, quality, count):
    unit = PRICE_USD.get((size, quality))
    return None if unit is None else round(unit * count, 2)


# ---- reading back what we were given ------------------------------------------


def png_size(data):
    """(width, height) from the PNG header, so the recorded dimensions are the
    file's own and not what we asked for."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def jpeg_size(data):
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return int(w), int(h)
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def measure(data):
    return png_size(data) or jpeg_size(data)


# ---- the API -------------------------------------------------------------------


class Client:
    """The thinnest possible gpt-image-1 client: one POST, stdlib only.

    The response carries base64 image data rather than a URL, so there is
    nothing to fetch afterwards and nothing to verify over HTTP — the bytes
    either decoded into an image with readable dimensions or they did not.
    """

    def __init__(self, provider=None, model=None, quality="high"):
        self.provider = provider or Generated()
        self.model = model or "gpt-image-1"
        self.quality = quality

    def available(self):
        return self.provider.available()

    def preflight(self):
        if not self.available():
            raise Unavailable("%s is not set" % self.provider.key_env)

    def generate(self, prompt, size, n=1):
        """-> [(bytes, mime)]. Raises RateLimited on 429, Unavailable on 401."""
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "quality": self.quality,
            "n": n,
        }).encode("utf-8")
        req = urllib.request.Request(
            api_base().rstrip("/") + "/images/generations",
            data=body,
            headers={"User-Agent": UA, "Content-Type": "application/json",
                     **self.provider.auth_headers()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                payload = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                pass
            if exc.code == 429:
                raise RateLimited("openai: rate limited or out of credit. %s" % detail)
            if exc.code in (401, 403):
                raise Unavailable("openai: key rejected (HTTP %d). %s" % (exc.code, detail))
            raise RuntimeError("openai: HTTP %d %s" % (exc.code, detail))

        out = []
        for item in payload.get("data") or []:
            if item.get("b64_json"):
                out.append((base64.b64decode(item["b64_json"]), "image/png"))
        if not out:
            raise RuntimeError("openai: response carried no image data")
        return out


# ---- the run -------------------------------------------------------------------


def slot_dir(slot):
    """One directory per slot. The slot key doubles as the path, with the
    characters a filesystem objects to folded out."""
    return os.path.join(CANDIDATE_DIR, slot.replace(":", "/").replace("/", os.sep))


class Job:
    """One instruction, aimed at one place on the site.

    `where` is the human-readable placement — "index.html · fj-open-plate,
    3:4" — and it is carried through to the contact sheet, because a picture
    that is right for the category and wrong for the slot it was made for is
    the failure mode this whole engine exists to avoid.
    """

    __slots__ = ("slot", "label", "where", "prompt", "size", "aspect", "have")

    def __init__(self, slot, label, where, prompt, size, aspect, have=0):
        self.slot, self.label, self.where = slot, label, where
        self.prompt, self.size, self.aspect, self.have = prompt, size, aspect, have


def jobs_for_placements(country, taxonomy, index, style, only=None):
    """The five hand-written pages: one job per targetable <img>."""
    from . import placements as pl

    out = []
    for p in pl.targetable(pl.scan(country)):
        if only and only not in (p["id"], p["page"], p["category"] or ""):
            continue
        entry = country.entry(p["category"]) if p["category"] else None
        slot = pool.placement_slot(p)
        out.append(Job(
            slot=slot,
            label=p["id"],
            where="%s · %s · %d:%d" % (p["page"], p["wrapper"] or "default",
                                       p["aspect"][0], p["aspect"][1]),
            prompt=prompting.for_placement(country, p, taxonomy, entry, style),
            size=prompting.size_for_aspect(p["aspect"], style),
            aspect=p["aspect"],
            have=len(index.generated(slot)),
        ))
    return out


def jobs_for_categories(country, taxonomy, index, style, only=None):
    """The generated /tourism/<country> page: one job per enabled category."""
    out = []
    for cat in taxonomy.enabled:
        if only and cat["id"] != only:
            continue
        entry = country.entry(cat["id"])
        if not entry:
            continue
        role = taxonomy.role(cat["id"])
        slot = pool.category_slot(country.slug, cat["id"])
        out.append(Job(
            slot=slot,
            label=cat["id"],
            where="tourism/%s.html · %s · %d:%d" % (country.slug, cat["role"],
                                                    role["aspect"][0], role["aspect"][1]),
            prompt=prompting.build(country, cat, entry, role, style),
            size=prompting.size_for(role, style),
            aspect=role["aspect"],
            have=len(index.generated(slot)),
        ))
    return out


def plan_jobs(country, taxonomy, index, style, scope="site", only=None):
    if scope == "tourism":
        return jobs_for_categories(country, taxonomy, index, style, only)
    if scope == "all":
        return (jobs_for_placements(country, taxonomy, index, style, only)
                + jobs_for_categories(country, taxonomy, index, style, only))
    return jobs_for_placements(country, taxonomy, index, style, only)


def run(country, taxonomy, scope="site", only=None, n=1, dry_run=False,
        force=False, client=None, style=None, log=print):
    """Generate candidates for every slot in scope. Returns a summary dict.

    Resumable in the same way the resolver is: a slot that already has as many
    generated candidates as asked for is skipped unless --force, so re-running
    after a rate limit or a half-finished run costs nothing.
    """
    style = style or prompting.load_style()
    model_cfg = style.get("model") or {}
    quality = model_cfg.get("quality", "high")
    client = client or Client(model=model_cfg.get("model"), quality=quality)
    index = pool.load()

    jobs = plan_jobs(country, taxonomy, index, style, scope, only)
    todo = [j for j in jobs if force or j.have < n]
    wanted = {j.slot: (n if force else n - j.have) for j in todo}
    total = sum(wanted.values())
    cost = sum(estimate(j.size, quality, wanted[j.slot]) or 0 for j in todo)

    log("%d slot(s) in scope, %d to fill, %d image(s) at %s quality  ~$%.2f estimated"
        % (len(jobs), len(todo), total, quality, cost))
    if not todo:
        log("nothing to do — every slot already has %d generated candidate(s). "
            "--force regenerates." % n)
        return {"generated": 0, "skipped": len(jobs), "failed": 0, "cost": 0.0}

    if dry_run:
        for j in todo:
            log("\n%s  [%s]  ->  %s" % (j.label, j.size, j.where))
            log("  %s" % j.prompt)
        log("\ndry run: nothing was sent, nothing was written, nothing was charged.")
        return {"generated": 0, "skipped": len(jobs) - len(todo), "failed": 0,
                "cost": 0.0, "planned": total}

    client.preflight()
    made = failed = 0
    try:
        for j in todo:
            try:
                images = client.generate(j.prompt, j.size, n=wanted[j.slot])
            except RateLimited as exc:
                log("  %-26s stopped: %s" % (j.label, exc))
                raise
            except Exception as exc:
                log("  %-26s failed: %s" % (j.label, exc))
                failed += 1
                continue

            for data, _mime in images:
                dims = measure(data)
                if not dims:
                    log("  %-26s discarded: response was not a readable image" % j.label)
                    failed += 1
                    continue
                directory = slot_dir(j.slot)
                os.makedirs(directory, exist_ok=True)
                # Recounted from the index every time rather than from j.have,
                # which is a snapshot taken before the loop: with n > 1 a
                # snapshot gives every image in the slot the same filename.
                seq = _next_seq(index, j.slot, directory, client.model)
                name = "%s-%02d.png" % (client.model, seq)
                path = os.path.join(directory, name)
                with open(path, "wb") as f:
                    f.write(data)
                index.add(j.slot, {
                    "source": "openai",
                    "model": client.model,
                    "id": "%s/%s" % (j.slot, name),
                    "file": os.path.relpath(path, ROOT).replace(os.sep, "/"),
                    "url": "/" + os.path.relpath(path, ROOT).replace(os.sep, "/"),
                    "width": dims[0],
                    "height": dims[1],
                    "bytes": len(data),
                    "prompt": j.prompt,
                    "where": j.where,
                    "aspect": list(j.aspect),
                    "size": j.size,
                    "quality": quality,
                    "inUse": False,
                    "createdAt": now(),
                })
                made += 1
                log("  %-26s %s  %dx%d  %dKB  ->  %s"
                    % (j.label, name, dims[0], dims[1], len(data) // 1024, j.where))
    finally:
        # Save whatever was produced even if the run was interrupted or the
        # quota ran out half way. Paid-for images are not thrown away.
        index.save()

    log("\ngenerated %d image(s), %d failed" % (made, failed))
    log("candidates are in tourism/candidates/ — nothing on the site has changed.")
    log("next: build.py compare   then   build.py place <picks.json>")
    return {"generated": made, "skipped": len(jobs) - len(todo), "failed": failed,
            "cost": round(cost, 2)}


def _next_seq(index, slot, directory, model):
    """The next free number for this slot.

    Checks the directory as well as the index because --force regenerates
    without dropping the old records, and a file on disk that nobody indexed is
    still a file that would be overwritten.
    """
    used = set()
    for cand in index.generated(slot):
        name = os.path.basename(cand.get("file") or "")
        if name.startswith(model + "-"):
            stem = name[len(model) + 1:].rsplit(".", 1)[0]
            if stem.isdigit():
                used.add(int(stem))
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if name.startswith(model + "-") and name.endswith(".png"):
                stem = name[len(model) + 1:-4]
                if stem.isdigit():
                    used.add(int(stem))
    seq = 1
    while seq in used:
        seq += 1
    return seq
