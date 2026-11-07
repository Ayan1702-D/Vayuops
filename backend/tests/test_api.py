"""Contract tests for the static VayuOps API."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


ASSETS = Path(__file__).resolve().parents[1] / "app" / "assets"


def test_every_endpoint() -> None:
    with TestClient(create_app(Settings(assets_dir=ASSETS))) as client:
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
        assert prediction["pm25_forecast"] >= 0
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


def test_unknown_city_and_validation_error() -> None:
    with TestClient(create_app(Settings(assets_dir=ASSETS))) as client:
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


def test_cors_origins_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://example.org,https://example.com")
    with TestClient(create_app(Settings(assets_dir=ASSETS))) as client:
        response = client.get("/cities", headers={"Origin": "https://example.org"})
        assert response.headers["access-control-allow-origin"] == "https://example.org"
