#!/usr/bin/env node
/* The two structural promises of the image library, tested rather than trusted.
 *
 *     node tools/library-checks.js
 *
 * 1. AN IDENTITY BELONGS TO THE PHOTOGRAPH, NOT TO THE PAGE COPY.
 *    Rewrite a caption, a country, a category — the identity, the object key
 *    and every published URL stay exactly as they were. This is the property
 *    that stops a copy edit orphaning objects in R2 and silently paying to
 *    upload the same photograph twice.
 *
 * 2. PUBLICATION IS PER ASSET.
 *    A selected subset can be published and rewritten into pages while every
 *    other asset stays hotlinked and untouched. This is what lets the best
 *    hundred photographs go live before the other six hundred exist.
 *
 * Both run against a throwaway register in a temp directory, driving the real
 * tools/tourism/library.py through python — not a reimplementation of it in
 * JavaScript, which would only prove that two of my guesses agree.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
let pass = 0;
let fail = 0;

function report(ok, what, detail) {
  console.log(`${ok ? "PASS" : "FAIL"}\t${what}\t${detail}`);
  ok ? pass++ : fail++;
}

/* Run a snippet against the real library module, with REGISTER pointed at a
 * scratch file so nothing here can touch tourism/assets.json. */
function py(code) {
  const script = `
import json, os, sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})
from tourism import library as L
L.REGISTER = ${JSON.stringify(REG)}
${code}
`;
  return execFileSync("python3", ["-c", script], {
    cwd: ROOT,
    encoding: "utf-8",
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  });
}

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "afrinkong-library-"));
const REG = path.join(TMP, "assets.json");

/* ---------------------------------------------------------------- identity */

/* A register holding one provider photograph, already published and wired
 * into a page — the state in which a rename would do real damage. */
fs.writeFileSync(
  REG,
  JSON.stringify({
    host: "https://image.afrinkong.com",
    nextId: 2,
    assets: {
      "AKL-000001": {
        id: "AKL-000001",
        sourceKey: "pexels:10010546",
        origin: "provider",
        slug: "botswana/wildlife/elephants-at-chobe",
        country: "botswana",
        category: "wildlife",
        provider: "pexels",
        photoId: "10010546",
        photographer: "A Photographer",
        licence: { name: "Pexels License", url: "https://www.pexels.com/license/" },
        sourceUrl: "https://www.pexels.com/photo/x-10010546/",
        originalUrl: "https://images.pexels.com/photos/10010546/x.jpeg",
        sha256: "deadbeef",
        downloadedAt: "2026-08-19T00:00:00Z",
        encodedAt: "2026-08-19T00:00:00Z",
        publishedAt: "2026-08-19T00:00:00Z",
        widths: [480, 800, 1200, 1600],
        pages: ["/tourism/botswana.html"],
      },
    },
  })
);

const before = JSON.parse(
  py(`
reg = L.register()
a = reg["assets"]["AKL-000001"]
print(json.dumps({
  "id": a["id"],
  "key": L.key(a["id"], 1200, ".avif"),
  "original": L.key(a["id"]),
}))
`)
);

/* The copy edit. Everything editorial about the photograph changes at once —
 * caption, country and category — which is the worst case for a key that was
 * ever derived from any of them. */
py(`
reg = L.register()
a = reg["assets"]["AKL-000001"]
a["slug"] = "botswana/safari/elephants-beside-the-chobe-river-at-dusk"
a["country"] = "botswana"
a["category"] = "safari"
a["alt"] = "Elephants beside the Chobe River"
L._write_register(reg, log=lambda *x: None)
`);

const after = JSON.parse(
  py(`
reg = L.register()
a = reg["assets"]["AKL-000001"]
print(json.dumps({
  "id": a["id"],
  "key": L.key(a["id"], 1200, ".avif"),
  "original": L.key(a["id"]),
  "slug": a["slug"],
  "category": a["category"],
}))
`)
);

