"""The image inventory: what this site hotlinks, from whom, and whether to keep it.

    python3 tools/tourism/build.py assets            # report to the terminal
    python3 tools/tourism/build.py assets --fetch    # and write data/asset-inventory.json

READS ONLY. This module does not download a photograph, does not touch an HTML
file and does not delete anything. It is the survey that has to happen before
any of that is decided, and it is deliberately separate from whatever executes
the decision.

---------------------------------------------------------------------------
WHY THIS EXISTS

Counted across the built site: 3,585 <img> tags point at images.pexels.com and
332 at images.unsplash.com. Eighty-six point at a file this project holds. So
the photography — which is most of what this site is — is somebody else's,
served from somebody else's machine, on somebody else's terms.

Three consequences, none of them design opinions:

  RELIABILITY   A URL that changes or a photograph that is withdrawn breaks a
                page silently. link-checks.js checks 78,595 internal links and
                cannot see any of these.
  PRIVACY       Every visitor's IP reaches Pexels and Unsplash on every page
                view, with no consent step. For a business selling into Europe
                that is a third-party transfer.
  CONTROL       The crops, the sizes and the formats are decided by a query
                string. There is no version of "our house style" that survives
                that.

---------------------------------------------------------------------------
WHAT IT KNOWS, AND FROM WHERE

Two sources, joined on the photograph's own id.

  the built HTML          which pages actually reference which URL, and at
                          what widths, and with what alt text. This is the
                          ground truth for "is it used".
  tourism/cache/images.json
                          what the resolver recorded when it chose the
                          photograph: provider, photo id, photographer and
                          their page, the source URL, the query that found it,
                          the date, the dimensions, the focal point, the alt
                          text it got and the alt text it WANTED, and its own
                          relevance score with the reasons behind it.

That cache is already most of a provenance record. What it does not hold is a
licence line, a download date (createdAt is when it was *chosen*), a stable
Afrinkong filename, or the pages using it — which is exactly what a first-party
library needs and what this inventory adds.

---------------------------------------------------------------------------
HOW A PHOTOGRAPH IS CLASSIFIED, AND WHY BY THESE RULES

The point of the survey is not to preserve what is there. It is to find what is
worth paying to host. Every rule below is a fact already recorded by the
resolver, not a judgement made here:

  REMOVE              nothing references it. A cache entry for a slot that no
                      longer renders is a photograph nobody is looking at.
  PROVENANCE REVIEW   the HTML points at a URL the cache has never heard of.
                      No photographer, no licence, no source page — and the
                      one thing a first-party library must never do is host a
                      file it cannot say where it came from.
  REPLACE             the resolver itself recorded a weak match. Three
                      independent signals, any one of which is enough:
                        - it scored under 4.0 out of 9.2 on its own relevance
                        - it had to broaden the query from the subject to the
                          category to find anything at all (queryTier)
                        - the alt text it got does not name the country the
                          page is about, while the alt text it WANTED did
                      These are the generic and the geographically unsupported
                      ones, in the resolver's own words.
  KEEP                everything else, which is the set worth downloading.

A photograph classified REPLACE is not deleted here and not downloaded here.
It stays on the page, hotlinked, until something better is commissioned or
found — because a plate is honest and a blank is not.
"""

import collections
import json
import os
import re

from .model import ROOT

CACHE = os.path.join(ROOT, "tourism", "cache", "images.json")
OUT = os.path.join(ROOT, "data", "asset-inventory.json")

EXTERNAL_RE = re.compile(r'https://images\.(?:pexels|unsplash)\.com/[^"\s\\]+')
TAG_RE = re.compile(r"<(?:img|source)\b[^>]*>", re.I)
ALT_RE = re.compile(r'\balt="([^"]*)"')

# What "worth hosting" costs. Measured on this site's own photographs by the
# `modern` pass: AVIF lands at 63% of the JPEG it replaces and WebP at 84%. A
# responsive ladder of four widths costs roughly 1.9x the largest alone, since
# each step down is about a quarter of the area of the one above it.
LADDER = (480, 800, 1200, 1600)
BYTES_PER_PIXEL_AVIF = 0.055      # measured across the 130 encoded photographs
LADDER_MULTIPLE = 1.0 + 0.5625 + 0.25 + 0.09


def identity(url):
    """The photograph a URL names, independent of size and query string.

    Pexels serves the same photograph at any width from one path with a
    numeric id in it; Unsplash from one path with an opaque id. Both are
    stable, and both are what "the same picture twice" has to be judged on —
    a URL with `?w=800` on it is not a different photograph.
    """
    core = url.split("?")[0]
    m = re.search(r"/photos/(\d+)/", core)
    if m:
        return "pexels:%s" % m.group(1)
    m = re.search(r"/(photo-[\w-]+)", core)
    if m:
        return "unsplash:%s" % m.group(1)
    return "other:%s" % core


def _pages(log=print):
    """identity -> {urls, pages, alts}, from the built HTML."""
    found = collections.defaultdict(
        lambda: {"urls": set(), "pages": set(), "alts": set()})
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ("node_modules", ".git", "incoming", "tools")
                   and not d.startswith(".")]
        for name in sorted(files):
            if not name.endswith(".html"):
                continue
            full = os.path.join(base, name)
            rel = "/" + os.path.relpath(full, ROOT).replace(os.sep, "/")
            with open(full, encoding="utf-8") as fh:
                html = fh.read()
            if "images.pexels.com" not in html and "images.unsplash.com" not in html:
                continue
            for tag in TAG_RE.finditer(html):
                urls = EXTERNAL_RE.findall(tag.group(0))
                if not urls:
                    continue
                alt = ALT_RE.search(tag.group(0))
                for url in urls:
                    rec = found[identity(url)]
                    rec["urls"].add(url)
                    rec["pages"].add(rel)
                    if alt and alt.group(1).strip():
                        rec["alts"].add(alt.group(1).strip())
    return found


