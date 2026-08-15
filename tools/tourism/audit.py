"""Does the photograph show what the page says it shows?

    python3 tools/tourism/build.py audit
    python3 tools/tourism/build.py audit --country cabo-verde

WHY THIS COULD NOT BE SEEN BEFORE

A place page carries a photograph, a caption and an alt attribute. The caption
and the alt are both written from the dataset — from what we meant to show —
so they agree with each other whatever the photograph turns out to be. "The
Cloud Forest of Santo Antao", alt "dragon trees and cloud in the highlands",
over a photograph of fishing boats in a dry harbour. Every text check on the
site passes, because the text is consistent; it is only wrong about the image.

That makes the alt worse than useless here. It is a false statement read aloud
to somebody who cannot see the photograph: /comoros told a screen reader it
was showing a dhow off the volcanic coast of Grande Comore, and was showing a
canal in Trieste.

WHAT THIS READS INSTEAD

The one piece of text about a photograph that was not written by us: the
provider's own. Pexels and Unsplash both describe their photographs, and the
description survives in the cached record's sourceUrl slug. That is evidence,
and it is already sitting in tourism/cache/images.json for all 854 resolved
slots — no API calls, no rate limit, no waiting three hours.

WHAT IT FINDS

  ELSEWHERE   the photograph names a place the journey does not go. Trieste as
              Comoros, Tenerife as Cabo Verde, Guayaquil as Cote d'Ivoire,
              children in Somalia as Cabo Verde. The worst class, because the
              page is not merely vague, it is wrong about the continent.

  STOPWORD    the slot was won on a function word. "subject: the" scored 4.17
              and published the fishing boats. relevance.words() dropped
              anything under three letters, which removes "of" and "in" and
              keeps "the", "and", "with", "from" — the four words least
              capable of telling two photographs apart.

  THIN        rescored under the corrected rules and now below MIN_SCORE. The
              photograph may be of the right country and is not evidently of
              the right subject.

By default it prints and changes nothing, because an audit that edits is an
audit nobody runs twice. With --force it quarantines what it found.

QUARANTINE, NOT DELETION

A rejected slot moves from `entries` to `rejected`, keeping the record and
gaining a reason. Two things follow. The page stops publishing the wrong
photograph immediately and falls back to the country plate — the designed
fallback that 604 unresolved slots already use, and unambiguously better than
Mount Vesuvius captioned as the Cameroonian Ring Road. And the photo id stays
known, so the resolver will not spend a fresh API call re-picking the same
picture it has already been told is wrong.
"""

import json
import os
import re

from . import relevance
from .model import ROOT, load_countries, load_taxonomy

CACHE = os.path.join(ROOT, "tourism", "cache", "images.json")


def slug_words(rec):
    """What the provider called this photograph.

    The trailing digits are the photo id and the leading words are the
    description, in both providers' URL shapes:
        /photo/colorful-fishing-boats-in-pedra-lume-cabo-verde-28486941/
        /photos/a-lone-tree-in-a-field-of-dry-grass-oBKy0j5HY5Y
    """
    slug = (rec.get("sourceUrl") or "").rstrip("/").split("/")[-1]
    # The id is the last hyphen-separated token and nothing more. A pattern
    # whose character class included the hyphen ate the whole description back
    # to the first word: "colorful fishing boats in pedra lume cabo verde"
    # became "colorful", which is also why the elsewhere check came up empty on
    # a country whose photographs are half Canary Islands.
    slug = re.sub(r"-[A-Za-z0-9_]{11}$", "", slug)     # unsplash id
    slug = re.sub(r"-\d+$", "", slug)                  # pexels id
    return slug.replace("-", " ")


def load_cache():
    with open(CACHE, encoding="utf-8") as fh:
        return json.load(fh)


def run(only=None, force=False, log=print):
    cache = load_cache()
    entries = cache.get("entries", {})
    tax = load_taxonomy()
    by_slug = {c.slug: c for c in load_countries()}

    found = {"elsewhere": [], "stopword": [], "thin": []}
    checked = 0

    for key, rec in sorted(entries.items()):
        slug = rec.get("country") or key.split("/")[0]
        if only and slug != only:
            continue
        country = by_slug.get(slug)
        if not country:
            continue
        checked += 1
        said = slug_words(rec)
        cand = {"text": said, "width": rec.get("width") or 0,
                "height": rec.get("height") or 0}

        away = relevance.elsewhere(cand, country)
        if away:
            found["elsewhere"].append((key, rec, said, ", ".join(away[:3])))
            continue

        # What the slot was won on, as recorded at the time.
        reasons = (rec.get("relevance") or {}).get("reasons") or []
        subj = [r for r in reasons if r.startswith("subject: ")]
        if subj:
            hits = subj[0][len("subject: "):].split(",")
            if hits and all(h.strip() in relevance.STOP for h in hits if h.strip()):
                found["stopword"].append((key, rec, said, ",".join(hits)))
                continue

        was = (rec.get("relevance") or {}).get("score")
        if was is not None and was < relevance.MIN_SCORE + 1.0:
            found["thin"].append((key, rec, said, "%.2f" % was))

    log("checked %d resolved photograph(s)%s\n"
        % (checked, " in %s" % only if only else ""))

    titles = {
        "elsewhere": "THE PHOTOGRAPH NAMES SOMEWHERE ELSE",
        "stopword": "THE SLOT WAS WON ON A FUNCTION WORD",
        "thin": "THIN: barely above the floor, and the floor is low",
    }
    for kind in ("elsewhere", "stopword", "thin"):
        rows = found[kind]
        if not rows:
            log("%s: none\n" % titles[kind])
            continue
        log("%s  (%d)" % (titles[kind], len(rows)))
        for key, rec, said, why in rows[:40]:
            log("  %-30s %-30s" % (key, (rec.get("caption") or "")[:28]))
            log("     page says : %s" % (rec.get("alt") or "")[:88])
            log("     photo says: %s   [%s]" % (said[:70], why))
        if len(rows) > 40:
            log("  ... %d more" % (len(rows) - 40))
        log("")

    total = sum(len(v) for v in found.values())
    log("%d of %d need a different photograph." % (total, checked))

    if not force:
        if total:
            log("\nNothing changed. Run with --force to quarantine them, and the "
                "pages fall back to the country plate until a photograph that "
                "shows the right thing is resolved.")
        return found

    rejected = cache.setdefault("rejected", {})
    moved = 0
    for kind, rows in found.items():
        for key, rec, said, why in rows:
            if key not in entries:
                continue
            out = dict(entries.pop(key))
            out["rejected"] = {"kind": kind, "why": why, "photoSays": said}
            rejected[key] = out
            moved += 1
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    log("\nquarantined %d; %d photographs still published."
        % (moved, len(entries)))
    return found