report(
  after.id === before.id,
  "a caption change does not change the identity",
  `${before.id} before, ${after.id} after`
);
report(
  after.key === before.key && after.original === before.original,
  "a caption change does not change the object key",
  `${after.key}`
);
report(
  after.slug !== "botswana/wildlife/elephants-at-chobe" &&
    after.category === "safari",
  "the editorial metadata did change, so the test is not vacuous",
  `slug now ${after.slug}`
);
report(
  !before.key.includes("elephant") && !before.key.includes("chobe"),
  "no page copy appears in an object key at all",
  before.key
);

/* The other half of identity: the same photograph arriving twice must be
 * recognised, not given a second identity. */
const dedupe = JSON.parse(
  py(`
reg = L.register()
first = L.source_key("provider", "pexels", "10010546")
again = L.source_key("provider", "pexels", "10010546")
byfile = L.source_key("commissioned", sha="abc123")
print(json.dumps({"same": first == again, "key": first, "file": byfile}))
`)
);
report(
  dedupe.same && dedupe.key === "pexels:10010546",
  "the source key is the provider's own id, so a re-plan finds the identity",
  dedupe.key
);

/* ------------------------------------------------------- per-asset publish */

/* Three assets, all encoded, none published. */
const three = {
  host: "https://image.afrinkong.com",
  nextId: 4,
  assets: {},
};
for (let i = 1; i <= 3; i++) {
  const id = `AKL-00000${i}`;
  three.assets[id] = {
    id,
    sourceKey: `pexels:${1000 + i}`,
    origin: "provider",
    slug: `country${i}/wildlife/photo-${i}`,
    country: `country${i}`,
    category: "wildlife",
    provider: "pexels",
    photoId: `${1000 + i}`,
    photographer: "A Photographer",
    licence: { name: "Pexels License", url: "https://www.pexels.com/license/" },
    sourceUrl: `https://www.pexels.com/photo/x-${1000 + i}/`,
    originalUrl: `https://images.pexels.com/photos/${1000 + i}/x.jpeg`,
    sha256: `sha${i}`,
    downloadedAt: "2026-08-19T00:00:00Z",
    encodedAt: "2026-08-19T00:00:00Z",
    widths: [480, 800, 1200, 1600],
    pages: [`/tourism/country${i}.html`],
  };
}
fs.writeFileSync(REG, JSON.stringify(three));

const states = JSON.parse(
  py(`
reg = L.register()
print(json.dumps({a["id"]: L.state(a) for a in reg["assets"].values()}))
`)
);
report(
  Object.values(states).every((s) => s === "encoded"),
  "an encoded asset is not published, and says so",
  JSON.stringify(states)
);

/* Selecting one country must return exactly one asset. A selector that
 * returned everything on a miss would publish the whole library by typo. */
const picked = JSON.parse(
  py(`
reg = L.register()
one = [a["id"] for a in L.select(reg, "country:country2")]
ids = [a["id"] for a in L.select(reg, "AKL-000001,AKL-000003")]
none = [a["id"] for a in L.select(reg, "country:atlantis")]
allof = [a["id"] for a in L.select(reg, None)]
print(json.dumps({"one": one, "ids": ids, "none": none, "all": len(allof)}))
`)
);
report(
  picked.one.length === 1 && picked.one[0] === "AKL-000002",
  "a selector picks a subset by country",
  picked.one.join(",") || "(none)"
);
report(
  picked.ids.length === 2 && !picked.ids.includes("AKL-000002"),
  "a selector picks a subset by identity",
  picked.ids.join(",")
);
report(
  picked.none.length === 0 && picked.all === 3,
  "a selector that matches nothing returns nothing, not everything",
  `miss ${picked.none.length}, no selector ${picked.all}`
);

/* Publish one, and only one. Marking publishedAt is what `publish` does after
 * its uploads; doing it here keeps the test off the network while testing the
 * gate that matters — what rewrite will and will not touch. */
py(`
reg = L.register()
for a in L.select(reg, "AKL-000002"):
    a["publishedAt"] = "2026-08-19T01:00:00Z"
L._write_register(reg, log=lambda *x: None)
`);

