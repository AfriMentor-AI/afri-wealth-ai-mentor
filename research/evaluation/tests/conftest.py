"""Offline test setup for the persona-vector probing module (card C3.3).

``persona_probe`` imports numpy at module load (a CPU dependency that IS present)
and defers torch / transformers / peft to inside :class:`HFActivationExtractor`,
so the extract → probe → diagnose pipeline is exercised here with an injected fake
activation function — no model, no GPU, no network.

These stubs cover the two optional deps the pipeline touches lazily:
  * ``mlflow`` — imported inside ``log_probe_to_mlflow`` and at the top of the
    ``probe.py`` runner; stubbed as an inert MagicMock so both import.
  * ``torch`` — imported inside the runner's GPU gate; stubbed to report **no
    CUDA**, so ``probe.run()`` deterministically takes its safe no-op path.
Each is stubbed only if genuinely absent, so a real install (a GPU node) is used
as-is.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# research/ root on path so `evaluation.*` resolves.
RESEARCH_ROOT = Path(__file__).resolve().parents[2]
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

if "mlflow" not in sys.modules:
    sys.modules["mlflow"] = MagicMock(name="mlflow")

if "torch" not in sys.modules:
    _torch = MagicMock(name="torch")
    _torch.cuda.is_available.return_value = False  # force the runner's no-GPU branch
    sys.modules["torch"] = _torch
