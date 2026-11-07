"""Date-based splits for next-day PM2.5 prediction."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def split_by_target_date(
    features: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, tuple[pd.Timestamp, pd.Timestamp]], pd.DataFrame]:
    """Return ordered split frames, inclusive cutoffs, and per-city counts."""
    cutoffs = {
        "train": (pd.Timestamp("2020-01-02"), pd.Timestamp("2023-12-31")),
        "val": (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-30")),
        "test_a": (pd.Timestamp("2024-07-01"), pd.Timestamp("2024-12-31")),
        "test_b": (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
    }
    dates = pd.to_datetime(features["target_date"])
    splits = {}
    for name, (start, end) in cutoffs.items():
        selected = features.loc[dates.between(start, end)].copy()
        if name == "test_a" and "target_source" in selected:
            selected = selected.loc[selected["target_source"].eq("cities_2020_2024")].copy()
        if name == "test_b" and "target_source" in selected:
            selected = selected.loc[selected["target_source"].eq("openaq_2025")].copy()
        splits[name] = selected
    cities = sorted(features["city"].astype(str).unique())
    rows = []
    for name, frame in splits.items():
        for city in cities:
            city_rows = frame.loc[frame["city"].astype(str).eq(city)]
            if name == "test_b":
                matched = city_rows["target_station_matched"].fillna(False).astype(bool)
                for status in (True, False):
                    rows.append({
                        "split": name, "city": city, "station_matched": status,
                        "rows": int(matched.eq(status).sum()),
                    })
            else:
                rows.append({
                    "split": name, "city": city, "station_matched": pd.NA,
                    "rows": len(city_rows),
                })
    return splits, cutoffs, pd.DataFrame(rows)


def main(root: Path) -> pd.DataFrame:
    """Print and save split cutoffs and city counts."""
    features = pd.read_parquet(root / "data" / "processed" / "features.parquet")
    splits, cutoffs, counts = split_by_target_date(features)
    for name, (start, end) in cutoffs.items():
        print(f"{name}: {start:%Y-%m-%d} to {end:%Y-%m-%d}, rows={len(splits[name]):,}")
    print(counts.to_string(index=False))
    output = root / "reports" / "split_counts.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    counts.to_csv(output, index=False)
    return counts


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[3])

