"""Adapter for station-level OpenAQ data."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .common import canonical_city, finish


def adapt_openaq_2025(path: Path, cfg: dict) -> pd.DataFrame:
    """Average station-day observations, then median stations by city-day."""
    spec = cfg["sources"]["openaq_2025"]
    raw = pd.read_csv(path)
    rows_in = len(raw)
    raw["city_canonical"] = canonical_city(raw[spec["city_column"]], cfg)
    aware = pd.to_datetime(raw[spec["date_column"]], utc=True, errors="coerce")
    raw["day_canonical"] = aware.dt.tz_convert(cfg["timezone"]).dt.tz_localize(None).dt.normalize()
    file_day = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    disagreement = (file_day.notna() & raw["day_canonical"].notna()
                    & file_day.ne(raw["day_canonical"])).sum()
    logging.getLogger(__name__).info("openaq_2025 file date disagrees with IST date: %d rows", disagreement)
    raw["target"] = raw[spec["parameter_column"]].map(spec["column_map"])
    raw["value_numeric"] = pd.to_numeric(raw[spec["value_column"]], errors="coerce")
    sentinel = raw["value_numeric"].isin((999.99, 9999))
    raw.loc[sentinel, "value_numeric"] = float("nan")
    factors = raw.apply(
        lambda row: spec["unit_factors"].get(row["target"], {}).get(row[spec["unit_column"]],
            1.0 if row[spec["unit_column"]] == spec["expected_unit"] else None),
        axis=1,
    )
    wrong = raw["target"].notna() & factors.isna()
    for parameter, count in raw.loc[wrong].groupby(spec["parameter_column"]).size().items():
        logging.getLogger(__name__).warning("openaq_2025 dropped wrong unit %s: %d", parameter, count)
    valid = (
        raw["target"].notna() & factors.notna() & raw["value_numeric"].notna()
        & raw["city_canonical"].notna() & raw["day_canonical"].notna()
        & raw[spec["station_column"]].notna()
    )
    station_filter = spec.get("openaq_station_filter", {})
    allowed = raw.apply(
        lambda row: not station_filter.get(row["city_canonical"])
        or row[spec["station_column"]] in station_filter[row["city_canonical"]],
        axis=1,
    )
    filtered = valid & allowed
    selected = raw.loc[filtered].copy()
    selected["converted"] = selected["value_numeric"] * factors.loc[filtered].astype(float)
    keys = ["city_canonical", "day_canonical", spec["station_column"], "target"]
    station = selected.groupby(keys, as_index=False)["converted"].mean()
    counts = station.groupby(["city_canonical", "day_canonical"])[spec["station_column"]].nunique()
    city = station.groupby(["city_canonical", "day_canonical", "target"])["converted"].median().unstack("target").reset_index()
    city = city.rename(columns={"city_canonical": "city", "day_canonical": "date"})
    station_names = station.groupby(["city_canonical", "day_canonical"])[spec["station_column"]].apply(
        lambda values: ", ".join(sorted(values.astype(str).unique()))
    )
    city["station_name"] = [
        station_names.loc[(row.city, row.date)]
        for row in city[["city", "date"]].itertuples(index=False)
    ]
    city["station_matched"] = city["city"].map(
        lambda name: bool(station_filter.get(name))
    )
    city["n_stations"] = [
        counts.loc[(row.city, row.date)] for row in city[["city", "date"]].itertuples(index=False)
    ]
    dropped = {
        "wrong unit": int(wrong.sum()),
        "station filter": int((valid & ~allowed).sum()),
        "sentinel": int(sentinel.sum()),
        "unknown parameter": int(raw["target"].isna().sum()),
        "other invalid": int((~valid & ~wrong & ~sentinel & raw["target"].notna()).sum()),
    }
    return finish(city, "openaq_2025", rows_in, dropped, cfg)

