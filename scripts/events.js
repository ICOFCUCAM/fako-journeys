/* Product events, counted without following anybody around.
 * ---------------------------------------------------------------------------
 * There is no analytics vendor on this site, no cookie, no identifier and no
 * network call. This is the layer that would send events if somebody chose a
 * destination for them, plus the guarantees that survive that choice:
 *
 *   1. An event not named in tourism/events.json is dropped.
 *   2. A property not named under its own event is stripped.
 *   3. Every permitted value is an enum the dataset already contains — a lens
 *      key, a country slug, a month number — or a small integer. Free text has
 *      nowhere to go, which matters because the journey builder has a box a
 *      visitor types a sentence into and recording it would be the obvious
 *      mistake.
 *   4. Nothing joins two page-loads together. No id is minted, stored or read.
 *   5. Do Not Track and Global Privacy Control switch the whole thing off,
 *      including the counting.
 *
 * With no sink configured `track()` validates and returns. That is deliberate:
 * the events exist so that wiring a destination later is one line and a visible
 * decision, rather than something inherited from a tag manager nobody read.
 *
 * To wire one:
 *
 *     window.AfrinkongEvents.sink(function (name, props) { ... });
 *
 * The sink receives only what survived validation.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongEvents = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var SCHEMA = null;      /* {event: [allowed prop]} */
  var SINK = null;
  var COUNTS = {};        /* in memory, for this page-load, and nowhere else */

  function refused() {
    /* Two signals a visitor can set that mean "do not". Both are honoured for
       counting as well as for sending: a count that is kept is data that is
       held, whatever the intention was for it. */
    if (typeof navigator === 'undefined') return false;
    return navigator.doNotTrack === '1' || navigator.doNotTrack === 'yes'
      || navigator.msDoNotTrack === '1'
      || navigator.globalPrivacyControl === true
      || (typeof window !== 'undefined' && window.doNotTrack === '1');
  }

  function load() {
    if (SCHEMA) return SCHEMA;
    var el = typeof document !== 'undefined'
      && document.getElementById('af-events');
    if (!el) return null;
    try { SCHEMA = (JSON.parse(el.textContent) || {}).events || null; }
    catch (e) { SCHEMA = null; }
    return SCHEMA;
  }

  /* A value is allowed through only if it is a short token or a small number.
     This is the last line of defence rather than the first: the schema already
     names which properties may travel, and this makes sure that a property
     whose name is right but whose value is a sentence still does not. */
  function clean(value) {
    if (typeof value === 'number') {
      return isFinite(value) && Math.abs(value) < 1000 ? Math.round(value) : null;
    }
    if (typeof value !== 'string') return null;
    return /^[a-z0-9][a-z0-9 '-]{0,39}$/i.test(value) && value.indexOf('  ') < 0
      ? value : null;
  }

  /* -> what would be sent, or null if the event is refused. Returned rather
     than only sent so that the whole rule set is testable without a sink. */
  function shape(name, props) {
    var schema = load();
    if (!schema || !Object.prototype.hasOwnProperty.call(schema, name)) return null;
    var allowed = schema[name] || [];
    var out = {};
    Object.keys(props || {}).forEach(function (k) {
      if (allowed.indexOf(k) < 0) return;
      var v = clean(props[k]);
      if (v !== null && v !== '') out[k] = v;
    });
    return out;
  }

  function track(name, props) {
    if (refused()) return null;
    var payload = shape(name, props);
    if (!payload) return null;
    COUNTS[name] = (COUNTS[name] || 0) + 1;
    if (SINK) {
      try { SINK(name, payload); } catch (e) { /* a sink must never break a page */ }
    }
    return payload;
  }

  function sink(fn) { SINK = typeof fn === 'function' ? fn : null; }

  /* What this page-load has counted. In memory, gone on reload, and here so
     that "what does this actually record" can be answered by looking rather
     than by trusting. */
  function counted() {
    var out = {};
    Object.keys(COUNTS).forEach(function (k) { out[k] = COUNTS[k]; });
    return out;
  }

  return {track: track, shape: shape, sink: sink, counted: counted,
          refused: refused};
});
