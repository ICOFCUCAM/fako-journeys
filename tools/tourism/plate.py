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

import os

from .model import ROOT, load_regions, region_of


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


# ---- the window ------------------------------------------------------------------


# The largest the window's photograph is ever painted, measured in a browser:
# 328 CSS pixels on a desktop and 239 on a 390-pixel phone, which at three
# device pixels is 717. An 800-wide file covers every case with room to spare.
WINDOW_DEVICE_PX = 800


def window_size(href):
    """-> the same photograph at a width the window can actually use.

    SVG <image> has no srcset. It takes one URL and paints it into a fixed box,
    so the responsive pass that fixed every <img> on the site could do nothing
    here — and the hero was serving 1200-wide files into a box that is 328
    pixels across on a desktop and 239 on a phone. Four hundred and eighty
    pixels of photograph per country, decoded and thrown away.

    Falls back to what it was given: a country whose 800 has not been made yet
    keeps its original rather than pointing at a file that does not exist.
    """
    import re as _re
    m = _re.match(r"^(/images/uploads/.+)-(\d+)w\.(jpg|jpeg|png|webp)$", href or "")
    if not m or int(m.group(2)) <= WINDOW_DEVICE_PX:
        return href
    want = "%s-%dw.%s" % (m.group(1), WINDOW_DEVICE_PX, m.group(3))
    return want if os.path.exists(os.path.join(ROOT, want.lstrip("/"))) else href


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
        image = window_size(image)
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


# A search result shows about 155 characters of a description and throws the
# rest away. Measured across the site, 125 pages were over 160 and the worst was
# 411 — two and a half times the budget, so two thirds of a carefully written
# sentence was being cut mid-word in the one place it was meant to be read.
META_LIMIT = 155


# A search result shows about sixty characters of a title. Fifty-eight country
# pages ran to a hundred and four, of which the last thirty-three were "|
# Guided Journeys and Experiences" — identical on every one of them, never
# visible on any of them, and pushing the only distinctive part past the cut.
TITLE_LIMIT = 60


def fit_title(name, line, brand="Afrinkong", limit=TITLE_LIMIT):
    """-> "Togo — a line | Afrinkong", inside the budget, name first.

    Same pecking order as fit(): the country's name is what somebody is
    scanning for and never goes; the brand is worth keeping if it costs nine
    characters and not if it costs thirty-three; the editorial line is trimmed
    at a word rather than a syllable.

    The brand is dropped rather than the line when both cannot fit. A result
    reading "Togo — Fifty kilometres wide, and a different country…" tells a
    reader what the page is; one reading "Togo — Fifty kilometres wide, and…
    | Afrinkong" spends its last characters on a word the reader has already
    seen in the URL.
    """
    name = " ".join((name or "").split())
    line = " ".join((line or "").split())
    tail = " | %s" % brand if brand else ""

    full = "%s \u2014 %s%s" % (name, line, tail)
    if len(full) <= limit:
        return full
    without = "%s \u2014 %s" % (name, line)
    if len(without) <= limit:
        return without
    room = limit - len(name) - 3          # name, space, em dash, space
    if room < 12:
        return name[:limit]
    clip = line[:room - 1].rsplit(" ", 1)[0].rstrip(" ,;:-\u2014")
    return "%s \u2014 %s\u2026" % (name, clip)


