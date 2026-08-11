#!/usr/bin/env python3
"""Tourism image system — command line.

    build.py validate            completeness + integrity report for every country
    build.py status              Country | Category | Photo ID | CDN URL | Status
    build.py queries             the search query for every slot
    build.py resolve             fill image slots from Unsplash, then Pexels
    build.py render              write tourism/<slug>.html
    build.py verify              check the rendered HTML
    build.py test                run the resolver test suite against a local mock
    build.py scaffold            create a new country with 27 empty slots
    build.py report              write tourism/REPORT.md
    build.py all                 validate, render, verify, report

Flags: --country <slug>  --category <id>  --provider unsplash|pexels  --force

Adding a country: drop a JSON file in tourism/countries/ and run `all`. No code
changes, no new components, no template edits.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tourism import cache as cache_mod  # noqa: E402
from tourism import imaging, providers, queries, render, resolve, validate, verify  # noqa: E402
from tourism.model import ROOT, attach_cache, load_countries, load_taxonomy  # noqa: E402


def dataset(country=None):
    """Every country, with resolved images bound on from the cache."""
    tax = load_taxonomy()
    cache = cache_mod.load()
    countries = attach_cache(load_countries(), cache)
    if country:
        countries = [c for c in countries if c.slug == country]
        if not countries:
            print("no country with slug %r in tourism/countries/" % country)
            sys.exit(2)
    return tax, countries, cache


def cmd_validate(args):
    tax, countries, _ = dataset(args.country)
    rows, findings = validate.report(countries, tax)
    print(validate.format_report(rows, findings, tax))
    return 1 if any(r["errors"] for r in rows) else 0


def cmd_status(args):
    """The per-slot table: Country | Category | Photo ID | CDN URL | Status."""
    tax, countries, cache = dataset(args.country)
    cats = [c for c in tax.enabled if not args.category or c["id"] == args.category]
    dupes = cache.duplicates()
    dupe_slots = {s for slots in dupes.values() for s in slots}
    print("%-13s %-19s %-9s %-13s %-44s %s"
          % ("COUNTRY", "CATEGORY", "PROVIDER", "PHOTO ID", "CDN URL", "STATUS"))
    print("-" * 128)
    counts = {}
    for c in countries:
        for cat in cats:
            entry = c.entry(cat["id"])
            slot = cache_mod.key(c.slug, cat["id"])
            if entry is None:
                pid, url, status, prov = "-", "-", "MISSING CATEGORY", "-"
            elif not entry.image:
                pid, url, status = "-", "-", "UNRESOLVED"
                prov = "local" if entry.local else "-"
            else:
                rec = entry.image
                pid = rec.get("photoId") or "?"
                prov = rec.get("provider") or "?"
                try:
                    url = imaging.cdn_url(rec, tax.role(cat["id"]), entry.focal)
                except ValueError:
                    url, status = rec.get("imageUrl", "?"), "INVALID URL"
                else:
                    status = "OK"
                    if slot in dupe_slots:
                        status = "DUPLICATE"
                    elif not rec.get("verifiedAt"):
                        status = "UNVERIFIED"
                    elif not rec.get("photographer"):
                        status = "NO CREDIT"
            if not entry or not entry.caption:
                status = "NO CAPTION"
            elif entry and not validate.alt_text(c, entry):
                status = "NO ALT TEXT"
            counts[status] = counts.get(status, 0) + 1
            print("%-13s %-19s %-9s %-13s %-44s %s"
                  % (c.slug, cat["id"], prov, pid[:13], (url or "-")[:44], status))
    print()
    print("  " + " · ".join("%s: %d" % (k, v) for k, v in sorted(counts.items())))
    if dupes:
        print("\n  duplicate photo ids:")
        for pid, slots in dupes.items():
            print("    %-14s %s" % (pid, ", ".join(slots)))
    return 0 if set(counts) <= {"OK", "UNRESOLVED"} else 1


def cmd_queries(args):
    tax, countries, _ = dataset(args.country)
    for c in countries:
        print("\n# %s" % c.name)
        for cat in tax.enabled:
            if args.category and cat["id"] != args.category:
                continue
            e = c.entry(cat["id"])
            if e:
                print("  %-20s %s" % (cat["id"], queries.build(c, cat, e)))
    return 0


def cmd_resolve(args):
    tax, countries, cache = dataset(args.country)
    cats = [c for c in tax.enabled if not args.category or c["id"] == args.category]
    if args.category and not cats:
        print("no category with id %r in tourism/categories.json" % args.category)
        return 2

    try:
        usable, problems = resolve.preflight(args.provider)
    except resolve.Unavailable as exc:
        print("RESOLVE UNAVAILABLE: %s" % exc)
        print("\nNo URLs were written. This system never stores an image URL it has not "
              "fetched, so unresolved slots stay unresolved rather than becoming "
              "plausible-looking broken links.")
        return 2
    print("providers: %s" % ", ".join(p.name for p in usable))
    for note in problems:
        print("  unavailable — %s" % note)

    # Resumable: everything already cached is skipped, and its photo id is still
    # reserved so a re-run cannot hand the same picture to a different slot.
    seen = set(cache.photo_ids())
    todo = [(c, cat) for c in countries for cat in cats
            if c.entry(cat["id"]) and (args.force or not cache.has(c.slug, cat["id"]))]
    skipped = sum(1 for c in countries for cat in cats
                  if c.entry(cat["id"]) and cache.has(c.slug, cat["id"])) if not args.force else 0
    print("%d slot(s) to resolve, %d already cached and skipped" % (len(todo), skipped))

    filled, failures, by_provider = 0, [], {}
    exhausted = set()
    try:
        for c, cat in todo:
            entry = c.entry(cat["id"])
            try:
                record, err = resolve.resolve_entry(c, cat, entry, tax.role(cat["id"]),
                                                    seen, args.provider, exhausted)
            except resolve.RateLimited as exc:
                print("\n  STOPPED: %s" % exc)
                print("  %d slot(s) still unresolved. Everything resolved so far is "
                      "cached; run again when the window resets." % (len(todo) - filled))
                break
            if record:
                cache.put(c.slug, cat["id"], record)
                entry.image = record
                filled += 1
                by_provider[record["provider"]] = by_provider.get(record["provider"], 0) + 1
                print("  ok    %-14s %-20s %-9s %-12s score %s"
                      % (c.slug, cat["id"], record["provider"], record["photoId"][:12],
                         (record.get("relevance") or {}).get("score")))
            else:
                failures.append((c.slug, cat["id"], err))
                print("  FAIL  %-14s %-20s %s" % (c.slug, cat["id"], err))
    finally:
        # Save whatever was resolved even if the run is interrupted or rate-limited;
        # the next run resumes from here instead of starting over.
        cache.save()

    print("\nresolved %d (%s), failed %d, cache: %s"
          % (filled,
             ", ".join("%s %d" % (k, v) for k, v in sorted(by_provider.items())) or "none",
             len(failures), os.path.relpath(cache.path, ROOT)))
    if failures:
        print("\nfailed slots (these keep their placeholder, nothing was invented):")
        for slug, cid, err in failures:
            print("  %-14s %-20s %s" % (slug, cid, err))
    return 0 if not failures else 1


def cmd_render(args):
    tax, countries, _ = dataset()
    rows, _ = validate.report(countries, tax)
    publishable = {r["slug"] for r in rows if r["publishable"]}
    blocked = [r["slug"] for r in rows if not r["publishable"]]
    for p in render.write_all(countries, tax, publishable):
        print("  wrote %s" % os.path.relpath(p, ROOT))
    if blocked:
        print("  BLOCKED (incomplete, not published): %s" % ", ".join(blocked))
    return 0


def cmd_verify(args):
    tax = load_taxonomy()
    pages, problems = verify.run(tax)
    print("checked %d rendered page(s)" % len(pages))
    if not problems:
        print("no problems: every category rendered, every image sized, boxed and described")
        return 0
    for p in problems[:60]:
        print("  " + p)
    if len(problems) > 60:
        print("  ... %d more" % (len(problems) - 60))
    return 1


def cmd_test(args):
    from tourism import tests
    return tests.main()


def cmd_scaffold(args):
    from tourism.model import COUNTRY_DIR, dump_country
    if not args.country:
        print("scaffold needs --country <slug>")
        return 2
    slug = args.country.strip().lower()
    path = os.path.join(COUNTRY_DIR, slug + ".json")
    if os.path.exists(path):
        print("%s already exists" % os.path.relpath(path, ROOT))
        return 2
    tax = load_taxonomy()
    name = slug.replace("-", " ").title()
    dump_country(path, {
        "slug": slug, "name": name, "adjective": name, "region": "",
        "tagline": "", "summary": "", "published": True,
        "entries": [{"category": c["id"], "caption": "", "description": "",
                     "subject": "", "focal": [50, 50]} for c in tax.enabled],
    })
    print("wrote %s with %d empty categories" % (os.path.relpath(path, ROOT), len(tax.enabled)))
    print("fill in caption/description/subject/focal, then: build.py all")
    return 0


def cmd_report(args):
    tax, countries, cache = dataset()
    rows, findings = validate.report(countries, tax)
    body = validate.format_report(rows, findings, tax)
    total = sum(len([c for c in tax.enabled if co.entry(c["id"])]) for co in countries)
    resolved = sum(1 for co in countries for c in tax.enabled
                   if co.entry(c["id"]) and (co.entry(c["id"]).image or {}).get("imageUrl"))
    path = os.path.join(ROOT, "tourism", "REPORT.md")
    with open(path, "w") as f:
        f.write("# Tourism image system — completeness report\n\n")
        f.write("Generated by `python3 tools/tourism/build.py report`.\n\n")
        by_provider = {}
        for co in countries:
            for c in tax.enabled:
                e = co.entry(c["id"])
                if e and e.image and e.image.get("provider"):
                    by_provider[e.image["provider"]] = by_provider.get(e.image["provider"], 0) + 1
        f.write("- Countries: **%d**\n- Categories per country: **%d**\n"
                "- Assignments: **%d**\n- Images resolved: **%d / %d**%s\n\n"
                % (len(countries), len(tax.enabled), total, resolved, total,
                   ("  (" + ", ".join("%s %d" % kv for kv in sorted(by_provider.items())) + ")")
                   if by_provider else ""))
        if resolved < total:
            f.write("> %s\n\n" % resolve.MISSING_KEY_WARNING)
        f.write("```\n%s\n```\n" % body)
    print("wrote %s" % os.path.relpath(path, ROOT))
    print(body)
    return 0


def cmd_providers(args):
    """The country x provider report."""
    tax, countries, cache = dataset(args.country)
    rows, _ = validate.report(countries, tax)
    expected = len(tax.enabled)
    dupes = cache.duplicates()
    total = {"resolved": 0, "unresolved": 0}
    for r in rows:
        country = [c for c in countries if c.slug == r["slug"]][0]
        resolved = sum(r["providers"].values())
        unresolved = expected - resolved
        local = sum(1 for c in tax.enabled
                    if country.entry(c["id"]) and not country.entry(c["id"]).image
                    and country.entry(c["id"]).local)
        dup_here = sum(1 for pid, slots in dupes.items()
                       for s in slots if s.startswith(r["slug"] + "/"))
        total["resolved"] += resolved
        total["unresolved"] += unresolved
        print("\n%s" % r["name"].upper())
        print("  %d/%d resolved" % (resolved, expected))
        for name in sorted(providers.BY_NAME):
            print("  %d %s" % (r["providers"].get(name, 0), name.title()))
        print("  %d unresolved (%d showing a local illustration)" % (unresolved, local))
        print("  %d duplicates" % dup_here)
    print("\nTOTAL  %d resolved, %d unresolved across %d countries"
          % (total["resolved"], total["unresolved"], len(rows)))
    return 0


def cmd_all(args):
    rc = cmd_validate(args)
    print()
    cmd_render(args)
    print()
    rc = cmd_verify(args) or rc
    cmd_report(args)
    return rc


COMMANDS = {
    "validate": cmd_validate, "status": cmd_status, "queries": cmd_queries,
    "providers": cmd_providers,
    "resolve": cmd_resolve, "render": cmd_render, "verify": cmd_verify,
    "test": cmd_test, "scaffold": cmd_scaffold, "report": cmd_report, "all": cmd_all,
}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("--country", help="limit to one country slug")
    p.add_argument("--category", help="limit to one category id")
    p.add_argument("--provider", help="limit to one provider (unsplash, pexels)")
    p.add_argument("--force", action="store_true",
                   help="re-resolve slots that are already cached")
    args = p.parse_args()
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
