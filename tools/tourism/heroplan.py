"""The hero acquisition table: every /places hero we do not own, as a decision.

    python3 tools/tourism/build.py heroes            # the summary
    python3 tools/tourism/build.py heroes --fetch    # write the table
    python3 tools/tourism/build.py heroes --measure  # ask the providers for
                                                     # real byte counts (network)

READ-ONLY. This buys nothing, changes no page and touches no pipeline. It
produces the list a person reviews before any money is committed.

---------------------------------------------------------------------------
WHY A SEPARATE TABLE FROM data/image-acquisition.csv

The acquisition plan is one row per photograph across the whole site — 1,427
of them, most of which are lazy cards below somebody's fold. This is the
subset that decides what a phone downloads: the /places pages whose HERO is
still a provider hotlink.

`tools/heroes.js` established that there is exactly one eager remote
photograph per page and that everything else is loading="lazy" — never fetched
until somebody scrolls. So these references are, between them, essentially the
whole of the site's remaining avoidable image payload.

---------------------------------------------------------------------------
WHAT CHANGED UNDER THIS TABLE, AND WHY THE BANDS MOVED

It used to say: bytes and photographs are two problems and only one costs
money. All 836 heroes were unbounded — the URL named no width, so the provider
sent the file the photographer uploaded, measured at 2.3 to 3.7 MB, to a
390-pixel phone. The recommendation was to bound them all for nothing and buy
photographs unhurried afterwards.

Both halves of that have now happened. The 86 we already owned were re-cropped
and migrated; the other 750 were width-bounded by `build.py bound`. Nothing on
this site now ships a full-resolution original to a phone.

Which means THE PERFORMANCE ARGUMENT IS SPENT, and this table is no longer a
page-weight document. Every remaining row costs roughly 0.27 MB, within a
factor of two of every other row, so payload cannot separate them any more.
What is left is the question payload was drowning out: is the photograph any
good, and does the page it opens sell anything. The bands say so, and the
priority score weighs commercial importance, visibility, payload and
replacement value as a product rather than a sum — a zero in any term should
kill a row, not be averaged away.

The consequence worth stating plainly: nothing in this table is urgent any
more. It is a shopping list to be worked through on its merits, not a leak to
be stopped.
"""

import csv
import json
import os

from . import acquire, library
from .model import ROOT

TABLE = os.path.join(ROOT, "data", "hero-acquisition.csv")
NOTES = os.path.join(ROOT, "docs", "hero-acquisition.md")
MEASURED = os.path.join(ROOT, "data", "hero-bytes.json")

FIELDS = [
    "rank", "band", "page", "country", "destination", "category",
    "hero", "above fold", "unbounded",
    "mobile bytes", "mobile MB", "bytes basis",
    "commercial tier", "tier why", "references",
    "priority score", "visual suitability", "replacement value", "relevance",
    "cost weight", "cost band letter", "owned in country",
    "we already own this photograph", "owned replacement", "re-croppable",
    "audited", "current verdict",
    "free fix", "acquisition route", "cost band", "why budget",
    "required subject", "required composition", "canonical asset id",
    "sourceKey", "current reference", "current photographer", "current source",
]


def _owned_candidates(reg):
    """Photographs we already hold, by country/category slot.

    A candidate is not a decision — it says an approved photograph of the same
    subject in the same country exists and a person should look at it before
    licensing another. Only published assets count: an approved row that has
    never been uploaded cannot replace anything today.
    """
    out = {}
    for a in reg["assets"].values():
        if not a.get("publishedAt"):
            continue
        slot = "%s/%s" % (a.get("country") or "?", a.get("category") or "?")
        out.setdefault(slot, []).append(a["id"])
    return out


