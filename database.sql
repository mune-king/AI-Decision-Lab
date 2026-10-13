create schema if not exists decision_private;
revoke all on schema decision_private from public, anon, authenticated;
create table decision_private.runs (
 id uuid primary key, secret_hash text not null,
 condition text not null check(condition in ('A','B','C','D','E')),
 rows jsonb not null default '[]', started_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
alter table decision_private.runs enable row level security;
create table decision_private.researchers(user_id uuid primary key references auth.users(id));
alter table decision_private.researchers enable row level security;
create function public.save_decision_run(p_run uuid,p_secret text,p_condition text,p_rows jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare old decision_private.runs; n int; i int; r jsonb; mode text; st int; price bigint; sh bigint:=100; ca bigint:=100000; q bigint; act text; clean jsonb:='[]'; prices int[]:=array[1000,950,900,850,800,750,700,650,600,650,700,750,800,850,900,950,1000];
begin
 if p_run is null or p_secret is null or p_secret !~ '^[0-9a-f]{64}$' or p_condition is null or p_condition not in ('A','B','C','D','E') or jsonb_typeof(p_rows) is distinct from 'array' then raise exception 'invalid request'; end if;
 n:=jsonb_array_length(p_rows);
 if n>34 or octet_length(p_rows::text)>65536 then raise exception 'invalid length'; end if;
 for i in 0..n-1 loop
  r:=p_rows->i; st:=i%17+1; mode:=case when i<17 then 'M0' else 'M1' end; price:=prices[st];
  if st=1 then sh:=100; ca:=100000; end if;
  if (r->>'step')::int is distinct from st or r->>'market_mode' is distinct from mode or (r->>'price_yen')::bigint is distinct from price or r->>'market_condition' is distinct from (case when mode='M0' then 'NONE' else p_condition end) then raise exception 'invalid sequence'; end if;
  q:=(r->>'trade_quantity')::bigint; act:=r->>'action';
  if q is null or q<0 or q>1000000 or act is null or act not in ('hold','sell','buy') or (act='hold' and q<>0) or (act<>'hold' and q=0) then raise exception 'invalid trade'; end if;
  if act='sell' then sh:=sh-q; ca:=ca+q*price; elsif act='buy' then sh:=sh+q; ca:=ca-q*price; end if;
  if sh<0 or ca<0 or (r->>'final_shares')::bigint is distinct from sh or (r->>'cash_yen')::bigint is distinct from ca or (r->>'total_assets_yen')::bigint is distinct from ca+sh*price or (r->>'answered_at_utc')::timestamptz is null then raise exception 'invalid balance'; end if;
  clean:=clean||jsonb_build_array(jsonb_build_object('market_mode',mode,'market_condition',r->>'market_condition','run_order',case when i<17 then 1 else 2 end,'step',st,'price_yen',price,'action',act,'trade_quantity',q,'final_shares',sh,'cash_yen',ca,'total_assets_yen',ca+sh*price,'initial_assets_yen',200000,'external_funds_yen',0,'answered_at_utc',r->>'answered_at_utc','consent_date',r->>'consent_date','edits_before_confirmation',r->'edits_before_confirmation','version','v1.0','condition_allocation','v10_random_ID_hash'));
 end loop;
 insert into decision_private.runs(id,secret_hash,condition) values(p_run,encode(extensions.digest(p_secret,'sha256'),'hex'),p_condition) on conflict do nothing;
 select * into old from decision_private.runs where id=p_run for update;
 if old.secret_hash<>encode(extensions.digest(p_secret,'sha256'),'hex') or old.condition<>p_condition then raise exception 'invalid capability' using errcode='42501'; end if;
 for i in 0..least(jsonb_array_length(old.rows),n)-1 loop
 if old.rows->i is distinct from clean->i then raise exception 'confirmed answer cannot be changed'; end if;
 end loop;
 if n>=jsonb_array_length(old.rows) then update decision_private.runs set rows=clean,updated_at=now() where id=p_run; end if;
 return jsonb_build_object('run_id',p_run,'saved_count',greatest(n,jsonb_array_length(old.rows)));
end $$;
revoke all on function public.save_decision_run(uuid,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.save_decision_run(uuid,text,text,jsonb) to anon;
create function public.research_decision_runs() returns jsonb language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not exists(select 1 from decision_private.researchers where user_id=auth.uid()) then raise exception 'researcher access required' using errcode='42501'; end if;
 return coalesce((select jsonb_agg(jsonb_build_object('run_id',id,'condition',condition,'rows',rows,'started_at',started_at,'updated_at',updated_at)) from decision_private.runs),'[]');
end $$;
revoke all on function public.research_decision_runs() from public,anon,authenticated;
grant execute on function public.research_decision_runs() to authenticated;
