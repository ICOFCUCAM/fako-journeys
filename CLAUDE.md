# Afrinkong — working notes

A static site: 1,597 HTML files, Vercel with `cleanUrls: true`, an empty
`buildCommand`, and zero npm dependencies at runtime. Pages are generated from
data by `tools/tourism/build.py` and then edited in place by late passes.

## Read these first, depending on the work

| doing | read |
|---|---|
| anything with photographs, R2, or the acquisition budget | **`docs/image-library-state.md`** — the handover, including a list of approaches already tried and found wrong |
| page weight, or quoting a performance number | `docs/weight-baseline.md` |
| deciding what photography to buy | `docs/hero-acquisition.md` |
| the site's structure | `docs/architecture.md` |
| what a Travel Point *is* | **`docs/travel-point-definition.md`** — Section A. The frame is proposed; the unit basis is open, and blocked on the buyback question first |
| what happens economically when one is bought | **`docs/travel-point-economics.md`** — Section B. B1 settled as a product decision, explicitly not a legal opinion; §B1.3 lists the four features counsel must weigh |
| Travel Points, the ledger, payments, or anything economic | **`docs/travel-points-architecture.md`** — audit, architecture, and the legal gate that must clear before a single payment is taken |
| any question of the form "can we ship X of the points product yet?" | **`docs/economic-model-decisions.md`** — eleven open decisions, their provisional defaults, and who owns each |

## The rule that catches people out

**Late passes edit built HTML, and any regeneration wipes them.**
`cmd_places` rewrites 1,363 place pages from scratch. So `bound`, `srcset`,
`sizeattr` and `modern` all run at the end of `cmd_all` — if you write a pass
that edits built HTML, it must join that chain, or one `build.py all` will
silently undo it and no check will notice.

**This applies to a SINGLE generator too, not just `all`.** Running
`build.py fund` on its own regenerated three pages and stripped the company
legal line — Wankong LLC, the Delaware registration, the address, the
privacy/terms links — because `company` and `graft` are late passes and a lone
generator does not run them. Nothing failed; the pages simply lost their
footer. After any single generator, re-run at least:

    python3 tools/tourism/build.py company
    python3 tools/tourism/build.py graft

**`styles/tourism.css` is GENERATED and carries a hand-edit.** Its masthead
breakpoint reads 1140px with a comment explaining that the browser suite caught
an overflow at 1024. The generator emits **1010px**. So any `render` reverts a
documented, browser-verified fix, and only a `git diff` will tell you. The
durable repair is to move that rule into the shell the generator reads; until
somebody does, check that file after regenerating.

## Gates

Run before claiming anything is done. All of these must pass.

    python3 tools/tourism/build.py verify        55 rendered pages
    node tools/library-checks.js                 31 checks
    node tools/heroes.js --check                 no unbounded hero
    node tools/journey-checks.js                 105
    node tools/link-checks.js                    78,595 links
    node tools/fund-checks.js                    64
    node tools/design-checks.js                  17
    node tools/points-checks.js                  33 — the Travel Point ledger
    node tools/goal-checks.js                    21 — the Travel Goal is planning only
    python3 tools/tourism/build.py library provenance
    node tools/browser-checks.js                 259 — 30-40 minutes

`browser-checks.js` takes 30–40 minutes and Node buffers its stdout, so an
empty log means it is running, not hung. Run it whenever HTML changes.

## This environment cannot reach the internet

The sandbox proxy refuses both image providers and our own asset host, and it
intercepts all TLS — so no certificate seen from here tells you anything.
Anything needing network is a GitHub Actions step, not a local command.

## The Travel Point product state

    PLANNING  ->  DRAFT_PROGRAM  ->  ACTIVE_PROGRAM
                                     only here may a point be issued

The site is in **DRAFT_PROGRAM**. `scripts/points-ledger.js` refuses to create
a point under a non-active programme, and two test files assert it. Moving
`PROGRAMS['AFK-TP-2026.1'].status` to `'active'` is a one-word change and the
most consequential one in this repository — it must not be made before the
eleven decisions in `docs/economic-model-decisions.md` have answers.

The Journey Fund shows an **Estimated Travel Goal**: the same journey estimate
in point units. It issues nothing, sells nothing, and holds nothing.

## Credentials

The four `R2_` secrets live in GitHub repository secrets and nowhere else.
Never in a file, a commit, a workflow body, or a log line.

## Style

Match the surrounding code: these files carry long comments that explain *why*,
usually naming the failure that prompted the change. That is deliberate — keep
it. Prefer recording a mistake over quietly deleting the evidence of it.
