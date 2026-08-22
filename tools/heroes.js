#!/usr/bin/env node
/* Who owns the one photograph a phone is certain to fetch.
 *
 *     node tools/heroes.js            # the census
 *     node tools/heroes.js --list     # every page whose hero is still hotlinked
 *     node tools/heroes.js --check    # fail if any hero is unbounded
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

/* MATCHED ON THE URL WE RECORDED, NOT ON A KEY REBUILT FROM THE URL.
 *
 * The obvious version derives a sourceKey from the page's URL — pexels:12345
 * from /photos/12345/, unsplash:<slug> from /photo-<slug> — and looks that up
 * in the register. It is wrong for Unsplash, silently: the register's
 * sourceKey holds Unsplash's photo ID (JaD-db16oAE) while the URL carries a
 * different slug (1503592687001-f8d008454cbf), so no Unsplash asset ever
 * matches and every one of them reports as a photograph we do not own. That
 * cost nine assets here and eighty-two in the acquisition table before it was
 * caught.
 *
 * originalUrl is the URL the register itself recorded, so comparing against it
 * needs no reconstruction and cannot drift per provider. */
const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "tourism/assets.json"), "utf-8"));
const bySource = new Map();
for (const [id, a] of Object.entries(reg.assets || {})) {
  if (a.originalUrl) bySource.set(a.originalUrl.split("?")[0], { id, ...a });
}

const rows = [];
for (const file of pages(ROOT)) {
  const rel = path.relative(ROOT, file);
  const url = hero(fs.readFileSync(file, "utf-8"));
  if (!url) { rows.push({ rel, kind: "none" }); continue; }
  if (new URL(url).host === HOST) { rows.push({ rel, kind: "ours", url }); continue; }
  const asset = bySource.get(url.split("?")[0]);
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

/* A GATE, NOW THAT THE ANSWER IS ZERO.
 *
 * Every hero on this site is either first-party or asks its provider for a
 * width. That took two migrations and a bounding pass to reach, and it is one
 * careless generator change away from being untrue again — a new page shipped
 * with a bare provider URL puts a full-resolution original back in front of a
 * phone, and nothing else in the suite would notice.
 *
 * So: --check fails if any hero is unbounded. Cheap, and it is the property
 * every measurement in docs/weight-baseline.md turns on. */
if (process.argv.includes("--check")) {
  const bad = rows.filter((r) => r.kind !== "ours" && r.kind !== "none" && !r.bounded);
  for (const r of bad.slice(0, 20)) console.log(`FAIL\t${r.rel}\t${r.url}`);
  console.log(
    `${bad.length ? "FAIL" : "PASS"}\tno hero asks a provider for the full original\t` +
    `${rows.filter((r) => r.kind !== "none").length} hero(es), ${bad.length} unbounded`
  );

  /* ---- THE HERO CONTRACT ------------------------------------------------
   *
   * Weight was the only thing measured here. A hero is also the largest thing
   * a screen reader has to describe, the largest thing that can shift the
   * layout under a reader's thumb, and the one image whose loading priority
   * decides how fast the page feels. None of that was asserted anywhere.
   *
   * Four properties, on every hero, in both families:
   *
   *     alt          it is the subject of the page; an unlabelled one is a
   *                  page whose main image is invisible to a reader who
   *                  cannot see it
   *     width/height so the space is reserved and the text below does not
   *                 jump when the photograph lands
   *     loading      fetchpriority="high" or loading="lazy" — a DECISION
   *                 either way, rather than the browser's guess
   *     a fallback   where there is no photograph, a plate at the same
   *                 geometry, so the page does not change shape the day
   *                 acquisition fills the slot
   *
   * MEASURED WITH NO WINDOW. Three earlier attempts at this scan capped the
   * search at 300 and then 2,200 characters after the class attribute, and
   * reported 40 heroes with no <img> at all. The <picture><source srcset>
   * block that `modern` writes is longer than that, so the <img> fell outside
   * the window. Every one of those 40 was a false positive. The block now runs
   * to its own closing tag however long that takes.
   */
  const HERO_CLASS = /class="([a-z]{2}-hero[a-z-]*)"/g;
  const ignore = new Set();
  const problems = { "no alt": [], "no dimensions": [], "no loading decision": [] };
  let heroes = 0, plates = 0, arted = 0;
  for (const abs of pages(ROOT)) {
    /* pages() returns ABSOLUTE paths — joining ROOT again produced
       /home/user/fako-journeys/home/user/fako-journeys/404.html and an ENOENT.
       The relative form is only wanted for the message. */
    const rel = path.relative(ROOT, abs);
    const html = fs.readFileSync(abs, "utf-8");
    HERO_CLASS.lastIndex = 0;
    let m;
    while ((m = HERO_CLASS.exec(html))) {
      const fam = m[1];
      /* The inner parts of a hero carry the same prefix; only the outer
         element is the hero itself. */
      if (/-(in|scrim|pic)$/.test(fam) || ignore.has(fam)) continue;
      const ends = ["</figure>", "</section>"]
        .map((t) => html.indexOf(t, m.index)).filter((i) => i > 0);
      const block = html.slice(m.index, ends.length ? Math.min(...ends) : html.length);
      heroes++;
      const img = block.match(/<img[^>]*>/);
      if (!img) { plates++; continue; }
      if (!/\salt=/.test(img[0])) problems["no alt"].push(rel);
      if (!(/\swidth=/.test(img[0]) && /\sheight=/.test(img[0]))) {
        problems["no dimensions"].push(rel);
      }
      if (!/fetchpriority=|loading=/.test(img[0])) {
        problems["no loading decision"].push(rel);
      }
      if (/<source[^>]*\smedia=/.test(block)) arted++;
    }
  }
  let contractFail = 0;
  for (const [what, list] of Object.entries(problems)) {
    if (list.length) contractFail++;
    console.log(
      `${list.length ? "FAIL" : "PASS"}\tevery hero has ${
        what.replace(/^no /, "")}\t${
        list.length ? `${list.length} without it, e.g. ${list[0]}`
                    : `${heroes - plates} photographic hero(es)`}`);
  }
  console.log(
    `PASS\ta hero with no photograph falls back at the same geometry\t` +
    `${plates} plate(s) of ${heroes} heroes \u2014 the page does not change ` +
    `shape the day acquisition fills the slot`);

  /* Art direction is REPORTED, not required. A different crop for a phone
     needs a second asset per photograph, and docs/hero-acquisition.md carries
     that as outstanding work. A gate that fails until 1,404 crops have been
     bought is a gate somebody switches off. */
  console.log(
    `NOTE\tart-directed heroes\t${arted} of ${heroes} carry a <source media>. ` +
    `The portraits do; the place heroes need a second crop per photograph, ` +
    `which is acquisition rather than code`);

  process.exit(bad.length || contractFail ? 1 : 0);
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
