"""GSC router tests — bulk ingest, query, rollup, redirects."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient


def test_bulk_ingest_inserts_rows(api: TestClient, project_id: int, article_id: int) -> None:
    """Repeated ingestion of the same row dedupes (uq_gsc_metrics_dedup).

    SQLite treats NULL columns as distinct in UNIQUE constraints; we set
    ``article_id`` so the dedup actually triggers per audit / PLAN.md L483.
    """
    payload = {
        "project_id": project_id,
        "rows": [
            {
                "article_id": article_id,
                "captured_at": "2026-05-07T00:00:00",
                "dimensions_hash": "h1",
                "impressions": 100,
                "clicks": 5,
                "ctr": 0.05,
                "avg_position": 7.0,
            }
        ],
    }
    r1 = api.post("/api/v1/gsc/bulk", json=payload)
    assert r1.status_code == 201
    assert r1.json()["data"]["inserted"] == 1
    r2 = api.post("/api/v1/gsc/bulk", json=payload)
    assert r2.json()["data"]["inserted"] == 0


def test_query_project(api: TestClient, project_id: int) -> None:
    """Queries return rows in ``[since, until)`` window."""
    api.post(
        "/api/v1/gsc/bulk",
        json={
            "project_id": project_id,
            "rows": [
                {
                    "captured_at": "2026-05-07T00:00:00",
                    "dimensions_hash": "h2",
                    "impressions": 10,
                    "clicks": 1,
                    "ctr": 0.1,
                    "avg_position": 3.0,
                }
            ],
        },
    )
    resp = api.get(
        f"/api/v1/projects/{project_id}/gsc?since=2026-05-01T00:00:00&until=2026-05-08T00:00:00"
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["impressions"] == 10 for r in rows)


def test_rollup_writes_daily_row(api: TestClient, project_id: int) -> None:
    """Rollup aggregates raw rows into the daily table."""
    api.post(
        "/api/v1/gsc/bulk",
        json={
            "project_id": project_id,
            "rows": [
                {
                    "captured_at": "2026-05-07T03:00:00",
                    "dimensions_hash": "ha",
                    "impressions": 5,
                    "clicks": 1,
                    "ctr": 0.2,
                    "avg_position": 5.0,
                },
                {
                    "captured_at": "2026-05-07T15:00:00",
                    "dimensions_hash": "hb",
                    "impressions": 7,
                    "clicks": 2,
                    "ctr": 0.28,
                    "avg_position": 4.0,
                },
            ],
        },
    )
    resp = api.post(f"/api/v1/projects/{project_id}/gsc/rollup?day=2026-05-07")
    assert resp.status_code == 200
    assert resp.json()["data"]["inserted"] >= 1


def test_redirects_full_cycle(api: TestClient, project_id: int) -> None:
    """Create + list redirects."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/redirects",
        json={"from_url": "/old", "kind": "301"},
    )
    assert resp.status_code == 201
    rows = api.get(f"/api/v1/projects/{project_id}/redirects").json()["items"]
    assert any(r["from_url"] == "/old" for r in rows)


_ = datetime  # imported for date docstrings
