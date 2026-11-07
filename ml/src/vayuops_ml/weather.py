"""Fetch and cache observed daily Open-Meteo archive weather by IST date."""

from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


def fetch_city_weather(city: str, cfg: dict) -> pd.DataFrame:
    """Fetch configured daily variables for one city from the archive API."""
    weather = cfg["weather"]
    latitude, longitude = weather["coordinates"][city]
    query = urlencode({
        "latitude": latitude, "longitude": longitude,
        "start_date": weather["start_date"], "end_date": weather["end_date"],
        "daily": ",".join(weather["daily"]), "timezone": weather["timezone"],
    })
    for attempt in range(5):
        try:
            with urlopen(f"{weather['api_url']}?{query}", timeout=90) as response:
                payload = json.load(response)
            break
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            delay = 10 * (attempt + 1)
            logging.warning("%s weather rate limited; retry in %d seconds", city, delay)
            time.sleep(delay)
    if payload.get("timezone") != weather["timezone"]:
        raise ValueError(f"{city}: unexpected weather timezone {payload.get('timezone')}")
    frame = pd.DataFrame(payload["daily"]).rename(columns={"time": "date"})
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    frame["city"] = city
    expected = {"date", "city", *weather["daily"]}
    if not expected.issubset(frame.columns):
        raise ValueError(f"{city}: missing weather variables {expected - set(frame.columns)}")
    return frame[["city", "date", *weather["daily"]]]


def load_weather(root: Path, cfg: dict) -> pd.DataFrame:
    """Load complete caches, fetching missing or incomplete city files."""
    cache = root / "data" / "raw" / "weather"
    cache.mkdir(parents=True, exist_ok=True)
    frames = []
    start = pd.Timestamp(cfg["weather"]["start_date"])
    end = pd.Timestamp(cfg["weather"]["end_date"])
    for city in cfg["weather"]["coordinates"]:
        path = cache / f"{city}.parquet"
        frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        if frame.empty or frame.date.min() > start or frame.date.max() < end:
            logging.info("Fetching IST daily weather for %s", city)
            frame = fetch_city_weather(city, cfg)
            frame.to_parquet(path, index=False)
            time.sleep(3)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def main(root: Path) -> pd.DataFrame:
    """Run the configured weather cache job."""
    cfg = json.loads((root / "ml" / "configs" / "train.yaml").read_text(encoding="utf-8-sig"))
    weather = load_weather(root, cfg)
    print(f"Cached {len(weather):,} city-days of IST weather")
    return weather


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main(Path(__file__).resolve().parents[3])

