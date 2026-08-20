/* Booking and redemption economics. Section D (redemption).
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
    if (wallet.available < required) {
      return {
        ok: false,
        why: 'not enough available Travel Points',
        required: required,
        available: wallet.available,
        shortfallPoints: required - wallet.available,
        /* NO CONVERSION. See D7 — the programme has not defined one and this
           is not the place to invent it. */
        settlement: {
          mechanism: null,
          note: 'A shortfall may be settleable through the normal payment ' +
                'mechanism. The conversion between Travel Points and money for ' +
                'that purpose is a programme term and has not been defined.'
        }
      };
    }
    return { ok: true, required: required, available: wallet.available,
             remainingAfter: wallet.available - required };
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

    if (t === 'RESERVED') {
      next.pointsReserved = booking.pointsRequired;
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
    advance: advance
  };
});
