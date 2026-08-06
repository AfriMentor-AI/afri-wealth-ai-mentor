from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "persona-prompt-service"
    env: str = os.getenv("APP_ENV", "dev")
    chat_service_url: str = os.getenv("CHAT_SERVICE_URL", "http://localhost:8003")


@lru_cache
def get_settings() -> Settings:
    return Settings()
