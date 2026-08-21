"""/travel-points — what a Travel Point is, and what it is not.

    python3 tools/tourism/build.py points

THE GAP THIS CLOSES.

Measured, and it was worse than it sounded. The repository holds about 10,900
lines of product and economic JavaScript, 9,800 lines of checks and 10,000
lines of architecture documents. The number of pages a visitor could open that
explain any of it was **zero**. Eight modules — account, booking, buyback,
entities, journey-catalogue, purchase-plan, risk, transfer, 1,973 lines — were
loaded by no page at all.

That is not merely a marketing omission. The Journey Fund **already shows a
customer a number denominated in Travel Points** — the Estimated Travel Goal,
which CLAUDE.md describes as "the same journey estimate in point units". So
the site prints a unit it has nowhere defined. A visitor who reads "4,800 TP"
and wants to know what a TP is has, today, nowhere to go.

This page is that somewhere. It is the explanatory half of the FUND layer, and
it is deliberately not the operational half.

TWO KINDS OF MANIFESTATION, AND ONLY ONE IS GATED.

    operational   the customer can DO it — buy, hold, transfer, redeem
                  gated by compliance. Correctly absent. Not built here.

    explanatory   the customer can UNDERSTAND what exists, who is responsible,
                  and what is not live. Gated by nothing. Was also absent,
                  and that was an oversight rather than a decision.

Treating those two as one thing is why a fully-specified economic model has no
surface. This page builds the second and refuses the first: there is no price,
no basket, no button, and nothing to buy.

WHY THE FACTS ARE READ FROM THE LEDGER RATHER THAN TYPED.

This codebase's recurring failure is two things that had to agree with nothing
comparing them — a sentence beside a generated block, a check pinned to a class
name, a masthead breakpoint hand-edited into a generated file. A page that
states the programme's identity and compliance state in prose is exactly that
shape of hazard: the ladder moves, and the page goes on saying DRAFT.

So the programme facts are parsed out of `scripts/points-ledger.js` at build
time, and `points-checks.js` asserts the rendered page agrees with the module.
Neither can move without the other.

WHAT THIS PAGE DELIBERATELY DOES NOT PRINT.

The issue rate and the entitlement rate. Decision I permits money against a
transaction and forbids it against a holding, so a rate is not itself illegal
copy — but publishing "$1 buys 1 TP" while `compliance` is DRAFT and nothing is
on sale reads as an offer, and a standing figure becomes the definition of the
point whatever the terms say. Rates belong beside a purchase, and there is no
purchase. When the programme opens, its terms are published with it.
"""

import os
import re

from . import company, plate
from .model import ROOT

PAGE = os.path.join(ROOT, "travel-points.html")
LEDGER = os.path.join(ROOT, "scripts", "points-ledger.js")

# The band comes from the family that owns it. This page is a fourth member of
# the Journey Fund family, not a family of its own, so it must not hold its own
# copy of the list — I wrote one, noticed it was the same duplication I had
# just spent an hour removing from the disclosure panels, and deleted it.
from .fund import FUND_NAV  # noqa: E402  (imported for its value, not its API)


def esc(v):
    return plate.esc(v)


def programme():
    """The facts, from the ledger that owns them.

    Narrow on purpose: only the fields this page states. A wider parser would
    be a second copy of the programme, which is the thing being avoided.
    """
    src = open(LEDGER, encoding="utf-8").read()
    # The programme closes at four spaces; every nested group inside it closes
    # at six or more, so this is the first four-space brace after the opener
    # and cannot land in the middle of one of its own sub-objects.
    block = re.search(r"'AFK-TP-2026\.1':\s*\{(.*?)\n    \}", src, re.S)
    if not block:
        raise ValueError(
            "points_page: could not find the programme in scripts/points-ledger.js "
            "— the shape it is declared in has changed, and this page would "
            "otherwise render whatever it last found. Fix the parser rather "
            "than typing the values in.")
    body = block.group(1)

    def field(name):
        m = re.search(r"\b%s:\s*'([^']*)'" % name, body)
        if not m:
            raise ValueError(
                "points_page: the programme has no %s. This page states it, so "
                "a missing value must stop the build rather than print an "
                "empty sentence." % name)
        return m.group(1)

    ladder = re.search(r"COMPLIANCE_STATES\s*=\s*\[([^\]]*)\]", src)
    if not ladder:
        raise ValueError("points_page: no COMPLIANCE_STATES in the ledger")
    states = re.findall(r"'([A-Z_]+)'", ladder.group(1))

    # COMPLIANCE_STATES holds two different things in one list: the rungs a
    # programme climbs to become issuable, and the states it ends its life in
    # — CLOSED_TO_NEW_PURCHASES, REDEMPTION_PERIOD, CLOSED, SUSPENDED, RETIRED.
    # Drawing all eleven as a ladder would tell a customer that a programme
    # progresses toward RETIRED, which is the opposite of what those states
    # mean. ACTIVE is the last rung of the climb, so the cut is taken from the
    # list rather than written as a number that would silently be wrong if a
    # rung were ever inserted.
    if "ACTIVE" not in states:
        raise ValueError(
            "points_page: ACTIVE is not in COMPLIANCE_STATES, so the end of "
            "the activation ladder cannot be located. The page draws that "
            "ladder and must not guess where it stops.")
    rungs = states[:states.index("ACTIVE") + 1]

    return {
        "id": field("id"),
        "name": field("name"),
        "issuer": field("issuer"),
        "brand": field("brand"),
        "compliance": field("compliance"),
        "rungs": rungs,
    }


