"""Unsplash — the primary provider.

API:  GET https://api.unsplash.com/search/photos
Auth: Authorization: Client-ID <access key>
CDN:  images.unsplash.com, which is imgix, so it can crop around a focal point.
"""

import os
import urllib.parse

from .base import Candidate, Provider, RateLimited, Unavailable


class Unsplash(Provider):
    name = "unsplash"
    requires_attribution = True
    key_env = "UNSPLASH_ACCESS_KEY"
    image_host = "https://images.unsplash.com/"
    supports_focal_crop = True      # imgix: crop=focalpoint&fp-x&fp-y
    quota_is_403 = True             # Unsplash answers 403, not 429, when spent

    def api_base(self):
        return os.environ.get("UNSPLASH_API_BASE") or "https://api.unsplash.com"

    def key(self):
        value = os.environ.get(self.key_env) or os.environ.get("UNSPLASH_API_KEY")
        if not value:
            raise Unavailable("UNSPLASH_ACCESS_KEY is not set")
        return value

    def available(self):
        return bool(os.environ.get(self.key_env) or os.environ.get("UNSPLASH_API_KEY"))

    def auth_headers(self):
        return {"Authorization": "Client-ID " + self.key(), "Accept-Version": "v1"}

    def preflight(self):
        try:
            self.get_json(self.api_base() + "/photos/random?count=1")
        except RateLimited:
            raise
        except Exception as exc:
            raise Unavailable("cannot reach api.unsplash.com (%s)" % exc)
        return True

    def search(self, query, orientation, per_page=15):
        url = self.api_base() + "/search/photos?" + urllib.parse.urlencode({
            "query": query, "orientation": orientation,
            "per_page": per_page, "content_filter": "high",
        })
        payload = self.get_json(url)
        out = []
        for p in payload.get("results", []):
            urls = p.get("urls") or {}
            source = urls.get("raw") or urls.get("full")
            if not p.get("id") or not self.owns(source or ""):
                continue
            user = p.get("user") or {}
            out.append(Candidate({
                "provider": self.name,
                "photoId": p["id"],
                "imageUrl": source.split("?", 1)[0],
                "sourceUrl": (p.get("links") or {}).get("html"),
                "photographer": user.get("name"),
                "photographerUrl": (user.get("links") or {}).get("html"),
                "width": p.get("width"),
                "height": p.get("height"),
                # what the picture says it is — the relevance scorer reads this
                # The blob below is for MATCHING — more words, better recall.
                # `wrote` is the photographer's own sentence and nothing else,
                # because alt_description is generated and sometimes wrong:
                # it called a caracal in the Ngorongoro Crater "brown and white
                # deer on green grass field". Matching wants every word; alt
                # text wants only the words a person chose.
                "wrote": (p.get("description") or "").strip(),
                "text": " ".join(filter(None, [
                    p.get("alt_description"), p.get("description"),
                    ((p.get("location") or {}).get("name")),
                    " ".join(t.get("title", "") for t in (p.get("tags") or [])),
                ])),
                "downloadLocation": (p.get("links") or {}).get("download_location"),
            }))
        return out

    def after_use(self, candidate):
        """Unsplash's API guidelines require pinging the download endpoint when a
        photo is actually used. Best effort — never fail a resolve over it."""
        dl = candidate.get("downloadLocation")
        if not dl:
            return
        try:
            self.get(dl, timeout=10).read(32)
        except Exception:
            pass

    def delivery_url(self, record, role, focal, width=None):
        base = (record.get("imageUrl") or "").split("?", 1)[0]
        if not self.owns(base):
            raise ValueError("not an Unsplash CDN URL: %r" % base)
        w = int(width or role["width"])
        aw, ah = role["aspect"]
        h = int(round(w * ah / aw))
        return self.qs(base, [
            ("auto", "format"), ("fit", "crop"), ("crop", "focalpoint"),
            ("fp-x", "%.3f" % (float(focal["x"]) / 100.0)),
            ("fp-y", "%.3f" % (float(focal["y"]) / 100.0)),
            ("w", w), ("h", h), ("q", role.get("quality", 82)),
        ])

    def thumbnail_url(self, record):
        base = (record.get("imageUrl") or "").split("?", 1)[0]
        return self.qs(base, [("auto", "format"), ("fit", "crop"),
                              ("w", 400), ("h", 300), ("q", 70)])
