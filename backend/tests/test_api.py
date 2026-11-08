"""Contract tests for the static VayuOps API."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.dummy import DummyRegressor

from app.config import Settings
from app.main import create_app


@pytest.fixture
def assets(tmp_path: Path) -> Path:
    """Write a complete serving snapshot from invented measurements."""
    day = pd.Timestamp("2025-01-01")
    serving = pd.DataFrame({"city": ["bengaluru"], "date": [day], "pm25_t": [20.0]})
    serving.to_parquet(tmp_path / "serving_features.parquet", index=False)
    model = DummyRegressor().fit(serving[["pm25_t"]], [23.0])
    joblib.dump(model, tmp_path / "model.joblib")

    serving.rename(columns={"pm25_t": "pm25"}).to_parquet(tmp_path / "history.parquet", index=False)
    serving[["city", "date"]].assign(
        split="test_a", station_matched=False, y_true=23.0, y_pred_best=23.0,
        y_pred_persistence=20.0,
    ).to_parquet(tmp_path / "backtest.parquet", index=False)

    selected = {"model": "dummy", "config_id": "synthetic", "target_mode": "level"}
    documents = {
        "metadata.json": {"selected_config": selected, "features": ["pm25_t"]},
        "results.json": {
            "best_model": "dummy", "summary_configs": [selected], "model_metrics": [],
            "split_dates": {},
        },
        "drift_summary.json": {
            "method": "synthetic", "reference_period": {}, "comparisons": {
                "test_a": {"status": "no_drift"}, "test_b": {"status": "no_drift"},
            },
        },
    }
    for name, content in documents.items():
        (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    return tmp_path


def test_every_endpoint(assets: Path) -> None:
    with TestClient(create_app(Settings(assets_dir=assets))) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["model_name"]
        assert health.json()["model_version"]
        assert health.json()["data_as_of_date"]
        assert health.headers["cache-control"] == "no-store"

        cities = client.get("/cities")
        assert cities.status_code == 200
        city = cities.json()["cities"][0]
        assert city == "bengaluru"
        assert cities.headers["cache-control"] == "public, max-age=300"

        forecast = client.get("/forecast", params={"city": city})
        assert forecast.status_code == 200
        prediction = forecast.json()
        assert prediction["city"] == city
        assert prediction["pm25_forecast"] == 23.0
        assert prediction["label"] == "static data snapshot"
        assert date.fromisoformat(prediction["target_date"]) == (
            date.fromisoformat(prediction["as_of_date"]) + timedelta(days=1)
        )

        history = client.get("/history", params={"city": city, "days": 7})
        assert history.status_code == 200
        assert history.json()["city"] == city
        assert 1 <= len(history.json()["rows"]) <= 7
        assert {"date", "pm25"} <= history.json()["rows"][0].keys()

        backtest = client.get("/backtest", params={"city": city, "split": "test_a"})
        assert backtest.status_code == 200
        assert backtest.json()["rows"]
        assert {"date", "y_true", "y_pred_best", "y_pred_persistence"} <= (
            backtest.json()["rows"][0].keys()
        )

        models = client.get("/models")
        assert models.status_code == 200
        assert models.json()["selected_config"]["model"] == health.json()["model_name"]
        assert models.json()["summary_configs"]

        drift = client.get("/drift")
        assert drift.status_code == 200
        assert set(drift.json()["comparisons"]) == {"test_a", "test_b"}


def test_unknown_city_and_validation_error(assets: Path) -> None:
    with TestClient(create_app(Settings(assets_dir=assets))) as client:
        unknown = client.get("/forecast", params={"city": "unknown"})
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "unknown_city"
        assert unknown.headers["cache-control"] == "no-store"
        invalid = client.get("/history", params={"city": "bengaluru", "days": 0})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"


def test_missing_asset_returns_503(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(assets_dir=tmp_path))) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "asset_unavailable"
        assert "model.joblib" in response.json()["error"]["message"]


def test_cors_origins_from_environment(monkeypatch: pytest.MonkeyPatch, assets: Path) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://example.org,https://example.com")
    with TestClient(create_app(Settings(assets_dir=assets))) as client:
        response = client.get("/cities", headers={"Origin": "https://example.org"})
        assert response.headers["access-control-allow-origin"] == "https://example.org"
