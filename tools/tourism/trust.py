"""The pages a company owes the people who read it.

    python3 tools/tourism/build.py trust    ->  /privacy  /terms  /accessibility

WHAT WAS MISSING

Afrinkong asks for a name, an email, a telephone number and a description of
somebody's holiday, and had no privacy notice. It counts product events in the
browser, and had no page saying so. It quotes prices in bands and takes
enquiries about journeys costing tens of thousands of dollars, and had no
terms. There was no accessibility statement either, on a site that has spent
months passing a contrast and tap-target gate nobody could read about.

Five legal pages were missing and the footer linked to none of them, which is
the kind of gap that is invisible until the moment it is expensive.

THESE DESCRIBE WHAT THE CODE ACTUALLY DOES

Every factual claim on these pages was read out of the repository, not copied
from a template:

    scripts/events.js       no cookie, no identifier, no network call, and
                            Do Not Track and Global Privacy Control switch off
                            the counting as well as the sending
    enquire.html            the six fields the form has, and the fact that it
                            hands them to the visitor's own mail client rather
                            than posting them anywhere
    tourism/rates.json      what a day rate covers and what is passed through
    tourism/transafrique.json   the deposit and balance terms

That matters more than the prose does. A privacy notice describing a tracking
system the site does not have is worse than none: it is a false statement about
the reader, written by somebody who did not look.

NOT LEGAL ADVICE, AND SAYING SO

This is an honest description of the system written by the people who built it.
It is not drafted by a lawyer and the trading entity is a Delaware LLC selling
into several jurisdictions. Before this is relied on commercially it wants a
solicitor's eye — which is a sentence that belongs in this docstring and in the
brief to whoever reviews it, not on the page, where it would read as a hedge.
"""

import html as html_mod
import json
import os

from .model import ROOT

PAGES = {
    "privacy": "privacy.html",
    "terms": "terms.html",
    "accessibility": "accessibility.html",
}


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def load(name):
    with open(os.path.join(ROOT, "tourism", name), encoding="utf-8") as fh:
        return json.load(fh)


def money(n):
    return "${:,}".format(int(n))


def block(title, *paras):
    body = "".join(
        p if p.lstrip().startswith("<") else "<p>%s</p>" % p for p in paras)
    return ('<section class="tr-block"><h2 class="tr-h2">%s</h2>%s</section>'
            % (esc(title), body))


def ul(items):
    return "<ul class=\"tr-list\">%s</ul>" % "".join(
        "<li>%s</li>" % i for i in items)


def dl(rows):
    """A definition list for the field-by-field table, which is the part of a
    privacy notice anybody actually reads."""
    return "<dl class=\"tr-fields\">%s</dl>" % "".join(
        "<div><dt>%s</dt><dd>%s</dd></div>" % (esc(k), esc(v)) for k, v in rows)


# --------------------------------------------------------------------------
# /privacy


