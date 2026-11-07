"""Adapter for the ten combined city CSVs."""

from pathlib import Path

import pandas as pd

from .common import adapt_wide


def adapt_cities_2020_2024(path: Path, cfg: dict) -> pd.DataFrame:
    """Adapt one combined city CSV."""
    return adapt_wide(path, cfg, "cities_2020_2024")

