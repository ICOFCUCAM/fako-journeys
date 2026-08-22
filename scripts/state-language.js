/* The Afrinkong state language. Item 4 of the design order.
 *
 * @product: live | @gate: none | @surface: /journey-fund
 * ===========================================================================
 * WHAT THIS IS FOR
 *
 * The system can distinguish 72 states. The website could express one, and it
 * was "empty". This file is the missing half: for every internal state, the one
 * sentence a customer is shown, the tone it is shown in, which of the five
 * kinds of state it is, and what the customer may do about it.
 *
 * It decides nothing economic. Every state named here already existed; this
 * names it in English and gives it a face. No state is added, removed, renamed
 * internally, or given a new transition.
 *
 * THE MEASUREMENT THAT PROMPTED IT
 *
 *     72 states across 12 vocabularies, every one of them already in code
 *     11 words carry more than one meaning, across 24 of those slots
 *
 * The published figure for this was 39 across five vocabularies. That
 * undercounted by 33: it missed account states, auth levels, the buyback
 * request lifecycle, risk holds, purchase plans, product state, transfer
 * kinds, and the journey's own six stages.
 *
 * `SETTLED` means three different things today: a point that has been bought
 * back and paid out, a payment that has cleared, and a buyback request that has
 * finished. `REJECTED` also means three. A third of the system's state slots
 * are spoken for by a word that is already ambiguous.
 *
 * THE RULE THAT FOLLOWS FROM THAT
 *
 * A small vocabulary and an unambiguous one pull in opposite directions, and
 * the resolution is that they are different vocabularies:
 *
 *     SIX TONES        the visual language. Learned once, then recognised
 *                      everywhere. This is the part that must stay small.
 *     SEVENTY-TWO      one per internal state, never shared. This is the part
 *     LABELS           that must stay precise.
 *
 * So the customer learns six shapes and reads a specific sentence. One word
 * never does two jobs — `points:RESERVED` is "Held for a booking" and
 * `booking:RESERVED` is "Your journey is reserved", because they are not the
 * same fact and a customer holding one should never be shown the other.
 *
 * ENDED IS NOT BROKEN, AND THAT IS THE MOST IMPORTANT LINE HERE
 *
 * An expired point, a cancelled journey and a closed programme are not
 * failures. A declined payment is. Products that paint them the same colour
 * teach people that ordinary endings are their fault, and then those people
 * stop pressing things. Two tones, deliberately, and a check asserts nothing
 * that merely ended is painted as broken.
 *
 * WHERE TRANSITIONS COME FROM
 *
 * Not from here. Five modules already carry transition tables — BOOKING_NEXT,
 * REQUEST_NEXT, COMPLIANCE_NEXT, PLAN_NEXT, HOLD_NEXT — and `nextOf()` reads
 * them. Copying a transition into this file would create a second answer to a
 * question that already has one, which is the exact defect this session has
 * spent its time finding. Where a vocabulary has no table in code, `nextOf`
 * says so rather than inventing one.
 *
 * Pure. No DOM, no network, no clock.
 */
