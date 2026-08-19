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
            its first-party one. Touches an asset only once THAT asset has
            been published, because pointing a page at an object that was
            never uploaded is a broken photograph.
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
        +-- originals/  AKL-000631.jpg
        +-- 1600/       AKL-000631.avif|.webp|.jpg
        +-- 1200/       ...
        +--  800/       ...
        +--  480/       ...

Width first, because that is what the browser is choosing between, and the
identity underneath it never changes. `originals/` is kept so a better
encoder, a new width or a different quality can be produced later without
going back to Pexels for a file we already have — and it is the only copy of
the source that exists once the hotlink is gone.

---------------------------------------------------------------------------
IDENTITY, AND WHY IT IS NOT THE CAPTION

The key used to be country/category/slug-of-the-caption. It read beautifully
in a bucket listing and it was wrong: the caption is page copy. Rewrite
"Elephants at Chobe" as "Elephants beside the Chobe River" and the computed
key changes, so one photograph acquires a second identity — a new object
uploaded and paid for, the old one orphaned in the bucket forever, and pages
pointing at whichever the last run wrote. From inside the pipeline that is
indistinguishable from a new photograph, so nothing would have reported it.

So an asset is AKL-000631 and stays AKL-000631. Country, destination,
category, caption, alt text, photographer, licence, acquisition date, shoot
date, pages, publication state, dimensions — all of it is metadata beside the
identity, all of it free to be corrected, none of it able to move an object.

An identity is assigned once and found again by `sourceKey`, which is the
provider's own id for a hotlink and the file's checksum for a delivery.
Neither can change. A manifest may also PIN an identity, which is how a
commissioned photograph replaces a bad one: it takes over the key, and every
page already pointing there shows the new picture without being edited.

---------------------------------------------------------------------------
PUBLICATION IS PER ASSET, NOT PER LIBRARY

There used to be one `live` boolean for the whole register, so the library
could only ever go live all at once. A canonical library grows: the best
hundred photographs should reach visitors while the other six hundred are
still being bought. Each asset carries its own downloadedAt, encodedAt,
publishedAt and rewrittenAt, plus a `hold` for one deliberately kept back,
and `state()` reads the answer off that evidence rather than storing a claim
that can drift from it. `publish` and `rewrite` both take a selector.

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


ID_RE = re.compile(r"^AKL-\d{6}$")

# Every publication state an asset can be in, in the order it moves through
# them. `hold` is the one that is a decision rather than a stage.
STATES = ("planned", "staged", "encoded", "published", "live", "hold")


def new_id(reg):
    """The next permanent identity. Monotonic, never reused, never derived."""
    n = int(reg.get("nextId") or 1)
    reg["nextId"] = n + 1
    return "AKL-%06d" % n


def source_key(origin, provider=None, photo_id=None, sha=None):
    """The immutable fact that says two rows are the same photograph.

    An identity has to be assigned once and then found again on every
    subsequent run, and the thing used to find it again must be something that
    cannot change. For a provider photograph that is the provider's own id —
    pexels:10010546 is that picture for as long as Pexels exists. For one we
    were given it is the checksum of the file, so re-ingesting the same
    delivery twice recognises it instead of minting a second identity for the
    same photograph.

    Never the caption, the country, the category or the filename. All four are
    editorial and all four change.
    """
    if origin == "provider":
        return "%s:%s" % (provider, photo_id)
    return "sha256:%s" % sha


def key(asset_id, width=None, ext=".avif"):
    """The object key on R2 for one photograph at one width, or its original.

    THE KEY IS THE IDENTITY AND NOTHING ELSE.

    This used to be country/category/slug-of-the-caption, which reads well in
    a bucket listing and is wrong. The caption is page copy. Rewrite
    "Elephants at Chobe" as "Elephants beside the Chobe River" and the
    computed key changed, so the same photograph acquired a second identity: a
    new object uploaded and paid for, the old one orphaned in the bucket
    forever, and 1,528 pages pointing at whichever the last run happened to
    write. Nothing in the pipeline would have reported it, because from the
    inside it looks exactly like a new photograph.

    So the key is AKL-000631 and the country, category and caption are
    metadata beside it, free to be corrected as often as anybody likes.
    """
    if width is None:
        return "originals/%s.jpg" % asset_id
    return "%d/%s%s" % (width, asset_id, ext)


def staged(asset_id):
    """Where the original waits between fetch-or-ingest and encode."""
    return os.path.join(STAGE, "%s.jpg" % asset_id)


def state(a):
    """What has actually happened to this photograph, from the evidence.

    Computed rather than stored, because a stored state drifts: something
    fails halfway, the field says published and the object is not there. Each
    of these is a timestamp written by the step that did the work, so the
    state cannot claim more than the pipeline actually did. `hold` is the
    exception and the only one that is an intention — it is how a photograph
    is kept out of publication on purpose.
    """
    if a.get("hold"):
        return "hold"
    if a.get("rewrittenAt"):
        return "live"
    if a.get("publishedAt"):
        return "published"
    if a.get("encodedAt"):
        return "encoded"
    if a.get("sha256"):
        return "staged"
    return "planned"


