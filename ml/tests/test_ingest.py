"""Small in-memory fixtures for adapters, priority, and validation."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd
import pytest

from vayuops_ml.adapters.air_pollution_data import adapt_air_pollution_data
from vayuops_ml.adapters.cities_2020_2024 import adapt_cities_2020_2024
from vayuops_ml.adapters.city_day import adapt_city_day
from vayuops_ml.adapters.openaq_2025 import adapt_openaq_2025
from vayuops_ml.ingest import add_quality_flags, load_config, select_modeling_rows, select_priority
from vayuops_ml.validate import validate_clean


@pytest.fixture
def cfg() -> dict:
    """Load the project source config."""
    path = Path(__file__).resolve().parents[1] / "configs" / "sources.yaml"
    return load_config(path)


def test_combined_city_uses_filename_and_keeps_location(tmp_path: Path, cfg: dict) -> None:
    """Location is raw station text; city comes from the filename."""
    path = tmp_path / "bengaluru_combined.csv"
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    pd.DataFrame([{"Timestamp": day.strftime("%d-%m-%Y"), "Location": "Wrong City - Station",
        "PM2.5": 10, "PM10": 20, "NO2": 3, "NH3": 4, "SO2": 5, "CO": .2, "O3": 6}
        for day in dates]).to_csv(path, index=False)
    result = adapt_cities_2020_2024(path, cfg)
    assert result.loc[0, "city"] == "bengaluru"
    assert result.loc[0, "location_raw"] == "Wrong City - Station"
    assert result.loc[0, "co"] == .2
    assert result.loc[0, "station_name"] == "Wrong City - Station"
    assert result.date.nunique() == 1827


def test_city_day_alias_and_nulls(tmp_path: Path, cfg: dict) -> None:
    """Configured aliases apply; missing pollutant values stay missing."""
    path = tmp_path / "city_day.csv"
    pd.DataFrame([{"City": " Bangalore ", "Date": "2020-01-01", "PM2.5": None,
        "PM10": 2, "NO2": 3, "SO2": 4, "CO": .1, "O3": 5, "NH3": 6}]).to_csv(path, index=False)
    result = adapt_city_day(path, cfg)
    assert result.loc[0, "city"] == "bengaluru"
    assert result.loc[0, "co"] == .1
    assert pd.isna(result.loc[0, "pm25"])


def test_air_pollution_mapping(tmp_path: Path, cfg: dict) -> None:
    """The source uses day-first dates and pm2_5."""
    path = tmp_path / "air.csv"
    pd.DataFrame([{"city": "Vizag", "date": "13-02-2020", "pm2_5": 12,
        "pm10": 20, "no2": 3, "so2": 4, "co": .5, "o3": 6, "nh3": 7}]).to_csv(path, index=False)
    result = adapt_air_pollution_data(path, cfg)
    assert result.loc[0, "city"] == "vizag"
    assert result.loc[0, "date"] == pd.Timestamp("2020-02-13")
    assert result.loc[0, "pm25"] == 12
    assert result.loc[0, "co"] == .0005


def test_openaq_ist_pivot_wrong_unit_and_station_median(
    tmp_path: Path, cfg: dict, caplog: pytest.LogCaptureFixture
) -> None:
    """Convert aware times to IST, average station repeats, then median stations."""
    path = tmp_path / "openaq.csv"
    base = {"city": "Bangalore", "date_from": "2025-01-01T20:00:00+00:00",
        "date": None, "unit": "ug/m3"}
    rows = [
        {**base, "station": "A", "parameter": "pm25", "value": 10},
        {**base, "station": "A", "parameter": "pm25", "value": 30},
        {**base, "station": "B", "parameter": "pm25", "value": 50},
        {**base, "station": "B", "parameter": "no2", "value": 8, "unit": "unsupported"},
        {**base, "station": "A", "parameter": "no2", "value": 10, "unit": "ppb"},
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    caplog.set_level(logging.INFO)
    result = adapt_openaq_2025(path, cfg)
    assert len(result) == 1
    assert result.loc[0, "date"] == pd.Timestamp("2025-01-02")
    assert result.loc[0, "city"] == "bengaluru"
    assert result.loc[0, "pm25"] == 35
    assert result.loc[0, "n_stations"] == 2
    assert result.loc[0, "station_name"] == "A, B"
    assert not result.loc[0, "station_matched"]
    assert "file date disagrees with IST date: 0" in caplog.text
    assert result.loc[0, "no2"] == pytest.approx(18.8)
    assert "wrong unit no2: 1" in caplog.text


def test_priority_does_not_impute(cfg: dict) -> None:
    """The first source wins even when its PM2.5 is null."""
    frame = pd.DataFrame([
        {"city": "delhi", "date": pd.Timestamp("2020-01-01"), "source": "city_day", "pm25": 20},
        {"city": "delhi", "date": pd.Timestamp("2020-01-01"), "source": "cities_2020_2024", "pm25": float("nan")},
    ])
    result = select_priority(frame, cfg)
    assert len(result) == 1
    assert result.loc[0, "source"] == "cities_2020_2024"
    assert pd.isna(result.loc[0, "pm25"])


def test_schema_pass_and_fail(cfg: dict) -> None:
    """Hard rules reject duplicates, negative values, and extreme PM2.5."""
    row = {"date": pd.Timestamp("2020-01-01"), "city": "delhi", "source": "city_day",
        "n_stations": pd.NA, "station_name": pd.NA, "station_matched": pd.NA,
        "pm25_suspect": False, **{name: 1.0 for name in cfg["pollutants"]}}
    valid = pd.DataFrame([row])
    valid["n_stations"] = valid["n_stations"].astype("Int64")
    valid["station_matched"] = valid["station_matched"].astype("boolean")
    empty_overlap = pd.DataFrame()
    validate_clean(valid, valid, empty_overlap, cfg)
    for invalid in (
        pd.concat([valid, valid], ignore_index=True),
        valid.assign(pm25=-1.0),
        valid.assign(pm25=2001.0),
        valid.assign(date=pd.Timestamp("2014-12-31")),
    ):
        with pytest.raises(Exception):
            validate_clean(invalid, invalid, empty_overlap, cfg)



def test_combined_date_assertion(tmp_path: Path, cfg: dict) -> None:
    """Incomplete combined-city coverage fails clearly."""
    path = tmp_path / "delhi_combined.csv"
    pd.DataFrame({"Timestamp": ["01-01-2020"], "Location": ["Delhi - A"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="1,827 unique consecutive dates"):
        adapt_cities_2020_2024(path, cfg)


def test_ambiguous_date_format_fails(tmp_path: Path, cfg: dict) -> None:
    """Day and month ambiguity must not be guessed."""
    path = tmp_path / "city_day.csv"
    pd.DataFrame({"Date": ["01-02-2020"], "City": ["Delhi"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="exactly one date format"):
        adapt_city_day(path, cfg)


def test_openaq_filter_and_units(tmp_path: Path, cfg: dict, caplog: pytest.LogCaptureFixture) -> None:
    """Station filter selects one station and converts every OpenAQ unit factor."""
    path = tmp_path / "openaq.csv"
    factors = cfg["sources"]["openaq_2025"]["unit_factors"]
    rows = []
    for parameter, unit_map in factors.items():
        unit = next(iter(unit_map))
        for station, value in (("A", 10.0), ("B", 30.0)):
            rows.append({"city": "Bangalore", "station": station, "parameter": parameter,
                "unit": unit, "value": value, "date_from": "2025-02-18 18:30:00+00:00",
                "date": "2025-02-18"})
    pd.DataFrame(rows).to_csv(path, index=False)
    caplog.set_level(logging.INFO)
    unfiltered = adapt_openaq_2025(path, cfg)
    assert unfiltered.loc[0, "date"] == pd.Timestamp("2025-02-19")
    assert unfiltered.loc[0, "n_stations"] == 2
    assert "file date disagrees with IST date: 12" in caplog.text
    for pollutant, unit_map in factors.items():
        assert unfiltered.loc[0, pollutant] == pytest.approx(20 * next(iter(unit_map.values())))
    cfg["sources"]["openaq_2025"]["openaq_station_filter"] = {"bengaluru": ["A"]}
    filtered = adapt_openaq_2025(path, cfg)
    assert filtered.loc[0, "n_stations"] == 1
    assert filtered.loc[0, "station_name"] == "A"
    assert filtered.loc[0, "station_matched"]
    for pollutant, unit_map in factors.items():
        assert filtered.loc[0, pollutant] == pytest.approx(10 * next(iter(unit_map.values())))


def test_sentinels_and_suspect_flag(tmp_path: Path, cfg: dict) -> None:
    """Sentinels become null; suspect values remain present."""
    path = tmp_path / "air.csv"
    rows = []
    for index in range(20):
        rows.append({"city": "Delhi", "date": f"{index + 1:02d}-02-2020",
            "pm2_5": 999.99 if index == 0 else (500 if index == 19 else 10),
            "pm10": 9999 if index == 0 else 20, "no2": 10,
            "so2": 5, "co": 1000, "o3": 10, "nh3": 2})
    pd.DataFrame(rows).to_csv(path, index=False)
    result = add_quality_flags(adapt_air_pollution_data(path, cfg))
    assert pd.isna(result.loc[0, "pm25"])
    assert pd.isna(result.loc[0, "pm10"])
    assert result.loc[19, "pm25"] == 500
    assert result.loc[19, "pm25_suspect"]
    assert not result.loc[1, "pm25_suspect"]




def test_modeling_scope(cfg: dict) -> None:
    """Clean inputs exclude comparison sources and non-backbone cities."""
    frame = pd.DataFrame([
        {"city": "delhi", "source": "cities_2020_2024"},
        {"city": "delhi", "source": "city_day"},
        {"city": "delhi", "source": "air_pollution_data"},
        {"city": "nagpur", "source": "openaq_2025"},
    ])
    result = select_modeling_rows(frame, cfg)
    assert result[["city", "source"]].to_dict("records") == [
        {"city": "delhi", "source": "cities_2020_2024"}
    ]
