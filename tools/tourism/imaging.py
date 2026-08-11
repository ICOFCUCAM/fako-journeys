"""Delivery: turn a resolved photo plus a focal point into an actual <img>.

Two things happen here that a naive implementation gets wrong.

1. The focal point is pushed into the *CDN crop* (`crop=focalpoint&fp-x&fp-y`),
   not only into CSS `object-position`. When the CDN returns a 4:3 frame cut from
   a 3:2 original it has to decide what to throw away; without fp-x/fp-y it throws
   away whatever is not in the middle. The CSS value is still emitted as a second
   line of defence for the cases where the element's box does not match the
   delivered ratio.

2. Width and height attributes are always emitted, from the role's aspect ratio,
   so the browser reserves the box before the bytes arrive. No layout shift.
"""

import os

UNSPLASH_HOST = "https://images.unsplash.com/"

# Test hook. The resolver and the delivery builder both refuse any source that is
# not the Unsplash CDN; the end-to-end test needs to point that at a local mock.
# Never set this outside tests — validate.py still checks stored data against the
# real host, so a dataset resolved against a mock will fail validation.
def allowed_host():
    return os.environ.get("UNSPLASH_IMAGE_HOST_OVERRIDE") or UNSPLASH_HOST


def dimensions(role, width=None):
    w = int(width or role["width"])
    aw, ah = role["aspect"]
    return w, int(round(w * ah / aw))


def cdn_url(photo_url, role, focal, width=None):
    """Build a delivery URL from a *resolved* Unsplash photo URL.

    photo_url must already be a real images.unsplash.com URL returned by the API.
    This function only appends transform parameters; it never invents an id.
    """
    if not photo_url:
        return None
    if not photo_url.startswith(allowed_host()):
        raise ValueError("refusing to build a delivery URL for a non-Unsplash source: %r" % photo_url)
    base = photo_url.split("?", 1)[0]
    w, h = dimensions(role, width)
    params = [
        "auto=format",
        "fit=crop",
        "crop=focalpoint",
        "fp-x=%.3f" % (float(focal["x"]) / 100.0),
        "fp-y=%.3f" % (float(focal["y"]) / 100.0),
        "w=%d" % w,
        "h=%d" % h,
        "q=%d" % role.get("quality", 82),
    ]
    return base + "?" + "&".join(params)


def srcset(photo_url, role, focal):
    if not photo_url:
        return None
    return ", ".join(
        "%s %dw" % (cdn_url(photo_url, role, focal, width=w), w) for w in role["srcset"]
    )


def object_position(focal):
    return "%d%% %d%%" % (int(focal["x"]), int(focal["y"]))


def delivery(entry, role):
    """Everything a template needs for one image, resolved or not.

    When the photo is unresolved the local illustration is served instead, at its
    natural ratio, with the same focal point and the same no-layout-shift box.
    The page is never broken by an unresolved slot; it is only less specific.
    """
    w, h = dimensions(role)
    focal = entry.focal
    resolved = bool(entry.image and entry.image.get("imageUrl"))
    out = {
        "resolved": resolved,
        "width": w,
        "height": h,
        "aspect": "%d / %d" % (role["aspect"][0], role["aspect"][1]),
        "loading": role["loading"],
        "priority": role.get("priority", False),
        "objectPosition": object_position(focal),
        "src": None,
        "srcset": None,
        "sizes": role["sizes"],
        "credit": None,
    }
    if resolved:
        photo = entry.image
        out["src"] = cdn_url(photo["imageUrl"], role, focal)
        out["srcset"] = srcset(photo["imageUrl"], role, focal)
        out["credit"] = {
            "name": photo.get("photographer"),
            "link": photo.get("photographerUrl"),
            "photo": photo.get("unsplashUrl"),
        }
    elif entry.local:
        out["src"] = entry.local
        out["placeholder"] = True
    return out