def fit(head, body, tail="", limit=META_LIMIT):
    """-> a description that fits, cut where a sentence ends rather than mid-word.

    Three parts, and they are dropped in order of how much they are worth:

        head   the country or place name. Never dropped — it is what the
               reader is scanning the result for.
        body   the editorial sentence, and the only part that differs between
               pages. Kept as whole sentences for as long as they fit, and
               failing that trimmed to a word boundary with an ellipsis.
        tail   the boilerplate. Identical on every page of a family, so it adds
               nothing a search engine can tell apart, and it is the first
               thing to go when the budget is tight.

    The old shape was head + body + tail with no budget at all, which meant a
    long body pushed the tail past the cut on the pages where the body was
    already good, and left it in on the pages where the body was thin.
    """
    head = " ".join((head or "").split())
    body = " ".join((body or "").split())
    tail = " ".join((tail or "").split())
    room = limit - len(head)
    if room <= 0:
        return head[:limit].rstrip()

    if len(body) + (1 + len(tail) if tail else 0) <= room:
        return (head + " " + body + ((" " + tail) if tail else "")).strip()

    if len(body) <= room:                       # body fits, tail does not
        return (head + " " + body).strip()

    # Keep whole sentences while they fit. Joined with a space, because
    # _sentence_end returns the index just past the full stop and the space
    # that followed it is on the other side of the cut — without this the
    # result read "From the Atlantic to the Indian Ocean.From rainforest to
    # savanna.", which is worse than the overlong sentence it replaced.
    kept, rest = [], body
    used = 0
    while True:
        cut = _sentence_end(rest)
        if cut <= 0 or used + cut + (1 if kept else 0) > room:
            break
        kept.append(rest[:cut].strip())
        used += cut + (1 if len(kept) > 1 else 0)
        rest = rest[cut:].lstrip()
    out = " ".join(kept).strip()
    if out:
        # Room left over and more to say: add a clipped fragment rather than
        # stopping short. One sentence of a three-sentence description is a
        # thin result when eighty characters of budget are going unused.
        spare = room - len(out) - 1
        if rest and spare > 30:
            clip = rest[:spare - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
            if clip:
                out = out + " " + clip + "\u2026"
        return (head + " " + out).strip()

    # Not even one sentence fits: trim to a word, and say so with an ellipsis
    # rather than stopping mid-word as the untrimmed version did.
    clip = body[:max(0, room - 1)].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (head + " " + clip + "\u2026").strip()


def _sentence_end(text):
    """-> index just past the first sentence, or 0 if there is not one."""
    import re as _re
    m = _re.search(r"[.!?](?=\s|$)", text)
    return m.end() if m else 0


def open_graph(title, description, path, kind="website", image=None,
               extra=None):
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
    graph = list(extra if isinstance(extra, list) else [extra]) if extra else []
    crumbs = trail(path, title)
    if crumbs:
        graph.append(crumbs)
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
        # `extra` is whatever this page adds to that graph — a trip, a
        # place — carried in the SAME graph so it can point at the
        # organisation by @id instead of describing it a second time. The
        # trail joins them there for the same reason: one graph, one place a
        # reader has to look.
        ld(graph or None),
    ]))


CRUMB_SECTIONS = {
    "tourism": ("Every country", "/tourism/"),
    "places": ("Every place", "/places"),
    "portrait": ("Stories", "/stories"),
    "trans-afrique": ("Trans Afrique", "/trans-afrique"),
    "journey-fund": ("The Journey Fund", "/journey-fund"),
}

_NAMES = {}


def _country_names():
    """-> {slug: name}, read once, for the middle crumb of a place page.

    Only the name is wanted, so this reads the country files directly rather
    than through load_countries(): that builds fifty-five Country objects with
    their entries, caches and images attached, and this needs one string from
    each.
    """
    if _NAMES:
        return _NAMES
    import json as _json
    d = os.path.join(ROOT, "tourism", "countries")
    try:
        files = sorted(os.listdir(d))
    except OSError:
        return _NAMES
    for f in files:
        if not f.endswith(".json") or f.startswith("_"):
            continue
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                raw = _json.load(fh)
        except (OSError, ValueError):
            continue
        if raw.get("name"):
            _NAMES[raw.get("slug") or f[:-5]] = raw["name"]
    return _NAMES


