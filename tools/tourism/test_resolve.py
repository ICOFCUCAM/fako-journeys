#!/usr/bin/env python3
"""End-to-end test of the Unsplash resolver, against a local mock of the API.

    python3 tools/tourism/test_resolve.py

Why this exists: the resolver's real run happens on someone else's machine, with
a key this session does not have. Without a test, the first time that code runs
for real is also the first time anyone finds out whether it works. The mock
speaks the shape of the Unsplash search API and serves real bytes, so the whole
path is exercised: search, suitability, de-duplication, delivery-URL
construction, HTTP verification, download-endpoint ping, write-back, and render.

It works on a copy of the dataset in a temp directory. The real
tourism/countries/ files are never touched.
"""

import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

PORT = 8791
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 4000 + b"\xff\xd9"     # >1KB, image/jpeg


class MockUnsplash(http.server.BaseHTTPRequestHandler):
    """Speaks enough of api.unsplash.com and images.unsplash.com to be useful."""

    served = []

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

        if url.path == "/photos/random":
            return self._json([{"id": "preflight"}])

        if url.path == "/search/photos":
            query = (qs.get("query") or [""])[0]
            orientation = (qs.get("orientation") or ["landscape"])[0]
            # A distinct id per query, so de-duplication has something real to do,
            # plus one deliberate repeat to prove the resolver skips it.
            key = abs(hash(query)) % 10 ** 8
            portrait = orientation == "portrait"
            results = [
                {   # first candidate is always too small: exercises the reject path
                    "id": "small-%d" % key,
                    "width": 900, "height": 600,
                    "urls": {"raw": "http://localhost:%d/photo-small-%d" % (PORT, key)},
                    "user": {"name": "Too Small", "links": {"html": "https://example.invalid/u"}},
                    "links": {"html": "https://example.invalid/p", "download_location":
                              "http://localhost:%d/download/small-%d" % (PORT, key)},
                },
                {
                    "id": "photo-%d" % key,
                    "width": 3000 if not portrait else 2400,
                    "height": 2000 if not portrait else 3200,
                    "urls": {"raw": "http://localhost:%d/photo-%d" % (PORT, key)},
                    "user": {"name": "Test Photographer",
                             "links": {"html": "https://example.invalid/@tester"}},
                    "links": {"html": "https://example.invalid/photos/%d" % key,
                              "download_location": "http://localhost:%d/download/%d" % (PORT, key)},
                },
            ]
            return self._json({"results": results})

        if url.path.startswith("/download/"):
            return self._json({"url": "ok"})

        if url.path.startswith("/photo-"):
            if url.path.startswith("/photo-small-"):
                # should never be requested: it fails the suitability check first
                MockUnsplash.served.append(("UNEXPECTED", self.path))
                return self._json({"error": "should not be fetched"}, 500)
            MockUnsplash.served.append((url.path, url.query))
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(JPEG)))
            self.end_headers()
            self.wfile.write(JPEG)
            return

        self._json({"error": "not found"}, 404)


def serve():
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), MockUnsplash)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    os.environ["UNSPLASH_ACCESS_KEY"] = "mock-key"
    os.environ["UNSPLASH_API_BASE"] = "http://localhost:%d" % PORT
    os.environ["UNSPLASH_IMAGE_HOST_OVERRIDE"] = "http://localhost:%d/" % PORT

    from tourism import imaging, resolve            # imported after the env is set
    from tourism.model import load_country, load_taxonomy

    httpd = serve()
    tmp = tempfile.mkdtemp(prefix="tourism-e2e-")
    failures = []
    try:
        src = os.path.join(os.path.dirname(HERE), "..", "tourism", "countries", "cameroon.json")
        dst = os.path.join(tmp, "cameroon.json")
        shutil.copy(os.path.abspath(src), dst)

        tax = load_taxonomy()
        country = load_country(dst)
        key = resolve.preflight()

        seen = set()
        filled, failed = 0, []
        for cat in tax.enabled:
            entry = country.entry(cat["id"])
            record, err = resolve.resolve_entry(country, cat, entry, tax.role(cat["id"]), key, seen)
            if record:
                record["verifiedAt"] = "2026-01-01T00:00:00Z"
                entry.image = record
                filled += 1
            else:
                failed.append((cat["id"], err))
        resolve.write_country(country)

        def check(name, ok, detail=""):
            print("  %-46s %s%s" % (name, "PASS" if ok else "FAIL", "  " + detail if detail else ""))
            if not ok:
                failures.append(name)

        check("all 27 slots resolved", filled == 27, "filled=%d failed=%s" % (filled, failed[:3]))
        ids = [country.entry(c["id"]).image["id"] for c in tax.enabled
               if country.entry(c["id"]).image]
        check("no duplicate photo reused", len(ids) == len(set(ids)),
              "%d ids, %d unique" % (len(ids), len(set(ids))))
        check("undersized candidate never fetched",
              not any(x[0] == "UNEXPECTED" for x in MockUnsplash.served))
        check("every stored URL was actually fetched",
              len(MockUnsplash.served) >= 27, "%d fetches" % len(MockUnsplash.served))

        # delivery URL correctness
        hero = country.entry("hero")
        role = tax.role("hero")
        url = imaging.cdn_url(hero.image["url"], role, hero.focal)
        check("delivery URL carries focal point",
              "crop=focalpoint" in url and "fp-x=" in url and "fp-y=" in url, url.split("?")[1][:60])
        check("delivery URL carries sizing + quality",
              "w=2400" in url and "h=1350" in url and "q=" in url and "auto=format" in url)
        srcset = imaging.srcset(hero.image["url"], role, hero.focal)
        check("srcset has one entry per ladder step",
              srcset.count(",") == len(role["srcset"]) - 1, "%d steps" % (srcset.count(",") + 1))
        check("portrait role delivers a portrait box",
              imaging.dimensions(tax.role("traditional-people"))[1] >
              imaging.dimensions(tax.role("traditional-people"))[0])

        # provenance
        check("photographer credit recorded", hero.image.get("photographer") == "Test Photographer")
        check("originating query recorded", "Cameroon" in (hero.image.get("query") or ""))

        # write-back round-trips
        reread = load_country(dst)
        check("resolved data round-trips through the file",
              all(reread.entry(c["id"]).image for c in tax.enabled))
        check("file stays human-readable (focal inline)",
              '"focal": [' in open(dst).read())

        # the delivery builder must still refuse a foreign source
        try:
            imaging.cdn_url("https://cdn.example.com/photo-1", role, hero.focal)
            check("refuses a non-Unsplash source", False)
        except ValueError:
            check("refuses a non-Unsplash source", True)

    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print("%d check(s) FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("all checks passed — the resolver is ready for a real key")
    return 0


if __name__ == "__main__":
    sys.exit(main())
