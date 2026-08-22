/* Giving Travel Points to somebody else. Decision E.
 *
 * @product: gated | @gate: programme-compliance | @surface: none
 * ===========================================================================
 * THE DISTINCTION THE WHOLE OF THIS FILE EXISTS TO HOLD
 *
 *   "I want to give my 3,000 TP to my wife."     -> allowed
 *   "I want to sell my 3,000 TP for $2,700."     -> not allowed
 *
 * Transfer and sale are the same movement of points and completely different
 * products. One is a travel entitlement being used by the person who will
 * actually travel; the other is a financial instrument changing hands for
 * money, and a system that permits the second has an exchange in it whether or
 * not anybody built one.
 *
 * `mayTransfer()` in points-ledger.js already refuses on `secondaryMarket`
 * separately from `transferable` — the split was built for Decision C and is
 * exactly the shape Decision E needs, so this file inherits it rather than
 * re-deciding it.
 *
 * E12: A TRANSFER IS NOT AN ISSUANCE. James -2,000, Sarah +2,000, and the
 * programme's total supply is unchanged. Two entries that must be appended
 * together or not at all, and `conserves()` below is the property stated as a
 * test rather than as a comment.
 *
 * IT APPENDS NOTHING, like booking.js and buyback.js. It returns the pair of
 * entries a transfer implies, for a caller with the authority to append them.
 *
 * Pure. No DOM, no network, no clock, no storage.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongTransfer = api;
})(typeof self !== 'undefined' ? self : this, function (Points) {
  'use strict';

  /* E3/E8/E11: WHY A TRANSFER IS TYPED RATHER THAN JUST BEING A TRANSFER.
   *
   * All four move points the same way. They differ in what documentation is
   * required before somebody may do it, and recording the type at the moment
   * it happens is the only chance to capture that — reconstructing "was this a
   * gift or an inheritance" from a ledger three years later is not possible.
   *
   * CORPORATE_GIFT and ESTATE are listed and not built. Decision E asks that
   * the economic model have a place for them, not that the machinery exist;
   * naming them costs nothing now and means neither becomes a new economic
   * unit later. `requiresDocumentation` is what marks the difference. */
  var TRANSFER_TYPES = {
    GIFT:           { requiresDocumentation: false,
                      note: 'A personal transfer to another identified customer.' },
    FAMILY_POOL:    { requiresDocumentation: false,
                      note: 'A contribution toward a shared journey goal.' },
    CORPORATE_GIFT: { requiresDocumentation: true,
                      note: 'An employer granting Travel Points as a benefit. ' +
                            'Not built: the model permits it, no corporate ' +
                            'machinery exists.' },
    ESTATE:         { requiresDocumentation: true,
                      note: 'Passing to a beneficiary. Requires documentation ' +
                            'and identity verification under programme terms ' +
                            'and applicable law. Not built.' }
  };

  /* E1-E6, E12: propose a transfer, or refuse it with the rule that refused.
   *
   * `from` and `to` are customer identifiers supplied by the caller. This
   * module does not know what a customer is and deliberately does not: it
   * checks that both are NAMED, which is E3, and leaves who they are to a
   * system that can verify it.
   */
  function propose(programId, from, to, points, opts) {
    var o = opts || {};
    var type = (o.type || 'GIFT').toUpperCase();
    var spec = TRANSFER_TYPES[type];
    if (!spec) {
      return { ok: false, why: 'unknown transfer type: ' + type,
               types: Object.keys(TRANSFER_TYPES) };
    }

    /* E3: NO ANONYMOUS TRANSFERS. Both ends named, and named differently —
       a transfer to oneself is either a mistake or an attempt to relabel
       points, and neither should append two entries. */
    if (!from || !to) {
      return { ok: false, why: 'a transfer must identify both sender and recipient',
               rule: 'identified' };
    }
    if (from === to) {
      return { ok: false, why: 'a transfer must have two different parties',
               rule: 'identified' };
    }

    if (!isFinite(points) || points <= 0 || Math.floor(points) !== points) {
      return { ok: false, why: 'points must be a positive whole number' };
    }

    /* E2/E6/E11: the programme's own gates — transferable, secondaryMarket,
       and the restricted window. Inherited rather than restated so a
       programme that changes any of them is obeyed here for free. */
    var allowed = Points.mayTransfer(programId, {
      forConsideration: !!o.forConsideration,
      commitments: o.commitments || []
    });
    if (!allowed.ok) return { ok: false, why: allowed.why, rule: allowed.rule };

    /* E6: and the sender must actually have them AVAILABLE. Reserved points
       are excluded by `available` itself, which is the same arithmetic that
       refuses a repurchase of committed points. */
    var w = Points.wallet(o.senderEntries || []);
    if (points > w.available) {
      return { ok: false, why: 'only available points can be transferred',
               rule: 'available', available: w.available, wanted: points };
    }

    /* A programme may forbid transferring the promotional lot while permitting
       transfer generally — `promotional.transferable` is already a term and,
       like `secondaryMarket` before Decision C, nothing read it. A grant that
       cannot be repurchased and expires on its own schedule is not obviously
       something to hand to a third party. */
    var pr = Points.program(programId).promotional;
    if (pr && pr.transferable === false && points > w.purchased) {
      return { ok: false,
               why: 'promotional points cannot be transferred under this programme',
               rule: 'promotionalTransferable',
               purchased: w.purchased, promotional: w.promotional };
    }

    if (spec.requiresDocumentation && !o.documentationRef) {
      return { ok: false,
               why: 'a ' + type + ' transfer requires documentation before it ' +
                    'may be proposed',
               rule: 'documentation' };
    }

    var p = Points.program(programId);
    var common = {
      status: 'SETTLED',
      /* E4: THE PROGRAMME TRAVELS WITH THE ENTITLEMENT.
         Both entries carry the SAME programVersion — the sender's, not
         whatever happens to be active when the recipient receives them. Sarah
         gets 2,000 TP under Programme 2026-A with 2026-A's terms, which is the
         whole of E4 and the reason the recipient cannot be quietly moved onto
         worse terms by the timing of a gift. */
      programVersion: p.id,
      transferType: type,
      /* E5: no fee on an ordinary personal transfer. Stated as a field rather
         than as an absence, so that a programme which ever introduces one has
         to put a number here and cannot do it by omission. */
      feeMinor: 0
    };
    return {
      ok: true,
      type: type,
      from: from,
      to: to,
      points: points,
      programId: p.id,
      programVersion: p.version,
      requiresDocumentation: spec.requiresDocumentation,
      documentationRef: o.documentationRef || null,
      note: spec.note,
      /* E12: two entries, equal and opposite. The pair is the transfer; one
         without the other is either points appearing from nowhere or points
         being destroyed. */
      entries: [
        Object.assign({}, common, {
          kind: 'TRANSFER_OUT', quantity: points,
          customerId: from, counterpartyId: to,
          id: o.outId || null, idempotencyKey: o.outKey || null
        }),
        Object.assign({}, common, {
          kind: 'TRANSFER_IN', quantity: points,
          customerId: to, counterpartyId: from,
          id: o.inId || null, idempotencyKey: o.inKey || null
        })
      ]
    };
  }

  /* E12 AS A PROPERTY, CHECKABLE ON ANY SET OF ENTRIES.
   *
   * The total supply a programme has issued must not change because points
   * moved between people. Given every entry across all customers, the sum of
   * TRANSFER_IN must equal the sum of TRANSFER_OUT — and if it does not, the
   * programme has either minted or destroyed points in the course of a gift.
   */
  function conserves(entries) {
    var out = 0, into = 0;
    (entries || []).forEach(function (e) {
      if (e.kind === 'TRANSFER_OUT') out += e.quantity;
      if (e.kind === 'TRANSFER_IN') into += e.quantity;
    });
    return {
      ok: out === into,
      transferredOut: out,
      transferredIn: into,
      difference: into - out,
      why: out === into ? null
        : into > out
          ? 'more points were received than were sent: a transfer created ' +
            (into - out) + ' TP'
          : (out - into) + ' TP were sent and never received'
    };
  }

  /* E7/E9: FAMILY POOLING, WHICH IS THE FEATURE HIDING INSIDE DECISION E.
   *
   * Four people with 3,000 / 4,000 / 1,500 / 500 TP toward one 10,000 TP
   * journey is a different product from four wallets, and the difference is
   * entirely in the presentation: the same points, counted toward one goal.
   *
   * NOTHING MOVES HERE. This does not transfer anything and appends nothing —
   * a pool is a VIEW over contributions people have separately decided to
   * make. Actually moving the points is `propose()` with type FAMILY_POOL, one
   * transfer per contributor, each with its own consent.
   *
   * Members' points must be under the same programme: pooling across
   * programmes would silently merge two sets of terms, which E4 forbids.
   */
  function pool(programId, members, target) {
    var contributions = [];
    var total = 0;
    var mismatched = [];
    (members || []).forEach(function (m) {
      if (m.programId && m.programId !== programId) {
        mismatched.push({ member: m.name || m.customerId,
                          programId: m.programId });
        return;
      }
      contributions.push({ member: m.name || m.customerId, points: m.points });
      total += m.points;
    });
    if (mismatched.length) {
      return { ok: false,
               why: 'every contribution must be under the same programme; ' +
                    'pooling across programmes would merge two sets of terms',
               mismatched: mismatched };
    }
    var remaining = Math.max(0, target - total);
    return {
      ok: true,
      programId: programId,
      contributions: contributions,
      total: total,
      target: target,
      remaining: remaining,
      /* D11's vocabulary, applied to a group. "Family Journey Goal —
         9,000 / 10,000 TP", never a combined balance. */
      funded: remaining === 0 && target > 0,
      display: total + ' / ' + target + ' TP',
      state: remaining === 0 && target > 0 ? 'FUNDED' : 'PLANNING',
      note: 'A shared view of points each person holds separately. Nothing ' +
            'has been transferred and no joint holding exists.'
    };
  }

  return {
    TRANSFER_TYPES: TRANSFER_TYPES,
    propose: propose,
    conserves: conserves,
    pool: pool
  };
});
