"""Idempotency dedup window per audit M-20 / PLAN.md L724-L727."""

from __future__ import annotations

from .conftest import MCPClient


def test_idempotency_replay_returns_cached_envelope(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Same idempotency_key within 24h returns the cached envelope."""
    pid = seeded_project["data"]["id"]
    args = {
        "project_id": pid,
        "title": "Topic-X",
        "idempotency_key": "abc-123",
    }
    first = mcp_client.call_tool_structured("topic.create", args)
    second = mcp_client.call_tool_structured("topic.create", args)
    # Both responses carry the same row id (proof of replay).
    assert first["data"]["id"] == second["data"]["id"]


def test_idempotency_different_keys_create_distinct_rows(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Different idempotency_keys are distinct calls."""
    pid = seeded_project["data"]["id"]
    a = mcp_client.call_tool_structured(
        "topic.create",
        {"project_id": pid, "title": "T-A", "idempotency_key": "a"},
    )
    b = mcp_client.call_tool_structured(
        "topic.create",
        {"project_id": pid, "title": "T-B", "idempotency_key": "b"},
    )
    assert a["data"]["id"] != b["data"]["id"]
