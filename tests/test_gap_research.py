from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from projects.gap_research.research import (
    Protocol, Split, choose, evaluate, factors, labels, load_panel, rank_ic, statistics,
)
from projects.gap_research.synthetic import generate


class GapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dates = pd.bdate_range("2020-01-01", periods=70)
        x = np.arange(70, dtype=float)
        closing = pd.DataFrame({"A": 100 + x, "B": 130 + x * 0.7, "C": 80 + x * 0.9}, index=self.dates)
        self.panel = {
            "close": closing, "open": closing * 0.99,
            "high": closing * 1.01, "low": closing * 0.98,
            "volume": closing * 100,
        }

    def test_exactly_sixteen_candidates_and_g16_formula(self) -> None:
        result = factors(self.panel)
        self.assertEqual(len(result), 16)
        gap = np.log(self.panel["open"] / self.panel["close"].shift(1))
        intraday = np.log(self.panel["close"] / self.panel["open"])
        pd.testing.assert_frame_equal(result["g16_gap_intraday"], (gap - intraday).rolling(5).mean())

    def test_no_future_feature_leakage(self) -> None:
        baseline = factors(self.panel)
        changed = {name: frame.copy() for name, frame in self.panel.items()}
        for frame in changed.values():
            frame.iloc[45:] *= 100
        revised = factors(changed)
        for name in baseline:
            pd.testing.assert_frame_equal(baseline[name].iloc[:45], revised[name].iloc[:45])

    def test_label_endpoints_and_split_purge(self) -> None:
        split = Split("train", self.dates[0], self.dates[10])
        target = labels(self.panel["close"], split)
        self.assertEqual(target.index[-1], self.dates[7])
        self.assertAlmostEqual(target.iloc[0]["A"], 103 / 101 - 1)

    def test_missing_sessions_not_next_observation_shift(self) -> None:
        closing = self.panel["close"].copy()
        closing.loc[self.dates[1], "A"] = np.nan
        target = labels(closing, Split("train", self.dates[0], self.dates[-1]))
        self.assertTrue(pd.isna(target.loc[self.dates[0], "A"]))
        closing.loc[self.dates[2], "B"] = np.nan
        target = labels(closing, Split("train", self.dates[0], self.dates[-1]))
        self.assertTrue(pd.isna(target.loc[self.dates[0], "B"]))
        with_gap = {name: frame.copy() for name, frame in self.panel.items()}
        with_gap["close"].loc[self.dates[30], "A"] = np.nan
        self.assertTrue(pd.isna(factors(with_gap)["g01_gap"].loc[self.dates[31], "A"]))

    def test_rank_ic_uses_paired_universe(self) -> None:
        feature = pd.DataFrame([[1, 2, 3, 100]], columns=list("ABCD"))
        target = pd.DataFrame([[3, 2, 1, np.nan]], columns=list("ABCD"))
        self.assertAlmostEqual(rank_ic(feature, target, 3).iloc[0], -1)
        self.assertTrue(pd.isna(rank_ic(feature, target, 4).iloc[0]))
        self.assertTrue(pd.isna(rank_ic(feature * 0, target, 3).iloc[0]))

    def test_selection_never_uses_validation_or_test(self) -> None:
        metrics = {
            "a": {"train": {"sufficient": True, "mean_rank_ic": 0.1}, "test": {"mean_rank_ic": -1}},
            "b": {"train": {"sufficient": True, "mean_rank_ic": 0.05}, "test": {"mean_rank_ic": 1}},
        }
        self.assertEqual(choose(metrics), "a")
        metrics["a"]["test"]["mean_rank_ic"] = 1
        self.assertEqual(choose(metrics), "a")
        with self.assertRaisesRegex(ValueError, "No positive"):
            choose({"a": {"train": {"sufficient": True, "mean_rank_ic": -0.1}}})

    def test_hac_statistics_and_insufficient_sample(self) -> None:
        stat = statistics(pd.Series([0.1] * 20), 5, 10)
        self.assertTrue(stat["sufficient"])
        self.assertAlmostEqual(stat["mean_rank_ic"], 0.1)
        np.testing.assert_allclose(stat["hac_95_ci"], [0.1, 0.1])
        empty = statistics(pd.Series([np.nan]), 5, 10)
        self.assertFalse(empty["sufficient"])
        self.assertIsNone(empty["mean_rank_ic"])

    def test_zero_volatility_does_not_produce_infinity(self) -> None:
        flat = {name: frame * 0 + 100 for name, frame in self.panel.items()}
        result = factors(flat)
        for frame in result.values():
            self.assertFalse(np.isinf(frame.to_numpy()).any())
        self.assertTrue(result["g07_gap_zscore"].isna().all().all())

    def test_synthetic_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sample"
            generate(root)
            panel, audit = load_panel(root / "synthetic_prices.csv", root / "synthetic_calendar.csv")
            protocol = Protocol.load(root / "synthetic_protocol.json")
            metrics, daily, selected = evaluate(panel, protocol)
            self.assertEqual(audit["symbols"], 40)
            self.assertEqual(len(metrics), 16)
            self.assertEqual(set(daily), {"train", "validation", "test"})
            self.assertIsNotNone(selected["selected"])
            self.assertTrue(all(len(segments) == 3 for segments in metrics.values()))

    def test_data_validation_and_calendar_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            calendar = root / "calendar.csv"
            rows = pd.DataFrame({
                "date": ["2020-01-01", "2020-01-03"], "symbol": ["A", "A"],
                "open": [10, 11], "high": [12, 12], "low": [9, 9],
                "close": [11, 10], "volume": [10, 0],
            })
            rows.to_csv(data, index=False)
            pd.DataFrame({"date": ["2020-01-01", "2020-01-02", "2020-01-03"]}).to_csv(calendar, index=False)
            panel, audit = load_panel(data, calendar)
            self.assertTrue(pd.isna(panel["close"].iloc[1, 0]))
            self.assertEqual(audit["zero_volume_rows"], 1)
            pd.concat([rows, rows.iloc[:1]]).to_csv(data, index=False)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_panel(data, calendar)
            rows.loc[0, "high"] = 1
            rows.to_csv(data, index=False)
            with self.assertRaisesRegex(ValueError, "OHLC"):
                load_panel(data, calendar)


if __name__ == "__main__":
    unittest.main()
