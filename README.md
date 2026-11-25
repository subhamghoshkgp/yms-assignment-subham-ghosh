# YMS Financials Assignment

## Will a Nifty-50 stock move more than 2% today?

For every trading day and every Nifty-50 stock, predict **before the market opens** whether the stock
will trade more than 2% away from its previous close at any point during the day:

```
moved = max(high - pclose, pclose - low) / pclose > 2%
```

`high`/`low` are that day's high and low and `pclose` is the previous close. In other words, the stock
leaves the band `(pclose × 0.98, pclose × 1.02)` at least once.

**Example.** ADANIENT on 2026-03-04 had `pclose = 2124.6`, so its band was 2082.1 to 2167.1. That day its
low was about 2037.5, which is 4.10% below `pclose` (`down_move_pct = 4.0996`), while its high stayed below
`pclose` (`up_move_pct = -0.9414`). The largest move was 4.10% > 2%, so `moved = True`.

**Size.** 50 stocks × 138 trading days = 6,900 (date, stock) rows: 97 training days (4,850 rows, 41.2%
moved) and 41 test days (2,050 rows, 34.4% moved), all between 2026-03-04 and 2026-10-30.

## Quick start

```
git clone https://github.com/shantanusinghyms/YMS-Financial-Assignment.git
cd YMS-Financial-Assignment
mkdir my_submission
python prepare_user_historical_info.py --out my_submission/user_historical_info.csv
cp predict.py my_submission/
python evaluator/run_evaluation.py my_submission       # scores the template on the training dates
```

This runs the example model end to end and prints its precision, recall and score. Replace
`predict.py` (and, if you want extra data, `prepare_user_historical_info.py`) with your own, and run it again.

## What you get

| Path | Contents |
|---|---|
| `data/historical_info/<YYYYMMDD>_n50.info.csv` | One file per **training** date (97 dates, 2026-03-04 .. 2026-10-30), 50 rows (one per stock), known at that day's open |
| `data/train_labels.csv` | The answer for every training (date, name): `moved`, plus `max_move_pct`, `up_move_pct`, `down_move_pct` |
| `data/all_dates.txt` | All 138 dates: the training dates **and** the 41 test dates, which are drawn at random from the same period |
| `data/n50_names.txt` | The 50 stock symbols |
| `predict.py` | The program you submit (a working example to replace) |
| `prepare_user_historical_info.py` | Builds your extra data file (a template to replace) |
| `test_predictions.py` | The official scorer |
| `evaluator/run_evaluation.py` | The exact program that grades your submission: runs `predict.py` one date at a time with no future data, then scores it |
| `evaluator/data/` | The grading data: `info_all.csv` (info rows for all 138 dates), `test_dates.txt`, `test_labels.csv`, `labels_all.csv`, `train_dates.txt`, `dropped_dates.txt`, `masked_train_dates.txt` |
| `evaluator/build_dataset.py` | How all the data was built from the raw VIX and price files (for reference; the raw files are not included) |
| `evaluator/baselines.py` | Scores of simple reference rules on the test dates (table below) |

### Columns of an info file (everything is known before 09:15 on that date)

| Column | Meaning |
|---|---|
| `date`, `name` | Trading day (YYYYMMDD), NSE symbol |
| `pclose` | Previous trading day's close (the reference price for the 2% band) |
| `phi`, `plo` | Previous trading day's high and low (blank if that day's data is incomplete) |
| `pvolume` | Previous day's cash-market traded value, in rupees |
| `mddv_20` | Median daily traded value over the last 20 days, in rupees |
| `vix_asof` | The date the VIX columns below were computed on (the latest day before `date`) |
| `vix` | The stock's option-implied volatility (annualised %), averaged over `vix_asof`'s session. See below |
| `vix_1m`, `vix_3m`, `vix_6m`, `vix_1y` | Averages of the daily `vix` over the last 30 / 90 / 180 / 365 calendar days up to `vix_asof` |
| `vix_zscore_smooth`, `vix_zscore_raw` | How high the stock's `vix` is compared with the typical volatility of all ~224 F&O stocks. See below |

**One row of `data/historical_info/20260304_n50.info.csv`** (rounded):

```
date      name      pclose  phi     plo     pvolume       mddv_20       vix_asof  vix   vix_1m ... vix_zscore_smooth
20260304  ADANIENT  2124.6  2147.9  2073.7  4,487,653,648 3,113,771,485 20260302  37.2  37.2   ... 0.91
```

Before the open on 2026-03-04 you know that ADANIENT closed at 2124.6 the day before, traded between
2073.7 and 2147.9 that day, and its options priced about 37.2% annual volatility, roughly
`37.2 / 15.9 ≈ 2.3%` a day, so a 2% move is less than one normal day's swing for this stock.

### Understanding the volatility columns

