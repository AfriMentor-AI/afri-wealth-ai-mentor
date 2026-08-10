"""Personality-consistency metric suite v0 (card C1.3).

Two metric families, per the C1.3 card and Abdulhai et al. (2025):

* **Trait-level fit** — administer BFI/TRAIT-style probes, estimate a Big Five
  trait vector from the responses, and compare it against the CHIOMA target
  profile by cosine similarity. See :mod:`app.metrics.trait_fit`.
* **Behavioral consistency** — prompt-to-line, line-to-line and Q&A consistency
  over a multi-turn dialogue. See :mod:`app.metrics.consistency`.

The scoring backend is pluggable (:mod:`app.metrics.scoring`). v0 ships a
deterministic lexical scorer with no ML dependencies so the suite runs in CI;
C2.3 can substitute an embedding-based scorer without touching metric code.
"""

from app.metrics.profile import TargetProfile, TraitTarget, load_profile
from app.metrics.report import EvaluationReport, score_dialogue, score_dialogues
from app.metrics.schemas import Dialogue, ProbeResponse, Turn

__all__ = [
    "Dialogue",
    "EvaluationReport",
    "ProbeResponse",
    "TargetProfile",
    "TraitTarget",
    "Turn",
    "load_profile",
    "score_dialogue",
    "score_dialogues",
]