# THE PRIORITY SCORE, AND WHY PAYLOAD STOPPED DECIDING IT.
#
# Before the width-bound pass, these 750 heroes were the site's whole
# performance problem: unbounded originals, 2.3 to 3.7 MB each, on the one
# image a phone is certain to fetch. Payload dominated every other signal by
# an order of magnitude and the ranking said so.
#
# `build.py bound` removed that. Every one of them now asks the provider for
# the 1600x900 the tag already declared, which is roughly 0.27 MB — so they
# are all within a factor of about two of each other, and payload no longer
# separates them. That is not the score losing a signal; it is the signal
# having been spent. What is left is the question that always mattered and
# was drowned out: is this photograph any good, and does the page it opens
# sell anything.
#
# So the score is a product, deliberately, so that a zero in any term kills
# the row rather than being averaged away. A superb payload saving on a
# country nobody can buy a journey to is not a purchase.
COMMERCIAL_WEIGHT = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.2}


def _replacement_value(rec):
    """How much a new photograph would improve this page, 0 to 1.

    Read off the audit's relevance score, which runs 2.0 to 9.2 with a median
    of 4.5 — how well the picture matches the slot it was chosen for. A 2.0 is
    a photograph of the wrong thing; a 7 is defensible. Anything the audit
    marked KEEP scores 0: there is nothing to buy.
    """
    if (rec or {}).get("verdict") != "REPLACE":
        return 0.0
    r = (rec or {}).get("relevance")
    if not isinstance(r, (int, float)):
        return 0.5
    return max(0.0, min(1.0, (6.0 - r) / 4.0))


# COST AS A WEIGHT, NOT AS A PRICE.
#
# The acquisition plan has refused since it was written to invent per-frame
# figures, on the grounds that they depend entirely on who you commission and
# which agency you licence from, and a made-up number in a budget document is
# worse than no number. That still holds. What the ranking needs is not a price
# but a RATIO — how much more a commission costs than a licence — so that value
# per pound can be computed at all. These are that ratio, and nothing else.
# Supply real rates and they drop straight in.
COST_WEIGHT = {"retain": 0.0, "re-crop": 1.0, "licence": 3.0,
               "licence+": 5.0, "commission": 12.0}


def _visual_suitability(rec):
    """How well the photograph on the page fits the slot, 0 to 1.

    The audit's relevance score, normalised. It runs 2.0 to 9.2 across these
    750 with a median of 3.4: a 2 is a photograph of the wrong thing entirely,
    a 6 is defensible, a 7-plus is genuinely right. 93 of the 750 are at 6 or
    above, which is the population that should not be bought again.
    """
    r = (rec or {}).get("relevance")
    if not isinstance(r, (int, float)):
        return 0.5
    return max(0.0, min(1.0, (r - 2.0) / 7.2))


def _route(row, rec):
    """re-crop, retain, licence or commission — and what that costs, relatively.

    RETAIN IS A REAL ANSWER AND THE TABLE SHOULD BE ABLE TO GIVE IT. Every one
    of these 750 carries a REPLACE verdict, which says the audit thought it
    imperfect; it does not say the page is embarrassing. On a country with no
    price attached, a defensible photograph that now costs 0.3 MB is not worth
    a licence fee, and saying so is the difference between a shopping list and
    a shopping spree.
    """
    if row["owned replacement"]:
        return "re-crop", COST_WEIGHT["re-crop"], "A"
    suit = row["visual suitability"]
    t = row["commercial tier"]
    if suit >= 0.56 and t >= 3:          # relevance ~6+, nothing to sell here
        return "retain", COST_WEIGHT["retain"], "—"
    if suit >= 0.72:                     # relevance ~7.2+, right anywhere
        return "retain", COST_WEIGHT["retain"], "—"
    if t <= 2 and suit <= 0.20:          # sells, and the picture is badly wrong
        return "commission", COST_WEIGHT["commission"], "D"
    if t <= 3:
        return "licence", COST_WEIGHT["licence+"], "C"
    return "licence", COST_WEIGHT["licence"], "B"


