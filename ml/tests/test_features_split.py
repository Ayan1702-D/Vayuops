"""Leakage, calendar alignment, fill, and split fixtures."""

from __future__ import annotations

import pandas as pd

from vayuops_ml.features import build_features, feature_columns
from vayuops_ml.split import split_by_target_date


def frame_for_city(city: str, dates: list[str], values: list[float | None]) -> pd.DataFrame:
    """Build a small clean input for one city."""
    return pd.DataFrame({
        "city": city, "date": pd.to_datetime(dates), "pm25": values,
        "pm10": [20.0] * len(dates), "no2": [10.0] * len(dates),
        "so2": [5.0] * len(dates), "co": [1.0] * len(dates),
        "o3": [12.0] * len(dates), "source": ["cities_2020_2024"] * len(dates),
        "station_matched": pd.array([pd.NA] * len(dates), dtype="boolean"),
    })


def test_missing_day_lag_alignment() -> None:
    """Lag one refers to the previous calendar day, including a gap."""
    data = frame_for_city("delhi", ["2020-01-01", "2020-01-03", "2020-01-04"], [10, 30, 40])
    features = build_features(data).set_index("date")
    assert features.loc[pd.Timestamp("2020-01-02"), "pm25_t"] == 10
    assert features.loc[pd.Timestamp("2020-01-03"), "pm25_t_minus_1"] == 10
    assert features.loc[pd.Timestamp("2020-01-03"), "target"] == 40


def test_future_changes_do_not_change_earlier_features() -> None:
    """Changing later measurements changes targets but not earlier inputs."""
    dates = pd.date_range("2020-01-01", periods=20).strftime("%Y-%m-%d").tolist()
    base = frame_for_city("delhi", dates, [float(i) for i in range(20)])
    changed = base.copy()
    changed.loc[changed.date.ge("2020-01-11"), ["pm25", "pm10", "no2", "so2", "co", "o3"]] = 999
    original_features = build_features(base).set_index("date")
    changed_features = build_features(changed).set_index("date")
    columns = [name for name in feature_columns() if name != "city"]
    pd.testing.assert_frame_equal(
        original_features.loc[original_features.index <= pd.Timestamp("2020-01-10"), columns],
        changed_features.loc[changed_features.index <= pd.Timestamp("2020-01-10"), columns],
    )


def test_no_nh3_or_future_feature() -> None:
    """Only current and past measurements appear in model inputs."""
    assert all("nh3" not in name and not name.endswith("_next") for name in feature_columns())


def test_forward_fill_limit_and_city_boundary() -> None:
    """A fourth missing day stays empty and another city's values never leak."""
    dates = pd.date_range("2020-01-01", periods=11).strftime("%Y-%m-%d").tolist()
    delhi = frame_for_city("delhi", dates, [10, None, None, None, 20, None, None, None, None, 30, 40])
    mumbai = frame_for_city("mumbai", dates, [100] * 11)
    features = build_features(pd.concat([delhi, mumbai], ignore_index=True))
    delhi_features = features.loc[features.city.eq("delhi")].set_index("date")
    assert pd.Timestamp("2020-01-04") in delhi_features.index
    assert delhi_features.loc[pd.Timestamp("2020-01-04"), "pm25_t"] == 10
    assert pd.Timestamp("2020-01-09") not in delhi_features.index
    assert delhi_features["pm25_t"].max() <= 30


def test_split_ranges_ordered_and_disjoint() -> None:
    """Inclusive target-date ranges do not overlap or randomize."""
    dates = pd.to_datetime(["2023-12-31", "2024-01-01", "2024-06-30",
                            "2024-07-01", "2024-12-31", "2025-01-01", "2025-12-31"])
    data = pd.DataFrame({
        "city": ["delhi"] * len(dates), "target_date": dates,
        "target_source": ["cities_2020_2024"] * 5 + ["openaq_2025"] * 2,
        "target_station_matched": pd.array([pd.NA] * 5 + [True, False], dtype="boolean"),
    })
    splits, cutoffs, counts = split_by_target_date(data)
    assert [len(splits[name]) for name in ("train", "val", "test_a", "test_b")] == [1, 2, 2, 2]
    ordered = list(cutoffs.values())
    assert all(left[1] < right[0] for left, right in zip(ordered, ordered[1:]))
    assert counts.loc[counts.split.eq("test_b"), "rows"].tolist() == [1, 1]

