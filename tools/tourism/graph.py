"""The story graph: what this dataset actually names, and where.

    python3 tools/tourism/build.py graph

Five hundred and ninety-four write-ups have been sitting here naming things —
Bwindi, Lalibela, the Rwenzori, Owino, Sauti za Busara, Kente — and until now
those names were only ever prose. Nothing could answer "where else does this
site mention the Rwenzori", because nothing had ever looked.

This looks. It reads every caption, description and photographic subject in
tourism/countries/*.json, pulls out the proper names, and records which write-up
each one came from. That is the whole of the claim it makes: *this name appears
in these write-ups*. It does not decide what a name is, where it is, how big it
is or whether it is worth visiting — all of which would be inventing geography,
and all of which the atlas and links.json already do properly from boundary data.

Extraction rather than assertion is the point. A hand-written index of African
place names would be a new set of facts to be wrong about; an index built by
reading the site's own sentences cannot contain anything the site does not
already say. If a name is wrong here, it is wrong in the country file, which is
the one place a correction belongs.

What comes out:

    data/graph.json   countries, themes, names, and the edges between them

It powers two things that could not exist before it: search that understands
"food in Cameroon" and "heritage in Ethiopia" as entities rather than as
substrings, and non-linear discovery — a name found in one country's story
leading to every other write-up that mentions it.
"""

import json
import os
import re

from .model import (ROOT, load_countries, load_operators, load_regions,
                    load_strands, load_taxonomy, region_of)

OUT = os.path.join(ROOT, "data", "graph.json")
LENSES = os.path.join(ROOT, "tourism", "lenses.json")

# Words that begin a sentence, or that are capitalised for reasons that have
# nothing to do with being a place. Without this list "The", "Where" and "Half"
# become the most-cited landmarks in Africa.
STOP = set("""
a an and the of in on at to for from by with without into onto over under near
this that these those it its is are was were be been being has have had do does
did not no nor but or so yet if then than as up down out off again once here
there when where why how all any both each few more most other some such only
own same too very can will just should now
he she they them their his her our your you we us i
one two three four five six seven eight nine ten eleven twelve
half almost about between across around through during before after until since
every everything nothing anything something someone somebody nobody everyone
what which who whom whose while because although though unless whether
""".split())

# Capitalised words that are real English words doing ordinary work in these
# sentences, or that name a thing rather than a place.
NOT_A_NAME = set("""
january february march april may june july august september october november
december monday tuesday wednesday thursday friday saturday sunday
africa african europe european asia asian america american atlantic indian
pacific mediterranean sahara sahel unesco unesco-listed world heritage site
national park
amphitheatre boulders cape corniche delta hole kings man moon mountains
plateau rift valley wall dive surf hike sail walk swim climb ride
""".split())

# A name may run through these without ending: "Mountains of the Moon",
# "Valley of the Kings", "Cape of Good Hope".
JOINERS = {"of", "the", "and", "de", "del", "da", "du", "des", "la", "le", "el",
           "al", "na", "za", "ya", "van", "op", "aan"}

WORD = r"[A-Z][\w'’-]*"
CANDIDATE = re.compile(
    r"\b(%s(?:\s+(?:%s)\s+%s|\s+%s)*)" % (WORD, "|".join(JOINERS), WORD, WORD))
SENTENCE_END = re.compile(r"[.!?—]\s+|^")


def load_lenses(path=LENSES):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (IOError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("$")}


def openers(text):
    """The character offsets a sentence starts at.

    A capitalised word at one of these is capitalised because of where it is,
    not because of what it is, which is the difference between "Half the world's
    gorillas" and "Bwindi". Names that only ever appear at a sentence start are
    dropped later; names that appear mid-sentence anywhere are kept everywhere.
    """
    spots = {0}
    for m in re.finditer(r"[.!?—:;]\s+", text):
        spots.add(m.end())
    return spots


def names_in(text):
    """-> [(name, started_the_sentence)] for one piece of prose.

    Only ever called on sentence-case prose. Captions are Title Case, where
    every word carries a capital and this would read "Rafting, Canoe the
    Zambezi" as a landmark — the capitals in a headline mean nothing about what
    is a name, so headlines are not read.
    """
    if not text:
        return []
    spots = openers(text)
    found = []
    for m in CANDIDATE.finditer(text):
        parts = m.group(1).strip().split()
        # A capitalised joiner is a new sentence's "The", not part of a name:
        # cut there rather than swallowing what follows it.
        for i, word in enumerate(parts[1:], 1):
            if word.lower() in JOINERS and word[:1].isupper():
                parts = parts[:i]
                break
        # A trailing joiner belongs to the sentence, not to the name:
        # "the Rwenzori and" is "the Rwenzori".
        while parts and parts[-1].lower() in JOINERS:
            parts.pop()
        while parts and parts[0].lower() in JOINERS:
            parts.pop(0)
        if not parts:
            continue
        name = " ".join(parts).rstrip(",;:")
        low = name.lower()
        if low in STOP or low in NOT_A_NAME or len(name) < 3:
            continue
        found.append((name, m.start() in spots))
    return found


def _canon(name):
    """"Africa's" and "Africa" are the same name wearing a possessive."""
    return re.sub(r"[’']s$", "", re.sub(r"\s+", " ", name).strip()).strip("'’")


