from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "notification-service"
    env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./notification_dev.db")
    progress_service_url: str = os.getenv("PROGRESS_SERVICE_URL", "http://localhost:8007")
    # v0 scaffold (card O3.4): how often the background sweep runs. Long default
    # in prod; override low in dev/demo to see it fire without waiting.
    sweep_interval_seconds: int = int(os.getenv("SWEEP_INTERVAL_SECONDS", "3600"))
    upstream_timeout_seconds: float = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "5"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
