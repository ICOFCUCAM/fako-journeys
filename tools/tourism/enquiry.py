"""Tell a visitor whose enquiry form they are standing in front of.

    python3 tools/tourism/build.py enquiry

/contact is the primary call of the entire site. Every Afrinkong page carries
"Plan a journey" and it points here; so does the closing block on the homepage,
which arrives with ?journey= already written out; so does the 404.

/contact is Kamerun's. It has Kamerun's masthead, Kamerun's four-item nav, a
Douala telephone number, "Plan a circuit" as its call, and a form that opens a
mailto to bonjour@kamerun.cm. Kamerun runs Cameroon. A visitor who has just
built a journey through Kenya and Tanzania on this site lands here, sees a page
that looks like it belongs to the site they were reading, fills in the form,
and emails a Cameroonian operator about the Serengeti.

Nothing on the page tells them. That is the whole defect, and it is not a
design problem — the page is well made — it is that one operator's enquiry desk
is standing in for the group's, silently.

Two things go in, both generated from the dataset so neither can drift:

  a bar under the masthead     saying where this form goes and who reads it,
                               with the way back to the atlas

  a script                     that reads ?journey= (and the URL generally),
                               finds the country names in it, and if Cameroon
                               is not among them says so before the form is
                               filled in rather than after it is sent

No email address is invented here. There is no group enquiry address anywhere
in this project, so the honest move is to name the operator this form reaches
and to point at the countries it does not cover, not to make one up.
"""

import json
import os
import re

from .model import ROOT, load_operators

PAGE = os.path.join(ROOT, "contact.html")
MARKERS = ("handoff", "reach")


def esc(v):
    import html as html_mod
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def covered(countries):
    """-> [(slug, name, operator name, operator url, operator base)]."""
    return [(c.slug, c.name, c.operator.name, c.operator.url, c.operator.base)
            for c in countries if c.operator and c.published]


def block_handoff(countries):
    """The bar under Kamerun's masthead, in Afrinkong's voice."""
    ours = covered(countries)
    # Whoever's desk this page actually is: the operator hosted on this domain
    # rather than on its own. The other two have their own sites and are links
    # away from here, not the page you are standing on.
    here = [row for row in ours if row[3].startswith("/")] or ours[:1]
    who = here[0]
    elsewhere = [row for row in ours if row[0] != who[0]]
    others = "".join(
        '<a href="%s">%s &mdash; %s</a>' % (esc(url), esc(name), esc(op))
        for _slug, name, op, url, _base in elsewhere)
    return (
        '<div class="fj-from" data-af-handoff>\n'
        '  <div class="fj-frame fj-from-in">\n'
        '    <p><b>You are on %s&rsquo;s enquiry page.</b> %s is the Afrinkong '
        'operator for %s, based in %s, and everything sent from this form is '
        'read by them.</p>\n'
        '    <p class="fj-from-else">Somewhere else in Africa? %s or start from '
        '<a href="/atlas">the atlas</a>.</p>\n'
        '  </div>\n'
        '</div>' % (esc(who[2]), esc(who[2]), esc(who[1]), esc(who[4]),
                    others or 'See <a href="/">the other operators</a>'))


def block_reach(countries):
    """What the page knows about which country belongs to whom.

    Inlined rather than fetched: this has to be true before the visitor starts
    typing, and a fetch that has not landed yet is the same as no warning.
    """
    ours = covered(countries)
    home = ours[0][0] if ours else ""
    reach = {
        "home": home,
        "ours": {slug: {"name": name, "op": op, "url": url}
                 for slug, name, op, url, _base in ours},
        "rest": {c.slug: c.name for c in countries
                 if c.published and not c.operator},
    }
    return ('<script type="application/json" id="fj-reach">%s</script>'
            % json.dumps(reach, ensure_ascii=False, separators=(",", ":")))


def splice(src, blocks):
    missing = [n for n in MARKERS if ("<!-- gen:%s -->" % n) not in src]
    if missing:
        raise ValueError("contact.html is missing markers: %s" % ", ".join(missing))
    for name, body in blocks.items():
        pattern = re.compile(r"(<!-- gen:%s -->\n).*?(\s*<!-- /gen:%s -->)"
                             % (name, name), re.S)
        src = pattern.sub(lambda m: m.group(1) + body + m.group(2), src, count=1)
    return src


def run(countries, page=None, log=print):
    page = page or PAGE
    with open(page) as fh:
        src = fh.read()
    live = [c for c in countries if c.published]
    out = splice(src, {"handoff": block_handoff(live), "reach": block_reach(live)})
    changed = out != src
    if changed:
        with open(page, "w") as fh:
            fh.write(out)
    log("%s the enquiry handoff (%d operators, %d countries without one) into %s"
        % ("rewrote" if changed else "no change:",
           sum(1 for c in live if c.operator),
           sum(1 for c in live if not c.operator),
           os.path.relpath(page, ROOT)))
    return changed
