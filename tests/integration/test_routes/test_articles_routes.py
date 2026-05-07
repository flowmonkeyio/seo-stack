"""Article CRUD + procedure-4 walk via REST.

The procedure-4 happy path: brief, outline, draft (3 append calls),
mark-drafted, edit, eeat-pass, publish — each step carrying the
``expected_etag`` rotated by the previous one.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_run(api: TestClient, project_id: int) -> int:
    """Insert a Run row directly via repository (no REST start endpoint)."""
    # We use the article repository import path because Session is held by
    # the dependency hierarchy; the cheapest way is to hit the test client
    # through a hook. Instead, lean on the article router by walking the
    # state machine — every transition past EEAT requires a real run id,
    # so we drop into the underlying engine here.
    # Simpler: use the daemon's app.state engine to write a row.
    engine = api.app.state.engine  # type: ignore[attr-defined]
    from sqlmodel import Session

    from content_stack.db.models import Run, RunKind, RunStatus

    with Session(engine) as s:
        run = Run(
            project_id=project_id,
            kind=RunKind.EEAT_GATE,
            status=RunStatus.RUNNING,
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        assert run.id is not None
        return run.id


def test_create_and_get_article(api: TestClient, project_id: int, article_id: int) -> None:
    """Article is created in ``status='briefing'`` with a fresh ``step_etag``."""
    resp = api.get(f"/api/v1/articles/{article_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "briefing"
    assert body["step_etag"] is not None


def test_full_procedure_4_walk(api: TestClient, project_id: int, article_id: int) -> None:
    """Brief → outline → draft → mark-drafted → edit → eeat-pass → publish."""
    article = api.get(f"/api/v1/articles/{article_id}").json()
    etag = article["step_etag"]

    # Brief.
    resp = api.post(
        f"/api/v1/articles/{article_id}/brief",
        json={"expected_etag": etag, "brief_json": {"hook": "test"}},
    )
    assert resp.status_code == 200
    article = resp.json()["data"]
    assert article["status"] == "outlined"
    etag = article["step_etag"]

    # Outline.
    resp = api.post(
        f"/api/v1/articles/{article_id}/outline",
        json={"expected_etag": etag, "outline_md": "## Outline"},
    )
    assert resp.status_code == 200
    article = resp.json()["data"]
    etag = article["step_etag"]

    # Draft #1 (replace).
    resp = api.post(
        f"/api/v1/articles/{article_id}/draft",
        json={"expected_etag": etag, "draft_md": "# Intro\n"},
    )
    article = resp.json()["data"]
    etag = article["step_etag"]
    # Draft #2 (append).
    resp = api.post(
        f"/api/v1/articles/{article_id}/draft?append=true",
        json={"expected_etag": etag, "draft_md": "## Body\n"},
    )
    article = resp.json()["data"]
    etag = article["step_etag"]
    # Draft #3 (append).
    resp = api.post(
        f"/api/v1/articles/{article_id}/draft?append=true",
        json={"expected_etag": etag, "draft_md": "## Conclusion\n"},
    )
    article = resp.json()["data"]
    assert "Conclusion" in article["draft_md"]
    etag = article["step_etag"]

    # Mark drafted.
    resp = api.post(
        f"/api/v1/articles/{article_id}/draft/mark-drafted",
        json={"expected_etag": etag},
    )
    article = resp.json()["data"]
    assert article["status"] == "drafted"
    etag = article["step_etag"]

    # Edit.
    resp = api.post(
        f"/api/v1/articles/{article_id}/edit",
        json={"expected_etag": etag, "edited_md": "edited"},
    )
    article = resp.json()["data"]
    assert article["status"] == "edited"
    etag = article["step_etag"]

    # EEAT pass — needs a real run id.
    run_id = _seed_run(api, project_id)
    resp = api.post(
        f"/api/v1/articles/{article_id}/eeat-pass",
        json={"expected_etag": etag, "run_id": run_id, "eeat_criteria_version": 1},
    )
    article = resp.json()["data"]
    assert article["status"] == "eeat_passed"
    etag = article["step_etag"]

    # Publish.
    resp = api.post(
        f"/api/v1/articles/{article_id}/publish",
        json={"expected_etag": etag, "run_id": run_id},
    )
    article = resp.json()["data"]
    assert article["status"] == "published"


def test_etag_mismatch_returns_412(api: TestClient, article_id: int) -> None:
    """Stale ``expected_etag`` yields 412 (etag-mismatch ConflictError)."""
    resp = api.post(
        f"/api/v1/articles/{article_id}/brief",
        json={"expected_etag": "stale", "brief_json": {}},
    )
    assert resp.status_code == 412
    assert resp.json()["code"] == -32008


def test_slug_immutable_after_publish(api: TestClient, project_id: int, article_id: int) -> None:
    """Slug PATCH is rejected on a published article (repo: 409 → mapped 412 in our handler)."""
    # Walk to published quickly through the typed verbs.
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    api.post(
        f"/api/v1/articles/{article_id}/brief",
        json={"expected_etag": etag, "brief_json": {}},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    api.post(
        f"/api/v1/articles/{article_id}/outline",
        json={"expected_etag": etag, "outline_md": "x"},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    api.post(
        f"/api/v1/articles/{article_id}/draft",
        json={"expected_etag": etag, "draft_md": "x"},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    api.post(
        f"/api/v1/articles/{article_id}/draft/mark-drafted",
        json={"expected_etag": etag},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    api.post(
        f"/api/v1/articles/{article_id}/edit",
        json={"expected_etag": etag, "edited_md": "x"},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    run_id = _seed_run(api, project_id)
    api.post(
        f"/api/v1/articles/{article_id}/eeat-pass",
        json={"expected_etag": etag, "run_id": run_id, "eeat_criteria_version": 1},
    )
    art = api.get(f"/api/v1/articles/{article_id}").json()
    etag = art["step_etag"]
    pub = api.post(
        f"/api/v1/articles/{article_id}/publish",
        json={"expected_etag": etag, "run_id": run_id},
    )
    assert pub.status_code == 200

    # Slug PATCH must now fail with conflict (the repo raises ConflictError;
    # our handler maps non-etag conflicts to 409 — etag conflicts to 412).
    resp = api.patch(f"/api/v1/articles/{article_id}", json={"slug": "new-slug"})
    assert resp.status_code in (409, 412)


def test_article_patch_with_if_match(api: TestClient, article_id: int) -> None:
    """``If-Match`` matching the row's ``updated_at`` succeeds; stale → 412."""
    art = api.get(f"/api/v1/articles/{article_id}").json()
    good = art["updated_at"]
    resp = api.patch(
        f"/api/v1/articles/{article_id}",
        json={"title": "New Title"},
        headers={"If-Match": good},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "New Title"

    stale = api.patch(
        f"/api/v1/articles/{article_id}",
        json={"title": "Newer"},
        headers={"If-Match": good},  # already advanced by previous PATCH
    )
    assert stale.status_code == 412


def test_refresh_due_listing(api: TestClient, project_id: int) -> None:
    """``refresh-due`` returns an empty page when nothing is published yet."""
    resp = api.get(f"/api/v1/projects/{project_id}/articles/refresh-due")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