def _leaf(title):
    """-> the page's own name, without the brand and without entities.

    Some callers pass a title through esc() and some do not, so this arrives
    as either `Côte d'Ivoire` or `C&#xf4;te d&#x27;Ivoire`. Unescaped here
    because the result goes into JSON, where an HTML entity is six literal
    characters and not an apostrophe.

    The brand comes off because it is already on the trail: a crumb reading
    "Zimbabwe: a portrait — Afrinkong" under a crumb reading "Home" says the
    company's name twice and the page's name once.
    """
    t = html_mod.unescape(title)
    for tail in (" — Afrinkong", " – Afrinkong", " - Afrinkong"):
        if t.endswith(tail):
            t = t[:-len(tail)]
            break
    return t.strip()


def trail(path, title):
    """-> a BreadcrumbList for this page, or None for the front door.

    WHAT THIS IS FOR

    Fifteen hundred and ninety-four pages, four levels deep at the deepest, and
    nothing anywhere said how one page sat under another. A result for a place
    page showed the raw address — afrinkong.com › places › zimbabwe ›
    victoria-falls — spelled out in slugs, because that is what a search engine
    falls back to when the page does not tell it the trail in words.

    The trail is derived from the address rather than passed in by sixteen
    callers, because the address is already the hierarchy: it is how the site
    is laid out on disk, it is what the canonical says, and a trail that
    disagreed with the URL would be the wrong trail.

    THE COUNTRY CRUMB ON A PLACE PAGE

    /places/zimbabwe/victoria-falls sits under Zimbabwe, and Zimbabwe's page is
    /tourism/zimbabwe. Crossing from one section into another looks odd written
    down and is right: the parent of a place in Zimbabwe is Zimbabwe, not the
    index of every place in Africa. It is only added when that country page
    exists, because a crumb pointing at a 404 is worse than a shorter trail.
    """
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return None
    here = "/" + "/".join(parts)
    crumbs = [("Home", "/")]
    sec = CRUMB_SECTIONS.get(parts[0])
    if sec and sec[1].rstrip("/") != here.rstrip("/"):
        crumbs.append(sec)
    leaf = _leaf(title)
    # A CRUMB IS NOT A TITLE.
    #
    # A page title has to stand alone in a tab and in a result, so it carries
    # the country and often the count: "Zimbabwe — all 18 experiences",
    # "Victoria Falls, Zimbabwe". A crumb is read along a line that already
    # says where it is, so it wants the shortest true name — and on a country
    # page that name is known exactly, rather than trimmed out of a sentence.
    known = _country_names().get(parts[1]) if len(parts) > 1 else None
    if len(parts) == 2 and parts[0] in ("tourism", "portrait") and known:
        leaf = known
    if sec and len(crumbs) > 1:
        # The crossing pages title themselves "Trans Afrique — West — Trans
        # Afrinkong", which is the right title for a tab and reads on a trail
        # as the series name three crumbs from the series crumb. Whatever the
        # crumb above already says, this one does not need to repeat.
        for sep in (" — ", " – ", ": "):
            if leaf.startswith(sec[0] + sep):
                leaf = leaf[len(sec[0] + sep):]
            if leaf.endswith(sep + sec[0]):
                leaf = leaf[:-len(sep + sec[0])]
        leaf = leaf.strip()
    if parts[0] == "places" and len(parts) == 3:
        if known and os.path.exists(
                os.path.join(ROOT, "tourism", parts[1] + ".html")):
            crumbs.append((known, "/tourism/" + parts[1]))
            if leaf.endswith(", " + known):
                leaf = leaf[:-len(", " + known)]
    crumbs.append((leaf, here))
    base = "https://afrinkong.com"
    return {
        "@type": "BreadcrumbList",
        "@id": base + here + "#trail",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n,
             "item": base + u}
            for i, (n, u) in enumerate(crumbs)],
    }


