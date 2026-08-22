#!/usr/bin/env python3
"""The design system, measured — and a ratchet so it can only consolidate.

    python3 tools/design-audit.py            the report
    python3 tools/design-audit.py --check    fail if the system has sprawled

COMMIT 05 OF THE 50-COMMIT INTEGRATION MANDATE.

THE MEASUREMENT IS THE HARD PART, AND I GOT IT WRONG TWICE BEFORE THIS.

Attempt one read only `styles/*.css` and reported 20 distinct font sizes.
Attempt two added the 66 pages carrying an inline <style> and still reported
20 — which should have been the tell. Both were truncating at

    css.split("@media print", 1)[0]

`afrinkong.css` sorts first and contains a print block partway down, so
everything after it — sixteen stylesheets and every inline block — was thrown
away. I was one step from reporting that `docs/design-audit.md` overstated the
problem by an order of magnitude, which would have been a confident, evidenced
and completely wrong finding, and would have cancelled consolidation work that
genuinely needs doing.

It is the same bug the token-contrast check had: a print block winning a
measurement about the screen. Removing a block requires counting braces, not
splitting on a string, so this counts braces.

WHAT IT MEASURES

Every rule the browser can apply on a screen: `styles/*.css` plus every
<style> block on every PUBLISHED page, with @media print blocks removed.

Declarations and distinct values are reported separately, because they answer
different questions. 1,274 font-size declarations drawn from 186 distinct
values is a system with 186 type sizes; the same declarations drawn from 11
would be a system with a type scale.

THE RATCHET

`--check` fails if any figure exceeds the ceiling recorded below. The ceilings
are today's measurements, and the rule is that they may only ever be LOWERED.
That converts "we should consolidate one day" into something a build can
enforce: the system is free to shrink and cannot grow.

It deliberately does not demand the target numbers now. Cutting 186 type sizes
to 11 is the work of many commits, and a gate that fails until then is a gate
somebody switches off.
"""

import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", "incoming", ".vercel"}

# TODAY'S MEASUREMENTS, AND THE RULE THAT THEY MAY ONLY EVER BE LOWERED.
#
# A number here going UP means somebody added a nineteenth shadow or a
# thirty-third breakpoint, which is the sprawl the design system exists to
# stop. A number going DOWN is consolidation, and lowering the ceiling to match
# is part of doing that work — otherwise the ratchet slips.
CEILING = {
    "font-size": 186,
    "box-shadow": 22,
    "border-radius": 4,
    "breakpoint": 32,
    "prefix": 26,
    "custom-property": 112,
    # The sum of each stylesheet's own distinct font sizes. This is the figure
    # docs/design-audit.md reported as "418 distinct font-size declarations
    # site-wide", and it is not that: it double-counts every value two
    # stylesheets share. Measured the same way today it is 439 — so by its own
    # method the type system has not consolidated, it has grown slightly.
    #
    # Both numbers are worth keeping. 186 is the vocabulary the site actually
    # uses; 439 is what it costs to state that vocabulary once per file. The
    # GAP between them, 253, is the duplication, and it is the number the
    # consolidation work should be driving down first.
    "font-size-per-file-sum": 439,

    # ---- COMPONENT SPRAWL, COMMIT 16 ------------------------------------
    #
    # The mandate asks for canonical buttons, cards, badges, frames and forms.
    # Measured, the site has 27 button-ish base components, 11 cards, 32
    # badges, 55 frames and 11 form components across 26 prefixes.
    #
    # (27/11/32/56/11 as this tool counts them, which includes inline <style>.)
    # Consolidating those is not one commit. It is a refactor across 17
    # stylesheets and 1,599 pages with real visual-regression risk, and doing
    # it in a hurry is how a design system acquires its SECOND set of
    # canonical components. What can be done now, and is worth more than a
    # hasty merge, is stopping the number growing.
    #
    # Each of these is today's count. They may only be lowered.
    "component:button": 27,
    "component:card": 11,
    "component:badge": 32,
    "component:frame": 56,
    "component:form": 11,

    # Rule bodies of 40+ characters written out under two or more different
    # selectors. Some are legitimate shared idioms — object-fit:cover on an
    # image, a focus ring — and some are a card invented three times. The
    # figure does not distinguish them and is not meant to: it is a direction
    # of travel, and the direction must be down.
    #
    # SET FROM THE TOOL'S OWN MEASUREMENT, NOT FROM THE SCAN THAT FOUND THEM.
    # My exploratory scan read styles/*.css and reported 55 frames and 127
    # duplicate bodies; this tool also reads the <style> blocks on 66 published
    # pages, and sees 56 and 133. A ceiling copied from a narrower scope fails
    # on the first run and teaches whoever meets it that the gate is noise.
    "duplicate rule bodies": 133,
}

