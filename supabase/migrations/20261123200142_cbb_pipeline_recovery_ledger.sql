-- Counts-only private execution ledger. Forecasts and raw provider data are not
-- stored here. A lease prevents a delayed scheduler/manual run duplicating work.
create table public.cbb_pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  stage text not null check (stage in ('odds','splits','consensus','grading')),
  status text not null check (status in ('running','completed','idle','failed','abandoned')),
  started_at timestamptz not null default clock_timestamp(),
  lease_until timestamptz not null,
  completed_at timestamptz,
  rows_verified integer not null default 0,
  details jsonb not null default '{}'::jsonb,
  error_summary text
);
create index cbb_pipeline_stage_time on public.cbb_pipeline_runs(stage,started_at desc);
alter table public.cbb_pipeline_runs enable row level security;
revoke all on public.cbb_pipeline_runs from public,anon,authenticated;
grant select,insert,update on public.cbb_pipeline_runs to service_role;

create function public.cbb_begin_pipeline_run(p_stage text)
returns uuid language plpgsql security invoker set search_path=''
as $$
declare v_id uuid;
begin
  perform pg_advisory_xact_lock(hashtextextended('cbb_pipeline_'||p_stage,0));
  update public.cbb_pipeline_runs set status='abandoned',completed_at=clock_timestamp(),
    error_summary='Execution lease expired; a later run may safely replay idempotent writes'
    where stage=p_stage and status='running' and lease_until<clock_timestamp();
  if exists(select 1 from public.cbb_pipeline_runs where stage=p_stage and status='running') then return null; end if;
  insert into public.cbb_pipeline_runs(stage,status,lease_until)
    values(p_stage,'running',clock_timestamp()+interval '15 minutes') returning id into v_id;
  return v_id;
end;
$$;
create function public.cbb_finish_pipeline_run(p_id uuid,p_status text,p_rows integer,p_details jsonb,p_error text)
returns boolean language plpgsql security invoker set search_path=''
as $$
begin
  if p_status not in ('completed','idle','failed') then raise exception 'Invalid terminal status'; end if;
  update public.cbb_pipeline_runs set status=p_status,completed_at=clock_timestamp(),
    rows_verified=greatest(0,p_rows),details=coalesce(p_details,'{}'::jsonb),error_summary=left(p_error,250)
    where id=p_id and status='running' and lease_until>=clock_timestamp();
  return found;
end;
$$;
revoke all on function public.cbb_begin_pipeline_run(text) from public,anon,authenticated;
revoke all on function public.cbb_finish_pipeline_run(uuid,text,integer,jsonb,text) from public,anon,authenticated;
grant execute on function public.cbb_begin_pipeline_run(text) to service_role;
grant execute on function public.cbb_finish_pipeline_run(uuid,text,integer,jsonb,text) to service_role;

create function public.cbb_current_model_health(p_date date)
returns jsonb language sql stable security invoker set search_path=''
as $$
  select coalesce((select jsonb_build_object(
    'expected_slate_date',p_date,'current_slate_published',true,
    'current_slate_rows',s.board_rows,'stored_rows',jsonb_array_length(s.board_json),
    'unique_game_ids',(select count(distinct nullif(g->>'Game ID','')) from jsonb_array_elements(s.board_json) g),
    'coverage_verified',s.board_rows>0 and s.board_rows=jsonb_array_length(s.board_json)
      and s.board_rows=(select count(distinct nullif(g->>'Game ID','')) from jsonb_array_elements(s.board_json) g),
    'model_version',s.model_version,'revision',s.revision,'published_at',s.published_at)
    from public.cbb_slates s where s.slate_date=p_date order by s.revision desc limit 1),
    jsonb_build_object('expected_slate_date',p_date,'current_slate_published',false,
      'current_slate_rows',0,'stored_rows',0,'unique_game_ids',0,'coverage_verified',false));
$$;
revoke all on function public.cbb_current_model_health(date) from public,anon,authenticated;
grant execute on function public.cbb_current_model_health(date) to service_role;
