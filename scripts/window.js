/* The country window — one definition, for the browser.
 * ---------------------------------------------------------------------------
 * A country's outline with a photograph masked into it. The same path draws the
 * border and clips the picture, so the photograph arrives inside the exact
 * shape of the country it was taken in and nothing is re-projected.
 *
 * This existed four times: once in the gateway's build step and once each in
 * the atlas, the journey engine and the human layer, drifting apart a little
 * with every change. There are now two — this, and `window_svg` in
 * tools/tourism/plate.py for the pages that are built rather than drawn — and a
 * test asserts the two produce the same markup for the same shape.
 *
 * The atlas is deliberately not a caller: it clips in *map* coordinates, where
 * the country is one shape among fifty in a continent, which is a different
 * component that happens to use the same idea.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongWindow = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
    });
  }

  /* shape: {w, h, d} from tourism/shapes.json.
     opts:  {image, alt, name, ident, classes}
     Returns '' for a country with no outline, so a caller can concatenate it
     without checking — a missing silhouette is a smaller page, not a broken one. */
  function svg(shape, opts) {
    if (!shape || !shape.d) return '';
    opts = opts || {};
    var ident = opts.ident || 'afw';
    var label = (opts.image && opts.alt) ? opts.alt
      : 'The outline of ' + (opts.name || 'this country');
    var art = opts.image
      ? '<image clip-path="url(#' + esc(ident) + ')" href="' + esc(opts.image)
        + '" x="0" y="0" width="' + shape.w + '" height="' + shape.h
        + '" preserveAspectRatio="xMidYMid slice"/>'
      : '';
    return '<svg class="' + esc(opts.classes || 'af-window-svg') + '" viewBox="0 0 '
      + shape.w + ' ' + shape.h + '" role="img" aria-label="' + esc(label) + '">'
      /* The outline goes in once and is referenced twice — same as the build's
         copy in tools/tourism/plate.py, and the pair is checked against each
         other by the suite. A country outline is about 1.3 KB of coordinates
         and writing it out for the clip and again for the fill doubled that
         everywhere a window is drawn. */
      + '<defs><path id="' + esc(ident) + '-d" d="' + shape.d + '"/>'
      + '<clipPath id="' + esc(ident) + '"><use href="#' + esc(ident) + '-d"/></clipPath></defs>'
      + '<use class="af-window-fill" href="#' + esc(ident) + '-d"/>' + art + '</svg>';
  }

  /* shapes.json, fetched at most once per page however many callers ask. Twenty-
     nine kilobytes of outlines is not worth carrying to somebody who never opens
     a country, and it is not worth fetching twice for somebody who opens two. */
  var pending = null;
  var cache = null;
  function shapes() {
    if (cache) return Promise.resolve(cache);
    if (pending) return pending;
    pending = fetch('/tourism/shapes.json')
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) { cache = j; return cache; })
      .catch(function () { cache = {}; return cache; });
    return pending;
  }

  return {svg: svg, shapes: shapes};
});
