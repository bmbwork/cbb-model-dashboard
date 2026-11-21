-- Apply independently to each sport project. No forecast or model tables change.
create table if not exists public.college_game_history (
 sport text not null check(sport in ('cfb','cbb')),
 season integer not null check(season between 2000 and 2100),
 event_id text not null,
 start_time timestamptz not null,
 completed_at timestamptz,
 home_team text not null,
 away_team text not null,
 home_team_id text,
 away_team_id text,
 home_score integer not null check(home_score>=0),
 away_score integer not null check(away_score>=0),
 home_rank integer check(home_rank between 1 and 25),
 away_rank integer check(away_rank between 1 and 25),
 rankings_verified boolean not null default false,
 ranking_source text,
 ranking_as_of timestamptz,
 ranking_semantics text check(ranking_semantics in ('game_week','dated_poll')),
 game_week integer,
 neutral_site boolean,
 overtimes integer check(overtimes>=0),
 result_source text not null,
 result_source_url text not null,
 fetched_at timestamptz not null,
 primary key(sport,season,event_id),
 check(home_team<>away_team),
 check(home_score<>away_score),
 check(completed_at is null or completed_at>=start_time),
 check(not rankings_verified or ranking_source is not null)
);
create index if not exists college_game_history_season_time_idx on public.college_game_history(sport,season,start_time);
create table if not exists public.college_history_refresh_runs (
 id uuid primary key default gen_random_uuid(),
 sport text not null check(sport in ('cfb','cbb')),
 season integer not null check(season between 2000 and 2100),
 requested_at timestamptz not null default now(),
 completed_at timestamptz,
 status text not null check(status in ('running','completed','failed')),
 complete boolean not null default false,
 source text not null,
 games_count integer not null default 0 check(games_count>=0),
 ranked_games_count integer not null default 0 check(ranked_games_count>=0),
 covered_teams text[] not null default '{}',
 complete_from timestamptz,
 complete_through timestamptz,
 error_summary text
);
create index if not exists college_history_refresh_season_time_idx on public.college_history_refresh_runs(sport,season,completed_at desc);
alter table public.college_game_history enable row level security;
alter table public.college_history_refresh_runs enable row level security;
revoke all on public.college_game_history,public.college_history_refresh_runs from public,anon,authenticated;
grant select,insert,update on public.college_game_history,public.college_history_refresh_runs to service_role;
comment on table public.college_game_history is 'Private verified college finals and game-time AP context; downstream research only, never model inputs. fetched_at is first observation of unchanged verified score.';
comment on table public.college_history_refresh_runs is 'Private full-season result coverage provenance. A partial or failed capture must not become a season W-L record.';

