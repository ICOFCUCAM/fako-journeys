#!/usr/bin/env node
/* Before and after, on the pages PR #22 actually rewrote.
 *
 *     node tools/weigh.js                 # the default six
 *     node tools/weigh.js algeria.html …  # named pages
 *
 * WHY THIS EXISTS AND WHY IT IS NOT browser-checks.js
 *
 * The suite already measures first-screen weight, but on four fixed pages —
 * index, trans-afrique, cameroon and one more — and none of those four is
 * among the seventy-six the rewrite touched. Their photography moved onto our
 * own files long ago. So the suite reported no change, correctly, and told us
 * nothing about whether first-party images are lighter than the hotlinks they
 * replaced. That question needs the pages that actually changed.
 *
 * WHAT "BEFORE" MEANS HERE
 *
 * The version of the same page at the commit before the rewrite, taken from
 * git rather than reconstructed. Both versions are served from a local static
 * server so the HTML itself is not the variable; what differs is where the
 * photographs come from — images.pexels.com and images.unsplash.com on one
 * side, image.afrinkong.com on the other.
 *
 * WHAT IS MEASURED
 *
 * Bytes actually transferred for image responses, and the count of them, at a
 * 390-wide phone viewport at 3x — the same viewport the budget checks use, and
 * the one that decides whether this site is usable on the device most of its
 * visitors will hold. Encoded bytes over the wire, not decoded size, because
 * the wire is what costs a visitor money.
 *
 * This needs the open internet. It cannot run in the development sandbox,
 * whose proxy refuses both providers and our own asset host, so it is a
 * workflow step — see .github/workflows/tourism-library.yml.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
/* The commit the rewrite landed in. Its parent is "before". */
const REWRITE = "c26c33a30f500fbd6cb386a193a84dec904b9cc3";

/* Six of the seventy-six, spread evenly across the four page shapes the
 * rewrite touched — 19 root country pages, 19 /tourism, 19 /portrait, 19
 * /places — so one unusual page cannot carry the result.
 *
 * These are checked against reality rather than assumed. The first list I
 * wrote included burundi.html, which was never rewritten: Burundi's culture
 * photograph is one of the six held back for a phone crop, so that page has
 * no first-party image on it at all and would have measured a change of
 * exactly zero while looking like a fair sample. */
const DEFAULT_PAGES = [
  "algeria.html",
  "angola.html",
  "tourism/algeria.html",
  "tourism/angola.html",
  "portrait/algeria.html",
  "places/algeria/a-thousand-kilometres-of-mediterranean.html",
];

function sh(cmd, args) {
  return execFileSync(cmd, args, { cwd: ROOT, encoding: "utf-8", maxBuffer: 1 << 28 });
}

/* One static server per tree, so a page loads its own stylesheets and scripts
 * exactly as it would in production. */
function serve(dir) {
  const server = http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split("?")[0]);
    if (p.endsWith("/")) p += "index.html";
    const file = path.join(dir, p);
    if (!file.startsWith(dir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404).end("not found");
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const type = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript",
                   ".json": "application/json", ".svg": "image/svg+xml",
                   ".woff2": "font/woff2", ".jpg": "image/jpeg", ".png": "image/png",
                   ".avif": "image/avif", ".webp": "image/webp" }[ext] || "application/octet-stream";
    res.writeHead(200, { "content-type": type });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

async function weigh(browser, url) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) " +
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
  });
  const page = await ctx.newPage();
  let bytes = 0, count = 0, failed = 0;
  const hosts = {};
  page.on("response", async (r) => {
    const type = (r.headers()["content-type"] || "");
    if (!type.startsWith("image/")) return;
    count++;
    if (!r.ok()) { failed++; return; }
    const len = Number(r.headers()["content-length"] || 0);
    let n = len;
    if (!n) { try { n = (await r.body()).length; } catch { n = 0; } }
    bytes += n;
    const h = new URL(r.url()).host;
    hosts[h] = (hosts[h] || 0) + n;
  });
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  } catch { /* a slow provider is still a measurement */ }
  await ctx.close();
  return { bytes, count, failed, hosts };
}

