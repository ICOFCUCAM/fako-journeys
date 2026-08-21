# Afrinkong — working notes

A static site: 1,597 HTML files, Vercel with `cleanUrls: true`, an empty
`buildCommand`, and zero npm dependencies at runtime. Pages are generated from
data by `tools/tourism/build.py` and then edited in place by late passes.

## Read these first, depending on the work

| doing | read |
|---|---|
| **the product as a whole — what exists, and how it connects** | **`docs/product-archaeology.md`** — Phase 1. Nine surfaces, four pages per country, and the edges missing rather than the nodes. START HERE for design work |
| **the customer-facing product, design system or IA** | **`docs/design-audit.md`** — the measured gap. NOTE: its "39 system states" undercounts; the real figure is 72, counted in `docs/state-language.md`. 15 stylesheets, 418 font sizes, 45 breakpoints, 52 tokens. The measured gap and the order to close it |
| **taking the model to counsel** | **`docs/travel-point-legal-review-package.md`** — 48 questions across nine areas, what is already decided, and the four blockers. THE CURRENT PHASE |
| accounts, the wallet view, recovery, admin adjustments | **`docs/travel-point-wallet.md`** — item Z. Planning needs no account; ownership does. There is no admin edit balance |
| fraud, risk holds, chargeback after travel | **`docs/travel-point-risk.md`** — item Y. A settled payment is necessary and never sufficient; absent signals HOLD, never ALLOW |
| "is X decided / built / open?" across the whole model | **`docs/travel-point-matrix.md`** — the A–AJ coverage map. 29 enforced, 3 counsel, 4 open, 0 conflicts |
| **anything economic — Travel Points, programmes, the ledger** | **`docs/travel-point-decisions.md`** — START HERE. The canonical index: definition → decisions A–I → programme state → implementation. Every other points document hangs off it |
| anything with photographs, R2, or the acquisition budget | **`docs/image-library-state.md`** — the handover, including a list of approaches already tried and found wrong |
| **what a customer is shown when something is pending, held, ended or broken** | **`docs/state-language.md`** — Item 4. 72 states, 6 tones, one sentence each. GENERATED: `node tools/state-doc.js > docs/state-language.md`. ENDED is not BROKEN, and that is the load-bearing line |
| **who is acting — Afrinkong, Wankong LLC or the operator** | **`docs/entity-architecture.md`** — three layers. Money and entitlement are ALWAYS Wankong LLC. A link is entity + context + position + action, never a URL. The payment check fails the day a card field appears without naming the payee |
| **the design mandate — START HERE for any visual work** | **`docs/system-audit.md`** — measured. 10 mastheads, 7 footers, 24 class prefixes, 183 type sizes, 1,529 pages with no body class. And what it found NOTHING wrong with |
| the product as a system, or which family a page belongs to | **`docs/product-architecture.md`** — A and D. Five kinds of surface, six page families, and the disposition of all 1,597 pages |
| **the navigation, the three areas, or "where does X live?"** | **`docs/navigation-architecture.md`** — B. BUILT AND LIVE on all 1,597 pages. Explore · Plan; TRAVEL and FUND reserved and absent. All seven questions settled |
| tokens, type, components, cards, buttons, states, photography | **`docs/design-system.md`** — C and E. 24 prefixes become 11 primitives; 183 type sizes become 11; 22 shadows become 2 |
| motion, responsive behaviour, forms, or what "premium" means here | **`docs/interaction-and-premium.md`** — F and G. Motion explains a relationship or it does not happen |
| **how to change anything visual without breaking the build** | **`docs/migration-plan.md`** — H. Every page is generated: 1,597 pages are reachable from 21 files. Three named hazards |
| page weight, or quoting a performance number | `docs/weight-baseline.md` |
| deciding what photography to buy | `docs/hero-acquisition.md` |
| the site's structure | `docs/architecture.md` |
| Decision B — how money becomes Travel Points (canonical) | **`docs/travel-point-issuance.md`** — the nine settled rules, the rate-versus-grant distinction, and the numbering map |
| what a Travel Point *is* | **`docs/travel-point-definition.md`** — Section A. The frame is proposed; the unit basis is open, and blocked on the buyback question first |
| what happens economically when one is bought | **`docs/travel-point-economics.md`** — Section B, B1–B25. **DESIGN APPROVED — PENDING LEGAL/REGULATORY REVIEW BEFORE ACTIVATION.** §B24 audits all 28 frozen rules against the code: 21 enforced, 7 recorded and pinned |
| Travel Points, the ledger, payments, or anything economic | **`docs/travel-points-architecture.md`** — audit, architecture, and the legal gate that must clear before a single payment is taken |
| how a customer acquires points over time | **`docs/travel-point-purchase.md`** — the purchase model. A plan is an intention, never a mandate; nothing charges anybody |
| the legal boundary, the compliance ladder, or what counsel must answer | **`docs/travel-point-compliance.md`** — Section D. The programme is `compliance: DRAFT`; only `PILOT` or `ACTIVE` may issue, and the ladder is not skippable |
| any question of the form "can we ship X of the points product yet?" | ask `readiness(programId)`, not a document. **`docs/economic-model-decisions.md`** is the reconciliation register — ten of eleven settled by Decisions A–I; question 11 (legal structure) is the gate and is still open |
| whether a Travel Point may ever show a cash value | **`docs/travel-point-display.md`** — Decision I. No. Four concepts, never one field called `value`; a buyback quote is `standing: false` |
| price changes, discontinuation, **cessation of travel**, or the activation gate | **`docs/travel-point-continuity.md`** — Decisions F/G/H. A reserved booking is price-locked; cessation makes redemption unavailable though still permitted; `active` is NOT `mayIssue` |
| Decision F — what a Travel Point can buy (canonical) | **`docs/travel-point-redemption.md`** — the eligible basket, the exclusions as a list with reasons, and the redemption cap |
| Decision E — gifting, inheritance, transferability (canonical) | **`docs/travel-point-transfer.md`** — REVERSES B14/C9: `transferable` is now true. Sale still forbidden. Records the buy-gift-cash-out hole this closed |
| Decision D — expiry, programme duration, unused points (canonical) | **`docs/travel-point-duration.md`** — eleven rules. D8 changed behaviour: earliest expiry first, not promotional first |
| Decision C — what happens when a customer leaves (canonical) | **`docs/travel-point-exit.md`** — the ten settled rules, and the three that were holding only by accident |
| repurchase ("buyback"), cancellation, transfer or expiry | **`docs/travel-point-buyback.md`** — Section E, including the B12/E2 contradiction and how it was reconciled |
| pricing, bonuses, or "why can't we just give a better rate for a bigger purchase?" | **`docs/travel-point-pricing.md`** — Section F. `issueRate` is one number per programme; a volume incentive is a grant, never a rate |

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
    node tools/journey-checks.js                 112
    node tools/link-checks.js                    80,367 links + the country graph
    node tools/fund-checks.js                    64
    node tools/design-checks.js                  17
    node tools/points-checks.js                 245 — the Travel Point ledger
    node tools/goal-checks.js                    36 — the Travel Goal is planning only
    node tools/state-checks.js                   25 — the state language vs the states
    node tools/shell-checks.js                   13 — one shell, one navigation
    node tools/entity-checks.js                  17 — who is acting, and why
    python3 tools/tourism/build.py test         960 — THE SUITE CI RUNS. ~25 min
    python3 tools/tourism/build.py library provenance
    node tools/browser-checks.js                 259 — 30-40 minutes

