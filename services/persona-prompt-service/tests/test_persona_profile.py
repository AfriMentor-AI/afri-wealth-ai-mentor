"""Unit tests for Persona Prompt Service & C1.4 profile spec."""

from fastapi.testclient import TestClient

from app.loader import (
    CANONICAL_PROFILE_PATH,
    SCHEMA_PATH,
    PersonaProfileSpec,
    load_persona_profile,
)
from app.main import app
from app.prompts import build_system_prompt

client = TestClient(app)


def test_canonical_profile_exists_and_validates():
    assert CANONICAL_PROFILE_PATH.is_file()
    assert SCHEMA_PATH.is_file()

    profile = load_persona_profile()
    assert isinstance(profile, PersonaProfileSpec)
    assert profile.profile_id == "chioma"
    assert profile.profile_version == "v1"
    assert len(profile.traits) == 5
    assert len(profile.distinctive_traits) == 4
    assert len(profile.all_traits) == 9


def test_build_system_prompt():
    profile = load_persona_profile()
    prompt = build_system_prompt(profile)
    assert "CHIOMA" in prompt
    assert "Conscientiousness" in prompt
    assert "Urgency & Action Bias" in prompt


def test_api_endpoints():
    r_health = client.get("/health")
    assert r_health.status_code == 200

    r_chioma = client.get("/personas/chioma")
    assert r_chioma.status_code == 200
    data = r_chioma.json()
    assert data["profile_id"] == "chioma"
    assert data["profile_version"] == "v1"
    assert len(data["traits"]) == 5

    r_prompt = client.get("/personas/chioma/prompt")
    assert r_prompt.status_code == 200
    prompt_data = r_prompt.json()
    assert prompt_data["profile_id"] == "chioma"
    assert "CHIOMA" in prompt_data["system_prompt"]