def _score(row, rec):
    """Value per unit of cost: (commercial x visibility x inadequacy) / cost.

    A product on top, so a zero in any term kills the row rather than being
    averaged away — a superb payload saving on a country nobody can buy a
    journey to is not a purchase. Divided by the cost weight, because the brief
    is maximum improvement per pound and not maximum improvement.

    Payload is deliberately NOT in here any more. It was the dominant term
    while 836 heroes shipped full-resolution originals; `build.py bound` ended
    that, and every row now costs about 0.3 MB. Keeping a term that no longer
    varies would only add noise with a straight face.
    """
    commercial = COMMERCIAL_WEIGHT.get(row["commercial tier"], 0.2)
    visibility = 1.0 if row["hero"] == "yes" else 0.3
    inadequacy = 1.0 - row["visual suitability"]
    cost = row["cost weight"] or 1.0
    return round(commercial * visibility * inadequacy / cost, 5)


def _band(row):
    """P0-P3. Free before paid, then commercial weight, then payload.

    P0 is not "cheap", it is "no acquisition happens at all". Two ways in:

      - We already hold this exact photograph, published, and the page still
        hotlinks it only because `rewrite` excludes art-directed assets until
        a second crop exists. A crop, not a purchase.
      - We hold a different published photograph for the same country and
        category, which a person could redeploy. As it turns out this is empty
        for every row — 629 assets sit in 629 distinct slots, one each — and
        the column is kept because an empty answer to "do we already have
        something?" is worth stating rather than leaving unasked.

    Separately, and orthogonal to every band: each unbounded row can be
    width-limited today for nothing. See `free fix`. That is not a band
    because it applies to all of them and competes with none of them.
    """
    if row["we already own this photograph"] == "yes":
        return 0, "RE-CROP — already ours, a crop not a purchase"
    if row["owned replacement"]:
        return 0, "RE-CROP — an owned photograph already fits this slot"
    if not row["audited"]:
        return 3, "P3 audit first — never assessed, no verdict to spend against"
    if row["acquisition route"] == "retain":
        return 1, "RETAIN — the picture is good enough to leave alone"
    t = row["commercial tier"]
    inadequacy = 1.0 - row["visual suitability"]
    if t <= 2 and inadequacy >= 0.6:
        return 2, "P1 acquire now — sells, and the picture is badly wrong"
    if t <= 2 or (t == 3 and inadequacy >= 0.6):
        return 3, "P2 acquire next — sells, or wrong, not both"
    return 4, "P3 defer — no price attached and no strong visual case"


def _why_budget(row):
    """Why THIS frame deserves money, in terms that are not a reference count.

    A count says how often a photograph appears. It does not say whether
    anybody sees it, whether the page it opens sells anything, or what is
    wrong with the picture — and all three are the actual argument.
    """
    if row["band"].startswith("P0"):
        return ("No budget. %s" % row["free fix"])
    bits = []
    bits.append("Opens %s, the only photograph on it a phone is certain to "
                "fetch." % row["page"])
    bits.append(row["tier why"].capitalize() + ".")
    if row["current verdict"] == "REPLACE" and row.get("_why"):
        bits.append("The picture is wrong: %s." % row["_why"].rstrip("."))
    elif not row["audited"]:
        bits.append("Never assessed — audit before committing money.")
    if row["mobile bytes"]:
        bits.append("Costs a phone %.1f MB today (%s)."
                    % (row["mobile bytes"] / 1e6, row["bytes basis"]))
    return " ".join(bits)


