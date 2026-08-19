"""The Afrinkong image library: plan, fetch, encode, register, rewrite, verify.

    python3 tools/tourism/build.py library plan       # names and sizes, no network
    python3 tools/tourism/build.py library fetch      # downloads the approved set
    python3 tools/tourism/build.py library encode     # AVIF + WebP at four widths
    python3 tools/tourism/build.py library verify     # every hosted file has a origin
    python3 tools/tourism/build.py library rewrite    # point the pages at us

The target is one sentence: a visitor should reach an Afrinkong URL, not
Pexels. Everything here exists to get from 1,426 hotlinks to that, without
putting several gigabytes into git and without hosting a single file this
project cannot say the origin of.

---------------------------------------------------------------------------
THE SIX STEPS, AND WHICH OF THEM CAN RUN WHERE

  plan      reads data/asset-inventory.json, takes only the KEEP set, and
            gives each photograph a stable Afrinkong name. No network.
  fetch     downloads exactly the planned set, at the largest useful size,
            and records provenance including a checksum. NEEDS NETWORK.
  encode    AVIF and WebP at four widths from what fetch put on disk. No
            network, and the same qualities the `modern` pass measured.
  publish   uploads the encoded ladder to object storage. NEEDS NETWORK AND
            CREDENTIALS. Deliberately not implemented here — see below.
  rewrite   a late pass over the built HTML swapping every external URL for
            its first-party one. REFUSES to run until the register says the
            library is live, because a rewrite before publication is 1,529
            pages of broken photographs.
  verify    every asset in the register has a source, a photographer, a
            licence and a page using it; every rewritten URL resolves to a
            registered asset. Runs anywhere.

fetch and publish are the two that need the internet, and this repository has
an established place for that: .github/workflows/. The development environment
here cannot reach images.pexels.com at all — the proxy answers 403 to the
CONNECT — so those two steps are workflow steps by necessity and not by
preference.

---------------------------------------------------------------------------
WHY NO IMAGE-TRANSFORM SERVICE

A resize-on-the-fly CDN (Cloudinary, imgix, Vercel's own) would make encode and
publish disappear. It would also make the thing this whole exercise is removing
— an uncontrolled third party between the visitor and the photograph — reappear
under a different name, with a bill attached to traffic. The ladder is built
once at publish time and served as static files, so the only thing between a
visitor and a photograph is object storage.

---------------------------------------------------------------------------
NAMING, AND WHY IT IS NOT THE SOURCE'S NAME

    <country>/<category>/<slug>-<width>.avif

`pexels-photo-18000433.jpeg` names a row in somebody else's database. This
names the thing: kenya/cities/nairobi-green-city-in-the-sun-1200.avif. It is
stable across a replacement — commission a better photograph of the same
subject and it takes the same name, the same URL, and every page that
references it needs no edit at all. That is the property that makes the 496
REPLACE assets a content job rather than another migration.
"""

import hashlib
import json
import os
import re
import time
import urllib.request

from .model import ROOT

INVENTORY = os.path.join(ROOT, "data", "asset-inventory.json")
REGISTER = os.path.join(ROOT, "tourism", "assets.json")
STAGE = os.path.join(ROOT, "incoming", "library")

# The widths this site actually paints, from data/sizes.json's own measurements.
LADDER = (480, 800, 1200, 1600)
AVIF_Q = 62
WEBP_Q = 82

# What each provider's licence is, as a fact about the provider rather than a
# claim about one photograph. The per-photograph half of provenance — who took
# it and where it came from — is recorded per row.
LICENCES = {
    "pexels": {"name": "Pexels License",
               "url": "https://www.pexels.com/license/"},
    "unsplash": {"name": "Unsplash License",
                 "url": "https://unsplash.com/license"},
}

SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text, fallback="image"):
    out = SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return (out or fallback)[:70]


def _read(path, fallback):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def register():
    return _read(REGISTER, {
        "$comment": "The Afrinkong image library. One row per hosted "
                    "photograph: where it came from, who took it, under what "
                    "licence, when it was taken down, what we call it, and "
                    "which pages use it. Written by tools/tourism/library.py. "
                    "`live` stays false until the assets are actually on the "
                    "asset host; the rewrite pass refuses to run while it is.",
        "host": "https://images.afrinkong.com",
        "live": False,
        "assets": {},
    })


