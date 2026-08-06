"""Gateway unit tests (card O1.3 acceptance): unauthenticated rejection, routing,
identity forwarding, and rate limiting. Upstream calls are mocked."""
import httpx


class _FakeResponse:
    def __init__(self, status=200, json_body=None):
        import json

        self.status_code = status
        self.content = json.dumps(json_body or {}).encode()
        self.headers = {"content-type": "application/json"}


def _patch_upstream(monkeypatch, capture=None):
    async def fake_request(self, method, url, **kwargs):
        if capture is not None:
            capture["url"] = url
            capture["headers"] = kwargs.get("headers", {})
            capture["method"] = method
        return _FakeResponse(200, {"ok": True, "url": url})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "api-gateway"


def test_unknown_route_404(client):
    r = client.get("/api/v1/nonexistent/thing")
    assert r.status_code == 404


def test_protected_route_rejects_missing_token(client):
    r = client.get("/api/v1/goals")
    assert r.status_code == 401
    assert "missing bearer" in r.json()["detail"].lower()


def test_protected_route_rejects_bad_token(client):
    r = client.get("/api/v1/goals", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_protected_route_rejects_expired_token(client, token_factory):
    tok = token_factory(expired=True)
    r = client.get("/api/v1/goals", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_protected_route_rejects_refresh_token(client, token_factory):
    tok = token_factory(token_type="refresh")
    r = client.get("/api/v1/goals", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_public_auth_route_needs_no_token(client, monkeypatch):
    capture = {}
    _patch_upstream(monkeypatch, capture)
    r = client.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "x"})
    assert r.status_code == 200
    assert capture["url"].endswith("/api/v1/auth/login")


def test_valid_token_proxies_and_forwards_identity(client, token_factory, monkeypatch):
    capture = {}
    _patch_upstream(monkeypatch, capture)
    tok = token_factory(sub="user-42", roles=["user", "admin"])
    r = client.get("/api/v1/goals", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert capture["headers"]["X-User-Id"] == "user-42"
    assert capture["headers"]["X-User-Roles"] == "user,admin"
    # client-supplied identity headers must be stripped/overwritten
    assert capture["url"].endswith("/api/v1/goals")


def test_profiles_route_proxies_to_intake_service(client, token_factory, monkeypatch):
    capture = {}
    _patch_upstream(monkeypatch, capture)
    tok = token_factory(sub="user-42")
    r = client.get(
        "/api/v1/profiles/user-42/diagnostic", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200
    assert capture["url"].endswith("/api/v1/profiles/user-42/diagnostic")
    assert capture["headers"]["X-User-Id"] == "user-42"


def test_client_cannot_spoof_identity_header(client, token_factory, monkeypatch):
    capture = {}
    _patch_upstream(monkeypatch, capture)
    tok = token_factory(sub="real-user")
    client.get(
        "/api/v1/goals",
        headers={"Authorization": f"Bearer {tok}", "X-User-Id": "attacker"},
    )
    assert capture["headers"]["X-User-Id"] == "real-user"


def test_rate_limit_returns_429(client, monkeypatch):
    _patch_upstream(monkeypatch)
    # public auth route limit is 20/min; hammer past it from one IP
    last = None
    for _ in range(25):
        last = client.post("/api/v1/auth/login", json={})
    assert last.status_code == 429
    assert last.headers.get("Retry-After")
