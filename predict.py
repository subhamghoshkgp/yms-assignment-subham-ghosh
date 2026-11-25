#!/usr/bin/env python3
"""Predict, for one trading day, which Nifty-50 stocks will move more than 2% from the previous close.

Interface (the evaluator calls exactly this, once per date):

  python predict.py --date YYYYMMDD --historical-info DIR --user-historical-info FILE --out-dir DIR

  --historical-info       folder of <YYYYMMDD>_n50.info.csv files. During evaluation it holds only the
                          dates up to and including --date (nothing from the future).
  --user-historical-info  your user_historical_info.csv (rows dated after --date are removed).
  --out-dir               write <out-dir>/<YYYYMMDD>.predictions.csv with columns name,prediction
                          (prediction = True if you expect the stock to move more than 2%), one row
                          for every name in that day's info file.

This file is a WORKING EXAMPLE you are expected to replace with your own model. It predicts a move
when yesterday's range or the volatility level is high. Any language features / libraries are fine
as long as this command line works.
"""
import argparse
import csv
import math
import os


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--historical-info', required=True)
    ap.add_argument('--user-historical-info', default=None)
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()

    with open(os.path.join(a.historical_info, a.date + '_n50.info.csv'), newline='') as f:
        today = list(csv.DictReader(f))

    rows = []
    for r in today:
        pclose, phi, plo, vix = num(r['pclose']), num(r['phi']), num(r['plo']), num(r['vix'])
        prev_range = (phi - plo) / pclose if pclose and phi and plo else None   # yesterday's high-low range
        daily_vol = vix / 100 / math.sqrt(252) if vix else None                 # option-implied daily sd
        move = bool((prev_range is not None and prev_range > 0.03) or (daily_vol is not None and daily_vol > 0.02))
        rows.append(dict(name=r['name'], prediction=move))

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, a.date + '.predictions.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['name', 'prediction'])
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
