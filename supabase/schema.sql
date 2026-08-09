-- CBB Model Dashboard v1.1
-- One persistent row per published slate date. Public users can SELECT only.

create extension if not exists pgcrypto;

create table if not exists public.cbb_slates (
    id uuid primary key default gen_random_uuid(),
    slate_date date not null unique,
    model_version text not null,
    revision integer not null default 1 check (revision >= 1),

    board_filename text not null,
    board_sha256 text not null,
    board_rows integer not null check (board_rows >= 0),
    board_json jsonb not null default '[]'::jsonb,

    grading_filename text,
    grading_sha256 text,
    grading_json jsonb,
    metrics_json jsonb,

    published_at timestamptz not null default now(),
    published_by text,
    graded_at timestamptz,
    graded_by text,
    schema_version text not null default 'cbb_web_v1_1',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.cbb_slates enable row level security;

revoke all on table public.cbb_slates from anon, authenticated;
grant select on table public.cbb_slates to anon, authenticated;

-- Recreate the public read policy idempotently.
drop policy if exists "cbb_slates_public_read" on public.cbb_slates;
create policy "cbb_slates_public_read"
on public.cbb_slates
for select
to anon, authenticated
using (true);

-- No public INSERT / UPDATE / DELETE policies are created.
-- Admin writes use the server-side Supabase secret key (or legacy service_role).

grant all privileges on table public.cbb_slates to service_role;

create index if not exists cbb_slates_date_desc_idx
    on public.cbb_slates (slate_date desc);

notify pgrst, 'reload schema';
