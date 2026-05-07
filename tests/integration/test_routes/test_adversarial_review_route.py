"""REST adversarial-review route — happy + plugin-missing."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_post_returns_skipped_when_plugin_not_installed(
    api: TestClient,
    project_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No CLAUDE_PLUGIN_ROOT → ``{verdict: 'SKIPPED', reason: 'plugin-not-installed'}``."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    resp = api.post(
        "/api/v1/adversarial-review",
        json={
            "article_md": "# Article",
            "eeat_criteria": [{"code": "T04"}],
            "project_id": project_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"verdict": "SKIPPED", "reason": "plugin-not-installed"}


def test_post_validates_required_fields(api: TestClient) -> None:
    """Missing ``article_md`` → 422."""
    resp = api.post(
        "/api/v1/adversarial-review",
        json={"project_id": 1},
    )
    assert resp.status_code == 422


def test_post_rejects_unknown_fields(api: TestClient, project_id: int) -> None:
    """``extra='forbid'`` rejects unknown body fields."""
    resp = api.post(
        "/api/v1/adversarial-review",
        json={
            "article_md": "# X",
            "eeat_criteria": [],
            "project_id": project_id,
            "rogue_field": "should-fail",
        },
    )
    assert resp.status_code == 422
