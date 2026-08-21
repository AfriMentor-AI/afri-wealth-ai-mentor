"""C3.2 — Behavioral consistency metrics tests."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.metrics.schemas import Dialogue, Speaker, Turn
from app.models.consistency_run import ConsistencyRun
from app.session_sampler import sample_completed_sessions

SYSTEM_PROMPT = (
    "You are Chioma, an AI business and wealth mentor. Give concrete, actionable "
    "guidance grounded in African market realities. Practise empathetic tough love."
)

ADMIN_HEADERS = {"X-User-Roles": "admin"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_in_memory_engine():
    # StaticPool keeps a single shared connection so the in-memory DB survives
    # across threads — TestClient runs sync endpoints in a worker thread.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def make_dialogue(n_turns: int = 4, dialogue_id: str = "test-conv-001") -> Dialogue:
    turns = []
    for i in range(n_turns):
        speaker = Speaker.user if i % 2 == 0 else Speaker.mentor
        text = (
            "How do I start saving money in Nigeria?" if speaker == Speaker.user
            else "Start by separating business and personal money. Dangote always reinvested first."
        )
        turns.append(Turn(speaker=speaker, text=text))
    return Dialogue(
        dialogue_id=dialogue_id,
        system_prompt=SYSTEM_PROMPT,
        persona_id="chioma",
        turns=turns,
    )


def make_mock_db(fetchall_batches: list[list]) -> MagicMock:
    """A mock SQLAlchemy session whose successive execute().fetchall() calls
    return each batch in order (first the conversation rows, then the message
    rows for each conversation)."""
    db = MagicMock()
    db.execute.return_value.fetchall.side_effect = fetchall_batches
    return db


# ── Model ───────────────────────────────────────────────────────────────────

def test_consistency_run_model_fields():
    run = ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id=str(uuid.uuid4()),
        conversation_id="conv-001",
        persona_id="chioma",
        prompt_to_line=0.75,
        line_to_line=0.80,
        qa_consistency=0.70,
        aggregate=0.75,
        turn_count=4,
        warnings_json="[]",
        scored_at=datetime.now(timezone.utc),
    )
    assert run.prompt_to_line == 0.75
    assert run.aggregate == 0.75
    assert run.turn_count == 4


# ── Session sampler ───────────────────────────────────────────────────────────

def test_session_sampler_returns_empty_on_no_db():
    """When the chat DB is unavailable, the sampler returns [] without crashing."""
    with patch("app.session_sampler._get_chat_engine", side_effect=Exception("refused")):
        result = sample_completed_sessions(limit=5)
    assert result == []


def test_session_sampler_builds_valid_dialogues():
    """Rows become Dialogues carrying the system-prompt anchor and persona_id."""
    conv_rows = [("conv-001", "chioma"), ("conv-002", None)]
    msgs_1 = [
        ("user", "How do I save money?", 0),
        ("assistant", "Separate business and personal money first.", 1),
    ]
    msgs_2 = [
        ("user", "Where do I begin?", 0),
        ("assistant", "Begin with a written budget and a fixed savings rate.", 1),
    ]
    mock_db = make_mock_db([conv_rows, msgs_1, msgs_2])

    with patch("app.session_sampler._get_chat_engine", return_value=MagicMock()), \
         patch("app.session_sampler.sessionmaker", return_value=lambda: mock_db), \
         patch("app.session_sampler.fetch_system_prompt", return_value=(SYSTEM_PROMPT, "test")):
        dialogues = sample_completed_sessions(limit=5)

    assert len(dialogues) == 2
    assert all(d.system_prompt == SYSTEM_PROMPT for d in dialogues)
    assert dialogues[0].persona_id == "chioma"
    assert dialogues[1].persona_id is None  # unbound session keeps a null persona
    assert dialogues[0].turns[0].speaker is Speaker.user
    assert dialogues[0].turns[1].speaker is Speaker.mentor


def test_session_sampler_filters_short_and_blank_conversations():
    """Conversations with <2 usable turns (too short, or all blank) are dropped."""
    conv_rows = [("conv-short", "chioma"), ("conv-blank", "chioma"), ("conv-ok", "chioma")]
    msgs_short = [("user", "just one turn", 0)]
    msgs_blank = [("user", "   ", 0), ("assistant", "", 1)]
    msgs_ok = [
        ("user", "How to budget?", 0),
        ("assistant", "Make a written plan with deadlines.", 1),
    ]
    mock_db = make_mock_db([conv_rows, msgs_short, msgs_blank, msgs_ok])

    with patch("app.session_sampler._get_chat_engine", return_value=MagicMock()), \
         patch("app.session_sampler.sessionmaker", return_value=lambda: mock_db), \
         patch("app.session_sampler.fetch_system_prompt", return_value=(SYSTEM_PROMPT, "test")):
        dialogues = sample_completed_sessions(limit=5)

    assert len(dialogues) == 1
    assert dialogues[0].dialogue_id == "conv-ok"


def test_session_sampler_empty_when_no_completed_conversations():
    """No completed conversations → [] and no system-prompt fetch attempted."""
    mock_db = make_mock_db([[]])
    with patch("app.session_sampler._get_chat_engine", return_value=MagicMock()), \
         patch("app.session_sampler.sessionmaker", return_value=lambda: mock_db), \
         patch("app.session_sampler.fetch_system_prompt") as fetch:
        result = sample_completed_sessions(limit=5)
    assert result == []
    fetch.assert_not_called()


# ── Job (SQLite in-memory) ────────────────────────────────────────────────────

def test_consistency_job_stores_results():
    """A full run stores one ConsistencyRun per scored dialogue."""
    from app.consistency_job import run_consistency_job

    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    mock_dialogues = [make_dialogue(4, f"conv-{i:03d}") for i in range(3)]

    with patch("app.consistency_job.sample_completed_sessions", return_value=mock_dialogues), \
         patch("app.consistency_job.SessionLocal", Session):
        summary = run_consistency_job(sample_size=3)

    assert summary["status"] == "completed"
    assert summary["session_count"] == 3
    assert 0.0 <= summary["mean_aggregate"] <= 1.0

    db = Session()
    runs = db.query(ConsistencyRun).filter_by(job_run_id=summary["run_id"]).all()
    assert len(runs) == 3
    for run in runs:
        assert 0.0 <= run.prompt_to_line <= 1.0
        assert 0.0 <= run.line_to_line <= 1.0
        assert 0.0 <= run.qa_consistency <= 1.0
        assert 0.0 <= run.aggregate <= 1.0
        assert run.turn_count == 4
        assert run.persona_id == "chioma"
        assert isinstance(json.loads(run.warnings_json), list)
    db.close()


def test_consistency_job_no_data_returns_no_data_status():
    """The job returns a no_data status when the sampler yields nothing."""
    from app.consistency_job import run_consistency_job

    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)

    with patch("app.consistency_job.sample_completed_sessions", return_value=[]), \
         patch("app.consistency_job.SessionLocal", Session):
        summary = run_consistency_job(sample_size=20)

    assert summary["status"] == "no_data"
    assert summary["session_count"] == 0


def test_consistency_run_queryable_by_conversation():
    """Stored runs are queryable by conversation_id — the acceptance criterion."""
    from app.consistency_job import run_consistency_job

    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    dialogues = [make_dialogue(4, "conv-queryable-001")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session):
        run_consistency_job(sample_size=1)

    db = Session()
    result = db.query(ConsistencyRun).filter_by(conversation_id="conv-queryable-001").first()
    assert result is not None
    assert result.aggregate >= 0.0
    db.close()


# ── Read endpoint ─────────────────────────────────────────────────────────────

def _client_with_db(engine) -> TestClient:
    """A TestClient whose get_db is overridden to the given engine. Constructed
    without a context manager so startup events (the scheduler) do not fire."""
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


def test_consistency_endpoint_reports_latest_run():
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)

    job_id = str(uuid.uuid4())
    db = Session()
    for i in range(3):
        db.add(ConsistencyRun(
            id=str(uuid.uuid4()),
            job_run_id=job_id,
            conversation_id=f"conv-{i}",
            persona_id="chioma",
            prompt_to_line=0.5,
            line_to_line=0.6,
            qa_consistency=0.4,
            aggregate=0.5,
            turn_count=4,
            warnings_json="[]",
            scored_at=datetime.now(timezone.utc),
        ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/metrics/consistency")
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_run_id"] == job_id
    assert body["session_count"] == 3
    assert body["aggregates"]["mean_aggregate"] == 0.5
    assert body["aggregates"]["mean_line_to_line"] == 0.6
    assert len(body["sessions"]) == 3
    assert body["sessions"][0]["persona_id"] == "chioma"


def test_consistency_endpoint_empty_when_no_runs():
    engine = make_in_memory_engine()
    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/metrics/consistency")
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_run_id"] is None
    assert body["session_count"] == 0
    assert body["sessions"] == []


# ── C4.1 — live pipeline: active-session sampling, alignment score, trigger ────

def test_session_sampler_includes_active_idle_when_requested():
    """With include_active_after_minutes set, the query also samples idle-but-
    active conversations (card C4.1) — nothing in the pilot marks sessions
    'completed', so this is what feeds the live dashboard."""
    conv_rows = [("conv-active", "chioma")]
    msgs = [
        ("user", "How do I price my product?", 0),
        ("assistant", "Anchor to value, not cost. Test a premium tier.", 1),
    ]
    mock_db = make_mock_db([conv_rows, msgs])

    with patch("app.session_sampler._get_chat_engine", return_value=MagicMock()), \
         patch("app.session_sampler.sessionmaker", return_value=lambda: mock_db), \
         patch("app.session_sampler.fetch_system_prompt", return_value=(SYSTEM_PROMPT, "test")):
        dialogues = sample_completed_sessions(limit=5, include_active_after_minutes=10)

    assert len(dialogues) == 1
    conv_query = mock_db.execute.call_args_list[0]
    sql = str(conv_query.args[0])
    assert "status = 'active'" in sql
    assert "make_interval" in sql
    assert conv_query.args[1]["idle_min"] == 10


def test_session_sampler_completed_only_by_default():
    """Default (include_active_after_minutes=None) keeps the completed-only query
    and passes no idle window — backward-compatible with C3.2."""
    conv_rows = [("conv-done", "chioma")]
    msgs = [
        ("user", "How do I save?", 0),
        ("assistant", "Automate a fixed transfer on payday.", 1),
    ]
    mock_db = make_mock_db([conv_rows, msgs])

    with patch("app.session_sampler._get_chat_engine", return_value=MagicMock()), \
         patch("app.session_sampler.sessionmaker", return_value=lambda: mock_db), \
         patch("app.session_sampler.fetch_system_prompt", return_value=(SYSTEM_PROMPT, "test")):
        sample_completed_sessions(limit=5)

    conv_query = mock_db.execute.call_args_list[0]
    sql = str(conv_query.args[0])
    assert "status = 'active'" not in sql
    assert "make_interval" not in sql
    assert "idle_min" not in conv_query.args[1]


def test_consistency_job_persists_trait_fit_and_composite():
    """Card C4.1 — the job persists the CHIOMA alignment numbers score_dialogue()
    produces (trait-fit cosine + composite), instead of discarding them."""
    from app.consistency_job import run_consistency_job

    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    dialogues = [make_dialogue(4, "conv-align-001")]

    with patch("app.consistency_job.sample_completed_sessions", return_value=dialogues), \
         patch("app.consistency_job.SessionLocal", Session):
        run_consistency_job(sample_size=1)

    db = Session()
    run = db.query(ConsistencyRun).filter_by(conversation_id="conv-align-001").first()
    assert run is not None
    assert run.trait_fit_cosine is not None
    assert -1.0 <= run.trait_fit_cosine <= 1.0
    assert run.composite_score is not None
    assert 0.0 <= run.composite_score <= 1.0
    db.close()


def test_consistency_endpoint_exposes_trait_fit_and_composite():
    """The metrics endpoint surfaces the new alignment aggregates and per-session
    fields (card C4.1) — the numbers the dashboard's CHIOMA alignment tile reads."""
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)

    job_id = str(uuid.uuid4())
    db = Session()
    for i in range(2):
        db.add(ConsistencyRun(
            id=str(uuid.uuid4()),
            job_run_id=job_id,
            conversation_id=f"conv-{i}",
            persona_id="chioma",
            prompt_to_line=0.5,
            line_to_line=0.6,
            qa_consistency=0.4,
            aggregate=0.5,
            turn_count=4,
            warnings_json="[]",
            trait_fit_cosine=0.8,
            composite_score=0.65,
            scored_at=datetime.now(timezone.utc),
        ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/metrics/consistency")
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["aggregates"]["mean_trait_fit_cosine"] == 0.8
    assert body["aggregates"]["mean_composite"] == 0.65
    assert body["sessions"][0]["trait_fit_cosine"] == 0.8
    assert body["sessions"][0]["composite_score"] == 0.65


def test_consistency_endpoint_alignment_mean_ignores_null_rows():
    """Legacy rows (null trait_fit/composite) don't crash the mean and are excluded
    from it — the mean is taken over rows that actually carry the C4.1 columns."""
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    job_id = str(uuid.uuid4())
    db = Session()
    db.add(ConsistencyRun(
        id=str(uuid.uuid4()), job_run_id=job_id, conversation_id="conv-new",
        persona_id="chioma", prompt_to_line=0.5, line_to_line=0.5,
        qa_consistency=0.5, aggregate=0.5, turn_count=4, warnings_json="[]",
        trait_fit_cosine=0.9, composite_score=0.7,
        scored_at=datetime.now(timezone.utc),
    ))
    db.add(ConsistencyRun(
        id=str(uuid.uuid4()), job_run_id=job_id, conversation_id="conv-legacy",
        persona_id="chioma", prompt_to_line=0.5, line_to_line=0.5,
        qa_consistency=0.5, aggregate=0.5, turn_count=4, warnings_json="[]",
        scored_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/metrics/consistency")
    finally:
        client.app.dependency_overrides.clear()

    body = resp.json()
    # mean over the single non-null row, not divided by the full row count
    assert body["aggregates"]["mean_trait_fit_cosine"] == 0.9
    assert body["aggregates"]["mean_composite"] == 0.7
    legacy = next(s for s in body["sessions"] if s["conversation_id"] == "conv-legacy")
    assert legacy["trait_fit_cosine"] is None
    assert legacy["composite_score"] is None


def test_consistency_endpoint_empty_state_includes_alignment_keys():
    """The empty-state aggregates still carry the new keys, so the frontend can
    read them unconditionally even before any run exists."""
    engine = make_in_memory_engine()
    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/metrics/consistency")
    finally:
        client.app.dependency_overrides.clear()

    body = resp.json()
    assert body["aggregates"]["mean_trait_fit_cosine"] == 0.0
    assert body["aggregates"]["mean_composite"] == 0.0


def test_trigger_consistency_run_requires_console_role():
    """The on-demand "Refresh now" trigger is admin-gated (card C4.1)."""
    engine = make_in_memory_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post("/api/v1/research/consistency/run")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_trigger_consistency_run_invokes_job_and_returns_summary():
    """With a console role, the trigger runs the job inline and returns its
    summary dict — patched here so the test never touches the real chat DB."""
    engine = make_in_memory_engine()
    client = _client_with_db(engine)
    summary = {"run_id": "abc", "session_count": 3, "status": "completed"}
    try:
        with patch("app.main.run_consistency_job", return_value=summary) as job:
            resp = client.post("/api/v1/research/consistency/run", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == summary
    job.assert_called_once()
