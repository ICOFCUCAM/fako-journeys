"""Compile one dataset entry into one generation instruction.

The country datasets already say what each of the 27 slots is a picture of —
`subject` was written slot by slot, for a specific place, and the resolver has
been searching stock libraries with it for weeks. A generator needs the same
sentence plus everything the search providers got for free and a model does not:

    what it is         entry.subject, in the country                dataset
    what kind of       what makes this category a good photograph   style.json
    where it sits      the focal point, as a composition note       dataset
    what shape         the delivered aspect ratio, so nothing       categories.json
                       important is composed into the part that
                       gets cropped away
    how it looks       the house photographic style                 style.json
    what it must not   no text, no collage, no travel-poster        style.json
    contain            layout

That last one is not boilerplate. The two band pictures on the home page arrived
as finished posters with their own headlines baked in, and the whole page had to
be rebuilt around them. A generator will produce exactly that unless told not to.

Deterministic: the same entry compiles to the same prompt every time, so a run is
reproducible and reviewable, and `build.py prompts` shows you every instruction
before you spend a cent generating from it.
"""

import json
import os

from .model import TOURISM

STYLE_FILE = os.path.join(TOURISM, "style.json")


def load_style(path=STYLE_FILE):
    with open(path) as f:
        return json.load(f)


def opening(subject, where):
    """The first two lines of every instruction.

    Labelled fields rather than a flowing sentence, because the subjects are
    written as standalone alt text and start with a capital: folded into
    "A photograph of ..." they read as a typo, and lower-casing the first word
    to fix that turns "Mount Cameroon" into "mount Cameroon". Labelling the
    field sidesteps the whole problem and is a clearer instruction besides.
    """
    return ["A documentary travel photograph.",
            "Subject: %s." % subject,
            "Location: %s." % where]


def _bucket(value, table):
    """First threshold the value falls under. Percentages -> a phrase."""
    for limit, phrase in table:
        if value < limit:
            return phrase
    return table[-1][1]


def composition(focal, style):
    table = style.get("composition") or {}
    parts = [
        _bucket(focal.get("x", 50), table.get("x") or []),
        _bucket(focal.get("y", 50), table.get("y") or []),
    ]
    return " ".join(p for p in parts if p)


def aspect_note(role):
    """Tell the model the delivered shape without asking it for that shape.

    The generator only offers three sizes, and the site delivers six ratios. So
    the frame is generated at the nearest available shape and the note asks for
    margin at the edges — a subject composed tight to the top of a 3:2 frame
    loses its head when the page crops it to 1:1.
    """
    aw, ah = role["aspect"]
    note = ("The frame will be cropped to %d:%d for use, so keep the subject clear "
            "of the edges and leave room around it." % (aw, ah))
    # And what that crop must not take with it. The same sentence is printed on
    # the review sheet beside every candidate, so the instruction the picture
    # was made to and the instruction it is judged against are one sentence
    # rather than two people's memory of one.
    focus = (role.get("focus") or "").strip()
    if focus:
        note += " What the crop must keep: %s." % focus.rstrip(".")
    return note


def size_for(role, style):
    sizes = (style.get("model") or {}).get("sizes") or {}
    aw, ah = role["aspect"]
    if ah > aw:
        return sizes.get("portrait", "1024x1536")
    if aw == ah:
        return sizes.get("square", "1024x1024")
    return sizes.get("landscape", "1536x1024")


def build(country, category, entry, role, style=None):
    """-> the full instruction string for one slot."""
    style = style or load_style()
    direction = (style.get("direction") or {}).get(category["id"], "")

    subject = (entry.subject or "").strip().rstrip(".")
    where = country.name
    if country.region and country.region.lower() not in where.lower():
        where = "%s, %s" % (country.name, country.region)

    sentences = opening(
        subject or category["title"].split("/")[0].strip().lower(), where)
    if direction:
        sentences.append(direction)

    comp = composition(entry.focal, style)
    if comp:
        sentences.append("Compose it %s." % comp)
    sentences.append(aspect_note(role))

    sentences.extend(style.get("look") or [])
    # Only spend the words on people when the picture is likely to contain any.
    if _about_people(category, subject):
        sentences.extend(style.get("people") or [])

    avoid = style.get("avoid") or []
    if avoid:
        sentences.append("Do not include " + "; ".join(avoid) + ".")

    return " ".join(s.strip() for s in sentences if s and s.strip())


def for_placement(country, placement, taxonomy, entry=None, style=None):
    """The instruction for one slot on one page.

    Differs from build() in what it takes as the subject. A category prompt
    describes the category's subject for that country; a placement prompt
    describes *this slot* — the sentence already written about the picture that
    belongs in it — and is cut for the shape that slot's own stylesheet imposes,
    which is frequently not the category's canonical shape. The same waterfall
    is a 16:9 band on one page and a 4:5 column on another, and a 4:5 crop of a
    frame composed for 16:9 is a picture of the middle third of a waterfall.
    """
    style = style or load_style()
    cat = taxonomy.by_id.get(placement.get("category") or "")
    direction = (style.get("direction") or {}).get((cat or {}).get("id", ""), "")

    where = country.name
    if country.region and country.region.lower() not in where.lower():
        where = "%s, %s" % (country.name, country.region)

    subject = (placement.get("instruction") or "").strip().rstrip(".")
    sentences = opening(subject, where)
    if direction:
        sentences.append(direction)

    focal = (entry.focal if entry else None) or {"x": 50, "y": 50}
    comp = composition(focal, style)
    if comp:
        sentences.append("Compose it %s." % comp)
    sentences.append(aspect_note({"aspect": placement["aspect"],
                                  "focus": placement.get("focus", "")}))

    sentences.extend(style.get("look") or [])
    if _about_people(cat or {"id": ""}, subject):
        sentences.extend(style.get("people") or [])
    avoid = style.get("avoid") or []
    if avoid:
        sentences.append("Do not include " + "; ".join(avoid) + ".")
    return " ".join(s.strip() for s in sentences if s and s.strip())


def size_for_aspect(aspect, style):
    aw, ah = aspect
    sizes = (style.get("model") or {}).get("sizes") or {}
    if ah > aw:
        return sizes.get("portrait", "1024x1536")
    if aw == ah:
        return sizes.get("square", "1024x1024")
    return sizes.get("landscape", "1536x1024")


PEOPLE_CATEGORIES = {
    "culture", "traditional-people", "festivals", "crafts", "local-life",
    "family-community", "food", "adventure", "safari", "eco-tourism", "cities",
}
PEOPLE_WORDS = ("guide", "porter", "villager", "trekker", "walker", "fisher",
                "trader", "woman", "women", "man", "men", "child", "children",
                "family", "crew", "dancer", "drummer", "weaver", "carver",
                "people", "person", "ranger", "driver", "cook")


def _about_people(category, subject):
    if category["id"] in PEOPLE_CATEGORIES:
        return True
    low = (subject or "").lower()
    return any(w in low for w in PEOPLE_WORDS)


def for_country(country, taxonomy, style=None):
    """[(category, entry, prompt)] for every enabled slot with content."""
    style = style or load_style()
    out = []
    for cat in taxonomy.enabled:
        entry = country.entry(cat["id"])
        if not entry:
            continue
        role = taxonomy.role(cat["id"])
        out.append((cat, entry, build(country, cat, entry, role, style)))
    return out
