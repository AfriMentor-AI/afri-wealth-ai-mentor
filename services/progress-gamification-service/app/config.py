from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "progress-gamification-service"
    env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./progress_dev.db")
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "")
    amqp_exchange: str = "afrimentor.events"
    # Rolling window (days) the activity heatmap reports (card O3.1).
    heatmap_window_days: int = int(os.getenv("HEATMAP_WINDOW_DAYS", "84"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
