"""Build stock features from quotes and disclosures available before 09:15 IST."""
import argparse
import csv
from bisect import bisect_left
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from math import log
from pathlib import Path

from market_data import announcements, board_notices, chart
from market_features import (Hourly, RelativePrice, StockHistory, average_present,
                             daily, filings, latest_results, market_gaps, opening_gap)

ADRS = {"HDFCBANK": "HDB", "ICICIBANK": "IBN", "INFY": "INFY", "WIPRO": "WIT", "DRREDDY": "RDY"}
SECTORS = [
    (("TCS", "HCLTECH", "TECHM", "INFY", "WIPRO"), ("INFY", "WIPRO")),
    (("HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN"), ("HDFCBANK", "ICICIBANK")),
    (("DRREDDY", "SUNPHARMA", "CIPLA"), ("DRREDDY",)),
]
HOUR_SERIES = ("1678.T", "201A.T", "2836.HK", "JPYINR=X", "HKDINR=X", "^NSEI",
               "ES=F", "NQ=F", "^N225", "^HSI", "BZ=F")
HEADER = ("date", "name", "local_asof", "range_1d", "range_5d", "range_22d", "abs_return_22d",
          "india_vix", "market_gap", "stock_gap", "results_at_ist", "meeting_today", "met_last_session")


def generate(dates, names, cache):
    first, last = dates[0], dates[-1]
    start = first - timedelta(days=130)
    daily_symbols = set(ADRS.values()) | {"INDY", "INDA", "^NSEI", "^INDIAVIX"}
    daily_symbols.update(name + ".NS" for name in set(names) | ADRS.keys())

    def quote_series(key):
        symbol, interval = key
        end = last + timedelta(days=1) if interval == "1h" else last
        data = chart(symbol, start, end, interval, cache)
        return Hourly(data) if interval == "1h" else daily(data)

    keys = [(s, "1d") for s in sorted(daily_symbols)] + [(s, "1h") for s in HOUR_SERIES]
    with ThreadPoolExecutor(max_workers=6) as pool:
        quotes = dict(zip(keys, pool.map(quote_series, keys)))
        index = quotes["^NSEI", "1d"]
        index_days = sorted(index)
        index_returns = {b: log(index[b][3] / index[a][3]) for a, b in zip(index_days, index_days[1:])}
        stocks = {s: StockHistory(quotes[s + ".NS", "1d"]) for s in names}
        vix = quotes["^INDIAVIX", "1d"]
        vix_days = sorted(vix)
        hourly = {s: quotes[s, "1h"] for s in HOUR_SERIES}
        markets = market_gaps(dates, hourly, index)
        adr_pairs = {s: RelativePrice(quotes[a, "1d"], quotes[s + ".NS", "1d"]) for s, a in ADRS.items()}
        etf_pairs = [RelativePrice(quotes[s, "1d"], index) for s in ("INDY", "INDA")]

        def results(s):
            rows = announcements(s, first - timedelta(days=31), last, cache)
            return filings(rows, s)
        releases = dict(zip(names, pool.map(results, names)))
        # Only older published snapshots can establish a schedule.
        notice_days = [d for d in index_days if first - timedelta(days=22) <= d < last]
        notices = defaultdict(dict)
        for publication, rows in zip(notice_days, pool.map(lambda d: board_notices(d, cache), notice_days)):
            for symbol, text in rows:
                meeting = date.fromisoformat(text)
                if publication < meeting:
                    notices[symbol].setdefault(meeting, publication)

    for target in dates:
        i = bisect_left(index_days, target)
        j = bisect_left(vix_days, target)
        if i == 0 or j == 0:
            raise ValueError(f"missing previous index session before {target}")
        index_window = index_days[max(0, i-50):i]
        previous_index = index_days[i-1]
        market = opening_gap(markets[target])
        us_index = 0.65 * etf_pairs[0].gap(target) + 0.35 * etf_pairs[1].gap(target)
        residual = {s: pair.gap(target) - us_index for s, pair in adr_pairs.items()}
        sector = {s: average_present([residual[p] for p in peers]) for members, peers in SECTORS for s in members}
        for name in names:
            stock = stocks[name]
            asof, last_range, week, month, abs_move = stock.recent(target)
            beta = stock.beta(index_window, index_returns)
            stock_gap = beta * market + 0.4 * sector.get(name, 0) + 0.25 * residual.get(name, 0)
            result = latest_results(releases[name], asof, target)
            values = (last_range, week, month, abs_move, vix[vix_days[j-1]][3], market, stock_gap)
            yield (target.strftime("%Y%m%d"), name, asof, *(round(v, 7) for v in values),
                   result.isoformat() if result else "", int(target in notices[name]),
                   int(previous_index in notices[name]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", type=Path, default=Path("data/all_dates.txt"))
    parser.add_argument("--names", type=Path, default=Path("data/n50_names.txt"))
    parser.add_argument("--out", type=Path, default=Path("user_historical_info.csv"))
    parser.add_argument("--cache-dir", type=Path, help="Reuse downloaded quotes and public exchange records")
    args = parser.parse_args()
    dates = sorted(datetime.strptime(d, "%Y%m%d").date() for d in args.dates.read_text().split())
    names = args.names.read_text().split()
    records = list(generate(dates, names, args.cache_dir))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(records)


if __name__ == "__main__":
    main()
