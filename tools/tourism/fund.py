"""The Journey Fund: /journey-fund and the two pages under it.

WHAT THIS IS, AND — MORE IMPORTANTLY — WHAT IT IS NOT

The Journey Fund is a way of arriving at an Afrinkong journey, not a third
product beside Afrinkong and Trans Afrique. A traveller who wants Kenya in
September 2028 can work out today what that costs, what putting something
aside every month would have to look like to reach it, and what they need to
have done — passport first, because six months' validity makes it a today
problem — long before anybody discusses money.

**Afrinkong holds nothing.** No account, no balance, no card, no charge, no
custody. The traveller's money stays in the traveller's own bank, and this
product's entire job is arithmetic, a calendar and a reminder. That is not a
reduced version of something else; it is the whole of what these three pages
do, and it is why they can exist at all while the questions about holding
customer money are still with the people who are qualified to answer them.

Everything on these pages is therefore true without a single regulatory
assumption, and the pages say so in those words rather than implying it.

THE FIGURES

Not one of them is written here. The tiers, the durations, the arrival charge
and the crossing bands all come from tourism/rates.json and
tourism/transafrique.json, and rates.drift() is run over the finished HTML to
prove that no dollar figure reached the page that those files cannot account
for. That guard already existed for the journey builder — it was written after
an opening plate said $350 for as long as it took somebody to scroll one
section further and read $650 — and these pages join it rather than acquiring
a second one.

The one arithmetic decision worth recording: the month strip is built in the
browser from the reader's own clock, not here. A static page built in August
that offers "September 2026" as the soonest month is wrong the following
spring and stays wrong silently, which is the worst way for a page to be
wrong. The server renders the default journey's total so the page is complete
and correct with scripting off; the calendar is the browser's job because only
the browser knows what day it is.

THE COLOUR

There isn't one. The Journey Fund takes the region tone of the place being
built toward — a Kenya plan is East Africa's teal, a Morocco plan is North
Africa's ochre — read from tourism/regions.json, the same five the atlas and
the country plates use. They travel to the browser in the estimator's payload
and are set as a custom property, so there is no second copy of those five
values in a stylesheet to be wrong about. A traveller changing their mind about the destination changes the colour
of the page, because the page is about the destination.
"""

import json
import os

from . import company, plate, rates
from .model import ROOT, load_countries, load_regions, region_of

DIR = os.path.join(ROOT, "journey-fund")
LANDING = os.path.join(ROOT, "journey-fund.html")
HOW = os.path.join(DIR, "how-it-works.html")
ASKED = os.path.join(DIR, "questions.html")

CROSSINGS = os.path.join(ROOT, "tourism", "transafrique.json")
PICKS = os.path.join(ROOT, "tourism", "picks.json")

# The photograph. Already placed, already optimised, already carrying a written
# alt text on the Trans Afrique pages — a convoy on a road at dusk. The
# creative direction asks for a photograph a traveller can look at forty times
# over two years without it wearing out, which rules out the spectacular one:
# the road is for anticipating, the summit is for wanting.
SHOT = "/images/uploads/cross-convoy-on-the-road"
SHOT_ALT = ("A convoy of expedition vehicles on a tarmac road at dusk, seen "
            "from inside one of them, with a family walking along the verge "
            "under acacia trees")
SHOT_W, SHOT_H = 1600, 1067


def esc(v):
    return plate.esc(v)


# --- the data the browser needs to do the arithmetic -------------------------


