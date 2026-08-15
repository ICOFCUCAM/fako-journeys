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

# Function words, which words() used to keep because it only dropped anything
# under three letters. "the" and "and" are four and three, so they survived and
# then scored as subject matches. That is not a subtlety; it is how a photograph
# of fishing boats came to illustrate "The Cloud Forest of Santo Antao" with the
# reason "subject: the", how Russian solyanka came to be Cabo Verdean cachupa on
# "subject: and,bowl", and how a carpet became pottery on "subject: and,woven".
# Every one of those scored above four out of nine and shipped.
STOP = {
    "the", "and", "for", "with", "from", "into", "onto", "over", "under",
    "near", "off", "out", "its", "his", "her", "their", "this", "that",
    "these", "those", "there", "here", "they", "them", "then", "than",
    "was", "were", "are", "been", "being", "has", "have", "had", "not",
    "but", "who", "what", "when", "where", "which", "while", "some", "any",
    "all", "one", "two", "three", "more", "most", "very", "just", "also",
    "you", "your", "our", "can", "will", "would", "about", "above", "after",
    "before", "between", "during", "such", "same", "other", "another",
}


def words(text):
    """Content words only.

    The length filter alone is not a stopword list: it drops "of" and "in" and
    keeps "the", "and", "with", "from" — the four words most likely to appear
    in any caption ever written, and therefore the four least capable of
    telling one photograph from another.
    """
    return {w for w in re.findall(r"[a-z']+", (text or "").lower())
            if len(w) > 2 and w not in STOP}


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


def sameness(candidate, taken):
    """How much this candidate looks like one already used in this country.

    De-duplication by photo id catches the same photograph twice. It does not
    catch the thing that actually ruins a country page: six different
    photographs of the same gorilla, taken by six photographers, filling
    wildlife, safari, forests, eco-tourism, photography and why-visit. Each one
    is a legitimate match for its slot and the page is still a wall of one
    animal.

    So a candidate is also weighed against what the country has already taken.
    `taken` is a list of word-bags, one per resolved slot; the overlap with the
    closest of them is what counts, because matching one earlier slot closely is
    the failure — matching six of them a little is just being about the country.
    """
    text = words(candidate.get("text")) - NOISE
    if not text or not taken:
        return 0.0
    worst = 0.0
    for earlier in taken:
        earlier = earlier - NOISE
        if not earlier:
            continue
        shared = len(text & earlier)
        if not shared:
            continue
        worst = max(worst, shared / float(min(len(text), len(earlier))))
    return worst


# Places that are not in Africa and keep winning African queries, because a
# stock library's Cabo Verde results are full of the Canaries and its Comoros
# results are full of anywhere warm with a boat. Naming one of these is not a
# weak signal to be outweighed by a big image and a lucky word — it is the
# provider telling us, in its own words, that the photograph is of somewhere
# else. Published examples: a canal in Trieste as Comoros, cliffs in Tenerife
# as Cabo Verde, a promenade in Guayaquil as Cote d'Ivoire.
ELSEWHERE = {
    "tenerife", "lanzarote", "fuerteventura", "gomera", "vallehermoso",
    "corralejo", "canary", "canaries", "madeira", "azores", "spain",
    "spanish", "portugal", "portuguese", "italy", "italian", "trieste",
    "greece", "greek", "croatia", "turkey", "turkish", "norway", "iceland",
    "scotland", "ireland", "france", "french", "germany", "switzerland",
    "brazil", "brazilian", "mexico", "peru", "chile", "argentina", "ecuador",
    "guayaquil", "cuba", "jamaica", "bahamas", "maldives", "india", "indian",
    "nepal", "china", "chinese", "japan", "japanese", "thailand", "vietnam",
    "indonesia", "bali", "philippines", "malaysia", "australia", "zealand",
    "florida", "california", "hawaii", "texas", "russia", "russian",
    "solyanka", "ukraine", "poland", "dubai", "emirates", "qatar",
}


def elsewhere(candidate, country):
    """The place this photograph says it is, when that is not this country.

    A country of ours named in the text is fine and common — a photo can be
    taken on a border, or a caption can list two. What is never fine is a
    caption naming somewhere the journey does not go.
    """
    text = words(candidate.get("text"))
    mine = words(country.name) | words(country.adjective)
    hits = (text & ELSEWHERE) - mine
    return sorted(hits)


def score(candidate, country, category, entry, role, taken=None):
    """-> (score, reasons). Higher is better; below MIN_SCORE is a rejection."""
    text = words(candidate.get("text"))

    # Checked before anything else and returned as a hard rejection rather than
    # a penalty. A -2.5 would have been outvoted by a 6000px image and two
    # lucky subject words, which is how these shipped in the first place.
    away = elsewhere(candidate, country)
    if away:
        return -99.0, ["the photograph says it is in %s" % ", ".join(away[:2])]

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

    # Variety, weighed after relevance and never instead of it. A photograph
    # that is genuinely the best match for its slot survives this; a sixth
    # near-identical one does not.
    same = sameness(candidate, taken)
    if same > 0.5:
        total -= (same - 0.5) * 4.0
        reasons.append("looks like %d%% of a slot already filled here"
                       % round(same * 100))

    return total, reasons


MIN_SCORE = 1.0            # below this, leave the slot unresolved
CLEARLY_BETTER = 2.0       # margin a fallback must beat the primary by

# The highest score any candidate can reach: every positive term at its cap and
# no penalty. 1.5 for naming the country, 4.0 for the subject, 3.0 for the
# category, 1.0 for being over 4000px wide. Nothing else adds.
#
# It exists so the resolver can know when asking another provider is provably
# pointless. A fallback only displaces the primary at CLEARLY_BETTER above it,
# so once the primary is above CEILING - CLEARLY_BETTER no possible answer from
# anywhere else can win, and the request would be spent to learn nothing. On a
# Demo key allowing fifty requests an hour that is not a rounding error.
CEILING = 1.5 + 4.0 + 3.0 + 1.0
UNBEATABLE = CEILING - CLEARLY_BETTER


def rank(candidates, country, category, entry, role, seen=None, taken=None):
    """Best first, already filtered for duplicates, sameness and hopeless crops."""
    seen = seen or set()
    scored = []
    for c in candidates:
        key = "%s:%s" % (c.get("provider"), c.get("photoId"))
        if key in seen:
            continue
        s, why = score(c, country, category, entry, role, taken)
        if s < MIN_SCORE:
            continue
        scored.append((s, why, c))
    scored.sort(key=lambda t: -t[0])
    return scored
