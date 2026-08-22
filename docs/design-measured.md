# The design system, measured

**GENERATED.** `python3 tools/design-audit.py > docs/design-audit.md`

16 stylesheets and 66 inline `<style>` blocks on published pages, with
`@media print` removed by counting braces rather than by splitting on a
string — a split discards everything after the first print block, which
here means sixteen stylesheets, and produces a figure nine times too
small.

| | declarations | distinct | target |
|---|---|---|---|
| font-size | 1277 | **186** | 11 |
| box-shadow | 31 | **22** | 2 |
| border-radius | 15 | **4** | — |
| breakpoint | 287 | **32** | 4 |
| prefix | 5338 | **26** | 11 |
| custom-property | 152 | **112** | — |

## The duplication, which is the number to drive down first

| | |
|---|---|
| distinct font sizes site-wide (the vocabulary) | **186** |
| sum of each stylesheet's own distinct sizes | **439** |
| the gap — the same size restated in another file | **253** |

`docs/design-audit.md` reported **418 distinct font-size declarations
site-wide**. That figure is the second row, not the first: it sums each
file's own distinct values and so double-counts everything two
stylesheets share. Measured its way today the number is 439, so by its
own method the type system has not consolidated — it has grown.

| stylesheet | its own distinct sizes |
|---|---|
| `gateway.css` | 81 |
| `tourism.css` | 44 |
| `transafrique.css` | 44 |
| `kamerun.css` | 36 |
| `journey.css` | 34 |
| `afrinkong.css` | 29 |
| `story.css` | 27 |
| `country.css` | 26 |

Declarations and distinct values answer different questions. 1277 font-size
declarations drawn from 186 distinct values is a system with 186 type sizes;
the same declarations drawn from 11 would be a system with a type scale.

## Breakpoints

`380px`, `400px`, `420px`, `460px`, `480px`, `520px`, `560px`, `561px`, `620px`, `640px`, `680px`, `700px`, `760px`, `820px`, `860px`, `880px`, `900px`, `901px`, `940px`, `950px`, `980px`, `1000px`, `1010px`, `1050px`, `1079px`, `1080px`, `1099px`, `1100px`, `1140px`, `1180px`, `1360px`, `1600px`

## Class prefixes

`fj`, `wa`, `jn`, `tf`, `af`, `at`, `jf`, `st`, `wo`, `mt`, `ct`, `tq`, `is`, `pl`, `po`, `cm`, `sx`, `hw`, `ex`, `tr`, `cp`, `pi`, `nf`, `no`, `xx`, `has`

## The ratchet

`--check` fails if any figure rises above the ceiling recorded in
`tools/design-audit.py`. The ceilings are today's measurements and may
only ever be lowered. The system is free to shrink and cannot grow.

It does not demand the target numbers yet. Cutting 186 type sizes to 11
is the work of many commits, and a gate that fails until then is a gate
somebody switches off.