def privacy():
    return "".join([
        block(
            "The short version",
            "Afrinkong holds what you type into an enquiry, because we cannot "
            "answer a question we have not been asked. Nothing else. There is "
            "no advertising network on this site, no analytics vendor, no "
            "cookie and no identifier that follows you from one page to the "
            "next — not as a policy we intend to keep, but as a fact "
            "about the code, which you can read."),
        block(
            "What the enquiry form collects",
            "The form at <a href=\"/enquire\">/enquire</a> has six fields:",
            dl([
                ("Your name", "so a reply can be addressed to somebody."),
                ("Email", "so there is somewhere to reply to."),
                ("Telephone or WhatsApp",
                 "optional. Given only if you would rather be called."),
                ("Your dates",
                 "free text, because “the last two weeks of March, "
                 "roughly” is a real answer."),
                ("How many of you", "a number, for vehicles and rooms."),
                ("Your journey",
                 "the description. If you used the journey builder this "
                 "arrives already written and you can change every word of "
                 "it before it goes."),
            ]),
            "<p>There is no hidden field. Nothing is collected that you cannot "
            "see on the page.</p>"),
        block(
            "Where it goes",
            "<p><strong>The form does not post your enquiry to a server.</strong> "
            "Pressing send hands the six fields to your own email application "
            "with the message already written, and you send it — or do "
            "not. Until you press send in your own mail client, nothing has "
            "left your device.</p>",
            "That is an unusual arrangement and it has a consequence worth "
            "stating plainly: your enquiry travels as ordinary email, with "
            "whatever privacy your mail provider and ours give it. Email is "
            "not a secure channel. Please do not send passport numbers, card "
            "details or anything else you would not put on a postcard. We will "
            "never ask for a card number by email."),
        block(
            "Counting, and how little of it there is",
            "The site counts a few product events — that a country page "
            "was opened, that a crossing was chosen. What it does with them is "
            "narrower than the word “analytics” suggests:",
            ul([
                "No cookie is set, by us or by anybody.",
                "No identifier is created, stored or read. Nothing joins one "
                "page-load to another, so there is no profile to build.",
                "No network request is made. With no destination configured, "
                "an event is validated and then discarded.",
                "Only values already published on this site can be recorded "
                "— a country slug, a month number. Free text has nowhere "
                "to go, which is deliberate: the journey builder has a box you "
                "type a sentence into, and recording that sentence would be "
                "the obvious mistake.",
                "If your browser sends Do Not Track or Global Privacy Control, "
                "the counting stops as well as the sending. A count that is "
                "kept is data that is held, whatever it was meant for.",
            ]),
            "<p>The rules above are enforced in code rather than promised in "
            "prose: an event not on the published list is dropped, and a "
            "property not named for that event is stripped before anything "
            "else happens.</p>"),
        block(
            "What other people's servers see",
            "Some photographs on this site are served from Unsplash and "
            "Pexels, and some pages are hosted on Vercel. Loading a page from "
            "any of them means your browser makes a request to them, and their "
            "servers see your IP address and what you asked for, as they would "
            "for any website. We do not send them anything about you and we "
            "receive nothing back about you. Their own notices govern what "
            "they do with a request they receive."),
        block(
            "Your rights, and how to use them",
            "You can ask what we hold about you, ask for a copy, ask for it "
            "corrected, or ask for it deleted. Because the only thing we hold "
            "is the email you sent us, “delete it” means we delete "
            "the correspondence, and it is a request we will action rather "
            "than argue with.",
            "Write to <a href=\"/contact\">us</a> and say what you want done. "
            "You do not need to give a reason."),
        block(
            "How long anything is kept",
            "Enquiry correspondence is kept while a journey is being arranged "
            "and for as long afterwards as the tax and liability rules of the "
            "jurisdiction require. An enquiry that never became a journey is "
            "deleted at your request, and otherwise is not kept indefinitely "
            "for its own sake."),
        block(
            "Who we are",
            "Afrinkong is a trading name of Wankong LLC, a Delaware limited "
            "liability company, registration number 10588061, at 8 The Green, "
            "Suite B, Dover, Delaware 19901, United States."),
    ])


# --------------------------------------------------------------------------
# /terms


