"""Who the traveller is contracting with, written from one file.

    python3 tools/tourism/build.py company

The tunnel quotes a ground journey in US dollars and says the money goes to
Wankong LLC. Someone who reads that has one fair question — who is Wankong, I
came here for Afrinkong — and until now the site could not answer it. The
words "Wankong LLC" were nowhere in the codebase, and the homepage footer
said, in as many words, that contact details on the page were illustrative
until verified. A price is worth exactly as much as the company behind it is
identifiable.

So the company is data, and every footer that names it is generated. Nine
hand-typed copies of a registration number is nine chances to be wrong in
three of them, and this repository has already had that failure with country
counts.

ONE THING THIS FILE IS CAREFUL ABOUT

The Delaware address is a REGISTERED office and is labelled as one everywhere
it appears. 8 The Green in Dover is a registered-agent address shared by a
very large number of Delaware companies. Publishing it as the registered
office is correct and ordinary. Presenting it as an operating address — a
place to visit, telephone or send documents — would be a claim about the
business that is not true, so `where()` prints the label and never a bare
address, and no template here puts it next to a telephone number or a "come
and see us".
"""

import html as html_mod
import json
import os
import re

from .model import ROOT

DATA = os.path.join(ROOT, "tourism", "company.json")

# Which pages carry it is decided by the marker in the page, not by a list
# here. A list would have to be kept in step with 1,458 generated place pages
# and portraits, and the first time it fell behind the company line would
# quietly stop appearing on most of the site.
#
# The Kamerun cluster has no marker, deliberately. Those footers carry the
# operator's own credentials — the MINTOUL licence, the Mount Cameroon
# Ecotourism Organisation — which are true, local, and theirs. Replacing them
# with a Delaware registration would swap real local facts for a foreign one.
SKIP = {"node_modules", ".git", "tourism"}


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def where(d, join=", "):
    """The registered office, always carrying its label."""
    o = d["office"]
    return "%s: %s, %s, %s %s, %s" % (
        o["kind"], o["street"], o["city"], o["region"], o["postcode"],
        o["country"]) if join == ", " else join.join(
        [o["kind"], o["street"], o["city"],
         "%s %s" % (o["region"], o["postcode"]), o["country"]])


def block_company(d):
    """One line, for the bar at the bottom of a footer."""
    o = d["office"]
    return (
        # No separator before the office: it is a block and the middot was
        # left dangling at the end of the line above it.
        '<span class="af-co-brand">%s</span> is a trading name of '
        '<b>%s</b> &middot; %s &middot; Registration No. %s'
        # No "Registered office:" label. It sits directly under a line giving
        # the jurisdiction and the registration number, so it already reads as
        # registration detail rather than a door to knock on — and the label
        # was the loudest thing in the quietest part of the page.
        '<span class="af-co-where">%s &middot; %s, %s %s</span>'
        % (esc(d["brand"]), esc(d["legal"]), esc(d["jurisdiction"]),
           esc(d["registration"]), esc(o["street"]),
           esc(o["city"]), esc(o["region"]), esc(o["postcode"])))


def block_colophon(d):
    """The last line on the page: whose copyright, and nothing else.

    Privacy, Terms and Cookies are not here. /privacy, /terms and /cookies do
    not exist, and a colophon that links to three 404s is less trustworthy than
    one that stays quiet — this is the strip a reader checks when they want to
    know who they are dealing with, so it is the worst possible place to be
    caught out. Write the pages and this will carry them.
    """
    return '&copy; %d %s' % (d["colophon"]["since"], esc(d["legal"]))


def block_whopays(d):
    """Said where the money is, not only at the bottom of the page."""
    return ('<p class="jn-g-who"><b>%s</b> %s</p>'
            % (esc(d["relation"]), esc(d["money"])))


def splice(src, blocks, where_):
    for name, body in blocks.items():
        open_m, close_m = "<!-- gen:%s -->" % name, "<!-- /gen:%s -->" % name
        if open_m not in src:
            continue
        pattern = re.compile(r"(%s\n?).*?(\s*%s)"
                             % (re.escape(open_m), re.escape(close_m)), re.S)
        src, hits = pattern.subn(lambda m: m.group(1) + body + m.group(2),
                                 src, count=1)
        if not hits:
            raise ValueError("gen:%s is present in %s but nothing was written "
                             "into it" % (name, where_))
    return src


def pages():
    """Every built page that asks for the company line."""
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as fh:
                if "<!-- gen:company -->" in fh.read():
                    yield path


def run(log=print):
    d = load()
    blocks = {"company": block_company(d), "colophon": block_colophon(d)}
    seen = touched = 0
    for path in pages():
        seen += 1
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        out = splice(src, blocks, os.path.relpath(path, ROOT))
        if out != src:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(out)
            touched += 1
    log("company: %s, trading as %s, into %d of %d page(s) that ask for it"
        % (d["legal"], d["brand"], touched, seen))
    return touched


def block_who(d, css="pl-who", stamp=True):
    """Who would take you, answered with who does rather than who does not.

    The block this replaces opened with "Not us, in Senegal" and closed with
    "Ask anyway", on roughly thirteen hundred place pages, the homepage, the
    atlas, the tunnel, /meet and the enquiry form. It was written to be
    scrupulously honest at a time when the only product was three local
    operators, and honest it was.

    It is now weak and out of date at once. Out of date because the ground
    journey is Afrinkong's own across all fifty-four countries, so "nobody of
    ours runs it" stopped being true. Weak because answering "who would take
    you" with a country we do not operate in sells nothing, and a reader
    deciding where to spend four thousand dollars does not need our
    org chart — they need to know somebody has the road.

    Availability, coverage and exclusions belong in the booking flow and the
    terms, where a traveller has asked. Not in the middle of the reason to go.
    """
    w = d["who"]
    return (
        '<div class="%s">%s<b>%s</b><p>%s</p><p class="%s-more">%s</p>'
        '<a class="af-go" href="%s">%s &rarr;</a></div>'
        % (esc(css),
           '<span class="af-stamp">%s</span>' % esc(w["stamp"]) if stamp
           else '<span>%s</span>' % esc(w["stamp"]),
           esc(w["name"]), esc(w["say"]), esc(css), esc(w["more"]),
           esc(w["href"]), esc(w["act"])))


def who_js(d):
    """The same words for the three scripts that build this block in the page."""
    w = d["who"]
    return {k: w[k] for k in ("stamp", "name", "say", "more", "act", "href")}
