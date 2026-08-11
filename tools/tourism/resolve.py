"""Server-side Unsplash resolver.

The hard rule this module exists to enforce: an image URL only ever reaches the
cache if the Unsplash API returned it AND a subsequent HTTP request fetched it
successfully. There is no code path — none — that constructs a photo id. The API
is the authority for ids and URLs; this module only appends transform parameters
to a URL the API handed back.

    export UNSPLASH_ACCESS_KEY=...
    python3 tools/tourism/build.py resolve
    python3 tools/tourism/build.py resolve --country cameroon
    python3 tools/tourism/build.py resolve --country kenya --category wildlife
    python3 tools/tourism/build.py resolve --force

The key is read from the environment and used only here, in a process that runs
on a developer's or CI machine. It is never written to the cache, never rendered
into HTML, and never reaches a browser: the site it produces is static files.
"""

import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import queries

def api_base():
    """Read at call time, not import time — the tests override it after import."""
    return os.environ.get("UNSPLASH_API_BASE") or "https://api.unsplash.com"
UA = "fako-journeys-tourism-image-system/1"

MISSING_KEY_WARNING = "Unsplash image resolution requires UNSPLASH_ACCESS_KEY."


class Unavailable(Exception):
    """No key, or no route to Unsplash. An environment problem, not a data one."""


class RateLimited(Exception):
    """The hourly quota is spent. Everything resolved so far is already cached,
    so the fix is to run again later, not to start over."""


def access_key():
    key = os.environ.get("UNSPLASH_ACCESS_KEY") or os.environ.get("UNSPLASH_API_KEY")
    if not key:
        raise Unavailable(
            MISSING_KEY_WARNING + " Get a free key at https://unsplash.com/developers, "
            "put it in .env (which is git-ignored) or export it, then run resolve again."
        )
    return key


