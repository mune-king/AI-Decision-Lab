# 第8教材 VDT VAS アンケート

視覚探索（12pt・10分）の開始直前 T0 と終了直後 T1 に、5項目（目・首肩・腰背中・全身疲労・集中のしづらさ）を 0–100 で回答する。株価実験（ルートの `index.html` 等）と `vdtnext/` とは独立しており、それらのファイルは変更しない。

## 構成

- `index.html`：学生用ページ（静的、ビルド不要）。保存先は Supabase RPC `public.vdt_vas_submit`。
- `setup_supabase.sql`：Supabase SQL（プロジェクト `plirzczxdhddfcxldnxj`）。新規テーブル `public.vdt_vas_responses` と新規関数 `public.vdt_vas_submit` のみを作る。再実行しても安全。
- `test_setup.sql`・`test-vas.cjs`：ローカル PostgreSQL と Chromium による検証（Supabase では実行しない）。

## 安全設計

- **保存権限**：テーブルは RLS 有効・ポリシーなし・`anon`／`authenticated` の権限なし。匿名ユーザーは Data API でテーブルを読む・書く・消すことができず、他人の回答は見えない。保存は `anon` だけが実行できる RPC のみで、返すのは受付番号と状態だけ。受信時刻はサーバーが付ける。
- **研究用ID**：半角英数字と `-` `_`、32文字まで（vdtNext と同じ形式）。氏名・学籍番号は保存しない。
- **重複送信**：回答IDはブラウザが作る UUID。同じ回答の再送（通信断・二重タップ）は `already_saved` を返し、1行のまま。同じIDで内容を変えた送信は拒否する。同じ研究用ID・同じ時点で別の回答が届いた場合は削除せずに保存し、解析時に最初の1件を採用する（ID入力ミスのとき、本来のIDの学生が送信できなくなるのを避けるため）。同じブラウザで同じID・同じ時点を再送しようとすると確認ダイアログを出す。
- **研究利用への同意**：回答ごとに agree／disagree の選択が必須。同意しなくても保存され、成績には影響しない。解析は `research_consent = 'agree'` のみを使う。
- **テストデータ**：研究用IDが `TEST` で始まる行は生成列 `is_test = true` になる。解析では除外し、試験後に削除する。
- **スライダー**：初期値に引っ張られないよう、つまみを一度も動かしていない項目があると送信できない。

## 教員用クエリ（Supabase SQL Editor）

研究用データ（T0・T1 とも同意あり、各時点で最初の1件）：

```sql
with first as (
  select distinct on (research_id, phase) *
  from public.vdt_vas_responses
  where not is_test
  order by research_id, phase, created_at
)
select b.research_id,
       b.eye b_eye, b.neck b_neck, b.back b_back, b.fatigue b_fatigue, b.focus b_focus,
       a.eye a_eye, a.neck a_neck, a.back a_back, a.fatigue a_fatigue, a.focus a_focus,
       b.created_at t0_at, a.created_at t1_at
from first b join first a on a.research_id = b.research_id and a.phase = 'after'
where b.phase = 'before' and b.research_consent = 'agree' and a.research_consent = 'agree'
order by b.research_id;
```

重複・欠損の点検：

```sql
select research_id, phase, count(*) n, min(created_at), max(created_at)
from public.vdt_vas_responses where not is_test
group by 1, 2 having count(*) > 1 order by 1, 2;
```

テストデータの削除：`delete from public.vdt_vas_responses where is_test;`

## 検証

```bash
psql "$PGURL" -v ON_ERROR_STOP=1 -f vas/setup_supabase.sql && psql "$PGURL" -v ON_ERROR_STOP=1 -f vas/test_setup.sql
PGURL=... node vas/test-vas.cjs
```

ローカル検証には `anon`・`authenticated` ロールが必要（Supabase の既定権限を真似て、public スキーマの全権限を事前に与えたうえで実施した）。

限界：URL を知っていれば誰でも送信でき、偽の回答やスパムも送れる。授業用のパイロットであり、本人確認の仕組みではない。
