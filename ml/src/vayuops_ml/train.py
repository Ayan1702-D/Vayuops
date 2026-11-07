"""Config-driven model grids, city-macro selection, uncertainty, and ablations."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import lightgbm as lgb
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import ParameterGrid
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from vayuops_ml.evaluate import (
    markdown_results, metrics, monthly_errors, moving_block_bootstrap, score_predictions,
)
from vayuops_ml.features import (
    add_anomaly_feature, add_festival_features, add_weather_features, build_features,
    build_serving_features, feature_columns, fit_anomaly_lookup, load_festival_dates,
    weather_feature_columns,
)
from vayuops_ml.registry import export_assets
from vayuops_ml.split import split_by_target_date
from vayuops_ml.weather import load_weather


class PersistenceModel(RegressorMixin, BaseEstimator):
    """Predict tomorrow's PM2.5 from today's value."""

    def fit(self, x: pd.DataFrame, y: pd.Series) -> PersistenceModel:
        """Return the parameter-free baseline."""
        return self

    def predict(self, x: pd.DataFrame) -> pd.Series:
        """Return today's PM2.5."""
        return pd.to_numeric(x["pm25_t"], errors="coerce")


def make_model(name: str, params: dict, columns: list[str], random_state: int = 42) -> object:
    """Create preprocessing and a fresh estimator for one grid configuration."""
    if name == "persistence":
        return PersistenceModel()
    numeric = [column for column in columns if column != "city"]
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if name == "ridge":
        steps.append(("scaler", StandardScaler()))
    preprocess = ColumnTransformer(
        [
            ("numeric", Pipeline(steps), numeric),
            ("city", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["city"]),
        ],
        sparse_threshold=0,
    )
    model_params = {key: value for key, value in params.items() if key != "objective"}
    if name == "ridge":
        estimator = Ridge(**model_params)
    elif name == "lightgbm":
        objectives = {"l2": "regression", "l1": "regression_l1", "huber": "huber"}
        estimator = lgb.LGBMRegressor(
            random_state=random_state, n_jobs=2, verbosity=-1,
            objective=objectives[params["objective"]], **model_params,
        )
    elif name == "xgboost":
        objectives = {
            "l2": "reg:squarederror", "l1": "reg:absoluteerror",
            "huber": "reg:pseudohubererror",
        }
        estimator = XGBRegressor(
            random_state=random_state, n_jobs=2, verbosity=0,
            objective=objectives[params["objective"]], **model_params,
        )
    else:
        raise ValueError(f"Unknown model: {name}")
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def model_target(frame: pd.DataFrame, mode: str) -> pd.Series:
    """Return the configured training target."""
    if mode == "level":
        return frame["target"].astype(float)
    if mode == "delta_log":
        return np.log1p(frame["target"].astype(float)) - np.log1p(frame["pm25_t"].astype(float))
    raise ValueError(f"Unknown target mode: {mode}")


def predict_level(
    model: object, frame: pd.DataFrame, columns: list[str], mode: str,
    train_city_max: dict[str, float] | None = None,
) -> pd.Series:
    """Convert a model output back to nonnegative PM2.5 levels."""
    raw = np.asarray(model.predict(frame[columns]), dtype=float)
    if mode == "delta_log":
        delta = np.clip(raw, -2, 2)
        raw = np.expm1(np.log1p(frame["pm25_t"].to_numpy(dtype=float)) + delta)
        if train_city_max is not None:
            upper = frame["city"].astype(str).map(train_city_max).to_numpy(dtype=float) * 1.5
            if np.isnan(upper).any():
                raise ValueError("Missing train PM2.5 maximum for a prediction city")
            raw = np.clip(raw, 0, upper)
        else:
            raw = np.clip(raw, 0, None)
    return pd.Series(raw, index=frame.index, dtype=float)


