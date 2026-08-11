"""Deterministic search queries, broadest-last.

The first version of this module handed Unsplash the whole subject phrase:

    Cameroon layered green highland ridges bamenda highlands landscape nature

Nine words. Unsplash's search is keyword matching over tags and titles, not
semantic retrieval, so a query that specific matches nothing at all — 22 of
Cameroon's 27 slots came back empty on the first real run, while the handful
that happened to be short enough succeeded. Precision was the bug.

So each slot gets a *ladder* of queries instead, tried in order until one
returns something usable:

    Cameroon Mount Cameroon        proper nouns — the place itself
    Cameroon trekkers slopes       the subject's own content words
    Cameroon mountain              the category, in this country
    Cameroon peak                  the category's other word

Same country and category always produce the same ladder, so a resolve run is
reproducible and reviewable. Country identity is in every rung — searching for
"beautiful africa" is how the same acacia sunset ends up on seven country pages.
"""

import re

STOP = {
    "a", "an", "the", "and", "of", "in", "on", "at", "with", "under", "over", "into",
    "from", "for", "its", "their", "his", "her", "it", "to", "by", "as", "that",
    "where", "who", "which", "is", "are", "was", "were", "has", "have", "been",
    "above", "below", "beside", "between", "through", "across", "along", "off",
}

# Words that describe the picture rather than the thing in it. Useful to a human
# reading the dataset, noise in an image search.
CAMERA = {
    "photograph", "photo", "shot", "frame", "close", "wide", "lens", "light",
    "morning", "evening", "dawn", "dusk", "afternoon", "seen", "first", "own",
}


def keywords(subject, limit=6):
    """Content words from the subject, in order, minus filler."""
    out = []
    for w in re.findall(r"[a-z']+", (subject or "").lower()):
        if w in STOP or w in CAMERA or len(w) < 3:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def proper_nouns(subject, country=None):
    """Capitalised runs in the subject — the named places, which is what
    Unsplash actually has tagged. 'the Lobe waterfalls near Kribi' -> ['Lobe',
    'Kribi']."""
    found = []
    for run in re.findall(r"\b([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)", subject or ""):
        for part in [run] if len(run.split()) <= 3 else [run.split()[0]]:
            if country and part.lower() == country.lower():
                continue
            if part not in found:
                found.append(part)
    return found


def ladder(country, category, entry):
    """[(query, tier)] for one slot, most specific first.

    tier is "subject" while the query still describes the thing the entry claims
    to show, and "category" once it has broadened to "Cameroon waterfall". That
    distinction matters downstream: a photo found on a category rung is a
    waterfall in Cameroon, not necessarily *the Lobe falls*, so it must not
    inherit alt text that says otherwise.

    There is deliberately no bare-country rung. "Cameroon" alone always returns
    something, and something is not the same as the right thing — a slot with no
    honest match stays unresolved and keeps its illustration.
    """
    hint = (category.get("queryHint") or "").split()
    subject = entry.subject or ""
    rungs = []

    named = proper_nouns(subject, country.name)
    if named:
        rungs.append(("%s %s" % (country.name, " ".join(named[:2])), "subject"))

    words = keywords(subject)
    if words:
        rungs.append(("%s %s" % (country.name, " ".join(words[:3])), "subject"))
        rungs.append(("%s %s" % (country.name, " ".join(words[:2])), "subject"))

    for h in hint[:2]:
        rungs.append(("%s %s" % (country.name, h), "category"))

    out, seen = [], set()
    for q, tier in rungs:
        q = " ".join(q.split())
        if q and q not in seen:
            seen.add(q)
            out.append((q, tier))
    return out


def build(country, category, entry):
    """The first rung — what a slot searches for when everything goes well."""
    rungs = ladder(country, category, entry)
    return rungs[0][0] if rungs else country.name


def generic_alt(country, category):
    """Honest alt text for a photo matched on a category rung."""
    title = category["title"].split("/")[0].split("&")[0].strip()
    return "%s in %s" % (title, country.name)


def orientation(role_name):
    return "portrait" if role_name == "portrait" else "landscape"
