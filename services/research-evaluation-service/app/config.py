"""Configuration for research-evaluation-service.

All values are read from environment variables; defaults allow the service and its
tests to run without Docker (SQLite + no RabbitMQ).
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "research-evaluation-service"
    env: str = os.getenv("APP_ENV", "dev")

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./research_evaluation.db")
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "")

    # RabbitMQ exchange (ADR-0001 §D3)
    amqp_exchange: str = "afrimentor.events"

    # Research salt for anonymization (anonymize_user_id function)
    research_salt: str = os.getenv("RESEARCH_SALT", "default-research-salt")


@lru_cache
def get_settings() -> Settings:
    return Settings()
