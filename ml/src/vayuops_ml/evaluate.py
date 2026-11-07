"""Pooled, city-macro, and paired uncertainty metrics for forecasts."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def metrics(y_true: pd.Series, y_pred: pd.Series, persistence: pd.Series) -> dict[str, float | int | None]:
    """Return pooled MAE/RMSE and skill versus persistence."""
    actual = pd.Series(y_true, dtype=float).reset_index(drop=True)
    predicted = pd.Series(y_pred, dtype=float).reset_index(drop=True)
    baseline = pd.Series(persistence, dtype=float).reset_index(drop=True)
    valid = actual.notna() & predicted.notna() & baseline.notna()
    if not valid.any():
        return {"n": 0, "mae": None, "rmse": None, "skill": None, "rmse_skill": None}
    error = actual[valid] - predicted[valid]
    base_error = actual[valid] - baseline[valid]
    mae = float(error.abs().mean())
    rmse = float(math.sqrt(error.pow(2).mean()))
    base_mae = float(base_error.abs().mean())
    base_rmse = float(math.sqrt(base_error.pow(2).mean()))
    return {
        "n": int(valid.sum()), "mae": mae, "rmse": rmse,
        "skill": float(1 - mae / base_mae) if base_mae else None,
        "rmse_skill": float(1 - rmse / base_rmse) if base_rmse else None,
    }


def score_predictions(frame: pd.DataFrame) -> dict[str, float | int | None]:
    """Report pooled and equal-city macro metrics on the same paired rows."""
    pooled = metrics(frame.y_true, frame.y_pred, frame.y_persistence)
    city_scores = [
        metrics(group.y_true, group.y_pred, group.y_persistence)
        for _, group in frame.groupby("city", observed=True)
    ]
    result = dict(pooled)
    for key in ("mae", "rmse", "skill", "rmse_skill"):
        valid = [score[key] for score in city_scores if score[key] is not None]
        result[f"macro_{key}"] = float(np.mean(valid)) if valid else None
    result["cities"] = len(city_scores)
    baseline_city_mae = [
        float((group.y_true - group.y_persistence).abs().mean())
        for _, group in frame.groupby("city", observed=True)
    ]
    baseline_macro_mae = float(np.mean(baseline_city_mae)) if baseline_city_mae else None
    result["macro_mae_skill"] = (
        float(1 - result["macro_mae"] / baseline_macro_mae)
        if baseline_macro_mae and result["macro_mae"] is not None else None
    )
    return result


def moving_block_bootstrap(
    frame: pd.DataFrame, block_days: int, resamples: int, seed: int,
    statistic: str = "mae_difference",
) -> dict[str, float | bool | None]:
    """Resample paired calendar-day blocks, keeping cities together within each day."""
    if frame.empty:
        return {"estimate": None, "ci_low": None, "ci_high": None, "excludes_zero": False}
    dates = pd.to_datetime(frame["date"])
    days = pd.date_range(dates.min(), dates.max(), freq="D")
    cities = sorted(frame["city"].astype(str).unique())
    day_positions = pd.Index(days).get_indexer(dates)
    city_positions = pd.Index(cities).get_indexer(frame["city"].astype(str))
    shape = (len(days), len(cities))
    model_error = np.full(shape, np.nan)
    base_error = np.full(shape, np.nan)
    model_error[day_positions, city_positions] = (
        frame["y_true"] - frame["y_pred"]
    ).abs().to_numpy(dtype=float)
    base_error[day_positions, city_positions] = (
        frame["y_true"] - frame["y_persistence"]
    ).abs().to_numpy(dtype=float)

    def calculate(indices: np.ndarray) -> float:
        model = model_error[indices]
        baseline = base_error[indices]
        if statistic == "mae_difference":
            return float(np.nanmean(model - baseline))
        if statistic == "macro_skill":
            model_city = np.nanmean(model, axis=0)
            base_city = np.nanmean(baseline, axis=0)
            valid = np.isfinite(model_city) & np.isfinite(base_city) & (base_city > 0)
            return float(np.mean(1 - model_city[valid] / base_city[valid])) if valid.any() else float("nan")
        raise ValueError(f"Unknown bootstrap statistic: {statistic}")

    point = calculate(np.arange(len(days)))
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, len(days) - block_days + 1))
    estimates = np.empty(resamples, dtype=float)
    blocks_needed = math.ceil(len(days) / block_days)
    for index in range(resamples):
        sampled_starts = rng.choice(starts, size=blocks_needed, replace=True)
        sampled_days = np.concatenate([
            np.arange(start, min(start + block_days, len(days))) for start in sampled_starts
        ])[:len(days)]
        estimates[index] = calculate(sampled_days)
    finite = estimates[np.isfinite(estimates)]
    if finite.size == 0:
        return {"estimate": point, "ci_low": None, "ci_high": None, "excludes_zero": False}
    low, high = np.quantile(finite, [0.025, 0.975])
    low, high = min(float(low), point), max(float(high), point)
    return {
        "estimate": point, "ci_low": low, "ci_high": high,
        "excludes_zero": bool(low > 0 or high < 0),
    }


def monthly_errors(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate selected-model and persistence MAE by split and month."""
    work = frame.copy()
    work["month"] = pd.to_datetime(work["date"]).dt.to_period("M").astype(str)
    work["best_error"] = (work["y_true"] - work["y_pred_best"]).abs()
    work["persistence_error"] = (work["y_true"] - work["y_pred_persistence"]).abs()
    return (
        work.groupby(["split", "month"], as_index=False)[["best_error", "persistence_error"]]
        .mean()
        .rename(columns={"best_error": "mae_best", "persistence_error": "mae_persistence"})
    )


