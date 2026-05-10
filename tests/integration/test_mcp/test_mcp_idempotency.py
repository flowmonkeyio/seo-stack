"""Idempotency dedup window per audit M-20 / PLAN.md L724-L727."""

from __future__ import annotations

from .conftest import MCPClient


def _run_token(mcp: MCPClient, project_id: int, skill_name: str = "_test_keyword_discovery") -> str:
    env = mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "procedure",
            "procedure_slug": skill_name,
            "skill_name": skill_name,
        },
    )
    return env["data"]["run_token"]


def test_idempotency_replay_returns_cached_envelope(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Same idempotency_key within 24h returns the cached envelope."""
    pid = seeded_project["data"]["id"]
    token = _run_token(mcp_client, pid)
    args = {
        "project_id": pid,
        "title": "Topic-X",
        "idempotency_key": "abc-123",
        "run_token": token,
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
    token = _run_token(mcp_client, pid)
    a = mcp_client.call_tool_structured(
        "topic.create",
        {"project_id": pid, "title": "T-A", "idempotency_key": "a", "run_token": token},
    )
    b = mcp_client.call_tool_structured(
        "topic.create",
        {"project_id": pid, "title": "T-B", "idempotency_key": "b", "run_token": token},
    )
    assert a["data"]["id"] != b["data"]["id"]


def test_failed_call_does_not_poison_idempotency_key(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """A failed fresh call releases the key so a corrected retry can succeed."""
    pid = seeded_project["data"]["id"]
    token = _run_token(mcp_client, pid, "01-research/content-brief")
    mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "Original", "slug": "same", "run_token": token},
    )
    err = mcp_client.call_tool_error(
        "article.create",
        {
            "project_id": pid,
            "title": "Duplicate",
            "slug": "same",
            "idempotency_key": "retry-after-failure",
            "run_token": token,
        },
    )
    assert err["code"] in {-32008, -32603}

    fixed = mcp_client.call_tool_structured(
        "article.create",
        {
            "project_id": pid,
            "title": "Fixed",
            "slug": "fixed",
            "idempotency_key": "retry-after-failure",
            "run_token": token,
        },
    )
    assert fixed["data"]["slug"] == "fixed"
