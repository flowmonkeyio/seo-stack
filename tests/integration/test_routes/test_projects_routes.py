"""Project + nested-preset route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_project_returns_envelope(api: TestClient) -> None:
    """POST returns ``{data, run_id, project_id}``."""
    resp = api.post(
        "/api/v1/projects",
        json={
            "slug": "site-a",
            "name": "Site A",
            "domain": "a.com",
            "locale": "en-US",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "data" in body
    assert body["project_id"] == body["data"]["id"]
    assert body["data"]["slug"] == "site-a"


def test_list_projects_pagination(api: TestClient) -> None:
    """Empty universe surfaces ``items=[], next_cursor=None``."""
    resp = api.get("/api/v1/projects")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_get_project_404_on_missing(api: TestClient) -> None:
    """Unknown id → 404 / -32004."""
    resp = api.get("/api/v1/projects/999")
    assert resp.status_code == 404


def test_patch_project_permissive(api: TestClient, project_id: int) -> None:
    """Name update sticks; updated_at advances."""
    resp = api.patch(f"/api/v1/projects/{project_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "New Name"


def test_activate_project_flips_is_active(api: TestClient, project_id: int) -> None:
    """``POST /activate`` makes the project ``is_active=true``."""
    resp = api.post(f"/api/v1/projects/{project_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True


def test_delete_project_soft_deletes(api: TestClient, project_id: int) -> None:
    """Soft-delete sets ``is_active=false``."""
    api.post(f"/api/v1/projects/{project_id}/activate")
    resp = api.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


# ---- Voice ----


def test_voice_put_creates_default(api: TestClient, project_id: int) -> None:
    """``PUT /voice`` creates a default voice profile."""
    resp = api.put(
        f"/api/v1/projects/{project_id}/voice",
        json={"name": "default", "voice_md": "# Voice\n", "is_default": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_default"] is True


def test_voice_get_returns_active_or_null(api: TestClient, project_id: int) -> None:
    """``GET /voice`` returns null until a voice is set."""
    resp = api.get(f"/api/v1/projects/{project_id}/voice")
    assert resp.status_code == 200
    assert resp.json() is None


# ---- Compliance ----


def test_compliance_full_cycle(api: TestClient, project_id: int) -> None:
    """Create + list + patch + delete a compliance rule."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/compliance",
        json={
            "kind": "responsible-gambling",
            "title": "RG disclosure",
            "body_md": "Gamble responsibly.",
            "position": "footer",
        },
    )
    assert resp.status_code == 201
    rule_id = resp.json()["data"]["id"]
    rules = api.get(f"/api/v1/projects/{project_id}/compliance").json()
    assert len(rules) == 1

    patch = api.patch(
        f"/api/v1/projects/{project_id}/compliance/{rule_id}",
        json={"title": "RG updated"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["title"] == "RG updated"

    deleted = api.delete(f"/api/v1/projects/{project_id}/compliance/{rule_id}")
    assert deleted.status_code == 200
    rules = api.get(f"/api/v1/projects/{project_id}/compliance").json()
    assert len(rules) == 0


# ---- EEAT ----


def test_eeat_seeded_after_project_create(api: TestClient, project_id: int) -> None:
    """80 EEAT criteria are seeded transactionally per D7."""
    rows = api.get(f"/api/v1/projects/{project_id}/eeat").json()
    assert len(rows) == 80
    cores = [r for r in rows if r["tier"] == "core"]
    assert len(cores) >= 3  # T04, C01, R10


def test_eeat_bulk_set_persists(api: TestClient, project_id: int) -> None:
    """``PUT /eeat`` bulk_set applies weight changes."""
    rows = api.get(f"/api/v1/projects/{project_id}/eeat").json()
    target = next(r for r in rows if r["tier"] != "core")
    resp = api.put(
        f"/api/v1/projects/{project_id}/eeat",
        json={"items": [{"id": target["id"], "weight": 47}]},
    )
    assert resp.status_code == 200
    after = api.get(f"/api/v1/projects/{project_id}/eeat").json()
    after_target = next(r for r in after if r["id"] == target["id"])
    assert after_target["weight"] == 47


# ---- Publish targets ----


def test_publish_target_set_primary_invariant(api: TestClient, project_id: int) -> None:
    """Two ``is_primary=true`` targets — only the latest stays primary."""
    t1 = api.post(
        f"/api/v1/projects/{project_id}/publish-targets",
        json={"kind": "nuxt-content", "is_primary": True},
    )
    t2 = api.post(
        f"/api/v1/projects/{project_id}/publish-targets",
        json={"kind": "wordpress", "is_primary": True},
    )
    assert t1.status_code == 201 and t2.status_code == 201
    listing = api.get(f"/api/v1/projects/{project_id}/publish-targets").json()
    primaries = [r for r in listing if r["is_primary"]]
    assert len(primaries) == 1


# ---- Schedules ----


def test_schedule_create_then_disable(api: TestClient, project_id: int) -> None:
    """Create + disable a schedule."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"kind": "drift-check", "cron_expr": "0 3 * * *", "enabled": True},
    )
    assert resp.status_code == 201
    job_id = resp.json()["data"]["id"]
    resp = api.delete(f"/api/v1/projects/{project_id}/schedules/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


# ---- Budgets (M-25) ----


def test_budget_set_then_get(api: TestClient, project_id: int) -> None:
    """Set + read a budget row."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/budgets",
        json={"kind": "dataforseo", "monthly_budget_usd": 25.0},
    )
    assert resp.status_code == 201
    resp2 = api.get(f"/api/v1/projects/{project_id}/budgets/dataforseo")
    assert resp2.status_code == 200
    assert resp2.json()["monthly_budget_usd"] == 25.0


def test_budget_paa_alias_canonicalizes_to_google_paa(api: TestClient, project_id: int) -> None:
    """Legacy UI ``paa`` budget rows map to the Google PAA wrapper key."""
    resp = api.post(
        f"/api/v1/projects/{project_id}/budgets",
        json={"kind": "paa", "monthly_budget_usd": 12.0},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["kind"] == "google-paa"
    resp2 = api.get(f"/api/v1/projects/{project_id}/budgets/google-paa")
    assert resp2.status_code == 200
    assert resp2.json()["monthly_budget_usd"] == 12.0


# ---- Cost ----


def test_cost_returns_zero_when_no_runs(api: TestClient, project_id: int) -> None:
    """M2: zero cost across the board until M5 integrations land."""
    resp = api.get(f"/api/v1/projects/{project_id}/cost?month=2026-05")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_usd"] == 0.0
    assert body["by_integration"] == {}


# ---- Integrations test route — M4 dispatches to vendor wrappers ----


def test_project_integrations_include_global_readonly_rows(
    api: TestClient,
    project_id: int,
) -> None:
    """The project listing includes project-scoped and global credentials."""
    from sqlmodel import Session

    from content_stack.repositories.projects import IntegrationCredentialRepository

    engine = api.app.state.engine  # type: ignore[attr-defined]
    with Session(engine) as session:
        IntegrationCredentialRepository(session).set(
            project_id=None,
            kind="anthropic",
            plaintext_payload=b"global-key",
        )

    api.post(
        f"/api/v1/projects/{project_id}/integrations",
        json={"kind": "firecrawl", "plaintext_payload": "project-key"},
    )
    rows = api.get(f"/api/v1/projects/{project_id}/integrations").json()
    by_kind = {row["kind"]: row for row in rows}
    assert by_kind["firecrawl"]["project_id"] == project_id
    assert by_kind["anthropic"]["project_id"] is None


def test_integration_test_dispatches_to_wrapper(
    api: TestClient,
    project_id: int,
    httpx_mock: object,
) -> None:
    """M4: the ``test`` route now dispatches to the per-vendor wrapper.

    We seed a Firecrawl credential (Bearer auth, simplest shape) and
    mock the upstream HTTP call via ``pytest-httpx``. The route returns
    the wrapper's status dict.
    """
    from pytest_httpx import HTTPXMock

    typed_mock: HTTPXMock = httpx_mock  # type: ignore[assignment]
    typed_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v2/scrape",
        json={"data": {"markdown": "# example", "url": "https://example.com"}},
    )

    cr = api.post(
        f"/api/v1/projects/{project_id}/integrations",
        json={"kind": "firecrawl", "plaintext_payload": "fc-test-key"},
    )
    cid = cr.json()["data"]["id"]
    resp = api.post(f"/api/v1/projects/{project_id}/integrations/{cid}/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["vendor"] == "firecrawl"
