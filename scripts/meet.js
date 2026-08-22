/* The human layer — two ways of asking the same seven questions.
 *
 * @product: live | @gate: none | @surface: /meet
 * ---------------------------------------------------------------------------
 *   one door,  twenty-two countries   #/food
 *   one country, seven doors          #/cameroon
 *   one answer                        #/food/cameroon
 *
 * The first mode is the argument of the page: the same question put to the
 * whole continent, coming back twenty-two different ways. The second is the
 * one anybody planning a trip actually wants. They are the same data read
 * along two axes, so there is one payload and one render.
 *
 * Nothing here writes a sentence. Every line on screen is a caption or a
 * description already written for that country, an operator's own words, or
 * this file's own labels — and the guide component renders nothing at all
 * while people.json is empty, which is the point of it.
 */
(function () {
  'use strict';

  var root = document.getElementById('mt');
  var doors = document.getElementById('doors');
  var stage = document.getElementById('stage');
  var box = document.getElementById('mt-answers');
  var eyebrow = document.getElementById('mt-eyebrow');
  var asks = document.getElementById('mt-asks');
  var line = document.getElementById('mt-line');
  if (!root || !box) return;

  var PEOPLE = readJSON('mt-people', []);
  var VOICES = readJSON('mt-voices', []);
  var reduced = matchMedia('(prefers-reduced-motion: reduce)');
  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };

  var D = null;                 /* data/meet.json, fetched once */
  var state = {strand: null, country: null};
  var order = [];               /* countries, in the order the continent reads */

  function readJSON(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }
  function strandBy(key) {
    for (var i = 0; i < D.strands.length; i++) {
      if (D.strands[i].key === key) return D.strands[i];
    }
    return D.strands[0];
  }

  /* ---- the two views ------------------------------------------------------ */

  /* One question, every country. Ordered geographically rather than
     alphabetically, so reading down the page is a sweep across the continent
     and the differences land as differences between neighbours. */
  function paintStrand() {
    var s = strandBy(state.strand);
    var rows = D.answers[s.key] || {};
    var slugs = order.filter(function (x) { return rows[x]; });
    eyebrow.textContent = slugs.length + ' countries · ' + s.title;
    asks.textContent = s.asks;
    line.textContent = s.line;
    box.className = 'mt-answers';
    box.innerHTML = slugs.map(function (slug) {
      var c = D.countries[slug];
      var a = rows[slug][0];
      return '<article class="mt-answer">'
        + '<p class="mt-answer-where"><button type="button" data-open="' + esc(slug)
        + '">' + esc(c.name) + '</button><span>' + esc(c.region) + '</span></p>'
        + '<h3 class="mt-answer-title">' + esc(a.title) + '</h3>'
        + '<p class="mt-answer-text">' + esc(a.text) + '</p>'
        + (rows[slug].length > 1
           ? '<p class="mt-answer-more">' + esc(rows[slug][1].title) + '</p>' : '')
        + '</article>';
    }).join('');
  }

  /* One country, all seven doors. The door keeps its universal word and shows
     that country's particular answer under it, which is what stops the page
     reading as seven generic cards. */
  function paintCountry() {
    var c = D.countries[state.country];
    if (!c) { paintStrand(); return; }
    eyebrow.textContent = c.region + ' · ' + D.strands.length + ' questions';
    asks.textContent = c.name;
    line.textContent = c.tagline;
    box.className = 'mt-answers mt-answers--country';
    var rooms = D.strands.map(function (s, i) {
      var rows = (D.answers[s.key] || {})[state.country];
      if (!rows || !rows.length) {
        return '<article class="mt-room mt-room--empty">'
          + '<p class="mt-room-eye">' + esc(s.title) + '</p>'
          + '<p class="mt-room-none">Not written up for ' + esc(c.name)
          + ' yet.</p></article>';
      }
      var open = state.strand === s.key;
      return '<article class="mt-room"' + (open ? ' data-open' : '') + '>'
        + '<button class="mt-room-hit" type="button" data-room="' + esc(s.key) + '"'
        + ' aria-expanded="' + (open ? 'true' : 'false') + '">'
        + '<span class="mt-room-no">' + (i < 9 ? '0' : '') + (i + 1) + '</span>'
        + '<span class="mt-room-body"><span class="mt-room-eye">' + esc(s.title)
        + '</span><b>' + esc(rows[0].title) + '</b></span>'
        + '<span class="mt-room-go" aria-hidden="true">&rarr;</span></button>'
        + '<div class="mt-room-in">'
        + rows.map(function (a, n) {
            return (n ? '<h4 class="mt-room-sub">' + esc(a.title) + '</h4>' : '')
              + '<p class="mt-room-text">' + esc(a.text) + '</p>'
              + '<p class="mt-room-cat">' + esc(a.group) + '</p>';
          }).join('')
        + '</div></article>';
    }).join('');

    box.innerHTML = '<div class="mt-country">'
      + '<div class="mt-country-shape" id="mt-shape"></div>'
      + '<div class="mt-rooms">' + rooms + '</div>'
      + '</div>'
      + voiceBlock(c) + peopleBlock(c)
      + '<div class="mt-acts">'
      + '<a class="af-btn af-btn--solid" href="/journey#/j/' + esc(state.country)
      + '/">Build a journey here<i>&rarr;</i></a>'
      + '<a class="af-btn af-btn--quiet" href="/portrait/' + esc(state.country)
      + '">Read the portrait</a>'
      + '<a class="af-btn af-btn--quiet" href="/atlas#/' + esc(state.country)
      + '">Find it on the map</a>'
      + '<a class="af-btn af-btn--quiet" href="' + esc(c.url) + '">All twenty-seven</a>'
      + '</div>';
    drawShape(state.country);
  }

  /* The silhouette is fetched only when a country is opened, and only once —
     twenty-nine kilobytes of outlines is not worth carrying to somebody who
     came to read about food. */
  function drawShape(slug) {
    var host = document.getElementById('mt-shape');
    if (!host) return;
    window.AfrinkongWindow.shapes().then(function (all) {
      var s = all[slug], c = D.countries[slug];
      if (!s || !c || !host.isConnected) return;
      host.toggleAttribute('data-photo', !!c.window);
      host.innerHTML = window.AfrinkongWindow.svg(s, {
        image: c.window, alt: c.windowAlt, name: c.name, ident: 'mtw',
        classes: 'af-window-svg'})
        + '<span class="mt-country-cap">' + esc(c.name) + '</span>';
    });
  }

  /* ---- the people components --------------------------------------------- */

  /* Local Voice. Where an operator has written something down it is printed in
     their name. Where they have not, the block still appears — but it says who
     the company is and what they run, in their own sentence, and anything the
     site itself knows is attributed to the site. Nothing is put in anybody's
     mouth. */
  function voiceBlock(c) {
    var said = VOICES.filter(function (v) { return v.country === state.country; })[0];
    if (said) {
      return '<section class="mt-voice"><span class="af-stamp">Local voice</span>'
        + (said.asked ? '<p class="mt-voice-q">' + esc(said.asked) + '</p>' : '')
        + '<blockquote class="mt-voice-said">&ldquo;' + esc(said.said) + '&rdquo;</blockquote>'
        + '<p class="mt-voice-by">' + esc(said.by ? said.by + ', ' : '')
        + esc(said.operator.name) + ' &mdash; ' + esc(said.operator.base) + '</p>'
        + '</section>';
    }
    /* Where there is no operator there is no quote, so nothing is rendered.
       The block that stood here printed a paragraph announcing the absence —
       "there is nobody here to quote, and we will not write a note on behalf
       of a company we have not named" — which is a section whose entire
       content is an apology for not being a section. Not writing a fake quote
       is right; devoting a panel to saying so is not. */
    if (!c.operator) return '';
    return '<section class="mt-voice"><span class="af-stamp">Local voice</span>'
      + '<blockquote class="mt-voice-said">&ldquo;' + esc(c.operator.line)
      + '&rdquo;</blockquote>'
      + '<p class="mt-voice-by">' + esc(c.operator.name) + ' &mdash; '
      + esc(c.operator.base) + (c.operator.since ? ', since ' + esc(c.operator.since) : '')
      + '</p>'
      + '<p class="mt-voice-note">That is the company’s own description of what '
      + 'it runs. Anything else on this page is Afrinkong’s writing, not theirs.</p>'
      + '</section>';
  }

  /* Guides. people.json is empty and this renders nothing while it is — a
     fabricated guide is worse than an absent one, because a visitor cannot tell
     the difference until they arrive. */
  function peopleBlock(c) {
    var here = PEOPLE.filter(function (p) { return p.country === state.country; });
    if (!here.length) return '';
    return '<section class="mt-people"><span class="af-stamp">Who might take you</span>'
      + '<ul class="mt-people-list">' + here.map(function (p) {
        return '<li class="mt-person">'
          + (p.photo ? '<img src="' + esc(p.photo) + '" alt="' + esc(p.photoAlt)
             + '" loading="lazy" width="240" height="300">' : '')
          + '<div><b>' + esc(p.name) + '</b>'
          + '<span class="mt-person-role">' + esc(p.role)
          + (p.base ? ' &middot; ' + esc(p.base) : '') + '</span>'
          + (p.line ? '<p>' + esc(p.line) + '</p>' : '')
          + '<dl class="mt-person-facts">'
          + (p.languages && p.languages.length
             ? '<dt>Languages</dt><dd>' + esc(p.languages.join(' · ')) + '</dd>' : '')
          + (p.since ? '<dt>Guiding since</dt><dd>' + esc(p.since) + '</dd>' : '')
          + (p.speciality ? '<dt>Speciality</dt><dd>' + esc(p.speciality) + '</dd>' : '')
          + '</dl></div></li>';
      }).join('') + '</ul></section>';
  }

  /* ---- chrome ------------------------------------------------------------ */

  function paintDoors() {
    [].forEach.call(doors.querySelectorAll('[data-strand]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.strand === state.strand
        && !state.country));
    });
    [].forEach.call(doors.querySelectorAll('[data-country]'), function (a) {
      a.toggleAttribute('data-on', a.dataset.country === state.country);
    });
    root.dataset.mode = state.country ? 'country' : 'strand';
  }

  function render() {
    paintDoors();
    if (state.country) paintCountry(); else paintStrand();
  }

  function go(next, push) {
    state = {strand: next.strand || state.strand, country: next.country || null};
    if (!D.answers[state.strand]) state.strand = D.strands[0].key;
    var h = '#/' + (state.country ? state.country + (next.strand ? '/' + state.strand : '')
                                  : state.strand);
    if (push !== false && h !== location.hash) history.pushState(null, '', h);
    if (state.country) track('meet_country_opened', {country: state.country});
    else track('meet_strand_opened', {strand: state.strand});
    render();
    stage.scrollIntoView({behavior: reduced.matches ? 'auto' : 'smooth', block: 'start'});
  }

  function fromHash(push) {
    var parts = (location.hash || '').replace(/^#\/?/, '').split('/').filter(Boolean);
    var strand = null, country = null;
    parts.forEach(function (p) {
      if (D.answers[p]) strand = p;
      else if (D.countries[p]) country = p;
    });
    state.strand = strand || D.strands[0].key;
    state.country = country;
    render();
    if (push) history.replaceState(null, '', '#/' + (country || state.strand));
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest(
      '[data-strand],[data-country],[data-open],[data-room]') : null;
    if (!t) return;
    if (t.hasAttribute('data-strand')) { go({strand: t.dataset.strand, country: null}); }
    else if (t.hasAttribute('data-country')) { e.preventDefault(); go({country: t.dataset.country}); }
    else if (t.hasAttribute('data-open')) { go({country: t.dataset.open}); }
    else if (t.hasAttribute('data-room')) {
      /* Inside a country the doors open in place rather than navigating: you
         are already in the room, and being thrown back to the top of the page
         to read the next paragraph is not opening a door. */
      var room = t.closest('.mt-room');
      var open = room.hasAttribute('data-open');
      [].forEach.call(box.querySelectorAll('.mt-room[data-open]'), function (r) {
        r.removeAttribute('data-open');
        r.querySelector('[aria-expanded]').setAttribute('aria-expanded', 'false');
      });
      if (!open) {
        room.setAttribute('data-open', '');
        t.setAttribute('aria-expanded', 'true');
        state.strand = t.dataset.room;
        history.replaceState(null, '', '#/' + state.country + '/' + state.strand);
      }
    }
  });

  /* Escape climbs back out of a country to the continent-wide view, which is
     the only place there is to go. */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && state.country) go({country: null, strand: state.strand});
  });

  window.addEventListener('popstate', function () { fromHash(false); });

  fetch('/data/meet.json').then(function (r) { return r.json(); })
    .then(function (j) {
      D = j;
      /* Geographic order, taken from the strip the page already printed, so
         the two agree and neither has to carry a second copy of it. */
      order = [].map.call(doors.querySelectorAll('[data-country]'),
        function (a) { return a.dataset.country; });
      fromHash(true);
    })
    .catch(function () {
      /* The first question, answered by everybody, is already on the page:
         if the payload never arrives the visitor still has that rather than
         an empty frame. */
      root.setAttribute('data-offline', '');
    });
})();
