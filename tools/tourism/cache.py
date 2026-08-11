"""The resolved-image cache.

Separation of concerns, on purpose:

    tourism/countries/<slug>.json   editorial content — caption, description,
                                    subject, focal point. Written by people.
    tourism/cache/unsplash.json     resolved image metadata. Written only by the
                                    resolver, only from an Unsplash API response.

Keeping them apart is what makes the resolver resumable and the content editable
without either one stepping on the other. An editor can rewrite every caption in
the site and no image has to be fetched again; the resolver can refresh every
image and no copy is touched.

The cache is the sole reason the site never calls Unsplash at page load: the
pages are static HTML generated from this file, so a visitor's browser talks to
images.unsplash.com for bytes and to nothing else.
"""

import json
import os

from .model import ROOT

CACHE_DIR = os.path.join(ROOT, "tourism", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "images.json")
LEGACY_FILE = os.path.join(CACHE_DIR, "unsplash.json")   # single-provider era


def cache_file():
    """Overridable so tests and CI never write the repo's cache."""
    return (os.environ.get("TOURISM_CACHE_FILE")
            or os.environ.get("UNSPLASH_CACHE_FILE")
            or CACHE_FILE)

# The stored schema. Provider-neutral: nothing here names Unsplash or Pexels
# except the `provider` field itself.
FIELDS = (
    "country", "category", "caption", "description", "provider", "photoId",
    "imageUrl", "thumbnailUrl", "sourceUrl", "photographer", "photographerUrl",
    "width", "height", "aspectRatio", "alt", "query", "focalPoint", "createdAt",
    "verifiedAt", "queryTier", "relevance",
)

REQUIRED = ("provider", "photoId", "imageUrl", "photographer")


def migrate(record):
    """Upgrade a single-provider record in place.

    The first eight images were resolved before Pexels existed, under a schema
    with no `provider` and an `unsplashUrl` field. They are real, fetched,
    verified photographs; re-resolving them would spend quota to get the same
    pictures back. So they are carried forward rather than discarded.
    """
    if record.get("provider"):
        return record
    record["provider"] = "unsplash"
    if "unsplashUrl" in record:
        record.setdefault("sourceUrl", record.pop("unsplashUrl"))
    if record.get("resolvedAt") and not record.get("createdAt"):
        record["createdAt"] = record.pop("resolvedAt")
    w, h = record.get("width") or 0, record.get("height") or 0
    if h and not record.get("aspectRatio"):
        record["aspectRatio"] = round(w / float(h), 4)
    if not record.get("thumbnailUrl"):
        from . import providers
        p = providers.for_record(record)
        if p:
            record["thumbnailUrl"] = p.thumbnail_url(record)
    return record

NOTE = ("Written only by tools/tourism/build.py resolve, only from an Unsplash API "
        "response that was then fetched over HTTP. Never hand-write an imageUrl here.")


def key(country_slug, category_id):
    return "%s/%s" % (country_slug, category_id)


class Cache:
    def __init__(self, raw=None, path=None):
        raw = raw or {}
        self.path = path or cache_file()
        self.version = raw.get("version", 1)
        self.entries = raw.get("entries", {})

    # -- reads ------------------------------------------------------------------

    def get(self, country_slug, category_id):
        return self.entries.get(key(country_slug, category_id))

    def has(self, country_slug, category_id):
        rec = self.get(country_slug, category_id)
        return bool(rec and rec.get("imageUrl"))

    @staticmethod
    def photo_key(record):
        """Provider-scoped: Unsplash ids and Pexels ids share no namespace, so
        the same string on two providers is two different photographs."""
        return "%s:%s" % (record.get("provider") or "?", record.get("photoId"))

    def photo_ids(self):
        """Every photo already spent, so the resolver never reuses one."""
        return {self.photo_key(r) for r in self.entries.values() if r.get("photoId")}

    def duplicates(self):
        """photoId -> [slot, slot, ...] for any id used more than once."""
        by_id = {}
        for slot, rec in sorted(self.entries.items()):
            if rec.get("photoId"):
                by_id.setdefault(self.photo_key(rec), []).append(slot)
        return {pid: slots for pid, slots in by_id.items() if len(slots) > 1}

    # -- writes -----------------------------------------------------------------

    def by_provider(self):
        counts = {}
        for r in self.entries.values():
            counts[r.get("provider") or "unknown"] = counts.get(r.get("provider") or "unknown", 0) + 1
        return counts

    def put(self, country_slug, category_id, record):
        missing = [f for f in REQUIRED if not record.get(f)]
        if missing:
            raise ValueError("refusing to cache an incomplete record, missing: %s"
                             % ", ".join(missing))
        self.entries[key(country_slug, category_id)] = record
        return record

    def drop(self, country_slug, category_id):
        return self.entries.pop(key(country_slug, category_id), None)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "version": self.version,
            "note": NOTE,
            "entries": dict(sorted(self.entries.items())),
        }
        with open(self.path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")


def load(path=None):
    path = path or cache_file()
    source = path
    if not os.path.exists(source) and path == CACHE_FILE and os.path.exists(LEGACY_FILE):
        source = LEGACY_FILE          # read the single-provider cache once
    if not os.path.exists(source):
        return Cache(path=path)
    with open(source) as f:
        cache = Cache(json.load(f), path=path)
    for record in cache.entries.values():
        migrate(record)
    return cache