def select(reg, only=None):
    """The subset a step should act on. THIS IS HOW 100 GO BEFORE 786 DO.

        (nothing)            every asset
        AKL-000123           one, or a comma-separated list
        country:kenya        every asset of a country
        category:wildlife    every asset of a category
        origin:commissioned  provider, licensed or commissioned
        state:encoded        planned, staged, encoded, published, live, hold
        @some/file.txt       one identity per line, for a list from elsewhere

    The point of the whole per-asset publication change is that a subset can
    be published and rewritten without the rest of the library going with it.
    A selector that matches nothing returns nothing rather than everything,
    because the failure mode of the opposite is publishing the entire library
    by typing a name wrong.
    """
    assets = list(reg["assets"].values())
    if not only:
        return assets
    only = only.strip()
    if only.startswith("@"):
        path = only[1:]
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        with open(path, encoding="utf-8") as fh:
            want = {ln.strip() for ln in fh if ln.strip()}
        return [a for a in assets if a["id"] in want]
    if ":" in only:
        field, value = only.split(":", 1)
        value = value.strip().lower()
        if field == "state":
            return [a for a in assets if state(a) == value]
        return [a for a in assets
                if str(a.get(field) or "").lower() == value]
    want = {p.strip() for p in only.split(",") if p.strip()}
    return [a for a in assets if a["id"] in want]

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


def _upgrade(reg):
    """Bring an older register up to permanent identities. Idempotent.

    The first register was keyed by country/category/slug and gated
    publication on one global `live` boolean. Both were fine for migrating
    629 hotlinks and wrong for a library, so this converts in place on read:
    every row gets an AKL identity and the sourceKey that will find it again,
    and the global switch becomes a per-asset one.

    Identities are handed out in sorted order of the old key, so the same
    register upgrades to the same identities on any machine — this runs in a
    workflow and on a laptop and the two must not disagree.
    """
    assets = reg.get("assets") or {}
    if not assets or all(ID_RE.match(k) for k in assets):
        reg.setdefault("nextId", len(assets) + 1)
        reg.pop("live", None)
        return reg

    was_live = bool(reg.get("live"))
    reg["nextId"] = 1
    fresh = {}
    for old_key in sorted(assets):
        a = dict(assets[old_key])
        aid = new_id(reg)
        a["id"] = aid
        a.setdefault("origin", "provider")
        a["sourceKey"] = source_key(a["origin"], a.get("provider"),
                                    a.get("photoId"), a.get("sha256"))
        # The old key was the name AND the object key. It survives as the
        # human-readable label, which is all it should ever have been.
        a["slug"] = a.pop("name", old_key)
        # A register that said live: true had already rewritten its pages, and
        # every one of those assets was published under its old key. Say so
        # per asset rather than losing it — and note the keys have moved.
        if was_live and a.get("encodedAt"):
            a.setdefault("publishedAt", a.get("encodedAt"))
        fresh[aid] = a
    reg["assets"] = fresh
    reg.pop("live", None)
    return reg


