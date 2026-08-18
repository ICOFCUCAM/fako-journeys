"""The Afrinkong ground journey: what it is, what it costs, what it is not.

Built into /journey by build.py journey — it is a stage of the tunnel, not a
page of its own.

WHERE THIS BELONGS, AND WHERE IT DOES NOT

The first draft of this put the ground journey on /pricing. That page is
Kamerun's: Kamerun masthead, Douala telephone, bonjour@kamerun.cm, a form
asking which Cameroon circuit you want priced. Afrinkong's flagship product
ended up under a local operator's letterhead, quoted in dollars on a page that
quotes CFA francs, and a traveller heading for Namibia was invited to pick
between CIR-01 Fako Ascent and CIR-06 Ring Road.

So it lives in the tunnel instead. /journey already asks what kind of Africa
you want, when, how long you have, and who is coming; it names a country and
composes a journey inside it. What it never did was say what the ground costs
— it shaped a journey and dropped the traveller at /contact with no figure.
This is that missing last step, and it is the same four answers carried
forward rather than four questions asked twice.

Kamerun keeps its own rates page. A local operator pricing its own circuits
per person in the local currency is correct; it is only wrong as the place the
continent-wide product lives.

THE PRODUCT

Not a tour. The part of the trip that begins when the plane lands: a vehicle,
a driver who stays with the journey, movement between destinations, and
somebody coordinating it. The traveller brings the passport, the visa, the
flight and the insurance. Afrinkong takes it from the airport.

Three consequences the markup has to carry:

  Priced per vehicle, not per head. Four people in one vehicle pay what two
  pay. A per-person price would be the safari-package model this is explicitly
  not, and it would punish exactly the parties most worth having.

  The exclusions are as prominent as the inclusions. A ground operator that
  lets a traveller believe lodges and permits are covered has not made a sale,
  it has made a complaint.

  Nothing here takes money. The stage produces a journey and hands it to the
  enquiry page as a sentence a person can read and edit. Afrinkong confirms the
  requirements before it confirms the journey, and no card is asked for until
  somebody has checked that the traveller can actually travel.

EVERY FIGURE COMES FROM tourism/rates.json
Nothing in this file knows what a day costs. Changing a rate is one edit in
one place, and the tiers, the durations, the extras and the running total all
move together — which is the failure this repository has already had three
times with country counts typed into copy.
"""
import json
import os

from .model import ROOT

DATA = os.path.join(ROOT, "tourism", "rates.json")


def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def esc(v):
    import html as h
    return h.escape(str(v if v is not None else ""), quote=True)


def money(n):
    return "${:,}".format(int(n))


def priced(d):
    """-> the subtree of this file that can put a figure on a page.

    Everything else in rates.json is prose: the names, the lines, the reasons,
    the paragraph about who feeds the driver. Those can be rewritten all day
    without any journey being worth a different amount. This is the part that
    cannot.

    Sorted and canonical so that two runs over the same numbers agree, and so
    that reordering a list in the file — which changes nothing anybody pays —
    does not read as a price change.
    """
    return {
        "arrival": d["arrival"]["rate"],
        "durations": sorted(d["durations"]),
        "tiers": sorted((t["id"], t["rate"]) for t in d["tiers"]),
        "service": sorted((r["name"], r["low"], r["high"]) for r in d["service"]),
        "options": sorted(
            (g["id"], sorted((c["id"], c.get("rate")) for c in g["choices"]))
            for g in d["options"]),
    }


