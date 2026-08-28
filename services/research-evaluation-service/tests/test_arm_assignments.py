"""Card C4.5 — study-arm assignment endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.arm_assignment import ArmAssignment
from app.models.session_metric import anonymize_user_id

ADMIN_HEADERS = {"X-User-Roles": "admin"}


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


def test_record_arm_assignments_requires_console_role():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/arm-assignments",
            json={"assignments": [{"user_id": "participant-1", "arm": "A"}]},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_record_arm_assignments_hashes_and_never_echoes_raw_id():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/arm-assignments",
            json={"assignments": [{"user_id": "participant-secret-42", "arm": "A"}]},
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "participant-secret-42" not in resp.text
    body = resp.json()
    assert len(body["recorded"]) == 1
    assert body["recorded"][0]["arm"] == "A"
    assert body["recorded"][0]["user_hash"] == anonymize_user_id("participant-secret-42")


def test_record_arm_assignments_rejects_unknown_arm():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/arm-assignments",
            json={"assignments": [{"user_id": "participant-1", "arm": "C"}]},
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_record_arm_assignments_upserts_on_resubmission():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        client.post(
            "/api/v1/research/arm-assignments",
            json={"assignments": [{"user_id": "participant-1", "arm": "A"}]},
            headers=ADMIN_HEADERS,
        )
        # Re-submitting the same participant with a corrected arm must update,
        # not duplicate or error — the enrolment sheet may be re-loaded.
        resp = client.post(
            "/api/v1/research/arm-assignments",
            json={"assignments": [{"user_id": "participant-1", "arm": "B"}]},
            headers=ADMIN_HEADERS,
        )
        listing = client.get("/api/v1/research/arm-assignments", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["assignments"]) == 1
    assert body["assignments"][0]["arm"] == "B"
    assert body["counts"] == {"A": 0, "B": 1}


def test_list_arm_assignments_reports_counts_per_group():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(ArmAssignment(user_hash="a" * 16, arm="A"))
    db.add(ArmAssignment(user_hash="b" * 16, arm="A"))
    db.add(ArmAssignment(user_hash="c" * 16, arm="B"))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/arm-assignments", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"] == {"A": 2, "B": 1}
    assert len(body["assignments"]) == 3
    hashes = {a["user_hash"] for a in body["assignments"]}
    assert hashes == {"a" * 16, "b" * 16, "c" * 16}
