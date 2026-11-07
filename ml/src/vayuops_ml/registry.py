"""Export selected model and bounded serving assets to the backend."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import joblib
import pandas as pd


def git_commit(root: Path) -> str | None:
    """Return HEAD when the project has a usable Git checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True, timeout=5,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def export_assets(
    root: Path,
    model: object,
    metadata: dict,
    serving_features: pd.DataFrame,
    clean: pd.DataFrame,
    backtest: pd.DataFrame,
    results: dict,
) -> list[Path]:
    """Write every backend asset and enforce a 10 MB limit per file."""
    assets = root / "backend" / "app" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    paths = {
        "model.joblib": assets / "model.joblib",
        "metadata.json": assets / "metadata.json",
        "serving_features.parquet": assets / "serving_features.parquet",
        "history.parquet": assets / "history.parquet",
        "backtest.parquet": assets / "backtest.parquet",
        "results.json": assets / "results.json",
    }
    joblib.dump(model, paths["model.joblib"])
    selected = metadata.get("selected_config") or {
        "model": metadata.get("model"),
        "params": metadata.get("params", {}),
    }
    persistence = metadata.get("persistence") or [
        row for row in results.get("model_metrics", [])
        if row.get("model") == "persistence"
    ]
    slim = {
        "selected_config": selected,
        "persistence": persistence,
        "summary_configs": metadata.get("summary_configs", results.get("summary_configs", [])),
        "split_dates": metadata.get("split_dates", results.get("split_dates", {})),
        "features": metadata["features"],
    }
    paths["metadata.json"].write_text(
        json.dumps(slim, indent=2, allow_nan=False), encoding="utf-8"
    )
    serving_features.to_parquet(paths["serving_features.parquet"], index=False)
    dates = pd.to_datetime(clean["date"])
    last = clean.assign(date=dates).groupby("city")["date"].transform("max")
    history = clean.loc[dates.ge(last - pd.Timedelta(days=399)), ["city", "date", "pm25"]]
    history.to_parquet(paths["history.parquet"], index=False)
    backtest.to_parquet(paths["backtest.parquet"], index=False)
    report_json = root / "reports" / "results.json"
    if report_json.exists():
        if json.loads(report_json.read_text(encoding="utf-8")) != results:
            raise ValueError("Registry results differ from reports/results.json")
        shutil.copyfile(report_json, paths["results.json"])
    else:
        paths["results.json"].write_text(
            json.dumps(results, indent=2, allow_nan=False), encoding="utf-8"
        )
    limit = 10 * 1024 * 1024
    too_large = [path for path in paths.values() if path.stat().st_size >= limit]
    if too_large:
        raise ValueError(f"Backend assets exceed 10 MB: {too_large}")
    return list(paths.values())