def terms():
    rates = load("rates.json")
    tf = load("transafrique.json")
    low_day = min(t["rate"] for t in rates["tiers"])
    low_band = min(r["low"] for r in tf["routes"])
    return "".join([
        block(
            "What this page is",
            "These are the terms on which Afrinkong arranges a journey. They "
            "are written to be read rather than survived, and where a term is "
            "in our favour it says so instead of being buried."),
        block(
            "A quotation is not a booking",
            "Every figure on this site is a starting point. <a href=\"/how-it-"
            "works\">Two things are sold here</a> and they are quoted "
            "differently: time in one country is a rate, from %s per vehicle "
            "per day; a crossing of several is a band for the whole journey, "
            "from %s."
            % (money(low_day), money(low_band)),
            "Nothing is held and nothing is owed until we have sent you a "
            "written quotation for your dates and you have accepted it. A "
            "price on a page is what a journey of that shape has cost; a price "
            "in your quotation is what yours costs."),
        block(
            "What a price includes",
            "Each quotation itemises this, and the general shape is on "
            "<a href=\"/how-it-works\">how it works</a>. Park entrance, "
            "conservation and permit charges are arranged by us and passed "
            "through at cost, on top of the rate rather than inside it, so a "
            "park raising its fee changes your total and does not change our "
            "margin. International flights, visas and travel insurance are "
            "yours."),
        block(
            "Paying, and changing your mind",
            "A deposit confirms the dates and the balance falls due before "
            "travel; both figures and both dates are in your quotation. If you "
            "cancel, what is refundable depends on what we have already paid "
            "on your behalf — a lodge that has taken a non-refundable "
            "deposit is money that has gone, and we will show you the invoice "
            "rather than quote you a percentage."),
        block(
            "When we change something",
            "A road closes, a park changes a rule, a lodge burns down. If we "
            "have to change your journey we will tell you what changed and "
            "what it does to the price before we act on it, and if the change "
            "is material you may take the amended journey or take your money "
            "back."),
        block(
            "What we are responsible for",
            "We are responsible for arranging what your quotation says we will "
            "arrange, and for choosing the operators who deliver it. We are "
            "not responsible for weather, for wildlife declining to appear, "
            "for the acts of a government, or for anything you book yourself "
            "and tell us about afterwards.",
            "Travel insurance is a condition of travelling with us. Africa is "
            "large and some of these journeys are a long way from a hospital."),
        block(
            "The writing on this site",
            "The words, photographs and maps here are ours or licensed to us. "
            "The photographs credited to Unsplash and Pexels are used under "
            "those services' licences and belong to the photographers named "
            "with them. Read the site, quote it, link to it; do not "
            "reproduce it wholesale as your own."),
        block(
            "Law",
            "These terms are governed by the law of the State of Delaware, "
            "United States, where Wankong LLC is registered. If you are a "
            "consumer somewhere with stronger protections than that, this does "
            "not take them away from you."),
    ])


# --------------------------------------------------------------------------
# /accessibility


def accessibility():
    return "".join([
        block(
            "What we aim at",
            "This site is built to meet WCAG 2.2 at level AA. That is the "
            "target, and the paragraphs below say where it is met, how it is "
            "checked, and where it is not."),
        block(
            "How it is checked",
            "Not by intention. Every page in the gate is opened in a real "
            "browser at eight widths, from 320 pixels to 1600, and measured:",
            ul([
                "Text contrast is sampled against the colour actually behind "
                "it — composited through every translucent layer to the "
                "first opaque one, because a panel at 60% over a photograph "
                "is not the colour the stylesheet names.",
                "Every interactive target is measured in both dimensions, not "
                "just the one that passes.",
                "Every line of prose is measured, and one running past 92 "
                "characters fails the build.",
                "Nothing may scroll sideways at any of the eight widths.",
                "Every page is loaded once with scripting switched off, and "
                "must still read.",
            ]),
            "<p>The gate is 210 checks and it runs before anything ships.</p>"),
        block(
            "What is already true",
            ul([
                "Every page has a skip link, landmark regions and one h1.",
                "Nothing on this site depends on colour alone to be understood.",
                "Every content image carries alt text describing the "
                "photograph. Where a photograph came from a stock library the "
                "alt is the photographer's own description of it, not our "
                "caption — our caption describes what we went looking "
                "for, which is not the same claim.",
                "Anything that moves on its own can be stopped, and starts "
                "stopped if you have asked for reduced motion.",
                "The whole site works with scripting off. Every enhancement is "
                "added to a page that already reads.",
            ])),
        block(
            "Where it falls short",
            "Two things, stated rather than left to be discovered:",
            ul([
                "The maps are drawn as SVG and carry a text description, but a "
                "reader using a screen reader gets the summary rather than the "
                "shape. A map is a hard thing to describe and ours is not "
                "fully described yet.",
                "The journey builder is a long interactive form. It is "
                "keyboard-operable throughout, but it has not been tested "
                "end-to-end with a screen reader by somebody who uses one "
                "daily, and until it has we will not claim that it is good.",
            ])),
        block(
            "If something here does not work for you",
            "Tell us, and be as specific as you can bear to be — which "
            "page, which browser, what you were trying to do. We will fix it "
            "and we will tell you when it is fixed. Write to us at "
            "<a href=\"/contact\">contact</a>."),
    ])