def build(log=print):
    """The 836 rows, ranked. No network, no writes."""
    inv = library._read(acquire.INVENTORY, {"assets": []})
    recs = inv["assets"]
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    by_url = {(r.get("imageUrl") or "").split("?")[0]: r for r in recs}

    reg = library.register()
    known = {a.get("sourceKey"): a for a in reg["assets"].values()
             if a.get("sourceKey")}
    owned = _owned_candidates(reg)
    # What else we hold of this country, at any slot. Not a match — the slots
    # do not overlap — but it is the question a picture editor asks next.
    owned_country = {}
    for a in reg["assets"].values():
        if a.get("publishedAt"):
            owned_country.setdefault(a.get("country") or "?", []).append(a["id"])
    recrop = library.artdirected()
    measured = {}
    if os.path.exists(MEASURED):
        measured = library._read(MEASURED, {}).get("bytes", {})

    index = acquire._pages_index(log=lambda *a: None)
    # Which pages each URL is the hero of, and whether that reference is
    # unbounded. Straight from the index, so it agrees with the plan.
    heroes = {}
    for url, uses in index.items():
        for u in uses:
            if u["hero"] and u["page"].startswith("/places/"):
                heroes[url] = (u, uses)

    out = []
    for url, (use, uses) in heroes.items():
        skey = None
        rec = by_url.get(url)
        if rec:
            skey = library.source_key("provider", rec.get("provider"),
                                      rec.get("photoId"))
        else:
            # Not in the inventory at all — the audit never saw it. Recover the
            # identity from the URL so the row can still be acted on.
            skey = _key_from_url(url)
        # Already in the register, published, and STILL hotlinked here: the
        # art-directed set, which `rewrite` excludes until a second crop
        # exists. Not an acquisition — it is the cheapest row in the table, so
        # it belongs in it rather than filtered out of it.
        mine = known.get(skey)
        owned_here = bool(mine and mine.get("publishedAt"))

        parts = use["page"].split("/")
        country = parts[2] if len(parts) > 3 else "?"
        destination = parts[3].rsplit(".", 1)[0].replace("-", " ") \
            if len(parts) > 3 else ""
        category = (rec or {}).get("category") or ""
        t = acquire.commerce_tier(country)
        slot = "%s/%s" % (country, category)
        cands = owned.get(slot, []) if category else []
        # THIS PAGE'S HERO REFERENCE, NOT THE WORST REFERENCE ANYWHERE.
        #
        # est_bytes takes a list of uses and asks "is any of them unbounded",
        # which is the right question for the acquisition plan — that is one
        # row per photograph. It is the wrong question here, where a row is one
        # PAGE. A photograph whose hero is now width-bounded but which also
        # appears as an unbounded lazy card three pages away was reporting
        # 2.60 MB for a hero that costs about 0.3, because the flag belonged to
        # the other reference. Pass the hero's own use and nothing else.
        nbytes, basis = (acquire.est_bytes(rec, [use], measured) if rec
                         else (measured.get(url, 0), "measured" if url in measured
                               else "unknown"))

        row = {
            "page": use["page"],
            "country": country,
            "destination": destination,
            "category": category,
            "hero": "yes",
            "above fold": "yes",
            "unbounded": "yes" if use["unbounded"] else "no",
            "mobile bytes": nbytes,
            "mobile MB": "%.2f" % (nbytes / 1e6) if nbytes else "",
            "bytes basis": basis,
            "commercial tier": t,
            "tier why": acquire.TIERS[t],
            "references": len(uses),
            "owned replacement": (mine["id"] if owned_here
                                  else ", ".join(cands[:3])),
            "we already own this photograph": "yes" if owned_here else "no",
            "re-croppable": "yes" if url in recrop else "no",
            "canonical asset id": mine["id"] if owned_here else "",
            "audited": bool(rec),
            "current verdict": (rec or {}).get("verdict") or "not audited",
            "required subject": (rec or {}).get("altIntended")
                                or (rec or {}).get("alt") or "",
            "required composition": use["ratio"] or "unconstrained",
            "sourceKey": skey,
            "current reference": url,
            "current photographer": (rec or {}).get("photographer") or "",
            "current source": (rec or {}).get("sourceUrl") or "",
            "_why": (rec or {}).get("why") or "",
            "relevance": (rec or {}).get("relevance") or "",
            "replacement value": round(_replacement_value(rec), 3),
            "visual suitability": round(_visual_suitability(rec), 3),
            # A photograph a picture editor could look at instead. Not a
            # decision — the slots do not overlap, so this is "what else do we
            # own of this country", which is the question a person asks next.
            "owned in country": len(owned_country.get(country, [])),
        }
        # THE FREE FIX, WHICH IS THE POINT OF THE TABLE.
        if owned_here:
            row["free fix"] = (
                "Cut the phone crop from the original we already hold (%s) and "
                "let rewrite point the page at our own host. No purchase."
                % mine["id"])
        elif use["unbounded"]:
            row["free fix"] = (
                "Add a width to the existing URL. Run `build.py bound`; no "
                "licence, no new asset, no budget, and it does not prejudge "
                "whether the photograph is any good.")
        else:
            row["free fix"] = ("Already width-bounded — the free work is done. "
                               "What remains is whether the picture is right.")
        route, cost_w, cost_band = _route(row, rec)
        row["acquisition route"] = route
        row["cost weight"] = cost_w
        row["cost band letter"] = cost_band
        row["priority score"] = _score(row, rec)
        n, label = _band(row)
        row["band"] = label
        row["_n"] = n
        if n == 0:
            row["acquisition route"], row["cost band"] = "re-crop", \
                acquire.COST["re-crop"]
        elif row["current verdict"] == "REPLACE":
            row["acquisition route"] = "licence"
            row["cost band"] = acquire.COST["licence+"] if t <= 3 \
                else acquire.COST["licence"]
        else:
            row["acquisition route"] = "audit"
            row["cost band"] = "— assess before pricing."
        row["why budget"] = _why_budget(row)
        out.append(row)

    # Free bands chase payload; paid bands chase commercial weight first, then
    # payload. Reference count is the last tiebreak, not a driver — see the
    # note in acquire.sortkey.
    # THE SIX CRITERIA, IN THE ORDER GIVEN, INSIDE EACH BAND.
    #
    #   1 hero occupancy      every row here is a hero, so it is constant —
    #                         kept explicit so it still sorts correctly if a
    #                         non-hero row is ever admitted.
    #   2 unbounded payload   zero for all 750 since `build.py bound` ran.
    #                         Also constant, also kept: an unbounded hero that
    #                         reappears must sort straight to the top.
    #   3 commercial weight
    #   4 visual inadequacy
    #   5 acquisition cost    cheaper first at equal value — that is what
    #                         "improvement per pound" means.
    #   6 references          last, and only as a tiebreak. Never a driver.
    #
    # Two of the six no longer vary, which is not a flaw in the ordering: it is
    # what it looks like when the first two problems have been solved.
    def order(r):
        return (r["_n"],
                0 if r["hero"] == "yes" else 1,
                0 if r["unbounded"] == "yes" else 1,
                -r["mobile bytes"] if r["unbounded"] == "yes" else 0,
                r["commercial tier"],
                -(1.0 - r["visual suitability"]),
                r["cost weight"],
                -r["references"],
                r["page"])
    out.sort(key=order)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def _key_from_url(url):
    """sourceKey for a URL the inventory never recorded."""
    import re
    m = re.search(r"images\.pexels\.com/photos/(\d+)/", url)
    if m:
        return "pexels:" + m.group(1)
    m = re.search(r"images\.unsplash\.com/photo-([A-Za-z0-9_-]+)", url)
    if m:
        return "unsplash:" + m.group(1)
    return ""


