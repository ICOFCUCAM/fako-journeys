#!/usr/bin/env python3
"""Tourism image system — command line.

    build.py validate            completeness + integrity report for every country
    build.py status              Country | Category | Photo ID | CDN URL | Status
    build.py queries             the search query for every slot
    build.py resolve             fill image slots from Unsplash, then Pexels
    build.py render              write tourism/<slug>.html
    build.py verify              check the rendered HTML
    build.py test                run the resolver test suite against a local mock
    build.py adopt               put resolved photographs on the five main pages
    build.py placements          every image slot on the site, and what belongs in it
    build.py prompts             the generation instruction for each of those slots
    build.py generate            make candidate images from them
    build.py intake              read incoming/ and propose a slot for each upload
    build.py compare             contact sheet: every candidate for every slot
    build.py place               put chosen candidates into their slots
    build.py optimise            resize and re-encode the placed images
    build.py homes               a standalone home page per country
    build.py cut <file|url>      cut one raw clip down to what the window can carry
    build.py film <file|url>     cut a whole film into the window's pieces
    build.py scaffold            create a new country with 27 empty slots
    build.py geo                 outlines and distances, from the map itself
    build.py grade               measure images against images/STANDARD.md
    build.py sizes               give placed photographs their own dimensions
    build.py audit               does the photograph show what the page says
    build.py enquire             /enquire, where a built journey actually arrives
    build.py wonders             /wonders, the whole collection
    build.py transafrique        /trans-afrique, the expedition
    build.py company             the legal entity, into every Afrinkong-side footer
    build.py gateway             rewrite the gateway's country lists from the dataset
    build.py sidebyside          write /compare.html — two countries, same questions
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
from tourism import cut as cut_mod  # noqa: E402
from tourism import imaging, providers, queries, render, resolve, validate, verify  # noqa: E402
from tourism.model import ROOT, attach_cache, load_countries, load_taxonomy  # noqa: E402


def dataset(country=None):
    """Every country, with resolved images bound on from the cache."""
    tax = load_taxonomy()
    cache = cache_mod.load()
    countries = attach_cache(load_countries(), cache, tax)
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
    # What each country has already been given, one word-bag per filled slot, so
    # the ranker can score down a sixth photograph of the same animal. Seeded
    # from the cache, because a resumed run has to know what the first run took.
    # `from tourism import`, not `from . import`. This file is executed as a
    # script — sys.path gets the parent directory at line 36 and every other
    # import in it is absolute — so a relative import here has no parent package
    # and raises ImportError at the moment the resolver starts filling slots.
    # It ran to 54 of 594 on cached entries and threw on the first uncached one.
    from tourism import relevance as _rel
    taken = {}
    for c in countries:
        bags = []
        for cat in cats:
            rec = cache.get(c.slug, cat["id"])
            if rec and rec.get("imageUrl"):
                bags.append(_rel.words(rec.get("alt") or rec.get("description") or ""))
        taken[c.slug] = bags
    try:
        for c, cat in todo:
            entry = c.entry(cat["id"])
            try:
                record, err = resolve.resolve_entry(c, cat, entry, tax.role(cat["id"]),
                                                    seen, args.provider, exhausted,
                                                    taken.get(c.slug))
            except resolve.RateLimited as exc:
                print("\n  STOPPED: %s" % exc)
                print("  %d slot(s) still unresolved. Everything resolved so far is "
                      "cached; run again when the window resets." % (len(todo) - filled))
                break
            if record:
                cache.put(c.slug, cat["id"], record)
                entry.image = record
                taken.setdefault(c.slug, []).append(
                    _rel.words(record.get("alt") or record.get("description") or ""))
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


def cmd_adopt(args):
    """Put the resolved photographs onto the five hand-written pages."""
    from tourism import adopt
    r = adopt.run(args.country or "cameroon", revert=args.revert)
    for page, changed in r["pages"]:
        print("  %-16s %d image(s) rewritten" % (page, changed))
    if args.revert:
        print("\nreverted %d slot(s) to their illustrations, "
              "left %d locked slot(s) alone" % (r["reverted"], r["locked"]))
    else:
        print("\nadopted %d photograph(s), kept %d illustration(s), "
              "left %d locked slot(s) alone" % (r["adopted"], r["kept"], r["locked"]))
        if r["missing"]:
            print("no resolved photo for: %s" % ", ".join(r["missing"]))
    return 0


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


def cmd_audit(args):
    """Check every resolved photograph against what the provider says it shows."""
    from tourism import audit
    found = audit.run(only=(args.country or "").strip().lower() or None,
                      force=bool(args.force))
    return 1 if sum(len(v) for v in found.values()) else 0


def cmd_enquire(args):
    """Afrinkong's own enquiry page, so a journey stops landing on Kamerun's."""
    from tourism import enquire
    enquire.run()
    return 0


def cmd_twoways(args):
    """The fork: a country priced per day, a crossing priced whole."""
    from tourism import twoways
    twoways.run()
    return 0


def cmd_wonders(args):
    """The Wonders of Africa, all of them, by strand."""
    from tourism import wonders
    from tourism.model import load_countries
    wonders.run([c for c in load_countries() if c.published])
    return 0


def cmd_transafrique(args):
    """Trans Afrique, the expedition page."""
    from tourism import transafrique
    from tourism.model import load_countries
    transafrique.run([c for c in load_countries() if c.published])
    return 0


def cmd_company(args):
    """Write the legal entity into the footers that name it."""
    from tourism import company
    company.run()
    return 0


def cmd_sizes(args):
    """Backfill width/height on placed photographs that were written without."""
    from tourism import place as place_mod
    place_mod.backfill_sizes()
    return 0


def cmd_grade(args):
    """Measure images against images/STANDARD.md. Paths on stdin, or all placed."""
    import subprocess
    from tourism import grade
    # Empty stdin means "all of them", not "none of them". isatty() alone said
    # none whenever the command was run with input redirected, which is how it
    # gets run from a script — so it printed a header and nothing under it.
    paths = [] if sys.stdin.isatty() else [l.strip() for l in sys.stdin if l.strip()]
    if not paths:
        out = subprocess.run(
            ["grep", "-rhoE", r"/images/[A-Za-z0-9._/-]+\.(jpg|jpeg|png|webp|avif)",
             "--include=*.html", "--include=*.json", "."],
            capture_output=True, text=True, cwd=ROOT)
        paths = sorted(set(out.stdout.split()))
        print("measuring every placed image (%d)\n" % len(paths))
    grade.main(paths)
    return 0


def cmd_geo(args):
    """The outlines and the distance table, from geometry the site already has."""
    from tourism import atlas_geo
    problems = atlas_geo.run(check=bool(getattr(args, "describe", False)))
    return 1 if problems else 0


def cmd_sidebyside(args):
    from tourism import sidebyside
    tax, countries, _cache = dataset()
    sidebyside.run(countries, tax)
    return 0


def cmd_atlas(args):
    """The living atlas: /atlas, plus one places payload per country."""
    from tourism import atlas
    tax, countries, _cache = dataset()
    atlas.run(countries, tax)
    return 0


def cmd_places(args):
    """A real page for every place, plus /places and sitemap.xml."""
    from tourism import places
    tax, countries, _cache = dataset()
    places.run(countries, tax)
    return 0


def cmd_links(args):
    """What borders what, and what else connects it."""
    from tourism import atlas, links
    _tax, countries, _cache = dataset()
    links.run(countries, atlas.load_lenses())
    return 0


def cmd_graph(args):
    """The story graph: every proper name in the dataset, and where it is said."""
    from tourism import graph
    tax, countries, _cache = dataset()
    graph.run(countries, tax)
    return 0


def cmd_story(args):
    """The living story engine: /portrait/<country> and /stories."""
    from tourism import story
    tax, countries, _cache = dataset()
    story.run(countries, tax)
    return 0


def cmd_meet(args):
    """The human layer: /meet."""
    from tourism import meet
    tax, countries, _cache = dataset()
    meet.run(countries, tax)
    return 0


def cmd_journey(args):
    """The journey engine: /journey."""
    from tourism import journey
    tax, countries, _cache = dataset()
    journey.run(countries, tax)
    return 0


def cmd_gateway(args):
    from tourism import gateway
    _tax, countries, _cache = dataset()
    gateway.run(countries)
    return 0


def cmd_enquiry(args):
    from tourism import enquiry
    _tax, countries, _cache = dataset()
    enquiry.run(countries)
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


def _one_country(args, default="cameroon"):
    """The generation commands work against one country's site pages."""
    _tax, countries, _cache = dataset(args.country or default)
    return countries[0]