`browser-checks.js` takes 30–40 minutes and Node buffers its stdout, so an
empty log means it is running, not hung. Run it whenever HTML changes.

**`build.py test` is the suite GitHub Actions runs, and it was missing from
this list.** Nine hundred and sixty checks, about twenty-five minutes. It was
absent here for long enough that a whole session's work was reported as "all
gates green" while CI was red — and because it is the FIRST step in
`tourism-tests.yml`, its failure skips every step after it, including "Rebuild
pages and check the generated HTML". A red suite there means CI has validated
nothing at all.

It has **25 pre-existing failures** that predate this list being corrected. They
are real and unfixed; see the run log. The number to hold the line on is 25 —
anything above it is new.

## This environment cannot reach the internet

The sandbox proxy refuses both image providers and our own asset host, and it
intercepts all TLS — so no certificate seen from here tells you anything.
Anything needing network is a GitHub Actions step, not a local command.

## The Travel Point product state

    PLANNING  ->  DRAFT_PROGRAM  ->  ACTIVE_PROGRAM
                                     only here may a point be issued

The site is in **DRAFT_PROGRAM**. `scripts/points-ledger.js` refuses to create
a point under a non-issuing programme, and two test files assert it.

**The gate is `compliance`, NOT `status`.** This file used to say that setting
`status` to `'active'` was a one-word change and the most consequential one in
the repository. That stopped being true when the compliance ladder was built:
`status: 'active'` is now inert — a programme carrying it still reports
`mayIssue: false` and `stateOf: DRAFT_PROGRAM`. Guarding the wrong word is
worse than guarding nothing, so the real boundary is:

    DRAFT -> LEGAL_REVIEW -> ACCOUNTING_REVIEW -> APPROVED -> PILOT -> ACTIVE

Not skippable, and `mayActivate()` refuses the last rung while any of
`maxProgrammeExposure`, `maxPerTransaction`, `maxPerCustomerPerYear`,
`buyback.basis` or `minPurchase` is unset, or while `issueRate` is anything but
a single positive number. It must not be walked before question 11 in
`docs/economic-model-decisions.md` has an answer.

**And reaching `ACTIVE` is still not enough.** Decision G separated approval
from operation: `mayIssue` requires an issuing compliance state AND
`issuanceEnabled === true`, which is a distinct act testing operational
readiness the ladder does not. Either alone is inert — the same failure
`status` was, so one flag is never the whole gate.

Ask `readiness(programId)` rather than reading this file. It reports the rung,
both conditions and every unmet one, and deliberately never consults `status`.

A check in `points-checks.js` fails if this file, or any decision document,
starts claiming otherwise again.

The Journey Fund shows an **Estimated Travel Goal**: the same journey estimate
in point units. It issues nothing, sells nothing, and holds nothing.

## Credentials

The four `R2_` secrets live in GitHub repository secrets and nowhere else.
Never in a file, a commit, a workflow body, or a log line.

## Style

Match the surrounding code: these files carry long comments that explain *why*,
usually naming the failure that prompted the change. That is deliberate — keep
it. Prefer recording a mistake over quietly deleting the evidence of it.
