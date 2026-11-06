-- CBB Stats Lab v1
-- Server-only CBBD cache. No anon/authenticated Data API access.
-- Dashboard reads through the Streamlit server's Supabase secret key.

create table if not exists public.cbb_stats_team_season (
  season integer not null,
  season_type text not null default 'regular',
  team_id integer not null,
  team text not null,
  conference text,
  games integer,
  wins double precision,
  losses double precision,
  total_minutes double precision,
  pace double precision,
  payload jsonb not null,
  refreshed_at timestamptz not null default now(),
  primary key (season, season_type, team_id)
);

create table if not exists public.cbb_stats_player_season (
  season integer not null,
  season_type text not null default 'regular',
  team_id integer not null,
  team text not null,
  conference text,
  athlete_id integer not null,
  name text not null,
  position text,
  games double precision,
  starts double precision,
  minutes double precision,
  payload jsonb not null,
  refreshed_at timestamptz not null default now(),
  primary key (season, season_type, team_id, athlete_id)
);

create table if not exists public.cbb_stats_team_shooting (
  season integer not null,
  season_type text not null default 'regular',
  team_id integer not null,
  team text not null,
  conference text,
  tracked_shots integer,
  payload jsonb not null,
  refreshed_at timestamptz not null default now(),
  primary key (season, season_type, team_id)
);

create table if not exists public.cbb_stats_player_shooting (
  season integer not null,
  season_type text not null default 'regular',
  team_id integer not null,
  team text not null,
  conference text,
  athlete_id integer not null,
  name text not null,
  position text,
  tracked_shots integer,
  payload jsonb not null,
  refreshed_at timestamptz not null default now(),
  primary key (season, season_type, team_id, athlete_id)
);

create index if not exists cbb_stats_team_season_team_idx
  on public.cbb_stats_team_season (season desc, team);
create index if not exists cbb_stats_team_season_conference_idx
  on public.cbb_stats_team_season (season desc, conference);
create index if not exists cbb_stats_player_season_name_idx
  on public.cbb_stats_player_season (season desc, name);
create index if not exists cbb_stats_player_season_team_idx
  on public.cbb_stats_player_season (season desc, team);
create index if not exists cbb_stats_player_season_conference_idx
  on public.cbb_stats_player_season (season desc, conference);

alter table public.cbb_stats_team_season enable row level security;
alter table public.cbb_stats_player_season enable row level security;
alter table public.cbb_stats_team_shooting enable row level security;
alter table public.cbb_stats_player_shooting enable row level security;

revoke all on table public.cbb_stats_team_season from anon, authenticated;
revoke all on table public.cbb_stats_player_season from anon, authenticated;
revoke all on table public.cbb_stats_team_shooting from anon, authenticated;
revoke all on table public.cbb_stats_player_shooting from anon, authenticated;

grant select, insert, update, delete on table public.cbb_stats_team_season to service_role;
grant select, insert, update, delete on table public.cbb_stats_player_season to service_role;
grant select, insert, update, delete on table public.cbb_stats_team_shooting to service_role;
grant select, insert, update, delete on table public.cbb_stats_player_shooting to service_role;
