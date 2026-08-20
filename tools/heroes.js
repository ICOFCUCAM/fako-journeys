#!/usr/bin/env node
/* Who owns the one photograph a phone is certain to fetch.
 *
 *     node tools/heroes.js            # the census
 *     node tools/heroes.js --list     # every page whose hero is still hotlinked
 *
 * WHY THIS EXISTS
 *
 * `tools/weigh.js` measured six rewritten pages after 527 photographs had been
 * migrated and the six-page total came out at 7.40 MB — ninety kilobytes better
 * than the same six pages measured when only nineteen were migrated. Five
 * hundred and eight additional first-party photographs bought almost nothing.
 *
 * That is not a fault in the migration. It is a fact about which photograph a
 * phone actually requests. Below the fold, `loading="lazy"` means a card is
 * never fetched at all, so migrating it changes no bytes until somebody
 * scrolls. The image that always crosses the wire is the eager one, and this
 * site has exactly one of those per page: the hero.
 *
 * So page weight is decided almost entirely by who serves the hero, and the
 * useful question is not "how many photographs are migrated" but "how many
 * heroes are ours". This counts that, and splits what remains by whether the
 * provider is being asked for a sensible width or for the full-resolution
 * original the photographer uploaded.
 *
 * It reads the built HTML and the register. No network, so it runs anywhere.
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const HOST = "image.afrinkong.com";
const SKIP = new Set([".git", "node_modules", "incoming"]);

function pages(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(e.name)) continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) pages(f, out);
    else if (e.name.endsWith(".html")) out.push(f);
  }
  return out;
}

/* A <picture> is one image unit, not three. Its <source> siblings carry no
 * loading attribute — that lives on the <img> inside — so treating each tag
 * separately reports a lazy first-party <picture> as eager, which is how I
 * first read this wrong and concluded the heroes were already ours. */
function units(src) {
  const found = [];
  const re = /<picture\b[\s\S]*?<\/picture>|<img\b[^>]*>/g;
  let m;
  while ((m = re.exec(src))) found.push(m[0]);
  return found;
}

function firstRemoteUrl(unit) {
  const urls = [...unit.matchAll(/(?:srcset|src)="([^"]+)"/g)]
    .map((x) => x[1].replace(/&amp;/g, "&").split(",")[0].trim().split(/\s+/)[0])
    .filter((u) => /^https?:/.test(u));
  return urls[0] || null;
}

/* The hero: the page's one eager remote photograph. Local files — the brand
 * mark, inline SVG, data URIs — are not it. */
function hero(src) {
  for (const u of units(src)) {
    const img = (u.match(/<img\b[^>]*>/) || [""])[0];
    if (/loading="lazy"/.test(img)) continue;
    const url = firstRemoteUrl(u);
    if (url) return url;
  }
  return null;
}

function sourceKey(url) {
  let m = url.match(/images\.pexels\.com\/photos\/(\d+)\//);
  if (m) return "pexels:" + m[1];
  m = url.match(/images\.unsplash\.com\/photo-([A-Za-z0-9_-]+)/);
  if (m) return "unsplash:" + m[1];
  return null;
}

const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "tourism/assets.json"), "utf-8"));
const bySource = new Map();
for (const [id, a] of Object.entries(reg.assets || {})) {
  if (a.sourceKey) bySource.set(a.sourceKey, { id, ...a });
}

const rows = [];
for (const file of pages(ROOT)) {
  const rel = path.relative(ROOT, file);
  const url = hero(fs.readFileSync(file, "utf-8"));
  if (!url) { rows.push({ rel, kind: "none" }); continue; }
  if (new URL(url).host === HOST) { rows.push({ rel, kind: "ours", url }); continue; }
  const asset = bySource.get(sourceKey(url) || "");
  rows.push({
    rel,
    kind: asset && asset.publishedAt ? "published-not-rewritten" : "unknown",
    bounded: /[?&]w=\d+/.test(url),
    id: asset ? asset.id : null,
    url,
  });
}

const section = (rel) => (rel.includes("/") ? rel.split("/")[0] : "(root)");
const tally = {};
for (const r of rows) {
  if (r.kind === "none") continue;
  const s = (tally[section(r.rel)] ||= { pages: 0, ours: 0, pub: 0, unknown: 0, unbounded: 0 });
  s.pages++;
  if (r.kind === "ours") s.ours++;
  else {
    r.kind === "published-not-rewritten" ? s.pub++ : s.unknown++;
    if (!r.bounded) s.unbounded++;
  }
}

if (process.argv.includes("--list")) {
  for (const r of rows) {
    if (r.kind === "ours" || r.kind === "none") continue;
    console.log("%s\t%s\t%s\t%s", r.rel, r.kind,
                r.bounded ? "bounded" : "unbounded", r.id || "-");
  }
  process.exit(0);
}

const n = (v, w) => String(v).padStart(w);
console.log("The hero census — the one photograph every visitor fetches\n");
console.log("section       pages     ours   published,     never       of these");
console.log("                               not rewritten  registered  unbounded");
console.log("-".repeat(72));
let t = { pages: 0, ours: 0, pub: 0, unknown: 0, unbounded: 0 };
for (const k of Object.keys(tally).sort((a, b) => tally[b].pages - tally[a].pages)) {
  const s = tally[k];
  for (const f of Object.keys(t)) t[f] += s[f];
  console.log("%s%s%s%s%s%s", k.padEnd(14), n(s.pages, 5), n(s.ours, 9),
              n(s.pub, 14), n(s.unknown, 12), n(s.unbounded, 15));
}
console.log("-".repeat(72));
console.log("%s%s%s%s%s%s", "total".padEnd(14), n(t.pages, 5), n(t.ours, 9),
            n(t.pub, 14), n(t.unknown, 12), n(t.unbounded, 15));
console.log("\n%d page(s) have no eager remote photograph at all.",
            rows.filter((r) => r.kind === "none").length);
console.log("\n"
  + "  ours                    served from " + HOST + ".\n"
  + "  published, not rewritten  the photograph is already on our host; the page\n"
  + "                          still hotlinks it because the asset is art-directed\n"
  + "                          and rewrite excludes those until a second crop\n"
  + "                          exists. No acquisition needed — a crop does it.\n"
  + "  never registered        not in the register at all. Needs a decision\n"
  + "                          before it can be migrated or replaced.\n"
  + "  unbounded               the URL carries no width, so the provider serves\n"
  + "                          the full-resolution original to a 390px phone.");
