"""Intake session flow tests (card O2.2 acceptance)."""

USER = "user-kofi"


def _headers(user_id=USER):
    return {"X-User-Id": user_id}


def test_start_session_requires_user_id(client):
    r = client.post("/api/v1/intake/sessions")
    assert r.status_code == 401


def test_start_session_creates_in_progress_session(client):
    r = client.post("/api/v1/intake/sessions", headers=_headers())
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == USER
    assert body["status"] == "in_progress"
    assert body["answers"] == []


def test_start_session_resumes_existing_in_progress_session(client):
    first = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    r = client.post("/api/v1/intake/sessions", headers=_headers())
    assert r.status_code == 200  # resumed, not created
    assert r.json()["id"] == first["id"]


def test_get_session_not_found_for_other_user(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    r = client.get(f"/api/v1/intake/sessions/{session['id']}", headers=_headers("someone-else"))
    assert r.status_code == 404


def test_get_session_unknown_id(client):
    r = client.get("/api/v1/intake/sessions/does-not-exist", headers=_headers())
    assert r.status_code == 404


def test_get_session_returns_owned_session(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    r = client.get(f"/api/v1/intake/sessions/{session['id']}", headers=_headers())
    assert r.status_code == 200
    assert r.json()["id"] == session["id"]


def test_submit_answer_stores_and_upserts(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    sid = session["id"]

    r = client.post(
        f"/api/v1/intake/sessions/{sid}/answers",
        json={"step": "sector", "payload": {"sector": "Trader"}},
        headers=_headers(),
    )
    assert r.status_code == 200
    answers = r.json()["answers"]
    assert len(answers) == 1
    assert answers[0]["step"] == "sector"
    assert answers[0]["payload"]["sector"] == "Trader"

    # Re-submitting the same step upserts rather than duplicating.
    r2 = client.post(
        f"/api/v1/intake/sessions/{sid}/answers",
        json={"step": "sector", "payload": {"sector": "Tech"}},
        headers=_headers(),
    )
    answers2 = r2.json()["answers"]
    assert len(answers2) == 1
    assert answers2[0]["payload"]["sector"] == "Tech"


def test_submit_answer_validates_payload_shape(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    r = client.post(
        f"/api/v1/intake/sessions/{session['id']}/answers",
        json={"step": "sector", "payload": {}},  # missing required `sector` key
        headers=_headers(),
    )
    assert r.status_code == 422


def test_submit_answer_requires_ownership(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    r = client.post(
        f"/api/v1/intake/sessions/{session['id']}/answers",
        json={"step": "sector", "payload": {"sector": "Trader"}},
        headers=_headers("someone-else"),
    )
    assert r.status_code == 404


def _answer_all_steps(client, session_id, user=USER):
    steps = [
        ("sector", {"sector": "Trader"}),
        (
            "education_time",
            {"education_level": "Secondary school", "time_available_per_week": "6-10 hours"},
        ),
        ("constraints", {"constraints": ["Limited startup capital"]}),
        (
            "confirm",
            {
                "name": "Kofi Mensah",
                "business_name": "Poultry Business - Kumasi",
                "location": "Kumasi, Ghana",
            },
        ),
    ]
    for step, payload in steps:
        r = client.post(
            f"/api/v1/intake/sessions/{session_id}/answers",
            json={"step": step, "payload": payload},
            headers=_headers(user),
        )
        assert r.status_code == 200
    return steps


def test_complete_session_requires_all_steps(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    client.post(
        f"/api/v1/intake/sessions/{session['id']}/answers",
        json={"step": "sector", "payload": {"sector": "Trader"}},
        headers=_headers(),
    )
    r = client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers=_headers())
    assert r.status_code == 400
    assert "education_time" in r.json()["detail"]


def test_complete_session_builds_diagnostic_profile(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    _answer_all_steps(client, session["id"])

    r = client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    profile = client.get(f"/api/v1/profiles/{USER}/diagnostic", headers=_headers()).json()
    assert profile["name"] == "Kofi Mensah"
    assert profile["business_name"] == "Poultry Business - Kumasi"
    assert profile["sector"] == "Trader"
    assert profile["education_level"] == "Secondary school"
    assert profile["time_available_per_week"] == "6-10 hours"
    assert profile["constraints"] == ["Limited startup capital"]
    assert profile["persona_id"] is None


def test_answers_rejected_once_session_completed(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    _answer_all_steps(client, session["id"])
    client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers=_headers())

    r = client.post(
        f"/api/v1/intake/sessions/{session['id']}/answers",
        json={"step": "sector", "payload": {"sector": "Tech"}},
        headers=_headers(),
    )
    assert r.status_code == 409

    r2 = client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers=_headers())
    assert r2.status_code == 409


def test_retaking_intake_updates_existing_diagnostic_profile(client):
    first_session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    _answer_all_steps(client, first_session["id"])
    client.post(f"/api/v1/intake/sessions/{first_session['id']}/complete", headers=_headers())

    second_session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    for step, payload in [
        ("sector", {"sector": "Tech"}),
        (
            "education_time",
            {"education_level": "University", "time_available_per_week": "20+ hours"},
        ),
        ("constraints", {"constraints": []}),
        (
            "confirm",
            {"name": "Kofi Mensah", "business_name": "Kofi Tech Repairs", "location": "Kumasi"},
        ),
    ]:
        client.post(
            f"/api/v1/intake/sessions/{second_session['id']}/answers",
            json={"step": step, "payload": payload},
            headers=_headers(),
        )
    client.post(f"/api/v1/intake/sessions/{second_session['id']}/complete", headers=_headers())

    profile = client.get(f"/api/v1/profiles/{USER}/diagnostic", headers=_headers()).json()
    assert profile["sector"] == "Tech"
    assert profile["business_name"] == "Kofi Tech Repairs"


def test_completing_intake_again_starts_a_fresh_session(client):
    session = client.post("/api/v1/intake/sessions", headers=_headers()).json()
    _answer_all_steps(client, session["id"])
    client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers=_headers())

    # No in-progress session left, so a new POST /sessions starts a brand new one.
    second = client.post("/api/v1/intake/sessions", headers=_headers())
    assert second.status_code == 201
    assert second.json()["id"] != session["id"]
