"""Pydantic v2 models for dialogues, probes and metric results."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Speaker(str, Enum):
    """Who produced a turn. Only ``mentor`` turns are scored for persona fit."""

    user = "user"
    mentor = "mentor"


class Turn(BaseModel):
    """A single utterance in a dialogue."""

    speaker: Speaker
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("turn text must not be blank")
        return stripped


class Dialogue(BaseModel):
    """A multi-turn conversation to be scored.

    ``system_prompt`` is the persona instruction the mentor was given; it is the
    anchor for the prompt-to-line consistency metric.
    """

    dialogue_id: str
    system_prompt: str = Field(min_length=1)
    turns: list[Turn] = Field(min_length=1)
    notes: str | None = None

    @property
    def mentor_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.speaker is Speaker.mentor]


class ProbeResponse(BaseModel):
    """One BFI/TRAIT-style probe and the mentor's free-text answer.

    ``trait`` names the Big Five trait the probe targets. ``reverse_scored``
    marks probes phrased against the trait, whose contribution is inverted.
    """

    probe_id: str
    trait: str
    question: str
    answer: str = Field(min_length=1)
    reverse_scored: bool = False


class TraitScore(BaseModel):
    """Estimated vs target level for a single trait."""

    trait: str
    label: str
    target_level: str
    target_value: float = Field(ge=0.0, le=1.0)
    observed_value: float = Field(ge=0.0, le=1.0)
    delta: float
    evidence_count: int = 0


class TraitFitResult(BaseModel):
    """Trait-level fit: per-trait estimates plus overall cosine similarity."""

    cosine_similarity: float = Field(ge=-1.0, le=1.0)
    mean_absolute_error: float = Field(ge=0.0)
    per_trait: list[TraitScore]
    source: Literal["probes", "dialogue"] = "dialogue"

    @property
    def worst_trait(self) -> TraitScore | None:
        if not self.per_trait:
            return None
        return max(self.per_trait, key=lambda t: abs(t.delta))


class ConsistencyResult(BaseModel):
    """Behavioral consistency, per Abdulhai et al. (2025).

    All three sub-scores are in [0, 1], higher is more consistent.
    ``n_*`` fields record how many comparisons backed each score; a score
    computed from zero comparisons is reported as 1.0 and flagged by n == 0.
    """

    prompt_to_line: float = Field(ge=0.0, le=1.0)
    line_to_line: float = Field(ge=0.0, le=1.0)
    qa_consistency: float = Field(ge=0.0, le=1.0)
    n_prompt_to_line: int = 0
    n_line_to_line: int = 0
    n_qa_pairs: int = 0

    @property
    def aggregate(self) -> float:
        """Unweighted mean of the three sub-scores."""
        return round((self.prompt_to_line + self.line_to_line + self.qa_consistency) / 3, 4)
