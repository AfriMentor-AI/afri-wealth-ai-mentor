"""Configuration for chat-orchestration-service.

All values are read from environment variables; defaults allow the service and its
tests to run without Docker (SQLite + no RabbitMQ/LLM calls).
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "chat-orchestration-service"
    env: str = os.getenv("APP_ENV", "dev")

    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./chat_dev.db")
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "")

    # Downstream service URLs (populated by docker-compose; empty = stub mode)
    persona_service_url: str = os.getenv("PERSONA_SERVICE_URL", "")
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "")
    goals_service_url: str = os.getenv("GOALS_SERVICE_URL", "http://localhost:8006")

    # LLM — OpenAI-compatible (Groq / Together AI / local vLLM)
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_model: str = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    # RabbitMQ exchange (ADR-0001 §D3)
    amqp_exchange: str = "afrimentor.events"

    # Commitment detection: keyword hints used by the stub detector
    commitment_keywords: list[str] = [
        "i will", "i'll", "i commit", "i promise", "i plan to",
        "my goal is", "i'm going to", "i intend to",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
