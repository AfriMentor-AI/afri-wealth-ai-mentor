"""Card C4.5 — financial-knowledge/self-efficacy survey score endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.models.session_metric import anonymize_user_id
from app.models.survey_score import SurveyScore

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


def test_record_survey_scores_requires_console_role():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T0",
                "financial_knowledge_score": 2, "self_efficacy_score": 18,
            }]},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_record_survey_scores_hashes_and_never_echoes_raw_id():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-secret-42", "wave": "T0",
                "financial_knowledge_score": 2, "self_efficacy_score": 18,
            }]},
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "participant-secret-42" not in resp.text
    body = resp.json()
    assert len(body["recorded"]) == 1
    assert body["recorded"][0]["wave"] == "T0"
    assert body["recorded"][0]["financial_knowledge_score"] == 2
    assert body["recorded"][0]["self_efficacy_score"] == 18
    assert body["recorded"][0]["user_hash"] == anonymize_user_id("participant-secret-42")


def test_record_survey_scores_rejects_unknown_wave():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T2",
                "financial_knowledge_score": 2, "self_efficacy_score": 18,
            }]},
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_record_survey_scores_rejects_out_of_range_scores():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        resp = client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T0",
                "financial_knowledge_score": 4, "self_efficacy_score": 18,
            }]},
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_record_survey_scores_upserts_same_participant_and_wave():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T0",
                "financial_knowledge_score": 1, "self_efficacy_score": 12,
            }]},
            headers=ADMIN_HEADERS,
        )
        # A corrected tracking-sheet row for the same participant + wave must
        # update, not duplicate or error.
        resp = client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T0",
                "financial_knowledge_score": 3, "self_efficacy_score": 20,
            }]},
            headers=ADMIN_HEADERS,
        )
        listing = client.get("/api/v1/research/survey-scores", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = listing.json()
    assert len(body["scores"]) == 1
    assert body["scores"][0]["financial_knowledge_score"] == 3
    assert body["scores"][0]["self_efficacy_score"] == 20
    assert body["counts"] == {"T0": 1, "T1": 0}


def test_record_survey_scores_keeps_t0_and_t1_as_separate_rows():
    engine = make_engine()
    client = _client_with_db(engine)
    try:
        client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T0",
                "financial_knowledge_score": 1, "self_efficacy_score": 10,
            }]},
            headers=ADMIN_HEADERS,
        )
        client.post(
            "/api/v1/research/survey-scores",
            json={"scores": [{
                "user_id": "participant-1", "wave": "T1",
                "financial_knowledge_score": 3, "self_efficacy_score": 22,
            }]},
            headers=ADMIN_HEADERS,
        )
        listing = client.get("/api/v1/research/survey-scores", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    body = listing.json()
    assert len(body["scores"]) == 2
    assert body["counts"] == {"T0": 1, "T1": 1}
    waves = {s["wave"]: s for s in body["scores"]}
    assert waves["T0"]["financial_knowledge_score"] == 1
    assert waves["T1"]["financial_knowledge_score"] == 3


def test_list_survey_scores_reports_counts_per_wave():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(SurveyScore(
        user_hash="a" * 16, wave="T0", financial_knowledge_score=2, self_efficacy_score=15,
    ))
    db.add(SurveyScore(
        user_hash="b" * 16, wave="T0", financial_knowledge_score=1, self_efficacy_score=12,
    ))
    db.add(SurveyScore(
        user_hash="a" * 16, wave="T1", financial_knowledge_score=3, self_efficacy_score=20,
    ))
    db.commit()
    db.close()

    client = _client_with_db(engine)
    try:
        resp = client.get("/api/v1/research/survey-scores", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"] == {"T0": 2, "T1": 1}
    assert len(body["scores"]) == 3
