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
from .model import ROOT

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
    """The width ladder — or the single real width, for a provider that has no
    CDN to ask for another size. Four identical URLs carrying four different
    width descriptors would be three lies, and the browser believes descriptors:
    told a 1024px file is 2400px wide, it will pick it for a 2400px slot and
    scale it up."""
    if not record:
        return None
    provider = provider_for(record)
    if not provider.supports_resize:
        width = record.get("width") or role["width"]
        return "%s %dw" % (cdn_url(record, role, focal), int(width))
    return ", ".join("%s %dw" % (cdn_url(record, role, focal, width=w), w)
                     for w in role["srcset"])


def object_position(focal):
    return "%d%% %d%%" % (int(focal["x"]), int(focal["y"]))


def art_direction(record, role, focal):
    """A second crop for narrow screens, where the role asks for one.

    A 16:9 band is forty pixels tall inside a 390px phone: technically the same
    photograph, practically a different picture with the subject cut out of it.
    Where a role declares `mobile`, the same original is asked for again in a
    taller frame around the same focal point, and the browser is given both and
    told which width each belongs to.

    Returns None when the role does not ask for one, or when the provider has no
    CDN to cut a second crop with — a provider that cannot resize cannot art
    direct either, and pretending otherwise would serve the wide file to the
    narrow slot with a descriptor that lies about it.
    """
    mobile = role.get("mobile")
    if not record or not mobile:
        return None
    provider = provider_for(record)
    if not provider.supports_resize:
        return None
    narrow = dict(role)
    narrow["aspect"] = mobile["aspect"]
    narrow["width"] = min(role["width"], 1200)
    narrow["srcset"] = [w for w in role["srcset"] if w <= 1400] or [role["srcset"][0]]
    return {
        "media": "(max-width: %dpx)" % int(mobile.get("upTo") or 700),
        "srcset": srcset(record, narrow, focal),
        "sizes": "100vw",
        "aspect": "%d / %d" % (mobile["aspect"][0], mobile["aspect"][1]),
    }


def delivery(entry, role):
    """Everything a template needs for one image, resolved or not.

    When the photo is unresolved the local illustration is served instead, with
    the same focal point and the same no-layout-shift box. The page is never
    broken by an unresolved slot; it is only less specific.
    """
    w, h = dimensions(role)
    focal = entry.focal
    record = entry.image
    # An own photograph is the best evidence on the page, so it is ranked above
    # a resolved stock URL rather than below it. `local` stays what it always
    # was — an illustration standing in for a photograph that is not here yet —
    # and is still last.
    own = getattr(entry, "photo", None)
    resolved = bool(record and record.get("imageUrl")) and not own
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
        # What the crop must not throw away. Carried through so the review sheet
        # can print it beside the candidate and a reviewer can check the crop
        # against the instruction rather than against their own memory of it.
        "focus": role.get("focus") or "",
        "mobile": None,
        "credit": None,
    }
    if resolved:
        provider = provider_for(record)
        out["src"] = cdn_url(record, role, focal)
        out["srcset"] = srcset(record, role, focal)
        out["mobile"] = art_direction(record, role, focal)
        text, link = provider.attribution(record)
        out["credit"] = {
            "name": record.get("photographer"),
            "link": record.get("photographerUrl"),
            "photo": record.get("sourceUrl"),
            "provider": provider.name,
            "text": text,
            "href": link,
        }
    elif own:
        # Not a placeholder, and never credited to a stock provider. It carries
        # `upload` for the same reason images/uploads/ exists at all: the folder
        # a URL sits on is the proof of what kind of picture it is.
        out["src"] = own
        out["resolved"] = True
        out["provider"] = "upload"
        # A stock photograph is resized by its CDN from a query parameter; a
        # file on disk cannot be, so the narrow variant has to already exist.
        # Offered only when it does — a srcset naming a file that is not there
        # is worse than none, because the browser will pick it.
        narrow = own.replace("-1600w.", "-800w.")
        if narrow != own and os.path.exists(
                os.path.join(ROOT, narrow.lstrip("/"))):
            out["srcset"] = "%s 800w, %s 1600w" % (narrow, own)
    elif entry.local:
        out["src"] = entry.local
        out["placeholder"] = True
    return out
