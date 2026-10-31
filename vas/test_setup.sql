-- ローカル PostgreSQL での検証用（Supabase では実行しない）。
-- 使い方: psql -v ON_ERROR_STOP=1 -f vas/test_setup.sql （setup_supabase.sql 実行後）
-- 各テストは失敗すると例外で止まる。最後に "ALL VAS SQL TESTS PASSED" を表示。
\set QUIET on
set role anon;

-- 1. 匿名はテーブルを直接読めない・書けない
do $$ begin
  begin perform * from public.vdt_vas_responses; raise exception 'FAIL: anon select allowed';
  exception when insufficient_privilege then null; end;
  begin insert into public.vdt_vas_responses (id, research_id, phase, eye, neck, back, fatigue, focus, research_consent)
        values (gen_random_uuid(), 'TEST01', 'before', 1, 1, 1, 1, 1, 'agree');
        raise exception 'FAIL: anon direct insert allowed';
  exception when insufficient_privilege then null; end;
  begin update public.vdt_vas_responses set eye = 0; raise exception 'FAIL: anon update allowed';
  exception when insufficient_privilege then null; end;
  begin delete from public.vdt_vas_responses; raise exception 'FAIL: anon delete allowed';
  exception when insufficient_privilege then null; end;
end $$;

-- 2. RPC で保存 → 同じ内容の再送は already_saved（行は増えない）→ 違う内容は拒否
do $$ declare r jsonb; begin
  r := public.vdt_vas_submit('11111111-2222-4333-8444-555555555555', 'TEST01', 'before', 10, 20, 30, 40, 50, 'agree');
  if r->>'status' <> 'saved' or r->>'receipt' <> '11111111' then raise exception 'FAIL first save: %', r; end if;
  r := public.vdt_vas_submit('11111111-2222-4333-8444-555555555555', 'TEST01', 'before', 10, 20, 30, 40, 50, 'agree');
  if r->>'status' <> 'already_saved' then raise exception 'FAIL retry: %', r; end if;
  begin perform public.vdt_vas_submit('11111111-2222-4333-8444-555555555555', 'TEST01', 'before', 99, 20, 30, 40, 50, 'agree');
        raise exception 'FAIL: overwrite with different content allowed';
  exception when insufficient_privilege then null; end;
  r := public.vdt_vas_submit('11111111-2222-4333-8444-666666666666', 'TEST01', 'after', 60, 70, 80, 90, 100, 'disagree');
  if r->>'status' <> 'saved' then raise exception 'FAIL after save: %', r; end if;
end $$;

-- 3. 不正値は拒否（範囲外・時点・同意・IDの形式・NULL）
do $$ declare bad text[]; i int := 0; begin
  foreach bad slice 1 in array array[
    array['TEST01','before','101','agree'], array['TEST01','before','-1','agree'],
    array['TEST01','during','10','agree'],  array['TEST01','before','10','yes'],
    array['TEST 01','before','10','agree'], array['山田','before','10','agree'],
    array['','before','10','agree'],        array['TEST01','before','10',null]] loop
    i := i + 1;
    begin
      perform public.vdt_vas_submit(gen_random_uuid(), bad[1], bad[2], bad[3]::int, 0, 0, 0, 0, bad[4]);
      raise exception 'FAIL: invalid case % accepted', i;
    exception when invalid_parameter_value then null; end;
  end loop;
end $$;

reset role;

-- 4. 保存内容の確認（管理者側）：2行のみ、TEST は is_test、created_at はサーバー時刻
do $$ declare n int; t int; begin
  select count(*), count(*) filter (where is_test and created_at > now() - interval '1 minute') into n, t
  from public.vdt_vas_responses where research_id = 'TEST01';
  if n <> 2 or t <> 2 then raise exception 'FAIL stored rows n=% test=%', n, t; end if;
end $$;

-- 5. authenticated（ログイン済み一般ユーザー）も直接アクセス・RPC不可
set role authenticated;
do $$ begin
  begin perform * from public.vdt_vas_responses; raise exception 'FAIL: authenticated select allowed';
  exception when insufficient_privilege then null; end;
  begin perform public.vdt_vas_submit(gen_random_uuid(), 'TEST02', 'before', 1, 1, 1, 1, 1, 'agree');
        raise exception 'FAIL: authenticated rpc allowed';
  exception when insufficient_privilege then null; end;
end $$;
reset role;

\echo ALL VAS SQL TESTS PASSED
