"""Unit tests for auth-user-service (card O1.3 acceptance)."""


def _signup_payload(email="ada@example.com"):
    return {
        "email": email,
        "password": "correcthorse1",
        "name": "Ada",
        "age": 29,
        "country": "NG",
        "device_type": "low_end",
        "sector_interest": "trader",
        "education_level": "secondary",
        "language": "en",
        "income_bracket": "low",
    }


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "auth-user-service"


def test_signup_issues_tokens_and_persists_profile(client):
    r = client.post("/auth/signup", json=_signup_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    profile = me.json()
    assert profile["email"] == "ada@example.com"
    assert profile["sector_interest"] == "trader"
    assert profile["country"] == "NG"
    assert profile["device_type"] == "low_end"


def test_signup_duplicate_email_conflicts(client):
    assert client.post("/auth/signup", json=_signup_payload()).status_code == 201
    r = client.post("/auth/signup", json=_signup_payload())
    assert r.status_code == 409


def test_signup_rejects_short_password(client):
    payload = _signup_payload()
    payload["password"] = "short"
    assert client.post("/auth/signup", json=payload).status_code == 422


def test_login_success_and_wrong_password(client):
    client.post("/auth/signup", json=_signup_payload())
    ok = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correcthorse1"}
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "nope"}
    )
    assert bad.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever12"})
    assert r.status_code == 401


def test_refresh_rotates_and_old_token_is_revoked(client):
    tokens = client.post("/auth/signup", json=_signup_payload()).json()
    r1 = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    new_tokens = r1.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Old refresh token must now be rejected (single-use rotation).
    reuse = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


def test_refresh_rejects_access_token(client):
    tokens = client.post("/auth/signup", json=_signup_payload()).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = client.post("/auth/signup", json=_signup_payload()).json()
    out = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_jwks_exposes_public_key(client):
    r = client.get("/auth/.well-known/jwks")
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "RS256"
    assert "BEGIN PUBLIC KEY" in body["public_key_pem"]
