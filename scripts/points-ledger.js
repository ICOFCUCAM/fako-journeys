/* The Travel Point ledger, with no interface and no database attached to it.
 * ===========================================================================
 * Split out for the same reason scripts/fund-math.js is split out of the fund
 * page: this is the part that has to be right, and a function that needs a
 * DOM or a network to run is a function that needs a browser or a server to
 * test. Everything here is pure — same inputs, same answer, no clock of its
 * own, no storage, no network, no dependencies.
 *
 * WHAT A TRAVEL POINT IS, IN ONE SENTENCE
 *
 * An Afrinkong-issued unit of travel purchasing entitlement that a customer
 * acquires over time and may later redeem toward eligible Afrinkong journeys
 * according to the terms applicable to the point.
 *
 * WHAT IT IS NOT, AND WHY THE CODE CARES
 *
 * Not cash, not a deposit, not an investment, not a security, not currency,
 * not stored fiat, not interest-bearing, not a general payment instrument.
 * That is a legal distinction, and it is also a design constraint that shows
 * up in three concrete places in this file:
 *
 *   - there is no `interest`, `yield`, `growth` or `projection` anywhere, and
 *     no function that makes a balance larger with the passage of time;
 *   - a point's worth is expressed as `entitlement`, never as a `balance` in
 *     dollars, and the conversion lives in a versioned program rather than as
 *     a constant;
 *   - buyback is a bounded, gated operation with a named program rule, not a
 *     withdrawal. See BUYBACK below.
 *
 * THE ONE RULE THIS FILE EXISTS TO ENFORCE
 *
 * A balance is never stored. It is folded from an append-only list of
 * entries, every time, from the beginning. `UPDATE balance = balance + 500`
 * is the mistake this whole module exists to make impossible: it destroys the
 * economic history that any reconciliation, audit or dispute depends on.
 *
 * So the only way to change a wallet is to append an entry, and `wallet()`
 * derives everything else. If the fold and a stored figure ever disagreed,
 * the fold is right by construction.
 *
 * IDEMPOTENCY IS NOT OPTIONAL
 *
 * Payments retry, webhooks are delivered more than once, and a customer will
 * double-click. Every entry carries an idempotency key and `fold` ignores an
 * entry whose key it has already seen. That is what stops one payment
 * becoming two issuances.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongPoints = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---- the lifecycle ------------------------------------------------------
   *
   *   CREATED -> ISSUED -> AVAILABLE -> RESERVED -> REDEEMED
   *                             |            |
   *                             |            +-> CANCELLED -> AVAILABLE
   *                             +-> TRANSFERRED
   *                             +-> BUYBACK_REQUESTED -> BUYBACK_APPROVED
   *                             |                              -> SETTLED
   *                             +-> EXPIRED
   *
   * Points are fungible within a lot, so the lifecycle is tracked per entry
   * rather than per individual point: a customer does not own point #4,182,
   * they hold a quantity in a state. Tracking individually would be precise
   * about something nobody can observe and slow about everything else.
   */
  var STATES = ['CREATED', 'ISSUED', 'AVAILABLE', 'RESERVED', 'REDEEMED',
                'TRANSFERRED', 'BUYBACK_REQUESTED', 'BUYBACK_APPROVED',
                'SETTLED', 'CANCELLED', 'EXPIRED'];

  /* Every kind of entry, and what it does to the fold. `available` and
     `reserved` are the two live pools; everything else is terminal and kept
     only so the history reads correctly. */
  var KINDS = {
    PURCHASE:     { available: +1, reserved: 0,  acquired: +1 },
    TRANSFER_IN:  { available: +1, reserved: 0,  acquired: +1 },
    ADJUST_UP:    { available: +1, reserved: 0,  acquired: +1, admin: true },

    RESERVE:      { available: -1, reserved: +1 },
    RELEASE:      { available: +1, reserved: -1 },
    REDEEM:       { available: 0,  reserved: -1, redeemed: +1 },

    TRANSFER_OUT: { available: -1, reserved: 0,  transferred: +1 },
    BUYBACK:      { available: -1, reserved: 0,  boughtBack: +1 },
    EXPIRE:       { available: -1, reserved: 0,  expired: +1 },
    ADJUST_DOWN:  { available: -1, reserved: 0,  adjusted: +1, admin: true }
  };

  /* ---- point programs, versioned -----------------------------------------
   *
   * NEVER `1 point = $1` AS A CONSTANT IN THE APPLICATION.
   *
   * The relationship between money and entitlement is a property of the
   * program a point was issued under, not of the codebase, and it has to be
   * able to change for future issuance without altering what past issuance
   * meant. A point bought in 2026 keeps its 2026 terms forever; that is the
   * whole reason this is a versioned record and not a number.
   *
   * `issueRate` is how many points a unit of money acquires. `entitlement` is
   * how much Afrinkong travel value one point applies when redeemed. They are
   * deliberately separate: holding them apart is what lets a program offer a
   * purchasing advantage without implying a cash value, and what stops anyone
   * reading a wallet as a dollar balance.
   */
  var PROGRAMS = {
    'AFK-TP-2026.1': {
      id: 'AFK-TP-2026.1',
      name: 'Afrinkong Travel Points 2026',
      version: 1,
      status: 'draft',            // never 'active' until counsel has signed it
      currency: 'USD',
      issueRate: 1,               // points acquired per 1 USD paid
      entitlement: 1,             // Afrinkong travel value applied per point
      minPurchase: 25,
      transferable: true,
      /* BUYBACK IS THE CLAUSE WITH REGULATORY WEIGHT.
         A guaranteed cash redemption can change what this product legally is.
         `discretionary` is the safe default and it is the one encoded here;
         moving it to a contractual guarantee is a decision for counsel, not
         for a commit. */
      buyback: {
        offered: true,
        discretionary: true,
        rate: 0.90,               // of eligible entitlement value
        minHoldDays: 90,
        minPoints: 100,
        maxPerYear: 5000
      },
      /* Attaches to the BOOKING, not to the customer's whole holding. A
         cancellation inside the restricted window affects the points reserved
         against that journey and leaves the rest of the wallet alone. */
      cancellation: [
        { fromDays: 31, release: 1.00, buybackEligible: true },
        { fromDays: 8,  release: 0.50, buybackEligible: false },
        { fromDays: 0,  release: 0.00, buybackEligible: false }
      ],
      expiryMonths: 0,            // 0 = no expiry under this program
      effectiveFrom: '2026-01-01',
      effectiveUntil: null
    }
  };

  function program(id) {
    var p = PROGRAMS[id];
    if (!p) throw new Error('unknown point program: ' + id);
    return p;
  }

  /* ---- product state ------------------------------------------------------
   *
   * THREE STATES, AND ONLY THE LAST ONE MAY ISSUE A POINT.
   *
   *   PLANNING        arithmetic only. A journey cost expressed in points so
   *                   somebody can see what the goal looks like. No program is
   *                   involved, nothing is owned, nothing is promised.
   *   DRAFT_PROGRAM   a program exists and its terms are written, but they
   *                   have not been approved. Goals may be calculated against
   *                   it and labelled as estimates. NOTHING MAY BE ISSUED.
   *   ACTIVE_PROGRAM  the terms are approved and the payment and ledger
   *                   infrastructure exists. Only here does a point become a
   *                   thing a customer holds.
   *
   * This is not a comment asking somebody to be careful. `fold` refuses any
   * entry that would create points under a program that is not active, so the
   * distinction is enforced by the same function that computes every balance.
   * The site is in DRAFT_PROGRAM today and the test suite asserts it.
   */
  var PRODUCT_STATE = {
    PLANNING: 'PLANNING',
    DRAFT_PROGRAM: 'DRAFT_PROGRAM',
    ACTIVE_PROGRAM: 'ACTIVE_PROGRAM'
  };

  /* Creating points. Moving points a customer already has between pools is
     not on this list: a RESERVE under a draft program cannot happen anyway,
     because there is nothing to reserve. */
  var ISSUING_KINDS = ['PURCHASE', 'TRANSFER_IN', 'ADJUST_UP'];

  function stateOf(id) {
    if (!id) return PRODUCT_STATE.PLANNING;
    return program(id).status === 'active'
      ? PRODUCT_STATE.ACTIVE_PROGRAM
      : PRODUCT_STATE.DRAFT_PROGRAM;
  }

  function mayIssue(id) {
    return stateOf(id) === PRODUCT_STATE.ACTIVE_PROGRAM;
  }

  /* ---- money and points ---------------------------------------------------
   *
   * Whole points only. A fraction of a unit of travel entitlement is not a
   * thing anybody can hold, spend or be told about honestly, and rounding
   * halves at the boundary is how a ledger acquires a slow leak. Money is
   * handled in minor units (cents) for the same reason: floating-point
   * dollars do not add up.
   */
  function pointsFor(programId, amountMinor) {
    var p = program(programId);
    if (!isFinite(amountMinor) || amountMinor <= 0) return 0;
    return Math.floor((amountMinor / 100) * p.issueRate);
  }

  function priceOf(programId, points) {
    var p = program(programId);
    if (!isFinite(points) || points <= 0) return 0;
    return Math.round((points / p.issueRate) * 100);
  }

  /* What a quantity of points applies toward a journey, in minor units. Named
     `entitlementOf` and not `valueOf` on purpose: this is what the points buy
     from Afrinkong, not what they are worth in cash. */
  function entitlementOf(programId, points) {
    var p = program(programId);
    return Math.round(points * p.entitlement * 100);
  }

  /* ---- the fold -----------------------------------------------------------
   *
   * The whole point of the module. Entries in, wallet out, no state kept.
   */
  function blank() {
    return {
      available: 0, reserved: 0, redeemed: 0, transferred: 0,
      boughtBack: 0, expired: 0, adjusted: 0, acquired: 0,
      entries: 0, ignored: 0, reservations: {}
    };
  }

  function fold(entries) {
    var w = blank();
    var seen = Object.create(null);
    var list = entries || [];
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      var kind = KINDS[e.kind];
      if (!kind) throw new Error('unknown ledger kind: ' + e.kind);
      if (!e.idempotencyKey) {
        throw new Error('ledger entry without an idempotency key: ' + e.id);
      }
      /* Delivered twice is the normal case, not the exceptional one. */
      if (seen[e.idempotencyKey]) { w.ignored++; continue; }
      seen[e.idempotencyKey] = true;

      var q = e.quantity;
      if (!isFinite(q) || q <= 0 || Math.floor(q) !== q) {
        throw new Error('ledger quantity must be a positive whole number: ' + q);
      }

      /* Only settled money creates points. A payment that is authorised,
         pending, or merely reported by a browser is not a payment. */
      if (e.kind === 'PURCHASE' && e.status !== 'SETTLED') { w.ignored++; continue; }

      /* AND ONLY AN APPROVED PROGRAM CREATES POINTS AT ALL.
         The site is in DRAFT_PROGRAM: the terms are written and the ledger
         works, and no customer holds anything. This refusal is what makes
         that true rather than merely intended — including if somebody wires a
         payment handler up before the legal answer arrives. */
      if (ISSUING_KINDS.indexOf(e.kind) !== -1 && !mayIssue(e.programVersion)) {
        throw new Error(
          'cannot issue points: program ' + (e.programVersion || '(none)') +
          ' is ' + stateOf(e.programVersion) +
          '. Points may only be issued under an ACTIVE_PROGRAM.');
      }

      for (var field in kind) {
        if (field === 'admin') continue;
        w[field] += kind[field] * q;
      }

      /* Reservations are tracked per journey so a cancellation can act on the
         booking it belongs to rather than on the wallet as a whole. */
      if (e.journeyRef) {
        var r = w.reservations[e.journeyRef] || 0;
        if (e.kind === 'RESERVE') r += q;
        if (e.kind === 'RELEASE' || e.kind === 'REDEEM') r -= q;
        w.reservations[e.journeyRef] = r;
        if (r < 0) {
          throw new Error('journey ' + e.journeyRef + ' released more than reserved');
        }
      }

      if (w.available < 0) {
        throw new Error('entry ' + e.id + ' would overdraw the wallet');
      }
      if (w.reserved < 0) {
        throw new Error('entry ' + e.id + ' releases points never reserved');
      }
      w.entries++;
    }
    return w;
  }

  /* The customer-facing shape. Total acquired is stated because "available"
     alone hides what somebody has put in over two years, and that number is
     the one they are proud of. */
  function wallet(entries) {
    var w = fold(entries);
    return {
      available: w.available,
      reserved: w.reserved,
      redeemed: w.redeemed,
      acquired: w.acquired,
      transferred: w.transferred,
      boughtBack: w.boughtBack,
      expired: w.expired,
      reservations: w.reservations,
      entriesApplied: w.entries,
      duplicatesIgnored: w.ignored
    };
  }

  /* ---- can this happen? ---------------------------------------------------
   *
   * Asked BEFORE an entry is appended, so a refusal is an answer rather than
   * an exception. The fold refuses too — that is the backstop — but a wallet
   * screen needs to say "no, and here is why" without throwing.
   */
  function can(entries, proposed) {
    var w = wallet(entries);
    var kind = KINDS[proposed.kind];
    if (!kind) return { ok: false, why: 'unknown entry kind' };
    var q = proposed.quantity;
    if (!isFinite(q) || q <= 0 || Math.floor(q) !== q) {
      return { ok: false, why: 'quantity must be a positive whole number' };
    }
    if (kind.available === -1 && w.available < q) {
      return { ok: false, why: 'not enough available points',
               available: w.available, wanted: q };
    }
    if (kind.reserved === -1 && w.reserved < q) {
      return { ok: false, why: 'not that many points are reserved' };
    }
    return { ok: true };
  }

  /* ---- cancellation -------------------------------------------------------
   *
   * ATTACHES TO THE BOOKING, NOT TO THE WALLET.
   *
   * A customer holding 5,000 points who reserved 3,500 against a journey and
   * cancels inside the restricted window has a question about those 3,500.
   * The other 1,500 are untouched, and any rule that forgets that is one that
   * destroys somebody's two years of accumulation over one changed plan.
   */
  function cancellation(programId, daysToDeparture, reservedPoints) {
    var p = program(programId);
    var band = null;
    for (var i = 0; i < p.cancellation.length; i++) {
      if (daysToDeparture >= p.cancellation[i].fromDays) { band = p.cancellation[i]; break; }
    }
    if (!band) band = p.cancellation[p.cancellation.length - 1];
    var released = Math.floor(reservedPoints * band.release);
    return {
      daysToDeparture: daysToDeparture,
      released: released,
      forfeited: reservedPoints - released,
      buybackEligible: band.buybackEligible,
      /* Said in words because this is the sentence a customer will read at the
         worst moment they will ever read anything on this site. */
      note: band.release === 1
        ? 'Outside the restricted window: every point reserved for this journey returns to your wallet.'
        : band.release === 0
          ? 'Inside seven days Afrinkong has already committed to suppliers, so points reserved for this journey cannot be returned. The rest of your wallet is unaffected.'
          : 'Part of the points reserved for this journey return to your wallet; the rest covers commitments already made. The rest of your wallet is unaffected.'
    };
  }

  /* ---- buyback ------------------------------------------------------------
   *
   * Deliberately hard to reach, and it returns a quote rather than performing
   * anything. Presenting this as "cash out any time" would be both untrue and
   * the fastest route to being a different kind of company than this one is.
   */
  function buybackQuote(programId, entries, points, heldDays, boughtBackThisYear) {
    var p = program(programId);
    var b = p.buyback;
    var w = wallet(entries);
    var refuse = function (why) { return { eligible: false, why: why, points: points }; };

    if (!b || !b.offered) return refuse('this program does not offer buyback');
    if (points < b.minPoints) return refuse('below the minimum of ' + b.minPoints + ' points');
    if (points > w.available) return refuse('only available points can be bought back');
    if (heldDays < b.minHoldDays) return refuse('points must be held for ' + b.minHoldDays + ' days');
    if ((boughtBackThisYear || 0) + points > b.maxPerYear) {
      return refuse('above the annual limit of ' + b.maxPerYear + ' points');
    }
    return {
      eligible: true,
      discretionary: b.discretionary,
      points: points,
      grossMinor: entitlementOf(programId, points),
      rate: b.rate,
      payableMinor: Math.round(entitlementOf(programId, points) * b.rate),
      note: b.discretionary
        ? 'Buyback is offered at Afrinkong’s discretion under the terms of this program. It is not a guaranteed right of redemption.'
        : 'Buyback is contractual under the terms of this program.'
    };
  }

  /* ---- the journey goal ---------------------------------------------------
   *
   * The bridge to the existing planner. scripts/fund-math.js divides a journey
   * cost by whole months; this expresses the same arithmetic as travel
   * purchasing power, which is the thing the customer is actually building.
   *
   * No projection, no growth, no assumption — the same division, in points.
   */
  function goal(programId, journeyCostMinor, held, months) {
    var target = Math.ceil(journeyCostMinor / 100 * program(programId).issueRate);
    var remaining = Math.max(0, target - (held || 0));
    return {
      target: target,
      held: held || 0,
      remaining: remaining,
      progress: target > 0 ? Math.min(1, (held || 0) / target) : 0,
      monthly: months > 0 ? Math.ceil(remaining / months) : null,
      months: months
    };
  }

  return {
    STATES: STATES,
    KINDS: KINDS,
    PROGRAMS: PROGRAMS,
    PRODUCT_STATE: PRODUCT_STATE,
    stateOf: stateOf,
    mayIssue: mayIssue,
    program: program,
    pointsFor: pointsFor,
    priceOf: priceOf,
    entitlementOf: entitlementOf,
    fold: fold,
    wallet: wallet,
    can: can,
    cancellation: cancellation,
    buybackQuote: buybackQuote,
    goal: goal
  };
});
