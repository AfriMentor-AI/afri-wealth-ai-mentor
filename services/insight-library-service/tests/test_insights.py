"""Tests for insight-library-service (card O3.2)."""
from __future__ import annotations

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}
ADMIN_HEADERS = {"X-User-Id": "user-admin", "X-User-Roles": "admin"}


def _insight_id_by_title(client, title: str) -> str:
    items = client.get("/api/v1/insights", headers=USER_HEADERS).json()
    return next(i["id"] for i in items if i["title"] == title)


# ── Catalog / search / filter ────────────────────────────────────────────────

def test_seed_data_present(client):
    r = client.get("/api/v1/insights", headers=USER_HEADERS)
    assert r.status_code == 200
    titles = {i["title"] for i in r.json()}
    assert "How to price your trade" in titles
    assert "Saving during lean seasons" in titles
    assert "Bookkeeping with Mobile Money" in titles


def test_list_requires_identity(client):
    r = client.get("/api/v1/insights")
    assert r.status_code == 422


def test_search_matches_title_and_summary(client):
    r = client.get("/api/v1/insights?search=mobile money", headers=USER_HEADERS)
    titles = {i["title"] for i in r.json()}
    assert titles == {"Bookkeeping with Mobile Money"}


def test_category_filter_scoped(client):
    r = client.get("/api/v1/insights?category=Savings", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["category"] == "Savings" for i in items)


def test_media_type_filter_audio(client):
    r = client.get("/api/v1/insights?media_type=audio", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["media_type"] == "audio" for i in items)


def test_media_type_filter_video(client):
    r = client.get("/api/v1/insights?media_type=video", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["media_type"] == "video" for i in items)


def test_media_type_filter_text(client):
    r = client.get("/api/v1/insights?media_type=text", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["media_type"] == "text" for i in items)


def test_language_filter(client):
    r = client.get("/api/v1/insights?language=sw", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["language"] == "sw" for i in items)


def test_difficulty_filter(client):
    r = client.get("/api/v1/insights?difficulty=advanced", headers=USER_HEADERS)
    items = r.json()
    assert len(items) >= 1
    assert all(i["difficulty"] == "advanced" for i in items)


def test_combined_filters_scoped(client):
    r = client.get(
        "/api/v1/insights?category=Bookkeeping&media_type=text", headers=USER_HEADERS
    )
    titles = {i["title"] for i in r.json()}
    assert "Bookkeeping with Mobile Money" in titles
    assert all(i["media_type"] == "text" for i in r.json())


def test_response_has_duration_seconds(client):
    r = client.get("/api/v1/insights", headers=USER_HEADERS)
    for item in r.json():
        assert "duration_seconds" in item
        assert item["duration_seconds"] > 0


def test_get_insight_not_found(client):
    r = client.get("/api/v1/insights/does-not-exist", headers=USER_HEADERS)
    assert r.status_code == 404


# ── Favorites / bookmarks ────────────────────────────────────────────────────

def test_bookmark_marks_is_favorited_for_owner_only(client):
    insight_id = _insight_id_by_title(client, "How to price your trade")

    r = client.post(f"/api/v1/insights/{insight_id}/bookmark", headers=USER_HEADERS)
    assert r.status_code == 204

    mine = client.get(f"/api/v1/insights/{insight_id}", headers=USER_HEADERS).json()
    assert mine["is_favorited"] is True

    theirs = client.get(f"/api/v1/insights/{insight_id}", headers=OTHER_HEADERS).json()
    assert theirs["is_favorited"] is False


def test_bookmark_is_idempotent(client):
    insight_id = _insight_id_by_title(client, "How to price your trade")
    url = f"/api/v1/insights/{insight_id}/bookmark"
    assert client.post(url, headers=USER_HEADERS).status_code == 204
    assert client.post(url, headers=USER_HEADERS).status_code == 204

    bookmarks = client.get("/api/v1/insights/bookmarks", headers=USER_HEADERS).json()
    assert len(bookmarks) == 1


def test_bookmark_nonexistent_insight_404(client):
    r = client.post("/api/v1/insights/does-not-exist/bookmark", headers=USER_HEADERS)
    assert r.status_code == 404


def test_unbookmark_clears_favorite(client):
    insight_id = _insight_id_by_title(client, "How to price your trade")
    client.post(f"/api/v1/insights/{insight_id}/bookmark", headers=USER_HEADERS)
    r = client.delete(f"/api/v1/insights/{insight_id}/bookmark", headers=USER_HEADERS)
    assert r.status_code == 204

    item = client.get(f"/api/v1/insights/{insight_id}", headers=USER_HEADERS).json()
    assert item["is_favorited"] is False


