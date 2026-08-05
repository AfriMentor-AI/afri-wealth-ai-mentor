from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"X-User-Id": "user-test-123"}

def test_ingest_missing_auth_returns_422():
    r = client.post(
        "/api/v1/rag/documents",
        json={"filename": "test.pdf", "text": "Some content"},
    )
    assert r.status_code == 422

def test_list_documents_missing_auth_returns_422():
    r = client.get("/api/v1/rag/documents")
    assert r.status_code == 422

def test_delete_missing_auth_returns_422():
    r = client.delete("/api/v1/rag/documents/some-id")
    assert r.status_code == 422

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
