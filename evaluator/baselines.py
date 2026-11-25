#!/usr/bin/env python3
"""Reference scores on the test dates, to calibrate the pass bar (standard library only).

  baselines.py

Thresholds of the single-feature rules are tuned on the TRAIN dates (best score), then
scored on TEST. Features come only from each day's open-time info file.
"""
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from test_predictions import load_labels, score  # noqa: E402

DATA = os.path.join(HERE, 'data')
labels = load_labels(os.path.join(DATA, 'labels_all.csv'))
train = set(open(os.path.join(DATA, 'train_dates.txt')).read().split())
test = set(open(os.path.join(DATA, 'test_dates.txt')).read().split())


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


feat = {}
for r in csv.DictReader(open(os.path.join(DATA, 'info_all.csv'))):
    pc, hi, lo, vix = num(r['pclose']), num(r['phi']), num(r['plo']), num(r['vix'])
    feat[(r['date'], r['name'])] = dict(
        prev_range=(hi - lo) / pc if pc and hi and lo else None,
        implied_daily_sd=vix / 100 / math.sqrt(252) if vix else None,
        vix_zscore=num(r['vix_zscore_smooth']))


def subset(ds):
    return {k: v for k, v in labels.items() if k[0] in ds}


def rule(fn):
    return {k: bool(fn(feat.get(k, {}))) for k in labels}


def tuned(name, min_p):
    """Best score on TRAIN among thresholds that keep train precision above min_p."""
    vals = sorted(v[name] for k, v in feat.items() if k[0] in train and v.get(name) is not None)
    grid = [vals[int(q * (len(vals) - 1))] for q in [i / 1000 for i in range(1, 1000)]]
    ok = [t for t in grid if score(subset(train), rule(lambda f: f.get(name) is not None and f[name] > t))['precision'] > min_p]
    best = max(ok, key=lambda t: score(subset(train), rule(lambda f: f.get(name) is not None and f[name] > t))['score'])
    return best, rule(lambda f: f.get(name) is not None and f[name] > best)


def top_share(name, q):
    """Flag only the top q share of rows by a feature (threshold from the train distribution)."""
    vals = sorted(v[name] for k, v in feat.items() if k[0] in train and v.get(name) is not None)
    t = vals[int(len(vals) * (1 - q))]
    return t, rule(lambda f: f.get(name) is not None and f[name] > t)


rows = [('all False', {k: False for k in labels}), ('all True', {k: True for k in labels})]
for q in (0.01, 0.03):
    t, preds = top_share('implied_daily_sd', q)
    rows.append(('only the top %d%% implied_daily_sd (> %.4f)' % (round(100 * q), t), preds))
rows.append(('predict.py template', rule(lambda f: (f.get('prev_range') or 0) > 0.03 or (f.get('implied_daily_sd') or 0) > 0.02)))
for min_p in (0.60, 0.70):
    for name in ('prev_range', 'implied_daily_sd', 'vix_zscore'):
        t, preds = tuned(name, min_p)
        rows.append(('%s > %.4f (train precision > %.2f)' % (name, t, min_p), preds))

tr, te = subset(train), subset(test)
print('base rate  train %.1f%%  test %.1f%%' % (100 * sum(tr.values()) / len(tr), 100 * sum(te.values()) / len(te)))
print('%-56s %9s %8s %7s %6s %9s' % ('rule (scored on TEST)', 'precision', 'recall', 'score', 'pass', 'flagged'))
for name, preds in rows:
    s = score(te, preds)
    flagged = sum(preds[k] for k in te) / len(te)
    print('%-56s %9.3f %8.3f %7.3f %6s %8.1f%%' % (name, s['precision'], s['recall'], s['score'], 'PASS' if s['precision'] > 0.60 else 'fail', 100 * flagged))
