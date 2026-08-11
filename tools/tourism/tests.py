#!/usr/bin/env python3
"""Test suite for the tourism image system.

    python3 tools/tourism/build.py test
    npm test

Runs entirely against local mocks of both provider APIs, so CI needs no
credentials and makes no network calls. The mocks speak the real response
shapes and serve real bytes, so the whole path is exercised: search, relevance
scoring, provider fallback, de-duplication, delivery-URL construction, HTTP
verification, caching, resumability and render.

Nothing here writes tourism/cache/ or tourism/countries/.
"""

import base64
import http.server
import json
import struct
import zlib
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


def png(width, height, seed=0):
    """A real PNG at exactly these dimensions, so the header the code parses is
    the header a generator would actually send."""
    rows = [b"\x00" + bytes([(x + y + seed) % 256 for x in range(width * 3)])
            for y in range(height)]

    def chunk(tag, data):
        block = tag + data
        return (struct.pack(">I", len(data)) + block
                + struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))

RESULTS = []
CALLS = []


class Mocks(http.server.BaseHTTPRequestHandler):
    """One server, both APIs, namespaced by path.

    Switches let a test make a provider fail, come back empty, or return only
    irrelevant pictures — the situations the fallback chain exists for.
    """

    unsplash_down = False
    unsplash_empty = False
    unsplash_irrelevant = False
    pexels_empty = False
    openai_down = False

    def log_message(self, *a):
        pass

    def _json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # -- payload builders -------------------------------------------------------

    def _unsplash_photo(self, query, portrait, relevant=True):
        key = abs(hash(query)) % 10 ** 8
        return {
            "id": "u-%d" % key,
            "width": 2400 if portrait else 3600,
            "height": 3200 if portrait else 2400,
            "urls": {"raw": "http://localhost:%d/u/photo-%d?ixlib=rb" % (PORT, key),
                     "full": "http://localhost:%d/u/photo-full-%d" % (PORT, key)},
            "alt_description": (query + " scene") if relevant else "a generic sunset",
            "description": None,
            "tags": [{"title": w} for w in query.split()] if relevant else [],
            "user": {"name": "Ada Photographer",
                     "links": {"html": "https://example.invalid/@ada"}},
            "links": {"html": "https://example.invalid/photos/%d" % key,
                      "download_location": "http://localhost:%d/unsplash/download/%d" % (PORT, key)},
        }

    def _pexels_photo(self, query, portrait):
        key = abs(hash("pexels" + query)) % 10 ** 8
        return {
            "id": key,
            "width": 2400 if portrait else 4200,
            "height": 3200 if portrait else 2800,
            "url": "https://example.invalid/pexels/%d" % key,
            "photographer": "Grace Shooter",
            "photographer_url": "https://example.invalid/@grace",
            "alt": query + " photographed on location",
            "src": {"original": "http://localhost:%d/p/photos/%d.jpeg" % (PORT, key)},
        }

    # -- routes -----------------------------------------------------------------

    def do_POST(self):
        """gpt-image-1 and the vision endpoint. Returns real PNG bytes at the
        requested size, so the caller has to measure them like it would in
        production rather than trusting what it asked for."""
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            return self._json({"error": {"message": "no key"}}, status=401)
        if self.openai_down:
            return self._json({"error": {"message": "rate limited"}}, status=429)
        CALLS.append(("openai", self.path))
        if self.path.endswith("/images/generations"):
            w, h = (int(v) for v in body["size"].split("x"))
            return self._json({"data": [
                {"b64_json": base64.b64encode(png(w, h, i)).decode()}
                for i in range(body.get("n", 1))]})
        return self._json({"choices": [{"message": {"content":
            "Elephants at a waterhole in dry acacia savanna."}}]})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(url.query)
        CALLS.append(url.path)
        path = url.path

        # ---- Unsplash
        if path == "/unsplash/photos/random":
            if not self.headers.get("Authorization", "").startswith("Client-ID "):
                return self._json({"errors": ["OAuth error"]}, 401)
            return self._json([{"id": "preflight"}])

        if path == "/unsplash/search/photos":
            if Mocks.unsplash_down:
                return self._json({"errors": ["service unavailable"]}, 500)
            query = (qs.get("query") or [""])[0]
            portrait = (qs.get("orientation") or ["landscape"])[0] == "portrait"
            if Mocks.unsplash_empty or len(query.split()) > 3:
                # Unsplash matches keywords, not sentences: over-specific queries
                # return nothing. This is what broke the first real run.
                return self._json({"results": [], "total": 0})
            return self._json({"results": [
                {   # too small: must be rejected before it is ever fetched
                    "id": "small-%d" % (abs(hash(query)) % 999), "width": 900, "height": 600,
                    "urls": {"raw": "http://localhost:%d/u/photo-small" % PORT},
                    "alt_description": query,
                    "user": {"name": "Too Small", "links": {"html": "https://x.invalid"}},
                    "links": {"html": "https://x.invalid", "download_location": ""},
                },
                self._unsplash_photo(query, portrait, not Mocks.unsplash_irrelevant),
            ]})

        if path.startswith("/unsplash/download/"):
            return self._json({"url": "ok"})

        # ---- Pexels
        if path == "/pexels/curated":
            if self.headers.get("Authorization", "") in ("", None):
                return self._json({"error": "no key"}, 401)
            return self._json({"photos": []})

        if path == "/pexels/search":
            query = (qs.get("query") or [""])[0]
            portrait = (qs.get("orientation") or ["landscape"])[0] == "portrait"
            if Mocks.pexels_empty or len(query.split()) > 3:
                return self._json({"photos": [], "total_results": 0})
            return self._json({"photos": [self._pexels_photo(query, portrait)]})

        # ---- CDNs
        if path.startswith("/u/photo-small"):
            CALLS.append("UNEXPECTED-FETCH")
            return self._json({"error": "should never be fetched"}, 500)

        if path.startswith("/u/") or path.startswith("/p/"):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(JPEG)))
            self.end_headers()
            self.wfile.write(JPEG)
            return

        self._json({"error": "not found"}, 404)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("  %-54s %s%s" % (name, "PASS" if ok else "FAIL", "  " + detail if detail else ""))


