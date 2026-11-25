#!/usr/bin/env python3
"""Run a submission one date at a time, with no look-ahead, then score it. This is the exact
program used to grade submissions.

  python evaluator/run_evaluation.py SUBMISSION_DIR                          # practice: the training dates
  python evaluator/run_evaluation.py SUBMISSION_DIR --data evaluator/data    # grading: the test dates

SUBMISSION_DIR must contain predict.py and user_historical_info.csv (from
prepare_user_historical_info.py). For each date D the submission's code is copied into a fresh
sandbox that holds only:
  historical_info/            <date>_n50.info.csv for every date <= D (never a later date)
  user_historical_info.csv    the submitted file with rows dated after D removed
and `predict.py --date D ...` runs there. The prediction files are collected into
SUBMISSION_DIR/eval_predictions/ and scored with test_predictions.py.
Data files inside the submission (csv/feather/parquet/pickle/zip) are not copied into the sandbox,
so a submission cannot bring later info files with it.

Practice mode (default) uses this kit's data/historical_info/ and data/train_labels.csv.
Grading mode (--data DIR) uses DIR/info_all.csv (info rows for every date), DIR/test_dates.txt and
DIR/test_labels.csv; the test data is in evaluator/data/.
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SKIP_EXT = ('.csv', '.feather', '.parquet', '.pkl', '.pickle', '.zip', '.gz', '.h5', '.npz')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('submission')
    ap.add_argument('--data', help='test data folder, e.g. evaluator/data (info_all.csv, test_dates.txt, '
                                   'test_labels.csv); default: practice on the training dates in data/')
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--timeout', type=int, default=300, help='seconds per date')
    ap.add_argument('--min-precision', default='0.60')
    a = ap.parse_args()

    sub = os.path.abspath(a.submission)
    for need in ('predict.py', 'user_historical_info.csv'):
        if not os.path.exists(os.path.join(sub, need)):
            sys.exit('submission is missing %s' % need)
    with open(os.path.join(sub, 'user_historical_info.csv'), newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        if header[:2] != ['date', 'name']:
            sys.exit('user_historical_info.csv must start with columns date,name (got %s)' % header[:2])
        user_rows = list(reader)

    by_date, info_cols = {}, None
    if a.data:  # grading: one file with the info rows of every date, plus the hidden test dates/labels
        info_files = [os.path.join(a.data, 'info_all.csv')]
        dates = open(os.path.join(a.data, 'test_dates.txt')).read().split()
        labels = os.path.join(a.data, 'test_labels.csv')
    else:       # practice: the training info files and labels shipped in data/
        hist_dir = os.path.join(KIT, 'data', 'historical_info')
        info_files = [os.path.join(hist_dir, n) for n in sorted(os.listdir(hist_dir)) if n.endswith('_n50.info.csv')]
        dates = [os.path.basename(p)[:8] for p in info_files]
        labels = os.path.join(KIT, 'data', 'train_labels.csv')
    for path in info_files:
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            info_cols = info_cols or reader.fieldnames
            for r in reader:
                by_date.setdefault(r['date'], []).append(r)
    info_dates = sorted(by_date)
    out = os.path.join(sub, 'eval_predictions')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    failures = []
    for d in dates:
        with tempfile.TemporaryDirectory(prefix='n50eval_') as box:
            shutil.copytree(sub, os.path.join(box, 'code'), symlinks=False,
                            ignore=lambda src, names: [n for n in names if n.lower().endswith(SKIP_EXT)
                                                       or n in ('eval_predictions', 'predictions', '.git')])
            hist = os.path.join(box, 'historical_info')
            os.makedirs(hist)
            for x in info_dates:
                if x <= d:
                    with open(os.path.join(hist, x + '_n50.info.csv'), 'w', newline='') as f:
                        w = csv.DictWriter(f, fieldnames=info_cols)
                        w.writeheader()
                        w.writerows(by_date[x])
            user = os.path.join(box, 'user_historical_info.csv')
            with open(user, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(r for r in user_rows if r and r[0] <= d)
            pred_dir = os.path.join(box, 'predictions')
            cmd = [a.python, 'predict.py', '--date', d, '--historical-info', hist,
                   '--user-historical-info', user, '--out-dir', pred_dir]
            try:
                p = subprocess.run(cmd, cwd=os.path.join(box, 'code'), capture_output=True, text=True, timeout=a.timeout)
                ok = p.returncode == 0
                err = p.stderr.strip().splitlines()[-1:] if not ok else []
            except subprocess.TimeoutExpired:
                ok, err = False, ['timeout after %ds' % a.timeout]
            result = os.path.join(pred_dir, d + '.predictions.csv')
            if ok and os.path.exists(result):
                shutil.copy(result, out)
            else:
                failures.append((d, err or ['no %s.predictions.csv written' % d]))
        print('%s %s' % (d, 'ok' if not failures or failures[-1][0] != d else 'FAILED: ' + ' '.join(failures[-1][1])), flush=True)
    print('ran %d dates, %d failed (a failed date counts as all wrong)' % (len(dates), len(failures)))
    scorer = [a.python, os.path.join(KIT, 'test_predictions.py'), out, '--labels', labels,
              '--json', os.path.join(sub, 'eval_score.json'), '--min-precision', a.min_precision]
    return subprocess.call(scorer)


if __name__ == '__main__':
    sys.exit(main())
