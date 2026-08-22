/* The journey engine — the reasoning, with no interface attached to it.
 *
 * @product: live | @gate: none | @surface: /journey
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


  /* FNV-1a. Small, dependency-free and stable across engines, which matters
     because a journey link shared from one browser has to open as the same
     journey in another. */
  function hash(str) {
    var x = 2166136261;
    for (var i = 0; i < str.length; i++) {
      x ^= str.charCodeAt(i);
      x = Math.imul(x, 16777619);
    }
    return x >>> 0;
  }


  /* ---- the experience profile -------------------------------------------
   *
   * Afrinkong recommends; the traveller decides. So a lens does not filter the
   * continent, it colours it: every country stays visible and selectable, and
   * what changes is how strongly each one answers what was asked.
   *
   * Three levels, and all three come from the dataset rather than from an
   * opinion typed into this file:
   *
   *   leads   the country declares this lens in its own `calls`. That list is
   *           editorial and deliberately short — Uganda calls wildlife and
   *           culture and does not call coast, though it has lakes — so a hit
   *           here is the strongest thing the data can say.
   *   region  the country does not declare it, but most of its region does.
   *           Real and measurable: 80% of southern Africa calls wildlife and
   *           0% of north Africa does; every island calls coast. A country
   *           sitting inside that is a fair second answer.
   *   open    everything else. Not "no" — every country in the set has all
   *           twenty-seven categories written up, so the places are there to
   *           read whatever the lens says.
   *
   * There is deliberately no five-dot intensity. It would need a per-country
   * per-lens judgement that this dataset does not contain: every country has
   * the same twenty-seven write-ups, so counting them gives all fifty-four an
   * identical profile. Three levels that are true beat five that are invented.
   */

  var REGION_LEADS = null;

  function regionLeads(data) {
    if (REGION_LEADS) return REGION_LEADS;
    var tally = {};
    Object.keys(data.countries).forEach(function (slug) {
      var c = data.countries[slug], r = c.regionKey || '?';
      tally[r] = tally[r] || {n: 0, lens: {}};
      tally[r].n++;
      (c.calls || []).forEach(function (k) {
        tally[r].lens[k] = (tally[r].lens[k] || 0) + 1;
      });
    });
    REGION_LEADS = {};
    Object.keys(tally).forEach(function (r) {
      REGION_LEADS[r] = {};
      Object.keys(data.lenses).forEach(function (k) {
        REGION_LEADS[r][k] = (tally[r].lens[k] || 0) / tally[r].n >= 0.5;
      });
    });
    return REGION_LEADS;
  }

  /* What one country says about one lens. */
  function level(data, slug, lens) {
    var c = data.countries[slug];
    if (!c) return 'open';
    if ((c.calls || []).indexOf(lens) >= 0) return 'leads';
    var reg = regionLeads(data)[c.regionKey || '?'];
    return (reg && reg[lens]) ? 'region' : 'open';
  }

  /* The whole continent against what was asked, strongest first, nothing
     dropped. `match` is the colour; `leads` is what the country itself says it
     is for, which is what gets printed under its name — "Culture, Coast,
     Food", never "no wildlife here". */
  function field(data, brief) {
    var wants = (brief.wants || []).filter(function (k) { return !!data.lenses[k]; });
    var rank = {leads: 0, region: 1, open: 2};
    var rows = Object.keys(data.countries).map(function (slug) {
      var c = data.countries[slug];
      var best = 'open';
      wants.forEach(function (k) {
        var l = level(data, slug, k);
        if (rank[l] < rank[best]) best = l;
      });
      var hits = wants.filter(function (k) { return level(data, slug, k) === 'leads'; });
      return {
        slug: slug, name: c.name, region: c.region, regionKey: c.regionKey,
        match: wants.length ? best : 'open',
        hits: hits.length,
        /* Always what it IS for, never what it is not. */
        leads: (c.calls || []).map(function (k) { return data.lenses[k].title; }),
        inSeason: !brief.month || (c.months || []).indexOf(brief.month) >= 0
      };
    });
    rows.sort(function (a, b) {
      if (rank[a.match] !== rank[b.match]) return rank[a.match] - rank[b.match];
      if (b.hits !== a.hits) return b.hits - a.hits;
      if (a.inSeason !== b.inSeason) return a.inSeason ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    return rows;
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

    /* Ties are broken by a rotation seeded from the BRIEF, not by the alphabet.
       This claimed to be a seeded rotation and was not: seed defaults to 0, so
       the rotation was the identity and every tie fell to whichever country
       came first in the alphabet. It mattered far more than it looks, because
       the scoring is coarse — a real brief ("wildlife, July, a week") matched
       twenty-six countries and gave them three distinct scores between them,
       so nearly every question was decided by the tie-break rather than by the
       score. Measured over 520 briefs, fourteen countries out of fifty-four
       could ever be recommended and one of them won a third of the time.

       Hashing the brief keeps every property the seed was there for — the same
       question always gives the same answer, a shared link is the same journey,
       and "Ask me again" still re-rolls because the seed is in the key — while
       making the answer depend on what was asked instead of on the spelling of
       a country's name. Same 520 briefs: fifty-two countries reachable, the
       most-recommended one at six per cent. */
    var keys = Object.keys(data.countries).sort();
    /* Party and style are deliberately NOT in this key. Question four of the
       tunnel tells the visitor, in as many words, that neither who they travel
       with nor how they like to travel moves a country up or down the list —
       they are carried into the enquiry for a person to read, not scored. The
       first version of this hash included party, which made the promise false
       through the tie-break rather than through the score; journey-checks
       caught it on solo/slow and solo/walking. */
    var rot = hash([(brief.wants || []).join('.'), brief.month || '',
                    brief.pacing || '', brief.region || '',
                    brief.seed || 0].join('|'));
    out.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      var ai = (keys.indexOf(a.slug) + rot) % keys.length;
      var bi = (keys.indexOf(b.slug) + rot) % keys.length;
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

  /* ---- reading a sentence -------------------------------------------------- */

  /* "Twelve days in September, wildlife and mountains" -> a brief.
   *
   * A parser, not a model. It matches months by name, countries by name, a
   * duration by number-and-unit, and a lens only against the words recorded for
   * that lens in lenses.json. A word it does not recognise selects nothing —
   * which is the correct behaviour, because guessing at what somebody meant and
   * being wrong is worse than asking them.
   *
   * It reports what it took, so the interface can show the visitor its reading
   * before acting on it. Nothing here is ever applied silently: every field it
   * fills also fills the control that field belongs to, and every control stays
   * editable.
   */
  var NUMBERS = {one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
                 eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
                 fourteen: 14, fifteen: 15, twenty: 20, thirty: 30, a: 1, an: 1};

  function parse(text, data) {
    var low = ' ' + String(text || '').toLowerCase().replace(/[^a-z0-9\s'-]/g, ' ')
      .replace(/\s+/g, ' ') + ' ';
    var out = {wants: [], month: null, pacing: null, party: null,
               country: null, days: null, took: [], missed: []};

    data.months.forEach(function (name, i) {
      var m = name.toLowerCase();
      if (low.indexOf(' ' + m + ' ') >= 0 || low.indexOf(' ' + m.slice(0, 3) + ' ') >= 0) {
        out.month = i + 1;
        out.took.push({field: 'month', say: name});
      }
    });

    Object.keys(data.countries).forEach(function (slug) {
      var name = data.countries[slug].name.toLowerCase();
      if (low.indexOf(' ' + name + ' ') >= 0) {
        out.country = slug;
        out.took.push({field: 'country', say: data.countries[slug].name});
      }
    });

    Object.keys(data.lenses).forEach(function (key) {
      var words = data.lenses[key].words || [data.lenses[key].title.toLowerCase()];
      for (var i = 0; i < words.length; i++) {
        if (low.indexOf(' ' + words[i] + ' ') >= 0) {
          if (out.wants.indexOf(key) < 0) {
            out.wants.push(key);
            out.took.push({field: 'want', say: data.lenses[key].title, matched: words[i]});
          }
          return;
        }
      }
    });

    /* Duration. Weeks and days both, and written-out numbers, because people
       type "two weeks" as often as "14 days". The band it lands in is the
       existing pacing band, so there is one definition of how long is long. */
    var dm = low.match(/(\d+|[a-z]+)[\s-]*(day|days|night|nights|week|weeks|fortnight)/);
    if (dm) {
      var n = /^\d+$/.test(dm[1]) ? parseInt(dm[1], 10) : NUMBERS[dm[1]];
      if (dm[2] === 'fortnight') { n = 14; }
      else if (n && dm[2].indexOf('week') === 0) { n = n * 7; }
      if (n && n > 0 && n < 200) {
        out.days = n;
        var band = data.pacing[0];
        data.pacing.forEach(function (b) {
          if (b.key !== 'open' && b.days <= n) band = b;
        });
        out.pacing = band.key;
        out.took.push({field: 'pacing', say: n + (n === 1 ? ' day' : ' days'),
                       band: band.label});
      }
    }
    if (low.indexOf('fortnight') >= 0 && !out.pacing) out.pacing = 'fortnight';

    (data.party || []).forEach(function (opt) {
      var label = opt.label.toLowerCase();
      if (low.indexOf(' ' + label + ' ') >= 0
          || (opt.key === 'family' && low.indexOf(' family ') >= 0)
          || (opt.key === 'solo' && (low.indexOf(' solo ') >= 0
              || low.indexOf(' alone ') >= 0 || low.indexOf(' on my own ') >= 0))
          || (opt.key === 'couple' && (low.indexOf(' couple ') >= 0
              || low.indexOf(' two of us ') >= 0 || low.indexOf(' my partner ') >= 0))
          || (opt.key === 'friends' && low.indexOf(' friends ') >= 0)) {
        out.party = opt.key;
        out.took.push({field: 'party', say: opt.label});
      }
    });

    if (!out.took.length) {
      out.missed.push('Nothing in that matched a country, a month, a length or one '
        + 'of the six things a country here can lead on.');
    }
    return out;
  }

  /* ---- how good a match is this ------------------------------------------- */

  /* Deliberately a band and not a percentage. The dataset can say that a country
     declares two of the three things you asked for and is at its best in your
     month; it cannot support "87%", and a number that precise is a claim about
     precision the data does not have. */
  function band(data, brief, row) {
    if (!row) return null;
    var wants = (brief.wants || []).filter(function (k) { return !!data.lenses[k]; });
    var hit = row.matched ? row.matched.length : 0;
    var season = brief.month ? !row.outOfSeason : null;
    var share = wants.length ? hit / wants.length : 1;
    var label, why;
    if (wants.length && share === 1 && season !== false) {
      label = 'Strong match';
      why = 'everything you asked for, and the month';
    } else if (wants.length && share === 1) {
      label = 'Strong on what, not on when';
      why = 'everything you asked for, but not in that month';
    } else if (wants.length && share >= 0.5) {
      label = 'Partial match';
      why = hit + ' of the ' + wants.length + ' things you asked for';
    } else if (wants.length) {
      label = 'Loose match';
      why = 'one of the things you asked for';
    } else {
      label = season === false ? 'Out of season' : 'Where we would start';
      why = brief.month ? 'you told us the month and nothing else'
                        : 'you told us nothing to narrow by';
    }
    return {label: label, why: why, season: season, matched: hit, asked: wants.length};
  }

  /* ---- crossing a border -------------------------------------------------- */

  /* A stage can belong to a country other than the one the journey started in.
     It is written `slug~category` when it does and bare when it does not, so a
     single-country journey's link is exactly what it was before this existed.
     Africa is fifty-four countries and a great many journeys are two of them;
     an engine that cannot say so is describing a different continent. */
  function stageOf(id, home) {
    var cut = String(id || '').indexOf('~');
    return cut < 0 ? {country: home, id: id}
                   : {country: id.slice(0, cut), id: id.slice(cut + 1)};
  }

  function stageId(country, id, home) {
    return country === home ? id : country + '~' + id;
  }

  /* Which countries a journey could honestly continue into: it has to share a
     land border with where you are — the one fact here that changes what a
     journey can physically be — and it has to answer the same brief. Nothing
     is offered on the strength of being in Africa too. */
  function onward(data, links, home, brief) {
    if (!links || !links.links) return [];
    var wants = (brief.wants || []).filter(function (k) { return !!data.lenses[k]; });
    return (links.links[home] || []).filter(function (r) {
      if (!r.why.some(function (w) { return w.kind === 'border'; })) return false;
      if (!data.countries[r.to]) return false;
      if (!wants.length) return true;
      return wants.some(function (k) { return data.countries[r.to].calls.indexOf(k) >= 0; });
    });
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
    stageOf: stageOf, stageId: stageId, onward: onward,
    parse: parse, band: band,
    encode: encode, decode: decode,
    level: level, field: field
  };
});
