"""What every image provider must look like.

The rest of the system knows nothing about Unsplash or Pexels. It asks a
provider for candidates, scores them, and asks the provider to build a delivery
URL. Adding a third provider means adding one file here and one line in the
registry — no change to the resolver, the renderer, the cache or the pages.

The one rule every provider inherits: `search()` may only return URLs the API
handed back. No provider is permitted to assemble a URL from an id.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

UA = "fako-journeys-tourism-image-system/2"


class Unavailable(Exception):
    """No key, or no route to the API. An environment problem, not a data one."""


class RateLimited(Exception):
    """Quota spent. Everything resolved so far is cached, so run again later."""


class Candidate(dict):
    """A normalised search result. Providers translate their own payload into
    this shape so the resolver never branches on provider."""

    @property
    def aspect(self):
        h = self.get("height") or 0
        return (self.get("width") or 0) / float(h) if h else 0


class Provider:
    name = "abstract"
    key_env = ""
    image_host = ""            # every stored imageUrl must start with this
    supports_focal_crop = False   # can the CDN crop around a focal point?
    supports_resize = True        # can it serve the same picture at another width?
    generates = False             # makes images rather than finding them

    # Two facts the quality gate needs and could otherwise only guess at from
    # the provider's name — which is exactly the sort of guess that lets a
    # synthetic picture publish itself as documentary photography.
    #
    #   synthetic              the pictures are made, not taken. Every record
    #                          from this provider must carry `generated`, and
    #                          the credit line must say so.
    #   requires_attribution   the licence obliges us to name the photographer.
    #                          A record without one is a licence breach, not a
    #                          design shortfall, so the gate treats it as an
    #                          error and refuses to publish the country.
    synthetic = False
    requires_attribution = False

    # -- configuration ----------------------------------------------------------

    def api_base(self):
        raise NotImplementedError

    def key(self):
        value = os.environ.get(self.key_env)
        if not value:
            raise Unavailable("%s is not set" % self.key_env)
        return value

    def available(self):
        return bool(os.environ.get(self.key_env))

    def allowed_host(self):
        """Overridable so the tests can point at a local mock."""
        return os.environ.get("%s_IMAGE_HOST_OVERRIDE" % self.name.upper()) or self.image_host

    # -- http -------------------------------------------------------------------

    def auth_headers(self):
        raise NotImplementedError

    def get(self, url, timeout=20, auth=True):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if auth:
            for k, v in self.auth_headers().items():
                req.add_header(k, v)
        return urllib.request.urlopen(req, timeout=timeout)

    def get_json(self, url, timeout=20):
        try:
            with self.get(url, timeout=timeout) as r:
                remaining = r.headers.get("X-Ratelimit-Remaining")
                payload = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and self.quota_is_403:
                raise RateLimited("%s: quota spent or key rejected (HTTP %d)"
                                  % (self.name, exc.code))
            if exc.code == 429:
                raise RateLimited("%s: rate limited (HTTP 429)" % self.name)
            raise
        if remaining is not None and str(remaining).isdigit() and int(remaining) <= 1:
            # Stop with one request still in hand rather than discovering the
            # limit through a wall of identical failures.
            raise RateLimited("%s: %s requests left this window" % (self.name, remaining))
        return payload

    quota_is_403 = False

    # -- interface --------------------------------------------------------------

    def preflight(self):
        """Fail early and clearly rather than part-way through 189 slots."""
        raise NotImplementedError

    def search(self, query, orientation, per_page=15):
        """-> [Candidate]. Must not be called unless available()."""
        raise NotImplementedError

    def delivery_url(self, record, role, focal, width=None):
        """A CDN URL for one crop, built by appending transform parameters to a
        URL the API returned."""
        raise NotImplementedError

    def thumbnail_url(self, record):
        raise NotImplementedError

    def attribution(self, record):
        """(text, link) for the visible credit. Both providers require one."""
        return ("%s / %s" % (record.get("photographer") or "Unknown",
                             self.name.title()),
                record.get("sourceUrl") or record.get("photographerUrl"))

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def qs(base, params):
        return base.split("?", 1)[0] + "?" + urllib.parse.urlencode(params)

    def owns(self, url):
        return bool(url) and url.startswith(self.allowed_host())
