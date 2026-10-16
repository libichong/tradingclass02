"""One frozen round of 16 gap factors; daily cross-sectional rank IC, not PnL."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp


@dataclass(frozen=True)
class Protocol:
    splits: tuple[Split, ...]
    min_stocks: int
    min_days: Mapping[str, int]
    hac_lag: int
    validation_mean_min: float

    @classmethod
    def load(cls, path: Path) -> Protocol:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("round") != 1 or value.get("candidate_count") != 16:
            raise ValueError("This implementation supports round 1 with exactly 16 candidates")
        if value.get("label") != "close_T_plus_3 / close_T_plus_1 - 1":
            raise ValueError("Unsupported label")
        if value.get("selection") != "highest_positive_training_mean_rank_ic":
            raise ValueError("Unsupported selection rule")
        splits: list[Split] = []
        for name in ("train", "validation", "test"):
            segment = value["splits"][name]
            start = pd.Timestamp(date.fromisoformat(segment["start"]))
            end = pd.Timestamp(date.fromisoformat(segment["end"]))
            if start > end or (splits and start <= splits[-1].end):
                raise ValueError("Splits must be chronological and nonoverlapping")
            splits.append(Split(name, start, end))
        min_stocks = value["min_stocks"]
        min_days = value["min_days"]
        lag = value["hac_lag"]
        if type(min_stocks) is not int or min_stocks < 3:
            raise ValueError("min_stocks must be an integer >= 3")
        if type(lag) is not int or lag < 2:
            raise ValueError("hac_lag must be an integer >= 2 for overlapping two-session returns")
        if not isinstance(min_days, dict) or any(
            type(min_days.get(name)) is not int or min_days[name] < max(2, lag + 1)
            for name in ("train", "validation", "test")
        ):
            raise ValueError("min_days must exceed HAC lag for each split")
        threshold = value["validation_mean_min"]
        if isinstance(threshold, bool) or not isinstance(threshold, (float, int)) or not math.isfinite(threshold):
            raise ValueError("validation_mean_min must be finite")
        if value.get("validation_ci_lower_min") != 0:
            raise ValueError("Validation requires a strictly positive lower 95% CI bound")
        return cls(tuple(splits), min_stocks, min_days, lag, float(threshold))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_dates(values: pd.Series, field: str) -> pd.DatetimeIndex:
    parsed = pd.DatetimeIndex(pd.to_datetime(values, format="%Y-%m-%d", errors="raise"))
    if parsed.hasnans or parsed.tz is not None or not parsed.equals(parsed.normalize()):
        raise ValueError(f"{field} must contain date-only values")
    return parsed


def load_panel(data_path: Path, calendar_path: Path) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    raw = pd.read_csv(data_path, dtype={"symbol": "str"})
    required = ("date", "symbol", "open", "high", "low", "close", "volume")
    if not set(required).issubset(raw.columns) or raw.empty:
        raise ValueError(f"Nonempty CSV requires columns: {', '.join(required)}")
    raw["date"] = parse_dates(raw["date"], "date")
    if raw["symbol"].isna().any() or raw["symbol"].str.strip().eq("").any():
        raise ValueError("Empty symbols")
    if raw.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate date/symbol rows")
    numeric = list(required[2:])
    for column in numeric:
        raw[column] = pd.to_numeric(raw[column], errors="raise")
    if not np.isfinite(raw[numeric].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite prices or volume")
    if (raw[["open", "high", "low", "close"]] <= 0).any().any() or (raw["volume"] < 0).any():
        raise ValueError("Prices must be positive and volume nonnegative")
    if (raw["high"] < raw[["open", "low", "close"]].max(axis=1)).any() or (
        raw["low"] > raw[["open", "high", "close"]].min(axis=1)
    ).any():
        raise ValueError("Invalid OHLC range")
    calendar_data = pd.read_csv(calendar_path)
    if "date" not in calendar_data or calendar_data.empty:
        raise ValueError("Calendar CSV requires nonempty date column")
    calendar = parse_dates(calendar_data["date"], "calendar.date")
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("Calendar must be sorted with unique trading dates")
    if not pd.Index(raw["date"]).isin(calendar).all():
        raise ValueError("Some market dates are absent from the supplied trading calendar")
    # Retain all calendar sessions, including missing observations; never forward fill.
    panel = {name: raw.pivot(index="date", columns="symbol", values=name).reindex(calendar)
             for name in numeric}
    audit: dict[str, object] = {
        "rows": len(raw), "symbols": raw["symbol"].nunique(), "calendar_sessions": len(calendar),
        "first_date": str(calendar[0].date()), "last_date": str(calendar[-1].date()),
        "missing_price_cells": int(panel["close"].isna().sum().sum()),
        "zero_volume_rows": int(raw["volume"].eq(0).sum()),
        "price_adjustment": "Caller must provide consistently adjusted OHLC; not inferred",
        "universe": "Observed symbols only; survivorship/delistings require independent audit",
    }
    return panel, audit


def safe_ratio(numerator: pd.DataFrame, denominator: pd.DataFrame) -> pd.DataFrame:
    return numerator.div(denominator.where(denominator != 0)).replace([np.inf, -np.inf], np.nan)


def factors(panel: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    opening, closing, volume = panel["open"], panel["close"], panel["volume"]
    gap = np.log(safe_ratio(opening, closing.shift(1)))
    intraday = np.log(safe_ratio(closing, opening))
    returns = np.log(safe_ratio(closing, closing.shift(1)))
    average = gap.rolling(20).mean().shift(1)
    gap_std = gap.rolling(20).std(ddof=1).shift(1)
    volatility = returns.rolling(20).std(ddof=1).shift(1)
    relative_volume = safe_ratio(volume, volume.rolling(20).mean().shift(1))
    return {
        "g01_gap": gap,
        "g02_gap_mean_3": gap.rolling(3).mean(),
        "g03_gap_mean_5": gap.rolling(5).mean(),
        "g04_gap_mean_10": gap.rolling(10).mean(),
        "g05_gap_mean_20": gap.rolling(20).mean(),
        "g06_gap_surprise": gap - average,
        "g07_gap_zscore": safe_ratio(gap - average, gap_std),
        "g08_gap_vol_scaled": safe_ratio(gap, volatility),
        "g09_gap_5_vol_scaled": safe_ratio(gap.rolling(5).mean(), volatility),
        "g10_gap_direction_5": np.sign(gap).rolling(5).mean(),
        "g11_gap_positive_share_10": (gap > 0).astype(float).where(gap.notna()).rolling(10).mean(),
        "g12_gap_volume": gap * np.log1p(relative_volume),
        "g13_gap_volume_mean_5": (gap * np.log1p(relative_volume)).rolling(5).mean(),
        "g14_gap_intraday_confirm": gap * np.sign(intraday),
        "g15_gap_intraday_sum": (gap + intraday).rolling(5).mean(),
        "g16_gap_intraday": (gap - intraday).rolling(5).mean(),
    }


def labels(closing: pd.DataFrame, split: Split) -> pd.DataFrame:
    future_1, future_2, future_3 = closing.shift(-1), closing.shift(-2), closing.shift(-3)
    target = safe_ratio(future_3, future_1) - 1
    target = target.where(future_2.notna() & closing.notna())
    end_dates = pd.Series(closing.index, index=closing.index).shift(-3)
    eligible = (closing.index >= split.start) & (closing.index <= split.end) & (end_dates <= split.end)
    return target.loc[eligible]


def rank_ic(feature: pd.DataFrame, target: pd.DataFrame, min_stocks: int) -> pd.Series:
    x = feature.reindex(index=target.index, columns=target.columns)
    valid = np.isfinite(x) & np.isfinite(target)
    # Rank only the common stock universe, not unmatched values.
    rx = x.where(valid).rank(axis=1, method="average")
    ry = target.where(valid).rank(axis=1, method="average")
    dx, dy = rx.sub(rx.mean(axis=1), axis=0), ry.sub(ry.mean(axis=1), axis=0)
    denominator = np.sqrt((dx * dx).sum(axis=1) * (dy * dy).sum(axis=1))
    ic = (dx * dy).sum(axis=1).div(denominator.where(denominator > 0))
    return ic.where(valid.sum(axis=1) >= min_stocks).rename("rank_ic")


def statistics(series: pd.Series, lag: int, min_days: int) -> dict[str, object]:
    valid = series.dropna()
    count = len(valid)
    result: dict[str, object] = {"days": count, "eligible_calendar_days": len(series), "sufficient": count >= min_days}
    if count < 2:
        return {**result, "mean_rank_ic": None, "hac_95_ci": None, "positive_day_fraction": None}
    mean = float(valid.mean())
    # Missing IC days are zero contributions, preserving actual calendar lag distances.
    centered = (series - mean).fillna(0).to_numpy(dtype=float)
    long_run_sum = float(centered @ centered)
    for offset in range(1, min(lag, len(centered) - 1) + 1):
        weight = 1 - offset / (lag + 1)
        long_run_sum += 2 * weight * float(centered[offset:] @ centered[:-offset])
    standard_error = math.sqrt(max(long_run_sum, 0) * count / (count - 1)) / count
    return {
        **result, "mean_rank_ic": mean,
        "hac_95_ci": [mean - 1.96 * standard_error, mean + 1.96 * standard_error],
        "positive_day_fraction": float((valid > 0).mean()),
    }


def choose(metrics: Mapping[str, Mapping[str, dict[str, object]]]) -> str:
    eligible: list[tuple[float, str]] = []
    for name, segments in metrics.items():
        train = segments["train"]
        mean = train["mean_rank_ic"]
        if train["sufficient"] and isinstance(mean, float) and mean > 0:
            eligible.append((mean, name))
    if not eligible:
        raise ValueError("No positive training candidate with sufficient days; no factor selected")
    # Deterministic tie break; validation/test statistics cannot influence selection.
    return sorted(eligible, key=lambda entry: (-entry[0], entry[1]))[0][1]


def evaluate(panel: Mapping[str, pd.DataFrame], protocol: Protocol, include_test: bool = False) -> tuple[dict, dict, dict]:
    candidates = factors(panel)
    if len(candidates) != 16:
        raise RuntimeError("Candidate count is not 16")
    metrics: dict[str, dict[str, dict[str, object]]] = {name: {} for name in candidates}
    daily: dict[str, pd.DataFrame] = {}
    for split in protocol.splits:
        if split.name == "test":
            continue
        target = labels(panel["close"], split)
        daily[split.name] = pd.DataFrame({
            name: rank_ic(feature, target, protocol.min_stocks)
            for name, feature in candidates.items()
        })
        for name in candidates:
            metrics[name][split.name] = statistics(daily[split.name][name], protocol.hac_lag,
                                                  protocol.min_days[split.name])
    try:
        selected = choose(metrics)
    except ValueError as exc:
        selection = {"selected": None, "validation_pass": False, "reason": str(exc)}
    else:
        validation = metrics[selected]["validation"]
        mean, interval = validation["mean_rank_ic"], validation["hac_95_ci"]
        passed = bool(validation["sufficient"] and isinstance(mean, float) and isinstance(interval, list)
                      and mean > protocol.validation_mean_min and interval[0] > 0)
        selection = {"selected": selected, "validation_pass": passed,
                     "rule": "training only; validation gates test opening; test is descriptive"}
        if include_test:
            split = next(segment for segment in protocol.splits if segment.name == "test")
            target = labels(panel["close"], split)
            daily["test"] = pd.DataFrame({selected: rank_ic(candidates[selected], target, protocol.min_stocks)})
            metrics[selected]["test"] = statistics(daily["test"][selected], protocol.hac_lag,
                                                   protocol.min_days["test"])
    selection["test_opened"] = "test" in daily
    return metrics, daily, selection


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def input_identity(data: Path, calendar: Path, protocol: Path) -> dict[str, str]:
    return {
        "data_sha256": sha256(data), "calendar_sha256": sha256(calendar),
        "protocol_sha256": sha256(protocol), "implementation_sha256": sha256(Path(__file__)),
        "dependency_lock_sha256": sha256(Path(__file__).resolve().parents[2] / "requirements-lock.txt"),
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
    }


def freeze_experiment(directory: Path, protocol_path: Path, identity: dict[str, str]) -> None:
    Protocol.load(protocol_path)
    value = json.loads(protocol_path.read_text(encoding="utf-8"))
    contract = value.get("research_contract")
    required = ("universe", "adjustment", "signal_time", "execution_time", "stop_rule",
                "future_holdout", "costs_and_constraints", "previously_examined")
    if not isinstance(contract, dict) or any(
        not isinstance(contract.get(key), str) or not contract[key].strip() for key in required
    ):
        raise ValueError("Real research requires nonempty research_contract fields: " + ", ".join(required))
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "manifest.json", {
        "schema": 1, "frozen_at": datetime.now(timezone.utc).isoformat(), "identity": identity,
        "contract": contract, "command": sys.argv,
    })
    (directory / "protocol.json").write_bytes(protocol_path.read_bytes())


def claim_stage(directory: Path, identity: dict[str, str], open_test: bool) -> Path:
    frozen = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if frozen.get("schema") != 1 or frozen.get("identity") != identity:
        raise ValueError("Frozen input, implementation or runtime identity mismatch; do not overwrite the freeze")
    if open_test:
        development = json.loads((directory / "development.json").read_text(encoding="utf-8"))
        if development.get("status") != "completed" or not development.get("validation_pass"):
            raise ValueError("Test remains sealed: development must complete and pass frozen validation gates")
    stage = directory / ("test.json" if open_test else "development.json")
    with stage.open("x", encoding="utf-8") as stream:
        json.dump({"status": "started", "started_at": datetime.now(timezone.utc).isoformat(),
                   "command": sys.argv}, stream, ensure_ascii=False, indent=2)
    return stage


def render_report(metrics: dict, selection: dict, audit: dict, synthetic: bool) -> str:
    rows = [
        "# 第一轮：16 个跳空因子",
        "",
        "**合成数据冒烟测试，不是市场研究结论。**" if synthetic else "**历史数据结果，不是净收益或未来有效性证明。**",
        "",
        f"输入：{audit['symbols']} 个标的，{audit['rows']} 行；候选数：16。",
        f"训练期选中：`{selection['selected']}`；验证标准通过：{selection['validation_pass']}。",
        f"历史测试已开封：{selection['test_opened']}（只报告训练期选中的候选）。",
        "",
        "| 因子 | 分段 | 有效日 | 日均排序相关 | HAC 95% 区间 |",
        "|---|---|---:|---:|---|",
    ]
    for name, segments in metrics.items():
        for split, stat in segments.items():
            mean, ci = stat["mean_rank_ic"], stat["hac_95_ci"]
            text_mean = "NA" if mean is None else f"{mean:.6f}"
            text_ci = "NA" if ci is None else f"[{ci[0]:.6f}, {ci[1]:.6f}]"
            rows.append(f"| {name} | {split} | {stat['days']} | {text_mean} | {text_ci} |")
    rows.extend([
        "", "全部候选的开发期结果和无效结果均保留在 metrics.json；逐日 IC 在 daily_*.csv。",
        "无足够样本或无正向训练候选时明确不选因子；不得改看测试期后重新选择。",
        "g16 含日内反转，不是纯跳空延续；g14 方向确认也不等价于可交易动量。",
        "未处理真实成交、手续费、冲击、涨跌停、历史成分和独立复权审计。",
        "HAC 区间是渐近估计，未校正 16 候选选择偏差，不是多重检验后的显著性。",
        "重复使用的历史年份不能称为全新独立测试；合成结果不得用于作业实证结论。",
        "",
    ])
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--calendar", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--freeze", type=Path, help="Local immutable experiment registry directory")
    parser.add_argument("--freeze-only", action="store_true", help="Freeze identities without evaluating candidates")
    parser.add_argument("--open-test", action="store_true", help="Explicit single-use historical test opening")
    parser.add_argument("--synthetic", action="store_true", help="Mark generated sample results as synthetic")
    args = parser.parse_args()
    if args.synthetic and (args.freeze_only or args.freeze or args.open_test):
        parser.error("Synthetic smoke runs cannot be used as real freeze/test-opening evidence")
    if not args.synthetic and args.freeze is None:
        parser.error("Real research requires --freeze; first run with --freeze-only")
    if args.freeze_only and (args.open_test or args.output):
        parser.error("--freeze-only cannot be combined with --open-test or --output")
    if not args.freeze_only and args.output is None:
        parser.error("Evaluation requires a new --output directory")
    stage: Path | None = None
    output_created = False
    try:
        protocol = Protocol.load(args.protocol)
        identity = input_identity(args.data, args.calendar, args.protocol)
        if args.freeze_only:
            freeze_experiment(args.freeze, args.protocol, identity)
            print(json.dumps({"status": "frozen_without_evaluation", "freeze": str(args.freeze)}))
            return 0
        if not args.synthetic:
            stage = claim_stage(args.freeze, identity, args.open_test)
        args.output.mkdir(parents=True, exist_ok=False)
        output_created = True
        write_json(args.output / "manifest.json", {
            "status": "started", "synthetic": args.synthetic,
            **identity, "command": sys.argv, "test_requested": args.synthetic or args.open_test,
        })
        (args.output / "protocol.json").write_bytes(args.protocol.read_bytes())
        panel, audit = load_panel(args.data, args.calendar)
        write_json(args.output / "data_audit.json", audit)
        metrics, daily, selection = evaluate(panel, protocol, include_test=args.synthetic or args.open_test)
        if input_identity(args.data, args.calendar, args.protocol) != identity:
            raise ValueError("Inputs changed during evaluation; results must not be used")
        write_json(args.output / "metrics.json", metrics)
        write_json(args.output / "selection.json", selection)
        for name, frame in daily.items():
            frame.to_csv(args.output / f"daily_{name}.csv", index_label="date")
        (args.output / "report.md").write_text(render_report(metrics, selection, audit, args.synthetic), encoding="utf-8")
        selected = selection["selected"]
        required_splits = ("train", "validation", "test") if selection["test_opened"] else ("train", "validation")
        completed = selected is not None and all(
            metrics[selected][name]["sufficient"] for name in required_splits)
        status = {"status": "completed" if completed else "insufficient_evidence", **selection,
                  "exit_code": 0 if completed else 2}
        write_json(args.output / "status.json", status)
        if stage is not None:
            write_json(stage, {**status, "output": str(args.output.resolve())})
        print(json.dumps({"output": str(args.output), "sufficient_evidence": completed, **selection}, ensure_ascii=False))
        return 0 if completed else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failure = {"status": "failed", "exit_code": 1, "error_type": type(exc).__name__}
        if stage is not None:
            write_json(stage, failure)
        if output_created:
            write_json(args.output / "status.json", failure)
        parser.exit(1, f"Research failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
