"""Build next-calendar-day PM2.5 features without future leakage."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pandas as pd


def feature_columns() -> list[str]:
    """Return model input columns; NH3 and future targets are excluded."""
    names = ["pm25_t", "pm25_t_minus_1", "pm25_t_minus_2", "pm25_t_minus_6"]
    names += ["pm25_mean_7", "pm25_std_7", "pm25_mean_14", "pm25_std_14"]
    for pollutant in ("pm10", "no2", "so2", "co", "o3"):
        names += [f"{pollutant}_t", f"{pollutant}_mean_3"]
    return names + ["day_of_week", "month_sin", "month_cos", "day_of_year_sin", "day_of_year_cos", "city"]


def build_features(clean: pd.DataFrame) -> pd.DataFrame:
    """Reindex each city daily, fill only past pollutant values, and target t+1."""
    required = {"city", "date", "pm25", "pm10", "no2", "so2", "co", "o3"}
    missing = required - set(clean.columns)
    if missing:
        raise ValueError(f"Missing clean columns: {sorted(missing)}")
    if clean.duplicated(["city", "date"]).any():
        raise ValueError("Clean data must have one row per city-date")
    outputs = []
    logger = logging.getLogger(__name__)
    for city, observed in clean.groupby("city", sort=True):
        observed = observed.copy()
        observed["date"] = pd.to_datetime(observed["date"])
        observed = observed.sort_values("date").set_index("date")
        days = pd.date_range(observed.index.min(), observed.index.max(), freq="D")
        daily = observed.reindex(days)
        daily.index.name = "date"
        pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]
        filled = daily[pollutants].ffill(limit=3)
        result = pd.DataFrame(index=days)
        result["city"] = city
        result["date"] = days
        result["target_date"] = days + pd.Timedelta(days=1)
        result["target"] = daily["pm25"].shift(-1)
        result["target_source"] = daily["source"].shift(-1) if "source" in daily else pd.NA
        result["target_station_matched"] = (
            daily["station_matched"].shift(-1) if "station_matched" in daily else pd.NA
        )
        for lag, name in ((0, "pm25_t"), (1, "pm25_t_minus_1"), (2, "pm25_t_minus_2"), (6, "pm25_t_minus_6")):
            result[name] = filled["pm25"].shift(lag)
        for window in (7, 14):
            result[f"pm25_mean_{window}"] = filled["pm25"].rolling(window, min_periods=4).mean()
            result[f"pm25_std_{window}"] = filled["pm25"].rolling(window, min_periods=4).std()
        for pollutant in pollutants[1:]:
            result[f"{pollutant}_t"] = filled[pollutant]
            result[f"{pollutant}_mean_3"] = filled[pollutant].rolling(3, min_periods=1).mean()
        result["day_of_week"] = days.dayofweek
        result["month_sin"] = [math.sin(2 * math.pi * month / 12) for month in days.month]
        result["month_cos"] = [math.cos(2 * math.pi * month / 12) for month in days.month]
        result["day_of_year_sin"] = [math.sin(2 * math.pi * day / 365.25) for day in days.dayofyear]
        result["day_of_year_cos"] = [math.cos(2 * math.pi * day / 365.25) for day in days.dayofyear]
        target_missing = result["target"].isna()
        lag_missing = result["pm25_t"].isna() & ~target_missing
        logger.info(
            "%s: calendar_rows=%d dropped_missing_target=%d dropped_missing_pm25_t=%d",
            city, len(result), int(target_missing.sum()), int(lag_missing.sum()),
        )
        outputs.append(result.loc[~target_missing & ~lag_missing])
    output = pd.concat(outputs, ignore_index=True)
    output["city"] = output["city"].astype("category")
    output["target_station_matched"] = output["target_station_matched"].astype("boolean")
    return output[["city", "date", "target_date", *feature_columns()[0:-1], "target", "target_source", "target_station_matched"]]


def main(root: Path) -> pd.DataFrame:
    """Read clean data and save the feature table."""
    clean = pd.read_parquet(root / "data" / "processed" / "clean.parquet")
    features = build_features(clean)
    path = root / "data" / "processed" / "features.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(path, index=False)
    print(f"Saved {len(features):,} feature rows to {path}")
    return features


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main(Path(__file__).resolve().parents[3])

