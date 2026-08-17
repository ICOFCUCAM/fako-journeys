"""Photographs for the wonders that have none.

    python3 tools/tourism/build.py wondershots            what it would ask for
    python3 tools/tourism/build.py wondershots --fetch    ask Unsplash, then Pexels

WHAT THIS IS FOR

/wonders lists twenty-three places and four of them carry a photograph. The
other nineteen are set as numbered entries instead, which is a real design and
not a hole — but it is a design chosen around a shortage, and the shortage is
worth fixing where it can be fixed honestly.

THE RULE THIS FILE EXISTS TO KEEP

    A photograph under a place name is a claim that the photograph is OF that
    place.

That sentence is already in tourism/wonders.json, and it is the reason nobody
simply searched "waterfall" nineteen times and called it done. Keyword search
knows what a picture was TAGGED with. It does not know where it was taken. Ask
Unsplash for "Timbuktu" and you will be handed handsome desert photographs, a
share of which are Morocco.

So this does not accept a photograph because it came back first. It accepts one
only when the provider's OWN text — the description the photographer wrote —
names the place, and every wonder carries the words that count as naming it in
`photo_terms`. Everything else is staged in incoming/wonders-candidates.json
with its thumbnail and the photographer's words, for somebody to look at and
decide. This is the same posture as tourism-footage.yml: it stages, and it
places only what it can justify.

THE KEYS ARE NOT HERE AND ARE NOT MEANT TO BE

api.unsplash.com and api.pexels.com are refused by the agent proxy's egress
policy, and the keys are repository secrets. This runs on a runner:

    Actions -> Photographs for the wonders -> Run workflow

Run it with --fetch off first. It prints every query it would send and what it
would accept, which costs nothing and is the cheapest way to find out that
"Madagascar" is a country, an island, a film and a wonder, and that the search
needs saying differently.
"""

import json
import os

from .model import ROOT

WONDERS = os.path.join(ROOT, "tourism", "wonders.json")
STAGE = os.path.join(ROOT, "incoming", "wonders-candidates.json")
SHEET = os.path.join(ROOT, "incoming", "wonders-contact-sheet.md")

# How many the provider is asked for, per wonder, per provider. Small on
# purpose: this is a shortlist for a person to look at, not a library.
PER_WONDER = 8


def load():
    with open(WONDERS, encoding="utf-8") as fh:
        return json.load(fh)


def missing(d):
    """-> the wonders with no photograph, in the order the page prints them."""
    return [w for w in d["wonders"] if not w.get("photo")]


def terms(w):
    """The words that have to appear in a photographer's description before a
    picture is allowed to stand under this name.

    Taken from the file where they are written down, because which words prove
    a photograph is of Great Zimbabwe is an editorial judgement and not
    something to derive from a slug. A wonder with no terms is never bound
    automatically — it is only ever staged.
    """
    return [t.lower() for t in (w.get("photo_terms") or []) if t]


def query(w):
    """What to ask for. The name alone is wrong often enough to be worth
    storing an override: `Madagascar` the wonder is an ecosystem and the search
    engines think it is a country, an island and a cartoon."""
    return w.get("photo_query") or w["name"]


def names_it(said, w):
    """Does the photographer's own text name this place?

    EVERY entry must appear, and an entry may offer alternatives separated by
    a bar. AND across entries because "valley" and "kings" separately match a
    great deal of the world and together very nearly only match one dry valley
    in Egypt; OR inside one because a place is allowed two true names, and a
    photograph of Sossusvlei described as "Namib desert" is not a photograph of
    somewhere else.
    """
    need = terms(w)
    if not need:
        return False
    low = " ".join((said or "").lower().split())
    if not low:
        return False
    return all(any(alt in low for alt in t.split("|") if alt)
               for t in need)


def plan(d):
    """-> what would be asked for, without asking. Printed by the dry run."""
    out = []
    for w in missing(d):
        out.append({
            "id": w["id"],
            "name": w["name"],
            "strand": w["strand"],
            "query": query(w),
            "terms": terms(w),
        })
    return out


def search(w, usable, log=print):
    """Ask each provider in turn and return every candidate, tagged with
    whether the photographer's words name the place."""
    from .providers.base import RateLimited, Unavailable
    found = []
    for provider in usable:
        try:
            cands = provider.search(query(w), "landscape", per_page=PER_WONDER)
        except RateLimited:
            log("    %s: rate limited, moving on" % provider.name)
            continue
        except Unavailable as exc:
            log("    %s: unavailable (%s)" % (provider.name, exc))
            continue
        except Exception as exc:                       # a provider is not the build
            log("    %s: failed (%s)" % (provider.name, exc))
            continue
        for c in cands:
            said = (c.get("text") or "").strip()
            found.append({
                "wonder": w["id"],
                "provider": provider.name,
                "photoId": c.get("photoId"),
                "imageUrl": c.get("imageUrl"),
                "thumbnailUrl": provider.thumbnail_url(c),
                "sourceUrl": c.get("sourceUrl"),
                "photographer": c.get("photographer"),
                "photographerUrl": c.get("photographerUrl"),
                "width": c.get("width") or 0,
                "height": c.get("height") or 0,
                "said": said,
                "names_it": names_it(said, w),
            })
    return found


