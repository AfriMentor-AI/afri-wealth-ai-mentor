"""Configuration for intake-profiling-service (card O2.2)."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "intake-profiling-service"
    env: str = os.getenv("APP_ENV", "dev")

    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite+pysqlite:///./intake_dev.db"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
