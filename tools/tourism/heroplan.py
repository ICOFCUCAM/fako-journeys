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
subset that decides what a phone downloads: the 836 /places pages whose HERO
is still a provider hotlink.

The distinction is not cosmetic. `tools/heroes.js` established that there is
exactly one eager remote photograph per page and that everything else is
loading="lazy" — never fetched until somebody scrolls. So these 836 references
are, between them, essentially the whole of the site's remaining avoidable
image payload, and every one of them is unbounded.

Eighty-six of the 836 are photographs we already own and have already
published; only 750 are an acquisition question at all. Those 86 are in the
table because they are the cheapest rows in it, not despite being cheap.

---------------------------------------------------------------------------
THE THING THIS TABLE EXISTS TO SAY

Bytes and photography are two problems, and only one of them costs money.

Every one of these 836 heroes is unbounded: the URL carries no width, so the
provider is asked for the file the photographer uploaded and sends it to a
390-pixel phone. That is fixable for nothing. 6,188 of the site's remaining
7,496 provider references already carry a width; these 836 do not, and adding
it needs no licence, no shoot, no agency and no new asset — it is the same
URL, asked for politely.

So the recommendation this table encodes is: bound them all now, which removes
most of the megabytes at zero cost, and then buy photographs on the merits of
the photographs, unhurried, because the page-weight emergency will already be
over.

That is why the bands below separate "free" from "worth paying for" rather
than ranking everything on one axis. Ranking a licence against a query-string
edit is comparing a purchase with a typo fix.
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
        return 0, "P0 free — already ours, needs a crop not a purchase"
    if row["owned replacement"]:
        return 0, "P0 free — an owned photograph already fits this slot"
    if not row["audited"]:
        # No verdict exists, so there is nothing to spend against. Buying a
        # replacement for a photograph nobody has assessed is how you pay for
        # a frame that was already correct.
        return 2, "P2 audit first — never assessed, no verdict to spend against"
    t = row["commercial tier"]
    if t <= 2:
        return 1, "P1 acquire now — operator or priced major route"
    if t == 3:
        return 2, "P2 acquire after P1 — priced West route"
    return 3, "P3 defer — no price attached to this country"


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
        nbytes, basis = (acquire.est_bytes(rec, uses, measured) if rec
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
        }
        # THE FREE FIX, WHICH IS THE POINT OF THE TABLE.
        if owned_here:
            row["free fix"] = (
                "Cut the phone crop from the original we already hold (%s) and "
                "let rewrite point the page at our own host. No purchase."
                % mine["id"])
        elif use["unbounded"]:
            row["free fix"] = (
                "Add a width to the existing URL — the same "
                "?auto=compress&cs=tinysrgb&w=1200 that 6,188 of the site's "
                "7,496 provider references already carry. No licence, no new "
                "asset, no "
                "budget, and it does not prejudge whether the photograph is "
                "any good.")
        else:
            row["free fix"] = "Already width-limited; nothing free left to do."
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
    def order(r):
        paid = r["_n"] >= 1
        return (r["_n"],
                (r["commercial tier"], -r["mobile bytes"]) if paid
                else (-r["mobile bytes"], r["commercial tier"]),
                -r["references"], r["country"], r["page"])
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
    for b in sorted(bands):
        log("  %-58s %4d   %6.2f GB" % (b, bands[b], bbytes[b] / 1e9))
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
        w("## The bands\n\n| band | pages | payload |\n|---|---:|---:|\n")
        for b in sorted(bands):
            w("| %s | %d | %.2f GB |\n" % (b, bands[b], bbytes[b] / 1e9))
        w("\n## Bytes and photographs are two problems\n\n")
        w("Only one of them costs money.\n\n")
        w("Every unbounded hero here can be width-limited today for nothing — "
          "the same `?auto=compress&cs=tinysrgb&w=1200` that 6,188 of the "
          "site's 7,496 remaining provider references already carry. No licence, no shoot, no "
          "agency, no new asset: the same URL, asked for politely. Doing that "
          "removes most of the payload below without spending a penny, and "
          "leaves the question of whether each photograph is any *good* to be "
          "answered on its own timetable.\n\n")
        w("That is the recommendation. Bound them all first; then buy "
          "photographs on the merits of the photographs.\n\n")
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
