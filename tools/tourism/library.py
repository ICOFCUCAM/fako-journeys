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

    image.afrinkong.com
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

The site asks for https://image.afrinkong.com/1200/kenya/cities/<slug>.avif
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

import base64
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
        "host": "https://image.afrinkong.com",
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


def reachable(log=print, sample=0):
    """Ask the public host for every object we published. NEEDS NETWORK.

    THIS IS THE STEP THAT CATCHES THE FAILURE `publish` CANNOT.

    `publish` talks to the S3 endpoint with credentials. A visitor talks to
    image.afrinkong.com with none. Those are two different systems and the
    second one can be wrong while the first reports success: the bucket has no
    custom domain bound, or the domain is bound but public access is off, or
    the key prefix on the host is not the key prefix in the bucket. Every one
    of those ends as a 1,529-page site of broken photographs, and every one of
    them is invisible to an upload that returned 200.

    So this walks the encoded ladder, asks the public host for each object by
    the same key `publish` used, and checks four things that a 200 alone does
    not establish:

      - the byte count matches the file on disk, so the host is serving the
        photograph and not a placeholder or an error page that happens to be
        served with a 200;
      - Content-Type is the image type, for the same reason;
      - Cache-Control survived the upload, because a year of immutability is
        the whole economics of putting these on object storage;
      - a key that does not exist answers 404 and not a 200 HTML page, because
        a 200 that is not an image is the one broken-image failure a browser
        cannot report and a monitor cannot see.

    It reports cf-cache-status where Cloudflare sends one. The first request
    for an object is a MISS by definition — that is not a fault, it is what a
    cold cache looks like — so each object is asked for twice and both answers
    are reported.
    """
    import socket
    import urllib.error
    import urllib.parse
    import urllib.request

    reg = register()
    host = (reg.get("host") or "").rstrip("/")
    if not host:
        log("library reachable: the register has no host")
        return 1
    root = os.path.join(ROOT, "images", "library")
    if not os.path.isdir(root):
        log("library reachable: nothing encoded — run encode first")
        return 1

    # RESOLVE THE NAME ONCE BEFORE ASKING IT FOR THREE HUNDRED FILES.
    # The first real run spent two minutes and twenty seconds discovering the
    # same fact 325 times — "Temporary failure in name resolution" against
    # every object — and printed twenty copies of it. One lookup establishes
    # it, and a name that does not resolve is a different problem from a name
    # that resolves and answers 404, so it deserves a different sentence.
    name = urllib.parse.urlsplit(host).hostname or ""
    try:
        socket.getaddrinfo(name, 443)
    except socket.gaierror as exc:
        log("library reachable: %s does not resolve (%s)" % (name, exc))
        log("  The objects may well be in the bucket — publish talks to the")
        log("  S3 endpoint, which is a different name and resolves fine. What")
        log("  is missing is public DNS for %s: either the zone's" % name)
        log("  nameservers do not point at Cloudflare yet, or the custom")
        log("  domain is bound in R2 but the record has not propagated. The")
        log("  R2 dashboard showing the domain as Active is not the same")
        log("  thing as the internet being able to look it up.")
        return 1

    def ask(url, method="HEAD"):
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {})
        except Exception as exc:                      # noqa: BLE001 — report, continue
            return 0, {"x-error": str(exc)}

    keys = []
    for base, _dirs, files in os.walk(root):
        for name in sorted(files):
            full = os.path.join(base, name)
            keys.append((os.path.relpath(full, root).replace(os.sep, "/"),
                         os.path.getsize(full)))
    keys.sort()
    if sample and sample < len(keys):
        step = len(keys) / float(sample)
        keys = [keys[int(i * step)] for i in range(sample)]

    bad, codes, cache, first, second = [], {}, {}, {}, {}
    for k, size in keys:
        url = "%s/%s" % (host, k)
        code, head = ask(url)
        codes[code] = codes.get(code, 0) + 1
        if code != 200:
            bad.append("%s: %s %s" % (k, code, head.get("x-error", "")))
            continue
        got = head.get("Content-Length")
        if got and int(got) != size:
            bad.append("%s: host says %s bytes, disk says %d" % (k, got, size))
        ctype = (head.get("Content-Type") or "").split(";")[0]
        if not ctype.startswith("image/"):
            bad.append("%s: Content-Type is %r, not an image" % (k, ctype))
        cc = head.get("Cache-Control") or ""
        cache[cc] = cache.get(cc, 0) + 1
        if "immutable" not in cc:
            bad.append("%s: Cache-Control is %r" % (k, cc))
        st = (head.get("cf-cache-status") or "-").upper()
        first[st] = first.get(st, 0) + 1
        st2 = (ask(url)[1].get("cf-cache-status") or "-").upper()
        second[st2] = second.get(st2, 0) + 1

    # A name nothing was ever published under. 404 is correct; 200 is the
    # failure mode that renders as a broken image with a successful request.
    miss_code, miss_head = ask("%s/1200/afrinkong/no-such-photograph.avif" % host)
    miss_type = (miss_head.get("Content-Type") or "").split(";")[0]

    log("library reachable: %d object(s) asked of %s" % (len(keys), host))
    log("  status      %s" % ", ".join("%s x%d" % (c, n) for c, n in sorted(codes.items())))
    log("  cache-control %s" % ", ".join("%r x%d" % (c, n) for c, n in cache.items()))
    log("  cf-cache-status  first %s | again %s"
        % (", ".join("%s x%d" % (s, n) for s, n in sorted(first.items())) or "-",
           ", ".join("%s x%d" % (s, n) for s, n in sorted(second.items())) or "-"))
    log("  absent key  %s %s" % (miss_code, miss_type or "(no type)"))
    if miss_code == 200:
        bad.append("a key that does not exist answers 200 — a broken image "
                   "with a successful request is the worst of both")
    for line in bad[:20]:
        log("  ! %s" % line)
    if len(bad) > 20:
        log("  ! ...and %d more" % (len(bad) - 20))
    log("library reachable: %s" % ("OK" if not bad else "%d problem(s)" % len(bad)))
    return 0 if not bad else 1


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
    # MIGRATED MEANS REWRITTEN, AND UNTIL THE REGISTER IS LIVE NOTHING IS.
    #
    # This comment said exactly that before the code did it, and the second
    # real run is what exposed the gap: `verify` now runs after `fetch`, so
    # 25 photographs had encodedAt for the first time, and the check called
    # all 25 migrated and reported 228 references as having "survived the
    # rewrite" — a rewrite that had not run and, by design, cannot run while
    # live is false. It refuses. So the pages were pointing at providers for
    # the only correct reason there is: nothing has replaced those URLs yet.
    #
    # Encoding a photograph changes what is in the bucket. Only `rewrite`
    # changes what a page asks for, and it is all-or-nothing across the
    # register behind the live flag. So that flag is the honest gate, and
    # before it is set the only true statement this check can make is the
    # count of what is left.
    skip = artdirected()
    migrated = set()
    if reg.get("live"):
        # An art-directed photograph is encoded and deliberately left
        # hotlinked until a second crop exists; counting it as a leak makes
        # this permanently red for a decision rather than a fault. One
        # definition, used by the pass that skips them and the check that
        # measures them.
        migrated = {a["originalUrl"] for a in reg["assets"].values()
                    if a.get("encodedAt") and a.get("originalUrl")
                    and a["originalUrl"].split("?")[0] not in skip}
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
            # Only what a browser would actually fetch. The rollback
            # breadcrumb — data-was — holds the whole original tag on purpose,
            # base64 so it is inert, and it is never requested. Counting
            # them said 312 references survived a rewrite that had in fact
            # left nothing behind. A leak check that cannot tell an inert
            # attribute from a request is worse than no leak check.
            live_html = re.sub(r'\sdata-was="[^"]*"', "", html)
            hits = re.findall(r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+",
                              live_html)
            if not hits:
                continue
            pages += 1
            left += len(hits)
            for h in hits:
                if h.split("?")[0] in {u.split("?")[0] for u in migrated}:
                    leaked.append(h)

    ok = not leaked
    if not reg.get("live"):
        # Not "nothing left behind", which would read as a clean rewrite. No
        # rewrite has happened, and saying so is the only honest PASS here.
        note = ("the register is not live, so nothing has been rewritten yet "
                "— every reference below is expected")
    elif ok:
        note = "nothing left behind"
    else:
        note = "%d reference(s) survived the rewrite" % len(leaked)
    log("%s\tno migrated photograph is still fetched from a provider\t%s"
        % ("PASS" if ok else "FAIL", note))
    log("        third-party image references remaining: %d across %d page(s) "
        "— the REPLACE and REVIEW sets, and the KEEP rows not yet migrated"
        % (left, pages))
    return 0 if ok else 1


