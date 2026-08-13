/* Search over the story graph. No index server, no fuzzy matching, no model.
 * ---------------------------------------------------------------------------
 * "food in Cameroon", "heritage in Ethiopia", "Kampala", "mountains".
 *
 * The whole of this file is a reader of three vocabularies the build already
 * wrote down: the countries, the themes (lenses, strands and the twenty-seven
 * categories, in one list), and the five hundred and eighty-one proper names
 * that were read out of the dataset's own sentences. A query is matched against
 * those and nothing else.
 *
 * That is a deliberate ceiling. A search that guesses is a search that can
 * answer a question about a country this site has never written about, and the
 * one rule the whole project runs on is that it may not do that. So a word this
 * dataset has never used matches nothing, and the interface says so in those
 * words rather than showing a near-miss and letting the visitor assume.
 *
 * Kept separate from stories.js — which is DOM wiring — so the matching can be
 * run under Node against the real data files and asserted on. The interesting
 * assertions are the negative ones: that an unknown word finds nothing, and
 * that no result is ever for a country the query did not lead to.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongSearch = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* Words that carry no query: dropping them is what lets "food in Cameroon"
     and "the food of Cameroon" reach the same place. */
  var NOISE = {'in': 1, 'of': 1, 'the': 1, 'a': 1, 'an': 1, 'at': 1, 'on': 1,
    'for': 1, 'to': 1, 'and': 1, 'or': 1, 'about': 1, 'from': 1, 'with': 1,
    'me': 1, 'i': 1, 'want': 1, 'show': 1, 'find': 1, 'what': 1, 'is': 1,
    'are': 1, 'where': 1, 'there': 1, 'best': 1, 'good': 1};

  function words(text) {
    return String(text || '').toLowerCase()
      .replace(/[^a-z0-9\s'-]/g, ' ')
      .split(/\s+/).filter(function (w) { return w && !NOISE[w]; });
  }

  function has(list, word) {
    for (var i = 0; i < list.length; i++) if (list[i] === word) return true;
    return false;
  }

  /* -> {country, theme, name, took[], missed[]} — never a guess.
     `missed` is the honest half: the words it recognised nothing for, so the
     interface can name them instead of quietly returning the results for the
     half it did understand. */
  function parse(query, graph) {
    var raw = String(query || '').toLowerCase().trim();
    var out = {country: null, theme: null, name: null, took: [], missed: []};
    if (!raw || !graph) return out;
    var terms = words(raw);
    if (!terms.length) return out;

    /* Names first, and longest first, because a name may be several words and
       may contain a theme word — "Victoria Falls" must not be read as the
       theme "falls" plus a leftover. */
    var names = Object.keys(graph.names || {});
    names.sort(function (a, b) { return b.length - a.length; });
    for (var n = 0; n < names.length; n++) {
      var low = names[n].toLowerCase();
      if (low.length < 4) continue;
      if (raw.indexOf(low) >= 0) {
        out.name = names[n];
        break;
      }
    }

    var countries = graph.countries || {};
    Object.keys(countries).forEach(function (slug) {
      if (out.country) return;
      var c = countries[slug];
      var forms = [String(c.name || '').toLowerCase(),
                   String(c.adjective || '').toLowerCase(),
                   slug.replace(/-/g, ' ')];
      for (var i = 0; i < forms.length; i++) {
        if (forms[i] && raw.indexOf(forms[i]) >= 0) { out.country = slug; return; }
      }
    });

    var themes = graph.themes || {};
    var best = null;
    Object.keys(themes).forEach(function (key) {
      var t = themes[key];
      var vocab = (t.words || []).concat([key]);
      for (var i = 0; i < vocab.length; i++) {
        var word = String(vocab[i]).toLowerCase();
        var hit = word.indexOf(' ') >= 0
          ? raw.indexOf(word) >= 0 : has(terms, word);
        if (!hit) continue;
        /* A theme named by more categories is a broader answer; prefer the
           narrower one when two match, so "food" beats the category list that
           merely contains food. */
        var size = (t.categories || []).length || 99;
        if (!best || size < best.size) best = {key: key, size: size, word: word};
      }
    });
    if (best) out.theme = best.key;

    terms.forEach(function (word) {
      var used = false;
      if (out.country && (String((countries[out.country] || {}).name || '')
          .toLowerCase().indexOf(word) >= 0
          || String((countries[out.country] || {}).adjective || '')
          .toLowerCase().indexOf(word) >= 0)) used = true;
      if (out.theme && String(out.theme + ' ' + ((themes[out.theme] || {}).words || [])
          .join(' ') + ' ' + ((themes[out.theme] || {}).title || '')).toLowerCase()
          .indexOf(word) >= 0) used = true;
      if (out.name && out.name.toLowerCase().indexOf(word) >= 0) used = true;
      (used ? out.took : out.missed).push(word);
    });
    return out;
  }

  function address(graph, slug, category) {
    var c = (graph.countries || {})[slug] || {};
    var row = (c.places || {})[category];
    if (!row || !row.u) return null;
    return {kind: 'place', country: slug, countryName: c.name, category: category,
            title: row.t, url: row.u};
  }

  /* -> {read: [], hits: [], said: ''} — what was understood, and what it found. */
  function search(query, graph, stories) {
    var read = parse(query, graph);
    var out = {read: read, hits: []};
    if (!graph) return out;
    var themes = graph.themes || {};
    var cats = read.theme ? ((themes[read.theme] || {}).categories || []) : [];
    var seen = {};

    function push(hit) {
      if (!hit) return;
      var id = hit.kind + ':' + (hit.url || hit.id);
      if (seen[id]) return;
      seen[id] = true;
      out.hits.push(hit);
    }

    /* A name is the most specific thing a query can contain, so it answers
       first: every write-up in the dataset that says this word. */
    var within = null;
    if (read.name) {
      var row = (graph.names || {})[read.name] || {};
      (row.at || []).forEach(function (at) {
        if (read.country && at.c !== read.country) return;
        push(address(graph, at.c, at.e));
      });
      /* And it narrows everything after it. "History of Buea" is a question
         about Buea; answering it with the heritage of twenty-two countries
         because one of the two words was a theme would be answering a question
         nobody asked. */
      within = read.country ? [read.country] : (row.in || []);
    }

    (stories || []).forEach(function (s) {
      if (read.country && s.country !== read.country) return;
      if (within && !has(within, s.country)) return;
      if (cats.length) {
        var touches = false;
        for (var i = 0; i < (s.chapters || []).length; i++) {
          if (has(cats, s.chapters[i])) { touches = true; break; }
        }
        if (!touches && !has(s.lenses || [], read.theme)) return;
      } else if (!read.country) {
        return;    /* nothing asked for, or a bare name: the write-ups answer */
      }
      push({kind: 'story', id: s.id, country: s.country, countryName: s.countryName,
            title: s.title, text: s.text, url: s.url, arcTitle: s.arcTitle,
            format: s.format});
    });

    /* A country on its own is answered by its portrait, at the end, as the
       thing to read rather than the thing to skim. */
    if (read.country && (graph.countries || {})[read.country]) {
      push({kind: 'portrait', country: read.country,
            countryName: graph.countries[read.country].name,
            title: graph.countries[read.country].name + ': a portrait',
            text: graph.countries[read.country].tagline,
            url: '/portrait/' + read.country});
    }
    return out;
  }

  /* What the search understood, in words, for the status line. It names what it
     did not understand too — a search that silently drops half a query is a
     search that answers a question nobody asked. */
  function said(result, graph) {
    var read = result.read;
    var themes = (graph || {}).themes || {};
    var countries = (graph || {}).countries || {};
    if (!read.theme && !read.country && !read.name) {
      return read.missed.length
        ? 'Nothing here is written about "' + read.missed.join(' ')
          + '". Nothing was guessed.'
        : '';
    }
    var bits = [];
    if (read.theme) bits.push((themes[read.theme] || {}).title || read.theme);
    if (read.name) bits.push(read.name);
    var where = read.country
      ? ((countries[read.country] || {}).name || read.country) : '';
    if (where) bits.push(bits.length ? 'in ' + where : where);
    var line = bits.join(', ') + ' — ' + result.hits.length
      + (result.hits.length === 1 ? ' result' : ' results');
    if (read.missed.length) {
      line += '. Nothing matched "' + read.missed.join(' ') + '".';
    }
    return line;
  }

  /* Which countries are written up as good in a given month. Derived, not
     scheduled: there is no calendar behind this and no event has a date. */
  function monthly(month, graph) {
    var countries = (graph || {}).countries || {};
    return Object.keys(countries).filter(function (slug) {
      var months = countries[slug].months || [];
      return months.indexOf(month) >= 0;
    }).sort(function (a, b) {
      return String(countries[a].name).localeCompare(String(countries[b].name));
    });
  }

  return {parse: parse, search: search, said: said, monthly: monthly,
          words: words};
});
