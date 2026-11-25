"""Build point-in-time global market features for the Nifty-50 assignment."""
import argparse
import csv
import json
import math
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from statistics import median
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ADRS = {"HDFCBANK": "HDB", "ICICIBANK": "IBN", "INFY": "INFY", "WIPRO": "WIT", "DRREDDY": "RDY"}
PAIRS = {"INDY": "^NSEI", "INDA": "^NSEI", **{adr: name + ".NS" for name, adr in ADRS.items()}}


def load_quotes(symbol, start, end):
    def unix_day(day):
        return int(datetime.combine(day, time(), timezone.utc).timestamp())

    params = urlencode({"period1": unix_day(start), "period2": unix_day(end + timedelta(days=1)), "interval": "1d"})
    for host in ("query2", "query1"):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?{params}"
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
                result = json.load(response)["chart"]["result"][0]
            zone = ZoneInfo(result["meta"]["exchangeTimezoneName"])
            fields = result["indicators"]["quote"][0]
            bars = {}
            for stamp, opening, closing in zip(result["timestamp"], fields["open"], fields["close"]):
                instant = datetime.fromtimestamp(stamp, zone)
                bars[instant.date()] = (opening, closing, instant)
            if not bars:
                raise ValueError("empty quote history")
            return bars
        except (OSError, KeyError, IndexError, TypeError, ValueError) as exc:
            if host == "query1":
                raise RuntimeError(f"could not load {symbol}") from exc


def valid(value):
    return value is not None and math.isfinite(value) and value > 0


def before(days, target):
    i = bisect_left(days, target) - 1
    if i < 0 or (target - days[i]).days > 10:
        raise ValueError(f"missing recent close before {target}")
    return days[i]


class RelativePrice:
    """US/local closing-price ratio relative to its preceding five matched sessions."""
    def __init__(self, us, india):
        self.us, self.india = us, india
        self.us_days, self.india_days = sorted(us), sorted(india)
        self.paired = sorted(us.keys() & india.keys())
        self.logs = [math.log(us[d] / india[d]) for d in self.paired]

    def gap(self, target):
        us_day = before(self.us_days, target)
        india_day = before(self.india_days, target)
        stop = bisect_left(self.paired, min(us_day, india_day))
        if stop < 5:
            raise ValueError(f"insufficient paired history before {target}")
        current = math.log(self.us[us_day] / self.india[india_day])
        return 100 * (current - median(self.logs[stop-5:stop]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", type=Path, default=Path("data/all_dates.txt"))
    parser.add_argument("--names", type=Path, default=Path("data/n50_names.txt"))
    parser.add_argument("--out", type=Path, default=Path("user_historical_info.csv"))
    args = parser.parse_args()
    dates = sorted(datetime.strptime(d, "%Y%m%d").date() for d in args.dates.read_text().split())
    names = args.names.read_text().split()
    symbols = sorted(set(PAIRS) | set(PAIRS.values()) | {"^GSPC", "^N225"})
    start = dates[0] - timedelta(days=48)
    def fetch(symbol):
        end = dates[-1] if symbol == "^N225" else dates[-1] - timedelta(days=1)
        return load_quotes(symbol, start, end)

    with ThreadPoolExecutor(max_workers=4) as pool:
        bars = dict(zip(symbols, pool.map(fetch, symbols)))
    closes = {s: {d: bar[1] for d, bar in series.items() if valid(bar[1])} for s, series in bars.items()}
    pairs = {s: RelativePrice(closes[s], closes[local]) for s, local in PAIRS.items()}
    us_days, jp_days = sorted(closes["^GSPC"]), sorted(closes["^N225"])
    records = []
    for target in dates:
        us_day = before(us_days, target)
        spx = closes["^GSPC"]
        spx_return = 100 * (spx[us_day] / spx[before(us_days, us_day)] - 1)
        # The Nikkei opens at 09:00 JST (05:30 IST). Ignore a late or absent bar.
        opening_bar = bars["^N225"].get(target)
        cutoff = datetime.combine(target, time(9, 15), ZoneInfo("Asia/Kolkata"))
        jp_gap = 0.0
        has_open = opening_bar and valid(opening_bar[0]) and opening_bar[2] < cutoff
        if has_open:
            jp_gap = 100 * (opening_bar[0] / closes["^N225"][before(jp_days, target)] - 1)
        market = 0.65 * pairs["INDY"].gap(target) + 0.35 * pairs["INDA"].gap(target)
        for name in names:
            stock = pairs[ADRS[name]].gap(target) if name in ADRS else market
            records.append((target.strftime("%Y%m%d"), name, us_day, target if has_open else "",
                            round(spx_return, 6), round(jp_gap, 6), round(market, 6), round(stock, 6)))
    with args.out.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["date", "name", "spx_asof", "nikkei_open_asof", "spx_return_pct",
                         "nikkei_open_gap_pct", "india_etf_gap_pct", "stock_gap_pct"])
        writer.writerows(records)


if __name__ == "__main__":
    main()
