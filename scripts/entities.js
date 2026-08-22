/* Who is acting, and why. The three-layer entity model.
 *
 * @product: live | @gate: none | @surface: /trust (rendered at build time by tools/tourism/trust_page.py)
 * ===========================================================================
 * Three companies' worth of responsibility run through this product, and a
 * customer is entitled to know which one they are dealing with at any moment.
 *
 *     AFRINKONG    experience    discover -> explore -> plan -> journey -> enquire
 *     WANKONG LLC  commercial    Travel Points, programmes, agreements, the
 *                                ledger, and eventually payment
 *     OPERATOR     operations    destination operations, suppliers, local
 *                                execution, the operational desk
 *
 * They are already in the data — company.json carries `brand`, `legal` and the
 * sentence "Afrinkong is a trading name of Wankong LLC", and operators.json
 * carries three named ground operations. What did not exist was any model of
 * WHICH ONE ACTS FOR A GIVEN THING, so nothing could be asked.
 *
 * THE MISTAKE THIS FILE EXISTS TO CORRECT
 *
 * The first guard on this boundary classified links BY URL: a list of paths
 * belonging to the operator, forbidden in certain places. That is wrong twice
 * over.
 *
 *   /cameroon  is Cameroon, one of fifty-four countries, and belongs in
 *              Explore. It is also where a ground operation is based. The URL
 *              cannot tell you which of those a given link means.
 *
 *   /contact   is an operator desk, and is perfectly correct on a page where
 *              the visitor is explicitly dealing with that operator.
 *
 * A link is classified by four things together — ENTITY, CONTEXT, POSITION and
 * ACTION — and any one of them alone gives the wrong answer.
 *
 * THE RULE THAT MATTERS MOST, AND MATTERS MORE EVERY MONTH
 *
 * A booking or payment flow must never silently move a customer from
 * Afrinkong's journey into the operator's desk BECAUSE THAT DESK ALREADY HAS
 * THE INFRASTRUCTURE. That is the cheapest wrong turn available: the form
 * exists, it works, and pointing at it saves a week. It also makes the brand a
 * referrer to its own supplier, and once money moves it makes the question
 * "who did I pay" unanswerable from the screen the customer was looking at.
 *
 * So every act in ACTS below names its actor, and the six that touch a
 * customer's money, entitlement or trip must DECLARE that actor on the surface
 * where they happen. Not in a footer. On the surface.
 *
 * Pure. No DOM, no network, no clock.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongEntities = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var ENTITY = {
    AFRINKONG: 'afrinkong',
    WANKONG:   'wankong',
    OPERATOR:  'operator'
  };

  /* The three layers, described in the terms a customer would recognise rather
     than in the terms a company register would. `legal` is the name that goes
     on anything with consequences. */
  var LAYER = {
    afrinkong: {
      layer: 'experience',
      name: 'Afrinkong',
      legal: null,               /* a trading name, not an entity */
      does: 'Shows you Africa, and helps you turn that into a journey.',
      owns: ['explore', 'plan', 'enquire']
    },
    wankong: {
      layer: 'commercial',
      name: 'Wankong LLC',
      legal: 'Wankong LLC',
      does: 'The company you contract with, and the one anything you pay goes '
          + 'to. Afrinkong is its trading name.',
      owns: ['book', 'pay', 'cancel', 'points']
    },
    operator: {
      layer: 'operations',
      name: null,                /* named per country, from operators.json */
      legal: null,
      does: 'The people on the ground who actually run your days.',
      owns: ['operate', 'desk']
    }
  };

  /* THE SIX THAT MUST DECLARE.
     The customer's money, their entitlement, or their trip. Every one of these
     needs the acting entity stated where it happens — which is the whole
     requirement, and the reason this is a module and not a comment. */
  var MUST_DECLARE = ['enquire', 'book', 'pay', 'cancel', 'points', 'support'];

  var ACTS = {
    /* Afrinkong's own — no money, no obligation, no contract. */
    explore: { actor: ENTITY.AFRINKONG, declares: false,
               why: 'Reading about somewhere commits you to nothing.' },
    plan:    { actor: ENTITY.AFRINKONG, declares: false,
               why: 'A plan is an intention. Nothing is held and nothing is '
                  + 'charged.' },

    /* The enquiry is Afrinkong's, and the answer may come from an operator.
       Both halves are true and the customer should be told both. */
    enquire: { actor: ENTITY.AFRINKONG, declares: true,
               also: ENTITY.OPERATOR,
               why: 'You are writing to Afrinkong. Where the journey is one a '
                  + 'local operation runs, they answer it.' },

    /* The commercial layer. Everything here is Wankong LLC and says so. */
    book:    { actor: ENTITY.WANKONG, declares: true, also: ENTITY.OPERATOR,
               why: 'The booking is an agreement with Wankong LLC. The days '
                  + 'themselves are run on the ground.' },
    pay:     { actor: ENTITY.WANKONG, declares: true,
               why: 'Money is paid to Wankong LLC, not to Afrinkong and not to '
                  + 'the operator.' },
    cancel:  { actor: ENTITY.WANKONG, declares: true,
               why: 'A cancellation is against the agreement, so it is Wankong '
                  + 'LLC that answers for it.' },
    points:  { actor: ENTITY.WANKONG, declares: true,
               why: 'Travel Points are issued by Wankong LLC under a programme '
                  + 'with written terms.' },

    /* Support splits, and the split is the useful part: before you travel it
       is Afrinkong, on the ground it is the people who are with you. */
    support: { actor: ENTITY.AFRINKONG, declares: true, also: ENTITY.OPERATOR,
               why: 'Before you travel, Afrinkong. While you are travelling, '
                  + 'the operation running your days.' },

    /* The operator's own. */
    operate: { actor: ENTITY.OPERATOR, declares: false,
               why: 'The ground operation running the country.' },
    desk:    { actor: ENTITY.OPERATOR, declares: true,
               why: 'This is the operator’s own desk, not Afrinkong’s.' }
  };

  function actor(act) {
    var a = ACTS[act];
    return a ? a.actor : null;
  }

  function mustDeclare(act) {
    return MUST_DECLARE.indexOf(act) !== -1;
  }

  /* THE DECLARATION A SURFACE HAS TO CARRY.
     `operatorName` comes from operators.json via the page that knows which
     country it is about; there is no default, because "the operator" without a
     name is exactly the vagueness this is against. */
  function declare(act, operatorName) {
    var a = ACTS[act];
    if (!a) return null;
    var who = LAYER[a.actor];
    var out = {
      act: act,
      entity: a.actor,
      layer: who.layer,
      name: who.name || operatorName || null,
      legal: who.legal,
      why: a.why,
      declares: !!a.declares
    };
    if (a.also) {
      var other = LAYER[a.also];
      out.and = {
        entity: a.also,
        layer: other.layer,
        name: other.name || operatorName || null
      };
    }
    return out;
  }

  /* ---- classifying a link ------------------------------------------------
   *
   * NOT BY URL. Four inputs, and the answer needs all four:
   *
   *   href      where it goes
   *   context   what the surrounding surface is about — the country whose
   *             page this is, or the entity the visitor is currently dealing
   *             with
   *   position  where on the page it sits. `nav`, `footer-nav`, `cta` and
   *             `body` are not decoration: a link in the primary navigation is
   *             a statement about the product's shape, and the same href in a
   *             paragraph is a reference
   *   act       what pressing it does
   *
   * The same href gets different answers. /contact in a paragraph on the
   * operator's own page is `operational`; /contact as the primary button on
   * Afrinkong's homepage is `misdirected`, which is the failure this whole
   * file is about.
   */
  var POSITION = ['nav', 'footer-nav', 'cta', 'body'];
  var VERDICT = {
    OWN:          'own',           /* the acting entity's own surface     */
    OPERATIONAL:  'operational',   /* another entity, in context, in body */
    HANDOVER:     'handover',      /* another entity, and declared        */
    MISDIRECTED:  'misdirected'    /* another entity, as a customer CTA   */
  };

  function classify(link) {
    var pos = POSITION.indexOf(link.position) >= 0 ? link.position : 'body';
    var target = link.targetEntity || ENTITY.AFRINKONG;
    var surface = link.surfaceEntity || ENTITY.AFRINKONG;

    if (target === surface) return VERDICT.OWN;

    /* Crossing an entity boundary. Where it sits decides what it is. */
    if (pos === 'nav' || pos === 'footer-nav' || pos === 'cta') {
      /* A declared handover is legitimate anywhere — that is the point of
         declaring it. An undeclared one in a customer position is not. */
      return link.declared ? VERDICT.HANDOVER : VERDICT.MISDIRECTED;
    }
    return link.declared ? VERDICT.HANDOVER : VERDICT.OPERATIONAL;
  }

  return {
    ENTITY: ENTITY, LAYER: LAYER, ACTS: ACTS, MUST_DECLARE: MUST_DECLARE,
    POSITION: POSITION, VERDICT: VERDICT,
    actor: actor, mustDeclare: mustDeclare, declare: declare,
    classify: classify
  };
});
