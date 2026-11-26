"""Pre-open signals computed from completed market sessions and timestamped filings."""
from bisect import bisect_left
from datetime import datetime, time, timezone
from math import fsum, isfinite, log
from statistics import median
from zoneinfo import ZoneInfo

INDIA = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def valid(x):
    return x is not None and isfinite(x) and x > 0


def pct(a, b):
    return 100 * log(a / b)


class Hourly:
    def __init__(self, chart):
        self.times = []
        self.values = []
        for ts, value in zip(chart["timestamp"], chart["indicators"]["quote"][0]["close"]):
            if valid(value):
                # Treat close as available only after the whole labelled hour has elapsed.
                self.times.append(ts + 3600)
                self.values.append(value)

    def last(self, cutoff, hours):
        stamp = cutoff.timestamp()
        i = bisect_left(self.times, stamp) - 1
        if i >= 0 and stamp - self.times[i] <= hours * 3600:
            return self.values[i]
        return None


def daily(chart):
    zone = ZoneInfo(chart["meta"]["exchangeTimezoneName"])
    quotes = chart["indicators"]["quote"][0]
    output = {}
    for i, ts in enumerate(chart["timestamp"]):
        prices = tuple(quotes[field][i] for field in ("open", "high", "low", "close"))
        if all(valid(x) for x in prices):
            output[datetime.fromtimestamp(ts, zone).date()] = prices
    return output


def etf_level(symbol, hourly, cutoff, hours):
    fund = hourly[symbol].last(cutoff, hours)
    fx = hourly["HKDINR=X" if symbol == "2836.HK" else "JPYINR=X"].last(cutoff, 6)
    return fund * fx if fund and fx else None


def market_gaps(dates, hourly, index):
    trading_days = sorted(index)
    funds = ("1678.T", "201A.T", "2836.HK")
    basis = {fund: [] for fund in funds}
    for day in trading_days:
        # Compare Asian fund and NSE quotes from the same historical trading window.
        anchor = datetime.combine(day, time(7, 1), UTC)
        local = hourly["^NSEI"].last(anchor, 1)
        for fund in funds:
            level = etf_level(fund, hourly, anchor, 1)
            if local and level:
                basis[fund].append((day, log(level / local)))
    output = {}
    for target in dates:
        pos = bisect_left(trading_days, target)
        if pos < 1:
            raise ValueError(f"no previous index session for {target}")
        previous = trading_days[pos - 1]
        close = index[previous][3]
        cutoff = datetime.combine(target, time(9, 15), INDIA)
        anchor = datetime.combine(previous, time(15, 30, 1), INDIA)
        row = {}
        for fund in funds:
            levels = basis[fund]
            stop = bisect_left(levels, (target, float("-inf")))
            level = etf_level(fund, hourly, cutoff, 3)
            row[fund] = (100 * (log(level / close) - median(v for _, v in levels[max(0, stop-5):stop]))
                         if level and stop >= 3 else None)
        for symbol in ("ES=F", "NQ=F", "BZ=F", "^N225", "^HSI"):
            first = hourly[symbol].last(anchor, 7)
            last = hourly[symbol].last(cutoff, 3)
            row[symbol] = pct(last, first) if first and last else None
        output[target] = row
    return output


def filings(raw, symbol):
    output = []
    for row in raw:
        if row.get("symbol") != symbol or not row.get("exchdisstime"):
            continue
        subject = (row.get("desc") or "").lower()
        body = (row.get("attchmntText") or "").lower()
        is_result = ("financial results" in subject or
                     ("outcome of board meeting" in subject and
                      any(word in body for word in ("result", "financial statement", "financial performance"))))
        if is_result:
            output.append(datetime.strptime(row["exchdisstime"], "%d-%b-%Y %H:%M:%S").replace(tzinfo=INDIA))
    return sorted(output)


def latest_results(events, previous_session, target):
    cutoff = datetime.combine(target, time(9, 15), INDIA)
    position = bisect_left(events, cutoff)
    if not position:
        return None
    release = events[position - 1]
    previous_close = datetime.combine(previous_session, time(15, 30), INDIA)
    return release if release >= previous_close else None


def bounded(x, low, high):
    return min(high, max(low, x))


def average_present(values):
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def opening_gap(markets):
    # Ridge fit on 267 Nifty opening gaps from before the assignment period.
    japan = average_present([markets["1678.T"], markets["201A.T"]])
    us = average_present([markets["NQ=F"], markets["ES=F"]])
    asia = average_present([markets["^HSI"], markets["^N225"]])
    hk = markets["2836.HK"]
    if hk is None:
        hk = japan if japan is not None else us
    if japan is None:
        japan = hk
    values = (japan, hk, us, asia, markets["BZ=F"])
    weights = (0.390640525417, 0.333233156111, 0.031214643423, 0.031725282664, -0.006716167480)
    return -0.0019622431 + sum(w * bounded(v or 0, -8, 8) for w, v in zip(weights, values))


class StockHistory:
    def __init__(self, bars):
        self.bars = bars
        self.days = sorted(bars)
        self.returns = {b: bounded(log(bars[b][3] / bars[a][3]), -0.08, 0.08)
                        for a, b in zip(self.days, self.days[1:])}

    def recent(self, target):
        pos = bisect_left(self.days, target)
        history = self.days[max(pos - 23, 0):pos]
        if len(history) < 2:
            raise ValueError(f"insufficient stock history before {target}")
        ranges = [min(12, pct(self.bars[d][1], self.bars[d][2])) for d in history[-22:]]
        moves = [min(10, abs(pct(self.bars[b][3], self.bars[a][3]))) for a, b in zip(history, history[1:])]
        return history[-1], ranges[-1], average_present(ranges[-5:]), average_present(ranges), average_present(moves)

    def beta(self, index_window, index_returns):
        pairs = [(self.returns[d], index_returns[d]) for d in index_window if d in self.returns and d in index_returns]
        if len(pairs) < 15:
            return 1.0
        stock_mean, index_mean = (sum(col) / len(pairs) for col in zip(*pairs))
        cov = fsum((s - stock_mean) * (m - index_mean) for s, m in pairs) / (len(pairs) - 1)
        index = [index_returns[d] for d in index_window if d in index_returns]
        mean = sum(index) / len(index)
        variance = fsum((m - mean)**2 for m in index) / (len(index) - 1)
        return bounded(0.66 * cov / variance + 0.34, 0.35, 2.1) if variance else 1.0


class RelativePrice:
    """US closing price relative to the Indian close and five earlier paired sessions."""
    def __init__(self, us, local):
        self.us, self.local = us, local
        self.us_days, self.local_days = sorted(us), sorted(local)
        self.paired = sorted(us.keys() & local.keys())
        self.logs = [log(us[d][3] / local[d][3]) for d in self.paired]

    def gap(self, target):
        u = self.us_days[bisect_left(self.us_days, target) - 1]
        d = self.local_days[bisect_left(self.local_days, target) - 1]
        stop = bisect_left(self.paired, min(u, d))
        if u >= target or d >= target or stop < 5:
            raise ValueError(f"insufficient paired prices before {target}")
        return 100 * (log(self.us[u][3] / self.local[d][3]) - median(self.logs[stop-5:stop]))
