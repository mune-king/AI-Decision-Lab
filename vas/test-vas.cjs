// VAS ページの結合テスト（実ブラウザ Chromium + ローカル PostgreSQL）。
// Supabase の RPC 呼び出しを横取りし、ローカル DB の public.vdt_vas_submit を anon 権限で実行する。
// 使い方: PGURL='postgres://postgres@/db?host=/sock&port=55432' node vas/test-vas.cjs
'use strict';
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const path = require('path');
const assert = require('assert');

const PGURL = process.env.PGURL;
if (!PGURL) { console.error('PGURL を指定してください'); process.exit(2); }
const sql = q => execFileSync('psql', [PGURL, '-XtAq', '-v', 'ON_ERROR_STOP=1', '-c', q], { encoding: 'utf8' }).trim();
const lit = v => v == null ? 'null' : "'" + String(v).replace(/'/g, "''") + "'";
const FILE = 'file://' + path.resolve(__dirname, 'index.html');

(async () => {
  sql("delete from public.vdt_vas_responses where research_id like 'TESTPW%'");
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  let mode = 'ok'; // ok | offline | lost-response
  let calls = 0;
  await page.route('**/rest/v1/rpc/vdt_vas_submit', async route => {
    calls++;
    if (mode === 'offline') return route.abort('internetdisconnected');
    const b = JSON.parse(route.request().postData());
    const h = route.request().headers();
    assert.ok(h.apikey && h.apikey.startsWith('sb_publishable_'), 'publishable key only');
    let status = 200, body;
    try {
      body = sql(`set role anon; select public.vdt_vas_submit(${lit(b.p_id)}::uuid, ${lit(b.p_research_id)}, ${lit(b.p_phase)}, ${b.p_eye}, ${b.p_neck}, ${b.p_back}, ${b.p_fatigue}, ${b.p_focus}, ${lit(b.p_research_consent)})`);
    } catch (e) { status = 400; body = JSON.stringify({ message: String(e.stderr || e).split('\n')[0] }); }
    if (mode === 'lost-response') return route.abort('connectionreset'); // サーバーには保存済みだが応答が届かない
    return route.fulfill({ status, contentType: 'application/json', body });
  });
  const status = () => page.textContent('#status');
  const fill = async (rid, phase, vals, consent) => {
    await page.fill('#rid', rid);
    await page.selectOption('#phase', phase);
    const ids = ['eye', 'neck', 'back', 'fatigue', 'focus'];
    for (let i = 0; i < ids.length; i++) if (vals[i] != null) await page.fill('#' + ids[i], String(vals[i]));
    if (consent) await page.check(`input[name=consent][value=${consent}]`);
  };

  // A. スライダー未操作・同意未選択では送信しない
  await page.goto(FILE);
  await page.fill('#rid', 'TESTPW1');
  assert.ok(await page.isVisible('#testNote'), 'TEST注記が出る');
  await page.selectOption('#phase', 'before');
  await page.click('#send');
  assert.match(await status(), /まだ動かしていない項目/);
  await fill('TESTPW1', 'before', [10, 20, 30, 0, 50], null);
  await page.click('#send');
  assert.match(await status(), /同意/);
  assert.strictEqual(calls, 0, 'invalid input must not be sent');

  // B. 正常送信 → 受付番号
  await page.check('input[name=consent][value=agree]');
  await page.click('#send');
  await page.waitForSelector('#done:not(.hidden)');
  const r1 = await page.textContent('#receipt');
  assert.match(r1, /^[0-9A-F]{8}$/);
  assert.strictEqual(sql("select count(*) from public.vdt_vas_responses where research_id='TESTPW1' and phase='before' and fatigue=0 and research_consent='agree' and is_test"), '1');
  assert.strictEqual(sql(`select upper(left(id::text,8)) from public.vdt_vas_responses where research_id='TESTPW1' and phase='before'`), r1, 'receipt matches DB');

  // C. 「次の測定時点」→ ID と T1 が引き継がれる。通信断 → 未確認保持 → 再読込でも残る → 再送で1行
  await page.click('#next');
  await page.waitForLoadState();
  assert.strictEqual(await page.inputValue('#rid'), 'TESTPW1');
  assert.strictEqual(await page.inputValue('#phase'), 'after');
  assert.strictEqual(page.url(), FILE, 'research ID is not put in the URL');
  await fill('TESTPW1', 'after', [60, 70, 80, 90, 100], 'disagree');
  mode = 'offline';
  await page.click('#send');
  await page.waitForFunction(() => /保存を確認できませんでした/.test(document.getElementById('status').textContent));
  assert.ok(await page.isDisabled('#eye'), 'pending answer is locked');
  await page.reload();
  assert.match(await status(), /残っています/);
  assert.strictEqual(await page.inputValue('#eye'), '60');
  mode = 'ok';
  await page.click('#send');
  await page.waitForSelector('#done:not(.hidden)');
  assert.strictEqual(sql("select count(*) from public.vdt_vas_responses where research_id='TESTPW1' and phase='after'"), '1');

  // D. サーバー保存済みで応答だけ失われた → 再送は already_saved、行は1つのまま
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await page.goto(FILE);
  await fill('TESTPW2', 'before', [5, 5, 5, 5, 5], 'agree');
  mode = 'lost-response';
  await page.click('#send');
  await page.waitForFunction(() => /保存を確認できませんでした/.test(document.getElementById('status').textContent));
  assert.strictEqual(sql("select count(*) from public.vdt_vas_responses where research_id='TESTPW2'"), '1');
  mode = 'ok';
  await page.click('#send');
  await page.waitForSelector('#done:not(.hidden)');
  assert.match(await page.textContent('#doneInfo'), /すでに届いていました/);
  assert.strictEqual(sql("select count(*) from public.vdt_vas_responses where research_id='TESTPW2'"), '1');

  // E. 同じブラウザで同じID・同じ時点を再度送ろうとすると確認が出る（キャンセルで送らない）
  await page.goto(FILE);
  await fill('TESTPW2', 'before', [1, 1, 1, 1, 1], 'agree');
  let dialog = '';
  page.once('dialog', d => { dialog = d.message(); d.dismiss(); });
  const before = calls;
  await page.click('#send');
  assert.match(dialog, /送信済み/);
  assert.strictEqual(calls, before, 'cancelled resubmission is not sent');

  await browser.close();
  sql("delete from public.vdt_vas_responses where research_id like 'TESTPW%'");
  console.log('ALL VAS PAGE TESTS PASSED');
})().catch(e => { console.error(e); process.exit(1); });
