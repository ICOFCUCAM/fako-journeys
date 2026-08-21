#!/usr/bin/env python3
"""Every published page, what it is, and whether it goes anywhere.

    python3 tools/page-inventory.py            the report
    python3 tools/page-inventory.py --check    fail if a page is stranded

COMMIT 02 OF THE 50-COMMIT INTEGRATION MANDATE.

PUBLISHED IS NOT THE SAME AS PRESENT, AND AN AUDIT THAT CONFUSES THEM CRIES
WOLF FOREVER.

The first pass of this inventory reported `tourism/compare.html` as a page with
no shell, no inbound link and no next action — an internal contact sheet of
image candidates, apparently deployed where anybody could reach it. It is
already in `.vercelignore` and has never been deployed at all. The finding was
about the repository, and the question was about the website.

So this reads `.vercelignore` first. Anything excluded from the deploy is
counted as a working artefact and held apart, because an auditor that reports
the same false positive every quarter is one that gets ignored on the quarter
it is right.

WHAT IT ASKS OF A PUBLISHED PAGE

    family      does it say what kind of page it is (body class af--<family>)
    shell       is it on the one global masthead
    inbound     can a visitor arrive at it from anywhere on the site
    onward      does <main> offer at least two ways to continue

The last is the one the mandate cares about most: "pages with no meaningful
next action". A page that a visitor can reach and cannot leave except by the
navigation is a dead end in a product whose whole proposition is a journey
from inspiration to intention.

TWO OUTBOUND LINKS, NOT ONE, IS THE THRESHOLD, AND IT IS A JUDGEMENT.
One link is frequently a breadcrumb or a lone credit; two is the point at which
a page is actually offering the reader a choice. The operator's own pages are
held to a lower bar and named as an exception rather than silently skipped —
they carry their own navigation and belong to a different company.
"""

import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", "incoming", ".vercel"}

# The operator's pages are a different company's surface with its own
# navigation. Named here so the exception is visible rather than a silent skip.
OPERATOR_PAGES = {"about.html", "contact.html", "pricing.html",
                  "services.html", "cameroon.html"}


def excluded():
    """Paths `.vercelignore` keeps out of the deploy."""
    path = os.path.join(ROOT, ".vercelignore")
    out = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line.rstrip("/"))
    return out


def is_published(rel, rules):
    for r in rules:
        if rel == r or rel.startswith(r + "/"):
            return False
    return True


def pages():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d[0] != "."]
        for name in sorted(filenames):
            if name.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    return sorted(out)


def url_of(rel):
    url = "/" + rel[:-5]
    if url.endswith("/index"):
        url = url[: -len("/index")] or "/"
    return url.rstrip("/") or "/"


def main():
    rules = excluded()
    all_pages = pages()
    published = [p for p in all_pages if is_published(p, rules)]
    artefacts = [p for p in all_pages if not is_published(p, rules)]

    html = {}
    for p in published:
        with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as fh:
            html[p] = fh.read()

    inbound = Counter()
    for p, h in html.items():
        for href in set(re.findall(r'href="(/[^"#?]*)"', h)):
            inbound[href.rstrip("/") or "/"] += 1

    fams = defaultdict(list)
    noshell, stranded, dead_end = [], [], []
    for p, h in html.items():
        m = re.search(r'<body[^>]*class="([^"]*)"', h)
        fam = re.search(r"\baf--([a-z]+)", m.group(1)) if m else None
        fams[fam.group(1) if fam else "NONE"].append(p)
        if "af-shell" not in h:
            noshell.append(p)
        if inbound[url_of(p)] == 0 and p != "404.html":
            stranded.append(p)
        main_m = re.search(r"<main.*?</main>", h, re.S)
        links = set(re.findall(r'href="(/[^"#]*)"', main_m.group(0) if main_m else ""))
        if len(links) < 2 and os.path.basename(p) not in OPERATOR_PAGES:
            dead_end.append((p, len(links)))

    if "--check" in sys.argv:
        bad = 0
        for label, items in (("no shell", noshell),
                             ("no inbound link", stranded),
                             ("no way onward from <main>", [d[0] for d in dead_end]),
                             ("no declared family", fams.get("NONE", []))):
            if items:
                bad += len(items)
                print("FAIL\t%s\t%d page(s): %s"
                      % (label, len(items), ", ".join(sorted(items)[:6])))
            else:
                print("PASS\t%s\tnone of %d published pages"
                      % (label, len(published)))
        print("\n%d published page(s), %d working artefact(s) excluded from the "
              "deploy" % (len(published), len(artefacts)))
        sys.exit(1 if bad else 0)

    w = print
    w("# The page inventory")
    w("")
    w("**GENERATED.** `python3 tools/page-inventory.py > docs/page-inventory.md`")
    w("")
    w("**Published is not the same as present.** `.vercelignore` keeps %d file(s)"
      % len(artefacts))
    w("out of the deploy; they are working artefacts and are held apart here. The")
    w("first version of this audit reported `tourism/compare.html` — an internal")
    w("sheet of image candidates — as an unreachable public page. It has never")
    w("been deployed. An auditor that reports the same false positive every")
    w("quarter is one that gets ignored on the quarter it is right.")
    w("")
    w("## Published pages by family")
    w("")
    w("| family | pages |")
    w("|---|---|")
    for k in sorted(fams, key=lambda k: -len(fams[k])):
        w("| `%s` | %d |" % (k, len(fams[k])))
    w("| **total** | **%d** |" % len(published))
    w("")
    w("## Working artefacts, not published")
    w("")
    for a in artefacts:
        w("- `%s`" % a)
    if not artefacts:
        w("None.")
    w("")
    w("## Stranded, dead-ended or undeclared")
    w("")
    w("| condition | pages |")
    w("|---|---|")
    w("| not on the global shell | %s |"
      % (", ".join("`%s`" % x for x in noshell) or "none"))
    w("| no inbound link from anywhere | %s |"
      % (", ".join("`%s`" % x for x in stranded) or "none"))
    w("| fewer than two ways onward from `<main>` | %s |"
      % (", ".join("`%s` (%d)" % (p, n) for p, n in dead_end) or "none"))
    w("| no declared family | %s |"
      % (", ".join("`%s`" % x for x in fams.get("NONE", [])) or "none"))
    w("")
    w("The operator's own pages — %s — are exempt from the onward test: they"
      % ", ".join("`%s`" % x for x in sorted(OPERATOR_PAGES)))
    w("are a different company's surface and carry their own navigation.")
    w("")


if __name__ == "__main__":
    main()
