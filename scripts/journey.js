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

  var brief = {wants: [], month: null, pacing: 'open', party: null, style: [], seed: 0};
  var picks = [];              /* the three the engine returned */
  var chosen = null;           /* the one being composed */
  var places = {};             /* slug -> the atlas payload, fetched once */
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
    if (t.hasAttribute('data-next')) { readForm(); show(step + 1); }
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
  });
  form.addEventListener('submit', function (e) { e.preventDefault(); readForm(); runReveal(); });

  /* ---- the reveal -------------------------------------------------------- */

  function runReveal(quiet) {
    var out = E.recommend(D, brief, 3);
    picks = out.picks;
    if (!picks.length) { noAnswer(); return; }
    chosen = picks[0];
    form.hidden = true;
    compose.hidden = true;
    reveal.hidden = false;
    paintReveal();
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
  }

  /* Who lives there, before why we chose it. A country that arrives as an
     outline, a season and a reason is a destination; a country that arrives
     with the people who live in it named is a place. Both lines are write-ups
     that already exist in that country's own file. */
  function meetsBlock(c) {
    if (!c.meets || !c.meets.length) return '';
    return '<p class="jn-meets"><span>Who lives here</span>'
      + c.meets.map(function (m) { return esc(m.title); }).join(' \u00b7 ')
      + ' <a href="/meet#/' + esc(chosen.slug) + '">Meet ' + esc(c.name)
      + ' &rarr;</a></p>';
  }

  /* Why this one, in the words of the thing that was actually matched. No
     percentage: a number implies a precision the dataset does not have, and a
     reason a traveller can check is worth more than one they cannot. */
  function whyBlock(p) {
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
    return '<p class="jn-why-head">Why this one</p><ul class="jn-why-list">'
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

  reveal.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-alt],[data-compose],[data-others],[data-restart]') : null;
    if (!t) return;
    if (t.hasAttribute('data-alt')) {
      var found = picks.filter(function (p) { return p.slug === t.dataset.alt; })[0];
      chosen = found || E.rank(D, {wants: [], month: brief.month}).filter(function (p) {
        return p.slug === t.dataset.alt; })[0];
      if (!chosen) return;
      picks = [chosen].concat(picks.filter(function (p) { return p.slug !== chosen.slug; }));
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
    } else if (t.hasAttribute('data-restart')) {
      /* Re-rolling changes the tie-break, not the rules: two countries that
         scored the same get to take turns. It travels in the link, so a
         shared journey is still the same journey. */
      brief.seed = (brief.seed + 1) % 7;
      reveal.hidden = true;
      form.hidden = false;
      show(1);
    }
  });

  /* ---- the composer ------------------------------------------------------ */

  function fetchPlaces(slug) {
    if (places[slug]) return Promise.resolve(places[slug]);
    return fetch('/data/atlas/' + encodeURIComponent(slug) + '.json')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { places[slug] = p; return p; })
      .catch(function () { places[slug] = {slug: slug, places: []}; return places[slug]; });
  }

  function openComposer(slug, keep) {
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
      writeHash();
      window.scrollTo({top: 0, behavior: 'auto'});
    });
  }

  function stageObjects() {
    var pack = places[chosen.slug] || {places: []};
    return stages.map(function (id) {
      return pack.places.filter(function (p) { return p.id === id; })[0];
    }).filter(Boolean);
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

    /* The timeline. Stage names and country facts are the dataset's; the day
       numbers are arithmetic on the length the traveller chose, and the line
       under the timeline says exactly that rather than implying a schedule. */
    var arrival = c.operator && c.operator.base ? c.operator.base : null;
    var rows = E.timeline(st, pace.days, arrival);
    document.getElementById('jn-line').innerHTML = rows.map(function (r) {
      var span = r.from === r.to ? 'Day ' + pad(r.from)
        : 'Days ' + pad(r.from) + '–' + pad(r.to);
      if (r.kind !== 'stage') {
        return '<li class="jn-leg jn-leg--edge"><span class="jn-leg-day">' + span + '</span>'
          + '<span class="jn-leg-body"><b>' + esc(r.label) + '</b></span></li>';
      }
      return '<li class="jn-leg"><span class="jn-leg-day">' + span + '</span>'
        + '<span class="jn-leg-body"><b>' + esc(r.stage.title) + '</b>'
        + '<span class="jn-leg-line">' + esc(r.stage.text) + '</span>'
        + '<span class="jn-leg-meta">' + esc(r.stage.group) + '</span></span>'
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

    document.getElementById('jn-who').innerHTML = whoBlock(c);

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
    var begin = document.getElementById('jn-begin');
    begin.href = '/contact?journey=' + encodeURIComponent(enquiry(title, c, rows, pace));
    begin.textContent = c.operator ? 'Send this to ' + c.operator.name : 'Begin this journey';
    begin.insertAdjacentHTML('beforeend', '<i>&rarr;</i>');
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /* Local means a company with an address, a year and a sentence about what it
     actually runs. Where we have that, print it; where we do not, say what is
     true — that the country is covered by a licensed company based in it —
     rather than pinning on a badge that means nothing. */
  function whoBlock(c) {
    if (!c.operator) {
      return '<div class="jn-who-in"><span class="af-stamp">Who would run it</span>'
        + '<b>A licensed company based in ' + esc(c.name) + '</b>'
        + '<p>We have not published its details here yet. Send the journey and we '
        + 'will put you in touch with the company that operates it.</p></div>';
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

  compose.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-toggle],[data-drop],[data-save],[data-share]') : null;
    if (!t) return;
    if (t.hasAttribute('data-toggle')) {
      var id = t.dataset.toggle;
      var at = stages.indexOf(id);
      if (at >= 0) stages.splice(at, 1); else stages.push(id);
      paintComposer(); writeHash();
    } else if (t.hasAttribute('data-drop')) {
      stages = stages.filter(function (x) { return x !== t.dataset.drop; });
      paintComposer(); writeHash();
    } else if (t.hasAttribute('data-save')) {
      save();
    } else if (t.hasAttribute('data-share')) {
      share();
    }
  });

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
  if (!restore()) show(1);
})();