def comparison_frame(frame: pd.DataFrame, predictions: pd.Series) -> pd.DataFrame:
    """Align observed values, model predictions, and persistence predictions."""
    return pd.DataFrame({
        "city": frame["city"].astype(str).to_numpy(),
        "date": pd.to_datetime(frame["target_date"]).to_numpy(),
        "station_matched": frame["target_station_matched"].fillna(False).astype(bool).to_numpy(),
        "y_true": frame["target"].to_numpy(dtype=float),
        "y_pred": predictions.to_numpy(dtype=float),
        "y_persistence": frame["pm25_t"].to_numpy(dtype=float),
    })


def candidate_grid(cfg: dict) -> list[dict]:
    """Expand each fixed grid without exceeding twelve combinations per model."""
    candidates = [{"model": "persistence", "target_mode": "level", "params": {}, "objective": "none"}]
    for name, grid in cfg["models"].items():
        combinations = list(ParameterGrid(grid))
        total = len(combinations) * len(cfg["target_modes"])
        if total > 12:
            raise ValueError(f"{name} has {total} combinations; maximum is 12")
        for mode in cfg["target_modes"]:
            for params in combinations:
                candidates.append({
                    "model": name, "target_mode": mode, "params": params,
                    "objective": params.get("objective", "none"),
                })
    for index, candidate in enumerate(candidates):
        candidate["config_id"] = f"{candidate['model']}-{index:02d}-{candidate['target_mode']}-{candidate['objective']}"
    return candidates


def group_columns(groups: list[str]) -> list[str]:
    """Select base features plus configured optional groups."""
    columns = feature_columns()
    if "weather" in groups:
        columns += weather_feature_columns()
    if "festival" in groups:
        columns += ["days_from_diwali", "is_diwali_window"]
    if "anomaly" in groups:
        columns += ["pm25_anomaly"]
    return columns


def train_city_maximum(train_frame: pd.DataFrame) -> dict[str, float]:
    """Freeze each city's largest observed train PM2.5 level."""
    grouped = train_frame.groupby("city", observed=True)
    return {
        str(city): float(max(group["pm25_t"].max(), group["target"].max()))
        for city, group in grouped
    }


def mark_unstable(row: dict, persistence_mae: float, multiplier: float = 2.0) -> dict:
    """Mark a validation configuration with excessive pooled MAE."""
    return {**row, "unstable": bool(row["mae"] > multiplier * persistence_mae)}


def summary_config_rows(
    model_metrics: list[dict], groups: list[str], selected_config_id: str,
) -> list[dict]:
    """Keep one stable validation winner per family, with test macro scores."""
    rows = []
    for family in ("persistence", "ridge", "lightgbm", "xgboost"):
        eligible = [
            row for row in model_metrics
            if row["model"] == family and row["split"] == "val" and not row["unstable"]
        ]
        if not eligible:
            continue
        best = min(eligible, key=lambda row: row["macro_mae"])
        tests = {
            row["split"]: row for row in model_metrics
            if row["config_id"] == best["config_id"] and row["split"] in ("test_a", "test_b")
        }
        rows.append({
            "model": family, "config_id": best["config_id"],
            "target_mode": best["target_mode"], "objective": best["objective"],
            "feature_groups": groups, "key_params": json.dumps(best["params"], sort_keys=True),
            "selected": best["config_id"] == selected_config_id,
            "val_macro_mae": best["macro_mae"], "val_macro_skill": best["macro_skill"],
            "val_macro_mae_skill": best["macro_mae_skill"],
            "test_a_macro_mae": tests["test_a"]["macro_mae"],
            "test_a_macro_mae_skill": tests["test_a"]["macro_mae_skill"],
            "test_a_macro_skill": tests["test_a"]["macro_skill"],
            "test_b_macro_mae": tests["test_b"]["macro_mae"],
            "test_b_macro_mae_skill": tests["test_b"]["macro_mae_skill"],
            "test_b_macro_skill": tests["test_b"]["macro_skill"],
        })
    if len(rows) > 12 or len({(row["model"], row["config_id"]) for row in rows}) != len(rows):
        raise ValueError("Summary must contain unique model/config rows and at most 12 rows")
    return rows


