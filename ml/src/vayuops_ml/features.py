"""Build next-calendar-day PM2.5 features without future leakage."""

from __future__ import annotations

import json
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


def build_features(clean: pd.DataFrame, include_missing_target: bool = False) -> pd.DataFrame:
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
        suspect = daily["pm25_suspect"] if "pm25_suspect" in daily else pd.Series(False, index=days)
        result["suspect_t"] = suspect.astype("boolean").fillna(False).astype(bool)
        result["suspect_target"] = suspect.astype("boolean").shift(-1).fillna(False).astype(bool)
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
        keep = ~result["pm25_t"].isna()
        if not include_missing_target:
            keep &= ~target_missing
        outputs.append(result.loc[keep])
    output = pd.concat(outputs, ignore_index=True)
    output["city"] = output["city"].astype("category")
    output["target_station_matched"] = output["target_station_matched"].astype("boolean")
    return output[["city", "date", "target_date", *feature_columns()[0:-1], "target", "target_source", "target_station_matched", "suspect_t", "suspect_target"]]


def build_serving_features(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Build one feature row at each city's last observed date, without a target."""
    built = build_features(clean_df, include_missing_target=True)
    last = clean_df.assign(date=pd.to_datetime(clean_df["date"])).groupby("city")["date"].max()
    selected = built.loc[
        built.apply(lambda row: row["date"] == last.loc[str(row["city"])], axis=1)
    ].copy()
    expected = clean_df["city"].nunique()
    if len(selected) != expected:
        raise ValueError(f"Serving features unavailable for {expected - len(selected)} cities")
    return selected[["city", "date", *[column for column in feature_columns() if column != "city"]]].reset_index(drop=True)


def weather_feature_columns() -> list[str]:
    """Return configured weather feature names, excluding future weather."""
    bases = (
        "temperature_2m_mean", "relative_humidity_2m_mean", "wind_speed_10m_mean",
        "wind_direction_sin", "wind_direction_cos", "precipitation_sum",
        "surface_pressure_mean",
    )
    return [f"weather_{base}_{suffix}" for base in bases for suffix in ("t", "t_minus_1", "mean_3")]


def add_weather_features(rows: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Join observed weather at t, t-1, and the trailing three-day mean."""
    observed = weather.copy()
    observed["date"] = pd.to_datetime(observed["date"])
    observed = observed.sort_values(["city", "date"])
    angle = observed["wind_direction_10m_dominant"].astype(float).map(math.radians)
    observed["wind_direction_sin"] = angle.map(math.sin)
    observed["wind_direction_cos"] = angle.map(math.cos)
    bases = (
        "temperature_2m_mean", "relative_humidity_2m_mean", "wind_speed_10m_mean",
        "wind_direction_sin", "wind_direction_cos", "precipitation_sum",
        "surface_pressure_mean",
    )
    pieces = []
    for city, group in observed.groupby("city", sort=False):
        group = group.sort_values("date").set_index("date")
        daily = group.reindex(pd.date_range(group.index.min(), group.index.max(), freq="D"))
        feature = pd.DataFrame({"city": city, "date": daily.index})
        for base in bases:
            values = pd.to_numeric(daily[base], errors="coerce")
            feature[f"weather_{base}_t"] = values.to_numpy()
            feature[f"weather_{base}_t_minus_1"] = values.shift(1).to_numpy()
            feature[f"weather_{base}_mean_3"] = values.rolling(3, min_periods=1).mean().to_numpy()
        pieces.append(feature)
    table = pd.concat(pieces, ignore_index=True)
    return rows.merge(table, on=["city", "date"], how="left", validate="many_to_one")


def load_festival_dates(path: Path) -> dict[int, pd.Timestamp]:
    """Read cited Diwali dates from JSON-compatible YAML."""
    text = "\n".join(
        line for line in path.read_text(encoding="utf-8-sig").splitlines()
        if not line.lstrip().startswith("#")
    )
    return {
        int(year): pd.Timestamp(day) for year, day in json.loads(text)["diwali"].items()
    }


def add_festival_features(rows: pd.DataFrame, dates: dict[int, pd.Timestamp]) -> pd.DataFrame:
    """Encode the configured Diwali window for each local calendar date."""
    result = rows.copy()
    day = pd.to_datetime(result["date"])
    diwali = day.dt.year.map(dates)
    offset = (day - diwali).dt.days
    result["days_from_diwali"] = offset.clip(-5, 7).astype(float)
    result["is_diwali_window"] = offset.between(-5, 7).fillna(False).astype(int)
    return result


def fit_anomaly_lookup(train: pd.DataFrame) -> pd.DataFrame:
    """Fit city-month PM2.5 medians on training rows only."""
    work = train.assign(month=pd.to_datetime(train["date"]).dt.month)
    return (
        work.groupby(["city", "month"], observed=True, as_index=False)["pm25_t"]
        .median().rename(columns={"pm25_t": "city_month_pm25_median"})
    )


def add_anomaly_feature(rows: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    """Apply the frozen training lookup to any split."""
    work = rows.assign(month=pd.to_datetime(rows["date"]).dt.month)
    work = work.merge(lookup, on=["city", "month"], how="left", validate="many_to_one")
    work["pm25_anomaly"] = work["pm25_t"] - work["city_month_pm25_median"]
    return work.drop(columns=["month", "city_month_pm25_median"])


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

