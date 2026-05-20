"""``integration.test`` MCP tool — M4 dispatcher (no longer a deferral)."""

from __future__ import annotations

import base64
from urllib.parse import parse_qs, urlparse

from pytest_httpx import HTTPXMock

from .conftest import MCPClient


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
    cred = mcp_client.call_tool_structured(
        "integration.set",
        {
            "project_id": project_id,
            "kind": "firecrawl",
            "plaintext_payload_b64": base64.b64encode(b"fc-key").decode("ascii"),
        },
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
    cred = mcp_client.call_tool_structured(
        "integration.set",
        {
            "project_id": project_id,
            "kind": "unknown-vendor",
            "plaintext_payload_b64": base64.b64encode(b"x").decode("ascii"),
        },
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
    cred = mcp_client.call_tool_structured(
        "integration.set",
        {
            "project_id": project_id,
            "kind": "wordpress",
            "plaintext_payload_b64": base64.b64encode(b"editor:app-pass").decode("ascii"),
            "config_json": {"wp_url": "https://wp.example"},
        },
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
    cred = mcp_client.call_tool_structured(
        "integration.set",
        {
            "project_id": project_id,
            "kind": "ghost",
            "plaintext_payload_b64": base64.b64encode(
                b"keyid:00112233445566778899aabbccddeeff"
            ).decode("ascii"),
            "config_json": {"ghost_url": "https://ghost.example", "api_version": "v5.0"},
        },
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


def test_gsc_oauth_start_returns_agent_consent_url(
    mcp_client: MCPClient,
    seeded_project: dict,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GSC_OAUTH_CLIENT_ID", "client-id-fake")
    monkeypatch.setenv("GSC_OAUTH_CLIENT_SECRET", "client-secret-fake")
    project_id = seeded_project["data"]["id"]

    out = mcp_client.call_tool_structured("gscOauth.start", {"project_id": project_id})
    parsed = urlparse(out["data"]["authorization_url"])
    params = parse_qs(parsed.query)

    assert out["project_id"] == project_id
    assert out["data"]["redirect_uri"] == (
        "http://127.0.0.1:5180/api/v1/integrations/gsc/oauth/callback"
    )
    assert params["client_id"] == ["client-id-fake"]
    assert params["state"] == [out["data"]["state"]]


def test_gsc_oauth_start_validates_missing_env(
    mcp_client: MCPClient,
    seeded_project: dict,
    monkeypatch,
) -> None:
    monkeypatch.delenv("GSC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GSC_OAUTH_CLIENT_SECRET", raising=False)

    err = mcp_client.call_tool_error(
        "gscOauth.start",
        {"project_id": seeded_project["data"]["id"]},
    )

    assert err["code"] == -32602
    assert err["message"] == "ValidationError"
    assert err["data"]["missing"] == ["GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET"]
