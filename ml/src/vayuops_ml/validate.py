"""Pandera schema and quality checks for canonical city-day data."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import pandera.pandas as pa


def schema(cfg: dict) -> pa.DataFrameSchema:
    """Build the canonical hard-fail schema."""
    columns = {
        "date": pa.Column(pa.DateTime, nullable=False),
        "city": pa.Column(str, nullable=False),
        "source": pa.Column(str, nullable=False),
        "n_stations": pa.Column("Int64", nullable=True, required=True),
        "station_name": pa.Column(str, nullable=True, required=True),
        "station_matched": pa.Column("boolean", nullable=True, required=True),
        "pm25_suspect": pa.Column(bool, nullable=False, required=True),
    }
    for pollutant in cfg["pollutants"]:
        upper = 2000 if pollutant == "pm25" else None
        checks = [pa.Check.ge(0)]
        if upper is not None:
            checks.append(pa.Check.le(upper))
        columns[pollutant] = pa.Column(float, checks=checks, nullable=True)
    return pa.DataFrameSchema(columns, strict=False, coerce=False)


def validate_clean(
    clean: pd.DataFrame, all_sources: pd.DataFrame, overlap: pd.DataFrame, cfg: dict
) -> None:
    """Hard fail invalid clean rows; log coverage and source disagreement warnings."""
    schema(cfg).validate(clean, lazy=True)
    if clean.duplicated(["city", "date"]).any():
        raise ValueError("Duplicate (city, date) in clean data")
    if clean["city"].astype("string").str.strip().eq("").any():
        raise ValueError("Empty city")
    lower = pd.Timestamp("2015-01-01")
    upper = pd.Timestamp(date.today())
    if clean["date"].lt(lower).any() or clean["date"].gt(upper).any():
        raise ValueError("Date outside 2015 to today")
    logger = logging.getLogger(__name__)
    high = clean["pm25"].gt(1000).sum()
    if high:
        logger.warning("PM2.5 > 1000: %d rows", high)
    for city, group in clean.groupby("city"):
        span = (group.date.max() - group.date.min()).days + 1
        covered = group.loc[group.pm25.notna(), "date"].nunique()
        if covered / span < 0.7:
            logger.warning("%s PM2.5 coverage below 70%%: %.1f%%", city, 100 * covered / span)
    for row in overlap.itertuples(index=False):
        ratio = row.ratio_of_medians
        if pd.notna(ratio) and (ratio > 2 or ratio < 0.5):
            logger.warning(
                "Median disagreement >2x: %s vs %s, %s, ratio %.2f",
                row.source_a, row.source_b, row.pollutant, ratio,
            )

