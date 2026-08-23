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

    # Nightly consistency scoring job (card C3.2). The scheduler runs in-process;
    # disable it in tests or one-off containers via ENABLE_SCHEDULER=false.
    enable_scheduler: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    consistency_sample_size: int = int(os.getenv("CONSISTENCY_SAMPLE_SIZE", "20"))

    # Live consistency cadence (card C4.1). The nightly cron (C3.2) establishes a
    # daily baseline; this short interval keeps the dashboard's aggregate score
    # live-updating from real sessions. Set CONSISTENCY_INTERVAL_MINUTES=0 to
    # disable the interval and keep only the nightly run.
    consistency_interval_minutes: int = int(os.getenv("CONSISTENCY_INTERVAL_MINUTES", "2"))
    # A still-active conversation must be idle this long before it is eligible for
    # scoring. Nothing in the pilot marks a conversation 'completed', so scoring
    # idle-but-active sessions is what feeds the live dashboard; the idle gate keeps
    # mid-reply conversations out. Set to 0 to score any active session immediately.
    session_idle_minutes: int = int(os.getenv("SESSION_IDLE_MINUTES", "10"))

    # Drift-threshold alerting (card O4.1). A persona's run-mean aggregate is
    # compared against its own rolling baseline (prior job runs only); crossing
    # this percent deviation fires a DriftAlert. Mirrors the ~14% deviation the
    # Research Console mockup uses as its illustrative alert copy.
    drift_threshold_pct: float = float(os.getenv("DRIFT_THRESHOLD_PCT", "15.0"))
    drift_baseline_window: int = int(os.getenv("DRIFT_BASELINE_WINDOW", "10"))

    # Manual audit workflow (card C4.2). A session whose raw consistency aggregate
    # is below this absolute floor is auto-flagged for human review, independent of
    # persona drift. The drift arm of the flag rule intentionally reuses
    # ``drift_threshold_pct`` above — but note the granularity differs: that
    # threshold gates a persona's *run-mean* deviation for DriftAlert (card O4.1),
    # whereas the review flag applies it to each *session's* own delta, which is
    # noisier. A session can therefore be flagged for review without a DriftAlert
    # firing, and vice-versa. (A future CONSISTENCY_REVIEW_DRIFT_PCT could decouple
    # the two sensitivities; not needed yet.)
    consistency_review_floor: float = float(os.getenv("CONSISTENCY_REVIEW_FLOOR", "0.70"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
