-- 第8教材 VDT VAS（実験前 T0 / 実験後 T1）
-- Supabase project: plirzczxdhddfcxldnxj
-- 既存の株価実験・vdtNext のオブジェクトには触れない（新規テーブル1つ・新規関数1つのみ）。
--
-- 方針
--  * 氏名・学籍番号は保存しない。研究用ID（vdtNext の姿勢データと共通）で紐づける。
--  * 匿名ユーザーはテーブルに直接アクセスできない（RLS有効・ポリシーなし・権限なし）。
--    保存は RPC public.vdt_vas_submit のみ。読み出し・更新・削除の経路は匿名に存在しない。
--  * 受信時刻 created_at はサーバーが付ける（クライアントは偽装できない）。
--  * 再送は回答ID（ブラウザが作るUUID）で冪等。同じ回答の再送は1行のまま、内容が違えば拒否。
--  * 研究利用への同意（agree / disagree）は回答ごとに必須。授業の記録とは独立。
--  * 研究用IDが TEST で始まる行は is_test = true（解析から除外する）。

-- 0. 旧ドラフト（anon に INSERT を直接許可していた版）が実行済みだった場合の後始末
do $$
begin
  if to_regclass('public.vdt_vas_responses') is not null then
    execute 'drop policy if exists "vas_anon_insert_only" on public.vdt_vas_responses';
    if not exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = 'vdt_vas_responses'
                     and column_name = 'research_consent') then
      raise exception 'public.vdt_vas_responses は旧ドラフトの列構成です。中身を確認してから手動で移行してください。';
    end if;
  end if;
end $$;

-- 1. 回答テーブル
create table if not exists public.vdt_vas_responses (
  id               uuid primary key,
  research_id      text not null check (research_id ~ '^[A-Za-z0-9_-]{1,32}$'),
  phase            text not null check (phase in ('before', 'after')),
  eye              smallint not null check (eye between 0 and 100),
  neck             smallint not null check (neck between 0 and 100),
  back             smallint not null check (back between 0 and 100),
  fatigue          smallint not null check (fatigue between 0 and 100),
  focus            smallint not null check (focus between 0 and 100),
  research_consent text not null check (research_consent in ('agree', 'disagree')),
  is_test          boolean generated always as (upper(research_id) like 'TEST%') stored,
  created_at       timestamptz not null default now()
);
create index if not exists vdt_vas_responses_rid_phase on public.vdt_vas_responses (research_id, phase, created_at);

alter table public.vdt_vas_responses enable row level security;
revoke all on table public.vdt_vas_responses from public, anon, authenticated;
-- ポリシーは作らない：Data API からの select / insert / update / delete はすべて拒否される。

-- 2. 保存用 RPC（匿名で呼べる唯一の入口）
create or replace function public.vdt_vas_submit(
  p_id uuid, p_research_id text, p_phase text,
  p_eye int, p_neck int, p_back int, p_fatigue int, p_focus int,
  p_research_consent text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  old public.vdt_vas_responses;
  st  text := 'saved';
begin
  if p_id is null
     or p_research_id is null or p_research_id !~ '^[A-Za-z0-9_-]{1,32}$'
     or p_phase is null or p_phase not in ('before', 'after')
     or p_eye is null or p_eye not between 0 and 100
     or p_neck is null or p_neck not between 0 and 100
     or p_back is null or p_back not between 0 and 100
     or p_fatigue is null or p_fatigue not between 0 and 100
     or p_focus is null or p_focus not between 0 and 100
     or p_research_consent is null or p_research_consent not in ('agree', 'disagree') then
    raise exception 'invalid request' using errcode = '22023';
  end if;

  begin
    insert into public.vdt_vas_responses
      (id, research_id, phase, eye, neck, back, fatigue, focus, research_consent)
    values
      (p_id, p_research_id, p_phase, p_eye, p_neck, p_back, p_fatigue, p_focus, p_research_consent);
  exception when unique_violation then
    -- 同じ回答IDの再送（通信切断後の再試行・二重タップ・同時送信）
    select * into old from public.vdt_vas_responses where id = p_id;
    if old.research_id <> p_research_id or old.phase <> p_phase
       or old.eye <> p_eye or old.neck <> p_neck or old.back <> p_back
       or old.fatigue <> p_fatigue or old.focus <> p_focus
       or old.research_consent <> p_research_consent then
      raise exception 'already registered with different content' using errcode = '42501';
    end if;
    st := 'already_saved';
  end;

  return jsonb_build_object('status', st, 'receipt', upper(left(p_id::text, 8)));
end $$;

revoke all on function public.vdt_vas_submit(uuid, text, text, int, int, int, int, int, text) from public, anon, authenticated;
grant execute on function public.vdt_vas_submit(uuid, text, text, int, int, int, int, int, text) to anon;

-- 3. 確認（RLS 有効・ポリシー 0 件・anon のテーブル権限なし・関数は anon のみ実行可）
select relrowsecurity as rls_on,
       (select count(*) from pg_policies where schemaname = 'public' and tablename = 'vdt_vas_responses') as policies,
       has_table_privilege('anon', 'public.vdt_vas_responses', 'select,insert,update,delete') as anon_table_access,
       has_function_privilege('anon', 'public.vdt_vas_submit(uuid,text,text,int,int,int,int,int,text)', 'execute') as anon_can_submit,
       has_function_privilege('authenticated', 'public.vdt_vas_submit(uuid,text,text,int,int,int,int,int,text)', 'execute') as authenticated_can_submit
from pg_class where oid = 'public.vdt_vas_responses'::regclass;
