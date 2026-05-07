"""Interlinks router tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _two_articles(api: TestClient, project_id: int) -> tuple[int, int]:
    """Create two articles for from/to FK references."""
    a = api.post(
        f"/api/v1/projects/{project_id}/articles",
        json={"title": "A", "slug": "art-a"},
    ).json()["data"]
    b = api.post(
        f"/api/v1/projects/{project_id}/articles",
        json={"title": "B", "slug": "art-b"},
    ).json()["data"]
    return int(a["id"]), int(b["id"])


def test_suggest_then_apply(api: TestClient, project_id: int) -> None:
    """suggest → apply moves a row from suggested → applied."""
    a, b = _two_articles(api, project_id)
    sug = api.post(
        f"/api/v1/projects/{project_id}/interlinks/suggest",
        json={
            "suggestions": [
                {
                    "from_article_id": a,
                    "to_article_id": b,
                    "anchor_text": "see also",
                }
            ]
        },
    )
    assert sug.status_code == 201
    link = sug.json()["data"][0]
    applied = api.post(f"/api/v1/projects/{project_id}/interlinks/{link['id']}/apply")
    assert applied.status_code == 200
    assert applied.json()["data"]["status"] == "applied"


def test_dismiss_terminal(api: TestClient, project_id: int) -> None:
    """dismiss is terminal — no transitions out."""
    a, b = _two_articles(api, project_id)
    sug = api.post(
        f"/api/v1/projects/{project_id}/interlinks/suggest",
        json={"suggestions": [{"from_article_id": a, "to_article_id": b, "anchor_text": "x"}]},
    )
    link = sug.json()["data"][0]
    dis = api.post(f"/api/v1/projects/{project_id}/interlinks/{link['id']}/dismiss")
    assert dis.status_code == 200
    # Re-applying a dismissed link should 409.
    again = api.post(f"/api/v1/projects/{project_id}/interlinks/{link['id']}/apply")
    assert again.status_code == 409


def test_repair_marks_applied_links_broken(api: TestClient, project_id: int) -> None:
    """``repair`` flips ``applied`` rows pointing AT ``article_id`` to ``broken``."""
    a, b = _two_articles(api, project_id)
    sug = api.post(
        f"/api/v1/projects/{project_id}/interlinks/suggest",
        json={"suggestions": [{"from_article_id": a, "to_article_id": b, "anchor_text": "x"}]},
    )
    link = sug.json()["data"][0]
    api.post(f"/api/v1/projects/{project_id}/interlinks/{link['id']}/apply")
    rep = api.post(
        f"/api/v1/projects/{project_id}/interlinks/repair",
        json={"article_id": b},
    )
    assert rep.status_code == 200
    rows = rep.json()["data"]
    assert len(rows) == 1
    assert rows[0]["status"] == "broken"


def test_bulk_apply(api: TestClient, project_id: int) -> None:
    """``bulk-apply`` is all-or-nothing across N suggestions."""
    a, b = _two_articles(api, project_id)
    sug = api.post(
        f"/api/v1/projects/{project_id}/interlinks/suggest",
        json={
            "suggestions": [
                {
                    "from_article_id": a,
                    "to_article_id": b,
                    "anchor_text": "x",
                    "position": 1,
                },
                {
                    "from_article_id": a,
                    "to_article_id": b,
                    "anchor_text": "y",
                    "position": 2,
                },
            ]
        },
    )
    ids = [r["id"] for r in sug.json()["data"]]
    resp = api.post(
        f"/api/v1/projects/{project_id}/interlinks/bulk-apply",
        json={"ids": ids},
    )
    assert resp.status_code == 200
    statuses = {r["status"] for r in resp.json()["data"]}
    assert statuses == {"applied"}


def test_list_filters(api: TestClient, project_id: int) -> None:
    """``status`` filter restricts the list."""
    resp = api.get(f"/api/v1/projects/{project_id}/interlinks?status=suggested")
    assert resp.status_code == 200
