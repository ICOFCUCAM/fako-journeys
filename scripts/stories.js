/* The reading room — /stories.
 * ---------------------------------------------------------------------------
 * The page is whole before this loads: every rail, every portrait and the whole
 * contemporary panel are in the HTML. Two things need a browser and only two.
 *
 *   the search       matching happens in story-search.js against the graph
 *   this month       which countries are written up as good in the month it is
 *                    where the visitor is sitting
 *
 * The second is the honest version of a "Today in Africa" module. There is no
 * feed, no ticketing partner and no dated event anywhere in this project, so a
 * live section would have to be invented, and inventing it is the one thing
 * this site does not do. What it can say truthfully is: it is August on your
 * device, and these eleven countries are written up as good in August. That is
 * a smaller sentence and it is one that is actually true.
 */
(function () {
  'use strict';

  var track = function (name, props) {
    if (window.AfrinkongEvents) window.AfrinkongEvents.track(name, props);
  };

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

  var boot = {};
  try {
    boot = JSON.parse((document.getElementById('sx-boot') || {}).textContent || '{}');
  } catch (e) { boot = {}; }

  var S = window.AfrinkongSearch;
  var graph = null;
  var stories = [];
  var box = document.getElementById('sx-q');
  var said = document.getElementById('sx-said');
  var panel = document.getElementById('sx-results');

  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ---- fetch, once, and only when it is needed ---------------------------- */

  var loading = null;

  function data() {
    if (loading) return loading;
    loading = Promise.all([
      fetch(boot.graph || '/data/graph.json').then(function (r) { return r.json(); }),
      fetch(boot.data || '/data/stories.json').then(function (r) { return r.json(); })
    ]).then(function (both) {
      graph = both[0];
      stories = (both[1] || {}).stories || [];
      return true;
    }).catch(function () {
      /* A search that cannot reach its index says so rather than saying
         "no results", which would be a different and untrue answer. */
      graph = null;
      return false;
    });
    return loading;
  }

  /* ---- search ------------------------------------------------------------- */

  var KIND = {place: 'Write-up', story: 'Chapter', portrait: 'Portrait'};

  function draw(result) {
    if (!panel) return;
    var hits = result.hits.slice(0, 36);
    if (!hits.length) {
      panel.innerHTML = '<p class="sx-none">Nothing on this site matches that. '
        + 'It has not been rounded to the nearest thing it does have — '
        + 'twenty-two countries are written up here and the rest of Africa is '
        + 'not, which is worth being plain about.</p>';
      panel.hidden = false;
      return;
    }
    panel.innerHTML = hits.map(function (h) {
      return '<a class="sx-hit" href="' + esc(h.url) + '">'
        + '<span>' + esc(KIND[h.kind] || 'Result') + ' &middot; '
        + esc(h.countryName || '') + '</span>'
        + '<b>' + esc(h.title) + '</b>'
        + (h.text ? '<p>' + esc(h.text) + '</p>' : '')
        + '</a>';
    }).join('');
    panel.hidden = false;
  }

  function ask() {
    var query = (box.value || '').trim();
    if (!query) {
      if (panel) { panel.hidden = true; panel.innerHTML = ''; }
      if (said) said.textContent = '';
      return;
    }
    data().then(function (ok) {
      if (!ok || !graph || !S) {
        if (said) said.textContent = 'The index could not be loaded, so nothing '
          + 'was searched. This is not "no results".';
        return;
      }
      var result = S.search(query, graph, stories);
      if (said) said.textContent = S.said(result, graph);
      draw(result);
      /* The count travels; the words never do. */
      track('story_searched', {matched: Math.min(result.hits.length, 999)});
    });
  }

  /* A query arriving in the address bar — from the 404's search box, or from a
     link somebody sent — runs immediately. The form on the 404 posts here rather
     than pretending to search a page that does not exist. */
  if (box) {
    var arrived = (location.search.match(/[?&]q=([^&]*)/) || [])[1];
    if (arrived) {
      box.value = decodeURIComponent(arrived.replace(/\+/g, ' '));
      setTimeout(ask, 0);
    }
    var timer = null;
    box.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(ask, 220);
    });
    box.addEventListener('search', ask);
    var form = box.form;
    if (form) form.addEventListener('submit', function (ev) { ev.preventDefault(); ask(); });
    /* Warm the index on focus rather than on load: a visitor who never searches
       never pays for the index, and one who does has it by the time they have
       finished typing the first word. */
    box.addEventListener('focus', data, {once: true});
  }

  /* ---- this month --------------------------------------------------------- */

  /* The months travel inline in the boot block rather than in the graph: this
     section is the first thing below the fold and needs about a kilobyte, and
     putting the whole index on the critical path of a page most people scroll
     and never search would be paying for a search nobody ran. */
  var list = document.getElementById('sx-monthlist');
  var heading = document.getElementById('sx-monthh');
  if (list) {
    var month = new Date().getMonth() + 1;
    if (heading) heading.textContent = 'Africa in ' + MONTHS[month - 1];
    var when = boot.when || {};
    var good = S ? S.monthly(month, {countries: when})
      : Object.keys(when).filter(function (slug) {
        return (when[slug].months || []).indexOf(month) >= 0;
      });
    if (!good.length) {
      list.innerHTML = '<p class="sx-none">No country in this set is written '
        + 'up as good in ' + MONTHS[month - 1] + '. That is what the files '
        + 'say, so that is what this says.</p>';
    } else {
      list.innerHTML = good.map(function (slug) {
        return '<a class="sx-mo" href="/portrait/' + esc(slug) + '#when">'
          + '<b>' + esc(when[slug].name) + '</b>'
          + '<span>' + esc(when[slug].line) + '</span></a>';
      }).join('');
      track('month_seen', {month: month});
    }
  }

  /* ---- what was opened ---------------------------------------------------- */

  document.addEventListener('click', function (ev) {
    var card = ev.target.closest && ev.target.closest('.sx-card,.sx-now,.sx-hit');
    if (!card) return;
    var rail = card.closest('.sx-rail');
    var link = card.tagName === 'A' ? card : card.querySelector('a');
    var href = link ? link.getAttribute('href') || '' : '';
    var slug = href.indexOf('/portrait/') === 0
      ? href.slice(10).split('#')[0] : (card.getAttribute('data-country') || null);
    track('story_opened', {
      country: slug,
      format: rail ? rail.getAttribute('data-format') : null
    });
  });
}());
