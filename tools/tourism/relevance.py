"""Score a candidate against the slot it would fill.

The naive resolver took the first result that was big enough. That is how a
generic savanna sunset ends up under "Uganda / Wildlife": it came back for the
query, it was 4000px wide, so it won.

Search rank alone is not relevance. Every candidate carries text the provider
wrote about it — Unsplash's alt_description, description, tags and location;
Pexels' alt — and that text is the only evidence available about what the
photograph actually shows. This module reads it, and weighs it against the
mechanical facts (orientation, resolution, how much of the frame the intended
crop throws away).

A candidate that matches nothing but the country name scores near zero, which
is the point: containing the word "Uganda" is not a reason to publish a picture
under "gorilla trekking".
"""

import re

from . import queries

# Words a tourism photo's description will contain no matter what it shows.
NOISE = {
    "travel", "trip", "tourism", "vacation", "holiday", "beautiful", "amazing",
    "background", "wallpaper", "view", "photo", "image", "picture", "shot",
    "africa", "african", "nature", "outdoor", "outdoors", "landscape",
}


def words(text):
    return {w for w in re.findall(r"[a-z']+", (text or "").lower()) if len(w) > 2}


def subject_terms(entry, category):
    """What this slot is actually about."""
    terms = set(queries.keywords(entry.subject, limit=10))
    terms |= words(entry.caption)
    terms -= NOISE
    hint = {w.lower() for w in (category.get("queryHint") or "").split()}
    return terms, hint - NOISE


def crop_waste(candidate, role):
    """Fraction of the original thrown away by the intended crop. 0 is perfect."""
    have = candidate.aspect
    if not have:
        return 1.0
    aw, ah = role["aspect"]
    want = aw / float(ah)
    if want >= have:
        kept = have / want       # cropping top and bottom
    else:
        kept = want / have       # cropping the sides
    return 1.0 - max(0.0, min(1.0, kept))


def score(candidate, country, category, entry, role):
    """-> (score, reasons). Higher is better; below MIN_SCORE is a rejection."""
    text = words(candidate.get("text"))
    terms, hint = subject_terms(entry, category)
    reasons = []
    total = 0.0

    country_words = words(country.name) | words(country.adjective)
    if text & country_words:
        total += 1.5
        reasons.append("names the country")

    subject_hits = text & terms
    if subject_hits:
        total += min(4.0, 2.0 * len(subject_hits))
        reasons.append("subject: " + ",".join(sorted(subject_hits)[:3]))

    hint_hits = text & hint
    if hint_hits:
        total += min(3.0, 1.5 * len(hint_hits))
        reasons.append("category: " + ",".join(sorted(hint_hits)[:2]))

    # A description that says something, and what it says is not this slot: that
    # is the exact failure this module exists to prevent — a generic country
    # photo winning because the country name matched.
    if candidate.get("text") and not subject_hits and not hint_hits:
        total -= 2.5
        reasons.append("described, but not as this subject")

    w = candidate.get("width") or 0
    if w >= 4000:
        total += 1.0
    elif w >= 2400:
        total += 0.5
    elif w < 1600:
        total -= 2.0
        reasons.append("under 1600px wide")

    waste = crop_waste(candidate, role)
    total -= waste * 3.0
    if waste > 0.45:
        reasons.append("crop discards %d%% of the frame" % round(waste * 100))

    if not candidate.get("text"):
        # No description at all is not evidence against the photo, only an
        # absence of evidence for it. Neither reward nor punish.
        reasons.append("no description to judge")

    return total, reasons


MIN_SCORE = 1.0            # below this, leave the slot unresolved
CLEARLY_BETTER = 2.0       # margin a fallback must beat the primary by


def rank(candidates, country, category, entry, role, seen=None):
    """Best first, already filtered for duplicates and hopeless crops."""
    seen = seen or set()
    scored = []
    for c in candidates:
        key = "%s:%s" % (c.get("provider"), c.get("photoId"))
        if key in seen:
            continue
        s, why = score(c, country, category, entry, role)
        if s < MIN_SCORE:
            continue
        scored.append((s, why, c))
    scored.sort(key=lambda t: -t[0])
    return scored
