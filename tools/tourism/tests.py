#!/usr/bin/env python3
"""Test suite for the tourism image system.

    python3 tools/tourism/build.py test
    npm run tourism:test

Runs entirely against a local mock of the Unsplash API, so CI needs no key and
makes no network calls. The mock speaks the shape of GET /search/photos and
serves real bytes, so the whole path is exercised: search, parsing, suitability,
de-duplication, delivery-URL construction, HTTP verification, caching,
resumability and render.

Every test works on a temp copy of the cache. tourism/cache/unsplash.json and
tourism/countries/ are never written.
"""

import http.server
import json
import os
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

PORT = 8791
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 4000 + b"\xff\xd9"

RESULTS = []          # assertion log
API_CALLS = []        # every request the mock received


class MockUnsplash(http.server.BaseHTTPRequestHandler):
    """Enough of api.unsplash.com and images.unsplash.com to be worth testing against."""

    fail_search = False

    def log_message(self, *a):
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(url.query)
        API_CALLS.append(url.path)

        if url.path == "/photos/random":
            if not self.headers.get("Authorization", "").startswith("Client-ID "):
                return self._json({"errors": ["OAuth error"]}, 401)
            return self._json([{"id": "preflight"}])

        if url.path == "/search/photos":
            if MockUnsplash.fail_search:
                return self._json({"errors": ["boom"]}, 500)
            query = (qs.get("query") or [""])[0]
            portrait = (qs.get("orientation") or ["landscape"])[0] == "portrait"
            key = abs(hash(query)) % 10 ** 8
            return self._json({"results": [
                {   # too small — must be rejected before it is ever fetched
                    "id": "small-%d" % key, "width": 900, "height": 600,
                    "urls": {"raw": "http://localhost:%d/photo-small-%d" % (PORT, key)},
                    "user": {"name": "Too Small", "links": {"html": "https://example.invalid/u"}},
                    "links": {"html": "https://example.invalid/p",
                              "download_location": "http://localhost:%d/download/s" % PORT},
                },
                {
                    "id": "real-%d" % key,
                    "width": 2400 if portrait else 3000,
                    "height": 3200 if portrait else 2000,
                    "urls": {"raw": "http://localhost:%d/photo-%d?ixlib=rb-4.0.3" % (PORT, key),
                             "full": "http://localhost:%d/photo-full-%d" % (PORT, key)},
                    "user": {"name": "Ada Photographer",
                             "links": {"html": "https://example.invalid/@ada"}},
                    "links": {"html": "https://example.invalid/photos/%d" % key,
                              "download_location": "http://localhost:%d/download/%d" % (PORT, key)},
                },
            ]})

        if url.path.startswith("/download/"):
            return self._json({"url": "ok"})

        if url.path.startswith("/photo-small-"):
            API_CALLS.append("UNEXPECTED-FETCH")
            return self._json({"error": "should never be fetched"}, 500)

        if url.path.startswith("/photo-"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(JPEG)))
            self.end_headers()
            self.wfile.write(JPEG)
            return

        self._json({"error": "not found"}, 404)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("  %-52s %s%s" % (name, "PASS" if ok else "FAIL", "  " + detail if detail else ""))


def resolve_all(tax, countries, cache, key, cats=None):
    from tourism import resolve
    seen = set(cache.photo_ids())
    filled, failed = 0, []
    for c in countries:
        for cat in (cats or tax.enabled):
            entry = c.entry(cat["id"])
            if not entry or cache.has(c.slug, cat["id"]):
                continue
            rec, err = resolve.resolve_entry(c, cat, entry, tax.role(cat["id"]), key, seen)
            if rec:
                cache.put(c.slug, cat["id"], rec)
                entry.image = rec
                filled += 1
            else:
                failed.append((c.slug, cat["id"], err))
    return filled, failed


