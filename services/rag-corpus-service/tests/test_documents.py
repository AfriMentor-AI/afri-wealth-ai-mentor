from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"X-User-Id": "user-test-123", "X-User-Roles": "admin"}
NON_ADMIN_AUTH = {"X-User-Id": "user-test-456"}

def test_ingest_missing_auth_returns_403():
    # Card O3.5: this endpoint is now admin-gated. With zero headers at all,
    # the admin-role dependency (X-User-Roles defaults to "", not required)
    # resolves and rejects before FastAPI gets to report the still-missing
    # required X-User-Id header — so the response is 403, not 422.
    r = client.post(
        "/api/v1/rag/documents",
        json={"filename": "test.pdf", "text": "Some content"},
    )
    assert r.status_code == 403

def test_list_documents_missing_auth_returns_403():
    r = client.get("/api/v1/rag/documents")
    assert r.status_code == 403

def test_delete_missing_auth_returns_403():
    r = client.delete("/api/v1/rag/documents/some-id")
    assert r.status_code == 403

def test_query_missing_auth_returns_422():
    r = client.post("/api/v1/rag/query", json={"query": "how to save money"})
    assert r.status_code == 422

def test_query_empty_string_rejected():
    r = client.post(
        "/api/v1/rag/query",
        json={"query": ""},
        headers=AUTH,
    )
    assert r.status_code == 422

def test_delete_nonexistent_doc_returns_404():
    from unittest.mock import MagicMock

    from app.api import routes

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Override the dependency used by the router so the endpoint uses our mock
    def _mock_get_db():
        yield mock_db

    client.app.dependency_overrides[routes.get_db] = _mock_get_db
    try:
        r = client.delete("/api/v1/rag/documents/nonexistent-id", headers=AUTH)
    finally:
        client.app.dependency_overrides.pop(routes.get_db, None)

    assert r.status_code == 404


# ── Admin-role gate (card O3.5) ──────────────────────────────────────────────
# Regression tests for the fix: ingest/list/delete/export/stats used to accept
# any authenticated user, letting a non-admin ingest/delete/export the shared
# corpus. POST /query is deliberately exempt — every user needs it for chat.

def test_ingest_requires_admin_role():
    r = client.post(
        "/api/v1/rag/documents",
        json={"filename": "test.pdf", "text": "Some content"},
        headers=NON_ADMIN_AUTH,
    )
    assert r.status_code == 403


def test_list_documents_requires_admin_role():
    r = client.get("/api/v1/rag/documents", headers=NON_ADMIN_AUTH)
    assert r.status_code == 403


def test_delete_requires_admin_role():
    r = client.delete("/api/v1/rag/documents/some-id", headers=NON_ADMIN_AUTH)
    assert r.status_code == 403


def test_query_does_not_require_admin_role():
    r = client.post(
        "/api/v1/rag/query", json={"query": "how to save money"}, headers=NON_ADMIN_AUTH
    )
    assert r.status_code == 200
