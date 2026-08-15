"""Two countries, side by side, on the same twenty-seven terms.

    python3 tools/tourism/build.py sidebyside     ->  /compare.html

The site says, on the gateway and on every country page, that each destination
is worked through the same twenty-seven categories "so you can compare two of
them on the same terms instead of on the strength of their marketing". That was
a claim with nothing behind it. This is the claim, delivered.

Everything comes from the data: which countries exist, what they lead on, when
they are good, who runs them, and what their twenty-seven say. The comparable
fields for every country ship as one inlined block and the switching happens in
the browser, because a comparison you have to wait for is one nobody makes
twice.

What is deliberately absent is a score. Kenya is not better than Ghana; they are
different, and the difference is the thing being chosen between. The moment this
page picks a winner it stops being a comparison and becomes the marketing it
exists to replace. It marks the rows where the two differ and stops there.

Not named `compare` because that command is the image contact sheet, which is a
different job entirely.
"""

import html as html_mod
import json
import os

from . import plate
from .model import ROOT

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def payload(countries, taxonomy):
    """The comparable fields, small enough to inline.

    Captions rather than descriptions: a caption is the thing itself — "The
    Great Rift Valley", "Walking safari at Mole" — and two columns of things
    read as a comparison, where two columns of prose read as two brochures.
    """
    out = {}
    for c in countries:
        if not c.published:
            continue
        rows = {}
        for cat in taxonomy.enabled:
            e = c.entry(cat["id"])
            if e and e.caption:
                rows[cat["id"]] = e.caption
        out[c.slug] = {
            "name": c.name, "region": c.region, "summary": c.summary, "url": c.url,
            "months": c.months, "when": c.when, "calls": c.calls,
            "operator": (c.operator.name if c.operator else ""),
            "base": (c.operator.base if c.operator else ""),
            "rows": rows,
        }
    return out


def build(countries, taxonomy):
    data = payload(countries, taxonomy)
    slugs = sorted(data, key=lambda s: data[s]["name"])
    cats = [{"id": c["id"], "title": c["title"].split("/")[0].strip()} for c in taxonomy.enabled]
    opts = "".join('<option value="%s">%s</option>' % (esc(s), esc(data[s]["name"])) for s in slugs)
    return TEMPLATE % {
        "options_a": opts.replace('value="%s"' % esc(slugs[0]),
                                  'value="%s" selected' % esc(slugs[0]), 1),
        "options_b": opts.replace('value="%s"' % esc(slugs[1]),
                                  'value="%s" selected' % esc(slugs[1]), 1),
        "count": len(taxonomy.enabled),
        # Six rows the table always has — region, in a sentence, leads on, when
        # to come, who runs it, read the whole thing — plus one per category.
        "cats": len(taxonomy.enabled),
        "rows": len(taxonomy.enabled) + 6,
        # /compare is in the sitemap and shipped without a canonical or a single
        # Open Graph tag, so a shared link to it had no card and search engines
        # had no preferred address for a page that takes ?a= and ?b=.
        "social": plate.open_graph(
            "Compare two African destinations on the same terms | Afrinkong",
            "Put any two Afrinkong destinations side by side across the same %d "
            "categories, the same calendar and the same questions about who runs "
            "them." % len(taxonomy.enabled), "/compare"),
        "total": len(slugs),
        "data": json.dumps({"countries": data, "cats": cats}, ensure_ascii=False),
    }


def run(countries, taxonomy, out_dir=None, log=print):
    path = os.path.join(out_dir or ROOT, "compare.html")
    with open(path, "w") as fh:
        fh.write(build(countries, taxonomy))
    log("wrote %s (%d countries x %d categories)"
        % (os.path.relpath(path, ROOT), len([c for c in countries if c.published]),
           len(taxonomy.enabled)))
    return path


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compare two African destinations on the same terms | Afrinkong</title>
<meta name="description" content="Put any two Afrinkong destinations side by side across the same %(count)d categories, the same calendar and the same questions about who runs them.">
%(social)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<style>
.mast{position:fixed;top:0;left:0;right:0;z-index:70;background:var(--c-bg);border-bottom:2px solid var(--c-primary)}
.mast-in{display:flex;align-items:center;gap:34px;padding:14px 0}
.mark{margin-right:auto;display:flex;flex-direction:column;gap:2px}
.mark i{font-style:normal;font-family:var(--fj-mono);font-size:8.5px;letter-spacing:.28em;text-transform:uppercase;color:var(--c-accent)}
.mark b{font-family:var(--fj-display);font-size:24px;font-weight:700;text-transform:uppercase;line-height:1}
.routes{display:flex;gap:24px}
.routes a{font-family:var(--fj-mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--c-muted);white-space:nowrap}
.routes a:hover{color:var(--c-primary)}
@media(max-width:900px){.routes{display:none}}

