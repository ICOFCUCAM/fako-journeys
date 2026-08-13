"""Data model for the tourism image system.

The source of truth is JSON on disk, not code:

    tourism/categories.json        the 27 categories, their order, and delivery presets
    tourism/countries/<slug>.json  one file per country, 27 entries each

Adding a country is one file. Nothing in this module, in the renderer, or in any
page needs to change — the engine walks tourism/countries/ and processes whatever
it finds. That is the whole point of the layout.
"""

import collections
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TOURISM = os.path.join(ROOT, "tourism")
COUNTRY_DIR = os.path.join(TOURISM, "countries")
CATEGORY_FILE = os.path.join(TOURISM, "categories.json")

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class DataError(Exception):
    """A dataset problem worth stopping for — malformed JSON, unknown category id."""


# ---- taxonomy ------------------------------------------------------------------


class Taxonomy:
    def __init__(self, raw):
        self.version = raw.get("version", 1)
        self.roles = {k: v for k, v in raw["roles"].items() if not k.startswith("$")}
        cats = sorted(raw["categories"], key=lambda c: c["order"])
        self.categories = [c for c in cats]
        self.by_id = {c["id"]: c for c in self.categories}
        for c in self.categories:
            if c["role"] not in self.roles:
                raise DataError("category %r uses unknown role %r" % (c["id"], c["role"]))

    @property
    def enabled(self):
        return [c for c in self.categories if c.get("enabled", True)]

    @property
    def ids(self):
        return [c["id"] for c in self.categories]

    def role(self, category_id):
        return self.roles[self.by_id[category_id]["role"]]


def load_taxonomy(path=CATEGORY_FILE):
    with open(path) as f:
        return Taxonomy(json.load(f))


# ---- countries -----------------------------------------------------------------


class Entry:
    """One country x category assignment, before delivery details are computed."""

    __slots__ = ("category", "caption", "description", "subject", "focal", "image", "local", "raw")

    def __init__(self, raw):
        self.raw = raw
        self.category = raw.get("category")
        self.caption = raw.get("caption")
        self.description = raw.get("description")
        self.subject = raw.get("subject")
        focal = raw.get("focal") or [50, 50]
        self.focal = {"x": focal[0], "y": focal[1]}
        # image is populated by the Unsplash resolver and never hand-written:
        # a URL nobody has fetched is a URL nobody can trust.
        # Populated from tourism/cache/unsplash.json by attach_cache(). Content
        # files never carry image URLs: an editor writing copy must not be able
        # to hand-write an imageUrl that nobody fetched.
        self.image = None
        self.local = raw.get("local")


class Operator(object):
    """One of our own companies.

    An operator was a string on three countries — the name, repeated wherever it
    was needed and carrying nothing else. It is the differentiator the whole
    platform rests on ("run by people who live there"), so it is an entity: a
    name, a base, a year, a sentence about what it actually runs, and where it
    lives. A country points at one by key.
    """

    def __init__(self, key, raw):
        self.key = key
        self.name = raw.get("name") or key
        self.country = raw.get("country") or ""
        self.base = raw.get("base") or ""
        self.since = raw.get("since") or ""
        self.line = raw.get("line") or ""
        self.url = raw.get("url") or ""


def load_operators(path=None):
    path = path or os.path.join(ROOT, "tourism", "operators.json")
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (IOError, ValueError):
        return {}
    return dict((k, Operator(k, v)) for k, v in raw.items())


OPERATORS = None


def operator(key):
    """-> Operator or None. Loaded once; the file is three entries."""
    global OPERATORS
    if OPERATORS is None:
        OPERATORS = load_operators()
    return OPERATORS.get(key) if key else None


class Region(object):
    """One of five. A region is the middle rung of the atlas — Africa, region,
    country — and it owns the editorial line and the terrain words that make it
    feel physically different from the one next to it."""

    def __init__(self, key, raw):
        self.key = key
        self.name = raw.get("name") or key
        self.line = raw.get("line") or ""
        self.terrain = list(raw.get("terrain") or [])
        self.includes = list(raw.get("includes") or [])
        # The ground a country from this region is drawn on when it has no
        # photograph yet. Five values of the same ink, not five brand colours.
        self.tone = raw.get("tone") or ""


