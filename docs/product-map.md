# The product map

**GENERATED.** `python3 tools/product-map.py > docs/product-map.md`

code module → user-facing capability → page. Every module gives one of
four answers, and the answer lives in the module's own header so it
cannot drift from the code it describes.

"Loaded by zero pages" is the wrong test for a static site. `entities.js`
is 223 lines the browser never sees, whose whole content a customer reads
at `/trust`, because the model is rendered into HTML at build time.
Shipping it to a phone to draw a static table would be worse in every
respect. The question is whether the KNOWLEDGE reaches a customer.

## live

*a customer meets this — in the browser, or rendered at build time*

| module | lines | pages loading it | surface |
|---|---|---|---|
| `atlas.js` | 973 | 1 | /atlas |
| `crossings.js` | 79 | 10 | /trans-afrique/* |
| `enquiry.js` | 103 | 5 | /enquire |
| `entities.js` | 225 | 0 | /trust (rendered at build time by tools/tourism/trust_page.py) |
| `events.js` | 114 | 1484 | 1,484 pages |
| `explore.js` | 315 | 1600 | every page |
| `fund-math.js` | 186 | 1 | /journey-fund |
| `fund.js` | 499 | 1 | /journey-fund |
| `journey-engine.js` | 675 | 1 | /journey |
| `journey.js` | 1549 | 1 | /journey |
| `meet.js` | 306 | 1 | /meet |
| `points-ledger.js` | 2679 | 1 | /journey-fund, /travel-points |
| `portrait.js` | 133 | 54 | /portrait/* |
| `state-language.js` | 470 | 1 | /journey-fund |
| `stories.js` | 184 | 1 | /stories |
| `story-search.js` | 231 | 1522 | 1,522 pages |
| `table.js` | 216 | 1 | / (the homepage strip) |
| `travel-goal.js` | 177 | 1 | /journey-fund |
| `window.js` | 75 | 2 | / and /trans-afrique |

## gated

*complete and correct, and must not be surfaced yet*

| module | lines | pages loading it | gate |
|---|---|---|---|
| `account.js` | 263 | 0 | accounts-not-built |
| `booking.js` | 348 | 0 | booking-not-built |
| `buyback.js` | 206 | 0 | programme-compliance |
| `journey-catalogue.js` | 268 | 0 | programme-compliance |
| `purchase-plan.js` | 160 | 0 | programme-compliance |
| `risk.js` | 255 | 0 | payments-not-live |
| `transfer.js` | 264 | 0 | programme-compliance |

## What is being held back, and by what

7 modules, 1764 lines. None of it is unfinished; all of it is waiting.

| gate | modules |
|---|---|
| `accounts-not-built` | `account.js` |
| `booking-not-built` | `booking.js` |
| `payments-not-live` | `risk.js` |
| `programme-compliance` | `buyback.js`, `journey-catalogue.js`, `purchase-plan.js`, `transfer.js` |

**A gated module that acquires a surface fails `--check`.** That is
the check that matters here: it is how unreleased economic
functionality would reach a customer by accident rather than by
decision.