def cmd_placements(args):
    """Every image slot on the five hand-written pages, and what belongs in it."""
    from tourism import placements as pl
    tax, countries, _cache = dataset(args.country or "cameroon")
    country = countries[0]
    rows = pl.scan(country)
    page = None
    for p in rows:
        if p["page"] != page:
            page = p["page"]
            print("\n# %s" % page)
        flag = "  [LOCKED]" if p["locked"] else ("" if p["category"] else "  [no category]")
        print("  %-26s %-14s %d:%d%s" % (p["id"], p["wrapper"] or "default",
                                         p["aspect"][0], p["aspect"][1], flag))
        print("      %s" % (p["instruction"] or "(no instruction — slot has no alt text)"))
    s = pl.summarise(rows)
    print("\n%d slot(s): %d targetable, %d locked, %d with no category"
          % (s["total"], s["targetable"], s["locked"], s["uncategorised"]))
    print("shapes in use: %s" % ", ".join(s["shapes"]))
    dupes = pl.duplicates(rows)
    if dupes:
        print("\nthe same illustration fills more than one slot — each gets its own "
              "picture, cut for its own shape:")
        for slot_id, items in sorted(dupes.items()):
            print("  %-26s %s" % (slot_id, ", ".join("%s %d:%d" % (i["page"], i["aspect"][0],
                                                                   i["aspect"][1])
                                                     for i in items)))
    return 0