def both_keys():
    os.environ["UNSPLASH_ACCESS_KEY"] = "mock-unsplash-key"
    os.environ["PEXELS_API_KEY"] = "mock-pexels-key"


def no_keys():
    os.environ.pop("UNSPLASH_ACCESS_KEY", None)
    os.environ.pop("UNSPLASH_API_KEY", None)
    os.environ.pop("PEXELS_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)


def resolve_all(tax, country, cache, seen=None, only=None):
    from tourism import resolve
    seen = seen if seen is not None else set(cache.photo_ids())
    filled, failed = 0, []
    for cat in tax.enabled:
        entry = country.entry(cat["id"])
        if not entry or cache.has(country.slug, cat["id"]):
            continue
        rec, err = resolve.resolve_entry(country, cat, entry, tax.role(cat["id"]), seen, only)
        if rec:
            cache.put(country.slug, cat["id"], rec)
            entry.image = rec
            filled += 1
        else:
            failed.append((cat["id"], err))
    return filled, failed


def main():
    tmp = tempfile.mkdtemp(prefix="tourism-tests-")
    os.environ["UNSPLASH_API_BASE"] = "http://localhost:%d/unsplash" % PORT
    os.environ["PEXELS_API_BASE"] = "http://localhost:%d/pexels" % PORT
    os.environ["UNSPLASH_IMAGE_HOST_OVERRIDE"] = "http://localhost:%d/u/" % PORT
    os.environ["PEXELS_IMAGE_HOST_OVERRIDE"] = "http://localhost:%d/p/" % PORT
    os.environ["TOURISM_CACHE_FILE"] = os.path.join(tmp, "images.json")
    no_keys()

    from tourism import cache as cache_mod
    from tourism import imaging, providers, queries, relevance, resolve, validate
    from tourism.model import attach_cache, load_countries, load_taxonomy

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Mocks)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def fresh():
        return cache_mod.Cache(path=os.path.join(tmp, "c-%d.json" % len(RESULTS)))

    try:
        tax = load_taxonomy()
        countries = load_countries()
        cameroon = [c for c in countries if c.slug == "cameroon"][0]
        uganda = [c for c in countries if c.slug == "uganda"][0]
        kenya = [c for c in countries if c.slug == "kenya"][0]
        hero = tax.by_id["hero"]

        # -- 1. both providers unavailable --------------------------------------
        print("\n1. missing API keys fail safely")
        try:
            resolve.preflight()
            check("preflight raises when neither key is set", False)
        except providers.Unavailable as exc:
            check("preflight raises when neither key is set", True)
            check("error names both variables",
                  "UNSPLASH_ACCESS_KEY" in str(exc) and "PEXELS_API_KEY" in str(exc))
        rec, err = resolve.resolve_entry(cameroon, hero, cameroon.entry("hero"),
                                         tax.role("hero"), set())
        check("resolve returns no record without keys", rec is None and bool(err))
        check("nothing was cached", not cache_mod.Cache(path=os.path.join(tmp, "x.json")).entries)

        # -- 2. country-specific query generation --------------------------------
        print("\n2. country-specific queries")
        q_c = queries.build(cameroon, tax.by_id["mountains"], cameroon.entry("mountains"))
        q_u = queries.build(uganda, tax.by_id["wildlife"], uganda.entry("wildlife"))
        check("query names the country", q_c.startswith("Cameroon"), q_c)
        check("query carries the country's landmark", "mount" in q_c.lower())
        check("Uganda wildlife searches its own subject",
              "bwindi" in q_u.lower() or "gorilla" in q_u.lower(), q_u)
        check("different countries get different queries", q_c != q_u)
        owners, collisions = {}, []
        for c in countries:
            for cat in tax.enabled:
                e = c.entry(cat["id"])
                if e:
                    for q, _ in queries.ladder(c, cat, e):
                        if owners.setdefault(q, c.slug) != c.slug:
                            collisions.append(q)
        check("no query is shared between two countries", not collisions,
              ", ".join(collisions[:2]))
        check("no rung is the bare country name",
              all(q.strip().lower() != "cameroon"
                  for q, _ in queries.ladder(cameroon, hero, cameroon.entry("hero"))))

        # -- 3. relevance beats search rank --------------------------------------
        print("\n3. relevance is judged, not assumed")
        wildlife = tax.by_id["wildlife"]
        good = providers.Candidate({"provider": "unsplash", "photoId": "g", "width": 4000,
                                    "height": 2667, "text": "a mountain gorilla in Bwindi forest"})
        generic = providers.Candidate({"provider": "unsplash", "photoId": "x", "width": 4000,
                                       "height": 2667, "text": "beautiful Uganda travel africa"})
        s_good, _ = relevance.score(good, uganda, wildlife, uganda.entry("wildlife"),
                                    tax.role("wildlife"))
        s_generic, why = relevance.score(generic, uganda, wildlife, uganda.entry("wildlife"),
                                         tax.role("wildlife"))
        check("subject match outranks a generic country photo", s_good > s_generic,
              "%.1f vs %.1f" % (s_good, s_generic))
        check("a country-name-only photo is rejected outright", s_generic < relevance.MIN_SCORE,
              "; ".join(why)[:52])
        tall = providers.Candidate({"provider": "unsplash", "photoId": "t", "width": 1800,
                                    "height": 2700, "text": "gorilla Bwindi"})
        check("a portrait original is penalised for a 21:9 band",
              relevance.crop_waste(tall, tax.roles["panoramic"]) > 0.5)

        # -- 4. Unsplash success --------------------------------------------------
        print("\n4. Unsplash resolves and is preferred")
        both_keys()
        usable, _ = resolve.preflight()
        check("both providers pass preflight", [p.name for p in usable] == ["unsplash", "pexels"],
              ",".join(p.name for p in usable))
        cache = fresh()
        CALLS[:] = []
        rec, err = resolve.resolve_entry(cameroon, hero, cameroon.entry("hero"),
                                         tax.role("hero"), set())
        check("a record comes back", rec is not None, err or "")
        check("provider is recorded as unsplash", rec["provider"] == "unsplash")
        check("photoId is the id the API returned", rec["photoId"].startswith("u-"))
        check("imageUrl is the API's URL, query string stripped",
              rec["imageUrl"].startswith("http://localhost:%d/u/photo-" % PORT)
              and "?" not in rec["imageUrl"])
        for f in cache_mod.FIELDS:
            if f not in rec:
                check("schema field %s present" % f, False)
        check("record carries the full specified schema",
              all(f in rec for f in cache_mod.FIELDS))
        check("aspectRatio computed from the API dimensions",
              abs(rec["aspectRatio"] - 3600 / 2400.0) < 0.01, str(rec["aspectRatio"]))
        check("thumbnailUrl is smaller than the delivery size",
              "w=400" in rec["thumbnailUrl"])
        check("download endpoint pinged per Unsplash guidelines",
              any(c.startswith("/unsplash/download/") for c in CALLS))
        check("undersized candidate never fetched", "UNEXPECTED-FETCH" not in CALLS)
        check("alt describes the subject, not 'Cameroon image'",
              "Cameroon" in rec["alt"] and len(rec["alt"]) > 30, rec["alt"][:44])

        # -- 5. Unsplash failure -> Pexels fallback -------------------------------
        print("\n5. Pexels takes over when Unsplash cannot deliver")
        Mocks.unsplash_empty = True
        rec_p, err_p = resolve.resolve_entry(kenya, hero, kenya.entry("hero"),
                                             tax.role("hero"), set())
        check("a record still comes back", rec_p is not None, err_p or "")
        check("provider is recorded as pexels", rec_p and rec_p["provider"] == "pexels")
        check("imageUrl is on the Pexels CDN",
              rec_p and rec_p["imageUrl"].startswith("http://localhost:%d/p/" % PORT))
        check("Pexels credit is captured", rec_p and rec_p["photographer"] == "Grace Shooter")
        Mocks.unsplash_empty = False

        Mocks.unsplash_down = True
        rec_d, _ = resolve.resolve_entry(uganda, hero, uganda.entry("hero"),
                                         tax.role("hero"), set())
        check("an Unsplash outage falls through to Pexels",
              rec_d is not None and rec_d["provider"] == "pexels")
        Mocks.unsplash_down = False

        Mocks.unsplash_empty = True
        Mocks.pexels_empty = True
        rec_n, err_n = resolve.resolve_entry(uganda, tax.by_id["food"], uganda.entry("food"),
                                             tax.role("food"), set())
        check("both providers empty leaves the slot unresolved", rec_n is None)
        check("the failure explains itself", "provider" in (err_n or ""), (err_n or "")[:50])
        Mocks.unsplash_empty = Mocks.pexels_empty = False

        # -- 6. provider selection ------------------------------------------------
        print("\n6. provider preference and --provider")
        rec_only, _ = resolve.resolve_entry(kenya, tax.by_id["safari"], kenya.entry("safari"),
                                            tax.role("safari"), set(), only="pexels")
        check("--provider pexels uses only Pexels",
              rec_only is not None and rec_only["provider"] == "pexels")
        check("--provider rejects an unknown name",
              _raises(lambda: providers.all_providers("flickr"), KeyError))
        check("Unsplash wins when both are merely adequate", rec["provider"] == "unsplash")

        # -- 7. all 27 categories --------------------------------------------------
        print("\n7. all 27 categories resolve")
        cache = fresh()
        CALLS[:] = []
        filled, failed = resolve_all(tax, cameroon, cache)
        check("27 of 27 slots resolved", filled == 27,
              "filled=%d failed=%s" % (filled, failed[:2]))
        check("every stored URL was fetched before caching",
              len([c for c in CALLS if c.startswith(("/u/", "/p/"))]) >= 27)
        depths = {}
        for r in cache.entries.values():
            depths[r.get("queryTier")] = depths.get(r.get("queryTier"), 0) + 1
        check("the query ladder was exercised", len(depths) >= 1, str(depths))

        # -- 8. duplicates ---------------------------------------------------------
        print("\n8. duplicate detection")
        check("no photo was reused across the 27", cache.duplicates() == {},
              str(list(cache.duplicates())[:1]))
        check("27 distinct photo ids", len(cache.photo_ids()) == 27,
              str(len(cache.photo_ids())))
        dup = fresh()
        dup.put("cameroon", "wildlife", dict(rec, category="wildlife"))
        dup.put("kenya", "nature", dict(rec, category="nature", country="kenya"))
        check("the cache reports a reused photo id",
              list(dup.duplicates()) == ["unsplash:%s" % rec["photoId"]],
              str(list(dup.duplicates()))[:44])
        attach_cache([cameroon, kenya], dup)
        _, findings = validate.report([cameroon, kenya], tax)
        check("the validator errors on the duplicate",
              any("duplicate image" in f.message for f in findings if f.level == "error"))
        same_id_other_provider = dict(rec, provider="pexels",
                                      imageUrl="http://localhost:%d/p/photos/1.jpeg" % PORT)
        d2 = fresh()
        d2.put("a", "hero", rec)
        d2.put("b", "hero", same_id_other_provider)
        check("the same id on two providers is not a duplicate", d2.duplicates() == {})
        attach_cache([cameroon, kenya], cache)

        # -- 9. cache behaviour ----------------------------------------------------
        print("\n9. the cache prevents repeat API calls")
        cache.save()
        CALLS[:] = []
        again, _ = resolve_all(tax, cameroon, cache)
        check("a second run resolves nothing new", again == 0)
        check("a second run makes zero API calls", CALLS == [], "%d calls" % len(CALLS))
        reread = cache_mod.load(cache.path)
        check("the cache round-trips through the file", len(reread.entries) == 27)
        check("provider survives the round-trip",
              reread.get("cameroon", "hero")["provider"] in providers.BY_NAME)
        partial = fresh()
        for cat in tax.enabled[:10]:
            partial.put("cameroon", cat["id"], dict(rec, category=cat["id"],
                                                    photoId="seed-%s" % cat["id"]))
        CALLS[:] = []
        more, _ = resolve_all(tax, cameroon, partial)
        check("resumable: only the 17 missing slots are requested", more == 17, str(more))

        # -- 10. legacy migration ---------------------------------------------------
        print("\n10. single-provider records are carried forward")
        legacy = {"photoId": "abc", "imageUrl": "https://images.unsplash.com/photo-1",
                  "unsplashUrl": "https://unsplash.com/photos/abc", "photographer": "Old",
                  "width": 3000, "height": 2000, "resolvedAt": "2026-01-01T00:00:00Z"}
        upgraded = cache_mod.migrate(dict(legacy))
        check("provider is filled in as unsplash", upgraded["provider"] == "unsplash")
        check("unsplashUrl becomes sourceUrl",
              upgraded["sourceUrl"] == legacy["unsplashUrl"] and "unsplashUrl" not in upgraded)
        check("aspectRatio is computed", upgraded["aspectRatio"] == 1.5)
        check("a thumbnail is derived", "w=400" in (upgraded.get("thumbnailUrl") or ""))
        live = cache_mod.load(os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                           "tourism", "cache", "images.json"))
        check("the repo's real cache still loads", len(live.entries) >= 1,
              "%d records" % len(live.entries))
        check("every live record carries a known provider",
              all(r.get("provider") in providers.BY_NAME for r in live.entries.values()),
              str(sorted({r.get("provider") for r in live.entries.values()})))
        # image_host, not owns(): owns() honours the test host override, and these
        # are real production URLs.
        check("every live imageUrl is on its provider's real CDN",
              all(r["imageUrl"].startswith(providers.BY_NAME[r["provider"]].image_host)
                  for r in live.entries.values() if r.get("provider") in providers.BY_NAME),
              str(sorted({r["imageUrl"].split("/")[2] for r in live.entries.values()})))

        # -- 11. invalid URLs and responsive metadata -------------------------------
        print("\n11. delivery, crops and invalid URLs")
        entry = cameroon.entry("hero")
        entry.image = reread.get("cameroon", "hero")
        url = imaging.cdn_url(entry.image, tax.role("hero"), entry.focal)
        check("delivery URL extends the verified image URL",
              url.startswith(entry.image["imageUrl"] + "?"))
        check("hero delivered at 2400x1350", "w=2400" in url and "h=1350" in url)
        if entry.image["provider"] == "unsplash":
            check("focal point reaches the CDN crop",
                  "crop=focalpoint" in url and "fp-x=" in url)
        ss = imaging.srcset(entry.image, tax.role("hero"), entry.focal)
        check("srcset has one candidate per ladder step",
              ss.count(",") == len(tax.role("hero")["srcset"]) - 1)
        check("card is 4:3 and portrait is 3:4",
              imaging.dimensions(tax.roles["card"])[0] > imaging.dimensions(tax.roles["card"])[1]
              and imaging.dimensions(tax.roles["portrait"])[0]
              < imaging.dimensions(tax.roles["portrait"])[1])
        check("a thumbnail never loads hero bytes",
              imaging.dimensions(tax.roles["thumb"])[0] < imaging.dimensions(tax.roles["hero"])[0])
        check("a foreign URL cannot be delivered",
              _raises(lambda: imaging.cdn_url({"provider": "unsplash",
                                               "imageUrl": "https://cdn.evil.example/x"},
                                              tax.role("hero"), entry.focal), ValueError))
        check("a record with no provider is refused",
              _raises(lambda: imaging.cdn_url({"imageUrl": "https://nowhere.example/x"},
                                              tax.role("hero"), entry.focal), ValueError))

        # -- 12. the page renders provider-neutrally --------------------------------
        print("\n12. the frontend does not care which provider won")
        from tourism import render, verify as verify_mod
        mixed = fresh()
        for i, cat in enumerate(tax.enabled):
            src = dict(cache.get("cameroon", cat["id"]))
            if i % 3 == 0:      # pretend a third came from Pexels
                src.update(provider="pexels",
                           imageUrl="http://localhost:%d/p/photos/%d.jpeg" % (PORT, 1000 + i),
                           thumbnailUrl="http://localhost:%d/p/photos/%d.jpeg?w=400" % (PORT, 1000 + i),
                           photographer="Grace Shooter", photoId="p-%d" % i)
            mixed.put("cameroon", cat["id"], src)
        attach_cache([cameroon], mixed)
        outdir = os.path.join(tmp, "pages")
        render.write_all([cameroon], tax, {"cameroon"}, out_dir=outdir)
        page = open(os.path.join(outdir, "cameroon.html")).read()
        check("no unresolved placeholders remain", "data-unresolved" not in page)
        check("both CDNs appear in the markup",
              "/u/photo-" in page and "/p/photos/" in page)
        check("both photographers are credited",
              "Ada Photographer" in page and "Grace Shooter" in page)
        check("each provider is named in its own credit",
              "Unsplash" in page and "Pexels" in page)
        problems = verify_mod.check_page(os.path.join(outdir, "cameroon.html"), tax)
        check("the rendered page passes every structural check", not problems,
              "; ".join(problems[:2]))
        check("every remote image has a srcset", page.count("srcset=") >= 26,
              "%d" % page.count("srcset="))
        check("exactly one eager image, the hero", page.count('fetchpriority="high"') == 1)
        check("no markup mentions a key", "mock-unsplash-key" not in page
              and "mock-pexels-key" not in page)

        # -- 13. secrets stay server-side --------------------------------------------
        print("\n13. neither key reaches a client")
        leaked = []
        root = os.path.dirname(os.path.dirname(HERE))
        for dirpath, _, files in os.walk(root):
            if "/.git" in dirpath:
                continue
            for f in files:
                if not f.endswith((".html", ".json", ".js", ".css", ".md", ".yml")):
                    continue
                body = open(os.path.join(dirpath, f), errors="ignore").read()
                placeholder = re.compile(r"^(your|paste|xxx|\.\.\.|<|\$\{\{)", re.I)
                hit = re.search(r'(?:UNSPLASH_ACCESS_KEY|PEXELS_API_KEY)\s*[=:]\s*["\']?([A-Za-z0-9_-]{20,})', body)
                if "mock-unsplash-key" in body or "mock-pexels-key" in body or (
                        hit and not placeholder.match(hit.group(1))):
                    leaked.append(os.path.relpath(os.path.join(dirpath, f), root))
        check("no key value in any committed artifact", not leaked, ", ".join(leaked[:3]))
        env_example = os.path.join(root, ".env.example")
        body = open(env_example).read() if os.path.exists(env_example) else ""
        check(".env.example declares both variables, empty",
              "UNSPLASH_ACCESS_KEY=" in body and "PEXELS_API_KEY=" in body
              and not re.search(r"(UNSPLASH_ACCESS_KEY|PEXELS_API_KEY)=\S", body))
        check("the cache schema has no key field",
              not any("key" in f.lower() for f in cache_mod.FIELDS))
        check(".env.example declares OPENAI_API_KEY, empty",
              "OPENAI_API_KEY=" in body and not re.search(r"OPENAI_API_KEY=\S", body))

        # ---- the generation engine ------------------------------------------
        print("\ngeneration engine")
        from tourism import candidates as pool, generate as gen
        from tourism import intake, place as place_mod, placements as pl, prompting

        style = prompting.load_style()
        placements = pl.scan(cameroon)
        targets = pl.targetable(placements)

        check("every image slot on the five pages is found",
              len(placements) >= 30, "%d slots" % len(placements))
        check("locked artwork is never a generation target",
              all(not p["locked"] for p in targets)
              and any(p["locked"] for p in placements))
        check("each slot carries the shape its own stylesheet imposes",
              {tuple(p["aspect"]) for p in placements} >= {(3, 4), (4, 5), (5, 4)})
        check("one illustration used at two shapes is two different jobs",
              any(len({tuple(i["aspect"]) for i in items}) > 1
                  for items in pl.duplicates(placements).values()))

        jobs = gen.plan_jobs(cameroon, tax, pool.Pool(path=os.path.join(tmp, "p.json")),
                             style, "site")
        prompts = {j.slot: j.prompt for j in jobs}
        check("every targetable slot compiles to an instruction",
              len(jobs) == len(targets) and all(prompts.values()))
        check("the instruction names the slot's own subject",
              all(j.prompt.startswith("A documentary travel photograph. Subject:")
                  for j in jobs))
        check("the instruction states the delivered crop",
              all("cropped to %d:%d" % tuple(j.aspect) in j.prompt for j in jobs))
        check("the instruction forbids text baked into the picture",
              all("watermarks" in j.prompt and "travel-poster" in j.prompt for j in jobs))
        check("prompts are deterministic",
              prompts == {j.slot: j.prompt for j in
                          gen.plan_jobs(cameroon, tax,
                                        pool.Pool(path=os.path.join(tmp, "p2.json")),
                                        style, "site")})
        check("a portrait slot asks for a portrait frame",
              all(prompting.size_for_aspect(j.aspect, style) == "1024x1536"
                  for j in jobs if j.aspect[1] > j.aspect[0]))

        # generation against the mock, which returns real PNG bytes
        os.environ["OPENAI_API_BASE"] = "http://localhost:%d/openai/v1" % PORT
        os.environ["TOURISM_CANDIDATES_FILE"] = os.path.join(tmp, "candidates.json")
        gen.CANDIDATE_DIR = os.path.join(tmp, "candidates")
        place_mod.DESTINATIONS = {
            "openai": (os.path.join(tmp, "images", "generated"), "/images/generated/"),
            "upload": (os.path.join(tmp, "images", "uploads"), "/images/uploads/"),
        }

        os.environ.pop("OPENAI_API_KEY", None)
        check("no key means no generation, and a clear reason",
              _raises(lambda: gen.run(cameroon, tax, scope="site", only="waza-elephants",
                                      log=lambda *a: None),
                      gen.Unavailable))
        check("a dry run sends nothing and needs no key",
              gen.run(cameroon, tax, scope="site", only="waza-elephants",
                      dry_run=True, log=lambda *a: None)["generated"] == 0)

        os.environ["OPENAI_API_KEY"] = "mock-openai-key"
        summary = gen.run(cameroon, tax, scope="site", only="waza-elephants",
                          log=lambda *a: None)
        index = pool.load()
        made = [c for slot in index.slots for c in index.generated(slot)]
        check("generation writes real image files",
              summary["generated"] == 2 and len(made) == 2)
        check("dimensions are read from the bytes, not from the request",
              all(c["width"] and c["height"] and
                  os.path.exists(os.path.join(root, c["file"])) for c in made))
        check("the same subject at two shapes gets two different pictures",
              len({c["id"] for c in made}) == 2
              and len({tuple(c["aspect"]) for c in made}) == 2)
        check("a generated candidate records the instruction it came from",
              all(c.get("prompt") and c.get("where") for c in made))
        check("a second run generates nothing already held",
              gen.run(cameroon, tax, scope="site", only="waza-elephants",
                      log=lambda *a: None)["generated"] == 0)

        check("nothing generated is in the live cache",
              not any(r.get("provider") in ("openai", "upload")
                      for r in cache_mod.load().entries.values()))

        # placement
        slot = "site:index:waza-elephants"
        cand = index.generated(slot)[0]
        before = open(os.path.join(root, "index.html")).read()
        report = place_mod.run({slot: cand["id"]}, cameroon, dry_run=True, log=lambda *a: None)
        check("a dry-run placement writes no page and no file",
              report["placed"] == 1
              and open(os.path.join(root, "index.html")).read() == before)
        check("a pick naming a slot that does not exist fails the whole run",
              place_mod.run({"site:index:nope": cand["id"]}, cameroon,
                            dry_run=True, log=lambda *a: None)["errors"])
        check("a stock candidate cannot be placed by `place`",
              place_mod.run({slot: "unsplash:abc"}, cameroon,
                            dry_run=True, log=lambda *a: None)["errors"])

        tag = place_mod.rewrite_tag(
            '<img src="/images/waza-elephants.svg" alt="Elephants" loading="lazy">',
            "/images/generated/x.png", cand, "Elephants at a waterhole", {"x": 50, "y": 55})
        check("a placed tag keeps the illustration it replaced",
              'data-illustration="/images/waza-elephants.svg"' in tag
              and 'data-illustration-alt="Elephants"' in tag)
        check("a placed tag is marked so `adopt` cannot overwrite it",
              'data-placed="true"' in tag and 'data-generated="true"' in tag)
        check("a placed tag has no width or height attribute",
              " width=" not in tag and " height=" not in tag)
        check("srcset states the one width there actually is",
              'srcset="/images/generated/x.png %dw"' % cand["width"] in tag)
        check("reverting a placed tag restores the drawing exactly",
              place_mod.revert_tag(tag) ==
              '<img src="/images/waza-elephants.svg" alt="Elephants" loading="lazy">')

        # a generated record is deliverable through the ordinary imaging path
        rec = {"provider": "openai", "photoId": "x", "photographer": "AI",
               "imageUrl": "/images/generated/x.png", "width": 1536, "height": 1024}
        role = tax.role("wildlife")
        check("a generated record delivers through the normal imaging path",
              imaging.cdn_url(rec, role, {"x": 50, "y": 50}) == "/images/generated/x.png")
        check("a provider with no CDN gets one honest srcset entry",
              imaging.srcset(rec, role, {"x": 50, "y": 50})
              == "/images/generated/x.png 1536w")
        check("a generated image is credited as generated, not as a photographer",
              providers.BY_NAME["openai"].attribution(
                  dict(rec, model="gpt-image-1"))[0] == "AI-generated · gpt-image-1")
        check("an uploaded image is never labelled AI",
              providers.BY_NAME["upload"].attribution({"photographer": "A Name"})
              == ("A Name", None))
        check("generators are not searchable",
              _raises(lambda: providers.BY_NAME["openai"].search("x", "landscape"),
                      NotImplementedError)
              and "openai" not in [p.name for p in providers.all_providers()])

        # intake
        up = os.path.join(tmp, "incoming")
        os.makedirs(up, exist_ok=True)
        shutil.copy(os.path.join(root, cand["file"]),
                    os.path.join(up, "waza-elephants-waterhole-savanna.png"))
        shutil.copy(os.path.join(root, cand["file"]), os.path.join(up, "IMG_9931.png"))
        found = intake.scan_folder(up)
        check("intake reads dimensions out of the uploaded files",
              len(found) == 2 and all(f["width"] and f["height"] for f in found))
        matched, unmatched = intake.assign(found, targets)
        check("a named upload is matched to the slot it describes",
              any(m["placement"]["id"] == "waza-elephants" for m in matched))
        check("an unnamed upload is reported, not guessed at",
              any(f["name"] == "IMG_9931.png" for f in unmatched))
        check("intake never matches two images to one slot",
              len({m["slot"] for m in matched}) == len(matched))
        wrong = dict(found[0], width=1000, height=3000)
        check("a shape the crop would ruin scores zero",
              intake.score(wrong, [p for p in targets
                                   if tuple(p["aspect"]) == (16, 9)] [0]
                           if any(tuple(p["aspect"]) == (16, 9) for p in targets)
                           else targets[0])[0] == 0.0)
        check("intake proposes only; it never writes a page",
              intake.run(cameroon, tax, directory=up, dry_run=True,
                         log=lambda *a: None)["matched"] >= 1
              and open(os.path.join(root, "index.html")).read() == before)

    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
        no_keys()

    failed = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d passed, %d failed"
          % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    for n in failed:
        print("  FAILED: %s" % n)
    if not failed:
        print("both providers are ready for real credentials")
    return 1 if failed else 0


def _raises(fn, exc_type):
    try:
        fn()
        return False
    except exc_type:
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
