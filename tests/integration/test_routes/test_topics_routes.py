"""Topic-route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_list_topics(api: TestClient, project_id: int, topic_id: int) -> None:
    """List shows the created topic."""
    resp = api.get(f"/api/v1/projects/{project_id}/topics")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(t["id"] == topic_id for t in items)


def test_bulk_create_preserves_order(api: TestClient, project_id: int) -> None:
    """Audit M-13: response order matches input order."""
    titles = [f"topic {i}" for i in range(5)]
    resp = api.post(
        f"/api/v1/projects/{project_id}/topics/bulk",
        json={
            "items": [
                {
                    "title": t,
                    "primary_kw": "k",
                    "intent": "informational",
                    "status": "queued",
                    "source": "manual",
                }
                for t in titles
            ]
        },
    )
    assert resp.status_code == 201
    out_titles = [t["title"] for t in resp.json()["data"]]
    assert out_titles == titles


def test_approve_and_reject(api: TestClient, topic_id: int) -> None:
    """``approve`` advances ``queued → approved``; ``reject`` from approved → rejected."""
    resp = api.post(f"/api/v1/topics/{topic_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "approved"

    resp = api.post(f"/api/v1/topics/{topic_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"


def test_bulk_update_status(api: TestClient, project_id: int) -> None:
    """``bulk-update-status`` is all-or-nothing."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/topics/bulk",
        json={
            "items": [
                {
                    "title": f"t{i}",
                    "primary_kw": "k",
                    "intent": "informational",
                    "status": "queued",
                    "source": "manual",
                }
                for i in range(3)
            ]
        },
    )
    ids = [t["id"] for t in resp.json()["data"]]
    upd = api.post(
        f"/api/v1/projects/{project_id}/topics/bulk-update-status",
        json={"ids": ids, "status": "approved"},
    )
    assert upd.status_code == 200
    statuses = {t["status"] for t in upd.json()["data"]}
    assert statuses == {"approved"}


def test_topic_filter_by_status(api: TestClient, project_id: int) -> None:
    """``?status=queued`` filters the list."""
    api.post(
        f"/api/v1/projects/{project_id}/topics",
        json={
            "title": "q-topic",
            "primary_kw": "k",
            "intent": "informational",
            "status": "queued",
            "source": "manual",
        },
    )
    resp = api.get(f"/api/v1/projects/{project_id}/topics?status=queued")
    assert resp.status_code == 200
    for t in resp.json()["items"]:
        assert t["status"] == "queued"


def test_topic_priority_tiebreaker(api: TestClient, project_id: int) -> None:
    """Audit B-16: ``(priority DESC, created_at ASC, id ASC)`` ordering."""
    api.post(
        f"/api/v1/projects/{project_id}/topics",
        json={
            "title": "low",
            "primary_kw": "k",
            "intent": "informational",
            "status": "queued",
            "source": "manual",
            "priority": 10,
        },
    )
    api.post(
        f"/api/v1/projects/{project_id}/topics",
        json={
            "title": "high",
            "primary_kw": "k",
            "intent": "informational",
            "status": "queued",
            "source": "manual",
            "priority": 90,
        },
    )
    resp = api.get(f"/api/v1/projects/{project_id}/topics?sort=priority")
    items = resp.json()["items"]
    # ``high`` (priority=90) must come before ``low`` (priority=10).
    high_idx = next(i for i, t in enumerate(items) if t["title"] == "high")
    low_idx = next(i for i, t in enumerate(items) if t["title"] == "low")
    assert high_idx < low_idx