def test_list_bookmarks_returns_only_favorited(client):
    a = _insight_id_by_title(client, "How to price your trade")
    b = _insight_id_by_title(client, "Saving during lean seasons")
    client.post(f"/api/v1/insights/{a}/bookmark", headers=USER_HEADERS)
    client.post(f"/api/v1/insights/{b}/bookmark", headers=USER_HEADERS)

    bookmarks = client.get("/api/v1/insights/bookmarks", headers=USER_HEADERS).json()
    assert {i["id"] for i in bookmarks} == {a, b}

    other_bookmarks = client.get("/api/v1/insights/bookmarks", headers=OTHER_HEADERS).json()
    assert other_bookmarks == []


# ── Catalog authoring (admin-only) ───────────────────────────────────────────

def test_create_insight_requires_admin_role(client):
    r = client.post(
        "/api/v1/insights",
        json={
            "title": "New lesson",
            "summary": "Something new.",
            "category": "Pricing",
            "media_type": "text",
            "duration_seconds": 240,
        },
        headers=USER_HEADERS,
    )
    assert r.status_code == 403


def test_create_insight_as_admin(client):
    r = client.post(
        "/api/v1/insights",
        json={
            "title": "New audio lesson",
            "summary": "Something new.",
            "category": "Pricing",
            "media_type": "audio",
            "duration_seconds": 240,
            "language": "en",
            "difficulty": "beginner",
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "New audio lesson"
    assert body["media_type"] == "audio"
    assert body["duration_seconds"] == 240

    titles = {i["title"] for i in client.get("/api/v1/insights", headers=USER_HEADERS).json()}
    assert "New audio lesson" in titles


def test_create_insight_invalid_media_type(client):
    r = client.post(
        "/api/v1/insights",
        json={
            "title": "Bad type",
            "summary": "x",
            "category": "Pricing",
            "media_type": "podcast",
            "duration_seconds": 60,
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_create_insight_invalid_difficulty(client):
    r = client.post(
        "/api/v1/insights",
        json={
            "title": "Bad difficulty",
            "summary": "x",
            "category": "Pricing",
            "media_type": "text",
            "duration_seconds": 60,
            "difficulty": "expert",
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


# ── Progress tracking ────────────────────────────────────────────────────────

def test_progress_upsert_and_get(client):
    insight_id = _insight_id_by_title(client, "Saving during lean seasons")

    r = client.put(
        f"/api/v1/insights/{insight_id}/progress",
        json={"position_seconds": 120, "completed": False},
        headers=USER_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["position_seconds"] == 120
    assert body["completed"] is False
    assert body["insight_id"] == insight_id

    r2 = client.get(f"/api/v1/insights/{insight_id}/progress", headers=USER_HEADERS)
    assert r2.status_code == 200
    assert r2.json()["position_seconds"] == 120


def test_progress_update_advances_position(client):
    insight_id = _insight_id_by_title(client, "Saving during lean seasons")
    client.put(
        f"/api/v1/insights/{insight_id}/progress",
        json={"position_seconds": 60, "completed": False},
        headers=USER_HEADERS,
    )
    client.put(
        f"/api/v1/insights/{insight_id}/progress",
        json={"position_seconds": 300, "completed": True},
        headers=USER_HEADERS,
    )
    r = client.get(f"/api/v1/insights/{insight_id}/progress", headers=USER_HEADERS)
    assert r.json()["position_seconds"] == 300
    assert r.json()["completed"] is True


def test_progress_isolated_per_user(client):
    insight_id = _insight_id_by_title(client, "Saving during lean seasons")
    client.put(
        f"/api/v1/insights/{insight_id}/progress",
        json={"position_seconds": 200, "completed": False},
        headers=USER_HEADERS,
    )
    r = client.get(f"/api/v1/insights/{insight_id}/progress", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_progress_not_allowed_for_text(client):
    insight_id = _insight_id_by_title(client, "How to price your trade")
    r = client.put(
        f"/api/v1/insights/{insight_id}/progress",
        json={"position_seconds": 10, "completed": False},
        headers=USER_HEADERS,
    )
    assert r.status_code == 400


def test_progress_get_no_record_404(client):
    insight_id = _insight_id_by_title(client, "Saving during lean seasons")
    r = client.get(f"/api/v1/insights/{insight_id}/progress", headers=USER_HEADERS)
    assert r.status_code == 404
