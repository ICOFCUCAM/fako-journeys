/* The Journey Fund's arithmetic, with no interface attached to it.
 * ===========================================================================
 * Split out of scripts/fund.js for the same reason the journey engine is split
 * out of the journey builder: this is the part that has to be right, and a
 * function that needs a DOM to run is a function that needs a browser to test.
 * Everything here is pure — same inputs, same answer, no clock of its own, no
 * storage, no network.
 *
 * WHAT IT IS DOING
 *
 * Division. That is the honest summary and it is worth stating plainly,
 * because products in this shape usually imply more: there is no interest
 * here, no growth, no projection, no return, no compounding, and no
 * assumption about anything. The cost of a journey, divided by the number of
 * whole months between now and the month somebody chose.
 *
 * THREE DECISIONS WORTH RECORDING
 *
 *   1. WHOLE MONTHS. A traveller who picks next month has zero months to put
 *      anything aside in, not one. Rounding that up produces a figure nobody
 *      can act on, and the page would rather say the month is too close.
 *
 *   2. CROSSINGS ARE PLANNED AGAINST THE BOTTOM OF THEIR BAND. A crossing is
 *      priced whole rather than by the day, and where in its band a particular
 *      route lands depends on its shape. Showing one number would be a figure
 *      we cannot stand behind, so both ends are shown and the arithmetic uses
 *      the low end. Planning against the top would overstate what most
 *      travellers need; the page says which end it used, so nobody is
 *      surprised later.
 *
 *   3. DESTINATION CHARGES ARE NOT IN ANY OF THIS. Park fees, conservation
 *      fees, permits and entrance charges are settled at cost and depend on
 *      the itinerary — a gorilla permit alone can exceed a day of the journey.
 *      They are excluded here and disclosed on the page, rather than being
 *      folded in as a guess that would look like a quotation.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongFund = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* Whole dollars with thousands separators. No cents anywhere in this
     product: a figure to the penny two years out is precision the arithmetic
     does not have and implies a promise it cannot make. */
  function money(n) {
    return '$' + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function tierOf(D, id) {
    for (var i = 0; i < D.tiers.length; i++) {
      if (D.tiers[i].id === id) return D.tiers[i];
    }
    return D.tiers[0];
  }

  function routeOf(D, id) {
    for (var i = 0; i < (D.routes || []).length; i++) {
      if (D.routes[i].s === id) return D.routes[i];
    }
    return null;
  }

  function countryOf(D, slug) {
    for (var i = 0; i < D.countries.length; i++) {
      if (D.countries[i].s === slug) return D.countries[i];
    }
    return null;
  }

  /* -> what the journey costs, or null if the choice does not name one.
     `plan` is the figure the rhythm is worked out against, and it is a
     separate field from `total` on purpose: for a country they are the same
     number, for a crossing they are not, and code downstream should never
     have to know which case it is in. */
  function price(D, s) {
    if (s.kind === 'crossing') {
      var r = routeOf(D, s.place);
      if (!r) return null;
      return {
        band: true, low: r.lo, high: r.hi, days: r.d,
        countries: r.c, name: r.n, plan: r.lo
      };
    }
    var t = tierOf(D, s.tier);
    var days = s.days;
    var ground = t.rate * days;
    return {
      band: false, ground: ground, arrival: D.arrival,
      total: ground + D.arrival, rate: t.rate, tierName: t.name,
      days: days, plan: ground + D.arrival
    };
  }

  /* Whole months from `now` to a "YYYY-M" value. `now` is passed in rather
     than read, so a test can ask what happens in December without waiting. */
  function monthsAhead(value, now) {
    if (!value) return null;
    var parts = String(value).split('-');
    var y = parseInt(parts[0], 10), m = parseInt(parts[1], 10);
    if (isNaN(y) || isNaN(m) || m < 1 || m > 12) return null;
    return (y - now.getFullYear()) * 12 + (m - 1 - now.getMonth());
  }

  /* -> {per, n, every} or {problem} — never an error and never a refusal.
     A month too close is a fact about the month, not a mistake by the reader,
     and the sentence the page prints says so. */
  function rhythm(plan, months, kind) {
    if (months === null || months === undefined) return { problem: 'nomonth' };
    if (months <= 0) return { problem: 'toosoon' };
    if (kind === 'quarterly') {
      var n = Math.floor(months / 3);
      if (n < 1) return { problem: 'toosoonquarterly' };
      return {
        per: plan / n, n: n,
        every: n === 1 ? 'one payment'
                       : n + ' payments, one every three months'
      };
    }
    return { per: plan / months, n: months, every: months + ' months' };
  }

  /* The ways out, when the figure is larger than most people would sustain.
     Never "that is too much" — always "here is what would reach it", because
     the question is about the journey and not about the reader. Returns an
     empty list when there is nothing honest left to offer, and the page then
     says nothing rather than inventing an option. */
  function doors(D, p, months, s, ceiling) {
    var out = [];
    if (months < 24) {
      out.push('a later month — twenty-four gives you '
               + money(p.plan / 24) + ' a month');
    }
    if (!p.band && s.days > D.days[0]) out.push('fewer days on the ground');
    if (!p.band && s.tier !== D.tiers[0].id) {
      out.push('the ' + D.tiers[0].name + ' journey');
    }
    return out;
  }

  /* The figure above which the page offers the doors. Not a judgement about
     anybody's means — it is the point past which the arithmetic is usually
     telling you something about the journey rather than about you. */
  var CEILING = 1200;

  /* A journey cannot be confirmed without a visa, permits and a booked flight
     behind it, and the rate card says so in as many words. Three months is the
     floor the month strip starts at for that reason, not for a commercial one. */
  var SOONEST_MONTHS = 3;
  var STRIP_MONTHS = 24;

  return {
    money: money, price: price, monthsAhead: monthsAhead, rhythm: rhythm,
    doors: doors, tierOf: tierOf, routeOf: routeOf, countryOf: countryOf,
    CEILING: CEILING, SOONEST_MONTHS: SOONEST_MONTHS, STRIP_MONTHS: STRIP_MONTHS
  };
});
