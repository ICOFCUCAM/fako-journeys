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
THE LAYOUT ON R2, AND THE URL THE SITE ASKS FOR

    images.afrinkong.com
        |
        +-- originals/  kenya/cities/nairobi-green-city-in-the-sun.jpg
        +-- 1600/       kenya/cities/nairobi-green-city-in-the-sun.avif|.webp|.jpg
        +-- 1200/       ...
        +--  800/       ...
        +--  480/       ...

Width first, because that is what the browser is choosing between, and the
name underneath it never changes. `originals/` is kept so a better encoder, a
new width or a different quality can be produced later without going back to
Pexels for a file we already have — and it is the only copy of the source that
exists once the hotlink is gone.

The site asks for https://images.afrinkong.com/1200/kenya/cities/<slug>.avif
and knows nothing else. Where the photograph came from lives in
tourism/assets.json and never in a URL.

---------------------------------------------------------------------------
NAMING, AND WHY IT IS NOT THE SOURCE'S NAME

`pexels-photo-18000433.jpeg` names a row in somebody else's database. This
names the thing: kenya/cities/nairobi-green-city-in-the-sun. It is stable
across a replacement — commission a better photograph of the same subject and
it takes the same name, the same URL, and every page referencing it needs no
edit at all. That is the property that makes the 786 REPLACE assets a content
job rather than a second migration.

---------------------------------------------------------------------------
THREE FORMATS AT EVERY WIDTH, AND WHY JPEG IS STILL ONE OF THEM

AVIF is taken by about ninety-three per cent of browsers and WebP by
ninety-seven. A <picture> falls through to the <img> when it can take neither,
so the <img> has to be the format everything reads. Three per cent of a
premium travel site's visitors seeing no photograph at all is not a saving.
JPEG costs the most bytes and is served the least often, which is the right
way round.
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
JPEG_Q = 82
FORMATS = (".avif", ".webp", ".jpg")


def key(name, width=None, ext=".avif"):
    """The object key on R2 for one photograph at one width, or its original."""
    if width is None:
        return "originals/%s.jpg" % name
    return "%d/%s%s" % (width, name, ext)

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


def pilot(reg, n):
    """A representative n, not the first n.

    Alphabetical order would take twenty-five photographs of Algeria and prove
    nothing about the other fifty-three countries or the other twenty-six
    categories. This spreads the pick across countries first and categories
    second, and prefers the photographs used on the most pages — so the pilot
    is looked at by the most visitors and any problem in it shows up soonest.
    """
    rows = sorted(reg["assets"].values(),
                  key=lambda a: (-len(a.get("pages") or []), a["name"]))
    out, taken = [], set()
    # One country at a time, most-used photograph first. A sample that is
    # twenty-five photographs of Algeria proves nothing about the other
    # fifty-three, and country is the axis this site's content is organised on.
    for axis in (lambda a: a["name"].split("/")[0],
                 lambda a: "/".join(a["name"].split("/")[:2])):
        seen = set()
        for a in rows:
            if len(out) >= n:
                break
            k = axis(a)
            if k in seen or a["name"] in taken:
                continue
            seen.add(k)
            taken.add(a["name"])
            out.append(a)
    for a in rows:                       # top up if both axes ran out first
        if len(out) >= n:
            break
        if a["name"] not in taken:
            taken.add(a["name"])
            out.append(a)
    return out[:n]


