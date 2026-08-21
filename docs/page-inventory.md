# The page inventory

**GENERATED.** `python3 tools/page-inventory.py > docs/page-inventory.md`

**Published is not the same as present.** `.vercelignore` keeps 1 file(s)
out of the deploy; they are working artefacts and are held apart here. The
first version of this audit reported `tourism/compare.html` — an internal
sheet of image candidates — as an unreachable public page. It has never
been deployed. An auditor that reports the same false positive every
quarter is one that gets ignored on the quarter it is right.

## Published pages by family

| family | pages |
|---|---|
| `place` | 1404 |
| `tourism` | 55 |
| `portrait` | 54 |
| `country` | 51 |
| `crossing` | 10 |
| `index` | 7 |
| `trust` | 6 |
| `operator` | 5 |
| `fund` | 4 |
| `atlas` | 1 |
| `home` | 1 |
| `journey` | 1 |
| **total** | **1599** |

## Working artefacts, not published

- `tourism/compare.html`

## Stranded, dead-ended or undeclared

| condition | pages |
|---|---|
| not on the global shell | none |
| no inbound link from anywhere | none |
| fewer than two ways onward from `<main>` | none |
| no declared family | none |

The operator's own pages — `about.html`, `cameroon.html`, `contact.html`, `pricing.html`, `services.html` — are exempt from the onward test: they
are a different company's surface and carry their own navigation.

