/* The Journey Fund estimator — the interface. /journey-fund.
 * ===========================================================================
 * The arithmetic is in scripts/fund-math.js and is tested there. This file is
 * the part that reads a form, writes a paragraph and remembers a choice: no
 * sums live here, and any that appear should be moved.
 *
 * WHAT IT DOES NOT DO
 *
 * It does not talk to a server, because there isn't one. It does not know who
 * you are, does not mint an identifier, does not send anything anywhere, and
 * does not touch money in any sense — Afrinkong holds nothing.
 *
 * THE ONE THING IT WRITES
 *
 * `localStorage`, and only when the reader presses "keep this plan". One key,
 * holding the choices — destination, tier, days, month, rhythm — and the rate
 * card version they were priced against. No name, no email, no figure that
 * identifies anybody. It is a bookmark with arithmetic attached, and the page
 * says exactly that beside the button.
 *
 * WHY THE MONTHS ARE BUILT HERE
 *
 * The page is static and cached. A month strip rendered at build time offers
 * the same soonest month forever and is wrong within weeks, silently. The
 * clock belongs to the browser, so the calendar does too.
 *
 * WHY NOTHING ANIMATES
 *
 * A figure that counts up on arrival is a figure performing at you. These
 * change when you change something, at rest, immediately.
 */
