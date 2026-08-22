# The system map

**GENERATED. Do not edit.** `python3 tools/system-map.py > docs/system-map.md`

Every figure here is measured at the moment of generation. A hand-written
map of a system this size is correct on the day it is written and quietly
wrong afterwards — and trusted anyway, because it looks authoritative.

## Pages

| family | pages |
|---|---|
| `place` | 1404 |
| `tourism` | 55 |
| `portrait` | 54 |
| `country` | 52 |
| `crossing` | 10 |
| `index` | 7 |
| `trust` | 6 |
| `operator` | 5 |
| `fund` | 4 |
| `atlas` | 1 |
| `home` | 1 |
| `journey` | 1 |
| **total** | **1600** |

1599 pages declare their own family in the body class `af--<family>`; 1
are classified only by where they sit on disk.
A page that can answer *what am I* only by its path is a page the
information architecture does not yet own.

## Modules, and how many pages load each

**A module loaded by zero pages is orphaned product code.** It may still
be infrastructure — required by another module, or by a check — so the
second column separates *nothing loads it in a browser* from *nothing
references it at all*.

| module | pages | referenced by |
|---|---|---|
| `account.js` | 0 | 2 |
| `atlas.js` | 1 | 1 |
| `booking.js` | 0 | 9 |
| `buyback.js` | 0 | 8 |
| `crossings.js` | 10 | 0 |
| `enquiry.js` | 5 | 0 |
| `entities.js` | 0 | 12 |
| `events.js` | 1484 | 13 |
| `explore.js` | 1600 | 6 |
| `fund-math.js` | 1 | 9 |
| `fund.js` | 1 | 10 |
| `journey-catalogue.js` | 0 | 3 |
| `journey-engine.js` | 1 | 4 |
| `journey.js` | 1 | 3 |
| `meet.js` | 1 | 5 |
| `points-ledger.js` | 1 | 33 |
| `portrait.js` | 54 | 1 |
| `purchase-plan.js` | 0 | 6 |
| `risk.js` | 0 | 9 |
| `state-language.js` | 1 | 9 |
| `stories.js` | 1 | 11 |
| `story-search.js` | 1522 | 5 |
| `table.js` | 1 | 1 |
| `transfer.js` | 0 | 0 |
| `travel-goal.js` | 1 | 18 |
| `window.js` | 2 | 3 |

**Orphaned in the browser: 8 module(s)** — `account.js`, `booking.js`, `buyback.js`, `entities.js`, `journey-catalogue.js`, `purchase-plan.js`, `risk.js`, `transfer.js`.

## Stylesheets, and how many pages load each

| stylesheet | pages | generated |
|---|---|---|
| `afrinkong.css` | 1599 | no |
| `atlas.css` | 1 | no |
| `country.css` | 52 | yes |
| `fund.css` | 4 | no |
| `gateway.css` | 1 | no |
| `howitworks.css` | 1 | no |
| `journey.css` | 18 | no |
| `kamerun.css` | 3 | no |
| `meet.css` | 1 | no |
| `places.css` | 1461 | no |
| `states.css` | 1 | no |
| `story.css` | 56 | no |
| `tokens.css` | 0 | no |
| `tourism.css` | 56 | yes |
| `transafrique.css` | 10 | no |
| `trust.css` | 4 | no |
| `wonders.css` | 1 | no |

## Datasets, and who reads them

One authoritative source per important fact is the rule. A dataset read
by nothing is dead; a dataset read by many is load-bearing and must not
be edited casually.

