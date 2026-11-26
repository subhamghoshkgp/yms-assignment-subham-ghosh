"""Regression checks for the pre-open information boundary."""
import csv
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_features import INDIA, Hourly, StockHistory, latest_results
from predict import predict_date


class PreOpenTests(unittest.TestCase):
    def test_hour_must_end_strictly_before_cutoff(self):
        cutoff = datetime(2026, 3, 4, 3, 45, tzinfo=timezone.utc)
        secs = int(cutoff.timestamp())
        bars = Hourly({"timestamp": [secs - 7200, secs - 3600, secs - 1800],
                       "indicators": {"quote": [{"close": [10, 90, 99]}]}})
        self.assertEqual(bars.last(cutoff, 3), 10)

    def test_same_day_price_cannot_change_rolling_range(self):
        target = date(2026, 3, 4)
        bars = {target - timedelta(days=i): (100, 101, 99, 100) for i in range(1, 25)}
        before = StockHistory(bars).recent(target)
        bars[target] = (100, 200, 50, 150)
        self.assertEqual(StockHistory(bars).recent(target), before)

    def test_only_overnight_results_published_before_open_qualify(self):
        previous, target = date(2026, 3, 3), date(2026, 3, 4)
        midday = datetime(2026, 3, 3, 12, 0, tzinfo=INDIA)
        overnight = datetime(2026, 3, 3, 18, 0, tzinfo=INDIA)
        cutoff = datetime(2026, 3, 4, 9, 15, tzinfo=INDIA)
        self.assertIsNone(latest_results([midday, cutoff], previous, target))
        self.assertEqual(latest_results([midday, overnight, cutoff], previous, target), overnight)

    def test_future_input_file_cannot_change_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            d = "20260304"
            (path / f"{d}_n50.info.csv").write_text("name,vix,vix_1m,pvolume,mddv_20\nA,22,21,10,10\n")
            user = path / "user.csv"
            user.write_text("date,name,range_1d,range_5d,range_22d,abs_return_22d,market_gap,stock_gap,"
                            "india_vix,results_at_ist,meeting_today,met_last_session\n"
                            "20260304,A,1,1,1,1,0,0,12,,0,0\n")
            expected = predict_date(d, path, user)
            (path / "20260305_n50.info.csv").write_text("name,vix\nA,1000\n")
            with user.open("a") as stream:
                csv.writer(stream).writerow(["20260305", "A", 8, 8, 8, 8, 8, 8, 80, "2026-03-05", 1, 1])
            self.assertEqual(expected, [("A", False)])
            self.assertEqual(predict_date(d, path, user), expected)


if __name__ == "__main__":
    unittest.main()
