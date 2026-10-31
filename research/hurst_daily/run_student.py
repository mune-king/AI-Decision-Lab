"""Daily-only student runner. No real market data are included."""
import argparse
from datetime import datetime
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import shutil
import sys
from analyze_daily import run
from summary_ja import write_summary

def diagnostics(output):
    df = pd.read_csv(output/'prices_returns.csv')
    df = df.iloc[1:].copy()
    r = df['log_return'].to_numpy()
    median = float(np.median(r))
    mad = float(np.median(np.abs(r-median)))
    score = 0.67448975*(r-median)/mad if mad > 0 else np.full(len(r), np.nan)
    df['return_percent'] = 100*r
    df['modified_z'] = score
    df['check_candidate_abs_z_gt_3p5'] = np.abs(score) > 3.5
    df['absolute_return_rank'] = df['log_return'].abs().rank(method='first',ascending=False).astype(int)
    df.to_csv(output/'return_diagnostics.csv',index=False)
    candidates = df.loc[df['check_candidate_abs_z_gt_3p5']].copy()
    candidates.to_csv(output/'outlier_candidates.csv',index=False)
    top = df.sort_values('absolute_return_rank').head(5)
    top.to_csv(output/'largest_moves_top5.csv',index=False)
    dates = pd.to_datetime(df['timestamp_jst'],utc=True).dt.tz_convert('Asia/Tokyo')
    fig, ax = plt.subplots(figsize=(10,4.5))
    ax.plot(dates,df['return_percent'],lw=.8,label='Daily log return (%)')
    marked = df['check_candidate_abs_z_gt_3p5']
    ax.scatter(dates[marked],df.loc[marked,'return_percent'],c='red',label='Check candidate: |modified z| > 3.5')
    for i,row in top.iterrows():
        ax.annotate(str(row['timestamp_jst'])[:10],(dates.loc[i],row['return_percent']),fontsize=7,xytext=(3,5),textcoords='offset points')
    ax.set(xlabel='Source bar timestamp (JST)',ylabel='Log return (%)',title='Large moves for source checking; observations retained')
    ax.legend(fontsize=8); ax.grid(alpha=.2); fig.tight_layout()
    fig.savefig(output/'return_diagnostics.png',dpi=150);plt.close(fig)
    (output/'diagnostics_method.json').write_text(json.dumps({'median':median,'MAD':mad,'modified_z':'0.67448975*(return-median)/MAD','threshold':3.5,'MAD_zero':'scores unavailable; top5 remains usable','interpretation':'Exploratory check candidates, not errors. No observations deleted.'},indent=2))

def main():
    parser = argparse.ArgumentParser(description='日足CSVのR/S・DFA1解析（学生用）')
    parser.add_argument('csv',nargs='?',help='日足CSV（列：datetime,close または time,close）')
    parser.add_argument('--demo',action='store_true',help='合成データで起動練習をする（市場データではない）')
    parser.add_argument('--drop-last',action='store_true',help='最終行が未確定と確認できた場合だけ付ける')
    parser.add_argument('--info',help='記入済みの INPUT_INFO_TEMPLATE.txt のコピー')
    args = parser.parse_args()
    if bool(args.csv) == bool(args.demo):
        parser.error('CSVファイル名か --demo のどちらか一方を指定してください。')
    base = Path(__file__).resolve().parent
    if args.info and not Path(args.info).is_file():
        parser.exit(2, f'エラー：入力情報ファイルが見つかりません：{args.info}\n'
                       '  直し方：INPUT_INFO_TEMPLATE.txt をコピーして記入し、そのファイル名を --info に指定してください。\n')
    if args.demo:
        sample = base/'SYNTHETIC_DEMO_NOT_MARKET.csv'
        rng = np.random.default_rng(20261029)
        returns = rng.normal(0,.01,219)
        returns[100] = .13
        prices = 100*np.exp(np.r_[0,np.cumsum(returns)])
        dates = pd.bdate_range('2026-01-02',periods=220,tz='Asia/Tokyo')+pd.Timedelta(hours=15,minutes=30)
        pd.DataFrame({'datetime':dates.astype(str),'close':prices}).to_csv(sample,index=False)
        source = sample
        print('SYNTHETIC DEMO ONLY: generated numbers, not market observations.')
        print('合成デモ：乱数で作った数値です。市場の観測結果ではありません。')
    else:
        source = Path(args.csv).resolve()
    output = base/'results'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    try:
        run(source,output,drop_last=args.drop_last)
    except ValueError as exc:
        sys.exit(f'\n入力エラー：{exc}\n'
                 '結果は保存していません。直せない場合は、このメッセージ全文と試した操作を報告してください。')
    diagnostics(output)
    if args.info:
        shutil.copyfile(args.info, output/'INPUT_INFO.txt')
    write_summary(output, base, info_path=args.info, demo=args.demo)
    print('Saved results:',output)
    print('結果の保存先：',output)
    print('まず RESULT_SUMMARY_JA.txt を開き、results.csv・scaling.png・return_diagnostics.png・'
          'largest_moves_top5.csv で数値を確かめてください。')

if __name__ == '__main__':
    main()
