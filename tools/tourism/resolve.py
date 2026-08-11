"""Fill the image slots from Unsplash — and refuse to fill them any other way.

The hard rule this module exists to enforce: an image URL only ever gets written
to a country dataset if the Unsplash API returned it AND a subsequent HTTP
request fetched it successfully. There is no offline path that produces a URL.
A photo id that nobody has fetched is a broken image with extra steps.

Usage:

    export UNSPLASH_ACCESS_KEY=...
    python3 tools/tourism/build.py resolve                 # every unresolved slot
    python3 tools/tourism/build.py resolve --country kenya
    python3 tools/tourism/build.py resolve --recheck       # re-verify resolved ones

Requires network access to api.unsplash.com and images.unsplash.com.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import queries

API = os.environ.get("UNSPLASH_API_BASE") or "https://api.unsplash.com"   # base is overridable for tests only
UA = "fako-journeys-tourism-image-system/1"


class Unavailable(Exception):
    """No key, or no route to Unsplash. Not a data problem — an environment one."""


def access_key():
    key = os.environ.get("UNSPLASH_ACCESS_KEY") or os.environ.get("UNSPLASH_API_KEY")
    if not key:
        raise Unavailable(
            "UNSPLASH_ACCESS_KEY is not set. Get a free key at "
            "https://unsplash.com/developers and export it before resolving."
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
        with _get(API + "/photos/random?count=1", key=key) as r:
            r.read(64)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise Unavailable("Unsplash rejected the key (HTTP %d)." % exc.code)
        raise Unavailable("Unsplash API returned HTTP %d." % exc.code)
    except Exception as exc:
        raise Unavailable(
            "cannot reach api.unsplash.com (%s). If this session runs behind a "
            "network policy, allow api.unsplash.com and images.unsplash.com first." % exc
        )
    return key


def search(query, orientation, key, per_page=12):
    url = API + "/search/photos?" + urllib.parse.urlencode(
        {"query": query, "orientation": orientation, "per_page": per_page, "content_filter": "high"}
    )
    with _get(url, key=key) as r:
        return json.loads(r.read().decode("utf-8")).get("results", [])


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
            body = r.read(4096)
            if len(body) < 1024:
                return False, "suspiciously small response"
            return True, ctype
    except urllib.error.HTTPError as exc:
        return False, "HTTP %d" % exc.code
    except Exception as exc:
        return False, str(exc)


def suitable(photo, role, min_width=1600):
    """Reject a photo the crop would ruin rather than forcing the crop."""
    w, h = photo.get("width") or 0, photo.get("height") or 0
    if w < min_width:
        return False, "only %dpx wide" % w
    want_w, want_h = role["aspect"]
    want = want_w / float(want_h)
    have = w / float(h) if h else 0
    # A 21:9 band cut from a 3:4 portrait is a disaster whatever the focal point.
    if want >= 2.0 and have < 1.2:
        return False, "portrait original cannot fill a panoramic band"
    if want < 1.0 and have > 1.6:
        return False, "wide original cannot fill a portrait frame"
    return True, None


def resolve_entry(country, category, entry, role, key, seen):
    """Search, pick the first suitable non-duplicate candidate, verify, return record."""
    from . import imaging

    query = queries.build(country, category, entry)
    orient = queries.orientation(category["role"])
    try:
        results = search(query, orient, key)
    except Exception as exc:
        return None, "search failed: %s" % exc
    if not results:
        return None, "no results for %r" % query

    for photo in results:
        pid = photo.get("id")
        if not pid or pid in seen:
            continue
        ok, why = suitable(photo, role)
        if not ok:
            continue
        raw = (photo.get("urls") or {}).get("raw")
        if not raw or not raw.startswith(imaging.ALLOWED_HOST):
            continue
        record = {
            "provider": "unsplash",
            "id": pid,
            "url": raw.split("?", 1)[0],
            "width": photo.get("width"),
            "height": photo.get("height"),
            "photographer": ((photo.get("user") or {}).get("name")),
            "photographerLink": ((photo.get("user") or {}).get("links") or {}).get("html"),
            "photoLink": (photo.get("links") or {}).get("html"),
            "query": query,
        }
        probe = imaging.cdn_url(record["url"], role, entry.focal)
        ok, detail = verify(probe)
        if not ok:
            continue
        # Unsplash API guidelines: trigger the download endpoint on use.
        dl = (photo.get("links") or {}).get("download_location")
        if dl:
            try:
                _get(dl, key=key, timeout=10).read(32)
            except Exception:
                pass
        seen.add(pid)
        return record, None
    return None, "no suitable, unused, verifiable result for %r" % query


def write_country(country):
    """Persist resolved photos back into the country's JSON — the data stays the
    source of truth, so an admin can later edit or replace any single image."""
    with open(country.path) as f:
        raw = json.load(f)
    by_cat = {e.category: e for e in country.entries}
    for item in raw.get("entries", []):
        entry = by_cat.get(item.get("category"))
        if entry is not None and entry.image:
            item["image"] = entry.image
    from .model import dump_country
    dump_country(country.path, raw)