def version(d=None):
    """-> a short fingerprint of what this file charges, e.g. "a1b2c3d4e5f6".

    A journey being planned two years out is priced against the rate card as it
    stood on the day it was planned, and the rate card is a file somebody edits.
    Without a version, a traveller who set a target in March and reads it again
    in September has no way to know whether the number moved because they
    changed something or because we did — and neither has anybody answering
    their letter.

    Derived rather than declared, because a version field in the JSON is a
    field somebody forgets to bump, and a forgotten version is worse than none:
    it asserts that nothing changed.
    """
    import hashlib
    canon = json.dumps(priced(d if d is not None else load()),
                       separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def drift(src, d):
    """Every dollar figure in the tunnel has to be a figure this file knows.

    The generated blocks are safe by construction. The prose around them is
    not: an opening plate said "$350 a day — Afrinkong Signature" for as long as
    it took someone to scroll one section further and read $650. A hand-written
    price that contradicts the table under it is worse than no price, because
    the reader believes the first one.

    So: collect every number rates.json can legitimately put on the page, read
    every $figure out of the page, and report the ones that came from nowhere.
    """
    import re
    known = {d["arrival"]["rate"]}
    for t in d["tiers"]:
        known.add(t["rate"])
    for row in d["service"]:
        known.update((row["low"], row["high"]))
    for g in d["options"]:
        known.update(c["rate"] for c in g["choices"] if "rate" in c)
    # Anything the configurator can total: days x tier, plus options, plus arrival.
    for t in d["tiers"]:
        for n in d["durations"]:
            base = t["rate"] * n
            for extra in [0] + [c["rate"] for g in d["options"]
                                for c in g["choices"] if c.get("rate")]:
                known.add(base + extra * n)
                known.add(base + extra * n + d["arrival"]["rate"])
    seen = {int(m.replace(",", "")) for m in re.findall(r"\$([\d,]+)", src)}
    return sorted(seen - known)


# --- the ground stage, in the tunnel's own language --------------------------
#
# The tunnel already speaks in jn-card / jn-chip / af-btn. This stage uses the
# same three, so the last question does not arrive looking like a checkout form
# bolted onto the end of an editorial sequence. A radio input inside a label,
# visually hidden and styled through :has() — the pattern every other question
# in /journey uses — keeps it operable from the keyboard.


def card(name, value, title, line, amount="", unit="", checked=False, rate=None,
         once=None, quote=False, mod=""):
    """One choice. The rate travels as data, never as parsed text.

    An earlier version totalled the journey by reading the dollars back out of
    the card's own label, which worked until a label said "Included" instead of
    "$0" and the total silently stopped counting that group.

    The amount is set apart from its unit because the generic card meta —
    .jn-card-n, 9.5px mono — is right for "3-4 days" on the pacing question and
    wrong here. It made $650 the smallest text on a card whose entire job is to
    say $650, sitting beside a 26px name. A price that has to be hunted for
    reads as a price somebody would rather you did not read.
    """
    at = ['type="radio"', 'name="%s"' % esc(name), 'value="%s"' % esc(value)]
    if checked:
        at.append("checked")
    if rate is not None:
        at.append('data-rate="%d"' % rate)
    if once is not None:
        at.append('data-once="%d"' % once)
    if quote:
        at.append('data-quote="true"')
    money_bit = ('<span class="jn-card-n"><b class="jn-card-amt">%s</b>%s</span>'
                 % (esc(amount), '<i>%s</i>' % esc(unit) if unit else "")) if amount else ""
    # "Included" and "Quoted" sit in the price slot but are not sums, and set at
    # the size a dollar figure earns they shout louder than the dollar figures.
    word = "" if amount.startswith("$") else ' data-word="true"'
    return (
        '<label class="jn-card jn-card--row jn-card--rate%s"%s>'
        '<input %s>'
        '<span class="jn-card-in"><b>%s</b>'
        '<span class="jn-card-line">%s</span>%s</span></label>'
        % (mod, word, " ".join(at), esc(title), esc(line), money_bit))


def block_ground(d):
    """The fifth question: what the ground costs, once the shape is known."""
    arrival = d["arrival"]
    out = ['<form class="jn-g" id="jn-g" data-arrival="%d">' % arrival["rate"]]

    out.append('<fieldset class="jn-g-set"><legend class="jn-h2">How many days on the ground?</legend>')
    out.append('<div class="jn-chips" role="group" aria-label="How many days">')
    for n in d["durations"]:
        out.append(
            '<label class="jn-chip"><input type="radio" name="days" value="%d"%s>'
            '<span>%d days</span></label>'
            % (n, " checked" if n == d["default_days"] else "", n))
    out.append(
        '<label class="jn-chip jn-chip--other"><input type="radio" name="days" value="other">'
        '<span>Other <input type="number" name="days_other" min="1" max="120" '
        'placeholder="days" aria-label="How many days"></span></label>')
    out.append('</div><p class="jn-note">Carried from what you already told us, '
               'and yours to change.</p></fieldset>')

    out.append('<fieldset class="jn-g-set"><legend class="jn-h2">Which journey?</legend>')
    out.append('<div class="jn-cards jn-cards--rows" role="group" aria-label="Which journey">')
    for t in d["tiers"]:
        out.append(card("tier", t["id"], t["name"], t["line"],
                        money(t["rate"]), "a day",
                        checked=t["id"] == d["default_tier"], rate=t["rate"],
                        mod=" is-rec" if t.get("recommended") else ""))
    out.append('</div></fieldset>')

    for g in d["options"]:
        out.append('<fieldset class="jn-g-set"><legend class="jn-h2">%s</legend>'
                   % esc(g["name"]))
        out.append('<p class="jn-lede">%s</p>' % esc(g["ask"]))
        out.append('<div class="jn-cards jn-cards--rows" role="group" aria-label="%s">'
                   % esc(g["name"]))
        for c in g["choices"]:
            if c.get("quote"):
                amount, unit = "Quoted", "for your destination"
            elif c.get("rate"):
                amount, unit = money(c["rate"]), "a day"
            else:
                amount, unit = "Included", ""
            out.append(card(g["id"], c["id"], c["name"], c.get("say", ""),
                            amount, unit, checked=bool(c.get("default")),
                            rate=c.get("rate"), quote=bool(c.get("quote"))))
        out.append('</div>')
        if g.get("note"):
            out.append('<p class="jn-note">%s</p>' % esc(g["note"]))
        out.append('</fieldset>')

    out.append(
        '<div class="jn-g-sum" aria-live="polite">'
        '<span class="af-stamp">Afrinkong service</span>'
        '<p class="jn-g-tot"><b data-total></b><span data-basis></span></p>'
        '<p class="jn-g-fine">Destination charges &mdash; park and conservation '
        'fees, permits, entrance &mdash; are calculated for your itinerary and '
        'added at cost. We settle them, so you are never at a gate working out '
        'what you owe.<span data-quote hidden> Some of what you have chosen is '
        'quoted once your destination is known.</span></p></div>')

    out.append('<div class="jn-g-need"><p class="jn-g-need-say">Before we can '
               'confirm a ground journey:</p>')
    for r in d["requirements"]:
        out.append('<label class="jn-g-row"><input type="checkbox" name="has" '
                   'value="%s" required><span>%s</span></label>'
                   % (esc(r["id"]), esc(r["say"])))
    out.append('<label class="jn-g-row"><input type="checkbox" name="has" '
               'value="excluded" required><span>I understand that '
               'accommodation, food, permits, entrance fees and personal '
               'expenses are not included unless I add them.</span></label>')
    out.append('</div></form>')
    return "".join(out)


def block_notincluded(d):
    """Said at the same size as the price, not in small print underneath it."""
    return (
        '<div class="jn-g-two">'
        '<div><h3 class="jn-h3">We arrange these, at cost</h3><ul class="jn-g-list">%s</ul>'
        '<p class="jn-note">Paid to us once, settled by us on the ground, and '
        'shown at what they actually cost.</p></div>'
        '<div><h3 class="jn-h3">And these stay yours</h3><ul class="jn-g-list is-not">%s</ul></div>'
        '</div>' % ("".join("<li>%s</li>" % esc(v) for v in d["destination_charges"]),
                    "".join("<li>%s</li>" % esc(v) for v in d["excluded"])))
