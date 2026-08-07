"""C2.3 — probe administration against the persona-prompted baseline model.

The live model is never called here: ``httpx`` transports are stubbed so the tests
stay hermetic and free. What is verified is everything around the call — that the
persona prompt is actually sent, that fixture answers are replaced by model output,
that failures are retried and then surfaced, and that a fixture run cannot be
mistaken for a real baseline.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.llm import (
    AdministeredProbe,
    LLMConfig,
    ProbeAdministrationError,
    administer_probe,
    administer_probes,
    build_system_prompt_local,
    fetch_system_prompt,
)
from app.metrics.profile import load_profile
from app.metrics.schemas import ProbeResponse
from scripts.run_trait_fit import DEFAULT_PROBE_PATH, load_probes, run_experiment

TEST_CONFIG = LLMConfig(api_key="test-key", model="test-model", max_retries=2)


def _completion(text: str, finish_reason: str = "stop") -> dict:
    """Minimal OpenAI-compatible chat-completions payload."""
    return {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


#: Bound before any patching. Tests patch ``app.llm.httpx.Client`` — which is the
#: real httpx module attribute — so the factory below must not go through the name
#: it is replacing, or it recurses into its own stub.
_REAL_CLIENT = httpx.Client


def _client_returning(handler) -> httpx.Client:
    return _REAL_CLIENT(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer test-key"},
    )


def _persona_response(url, timeout=None, version: str | None = None) -> httpx.Response:
    """Stub persona-prompt-service reply, with the request set so raise_for_status works."""
    return httpx.Response(
        200,
        json={
            "profile_id": "chioma",
            "profile_version": version or load_profile().profile_version,
            "system_prompt": "You are CHIOMA.",
        },
        request=httpx.Request("GET", url),
    )


# ── Config ────────────────────────────────────────────────────────────────────


def test_config_is_live_requires_api_key():
    assert not LLMConfig(api_key="").is_live
    assert LLMConfig(api_key="sk-x").is_live


def test_config_from_env_defaults_to_deterministic_sampling(monkeypatch):
    """A baseline is compared against later runs, so it must not vary run to run."""
    monkeypatch.delenv("PROBE_TEMPERATURE", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    assert LLMConfig.from_env().temperature == 0.0


def test_config_from_env_reads_shared_llm_vars(monkeypatch):
    """Same var names as chat-orchestration-service, so both point at one model."""
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1/")
    config = LLMConfig.from_env()
    assert config.model == "custom-model"
    assert config.base_url == "https://example.test/v1"  # trailing slash stripped


# ── System prompt ─────────────────────────────────────────────────────────────


def test_local_prompt_contains_every_trait_behaviour():
    profile = load_profile()
    prompt = build_system_prompt_local(profile)
    assert profile.display_name in prompt
    for trait in profile.all_traits:
        assert trait.behaviour in prompt


def test_fetch_prompt_prefers_persona_service():
    profile = load_profile()

    with patch("app.llm.httpx.get", lambda url, timeout: _persona_response(url, version=profile.profile_version)):
        prompt, provenance = fetch_system_prompt(profile, persona_service_url="http://persona:8004")

    assert "You are CHIOMA" in prompt
    assert provenance.startswith("persona-prompt-service:")


def test_fetch_prompt_falls_back_when_service_unreachable():
    profile = load_profile()

    def boom(url, timeout):
        raise httpx.ConnectError("connection refused")

    with patch("app.llm.httpx.get", boom):
        prompt, provenance = fetch_system_prompt(profile, persona_service_url="http://persona:8004")

    assert provenance == "local-fallback"
    assert profile.display_name in prompt


def test_fetch_prompt_warns_on_profile_version_mismatch(caplog):
    """Prompting with one profile version and scoring against another is silent drift."""
    profile = load_profile()

    with patch("app.llm.httpx.get", lambda url, timeout: _persona_response(url, version="v99-divergent")), \
         caplog.at_level("WARNING"):
        _, provenance = fetch_system_prompt(profile, persona_service_url="http://persona:8004")

    assert "v99-divergent" in provenance
    assert "version mismatch" in caplog.text


def test_fetch_prompt_local_when_url_unset(monkeypatch):
    monkeypatch.delenv("PERSONA_SERVICE_URL", raising=False)
    prompt, provenance = fetch_system_prompt(load_profile())
    assert provenance == "local"
    assert prompt


# ── Single probe ──────────────────────────────────────────────────────────────


def test_administer_probe_sends_persona_prompt_and_question():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_completion("I hold her to the commitment."))

    with _client_returning(handler) as client:
        result = administer_probe("What do you do?", "You are CHIOMA.", TEST_CONFIG, client=client)

    assert result.answer == "I hold her to the commitment."
    assert captured["messages"][0] == {"role": "system", "content": "You are CHIOMA."}
    assert captured["messages"][1] == {"role": "user", "content": "What do you do?"}
    assert captured["temperature"] == 0.0
    assert captured["model"] == "test-model"


def test_administer_probe_flags_truncated_answer():
    """finish_reason=length means trailing trait markers were cut off."""
    def handler(request):
        return httpx.Response(200, json=_completion("I hold her to the com", finish_reason="length"))

    with _client_returning(handler) as client:
        result = administer_probe("Q?", "prompt", TEST_CONFIG, client=client)

    assert result.truncated is True


def test_administer_probe_rejects_empty_answer():
    def handler(request):
        return httpx.Response(200, json=_completion("   "))

    with _client_returning(handler) as client, pytest.raises(ProbeAdministrationError, match="empty answer"):
        administer_probe("Q?", "prompt", TEST_CONFIG, client=client)


def test_administer_probe_rejects_malformed_payload():
    def handler(request):
        return httpx.Response(200, json={"unexpected": "shape"})

    with _client_returning(handler) as client, pytest.raises(ProbeAdministrationError, match="malformed"):
        administer_probe("Q?", "prompt", TEST_CONFIG, client=client)


def test_administer_probe_retries_transient_failure_then_succeeds():
    """A 429 mid-run must not discard the whole probe set."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_completion("Recovered answer."))

    with patch("app.llm.time.sleep"), _client_returning(handler) as client:
        result = administer_probe("Q?", "prompt", TEST_CONFIG, client=client)

    assert calls["n"] == 2
    assert result.answer == "Recovered answer."


