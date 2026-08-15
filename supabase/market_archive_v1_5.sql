-- CBB Dashboard v1.5.0: independent Owls best-odds historical archive.
-- Run once in Supabase SQL Editor before enabling the GitHub Actions scheduler.

create extension if not exists pgcrypto;

create table if not exists public.cbb_owls_best_odds_archive (
    id uuid primary key default gen_random_uuid(),
    archive_event_key text not null,
    provider text not null default 'owls_insight',
    provider_event_id text,
    home_team text not null,
    away_team text not null,
    commence_time_utc timestamptz not null,
    captured_at_utc timestamptz not null,
    provider_timestamp_utc timestamptz,
    snapshot_role text not null check (snapshot_role in ('open','observed','close')),
    capture_trigger text not null,
    market_type text not null check (market_type in ('spread','moneyline')),
    best_home_line numeric,
    best_home_price numeric,
    best_home_book_key text,
    best_home_book_title text,
    best_away_line numeric,
    best_away_price numeric,
    best_away_book_key text,
    best_away_book_title text,
    book_count integer not null default 0,
    books_seen jsonb not null default '[]'::jsonb,
    book_quotes jsonb not null default '[]'::jsonb,
    raw_snapshot_hash text not null unique,
    created_at timestamptz not null default now()
);

create index if not exists cbb_best_odds_event_capture_idx
    on public.cbb_owls_best_odds_archive (archive_event_key, captured_at_utc);
create index if not exists cbb_best_odds_commence_idx
    on public.cbb_owls_best_odds_archive (commence_time_utc);
create index if not exists cbb_best_odds_role_idx
    on public.cbb_owls_best_odds_archive (snapshot_role, commence_time_utc);

alter table public.cbb_owls_best_odds_archive enable row level security;

drop policy if exists "CBB public reads best odds archive" on public.cbb_owls_best_odds_archive;
create policy "CBB public reads best odds archive"
    on public.cbb_owls_best_odds_archive
    for select
    to anon, authenticated
    using (true);

-- Writes are intentionally not granted to anon/authenticated. The scheduled
-- GitHub Action writes with the Supabase secret/service-role key.

-- Lightweight card-state view: retain full hourly history in the base table,
-- but expose only open/current/close rows to Streamlit and scheduler state checks.
create or replace view public.cbb_owls_best_odds_card_state
with (security_invoker = true)
as
with ranked as (
    select
        a.*,
        row_number() over (
            partition by archive_event_key, market_type
            order by captured_at_utc asc, id asc
        ) as rn_open,
        row_number() over (
            partition by archive_event_key, market_type
            order by captured_at_utc desc, id desc
        ) as rn_current,
        row_number() over (
            partition by archive_event_key, market_type, snapshot_role
            order by captured_at_utc desc, id desc
        ) as rn_role
    from public.cbb_owls_best_odds_archive a
)
select
    id, archive_event_key, provider, provider_event_id, home_team, away_team,
    commence_time_utc, captured_at_utc, provider_timestamp_utc,
    'open'::text as snapshot_role, capture_trigger, market_type,
    best_home_line, best_home_price, best_home_book_key, best_home_book_title,
    best_away_line, best_away_price, best_away_book_key, best_away_book_title,
    book_count, books_seen, book_quotes, raw_snapshot_hash, created_at
from ranked
where rn_open = 1
union all
select
    id, archive_event_key, provider, provider_event_id, home_team, away_team,
    commence_time_utc, captured_at_utc, provider_timestamp_utc,
    'current'::text as snapshot_role, capture_trigger, market_type,
    best_home_line, best_home_price, best_home_book_key, best_home_book_title,
    best_away_line, best_away_price, best_away_book_key, best_away_book_title,
    book_count, books_seen, book_quotes, raw_snapshot_hash, created_at
from ranked
where rn_current = 1
union all
select
    id, archive_event_key, provider, provider_event_id, home_team, away_team,
    commence_time_utc, captured_at_utc, provider_timestamp_utc,
    'close'::text as snapshot_role, capture_trigger, market_type,
    best_home_line, best_home_price, best_home_book_key, best_home_book_title,
    best_away_line, best_away_price, best_away_book_key, best_away_book_title,
    book_count, books_seen, book_quotes, raw_snapshot_hash, created_at
from ranked
where snapshot_role = 'close' and rn_role = 1;

grant select on public.cbb_owls_best_odds_card_state to anon, authenticated;
