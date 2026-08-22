/* The long read — /portrait/<country>.
 *
 * @product: live | @gate: none | @surface: /portrait/*
 * ---------------------------------------------------------------------------
 * The page is already complete before this file arrives. Every chapter, every
 * picture, every link and every anchor is in the HTML, which is the whole point
 * of generating these at build time: a portrait read with JavaScript switched
 * off is the same portrait.
 *
 * So this adds three things and nothing else:
 *
 *   how far through you are      a progress bar, driven by scroll
 *   where you are               the contents rail marks the chapter you are in
 *   what month it is            the season band says so, from the visitor's own
 *                               clock — which is the only "now" this site has
 *
 * The third one is worth being careful about. There is no live feed anywhere in
 * this project and no dated event in the dataset, so "right now" can only ever
 * mean the month on the reader's device compared against the months the country
 * file lists. That is a smaller claim than a calendar and it is one this site
 * can actually stand behind.
 */
(function () {
  'use strict';

  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

  var body = document.body;
  var slug = (location.pathname.split('/').filter(Boolean).pop() || '')
    .replace(/\.html$/, '');

  /* ---- how far through ---------------------------------------------------- */

  var bar = document.querySelector('#po-progress i');
  var ticking = false;

  function paint() {
    ticking = false;
    if (!bar) return;
    var height = document.documentElement.scrollHeight - window.innerHeight;
    var done = height > 0 ? Math.min(1, Math.max(0, window.scrollY / height)) : 0;
    bar.style.transform = 'scaleX(' + done.toFixed(4) + ')';
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(paint);
  }

  addEventListener('scroll', onScroll, {passive: true});
  addEventListener('resize', onScroll, {passive: true});
  paint();

  /* ---- where you are ------------------------------------------------------ */
  /* An observer rather than a scroll handler doing arithmetic: the browser
     already knows which sections are on screen and asking it is both cheaper
     and correct at the top and bottom of the document, which hand-rolled
     versions of this usually are not. */

  var jumps = {};
  Array.prototype.forEach.call(
    document.querySelectorAll('.po-jump a'), function (a) {
      var id = (a.getAttribute('href') || '').slice(1);
      if (id) jumps[id] = a;
    });

  var read = {};
  var anchored = Object.keys(jumps)
    .map(function (id) { return document.getElementById(id); })
    .filter(Boolean);

  function mark(id) {
    Object.keys(jumps).forEach(function (k) {
      if (k === id) jumps[k].setAttribute('aria-current', 'true');
      else jumps[k].removeAttribute('aria-current');
    });
    var rail = document.querySelector('.po-jump');
    if (rail && jumps[id] && rail.scrollWidth > rail.clientWidth) {
      var a = jumps[id];
      var want = a.offsetLeft - rail.clientWidth / 2 + a.offsetWidth / 2;
      rail.scrollTo({left: Math.max(0, want), behavior: 'smooth'});
    }
    /* Counted once per chapter per page-load: how many chapters of a portrait
       get read at all is the one thing worth knowing about a long page, and
       counting it every time it scrolls back into view would answer a
       different question badly. */
    if (!read[id]) {
      read[id] = true;
      track('chapter_read', {country: slug, arc: id});
    }
  }

  if (anchored.length && 'IntersectionObserver' in window) {
    var seen = {};
    var watcher = new IntersectionObserver(function (rows) {
      rows.forEach(function (row) { seen[row.target.id] = row.isIntersecting; });
      for (var i = 0; i < anchored.length; i++) {
        if (seen[anchored[i].id]) { mark(anchored[i].id); return; }
      }
    }, {rootMargin: '-30% 0px -55% 0px'});
    anchored.forEach(function (el) { watcher.observe(el); });
  }

  /* ---- what month it is --------------------------------------------------- */

  var now = document.getElementById('po-now');
  if (now) {
    var month = new Date().getMonth() + 1;
    var chip = document.querySelector('.po-months [data-month="' + month + '"]');
    var good = chip && chip.className.indexOf('is-good') >= 0;
    var name = body.querySelector('.po-h1');
    name = name ? name.textContent.trim() : 'this country';
    if (chip) chip.className += ' is-here';
    now.textContent = 'Your device says it is ' + MONTHS[month - 1] + '. '
      + (good ? name + ' is written up as good in it.'
              : MONTHS[month - 1] + ' is not one of the months ' + name
                + ' is written up as good in — which is worth knowing rather '
                + 'than worth hiding.');
    track('month_seen', {month: month});
  }

  var region = document.querySelector('.pl-where a[href^="/atlas#/"]');
  track('portrait_opened', {
    country: slug,
    region: region ? (region.getAttribute('href') || '').split('/').pop() : null
  });
}());
