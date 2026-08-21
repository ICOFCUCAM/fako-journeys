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
| Decision B — how money becomes Travel Points (canonical) | **`docs/travel-point-issuance.md`** — the nine settled rules, the rate-versus-grant distinction, and the numbering map |
| what a Travel Point *is* | **`docs/travel-point-definition.md`** — Section A. The frame is proposed; the unit basis is open, and blocked on the buyback question first |
| what happens economically when one is bought | **`docs/travel-point-economics.md`** — Section B, B1–B25. **DESIGN APPROVED — PENDING LEGAL/REGULATORY REVIEW BEFORE ACTIVATION.** §B24 audits all 28 frozen rules against the code: 21 enforced, 7 recorded and pinned |
| Travel Points, the ledger, payments, or anything economic | **`docs/travel-points-architecture.md`** — audit, architecture, and the legal gate that must clear before a single payment is taken |
| how a customer acquires points over time | **`docs/travel-point-purchase.md`** — the purchase model. A plan is an intention, never a mandate; nothing charges anybody |
| the legal boundary, the compliance ladder, or what counsel must answer | **`docs/travel-point-compliance.md`** — Section D. The programme is `compliance: DRAFT`; only `PILOT` or `ACTIVE` may issue, and the ladder is not skippable |
| any question of the form "can we ship X of the points product yet?" | **`docs/economic-model-decisions.md`** — the reconciliation register. Ten of the original eleven are now settled by Decisions A–F; question 11 (legal structure) is the gate and is still open |
| whether a Travel Point may ever show a cash value | **`docs/travel-point-display.md`** — Decision I. No. Four concepts, never one field called `value`; a buyback quote is `standing: false` |
| price changes, programme discontinuation, wind-down and migration | **`docs/travel-point-continuity.md`** — Decisions F/G/H. A reserved booking is price-locked; migration needs a named successor AND consent; government charges left the default basket |
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
    node tools/journey-checks.js                 105
    node tools/link-checks.js                    78,595 links
    node tools/fund-checks.js                    64
    node tools/design-checks.js                  17
    node tools/points-checks.js                 200 — the Travel Point ledger
    node tools/goal-checks.js                    36 — the Travel Goal is planning only
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
