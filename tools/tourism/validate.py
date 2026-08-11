"""Completeness and integrity checks.

The rule the report enforces: 27 categories per country, every one with a caption,
a description, a subject, a focal point, and alt text that says something. A
country that fails is reported, not silently published.

Severities:
    error   blocks the country from being published
    warn    publishes, but the report says what is missing (typically: image
            slots that have not been resolved from Unsplash yet)
"""

from . import imaging


class Finding:
    __slots__ = ("level", "country", "category", "message")

    def __init__(self, level, country, category, message):
        self.level = level
        self.country = country
        self.category = category
        self.message = message

    def __str__(self):
        where = self.country + (" / " + self.category if self.category else "")
        return "%-5s %-28s %s" % (self.level.upper(), where, self.message)


def alt_text(country, entry):
    """Derived, never "Uganda image": the subject phrase, placed in its country."""
    subject = (entry.subject or "").strip().rstrip(".")
    if not subject:
        return ""
    if country.name.lower() in subject.lower():
        return subject
    return "%s, %s" % (subject, country.name)


def check_country(country, taxonomy, global_images, global_subjects):
    findings = []
    seen = set()

    for entry in country.entries:
        if entry.category not in taxonomy.by_id:
            findings.append(Finding("error", country.slug, entry.category or "?",
                                    "unknown category id"))
            continue
        if entry.category in seen:
            findings.append(Finding("error", country.slug, entry.category,
                                    "duplicate category entry"))
        seen.add(entry.category)

    for cat in taxonomy.categories:
        if not cat.get("enabled", True):
            continue
        entry = country.entry(cat["id"])
        if entry is None:
            findings.append(Finding("error", country.slug, cat["id"], "missing category"))
            continue

        if not entry.caption:
            findings.append(Finding("error", country.slug, cat["id"], "missing caption"))
        elif len(entry.caption) > 46:
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "caption is %d chars, too long for a card overlay"
                                    % len(entry.caption)))
        if not entry.description:
            findings.append(Finding("error", country.slug, cat["id"], "missing description"))
        if not entry.subject:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "missing subject (alt text and search query derive from it)"))
        alt = alt_text(country, entry)
        if len(alt) < 18:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "alt text too thin to be useful: %r" % alt))
        fx, fy = entry.focal["x"], entry.focal["y"]
        if not (0 <= fx <= 100 and 0 <= fy <= 100):
            findings.append(Finding("error", country.slug, cat["id"],
                                    "focal point out of range: %s,%s" % (fx, fy)))
        role_name = cat["role"]
        if role_name in ("hero", "panoramic", "portrait") and (fx, fy) == (50, 50):
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "%s crop left on dead centre — set a focal point" % role_name))

        # captions must not be the bare category title on every country
        if entry.caption and entry.caption.strip().lower() == cat["title"].strip().lower():
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "caption is just the category title; write country-specific copy"))

        if entry.image:
            url = entry.image.get("url") or ""
            if not url.startswith(imaging.UNSPLASH_HOST):
                findings.append(Finding("error", country.slug, cat["id"],
                                        "image is not an images.unsplash.com URL"))
            if not entry.image.get("verifiedAt"):
                findings.append(Finding("warn", country.slug, cat["id"],
                                        "image has never been HTTP-verified"))
            key = entry.image.get("id") or url
            if key in global_images:
                findings.append(Finding("error", country.slug, cat["id"],
                                        "duplicate image, already used by %s" % global_images[key]))
            else:
                global_images[key] = "%s/%s" % (country.slug, cat["id"])
        else:
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "image unresolved (run: build.py resolve)"))

        subj = (entry.subject or "").strip().lower()
        if subj:
            if subj in global_subjects:
                findings.append(Finding("warn", country.slug, cat["id"],
                                        "subject identical to %s — images will collide"
                                        % global_subjects[subj]))
            else:
                global_subjects[subj] = "%s/%s" % (country.slug, cat["id"])

    return findings


def report(countries, taxonomy):
    """Returns (rows, findings). rows feed the completeness table."""
    findings = []
    rows = []
    global_images = {}
    global_subjects = {}
    expected = len(taxonomy.enabled)

    for country in countries:
        if not country.slug:
            findings.append(Finding("error", country.path, "", "country has no slug"))
            continue
        f = check_country(country, taxonomy, global_images, global_subjects)
        findings.extend(f)
        present = [c["id"] for c in taxonomy.enabled if country.entry(c["id"])]
        resolved = [c["id"] for c in taxonomy.enabled
                    if country.entry(c["id"]) and (country.entry(c["id"]).image or {}).get("url")]
        missing = [c["id"] for c in taxonomy.enabled if c["id"] not in present]
        errors = [x for x in f if x.level == "error"]
        rows.append({
            "slug": country.slug,
            "name": country.name,
            "categories": "%d/%d" % (len(present), expected),
            "images": "%d/%d" % (len(resolved), expected),
            "missing": missing,
            "errors": len(errors),
            "ok": not errors and len(present) == expected,
            "publishable": not errors and len(present) == expected,
        })
    return rows, findings


def format_report(rows, findings, taxonomy):
    out = []
    width = max([len(r["name"]) for r in rows] + [7])
    out.append("%-*s  %-11s  %-11s  %s" % (width, "COUNTRY", "CATEGORIES", "IMAGES", "STATUS"))
    out.append("-" * (width + 40))
    for r in rows:
        status = "OK" if r["ok"] else "INCOMPLETE"
        out.append("%-*s  %-11s  %-11s  %s" % (width, r["name"], r["categories"], r["images"], status))
        if r["missing"]:
            out.append("%-*s  missing: %s" % (width, "", ", ".join(r["missing"])))
    errs = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    out.append("")
    out.append("%d error(s), %d warning(s)" % (len(errs), len(warns)))
    for f in errs[:40]:
        out.append("  " + str(f))
    if len(errs) > 40:
        out.append("  ... %d more" % (len(errs) - 40))
    # warnings are summarised by kind; 189 "unresolved" lines help nobody
    kinds = {}
    for f in warns:
        key = f.message.split("(")[0].split("—")[0].strip()
        kinds[key] = kinds.get(key, 0) + 1
    for key, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        out.append("  WARN  x%-4d %s" % (n, key))
    return "\n".join(out)
