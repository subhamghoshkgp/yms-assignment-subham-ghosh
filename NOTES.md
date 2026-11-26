# Model and validation

## What the model knows at 09:15 IST

| Signal | Construction and cutoff |
|---|---|
| Stock volatility | Use the latest available stock option IV, the last completed NSE high–low range, its 5- and 22-session averages, and the mean absolute close-to-close return over 22 sessions. Domestic price observations have exchange dates strictly earlier than the prediction date. |
| Market opening gap | Convert the two Tokyo Nifty ETFs and the Hong Kong Sensex ETF into rupees. Compare each value with the previous Nifty close after centering the fund/index ratio on five earlier overlapping trading sessions. Combine these signals with US futures, Asian indices and Brent. |
| Stock opening gap | Multiply the estimated market gap by a 50-session stock beta, shrunk toward one. Adjust it for the US-listed ADR’s repricing where available and for peer ADRs in banking, IT and pharmaceuticals. |
| Market conditions | Use the previous India VIX close and yesterday’s traded value relative to its 20-session median. The assignment IV carries forward when a practice row is masked. |
| Earnings | Read the exchange dissemination time from NSE corporate announcements. A financial-results filing since the previous stock session’s 15:30 close and strictly before 09:15 triggers a flag. Notices from earlier daily NSE PR archives separately identify scheduled meetings today or in the last index session. |

The CSV’s `local_asof` is the last domestic stock price date. Nonempty `results_at_ist` entries preserve the filing’s timestamp and UTC offset. For foreign hourly bars, the availability check adds a full hour to the bar’s start and requires that time to be **strictly earlier** than the cutoff. A 09:00–10:00 IST bar is therefore ineligible. The evaluator provides each stock’s date-specific IV and turnover directly at prediction time.

## Decision rule

1. Form a weighted geometric mean of stock IV and rescaled realized volatility. The weights for IV, weekly range, monthly range, yesterday’s range and monthly absolute return are 45%, 30%, 15%, 5% and 5%. Percentage ranges are multiplied by 12 and absolute returns by 20 to put their magnitudes on a comparable scale. Cap an individual historical range at 12% and an absolute daily return at 10%.
2. Add 16 times the weighted magnitude of the predicted stock and index gaps. The weights are 65% and 35%, and each magnitude is capped at 5 percentage points. Add 12 times the clipped log of India VIX divided by 15, and 1.2 times the log of relative turnover.
3. Add 5 points for a previously announced results meeting today and 10 for one in the last index session. Flag scores of **45 or more**, as well as stocks with fresh results filings. A score of 45 is a decision threshold on this scale.

## Model selection

The opening-gap regression used 267 Nifty sessions between February 2025 and the start of the assignment in March 2026. Its target was the historical Nifty open relative to the previous close. All five inputs were available before that open. Ridge regression used an intercept and a penalty of 5. In a time split starting validation in October 2025, combining the Tokyo and Hong Kong signals gave an opening-gap mean absolute error of 0.228 percentage points and an R² of 0.559. The coefficients in `market_features.py` then used the full pre-assignment window.

For the stock decision, the first 66 assignment **training** dates served as development data, in three successive blocks of 22. Experiments compared the original model, multihorizon volatility blends, pre-period logistic regression, shallow gradient boosting, expanding logistic fits, and overnight-risk models with and without sector commodity shocks. The final search maximized the assignment score among candidates with at least 75% pooled precision and 62% precision in each development block. The selected model’s block precisions were 80.8%, 65.1% and 62.2%.

The following 31 training dates served as a chronological check. The earlier model’s official score was already known from the prior submission. The new model used training dates for selection and its threshold was fixed before its official evaluation.

| Period | Model | Correct flags / flags | Actual moves | Precision | Recall | Score |
|---|---|---:|---:|---:|---:|---:|
| First 66 training dates | Previous | 628 / 836 | 1,535 | 75.12% | 40.91% | 0.7882 |
| First 66 training dates | Current | 781 / 1,030 | 1,535 | 75.83% | 50.88% | 0.8219 |
| Later 31 training dates | Previous | 26 / 43 | 461 | 60.47% | 5.64% | 0.4198 |
| Later 31 training dates | Current | 33 / 42 | 461 | 78.57% | 7.16% | 0.4742 |
| Official test, 41 dates | Previous | 172 / 282 | 706 | 60.99% | 24.36% | 0.6658 |
| Official test, 41 dates | Current | 208 / 303 | 706 | 68.65% | 29.46% | 0.7178 |

A second feature build from the cached source responses reproduced the evaluated CSV byte for byte. The production predictor also matched the research decisions on all 4,850 training stock-days.

## Limitations

The model flags few stocks in quiet sessions. On the later training dates it missed 428 of 461 moves. Foreign ETFs can deviate from the underlying through currency effects, thin trading and tracking error. If an Asian market is closed, the gap estimate falls back to available markets. A published meeting notice records the schedule known on the publication date and can subsequently be revised. Exchange and vendor histories can also change, and intraday download retention is finite. The checked-in CSV preserves the evaluated inputs.

## Research and data sources

- Prior work on foreign-market information and opening gaps motivated the overnight signals. [De Gooijer, Diks and Gatarek](https://cendef.uva.nl/binaries/content/assets/subsites/amsterdam-school-of-economics/amsterdam-school-of-economics-research-institute/cendef/working-papers-2009/information---nfda_cendef_wp_0913.pdf)
- Multihorizon volatility research and an open implementation of the Optiver volatility task motivated testing rolling windows and boosted trees. [Journal of Econometrics](https://doi.org/10.1016/j.jeconom.2010.03.029) · [Optiver implementation](https://github.com/scottgrew/optiver-volatility)
- Instrument definitions for Tokyo tickers 1678 and 201A and Hong Kong ticker 2836. [Japan Exchange Group](https://www.jpx.co.jp/english/equities/products/etfs/issues/01-08.html) · [BlackRock prospectus](https://www.blackrock.com/hk/en/literature/prospectus/20250630-ishares-core-sp-bse-sensex-india-etf-prospectus-hk-en.pdf)
- Market prices come from Yahoo Finance charts. Corporate notices come from NSE filings and daily price-report archives. [Yahoo Finance](https://finance.yahoo.com/) · [NSE corporate announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements)