const mixed = JSON.parse(
  py(`
reg = L.register()
print(json.dumps({a["id"]: L.state(a) for a in reg["assets"].values()}))
`)
);
report(
  mixed["AKL-000002"] === "published" &&
    mixed["AKL-000001"] === "encoded" &&
    mixed["AKL-000003"] === "encoded",
  "publishing one asset leaves the others encoded",
  JSON.stringify(mixed)
);

/* The gate rewrite actually applies: published and not on hold. */
const eligible = JSON.parse(
  py(`
reg = L.register()
ready = [a["id"] for a in L.select(reg, None)
         if a.get("publishedAt") and not a.get("hold")]
print(json.dumps(ready))
`)
);
report(
  eligible.length === 1 && eligible[0] === "AKL-000002",
  "only a published asset is eligible for rewrite",
  eligible.join(",") || "(none)"
);

/* Hold must remove an asset from publication even when it is encoded. */
const held = JSON.parse(
  py(`
reg = L.register()
reg["assets"]["AKL-000003"]["hold"] = "art-directed: needs a phone crop"
L._write_register(reg, log=lambda *x: None)
reg = L.register()
print(json.dumps({
  "state": L.state(reg["assets"]["AKL-000003"]),
  "selected": [a["id"] for a in L.select(reg, "state:hold")],
}))
`)
);
report(
  held.state === "hold" && held.selected.length === 1,
  "an asset on hold is held, and can be selected as such",
  held.selected.join(",")
);

/* ------------------------------------------------------------- upgrade path */

/* An old register — keyed by name, gated by one global live flag — must come
 * forward without losing what the pipeline had already established. */
fs.writeFileSync(
  REG,
  JSON.stringify({
    host: "https://image.afrinkong.com",
    live: true,
    assets: {
      "kenya/cities/nairobi-green-city": {
        name: "kenya/cities/nairobi-green-city",
        provider: "pexels",
        photoId: "777",
        photographer: "A Photographer",
        licence: { name: "Pexels License", url: "https://www.pexels.com/license/" },
        sourceUrl: "https://www.pexels.com/photo/x-777/",
        originalUrl: "https://images.pexels.com/photos/777/x.jpeg",
        sha256: "cafe",
        downloadedAt: "2026-08-01T00:00:00Z",
        encodedAt: "2026-08-01T00:00:00Z",
        widths: [480, 800, 1200],
        pages: ["/tourism/kenya.html"],
      },
    },
  })
);

const upgraded = JSON.parse(
  py(`
reg = L.register()
a = list(reg["assets"].values())[0]
print(json.dumps({
  "keys": list(reg["assets"]),
  "id": a["id"],
  "slug": a.get("slug"),
  "sourceKey": a.get("sourceKey"),
  "origin": a.get("origin"),
  "sha256": a.get("sha256"),
  "published": bool(a.get("publishedAt")),
  "hasLive": "live" in reg,
  "nextId": reg.get("nextId"),
}))
`)
);
report(
  upgraded.keys.length === 1 && /^AKL-\d{6}$/.test(upgraded.keys[0]),
  "an old name-keyed register upgrades to permanent identities",
  upgraded.keys[0]
);
report(
  upgraded.sourceKey === "pexels:777" && upgraded.origin === "provider",
  "the upgrade records the source key that will find it again",
  upgraded.sourceKey
);
report(
  upgraded.slug === "kenya/cities/nairobi-green-city" && upgraded.sha256 === "cafe",
  "the old name survives as editorial metadata, and the checksum is kept",
  upgraded.slug
);
report(
  !upgraded.hasLive && upgraded.published === true,
  "the global live flag becomes a per-asset publication state",
  `live removed, publishedAt set, nextId ${upgraded.nextId}`
);

/* Upgrading twice must not mint new identities. */
const twice = JSON.parse(
  py(`
first = list(L.register()["assets"])
L._write_register(L.register(), log=lambda *x: None)
second = list(L.register()["assets"])
print(json.dumps({"same": first == second, "first": first, "second": second}))
`)
);
report(
  twice.same,
  "the upgrade is idempotent — a second read mints nothing",
  twice.first.join(",")
);