def cmd_prompts(args):
    """The generation instruction for every slot. Read before spending money."""
    from tourism import candidates as pool, generate as gen, prompting
    tax, countries, _cache = dataset(args.country or "cameroon")
    country = countries[0]
    style = prompting.load_style()
    jobs = gen.plan_jobs(country, tax, pool.load(), style, args.scope, args.only)
    for j in jobs:
        print("\n%s  [%s]  ->  %s" % (j.label, j.size, j.where))
        print("  %s" % j.prompt)
    print("\n%d instruction(s). Nothing was sent; this is what would be." % len(jobs))
    return 0


def cmd_generate(args):
    """Make candidate images from those instructions."""
    from tourism import generate as gen
    tax, countries, _cache = dataset(args.country or "cameroon")
    country = countries[0]
    try:
        summary = gen.run(country, tax, scope=args.scope, only=args.only,
                          n=args.n, dry_run=args.dry_run, force=args.force)
    except gen.Unavailable as exc:
        print("GENERATION UNAVAILABLE: %s" % exc)
        print("\nSet OPENAI_API_KEY, or run with --dry-run to see the instructions "
              "without sending anything.")
        return 2
    except gen.RateLimited as exc:
        print("\nSTOPPED: %s" % exc)
        print("Everything generated so far is saved. Run again to continue.")
        return 1
    return 0 if not summary.get("failed") else 1


def cmd_intake(args):
    """Read uploaded images and propose a slot for each."""
    from tourism import intake
    tax, countries, _cache = dataset(args.country or "cameroon")
    directory = args.source_dir
    if not os.path.isabs(directory):
        directory = os.path.join(ROOT, directory)
    try:
        intake.run(countries[0], tax, directory=directory,
                   do_describe=args.describe, dry_run=args.dry_run)
    except intake.Unavailable as exc:
        print("INTAKE: %s" % exc)
        print("\nRun without --describe to match on shape and filename alone.")
        return 2
    except intake.RateLimited as exc:
        print("\nSTOPPED: %s" % exc)
        return 1
    return 0


