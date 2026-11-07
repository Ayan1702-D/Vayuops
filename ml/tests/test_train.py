"""Training, evaluation, serving-feature, and registry fixtures."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from vayuops_ml.evaluate import metrics
from vayuops_ml.features import build_features, build_serving_features, feature_columns
from vayuops_ml.registry import export_assets
from vayuops_ml.train import PersistenceModel, make_model


def tiny_clean() -> pd.DataFrame:
    """Seven observed days with a changing next-day target."""
    dates = pd.date_range("2020-01-01", periods=7)
    return pd.DataFrame({
        "city": ["delhi"] * 7, "date": dates, "pm25": [10., 12., 15., 13., 17., 16., 20.],
        "pm10": [25.] * 7, "no2": [12.] * 7, "so2": [6.] * 7,
        "co": [1.] * 7, "o3": [18.] * 7,
        "source": ["cities_2020_2024"] * 7,
        "station_matched": pd.array([pd.NA] * 7, dtype="boolean"),
    })


def test_serving_row_matches_training_features() -> None:
    """The same calendar date has identical serving and training inputs."""
    clean = tiny_clean()
    serving = build_serving_features(clean)
    training = build_features(clean)
    reference = training.loc[training.date.eq(pd.Timestamp("2020-01-06"))].iloc[0]
    extended = build_serving_features(clean.loc[clean.date.le("2020-01-06")])
    for column in feature_columns():
        actual, expected = extended.iloc[0][column], reference[column]
        if pd.isna(expected):
            assert pd.isna(actual)
        elif column == "city":
            assert actual == expected
        else:
            assert actual == pytest.approx(expected)
    assert len(serving) == 1
    assert serving.iloc[0]["date"] == pd.Timestamp("2020-01-07")


def test_persistence_is_current_pm25() -> None:
    """The baseline uses day t, while the target is next calendar day."""
    frame = build_features(tiny_clean())
    predicted = PersistenceModel().predict(frame)
    assert predicted.iloc[0] == 10
    assert frame.iloc[0]["target"] == 12


def test_train_only_preprocessing_statistics() -> None:
    """Validation extremes cannot refit the median imputer or scaler."""
    columns = feature_columns()
    row = {name: 1.0 for name in columns if name != "city"}
    train_x = pd.DataFrame([{**row, "city": "delhi", "pm25_t": 1.0},
                            {**row, "city": "mumbai", "pm25_t": 3.0}])
    train_x.loc[0, "pm25_t_minus_1"] = float("nan")
    model = make_model("ridge", {"alpha": 1.0}, columns)
    model.fit(train_x[columns], pd.Series([2., 4.]))
    numeric = model.named_steps["preprocess"].named_transformers_["numeric"]
    before_median = numeric.named_steps["imputer"].statistics_.copy()
    before_mean = numeric.named_steps["scaler"].mean_.copy()
    validation = train_x.iloc[[0]].copy()
    validation["pm25_t"] = 1_000_000.
    model.predict(validation[columns])
    assert numeric.named_steps["imputer"].statistics_.tolist() == before_median.tolist()
    assert numeric.named_steps["scaler"].mean_.tolist() == before_mean.tolist()


def test_known_metrics() -> None:
    """MAE, RMSE, and persistence skill use matching examples."""
    result = metrics(pd.Series([2., 4.]), pd.Series([2., 3.]), pd.Series([1., 1.]))
    assert result["n"] == 2
    assert result["mae"] == pytest.approx(.5)
    assert result["rmse"] == pytest.approx(math.sqrt(.5))
    assert result["skill"] == pytest.approx(.75)


def test_registry_writes_every_asset(tmp_path: Path) -> None:
    """Export the six bounded files with metadata and history."""
    clean = tiny_clean()
    serving = build_serving_features(clean)
    backtest = pd.DataFrame({
        "city": ["delhi"], "date": [pd.Timestamp("2020-01-02")],
        "split": ["val"], "station_matched": [False],
        "y_true": [12.], "y_pred_best": [10.], "y_pred_persistence": [10.],
    })
    results = {"best_model": "persistence", "model_metrics": []}
    metadata = {"model": "persistence", "params": {}, "features": feature_columns(),
                "split_dates": {}, "metrics": []}
    paths = export_assets(
        tmp_path, PersistenceModel(), metadata, serving, clean, backtest, results
    )
    assert {path.name for path in paths} == {
        "model.joblib", "metadata.json", "serving_features.parquet",
        "history.parquet", "backtest.parquet", "results.json",
    }
    assert all(path.stat().st_size < 10 * 1024 * 1024 for path in paths)
    saved = json.loads((tmp_path / "backend/app/assets/metadata.json").read_text())
    assert saved["features"] == feature_columns()