def _cache():
    """identity -> the resolver's record, plus the slot it was chosen for."""
    try:
        with open(CACHE, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (IOError, ValueError):
        return {}
    out = {}
    for slot, rec in (raw.get("entries") or {}).items():
        url = rec.get("imageUrl") or ""
        if not url:
            continue
        rec = dict(rec)
        rec["slot"] = slot
        out[identity(url)] = rec
    return out


def _classify(rec, used):
    """One photograph, one verdict, and the reason in the resolver's words."""
    if not used:
        return "REMOVE", "no page references it"
    if not rec:
        return "PROVENANCE REVIEW", "no resolver record — photographer and licence unknown"

    why = []
    score = (rec.get("relevance") or {}).get("score")
    if isinstance(score, (int, float)) and score < 4.0:
        why.append("relevance %.1f" % score)
    if rec.get("queryTier") and rec["queryTier"] != "subject":
        why.append("query broadened to %s" % rec["queryTier"])
    country = (rec.get("country") or "").replace("-", " ")
    alt = (rec.get("alt") or "").lower()
    intended = (rec.get("altIntended") or "").lower()
    if country and country not in alt and country in intended:
        why.append("does not name %s, which the slot asked for" % country.title())
    if why:
        return "REPLACE", "; ".join(why)
    return "KEEP", "relevance %.1f, subject query, names its country" % (score or 0)


def _bytes(rec):
    """What one photograph would cost as an AVIF ladder, in bytes.

    From its own recorded dimensions, capped at the widest size this site
    actually paints, and multiplied out over the four-step ladder.
    """
    w = float(rec.get("width") or 1600)
    h = float(rec.get("height") or 1067)
    ratio = (h / w) if w else 0.667
    top = min(w, float(LADDER[-1]))
    return int(top * top * ratio * BYTES_PER_PIXEL_AVIF * LADDER_MULTIPLE)


def survey(log=print):
    used = _pages(log=log)
    cache = _cache()

    rows = []
    for ident in sorted(set(used) | set(cache)):
        rec = cache.get(ident, {})
        seen = used.get(ident)
        verdict, why = _classify(rec, seen)
        rows.append({
            "id": ident,
            "provider": rec.get("provider") or ident.split(":")[0],
            "photoId": rec.get("photoId") or ident.split(":", 1)[1],
            "verdict": verdict,
            "why": why,
            "pages": sorted(seen["pages"]) if seen else [],
            "pageCount": len(seen["pages"]) if seen else 0,
            "slot": rec.get("slot"),
            "country": rec.get("country"),
            "category": rec.get("category"),
            "photographer": rec.get("photographer"),
            "photographerUrl": rec.get("photographerUrl"),
            "sourceUrl": rec.get("sourceUrl"),
            "imageUrl": rec.get("imageUrl") or (sorted(seen["urls"])[0] if seen else None),
            "query": rec.get("query"),
            "chosenAt": rec.get("createdAt"),
            "width": rec.get("width"),
            "height": rec.get("height"),
            "relevance": (rec.get("relevance") or {}).get("score"),
            "alt": rec.get("alt"),
            "altIntended": rec.get("altIntended"),
            "estimatedAvifBytes": _bytes(rec) if verdict == "KEEP" else 0,
        })
    return rows


def run(write=False, log=print):
    rows = survey(log=log)
    by = collections.Counter(r["verdict"] for r in rows)
    prov = collections.Counter(r["provider"] for r in rows)
    pages = set()
    for r in rows:
        pages.update(r["pages"])
    keep = [r for r in rows if r["verdict"] == "KEEP"]
    store = sum(r["estimatedAvifBytes"] for r in keep)

    log("")
    log("  THE EXTERNAL IMAGE INVENTORY")
    log("  ---------------------------------------------------------------")
    log("  unique photographs hotlinked   %6d" % len([r for r in rows if r["pageCount"]]))
    log("    of them from Pexels          %6d" % prov.get("pexels", 0))
    log("    of them from Unsplash        %6d" % prov.get("unsplash", 0))
    log("  pages affected                 %6d" % len(pages))
    log("")
    for verdict in ("KEEP", "REPLACE", "PROVENANCE REVIEW", "REMOVE"):
        log("  %-22s %6d" % (verdict, by.get(verdict, 0)))
    log("")
    log("  storage if only KEEP is hosted, AVIF, four widths to 1600:")
    log("    %.0f MB across %d photographs (%.0f KB each)"
        % (store / 1e6, len(keep), (store / len(keep) / 1e3) if keep else 0))
    log("")

    if write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({
                "$comment": "Every external photograph this site references, "
                            "what it is, where it is used, and whether it is "
                            "worth hosting. Written by tools/tourism/assets.py. "
                            "Nothing here has been downloaded.",
                "counts": dict(by),
                "pagesAffected": len(pages),
                "estimatedKeepBytes": store,
                "assets": rows,
            }, fh, indent=1, ensure_ascii=False, sort_keys=False)
        log("  written to %s (%.0f KB)"
            % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1e3))
    else:
        log("  dry run — add --fetch to write data/asset-inventory.json")
    return 0
