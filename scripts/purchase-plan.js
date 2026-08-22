/* How somebody acquires Travel Points over time. Section C, purchase model.
 *
 * @product: gated | @gate: programme-compliance | @surface: none
 * ===========================================================================
 * A PLAN IS AN INTENTION, NOT A MANDATE.
 *
 * This is the part most likely to be misread, so it is the first thing said:
 * nothing here charges anybody. A plan records what a customer says they mean
 * to buy and how often, and every actual purchase remains a separate,
 * separately authorised act. There is no payment mandate, no stored card, no
 * scheduled debit and no code that could become one without somebody adding a
 * payment provider that does not exist yet.
 *
 * That is a deliberate product decision rather than an unfinished feature.
 * Automatic recurring payment brings mandates, cancellation rights, failed
 * payments, refunds, and a different regulatory conversation; the customer can
 * buy every month by choosing to, and "Automatic Travel Point Purchase" can be
 * its own product later if it is ever wanted.
 *
 * WHAT STOPPING MEANS
 *
 * Stopping a plan stops FUTURE purchases. It does not touch a single point
 * already issued — those are entitlement the customer has already acquired,
 * recorded in a ledger nothing here can reach. A plan and a balance are
 * different things and this file cannot append to a ledger at all.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongPurchase = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /* A plan is in one of three states, and the transitions are the ones C3
     names: buy once, buy monthly, raise it, lower it, pause it, stop.
     PAUSED and STOPPED differ in intent rather than in effect — a pause says
     "not now", a stop says "no more" — and keeping them apart means a customer
     who paused is not told they cancelled. */
  var PLAN_STATES = ['ACTIVE', 'PAUSED', 'STOPPED'];
  var PLAN_NEXT = {
    ACTIVE:  ['PAUSED', 'STOPPED'],
    PAUSED:  ['ACTIVE', 'STOPPED'],
    STOPPED: []                     /* a stopped plan is finished; a customer
                                       who returns starts a new one, so the
                                       record of what they meant last time
                                       survives intact */
  };

  var CADENCES = ['ONCE', 'MONTHLY'];

  /* Build a plan, or refuse it with a reason. Bounds come from the programme
     — C13/C14 — because they are terms rather than constants, and a plan that
     could not be executed should not be offered. */
  function create(programId, points, cadence) {
    var c = (cadence || 'ONCE').toUpperCase();
    if (CADENCES.indexOf(c) === -1) {
      return { ok: false, why: 'cadence must be ONCE or MONTHLY' };
    }
    var allowed = Points.canPurchase(programId, points, 0);
    if (!allowed.ok) return { ok: false, why: allowed.why };
    return {
      ok: true,
      plan: {
        programId: programId,
        points: points,
        cadence: c,
        state: 'ACTIVE',
        /* Every change to the plan, in order. A customer who raised their
           intended purchase twice and then paused has a story, and support
           should be able to read it rather than infer it. */
        history: [{ to: 'ACTIVE', points: points, cadence: c }]
      }
    };
  }

  function transition(plan, to, note) {
    var t = (to || '').toUpperCase();
    if (PLAN_STATES.indexOf(t) === -1) {
      return { ok: false, why: 'unknown plan state: ' + to };
    }
    var allowed = PLAN_NEXT[plan.state] || [];
    if (allowed.indexOf(t) === -1) {
      return { ok: false, why: plan.state + ' cannot move to ' + t,
               from: plan.state, allowed: allowed };
    }
    var next = clone(plan);
    next.state = t;
    next.history = plan.history.concat([{ to: t, note: note || null }]);
    return { ok: true, plan: next };
  }

  /* Raising or lowering the intended amount. Re-checked against the programme,
     because a customer who doubles their intention may cross a ceiling. */
  function amend(plan, points) {
    if (plan.state === 'STOPPED') {
      return { ok: false, why: 'a stopped plan cannot be amended; start a new one' };
    }
    var allowed = Points.canPurchase(plan.programId, points, 0);
    if (!allowed.ok) return { ok: false, why: allowed.why };
    var next = clone(plan);
    next.points = points;
    next.history = plan.history.concat([{ to: plan.state, points: points }]);
    return { ok: true, plan: next };
  }

  /* C6: WHAT ACCUMULATING TOWARD A GOAL LOOKS LIKE, MONTH BY MONTH.
   *
   * A projection over a plan the customer has described. The last month is
   * short by construction — 4,800 at 1,000 a month is four full months and one
   * of 800, not five of 960 — because the customer buys what they need rather
   * than what divides evenly.
   *
   * Nothing here promises the requirement will still be `target` when they
   * arrive. `basis` carries the programme and rate card that produced it so
   * the projection can be compared against the journey later; C8 of the
   * pricing section is how that comparison is shown.
   */
  function accumulate(plan, target, held, maxMonths) {
    var rows = [];
    var have = held || 0;
    var cap = maxMonths || 240;
    if (plan.state !== 'ACTIVE' || plan.points <= 0) {
      return { rows: rows, reaches: have >= target, months: have >= target ? 0 : null,
               finalHeld: have };
    }
    var month = 0;
    while (have < target && month < cap) {
      month++;
      var buy = plan.points;
      if (plan.cadence === 'ONCE' && month > 1) break;
      /* Buy what is still needed rather than the full instalment, so the table
         ends on the target instead of overshooting it. */
      if (have + buy > target) buy = target - have;
      have += buy;
      rows.push({ month: month, purchased: buy, held: have });
    }
    return {
      rows: rows,
      reaches: have >= target,
      months: have >= target ? rows.length : null,
      finalHeld: have
    };
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  return {
    PLAN_STATES: PLAN_STATES,
    PLAN_NEXT: PLAN_NEXT,
    CADENCES: CADENCES,
    create: create,
    transition: transition,
    amend: amend,
    accumulate: accumulate
  };
});
