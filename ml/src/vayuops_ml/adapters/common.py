"""Shared, stateless adapter helpers."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


def canonical_city(values: pd.Series, cfg: dict) -> pd.Series:
    """Normalize city labels and configured aliases."""
    cleaned = values.astype("string").str.strip().str.lower()
    return cleaned.replace(cfg.get("aliases", {}))


def local_days(values: pd.Series, cfg: dict, date_format: str | None = None) -> pd.Series:
    """Convert aware timestamps to IST; preserve naive date-only calendar days."""
    timezone = cfg["timezone"]
    if date_format:
        return pd.to_datetime(values, format=date_format, errors="coerce").dt.normalize()
    def parse(value: object) -> pd.Timestamp:
        if pd.isna(value):
            return pd.NaT
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert(timezone).tz_localize(None)
        return timestamp.normalize()
    return values.map(parse)


def detect_date_format(values: pd.Series, source: str) -> str:
    """Choose exactly one complete parse from the allowed date formats."""
    candidates = ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y")
    nonnull = values.dropna()
    fits = [
        fmt for fmt in candidates
        if not nonnull.empty and pd.to_datetime(nonnull, format=fmt, errors="coerce").notna().all()
    ]
    if len(fits) != 1:
        raise ValueError(f"{source}: expected exactly one date format, found {fits}")
    logging.getLogger(__name__).info("%s detected date format %s", source, fits[0])
    return fits[0]


def finish(frame: pd.DataFrame, source: str, rows_in: int, dropped: dict[str, int], cfg: dict) -> pd.DataFrame:
    """Set canonical columns and log adapter outcomes."""
    columns = ["date", "city", *cfg["pollutants"], "source", "n_stations", "station_name", "station_matched"]
    for column in columns:
        if column not in frame:
            frame[column] = pd.NA
    frame["source"] = source
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["n_stations"] = pd.array(frame["n_stations"], dtype="Int64")
    frame["station_matched"] = pd.array(frame["station_matched"], dtype="boolean")
    for column in cfg["pollutants"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
        sentinel = frame[column].isin((999.99, 9999))
        dropped["sentinel"] = dropped.get("sentinel", 0) + int(sentinel.sum())
        frame.loc[sentinel, column] = float("nan")
    result = frame[columns + (["location_raw"] if "location_raw" in frame else [])].copy()
    dates = f"{result.date.min()}..{result.date.max()}" if not result.empty else "none"
    logger = logging.getLogger(__name__)
    for pollutant in cfg["pollutants"]:
        median = result[pollutant].median() if result[pollutant].notna().any() else float("nan")
        logger.info("%s median %s=%s", source, pollutant, median)
        bounds = {"co": (0.1, 5), "no2": (5, 100), "so2": (1, 60)}
        if pollutant in bounds and pd.notna(median):
            low, high = bounds[pollutant]
            if not low <= median <= high:
                logger.warning("%s median %s=%.3f outside [%.1f, %.1f]", source, pollutant, median, low, high)
    logger.info(
        "%s: rows_in=%d rows_out=%d dates=%s cities=%d dropped=%s",
        source, rows_in, len(result), dates, result.city.nunique(), dropped,
    )
    return result


def adapt_wide(path: Path, cfg: dict, source: str) -> pd.DataFrame:
    """Map one city-level wide CSV to canonical columns."""
    spec = cfg["sources"][source]
    raw = pd.read_csv(path)
    frame = pd.DataFrame(index=raw.index)
    date_format = (
        spec["date_format"] if source == "cities_2020_2024"
        else detect_date_format(raw[spec["date_column"]], source)
    )
    frame["date"] = local_days(raw[spec["date_column"]], cfg, date_format)
    if source == "cities_2020_2024":
        expected = pd.date_range("2020-01-01", "2024-12-31", freq="D")
        actual = pd.DatetimeIndex(frame["date"].dropna().unique()).sort_values()
        if len(actual) != 1827 or not actual.equals(expected):
            raise ValueError(
                f"{path.name}: expected exactly 1,827 unique consecutive dates "
                "from 2020-01-01 to 2024-12-31"
            )
    if source == "cities_2020_2024":
        city = path.stem.removesuffix("_combined")
        frame["city"] = canonical_city(pd.Series(city, index=raw.index), cfg)
        frame["location_raw"] = raw[spec["location_column"]]
        frame["station_name"] = raw[spec["location_column"]]
    else:
        frame["city"] = canonical_city(raw[spec["city_column"]], cfg)
    sentinel_count = 0
    for original, target in spec["column_map"].items():
        values = pd.to_numeric(raw[original], errors="coerce")
        sentinel = values.isin((999.99, 9999))
        sentinel_count += int(sentinel.sum())
        frame[target] = values.mask(sentinel) * spec.get("scale", {}).get(original, 1.0)
    invalid = frame["date"].isna() | frame["city"].isna() | frame["city"].eq("")
    dropped = {"invalid city/date": int(invalid.sum()), "sentinel": sentinel_count}
    return finish(frame.loc[~invalid].copy(), source, len(raw), dropped, cfg)

