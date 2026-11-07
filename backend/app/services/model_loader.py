"""Load and hold all backend assets for the application lifespan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


@dataclass(frozen=True)
class AssetStore:
    """An immutable reference to the loaded snapshot assets."""

    model: Any
    metadata: dict
    serving: pd.DataFrame
    history: pd.DataFrame
    backtest: pd.DataFrame
    results: dict
    drift: dict


def load_assets(directory: Path) -> AssetStore:
    """Read required assets once; raise a clear error if any is absent or invalid."""
    names = (
        "model.joblib", "metadata.json", "serving_features.parquet",
        "history.parquet", "backtest.parquet", "results.json", "drift_summary.json",
    )
    for name in names:
        if not (directory / name).is_file():
            raise FileNotFoundError(f"Required backend asset is missing: {name}")
    try:
        model = joblib.load(directory / "model.joblib")
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        serving = pd.read_parquet(directory / "serving_features.parquet")
        history = pd.read_parquet(directory / "history.parquet")
        backtest = pd.read_parquet(directory / "backtest.parquet")
        results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
        drift = json.loads((directory / "drift_summary.json").read_text(encoding="utf-8"))
        missing = set(metadata["features"]) - set(serving.columns)
        if missing:
            raise ValueError(f"Serving features missing model columns: {sorted(missing)}")
        if serving["city"].duplicated().any():
            raise ValueError("Serving features contain duplicate cities")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Backend asset could not be loaded: {exc}") from exc
    return AssetStore(model, metadata, serving, history, backtest, results, drift)
