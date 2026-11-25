-- TARGET: CBB mtiwegegbmheefqombrw. Preserve published forecast revisions.
CREATE OR REPLACE FUNCTION public.mobile_research_source_v14(p_selection text DEFAULT NULL::text, p_operation text DEFAULT 'board'::text, p_fighter text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 security invoker
 SET search_path TO ''
AS $function$
declare chosen date; result jsonb;
begin
 if p_operation<>'board' then raise exception 'Unsupported operation'; end if;
 if p_selection is not null and p_selection!~'^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then raise exception 'Invalid date'; end if;
 chosen:=p_selection::date;
 if chosen is null then select slate_date into chosen from public.cbb_slates order by case when slate_date>=current_date then 0 else 1 end,case when slate_date>=current_date then slate_date end,slate_date desc limit 1; end if;
 if (select count(*) from public.cbb_slate_revisions where slate_date=chosen)>100 then raise exception 'Archive limit'; end if;
 with periods as(select slate_date::text as key,slate_date as date from public.cbb_slates order by slate_date desc limit 400),
 records as (select to_jsonb(s)-'published_by'-'graded_by' as record from public.cbb_slates s where slate_date=chosen union all select r.record-'published_by'-'graded_by' from public.cbb_slate_revisions r where slate_date=chosen),
 -- Match the same published tipoff boundaries the app uses. If archived and
 -- published tipoffs differ, each interval keeps its own price endpoints.
 game_tips as materialized (
   select distinct g->>'Game ID' as game_id,
     case when pg_input_is_valid(g->>'Start Time UTC','timestamp with time zone')
          then (g->>'Start Time UTC')::timestamptz end as starts_at
   from records cross join lateral jsonb_array_elements(record->'board_json') g
 ),
 archive as materialized (
   select m.id,m.archive_event_key,m.provider,m.provider_event_id,m.home_team,m.away_team,
     m.commence_time_utc,m.captured_at_utc,m.snapshot_role,m.capture_trigger,m.market_type,
     m.book_quotes,t.cutoff
   from public.cbb_owls_best_odds_archive m
   cross join lateral (
     select min(g.starts_at) as cutoff from game_tips g
     where g.starts_at between m.commence_time_utc-interval '30 minutes'
       and m.commence_time_utc+interval '30 minutes' and g.starts_at>m.captured_at_utc
   ) t
   where m.commence_time_utc>=chosen::timestamptz and m.commence_time_utc<(chosen+2)::timestamptz
     and m.captured_at_utc<least(m.commence_time_utc,statement_timestamp()) and t.cutoff is not null
 ),
 book_rows as (
   select m.id,m.archive_event_key,m.provider,m.provider_event_id,m.home_team,m.away_team,
     m.commence_time_utc,m.captured_at_utc,m.snapshot_role,m.capture_trigger,m.market_type,m.cutoff,b.quote,
     coalesce(nullif(b.quote->>'book_key',''),nullif(b.quote->>'book',''),b.quote->>'key') as book,
     b.quote->'is_alternate' as alternate,b.quote->'is_suspended' as suspended,
     case when btrim(b.quote->>'home_price')~'^[-+]?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'
       and pg_input_is_valid(b.quote->>'home_price','numeric') then (b.quote->>'home_price')::numeric end as hp,
     case when btrim(b.quote->>'away_price')~'^[-+]?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'
       and pg_input_is_valid(b.quote->>'away_price','numeric') then (b.quote->>'away_price')::numeric end as ap,
     case when btrim(b.quote->>'home_line')~'^[-+]?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'
       and pg_input_is_valid(b.quote->>'home_line','numeric') then (b.quote->>'home_line')::numeric end as hl,
     case when btrim(b.quote->>'away_line')~'^[-+]?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'
       and pg_input_is_valid(b.quote->>'away_line','numeric') then (b.quote->>'away_line')::numeric end as al
   from archive m cross join lateral (
     select q as quote from jsonb_array_elements(case when jsonb_typeof(m.book_quotes)='array' then m.book_quotes else '[]'::jsonb end) q
     union all
     select value||jsonb_build_object('book',key)
     from jsonb_each(case when jsonb_typeof(m.book_quotes)='object' then m.book_quotes else '{}'::jsonb end)
   ) b
 ),
 -- Keep each book's own first and last observation in each phase. Include
 -- all tied observations so the client can still flag conflicts. Separate
 -- one-sided, noncomparable, and suspended captures from valid price pairs.
 book_endpoints as (
   select b.*,min(captured_at_utc) over series as first_at,max(captured_at_utc) over series as last_at
   from book_rows b
   where nullif(book,'') is not null
   window series as (
     partition by archive_event_key,provider,provider_event_id,home_team,away_team,commence_time_utc,
       market_type,book,snapshot_role,capture_trigger,cutoff,alternate,suspended,
       (abs(hp)>=100 and (market_type='moneyline' or hl is not null)),
       (abs(ap)>=100 and (market_type='moneyline' or al is not null)),
       (market_type='moneyline' or abs(hl+al)<=.01),
       (case when alternate='true'::jsonb then hl end),(case when alternate='true'::jsonb then al end)
   )
 ),
 market_rows as (
   select id,archive_event_key,provider,provider_event_id,home_team,away_team,commence_time_utc,
     captured_at_utc,snapshot_role,capture_trigger,market_type,jsonb_agg(quote order by book,quote) as book_quotes
   from book_endpoints
   where captured_at_utc in (first_at,last_at)
   group by id,archive_event_key,provider,provider_event_id,home_team,away_team,commence_time_utc,
     captured_at_utc,snapshot_role,capture_trigger,market_type
 ),
 -- Canonical pairing remains the fallback for totals and provider aliases.
 -- Use the same price/line integrity checks as the normalizer before choosing
 -- the endpoints, so an invalid newer quote cannot hide a valid earlier one.
 paired_endpoints as (
   select m.id,m.game_id,m.provider,m.provider_game_id,m.market_type,m.snapshot_time_utc,m.snapshot_role,
     m.home_line,m.away_line,m.total_line,m.home_price,m.away_price,m.over_price,m.under_price,m.source_label,
     min(m.snapshot_time_utc) over series as first_at,max(m.snapshot_time_utc) over series as last_at
   from public.cbb_market_snapshots m
   cross join lateral (
     select min(g.starts_at) as cutoff from game_tips g
     where g.game_id=m.game_id and g.starts_at>m.snapshot_time_utc
   ) t
   where m.slate_date=chosen and m.snapshot_time_utc<statement_timestamp() and t.cutoff is not null
     and m.provider='owls_insight_odds' and nullif(m.provider_game_id,'') is not null
     and m.source_label~'^Owls Insight · [^·]+$'
     and case
       when m.market_type='total' then m.total_line>0 and abs(m.over_price)>=100 and abs(m.under_price)>=100
       when m.market_type='spread' then abs(m.home_line+m.away_line)<=.01 and abs(m.home_price)>=100 and abs(m.away_price)>=100
       when m.market_type='moneyline' then abs(m.home_price)>=100 and abs(m.away_price)>=100
       else false end
   window series as (partition by m.game_id,m.provider_game_id,m.source_label,m.market_type,m.snapshot_role,t.cutoff)
 ),
 paired_rows as (
   select to_jsonb(m)-'first_at'-'last_at' as row from paired_endpoints m where snapshot_time_utc in (first_at,last_at)
 ),
 splits as (select distinct on(game_id,provider,sportsbook_scope,market_type) to_jsonb(s)-'published_by' as row from public.cbb_owner_betting_splits s where slate_date=chosen and snapshot_time_utc<=statement_timestamp() order by game_id,provider,sportsbook_scope,market_type,snapshot_time_utc desc),
 public_batches as (select distinct on(game_id,market_type) game_id,market_type,observed_at from public.cbb_consensus_splits where slate_date=chosen and observed_at<=statement_timestamp() group by game_id,market_type,observed_at having count(distinct side)>=2 order by game_id,market_type,observed_at desc)
 select jsonb_build_object('sport','cbb','selection',chosen::text,'periods',coalesce((select jsonb_agg(p) from periods p),'[]'::jsonb),'records',coalesce((select jsonb_agg(record) from records),'[]'::jsonb),'contexts',coalesce((select jsonb_agg(to_jsonb(c)-'published_by') from public.cbb_game_context c where slate_date=chosen),'[]'::jsonb),'teams',coalesce((select jsonb_agg(t) from public.cbb_stats_team_season t where season in(extract(year from chosen)::int,extract(year from chosen)::int+1)),'[]'::jsonb),'markets',coalesce((select jsonb_agg(m order by captured_at_utc,id) from market_rows m),'[]'::jsonb),'pairedMarkets',coalesce((select jsonb_agg(row order by row->>'snapshot_time_utc',row->>'id') from paired_rows),'[]'::jsonb),'splits',coalesce((select jsonb_agg(row) from splits),'[]'::jsonb),'collegeHistory',coalesce((select jsonb_agg(h order by h.start_time,h.event_id) from public.college_game_history h where h.sport='cbb' and h.season=(extract(year from chosen)::int+case when extract(month from chosen)>=7 then 1 else 0 end) and (h.home_team in(select g->>'Home Team' from records cross join lateral jsonb_array_elements(record->'board_json') g union select g->>'Away Team' from records cross join lateral jsonb_array_elements(record->'board_json') g) or h.away_team in(select g->>'Home Team' from records cross join lateral jsonb_array_elements(record->'board_json') g union select g->>'Away Team' from records cross join lateral jsonb_array_elements(record->'board_json') g)) and h.start_time<statement_timestamp()),'[]'::jsonb),'collegeHistoryCoverage',coalesce((select jsonb_agg(c) from (select r.* from public.college_history_refresh_runs r where r.sport='cbb' and r.season=(extract(year from chosen)::int+case when extract(month from chosen)>=7 then 1 else 0 end) and r.status='completed' and r.complete=true order by r.completed_at desc limit 1) c),'[]'::jsonb),'publicSplits',coalesce((select jsonb_agg(c) from public.cbb_consensus_splits c join public_batches b using(game_id,market_type,observed_at) where slate_date=chosen),'[]'::jsonb)) into result;
 return result;
end $function$;
revoke all on function public.mobile_research_source_v14(text,text,text) from public,anon,authenticated;
grant execute on function public.mobile_research_source_v14(text,text,text) to service_role;
