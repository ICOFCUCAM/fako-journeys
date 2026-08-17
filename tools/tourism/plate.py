"""Two pieces of the visual system that were being written four times each.

    the window   a country's outline with a photograph inside it
    the plate    what a slot looks like when there is no photograph yet

The window is the site's signature and was implemented separately in the
gateway, the atlas, the journey engine and the human layer — four copies of the
same clip-path, drifting. It is defined here once for the build and once in
scripts/window.js for the browser, and a test asserts the two agree.

The plate matters more than it sounds. Five hundred and sixty-seven of the five
hundred and ninety-four image slots in this dataset have no photograph, because
the resolver has never been run against real credentials. Every one of them was
rendering a grey box with its own alt text in it. That is most of what a visitor
currently sees, so it is not an edge case — it is the site's actual appearance,
and it deserves to be designed rather than merely survived.

So a slot without a photograph draws:

    the country's own outline, large and quiet, bled off one edge
    the category, in the label voice
    the caption, set at the size the photograph's headline would be
    the ground tinted with that country's region tone

Which means an unresolved Namibia looks like Namibia and not like an unresolved
Ghana, a page of them reads as a designed grid rather than as damage, and the
moment a photograph is resolved it takes the same box at the same aspect ratio
with no layout shift. It never says "image missing"; it says what the picture is
of, which is true and is also the most useful thing it can say.
"""

import html as html_mod

from .model import load_regions, region_of


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


# ---- the window ------------------------------------------------------------------


def window_svg(shape, name, image=None, alt=None, ident="w", classes="af-window-svg"):
    """A country's outline, with a photograph masked into it where there is one.

    `shape` is one entry of tourism/shapes.json: {w, h, d}. The same path draws
    the border and clips the picture, so the photograph arrives inside the exact
    outline of the country it was taken in and nothing is re-projected.

    Where there is no photograph the outline is filled instead — which is not a
    failure state, it is the same component with its picture not yet placed.
    """
    if not shape or not shape.get("d"):
        return ""
    label = alt if (image and alt) else "The outline of %s" % name
    art = ""
    if image:
        art = ('<image clip-path="url(#%s)" href="%s" x="0" y="0" width="%s" '
               'height="%s" preserveAspectRatio="xMidYMid slice"/>'
               % (esc(ident), esc(image), shape["w"], shape["h"]))
    # The outline goes in once and is referenced twice. It used to be written
    # out twice — once inside the clipPath and once as the visible fill — which
    # is 1.3 KB of identical coordinates per country and 27.5 KB on the gateway
    # alone, where twenty-two of these are inlined. <use> inside a clipPath is
    # plain SVG 1.1 and has worked everywhere since it existed.
    return ('<svg class="%s" viewBox="0 0 %s %s" role="img" aria-label="%s">'
            '<defs><path id="%s-d" d="%s"/>'
            '<clipPath id="%s"><use href="#%s-d"/></clipPath></defs>'
            '<use class="af-window-fill" href="#%s-d"/>%s</svg>'
            % (esc(classes), shape["w"], shape["h"], esc(label),
               esc(ident), shape["d"],
               esc(ident), esc(ident), esc(ident), art))


# ---- the plate -------------------------------------------------------------------


def tone_for(country, regions=None):
    """The ground a country is drawn on. Its region's, or the house ink."""
    _key, reg = region_of(country, regions if regions is not None else load_regions())
    return (reg.tone if reg and reg.tone else "#1C2A25")