def cmd_compare(args):
    """Write the contact sheet."""
    from tourism import compare
    tax, countries, cache = dataset(args.country or "cameroon")
    counts, path = compare.build(countries[0], tax, cache)
    print("wrote %s" % os.path.relpath(path, ROOT))
    print("%d slot(s), %d generated candidate(s), %d slot(s) with none yet"
          % (counts["slots"], counts["generated"], counts["empty"]))
    print("open it, pick one per slot, download picks.json, then: build.py place picks.json")
    return 0


def cmd_homes(args):
    """Write a standalone home page for every country but Cameroon."""
    from tourism import home
    tax, countries, _cache = dataset(args.country)
    written = home.write_all(countries, tax)
    print("\n%d country home page(s)" % len(written))
    return 0


def cmd_optimise(args):
    """Resize and re-encode the placed images so the site is deliverable."""
    from tourism import optimise
    country = _one_country(args)
    summary = optimise.run(country, dry_run=args.dry_run)
    return 0 if summary.get("available") else 2


def cmd_place(args):
    """Put chosen candidates into the slots they were generated for."""
    from tourism import place
    country = _one_country(args)
    picks = {}
    if not args.revert:
        if not args.picks:
            print("place needs a picks.json — download one from the contact sheet "
                  "(build.py compare), or pass --revert to undo.")
            return 2
        picks = place.load_picks(args.picks)
    report = place.run(picks, country, revert=args.revert, dry_run=args.dry_run)
    for err in report["errors"]:
        print("  error: %s" % err)
    if report["errors"]:
        print("\nnothing was written — fix the picks file and run again.")
        return 2
    for page, changed in report["pages"]:
        print("  %-16s %d image(s) rewritten" % (page, changed))
    if args.revert:
        print("\nreverted %d placed slot(s) to their illustrations" % report["reverted"])
        if report["reverted"]:
            print("run `adopt` to put resolved stock photographs back where there "
                  "were any — that pair is a byte-identical round trip.")
    else:
        print("\nplaced %d image(s), left %d slot(s) as they were, "
              "%d locked slot(s) alone" % (report["placed"], report["skipped"],
                                           report["locked"]))
        if args.dry_run:
            print("dry run: no page and no file was written.")
    return 0


def cmd_all(args):
    """Everything that turns the dataset into pages, in dependency order.

    `homes` and `gateway` are part of this and not an afterthought: a resolve
    run that fills the cache and leaves the country pages and the gateway
    showing what was there before is a run that did nothing a visitor can see.
    """
    # geo first, and before validate reads anything: a country added to
    # tourism/countries/ has no outline, no view box, no distances and is still
    # drawn as part of the map's scenery until this runs. Leaving it as a
    # separate command meant "drop a JSON file in and run all", which is what
    # this file's own docstring promises, quietly produced a country that was on
    # every list and unreachable on the map. Deriving is cheap and idempotent —
    # it fills gaps and rewrites nothing that is already there.
    cmd_geo(args)
    print()
    rc = cmd_validate(args)
    print()
    cmd_render(args)
    print()
    cmd_homes(args)
    print()
    cmd_gateway(args)
    print()
    cmd_enquiry(args)
    print()
    cmd_atlas(args)
    print()
    cmd_journey(args)
    print()
    cmd_meet(args)
    print()
    cmd_links(args)
    print()
    cmd_places(args)
    print()
    cmd_graph(args)
    print()
    cmd_story(args)
    print()
    cmd_sidebyside(args)
    print()
    rc = cmd_verify(args) or rc
    cmd_report(args)
    return rc


