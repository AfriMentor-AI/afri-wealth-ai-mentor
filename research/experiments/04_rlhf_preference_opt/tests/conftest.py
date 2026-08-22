"""Pytest configuration for the C4 RLHF test suite.

Patches torch.cuda.is_available() → False for all tests in this suite so
the GPU guards in the runner always take the CPU path, keeping tests offline.
"""
from __future__ import annotations

import importlib.util
from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def no_cuda(monkeypatch):
    """Ensure every test runs as if there is no CUDA GPU."""
    if importlib.util.find_spec("torch") is not None:
        with patch("torch.cuda.is_available", return_value=False):
            yield
    else:
        yield