def _write_register(reg, log=print):
    with open(REGISTER, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=1, ensure_ascii=False)
    log("  register: %d asset(s) in %s"
        % (len(reg["assets"]), os.path.relpath(REGISTER, ROOT)))


def plan(write=False, log=print):
    """Name every approved photograph. Reads the inventory, writes no bytes."""
    inv = _read(INVENTORY, None)
    if not inv:
        log("library: no data/asset-inventory.json — run `build.py assets --fetch`")
        return 1

    keep = [a for a in inv["assets"] if a["verdict"] == "KEEP"]
    reg = register()
    # A fresh set, not a merge. The register is the current approved list, and
    # a photograph that has been reclassified out of KEEP has to leave it —
    # otherwise a later fetch downloads something the audit has since refused.
    # What carries forward is only what a re-plan cannot recompute: the date it
    # was taken down and the checksum of what arrived.
    previous = reg.get("assets") or {}
    reg["assets"] = {}
    named, clash = {}, 0
    for a in keep:
        country = _slug(a.get("country") or "world")
        category = _slug(a.get("category") or "general")
        stem = _slug(a.get("caption") or a.get("altIntended") or a.get("photoId"))
        name = "%s/%s/%s" % (country, category, stem)
        # A collision means two photographs claim one subject; the id keeps
        # them apart rather than one silently overwriting the other.
        if name in named:
            clash += 1
            name = "%s-%s" % (name, a["photoId"][:8])
        named[name] = a
        reg["assets"][name] = {
            "name": name,
            "provider": a["provider"],
            "photoId": a["photoId"],
            "photographer": a.get("photographer"),
            "photographerUrl": a.get("photographerUrl"),
            "sourceUrl": a.get("sourceUrl"),
            "originalUrl": a.get("imageUrl"),
            "licence": LICENCES.get(a["provider"], {}),
            "chosenAt": a.get("chosenAt"),
            "downloadedAt": previous.get(name, {}).get("downloadedAt"),
            "sha256": previous.get(name, {}).get("sha256"),
            "slot": a.get("slot"),
            "alt": a.get("alt"),
            "width": a.get("width"),
            "height": a.get("height"),
            "pages": a.get("pages", []),
            "widths": list(LADDER),
        }

    log("")
    log("  library plan")
    log("  ---------------------------------------------------------------")
    log("  approved for hosting        %6d" % len(keep))
    log("  names assigned              %6d  (%d disambiguated by photo id)"
        % (len(named), clash))
    log("  widths per photograph       %6d  %s" % (len(LADDER), list(LADDER)))
    log("  files to publish            %6d  (AVIF + WebP)"
        % (len(named) * len(LADDER) * 2))
    log("  host                        %s  (live: %s)"
        % (reg["host"], reg["live"]))
    log("")
    if write:
        _write_register(reg, log=log)
    else:
        log("  dry run — add --fetch to write the register")
    return 0


