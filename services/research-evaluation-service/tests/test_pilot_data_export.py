"""Card O4.4 — anonymized pilot-data export tests."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.consistency_run import ConsistencyRun
from app.models.session_metric import SessionMetric

ADMIN_HEADERS = {"X-User-Roles": "admin"}
RESEARCHER_HEADERS = {"X-User-Roles": "researcher"}


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


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


def test_pilot_export_requires_console_role():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/export/pilot-data.csv")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_pilot_export_joins_session_metrics_with_consistency_scores():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    # A scored session — has both a SessionMetric and a matching ConsistencyRun.
    db.add(SessionMetric(
        user_hash="a" * 16,
        session_date=date(2026, 8, 1),
        session_duration_seconds=300,
        message_count=12,
        conversation_id="conv-scored",
        recorded_at=datetime.now(UTC),
    ))
    db.add(ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id="run-1",
        conversation_id="conv-scored",
        persona_id="chioma-base",
        prompt_to_line=0.9,
        line_to_line=0.85,
        qa_consistency=0.8,
        aggregate=0.85,
        turn_count=6,
        warnings_json="[]",
        consistency_delta_pct=-2.1,
        scored_at=datetime.now(UTC),
    ))
    # An unscored session — SessionMetric only, no nightly job has covered it yet.
    db.add(SessionMetric(
        user_hash="b" * 16,
        session_date=date(2026, 8, 2),
        session_duration_seconds=120,
        message_count=4,
        conversation_id="conv-unscored",
        recorded_at=datetime.now(UTC),
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/export/pilot-data.csv", headers=RESEARCHER_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2

    scored = next(r for r in rows if r["user_hash"] == "a" * 16)
    assert scored["session_date"] == "2026-08-01"
    assert scored["session_duration_seconds"] == "300"
    assert scored["message_count"] == "12"
    assert scored["persona_id"] == "chioma-base"
    assert scored["aggregate"] == "0.85"
    assert scored["consistency_delta_pct"] == "-2.1"

    unscored = next(r for r in rows if r["user_hash"] == "b" * 16)
    assert unscored["persona_id"] == ""
    assert unscored["aggregate"] == ""


def test_pilot_export_never_leaks_raw_conversation_id_or_user_id():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(SessionMetric(
        user_hash="c" * 16,
        session_date=date(2026, 8, 3),
        session_duration_seconds=60,
        message_count=2,
        conversation_id="super-secret-conversation-id",
        recorded_at=datetime.now(UTC),
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/export/pilot-data.csv", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert "super-secret-conversation-id" not in resp.text
    header_row = resp.text.splitlines()[0]
    assert "conversation_id" not in header_row
    assert "user_id" not in header_row


def test_pilot_export_respects_date_filters():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(SessionMetric(
        user_hash="d" * 16, session_date=date(2026, 1, 1),
        session_duration_seconds=60, message_count=1,
        conversation_id="conv-jan", recorded_at=datetime.now(UTC),
    ))
    db.add(SessionMetric(
        user_hash="e" * 16, session_date=date(2026, 8, 1),
        session_duration_seconds=60, message_count=1,
        conversation_id="conv-aug", recorded_at=datetime.now(UTC),
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get(
            "/api/v1/research/export/pilot-data.csv?start_date=2026-07-01",
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["user_hash"] == "e" * 16
