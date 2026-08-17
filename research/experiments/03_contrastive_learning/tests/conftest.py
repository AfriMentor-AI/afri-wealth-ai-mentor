"""Offline test setup for the C3 contrastive-learning runner (card C3.1).

The C3 pipeline depends on the ML training/eval stack — torch, the TRL/PEFT
trainer, MLflow, and the OpenAI-compatible judge client — that is intentionally
NOT installed outside GPU nodes (see research/requirements-gpu.txt). These stubs
let the runner's control flow and the metric-suite wiring be exercised on a bare
interpreter:

  * torch reports **no CUDA**, so train() deterministically takes its no-GPU path;
  * mlflow / openai are inert MagicMocks (individual tests swap in their own to
    assert on logged metrics).

Generation and the LLM judge are injected / patched per test, so no network call
or model load ever happens.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# research/ root on path so `evaluation.*` and the runner resolve.
RESEARCH_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

# Stub only if genuinely absent, so a real install (on a GPU node) is used as-is.
for _name in ("mlflow", "openai"):
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock(name=_name)

if "torch" not in sys.modules:
    _torch = MagicMock(name="torch")
    _torch.cuda.is_available.return_value = False  # force train()'s no-GPU branch
    sys.modules["torch"] = _torch
