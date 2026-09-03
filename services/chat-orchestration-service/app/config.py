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
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    llm_streaming_enabled: bool = (
        os.getenv("LLM_STREAMING_ENABLED", "true").strip().lower() == "true"
    )
    cache_ttl_seconds: float = float(os.getenv("CHAT_CACHE_TTL_SECONDS", "300"))
    cache_max_entries: int = int(os.getenv("CHAT_CACHE_MAX_ENTRIES", "256"))
    http_pool_max_connections: int = int(os.getenv("HTTP_POOL_MAX_CONNECTIONS", "120"))
    http_pool_max_keepalive: int = int(os.getenv("HTTP_POOL_MAX_KEEPALIVE", "60"))
    guardrails_stream_check_interval: int = int(os.getenv("GUARDRAILS_STREAM_CHECK_INTERVAL", "4"))

    # RabbitMQ exchange (ADR-0001 §D3)
    amqp_exchange: str = "afrimentor.events"

    # Commitment detection: keyword hints used by the stub detector
    commitment_keywords: list[str] = [
        "i will", "i'll", "i commit", "i promise", "i plan to",
        "my goal is", "i'm going to", "i intend to",
    ]

    # Guardrails (card C2.4). Defaults ON: an unset or misspelled env var must
    # leave the high-risk-advice filter running, not silently disable it. Only
    # the exact string "false" turns it off, so GUARDRAILS_ENABLED=0 or "no"
    # will not accidentally open the gate.
    guardrails_enabled: bool = os.getenv("GUARDRAILS_ENABLED", "true").strip().lower() != "false"

    # CHIOMA alignment condition (Sprint 4 comparative eval — card D1.4).
    # Identifies which research alignment condition is active in production.
    # "C4" (RLHF / Preference Optimization, composite 0.654) is the Sprint 4
    # winner; update to "C4-gpu" once the afrimentor/chioma-rlhf-v1 adapter
    # is trained and the service is pointed at it.
    chioma_alignment_condition: str = os.getenv("CHIOMA_ALIGNMENT_CONDITION", "C4")


@lru_cache
def get_settings() -> Settings:
    return Settings()