# =========================================================================
# THE SHELL. Phase 5 + 6.
#
# One navigation system, one shell, one visual language, and product identity
# on top of it rather than instead of it.
#
# WHAT THIS REPLACES
#
# Ten masthead classes across 1,597 pages — pl-mast (1,461), fj-mast (60),
# mast (52), jn-mast (17), jf-mast (3), wa-mast, mt-mast, at-mast, top. Ten
# interpretations of the same idea, none of which knew about the others, and
# one of which (fj-mast) was worn by two DIFFERENT companies: Afrinkong's 55
# tourism pages and the Kamerun operator's five own pages, which carry
# completely different navigation. A change to that one class changed two
# products at once.
#
# THE SPINE IS EXPLORE -> PLAN -> TRAVEL. THE NAVIGATION SHOWS TWO.
#
# TRAVEL is not here because bookable travel is not operational, and FUND is
# not here because issuance and the wallet are gated. A navigation item that
# says "click here to do something you cannot do" is the one failure this
# programme has spent its whole life avoiding. Both join the moment they are
# real, and nothing in this file has to be redesigned when they do — they are
# two more entries in AREAS.
#
# WHY TWO ROWS AND NOT A DROPDOWN
#
# The shell must work with no JavaScript. portrait.js states the site's rule in
# its own header — the page is complete before the script arrives — and 1,596
# pages satisfy it today. A hover menu fails that, fails touch, and fails the
# keyboard without work a two-row bar simply does not need.
#
# The second row is also more useful than a dropdown: it shows the children of
# the area THIS page belongs to, always visible, so the area's contents are
# discovered rather than hunted for.
# =========================================================================

AREAS = (
    ("explore", "Explore", (
        ("/places", "Destinations"),
        ("/tourism/", "Countries"),
        ("/atlas", "The Atlas"),
        ("/stories", "Stories"),
        ("/meet", "Meet Africa"),
        ("/trans-afrique", "Trans Afrique"),
    )),
    ("plan", "Plan", (
        ("/journey", "Journey Planner"),
        ("/journey-fund", "Journey Fund"),
        # A section of the Fund today rather than a page, and linked as one.
        # It becomes its own surface when there are accounts to hold goals,
        # and then this line changes and nothing else does.
        ("/journey-fund#jf-goal", "Travel Goal"),
    )),
)

UTILITY = (
    ("/about-afrinkong", "About Afrinkong"),
)

# The operator's own front door. NOT Afrinkong's navigation: these five pages
# belong to the Kamerun ground operation, and the footer already says so. They
# are listed here so that the one place that decides navigation decides this
# too, rather than leaving five pages to keep their own copy by accident.
OPERATOR_NAV = (
    ("/services", "Circuits"),
    ("/pricing", "Rates &amp; Fees"),
    ("/about", "The Operator"),
    ("/contact", "Enquire"),
)


def _same(a, b):
    """Is `a` the page we are on — not merely a section of it.

    A FRAGMENT LINK IS NOT THE PAGE. The first version of this stripped the
    fragment from both sides, which meant /journey-fund and
    /journey-fund#jf-goal both came back true and the rendered nav carried
    aria-current="page" TWICE on one page. Only one element may, and a screen
    reader given two has been told the reader is in two places.

    So a link that names a fragment is never "the current page": it is a link
    into the current page, which is a different thing and correctly gets no
    marker at all. Travel Goal is a section of the Journey Fund today, and this
    is the line that keeps that honest.
    """
    if "#" in (a or ""):
        return False
    return (a or "").rstrip("/") == (b or "").split("#")[0].rstrip("/")


