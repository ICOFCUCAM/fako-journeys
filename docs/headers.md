# The response headers, and how each value was arrived at

`vercel.json` sends six headers on every response. None of them is a default
copied from a checklist: each one was written against what this site actually
loads, measured in the built output, and each is recorded here with what would
break it — because a header that nobody can safely change is a header that will
eventually be deleted instead.

## Content-Security-Policy

The policy is `'self'` for everything, with three deliberate exceptions.

**`img-src` names two hosts.** The resolver files photographs from Pexels and
Unsplash and the built pages reference them at their own CDNs — 140 references
to `images.pexels.com` and 21 to `images.unsplash.com` on a sample of seven
pages. `data:` is there for the inline SVG marks. Nothing else is allowed to
paint a pixel on this site.

**`style-src` and `script-src` allow `'unsafe-inline'`.** They have to: the
gateway, the atlas, the journey engine and every generated page carry inline
`<script>` and `<style>` blocks, and a static host has no request-time step in
which to mint a nonce. This is the honest limit of what a CSP can be worth here
— it stops a script being fetched from somewhere else, and it does not stop an
injected inline one. The site carries no inline event handlers (`onclick=` and
its family appear nowhere in the built HTML, which was checked rather than
assumed), so the day this site gains a build step that can emit nonces, both
keywords can come out without touching the markup.

**`form-action` allows `mailto:`.** /enquire posts to
`mailto:hello@afrinkong.com` because there is no server to post to yet. The day
an endpoint exists, this becomes `'self'` and the mailto goes.

`connect-src 'self'` is not a guess either: every `fetch()` in `scripts/` asks
for a path beginning with `/data/`, so nothing on this site talks to another
origin at runtime.

Two links point at operator sites on `vercel.app`. They are anchors, not
resources, and a CSP does not govern where a link may go.

## The other five

- **`X-Content-Type-Options: nosniff`** — an upload served under the wrong
  extension should not be executed because a browser guessed at its contents.
- **`Referrer-Policy: strict-origin-when-cross-origin`** — a reader who follows
  a link from a page about their own journey to an operator's site sends the
  origin, not the path they were on.
- **`X-Frame-Options: SAMEORIGIN`** alongside `frame-ancestors 'self'`. The CSP
  directive supersedes the header in anything current; the header stays for
  what is not.
- **`Permissions-Policy`** turns off features this site has no use for.
  `interest-cohort=()` is a dead flag in most browsers now and costs nothing to
  keep refusing.
- **`Strict-Transport-Security: max-age=31536000; includeSubDomains`** — a year,
  and **deliberately without `preload`**. Preloading is close to irreversible: it
  is a list baked into browser binaries, and removal takes months. It is the
  right thing to add once the domain has been live on HTTPS for a while and
  nobody plans a subdomain that cannot be. Not on the day the domain is bought.

## Cache-Control, and why two policies rather than one

The site had six security headers and nothing about caching, so every asset
took whatever the host felt like. Two policies, split on one question: does the
content at this filename ever change?

**A year, immutable — `/images`, `/fonts`, `/videos`.** A file at
`/images/uploads/x-1600w.jpg` is that photograph and stays that photograph; a
different photograph gets a different name. `immutable` means the browser does
not even send a conditional request, which on a site whose first screen is
photographs is most of the repeat-visit cost.

**An hour with background revalidation — `/styles`, `/scripts`.** These
filenames are stable across deploys and their contents are not: there is no
content hash in `afrinkong.css`. A year here would leave a returning reader on
the previous stylesheet until they cleared their cache, which is the classic
way a deploy appears not to have happened. `stale-while-revalidate=86400` lets
them have the cached copy instantly and fetches the new one behind it.

**Ten minutes — `/data`.** The payloads the atlas and the journey engine fetch.
Same reasoning as the stylesheets and shorter, because a country's write-up
changing is the thing a reader would most notice not changing.

**Nothing for HTML on purpose.** The pages are the site; they must revalidate,
and the host's default already does that. Setting a long life on them is how a
static site starts serving last week.

## Before changing any of this

`afrinkong.com` is not registered yet, so none of these headers has ever been
served to a real browser. The first deploy to the real domain is the moment to
check the site still works with them on — the CSP is the one that can break a
page silently, and the thing to watch is the browser console, not the page.
