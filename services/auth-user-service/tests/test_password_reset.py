"""Password reset flow tests (card O2.1)."""


def _signup(client, email="chidi@example.com", password="correcthorse1"):
    return client.post(
        "/auth/signup", json={"email": email, "password": password, "name": "Chidi"}
    ).json()


def test_request_reset_for_known_email_returns_token_in_dev(client):
    _signup(client)
    r = client.post("/auth/password-reset/request", json={"email": "chidi@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["reset_token"]  # APP_ENV=test in this fixture, not prod


def test_request_reset_for_unknown_email_is_indistinguishable(client):
    r = client.post("/auth/password-reset/request", json={"email": "ghost@example.com"})
    assert r.status_code == 200
    body = r.json()
    # Same shape/absence of a token either way — doesn't leak whether the email exists.
    assert body["reset_token"] is None


def test_confirm_reset_changes_password_and_is_single_use(client):
    _signup(client)
    req = client.post(
        "/auth/password-reset/request", json={"email": "chidi@example.com"}
    ).json()
    token = req["reset_token"]

    confirm = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": token, "new_password": "newpassword2"},
    )
    assert confirm.status_code == 204

    # Old password no longer works, new one does.
    old = client.post(
        "/auth/login", json={"email": "chidi@example.com", "password": "correcthorse1"}
    )
    assert old.status_code == 401
    new = client.post(
        "/auth/login", json={"email": "chidi@example.com", "password": "newpassword2"}
    )
    assert new.status_code == 200

    # The token cannot be reused.
    reuse = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": token, "new_password": "yetanother3"},
    )
    assert reuse.status_code == 400


def test_new_reset_request_invalidates_earlier_unused_token(client):
    _signup(client)
    first = client.post(
        "/auth/password-reset/request", json={"email": "chidi@example.com"}
    ).json()["reset_token"]
    second = client.post(
        "/auth/password-reset/request", json={"email": "chidi@example.com"}
    ).json()["reset_token"]
    assert first != second

    stale = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": first, "new_password": "newpassword2"},
    )
    assert stale.status_code == 400

    fresh = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": second, "new_password": "newpassword2"},
    )
    assert fresh.status_code == 204


def test_confirm_reset_rejects_unknown_token(client):
    r = client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": "not-a-real-token", "new_password": "newpassword2"},
    )
    assert r.status_code == 400


def test_confirm_reset_invalidates_existing_sessions(client):
    tokens = _signup(client)
    req = client.post(
        "/auth/password-reset/request", json={"email": "chidi@example.com"}
    ).json()
    client.post(
        "/auth/password-reset/confirm",
        json={"reset_token": req["reset_token"], "new_password": "newpassword2"},
    )
    refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_reset_token_omitted_in_prod(client, monkeypatch):
    _signup(client, email="prod@example.com")
    from app.routers import auth as auth_router_module

    monkeypatch.setattr(auth_router_module.settings, "env", "prod")
    r = client.post("/auth/password-reset/request", json={"email": "prod@example.com"})
    assert r.status_code == 200
    assert r.json()["reset_token"] is None