| dataset | readers | records |
|---|---|---|
| `data/asset-inventory.json` | 2 | 5 |
| `data/atlas/algeria.json` | 0 | 3 |
| `data/atlas/angola.json` | 0 | 3 |
| `data/atlas/benin.json` | 0 | 3 |
| `data/atlas/botswana.json` | 0 | 3 |
| `data/atlas/burkina-faso.json` | 0 | 3 |
| `data/atlas/burundi.json` | 0 | 3 |
| `data/atlas/cabo-verde.json` | 0 | 3 |
| `data/atlas/cameroon.json` | 0 | 3 |
| `data/atlas/central-african-republic.json` | 0 | 3 |
| `data/atlas/chad.json` | 0 | 3 |
| `data/atlas/comoros.json` | 0 | 3 |
| `data/atlas/congo.json` | 0 | 3 |
| `data/atlas/cote-divoire.json` | 0 | 3 |
| `data/atlas/djibouti.json` | 0 | 3 |
| `data/atlas/dr-congo.json` | 0 | 3 |
| `data/atlas/egypt.json` | 0 | 3 |
| `data/atlas/equatorial-guinea.json` | 0 | 3 |
| `data/atlas/eritrea.json` | 0 | 3 |
| `data/atlas/eswatini.json` | 0 | 3 |
| `data/atlas/ethiopia.json` | 0 | 3 |
| `data/atlas/gabon.json` | 0 | 3 |
| `data/atlas/gambia.json` | 0 | 3 |
| `data/atlas/ghana.json` | 0 | 3 |
| `data/atlas/guinea-bissau.json` | 0 | 3 |
| `data/atlas/guinea.json` | 0 | 3 |
| `data/atlas/kenya.json` | 0 | 3 |
| `data/atlas/lesotho.json` | 0 | 3 |
| `data/atlas/liberia.json` | 0 | 3 |
| `data/atlas/libya.json` | 0 | 3 |
| `data/atlas/madagascar.json` | 0 | 3 |
| `data/atlas/malawi.json` | 0 | 3 |
| `data/atlas/mali.json` | 0 | 3 |
| `data/atlas/mauritania.json` | 0 | 3 |
| `data/atlas/mauritius.json` | 0 | 3 |
| `data/atlas/morocco.json` | 0 | 3 |
| `data/atlas/mozambique.json` | 0 | 3 |
| `data/atlas/namibia.json` | 0 | 3 |
| `data/atlas/niger.json` | 0 | 3 |
| `data/atlas/nigeria.json` | 0 | 3 |
| `data/atlas/rwanda.json` | 0 | 3 |
| `data/atlas/sao-tome-and-principe.json` | 0 | 3 |
| `data/atlas/senegal.json` | 0 | 3 |
| `data/atlas/seychelles.json` | 0 | 3 |
| `data/atlas/sierra-leone.json` | 0 | 3 |
| `data/atlas/somalia.json` | 0 | 3 |
| `data/atlas/south-africa.json` | 0 | 3 |
| `data/atlas/south-sudan.json` | 0 | 3 |
| `data/atlas/sudan.json` | 0 | 3 |
| `data/atlas/tanzania.json` | 0 | 3 |
| `data/atlas/togo.json` | 0 | 3 |
| `data/atlas/tunisia.json` | 0 | 3 |
| `data/atlas/uganda.json` | 0 | 3 |
| `data/atlas/zambia.json` | 0 | 3 |
| `data/atlas/zimbabwe.json` | 0 | 3 |
| `data/focal-cache.json` | 1 | 151 |
| `data/graph.json` | 3 | 3 |
| `data/journey-requirements.json` | 2 | 4 |
| `data/links.json` | 3 | 4 |
| `data/meet.json` | 3 | 3 |
| `data/sizes.json` | 2 | 4 |
| `data/stories.json` | 3 | 3 |
| `data/table.json` | 2 | 4 |
| `tourism/arcs.json` | 1 | 4 |
| `tourism/assets.json` | 2 | 5 |
| `tourism/atlas-detail.json` | 2 | 10 |
| `tourism/cache/images.json` | 2 | 4 |
| `tourism/candidates/index.json` | 2 | 3 |
| `tourism/categories.json` | 2 | 4 |
| `tourism/cities.json` | 2 | 4 |
| `tourism/company.json` | 2 | 13 |
| `tourism/countries/algeria.json` | 0 | 11 |
| `tourism/countries/angola.json` | 0 | 11 |
| `tourism/countries/benin.json` | 0 | 11 |
| `tourism/countries/botswana.json` | 0 | 11 |
| `tourism/countries/burkina-faso.json` | 0 | 11 |
| `tourism/countries/burundi.json` | 0 | 11 |
| `tourism/countries/cabo-verde.json` | 0 | 11 |
| `tourism/countries/cameroon.json` | 0 | 15 |
| `tourism/countries/central-african-republic.json` | 0 | 11 |
| `tourism/countries/chad.json` | 0 | 11 |
| `tourism/countries/comoros.json` | 0 | 11 |
| `tourism/countries/congo.json` | 0 | 11 |
| `tourism/countries/cote-divoire.json` | 0 | 11 |
| `tourism/countries/djibouti.json` | 0 | 11 |
| `tourism/countries/dr-congo.json` | 0 | 11 |
| `tourism/countries/egypt.json` | 0 | 11 |
| `tourism/countries/equatorial-guinea.json` | 0 | 11 |
| `tourism/countries/eritrea.json` | 0 | 11 |
| `tourism/countries/eswatini.json` | 0 | 11 |
| `tourism/countries/ethiopia.json` | 0 | 11 |
| `tourism/countries/gabon.json` | 0 | 11 |
| `tourism/countries/gambia.json` | 0 | 11 |
| `tourism/countries/ghana.json` | 0 | 11 |
| `tourism/countries/guinea-bissau.json` | 0 | 11 |
| `tourism/countries/guinea.json` | 0 | 11 |
| `tourism/countries/kenya.json` | 0 | 13 |
| `tourism/countries/lesotho.json` | 0 | 11 |
| `tourism/countries/liberia.json` | 0 | 11 |
| `tourism/countries/libya.json` | 0 | 11 |
| `tourism/countries/madagascar.json` | 0 | 11 |
| `tourism/countries/malawi.json` | 0 | 11 |
| `tourism/countries/mali.json` | 0 | 11 |
| `tourism/countries/mauritania.json` | 0 | 11 |
| `tourism/countries/mauritius.json` | 0 | 11 |
| `tourism/countries/morocco.json` | 0 | 11 |
| `tourism/countries/mozambique.json` | 0 | 11 |
| `tourism/countries/namibia.json` | 0 | 13 |
| `tourism/countries/niger.json` | 0 | 11 |
| `tourism/countries/nigeria.json` | 0 | 11 |
| `tourism/countries/rwanda.json` | 0 | 11 |
| `tourism/countries/sao-tome-and-principe.json` | 0 | 11 |
| `tourism/countries/senegal.json` | 0 | 11 |
| `tourism/countries/seychelles.json` | 0 | 11 |
| `tourism/countries/sierra-leone.json` | 0 | 11 |
| `tourism/countries/somalia.json` | 0 | 11 |
| `tourism/countries/south-africa.json` | 0 | 11 |
| `tourism/countries/south-sudan.json` | 0 | 11 |
| `tourism/countries/sudan.json` | 0 | 11 |
| `tourism/countries/tanzania.json` | 0 | 13 |
| `tourism/countries/togo.json` | 0 | 11 |
| `tourism/countries/tunisia.json` | 0 | 11 |
| `tourism/countries/uganda.json` | 0 | 15 |
| `tourism/countries/zambia.json` | 0 | 13 |
| `tourism/countries/zimbabwe.json` | 0 | 11 |
| `tourism/events.json` | 2 | 3 |
| `tourism/journeys.json` | 1 | 6 |
| `tourism/lenses.json` | 2 | 10 |
| `tourism/map.json` | 2 | 4 |
| `tourism/moments.json` | 1 | 3 |
| `tourism/motion.json` | 2 | 3 |
| `tourism/neighbours.json` | 2 | 3 |
| `tourism/operators.json` | 2 | 3 |
| `tourism/people.json` | 1 | 3 |
| `tourism/picks.json` | 2 | 8 |
| `tourism/rates.json` | 3 | 18 |
| `tourism/regions.json` | 2 | 7 |
| `tourism/respect.json` | 1 | 4 |
| `tourism/scale.json` | 1 | 3 |
| `tourism/shapes.json` | 3 | 54 |
| `tourism/strands.json` | 1 | 9 |
| `tourism/style.json` | 1 | 10 |
| `tourism/transafrique.json` | 2 | 44 |
| `tourism/views.json` | 2 | 2 |
| `tourism/voices.json` | 2 | 3 |
| `tourism/wonders.json` | 2 | 16 |

