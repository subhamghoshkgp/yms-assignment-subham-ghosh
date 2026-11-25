#!/usr/bin/env python3
"""Build the assignment data from the Nifty-50 VIX files and the all-underlyings OHLC files.

Truth (in evaluator/data, from the OHLC files):  moved = max(high - pclose, pclose - low) / pclose > 2%
  i.e. the stock trades outside (pclose*0.98, pclose*1.02) at some point during day D.

Info file for day D ("as of D's 09:15 open", no look-ahead):
  pclose, phi, plo, pvolume, mddv_20      from D's VIX file (all known before the open)
  vix, vix_1m..vix_1y, vix_zscore_*       from the PREVIOUS VIX date (vix_asof): D's own VIX file
                                          averages D's intraday VIX, which is not known at the open
Dates: every VIX date that has a previous VIX date and a full-day high/low for its truth.
Split: 30% of the dates drawn at random as test (fixed seed), every other date is train.
  (--split chrono gives the first 70% train / last 30% test instead.)
data/historical_info (practice files): a train date whose previous date is a test date has
pclose/phi/plo and the VIX columns blanked, because they are that test day's close/high/low/session VIX.
evaluator/data/info_all.csv keeps the real values: the grader only ever shows days before the one
being predicted.

  evaluator/build_dataset.py [--vix DIR ...] [--ohlc DIR] [--out KIT] [--split random|chrono] [--seed N]
"""
import argparse
import csv
import glob
import math
import os
import random
import shutil

HOME = os.path.expanduser('~')
P = argparse.ArgumentParser()
P.add_argument('--vix', nargs='+', default=[HOME + '/projects/vix_daily/data/n50_pre0904',
                                            HOME + '/projects/vix_daily/data/n50_post0904'])
