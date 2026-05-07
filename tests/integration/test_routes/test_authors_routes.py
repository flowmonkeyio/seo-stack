"""Author router tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_authors_full_cycle(api: TestClient, project_id: int) -> None:
    """Create + list + patch + delete."""
    create = api.post(
        f"/api/v1/projects/{project_id}/authors",
        json={"name": "Jane Doe", "slug": "jane-doe", "role": "Editor"},
    )
    assert create.status_code == 201
    author_id = create.json()["data"]["id"]

    listing = api.get(f"/api/v1/projects/{project_id}/authors").json()
    assert any(a["slug"] == "jane-doe" for a in listing["items"])

    patch = api.patch(
        f"/api/v1/projects/{project_id}/authors/{author_id}",
        json={"role": "Senior Editor"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["role"] == "Senior Editor"

    deleted = api.delete(f"/api/v1/projects/{project_id}/authors/{author_id}")
    assert deleted.status_code == 200


def test_author_slug_unique_per_project(api: TestClient, project_id: int) -> None:
    """Duplicate slug → 409."""
    api.post(
        f"/api/v1/projects/{project_id}/authors",
        json={"name": "X", "slug": "dup"},
    )
    resp = api.post(
        f"/api/v1/projects/{project_id}/authors",
        json={"name": "Y", "slug": "dup"},
    )
    assert resp.status_code == 409