def shell(here=None, area=None, product=None, product_href=None,
          product_nav=(), operator=False):
    """The masthead every page wears.

    here          the path of the page being rendered, so it can mark itself
                  and so it never offers a link back to itself
    area          "explore" | "plan" | None — which row two shows
    product       an optional product band beneath: Trans Afrique, the Journey
                  Fund, a country name. This is where identity lives, and most
                  of the 1,405 place pages have none because they are Afrinkong
                  plainly
    operator      render the Kamerun operator's shell instead. A different
                  company, a different navigation, deliberately not this one

    Active state is derived, never authored per page: aria-current="page" on
    the exact page, `is-here` on the area, and data-area on the <body> so the
    area row can render without a script.
    """
    if operator:
        links = "".join(
            '<a href="%s"%s>%s</a>' % (
                h, ' aria-current="page"' if _same(h, here) else "", n)
            for h, n in OPERATOR_NAV)
        return (
            '<header class="af-shell af-shell--operator">\n'
            '  <div class="af-shell-in">\n'
            '    <a class="af-shell-mark" href="/cameroon">%s'
            '<b>Kamerun</b><span>Afrinkong in Cameroon</span></a>\n'
            '    <nav class="af-shell-nav" aria-label="Primary">%s</nav>\n'
            '  </div>\n'
            '</header>' % (emblem(34, "af-emblem--mast"), links))

    areas = "".join(
        '<a class="af-shell-area%s" href="%s"%s>%s</a>' % (
            " is-here" if key == area else "",
            children[0][0],
            ' aria-current="true"' if key == area else "",
            label)
        for key, label, children in AREAS)

    util = "".join('<a href="%s"%s>%s</a>' % (
        h, ' aria-current="page"' if _same(h, here) else "", n)
        for h, n in UTILITY)

    # Row two: the children of the current area. A page with no area — the
    # homepage, the trust pages — gets no second row rather than an arbitrary
    # one.
    #
    # AND A PAGE WITH A PRODUCT BAND GETS NO SECOND ROW EITHER, which is the
    # more interesting rule and was forced by a measurement.
    #
    # The first version stacked all three: the platform, then the area's
    # children, then the product's own navigation. 144 pixels of masthead. The
    # browser suite caught what that cost — on /trans-afrique the band's copy is
    # centred in the viewport, and at three of five widths the top of it landed
    # at 124px, underneath the bar. Three rows of navigation is also simply a
    # lot to put above a photograph.
    #
    # Dropping the area row where a product band exists is better design and
    # not merely shorter. On a Kenya place page the useful context is Kenya —
    # overview, portrait, places, what it costs — not the six things Explore
    # contains; and Explore is still one press away in row one. The area row
    # earns its place exactly where there is no product to be more specific
    # than it.
    row2 = ""
    if not product:
        for key, label, children in AREAS:
            if key != area:
                continue
            row2 = ('  <nav class="af-shell-sub" aria-label="%s">%s</nav>\n' % (
                label, "".join(
                    '<a href="%s"%s>%s</a>' % (
                        h, ' aria-current="page"' if _same(h, here) else "", n)
                    for h, n in children)))

    # The phone menu. <details> because it opens with no JavaScript, is
    # keyboard operable by default, and announces its own expanded state —
    # none of which is true of a button plus a class plus aria that somebody
    # has to keep in step.
    menu = "".join(
        '<b>%s</b><span>%s</span>' % (label, "".join(
            '<a href="%s"%s>%s</a>' % (
                h, ' aria-current="page"' if _same(h, here) else "", n)
            for h, n in children))
        for _key, label, children in AREAS)

    return (
        '<header class="af-shell">\n'
        '  <div class="af-shell-in">\n'
        '    <a class="af-shell-mark" href="/">%s<b>Afrinkong</b>'
        '<span>Journeys across Africa</span></a>\n'
        '    <nav class="af-shell-nav" aria-label="Primary">%s</nav>\n'
        '    <div class="af-shell-util">%s</div>\n'
        '    <details class="af-shell-menu">\n'
        '      <summary>Menu</summary>\n'
        '      <div class="af-shell-menu-in">%s%s</div>\n'
        '    </details>\n'
        '  </div>\n'
        '%s'
        '%s'
        '</header>' % (
            emblem(34, "af-emblem--mast"), areas, util, menu,
            "".join('<a href="%s">%s</a>' % (h, n) for h, n in UTILITY),
            row2,
            _product_band(product, product_href, product_nav, here)))


