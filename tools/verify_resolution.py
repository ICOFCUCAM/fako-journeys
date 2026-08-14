"""Make the green check on the resolve workflow mean something.

    python3 tools/verify_resolution.py [cached_before]

`build.py status` prints six hundred lines of per-slot detail for a human to
read. This counts the same cache and fails on what a human would miss in six
hundred lines — which is exactly what happened: the resolver died on an
ImportError at the first uncached slot, the workflow swallowed the non-zero exit
with `|| true`, and the run reported "OK: 54 · UNRESOLVED: 540" under a green
tick. Nobody goes looking behind a green tick.

The bar is "no worse than we started", not "everything resolved". Providers
rate-limit, and a run that fills two hundred slots and stops is real progress
that should not fail the job. What must never pass is a run that fills nothing
while reporting success.
"""

import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main(before=0):
    cache_path = os.path.join(ROOT, "tourism", "cache", "images.json")
    try:
        cache = json.load(open(cache_path))["entries"]
    except (IOError, ValueError, KeyError) as exc:
        print("::error::the image cache is unreadable: %s" % exc)
        return 1

    slots = 0
    for f in glob.glob(os.path.join(ROOT, "tourism", "countries", "*.json")):
        slots += len(json.load(open(f)).get("entries") or [])

    ok = len(cache)
    bad = sorted(k for k, v in cache.items()
                 if not str((v or {}).get("imageUrl") or "").startswith("https://"))

    rows = [("image slots", slots), ("resolved", ok), ("unresolved", slots - ok),
            ("invalid url", len(bad)), ("cached before this run", before)]
    print("| metric | result |")
    print("|--------|--------|")
    for k, v in rows:
        print("| %s | %d |" % (k, v))

    fail = []
    if bad:
        fail.append("%d cached entries are not https URLs: %s"
                    % (len(bad), ", ".join(bad[:5])))
    if ok < before:
        fail.append("the cache shrank: %d entries before this run, %d after" % (before, ok))
    if slots and ok == before and ok < slots:
        fail.append("nothing resolved and %d slots are still empty — the resolver "
                    "ran without doing anything, which is the failure this check "
                    "exists to catch" % (slots - ok))
    for f in fail:
        print("::error::" + f)
    return 1 if fail else 0


if __name__ == "__main__":
    try:
        arg = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    except ValueError:
        arg = 0
    sys.exit(main(arg))