DEFERRED_RE = re.compile(r'\bdata-src="')
REAL_SRC_RE = re.compile(r'(?<![-\w])src="([^"]+)"')
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
HAS_SIZES_RE = re.compile(r'(?<![-\w])sizes="([^"]+)"')


def artdirected():
    """Photographs the pages crop differently for the phone. Not migratable yet.

    The fifty /tourism pages wrap their feature photographs in a <picture> with
    <source media="(max-width: 700px)"> — a different crop, cut by the
    provider's focal-point API. This library holds one crop per photograph, so
    migrating the <img> and leaving that <source> on Pexels serves half the
    photograph from us and half from them, and migrating both would silently
    replace a phone crop somebody chose with a desktop crop nobody did.

    102 of the 629 approved photographs are in this shape. They wait for a
    second crop to be produced, which is art direction and out of scope.
    """
    out = set()
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                html = fh.read()
            if "<source media=" not in html:
                continue
            for pm in re.finditer(r"<picture>.*?</picture>", html, re.S):
                if "<source media=" not in pm.group(0):
                    continue
                for u in re.findall(
                        r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+",
                        pm.group(0)):
                    out.add(u.split("?")[0])
    return out


def rewrite(write=False, revert=False, log=print):
    """Point every migrated photograph at the library, or put it back.

    A rewrite before publication is 1,529 pages of broken photographs, so the
    gate is the register's own `live` flag and not a comment asking somebody to
    be careful. Only assets that have actually been ENCODED are rewritten — a
    row that is planned but not fetched stays hotlinked, which is exactly what
    lets a twenty-five photograph pilot leave six hundred alone.

    WHAT IT WRITES. Not a swapped URL: the whole ladder, as a <picture> with
    AVIF and WebP sources at every width that exists and a JPEG <img> under
    them. Swapping one URL for one URL would move the hosting and throw away
    the responsive part, which is most of the point.

    An image the page is holding back with data-src is not wrapped, for the
    same reason the `modern` pass leaves them alone: a <picture> full of
    candidates gives the browser nothing left to wait for, and the homepage's
    deferred photographs would all load at once. Its data-src is rewritten in
    place instead, so it still comes from us — it simply keeps being deferred.

    ROLLBACK IS THE SAME PASS RUN BACKWARDS. Every asset keeps its
    originalUrl, so --revert restores exactly the URL that was there, from the
    register rather than from a backup that could drift. That is step twelve
    of the pilot and it has to work before step thirteen is allowed.
    """
    reg = register()
    if not revert and not reg.get("live"):
        log("library rewrite: refused. tourism/assets.json says live: false — "
            "publish the ladder to %s and set it." % reg.get("host"))
        return 1

    host = (reg.get("host") or "").rstrip("/")
    # Art direction is a property of the photograph, not of one page. An asset
    # that appears in an art-directed <picture> anywhere is excluded
    # everywhere: migrating it on the pages that do not art-direct it and
    # leaving it hotlinked on the ones that do would put the same photograph on
    # two hosts and leave the leak check permanently red.
    blocked = artdirected()

    ready = [a for a in reg["assets"].values()
             if a.get("originalUrl") and a.get("encodedAt") and a.get("widths")
             and a["originalUrl"].split("?")[0] not in blocked]
    by_url = {}
    for a in ready:
        by_url[a["originalUrl"].split("?")[0]] = a
    if not ready:
        log("library rewrite: nothing has been encoded yet")
        return 0

    def url_for(a, width, ext):
        return "%s/%s" % (host, key(a["name"], width, ext))

    def wrap(tag, a):
        sizes = HAS_SIZES_RE.search(tag)
        sizes_attr = ' sizes="%s"' % sizes.group(1) if sizes else ""
        out = []
        for ext, mime in ((".avif", "image/avif"), (".webp", "image/webp")):
            ladder = ", ".join("%s %dw" % (url_for(a, w, ext), w) for w in a["widths"])
            out.append('<source type="%s" srcset="%s"%s>' % (mime, ladder, sizes_attr))
        # The <img> keeps every attribute it had — alt, width, height, loading,
        # decoding, the focal point in its style — and only its src moves. A
        # missing width or height here is a layout shift, and this pass is not
        # allowed to introduce one.
        #
        # REVERSIBLE BY CONSTRUCTION, WHICH THE FIRST VERSION WAS NOT.
        # That version swapped the src for ours and deleted the provider's
        # srcset, and revert put back the bare imageUrl from the register. The
        # register holds one URL per photograph; the page held a URL per USE,
        # with the focal-point crop and the width in its query string. Fifty
        # pages came back missing their srcset and their crop, and git was the
        # only thing that noticed.
        #
        # The old values ride along on the tag instead. Revert reads them off
        # the element it is undoing rather than out of a table that never knew
        # them, so it restores the bytes that were there. They cost a few
        # hundred characters a tag and come out in a --finalise pass once a
        # migration is accepted and rollback is no longer wanted.
        widest = a["widths"][-1]
        # The WHOLE original tag, base64, in one attribute. Storing src and
        # srcset separately restored both values and put them back in a
        # different order, so a revert produced HTML that rendered identically
        # and did not match byte for byte — which makes it impossible to read a
        # rollback diff and see whether anything unintended happened. Exact is
        # a much stronger property than equivalent, and it costs one attribute.
        # Base64 because an <img> tag inside an attribute otherwise needs quote
        # escaping, and an escaping bug here corrupts the only copy of what was
        # there. Removed by --finalise once a migration is accepted.
        keep = base64.b64encode(tag.encode("utf-8")).decode("ascii")
        img = REAL_SRC_RE.sub(lambda m: 'src="%s"' % url_for(a, widest, ".jpg"), tag, count=1)
        img = re.sub(r'(?<![-\w])srcset="[^"]*"\s*', "", img)
        img = img[:-1].rstrip() + ' data-was="%s">' % keep
        return "<picture>" + "".join(out) + img + "</picture>"

    changed_pages, changed_tags = 0, 0
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
            before, n = html, 0

            if revert:
                # Undo from what the tag itself remembers, so the bytes that
                # come back are the bytes that were there — including the
                # focal-point crop and the width in the provider's query
                # string, neither of which the register has ever held.
                def undo(m):
                    was = re.search(r'\bdata-was="([A-Za-z0-9+/=]+)"', m.group(1))
                    if not was:
                        return m.group(0)
                    return base64.b64decode(was.group(1)).decode("utf-8")

                html, k = re.subn(
                    r"<picture>(?:<source[^>]*>)+(<img\b[^>]*data-was=[^>]*>)</picture>",
                    undo, html)
                n += k
                # A deferred image was never wrapped; its data-src moved in
                # place and moves back the same way.
                for a in ready:
                    for w in a["widths"]:
                        for ext in FORMATS:
                            html = html.replace(url_for(a, w, ext), a["originalUrl"])
            else:
                out, cut = [], 0
                for m in IMG_TAG_RE.finditer(html):
                    tag = m.group(0)
                    urls = re.findall(r"https://images\.(?:pexels|unsplash)\.com/[^\"\s]+", tag)
                    hit = next((by_url[u.split("?")[0]] for u in urls
                                if u.split("?")[0] in by_url), None)
                    if not hit:
                        continue
                    out.append(html[cut:m.start()])
                    if DEFERRED_RE.search(tag) and not REAL_SRC_RE.search(tag):
                        # Held back by the page's own loader: move the URL, keep
                        # the deferral.
                        moved = tag
                        for u in urls:
                            moved = moved.replace(
                                u, url_for(hit, hit["widths"][-1], ".jpg"))
                        out.append(moved)
                    else:
                        out.append(wrap(tag, hit))
                    cut = m.end()
                    n += 1
                if n:
                    out.append(html[cut:])
                    html = "".join(out)

            if html == before:
                continue
            changed_pages += 1
            changed_tags += n
            if write:
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(html)

    log("library %s: %d tag(s) across %d page(s) %s"
        % ("revert" if revert else "rewrite", changed_tags, changed_pages,
           "written" if write else "would change"))
    return 0