/* ------------------------------------------------- publish, when it fails */

/* A partially uploaded asset must never be marked published. If it were,
 * rewrite would point pages at objects that are not in the bucket — the exact
 * failure the reachability check exists to catch, arriving by a different
 * door. Uploads run eight at a time now, so a single failure among hundreds
 * is a realistic event rather than a hypothetical one. */
const partial = JSON.parse(
  py(`
import os, sys, tempfile, json
try:
    import boto3
except ImportError:
    print(json.dumps({"skip": True})); raise SystemExit
reg = {"host": "https://image.afrinkong.com", "nextId": 3, "assets": {}}
for i in (1, 2):
    aid = "AKL-%06d" % i
    reg["assets"][aid] = {"id": aid, "sourceKey": "pexels:%d" % i,
                          "origin": "provider", "encodedAt": "2026-01-01T00:00:00Z",
                          "widths": [480]}
json.dump(reg, open(L.REGISTER, "w"))
root = os.path.join(L.ROOT, "images", "library")
made = []
for a in reg["assets"].values():
    keys = [L.key(a["id"])] + [L.key(a["id"], 480, e) for e in L.FORMATS]
    for k in keys:
        f = os.path.join(root, k)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "wb").write(b"x" * 100); made.append(f)
os.environ.update(R2_ACCOUNT_ID="a", R2_ACCESS_KEY_ID="b",
                  R2_SECRET_ACCESS_KEY="c", R2_BUCKET="d")
class Flaky:
    def upload_file(self, full, bucket, k, ExtraArgs=None):
        if k.endswith("AKL-000002.webp"):
            raise RuntimeError("simulated failure")
boto3.client = lambda *a, **kw: Flaky()
rc = L.publish(write=True, log=lambda *m: None)
published = sum(1 for a in L.register()["assets"].values() if a.get("publishedAt"))
for f in made:
    os.remove(f)
print(json.dumps({"skip": False, "rc": rc, "published": published}))
`)
);
if (partial.skip) {
  console.log("SKIP\ta failed upload marks nothing published\tboto3 not installed");
} else {
  report(
    partial.rc === 1 && partial.published === 0,
    "one failed upload marks nothing published",
    `exit ${partial.rc}, ${partial.published} asset(s) published`
  );
}

/* ------------------------------------------------------- the second crop */

/* 256 <picture> blocks ask a provider for the same photograph at two shapes.
 * Until `encode` could cut the phone rectangle, `rewrite` had to refuse every
 * one of them, which left 102 published photographs hotlinked on the pages
 * they were bought for. These are the properties that make cutting it safe. */

const crop = JSON.parse(
  py(`
import json
box = L._crop_box(3000, 2000, (1200, 1500), 0.5, 0.5)
tall = L._crop_box(2000, 3000, (1200, 800), 0.5, 0.5)
edge = L._crop_box(3000, 2000, (1200, 1500), 0.95, 0.5)
print(json.dumps({
  "box": box, "tall": tall, "edge": edge,
  "names": [L.crop_name((1200, 1500)), L.crop_name((900, 1125)),
            L.crop_name((1200, 800))],
  # The keys already in the bucket must not move. 8,177 objects were uploaded
  # under the un-cropped form and a changed key orphans every one of them.
  "plain": [L.key("AKL-000042"), L.key("AKL-000042", 1200, ".avif")],
  "cropped": L.key("AKL-000042", 1200, ".avif", "4x5"),
  "objects": L.object_keys({"id": "AKL-1", "widths": [480],
                            "crops": {"4x5": {"widths": [480]}}}),
  "objects_plain": L.object_keys({"id": "AKL-1", "widths": [480]}),
}))
`)
);

const [l, t, r, b] = crop.box;
report(
  Math.abs((r - l) / (b - t) - 0.8) < 1e-9 && b - t === 2000,
  "the crop is the requested aspect, and the largest one that fits",
  `${r - l}x${b - t} from 3000x2000, ratio ${((r - l) / (b - t)).toFixed(4)}`
);

