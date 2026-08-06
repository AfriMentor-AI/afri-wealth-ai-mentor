"""Profile CRUD tests: PATCH/DELETE /auth/me (card O2.1)."""


def _signup(client, email="bola@example.com"):
    payload = {
        "email": email,
        "password": "correcthorse1",
        "name": "Bola",
        "age": 34,
        "country": "NG",
        "device_type": "mid",
        "sector_interest": "tech",
        "education_level": "tertiary",
        "language": "en",
        "income_bracket": "mid",
    }
    return client.post("/auth/signup", json=payload).json()


def _auth_header(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_patch_me_updates_only_supplied_fields(client):
    tokens = _signup(client)
    r = client.patch("/auth/me", json={"name": "Bola A."}, headers=_auth_header(tokens))
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Bola A."
    # untouched fields survive the partial update
    assert body["country"] == "NG"
    assert body["sector_interest"] == "tech"


def test_patch_me_can_change_sector_and_income(client):
    tokens = _signup(client)
    r = client.patch(
        "/auth/me",
        json={"sector_interest": "creative", "income_bracket": "upper_mid"},
        headers=_auth_header(tokens),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sector_interest"] == "creative"
    assert body["income_bracket"] == "upper_mid"


def test_patch_me_rejects_invalid_enum(client):
    tokens = _signup(client)
    r = client.patch(
        "/auth/me", json={"sector_interest": "not-a-real-sector"}, headers=_auth_header(tokens)
    )
    assert r.status_code == 422


def test_patch_me_requires_auth(client):
    r = client.patch("/auth/me", json={"name": "Nope"})
    assert r.status_code == 401


def test_delete_me_deactivates_and_revokes_sessions(client):
    tokens = _signup(client)
    r = client.delete("/auth/me", headers=_auth_header(tokens))
    assert r.status_code == 204

    # Deactivated account can no longer log in...
    login = client.post(
        "/auth/login", json={"email": "bola@example.com", "password": "correcthorse1"}
    )
    assert login.status_code == 403

    # ...and its existing refresh token no longer works (sessions revoked).
    refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_delete_me_requires_auth(client):
    assert client.delete("/auth/me").status_code == 401


def test_deactivated_account_access_token_is_rejected_immediately(client):
    """A still-unexpired access token from before deactivation must stop working too,
    not just the refresh token (card O2.1: DELETE /auth/me hardening)."""
    tokens = _signup(client)
    client.delete("/auth/me", headers=_auth_header(tokens))
    r = client.get("/auth/me", headers=_auth_header(tokens))
    assert r.status_code == 401