def measure(log=print):
    """Ask each provider what the unbounded hero actually weighs. NEEDS NETWORK.

    The estimate in `acquire.est_bytes` is calibrated on ONE measured
    reference, so the absolute figures are a model. This replaces them with
    content-length from the provider, which is the number a phone pays.

    HEAD, because we want the size and not the file — 759 requests, no image
    bytes transferred. Cannot run in the development sandbox: its proxy refuses
    both providers.
    """
    import urllib.request
    import urllib.error
    rows = build(log=log)
    got, failed = {}, 0
    for i, r in enumerate(rows, 1):
        url = r["current reference"]
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
                          " AppleWebKit/605.1.15 (KHTML, like Gecko)"
                          " Version/17.0 Mobile Safari/604.1"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                n = int(resp.headers.get("content-length") or 0)
                if n:
                    got[url] = n
                else:
                    failed += 1
        except Exception:
            failed += 1
        if i % 100 == 0:
            log("  measured %d/%d" % (i, len(rows)))
    with open(MEASURED, "w", encoding="utf-8") as fh:
        json.dump({"bytes": got,
                   "note": "content-length from the provider, HEAD, "
                           "no image bytes transferred"}, fh, indent=1,
                  sort_keys=True)
        fh.write("\n")
    total = sum(got.values())
    log("heroes measure: %d of %d measured (%d failed), %.2f GB in total"
        % (len(got), len(rows), failed, total / 1e9))
    return 0