(function (root, factory) {
  var api = factory(
    typeof require === 'function' ? require('./points-ledger.js') : root.AfrinkongPoints,
    typeof require === 'function' ? require('./booking.js') : root.AfrinkongBooking,
    typeof require === 'function' ? require('./buyback.js') : root.AfrinkongBuyback,
    typeof require === 'function' ? require('./account.js') : root.AfrinkongAccount,
    typeof require === 'function' ? require('./risk.js') : root.AfrinkongRisk,
    typeof require === 'function' ? require('./purchase-plan.js') : root.AfrinkongPlan
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongStates = api;
})(typeof self !== 'undefined' ? self : this,
   function (Points, Booking, Buyback, Account, Risk, Plan) {
  'use strict';

  /* ---- the six tones ----------------------------------------------------
     The whole visual vocabulary. A seventh would have to earn itself against
     the question "which of these six is it, really", and so far nothing has. */
  var TONE = {
    NEUTRAL: 'neutral',   /* a fact. Nothing is happening and nothing is wrong */
    WORKING: 'working',   /* we are doing it; it finishes without anybody      */
    WAITING: 'waiting',   /* it needs a person. It will NOT finish on its own  */
    DONE:    'done',      /* finished the way it was meant to                  */
    ENDED:   'ended',     /* over, by choice or by time. NOT a failure         */
    BROKEN:  'broken'     /* went wrong, and somebody has to look              */
  };

  /* ---- the five kinds of state ------------------------------------------
     The brief's own division, and it is a real one: a customer can be in five
     of these at once, and confusing any two of them produces a sentence that
     is true about the wrong subject. "Cancelled" said about money, about
     points and about a journey are three different pieces of news. */
  var DOMAIN = {
    POINTS:  'points',    /* entitlement — what happened to Travel Points   */
    MONEY:   'money',     /* payment    — what happened to money            */
    TRAVEL:  'travel',    /* journey    — what happened to the booking      */
    ACCOUNT: 'account',   /* permission — what the customer may do          */
    SYSTEM:  'system'     /* platform   — what Afrinkong is currently doing */
  };

  /* Actions are named, not free text, so that a surface cannot offer a verb
     the language never sanctioned and a check can compare the two lists. */
  var ACTION = {
    NONE:        'none',
    WAIT:        'wait',
    RETRY_PAY:   'retry-payment',
    CONTACT:     'contact-us',
    VERIFY:      'verify-identity',
    CONFIRM:     'confirm',
    CANCEL:      'cancel',
    ACCEPT:      'accept-quote',
    DECLINE:     'decline-quote',
    PLAN:        'plan-a-journey',
    RESUME:      'resume-plan',
    PAUSE:       'pause-plan',
    VIEW:        'view-details'
  };

  function S(label, explain, tone, domain, actions) {
    return { label: label, explain: explain, tone: tone,
             domain: domain, actions: actions || [ACTION.NONE] };
  }

  /* ---- the language -----------------------------------------------------
     Keyed `vocabulary:STATE`. The vocabulary half is not decoration: it is
     what stops `SETTLED` needing to mean three things. */
  var LANGUAGE = {

    /* -- entitlement. Decision I governs every line in this block: a Travel
          Point never shows a cash value, so no label here names an amount of
          money, and points-checks greps for exactly that. -------------- */
    'points:CREATED': S('Being prepared',
      'The record exists and the point is not yours yet.',
      TONE.WORKING, DOMAIN.POINTS, [ACTION.WAIT]),
    'points:ISSUED': S('Issued to you',
      'The point is yours. It is about to become available to spend.',
      TONE.WORKING, DOMAIN.POINTS, [ACTION.WAIT]),
    'points:AVAILABLE': S('Ready to use',
      'You can put this towards a journey whenever you choose.',
      TONE.NEUTRAL, DOMAIN.POINTS, [ACTION.PLAN]),
    'points:RESERVED': S('Held for a booking',
      'Set aside for a journey you have started. Still yours, not yet spent.',
      TONE.WAITING, DOMAIN.POINTS, [ACTION.VIEW, ACTION.CANCEL]),
    'points:REDEEMED': S('Used for travel',
      'Spent on a journey. This is what a Travel Point is for.',
      TONE.DONE, DOMAIN.POINTS, [ACTION.VIEW]),
    'points:TRANSFERRED': S('Given to someone',
      'Passed to another person. It is theirs now, not yours.',
      TONE.DONE, DOMAIN.POINTS, [ACTION.VIEW]),
    'points:BUYBACK_REQUESTED': S('Repurchase asked for',
      'You have asked us to buy this back. Nothing has moved yet.',
      TONE.WAITING, DOMAIN.POINTS, [ACTION.WAIT]),
    'points:BUYBACK_APPROVED': S('Repurchase agreed',
      'We have agreed to buy it back, and the payment is being arranged.',
      TONE.WORKING, DOMAIN.POINTS, [ACTION.WAIT]),
    'points:SETTLED': S('Repurchase completed',
      'Bought back, and the payment has left us.',
      TONE.DONE, DOMAIN.POINTS, [ACTION.VIEW]),
    'points:CANCELLED': S('Cancelled',
      'This point was undone, and the record of why it existed remains.',
      TONE.ENDED, DOMAIN.POINTS, [ACTION.VIEW]),
    'points:EXPIRED': S('Expired',
      'Past the date it could be used by. Nothing was taken from you.',
      TONE.ENDED, DOMAIN.POINTS, [ACTION.VIEW]),

    'points:TRANSFER_IN': S('Received from someone',
      'Somebody passed these to you.',
      TONE.NEUTRAL, DOMAIN.POINTS, [ACTION.VIEW]),
    'points:TRANSFER_OUT': S('Sent to someone',
      'You passed these on. They belong to the person you sent them to.',
      TONE.NEUTRAL, DOMAIN.POINTS, [ACTION.VIEW]),

    /* -- money ------------------------------------------------------------
          Seven payment states, and six of them are invisible on most sites.
          A customer whose card needs a second step is told that, rather than
          being shown a spinner that never ends. */
    'payment:pending': S('Payment starting',
      'Your bank has the request. This usually takes a few seconds.',
      TONE.WORKING, DOMAIN.MONEY, [ACTION.WAIT]),
    'payment:requires_capture': S('Payment needs one more step',
      'Your bank has asked you to confirm this before it will go through.',
      TONE.WAITING, DOMAIN.MONEY, [ACTION.CONFIRM]),
    'payment:authorised': S('Payment approved, not yet taken',
      'Your bank has approved it. Nothing has left your account.',
      TONE.WORKING, DOMAIN.MONEY, [ACTION.WAIT]),
    'payment:settled': S('Payment received',
      'The money has reached us.',
      TONE.DONE, DOMAIN.MONEY, [ACTION.VIEW]),
    'payment:failed': S('Payment did not go through',
      'Your bank declined it. Nothing was taken, and you can try again.',
      TONE.BROKEN, DOMAIN.MONEY, [ACTION.RETRY_PAY, ACTION.CONTACT]),
    'payment:refunded': S('Payment returned',
      'The money has gone back to where it came from.',
      TONE.ENDED, DOMAIN.MONEY, [ACTION.VIEW]),
    'payment:charged_back': S('Payment disputed',
      'Your bank has reversed this and we are looking into it with them.',
      TONE.BROKEN, DOMAIN.MONEY, [ACTION.CONTACT]),

    /* -- the repurchase conversation. Separate from points:BUYBACK_* on
          purpose: those are what happened to the POINTS, these are what
          happened to the REQUEST, and the two move at different times. */
    'buyback:REQUESTED': S('Repurchase request received',
      'We have your request and are working out what we can offer.',
      TONE.WORKING, DOMAIN.MONEY, [ACTION.WAIT]),
    'buyback:REFUSED': S('Repurchase not available',
      'We cannot buy these back at the moment, and here is why.',
      TONE.ENDED, DOMAIN.MONEY, [ACTION.CONTACT]),
    'buyback:QUOTED': S('Repurchase offer ready',
      'Here is what we can offer. It is a quote, not a hold, and it can change.',
      TONE.WAITING, DOMAIN.MONEY, [ACTION.ACCEPT, ACTION.DECLINE]),
    'buyback:LAPSED': S('Repurchase offer expired',
      'This offer was not taken up in time. You can ask again.',
      TONE.ENDED, DOMAIN.MONEY, [ACTION.VIEW]),
    'buyback:DECLINED': S('Repurchase offer declined',
      'You turned this offer down. Your points are untouched.',
      TONE.ENDED, DOMAIN.MONEY, [ACTION.VIEW]),
    'buyback:ACCEPTED': S('Repurchase offer accepted',
      'You have accepted. We are checking it before anything moves.',
      TONE.WORKING, DOMAIN.MONEY, [ACTION.WAIT]),
    'buyback:APPROVED': S('Repurchase approved',
      'Checked and agreed. The payment is being arranged.',
      TONE.WORKING, DOMAIN.MONEY, [ACTION.WAIT]),
    'buyback:REJECTED': S('Repurchase stopped after review',
      'Our checks stopped this one. Talk to us and we will explain.',
      TONE.BROKEN, DOMAIN.MONEY, [ACTION.CONTACT]),
    'buyback:SETTLED': S('Repurchase paid',
      'The money has been sent.',
      TONE.DONE, DOMAIN.MONEY, [ACTION.VIEW]),

    /* -- a purchase plan is an intention and charges nobody. The labels say
          "plan" in every one of them so that no line here can be misread as
          money having moved. */
    'plan:ACTIVE': S('Plan running',
      'Your plan is set. Nothing is charged automatically.',
      TONE.NEUTRAL, DOMAIN.MONEY, [ACTION.PAUSE]),
    'plan:PAUSED': S('Plan paused',
      'On hold, and nothing about it is lost.',
      TONE.WAITING, DOMAIN.MONEY, [ACTION.RESUME]),
    'plan:STOPPED': S('Plan stopped',
      'Finished. Starting again begins a new plan, and this one stays on record.',
      TONE.ENDED, DOMAIN.MONEY, [ACTION.PLAN]),

    /* -- travel ------------------------------------------------------------ */
    'booking:REQUESTED': S('Journey requested',
      'We have your journey and somebody is reading it.',
      TONE.WORKING, DOMAIN.TRAVEL, [ACTION.WAIT, ACTION.CANCEL]),
    'booking:ACCEPTED': S('Journey accepted',
      'We can run this journey. Next it is reserved.',
      TONE.WORKING, DOMAIN.TRAVEL, [ACTION.VIEW, ACTION.CANCEL]),
    'booking:REJECTED': S('Journey not accepted',
      'We cannot run this one, and we will say what would work instead.',
      TONE.ENDED, DOMAIN.TRAVEL, [ACTION.CONTACT, ACTION.PLAN]),
    'booking:RESERVED': S('Journey reserved',
      'Held for you, at the price shown. That price is now locked.',
      TONE.WAITING, DOMAIN.TRAVEL, [ACTION.CONFIRM, ACTION.CANCEL]),
    'booking:CONFIRMED': S('Journey confirmed',
      'It is booked. The price cannot change from here.',
      TONE.DONE, DOMAIN.TRAVEL, [ACTION.VIEW, ACTION.CANCEL]),
    'booking:CANCELLED': S('Journey cancelled',
      'This journey is off, and anything held for it has been released.',
      TONE.ENDED, DOMAIN.TRAVEL, [ACTION.PLAN]),
    'booking:REDEEMED': S('Journey travelled',
      'You went. This is the end of the journey, not of the account.',
      TONE.DONE, DOMAIN.TRAVEL, [ACTION.VIEW]),

    /* -- THE JOURNEY'S OWN STAGES, and the one vocabulary I nearly duplicated.
          The first draft of this file invented `goal:NO_TARGET / UNDERWAY /
          FUNDED`, on the belief that the Travel Goal had no state vocabulary
          and that `funded` was a boolean computed inline.

          It is not. travel-goal.js line 89 says so in capitals: "D11: THE
          JOURNEY STATE, WHICH IS THE VOCABULARY THIS PRODUCT USES. A financial
          wallet has a balance; a journey has a stage." It exports
          `journeyState` and the full six-stage list beside it, and has done
          all along.

          Inventing a parallel set would have been precisely the defect this
          whole file exists to prevent — two vocabularies for one thing, with
          nothing comparing them — and it would have been committed inside the
          module written to stop that happening. These are the six the product
          already uses. Nothing here is new. */
    'journey:PLANNING': S('Planning this journey',
      'You are working out what it takes. Nothing is booked and nothing is owed.',
      TONE.NEUTRAL, DOMAIN.TRAVEL, [ACTION.PLAN]),
    'journey:FUNDED': S('Journey funded',
      'You have reached what this journey takes. This is the beginning of '
        + 'booking, not the end of saving.',
      TONE.DONE, DOMAIN.TRAVEL, [ACTION.PLAN]),
    'journey:BOOKING': S('Being booked',
      'We are turning this into a real itinerary with the people who run it.',
      TONE.WORKING, DOMAIN.TRAVEL, [ACTION.WAIT]),
    'journey:RESERVED': S('Held for you',
      'Your place is held at the price you were shown.',
      TONE.WAITING, DOMAIN.TRAVEL, [ACTION.CONFIRM, ACTION.CANCEL]),
    'journey:TRAVELLING': S('Travelling',
      'You are on it. This is the part the rest was for.',
      TONE.WORKING, DOMAIN.TRAVEL, [ACTION.CONTACT]),
    'journey:COMPLETED': S('Journey complete',
      'You went and you came back. The record stays with you.',
      TONE.DONE, DOMAIN.TRAVEL, [ACTION.PLAN]),

    /* -- account ----------------------------------------------------------
          What the customer is PERMITTED to do, which is a different question
          from what they hold. */
    'account:UNVERIFIED': S('Not verified yet',
      'You can plan and explore. Holding or moving points needs verification.',
      TONE.NEUTRAL, DOMAIN.ACCOUNT, [ACTION.VERIFY]),
    'account:VERIFIED': S('Verified',
      'Everything on your account is open to you.',
      TONE.NEUTRAL, DOMAIN.ACCOUNT, [ACTION.NONE]),
    'account:RESTRICTED': S('Temporarily limited',
      'Some actions are paused while we check something. You keep what you hold.',
      TONE.WAITING, DOMAIN.ACCOUNT, [ACTION.CONTACT]),
    'account:CLOSED': S('Account closed',
      'Closed. The record of what happened stays, and we can still talk to you.',
      TONE.ENDED, DOMAIN.ACCOUNT, [ACTION.CONTACT]),

    'auth:NONE': S('Signed out',
      'Planning needs no account. Anything you own does.',
      TONE.NEUTRAL, DOMAIN.ACCOUNT, [ACTION.NONE]),
    'auth:NORMAL': S('Signed in',
      'You are signed in.',
      TONE.NEUTRAL, DOMAIN.ACCOUNT, [ACTION.NONE]),
    'auth:STEP_UP': S('One more confirmation needed',
      'This one matters enough that we would like to be sure it is you.',
      TONE.WAITING, DOMAIN.ACCOUNT, [ACTION.CONFIRM]),

    /* -- what the platform is doing --------------------------------------
          Risk decisions are shown to a customer in the softest true form.
          "HOLD" is not "you are a suspect", it is "we are checking", because
          absent signals produce a hold and most holds are nobody's fault. */
    'risk:ALLOW': S('Checks passed',
      'Nothing needed looking at.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.NONE]),
    'risk:HOLD': S('Being checked',
      'We are looking at this before it goes ahead. It is usually quick.',
      TONE.WAITING, DOMAIN.SYSTEM, [ACTION.WAIT]),
    'risk:REJECT': S('Cannot go ahead',
      'This one cannot proceed. Talk to us and a person will look again.',
      TONE.BROKEN, DOMAIN.SYSTEM, [ACTION.CONTACT]),

    'hold:HELD': S('Waiting on a review',
      'Somebody is reviewing this. Nothing has been decided against you.',
      TONE.WAITING, DOMAIN.SYSTEM, [ACTION.WAIT]),
    'hold:RELEASED': S('Review cleared',
      'The review is finished and this can carry on.',
      TONE.DONE, DOMAIN.SYSTEM, [ACTION.VIEW]),
    'hold:REJECTED': S('Review did not clear',
      'The review stopped this. Talk to us and we will explain what we can.',
      TONE.BROKEN, DOMAIN.SYSTEM, [ACTION.CONTACT]),

    /* -- the programme itself. Almost none of this belongs on a customer
          screen, and it is written here anyway: the moment one of these DOES
          need showing — a suspension, a redemption period — the sentence
          should already exist rather than being invented under pressure. */
    'programme:DRAFT': S('Programme in draft',
      'Being designed. Nothing can be bought or issued.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:LEGAL_REVIEW': S('Programme with our lawyers',
      'Under legal review before anything can be offered.',
      TONE.WORKING, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:ACCOUNTING_REVIEW': S('Programme with our accountants',
      'Under accounting review before anything can be offered.',
      TONE.WORKING, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:APPROVED': S('Programme approved, not started',
      'Cleared to begin, and not begun. Still nothing to buy.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:PILOT': S('Programme in pilot',
      'Running with a small group before it opens.',
      TONE.WORKING, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:ACTIVE': S('Programme open',
      'Open, subject to the same checks everything else is.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.NONE]),
    'programme:CLOSED_TO_NEW_PURCHASES': S('Closed to new purchases',
      'No new points are being sold. Everything you hold still works.',
      TONE.WAITING, DOMAIN.SYSTEM, [ACTION.PLAN]),
    'programme:REDEMPTION_PERIOD': S('Winding down',
      'The programme is ending. What you hold can still be used, until a date '
        + 'we will tell you.',
      TONE.WAITING, DOMAIN.SYSTEM, [ACTION.PLAN, ACTION.CONTACT]),
    'programme:CLOSED': S('Programme closed',
      'Closed. If you still hold anything we will have written to you.',
      TONE.ENDED, DOMAIN.SYSTEM, [ACTION.CONTACT]),
    'programme:SUSPENDED': S('Programme paused',
      'Paused while something is resolved. Nothing you hold is lost.',
      TONE.WAITING, DOMAIN.SYSTEM, [ACTION.CONTACT]),
    'programme:RETIRED': S('Programme retired',
      'Finished for good, and kept on record.',
      TONE.ENDED, DOMAIN.SYSTEM, [ACTION.VIEW]),

    'product:PLANNING': S('Planning only',
      'Everything here is an estimate. Nothing is for sale.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.PLAN]),
    'product:DRAFT_PROGRAM': S('Not issuing yet',
      'The programme exists on paper and cannot issue anything.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.PLAN]),
    'product:ACTIVE_PROGRAM': S('Issuing',
      'The programme can issue Travel Points.',
      TONE.NEUTRAL, DOMAIN.SYSTEM, [ACTION.NONE])
  };

  /* ---- reading it ------------------------------------------------------- */

  function key(vocab, state) { return String(vocab) + ':' + String(state); }

  function describe(vocab, state) {
    return LANGUAGE[key(vocab, state)] || null;
  }

  /* THE TRANSITION TABLES, READ FROM THE MODULES THAT OWN THEM.
     Deliberately not copied. A vocabulary with no table in code returns null,
     which is different from returning [] — "nobody wrote one down" is not the
     same news as "this state is terminal". */
  var TABLES = {
    booking:   Booking && Booking.BOOKING_NEXT,
    buyback:   Buyback && Buyback.REQUEST_NEXT,
    programme: Points && Points.COMPLIANCE_NEXT,
    plan:      Plan && Plan.PLAN_NEXT,
    hold:      Risk && Risk.HOLD_NEXT
  };

  function nextOf(vocab, state) {
    var t = TABLES[vocab];
    if (!t) return null;
    return t[state] || [];
  }

  /* The journey's stage, READ off the goal rather than recomputed from its
     numbers. travel-goal.js decides this and is the only thing that should:
     a second derivation here would agree today and disagree the first time
     the rule changed, and the reader would be shown whichever of the two the
     surface happened to ask. */
  function journeyStateOf(goal) {
    return (goal && goal.journeyState) || null;
  }

  function toneOf(vocab, state) {
    var d = describe(vocab, state);
    return d ? d.tone : null;
  }

  /* What a surface writes into the DOM. One class and one data attribute, so
     that CSS styles the tone and a check can read the state back off the page
     and compare it with this file. */
  function attrs(vocab, state) {
    var d = describe(vocab, state);
    if (!d) return null;
    return {
      'class': 'af-state af-state--' + d.tone,
      'data-state': key(vocab, state),
      'data-domain': d.domain
    };
  }

  /* Every key, for the checks and for anything that wants to render the whole
     table — the documentation page builds itself from this rather than from a
     list somebody keeps in step by hand. */
  function all() { return Object.keys(LANGUAGE).slice(); }

  return {
    TONE: TONE, DOMAIN: DOMAIN, ACTION: ACTION,
    LANGUAGE: LANGUAGE, TABLES: TABLES,
    key: key, describe: describe, nextOf: nextOf,
    toneOf: toneOf, attrs: attrs, all: all, journeyStateOf: journeyStateOf
  };
});
