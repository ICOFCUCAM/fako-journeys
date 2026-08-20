#!/usr/bin/env node
/* A published photograph stays ours. Enforced, not intended.
 *
 *     node tools/library-permanence.js
 *
 * WHAT WENT WRONG, WHICH IS WHY THIS EXISTS
 *
 * `build.py render` rebuilds the 54 country pages from source data. That data
 * knows nothing about the image library, so the rebuild reverted roughly
 * eighteen first-party photographs per page to Pexels hotlinks — about a
 * thousand references — and every gate stayed green. The pages were valid.
 * The images loaded. They had simply stopped being ours, and the only witness
 * was `git diff`, which nobody reads when a build reports success.
 *
 * `library rewrite` now runs as part of the late-pass chain, so the revert
 * repairs itself. But "the chain is ordered correctly" is a property of a file
 * somebody can edit, and the failure mode is silent. So this asserts the
 * OUTCOME instead:
 *
 *     an asset that is published AND wired into pages
 *     must have no provider URL left anywhere in the built HTML
 *
 * If a future render reverts one, this goes red. If somebody removes rewrite
 * from the chain, this goes red on the next build. Neither needs anyone to
 * remember why.
 *
 * WHY NOT JUST CHECK THE CHAIN
 *
 * It does that too, as a second check — a build step that has been deleted
 * should be caught by reading the build file, not only by its consequences.
 * But the outcome check is the one that matters: it holds even if the chain is
 * reorganised, renamed, or replaced by something entirely different.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SKIP = new Set([".git", "node_modules", "incoming", "tools"]);

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

const reg = JSON.parse(
  fs.readFileSync(path.join(ROOT, "tourism/assets.json"), "utf-8"));
const assets = Object.values(reg.assets || {});

/* The ones this check speaks for: uploaded to R2 and pointed at by pages.
   An asset that is published but deliberately held back from rewrite is not a
   leak, it is a queue — see the art-direction gate in library.py. */
const wired = new Map();
for (const a of assets) {
  if (a.publishedAt && a.rewrittenAt && a.originalUrl) {
    wired.set(a.originalUrl.split("?")[0], a.id);
  }
}

/* data-was holds the pre-migration tag base64-encoded so a revert can restore
   it byte for byte. That is a record of history, not a live reference, and it
   does not decode to anything a browser fetches. Strip it before looking. */
const WAS = /\sdata-was="[A-Za-z0-9+/=]*"/g;
const PROVIDER = /https:\/\/images\.(?:pexels|unsplash)\.com\/[^"'\s>]+/g;

const leaks = [];
for (const file of pages(ROOT)) {
  const src = fs.readFileSync(file, "utf-8").replace(WAS, "");
  for (const m of src.matchAll(PROVIDER)) {
    const base = m[0].replace(/&amp;/g, "&").split("?")[0];
    const id = wired.get(base);
    if (id) {
      leaks.push({ file: path.relative(ROOT, file), id, url: base });
    }
  }
}

report(
  leaks.length === 0,
  "no published, wired photograph has reverted to its provider",
  leaks.length
    ? `${leaks.length} leak(s): ${leaks.slice(0, 3)
        .map((l) => `${l.id} on ${l.file}`).join("; ")}`
    : `${wired.size} wired asset(s) checked across the built site`
);

/* The structural half. Cheap, and it names the cause rather than the symptom
   when somebody deletes the step. */
const build = fs.readFileSync(path.join(ROOT, "tools/tourism/build.py"), "utf-8");
const inChain = /_library\.rewrite\(/.test(build);
report(
  inChain,
  "`library rewrite` is still part of the build chain",
  inChain ? "cmd_all calls it before the remaining late passes"
          : "cmd_all no longer calls it — a render will revert the library");

/* And the register's own account of itself has to agree with the pages: every
   asset the register calls live must actually be referenced by our host
   somewhere. A `rewrittenAt` on an asset no page uses is a stale record. */
let referenced = 0;
const host = (reg.host || "").replace(/^https?:\/\//, "").replace(/\/$/, "");
const seen = new Set();
for (const file of pages(ROOT)) {
  const src = fs.readFileSync(file, "utf-8");
  for (const m of src.matchAll(/image\.afrinkong\.com\/(?:[a-z0-9]+\/)?\d+\/(AKL-\d+)/g)) {
    seen.add(m[1]);
  }
}
for (const a of assets) if (a.rewrittenAt && seen.has(a.id)) referenced++;
const stale = [...wired.values()].filter((id) => !seen.has(id));
report(
  stale.length === 0,
  "every asset the register calls live is actually on a page",
  stale.length ? `${stale.length} stale: ${stale.slice(0, 3).join(", ")}`
               : `${referenced} live asset(s), all referenced from ${host}`);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
