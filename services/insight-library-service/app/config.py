from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "insight-library-service"
    env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./insight_dev.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