def country_band(name, slug):
    """The four depths, as a product band — and only the ones that exist.

    -> (product, product_href, product_nav) for shell().

    THE HAZARD THIS EXISTS FOR, WHICH I WALKED INTO HAVING WRITTEN IT DOWN.
    /<slug> does not exist for every country: home.NO_PAGE skips Uganda and
    Namibia because both have operator sites of their own, and its comment says
    plainly that nothing on any page may link to them. The first version of the
    shell linked the Overview unconditionally and put 56 dead links onto
    Namibia's place pages — caught by link-checks, which is what it is for.

    Cameroon is in that same tuple for a DIFFERENT reason: its page is
    hand-built rather than generated, so it is perfectly linkable. Treating the
    tuple as one list would silently drop a real page, which is why this asks
    the filesystem "is there a page there" rather than the generator "do you
    skip this one". They are different questions and only one of them is what a
    link needs to be true.

    Written once here so that the four callers — places, tourism, country and
    portrait — cannot each get it right or wrong separately.
    """
    nav = []
    if os.path.exists(os.path.join(ROOT, "%s.html" % slug)):
        nav.append(("/%s" % slug, "Overview"))
    if os.path.exists(os.path.join(ROOT, "portrait", "%s.html" % slug)):
        nav.append(("/portrait/%s" % slug, "Portrait"))
    if os.path.isdir(os.path.join(ROOT, "places", slug)):
        nav.append(("/places#%s" % slug, "Places"))
    if os.path.exists(os.path.join(ROOT, "tourism", "%s.html" % slug)):
        nav.append(("/tourism/%s" % slug, "What it costs"))
    # The band's own title links the overview where there is one, and is plain
    # text where there is not — a heading that goes nowhere beats a 404.
    href = ("/%s" % slug) if nav and nav[0][1] == "Overview" else None
    return name, href, tuple(nav)


def _product_band(name, href, nav, here):
    """Product identity, BENEATH the platform bar rather than instead of it.

    Trans Afrique, the Journey Fund, the journey builder and the atlas are
    products with their own character, and instruction 5 is explicit that they
    keep it. What they must not keep is their own idea of what a masthead is.
    """
    if not name:
        return ""
    links = "".join(
        '<a href="%s"%s>%s</a>' % (
            h, ' aria-current="page"' if _same(h, here) else "", n)
        for h, n in (nav or ()))
    title = ('<a class="af-shell-prod-n" href="%s">%s</a>' % (href, name)
             if href else '<b class="af-shell-prod-n">%s</b>' % name)
    return ('  <div class="af-shell-prod">%s%s</div>\n' % (
        title, ('<nav class="af-shell-prod-nav" aria-label="%s">%s</nav>'
                % (name, links)) if links else ""))


FOOT_LINKS = (
    ("/atlas", "The Atlas"),
    ("/places", "Destinations"),
    ("/stories", "Stories"),
    ("/tourism/", "Countries"),
    ("/journey", "Journey Planner"),
    ("/journey-fund", "Journey Fund"),
    ("/about-afrinkong", "About Afrinkong"),
    ("/enquire", "Begin a journey"),
)


