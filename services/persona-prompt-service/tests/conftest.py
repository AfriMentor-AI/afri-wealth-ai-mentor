from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT_STR = str(SERVICE_ROOT)

if SERVICE_ROOT_STR not in sys.path:
    sys.path.insert(0, SERVICE_ROOT_STR)


@pytest.fixture()
def beta_personas_enabled(monkeypatch):
    """Flip ENABLE_BETA_PERSONAS on for one test (card C4.4).

    Settings.enable_beta_personas uses a default_factory so it re-reads the env
    var on each Settings() construction — cache_clear() forces that re-read.
    """
    from app.config import get_settings

    monkeypatch.setenv("ENABLE_BETA_PERSONAS", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