## The navigation architecture

Four areas, each with a gate. `None` means open; anything else names the
condition holding it shut, in the same vocabulary `tools/product-map.py`
uses for the modules behind it. `plate.shell()` renders only the open
ones, so a held area appears on no page — in no menu, on no phone
drawer, in no footer — until its gate is set to `None`.

| area | gate | children |
|---|---|---|
| **Explore** | open | Destinations, Countries, The Atlas, Stories, Meet Africa, Trans Afrique |
| **Plan** | open | Journey Planner, Journey Fund, Travel Goal |
| **Fund** | `programme-compliance` | Travel Points, Travel Wallet, Travel Goals, Point activity |
| **Travel** | `booking-not-built` | My Journeys, Bookings, Itinerary, Travel Documents, Travel Support |

That is the difference between a promise deferred and a promise
omitted: the shape of the product is written down in one place, and the
navigation still offers nothing it cannot honour.

## Generators

`build.py` exposes **58 commands**. Every page on this site is generated;
nothing here is written by hand and left alone.

```
acquire  adopt  all  assets  atlas  audit  bound  company  compare
cut  enquire  enquiry  entities  film  focal  footage  fund  gateway
generate  geo  grade  graft  graph  heroes  homes  intake  journey
library  links  meet  modern  optimise  place  placements  places
points  prompts  providers  queries  render  report  resolve
scaffold  sidebyside  sizeattr  sizes  srcset  status  story  test
trails  transafrique  trust  twoways  validate  verify  wonders
wondershots
```

**Late passes edit built HTML, and any regeneration wipes them.** The
chain is `library rewrite` → `bound` → `srcset` → `sizeattr` → `modern`,
behind `company` and `graft`. A single generator run does not execute it.

## Gates

| suite | lines |
|---|---|
| `tools/browser-checks.js` | 1567 |
| `tools/content-checks.js` | 148 |
| `tools/design-checks.js` | 525 |
| `tools/entity-checks.js` | 334 |
| `tools/fund-checks.js` | 542 |
| `tools/goal-checks.js` | 393 |
| `tools/idempotence-checks.js` | 142 |
| `tools/journey-checks.js` | 838 |
| `tools/library-checks.js` | 591 |
| `tools/link-checks.js` | 296 |
| `tools/points-checks.js` | 3995 |
| `tools/shell-checks.js` | 395 |
| `tools/state-checks.js` | 457 |
| `tools/tourism/tests.py` (the suite CI runs) | 3799 |
| **total** | **14022** |

## Documentation

42 documents, 10255 lines.

## The ratio

| | |
|---|---|
| product and economic JavaScript | 10953 lines |
| gates | 14022 lines |
| documentation | 10255 lines |
| modules a browser never loads | 8 |

This is the figure the integration mandate exists to close. Architecture
that no visitor can reach is architecture that has not shipped.