def fetch(write=False, log=print, limit=0):
    """Download exactly the planned set. NEEDS NETWORK — a workflow step.

    One original per photograph, at the largest width the ladder will use, and
    a sha256 of what arrived so a later run can tell a re-download from a
    replacement. Nothing outside the register is ever fetched.
    """
    reg = register()
    todo = [a for a in reg["assets"].values() if not a.get("sha256")]
    if limit:
        # The pilot is a sample of the library, not its first page.
        spread = pilot(reg, limit)
        todo = [a for a in spread if not a.get("sha256")]
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
    """The ladder, laid out the way R2 will hold it. No network.

    Three formats at four widths from the staged original, written under
    images/library/<width>/<name>.<ext> so that directory IS the bucket's
    shape and `publish` is a copy rather than a translation. A width larger
    than the original is skipped: upscaling a photograph to fill a rung of the
    ladder invents detail, and a browser asked to choose between 1200 and a
    fake 1600 will take the fake one.
    """
    try:
        from PIL import Image
    except ImportError:
        log("library encode: Pillow is not installed")
        return 1
    reg = register()
    out_root = os.path.join(ROOT, "images", "library")
    made, skipped, bytes_out = 0, 0, 0
    for a in reg["assets"].values():
        src = os.path.join(STAGE, a["name"].replace("/", "__") + ".jpg")
        if not os.path.exists(src):
            skipped += 1
            continue
        if not write:
            made += len(LADDER) * len(FORMATS)
            continue
        widths = []
        with Image.open(src) as im:
            im = im.convert("RGB")
            # The original, kept as it arrived: a better encoder or a new width
            # later must not mean going back to Pexels for a file we already
            # hold, and after the rewrite this is the only copy that exists.
            orig = os.path.join(out_root, key(a["name"], None))
            os.makedirs(os.path.dirname(orig), exist_ok=True)
            im.save(orig, quality=94)
            bytes_out += os.path.getsize(orig)
            for w in LADDER:
                if w > im.width:
                    continue
                widths.append(w)
                small = im.resize((w, round(im.height * w / im.width)),
                                  Image.LANCZOS)
                for ext, kw in ((".avif", {"quality": AVIF_Q}),
                                (".webp", {"quality": WEBP_Q, "method": 5}),
                                (".jpg", {"quality": JPEG_Q, "optimize": True})):
                    dst = os.path.join(out_root, key(a["name"], w, ext))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    small.save(dst, **kw)
                    bytes_out += os.path.getsize(dst)
                    made += 1
        a["widths"] = widths
        a["encodedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if write:
        _write_register(reg, log=log)
    log("library encode: %d file(s) %s (%.1f MB), %d asset(s) not yet downloaded"
        % (made, "written" if write else "would be written",
           bytes_out / 1e6, skipped))
    return 0


def publish(write=False, log=print):
    """Copy images/library/ to the R2 bucket. NEEDS NETWORK AND CREDENTIALS.

    R2 speaks the S3 API, so this is boto3 against an account-specific
    endpoint. Four secrets, all repository secrets and none of them ever in a
    working copy:

        R2_ACCOUNT_ID  R2_ACCESS_KEY_ID  R2_SECRET_ACCESS_KEY  R2_BUCKET

    Cache-Control is set here rather than at the CDN because these objects are
    immutable by construction: a name identifies a photograph at a width in a
    format, and a replacement is a different photograph under the same name
    only when somebody has decided it should be. A year, and the same
    `immutable` the site's own /images already carries.
    """
    try:
        import boto3
    except ImportError:
        log("library publish: boto3 is not installed — this is a workflow step")
        return 1
    need = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        log("library publish: missing %s" % ", ".join(missing))
        return 1

    root = os.path.join(ROOT, "images", "library")
    if not os.path.isdir(root):
        log("library publish: nothing encoded yet")
        return 1
    types = {".avif": "image/avif", ".webp": "image/webp", ".jpg": "image/jpeg"}
    client = boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com" % os.environ["R2_ACCOUNT_ID"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto")
    bucket = os.environ["R2_BUCKET"]

    sent, size = 0, 0
    for base, _dirs, files in os.walk(root):
        for name in sorted(files):
            full = os.path.join(base, name)
            k = os.path.relpath(full, root).replace(os.sep, "/")
            if not write:
                sent += 1
                size += os.path.getsize(full)
                continue
            client.upload_file(full, bucket, k, ExtraArgs={
                "ContentType": types.get(os.path.splitext(name)[1], "application/octet-stream"),
                "CacheControl": "public, max-age=31536000, immutable"})
            sent += 1
            size += os.path.getsize(full)
    log("library publish: %d object(s) %s (%.1f MB)"
        % (sent, "uploaded" if write else "would be uploaded", size / 1e6))
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


