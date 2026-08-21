"""/trust — who you are dealing with, and why it is them.

    python3 tools/tourism/build.py entities

THE MODULE THAT NOBODY COULD READ.

`scripts/entities.js` encodes the single fact this business most needs a
customer to be able to establish: which of three companies is acting at any
moment. Three layers, ten acts, six that must declare, and a classifier that
takes entity + context + position + action rather than guessing from a URL. It
is guarded by seventeen checks and described in a 169-line document.

It was loaded by no page. A customer could not learn from this website the one
thing the model exists to make knowable.

THE COPY IS THE MODULE'S OWN.

Every layer description and every reason on this page is the `does` and `why`
string out of `entities.js`. That is not a shortcut — those strings were
already written in customer-facing language, for exactly this purpose, and
retyping them into a template is how the page and the model start disagreeing.
The page is a *rendering* of the model. A check asserts every act in ACTS
appears on it, so an act added to the model cannot quietly fail to appear.

THE TRAP ON THIS PARTICULAR PAGE.

`tourism/operators.json` gives Kamerun a `url` of `/cameroon`, and it would be
the obvious thing to link. It is also precisely the confusion this page exists
to dispel: `/cameroon` is Cameroon, one of fifty-four countries, and belongs to
Explore. That a ground operation happens to be based there is a different fact
about a different layer, and `docs/entity-architecture.md` names this exact
example. So an operator is linked to the operator's OWN surface where it has
one, and to nothing where it does not — never to the country it works in.

And the links are body links in context, never calls to action.
`entity-checks.js` fails a primary button pointing at the operator's desk, and
it is right to: a page explaining the boundary must not cross it while doing so.
"""

import json
import os
import re

from . import plate
from .model import ROOT

PAGE = os.path.join(ROOT, "trust.html")
MODULE = os.path.join(ROOT, "scripts", "entities.js")
OPERATORS = os.path.join(ROOT, "tourism", "operators.json")

# The operator's own front door. `/about` is the page that describes the ground
# operation itself — see plate.OPERATOR_NAV, where it is labelled "The
# Operator". Kamerun is the one operation with pages on this site; the other
# two are separate sites and carry their own absolute URL in operators.json.
KAMERUN_OWN = "/about"


def esc(v):
    return plate.esc(v)


def _strings(src, start, end):
    """Pull one object literal out of the module by its declaration."""
    m = re.search(re.escape(start) + r"(.*?)" + end, src, re.S)
    if not m:
        raise ValueError(
            "trust_page: could not find %s in scripts/entities.js. This page "
            "renders the module rather than restating it, so a shape change "
            "must stop the build instead of producing a page that quietly "
            "describes a model that is no longer there." % start.strip())
    return m.group(1)


def _js_string(chunk, key):
    """A JS string value, including the `'a' + 'b'` continuation form.

    entities.js wraps its longer sentences across lines with `+`, which a naive
    single-quote match truncates at the first fragment — and a truncated
    sentence is worse than a missing one, because it still reads as a sentence.
    """
    m = re.search(r"\b%s:\s*((?:'(?:[^'\\]|\\.)*'\s*\+?\s*)+)" % key, chunk, re.S)
    if not m:
        return None
    parts = re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))
    return "".join(parts).replace("\\'", "'")