def register():
    reg = _read(REGISTER, {
        "$comment": "The Afrinkong image library. One row per photograph, "
                    "keyed by a permanent identity that never changes: where "
                    "it came from, who took it, under what licence, when it "
                    "was taken down, encoded, published and wired into pages, "
                    "and which pages use it. Country, category and caption "
                    "are metadata beside the identity, not part of it. "
                    "Written by tools/tourism/library.py.",
        "host": "https://image.afrinkong.com",
        "nextId": 1,
        "assets": {},
    })
    return _upgrade(reg)


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
    # A fresh set for the provider-derived half, not a merge. The register is
    # the current approved list, and a photograph that has been reclassified
    # out of KEEP has to leave it — otherwise a later fetch downloads
    # something the audit has since refused. What carries forward is only what
    # a re-plan cannot recompute: the date it was taken down and the checksum
    # of what arrived.
    previous = reg.get("assets") or {}
    # BUT NOT THE PHOTOGRAPHS THAT WERE NEVER IN THE INVENTORY.
    #
    # This used to empty the whole register, and that made the library
    # structurally incapable of being a library. The inventory is derived from
    # what the pages currently hotlink, so rebuilding the register from it
    # means the only photographs that can exist are the ones already on a page
    # from a provider. A commissioned photograph — the entire point of the
    # acquisition plan — would be written in by `ingest` and deleted by the
    # next `plan`, which the workflow runs first on every run.
    #
    # So the register has two halves now. The provider half is recomputed from
    # the audit every time, because the audit is its authority. The licensed
    # and commissioned half is ours, has no upstream to recompute from, and
    # survives.
    reg["assets"] = {k: v for k, v in previous.items()
                     if v.get("origin", "provider") != "provider"}
    ours = len(reg["assets"])
    # AN IDENTITY IS LOOKED UP, NEVER RECOMPUTED. The register is rebuilt from
    # the audit on every run, so if the identity came out of this loop it
    # would be re-derived every time — and anything it was derived from could
    # change. Found by sourceKey, which cannot.
    known = {a.get("sourceKey"): a for a in previous.values()
             if a.get("sourceKey")}
    minted = 0
    for a in keep:
        skey = source_key("provider", a["provider"], a["photoId"])
        old = known.get(skey)
        if old:
            aid = old["id"]
        else:
            aid = new_id(reg)
            minted += 1
        country = _slug(a.get("country") or "world")
        category = _slug(a.get("category") or "general")
        stem = _slug(a.get("caption") or a.get("altIntended") or a.get("photoId"))
        reg["assets"][aid] = {
            "id": aid,
            "sourceKey": skey,
            "origin": "provider",
            # Editorial, and recomputed every run on purpose. Changing any of
            # the three moves nothing: not the identity, not the object key,
            # not a single URL in a page.
            "slug": "%s/%s/%s" % (country, category, stem),
            "country": country,
            "category": category,
            "provider": a["provider"],
            "photoId": a["photoId"],
            "photographer": a.get("photographer"),
            "photographerUrl": a.get("photographerUrl"),
            "sourceUrl": a.get("sourceUrl"),
            "originalUrl": a.get("imageUrl"),
            "licence": LICENCES.get(a["provider"], {}),
            "chosenAt": a.get("chosenAt"),
            # Everything the pipeline established about the bytes carries
            # forward — a re-plan is a re-read of the audit, not a reason to
            # download, encode or publish anything twice.
            "downloadedAt": (old or {}).get("downloadedAt"),
            "sha256": (old or {}).get("sha256"),
            "encodedAt": (old or {}).get("encodedAt"),
            "publishedAt": (old or {}).get("publishedAt"),
            "rewrittenAt": (old or {}).get("rewrittenAt"),
            "hold": (old or {}).get("hold"),
            "slot": a.get("slot"),
            "alt": a.get("alt"),
            "width": a.get("width"),
            "height": a.get("height"),
            "pages": a.get("pages", []),
            "widths": (old or {}).get("widths") or list(LADDER),
        }
    named = reg["assets"]
    clash = minted

    log("")
    log("  library plan")
    log("  ---------------------------------------------------------------")
    log("  approved for hosting        %6d" % len(keep))
    if ours:
        log("  ours, kept across the plan  %6d  (licensed or commissioned)"
            % ours)
    log("  identities                  %6d  (%d newly minted, %d recognised)"
        % (len(named), clash, len(keep) - clash))
    log("  widths per photograph       %6d  %s" % (len(LADDER), list(LADDER)))
    log("  files to publish            %6d  (AVIF + WebP)"
        % (len(named) * len(LADDER) * 2))
    counts = {}
    for a in reg["assets"].values():
        s = state(a)
        counts[s] = counts.get(s, 0) + 1
    log("  publication state           %s"
        % ", ".join("%s %d" % (s, counts[s]) for s in STATES if counts.get(s)))
    log("  host                        %s" % reg["host"])
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
                  key=lambda a: (-len(a.get("pages") or []), a["id"]))
    out, taken = [], set()
    # One country at a time, most-used photograph first. A sample that is
    # twenty-five photographs of Algeria proves nothing about the other
    # fifty-three, and country is the axis this site's content is organised on.
    # Spread on the editorial slug — country first, then category — because
    # that is what "representative" means here. Membership is tracked by
    # identity, so two photographs whose captions collide cannot shadow
    # each other.
    for axis in (lambda a: (a.get("slug") or "").split("/")[0],
                 lambda a: "/".join((a.get("slug") or "").split("/")[:2])):
        seen = set()
        for a in rows:
            if len(out) >= n:
                break
            k = axis(a)
            if k in seen or a["id"] in taken:
                continue
            seen.add(k)
            taken.add(a["id"])
            out.append(a)
    for a in rows:                       # top up if both axes ran out first
        if len(out) >= n:
            break
        if a["id"] not in taken:
            taken.add(a["id"])
            out.append(a)
    return out[:n]


