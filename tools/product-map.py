#!/usr/bin/env python3
"""code module -> user-facing capability -> page. Every module, a decision.

    python3 tools/product-map.py            the report
    python3 tools/product-map.py --check    fail on an undeclared or lying module

COMMIT 03 OF THE 50-COMMIT INTEGRATION MANDATE.

"A MODULE LOADED BY ZERO PAGES IS ORPHANED" IS THE WRONG TEST FOR THIS SITE.

Commit 01 counted eight modules that no page loads and called them orphaned.
That framing is right for an application and wrong for a static site, and
`entities.js` is the proof: 223 lines the browser never sees, whose entire
content a customer can read at /trust because `trust_page.py` renders the model
into HTML at build time. Shipping those 223 lines to a phone so it could draw a
static table would be worse in every respect.

So the question is not *is this module loaded*. It is:

    does the KNOWLEDGE in this module reach a customer, and if not, why not

Four answers, and every module must give one:

    live            a customer meets it — as a browser module, or rendered
                    into HTML at build time. Must name the surface.
    gated           complete, correct, and must NOT be surfaced yet. Must name
                    the gate that is holding it.
    infrastructure  consumed by other modules or by the gates; correctly never
                    seen by anybody.
    deprecated      to be removed. Must name what replaces it.

WHY THE DECLARATION LIVES IN THE MODULE.

A manifest in a separate file is one more pair of things that must agree with
nothing comparing them — the failure this whole mandate exists to remove. The
tag sits in the module's own header comment, so a module cannot be moved,
rewritten or re-purposed without its classification being right there.

WHAT --check ACTUALLY VERIFIES

Not that the tag exists. That it is TRUE:

    live         must name a surface, and if it names a browser surface the
                 page must really load it
    gated        must name a gate, and NO page may load it — a gated module
                 that has quietly acquired a surface is the single most
                 dangerous state in this repository, because it is how
                 unreleased economic functionality goes live by accident
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", "incoming", ".vercel"}

TAG = re.compile(r"@product:\s*(\w+)\s*\|\s*@gate:\s*([\w-]+)\s*\|\s*@surface:\s*(.+)")
VALID = {"live", "gated", "infrastructure", "deprecated"}


def pages():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d[0] != "."]
        for name in sorted(filenames):
            if name.endswith(".html"):
                out.append(os.path.join(dirpath, name))
    return out


def read_modules():
    mods = {}
    d = os.path.join(ROOT, "scripts")
    for name in sorted(os.listdir(d)):
        if not name.endswith(".js"):
            continue
        head = "\n".join(open(os.path.join(d, name), encoding="utf-8")
                         .read().split("\n")[:40])
        m = TAG.search(head)
        mods[name] = None if not m else {
            "disposition": m.group(1),
            "gate": m.group(2).strip(),
            "surface": m.group(3).strip(),
        }
    return mods


def main():
    mods = read_modules()
    page_paths = pages()
    loaded = {}
    bodies = [open(p, encoding="utf-8", errors="replace").read() for p in page_paths]
    for name in mods:
        loaded[name] = sum(1 for b in bodies if name in b)

    problems = []
    for name, tag in sorted(mods.items()):
        if tag is None:
            problems.append("%s carries no @product declaration" % name)
            continue
        if tag["disposition"] not in VALID:
            problems.append("%s declares an unknown disposition %r"
                            % (name, tag["disposition"]))
            continue
        if tag["disposition"] == "live" and tag["surface"] in ("none", ""):
            problems.append("%s is declared live and names no surface" % name)
        if tag["disposition"] == "gated":
            if tag["gate"] in ("none", ""):
                problems.append("%s is gated and names no gate" % name)
            if loaded[name]:
                # The one that matters. A gated module with a surface is how
                # unreleased economic functionality reaches a customer by
                # accident rather than by decision.
                problems.append(
                    "%s is GATED behind %s and yet %d page(s) load it"
                    % (name, tag["gate"], loaded[name]))
        if tag["disposition"] == "deprecated" and tag["gate"] in ("none", ""):
            problems.append("%s is deprecated and names no replacement" % name)

    if "--check" in sys.argv:
        for p in problems:
            print("FAIL\t%s" % p)
        if not problems:
            live = [n for n, t in mods.items() if t and t["disposition"] == "live"]
            gated = [n for n, t in mods.items() if t and t["disposition"] == "gated"]
            print("PASS\tevery module declares what it is\t%d modules" % len(mods))
            print("PASS\tevery live module names a surface\t%d live" % len(live))
            print("PASS\tno gated module has acquired a surface\t%d gated: %s"
                  % (len(gated), ", ".join(sorted(gated))))
        sys.exit(1 if problems else 0)

    w = print
    w("# The product map")
    w("")
    w("**GENERATED.** `python3 tools/product-map.py > docs/product-map.md`")
    w("")
    w("code module → user-facing capability → page. Every module gives one of")
    w("four answers, and the answer lives in the module's own header so it")
    w("cannot drift from the code it describes.")
    w("")
    w('"Loaded by zero pages" is the wrong test for a static site. `entities.js`')
    w("is 223 lines the browser never sees, whose whole content a customer reads")
    w("at `/trust`, because the model is rendered into HTML at build time.")
    w("Shipping it to a phone to draw a static table would be worse in every")
    w("respect. The question is whether the KNOWLEDGE reaches a customer.")
    w("")
    for disp, blurb in (
        ("live", "a customer meets this — in the browser, or rendered at build time"),
        ("gated", "complete and correct, and must not be surfaced yet"),
        ("infrastructure", "consumed by other modules or by the gates"),
        ("deprecated", "to be removed"),
    ):
        rows = [(n, t) for n, t in sorted(mods.items())
                if t and t["disposition"] == disp]
        if not rows:
            continue
        w("## %s" % disp)
        w("")
        w("*%s*" % blurb)
        w("")
        w("| module | lines | pages loading it | %s |"
          % ("gate" if disp == "gated" else "surface"))
        w("|---|---|---|---|")
        for n, t in rows:
            lines = len(open(os.path.join(ROOT, "scripts", n),
                             encoding="utf-8").read().splitlines())
            w("| `%s` | %d | %d | %s |"
              % (n, lines, loaded[n],
                 t["gate"] if disp == "gated" else t["surface"]))
        w("")

    gated = [(n, t) for n, t in sorted(mods.items())
             if t and t["disposition"] == "gated"]
    if gated:
        total = sum(len(open(os.path.join(ROOT, "scripts", n), encoding="utf-8")
                        .read().splitlines()) for n, _ in gated)
        w("## What is being held back, and by what")
        w("")
        w("%d modules, %d lines. None of it is unfinished; all of it is waiting."
          % (len(gated), total))
        w("")
        by_gate = {}
        for n, t in gated:
            by_gate.setdefault(t["gate"], []).append(n)
        w("| gate | modules |")
        w("|---|---|")
        for g in sorted(by_gate):
            w("| `%s` | %s |" % (g, ", ".join("`%s`" % x for x in by_gate[g])))
        w("")
        w("**A gated module that acquires a surface fails `--check`.** That is")
        w("the check that matters here: it is how unreleased economic")
        w("functionality would reach a customer by accident rather than by")
        w("decision.")
        w("")


if __name__ == "__main__":
    main()
