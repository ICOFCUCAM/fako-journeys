/* Booking and redemption economics. Section D (redemption).
 *
 * @product: gated | @gate: booking-not-built | @surface: none
 * ===========================================================================
 * A note on numbering: an earlier Section D settled the legal and compliance
 * boundary and lives in `docs/travel-point-compliance.md`. This is a second
 * Section D covering what happens when somebody actually travels. Both are
 * kept.
 *
 * THE ONE THING THIS FILE EXISTS TO PREVENT
 *
 * `balance -= 4800` when a customer clicks Book.
 *
 * A booking is a conversation with Afrinkong that can be rejected, abandoned
 * or cancelled, and points must survive all three. So clicking Book RESERVES
 * points — they stop being spendable elsewhere and remain entirely the
 * customer's — and only a confirmed itinerary REDEEMS them. Two events, never
 * one, and the ledger records both.
 *
 * IT APPENDS NOTHING. Every function here returns the ledger entries a
 * transition *implies*, for a caller with the authority to append them. That
 * keeps the booking machine testable without a ledger and makes it impossible
 * for a booking screen to issue or consume points on its own — D21.2 of the
 * compliance section.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongBooking = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /*        REQUESTED
   *        ├── REJECTED            (by Afrinkong; nothing was reserved)
   *        └── ACCEPTED
   *            └── RESERVED
   *                ├── CANCELLED   (by the customer; bands apply)
   *                └── CONFIRMED
   *                    └── REDEEMED
   */
  var BOOKING_STATES = ['REQUESTED', 'ACCEPTED', 'REJECTED', 'RESERVED',
                        'CONFIRMED', 'CANCELLED', 'REDEEMED'];
  var BOOKING_NEXT = {
    REQUESTED: ['ACCEPTED', 'REJECTED'],
    ACCEPTED:  ['RESERVED', 'REJECTED'],
    RESERVED:  ['CONFIRMED', 'CANCELLED'],
    CONFIRMED: ['REDEEMED', 'CANCELLED'],
    REDEEMED:  [],
    REJECTED:  [],
    CANCELLED: []
  };

  /* Which ledger entries a transition implies. Reservation and redemption are
     separate kinds precisely so that a wallet can show points committed but
     not yet consumed. */
  var IMPLIES = {
    RESERVED:  'RESERVE',
    CANCELLED: 'RELEASE',
    REDEEMED:  'REDEEM'
  };

  /* D9/C12: WHAT A POINT MAY BE SPENT ON IS A PROGRAMME TERM.
   *
   * Not everything on a journey is inside the programme. The site already
   * settles park fees, permits and conservation charges separately and says so
   * on its own pages; expressing that as programme scope rather than as a
   * hard-coded list means a later programme can widen or narrow it without
   * touching the ledger.
   *
   * Returns the services that fall OUTSIDE scope, so a caller can show a
   * customer exactly which line of their journey the points do not reach. */
  function ineligible(programId, serviceTypes) {
    var scope = Points.program(programId).eligibleServices || [];
    return (serviceTypes || []).filter(function (t) {
      return scope.indexOf(t) === -1;
    });
  }

  /* D1/D10: CAN THIS CUSTOMER BOOK THIS JOURNEY?
   *
   * The shortfall is reported IN POINTS and nothing else. It is deliberately
   * not converted to money: D7 says the programme must define the settlement
   * mechanism for a mixed payment, that decision has not been made, and a
   * function that quietly returned "$1,500" would have made it. */
  function request(programId, journey, wallet, serviceTypes) {
    var required = journey.requirement;
    var outside = ineligible(programId, serviceTypes || ['journey']);
    if (outside.length) {
      return { ok: false, why: 'outside the programme’s eligible services',
               ineligible: outside, required: required };
    }
    /* F: THE PROGRAMME MAY CAP HOW MUCH OF A JOURNEY POINTS COVER.
       A programme saying "up to 70% of the eligible journey" means a customer
       with enough points still settles the rest another way — so the cap is
       applied BEFORE the sufficiency test, or a 70% programme would happily
       report `ok` for a full-point booking it does not permit. */
    var cap = Points.program(programId).redemptionCap || { maxPortion: 1 };
    var payableByPoints = Math.floor(required * (cap.maxPortion == null
                                                 ? 1 : cap.maxPortion));
    if (payableByPoints < required) {
      var have = Math.min(wallet.available, payableByPoints);
      return {
        ok: false,
        why: 'this programme covers part of a journey with Travel Points',
        required: required,
        payableByPoints: payableByPoints,
        maxPortion: cap.maxPortion,
        available: wallet.available,
        applied: have,
        /* The remainder is stated IN POINTS, not converted. Same rule as the
           shortfall below and for the same reason. */
        remainderPoints: required - have,
        settlement: settlementTerms(programId)
      };
    }

    if (wallet.available < required) {
      return {
        ok: false,
        why: 'not enough available Travel Points',
        required: required,
        available: wallet.available,
        shortfallPoints: required - wallet.available,
        /* F9/F10: WHAT A CUSTOMER 300 POINTS SHORT MAY ACTUALLY DO.
         *
         * This used to report the shortfall and stop, which is correct about
         * the conversion rate and unhelpful about everything else — a customer
         * reading it would conclude they must buy another whole block of
         * points. Decision F settles that points and money MAY be combined, so
         * the permission is now reported.
         *
         * The RATE is still not invented here. Whether the combination is
         * permitted is a programme term and is answered; how a shortfall
         * converts to money is a different programme term, is not decided, and
         * `mechanism: null` says so. A function that quietly returned "$1,500"
         * would have made that decision at a call site. B-iv. */
        settlement: settlementTerms(programId),
        /* F9: and the other paths, so the answer is never just "no". None of
           them is a conversion of the customer's points into cash. */
        alternatives: ['acquire the additional Travel Points',
                       'change the itinerary',
                       'choose another journey',
                       'wait — the points do not expire under this programme']
      };
    }
    return { ok: true, required: required, available: wallet.available,
             remainingAfter: wallet.available - required };
  }

  /* Locked from the moment points are reserved. Not from ACCEPTED: nothing is
     committed there and a customer who has not yet reserved should see the
     current price, not a stale one that happens to favour them. */
  var LOCKED_STATES = ['RESERVED', 'CONFIRMED', 'REDEEMED'];
  function isLocked(booking) {
    return LOCKED_STATES.indexOf(booking.state) !== -1;
  }

  /* DECISION F: BEFORE THE LOCK, A REQUIREMENT MAY MOVE — AND IS SHOWN MOVING.
   *
   * A customer still saving is not protected from a price change and should not
   * be told they are. What they get instead is both numbers and the difference,
   * which is C8's rule, and the explicit statement that their POINTS did not
   * change — because a requirement that moved and a balance that moved look the
   * same on a screen unless somebody says otherwise. */
  function reprice(booking, newRequirement, rateCardVersion) {
    if (isLocked(booking)) {
      return { ok: false,
               why: 'a booking whose points are reserved is price-locked',
               locked: true, pointsRequired: booking.pointsRequired };
    }
    var next = JSON.parse(JSON.stringify(booking));
    var was = booking.pointsRequired;
    next.pointsRequired = newRequirement;
    next.rateCardVersion = rateCardVersion || booking.rateCardVersion || null;
    next.repricing = {
      was: was,
      now: newRequirement,
      difference: newRequirement - was,
      direction: newRequirement === was ? 'unchanged'
               : newRequirement > was ? 'increased' : 'decreased',
      /* B18/F, said rather than implied. */
      pointsHeldUnaffected: true,
      note: 'The journey\u2019s requirement changed. The Travel Points you ' +
            'hold did not.'
    };
    return { ok: true, booking: next, repricing: next.repricing };
  }

  /* Shared by the cap path and the shortfall path, so the two cannot drift
     into describing the same programme term differently. */
  function settlementTerms(programId) {
    /* H: `available`, not just `permitted`. A programme may intend to allow a
       mixed settlement and have no defined mechanism for one, and a screen
       reading only `permitted` would offer the customer something nobody can
       perform. mixedSettlement() computes both together so they cannot be
       read apart. */
    var m = Points.mixedSettlement(programId);
    return {
      permitted: m.permitted,
      mechanism: m.mechanism,
      available: m.available,
      pointsFirst: m.pointsFirst,
      note: m.available
        ? 'This programme permits a journey to be settled partly in Travel ' +
          'Points and partly through an approved payment method.'
        : m.permitted
          ? 'A mixed settlement is contemplated by this programme but the ' +
            'mechanism has not been defined, so it cannot be offered yet.'
          : 'This programme does not permit a journey to be settled partly in money.'
    };
  }

  /* D2: THE ECONOMIC AGREEMENT, RECONSTRUCTABLE LATER.
     A booking that recorded only "4,800 TP" could not answer what those points
     meant when they were committed. Programme and version travel with it. */
  function open(programId, journey) {
    var p = Points.program(programId);
    return {
      journeyId: journey.journeyId,
      programId: p.id,
      programVersion: p.version,
      pointsRequired: journey.requirement,
      pointsReserved: 0,
      pointsRedeemed: 0,
      rateCardVersion: journey.rateCardVersion || null,
      state: 'REQUESTED',
      history: [{ to: 'REQUESTED' }]
    };
  }

  /* Advance the booking, and return the ledger entries it implies. The caller
     appends them; this cannot. */
  function advance(booking, to, opts) {
    var t = (to || '').toUpperCase();
    if (BOOKING_STATES.indexOf(t) === -1) {
      return { ok: false, why: 'unknown booking state: ' + to };
    }
    var allowed = BOOKING_NEXT[booking.state] || [];
    if (allowed.indexOf(t) === -1) {
      return { ok: false, why: booking.state + ' cannot move to ' + t,
               from: booking.state, allowed: allowed };
    }
    var o = opts || {};
    var next = JSON.parse(JSON.stringify(booking));
    var entries = [];
    var kind = IMPLIES[t];

    /* DECISION F: A CONFIRMED BOOKING IS PRICE-LOCKED.
     *
     * "The price increased to 6,000 TP, so give us another 1,000" is the
     * sentence this refuses. Once the points are reserved against a journey the
     * requirement is fixed for that booking, and a later rate card cannot reach
     * back into it.
     *
     * The lock was already true STRUCTURALLY — every branch below reads
     * `booking.pointsRequired` and nothing recomputes it — but structural
     * truth is not a refusal, and a caller passing a new requirement would
     * simply have been ignored rather than told. Silently ignoring a reprice
     * and refusing it look identical until somebody relies on the first. */
    if (o.pointsRequired != null &&
        o.pointsRequired !== booking.pointsRequired && isLocked(booking)) {
      return { ok: false,
               why: 'this booking\u2019s Travel Point requirement is locked at ' +
                    booking.pointsRequired +
                    '; a price change cannot be applied to a booking whose ' +
                    'points are already reserved',
               locked: true,
               pointsRequired: booking.pointsRequired,
               attempted: o.pointsRequired,
               lockedAt: booking.lockedAt || null };
    }

    if (t === 'RESERVED') {
      next.pointsReserved = booking.pointsRequired;
      /* The moment the lock takes effect, recorded WITH the rate card that
         produced the figure — so "why 5,000 and not 6,000" is answerable from
         the booking rather than from somebody's memory of when they clicked. */
      next.priceLocked = true;
      next.lockedAt = { state: 'RESERVED',
                        pointsRequired: booking.pointsRequired,
                        rateCardVersion: booking.rateCardVersion || null,
                        programVersion: booking.programVersion };
    } else if (t === 'CANCELLED') {
      /* D-cancellation: how much comes back is a PROGRAMME term read from the
         band, not a number chosen here. `daysToDeparture` is supplied by the
         caller because this module has no clock. */
      var band = Points.cancellation(booking.programId,
                                     o.daysToDeparture == null ? 999 : o.daysToDeparture,
                                     booking.pointsReserved || booking.pointsRequired);
      next.cancellation = band;
      next.pointsReserved = 0;
      if (band.released > 0) {
        entries.push(entry('RELEASE', band.released, booking, o));
      }
      if (band.forfeited > 0) {
        /* Forfeited points leave the reserved pool without returning. Recorded
           as its own movement so the history says what happened rather than
           leaving a gap somebody has to explain. */
        entries.push(entry('REDEEM', band.forfeited, booking, o));
      }
      return { ok: true, booking: stamp(next, t), entries: entries };
    } else if (t === 'REDEEMED') {
      next.pointsRedeemed = booking.pointsRequired;
      next.pointsReserved = 0;
    }

    if (kind && t !== 'CANCELLED') {
      entries.push(entry(kind, booking.pointsRequired, booking, o));
    }
    return { ok: true, booking: stamp(next, t), entries: entries };
  }

  function entry(kind, quantity, booking, o) {
    return {
      kind: kind,
      quantity: quantity,
      status: 'SETTLED',
      programVersion: booking.programId,
      journeyRef: booking.journeyId,
      /* The caller supplies ids; this module invents none, because an id it
         invented could collide with one a database issued. */
      id: o.entryId || null,
      idempotencyKey: o.idempotencyKey || null
    };
  }

  function stamp(b, to) {
    b.state = to;
    b.history = b.history.concat([{ to: to }]);
    return b;
  }

  return {
    BOOKING_STATES: BOOKING_STATES,
    BOOKING_NEXT: BOOKING_NEXT,
    ineligible: ineligible,
    request: request,
    open: open,
    advance: advance,
    reprice: reprice,
    isLocked: isLocked,
    LOCKED_STATES: LOCKED_STATES
  };
});
