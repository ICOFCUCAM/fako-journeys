"""The contact sheet: every slot on the site, with every candidate for it.

    python3 tools/tourism/build.py compare
    open tourism/compare.html

One row per slot. On the left, what the page is showing now — the Unsplash or
Pexels photograph the resolver chose, or the SVG illustration if nothing was
ever resolved. To the right, the generated candidates for that slot. All of them
cropped to the shape the slot actually imposes, because judging a 3:2 frame that
will be delivered at 4:5 tells you nothing about how it will look on the page.

Choosing writes to localStorage and downloads a picks.json, which
`build.py place picks.json` applies. That round trip is deliberate: a static
page cannot write to the repository, and a review tool that could silently
change the site would be a worse tool.

The sheet is generated into tourism/, which .vercelignore keeps out of the
deployment — it is a workshop document, not a page.
"""

import html as html_mod
import json
import os

from . import candidates as pool, placements as pl
from .model import ROOT

OUT = os.path.join(ROOT, "tourism", "compare.html")


def esc(value):
    return html_mod.escape(str(value if value is not None else ""), quote=True)


def local_url(url):
    """Site-absolute paths, made relative to where this file sits.

    The sheet lives in tourism/ and is opened straight off disk — or unzipped
    out of a CI artifact — so "/images/x.svg" would resolve against the
    filesystem root and show nothing. Remote URLs are left alone.
    """
    if not url or "://" in url:
        return url
    if url.startswith("/"):
        return os.path.relpath(os.path.join(ROOT, url.lstrip("/")),
                               os.path.dirname(OUT)).replace(os.sep, "/")
    return url