def fetch(write=False, log=print, limit=0):
    """Download exactly the planned set. NEEDS NETWORK — a workflow step.

    One original per photograph, at the largest width the ladder will use, and
    a sha256 of what arrived so a later run can tell a re-download from a
    replacement. Nothing outside the register is ever fetched.
    """
    reg = register()
    todo = [a for a in reg["assets"].values() if not a.get("sha256")]
    if limit:
        todo = todo[:limit]
    if not write:
        log("library fetch: %d of %d asset(s) not yet downloaded. dry run."
            % (len(todo), len(reg["assets"])))
        return 0

    os.makedirs(STAGE, exist_ok=True)
    got, failed = 0, []
    for a in todo:
        url = a.get("originalUrl") or ""
        if not url:
            failed.append((a["name"], "no source url"))
            continue
        # Ask each provider for the widest size the ladder needs and no more.
        sep = "&" if "?" in url else "?"
        want = "%s%sw=%d" % (url, sep, LADDER[-1])
        out = os.path.join(STAGE, a["name"].replace("/", "__") + ".jpg")
        try:
            req = urllib.request.Request(want, headers={"User-Agent": "afrinkong-library"})
            with urllib.request.urlopen(req, timeout=45) as res:
                body = res.read()
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(body)
            a["sha256"] = hashlib.sha256(body).hexdigest()
            a["downloadedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            a["bytes"] = len(body)
            got += 1
        except Exception as exc:                       # noqa: BLE001 — report, continue
            failed.append((a["name"], str(exc)[:70]))
    log("library fetch: %d downloaded, %d failed" % (got, len(failed)))
    for name, why in failed[:5]:
        log("  %s — %s" % (name, why))
    _write_register(reg, log=log)
    return 0


def encode(write=False, log=print):
    """AVIF and WebP at four widths, from whatever fetch staged. No network."""
    try:
        from PIL import Image
    except ImportError:
        log("library encode: Pillow is not installed")
        return 1
    reg = register()
    made, skipped = 0, 0
    out_root = os.path.join(ROOT, "images", "library")
    for a in reg["assets"].values():
        src = os.path.join(STAGE, a["name"].replace("/", "__") + ".jpg")
        if not os.path.exists(src):
            skipped += 1
            continue
        if not write:
            made += len(LADDER) * 2
            continue
        with Image.open(src) as im:
            im = im.convert("RGB")
            for w in LADDER:
                if w > im.width:
                    continue
                h = round(im.height * w / im.width)
                small = im.resize((w, h), Image.LANCZOS)
                for ext, kw in ((".avif", {"quality": AVIF_Q}),
                                (".webp", {"quality": WEBP_Q, "method": 5})):
                    dst = os.path.join(out_root, "%s-%d%s" % (a["name"], w, ext))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    small.save(dst, **kw)
                    made += 1
    log("library encode: %d file(s) %s, %d asset(s) not yet downloaded"
        % (made, "written" if write else "would be written", skipped))
    return 0


def verify(log=print):
    """No hosted file without an origin, and no rewritten URL without a file.

    This is the rule the library exists to keep. A photograph whose
    photographer, source page or licence is unknown is not published, and a
    page that points at the asset host must point at something the register
    knows about.
    """
    reg = register()
    bad = []
    for name, a in reg["assets"].items():
        for field in ("provider", "photoId", "sourceUrl", "originalUrl"):
            if not a.get(field):
                bad.append("%s: no %s" % (name, field))
        if not (a.get("licence") or {}).get("url"):
            bad.append("%s: no licence" % name)
        if not a.get("photographer"):
            bad.append("%s: no photographer" % name)
        if not a.get("pages"):
            bad.append("%s: no page uses it" % name)

    host = reg.get("host", "")
    unknown = []
    if host:
        pat = re.compile(re.escape(host) + r"/([\w/\-]+?)-\d+\.(?:avif|webp|jpg)")
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in
                       ("node_modules", ".git", "incoming", "tools")
                       and not d.startswith(".")]
            for name in files:
                if not name.endswith(".html"):
                    continue
                with open(os.path.join(base, name), encoding="utf-8") as fh:
                    html = fh.read()
                if host not in html:
                    continue
                for m in pat.finditer(html):
                    if m.group(1) not in reg["assets"]:
                        unknown.append(m.group(1))

    ok = not bad and not unknown
    log("%s\tevery hosted photograph has an origin\t%s"
        % ("PASS" if not bad else "FAIL",
           "%d asset(s) registered" % len(reg["assets"]) if not bad
           else "%d problem(s): %s" % (len(bad), "; ".join(bad[:3]))))
    log("%s\tevery first-party image URL is a registered asset\t%s"
        % ("PASS" if not unknown else "FAIL",
           "nothing points at an unregistered file" if not unknown
           else "%d unknown: %s" % (len(unknown), ", ".join(sorted(set(unknown))[:3]))))
    return 0 if ok else 1


def rewrite(write=False, log=print):
    """Point every external <img> at the library. Refuses until it is live.

    A rewrite before publication is 1,529 pages of broken photographs, so the
    gate is the register's own `live` flag rather than a comment asking
    somebody to be careful.
    """
    reg = register()
    if not reg.get("live"):
        log("library rewrite: refused. tourism/assets.json says live: false — "
            "publish the ladder to %s first, then set it." % reg.get("host"))
        return 1
    log("library rewrite: not implemented until the host is live and the "
        "ladder is on it; the URL shape it will write is "
        "%s/<name>-<width>.avif" % reg.get("host"))
    return 0
