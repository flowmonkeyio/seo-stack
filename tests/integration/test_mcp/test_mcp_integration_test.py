"""``integration.test`` MCP tool — M4 dispatcher (no longer a deferral)."""

from __future__ import annotations

import base64

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
