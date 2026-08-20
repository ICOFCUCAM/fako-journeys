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

## The rule that catches people out

**Late passes edit built HTML, and any regeneration wipes them.**
`cmd_places` rewrites 1,363 place pages from scratch. So `bound`, `srcset`,
`sizeattr` and `modern` all run at the end of `cmd_all` — if you write a pass
that edits built HTML, it must join that chain, or one `build.py all` will
silently undo it and no check will notice.

## Gates

Run before claiming anything is done. All of these must pass.

    python3 tools/tourism/build.py verify        55 rendered pages
    node tools/library-checks.js                 31 checks
    node tools/heroes.js --check                 no unbounded hero
    node tools/journey-checks.js                 105
    node tools/link-checks.js                    78,595 links
    node tools/fund-checks.js                    64
    node tools/design-checks.js                  17
    python3 tools/tourism/build.py library provenance
    node tools/browser-checks.js                 259 — 30-40 minutes

`browser-checks.js` takes 30–40 minutes and Node buffers its stdout, so an
empty log means it is running, not hung. Run it whenever HTML changes.

## This environment cannot reach the internet

The sandbox proxy refuses both image providers and our own asset host, and it
intercepts all TLS — so no certificate seen from here tells you anything.
Anything needing network is a GitHub Actions step, not a local command.

## Credentials

The four `R2_` secrets live in GitHub repository secrets and nowhere else.
Never in a file, a commit, a workflow body, or a log line.

## Style

Match the surrounding code: these files carry long comments that explain *why*,
usually naming the failure that prompted the change. That is deliberate — keep
it. Prefer recording a mistake over quietly deleting the evidence of it.