# Where the design system is going. Recorded so the gap is visible on every
# run rather than living in a document nobody opens. See docs/design-system.md.
TARGET = {
    "font-size": 11,
    "box-shadow": 2,
    "breakpoint": 4,
    "prefix": 11,
}


def strip_print(css):
    """Remove @media print blocks by counting braces.

    NOT `split("@media print")`. A split throws away everything after the first
    print block, which on this codebase means sixteen stylesheets, because
    afrinkong.css sorts first and has one in the middle. That produced a
    measurement nine times too small and very nearly a confident wrong report.
    """
    out, i = [], 0
    while True:
        m = re.search(r"@media[^{]*\bprint\b[^{]*\{", css[i:])
        if not m:
            out.append(css[i:])
            return "".join(out)
        start, body = i + m.start(), i + m.end()
        depth, j = 1, body
        while j < len(css) and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        out.append(css[i:start])
        i = j


def published():
    rules = []
    vi = os.path.join(ROOT, ".vercelignore")
    if os.path.exists(vi):
        rules = [l.strip().rstrip("/") for l in open(vi, encoding="utf-8")
                 if l.strip() and not l.startswith("#")]
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d[0] != "."]
        for name in sorted(filenames):
            if not name.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
            if not any(rel == r or rel.startswith(r + "/") for r in rules):
                out.append(rel)
    return sorted(out)


def gather():
    css, sheets, inline = "", [], 0
    d = os.path.join(ROOT, "styles")
    for name in sorted(os.listdir(d)):
        if name.endswith(".css"):
            sheets.append(name)
            css += open(os.path.join(d, name), encoding="utf-8").read() + "\n"
    for rel in published():
        s = open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()
        for block in re.findall(r"<style[^>]*>(.*?)</style>", s, re.S):
            inline += 1
            css += block + "\n"
    return strip_print(css), sheets, inline


PATTERNS = {
    "font-size": r"font-size:\s*([^;}\n]+)",
    "box-shadow": r"box-shadow:\s*([^;}\n]+)",
    "border-radius": r"border-radius:\s*([^;}\n]+)",
    "breakpoint": r"@media[^{]*?\(\s*(?:min|max)-width:\s*([0-9.]+px)",
}


def resolve_tokens(screen):
    """Replace var(--x) with the value --x is declared as, once.

    WITHOUT THIS, MIGRATING A RULE ONTO A TOKEN MAKES THE NUMBERS WORSE.

    Rewriting `font-size:15px` as `font-size:var(--fj-t-body)` renders exactly
    the same pixel and, to a scanner comparing strings, invents a 187th type
    size. Adopting the token layer moved the count from 186 to 190 and tripped
    the ratchet — punishing the consolidation the ratchet exists to encourage.

    A metric that penalises the fix is worse than no metric. So a var() is
    resolved to what it stands for before anything is counted: the migration is
    NEUTRAL while both forms coexist, and the count falls when the last literal
    goes. One pass only — a token defined in terms of another token is rare
    here and resolving recursively would risk a loop for no gain.
    """
    values = dict(re.findall(r"(--[a-z0-9-]+):\s*([^;{}]+);", screen))
    return re.sub(r"var\((--[a-z0-9-]+)\)",
                  lambda m: values.get(m.group(1), m.group(0)).strip(), screen)


