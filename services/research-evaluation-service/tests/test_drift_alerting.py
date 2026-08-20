"""Card O4.1 — session audit fields and drift-threshold alerting tests."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.drift import (
    audit_fields_for_dialogue,
    classify_primary_intent,
    compute_persona_baseline,
    delta_pct,
    evaluate_drift_and_alert,
    extract_prompt_context,
)
from app.metrics.schemas import Dialogue, Speaker, Turn
from app.models.consistency_run import ConsistencyRun
from app.models.drift_alert import DriftAlert

ADMIN_HEADERS = {"X-User-Roles": "admin"}


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def add_run(Session, *, persona_id="chioma", job_run_id=None, aggregate=0.8, **kwargs):
    job_run_id = job_run_id or str(uuid.uuid4())
    db = Session()
    run = ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id=job_run_id,
        conversation_id=kwargs.get("conversation_id", f"conv-{uuid.uuid4().hex[:8]}"),
        persona_id=persona_id,
        prompt_to_line=aggregate,
        line_to_line=aggregate,
        qa_consistency=aggregate,
        aggregate=aggregate,
        turn_count=4,
        warnings_json="[]",
        primary_intent=kwargs.get("primary_intent"),
        prompt_context=kwargs.get("prompt_context"),
        scored_at=kwargs.get("scored_at", datetime.now(UTC)),
    )
    db.add(run)
    db.commit()
    db.close()
    return job_run_id


# ── Intent classification ────────────────────────────────────────────────────

def test_classify_primary_intent_matches_keywords():
    assert classify_primary_intent("How do I start saving money?") == "savings"
    assert classify_primary_intent("I have a loan I can't repay") == "debt_management"
    assert classify_primary_intent("Help me make a budget") == "budgeting"
    assert classify_primary_intent("Should I invest in shares?") == "investing"
    assert classify_primary_intent("My business needs more customers") == "business_growth"


def test_classify_primary_intent_falls_back_when_no_keyword_matches():
    assert classify_primary_intent("Tell me about the weather") == "general_mentorship"


def test_classify_primary_intent_handles_none_and_empty():
    assert classify_primary_intent(None) == "general_mentorship"
    assert classify_primary_intent("") == "general_mentorship"


def test_extract_prompt_context_truncates_long_text():
    long_text = "a" * 500
    result = extract_prompt_context(long_text, max_len=240)
    assert result is not None
    assert len(result) == 240
    assert result.endswith("…")


def test_extract_prompt_context_returns_none_for_none():
    assert extract_prompt_context(None) is None


def test_audit_fields_for_dialogue_uses_first_user_turn():
    dialogue = Dialogue(
        dialogue_id="conv-1",
        system_prompt="You are Chioma.",
        persona_id="chioma",
        turns=[
            Turn(speaker=Speaker.user, text="How do I save for my business?"),
            Turn(speaker=Speaker.mentor, text="Start with a fixed weekly amount."),
        ],
    )
    intent, context = audit_fields_for_dialogue(dialogue)
    assert intent == "savings"
    assert context == "How do I save for my business?"


# ── Baseline computation ─────────────────────────────────────────────────────

def test_compute_persona_baseline_none_when_no_history():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    result = compute_persona_baseline(db, "chioma", exclude_job_run_id="run-x", window=10)
    db.close()
    assert result is None


def test_compute_persona_baseline_averages_prior_runs_only():
    engine = make_engine()
    Session = sessionmaker(bind=engine)

    add_run(Session, persona_id="chioma", aggregate=0.8)
    add_run(Session, persona_id="chioma", aggregate=0.6)
    current_run_id = add_run(Session, persona_id="chioma", aggregate=0.1)

    db = Session()
    baseline = compute_persona_baseline(db, "chioma", exclude_job_run_id=current_run_id, window=10)
    db.close()

    assert baseline == 0.7  # mean of 0.8 and 0.6 — current run excluded


def test_compute_persona_baseline_respects_window():
    engine = make_engine()
    Session = sessionmaker(bind=engine)

    now = datetime.now(UTC)
    for i, score in enumerate([1.0, 1.0, 0.0]):
        add_run(
            Session,
            persona_id="chioma",
            aggregate=score,
            scored_at=now - timedelta(days=10 - i),
        )
    current_run_id = add_run(Session, persona_id="chioma", aggregate=0.5, scored_at=now)

    db = Session()
    baseline = compute_persona_baseline(db, "chioma", exclude_job_run_id=current_run_id, window=1)
    db.close()

    assert baseline == 0.0  # only the single most recent prior run (window=1)


def test_recent_prior_run_ids_stmt_compiles_postgres_safe():
    """Regression guard for a Postgres-only failure the SQLite suite can't reach.

    The baseline query must not be ``SELECT DISTINCT`` ordered by a non-selected
    column: Postgres raises ``InvalidColumnReference`` ("ORDER BY expressions must
    appear in select list"), while SQLite runs it fine — so every test here would
    stay green while production (Postgres) fails, exactly as it did before this
    guard. Compile the real statement builder against the Postgres dialect and
    assert the safe GROUP BY shape, so a revert to the DISTINCT form fails in CI.
    """
    from sqlalchemy.dialects import postgresql

    from app.drift import _recent_prior_run_ids_stmt

    sql = str(
        _recent_prior_run_ids_stmt("chioma", "current-run", window=10).compile(
            dialect=postgresql.dialect()
        )
    ).upper()
    assert "DISTINCT" not in sql
    assert "GROUP BY" in sql
    assert "ORDER BY" in sql


def test_delta_pct_none_without_baseline():
    assert delta_pct(None, 0.5) is None


def test_delta_pct_positive_when_current_below_baseline():
    assert delta_pct(1.0, 0.8) == 20.0


# ── Drift alerting ────────────────────────────────────────────────────────────

def test_evaluate_drift_and_alert_fires_when_threshold_crossed():
    engine = make_engine()
    Session = sessionmaker(bind=engine)

    add_run(Session, persona_id="chioma", aggregate=0.9)
    current_run_id = add_run(Session, persona_id="chioma", aggregate=0.5)  # ~44% below baseline

    db = Session()
    alerts = evaluate_drift_and_alert(db, current_run_id, threshold_pct=15.0)
    assert len(alerts) == 1
    assert alerts[0].persona_id == "chioma"
    assert alerts[0].delta_pct > 15.0
    db.close()


def test_evaluate_drift_and_alert_silent_under_threshold():
    engine = make_engine()
    Session = sessionmaker(bind=engine)

    add_run(Session, persona_id="chioma", aggregate=0.80)
    current_run_id = add_run(Session, persona_id="chioma", aggregate=0.78)  # ~2.5% below

    db = Session()
    alerts = evaluate_drift_and_alert(db, current_run_id, threshold_pct=15.0)
    db.close()

    assert alerts == []


def test_evaluate_drift_and_alert_skips_persona_with_no_baseline():
    engine = make_engine()
    Session = sessionmaker(bind=engine)

    current_run_id = add_run(Session, persona_id="kwame", aggregate=0.1)  # first-ever run

    db = Session()
    alerts = evaluate_drift_and_alert(db, current_run_id, threshold_pct=15.0)
    db.close()

    assert alerts == []


# ── Full job wiring ───────────────────────────────────────────────────────────

def make_dialogue(dialogue_id: str, user_text: str, persona_id: str = "chioma") -> Dialogue:
    return Dialogue(
        dialogue_id=dialogue_id,
        system_prompt="You are Chioma, an AI business and wealth mentor.",
        persona_id=persona_id,
        turns=[
            Turn(speaker=Speaker.user, text=user_text),
            Turn(speaker=Speaker.mentor, text="Separate business and personal money first."),
        ],
    )


def test_consistency_job_populates_audit_fields_and_delta_from_seeded_baseline():
    """Full job wiring, real scorer (no mocked score_dialogue — matches the
    convention in test_consistency_metrics.py). Verifies primary_intent and
    prompt_context are populated from the first user turn, and that
    consistency_delta_pct matches app.drift.delta_pct applied to the seeded
    baseline and whatever aggregate the real LexicalScorer produced — robust to
    the scorer's exact output rather than asserting a hardcoded score."""
    from app.consistency_job import run_consistency_job
    from app.drift import delta_pct as expected_delta_pct

    engine = make_engine()
    Session = sessionmaker(bind=engine)

    # Seed a baseline run for chioma so the new session has something to compare against.
    add_run(Session, persona_id="chioma", aggregate=0.9)

    dialogues = [make_dialogue("conv-new", "How do I start saving for my shop?")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session):
        summary = run_consistency_job(sample_size=1)

    assert summary["status"] == "completed"

    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-new").first()
    assert run.primary_intent == "savings"
    assert run.prompt_context == "How do I start saving for my shop?"
    assert run.consistency_delta_pct == expected_delta_pct(0.9, run.aggregate)

    fired = "chioma" in summary["drift_alerts"]
    alert = db.query(DriftAlert).filter_by(persona_id="chioma").first()
    assert fired == (alert is not None)
    if alert is not None:
        assert alert.status == "open"
        assert abs(alert.delta_pct) >= 15.0
    db.close()


# ── API endpoints ─────────────────────────────────────────────────────────────

def _client_with_db(engine) -> TestClient:
    import app.main as main

    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    return TestClient(main.app)


def test_audit_sessions_endpoint_requires_admin_role():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/audit-sessions")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_audit_sessions_endpoint_returns_rows():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id="run-1",
        conversation_id="conv-abc",
        persona_id="chioma",
        prompt_to_line=0.5,
        line_to_line=0.5,
        qa_consistency=0.5,
        aggregate=0.5,
        turn_count=4,
        warnings_json="[]",
        primary_intent="savings",
        prompt_context="How do I save?",
        consistency_delta_pct=12.5,
        scored_at=datetime.now(UTC),
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/audit-sessions", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sessions"]) == 1
    row = body["sessions"][0]
    assert row["session_id"] == "conv-abc"
    assert row["primary_intent"] == "savings"
    assert row["prompt_context"] == "How do I save?"
    assert row["consistency_delta_pct"] == 12.5


def test_drift_alerts_endpoint_and_acknowledge_flow():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    alert = DriftAlert(
        id=str(uuid.uuid4()),
        job_run_id="run-1",
        persona_id="chioma",
        baseline_aggregate=0.9,
        current_aggregate=0.5,
        delta_pct=44.4,
        message="Consistency deviated 44.4%",
        status="open",
        created_at=datetime.now(UTC),
    )
    db.add(alert)
    db.commit()
    alert_id = alert.id
    db.close()

    client = _client_with_db(engine)
    try:
        list_resp = client.get("/api/v1/research/drift-alerts", headers=ADMIN_HEADERS)
        assert list_resp.status_code == 200
        assert list_resp.json()["alerts"][0]["status"] == "open"

        ack_resp = client.post(
            f"/api/v1/research/drift-alerts/{alert_id}/acknowledge", headers=ADMIN_HEADERS
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "acknowledged"

        list_resp_2 = client.get(
            "/api/v1/research/drift-alerts?status=acknowledged", headers=ADMIN_HEADERS
        )
        assert len(list_resp_2.json()["alerts"]) == 1
    finally:
        client.app.dependency_overrides.clear()


def test_acknowledge_unknown_alert_returns_404():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/drift-alerts/does-not-exist/acknowledge", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404
