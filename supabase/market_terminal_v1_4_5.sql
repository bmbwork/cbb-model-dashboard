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

-- v1.4.5 qualitative sharp-money fields derived from owner-only split data.
-- No raw percentages are added to the public context table.
alter table public.cbb_game_context add column if not exists betting_sharp_side text;
alter table public.cbb_game_context add column if not exists betting_sharp_signal text;
alter table public.cbb_game_context add column if not exists betting_sharp_confidence text;
alter table public.cbb_game_context add column if not exists betting_sharp_note text;
alter table public.cbb_game_context add column if not exists betting_sharp_books text;

notify pgrst, 'reload schema';