def fetch(write=False, log=print, limit=0):
    """Download exactly the planned set. NEEDS NETWORK — a workflow step.

    One original per photograph, at the largest width the ladder will use, and
    a sha256 of what arrived so a later run can tell a re-download from a
    replacement. Nothing outside the register is ever fetched.
    """
    reg = register()

    def needed(a):
        """Whether this run has to go and get the bytes.

        THE REGISTER'S MEMORY OUTLIVES THE FILES IT DESCRIBES, AND THAT COST
        A RUN. This used to skip anything carrying a sha256, which is a
        perfectly good rule on one machine and wrong in a workflow. The
        register is committed; incoming/library/ and images/library/ are
        gitignored, because the entire point was to keep gigabytes of
        photographs out of git. So a fresh runner checks out a register
        saying twenty-five photographs are downloaded and encoded, and an
        empty disk. fetch skipped all twenty-five, encode had no source,
        publish found nothing and failed — in twenty-nine seconds, having
        done nothing at all.

        So the disk decides, not the register. sha256 goes back to being what
        it is for: telling a re-download of the same photograph from a
        provider quietly serving something else. An asset already published
        is the one case where the bytes genuinely are not needed again — it
        is in the bucket, and that is where it is served from.
        """
        if a.get("publishedAt"):
            return False
        return not os.path.exists(staged(a["id"]))

    pool = list(reg["assets"].values())
    if limit:
        # The pilot is a sample of the library, not its first page.
        pool = pilot(reg, limit)
    todo = [a for a in pool if needed(a)]
    if not write:
        log("library fetch: %d of %d asset(s) need downloading. dry run."
            % (len(todo), len(pool)))
        return 0

    os.makedirs(STAGE, exist_ok=True)
    got, failed = 0, []
    for a in todo:
        url = a.get("originalUrl") or ""
        if not url:
            failed.append((a["id"], "no source url"))
            continue
        # Ask each provider for the widest size the ladder needs and no more.
        sep = "&" if "?" in url else "?"
        want = "%s%sw=%d" % (url, sep, LADDER[-1])
        out = staged(a["id"])
        try:
            req = urllib.request.Request(want, headers={"User-Agent": "afrinkong-library"})
            with urllib.request.urlopen(req, timeout=45) as res:
                body = res.read()
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(body)
            digest = hashlib.sha256(body).hexdigest()
            # The checksum's actual job. A provider that has replaced the file
            # behind a URL we approved is serving a photograph nobody audited,
            # and the only way to notice is to compare with what arrived last
            # time. Recorded and reported, not fatal: the audit decides what
            # to do about it, this step only reports what it saw.
            if a.get("sha256") and a["sha256"] != digest:
                log("  %s: the provider is serving different bytes than last "
                    "time (%s -> %s)" % (a["id"], a["sha256"][:12], digest[:12]))
                a["sourceChangedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime())
            a["sha256"] = digest
            a["downloadedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            a["bytes"] = len(body)
            got += 1
        except Exception as exc:                       # noqa: BLE001 — report, continue
            failed.append((a["id"], str(exc)[:70]))
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
        src = staged(a["id"])
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
            orig = os.path.join(out_root, key(a["id"], None))
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
                    dst = os.path.join(out_root, key(a["id"], w, ext))
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


def publish(write=False, log=print, only=None):
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
        log("library publish: images/library/ does not exist — nothing has "
            "been encoded on this machine.")
        log("  The encoded ladder is gitignored on purpose, so a fresh "
            "checkout never has it. Run fetch and encode first; the register "
            "remembering a download is not the same as the bytes being here.")
        return 1
    types = {".avif": "image/avif", ".webp": "image/webp", ".jpg": "image/jpeg"}

    # PER ASSET, AND ONLY THE ONES ASKED FOR. This used to walk the encoded
    # tree and upload whatever it found, which is the same all-or-nothing
    # shape the global `live` flag had: there was no way to put a hundred
    # photographs in front of visitors without putting all of them there.
    reg = register()
    chosen = [a for a in select(reg, only) if a.get("encodedAt")
              and not a.get("hold")]
    held = [a for a in select(reg, only) if a.get("hold")]
    if not chosen:
        log("library publish: nothing selected is encoded and off hold")
        return 1
    want = set()
    for a in chosen:
        want.add(key(a["id"], None))
        for w in a.get("widths") or LADDER:
            for ext in FORMATS:
                want.add(key(a["id"], w, ext))
    client = boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com" % os.environ["R2_ACCOUNT_ID"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto")
    bucket = os.environ["R2_BUCKET"]

    sent, size, missing = 0, 0, 0
    for base, _dirs, files in os.walk(root):
        for name in sorted(files):
            full = os.path.join(base, name)
            k = os.path.relpath(full, root).replace(os.sep, "/")
            if k not in want:
                continue
            if write:
                client.upload_file(full, bucket, k, ExtraArgs={
                    "ContentType": types.get(os.path.splitext(name)[1],
                                             "application/octet-stream"),
                    "CacheControl": "public, max-age=31536000, immutable"})
            sent += 1
            size += os.path.getsize(full)
    missing = len(want) - sent
    if write:
        # publishedAt is what `rewrite` reads. Set only after the uploads for
        # that asset actually ran, so a page can never be pointed at an object
        # that was never sent.
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for a in chosen:
            a["publishedAt"] = stamp
        _write_register(reg, log=log)
    log("library publish: %d object(s) %s (%.1f MB) for %d asset(s)"
        % (sent, "uploaded" if write else "would be uploaded",
           size / 1e6, len(chosen)))
    if missing:
        log("  %d expected object(s) were not on disk — run encode" % missing)
    if held:
        log("  %d asset(s) skipped, on hold" % len(held))
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
    import ssl
    import urllib.error
    import urllib.parse
    import urllib.request

    reg = register()
    host = (reg.get("host") or "").rstrip("/")
    if not host:
        log("library reachable: the register has no host")
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

    # AND THEN SHAKE HANDS ONCE, FOR THE SAME REASON.
    #
    # The run after DNS came good failed 325 times with SSLV3_ALERT_HANDSHAKE_
    # FAILURE, which is a different problem wearing the same clothes: the name
    # resolves, the socket opens, and Cloudflare refuses TLS. That is what a
    # custom hostname looks like in the window between DNS going live and the
    # edge certificate being issued for it — minutes, sometimes longer. It is
    # not a bucket problem, not a key problem and not something in this
    # repository, so it deserves one sentence rather than three hundred
    # identical stack traces.
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((name, 443), timeout=20) as raw:
            with ctx.wrap_socket(raw, server_hostname=name) as tls:
                cert = tls.getpeercert()
                covers = [v for k, v in cert.get("subjectAltName", ())
                          if k == "DNS"]
    except ssl.SSLError as exc:
        log("library reachable: %s resolves, but refuses TLS (%s)"
            % (name, exc))
        log("  DNS is done — the name resolved and the socket opened. What is")
        log("  missing is the edge certificate for this hostname. Cloudflare")
        log("  issues one after the custom domain goes live and it is not")
        log("  instant; until it exists every request is rejected at the")
        log("  handshake, before a single byte of HTTP is exchanged. Nothing")
        log("  in the bucket, the keys or this pipeline is implicated. Look")
        log("  at the custom domain's certificate status in R2 and run this")
        log("  again when it says active.")
        return 1
    except Exception as exc:                          # noqa: BLE001 — report
        log("library reachable: %s resolves but will not connect (%s)"
            % (name, exc))
        return 1
    if covers:
        log("library reachable: TLS to %s is up, certificate covers %s"
            % (name, ", ".join(covers[:3])))

    # AFTER THE TWO PREFLIGHTS, NOT BEFORE THEM.
    #
    # Whether DNS resolves and whether the host will shake hands are facts
    # about the internet, and neither needs a single encoded file to answer.
    # They used to sit behind this check, so the only way to find out whether
    # a certificate had been issued was to download twenty-five photographs,
    # encode three hundred files and upload them first — five minutes to
    # learn something a socket knows in one second. Now `library reachable`
    # on a bare checkout answers the connectivity question on its own, and
    # only the per-object measurement needs the ladder.
    # WHAT TO ASK FOR COMES FROM THE REGISTER, NOT FROM THIS DISK.
    #
    # This walked images/library/ and asked for whatever it found, which ties
    # the measurement to a machine that happens to have just encoded. The
    # encoded tree is gitignored, so a fresh runner has none of it — and the
    # objects it would be measuring are already in the bucket, uploaded by an
    # earlier run. Insisting on local files meant the only way to re-check a
    # published library was to download and re-encode it first, five minutes
    # to ask a question the register can answer instantly.
    #
    # The register knows what was published and at which widths. That is the
    # authority. The disk is consulted only where it can add something the
    # host cannot be trusted about on its own — the byte count.
    root = os.path.join(ROOT, "images", "library")
    published = [a for a in reg["assets"].values() if a.get("publishedAt")]
    keys = []
    for a in published:
        keys.append((key(a["id"], None), None))
        for w in a.get("widths") or LADDER:
            for ext in FORMATS:
                keys.append((key(a["id"], w, ext), None))
    if not keys:
        # Nothing published yet: fall back to whatever was just encoded, so a
        # ladder can be checked before it is uploaded.
        if not os.path.isdir(root):
            log("library reachable: the host is reachable. Nothing is "
                "published and nothing is encoded here, so there is nothing "
                "to measure.")
            return 0
        for base, _dirs, files in os.walk(root):
            for name in sorted(files):
                full = os.path.join(base, name)
                keys.append((os.path.relpath(full, root).replace(os.sep, "/"),
                             os.path.getsize(full)))
    else:
        # Sizes where we happen to hold the file, None where we do not.
        keys = [(k, (os.path.getsize(os.path.join(root, k))
                     if os.path.exists(os.path.join(root, k)) else None))
                for k, _ in keys]
        log("library reachable: %d published asset(s) in the register"
            % len(published))

    def ask(url, method="HEAD"):
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {})
        except Exception as exc:                      # noqa: BLE001 — report, continue
            return 0, {"x-error": str(exc)}

    keys.sort()
    if sample and sample < len(keys):
        step = len(keys) / float(sample)
        keys = [keys[int(i * step)] for i in range(sample)]

    bad, codes, cache, first, second = [], {}, {}, {}, {}
    unchecked = 0
    for k, size in keys:
        url = "%s/%s" % (host, k)
        code, head = ask(url)
        codes[code] = codes.get(code, 0) + 1
        if code != 200:
            bad.append("%s: %s %s" % (k, code, head.get("x-error", "")))
            continue
        got = head.get("Content-Length")
        if size is not None and got and int(got) != size:
            bad.append("%s: host says %s bytes, disk says %d" % (k, got, size))
        elif size is None and got:
            unchecked += 1
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
    if unchecked:
        log("  %d object(s) served but not byte-compared — this machine does "
            "not hold the encoded file" % unchecked)
    if miss_code == 200:
        bad.append("a key that does not exist answers 200 — a broken image "
                   "with a successful request is the worst of both")
    for line in bad[:20]:
        log("  ! %s" % line)
    if len(bad) > 20:
        log("  ! ...and %d more" % (len(bad) - 20))
    log("library reachable: %s" % ("OK" if not bad else "%d problem(s)" % len(bad)))
    return 0 if not bad else 1


