"""Tests for ``POST /api/v1/projects/{id}/sitemap-fetch``.

The route is a thin REST seam over
``content_stack.integrations.sitemap.fetch_sitemap_entries``; the
helper itself is unit-tested in
``tests/integration/test_integrations/test_sitemap.py``. Here we
verify the route plumbing — payload validation, project resolution,
response shape — using a stubbed helper so we don't depend on real
HTTP traffic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from content_stack.api import projects as projects_module
from content_stack.integrations.sitemap import (
    SitemapEntry,
    SitemapFetchError,
    SitemapFetchResult,
)


@pytest.fixture(autouse=True)
def _stub_sitemap_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the helper with a deterministic stub.

    Real fetches against arbitrary external URLs are not appropriate
    inside the test harness; we exercise the helper itself in the
    unit-test module.
    """

    async def _fake_fetch(
        urls: list[str],
        *,
        client: object | None = None,
        timeout_s: float = 15.0,
        max_index_depth: int = 2,
        max_entries: int = 5_000,
    ) -> SitemapFetchResult:
        entries: list[SitemapEntry] = []
        errors: list[SitemapFetchError] = []
        for u in urls:
            if "broken" in u:
                errors.append(SitemapFetchError(url=u, error="HTTP 404"))
                continue
            entries.append(
                SitemapEntry(
                    url=f"{u.rstrip('/')}/post-1",
                    lastmod="2026-01-02",
                    source_sitemap=u,
                )
            )
        return SitemapFetchResult(entries=entries, errors=errors)

    # Patch inside the api module's import namespace; the route imports
    # the helper inside the function body, so monkeypatch the
    # integrations.sitemap module directly.
    import content_stack.integrations.sitemap as helper_module

    monkeypatch.setattr(helper_module, "fetch_sitemap_entries", _fake_fetch)
    # Importing `projects_module` keeps the dependency referenced.
    assert projects_module is not None


def test_sitemap_fetch_returns_entries_and_errors(api: TestClient, project_id: int) -> None:
    body = {
        "urls": [
            "https://good.example/sitemap.xml",
            "https://broken.example/sitemap.xml",
        ],
        "max_entries": 100,
    }
    resp = api.post(f"/api/v1/projects/{project_id}/sitemap-fetch", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["url"].endswith("/post-1")
    assert payload["entries"][0]["lastmod"] == "2026-01-02"
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["error"] == "HTTP 404"


def test_sitemap_fetch_404_on_missing_project(api: TestClient) -> None:
    resp = api.post(
        "/api/v1/projects/9999/sitemap-fetch",
        json={"urls": ["https://example.com/sitemap.xml"]},
    )
    assert resp.status_code == 404


def test_sitemap_fetch_validates_payload(api: TestClient, project_id: int) -> None:
    # Empty url list rejected.
    resp = api.post(
        f"/api/v1/projects/{project_id}/sitemap-fetch",
        json={"urls": []},
    )
    assert resp.status_code == 422