def cmd_footage(args):
    """Stage candidate clips from Pexels in incoming/video/. Places none of them.

    `footage` rather than `resolve` on purpose. The image resolver picks a
    photograph and files it against a slot; this one cannot, because keyword
    search knows what a clip was tagged with and not where it was shot, and the
    window under the hero captions its shots with places. Somebody looks at the
    file and decides. See tools/tourism/footage.py.
    """
    from tourism import footage
    qs = [q.strip() for q in (args.query or "").split(",") if q.strip()]
    if args.list_only or not qs:
        led = footage.ledger()
        if not led["clips"]:
            print("nothing staged. Try: build.py footage --query \"aerial lagos\"")
            return 0
        print("%-34s %-26s %-11s %s" % ("QUERY", "FILE", "SIZE", "WHERE"))
        for c in led["clips"]:
            print("%-34s %-26s %-11s %s"
                  % (c.get("query", "")[:34],
                     (c.get("file") or "").rsplit("/", 1)[-1][:26],
                     "%dx%d %ds" % (c.get("width") or 0, c.get("height") or 0,
                                    c.get("seconds") or 0),
                     c.get("where") or "unknown — not placeable until known"))
        return 0
    return 0 if footage.run(qs, want=max(1, args.n)) >= 0 else 1


def cmd_cut(args):
    """Cut one raw clip down to something the homepage can afford to serve.

    The master is not meant to survive this. Git keeps every binary forever, so
    a 25 MB original committed once costs 25 MB in every clone and every deploy
    from then on, in exchange for the two megabytes that are actually served —
    which is also why `--from-url` exists. See tools/tourism/cut.py.
    """
    src = args.picks
    if not src:
        print("cut needs a source: a path under incoming/video/, or a URL.\n"
              "  build.py cut incoming/video/lagos.mp4 --name city-lagos-marina\n"
              "  build.py cut https://github.com/<owner>/<repo>/releases/download/"
              "footage/lagos.mp4 --name city-lagos-marina")
        return 2
    if not args.name:
        print("cut needs --name: the file it writes into videos/, and the value "
              "that goes in \"clip\" on a shot in tourism/motion.json.")
        return 2
    if src.startswith("http://") or src.startswith("https://"):
        into = os.path.join(cut_mod.MASTERS,
                            os.path.basename(src.split("?")[0]) or "master.mp4")
        print("fetching the master to %s — gitignored, so it never enters the "
              "history" % os.path.relpath(into, ROOT))
        src = cut_mod.fetch(src, into)
    if not os.path.exists(src):
        print("no such file: %s" % src)
        return 2
    cut_mod.cut(src, args.name, seconds=args.seconds, start=args.start,
                width=args.width, mb=args.mb, keep_audio=args.keep_audio)
    return 0


def cmd_film(args):
    """Cut one supplied film into the pieces the window can carry, and place them.

    `cut` takes one excerpt. This takes the whole thing: sixteen consecutive
    pieces on the film's own scene boundaries, covering it end to end with
    nothing dropped and nothing repeated. See tools/tourism/film.py for why the
    boundaries are a table rather than an eight-second stride.
    """
    from tourism import film
    if args.list_only:
        print("%-3s %-7s %-7s %-6s %s" % ("#", "FROM", "TO", "LEN", "CAPTION"))
        for i, (a, b, _slug, say, _alt) in enumerate(film.PIECES):
            print("%-3d %-7.2f %-7.2f %-6.2f %s" % (i + 1, a, b, b - a, say))
        gaps = film.covers()
        print("\n%d pieces, %.2fs in total%s"
              % (len(film.PIECES), film.PIECES[-1][1] - film.PIECES[0][0],
                 "" if not gaps else " — BUT THEY DO NOT JOIN: " + "; ".join(gaps)))
        return 1 if gaps else 0
    src = args.picks
    if not src:
        print("film needs the master: a path, or a URL to fetch it from.")
        return 2
    if src.startswith("http://") or src.startswith("https://"):
        into = os.path.join(cut_mod.MASTERS,
                            os.path.basename(src.split("?")[0]) or "master.mp4")
        print("fetching the master to %s — gitignored, so it never enters the "
              "history" % os.path.relpath(into, ROOT))
        src = cut_mod.fetch(src, into)
    if not os.path.exists(src):
        print("no such file: %s" % src)
        return 2
    film.place(film.run(src, mb=args.mb if args.mb != cut_mod.MB else film.MB,
                        keep_audio=args.keep_audio))
    print("now run: python3 tools/tourism/build.py gateway")
    return 0