def payload(countries, regions, crossings, money):
    """-> what the estimator is given, as small as it can honestly be.

    Slug, name and region for each published country; the crossing bands; the
    rate card's own numbers. No prose, no photographs, no place lists — the
    estimator prices a journey and does not describe one, and every kilobyte
    here is on the critical path of a page whose whole argument is that it
    answers instantly.

    The rate card's version travels with it. A plan kept in a browser in March
    and reopened in September was priced against a rate card that may have
    moved, and without the version there is no way for the page to know that,
    let alone say it.
    """
    tone = {}
    for key, region in (regions or {}).items():
        colour = getattr(region, "tone", None) or getattr(region, "colour", None)
        if colour:
            tone[key] = colour

    places = []
    for c in countries:
        if not c.published or not c.slug:
            continue
        # region_of, not c.region. The country files carry the region's
        # DISPLAY NAME — "East Africa" — and the tones are keyed by its slug.
        # Using the wrong one is invisible: every destination simply falls back
        # to basalt and the whole tone system is quietly dead. It was, until a
        # check asserted that every country in this payload names a region that
        # has a tone.
        key, _reg = region_of(c, regions)
        places.append({
            "s": c.slug,
            "n": c.name,
            "r": key,
        })
    places.sort(key=lambda p: p["n"])

    routes = []
    for r in crossings.get("routes", []):
        routes.append({
            "s": r["id"],
            "n": r["name"],
            "d": r["days"],
            "lo": r["low"],
            "hi": r["high"],
            "c": len(r.get("countries") or []),
            # A crossing spans regions, so it has no single tone. It takes the
            # tone of the region it opens in, which is the one a traveller
            # pictures when they picture the route.
            "r": _route_region(r, countries, regions),
        })

    return {
        "v": rates.version(money),
        "tiers": [{"id": t["id"], "name": t["name"], "rate": t["rate"],
                   "line": t["line"]} for t in money["tiers"]],
        "days": money["durations"],
        "arrival": money["arrival"]["rate"],
        "default": {"tier": money["default_tier"], "days": money["default_days"]},
        "countries": places,
        "first": opens_on(countries),
        "routes": routes,
        "tones": tone,
    }


def opens_on(countries):
    """Which destination the estimator shows before anybody has chosen one.

    It was whichever country sorts first alphabetically, which is Algeria — a
    real country, a real journey, and a completely arbitrary answer to "what
    does Africa cost". A page that opens on an accident is a page that has not
    decided anything.

    So it opens on the site's own editorial lead for wildlife, which
    tourism/picks.json names, and which is also one of the three countries
    where the ground operation is Afrinkong's own. The worked example is
    therefore a journey the company runs end to end, chosen by the file that
    already exists to make that kind of choice. Change the pick and this
    changes with it.
    """
    try:
        with open(PICKS, encoding="utf-8") as fh:
            picks = json.load(fh)
        want = (picks.get("wildlife") or {}).get("country")
    except (IOError, ValueError, AttributeError):
        want = None
    have = {c.slug for c in countries if c.published and c.slug}
    if want in have:
        return want
    return sorted(have)[0] if have else ""


def _route_region(route, countries, regions):
    """The region a crossing opens in — its first country's."""
    first = (route.get("countries") or [None])[0]
    for c in countries:
        if c.slug == first:
            return region_of(c, regions)[0]
    return ""


# --- the pieces of the landing page -----------------------------------------


def block_tracks():
    """Money, papers, calendar.

    Three columns of running text rather than three cards. Cards would say
    these are three things you do; they are three things that are true at once,
    and the middle one is the reason this product is worth building before any
    money moves — a passport that runs out four months before departure stops a
    journey more completely than being four hundred dollars short, and it is
    discoverable a year and a half in advance.
    """
    tracks = (
        ("The money", "What the journey costs",
         "Priced from the same rate card as everything else on this site: per "
         "vehicle, per day, with the arrival coordination named separately. "
         "Divide it by the months between now and then and you have the "
         "figure this page exists to give you."),
        ("The papers", "What you need to have done",
         "A passport with six months left on it at the border, the entry "
         "authorisation for where you are going, insurance, a flight, one "
         "emergency contact. They come due in that order, and the first one "
         "is a today problem rather than a next-year one."),
        ("The calendar", "Whether the two agree",
         "A month, and a rhythm that reaches it. If they do not agree, the "
         "answer is not to try harder — it is a later month, a shorter "
         "journey, or a different tier, and this page will tell you which."),
    )
    return "".join(
        '<div class="jf-track"><b>%s</b><h3>%s</h3><p>%s</p></div>'
        % (esc(a), esc(b), esc(c)) for a, b, c in tracks)


def block_tiers(money):
    """The three tiers, in the rate card's own words.

    Names and lines are quoted from tourism/rates.json rather than rewritten,
    so a traveller comparing this page with /pricing and /journey reads the
    same sentence three times instead of three sentences that nearly agree.
    """
    out = []
    for t in money["tiers"]:
        checked = ' checked' if t["id"] == money["default_tier"] else ""
        out.append(
            '<label class="jf-tier"><input type="radio" name="jf-tier" '
            'value="%s" data-rate="%d"%s><span><b>%s</b><em>%s a day</em>'
            '<i>%s</i></span></label>'
            % (esc(t["id"]), t["rate"], checked, esc(t["name"]),
               rates.money(t["rate"]), esc(t["line"])))
    return "".join(out)


