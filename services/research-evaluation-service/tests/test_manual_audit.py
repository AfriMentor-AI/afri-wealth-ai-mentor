"""Card C4.2 — manual audit workflow: flag rule, job wiring, and the
"New Manual Audit" / "Filter by Drift" / "Mark reviewed" endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.drift import evaluate_review_flag
from app.metrics.schemas import Dialogue, Speaker, Turn
from app.models.consistency_run import ConsistencyRun

ADMIN_HEADERS = {"X-User-Roles": "admin"}

# The config defaults the service runs with; the flag-rule unit tests pass these
# explicitly so a change to the defaults can't quietly move the boundaries.
FLOOR = 0.70
THRESH = 15.0


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def add_run(
    Session,
    *,
    aggregate=0.8,
    persona_id="chioma",
    conversation_id=None,
    job_run_id=None,
    consistency_delta_pct=None,
    review_status=None,
    review_reason=None,
    reviewed_at=None,
    scored_at=None,
) -> str:
    """Insert one ConsistencyRun and return its PK id (the key /review uses)."""
    run_id = str(uuid.uuid4())
    db = Session()
    db.add(ConsistencyRun(
        id=run_id,
        job_run_id=job_run_id or str(uuid.uuid4()),
        conversation_id=conversation_id or f"conv-{uuid.uuid4().hex[:8]}",
        persona_id=persona_id,
        prompt_to_line=aggregate,
        line_to_line=aggregate,
        qa_consistency=aggregate,
        aggregate=aggregate,
        turn_count=4,
        warnings_json="[]",
        consistency_delta_pct=consistency_delta_pct,
        review_status=review_status,
        review_reason=review_reason,
        reviewed_at=reviewed_at,
        scored_at=scored_at or datetime.now(UTC),
    ))
    db.commit()
    db.close()
    return run_id


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


def fake_report(aggregate: float):
    """A stand-in for score_dialogue()'s return, carrying just the attributes the
    job reads. Patched into the job-wiring tests so the aggregate lands on a known
    side of the floor — unlike the sibling suites, which assert robustly against
    the real scorer; here the point under test is the flag, not the score."""
    return SimpleNamespace(
        consistency=SimpleNamespace(
            prompt_to_line=aggregate,
            line_to_line=aggregate,
            qa_consistency=aggregate,
            aggregate=aggregate,
        ),
        warnings=[],
        trait_fit=SimpleNamespace(cosine_similarity=0.5),
        composite_score=aggregate,
    )


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


# ── Flag rule (pure function) ─────────────────────────────────────────────────

def test_flag_none_when_healthy():
    assert evaluate_review_flag(0.85, 5.0, floor=FLOOR, drift_threshold_pct=THRESH) is None


def test_flag_below_floor_only():
    assert evaluate_review_flag(0.5, 3.0, floor=FLOOR, drift_threshold_pct=THRESH) == "below_floor"


def test_flag_drift_only():
    assert evaluate_review_flag(0.9, 20.0, floor=FLOOR, drift_threshold_pct=THRESH) == "drift"


def test_flag_both_arms_union():
    assert (
        evaluate_review_flag(0.5, 20.0, floor=FLOOR, drift_threshold_pct=THRESH)
        == "below_floor+drift"
    )


def test_flag_delta_none_uses_floor_arm_only_and_never_raises():
    """F1: a persona's first-ever session has no baseline, so delta is None. The
    floor arm must still apply and the guarded abs() must not raise (an exception
    here would be swallowed by the job loop and silently drop the row)."""
    assert evaluate_review_flag(0.5, None, floor=FLOOR, drift_threshold_pct=THRESH) == "below_floor"
    assert evaluate_review_flag(0.9, None, floor=FLOOR, drift_threshold_pct=THRESH) is None


def test_flag_floor_boundary_not_flagged():
    # aggregate == floor is not *below* the floor.
    assert evaluate_review_flag(0.70, None, floor=FLOOR, drift_threshold_pct=THRESH) is None


def test_flag_drift_boundary_is_flagged():
    # |delta| == threshold trips the drift arm (>=).
    assert evaluate_review_flag(0.9, 15.0, floor=FLOOR, drift_threshold_pct=THRESH) == "drift"


def test_flag_negative_delta_uses_abs():
    # An improvement past the threshold is still drift — the rule is on magnitude.
    assert evaluate_review_flag(0.9, -20.0, floor=FLOOR, drift_threshold_pct=THRESH) == "drift"


# ── Job wiring (SQLite in-memory, aggregate pinned via fake_report) ────────────

def test_job_flags_below_floor_first_run_persona_and_persists():
    """F1 end-to-end: a below-floor session for a persona with NO baseline
    (delta None) must be flagged on the floor arm AND persisted — not dropped."""
    from app.consistency_job import run_consistency_job

    engine = make_engine()
    Session = sessionmaker(bind=engine)
    dialogues = [make_dialogue("conv-low", "How do I save?")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session), \
         patch("app.consistency_job.score_dialogue", return_value=fake_report(0.4)):
        summary = run_consistency_job(sample_size=1)

    assert summary["flagged_count"] == 1
    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-low").first()
    assert run is not None  # would be None if abs(None) had raised and dropped it
    assert run.consistency_delta_pct is None
    assert run.review_status == "pending_review"
    assert run.review_reason == "below_floor"
    db.close()


def test_job_does_not_flag_healthy_session():
    from app.consistency_job import run_consistency_job

    engine = make_engine()
    Session = sessionmaker(bind=engine)
    dialogues = [make_dialogue("conv-ok", "How do I save?")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session), \
         patch("app.consistency_job.score_dialogue", return_value=fake_report(0.9)):
        summary = run_consistency_job(sample_size=1)

    assert summary["flagged_count"] == 0
    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-ok").first()
    assert run.review_status is None
    assert run.review_reason is None
    db.close()


def test_job_flags_both_arms_with_seeded_baseline():
    from app.consistency_job import run_consistency_job

    engine = make_engine()
    Session = sessionmaker(bind=engine)
    add_run(Session, persona_id="chioma", aggregate=0.9)  # prior-run baseline
    dialogues = [make_dialogue("conv-drift", "How do I save?")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session), \
         patch("app.consistency_job.score_dialogue", return_value=fake_report(0.4)):
        summary = run_consistency_job(sample_size=1)

    assert summary["flagged_count"] == 1
    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-drift").first()
    assert run.consistency_delta_pct is not None  # baseline existed → real delta
    assert run.review_status == "pending_review"
    assert run.review_reason == "below_floor+drift"
    db.close()


def test_job_flags_drift_only_when_above_floor():
    """Drift arm fires independent of the floor: healthy raw score, but the
    per-session delta crosses the threshold."""
    from app.consistency_job import run_consistency_job

    engine = make_engine()
    Session = sessionmaker(bind=engine)
    add_run(Session, persona_id="chioma", aggregate=0.9)  # baseline
    dialogues = [make_dialogue("conv-slip", "How do I save?")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session), \
         patch("app.consistency_job.score_dialogue", return_value=fake_report(0.75)):
        summary = run_consistency_job(sample_size=1)

    assert summary["flagged_count"] == 1
    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-slip").first()
    assert run.aggregate >= FLOOR
    assert run.review_status == "pending_review"
    assert run.review_reason == "drift"
    db.close()


# ── POST /audits — "New Manual Audit" ─────────────────────────────────────────

def test_manual_audit_requires_admin():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post("/api/v1/research/audits")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_manual_audit_returns_run_and_only_its_scored_sessions():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    run_id = "known-run-1"
    add_run(Session, job_run_id=run_id, conversation_id="conv-a", aggregate=0.4,
            review_status="pending_review", review_reason="below_floor")
    add_run(Session, job_run_id=run_id, conversation_id="conv-b", aggregate=0.9)
    add_run(Session, job_run_id="other-run", conversation_id="conv-c", aggregate=0.5)

    summary = {
        "run_id": run_id, "session_count": 2, "mean_aggregate": 0.65,
        "flagged_count": 1, "status": "completed", "drift_alerts": [],
    }
    client = _client_with_db(engine)
    try:
        with patch("app.main.run_consistency_job", return_value=summary) as job:
            resp = client.post("/api/v1/research/audits", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    job.assert_called_once()
    body = resp.json()
    assert body["run"]["run_id"] == run_id
    assert body["run"]["flagged_count"] == 1
    # Only this run's rows, never the other run's conv-c.
    assert {s["session_id"] for s in body["sessions"]} == {"conv-a", "conv-b"}
    flagged = next(s for s in body["sessions"] if s["session_id"] == "conv-a")
    assert flagged["review_status"] == "pending_review"
    assert flagged["review_reason"] == "below_floor"
    assert flagged["id"]  # PK present for the /review call


def test_manual_audit_no_data_returns_empty_sessions():
    engine = make_engine()
    client = _client_with_db(engine)
    summary = {"run_id": "r", "session_count": 0, "status": "no_data", "drift_alerts": []}
    try:
        with patch("app.main.run_consistency_job", return_value=summary):
            resp = client.post("/api/v1/research/audits", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["status"] == "no_data"
    assert body["sessions"] == []


# ── GET /audit-sessions?flagged_only — "Filter by Drift" ──────────────────────

def test_flagged_only_returns_pending_and_reviewed_not_healthy():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    add_run(Session, conversation_id="conv-flagged",
            review_status="pending_review", review_reason="below_floor")
    add_run(Session, conversation_id="conv-reviewed",
            review_status="reviewed", review_reason="drift")
    add_run(Session, conversation_id="conv-healthy")  # review_status stays None

    client = _client_with_db(engine)
    try:
        resp = client.get(
            "/api/v1/research/audit-sessions?flagged_only=true", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = {s["session_id"] for s in resp.json()["sessions"]}
    assert ids == {"conv-flagged", "conv-reviewed"}


def test_default_listing_returns_all_including_unflagged():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    add_run(Session, conversation_id="conv-flagged",
            review_status="pending_review", review_reason="below_floor")
    add_run(Session, conversation_id="conv-healthy")

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/audit-sessions", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    ids = {s["session_id"] for s in resp.json()["sessions"]}
    assert ids == {"conv-flagged", "conv-healthy"}


def test_audit_session_rows_carry_review_keys():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    add_run(Session, conversation_id="conv-flagged",
            review_status="pending_review", review_reason="below_floor")

    client = _client_with_db(engine)
    try:
        resp = client.get(
            "/api/v1/research/audit-sessions?flagged_only=true", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()

    row = resp.json()["sessions"][0]
    for key in ("id", "session_id", "review_status", "review_reason", "reviewed_at"):
        assert key in row
    assert row["review_status"] == "pending_review"
    assert row["review_reason"] == "below_floor"


# ── POST /audit-sessions/{id}/review — "Mark reviewed" ────────────────────────

def test_review_requires_admin():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post("/api/v1/research/audit-sessions/whatever/review")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_review_marks_reviewed_and_preserves_reason():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    audit_id = add_run(Session, conversation_id="conv-x",
                       review_status="pending_review", review_reason="below_floor")

    client = _client_with_db(engine)
    try:
        resp = client.post(
            f"/api/v1/research/audit-sessions/{audit_id}/review", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["review_status"] == "reviewed"
    assert body["review_reason"] == "below_floor"  # preserved, not cleared
    assert body["reviewed_at"] is not None

    db = Session()
    run = db.query(ConsistencyRun).filter_by(id=audit_id).first()
    assert run.review_status == "reviewed"
    assert run.reviewed_at is not None
    db.close()


def test_review_unknown_id_returns_404():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/audit-sessions/does-not-exist/review", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_review_keys_by_pk_not_conversation_id():
    """F10: the same conversation is re-scored across runs, so conversation_id is
    not unique. Reviewing one row's PK must not touch the sibling row that shares
    its conversation_id."""
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    id1 = add_run(Session, conversation_id="conv-dup", job_run_id="run-1",
                  review_status="pending_review", review_reason="below_floor")
    id2 = add_run(Session, conversation_id="conv-dup", job_run_id="run-2",
                  review_status="pending_review", review_reason="drift")

    client = _client_with_db(engine)
    try:
        resp = client.post(
            f"/api/v1/research/audit-sessions/{id1}/review", headers=ADMIN_HEADERS
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    db = Session()
    assert db.query(ConsistencyRun).filter_by(id=id1).first().review_status == "reviewed"
    assert db.query(ConsistencyRun).filter_by(id=id2).first().review_status == "pending_review"
    db.close()
