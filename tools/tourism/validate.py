"""Completeness and integrity checks.

The rule the report enforces: 27 categories per country, every one with a caption,
a description, a subject, a focal point, and alt text that says something. A
country that fails is reported, not silently published.

Severities:
    error   blocks the country from being published
    warn    publishes, but the report says what is missing (typically: image
            slots that have not been resolved from Unsplash yet)
"""

from . import imaging, providers
from .model import ROOT


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


# ---- the image quality gate ------------------------------------------------------


def check_images(country, taxonomy, root=None):
    """What a broken image record looks like, checked before it can be published.

    Everything here is a failure the page cannot show you: a focal point outside
    the frame quietly becomes a centre crop, a local asset that is not on disk
    becomes a broken box, a record with no provider cannot build a URL at all,
    and a photograph that requires attribution and carries no photographer is a
    licence breach rather than a design problem.

    Errors, not warnings, for anything that would publish something wrong. A
    slot with no photograph is neither: it is the normal state of this dataset
    and it renders a plate.
    """
    import os as _os
    findings = []
    root = root or ROOT

    for cat in taxonomy.enabled:
        entry = country.entry(cat["id"])
        if not entry:
            continue
        role = taxonomy.role(cat["id"])

        fx, fy = entry.focal["x"], entry.focal["y"]
        if not (0 <= fx <= 100 and 0 <= fy <= 100):
            findings.append(Finding("error", country.slug, cat["id"],
                                    "focal point %s,%s is outside the frame" % (fx, fy)))

        if entry.local:
            path = _os.path.join(root, entry.local.lstrip("/"))
            if not _os.path.exists(path):
                findings.append(Finding("error", country.slug, cat["id"],
                                        "local asset %s is not on disk" % entry.local))

        record = entry.image or {}
        if not record.get("imageUrl"):
            continue

        provider = providers.for_record(record)
        if provider is None:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "no registered provider owns %s"
                                    % record.get("imageUrl")))
            continue
        if provider.requires_attribution and not record.get("photographer"):
            findings.append(Finding("error", country.slug, cat["id"],
                                    "%s requires attribution and this record names "
                                    "no photographer" % provider.name))
        if provider.synthetic and not record.get("generated"):
            findings.append(Finding("error", country.slug, cat["id"],
                                    "a %s record is not disclosed as generated"
                                    % provider.name))
        if record.get("generated") and not provider.synthetic:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "record is flagged generated but %s is a "
                                    "photography provider" % provider.name))
        if record.get("country") and record["country"] != country.slug:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "record belongs to %s" % record["country"]))
        if record.get("category") and record["category"] != cat["id"]:
            findings.append(Finding("error", country.slug, cat["id"],
                                    "record was resolved for %s" % record["category"]))

        width = record.get("width") or 0
        wanted = role["srcset"][0] if role.get("srcset") else role["width"]
        if width and width < wanted:
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "%dpx original for a slot delivered at %dpx"
                                    % (width, wanted)))

        alt = (record.get("alt") or "").strip()
        if alt and alt.lower() in (country.name.lower(), country.slug):
            findings.append(Finding("warn", country.slug, cat["id"],
                                    "alt text is only the country name"))
    return findings


# ---- how people are written about ------------------------------------------------

# Words and phrasings that turn people into scenery. The list is short and every
# entry earned its place: each one is a way of writing about somebody that makes
# a visitor the subject and a resident the backdrop.
#
# Two kinds. `NEVER` is language that is wrong wherever it appears — "primitive",
# "tribesman", "unspoilt by man". `GENERALISING` is a construction that is only
# wrong at continental scale: "African culture", "the African people", "an
# African village". Africa is fifty-four countries and roughly two thousand
# languages, and a sentence that says "African" where it means "Bamileke" has
# thrown away the only fact worth having.
#
# The check runs over every caption, description, subject, tagline and summary
# in the dataset — every string a visitor can read — and it is a warning rather
# than an error, because it is a prompt to a writer and not a machine's verdict
# on their sentence. It is deliberately not a spelling of what to say.
NEVER = (
    "primitive", "uncivilised", "uncivilized", "backward", "savage",
    "tribesman", "tribesmen", "tribeswoman", "native people", "the natives",
    "witch doctor", "voodoo magic", "exotic people", "exotic tribe",
    "untouched by civilisation", "untouched by civilization",
    "unspoilt by man", "unspoiled by man", "third world", "dark continent",
    "real africa", "authentic africans", "simple people", "simple life of",
    "poverty tourism", "slum tour", "local colour", "local color",
)