def block_days(money):
    out = []
    for n in money["durations"]:
        checked = ' checked' if n == money["default_days"] else ""
        out.append(
            '<label class="jf-chip"><input type="radio" name="jf-days" '
            'value="%d"%s><span>%d days</span></label>' % (n, checked, n))
    return "".join(out)


def block_sum(money):
    """The default journey's arithmetic, rendered here so the page is complete
    with scripting off.

    The script replaces this the moment it runs. Until then it is not a
    placeholder — it is a correct answer to the most common question, which is
    what a week in one country with a driver actually costs.
    """
    tier = next(t for t in money["tiers"] if t["id"] == money["default_tier"])
    days = money["default_days"]
    ground = tier["rate"] * days
    arrival = money["arrival"]["rate"]
    return (
        '<div><span>%s, %d days</span><span>%s</span></div>'
        '<div><span>%s</span><span>%s</span></div>'
        '<div class="jf-rule"><span>Journey target</span><b>%s</b></div>'
        % (esc(tier["name"]), days, rates.money(ground),
           esc(money["arrival"]["name"]), rates.money(arrival),
           rates.money(ground + arrival)))


def block_places(countries, regions, first=None):
    """The fifty-four, as real options in the HTML.

    The first version left this select empty and let the script fill it, which
    made the one control the page is built around useless with scripting off —
    on a page whose own copy claims to be complete without it. Fifty-four
    options is about two kilobytes, and unlike the month strip they never go
    stale, so there is no reason for them to arrive late.

    The script replaces this list when the reader switches to crossings, and
    otherwise leaves it exactly as it found it.
    """
    out = []
    for c in sorted([c for c in countries if c.published and c.slug],
                    key=lambda c: c.name):
        sel = ' selected' if c.slug == first else ''
        out.append('<option value="%s"%s>%s</option>'
                   % (esc(c.slug), sel, esc(c.name)))
    return "".join(out)


# --- the three pages ---------------------------------------------------------


def render_landing(countries, regions, crossings, money, co):
    data = payload(countries, regions, crossings, money)
    return LANDING_TEMPLATE % {
        "og": plate.open_graph(
            "The Journey Fund — Afrinkong",
            "Work out what an Afrinkong journey costs, and what putting "
            "something aside each month would have to look like to reach it. "
            "We hold no money and charge nothing.",
            "/journey-fund"),
        "preload": plate.PRELOAD,
        "mast": mast("/journey-fund"),
        "foot": plate.colophon_foot("/journey-fund"),
        "events": plate.events_block(),
        "data": json.dumps(data, separators=(",", ":"), sort_keys=True),
        "shot": SHOT,
        "shot_alt": esc(SHOT_ALT),
        "shot_w": SHOT_W,
        "shot_h": SHOT_H,
        "places": block_places(countries, regions, data["first"]),
        "tracks": block_tracks(),
        "tiers": block_tiers(money),
        "days": block_days(money),
        "sum": block_sum(money),
        "n": len(data["countries"]),
        "crossings": len(data["routes"]),
    }


def render_how(money, co):
    return HOW_TEMPLATE % {
        "og": plate.open_graph(
            "How the Journey Fund works — Afrinkong",
            "Where the money sits, what happens if you stop, what happens if "
            "you change your mind, and what happens if the price moves.",
            "/journey-fund/how-it-works"),
        "preload": plate.PRELOAD,
        "mast": mast("/journey-fund/how-it-works"),
        "foot": plate.colophon_foot("/journey-fund/how-it-works"),
        "events": plate.events_block(),
    }


def render_questions(money, co):
    return ASKED_TEMPLATE % {
        "og": plate.open_graph(
            "Journey Fund questions — Afrinkong",
            "The questions people actually ask about planning an Afrinkong "
            "journey a year or two ahead, answered plainly.",
            "/journey-fund/questions"),
        "preload": plate.PRELOAD,
        "mast": mast("/journey-fund/questions"),
        "foot": plate.colophon_foot("/journey-fund/questions"),
        "events": plate.events_block(),
    }


