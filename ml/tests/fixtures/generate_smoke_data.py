"""Write a small synthetic clean table and training config for the pipeline smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def generate(root: Path) -> None:
    """Create observations in each production split, with no external inputs."""
    rows = []
    for city, offset in (("bengaluru", 0), ("delhi", 8)):
        for start in ("2023-10-01", "2024-02-01", "2024-08-01", "2025-02-01"):
            for day, date in enumerate(pd.date_range(start, periods=42)):
                pm25 = 25 + offset + 25 * (date.dayofweek % 2) + day % 5
                openaq = date.year == 2025
                rows.append({
                    "city": city,
                    "date": date,
                    "pm25": float(pm25),
                    "pm10": float(pm25 + 20),
                    "no2": 15.0 + day % 7,
                    "so2": 5.0 + day % 3,
                    "co": 0.5 + day % 4 / 10,
                    "o3": 20.0 + day % 6 + 8 * openaq,
                    "nh3": None if openaq else 9.0,
                    "source": "openaq_2025" if openaq else "cities_2020_2024",
                    "n_stations": 2 if openaq else None,
                    "station_matched": False if openaq else None,
                    "pm25_suspect": False,
                })

    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    clean = pd.DataFrame(rows).astype({"station_matched": "boolean", "n_stations": "Int64"})
    clean.to_parquet(processed / "clean.parquet", index=False)

    config = {
        "tracking_uri": "./mlruns",
        "experiment": "synthetic-smoke",
        "random_state": 42,
        "exclude_suspect": True,
        "bootstrap": {"block_days": 7, "resamples": 10, "seed": 42},
        "target_modes": ["level"],
        "enabled_groups": {"weather": False, "festival": False, "anomaly": False},
        "models": {
            "ridge": {"alpha": [1.0]},
            "lightgbm": {"n_estimators": [4], "num_leaves": [7], "objective": ["l2"]},
            "xgboost": {"n_estimators": [4], "max_depth": [2], "objective": ["l2"]},
        },
        "ablation_sets": {"base": []},
    }
    configs = root / "ml" / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    (configs / "train.yaml").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Isolated pipeline workspace")
    generate(parser.parse_args().root)
