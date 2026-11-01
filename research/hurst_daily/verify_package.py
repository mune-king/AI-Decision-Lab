"""Package self-check (synthetic data only). Run: python verify_package.py

1. Synthetic demo reruns and the injected +0.13 log return is rank 1 and a check candidate.
2. Numbers equal the v0.3 baseline (commit 2700358, same synthetic input, same conditions).
3. Invalid inputs stop with a Japanese cause + fix message and save no results.
4. RESULT_SUMMARY_JA.txt matches results.csv / largest_moves_top5.csv / audit.json.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
# v0.3 (commit 2700358) synthetic demo output, recorded before any v0.4 change.
BASELINE = {'input_sha256': 'd405f7130eaad63a25d6e7b1f8b64d33a72cca5cffb17ffd257fb47e60223aec',
            'H_RS': 0.5756425738069423, 'H_RS_R2': 0.9704282097913034,
            'alpha_DFA1': 0.6561148341594414, 'alpha_DFA1_R2': 0.8191333322426698,
            'returns_used': 219, 'min_scale': 16, 'max_scale': 54, 'top1_date': '2026-05-25',
            'candidates': 1}
failures = []


def check(ok, label):
    print(('OK   ' if ok else 'FAIL ') + label)
    if not ok:
        failures.append(label)


def run_cli(*args):
    return subprocess.run([sys.executable, str(BASE/'run_student.py'), *args],
                          capture_output=True, text=True, cwd=BASE)


def newest_result(before):
    after = set((BASE/'results').glob('*')) if (BASE/'results').exists() else set()
    new = sorted(after - before)
    return new[-1] if new else None


def existing():
    return set((BASE/'results').glob('*')) if (BASE/'results').exists() else set()


# 1 + 2: demo and baseline comparison
before = existing()
proc = run_cli('--demo')
check(proc.returncode == 0, 'demo exits normally')
check('Warning' not in proc.stderr, 'demo prints no Python warnings (stderr clean)')
out = newest_result(before)
res = pd.read_csv(out/'results.csv').set_index('method')
audit = json.loads((out/'audit.json').read_text(encoding='utf-8'))
top = pd.read_csv(out/'largest_moves_top5.csv')
cand = pd.read_csv(out/'outlier_candidates.csv')
if audit['input_sha256'] == BASELINE['input_sha256']:
    check(True, 'synthetic input identical to v0.3 (SHA256)')
else:
    # Different numpy/pandas builds can round the last printed digit of the generated closes
    # differently (relative ~1e-15). This is an environment difference, not a method change:
    # compare the values, keep audit.json as written, and say so in the output.
    demo = pd.read_csv(BASE/'SYNTHETIC_DEMO_NOT_MARKET.csv')
    rng = np.random.default_rng(20261029)
    r = rng.normal(0, .01, 219); r[100] = .13
    ref = 100*np.exp(np.r_[0, np.cumsum(r)])
    rel = float(np.max(np.abs(demo['close'].to_numpy()/ref-1)))
    check(len(demo) == 220 and str(demo['datetime'].iloc[0]) == '2026-01-02 15:30:00+09:00' and rel < 1e-12,
          f'synthetic input matches v0.3 values (SHA256 differs by environment rounding; max relative diff {rel:.1e})')
    print('     NOTE: SHA256 differs from v0.3 only through last-digit rounding in this environment; '
          'audit.json is left unchanged.')
for key, method, col in [('H_RS', 'R/S', 'exponent'), ('H_RS_R2', 'R/S', 'loglog_R2'),
                         ('alpha_DFA1', 'DFA1', 'exponent'), ('alpha_DFA1_R2', 'DFA1', 'loglog_R2')]:
    check(abs(res.loc[method, col]-BASELINE[key]) < 1e-12, f'{key} equals v0.3 baseline {BASELINE[key]:.6f}')
check(int(res.loc['R/S', 'returns_used']) == BASELINE['returns_used'], 'returns_used = 219')
check((int(res.loc['R/S', 'min_scale']), int(res.loc['R/S', 'max_scale'])) == (16, 54), 'scale range 16-54')
check(str(top.iloc[0]['timestamp_jst'])[:10] == BASELINE['top1_date'] and abs(top.iloc[0]['log_return']-0.13) < 1e-9
      and bool(top.iloc[0]['check_candidate_abs_z_gt_3p5']), 'injected +0.13 is rank 1 and a check candidate')
check(len(cand) == BASELINE['candidates'], 'exactly 1 check candidate')

# 4: summary agrees with CSV
summary = (out/'RESULT_SUMMARY_JA.txt').read_text(encoding='utf-8')
check(f"{res.loc['R/S', 'exponent']:.4f}" in summary and f"{res.loc['DFA1', 'exponent']:.4f}" in summary,
      'summary H_RS / alpha_DFA1 match results.csv')
check(audit['input_sha256'] in summary, 'summary input SHA256 matches audit.json')
check(all(str(d)[:10] in summary for d in top['timestamp_jst']), 'summary lists the same top-5 dates')
check('合成デモ' in summary, 'summary labels synthetic demo')
check(f"{top.iloc[0]['log_return']:+.4f}" in summary and '約+13.9%' in summary,
      'summary shows log return 0.13 and simple change ~13.9% (not "+13%")')

# 5: Excel "CSV UTF-8" (BOM) input and --info give the same numbers and copy the filled info
with tempfile.TemporaryDirectory() as tmp:
    bom = Path(tmp)/'excel_utf8.csv'
    bom.write_text(pd.read_csv(BASE/'SYNTHETIC_DEMO_NOT_MARKET.csv').to_csv(index=False), encoding='utf-8-sig')
    info = Path(tmp)/'my_info.txt'
    info.write_text((BASE/'INPUT_INFO_TEMPLATE.txt').read_text(encoding='utf-8')
                    .replace('取得元URL：', '取得元URL：https://example.invalid/synthetic'), encoding='utf-8')
    before = existing()
    proc = run_cli(str(bom), '--info', str(info))
    got = newest_result(before)
    ok = proc.returncode == 0 and got is not None
    if ok:
        r2 = pd.read_csv(got/'results.csv').set_index('method')
        s2 = (got/'RESULT_SUMMARY_JA.txt').read_text(encoding='utf-8')
        ok = (abs(r2.loc['R/S', 'exponent']-BASELINE['H_RS']) < 1e-12
              and abs(r2.loc['DFA1', 'exponent']-BASELINE['alpha_DFA1']) < 1e-12
              and (got/'INPUT_INFO.txt').is_file() and 'https://example.invalid/synthetic' in s2)
    check(ok, 'Excel CSV UTF-8 (BOM) + --info: same exponents, INPUT_INFO.txt copied, info in summary')

# 3: invalid inputs -> Japanese message, no result folder
good = pd.read_csv(BASE/'SYNTHETIC_DEMO_NOT_MARKET.csv')
cases = {
    'missing file': None,
    'wrong column name': good.rename(columns={'close': 'Close'}),
    'too few rows': good.head(10),
    'duplicate timestamp': pd.concat([good.iloc[:30], good.iloc[[29]], good.iloc[30:]]),
    'unsorted': good.iloc[::-1],
    'non-numeric close': good.assign(close=good['close'].astype(str).where(good.index != 5, '1,234')),
    'non-positive close': good.assign(close=good['close'].where(good.index != 7, 0.0)),
    'intraday (4h-like) rows': pd.DataFrame({'datetime': pd.date_range('2026-01-05', periods=240, freq='4h',
                                                                       tz='Asia/Tokyo').astype(str),
                                             'close': 100+np.arange(240)*0.1}),
    'bad datetime text': good.assign(datetime=good['datetime'].where(good.index != 3, 'abc')),
    'too short for scales': good.head(40),
}
with tempfile.TemporaryDirectory() as tmp:
    for name, frame in cases.items():
        path = Path(tmp)/f'{name.replace(" ", "_")}.csv'
        if frame is not None:
            frame.to_csv(path, index=False)
        before = existing()
        proc = run_cli(str(path))
        message = proc.stderr + proc.stdout
        check(proc.returncode != 0 and '直し方' in message and newest_result(before) is None,
              f'invalid input "{name}" -> Japanese fix message, nothing saved')
        if name == 'too short for scales':
            check('データが不足' in message and '取得期間' in message and '取得漏れ' in message
                  and '報告' in message and 'を小さく' not in message,
                  'shortage message asks to check period / missing data / point count, not to shrink scales')

print()
print('ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED: {failures}')
sys.exit(1 if failures else 0)
