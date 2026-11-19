-- Counts and fetch status only. Raw splits stay in the existing private archive.
create table if not exists public.cbb_split_refresh_runs (
  id uuid primary key default gen_random_uuid(),
  requested_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null check (status in ('running','completed','failed')),
  feed_state text check (feed_state in ('idle','reported','not_reported')),
  requested_games integer not null default 0 check (requested_games >= 0),
  provider_events integer not null default 0 check (provider_events >= 0),
  mapped_games integer not null default 0 check (mapped_games >= 0),
  split_games integer not null default 0 check (split_games >= 0),
  rows_written integer not null default 0 check (rows_written >= 0),
  provider_observed_at timestamptz,
  error_summary text
);
create index if not exists cbb_split_refresh_runs_requested_idx on public.cbb_split_refresh_runs(requested_at desc);
alter table public.cbb_split_refresh_runs enable row level security;
revoke all on public.cbb_split_refresh_runs from public, anon, authenticated;
grant select,insert,update on public.cbb_split_refresh_runs to service_role;