def markdown_results(results: dict) -> str:
    """Render a compact report with macro MAE reduction as the headline metric."""
    def number(value: float | int | None) -> str:
        return "—" if value is None else f"{value:.3f}"

    selected_id = results["best_config"]["config_id"]
    selected = {
        row["split"]: row for row in results["model_metrics"]
        if row["config_id"] == selected_id
    }
    lines = [
        "# VayuOps model results", "", "## Findings", "", results["findings"], "",
        "MAE reduction vs persistence = 1 - macro MAE / persistence macro MAE.",
        "",
        "## Best stable configuration per model family", "",
        "| Model | Config | Target | Objective | Features | Key params | Selected | Fit (val / test) | Val macro MAE | Val MAE reduction | Val mean per-city skill | Test A macro MAE | Test A MAE reduction | Test A mean per-city skill | Test B macro MAE | Test B MAE reduction | Test B mean per-city skill |",
        "|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results["summary_configs"]:
        lines.append(
            f"| {row['model']} | {row['config_id']} | {row['target_mode']} | "
            f"{row['objective']} | {', '.join(row['feature_groups']) or 'base'} | "
            f"{row['key_params']} | {'Yes' if row['selected'] else ''} | train / train+val | "
            + " | ".join(number(row[key]) for key in (
                "val_macro_mae", "val_macro_mae_skill", "val_macro_skill",
                "test_a_macro_mae", "test_a_macro_mae_skill", "test_a_macro_skill",
                "test_b_macro_mae", "test_b_macro_mae_skill", "test_b_macro_skill",
            )) + " |"
        )
    lines.extend([
        "", "All configurations, including unstable ones: `reports/grid_results.csv`.",
        "", "## Paired MAE difference versus persistence", "",
        "Negative paired differences favor the selected model. Moving-block bootstrap: 14-day blocks, 1,000 resamples.",
        "", "| Split | MAE reduction | Paired MAE difference | 95% interval | Excludes zero |",
        "|---|---:|---:|---:|---|",
    ])
    for split in ("val", "test_a", "test_b"):
        row = results["bootstrap"][split]
        lines.append(
            f"| {split} | {number(selected[split]['macro_mae_skill'])} | "
            f"{number(row['estimate'])} | "
            f"[{number(row['ci_low'])}, {number(row['ci_high'])}] | "
            f"{row['excludes_zero']} |"
        )
    lines.extend([
        "", "## Selected model by city", "",
        "| Split | City | n | MAE | RMSE | MAE reduction | RMSE skill |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in results["per_city"]:
        lines.append(
            f"| {row['split']} | {row['city']} | {row['n']} | "
            + " | ".join(number(row[key]) for key in ("mae", "rmse", "skill", "rmse_skill"))
            + " |"
        )
    lines.extend([
        "", "## Test B station match", "",
        "| Matched | n | MAE | Macro MAE | MAE reduction | Mean per-city skill |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in results["test_b_station_match"]:
        lines.append(
            f"| {row['station_matched']} | {row['n']} | "
            + " | ".join(number(row[key]) for key in (
                "mae", "macro_mae", "macro_mae_skill", "macro_skill"
            )) + " |"
        )
    if not any(row["station_matched"] and row["n"] for row in results["test_b_station_match"]):
        lines.extend(["", "No matched-station Test B rows (matched n = 0); 2025 uses city-level unmatched features."])
    totals = {
        split: sum(row["rows"] for row in results["suspect_exclusions"] if row["split"] == split)
        for split in ("train", "val", "test_a", "test_b")
    }
    lines.extend([
        "", "Suspect rows excluded: " + "; ".join(f"{split} {count}" for split, count in totals.items()) + ".",
        "", "Mean per-city skill is the arithmetic mean of each city's "
        "1 - city MAE / city persistence MAE. It differs from the headline "
        "MAE reduction, which uses the ratio of macro MAEs.",
    ])
    return "\n".join(lines) + "\n"
