/* What a journey requires, in Travel Points. Section C phase C3.
 * ===========================================================================
 * C7: "Each journey should have a Travel Point requirement, calculated from the
 * applicable itinerary/service pricing." And: "the journey consumes
 * entitlement, not dollars."
 *
 * So this does not invent a second price list. It reads the one the site
 * already publishes — `tourism/rates.json`, through `fund-math.price()` — and
 * expresses the same journey in the unit the programme issues. One rate card,
 * two denominations, and they cannot drift because the second is derived from
 * the first every time.
 *
 * WHY THE VERSION STAMP IS NOT DECORATION
 *
 * C8 asks what happens when supplier costs rise and a journey that required
 * 4,800 TP now requires 5,050. The answer is that the customer is shown both
 * numbers and the difference, and nobody's existing points are revalued — B18,
 * and the CFPB's concern about devaluing rewards somebody has already bought.
 *
 * That is only possible if a requirement remembers which rate card produced it.
 * Every requirement here carries the rate card's version hash, so a goal set in
 * March can be compared against the same journey in September and the change
 * attributed rather than merely observed.
 *
 * Pure. No DOM, no network, no clock.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./fund-math.js') : root.AfrinkongFund,
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongJourneys = api;
})(typeof self !== 'undefined' ? self : this, function (Fund, Points) {
  'use strict';

  var DRAFT_PROGRAM = 'AFK-TP-2026.1';

  /* A journey is identified by what was chosen, not by a display name: a
     caption is page copy and would change the identity of the same journey the
     moment somebody rewrote it. The same mistake the image library made with
     object keys, and the same fix. */
  function journeyId(spec) {
    if (spec.kind === 'crossing') return 'crossing:' + spec.place;
    return ['country', spec.place, spec.tier, spec.days].join(':');
  }

  /* THE REQUIREMENT, AND WHAT IT WAS DERIVED FROM.
   *
   * Returns null rather than a guess when the rate card does not know the
   * place. A requirement nobody can trace to a price is worse than none. */
  function requirementFor(D, spec, programId) {
    var id = programId || DRAFT_PROGRAM;
    var priced = Fund.price(D, spec);
    if (!priced) return null;
    var minor = Math.round(priced.plan * 100);
    return {
      journeyId: journeyId(spec),
      programId: id,
      /* The requirement, in points. goalRequirement divides by `entitlement`,
         so a purchase bonus cannot inflate it — B5's rule, A5.1's fix. */
      requirement: Points.goalRequirement(id, minor),
      priceMinor: minor,
      currency: (Points.program(id).currency || 'USD'),
      /* Which rate card said so. Without this, C8 can only report that a
         number changed, not what changed it. */
      rateCardVersion: D.v || 'unknown',
      band: !!priced.band,
      days: priced.days || null
    };
  }

  /* C8: THE CUSTOMER SEES BOTH NUMBERS AND THE DIFFERENCE.
   *
   *     original journey target     4,800 TP
   *     current journey requirement 5,050 TP
   *     difference                    250 TP
   *
   * No hidden devaluation: the customer's 4,800 points are still 4,800 points
   * under the terms they were bought on. What changed is the journey, and they
   * are told so and can acquire the difference.
   *
   * `same` is deliberately about the rate card rather than the number. Two rate
   * cards can agree on one journey and disagree on another, and a comparison
   * that only looked at the figure would report "no change" while sitting on a
   * different price list. */
  function compare(original, current) {
    if (!original || !current) return null;
    var diff = current.requirement - original.requirement;
    return {
      journeyId: current.journeyId,
      original: original.requirement,
      current: current.requirement,
      difference: diff,
      direction: diff === 0 ? 'unchanged' : diff > 0 ? 'increased' : 'decreased',
      sameRateCard: original.rateCardVersion === current.rateCardVersion,
      originalRateCard: original.rateCardVersion,
      currentRateCard: current.rateCardVersion,
      /* B18: what did NOT change. Stated explicitly because it is the whole
         reassurance, and because a difference shown without it reads as a
         devaluation. */
      pointsHeldUnaffected: true
    };
  }

  /* The published catalogue: every country at the programme's default shape,
     plus the four Trans Afrique routes. C7's table, generated rather than
     typed, so it cannot disagree with the rate card. */
  function catalogue(D, programId) {
    var out = [];
    var d = D['default'] || { days: 7, tier: 'signature' };
    (D.countries || []).forEach(function (c) {
      var r = requirementFor(D, { kind: 'country', place: c.s,
                                  tier: d.tier, days: d.days }, programId);
      if (r) { r.name = c.n; r.region = c.r; out.push(r); }
    });
    (D.routes || []).forEach(function (t) {
      var r = requirementFor(D, { kind: 'crossing', place: t.s }, programId);
      if (r) { r.name = t.n; r.region = t.r; out.push(r); }
    });
    return out;
  }

  return {
    DRAFT_PROGRAM: DRAFT_PROGRAM,
    journeyId: journeyId,
    requirementFor: requirementFor,
    compare: compare,
    catalogue: catalogue
  };
});