P.add_argument('--ohlc', default=HOME + '/projects/vix_daily/data/ohlc_all_2026mar_oct/daily')
P.add_argument('--out', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P.add_argument('--threshold', type=float, default=0.02)
P.add_argument('--train-frac', type=float, default=0.70)
P.add_argument('--split', choices=['random', 'chrono'], default='random')
P.add_argument('--seed', type=int, default=20261122)
A = P.parse_args()

PREOPEN = ['pclose', 'phi', 'plo', 'pvolume', 'mddv_20']
VIXCOLS = ['vix', 'vix_1m', 'vix_3m', 'vix_6m', 'vix_1y', 'vix_zscore_smooth', 'vix_zscore_raw']
INFO_COLS = ['date', 'name'] + PREOPEN + ['vix_asof'] + VIXCOLS


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def read(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


vix = {}
for d in A.vix:
    for p in sorted(glob.glob(os.path.join(d, '*.vix_n50.csv'))):
        vix[os.path.basename(p)[:8]] = {r['name']: r for r in read(p)}
vdates = sorted(vix)

usable, labels, info, dropped = [], [], {}, {}
for i, d in enumerate(vdates):
    if i == 0:
        dropped[d] = 'no previous VIX date for the open-time VIX columns'
        continue
    asof = vdates[i - 1]
    op = os.path.join(A.ohlc, d + '.ohlc_all.csv')
    if not os.path.exists(op):
        dropped[d] = 'no OHLC file'
        continue
    ohlc = {r['name']: r for r in read(op)}
    rows, labs, missing = [], [], 0
    for name in sorted(vix[d]):
        v, pv, o = vix[d][name], vix[asof].get(name, {}), ohlc.get(name)
        hi, lo, pc = (num(o['high']), num(o['low']), num(o['pclose'])) if o else (None, None, None)
        if hi is None or lo is None or not pc:
            missing += 1
            continue
        if num(v['pclose']) is not None and abs(num(v['pclose']) - pc) > 0.005:
            raise SystemExit('%s %s: VIX pclose %s != OHLC pclose %s' % (d, name, v['pclose'], pc))
        move = max(hi - pc, pc - lo) / pc
        labs.append(dict(date=d, name=name, moved=move > A.threshold, max_move_pct=round(100 * move, 4),
                         up_move_pct=round(100 * (hi - pc) / pc, 4), down_move_pct=round(100 * (pc - lo) / pc, 4)))
        row = dict(date=d, name=name, vix_asof=asof)
        row.update({c: v.get(c, '') for c in PREOPEN})
        row.update({c: pv.get(c, '') for c in VIXCOLS})
        rows.append(row)
    if missing == len(vix[d]):
        dropped[d] = 'no full-day high/low for the truth (capture ended early)'
        continue
    if missing:
        print('WARN %s: %d names without truth, left out' % (d, missing))
    usable.append(d)
    labels += labs
    info[d] = rows

n_train = int(round(len(usable) * A.train_frac))
if A.split == 'chrono':
    train, test = usable[:n_train], usable[n_train:]
else:
    test = sorted(random.Random(A.seed).sample(usable, len(usable) - n_train))
    train = [d for d in usable if d not in set(test)]
test_set = set(test)
prev_vix = {d: vdates[vdates.index(d) - 1] for d in usable}
masked = [d for d in train if prev_vix[d] in test_set]   # their pclose/phi/plo/VIX come from a test day
MASK = ['pclose', 'phi', 'plo'] + VIXCOLS

kit = A.out
ev = os.path.join(kit, 'evaluator')
for sub in (os.path.join(ev, 'data'), os.path.join(kit, 'data')):
    shutil.rmtree(sub, ignore_errors=True)
os.makedirs(os.path.join(ev, 'data'))
os.makedirs(os.path.join(kit, 'data', 'historical_info'))


def write(path, cols, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# evaluator keeps every date in one file (run_evaluation.py writes the per-date files it shows);
# candidates get one file per train date
write(os.path.join(ev, 'data', 'info_all.csv'), INFO_COLS, [r for d in usable for r in info[d]])
for d in usable:
    if d in train:
        rows = info[d]
        if d in masked:
            rows = [dict(r, **{c: '' for c in MASK}, vix_asof='') for r in rows]
        write(os.path.join(kit, 'data', 'historical_info', d + '_n50.info.csv'), INFO_COLS, rows)
lab_cols = ['date', 'name', 'moved', 'max_move_pct', 'up_move_pct', 'down_move_pct']
write(os.path.join(ev, 'data', 'labels_all.csv'), lab_cols, labels)
write(os.path.join(ev, 'data', 'test_labels.csv'), ['date', 'name', 'moved'],
      [{k: r[k] for k in ('date', 'name', 'moved')} for r in labels if r['date'] in test])
write(os.path.join(kit, 'data', 'train_labels.csv'), lab_cols, [r for r in labels if r['date'] in train])
for path, ds in ((os.path.join(ev, 'data', 'train_dates.txt'), train), (os.path.join(ev, 'data', 'test_dates.txt'), test),
                 (os.path.join(kit, 'data', 'all_dates.txt'), usable),
                 (os.path.join(kit, 'data', 'n50_names.txt'), sorted({r['name'] for r in labels}))):
    open(path, 'w').write('\n'.join(ds) + '\n')
with open(os.path.join(ev, 'data', 'dropped_dates.txt'), 'w') as f:
    for d, why in sorted(dropped.items()):
        f.write('%s %s\n' % (d, why))

rate = lambda ds: (sum(r['moved'] for r in labels if r['date'] in ds), sum(1 for r in labels if r['date'] in ds))
for tag, ds in (('train', set(train)), ('test', set(test))):
    k, n = rate(ds)
    print('%-5s %3d dates %s..%s  rows %5d  moved>2%%: %5d (%.1f%%)' % (tag, len(ds), min(ds), max(ds), n, k, 100.0 * k / n))
print('split %s (seed %d): train %d, test %d; %d train files blanked in the candidate copy (day before is a test day)'
      % (A.split, A.seed, len(train), len(test), len(masked)))
open(os.path.join(ev, 'data', 'masked_train_dates.txt'), 'w').write('\n'.join(masked) + '\n')
print('dropped', len(dropped), dict(sorted(dropped.items())))
