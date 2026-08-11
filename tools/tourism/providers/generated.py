"""Images this project made, rather than found.

A generated picture is not a search result, but once it is chosen it is a record
in the same cache as every other image and the renderer must not have to care.
So it arrives as a Provider like the other two, with three differences that the
rest of the system reads off the class rather than special-casing:

    image_host        "/images/generated/" — the bytes are ours and ship with
                      the site, so the delivery URL is a path, not a CDN.
    supports_resize   False. There is no CDN to ask for another width, so the
                      srcset is the one file at its real width, which is the
                      truth rather than four identical URLs with four different
                      width descriptors.
    attribution       there is no photographer. The credit says the picture was
                      generated and names the model, because a synthetic
                      photograph of a real place presented as a photograph of
                      that place is a lie told to a visitor.

It is deliberately NOT in the search registry: `resolve` must never call it, and
it has no search() to call. It is in BY_NAME so that a cached record can find its
owner, which is all the renderer, validator and imaging layer need.
"""

from .base import Provider


class Generated(Provider):
    name = "openai"
    key_env = "OPENAI_API_KEY"
    image_host = "/images/generated/"
    supports_focal_crop = False     # the composition has to be right in the original
    supports_resize = False
    generates = True

    def api_base(self):
        return "https://api.openai.com/v1"

    def auth_headers(self):
        return {"Authorization": "Bearer %s" % self.key()}

    def allowed_host(self):
        return self.image_host

    def preflight(self):
        raise NotImplementedError("generation is driven by tools/tourism/generate.py")

    def search(self, query, orientation, per_page=15):
        raise NotImplementedError("%s does not search; it generates" % self.name)

    def delivery_url(self, record, role, focal, width=None):
        """The file itself. No transform parameters exist for a static path, so
        the crop is done by CSS object-fit and the focal point by
        object-position — which imaging.py emits for every provider anyway."""
        url = (record or {}).get("imageUrl")
        if not url:
            raise ValueError("generated record has no imageUrl")
        return url

    def thumbnail_url(self, record):
        return (record or {}).get("thumbnailUrl") or (record or {}).get("imageUrl")

    def attribution(self, record):
        model = (record or {}).get("model") or "an image model"
        return ("AI-generated · %s" % model, None)
