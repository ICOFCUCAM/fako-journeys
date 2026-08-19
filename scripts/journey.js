/* The journey engine's interface.
 * ---------------------------------------------------------------------------
 * The reasoning lives in journey-engine.js and is not touched here. This file
 * does three things: it moves through four questions one at a time, it puts the
 * answer on screen, and it lets the answer be edited, saved, and sent.
 *
 * The address bar is the state. A journey that has been composed is written
 * into the hash, so a reload restores it, Back steps out of it, and the link
 * somebody sends is the journey they were looking at — no account, no record on
 * a server, nothing that stops meaning anything the day the database moves.
 */
(function () {
  'use strict';

  var E = window.AfrinkongJourney;
  /* Counting, not following. The layer drops anything not named in the schema
     and strips any property not allowed under its event, so the sentence a
     visitor types into the box below has nowhere to go — which is the one thing
     on this page that would be tempting to record and must not be. */
  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };
  var node = document.getElementById('jn-data');
  if (!E || !node) return;
  var D = JSON.parse(node.textContent);

  var root = document.getElementById('jn');
  var form = document.getElementById('ask');
  var reveal = document.getElementById('reveal');
  var compose = document.getElementById('compose');
  var steps = [].slice.call(form.querySelectorAll('.jn-step'));
  var dots = [].slice.call(form.querySelectorAll('.jn-progress span'));
  var reduced = matchMedia('(prefers-reduced-motion: reduce)');
  var SAVED = 'afrinkong-journeys';

  var brief = {wants: [], month: null, pacing: 'open', party: null, style: [], seed: 0,
               start: null};   /* a country named on the way in, from a link or a sentence */
  var picks = [];              /* the three the engine returned */
  var chosen = null;           /* the one being composed */
  var places = {};             /* slug -> the atlas payload, fetched once */
  var LINKS = null;            /* data/links.json, fetched when a journey opens */
  var stages = [];             /* place ids, in order */
  var step = 1;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }
  function val(name) {
    var el = form.querySelector('[name="' + name + '"]:checked');
    return el ? el.value : null;
  }
  function vals(name) {
    return [].map.call(form.querySelectorAll('[name="' + name + '"]:checked'),
      function (el) { return el.value; }).filter(Boolean);
  }

  function readForm() {
    brief.wants = vals('want');
    var m = val('month');
    brief.month = m ? Number(m) : null;
    brief.pacing = val('pacing') || 'open';
    brief.party = val('party');
    brief.style = vals('style');
  }

  /* ---- the four questions ------------------------------------------------ */

  var painted = false;
  function show(n) {
    step = Math.max(1, Math.min(steps.length, n));
    root.dataset.step = String(step);
    steps.forEach(function (s) { s.hidden = Number(s.dataset.step) !== step; });
    dots.forEach(function (d, i) { d.toggleAttribute('data-on', i < step); });
    /* Moving focus onto the new question is what tells a screen reader the
       page has changed under it. Not on the first paint, though: stealing
       focus on arrival puts the masthead behind the visitor before they have
       pressed anything. */
    var h = steps[step - 1].querySelector('.jn-h1');
    if (h && painted) { h.setAttribute('tabindex', '-1'); h.focus({preventScroll: true}); }
    if (painted) window.scrollTo({top: 0, behavior: reduced.matches ? 'auto' : 'smooth'});
    painted = true;
  }

  form.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('button') : null;
    if (!t) return;
    if (t.hasAttribute('data-next')) {
      readForm();
      track('question_answered', {step: step, wants: brief.wants.length,
        month: brief.month, pacing: brief.pacing, party: brief.party});
      show(step + 1);
    }
    else if (t.hasAttribute('data-back')) show(step - 1);
    else if (t.hasAttribute('data-open')) {
      /* "I don't know yet" is a real answer, not a skip: it drops the
         experience question and lets season, depth and who runs the place do
         the ranking, which is exactly what somebody with no preference wants. */
      form.querySelectorAll('[name="want"]:checked').forEach(function (i) {
        i.checked = false;
      });
      readForm();
      show(2);
    } else if (t.hasAttribute('data-reveal')) { readForm(); runReveal(); }
    else if (t.hasAttribute('data-read')) readSentence();
  });
  form.addEventListener('submit', function (e) { e.preventDefault(); readForm(); runReveal(); });

  /* A sentence, turned into the same answers the buttons give. It fills the
     controls rather than skipping them, so the visitor sees the reading and can
     correct it before anything is decided — a parser that acts on its own
     interpretation is a parser you cannot argue with. */
  function readSentence() {
    var box = document.getElementById('jn-said-it');
    var out = document.getElementById('jn-say-got');
    if (!box) return;
    var got = E.parse(box.value, D);
    var set = function (name, value) {
      var el = value && form.querySelector('[name="' + name + '"][value="' + value + '"]');
      if (el) { el.checked = true; return true; }
      return false;
    };
    form.querySelectorAll('[name="want"]:checked').forEach(function (i) { i.checked = false; });
    got.wants.forEach(function (k) { set('want', k); });
    if (got.month) set('month', got.month);
    if (got.pacing) set('pacing', got.pacing);
    if (got.party) set('party', got.party);
    readForm();
    if (got.country) brief.start = got.country;
    if (!got.took.length) {
      out.textContent = got.missed.join(' ') + ' Use the choices below instead.';
      out.setAttribute('data-warn', '');
      return;
    }
    out.removeAttribute('data-warn');
    /* How many things it understood, never what was typed. */
    track('sentence_read', {wants: got.wants.length, month: got.month,
                            pacing: got.pacing});
    out.textContent = 'Read as: ' + got.took.map(function (t) {
      return t.say + (t.band ? ' (' + t.band + ')' : ''); }).join(' \u00b7 ')
      + '. Everything below is still yours to change.';
  }

  /* ---- the reveal -------------------------------------------------------- */

  function runReveal(quiet) {
    var out = E.recommend(D, brief, 3);
    picks = out.picks;
    /* Somebody who arrived saying "Uganda" gets Uganda first — but ranked and
       explained like everything else, and with the alternatives still there. */
    if (brief.start && D.countries[brief.start]) {
      var named = E.rank(D, brief).filter(function (p) { return p.slug === brief.start; })[0]
        || {slug: brief.start, reasons: [], outOfSeason: false, matched: []};
      picks = [named].concat(picks.filter(function (p) { return p.slug !== brief.start; }))
        .slice(0, 3);
    }
    if (!picks.length) { noAnswer(); return; }
    chosen = picks[0];
    form.hidden = true;
    compose.hidden = true;
    reveal.hidden = false;
    paintReveal();
    var b = E.band(D, brief, chosen);
    track('journey_revealed', {country: chosen.slug, band: b && b.label,
      wants: brief.wants.length, month: brief.month});
    if (!quiet && !reduced.matches) {
      reveal.setAttribute('data-arriving', '');
      setTimeout(function () { reveal.removeAttribute('data-arriving'); }, 40);
    }
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  /* Asked for something nothing in the set leads on. Say that plainly and say
     what would be closest, rather than shrugging or inventing a match. */
  function noAnswer() {
    form.hidden = true;
    reveal.hidden = false;
    document.getElementById('jn-shape').innerHTML = '';
    document.getElementById('jn-name').textContent = 'Not yet';
    document.getElementById('jn-tag').textContent =
      'Twenty-two of Africa’s fifty-four countries are written up here, and '
      + 'none of them leads on everything you asked for at once.';
    var loose = E.recommend(D, {wants: brief.wants.slice(0, 1), month: brief.month,
      seed: brief.seed}, 3);
    document.getElementById('jn-why').innerHTML = loose.picks.length
      ? '<p class="jn-why-head">Closest, on one of the things you asked for</p>'
        + '<ul class="jn-why-list">' + loose.picks.map(function (p) {
          return '<li><button type="button" data-alt="' + esc(p.slug) + '">'
            + esc(D.countries[p.slug].name) + ' &mdash; '
            + esc(D.countries[p.slug].tagline) + '</button></li>';
        }).join('') + '</ul>'
      : '';
    document.getElementById('jn-alts').innerHTML = '';
  }

  /* The window, from the one place it is defined. The journey page carries the
     silhouettes in its own payload because the reveal has to be instant — there
     is no moment to fetch in between the last question and the answer. */
  function shapeOf(slug) {
    var c = D.countries[slug];
    if (!c || !c.shape) return '';
    return window.AfrinkongWindow.svg(c.shape, {
      image: c.window, alt: c.windowAlt, name: c.name, ident: 'jw',
      classes: 'af-window-svg'});
  }

  function paintReveal() {
    var c = D.countries[chosen.slug];
    document.getElementById('jn-shape').innerHTML = shapeOf(chosen.slug);
    document.getElementById('jn-name').textContent = c.name;
    document.getElementById('jn-tag').textContent = c.tagline;
    document.getElementById('jn-why').innerHTML = meetsBlock(c) + whyBlock(chosen);
    document.getElementById('jn-alts').innerHTML = picks.slice(1).map(function (p, i) {
      var a = D.countries[p.slug];
      return '<button class="jn-alt" type="button" data-alt="' + esc(p.slug) + '">'
        + '<span class="jn-alt-no">0' + (i + 2) + '</span>'
        + '<span class="jn-alt-body"><b>' + esc(a.name) + '</b>'
        + '<span class="jn-alt-line">' + esc(a.tagline) + '</span>'
        + '<span class="jn-alt-why">' + esc(oneLine(p)) + '</span></span>'
        + '<span class="jn-alt-go" aria-hidden="true">&rarr;</span></button>';
    }).join('');
    paintField();
    paintMap();
  }

  /* The continent, coloured rather than filtered.
     Every country stays on the page and stays clickable. What a lens changes
     is the colour, not the population — and the line under each name is always
     what that country leads on, never what it does not. "Senegal — Cities,
     Culture, Food, Coast" says everything "no wildlife in Senegal" would have
     said, without the site being the one to say no. */
  function paintField() {
    var grid = document.getElementById('jn-field-grid');
    if (!grid) return;
    var sec = document.getElementById('jn-field');
    if (sec) sec.hidden = false;
    var rows = E.field(D, brief);
    var say = document.getElementById('jn-field-say');
    var strong = rows.filter(function (r) { return r.match === 'leads'; }).length;
    if (say) {
      say.textContent = brief.wants.length
        ? strong + ' of the fifty-four lead on what you asked for. The rest are '
          + 'here too, and any of them can be your journey.'
        : 'Choose any one, or answer the questions again and watch them re-colour.';
    }
    grid.innerHTML = rows.map(function (r) {
      return '<button class="jn-c" type="button" data-country="' + esc(r.slug) + '"'
        + ' data-match="' + r.match + '"'
        + (chosen && chosen.slug === r.slug ? ' data-picked="true"' : '')
        + (r.inSeason ? '' : ' data-off="true"')
        + '><b>' + esc(r.name) + '</b>'
        + '<span class="jn-c-for">' + esc(r.leads.join(' \u00b7 ')) + '</span>'
        + '</button>';
    }).join('');
  }

  /* ---- the continent ----------------------------------------------------- */

  /* EVERY ANSWER LANDS ON THE MAP, AND IT LANDS AS THE ANSWER IS GIVEN.
   *
   * The country grid says the same thing, and says it once, at the end. The
   * map's job is different: it is the only part of this page that can answer
   * a question before the question after it has been asked, which is what
   * makes four questions feel like a conversation rather than a form.
   *
   * It writes the same three attributes the grid writes, off the same rows
   * from the same engine call. Nothing here decides anything — if the map and
   * the grid ever disagree it is because one of them stopped calling
   * E.field(), and that is a bug with one place to look.
   */
  var mapEl = document.getElementById('jn-map');
  var mapSay = document.getElementById('jn-map-say');
  var mapKey = document.getElementById('jn-map-key');
  var mapC = mapEl
    ? [].slice.call(mapEl.querySelectorAll('.jn-map-c')) : [];
  var mapBy = {};
  mapC.forEach(function (el) { mapBy[el.getAttribute('data-slug')] = el; });

  function paintMap() {
    if (!mapC.length) return;
    var rows = E.field(D, brief);
    var lit = 0;
    rows.forEach(function (r) {
      var el = mapBy[r.slug];
      if (!el) return;
      el.setAttribute('data-match', r.match);
      if (r.match === 'leads') lit++;
      if (r.inSeason) el.removeAttribute('data-off');
      else el.setAttribute('data-off', 'true');
      if (chosen && chosen.slug === r.slug) {
        el.setAttribute('data-picked', 'true');
        /* The tab stop follows the choice: a reader who picks Kenya and comes
           back to the map should land on Kenya. */
        if (typeof focusable === 'function') focusable(el);
      } else { el.removeAttribute('data-picked'); }
    });
    var asked = (brief.wants || []).length || brief.month;
    if (mapKey) mapKey.hidden = !asked;
    /* Once a journey is drawn the caption belongs to the journey. Both of
       these write the same element and the composer's sentence is the more
       specific one, so the field's sentence gives way rather than racing it. */
    if (routeEl && routeEl.childNodes.length) return;
    if (mapSay) {
      mapSay.textContent = !asked
        ? 'Fifty-four countries. Answer a question and watch them answer back.'
        : lit + ' of the fifty-four lead on what you have asked for so far. '
          + 'Every one of them is still yours to choose.';
    }
  }

  /* ONE TAB STOP FOR FIFTY-FOUR COUNTRIES.
   *
   * The map is the first thing in the document, which is where it belongs —
   * the page's subject, above the question about it. Left as fifty-four
   * ordinary links that costs a keyboard reader fifty-four presses before the
   * first question, which is not a map being first, it is a map being in the
   * way.
   *
   * So it is navigated the way a grid is: the group takes one stop, and the
   * arrows move inside it. The roving tabindex is applied by the script, so
   * with scripting off — where there is no interactive map anyway and the
   * links ARE the content — all fifty-four stay in the tab order as plain
   * links to plain pages.
   *
   * The arrows move geographically, not in document order. Document order is
   * alphabetical, so Right from Algeria would be Angola: two thousand miles
   * south and the wrong direction entirely. Each press picks the nearest
   * centroid inside a sixty-degree cone in the direction asked for, which on a
   * map is what "right" means.
   */
  var roving = null;
  function focusable(el) {
    mapC.forEach(function (c) { c.setAttribute('tabindex', '-1'); });
    if (el) { el.setAttribute('tabindex', '0'); roving = el; }
  }
  function centre(el) {
    var raw = el && el.getAttribute('data-at');
    if (!raw) return null;
    var n = raw.split(/[ ,]+/).map(Number);
    return {x: n[0], y: n[1]};
  }
  /* Nearest centroid within sixty degrees of the direction asked for. The cone
     is what stops "up" from Ghana landing on Chad because Chad happens to be
     the closest thing that is even slightly north. */
  function neighbour(from, dx, dy) {
    var a = centre(from);
    if (!a) return null;
    var best = null, bestD = 1e9;
    mapC.forEach(function (el) {
      if (el === from) return;
      var b = centre(el);
      if (!b) return;
      var vx = b.x - a.x, vy = b.y - a.y;
      var d = Math.sqrt(vx * vx + vy * vy);
      if (!d) return;
      var cos = (vx * dx + vy * dy) / d;
      if (cos < 0.5) return;                  /* outside the sixty-degree cone */
      var cost = d / cos;                     /* straight ahead beats sideways */
      if (cost < bestD) { bestD = cost; best = el; }
    });
    return best;
  }
  if (mapC.length) {
    focusable(mapC[0]);
    mapEl.addEventListener('keydown', function (e) {
      var here = e.target.closest ? e.target.closest('.jn-map-c') : null;
      if (!here) return;
      var go = null;
      if (e.key === 'ArrowRight') go = neighbour(here, 1, 0);
      else if (e.key === 'ArrowLeft') go = neighbour(here, -1, 0);
      else if (e.key === 'ArrowUp') go = neighbour(here, 0, -1);
      else if (e.key === 'ArrowDown') go = neighbour(here, 0, 1);
      else if (e.key === 'Home') go = mapC[0];
      else if (e.key === 'End') go = mapC[mapC.length - 1];
      else return;
      if (!go) { e.preventDefault(); return; }
      e.preventDefault();
      focusable(go);
      go.focus();
    });
    /* Whatever was last touched keeps the stop, so tabbing away and back
       returns to where the reader was rather than to Algeria. */
    mapEl.addEventListener('focusin', function (e) {
      var here = e.target.closest ? e.target.closest('.jn-map-c') : null;
      if (here && here !== roving) focusable(here);
    });
  }

  /* THE TARGETS ARE SIZED IN PIXELS, AND CAPPED BY THE GEOGRAPHY.
   *
   * The discs are 17 units in a 1000-unit drawing. On the rail that renders at
   * seven pixels across; on a phone, where the map is 300px wide, it is five.
   * A five-pixel target is not a target. The browser suite does not catch this
   * — its tap-target pass skips anything inside an <svg>, which was right when
   * SVG on this site was decoration and is not right now that it carries
   * fifty-four controls.
   *
   * So they are sized against the render: eleven pixels of radius, converted
   * into user units through whatever the viewBox currently is, which means
   * they also grow correctly when the map flies in.
   *
   * And capped by half the distance to the nearest other centroid, because the
   * alternative is worse than a small target: at the size a phone wants, the
   * discs for Togo and Benin would each cover the other and one of the two
   * countries would become unpressable. Geometry gets the final say — no disc
   * may reach its neighbour's centre, and that was measured: zero overlapping
   * pairs at 390, 768 and 1440.
   *
   * WHERE THAT LEAVES THE DENSE PLACES, HONESTLY. Fifty-four centroid discs on
   * a 253px drawing cannot all be finger-sized, and pretending otherwise would
   * mean letting Rwanda's disc cover Burundi. On the unflown continent the
   * tightest targets measure 3px across at 390 and 5px at 1440 — Gambia,
   * Rwanda, Burundi — and for those the country grid below, whose buttons are
   * the full width of the column, is the real control. The map is the coarse
   * one.
   *
   * Flying in is what fixes it, and it fixes it by itself. Zoom changes
   * units-per-pixel, so the same rule hands out bigger discs: after a fly to
   * Rwanda those same three go from 3px to 10-11px at 390, and from 5px to
   * 17px at 1440. Measured, both states.
   */
  var hits = mapEl
    ? [].slice.call(mapEl.querySelectorAll('.jn-map-hit')) : [];
  var nearest = hits.map(function (a, i) {
    var ax = +a.getAttribute('cx'), ay = +a.getAttribute('cy'), best = 1e9;
    hits.forEach(function (b, j) {
      if (i === j) return;
      var dx = ax - (+b.getAttribute('cx')), dy = ay - (+b.getAttribute('cy'));
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < best) best = d;
    });
    return best;
  });

  function sizeHits() {
    if (!hits.length || !mapEl) return;
    var box = mapEl.getBoundingClientRect();
    if (!box.width) return;
    var units = (mapEl.getAttribute('viewBox') || HOME).split(/[ ,]+/).map(Number);
    var perPx = units[2] / box.width;
    var want = 11 * perPx;
    hits.forEach(function (el, i) {
      var cap = nearest[i] * 0.48;
      el.setAttribute('r', Math.max(6, Math.min(want, cap)).toFixed(1));
    });
    /* The stops are drawn in pixels for the same reason the targets are. At
       3.3x — which is what choosing Rwanda gives you — a nine-unit stop is
       thirty pixels across and covers the country it is marking. */
    if (mapEl) {
      [].forEach.call(mapEl.querySelectorAll('.jn-map-stop'), function (el) {
        el.setAttribute('r',
          ((el.classList.contains('is-end') ? 6 : 4.5) * perPx).toFixed(1));
      });
    }
  }
  sizeHits();
  addEventListener('resize', sizeHits);

  /* ---- THE JOURNEY, DRAWN ------------------------------------------------
   * The specification's last line, and the one with an honest limit on it.
   *
   * A place on this site carries a group, a lens set and a write-up. It does
   * not carry a position — data/atlas/*.json has no coordinates in it — so
   * there is no way to put a pin on the Mara that is not invented. Thirteen
   * places do have a real position, in tourism/atlas-detail.json, and the
   * countries have centroids. That is what can be drawn, so that is what is
   * drawn, and the caption says which of the two it is doing rather than
   * letting a reader assume every node was surveyed.
   *
   * Country centroids for the shape of the journey, city nodes where a stage
   * names one of the thirteen, and a line through them in the order they are
   * visited. One point is not a route and is drawn as one node; no points is
   * drawn as nothing at all rather than as a line between guesses.
   */
  var routeEl = document.getElementById('jn-map-route');
  var CITY = {};
  (D.cities || []).forEach(function (c) { CITY[c.name.toLowerCase()] = c; });

  function atOf(slug) {
    var el = mapBy[slug];
    var raw = el && el.getAttribute('data-at');
    if (!raw) return null;
    var n = raw.split(/[ ,]+/).map(Number);
    return (n.length === 2 && !isNaN(n[0])) ? {x: n[0], y: n[1]} : null;
  }

  /* A stage's own position, if one exists. Matched on the city's name
     appearing in the stage's title — "Nairobi, Green City in the Sun" is
     Nairobi — and on nothing looser than that, because a fuzzy match here puts
     a node on the wrong continent and calls it data. */
  function cityFor(st) {
    var title = String(st.title || '').toLowerCase();
    for (var k in CITY) {
      if (title.indexOf(k) >= 0) return CITY[k];
    }
    return null;
  }

  /* Catmull-Rom through the points, as one cubic. The same curve the crossing
     maps use, at the same tension, so a route on this page and a route on
     /trans-afrique are the same object drawn by the same rule. */
  function through(pts) {
    if (pts.length < 2) return '';
    var d = 'M' + pts[0].x.toFixed(1) + ' ' + pts[0].y.toFixed(1);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i],
          p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      var t = 0.62 / 3;
      d += ' C' + (p1.x + (p2.x - p0.x) * t).toFixed(1) + ' '
         + (p1.y + (p2.y - p0.y) * t).toFixed(1) + ', '
         + (p2.x - (p3.x - p1.x) * t).toFixed(1) + ' '
         + (p2.y - (p3.y - p1.y) * t).toFixed(1) + ', '
         + p2.x.toFixed(1) + ' ' + p2.y.toFixed(1);
    }
    return d;
  }

  function drawRoute() {
    if (!routeEl) return;
    var st = (typeof stageObjects === 'function') ? stageObjects() : [];
    var pts = [], seen = {}, named = 0;
    st.forEach(function (stage) {
      var city = cityFor(stage);
      if (city) {
        pts.push({x: city.x, y: city.y, label: city.name});
        named++;
        seen[stage.country] = true;
        return;
      }
      if (seen[stage.country]) return;
      var a = atOf(stage.country);
      if (!a) return;
      seen[stage.country] = true;
      pts.push({x: a.x, y: a.y, label: stage.countryName});
    });
    if (!pts.length && chosen) {
      var a0 = atOf(chosen.slug);
      if (a0) pts.push({x: a0.x, y: a0.y,
        label: (D.countries[chosen.slug] || {}).name || chosen.slug});
    }

    var bits = [];
    if (pts.length > 1) {
      bits.push('<path class="jn-map-road" d="' + through(pts) + '"/>');
    }
    pts.forEach(function (p, i) {
      bits.push('<circle class="jn-map-stop'
        + (i === pts.length - 1 ? ' is-end' : '') + '" cx="' + p.x.toFixed(1)
        + '" cy="' + p.y.toFixed(1) + '" r="6"/>');
    });
    routeEl.innerHTML = bits.join('');
    sizeHits();

    /* The caption says which kind of node the reader is looking at, because a
       node drawn at a country's centre and a node on a surveyed city look
       identical and mean different things. A map that does not say which is a
       map that is quietly claiming the second. */
    if (mapSay) {
      var says;
      if (!pts.length) {
        says = 'Nothing in this journey has a published position yet.';
      } else if (pts.length === 1) {
        says = named
          ? 'One stop on the map: ' + pts[0].label + ', the only place in this '
            + 'journey with a surveyed position.'
          : 'Drawn at the centre of ' + pts[0].label + '. The places in this '
            + 'journey do not carry coordinates.';
      } else {
        says = pts.length + ' stops, in the order you would take them.'
          + (named
              ? ' ' + named + ' of them ' + (named === 1 ? 'is a city' : 'are cities')
                + ' with a surveyed position; the rest sit at their '
                + 'country\u2019s centre.'
              : ' Each at its country\u2019s centre \u2014 the places on this '
                + 'site do not carry coordinates.');
      }
      mapSay.textContent = says;
    }

    /* A journey that crosses a border needs a frame that holds both sides of
       it. Flying to the chosen country and leaving the second stop off the
       edge is worse than not flying at all: the reader is looking at a route
       with one end outside the picture and no way to know it. */
    if (pts.length > 1) flyTo(frameAround(pts));
  }

  /* The smallest frame at the home proportion that holds every point, with
     room round it, clamped to the continent. */
  function frameAround(pts) {
    var home = HOME.split(/[ ,]+/).map(Number);
    var xs = pts.map(function (p) { return p.x; });
    var ys = pts.map(function (p) { return p.y; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var pad = Math.max(x1 - x0, y1 - y0) * 0.35 + 70;
    var w = Math.max((x1 - x0) + pad * 2, 300);
    var h = w / ASPECT;
    if (h < (y1 - y0) + pad * 2) { h = (y1 - y0) + pad * 2; w = h * ASPECT; }
    if (w > home[2]) { w = home[2]; h = home[3]; }
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    var x = Math.min(Math.max(cx - w / 2, home[0]), home[0] + home[2] - w);
    var y = Math.min(Math.max(cy - h / 2, home[1]), home[1] + home[3] - h);
    return [x, y, w, h].map(function (n) { return Math.round(n * 10) / 10; })
      .join(' ');
  }

  /* ---- FLYING TO THE COUNTRY -------------------------------------------
   * The specification's second verb. Choosing a country should not merely
   * ring it on a continent-sized drawing where Rwanda is four pixels across;
   * the map should go there.
   *
   * It is the viewBox that moves, not a transform. A transform scales the
   * strokes with it — a 1px border becomes a 6px border at 6x — and it scales
   * the transparent hit discs too, so the targets would drift away from the
   * countries under them. Moving the viewBox moves the camera: the strokes
   * are non-scaling, the discs stay on their centroids, and the drawing is
   * resolution-independent all the way in.
   *
   * THE ASPECT RATIO IS HELD. The element has no height of its own — it takes
   * it from the viewBox — so a target box of a different shape resizes the
   * element and shifts the page under the reader. This page is measured for
   * layout shift; a fly-to that scores 0.4 CLS is a fly-to that has to be
   * reverted. Every target is built at the home box's own proportion.
   */
  var HOME = mapEl ? (mapEl.getAttribute('viewBox') || '0 0 1000 1060') : null;
  var ASPECT = HOME ? (function (v) {
    var n = v.split(/[ ,]+/).map(Number); return n[2] / n[3]; }(HOME)) : 1;
  var flying = null;

  function boxOf(slug) {
    var el = mapBy[slug];
    if (!el || !el.getBBox) return null;
    try { return el.getBBox(); } catch (e) { return null; }
  }

  /* A box around the country, at the home proportion, never smaller than a
     minimum and never larger than the continent. The minimum is what stops
     Comoros filling the frame with three dots and no coastline to say where
     they are: a country is only legible with some of its neighbours in shot. */
  function frameFor(slug) {
    var b = boxOf(slug);
    if (!b) return HOME;
    var home = HOME.split(/[ ,]+/).map(Number);
    var pad = Math.max(b.width, b.height) * 0.55 + 40;
    var w = Math.max(b.width + pad * 2, 300);
    var h = w / ASPECT;
    if (h < b.height + pad * 2) { h = b.height + pad * 2; w = h * ASPECT; }
    if (w > home[2]) { w = home[2]; h = home[3]; }
    var cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    var x = Math.min(Math.max(cx - w / 2, home[0]), home[0] + home[2] - w);
    var y = Math.min(Math.max(cy - h / 2, home[1]), home[1] + home[3] - h);
    return [x, y, w, h].map(function (n) { return Math.round(n * 10) / 10; })
      .join(' ');
  }

  var wideEl = document.getElementById('jn-map-wide');
  function setBox(v) {
    if (!mapEl) return;
    mapEl.setAttribute('viewBox', v);
    /* The control exists only while there is something off the edge. */
    if (wideEl) wideEl.hidden = (v === HOME);
  }
  if (wideEl) {
    wideEl.addEventListener('click', function () {
      flyTo(HOME);
      track('map_widened', {country: chosen ? chosen.slug : null});
    });
  }

  function flyTo(target) {
    if (!mapEl) return;
    var from = (mapEl.getAttribute('viewBox') || HOME).split(/[ ,]+/).map(Number);
    var to = String(target).split(/[ ,]+/).map(Number);
    if (flying) { cancelAnimationFrame(flying); flying = null; }
    /* Reduced motion gets the destination, not a slower journey to it. */
    if (reduced.matches) { setBox(to.join(' ')); sizeHits(); return; }
    var t0 = performance.now(), ms = 620;
    var tick = function (now) {
      var k = Math.min(1, (now - t0) / ms);
      var e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      setBox(from.map(function (v, i) {
        return Math.round((v + (to[i] - v) * e) * 10) / 10; }).join(' '));
      if (k < 1) flying = requestAnimationFrame(tick);
      else { flying = null; sizeHits(); }
    };
    flying = requestAnimationFrame(tick);
  }

  /* Live, not on submit. The controls are radios and checkboxes, so `change`
     fires on the press that matters and on nothing else; `input` would fire
     for the sentence box too, and the sentence has its own button. */
  form.addEventListener('change', function () { readForm(); paintMap(); });
  paintMap();

  /* Who lives there, before why we chose it. A country that arrives as an
     outline, a season and a reason is a destination; a country that arrives
     with the people who live in it named is a place. Both lines are write-ups
     that already exist in that country's own file. */
  function meetsBlock(c) {
    if (!c.meets || !c.meets.length) return '';
    return '<p class="jn-meets"><span>Who lives here</span>'
      + c.meets.map(function (m) { return esc(m.title); }).join(' \u00b7 ')
      + ' <a href="/meet#/' + esc(chosen.slug) + '">Meet ' + esc(c.name)
      + ' &rarr;</a> <a href="/portrait/' + esc(chosen.slug) + '">Read the '
      + 'portrait &rarr;</a></p>';
  }

  /* Why this one, in the words of the thing that was actually matched. No
     percentage: a number implies a precision the dataset does not have, and a
     reason a traveller can check is worth more than one they cannot. */
  function whyBlock(p) {
    var b = E.band(D, brief, p);
    var rows = p.reasons.map(function (r) {
      return '<li data-key="' + esc(r.key) + '">' + esc(r.say) + '</li>';
    });
    if (p.outOfSeason && brief.month) {
      rows.push('<li data-key="warn">' + esc(D.months[brief.month - 1])
        + ' is not one of the months it names as its best &mdash; worth asking about</li>');
    }
    if (!rows.length) {
      rows.push('<li data-key="open">You told us nothing to narrow by, so this is '
        + 'simply where we would start</li>');
    }
    var carried = [];
    if (brief.party) {
      carried.push(D.party.filter(function (x) { return x.key === brief.party; })
        .map(function (x) { return x.label.toLowerCase(); })[0]);
    }
    brief.style.forEach(function (k) {
      var s = D.style.filter(function (x) { return x.key === k; })[0];
      if (s && s.key !== 'unsure') carried.push(s.label.toLowerCase());
    });
    return (b ? '<p class="jn-band" data-kind="' + esc(b.label.split(' ')[0].toLowerCase())
                + '"><b>' + esc(b.label) + '</b><span>' + esc(b.why) + '</span></p>' : '')
      + '<p class="jn-why-head">Why this one</p><ul class="jn-why-list">'
      + rows.join('') + '</ul>'
      + (carried.length
         ? '<p class="jn-why-carried">Carried to the operator, not scored: '
           + esc(carried.join(', ')) + '.</p>'
         : '');
  }

  /* The alternatives get the short form of every reason rather than the first
     one, because the first one is usually the thing all three have in common
     and a list where every row says the same sentence is a list of one. */
  function oneLine(p) {
    var bits = p.reasons.map(function (r) { return r.text; }).filter(Boolean);
    return bits.length ? bits.join(' \u00b7 ') : 'Where we would start';
  }

  /* The field is its own section now, so the delegated handler has to be bound
     to both. Bound only to .jn-reveal, every country in the grid was inert. */
  /* They picked one themselves. That is the whole point of showing all
     fifty-four, so nothing here second-guesses it: the country they chose
     becomes the journey, whatever the ranking thought.

     One function for two doors. The grid and the map are the same choice made
     two ways, and the moment they were two code paths one of them would start
     forgetting something the other does — which is how a map ends up not
     recording that a country was chosen from it. `how` is the only thing that
     differs, and it is a label on the count, not a branch. */
  function chooseCountry(want, how) {
    if (!want || !D.countries[want]) return false;
    var found = E.rank(D, {wants: brief.wants, month: brief.month, seed: brief.seed})
      .filter(function (p) { return p.slug === want; })[0];
    chosen = found || {slug: want, reasons: [], outOfSeason: false};
    picks = [chosen].concat(picks.filter(function (p) { return p.slug !== want; }));
    track('country_chosen', {country: want, from: how || 'grid'});
    var fs = document.getElementById('jn-field');
    if (fs) fs.hidden = true;
    paintMap();
    openComposer(want);
    return true;
  }

  function onPick(e) {
    var t = e.target.closest ? e.target.closest('[data-alt],[data-compose],[data-others],[data-restart],[data-country]') : null;
    if (!t) return;
    if (t.hasAttribute('data-alt')) {
      var found = picks.filter(function (p) { return p.slug === t.dataset.alt; })[0];
      chosen = found || E.rank(D, {wants: [], month: brief.month}).filter(function (p) {
        return p.slug === t.dataset.alt; })[0];
      if (!chosen) return;
      picks = [chosen].concat(picks.filter(function (p) { return p.slug !== chosen.slug; }));
      track('alternative_opened', {country: chosen.slug});
      paintReveal();
      window.scrollTo({top: 0, behavior: reduced.matches ? 'auto' : 'smooth'});
    } else if (t.hasAttribute('data-compose')) {
      openComposer(chosen.slug);
    } else if (t.hasAttribute('data-others')) {
      var alts = document.getElementById('jn-alts');
      alts.toggleAttribute('data-open');
      if (alts.hasAttribute('data-open')) {
        alts.scrollIntoView({behavior: reduced.matches ? 'auto' : 'smooth', block: 'start'});
      }
    } else if (t.hasAttribute('data-country')) {
      chooseCountry(t.dataset.country, 'grid');
    } else if (t.hasAttribute('data-restart')) {
      /* Re-rolling changes the tie-break, not the rules: two countries that
         scored the same get to take turns. It travels in the link, so a
         shared journey is still the same journey. */
      brief.seed = (brief.seed + 1) % 7;
      /* Back to the whole continent: the questions are about all of it again. */
      chosen = null;
      paintMap();
      if (routeEl) routeEl.innerHTML = '';
      flyTo(HOME);
      reveal.hidden = true;
      form.hidden = false;
      var fieldSec = document.getElementById('jn-field');
      if (fieldSec) fieldSec.hidden = true;
      show(1);
    }
  }
  /* THE MAP IS A DOOR, AND IT IS A LINK FIRST.
     Every country is an <a> to its own page, so with the script off — or
     before it loads, or if it throws — pressing Ghana goes to Ghana, which is
     a reasonable thing for pressing Ghana to do. With the script running the
     press is intercepted and the country becomes the journey instead.

     Two targets resolve to one slug: the outline, which is what a pointer
     lands on for a country the size of Algeria, and the transparent disc at
     the centroid, which is the only way to press The Gambia. A country this
     site has not written up is not intercepted at all — the link goes where
     the link says. */
  if (mapEl) {
    mapEl.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target : null;
      if (!t) return;
      var hit = t.closest('.jn-map-hit');
      var link = t.closest('.jn-map-c');
      var slug = hit ? hit.getAttribute('data-slug')
        : (link ? link.getAttribute('data-slug') : null);
      if (!slug) return;
      if (chooseCountry(slug, 'map')) e.preventDefault();
    });
    /* Pointing at the disc lights the country under it, because the disc is
       invisible and the country is what the reader thinks they are pointing
       at. Without this, hovering The Gambia lights nothing. */
    mapEl.addEventListener('mouseover', function (e) {
      var hit = e.target.closest ? e.target.closest('.jn-map-hit') : null;
      if (!hit) return;
      var el = mapBy[hit.getAttribute('data-slug')];
      if (el) el.setAttribute('data-hot', 'true');
    });
    mapEl.addEventListener('mouseout', function (e) {
      var hit = e.target.closest ? e.target.closest('.jn-map-hit') : null;
      if (!hit) return;
      var el = mapBy[hit.getAttribute('data-slug')];
      if (el) el.removeAttribute('data-hot');
    });
  }

  reveal.addEventListener('click', onPick);
  var fieldEl = document.getElementById('jn-field');
  if (fieldEl) fieldEl.addEventListener('click', onPick);

  /* ---- the composer ------------------------------------------------------ */

  function fetchPlaces(slug) {
    if (places[slug]) return Promise.resolve(places[slug]);
    return fetch('/data/atlas/' + encodeURIComponent(slug) + '.json')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { places[slug] = p; return p; })
      .catch(function () { places[slug] = {slug: slug, places: []}; return places[slug]; });
  }

  function needLinks() {
    if (LINKS) return Promise.resolve(LINKS);
    return fetch('/data/links.json').then(function (r) { return r.json(); })
      .then(function (j) { LINKS = j; return j; })
      .catch(function () { LINKS = {links: {}, nodes: {}}; return LINKS; });
  }

  function openComposer(slug, keep) {
    needLinks().then(function () {
      if (!compose.hidden && chosen && chosen.slug === slug) paintComposer();
    });
    /* Anything already in the journey from another country needs its places too,
       or a shared link would open a journey with holes in it. */
    var others = stages.map(function (raw) { return E.stageOf(raw, slug).country; })
      .filter(function (c, i, a) { return c !== slug && a.indexOf(c) === i; });
    others.forEach(function (c) {
      fetchPlaces(c).then(function () {
        if (!compose.hidden && chosen && chosen.slug === slug) paintComposer();
      });
    });
    fetchPlaces(slug).then(function (pack) {
      chosen = chosen && chosen.slug === slug ? chosen
        : (E.rank(D, brief).filter(function (p) { return p.slug === slug; })[0]
           || {slug: slug, reasons: [], outOfSeason: false});
      if (!keep || !stages.length) {
        stages = E.suggestStages(pack.places, brief, E.pacingFor(D, brief.pacing));
      }
      form.hidden = true;
      reveal.hidden = true;
      compose.hidden = false;
      paintComposer();
      /* One place the map is told a journey has opened, because there are four
         ways in — the grid, the map, the "somewhere else" select, and a shared
         link restoring from the hash — and a restored journey that arrives on
         an unflown continent is the one nobody would have tested. */
      paintMap();
      flyTo(frameFor(slug));
      track('journey_composed', {country: slug, stages: stages.length,
                                 pacing: brief.pacing, month: brief.month});
      writeHash();
      window.scrollTo({top: 0, behavior: 'auto'});
    });
  }

  /* A stage knows which country it is in, because a journey can cross a border.
     Anything from a country whose places have not arrived yet is simply not
     drawn until they have — a half-loaded journey is a shorter journey, not a
     broken one. */
  function stageObjects() {
    return stages.map(function (raw) {
      var st = E.stageOf(raw, chosen.slug);
      var pack = places[st.country];
      if (!pack) return null;
      var found = pack.places.filter(function (p) { return p.id === st.id; })[0];
      return found ? Object.assign({}, found, {country: st.country,
        countryName: (D.countries[st.country] || {}).name || st.country}) : null;
    }).filter(Boolean);
  }

  /* Every country a stage belongs to, in the order they are first visited. */
  function countriesInPlay() {
    var out = [];
    stages.forEach(function (raw) {
      var c = E.stageOf(raw, chosen.slug).country;
      if (out.indexOf(c) < 0) out.push(c);
    });
    if (!out.length) out.push(chosen.slug);
    return out;
  }

  function paintComposer() {
    var c = D.countries[chosen.slug];
    var pace = E.pacingFor(D, brief.pacing);
    var st = stageObjects();
    var title = E.name(c, st);

    document.getElementById('jn-c-stamp').textContent =
      c.name + ' · ' + pace.short + (brief.month ? ' · ' + D.months[brief.month - 1] : '');
    document.getElementById('jn-c-name').textContent = title;
    document.getElementById('jn-c-line').textContent = c.summary;
    var carry = (chosen.reasons || []).map(function (r) {
      return '<span data-key="' + esc(r.key) + '">' + esc(r.text || r.say) + '</span>';
    });
    if (chosen.outOfSeason && brief.month) {
      carry.push('<span data-key="warn">Not ' + esc(D.months[brief.month - 1])
        + '&rsquo;s best month</span>');
    }
    document.getElementById('jn-c-why').innerHTML = carry.join('');
    paintTweaks();

    /* The timeline. Stage names and country facts are the dataset's; the day
       numbers are arithmetic on the length the traveller chose, and the line
       under the timeline says exactly that rather than implying a schedule. */
    var arrival = c.operator && c.operator.base ? c.operator.base : null;
    var rows = E.timeline(st, pace.days, arrival);
    var last = null;
    document.getElementById('jn-line').innerHTML = rows.map(function (r) {
      var span = r.from === r.to ? 'Day ' + pad(r.from)
        : 'Days ' + pad(r.from) + '–' + pad(r.to);
      if (r.kind !== 'stage') {
        return '<li class="jn-leg jn-leg--edge"><span class="jn-leg-day">' + span + '</span>'
          + '<span class="jn-leg-body"><b>' + esc(r.label) + '</b></span></li>';
      }
      /* A border is the one thing in a timeline worth interrupting it for. */
      var crossed = last && last !== r.stage.country;
      last = r.stage.country;
      return (crossed
        ? '<li class="jn-cross"><span>' + esc(D.countries[r.stage.country].name)
          + '</span></li>' : '')
        + '<li class="jn-leg"><span class="jn-leg-day">' + span + '</span>'
        + '<span class="jn-leg-body"><b>' + esc(r.stage.title) + '</b>'
        + '<span class="jn-leg-line">' + esc(r.stage.text) + '</span>'
        + '<span class="jn-leg-meta">' + esc(r.stage.group)
        + (r.stage.country !== chosen.slug
           ? ' &middot; ' + esc(r.stage.countryName) : '') + '</span></span>'
        + '<button class="jn-leg-x" type="button" data-drop="' + esc(r.stage.id)
        + '" aria-label="Remove ' + esc(r.stage.title) + ' from the journey">&times;</button>'
        + '</li>';
    }).join('') || '<li class="jn-leg jn-leg--edge"><span class="jn-leg-body">'
      + '<b>Nothing chosen yet</b></span></li>';

    document.getElementById('jn-caveat').textContent =
      'Day numbers are a shape to argue with, not a schedule. How far apart these '
      + 'places actually are, and how long each is worth, is what the operator '
      + 'settles once they know when you are coming.';

    /* What it is made of: a tally of the stages actually chosen, by the same
       six lenses the questions used. No estimate, no invented weighting. */
    var mix = E.composition(D, st);
    document.getElementById('jn-dna').innerHTML = mix.length
      ? mix.map(function (m) {
          return '<div class="jn-bar"><span class="jn-bar-k">' + esc(m.label) + '</span>'
            + '<span class="jn-bar-t"><i style="width:' + Math.round(m.share * 100)
            + '%"></i></span>'
            + '<span class="jn-bar-n">' + Math.round(m.share * 100) + '%</span></div>';
        }).join('')
      : '<p class="jn-note">Add a stage and this fills in.</p>';

    document.getElementById('jn-who').innerHTML = onwardBlock() + whoBlock(c);

    var pick = document.getElementById('jn-picks');
    var pack = places[chosen.slug] || {places: []};
    var wants = brief.wants;
    document.getElementById('jn-pick-note').textContent =
      pack.places.length
        ? 'Everything written up in ' + c.name + ', the way ' + c.name
          + ' tells it. ' + stages.length + ' of ' + pack.places.length + ' in the journey.'
        : 'Nothing is written up for ' + c.name + ' yet. Talk to the operator and '
          + 'they will build it with you.';
    pick.innerHTML = pack.places.map(function (p) {
      var on = stages.indexOf(p.id) >= 0;
      var lead = (p.lenses || []).some(function (k) { return wants.indexOf(k) >= 0; });
      return '<li><button class="jn-pick" type="button" data-toggle="' + esc(p.id) + '"'
        + (on ? ' aria-pressed="true"' : ' aria-pressed="false"')
        + (lead ? ' data-lead' : '') + '>'
        + '<span class="jn-pick-mark" aria-hidden="true">' + (on ? '&minus;' : '+') + '</span>'
        + '<span class="jn-pick-body"><b>' + esc(p.title) + '</b>'
        + '<span class="jn-pick-line">' + esc(p.text) + '</span>'
        + '<span class="jn-pick-meta">' + esc(p.group) + '</span></span></button></li>';
    }).join('');

    var meet = document.getElementById('jn-meet');
    if (meet) {
      meet.href = '/meet#/' + encodeURIComponent(chosen.slug);
      meet.textContent = 'Meet ' + c.name;
    }
    /* The ground stage sends this same brief with the figure appended, so it is
       built once here and read there rather than assembled twice from the same
       inputs — which is how the two of them would drift apart. */
    lastBrief = enquiry(title, c, rows, pace);
    var begin = document.getElementById('jn-begin');
    begin.onclick = function () {
      track('enquiry_started', {country: chosen.slug, stages: stages.length,
                                month: brief.month, pacing: brief.pacing});
    };
    drawRoute();
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /* Change one thing. Starting the four questions again to see the same country
     in a different month is the sort of thing that makes people leave, so the
     three answers that reshape a journey are editable where the journey is. */
  function paintTweaks() {
    var box = document.getElementById('jn-tweak');
    if (!box) return;
    var pace = E.pacingFor(D, brief.pacing);
    box.innerHTML =
      '<span class="jn-tweak-say">Change one thing</span>'
      + '<label class="jn-tweak-f"><span>How long</span><select data-tweak="pacing">'
      + D.pacing.map(function (p) {
          return '<option value="' + esc(p.key) + '"'
            + (p.key === pace.key ? ' selected' : '') + '>' + esc(p.label) + '</option>';
        }).join('') + '</select></label>'
      + '<label class="jn-tweak-f"><span>When</span><select data-tweak="month">'
      + '<option value="">Flexible</option>'
      + D.months.map(function (m, i) {
          return '<option value="' + (i + 1) + '"'
            + (brief.month === i + 1 ? ' selected' : '') + '>' + esc(m) + '</option>';
        }).join('') + '</select></label>'
      + '<label class="jn-tweak-f"><span>Somewhere else</span><select data-tweak="country">'
      + Object.keys(D.countries).sort(function (a, b) {
          return D.countries[a].name < D.countries[b].name ? -1 : 1; })
        .map(function (s) {
          return '<option value="' + esc(s) + '"'
            + (s === chosen.slug ? ' selected' : '') + '>' + esc(D.countries[s].name)
            + '</option>';
        }).join('') + '</select></label>';
  }

  /* Where this journey could carry on to. Only across a real land border, and
     only into a country that answers the same brief — the two conditions that
     make a second country a continuation rather than a second holiday. */
  function onwardBlock() {
    var here = countriesInPlay();
    var rows = [];
    here.forEach(function (from) {
      E.onward(D, LINKS, from, brief).forEach(function (r) {
        if (here.indexOf(r.to) >= 0) return;
        if (rows.some(function (x) { return x.to === r.to; })) return;
        rows.push(Object.assign({}, r, {from: from}));
      });
    });
    if (!rows.length) return '';
    return '<div class="jn-onward"><span class="af-stamp">Carry on over the border</span>'
      + '<ul>' + rows.slice(0, 3).map(function (r) {
          var c = D.countries[r.to];
          return '<li><button type="button" data-cross="' + esc(r.to) + '">'
            + '<b>' + esc(c.name) + '</b>'
            + '<span class="jn-onward-km">' + (r.km != null ? r.km + ' km' : '') + '</span>'
            + '<span class="jn-onward-why">' + esc(c.tagline) + ' &mdash; '
            + esc(r.why.filter(function (w) { return w.kind !== 'season'; })
                   .map(function (w) { return w.say; }).join(', ')) + '</span>'
            + '</button></li>';
        }).join('') + '</ul>'
      + '<p class="jn-onward-note">Straight-line distances between country centres. '
      + 'Your coordinator plans the road and the border post around your '
      + 'dates.</p></div>';
  }

  /* Local means a company with an address, a year and a sentence about what it
     actually runs. Where we have that, name it — it is evidence and it is a
     strength. Where we do not, the answer is not "nobody of ours": the ground
     journey is Afrinkong's own everywhere, which is the thing the traveller is
     actually asking about at the end of composing one. */
  function whoBlock(c) {
    if (!c.operator) {
      return '<div class="jn-who-in" data-house><span class="af-stamp">Who would run it</span>'
        + '<b>Afrinkong</b>'
        + '<p>Your vehicle, your driver for the whole journey, and a coordinator '
        + 'holding the days together — ours, wherever this goes.</p></div>';
    }
    var o = c.operator;
    return '<div class="jn-who-in" data-ours><span class="af-stamp">Operated locally by</span>'
      + '<b>' + esc(o.name) + '</b>'
      + '<span class="jn-who-base">' + esc(o.base)
      + (o.since ? ' · operating since ' + esc(o.since) : '') + '</span>'
      + '<p>' + esc(o.line) + '</p>'
      + (o.url ? '<a class="af-go" href="' + esc(o.url) + '">Open ' + esc(o.name)
                 + ' &rarr;</a>' : '')
      + '</div>';
  }

  /* What gets carried into the enquiry. Everything the traveller said, in
     plain sentences, including the two things the engine deliberately did not
     score — those are the parts a person is better at than a weighting. */
  function enquiry(title, c, rows, pace) {
    var lines = [title, '', c.name + ' · ' + pace.label
      + (brief.month ? ' · ' + D.months[brief.month - 1] : '')];
    rows.forEach(function (r) {
      var span = r.from === r.to ? 'Day ' + r.from : 'Days ' + r.from + '-' + r.to;
      lines.push(span + ': ' + (r.kind === 'stage' ? r.stage.title : r.label));
    });
    if (brief.wants.length) {
      lines.push('', 'Looking for: ' + brief.wants.map(function (k) {
        return D.lenses[k].title.toLowerCase(); }).join(', '));
    }
    if (brief.party) {
      lines.push('Travelling: ' + D.party.filter(function (x) {
        return x.key === brief.party; }).map(function (x) { return x.label; })[0]);
    }
    if (brief.style.length) {
      lines.push('Preferences: ' + brief.style.map(function (k) {
        return (D.style.filter(function (x) { return x.key === k; })[0] || {}).label;
      }).filter(Boolean).join(', '));
    }
    lines.push('', 'Built at ' + location.origin + location.pathname + E.encode(stateNow()));
    return lines.join('\n');
  }

  compose.addEventListener('change', function (e) {
    var t = e.target.closest ? e.target.closest('[data-tweak]') : null;
    if (!t) return;
    var what = t.dataset.tweak;
    if (what === 'pacing') {
      brief.pacing = t.value;
      /* A longer trip earns more stages; a shorter one loses the last ones
         rather than being re-picked, so nothing the visitor chose disappears
         without them seeing it go. */
      var want = E.pacingFor(D, brief.pacing).stages;
      var pack = places[chosen.slug] || {places: []};
      if (stages.length > want) stages = stages.slice(0, want);
      else if (stages.length < want) {
        E.suggestStages(pack.places, brief, {stages: want}).forEach(function (id) {
          if (stages.length < want && stages.indexOf(id) < 0) stages.push(id);
        });
      }
      track('journey_tweaked', {country: chosen.slug, pacing: brief.pacing,
                                month: brief.month});
      paintComposer(); writeHash();
    } else if (what === 'month') {
      brief.month = t.value ? Number(t.value) : null;
      chosen = E.rank(D, brief).filter(function (p) { return p.slug === chosen.slug; })[0]
        || chosen;
      track('journey_tweaked', {country: chosen.slug, pacing: brief.pacing,
                                month: brief.month});
      paintComposer(); writeHash();
    } else if (what === 'country' && t.value !== chosen.slug) {
      /* `chosen` is deliberately left standing: openComposer replaces it, and
         everything that repaints in between reads it. Nulling it here left a
         window in which the composer was drawing a journey with no country. */
      stages = [];
      openComposer(t.value, false);
    }
  });

  compose.addEventListener('click', function (e) {
    var t = e.target.closest
      ? e.target.closest('[data-toggle],[data-drop],[data-save],[data-share],[data-cross],[data-ground]')
      : null;
    if (!t) return;
    if (t.hasAttribute('data-cross')) {
      var to = t.dataset.cross;
      fetchPlaces(to).then(function (pack) {
        var add = E.suggestStages(pack.places, brief, {stages: 2});
        add.forEach(function (id) { stages.push(E.stageId(to, id, chosen.slug)); });
        track('border_crossed', {country: chosen.slug, to: to});
        paintComposer(); writeHash();
      });
      return;
    }
    if (t.hasAttribute('data-toggle')) {
      var id = t.dataset.toggle;
      var at = stages.indexOf(id);
      if (at >= 0) stages.splice(at, 1); else stages.push(id);
      track('stage_changed', {country: chosen.slug, stages: stages.length});
      paintComposer(); writeHash();
    } else if (t.hasAttribute('data-drop')) {
      stages = stages.filter(function (x) { return x !== t.dataset.drop; });
      paintComposer(); writeHash();
    } else if (t.hasAttribute('data-save')) {
      save();
    } else if (t.hasAttribute('data-share')) {
      share();
    } else if (t.hasAttribute('data-ground')) {
      openGround();
    }
  });


  /* ---- the ground --------------------------------------------------------- */

  /* The tunnel used to stop at the composer: a journey with a shape, a name and
     no figure, handed to /contact for somebody to price by hand. This is the
     fifth question. It carries the days already answered rather than asking a
     second time, and it totals from data-rate attributes rather than by reading
     the dollars back out of the labels — a label that says "Included" instead
     of "$0" is exactly how a group silently stops being counted. */

  var lastBrief = '';
  var ground = document.getElementById('ground');
  var gform = document.getElementById('jn-g');

  function money(n) { return '$' + Math.round(n).toLocaleString('en-US'); }

  /* How many days the traveller is actually being quoted for. The chips offer
     the common lengths; anything else goes in "Other", which is also where the
     pacing answer lands when it does not match a chip — 12 days is a real
     answer and rounding it to 10 or 14 to fit the UI would be the interface
     lying about what it was told. */
  function groundDays() {
    var on = gform.querySelector('input[name=days]:checked');
    if (!on) return 0;
    if (on.value !== 'other') return parseInt(on.value, 10) || 0;
    var other = gform.querySelector('input[name=days_other]');
    return Math.max(0, parseInt(other && other.value, 10) || 0);
  }

  function prefillDays(want) {
    var chip = gform.querySelector('input[name=days][value="' + want + '"]');
    if (chip) { chip.checked = true; return; }
    var other = gform.querySelector('input[name=days][value=other]');
    var box = gform.querySelector('input[name=days_other]');
    if (other && box) { other.checked = true; box.value = want; }
  }

  function total() {
    var days = groundDays();
    var perDay = 0, once = parseInt(gform.dataset.arrival, 10) || 0, quote = false;
    var tier = null;
    gform.querySelectorAll('input:checked').forEach(function (i) {
      if (i.name === 'days' || i.type === 'checkbox') return;
      if (i.hasAttribute('data-quote')) quote = true;
      if (i.dataset.rate) perDay += parseInt(i.dataset.rate, 10) || 0;
      if (i.dataset.once) once += parseInt(i.dataset.once, 10) || 0;
      if (i.name === 'tier') tier = i;
    });
    return {days: days, sum: perDay * days + (days ? once : 0), quote: quote,
            tier: tier ? tier.closest('.jn-card').querySelector('b').textContent : ''};
  }

  function paintGround() {
    var t = total();
    var sum = gform.querySelector('[data-total]');
    var basis = gform.querySelector('[data-basis]');
    var note = gform.querySelector('[data-quote]');
    if (sum) sum.textContent = t.days ? money(t.sum) : '—';
    if (basis) {
      basis.textContent = t.days
        ? t.days + ' days \u00b7 ' + t.tier + ' \u00b7 arrival included'
        : 'Tell us how many days';
    }
    if (note) note.hidden = !t.quote;

    /* /enquire, not /contact. The tunnel used to end on Kamerun's page: a
       journey composed for Eritrea arrived under a KAMERUN masthead beside a
       Douala address and a +237 number. */
    var go = document.getElementById('jn-go');
    if (go && chosen) {
      var c = D.countries[chosen.slug];
      var lines = [lastBrief,
                   '', 'THE GROUND',
                   'Journey: ' + t.tier,
                   'Days: ' + (t.days || 'not yet said'),
                   'Afrinkong service: ' + (t.days ? money(t.sum) : 'not yet priced')
                     + ' USD, arrival coordination included'];
      if (t.quote) {
        lines.push('One choice is quoted once the destination is known.');
      }
      lines.push('Destination charges (parks, permits, entrance) are arranged by '
                 + 'Afrinkong and added at cost.');
      go.href = '/enquire?journey=' + encodeURIComponent(lines.join('\n'));
      go.textContent = c.operator ? 'Send this to ' + c.operator.name
                                  : 'Begin this journey';
      go.insertAdjacentHTML('beforeend', '<i>&rarr;</i>');
    }

    /* The second door carries the SHAPE of the journey rather than the
       sentence: the planner needs a country, a tier and a length it can price
       again, not a paragraph to read. Nothing about the traveller travels with
       it — no name, no dates typed into a box, no figure — because the page it
       opens has no account to attach any of that to. */
    var toward = document.getElementById('jn-toward');
    if (toward && chosen) {
      var q = ['place=' + encodeURIComponent(chosen.slug)];
      if (t.tier) q.push('tier=' + encodeURIComponent(t.tier));
      if (t.days) q.push('days=' + encodeURIComponent(t.days));
      toward.href = '/journey-fund?' + q.join('&');
    }
  }

  function openGround() {
    compose.hidden = true;
    ground.hidden = false;
    prefillDays(E.pacingFor(D, brief.pacing).days);
    paintGround();
    track('ground_opened', {country: chosen ? chosen.slug : null,
                            pacing: brief.pacing});
    window.scrollTo({top: 0, behavior: reduced.matches ? 'auto' : 'smooth'});
    var h = ground.querySelector('.jn-h1');
    if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
  }

  if (gform) {
    gform.addEventListener('change', paintGround);
    gform.addEventListener('input', paintGround);
    gform.addEventListener('submit', function (e) { e.preventDefault(); });
  }
  if (ground) {
    ground.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('[data-back-compose]') : null;
      if (!t) return;
      ground.hidden = true;
      compose.hidden = false;
      window.scrollTo({top: 0, behavior: reduced.matches ? 'auto' : 'smooth'});
    });
  }

  /* ---- saving, sharing, restoring ---------------------------------------- */

  function stateNow() {
    return {country: chosen ? chosen.slug : null, stages: stages, month: brief.month,
            pacing: brief.pacing, party: brief.party, wants: brief.wants,
            style: brief.style, seed: brief.seed};
  }

  function writeHash() {
    var h = E.encode(stateNow());
    if (h !== location.hash) history.replaceState(null, '', h);
  }

  function say(text) {
    var el = document.getElementById('jn-said');
    el.textContent = text;
    el.setAttribute('data-on', '');
  }

  /* No accounts, and nothing that pretends to be one. A journey is kept in this
     browser and is addressable by its own link, so the day accounts arrive the
     saved list is a list of links to import rather than a schema to migrate. */
  function save() {
    var c = D.countries[chosen.slug];
    var title = E.name(c, stageObjects());
    var list = read();
    var url = E.encode(stateNow());
    list = list.filter(function (j) { return j.url !== url; });
    list.unshift({url: url, title: title, country: c.name, stages: stages.length});
    try {
      localStorage.setItem(SAVED, JSON.stringify(list.slice(0, 12)));
      track('journey_saved', {country: chosen.slug, stages: stages.length});
      say('Saved in this browser. It is also in the address bar — copy the '
        + 'link and it will open anywhere.');
    } catch (err) {
      say('This browser will not let the page save anything. The link in the '
        + 'address bar is the journey — copy that instead.');
    }
  }

  function read() {
    try { return JSON.parse(localStorage.getItem(SAVED) || '[]'); }
    catch (err) { return []; }
  }

  function share() {
    var url = location.origin + location.pathname + E.encode(stateNow());
    track('journey_shared', {country: chosen.slug, stages: stages.length});
    var done = function () {
      say('Link copied. Anyone who opens it sees this journey, with the stages '
        + 'you chose.');
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done, function () { say(url); });
    } else {
      say(url);
    }
  }

  /* A saved list is only worth showing if there is one. It goes above the first
     question, where somebody coming back will look for it. */
  function paintSaved() {
    var list = read();
    var old = document.getElementById('jn-saved');
    if (old) old.remove();
    if (!list.length) return;
    var box = document.createElement('div');
    box.id = 'jn-saved';
    box.className = 'jn-saved';
    box.innerHTML = '<span class="af-stamp">Where you left off</span><ul>'
      + list.map(function (j) {
        return '<li><a href="' + esc(j.url) + '"><b>' + esc(j.title) + '</b>'
          + '<span>' + esc(j.country) + ' · ' + j.stages
          + (j.stages === 1 ? ' stage' : ' stages') + '</span></a></li>';
      }).join('') + '</ul>';
    steps[0].insertBefore(box, steps[0].firstChild);
  }

  /* Entry points. A link can arrive already carrying an answer — from the
     atlas's month strip, from a lens, from a country page — and the builder
     picks up at the next unanswered question rather than asking again for
     something the visitor has already told the site. */
  function entry() {
    var s = E.decode(location.hash);
    if (s.country && D.countries[s.country]) return false;   /* restore() handles it */
    var got = false;
    (s.wants || []).forEach(function (k) {
      var el = D.lenses[k] && form.querySelector('[name="want"][value="' + k + '"]');
      if (el) { el.checked = true; got = true; }
    });
    var one = function (n, v) {
      var el = v && form.querySelector('[name="' + n + '"][value="' + v + '"]');
      if (el) { el.checked = true; return true; }
      return false;
    };
    if (one('month', s.month)) got = true;
    if (one('pacing', s.pacing)) got = true;
    if (one('party', s.party)) got = true;
    if (!got) return false;
    readForm();
    /* Start on the first thing they have not said. */
    show(brief.wants.length ? (brief.month ? (val('pacing') ? 4 : 3) : 2) : 1);
    return true;
  }

  function restore() {
    var s = E.decode(location.hash);
    if (!s.country || !D.countries[s.country]) return false;
    brief.wants = s.wants.filter(function (k) { return !!D.lenses[k]; });
    brief.month = s.month;
    brief.pacing = s.pacing || 'open';
    brief.party = s.party;
    brief.style = s.style;
    brief.seed = s.seed;
    stages = s.stages;
    /* Deliberately not set here: the composer re-ranks so the reasons the
       journey was chosen for come back with it. A shared link that arrives
       without its "why" is a recommendation with the argument torn off. */
    chosen = null;
    /* Put the answers back in the form too, so "ask me again" starts from what
       the link said rather than from blank. */
    brief.wants.forEach(function (k) {
      var el = form.querySelector('[name="want"][value="' + k + '"]');
      if (el) el.checked = true;
    });
    var setOne = function (n, v) {
      var el = v && form.querySelector('[name="' + n + '"][value="' + v + '"]');
      if (el) el.checked = true;
    };
    setOne('month', s.month);
    setOne('pacing', s.pacing);
    setOne('party', s.party);
    brief.style.forEach(function (k) { setOne('style', k); });
    openComposer(s.country, true);
    return true;
  }

  window.addEventListener('hashchange', function () {
    var s = E.decode(location.hash);
    if (!s.country && !compose.hidden) {
      compose.hidden = true; form.hidden = false; show(1);
    }
  });

  paintSaved();
  var restored = restore();
  var entered = !restored && entry();
  track('journey_started', {source: restored ? 'link' : (entered ? 'link' : 'questions')});
  if (!restored && !entered) show(1);
})();
