from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "persona-prompt-service"
    env: str = os.getenv("APP_ENV", "dev")
    chat_service_url: str = os.getenv("CHAT_SERVICE_URL", "http://localhost:8003")
    # card C4.4: gates `status: beta` personas (e.g. KWAME). default_factory, not a
    # bare os.getenv(...) default, so the env var is re-read on every Settings()
    # instantiation instead of being baked in once at import time — tests need to
    # toggle this per-case via monkeypatch + get_settings.cache_clear().
    enable_beta_personas: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_BETA_PERSONAS", "false").lower() == "true"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
