"""Server-side image resolver: Unsplash first, Pexels as fallback.

The hard rule, unchanged and now enforced for both providers: a URL only
reaches the cache if the provider's API returned it AND a subsequent HTTP
request fetched it successfully. No code path anywhere constructs a photo id.
The APIs are the authority for ids and URLs; this module only appends transform
parameters to URLs they handed back.

    export UNSPLASH_ACCESS_KEY=...          # primary
    export PEXELS_API_KEY=...               # fallback
    python3 tools/tourism/build.py resolve --country cameroon
    python3 tools/tourism/build.py resolve --provider pexels --force

Order per slot, for each query in the ladder:

    Unsplash  ->  Pexels  ->  next query  ->  local illustration  ->  unresolved

Unsplash wins ties. Pexels only displaces it when it scores CLEARLY_BETTER, so
the fallback cannot quietly become the default.

Keys are read from the environment by this CLI, which runs on a developer or CI
machine. Neither key is written to the cache, rendered into HTML, committed, or
sent to a browser: the site is static files.
"""

import datetime
import urllib.error
import urllib.request

from . import providers, queries, relevance
from .providers import RateLimited, Unavailable  # noqa: F401  (re-exported)

MISSING_KEY_WARNING = providers.MISSING_KEYS_WARNING
UA = providers.base.UA


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def preflight(only=None):
    """At least one provider must be usable. Returns the ones that are."""
    usable, problems = [], []
    for p in providers.all_providers(only):
        if not p.available():
            problems.append("%s: %s not set" % (p.name, p.key_env))
            continue
        try:
            p.preflight()
            usable.append(p)
        except Exception as exc:
            problems.append("%s: %s" % (p.name, exc))
    if not usable:
        raise Unavailable(MISSING_KEY_WARNING + " " + "; ".join(problems))
    return usable, problems


def verify(url, timeout=20):
    """Fetch the delivery URL for real. Returns (ok, detail)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if r.status != 200:
                return False, "HTTP %s" % r.status
            if not ctype.startswith("image/"):
                return False, "content-type %s" % ctype
            if len(r.read(4096)) < 1024:
                return False, "suspiciously small response"
            return True, ctype
    except urllib.error.HTTPError as exc:
        return False, "HTTP %d" % exc.code
    except Exception as exc:
        return False, str(exc)


def build_record(candidate, provider, country, category, entry, query, tier, role):
    """Normalise a candidate into the stored schema. Every value here either came
    from the API response or from the country dataset — none is invented."""
    from .validate import alt_text

    alt = (alt_text(country, entry) if tier == "subject"
           else queries.generic_alt(country, category))
    w, h = candidate.get("width") or 0, candidate.get("height") or 0
    return {
        "country": country.slug,
        "category": category["id"],
        "caption": entry.caption,
        "description": entry.description,
        "provider": provider.name,
        "photoId": candidate["photoId"],
        "imageUrl": candidate["imageUrl"],
        "thumbnailUrl": provider.thumbnail_url(candidate),
        "sourceUrl": candidate.get("sourceUrl"),
        "photographer": candidate.get("photographer"),
        "photographerUrl": candidate.get("photographerUrl"),
        "width": w,
        "height": h,
        "aspectRatio": round(w / float(h), 4) if h else None,
        "alt": alt,
        "query": query,
        "queryTier": tier,
        "focalPoint": {"x": entry.focal["x"], "y": entry.focal["y"]},
        "createdAt": now(),
        "verifiedAt": None,
        "relevance": None,
    }


def _best_from(provider, query, orient, country, category, entry, role, seen):
    """Search one provider, rank, and return the best candidate that survives a
    real HTTP fetch. Returns (record, score, notes, candidate).

    The candidate travels back alongside the record because Unsplash's guidelines
    require pinging a download endpoint that only exists on the raw API object —
    it is deliberately not part of the stored schema.
    """
    try:
        candidates = provider.search(query, orient)
    except RateLimited:
        raise
    except Exception as exc:
        return None, 0.0, ["%s search failed: %s" % (provider.name, exc)], None
    if not candidates:
        return None, 0.0, ["%s: no results" % provider.name], None

    ranked = relevance.rank(candidates, country, category, entry, role, seen)
    if not ranked:
        return None, 0.0, ["%s: %d results, none relevant enough"
                           % (provider.name, len(candidates))], None

    notes = []
    for score, why, cand in ranked[:4]:
        record = build_record(cand, provider, country, category, entry, query, "subject", role)
        try:
            probe = provider.delivery_url(record, role, entry.focal)
        except ValueError as exc:
            notes.append(str(exc))
            continue
        ok, detail = verify(probe)
        if not ok:
            notes.append("%s %s failed verification (%s)"
                         % (provider.name, cand["photoId"], detail))
            continue
        record["verifiedAt"] = now()
        record["relevance"] = {"score": round(score, 2), "reasons": why}
        return record, score, notes, cand
    return None, 0.0, notes, None


def resolve_entry(country, category, entry, role, seen, only=None):
    """Fill one slot. Returns (record, error).

    Walks the query ladder; at each rung tries every available provider in
    priority order before broadening the query, because a precise query on the
    fallback beats a vague one on the primary.
    """
    orient = queries.orientation(category["role"])
    rungs = queries.ladder(country, category, entry)
    usable = providers.available(only)
    if not usable:
        return None, MISSING_KEY_WARNING
    notes = []

    for query, tier in rungs:
        results = []
        for provider in usable:
            record, score, why, cand = _best_from(provider, query, orient, country,
                                                  category, entry, role, seen)
            notes.extend(why)
            if record:
                record["queryTier"] = tier
                if tier != "subject":
                    record["alt"] = queries.generic_alt(country, category)
                results.append((provider, record, score, cand))

        if results:
            primary, rec, best, chosen = results[0]
            for provider, record, score, cand in results[1:]:
                # A fallback has to be clearly better, not merely better, or the
                # primary stops meaning anything.
                if score >= best + relevance.CLEARLY_BETTER:
                    primary, rec, best, chosen = provider, record, score, cand
            primary.after_use(chosen or {})
            seen.add("%s:%s" % (rec["provider"], rec["photoId"]))
            return rec, None

    return None, "no relevant, verifiable image across %d queries and %d provider(s): %s" % (
        len(rungs), len(usable), "; ".join(notes[:3]))