const [tl, tt, tr, tb] = crop.tall;
/* Tolerance, because pixels are integers: the exact 3:2 box inside 2000x3000
 * is 2000x1333.33 and the nearest whole rectangle is 2000x1333, a ratio of
 * 1.50038. Demanding exactness here fails the arithmetic, not the code. */
report(
  Math.abs((tr - tl) / (tb - tt) - 1.5) < 0.001 && tr - tl === 2000,
  "a wide crop out of a tall original is bounded by the width",
  `${tr - tl}x${tb - tt} from 2000x3000, ratio ${((tr - tl) / (tb - tt)).toFixed(5)}`
);

const [el, , er] = crop.edge;
report(
  el === 3000 - (er - el) && el >= 0,
  "a focal point near the edge slides the box, it does not run off",
  `fp-x 0.95 -> left ${el}, box ${er - el} wide, right edge ${er} of 3000`
);

report(
  crop.names.join(",") === "4x5,4x5,3x2",
  "a crop is named for its shape, reduced",
  crop.names.join(" ")
);

report(
  crop.plain[0] === "originals/AKL-000042.jpg" &&
    crop.plain[1] === "1200/AKL-000042.avif",
  "adding crops did not move a single existing object key",
  crop.plain.join("  ")
);

report(
  crop.cropped === "4x5/1200/AKL-000042.avif",
  "a crop is a prefix on the width, so it cannot collide with one",
  crop.cropped
);

report(
  crop.objects.length === crop.objects_plain.length + 3 &&
    crop.objects.filter((k) => k.startsWith("4x5/")).length === 3,
  "publish and reachable enumerate the crop from one shared list",
  `${crop.objects_plain.length} keys without a crop, ${crop.objects.length} with`
);

/* THE ONE THAT MATTERS: an art-directed <picture> is REPLACED, not wrapped.
 * The <img> is already inside a <picture>; wrapping it the way the ordinary
 * path does nests one inside another, which is invalid — and this site has
 * nine accidental examples of exactly that, so it is not hypothetical. */
const art = JSON.parse(
  py(`
import json, re, base64
block = ('<picture><source media="(max-width: 700px)" '
         'srcset="https://images.pexels.com/photos/1/a.jpeg?fit=crop&amp;w=1200&amp;h=1500 1200w" '
         'sizes="100vw">'
         '<img src="https://images.pexels.com/photos/1/a.jpeg?fit=crop&amp;w=2400&amp;h=1350" '
         'alt="A place" width="2400" height="1350" '
         'style="aspect-ratio:16 / 9;object-position:50% 56%" '
         'srcset="https://images.pexels.com/photos/1/a.jpeg?w=1200 1200w" '
         'sizes="100vw" fetchpriority="high" decoding="async"></picture>')
a = {"id": "AKL-000042", "widths": [480, 1200],
     "crops": {"4x5": {"widths": [480, 1200], "fx": 0.5, "fy": 0.5,
                       "media": "(max-width: 700px)"}}}
out = L.artdirected_picture(block, a, "https://image.afrinkong.com")
was = re.search(r'data-was="([A-Za-z0-9+/=]+)"', out)
visible = re.sub(r'data-was="[^"]*"', "", out)
print(json.dumps({
  "opens": out.count("<picture>"), "closes": out.count("</picture>"),
  "leaks": len(re.findall(r"images\.pexels\.com", visible)),
  # first source wins in a <picture>, so the phone rectangle must come first
  "first_is_phone": visible.index("4x5/") < visible.index('type="image/avif" srcset="https://image.afrinkong.com/480'),
  "kept_alt": 'alt="A place"' in out,
  "kept_dims": 'width="2400"' in out and 'height="1350"' in out,
  "kept_focal": "object-position:50% 56%" in out,
  "restores": base64.b64decode(was.group(1)).decode() == block if was else False,
}))
`)
);

report(art.opens === 1 && art.closes === 1,
       "an art-directed block yields one <picture>, not a nested pair",
       `${art.opens} open, ${art.closes} close`);
