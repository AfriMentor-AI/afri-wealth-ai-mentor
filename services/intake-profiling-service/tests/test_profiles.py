"""Diagnostic profile lookup tests (card O2.2 acceptance: GET /profiles/{userId}/diagnostic)."""

USER = "user-ama"


def _complete_intake(client, user=USER):
    session = client.post("/api/v1/intake/sessions", headers={"X-User-Id": user}).json()
    steps = [
        ("sector", {"sector": "Creative"}),
        (
            "education_time",
            {"education_level": "Vocational training", "time_available_per_week": "11-20 hours"},
        ),
        ("constraints", {"constraints": []}),
        (
            "confirm",
            {"name": "Ama Boateng", "business_name": "Ama Designs", "location": "Accra"},
        ),
    ]
    for step, payload in steps:
        client.post(
            f"/api/v1/intake/sessions/{session['id']}/answers",
            json={"step": step, "payload": payload},
            headers={"X-User-Id": user},
        )
    client.post(f"/api/v1/intake/sessions/{session['id']}/complete", headers={"X-User-Id": user})


def test_diagnostic_profile_not_found_before_intake(client):
    r = client.get(f"/api/v1/profiles/{USER}/diagnostic", headers={"X-User-Id": USER})
    assert r.status_code == 404


def test_diagnostic_profile_self_lookup(client):
    _complete_intake(client)
    r = client.get(f"/api/v1/profiles/{USER}/diagnostic", headers={"X-User-Id": USER})
    assert r.status_code == 200
    assert r.json()["sector"] == "Creative"


def test_diagnostic_profile_rejects_other_users_via_gateway_header(client):
    _complete_intake(client)
    r = client.get(f"/api/v1/profiles/{USER}/diagnostic", headers={"X-User-Id": "someone-else"})
    assert r.status_code == 403


def test_diagnostic_profile_allows_internal_service_call_without_header(client):
    """No X-User-Id at all means the caller reached this service directly on the
    docker network (e.g. Chat Orchestration), not through the gateway — trusted."""
    _complete_intake(client)
    r = client.get(f"/api/v1/profiles/{USER}/diagnostic")
    assert r.status_code == 200
    assert r.json()["user_id"] == USER
