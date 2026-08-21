"""Two ways to travel, and why they are priced differently.

    python3 tools/tourism/build.py twoways      ->  /how-it-works

THE PROBLEM THIS PAGE EXISTS TO FIX

Afrinkong sells two things and the site never says so in one place.

    a country     /atlas -> a country -> /journey -> /enquire
                  priced PER VEHICLE PER DAY, plus park and permit charges
                  passed through at cost

    a crossing    /trans-afrique -> the crossings -> a journey
                  priced as a BAND FOR THE WHOLE JOURNEY, because a month of
                  one vehicle does not cost thirty times a day of it

Before this page the two never met. /journey never mentioned a crossing even
for somebody asking for thirty days; /trans-afrique never mentioned the daily
rate; and nothing anywhere explained why one is a rate and the other is a
band. A reader who had seen "$450 a day" and then "$15,000 to $30,000" had no
way to tell whether those were the same product quoted twice.

THE NAME COLLISION IS REAL AND IS NOT FIXED HERE

Both systems have a tier called Private and one called Signature, and they do
not mean the same thing:

    Afrinkong Private        the ENTRY tier for a country
    Trans Afrique Private    the TOP tier for a crossing

Same word, opposite ends of the range. This page sets the two ladders side by
side so the difference is at least visible, and says out loud that the names
repeat. Renaming a tier is a brand decision with a price list attached to it,
so it is flagged rather than quietly done — see the note under `$naming` in
tourism/rates.json.

EVERY FIGURE IS READ FROM THE FILE THAT OWNS IT

Nothing here is typed. The day rates come from rates.json, the journey bands
from transafrique.json, and the two lists of what is and is not included come
from the same arrays their own pages print. A third copy of a price is a third
thing to forget to update, and this repository has already been caught once by
a hero plate saying $350 beside a tier saying $650.
"""

import html as html_mod
import json
import os

from . import plate
from .model import ROOT

PAGE = os.path.join(ROOT, "how-it-works.html")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def money(n):
    return "${:,}".format(int(n))


def load(name):
    with open(os.path.join(ROOT, "tourism", name), encoding="utf-8") as fh:
        return json.load(fh)


def ladder(title, unit, rows, note):
    """One of the two price ladders, set the same way as the other so the shapes
    can actually be compared. The unit is printed at the head of each because
    the unit IS the difference — everything else is just numbers."""
    body = "".join(
        '<div class="hw-step"><dt>%s</dt><dd>%s<span>%s</span></dd></div>'
        % (esc(n), esc(v), esc(w)) for n, v, w in rows)
    return ('<div class="hw-ladder"><h3 class="hw-ladder-h">%s</h3>'
            '<p class="hw-unit">%s</p><dl class="hw-steps">%s</dl>'
            '<p class="hw-note">%s</p></div>'
            % (esc(title), esc(unit), body, esc(note)))


def build():
    rates = load("rates.json")
    tf = load("transafrique.json")

    country_rows = [(t["name"],
                     "%s%s" % ("from " if t.get("from") else "", money(t["rate"])),
                     t["line"]) for t in rates["tiers"]]
    # A literal en dash, not the entity: ladder() escapes what it is handed —
    # as it must, these strings come from data — so "&ndash;" arrived on the
    # page spelled out.
    crossing_rows = [(v["name"],
                      "%s\u2013%s" % (money(v["low"]), money(v["high"])),
                      v["line"]) for v in tf["levels"]]

    # The two "what it covers" lists, each from the file that owns it.
    def ul(items, cls=""):
        return ('<ul class="hw-list%s">%s</ul>'
                % (cls, "".join("<li>%s</li>" % esc(x) for x in items)))

    lowest_day = min(t["rate"] for t in rates["tiers"])
    lowest_band = min(r["low"] for r in tf["routes"])

    return TEMPLATE % {
        "mast": plate.shell(here="/how-it-works"),
        "country_ladder": ladder(
            "Travelling in one country", rates["unit"], country_rows,
            "Park entrance, conservation and permit charges are arranged by "
            "Afrinkong and passed through at cost, itemised, on top of the "
            "rate. They are not inside it."),
        "crossing_ladder": ladder(
            "Crossing several", "per journey, quoted whole", crossing_rows,
            "One figure for the crossing. It is lower per day than the daily "
            "rate above and that is the shape of the thing, not a discount: "
            "a vehicle and a driver committed for a month cost less per day "
            "than the same pair for four days, and a road that repeats across "
            "departures is a road already solved."),
        "in_country": ul(rates["tiers"][0]["includes"]),
        "at_cost": ul(rates["destination_charges"]),
        "yours": ul(rates["excluded"], " is-not"),
        "tf_in": ul(tf["included"]),
        "tf_arranged": ul(tf["arranged"]),
        "tf_yours": ul(tf["excluded"], " is-not"),
        "from_day": money(lowest_day),
        "from_band": money(lowest_band),
        "n_routes": len(tf["routes"]),
        "fine": esc(rates.get("$model", "")),
    }


