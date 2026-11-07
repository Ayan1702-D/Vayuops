"""Public API response schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_name: str
    model_version: str
    data_as_of_date: date


class CitiesResponse(BaseModel):
    cities: list[str]


class ForecastResponse(BaseModel):
    city: str
    as_of_date: date
    target_date: date
    pm25_forecast: float = Field(ge=0)
    unit: Literal["ug/m3"] = "ug/m3"
    label: Literal["static data snapshot"] = "static data snapshot"
    model_name: str
    model_version: str


class HistoryPoint(BaseModel):
    date: date
    pm25: float | None


class HistoryResponse(BaseModel):
    city: str
    days: int
    rows: list[HistoryPoint]


class BacktestPoint(BaseModel):
    date: date
    station_matched: bool
    y_true: float | None
    y_pred_best: float | None
    y_pred_persistence: float | None


class BacktestResponse(BaseModel):
    city: str
    split: Literal["val", "test_a", "test_b"]
    rows: list[BacktestPoint]


class ModelsResponse(BaseModel):
    selected_config: dict[str, Any]
    best_model: str
    summary_configs: list[dict[str, Any]]
    model_metrics: list[dict[str, Any]]
    split_dates: dict[str, Any]


class DriftResponse(BaseModel):
    method: str
    reference_period: dict[str, Any]
    comparisons: dict[str, Any]
