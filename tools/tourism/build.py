#!/usr/bin/env python3
"""Tourism image system — command line.

    python3 tools/tourism/build.py validate     completeness report for every country
    python3 tools/tourism/build.py queries      the search query for every slot
    python3 tools/tourism/build.py resolve      fill image slots from Unsplash (needs a key)
    python3 tools/tourism/build.py render       write tourism/<slug>.html
    python3 tools/tourism/build.py all          validate, then render what passed
    python3 tools/tourism/build.py report       write tourism/REPORT.md

Adding a country: drop a JSON file in tourism/countries/ and run `all`. No code
changes, no new components, no template edits.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tourism import queries, render, resolve, validate, verify  # noqa: E402
from tourism.model import ROOT, load_countries, load_taxonomy  # noqa: E402


def cmd_validate(args):
    tax = load_taxonomy()
    countries = load_countries()
    rows, findings = validate.report(countries, tax)
    print(validate.format_report(rows, findings, tax))
    return 1 if any(r["errors"] for r in rows) else 0


def cmd_queries(args):
    tax = load_taxonomy()
    for c in load_countries():
        if args.country and c.slug != args.country:
            continue
        print("\n# %s" % c.name)
        for cat in tax.enabled:
            e = c.entry(cat["id"])
            if e:
                print("  %-20s %s" % (cat["id"], queries.build(c, cat, e)))
    return 0


def cmd_resolve(args):
    tax = load_taxonomy()
    countries = [c for c in load_countries() if not args.country or c.slug == args.country]
    try:
        key = resolve.preflight()
    except resolve.Unavailable as exc:
        print("RESOLVE UNAVAILABLE: %s" % exc)
        print("\nNo URLs were written. This system never stores an image URL it has "
              "not fetched, so unresolved slots stay unresolved rather than becoming "
              "plausible-looking broken links.")
        return 2
    seen = set()
    for c in countries:
        for cat in tax.enabled:
            e = c.entry(cat["id"])
            if e and e.image and not args.recheck:
                seen.add(e.image.get("id"))
    filled = failed = 0
    for c in countries:
        for cat in tax.enabled:
            e = c.entry(cat["id"])
            if not e or (e.image and not args.recheck):
                continue
            role = tax.role(cat["id"])
            record, err = resolve.resolve_entry(c, cat, e, role, key, seen)
            if record:
                import datetime
                record["verifiedAt"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                e.image = record
                filled += 1
                print("  ok    %-14s %-20s %s" % (c.slug, cat["id"], record["id"]))
            else:
                failed += 1
                print("  FAIL  %-14s %-20s %s" % (c.slug, cat["id"], err))
        resolve.write_country(c)
    print("\nresolved %d, failed %d" % (filled, failed))
    return 0 if not failed else 1


def cmd_render(args):
    tax = load_taxonomy()
    countries = load_countries()
    rows, _ = validate.report(countries, tax)
    publishable = {r["slug"] for r in rows if r["publishable"]}
    blocked = [r["slug"] for r in rows if not r["publishable"]]
    written = render.write_all(countries, tax, publishable)
    for p in written:
        print("  wrote %s" % os.path.relpath(p, ROOT))
    if blocked:
        print("  BLOCKED (incomplete, not published): %s" % ", ".join(blocked))
    return 0


def cmd_scaffold(args):
    """Create a complete 27-entry skeleton for a new country.

    This is the answer to "adding a country must not mean writing 27 components":
    the structure is generated, and whoever adds the country only fills in copy.
    """
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
    raw = {
        "slug": slug, "name": name, "adjective": name, "region": "",
        "tagline": "", "summary": "", "published": True,
        "entries": [
            {"category": c["id"],
             "caption": "", "description": "", "subject": "",
             "focal": [50, 50]}
            for c in tax.enabled
        ],
    }
    dump_country(path, raw)
    print("wrote %s with %d empty categories" % (os.path.relpath(path, ROOT), len(tax.enabled)))
    print("fill in caption/description/subject/focal, then: build.py all")
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


def cmd_report(args):
    tax = load_taxonomy()
    countries = load_countries()
    rows, findings = validate.report(countries, tax)
    body = validate.format_report(rows, findings, tax)
    total_assignments = sum(len([c for c in tax.enabled if co.entry(c["id"])]) for co in countries)
    resolved = sum(
        1 for co in countries for c in tax.enabled
        if co.entry(c["id"]) and (co.entry(c["id"]).image or {}).get("url")
    )
    path = os.path.join(ROOT, "tourism", "REPORT.md")
    with open(path, "w") as f:
        f.write("# Tourism image system — completeness report\n\n")
        f.write("Generated by `python3 tools/tourism/build.py report`.\n\n")
        f.write("- Countries: **%d**\n- Categories per country: **%d**\n"
                "- Assignments: **%d**\n- Images resolved from Unsplash: **%d / %d**\n\n"
                % (len(countries), len(tax.enabled), total_assignments, resolved, total_assignments))
        f.write("```\n%s\n```\n" % body)
    print("wrote %s" % os.path.relpath(path, ROOT))
    print(body)
    return 0


def cmd_all(args):
    rc = cmd_validate(args)
    print()
    cmd_render(args)
    print()
    rc = cmd_verify(args) or rc
    cmd_report(args)
    return rc


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["validate", "queries", "resolve", "render", "verify",
                                       "report", "scaffold", "all"])
    p.add_argument("--country", help="limit to one slug")
    p.add_argument("--recheck", action="store_true", help="re-resolve slots that already have an image")
    args = p.parse_args()
    return {"validate": cmd_validate, "queries": cmd_queries, "resolve": cmd_resolve,
            "render": cmd_render, "verify": cmd_verify, "report": cmd_report,
            "scaffold": cmd_scaffold, "all": cmd_all}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
