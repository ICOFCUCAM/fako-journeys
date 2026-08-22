/* Repurchase, as a sequence of decisions rather than a button. Section E.
 *
 * @product: gated | @gate: programme-compliance | @surface: none
 * ===========================================================================
 * WHAT THIS IS NOT
 *
 * It is not a withdrawal, it is not a refund of a purchase price, and it is
 * not a right. E2 is explicit that describing repurchase as "get 90% of the
 * money you paid back" makes the product a different product — money in, money
 * out, with a holding period in the middle — whatever the terms say. So the
 * word used throughout is REPURCHASE: Afrinkong may, at its discretion and
 * under the terms of a particular programme, buy back travel entitlement it
 * previously issued. The programme decides the basis; `basis` is a term, not a
 * definition.
 *
 * E3'S SEQUENCE, AND WHY IT HAS FIVE STEPS INSTEAD OF ONE
 *
 *     request -> eligibility -> quotation -> acceptance -> settlement
 *
 * A single `buyback(points)` call would collapse five separable decisions into
 * one, and each of them is one somebody can refuse. A customer may ask what
 * they would be offered without selling anything; Afrinkong may decline,
 * because E1 says repurchase is discretionary and a discretion exercised
 * nowhere is not a discretion; and the customer may walk away from a quote
 * they do not like. Only the last step touches a ledger.
 *
 * IT APPENDS NOTHING — the same rule booking.js follows. `settle()` returns
 * the BUYBACK entry a settlement implies, for a caller with the authority to
 * append it. A quote removes no points, and a quote a customer never accepted
 * must leave no trace anywhere.
 *
 * AND IT MOVES NO MONEY. `SETTLED` here means the ledger event: the points
 * have left the wallet. Paying the customer is a separate act in a separate
 * system that does not exist yet, and `payment: null` on the result says so
 * rather than implying it happened.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongBuyback = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /*        REQUESTED
   *        ├── REFUSED           (ineligible; nothing was ever quoted)
   *        └── QUOTED
   *            ├── LAPSED        (the customer did not answer in time)
   *            ├── DECLINED      (the customer said no)
   *            └── ACCEPTED
   *                ├── REJECTED  (Afrinkong's discretion — E1)
   *                └── APPROVED
   *                    └── SETTLED   -> implies one BUYBACK ledger entry
   *
   * REFUSED and REJECTED are kept apart on purpose. Refused means the terms
   * did not permit it and the customer can be told exactly which term; rejected
   * means the terms permitted it and Afrinkong chose not to. Collapsing them
   * would turn a discretionary decision into an apparent rule, which is the
   * misrepresentation E1 is guarding against.
   */
  var REQUEST_STATES = ['REQUESTED', 'REFUSED', 'QUOTED', 'LAPSED', 'DECLINED',
                        'ACCEPTED', 'REJECTED', 'APPROVED', 'SETTLED'];
  var REQUEST_NEXT = {
    REQUESTED: ['QUOTED', 'REFUSED'],
    QUOTED:    ['ACCEPTED', 'DECLINED', 'LAPSED'],
    ACCEPTED:  ['APPROVED', 'REJECTED'],
    APPROVED:  ['SETTLED', 'REJECTED'],
    SETTLED:   [],
    REFUSED:   [],
    LAPSED:    [],
    DECLINED:  [],
    REJECTED:  []
  };

  /* E3 step 1-3: ask, and be told. Returns a request in QUOTED or REFUSED —
     never in a state that has moved any points, because at this stage the
     customer has done nothing but ask a question.

     `context` carries what this module cannot know and refuses to guess:
     `heldDays`, `boughtBackThisYear`, and `commitments` — the journeys these
     points are committed to, with days to departure, which E6 needs in order
     to refuse a repurchase inside a journey's restricted window. */
  function request(programId, entries, points, context) {
    var c = context || {};
    var quote = Points.buybackQuote(programId, entries, points,
                                    c.heldDays == null ? 0 : c.heldDays,
                                    c.boughtBackThisYear || 0,
                                    c.commitments || []);
    var p = Points.program(programId);
    var base = {
      programId: p.id,
      programVersion: p.version,
      points: points,
      /* E2/E11: which basis produced the figure, recorded on the request
         itself. A quote read a year later has to be able to say what rule it
         was quoted under, and the programme's terms may have moved on. */
      basis: (p.buyback && p.buyback.basis) || null,
      discretionary: !!(p.buyback && p.buyback.discretionary),
      quote: null
    };
    if (!quote.eligible) {
      return stamp(Object.assign(base, {
        state: 'REQUESTED', why: quote.why, detail: quote,
        history: [{ to: 'REQUESTED' }]
      }), 'REFUSED');
    }
    return stamp(Object.assign(base, {
      state: 'REQUESTED', quote: quote, history: [{ to: 'REQUESTED' }]
    }), 'QUOTED');
  }

  /* Advance a request, and return the ledger entries it implies — which is
     nothing at all until SETTLED, and exactly one entry then. */
  function advance(req, to, opts) {
    var t = (to || '').toUpperCase();
    if (REQUEST_STATES.indexOf(t) === -1) {
      return { ok: false, why: 'unknown buyback state: ' + to };
    }
    var allowed = REQUEST_NEXT[req.state] || [];
    if (allowed.indexOf(t) === -1) {
      return { ok: false, why: req.state + ' cannot move to ' + t,
               from: req.state, allowed: allowed };
    }
    var o = opts || {};
    var next = clone(req);

    if (t === 'REJECTED') {
      /* E1: a discretionary refusal is recorded WITH ITS REASON. A discretion
         nobody has to account for reads as arbitrary, and the file that stores
         the decision is the only place the accounting can happen. */
      next.rejectedReason = o.reason || null;
    }

    if (t !== 'SETTLED') {
      return { ok: true, request: stamp(next, t), entries: [] };
    }

    /* THE ONE PLACE POINTS ACTUALLY LEAVE, AND IT RE-CHECKS EVERYTHING.
     *
     * A quote is not a hold. Between quotation and settlement the customer may
     * have reserved those same points against a journey, spent them, or had
     * them lapse — and settling a stale quote would let one set of points be
     * both sold back and travelled on. So the request is re-quoted against the
     * ledger as it stands now, and a settlement that no longer qualifies is
     * refused rather than honoured on the strength of an old number.
     *
     * `entries` must therefore be supplied at settlement. Refusing without it
     * is deliberate: defaulting to the quotation's own figures would restore
     * exactly the bug this paragraph exists to prevent. */
    if (!o.entries) {
      return { ok: false, why: 'settlement requires the current ledger; a quote is not a hold' };
    }
    var now = Points.buybackQuote(req.programId, o.entries, req.points,
                                  o.heldDays == null ? 0 : o.heldDays,
                                  o.boughtBackThisYear || 0,
                                  o.commitments || []);
    if (!now.eligible) {
      return { ok: false, why: 'no longer eligible at settlement: ' + now.why,
               requoted: now };
    }
    next.settledQuote = now;
    /* If the world moved between quotation and settlement, say which figure
       was honoured rather than letting the difference pass unremarked. */
    next.quoteChanged = !!(req.quote &&
      req.quote.payableMinor !== now.payableMinor);

    return {
      ok: true,
      request: stamp(next, t),
      entries: [{
        kind: 'BUYBACK',
        quantity: req.points,
        status: 'SETTLED',
        programVersion: req.programId,
        /* E9: a repurchase and a cancellation are different events and this is
           where that is true rather than merely stated. A cancellation emits
           RELEASE and REDEEM against a journeyRef; a repurchase emits BUYBACK
           against none, because no journey was involved. Nothing downstream
           has to infer which happened from amounts. */
        journeyRef: null,
        id: o.entryId || null,
        idempotencyKey: o.idempotencyKey || null
      }],
      /* Not a payment instruction. See the header. */
      payment: null
    };
  }

  function stamp(r, to) {
    r.state = to;
    r.history = (r.history || []).concat([{ to: to }]);
    return r;
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  return {
    REQUEST_STATES: REQUEST_STATES,
    REQUEST_NEXT: REQUEST_NEXT,
    request: request,
    advance: advance
  };
});
