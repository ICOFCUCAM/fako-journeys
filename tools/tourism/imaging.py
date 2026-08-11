"""Delivery: turn a resolved record plus a focal point into an actual <img>.

Provider-neutral by construction. This module knows that an image has a role, a
focal point and a set of widths; it asks whichever provider owns the record to
build the URLs. A component never learns where a photograph came from.

Three things here that a naive implementation gets wrong:

1. The focal point goes into the *CDN crop* where the CDN supports it
   (`crop=focalpoint&fp-x&fp-y` on Unsplash/imgix), not only into CSS
   `object-position`. When a CDN returns a 4:3 frame cut from a 3:2 original it
   has to decide what to discard; without a focal point it discards whatever is
   not in the middle. Pexels has no such parameter, so for those records the CSS
   value is the only defence — which is exactly why it is always emitted too.

2. Width and height attributes are always present, derived from the role's
   aspect ratio, so the browser reserves the box before the bytes arrive.

3. Sizes come from the role, so a 368px card never downloads a 2400px hero.
"""

import os

from . import providers

UNSPLASH_HOST = "https://images.unsplash.com/"      # kept for existing callers


def allowed_host():
    """The primary provider's host. Historic helper — prefer providers.owns_any."""
    return os.environ.get("UNSPLASH_IMAGE_HOST_OVERRIDE") or UNSPLASH_HOST


def dimensions(role, width=None):
    w = int(width or role["width"])
    aw, ah = role["aspect"]
    return w, int(round(w * ah / aw))


def provider_for(record):
    p = providers.for_record(record)
    if p is None:
        raise ValueError("no provider owns this record: %r"
                         % (record or {}).get("imageUrl"))
    return p


def cdn_url(record, role, focal, width=None):
    """Delivery URL for one crop. `record` is a cached image record."""
    if not record:
        return None
    return provider_for(record).delivery_url(record, role, focal, width)


def srcset(record, role, focal):
    if not record:
        return None
    return ", ".join("%s %dw" % (cdn_url(record, role, focal, width=w), w)
                     for w in role["srcset"])


def object_position(focal):
    return "%d%% %d%%" % (int(focal["x"]), int(focal["y"]))


def delivery(entry, role):
    """Everything a template needs for one image, resolved or not.

    When the photo is unresolved the local illustration is served instead, with
    the same focal point and the same no-layout-shift box. The page is never
    broken by an unresolved slot; it is only less specific.
    """
    w, h = dimensions(role)
    focal = entry.focal
    record = entry.image
    resolved = bool(record and record.get("imageUrl"))
    out = {
        "resolved": resolved,
        "provider": (record or {}).get("provider"),
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
        provider = provider_for(record)
        out["src"] = cdn_url(record, role, focal)
        out["srcset"] = srcset(record, role, focal)
        text, link = provider.attribution(record)
        out["credit"] = {
            "name": record.get("photographer"),
            "link": record.get("photographerUrl"),
            "photo": record.get("sourceUrl"),
            "provider": provider.name,
            "text": text,
            "href": link,
        }
    elif entry.local:
        out["src"] = entry.local
        out["placeholder"] = True
    return out
