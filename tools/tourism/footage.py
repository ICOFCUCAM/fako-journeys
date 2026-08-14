"""Fetch candidate clips from Pexels into incoming/video/, and place none of them.

    export PEXELS_API_KEY=...
    python3 tools/tourism/build.py footage --query "aerial lagos nigeria" -n 3
    python3 tools/tourism/build.py footage --list

WHY THIS ONLY FETCHES

The image resolver picks a photograph and files it against a slot, and that is
already the source of the complaint that some of the resolved pictures do not
look like the place they are captioned with. A video is worse: it is longer, it
is the first thing under the hero, and a viewer watches it for six seconds
rather than glancing at it. Keyword search cannot tell you where footage was
shot. "Lagos" on Pexels returns handsome clips of somewhere, and a clip of
somewhere captioned Lagos is the same fault as a generated picture of a real
city.

So this fetches into incoming/video/ and writes a sidecar recording the query,
the Pexels id and URL, the photographer and the licence. Placing a clip against
a shot in motion.json is a decision a person makes with the file in front of
them, and the caption is theirs to make true.

WHERE IT RUNS

Not on a developer machine behind the agent proxy: api.pexels.com and
videos.pexels.com are both refused there by egress policy, which is why the
image resolver has always run in GitHub Actions. Same here. The key lives in
Actions secrets and never touches the repository.

WHAT IT REFUSES TO WRITE

A file that is not a video, a file larger than the ceiling, and a URL the API
did not hand back. There is no code path here that builds a Pexels URL from an
id — the API is the authority, exactly as it is for photographs.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .providers.base import RateLimited, Unavailable, UA
from .model import ROOT

INBOX = os.path.join(ROOT, "incoming", "video")
LEDGER = os.path.join(INBOX, "candidates.json")

# The page shows this at about 690px wide. Anything over 1080p is weight a
# visitor pays for and cannot see, and the fetch is metered by quota as well as
# by bandwidth.
MAX_W = 1920
MIN_W = 1280
MAX_BYTES = 40 * 1024 * 1024      # a raw candidate, before it is cut
MAX_SECONDS = 45                  # anything longer is a film, not a shot


def api_base():
    return os.environ.get("PEXELS_API_BASE") or "https://api.pexels.com/videos"


def key():
    k = os.environ.get("PEXELS_API_KEY")
    if not k:
        raise Unavailable("PEXELS_API_KEY is not set. This runs in CI, where it "
                          "is a secret; it is not meant to run on a laptop.")
    return k


def get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "Authorization": key(), "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimited("Pexels quota spent")
        raise Unavailable("Pexels said HTTP %s" % exc.code)
    except Exception as exc:
        raise Unavailable("cannot reach the Pexels video API (%s)" % exc)


def best_file(video):
    """The largest mp4 at or under MAX_W, or nothing.

    Pexels hands back several renditions per clip. Picking the biggest would
    fetch 4K to show at 690px; picking the smallest gives a soft frame on a
    retina screen. This takes the widest that is still within the ceiling.
    """
    best = None
    for f in video.get("video_files") or []:
        link, w = f.get("link"), f.get("width") or 0
        if not link or f.get("file_type") != "video/mp4":
            continue
        if w > MAX_W or w < MIN_W:
            continue
        if best is None or w > (best.get("width") or 0):
            best = f
    return best


def search(query, want=3, orientation="landscape"):
    """Candidates for one query. Returns the ones worth downloading."""
    url = api_base() + "/search?" + urllib.parse.urlencode({
        "query": query, "orientation": orientation,
        "per_page": max(want * 4, 12), "size": "medium",
    })
    out = []
    for v in (get_json(url).get("videos") or []):
        if (v.get("duration") or 0) > MAX_SECONDS:
            continue
        f = best_file(v)
        if not f:
            continue
        out.append({
            "id": v.get("id"),
            "query": query,
            "url": f["link"],                       # the API's URL, never built
            "page": v.get("url"),
            "width": f.get("width"), "height": f.get("height"),
            "seconds": v.get("duration"),
            "by": ((v.get("user") or {}).get("name") or "").strip(),
            "by_url": (v.get("user") or {}).get("url"),
            "licence": "Pexels licence — free for commercial use, no attribution "
                       "required; individual clips may carry model or property "
                       "restrictions.",
            "where": None,       # nobody knows yet, and the sidecar says so
        })
        if len(out) >= want:
            break
    return out


def fetch(cand, timeout=120):
    """Download one candidate. Returns its path, or raises."""
    os.makedirs(INBOX, exist_ok=True)
    name = "pexels-%s-%dw.mp4" % (cand["id"], cand.get("width") or 0)
    path = os.path.join(INBOX, name)
    req = urllib.request.Request(cand["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        if r.status != 200:
            raise Unavailable("HTTP %s fetching %s" % (r.status, name))
        if not ctype.startswith("video/"):
            raise Unavailable("%s is not a video (%s)" % (name, ctype))
        body = r.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise Unavailable("%s is over the %d MB ceiling"
                              % (name, MAX_BYTES // (1024 * 1024)))
        if len(body) < 64 * 1024:
            raise Unavailable("%s is suspiciously small" % name)
    with open(path, "wb") as fh:
        fh.write(body)
    cand["file"] = "/incoming/video/" + name
    cand["bytes"] = len(body)
    return path


def ledger():
    try:
        with open(LEDGER) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return {"$comment": [
            "Every clip fetched into this directory, and what is known about it.",
            "",
            "`where` is null on everything the API returned, and that is the",
            "point: Pexels can say what a clip was tagged with and cannot say",
            "where it was shot. A clip goes on a shot in motion.json only once",
            "somebody has looked at it and can stand behind the caption.",
            "",
            "`licence` is recorded per clip rather than per site, because free",
            "for commercial use is a property of a file and not of a domain.",
        ], "clips": []}


def save(led):
    os.makedirs(INBOX, exist_ok=True)
    with open(LEDGER, "w") as fh:
        json.dump(led, fh, indent=1, ensure_ascii=False)


def run(queries, want=3, log=print):
    """Fetch candidates for each query. Nothing is placed against a shot."""
    led = ledger()
    have = {c.get("id") for c in led["clips"]}
    got, failed = 0, []
    for q in queries:
        try:
            cands = search(q, want=want)
        except RateLimited:
            raise
        except Unavailable as exc:
            failed.append("%s: %s" % (q, exc))
            continue
        if not cands:
            log("  %-34s nothing within the size and length limits" % q)
            continue
        for c in cands:
            if c["id"] in have:
                continue
            try:
                fetch(c)
            except Unavailable as exc:
                failed.append(str(exc))
                continue
            have.add(c["id"])
            led["clips"].append(c)
            got += 1
            log("  %-34s %s  %dx%d  %ds  %.1f MB"
                % (q, c["file"].rsplit("/", 1)[-1], c["width"], c["height"],
                   c["seconds"] or 0, c["bytes"] / 1048576.0))
    save(led)
    log("%d clip(s) staged in incoming/video/, %d placed against a shot"
        % (got, 0))
    if failed:
        log("could not fetch: " + "; ".join(failed[:6]))
    return got
