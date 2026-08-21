/* Fraud and risk. Item Y.
 * ===========================================================================
 * THE PRINCIPLE THIS FILE EXISTS FOR
 *
 *   Fraud controls must protect the LEDGER, not merely Stripe.
 *
 * A payment provider tells you whether a card worked. It cannot tell you
 * whether entitlement should be created, because it does not know what
 * entitlement is. So a settled payment is a necessary condition for issuance
 * and never a sufficient one, and the gap between those two words is where
 * every stolen-card loss lives:
 *
 *     Stripe payment  ->  appears successful  ->  RISK HOLD
 *                                             ->  no Travel Points issued
 *
 * The money can be refunded. Points that were issued, spent on a journey and
 * flown are not recoverable, which is why the hold belongs BEFORE issuance and
 * not after it.
 *
 * WHAT THIS IS NOT
 *
 * It is not a fraud model. It has no scores, no thresholds tuned against real
 * traffic, and no machine learning; those need data that does not exist yet.
 * It is the ARCHITECTURE — the decision points, the states, and the refusals —
 * so that when a real model arrives it has somewhere to plug in, and so that
 * nothing can be built in the meantime that bypasses the place it will go.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongRisk = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /* The four inputs Y names. Each is supplied by the caller — this module has
     no session, no device and no database, deliberately, so that it stays
     testable and so that a risk decision is always reconstructable from the
     signals that produced it. */
  var SIGNALS = ['authentication', 'paymentIdentity', 'deviceSession', 'history'];

  var DECISIONS = ['ALLOW', 'HOLD', 'REJECT'];

  /* ACTIONS THAT CAN LOSE SOMEBODY ELSE'S MONEY.
   *
   * Y's account-takeover case is the reason this is a list rather than a check
   * on issuance alone. An attacker inside somebody's account does not need to
   * buy anything: they need to move what is already there. Each of these is a
   * way value leaves a customer, so each needs its own decision rather than
   * inheriting one made at login.
   *
   * `stepUp` is what an attacker with a session cookie cannot satisfy. */
  var ACTIONS = {
    ISSUE:         { stepUp: false, why: 'creates entitlement from a payment' },
    TRANSFER:      { stepUp: true,  why: 'moves points to another person' },
    RESERVE:       { stepUp: true,  why: 'commits points to a journey' },
    BUYBACK:       { stepUp: true,  why: 'converts entitlement toward money' },
    PAYOUT_CHANGE: { stepUp: true,  why: 'changes where money would be sent' }
  };

  /* A hold is a state, not a flag: somebody has to end it, and the ending is
     recorded. HELD -> RELEASED means a human looked and allowed it. */
  var HOLD_STATES = ['HELD', 'RELEASED', 'REJECTED'];
  var HOLD_NEXT = { HELD: ['RELEASED', 'REJECTED'], RELEASED: [], REJECTED: [] };

  /* THE RISK ENGINE.
   *
   * Returns a decision and, crucially, the REASONS — a hold nobody can explain
   * is a hold nobody can review, and manual review is the whole point of the
   * HOLD branch existing.
   *
   * Unknown signals count against, not for. A caller that supplies nothing
   * gets HOLD rather than ALLOW, because the alternative is that forgetting to
   * wire up a signal silently opens the gate. That default is the single most
   * important line in this file.
   */
  function assess(action, signals, opts) {
    var spec = ACTIONS[String(action).toUpperCase()];
    if (!spec) {
      return { decision: 'REJECT', action: action,
               reasons: ['unknown action: ' + action] };
    }
    var s = signals || {};
    var o = opts || {};
    var reasons = [];
    var missing = SIGNALS.filter(function (k) { return s[k] == null; });

    /* Absent evidence is not favourable evidence. */
    if (missing.length) {
      reasons.push('signals not supplied: ' + missing.join(', '));
    }
    if (s.authentication === false) {
      reasons.push('the request is not authenticated');
    }
    /* Y's stolen-card case. The payment succeeding is what makes this
       dangerous rather than obvious: the money looks real. */
    if (s.paymentIdentity === false) {
      reasons.push('the payment instrument does not match the account holder');
    }
    if (s.deviceSession === false) {
      reasons.push('the device or session is unrecognised');
    }
    if (s.history === false) {
      reasons.push('the account history is inconsistent with this request');
    }
    /* Y's account-takeover case: a sensitive action needs more than a session,
       because a session is exactly what an attacker has. */
    if (spec.stepUp && o.stepUpSatisfied !== true) {
      reasons.push('this action requires step-up verification, which has not ' +
                   'been satisfied');
    }

    var decision = reasons.length === 0 ? 'ALLOW'
      : s.authentication === false ? 'REJECT'
      : 'HOLD';

    return {
      decision: decision,
      action: spec === ACTIONS.ISSUE ? 'ISSUE' : String(action).toUpperCase(),
      requiresStepUp: spec.stepUp,
      reasons: reasons,
      /* What a reviewer needs, assembled rather than reconstructed later. */
      review: decision === 'HOLD'
        ? { state: 'HELD', reasons: reasons }
        : null,
      note: decision === 'ALLOW'
        ? null
        : decision === 'REJECT'
          ? 'Refused. Nothing is created and nothing moves.'
          : 'Held for manual review. No Travel Points are issued and no points ' +
            'move while a hold stands.'
    };
  }

  function advanceHold(hold, to, opts) {
    var t = String(to || '').toUpperCase();
    if (HOLD_STATES.indexOf(t) === -1) {
      return { ok: false, why: 'unknown hold state: ' + to };
    }
    var allowed = HOLD_NEXT[hold.state] || [];
    if (allowed.indexOf(t) === -1) {
      return { ok: false, why: hold.state + ' cannot move to ' + t };
    }
    var o = opts || {};
    /* A release is a person deciding. Recording who is not bureaucracy: it is
       the difference between a reviewed release and a script that released
       everything at 3am. */
    if (t === 'RELEASED' && !o.reviewedBy) {
      return { ok: false, why: 'a release must name the reviewer' };
    }
    var next = JSON.parse(JSON.stringify(hold));
    next.state = t;
    next.reviewedBy = o.reviewedBy || null;
    next.reviewNote = o.note || null;
    return { ok: true, hold: next, mayProceed: t === 'RELEASED' };
  }

  /* Y: THE LEDGER GATE. A settled payment is necessary and never sufficient.
   *
   * Returns the entries an issuance implies ONLY when risk allows it. This
   * wraps `Points.issuance()` rather than living inside it so that the risk
   * decision is visible at the call site — an issuance path that forgot to
   * consult risk should look wrong when you read it, not merely behave wrong.
   */
  function issuanceUnderRisk(programId, points, payment, signals, refs) {
    var verdict = assess('ISSUE', signals, refs || {});
    if (verdict.decision !== 'ALLOW') {
      return {
        ok: false,
        why: 'risk ' + verdict.decision.toLowerCase() +
             ': no Travel Points are issued',
        risk: verdict,
        /* Stated because it is the whole architecture in one line: the money
           may well have settled. That is not the question being answered. */
        paymentMayHaveSettled: true,
        entries: []
      };
    }
    var built = Points.issuance(programId, points, payment, refs);
    if (!built.ok) return built;
    built.risk = verdict;
    return built;
  }

  /* Y: CHARGEBACK AFTER REDEMPTION.
   *
   * The case that makes this an economic problem rather than a security one.
   * The customer flew. The ledger does not erase the redemption — history is
   * append-only and the journey happened — so what is created is a LIABILITY:
   * a record that WANKONG LLC is owed for travel Afrinkong delivered against a
   * payment that was reversed. The entity distinction is load-bearing: the
   * brand provided the journey, the legal entity carries the debt.
   *
   * Deliberately not a points adjustment. The points are gone, correctly, and
   * inventing a negative balance would misstate what the customer holds. The
   * debt is money, it belongs in the payments system, and this returns the
   * record rather than resolving it — B-recovery is still open.
   */
  function chargebackAfterRedemption(programId, entries, originalEntryId, ctx) {
    /* Z: a chargeback reversal is an administrative entry, so it names a
       human like every other one. A reversal nobody signed is exactly what
       that rule guards against. */
    var reversal = Points.reversal(programId, entries, originalEntryId,
                                   'chargeback after redemption',
                                   { approvedBy: (ctx || {}).approvedBy });
    if (!reversal.ok) return reversal;
    var o = ctx || {};
    var consumed = reversal.shortfall;
    return {
      ok: true,
      recoverablePoints: reversal.recoverable,
      /* Only the part still in the wallet can be taken back as points. */
      entries: reversal.recoverable > 0
        ? [Object.assign({}, reversal.entries[0],
                         { quantity: reversal.recoverable })]
        : [],
      liability: consumed > 0
        ? { points: consumed,
            kind: 'TRAVEL_DELIVERED_AGAINST_REVERSED_PAYMENT',
            paymentRef: o.paymentRef || null,
            /* No figure. What this is worth in money depends on the payment
               that was reversed, which lives in `payments` — and Decision I
               forbids attaching a money figure to a quantity of points. */
            amountMinor: null,
            note: consumed + ' TP were already consumed for travel that was ' +
                  'delivered. The redemption is not reversed; this records a ' +
                  'debt for recovery through the payment system.' }
        : null,
      unresolved: consumed > 0
        ? 'How this debt is pursued has not been decided — B-recovery.'
        : null
    };
  }

  return {
    SIGNALS: SIGNALS,
    DECISIONS: DECISIONS,
    ACTIONS: ACTIONS,
    HOLD_STATES: HOLD_STATES,
    assess: assess,
    advanceHold: advanceHold,
    issuanceUnderRisk: issuanceUnderRisk,
    chargebackAfterRedemption: chargebackAfterRedemption
  };
});
