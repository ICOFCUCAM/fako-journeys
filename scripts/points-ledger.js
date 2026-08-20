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
      entitlementRate: 1,         // eligible travel entitlement one point provides

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

      /* ---- repurchase (E1-E6) --------------------------------------------
         THE BASIS IS A PROGRAMME TERM, NOT A DEFINITION.
         E2 is explicit that this must not be described as "90% of the money
         you paid": deposit $5,000, wait, withdraw $4,500 is a different
         product with a different characterisation, and a basis hard-coded to
         the purchase price makes the product that whether or not the terms say
         so. So `basis` names which rule THIS programme applies and the quote
         says which it used.
         B12.2's concern survives the change as a rail rather than as the
         definition: `maxPayableIsConsideration` caps any quote at what the
         customer actually paid, under EVERY basis. That closes the arbitrage —
         a promotional bonus can never be extracted as cash — without turning
         repurchase into a refund. */
      buyback: {
        offered: true,
        discretionary: true,      // never a contractual right of redemption
        basis: 'consideration',   // 'consideration' | 'entitlement' | 'programme'
        /* Never pay out more than came in, whatever the basis says. */
        maxPayableIsConsideration: true,
        rate: 0.90,               // of eligible purchase consideration
        minHoldDays: 90,
        minPoints: 100,
        /* C5: TWO SHAPES OF ANNUAL LIMIT, AND THEY BEHAVE DIFFERENTLY.
           An absolute cap bites hardest on the largest holders — 5,000 TP is
           all of a small holding and a tenth of a large one. A percentage cap
           scales, which is what "no more than X% of their eligible unreserved
           points" asks for. Both are supported and whichever is tighter binds;
           `maxPctPerYear: null` means only the absolute cap applies. Neither
           number is settled — C-limits. */
        maxPerYear: 5000,
        maxPctPerYear: null,      // e.g. 0.25 for 25% of eligible holdings
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
        /* F3: AND THIS IS THE ONLY PLACE A VOLUME INCENTIVE MAY LIVE.
           A bigger purchase may earn a bigger GRANT. It may not earn a better
           `issueRate`, because that would give a point a different money price
           in each tranche and a thing with a price per tranche is a currency.
           See F2. `null` means the flat `bonusRate` applies at every size;
           an array of { fromPoints, bonusRate } sets a ladder. Nobody has
           decided whether a ladder is wanted — F-c. */
        tiers: null,
        transferable: false,
        repurchasable: false,
        expiryMonths: 24,
        cancellationTreatment: 'forfeit'
      }
    }
  };

  /* ---- B4/B7: TERMS ARE IMMUTABLE, IN THE MODULE AND NOT ONLY IN THE SCHEMA
   *
   * `point_programs` refuses an UPDATE to issue_rate, entitlement_rate,
   * buyback or cancellation. That protects the database and does nothing for
   * the module — and the module is what runs in a browser and in every test.
   * Until this, `PROGRAMS['AFK-TP-2026.1'].entitlementRate = 99` simply worked.
   *
   * Frozen deeply, because the interesting terms are nested: a shallow freeze
   * leaves buyback.rate writable, which is the one somebody would reach for.
   *
   * WHAT-IF WITHOUT MUTATION. Asking "what would a 25% bonus do" is a fair
   * question and the answer must not be "edit the live programme". `variant()`
   * registers a NEW programme built from an old one, which is also exactly what
   * B18 requires of a real change: you do not rewrite 2026-A, you publish
   * 2027-B. The test suite and a future promotion take the same door.
   */
  function deepFreeze(o) {
    Object.getOwnPropertyNames(o).forEach(function (k) {
      var v = o[k];
      if (v && typeof v === 'object' && !Object.isFrozen(v)) deepFreeze(v);
    });
    return Object.freeze(o);
  }

  function variant(baseId, overrides, newId) {
    var base = program(baseId);
    var id = newId || (baseId + '~' + (Object.keys(PROGRAMS).length + 1));
    var next = {};
    Object.keys(base).forEach(function (k) { next[k] = base[k]; });
    Object.keys(overrides || {}).forEach(function (k) { next[k] = overrides[k]; });
    next.id = id;
    PROGRAMS[id] = deepFreeze(next);
    return id;
  }

  function program(id) {
    var p = PROGRAMS[id];
    if (!p) throw new Error('unknown point program: ' + id);
    return p;
  }

  /* Frozen at load. Anything that needs different terms asks for a variant. */
  Object.keys(PROGRAMS).forEach(function (k) { deepFreeze(PROGRAMS[k]); });

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
                           'APPROVED', 'PILOT', 'ACTIVE',
                           /* E10: a programme stops SELLING long before it
                              stops OWING. Points already issued do not vanish
                              because new ones are no longer offered, so
                              closure is a sequence with a redemption period in
                              it rather than an off switch. */
                           'CLOSED_TO_NEW_PURCHASES', 'REDEMPTION_PERIOD',
                           'CLOSED', 'SUSPENDED', 'RETIRED'];

  var COMPLIANCE_NEXT = {
    DRAFT:              ['LEGAL_REVIEW', 'RETIRED'],
    LEGAL_REVIEW:       ['ACCOUNTING_REVIEW', 'DRAFT', 'RETIRED'],
    ACCOUNTING_REVIEW:  ['APPROVED', 'LEGAL_REVIEW', 'DRAFT', 'RETIRED'],
    APPROVED:           ['PILOT', 'ACCOUNTING_REVIEW', 'RETIRED'],
    PILOT:              ['ACTIVE', 'CLOSED_TO_NEW_PURCHASES', 'SUSPENDED', 'RETIRED'],
    ACTIVE:             ['CLOSED_TO_NEW_PURCHASES', 'SUSPENDED', 'RETIRED'],
    CLOSED_TO_NEW_PURCHASES: ['REDEMPTION_PERIOD', 'ACTIVE', 'SUSPENDED'],
    REDEMPTION_PERIOD:  ['CLOSED', 'SUSPENDED'],
    /* CLOSED is not RETIRED. Closed means the redemption period ran and the
       programme's own terms say what became of anything outstanding; retired
       means it never traded. Collapsing them would lose the difference between
       "settled" and "never happened". */
    CLOSED:             ['RETIRED'],
    SUSPENDED:          ['ACTIVE', 'PILOT', 'RETIRED'],
    RETIRED:            []
  };

  /* The only two states in which a point may come into existence. */
  var ISSUING_STATES = ['PILOT', 'ACTIVE'];

  /* E10: and the states in which one may still be SPENT. A programme that has
     stopped selling still owes travel to everybody holding its points, and
     refusing redemption the moment sales stop would be the silent deletion
     E9 forbids. */
  var REDEEMING_STATES = ['PILOT', 'ACTIVE', 'CLOSED_TO_NEW_PURCHASES',
                          'REDEMPTION_PERIOD'];

  function mayRedeem(id) {
    return REDEEMING_STATES.indexOf(complianceOf(id)) !== -1;
  }

  /* E4: AND THE STATES IN WHICH A POINT MAY BE BOUGHT BACK.
   *
   * The same set as redemption, and that is an argument rather than a
   * coincidence: repurchase is a way of discharging the obligation a point
   * represents, so a programme that may still honour a point may still buy one
   * back, and one that may not, may not.
   *
   * The consequence worth naming is the draft one. `AFK-TP-2026.1` is DRAFT,
   * so `buybackQuote()` refuses outright — a draft programme cannot quote a
   * repurchase any more than it can issue a point, and a quote is the half of
   * this that would otherwise look harmless enough to wire to a button. */
  function mayBuyBack(id) {
    return REDEEMING_STATES.indexOf(complianceOf(id)) !== -1;
  }

  /* D4: CLOSING A PROGRAMME MUST NEVER BE A WAY OF CANCELLING WHAT IS OWED.
   *
   * This is the strongest rule in Decision D and it needs to be a refusal
   * rather than a promise. `CLOSED` is the one state in which points can
   * neither be redeemed nor bought back — so a programme reaching it while
   * customers still hold points is confiscation, whatever the reason given.
   *
   * So the transition is gated on the outstanding balance. A programme with
   * anything outstanding may go to CLOSED_TO_NEW_PURCHASES (stop selling) and
   * to REDEMPTION_PERIOD (run-off), which is the whole point of those two
   * states existing — but not to CLOSED.
   *
   * `outstanding` is supplied by the caller because this module has no
   * database. Passing 0 when it is not 0 is possible, and is the reason the
   * argument is named rather than inferred: somebody has to state the number.
   */
  function mayClose(id, outstandingPoints) {
    if (outstandingPoints == null) {
      return { ok: false, why: 'the outstanding balance must be stated before ' +
                              'a programme may close; it cannot be assumed zero' };
    }
    if (outstandingPoints > 0) {
      return { ok: false,
               why: 'programme ' + id + ' still has ' + outstandingPoints +
                    ' TP outstanding. Closing a programme does not cancel ' +
                    'what it owes — move to REDEMPTION_PERIOD and run off.',
               outstanding: outstandingPoints };
    }
    return { ok: true };
  }

  function complianceOf(id) {
    var p = program(id);
    return p.compliance || 'DRAFT';
  }

  /* Is this transition one the ladder allows? Checked rather than assigned. */
  function mayTransition(id, to, opts) {
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
    /* D4: and reaching CLOSED requires that nothing is still owed. */
    if (to === 'CLOSED') {
      var clear = mayClose(id, (opts || {}).outstanding);
      if (!clear.ok) {
        return { ok: false, why: clear.why, outstanding: clear.outstanding };
      }
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

  /* The two that move points between people rather than between pools. E8. */
  var TRANSFER_KINDS = ['TRANSFER_IN', 'TRANSFER_OUT'];

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
    /* F2: ONE RATE, OR THE PROGRAMME DOES NOT GO LIVE.
       A tiered `issueRate` — an array, a map of bands, anything but a single
       finite number — gives a point a different money price in each tranche,
       and that is the step that turns entitlement into currency. A volume
       incentive belongs in `promotional.tiers`, which grants extra points
       rather than repricing them. Checked here so it cannot be reached by
       editing a term. */
    if (typeof p.issueRate !== 'number' || !isFinite(p.issueRate) ||
        p.issueRate <= 0) {
      return { ok: false, why: 'issueRate must be a single positive number: a ' +
                              'rate that varies by tranche gives a point a price',
               missing: ['issueRate'] };
    }
    if (typeof p.entitlementRate !== 'number' || !isFinite(p.entitlementRate) ||
        p.entitlementRate <= 0) {
      return { ok: false, why: 'entitlementRate must be a single positive number',
               missing: ['entitlementRate'] };
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
      entries: 0, ignored: 0, reservations: {}, corrections: [],
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
    return Math.round(points * p.entitlementRate * 100);
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
    return Math.ceil((journeyCostMinor / 100) / p.entitlementRate);
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

  /* ---- Decision B6: nothing is issued before the money has settled --------
   *
   * THE FIVE STAGES A PAYMENT PASSES THROUGH, AND THE ONE THAT ISSUES.
   *
   *   checkout session created   nothing has happened
   *   customer clicked Pay       nothing has happened
   *   authorised                 the bank has agreed to pay; it has not paid
   *   requires_capture           we have not asked for the money yet
   *   settled                    THE MONEY IS OURS.   <- points exist here
   *   failed / refunded / charged_back   it was never ours, or is not now
   *
   * The interesting boundary is `authorised`, because it is the one that looks
   * finished. An authorisation is a promise that can be withdrawn, and points
   * issued against one are entitlement created against money that never
   * arrived. Naming the states rather than testing `if (paid)` is what makes
   * that distinction survive the next person to read this.
   *
   * Mirrors `payments.status` in tools/points/schema.sql. If one gains a state
   * the other must, and a check asserts they agree.
   */
  var PAYMENT_STATES = ['pending', 'requires_capture', 'authorised', 'settled',
                        'failed', 'refunded', 'charged_back'];
  var ISSUING_PAYMENT_STATES = ['settled'];

  function maySettleIssuance(paymentStatus) {
    return ISSUING_PAYMENT_STATES.indexOf(String(paymentStatus)) !== -1;
  }

  /* B9: A REVERSAL IS AN ENTRY, NEVER AN EDIT.
   *
   * A chargeback three months after the fact does not travel back in time and
   * un-issue points. It is a new economic event, and the history has to keep
   * both: the customer did buy 1,100 points on 3 March, and the payment was
   * reversed on 7 June. Editing the first to make the second true destroys the
   * only record of what actually happened, which is the record a dispute is
   * answered from.
   *
   * Returns the compensating entries a reversal implies. Appends nothing.
   *
   * THE HARD CASE IS REPORTED, NOT DECIDED. If the customer has already spent
   * the points, the compensating entry would overdraw the wallet — and what
   * should happen then (pursue the debt, void the booking, absorb it) is a
   * legal and commercial question, not an arithmetic one. This says so and
   * hands back the shortfall rather than picking. B-recovery in the doc.
   */
  function reversal(programId, entries, originalEntryId, reason) {
    var original = null;
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].id === originalEntryId) { original = entries[i]; break; }
    }
    if (!original) {
      return { ok: false, why: 'no entry ' + originalEntryId + ' in this ledger' };
    }
    if (ISSUING_KINDS.indexOf(original.kind) === -1) {
      return { ok: false, why: 'only an issuance can be reversed; ' +
                              original.kind + ' is not one' };
    }
    var w = wallet(entries);
    var q = original.quantity;
    var shortfall = Math.max(0, q - w.available);
    return {
      ok: true,
      /* ADJUST_DOWN rather than a new kind. B7.1 fixed the set of kinds so
         that adding one has to be argued for, and a reversal is an
         administrative removal — which is exactly what ADJUST_DOWN is. The
         `corrects` pointer is what makes it a reversal rather than an
         unexplained deduction. */
      entries: [{
        kind: 'ADJUST_DOWN',
        quantity: q,
        status: 'SETTLED',
        programVersion: original.programVersion,
        corrects: original.id,
        reason: reason || 'payment reversed',
        /* B9: a reversal is an exceptional entry and needs a named human.
           The schema enforces it; the caller supplies it. */
        approvedBy: null
      }],
      reverses: { entry: original.id, kind: original.kind, quantity: q },
      /* The customer spent them before the reversal arrived. */
      recoverable: q - shortfall,
      shortfall: shortfall,
      unresolved: shortfall > 0
        ? 'The customer has already committed or consumed ' + shortfall +
          ' of these points. What follows — recovery of the debt, voiding the ' +
          'booking, or absorbing it — is a legal and commercial decision that ' +
          'has not been made. See B-recovery.'
        : null
    };
  }

  /* ---- Section F: what the customer pays, and what they receive -----------
   *
   * F2: `issueRate` IS ONE NUMBER PER PROGRAMME. IT MAY NOT VARY BY TRANCHE.
   *
   * This is the rule that keeps a Travel Point from becoming money, and it is
   * worth being exact about why, because the alternative looks harmless and is
   * what most loyalty schemes do.
   *
   * A volume incentive can be built two ways.
   *
   *   (a) Move the rate. "Buy 5,000 and get them at 0.91." Now a point has a
   *       money price, that price differs between customers and between
   *       tranches, and a customer holding 5,000 points can reasonably ask
   *       what theirs cost and what somebody else's cost. A thing with a spot
   *       price per tranche is a currency, and a wallet of them is a balance,
   *       whatever the terms call it.
   *
   *   (b) Grant the extra. The customer pays the same single rate for 5,000
   *       points and RECEIVES 250 more as a promotional grant — a separate
   *       issuance, in its own lot, that was not paid for at all, that expires,
   *       and that cannot be repurchased.
   *
   * (b) is what this implements. Under it the question "what is a point worth"
   * has one answer for purchased points — what the programme charges — and no
   * answer at all for granted ones, because nothing was paid. The incentive is
   * fully expressible and the point never acquires a variable price.
   *
   * `mayActivate()` refuses a programme whose `issueRate` is not a single
   * finite number, so (a) cannot be reached by editing a term.
   */
  function bonusFor(programId, points) {
    var p = program(programId);
    var pr = p.promotional;
    if (!pr || !pr.offered || !(points > 0)) return 0;
    var rate = pr.bonusRate || 0;
    /* A ladder, if the programme sets one. Highest matching band wins, and the
       bands are read in the order the programme wrote them. */
    if (pr.tiers) {
      for (var i = 0; i < pr.tiers.length; i++) {
        if (points >= pr.tiers[i].fromPoints) { rate = pr.tiers[i].bonusRate; break; }
      }
    }
    /* Floor: a grant is whole points, and rounding a bonus up would issue
       entitlement nobody decided to give away. */
    return Math.floor(points * rate);
  }

  /* F1/F4: THE PURCHASE OFFER — the one screen where money and points appear
   * together, and the shape that keeps them apart while they do.
   *
   * `priceMinor` is the price of THIS TRANSACTION. It is computed from
   * `issueRate` alone and the bonus does not reduce it: the customer pays the
   * same price for 1,000 points whether or not a promotion is running, and
   * receives 50 more when one is. That is the difference between a discount —
   * which reprices the point — and a grant, which does not.
   *
   * The two entries are returned, never one inflated one. B7.2 and C5 settled
   * that, and this is where the second entry actually comes from: until now
   * `promotional.bonusRate` was a term nothing computed.
   *
   * APPENDS NOTHING. Like booking.js and buyback.js, this returns what a
   * purchase implies for a caller with the authority to append it — and under
   * a draft programme the fold will refuse those entries anyway.
   */
  function purchaseOffer(programId, points, boughtThisYear) {
    var p = program(programId);
    var allowed = canPurchase(programId, points, boughtThisYear || 0);
    if (!allowed.ok) return { ok: false, why: allowed.why };
    var bonus = bonusFor(programId, points);
    return {
      ok: true,
      programId: p.id,
      programVersion: p.version,
      /* What is paid, and what is received. Deliberately not one number: the
         customer is buying 1,000 points and being given 50, and a single
         "1,050 for $1,000" would state an effective rate that is not the
         programme's rate and would become the number people quote. */
      points: points,
      bonus: bonus,
      total: points + bonus,
      priceMinor: priceOfPoints(programId, points),
      currency: p.currency,
      issueRate: p.issueRate,
      /* F4: the only money figure here is the price of this transaction, and
         it is named as one. There is deliberately no `valueMinor`, no
         `worthMinor` and no per-point price — see MONEY_MOMENTS. */
      entries: bonus > 0
        ? [{ kind: 'PURCHASE', quantity: points },
           { kind: 'PROMOTION', quantity: bonus }]
        : [{ kind: 'PURCHASE', quantity: points }],
      note: bonus > 0
        ? 'You are purchasing ' + points + ' Travel Points and receiving ' +
          bonus + ' more as a promotional grant. Granted points expire and ' +
          'cannot be repurchased.'
        : 'You are purchasing ' + points + ' Travel Points.'
    };
  }

  /* B3/B7: THE ENTRIES A SETTLED PURCHASE IMPLIES, SELF-DESCRIBING.
   *
   * `purchaseOffer` above is what the customer is shown before they pay. This
   * is what is written after the money settles, and it will not write anything
   * against a payment that has not.
   *
   * WHAT IS STAMPED, AND WHAT IS DELIBERATELY NOT.
   *
   * `issueRateApplied` is stamped on the entry even though `programVersion`
   * already determines it. Programmes are immutable, so this is not needed to
   * reconstruct the rate — it is there so that an auditor reading one row can
   * see the term that produced it without loading anything, and so that a
   * disagreement between the two is detectable rather than silent. Under
   * B7.1's spirit, a redundant fact that can be checked is worth more than a
   * derivable one that cannot.
   *
   * The AMOUNT PAID is NOT stamped. B19/B22 keep money in `payments` and
   * entitlement in the ledger, joined by a reference — and an amount recorded
   * in two places is an amount that can disagree with itself, at which point
   * nobody knows which is the payment. `paymentRef` carries the join.
   *
   * B7: the promotional grant is a SECOND ENTRY with its own lot, so its
   * origin is in the ledger rather than inferable from a rate. That is what
   * makes it excludable from repurchase (E7) and expirable (E9) at all.
   */
  function issuance(programId, points, payment, refs) {
    var p = program(programId);
    if (!payment || !payment.ref) {
      return { ok: false, why: 'issuance requires a payment reference' };
    }
    if (!maySettleIssuance(payment.status)) {
      return { ok: false, why: 'payment ' + payment.ref + ' is ' +
                              payment.status + '; points are issued only ' +
                              'after settlement',
               paymentStatus: payment.status };
    }
    var offer = purchaseOffer(programId, points, (refs || {}).boughtThisYear || 0);
    if (!offer.ok) return offer;
    var r = refs || {};
    var common = {
      status: 'SETTLED',
      programVersion: p.id,
      paymentRef: payment.ref,
      issueRateApplied: p.issueRate
    };
    var out = [Object.assign({}, common, {
      kind: 'PURCHASE',
      quantity: offer.points,
      id: r.purchaseId || null,
      idempotencyKey: r.purchaseKey || null,
      payment: payment
    })];
    if (offer.bonus > 0) {
      out.push(Object.assign({}, common, {
        kind: 'PROMOTION',
        quantity: offer.bonus,
        id: r.promotionId || null,
        idempotencyKey: r.promotionKey || null,
        /* No payment on the grant: nothing was paid for it, and that absence
           is what E7's "only purchased points can be bought back" reads. */
        grantedUnder: (p.promotional && p.promotional.tiers) ? 'tier' : 'flat'
      }));
    }
    return { ok: true, offer: offer, entries: out };
  }

  /* F4: WHERE A MONEY FIGURE MAY APPEAR, AS DATA RATHER THAN AS A CONVENTION.
   *
   * A convention in a document is a convention somebody has not read. This is
   * the closed list, and `tools/points-checks.js` asserts that the customer-
   * facing surfaces show money at these three moments and nowhere else.
   *
   * The distinction that decides every case: money attaches to a TRANSACTION
   * or to a JOURNEY. It never attaches to a HOLDING. "$1,000" beside a
   * purchase button is a price; "$4,800" beside a journey is what the journey
   * costs; "3,650 TP ($3,650)" beside a wallet is a balance, and that is the
   * sentence that makes this a financial product.
   */
  var MONEY_MOMENTS = [
    { moment: 'purchase',  shows: 'the price of this transaction',
      why: 'the customer is being charged and must see what' },
    { moment: 'journey',   shows: 'what the journey costs',
      why: 'a travel price, quoted in money because travel is sold in money' },
    { moment: 'repurchase', shows: 'what is offered for specific points',
      why: 'an offer about identified points, not a statement of their worth' }
  ];

  /* Kept under their old names so nothing that already calls them breaks. The
     new names say which question they answer, which is the entire lesson of
     A4. */
  var pointsFor = pointsForPurchase;
  var priceOf = priceOfPoints;

  function fold(entries) {
    var w = blank();
    var seen = Object.create(null);
    var byId = Object.create(null);
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

      /* B6: AND THE PAYMENT'S OWN STATE, WHICH IS THE ONE THAT MATTERS.
         The entry's status says what WE think; `payment.status` says what the
         provider says, and only one of those is evidence. An entry marked
         SETTLED against an authorisation is the exact failure B6 names —
         entitlement created against money the bank has merely promised — and
         it used to fold cleanly because nothing looked past the entry. */
      if (ISSUING_KINDS.indexOf(e.kind) !== -1 && e.payment &&
          e.payment.status != null && !maySettleIssuance(e.payment.status)) {
        throw new Error(
          'cannot issue points: entry ' + e.id + ' is marked ' + e.status +
          ' but its payment is ' + e.payment.status +
          '. Points are issued only after settlement.');
      }

      /* AND ONLY AN APPROVED PROGRAM CREATES POINTS AT ALL.
         The site is in DRAFT_PROGRAM: the terms are written and the ledger
         works, and no customer holds anything. This refusal is what makes
         that true rather than merely intended — including if somebody wires a
         payment handler up before the legal answer arrives. */
      /* D1: EVERY POINT BELONGS TO A NAMED PROGRAMME, INCLUDING WHEN IT LEAVES.
         Issuance already required one. Nothing required it of a RESERVE, a
         REDEEM or a BUYBACK, so an entry could move points without naming the
         terms they moved under — and D5 says the terms travel with the points
         for their whole life, not only at the moment they are created. */
      if (!e.programVersion) {
        throw new Error('ledger entry without a programme: ' + e.id +
                        ' (' + e.kind + '). Every Travel Point belongs to a ' +
                        'named programme for the whole of its life.');
      }

      if (ISSUING_KINDS.indexOf(e.kind) !== -1 && !mayIssue(e.programVersion)) {
        throw new Error(
          'cannot issue points: program ' + (e.programVersion || '(none)') +
          ' is ' + stateOf(e.programVersion) +
          '. Points may only be issued under an ACTIVE_PROGRAM.');
      }

      /* E8: NON-TRANSFERABILITY IS ENFORCED, NOT MERELY DECLARED.
         `transferable: false` was a term nothing read. The kinds stay — B14
         settled that policy is not capability, and an administrative
         correction under a later programme still needs them — but under a
         programme that forbids transfer, an entry that moves points between
         customers is refused where it is written rather than where it is
         reviewed. */
      if (TRANSFER_KINDS.indexOf(e.kind) !== -1 &&
          program(e.programVersion).transferable === false) {
        throw new Error(
          'cannot transfer points: program ' + (e.programVersion || '(none)') +
          ' is not transferable. Person-to-person transfer is outside V1.');
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
        /* D8: EARLIEST EXPIRY FIRST, WHICH IS NOT THE SAME RULE AS
           "PROMOTIONAL FIRST".

           This used to spend the promotional pool first unconditionally, and
           under `AFK-TP-2026.1` that is the right answer — purchased points
           never lapse, promotional ones lapse at 24 months, so promotional is
           the earlier expiry. The two rules AGREE here, which is exactly why
           the difference went unnoticed.

           They stop agreeing the moment a programme sets a shorter validity on
           purchased points than on promotional ones. "Promotional first" would
           then burn the longer-lived points first and let the shorter-lived
           ones lapse — costing the customer points they had already paid for.
           So the order is now DERIVED from the programme's own validity terms.

           Clock-free: it compares the programme's validity in MONTHS, not
           dates, so no balance can move because time passed. `null` means
           never lapses and sorts last, which is the whole of D2. */
        var order = consumptionOrder(e.programVersion);
        /* Its own remainder, NOT `q`: the reservation and correction bookkeeping
           further down this same loop still needs the entry's full quantity,
           and decrementing `q` here silently zeroed both. */
        var left = q;
        for (var oi = 0; oi < order.length && left > 0; oi++) {
          var pool = order[oi];
          var take = Math.min(w[pool], left);
          w[pool] -= take;
          left -= take;
        }
      }

      /* B4: A COMPENSATING ENTRY SAYS WHAT IT COMPENSATES.
         Nothing is ever edited, so a correction is a new entry — and a
         correction that does not name the entry it corrects leaves an auditor
         to infer the pairing from amounts and timing, which is how two
         unrelated adjustments get read as one correction. `corrects` must
         point at an entry the fold has already seen: a correction cannot
         precede its cause. */
      if (e.corrects) {
        if (!byId[e.corrects]) {
          throw new Error('entry ' + e.id + ' corrects ' + e.corrects +
                          ', which is not earlier in this ledger');
        }
        w.corrections.push({ entry: e.id, corrects: e.corrects,
                             kind: e.kind, quantity: q });
      }
      byId[e.id] = true;

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
      /* Administrative corrections move the balance, so a wallet that hides
         them cannot be reconciled against its own entries — the identity
         available = acquired - reserved - redeemed - boughtBack - expired
         - adjusted simply would not close. The fold always tracked this; the
         return forgot it, and a test asking the identity to hold is what
         noticed. */
      adjusted: w.adjusted,
      boughtBack: w.boughtBack,
      expired: w.expired,
      reservations: w.reservations,
      corrections: w.corrections,
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
  /* ---- C8: WHERE DID THESE POINTS COME FROM ------------------------------
   *
   * The wallet answers "how many", which is what a customer sees and what a
   * booking needs. C8 asks nine questions the aggregate cannot answer: when
   * were these issued, under which programme, at what issue rate, carrying
   * what entitlement, were they promotional, reserved, redeemed, expired,
   * cancelled, bought back.
   *
   * All of it is in the ledger already — this reads it back per lot rather
   * than folding it away. Consumption is applied in the programme's lotOrder
   * (provisionally FIFO, open question B-ii) so a lot can say how much of it
   * is left, and the answer is derived rather than stored, like every other
   * figure here.
   *
   * Deliberately NOT part of `wallet()`. A wallet is what a customer is shown
   * and B22 keeps it to counts of points; this is what an auditor, a dispute
   * or a repurchase quote needs, and mixing them would put lot detail on a
   * screen that should carry a balance.
   */
  function lots(entries) {
    var open = [];
    var consumed = [];

    (entries || []).forEach(function (e) {
      var kind = KINDS[e.kind];
      if (!kind) return;
      if (e.kind === 'PURCHASE' && e.status !== 'SETTLED') return;

      if (kind.lot) {
        var p = PROGRAMS[e.programVersion];
        open.push({
          entry: e.id,
          issuedAt: e.at || null,          // recorded by the caller, not a clock
          programId: e.programVersion || null,
          programVersion: p ? p.version : null,
          issueRate: p ? p.issueRate : null,
          entitlementRate: p ? p.entitlementRate : null,
          promotional: kind.lot === 'promotional',
          quantity: e.quantity,
          remaining: e.quantity,
          paymentRef: e.paymentRef || (e.payment ? e.payment.ref || null : null),
          considerationMinor: e.payment ? e.payment.amountMinor : null,
          currency: e.payment ? e.payment.currency : null,
          spent: {}                        // kind -> quantity taken from this lot
        });
        return;
      }

      /* Anything that removes points takes them from open lots in order, so
         "have these been redeemed" has a per-lot answer rather than a
         site-wide total. */
      if (kind.available === -1 || kind.reserved === -1) {
        var want = e.quantity;
        for (var i = 0; i < open.length && want > 0; i++) {
          var lot = open[i];
          if (lot.remaining <= 0) continue;
          var take = Math.min(want, lot.remaining);
          lot.remaining -= take;
          lot.spent[e.kind] = (lot.spent[e.kind] || 0) + take;
          want -= take;
        }
        consumed.push({ entry: e.id, kind: e.kind, quantity: e.quantity,
                        unmatched: want });
      }
    });

    return { lots: open, movements: consumed };
  }

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

  /* ---- D6: when the journey the points were meant for disappears ----------
   *
   * The hard case, and the one where doing nothing IS the failure. A customer
   * who accumulated toward a journey Afrinkong no longer sells must be offered
   * something, in a stated order, and "the points are void" is not on the list
   * at any position.
   *
   *   1. equivalent travel        a comparable eligible service
   *   2. another eligible service anything else within programme scope
   *   3. programme buyback        if the programme's terms permit it
   *
   * Returned as an ordered list of remedies that are ACTUALLY AVAILABLE under
   * this programme, so a caller cannot offer a repurchase that the programme
   * does not offer, or an alternative service that is out of scope. If the
   * list would ever be empty, that is itself the answer a human has to deal
   * with — `exhausted: true` — rather than a silent zero.
   */
  function remedies(programId, opts) {
    var p = program(programId);
    var o = opts || {};
    var out = [];
    if ((o.equivalents || []).length) {
      out.push({ remedy: 'equivalent', rank: 1,
                 options: o.equivalents,
                 note: 'A comparable eligible journey under the same programme.' });
    }
    var scope = (p.eligibleServices || []).filter(function (s) {
      return (o.unavailableServices || []).indexOf(s) === -1;
    });
    if (scope.length) {
      out.push({ remedy: 'alternative', rank: 2,
                 services: scope,
                 note: 'The points may be applied to another eligible service ' +
                       'under this programme.' });
    }
    if (p.buyback && p.buyback.offered && mayBuyBack(programId)) {
      out.push({ remedy: 'buyback', rank: 3,
                 discretionary: !!p.buyback.discretionary,
                 note: 'The programme’s repurchase terms may apply. This ' +
                       'is an offer under those terms, not a refund.' });
    }
    return {
      programId: p.id,
      remedies: out,
      exhausted: out.length === 0,
      /* Said explicitly because the whole rule is what must NOT happen. */
      neverAnOption: 'expiring or voiding the points because the journey ' +
                     'is no longer offered',
      note: out.length === 0
        ? 'No remedy is available under this programme’s current terms. ' +
          'This requires a human decision; it is not a case where the points ' +
          'lapse.'
        : null
    };
  }

  /* ---- transfer, and the two separate reasons to refuse it ----------------
   *
   * C8/C9: THE FINAL-WINDOW BAR MUST NOT DEPEND ON THE GLOBAL ONE.
   *
   * Today `transferable: false` refuses every transfer at the fold (E8), so
   * "reserved points cannot be transferred inside the final window" is true —
   * but true for the wrong reason. The moment a future programme sets
   * `transferable: true`, C8's window bar would vanish silently, because
   * nothing else was ever enforcing it. A rule that holds only as a side
   * effect of a different rule is a rule waiting to be lost.
   *
   * So there are three independent refusals here:
   *
   *   1. the programme forbids transfer at all              (C9, E8)
   *   2. the transfer is a SALE and the programme forbids
   *      a secondary market                                 (C9)
   *   3. the points are committed to a journey inside its
   *      restricted window                                  (C8)
   *
   * The second is why `secondaryMarket` finally reads. Until now it was a
   * declared term that nothing consulted — exactly the state `transferable`
   * was in before E8, and found the same way.
   *
   * NO CLOCK, so `commitments` arrives from the caller, the same shape and for
   * the same reason as in `buybackQuote`. The fold cannot do this check: it
   * has no departure dates and must not acquire any.
   */
  function mayTransfer(programId, opts) {
    var p = program(programId);
    var o = opts || {};
    if (p.transferable === false) {
      return { ok: false, why: 'this programme does not permit transfer',
               rule: 'transferable' };
    }
    if (o.forConsideration && p.secondaryMarket === false) {
      return { ok: false, why: 'this programme does not permit points to be ' +
                              'sold to another customer',
               rule: 'secondaryMarket' };
    }
    var restricted = (o.commitments || []).filter(function (c) {
      return cancellation(programId, c.daysToDeparture, c.points || 0)
               .buybackEligible === false;
    });
    if (restricted.length) {
      return { ok: false,
               why: 'points committed to a journey inside its restricted ' +
                    'period cannot be transferred',
               rule: 'restrictedWindow',
               restricted: restricted.map(function (c) {
                 return { journeyRef: c.journeyRef,
                          daysToDeparture: c.daysToDeparture };
               }) };
    }
    return { ok: true };
  }

  /* ---- validity -----------------------------------------------------------
   *
   * E9: HOW LONG A POINT LASTS IS A PROGRAMME TERM AND DIFFERS BY LOT.
   *
   * `AFK-TP-2026.1` says purchased points never lapse from time alone and
   * promotional points lapse at 24 months. One scalar could not have said
   * that, which is why `expiry` is a block; and `null` means never rather
   * than unset, because a term that has to distinguish "forever" from
   * "nobody decided" cannot use the same value for both.
   *
   * NO CLOCK. `monthsHeld` is supplied by the caller for the same reason
   * `daysToDeparture` is: D21.4 says no balance may grow or shrink because
   * time passed inside this module, and a module that could read a date could
   * expire somebody's holding without an entry. Lapsing still costs an
   * explicit EXPIRE entry that a human or a job appended.
   */
  function validity(programId, lot) {
    var e = program(programId).expiry || {};
    var months = e[lot === 'promotional' ? 'promotional' : 'purchased'];
    return {
      lot: lot === 'promotional' ? 'promotional' : 'purchased',
      months: months == null ? null : months,
      lapses: months != null
    };
  }

  /* D8: WHICH POOL IS SPENT FIRST, DERIVED RATHER THAN ASSUMED.
   *
   * Answers the promotional half of long-open question B-ii, which Decision D
   * settles: earliest expiry first, so the customer keeps what would otherwise
   * lapse. `null` months means the pool never lapses and therefore sorts last.
   *
   * A stable tie-break matters: when neither pool lapses, or both lapse at the
   * same month, the order must not depend on object key order or on a sort
   * implementation. Promotional goes first on a tie, because it is the pool
   * that cannot be repurchased (E7) and is forfeited on cancellation — so
   * spending it first is still the treatment that costs the customer least.
   */
  function consumptionOrder(programId) {
    var far = Infinity;
    var months;
    try {
      months = {
        promotional: validity(programId, 'promotional').months,
        purchased: validity(programId, 'purchased').months
      };
    } catch (err) {
      /* An entry with no programme cannot name a validity. D1 refuses such an
         entry at the fold; this keeps the helper total for callers that ask
         about one anyway. */
      return ['promotional', 'purchased'];
    }
    var p = months.promotional == null ? far : months.promotional;
    var u = months.purchased == null ? far : months.purchased;
    return u < p ? ['purchased', 'promotional'] : ['promotional', 'purchased'];
  }

  /* D7: WHICH OF MY POINTS EXPIRE, AND WHEN — ANSWERED, NOT LEFT TO INFERENCE.
   *
   * "The customer should never have to guess which points are expiring." A
   * wallet that says 5,500 TP and a footnote saying some of them lapse is
   * exactly that guess. This returns the two pools separately, each with its
   * own validity and the order they will be spent in, so a surface can show
   * the sentence rather than the arithmetic.
   *
   * Still no clock. Months are the programme's term; a date needs an issuance
   * date, and that belongs to whatever stores the entries.
   */
  function expiryDisclosure(programId, entries) {
    var w = wallet(entries);
    var order = consumptionOrder(programId);
    var pools = [
      { lot: 'purchased', points: w.purchased },
      { lot: 'promotional', points: w.promotional }
    ].map(function (x) {
      var v = validity(programId, x.lot);
      return {
        lot: x.lot,
        points: x.points,
        lapses: v.lapses,
        validityMonths: v.months,
        spentAt: order.indexOf(x.lot) + 1,
        /* The sentence, assembled here so every surface says the same thing
           and none of them can render the number while dropping the terms. */
        statement: x.points === 0 ? null
          : v.lapses
            ? x.points + ' TP acquired as a promotional grant, valid for ' +
              v.months + ' months from issue.'
            : x.points + ' TP purchased. These do not expire.'
      };
    });
    return {
      programId: program(programId).id,
      total: w.available,
      pools: pools,
      /* D8 stated in words, because "which of mine gets used first" is the
         customer's real question and the answer is reassuring. */
      spendOrder: order,
      spendNote: 'Points that expire soonest are used first, so nothing lapses ' +
                 'that could have been spent.',
      /* D2/D10 stated so a surface cannot imply the opposite by omission. */
      inactivityNote: 'Purchased Travel Points are not affected by how long ' +
                      'you go without using your account.'
    };
  }

  function hasLapsed(programId, lot, monthsHeld) {
    var v = validity(programId, lot);
    return v.lapses && (monthsHeld || 0) >= v.months;
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

  /* E3: A QUOTE, NOT A SETTLEMENT.
   *
   *   request -> eligibility -> QUOTATION -> customer accepts -> settlement
   *                                                           -> ledger BUYBACK
   *
   * This function does the first three. It removes no points and appends
   * nothing: a customer asking what they would be offered has not sold
   * anything, and a quote they never accept must leave no trace on a balance.
   *
   * E6: `commitments` is how the restricted window finally reaches this
   * function. It is a list of { journeyRef, daysToDeparture, points } supplied
   * by the caller, because this module has no clock and no bookings table.
   * Until now `cancellation()` computed buybackEligible:false inside seven days
   * and the quote could not see it — two functions holding half a rule each,
   * which is how somebody inside the final window gets offered a quote they
   * should never have been given. B24 rule 22, and the last of the contradicted
   * rules.
   */
  function buybackQuote(programId, entries, points, heldDays, boughtBackThisYear,
                        commitments) {
    var p = program(programId);
    var b = p.buyback;
    var w = wallet(entries);
    var refuse = function (why, extra) {
      var r = { eligible: false, why: why, points: points };
      if (extra) for (var k in extra) r[k] = extra[k];
      return r;
    };

    if (!b || !b.offered) return refuse('this program does not offer buyback');
    /* E4/E11: the ladder first, before any arithmetic. A draft programme that
       computed a payable figure and only then declined to pay it would have
       produced the number, and a number that exists gets shown. */
    if (!mayBuyBack(programId)) {
      return refuse('program ' + programId + ' is ' + complianceOf(programId) +
                    '; points cannot be bought back under it',
                    { compliance: complianceOf(programId) });
    }
    if (points < b.minPoints) return refuse('below the minimum of ' + b.minPoints + ' points');
    /* C16: reserved points repurchase at zero — committed to a journey is not
       available to sell back. `available` already excludes them. */
    if (points > w.available) return refuse('only available points can be bought back');
    if (heldDays < b.minHoldDays) return refuse('points must be held for ' + b.minHoldDays + ' days');
    if ((boughtBackThisYear || 0) + points > b.maxPerYear) {
      return refuse('above the annual limit of ' + b.maxPerYear + ' points');
    }
    /* C5: and the percentage cap, when the programme sets one.
       THE BASE INCLUDES WHAT HAS ALREADY BEEN SOLD BACK THIS YEAR. Measuring
       against the holding as it stands now would let a customer sell 25% of a
       shrinking balance over and over — 25%, then 25% of the remainder — and
       reach most of their holding inside a year while never once exceeding the
       limit. The base is what they held at the start of the year's selling,
       reconstructed as (eligible now + already sold back). */
    if (b.maxPctPerYear != null) {
      var eligibleNow = b.promotionalEligible === false ? w.purchased : w.available;
      var base = eligibleNow + (boughtBackThisYear || 0);
      var ceiling = Math.floor(base * b.maxPctPerYear);
      if ((boughtBackThisYear || 0) + points > ceiling) {
        return refuse('above the annual limit of ' +
                      Math.round(b.maxPctPerYear * 100) + '% of eligible points',
                      { annualCeiling: ceiling, base: base,
                        alreadyBoughtBack: boughtBackThisYear || 0 });
      }
    }
    /* E6: points committed to a journey inside its restricted window are not
       available to sell back, however much the wallet says is available. The
       band is the programme's, read through cancellation(), so a programme
       that sets a different window is obeyed without editing this. */
    var restricted = (commitments || []).filter(function (c) {
      var band = cancellation(programId, c.daysToDeparture, c.points || 0);
      return band.buybackEligible === false;
    });
    if (restricted.length) {
      return refuse('points committed to a journey inside its restricted ' +
                    'period cannot be bought back',
                    { restricted: restricted.map(function (c) {
                        return { journeyRef: c.journeyRef,
                                 daysToDeparture: c.daysToDeparture };
                      }) });
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
      var payable = Math.round(c.minor * b.rate);
      return {
        eligible: true,
        discretionary: b.discretionary,
        points: points,
        basis: 'consideration',
        grossMinor: c.minor,
        currency: c.currency,
        rate: b.rate,
        payableMinor: payable,
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
    /* E2's rail. Whatever basis a programme names, a repurchase may never pay
       out more than the customer put in — which closes B12.2's arbitrage under
       every basis rather than only under one, and does it without describing
       repurchase as a refund. */
    var gross = entitlementOf(programId, points);
    var raw = Math.round(gross * b.rate);
    var capped = raw;
    var cap = null;
    if (b.maxPayableIsConsideration) {
      var paid = considerationFor(programId, entries, points);
      if (paid.ok) { cap = paid.minor; capped = Math.min(raw, paid.minor); }
    }
    return {
      eligible: true,
      discretionary: b.discretionary,
      points: points,
      basis: 'entitlement',
      grossMinor: gross,
      rate: b.rate,
      payableMinor: capped,
      cappedAtConsideration: cap !== null && capped < raw,
      note: 'Quoted on the entitlement basis under this programme’s terms. ' +
            'This is an offer, not a refund of a purchase price.'
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
    REDEEMING_STATES: REDEEMING_STATES,
    mayRedeem: mayRedeem,
    mayBuyBack: mayBuyBack,
    mayTransfer: mayTransfer,
    mayClose: mayClose,
    remedies: remedies,
    consumptionOrder: consumptionOrder,
    expiryDisclosure: expiryDisclosure,
    TRANSFER_KINDS: TRANSFER_KINDS,
    validity: validity,
    hasLapsed: hasLapsed,
    complianceOf: complianceOf,
    mayTransition: mayTransition,
    considerationFor: considerationFor,
    program: program,
    variant: variant,
    pointsFor: pointsFor,
    bonusFor: bonusFor,
    purchaseOffer: purchaseOffer,
    issuance: issuance,
    reversal: reversal,
    PAYMENT_STATES: PAYMENT_STATES,
    ISSUING_PAYMENT_STATES: ISSUING_PAYMENT_STATES,
    maySettleIssuance: maySettleIssuance,
    MONEY_MOMENTS: MONEY_MOMENTS,
    priceOf: priceOf,
    entitlementOf: entitlementOf,
    pointsForPurchase: pointsForPurchase,
    priceOfPoints: priceOfPoints,
    goalRequirement: goalRequirement,
    canPurchase: canPurchase,
    fold: fold,
    wallet: wallet,
    lots: lots,
    can: can,
    cancellation: cancellation,
    buybackQuote: buybackQuote,
    goal: goal,
    project: project
  };
});