def ladder_html(prog):
    """The compliance ladder, with the rung the programme is actually on.

    Drawn rather than described because "not skippable" is a property of a
    sequence, and a sequence is a thing to look at. The current rung is marked
    with aria-current so the fact survives with no styling and no sight.
    """
    here = prog["compliance"]
    out = []
    for rung in prog["rungs"]:
        is_here = rung == here
        out.append(
            '<li class="jf-rung%s"%s>%s%s</li>'
            % (" is-here" if is_here else "",
               ' aria-current="step"' if is_here else "",
               esc(rung.replace("_", " ").title()),
               ' <b>&larr; the programme is here</b>' if is_here else ""))
    return "\n      ".join(out)


def render(prog, co):
    return TEMPLATE % {
        "og": plate.open_graph(
            "What a Travel Point is \u2014 Afrinkong",
            "A unit of travel purchasing entitlement issued by %s. Not money, "
            "not a deposit, not an investment. Nothing is on sale today."
            % prog["issuer"],
            "/travel-points"),
        "preload": plate.PRELOAD,
        "mast": plate.shell(here="/travel-points", area="plan",
                            product="The Journey Fund",
                            product_href="/journey-fund",
                            product_nav=FUND_NAV),
        "foot": plate.colophon_foot("/travel-points"),
        "events": plate.events_block(),
        "issuer": esc(prog["issuer"]),
        "brand": esc(prog["brand"]),
        "progid": esc(prog["id"]),
        "progname": esc(prog["name"]),
        "compliance": esc(prog["compliance"]),
        "ladder": ladder_html(prog),
    }