# --------------------------------------------------------------------------


SPEC = {
    "privacy": {
        "eyebrow": "Privacy",
        "h1": "What we hold, and what we do not.",
        "lede": "Afrinkong keeps what you type into an enquiry and nothing "
                "else. No cookie, no identifier, no advertising network — "
                "which is a fact about the code rather than a promise about "
                "our intentions.",
        "desc": "What Afrinkong collects, where it goes, and how little of it "
                "there is. No cookies, no identifiers, no analytics vendor.",
        "body": privacy,
    },
    "terms": {
        "eyebrow": "Terms",
        "h1": "The terms, written to be read.",
        "lede": "How a quotation becomes a booking, what a price includes, "
                "what happens when something changes, and what each of us is "
                "responsible for.",
        "desc": "Afrinkong's booking terms: quotations, deposits, what a price "
                "includes, cancellation and liability.",
        "body": terms,
    },
    "accessibility": {
        "eyebrow": "Accessibility",
        "h1": "Built to be used, and measured to prove it.",
        "lede": "This site targets WCAG 2.2 AA. Here is how that is checked, "
                "what is already true, and the two places it falls short.",
        "desc": "Afrinkong's accessibility statement: the standard, how it is "
                "measured in a real browser, and where it falls short.",
        "body": accessibility,
    },
}


def run(countries=(), log=print):
    from . import plate
    out = []
    for key, spec in SPEC.items():
        html = TEMPLATE % {
            "og": plate.open_graph("%s — Afrinkong" % spec["eyebrow"],
                                   spec["desc"], "/%s" % key),
            "events": plate.events_block(),
            "eyebrow": esc(spec["eyebrow"]),
            "h1": esc(spec["h1"]),
            "lede": esc(spec["lede"]),
            "desc": esc(spec["desc"]),
            "title": esc(spec["eyebrow"]),
            "body": spec["body"](),
            "key": esc(key),
        }
        path = os.path.join(ROOT, PAGES[key])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        out.append(path)
        log("trust: %s (%.1f KB)"
            % (os.path.relpath(path, ROOT), len(html) / 1024.0))
    return out


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s &mdash; Afrinkong</title>
<meta name="description" content="%(desc)s">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<link rel="stylesheet" href="/styles/trust.css">
</head>
<body class="tr-body">
<a class="af-skip" href="#main">Skip to the text</a>
<header class="jn-mast">
  <a class="jn-mark" href="/"><i>Afrinkong</i><b>%(eyebrow)s</b></a>
  <nav class="jn-routes" aria-label="Primary">
    <a href="/atlas">The Atlas</a>
    <a href="/trans-afrique">Trans Afrique</a>
    <a href="/how-it-works">How it works</a>
    <a href="/places">Every place</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/enquire">Start a journey<i>&rarr;</i></a>
</header>

<main id="main" class="tr-page">
  <div class="tr-open">
    <p class="tr-eyebrow">%(eyebrow)s</p>
    <h1 class="tr-h1">%(h1)s</h1>
    <p class="tr-lede">%(lede)s</p>
  </div>
  <!-- The three read as one set, so each names the other two. A legal page
       that is a dead end makes the reader go back to the footer to find its
       neighbour, and the footer is the place they were trying to leave. -->
  <nav class="tr-also" aria-label="The other statements">
    <a href="/privacy">Privacy</a>
    <a href="/terms">Terms</a>
    <a href="/accessibility">Accessibility</a>
  </nav>
%(body)s
  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</main>
%(events)s
</body>
</html>
"""
