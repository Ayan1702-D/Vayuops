"""Profile CSV, XLSX, and JSON files under data/raw without changing them."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "docs" / "data-inventory.md"
EXTENSIONS = {".csv", ".xlsx", ".json"}
POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "aqi")


def cell(value: object) -> str:
    """Keep a value on one Markdown line."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def read(path: Path) -> pd.DataFrame:
    """Read one supported file with pandas."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    try:
        return pd.read_json(path)
    except ValueError:
        return pd.read_json(path, lines=True)


def infer_date(frame: pd.DataFrame) -> tuple[object | None, pd.Series | None]:
    """Select the best populated date or time field."""
    options = []
    for name in frame.columns:
        if not any(word in str(name).casefold() for word in ("date", "time", "timestamp")):
            continue
        parsed = pd.to_datetime(frame[name], errors="coerce", format="mixed", utc=True)
        options.append((int(parsed.notna().sum()), name, parsed))
    if not options:
        return None, None
    count, name, parsed = max(options, key=lambda option: option[0])
    return (name, parsed) if count else (None, None)


def infer_location(frame: pd.DataFrame) -> object | None:
    """Select a likely location field by name."""
    for word in ("city", "location", "station", "site", "district", "region"):
        for name in frame.columns:
            normalized = re.sub("[^a-z0-9]", "", str(name).casefold())
            if normalized == word or normalized.startswith(word):
                return name
    return None


def cadence(dates: pd.Series | None, locations: pd.Series | None) -> str:
    """Infer cadence from unique successive timestamps."""
    if dates is None:
        return "other"
    pairs = pd.DataFrame({"date": dates})
    if locations is not None:
        pairs["location"] = locations
        pairs = pairs.dropna().drop_duplicates()
        gaps = pairs.groupby("location")["date"].apply(
            lambda values: values.sort_values().diff().dropna()
        )
    else:
        gaps = pairs["date"].dropna().drop_duplicates().sort_values().diff().dropna()
    if gaps.empty:
        return "other"
    hours = gaps.median() / pd.Timedelta(hours=1)
    if 0.5 <= hours <= 2:
        return "hourly"
    if 18 <= hours <= 36:
        return "daily"
    return "other"


def profile(path: Path) -> tuple[list[str], dict[str, tuple[pd.Timestamp, pd.Timestamp]]]:
    """Summarize one file and its date coverage by location."""
    filename = path.relative_to(RAW).as_posix()
    try:
        frame = read(path)
    except (ValueError, ImportError, OSError, UnicodeError) as error:
        return [f"### {cell(filename)}", f"- Read error: {cell(error)}"], {}

    date_name, dates = infer_date(frame)
    location_name = infer_location(frame)
    locations = frame[location_name] if location_name is not None else None
    if locations is None and path.stem.endswith("_combined"):
        locations = pd.Series(path.stem.removesuffix("_combined"), index=frame.index)
    if locations is not None:
        locations = locations.astype("string").str.strip().replace("", pd.NA)
    location_count = locations.nunique() if locations is not None else 0
    date_range = (
        f"{dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}"
        if dates is not None and dates.notna().any() else "unknown"
    )
    columns = "; ".join(
        f"{cell(name)} ({frame[name].dtype}, {frame[name].isna().mean():.1%} missing)"
        for name in frame.columns
    ) or "none"
    numeric = frame.select_dtypes(include="number")
    negative = numeric.lt(0).sum()
    negatives = ", ".join(
        f"{cell(name)}: {count:,}" for name, count in negative.items() if count
    ) or "none"
    pollutants = [
        cell(name) for name in frame.columns
        if any(
            word in re.sub("[^a-z0-9]", "", str(name).casefold())
            for word in POLLUTANTS
        )
    ]
    lines = [
        f"### {cell(filename)}",
        f"- Format: {path.suffix[1:].upper()} | Rows: {len(frame):,} | Dates: {date_range} | Granularity: {cadence(dates, locations)}",
        f"- Columns: {columns}",
        f"- Candidate date: {cell(date_name) if date_name is not None else 'none'} | Candidate location: {cell(location_name) if location_name is not None else 'none'} | Unique locations: {location_count:,}",
        f"- Duplicate rows: {frame.duplicated().sum():,} | Negative numeric values: {negatives}",
        f"- Pollutant/AQI columns: {', '.join(pollutants) or 'none'}",
    ]
    intervals = {}
    if dates is not None and locations is not None:
        pairs = pd.DataFrame({"location": locations, "date": dates}).dropna()
        for location, group in pairs.groupby("location"):
            intervals[str(location).casefold()] = (group["date"].min(), group["date"].max())
    return lines, intervals


def build_report() -> str:
    """Build a compact inventory and shared-location overlap section."""
    paths = sorted(
        path for path in RAW.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    )
    lines = ["# Data inventory", "", f"Datasets: {len(paths)}", ""]
    coverage = defaultdict(list)
    for path in paths:
        summary, intervals = profile(path)
        lines.extend(summary + [""])
        for location, (start, end) in intervals.items():
            coverage[location].append((path.relative_to(RAW).as_posix(), start, end))
    lines.extend(["## Cross-dataset locations and overlapping date ranges", ""])
    found = False
    for location, entries in sorted(coverage.items()):
        for index, (left, left_start, left_end) in enumerate(entries):
            for right, right_start, right_end in entries[index + 1:]:
                start, end = max(left_start, right_start), min(left_end, right_end)
                if start <= end:
                    lines.append(
                        f"- {cell(location)}: {cell(left)} <-> {cell(right)} - "
                        f"{start:%Y-%m-%d} to {end:%Y-%m-%d}"
                    )
                    found = True
    if not found:
        lines.append("- No overlapping location and date ranges found.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report, end="")