def run(countries=(), log=print):
    from . import plate
    html = build() % {
        "og": plate.open_graph(
            "How it works — Afrinkong",
            "Afrinkong arranges two kinds of journey: time in one country, "
            "priced per day, and a crossing of several, priced whole. "
            "What each covers, and why the shapes differ.",
            "/how-it-works"),
        "events": plate.events_block(),
    }
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("how-it-works: %s (%.1f KB)"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How it works &mdash; Afrinkong</title>
<meta name="description" content="Afrinkong arranges two kinds of journey: time in one country, priced per day, and a crossing of several, priced whole. What each covers, and why the two shapes differ.">
%%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<link rel="stylesheet" href="/styles/howitworks.css">
</head>
<body class="af af--trust hw-body">
<a class="af-skip" href="#main">Skip to how it works</a>
%(mast)s

<main id="main" class="hw-page">
  <div class="hw-open">
    <p class="hw-eyebrow">How it works</p>
    <h1 class="hw-h1">Two kinds of journey, priced two different ways.</h1>
    <p class="hw-lede">Afrinkong arranges time in one country and journeys
      that cross several. They are not the same product and they are not
      quoted the same way, which is worth knowing before you see a figure.</p>
  </div>

  <!-- THE FORK, AND IT IS THE POINT OF THE PAGE. Two doors, named, with the
       shape of each one's price under it. A reader who knows which of these
       they are in can read every other number on the site correctly. -->
  <section class="hw-fork">
    <article class="hw-door">
      <p class="hw-door-no">01</p>
      <h2 class="hw-door-h">A country, in depth</h2>
      <p class="hw-door-say">One country, a vehicle and a driver of your own,
        and days built around what you came for. Most journeys are this.</p>
      <p class="hw-door-price">From %(from_day)s <span>per vehicle, per day</span></p>
      <a class="hw-door-go" href="/journey">Build a journey<i>&rarr;</i></a>
    </article>
    <article class="hw-door">
      <p class="hw-door-no">02</p>
      <h2 class="hw-door-h">A crossing, by road</h2>
      <p class="hw-door-say">Several countries in one continuous journey, with
        a team that travels with you. %(n_routes)d crossings, from a fortnight
        to two months.</p>
      <p class="hw-door-price">From %(from_band)s <span>for the whole crossing</span></p>
      <a class="hw-door-go" href="/trans-afrique">See Trans Afrique<i>&rarr;</i></a>
    </article>
  </section>

  <section class="hw-block">
    <h2 class="hw-h2">Why one is a rate and the other is a band</h2>
    <div class="hw-ladders">
%(country_ladder)s
%(crossing_ladder)s
    </div>
    <!-- SAID OUT LOUD BECAUSE IT IS A REAL TRAP. Both ladders have a Private
         and a Signature and they sit at opposite ends of their own ranges. -->
    <p class="hw-warn">Both ladders have a tier called Private and one called
      Signature, and they do not line up: Afrinkong Private is where a country
      journey starts, while Trans Afrique Private is where a crossing tops out.
      Read the tier against its own ladder, never across the two.</p>
  </section>

  <!-- THE ONLY PHOTOGRAPH ON THIS PAGE, AND WHY IT IS THIS ONE.
       Everything above is a price and a distinction between two ladders. What
       neither of them shows is the thing being bought, which is not a vehicle
       and not an animal: it is the man in the white shirt on the wing seat,
       who is looking at the elephant so that the people behind him do not have
       to work out whether they should be worried.

       One vehicle, not a line of them. Nobody looking at the camera. No
       country named, because this frame does not tell us which one it is and
       the site does not claim what a photograph cannot support.

       It lives here rather than in the built page. It was added to
       how-it-works.html by hand, which meant every `build.py all` deleted it
       and nobody would have noticed until somebody looked at the page after a
       rebuild. Anything a generator writes has to be written in the
       generator. -->
  <figure class="hw-plate">
    <img src="/images/uploads/guide-elephant-on-the-track-1600w.jpg"
      width="1600" height="1066" loading="lazy" decoding="async"
      data-provider="upload"
      srcset="/images/uploads/guide-elephant-on-the-track-800w.jpg 800w,
              /images/uploads/guide-elephant-on-the-track-1600w.jpg 1600w"
      alt="A tracker in a white shirt and cap sits on the wing seat of an open Land Rover, watching an elephant walk along the sand track beside them while three passengers look on from the tiered seats behind">
    <figcaption>What the day rate is actually for: one vehicle, and somebody
      whose job is to have seen this before.</figcaption>
  </figure>

  <section class="hw-block">
    <h2 class="hw-h2">What each one covers</h2>
    <div class="hw-cols">
      <div class="hw-col">
        <h3 class="hw-col-h">In a country journey</h3>
        <p class="hw-col-say">In the day rate</p>
%(in_country)s
        <p class="hw-col-say">Arranged by Afrinkong, at cost</p>
%(at_cost)s
        <p class="hw-col-say">Yours</p>
%(yours)s
      </div>
      <div class="hw-col">
        <h3 class="hw-col-h">In a crossing</h3>
        <p class="hw-col-say">In the journey fee</p>
%(tf_in)s
        <p class="hw-col-say">Arranged by Afrinkong, at cost</p>
%(tf_arranged)s
        <p class="hw-col-say">Yours</p>
%(tf_yours)s
      </div>
    </div>
  </section>

  <section class="hw-end">
    <h2 class="hw-end-h">Not sure which one you want?</h2>
    <p class="hw-end-say">Say how long you have and what you want to see. We
      will tell you which of the two fits, and what it costs, in writing before
      anything is held.</p>
    <div class="hw-end-acts">
      <a class="af-btn hw-end-go" href="/journey">Build a journey<i>&rarr;</i></a>
      <a class="af-btn af-btn--quiet" href="/enquire">Ask us<i>&rarr;</i></a>
    </div>
  </section>

  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</main>
%%(events)s
</body>
</html>
"""
