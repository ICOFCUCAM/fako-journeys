"""Provider registry.

Order matters: this list is the priority order. Unsplash first, Pexels as the
fallback. Adding a third provider is one import and one entry.
"""

from .base import Candidate, Provider, RateLimited, Unavailable  # noqa: F401
from .pexels import Pexels
from .unsplash import Unsplash

REGISTRY = [Unsplash(), Pexels()]
BY_NAME = {p.name: p for p in REGISTRY}

MISSING_KEYS_WARNING = (
    "Tourism image resolution requires UNSPLASH_ACCESS_KEY or PEXELS_API_KEY."
)


def all_providers(only=None):
    """Providers in priority order, optionally narrowed to one by name."""
    if only:
        if only not in BY_NAME:
            raise KeyError("unknown provider %r; known: %s"
                           % (only, ", ".join(sorted(BY_NAME))))
        return [BY_NAME[only]]
    return list(REGISTRY)


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
    for p in REGISTRY:
        if p.owns(url):
            return p
    return None


def owns_any(url):
    return any(p.owns(url) for p in REGISTRY)
