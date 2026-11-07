"""Tests for macro evaluation, uncertainty, optional features, and exclusions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from vayuops_ml.evaluate import moving_block_bootstrap, score_predictions
from vayuops_ml.features import (
    add_anomaly_feature, add_festival_features, add_weather_features,
    fit_anomaly_lookup, load_festival_dates,
)
from vayuops_ml.train import (
    assert_fit_consistency, candidate_grid, exclude_suspect_rows, mark_unstable,
    model_target, predict_level, summary_config_rows,
)


def test_fit_scope_identical_across_candidates() -> None:
    """Every configuration has train validation and train+val tests."""
    rows = [
        {"model": model, "split": split, "Fit": scope}
        for model in ("ridge", "lightgbm", "xgboost", "persistence")
        for split, scope in (("val", "train"), ("test_a", "train+val"), ("test_b", "train+val"))
    ]
    assert_fit_consistency(rows)
    with pytest.raises(ValueError, match="inconsistent"):
        assert_fit_consistency(rows + [{"model": "bad", "split": "test_b", "Fit": "train"}])


def test_block_bootstrap_reproducible_and_contains_estimate() -> None:
    """Paired resampling uses a fixed seed and includes the observed estimate."""
    days = pd.date_range("2024-01-01", periods=35)
    frame = pd.DataFrame({
        "city": ["delhi"] * len(days), "date": days,
        "y_true": np.arange(35, dtype=float) + 10,
        "y_pred": np.arange(35, dtype=float) + 9,
        "y_persistence": np.arange(35, dtype=float) + 7,
    })
    first = moving_block_bootstrap(frame, 14, 1000, 42)
    second = moving_block_bootstrap(frame, 14, 1000, 42)
    assert first == second
    assert first["ci_low"] <= first["estimate"] <= first["ci_high"]


class PerfectDelta:
    """Return a known delta for a tiny round-trip example."""

    def __init__(self, delta: float) -> None:
        self.delta = delta

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return np.full(len(x), self.delta)


def test_delta_log_round_trip() -> None:
    """An exact log delta recovers the next-day PM2.5 level."""
    frame = pd.DataFrame({"pm25_t": [10.], "target": [25.], "city": ["delhi"]})
    delta = model_target(frame, "delta_log").iloc[0]
    predicted = predict_level(PerfectDelta(delta), frame, ["pm25_t", "city"], "delta_log")
    assert predicted.iloc[0] == pytest.approx(25.)


def test_weather_future_change_leaves_earlier_features_alone() -> None:
    """Trailing weather windows never include later dates."""
    days = pd.date_range("2024-01-01", periods=5)
    rows = pd.DataFrame({"city": ["delhi"] * 5, "date": days})
    weather = pd.DataFrame({
        "city": ["delhi"] * 5, "date": days,
        "temperature_2m_mean": [1., 2., 3., 4., 5.],
        "relative_humidity_2m_mean": [1.] * 5,
        "wind_speed_10m_mean": [1.] * 5,
        "wind_direction_10m_dominant": [90.] * 5,
        "precipitation_sum": [1.] * 5,
        "surface_pressure_mean": [1000.] * 5,
    })
    before = add_weather_features(rows, weather)
    changed = weather.copy()
    changed.loc[changed.date.gt("2024-01-03"), "temperature_2m_mean"] = 1000.
    after = add_weather_features(rows, changed)
    columns = [column for column in before if column.startswith("weather_")]
    pd.testing.assert_frame_equal(before.loc[:2, columns], after.loc[:2, columns])


def test_festival_windows_cover_2020_to_2025() -> None:
    """Every cited Diwali date and its nearby days receive a window flag."""
    root = Path(__file__).resolve().parents[1]
    dates = load_festival_dates(root / "configs" / "festivals.yaml")
    assert set(dates) == set(range(2020, 2026))
    rows = pd.DataFrame({
        "date": [day + pd.Timedelta(days=offset) for day in dates.values() for offset in (-5, 0, 7)],
        "city": ["delhi"] * 18,
    })
    result = add_festival_features(rows, dates)
    assert result["is_diwali_window"].eq(1).all()
    assert result["days_from_diwali"].tolist() == [-5., 0., 7.] * 6


def test_anomaly_lookup_fits_train_only() -> None:
    """Changing a test value cannot alter the frozen city-month median."""
    train = pd.DataFrame({
        "city": ["delhi"] * 3, "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
        "pm25_t": [10., 20., 30.],
    })
    lookup = fit_anomaly_lookup(train)
    test = pd.DataFrame({"city": ["delhi"], "date": [pd.Timestamp("2024-01-01")], "pm25_t": [100.]})
    first = add_anomaly_feature(test, lookup)["pm25_anomaly"].iloc[0]
    test["pm25_t"] = 100000.
    second = add_anomaly_feature(test, lookup)["pm25_anomaly"].iloc[0]
    assert lookup["city_month_pm25_median"].iloc[0] == 20.
    assert first == 80.
    assert second == 99980.


def test_suspect_rows_excluded_from_each_split() -> None:
    """Rows flagged at t or t+1 leave both training and evaluation."""
    frame = pd.DataFrame({
        "city": ["delhi"] * 3, "suspect_t": [False, True, False],
        "suspect_target": [False, False, True], "target": [1., 2., 3.],
    })
    filtered, counts = exclude_suspect_rows({"train": frame, "val": frame}, True)
    assert len(filtered["train"]) == len(filtered["val"]) == 1
    assert counts["rows"].tolist() == [2, 2]


def test_macro_selection_differs_from_pooled() -> None:
    """City-macro scores give each city equal weight."""
    frame = pd.DataFrame({
        "city": ["a"] * 10 + ["b"],
        "y_true": [10.] * 11,
        "y_pred": [9.] * 10 + [5.],
        "y_persistence": [8.] * 11,
    })
    result = score_predictions(frame)
    assert result["macro_mae"] == pytest.approx(3.)
    assert result["mae"] == pytest.approx(15 / 11)


def test_config_grids_at_most_twelve() -> None:
    """The configured grids stay within the requested cap."""
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "configs" / "train.yaml").read_text())
    candidates = candidate_grid(cfg)
    for name in ("ridge", "lightgbm", "xgboost"):
        assert sum(candidate["model"] == name for candidate in candidates) <= 12



def test_unstable_config_excluded_from_selection_summary() -> None:
    """A >2x validation MAE remains detailed but cannot be summarized."""
    assert mark_unstable({"mae": 21.}, 10.)["unstable"]
    assert not mark_unstable({"mae": 20.}, 10.)["unstable"]
    rows = []
    for config_id, unstable, mae in (("ridge-good", False, 9.), ("ridge-bad", True, 1.)):
        for split in ("val", "test_a", "test_b"):
            rows.append({
                "model": "ridge", "config_id": config_id, "split": split,
                "unstable": unstable, "macro_mae": mae,
                "macro_skill": .1, "macro_mae_skill": .1,
                "target_mode": "level", "objective": "none", "params": {"alpha": 1.},
            })
    summary = summary_config_rows(rows, ["weather"], "ridge-good")
    assert len(summary) == 1
    assert summary[0]["config_id"] == "ridge-good"


def test_delta_log_clipping_bounds() -> None:
    """Large deltas and the city train maximum bound the inverse transform."""
    class Extreme:
        def predict(self, x: pd.DataFrame) -> np.ndarray:
            return np.array([100., -100.])

    frame = pd.DataFrame({"city": ["delhi", "delhi"], "pm25_t": [10., 0.]})
    predicted = predict_level(
        Extreme(), frame, ["city", "pm25_t"], "delta_log", {"delhi": 20.}
    )
    assert predicted.tolist() == pytest.approx([30., 0.])


def test_summary_has_unique_model_config_rows() -> None:
    """A family appears only once even when every split has a metric row."""
    rows = []
    for family in ("persistence", "ridge"):
        for split in ("val", "test_a", "test_b"):
            rows.append({
                "model": family, "config_id": family + "-best", "split": split,
                "unstable": False, "macro_mae": 2.,
                "macro_skill": 0., "macro_mae_skill": 0.,
                "target_mode": "level", "objective": "none", "params": {},
            })
    summary = summary_config_rows(rows, [], "ridge-best")
    assert len(summary) == 2
    assert len({(row["model"], row["config_id"]) for row in summary}) == len(summary)
