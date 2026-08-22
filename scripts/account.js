/* The authenticated Travel Wallet. Item Z.
 *
 * @product: gated | @gate: accounts-not-built | @surface: none
 * ===========================================================================
 * THE BOUNDARY THIS FILE EXISTS TO DRAW
 *
 *   Planning does not require an account. Ownership of Travel Points does.
 *
 * A visitor can explore, price a journey in points, set a goal and keep it in
 * their own browser, and Afrinkong has no financial relationship with them at
 * all. Nothing here is needed for any of that — and `requiresAccount()` below
 * says so as a list rather than as a convention, because the failure mode is
 * somebody putting a sign-in wall in front of the planner.
 *
 * THREE LAYERS, THREE QUESTIONS
 *
 *   ACCOUNT  who is this person?
 *   WALLET   what entitlements do they currently hold?
 *   LEDGER   why does the wallet contain those entitlements?
 *
 * The arrow only points one way. The wallet is DERIVED from the ledger and is
 * never a source of truth, so nothing here holds a balance, and the one
 * function that assembles a wallet takes ledger entries as its input rather
 * than storing anything.
 *
 * NOT BUILT, DELIBERATELY: no issuance, no Stripe, no database, no production
 * wallet, no live transfer or buyback. This is the architecture, the states
 * and the refusals. Every economic operation still terminates in the readiness
 * gates, which report four unmet conditions.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongAccount = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /* An account is a person, and a person can be in the system without holding
     anything. VERIFIED is about contact and identity, not about money. */
  var ACCOUNT_STATES = ['UNVERIFIED', 'VERIFIED', 'RESTRICTED', 'CLOSED'];

  var AUTH = { NONE: 'NONE', NORMAL: 'NORMAL', STEP_UP: 'STEP_UP' };

  /* Z's table, as data. The reason it is data and not prose: a screen that
     needs to know whether an action requires step-up must be able to ASK, and
     a convention in a document is a convention somebody has not read. */
  var ACTIONS = {
    VIEW_POINTS:        { auth: AUTH.NORMAL,  account: true },
    VIEW_LEDGER:        { auth: AUTH.NORMAL,  account: true },
    CREATE_GOAL:        { auth: AUTH.NONE,    account: false,
                          why: 'planning is not ownership' },
    EXPLORE:            { auth: AUTH.NONE,    account: false,
                          why: 'planning is not ownership' },
    PRICE_JOURNEY:      { auth: AUTH.NONE,    account: false,
                          why: 'planning is not ownership' },
    BUY_POINTS:         { auth: AUTH.NORMAL,  account: true,  risk: true },
    RESERVE_JOURNEY:    { auth: AUTH.NORMAL,  account: true,  entitlement: true },
    TRANSFER_POINTS:    { auth: AUTH.STEP_UP, account: true,  risk: true },
    REQUEST_BUYBACK:    { auth: AUTH.STEP_UP, account: true,  risk: true },
    CHANGE_IDENTITY:    { auth: AUTH.STEP_UP, account: true },
    CHANGE_PAYOUT:      { auth: AUTH.STEP_UP, account: true,  risk: true }
  };

  /* THE LIST THAT KEEPS THE PLANNER OPEN.
     Everything a visitor may do without ever meeting a sign-in form. If this
     list shrinks, somebody has put a wall in front of the product's front
     door — so it is asserted rather than assumed. */
  function requiresAccount(action) {
    var spec = ACTIONS[String(action).toUpperCase()];
    if (!spec) return { known: false, requiresAccount: true,
                        why: 'unknown action, and the safe answer is yes' };
    return {
      known: true,
      requiresAccount: spec.account,
      auth: spec.auth,
      why: spec.why || null
    };
  }

  /* Z + Y: MAY THIS SESSION DO THIS?
   *
   * A stolen session is not authority to move economic entitlement, which is
   * why `auth` and `stepUp` are separate inputs rather than one boolean. The
   * risk verdict is passed in rather than computed, because `risk.js` owns
   * that decision and two modules answering the same question is how they
   * start disagreeing.
   */
  function mayPerform(action, session, riskVerdict) {
    var key = String(action).toUpperCase();
    var spec = ACTIONS[key];
    if (!spec) return { ok: false, why: 'unknown action: ' + action };
    var s = session || {};

    if (!spec.account) return { ok: true, action: key, anonymous: true };

    if (!s.accountId) {
      return { ok: false, action: key, why: 'this action requires an account' };
    }
    if (s.state === 'CLOSED') {
      return { ok: false, action: key, why: 'this account is closed' };
    }
    /* A restricted account may still LOOK. Freezing somebody out of seeing
       what they hold, during a recovery or a dispute, is its own harm. */
    if (s.state === 'RESTRICTED' && key.indexOf('VIEW_') !== 0) {
      return { ok: false, action: key,
               why: 'this account is restricted; viewing remains available' };
    }
    if (!s.authenticated) {
      return { ok: false, action: key, why: 'not authenticated' };
    }
    if (spec.auth === AUTH.STEP_UP && s.stepUp !== true) {
      return { ok: false, action: key, why: 'this action requires step-up ' +
               'verification; a session alone is not authority to move ' +
               'economic entitlement' };
    }
    if (spec.risk && riskVerdict && riskVerdict.decision !== 'ALLOW') {
      return { ok: false, action: key,
               why: 'risk ' + String(riskVerdict.decision).toLowerCase(),
               risk: riskVerdict };
    }
    if (spec.risk && !riskVerdict) {
      /* Same rule as risk.js: absent evidence is not favourable evidence. */
      return { ok: false, action: key,
               why: 'this action requires a risk decision and none was supplied' };
    }
    return { ok: true, action: key };
  }

  /* Z: THE WALLET, WHICH IS A VIEW AND HOLDS NOTHING.
   *
   * Assembled from ledger entries every time. There is no stored figure here
   * to drift, and `restricted` deliberately comes from the ACCOUNT rather than
   * from the ledger — a restriction is a fact about a person under recovery or
   * dispute, not a movement of points, and inventing a ledger kind for it
   * would have broken B7's closed set for something that is not an economic
   * event at all.
   */
  function wallet(entries, account) {
    var w = Points.wallet(entries || []);
    var a = account || {};
    var restricted = a.state === 'RESTRICTED' ? w.available : 0;
    return {
      /* Z's five figures, in Z's words. */
      available: w.available - restricted,
      reserved: w.reserved,
      totalHeld: w.available + w.reserved,
      pending: w.pending,
      restricted: restricted,
      /* Kept because a customer is proud of it, and it is the one number that
         only ever goes up. */
      acquired: w.acquired,
      /* Decision I, restated at the surface most likely to break it. */
      cashEquivalent: null,
      display: Points.holdingDisplay(w.available - restricted, a.target || 0),
      note: restricted > 0
        ? 'Some points are temporarily restricted while your account is under ' +
          'review. They remain yours and nothing has been removed.'
        : null
    };
  }

  /* Z: ACCOUNT RECOVERY IS AN ECONOMIC-CONTROL PROBLEM.
   *
   * "We'll reset the account" is a sentence that can move thousands of points
   * to whoever asked most convincingly. So the requirement scales with what is
   * at stake — not with what the customer says, and not with how sympathetic
   * the request sounds.
   *
   * `heldPoints` and `authority` come from the caller because this module has
   * no ledger and no session; the tiers are stated here so the same answer is
   * given every time rather than being argued case by case at the moment
   * somebody is upset.
   */
  var RECOVERY_TIERS = [
    { tier: 'LOW', maxPoints: 1000, requires: ['contact verification'],
      why: 'little is at stake and the friction would cost more than the risk' },
    { tier: 'STANDARD', maxPoints: 10000,
      requires: ['contact verification', 'identity verification'],
      why: 'a meaningful holding' },
    { tier: 'HIGH', maxPoints: null,
      requires: ['contact verification', 'identity verification',
                 'manual review', 'cooling-off period'],
      why: 'a holding large enough that a successful social-engineering ' +
           'attempt would be worth somebody’s time' }
  ];

  function recoveryRequirements(heldPoints, opts) {
    var o = opts || {};
    var held = heldPoints || 0;
    var tier = RECOVERY_TIERS.filter(function (t) {
      return t.maxPoints === null || held <= t.maxPoints;
    })[0];
    var requires = tier.requires.slice();
    /* Recovering the ACCOUNT is not the same as recovering the authority to
       move what is in it. Somebody who has just proved their identity to a
       support agent should not immediately be able to transfer or sell. */
    if (o.restoringAuthority) {
      requires.push('step-up verification');
      requires.push('restriction period before transfer or buyback');
    }
    return {
      heldPoints: held,
      tier: tier.tier,
      requires: requires,
      why: tier.why,
      /* Said plainly because it is the sentence that stops a well-meaning
         agent from being helpful in the wrong direction. */
      note: 'Recovery restores access to an account. It does not by itself ' +
            'restore authority to move Travel Points out of it.'
    };
  }

  /* Z: THERE IS NO ADMIN EDIT BALANCE, so this is what an administrator gets
   * instead — a proposed ENTRY, which the ledger will refuse unless it names a
   * human and a reason. `points-ledger.js` enforces that in the fold; this is
   * the shape a caller should build.
   *
   * Appends nothing, like every other module here. */
  function adjustment(programId, points, opts) {
    var o = opts || {};
    if (!o.approvedBy) {
      return { ok: false, why: 'an adjustment must name the person who ' +
                              'approved it' };
    }
    if (!o.reason) {
      return { ok: false, why: 'an adjustment must give a reason' };
    }
    if (!isFinite(points) || points === 0 || Math.floor(points) !== points) {
      return { ok: false, why: 'an adjustment must be a non-zero whole number' };
    }
    return {
      ok: true,
      entries: [{
        kind: points > 0 ? 'ADJUST_UP' : 'ADJUST_DOWN',
        quantity: Math.abs(points),
        status: 'SETTLED',
        programVersion: programId,
        approvedBy: o.approvedBy,
        reason: o.reason,
        reference: o.reference || null,
        id: o.entryId || null,
        idempotencyKey: o.idempotencyKey || null
      }],
      note: 'This is an entry, not an edit. Nothing earlier changes.'
    };
  }

  return {
    ACCOUNT_STATES: ACCOUNT_STATES,
    AUTH: AUTH,
    ACTIONS: ACTIONS,
    RECOVERY_TIERS: RECOVERY_TIERS,
    requiresAccount: requiresAccount,
    mayPerform: mayPerform,
    wallet: wallet,
    recoveryRequirements: recoveryRequirements,
    adjustment: adjustment
  };
});
