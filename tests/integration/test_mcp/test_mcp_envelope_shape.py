"""Every mutating tool's response carries ``{data, run_id, project_id}``.

Read tools return bare data (no envelope wrapping) per PLAN.md L754-L763.
"""

from __future__ import annotations

from .conftest import MCPClient


def test_mutating_create_carries_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Every mutating tool wraps its data in {data, run_id, project_id}."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured("topic.create", {"project_id": pid, "title": "T"})
    assert set(env.keys()) >= {"data", "run_id", "project_id"}


def test_read_topic_returns_bare_data(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Read tool returns the row data, not an envelope."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured("topic.create", {"project_id": pid, "title": "T"})
    tid = env["data"]["id"]
    bare = mcp_client.call_tool_structured("topic.get", {"topic_id": tid})
    # No 'data'/'run_id'/'project_id' wrapper — just the row.
    assert "data" not in bare
    assert bare["id"] == tid
    assert bare["title"] == "T"


def test_list_returns_page_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """List reads return Page = {items, next_cursor, total_estimate}."""
    page = mcp_client.call_tool_structured(
        "topic.list", {"project_id": seeded_project["data"]["id"]}
    )
    assert set(page.keys()) >= {"items", "next_cursor", "total_estimate"}


def test_meta_enums_returns_bare_data(mcp_client: MCPClient) -> None:
    """meta.enums is a read tool — bare payload, no wrapper."""
    payload = mcp_client.call_tool_structured("meta.enums", {})
    assert "data" not in payload
    assert "topics_status" in payload