def emblem(px=56, extra=""):
    """The company's mark, written once and used everywhere it belongs.

    The site's identity is typographic — the word AFRINKONG set in the display
    face — and it has been carrying the brand alone on 1,597 pages. The mark
    exists and was reaching the reader only as a favicon and a home-screen
    icon, which is the one place a logo is too small to be a logo.

    THE MARK, NOT THE LOCKUP. images/brand/lockup.png is the mark plus the
    wordmark plus the tagline, and every footer on this site already prints the
    wordmark and the tagline in type. Dropping the lockup beside them would
    print the company's name twice and its tagline twice, in two different
    faces, one of which is a photograph of type. The mark is the half that is
    not already there.

    Decorative, deliberately. It sits next to the word "Afrinkong" in every
    place it is used, so a screen reader that announced it would read the
    company's name twice in a row. alt="" and the wordmark does the naming —
    which is what alt="" is for and not a shortcut around writing alt text.

    Served at 128px for a mark drawn at 24 to 56, so it is at or above 2x
    everywhere it appears without a srcset to keep in step with a layout. One
    file, 26 KB, cached once for the whole site.
    """
    # LAZY EVERYWHERE EXCEPT THE MASTHEAD. The mark in the shell is the first
    # thing above the fold on all 1,597 pages, and loading="lazy" on it asks the
    # browser to defer the one image that is certainly visible — which delays
    # the brand and costs a layout shift for nothing. The footer's copy stays
    # lazy, because it genuinely is below the fold.
    mast = "af-emblem--mast" in (extra or "")
    return ('<img class="af-emblem%s" src="/images/brand/mark-128.png" '
            'width="128" height="128" alt="" loading="%s" decoding="async" '
            'style="--af-emblem:%dpx">'
            % ((" " + extra) if extra else "", "eager" if mast else "lazy", px))


def colophon_foot(here=None):
    """The last thing on a page: where else to go, and who this is.

    FOUR PAGES ENDED AT </main>.

    /atlas, /meet, /journey and /places each stopped dead: no footer, no way
    onward, and — the part that matters — no statement anywhere on the page of
    who the company is. The legal name, the jurisdiction, the registration
    number and the three statements are on fifteen hundred pages of this site
    and were on none of those four, which are between them the pages a visitor
    is on when they are closest to enquiring.

    The company line comes from the same marker every other page uses, so it is
    written once in tourism/company.json and cannot drift from the other
    fifteen hundred. `here` drops the link to the page you are already on
    rather than offering it back.

    Basalt, and not the country tone the place pages use: this footer appears
    on pages that are not about one country, and a fixed ground is a ground the
    dark-surface tokens are already correct for.
    """
    links = "".join(
        '<a href="%s">%s</a>' % (h, esc(n))
        for h, n in FOOT_LINKS
        if not here or h.rstrip("/") != here.rstrip("/"))
    return ('<footer class="af-foot">\n'
            '  <div class="af-foot-in">\n'
            '    <a class="af-foot-brand" href="/">%s<b>Afrinkong</b>'
            '<span>Journeys across Africa</span></a>\n'
            '    <nav class="af-foot-nav" aria-label="Elsewhere on this site">'
            '%s</nav>\n'
            '    <p class="af-foot-co"><!-- gen:company -->\n'
            '    <!-- /gen:company --></p>\n'
            '  </div>\n'
            '</footer>' % (emblem(52), links))


PRELOAD = ('<link rel="preload" href="/fonts/archivo-narrow-latin.woff2" '
           'as="font" type="font/woff2" crossorigin>')


EXPLORE = '<script src="/scripts/explore.js" defer></script>'


def graft_explore(write=False, log=print):
    """Put the universal index on the pages that were built without it.

    The index is the site's one search — Cmd/Ctrl-K, or `/`, or the button —
    and it was on 1,522 pages and missing from seventy-five: all fifty-six
    /tourism country pages, the whole Trans Afrique series, the Journey Fund
    and its two subpages, /wonders, /how-it-works, /enquire and the three legal
    pages. Those are not minor addresses. A reader on /tourism/kenya, looking
    at all twenty-seven of that country's write-ups, had no way to search the
    site from where they stood.

    It needs nothing but the script: explore.js builds its own dialog and the
    styles for it are in afrinkong.css, which every page already loads.

    Grafted rather than added to seven generators, which is the same reasoning
    as the preload above and as `company`: one pass over the output is one
    place to be right. Idempotent — a page that already has it is skipped —
    and keyed on </body>, which every page on this site has.
    """
    done = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            full = os.path.join(base, name)
            with open(full, encoding="utf-8") as fh:
                src = fh.read()
            if "explore.js" in src or "</body>" not in src:
                continue
            done += 1
            if write:
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(src.replace("</body>", EXPLORE + "\n</body>", 1))
    log("%s the universal index onto %d page(s)"
        % ("put" if write else "WOULD put", done))


