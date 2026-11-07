"""Adapter for city_day.csv."""

from pathlib import Path

import pandas as pd

from .common import adapt_wide


def adapt_city_day(path: Path, cfg: dict) -> pd.DataFrame:
    """Adapt the city-day source."""
    return adapt_wide(path, cfg, "city_day")