def load_regions(path=None):
    path = path or os.path.join(ROOT, "tourism", "regions.json")
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (IOError, ValueError):
        return {}
    return collections.OrderedDict((k, Region(k, v)) for k, v in raw.items()
                                   if not k.startswith("$"))


def region_of(country, regions=None):
    """Which of the five a country files itself under. One definition, because
    four modules were each deriving it from `includes` on their own."""
    regions = regions if regions is not None else load_regions()
    for key, reg in regions.items():
        if country.region in reg.includes:
            return key, reg
    return "", None


def load_picks(path=None):
    """What we would actually say if somebody told us what they wanted.

    A tourism site answers "I want wildlife" with six cards. This answers with a
    country and a reason, in the voice of somebody who has been — including the
    thing not to do first. It is editorial, so it is written down rather than
    computed; the rest of the platform is comparison and this is opinion, and
    the difference is the point.
    """
    path = path or os.path.join(ROOT, "tourism", "picks.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {}


class Person(object):
    """Somebody real, who agreed to be here.

    The class exists so that the difference between a real guide and a
    convincing one is a file on disk rather than a judgement in a template.
    Every field is optional except a name and a role, and anything missing is
    left out of the page rather than filled in with something plausible — a
    fabricated guide is worse than no guide at all, because a visitor cannot
    tell the difference until they arrive.
    """

    def __init__(self, key, raw):
        self.key = key
        self.name = raw.get("name") or ""
        self.role = raw.get("role") or ""
        self.operator_key = raw.get("operator") or ""
        self.country = raw.get("country") or ""
        self.base = raw.get("base") or ""
        self.languages = list(raw.get("languages") or [])
        self.since = raw.get("since") or ""
        self.speciality = raw.get("speciality") or ""
        self.line = raw.get("line") or ""
        self.photo = raw.get("photo") or ""
        self.photo_alt = raw.get("photo_alt") or ""
        self.verified = raw.get("verified") or ""

    @property
    def usable(self):
        """A person with no name and no role is a placeholder, not a person."""
        return bool(self.name and self.role)


def load_people(path=None):
    """-> {slug: Person}. Empty is the normal state and is not an error."""
    path = path or os.path.join(ROOT, "tourism", "people.json")
    raw = _read_json(path, {})
    out = collections.OrderedDict()
    for key, row in sorted((raw.get("people") or {}).items()):
        person = Person(key, row)
        if person.usable:
            out[key] = person
    return out


class Voice(object):
    """One thing an operator actually said, and the question they were asked.

    `said` is verbatim and is the only text on the site attributed to a named
    company. Anything the site itself knows — the season, the summary — is
    attributed to the site, because putting editorial into somebody else's
    mouth is fabrication whether or not the sentence is true.
    """

    def __init__(self, raw):
        self.operator_key = raw.get("operator") or ""
        self.country = raw.get("country") or ""
        self.asked = raw.get("asked") or ""
        self.said = raw.get("said") or ""
        self.by = raw.get("by") or ""
        self.verified = raw.get("verified") or ""

    @property
    def usable(self):
        return bool(self.said and self.operator_key)


def load_voices(path=None):
    """-> [Voice]. Only entries with an operator and something said."""
    path = path or os.path.join(ROOT, "tourism", "voices.json")
    raw = _read_json(path, {})
    return [v for v in (Voice(r) for r in (raw.get("voices") or [])) if v.usable]


def load_strands(path=None):
    """The seven doors of the human layer, minus the file's own notes."""
    path = path or os.path.join(ROOT, "tourism", "strands.json")
    raw = _read_json(path, {})
    return collections.OrderedDict(
        (k, v) for k, v in raw.items() if not k.startswith("$"))


def _read_json(path, fallback):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback


def load_views(path=None):
    """Country boxes in the continental map's coordinates, from africa_map.py."""
    path = path or os.path.join(ROOT, "tourism", "views.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {"africa": [0, 0, 1000, 1060], "countries": {}}


class Country:
    def __init__(self, raw, path):
        self.path = path
        self.slug = raw.get("slug") or ""
        self.name = raw.get("name") or ""
        self.adjective = raw.get("adjective") or self.name
        self.region = raw.get("region") or ""
        self.tagline = raw.get("tagline") or ""
        self.summary = raw.get("summary") or ""
        self.published = raw.get("published", True)
        # Where this country lives. Defaults to its own generated page; a country
        # run by a sister operator points at that operator's site instead, which
        # is why the region strips and the gateway can link every country without
        # anybody keeping a second list of exceptions in code.
        self.url = raw.get("url") or ("/%s" % self.slug)
        # What this country leads on, which of our companies runs it, and the
        # picture that belongs in its window. Editorial facts, so they live with
        # the rest of the country's editorial rather than in a table in code.
        self.calls = list(raw.get("calls") or [])
        self.operator_key = raw.get("operator") or ""
        self.window = raw.get("window") or ""
        self.window_alt = raw.get("window_alt") or ""
        # Which months are actually good here, and the sentence that says why.
        # "When can I go" is the second question every traveller asks and the
        # first one most tourism sites answer with a paragraph nobody reads.
        self.months = [int(m) for m in (raw.get("months") or [])]
        self.when = raw.get("when") or ""
        self.entries = [Entry(e) for e in raw.get("entries", [])]
        self.by_category = {}
        for e in self.entries:
            self.by_category.setdefault(e.category, []).append(e)

    @property
    def operator(self):
        return operator(self.operator_key)

    def entry(self, category_id):
        found = self.by_category.get(category_id)
        return found[0] if found else None


def load_country(path):
    with open(path) as f:
        try:
            raw = json.load(f)
        except ValueError as exc:
            raise DataError("%s is not valid JSON: %s" % (os.path.basename(path), exc))
    return Country(raw, path)


# The record fields that, between them, are the evidence a photograph shows what
# its alt text says: which rung of the query ladder matched it, and what the
# scorer found in the provider's own description.
PROVEN = ("queryTier", "relevance")


def attach_cache(countries, cache, taxonomy=None):
    """Bind resolved image metadata onto the content entries.

    And, on the way, refuse to let a record assert more than it can show.

    Alt text is spoken aloud as fact. The resolver is careful about this — a
    photograph matched on a broadened query gets a generic alt, because it is a
    waterfall in Cameroon and not the Lobe falls. But five records in the cache
    predate both the relevance scorer and the queryTier field: no rung, no
    score, no provider description, and alt text asserting "masked dancers and
    horsemen at the Nguon festival in Foumban" and "elephants and giraffe at a
    dry-season waterhole in Waza National Park".

    Those sentences may well be true. Nothing in the record says so, and the
    site's own rule is that it does not claim what it cannot support. Until such
    a record is resolved again — which costs one request each and settles it —
    it carries the generic alt instead. The caption and description on the page
    are unaffected: those are this site's writing about the place, not a claim
    about the photograph.
    """
    for country in countries:
        for entry in country.entries:
            rec = cache.get(country.slug, entry.category)
            if rec and not any(rec.get(k) for k in PROVEN):
                cat = (taxonomy.by_id.get(entry.category) if taxonomy else None)
                rec = dict(rec)
                # "Hero in Cameroon" is not a sentence. The opening picture of a
                # country is described by the country.
                if entry.category == "hero" or not cat:
                    rec["alt"] = country.name
                else:
                    rec["alt"] = "%s in %s" % (
                        cat["title"].split("/")[0].split("&")[0].strip(), country.name)
                rec["altUnproven"] = True
            entry.image = rec
    return countries


def load_countries(directory=COUNTRY_DIR):
    """Every country in the dataset, in slug order. No allow-list, no registry —
    the directory listing *is* the registry."""
    out = []
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        out.append(load_country(os.path.join(directory, name)))
    return out


# ---- writing back --------------------------------------------------------------


def dump_country(path, raw):
    """Write a country file the way a human would.

    json.dump(indent=2) explodes [50, 58] over four lines, which turns a readable
    dataset into something nobody wants to edit by hand. Focal pairs stay inline.
    """
    text = json.dumps(raw, indent=2, ensure_ascii=False)
    text = re.sub(
        r'\[\s*\n\s*(-?\d+(?:\.\d+)?),\s*\n\s*(-?\d+(?:\.\d+)?)\s*\n\s*\]',
        r"[\1, \2]",
        text,
    )
    with open(path, "w") as f:
        f.write(text + "\n")
