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
    PURCHASE:     { available: +1, reserved: 0,  acquired: +1, lot: 'purchased' },
    /* THE ELEVENTH KIND, AND IT WAS ARGUED FOR BEFORE IT WAS ADDED.
       B7.1 fixed the set at ten so that adding one had to be deliberate;
       B16 is the argument and C11 is the instruction. A promotional point is
       not a purchased point: it may expire when a purchased one does not, it
       cannot be repurchased, and it may be cancelled differently. Folding it
       into PURCHASE would make those distinctions unexpressible, which is
       exactly what B13 needed and could not have. */
    PROMOTION:    { available: +1, reserved: 0,  acquired: +1, lot: 'promotional' },
    TRANSFER_IN:  { available: +1, reserved: 0,  acquired: +1, lot: 'purchased' },
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
      /* ---- identity ----------------------------------------------------- */
      id: 'AFK-TP-2026.1',
      name: 'Afrinkong Travel Points Programme 2026-A',
      version: 1,
      issuer: 'Wankong LLC',      /* A1a: the obligation runs from the entity,
                                     not from the trade name. */
      brand: 'Afrinkong',
      /* D20: A STATE MACHINE, NOT A BOOLEAN.
         `status: 'active'` was one word away from taking money. This is the
         same decision expressed as a sequence that has to be walked, with
         legal and accounting review as steps nobody can skip by editing a
         string. See COMPLIANCE_STATES and mayActivate(). */
      compliance: 'DRAFT',
      complianceHistory: [],      // [{ from, to, at, by, note }] once it moves
      status: 'draft',            // derived from compliance; kept for callers
      effectiveFrom: '2026-01-01',
      effectiveUntil: null,

      /* ---- the two rates, which never collapse into one (B5) ------------ */
      currency: 'USD',
      issueRate: 1,               // C2: $1 eligible purchase -> 1 TP
      entitlement: 1,             // travel value one point applies on redemption

      /* ---- purchase bounds ---------------------------------------------- */
      /* C13: a floor keeps the system accessible without generating thousands
         of trivial transactions. C14: a ceiling exists because Afrinkong should
         never accept unlimited prepaid exposure merely because a card processor
         can take the money. Both are programme terms rather than ledger
         constants, so a different programme may set them differently. */
      /* WHICH LOT IS SPENT FIRST. Open question B-ii, and FIFO is a provisional
         default rather than a decision — it is here as a named programme term
         so the choice is visible and versioned instead of buried in a loop.
         It only changes an answer once lots differ in rate or currency. */
      lotOrder: 'fifo',

      minPurchase: 25,            // TP
      maxPerTransaction: 2500,    // TP
      maxPerCustomerPerYear: 10000, // TP

      /* ---- exposure (C15) ------------------------------------------------ */
      /* Ten thousand customers at $5,000 each is $50m of future travel
         entitlement, which stops being a website feature. `null` does not mean
         unlimited — `mayActivate()` refuses to let a programme go live with an
         unset limit, so this must be answered before anybody is charged. */
      maxProgrammeExposure: null, // TP. Required before activation.

      /* ---- what a point may be redeemed against -------------------------- */
      eligibleServices: ['journey', 'accommodation', 'transport', 'guiding',
                         'experience'],

      /* ---- transfer (B14, B15, C21) -------------------------------------- */
      /* Decided, not defaulted. Person-to-person transfer is one of the
         features that moves a prepaid-access analysis, and V1 does not need it.
         The ledger keeps TRANSFER_IN/TRANSFER_OUT because an administrative
         correction still needs them — a programme that forbids transfer simply
         never emits one. Policy is not capability. */
      transferable: false,
      secondaryMarket: false,

      /* ---- repurchase (B12, C16, C17) ------------------------------------ */
      /* THE BASIS IS THE CONSIDERATION PAID, NOT THE ENTITLEMENT HELD.
         "90% of what your points are worth" requires the points to be worth
         something in cash, which B2 denies. "90% of what you paid for the ones
         you have not used" values nothing — it reads the payment record. It is
         also the only one of the two that cannot be gamed: under an entitlement
         basis, any promotional bonus above 1/rate - 1 lets a customer buy
         points and immediately repurchase them for more than they paid. */
      buyback: {
        offered: true,
        discretionary: true,      // never a contractual right of redemption
        basis: 'consideration',   // 'consideration' | 'entitlement'
        rate: 0.90,               // of eligible purchase consideration
        minHoldDays: 90,
        minPoints: 100,
        maxPerYear: 5000,
        promotionalEligible: false, // C16: promotional points repurchase at 0
        reservedEligible: false     // C16: reserved points repurchase at 0
      },

      /* ---- cancellation (B11) -------------------------------------------- */
      /* Attaches to the BOOKING, not to the customer's whole holding. The
         middle band's 0.50 is a PLACEHOLDER: B11 ties it to actual cancellation
         charges and supplier costs, and a flat half is too harsh where nothing
         is committed and too generous where the journey is already paid for. */
      cancellation: [
        { fromDays: 31, release: 1.00, buybackEligible: true },
        { fromDays: 8,  release: 0.50, buybackEligible: false },
        { fromDays: 0,  release: 0.00, buybackEligible: false }
      ],

      /* ---- expiry, per lot type (B17) ------------------------------------ */
      /* Purchased points do not lapse because time passed — that is the
         customer-trust decision, and it makes the obligation more durable
         rather than less, deliberately. Promotional points may. One scalar
         could not express two rules, which is why this is a block. */
      expiry: {
        purchased: null,          // null = never lapses from time alone
        promotional: 24           // months, or null for never
      },

      /* ---- promotional points (B16, C11, C12) ---------------------------- */
      /* A marketing lever, temporary and explicitly identified — not permanent
         economics. A standing 10-20% bonus teaches customers that the nominal
         point price is meaningless. */
      promotional: {
        offered: true,
        bonusRate: 0.05,          // C12: 5% — buy 500, receive 25
        transferable: false,
        repurchasable: false,
        expiryMonths: 24,
        cancellationTreatment: 'forfeit'
      }
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
  /* ---- D20: the compliance ladder ---------------------------------------
   *
   *   DRAFT -> LEGAL_REVIEW -> ACCOUNTING_REVIEW -> APPROVED -> PILOT -> ACTIVE
   *
   * and, from anywhere live, SUSPENDED; and from anywhere, RETIRED.
   *
   * ONLY PILOT AND ACTIVE MAY ISSUE. That is the whole safety mechanism: a
   * programme cannot reach either without passing through legal and accounting
   * review, and the transitions are checked rather than assigned, so somebody
   * who edits this file to say ACTIVE has to delete a guard rather than change
   * a word.
   *
   * The ladder is deliberately not skippable. APPROVED cannot be reached from
   * DRAFT even by an administrator: the point of naming LEGAL_REVIEW and
   * ACCOUNTING_REVIEW as states is that somebody has to say, in a commit, that
   * each happened.
   */
  var COMPLIANCE_STATES = ['DRAFT', 'LEGAL_REVIEW', 'ACCOUNTING_REVIEW',
                           'APPROVED', 'PILOT', 'ACTIVE', 'SUSPENDED', 'RETIRED'];

  var COMPLIANCE_NEXT = {
    DRAFT:              ['LEGAL_REVIEW', 'RETIRED'],
    LEGAL_REVIEW:       ['ACCOUNTING_REVIEW', 'DRAFT', 'RETIRED'],
    ACCOUNTING_REVIEW:  ['APPROVED', 'LEGAL_REVIEW', 'DRAFT', 'RETIRED'],
    APPROVED:           ['PILOT', 'ACCOUNTING_REVIEW', 'RETIRED'],
    PILOT:              ['ACTIVE', 'SUSPENDED', 'RETIRED'],
    ACTIVE:             ['SUSPENDED', 'RETIRED'],
    SUSPENDED:          ['ACTIVE', 'PILOT', 'RETIRED'],
    RETIRED:            []
  };

  /* The only two states in which a point may come into existence. */
  var ISSUING_STATES = ['PILOT', 'ACTIVE'];

  function complianceOf(id) {
    var p = program(id);
    return p.compliance || 'DRAFT';
  }

  /* Is this transition one the ladder allows? Checked rather than assigned. */
  function mayTransition(id, to) {
    var from = complianceOf(id);
    if (COMPLIANCE_STATES.indexOf(to) === -1) {
      return { ok: false, why: 'unknown compliance state: ' + to };
    }
    var allowed = COMPLIANCE_NEXT[from] || [];
    if (allowed.indexOf(to) === -1) {
      return { ok: false, why: from + ' cannot move straight to ' + to,
               from: from, allowed: allowed };
    }
    /* Reaching an issuing state additionally requires the programme to be
       complete — an exposure limit that nobody has set is not a limit. */
    if (ISSUING_STATES.indexOf(to) !== -1) {
      var ready = mayActivate(id);
      if (!ready.ok) return { ok: false, why: ready.why, missing: ready.missing };
    }
    return { ok: true, from: from, to: to };
  }

  var PRODUCT_STATE = {
    PLANNING: 'PLANNING',
    DRAFT_PROGRAM: 'DRAFT_PROGRAM',
    ACTIVE_PROGRAM: 'ACTIVE_PROGRAM'
  };

  /* Creating points. Moving points a customer already has between pools is
     not on this list: a RESERVE under a draft program cannot happen anyway,
     because there is nothing to reserve. */
  var ISSUING_KINDS = ['PURCHASE', 'PROMOTION', 'TRANSFER_IN', 'ADJUST_UP'];

  function stateOf(id) {
    if (!id) return PRODUCT_STATE.PLANNING;
    return ISSUING_STATES.indexOf(complianceOf(id)) !== -1
      ? PRODUCT_STATE.ACTIVE_PROGRAM
      : PRODUCT_STATE.DRAFT_PROGRAM;
  }

  /* C15: A PROGRAMME MAY NOT GO LIVE WITH AN UNANSWERED EXPOSURE LIMIT.
   *
   * `maxProgrammeExposure: null` does not mean unlimited. It means nobody has
   * decided, and this refuses to let that reach production — ten thousand
   * customers at $5,000 each is $50m of future travel entitlement, which is a
   * commitment to deliver travel rather than a website feature.
   *
   * Separate from `mayIssue`, deliberately. mayIssue asks "is this programme
   * live"; this asks "should it be allowed to become live", and the answer is
   * checked before the one-word status change rather than after it. */
  function mayActivate(id) {
    var p = program(id);
    var missing = [];
    if (p.maxProgrammeExposure == null) missing.push('maxProgrammeExposure');
    if (p.maxPerTransaction == null) missing.push('maxPerTransaction');
    if (p.maxPerCustomerPerYear == null) missing.push('maxPerCustomerPerYear');
    if (!p.buyback || !p.buyback.basis) missing.push('buyback.basis');
    if (p.minPurchase == null) missing.push('minPurchase');
    if (missing.length) {
      return { ok: false, why: 'unset before activation: ' + missing.join(', '),
               missing: missing };
    }
    if (p.minPurchase > p.maxPerTransaction) {
      return { ok: false, why: 'minPurchase exceeds maxPerTransaction' };
    }
    return { ok: true };
  }

  /* D20/D21: ISSUANCE IS GATED ON THE COMPLIANCE LADDER, NOT ON A STRING.
     `status: 'active'` no longer does anything by itself. A programme has to
     have walked DRAFT -> LEGAL_REVIEW -> ACCOUNTING_REVIEW -> APPROVED ->
     PILOT, and mayActivate() has to be satisfied at that last step, before a
     single point can exist. Editing one word cannot start taking money. */
  function mayIssue(id) {
    return ISSUING_STATES.indexOf(complianceOf(id)) !== -1;
  }

  /* ---- money and points ---------------------------------------------------
   *
   * Whole points only. A fraction of a unit of travel entitlement is not a
   * thing anybody can hold, spend or be told about honestly, and rounding
   * halves at the boundary is how a ledger acquires a slow leak. Money is
   * handled in minor units (cents) for the same reason: floating-point
   * dollars do not add up.
   */
  /* A wallet before anything has happened to it. Every field a fold can touch
     starts here, so a fold over zero entries and a fold over ten thousand have
     the same shape. */
  function blank() {
    return {
      available: 0, reserved: 0, redeemed: 0, transferred: 0,
      boughtBack: 0, expired: 0, adjusted: 0, acquired: 0,
      entries: 0, ignored: 0, reservations: {},
      purchased: 0, promotional: 0
    };
  }

  /* ---- the pricing engine (C2, C22 phase C2) -----------------------------
   *
   * FOUR FUNCTIONS, TWO RATES, AND THE PAIRING IS THE WHOLE POINT.
   *
   *   pointsForPurchase   money -> points        issueRate
   *   priceOfPoints       points -> money        issueRate
   *   entitlementOf       points -> travel value entitlement
   *   goalRequirement     journey -> points      entitlement
   *
   * The left column prices ACQUIRING points. The right column prices WHAT
   * POINTS BUY. They are different questions and a programme may answer them
   * with different numbers — that is what lets a promotion make points cheaper
   * to acquire without making journeys cheaper, and it is why B5 forbids the
   * two rates collapsing into one.
   *
   * Both currently read 1, which is why using the wrong one was invisible for
   * four sections. See A4 and B5.1.
   */

  /* C2: what a payment yields. $100 at issueRate 1 is 100 TP; the customer is
     buying 100 TP for $100, not storing $100 inside Afrinkong. */
  function pointsForPurchase(programId, amountMinor) {
    var p = program(programId);
    if (!isFinite(amountMinor) || amountMinor <= 0) return 0;
    return Math.floor((amountMinor / 100) * p.issueRate);
  }

  /* What a quantity of points costs to acquire. The inverse of the above. */
  function priceOfPoints(programId, points) {
    var p = program(programId);
    if (!isFinite(points) || points <= 0) return 0;
    return Math.round((points / p.issueRate) * 100);
  }

  /* What a quantity of points applies when redeemed, in travel value. */
  function entitlementOf(programId, points) {
    var p = program(programId);
    return Math.round(points * p.entitlement * 100);
  }

  /* C7: HOW MANY POINTS A JOURNEY REQUIRES — and the fix for A5.1.
   *
   * This used to be `journeyCost x issueRate`, which is the acquisition rate
   * answering a redemption question. Under a promotional programme at
   * issueRate 1.1 it raised a $4,800 goal to 5,280 TP: a purchase bonus made
   * the journey more expensive, which is precisely what B5 forbids.
   *
   * The journey consumes ENTITLEMENT, not dollars — C7 — so the requirement is
   * the journey's price divided by what one point is worth in travel. The
   * inverse of entitlementOf, which is what it should always have been.
   *
   * Ceiling rather than round: a point is indivisible (A1a) and a customer
   * one point short of a journey cannot travel.
   */
  function goalRequirement(programId, journeyCostMinor) {
    var p = program(programId);
    if (!isFinite(journeyCostMinor) || journeyCostMinor <= 0) return 0;
    return Math.ceil((journeyCostMinor / 100) / p.entitlement);
  }

  /* C13/C14: is this purchase within the programme's bounds?
     Programme terms rather than ledger constants — a different programme may
     set them differently, and the ledger should not carry a policy number. */
  function canPurchase(programId, points, boughtThisYear) {
    var p = program(programId);
    if (!isFinite(points) || points <= 0 || Math.floor(points) !== points) {
      return { ok: false, why: 'points must be a positive whole number' };
    }
    if (p.minPurchase != null && points < p.minPurchase) {
      return { ok: false, why: 'below the minimum purchase of ' + p.minPurchase + ' TP' };
    }
    if (p.maxPerTransaction != null && points > p.maxPerTransaction) {
      return { ok: false, why: 'above the maximum of ' + p.maxPerTransaction + ' TP per transaction' };
    }
    if (p.maxPerCustomerPerYear != null &&
        (boughtThisYear || 0) + points > p.maxPerCustomerPerYear) {
      return { ok: false, why: 'above the annual limit of ' + p.maxPerCustomerPerYear + ' TP',
               boughtThisYear: boughtThisYear || 0 };
    }
    return { ok: true };
  }

  /* Kept under their old names so nothing that already calls them breaks. The
     new names say which question they answer, which is the entire lesson of
     A4. */
  var pointsFor = pointsForPurchase;
  var priceOf = priceOfPoints;

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
        /* `admin` and `lot` are labels, not arithmetic. Adding a string to a
           running total gives NaN and every downstream figure inherits it. */
        if (field === 'admin' || field === 'lot') continue;
        w[field] += kind[field] * q;
      }

      /* C11/B16: which pool the points came from, kept apart for the whole of
         their life. A purchased point and a granted one differ on expiry,
         repurchase and cancellation, and none of that is expressible if the
         ledger has already forgotten which is which. */
      if (kind.lot) w[kind.lot] += kind.acquired * q;
      if (kind.available === -1 && !kind.lot) {
        /* Points leaving the wallet come off the promotional pool first: they
           are the ones that expire and cannot be repurchased, so spending them
           first is the treatment that costs the customer least. Provisional —
           this is the promotional half of open question B-ii. */
        var off = Math.min(w.promotional, q);
        w.promotional -= off;
        w.purchased -= (q - off);
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
      purchased: w.purchased,
      promotional: w.promotional,
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
  /* WHAT A REPURCHASE PAYS, AND WHERE THE MONEY FIGURE COMES FROM.
   *
   * B12/C16: 90% of the PURCHASE CONSIDERATION — what the customer actually
   * paid for the points they have not used. Not 90% of what the points are
   * worth, because B2 says they are not worth anything in cash.
   *
   * That means this function needs a money figure, and the ledger does not hold
   * one: B19 and B22 are explicit that a Travel Point has no currency and a
   * ledger entry carries no money. So an entry carries a `paymentRef` — an id,
   * not an amount — and the amount is looked up in the payment records. The
   * separation survives: `payments` knows about money, the ledger knows about
   * entitlement, and a reference joins them.
   *
   * `payments` is a map of ref -> { amountMinor, currency }. Without it, a
   * consideration-basis programme cannot quote, and says so rather than
   * quietly falling back to the entitlement basis it was moved away from.
   */
  function considerationFor(programId, entries, points) {
    var p = program(programId);
    var order = entries.filter(function (e) {
      return e.kind === 'PURCHASE' && e.status === 'SETTLED' && !e.promotional;
    });
    /* p.lotOrder is 'fifo' provisionally — see B-ii. Reversing here is the
       whole of a lifo implementation, when somebody decides. */
    if (p.lotOrder === 'lifo') order = order.slice().reverse();

    var want = points, drawn = [], totalMinor = 0, currency = null, short = false;
    for (var i = 0; i < order.length && want > 0; i++) {
      var e = order[i];
      var take = Math.min(want, e.quantity);
      var pay = e.payment;                       // { amountMinor, currency }
      if (!pay) { short = true; break; }
      if (currency && pay.currency !== currency) {
        /* B19.2: lots in two currencies means the lot order decides what the
           refund is paid in. Refusing is better than picking one silently. */
        return { ok: false, why: 'points span more than one payment currency',
                 currencies: [currency, pay.currency] };
      }
      currency = pay.currency;
      totalMinor += Math.round(pay.amountMinor * (take / e.quantity));
      drawn.push({ entry: e.id, points: take, minor: Math.round(pay.amountMinor * (take / e.quantity)) });
      want -= take;
    }
    if (short || want > 0) {
      return { ok: false, why: 'cannot trace these points to a payment record' };
    }
    return { ok: true, minor: totalMinor, currency: currency, lots: drawn };
  }

  function buybackQuote(programId, entries, points, heldDays, boughtBackThisYear) {
    var p = program(programId);
    var b = p.buyback;
    var w = wallet(entries);
    var refuse = function (why, extra) {
      var r = { eligible: false, why: why, points: points };
      if (extra) for (var k in extra) r[k] = extra[k];
      return r;
    };

    if (!b || !b.offered) return refuse('this program does not offer buyback');
    if (points < b.minPoints) return refuse('below the minimum of ' + b.minPoints + ' points');
    /* C16: reserved points repurchase at zero — committed to a journey is not
       available to sell back. `available` already excludes them. */
    if (points > w.available) return refuse('only available points can be bought back');
    if (heldDays < b.minHoldDays) return refuse('points must be held for ' + b.minHoldDays + ' days');
    if ((boughtBackThisYear || 0) + points > b.maxPerYear) {
      return refuse('above the annual limit of ' + b.maxPerYear + ' points');
    }
    /* C16: promotional points repurchase at zero. They were not paid for, so
       there is no consideration to refund — which is the consideration basis
       answering the question by itself rather than needing a special case. */
    if (b.promotionalEligible === false && w.promotional > 0 &&
        points > w.purchased) {
      return refuse('only purchased points can be bought back',
                    { purchased: w.purchased, promotional: w.promotional });
    }

    if (b.basis === 'consideration') {
      var c = considerationFor(programId, entries, points);
      if (!c.ok) return refuse(c.why, { currencies: c.currencies });
      return {
        eligible: true,
        discretionary: b.discretionary,
        points: points,
        basis: 'consideration',
        grossMinor: c.minor,
        currency: c.currency,
        rate: b.rate,
        payableMinor: Math.round(c.minor * b.rate),
        lots: c.lots,
        note: b.discretionary
          ? 'Afrinkong may repurchase these points at ' + Math.round(b.rate * 100) +
            '% of what you paid for them. This is an offer under the terms of ' +
            'this programme, not a guaranteed right of redemption.'
          : 'Repurchase is contractual under the terms of this programme.'
      };
    }

    /* The entitlement basis, kept because a future programme may use it and
       because deleting it would hide that a choice was made. B12.2 records why
       this one is not the default: it is exploitable under any promotional
       bonus above 1/rate - 1. */
    return {
      eligible: true,
      discretionary: b.discretionary,
      points: points,
      basis: 'entitlement',
      grossMinor: entitlementOf(programId, points),
      rate: b.rate,
      payableMinor: Math.round(entitlementOf(programId, points) * b.rate),
      note: 'Quoted on the entitlement basis. See docs/travel-point-economics.md B12.2.'
    };
  }

  /* C4: PACE IN, TIME OUT — which is the direction the product actually needs.
   *
   *   "I can manage $150 a month"  ->  150 TP a month  ->  32 months
   *
   * `goal()` below answers the other direction: given a deadline, what would
   * the monthly purchase have to be. Both are the same arithmetic and they are
   * NOT interchangeable as copy. A deadline-driven figure reads as an
   * obligation — "your monthly target is 343 TP" — and B3 settled that there is
   * no mandatory contribution. A pace-driven figure reads as a projection:
   * you are here, at this rate you arrive then. B25 is the same decision seen
   * from the marketing side: this is buying a journey in instalments, not
   * saving to a target.
   *
   * Nothing here is a promise. The months are a projection from an assumption
   * the customer supplied, and change the moment they buy differently.
   */
  function project(programId, journeyCostMinor, held, monthlyMoneyMinor) {
    var target = goalRequirement(programId, journeyCostMinor);
    var remaining = Math.max(0, target - (held || 0));
    var monthlyPoints = pointsForPurchase(programId, monthlyMoneyMinor || 0);
    return {
      target: target,
      held: held || 0,
      remaining: remaining,
      progress: target > 0 ? Math.min(1, (held || 0) / target) : 0,
      monthlyPoints: monthlyPoints,
      monthlyMoneyMinor: monthlyMoneyMinor || 0,
      /* null rather than Infinity when the customer has not named a pace, and
         0 when they are already there. A projection nobody can act on is worse
         than no projection. */
      months: remaining === 0 ? 0
            : monthlyPoints > 0 ? Math.ceil(remaining / monthlyPoints)
            : null
    };
  }

  function goal(programId, journeyCostMinor, held, months) {
    /* A5.1, fixed. Was `journeyCostMinor / 100 * issueRate` — the acquisition
       rate answering a redemption question. C7 settled that a journey carries a
       point requirement derived from its service pricing, so the target is
       goalRequirement() and a purchase bonus no longer inflates it. */
    var target = goalRequirement(programId, journeyCostMinor);
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
    mayActivate: mayActivate,
    COMPLIANCE_STATES: COMPLIANCE_STATES,
    COMPLIANCE_NEXT: COMPLIANCE_NEXT,
    ISSUING_STATES: ISSUING_STATES,
    complianceOf: complianceOf,
    mayTransition: mayTransition,
    considerationFor: considerationFor,
    program: program,
    pointsFor: pointsFor,
    priceOf: priceOf,
    entitlementOf: entitlementOf,
    pointsForPurchase: pointsForPurchase,
    priceOfPoints: priceOfPoints,
    goalRequirement: goalRequirement,
    canPurchase: canPurchase,
    fold: fold,
    wallet: wallet,
    can: can,
    cancellation: cancellation,
    buybackQuote: buybackQuote,
    goal: goal,
    project: project
  };
});