def test_administer_probe_raises_after_exhausting_retries():
    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    with patch("app.llm.time.sleep"), _client_returning(handler) as client:
        with pytest.raises(ProbeAdministrationError, match="failed after 2 attempts"):
            administer_probe("Q?", "prompt", TEST_CONFIG, client=client)


# ── Probe set ─────────────────────────────────────────────────────────────────


def test_administer_probes_replaces_fixture_answers():
    """The core C2.3 requirement: scored answers come from the model, not the file."""
    probe_set = load_probes(DEFAULT_PROBE_PATH)
    fixture_answers = {p.answer for p in probe_set}

    def handler(request):
        return httpx.Response(200, json=_completion("A fresh answer from the model."))

    with patch("app.llm.httpx.Client", lambda **kw: _client_returning(handler)):
        administered = administer_probes(probe_set, "You are CHIOMA.", config=TEST_CONFIG)

    assert len(administered) == len(probe_set)
    assert all(p.answer == "A fresh answer from the model." for p in administered)
    assert all(p.answer not in fixture_answers for p in administered)
    # Instrument metadata is carried through from the probe set, not invented.
    assert [p.probe_id for p in administered] == [p.probe_id for p in probe_set]
    assert [p.trait for p in administered] == [p.trait for p in probe_set]
    assert [p.reverse_scored for p in administered] == [p.reverse_scored for p in probe_set]


def test_administer_probes_requires_api_key():
    probe_set = load_probes(DEFAULT_PROBE_PATH)
    with pytest.raises(ProbeAdministrationError, match="LLM_API_KEY is not set"):
        administer_probes(probe_set, "prompt", config=LLMConfig(api_key=""))


