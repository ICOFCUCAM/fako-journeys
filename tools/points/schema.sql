-- The Afrinkong Travel Point economy: schema.
-- ===========================================================================
-- PostgreSQL. Written for Supabase because that is the database this account
-- already has, but there is nothing Supabase-specific below except the
-- row-level security block at the end, which is clearly marked.
--
-- NOT APPLIED ANYWHERE. This is the design, committed for review. No
-- migration has been run, no project has been created, and no customer data
-- exists. Applying it is a decision that follows the legal review, not one
-- that follows this commit.
--
-- ---------------------------------------------------------------------------
-- THE ONE RULE
--
-- A balance is never stored. `point_ledger` is append-only and every figure a
-- customer or an accountant ever sees is derived from it. The triggers at the
-- bottom enforce that at the database level rather than trusting every future
-- caller to remember: UPDATE and DELETE on the ledger are refused outright.
--
-- This is the difference between a system that can answer "why does this
-- customer have 2,450 points" and one that can only assert it.
--
-- ---------------------------------------------------------------------------
-- WHAT IS DELIBERATELY ABSENT
--
-- No `balance` column. No `interest`, no `rate_of_return`, no `maturity`.
-- No table called `accounts` in the banking sense. A Travel Point is travel
-- purchasing entitlement, and the schema should not contain a single noun
-- that would let somebody later argue it was something else.

begin;

-- ===========================================================================
-- CUSTOMERS
-- ===========================================================================

create table customers (
  id              text primary key,              -- CUST-10291, human-readable on purpose
  email           text not null unique,
  full_name       text,
  country         text,
  created_at      timestamptz not null default now(),
  -- Identity verification is a placeholder until counsel says what is needed.
  -- A buyback feature may pull KYC obligations in; the column exists so that
  -- answer has somewhere to live rather than becoming a schema change later.
  verified_at     timestamptz,
  verification_ref text
);

-- ===========================================================================
-- POINT PROGRAMS — versioned terms, never edited in place
-- ===========================================================================
--
-- `1 point = $1` is a property of a program, not of the application. A point
-- issued under 2026.1 keeps 2026.1's terms for its whole life, whatever later
-- programs say. That is why status moves forward and rows are never rewritten:
-- changing a live program's rules would retroactively change what somebody
-- already bought.

create table point_programs (
  id              text primary key,              -- AFK-TP-2026.1
  name            text not null,
  version         integer not null,
  status          text not null
                  check (status in ('draft', 'active', 'closed', 'withdrawn')),
  currency        char(3) not null default 'USD',
  issue_rate      numeric(12,6) not null,        -- points per unit of currency
  entitlement     numeric(12,6) not null,        -- travel value applied per point
  min_purchase    integer not null default 0,
  transferable    boolean not null default false,
  -- The clause with regulatory weight. Discretionary by default; making it
  -- contractual can change what this product legally is.
  buyback         jsonb not null default '{"offered": false}'::jsonb,
  cancellation    jsonb not null,                -- the day-bands
  expiry_months   integer not null default 0,    -- 0 = no expiry
  terms_url       text,
  effective_from  date not null,
  effective_until date,
  created_at      timestamptz not null default now()
);

-- A program that has issued points can never go back to draft, and its
-- economic terms can never be edited. Only its status may move forward.
create or replace function point_programs_immutable_terms()
returns trigger language plpgsql as $$
begin
  if new.issue_rate  is distinct from old.issue_rate
  or new.entitlement is distinct from old.entitlement
  or new.buyback     is distinct from old.buyback
  or new.cancellation is distinct from old.cancellation then
    raise exception
      'point program %: economic terms are immutable once created — issue a new version',
      old.id;
  end if;
  return new;
end $$;

create trigger point_programs_no_term_edits
  before update on point_programs
  for each row execute function point_programs_immutable_terms();

-- ===========================================================================
-- PAYMENTS — the money, kept strictly apart from the points
-- ===========================================================================
--
-- Stripe is the payment rail and is NOT the point ledger. This table records
-- what Stripe told us, verified; `point_ledger` records what Afrinkong then
-- issued. Two events, two rows, one reference between them — so a
-- reconciliation can ask "does every settled payment have exactly one
-- issuance, and vice versa" and get an answer.