GENERALISING = (
    "african culture", "african tradition", "african traditions",
    "african people", "the african people", "african tribes", "african tribe",
    "african village", "african villages", "african food", "african music",
    "african way of life", "typical african", "typically african",
    "africans believe", "africans are",
)

# Read strings, in the order a visitor meets them.
READABLE = ("tagline", "summary", "when")


def _sentences(country):
    """Every string in a country file that a visitor can read."""
    out = []
    for field in READABLE:
        text = getattr(country, field, "") or ""
        if text:
            out.append(("", field, text))
    for entry in country.entries:
        for field in ("caption", "description", "subject"):
            text = getattr(entry, field, "") or ""
            if text:
                out.append((entry.category or "?", field, text))
    return out


def check_language(country):
    """Flag writing that turns people into scenery.

    Nothing here rewrites a sentence or blocks a build. It reports, with the
    field and the phrase, so that a human decides — which is the only way this
    check can be right, because the same word is fine in one sentence and not in
    the next and a program cannot tell which.
    """
    findings = []
    for category, field, text in _sentences(country):
        low = text.lower()
        for phrase in NEVER:
            if phrase in low:
                findings.append(Finding(
                    "warn", country.slug, category,
                    "%s: %r turns people into scenery \u2014 name the community, "
                    "the place or the practice instead" % (field, phrase)))
        for phrase in GENERALISING:
            if phrase in low:
                findings.append(Finding(
                    "warn", country.slug, category,
                    "%s: %r generalises a continent \u2014 %s is one of "
                    "fifty-four, say which people or which country"
                    % (field, phrase, country.name)))
    return findings


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
            rec = entry.image
            url = rec.get("imageUrl") or ""
            if not rec.get("provider"):
                findings.append(Finding("error", country.slug, cat["id"],
                                        "image record has no provider"))
            elif rec["provider"] not in providers.BY_NAME:
                findings.append(Finding("error", country.slug, cat["id"],
                                        "unknown provider %r" % rec["provider"]))
            elif not providers.BY_NAME[rec["provider"]].owns(url):
                findings.append(Finding("error", country.slug, cat["id"],
                                        "imageUrl is not on %s's CDN" % rec["provider"]))
            for field in ("thumbnailUrl", "sourceUrl", "alt", "aspectRatio", "createdAt"):
                if not rec.get(field):
                    findings.append(Finding("warn", country.slug, cat["id"],
                                            "image record missing %s" % field))
            if not rec.get("photographer"):
                findings.append(Finding("error", country.slug, cat["id"],
                                        "image has no photographer credit"))
            if rec.get("queryTier") == "category":
                findings.append(Finding("warn", country.slug, cat["id"],
                                        "matched on a broadened query — accurate for the "
                                        "category, not for the specific subject"))
            if not rec.get("verifiedAt"):
                findings.append(Finding("warn", country.slug, cat["id"],
                                        "image has never been HTTP-verified"))
            key = "%s:%s" % (rec.get("provider"), rec.get("photoId") or url)
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
        f.extend(check_language(country))
        f.extend(check_images(country, taxonomy))
        findings.extend(f)
        present = [c["id"] for c in taxonomy.enabled if country.entry(c["id"])]
        resolved = [c["id"] for c in taxonomy.enabled
                    if country.entry(c["id"]) and (country.entry(c["id"]).image or {}).get("imageUrl")]
        missing = [c["id"] for c in taxonomy.enabled if c["id"] not in present]
        errors = [x for x in f if x.level == "error"]
        by_provider = {}
        for c in taxonomy.enabled:
            e = country.entry(c["id"])
            if e and e.image and e.image.get("provider"):
                pv = e.image["provider"]
                by_provider[pv] = by_provider.get(pv, 0) + 1
        rows.append({
            "providers": by_provider,
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
