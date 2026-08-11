"""Deterministic search queries.

Same country + same category always produces the same query, so a resolve run is
reproducible and reviewable. Country identity is always in the query — a search
for "beautiful africa" is how you end up with the same acacia sunset on seven
different country pages.

Precedence: the country entry's own subject wins, the category hint fills in, and
the country name anchors it geographically.
"""

import re

STOP = {
    "a", "an", "the", "and", "of", "in", "on", "at", "with", "under", "over", "into",
    "from", "for", "its", "their", "his", "her", "it", "to", "by", "as", "that",
    "where", "who", "which", "is", "are", "was", "were", "has", "have", "been",
}

# Words that describe the picture rather than the thing in it. They help a human
# read the dataset but only add noise to an image search.
CAMERA = {
    "photograph", "photo", "shot", "frame", "close", "wide", "lens", "light",
    "morning", "evening", "dawn", "dusk", "afternoon",
}


def keywords(subject, limit=6):
    words = re.findall(r"[a-z']+", (subject or "").lower())
    out = []
    for w in words:
        if w in STOP or w in CAMERA or len(w) < 3:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def build(country, category, entry):
    """The query string handed to the Unsplash search endpoint."""
    parts = [country.name]
    parts += keywords(entry.subject)
    hint = (category.get("queryHint") or "").split()
    for h in hint:
        if h not in parts:
            parts.append(h)
    return " ".join(parts)


def orientation(role_name):
    return "portrait" if role_name == "portrait" else "landscape"