.open{padding:calc(var(--mast) + 52px) 0 30px}
.open h1{font-size:clamp(34px,5vw,64px);max-width:18ch;margin-top:14px}
.open h1 em{font-style:normal;color:var(--c-accent)}
.open p{margin-top:18px;color:var(--c-muted);max-width:72ch}

/* Two columns are the page. Every row spans them, so the eye runs down one
   country and across to the other without needing a legend. */
.cp{border-top:2px solid var(--c-primary)}
.cp-pick{display:grid;grid-template-columns:1fr 1fr;position:sticky;top:var(--mast);z-index:40;
  background:var(--c-bg);border-bottom:var(--fj-rule)}
.cp-pick div{padding:16px 20px 16px 0;border-right:var(--fj-rule)}
.cp-pick div:last-child{border-right:0;padding-right:0;padding-left:20px}
.cp-pick label{display:block;font-family:var(--fj-mono);font-size:9px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--c-muted);margin-bottom:8px}
.cp-pick select{width:100%%;font-family:var(--fj-display);font-size:clamp(20px,2.8vw,32px);
  font-weight:700;text-transform:uppercase;color:var(--c-primary);background:none;border:0;
  border-bottom:2px solid var(--c-accent);padding:0 0 8px;cursor:pointer;appearance:none;-webkit-appearance:none}

.cp-row{display:grid;grid-template-columns:1fr 1fr;border-bottom:var(--fj-rule)}
.cp-row>div{padding:16px 20px 18px 0;border-right:var(--fj-rule)}
.cp-row>div:last-child{border-right:0;padding-right:0;padding-left:20px}
.cp-label{grid-column:1/-1;font-family:var(--fj-mono);font-size:9px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--c-muted);padding:22px 0 6px;border-right:0 !important}
.cp-val{font-size:15.5px}
.cp-val--big{font-family:var(--fj-display);font-size:20px;font-weight:700;text-transform:uppercase}
.cp-val--muted{color:var(--c-muted)}
/* Where they differ, the row says so — a reader is here for the difference. */
.cp-row[data-diff]{background:color-mix(in srgb,var(--c-bg) 93%%,var(--c-accent))}
.cp-row[data-diff] .cp-label{color:var(--c-accent)}
.cp-mons{display:flex;flex-wrap:wrap;gap:3px}
.cp-mon{width:22px;height:22px;display:flex;align-items:center;justify-content:center;
  border:1px solid var(--c-border);font-family:var(--fj-mono);font-size:9px;color:var(--c-muted)}
.cp-mon[data-on]{background:var(--c-accent);border-color:var(--c-accent);color:var(--c-bg)}
.cp-calls{display:flex;flex-wrap:wrap;gap:5px}
.cp-calls span{font-family:var(--fj-mono);font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;
  border:1px solid var(--c-border);padding:4px 7px;color:var(--c-muted)}
.cp-only{display:block;margin-top:6px;font-family:var(--fj-mono);font-size:8.5px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--c-accent)}
/* Three widths set in em, which is not the unit a reader crosses: 46em of a
   15px face is 100 average characters, 48em of a 17px face is 105, 44em is 96.
   72ch measures 78 in this serif, which is where the rest of the site sits. */
.cp-note{margin:32px 0 0;color:var(--c-muted);max-width:72ch;font-size:15px}
/* The table is built by the script, so #cp-body is empty when the page paints
   and everything below it — the note, the footer — sat at the top of the
   viewport and then dropped 3,500 pixels when the rows arrived. Measured at
   CLS 0.19, which is past the point Google calls a page bad, and it happened on
   every load rather than only on a slow one.

   Reserved from the row count rather than a magic number: %(rows)d rows (six
   fixed plus %(cats)d categories). 101px is the shortest row height measured
   across 1440, 1280, 900, 700 and 390 pixels wide and three different pairs of
   countries — deliberately the shortest, so the reservation is never larger
   than the table and never leaves a gap under it. */