def measure(screen):
    got = {}
    resolved = resolve_tokens(screen)
    for key, pat in PATTERNS.items():
        src = resolved if key in ("font-size", "box-shadow", "border-radius") else screen
        vals = [v.strip() for v in re.findall(pat, src)]
        got[key] = (len(vals), len(set(vals)), sorted(set(vals)))
    prefixes = collections.Counter(re.findall(r"\.([a-z]{2,3})-[a-z-]+", screen))

    got["prefix"] = (sum(prefixes.values()), len(prefixes),
                     [k for k, _ in prefixes.most_common()])
    COMPONENTS = {
        "button": r"\.([a-z]{2,3}-[a-z-]*(?:btn|button|act|cta)[a-z-]*)\b",
        "card": r"\.([a-z]{2,3}-[a-z-]*card[a-z-]*)\b",
        "badge": r"\.([a-z]{2,3}-[a-z-]*(?:badge|stamp|chip|tag|pill)[a-z-]*)\b",
        "frame": r"\.([a-z]{2,3}-[a-z-]*(?:frame|figure|shot|pic|hero)[a-z-]*)\b",
        "form": r"\.([a-z]{2,3}-[a-z-]*(?:field|input|form|select)[a-z-]*)\b",
    }
    for kind, pat in COMPONENTS.items():
        names = set(re.findall(pat, screen))
        # A modifier is not a component: .af-btn--solid belongs to .af-btn.
        base = sorted({n.split("--")[0] for n in names})
        got["component:" + kind] = (len(names), len(base), base)

    # Provable duplication: the same declarations, written out twice, under
    # different selectors. Short bodies are excluded because two rules
    # coinciding on `display:block` is not duplication, it is CSS.
    seen = {}
    for m in re.finditer(r"([^{}@]+)\{([^{}]+)\}", screen):
        sel, body = m.group(1).strip(), re.sub(r"\s+", "", m.group(2)).rstrip(";")
        if len(body) < 40 or sel.startswith(("@", ":root")):
            continue
        seen.setdefault(body, set()).add(sel)
    dupes = [b for b, sels in seen.items() if len(sels) > 1]
    got["duplicate rule bodies"] = (len(seen), len(dupes), [])

    props = sorted(set(re.findall(r"(--[a-z0-9-]+):", screen)))
    got["custom-property"] = (len(re.findall(r"--[a-z0-9-]+:", screen)),
                              len(props), props)
    return got


def per_file_font_sizes():
    """Each stylesheet's own distinct font sizes, summed.

    The measure docs/design-audit.md used, reproduced so the two can be
    compared honestly rather than argued about.
    """
    total, rows = 0, []
    d = os.path.join(ROOT, "styles")
    all_css = "".join(open(os.path.join(d, n2), encoding="utf-8").read()
                      for n2 in sorted(os.listdir(d)) if n2.endswith(".css"))
    token_values = dict(re.findall(r"(--[a-z0-9-]+):\s*([^;{}]+);", all_css))
    for name in sorted(os.listdir(d)):
        if not name.endswith(".css"):
            continue
        css = strip_print(open(os.path.join(d, name), encoding="utf-8").read())
        # Resolved against the WHOLE stylesheet set, because a file may use a
        # token another file declares — which is the entire point of a token.
        #
        # An earlier version concatenated all_css in front and sliced the
        # result back off by length. Resolution changes the length, so the
        # slice landed mid-text and the count jumped from 439 to 454 — a
        # measurement artefact that looked exactly like sprawl. Substituting
        # into this file alone, with a map built from all of them, has no such
        # arithmetic in it.
        css = re.sub(r"var\((--[a-z0-9-]+)\)",
                     lambda m: token_values.get(m.group(1), m.group(0)).strip(),
                     css)
        n = len({v.strip() for v in re.findall(PATTERNS["font-size"], css)})
        total += n
        rows.append((name, n))
    return total, sorted(rows, key=lambda r: -r[1])


