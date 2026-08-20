#!/usr/bin/env node
/* build(build(site)) must equal build(site). Exactly, not approximately.
 *
 *     node tools/idempotence-checks.js
 *
 * WHY THIS EXISTS
 *
 * `modern` wrapped every <img> it found in a <picture>, and decided "already
 * wrapped" by reading the 400 characters before the tag. That is fine for a
 * <picture> holding two short local sources and wrong for every one the image
 * library writes: four <source> elements of image.afrinkong.com URLs run past
 * eight hundred characters, so the opening tag fell outside the window and the
 * pass wrapped the image again. Every build added a layer.
 *
 *     <picture><picture><picture><img></picture></picture></picture>
 *
 * Thirty-six of those were sitting on main. Every gate was green: the pages
 * rendered, the images loaded, 259 browser checks passed, and the only witness
 * was `git diff` — which nobody reads when a build reports success.
 *
 * That is the general shape of the danger, and it is not specific to `modern`.
 * A pass that edits built HTML can accumulate damage silently across builds
 * while every check that looks at ONE build stays green. The property that
 * catches it is not about pictures at all:
 *
 *     running the build twice must produce what running it once produced.
 *
 * So this runs the late-pass chain, snapshots every page, runs it again, and
 * fails on the first byte that moved. It needs no knowledge of what the passes
 * do, which is exactly why it will catch the next one too.
 *
 * WHAT IT DOES NOT DO
 *
 * It does not run `render` or `places`, which regenerate from source data and
 * legitimately rewrite files wholesale. Those are checked by the fact that the
 * late passes restore them — see the note in cmd_all. This is about the passes
 * that EDIT existing HTML, which are the ones that can compound.
 */

const { execFileSync } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SKIP = new Set([".git", "node_modules", "incoming", "tools"]);

/* The passes that edit built HTML in place. Order matters and matches the
   tail of cmd_all: anything that rewrites URLs runs before anything that
   reads them. */
const CHAIN = [
  ["library", "rewrite"],
  ["bound"],
  ["srcset"],
  ["sizeattr"],
  ["modern"],
];

let pass = 0;
let fail = 0;
function report(ok, what, detail) {
  console.log(`${ok ? "PASS" : "FAIL"}\t${what}\t${detail}`);
  ok ? pass++ : fail++;
}

function pages(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(e.name) || e.name.startsWith(".")) continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) pages(f, out);
    else if (e.name.endsWith(".html")) out.push(f);
  }
  return out;
}

function snapshot() {
  const out = new Map();
  for (const f of pages(ROOT)) {
    out.set(path.relative(ROOT, f),
            crypto.createHash("sha1").update(fs.readFileSync(f)).digest("hex"));
  }
  return out;
}

function runChain() {
  for (const step of CHAIN) {
    execFileSync("python3", ["tools/tourism/build.py", ...step, "--fetch"],
                 { cwd: ROOT, encoding: "utf-8", maxBuffer: 1 << 28 });
  }
}

/* A dirty tree would make the diff below meaningless — it could not tell a
   pass that changed something from an edit somebody had not committed. */
const dirty = execFileSync("git", ["status", "--porcelain", "--", "*.html"],
                           { cwd: ROOT, encoding: "utf-8" }).trim();
if (dirty) {
  console.log("SKIP\tbuild(build(x)) = build(x)\tuncommitted HTML in the tree:\n" +
              dirty.split("\n").slice(0, 5).map((l) => "  " + l).join("\n"));
  process.exit(0);
}

runChain();
const first = snapshot();
runChain();
const second = snapshot();

const moved = [];
for (const [file, hash] of first) {
  if (second.get(file) !== hash) moved.push(file);
}

report(
  moved.length === 0,
  "build(build(x)) = build(x) — the late passes are idempotent",
  moved.length
    ? `${moved.length} page(s) changed on the second run: ${moved.slice(0, 4).join(", ")}`
    : `${first.size} pages, byte-identical after a second full chain`
);

/* The specific damage that motivated all this, asserted directly: whatever the
   passes do, no <picture> may end up inside another one. Kept separate from the
   general property because a named failure reads better than a hash mismatch,
   and because this one is invalid HTML rather than merely unstable. */
let nested = 0;
const where = [];
for (const f of pages(ROOT)) {
  const src = fs.readFileSync(f, "utf-8");
  for (const m of src.matchAll(/<picture\b[^>]*>[\s\S]*?<\/picture\s*>/g)) {
    if (/<picture\b/.test(m[0].slice(9))) {
      nested++;
      if (where.length < 3) where.push(path.relative(ROOT, f));
    }
  }
}
report(
  nested === 0,
  "no <picture> is nested inside another",
  nested ? `${nested} nested block(s), e.g. ${where.join(", ")}` : "none found"
);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
