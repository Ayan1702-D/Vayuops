"""Adapter for air_pollution_data.csv."""

from pathlib import Path

import pandas as pd

from .common import adapt_wide


def adapt_air_pollution_data(path: Path, cfg: dict) -> pd.DataFrame:
    """Adapt the city-level air-pollution source."""
    return adapt_wide(path, cfg, "air_pollution_data")