def main():
    os.environ["UNSPLASH_API_BASE"] = "http://localhost:%d" % PORT
    os.environ["UNSPLASH_IMAGE_HOST_OVERRIDE"] = "http://localhost:%d/" % PORT
    os.environ.pop("UNSPLASH_ACCESS_KEY", None)

    from tourism import cache as cache_mod
    from tourism import imaging, queries, resolve, validate
    from tourism.model import attach_cache, load_countries, load_taxonomy

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), MockUnsplash)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    tmp = tempfile.mkdtemp(prefix="tourism-tests-")

    try:
        tax = load_taxonomy()
        countries = load_countries()
        cameroon = [c for c in countries if c.slug == "cameroon"][0]

        # -- 1. missing API key fails safely ------------------------------------
        print("\n1. missing API key fails safely")
        try:
            resolve.preflight()
            check("preflight raises without a key", False)
        except resolve.Unavailable as exc:
            check("preflight raises without a key", True)
            check("error names the exact variable", "UNSPLASH_ACCESS_KEY" in str(exc))
            check("warning text is the specified string",
                  resolve.MISSING_KEY_WARNING ==
                  "Unsplash image resolution requires UNSPLASH_ACCESS_KEY.")
        cache_before = cache_mod.load()
        check("no cache entries written without a key", not cache_before.entries,
              "%d entries" % len(cache_before.entries))

        # -- 2. country-specific queries ----------------------------------------
        print("\n2. country-specific queries are generated correctly")
        q_cmr = queries.build(cameroon, tax.by_id["mountains"], cameroon.entry("mountains"))
        kenya = [c for c in countries if c.slug == "kenya"][0]
        q_ken = queries.build(kenya, tax.by_id["wildlife"], kenya.entry("wildlife"))
        check("query is prefixed with the country", q_cmr.startswith("Cameroon"), q_cmr[:44])
        check("query carries the country's own subject", "cameroon" in q_cmr.lower()
              and "mount" in q_cmr.lower())
        check("a different country gets a different query", q_cmr != q_ken, q_ken[:44])
        check("query includes the category hint", "wildlife" in q_ken)
        allq = {queries.build(c, cat, c.entry(cat["id"]))
                for c in countries for cat in tax.enabled if c.entry(cat["id"])}
        check("every one of the 189 queries is unique", len(allq) == 189, "%d unique" % len(allq))
        check("portrait categories search portrait orientation",
              queries.orientation("portrait") == "portrait"
              and queries.orientation("panoramic") == "landscape")

        # -- 3. valid API responses parse; ids and URLs come from the response ---
        print("\n3. API responses are parsed, ids and URLs come from the response")
        os.environ["UNSPLASH_ACCESS_KEY"] = "mock-key"
        key = resolve.preflight()
        cache = cache_mod.Cache(path=os.path.join(tmp, "unsplash.json"))
        hero_cat = tax.by_id["hero"]
        rec, err = resolve.resolve_entry(cameroon, hero_cat, cameroon.entry("hero"),
                                         tax.role("hero"), key, set())
        check("a record is returned", rec is not None, err or "")
        check("photoId is the id the API returned",
              rec["photoId"].startswith("real-"), rec["photoId"])
        check("imageUrl derives from urls.raw, query string stripped",
              rec["imageUrl"].startswith("http://localhost:%d/photo-" % PORT)
              and "?" not in rec["imageUrl"], rec["imageUrl"][-30:])
        check("photographer taken from user.name", rec["photographer"] == "Ada Photographer")
        check("photographerUrl taken from user.links.html",
              rec["photographerUrl"] == "https://example.invalid/@ada")
        check("unsplashUrl taken from links.html",
              rec["unsplashUrl"].startswith("https://example.invalid/photos/"))
        check("width/height taken from the response", rec["width"] == 3000 and rec["height"] == 2000)
        for field in ("photoId", "photographer", "photographerUrl", "unsplashUrl", "imageUrl",
                      "category", "country", "query", "alt", "width", "height", "focalPoint"):
            if field not in rec:
                check("schema field %s present" % field, False)
        check("stored schema matches the specification",
              all(f in rec for f in ("photoId", "photographer", "photographerUrl", "unsplashUrl",
                                     "imageUrl", "category", "country", "query", "alt",
                                     "width", "height", "focalPoint")))
        check("alt text is descriptive, not 'Cameroon image'",
              "Cameroon" in rec["alt"] and len(rec["alt"]) > 30, rec["alt"][:44])

        # -- 4. fake ids are never generated ------------------------------------
        print("\n4. photo ids are never fabricated")
        src = "".join(open(os.path.join(HERE, f)).read()
                      for f in ("resolve.py", "imaging.py", "cache.py"))
        check("no code path builds a photo- id from a template",
              not re.search(r'["\']photo-%[sd]', src) and not re.search(r'photo-\{', src))
        check("cdn_url refuses a source the API did not return",
              _refuses(imaging, tax.role("hero"), cameroon.entry("hero")))
        bad = dict(rec, imageUrl="https://cdn.example.com/photo-1")
        check("a foreign imageUrl cannot be delivered", _refuses_url(imaging, bad, tax, cameroon))

        # -- 5. all 27 categories resolve ---------------------------------------
        print("\n5. all 27 categories can be resolved")
        API_CALLS[:] = []
        filled, failed = resolve_all(tax, [cameroon], cache, key)
        check("27 of 27 slots resolved", filled == 27, "filled=%d failed=%s" % (filled, failed[:2]))
        check("undersized candidate was never fetched", "UNEXPECTED-FETCH" not in API_CALLS)
        check("every stored URL was fetched before caching",
              len([c for c in API_CALLS if c.startswith("/photo-")]) >= 27)
        check("download endpoint pinged per Unsplash guidelines",
              len([c for c in API_CALLS if c.startswith("/download/")]) >= 27)

        # -- 6. duplicates ------------------------------------------------------
        print("\n6. duplicate images are detected")
        check("resolver did not reuse a photo id",
              len(cache.photo_ids()) == 27, "%d unique ids" % len(cache.photo_ids()))
        check("cache reports no duplicates", cache.duplicates() == {})
        dup = cache_mod.Cache(path=os.path.join(tmp, "dup.json"))
        dup.put("cameroon", "wildlife", dict(rec, category="wildlife"))
        dup.put("kenya", "nature", dict(rec, category="nature", country="kenya"))
        check("cache detects a reused photo id", list(dup.duplicates()) == [rec["photoId"]])
        attach_cache([cameroon, kenya], dup)
        _, findings = validate.report([cameroon, kenya], tax)
        check("validator raises an error for the duplicate",
              any("duplicate image" in f.message for f in findings if f.level == "error"))
        attach_cache([cameroon, kenya], cache)

        # -- 7. cache prevents unnecessary requests -----------------------------
        print("\n7. the cache prevents unnecessary API requests")
        cache.save()
        API_CALLS[:] = []
        filled2, _ = resolve_all(tax, [cameroon], cache, key)
        check("a second run resolves nothing new", filled2 == 0)
        check("a second run makes zero API calls", API_CALLS == [], "%d calls" % len(API_CALLS))
        reread = cache_mod.load(cache.path)
        check("cache round-trips through the file", len(reread.entries) == 27)
        check("cached record keeps its real photo id",
              reread.get("cameroon", "hero")["photoId"] == rec["photoId"])
        partial = cache_mod.Cache(path=os.path.join(tmp, "partial.json"))
        for cat in tax.enabled[:10]:
            partial.put("cameroon", cat["id"], dict(rec, category=cat["id"],
                                                    photoId="seed-%s" % cat["id"]))
        API_CALLS[:] = []
        filled3, _ = resolve_all(tax, [cameroon], partial, key)
        check("resumable: only the 17 missing slots are requested", filled3 == 17,
              "resolved %d" % filled3)

        # -- 8. delivery --------------------------------------------------------
        print("\n8. delivery URLs are built from the verified URL")
        entry = cameroon.entry("hero")
        entry.image = reread.get("cameroon", "hero")
        url = imaging.cdn_url(entry.image["imageUrl"], tax.role("hero"), entry.focal)
        check("delivery URL starts with the verified image URL",
              url.startswith(entry.image["imageUrl"] + "?"))
        check("focal point reaches the CDN parameters",
              "crop=focalpoint" in url and "fp-x=0.520" in url and "fp-y=0.580" in url)
        check("hero delivered at 2400x1350 with quality",
              "w=2400" in url and "h=1350" in url and "q=" in url)
        ss = imaging.srcset(entry.image["imageUrl"], tax.role("hero"), entry.focal)
        check("srcset has one candidate per ladder step",
              ss.count(",") == len(tax.role("hero")["srcset"]) - 1)
        check("card role delivers 4:3, portrait role delivers 3:4",
              imaging.dimensions(tax.roles["card"])[0] > imaging.dimensions(tax.roles["card"])[1]
              and imaging.dimensions(tax.roles["portrait"])[0]
              < imaging.dimensions(tax.roles["portrait"])[1])

        # -- 9. the key never leaves the server ---------------------------------
        print("\n9. the access key never reaches a client")
        leaked = []
        for root, _, files in os.walk(os.path.dirname(os.path.dirname(HERE))):
            if "/.git" in root:
                continue
            for f in files:
                if not f.endswith((".html", ".json", ".js", ".css", ".md")):
                    continue
                path = os.path.join(root, f)
                try:
                    body = open(path, errors="ignore").read()
                except OSError:
                    continue
                if "mock-key" in body or re.search(r'UNSPLASH_ACCESS_KEY\s*[=:]\s*["\']?\S{8,}',
                                                   body):
                    leaked.append(os.path.relpath(path))
        check("no key value in any html/json/js/css/md artifact", not leaked, ", ".join(leaked[:3]))
        check("cache schema has no key field",
              "accessKey" not in cache_mod.FIELDS and "key" not in cache_mod.FIELDS)
        env_example = os.path.join(os.path.dirname(os.path.dirname(HERE)), ".env.example")
        if os.path.exists(env_example):
            body = open(env_example).read()
            check(".env.example declares the variable empty",
                  "UNSPLASH_ACCESS_KEY=" in body and
                  not re.search(r"UNSPLASH_ACCESS_KEY=\S", body))

        # -- 10. the rendered page uses the cached URL, responsively -------------
        print("\n10. the frontend renders the cached real URL")
        from tourism import render, verify as verify_mod
        attach_cache([cameroon], reread)
        outdir = os.path.join(tmp, "pages")
        render.write_all([cameroon], tax, {"cameroon"}, out_dir=outdir)
        page = open(os.path.join(outdir, "cameroon.html")).read()
        check("page carries no unresolved placeholders", 'data-unresolved' not in page)
        check("page uses the cached image URL",
              reread.get("cameroon", "hero")["imageUrl"] in page)
        check("page credits the photographer", "Ada Photographer" in page)
        check("page links back to Unsplash", "example.invalid/photos/" in page)
        problems = verify_mod.check_page(os.path.join(outdir, "cameroon.html"), tax)
        check("rendered page passes every structural check", not problems,
              "; ".join(problems[:2]))
        check("every remote image got a srcset", page.count("srcset=") >= 26,
              "%d srcsets" % page.count("srcset="))
        check("exactly one eager image, the hero",
              page.count("fetchpriority=\"high\"") == 1)
        check("no API key anywhere in the generated page",
              "mock-key" not in page and "UNSPLASH_ACCESS_KEY" not in page)

        # -- 11. failure handling ------------------------------------------------
        print("\n11. API failures are reported, not papered over")
        MockUnsplash.fail_search = True
        empty = cache_mod.Cache(path=os.path.join(tmp, "fail.json"))
        rec2, err2 = resolve.resolve_entry(cameroon, hero_cat, cameroon.entry("hero"),
                                           tax.role("hero"), key, set())
        MockUnsplash.fail_search = False
        check("a failed search returns an error, not a record", rec2 is None and bool(err2),
              (err2 or "")[:44])
        check("nothing is cached on failure", not empty.entries)

    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop("UNSPLASH_ACCESS_KEY", None)

    failed = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d passed, %d failed" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    if failed:
        for n in failed:
            print("  FAILED: %s" % n)
        return 1
    print("the resolver is ready for a real UNSPLASH_ACCESS_KEY")
    return 0


def _refuses(imaging, role, entry):
    try:
        imaging.cdn_url("https://evil.example/photo-1", role, entry.focal)
        return False
    except ValueError:
        return True


def _refuses_url(imaging, record, tax, country):
    try:
        imaging.cdn_url(record["imageUrl"], tax.role("hero"), country.entry("hero").focal)
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    sys.exit(main())