-- TARGET: CBB mtiwegegbmheefqombrw. Historical revisions remain timestamped.
create or replace function public.mobile_research_source_v14(p_selection text default null,p_operation text default 'board',p_fighter text default null)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare chosen date; result jsonb;
begin
 if p_operation<>'board' then raise exception 'Unsupported operation'; end if;
 if p_selection is not null and p_selection!~'^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then raise exception 'Invalid date'; end if;
 chosen:=p_selection::date;
 if chosen is null then select slate_date into chosen from public.cbb_slates order by case when slate_date>=current_date then 0 else 1 end,case when slate_date>=current_date then slate_date end,slate_date desc limit 1; end if;
 if (select count(*) from public.cbb_slate_revisions where slate_date=chosen)>100 then raise exception 'Archive limit'; end if;
 if (select count(*) from public.cbb_owls_best_odds_archive m where m.commence_time_utc>=chosen::timestamptz and m.commence_time_utc<(chosen+2)::timestamptz and m.captured_at_utc<least(m.commence_time_utc,statement_timestamp()))>20000 then raise exception 'Market archive limit; refusing truncated history'; end if;
 if (select count(*) from public.cbb_market_snapshots m where m.slate_date=chosen and m.snapshot_time_utc<statement_timestamp())>20000 then raise exception 'Paired market archive limit; refusing truncated history'; end if;
 with periods as(select slate_date::text as key,slate_date as date from public.cbb_slates order by slate_date desc limit 400),
 records as (select to_jsonb(s)-'published_by'-'graded_by' as record from public.cbb_slates s where slate_date=chosen union all select r.record-'published_by'-'graded_by' from public.cbb_slate_revisions r where slate_date=chosen),
 -- Read genuine retained observations before reducing by sportsbook. The
 -- card-state view chooses its first record across all books and loses books
 -- that join later, as in the Kansas State/Northridge tester report.
 market_rows as (select m.* from public.cbb_owls_best_odds_archive m where m.commence_time_utc>=chosen::timestamptz and m.commence_time_utc<(chosen+2)::timestamptz and m.captured_at_utc<least(m.commence_time_utc,statement_timestamp())),
 -- The web dashboard already retains canonical CBBD game IDs and board-side
 -- orientation here. Keep these genuine reference-book prices for provider
 -- abbreviations that cannot be joined safely by names and for totals.
 paired_rows as (select to_jsonb(m)-'published_by'-'raw_snapshot_hash' as row from public.cbb_market_snapshots m where m.slate_date=chosen and m.snapshot_time_utc<statement_timestamp()),
 splits as (select distinct on(game_id,provider,sportsbook_scope,market_type) to_jsonb(s)-'published_by' as row from public.cbb_owner_betting_splits s where slate_date=chosen and snapshot_time_utc<=statement_timestamp() order by game_id,provider,sportsbook_scope,market_type,snapshot_time_utc desc),
 public_batches as (select distinct on(game_id,market_type) game_id,market_type,observed_at from public.cbb_consensus_splits where slate_date=chosen and observed_at<=statement_timestamp() group by game_id,market_type,observed_at having count(distinct side)>=2 order by game_id,market_type,observed_at desc)
 select jsonb_build_object('sport','cbb','selection',chosen::text,'periods',coalesce((select jsonb_agg(p) from periods p),'[]'::jsonb),'records',coalesce((select jsonb_agg(record) from records),'[]'::jsonb),'contexts',coalesce((select jsonb_agg(to_jsonb(c)-'published_by') from public.cbb_game_context c where slate_date=chosen),'[]'::jsonb),'teams',coalesce((select jsonb_agg(t) from public.cbb_stats_team_season t where season in(extract(year from chosen)::int,extract(year from chosen)::int+1)),'[]'::jsonb),'markets',coalesce((select jsonb_agg(m) from market_rows m),'[]'::jsonb),'pairedMarkets',coalesce((select jsonb_agg(row) from paired_rows),'[]'::jsonb),'splits',coalesce((select jsonb_agg(row) from splits),'[]'::jsonb),'collegeHistory',coalesce((select jsonb_agg(h order by h.start_time,h.event_id) from public.college_game_history h where h.sport='cbb' and h.season=(extract(year from chosen)::int+case when extract(month from chosen)>=7 then 1 else 0 end) and (h.home_team in(select g->>'Home Team' from records cross join lateral jsonb_array_elements(record->'board_json') g union select g->>'Away Team' from records cross join lateral jsonb_array_elements(record->'board_json') g) or h.away_team in(select g->>'Home Team' from records cross join lateral jsonb_array_elements(record->'board_json') g union select g->>'Away Team' from records cross join lateral jsonb_array_elements(record->'board_json') g)) and h.start_time<statement_timestamp()),'[]'::jsonb),'collegeHistoryCoverage',coalesce((select jsonb_agg(c) from (select r.* from public.college_history_refresh_runs r where r.sport='cbb' and r.season=(extract(year from chosen)::int+case when extract(month from chosen)>=7 then 1 else 0 end) and r.status='completed' and r.complete=true order by r.completed_at desc limit 1) c),'[]'::jsonb),'publicSplits',coalesce((select jsonb_agg(c) from public.cbb_consensus_splits c join public_batches b using(game_id,market_type,observed_at) where slate_date=chosen),'[]'::jsonb)) into result;
 return result;
end $$;
revoke all on function public.mobile_research_source_v14(text,text,text) from public,anon,authenticated;
grant execute on function public.mobile_research_source_v14(text,text,text) to service_role;

-- Required underlying table for the security-invoker card-state view.
-- Public client grants are not expanded.
grant select on table public.cbb_owls_best_odds_archive to service_role;
grant select on table public.cbb_market_snapshots to service_role;
