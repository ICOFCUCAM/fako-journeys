/* The crossings plate — choosing which road is lit.
 *
 * @product: live | @gate: none | @surface: /trans-afrique/*
 * ---------------------------------------------------------------------------
 * PROGRESSIVE, NOT REQUIRED. Everything this file touches is already on the
 * page and already legible: the plate draws all four roads, every country name
 * is in the SVG, and all four summaries are open. What the script adds is the
 * ability to choose one — it marks the figure `is-live`, which is the only
 * thing that turns the summaries into an accordion. Without it the reader gets
 * the whole map and all four journeys laid out instead of selected, which is a
 * different experience and not a broken one.
 *
 * THE STATE LIVES IN ONE ATTRIBUTE. `data-lit` on the figure is either absent
 * (all four roads at full strength) or a route id. Every visual consequence —
 * roads dimming, nodes growing, country names appearing, the panel entry
 * opening — is a CSS rule keyed off that attribute. No element is styled from
 * here, so the whole look can be rewritten in the stylesheet without touching
 * this file, and there is no way for the map and the panel to disagree about
 * what is selected.
 *
 * HOVER PREVIEWS, CLICK COMMITS. Pointing at an entry lights its road while
 * the pointer is there and lets go when it leaves; clicking holds it. A hover
 * that stuck would leave the reader with a selection they did not make, and on
 * a touch screen there is no hover at all — which is why the click path is the
 * real one and the hover is decoration over it.
 */
(function () {
  'use strict';

  var figures = document.querySelectorAll('[data-crossings]');
  if (!figures.length) return;

  Array.prototype.forEach.call(figures, function (fig) {
    var picks = fig.querySelectorAll('.tf-pick-hit');
    if (!picks.length) return;

    /* Announced only once the accordion exists. Before this the summaries are
       open and the buttons control nothing, so aria-expanded="true" in the
       markup is the truth; from here they are collapsed until chosen. */
    fig.classList.add('is-live');

    var held = null;      /* what the reader chose */
    var over = null;      /* what the reader is pointing at */

    function paint() {
      var lit = over || held;
      if (lit) fig.setAttribute('data-lit', lit);
      else fig.removeAttribute('data-lit');
      Array.prototype.forEach.call(picks, function (b) {
        var mine = b.getAttribute('data-route');
        b.setAttribute('aria-expanded', mine === held ? 'true' : 'false');
        /* aria-current says which one is chosen, which is not the same claim
           as which one is momentarily under the pointer. */
        if (mine === held) b.setAttribute('aria-current', 'true');
        else b.removeAttribute('aria-current');
      });
    }

    Array.prototype.forEach.call(picks, function (b) {
      var id = b.getAttribute('data-route');
      b.addEventListener('click', function () {
        held = (held === id) ? null : id;   /* a second press puts it back */
        over = null;
        paint();
        if (held && window.AfrinkongEvents) {
          try { window.AfrinkongEvents.track('crossing_opened', {crossing: held}); }
          catch (e) { /* counting must never break the page */ }
        }
      });
      b.addEventListener('mouseenter', function () { over = id; paint(); });
      b.addEventListener('mouseleave', function () { over = null; paint(); });
      /* Keyboard focus is a pointer for anyone not using one. */
      b.addEventListener('focus', function () { over = id; paint(); });
      b.addEventListener('blur', function () { over = null; paint(); });
    });

    paint();
  });
})();
