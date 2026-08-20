# The Afrinkong Travel Point economy — audit and architecture

Wankong LLC, trading as Afrinkong. Written 20 August 2026 against the Travel
Point Economy brief, following its own §33: audit first, produce a migration
architecture, then implement incrementally.

**Nothing in this document has been deployed.** No database exists, no payment
integration exists, no point has been issued, and no customer money has moved.
What has been built is the domain model, the schema and the ledger — the three
things §33's priority order puts first, and the three that everything else is
worthless without.

---

## Part 1 — The audit (§33.1–8)

Evidence, not impressions. Every line below was checked against the repository.

### 1. What the repository is

A **static site**. 1,597 HTML files, Vercel with `cleanUrls: true`, an empty
`buildCommand`, and — checked in `package.json` — **zero runtime dependencies**.
Pages are generated from JSON by `tools/tourism/build.py` and then edited in
place by late passes.

**There is no server.** This is the single most consequential finding in the
audit and it is dealt with in Part 2.

### 2. The existing travel planner

Two products, both already built and both well factored:

| | interface | pure logic | data |
|---|---|---|---|
| Journey Fund | `scripts/fund.js` (349 lines) | `scripts/fund-math.js` (168) | `tourism/rates.json` |
| Journey Builder | `scripts/journey.js` (1,512) | `scripts/journey-engine.js` (673) | `tourism/journeys.json` |

`fund-math.js` already separates arithmetic from the DOM, with a docstring that
says why: *"this is the part that has to be right, and a function that needs a
DOM to run is a function that needs a browser to test."* The Travel Point
ledger is written in the same shape for the same reason.

What the fund currently does is **division**: journey cost ÷ whole months. Its
own comments are emphatic that there is *"no interest here, no growth, no
projection, no return, no compounding."* That discipline is exactly what the
Travel Point layer must preserve.

### 3. Pricing and rate cards

`tourism/rates.json` is a real rate card and is better structured than most:

- three tiers — Afrinkong Private $450/day, Signature $650, Bespoke $1,000,
  per vehicle per day
- durations 3/5/7/10/14 days, default 7
- arrival coordination $200 per journey
- **`destination_charges` held strictly separate from Afrinkong service**, with
  a `$model` note explaining that the two must never be mixed

That separation matters for points: park fees and permits are settled at cost
and are not Afrinkong revenue, so they are not obviously redeemable with Travel
Points. **This needs an explicit product decision** — see Open questions.

### 4. Customer and storage assumptions

There are **no customers**. No accounts, no identity, no sessions, no server
state. Everything lives in `localStorage` under two keys:

    afrinkong.journey-fund.plan     the saved fund plan
    (journey.js)                    up to 12 saved journeys

A plan is anonymous, device-local, and lost when the browser is cleared. That
is fine for a planner and impossible for an economy.

### 5. Stripe

**None.** Every `stripe` match in the repository is the word in image alt text
— fabric patterns, painted stripes. There is no payment integration of any
kind.

### 6. Supabase and databases

**None in the repository.** The account has 17 Supabase projects, all currently
paused, none of them Afrinkong — the closest by name are `Wankongreal` and
`wankongos`, neither of which is this platform. No project has been created for
this work.

### 7. Journey and itinerary models

`tourism/journeys.json` holds the builder's vocabulary and weights — pacing,
party, style, lens, depth, season, operator, region — deliberately kept out of
code *"so the reasoning can be read by somebody who does not read JavaScript."*
Per-country data lives in `tourism/countries/`, with 1,363 place pages and 54
country portraits generated from it.

### 8. Where Travel Points fit without breaking anything

`fund-math.js` is the seam, and it is a clean one.

It already computes a journey total and a monthly figure. The point layer takes
that total and restates it as travel purchasing power. **The planner does not
change.** `points-ledger.js` exposes `goal(programId, journeyCostMinor, held,
months)` which performs the same division in points and returns target, held,
remaining, progress and monthly — so §21's "Your Journey Goal" panel is a
presentation change over an unchanged calculation.

Nothing in the existing planner has been modified by this work.

---

## Part 2 — The migration architecture (§33.9–10)

### The finding that shapes everything

The site is static. §15 forbids issuing points on a frontend's say-so and §25
forbids client-side balance mutation — correctly, because a browser that can
write to the ledger is a browser that can mint points.

**So Phase 1 necessarily introduces a server.** There is no version of this
product that lives in `localStorage`. That is not a preference; it follows
directly from the security requirements in the brief.

### The separation (§33.10)

Three planes, and the existing site keeps its shape:

    STATIC PLANE                DYNAMIC PLANE
    the site as it is now       new, and only new
    ─────────────────────       ─────────────────────
    1,597 generated pages       identity and sessions
    the planner (localStorage)  the Travel Point ledger
    the journey builder         payments and webhooks
    the image library           the wallet
    Vercel, no build            reconciliation, admin

The static plane is not rewritten. The Travel Wallet is a new authenticated
area; the planner keeps working for anonymous visitors exactly as it does
today, and gains a "start a travel goal" door that leads into the dynamic
plane. A visitor who never signs in loses nothing they have now.

### What has been built in this commit

| piece | file | state |
|---|---|---|
| domain model + ledger | `scripts/points-ledger.js` | **implemented**, 29 checks passing |
| ledger tests | `tools/points-checks.js` | **implemented** |
| database schema | `tools/points/schema.sql` | **designed, not applied** |

`points-ledger.js` is zero-dependency UMD, exactly like `fund-math.js`: it runs
in Node for the tests and in a browser for read-only projections, and it will
run unchanged on a server. That is deliberate — the same fold that draws a
customer's wallet is the one that validates an issuance.

### What the ledger enforces, in code

