"""Provider registry.

Two lists, because there are two kinds of provider and only one kind can be
searched:

    SEARCH      Unsplash, Pexels. In priority order — this list *is* the
                priority order. `resolve` walks it and nothing else.
    GENERATORS  the generated-image provider. It owns records and builds
                delivery URLs like any other provider, but it has no search()
                and must never be handed a query.

BY_NAME spans both, because a cached record has to be able to find its owner
whichever kind made it. Adding a third search provider is one import and one
entry in SEARCH; nothing else in the system changes.
"""

from .base import Candidate, Provider, RateLimited, Unavailable  # noqa: F401
from .generated import Generated
from .pexels import Pexels
from .unsplash import Unsplash
from .uploaded import Uploaded

SEARCH = [Unsplash(), Pexels()]
# Not searchable, but they own records: a picture we made, and a picture we
# were given. Both are local files with no CDN behind them.
LOCAL = [Generated(), Uploaded()]
GENERATORS = LOCAL

REGISTRY = SEARCH                      # historic name: the searchable ones
BY_NAME = {p.name: p for p in SEARCH + LOCAL}

MISSING_KEYS_WARNING = (
    "Tourism image resolution requires UNSPLASH_ACCESS_KEY or PEXELS_API_KEY."
)


def all_providers(only=None):
    """Searchable providers in priority order, optionally narrowed to one.

    Deliberately not the generators: `resolve` is the only caller, and asking a
    generator for search results is a bug, not a fallback.
    """
    if only:
        if only not in {p.name for p in SEARCH}:
            raise KeyError("unknown provider %r; known: %s"
                           % (only, ", ".join(sorted(p.name for p in SEARCH))))
        return [p for p in SEARCH if p.name == only]
    return list(SEARCH)


def available(only=None):
    return [p for p in all_providers(only) if p.available()]


def for_record(record):
    """The provider that owns a cached record. Records carry `provider`, so this
    never has to guess from the URL."""
    name = (record or {}).get("provider")
    if name in BY_NAME:
        return BY_NAME[name]
    # Pre-provider records were all Unsplash; recognise them by host.
    url = (record or {}).get("imageUrl") or ""
    for p in SEARCH:
        if p.owns(url):
            return p
    return None


def owns_any(url):
    return any(p.owns(url) for p in BY_NAME.values())