def run(countries=None, log=print):
    if countries is None:
        countries = load_countries()
    regions = load_regions()
    money = rates.load()
    co = company.load()
    with open(CROSSINGS, encoding="utf-8") as fh:
        crossings = json.load(fh)

    if not [c for c in countries if c.published]:
        raise IOError("no published countries — nothing to build toward")

    pages = [
        (LANDING, render_landing(countries, regions, crossings, money, co)),
        (HOW, render_how(money, co)),
        (ASKED, render_questions(money, co)),
    ]

    # The guard the journey builder already runs. Every dollar figure on these
    # pages has to be one tourism/rates.json can account for; the crossing
    # bands never appear as text, only as integers inside the JSON the
    # estimator reads, so they are correctly invisible to it.
    for path, html in pages:
        stray = rates.drift(html, money)
        if stray:
            raise ValueError(
                "%s prints %s, which tourism/rates.json does not price — a "
                "figure in the copy has drifted from the rate card."
                % (os.path.relpath(path, ROOT),
                   ", ".join(rates.money(v) for v in stray)))

    if not os.path.isdir(DIR):
        os.makedirs(DIR)
    for path, html in pages:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        log("fund: %s (%.1f KB)" % (os.path.relpath(path, ROOT), len(html) / 1024.0))

    log("fund: rate card %s, %d countries, %d crossings"
        % (rates.version(money),
           len([c for c in countries if c.published]),
           len(crossings.get("routes", []))))
    return [p for p, _ in pages]


# --- the templates -----------------------------------------------------------

# THE SHELL, NOT A MASTHEAD OF ITS OWN. Phase 5 + 6.
#
# This used to be one of ten mastheads. The Journey Fund keeps its identity —
# it gets a product band with its own name and its own three links — but it
# stops having its own idea of what a masthead IS. plate.shell() owns that now,
# and these three pages are the first family to adopt it because they are the
# smallest and because this is the family the state language already proved
# things on.
# The fourth entry is the explanatory page for the unit this family already
# quotes. The label is a sentence, not a noun: "Travel Points" in a navigation
# bar reads as a shelf you can buy from, and "What a Travel Point is" cannot be
# misread as an offer while the programme is still in compliance review.
#
# This tuple is the ONE definition of the band. tools/tourism/points_page.py
# imports it rather than restating it — a near-copy of a navigation list is how
# two pages in the same family end up disagreeing about what family they are in.
FUND_NAV = (
    ("/journey-fund", "Plan a journey"),
    ("/journey-fund/how-it-works", "How it works"),
    ("/journey-fund/questions", "Questions"),
    ("/travel-points", "What a Travel Point is"),
)


def mast(here):
    from . import plate
    return plate.shell(here=here, area="plan", product="The Journey Fund",
                       product_href="/journey-fund", product_nav=FUND_NAV)

LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Journey Fund &mdash; Afrinkong</title>
<meta name="description" content="Work out what an Afrinkong journey costs, and what putting something aside each month would have to look like to reach it. We hold no money and charge nothing.">
%(og)s
<meta name="theme-color" content="#10251F">
%(preload)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/fund.css">
<!-- The state language. Item 4. Only the landing links it, because the Travel
     Goal is the only surface on this site with a live state today. -->