.cp{--cp-rows:%(rows)d}
#cp-body{min-height:calc(var(--cp-rows) * 101px)}
.cp-nojs{padding:34px 0 10px;max-width:60ch}
.cp-nojs h2{font-size:clamp(24px,3vw,34px)}
.cp-nojs p{margin-top:14px;color:var(--c-muted)}
.cp-nojs-go{margin-top:22px;display:flex;flex-wrap:wrap;gap:20px}
.cp-nojs-go a{font-family:var(--fj-mono);font-size:10.5px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--c-accent);
  border-bottom:1px solid color-mix(in srgb,var(--c-accent) 40%%,transparent)}
@media(max-width:700px){#cp-body{min-height:calc(var(--cp-rows) * 99px)}}
@media(max-width:700px){
  .cp-row>div,.cp-pick div{padding:14px 10px 16px 0}
  .cp-row>div:last-child,.cp-pick div:last-child{padding-left:10px}
  .cp-val{font-size:14px}}

.foot{background:var(--fj-basalt);color:var(--fj-onbasalt);padding:52px 0;margin-top:66px}
.foot a{border-bottom:1px solid var(--c-accent)}
.foot p{max-width:72ch;color:var(--fj-onbasalt-dim)}
</style>
<noscript><style>
/* After the block above, not before it: same specificity, so the later rule is
   the one that applies. The reservation exists so the table does not shove the
   page down when the script builds it. With no script there is no table, and
   holding 3,300 pixels open for one that is never coming is worse than not
   holding it at all. */
#cp-body{min-height:0}
</style></noscript>
</head>
<body>
<a class="af-skip" href="#main">Skip to content</a>
<header class="mast">
  <div class="af-frame mast-in">
    <a class="mark" href="/"><i>Afrinkong</i><b>Compare</b></a>
    <nav class="routes" aria-label="Primary">
      <a href="/#window">The map</a>
      <a href="/#destinations">Destinations</a>
      <a href="/tourism/">Every country</a>
      <a href="/contact">Plan a journey</a>
    </nav>
  </div>
</header>

<main id="main">
<section class="open">
  <div class="af-frame">
    <span class="af-stamp">%(total)d destinations &middot; %(count)d categories each</span>
    <h1>Two countries, <em>the same questions</em>.</h1>
    <p>Every destination here is worked through the same %(count)d categories, the same calendar and the same questions about who runs it. That only matters if you can hold two of them side by side &mdash; so pick any two. Rows where they differ are marked. Nothing is scored: one of these is not better than the other, they are different, and the difference is what you are choosing between.</p>
  </div>
</section>

<section class="af-frame cp">
  <div class="cp-pick">
    <div><label for="cp-a">First</label><select id="cp-a">%(options_a)s</select></div>
    <div><label for="cp-b">Second</label><select id="cp-b">%(options_b)s</select></div>
  </div>
  <div id="cp-body"><noscript>
    <div class="cp-nojs">
      <h2>This one needs a script, and there is not one running.</h2>
      <p>The table is assembled in the browser from a payload carrying all
        %(total)d countries, so that changing either menu is instant rather than a
        page load. With scripting off there is nothing to assemble it.</p>
      <p>Every country here has its own page, written through the same
        %(count)d categories in the same order, so two of them read side by side
        in two tabs say exactly what this table would have said.</p>
      <p class="cp-nojs-go"><a href="/places">Every place, country by country</a>
        <a href="/atlas">The atlas</a>
        <a href="/stories">The portraits</a></p>
    </div>
  </noscript></div>
  <p class="cp-note">Captions rather than sentences, on purpose. The full description of any of these is on that country's own page.</p>
</section>
</main>

<footer class="foot">
  <div class="af-frame">
    <p>Afrinkong runs tour operators of its own in three countries and writes up %(total)d, all through the same %(count)d categories. <a href="/#destinations">See all destinations</a>, or <a href="/contact">tell us what you are after</a>.</p>
    <p class="foot-co"><!-- gen:company -->
    <!-- /gen:company --></p>
  </div>
</footer>

<script>
/* --mast is a design-system default, and this page's masthead is not exactly
   that tall. The picker sticks directly under it, so an eight-pixel discrepancy
   is a strip of the page showing through above it. Measure once and tell the
   variable the truth. */
(function(){
  var m = document.querySelector('.mast');
  function set(){ document.documentElement.style.setProperty('--mast', m.offsetHeight + 'px'); }
  set();
  addEventListener('resize', set, {passive:true});
})();
</script>
<script id="cp-data" type="application/json">%(data)s</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById('cp-data').textContent);
  var a = document.getElementById('cp-a'), b = document.getElementById('cp-b');
  var body = document.getElementById('cp-body');
  var MONTHS = ['January','February','March','April','May','June',
                'July','August','September','October','November','December'];
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
  }
  function months(list){
    var out = '<div class="cp-mons">';
    for (var i = 1; i <= 12; i++) {
      out += '<span class="cp-mon"' + (list.indexOf(i) >= 0 ? ' data-on' : '')
           + ' title="' + MONTHS[i-1] + '">' + MONTHS[i-1][0] + '</span>';
    }
    return out + '</div>';
  }
  function calls(list){
    if (!list.length) return '<span class="cp-val cp-val--muted">&mdash;</span>';
    return '<div class="cp-calls">' + list.map(function(c){
      return '<span>' + esc(c) + '</span>'; }).join('') + '</div>';
  }
  function row(label, left, right, differs){
    return '<div class="cp-row"' + (differs ? ' data-diff' : '') + '>'
      + '<p class="cp-label">' + esc(label) + '</p>'
      + '<div>' + left + '</div><div>' + right + '</div></div>';
  }
  function render(){
    var A = DATA.countries[a.value], B = DATA.countries[b.value];
    if (!A || !B) return;
    var h = '';
    h += row('Region', '<p class="cp-val cp-val--big">' + esc(A.region) + '</p>',
                       '<p class="cp-val cp-val--big">' + esc(B.region) + '</p>',
             A.region !== B.region);
    h += row('In a sentence', '<p class="cp-val">' + esc(A.summary) + '</p>',
                              '<p class="cp-val">' + esc(B.summary) + '</p>', false);
    h += row('Leads on', calls(A.calls), calls(B.calls), A.calls.join() !== B.calls.join());
    h += row('When to come',
      months(A.months) + '<p class="cp-val cp-val--muted" style="margin-top:10px">' + esc(A.when) + '</p>',
      months(B.months) + '<p class="cp-val cp-val--muted" style="margin-top:10px">' + esc(B.when) + '</p>',
      A.months.join() !== B.months.join());
    h += row('Who runs it',
      '<p class="cp-val cp-val--big">' + esc(A.operator || 'No operator of ours') + '</p>'
        + (A.base ? '<p class="cp-val cp-val--muted">' + esc(A.base) + '</p>' : ''),
      '<p class="cp-val cp-val--big">' + esc(B.operator || 'No operator of ours') + '</p>'
        + (B.base ? '<p class="cp-val cp-val--muted">' + esc(B.base) + '</p>' : ''),
      (A.operator ? 1 : 0) !== (B.operator ? 1 : 0));
    /* A category one country answers and the other does not is the most useful
       line on the page, so it is called out rather than left blank. */
    DATA.cats.forEach(function(cat){
      var la = A.rows[cat.id] || '', lb = B.rows[cat.id] || '';
      if (!la && !lb) return;
      h += row(cat.title,
        la ? '<p class="cp-val">' + esc(la) + '</p>'
           : '<p class="cp-val cp-val--muted">&mdash;<span class="cp-only">Only ' + esc(B.name) + '</span></p>',
        lb ? '<p class="cp-val">' + esc(lb) + '</p>'
           : '<p class="cp-val cp-val--muted">&mdash;<span class="cp-only">Only ' + esc(A.name) + '</span></p>',
        !la || !lb);
    });
    h += row('Read the whole thing',
      '<a class="af-go" href="' + esc(A.url) + '">Enter ' + esc(A.name) + ' &rarr;</a>',
      '<a class="af-go" href="' + esc(B.url) + '">Enter ' + esc(B.name) + ' &rarr;</a>', false);
    body.innerHTML = h;
    /* The pair lives in the URL, so a comparison can be sent to somebody. */
    history.replaceState(null, '', location.pathname + '?a=' + encodeURIComponent(a.value)
      + '&b=' + encodeURIComponent(b.value));
  }
  var p = new URLSearchParams(location.search);
  if (DATA.countries[p.get('a')]) a.value = p.get('a');
  if (DATA.countries[p.get('b')]) b.value = p.get('b');
  a.addEventListener('change', render);
  b.addEventListener('change', render);
  render();
})();
</script>
<script src="/scripts/story-search.js" defer></script>
<script src="/scripts/explore.js" defer></script>
</body>
</html>
"""
