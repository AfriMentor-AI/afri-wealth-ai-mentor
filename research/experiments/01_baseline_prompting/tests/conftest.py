from __future__ import annotations

import sys
from pathlib import Path

# research/ root on path so `evaluation`, `experiments` packages resolve
RESEARCH_ROOT = Path(__file__).resolve().parents[3]
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))
