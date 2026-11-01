"""Write RESULT_SUMMARY_JA.txt from the files already saved in one results folder.

The summary reads results.csv, scales.csv, largest_moves_top5.csv,
outlier_candidates.csv, diagnostics_method.json and audit.json, so every
number in it is copied from those files (no separate calculation).
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

CODE_VERSION = 'v0.4.2（2026-11-01、学生用3ステップ整備版）'
INFO_KEYS = ['取得元URL', '銘柄', '種別（現物指数／先物／CFD）', '先物の限月つなぎ・価格調整', '足',
             '期間', '本数', 'タイムゾーン', '日時の意味（取引日／足の開始／足の終了）', '終値の定義',
             '取得日時', '最終行が確定足か', '未確認点']
UNFILLED = '（未記入）'


def code_revision(base):
    """Git commit of this folder if available (ZIP copies have none)."""
    try:
        out = subprocess.run(['git', '-C', str(base), 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            dirty = subprocess.run(['git', '-C', str(base), 'status', '--porcelain', '--', '.'],
                                   capture_output=True, text=True, timeout=5).stdout
            return out.stdout.strip() + ('（未コミットの変更あり）' if dirty.strip() else '')
    except (OSError, subprocess.SubprocessError):
        pass
    return '不明（gitなしで実行）'


def read_info(path):
    """Parse 'key: value' / 'key：value' lines of INPUT_INFO_TEMPLATE.txt."""
    info = {}
    if path is None:
        return info
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        for sep in ('：', ':'):
            if sep in line:
                key, value = line.split(sep, 1)
                info[key.strip()] = value.strip()
                break
    return info


def fmt(v, digits=4):
    return f'{v:.{digits}f}' if isinstance(v, float) else str(v)


def write_summary(output, base, info_path=None, demo=False):
    output = Path(output)
    results = pd.read_csv(output/'results.csv')
    scales = pd.read_csv(output/'scales.csv')
    top = pd.read_csv(output/'largest_moves_top5.csv')
    cand = pd.read_csv(output/'outlier_candidates.csv')
    method = json.loads((output/'diagnostics_method.json').read_text())
    audit = json.loads((output/'audit.json').read_text(encoding='utf-8'))
    info = read_info(info_path)
    rs = results.loc[results['method'] == 'R/S'].iloc[0]
    dfa = results.loc[results['method'] == 'DFA1'].iloc[0]

    L = []
    add = L.append
    add('日足 R/S・DFA1 解析 結果概要（自動生成）')
    add('=' * 44)
    if demo:
        add('【注意】合成デモ（乱数で作った数値）です。市場の観測結果ではありません。')
    add('この概要は同じフォルダのCSV・JSONから値を写したものです。数値は元ファイルでも確認してください。')
    add('')
    add('■ 1. 入力データ')
    add(f'入力ファイル：{audit["input_filename"]}')
    add(f'入力SHA256：{audit["input_sha256"]}')
    add(f'元データの期間（JST）：{audit["source_first_timestamp_jst"]} ～ {audit["source_last_timestamp_jst"]}')
    add(f'元データの行数：{audit["source_rows"]}（うち2026年：{audit["source_rows_2026"]}）')
    add(f'解析に使った価格：{audit["price_rows_used"]}本、収益率：{audit["returns_used"]}点')
    add(f'最終行の除外（--drop-last）：{"あり" if audit["drop_last"] else "なし"}')
    add('入力情報（INPUT_INFO の記入内容）：' + ('' if info else '未提出。--info で記入済みひな型を渡してください。'))
    for key in INFO_KEYS:
        value = info.get(key, '') or UNFILLED
        add(f'  {key}：{value}')
    add('')
    add('■ 2. 主要な数値（results.csv）')
    add(f'H_RS（R/S行のexponent）　　　：{fmt(rs["exponent"])}　loglog_R2={fmt(rs["loglog_R2"])}')
    add(f'alpha_DFA1（DFA1行のexponent）：{fmt(dfa["exponent"])}　loglog_R2={fmt(dfa["loglog_R2"])}')
    add(f'収益率の点数 returns_used：{int(rs["returns_used"])}')
    add(f'尺度範囲 min_scale～max_scale：R/S {int(rs["min_scale"])}～{int(rs["max_scale"])}点、'
        f'DFA1 {int(dfa["min_scale"])}～{int(dfa["max_scale"])}点（使用尺度 {int(rs["scales_used"])}個／{int(dfa["scales_used"])}個）')
    add('loglog_R2は直線への当てはまりで、有意性や予測の正しさを示す数値ではありません。')
    add('')
    add('■ 3. 尺度ごとの窓数（scales.csv）')
    add('尺度(点)  R/S窓数  DFA窓数')
    for _, row in scales.iterrows():
        add(f'{int(row["scale_observations"]):>7}  {int(row["rs_windows"]):>7}  {int(row["dfa_windows"]):>7}')
    add('窓が4個未満の尺度は傾きの計算に使っていません。窓が少ない大きな尺度ほど値はばらつきます。')
    add('')
    add('■ 4. 変動の大きい上位5日（largest_moves_top5.csv）')
    for _, row in top.iterrows():
        z = '算出不可' if pd.isna(row['modified_z']) else fmt(float(row['modified_z']), 2)
        flag = '確認候補' if bool(row['check_candidate_abs_z_gt_3p5']) else '－'
        add(f'{int(row["absolute_return_rank"])}位 {str(row["timestamp_jst"])[:10]}  '
            f'対数収益率 {float(row["log_return"]):+.4f}（単純騰落率 約{100*np.expm1(float(row["log_return"])):+.1f}%）'
            f'  modified_z={z}  {flag}')
    add('※CSVの return_percent は対数収益率×100の値で、単純騰落率（%）ではありません。')
    add(f'外れ値の確認候補（|modified_z|>{method["threshold"]}）：{len(cand)}件（outlier_candidates.csv）')
    if not method['MAD'] > 0:
        add('MADが0のためmodified_zは算出できません。上位5日の確認だけを使ってください。')
    add('候補は削除指示ではありません。原資料で、実際の大変動・限月交代・欠測・取得ミスを確認してください。')
    add('')
    add('■ 5. 図の保存先')
    for name, what in [('prices_returns.png', '上段：終値、下段：対数収益率'),
                       ('scaling.png', '尺度と変動量の両対数図（左R/S、右DFA1）'),
                       ('return_diagnostics.png', '収益率と確認候補（赤点）、上位5日の日付')]:
        add(f'{output/name}　…{what}')
    add('')
    add('■ 6. 実行条件とコードの版')
    add(f'コードの版：{CODE_VERSION}、git：{code_revision(base)}')
    add(f'Python {audit["python"]}, numpy {audit["numpy"]}, pandas {audit["pandas"]}, matplotlib {audit["matplotlib"]}')
    add(f'尺度：{audit["scales"]}')
    add('窓：前から重ならない窓、余りは捨てる。回帰：自然対数での重みなし最小二乗。')
    add('')
    add('■ 7. 未確認点（学生が埋める・報告する）')
    add('・日時が取引日か足の開始／終了時刻か：' + (info.get('日時の意味（取引日／足の開始／足の終了）') or 'CSVからは確定できません'))
    add('・取引所の休日カレンダーとの照合：未実施（収益率は隣り合う観測日の終値から計算）')
    add('・先物の限月つなぎ・価格調整：' + (info.get('先物の限月つなぎ・価格調整') or 'CSVからは確定できません'))
    add('・最終行が確定足か：' + (info.get('最終行が確定足か') or '未確認'))
    add('・上位5日・確認候補の原因：原資料で照合して報告してください')
    if info.get('未確認点'):
        add('・記入された未確認点：' + info['未確認点'])
    add('')
    add('■ 読み方の注意')
    add('・H_RSとalpha_DFA1は別々に報告します。DFA1のalphaを自動的にHとは見なしません。')
    add('・0.5との大小やloglog_R2の高さだけで、持続性・予測力・統計的有意性を主張しません。')
    add('・約200点の日足では尺度の上限が約50点です。長期記憶の証明や「毎日のH」には使えません。')
    add('・全期間で一つの指数と、日別の心理スコアとの相関は計算しません。')
    text = '\n'.join(L) + '\n'
    (output/'RESULT_SUMMARY_JA.txt').write_text(text, encoding='utf-8')
    return text
