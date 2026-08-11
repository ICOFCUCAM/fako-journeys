"""Photographs the site's owner supplied.

Separate from the generated provider, and deliberately not a variant of it. The
two look identical to the layout — a local file, no CDN, no resize — and are
completely different to a visitor:

    generated   a synthetic picture of a real place. The credit line has to say
                so, and does.
    uploaded    a real photograph belonging to whoever runs the site. It carries
                their credit, or none, and it must never be labelled AI.

Getting that backwards in either direction is the kind of error that matters, so
they are two classes with two hosts rather than one class with a flag.
"""

from .base import Provider


class Uploaded(Provider):
    name = "upload"
    key_env = "OPENAI_API_KEY"      # only for --describe; not needed to place one
    image_host = "/images/uploads/"
    supports_focal_crop = False
    supports_resize = False

    def api_base(self):
        return "https://api.openai.com/v1"

    def auth_headers(self):
        return {"Authorization": "Bearer %s" % self.key()}

    def allowed_host(self):
        return self.image_host

    def preflight(self):
        raise NotImplementedError("uploads are not fetched; they are already here")

    def search(self, query, orientation, per_page=15):
        raise NotImplementedError("%s does not search" % self.name)

    def delivery_url(self, record, role, focal, width=None):
        url = (record or {}).get("imageUrl")
        if not url:
            raise ValueError("uploaded record has no imageUrl")
        return url

    def thumbnail_url(self, record):
        return (record or {}).get("thumbnailUrl") or (record or {}).get("imageUrl")

    def attribution(self, record):
        """No provider to credit. If a photographer was named, name them; if not,
        say nothing rather than inventing a source."""
        who = (record or {}).get("photographer")
        return ((who, (record or {}).get("photographerUrl")) if who else (None, None))