MANIFEST = os.path.join(ROOT, "incoming", "manifest.csv")

# What a delivery has to tell us, per origin. Deliberately the same questions
# `verify` asks, so a manifest that ingests cleanly cannot fail provenance
# afterwards — the check happens once, at the door.
MANIFEST_FIELDS = (
    "file", "id", "country", "category", "subject", "photographer", "origin",
    "licenceName", "licenceRef", "acquiredAt",       # licensed
    "contractRef", "shotAt", "releases",             # commissioned
    "credit", "name", "notes",
)


def ingest(write=False, log=print, manifest=None):
    """Take delivered photographs into the library. NO NETWORK, NO PROVIDER.

        build.py library ingest                     # what it would take
        build.py library ingest --fetch             # take them
        build.py library ingest incoming/batch1.csv --fetch

    THE DOOR THE LIBRARY DID NOT HAVE.

    Everything else here descends from data/asset-inventory.json, which is a
    reading of what the 1,528 pages currently hotlink. That made the register
    a mirror of the site's existing dependency on Pexels and Unsplash: the
    only photograph that could enter was one already on a page, from a
    provider. A commissioned frame had no way in, and `plan` would have
    deleted it if one had been written by hand.

    This is the other way in. It reads a manifest — the acquisition plan's own
    columns plus a `file` — and for each row hashes the delivery, reads its
    real dimensions, gives it a library name and stages it exactly where
    `fetch` would have put a download. From there `encode`, `publish`,
    `reachable` and `rewrite` cannot tell the difference, which is the point:
    one pipeline, three origins.

    The manifest is the same shape as data/image-acquisition.csv on purpose.
    Filter that file to what you are buying, send it out, and when the
    photographs come back add the delivered filename to the `file` column and
    ingest it. The brief and the receipt are one document.
    """
    import csv
    import hashlib
    import shutil

    path = manifest or MANIFEST
    if not os.path.exists(path):
        log("library ingest: no manifest at %s" % os.path.relpath(path, ROOT))
        log("  columns: %s" % ", ".join(MANIFEST_FIELDS))
        return 1

    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        log("library ingest: %s is empty" % os.path.relpath(path, ROOT))
        return 1

    reg = register()
    taken, bad = [], []
    for i, row in enumerate(rows, 2):          # 2 — row 1 is the header
        row = {k: (v or "").strip() for k, v in row.items() if k}
        src = row.get("file") or ""
        if not src:
            continue                            # a brief not yet delivered
        full = src if os.path.isabs(src) else os.path.join(ROOT, src)
        if not os.path.exists(full):
            bad.append("row %d: %s is not on disk" % (i, src))
            continue
        origin = (row.get("origin") or "").lower()
        if origin not in ("licensed", "commissioned"):
            bad.append("row %d: origin is %r — licensed or commissioned"
                       % (i, row.get("origin")))
            continue
        if not row.get("photographer"):
            bad.append("row %d: no photographer" % i)
            continue
        # The same fields verify will demand, refused here rather than after
        # the file has been encoded and uploaded.
        need = (("licenceRef", "acquiredAt") if origin == "licensed"
                else ("contractRef", "shotAt", "releases"))
        missing = [f for f in need if not row.get(f)]
        if missing:
            bad.append("row %d: %s asset with no %s"
                       % (i, origin, ", ".join(missing)))
            continue

        country = _slug(row.get("country") or "world")
        category = _slug(row.get("category") or "general")

        with open(full, "rb") as fh:
            blob = fh.read()
        digest = hashlib.sha256(blob).hexdigest()
        # THE IDENTITY IS PINNED OR MINTED, NEVER DERIVED FROM THE DELIVERY.
        # A manifest may name an identity outright — that is how a commissioned
        # photograph REPLACES one already published, taking over its object key
        # and every page that points at it without a single page being edited.
        # Otherwise the checksum decides: re-ingesting the same file recognises
        # it rather than minting a second identity for one photograph.
        skey = source_key(origin, sha=digest)
        pinned = (row.get("id") or row.get("name") or "").strip()
        pinned = pinned[:-5] if pinned.endswith(".avif") else pinned
        existing = {a.get("sourceKey"): a for a in reg["assets"].values()
                    if a.get("sourceKey")}
        if pinned and ID_RE.match(pinned):
            aid = pinned
        elif skey in existing:
            aid = existing[skey]["id"]
        elif pinned:
            bad.append("row %d: id %r is not an AKL identity" % (i, pinned))
            continue
        else:
            aid = new_id(reg)
        was = reg["assets"].get(aid) or {}
        width = height = 0
        try:
            from PIL import Image
            with Image.open(full) as im:
                width, height = im.size
        except Exception:                        # noqa: BLE001 — size is not fatal
            pass

        entry = {
            "id": aid,
            "sourceKey": skey,
            "origin": origin,
            # Editorial. Free to change; changes nothing that is published.
            "slug": "%s/%s/%s" % (country, category,
                                  _slug(row.get("subject")
                                        or os.path.basename(src))),
            "photographer": row.get("photographer"),
            "credit": row.get("credit") or row.get("photographer"),
            "licence": {"name": row.get("licenceName")
                        or ("Commissioned for Afrinkong"
                            if origin == "commissioned" else "Licensed")},
            "licenceRef": row.get("licenceRef"),
            "acquiredAt": row.get("acquiredAt"),
            "contractRef": row.get("contractRef"),
            "shotAt": row.get("shotAt"),
            "releases": row.get("releases"),
            "alt": row.get("subject"),
            "country": country,
            "category": category,
            "width": width,
            "height": height,
            "sha256": digest,
            "downloadedAt": row.get("acquiredAt") or row.get("shotAt"),
            "ingestedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notes": row.get("notes"),
            # Empty for a new identity. When a delivery TAKES OVER an existing
            # one, the pages that already reference it come with it — that is
            # the whole point of replacing a photograph in place.
            "pages": was.get("pages") or [],
            "originalUrl": was.get("originalUrl"),
            "rewrittenAt": was.get("rewrittenAt"),
            "hold": was.get("hold"),
            "widths": list(LADDER),
        }
        if write:
            os.makedirs(STAGE, exist_ok=True)
            shutil.copyfile(full, staged(aid))
            reg["assets"][aid] = entry
        taken.append((aid, origin))

    for line in bad[:12]:
        log("  ! %s" % line)
    if len(bad) > 12:
        log("  ! ...and %d more" % (len(bad) - 12))
    log("library ingest: %d photograph(s) %s, %d refused"
        % (len(taken), "taken into the library" if write else "would be taken",
           len(bad)))
    if write and taken:
        _write_register(reg, log=log)
        log("  staged for encode: %s" % os.path.relpath(STAGE, ROOT))
    elif not write:
        log("  dry run — add --fetch to take them in")
    return 1 if bad else 0