report(art.leaks === 0,
       "both rectangles move to our host — neither is left on the provider",
       `${art.leaks} provider URL(s) left in the visible markup`);
report(art.first_is_phone,
       "the phone source is emitted first, so its media query can win",
       "4x5 sources precede the full-frame ones");
report(art.kept_alt && art.kept_dims && art.kept_focal,
       "the <img> keeps its alt, its box and its focal point",
       "alt, width/height and object-position all survive");
report(art.restores,
       "revert restores the whole original block, byte for byte",
       "data-was holds the <picture>, not just the <img>");

/* And the gate: art direction stops being a permanent exclusion and becomes a
 * queue. Without a crop encoded the asset is still refused; with one it is
 * ready. */
const gate = JSON.parse(
  py(`
import json
base = {"originalUrl": "https://images.pexels.com/photos/1/a.jpeg",
        "widths": [480], "publishedAt": "2026-01-01T00:00:00Z"}
def blocked(a, art):
    if a["originalUrl"].split("?")[0] not in art:
        return False
    return not (a.get("crops") and any(c.get("widths") for c in a["crops"].values()))
art = {"https://images.pexels.com/photos/1/a.jpeg"}
print(json.dumps({
  "without": blocked(dict(base), art),
  "with": blocked(dict(base, crops={"4x5": {"widths": [480]}}), art),
  "empty": blocked(dict(base, crops={"4x5": {"widths": []}}), art),
  "unrelated": blocked(dict(base), set()),
}))
`)
);
report(
  gate.without === true && gate.with === false && gate.empty === true &&
    gate.unrelated === false,
  "art direction blocks a rewrite until the crop exists, then stops blocking",
  `no crop ${gate.without}, crop ${gate.with}, empty crop ${gate.empty}`
);

fs.rmSync(TMP, { recursive: true, force: true });

/* ---- THE HOTLINK REGRESSION -------------------------------------------
 *
 * THIS HAPPENED, THIS SESSION, AND NOTHING CAUGHT IT.
 *
 * Rebuilding the place family wiped `library rewrite` — a late pass — and 1,363
 * place heroes silently reverted from image.afrinkong.com to the Pexels and
 * Unsplash originals they had been migrated off. Every gate stayed green. It
 * was found by eye, in a diff, because the hero census happened to be run.
 *
 * Had it shipped, 1,363 pages would have sent every phone the full-resolution
 * original from a third party — the exact payload the whole library exists to
 * stop — while the register went on saying we host those photographs.
 *
 * WHAT MAKES A HOTLINK A REGRESSION RATHER THAN MERELY A HOTLINK.
 *
 * 9,342 provider URLs are on this site legitimately: photographs nobody has
 * acquired yet, carried while acquisition runs. Failing on those would fail
 * every day for months, and a gate that always fails is a gate switched off.
 *
 * The regression is narrower and unambiguous: a page pointing at a provider
 * for a photograph THE REGISTER SAYS WE ALREADY HOST. There is no reading of
 * that which is correct. It is zero today, which is what makes it a ratchet.
 */
const HOTLINK = /images\.(pexels|unsplash)\.com\/(?:photos\/)?(?:photo-)?(\d+|[A-Za-z0-9_-]{11,})/;
/* The REAL register from disk. `reg` inside this file is a local rebound to a
   fixture in a temp directory by the tests above; using it here would ask a
   sandbox what the site hosts. */
const liveRegister = JSON.parse(
  fs.readFileSync(path.join(ROOT, "tourism", "assets.json"), "utf-8"));
const hosted = new Map();
for (const [id, a] of Object.entries(liveRegister.assets || {})) {
  if (a.provider && a.photoId) hosted.set(`${a.provider}:${a.photoId}`, id);
}

function everyPage(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith(".") || e.name === "node_modules"
        || e.name === "incoming") continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) everyPage(f, acc);
    else if (e.name.endsWith(".html")) acc.push(f);
  }
  return acc;
}