def bind(w, c):
    """Write a chosen photograph onto a wonder, in the shape /wonders already
    reads. The alt is the PHOTOGRAPHER'S sentence, never ours: our sentence is
    what we went looking for, and if the search returned something else our
    sentence confidently describes the something else."""
    w["photo"] = c["imageUrl"]
    w["photo_w"] = int(c["width"] or 1600)
    w["photo_h"] = int(c["height"] or 900)
    said = " ".join((c.get("said") or "").split())
    w["photo_alt"] = said[:1].upper() + said[1:] if said else w["name"]
    w["photo_provider"] = c["provider"]
    w["photo_by"] = c.get("photographer") or ""
    w["photo_by_url"] = c.get("photographerUrl") or ""
    w["photo_source"] = c.get("sourceUrl") or ""
    return w


def sheet(rows, d):
    """A contact sheet, so choosing is looking rather than reading JSON."""
    by = {}
    for r in rows:
        by.setdefault(r["wonder"], []).append(r)
    names = {w["id"]: w for w in d["wonders"]}
    out = ["# Candidate photographs for the wonders", "",
           "Every row is a picture a provider returned. **Named** means the",
           "photographer's own description contains every one of that wonder's",
           "`photo_terms` — those were bound automatically. The rest are here",
           "because keyword search knows what a picture was tagged with and not",
           "where it was taken; somebody has to look.", "",
           "To place one by hand: copy its image URL into that wonder's `photo`",
           "in `tourism/wonders.json`, with `photo_w`, `photo_h` and a",
           "`photo_alt` describing what is actually in the frame.", ""]
    for wid, rs in by.items():
        w = names.get(wid) or {"name": wid}
        out.append("## %s" % w.get("name", wid))
        out.append("")
        out.append("Asked for: `%s` — needs all of: %s"
                   % (query(w), ", ".join("`%s`" % t for t in terms(w)) or "_nothing set_"))
        out.append("")
        out.append("| | named | photographer | said |")
        out.append("|---|---|---|---|")
        for r in rs:
            out.append("| ![](%s) | %s | [%s](%s) | %s |"
                       % (r["thumbnailUrl"], "**yes**" if r["names_it"] else "no",
                          r.get("photographer") or "?", r.get("photographerUrl") or "#",
                          (r.get("said") or "").replace("|", "/") or "_nothing_"))
        out.append("")
    return "\n".join(out) + "\n"


def run(fetch=False, only=None, log=print):
    d = load()
    want = missing(d)
    if only:
        want = [w for w in want if w["id"] == only]
        if not want:
            log("no wonder with id %r is missing a photograph" % only)
            return 2

    log("%d of %d wonders have no photograph."
        % (len(missing(d)), len(d["wonders"])))
    no_terms = [w["name"] for w in want if not terms(w)]
    if no_terms:
        log("\n%d have no photo_terms and can only ever be staged, never bound:"
            % len(no_terms))
        for n in no_terms:
            log("    %s" % n)

    if not fetch:
        log("\nDRY RUN — nothing was asked for. What it would send:\n")
        for p in plan(d):
            log("  %-28s  %-42s  needs all of: %s"
                % (p["name"], '"%s"' % p["query"],
                   ", ".join(p["terms"]) or "— (stage only)"))
        log("\nRun it with --fetch, on a runner that has the keys:")
        log("    Actions -> Photographs for the wonders -> Run workflow")
        return 0

    from . import resolve
    from .providers.base import Unavailable
    try:
        usable, problems = resolve.preflight(None)
    except Unavailable as exc:
        log("UNAVAILABLE: %s" % exc)
        log("\nNothing was written. This repository never stores an image URL it "
            "has not fetched, so a wonder with no photograph keeps its number "
            "rather than gaining a plausible-looking broken link.")
        return 2
    log("providers: %s" % ", ".join(p.name for p in usable))
    for note in problems:
        log("  unavailable — %s" % note)

    rows, bound, taken = [], 0, set()
    for w in want:
        log("\n%s" % w["name"])
        found = search(w, usable, log=log)
        rows.extend(found)
        pick = next((c for c in found
                     if c["names_it"] and c["photoId"] not in taken), None)
        if pick:
            # One photograph is never handed to two wonders. Two entries on one
            # page carrying the same picture under different names would break
            # the claim this whole file is built to keep, twice at once.
            taken.add(pick["photoId"])
            bind(w, pick)
            bound += 1
            log("    BOUND  %s — \"%s\"" % (pick["provider"], pick["said"]))
        else:
            log("    staged %d candidate(s); none named it" % len(found))

    os.makedirs(os.path.dirname(STAGE), exist_ok=True)
    with open(STAGE, "w", encoding="utf-8") as fh:
        json.dump({"$says": ("Candidates for the wonders with no photograph. "
                             "Nothing here is on the site. `names_it` is the "
                             "photographer's own description containing every "
                             "one of that wonder's photo_terms."),
                   "candidates": rows}, fh, ensure_ascii=False, indent=1,
                  sort_keys=True)
        fh.write("\n")
    with open(SHEET, "w", encoding="utf-8") as fh:
        fh.write(sheet(rows, d))

    if bound:
        with open(WONDERS, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

    log("\nbound %d, staged %d candidate(s) across %d wonder(s)"
        % (bound, len(rows), len(want)))
    log("  %s" % os.path.relpath(SHEET, ROOT))
    log("  %s" % os.path.relpath(STAGE, ROOT))
    if bound:
        log("\nnow run: python3 tools/tourism/build.py wonders")
    return 0
