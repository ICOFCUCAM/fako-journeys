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
CACHE_FILE = os.path.join(CACHE_DIR, "unsplash.json")


def cache_file():
    """Overridable so tests and CI never write the repo's cache."""
    return os.environ.get("UNSPLASH_CACHE_FILE") or CACHE_FILE

# Exactly the schema the brief specifies, plus provenance timestamps.
FIELDS = (
    "photoId", "photographer", "photographerUrl", "unsplashUrl", "imageUrl",
    "category", "country", "query", "alt", "width", "height", "focalPoint",
    "resolvedAt", "verifiedAt",
)

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

    def photo_ids(self):
        """Every photo id already spent, so the resolver never reuses one."""
        return {r.get("photoId") for r in self.entries.values() if r.get("photoId")}

    def duplicates(self):
        """photoId -> [slot, slot, ...] for any id used more than once."""
        by_id = {}
        for slot, rec in sorted(self.entries.items()):
            pid = rec.get("photoId")
            if pid:
                by_id.setdefault(pid, []).append(slot)
        return {pid: slots for pid, slots in by_id.items() if len(slots) > 1}

    # -- writes -----------------------------------------------------------------

    def put(self, country_slug, category_id, record):
        missing = [f for f in ("photoId", "imageUrl", "photographer") if not record.get(f)]
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
    if not os.path.exists(path):
        return Cache(path=path)
    with open(path) as f:
        return Cache(json.load(f), path=path)
