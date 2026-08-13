"""Pexels — the fallback provider.

API:  GET https://api.pexels.com/v1/search
Auth: Authorization: <api key>          (no "Bearer" prefix — Pexels is unusual here)
CDN:  images.pexels.com

One real difference from Unsplash, worth being honest about rather than
papering over: the Pexels CDN has no focal-point crop. It can resize and
centre-crop, and that is all. So a focal point is still stored and still
applied — as CSS `object-position` in the page — but it cannot be pushed into
the URL the way imgix allows. `supports_focal_crop = False` is what lets the
resolver prefer Unsplash for the crops where that matters most.
"""

import os
import urllib.parse

from .base import Candidate, Provider, RateLimited, Unavailable


class Pexels(Provider):
    name = "pexels"
    requires_attribution = True
    key_env = "PEXELS_API_KEY"
    image_host = "https://images.pexels.com/"
    supports_focal_crop = False

    def api_base(self):
        return os.environ.get("PEXELS_API_BASE") or "https://api.pexels.com/v1"

    def auth_headers(self):
        return {"Authorization": self.key()}

    def preflight(self):
        try:
            self.get_json(self.api_base() + "/curated?per_page=1")
        except RateLimited:
            raise
        except Exception as exc:
            raise Unavailable("cannot reach api.pexels.com (%s)" % exc)
        return True

    def search(self, query, orientation, per_page=15):
        url = self.api_base() + "/search?" + urllib.parse.urlencode({
            "query": query, "orientation": orientation,
            "per_page": per_page, "size": "large",
        })
        payload = self.get_json(url)
        out = []
        for p in payload.get("photos", []):
            src = p.get("src") or {}
            source = src.get("original")
            if not p.get("id") or not self.owns(source or ""):
                continue
            out.append(Candidate({
                "provider": self.name,
                "photoId": str(p["id"]),
                "imageUrl": source.split("?", 1)[0],
                "sourceUrl": p.get("url"),
                "photographer": p.get("photographer"),
                "photographerUrl": p.get("photographer_url"),
                "width": p.get("width"),
                "height": p.get("height"),
                "text": p.get("alt") or "",
            }))
        return out

    def after_use(self, candidate):
        """Pexels has no download-tracking endpoint. Attribution is still
        required, and is rendered with the picture."""
        return

    def delivery_url(self, record, role, focal, width=None):
        base = (record.get("imageUrl") or "").split("?", 1)[0]
        if not self.owns(base):
            raise ValueError("not a Pexels CDN URL: %r" % base)
        w = int(width or role["width"])
        aw, ah = role["aspect"]
        h = int(round(w * ah / aw))
        # No focal-point crop available here; the page carries object-position.
        return self.qs(base, [
            ("auto", "compress"), ("cs", "tinysrgb"), ("fit", "crop"),
            ("w", w), ("h", h),
        ])

    def thumbnail_url(self, record):
        base = (record.get("imageUrl") or "").split("?", 1)[0]
        return self.qs(base, [("auto", "compress"), ("cs", "tinysrgb"),
                              ("fit", "crop"), ("w", 400), ("h", 300)])
