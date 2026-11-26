# Nifty-50 pre-open move prediction

This repository contains Subham Ghosh’s submission for the YMS Financials assignment. Before 09:15 IST, the predictor flags stocks expected to trade more than 2% above or below their previous close at any point during the session.

## Official evaluation

| Model | Precision | Recall | Score | Correct flags | False alarms |
|---|---:|---:|---:|---:|---:|
| Previous submission | 60.99% | 24.36% | 0.6658 | 172 | 110 |
| Current submission | 68.65% | 29.46% | 0.7178 | 208 | 95 |

The official grader scored 2,050 stock-days across 41 dates. The current model flagged 303 cases, caught 208 of the 706 moves, and passed the 60% precision requirement. All required predictions were present.

## Run the grader

Use Python 3.9 or later. The checked-in feature file covers all 50 stocks on all 138 assignment dates. Grading runs offline.

```sh
python -m pip install -r requirements.txt
python evaluator/run_evaluation.py .                     # 97 practice dates
python evaluator/run_evaluation.py . --data evaluator/data  # 41 official test dates
```

## How the prediction works

The model estimates the Nifty’s overnight move from India-focused ETFs trading in Tokyo and Hong Kong, exchange rates, and international markets. For each stock, it combines this estimate with the stock’s sensitivity to the index, recent trading ranges, options-implied volatility, and earnings disclosures. A qualifying results filing between the previous close and the cutoff triggers a flag directly.

## Repository guide

| File or directory | Purpose |
|---|---|
| `predict.py` | Offline prediction entry point used by the official grader |
| `user_historical_info.csv` | Frozen pre-open features for the 6,900 stock-days |
| `prepare_user_historical_info.py` | Rebuilds the feature file from public sources |
| `market_data.py`, `market_features.py` | Data retrieval, timestamp alignment and feature calculations |
| `NOTES.md` | Model specification, chronological validation, results and limitations |
| `tests/` | Checks for the 09:15 cutoff and exclusion of future observations |
| `data/`, `evaluator/`, `test_predictions.py` | Original assignment dataset, evaluator and scorer |

## Rebuild and verify

```sh
python prepare_user_historical_info.py --cache-dir .cache/yms --out user_historical_info.csv
python -m unittest discover -s tests -v
```

Rebuilding requires internet access to Yahoo Finance and NSE. The optional cache saves repeat downloads. The official assignment specification is available in the [YMS template](https://github.com/shantanusinghyms/YMS-Financial-Assignment).