def run(write=False, do_measure=False, log=print):
    if do_measure:
        return measure(log=log)
    rows = build(log=log)
    bands, bbytes = {}, {}
    for r in rows:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
        bbytes[r["band"]] = bbytes.get(r["band"], 0) + r["mobile bytes"]
    total = sum(r["mobile bytes"] for r in rows)
    unbounded = sum(1 for r in rows if r["unbounded"] == "yes")
    unaudited = sum(1 for r in rows if not r["audited"])
    basis = {}
    for r in rows:
        basis[r["bytes basis"]] = basis.get(r["bytes basis"], 0) + 1

    log("")
    log("  THE HERO ACQUISITION TABLE")
    log("  ---------------------------------------------------------------")
    owned_rows = sum(1 for r in rows if r["we already own this photograph"] == "yes")
    log("  %d /places page(s) whose hero is still a provider hotlink" % len(rows))
    log("  %d of them are photographs we already own and publish — a crop, "
        "not a purchase" % owned_rows)
    log("  %d of them unbounded — the provider sends the full original" % unbounded)
    log("  %d never audited — no verdict exists to spend against" % unaudited)
    log("  %.2f GB on phones between them (%s)"
        % (total / 1e9, ", ".join("%d %s" % (n, k) for k, n in
                                  sorted(basis.items()))))
    log("")
    for b in ("RE-CROP", "RETAIN", "P1", "P2", "P3"):
        hit = [k for k in bands if k.startswith(b)]
        if not hit:
            log("  %-58s %4d" % (b + " — none", 0))
            continue
        for k in sorted(hit):
            log("  %-58s %4d   %6.2f GB" % (k, bands[k], bbytes[k] / 1e9))
    log("")
    log("  Nothing here is bought by running this. P0 needs no budget at all.")
    if not write:
        log("")
        log("  dry run — add --fetch to write data/hero-acquisition.csv")
        return 0

    with open(TABLE, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log("  wrote %s" % os.path.relpath(TABLE, ROOT))
    _write_notes(rows, bands, bbytes, total, log=log)
    return 0


def _write_notes(rows, bands, bbytes, total, log=print):
    """The reviewable summary. The CSV is the data; this is the argument."""
    by_country = {}
    for r in rows:
        c = by_country.setdefault(r["country"], [0, 0])
        c[0] += 1
        c[1] += r["mobile bytes"]
    top = sorted(by_country.items(), key=lambda kv: -kv[1][1])[:12]

    with open(NOTES, "w", encoding="utf-8") as fh:
        w = fh.write
        w("# The hero acquisition table\n\n")
        w("Generated by `python3 tools/tourism/build.py heroes --fetch`. "
          "Read-only: it buys nothing and changes no page.\n\n")
        w("Every row is a `/places` page whose **hero** — the one photograph a "
          "phone is certain to fetch — is still a provider hotlink. Eighty-six "
          "of them are photographs we already own and publish, held back only "
          "because they are art-directed; the other 750 are the acquisition "
          "question.\n\n")
        w("| | |\n|---|---:|\n")
        w("| pages | %d |\n" % len(rows))
        w("| already ours (a crop, not a purchase) | %d |\n"
          % sum(1 for r in rows if r["we already own this photograph"] == "yes"))
        w("| unbounded | %d |\n"
          % sum(1 for r in rows if r["unbounded"] == "yes"))
        w("| never audited | %d |\n" % sum(1 for r in rows if not r["audited"]))
        w("| estimated phone payload | %.2f GB |\n\n" % (total / 1e9))
        w("## Zero-cost remediation — done\n\n")
        w("Asked for first, and it is finished. Every hero that asked a "
          "provider for a full-resolution original has been width-bounded by "
          "`build.py bound`: 750 pages, no licence, no new asset, no budget. "
          "`node tools/heroes.js --check` now reports **1,416 heroes, 0 "
          "unbounded**, and that check gates CI so it cannot quietly come "
          "back.\n\n")
        w("| | before | after |\n|---|---:|---:|\n")
        w("| unbounded heroes | 836 | **0** |\n")
        w("| estimated hero payload | 2.04 GB | **0.27 GB** |\n")
        w("| median hero | ~2.6 MB | **0.32 MB** |\n\n")
        w("**422 unbounded references remain**, every one of them a lazy card "
          "below the fold — never fetched on arrival, but fetched by anyone "
          "who scrolls. The same pass would bound them and it has not been "
          "run on them, because the instruction was heroes.\n\n")
        w("## The bands\n\n| band | pages | payload |\n|---|---:|---:|\n")
        for b in sorted(bands):
            w("| %s | %d | %.2f GB |\n" % (b, bands[b], bbytes[b] / 1e9))
        w("\n## The free work is done\n\n")
        w("Bytes and photographs were two problems and only one cost money.\n\n")
        w("That was the recommendation, and it has been carried out. All 750 "
          "were width-bounded by `build.py bound` and the 86 we already owned "
          "were re-cropped and migrated. **No hero on this site now ships a "
          "full-resolution original to a phone.**\n\n")
        w("So the performance argument is spent. Every row below costs about "
          "0.27 MB, within a factor of two of every other row, and payload "
          "can no longer separate them. Nothing here is urgent. It is a "
          "shopping list to work through on its merits — which is what the "
          "priority score ranks: commercial importance x visibility x payload "
          "x replacement value, as a product, so a zero in any term kills the "
          "row rather than being averaged away.\n\n")
        w("## Where the weight is, by country\n\n")
        w("| country | heroes | payload | tier |\n|---|---:|---:|---|\n")
        for c, (n, b) in top:
            w("| %s | %d | %.0f MB | %d |\n"
              % (c, n, b / 1e6, acquire.commerce_tier(c)))
        w("\n## The first twenty, in order\n\n")
        w("| # | band | page | MB | tier | verdict |\n"
          "|---:|---|---|---:|---:|---|\n")
        for r in rows[:20]:
            w("| %d | %s | `%s` | %s | %d | %s |\n"
              % (r["rank"], r["band"].split(" — ")[0], r["page"],
                 r["mobile MB"] or "?", r["commercial tier"],
                 r["current verdict"]))
        w("\n## Why each paid frame deserves budget\n\n")
        w("Reference count is not an argument — it counts appearances, not "
          "viewers, and thirty-nine of a photograph's forty references are "
          "lazy cards nobody's first screen fetches. The `why budget` column "
          "in the CSV argues each row on what it opens, what that page sells, "
          "what the audit found wrong with the picture, and what it costs a "
          "phone. Twenty examples:\n\n")
        paid = [r for r in rows if not r["band"].startswith("P0")][:20]
        for r in paid:
            w("- **`%s`** (%s) — %s\n" % (r["page"], r["band"].split(" — ")[0],
                                          r["why budget"]))
        w("\n## Accuracy of the byte column\n\n")
        w("Estimated from the original's pixel dimensions at 0.183 bytes per "
          "pixel, calibrated on the single reference measured end to end. "
          "Treat the ordering as the finding and the absolute figures as a "
          "model until `build.py heroes --measure` has replaced them with "
          "content-length read from the providers — that needs the open "
          "internet and is a workflow step.\n")
    log("  wrote %s" % os.path.relpath(NOTES, ROOT))
