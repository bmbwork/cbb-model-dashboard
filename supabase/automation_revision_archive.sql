-- Preserve existing/current publications and all future revisions, without rewriting model values.
create schema if not exists stat_factory_internal;
revoke all on schema stat_factory_internal from public, anon, authenticated;
create table if not exists public.cbb_slate_revisions (
  slate_date date not null,
  revision integer not null,
  board_sha256 text not null,
  record jsonb not null,
  archived_at timestamptz not null default now(),
  primary key(slate_date, revision)
);
alter table public.cbb_slate_revisions enable row level security;
revoke all on public.cbb_slate_revisions from public, anon, authenticated;
grant select on public.cbb_slate_revisions to anon, authenticated;
grant all on public.cbb_slate_revisions to service_role;
create policy cbb_revisions_published_read on public.cbb_slate_revisions
for select to anon, authenticated using (
  record->>'published_at' is not null and exists(
    select 1 from public.cbb_slates s where s.slate_date=cbb_slate_revisions.slate_date
  )
);
insert into public.cbb_slate_revisions(slate_date,revision,board_sha256,record)
select s.slate_date,s.revision,s.board_sha256,to_jsonb(s) from public.cbb_slates s
on conflict (slate_date,revision) do nothing;
create or replace function stat_factory_internal.archive_cbb_revision()
returns trigger language plpgsql security invoker set search_path='' as $$
declare prior jsonb;
begin
  select record into prior from public.cbb_slate_revisions
    where slate_date=new.slate_date and revision=new.revision;
  if prior is not null and (
    prior->>'board_sha256' is distinct from new.board_sha256 or
    prior->'board_json' is distinct from to_jsonb(new)->'board_json' or
    prior->>'model_version' is distinct from new.model_version
  ) then
    raise exception 'Immutable forecast revision cannot be overwritten';
  end if;
  insert into public.cbb_slate_revisions(slate_date,revision,board_sha256,record)
  values(new.slate_date,new.revision,new.board_sha256,to_jsonb(new))
  on conflict (slate_date,revision) do update
    set record=cbb_slate_revisions.record || jsonb_build_object('grading_filename', to_jsonb(new)->'grading_filename', 'grading_sha256', to_jsonb(new)->'grading_sha256', 'grading_json', to_jsonb(new)->'grading_json', 'metrics_json', to_jsonb(new)->'metrics_json', 'graded_at', to_jsonb(new)->'graded_at', 'graded_by', to_jsonb(new)->'graded_by', 'updated_at', to_jsonb(new)->'updated_at');
  return new;
end $$;
revoke all on function stat_factory_internal.archive_cbb_revision() from public, anon, authenticated;
grant usage on schema stat_factory_internal to service_role;
grant execute on function stat_factory_internal.archive_cbb_revision() to service_role;
create trigger cbb_preserve_forecast_revision after insert or update on public.cbb_slates
for each row execute function stat_factory_internal.archive_cbb_revision();