<link rel="stylesheet" href="/styles/states.css">
</head>
<body class="af af--fund jf-page" data-area="plan">
<a class="af-skip" href="#plan">Skip to the planner</a>
%(mast)s
<main>
  <section class="jf-frame jf-open jf-move" id="dream" aria-labelledby="m1">
    <p class="af-stamp jf-move-n"><b>01</b> Dream</p>
    <h1 id="m1">Your journey can start long before you leave.</h1>
    <p class="jf-sub">Choose where, and choose when. This page works out what
      the journey costs, and what the months between now and then would have to
      look like to reach it.</p>
    <figure class="jf-shot">
      <img src="%(shot)s-1600w.jpg" width="%(shot_w)d" height="%(shot_h)d"
        alt="%(shot_alt)s" decoding="async" fetchpriority="high"
        data-provider="upload"
        srcset="%(shot)s-800w.jpg 800w, %(shot)s-1600w.jpg 1600w">
      <figcaption>On the road, somewhere between the two countries</figcaption>
    </figure>
  </section>

  <form class="jf-form" id="jf-form" novalidate>
    <section class="jf-frame jf-move" id="choose" aria-labelledby="m2">
      <p class="af-stamp jf-move-n"><b>02</b> Choose</p>
      <h2 class="af-stamp" id="m2">Where, and when</h2>
      <div class="jf-two">
        <fieldset class="jf-ask">
          <legend>Where</legend>
          <div class="jf-chips" id="jf-kind" role="group" aria-label="A country or a crossing">
            <label class="jf-chip"><input type="radio" name="jf-kind" value="country" checked><span>One country</span></label>
            <label class="jf-chip"><input type="radio" name="jf-kind" value="crossing"><span>A crossing</span></label>
          </div>
          <p class="jf-fine" id="jf-where-fine">%(n)d countries written up, %(crossings)d crossings.</p>
          <label class="af-stamp jf-lab" for="jf-place">The destination</label>
          <select id="jf-place" name="place" class="jf-select">%(places)s</select>
          <!-- THE WAY BACK TO THE BUILDER.
               This page could already RECEIVE a journey - fund.js has read
               place, tier and days off the query string since the builder
               grew a door to here - but it could not SEND anybody to compose
               one. A reader who does not yet know where they want to go was
               handed a dropdown of fifty-four countries and left to it.
               One direction of an edge is not an edge. -->
          <p class="jf-fine jf-where-back">Not sure yet?
            <a href="/journey">Compose a journey</a> in four questions and
            bring it back here to price.</p>
        </fieldset>

        <fieldset class="jf-ask">
          <legend>When</legend>
          <label class="af-stamp jf-lab" for="jf-month">The month you would go</label>
          <select id="jf-month" name="month" class="jf-select">
            <option value="">Any month from three months out</option>
          </select>
        </fieldset>
      </div>
    </section>

    <section class="jf-frame jf-planner jf-move" id="plan" aria-labelledby="plan-h">
      <p class="af-stamp jf-move-n"><b>03</b> Build</p>
      <h2 class="af-stamp" id="plan-h">Your journey plan</h2>
      <div class="jf-est">
        <div class="jf-asks">
          <fieldset class="jf-ask" id="jf-days-ask">
            <legend>How long</legend>
            <div class="jf-chips" role="group" aria-label="How many days">%(days)s</div>
          </fieldset>

          <fieldset class="jf-ask" id="jf-tier-ask">
            <legend>Which journey</legend>
            <div class="jf-tiers" role="group" aria-label="Which journey">%(tiers)s</div>
          </fieldset>

          <fieldset class="jf-ask">
            <legend>How often</legend>
            <div class="jf-chips" role="group" aria-label="How often">
              <label class="jf-chip"><input type="radio" name="jf-rhythm" value="monthly" checked><span>Every month</span></label>
              <label class="jf-chip"><input type="radio" name="jf-rhythm" value="quarterly"><span>Every three months</span></label>
            </div>
          </fieldset>
        </div>

        <div class="jf-work">
          <p class="af-stamp jf-plan-eye">The plan</p>
          <p class="jf-where" id="jf-where">Uganda</p>
          <p class="jf-when" id="jf-when">Choose a month</p>
          <div class="jf-sum" id="jf-sum" aria-live="polite">%(sum)s</div>
          <p class="jf-said" id="jf-said" aria-live="polite">With scripting on,
            this shows what reaching it would look like &mdash; <b>a pace you choose</b>, not a payment you owe.</p>
          <div class="jf-reach" id="jf-reach" hidden></div>

          <!-- THE TRAVEL GOAL. A PLANNING FIGURE, AND LABELLED AS ONE.
               The same journey estimate above, restated in the units of a
               draft Travel Point programme, so a reader can see the shape of
               the commitment. Nothing is on sale, nothing is owned and no
               account exists; the panel says so in its own heading rather
               than in fine print underneath, because a number with a caveat
               below it is a number people read without the caveat. -->
          <section class="jf-goal" id="jf-goal" hidden aria-labelledby="jf-goal-h">
            <h3 class="jf-goal-h" id="jf-goal-h">Estimated Travel Goal
              <span class="jf-goal-tag">planning only &mdash; not for sale</span></h3>
            <!-- THE STATE CHIP. Item 4's one adoption.
                 The stage comes from travel-goal.js, which has published
                 `journeyState` all along, and the sentence and the tone come
                 from state-language.js. Nothing here decides either: fund.js
                 asks the language and writes what it is told, and
                 state-checks reads this attribute back off the built page and
                 fails if the tone beside it is not the one the language chose.
                 RENDERED WITH ITS OPENING STAGE RATHER THAN EMPTY. Every
                 reader starts in PLANNING — that is what the Travel Goal is —
                 so the chip is correct before any script runs, and fund.js
                 only ever moves it on. An empty chip filled in by JavaScript
                 would also have made the checks vacuous: state-checks reads
                 the BUILT page, and a state that only exists at runtime is a
                 state nothing static can verify.

                 The tone is written here and is NOT this file's decision.
                 state-language.js chose `neutral` for journey:PLANNING, and
                 state-checks reads this attribute back off the built HTML and
                 fails if the class beside it is not the tone the language
                 picked. Copying it is safe precisely because copying it is
                 checked. -->
            <p class="af-state af-state--neutral jf-goal-state" id="jf-goal-state"
               data-state="journey:PLANNING" data-domain="travel">Planning this journey</p>
            <div class="jf-goal-grid" id="jf-goal-grid"></div>
            <!-- D-goalinput. The panel showed zero progress forever because
                 fund.js passed a hard-coded 0 and nothing let a reader say
                 otherwise. (No per-cent sign in this comment on purpose:
                 LANDING_TEMPLATE is printf-style, so a bare one breaks
                 it -- including, on the first attempt, inside this very
                 warning.) This is a NOTE ON THEIR OWN DEVICE: Afrinkong is
                 told nothing, holds nothing, and no account exists. That is
                 why it says "set aside" rather than "your Travel Points" —
                 planning is not ownership, and the wording must not imply a
                 holding the reader does not have. -->
            <div class="jf-goal-set">
              <label class="jf-goal-set-l" for="jf-goal-have">If you have
                started setting money aside, record it here to see where you
                are</label>
              <span class="jf-goal-set-row">
                <input class="jf-goal-set-i" id="jf-goal-have" type="number"
                       min="0" step="1" inputmode="numeric"
                       placeholder="0" aria-describedby="jf-goal-set-f">
                <span class="jf-goal-set-u">TP</span>
                <button class="jf-goal-set-c" id="jf-goal-clear"
                        type="button">Clear</button>
              </span>
              <span class="jf-fine" id="jf-goal-set-f">Kept in this browser
                only. Nothing is sent to Afrinkong, and nothing is
                purchased.</span>
            </div>
            <p class="jf-goal-note" id="jf-goal-note"></p>
            <p class="jf-fine" id="jf-goal-prov"></p>
          </section>
          <p class="jf-fine">Park and conservation fees, permits and entrance
            charges are settled by us at cost and are <b>not</b> in this figure.
            They depend on the itinerary, and a gorilla permit alone can be more
            than a day of the journey.</p>
          <p class="jf-fine">An estimate against today&rsquo;s rate card, not a
            quotation.</p>
        </div>
      </div>

      <div class="jf-keep">
        <p>Come back to this plan whenever you like: it can be kept in this
          browser and nowhere else &mdash; no account, no email, nothing sent
          anywhere, and no money held by us.</p>
        <div class="jf-acts">
          <button class="af-btn" type="button" id="jf-keep">Keep this plan</button>
          <a class="af-btn af-btn--solid" href="/enquire" id="jf-send">Talk to us about it<i>&rarr;</i></a>
        </div>
        <p class="jf-kept-note" id="jf-kept" hidden></p>
      </div>
    </section>
  </form>

  <section class="jf-frame jf-move" id="ready" aria-labelledby="m4">
    <p class="af-stamp jf-move-n"><b>04</b> Journey</p>
    <h2 class="af-stamp" id="m4">What a journey is ready on</h2>
    <div class="jf-tracks">%(tracks)s</div>
  </section>

  <section class="jf-frame jf-close">
    <p class="jf-note">Afrinkong holds none of this money &mdash; it stays in
      your own account and nothing is charged, now or later, until you decide
      to travel. <a href="/journey-fund/how-it-works">How it works</a> says
      where it sits and what happens if you stop, and the
      <a href="/journey-fund/questions">questions people ask</a> covers the
      rest.</p>
  </section>
