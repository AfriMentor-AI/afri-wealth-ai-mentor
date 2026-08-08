"""Milestone tests (card O2.3 — extends the D2.3 goals-milestones-service)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(fresh_db):
    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def goal_id(client):
    r = client.post(
        "/api/v1/goals", json={"title": "Start a Poultry Business"}, headers=USER_HEADERS
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_new_goal_has_zero_progress(client, goal_id):
    r = client.get(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS)
    assert r.json()["progress_pct"] == 0


def test_add_milestone_defaults(client, goal_id):
    r = client.post(
        f"/api/v1/goals/{goal_id}/milestones",
        json={"title": "Vision Foundation"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "upcoming"
    assert body["order"] == 0


def test_add_milestone_requires_goal_ownership(client, goal_id):
    r = client.post(
        f"/api/v1/goals/{goal_id}/milestones",
        json={"title": "Sneaky"},
        headers=OTHER_HEADERS,
    )
    assert r.status_code == 404


def test_add_milestone_unknown_goal(client):
    r = client.post(
        "/api/v1/goals/does-not-exist/milestones", json={"title": "X"}, headers=USER_HEADERS
    )
    assert r.status_code == 404


def test_list_milestones_ordered(client, goal_id):
    for title in ["Vision Foundation", "Legal Readiness", "Operations", "Launch"]:
        client.post(
            f"/api/v1/goals/{goal_id}/milestones", json={"title": title}, headers=USER_HEADERS
        )
    r = client.get(f"/api/v1/goals/{goal_id}/milestones", headers=USER_HEADERS)
    assert [m["title"] for m in r.json()] == [
        "Vision Foundation", "Legal Readiness", "Operations", "Launch",
    ]


def test_complete_milestone_updates_progress(client, goal_id):
    m1 = client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Vision Foundation"},
        headers=USER_HEADERS,
    ).json()
    client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Legal Readiness"},
        headers=USER_HEADERS,
    )

    r = client.post(f"/api/v1/milestones/{m1['id']}/complete", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    goal = client.get(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS).json()
    assert goal["progress_pct"] == 50


def test_update_milestone_status(client, goal_id):
    m = client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Legal Readiness"},
        headers=USER_HEADERS,
    ).json()
    r = client.patch(
        f"/api/v1/milestones/{m['id']}", json={"status": "blocked"}, headers=USER_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"


def test_update_milestone_ignores_explicit_null_status(client, goal_id):
    m = client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Legal Readiness"},
        headers=USER_HEADERS,
    ).json()
    r = client.patch(
        f"/api/v1/milestones/{m['id']}",
        json={"title": "Renamed", "status": None},
        headers=USER_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Renamed"
    assert body["status"] == "upcoming"  # unchanged, not nulled


def test_milestone_route_requires_ownership(client, goal_id):
    m = client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Legal Readiness"},
        headers=USER_HEADERS,
    ).json()
    r = client.post(f"/api/v1/milestones/{m['id']}/complete", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_delete_milestone(client, goal_id):
    m = client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Legal Readiness"},
        headers=USER_HEADERS,
    ).json()
    r = client.delete(f"/api/v1/milestones/{m['id']}", headers=USER_HEADERS)
    assert r.status_code == 204
    listing = client.get(f"/api/v1/goals/{goal_id}/milestones", headers=USER_HEADERS)
    assert listing.json() == []


def test_unknown_milestone_404(client):
    r = client.patch(
        "/api/v1/milestones/does-not-exist", json={"status": "done"}, headers=USER_HEADERS
    )
    assert r.status_code == 404