def thirdparty(log=print):
    """Step eleven: does a visitor's browser still reach Pexels or Unsplash?

    Counted in the built HTML rather than in a browser, because the browser
    only requests what is on the screen and this has to see every page. The
    number that matters is not "did the pilot work" — it is how far the site
    still is from the target, which is zero.

    A migrated photograph should leave nothing behind: no <img>, no <source>,
    no preload. Anything still pointing at a provider is either a REPLACE
    waiting for art direction, a REVIEW waiting for a person, or a bug.
    """
    reg = register()
    migrated = {a["originalUrl"] for a in reg["assets"].values()
                if a.get("encodedAt") and a.get("originalUrl")}
    left, leaked, pages = 0, [], 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                html = fh.read()
            hits = re.findall(r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+", html)
            if not hits:
                continue
            pages += 1
            left += len(hits)
            for h in hits:
                if h.split("?")[0] in {u.split("?")[0] for u in migrated}:
                    leaked.append(h)

    ok = not leaked
    log("%s\tno migrated photograph is still fetched from a provider\t%s"
        % ("PASS" if ok else "FAIL",
           "nothing left behind" if ok
           else "%d reference(s) survived the rewrite" % len(leaked)))
    log("        third-party image references remaining: %d across %d page(s) "
        "— the REPLACE and REVIEW sets, and the KEEP rows not yet migrated"
        % (left, pages))
    return 0 if ok else 1


def rewrite(write=False, revert=False, log=print):
    """Point every migrated <img> at the library, or put it back. Gated on live.

    A rewrite before publication is 1,529 pages of broken photographs, so the
    gate is the register's own `live` flag and not a comment asking somebody to
    be careful. Only assets that have actually been encoded are rewritten — a
    row that has been planned but not fetched is left hotlinked, which is why
    the pilot can migrate twenty-five photographs and leave six hundred alone.

    ROLLBACK IS THE SAME PASS RUN BACKWARDS. Every asset keeps its
    `originalUrl`, so --revert restores exactly the URL that was there before,
    from the register rather than from a backup that could drift. That is step
    twelve of the pilot and it has to work before step thirteen is allowed.
    """
    reg = register()
    if not revert and not reg.get("live"):
        log("library rewrite: refused. tourism/assets.json says live: false — "
            "publish the ladder to %s and set it." % reg.get("host"))
        return 1

    host = reg.get("host", "").rstrip("/")
    ready = {a["originalUrl"]: a for a in reg["assets"].values()
             if a.get("originalUrl") and a.get("encodedAt") and a.get("widths")}
    if not ready:
        log("library rewrite: nothing has been encoded yet")
        return 0

    def sources(a):
        """The <picture> for one asset: AVIF, then WebP, then a JPEG <img>."""
        out = []
        for ext, mime in ((".avif", "image/avif"), (".webp", "image/webp")):
            ladder = ", ".join("%s/%s %dw" % (host, key(a["name"], w, ext), w)
                               for w in a["widths"])
            out.append('<source type="%s" srcset="%s">' % (mime, ladder))
        return "".join(out)

    changed, pages = 0, 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            full = os.path.join(base, name)
            with open(full, encoding="utf-8") as fh:
                html = fh.read()
            before = html
            if revert:
                for a in reg["assets"].values():
                    if not a.get("originalUrl"):
                        continue
                    widest = "%s/%s" % (host, key(a["name"], a["widths"][-1], ".jpg")) \
                        if a.get("widths") else None
                    if widest and widest in html:
                        html = html.replace(widest, a["originalUrl"])
            else:
                for url, a in ready.items():
                    if url not in html:
                        continue
                    html = html.replace(
                        url, "%s/%s" % (host, key(a["name"], a["widths"][-1], ".jpg")))
            if html == before:
                continue
            pages += 1
            changed += 1
            if write:
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(html)

    log("library %s: %d page(s) %s"
        % ("revert" if revert else "rewrite", pages,
           "rewritten" if write else "would change"))
    return 0
