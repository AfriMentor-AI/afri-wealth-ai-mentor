def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "intake-profiling-service"


def test_root_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "intake-profiling-service"