def card(candidate, aspect, current=False):
    """One candidate, cropped to the slot's real aspect ratio."""
    url = local_url(candidate.get("url") or candidate.get("full") or "")
    source = candidate.get("source") or "?"
    bits = []
    if candidate.get("width"):
        bits.append("%s&times;%s" % (candidate["width"], candidate.get("height") or "?"))
    if candidate.get("photographer"):
        bits.append(esc(candidate["photographer"]))
    if candidate.get("score") is not None:
        bits.append("score %s" % candidate["score"])
    if candidate.get("bytes"):
        bits.append("%dKB" % (candidate["bytes"] // 1024))

    classes = "cand" + (" in-use" if candidate.get("inUse") or current else "")
    return """
      <label class="%s" data-id="%s">
        <input type="radio" name="%s" value="%s"%s%s>
        <span class="shot" style="aspect-ratio:%d/%d"><img src="%s" alt="" loading="lazy"></span>
        <span class="meta"><b class="src src-%s">%s</b>%s</span>
        <span class="why">%s</span>
      </label>""" % (
        classes, esc(candidate.get("id")),
        esc(candidate.get("_slot")), esc(candidate.get("id")),
        " checked" if candidate.get("inUse") or current else "",
        " data-placeable" if source in ("openai", "upload") else "",
        aspect[0], aspect[1], esc(url),
        esc(source), esc(source),
        "".join("<i>%s</i>" % b for b in bits),
        esc(candidate.get("prompt") or " ".join(candidate.get("reasons") or []) or ""),
    )


def build(country, taxonomy, cache, path=OUT):
    index = pool.load()
    placements = pl.scan(country)
    rows = []
    counts = {"slots": 0, "generated": 0, "stock": 0, "empty": 0}

    for p in placements:
        slot = pool.placement_slot(p)
        cands = []

        if p["locked"]:
            pass
        else:
            record = None
            if p["category"]:
                record = cache.get(country.slug, p["category"])
            current = pool.from_cache_record(record)
            if current:
                current["_slot"] = slot
                cands.append(current)
            elif p["current"]:
                cands.append({"_slot": slot, "source": "illustration",
                              "id": "illustration:" + p["id"], "url": p["current"],
                              "inUse": True})
            for g in index.generated(slot):
                g = dict(g)
                g["_slot"] = slot
                cands.append(g)
            for s in index.stock(slot):
                if any(c.get("id") == s.get("id") for c in cands):
                    continue
                s = dict(s)
                s["_slot"] = slot
                cands.append(s)

        counts["slots"] += 1
        counts["generated"] += len([c for c in cands if c.get("source") == "openai"])
        counts["stock"] += len([c for c in cands if c.get("source") in ("unsplash", "pexels")])
        if not [c for c in cands if c.get("source") == "openai"]:
            counts["empty"] += 1

        rows.append("""
    <section class="slot%s" data-slot="%s">
      <header>
        <h2>%s</h2>
        <p class="where">%s &middot; <b>%s</b> &middot; delivered %d:%d</p>
        <p class="brief">%s</p>
        <p class="focus">%s</p>
      </header>
      <div class="cands">%s</div>
    </section>""" % (
            " locked" if p["locked"] else "",
            esc(slot), esc(p["id"]), esc(p["page"]),
            esc(p["wrapper"] or "default"), p["aspect"][0], p["aspect"][1],
            esc("LOCKED — hand-picked artwork, not a generated slot"
                if p["locked"] else p["instruction"]),
            esc(("The crop must keep: " + p["focus"]) if p.get("focus") else ""),
            "".join(card(c, p["aspect"]) for c in cands)
            or '<p class="none">no candidates yet — run <code>build.py generate</code></p>',
        ))

    doc = TEMPLATE % {
        "country": esc(country.name),
        "counts": "%d slots &middot; %d generated candidate(s) &middot; %d slot(s) with none yet"
                  % (counts["slots"], counts["generated"], counts["empty"]),
        "rows": "\n".join(rows),
    }
    with open(path, "w") as f:
        f.write(doc)
    return counts, path


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image candidates — %(country)s</title>
<!-- An internal review sheet for placing photographs, not a page for
     visitors: it is not linked from the site and not in the sitemap. -->
<meta name="robots" content="noindex">
<style>
:root{--bg:#F7F2E7;--ink:#1F211C;--muted:#6E7166;--line:#DDD4C1;--accent:#BE5527;--go:#1C2A25}
*{margin:0;padding:0;box-sizing:border-box}
body{font:16px/1.6 Charter,Georgia,serif;background:var(--bg);color:var(--ink);padding:0 0 120px}
header.top{position:sticky;top:0;z-index:9;background:var(--bg);border-bottom:2px solid var(--go);padding:18px 32px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
h1{font:700 24px/1 "Archivo Narrow",Arial Narrow,sans-serif;text-transform:uppercase}
.count{font:11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
button{font:11px/1 ui-monospace,Menlo,monospace;letter-spacing:.16em;text-transform:uppercase;padding:12px 18px;border:0;background:var(--go);color:var(--bg);cursor:pointer}
button.ghost{background:transparent;color:var(--go);border:1px solid var(--line)}
button:hover{background:var(--accent);color:var(--bg)}
.hint{margin-left:auto;font:11px/1.5 ui-monospace,Menlo,monospace;color:var(--muted);text-align:right}
.slot{padding:30px 32px;border-bottom:1px solid var(--line)}
.slot.locked{opacity:.5}
.slot h2{font:700 19px/1.1 "Archivo Narrow",Arial Narrow,sans-serif;text-transform:uppercase}
.where{font:10.5px/1.6 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.brief{margin:8px 0 6px;max-width:80ch;color:var(--muted)}
/* What the crop must not throw away, from the role. The one thing a reviewer is
   actually judging and it was not on the sheet: a candidate can be the right
   subject and still be the wrong photograph once this frame is cut out of it. */
.focus{margin:0 0 18px;max-width:80ch;font:12px/1.6 ui-monospace,Menlo,monospace;
  color:var(--accent)}
.focus:empty{display:none}
.cands{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,240px));gap:18px}
.cand{display:block;cursor:pointer;border:2px solid transparent;padding:8px;background:#fff}
.cand:hover{border-color:var(--line)}
.cand input{position:absolute;opacity:0;pointer-events:none}
.cand:has(input:checked){border-color:var(--accent);box-shadow:0 8px 24px rgba(20,19,16,.14)}
.shot{display:block;width:100%%;max-height:300px;overflow:hidden;background:var(--line)}
.shot img{width:100%%;height:100%%;object-fit:cover;display:block}
.meta{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-top:8px}
.meta i{font:10px/1 ui-monospace,Menlo,monospace;font-style:normal;color:var(--muted)}
.src{font:10px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;padding:4px 7px;color:#fff;background:var(--muted)}
.src-openai{background:var(--accent)}.src-unsplash{background:#111}.src-pexels{background:#05A081}
.src-illustration{background:#8a8577}
.why{display:block;margin-top:6px;font-size:12px;line-height:1.5;color:var(--muted);max-height:4.5em;overflow:hidden}
.in-use{border-color:var(--go)}
.none{color:var(--muted);font-size:14px}
code{font:12px ui-monospace,Menlo,monospace;background:#fff;padding:2px 5px}
</style>
</head>
<body>
<header class="top">
  <h1>Candidates — %(country)s</h1>
  <span class="count">%(counts)s</span>
  <button id="save">Download picks.json</button>
  <button class="ghost" id="clear">Clear</button>
  <span class="hint">Pick one per slot, download, then run<br><code>npm run tourism:place -- picks.json</code></span>
</header>
%(rows)s
<script>
var KEY = 'fako-picks';
var saved = JSON.parse(localStorage.getItem(KEY) || '{}');
Object.keys(saved).forEach(function(slot){
  var el = document.querySelector('input[name="' + CSS.escape(slot) + '"][value="' + CSS.escape(saved[slot]) + '"]');
  if (el) el.checked = true;
});
document.addEventListener('change', function(e){
  if (e.target.type !== 'radio') return;
  saved[e.target.name] = e.target.value;
  localStorage.setItem(KEY, JSON.stringify(saved));
});
document.getElementById('save').addEventListener('click', function(){
  // `place` handles local files — generated and uploaded. A stock pick is a job
  // for resolve/adopt, so it is left out rather than written into a file that
  // would fail half way through. The marker comes off the input, not off the
  // shape of the id, because ids from different sources do not share a shape.
  var out = {}, skipped = 0;
  Object.keys(saved).forEach(function(slot){
    var el = document.querySelector('input[name="' + CSS.escape(slot) + '"][value="' + CSS.escape(saved[slot]) + '"]');
    if (el && el.hasAttribute('data-placeable')) out[slot] = saved[slot];
    else if (el) skipped++;
  });
  if (skipped) console.info(skipped + ' stock pick(s) left out — those are resolve/adopt\'s job.');
  var blob = new Blob([JSON.stringify(out, null, 2) + '\\n'], {type: 'application/json'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'picks.json';
  a.click();
});
document.getElementById('clear').addEventListener('click', function(){
  localStorage.removeItem(KEY);
  document.querySelectorAll('input:checked').forEach(function(i){ i.checked = false; });
});
</script>
</body>
</html>
"""
