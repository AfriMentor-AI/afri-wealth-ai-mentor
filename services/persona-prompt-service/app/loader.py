"""Loader and validator for machine-readable persona target profile specs (card C1.4)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = SERVICE_ROOT / "data"
CANONICAL_PROFILE_PATH = DATA_DIR / "chioma_profile.v1.json"
SCHEMA_PATH = DATA_DIR / "schemas" / "persona_profile.schema.json"

LEVEL_VALUES: dict[str, float] = {
    "VERY_LOW": 0.05,
    "LOW": 0.25,
    "MODERATE_LOW": 0.40,
    "MODERATE": 0.50,
    "MODERATE_HIGH": 0.70,
    "HIGH": 0.85,
    "VERY_HIGH": 0.95,
}


class TraitTargetSpec(BaseModel):
    """Specification of a single personality trait target."""

    key: str
    label: str
    target_level: Literal[
        "VERY_LOW",
        "LOW",
        "MODERATE_LOW",
        "MODERATE",
        "MODERATE_HIGH",
        "HIGH",
        "VERY_HIGH",
    ]
    behaviour: str
    markers: list[str] = Field(default_factory=list)
    counter_markers: list[str] = Field(default_factory=list)

    @property
    def target_value(self) -> float:
        return LEVEL_VALUES[self.target_level]


class PersonaProfileSpec(BaseModel):
    """Full versioned persona profile specification."""

    schema_version: str
    profile_id: str
    profile_version: str
    display_name: str
    source: str | None = None
    traits: list[TraitTargetSpec]
    distinctive_traits: list[TraitTargetSpec] = Field(default_factory=list)

    @property
    def all_traits(self) -> list[TraitTargetSpec]:
        return [*self.traits, *self.distinctive_traits]

    def get_trait(self, key: str) -> TraitTargetSpec | None:
        return next((t for t in self.all_traits if t.key == key), None)


@lru_cache(maxsize=4)
def _load_cached(path_str: str) -> PersonaProfileSpec:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Persona profile spec not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PersonaProfileSpec.model_validate(data)


def load_persona_profile(path: str | Path | None = None) -> PersonaProfileSpec:
    """Load and validate the machine-readable persona profile spec."""
    resolved = Path(path) if path else CANONICAL_PROFILE_PATH
    return _load_cached(str(resolved))
