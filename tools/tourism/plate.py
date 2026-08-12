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
    return ('<svg class="%s" viewBox="0 0 %s %s" role="img" aria-label="%s">'
            '<defs><clipPath id="%s"><path d="%s"/></clipPath></defs>'
            '<path class="af-window-fill" d="%s"/>%s</svg>'
            % (esc(classes), shape["w"], shape["h"], esc(label),
               esc(ident), shape["d"], shape["d"], art))


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


# ---- the stylesheet's contract ---------------------------------------------------

# What the plate and the window need from afrinkong.css, listed here so that a
# change to one is visibly a change to the other. Both classes live in the
# design system rather than in a page, because both appear on every surface.
CLASSES = ("af-window-svg", "af-window-fill", "af-plate", "af-plate-shape",
           "af-plate-eye", "af-plate-say", "af-plate-where")
