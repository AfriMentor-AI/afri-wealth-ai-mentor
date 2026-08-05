"""Loader for the CHIOMA target personality profile.

v0 reads a local JSON stand-in (``data/chioma_profile.v0.json``). Card C1.4
publishes the canonical versioned profile from persona-prompt-service; when it
lands, point ``CHIOMA_PROFILE_PATH`` at it — the schema here is the contract.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

#: Ordinal target levels mapped onto the [0, 1] scale the metrics operate in.
LEVEL_VALUES: dict[str, float] = {
    "VERY_LOW": 0.05,
    "LOW": 0.25,
    "MODERATE_LOW": 0.40,
    "MODERATE": 0.50,
    "MODERATE_HIGH": 0.70,
    "HIGH": 0.85,
    "VERY_HIGH": 0.95,
}

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "chioma_profile.v0.json"


class TraitTarget(BaseModel):
    """One trait's target level and the lexical evidence used to estimate it."""

    key: str
    label: str
    target_level: str
    behaviour: str
    markers: list[str] = Field(default_factory=list)
    counter_markers: list[str] = Field(default_factory=list)

    @property
    def target_value(self) -> float:
        try:
            return LEVEL_VALUES[self.target_level]
        except KeyError as exc:
            raise ValueError(
                f"trait {self.key!r} has unknown target_level {self.target_level!r}; "
                f"expected one of {sorted(LEVEL_VALUES)}"
            ) from exc


class TargetProfile(BaseModel):
    """The full CHIOMA target: Big Five plus the distinctive trait additions."""

    schema_version: str
    profile_id: str
    profile_version: str
    display_name: str
    traits: list[TraitTarget]
    distinctive_traits: list[TraitTarget] = Field(default_factory=list)

    @property
    def all_traits(self) -> list[TraitTarget]:
        """Big Five first, then distinctive additions. Order is the vector order."""
        return [*self.traits, *self.distinctive_traits]

    def by_key(self, key: str) -> TraitTarget | None:
        return next((t for t in self.all_traits if t.key == key), None)

    def target_vector(self, include_distinctive: bool = True) -> list[float]:
        traits = self.all_traits if include_distinctive else self.traits
        return [t.target_value for t in traits]


@lru_cache(maxsize=4)
def _load_cached(path_str: str) -> TargetProfile:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(
            f"CHIOMA profile not found at {path}. Set CHIOMA_PROFILE_PATH or restore "
            f"{DEFAULT_PROFILE_PATH.name}."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = TargetProfile.model_validate(data)
    # Surface a bad target_level at load time rather than mid-scoring.
    for trait in profile.all_traits:
        _ = trait.target_value
    return profile


def load_profile(path: str | Path | None = None) -> TargetProfile:
    """Load the target profile.

    Resolution order: explicit ``path`` → ``CHIOMA_PROFILE_PATH`` env var →
    the bundled v0 stand-in.
    """
    resolved = path or os.getenv("CHIOMA_PROFILE_PATH") or DEFAULT_PROFILE_PATH
    return _load_cached(str(resolved))
