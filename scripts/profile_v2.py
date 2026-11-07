"""Print and save a compact, read-only profile of the four raw data sources."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "data-inventory-v2.md"
CITY_FILES = RAW / "indian_cities_aqi_2020_2024"
POLLUTANTS = ("PM2.5", "PM10", "NO2", "NH3", "SO2", "CO", "O3")


def items(values: object) -> str:
    """Join distinct values without printing source rows."""
    return ", ".join(sorted(str(value) for value in pd.Series(values).dropna().unique())) or "none"


def samples(values: pd.Series) -> str:
    """Show the first three non-null values as literal text."""
    return " | ".join(values.dropna().astype(str).head(3)) or "none"


def stats(frame: pd.DataFrame, names: tuple[str, ...]) -> str:
    """Format min, median, p95, and max for requested numeric columns."""
    parts = []
    for name in names:
        numbers = pd.to_numeric(frame[name], errors="coerce").dropna()
        if numbers.empty:
            parts.append(f"{name}: no numeric values")
        else:
            parts.append(
                f"{name}: {numbers.min():.2f}/{numbers.median():.2f}/"
                f"{numbers.quantile(.95):.2f}/{numbers.max():.2f}"
            )
    return "; ".join(parts)


def normalize(values: object) -> set[str]:
    """Normalize city labels for source comparisons."""
    return {str(value).strip().lower() for value in pd.Series(values).dropna() if str(value).strip()}


def main() -> str:
    """Build the report and return its Markdown text."""
    lines = ["# Data inventory v2", "", "Statistics use min / median / p95 / max.", ""]
    names: dict[str, set[str]] = {}

    city_paths = sorted(CITY_FILES.glob("*.csv"))
    lines.append("## Indian cities AQI 2020–2024")
    names["indian_cities_aqi_2020_2024"] = set()
    for path in city_paths:
        frame = pd.read_csv(path)
        locations = frame["Location"]
        names["indian_cities_aqi_2020_2024"].add(path.stem.removesuffix("_combined").strip().lower())
        lines.extend([
            f"- **{path.name}** — Location: {items(locations)}; Timestamp examples: {samples(frame['Timestamp'])}",
            f"  - Pollutants: {stats(frame, POLLUTANTS)}",
        ])
    lines.append("")

    lines.append("## India air quality 2025")
    openaq = pd.read_csv(RAW / "india_air_quality_2025_openaq" / "india_air_quality_2025.csv")
    names["india_air_quality_2025"] = normalize(openaq["city"])
    station_counts = openaq.groupby("city")["station"].nunique().sort_index()
    lines.append("- Stations per city: " + "; ".join(f"{city}: {count}" for city, count in station_counts.items()))
    parameter_counts = openaq.groupby(["parameter", "unit"], dropna=False).size().sort_index()
    lines.append("- Parameters (unit, rows): " + "; ".join(
        f"{parameter} ({unit}: {count:,})" for (parameter, unit), count in parameter_counts.items()
    ))
    lines.append(f"- date_from examples: {samples(openaq['date_from'])}; date_to examples: {samples(openaq['date_to'])}")
    grouped = openaq.groupby(["station", "parameter", "date"], dropna=False).size()
    lines.append(f"- Median rows per (station, parameter, date): {grouped.median():g}")
    openaq_dates = pd.to_datetime(openaq["date"], errors="coerce")
    city_dates = pd.DataFrame({"city": openaq["city"], "date": openaq_dates}).groupby("city")["date"].agg(["min", "max"])
    lines.append("- Date ranges by city: " + "; ".join(
        f"{city}: {row['min']:%Y-%m-%d} to {row['max']:%Y-%m-%d}"
        for city, row in city_dates.iterrows()
    ))
    lines.append("")

    lines.append("## Air pollution data")
    air = pd.read_csv(RAW / "air_pollution_data.csv" / "air_pollution_data.csv")
    names["air_pollution_data"] = normalize(air["city"])
    lines.append("- AQI values (rows): " + "; ".join(
        f"{value}: {count:,}" for value, count in air["aqi"].value_counts(dropna=False).sort_index().items()
    ))
    lines.append("- Rows per city: " + "; ".join(
        f"{city}: {count:,}" for city, count in air["city"].value_counts().sort_index().items()
    ))
    air_dates = pd.to_datetime(air["date"], format="%d-%m-%Y", errors="coerce")
    city_groups = pd.DataFrame({"city": air["city"], "date": air_dates}).dropna().groupby("city")["date"]
    missing = []
    for city, dates in city_groups:
        unique = dates.dt.normalize().nunique()
        span = (dates.max().normalize() - dates.min().normalize()).days + 1
        missing.append(f"{city}: {span - unique}")
    lines.append("- Missing calendar dates per city (between first and last): " + "; ".join(missing))
    lines.append("- PM2.5 / CO / NO2: " + stats(air, ("pm2_5", "co", "no2")))
    lines.append("")

    lines.append("## City day")
    city_day = pd.read_csv(RAW / "city_day.csv" / "city_day.csv")
    names["city_day"] = normalize(city_day["City"])
    lines.append("- Cities: " + items(city_day["City"]))
    lines.append("- PM2.5 / CO / NO2: " + stats(city_day, ("PM2.5", "CO", "NO2")))
    lines.append("")

    lines.append("## Name check")
    for source, city_names in names.items():
        lines.append(f"- {source}: " + ", ".join(sorted(city_names)))
    owners: dict[str, set[str]] = {}
    for source, city_names in names.items():
        for city in city_names:
            owners.setdefault(city, set()).add(source)
    unique_to_one = sorted(city for city, sources in owners.items() if len(sources) == 1)
    similar = set()
    for left in unique_to_one:
        for right, right_sources in owners.items():
            if left == right or owners[left] & right_sources:
                continue
            score = SequenceMatcher(None, left, right).ratio()
            if score >= 0.72 or {left, right} == {"bangalore", "bengaluru"}:
                similar.add((left, right) if left < right else (right, left))
    lines.append("- Similar names across sources: " + (
        "; ".join(f"{left} ~ {right}" for left, right in sorted(similar)) or "none"
    ))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = main()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report, end="")