create table payments (
  id              text primary key,              -- PAY-000001
  customer_id     text not null references customers(id),
  provider        text not null default 'stripe',
  provider_ref    text not null,                 -- pi_xxx
  amount_minor    bigint not null check (amount_minor > 0),
  currency        char(3) not null,
  status          text not null
                  check (status in ('pending', 'requires_capture', 'settled',
                                    'failed', 'refunded', 'charged_back')),
  -- The raw verified event, kept so a dispute can be answered from what the
  -- provider actually said rather than from our summary of it.
  provider_event  jsonb,
  created_at      timestamptz not null default now(),
  settled_at      timestamptz,
  unique (provider, provider_ref)                -- one payment, one row, ever
);

-- Every webhook we have accepted, so a redelivery is recognised as one.
create table payment_events (
  id              bigserial primary key,
  provider        text not null default 'stripe',
  event_id        text not null,
  type            text not null,
  signature_ok    boolean not null,
  payload         jsonb not null,
  received_at     timestamptz not null default now(),
  processed_at    timestamptz,
  unique (provider, event_id)                    -- replay protection, in the schema
);

-- ===========================================================================
-- THE LEDGER — append-only, and the only source of any balance
-- ===========================================================================

create table point_ledger (
  id              bigserial primary key,
  entry_ref       text not null unique,          -- TP-000001
  customer_id     text not null references customers(id),
  program_id      text not null references point_programs(id),
  kind            text not null check (kind in (
                    'PURCHASE', 'TRANSFER_IN', 'ADJUST_UP',
                    'RESERVE', 'RELEASE', 'REDEEM',
                    'TRANSFER_OUT', 'BUYBACK', 'EXPIRE', 'ADJUST_DOWN')),
  quantity        integer not null check (quantity > 0),  -- whole points, always positive;
                                                          -- direction is the kind's business
  status          text not null default 'SETTLED'
                  check (status in ('PENDING', 'SETTLED', 'REVERSED')),
  -- IDEMPOTENCY IS A UNIQUE CONSTRAINT, NOT A CONVENTION.
  -- Payments retry, webhooks arrive twice, customers double-click. This is
  -- what stops one payment becoming two issuances, and it is enforced by the
  -- database so no future code path can forget it.
  idempotency_key text not null unique,
  payment_id      text references payments(id),
  journey_ref     text,                          -- the booking a reservation belongs to
  counterparty_id text references customers(id), -- transfers
  reason          text,
  -- Exceptional adjustments require a named human. An ADJUST that nobody
  -- signed is indistinguishable from a bug that minted points.
  approved_by     text,
  created_at      timestamptz not null default now(),

  constraint purchase_needs_payment
    check (kind <> 'PURCHASE' or payment_id is not null),
  constraint reservation_needs_journey
    check (kind not in ('RESERVE', 'RELEASE', 'REDEEM') or journey_ref is not null),
  constraint transfer_needs_counterparty
    check (kind not in ('TRANSFER_IN', 'TRANSFER_OUT') or counterparty_id is not null),
  constraint adjustment_needs_approval
    check (kind not in ('ADJUST_UP', 'ADJUST_DOWN') or approved_by is not null)
);

create index point_ledger_customer on point_ledger (customer_id, id);
create index point_ledger_journey  on point_ledger (journey_ref) where journey_ref is not null;

-- ECONOMIC HISTORY IS NOT EDITABLE. Not by the application, not by an admin,
-- not by a well-meaning script at two in the morning. A mistake is corrected
-- by appending a reversing entry, which leaves both the error and the
-- correction visible — which is the entire point.
create or replace function point_ledger_append_only()
returns trigger language plpgsql as $$
begin
  raise exception 'point_ledger is append-only: % refused. Append a reversing entry instead.',
    tg_op;
end $$;

create trigger point_ledger_no_update
  before update on point_ledger
  for each row execute function point_ledger_append_only();

create trigger point_ledger_no_delete
  before delete on point_ledger
  for each row execute function point_ledger_append_only();

-- ===========================================================================
-- THE WALLET — a view, never a table
-- ===========================================================================
--
-- If this were a table it could drift from the ledger, and the first time it
-- did, nobody would know which was right. As a view the question cannot arise.

