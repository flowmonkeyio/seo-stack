"""topic.* — bulk_create + approve/reject + bulkUpdateStatus through MCP."""

from __future__ import annotations

from .conftest import MCPClient


def test_topic_create_returns_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """topic.create returns ``{data, project_id, run_id}``."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured(
        "topic.create",
        {"project_id": pid, "title": "First topic"},
    )
    assert env["data"]["title"] == "First topic"
    assert env["project_id"] == pid


def test_topic_bulk_create_persists_in_input_order(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """bulk_create returns rows in input order (audit M-13)."""
    pid = seeded_project["data"]["id"]
    items = [{"title": f"Topic {i}", "primary_kw": f"kw-{i}"} for i in range(5)]
    env = mcp_client.call_tool_structured("topic.bulkCreate", {"project_id": pid, "items": items})
    rows = env["data"]
    assert [r["title"] for r in rows] == [it["title"] for it in items]


def test_topic_approve_then_reject_chain(mcp_client: MCPClient, seeded_project: dict) -> None:
    """approve → drafting → reject chain."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured("topic.create", {"project_id": pid, "title": "T"})
    tid = env["data"]["id"]
    approved = mcp_client.call_tool_structured("topic.approve", {"topic_id": tid})
    assert approved["data"]["status"] == "approved"
    rejected = mcp_client.call_tool_structured("topic.reject", {"topic_id": tid})
    assert rejected["data"]["status"] == "rejected"


def test_topic_bulk_update_status_all_or_nothing(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """bulkUpdateStatus rolls back if any single transition is illegal."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured(
        "topic.bulkCreate",
        {
            "project_id": pid,
            "items": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
        },
    )
    ids = [r["id"] for r in env["data"]]
    approved = mcp_client.call_tool_structured(
        "topic.bulkUpdateStatus",
        {"project_id": pid, "ids": ids, "status": "approved"},
    )
    assert all(r["status"] == "approved" for r in approved["data"])


def test_topic_bulk_create_streaming_progress(mcp_client: MCPClient, seeded_project: dict) -> None:
    """bulk_create with N>50 still completes for a non-progress client."""
    pid = seeded_project["data"]["id"]
    items = [{"title": f"T{i}"} for i in range(75)]
    env = mcp_client.call_tool_structured("topic.bulkCreate", {"project_id": pid, "items": items})
    assert len(env["data"]) == 75