**`vix`: the stock's own "fear gauge".** It is the volatility the options market expects for that stock
over the next ~30 days, worked out from the prices of its options (the same method as the India VIX /
CBOE VIX, applied to one stock). It is an annualised percentage, computed every minute from 09:30 to
15:30 and averaged over the day. Higher means options are pricing bigger moves.

A useful rule of thumb turns it into an expected **daily** move: `vix / sqrt(252)` is roughly one
standard deviation of a day's close-to-close move. For example `vix = 32` → about `32 / 15.9 ≈ 2.0%` a
day. The daily high-low range is usually larger than the close-to-close move.

**`vix_1m`, `vix_3m`, `vix_6m`, `vix_1y`: its recent history.** Averages of the daily `vix` over the
last 30 / 90 / 180 / 365 calendar days. The data starts on 2026-03-02, so early on these windows hold
only the days available: `vix_1y` always covers everything since 2026-03-02, and `vix_6m` equals it
until 2026-09-01. Comparing `vix` with
`vix_1m` shows whether a stock's volatility is rising or falling.

**`vix_zscore_smooth`: how volatile this stock is compared with the whole market.**

```
vix_zscore_smooth = (vix - M) / S
```

- `M` is the typical volatility level: the average, over ~All stocks (224 stocks) which have Futures and Options, of each stock's own
  3-month average `vix` (for example M ≈ 28).
- `S` is the typical spread: it combines how much each stock's `vix` varies over 3 months with how
  much the stocks differ from each other (for example S ≈ 7).
- `M` and `S` are the same for every stock on a given date, so the z-score ranks stocks against each
  other: `0` = an average F&O stock, `+1` = one spread above it (≈ 35 when M ≈ 28, S ≈ 7), `-1` = calmer
  than usual.

**`vix_zscore_raw`** is the same calculation on the unsmoothed minute-by-minute VIX (`vix` and
`vix_zscore_smooth` use a lightly smoothed series). The two are usually close; the raw one reacts
more to short spikes.

In `data/historical_info/`, some training dates have `pclose`, `phi`, `plo` and the VIX columns blank:
the day before was a test day, and those values would give its answer away. Their labels in
`train_labels.csv` are complete. During grading, every info file you are given is complete.

## What you submit

1. **`predict.py`**: run once per date as

   ```
   python predict.py --date YYYYMMDD --historical-info DIR --user-historical-info FILE --out-dir DIR
   ```

   It must write `<out-dir>/<YYYYMMDD>.predictions.csv` with columns `name,prediction`, one row per stock in
   that day's info file, `prediction` = `True` if you expect a move of more than 2%, otherwise `False`.
   For example, `predictions/20260304.predictions.csv`:

   ```
   name,prediction
   ADANIENT,True
   ADANIPORTS,False
   APOLLOHOSP,False
   ...                   (50 rows, one per stock)
   ```
2. **`prepare_user_historical_info.py`** and the **`user_historical_info.csv`** it produces: any extra data
   you want (market data APIs, index levels, global markets, …). Columns `date,name,<your features>`.
   Cover **every date in `data/all_dates.txt`**.
3. Any helper modules and model files your `predict.py` needs (not data files: see below).

Python 3 is assumed. List any packages you need in `requirements.txt`.

## How you are evaluated

Grading runs `evaluator/run_evaluation.py`, the same program included here, on the 41 test dates in `evaluator/data/`.
It runs your `predict.py` once per test date, one date at a time, in a fresh folder that contains only:
- `historical_info/` with the info files for every date **up to and including** the date being predicted
  (training dates and earlier test dates, never later ones);
- your `user_historical_info.csv` with rows dated **after** that date removed.

CSV/feather/parquet/pickle/zip files inside your submission are not copied into that folder, so put
learned parameters in code or a small `.json`/`.txt` file.

All test (date, stock) rows are scored together. A "positive" is a predicted move (`True`):

```
precision = TP / (TP + FP)      of the moves you predicted, how many happened
recall    = TP / (TP + FN)      of the moves that happened, how many you predicted

score     = sqrt( 1 / (0.75 / precision + 0.25 / recall) )
pass      = precision > 0.60
```

Candidates who pass are ranked by `score` (0 to 1, higher is better).

- The score is a **weighted harmonic mean**, with 75% of the weight on precision, put through a square root
  so that a solid model reads about 0.7 and a very good one about 0.8.
- A harmonic mean is close to 0 whenever either side is close to 0. Flagging only a handful of
  near-certain moves gets high precision but almost no recall, so it scores low (about 0.3–0.5).
  Flagging everything fails the precision bar.
- A missing prediction file or row counts as wrong: a missed move, or a false alarm.

**Worked example.** On the 2,050 test rows, 706 stocks actually move. Suppose you flag 320 rows and
210 of them move:

