# incoming/

Drop photographs here, then run:

    npm run tourism:intake -- --describe

Each file is measured, matched against every image slot on the site, and
proposed for the one it fits — by shape, by what the filename says, and (with
`--describe`) by what the vision model sees in it. Nothing is placed: the
proposals land in the candidate pool, `npm run tourism:compare` shows them
beside the generated and stock options, and you choose.

Name files after what they show. `mount-cameroon-trekkers-above-treeline.jpg`
matches itself to a slot; `IMG_4471.jpg` is reported as unmatched unless you
run `--describe`.

This folder is not deployed.
