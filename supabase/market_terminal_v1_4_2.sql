-- CBB Dashboard v1.4.2 Market Terminal migration — The Odds API primary
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
