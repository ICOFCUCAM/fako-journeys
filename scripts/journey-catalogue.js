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

  /* F8/F13: THE JOURNEY, BROKEN INTO WHAT IT IS ACTUALLY MADE OF.
   *
   * "Your Travel Points are worth $8,000" is the sentence Decision F exists to
   * prevent. "Your selected journey requires 8,000 Travel Points, and here is
   * which parts of it produced that figure" is the same arithmetic read as
   * travel, and it is what a customer can check.
   *
   * DETERMINISTIC, AND ONLY FROM WHAT THE RATE CARD KNOWS.
   *
   * F13 requires a versioned calculation that can be explained later, not an
   * approximation. So this decomposes the requirement into exactly the
   * components `rates.json` prices — ground services and arrival coordination
   * — and no others.
   *
   * It deliberately does NOT invent a seven-line split. The rate card prices a
   * tier per day, and that tier's `includes` list names what the day covers
   * (vehicle, driver, fuel, movement, coordination); it does not carry a
   * separate accommodation or safari figure, and manufacturing one would give
   * the customer a table that looks precise and is fiction. Where a real
   * component exists it is listed; where the rate card only knows a bundle,
   * the bundle is named along with what it contains.
   *
   * F3: destination charges are ELIGIBLE and not in this total, because the
   * site prices them per journey rather than per day. They are listed as
   * eligible-but-unpriced rather than silently omitted — a customer who
   * discovers a $700 permit at booking has been misled by an omission.
   */
  function breakdown(D, spec, programId) {
    var id = programId || DRAFT_PROGRAM;
    var priced = Fund.price(D, spec);
    if (!priced) return null;
    var p = Points.program(id);
    var components = [];

    if (priced.band) {
      /* A Trans Afrique route is quoted as a band, not built from a tier, so
         the only honest component is the route itself. */
      components.push({
        component: 'journey',
        label: priced.name || 'Trans Afrique route',
        service: 'journey',
        points: Points.goalRequirement(id, Math.round(priced.plan * 100)),
        basis: 'route band, planning figure at the lower bound'
      });
    } else {
      var tier = (D.tiers || []).filter(function (t) {
        return t.id === (spec.tier || D.default_tier);
      })[0];
      components.push({
        component: 'ground',
        label: (priced.tierName || 'Ground services') + ' — ' +
               priced.days + (priced.days === 1 ? ' day' : ' days'),
        service: 'transport',
        points: Points.goalRequirement(id, Math.round(priced.ground * 100)),
        basis: priced.rate + ' per day x ' + priced.days,
        /* What the bundle actually covers, in the rate card's own words, so
           the line is explicable rather than merely labelled. */
        includes: tier ? (tier.includes || []) : []
      });
      components.push({
        component: 'arrival',
        label: 'Arrival coordination',
        service: 'afrinkong_service',
        points: Points.goalRequirement(id, Math.round(priced.arrival * 100)),
        basis: 'once per journey'
      });
    }

    /* Every component must be inside programme scope, or the breakdown is
       quoting something the points cannot pay for. Checked rather than
       assumed, because the basket and the rate card are edited separately. */
    var outOfScope = components.filter(function (c) {
      return (p.eligibleServices || []).indexOf(c.service) === -1;
    });

    var total = components.reduce(function (n, c) { return n + c.points; }, 0);
    return {
      journeyId: journeyId(spec),
      programId: p.id,
      programVersion: p.version,
      rateCardVersion: D.v || 'unknown',
      components: components,
      /* The sum of the components IS the requirement. If these two ever
         disagree the table is decorative, which is worse than no table. */
      total: total,
      requirement: (requirementFor(D, spec, id) || {}).requirement,
      outOfScope: outOfScope.map(function (c) { return c.service; }),

      /* F3: ELIGIBLE, AND NOT IN THE FIGURE ABOVE — which a customer must be
         told, because discovering a $700 permit at booking is being misled by
         an omission just as surely as by a wrong number.

         Named charges come from the rate card when it carries them; the
         embedded card on the fund page does not, and `tourism/rates.json`
         does. So the programme's own charge-type scope is the floor, and the
         rate card's list enriches it when present. Neither source alone is
         reliable and the union is what the customer is actually owed. */
      eligibleNotYetPriced: (function () {
        var named = (D.destination_charges || []).map(function (c) {
          return { charge: c, source: 'rate card' };
        });
        if (named.length) return named.map(stamp);
        return (p.eligibleServices || []).filter(function (s) {
          return /_(fee|charge)$|^permit$/.test(s);
        }).map(function (s) {
          return stamp({ charge: s.replace(/_/g, ' '), source: 'programme scope' });
        });
        function stamp(x) {
          x.note = 'Eligible for Travel Points where Afrinkong arranges and ' +
                   'settles it. Priced per journey, so it is not in the ' +
                   'figure above.';
          return x;
        }
      }()),

      /* F12: what is NOT included, shown before booking rather than buried in
         terms. Read from the programme, which a check holds against the list
         the site already publishes. */
      notIncluded: (p.excludedServices || []).map(function (x) {
        return { service: x.service, why: x.why };
      }),

      /* F13/F14: how this figure was reached, and what it is not. */
      derivation: 'Journey -> eligible components -> programme pricing rules ' +
                  '-> point requirement. Recomputable from rate card ' +
                  (D.v || 'unknown') + ' and programme ' + p.id +
                  ' v' + p.version + '.',
      notDerivedFromCost: 'The requirement expresses travel entitlement under ' +
                          'this programme. It is not Afrinkong’s supplier ' +
                          'cost and implies no exchange rate between points ' +
                          'and money.'
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
    breakdown: breakdown,
    compare: compare,
    catalogue: catalogue
  };
});
