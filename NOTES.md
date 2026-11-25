# Predicting a 2% intraday move before the Nifty opens

The target is a breach of either side of the band around yesterday’s close. The predictor produces one Boolean per stock and runs offline using only the supplied pre-open history and the submitted CSV.

## Signals

- **Stock volatility.** The base score is a weighted geometric mean of annualized implied volatility (65%), an exponentially smoothed previous-session high–low range (30%), and the most recent range (5%). Ranges are percentages of the previous close and are multiplied by 12 to put them on a comparable scale. The range smoother gives 15% weight to each new observation. Small adjustments account for implied volatility relative to its one-month average and turnover relative to its 20-session median. Missing observations use earlier values for the same stock. An unseen stock starts with a neutral IV of 23 if both IV fields are missing.
- **Overnight repricing.** Compare US closing prices of INDY and INDA with the latest previous Nifty close. Measure each log price ratio against its median over the five earlier matched sessions. This centers differences in price levels and persistent fund premiums. INDY receives 65% weight and INDA 35%. For HDFC Bank, ICICI Bank, Infosys, Wipro and Dr. Reddy’s, the corresponding ADR/local price ratio supplies a stock-specific signal. These ratios also reflect currency and tracking differences.
- **Global moves.** The latest completed S&P 500 close-to-close return and the Nikkei 225 opening gap provide two additional measures of market stress. All US and Indian closing prices have local session dates strictly earlier than the target date. The Nikkei normally opens at 05:30 IST. Only the Japanese opening value is used from the target session, against a strictly earlier close. An absent or late Japanese opening bar contributes zero.
- **Decision.** Add four times the overnight gap magnitude, twice the absolute S&P return and eight times the absolute Japanese opening gap to the base score. The overnight magnitude uses 70% stock and 30% index signals, capped at 4 percentage points. The other two magnitudes are each capped at 3 points. Predict a breach at a score of 44 or higher. This score is an index, not a calibrated probability.

## Training-only selection

The first 66 supplied training dates were used for model and threshold selection, examined in three consecutive 22-date blocks. The last 31 training dates were held back for a single chronological check. No random stock-row split was used. The selection compared IV alone, heavier weighting of realized ranges, a Monday adjustment, US-market-only signals, and combinations of ETF/ADR and Japanese opening signals. The selection favored the highest aggregate grading score among the final candidates with at least 73% development precision. The Monday adjustment reduced the score in the US-market comparison.

| Training period | Correct flags / all flags | Actual moves | Precision | Recall | Score |
|---|---:|---:|---:|---:|---:|
| Development, March 4–August 7 | 628 / 836 | 1,535 | 75.1% | 40.9% | 0.7882 |
| Held back, August 10–October 30 | 26 / 43 | 461 | 60.5% | 5.6% | 0.4198 |

The later period had fewer large moves and the model flagged very few of them. Its precision estimate rests on just 43 flags. All tuning and selection used training dates only. The published grading files were reserved for running the official evaluator after the model was fixed.

## Reproduction

Run from the repository root. The checked-in CSV covers all 6,900 date/stock pairs. Regenerating it requires internet access. The generator reads unadjusted daily OHLC fields from Yahoo Finance’s chart endpoint, using exchange-local dates. The two as-of columns identify the S&P session and whether a Japanese opening observation was used. The ETF/ADR alignment handles US and Indian holidays separately. Archived vendor prices can be corrected after the fact.

```sh
python -m pip install -r requirements.txt
python prepare_user_historical_info.py --out user_historical_info.csv
python evaluator/run_evaluation.py .
python evaluator/run_evaluation.py . --data evaluator/data
```

Nikkei publishes the time of its first index calculation in its [index FAQ](https://indexes.nikkei.co.jp/nkave/archives/faq/faq_nikkei_stock_average_en.pdf).
