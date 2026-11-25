#!/usr/bin/env python3
"""Build user_historical_info.csv: any extra per-(date, name) data you want predict.py to use.

  python prepare_user_historical_info.py --dates data/all_dates.txt --names data/n50_names.txt \
                                         --out user_historical_info.csv

Required format: a CSV with columns `date` (YYYYMMDD) and `name` (NSE symbol, as in the info files),
followed by any feature columns you like. Cover every date in data/all_dates.txt (train AND test):
the evaluator passes this file to predict.py and only removes rows dated after the day being predicted.

RULE: a row dated D may only contain information that was public before 09:15 on day D (for example
the previous day's close, overnight global indices, news timestamped before the open). Anything from
day D's session or later is look-ahead and disqualifies the submission.

This file is a TEMPLATE. It writes the required date/name skeleton plus one example column
(day of week); replace or extend it with your own sources (market data APIs, index levels, etc.).
"""
import argparse
import csv
import datetime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dates', default='data/all_dates.txt')
    ap.add_argument('--names', default='data/n50_names.txt')
    ap.add_argument('--out', default='user_historical_info.csv')
    a = ap.parse_args()
    dates = open(a.dates).read().split()
    names = open(a.names).read().split()

    with open(a.out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['date', 'name', 'weekday'])
        for d in dates:
            weekday = datetime.datetime.strptime(d, '%Y%m%d').weekday()   # example feature, known in advance
            for n in names:
                w.writerow([d, n, weekday])
    print('wrote %s: %d dates x %d names' % (a.out, len(dates), len(names)))


if __name__ == '__main__':
    main()