def plate(country, entry, aspect, label, shape=None, regions=None, ident=None,
          ground=False):
    """One slot, with no photograph in it, drawn on purpose.

    `aspect` is the role's, so the plate occupies exactly the box the photograph
    will occupy and swapping one for the other shifts nothing. `label` is the
    category's own title. The caption is the entry's, which is a sentence
    somebody wrote about that country and not a placeholder.

    `ground=True` drops the type. Use it wherever the surrounding component
    already prints the caption — which is most places, and printing it twice is
    the difference between a colour field that looks decided and a card that
    looks like it rendered wrong.
    """
    aw, ah = aspect
    tone = tone_for(country, regions)
    ident = ident or ("pl-%s-%s" % (country.slug, entry.category or "x"))
    art = ""
    if shape and shape.get("d"):
        art = ('<svg class="af-plate-shape" viewBox="0 0 %s %s" aria-hidden="true">'
               '<path d="%s"/></svg>' % (shape["w"], shape["h"], shape["d"]))
    caption = entry.caption or (country.name)
    # A plate used as a full-bleed backdrop carries no type of its own: the page
    # already has a headline over it, and two headlines in the same box is not a
    # design, it is an accident.
    if ground:
        # Marked aria-hidden rather than labelled: in every place this variant is
        # used the caption and the category are already printed as text next to
        # it, so a label here would read the same sentence to a screen reader
        # twice.
        return ('<div class="af-plate af-plate--ground" '
                'style="aspect-ratio:%d/%d;--plate-tone:%s" aria-hidden="true">%s</div>'
                % (aw, ah, esc(tone), art))
    return (
        '<div class="af-plate" style="aspect-ratio:%d/%d;--plate-tone:%s" '
        'role="img" aria-label="%s" data-unresolved="true">'
        '%s'
        '<span class="af-plate-eye">%s</span>'
        '<span class="af-plate-say">%s</span>'
        '<span class="af-plate-where">%s</span>'
        '</div>'
        % (aw, ah, esc(tone), esc(label), art, esc((entry.category or "").replace("-", " ")),
           esc(caption), esc(country.name)))


def open_graph(title, description, path, kind="website", image=None):
    """The card a shared link becomes, and the icon in the browser tab.

    Absolute URLs, because a relative one in an Open Graph tag is a broken
    image on every platform that reads it.

    THE IMAGE

    There was none, and the reason given was that most of the photographs did
    not exist yet — pointing every card at the one that did would have made a
    card about Cameroon on a link about Ghana. That was right at the time. It
    left every one of fifteen hundred pages sharing as a blank rectangle, which
    is what a link to this site looked like in a message for as long as it
    stood.

    The brand mark answers it without that risk: a share card that shows the
    company is never wrong about the country. A page can still pass its own
    image and override this — a place page eventually should — but the floor is
    no longer nothing.

    THE ICON

    Also nothing, anywhere. The roundel scales down to a recognisable Africa at
    32px, which is more than most marks manage, so it is the tab icon at three
    sizes and the touch icon on a phone home screen.
    """
    base = "https://afrinkong.com"
    url = base + (path if path.startswith("/") else "/" + path)
    card = base + (image or "/images/brand/share.jpg")
    return ("\n".join([
        '<meta property="og:type" content="%s">' % kind,
        '<meta property="og:site_name" content="Afrinkong">',
        '<meta property="og:title" content="%s">' % title,
        '<meta property="og:description" content="%s">' % description,
        '<meta property="og:url" content="%s">' % url,
        '<meta property="og:image" content="%s">' % card,
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:image" content="%s">' % card,
        '<link rel="canonical" href="%s">' % url,
        icons(),
        # Every page that has a share card also declares who published it.
        # This is the one wiring point the whole site already passes through.
        ld(),
    ]))


def icons():
    """The tab icon, the home-screen icon, and the manifest.

    The manifest is what turns four icon files into an identity: saved to a
    phone's home screen this site was previously called whatever the <title>
    happened to say on the page somebody saved, opened in a browser chrome that
    contradicted its own theme colour, and offered no way in but the front
    door. It is named, scoped, themed, and carries three shortcuts to the three
    things people arrive for.

    Every icon it lists is a file that exists. A manifest naming an icon that is
    not there is worse than none: the browser falls back silently and nobody
    ever finds out.
    """
    return ("\n".join([
        '<link rel="icon" href="/images/brand/mark-32.png" sizes="32x32">',
        '<link rel="icon" href="/images/brand/mark-512.png" sizes="512x512">',
        '<link rel="apple-touch-icon" href="/images/brand/mark-180.png">',
        '<link rel="manifest" href="/site.webmanifest">',
        '<meta name="theme-color" content="#10251F">',
    ]))


ORG_ID = "https://afrinkong.com/#org"
SITE_ID = "https://afrinkong.com/#site"