def harvest(countries, taxonomy):
    """Every proper name in the dataset, with the write-ups it came from.

    Two passes. The first collects candidates and remembers whether each one was
    ever seen away from the start of a sentence; the second keeps only those,
    because a word that has only ever been seen with a capital at the front of a
    sentence has not been shown to be a name at all.
    """
    titles = {c["id"]: c["title"] for c in taxonomy.categories}
    raw, mid = {}, set()
    for country in countries:
        if not country.published:
            continue
        for entry in country.entries:
            for source, blob in (("text", entry.description or ""),
                                 ("subject", entry.subject or "")):
                for name, at_start in names_in(blob):
                    key = _canon(name)
                    if not at_start:
                        mid.add(key.lower())
                    slot = raw.setdefault(key, [])
                    slot.append((country.slug, entry.category, source))

    names = {}
    for key, hits in raw.items():
        low = key.lower()
        if low not in mid:
            continue                      # only ever a sentence opener
        if low in NOT_A_NAME or low in STOP:
            continue
        seen, where, kinds = set(), [], {}
        for slug, category, source in hits:
            kinds[category] = kinds.get(category, 0) + 1
            if (slug, category) in seen:
                continue
            seen.add((slug, category))
            where.append({"c": slug, "e": category,
                          "t": titles.get(category, category), "s": source})
        countries_named = []
        for slug, _c, _s in hits:
            if slug not in countries_named:
                countries_named.append(slug)
        names[key] = {
            "in": countries_named,
            "at": where,
            "n": len(where),
            "kinds": [k for k, _n in sorted(kinds.items(), key=lambda x: -x[1])][:3],
        }
    return names


def prune(names, countries):
    """Drop the names that are the dataset talking about itself.

    Country names, the adjectives made from them and the region names are all
    proper nouns and all useless as an index: every write-up in Uganda is about
    Uganda, so "Uganda appears in twenty-seven write-ups" is a fact about the
    filing system rather than about the country.
    """
    own = set()
    for c in countries:
        own.add(c.name.lower())
        own.add((c.adjective or "").lower())
        own.add(c.region.lower())
        for word in c.name.lower().split():
            if len(word) > 3:
                own.add(word)
    return {k: v for k, v in names.items()
            if k.lower() not in own and v["n"] >= 1}


def themes(taxonomy):
    """The words a visitor would actually type, mapped to the write-ups they mean.

    Lenses, strands and the categories themselves, in one vocabulary, because a
    visitor typing "food" does not know whether this site files food under a
    lens, a strand or a category — and here it is all three.
    """
    out = {}
    for key, lens in load_lenses().items():
        out[key] = {"title": lens.get("title") or key, "kind": "lens",
                    "categories": lens.get("categories") or [],
                    "words": lens.get("words") or [key],
                    "url": "/atlas#/%s" % key}
    for key, strand in load_strands().items():
        row = out.setdefault(key, {"title": strand.get("title") or key,
                                   "kind": "strand", "categories": [], "words": [],
                                   "url": "/meet#/%s" % key})
        row["categories"] = sorted(set(row["categories"])
                                   | set(strand.get("categories") or []))
        row["words"] = sorted(set(row["words"]) | {key})
        row["asks"] = strand.get("asks") or ""
        if row["kind"] == "lens":
            row["kind"] = "both"
    for cat in taxonomy.categories:
        key = cat["id"]
        words = [w for w in re.split(r"[^a-z]+", cat["title"].lower()) if len(w) > 2]
        row = out.setdefault(key, {"title": cat["title"], "kind": "category",
                                   "categories": [key], "words": [],
                                   "url": "/places"})
        row["words"] = sorted(set(row["words"]) | set(words) | {key})
        if key not in row["categories"]:
            row["categories"] = sorted(set(row["categories"]) | {key})
    return out


def _addresses(slug):
    """{category: {title, url}} for one country, read from the atlas payload.

    Read rather than derived: atlas.py already computed every one of these
    addresses and places.py already wrote a page at each, so computing them a
    third time here would be a third chance to disagree with the other two.
    """
    path = os.path.join(ROOT, "data", "atlas", "%s.json" % slug)
    try:
        with open(path) as fh:
            pack = json.load(fh)
    except (IOError, ValueError):
        return {}
    return {p["id"]: {"t": p["title"], "u": p.get("url") or ""}
            for p in pack.get("places") or []}


def run(countries, taxonomy, log=print):
    live = [c for c in countries if c.published]
    regions = load_regions()
    ops = load_operators()

    found = prune(harvest(live, taxonomy), live)
    graph = {
        "countries": {},
        "themes": themes(taxonomy),
        "names": dict(sorted(found.items())),
    }
    for c in live:
        key, _reg = region_of(c, regions)
        op = ops.get(c.operator_key)
        graph["countries"][c.slug] = {
            "name": c.name, "adjective": c.adjective, "region": c.region,
            "regionKey": key, "tagline": c.tagline, "months": c.months,
            "calls": c.calls, "url": c.url,
            "operator": op.name if op else None,
            # Where each of this country's write-ups lives. Without it a name
            # found in the index would be a fact with nowhere to go: search
            # would be able to say "the Rwenzori are mentioned in four write-ups"
            # and then not be able to open one of them.
            "places": _addresses(c.slug),
        }

    folder = os.path.dirname(OUT)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(OUT, "w") as fh:
        json.dump(graph, fh, separators=(",", ":"), sort_keys=True)
    shared = sum(1 for v in found.values() if len(v["in"]) > 1)
    log("graph: data/graph.json (%.1f KB), %d names read out of the dataset, "
        "%d of them in more than one country, %d themes"
        % (os.path.getsize(OUT) / 1024.0, len(found), shared, len(graph["themes"])))
    return len(found)