def test_administered_probe_converts_to_scorable_response():
    probe = AdministeredProbe(
        probe_id="bfi-c-01",
        trait="conscientiousness",
        question="Q?",
        answer="A.",
        reverse_scored=True,
    )
    response = probe.to_response()
    assert isinstance(response, ProbeResponse)
    assert response.probe_id == "bfi-c-01"
    assert response.reverse_scored is True


# ── End-to-end live run ───────────────────────────────────────────────────────


def _in_memory_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.audit import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


def test_run_experiment_live_scores_model_answers(tmp_path):
    """End-to-end with a stubbed model: report records real provenance."""
    engine, Session = _in_memory_session()
    out_file = tmp_path / "live.json"

    answer = (
        "I hold her to the commitment. We review week by week, then set a "
        "concrete deadline and track it. You decide the next step, not me."
    )

    def handler(request):
        return httpx.Response(200, json=_completion(answer))

    with patch("scripts.run_trait_fit.engine", engine), \
         patch("scripts.run_trait_fit.SessionLocal", Session), \
         patch("app.llm.httpx.Client", lambda **kw: _client_returning(handler)), \
         patch("app.llm.httpx.get", lambda url, timeout: _persona_response(url)):
        result = run_experiment(
            model_id="qwen-baseline",
            name="live-run-001",
            out_path=out_file,
            live=True,
            llm_config=TEST_CONFIG,
        )

    assert result["status"] == "completed"
    assert result["answer_source"] == "model"
    # No fixture suffix: this one is a real baseline.
    assert result["model_id"] == "qwen-baseline"
    assert result["llm_model"] == "test-model"
    assert result["llm_temperature"] == 0.0

    administered = result["administered_probes"]
    assert len(administered) > 0
    assert all(p["answer"] == answer for p in administered)

    # Answers are auditable from the saved report, not just the score.
    saved = json.loads(out_file.read_text())
    assert saved["administered_probes"][0]["answer"] == answer


def test_run_experiment_live_without_key_fails_loudly():
    """Silently degrading to fixtures would publish a fake baseline."""
    engine, Session = _in_memory_session()
    with patch("scripts.run_trait_fit.engine", engine), \
         patch("scripts.run_trait_fit.SessionLocal", Session):
        with pytest.raises(ProbeAdministrationError, match="LLM_API_KEY is not set"):
            run_experiment(name="no-key", live=True, llm_config=LLMConfig(api_key=""))


def test_run_experiment_fixture_mode_is_labelled():
    engine, Session = _in_memory_session()
    with patch("scripts.run_trait_fit.engine", engine), \
         patch("scripts.run_trait_fit.SessionLocal", Session):
        result = run_experiment(model_id="plumbing", name="fixture-run", live=False)

    assert result["answer_source"] == "fixtures"
    assert result["model_id"] == "plumbing+fixture-answers"
    assert result["administered_probes"] == []
    assert any("not a valid model baseline" in w for w in result["probe_trait_fit"]["warnings"])


def test_run_experiment_records_model_failure_on_the_run():
    """A crashed run must leave evidence, not vanish."""
    from app.models.audit import ExperimentRun, ExperimentStatus

    engine, Session = _in_memory_session()

    def handler(request):
        return httpx.Response(500, json={"error": "upstream exploded"})

    with patch("scripts.run_trait_fit.engine", engine), \
         patch("scripts.run_trait_fit.SessionLocal", Session), \
         patch("app.llm.time.sleep"), \
         patch("app.llm.httpx.Client", lambda **kw: _client_returning(handler)), \
         patch("app.llm.httpx.get", lambda url, timeout: _persona_response(url)):
        with pytest.raises(ProbeAdministrationError):
            run_experiment(name="doomed-run", live=True, llm_config=TEST_CONFIG)

    db = Session()
    run = db.query(ExperimentRun).filter_by(name="doomed-run").first()
    assert run is not None
    assert run.status == ExperimentStatus.failed
    assert run.error_message
    db.close()
