-- Aggregated public sportsbook consensus, kept separate from Owl book-specific splits.
create table if not exists public.cbb_consensus_refresh_runs (
  refresh_run_id text primary key,
  requested_at timestamptz not null,
  completed_at timestamptz,
  status text not null check (status in ('running','completed','failed')),
  source_url text not null,
  requested_games integer,
  parsed_matchups integer,
  matched_events integer,
  unmatched_active_events integer,
  diagnostics jsonb not null default '{}'::jsonb
);

create table if not exists public.cbb_consensus_splits (
  consensus_split_id bigserial primary key,
  refresh_run_id text not null references public.cbb_consensus_refresh_runs(refresh_run_id) on delete cascade,
  slate_date date not null,
  game_id text not null,
  market_type text not null check (market_type in ('spread','moneyline','total')),
  side text not null check (side in ('spread_away','spread_home','moneyline_away','moneyline_home','total_over','total_under')),
  line double precision,
  tickets_pct double precision not null check (tickets_pct between 0 and 100),
  handle_pct double precision not null check (handle_pct between 0 and 100),
  observed_at timestamptz not null,
  unique(refresh_run_id,slate_date,game_id,market_type,side)
);
create index if not exists idx_cbb_consensus_splits_game_time on public.cbb_consensus_splits(slate_date,game_id,observed_at desc);
alter table public.cbb_consensus_refresh_runs enable row level security;
alter table public.cbb_consensus_splits enable row level security;
revoke all on table public.cbb_consensus_refresh_runs from anon, authenticated;
revoke all on table public.cbb_consensus_splits from anon, authenticated;
drop policy if exists "public can read CBB aggregated consensus splits" on public.cbb_consensus_splits;
create policy "public can read CBB aggregated consensus splits" on public.cbb_consensus_splits for select to anon, authenticated using (true);
grant select on public.cbb_consensus_splits to anon, authenticated;
grant select, insert, update, delete on public.cbb_consensus_refresh_runs to service_role;
grant select, insert, update, delete on public.cbb_consensus_splits to service_role;
grant usage, select on sequence public.cbb_consensus_splits_consensus_split_id_seq to service_role;
grant usage on schema public to anon, authenticated, service_role;