def grid_results_frame(rows: list[dict], groups: list[str]) -> pd.DataFrame:
    """Flatten all candidate/split/fit metrics for the detailed CSV."""
    flattened = []
    for row in rows:
        params = row["params"]
        flattened.append({
            "model": row["model"], "config_id": row["config_id"],
            "split": row["split"], "Fit": row["Fit"],
            "target_mode": row["target_mode"], "objective": row["objective"],
            "feature_groups": ",".join(groups), "unstable": row["unstable"],
            "mae_reduction": row["macro_mae_skill"],
            **{key: params.get(key) for key in (
                "alpha", "n_estimators", "num_leaves", "max_depth", "learning_rate"
            )},
            **{key: row[key] for key in (
                "n", "cities", "mae", "rmse", "skill", "rmse_skill",
                "macro_mae", "macro_rmse", "macro_skill",
                "macro_rmse_skill", "macro_mae_skill"
            )},
        })
    result = pd.DataFrame(flattened)
    if result.duplicated(["config_id", "split", "Fit"]).any():
        raise ValueError("Duplicate config/split/fit rows in grid results")
    return result


def _fit(candidate: dict, frame: pd.DataFrame, columns: list[str], cfg: dict) -> object:
    model = make_model(candidate["model"], candidate["params"], columns, cfg["random_state"])
    model.fit(frame[columns], model_target(frame, candidate["target_mode"]))
    return model


def _metric_row(candidate: dict, split: str, fit_scope: str, frame: pd.DataFrame) -> dict:
    return {
        "model": candidate["model"], "config_id": candidate["config_id"],
        "target_mode": candidate["target_mode"], "objective": candidate["objective"],
        "params": candidate["params"], "split": split, "Fit": fit_scope,
        **score_predictions(frame),
    }


def _log_metrics(prefix: str, score: dict) -> None:
    mlflow.log_metrics({
        f"{prefix}_{key}": float(value) for key, value in score.items()
        if key in ("mae", "rmse", "skill", "rmse_skill", "macro_mae", "macro_rmse", "macro_skill", "macro_rmse_skill", "macro_mae_skill")
        and value is not None
    })