def model():
    src = open(MODULE, encoding="utf-8").read()

    layers = []
    layer_src = _strings(src, "var LAYER = {", r"\n  \};")
    for key in ("afrinkong", "wankong", "operator"):
        chunk = re.search(re.escape(key) + r":\s*\{(.*?)\n    \}", layer_src, re.S)
        if not chunk:
            raise ValueError("trust_page: LAYER has no %s" % key)
        c = chunk.group(1)
        layers.append({
            "key": key,
            "layer": _js_string(c, "layer"),
            "name": _js_string(c, "name"),
            "legal": _js_string(c, "legal"),
            "does": _js_string(c, "does"),
        })

    must = re.search(r"var MUST_DECLARE = \[([^\]]*)\]", src)
    must_declare = re.findall(r"'([a-z]+)'", must.group(1)) if must else []

    acts = []
    act_src = _strings(src, "var ACTS = {", r"\n  \};")
    # THE TRAILING NEWLINE MUST NOT BE CONSUMED.
    #
    # The first version ended the group with `\n(?=    [a-z]+:|\s*\};)`. The
    # lookahead does not consume, but that `\n` does — and it is the same
    # newline the *next* entry's `\n    ` prefix needs to match. So finditer
    # took every other act: 5 of 10, dropping plan, book, cancel, support and
    # desk. Four of the six that must declare were among the missing, and the
    # page would have rendered a shorter table that still looked complete.
    for m in re.finditer(r"\n    ([a-z]+):\s*\{(.*?)(?=\n    [a-z]+:|\n  \};)",
                         act_src + "\n  };", re.S):
        name, c = m.group(1), m.group(2)
        actor = re.search(r"actor:\s*ENTITY\.([A-Z]+)", c)
        also = re.search(r"also:\s*ENTITY\.([A-Z]+)", c)
        acts.append({
            "act": name,
            "actor": actor.group(1).lower() if actor else None,
            "also": also.group(1).lower() if also else None,
            "declares": "declares: true" in c,
            "why": _js_string(c, "why"),
        })

    if not acts:
        raise ValueError("trust_page: no acts parsed out of ACTS")
    if not must_declare:
        raise ValueError("trust_page: MUST_DECLARE is empty")

    # A PARTIAL PARSE MUST NOT LOOK LIKE A COMPLETE ONE.
    #
    # This is the guard the regex bug above needed and did not have: a table of
    # five acts reads exactly as convincingly as a table of ten. So the count
    # is checked against the declarations in the source independently of the
    # parser that built the list, and every act named in MUST_DECLARE has to be
    # among them — those six are the ones where somebody's money is at stake,
    # and they are precisely the ones it would be worst to silently omit.
    declared = set(re.findall(r"\n    ([a-z]+):\s*\{", act_src))
    got = {a["act"] for a in acts}
    if got != declared:
        raise ValueError(
            "trust_page: parsed %d acts but ACTS declares %d — missing %s. "
            "A short table looks as complete as a full one, so this stops the "
            "build." % (len(got), len(declared),
                        ", ".join(sorted(declared - got)) or "none"))
    missing = [a for a in must_declare if a not in got]
    if missing:
        raise ValueError(
            "trust_page: MUST_DECLARE names %s, which the page did not parse. "
            "These are the acts where money or entitlement is at stake."
            % ", ".join(missing))

    return {"layers": layers, "acts": acts, "must": must_declare}


