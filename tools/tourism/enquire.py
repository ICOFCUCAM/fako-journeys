"""/enquire — where a journey built in the tunnel actually arrives.

    python3 tools/tourism/build.py enquire

WHY THIS PAGE HAD TO EXIST

The tunnel ended at /contact, and /contact is Kamerun's. A traveller who
answered four questions, was shown Eritrea, composed Asmara and Massawa and
priced the ground in US dollars then landed on a page headed KAMERUN, under
"Discover Cameroon.", beside a Douala street address, a Buea street address, a
+237 telephone number and a button offering to plan a circuit. The journey text
carried across perfectly. Everything around it belonged to a different company
on a different side of the continent.

That is not a routing detail. It is the last thing a traveller sees before
deciding whether these people can be trusted with four thousand dollars, and it
said the quiet part out loud: this was a Cameroon tour operator's site with a
continent bolted on.

WHAT THIS IS

Afrinkong's own enquiry page, in the tunnel's language, carrying the journey
the tunnel built. It reads the same ?journey= parameter /contact does, so the
handoff is unchanged and nothing about the tunnel had to move.

Kamerun keeps /contact. A local operator with two offices, a landline and a
WhatsApp number should say so on its own pages — that page is good, it was
simply never Afrinkong's. Its addresses are real and specific and they belong
to Cameroon.

EVERY DETAIL COMES FROM tourism/company.json
The company, the registered office and the mailbox are read, never typed. The
mailbox is the one value on this page that is a placeholder rather than a fact,
and it is marked as such in that file.
"""

import html as html_mod
import os

from . import company, plate
from .model import ROOT

PAGE = os.path.join(ROOT, "enquire.html")


def esc(v):
    return html_mod.escape(str(v if v is not None else ""), quote=True)


def render():
    d = company.load()
    q = d["enquiries"]
    o = d["office"]
    return TEMPLATE % {
        "og": plate.open_graph(
            "Begin your journey — Afrinkong",
            "Send the journey you built. We arrange the ground wherever it goes.",
            "/enquire"),
        "events": plate.events_block(),
        "mail": esc(q["email"]),
        "say": esc(q["say"]),
        "hours": esc(q["hours"]),
        "relation": esc(d["relation"]),
        "money": esc(d["money"]),
        "company": company.block_company(d),
        "office": esc("%s, %s, %s %s" % (o["street"], o["city"], o["region"],
                                         o["postcode"])),
        "kind": esc(o["kind"]),
    }


def run(log=print):
    html = render()
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(html)
    log("enquire: %s (%.1f KB), journeys reach %s"
        % (os.path.relpath(PAGE, ROOT), len(html) / 1024.0,
           company.load()["enquiries"]["email"]))
    return PAGE


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Begin your journey &mdash; Afrinkong</title>
<meta name="description" content="Send us the journey you built. Afrinkong arranges the ground wherever it goes — the vehicle, the driver, the coordination.">
<link rel="canonical" href="https://afrinkong.com/enquire">
%(og)s
<link rel="stylesheet" href="/styles/afrinkong.css">
<link rel="stylesheet" href="/styles/journey.css">
<noscript><style>.fj-rise{opacity:1;transform:none}</style></noscript>
</head>
<body>
<a class="af-skip" href="#say">Skip to the form</a>
<header class="jn-mast">
  <a class="jn-mark af-lockup" href="/"><img class="af-emblem af-emblem--mast" src="/images/brand/mark-128.png" width="128" height="128" alt="" decoding="async" style="--af-emblem:34px"><i>Afrinkong</i><b>Begin your journey</b></a>
  <nav class="jn-routes" aria-label="Primary">
    <a href="/journey">Build a journey</a>
    <a href="/atlas">The Atlas</a>
    <a href="/meet">Meet Africa</a>
    <a href="/places">Every place</a>
    <a href="/stories">Stories</a>
  </nav>
  <a class="af-btn af-btn--quiet" href="/journey">Build a journey<i>&rarr;</i></a>
</header>