```
precision = 210 / 320                                = 0.656   (passes the 0.60 bar)
recall    = 210 / 706                                = 0.297
score     = sqrt( 1 / (0.75 / 0.656 + 0.25 / 0.297) ) = 0.710
```

**The test dates are calmer than the training dates.** About 34% of test rows move, against 41% of
training rows, so precision usually drops on the test dates. The template `predict.py` reaches 62.7%
precision on the training dates but only 53.3% on the test dates, which fails. Aim clearly above 60%
when you tune on the training dates.

### Reference scores on the test dates (`python evaluator/baselines.py`)

| Rule | Precision | Recall | Score | Result |
|---|---|---|---|---|
| Flag everything | 0.344 | 1.000 | 0.642 | fail |
| Only the top 1% by implied daily volatility | 0.895 | 0.024 | 0.299 | pass |
| Only the top 3% by implied daily volatility | 0.823 | 0.072 | 0.478 | pass |
| The template `predict.py` | 0.533 | 0.439 | 0.711 | fail |
| Implied daily volatility, tuned to 60% precision on train | 0.515 | 0.472 | 0.710 | fail |
| Implied daily volatility, tuned to 70% precision on train | 0.617 | 0.242 | 0.667 | pass |
| VIX z-score, tuned to 70% precision on train | 0.689 | 0.163 | 0.617 | pass |

### Run the grader yourself

Put `predict.py` and your `user_historical_info.csv` in one folder:

```
mkdir my_submission
python prepare_user_historical_info.py --out my_submission/user_historical_info.csv
cp predict.py my_submission/
python evaluator/run_evaluation.py my_submission                          # practice: the training dates
python evaluator/run_evaluation.py my_submission --data evaluator/data    # grading: the test dates
```

Each run writes `my_submission/eval_predictions/` and `my_submission/eval_score.json` and prints
precision, recall, score and PASS/FAIL. The second command is exactly how your submission is graded.

## Rules

- **No look-ahead.** A prediction for day D may only use information public before 09:15 on day D. A
  row of `user_historical_info.csv` dated D must follow the same rule (for example the previous day's
  close is fine, day D's own high or close is not).
- When predicting day D, `predict.py` may read only the files it is given.
- `evaluator/data/` holds the test dates and their answers so you can see exactly how grading works.
  Do not use the test labels, or anything about the test dates, to build, select or tune your model:
  tune on the training dates only, and say how in `NOTES.md`.
- Explain your approach in a short `NOTES.md`: features, model, and how you tuned it without using the
  test dates.

## How to submit

Keep your work private. **Do not fork this repository**: a fork of a public repository is public, so
other candidates could see your solution. Do not open a pull request either.

1. **Make your own private copy.** Click **Use this template → Create a new repository**, name it, for
   example, `yms-assignment-<your-name>`, select **Private**, and click **Create repository**.
   Without the button, create an empty **private** repository on GitHub and run:

   ```
   git clone https://github.com/shantanusinghyms/YMS-Financial-Assignment.git yms-assignment
   cd yms-assignment
   git remote set-url origin https://github.com/<your-username>/<your-private-repo>.git
   git push -u origin main
   ```

2. **Put your work at the top level of that repository:** `predict.py`, `prepare_user_historical_info.py`,
   `user_historical_info.csv`, `NOTES.md`, `requirements.txt`, and any helper modules or small model files.
3. **Check that it runs.** From the top of your repository, `python evaluator/run_evaluation.py .` grades
   it on the training dates, and adding `--data evaluator/data` grades it on the test dates.
4. **Give us access.** In your repository, go to **Settings → Collaborators → Add people** and invite
   both reviewers, one at a time: **`shantanusinghyms`** and **`Koteswar1008`**.
5. **Send us the link** to your repository. We grade the last commit on `main` with our own copy of
   `evaluator/` and `test_predictions.py`, so changes to those files in your repository have no effect.

## FAQ

**Can I use data that is not in the info files?** Yes. Put it in `user_historical_info.csv` (built by
your `prepare_user_historical_info.py`): index levels, global markets, earnings dates, anything. It must
cover every date in `data/all_dates.txt`, and a row dated D may only use information public before
09:15 on D.

**Which libraries can I use?** Any. List them in `requirements.txt`. The provided scripts need only the
Python standard library.

**How long may `predict.py` take?** The grader allows 300 seconds per date. A date that crashes or times
out writes no predictions, so all 50 rows of that date count as wrong.

**Some values are blank. Is that a bug?** No. `phi`/`plo` are blank when the previous day's data is
incomplete, and some training files are partly blanked (see above). Your code must handle blanks.

**Is accuracy part of the score?** No. It is printed for information only. Only precision (the pass bar)
and the score count.

**What should `NOTES.md` cover?** Your features, your model, how you chose its threshold on the training
dates (for example a walk-forward or a time-based split), and what you tried that did not work.

