"""Pagination wire-shape tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_pagination_defaults(api: TestClient) -> None:
    """Default page is ``limit=50`` (we don't have 50 projects, so cursor None)."""
    resp = api.get("/api/v1/projects")
    body = resp.json()
    assert resp.status_code == 200
    assert "items" in body
    assert "next_cursor" in body
    assert "total_estimate" in body
    # Empty universe — cursor None.
    assert body["next_cursor"] is None


def test_pagination_limit_capped_at_200(api: TestClient) -> None:
    """``limit=999`` is rejected with 422 (FastAPI Query bound)."""
    resp = api.get("/api/v1/projects?limit=999")
    assert resp.status_code == 422


def test_pagination_after_returns_empty_when_no_data(api: TestClient) -> None:
    """``after=999`` on an empty table returns an empty page."""
    resp = api.get("/api/v1/projects?after=999")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_pagination_traverses_pages(api: TestClient) -> None:
    """Create 3 projects and walk them with limit=2 to verify the cursor."""
    for slug in ("p1", "p2", "p3"):
        resp = api.post(
            "/api/v1/projects",
            json={
                "slug": slug,
                "name": slug.upper(),
                "domain": f"{slug}.com",
                "locale": "en-US",
            },
        )
        assert resp.status_code == 201
    page1 = api.get("/api/v1/projects?limit=2").json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None
    assert page1["total_estimate"] == 3
    page2 = api.get(f"/api/v1/projects?limit=2&after={page1['next_cursor']}").json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
