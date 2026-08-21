#!/usr/bin/env python3
"""The authoritative system map — measured, never asserted.

    python3 tools/system-map.py > docs/system-map.md

COMMIT 01 OF THE 50-COMMIT INTEGRATION MANDATE.

WHY THIS IS A GENERATOR AND NOT A DOCUMENT.

This repository's characteristic failure is two things that had to agree with
nothing comparing them: a sentence beside a generated block, a check pinned to
a class name, a masthead breakpoint hand-edited into a generated file, a
navigation present in the markup of 1,597 pages and visible on none. A
hand-written system map is that failure in its purest form — it is correct on
the day it is written and silently wrong forever after, and it is trusted
precisely because it looks authoritative.

So the map is measured on every run. Orphaned code is not a list somebody
remembered to update; it is `scripts/x.js` appearing in zero pages, computed
now. If a module gains a surface, this map says so without anybody editing it.

WHAT IT ANSWERS

    what exists            pages, generators, modules, styles, data, checks
    what is connected      which module is loaded by how many pages
    what is orphaned       the modules loaded by none
    what writes what       which generator owns which surface
    who reads a dataset    so "one authoritative source" can be verified

It deliberately does NOT judge. Commit 03 decides what to do with an orphan —
integrate, retain as infrastructure, deprecate, delete. This one only finds it.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", "incoming", ".vercel"}


def walk(ext, under=None):
    base = os.path.join(ROOT, under) if under else ROOT
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d[0] != "."]
        for name in sorted(filenames):
            if name.endswith(ext):
                yield os.path.join(dirpath, name)


def rel(path):
    return os.path.relpath(path, ROOT)


def pages():
    return sorted(walk(".html"))


def family_of(html, path):
    """What kind of page this is, from the page itself.

    The body class `af--<family>` is the page's own declaration; the path is a
    fallback for any surface that has not got one. A page that answers "what am
    I" only by where it sits on disk is a page the information architecture
    does not really own, so counting those is itself a finding.
    """
    # THE CONVENTION IS A BODY CLASS, `af--<family>`, AND IT ALREADY EXISTS.
    #
    # The first version of this map read `data-family`, which I had introduced
    # on two new pages a few commits earlier without checking what the other
    # 1,598 already used. It reported "2 pages declare their family" — a
    # finding about my own invention, not about the site. shell-checks.js has
    # asserted the body class on every page all along.
    #
    # A second way of stating one fact is the failure this mandate exists to
    # remove, so `data-family` is gone and this reads the convention that was
    # already there.
    m = re.search(r'<body[^>]*class="([^"]*)"', html)
    if m:
        fam = re.search(r'\baf--([a-z]+)', m.group(1))
        if fam:
            return fam.group(1), "declared"
    r = rel(path)
    if r.startswith("places/"):
        return "place", "path"
    if r.startswith("portrait/"):
        return "portrait", "path"
    if r.startswith("tourism/"):
        return "country", "path"
    if r.startswith("trans-afrique/"):
        return "crossing", "path"
    if r.startswith("journey-fund/"):
        return "fund", "path"
    return "root", "path"


def main():
    out = []
    w = out.append

    page_paths = pages()
    bodies = {}
    for p in page_paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            bodies[p] = fh.read()

    w("# The system map")
    w("")
    w("**GENERATED. Do not edit.** `python3 tools/system-map.py > docs/system-map.md`")
    w("")
    w("Every figure here is measured at the moment of generation. A hand-written")
    w("map of a system this size is correct on the day it is written and quietly")
    w("wrong afterwards — and trusted anyway, because it looks authoritative.")
    w("")

    # ---- pages ------------------------------------------------------------
    fams = {}
    how = {"declared": 0, "path": 0}
    for p in page_paths:
        fam, source = family_of(bodies[p], p)
        fams.setdefault(fam, []).append(p)
        how[source] += 1
    w("## Pages")
    w("")
    w("| family | pages |")
    w("|---|---|")
    for fam in sorted(fams, key=lambda k: -len(fams[k])):
        w("| `%s` | %d |" % (fam, len(fams[fam])))
    w("| **total** | **%d** |" % len(page_paths))
    w("")
    w("%d pages declare their own family in the body class `af--<family>`; %d"
      % (how["declared"], how["path"]))
    w("are classified only by where they sit on disk.")
    w("A page that can answer *what am I* only by its path is a page the")
    w("information architecture does not yet own.")
    w("")

    # ---- scripts, and what loads them -------------------------------------
    w("## Modules, and how many pages load each")
    w("")
    w("**A module loaded by zero pages is orphaned product code.** It may still")
    w("be infrastructure — required by another module, or by a check — so the")
    w("second column separates *nothing loads it in a browser* from *nothing")
    w("references it at all*.")
    w("")
    w("| module | pages | referenced by |")
    w("|---|---|---|")
    script_paths = sorted(walk(".js", "scripts"))
    all_src = ""
    for p in list(walk(".js", "scripts")) + list(walk(".js", "tools")) + list(walk(".py", "tools")):
        with open(p, encoding="utf-8", errors="replace") as fh:
            all_src += fh.read()
    orphans = []
    for sp in script_paths:
        base = os.path.basename(sp)
        n = sum(1 for p in page_paths if base in bodies[p])
        refs = len(re.findall(re.escape(base), all_src)) - 1  # minus its own name
        w("| `%s` | %d | %d |" % (base, n, max(refs, 0)))
        if n == 0:
            orphans.append(base)
    w("")
    if orphans:
        w("**Orphaned in the browser: %d module(s)** — `%s`."
          % (len(orphans), "`, `".join(orphans)))
    else:
        w("**No module is orphaned.** Every module in `scripts/` is loaded by at")
        w("least one page.")
    w("")

    # ---- stylesheets ------------------------------------------------------
    w("## Stylesheets, and how many pages load each")
    w("")
    w("| stylesheet | pages | generated |")
    w("|---|---|---|")
    # The two generated stylesheets are named in CLAUDE.md; asserting it here
    # rather than restating it means a third one appearing is visible.
    GENERATED = {"tourism.css", "country.css"}
    for sp in sorted(walk(".css", "styles")):
        base = os.path.basename(sp)
        n = sum(1 for p in page_paths if base in bodies[p])
        w("| `%s` | %d | %s |"
          % (base, n, "yes" if base in GENERATED else "no"))
    w("")

    # ---- datasets ---------------------------------------------------------
    w("## Datasets, and who reads them")
    w("")
    w("One authoritative source per important fact is the rule. A dataset read")
    w("by nothing is dead; a dataset read by many is load-bearing and must not")
    w("be edited casually.")
    w("")
    w("| dataset | readers | records |")
    w("|---|---|---|")
    for dp in sorted(list(walk(".json", "tourism")) + list(walk(".json", "data"))):
        base = os.path.basename(dp)
        readers = len(set(re.findall(r"[\w/]*" + re.escape(base), all_src)))
        try:
            with open(dp, encoding="utf-8") as fh:
                doc = json.load(fh)
            size = len(doc) if isinstance(doc, (list, dict)) else 1
        except Exception:
            size = "?"
        w("| `%s` | %s | %s |" % (rel(dp), readers, size))
    w("")

    # ---- generators -------------------------------------------------------
    w("## Generators")
    w("")
    build = open(os.path.join(ROOT, "tools", "tourism", "build.py"),
                 encoding="utf-8").read()
    cmds = sorted(set(re.findall(r'"([a-z]+)":\s*cmd_[a-z_]+', build)))
    w("`build.py` exposes **%d commands**. Every page on this site is generated;"
      % len(cmds))
    w("nothing here is written by hand and left alone.")
    w("")
    w("```")
    line = ""
    for c in cmds:
        if len(line) + len(c) > 68:
            w(line.rstrip())
            line = ""
        line += c + "  "
    if line:
        w(line.rstrip())
    w("```")
    w("")
    w("**Late passes edit built HTML, and any regeneration wipes them.** The")
    w("chain is `library rewrite` → `bound` → `srcset` → `sizeattr` → `modern`,")
    w("behind `company` and `graft`. A single generator run does not execute it.")
    w("")

    # ---- checks -----------------------------------------------------------
    w("## Gates")
    w("")
    w("| suite | lines |")
    w("|---|---|")
    total = 0
    for cp in sorted(walk("-checks.js", "tools")):
        n = len(open(cp, encoding="utf-8", errors="replace").read().splitlines())
        total += n
        w("| `%s` | %d |" % (rel(cp), n))
    tests_py = os.path.join(ROOT, "tools", "tourism", "tests.py")
    if os.path.exists(tests_py):
        n = len(open(tests_py, encoding="utf-8").read().splitlines())
        total += n
        w("| `tools/tourism/tests.py` (the suite CI runs) | %d |" % n)
    w("| **total** | **%d** |" % total)
    w("")

    # ---- documentation ----------------------------------------------------
    # A COUNTER THAT COUNTS ITSELF IS NOT DETERMINISTIC.
    #
    # This wrote docs/system-map.md and then counted docs/*.md — including the
    # file it had just written — so run one reported 10,061 lines and run two
    # reported 10,363, with nothing in the repository having changed. Caught by
    # running the generator twice and diffing, which is the check Commit 42
    # exists to institutionalise and which found its first victim here.
    #
    # The map describes the repository; it is not part of what it describes.
    docs = [d for d in sorted(walk(".md", "docs"))
            if os.path.basename(d) != "system-map.md"]
    doc_lines = sum(len(open(d, encoding="utf-8", errors="replace").read().splitlines())
                    for d in docs)
    w("## Documentation")
    w("")
    w("%d documents, %d lines." % (len(docs), doc_lines))
    w("")

    # ---- the ratio that started the mandate -------------------------------
    js_lines = sum(len(open(p, encoding="utf-8", errors="replace").read().splitlines())
                   for p in script_paths)
    w("## The ratio")
    w("")
    w("| | |")
    w("|---|---|")
    w("| product and economic JavaScript | %d lines |" % js_lines)
    w("| gates | %d lines |" % total)
    w("| documentation | %d lines |" % doc_lines)
    w("| modules a browser never loads | %d |" % len(orphans))
    w("")
    w("This is the figure the integration mandate exists to close. Architecture")
    w("that no visitor can reach is architecture that has not shipped.")
    w("")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