</main>
%(foot)s
%(events)s
<script type="application/json" id="jf-data">%(data)s</script>
<script src="/scripts/fund-math.js" defer></script>
<!-- Read-only arithmetic. Neither of these can issue, sell or hold anything:
     the point program is a draft and points-ledger.js refuses to create a
     point under a draft program. -->
<script src="/scripts/points-ledger.js" defer></script>
<script src="/scripts/travel-goal.js" defer></script>
<script src="/scripts/state-language.js" defer></script>
<script src="/scripts/fund.js" defer></script>
</body>
</html>
"""

HOW_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How the Journey Fund works &mdash; Afrinkong</title>
<meta name="description" content="Where the money sits, what happens if you stop, what happens if you change your mind, and what happens if the price moves.">
%(og)s
<meta name="theme-color" content="#10251F">
%(preload)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/fund.css">
</head>
<body class="af af--fund jf-page" data-area="plan">
<a class="af-skip" href="#qs">Skip to the answers</a>
%(mast)s
<main>
  <section class="jf-frame jf-open jf-open--short">
    <h1>How it works</h1>
    <p class="jf-sub">Four questions, in the order people actually ask them
      rather than the order we would prefer. The first one is the one everybody
      wants answered first, so it is first.</p>
  </section>

  <div class="jf-frame jf-qs" id="qs">
    <article class="jf-q">
      <h2>Where does my money sit?</h2>
      <p><b>In your own bank account.</b> Nothing on this page moves
        money. The planner does arithmetic; it takes no payment, opens no
        account and has no way of knowing whether you have put anything aside
        at all.</p>
      <p>Afrinkong does not operate a customer bank account or a deposit
        account, and it will not. If Travel Points are ever offered, buying one
        would be a <b>purchase of travel entitlement</b> under the terms of the
        programme that issued it &mdash; a payment for something, the way any
        purchase is, rather than money placed with us for safekeeping. The
        difference matters and we would rather state it now than discover later
        that a sentence written today had quietly stopped being true. What we give you is the arithmetic &mdash; what the
        journey costs, how many months there are, and therefore what each month
        would have to look like &mdash; and a calendar that tells you when your
        passport needs attention. The money is yours and stays yours until the
        day you decide to travel and we send you an invoice like any other
        company.</p>
      <p>If that ever changes, it will not change quietly. Holding a
        customer&rsquo;s money is a different undertaking with different
        obligations, and it would arrive as a different agreement that you
        would have to read and accept. Not as an update to this page.</p>
    </article>

    <article class="jf-q">
      <h2>What if I stop?</h2>
      <p>Nothing happens, because nothing was started. There is no schedule to
        break, no charge to miss, no fee, no record anywhere of you having
        stopped. You made a plan and you are no longer keeping it, which is
        your business and not ours.</p>
      <p>The plan you kept in your browser stays there until you clear it.
        Nobody is emailed about it and nobody follows up.</p>
    </article>

    <article class="jf-q">
      <h2>What if I change my mind about where?</h2>
      <p>Change it. Put Namibia where Kenya was and the page recalculates: the
        journey is a different length, the figure is different, the month may
        move, and the colour of the page changes because the page is about the
        destination rather than about the money.</p>
      <p>Nothing is lost by changing, because nothing was committed. This is
        the part most worth saying plainly: two years is a long time to be
        certain about a continent you have not visited yet, and a plan you
        cannot change is a plan you abandon instead.</p>
    </article>

    <article class="jf-q">
      <h2>What if the price changes before I go?</h2>
      <p>It might. The figure this page gives you is an estimate against
        today&rsquo;s rate card, and the rate card is a published document that
        can be revised. A plan you keep records which version of it priced
        your journey, so when you come back the page can tell you whether the
        number moved because you changed something or because we did.</p>
      <p>Two things are outside the estimate in either direction. Park and
        conservation fees, permits, entrance and government charges are settled
        by us <b>at cost</b> and depend on the itinerary &mdash; a gorilla
        permit alone can exceed a day of the journey. And international
        flights, visas, insurance, your own meals and your personal spending
        are yours, as they are on every Afrinkong journey.</p>
    </article>

    <article class="jf-q">
      <h2 class="jf-q-small"><span class="jf-hold">Not built yet</span>What this page cannot do</h2>
      <p>It cannot take a payment, keep a plan across two devices, remind you
        by email, or tell you how far along you are, because all of those need
        an account and this version has none. What you keep is kept in this
        browser.</p>
      <p>That is a deliberate order of work rather than an unfinished feature.
        The planning is useful on its own, it can be built and checked without
        anybody&rsquo;s money being involved, and it means the questions that
        do involve money can be answered properly by people qualified to answer
        them rather than quickly by us.</p>
    </article>
  </div>
</main>
%(foot)s
%(events)s
</body>
</html>
"""

