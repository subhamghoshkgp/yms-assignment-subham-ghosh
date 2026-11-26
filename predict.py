"""Write one pre-open 2% band-breach prediction per stock for the requested date."""
import argparse
import csv
from math import isfinite, log
from pathlib import Path

THRESHOLD = 45.0


def positive(row, key):
    try:
        value = float(row[key])
    except (KeyError, ValueError, TypeError):
        return None
    return value if isfinite(value) and value > 0 else None


def predict(iv, turnover, row):
    if row["results_at_ist"]:
        return True
    volatility = (iv ** 0.45 * (12 * float(row["range_5d"])) ** 0.30
                  * (12 * float(row["range_22d"])) ** 0.15 * (12 * float(row["range_1d"])) ** 0.05
                  * (20 * float(row["abs_return_22d"])) ** 0.05)
    market = min(5, abs(float(row["market_gap"])))
    stock = min(5, abs(float(row["stock_gap"])))
    india_vix = max(-1, min(1, log(float(row["india_vix"]) / 15)))
    score = (volatility + 16 * (0.65 * stock + 0.35 * market) + 12 * india_vix
             + 1.2 * log(turnover) + 10 * int(row["met_last_session"]) + 5 * int(row["meeting_today"]))
    return score >= THRESHOLD


def predict_date(date, historical_info, user_info):
    last_iv, monthly_iv = {}, {}
    today_path = historical_info / f"{date}_n50.info.csv"
    if not today_path.is_file():
        raise ValueError(f"missing info file for {date}")
    for path in sorted(historical_info.glob("*_n50.info.csv")):
        session = path.name[:8]
        if session > date:
            break
        with path.open(newline="") as stream:
            today = list(csv.DictReader(stream))
        for r in today:
            for key, state in (("vix", last_iv), ("vix_1m", monthly_iv)):
                value = positive(r, key)
                if value is not None:
                    state[r["name"]] = value
        if session == date:
            break
    with user_info.open(newline="") as stream:
        context = {r["name"]: r for r in csv.DictReader(stream) if r["date"] == date}
    predictions = []
    for r in today:
        name = r["name"]
        volume, typical = positive(r, "pvolume"), positive(r, "mddv_20")
        turnover = max(0.3, min(5, volume / typical)) if volume and typical else 1
        predictions.append((name, predict(last_iv.get(name, monthly_iv.get(name, 23)), turnover, context[name])))
    return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--historical-info", type=Path, required=True)
    parser.add_argument("--user-historical-info", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = predict_date(args.date, args.historical_info, args.user_historical_info)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / f"{args.date}.predictions.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["name", "prediction"])
        writer.writerows(rows)


if __name__ == "__main__":
    main()