COMMANDS = {
    "validate": cmd_validate, "status": cmd_status, "queries": cmd_queries,
    "providers": cmd_providers,
    "resolve": cmd_resolve, "render": cmd_render, "verify": cmd_verify,
    "test": cmd_test, "scaffold": cmd_scaffold, "report": cmd_report,
    "company": cmd_company, "audit": cmd_audit, "enquire": cmd_enquire, "wonders": cmd_wonders, "transafrique": cmd_transafrique, "twoways": cmd_twoways,
    "geo": cmd_geo, "grade": cmd_grade, "sizes": cmd_sizes, "gateway": cmd_gateway, "enquiry": cmd_enquiry, "sidebyside": cmd_sidebyside, "atlas": cmd_atlas, "journey": cmd_journey, "meet": cmd_meet, "links": cmd_links, "places": cmd_places,
    "graph": cmd_graph, "story": cmd_story,
    "adopt": cmd_adopt, "all": cmd_all,
    "placements": cmd_placements, "prompts": cmd_prompts, "generate": cmd_generate,
    "compare": cmd_compare, "place": cmd_place, "intake": cmd_intake,
    "optimise": cmd_optimise, "homes": cmd_homes,
    "footage": cmd_footage, "cut": cmd_cut, "film": cmd_film,
}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("--country", help="limit to one country slug")
    p.add_argument("--category", help="limit to one category id")
    p.add_argument("--provider", help="limit to one provider (unsplash, pexels)")
    p.add_argument("--revert", action="store_true",
                   help="adopt: put the illustrations back")
    p.add_argument("--force", action="store_true",
                   help="re-resolve slots that are already cached")
    # generation and intake
    p.add_argument("--scope", choices=("site", "tourism", "all"), default="site",
                   help="site: the five hand-written pages (default). "
                        "tourism: the generated country page. all: both")
    p.add_argument("--only", help="one slot id, page or category")
    p.add_argument("-n", type=int, default=1,
                   help="candidates to generate per slot (default 1)")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would happen; send nothing, write nothing")
    p.add_argument("--from", dest="source_dir", default="incoming",
                   help="intake: the folder of uploaded images (default incoming/)")
    p.add_argument("--describe", action="store_true",
                   help="intake: ask the vision model what each upload shows")
    p.add_argument("--query", help="footage: comma-separated search terms")
    p.add_argument("--list", dest="list_only", action="store_true",
                   help="footage: show what is already staged")
    # cut
    p.add_argument("--name", help="cut: what to call the result in videos/, "
                                  "without the .mp4")
    p.add_argument("--seconds", type=float, default=cut_mod.SECONDS,
                   help="cut: how much to keep (default %g)" % cut_mod.SECONDS)
    p.add_argument("--start", type=float, default=0.0,
                   help="cut: where in the master to start, in seconds")
    p.add_argument("--width", type=int, default=cut_mod.WIDTH,
                   help="cut: output width in pixels (default %d)" % cut_mod.WIDTH)
    p.add_argument("--keep-audio", dest="keep_audio", action="store_true",
                   help="cut/film: keep the audio track. Off by default — the "
                        "window plays muted. See images/VIDEO.md on narration")
    p.add_argument("--mb", type=float, default=cut_mod.MB,
                   help="cut: the ceiling the result has to come in under "
                        "(default %g)" % cut_mod.MB)
    p.add_argument("picks", nargs="?",
                   help="place: the picks.json to apply. cut: the clip to cut, "
                        "as a path or a URL")
    args = p.parse_args()
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