- **A balance is never stored.** `wallet()` folds the whole entry list every
  time. There is no `balance` field anywhere in the module or the schema.
- **Idempotency is mandatory.** An entry without a key throws; a repeated key
  is ignored. A webhook delivered twice issues points once.
- **Payment ≠ points.** A `PURCHASE` entry whose status is not `SETTLED`
  contributes nothing.
- **No overdraft.** Reserving or redeeming beyond the wallet throws, and
  `can()` answers the same question without throwing so a screen can explain.
- **Cancellation attaches to the booking.** A forfeiture of the 3,500 points
  reserved for a journey leaves the other 1,500 untouched. Tested explicitly,
  because getting this wrong destroys somebody's two years of accumulation.
- **No growth vocabulary.** A test greps the compiled code for `interest`,
  `compound`, `yield`, `apr`, `apy`, `accrue`, `dividend` and fails if any
  appears. This is a legal boundary expressed as a unit test.
- **Programs are versioned and unknown ones are refused** — no silent fallback
  to `1 point = $1`.

### What the schema enforces, at the database

- `point_ledger` has `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise.
  Economic history is corrected by appending a reversal, never by editing.
- `idempotency_key` is a `UNIQUE` constraint, not a convention.
- `payment_events` is unique on `(provider, event_id)` — replay protection in
  the schema rather than in a code path somebody can forget.
- Point program economic terms are immutable after creation; only `status`
  moves forward.
- `travel_wallets` is a **view**, not a table, so it cannot drift from the
  ledger.
- Row-level security grants customers `SELECT` on their own rows and **no
  write policy at all**. Absence is the policy.
- `unreconciled_payments` and `unbacked_issuance` are the two daily questions
  from §27, as views.

---

## Part 3 — What has NOT been built, and why

Stated plainly rather than implied by omission.

| §  | item | why not |
|---|---|---|
| 14, 15 | Stripe integration | needs API keys, a server to receive webhooks, and a Stripe account. No keys exist and none should be pasted into a repository. |
| 9 | Travel Wallet UI | needs identity and a server. Building the screen before the ledger it reads would be building the part that photographs well. |
| 26 | Travel Economy Console | Phase 2. Depends on the ledger being live and populated. |
| 6, 7 | recurring purchase, packages | Phase 2 per §24; recurring billing is a Stripe subscription concern. |
| 11 | buyback execution | quoting is implemented and gated; **executing** it is deliberately deferred pending §11's legal review. |
| 12 | reservation integration | needs bookings, which need suppliers. Phase 2. |
| 30 | image library provenance extension | the library already records source, licence, photographer, country, category, hash and formats. `contract`, `release`, `capture date`, `location` and `rights` are additions for when commissioned assets exist — there are none yet. |

---

## Part 4 — The thing that must be resolved before launch

The brief already recognises this in §11. Restating it once, factually:

**A product where customers pay money over time, accumulate redeemable units,
and can convert those units back to cash may be regulated as stored value or
money transmission** in the United States, at both federal and state level,
regardless of what the units are called. The features that most affect that
assessment are:

1. whether buyback is **discretionary or contractual** — a guaranteed right of
   redemption is materially different from a discretionary programme;
2. whether points are **transferable to third parties**;
3. how long funds are held before travel;
4. whether points are redeemable for anything other than Afrinkong services.

The code takes the conservative position on every one of these: buyback is
`discretionary: true`, the program ships as `status: 'draft'`, and the module
refuses to treat any program as live that has not been explicitly marked.
`PROGRAMS['AFK-TP-2026.1'].status` must not read `'active'` until counsel has
signed the terms, and the test suite asserts it currently does not.

This is not a reason to stop building the ledger — the ledger is needed whatever
counsel decides. It is a reason not to take a single customer payment first.

### Open product questions

1. **Are destination charges redeemable with points?** `rates.json` keeps park
   fees and permits separate from Afrinkong service because they are settled at
   cost. If points redeem against them, Afrinkong is holding value for
   third-party obligations, which is a different risk. Recommendation: points
   redeem against **Afrinkong service only**, at least initially.
2. **What happens on a chargeback after redemption?** A customer disputes a
   payment for points already used on a journey. The schema records
   `charged_back`; the policy is undecided.
3. **Journey price protection.** §20 asks the system to explain why a journey
   is 4,800 when it was 4,000. `journey_prices` records the rate card version
   and the price the customer was shown. Whether the *earlier* price is
   honoured is a commercial promise nobody has made yet.

---

## Part 5 — The order of work from here

Following §33's priority order. Items 1–3 are done.

    1. Domain model                    DONE   scripts/points-ledger.js
    2. Database schema                 DONE   tools/points/schema.sql (unapplied)
    3. Immutable point ledger          DONE   29 checks
    ───────────────────────────────────────── legal review gate ─────
    4. Point products                  needs the program terms signed
    5. Stripe payment integration      needs keys, a server, an account
    6. Travel Wallet                   needs 4 and 5
    7. Journey Goal integration        can start early — goal() exists
    8. Redemption                      needs 6
    9. Reservation integration         needs bookings
    10. Buyback / transfer             needs the legal answer, not just code
    11. Admin Travel Economy Console   needs a populated ledger
    12. Reconciliation                 views exist; needs live data
    13. Customer education and legal   needs counsel

**Do not build 10 before 1–3 are correct.** The brief says so and it is right:
a buyback mechanism sitting on an accounting model that cannot be audited is
how a company discovers it has been quietly wrong for a year.

The cheapest genuinely useful next step is **item 7** — restating the existing
fund planner's output in points. It needs no server, no payments and no legal
sign-off, because it shows a customer what their goal looks like in Travel
Points without issuing any. That is `goal()`, and it is already written and
tested.
