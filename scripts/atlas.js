/* The atlas — the geography as the interface.
 * ---------------------------------------------------------------------------
 * One state object, one render. Everything the visitor can do — press a region,
 * press a country on the map, pick a place, choose a lens, choose a month, ask
 * to be sent somewhere, press Back — sets state and re-renders. There is no
 * second path through this file, which is why the map, the panel, the
 * breadcrumb and the address bar cannot disagree with each other.
 *
 *     state = { level, region, country, place, want, when }
 *
 * and the address is `#/east/uganda/mountains?want=wildlife&when=11`, so any
 * view of the continent is a link somebody can send.
 *
 * The map is navigated, never redrawn. Flying is four numbers on a viewBox;
 * descending a rung is a fill, an opacity and a clip-path. Nothing here parses
 * geometry, and no path data is touched after the page has painted.
 */
(function () {
  'use strict';

  var node = document.getElementById('at-spine');
  if (!node) return;
  var SP = JSON.parse(node.textContent);

  var root = document.getElementById('atlas');
  var svg = document.getElementById('at-svg');
  var crumb = document.getElementById('at-crumb');
  var panel = document.getElementById('at-panel');
  var labels = document.getElementById('at-labels');
  var count = document.getElementById('at-count');
  var panes = {};
  [].forEach.call(panel.querySelectorAll('.at-pane'), function (p) {
    panes[p.dataset.pane] = p;
  });
  var lands = [].slice.call(svg.querySelectorAll('.at-c'));
  /* The map is a composite control, not twenty-two links in a row. Tabbing
     through every country before reaching the panel is technically accessible
     and practically unusable, so one country holds the tab stop and the arrow
     keys move between them — the pattern a listbox uses, on geography.
     This is done in script: with no script they are ordinary links, and
     ordinary links should all be reachable. */
  function rove(to) {
    lands.forEach(function (a) {
      a.setAttribute('tabindex', a === to ? '0' : '-1');
    });
  }
  rove(lands[0]);
  var byslug = {};
  lands.forEach(function (a) { byslug[a.dataset.slug] = a; });
  var labelBySlug = {};
  [].forEach.call(svg.querySelectorAll('.at-label'), function (t) {
    labelBySlug[t.dataset.slug] = t;
  });
  var winBySlug = {};
  [].forEach.call(svg.querySelectorAll('.at-win'), function (im) {
    winBySlug[im.id.slice(3)] = im;
  });
  var regionByKey = {};
  SP.regions.forEach(function (r) { regionByKey[r.key] = r; });
  var lensByKey = {};
  SP.lenses.forEach(function (l) { lensByKey[l.key] = l; });

  var web = document.getElementById('at-web');
  var reduced = matchMedia('(prefers-reduced-motion: reduce)');
  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };
  var LINKS = null;             /* data/links.json, fetched when links mode opens */
  var LABEL = 13;                      /* label size at the full continental view */
  var state = {level: 'africa', region: null, country: null, place: null,
               want: null, when: null, web: false};
  var loaded = {};                     /* slug -> places payload, fetched once */
  var seen = {};                       /* what "take me somewhere" has already used */
  var view = SP.view.slice();
  var anim = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }

  /* ---- flying ------------------------------------------------------------ */

  /* The viewBox is four numbers and the browser composites the result, so this
     costs nothing next to redrawing fifty countries. Reduced motion gets the
     destination on the first frame: the information is the view, not the trip. */
  function flyTo(to) {
    if (anim) cancelAnimationFrame(anim);
    if (!to) return;
    if (reduced.matches) { view = to.slice(); apply(); declutter(); return; }
    var from = view.slice(), t0 = performance.now(), ms = 700;
    (function step(now) {
      var p = Math.min(1, (now - t0) / ms);
      var e = 1 - Math.pow(1 - p, 3);
      view = from.map(function (v, i) { return v + (to[i] - v) * e; });
      apply();
      if (p < 1) anim = requestAnimationFrame(step);
      else declutter();
    })(t0);
  }

  /* Ghana and Côte d'Ivoire are neighbours and both small, so at continental
     zoom their names land on top of each other and neither is readable. Rather
     than hand-nudging anchors — which would have to be redone for every country
     added — the names are laid down largest country first and any that lands on
     one already placed is dropped. Zoom in and it comes back, because there is
     then room for it. Text measurement is a layout read, so this runs once when
     a flight settles and never inside the animation. */
  function declutter() {
    var on = Object.keys(labelBySlug).filter(function (s) {
      return labelBySlug[s].hasAttribute('data-on');
    });
    on.sort(function (a, b) { return boxArea(b) - boxArea(a); });
    var placed = [];
    on.forEach(function (s) {
      var t = labelBySlug[s];
      t.removeAttribute('data-hide');
      var r;
      try { r = t.getBBox(); } catch (err) { return; }
      var clash = placed.some(function (o) {
        return !(r.x + r.width < o.x || o.x + o.width < r.x
                 || r.y + r.height < o.y || o.y + o.height < r.y);
      });
      if (clash) t.setAttribute('data-hide', '');
      else placed.push(r);
    });
  }

  function boxArea(slug) {
    var box = SP.countries[slug] && SP.countries[slug].box;
    return box ? box[2] * box[3] : 0;
  }

  function apply() {
    svg.setAttribute('viewBox', view.map(function (v) { return v.toFixed(1); }).join(' '));
    /* Labels are pinned to the ground but must not grow with the zoom, so their
       size is expressed as a fraction of how much continent is on screen. */
    var k = LABEL * view[2] / SP.view[2];
    labels.setAttribute('font-size', k.toFixed(2));
    labels.setAttribute('stroke-width', (k * 0.28).toFixed(2));
  }

  /* ---- what is in view --------------------------------------------------- */

  /* The lens set. `want` narrows to the countries that lead on that thing;
     `when` narrows to the ones whose season includes that month. Both are
     dataset facts — a country's own `calls` and its own months — so an empty
     result is a real answer and is reported as one rather than hidden. */
  function filtered() {
    var slugs = Object.keys(SP.countries);
    if (state.want && lensByKey[state.want]) {
      var lens = lensByKey[state.want];
      slugs = slugs.filter(function (s) { return lens.countries.indexOf(s) >= 0; });
    }
    if (state.when) {
      slugs = slugs.filter(function (s) {
        return (SP.countries[s].months || []).indexOf(state.when) >= 0;
      });
    }
    return slugs;
  }

  function inScope() {
    var pool = filtered();
    if (state.level === 'region' && state.region) {
      var members = regionByKey[state.region].countries;
      return pool.filter(function (s) { return members.indexOf(s) >= 0; });
    }
    if (state.country) return [state.country];
    return pool;
  }

  /* ---- painting the map -------------------------------------------------- */

  function paintMap() {
    var lit = {}, quiet = {};
    var scope = inScope();
    scope.forEach(function (s) { lit[s] = true; });

    /* At country level the rest of the region stays on the map, dimmed but not
       switched off: a country with its neighbours removed is a diagram of a
       country, and the whole argument of this page is that it is a place with
       things next to it. */
    if (state.country) {
      var rk = SP.countries[state.country].regionKey;
      (regionByKey[rk] ? regionByKey[rk].countries : []).forEach(function (s) {
        if (!lit[s]) quiet[s] = true;
      });
    }

    lands.forEach(function (a) {
      var s = a.dataset.slug;
      var on = !!lit[s], near = !!quiet[s];
      a.toggleAttribute('data-dim', !on && !near);
      a.toggleAttribute('data-near', near);
      a.toggleAttribute('data-lit', on && !state.country && !!state.want);
      var isFocus = state.country === s;
      a.toggleAttribute('data-win', isFocus && !!windowFor(s));
    });

    /* Names appear when there is room for them: our own countries on the
       continental view, everything in scope once a region is open. Once a
       country is the subject its own name is set in sixty-four point in the
       panel beside it, so the label comes off the map and the neighbours' names
       go on instead — which is the thing you cannot read anywhere else. */
    var showNames = state.level !== 'africa' || !!state.want || !!state.when;
    Object.keys(labelBySlug).forEach(function (s) {
      var t = labelBySlug[s];
      var on;
      if (state.country) on = !!quiet[s];
      else if (showNames) on = !!lit[s];
      else on = !!(byslug[s] && byslug[s].dataset.tier === 'ours');
      t.toggleAttribute('data-on', !!on);
      t.toggleAttribute('data-quiet', !!(on && state.country));
      t.toggleAttribute('data-inv', !!(byslug[s] && byslug[s].hasAttribute('data-lit')));
    });

    /* The tab stop has to be somewhere you can still reach: if the country
       holding it has just been dimmed out of the view, hand it to the first one
       that is in it. */
    var open = lands.filter(function (a) { return !a.hasAttribute('data-dim'); });
    if (open.length && !open.some(function (a) { return a.getAttribute('tabindex') === '0'; })) {
      rove(open[0]);
    }

    paintWindow();
    paintWeb();
    requestAnimationFrame(declutter);
  }

  /* Whatever the visitor has already told the map, carried into the builder so
     it does not ask again. An entry point is only worth having if it remembers
     the answer that brought somebody through it. */
  function briefQuery() {
    var q = [];
    if (state.want) q.push('w=' + state.want);
    if (state.when) q.push('m=' + state.when);
    return q.length ? '?' + q.join('&') : '';
  }

  /* ---- the constellation -------------------------------------------------- */

  /* The same twenty-two countries, read as a network instead of as land. Every
     node sits at its own country's centre in these coordinates, so switching
     modes changes the drawing and not the subject — Uganda is in the same place
     either way, and nothing has to be relearned.
     Only two kinds of line are ever drawn, and both are facts: a shared land
     border, read out of Natural Earth, and the thing two countries both say
     they lead on. There is no line for "these are both in Africa". */
  function paintWeb() {
    root.toggleAttribute('data-web', state.web);
    if (!state.web || !LINKS) { web.innerHTML = ''; return; }
    var scope = inScope();
    var lit = {};
    scope.forEach(function (s) { lit[s] = true; });
    var focus = state.country;
    var bits = [];

    var drawn = {};
    function edge(a, b, kind, on) {
      var pa = (LINKS.nodes[a] || {}).at, pb = (LINKS.nodes[b] || {}).at;
      if (!pa || !pb) return;
      var key = [a, b].sort().join('|') + kind;
      if (drawn[key]) return;
      drawn[key] = true;
      bits.push('<line x1="' + pa[0] + '" y1="' + pa[1] + '" x2="' + pb[0]
        + '" y2="' + pb[1] + '" data-kind="' + kind + '"' + (on ? ' data-lit' : '') + '/>');
    }

    Object.keys(LINKS.borders).forEach(function (a) {
      LINKS.borders[a].forEach(function (b) {
        /* With a lens on, a border between two countries that are not the
           answer is a line about something else. */
        if (state.want && !(lit[a] && lit[b])) return;
        edge(a, b, 'border', !!(focus && (a === focus || b === focus)));
      });
    });

    /* A lens turns the network into an answer — but not into a mesh. Joining
       every pair that leads on wildlife draws fifty-five lines for eleven
       countries, which is a hairball and says nothing: of course they are all
       connected, that is what the filter did. So each country is joined to the
       nearest other country in the answer, and to nobody else. Eleven lines,
       and they trace the shape of the answer across the continent instead of
       burying it. */
    if (state.want) {
      var pool = Object.keys(lit);
      pool.forEach(function (a) {
        var best = null, bestKm = Infinity;
        pool.forEach(function (b) {
          if (a === b) return;
          var km = ((LINKS.km || {})[a] || {})[b];
          if (km == null) {
            var pa = (LINKS.nodes[a] || {}).at, pb = (LINKS.nodes[b] || {}).at;
            km = (pa && pb) ? Math.hypot(pa[0] - pb[0], pa[1] - pb[1]) * 8 : null;
          }
          if (km != null && km < bestKm) { bestKm = km; best = b; }
        });
        if (best) edge(a, best, 'lens', false);
      });
    }
    if (focus) {
      (LINKS.links[focus] || []).slice(0, 5).forEach(function (r) {
        edge(focus, r.to, r.why.some(function (w) { return w.kind === 'border'; })
          ? 'border' : 'lens', true);
      });
    }

    Object.keys(LINKS.nodes).forEach(function (s) {
      var n = LINKS.nodes[s];
      if (!n.at) return;
      var tier = byslug[s] ? byslug[s].dataset.tier : 'live';
      bits.push('<circle cx="' + n.at[0] + '" cy="' + n.at[1] + '" r="'
        + (focus === s ? 9 : 6) + '" data-tier="' + esc(tier) + '"'
        + (focus === s || (!focus && lit[s]) ? ' data-lit' : '')
        + (lit[s] ? '' : ' data-dim') + '/>');
    });
    web.innerHTML = bits.join('');
  }

  function needLinks() {
    if (LINKS) return Promise.resolve(LINKS);
    return fetch('/data/links.json').then(function (r) { return r.json(); })
      .then(function (j) { LINKS = j; return j; })
      .catch(function () { LINKS = {nodes: {}, links: {}, borders: {}}; return LINKS; });
  }

  /* What is next to this country, and why. Never "you may also like": every row
     carries the evidence it was offered on, and a row with no evidence is not
     offered at all. */
  function nextBlock(slug) {
    var rows = (LINKS && LINKS.links[slug]) || [];
    if (!rows.length) return '';
    var borders = rows.filter(function (r) {
      return r.why.some(function (w) { return w.kind === 'border'; }); });
    return '<div class="at-next"><p class="at-next-head">Continue to</p><ul>'
      + rows.slice(0, 4).map(function (r) {
          return '<li><button type="button" data-go="country" data-key="' + esc(r.to) + '">'
            + '<b>' + esc(r.name) + '</b>'
            + '<span class="at-next-km">' + (r.km != null ? r.km + ' km' : '') + '</span>'
            + '<span class="at-next-why">' + r.why.map(function (w) {
                return w.kind === 'border'
                  ? '<em>' + esc(w.say) + '</em>' : esc(w.say);
              }).join(' &middot; ') + '</span></button></li>';
        }).join('') + '</ul>'
      + '<p class="at-next-note">'
      + (borders.length
         ? borders.length + (borders.length === 1 ? ' of these shares' : ' of these share')
           + ' a land border with it. '
         : 'None of these shares a land border with it. ')
      + 'Distances are straight lines between country centres, not driving times '
      + '&mdash; how long the road takes is not something we know.</p></div>';
  }

  /* Hovering a region on the continental list lights its countries. The list
     and the map are two views of the same five things, and this is the cheapest
     possible way to say so. */
  function preview(slugs) {
    lands.forEach(function (a) {
      a.toggleAttribute('data-peek', !!slugs && slugs.indexOf(a.dataset.slug) >= 0);
    });
  }

  /* The signature move: a country stops being a shape and becomes a window.
     The same path that draws the border clips the photograph, so nothing is
     swapped, nothing is re-projected, and the picture arrives inside the exact
     outline of the country it was taken in. Countries with no photograph yet
     keep their fill — which is the empty state, and is meant to look decided. */
  function windowFor(slug) {
    var c = SP.countries[slug];
    if (!c) return null;
    if (state.place && state.country === slug) {
      var pl = placeIn(slug, state.place);
      if (pl && pl.image && pl.image.url) return pl.image.url;
    }
    return c.window || null;
  }

  function paintWindow() {
    Object.keys(winBySlug).forEach(function (s) {
      var im = winBySlug[s];
      var url = state.country === s ? windowFor(s) : null;
      if (url) {
        if (im.getAttribute('href') !== url) im.setAttribute('href', url);
        im.setAttribute('data-on', '');
      } else {
        im.removeAttribute('data-on');
      }
    });
  }

  function placeIn(slug, id) {
    var pack = loaded[slug];
    if (!pack) return null;
    for (var i = 0; i < pack.places.length; i++) {
      if (pack.places[i].id === id) return pack.places[i];
    }
    return null;
  }

  /* ---- the panel --------------------------------------------------------- */

  function showPane(name) {
    Object.keys(panes).forEach(function (k) {
      panes[k].toggleAttribute('data-on', k === name);
    });
    if (panes[name]) panes[name].scrollTop = 0;
  }

  function row(attrs, no, title, line, meta) {
    return '<li><button class="at-row" type="button" ' + attrs + '>'
      + '<span class="at-row-no">' + esc(no) + '</span>'
      + '<span class="at-row-body"><b>' + esc(title) + '</b>'
      + (line ? '<span class="at-row-line">' + esc(line) + '</span>' : '')
      + (meta ? '<span class="at-row-meta">' + esc(meta) + '</span>' : '')
      + '</span><span class="at-row-go" aria-hidden="true">&rarr;</span></button></li>';
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function season(months) {
    var short = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
    return '<div class="at-season" role="img" aria-label="Best months: '
      + esc(months.map(function (m) { return SP.months[m - 1]; }).join(', ') || 'not recorded')
      + '">' + short.map(function (s, i) {
        return '<span' + (months.indexOf(i + 1) >= 0 ? ' data-on' : '') + '>' + s + '</span>';
      }).join('') + '</div>';
  }

  function who(c) {
    if (!c.operator) {
      /* Was "Not us" and "We do not run a company in <Country>". Answering
         "who takes you" by naming somebody who does not is a sentence that
         sells nothing, and it stopped being true when the ground journey
         became ours across all fifty-four. */
      return '<div class="at-who at-who--house"><span>Who takes you</span>'
        + '<b>Afrinkong</b>'
        + '<p>The ground is ours right across Africa: your vehicle, your driver '
        + 'for the whole journey, and the days shaped around what you came for.</p>'
        + '<a class="af-go" href="/journey">Plan your journey &rarr;</a></div>';
    }
    var op = c.operator;
    return '<div class="at-who"><span>Who takes you</span><b>' + esc(op.name) + '</b>'
      + '<p>' + esc(op.base) + (op.since ? ', since ' + esc(op.since) : '') + '. '
      + esc(op.line) + '</p></div>';
  }

  /* The answer pane. A lens on the continental view is a question — "I want
     mountains", "I am going in November" — and a question deserves an answer
     rather than the same list of five regions with some of it greyed out.
     Where picks.json has an opinion on this want, the answer leads with it. */
  function paneLens() {
    var pool = filtered();
    var lens = state.want ? lensByKey[state.want] : null;
    var month = state.when ? SP.months[state.when - 1] : null;
    var head, line;
    if (lens && month) { head = lens.title; line = lens.line + ' In ' + month + '.'; }
    else if (lens) { head = lens.title; line = lens.line; }
    else { head = month; line = 'Where the continent is at its best in ' + month + '.'; }

    var pick = lens ? SP.picks[state.want] : null;
    var opinion = '';
    if (pick && SP.countries[pick.country] && pool.indexOf(pick.country) >= 0) {
      opinion = '<blockquote class="at-why"><b>' + esc(pick.hook) + '</b>'
        + '<p>' + esc(pick.why) + '</p>'
        + '<button class="af-go" type="button" data-go="country" data-key="'
        + esc(pick.country) + '">Open ' + esc(SP.countries[pick.country].name)
        + ' &rarr;</button></blockquote>';
    }

    var order = pool.slice().sort(function (a, b) {
      var ta = byslug[a] ? byslug[a].dataset.tier : 'live';
      var tb = byslug[b] ? byslug[b].dataset.tier : 'live';
      if (ta !== tb) return ta === 'ours' ? -1 : 1;
      return SP.countries[a].name < SP.countries[b].name ? -1 : 1;
    });
    var rows = order.map(function (s, i) {
      var c = SP.countries[s];
      var meta = c.region;
      if (state.when) meta += ' \u00b7 ' + shortMonths(c.months);
      return row('data-go="country" data-key="' + esc(s) + '"'
        + (byslug[s] ? ' data-tier="' + esc(byslug[s].dataset.tier) + '"' : ''),
        pad2(i + 1), c.name, c.tagline, meta);
    }).join('');

    panes.lens.innerHTML =
      '<span class="af-stamp">' + (lens ? 'I want' : 'I am going') + '</span>'
      + '<h1 class="at-h1">' + esc(head) + '</h1>'
      + '<p class="at-sub">' + esc(line) + '</p>'
      + opinion
      + (pool.length
         ? '<ol class="at-rows">' + rows + '</ol>'
         : '<p class="at-empty">Nothing in the set answers to that yet. '
           + 'Twenty-two countries are written up here, not fifty-four &mdash; '
           + 'so this is a gap in the dataset, not in Africa.</p>')
      + (pool.length
         ? '<div class="at-acts"><a class="af-btn af-btn--solid" href="/journey#/'
           + briefQuery().replace('?', '?') + '">Build a journey around this<i>&rarr;</i></a>'
           + '</div>'
         : '')
      + '<p class="at-foot-note">' + pool.length
      + (pool.length === 1 ? ' country' : ' countries') + ' &middot; press one, '
      + 'or press it on the map</p>';
    showPane('lens');
  }

  /* The months a country is at its best, said in the width of a line. */
  function shortMonths(months) {
    if (!months || !months.length) return 'season not recorded';
    var s = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months.slice().sort(function (a, b) { return a - b; })
      .map(function (m) { return s[m - 1]; }).join(' ');
  }

  function paneRegion() {
    var reg = regionByKey[state.region];
    if (!reg) return;
    var scope = inScope();
    var rows = reg.countries.map(function (s, i) {
      var c = SP.countries[s];
      var off = scope.indexOf(s) < 0;
      return row('data-go="country" data-key="' + esc(s) + '"'
        + (byslug[s] ? ' data-tier="' + esc(byslug[s].dataset.tier) + '"' : '')
        + (off ? ' data-off="true"' : ''),
        pad2(i + 1), c.name, c.tagline,
        c.places + ' places \u00b7 ' + (c.operator ? c.operator.name : 'local operator'));
    }).join('');
    panes.region.innerHTML =
      '<span class="af-stamp">Region</span>'
      + '<h1 class="at-h1">' + esc(reg.name) + '</h1>'
      + '<p class="at-lede">' + esc(reg.line) + '</p>'
      + '<div class="at-terrain">' + reg.terrain.map(function (t) {
        return '<span>' + esc(t) + '</span>'; }).join('') + '</div>'
      + '<ol class="at-rows">' + rows + '</ol>'
      + narrowNote(reg.countries)
      + '<p class="at-foot-note">' + reg.countries.length + ' countries in this region</p>';
    showPane('region');
  }

  /* When a lens is on and it has excluded some of what is listed, say so. A
     filter that silently shortens a list is a filter the visitor cannot trust. */
  function narrowNote(pool) {
    if (!state.want && !state.when) return '';
    var scope = inScope();
    var off = pool.filter(function (s) { return scope.indexOf(s) < 0; });
    if (!off.length) return '';
    var bits = [];
    if (state.want) bits.push('lead on ' + lensByKey[state.want].title.toLowerCase());
    if (state.when) bits.push('are at their best in ' + SP.months[state.when - 1]);
    return '<p class="at-empty">' + off.length + ' of these do not ' + esc(bits.join(', or '))
      + ' &mdash; still listed, still open, just not what you asked for.</p>';
  }

  function paneCountry() {
    var slug = state.country, c = SP.countries[slug];
    if (!c) return;
    var pack = loaded[slug];
    var head = '<span class="af-stamp">' + esc(c.region) + '</span>'
      + '<h1 class="at-h1">' + esc(c.name) + '</h1>'
      + '<p class="at-sub">' + esc(c.tagline) + '</p>'
      + '<p class="at-body">' + esc(c.summary) + '</p>'
      + season(c.months || [])
      + (c.when ? '<p class="at-lede">' + esc(c.when) + '</p>' : '')
      + who(c);
    if (!pack) {
      panes.country.innerHTML = head
        + '<p class="at-empty">Opening ' + esc(c.name) + '&hellip;</p>';
      showPane('country');
      return;
    }
    var list = pack.places;
    if (state.want && lensByKey[state.want]) {
      var cats = lensByKey[state.want].categories;
      var hit = list.filter(function (p) { return cats.indexOf(p.id) >= 0; });
      if (hit.length) list = hit.concat(list.filter(function (p) { return cats.indexOf(p.id) < 0; }));
    }
    panes.country.innerHTML = head
      + '<ol class="at-rows">' + list.map(function (p, i) {
        return row('data-go="place" data-key="' + esc(p.id) + '"', pad2(i + 1),
                   p.title, p.text, p.group);
      }).join('') + '</ol>'
      + '<div class="at-acts">'
      + '<a class="af-btn af-btn--solid" href="' + esc(c.url) + '">Enter ' + esc(c.name)
      + '<i>&rarr;</i></a>'
      + '<a class="af-btn af-btn--quiet" href="/journey#/j/' + esc(slug) + '/'
      + briefQuery() + '">Build a journey here</a>'
      + '</div>'
      + nextBlock(slug);
    showPane('country');
  }

  /* Where we have an opinion on file, say it. picks.json is the one editorial
     answer in the dataset — the country we would actually send somebody to for
     a given want, and the thing not to do first — and a place that happens to
     be that answer should carry it rather than reading like a caption. */
  function why(slug, p) {
    var keys = p.lenses || [];
    for (var i = 0; i < keys.length; i++) {
      var pick = SP.picks[keys[i]];
      if (pick && pick.country === slug) {
        return '<blockquote class="at-why"><b>' + esc(pick.hook) + '</b>'
          + '<p>' + esc(pick.why) + '</p></blockquote>';
      }
    }
    return '';
  }

  function panePlace() {
    var slug = state.country, c = SP.countries[slug];
    var p = placeIn(slug, state.place);
    if (!p) { paneCountry(); return; }
    var tags = (p.lenses || []).map(function (k) {
      return lensByKey[k] ? '<button type="button" data-lens-go="' + esc(k) + '">'
        + esc(lensByKey[k].title) + ' across Africa</button>' : '';
    }).join('');
    panes.place.innerHTML =
      '<span class="af-stamp">' + esc(c.name) + ' \u00b7 ' + esc(p.group) + '</span>'
      + '<h1 class="at-h1">' + esc(p.title) + '</h1>'
      + '<p class="at-body">' + esc(p.text) + '</p>'
      + (tags ? '<div class="at-tags">' + tags + '</div>' : '')
      + why(slug, p)
      + who(c)
      + '<div class="at-acts">'
      + (p.url ? '<a class="af-btn af-btn--solid" href="' + esc(p.url) + '">Open '
                 + esc(p.title) + '<i>&rarr;</i></a>' : '')
      /* The tunnel, seeded with the country the visitor is standing in — the
         same #/j/<slug>/ the portraits already use. This went to /contact,
         which threw away the country and handed them an empty message box. */
      + '<a class="af-btn af-btn--quiet" href="/journey#/j/' + esc(slug) + '/">Build this journey</a>'
      + '<button class="af-btn af-btn--quiet" type="button" data-go="country" data-key="'
      + esc(slug) + '">All ' + c.places + ' in ' + esc(c.name) + '</button>'
      + '</div>';
    showPane('place');
  }

  /* ---- breadcrumb -------------------------------------------------------- */

  function paintCrumb() {
    var segs = [{go: 'africa', key: '', label: 'Africa'}];
    if (state.region) {
      segs.push({go: 'region', key: state.region, label: regionByKey[state.region].name});
    }
    if (state.country) {
      segs.push({go: 'country', key: state.country, label: SP.countries[state.country].name});
    }
    if (state.place && state.country) {
      var p = placeIn(state.country, state.place);
      if (p) segs.push({go: 'place', key: state.place, label: p.title});
    }
    crumb.innerHTML = segs.map(function (s, i) {
      var last = i === segs.length - 1;
      return (i ? '<span class="at-crumb-sep" aria-hidden="true">/</span>' : '')
        + '<button class="at-crumb-seg" type="button" data-go="' + s.go + '" data-key="'
        + esc(s.key) + '"' + (last ? ' aria-current="page"' : '') + '>' + esc(s.label)
        + '</button>';
    }).join('');
  }

  /* ---- the lenses -------------------------------------------------------- */

  function paintLenses() {
    [].forEach.call(document.querySelectorAll('[data-lens]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.lens === state.want));
    });
    [].forEach.call(document.querySelectorAll('[data-month]'), function (b) {
      b.setAttribute('aria-pressed', String(Number(b.dataset.month) === state.when));
    });
    var n = filtered().length;
    var say = n + (n === 1 ? ' country' : ' countries');
    if (state.want) say += ' lead on ' + lensByKey[state.want].title.toLowerCase();
    if (state.when) say += (state.want ? ', at their best in ' : ' are at their best in ')
      + SP.months[state.when - 1];
    if (!state.want && !state.when) {
      say = n + ' countries \u00b7 ' + Object.keys(SP.countries).reduce(function (t, s) {
        return t + SP.countries[s].places; }, 0) + ' places';
    }
    count.textContent = say;
  }

  /* ---- render ------------------------------------------------------------ */

  function render(fly) {
    root.dataset.level = state.level;
    paintLenses();
    paintMap();
    paintCrumb();
    if (state.level === 'africa') {
      if (state.want || state.when) paneLens(); else showPane('africa');
    }
    else if (state.level === 'region') paneRegion();
    else if (state.level === 'country') paneCountry();
    else if (state.level === 'place') panePlace();
    if (fly !== false) flyTo(target());
  }

  function target() {
    if (state.country && SP.countries[state.country]) {
      var box = SP.countries[state.country].view;
      /* Opening a place pushes in a little further. There is no coordinate for
         a place in this dataset and none is invented here — but a descent that
         moves the map is a descent you can feel, and the country is still the
         only thing being claimed. */
      if (state.level !== 'place') return box;
      var k = 0.86;
      return [box[0] + box[2] * (1 - k) / 2, box[1] + box[3] * (1 - k) / 2,
              box[2] * k, box[3] * k];
    }
    if (state.region && regionByKey[state.region]) return regionByKey[state.region].view;
    /* A lens on the continental view flies to the countries it found, which is
       the answer to "where" drawn rather than written. */
    var pool = filtered();
    if ((state.want || state.when) && pool.length) {
      var boxes = pool.map(function (s) { return SP.countries[s].box; }).filter(Boolean);
      if (boxes.length) {
        var x0 = Math.min.apply(null, boxes.map(function (b) { return b[0]; }));
        var y0 = Math.min.apply(null, boxes.map(function (b) { return b[1]; }));
        var x1 = Math.max.apply(null, boxes.map(function (b) { return b[0] + b[2]; }));
        var y1 = Math.max.apply(null, boxes.map(function (b) { return b[1] + b[3]; }));
        var m = Math.max(x1 - x0, y1 - y0) * 0.1;
        return [x0 - m, y0 - m, (x1 - x0) + 2 * m, (y1 - y0) + 2 * m];
      }
    }
    return SP.view;
  }

  /* ---- moving ------------------------------------------------------------ */

  function fetchPlaces(slug) {
    if (loaded[slug]) return Promise.resolve(loaded[slug]);
    return fetch('/data/atlas/' + encodeURIComponent(slug) + '.json')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (pack) { loaded[slug] = pack; return pack; })
      .catch(function () {
        /* A country whose places will not load is still a country: the summary,
           the season and the operator are already here, so it degrades to that
           rather than to an error page. */
        loaded[slug] = {slug: slug, name: SP.countries[slug].name, places: []};
        return loaded[slug];
      });
  }

  function go(level, key, push) {
    if (level === 'africa') {
      state.level = 'africa'; state.region = null; state.country = null; state.place = null;
    } else if (level === 'region') {
      if (!regionByKey[key]) return;
      state.level = 'region'; state.region = key; state.country = null; state.place = null;
    } else if (level === 'country') {
      if (!SP.countries[key]) return;
      state.level = 'country'; state.country = key;
      state.region = SP.countries[key].regionKey || state.region;
      state.place = null;
    } else if (level === 'place') {
      if (!state.country) return;
      state.level = 'place'; state.place = key;
    }
    if (push !== false) writeHash();
    if (level === 'region') track('atlas_region_opened', {region: state.region});
    else if (level === 'country') {
      track('atlas_country_opened', {country: state.country,
        region: SP.countries[state.country] && SP.countries[state.country].regionKey});
    } else if (level === 'place') track('atlas_place_opened', {country: state.country});
    render();
    if ((level === 'country' || level === 'place') && state.country) {
      var slug = state.country;
      needLinks().then(function () {
        if (state.country === slug && state.level === 'country') { paneCountry(); paintWeb(); }
      });
      fetchPlaces(slug).then(function () {
        if (state.country !== slug) return;
        if (state.level === 'country') paneCountry();
        else if (state.level === 'place') { panePlace(); paintCrumb(); paintWindow(); }
      });
    }
  }

  /* ---- the address bar --------------------------------------------------- */

  function writeHash() {
    var path = ['#'];
    if (state.region) path.push(state.region);
    if (state.country) path.push(state.country);
    if (state.place) path.push(state.place);
    var q = [];
    if (state.want) q.push('want=' + state.want);
    if (state.when) q.push('when=' + state.when);
    var h = path.join('/') + (q.length ? '?' + q.join('&') : '');
    if (h === (location.hash || '#')) return;
    history.pushState(null, '', h);
  }

  function readHash(push) {
    var raw = (location.hash || '').replace(/^#\/?/, '');
    var parts = raw.split('?');
    var path = parts[0] ? parts[0].split('/').filter(Boolean) : [];
    var q = {};
    (parts[1] || '').split('&').forEach(function (kv) {
      var bits = kv.split('=');
      if (bits[0]) q[bits[0]] = decodeURIComponent(bits[1] || '');
    });
    state.want = lensByKey[q.want] ? q.want : null;
    state.when = /^([1-9]|1[0-2])$/.test(q.when) ? Number(q.when) : null;

    var level = 'africa', region = null, country = null, place = null;
    path.forEach(function (seg) {
      if (regionByKey[seg] && !country) { region = seg; level = 'region'; }
      else if (SP.countries[seg]) {
        country = seg; level = 'country';
        region = SP.countries[seg].regionKey || region;
      } else if (country) { place = seg; level = 'place'; }
    });
    state.level = level; state.region = region; state.country = country; state.place = place;
    render();
    if (country) {
      needLinks().then(function () {
        if (state.country === country && state.level === 'country') {
          paneCountry(); paintWeb();
        }
      });
      fetchPlaces(country).then(function () {
        if (state.country !== country) return;
        if (state.level === 'country') paneCountry();
        else { panePlace(); paintCrumb(); }
        paintWindow();
      });
    }
    if (push) writeHash();
  }

  /* ---- events ------------------------------------------------------------ */

  /* One listener for the whole page. Every control is a button or a link with a
     data attribute saying where it goes, so adding a rung is markup, not code. */
  document.addEventListener('click', function (e) {
    var land = e.target.closest ? e.target.closest('.at-c') : null;
    if (land) {
      e.preventDefault();
      go('country', land.dataset.slug);
      return;
    }
    var b = e.target.closest ? e.target.closest('[data-go]') : null;
    if (b) { e.preventDefault(); go(b.dataset.go, b.dataset.key); return; }
    var lens = e.target.closest ? e.target.closest('[data-lens]') : null;
    if (lens) {
      state.want = state.want === lens.dataset.lens ? null : lens.dataset.lens;
      if (state.want) track('atlas_lens_used', {want: state.want, month: state.when});
      if (state.level === 'africa' || state.level === 'region') { writeHash(); render(); }
      else { writeHash(); render(false); }
      return;
    }
    var jump = e.target.closest ? e.target.closest('[data-lens-go]') : null;
    if (jump) {
      state.want = jump.dataset.lensGo;
      go('africa', null);
      return;
    }
    var mode = e.target.closest ? e.target.closest('[data-mode]') : null;
    if (mode) {
      state.web = mode.dataset.mode === 'links';
      [].forEach.call(document.querySelectorAll('[data-mode]'), function (b) {
        b.setAttribute('aria-pressed', String((b.dataset.mode === 'links') === state.web));
      });
      if (state.web) track('atlas_links_opened', {want: state.want});
      needLinks().then(function () { paintWeb(); });
      return;
    }
    var mon = e.target.closest ? e.target.closest('[data-month]') : null;
    if (mon) {
      var m = Number(mon.dataset.month);
      state.when = state.when === m ? null : m;
      if (state.level === 'africa' || state.level === 'region') { writeHash(); render(); }
      else { writeHash(); render(false); }
    }
  });

  /* A row of twelve months is one control, not twelve tab stops. ARIA calls
     this a toolbar: Tab reaches it, the arrow keys move inside it, Tab leaves.
     Without it a keyboard user walks past eighteen chips to reach the panel. */
  function toolbar(box) {
    var items = [].slice.call(box.querySelectorAll('button'));
    if (items.length < 2) return;
    var group = box.closest('[aria-label]');
    box.setAttribute('role', 'toolbar');
    if (group) box.setAttribute('aria-label', group.getAttribute('aria-label'));
    items.forEach(function (b, i) { b.tabIndex = i ? -1 : 0; });
    box.addEventListener('keydown', function (e) {
      var i = items.indexOf(document.activeElement);
      if (i < 0) return;
      var n;
      if (e.key === 'ArrowRight') n = (i + 1) % items.length;
      else if (e.key === 'ArrowLeft') n = (i - 1 + items.length) % items.length;
      else if (e.key === 'Home') n = 0;
      else if (e.key === 'End') n = items.length - 1;
      else return;
      e.preventDefault();
      items.forEach(function (b) { b.tabIndex = -1; });
      items[n].tabIndex = 0;
      items[n].focus();
    });
  }
  [].forEach.call(document.querySelectorAll('.at-chips'), toolbar);

  /* Take me somewhere. Not random: it draws from what the lenses currently
     allow, prefers a country you have not been sent to yet, and opens it on the
     place that country leads with — which is an editor's answer, not a shuffle. */
  var surprise = document.getElementById('at-surprise');
  if (surprise) {
    surprise.addEventListener('click', function () {
      var pool = filtered();
      if (!pool.length) return;
      var fresh = pool.filter(function (s) { return !seen[s]; });
      if (!fresh.length) { seen = {}; fresh = pool; }
      var slug = fresh[Math.floor(Math.random() * fresh.length)];
      seen[slug] = true;
      track('surprise_taken', {country: slug, want: state.want, month: state.when});
      fetchPlaces(slug).then(function (pack) {
        go('country', slug);
        if (pack.places.length) go('place', pack.places[0].id);
      });
    });
  }

  /* Keyboard. The map is a set of links, so Tab already reaches every country;
     these add the two things a map needs and links do not — stepping to the
     next country in view, and getting back out. */
  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    if (e.key === 'Escape') {
      if (state.level === 'place') go('country', state.country);
      else if (state.level === 'country') go('region', state.region);
      else if (state.level === 'region') go('africa', null);
      return;
    }
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    var here = e.target.closest ? e.target.closest('.at-c') : null;
    if (!here) return;
    e.preventDefault();
    var open = lands.filter(function (a) { return !a.hasAttribute('data-dim'); });
    var i = open.indexOf(here);
    if (i < 0) return;
    var next = open[(i + (e.key === 'ArrowRight' ? 1 : open.length - 1)) % open.length];
    rove(next);
    next.focus();
  });

  ['pointerover', 'focusin'].forEach(function (ev) {
    panel.addEventListener(ev, function (e) {
      var b = e.target.closest ? e.target.closest('[data-slugs]') : null;
      preview(b ? b.dataset.slugs.split(' ') : null);
    });
  });
  ['pointerleave', 'focusout'].forEach(function (ev) {
    panel.addEventListener(ev, function () { preview(null); });
  });

  var resized = null;
  window.addEventListener('resize', function () {
    clearTimeout(resized);
    resized = setTimeout(declutter, 150);
  });

  window.addEventListener('popstate', function () { readHash(false); });
  window.addEventListener('hashchange', function () { readHash(false); });

  apply();
  readHash(false);
})();