def graft_preload(write=False, log=print):
    """Put the font preload on the pages whose head is not built by icons().

    Six pages write their own head — the gateway and the five hand-written
    ones — so the line added to icons() reached 1,588 pages and missed the
    homepage, which is the one page every visitor sees first and the one where
    a headline reflowing on arrival is most expensive.

    Keyed on the manifest link rather than on a list of files: any page that
    has been given the icon block has been given it in the same shape, and a
    page that gains one later gets the preload without anybody remembering.
    Idempotent — a page that already names the file is skipped.
    """
    tag = '<link rel="manifest" href="/site.webmanifest">'
    done = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            full = os.path.join(base, name)
            with open(full, encoding="utf-8") as fh:
                src = fh.read()
            if tag not in src or "archivo-narrow-latin.woff2" in src:
                continue
            done += 1
            if write:
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(src.replace(tag, tag + "\n" + PRELOAD, 1))
    log("%s the display face preload onto %d page(s)"
        % ("put" if write else "WOULD put", done))
    return 0


HANDWRITTEN = {
    "about.html": ("/about", "The operator"),
    "contact.html": ("/contact", "Contact"),
    "pricing.html": ("/pricing", "Rates and fees"),
    "services.html": ("/services", "Circuits and experiences"),
    "cameroon.html": ("/cameroon", "Cameroon"),
}


def graft_trails(write=False, log=print):
    """Put the trail on the five pages no generator writes.

    Every page that goes through open_graph gets its trail from the address it
    was built at. Five do not go through it at all — they were written by hand
    before any of the generators existed and are still maintained that way, and
    they are five of the site's most linked pages.

    They each carry the organisation graph as a literal string in the file, so
    this reads that block, adds the trail to it, and writes it back. Where the
    graph already carries a trail nothing matches and nothing is written, which
    is what makes it safe to run on every build.

    NOT 404, AND NOT THE CONTACT SHEET. Both carry noindex: a trail is a thing
    said to a search engine, and neither page is talking to one. Their names in
    a result would be the two names this site least wants in a result.
    """
    import json as _json
    import re as _re
    block = _re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)',
                        _re.S)
    done = 0
    for name, (path, leaf) in sorted(HANDWRITTEN.items()):
        full = os.path.join(ROOT, name)
        try:
            with open(full, encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            log("  %-18s not here" % name)
            continue
        m = block.search(src)
        if not m:
            log("  %-18s carries no graph to add to" % name)
            continue
        doc = _json.loads(m.group(2).replace("<\\/", "</"))
        graph = doc.get("@graph")
        if graph is None or any(g.get("@type") == "BreadcrumbList" for g in graph):
            continue
        graph.append(trail(path, leaf))
        body = _json.dumps(doc, ensure_ascii=False,
                           separators=(",", ":")).replace("</", "<\\/")
        out = src[:m.start()] + m.group(1) + body + m.group(3) + src[m.end():]
        done += 1
        log("  %-18s Home › %s" % (name, leaf))
        if write:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(out)
    log("%s a trail onto %d hand-written page(s)"
        % ("put" if write else "WOULD put", done))
    return 0


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
        # THE ONE FILE WORTH ASKING FOR EARLY.
        #
        # The display face is discovered only when the browser has parsed
        # afrinkong.css, matched a rule, and found a character that needs it —
        # three steps after the HTML arrives, by which time the first paint has
        # already happened in the fallback. Preloading moves the request to the
        # same moment as the stylesheet's, so the swap lands within the first
        # paint rather than visibly after it.
        #
        # The latin subset only. latin-ext carries the accents in a handful of
        # country names and is fetched on demand by the pages that need it;
        # preloading a file most pages never touch is how a preload turns into
        # a cost.
        '<link rel="preload" href="/fonts/archivo-narrow-latin.woff2" '
        'as="font" type="font/woff2" crossorigin>',
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
