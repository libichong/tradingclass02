"""Generate explicitly synthetic fixtures to exercise the research pipeline."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .research import write_json


def generate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    random = np.random.default_rng(20261011)
    dates = pd.bdate_range("2016-01-01", periods=360)
    frames: list[pd.DataFrame] = []
    for number in range(40):
        strength = (number - 19.5) / 19.5
        gap = strength * 0.003 + random.normal(0, 0.002, len(dates))
        intraday = strength * 0.001 + random.normal(0, 0.003, len(dates))
        close = 50 * np.exp(np.cumsum(gap + intraday))
        previous = np.r_[50, close[:-1]]
        opening = previous * np.exp(gap)
        frames.append(pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"), "symbol": f"SYNTH{number:03d}",
            "open": opening, "high": np.maximum(opening, close) * 1.002,
            "low": np.minimum(opening, close) * 0.998, "close": close,
            "volume": random.integers(1000, 100000, len(dates)),
        }))
    pd.concat(frames, ignore_index=True).to_csv(directory / "synthetic_prices.csv", index=False)
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d")}).to_csv(directory / "synthetic_calendar.csv", index=False)
    write_json(directory / "synthetic_protocol.json", {
        "round": 1, "candidate_count": 16,
        "label": "close_T_plus_3 / close_T_plus_1 - 1",
        "selection": "highest_positive_training_mean_rank_ic",
        "splits": {
            name: {"start": str(dates[start].date()), "end": str(dates[end].date())}
            for name, start, end in (("train", 0, 179), ("validation", 180, 269), ("test", 270, 359))
        },
        "min_stocks": 30, "min_days": {"train": 60, "validation": 20, "test": 20},
        "hac_lag": 5, "validation_mean_min": 0.01, "validation_ci_lower_min": 0,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    generate(parser.parse_args().output)
