"""Predict an intraday breach using only information available before the open."""
import argparse
import csv
import math
from pathlib import Path


def positive(row, column):
    try:
        x = float(row[column])
    except (KeyError, ValueError, TypeError):
        return None
    return x if math.isfinite(x) and x > 0 else None


def clamp(value, low, high):
    return min(high, max(low, value))


def sessions(directory, through):
    for path in sorted(directory.glob("*_n50.info.csv")):
        date = path.name[:8]
        if date <= through:
            with path.open(newline="") as f:
                yield date, list(csv.DictReader(f))


def features(history):
    """Update stock histories once per observed session, including its pre-open row."""
    states = {}
    for date, rows in history:
        stock_features = {}
        for row in rows:
            name = row["name"]
            state = states.setdefault(name, {})
            for col in ("vix", "vix_1m"):
                value = positive(row, col)
                if value is not None:
                    state[col] = value
            iv = state.get("vix", state.get("vix_1m", 23.0))
            normal_iv = state.get("vix_1m", iv)
            close, high, low = (positive(row, k) for k in ("pclose", "phi", "plo"))
            if close and high and low and high > low:
                price_range = clamp(100 * (high - low) / close, 0.25, 14.0)
                old_range = state.get("range", iv / 12.0)
                state["range"] = 0.15 * price_range + 0.85 * old_range
            else:
                price_range = state.get("range", iv / 12.0)
            recent_range = state.get("range", price_range)
            volume, usual = positive(row, "pvolume"), positive(row, "mddv_20")
            turnover = clamp(volume / usual, 0.25, 6.0) if volume and usual else 1.0
            stock_features[name] = (iv, normal_iv, price_range, recent_range, turnover)
        yield date, stock_features


def risk_score(stock, global_row):
    iv, normal_iv, last_range, avg_range, turnover = stock
    # Put percentage high-low ranges on a scale comparable with annualized IV.
    base = iv ** 0.65 * (12 * avg_range) ** 0.30 * (12 * last_range) ** 0.05
    base *= clamp(iv / normal_iv, 0.7, 1.5) ** 0.15 * turnover ** 0.05
    index_gap = abs(float(global_row["india_etf_gap_pct"]))
    stock_gap = abs(float(global_row["stock_gap_pct"]))
    overnight = min(0.3 * index_gap + 0.7 * stock_gap, 4.0)
    spx_move = min(abs(float(global_row["spx_return_pct"])), 3.0)
    japan_move = min(abs(float(global_row["nikkei_open_gap_pct"])), 3.0)
    return base + 4 * overnight + 2 * spx_move + 8 * japan_move


THRESHOLD = 44.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--historical-info", type=Path, required=True)
    parser.add_argument("--user-historical-info", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    for date, day in features(sessions(args.historical_info, args.date)):
        if date == args.date:
            break
    else:
        parser.error(f"missing historical info for {args.date}")
    with args.user_historical_info.open(newline="") as f:
        global_rows = {r["name"]: r for r in csv.DictReader(f) if r["date"] == date}
    scores = {name: risk_score(stock, global_rows[name]) for name, stock in day.items()}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / f"{date}.predictions.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["name", "prediction"])
        writer.writerows((name, score >= THRESHOLD) for name, score in scores.items())


if __name__ == "__main__":
    main()
