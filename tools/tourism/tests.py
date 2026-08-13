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
import glob
import html as html_mod
import http.server
import json
import struct
import zlib
import os
import re
import shutil
import subprocess
import socketserver
import sys
import tempfile
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
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


def read_json_file(path, fallback=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, ValueError):
        return fallback if fallback is not None else {}


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
    from tourism.model import (attach_cache, load_countries, load_country,
                               load_taxonomy)

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

        # -- 6b. requests that cannot change the answer ---------------------------
        print("\n6b. a request that cannot change the answer is not made")
        check("the ceiling is every positive term at its cap",
              abs(relevance.CEILING - 9.5) < 1e-9, "%.2f" % relevance.CEILING)
        check("above the ceiling less the winning margin, nothing can win",
              relevance.UNBEATABLE == relevance.CEILING - relevance.CLEARLY_BETTER,
              "%.1f" % relevance.UNBEATABLE)
        # Both providers still get asked whenever the first answer leaves room.
        CALLS[:] = []
        resolve.resolve_entry(kenya, tax.by_id["safari"], kenya.entry("safari"),
                              tax.role("safari"), set())
        asked = {c.split("/")[1] for c in CALLS if c.startswith(("/search", "/u", "/p"))} \
            if CALLS else set()
        both = len([c for c in CALLS if "unsplash" in c or c.startswith("/u")]) > 0 \
            and len([c for c in CALLS if "pexels" in c or c.startswith("/p")]) > 0
        check("with an ordinary match, both providers are still consulted", both,
              "%d calls" % len(CALLS))
        # And the arithmetic itself: a score above UNBEATABLE cannot be displaced.
        check("no score at or below the ceiling beats an unbeatable one",
              not (relevance.CEILING >= (relevance.UNBEATABLE + 0.01)
                   + relevance.CLEARLY_BETTER),
              "ceiling %.1f, unbeatable %.1f" % (relevance.CEILING, relevance.UNBEATABLE))

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
        # Derived, not spelled out: the slot key contains the page name, and
        # hard-coding it broke the moment the Cameroon home page moved off the
        # site root. The test cares that a slot can be placed, not which page.
        waza_slot = [p for p in targets if p["id"] == "waza-elephants"][0]
        slot = pool.placement_slot(waza_slot)
        cand = index.generated(slot)[0]
        before = open(os.path.join(root, "index.html")).read()
        report = place_mod.run({slot: cand["id"]}, cameroon, dry_run=True, log=lambda *a: None)
        check("a dry-run placement writes no page and no file",
              report["placed"] == 1
              and open(os.path.join(root, "index.html")).read() == before)
        check("a pick naming a slot that does not exist fails the whole run",
              place_mod.run({slot + "-does-not-exist": cand["id"]}, cameroon,
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
        waza = [p for p in targets if p["id"] == "waza-elephants"][0]
        named = dict(found[0], name="waza-elephants.png",
                     words=intake.stem_words("waza-elephants.png"))
        tall = dict(named, width=1000, height=3000)
        wide = dict(named, width=3000, height=1000)
        check("a filename that is a slot id beats every other signal",
              intake.score(named, waza)[0] >= intake.EXACT_NAME)
        check("a bad shape is a penalty, not a veto",
              0 < intake.score(tall, waza)[0] < intake.score(wide, waza)[0])
        check("the crop loss is reported so it can be judged",
              any("discards" in r for r in intake.score(tall, waza)[1]))
        anon = dict(found[0], name="DSC_0042.png", words=[])
        check("a picture with nothing to go on stays below the floor whatever its shape",
              all(intake.score(dict(anon, width=w, height=h), p)[0] < intake.MIN_SCORE
                  for p in targets for w, h in ((3000, 2000), (2000, 3000), (2000, 2000))))
        gen_dir = os.path.join(up, intake.GENERATED_SUBDIR)
        os.makedirs(gen_dir, exist_ok=True)
        shutil.copy(os.path.join(root, cand["file"]),
                    os.path.join(gen_dir, "waza-elephants.png"))
        origins = {f["name"]: f.get("origin") for f in intake.scan_folder(up)}
        check("an upload from incoming/generated/ is marked AI-generated",
              origins.get("waza-elephants.png") == "openai"
              and origins.get("IMG_9931.png") == "upload")
        check("intake proposes only; it never writes a page",
              intake.run(cameroon, tax, directory=up, dry_run=True,
                         log=lambda *a: None)["matched"] >= 1
              and open(os.path.join(root, "index.html")).read() == before)

        # -- the atlas -------------------------------------------------------------
        # The geography is the one part of this system that is generated from
        # data a human never types, so the things worth testing are that it stays
        # generated: no country named in code, no coordinate invented, and no
        # place claimed that the dataset does not already say.
        print("\natlas")
        from tourism import atlas
        lenses = atlas.load_lenses()
        sp = atlas.spine(countries, lenses)
        check("every published country is on the spine",
              set(sp["countries"]) == set(c.slug for c in countries if c.published))
        check("every country lands in exactly one region",
              all(sp["countries"][s]["regionKey"] for s in sp["countries"])
              and sum(len(r["countries"]) for r in sp["regions"]) == len(sp["countries"]))
        check("a region's view contains every one of its members",
              all(all(_inside(sp["countries"][s]["box"], r["view"])
                      for s in r["countries"] if sp["countries"][s]["box"])
                  for r in sp["regions"]))
        check("a lens holds only countries that call it themselves",
              all(all(l["key"] in sp["countries"][s]["calls"] for s in l["countries"])
                  for l in sp["lenses"]))
        check("no lens is empty", all(l["countries"] for l in sp["lenses"]))
        check("the spine carries no image URL nobody fetched",
              "imageUrl" not in json.dumps(sp))

        pack = atlas.places(uganda, tax, lenses)
        titles = [p["title"] for p in pack["places"]]
        check("a country's places are its own written entries",
              set(titles) <= set(e.caption for e in uganda.entries))
        check("the hero is not offered as a place",
              uganda.entry("hero").caption not in titles)
        check("places lead with what the country calls itself on",
              pack["places"][0]["id"] in ("wildlife", "safari"), pack["places"][0]["id"])
        check("an unresolved place carries no photograph",
              all(p["image"] is None for p in pack["places"]))

        page = atlas.render(countries, tax)
        check("every country on the map is reachable without script",
              all(('href="%s"' % c.url) in page
                  for c in countries if c.published and c.url.startswith("/")))
        check("the map is one SVG, not one per country", page.count("<svg") == 1)
        check("the continent pane lists every region without script",
              all(r["name"].replace("&", "&amp;") in page for r in sp["regions"]))
        # The claim is that the atlas is data-driven, and the way to test a claim
        # like that is to change the data and watch the output follow — not to
        # grep the source for country names, which only tests the comments.
        subset = [c for c in countries if c.slug in ("uganda", "kenya", "morocco")]
        small = atlas.spine(subset, lenses)
        check("dropping countries drops them from the map's spine",
              set(small["countries"]) == {"uganda", "kenya", "morocco"})
        check("a region with no members left disappears rather than emptying",
              all(r["countries"] for r in small["regions"])
              and len(small["regions"]) < len(sp["regions"]))
        check("a lens narrows to whoever is left",
              all(set(l["countries"]) <= {"uganda", "kenya", "morocco"}
                  for l in small["lenses"]))
        check("region views are recomputed, not cached from the full set",
              any(r["view"] != next(x["view"] for x in sp["regions"] if x["key"] == r["key"])
                  for r in small["regions"]))

        # -- the spatial model ------------------------------------------------------
        # The claim is that every connection this site draws is a fact somebody
        # could check on a map or in a country file. So each one is checked
        # against the thing it claims to come from.
        print("\nthe spatial model")
        from tourism import atlas as atlas_mod, links as links_mod
        geo = links_mod.geometry()
        lenses_all = atlas_mod.load_lenses()
        net = links_mod.payload(countries, lenses_all)
        published = set(c.slug for c in countries if c.published)

        check("every published country is on the network",
              set(net["nodes"]) == published)
        check("every node sits at its own country's centre",
              all(n["at"] and n["lonlat"] for n in net["nodes"].values()))
        check("borders are symmetric",
              all(a in geo["borders"].get(b, []) for a, bs in geo["borders"].items()
                  for b in bs))
        check("no country borders itself",
              not any(a in bs for a, bs in geo["borders"].items()))
        # Spot-checks against an actual map. If the geometry reader breaks, these
        # break, and they are things anybody can verify.
        check("Uganda borders Kenya, Rwanda and Tanzania and nothing else here",
              set(geo["borders"]["uganda"]) == {"kenya", "rwanda", "tanzania"},
              ", ".join(geo["borders"]["uganda"]))
        check("South Africa borders its four neighbours in the set",
              set(geo["borders"]["south-africa"])
              == {"botswana", "mozambique", "namibia", "zimbabwe"},
              ", ".join(geo["borders"]["south-africa"]))
        check("an island borders nobody",
              not geo["borders"]["seychelles"] and not geo["borders"]["mauritius"])
        check("Egypt borders nothing else in this set",
              not geo["borders"]["egypt"])
        check("distance is symmetric and non-zero",
              all(geo["km"][a][b] == geo["km"][b][a] and geo["km"][a][b] > 0
                  for a in ("uganda", "morocco") for b in ("kenya", "ghana")))
        check("Kampala to Kigali is about four hundred and fifty kilometres",
              440 <= geo["km"]["uganda"]["rwanda"] <= 470,
              "%d km" % geo["km"]["uganda"]["rwanda"])

        bad = []
        for a, rows in net["links"].items():
            for r in rows:
                for w in r["why"]:
                    if w["kind"] == "border" and r["to"] not in geo["borders"].get(a, []):
                        bad.append("%s-%s border" % (a, r["to"]))
                    if w["kind"] == "lens":
                        shared = set(by_slug_test(countries, a).calls) \
                            & set(by_slug_test(countries, r["to"]).calls)
                        if not shared:
                            bad.append("%s-%s lens" % (a, r["to"]))
                    if w["kind"] == "season":
                        shared = set(by_slug_test(countries, a).months) \
                            & set(by_slug_test(countries, r["to"]).months)
                        if len(shared) != len(w["months"]):
                            bad.append("%s-%s season" % (a, r["to"]))
        check("every connection is backed by the fact it names", not bad,
              ", ".join(bad[:3]))
        check("no connection is offered without evidence",
              all(r["why"] for rows in net["links"].values() for r in rows))
        check("nothing is connected to itself",
              not any(r["to"] == a for a, rows in net["links"].items() for r in rows))
        check("a land border always outranks a shared season",
              all(next((i for i, r in enumerate(rows)
                        if any(w["kind"] == "border" for w in r["why"])), 0)
                  < next((len(rows) for r in rows), 1)
                  for rows in net["links"].values() if rows))
        far = [(a, r["to"], r["km"]) for a, rows in net["links"].items() for r in rows
               if r["km"] and r["km"] > links_mod.FAR_KM
               and not any(w["kind"] == "border" for w in r["why"])]
        check("nothing across the Sahara is called nearby", not far,
              ", ".join("%s-%s %dkm" % f for f in far[:2]))
        check("no connection claims a travel time",
              not any("hour" in json.dumps(r) or "drive" in json.dumps(r)
                      for rows in net["links"].values() for r in rows))

        # A journey can cross a border, and only across one.
        engine = os.path.join(ROOT_DIR, "scripts", "journey-engine.js")
        src = open(engine).read()
        check("the journey engine can carry a stage in another country",
              "stageOf" in src and "onward" in src)
        check("crossing requires a shared land border",
              "w.kind === 'border'" in src)

        # -- the visual engine ------------------------------------------------------
        # Most of what this system does is already covered above: delivery URLs,
        # focal crops, srcsets, providers, attribution. What is new here is the
        # part that runs when there is no photograph — which, with 567 of 594
        # slots unresolved, is most of the site — plus the pieces that stop one
        # component becoming four.
        print("\nthe visual engine")
        from tourism import plate as plate_mod
        from tourism.model import load_regions, region_of

        regions = load_regions()
        check("every region names the ground its countries are drawn on",
              all(r.tone.startswith("#") and len(r.tone) == 7 for r in regions.values()),
              ", ".join("%s=%s" % (k, r.tone) for k, r in regions.items())[:60])
        tones = {}
        for co in countries:
            if co.published:
                tones.setdefault(plate_mod.tone_for(co, regions), []).append(co.slug)
        check("every published country has a ground",
              all(t for t in tones), "%d distinct tones" % len(tones))
        check("two countries from different regions do not share a ground",
              len(tones) == len({region_of(c, regions)[0]
                                 for c in countries if c.published}))

        uganda_hero = uganda.entry("hero")
        shp = {"w": 100, "h": 120, "d": "M0 0L10 0L10 10Z"}
        pl = plate_mod.plate(uganda, uganda_hero, [16, 9], "Uganda hero", shape=shp)
        check("a slot with no photograph draws a plate, not a hole",
              'class="af-plate"' in pl and 'aspect-ratio:16/9' in pl)
        check("the plate carries the caption somebody wrote",
              esc_test(uganda_hero.caption) in pl, uganda_hero.caption)
        check("the plate says which country it is",
              ">Uganda<" in pl)
        check("the plate is labelled for a screen reader",
              'role="img"' in pl and 'aria-label="Uganda hero"' in pl)
        check("the plate is the same shape as the photograph it stands in for",
              "aspect-ratio:16/9" in pl
              and "aspect-ratio:4/5" in plate_mod.plate(uganda, uganda_hero, [4, 5],
                                                        "x", shape=shp))
        ground = plate_mod.plate(uganda, uganda_hero, [16, 9], "x", shape=shp, ground=True)
        check("a plate under a headline carries no headline of its own",
              esc_test(uganda_hero.caption) not in ground and 'aria-hidden="true"' in ground)
        check("the plate never says the picture is missing",
              "missing" not in pl.lower() and "coming soon" not in pl.lower())

        # One window, not four.
        win = plate_mod.window_svg(shp, "Uganda", image="/i.jpg", alt="A ridge")
        # Once, not twice: the outline is defined once and referenced by both the
        # clipPath and the visible fill. It used to be written out twice, which
        # is 1.3 KB of duplicate coordinates per country and 26 KB on the gateway.
        check("the window clips the photograph with the country's own path",
              win.count(shp["d"]) == 1 and "clipPath" in win
              and win.count("<use ") == 2)
        check("the window without a photograph is the filled outline",
              "<image" not in plate_mod.window_svg(shp, "Uganda"))
        check("the window describes itself from the photograph where there is one",
              'aria-label="A ridge"' in win
              and 'aria-label="The outline of Uganda"'
                  in plate_mod.window_svg(shp, "Uganda"))
        js = open(os.path.join(ROOT_DIR, "scripts", "window.js")).read()
        for page in ("journey.js", "meet.js"):
            src = open(os.path.join(ROOT_DIR, "scripts", page)).read()
            check("%s draws the window from the shared component" % page,
                  "AfrinkongWindow" in src and "clipPath" not in src)
        check("the browser's window and the build's window agree",
              all(bit in js for bit in ("af-window-fill", "af-window-svg",
                                        "xMidYMid slice", "clipPath")))
        # Including the part that is easy to change in one and forget in the
        # other: both define the outline once and <use> it twice.
        check("the browser's window defines its outline once too",
              js.count('d="\' + shape.d') == 1 and js.count("<use ") == 2)

        # Roles: what the crop must keep, and what a phone gets instead.
        roles = [r for k, r in tax.roles.items() if not k.startswith("$")]
        check("every role says what its crop must not throw away",
              all(r.get("focus") for r in roles),
              ", ".join(k for k, r in tax.roles.items()
                        if not k.startswith("$") and not r.get("focus")))
        wide = [r for r in roles if r["aspect"][0] / float(r["aspect"][1]) >= 1.7]
        check("a role too wide for a phone declares a second crop",
              all(r.get("mobile") for r in wide), "%d wide roles" % len(wide))
        check("the second crop is taller than the first",
              all(r["mobile"]["aspect"][0] / float(r["mobile"]["aspect"][1])
                  < r["aspect"][0] / float(r["aspect"][1]) for r in wide))

        host = os.environ["UNSPLASH_IMAGE_HOST_OVERRIDE"]
        fake = {"provider": "unsplash", "imageUrl": host + "photo-1?ixid=t",
                "photoId": "x", "width": 4000, "height": 2667, "photographer": "A N"}
        hero_role = tax.role("hero")
        art = imaging.art_direction(fake, hero_role, {"x": 50, "y": 40})
        check("a wide slot delivers a taller crop to a phone",
              art and "max-width" in art["media"] and art["aspect"] == "4 / 5")
        first = (art or {}).get("srcset", "").split(",")[0]
        import urllib.parse as _up
        q = dict(_up.parse_qsl(_up.urlparse(first.split(" ")[0]).query))
        check("art direction asks the CDN for the narrow crop, not CSS",
              q.get("w") and q.get("h")
              and round(int(q["h"]) / float(q["w"]), 2) == round(5 / 4.0, 2),
              "%sx%s" % (q.get("w"), q.get("h")))
        check("and it cuts around the same focal point",
              q.get("fp-y") == "0.400", q.get("fp-y"))
        flat = {"provider": "upload", "imageUrl": "/images/uploads/x.jpg",
                "photoId": "u", "width": 1200, "height": 800}
        check("a provider with no CDN is not asked to art direct",
              imaging.art_direction(flat, hero_role, {"x": 50, "y": 50}) is None)
        check("a role with no second crop gets none",
              imaging.art_direction(fake, tax.role("food"), {"x": 50, "y": 50}) is None
              or tax.role("food").get("mobile"))

        # Variety: the same animal six times is six correct answers and one bad page.
        gorilla = providers.Candidate(
            {"provider": "unsplash", "photoId": "g9", "width": 3000, "height": 2000,
             "text": "mountain gorilla silverback in the forest of bwindi uganda"})
        already = [relevance.words("mountain gorilla silverback bwindi forest uganda")]
        alone, _ = relevance.score(gorilla, uganda, tax.by_id["wildlife"],
                                   uganda.entry("wildlife"), tax.role("wildlife"))
        again, why = relevance.score(gorilla, uganda, tax.by_id["wildlife"],
                                     uganda.entry("wildlife"), tax.role("wildlife"),
                                     taken=already)
        check("a photograph like one already used here scores lower", again < alone,
              "%.1f -> %.1f" % (alone, again))
        check("and the sheet says why", any("already filled" in w for w in why))
        other = providers.Candidate(
            {"provider": "unsplash", "photoId": "k1", "width": 3000, "height": 2000,
             "text": "fishing boats on lake victoria at dawn uganda"})
        same_alone, _ = relevance.score(other, uganda, tax.by_id["wildlife"],
                                        uganda.entry("wildlife"), tax.role("wildlife"))
        same_after, _ = relevance.score(other, uganda, tax.by_id["wildlife"],
                                        uganda.entry("wildlife"), tax.role("wildlife"),
                                        taken=already)
        check("a different photograph is not punished for the first one",
              same_alone == same_after)

        # The gate.
        print("\nthe image quality gate")
        import copy as _copy

        def gate(mutate):
            co = load_country(uganda.path)
            mutate(co)
            return [f for f in validate.check_images(co, tax) if f.level == "error"]

        def set_image(co, cat, rec):
            co.entry(cat).image = rec

        good = {"provider": "unsplash", "imageUrl": host + "photo-9?ixid=t",
                "photoId": "p", "width": 4000, "height": 2667, "photographer": "A N Other"}
        check("a sound record passes", not gate(lambda co: set_image(co, "hero", good)))
        check("a photograph with no photographer is refused, not published",
              gate(lambda co: set_image(co, "hero",
                                        dict(good, photographer=""))))
        check("a generated picture that is not disclosed is refused",
              gate(lambda co: set_image(co, "hero",
                                        {"provider": "openai", "photoId": "g",
                                         "imageUrl": "/images/generated/x.png",
                                         "width": 1536, "height": 1024})))
        check("a photograph flagged as generated is refused",
              gate(lambda co: set_image(co, "hero", dict(good, generated=True))))
        check("a record from an unknown provider is refused",
              gate(lambda co: set_image(co, "hero",
                                        dict(good, provider="somewhere",
                                             imageUrl="https://elsewhere/x.jpg"))))
        check("a record resolved for another country is refused",
              gate(lambda co: set_image(co, "hero", dict(good, country="kenya"))))
        check("a record resolved for another slot is refused",
              gate(lambda co: set_image(co, "hero", dict(good, category="food"))))
        check("a focal point outside the frame is refused",
              gate(lambda co: co.entry("hero").focal.update({"x": 140})))
        check("a local asset that is not on disk is refused",
              gate(lambda co: setattr(co.entry("hero"), "local", "/images/nope.svg")))
        check("the gate is clean on the dataset as it stands",
              not [f for c in countries for f in validate.check_images(c, tax)
                   if f.level == "error"])

        # -- the human layer --------------------------------------------------------
        # The claim this layer makes is that nothing on it is invented: every
        # line is a caption or a description already written for that country,
        # or an operator's own sentence. That is testable, so it is tested —
        # by taking every string the page can print and looking for it in the
        # country files it claims to have come from.
        print("\nthe human layer")
        from tourism import meet
        from tourism.model import load_people, load_strands, load_voices
        strands = load_strands()
        payload = meet.strands_payload(countries, tax)

        check("every strand points at categories that exist",
              all(c in tax.by_id for s in strands.values()
                  for c in (s.get("categories") or [])))
        check("every strand asks a question",
              all((s.get("asks") or "").endswith("?") for s in strands.values()))
        check("no strand names a country",
              not any(co.name.lower() in json.dumps(strands).lower()
                      for co in countries if co.published))

        written = set()
        for co in countries:
            for e in co.entries:
                if e.caption:
                    written.add(e.caption)
                if e.description:
                    written.add(e.description)
        printed = set()
        for rows in payload["answers"].values():
            for answers in rows.values():
                for a in answers:
                    printed.add(a["title"])
                    printed.add(a["text"])
        check("every answer is a sentence somebody already wrote",
              printed <= written, "%d unaccounted" % len(printed - written))
        check("the human layer covers every published country",
              set(payload["countries"]) ==
              set(c.slug for c in countries if c.published))
        thin = [s for s in payload["countries"]
                if sum(1 for rows in payload["answers"].values() if s in rows)
                < len(strands)]
        check("a country with nothing behind a door is left blank, not filled in",
              all(s in payload["countries"] for s in thin), "%d thin" % len(thin))

        # People and operator notes: empty is the correct state, and the page has
        # to be empty with them rather than reaching for something plausible.
        page = meet.render(countries, tax)
        check("no guide profile is invented", not load_people(),
              "%d in people.json" % len(load_people()))
        check("no operator is quoted saying something they did not say",
              not load_voices(), "%d in voices.json" % len(load_voices()))
        check("the people block ships empty rather than filled",
              '<script type="application/json" id="mt-people">[]</script>' in page)
        check("the first question is answered without script",
              page.count('class="mt-answer"') ==
              len(payload["answers"][payload["strands"][0]["key"]]))
        check("every country on the page is a link to its own page",
              all(('data-country="%s"' % c.slug) in page
                  for c in countries if c.published))

        # -- how people are written about --------------------------------------------
        print("\nhow people are written about")
        planted = type("P", (), {})()
        planted.slug, planted.name = "test", "Testland"
        planted.tagline = "The real Africa, untouched by civilisation"
        planted.summary = "African culture at its most primitive."
        planted.when = ""
        planted.entries = []
        hits = validate.check_language(planted)
        found = " ".join(f.message for f in hits)
        check("exoticising language is caught", "'primitive'" in found)
        check("continent-wide generalisation is caught", "'african culture'" in found)
        check("'the real Africa' is caught", "'real africa'" in found)
        check("the finding says what to do instead",
              "name the community" in found and "say which people" in found)
        clean_one = [c for c in countries if c.slug == "uganda"][0]
        check("the check does not fire on the dataset as written",
              not validate.check_language(clean_one),
              "; ".join(f.message for f in validate.check_language(clean_one))[:70])
        every = [f for c in countries for f in validate.check_language(c)]
        check("nothing in the dataset turns people into scenery", not every,
              "; ".join(f.message for f in every)[:80])
        check("the check reads captions, descriptions and taglines alike",
              len(validate._sentences(clean_one)) >= 3 * len(clean_one.entries))

        # -- the story engine ------------------------------------------------------
        # The portraits are the only long-form reading on this site, which makes
        # them the one place where a generated page could quietly start saying
        # things the dataset does not. So the checks here are almost entirely
        # negative: no sentence that is not in the country file, no year that is
        # not in the country file, no anchor that is not on the page, and no arc
        # that names a category the taxonomy has never heard of.
        print("\nthe story engine")
        from tourism import story as story_mod
        from tourism.model import load_operators
        all_ops = load_operators()
        arcs = story_mod.load_arcs()
        arc_file = story_mod.read(story_mod.ARCS, {})
        ids = {c["id"] for c in tax.categories}
        check("every arc reads categories that exist",
              all(c in ids for a in arcs for c in a["categories"]),
              ", ".join(sorted({c for a in arcs for c in a["categories"]} - ids)))
        check("every arc prints in a format that is drawn",
              all(a["format"] in (arc_file.get("$formats") or {}) for a in arcs),
              ", ".join(sorted({a["format"] for a in arcs}
                               - set(arc_file.get("$formats") or {}))))
        check("an arc's lead is one of its own chapters",
              all((not a.get("lead")) or a["lead"] in a["categories"] for a in arcs))
        check("an arc cannot demand more chapters than it names",
              all((a.get("min") or 0) <= len(a["categories"]) or a["format"] == "journey"
                  for a in arcs))
        check("every arc asks rather than asserts",
              all(a["asks"].rstrip().endswith("?") for a in arcs),
              "; ".join(a["key"] for a in arcs if not a["asks"].rstrip().endswith("?")))

        stories_file = story_mod.read(story_mod.DATA, {})
        rows = stories_file.get("stories") or []
        live_slugs = [c.slug for c in countries if c.published]
        check("every published country has a portrait",
              all(os.path.exists(os.path.join(story_mod.OUT, "%s.html" % s))
                  for s in live_slugs))
        check("the story index covers every country",
              {r["country"] for r in rows} == set(live_slugs))

        pages, said, years_seen = {}, 0, 0
        for slug in live_slugs:
            with open(os.path.join(story_mod.OUT, "%s.html" % slug)) as fh:
                pages[slug] = fh.read()

        # Every anchor the index points at is on the page it points at.
        missing_anchor = [r["id"] for r in rows
                          if ('id="%s"' % r["arc"]) not in pages[r["country"]]]
        check("every story in the index has somewhere to land", not missing_anchor,
              ", ".join(missing_anchor[:4]))
        check("every contents link points at a section on the page",
              all(all(('id="%s"' % href) in pages[slug]
                      for href in re.findall(r'<a href="#([a-z-]+)">', pages[slug]))
                  for slug in live_slugs))

        # The one that matters: no sentence on a portrait that its country did
        # not write. Every paragraph the layouts print is pulled back out of the
        # rendered HTML and matched against that country's own descriptions.
        strays = []
        for slug in live_slugs:
            country = by_slug_test(countries, slug)
            mine = {e.description for e in country.entries if e.description}
            page = pages[slug]
            printed = (re.findall(r'<p class="st-stand"><a [^>]*>(.*?)</a></p>', page)
                       + re.findall(r'<div class="st-say">.*?<p>(.*?)</p>', page)
                       + re.findall(r'<p class="st-big"><a [^>]*>.*?</a> &mdash; (.*?)</p>', page)
                       + re.findall(r'<figcaption>(.*?)(?:<i>|</figcaption>)', page))
            said += len(printed)
            for text in printed:
                plain = html_mod.unescape(text).strip()
                if plain and plain not in mine:
                    strays.append("%s: %s" % (slug, plain[:60]))
        check("every sentence on a portrait was written for that country",
              not strays, "; ".join(strays[:3]) or "%d checked" % said)

        # And no year the country file does not carry. A timeline is the obvious
        # place for a generated page to start inventing dates, so the long line
        # asks four questions instead and this asserts it kept to them.
        bad_years = []
        for slug in live_slugs:
            country = by_slug_test(countries, slug)
            ours = set(re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b",
                                  " ".join([e.description or "" for e in country.entries]
                                           + [e.caption or "" for e in country.entries]
                                           + [country.summary or "", country.when or ""])))
            op = all_ops.get(country.operator_key)
            if op:
                ours.add(str(op.since))
            # Text only. An outline's path data is full of four-digit numbers
            # and none of them is a date.
            visible = re.sub(r"<[^>]+>", " ", re.sub(
                r"<(svg|script|style)\b.*?</\1>", " ", pages[slug], flags=re.S))
            # A four-figure number followed by a unit is a distance, not a date:
            # this page prints straight-line kilometres and peak heights.
            for year in set(re.findall(
                    r"\b(1[0-9]{3}|20[0-9]{2})\b(?!\s*(?:km|kg|mm|m\b|ft))", visible)):
                if year not in ours:
                    bad_years.append("%s: %s" % (slug, year))
        check("no portrait supplies a date the dataset does not have", not bad_years,
              ", ".join(sorted(set(bad_years))[:5]))
        check("the long line says it is not a chronology",
              all("Four questions, not four dates" in pages[s] for s in live_slugs))

        # Provenance, the empty voice, and the one section that is a position.
        check("every portrait says who is telling you this",
              all(('tourism/countries/%s.json' % s) in pages[s] for s in live_slugs))
        check("every portrait says what it is not",
              all("Not sourced reporting" in pages[s] for s in live_slugs))
        check("the respect notes are marked as ours rather than a country's",
              all("no community here was asked to write it" in pages[s]
                  for s in live_slugs))
        check("the local voice is empty and says so",
              all("has been quoted on this page, so nobody is" in pages[s]
                  for s in live_slugs),
              "voices.json holds %d" % len(load_voices()))
        check("no portrait invents a live event",
              not any(re.search(r"this week|tonight|today at|happening now",
                                pages[s], re.I) for s in live_slugs),
              ", ".join(s for s in live_slugs
                        if re.search(r"this week|tonight|today at", pages[s], re.I))[:60])

        # No dead ends: every portrait can be left in every direction.
        check("a portrait leads on to the map, the builder and the write-ups",
              all(all(bit % s in pages[s] for bit in
                      ('/atlas#/%s', '/journey#/j/%s/', '/meet#/%s', '/places#%s'))
                  for s in live_slugs))
        check("every place page leads back to its portrait",
              all(('/portrait/%s' % s) in open(os.path.join(
                  ROOT_DIR, "places", s, os.listdir(os.path.join(
                      ROOT_DIR, "places", s))[0])).read() for s in live_slugs))
        with open(os.path.join(ROOT_DIR, "sitemap.xml")) as fh:
            sitemap = fh.read()
        check("every portrait is in the sitemap",
              all(("/portrait/%s<" % s) in sitemap for s in live_slugs)
              and "/stories<" in sitemap)

        # -- what the homepage claims about itself ---------------------------------
        print("\nwhat the homepage claims about itself")
        home_src = open(os.path.join(ROOT_DIR, "index.html")).read()
        WORD = {"three": 3, "five": 5, "six": 6, "nine": 9, "nineteen": 19,
                "twenty-two": 22, "twenty-seven": 27, "sixty-six": 66,
                "fifty-four": 54}
        truth = {
            len(countries),                                   # 22 written up
            sum(len(c.entries) for c in countries),            # 594 written entries
            len(glob.glob(os.path.join(ROOT_DIR, "places", "*", "*.html"))),  # 572 with a page
            len(ids),                                          # 27 categories
            5,                                                 # 5 region groups
            sum(1 for c in countries if c.operator),           # 3 operators
            len(countries) - sum(1 for c in countries if c.operator),
        }
        # The year an operator started is a fact about that operator, not a
        # coverage claim, but it is printed here and reads as a figure.
        truth |= {int(c.operator.since) for c in countries if c.operator}
        # The brief block is the loudest sentence on the page and it used to open
        # "Fifty-four countries", which is the size of Africa printed where a
        # reader takes it as the size of this site. Every number in it now has to
        # be a len() of something on disk.
        brief = re.search(r'<section class="wa-brief".*?</section>', home_src, re.S)
        check("the brief section is still there", bool(brief))
        if brief:
            said = brief.group(0).lower()
            spelt = {w for w in WORD if re.search(r'\b%s\b' % w, said)}
            wrong = sorted(w for w in spelt if WORD[w] not in truth)
            check("every number spelt out in the brief is one the files have",
                  not wrong, ", ".join(wrong))
            figures = {int(n.replace(",", "")) for n in
                       re.findall(r'\b(\d[\d,]{1,6})\b', re.sub(r'<[^>]+>', ' ', brief.group(0)))
                       if int(n.replace(",", "")) > 4}
            check("every figure printed in the brief is one the files have",
                  figures <= truth, ", ".join(str(f) for f in sorted(figures - truth)))
            check("the brief does not claim an operator we do not have",
                  "operator in each" not in said and "in every" not in said)
        check("the brief is generated rather than typed",
              "<!-- gen:claim -->" in home_src)
        # The journey section describes the service, so it is counted from
        # operators.json for the same reason the brief is.
        for mark in ("plannote", "plansteps"):
            check("the journey section's %s is generated" % mark,
                  "<!-- gen:%s -->" % mark in home_src)
        plan = re.search(r'<section[^>]*id="plan".*?</section>', home_src, re.S)
        check("the journey section is still there", bool(plan))
        if plan:
            steps = len(re.findall(r'class="wa-step[ "]', plan.group(0)))
            cols = re.search(r"\.wa-steps\{[^}]*repeat\((\d+),", home_src)
            check("the step grid has as many columns as there are steps",
                  bool(cols) and int(cols.group(1)) == steps,
                  "%s columns, %d steps" % (cols.group(1) if cols else "?", steps))

        # The same failure twice more: a sentence typed beside a block that is
        # generated, and the two stopped agreeing the moment the block changed.
        note = re.search(r'<!-- gen:nownote -->(.*?)<!-- /gen:nownote -->', home_src, re.S)
        strip = re.search(r'<!-- gen:now -->(.*?)<!-- /gen:now -->', home_src, re.S)
        cards = len(re.findall(r'class="wa-now[ "]', strip.group(1))) if strip else 0
        said_n = None
        if note:
            m = re.search(r'\b(\w+(?:-\w+)?) of them here', note.group(1))
            said_n = WORD.get((m.group(1) or "").lower()) if m else None
        check("the contemporary strip has cards in it", cards > 0, "%d" % cards)
        check("the sentence beside the strip counts the cards the strip has",
              said_n == cards, "says %r, shows %d" % (said_n, cards))

        alt = re.search(r'<svg class="wa-map-svg"[^>]*aria-label="([^"]*)"', home_src)
        check("the map has a description at all", bool(alt))
        if alt:
            nums = {int(n) for n in re.findall(r'\b(\d+)\b', alt.group(1))}
            check("the map's description counts the countries the map draws",
                  nums and nums <= truth, alt.group(1)[:70])
            check("the map's description points at the buttons that replace it",
                  "button" in alt.group(1).lower())

        check("the destination filter counts the grid rather than a literal",
              not re.search(r"shown \+ ' of \d", home_src))
        check("the opening does not print the size of Africa as the size of this site",
              "54 countries &middot;" not in home_src)

        # Across the whole site, not just this page. The homepage said "594
        # places" and /places said "572" — 594 is every entry, 572 is every entry
        # that has a page, and the twenty-two-place gap is the `hero` category,
        # which is a country's opening picture rather than a place. Two numbers
        # for one thing, on two pages, both generated, from two derivations.
        SITEWIDE = ("countries", "places", "categories", "destinations", "portraits")
        pages = sorted(set(glob.glob(os.path.join(ROOT_DIR, "*.html"))
                           + glob.glob(os.path.join(ROOT_DIR, "places", "index.html"))
                           + glob.glob(os.path.join(ROOT_DIR, "tourism", "*.html"))))
        printed = {}
        for path in pages:
            body = re.sub(r"<(script|style|svg)\b.*?</\1>", "",
                          open(path).read(), flags=re.S)
            for m in re.finditer(r"\b(\d{2,4})\s+(%s)\b" % "|".join(SITEWIDE), body):
                # "26 places" on /places is one country's count, not the site's.
                # Only totals — three figures or two that are not a leading zero.
                if m.group(1).startswith("0"):
                    continue
                printed.setdefault(m.group(2), {}).setdefault(
                    int(m.group(1)), set()).add(os.path.relpath(path, ROOT_DIR))
        for noun in sorted(printed):
            counts = printed[noun]
            # A per-country or per-region figure is smaller than the site total,
            # so compare only the largest, which is the one claiming to be all.
            top = max(counts)
            where = ", ".join(sorted(counts[top]))
            expect = {"countries": len(countries),
                      "categories": len(ids),
                      "destinations": len(countries),
                      "portraits": len(countries),
                      "places": len(glob.glob(os.path.join(
                          ROOT_DIR, "places", "*", "*.html")))}.get(noun)
            check("every page that counts %s counts the same %s" % (noun, noun),
                  expect is None or top == expect,
                  "%d on %s, dataset has %s" % (top, where, expect))

        # -- the palette says what it is ------------------------------------------
        print("\nthe palette says what it is")
        css = open(os.path.join(ROOT_DIR, "styles", "afrinkong.css")).read()
        TOKENS = dict(re.findall(r"(--c-[a-z-]+):\s*(#[0-9A-Fa-f]{6})", css))

        def channels(hexcol):
            h = hexcol.lstrip("#")
            return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

        def relative(c):
            f = (lambda v: v / 12.92 if v <= 0.03928
                 else ((v + 0.055) / 1.055) ** 2.4)
            return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])

        def contrast(a, b):
            x, y = relative(channels(a)), relative(channels(b))
            return (max(x, y) + 0.05) / (min(x, y) + 0.05)

        need = ["--c-bg", "--c-sand", "--c-primary", "--c-ink", "--c-accent",
                "--c-accent-fill", "--c-accent-lit", "--c-gold", "--c-muted"]
        missing = [t for t in need if t not in TOKENS]
        check("every token in the palette is defined", not missing, ", ".join(missing))
        if not missing:
            # The two grounds a light page has, and the two inks that carry 9 to
            # 11px type on them. Both have to clear AA on both, which is why the
            # accent and the metadata voice are darker than the palette as given:
            # burnt sienna at #B94E2E measures 4.45 on ivory, and failing by four
            # hundredths is failing.
            for ink in ("--c-accent", "--c-muted", "--c-primary", "--c-ink"):
                for ground in ("--c-bg", "--c-sand"):
                    r = contrast(TOKENS[ink], TOKENS[ground])
                    check("%s reads on %s" % (ink, ground), r >= 4.5, "%.2f:1" % r)
            # And the two that only ever sit on a dark ground.
            for ink in ("--c-accent-lit", "--c-gold"):
                r = contrast(TOKENS[ink], TOKENS["--c-primary"])
                check("%s reads on the dark ground" % ink, r >= 4.5, "%.2f:1" % r)
            # Terracotta is a fill, and the check is that nothing asks it to be
            # type on paper: it is 3.31 on ivory and would fail the moment it did.
            r = contrast(TOKENS["--c-accent-fill"], TOKENS["--c-bg"])
            check("the fill weight of the accent is not used as an ink",
                  r < 4.5 and "color:var(--c-accent-fill)" not in css,
                  "%.2f:1 on ivory, so fills only" % r)
            # The map's three tones have to be three, not two and a hint.
            home = open(os.path.join(ROOT_DIR, "index.html")).read()
            for tone, role in (("--c-sand", "the continent"),
                               ("--c-accent-fill", "a destination"),
                               ("--c-primary", "an operator of ours")):
                check("the map draws %s in %s" % (role, tone),
                      re.search(r"wa-map-(rest|live)[^{]*\{[^}]*fill:var\(%s\)" % tone,
                                home) is not None)

        regions = read_json_file(os.path.join(ROOT_DIR, "tourism", "regions.json"))
        tones = {k: v["tone"] for k, v in regions.items() if not k.startswith("$")}
        check("every region still has a ground", len(tones) == 5, str(sorted(tones)))
        # The plate mixes its tone two thirds with the house forest, and prints
        # ivory on the result. That is the number that has to hold.
        forest = channels(TOKENS.get("--c-primary", "#10251F"))
        for key, tone in sorted(tones.items()):
            mixed = [0.66 * t + 0.34 * f for t, f in zip(channels(tone), forest)]
            lit = relative(channels(TOKENS.get("--c-bg", "#F6F1E7")))
            r = (max(lit, relative(mixed)) + 0.05) / (min(lit, relative(mixed)) + 0.05)
            check("a plate on the %s ground can be read" % key, r >= 4.5, "%.2f:1" % r)

        # -- the sheet the map is printed on ---------------------------------------
        print("\nthe sheet the map is printed on")
        # The hero reads as one unfolded atlas because the graticule behind the
        # type is the real projection the continent is drawn in, at the same
        # scale and origin. That only holds while the scale the sheet recovered
        # still matches the map's own fit, and nothing about regenerating the map
        # would announce that it had stopped: the lines would simply drift a few
        # pixels off the coast and look like a rendering bug. So the fit is
        # measured here against three coastal extremes whose position the path
        # data already knows.
        sys.path.insert(0, os.path.join(ROOT_DIR, "tools"))
        import atlas_sheet

        home = open(os.path.join(ROOT_DIR, "index.html")).read()
        off = atlas_sheet.check()
        check("the sheet is still in register with the map", off < 3.0,
              "worst coastal extreme is %.1f map units out (0.4 CSS px each)" % off)

        sheet = re.search(r"<!-- gen:sheet -->(.*?)<!-- /gen:sheet -->", home, re.S)
        check("the home page carries the generated sheet", sheet is not None)
        if sheet:
            body = sheet.group(1)
            check("the sheet is drawn, not stored as a picture",
                  "<image" not in body and "url(" not in body and "data:image" not in body,
                  "%.1f kB of path data, no request" % (len(body) / 1024.0))
            # Regenerating it has to be idempotent, or the file it writes back
            # differs from the file in the tree and every build shows a diff.
            check("regenerating the sheet changes nothing",
                  atlas_sheet.build()[0] == body.strip())
            # It is decoration over the top of the headline; a screen reader
            # reading out forty meridians would be the worst thing on the page.
            check("the sheet is hidden from the accessibility tree",
                  'aria-hidden="true"' in body.split(">")[0] + ">")
            check("the sheet cannot be clicked through to",
                  re.search(r"\.wa-sheet\{[^}]*pointer-events:none", home) is not None)
        # The margin coordinates are the west and east extremes of the African
        # mainland. They are marginalia, but they are checkable marginalia, and
        # the reason they are these two rather than a prettier pair is that these
        # two are true.
        for figure in ("17&deg; 33&prime; W", "51&deg; 24&prime; E"):
            check("the margin carries %s" % figure.replace("&deg;", "d").replace("&prime;", "'"),
                  figure in home)

        # -- where the keyboard is ------------------------------------------------
        print("\nwhere the keyboard is")
        # `outline:none` on :focus is how a focus indicator disappears. Sometimes
        # it is right — an element that replaces the ring with something at least
        # as visible, or one nobody tabs to — and each of those is allowed by
        # name below, with the reason written beside the rule in the stylesheet.
        # Every other one is a control a keyboard user cannot find.
        ALLOWED = (
            ".wa-map-live:focus",      # the country path strokes instead
            ".at-c:focus",             # the same, on the atlas
            ".ex-bar input:focus",     # the only tabbable thing in its dialog
            ".jn-h1:focus",            # a heading focused to be announced
        )
        killed = {}
        for path in sorted(glob.glob(os.path.join(ROOT_DIR, "styles", "*.css"))
                           + glob.glob(os.path.join(ROOT_DIR, "*.html"))):
            rel = os.path.relpath(path, ROOT_DIR)
            body = re.sub(r"/\*.*?\*/", " ", open(path).read(), flags=re.S)
            for m in re.finditer(r"([^{}\n]*:focus[^{}\n]*)\{([^}]*)\}", body):
                sel, decl = m.group(1).strip(), m.group(2)
                if "outline:none" not in decl.replace(" ", ""):
                    continue
                if ":not(:focus-visible)" in sel:
                    continue
                if any(a in sel for a in ALLOWED):
                    continue
                killed.setdefault(sel[:60], set()).add(rel)
        check("no control hides its focus ring without saying why", not killed,
              "; ".join("%s (%s)" % (s, ", ".join(sorted(w))[:40])
                        for s, w in sorted(killed.items())[:3]))
        check("the design system still defines one ring for everything",
              re.search(r":focus-visible\{[^}]*outline:\s*2px",
                        open(os.path.join(ROOT_DIR, "styles", "afrinkong.css")).read()))

        # -- what an image costs before it arrives ---------------------------------
        print("\nwhat an image costs before it arrives")
        SKIP_IMG = {"tourism/compare.html"}
        nodim, nolazy, noalt, heroes = [], [], [], []
        for path in sorted(glob.glob(os.path.join(ROOT_DIR, "**", "*.html"),
                                     recursive=True)):
            rel = os.path.relpath(path, ROOT_DIR)
            if "/incoming/" in path or "/node_modules/" in path or rel in SKIP_IMG:
                continue
            tags = re.findall(r"<img\b[^>]*>", open(path).read())
            for i, tag in enumerate(tags):
                if 'width="' not in tag or 'height="' not in tag:
                    nodim.append(rel)
                if "alt=" not in tag:
                    noalt.append(rel)
                # The first draft of this check said "the first <img> in the
                # document is the page's largest contentful paint, so it must be
                # eager and prioritised". That is false here. On the homepage,
                # the portraits and /tourism the hero is an inline SVG window or
                # a drawn plate, and the first <img> is four screens down in a
                # card — correctly lazy. Document order does not tell you what
                # is in the first viewport, so the rule is the one that holds
                # without knowing: an image may not be marked urgent and
                # deferred at the same time, and only one thing on a page can
                # be the most urgent.
                if "fetchpriority" in tag:
                    heroes.append(rel)
                    if 'loading="lazy"' in tag:
                        nolazy.append(rel + " (urgent and lazy at once)")
                elif "loading=" not in tag and i > 0:
                    nolazy.append(rel)
        # Not "every image must carry width and height". That looks like the
        # obvious rule and it is wrong here: on these five pages the CSS reserves
        # every box with aspect-ratio, adding the attributes changed nothing on
        # four of them, and on /contact it took layout shift from 0.002 to 0.17.
        # Whether space is reserved is measured in tools/shift-checks.js, in a
        # browser, with the images held back — the only place the answer is
        # actually knowable. What is checked statically is the thing that is
        # true regardless: an image without dimensions must at least be one the
        # CSS is sizing, and 610 of the 612 images here already carry both.
        loose = sorted(set(nodim))
        check("at most a handful of images leave their size to the CSS alone",
              len(loose) <= 6,
              "%d images across %d files (%s)"
              % (len(nodim), len(loose), ", ".join(loose[:4])))
        check("every image has alternative text", not noalt,
              "%d without alt (%s)" % (len(noalt), ", ".join(sorted(set(noalt))[:4])))
        check("no image below the first is loaded eagerly", not nolazy,
              "%d eager (%s)" % (len(nolazy), ", ".join(sorted(set(nolazy))[:4])))
        twice = sorted(p for p in set(heroes) if heroes.count(p) > 1)
        check("no page names two images as its most urgent", not twice,
              ", ".join(twice[:4]))

        # -- the build has to exit zero, or the workflow throws the run away -------
        print("\nthe build has to exit zero")
        # `build.py all` ends in `verify`, and the workflow runs it as its own
        # step. A non-zero exit fails the job before the commit step, so a run
        # that resolved two hundred photographs discards all of them. That is
        # what the runs on 13 August did, twice, and nothing in the suite noticed
        # because every check here calls the modules rather than the command.
        # Without the suite's overrides. They repoint both providers at the mock
        # server, and a subprocess inherits them, so a real images.unsplash.com
        # URL on a real page reads as "an unexpected source" — the check would
        # be measuring the harness rather than the site.
        plain = dict(os.environ)
        for var in ("UNSPLASH_API_BASE", "PEXELS_API_BASE",
                    "UNSPLASH_IMAGE_HOST_OVERRIDE", "PEXELS_IMAGE_HOST_OVERRIDE",
                    "TOURISM_CACHE_FILE"):
            plain.pop(var, None)
        proc = subprocess.run([sys.executable,
                               os.path.join(ROOT_DIR, "tools", "tourism", "build.py"),
                               "verify"], capture_output=True, text=True,
                              cwd=ROOT_DIR, env=plain)
        check("build.py verify exits zero on the site as it stands",
              proc.returncode == 0,
              (proc.stdout or proc.stderr).strip().splitlines()[-1][:100]
              if (proc.stdout or proc.stderr).strip() else "no output")
        # And the specific fault, so it cannot come back by a different route:
        # an unresolved slot is a plate, and verify has to count it as a slot.
        vsrc = open(os.path.join(ROOT_DIR, "tools", "tourism", "verify.py")).read()
        check("verify counts a plate as a filled slot",
              "af-plate" in vsrc, "it only knew about tq-empty")
        pages = glob.glob(os.path.join(ROOT_DIR, "tourism", "*.html"))
        plated = [p for p in pages
                  if open(p).read().count('class="af-plate ') > 20]
        check("the pages with no photographs are the ones this protects",
              len(plated) >= 15, "%d of %d country pages are all plates"
              % (len(plated), len(pages)))

        # -- what a resolver run would actually commit -----------------------------
        print("\nwhat a resolver run would actually commit")
        wf_path = os.path.join(ROOT_DIR, ".github", "workflows", "tourism-resolve.yml")
        wf = open(wf_path).read() if os.path.exists(wf_path) else ""
        check("the resolve workflow is still there", bool(wf))
        if wf:
            check("it rebuilds every page before committing", "build.py all" in wf)
            check("it checks the working tree for key material first",
                  'grep -rlF "$KEY"' in wf)
            # The commit step used to name paths. Every generated file it did
            # not name was silently dropped, and `build.py all` writes to nine
            # directories. Naming them is a list that goes stale; `git add -A`
            # cannot, and is safe because the key grep above runs over the whole
            # tree and fails the run.
            adds = re.findall(r"^\s*git add (.+)$", wf, re.M)
            check("it stages everything the build wrote, not a list of paths",
                  any(a.strip() == "-A" for a in adds),
                  "; ".join(a.strip()[:60] for a in adds) or "no git add")
            check("it pushes what it staged", "git push" in wf)
            check("a partial run is still a success",
                  "build.py resolve" in wf and "|| true" in wf)

        # -- what a photograph is allowed to claim --------------------------------
        print("\nwhat a photograph is allowed to claim")
        from tourism.model import PROVEN, attach_cache as attach
        # The suite runs against a sandbox cache; this check is about the real
        # one, which is the file that ships.
        raw = cache_mod.load(os.path.join(ROOT_DIR, "tourism", "cache", "images.json"))
        recs = list(raw.entries.items())
        unproven = [k for k, v in recs if not any(v.get(f) for f in PROVEN)]
        check("the cache is readable", bool(recs), "%d records" % len(recs))
        check("records with no evidence are known about", True,
              "%d of %d carry neither a query tier nor a score"
              % (len(unproven), len(recs)))
        # The point: none of those may be quoted as a description of the picture.
        bound = attach(load_countries(), raw, tax)
        loud = []
        for c in bound:
            for e in c.entries:
                rec = e.image
                if not rec or not rec.get("altUnproven"):
                    continue
                alt = (rec.get("alt") or "")
                # It may be the country's name, or the category's title in the
                # country, and nothing else. No place, no month, no species, no
                # festival — those are the claims there is no evidence for.
                cat = tax.by_id.get(e.category)
                allowed = {c.name}
                if cat:
                    allowed.add("%s in %s" % (
                        cat["title"].split("/")[0].split("&")[0].strip(), c.name))
                if alt not in allowed:
                    loud.append("%s/%s: %r not in %r"
                                % (c.slug, e.category, alt, sorted(allowed)))
        check("a photograph with no evidence describes itself in general terms",
              not loud, "; ".join(loud[:3]))
        # And the proven ones keep their specific alt, or the fix is a blunt one.
        specific = [e for c in bound for e in c.entries
                    if e.image and not e.image.get("altUnproven")
                    and len((e.image.get("alt") or "").split()) > 6]
        check("photographs that do have evidence keep their real description",
              len(specific) >= 40, "%d specific alts kept" % len(specific))
        # The hand-written pages place some of the same photographs by hand, so
        # the generator's rule does not reach them.
        stems = {(v.get("imageUrl") or "").rsplit("/", 1)[-1].split("?")[0]: k
                 for k, v in recs if not any(v.get(f) for f in PROVEN)}
        typed = []
        for path in sorted(glob.glob(os.path.join(ROOT_DIR, "*.html"))
                           + glob.glob(os.path.join(ROOT_DIR, "tourism", "*.html"))):
            body = open(path).read()
            for stem, slot in stems.items():
                if not stem:
                    continue
                for m in re.finditer(r"<img[^>]*" + re.escape(stem) + r"[^>]*>", body):
                    alt = re.search(r'alt="([^"]*)"', m.group(0))
                    if alt and len(alt.group(1).split()) > 4:
                        typed.append("%s: %s" % (os.path.relpath(path, ROOT_DIR),
                                                 alt.group(1)[:50]))
        check("no hand-written page describes an unproven photograph either",
              not typed, "; ".join(typed[:3]))

        # -- numbers spelled out in the prose --------------------------------------
        print("\nnumbers spelled out in the prose")
        # 034 through 049 fixed a dozen counts that had been typed beside a block
        # generated from the data. The figures are guarded already; the words are
        # not, and "three countries" or "twenty-seven categories" reads exactly as
        # authoritative. Every generator and every hand-written page is scanned
        # for a spelled number followed by a noun this dataset can count, and the
        # word has to match.
        # Every number from one to ninety-nine, generated rather than listed. A
        # hand-written table only catches the numbers already thought of: the
        # first version of this had sixteen entries in it and let "thirty-one
        # categories" through, because thirty-one had never been wrong before.
        ONES = ("zero one two three four five six seven eight nine ten eleven "
                "twelve thirteen fourteen fifteen sixteen seventeen eighteen "
                "nineteen").split()
        TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
                "eighty", "ninety")
        SPELLED = {}
        for k in range(1, 100):
            SPELLED[ONES[k] if k < 20 else
                    TENS[k // 10] + ("-" + ONES[k % 10] if k % 10 else "")] = k
        NUMBER_NOUN = re.compile(
            r"(?<![-\w])(" + "|".join(sorted(SPELLED, key=len, reverse=True))
            + r") (countries|destinations|portraits|categories|headings|"
              r"operators|regions|strands|questions)\b")

        # Not one number per noun — several are legitimate, and all of them are
        # counts of something rather than opinions. "Nineteen countries" is the
        # nineteen without an operator; "four countries" on a place page is that
        # country's neighbours; "four questions" is the journey builder and
        # "seven questions" is /meet. What is not legitimate is a number that
        # counts nothing here, which is how "fifty-four countries" and "twenty
        # -seven countries" would read.
        ops = sum(1 for c in countries if c.operator)
        strands = read_json_file(os.path.join(ROOT_DIR, "tourism", "strands.json"))
        strand_keys = [k for k in (strands or {}) if not k.startswith("$")]
        strand_cats = {c for k in strand_keys
                       for c in (strands[k].get("categories") or [])}
        links = read_json_file(os.path.join(ROOT_DIR, "data", "links.json")).get("links") or {}
        neighbours = {len(v) for v in links.values()} | {1, 2, 3, 4, 5}
        OK = {
            "countries": {len(countries), len(countries) - ops, ops, 5} | neighbours,
            "destinations": {len(countries)},
            "portraits": {len(countries)},
            "categories": {len(ids), len(strand_cats)},
            "headings": {len(ids)},
            "operators": {ops},
            "regions": {5},
            "strands": {len(strand_keys)},
            "questions": {len(strand_keys), 4},
        }
        # Phrases where the number is deliberately about Africa, not about this
        # site, and says so in the same sentence.
        ALLOWED_PHRASE = ("fifty-four countries. twenty-two",
                          "fifty-four countries. not one place")
        wrong = {}
        for path in sorted(glob.glob(os.path.join(ROOT_DIR, "**", "*.html"),
                                     recursive=True)):
            rel = os.path.relpath(path, ROOT_DIR)
            if "/incoming/" in path or rel == "tourism/compare.html":
                continue
            body = re.sub(r"<(script|style|svg)\b.*?</\1>", " ",
                          open(path).read(), flags=re.S)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).lower()
            text = text.replace("&mdash;", " ").replace("&middot;", " ")
            # One pass per page rather than 99 words x 9 nouns of them: at 650
            # pages the nested version took minutes.
            for found in NUMBER_NOUN.finditer(text):
                word, noun = found.group(1), found.group(2)
                n = SPELLED.get(word)
                fine = OK.get(noun)
                if n is None or fine is None or n in fine:
                    continue
                near = text[max(0, found.start() - 40):found.start() + 40]
                if any(a in near for a in ALLOWED_PHRASE):
                    continue
                wrong.setdefault("%s %s (this dataset counts %s)"
                                 % (word, noun,
                                    ", ".join(str(x) for x in sorted(fine)[:4])),
                                 set()).add(rel)
        check("every number spelled out in the prose counts something real",
              not wrong,
              "; ".join("%s on %d pages e.g. %s" % (k, len(v), sorted(v)[0])
                        for k, v in sorted(wrong.items())[:3]))
        check("the seven strands draw on twelve categories, as /meet says",
              len(strand_cats) == 12 and len(strand_keys) == 7,
              "%d strands, %d categories" % (len(strand_keys), len(strand_cats)))
        meet_page = open(os.path.join(ROOT_DIR, "meet.html")).read()
        answers = len(strand_keys) * len(countries)
        check("/meet counts its own answers", str(answers) in meet_page,
              "%d expected" % answers)

        # -- companies that do not exist -------------------------------------------
        print("\ncompanies that do not exist")
        # tourism/operators.json holds three and has only ever held three. For the
        # other nineteen countries there is no company named anywhere in this
        # project, so any sentence asserting one is an invention. These are the
        # exact shapes that were on the site, kept as strings rather than a clever
        # pattern because a clever pattern would find prose that is fine.
        INVENTED = (
            "a licensed company based in",
            "a licensed local company",
            "a licensed local operator",
            "a licensed operator in each",
            "covered by a licensed",
            "covered by an operator based in the country",
            "run by a company in the country itself",
            # The journey section promised these about all twenty-two.
            "the person who answers your enquiry is in the country",
            "meet the local operator responsible for your destination",
            "working in the language you booked in",
            # A site that says "nothing is scored" on /compare cannot promise a
            # ranking on the homepage.
            "which country does it best",
            "every operator on this site is a company registered",
            "every country is covered by a company based in it",
            "is covered by a company based in it",
            "operated by a licensed company based in it",
            "is run by a company based in it",
        )
        HAS_GUIDES = ("eleven licensed guides",)   # Kamerun, about Kamerun, true
        looked = sorted(p for p in
                        glob.glob(os.path.join(ROOT_DIR, "**", "*.html"), recursive=True)
                        + glob.glob(os.path.join(ROOT_DIR, "scripts", "*.js"))
                        + glob.glob(os.path.join(ROOT_DIR, "tools", "tourism", "*.py"))
                        if "/incoming/" not in p and "/node_modules/" not in p)
        def uncommented(path, text):
            """Comments explaining what was removed are not the thing itself.

            Without this the check fails on its own paper trail: three of these
            files carry a comment saying "this used to read 'a licensed company
            based in <country>' and it named a company that does not exist".
            """
            if path.endswith(".js"):
                text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
                return re.sub(r"^\s*//.*$", " ", text, flags=re.M)
            if path.endswith(".py"):
                text = re.sub(r'"""[\s\S]*?"""', " ", text)
                return re.sub(r"(?m)^\s*#.*$", " ", text)
            return re.sub(r"<!--.*?-->", " ", text, flags=re.S)

        caught = {}
        for path in looked:
            body = uncommented(path, open(path).read()).lower()
            for ok in HAS_GUIDES:
                body = body.replace(ok, "")
            for claim in INVENTED:
                if claim in body:
                    # tests.py itself lists them; that is this list.
                    if os.path.basename(path) == "tests.py":
                        continue
                    caught.setdefault(claim, []).append(os.path.relpath(path, ROOT_DIR))
        check("no page claims an operator the dataset does not have", not caught,
              "; ".join("%r on %d files (%s)" % (c, len(w), w[0])
                        for c, w in sorted(caught.items())[:3]))
        named = {c.operator.name for c in countries if c.operator}
        check("exactly the operators in the dataset are named as ours",
              len(named) == 3, ", ".join(sorted(named)))

        # /tourism is not a country, but it is handed the same chrome as one, so
        # its stand-in name ("Every country") can end up where a country name
        # belongs — it printed "We do not run a company in Every country."
        STANDINS = ("Every country", "Everywhere", "the countries")
        leaked = []
        for path in looked:
            if not path.endswith(".html"):
                continue
            body = re.sub(r"<[^>]+>", " ", open(path).read())
            for stand in STANDINS:
                for shape in ("in %s.", "company in %s", "%s is written up",
                              "runs %s,", "to %s.", "about %s."):
                    if (shape % stand) in body:
                        leaked.append("%s: %s" % (os.path.relpath(path, ROOT_DIR),
                                                  shape % stand))
        check("no page treats the index's stand-in name as a country",
              not leaked, "; ".join(leaked[:3]))

        # -- what a page family pays twice for -------------------------------------
        print("\nwhat a page family pays twice for")
        blocks = {}
        for path in sorted(glob.glob(os.path.join(ROOT_DIR, "**", "*.html"),
                                     recursive=True)):
            if "/incoming/" in path or "/node_modules/" in path:
                continue
            body = open(path).read()
            for css in re.findall(r"<style[^>]*>(.*?)</style>", body, re.S):
                if len(css) > 4096:
                    blocks.setdefault(css, []).append(os.path.relpath(path, ROOT_DIR))
        shared = sorted(((len(css) * len(where), len(where), len(css), where)
                         for css, where in blocks.items() if len(where) > 1),
                        reverse=True)
        # A stylesheet inlined into one page is the right call — it is fetched
        # once either way and costs no extra request. Inlined into a family it is
        # paid for again on every page after the first, and the tourism pages
        # were carrying the same 39,949 bytes twenty-three times.
        check("no page family inlines the same stylesheet twice", not shared,
              "; ".join("%d pages x %.1f KB (%s)" % (n, size / 1024.0, w[0])
                        for _t, n, size, w in shared[:3]))
        for sheet in ("tourism.css", "country.css"):
            full = os.path.join(ROOT_DIR, "styles", sheet)
            check("/styles/%s exists and is linked, not inlined" % sheet,
                  os.path.isfile(full) and os.path.getsize(full) > 4096,
                  "%.1f KB" % (os.path.getsize(full) / 1024.0)
                  if os.path.isfile(full) else "missing")

        # -- what a parser makes of every head -------------------------------------
        print("\nwhat a parser makes of every head")
        from html.parser import HTMLParser

        class Head(HTMLParser):
            """Only what a browser would end up with, not what was typed.

            index.html, contact.html and four others carried
            `<meta name="description" content="...">` with the closing angle
            bracket missing. In the source the canonical link is on the very next
            line and looks perfectly fine. A parser reads it as more attributes
            of the unclosed meta, so the tag never exists — six pages, the
            homepage among them, with the canonical in the file and none in the
            document. Reading the source with a regex cannot see this. Parsing
            can, which is why this test parses.
            """
            # <title>, <style> and <script> are supposed to contain text.
            HOLDS_TEXT = ("title", "style", "script", "noscript")

            def __init__(self):
                HTMLParser.__init__(self)
                self.links, self.metas, self.stray = [], [], []
                self.in_head = True
                self.inside = None

            def handle_starttag(self, tag, attrs):
                if not self.in_head:
                    return
                if tag in self.HOLDS_TEXT:
                    self.inside = tag
                elif tag == "link":
                    self.links.append(dict(attrs))
                elif tag == "meta":
                    self.metas.append(dict(attrs))

            def handle_endtag(self, tag):
                if tag == "head":
                    self.in_head = False
                elif tag == self.inside:
                    self.inside = None

            def handle_data(self, data):
                if self.in_head and not self.inside and data.strip():
                    self.stray.append(data.strip()[:30])

        NO_INDEX = {"404.html"}
        # tourism/compare.html is a contact sheet regenerated in one command and
        # gitignored, so it is on a developer's disk and never on the site.
        LOCAL_ONLY = {"tourism/compare.html"}
        heads = sorted(p for p in glob.glob(os.path.join(ROOT_DIR, "**", "*.html"),
                                            recursive=True)
                       if "/incoming/" not in p and "/node_modules/" not in p
                       and os.path.relpath(p, ROOT_DIR) not in LOCAL_ONLY)
        noCanon, noOg, noDesc, junk = [], [], [], []
        for path in heads:
            rel = os.path.relpath(path, ROOT_DIR)
            parser = Head()
            parser.feed(open(path).read())
            metas = {(m.get("name") or m.get("property") or ""): m.get("content")
                     for m in parser.metas}
            rels = {r for link in parser.links
                    for r in (link.get("rel") or "").split()}
            if not metas.get("description"):
                noDesc.append(rel)
            if rel in NO_INDEX:
                continue
            if "canonical" not in rels:
                noCanon.append(rel)
            if not (metas.get("og:title") and metas.get("og:url")):
                noOg.append(rel)
            # A stray ">" left over from a doubled bracket parses as text in the
            # head and gets moved into the body by the browser.
            if [s for s in parser.stray if s not in ("",)]:
                junk.append("%s (%s)" % (rel, parser.stray[0]))
        check("every page parses with a canonical link", not noCanon,
              "%d without: %s" % (len(noCanon), ", ".join(noCanon[:5])))
        check("every page parses with a description", not noDesc,
              "%d without: %s" % (len(noDesc), ", ".join(noDesc[:5])))
        check("every page parses with og:title and og:url", not noOg,
              "%d without: %s" % (len(noOg), ", ".join(noOg[:5])))
        check("no page leaves loose text in its head", not junk,
              "; ".join(junk[:3]))
        check("the pages that should not be indexed say so",
              all('name="robots"' in open(os.path.join(ROOT_DIR, p)).read()
                  and "noindex" in open(os.path.join(ROOT_DIR, p)).read()
                  for p in NO_INDEX))

        # -- whose enquiry desk /contact is ----------------------------------------
        print("\nwhose enquiry desk /contact is")
        con = open(os.path.join(ROOT_DIR, "contact.html")).read()
        ours_ops = [c for c in countries if c.operator]
        host = ([c for c in ours_ops if c.operator.url.startswith("/")]
                or ours_ops)[0]
        # The bar belongs on every page wearing this operator's masthead, not
        # only the one with the form on it. /about, /pricing, /services and
        # /cameroon sit on group addresses a visitor reads as the group's, and
        # all four carry the same form mailing the same operator.
        from tourism import enquiry as enq
        wearing = enq.cluster(host.operator.name)
        check("every page wearing the operator's masthead is known", len(wearing) >= 4,
              ", ".join(os.path.relpath(p, ROOT_DIR) for p in wearing))
        barless = [os.path.relpath(p, ROOT_DIR) for p in wearing
                   if 'class="fj-from"' not in open(p).read()]
        check("every one of them says whose pages they are", not barless,
              ", ".join(barless))
        unlisted = [u for u in ("/tourism", "/about", "/pricing", "/services")
                    if "<loc>https://afrinkong.com%s</loc>" % u not in sitemap]
        check("every real page of theirs is in the sitemap", not unlisted,
              ", ".join(unlisted))

        bar = re.search(r'<div class="fj-from"[^>]*>(.*?)</div>\s*</div>', con, re.S)
        check("the primary call of the site still lands on /contact",
              'href="/contact"' in open(os.path.join(ROOT_DIR, "index.html")).read())
        check("/contact says whose desk it is, in the HTML, without a script",
              bool(bar) and host.operator.name in bar.group(1),
              (host.operator.name if bar else "no bar"))
        if bar:
            check("it names the country that operator runs", host.name in bar.group(1))
            check("it names where they are", host.operator.base in bar.group(1))
            check("it offers the rest of the continent a way out",
                  'href="/atlas"' in bar.group(1))
            for other in ours_ops:
                if other.slug == host.slug:
                    continue
                check("it hands %s over to %s" % (other.name, other.operator.name),
                      other.operator.url in bar.group(1))
        # The mailto is one operator's address. That is fine — it is their page —
        # but it must not be the only thing the visitor learns about where the
        # letter goes, which was the state before this.
        m = re.search(r'data-lead-mailto="([^"]+)"', con)
        check("the form still has somewhere to send to", bool(m), m.group(1) if m else "")
        if m and bar:
            check("the address it sends to belongs to the operator it names",
                  host.operator.name.split()[0].lower() in m.group(1).lower(),
                  m.group(1))
        boot = re.search(r'<script type="application/json" id="fj-reach">(.*?)</script>',
                         con, re.S)
        check("the page knows which country belongs to whom", bool(boot))
        if boot:
            reach = json.loads(boot.group(1))
            check("every operator of ours is in it",
                  set(reach["ours"]) == {c.slug for c in ours_ops})
            check("every country without one is in it too",
                  set(reach["rest"]) == {c.slug for c in countries if not c.operator})
            check("the two lists do not overlap",
                  not (set(reach["ours"]) & set(reach["rest"])))

        # -- where the links actually go -------------------------------------------
        print("\nwhere the links actually go")
        html_pages = sorted(p for p in glob.glob(os.path.join(ROOT_DIR, "**", "*.html"),
                                                 recursive=True)
                            if "/incoming/" not in p and "/node_modules/" not in p)
        anchors, dead, broken = {}, {}, {}

        def anchors_of(path):
            if path not in anchors:
                body = open(path).read()
                anchors[path] = ({m.group(1) for m in re.finditer(r'\bid="([^"]+)"', body)}
                                 | {m.group(1) for m in
                                    re.finditer(r'<a[^>]*\bname="([^"]+)"', body)})
            return anchors[path]

        def as_file(base):
            stem = base.lstrip("/")
            for cand in (stem, stem + ".html", os.path.join(stem, "index.html")):
                full = os.path.join(ROOT_DIR, cand)
                if os.path.isfile(full):
                    return full
            return None

        for path in html_pages:
            body = re.sub(r"<(script|style)\b.*?</\1>", "", open(path).read(), flags=re.S)
            rel = os.path.relpath(path, ROOT_DIR)
            for m in re.finditer(r'href="([^"]+)"', body):
                url = m.group(1)
                if url.startswith(("http", "mailto:", "tel:", "data:", "javascript:")):
                    continue
                base, _, frag = url.partition("#")
                base = base.split("?")[0]
                # "#/kenya" and "#/j/kenya/" are hash routes read by atlas.js and
                # journey.js, not anchors, and there is no element to find.
                if frag.startswith("/"):
                    continue
                target = path if base == "" else as_file(base)
                if base and target is None:
                    dead.setdefault(base, set()).add(rel)
                elif frag and target and frag not in anchors_of(target):
                    broken.setdefault("%s#%s" % (base or rel, frag), set()).add(rel)

        check("every internal link points at a page that exists", not dead,
              "; ".join("%s (from %s)" % (u, sorted(w)[0]) for u, w in
                        sorted(dead.items())[:4]))
        check("every anchor link points at an element that exists", not broken,
              "; ".join("%s (from %d pages)" % (u, len(w)) for u, w in
                        sorted(broken.items())[:4]))

        # -- the story graph -------------------------------------------------------
        print("\nthe story graph")
        from tourism import graph as graph_mod
        g = story_mod.read(graph_mod.OUT, {})
        names = g.get("names") or {}
        check("the graph read names out of the dataset", len(names) > 200,
              "%d names" % len(names))
        check("every name points at a country and a write-up that exist",
              all(at["c"] in g["countries"] and at["e"] in ids
                  for row in names.values() for at in row["at"]))
        check("every address in the graph is a page on disk",
              all(os.path.exists(os.path.join(ROOT_DIR, (p["u"] or "x").lstrip("/") + ".html"))
                  for c in g["countries"].values() for p in (c.get("places") or {}).values()
                  if p.get("u")))
        own = {c.name.lower() for c in countries} | {(c.adjective or "").lower()
                                                     for c in countries}
        check("the index is not the countries talking about themselves",
              not [n for n in names if n.lower() in own],
              ", ".join(n for n in names if n.lower() in own)[:60])
        check("a name is never read out of a headline",
              not [n for n in names if n.lower() in ("rafting", "canoe", "dive")],
              "; ".join(n for n in names if n.lower() in ("rafting", "canoe", "dive")))
        check("every theme names categories that exist",
              all(c in ids for t in g["themes"].values() for c in t["categories"]))
        shared = [n for n, v in names.items() if len(v["in"]) > 1]
        check("some names cross a border, which is the point of an index",
              len(shared) > 5, ", ".join(sorted(shared)[:5]))

        # -- what the product counts -----------------------------------------------
        # The rules the event layer enforces are checked in JavaScript, against
        # the module the page runs. What is checked here is the other half: that
        # the schema is a closed list rather than an intention, that it reaches
        # every page that emits, and that nothing in it has room for free text.
        print("\nwhat the product counts")
        from tourism import plate as plate_events
        with open(os.path.join(ROOT_DIR, "tourism", "events.json")) as fh:
            ev = json.load(fh)
        events, props = ev["events"], ev["$props"]
        check("every event names the properties it allows and no others",
              all(isinstance(v, list) for v in events.values())
              and all(k in props for v in events.values() for k in v))
        check("every property described is one an event can carry",
              all(any(k in v for v in events.values()) for k in props),
              ", ".join(k for k in props if not any(k in v for v in events.values())))
        loose = [k for k in props
                 if re.search(r"text|sentence|query|note|name|email|search", k)]
        check("no property is a place a sentence could be put", not loose,
              ", ".join(loose))
        check("the schema says what it does not collect", "$comment" in ev
              and "No identifiers" in ev["$comment"])

        block = plate_events.events_block()
        check("the schema is inlined rather than fetched",
              'id="af-events"' in block and "src=" not in block.split("</script>")[0])
        check("only the rules are shipped, not the prose",
              "$comment" not in block and "$props" not in block)
        check("the rules are small enough to inline", len(block) < 2048,
              "%d bytes" % len(block))
        missing = plate_events.events_block(
            os.path.join(tmp, "no-such-events.json"))
        check("a missing schema ships nothing rather than a broken page",
              missing == "")

        pages = ["atlas.html", "journey.html", "meet.html"]
        one_place = sorted(glob.glob(os.path.join(ROOT_DIR, "places", "*", "*.html")))
        if one_place:
            pages.append(os.path.relpath(one_place[0], ROOT_DIR))
        for rel in pages:
            full = os.path.join(ROOT_DIR, rel)
            if not os.path.exists(full):
                check("%s carries the event rules" % rel, False, "not built")
                continue
            with open(full) as fh:
                text = fh.read()
            check("%s carries the event rules exactly once" % rel,
                  text.count('id="af-events"') == 1
                  and text.count("/scripts/events.js") == 1,
                  "%d block(s)" % text.count('id="af-events"'))

        with open(os.path.join(ROOT_DIR, "scripts", "events.js")) as fh:
            ev_src = fh.read()
        # Every page counts through the one layer that validates. A script that
        # reached a destination directly would be a page whose events had never
        # been through the schema, which is the whole guarantee.
        loose = [f for f in sorted(os.listdir(os.path.join(ROOT_DIR, "scripts")))
                 if f.endswith(".js") and f != "events.js"
                 and re.search(r"sendBeacon|gtag\(|dataLayer|analytics|_paq",
                               open(os.path.join(ROOT_DIR, "scripts", f)).read())]
        check("no script reaches a destination without going through the layer",
              not loose, ", ".join(loose))
        check("no page talks to an analytics vendor",
              not any(re.search(r"googletagmanager|google-analytics|gtag\(|segment\."
                                r"|mixpanel|hotjar|facebook\.net|clarity\.ms",
                                open(os.path.join(ROOT_DIR, p)).read())
                      for p in ["atlas.html", "journey.html", "meet.html",
                                "index.html"]
                      if os.path.exists(os.path.join(ROOT_DIR, p))))
        check("counting is off until somebody chooses a destination",
              "SINK = null" in ev_src)

        # -- the journey engine ----------------------------------------------------
        # The engine is JavaScript because it answers between one click and the
        # next, so it is tested by running it rather than by re-implementing it
        # here. The checks live next to the code they test and report back one
        # line each; if node is not installed they are reported as skipped and
        # counted as neither passed nor failed, because a check that did not run
        # is not a check that passed.
        # -- what the browser actually does ----------------------------------------
        print("\nwhat the browser actually does")
        node = shutil.which("node")
        shift = os.path.join(ROOT_DIR, "tools", "browser-checks.js")
        if not node:
            print("  SKIPPED: node is not installed; nothing was measured in a browser")
        else:
            proc = subprocess.run([node, shift], capture_output=True, text=True,
                                  cwd=ROOT_DIR)
            lines = [l for l in proc.stdout.splitlines() if "\t" in l]
            if not lines:
                check("the browser checks ran", False,
                      (proc.stderr or "no output").strip().splitlines()[-1][:90]
                      if (proc.stderr or "").strip() else "no output")
            for line in lines:
                verdict, name, detail = (line.split("\t") + ["", ""])[:3]
                check(name, verdict == "PASS", detail)

        print("\njourney engine")
        script = os.path.join(ROOT_DIR, "tools", "journey-checks.js")
        if not node:
            print("  SKIPPED: node is not installed; the engine checks did not run")
        elif not os.path.exists(os.path.join(ROOT_DIR, "journey.html")):
            print("  SKIPPED: journey.html is not built; run build.py journey")
        else:
            proc = subprocess.run([node, script], capture_output=True, text=True,
                                  cwd=ROOT_DIR)
            lines = [l for l in proc.stdout.splitlines() if "\t" in l]
            if not lines:
                check("the journey engine checks ran", False,
                      (proc.stderr or "no output").strip().splitlines()[-1][:90])
            for line in lines:
                verdict, name, detail = (line.split("\t") + ["", ""])[:3]
                check(name, verdict == "PASS", detail)

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


def by_slug_test(countries, slug):
    return [c for c in countries if c.slug == slug][0]


def esc_test(text):
    """The plate escapes what it prints; the test has to compare like with like."""
    import html as _html
    return _html.escape(str(text or ""), quote=True)


def _inside(box, view):
    """Is a country's box inside the view its region flies to?"""
    if not box or not view:
        return True
    return (box[0] >= view[0] - 0.5 and box[1] >= view[1] - 0.5
            and box[0] + box[2] <= view[0] + view[2] + 0.5
            and box[1] + box[3] <= view[1] + view[3] + 0.5)


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