def organisation_ld():
    """Who Afrinkong is, in the one vocabulary a machine reads.

    Fifty-four portrait pages carried an Article each and nothing anywhere said
    what the SITE was or who stood behind it. A search engine, an assistant or
    a model reading this domain could tell you a great deal about Djibouti and
    could not tell you that Afrinkong is a travel company, that it is a trading
    name of a Delaware LLC, or where its registration number is — all of
    which is printed in the footer of thirteen hundred pages in prose, which is
    exactly the form a machine cannot use.

    THE ADDRESS IS THE REGISTERED OFFICE AND IS TYPED AS ONE. company.json is
    emphatic that 8 The Green is a registered-agent address shared by a great
    many companies and must never be presented as somewhere to visit. Schema.org
    has no "registered office" address type, so it goes in as the organisation's
    `address` — which is correct — and the operating truth is carried by
    `areaServed` and by not inventing a telephone number for a door that has
    nobody behind it. No `openingHours`, no `geo`, no `telephone`.

    Two objects with stable ids, so everything else on the site can point at
    them by reference instead of repeating them: the organisation, and the
    website it publishes. The portrait pages carry an Article block of their
    own alongside this one — several blocks per page is ordinary and they
    are merged by anything that reads them, which is precisely why the ids are
    stable: the Article names its publisher by @id rather than describing the
    company a second time and slightly differently.
    """
    from .company import load as load_company
    d = load_company()
    o = d["office"]
    org = {
        "@type": "TravelAgency",
        "@id": ORG_ID,
        "name": d["brand"],
        "legalName": d["legal"],
        "url": "https://afrinkong.com/",
        "logo": "https://afrinkong.com/images/brand/mark-512.png",
        "image": "https://afrinkong.com/images/brand/share.jpg",
        "description": ("Afrinkong arranges journeys across Africa: time in "
                        "one country, priced per day, and crossings of several, "
                        "priced whole."),
        "identifier": {"@type": "PropertyValue",
                       "name": "Registration number",
                       "value": d["registration"]},
        "address": {"@type": "PostalAddress",
                    "streetAddress": o["street"],
                    "addressLocality": o["city"],
                    "addressRegion": o["region"],
                    "postalCode": o["postcode"],
                    "addressCountry": "US"},
        "areaServed": {"@type": "Place", "name": "Africa"},
        "knowsAbout": ["Travel in Africa", "Safari", "Overland journeys",
                       "African cities", "African cuisine"],
    }
    site = {
        "@type": "WebSite",
        "@id": SITE_ID,
        "url": "https://afrinkong.com/",
        "name": "Afrinkong",
        "publisher": {"@id": ORG_ID},
        "inLanguage": "en",
    }
    return {"@context": "https://schema.org", "@graph": [org, site]}


def ld(extra=None):
    """-> one <script> carrying the organisation, the site, and whatever this
    page adds to them. Anything page-specific goes in the SAME graph rather
    than a second block where it can be dropped independently."""
    import json as _json
    doc = organisation_ld()
    if extra:
        doc["@graph"].extend(extra if isinstance(extra, list) else [extra])
    # </script> inside a JSON string would end the block early. It cannot
    # happen with this data and it is one character to make it impossible.
    body = _json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("</", "<\\/")
    return '<script type="application/ld+json">%s</script>' % body


def events_block(path=None):
    """The event schema, inlined, plus the script that enforces it.

    Inlined rather than fetched because it is the thing that decides what may be
    recorded: a page that had already counted three events before its own rules
    arrived would be a page whose rules did not apply. It is under a kilobyte.
    """
    import json as _json
    import os as _os
    from .model import ROOT as _ROOT
    path = path or _os.path.join(_ROOT, "tourism", "events.json")
    try:
        with open(path) as fh:
            data = _json.load(fh)
    except (IOError, ValueError):
        return ""
    lean = {"events": data.get("events") or {}}
    return ('<script type="application/json" id="af-events">%s</script>\n'
            '<script src="/scripts/events.js" defer></script>'
            % _json.dumps(lean, separators=(",", ":"), sort_keys=True))


# ---- the stylesheet's contract ---------------------------------------------------

# What the plate and the window need from afrinkong.css, listed here so that a
# change to one is visibly a change to the other. Both classes live in the
# design system rather than in a page, because both appear on every surface.
CLASSES = ("af-window-svg", "af-window-fill", "af-plate", "af-plate-shape",
           "af-plate-eye", "af-plate-say", "af-plate-where")


def explore_block():
    """The universal index, on every page that ships this.

    Two script tags and nothing else: explore.js builds its own dialog the first
    time somebody presses the key, and fetches the index only then. A visitor who
    never opens it pays for two deferred requests that are cached across the whole
    site — which is the point of it living here rather than being a feature of one
    page.
    """
    return ('<script src="/scripts/story-search.js" defer></script>\n'
            '<script src="/scripts/explore.js" defer></script>')
