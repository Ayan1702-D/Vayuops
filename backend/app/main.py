"""FastAPI endpoints backed by a static, startup-loaded model snapshot."""

from __future__ import annotations

import math
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.core.errors import api_error
from app.core.logging import configure_logging
from app.schemas import (
    BacktestPoint, BacktestResponse, CitiesResponse, DriftResponse, ForecastResponse,
    HealthResponse, HistoryPoint, HistoryResponse, ModelsResponse,
)
from app.services.model_loader import AssetStore, load_assets


def finite_or_none(value: object) -> float | None:
    """Convert nullable parquet numbers to JSON-safe floats."""
    if pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def get_store(request: Request) -> AssetStore:
    """Require a complete startup snapshot for every data endpoint."""
    store = getattr(request.app.state, "assets", None)
    if store is None:
        message = getattr(request.app.state, "asset_error", "Assets have not loaded")
        raise api_error(503, "asset_unavailable", message)
    return store


def known_city(store: AssetStore, city: str) -> str:
    name = city.strip().lower()
    if name not in set(store.serving["city"].astype(str)):
        raise api_error(404, "unknown_city", f"Unknown city: {city}")
    return name


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an independently testable application with one asset load per lifespan."""
    config = settings or Settings()
    logger = configure_logging()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            application.state.assets = load_assets(config.assets_dir)
            application.state.asset_error = None
            logger.info("assets_loaded", extra={"asset": str(config.assets_dir)})
        except (OSError, ValueError, ImportError) as exc:
            application.state.assets = None
            application.state.asset_error = str(exc)
            logger.error("assets_unavailable", extra={"asset": str(config.assets_dir)})
        yield
        application.state.assets = None

    application = FastAPI(title="VayuOps API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware, allow_origins=config.allowed_origins,
        allow_credentials=False, allow_methods=["GET"], allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_log_and_cache(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["Cache-Control"] = (
            "public, max-age=300" if response.status_code < 400 and request.url.path != "/health"
            else "no-store"
        )
        logger.info("http_request", extra={
            "method": request.method, "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        })
        return response

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "code": "http_error", "message": str(exc.detail),
        }
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "Invalid request parameters",
            "details": jsonable_encoder(exc.errors()),
        }})

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        logger.exception("unhandled_error", exc_info=exc)
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "Internal server error",
        }})

    @application.get("/health", response_model=HealthResponse)
    def health(store: AssetStore = Depends(get_store)) -> HealthResponse:
        selected = store.metadata["selected_config"]
        return HealthResponse(
            status="ok", model_name=str(selected["model"]),
            model_version=str(selected["config_id"]),
            data_as_of_date=pd.to_datetime(store.serving["date"]).max().date(),
        )

    @application.get("/cities", response_model=CitiesResponse)
    def cities(store: AssetStore = Depends(get_store)) -> CitiesResponse:
        return CitiesResponse(cities=sorted(store.serving["city"].astype(str).unique()))

    @application.get("/forecast", response_model=ForecastResponse)
    def forecast(city: str, store: AssetStore = Depends(get_store)) -> ForecastResponse:
        name = known_city(store, city)
        row = store.serving.loc[store.serving["city"].eq(name)]
        columns = store.metadata["features"]
        raw = float(store.model.predict(row[columns])[0])
        if store.metadata["selected_config"].get("target_mode") == "delta_log":
            import numpy as np

            delta = float(np.clip(raw, -2, 2))
            raw = float(np.expm1(np.log1p(float(row.iloc[0]["pm25_t"])) + delta))
            # The registry does not currently export the training city maximum.
            raw = max(0.0, raw)
        if not math.isfinite(raw) or raw < 0:
            raise api_error(503, "prediction_unavailable", "Model returned an invalid forecast")
        as_of = pd.Timestamp(row.iloc[0]["date"]).date()
        selected = store.metadata["selected_config"]
        return ForecastResponse(
            city=name, as_of_date=as_of, target_date=as_of + timedelta(days=1),
            pm25_forecast=raw, model_name=str(selected["model"]),
            model_version=str(selected["config_id"]),
        )

    @application.get("/history", response_model=HistoryResponse)
    def history(
        city: str, store: AssetStore = Depends(get_store),
        days: int = Query(default=30, ge=1, le=400),
    ) -> HistoryResponse:
        name = known_city(store, city)
        frame = store.history.loc[store.history["city"].eq(name)].sort_values("date")
        if not frame.empty:
            cutoff = pd.Timestamp(frame["date"].max()) - pd.Timedelta(days=days - 1)
            frame = frame.loc[pd.to_datetime(frame["date"]).ge(cutoff)]
        return HistoryResponse(city=name, days=days, rows=[
            HistoryPoint(date=pd.Timestamp(row.date).date(), pm25=finite_or_none(row.pm25))
            for row in frame.itertuples(index=False)
        ])

    @application.get("/backtest", response_model=BacktestResponse)
    def backtest(
        city: str, split: Literal["val", "test_a", "test_b"],
        store: AssetStore = Depends(get_store),
    ) -> BacktestResponse:
        name = known_city(store, city)
        frame = store.backtest.loc[
            store.backtest["city"].eq(name) & store.backtest["split"].eq(split)
        ].sort_values("date")
        return BacktestResponse(city=name, split=split, rows=[
            BacktestPoint(
                date=pd.Timestamp(row.date).date(),
                station_matched=bool(row.station_matched),
                y_true=finite_or_none(row.y_true),
                y_pred_best=finite_or_none(row.y_pred_best),
                y_pred_persistence=finite_or_none(row.y_pred_persistence),
            ) for row in frame.itertuples(index=False)
        ])

    @application.get("/models", response_model=ModelsResponse)
    def models(store: AssetStore = Depends(get_store)) -> ModelsResponse:
        data = store.results
        return ModelsResponse(
            selected_config=store.metadata["selected_config"],
            best_model=data["best_model"],
            summary_configs=data["summary_configs"],
            model_metrics=data["model_metrics"],
            split_dates=data["split_dates"],
        )

    @application.get("/drift", response_model=DriftResponse)
    def drift(store: AssetStore = Depends(get_store)) -> DriftResponse:
        return DriftResponse.model_validate(store.drift)

    return application


app = create_app()
