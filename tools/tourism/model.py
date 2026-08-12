"""Data model for the tourism image system.

The source of truth is JSON on disk, not code:

    tourism/categories.json        the 27 categories, their order, and delivery presets
    tourism/countries/<slug>.json  one file per country, 27 entries each

Adding a country is one file. Nothing in this module, in the renderer, or in any
page needs to change — the engine walks tourism/countries/ and processes whatever
it finds. That is the whole point of the layout.
"""

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
        self.operator = raw.get("operator") or ""
        self.window = raw.get("window") or ""
        self.window_alt = raw.get("window_alt") or ""
        self.entries = [Entry(e) for e in raw.get("entries", [])]
        self.by_category = {}
        for e in self.entries:
            self.by_category.setdefault(e.category, []).append(e)

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


def attach_cache(countries, cache):
    """Bind resolved image metadata onto the content entries."""
    for country in countries:
        for entry in country.entries:
            entry.image = cache.get(country.slug, entry.category)
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
