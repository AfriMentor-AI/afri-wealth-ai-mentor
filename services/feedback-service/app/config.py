from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "feedback-service"
    env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL") or "sqlite+pysqlite:///./feedback_dev.db"
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "")
    amqp_exchange: str = "afrimentor.events"
    amqp_queue: str = "feedback-service.milestone_completed"


@lru_cache
def get_settings() -> Settings:
    return Settings()