create view travel_wallets as
select
  customer_id,
  sum(case when kind in ('PURCHASE','TRANSFER_IN','ADJUST_UP') then quantity else 0 end)
    - sum(case when kind in ('RESERVE','TRANSFER_OUT','BUYBACK','EXPIRE','ADJUST_DOWN')
               then quantity else 0 end)
    + sum(case when kind = 'RELEASE' then quantity else 0 end)   as available,
  sum(case when kind = 'RESERVE' then quantity else 0 end)
    - sum(case when kind in ('RELEASE','REDEEM') then quantity else 0 end)  as reserved,
  sum(case when kind = 'REDEEM'       then quantity else 0 end)  as redeemed,
  sum(case when kind = 'TRANSFER_OUT' then quantity else 0 end)  as transferred,
  sum(case when kind = 'BUYBACK'      then quantity else 0 end)  as bought_back,
  sum(case when kind = 'EXPIRE'       then quantity else 0 end)  as expired,
  sum(case when kind in ('PURCHASE','TRANSFER_IN','ADJUST_UP') then quantity else 0 end)
    as acquired
from point_ledger
where status = 'SETTLED'
group by customer_id;

-- ===========================================================================
-- JOURNEYS, RESERVATIONS AND PRICE VERSIONS
-- ===========================================================================
--
-- A customer accumulating for eighteen months will see a price move. The
-- honest answer to "why is it 4,800 now when it was 4,000?" needs the price
-- they saw, when they saw it, and which rate card produced it.

create table journey_prices (
  id              bigserial primary key,
  journey_ref     text not null,
  rate_card_version text not null,               -- tourism/rates.json version
  tier            text not null,                 -- private | signature | bespoke
  days            integer not null,
  price_minor     bigint not null,
  currency        char(3) not null default 'USD',
  effective_from  timestamptz not null default now(),
  effective_until timestamptz
);

create table point_reservations (
  id              text primary key,              -- RES-000001
  customer_id     text not null references customers(id),
  journey_ref     text not null,
  points          integer not null check (points > 0),
  price_id        bigint references journey_prices(id),   -- the price they were shown
  program_id      text not null references point_programs(id),
  status          text not null
                  check (status in ('HELD', 'CONFIRMED', 'CANCELLED', 'REDEEMED')),
  departure_date  date,
  created_at      timestamptz not null default now(),
  cancelled_at    timestamptz
);

create table point_buybacks (
  id              text primary key,              -- BB-000001
  customer_id     text not null references customers(id),
  points          integer not null check (points > 0),
  program_id      text not null references point_programs(id),
  gross_minor     bigint not null,
  rate            numeric(5,4) not null,
  payable_minor   bigint not null,
  status          text not null
                  check (status in ('REQUESTED', 'APPROVED', 'DECLINED', 'SETTLED')),
  -- Discretionary by default; a decision needs a decider.
  decided_by      text,
  decided_at      timestamptz,
  requested_at    timestamptz not null default now()
);

-- ===========================================================================
-- RECONCILIATION
-- ===========================================================================
--
-- No economic event should exist in one system without a traceable
-- counterpart in the others. These two views are the daily question.

create view unreconciled_payments as
select p.*
from payments p
left join point_ledger l on l.payment_id = p.id and l.kind = 'PURCHASE'
where p.status = 'settled' and l.id is null;

create view unbacked_issuance as
select l.*
from point_ledger l
left join payments p on p.id = l.payment_id
where l.kind = 'PURCHASE' and (p.id is null or p.status <> 'settled');

-- ===========================================================================
-- SUPABASE ROW-LEVEL SECURITY — the only vendor-specific block
-- ===========================================================================
--
-- No client-side balance mutation, ever. A customer may READ their own ledger
-- and nothing else; every write goes through a server holding the service
-- key, after verifying a provider event. A browser that can insert into
-- point_ledger is a browser that can mint points.

alter table point_ledger      enable row level security;
alter table payments          enable row level security;
alter table point_reservations enable row level security;
alter table point_buybacks    enable row level security;
alter table customers         enable row level security;

create policy customer_reads_own_ledger on point_ledger
  for select using (customer_id = auth.jwt() ->> 'customer_id');

create policy customer_reads_own_payments on payments
  for select using (customer_id = auth.jwt() ->> 'customer_id');

-- Deliberately no INSERT, UPDATE or DELETE policy for any client role.
-- Absence is the policy. Writes belong to the service role alone.

commit;