def run(log=print):
    prog = programme()
    co = company.load()
    html = render(prog, co)
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("points page: /travel-points (%.1f KB) \u2014 %s, compliance %s"
        % (len(html) / 1024.0, prog["id"], prog["compliance"]))
    return [PAGE]


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What a Travel Point is &mdash; Afrinkong</title>
<meta name="description" content="A unit of travel purchasing entitlement issued by %(issuer)s. Not money, not a deposit, not an investment. Nothing is on sale today.">
%(og)s
<meta name="theme-color" content="#10251F">
%(preload)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/fund.css">
</head>
<body class="af af--fund jf-page" data-area="plan">
<a class="af-skip" href="#what">Skip to what a Travel Point is</a>
%(mast)s
<main>
  <section class="jf-frame jf-open jf-open--short">
    <h1>What a Travel Point is</h1>
    <p class="jf-sub">The Journey Fund shows you a number of Travel Points,
      so this page says what one is before you are ever asked to hold one.
      <b>Nothing on this site sells them today.</b></p>
  </section>

  <div class="jf-frame jf-qs" id="what">
    <article class="jf-q">
      <h2>The definition</h2>
      <p class="jf-said">A Travel Point is one unit of travel purchasing
        entitlement issued by <b>%(issuer)s</b> under a named Travel Point
        Programme, redeemable toward eligible Afrinkong travel services on the
        terms of the programme under which it was issued.</p>
      <p>Every clause in that sentence is load-bearing. It is
        <i>entitlement</i>, not money. It is issued by a <i>company</i>, not by
        a brand. It belongs to a <i>named programme</i>, not to the site in
        general. And it is redeemable on <i>that programme's</i> terms, not on
        whichever terms happen to be current when you come to use it.</p>
    </article>

    <article class="jf-q">
      <h2>What it is not</h2>
      <p>Stated plainly, because the things it is not are the things people
        reasonably assume it might be.</p>
      <ul class="jf-nots">
        <li><b>Not money.</b> A Travel Point has no cash denomination. You will
          not find a figure on this site telling you what your points are
          &ldquo;worth&rdquo;, because a standing figure like that becomes the
          definition of the point whatever the written terms say.</li>
        <li><b>Not a deposit.</b> Nothing is held on your behalf in an account.</li>
        <li><b>Not a bank account</b>, and not a substitute for one.</li>
        <li><b>Not an investment</b>, and not interest-bearing. Points do not
          grow, earn or accrue.</li>
        <li><b>Not a claim on cash.</b> A programme may offer to repurchase
          eligible points on stated terms; that is a specific offer about
          specific points, not a valuation of a holding.</li>
      </ul>
    </article>

    <article class="jf-q">
      <h2>Who issues it, and why that is not %(brand)s</h2>
      <p><b>%(issuer)s</b> issues Travel Points. %(brand)s is a trading name of
        that company &mdash; it is the experience you are reading, and it
        issues nothing, because a trading name is not a party to anything.</p>
      <p>The same separation runs through everything that touches money or
        entitlement. Journeys are quoted, invoiced and settled to %(issuer)s.
        The days themselves are run by a named local operation in the country
        you travel to. Three responsibilities, three names, and you are
        entitled to know which one you are dealing with at any moment.</p>
    </article>

    <article class="jf-q">
      <h2>Programmes, and why a point remembers the one that made it</h2>
      <p>Travel Points are issued under a <b>named, versioned programme</b>. A
        programme fixes the issuer, the rate, what the points may be redeemed
        against, whether they may be transferred, what happens on cancellation,
        whether they may be repurchased, and when they expire.</p>
      <p>Once a point exists, those terms are <b>its</b> terms. A later
        programme may set different ones, and it does not reach backwards: a
        point issued under one programme cannot be quietly reinterpreted under
        another. That is why programmes carry versions rather than being
        edited.</p>
      <p class="jf-fine">The current programme is
        <b>%(progname)s</b> <code>%(progid)s</code>.</p>
    </article>

    <article class="jf-q">
      <h2>What is live today: nothing</h2>
      <p>No Travel Point has been issued. None can be. The programme is at
        <b>%(compliance)s</b> on a compliance sequence that has to be walked
        rung by rung, and issuance is refused at every rung before the last.</p>
      <ol class="jf-ladder">
      %(ladder)s
      </ol>
      <p>Reaching the last rung is <b>still not sufficient</b>. Approval and
        operation are separate decisions: a programme that has cleared the
        ladder issues nothing until issuance is separately enabled, which is
        its own act testing whether the operation is actually ready. Either one
        alone does nothing.</p>
      <p>Until both are true, the Travel Points you see quoted anywhere on this
        site &mdash; including the Estimated Travel Goal in the Journey Fund
        &mdash; are <b>arithmetic about a journey</b>, not a holding, not a
        balance, and not a thing anyone is keeping for you.</p>
    </article>

    <article class="jf-q">
      <h2>What the Journey Fund is showing you</h2>
      <p>The Journey Fund prices a journey and then expresses that estimate in
        point units, so that the requirement is legible in the unit the
        programme would eventually use. It is a target, in the way a distance
        is a target.</p>
      <p><b>It is not a wallet.</b> The Fund takes no payment, opens no
        account, holds nothing, and has no way of knowing whether you have put
        anything aside at all. <a href="/journey-fund/how-it-works">How it
        works</a> says where the money sits, which is: in your own bank
        account.</p>
    </article>

    <article class="jf-q">
      <h2>Start with the journey, not the unit</h2>
      <p>A Travel Point only ever means something against a particular journey,
        so the useful order is the opposite of this page&rsquo;s:
        <a href="/journey">build a journey</a> first, and the unit follows from
        what it costs. <a href="/journey-fund">The Journey Fund</a> will then
        show you the requirement in both.</p>
    </article>
  </div>
</main>
%(foot)s
%(events)s
</body>
</html>
"""
