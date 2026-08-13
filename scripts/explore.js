/* Explore Africa — the universal index. Cmd/Ctrl-K, or / , or the button.
 * ---------------------------------------------------------------------------
 * Nine prompts built nine surfaces: a map, a builder, seven human doors, five
 * hundred and seventy-two addresses, twenty-two long reads. Each one was a good
 * way in and each one was a *different* way in, which is what makes a product
 * feel like a folder of features. This is the answer to that: one index over
 * all of it, reachable with the same keystroke from any page on the site,
 * including the 404.
 *
 * It searches everything the build wrote down, and nothing else:
 *
 *   countries    22 portraits, by name or by the adjective
 *   places       572 write-ups, by their own captions
 *   stories      220 chapters, by headline
 *   names        581 proper names read out of the dataset's own sentences
 *   sections     the map, the builder, the human layer, the reading room
 *
 * What it deliberately is not: a guesser. There is no model behind it, no fuzzy
 * distance, no "did you mean". A query it cannot match against one of those five
 * lists returns nothing and says so, because the alternative — rounding an
 * unknown word to the nearest thing in stock — is how a travel site ends up
 * answering a question about a country it has never written about.
 *
 * Cost: nothing until it is opened. The index is two fetches on first use, and
 * a visitor who never presses the key never pays for it.
 */