def main():
    screen, sheets, inline = gather()
    got = measure(screen)
    per_sum, per_rows = per_file_font_sizes()
    got["font-size-per-file-sum"] = (per_sum, per_sum, [])

    if "--check" in sys.argv:
        bad = 0
        for key, limit in sorted(CEILING.items()):
            n = got[key][1]
            if n > limit:
                bad += 1
                print("FAIL\tthe design system has grown a new %s\t%d distinct, "
                      "ceiling %d" % (key, n, limit))
            else:
                note = "at the ceiling" if n == limit else \
                       "%d below the ceiling — lower CEILING[%r] to %d" % (limit - n, key, n)
                print("PASS\tno new %s\t%d distinct of %d declarations, %s"
                      % (key, n, got[key][0], note))
        sys.exit(1 if bad else 0)

    w = print
    w("# The design system, measured")
    w("")
    w("**GENERATED.** `python3 tools/design-audit.py > docs/design-audit.md`")
    w("")
    w("%d stylesheets and %d inline `<style>` blocks on published pages, with"
      % (len(sheets), inline))
    w("`@media print` removed by counting braces rather than by splitting on a")
    w("string — a split discards everything after the first print block, which")
    w("here means sixteen stylesheets, and produces a figure nine times too")
    w("small.")
    w("")
    w("| | declarations | distinct | target |")
    w("|---|---|---|---|")
    for key in ("font-size", "box-shadow", "border-radius", "breakpoint",
                "prefix", "custom-property"):
        decl, distinct, _ = got[key]
        w("| %s | %d | **%d** | %s |"
          % (key, decl, distinct,
             TARGET.get(key, "\u2014")))
    w("")
    w("## The duplication, which is the number to drive down first")
    w("")
    w("| | |")
    w("|---|---|")
    w("| distinct font sizes site-wide (the vocabulary) | **%d** |" % got["font-size"][1])
    w("| sum of each stylesheet's own distinct sizes | **%d** |" % per_sum)
    w("| the gap \u2014 the same size restated in another file | **%d** |"
      % (per_sum - got["font-size"][1]))
    w("")
    w("`docs/design-audit.md` reported **418 distinct font-size declarations")
    w("site-wide**. That figure is the second row, not the first: it sums each")
    w("file's own distinct values and so double-counts everything two")
    w("stylesheets share. Measured its way today the number is %d, so by its" % per_sum)
    w("own method the type system has not consolidated \u2014 it has grown.")
    w("")
    w("| stylesheet | its own distinct sizes |")
    w("|---|---|")
    for name, n in per_rows[:8]:
        w("| `%s` | %d |" % (name, n))
    w("")
    w("Declarations and distinct values answer different questions. %d font-size"
      % got["font-size"][0])
    w("declarations drawn from %d distinct values is a system with %d type sizes;"
      % (got["font-size"][1], got["font-size"][1]))
    w("the same declarations drawn from %d would be a system with a type scale."
      % TARGET["font-size"])
    w("")
    w("## Breakpoints")
    w("")
    w("`%s`" % "`, `".join(sorted(got["breakpoint"][2],
                                  key=lambda x: float(x[:-2]))))
    w("")
    w("## Class prefixes")
    w("")
    w("`%s`" % "`, `".join(got["prefix"][2]))
    w("")
    w("## The ratchet")
    w("")
    w("`--check` fails if any figure rises above the ceiling recorded in")
    w("`tools/design-audit.py`. The ceilings are today's measurements and may")
    w("only ever be lowered. The system is free to shrink and cannot grow.")
    w("")
    w("It does not demand the target numbers yet. Cutting %d type sizes to %d"
      % (got["font-size"][1], TARGET["font-size"]))
    w("is the work of many commits, and a gate that fails until then is a gate")
    w("somebody switches off.")
    w("")


if __name__ == "__main__":
    main()