def operators():
    with open(OPERATORS, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for key, op in data.items():
        url = op.get("url") or ""
        # NEVER the country. See the module docstring: /cameroon is a
        # destination, and pointing at it here would say the operator and the
        # country are the same thing on the one page insisting they are not.
        own = KAMERUN_OWN if url.startswith("/") else url
        out.append({
            "name": op.get("name"), "base": op.get("base"),
            "since": op.get("since"), "line": op.get("line"),
            "own": own if own.startswith("http") or own == KAMERUN_OWN else "",
        })
    return out


NAMES = {"afrinkong": "Afrinkong", "wankong": "Wankong LLC",
         "operator": "the operator"}


def layers_html(m):
    rows = []
    for i, L in enumerate(m["layers"], 1):
        name = L["name"] or "The named ground operation"
        legal = ""
        if L["key"] == "afrinkong":
            legal = ("<span class=\"af-stamp\">a trading name</span>")
        elif L["legal"]:
            legal = ("<span class=\"af-stamp\">the company</span>")
        else:
            legal = ("<span class=\"af-stamp\">named per country</span>")
        rows.append(
            '<li class="af-layer">'
            '<p class="af-layer-n">%s</p>'
            '<h3>%s %s</h3>'
            '<p>%s</p></li>'
            % (esc(L["layer"]), esc(name), legal, esc(L["does"] or "")))
    return "\n      ".join(rows)


def acts_html(m):
    rows = []
    for a in m["acts"]:
        who = NAMES.get(a["actor"], a["actor"] or "")
        if a["also"]:
            who += " <i>and %s</i>" % NAMES.get(a["also"], a["also"])
        rows.append(
            '<tr%s><th scope="row">%s</th><td>%s</td><td>%s</td></tr>'
            % (' class="is-declare"' if a["declares"] else "",
               esc(a["act"]), who, esc(a["why"] or "")))
    return "\n        ".join(rows)


def ops_html(ops):
    rows = []
    for o in ops:
        who = esc(o["name"] or "")
        if o["own"]:
            who = '<a href="%s">%s</a>' % (esc(o["own"]), who)
        rows.append(
            '<li class="af-op"><h3>%s</h3>'
            '<p class="af-note">%s &middot; since %s</p>'
            '<p>%s</p></li>'
            % (who, esc(o["base"] or ""), esc(str(o["since"] or "")),
               esc(o["line"] or "")))
    return "\n      ".join(rows)


def render(m, ops):
    return TEMPLATE % {
        "og": plate.open_graph(
            "Who you are dealing with \u2014 Afrinkong",
            "Three companies' worth of responsibility run through this "
            "product. Which one is acting, at every moment it matters.",
            "/trust"),
        "preload": plate.PRELOAD,
        "mast": plate.shell(here="/trust"),
        "foot": plate.colophon_foot("/trust"),
        "events": plate.events_block(),
        "layers": layers_html(m),
        "acts": acts_html(m),
        "ops": ops_html(ops),
        "nmust": len(m["must"]),
        "ndecl": len([a for a in m["acts"] if a["declares"]]),
        "nacts": len(m["acts"]),
    }


def run(log=print):
    m = model()
    ops = operators()
    html = render(m, ops)
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("trust page: /trust (%.1f KB) \u2014 %d layers, %d acts, %d must "
        "declare, %d ground operations"
        % (len(html) / 1024.0, len(m["layers"]), len(m["acts"]),
           len(m["must"]), len(ops)))
    return [PAGE]


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Who you are dealing with &mdash; Afrinkong</title>
<meta name="description" content="Three companies' worth of responsibility run through this product. Which one is acting, at every moment it matters.">
%(og)s
<meta name="theme-color" content="#10251F">
%(preload)s
<link rel="stylesheet" href="/styles/afrinkong.css">
</head>
<body class="af af--explain" data-family="explain">
<a class="af-skip" href="#layers">Skip to the three layers</a>
%(mast)s
<main>
  <section class="af-frame af-ex-open">
    <h1>Who you are dealing with</h1>
    <p class="af-note">Three companies&rsquo; worth of responsibility run
      through this product, and you are entitled to know which one you are
      dealing with at any moment &mdash; on the surface where it matters,
      not inferable from a footer.</p>
  </section>

  <div class="af-frame" id="layers">
    <ul class="af-layers">
      %(layers)s
    </ul>
  </div>

  <div class="af-frame af-explain">
    <article class="af-ex">
      <h2>Money is always the company</h2>
      <p>Everything that moves money or entitlement is <b>Wankong LLC</b>.
        Not Afrinkong, which is a name. Not the operator, who is a supplier.
        Journeys are quoted, invoiced and settled in US dollars to Wankong
        LLC, and <a href="/travel-points">Travel Points</a> &mdash; when a
        programme is ever able to issue any &mdash; are issued by that same
        company under written terms.</p>
      <p>Nothing on this site takes a payment today, which is exactly why the
        rule is written now. A surface that carries a card field or a
        &ldquo;pay&rdquo; button without naming the payee <b>on itself</b>
        fails a check, and that check was verified by building such a page and
        watching it fail.</p>
    </article>

    <article class="af-ex">
      <h2>Every act, and who performs it</h2>
      <p>All %(nacts)s of them. %(ndecl)s declare who is acting. %(nmust)s of
        those are the ones where your money, your entitlement or your trip is
        at stake &mdash; the rest is the operator&rsquo;s own desk saying that
        it is the operator&rsquo;s, which is a courtesy rather than an
        obligation.</p>
      <div class="af-scroll">
        <table class="af-acts">
          <caption class="af-note">Rows marked &bull; must name the acting
            party on the surface where the act occurs.</caption>
          <thead><tr><th scope="col">Act</th><th scope="col">Who acts</th>
            <th scope="col">Why them</th></tr></thead>
          <tbody>
        %(acts)s
          </tbody>
        </table>
      </div>
    </article>

    <article class="af-ex">
      <h2>Two of them have two answers</h2>
      <p>A booking is an agreement with one company and days run by another,
        and telling you only half of that is how <i>&ldquo;who do I
        call&rdquo;</i> becomes unanswerable. So where an act has a second
        party, both are named above rather than one.</p>
      <p>Support splits the same way, and the split is the useful part:
        before you travel it is Afrinkong; while you are travelling it is the
        people who are with you.</p>
    </article>

    <article class="af-ex">
      <h2>A link is not a URL</h2>
      <p>The first guard on this boundary classified links by address, with a
        list of operator paths forbidden in certain places. That is wrong twice
        over. <a href="/cameroon">Cameroon</a> is one of fifty-four countries
        and belongs in Explore; that a ground operation is based there is a
        different fact about a different layer. And an operator&rsquo;s own
        desk is perfectly correct on a page where you are explicitly dealing
        with that operator.</p>
      <p>So a link is judged by <b>entity, context, position and action</b>
        together &mdash; any one of them alone gives the wrong answer. The same
        address in the body of a page about an operation is fine; in the
        primary navigation, or as a primary button, it is a misdirection. What
        turns a misdirection into a handover is <b>declaring it</b>. Crossing
        a boundary is fine. Crossing it silently is not.</p>
    </article>
  </div>

  <div class="af-frame">
    <h2>The ground operations</h2>
    <p class="af-note">Named, and reachable. These are the people who run your
      days.</p>
    <ul class="af-ops">
      %(ops)s
    </ul>
  </div>
</main>
%(foot)s
%(events)s
</body>
</html>
"""