(function () {
  'use strict';

  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };

  var KINDS = [
    ['country', 'Countries'],
    ['story', 'Stories'],
    ['place', 'Places'],
    ['name', 'Named in the writing'],
    ['go', 'Go to']
  ];

  /* The site's own rooms, so the index can move you as well as find things. */
  var ROOMS = [
    {kind: 'go', label: 'The Atlas', sub: 'The continent, region by region', url: '/atlas',
     words: 'atlas map continent regions explore geography'},
    {kind: 'go', label: 'Build a journey', sub: 'Four questions, then somewhere to go',
     url: '/journey', words: 'journey build plan itinerary trip route'},
    {kind: 'go', label: 'Meet Africa', sub: 'Seven doors into who lives here', url: '/meet',
     words: 'meet people human culture who lives'},
    {kind: 'go', label: 'Stories', sub: 'Twenty-two portraits, at reading length',
     url: '/stories', words: 'stories reading portraits editorial read'},
    {kind: 'go', label: 'Every place', sub: 'The plain list of everything written up',
     url: '/places', words: 'places index list everything all'},
    {kind: 'go', label: 'Enquire', sub: 'Talk to the company who works there',
     url: '/contact', words: 'contact enquire enquiry book talk email'}
  ];

  var dialog = null, box = null, list = null, status = null, opener = null;
  var rows = null, loading = null, active = -1, shown = [];

  /* ---- the index ---------------------------------------------------------- */

  function build(graph, stories) {
    var out = ROOMS.slice();
    var countries = graph.countries || {};
    Object.keys(countries).forEach(function (slug) {
      var c = countries[slug];
      out.push({kind: 'country', label: c.name, sub: c.tagline || c.region,
                url: '/portrait/' + slug,
                words: [c.name, c.adjective, c.region, slug.replace(/-/g, ' ')].join(' ')});
      var places = c.places || {};
      Object.keys(places).forEach(function (cat) {
        var p = places[cat];
        if (!p.u) return;
        out.push({kind: 'place', label: p.t, sub: c.name, url: p.u,
                  words: p.t + ' ' + c.name + ' ' + cat.replace(/-/g, ' ')});
      });
    });
    (stories || []).forEach(function (s) {
      out.push({kind: 'story', label: s.title, sub: s.countryName + ' · ' + s.arcTitle,
                url: s.url, words: s.title + ' ' + s.countryName + ' ' + s.arcTitle});
    });
    var names = graph.names || {};
    Object.keys(names).forEach(function (n) {
      var row = names[n], at = (row.at || [])[0];
      if (!at) return;
      var c = countries[at.c] || {};
      var addr = ((c.places || {})[at.e] || {}).u;
      if (!addr) return;
      out.push({kind: 'name', label: n,
                sub: 'in ' + row.n + (row.n === 1 ? ' write-up · ' : ' write-ups · ')
                  + (row.in || []).map(function (s) {
                    return (countries[s] || {}).name || s;
                  }).slice(0, 3).join(', '),
                url: addr, words: n});
    });
    out.forEach(function (r) { r.hay = (' ' + r.words + ' ').toLowerCase(); });
    return out;
  }

  function load() {
    if (loading) return loading;
    loading = Promise.all([
      fetch('/data/graph.json').then(function (r) { return r.json(); }),
      fetch('/data/stories.json').then(function (r) { return r.json(); })
    ]).then(function (both) {
      rows = build(both[0], (both[1] || {}).stories || []);
      return true;
    }).catch(function () { rows = null; return false; });
    return loading;
  }

  /* Rank: a label that starts with the query beats a word that starts with it,
     which beats a match anywhere. No scoring beyond that — a search that cannot
     explain its own order is a search nobody trusts. */
  function match(query) {
    var q = query.trim().toLowerCase();
    if (!q || !rows) return [];
    var hits = [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i], low = r.label.toLowerCase(), rank = -1;
      if (low.indexOf(q) === 0) rank = 0;
      else if (r.hay.indexOf(' ' + q) >= 0) rank = 1;
      else if (r.hay.indexOf(q) >= 0) rank = 2;
      if (rank >= 0) hits.push({r: r, rank: rank, len: low.length});
    }
    hits.sort(function (a, b) {
      return a.rank - b.rank || a.len - b.len || a.r.label.localeCompare(b.r.label);
    });
    return hits.map(function (h) { return h.r; });
  }

  /* ---- the dialog --------------------------------------------------------- */

  function esc(t) {
    return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function make() {
    dialog = document.createElement('div');
    dialog.className = 'ex';
    dialog.hidden = true;
    dialog.innerHTML =
      '<div class="ex-veil" data-close></div>'
      + '<div class="ex-panel" role="dialog" aria-modal="true" aria-labelledby="ex-h">'
      + '<h2 class="ex-h" id="ex-h">Explore Africa</h2>'
      + '<div class="ex-bar"><input id="ex-q" type="text" autocomplete="off"'
      + ' spellcheck="false" aria-controls="ex-list" aria-describedby="ex-status"'
      + ' placeholder="A country, a place, a name — Bwindi, Lalibela, Kampala">'
      + '<button type="button" class="ex-esc" data-close>Esc</button></div>'
      + '<p class="ex-status" id="ex-status" role="status"></p>'
      + '<div class="ex-list" id="ex-list" role="listbox" aria-label="Results"></div>'
      + '<p class="ex-foot">Twenty-two countries are written up here. The rest of '
      + 'Africa is not yet, and nothing is guessed.</p>'
      + '</div>';
    document.body.appendChild(dialog);
    box = dialog.querySelector('#ex-q');
    list = dialog.querySelector('#ex-list');
    status = dialog.querySelector('#ex-status');

    dialog.addEventListener('click', function (ev) {
      if (ev.target.hasAttribute && ev.target.hasAttribute('data-close')) close();
      var hit = ev.target.closest && ev.target.closest('.ex-row');
      if (hit) track('explore_opened', {kind: hit.getAttribute('data-kind')});
    });
    box.addEventListener('input', function () { paint(box.value); });
    box.addEventListener('keydown', keys);
  }

  function paint(query) {
    shown = match(query).slice(0, 40);
    active = -1;
    if (!rows) {
      status.textContent = 'The index could not be loaded. This is not "no results".';
      list.innerHTML = '';
      return;
    }
    if (!query.trim()) {
      status.textContent = '';
      list.innerHTML = ROOMS.map(function (r, i) { return row(r, i); }).join('');
      shown = ROOMS.slice();
      return;
    }
    if (!shown.length) {
      status.textContent = 'Nothing here matches that.';
      list.innerHTML = '<p class="ex-none">This site has not been rounded to the '
        + 'nearest thing it does have. Twenty-two countries are written up; if '
        + 'what you asked for is not among them, it is not here yet.</p>';
      return;
    }
    status.textContent = shown.length + (shown.length === 1 ? ' result' : ' results');
    var html = '', n = 0;
    KINDS.forEach(function (pair) {
      var group = shown.filter(function (r) { return r.kind === pair[0]; });
      if (!group.length) return;
      html += '<p class="ex-group">' + esc(pair[1]) + '</p>';
      group.forEach(function (r) { html += row(r, n++); });
    });
    /* Re-order `shown` to match what was painted, so the arrow keys walk the
       list a reader is actually looking at rather than the order it was found. */
    shown = KINDS.reduce(function (acc, pair) {
      return acc.concat(shown.filter(function (r) { return r.kind === pair[0]; }));
    }, []);
    list.innerHTML = html;
  }

  function row(r, i) {
    return '<a class="ex-row" role="option" aria-selected="false" id="ex-r' + i + '"'
      + ' data-kind="' + esc(r.kind) + '" href="' + esc(r.url) + '">'
      + '<b>' + esc(r.label) + '</b><span>' + esc(r.sub) + '</span></a>';
  }

  function move(step) {
    var all = list.querySelectorAll('.ex-row');
    if (!all.length) return;
    if (active >= 0 && all[active]) {
      all[active].setAttribute('aria-selected', 'false');
      all[active].classList.remove('is-on');
    }
    active = (active + step + all.length) % all.length;
    all[active].setAttribute('aria-selected', 'true');
    all[active].classList.add('is-on');
    all[active].scrollIntoView({block: 'nearest'});
    box.setAttribute('aria-activedescendant', all[active].id);
  }

  function keys(ev) {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); move(1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); move(-1); }
    else if (ev.key === 'Enter') {
      var all = list.querySelectorAll('.ex-row');
      var pick = all[active >= 0 ? active : 0];
      if (pick) {
        ev.preventDefault();
        track('explore_opened', {kind: pick.getAttribute('data-kind')});
        location.href = pick.getAttribute('href');
      }
    } else if (ev.key === 'Escape') { ev.preventDefault(); close(); }
  }

  function open(seed) {
    if (!dialog) make();
    opener = document.activeElement;
    dialog.hidden = false;
    document.documentElement.classList.add('ex-open');
    box.value = seed || '';
    status.textContent = 'Reading the index…';
    box.focus();
    track('explore_opened', {kind: 'open'});
    load().then(function () { paint(box.value); });
  }

  function close() {
    if (!dialog || dialog.hidden) return;
    dialog.hidden = true;
    document.documentElement.classList.remove('ex-open');
    /* Focus goes back where it came from. A dialog that dumps you at the top of
       the document is a dialog that has to be escaped twice. */
    if (opener && opener.focus) opener.focus();
  }

  /* ---- the ways in -------------------------------------------------------- */

  addEventListener('keydown', function (ev) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((ev.target.tagName || ''))
      || ev.target.isContentEditable;
    if ((ev.metaKey || ev.ctrlKey) && (ev.key === 'k' || ev.key === 'K')) {
      ev.preventDefault();
      dialog && !dialog.hidden ? close() : open();
      return;
    }
    if (ev.key === '/' && !typing && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
      ev.preventDefault();
      open();
    }
  });

  /* A visible affordance, because a keystroke nobody is told about is not a
     feature — and because a phone has no Cmd key. Injected into whichever
     masthead this page happens to carry, so the six mastheads on this site do
     not each need editing.
     
     Placed *beside* the nav rather than inside it. Every masthead on this site
     hides its list of routes below about a thousand pixels, and a button inside
     a hidden list is a hidden button — which would have made the index, the one
     thing that works the same everywhere, reachable on desktop only. On a phone
     it is the only way in besides the five links, so it cannot be the thing
     that disappears first. */
  addEventListener('DOMContentLoaded', function () {
    var nav = document.querySelector('.pl-routes,.at-routes,.jn-routes,.mt-routes,'
      + '.wa-routes,.fj-routes,.routes');
    if (!nav || !nav.parentElement
        || nav.parentElement.querySelector('.ex-key')) return;
    var mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'ex-key';
    b.innerHTML = 'Explore <kbd>' + (mac ? '⌘' : 'Ctrl') + 'K</kbd>';
    b.setAttribute('aria-label', 'Explore Africa — search every country, place and story');
    b.addEventListener('click', function () { open(); });
    nav.parentElement.insertBefore(b, nav.nextSibling);
  });

  window.AfrinkongExplore = {open: open, close: close, match: match, build: build};
}());