(function () {
  'use strict';

  var F = window.AfrinkongFund;
  var node = document.getElementById('jf-data');
  var form = document.getElementById('jf-form');
  if (!F || !node || !form) return;

  var D;
  try { D = JSON.parse(node.textContent || '{}'); } catch (e) { return; }
  if (!D.tiers || !D.countries) return;

  var page = document.querySelector('.jf-page');
  var placeSel = document.getElementById('jf-place');
  var monthSel = document.getElementById('jf-month');
  var whereEl = document.getElementById('jf-where');
  var whenEl = document.getElementById('jf-when');
  var sumEl = document.getElementById('jf-sum');
  var saidEl = document.getElementById('jf-said');
  var reachEl = document.getElementById('jf-reach');
  var daysAsk = document.getElementById('jf-days-ask');
  var tierAsk = document.getElementById('jf-tier-ask');
  var whereFine = document.getElementById('jf-where-fine');
  var keepBtn = document.getElementById('jf-keep');
  var keptNote = document.getElementById('jf-kept');
  var sendLink = document.getElementById('jf-send');

  var STORE = 'afrinkong.journey-fund.plan';
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December'];

  /* ---- reading the form -------------------------------------------------- */

  function picked(name) {
    var el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : null;
  }

  function state() {
    return {
      kind: picked('jf-kind') || 'country',
      place: placeSel.value,
      days: parseInt(picked('jf-days'), 10) || D['default'].days,
      tier: picked('jf-tier') || D['default'].tier,
      month: monthSel.value,
      rhythm: picked('jf-rhythm') || 'monthly'
    };
  }

  /* ---- what the browser writes ------------------------------------------- */

  function fillPlaces(kind) {
    /* The chosen destination survives the list being rebuilt. Without this the
       server-rendered selection is thrown away on the first call and the page
       silently reverts to whatever sorts first, which is how it came to open
       on Algeria. */
    var was = placeSel.value;
    var list = kind === 'crossing' ? D.routes : D.countries;
    var frag = document.createDocumentFragment();
    var has = false;
    for (var i = 0; i < list.length; i++) {
      var o = document.createElement('option');
      o.value = list[i].s;
      o.textContent = list[i].n;
      if (o.value === was) has = true;
      frag.appendChild(o);
    }
    placeSel.textContent = '';
    placeSel.appendChild(frag);
    if (has) placeSel.value = was;
    else if (kind !== 'crossing' && D.first) placeSel.value = D.first;
    whereFine.textContent = kind === 'crossing'
      ? D.routes.length + ' crossings, each priced whole rather than by the day.'
      : D.countries.length + ' countries, priced per vehicle per day.';
    /* A crossing has no tier and no duration to choose: the route is the
       journey. Hiding the two questions is more honest than showing them
       disabled, which would imply they apply and are merely unavailable. */
    daysAsk.hidden = kind === 'crossing';
    tierAsk.hidden = kind === 'crossing';
  }

  function fillMonths() {
    var now = new Date();
    var frag = document.createDocumentFragment();
    var last = F.SOONEST_MONTHS + F.STRIP_MONTHS;
    for (var i = F.SOONEST_MONTHS; i <= last; i++) {
      var d = new Date(now.getFullYear(), now.getMonth() + i, 1);
      var o = document.createElement('option');
      o.value = d.getFullYear() + '-' + (d.getMonth() + 1);
      o.textContent = MONTHS[d.getMonth()] + ' ' + d.getFullYear();
      if (i === 12) o.selected = true;
      frag.appendChild(o);
    }
    monthSel.textContent = '';
    monthSel.appendChild(frag);
  }

  function row(label, value) {
    return '<div><span>' + label + '</span><span>' + value + '</span></div>';
  }

  function total(label, value) {
    return '<div class="jf-rule"><span>' + label + '</span><b>' + value
         + '</b></div>';
  }

  function draw() {
    var s = state();
    var p = F.price(D, s);
    if (!p) return;

    /* The tone. The page takes the region of the place being built toward, so
       changing your mind about the destination changes the colour of the page.
       A crossing takes the region it opens in.

       Set from the payload rather than matched against a list of regions in
       the stylesheet: tourism/regions.json is the one file that knows what
       East Africa looks like, and a copy of those five values anywhere else is
       a copy that can be wrong. */
    var here = s.kind === 'crossing' ? F.routeOf(D, s.place)
                                     : F.countryOf(D, s.place);
    if (page && here && here.r) {
      page.setAttribute('data-region', here.r);
      var tone = D.tones && D.tones[here.r];
      if (tone) page.style.setProperty('--jf-tone', tone);
    }

    whereEl.textContent = here ? here.n : '';
    var label = monthSel.options[monthSel.selectedIndex];
    whenEl.textContent = label ? label.textContent : '';

    /* The itemisation, then the total. That order is deliberate: a total on
       its own is a price tag; a total underneath its parts is an estimate,
       which is what this actually is. */
    sumEl.innerHTML = p.band
      ? row(p.countries + ' countries, ' + p.days + ' days',
            F.money(p.low) + ' to ' + F.money(p.high))
        + total('Journey target', F.money(p.plan))
      : row(p.tierName + ', ' + p.days + ' days', F.money(p.ground))
        + row('Airport arrival coordination', F.money(p.arrival))
        + total('Journey target', F.money(p.total));

    var months = F.monthsAhead(s.month, new Date());
    var r = F.rhythm(p.plan, months, s.rhythm);
    reachEl.hidden = true;

    if (r.problem === 'toosoonquarterly') {
      /* Not "you cannot" — what would work instead. Under six months there is
         room for one quarterly payment, and one payment is a purchase rather
         than a rhythm, so the honest answer is the other rhythm or a later
         month. */
      saidEl.textContent = 'Too close for a quarterly rhythm — that would be a '
        + 'single payment rather than something put aside. Every month reaches '
        + 'it, or choose a later month.';
      show(F.doors(D, p, months, s));
      return;
    }
    if (r.problem) {
      saidEl.textContent = 'Choose a month far enough ahead to put something '
        + 'aside in.';
      return;
    }

    /* The month is the subject and the money is the predicate, which is the
       whole argument of this product expressed as grammar. */
    saidEl.innerHTML = 'Planned contribution: <b>' + F.money(r.per)
      + '</b>, over ' + r.every + '.';

    if (r.per > F.CEILING) show(F.doors(D, p, months, s));
  }

  function show(doors) {
    if (!doors.length) return;
    /* "Or" was the label, which read as a shrug above a list. The heading of
       this box should say what the box is for, and what it is for is naming
       the shapes of journey that the arithmetic does reach — a question about
       the journey rather than about the reader. */
    reachEl.innerHTML = '<b>What would reach it</b>'
      + doors.join(', or ').replace(/^./, function (c) { return c.toUpperCase(); })
      + '.';
    reachEl.hidden = false;
  }

  /* ---- keeping it -------------------------------------------------------- */

  function say(text) {
    keptNote.textContent = text;
    keptNote.hidden = false;
  }

  function keep() {
    var s = state();
    s.v = D.v;
    try {
      window.localStorage.setItem(STORE, JSON.stringify(s));
      say('Kept in this browser. Nothing was sent anywhere.');
    } catch (e) {
      /* Private browsing, a storage quota, or a reader who has turned it off.
         None of those is an error on their part, and the page still works — it
         simply cannot remember. Saying so is better than a button that looks
         like it worked. */
      say('This browser will not let a page store anything, so the plan '
          + 'cannot be kept here. Everything else on the page still works.');
    }
  }

  function restore() {
    var raw;
    try { raw = window.localStorage.getItem(STORE); } catch (e) { return; }
    if (!raw) return;
    var s;
    try { s = JSON.parse(raw); } catch (e) { return; }
    if (!s || !s.place) return;

    check('jf-kind', s.kind);
    fillPlaces(s.kind || 'country');
    placeSel.value = s.place;
    check('jf-days', String(s.days));
    check('jf-tier', s.tier);
    check('jf-rhythm', s.rhythm);
    /* A month that has since passed is simply not in the strip any more, so
       it is dropped rather than re-offered. The default stands. */
    for (var i = 0; s.month && i < monthSel.options.length; i++) {
      if (monthSel.options[i].value === s.month) {
        monthSel.value = s.month;
        break;
      }
    }
    /* The rate card can be revised between keeping a plan and returning to it.
       Without this the reader sees a different figure and has no way to know
       whether they changed something or we did. */
    if (s.v && D.v && s.v !== D.v) {
      say('Our rates have been revised since you kept this plan, so the figure '
          + 'below is not the one you saw.');
    }
  }

  function check(name, value) {
    if (value == null) return;
    var el = form.querySelector('input[name="' + name + '"][value="'
                                + value + '"]');
    if (el) el.checked = true;
  }

  /* The enquiry carries the plan as a sentence, in the query string /enquire
     already reads. No new endpoint and no new format. */
  function retarget() {
    if (!sendLink) return;
    var s = state();
    var here = s.kind === 'crossing' ? F.routeOf(D, s.place)
                                     : F.countryOf(D, s.place);
    if (!here) return;
    var label = monthSel.options[monthSel.selectedIndex];
    var said = here.n + (label ? ', ' + label.textContent : '');
    if (s.kind !== 'crossing') {
      said += ' — ' + F.tierOf(D, s.tier).name + ', ' + s.days + ' days';
    }
    sendLink.href = '/enquire?journey=' + encodeURIComponent(said);
  }

  /* ---- wiring ------------------------------------------------------------ */

  fillPlaces('country');
  fillMonths();
  restore();

  form.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'jf-kind') fillPlaces(e.target.value);
    draw();
    retarget();
  });
  placeSel.addEventListener('change', function () { draw(); retarget(); });
  monthSel.addEventListener('change', function () { draw(); retarget(); });
  if (keepBtn) keepBtn.addEventListener('click', keep);

  draw();
  retarget();
}());
