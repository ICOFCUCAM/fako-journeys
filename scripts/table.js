/* The table strip, turning over.
 * ---------------------------------------------------------------------------
 * PROGRESSIVE, NOT REQUIRED. The six cards the server sends are the six
 * NOW_PICK names, already photographed, already linked, already legible. What
 * this file adds is the other thirty-eight: each card keeps its own running
 * order and turns over to the next country in it, so a row about what a
 * continent eats stops being a row about six countries. With the script off,
 * or the fetch refused, the reader gets the six that were always there.
 *
 * ONE CARD AT A TIME. Six photographs changing together is a slideshow, and
 * this section is not a slideshow — it is a page that happens to be alive. The
 * strip advances a single card every NOW_HOLD seconds and comes back round to
 * the first, so any one card holds for six times that.
 *
 * THE DECKS SHARE NO COUNTRY. That is settled in the build (see table_deck in
 * gateway.py), not here, which is why this file never has to check whether the
 * frame it is about to show is already on screen somewhere else.
 *
 * IT STOPS WHEN ANYBODY IS USING IT. A link whose href changes under the
 * pointer is a link that sends you somewhere you did not choose, so the strip
 * holds still while the pointer is inside it, while focus is inside it, while
 * the tab is in the background, and whenever the reader presses the control.
 * WCAG 2.2.2 asks for a way to stop content that moves on its own; the pointer
 * and focus rules are not that mechanism, the button is, and the others are
 * ordinary courtesy. A reader who has asked for reduced motion starts held —
 * which is the starting position, not a veto: the button still works, because
 * a switch wired to nothing is its own kind of insult.
 *
 * NOTHING TURNS TO A PICTURE THAT IS NOT THERE YET. The next photograph is
 * loaded before the fade starts and a frame whose image will not load is
 * dropped from the deck rather than shown as a hole. A card that briefly got
 * worse on a timer would be a strange thing to have built on purpose.
 */