def _get(url, key=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if key:
        req.add_header("Authorization", "Client-ID " + key)
        req.add_header("Accept-Version", "v1")
    return urllib.request.urlopen(req, timeout=timeout)


def preflight():
    """Fail loudly and early rather than half way through 189 slots."""
    key = access_key()
    try:
        with _get(api_base() + "/photos/random?count=1", key=key) as r:
            r.read(64)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise Unavailable("Unsplash rejected the key (HTTP %d). Check UNSPLASH_ACCESS_KEY."
                              % exc.code)
        if exc.code == 429:
            raise Unavailable("Unsplash rate limit reached (HTTP 429). Demo keys allow 50 "
                              "requests/hour; wait, or apply for production access.")
        raise Unavailable("Unsplash API returned HTTP %d." % exc.code)
    except Exception as exc:
        raise Unavailable(
            "cannot reach api.unsplash.com (%s). If this session runs behind a "
            "network policy, allow api.unsplash.com and images.unsplash.com first." % exc
        )
    return key


def search(query, orientation, key, per_page=15):
    url = api_base() + "/search/photos?" + urllib.parse.urlencode(
        {"query": query, "orientation": orientation, "per_page": per_page,
         "content_filter": "high"}
    )
    try:
        with _get(url, key=key) as r:
            remaining = r.headers.get("X-Ratelimit-Remaining")
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            # Unsplash returns 403, not 429, when the hourly quota is spent.
            raise RateLimited("hourly rate limit reached")
        raise
    if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
        # Stop while one request is still in hand rather than discovering the
        # limit through a wall of identical failures.
        raise RateLimited("hourly rate limit nearly reached (%s left)" % remaining)
    return payload.get("results", [])


def verify(url, timeout=20):
    """Fetch the delivery URL for real. Returns (ok, detail)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if r.status != 200:
                return False, "HTTP %s" % r.status
            if not ctype.startswith("image/"):
                return False, "content-type %s" % ctype
            if len(r.read(4096)) < 1024:
                return False, "suspiciously small response"
            return True, ctype
    except urllib.error.HTTPError as exc:
        return False, "HTTP %d" % exc.code
    except Exception as exc:
        return False, str(exc)


def suitable(photo, role, min_width=1600):
    """Reject a photo the intended crop would ruin, rather than forcing the crop."""
    w, h = photo.get("width") or 0, photo.get("height") or 0
    if w < min_width:
        return False, "only %dpx wide" % w
    want_w, want_h = role["aspect"]
    want = want_w / float(want_h)
    have = w / float(h) if h else 0
    if want >= 2.0 and have < 1.2:
        return False, "portrait original cannot fill a panoramic band"
    if want < 1.0 and have > 1.6:
        return False, "wide original cannot fill a portrait frame"
    return True, None


def photo_record(photo, country, category, entry, query, alt):
    """Map an Unsplash API photo object onto the stored schema.

    Every field here comes out of the API response. `imageUrl` is urls.raw with
    its query string stripped (raw carries Unsplash's own default params), and
    falls back to urls.full. Nothing is assembled from an id.
    """
    from . import imaging

    urls = photo.get("urls") or {}
    source = urls.get("raw") or urls.get("full")
    if not source or not source.startswith(imaging.allowed_host()):
        return None
    user = photo.get("user") or {}
    return {
        "photoId": photo.get("id"),
        "photographer": user.get("name"),
        "photographerUrl": (user.get("links") or {}).get("html"),
        "unsplashUrl": (photo.get("links") or {}).get("html"),
        "imageUrl": source.split("?", 1)[0],
        "category": category["id"],
        "country": country.slug,
        "query": query,
        "alt": alt,
        "width": photo.get("width"),
        "height": photo.get("height"),
        "focalPoint": {"x": entry.focal["x"], "y": entry.focal["y"]},
        "resolvedAt": None,
        "verifiedAt": None,
    }


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_entry(country, category, entry, role, key, seen):
    """Search, pick the first suitable unused candidate, verify it, return a record.

    Returns (record, error). A record is only ever built from `results`.
    """
    orient = queries.orientation(category["role"])
    rungs = queries.ladder(country, category, entry)
    rejected = []

    for depth, (query, tier) in enumerate(rungs):
        try:
            results = search(query, orient, key)
        except RateLimited:
            raise
        except Exception as exc:
            return None, "search failed: %s" % exc
        if not results:
            rejected.append("%r: no results" % query)
            continue
        record = _pick(results, country, category, entry, role, key, query,
                       seen, rejected, tier)
        if record:
            record["queryDepth"] = depth
            record["queryTier"] = tier
            return record, None

    return None, "nothing usable across %d queries (%s)" % (
        len(rungs), "; ".join(rejected[:3]))


def _pick(results, country, category, entry, role, key, query, seen, rejected,
          tier="subject"):
    """First candidate that is unused, suitable and actually fetchable."""
    from . import imaging
    from .validate import alt_text

    for photo in results:
        pid = photo.get("id")
        if not pid:
            continue
        if pid in seen:
            rejected.append("%s already used" % pid)
            continue
        ok, why = suitable(photo, role)
        if not ok:
            rejected.append("%s %s" % (pid, why))
            continue
        alt = (alt_text(country, entry) if tier == "subject"
               else queries.generic_alt(country, category))
        record = photo_record(photo, country, category, entry, query, alt)
        if not record:
            rejected.append("%s no usable urls.raw/full" % pid)
            continue
        probe = imaging.cdn_url(record["imageUrl"], role, entry.focal)
        ok, detail = verify(probe)
        if not ok:
            rejected.append("%s failed verification (%s)" % (pid, detail))
            continue
        # Unsplash API guidelines: ping the download endpoint when a photo is used.
        dl = (photo.get("links") or {}).get("download_location")
        if dl:
            try:
                _get(dl, key=key, timeout=10).read(32)
            except Exception:
                pass
        record["resolvedAt"] = now()
        record["verifiedAt"] = now()
        seen.add(pid)
        return record
    return None
