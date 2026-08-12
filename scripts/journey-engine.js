/* The journey engine — the reasoning, with no interface attached to it.
 * ---------------------------------------------------------------------------
 * Pure functions over the dataset: no DOM, no fetch, no clock, no randomness
 * that is not seeded. The same inputs always produce the same journey, which is
 * what makes a shared link a real link and a test a real test. This file runs
 * unchanged in the browser and under Node, and the test suite runs the same
 * code the page runs rather than a Python impression of it.
 *
 * Three rules hold the whole thing up:
 *
 *   1. A signal is scored only if the dataset holds it. What a country calls
 *      itself on, the months it says it is good in, whether one of our own
 *      companies runs it, which region it is in and how much has been written
 *      about the things you asked for — those are recorded. How you like to
 *      travel and who you are travelling with are not, so they are carried to
 *      the operator and never scored. `explain()` therefore never has a line
 *      in it that the data cannot back.
 *
 *   2. Nothing is invented to fill a gap. A country that has no photograph, no
 *      season or no operator of ours is still recommendable; the parts we do
 *      not have simply do not appear.
 *
 *   3. Days are a shape, not a schedule. The engine splits a trip across the
 *      stages a traveller chose; it does not know how long the roads take and
 *      does not pretend to.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AfrinkongJourney = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---- scoring ----------------------------------------------------------- */

  /* A brief is what the traveller has told us:
       { wants: [lensKey], month: 1-12|null, pacing: key, party: key,
         style: [key], region: key|null, seed: int }
     Everything is optional. An empty brief is the "I'm open" path and is a
     legitimate question, not a missing answer. */
  /* "a, b and c" rather than "a and b and c". A recommendation that cannot
     write a list is not going to be believed about anything else. */
  function join(list) {
    if (list.length < 2) return list[0] || '';
    return list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1];
  }

  function rank(data, brief) {
    var w = data.weights;
    var wants = (brief.wants || []).filter(function (k) { return !!data.lenses[k]; });
    var out = [];

    Object.keys(data.countries).forEach(function (slug) {
      var c = data.countries[slug];
      var reasons = [];

      /* What it leads on. A country declares this itself and declares few, so a
         match here is the strongest thing the dataset can say. */
      var hit = wants.filter(function (k) { return c.calls.indexOf(k) >= 0; });
      var lensShare;
      if (!wants.length) {
        lensShare = 0.5;                       /* nothing asked, nothing implied */
      } else if (!hit.length) {
        return;                                /* asked, and this is not it */
      } else {
        lensShare = hit.length / wants.length;
        var titles = hit.map(function (k) { return data.lenses[k].title.toLowerCase(); });
        reasons.push({key: 'lens', text: join(titles),
          say: 'It leads on ' + join(titles)});

        /* And what it does not lead on. A partial match that only lists its
           hits is a partial match pretending to be a whole one; naming the gap
           is the difference between a recommendation and a sales pitch. */
        var missed = wants.filter(function (k) { return hit.indexOf(k) < 0; });
        if (missed.length) {
          var lost = join(missed.map(function (k) {
            return data.lenses[k].title.toLowerCase(); }));
          reasons.push({key: 'gap', text: 'not ' + lost,
            say: 'It does not lead on ' + lost + ' \u2014 worth asking whether '
              + 'that matters to you'});
        }
      }

      /* How much there is to do once you are there, counted in write-ups that
         fall under what you asked for. Depth separates a country that mentions
         mountains from one with six mountain places written up. */
      var depth = 0;
      (wants.length ? wants : Object.keys(data.lenses)).forEach(function (k) {
        depth += (c.lensCounts && c.lensCounts[k]) || 0;
      });
      var depthShare = Math.min(1, depth / w.depthTarget);
      if (wants.length && depth >= 3) {
        reasons.push({key: 'depth', text: depth + ' places',
          say: depth + ' places here are written up under what you asked for'});
      }

      /* The month. A country lists the months it is actually good in; out of
         season is not a disqualification, it is something to be told. */
      var seasonHit = 0.5, outOfSeason = false;
      if (brief.month) {
        if ((c.months || []).indexOf(brief.month) >= 0) {
          seasonHit = 1;
          reasons.push({key: 'season', text: data.months[brief.month - 1],
            say: data.months[brief.month - 1] + ' is one of its good months'});
        } else {
          seasonHit = 0;
          outOfSeason = true;
        }
      }

      /* Ours. Not a quality claim — a claim about who answers the telephone. */
      var ours = c.operator ? 1 : 0;
      if (ours) {
        reasons.push({key: 'operator', text: c.operator.name,
          say: 'Run by ' + c.operator.name + ', based in ' + c.operator.base});
      }

      var regionHit = 0.5;
      if (brief.region) {
        regionHit = c.regionKey === brief.region ? 1 : 0;
        if (regionHit) {
          reasons.push({key: 'region', text: c.region, say: 'In ' + c.region});
        }
      }

      var score = w.lens * lensShare + w.depth * depthShare + w.season * seasonHit
        + w.operator * ours + w.region * regionHit;

      out.push({slug: slug, score: Math.round(score * 10) / 10, reasons: reasons,
                outOfSeason: outOfSeason, depth: depth, matched: hit});
    });

    /* Ties are broken by a seeded rotation rather than by the alphabet, so
       "I'm open" can be asked twice and answered twice without the engine
       becoming random: the seed travels in the link, so a shared journey is
       the same journey. */
    var seed = brief.seed || 0;
    var keys = Object.keys(data.countries).sort();
    out.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      var ai = (keys.indexOf(a.slug) + seed) % keys.length;
      var bi = (keys.indexOf(b.slug) + seed) % keys.length;
      return ai - bi;
    });
    return out;
  }

  /* Three, and from three different regions where the data allows it. A list
     whose top three are neighbours has answered a narrower question than the
     one that was asked. */
  function recommend(data, brief, n) {
    n = n || 3;
    var all = rank(data, brief);
    var picked = [], seenRegion = {};
    all.forEach(function (r) {
      if (picked.length >= n) return;
      var reg = data.countries[r.slug].regionKey;
      if (seenRegion[reg]) return;
      seenRegion[reg] = true;
      picked.push(r);
    });
    all.forEach(function (r) {
      if (picked.length >= n) return;
      if (picked.indexOf(r) < 0) picked.push(r);
    });
    return {picks: picked, considered: all.length};
  }

  /* ---- the journey ------------------------------------------------------- */

  function pacingFor(data, key) {
    var found = data.pacing.filter(function (p) { return p.key === key; })[0];
    return found || data.pacing[data.pacing.length - 1];
  }

  /* Which of a country's places to open with. The dataset already orders them
     the way the country would tell them — whatever it calls itself on comes
     first — so this only has to lift anything the traveller asked for above
     the rest and then take as many as the trip is long enough for. */
  function suggestStages(places, brief, pace) {
    var wants = brief.wants || [];
    var lead = [], rest = [];
    places.forEach(function (p) {
      var hit = (p.lenses || []).some(function (k) { return wants.indexOf(k) >= 0; });
      (hit ? lead : rest).push(p);
    });
    return lead.concat(rest).slice(0, pace.stages).map(function (p) { return p.id; });
  }

  /* Days across stages. The trip's length is the traveller's; how it divides is
     arithmetic. One day to arrive, one to leave, the rest shared out with the
     remainder going to the earlier stages, because the first place is usually
     the one worth the extra night. Nothing here knows how far apart two places
     are, and the page says so rather than implying a schedule. */
  function timeline(stages, days, arrival) {
    if (!stages.length) return [];
    var body = Math.max(stages.length, days - 2);
    var each = Math.floor(body / stages.length);
    var spare = body - each * stages.length;
    var rows = [];
    var day = 1;
    if (days > 2) {
      rows.push({kind: 'arrive', label: arrival || 'Arrival', from: day, to: day});
      day += 1;
    }
    stages.forEach(function (s, i) {
      var span = each + (i < spare ? 1 : 0);
      rows.push({kind: 'stage', stage: s, from: day, to: day + span - 1});
      day += span;
    });
    if (days > 2) rows.push({kind: 'leave', label: 'Departure', from: day, to: day});
    return rows;
  }

  /* ---- the name ---------------------------------------------------------- */

  var STOP = ('the a an and or of in on at to for from with within where what when '
    + 'how why is are was were be been being by into out up down over under above '
    + 'below through again more most less least this that these those it its still '
    + 'then than some other others another every all both few many much such only '
    + 'just even also but if not no nor own same too very your his her their our '
    + 'end side line part place thing hundred thousand dozen million half first '
    + 'last second third next whole entire').split(' ');

  /* Words that classify rather than name. "Mount" on its own is not a place, so
     when one of these wins it takes the name that follows it with it. */
  var CLASSIFIERS = ('mount mt mont lake cape gulf bay port saint st river '
    + 'valley island isles').split(' ');

  /* Titles are set in title case, which capitalises the verb in "Where the Nile
     Begins" and makes it look like a proper noun. These are the forms that turn
     up in a caption; anything ending in -ing is skipped by rule below. */
  var VERBS = ('begins began start starts started ends ended holds held runs ran '
    + 'makes made goes went comes came meets met rises rose falls fell stands '
    + 'stood keeps kept walks walked waits waited leaves left returns returned '
    + 'sits sat lies lay').split(' ');

  /* The strongest word in a place's title: the longest one that is not
     furniture. "Where the Nile Begins" gives NILE; "The Mountains of the Moon"
     gives MOUNTAINS. It is a rule, not a lookup table, so it works on the
     fifty-fifth country's write-ups too. */
  function keyword(title) {
    /* Punctuation matters, so the title is cut on it first: "Dunes, Gorges"
       is two things and a name must not be assembled across the comma. Inside
       a clause the words keep their positions, because a phrase is built back
       out of neighbours. */
    var words = [];
    String(title || '').split(/[^A-Za-zÀ-ɏ' -]+/).forEach(function (clause, ci) {
      clause.split(/[\s-]+/).filter(Boolean).forEach(function (w) {
        var low = w.toLowerCase();
        words.push({w: w, c: ci, i: words.length, cap: /^[A-ZÀ-ſ]/.test(w),
                    stop: STOP.indexOf(low) >= 0 || VERBS.indexOf(low) >= 0,
                    /* "Following" and "Adapted" are verbs wearing title case;
                       "Ring" and "Sand" are not. Seven letters is where the
                       participle rule stops catching ordinary nouns. */
                    verby: w.length >= 7 && /(ing|ed)$/.test(low)});
      });
    });
    var live = words.filter(function (x) { return !x.stop && x.w.length > 2; });
    if (!live.length) return '';

    /* A participle is doing a job in the sentence, not naming the place, so it
       is only used when there is nothing else at all. */
    var solid = live.filter(function (x) { return !x.verby; });
    var pool = solid.length ? solid : live;

    /* A proper noun beats a common one: "Bwindi" says more than
       "impenetrable". */
    var proper = pool.filter(function (x) { return x.cap; });
    if (proper.length) pool = proper;
    var best = pool[0];
    pool.forEach(function (x) { if (x.w.length > best.w.length) best = x; });

    var usable = function (x) {
      return x && x.c === best.c && x.cap && !x.stop && !x.verby && x.w.length > 2;
    };
    /* A classifier takes the name after it — "Mount Nimba", not "Mount" — and
       so does any proper noun with another one beside it: "Black Sand",
       "Queen Elizabeth", "Big Five". Forwards first, because English puts the
       head noun last. */
    var after = words[best.i + 1];
    if (best.cap && usable(after)
        && (CLASSIFIERS.indexOf(best.w.toLowerCase()) >= 0 || after.w.length >= best.w.length
            || CLASSIFIERS.indexOf(after.w.toLowerCase()) < 0)) {
      if (CLASSIFIERS.indexOf(best.w.toLowerCase()) >= 0) return best.w + ' ' + after.w;
    }
    var before = words[best.i - 1];
    if (best.cap && usable(before)) return before.w + ' ' + best.w;
    if (best.cap && usable(after)) return best.w + ' ' + after.w;
    return best.w;
  }

  /* Two stages sit beside each other; three or more is a route, and a route
     goes from somewhere to somewhere. That is the whole rule — it reads as
     authored because it is built out of what the country actually wrote, not
     because a list of adjectives was drawn from a hat. */
  function name(country, stages) {
    if (!stages.length) return country.name.toUpperCase();
    if (stages.length === 1) return stages[0].title.toUpperCase();
    var first = keyword(stages[0].title);
    var last = keyword(stages[stages.length - 1].title);
    if (!first || !last) return country.name.toUpperCase();
    if (first.toLowerCase() === last.toLowerCase()) {
      return (first + ', the long way').toUpperCase();
    }
    return (first + (stages.length > 2 ? ' to ' : ' and ') + last).toUpperCase();
  }

  /* ---- what the journey is made of --------------------------------------- */

  /* Counted, not estimated. Each stage is one of the twenty-six write-ups and
     each write-up belongs to whichever lenses its category belongs to, so this
     is a tally of what was actually chosen. A stage under no lens is counted
     under its own heading rather than rounded into one it does not belong to. */
  function composition(data, stages) {
    var tally = {}, total = 0;
    stages.forEach(function (s) {
      var keys = (s.lenses || []);
      if (!keys.length) keys = ['·' + s.group];
      keys.forEach(function (k) { tally[k] = (tally[k] || 0) + 1 / keys.length; });
      total += 1;
    });
    return Object.keys(tally).map(function (k) {
      return {
        key: k,
        label: k.charAt(0) === '·' ? k.slice(1) : data.lenses[k].title,
        share: total ? tally[k] / total : 0,
        count: Math.round(tally[k] * 100) / 100
      };
    }).sort(function (a, b) { return b.share - a.share || (a.label < b.label ? -1 : 1); });
  }

  /* ---- the link ---------------------------------------------------------- */

  /* A journey is its own address. Everything needed to rebuild it goes in the
     hash — no server, no account, no identifier that means nothing without a
     database behind it. */
  function encode(state) {
    var bits = ['j', state.country || '', (state.stages || []).join('.')];
    var q = [];
    if (state.month) q.push('m=' + state.month);
    if (state.pacing) q.push('d=' + state.pacing);
    if (state.party) q.push('p=' + state.party);
    if ((state.wants || []).length) q.push('w=' + state.wants.join('.'));
    if ((state.style || []).length) q.push('s=' + state.style.join('.'));
    if (state.seed) q.push('r=' + state.seed);
    return '#/' + bits.join('/') + (q.length ? '?' + q.join('&') : '');
  }

  function decode(hash) {
    var raw = String(hash || '').replace(/^#\/?/, '');
    var half = raw.split('?');
    var path = half[0].split('/').filter(function (x) { return x !== ''; });
    var q = {};
    (half[1] || '').split('&').forEach(function (kv) {
      var i = kv.indexOf('=');
      if (i > 0) q[kv.slice(0, i)] = kv.slice(i + 1);
    });
    var num = function (v, lo, hi) {
      var n = parseInt(v, 10);
      return (!isNaN(n) && n >= lo && n <= hi) ? n : null;
    };
    var list = function (v) { return v ? v.split('.').filter(Boolean) : []; };
    return {
      country: path[0] === 'j' ? (path[1] || null) : null,
      stages: path[0] === 'j' ? list(path[2]) : [],
      month: num(q.m, 1, 12),
      pacing: q.d || null,
      party: q.p || null,
      wants: list(q.w),
      style: list(q.s),
      seed: num(q.r, 0, 999) || 0
    };
  }

  return {
    rank: rank, recommend: recommend, pacingFor: pacingFor,
    suggestStages: suggestStages, timeline: timeline,
    keyword: keyword, name: name, composition: composition,
    encode: encode, decode: decode
  };
});