<main class="jn jn-enq" id="main">
  <div class="jn-enq-grid">
    <div class="jn-enq-say">
      <span class="af-stamp">Begin</span>
      <h1 class="jn-h1">Send us the journey <em>you built</em>.</h1>
      <p class="jn-lede">Nothing here commits you to anything and nothing is
        charged. We read what you have written, confirm what can be arranged on
        your dates, and come back with the figure in writing.</p>

      <dl class="jn-enq-facts">
        <div><dt>Written</dt><dd><a href="mailto:%(mail)s">%(mail)s</a></dd></div>
        <div><dt>Reply</dt><dd>%(hours)s</dd></div>
        <div><dt>Quoted in</dt><dd>US dollars</dd></div>
      </dl>

      <p class="jn-enq-note">%(say)s</p>

      <!-- The registered office, labelled. It is a registered-agent address in
           Delaware shared by a great many companies, so it is printed as what
           it is and never as somewhere to visit or telephone. -->
      <div class="jn-enq-co">
        <p><b>%(relation)s</b> %(money)s</p>
        <p class="jn-enq-office">%(kind)s: %(office)s</p>
      </div>
    </div>

    <!-- THE FORM HAS AN ACTION NOW, AND IT IS NOT DECORATION.
         With scripting off, a form with no action posts to its own URL: the
         page reloaded, the fields came back as a query string, and the enquiry
         was gone. Silently. On the one page this whole site exists to reach.
         A mailto action is imperfect — support varies and some browsers
         warn — but "opens something the visitor can see and cancel" beats
         "looks like it worked and did not". The script still intercepts and
         does the better job whenever it is there. -->
    <form class="jn-enq-form" id="say" method="post" enctype="text/plain"
      action="mailto:%(mail)s?subject=A%%20journey%%20built%%20on%%20afrinkong.com"
      data-lead-mailto="%(mail)s" data-lead-form
      data-lead-success="Thank you — your journey has reached us. We will come back within one working day with what can be arranged on your dates and the figure in writing."
      data-lead-error="That did not send. Please write to %(mail)s directly and paste your journey in — it is the text in the box below.">
      <div class="jn-enq-row">
        <div class="jn-enq-cell"><label for="enm">Your name</label><input id="enm" name="name" required></div>
        <div class="jn-enq-cell"><label for="eph">Telephone or WhatsApp</label><input id="eph" name="phone"></div>
      </div>
      <div class="jn-enq-row">
        <div class="jn-enq-cell"><label for="eem">Email</label><input id="eem" name="email" type="email" required></div>
        <div class="jn-enq-cell"><label for="edt">Dates or month</label><input id="edt" name="dates" placeholder="e.g. late November, two weeks"></div>
      </div>
      <div class="jn-enq-cell"><label for="epx">Travellers</label><input id="epx" name="party" placeholder="e.g. 2 adults"></div>
      <div class="jn-enq-cell">
        <label for="ejr">Your journey, as you built it &mdash; edit anything</label>
        <textarea id="ejr" name="journey" rows="10" data-journey-box></textarea>
      </div>
      <button class="af-btn af-btn--solid" type="submit">Send this journey<i>&rarr;</i></button>
      <p class="jn-enq-fine">Your details stay with us. No mailing list, no
        agents, nothing forwarded to third parties &mdash;
        <a href="/privacy">what we hold, and what we do not</a>.</p>
      <!-- THE WAY OUT WHEN THE SEND BUTTON CANNOT WORK.
           Pressing send hands the letter to the visitor's mail application. On
           a machine with none configured — a shared desktop, a locked-down
           laptop, a browser where webmail was never registered as the handler
           — nothing at all happens, and the visitor has no way of knowing
           that is what went wrong. So the address is printed where they can
           see it before they press anything, and the letter can be lifted in
           one press. Two ways to send the same thing is not clutter on the
           only page that converts. -->
      <p class="jn-enq-alt">Nothing happened when you pressed send? Your
        browser has no mail application set up. Write to
        <a href="mailto:%(mail)s">%(mail)s</a> and paste your journey in
        &mdash; it is the text in the box above.
        <button class="jn-enq-copy" type="button" data-copy-journey hidden>Copy
          my journey</button></p>
      <p class="jn-enq-flash" data-lead-success-msg></p>
      <p class="jn-enq-flash" data-lead-error-msg></p>
    </form>
  </div>

  <footer class="jn-enq-foot">
    <!-- gen:company -->
    <!-- /gen:company -->
  </footer>
</main>
%(events)s
<script>
(function(){
  /* The journey arrives as ?journey=, exactly as it does on /contact, and is
     dropped into the box rather than a hidden field so the traveller can read
     it, cut it and argue with it before it goes. An enquiry nobody can read
     before sending is a form, not a letter. */
  var box = document.querySelector('[data-journey-box]');
  var q = new URLSearchParams(location.search).get('journey');
  if (box && q) { box.value = q; box.setAttribute('rows', '14'); }
  else if (box) {
    box.setAttribute('placeholder', 'Tell us where you want to go, roughly how '
      + 'long you have and what you want out of it \u2014 or build one first at '
      + '/journey and it will arrive here already written.');
  }
  /* The copy button only exists where the clipboard does, which is why it
     ships hidden and is revealed here rather than being disabled on arrival.
     A control that is visible and does nothing is worse than one that is not
     there: the address beside it works either way. */
  var copy = document.querySelector('[data-copy-journey]');
  if (copy && navigator.clipboard) {
    copy.hidden = false;
    copy.addEventListener('click', function () {
      var box = document.querySelector('[data-journey-box]');
      if (!box || !box.value) return;
      navigator.clipboard.writeText(box.value).then(function () {
        copy.textContent = 'Copied \u2014 now paste it into an email';
      }, function () {
        copy.textContent = 'Could not copy \u2014 select the text above';
      });
    });
  }
  document.querySelectorAll('[data-lead-form]').forEach(function(fm){
    fm.addEventListener('submit', function(e){
      e.preventDefault();
      var to = fm.getAttribute('data-lead-mailto') || '';
      var lines = [];
      fm.querySelectorAll('input,textarea,select').forEach(function(i){
        if (i.type === 'hidden' || !i.value) return;
        var lab = fm.querySelector('label[for="' + i.id + '"]');
        lines.push((lab ? lab.textContent.trim() : (i.name || i.id)) + ': ' + i.value);
      });
      var note = fm.querySelector('[data-lead-success-msg]');
      if (note) {
        note.textContent = 'Opening your email app with this journey ready to '
          + 'send. If nothing happens, write to ' + to + ' directly.';
        note.className = note.className.replace(/(^| )on( |$)/, ' ') + ' on';
      }
      window.location.href = 'mailto:' + to + '?subject='
        + encodeURIComponent('A journey built on afrinkong.com')
        + '&body=' + encodeURIComponent(lines.join(String.fromCharCode(10)));
    });
  });
})();
</script>
</body>
</html>
"""