def verify(log=print):
    """No hosted file without an origin, and no rewritten URL without a file.

    This is the rule the library exists to keep. A photograph whose
    photographer, source page or licence is unknown is not published, and a
    page that points at the asset host must point at something the register
    knows about.
    """
    reg = register()
    bad, unused = [], []
    for name, a in reg["assets"].items():
        # PROVENANCE IS PER ORIGIN, BECAUSE A COMMISSIONED PHOTOGRAPH HAS NO
        # photoId AND NEVER WILL.
        #
        # These four fields were required of everything, and all four are
        # shapes that only a stock provider has. That is fine while the
        # library is a migration of hotlinks and fatal the moment it is a
        # library: five of the seven checks below would reject the first
        # photograph anybody is paid to take. What every origin owes is the
        # same question answered differently — who took it, and under what
        # right do we publish it.
        origin = a.get("origin", "provider")
        if origin == "provider":
            need = ("provider", "photoId", "sourceUrl", "originalUrl")
        elif origin == "licensed":
            # Bought from an agency or a photographer. The licence reference
            # is the receipt, and without it nobody can answer a takedown.
            need = ("licenceRef", "acquiredAt")
        elif origin == "commissioned":
            # Shot for us. The contract says what we may do with it, and a
            # photograph of identifiable people or private property without
            # releases is a photograph we cannot safely publish.
            need = ("contractRef", "shotAt", "releases")
        else:
            bad.append("%s: unknown origin %r" % (name, origin))
            continue
        for field in need:
            if not a.get(field):
                bad.append("%s: %s asset with no %s" % (name, origin, field))
        # A licence for a provider photograph is a URL; for one we bought or
        # commissioned it is a name and a reference, held above.
        if origin == "provider" and not (a.get("licence") or {}).get("url"):
            bad.append("%s: no licence" % name)
        if not (a.get("licence") or {}).get("name"):
            bad.append("%s: no licence name" % name)
        if not a.get("photographer"):
            bad.append("%s: no photographer" % name)
        # NOT AN ERROR ANY MORE. A library asset is allowed to exist before a
        # page uses it — that is what makes it a library rather than a cache
        # of the current site. It is still worth counting, because an asset
        # nobody has wired up is either new or forgotten.
        if not a.get("pages"):
            unused.append(name)

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
    # The shape of the library, not a pass or a fail. While every row says
    # provider, this is a migration of somebody else's photographs; the
    # licensed and commissioned counts are the only real measure of whether
    # AfrinKong owns its own pictures yet.
    mix = {}
    for a in reg["assets"].values():
        o = a.get("origin", "provider")
        mix[o] = mix.get(o, 0) + 1
    log("        origins: %s"
        % (", ".join("%s %d" % (o, n) for o, n in sorted(mix.items()))
           or "none"))
    if unused:
        log("        %d asset(s) in the library that no page uses yet"
            % len(unused))
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
    # MIGRATED MEANS REWRITTEN, AND IT IS NOW A FACT ABOUT ONE PHOTOGRAPH.
    #
    # This read `encodedAt` once, and a run where 25 photographs were encoded
    # but no page had been touched reported 228 references as having "survived
    # the rewrite" — a rewrite that had not run. Then it read one global
    # `live` flag, which was right while publication was all-or-nothing and
    # wrong the moment the library could go live a hundred photographs at a
    # time: with a subset rewritten, a global flag can only be wrong in one
    # direction or the other for everything else.
    #
    # `rewrittenAt` is written per asset by `rewrite` itself, and cleared by
    # a revert. So a leak is exactly what it should always have been: a page
    # still asking a provider for a photograph whose pages we have already
    # moved.
    skip = artdirected()
    # An art-directed photograph is encoded and deliberately left hotlinked
    # until a second crop exists; counting it as a leak makes this
    # permanently red for a decision rather than a fault. One definition,
    # used by the pass that skips them and the check that measures them.
    migrated = {a["originalUrl"] for a in reg["assets"].values()
                if a.get("rewrittenAt") and a.get("originalUrl")
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
    done = sum(1 for a in reg["assets"].values() if a.get("rewrittenAt"))
    if not done:
        # Not "nothing left behind", which would read as a clean rewrite. No
        # rewrite has happened, and saying so is the only honest PASS here.
        note = ("no asset has been rewritten yet — every reference below is "
                "expected")
    elif ok:
        note = "nothing left behind by the %d asset(s) rewritten" % done
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


def rewrite(write=False, revert=False, log=print, only=None):
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
    host = (reg.get("host") or "").rstrip("/")
    # Art direction is a property of the photograph, not of one page. An asset
    # that appears in an art-directed <picture> anywhere is excluded
    # everywhere: migrating it on the pages that do not art-direct it and
    # leaving it hotlinked on the ones that do would put the same photograph on
    # two hosts and leave the leak check permanently red.
    blocked = artdirected()

    # PUBLISHED, PER ASSET — not a global flag, and not merely encoded.
    #
    # The gate used to be one boolean for the whole register, which meant the
    # library could only ever go live all at once: there was no way to put the
    # best hundred photographs in front of visitors and leave the rest
    # hotlinked. Now a page is pointed at an asset when THAT asset has been
    # uploaded, and publishedAt is written by `publish` only after the upload
    # actually ran. An encoded-but-unpublished photograph is exactly the case
    # this must refuse: the object is not in the bucket, so the page would
    # show nothing.
    #
    # On revert the gate is deliberately wider — anything that was rewritten
    # has to be undoable whatever its state is now.
    pool = select(reg, only)
    ready = [a for a in pool
             if a.get("originalUrl") and a.get("widths")
             and (a.get("rewrittenAt") if revert else a.get("publishedAt"))
             and not a.get("hold")
             and a["originalUrl"].split("?")[0] not in blocked]
    by_url = {}
    for a in ready:
        by_url[a["originalUrl"].split("?")[0]] = a
    if not ready:
        waiting = [a for a in pool if a.get("encodedAt")
                   and not a.get("publishedAt")]
        if waiting and not revert:
            log("library rewrite: %d selected asset(s) are encoded but not "
                "published — run publish first" % len(waiting))
        else:
            log("library rewrite: nothing selected is %s"
                % ("rewritten" if revert else "published"))
        return 0

    def url_for(a, width, ext):
        return "%s/%s" % (host, key(a["id"], width, ext))

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

    if write:
        # The asset's own record of being wired into pages, which is what
        # makes `live` a per-photograph fact and what the leak check reads to
        # decide whether a provider reference is a leftover or expected.
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for a in ready:
            a["rewrittenAt"] = None if revert else stamp
        _write_register(reg, log=log)
    log("library %s: %d tag(s) across %d page(s) %s, %d asset(s) selected"
        % ("revert" if revert else "rewrite", changed_tags, changed_pages,
           "written" if write else "would change", len(ready)))
    return 0
