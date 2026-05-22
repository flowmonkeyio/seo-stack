"""Legacy vendor MCP tools are removed from the daemon catalog."""

from __future__ import annotations

from .conftest import MCPClient


def _start_run_for_skill(mcp: MCPClient, project_id: int, skill_name: str) -> str:
    env = mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "run-plan",
            "skill_name": skill_name,
        },
    )
    return env["data"]["run_token"]


def test_legacy_vendor_tool_is_unknown(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    project_id = seeded_project["data"]["id"]

    err = mcp_client.call_tool_error(
        "jina.read",
        {"project_id": project_id, "url": "https://example.com"},
    )

    assert err["code"] == -32601


def test_removed_legacy_skill_names_do_not_restore_vendor_tools(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    project_id = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, project_id, "01-research/serp-analyzer")

    err = mcp_client.call_tool_error(
        "jina.read",
        {
            "project_id": project_id,
            "url": "https://example.com",
            "run_token": token,
        },
    )

    assert err["code"] == -32601
