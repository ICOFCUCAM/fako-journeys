/* Whose desk is this? — /contact.
 * ---------------------------------------------------------------------------
 * The page is complete and correct without this. The bar above the form is in
 * the HTML and says, for every visitor, that this form reaches Kamerun in
 * Douala and Buea. That much needs no JavaScript and gets none.
 *
 * What needs a browser is the specific case: a visitor arriving from the
 * journey builder with ?journey= already written out. That sentence names
 * countries. If none of them is a country Kamerun runs, the visitor is about to
 * send a Cameroonian operator a letter about the Serengeti, and the moment to
 * say so is before the form is filled in, not in the reply a day later.
 *
 * It names countries and operators only. It does not rewrite the enquiry, does
 * not redirect, and does not block sending — a traveller is allowed to write to
 * whoever they like, and being told is the whole of what was missing.
 */
(function () {
  'use strict';

  var node = document.getElementById('fj-reach');
  var bar = document.querySelector('[data-af-handoff]');
  if (!node || !bar) return;

  var reach;
  try { reach = JSON.parse(node.textContent || '{}'); } catch (e) { return; }
  var ours = reach.ours || {};
  var rest = reach.rest || {};
  if (!reach.home || !ours[reach.home]) return;

  /* What the visitor brought with them. The journey sentence is the reliable
     one; the rest of the query string is read too, because a link somebody
     pasted may carry a country and nothing else. */
  var said = '';
  try {
    said = decodeURIComponent((location.search || '').replace(/\+/g, ' '));
  } catch (e) { said = location.search || ''; }
  if (!said) return;

  function saidIn(name) {
    /* Word boundaries by hand: "Chad" must not match inside "Chadian", and a
       country whose name is two words has to match as two words. */
    var safe = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp('(^|[^A-Za-z])' + safe + '([^A-Za-z]|$)', 'i').test(said);
  }

  var named = [], covered = [], slug;
  for (slug in ours) {
    if (saidIn(ours[slug].name)) { named.push(slug); covered.push(slug); }
  }
  for (slug in rest) {
    if (saidIn(rest[slug])) named.push(slug);
  }

  /* Nothing recognisable, or Kamerun's own country is in there: the bar already
     says what it needs to and adding a second sentence would be noise. */
  if (!named.length || covered.indexOf(reach.home) >= 0) return;

  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function listed(parts) {
    if (parts.length === 1) return parts[0];
    return parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1];
  }

  var names = named.map(function (s) {
    return esc((ours[s] || rest[s] || {}).name || rest[s]);
  });

  var say = document.createElement('p');
  say.className = 'fj-from-warn';
  var lead = 'Your journey names ' + listed(names) + '. '
    + esc(ours[reach.home].op) + ' runs ' + esc(ours[reach.home].name)
    + ', so this form is not their desk.';

  if (covered.length) {
    /* One of ours, just not this one — hand them straight over. */
    say.innerHTML = lead + ' ' + covered.map(function (s) {
      return '<a href="' + esc(ours[s].url) + '">' + esc(ours[s].name)
        + ' is run by ' + esc(ours[s].op) + ' &rarr;</a>';
    }).join(' ');
  } else {
    /* None of the three. Say that plainly rather than routing them anywhere:
       the site has already said it does not run a company in the other
       nineteen, and repeating that here is the consistent answer. */
    say.innerHTML = lead
      + ' We do not run a company in ' + listed(names) + ' &mdash; '
      + (named.length > 1 ? 'those countries are' : 'that country is')
      + ' written up here but booked through someone else. Send it anyway and '
      + 'they will say who, or read '
      + listed(named.map(function (s) {
        return '<a href="/portrait/' + esc(s) + '">' + esc((ours[s] || {}).name || rest[s]) + '</a>';
      })) + ' first.';
  }

  bar.appendChild(say);
  bar.setAttribute('data-af-warned', 'true');
}());
