#!/usr/bin/env python3
"""Daily CSV: inventory, close-to-close log returns, R/S, DFA1 and saved figures."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class InputError(ValueError):
    """Input problem with a Japanese explanation of cause and fix."""


def _fail(problem, fix):
    raise InputError(f'{problem}\n  直し方：{fix}')


def _rows(index, limit=5):
    """CSV line numbers (header = line 1) for the first offending rows."""
    lines = [str(int(i)+2) for i in list(index)[:limit]]
    more = '' if len(index) <= limit else f' ほか{len(index)-limit}か所'
    return '、'.join(lines) + more


def load_daily(path, drop_last=False):
    path = Path(path)
    if not path.is_file():
        _fail(f'入力ファイルが見つかりません：{path}',
              'ファイル名と保存場所を確認してください。スペースを含む名前は "" で囲みます。')
    try:
        raw = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        _fail(f'入力ファイルが空です：{path.name}', '日足CSVを保存し直してください。')
    except UnicodeDecodeError:
        _fail(f'文字コードを読めません：{path.name}', 'CSVを「CSV UTF-8」形式で保存し直してください。')
    except pd.errors.ParserError as exc:
        _fail(f'CSVとして読めません（列数が行ごとに違う可能性）：{exc}',
              '区切りがカンマ1種類か、説明行や合計行が混ざっていないか確認してください。')
    raw.columns = [str(c).lstrip('\ufeff') for c in raw.columns]
    if 'close' not in raw or not ({'time', 'datetime'} & set(raw)):
        _fail(f'必要な列がありません。見つかった列：{list(raw.columns)}',
              '1行目の列名を datetime,close（ISO8601の日時）または time,close（Unix秒）にしてください。'
              '大文字・空白も区別します（Close や " close" は不可）。')
    if len(raw) < 20:
        _fail(f'行数が{len(raw)}行しかありません（最低20行）。',
              '取得期間が予定どおりか、取得漏れ・欠測・入力形式の問題がないかを確認してください。'
              '解消できなければ、期間・本数とこのエラー全文を報告してください。')
    field = 'time' if 'time' in raw else 'datetime'
    if field == 'time' and pd.api.types.is_numeric_dtype(raw[field]):
        times = pd.DatetimeIndex(pd.to_datetime(raw[field], unit='s', utc=True)).tz_convert('Asia/Tokyo')
    else:
        stamps = []
        for i, s in enumerate(raw[field]):
            try:
                stamps.append(pd.Timestamp(s))
            except (ValueError, TypeError):
                _fail(f'{field}列を日時として読めません（{i+2}行目：{s!r}）。',
                      '2026-01-05T15:30:00+09:00 のようなISO8601形式か、Unix秒の time 列にしてください。'
                      '提供元の日時を保ち、時刻を作って埋めないでください。')
        if len({s.tzinfo is not None for s in stamps}) != 1:
            _fail('タイムゾーン付きの日時と無しの日時が混在しています。',
                  '提供元の仕様を確認し、全行を同じ表記にしてください（推測で+09:00を付けない）。')
        times = (pd.DatetimeIndex(pd.to_datetime(raw[field], utc=True, format='ISO8601')).tz_convert('Asia/Tokyo')
                 if stamps and stamps[0].tzinfo is not None else pd.DatetimeIndex(stamps).tz_localize('Asia/Tokyo'))
    if times.hasnans:
        _fail(f'日時が空欄の行があります（{_rows(np.flatnonzero(times.isna()))}行目）。',
              '元CSVで該当行を確認してください。日時を推測で埋めないでください。')
    if times.has_duplicates:
        _fail(f'同じ日時の行が重複しています（{_rows(np.flatnonzero(times.duplicated()))}行目）。',
              '重複行を元データと照合し、同じ足が二重に保存されていれば一方を外して記録してください。')
    if not times.is_monotonic_increasing:
        bad = np.flatnonzero(np.diff(times.asi8) < 0) + 1
        _fail(f'日時が古い順に並んでいません（{_rows(bad)}行目で逆行）。',
              '解析用コピーを日時の昇順に並べ替えてください（元CSVは保存したまま）。')
    close = pd.to_numeric(raw['close'], errors='coerce').to_numpy(float)
    if not np.isfinite(close).all():
        _fail(f'close列に数値でない値・空欄があります（{_rows(np.flatnonzero(~np.isfinite(close)))}行目）。',
              '桁区切りのカンマ（1,234）や文字を除き、空欄は元データで確認してください。自動補間はしません。')
    if (close <= 0).any():
        _fail(f'close列に0以下の価格があります（{_rows(np.flatnonzero(close <= 0))}行目）。',
              '取得ミスの可能性があります。元データと照合してください。対数収益率は正の価格でのみ計算できます。')
    if times.normalize().has_duplicates:
        _fail(f'同じ日付（日本時間）に複数の行があります（{_rows(np.flatnonzero(times.normalize().duplicated()))}行目）。',
              '日足ではなく4時間足などの可能性があります。現版は日足専用です。日足を取得し直してください。')
    ohlc_bad = None
    if {'open', 'high', 'low'} <= set(raw):
        ohlc = raw[['open', 'high', 'low', 'close']].apply(pd.to_numeric, errors='coerce')
        ohlc_bad = int((~np.isfinite(ohlc).all(axis=1) | (ohlc['low'] > ohlc[['open', 'close']].min(axis=1))
                        | (ohlc['high'] < ohlc[['open', 'close']].max(axis=1)) | (ohlc['low'] > ohlc['high'])).sum())
        if ohlc_bad:
            _fail(f'open/high/low/close の関係が矛盾する行が{ohlc_bad}行あります。',
                  '高値<安値などがないか元データで確認してください。不要なら open,high,low 列を外せます。')
    inventory = {'input_filename': Path(path).name,
                 'input_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                 'instrument': 'User-declared daily input; instrument identity is not validated by this script',
                 'source_first_timestamp_jst': times[0].isoformat(), 'source_last_timestamp_jst': times[-1].isoformat(),
                 'source_rows': len(raw), 'source_columns': list(raw.columns), 'close_missing': 0,
                 'duplicate_timestamps': 0, 'ohlc_invalid_rows': ohlc_bad,
                 'source_rows_2026': int(np.sum(times.year == 2026)), 'drop_last': bool(drop_last),
                 'timestamp_meaning': 'Source bar timestamp only; NOT verified trading-date or close-time labels',
                 'roll_adjustment': 'Not established from CSV',
                 'calendar_check': 'Exchange holiday calendar not verified; returns link adjacent observed daily bars'}
    frame = pd.DataFrame({'timestamp_jst': times.astype(str), 'close': close})
    frame['elapsed_calendar_days'] = pd.Series(times).diff().dt.total_seconds() / 86400
    if drop_last:
        frame = frame.iloc[:-1].copy()
    frame['log_return'] = np.r_[np.nan, np.diff(np.log(frame['close'].to_numpy()))]
    inventory.update({'price_rows_used': len(frame), 'returns_used': len(frame)-1,
                      'analysis_first_timestamp_jst': frame['timestamp_jst'].iloc[0],
                      'analysis_last_timestamp_jst': frame['timestamp_jst'].iloc[-1],
                      'return_first_timestamp_jst': frame['timestamp_jst'].iloc[1]})
    return frame, inventory


def fluctuations(x, scales):
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).all():
        raise ValueError('Nonfinite returns.')
    profile = np.cumsum(x-x.mean())
    rows = []
    for s in scales:
        s = int(s)
        grid = np.arange(s, dtype=float); centered = grid-grid.mean()
        rs, mse = [], []
        for begin in range(0, len(x)-s+1, s):
            block = x[begin:begin+s]
            sd = np.std(block, ddof=1)
            if sd > 0:
                rs.append(np.ptp(np.cumsum(block-block.mean())) / sd)
            block_profile = profile[begin:begin+s]
            slope = np.dot(centered, block_profile-block_profile.mean()) / np.dot(centered, centered)
            residual = block_profile-(block_profile.mean()+slope*centered)
            mse.append(float(np.mean(residual**2)))
        rows.append({'scale_observations': s, 'rs_mean': float(np.mean(rs)) if rs else np.nan,
                     'dfa_F': float(np.sqrt(np.mean(mse))) if mse else np.nan,
                     'rs_windows': len(rs), 'dfa_windows': len(mse)})
    return pd.DataFrame(rows)


SHORTAGE_GUIDE = (
    '  直し方（まず確認すること）：\n'
    '   1. 取得期間が予定どおりか（2026年1月から最新確定日まで取れているか）。\n'
    '   2. 取得漏れ・欠測・入力形式の問題（途中で切れた保存、ページ分割された取得、別の足の混入など）がないか。\n'
    '   3. 期間を見直して、必要な観測点数を確保できるか。\n'
    '  不足を解消できなければ、上の期間・本数とこのエラー全文を報告してください。\n'
    '  計算を通すためだけに尺度（--min-scale / --max-scale）を変えないでください。\n'
    '  解析条件を変える必要があると考える場合は、変更せずにその理由と影響を報告して相談してください。')


class DataShortage(ValueError):
    """Too few observations for the scale analysis."""


def _shortage(audit, n, detail):
    return InputError(
        f'データが不足しているため解析できません：{detail}\n'
        f'  入力期間（JST）：{audit["analysis_first_timestamp_jst"]} ～ {audit["analysis_last_timestamp_jst"]}、'
        f'価格{audit["price_rows_used"]}本・収益率{n}点'
        f'（元ファイル{audit["source_rows"]}行、--drop-last {"あり" if audit["drop_last"] else "なし"}）\n'
        + SHORTAGE_GUIDE)


def fit(table, column, count):
    usable = (table[column] > 0) & np.isfinite(table[column]) & (table[count] >= 4)
    if usable.sum() < 4:
        raise DataShortage('有効な尺度が4つ未満です（各尺度で重ならない窓が4個以上必要）。')
    xx = np.log(table.loc[usable, 'scale_observations'].to_numpy())
    yy = np.log(table.loc[usable, column].to_numpy())
    slope, intercept = np.polyfit(xx, yy, 1)
    total = np.sum((yy-yy.mean())**2)
    r2 = float(1-np.sum((yy-(slope*xx+intercept))**2)/total) if total > 0 else float('nan')
    return float(slope), float(intercept), r2, usable


def run(csv, out, drop_last=False, min_scale=16, max_scale=None, banner=''):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise InputError('出力先フォルダが空ではありません。\n  直し方：新しい --out フォルダを指定してください。')
    frame, audit = load_daily(csv, drop_last)
    x = frame['log_return'].iloc[1:].to_numpy()
    max_scale = len(x)//4 if max_scale is None else max_scale
    if not 4 <= min_scale < max_scale <= len(x)//4:
        if len(x)//4 <= min_scale:
            raise _shortage(audit, len(x), f'最小尺度{min_scale}点で各尺度に窓4個以上を取るには、'
                                           f'収益率が{4*(min_scale+1)}点以上必要です（現在{len(x)}点）。')
        raise InputError(f'指定した尺度範囲が使えません：min={min_scale}, max={max_scale}'
                         f'（4 <= min < max <= 収益率{len(x)}点 // 4 = {len(x)//4} が必要）。\n'
                         '  直し方：通常は --min-scale / --max-scale を指定せず既定値で実行してください。'
                         '条件を変える場合は、理由と影響を記録して報告してください。')
    scales = np.unique(np.round(np.geomspace(min_scale, max_scale, 12)).astype(int))
    table = fluctuations(x, scales)
    results = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, method, column, count, name in zip(axes, ['R/S', 'DFA1'], ['rs_mean', 'dfa_F'],
                                            ['rs_windows', 'dfa_windows'], ['H_RS', 'alpha_DFA1']):
        try:
            exponent, intercept, r2, usable = fit(table, column, count)
        except DataShortage as exc:
            raise _shortage(audit, len(x), str(exc)) from None
        selected = table.loc[usable, 'scale_observations']
        results.append({'method': method, 'exponent_name': name, 'exponent': exponent, 'loglog_R2': r2,
                        'min_scale': int(selected.min()), 'max_scale': int(selected.max()),
                        'scales_used': int(usable.sum()), 'returns_used': len(x), 'drop_last': drop_last,
                        'windowing': 'forward_nonoverlapping; remainder discarded at each scale'})
        ax.loglog(table['scale_observations'], table[column], 'o', color='#086788', label='Data')
        ax.loglog(selected, np.exp(intercept)*selected**exponent, color='#dc6a3b',
                  label=f'{name} = {exponent:.4f}\nR-squared = {r2:.4f}')
        ax.set(title=method, xlabel='Scale (daily return observations)', ylabel='Mean R/S' if method == 'R/S' else 'F(s)')
        ax.legend(); ax.grid(alpha=.2, which='both')
    fig.suptitle(f'{banner}DAILY log returns (input instrument declared by user) | N = {len(x)}\n'
                 f'Forward nonoverlapping windows; source last row {"excluded" if drop_last else "included"}', fontsize=11)
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out/'scaling.png', dpi=170); plt.close(fig)
    times = pd.to_datetime(frame['timestamp_jst'], utc=True).dt.tz_convert('Asia/Tokyo')
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True)
    axes[0].plot(times, frame['close'], color='#086788', linewidth=.9)
    axes[0].set(ylabel='Close (source units)', title='Source daily close; roll adjustment not verified')
    axes[1].plot(times.iloc[1:], 100*x, color='#dc6a3b', linewidth=.7)
    axes[1].set(ylabel='Log return (%)', xlabel='Source bar timestamp date (JST); trading-date mapping unverified')
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle(f'{banner}DAILY INPUT | {len(frame)} price bars / {len(x)} log returns', fontsize=12)
    fig.tight_layout(); fig.savefig(out/'prices_returns.png', dpi=170); plt.close(fig)
    frame.to_csv(out/'prices_returns.csv', index=False)
    table.to_csv(out/'scales.csv', index=False)
    pd.DataFrame(results).to_csv(out/'results.csv', index=False)
    sensitivity = []
    for lo, hi in [(8,64), (16,128), (32,256), (64,505), (16,505)]:
        if hi > len(x)//4: continue
        tt = fluctuations(x, np.unique(np.round(np.geomspace(lo,hi,12)).astype(int)))
        for method, col, count in [('R/S','rs_mean','rs_windows'),('DFA1','dfa_F','dfa_windows')]:
            slope, _, r2, _ = fit(tt, col, count)
            sensitivity.append({'min_scale': lo, 'max_scale': hi, 'method': method, 'exponent': slope, 'loglog_R2': r2})
    pd.DataFrame(sensitivity, columns=['min_scale','max_scale','method','exponent','loglog_R2']).to_csv(out/'scale_sensitivity.csv', index=False)
    audit.update({'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                  'matplotlib': matplotlib.__version__, 'scales': scales.tolist(),
                  'rs': 'Within each block: range(cumsum(x-block_mean)) / sample_sd(ddof=1); mean across blocks',
                  'dfa1': 'Global profile cumsum(x-global_mean); local least-squares line; sqrt(mean(window residual MSE))',
                  'windowing': 'Forward, nonoverlapping windows, discard remainder; minimum 4 windows per scale',
                  'regression': 'Unweighted OLS in natural log coordinates; 12 rounded geometric scales',
                  'interpretation': 'Descriptive exponents only; alpha is not automatically H; no persistence/significance claim'})
    (out/'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'out': str(out), 'audit': audit, 'results': results}, ensure_ascii=False, indent=2))
    return audit, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv'); parser.add_argument('--out', required=True)
    parser.add_argument('--drop-last', action='store_true', help='Explicitly exclude the unverified last source bar')
    parser.add_argument('--min-scale', type=int, default=16)
    parser.add_argument('--max-scale', type=int)
    args = parser.parse_args()
    try:
        run(args.csv, args.out, args.drop_last, args.min_scale, args.max_scale)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'エラー：{exc}\n')


if __name__ == '__main__':
    main()