def exclude_suspect_rows(
    splits: dict[str, pd.DataFrame], enabled: bool
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Remove rows flagged at day t or target day and count removals by city."""
    if not enabled:
        return splits, pd.DataFrame(columns=["split", "city", "rows"])
    filtered = {}
    exclusions = []
    for split, frame in splits.items():
        suspect = frame["suspect_t"].fillna(False) | frame["suspect_target"].fillna(False)
        for city, group in frame.assign(_suspect=suspect).groupby("city", observed=True):
            count = int(group["_suspect"].sum())
            exclusions.append({"split": split, "city": str(city), "rows": count})
            logging.info("Excluded suspect rows %s %s: %d", split, city, count)
        filtered[split] = frame.loc[~suspect].copy()
    return filtered, pd.DataFrame(exclusions)


def assert_fit_consistency(rows: list[dict]) -> None:
    """Require the same training scope for every model within each split."""
    expected = {"val": "train", "test_a": "train+val", "test_b": "train+val"}
    for split, scope in expected.items():
        observed = {row["Fit"] for row in rows if row["split"] == split}
        if observed != {scope}:
            raise ValueError(f"{split} has inconsistent Fit values: {observed}")


def _prepare(root: Path, cfg: dict) -> tuple[dict[str, pd.DataFrame], dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clean = pd.read_parquet(root / "data" / "processed" / "clean.parquet")
    features = build_features(clean)
    features.to_parquet(root / "data" / "processed" / "features.parquet", index=False)
    need_weather = cfg["enabled_groups"].get("weather") or any(
        "weather" in groups for groups in cfg["ablation_sets"].values()
    )
    weather = load_weather(root, cfg) if need_weather else pd.DataFrame()
    if need_weather:
        features = add_weather_features(features, weather)
    if cfg["enabled_groups"].get("festival") or any(
        "festival" in groups for groups in cfg["ablation_sets"].values()
    ):
        festival_dates = load_festival_dates(root / "ml" / "configs" / "festivals.yaml")
        features = add_festival_features(features, festival_dates)
    splits, cutoffs, _ = split_by_target_date(features)
    splits, exclusions = exclude_suspect_rows(splits, cfg["exclude_suspect"])
    if any(frame.empty for frame in splits.values()):
        raise ValueError("A configured split is empty after suspect exclusion")
    lookup = fit_anomaly_lookup(splits["train"])
    if cfg["enabled_groups"].get("anomaly") or any(
        "anomaly" in groups for groups in cfg["ablation_sets"].values()
    ):
        splits = {name: add_anomaly_feature(frame, lookup) for name, frame in splits.items()}
    return splits, cutoffs, exclusions, clean, lookup


def train(root: Path) -> dict:
    """Select by validation macro MAE, refit all candidates, and export reports."""
    cfg = json.loads((root / "ml" / "configs" / "train.yaml").read_text(encoding="utf-8-sig"))
    splits, cutoffs, exclusions, clean, lookup = _prepare(root, cfg)
    active_groups = [name for name, enabled in cfg["enabled_groups"].items() if enabled]
    columns = group_columns(active_groups)
    candidates = candidate_grid(cfg)
    train_frame, val_frame = splits["train"], splits["val"]
    city_max = train_city_maximum(train_frame)
    persistence_mae = float((val_frame["target"] - val_frame["pm25_t"]).abs().mean())
    train_val = pd.concat([train_frame, val_frame], ignore_index=True)
    mlflow.set_tracking_uri((root / cfg["tracking_uri"]).resolve().as_uri())
    mlflow.set_experiment(cfg["experiment"])
    val_rows = []
    val_predictions = {}
    for candidate in candidates:
        model = _fit(candidate, train_frame, columns, cfg)
        prediction = predict_level(
            model, val_frame, columns, candidate["target_mode"], city_max
        )
        scored = comparison_frame(val_frame, prediction)
        row = mark_unstable(
            _metric_row(candidate, "val", "train", scored), persistence_mae
        )
        candidate["unstable"] = row["unstable"]
        val_rows.append(row)
        val_predictions[candidate["config_id"]] = scored
        with mlflow.start_run(run_name=f"{candidate['config_id']}-val"):
            mlflow.log_params({
                "model": candidate["model"], "target_mode": candidate["target_mode"],
                "objective": candidate["objective"], "config_id": candidate["config_id"],
                **candidate["params"], "Fit": "train",
            })
            _log_metrics("val", row)
        logging.info("%s val macro MAE %.3f", candidate["config_id"], row["macro_mae"])
    best_row = min(
        (row for row in val_rows if not row["unstable"]),
        key=lambda row: row["macro_mae"],
    )
    best = next(candidate for candidate in candidates if candidate["config_id"] == best_row["config_id"])
    best_lightgbm = min(
        (row for row in val_rows if row["model"] == "lightgbm" and not row["unstable"]),
        key=lambda row: row["macro_mae"],
    )
    lightgbm_candidate = next(
        candidate for candidate in candidates if candidate["config_id"] == best_lightgbm["config_id"]
    )
    model_metrics = list(val_rows)
    best_model = None
    best_frames = [val_predictions[best["config_id"]].assign(split="val")]
    for candidate in candidates:
        model = _fit(candidate, train_val, columns, cfg)
        with mlflow.start_run(run_name=f"{candidate['config_id']}-refit"):
            mlflow.log_params({
                "model": candidate["model"], "target_mode": candidate["target_mode"],
                "objective": candidate["objective"], "config_id": candidate["config_id"],
                **candidate["params"], "Fit": "train+val",
            })
            for split_name in ("test_a", "test_b"):
                frame = splits[split_name]
                prediction = predict_level(
                    model, frame, columns, candidate["target_mode"], city_max
                )
                scored = comparison_frame(frame, prediction)
                row = {
                    **_metric_row(candidate, split_name, "train+val", scored),
                    "unstable": candidate["unstable"],
                }
                model_metrics.append(row)
                _log_metrics(split_name, row)
                if candidate["config_id"] == best["config_id"]:
                    best_frames.append(scored.assign(split=split_name))
            mlflow.sklearn.log_model(sk_model=model, name="model")
        if candidate["config_id"] == best["config_id"]:
            best_model = model
    assert_fit_consistency(model_metrics)
    backtest = pd.concat(best_frames, ignore_index=True)
    backtest = backtest.rename(columns={
        "y_pred": "y_pred_best", "y_persistence": "y_pred_persistence"
    })
    boot_cfg = cfg["bootstrap"]
    bootstrap = {}
    per_city = []
    for split_name, group in backtest.groupby("split", sort=False):
        comparable = group.rename(columns={
            "y_pred_best": "y_pred", "y_pred_persistence": "y_persistence"
        })
        bootstrap[split_name] = moving_block_bootstrap(
            comparable, boot_cfg["block_days"], boot_cfg["resamples"], boot_cfg["seed"]
        )
        for city, city_frame in comparable.groupby("city"):
            per_city.append({
                "split": split_name, "city": city,
                **metrics(city_frame.y_true, city_frame.y_pred, city_frame.y_persistence),
            })
    matched = []
    test_b = backtest.loc[backtest.split.eq("test_b")]
    for status in (True, False):
        group = test_b.loc[test_b.station_matched.eq(status)].rename(columns={
            "y_pred_best": "y_pred", "y_pred_persistence": "y_persistence"
        })
        matched.append({"station_matched": status, **score_predictions(group)})
    findings = [
        f"Selected {best['config_id']} ({best['target_mode']}, {best['objective']}; "
        f"params {json.dumps(best['params'], sort_keys=True)}; groups "
        f"{', '.join(active_groups) or 'base'}) by validation macro MAE."
    ]
    for split_name in ("val", "test_a", "test_b"):
        interval = bootstrap[split_name]
        selected_row = next(
            row for row in model_metrics
            if row["config_id"] == best["config_id"] and row["split"] == split_name
        )
        baseline_row = next(
            row for row in model_metrics
            if row["model"] == "persistence" and row["split"] == split_name
        )
        mae_reduction = selected_row["macro_mae_skill"]
        rmse_reduction = baseline_row["rmse"] - selected_row["rmse"]
        findings.append(
            f"{split_name}: headline MAE reduction {mae_reduction:.1%} "
            f"(1 - macro MAE / persistence macro MAE); paired MAE difference "
            f"95% interval [{interval['ci_low']:.2f}, {interval['ci_high']:.2f}] "
            f"{'excludes' if interval['excludes_zero'] else 'includes'} zero; "
            f"pooled RMSE reduction {rmse_reduction:.2f}."
        )
    for split_name in ("val", "test_a"):
        worse = sorted(
            row["city"] for row in per_city
            if row["split"] == split_name and row["skill"] is not None and row["skill"] < 0
        )
        findings.append(
            f"Cities worse than persistence on {split_name}: "
            f"{', '.join(worse) if worse else 'none'}."
        )
    findings.append("Test B used city-level unmatched 2025 features; matched-station n is 0.")
    summary_configs = summary_config_rows(model_metrics, active_groups, best["config_id"])
    results = {
        "summary_configs": summary_configs,
        "best_model": best["model"], "best_config": best,
        "validation_macro_mae": best_row["macro_mae"],
        "validation_macro_skill": best_row["macro_skill"],
        "validation_mae_reduction": best_row["macro_mae_skill"],
        "model_metrics": model_metrics, "per_city": per_city,
        "test_b_station_match": matched, "bootstrap": bootstrap,
        "suspect_exclusions": exclusions.to_dict("records"),
        "split_dates": {
            name: {"start": str(start.date()), "end": str(end.date())}
            for name, (start, end) in cutoffs.items()
        },
        "split_counts": {name: len(frame) for name, frame in splits.items()},
        "feature_groups": active_groups, "findings": " ".join(findings),
    }
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    grid_results_frame(model_metrics, active_groups).to_csv(
        reports / "grid_results.csv", index=False
    )
    (reports / "results.md").write_text(markdown_results(results), encoding="utf-8")
    (reports / "results.json").write_text(
        json.dumps(results, indent=2, allow_nan=False), encoding="utf-8"
    )
    monthly_errors(backtest).to_csv(reports / "monthly_mae.csv", index=False)
    backtest.to_parquet(reports / "backtest.parquet", index=False)

    ablations = []
    for set_name, groups in cfg["ablation_sets"].items():
        selected_columns = group_columns(groups)
        fit_val = _fit(lightgbm_candidate, train_frame, selected_columns, cfg)
        fit_test = _fit(lightgbm_candidate, train_val, selected_columns, cfg)
        for split_name, model in (("val", fit_val), ("test_a", fit_test)):
            frame = splits[split_name]
            prediction = predict_level(
                model, frame, selected_columns, lightgbm_candidate["target_mode"], city_max
            )
            scored = comparison_frame(frame, prediction)
            score = score_predictions(scored)
            interval = moving_block_bootstrap(
                scored, boot_cfg["block_days"], boot_cfg["resamples"],
                boot_cfg["seed"], statistic="macro_skill",
            )
            ablations.append({
                "feature_set": set_name, "split": split_name,
                "Fit": "train" if split_name == "val" else "train+val",
                "macro_mae": score["macro_mae"], "macro_skill": score["macro_skill"],
                "mae_reduction": score["macro_mae_skill"],
                "skill_ci_low": interval["ci_low"], "skill_ci_high": interval["ci_high"],
            })
    ablation_lines = [
        "# LightGBM feature ablation", "",
        f"Fixed validation-selected configuration: {lightgbm_candidate['config_id']}.",
        "All rows use the same suspect exclusion and split dates.", "",
        "MAE reduction vs persistence = 1 - macro MAE / persistence macro MAE.",
        "",
        "| Features | Split | Fit | Macro MAE | MAE reduction | Mean per-city skill | 95% block interval for mean per-city skill |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in ablations:
        ablation_lines.append(
            f"| {row['feature_set']} | {row['split']} | {row['Fit']} | "
            f"{row['macro_mae']:.3f} | {row['mae_reduction']:.3f} | "
            f"{row['macro_skill']:.3f} | "
            f"[{row['skill_ci_low']:.3f}, {row['skill_ci_high']:.3f}] |"
        )
    (reports / "ablation.md").write_text("\n".join(ablation_lines) + "\n", encoding="utf-8")
    serving = build_serving_features(clean)
    if "weather" in active_groups:
        weather = load_weather(root, cfg)
        serving = add_weather_features(serving, weather)
    if "festival" in active_groups:
        serving = add_festival_features(
            serving, load_festival_dates(root / "ml" / "configs" / "festivals.yaml")
        )
    if "anomaly" in active_groups:
        serving = add_anomaly_feature(serving, lookup)
    metadata = {
        "selected_config": best,
        "persistence": [
            row for row in model_metrics if row["model"] == "persistence"
        ],
        "summary_configs": summary_configs,
        "split_dates": results["split_dates"],
        "features": columns,
    }
    export_assets(root, best_model, metadata, serving, clean, backtest, results)
    print(
        f"Selected {best['config_id']} by validation macro MAE "
        f"{best_row['macro_mae']:.3f}; macro skill {best_row['macro_skill']:.3f}"
    )
    print("Split rows: " + ", ".join(
        f"{name}={len(frame):,}" for name, frame in splits.items()
    ))
    if best_row["macro_skill"] < 0.05:
        print("Validation macro skill is below 0.05; stopping without further tuning.")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    train(Path(__file__).resolve().parents[3])

