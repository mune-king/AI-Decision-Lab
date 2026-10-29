-- vdtNext ZIP uploader: Supabase setup (run once in the SQL Editor of project plirzczxdhddfcxldnxj).
-- Safe to re-run. Does not touch the AI Decision Lab objects (decision_private, save_decision_run, ...).

-- 1. Private Storage bucket. Anonymous users may only CREATE new objects under submissions/<uuid>.zip.
--    They cannot list, download, overwrite or delete anything.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('vdtnext-pilot', 'vdtnext-pilot', false, 31457280, array['application/zip', 'application/x-zip-compressed'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "vdtnext anon insert zip" on storage.objects;
create policy "vdtnext anon insert zip" on storage.objects for insert to anon
with check (bucket_id = 'vdtnext-pilot' and name ~ '^submissions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.zip$');

-- 2. Research data (no student number, no original file name).
create table if not exists public.vdtnext_uploads (
 id uuid primary key,
 research_id text not null check (research_id ~ '^[A-Za-z0-9_-]{1,32}$'),
 age smallint not null check (age between 15 and 99),
 measured_on date not null,
 font_order text not null check (font_order in ('12-10.5-9', '12-9-10.5', '10.5-12-9', '10.5-9-12', '9-12-10.5', '9-10.5-12')),
 research_consent text not null check (research_consent in ('agree', 'disagree')),
 storage_bucket text not null default 'vdtnext-pilot',
 storage_path text not null unique,
 file_bytes bigint not null,
 file_sha256 text not null check (file_sha256 ~ '^[0-9a-f]{64}$'),
 submitted_at timestamptz not null default now()
);
alter table public.vdtnext_uploads enable row level security;
revoke all on table public.vdtnext_uploads from public, anon, authenticated;

-- 3. Course-submission record (student number) kept apart from the research table.
--    Not exposed through the Data API. The upload_id link is the correspondence table; keep access limited to the instructor.
create schema if not exists vdtnext_private;
revoke all on schema vdtnext_private from public, anon, authenticated;
create table if not exists vdtnext_private.course_submissions (
 upload_id uuid primary key references public.vdtnext_uploads(id) on delete cascade,
 student_number text not null check (student_number ~ '^[A-Za-z0-9-]{4,20}$'),
 submitted_at timestamptz not null default now()
);
alter table vdtnext_private.course_submissions enable row level security;

-- 4. Registration RPC: callable anonymously, only after the ZIP really exists in Storage.
create or replace function public.vdtnext_register_upload(
 p_id uuid, p_research_id text, p_age int, p_measured_on date, p_font_order text,
 p_research_consent text, p_sha256 text, p_student_number text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare path text := 'submissions/' || p_id::text || '.zip'; bytes bigint; old public.vdtnext_uploads;
begin
 if p_id is null or p_research_id is null or p_research_id !~ '^[A-Za-z0-9_-]{1,32}$'
  or p_age is null or p_age not between 15 and 99
  or p_measured_on is null or p_measured_on < date '2026-01-01' or p_measured_on > current_date + 1
  or p_font_order is null or p_font_order not in ('12-10.5-9', '12-9-10.5', '10.5-12-9', '10.5-9-12', '9-12-10.5', '9-10.5-12')
  or p_research_consent is null or p_research_consent not in ('agree', 'disagree')
  or p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$'
  or p_student_number is null or p_student_number !~ '^[A-Za-z0-9-]{4,20}$'
  or upper(p_student_number) = upper(p_research_id) then
  raise exception 'invalid request' using errcode = '22023';
 end if;
 select (o.metadata->>'size')::bigint into bytes from storage.objects o where o.bucket_id = 'vdtnext-pilot' and o.name = path;
 if not found then raise exception 'zip not found in storage' using errcode = 'P0002'; end if;
 select * into old from public.vdtnext_uploads where id = p_id;
 if found then
  -- Idempotent retry of the same submission; anything else is rejected.
  if old.research_id <> p_research_id or old.age <> p_age or old.measured_on <> p_measured_on or old.font_order <> p_font_order
   or old.research_consent <> p_research_consent or old.file_sha256 <> p_sha256 then
   raise exception 'already registered' using errcode = '42501';
  end if;
 else
  insert into public.vdtnext_uploads (id, research_id, age, measured_on, font_order, research_consent, storage_path, file_bytes, file_sha256)
  values (p_id, p_research_id, p_age, p_measured_on, p_font_order, p_research_consent, path, bytes, p_sha256);
  insert into vdtnext_private.course_submissions (upload_id, student_number) values (p_id, upper(p_student_number));
 end if;
 return jsonb_build_object('upload_id', p_id, 'stored_bytes', bytes, 'receipt', upper(left(p_id::text, 8)));
end $$;
revoke all on function public.vdtnext_register_upload(uuid, text, int, date, text, text, text, text) from public, anon, authenticated;
grant execute on function public.vdtnext_register_upload(uuid, text, int, date, text, text, text, text) to anon;

-- 5. Check (should return bucket public=false, the policy and the empty tables).
select id, public, file_size_limit, allowed_mime_types from storage.buckets where id = 'vdtnext-pilot';
