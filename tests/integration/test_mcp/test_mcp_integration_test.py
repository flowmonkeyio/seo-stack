"""``integration.test`` MCP tool and generic auth boundary."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from pytest_httpx import HTTPXMock

from .conftest import MCPClient


def _create_integration_credential(
    mcp: MCPClient,
    *,
    project_id: int,
    kind: str,
    payload: bytes,
    config_json: dict | None = None,
) -> dict:
    response = mcp.test_client.post(
        f"/api/v1/projects/{project_id}/integrations",
        json={
            "kind": kind,
            "plaintext_payload": payload.decode("utf-8"),
            "config_json": config_json,
        },
        headers=mcp._headers(),
    )
    response.raise_for_status()
    return response.json()


def test_integration_test_dispatches_to_firecrawl(
    mcp_client: MCPClient,
    seeded_project: dict,
    httpx_mock: HTTPXMock,
) -> None:
    """``integration.test`` dispatches via the registry to the per-vendor wrapper."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v2/scrape",
        json={"data": {"markdown": "# ok"}},
    )

    project_id = seeded_project["data"]["id"]
    cred = _create_integration_credential(
        mcp_client,
        project_id=project_id,
        kind="firecrawl",
        payload=b"fc-key",
    )
    cid = cred["data"]["id"]

    out = mcp_client.call_tool_structured(
        "integration.test",
        {"credential_id": cid},
    )
    # The wrapper returns ``{"ok": True, "vendor": "firecrawl", ...}`` wrapped in WriteEnvelope.
    assert out["data"]["ok"] is True
    assert out["data"]["vendor"] == "firecrawl"


def test_integration_test_validates_unknown_kind(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    """A credential with an unknown kind surfaces ``ValidationError`` (-32602)."""
    project_id = seeded_project["data"]["id"]
    cred = _create_integration_credential(
        mcp_client,
        project_id=project_id,
        kind="unknown-vendor",
        payload=b"x",
    )
    cid = cred["data"]["id"]
    err = mcp_client.call_tool_error(
        "integration.test",
        {"credential_id": cid},
    )
    assert err["code"] == -32602
    assert err["message"] == "ValidationError"


def test_integration_test_dispatches_to_wordpress(
    mcp_client: MCPClient,
    seeded_project: dict,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://wp.example/wp-json/wp/v2/users/me?context=edit",
        json={"id": 7, "name": "Editor", "roles": ["editor"]},
    )

    project_id = seeded_project["data"]["id"]
    cred = _create_integration_credential(
        mcp_client,
        project_id=project_id,
        kind="wordpress",
        payload=b"editor:app-pass",
        config_json={"wp_url": "https://wp.example"},
    )

    out = mcp_client.call_tool_structured(
        "integration.test",
        {"credential_id": cred["data"]["id"]},
    )
    assert out["data"]["ok"] is True
    assert out["data"]["vendor"] == "wordpress"


def test_integration_test_dispatches_to_ghost(
    mcp_client: MCPClient,
    seeded_project: dict,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://ghost.example/ghost/api/admin/users/?limit=1&include=roles",
        json={"users": [{"id": "u1", "name": "Editor", "roles": [{"name": "Editor"}]}]},
    )

    project_id = seeded_project["data"]["id"]
    cred = _create_integration_credential(
        mcp_client,
        project_id=project_id,
        kind="ghost",
        payload=b"keyid:00112233445566778899aabbccddeeff",
        config_json={"ghost_url": "https://ghost.example", "api_version": "v5.0"},
    )

    out = mcp_client.call_tool_structured(
        "integration.test",
        {"credential_id": cred["data"]["id"]},
    )
    assert out["data"]["ok"] is True
    assert out["data"]["vendor"] == "ghost"


def test_gsc_oauth_get_reports_missing_env(
    mcp_client: MCPClient,
    monkeypatch,
) -> None:
    monkeypatch.delenv("GSC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GSC_OAUTH_CLIENT_SECRET", raising=False)

    out = mcp_client.call_tool_structured("gscOauth.get", {})

    assert out["configured"] is False
    assert out["missing"] == ["GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET"]
    assert out["redirect_uri"] == "http://127.0.0.1:5180/api/v1/integrations/gsc/oauth/callback"


def test_auth_start_route_returns_gsc_consent_url(
    mcp_client: MCPClient,
    seeded_project: dict,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GSC_OAUTH_CLIENT_ID", "client-id-fake")
    monkeypatch.setenv("GSC_OAUTH_CLIENT_SECRET", "client-secret-fake")
    project_id = seeded_project["data"]["id"]

    response = mcp_client.test_client.post(
        f"/api/v1/projects/{project_id}/auth/gsc/start",
        json={},
        headers=mcp_client._headers(),
    )
    response.raise_for_status()
    out = response.json()
    parsed = urlparse(out["data"]["authorization_url"])
    params = parse_qs(parsed.query)

    assert out["project_id"] == project_id
    assert out["data"]["redirect_uri"] == (
        "http://127.0.0.1:5180/api/v1/integrations/gsc/oauth/callback"
    )
    assert params["client_id"] == ["client-id-fake"]
    assert params["state"] == [out["data"]["state"]]
    assert out["data"]["credential_ref"].startswith("cred_")


def test_auth_start_route_validates_missing_gsc_env(
    mcp_client: MCPClient,
    seeded_project: dict,
    monkeypatch,
) -> None:
    monkeypatch.delenv("GSC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GSC_OAUTH_CLIENT_SECRET", raising=False)

    response = mcp_client.test_client.post(
        f"/api/v1/projects/{seeded_project['data']['id']}/auth/gsc/start",
        json={},
        headers=mcp_client._headers(),
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == -32602
    assert body["data"]["missing"] == ["GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET"]


def test_auth_start_is_not_agent_system_granted(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    err = mcp_client.call_tool_error(
        "auth.start",
        {"project_id": seeded_project["data"]["id"], "provider_key": "gsc"},
    )

    assert err["code"] == -32007
    assert err["message"] == "ToolNotGrantedError"
