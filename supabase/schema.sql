-- CBB Model Dashboard v1.1
-- One persistent row per published slate date. Public users can SELECT only.

create extension if not exists pgcrypto;

create table if not exists public.cbb_slates (
    id uuid primary key default gen_random_uuid(),
    slate_date date not null unique,
    model_version text not null,
    revision integer not null default 1 check (revision >= 1),

    board_filename text not null,
    board_sha256 text not null,
    board_rows integer not null check (board_rows >= 0),
    board_json jsonb not null default '[]'::jsonb,

    grading_filename text,
    grading_sha256 text,
    grading_json jsonb,
    metrics_json jsonb,

    published_at timestamptz not null default now(),
    published_by text,
    graded_at timestamptz,
    graded_by text,
    schema_version text not null default 'cbb_web_v1_1',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.cbb_slates enable row level security;

revoke all on table public.cbb_slates from anon, authenticated;
grant select on table public.cbb_slates to anon, authenticated;

-- Recreate the public read policy idempotently.
drop policy if exists "cbb_slates_public_read" on public.cbb_slates;
create policy "cbb_slates_public_read"
on public.cbb_slates
for select
to anon, authenticated
using (true);

-- No public INSERT / UPDATE / DELETE policies are created.
-- Admin writes use the server-side Supabase secret key (or legacy service_role).

grant all privileges on table public.cbb_slates to service_role;

create index if not exists cbb_slates_date_desc_idx
    on public.cbb_slates (slate_date desc);

notify pgrst, 'reload schema';
-- CBB Dashboard v1.4 Market Terminal migration
-- Append-only market observations plus one contextual row per published game.
-- Public users can SELECT. Only server-side secret/service-role clients write.

create extension if not exists pgcrypto;

create table if not exists public.cbb_market_snapshots (
    id uuid primary key default gen_random_uuid(),
    slate_date date not null,
    game_id text not null,
    provider text not null,
    provider_game_id text,
    market_type text not null check (market_type in ('spread','moneyline','total')),
    snapshot_time_utc timestamptz not null,
    snapshot_role text not null default 'observed',
    minutes_to_tip numeric,

    home_ticket_pct numeric check (home_ticket_pct between 0 and 100),
    away_ticket_pct numeric check (away_ticket_pct between 0 and 100),
    home_money_pct numeric check (home_money_pct between 0 and 100),
    away_money_pct numeric check (away_money_pct between 0 and 100),
    over_ticket_pct numeric check (over_ticket_pct between 0 and 100),
    under_ticket_pct numeric check (under_ticket_pct between 0 and 100),
    over_money_pct numeric check (over_money_pct between 0 and 100),
    under_money_pct numeric check (under_money_pct between 0 and 100),

    home_line numeric,
    away_line numeric,
    total_line numeric,
    opening_home_line numeric,
    opening_away_line numeric,
    opening_total numeric,
    home_price numeric,
    away_price numeric,
    over_price numeric,
    under_price numeric,

    source_label text,
    sportsbook_scope text,
    activity_level text,
    ticket_count bigint check (ticket_count is null or ticket_count >= 0),
    provider_signals text,
    book_count integer,
    home_spread_min numeric,
    home_spread_max numeric,
    book_spread_range numeric,
    book_agreement text,
    raw_snapshot_hash text not null unique,
    published_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.cbb_game_context (
    id uuid primary key default gen_random_uuid(),
    slate_date date not null,
    game_id text not null,
    provider text,
    provider_game_id text,
    home_rank integer check (home_rank is null or home_rank between 1 and 25),
    away_rank integer check (away_rank is null or away_rank between 1 and 25),
    home_conference text,
    away_conference text,
    conference_game boolean not null default false,
    saturday boolean not null default false,
    prime_time boolean not null default false,
    neutral_site boolean not null default false,
    local_start text,
    context_source text,
    published_by text,
    updated_at timestamptz not null default now(),
    unique (slate_date, game_id)
);

alter table public.cbb_market_snapshots add column if not exists ticket_count bigint;
alter table public.cbb_market_snapshots add column if not exists provider_signals text;
alter table public.cbb_market_snapshots add column if not exists book_count integer;
alter table public.cbb_market_snapshots add column if not exists home_spread_min numeric;
alter table public.cbb_market_snapshots add column if not exists home_spread_max numeric;
alter table public.cbb_market_snapshots add column if not exists book_spread_range numeric;
alter table public.cbb_market_snapshots add column if not exists book_agreement text;

alter table public.cbb_market_snapshots enable row level security;
alter table public.cbb_game_context enable row level security;

revoke all on table public.cbb_market_snapshots from anon, authenticated;
revoke all on table public.cbb_game_context from anon, authenticated;
grant select on table public.cbb_market_snapshots to anon, authenticated;
grant select on table public.cbb_game_context to anon, authenticated;

drop policy if exists "cbb_market_snapshots_public_read" on public.cbb_market_snapshots;
create policy "cbb_market_snapshots_public_read"
on public.cbb_market_snapshots for select to anon, authenticated using (true);

drop policy if exists "cbb_game_context_public_read" on public.cbb_game_context;
create policy "cbb_game_context_public_read"
on public.cbb_game_context for select to anon, authenticated using (true);

grant all privileges on table public.cbb_market_snapshots to service_role;
grant all privileges on table public.cbb_game_context to service_role;

create index if not exists cbb_market_snapshots_slate_game_time_idx
    on public.cbb_market_snapshots (slate_date, game_id, snapshot_time_utc);
create index if not exists cbb_market_snapshots_provider_game_idx
    on public.cbb_market_snapshots (provider, provider_game_id);
create index if not exists cbb_game_context_slate_idx
    on public.cbb_game_context (slate_date, game_id);

notify pgrst, 'reload schema';

-- CBB Dashboard v1.4.4 — Owls Insight owner-only raw betting splits
-- Raw ticket/handle percentages are service-role only.
-- Public users receive only qualitative derived notes through cbb_game_context.

create extension if not exists pgcrypto;

create table if not exists public.cbb_owner_betting_splits (
    id uuid primary key default gen_random_uuid(),
    slate_date date not null,
    game_id text not null,
    provider text not null default 'owlsinsight',
    provider_game_id text,
    market_type text not null check (market_type in ('spread','moneyline','total')),
    snapshot_time_utc timestamptz not null,
    snapshot_role text not null default 'observed',
    minutes_to_tip numeric,

    home_ticket_pct numeric check (home_ticket_pct between 0 and 100),
    away_ticket_pct numeric check (away_ticket_pct between 0 and 100),
    home_money_pct numeric check (home_money_pct between 0 and 100),
    away_money_pct numeric check (away_money_pct between 0 and 100),
    over_ticket_pct numeric check (over_ticket_pct between 0 and 100),
    under_ticket_pct numeric check (under_ticket_pct between 0 and 100),
    over_money_pct numeric check (over_money_pct between 0 and 100),
    under_money_pct numeric check (under_money_pct between 0 and 100),

    home_line numeric,
    away_line numeric,
    total_line numeric,
    opening_home_line numeric,
    opening_away_line numeric,
    opening_total numeric,
    home_price numeric,
    away_price numeric,
    over_price numeric,
    under_price numeric,

    source_label text,
    sportsbook_scope text,
    activity_level text,
    ticket_count bigint check (ticket_count is null or ticket_count >= 0),
    provider_signals text,
    book_count integer,
    home_spread_min numeric,
    home_spread_max numeric,
    book_spread_range numeric,
    book_agreement text,
    raw_snapshot_hash text not null unique,
    published_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.cbb_owner_betting_splits enable row level security;
revoke all on table public.cbb_owner_betting_splits from anon, authenticated;
grant all privileges on table public.cbb_owner_betting_splits to service_role;

-- Deliberately NO anon/authenticated SELECT policy on the owner table.
drop policy if exists "cbb_owner_betting_splits_public_read" on public.cbb_owner_betting_splits;

create index if not exists cbb_owner_betting_splits_slate_game_time_idx
    on public.cbb_owner_betting_splits (slate_date, game_id, snapshot_time_utc);
create index if not exists cbb_owner_betting_splits_provider_game_idx
    on public.cbb_owner_betting_splits (provider, provider_game_id);

alter table public.cbb_game_context add column if not exists betting_public_side text;
alter table public.cbb_game_context add column if not exists betting_money_side text;
alter table public.cbb_game_context add column if not exists betting_signal text;
alter table public.cbb_game_context add column if not exists betting_label text;
alter table public.cbb_game_context add column if not exists betting_note text;
alter table public.cbb_game_context add column if not exists betting_source text;
alter table public.cbb_game_context add column if not exists betting_books text;
alter table public.cbb_game_context add column if not exists betting_updated_at timestamptz;

notify pgrst, 'reload schema';


-- CBB Dashboard v1.4.5 — qualitative sharp-money context derived from private Owls splits.
alter table public.cbb_game_context add column if not exists betting_sharp_side text;
alter table public.cbb_game_context add column if not exists betting_sharp_signal text;
alter table public.cbb_game_context add column if not exists betting_sharp_confidence text;
alter table public.cbb_game_context add column if not exists betting_sharp_note text;
alter table public.cbb_game_context add column if not exists betting_sharp_books text;

notify pgrst, 'reload schema';