(async () => {
  const pages = process.argv.slice(2).length ? process.argv.slice(2) : DEFAULT_PAGES;
  /* The same resolution browser-checks.js uses: playwright-core lives in the
     image, not in the repository, so it is found rather than depended on. */
  const chromium = (() => {
    const roots = ["/opt/node22/lib/node_modules/playwright/node_modules/playwright-core",
                   "playwright-core", "playwright"];
    /* A globally installed playwright is not on node's resolution path for a
       script inside this repository, which is exactly how the first CI run
       failed: 115 MB of browser downloaded, then nothing measured. Ask npm
       where global packages live and look there too. */
    try {
      const g = execFileSync("npm", ["root", "-g"], { encoding: "utf-8" }).trim();
      if (g) roots.push(path.join(g, "playwright"), path.join(g, "playwright-core"));
    } catch (e) { /* no npm, no global root */ }
    for (const r of roots) {
      try { return require(r).chromium; } catch (e) { /* next */ }
    }
    return null;
  })();
  if (!chromium) {
    console.log("no playwright — nothing measured. A check that cannot run "
                + "must say so rather than pass.");
    process.exit(1);
  }
  const exe = (() => {
    const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
    let names = [];
    try { names = fs.readdirSync(base); } catch (e) { return null; }
    for (const d of names.filter(n => n.indexOf("chromium") === 0).sort().reverse()) {
      for (const rel of ["chrome-linux/headless_shell", "chrome-linux/chrome"]) {
        const full = path.join(base, d, rel);
        if (fs.existsSync(full)) return full;
      }
    }
    return fs.existsSync(path.join(base, "chromium")) ? path.join(base, "chromium") : null;
  })();

  /* "before" = the same tree at the rewrite's parent commit. */
  const before = fs.mkdtempSync(path.join(os.tmpdir(), "weigh-before-"));
  sh("git", ["worktree", "add", "-q", "--detach", before, `${REWRITE}^`]);

  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  const [sBefore, sAfter] = [await serve(before), await serve(ROOT)];
  const pBefore = sBefore.address().port, pAfter = sAfter.address().port;

  console.log("page                       before        after      change   requests");
  console.log("-".repeat(76));
  let tb = 0, ta = 0;
  for (const p of pages) {
    const b = await weigh(browser, `http://127.0.0.1:${pBefore}/${p}`);
    const a = await weigh(browser, `http://127.0.0.1:${pAfter}/${p}`);
    tb += b.bytes; ta += a.bytes;
    const pct = b.bytes ? ((a.bytes - b.bytes) / b.bytes) * 100 : 0;
    console.log(
      "%s %s %s %s %s",
      p.replace(".html", "").padEnd(24),
      `${(b.bytes / 1e6).toFixed(2)} MB`.padStart(10),
      `${(a.bytes / 1e6).toFixed(2)} MB`.padStart(12),
      `${pct >= 0 ? "+" : ""}${pct.toFixed(0)}%`.padStart(11),
      `${b.count} → ${a.count}${a.failed ? ` (${a.failed} failed)` : ""}`.padStart(12)
    );
    for (const [h, n] of Object.entries(a.hosts)) {
      console.log("    after, from %s: %s MB", h, (n / 1e6).toFixed(2));
    }
  }
  console.log("-".repeat(76));
  const pct = tb ? ((ta - tb) / tb) * 100 : 0;
  console.log("total %s MB before, %s MB after, %s%s%%",
    (tb / 1e6).toFixed(2), (ta / 1e6).toFixed(2), pct >= 0 ? "+" : "", pct.toFixed(0));

  await browser.close();
  sBefore.close(); sAfter.close();
  sh("git", ["worktree", "remove", "--force", before]);
})();
