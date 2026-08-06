from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "goals-milestones-service"
    env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./goals_dev.db")
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "")
    amqp_exchange: str = "afrimentor.events"


@lru_cache
def get_settings() -> Settings:
    return Settings()
