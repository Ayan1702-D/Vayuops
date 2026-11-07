"""Backend configuration read from environment variables."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the immutable model snapshot API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assets_dir: Path = Path(__file__).resolve().parent / "assets"
    cors_origins: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        """Accept comma-separated origins or a JSON array in CORS_ORIGINS."""
        raw = self.cors_origins.strip()
        if not raw:
            return []
        if raw.startswith("["):
            origins = json.loads(raw)
            if not isinstance(origins, list) or not all(isinstance(x, str) for x in origins):
                raise ValueError("CORS_ORIGINS must be a list of strings")
            return [origin.strip() for origin in origins if origin.strip()]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
