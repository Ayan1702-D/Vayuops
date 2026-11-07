"""Ingest configured raw sources into canonical parquet and quality reports."""

from __future__ import annotations

import json
import logging
from itertools import combinations
from pathlib import Path

import pandas as pd

from vayuops_ml.adapters.air_pollution_data import adapt_air_pollution_data
from vayuops_ml.adapters.cities_2020_2024 import adapt_cities_2020_2024
from vayuops_ml.adapters.city_day import adapt_city_day
from vayuops_ml.adapters.openaq_2025 import adapt_openaq_2025
from vayuops_ml.validate import validate_clean

def load_config(path: Path) -> dict:
    """Load JSON-compatible YAML without a separate YAML dependency."""
    return json.loads("\n".join(line for line in path.read_text(encoding="utf-8-sig").splitlines() if not line.lstrip().startswith("#")))


def select_modeling_rows(all_sources: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Restrict the modeling table to enabled sources and backbone cities."""
    enabled = {
        source for source, spec in cfg["sources"].items()
        if spec["modeling_enabled"]
    }
    return all_sources.loc[
        all_sources["source"].isin(enabled)
        & all_sources["city"].isin(cfg["modeling_cities"])
    ].copy()


def select_priority(all_sources: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Choose the first configured source for each city-date without filling nulls."""
    ranks = {source: index for index, source in enumerate(cfg["priority"])}
    ranked = all_sources.assign(_priority=all_sources["source"].map(ranks))
    if ranked["_priority"].isna().any():
        raise ValueError("Source missing from priority configuration")
    return (
        ranked.sort_values(["city", "date", "_priority"], kind="stable")
        .drop_duplicates(["city", "date"], keep="first")
        .drop(columns="_priority")
        .reset_index(drop=True)
    )


def add_quality_flags(all_sources: pd.DataFrame) -> pd.DataFrame:
    """Flag suspicious PM2.5 values without changing them."""
    result = all_sources.copy()
    p95 = result.groupby(["source", "city"])["pm25"].transform(
        lambda values: values.quantile(0.95)
    )
    result["pm25_suspect"] = (
        result["pm25"].gt(result["pm10"])
        | result["pm25"].gt(10 * p95)
    ).fillna(False).astype(bool)
    return result


def quality_flags_report(all_sources: pd.DataFrame) -> pd.DataFrame:
    """Combine city-source flag counts with the 20 largest flagged rows."""
    counts = all_sources.groupby(["city", "source"], as_index=False)["pm25_suspect"].sum()
    counts = counts.rename(columns={"pm25_suspect": "suspect_count"})
    counts["record_type"] = "count"
    counts["date"] = pd.NaT
    counts["pm25"] = float("nan")
    counts["pm10"] = float("nan")
    largest = all_sources.loc[all_sources["pm25_suspect"]].nlargest(20, "pm25")[
        ["city", "source", "date", "pm25", "pm10"]
    ].copy()
    largest["suspect_count"] = pd.NA
    largest["record_type"] = "top_20"
    return pd.concat([counts, largest], ignore_index=True)[
        ["record_type", "city", "source", "suspect_count", "date", "pm25", "pm10"]
    ]


def coverage_report(all_sources: pd.DataFrame) -> pd.DataFrame:
    """Calculate monthly PM2.5 day coverage within each source-city observed range."""
    result = []
    for (source, city), group in all_sources.groupby(["source", "city"]):
        first, last = group["date"].min(), group["date"].max()
        city_days = group["date"].nunique()
        for month in pd.period_range(first, last, freq="M"):
            start = max(month.start_time.normalize(), first)
            end = min(month.end_time.normalize(), last)
            denominator = (end - start).days + 1
            observed = group.loc[
                group["date"].between(start, end) & group["pm25"].notna(), "date"
            ].nunique()
            result.append((city, str(month), source, observed / denominator, first, last, city_days))
    return pd.DataFrame(result, columns=[
        "city", "month", "source", "pm25_coverage",
        "first_ist_date", "last_ist_date", "city_days",
    ])


def overlap_report(all_sources: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Compare pollutant values for each pair of sources on shared city-dates."""
    rows = []
    for left_name, right_name in combinations(cfg["priority"], 2):
        left = all_sources.loc[all_sources.source.eq(left_name)].set_index(["city", "date"])
        right = all_sources.loc[all_sources.source.eq(right_name)].set_index(["city", "date"])
        common = left.index.intersection(right.index)
        for pollutant in cfg["pollutants"]:
            a = left.loc[common, pollutant]
            b = right.loc[common, pollutant]
            mask = a.notna() & b.notna()
            a, b = a[mask], b[mask]
            if a.empty:
                continue
            median_b = b.median()
            rows.append({
                "source_a": left_name, "source_b": right_name, "pollutant": pollutant,
                "n": len(a), "mean_difference": (a - b).mean(),
                "ratio_of_medians": a.median() / median_b if median_b else float("nan"),
                "pearson_correlation": a.corr(b) if len(a) > 1 else float("nan"),
            })
    return pd.DataFrame(rows, columns=[
        "source_a", "source_b", "pollutant", "n", "mean_difference",
        "ratio_of_medians", "pearson_correlation",
    ])


def quality_summary(all_sources: pd.DataFrame, clean: pd.DataFrame) -> str:
    """Return a short Markdown quality summary."""
    counts = all_sources.groupby("source").size()
    lines = ["## Data quality summary", ""]
    lines.append("- Rows per source: " + "; ".join(f"{name}: {count:,}" for name, count in counts.items()))
    lines.append(f"- Clean rows: {len(clean):,}; cities: {clean.city.nunique()}; date range: {clean.date.min():%Y-%m-%d} to {clean.date.max():%Y-%m-%d}")
    missing = clean.groupby("city")["pm25"].apply(lambda values: values.isna().mean() * 100)
    lines.append("- Missing PM2.5 per city: " + "; ".join(
        f"{city}: {pct:.1f}%" for city, pct in missing.items()
    ))
    return "\n".join(lines) + "\n"


def ingest(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Adapt, combine, validate, persist, and report all configured sources."""
    cfg = load_config(root / "ml" / "configs" / "sources.yaml")
    adapters = {
        "cities_2020_2024": adapt_cities_2020_2024,
        "openaq_2025": adapt_openaq_2025,
        "city_day": adapt_city_day,
        "air_pollution_data": adapt_air_pollution_data,
    }
    frames = []
    for source, spec in cfg["sources"].items():
        paths = sorted((root / "data" / "raw").glob(spec["glob"]))
        if not paths:
            raise FileNotFoundError(f"No source files for {source}: {spec['glob']}")
        for path in paths:
            frames.append(adapters[source](path, cfg))
    all_sources = add_quality_flags(pd.concat(frames, ignore_index=True))
    duplicates = all_sources.groupby(["city", "date"])["source"].nunique().gt(1).sum()
    logging.info("City-dates with more than one source: %d", duplicates)
    clean = select_priority(select_modeling_rows(all_sources, cfg), cfg)
    overlap = overlap_report(all_sources, cfg)
    validate_clean(clean, all_sources, overlap, cfg)
    processed = root / "data" / "processed"
    reports = root / "reports"
    docs = root / "docs"
    processed.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    all_sources.to_parquet(processed / "clean_all_sources.parquet", index=False)
    clean.to_parquet(processed / "clean.parquet", index=False)
    coverage_report(all_sources).to_csv(reports / "coverage.csv", index=False)
    overlap.to_csv(reports / "source_overlap.csv", index=False)
    quality_flags_report(all_sources).to_csv(reports / "quality_flags.csv", index=False)
    summary = quality_summary(all_sources, clean)
    inventory = docs / "data-inventory.md"
    previous = inventory.read_text(encoding="utf-8") if inventory.exists() else ""
    heading = "## Data quality summary"
    previous = previous.split(heading)[0].rstrip()
    inventory.write_text(previous + "\n\n" + summary, encoding="utf-8")
    print(summary, end="")
    return all_sources, clean


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest(Path(__file__).resolve().parents[3])