ASKED_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Journey Fund questions &mdash; Afrinkong</title>
<meta name="description" content="The questions people actually ask about planning an Afrinkong journey a year or two ahead, answered plainly.">
%(og)s
<meta name="theme-color" content="#10251F">
%(preload)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/fund.css">
</head>
<body class="af af--fund jf-page" data-area="plan">
<a class="af-skip" href="#qs">Skip to the questions</a>
%(mast)s
<main>
  <section class="jf-frame jf-open jf-open--short">
    <h1>Questions</h1>
    <p class="jf-sub">The ones that actually get asked. If yours is not here,
      <a href="/enquire">write to us</a> &mdash; a person answers.</p>
  </section>

  <div class="jf-frame jf-qs" id="qs">
    <article class="jf-q">
      <h2>Who can use this?</h2>
      <p>Anyone aged eighteen or over. There is nothing to sign up for, so
        there is nothing to be eligible for &mdash; but the journeys themselves
        are arranged for adults, and a traveller under eighteen travels with
        one.</p>
    </article>

    <article class="jf-q">
      <h2>Why does the passport come first?</h2>
      <p>Because most African countries want six months&rsquo; validity beyond
        your date of entry, which means a passport expiring the spring after
        your journey is already a problem today. It is the single item on the
        list that is worth knowing about eighteen months early, and it is the
        main reason this page exists at all.</p>
      <p>The rest come due in the order they actually matter: insurance before
        the month you are going, the flight once the journey is close enough to
        be real, the entry authorisation after the flight because several are
        dated from the day they are issued, and the emergency contact last
        because it takes a minute.</p>
    </article>

    <article class="jf-q">
      <h2>What currency is this in?</h2>
      <p>United States dollars, which is what the rate card is in. If you bank
        in something else, your own bank decides the rate on the day you
        eventually pay &mdash; we do not quote a fixed figure in another
        currency two years ahead, because holding that promise would mean
        taking a position on exchange rates, and Afrinkong is not in that
        business.</p>
    </article>

    <article class="jf-q">
      <h2>How is the monthly figure worked out?</h2>
      <p>The journey&rsquo;s cost divided by the number of whole months between
        now and the month you chose. No interest, no growth, no assumptions
        about anything &mdash; division, and nothing else. If you choose to put
        something aside every three months instead, it is the same total in
        fewer, larger amounts.</p>
      <p>If the arithmetic cannot reach the month you picked, the page says so
        and offers the three or four things that would: a later month, fewer
        days, a different tier, or a larger amount. It does not tell you to try
        harder.</p>
    </article>

    <article class="jf-q">
      <h2>Is this a savings account?</h2>
      <p>No. Afrinkong is a travel company. Nothing here is an account,
        a deposit, a balance or an investment, no interest or return is paid or
        offered, and there is nothing to withdraw because there is nothing
        held. If you put money aside, you put it aside somewhere of your own
        choosing and it earns whatever that place pays.</p>
    </article>

    <article class="jf-q">
      <h2>Will Afrinkong ever hold the money?</h2>
      <p>Possibly, and not yet. Taking a customer&rsquo;s money a year or two
        before delivering anything raises real questions about who holds it,
        what it legally is and what protects it, and those are questions for
        qualified advisers rather than for a web page. Until they are answered
        properly, we would rather do the part that helps and none of the part
        that does not.</p>
      <p>If it ever happens, it will be a separate agreement you read and
        accept, not a change to how this page behaves.</p>
    </article>

    <article class="jf-q">
      <h2>What happens to the plan I keep?</h2>
      <p>It is stored by your own browser on your own device. It is not sent to
        us, not attached to your name, and not readable by anybody but you.
        Clearing your browser&rsquo;s data clears it, and using a different
        device means it is not there. There is no copy anywhere else.</p>
    </article>

    <article class="jf-q">
      <h2>What if I just want to book?</h2>
      <p>Then book. <a href="/journey">Build the journey</a>, send it to us and
        we will come back with what can be arranged on your dates and the
        figure in writing. This page is for the case where the journey is
        further away than the money is, which is most people most of the
        time.</p>
    </article>
  </div>
</main>
%(foot)s
%(events)s
</body>
</html>
"""