(function () {
  'use strict';

  var strip = document.querySelector('.wa-nows[data-table]');
  if (!strip || !window.fetch || !window.IntersectionObserver) return;

  var cards = Array.prototype.slice.call(strip.querySelectorAll('.wa-now[data-slot]'));
  if (!cards.length) return;

  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');

  var decks = null;      /* one running order per card, from the build */
  var at = [];           /* which frame each card is showing */
  var turn = 0;          /* whose turn it is to change */
  var timer = null;
  var hold = 4000;
  var paused = false;    /* the reader pressed the control */
  var busy = false;      /* a fade is in flight; do not start another */
  var button = null;

  /* ---- the control -------------------------------------------------------
     Built here rather than in the markup: without this script there is nothing
     to pause, and a button that controls nothing is worse than no button. */
  function control() {
    var wrap = document.createElement('p');
    wrap.className = 'wa-now-turn';
    button = document.createElement('button');
    button.type = 'button';
    button.className = 'wa-now-hold';
    button.setAttribute('aria-pressed', 'false');
    button.appendChild(document.createElement('i'));
    button.appendChild(document.createTextNode(''));
    button.addEventListener('click', function () {
      paused = !paused;
      say();
      if (paused) stop(); else start();
    });
    wrap.appendChild(button);
    strip.parentNode.insertBefore(wrap, strip.nextSibling);
    say();
  }

  function say() {
    if (!button) return;
    button.setAttribute('aria-pressed', paused ? 'true' : 'false');
    button.lastChild.nodeValue = paused ? 'Start the tables' : 'Hold the tables';
    strip.setAttribute('data-turning', paused ? 'no' : 'yes');
  }

  /* ---- holding still -----------------------------------------------------
     Any of these being true is enough. `paused` is the reader's decision and
     survives the pointer leaving; the rest are conditions and are re-read every
     time the timer would fire. */
  function frozen() {
    if (paused) return true;
    if (document.hidden) return true;
    if (strip.matches(':hover')) return true;
    return strip.contains(document.activeElement);
  }

  function start() {
    if (timer || !decks) return;
    timer = window.setInterval(tick, hold);
  }

  function stop() {
    if (!timer) return;
    window.clearInterval(timer);
    timer = null;
  }

  function tick() {
    if (frozen() || busy) return;
    var n = turn % cards.length;
    turn += 1;
    step(cards[n], n);
  }

  /* ---- one card's turn ---------------------------------------------------
     Load first, then fade, then swap under the fade, then fade back. Swapping
     before the photograph is decoded shows the alt text for a beat, which is
     the one thing a picture strip must never do. */
  function step(card, n) {
    var deck = decks[n];
    if (!deck || deck.length < 2) return;
    var next = (at[n] + 1) % deck.length;
    var frame = deck[next];
    if (!frame) return;

    busy = true;
    var pre = new window.Image();
    pre.onload = function () {
      at[n] = next;
      card.classList.add('is-turning');
      window.setTimeout(function () {
        paint(card, frame);
        card.classList.remove('is-turning');
        busy = false;
      }, 340);
    };
    pre.onerror = function () {
      /* A dead photograph is dropped rather than shown. The deck shortens and
         that card simply has one fewer country in it. */
      deck.splice(next, 1);
      if (next < at[n]) at[n] -= 1;
      busy = false;
    };
    pre.src = frame.image;
  }

  function paint(card, frame) {
    var img = card.querySelector('.wa-now-art img');
    var say = card.querySelector('.wa-now-say');
    if (!img || !say) return;
    card.setAttribute('href', frame.url);
    if (frame.tone) card.style.setProperty('--reg-tone', frame.tone);
    img.setAttribute('src', frame.image);
    img.setAttribute('alt', frame.text);
    var i = say.querySelector('i'), b = say.querySelector('b'),
        p = say.querySelector('p');
    /* · is the middot the server writes between the country and the arc;
       building it from the two fields keeps the separator in one place. */
    if (i) i.textContent = frame.name + ' · ' + frame.arc;
    if (b) b.textContent = frame.title;
    if (p) p.textContent = frame.text;
  }

  /* ---- fetch on approach -------------------------------------------------
     Ten kilobytes of running order is not worth carrying for a reader who
     never scrolls this far, which is the same argument loading="lazy" already
     makes for the photographs above it. */
  function load() {
    window.fetch('/data/table.json').then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (doc) {
      if (!doc || !doc.decks || doc.decks.length < cards.length) return;
      decks = doc.decks;
      hold = Math.max(2000, (doc.hold || 4) * 1000);
      at = cards.map(function () { return 0; });
      /* REDUCED MOTION SETS THE STARTING POSITION, IT DOES NOT OVERRULE THE
         READER. Held here rather than inside frozen(), so somebody who asks for
         a still page gets one — and still gets a button that says "Start the
         tables" and means it. A condition that outranked the control would have
         left them pressing a switch wired to nothing. */
      paused = !!(still && still.matches);
      strip.classList.add('is-live');
      control();
      if (!paused) start();
    })['catch'](function () { /* the six on the page are a complete section */ });
  }

  var watch = new window.IntersectionObserver(function (entries) {
    for (var n = 0; n < entries.length; n += 1) {
      if (entries[n].isIntersecting) {
        watch.disconnect();
        load();
        return;
      }
    }
  }, {rootMargin: '300px'});
  watch.observe(strip);

  /* A background tab should not burn a timer, and coming back should not
     dump six changes at once — the interval simply resumes. */
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stop();
    else if (!paused) start();
  });
  /* Asking for reduced motion mid-visit stops the strip and says so. Turning
     it back off does not start it again: that was never the reader pressing
     play, and a page that begins moving on its own is the thing they asked not
     to have. */
  if (still && still.addEventListener) {
    still.addEventListener('change', function () {
      if (!still.matches) return;
      paused = true;
      say();
      stop();
    });
  }
})();