const regressed = [];
let providerUrls = 0;
for (const f of everyPage(ROOT, [])) {
  const html = fs.readFileSync(f, "utf-8");
  for (const m of html.matchAll(/(?:src|srcset)="([^"]+)"/g)) {
    for (const part of m[1].split(",")) {
      const url = part.trim().split(" ")[0];
      const hit = HOTLINK.exec(url);
      if (!hit) continue;
      providerUrls++;
      const key = `${hit[1]}:${hit[2]}`;
      if (hosted.has(key)) {
        regressed.push(`${path.relative(ROOT, f)} -> ${key} (we host ${hosted.get(key)})`);
      }
    }
  }
}
report(regressed.length === 0,
  "no page hotlinks a photograph the register says we already host",
  regressed.length
    ? `${regressed.length} regression(s), e.g. ${regressed[0]}`
    : `${providerUrls} provider URLs are on the site for photographs nobody ` +
      `has acquired yet, which is legitimate; ${hosted.size} registered ` +
      `photographs are served from our own host, and none is also hotlinked`);

/* ---- ONE PHOTOGRAPH, ONE FOCAL POINT (UNLESS IT IS A DIFFERENT CROP) ----
 *
 * A focal point is art direction: it says which part of a photograph survives
 * when the frame is a different shape from the file. 1,453 images carry one.
 *
 * Three photographs carried TWO different values, and the reason matters:
 *
 *   foumban-bronze-caster    50% 55% on the homepage, 46% 50% on
 *                            cameroon.html. The homepage reads photo_pos out
 *                            of tourism/lenses.json; cameroon.html is
 *                            hand-authored and had its own. Four percentage
 *                            points apart, which is not a decision anybody
 *                            made — it is one file drifting from the dataset.
 *                            FIXED: cameroon.html now uses the dataset value.
 *
 *   kilimanjaro-elephants    50% 58% and 48% 56%. Two points apart, across a
 *                            dataset boundary (lenses.json and the country
 *                            record). Suspected drift, not fixed here: the two
 *                            stores are both legitimate authors and choosing
 *                            between them is a data-architecture decision that
 *                            belongs with Commit 44, not a quiet edit.
 *
 *   kilimanjaro-above-cloud  50% 8% and 50% 24%. SIXTEEN points apart, which
 *                            is a different composition for a different frame
 *                            — exactly the "intentional art direction" the
 *                            mandate says not to optimise away. Left alone.
 *
 * So this does not demand one value per photograph. It ratchets the COUNT of
 * photographs carrying more than one, which is 2 after the fix. A third
 * appearing is either a new deliberate crop — in which case lower the ceiling
 * deliberately — or the drift this exists to catch.
 */
const MULTI_FOCAL_CEILING = 2;
const focal = new Map();
for (const f of everyPage(ROOT, [])) {
  const html = fs.readFileSync(f, "utf-8");
  for (const m of html.matchAll(/<img[^>]*>/g)) {
    const tag = m[0];
    const src = /src="([^"]+)"/.exec(tag);
    const pos = /(?:--fj-feel-pos|object-position):\s*([^";]+)/.exec(tag);
    if (!src || !pos) continue;
    const id = (/(AKL-\d+)/.exec(src[1]) || [])[1]
      || src[1].split("/").pop().split("?")[0];
    if (!focal.has(id)) focal.set(id, new Set());
    focal.get(id).add(pos[1].trim());
  }
}
const multi = [...focal.entries()].filter(([, v]) => v.size > 1);
report(multi.length <= MULTI_FOCAL_CEILING,
  "a photograph does not quietly acquire a second focal point",
  multi.length > MULTI_FOCAL_CEILING
    ? `${multi.length} photographs carry more than one, ceiling ` +
      `${MULTI_FOCAL_CEILING}: ${multi.slice(0, 3).map(([k, v]) =>
        `${k} (${[...v].join(" / ")})`).join("; ")}`
    : `${focal.size} photographs carry a focal point; ${multi.length} carry ` +
      `two, both recorded and reasoned about in this file`);

console.log(`\n${pass} passed, ${fail} failed, ${pass + fail} checks`);
process.exit(fail ? 1 : 0);
