/* The Travel Goal: a journey estimate, restated as travel purchasing power.
 * ===========================================================================
 * Pure arithmetic. No DOM, no storage, no network, no dependencies — the same
 * shape as scripts/fund-math.js, and for the same reason.
 *
 * WHAT THIS IS, AND MUCH MORE IMPORTANTLY WHAT IT IS NOT
 *
 * It is a PLANNING CALCULATION. It takes the journey estimate the Journey Fund
 * already computes and expresses it in Travel Points, so somebody can see the
 * shape of the commitment before any product exists to sell them.
 *
 * It is not a purchase, an account, a balance, an entitlement, or a statement
 * that the reader owns anything. Nobody has bought a Travel Point, because
 * Travel Points cannot be bought: the point program is a draft and
 * `points-ledger.js` refuses to issue under a draft program.
 *
 * THIS FILE DELIBERATELY CANNOT ISSUE ANYTHING
 *
 * It does not import the ledger's issuing side and it has no access to one. It
 * computes a target and a rhythm and returns numbers. If a future change makes
 * this file able to create a point, that change is a mistake, and
 * tools/goal-checks.js is written to fail if the vocabulary of ownership ever
 * appears in what it returns.
 *
 * THE VOCABULARY MATTERS, SO IT IS FIXED HERE
 *
 *   "target"       how many points the journey would need
 *   "recorded"     what the reader has told THIS BROWSER they have set aside.
 *                  Their own note to themselves. Afrinkong holds nothing and
 *                  knows nothing about it.
 *   "remaining"    target minus recorded
 *   "monthly"      remaining divided by whole months. Division, nothing else.
 *
 * Never "balance", never "your points", never "owned", never "available" —
 * those words belong to a wallet, and there is no wallet.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js')
                                  : root.AfrinkongPoints);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongGoal = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /* The program a goal is quoted against. Draft, and stated as draft on every
     result, so no caller can render a figure without also being handed the
     fact that the terms are not final. */
  var DRAFT_PROGRAM = 'AFK-TP-2026.1';

  function money(n) {
    return '$' + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function points(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',') + ' TP';
  }

  /* ---- the calculation ----------------------------------------------------
   *
   * `journeyTotal`  whole dollars, as fund-math.js already computes it
   * `months`        whole months to the chosen month, as fund-math.js counts
   * `recorded`      the reader's own note, in points, or 0
   * `rateVersion`   the rate card hash the page was built with, so the figure
   *                 can be traced to the prices that produced it
   */
  function build(journeyTotal, months, recorded, rateVersion, programId) {
    var id = programId || DRAFT_PROGRAM;
    var program = Points.program(id);
    var state = Points.stateOf(id);
    var g = Points.goal(id, Math.round(journeyTotal * 100), recorded || 0, months);

    return {
      /* THE STATE COMES FIRST IN THE OBJECT ON PURPOSE. A caller destructuring
         this cannot easily take the numbers without meeting the state. */
      productState: state,
      issued: false,
      sellable: Points.mayIssue(id),

      target: g.target,
      recorded: g.held,
      remaining: g.remaining,
      progress: g.progress,
      monthly: g.monthly,
      months: g.months,

      journeyTotal: journeyTotal,
      currency: program.currency,

      /* WHICH PRICES AND WHICH TERMS PRODUCED THIS.
         A reader who returns in eight months to a different number deserves to
         be able to see that the rate card moved, rather than being told the
         estimate changed. */
      rateCardVersion: rateVersion || 'unknown',
      programId: program.id,
      programVersion: program.version,
      programStatus: program.status,

      /* Formatted here rather than in the page, so every surface says the same
         thing in the same words. */
      display: {
        target: points(g.target),
        recorded: points(g.held),
        remaining: points(g.remaining),
        monthly: g.monthly === null ? null : points(g.monthly) + ' a month',
        progress: (g.progress * 100).toFixed(g.progress >= 0.995 ? 0 : 1) + '%',
        journeyTotal: money(journeyTotal),
        time: g.months > 0
          ? g.months + (g.months === 1 ? ' month' : ' months')
          : 'no whole months left'
      },

      /* The sentence a reader must not be able to miss. Returned as data so
         the page cannot render the numbers while forgetting the caveat, and so
         it is testable. */
      disclosure: 'A planning estimate. Travel Points are not on sale, nothing '
                + 'has been purchased, and this is not an account or a balance. '
                + 'The figure shown is today’s journey estimate expressed '
                + 'in the units of a draft programme whose terms are not final.'
    };
  }

  /* What a reader has told this browser they have set aside. Their note, kept
     on their device — Afrinkong holds nothing and is told nothing. Clamped so
     a typo cannot produce a nonsense goal. */
  function readRecorded(raw) {
    var n = parseInt(raw, 10);
    if (!isFinite(n) || n < 0) return 0;
    return Math.min(n, 1000000);
  }

  return {
    DRAFT_PROGRAM: DRAFT_PROGRAM,
    build: build,
    readRecorded: readRecorded,
    points: points,
    money: money
  };
});
